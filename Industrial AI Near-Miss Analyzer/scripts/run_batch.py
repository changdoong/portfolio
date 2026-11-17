"""여러 영상 × 실행 조건(정밀도 × 영상 저장)을 일괄 실행하고 성능·추적 통계를 정리한다.

    .\\.venv\\Scripts\\python.exe scripts\\run_batch.py --videos configs\\day2_videos.yaml

출력 (outputs/ 는 Git 제외)
  outputs/day2/<video_id>/<fp16|fp32>_save_<on|off>/
      perf.json  events.csv  tracks.csv  frames.csv  resource.json  run.json  [result.mp4]
  outputs/day2/summary.json, summary.md

측정 조건
  - 실행 전 전체 워밍업 1회(첫 영상 30프레임, 결과 미사용) → CUDA 초기화/cudnn 튜닝 영향 제거
  - 각 실행의 처음 perf.warmup_frames 프레임은 FPS 통계에서 제외
  - 화면 출력 OFF. 파일 입력이므로 실시간 속도 제한 없이 최대 처리량을 측정
  - 리소스: 0.5초 간격 샘플링, GPU 값은 장치 전체 기준(다른 프로세스 포함), 실행 전 유휴 baseline 함께 기록
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
import logging
import os
import sys
import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.pipeline import NearMissPipeline  # noqa: E402
from src.utils.resource_monitor import ResourceMonitor  # noqa: E402

logger = logging.getLogger("run_batch")


# ----------------------------------------------------------------------
# 설정 구성
# ----------------------------------------------------------------------
def deep_merge(base: Dict, over: Dict) -> Dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def run_tag(precision: str, save: bool) -> str:
    return f"{precision}_save_{'on' if save else 'off'}"


def build_run_cfg(base: Dict, batch: Dict, video: Dict, precision: str, save: bool, out_root: str) -> Tuple[Dict, str]:
    if precision not in ("fp16", "fp32"):
        raise ValueError(f"precision 은 fp16 | fp32: {precision}")
    run_dir = os.path.join(out_root, video["id"], run_tag(precision, save))
    cfg = deep_merge(base, batch.get("overrides", {}))
    cfg["video"]["source"] = video["path"]
    cfg.setdefault("detection", {})["half"] = precision == "fp16"
    cfg["output"].update({
        "save_video": bool(save),
        "video_path": os.path.join(run_dir, "result.mp4"),
        "event_log": os.path.join(run_dir, "events.csv"),
        "perf_path": os.path.join(run_dir, "perf.json"),
        "track_log": os.path.join(run_dir, "tracks.csv"),
        "frame_log": os.path.join(run_dir, "frames.csv"),
        "merge_log": os.path.join(run_dir, "merge_log.csv"),     # analysis 활성 시에만 생성
        "static_log": os.path.join(run_dir, "static_log.csv"),
        "role_log": os.path.join(run_dir, "role_log.csv"),
        "show_window": False,
    })
    cfg["meta"] = {**batch.get("meta", {}), "clip": video["id"]}
    return cfg, run_dir


# ----------------------------------------------------------------------
# 통계
# ----------------------------------------------------------------------
def _num(x) -> Optional[float]:
    return None if x in (None, "", "None") else float(x)


def track_stats(tracks_csv: str, short_len: int = 10, long_len: int = 30) -> Dict:
    """ByteTrack ID 통계. 정답 라벨이 없으므로 ID 전환 횟수는 산출하지 않는다."""
    frames_by_id: Dict[Tuple[str, int], List[int]] = defaultdict(list)
    classes_by_id: Dict[Tuple[str, int], set] = defaultdict(set)
    with open(tracks_csv, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            key = (r["category"], int(r["track_id"]))
            frames_by_id[key].append(int(r["frame"]))
            if r["class_name"]:
                classes_by_id[key].add(r["class_name"])
    out = {}
    for cat in ("person", "vehicle"):
        lens = sorted((len(v) for (c, _), v in frames_by_id.items() if c == cat), reverse=True)
        ids = sorted(tid for (c, tid) in frames_by_id if c == cat)
        spans = [max(v) - min(v) + 1 for (c, _), v in frames_by_id.items() if c == cat]
        gaps = [s - n for s, n in zip(spans, [len(v) for (c, _), v in frames_by_id.items() if c == cat])]
        out[cat] = {
            "unique_ids": len(ids),
            "ids": ids,
            "lifetime_frames_mean": round(sum(lens) / len(lens), 1) if lens else 0,
            "lifetime_frames_max": lens[0] if lens else 0,
            f"tracks_ge_{long_len}f": sum(n >= long_len for n in lens),
            f"tracks_lt_{short_len}f": sum(n < short_len for n in lens),
            "tracks_with_gaps": sum(g > 0 for g in gaps),
            "coco_classes": sorted({c for (cc, _), s in classes_by_id.items() if cc == cat for c in s}),
        }
    return out


def frame_stats(frames_csv: str) -> Dict:
    rows = list(csv.DictReader(open(frames_csv, encoding="utf-8")))
    n = len(rows)
    out = {"frames": n}
    for key in ("det_person", "det_vehicle", "track_person", "track_vehicle"):
        vals = [int(r[key]) for r in rows]
        out[key] = {"frames_with": sum(v > 0 for v in vals), "ratio": round(sum(v > 0 for v in vals) / n, 3) if n else 0,
                    "mean": round(sum(vals) / n, 2) if n else 0, "max": max(vals) if vals else 0}
    both = sum(int(r["det_person"]) > 0 and int(r["det_vehicle"]) > 0 for r in rows)
    out["det_both_ratio"] = round(both / n, 3) if n else 0
    out["frames_untracked"] = sum(int(r["untracked"]) > 0 for r in rows)
    return out


def event_stats(events_csv: str) -> Dict:
    rows = list(csv.DictReader(open(events_csv, encoding="utf-8")))
    starts = [r for r in rows if r.get("phase") in ("start", "", None)]
    return {"rows": len(rows), "episodes": len(starts),
            "by_severity": {s: sum(r["severity"] == s for r in starts) for s in ("warning", "danger")}}


# ----------------------------------------------------------------------
# 실행
# ----------------------------------------------------------------------
def run_one(cfg: Dict, run_dir: str, detector=None, monitor: bool = True, max_frames: Optional[int] = None) -> Dict:
    os.makedirs(run_dir, exist_ok=True)
    torch = _torch()
    if torch is not None and torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    pipe = NearMissPipeline(cfg, detector=detector)
    mon = ResourceMonitor(interval=0.5, gpu_index=0 if monitor else None)
    try:
        baseline = mon.baseline(1.0) if monitor else "skipped"
        with mon:
            pipe.run(max_frames=max_frames)
        resource = {"during_run": mon.summary(), "baseline_idle_1s": baseline}
    finally:
        mon.close()
    if torch is not None and torch.cuda.is_available():
        resource["torch_peak_allocated_mib"] = round(torch.cuda.max_memory_allocated() / 2**20, 1)
    json.dump(resource, open(os.path.join(run_dir, "resource.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    out = {"perf": pipe.perf, "resource": resource,
           "tracks": track_stats(cfg["output"]["track_log"]),
           "frames": frame_stats(cfg["output"]["frame_log"]),
           "events": event_stats(cfg["output"]["event_log"])}
    run_json = os.path.join(run_dir, "run.json")
    json.dump(out, open(run_json, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    out["files"] = sorted(os.listdir(run_dir))           # run.json 포함 최종 파일 목록
    json.dump(out, open(run_json, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return out


def _torch():
    try:
        import torch

        return torch
    except ImportError:
        return None


def run_batch(base: Dict, batch: Dict, out_root: str, only: Optional[List[str]] = None,
              max_frames: Optional[int] = None, global_warmup: bool = True, detector_factory=None,
              monitor: bool = True) -> Dict:
    videos = [v for v in batch["videos"] if not only or v["id"] in only]
    cond = batch.get("conditions", {})
    precisions = cond.get("precisions", ["fp16"])
    saves = cond.get("save_video", [False])
    results, order = [], 0

    if global_warmup and videos:
        wcfg, wdir = build_run_cfg(base, batch, videos[0], precisions[0], False, os.path.join(out_root, "_warmup"))
        logger.info("전체 워밍업 (결과 미사용): %s 30프레임", videos[0]["id"])
        NearMissPipeline(wcfg, detector=detector_factory() if detector_factory else None).run(max_frames=30)

    for v in videos:
        if not os.path.exists(v["path"]):
            raise FileNotFoundError(f"영상 없음: {v['path']} (data/README.md 의 다운로드 방법 참고)")
        for p in precisions:
            for s in saves:
                order += 1
                cfg, run_dir = build_run_cfg(base, batch, v, p, s, out_root)
                logger.info("[%d] %s %s", order, v["id"], run_tag(p, s))
                if max_frames:
                    cfg.setdefault("perf", {})["warmup_frames"] = min(cfg.get("perf", {}).get("warmup_frames", 10),
                                                                      max(max_frames // 4, 0))
                t = time.time()
                r = run_one(cfg, run_dir, detector=detector_factory() if detector_factory else None,
                            monitor=monitor, max_frames=max_frames)
                results.append({"order": order, "video": v["id"], "precision": p, "save_video": s,
                                "run_dir": run_dir, "elapsed_sec": round(time.time() - t, 2), **r})

    summary = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "meta": batch.get("meta", {}),
               "global_warmup": bool(global_warmup), "conditions": cond,
               "warmup_frames_per_run": deep_merge(base, batch.get("overrides", {})).get("perf", {}).get("warmup_frames"),
               "runs": results}
    os.makedirs(out_root, exist_ok=True)
    json.dump(summary, open(os.path.join(out_root, "summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    with open(os.path.join(out_root, "summary.md"), "w", encoding="utf-8") as f:
        f.write(render_markdown(summary))
    return summary


# ----------------------------------------------------------------------
# 보고서
# ----------------------------------------------------------------------
def _g(d, *keys, default=None):
    for k in keys:
        if not isinstance(d, dict) or k not in d:
            return default
        d = d[k]
    return d


def _fmt(x, nd=1):
    return "N/A" if x is None else f"{x:.{nd}f}"


def render_markdown(summary: Dict) -> str:
    runs = summary["runs"]
    L = ["# 영상별 성능·추적 요약", "",
         f"- 생성: {summary['generated_at']}",
         f"- 데이터: {summary['meta'].get('dataset')} / domain: **{summary['meta'].get('domain')}**",
         f"- 전체 워밍업: {'실행 (첫 영상 30프레임, 결과 미사용)' if summary['global_warmup'] else '없음'} · "
         f"실행별 FPS 통계 제외 프레임: {summary['warmup_frames_per_run']}",
         "- Inference = 모델 forward 만 (ultralytics speed['inference']) · Pipeline = 프레임 읽기~저장 종료 전체",
         "- 파일 입력은 실시간 속도 제한 없이 처리 → Pipeline FPS 는 최대 처리량",
         "- GPU 사용률·메모리는 장치 전체 기준(다른 프로세스 포함). torch peak = 이 프로세스의 PyTorch 할당 최대치", "",
         "## 1. 실행별 성능", "",
         "| 영상 | 조건 | 장치 | Inference ms (FPS) | Pipeline 평균 ms (FPS) | Pipeline p95 ms | encode ms | "
         "GPU util 평균/최대 % | GPU mem 평균/최대 MiB | torch peak MiB | CPU(프로세스) 평균/최대 % |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in runs:
        p, res = r["perf"], r["resource"]["during_run"]
        inf, pip = p["inference_ms"], p["pipeline_ms"]
        dev = f"{p['conditions']['device']} {'FP16' if p['conditions']['half'] else 'FP32'}"
        L.append(
            f"| {r['video']} | {run_tag(r['precision'], r['save_video'])} | {dev} | "
            f"{_fmt(_g(inf, 'mean_ms'), 2)} ({_fmt(_g(inf, 'fps'))}) | {_fmt(pip.get('mean_ms'), 2)} ({_fmt(pip.get('fps'))}) | "
            f"{_fmt(pip.get('p95_ms'), 2)} | {_fmt(_g(p, 'stage_ms', 'encode', 'mean_ms'), 2)} | "
            f"{_fmt(_g(res, 'gpu_util_pct', 'mean'))}/{_fmt(_g(res, 'gpu_util_pct', 'max'))} | "
            f"{_fmt(_g(res, 'gpu_mem_used_mib', 'mean'), 0)}/{_fmt(_g(res, 'gpu_mem_used_mib', 'max'), 0)} | "
            f"{_fmt(r['resource'].get('torch_peak_allocated_mib'))} | "
            f"{_fmt(_g(res, 'cpu_process_pct', 'mean'))}/{_fmt(_g(res, 'cpu_process_pct', 'max'))} |")

    L += ["", "## 2. FP16 vs FP32 (영상 저장 OFF 기준, 영상별)", "",
          "| 영상 | Inference ms FP16 | Inference ms FP32 | Pipeline ms FP16 | Pipeline ms FP32 |", "|---|---|---|---|---|"]
    by = {(r["video"], r["precision"], r["save_video"]): r for r in runs}
    vids = list(dict.fromkeys(r["video"] for r in runs))
    for v in vids:
        a, b = by.get((v, "fp16", False)), by.get((v, "fp32", False))
        if a and b:
            L.append(f"| {v} | {_fmt(_g(a, 'perf', 'inference_ms', 'mean_ms'), 2)} | {_fmt(_g(b, 'perf', 'inference_ms', 'mean_ms'), 2)} | "
                     f"{_fmt(_g(a, 'perf', 'pipeline_ms', 'mean_ms'), 2)} | {_fmt(_g(b, 'perf', 'pipeline_ms', 'mean_ms'), 2)} |")

    L += ["", "## 3. 영상 저장(인코딩) 부담", "",
          "| 영상 | 정밀도 | Pipeline ms 저장 OFF | Pipeline ms 저장 ON | 차이 ms | encode 구간 평균 ms |", "|---|---|---|---|---|---|"]
    for v in vids:
        for prec in ("fp16", "fp32"):
            off, on = by.get((v, prec, False)), by.get((v, prec, True))
            if off and on:
                a, b = _g(off, "perf", "pipeline_ms", "mean_ms"), _g(on, "perf", "pipeline_ms", "mean_ms")
                L.append(f"| {v} | {prec} | {_fmt(a, 2)} | {_fmt(b, 2)} | {_fmt(b - a if a and b else None, 2)} | "
                         f"{_fmt(_g(on, 'perf', 'stage_ms', 'encode', 'mean_ms'), 2)} |")

    L += ["", "## 4. ByteTrack ID / 검출 통계 (각 영상 첫 조건 기준)", "",
          "| 영상 | 프레임 | person 검출 프레임 비율 | vehicle(COCO) 검출 프레임 비율 | 동시 검출 비율 | "
          "person ID 수 (≥30f / <10f) | vehicle ID 수 (≥30f / <10f) | vehicle COCO 클래스 | 미확정 검출 프레임 | 근접 에피소드 |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for v in vids:
        r = next(x for x in runs if x["video"] == v)
        fr, tr, ev = r["frames"], r["tracks"], r["events"]
        tp, tv = tr["person"], tr["vehicle"]
        L.append(f"| {v} | {fr['frames']} | {fr['det_person']['ratio']:.3f} | {fr['det_vehicle']['ratio']:.3f} | "
                 f"{fr['det_both_ratio']:.3f} | {tp['unique_ids']} ({tp['tracks_ge_30f']} / {tp['tracks_lt_10f']}) | "
                 f"{tv['unique_ids']} ({tv['tracks_ge_30f']} / {tv['tracks_lt_10f']}) | {', '.join(tv['coco_classes'])} | "
                 f"{fr['frames_untracked']} | {ev['episodes']} (warning {ev['by_severity']['warning']}, danger {ev['by_severity']['danger']}) |")
    L += ["", "※ vehicle = COCO car/motorcycle/bus/truck 검출이며 지게차 검출이 아님. 근접 에피소드는 미보정 픽셀 거리 기준 지표이며 "
          "Near-Miss 확정이 아님. ID 수는 정답 라벨 없이 산출한 값으로 ID 전환 횟수를 의미하지 않음.", ""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="영상 × 조건 일괄 실행")
    ap.add_argument("--config", default="configs/config.yaml")
    ap.add_argument("--videos", default="configs/day2_videos.yaml")
    ap.add_argument("--out", default="outputs/day2")
    ap.add_argument("--only", nargs="*", help="실행할 video id 만 지정")
    ap.add_argument("--no-global-warmup", action="store_true")
    args = ap.parse_args()

    os.chdir(ROOT)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for noisy in ("src.pipeline", "ultralytics"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    base = yaml.safe_load(open(args.config, encoding="utf-8"))
    batch = yaml.safe_load(open(args.videos, encoding="utf-8"))
    summary = run_batch(base, batch, args.out, only=args.only, global_warmup=not args.no_global_warmup)
    print(render_markdown(summary))


if __name__ == "__main__":
    main()
