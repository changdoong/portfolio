"""검출 → 추적 → 위험 분석 → 시각화/로깅 파이프라인.

추적기 종류에 따라 프레임당 검출기 호출은 정확히 1회:
  bytetrack : detector.track(frame)  → ByteTrackAdapter   (ByteTrack 은 ultralytics 내부에서 1회 실행)
  iou       : detector.detect(frame) → IoUTracker

성능 측정
  Inference FPS : 모델 forward 시간만 (ultralytics result.speed["inference"], ms)
  Pipeline FPS  : source.read() 시작 ~ 검출·추적·위험분석·시각화·저장/화면출력 종료 (wall-clock)
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Dict, List, Optional

import cv2
import numpy as np

from src.risk.near_miss import NearMissDetector, PairRisk
from src.risk.zone import Zone, ZoneMonitor
from src.tracking.tracker import Track, build_tracker
from src.utils.metrics import EventLogger, FPSMeter, LatencyStats
from src.video.video_source import create_source

logger = logging.getLogger(__name__)

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

                detections = self._infer(frame)
                speed = getattr(self.detector, "last_speed", None) or {}
                for k in ("inference", "preprocess", "postprocess"):
                    stats[k].add(speed.get(k))
                if getattr(self.detector, "last_untracked", 0):
                    untracked_frames += 1

                tracks = self.tracker.update(detections)
                zone_events = self.zone_monitor.update(tracks, frame_idx)
                risks, nm_events = near_miss.update(tracks, frame_idx)
                self._log(event_logger, zone_events + nm_events)

                self.fps_meter.tick()
                vis = self.draw(frame, tracks, risks, speed.get("inference"))

                if ocfg.get("save_video"):
                    if writer is None:
                        os.makedirs(os.path.dirname(ocfg["video_path"]) or ".", exist_ok=True)
                        h, w = vis.shape[:2]
                        writer = cv2.VideoWriter(ocfg["video_path"], cv2.VideoWriter_fourcc(*"mp4v"), src_fps, (w, h))
                        if not writer.isOpened():
                            raise IOError(f"VideoWriter 를 열 수 없습니다: {ocfg['video_path']}")
                    writer.write(vis)

                stop = False
                if ocfg.get("show_window"):
                    cv2.imshow("Near-Miss Analyzer", vis)
                    stop = (cv2.waitKey(1) & 0xFF) in (ord("q"), 27)

                stats["pipeline"].add((time.perf_counter() - t0) * 1000.0)
                frame_idx += 1
                if stop:
                    break

            last = max(frame_idx - 1, 0)
            self._log(event_logger, self.zone_monitor.close(last) + near_miss.close(last))
        finally:
            self.source.release()
            event_logger.close()
            if writer is not None:
                writer.release()
            if ocfg.get("show_window"):
                cv2.destroyAllWindows()

        total_sec = time.perf_counter() - t_start
        self.perf = self._perf_report(stats, frame_idx, total_sec, frame_size, untracked_frames)
        perf_path = ocfg.get("perf_path") or os.path.join(os.path.dirname(ocfg["event_log"]) or ".", "perf.json")
        with open(perf_path, "w", encoding="utf-8") as f:
            json.dump(self.perf, f, ensure_ascii=False, indent=2)

        summary = event_logger.summary()
        logger.info("처리 프레임: %d, 이벤트 요약: %s", frame_idx, summary)
        logger.info("Inference: %s", self.perf["inference_ms"])
        logger.info("Pipeline : %s", self.perf["pipeline_ms"])
        return summary

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
            x1, y1, x2, y2 = t.bbox.astype(int)
            cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)
            cv2.putText(vis, f"{t.category} #{t.track_id}", (x1, y1 - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
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
