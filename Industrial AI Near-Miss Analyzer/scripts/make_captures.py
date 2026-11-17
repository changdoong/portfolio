"""공개용 캡처 생성 (탐지 화면 / ByteTrack ID 추적 화면) — 비식별 처리된 이미지만 출력.

    .\\.venv\\Scripts\\python.exe scripts\\make_captures.py                       # outputs/day2/captures_public/<시각>/
    .\\.venv\\Scripts\\python.exe scripts\\make_captures.py --out outputs\\day2\\captures_public\\v1

입력  : outputs/day2/<video>/<run_tag>/result.mp4 + tracks.csv (scripts/run_batch.py 결과)
출력  : <out>/<video>_detect.jpg, <out>/<video>_track_ids.jpg, <out>/privacy_log.csv

안전장치
  - 출력 폴더가 이미 있으면 중단 (기존 결과 덮어쓰기 금지)
  - 모든 이미지의 비식별 검증이 통과한 뒤에만 파일을 쓴다. 하나라도 실패하면 아무것도 쓰지 않고 종료코드 1
  - 블러 전 원본은 기본적으로 저장하지 않는다. --save-raw-local 로 지정한 로컬 폴더(공개 폴더 밖)에만 저장 가능
비식별 영역 (src/utils/privacy.py)
  - 사람 머리: tracks.csv person ∪ 원본 프레임 재검출(conf 0.05) ∪ 차량 박스 2배 확대 crop 재검출(운전자)
  - 고정 카메라 작업대 마스크
  - 큰 차량(프레임 높이 25% 이상)의 운전석 추정 영역: tracks.csv vehicle ∪ 원본 프레임 vehicle 재검출
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from collections import defaultdict
from typing import Dict, List, Tuple

import cv2
import numpy as np
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.detection.detector import YOLODetector  # noqa: E402
from src.utils.privacy import PrivacyError, anonymize, find_people  # noqa: E402

SIZE = (1280, 720)


def read_frame(path: str, idx: int, size=None) -> np.ndarray:
    cap = cv2.VideoCapture(path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, fr = cap.read()
    cap.release()
    if not ok:
        raise IOError(f"{path} frame {idx} 읽기 실패")
    return cv2.resize(fr, size) if size and (fr.shape[1], fr.shape[0]) != size else fr


def load_tracks(path: str) -> Dict[int, List[dict]]:
    by_frame = defaultdict(list)
    for r in csv.DictReader(open(path, encoding="utf-8")):
        by_frame[int(r["frame"])].append(r)
    return by_frame


def boxes(rows: List[dict], category: str) -> List[Tuple[float, float, float, float]]:
    return [tuple(float(r[k]) for k in ("x1", "y1", "x2", "y2")) for r in rows if r["category"] == category]


class Anonymizer:
    def __init__(self, model: str, conf: float = 0.05, vehicle_conf: float = 0.10):
        self.person_det = YOLODetector(model, conf=conf, device="cuda:0", half=False, class_map={"person": [0]})
        self.vehicle_det = YOLODetector(model, conf=vehicle_conf, device="cuda:0", half=False,
                                        class_map={"vehicle": [2, 3, 5, 7]})

    def __call__(self, shown: np.ndarray, source_frame: np.ndarray, track_rows: List[dict]):
        """shown = 공개할 이미지(결과 영상 프레임), source_frame = 같은 시점 원본(1280x720)."""
        vboxes = boxes(track_rows, "vehicle") + [tuple(map(float, d.bbox)) for d in self.vehicle_det.detect(source_frame)]
        people = boxes(track_rows, "person") + find_people(self.person_det, source_frame, vboxes)
        return anonymize(shown, people, vboxes)


def select_frames(by_frame: Dict[int, List[dict]]):
    score = {f: (any(r["category"] == "person" for r in v) and any(r["category"] == "vehicle" for r in v)) * len(v)
             for f, v in by_frame.items()}
    f_det = max(sorted(score), key=lambda f: score[f])
    life = defaultdict(list)
    for f, v in by_frame.items():
        for r in v:
            if r["category"] == "person":
                life[int(r["track_id"])].append(f)
    pid = max(life, key=lambda k: len(life[k]))
    fs = sorted(life[pid])
    return f_det, pid, len(fs), [fs[int(len(fs) * q)] for q in (0.15, 0.5, 0.85)]


def build(videos, runs_root, run_tag, anonymizer) -> Tuple[Dict[str, np.ndarray], List[list], Dict[str, np.ndarray]]:
    images, log, raws = {}, [], {}
    for v in videos:
        run = os.path.join(runs_root, v["id"], run_tag)
        res, by_frame = os.path.join(run, "result.mp4"), load_tracks(os.path.join(run, "tracks.csv"))
        f_det, pid, plen, picks = select_frames(by_frame)

        shown = read_frame(res, f_det)
        out, regions = anonymizer(shown, read_frame(v["path"], f_det, SIZE), by_frame[f_det])
        images[f"{v['id']}_detect.jpg"], raws[f"{v['id']}_detect.jpg"] = out, shown
        log.append([v["id"], "detect", f_det, len(regions), _kinds(regions)])

        tiles, raw_tiles = [], []
        for f in picks:
            shown = read_frame(res, f)
            out, regions = anonymizer(shown, read_frame(v["path"], f, SIZE), by_frame[f])
            log.append([v["id"], "track_ids", f, len(regions), _kinds(regions)])
            for dst, img in ((tiles, out), (raw_tiles, shown)):
                im = cv2.resize(img, (640, 360))
                cv2.rectangle(im, (0, 330), (640, 360), (0, 0, 0), -1)
                cv2.putText(im, f"{v['id']}  frame {f}  (person ID #{pid} tracked {plen} frames)", (8, 351),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                dst.append(im)
        images[f"{v['id']}_track_ids.jpg"], raws[f"{v['id']}_track_ids.jpg"] = np.hstack(tiles), np.hstack(raw_tiles)
    return images, log, raws


def _kinds(regions) -> str:
    c = defaultdict(int)
    for k, _ in regions:
        c[k] += 1
    return ";".join(f"{k}={n}" for k, n in sorted(c.items()))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--videos", default="configs/day2_videos.yaml")
    ap.add_argument("--runs-root", default="outputs/day2")
    ap.add_argument("--run-tag", default="fp16_save_on")
    ap.add_argument("--out", default=None, help="기본: outputs/day2/captures_public/<YYYYmmdd_HHMMSS>")
    ap.add_argument("--model", default="models/yolov8n.pt")
    ap.add_argument("--save-raw-local", default=None, help="(선택) 블러 전 원본 저장 폴더. 공개 폴더 밖이어야 함")
    args = ap.parse_args(argv)
    os.chdir(ROOT)

    out = args.out or os.path.join("outputs", "day2", "captures_public", time.strftime("%Y%m%d_%H%M%S"))
    if os.path.exists(out):
        print(f"[중단] 출력 폴더가 이미 존재합니다 (덮어쓰기 금지): {out}")
        return 1
    if args.save_raw_local and os.path.abspath(args.save_raw_local).startswith(os.path.abspath(out)):
        print("[중단] 원본 저장 폴더는 공개 폴더 밖이어야 합니다.")
        return 1

    videos = yaml.safe_load(open(args.videos, encoding="utf-8"))["videos"]
    try:
        images, log, raws = build(videos, args.runs_root, args.run_tag, Anonymizer(args.model))
    except PrivacyError as e:
        print(f"[중단] 비식별 처리 실패 → 공개용 이미지를 생성하지 않습니다: {e}")
        return 1

    os.makedirs(out)
    for name, img in images.items():
        cv2.imwrite(os.path.join(out, name), img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    with open(os.path.join(out, "privacy_log.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["video", "capture", "frame", "regions", "region_kinds"])
        w.writerows(log)
    if args.save_raw_local:
        os.makedirs(args.save_raw_local, exist_ok=True)
        for name, img in raws.items():
            cv2.imwrite(os.path.join(args.save_raw_local, name), img)
    print(f"공개용(비식별) 캡처 {len(images)}장 → {out}")
    print("※ 자동 비식별은 완전하지 않습니다. 공개 전 직접 확인하세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
