"""검출 → 추적 → 위험 분석 → 시각화/로깅 파이프라인.

추적기 종류에 따라 프레임당 검출기 호출은 정확히 1회:
  bytetrack : detector.track(frame)  → ByteTrackAdapter   (ByteTrack 은 ultralytics 내부에서 1회 실행)
  iou       : detector.detect(frame) → IoUTracker

성능 측정
  Inference FPS : 모델 forward 시간만 (ultralytics result.speed["inference"], ms)
  Pipeline FPS  : source.read() 시작 ~ 검출·추적·위험분석·시각화·저장/화면출력 종료 (wall-clock)

선택 기능 (설정이 없으면 비활성화 → 기존 동작과 동일)
  output.track_log   : 프레임별 확정 트랙 CSV (frame, track_id, category, class_name, score, bbox, 하단 중앙)
  output.frame_log   : 프레임별 검출/트랙 수 + 구간 시간 CSV
  perf.stage_timing  : 구간별 시간 통계(read / detector / track_risk / draw / encode / display)를 perf.json 에 추가
  meta               : domain(real_cctv | synthetic) / dataset / clip 을 perf.json conditions 에 기록
  analysis           : ID 병합(canonical_track_id) / 정지 물체 필터 / 운전자 구분 (src/risk/track_analysis.py)
                       output.merge_log / static_log / role_log 로 판정 근거 CSV 기록
"""
from __future__ import annotations

import csv
import json
import logging
import os
import time
from typing import Dict, List, Optional

import cv2
import numpy as np

from src.risk.near_miss import NearMissDetector, PairRisk
from src.risk.track_analysis import TrackAnalyzer
from src.risk.zone import Zone, ZoneMonitor
from src.tracking.tracker import Track, build_tracker
from src.utils.metrics import EventLogger, FPSMeter, LatencyStats
from src.video.video_source import create_source

logger = logging.getLogger(__name__)

def _r(v: Optional[float], nd: int = 3):
    return None if v is None else round(float(v), nd)


class _CsvLog:
    """경로가 주어졌을 때만 동작하는 CSV 기록기 (None 이면 아무것도 하지 않음)."""

    def __init__(self, path: Optional[str], header: List[str]):
        self.enabled = bool(path)
        self._f = self._w = None
        if self.enabled:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            self._f = open(path, "w", newline="", encoding="utf-8")
            self._w = csv.writer(self._f)
            self._w.writerow(header)

    def write(self, row) -> None:
        self._w.writerow(row)

    def close(self) -> None:
        if self._f is not None:
            self._f.close()
            self._f = None


CATEGORY_COLORS = {"person": (80, 220, 80), "vehicle": (255, 160, 40)}
SEVERITY_COLORS = {"danger": (0, 0, 255), "warning": (0, 200, 255)}


