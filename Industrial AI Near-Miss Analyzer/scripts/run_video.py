"""영상 파일 / 웹캠 / RTSP 스트림에 대해 Near-Miss 분석 실행.

예)
    python scripts/run_video.py --source data/sample.mp4
    python scripts/run_video.py --source 0 --no-show
    python scripts/run_video.py --source rtsp://username:password@camera-ip:554/stream

    ※ 위 RTSP 주소는 설명용 placeholder 이며 실제 접속정보가 아니다.
      username / password / camera-ip / stream 을 실제 카메라 값으로 바꿔 사용한다.
      (RTSP 입력은 아직 실제 스트림으로 검증되지 않았다.)
"""
import argparse
import logging
import os
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)  # config 의 상대 경로를 프로젝트 루트 기준으로 해석

from src.pipeline import NearMissPipeline  # noqa: E402


def parse_args():
    ap = argparse.ArgumentParser(description="Industrial AI Near-Miss Analyzer")
    ap.add_argument("--config", default="configs/config.yaml")
    ap.add_argument("--source", help="config 의 video.source 덮어쓰기")
    ap.add_argument("--model", help="config 의 detection.model 덮어쓰기")
    ap.add_argument("--device", help="cpu / cuda:0")
    ap.add_argument("--tracker", choices=["bytetrack", "iou"], help="config 의 tracking.type 덮어쓰기")
    ap.add_argument("--half", action=argparse.BooleanOptionalAction, default=None,
                    help="FP16 사용 여부 (--half / --no-half). CUDA 가 없으면 자동 FP32")
    ap.add_argument("--max-frames", type=int, default=None)
    ap.add_argument("--no-show", action="store_true", help="화면 출력 끄기 (서버 환경)")
    ap.add_argument("--no-save", action="store_true", help="결과 영상 저장 끄기")
    return ap.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    if args.source is not None:
        cfg["video"]["source"] = args.source
    if args.model:
        cfg["detection"]["model"] = args.model
    if args.device:
        cfg["detection"]["device"] = args.device
    if args.tracker:
        cfg["tracking"]["type"] = args.tracker
    if args.half is not None:
        cfg["detection"]["half"] = args.half
    if args.no_show:
        cfg["output"]["show_window"] = False
    if args.no_save:
        cfg["output"]["save_video"] = False

    pipeline = NearMissPipeline(cfg)
    summary = pipeline.run(max_frames=args.max_frames)
    print("\n=== Event Summary (에피소드 수) ===")
    for k, v in (summary or {"(no events)": 0}).items():
        print(f"{k:30s} {v}")

    p = pipeline.perf
    print("\n=== Performance ===")
    print("conditions :", p["conditions"])
    print("Inference  :", p["inference_ms"])
    print("Pipeline   :", p["pipeline_ms"])
    print(f"frames {p['frames']}, wall {p['wall_time_sec']}s, overall {p['overall_fps']} FPS")


if __name__ == "__main__":
    main()
