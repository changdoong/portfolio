"""GPU 실추론 검증 + Inference 속도 측정 (정지 이미지 반복).

    .\\.venv\\Scripts\\python.exe scripts\\gpu_smoke_test.py               # FP16
    .\\.venv\\Scripts\\python.exe scripts\\gpu_smoke_test.py --no-half     # FP32 비교

- 입력: ultralytics 패키지에 포함된 예제 이미지 bus.jpg (810x1080)
- 측정: ultralytics result.speed (preprocess / inference / postprocess, ms)
        + detect()/track() 호출 전체 wall-clock (ms)
- 출력: outputs/gpu_smoke_<fp16|fp32>.json, outputs/gpu_smoke_<fp16|fp32>.jpg (박스+ID 시각화)

※ 정지 이미지 반복 측정이므로 실제 영상(MP4)의 Pipeline FPS 와는 다르다.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import cv2  # noqa: E402
import torch  # noqa: E402
import ultralytics  # noqa: E402

from src.detection.detector import YOLODetector  # noqa: E402
from src.tracking.tracker import ByteTrackAdapter  # noqa: E402
from src.utils.metrics import LatencyStats  # noqa: E402


def bench(fn, img, detector, iters, warmup):
    stats = {k: LatencyStats(warmup) for k in ("preprocess", "inference", "postprocess", "call_wall")}
    out = None
    for _ in range(warmup + iters):
        t0 = time.perf_counter()
        out = fn(img)
        stats["call_wall"].add((time.perf_counter() - t0) * 1000)
        for k in ("preprocess", "inference", "postprocess"):
            stats[k].add(detector.last_speed.get(k))
    return out, {k: s.summary() for k, s in stats.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="models/yolov8n.pt")
    ap.add_argument("--half", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--iters", type=int, default=200)
    ap.add_argument("--warmup", type=int, default=20)
    args = ap.parse_args()

    img_path = Path(ultralytics.__file__).parent / "assets" / "bus.jpg"
    img = cv2.imread(str(img_path))
    det = YOLODetector(args.model, device="cuda:0", half=args.half, tracker_cfg="configs/bytetrack.yaml")
    tag = "fp16" if det.half else "fp32"

    torch.cuda.reset_peak_memory_stats()
    dets, detect_perf = bench(det.detect, img, det, args.iters, args.warmup)
    param = next(det.torch_module().parameters())

    det.reset_tracking()
    adapter = ByteTrackAdapter()
    tracked, track_perf = bench(lambda im: det.track(im), img, det, args.iters, args.warmup)
    tracks = adapter.update(tracked)

    report = {
        "image": f"{img_path.name} {img.shape[1]}x{img.shape[0]}",
        "model": args.model,
        "gpu": torch.cuda.get_device_name(0),
        "torch": torch.__version__,
        "ultralytics": ultralytics.__version__,
        "requested_half": args.half,
        "effective": {"device": det.device, "half": det.half,
                      "param_device": str(param.device), "param_dtype": str(param.dtype)},
        "imgsz": det.imgsz,
        "iters": args.iters, "warmup": args.warmup,
        "detect": {"detections": [(d.category, round(d.score, 3)) for d in dets], "speed_ms": detect_perf},
        "track": {"tracks": [(t.track_id, t.category) for t in tracks], "speed_ms": track_perf},
        "peak_gpu_memory_mb": round(torch.cuda.max_memory_allocated() / 1024**2, 1),
    }

    vis = img.copy()
    for t in tracks:
        x1, y1, x2, y2 = t.bbox.astype(int)
        color = (80, 220, 80) if t.category == "person" else (255, 160, 40)
        cv2.rectangle(vis, (x1, y1), (x2, y2), color, 3)
        cv2.putText(vis, f"{t.category} #{t.track_id}", (x1, max(y1 - 8, 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    inf = track_perf["inference"]
    cv2.putText(vis, f"{report['gpu']} | {tag.upper()} | inference {inf['mean_ms']:.1f} ms ({inf['fps']:.0f} FPS)",
                (10, img.shape[0] - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    os.makedirs("outputs", exist_ok=True)
    cv2.imwrite(f"outputs/gpu_smoke_{tag}.jpg", vis)
    with open(f"outputs/gpu_smoke_{tag}.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