class NearMissPipeline:
    def __init__(self, cfg: Dict, detector=None):
        """detector 를 주입하면 YOLO 대신 사용 (테스트/다른 모델 교체용)."""
        self.cfg = cfg
        vcfg = cfg["video"]
        self.source = create_source(vcfg["source"], vcfg.get("resize_width"), **vcfg.get("rtsp", {}))

        self.tracker_type, self.tracker = build_tracker(cfg["tracking"])

        if detector is None:
            from src.detection.detector import YOLODetector

            dcfg = cfg["detection"]
            detector = YOLODetector(
                model=dcfg["model"], class_map=dcfg.get("class_map"), conf=dcfg["conf"],
                iou=dcfg["iou"], device=dcfg["device"], imgsz=dcfg.get("imgsz", 640),
                half=dcfg.get("half", False),
                tracker_cfg=cfg["tracking"].get("tracker_config", "bytetrack.yaml"),
            )
        if self.tracker_type == "bytetrack" and not hasattr(detector, "track"):
            raise TypeError("tracking.type=bytetrack 에는 track() 을 제공하는 검출기가 필요합니다.")
        self.detector = detector

        rcfg = cfg["risk"]
        zev = rcfg.get("zone_events")   # 없으면 이전 버전 동작
        self.zone_monitor = ZoneMonitor(
            [Zone.from_config(z) for z in rcfg.get("zones", [])],
            release_frames=None if zev is None else zev.get("release_frames", 15),
            cooldown_frames=0 if zev is None else zev.get("cooldown_frames", 90),
        )
        self.fps_meter = FPSMeter()
        self.perf: Dict = {}
        self.analyzer = TrackAnalyzer.from_config(cfg.get("analysis"))   # 설정 없으면 None (기존 동작)
        self._show_ttc = False   # TTC 가 판정에 쓰일 때만 화면에 표시

    # ------------------------------------------------------------------
    def _infer(self, frame: np.ndarray):
        """프레임당 검출기 호출 1회. 추적기 종류에 맞는 메서드만 호출한다."""
        if self.tracker_type == "bytetrack":
            return self.detector.track(frame)
        return self.detector.detect(frame)

    def run(self, max_frames: Optional[int] = None) -> Dict[str, int]:
        ocfg = self.cfg["output"]
        warmup = self.cfg.get("perf", {}).get("warmup_frames", 10)
        self.source.open()
        src_fps = self.source.fps
        near_miss = NearMissDetector(fps=src_fps, **self.cfg["risk"]["near_miss"])
        self._show_ttc = near_miss.enable_ttc
        self.zone_monitor.set_fps(src_fps)
        event_logger = EventLogger(ocfg["event_log"], src_fps)
        if hasattr(self.detector, "reset_tracking"):
            self.detector.reset_tracking()

        stats = {k: LatencyStats(warmup) for k in ("pipeline", "inference", "preprocess", "postprocess")}
        stage_timing = bool(self.cfg.get("perf", {}).get("stage_timing", False))
        stage_keys = ("read", "detector", "track_risk", "draw", "encode", "display")
        stage_stats = {k: LatencyStats(warmup) for k in stage_keys} if stage_timing else None
        track_cols = ["frame", "track_id", "category", "class_name", "score", "x1", "y1", "x2", "y2", "foot_x", "foot_y"]
        if self.analyzer:
            track_cols += ["canonical_track_id", "vehicle_status", "person_role"]
        track_log = _CsvLog(ocfg.get("track_log"), track_cols)
        frame_log = _CsvLog(ocfg.get("frame_log"), ["frame", "det_person", "det_vehicle", "track_person",
                                                      "track_vehicle", "untracked", "inference_ms",
                                                      "read_ms", "detector_ms", "track_risk_ms", "draw_ms",
                                                      "encode_ms", "display_ms", "pipeline_ms"])
        names = getattr(getattr(self.detector, "model", None), "names", None) or {}
        writer = None
        frame_idx = 0
        frame_size = None
        untracked_frames = 0
        t_start = time.perf_counter()

        try:
            while max_frames is None or frame_idx < max_frames:
                t0 = time.perf_counter()
                frame = self.source.read()
                if frame is None:
                    break
                frame_size = frame.shape[1], frame.shape[0]
                t_read = time.perf_counter()

                detections = self._infer(frame)
                t_det = time.perf_counter()
                speed = getattr(self.detector, "last_speed", None) or {}
                for k in ("inference", "preprocess", "postprocess"):
                    stats[k].add(speed.get(k))
                untracked = getattr(self.detector, "last_untracked", 0)
                if untracked:
                    untracked_frames += 1

                tracks = self.tracker.update(detections)
                views, risk_tracks, exclude = tracks, tracks, None
                if self.analyzer:
                    views, risk_tracks, exclude = self.analyzer.process(tracks, frame_idx, frame.shape[0])
                zone_events = self.zone_monitor.update(views, frame_idx)
                risks, nm_events = near_miss.update(risk_tracks, frame_idx, exclude_pairs=exclude)
                self._log(event_logger, zone_events + nm_events)
                t_risk = time.perf_counter()

                self.fps_meter.tick()
                vis = self.draw(frame, views, risks, speed.get("inference"))
                t_draw = time.perf_counter()

                if ocfg.get("save_video"):
                    if writer is None:
                        os.makedirs(os.path.dirname(ocfg["video_path"]) or ".", exist_ok=True)
                        h, w = vis.shape[:2]
                        writer = cv2.VideoWriter(ocfg["video_path"], cv2.VideoWriter_fourcc(*"mp4v"), src_fps, (w, h))
                        if not writer.isOpened():
                            raise IOError(f"VideoWriter 를 열 수 없습니다: {ocfg['video_path']}")
                    writer.write(vis)
                t_enc = time.perf_counter()

                stop = False
                if ocfg.get("show_window"):
                    cv2.imshow("Near-Miss Analyzer", vis)
                    stop = (cv2.waitKey(1) & 0xFF) in (ord("q"), 27)
                t_end = time.perf_counter()

                pipeline_ms = (t_end - t0) * 1000.0
                stats["pipeline"].add(pipeline_ms)
                stage_ms = dict(zip(stage_keys, ((b - a) * 1000.0 for a, b in
                                                 ((t0, t_read), (t_read, t_det), (t_det, t_risk),
                                                  (t_risk, t_draw), (t_draw, t_enc), (t_enc, t_end)))))
                if stage_stats is not None:
                    for k, v in stage_ms.items():
                        stage_stats[k].add(v)
                if track_log.enabled:
                    cls_of = {d.track_id: d.class_id for d in detections if d.track_id is not None}
                    for t in views:
                        raw = getattr(t, "raw_track_id", t.track_id)
                        cid = cls_of.get(raw)
                        fx, fy = t.foot_point
                        row = [frame_idx, raw, t.category, names.get(cid, "") if cid is not None else "",
                               round(t.score, 3), *(round(float(v), 1) for v in t.bbox),
                               round(float(fx), 1), round(float(fy), 1)]
                        if self.analyzer:
                            row += [t.track_id, t.vehicle_status or "", t.person_role or ""]
                        track_log.write(row)
                if frame_log.enabled:
                    frame_log.write([frame_idx,
                                     sum(d.category == "person" for d in detections),
                                     sum(d.category == "vehicle" for d in detections),
                                     sum(t.category == "person" for t in tracks),
                                     sum(t.category == "vehicle" for t in tracks),
                                     untracked, _r(speed.get("inference")),
                                     *(_r(stage_ms[k]) for k in stage_keys), _r(pipeline_ms)])
                frame_idx += 1
                if stop:
                    break

            last = max(frame_idx - 1, 0)
            self._log(event_logger, self.zone_monitor.close(last) + near_miss.close(last))
        finally:
            self.source.release()
            event_logger.close()
            track_log.close()
            frame_log.close()
            if writer is not None:
                writer.release()
            if ocfg.get("show_window"):
                cv2.destroyAllWindows()

        total_sec = time.perf_counter() - t_start
        self.perf = self._perf_report(stats, frame_idx, total_sec, frame_size, untracked_frames)
        if stage_stats is not None:
            self.perf["stage_ms"] = {k: s.summary() for k, s in stage_stats.items()}
        if self.analyzer:
            self.perf["analysis"] = self.analyzer.summary()
            self._write_analysis_logs(ocfg)
        if self.cfg.get("meta"):
            self.perf["conditions"].update({k: self.cfg["meta"].get(k) for k in ("domain", "dataset", "clip")})
        perf_path = ocfg.get("perf_path") or os.path.join(os.path.dirname(ocfg["event_log"]) or ".", "perf.json")
        with open(perf_path, "w", encoding="utf-8") as f:
            json.dump(self.perf, f, ensure_ascii=False, indent=2)

        summary = event_logger.summary()
        logger.info("처리 프레임: %d, 이벤트 요약: %s", frame_idx, summary)
        logger.info("Inference: %s", self.perf["inference_ms"])
        logger.info("Pipeline : %s", self.perf["pipeline_ms"])
        return summary

    def _write_analysis_logs(self, ocfg: Dict) -> None:
        a = self.analyzer
        for key, rows in (("merge_log", a.merger.merges if a.merger else None),
                          ("static_log", a.static.log if a.static else None),
                          ("role_log", a.role.log if a.role else None)):
            path = ocfg.get(key)
            if not path or rows is None:
                continue
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", newline="", encoding="utf-8") as f:
                fields = list(rows[0].keys()) if rows else ["frame"]
                w = csv.DictWriter(f, fieldnames=fields)
                w.writeheader()
                w.writerows(rows)

    # ------------------------------------------------------------------
    @staticmethod
    def _log(event_logger: EventLogger, events: List[Dict]) -> None:
        event_logger.log(events)
        for e in events:
            logger.info("[%s] %s", str(e.get("severity")).upper(), e)

    def _perf_report(self, stats, frames, total_sec, frame_size, untracked_frames) -> Dict:
        inf = stats["inference"].summary()
        ocfg = self.cfg["output"]
        return {
            "frames": frames,
            "wall_time_sec": round(total_sec, 3),
            "overall_fps": round(frames / total_sec, 2) if total_sec > 0 else None,
            "inference_ms": inf if inf["count"] else "N/A (검출기가 inference 시간을 제공하지 않음)",
            "preprocess_ms": stats["preprocess"].summary(),
            "postprocess_ms": stats["postprocess"].summary(),
            "pipeline_ms": stats["pipeline"].summary(),
            "frames_with_untracked_detections": untracked_frames,
            "conditions": {
                "source": str(self.cfg["video"]["source"]),
                "frame_size": frame_size,
                "model": getattr(self.detector, "model_path", type(self.detector).__name__),
                "device": getattr(self.detector, "device", None),
                "half": getattr(self.detector, "half", None),
                "imgsz": getattr(self.detector, "imgsz", None),
                "tracker": self.tracker_type,
                "show_window": bool(ocfg.get("show_window")),
                "save_video": bool(ocfg.get("save_video")),
            },
        }

    # ------------------------------------------------------------------
    def draw(self, frame: np.ndarray, tracks: List[Track], risks: List[PairRisk],
             inference_ms: Optional[float] = None) -> np.ndarray:
        vis = frame.copy()
        self.zone_monitor.draw(vis)
        by_id = {t.track_id: t for t in tracks}

        for t in tracks:
            color = CATEGORY_COLORS.get(t.category, (200, 200, 200))
            label = f"{t.category} #{t.track_id}"
            raw = getattr(t, "raw_track_id", t.track_id)
            if raw != t.track_id:
                label += f" (raw {raw})"
            status, role = getattr(t, "vehicle_status", None), getattr(t, "person_role", None)
            if status in ("static", "ignored_zone"):
                color, label = (150, 150, 150), label + f" [{status}]"
            if role == "driver":
                color, label = (150, 150, 150), label + " [driver]"
            x1, y1, x2, y2 = t.bbox.astype(int)
            cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)
            cv2.putText(vis, label, (x1, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            pts = np.array(t.history, dtype=np.int32)
            if len(pts) > 1:
                cv2.polylines(vis, [pts.reshape(-1, 1, 2)], False, color, 1)
            cv2.circle(vis, tuple(t.foot_point.astype(int)), 4, color, -1)   # 거리 기준점

        n_alert = 0
        for r in risks:
            if r.severity is None:
                continue
            n_alert += 1
            p, v = by_id[r.person_id], by_id[r.vehicle_id]
            c = SEVERITY_COLORS[r.severity]
            a, b = tuple(p.foot_point.astype(int)), tuple(v.foot_point.astype(int))
            cv2.line(vis, a, b, c, 3)
            label = f"{r.severity.upper()} {r.distance:.0f}px"
            if r.ttc is not None and self._show_ttc:
                label += f" TTC {r.ttc:.1f}s"
            mid = ((a[0] + b[0]) // 2, (a[1] + b[1]) // 2)
            cv2.putText(vis, label, mid, cv2.FONT_HERSHEY_SIMPLEX, 0.6, c, 2)

        inf = f"{inference_ms:5.1f}ms" if inference_ms is not None else "  N/A"
        hud = f"Pipeline {self.fps_meter.fps:5.1f} FPS | infer {inf} | tracks {len(tracks)} | alerts {n_alert}"
        cv2.rectangle(vis, (0, 0), (600, 32), (0, 0, 0), -1)
        cv2.putText(vis, hud, (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        return vis
