"""YOLO 없이 합성 영상 + 가짜 검출기로 파이프라인 전체(E2E) 검증."""
import csv

import cv2
import numpy as np

from src.detection.detector import Detection
from src.pipeline import NearMissPipeline

N_FRAMES, FPS, W, H = 60, 30, 640, 360


def person_box(i):   # 사람은 정지
    return np.array([300, 200, 320, 260], dtype=float)


def vehicle_box(i):  # 차량이 왼쪽에서 사람 쪽으로 5px/frame (=150px/s) 접근
    x = 40 + 5 * i
    return np.array([x, 210, x + 60, 260], dtype=float)


class FakeDetector:
    def __init__(self):
        self.i = 0

    def detect(self, frame):
        dets = [
            Detection(person_box(self.i), 0.9, 0, "person"),
            Detection(vehicle_box(self.i), 0.9, 7, "vehicle"),
        ]
        self.i += 1
        return dets


def make_video(path):
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    for _ in range(N_FRAMES):
        vw.write(np.zeros((H, W, 3), np.uint8))
    vw.release()


def test_pipeline_end_to_end(tmp_path):
    video = tmp_path / "synthetic.mp4"
    make_video(video)
    cfg = {
        "video": {"source": str(video), "resize_width": None},
        "tracking": {"iou_threshold": 0.3, "max_age": 5, "min_hits": 2, "history_len": 30},
        "risk": {
            "zones": [{"name": "dock", "level": "danger", "polygon": [[280, 180], [360, 180], [360, 300], [280, 300]]}],
            "near_miss": {"distance_px": 60, "ttc_sec": 1.5, "min_closing_speed": 20, "cooldown_frames": 1000},
        },
        "output": {
            "save_video": True, "video_path": str(tmp_path / "out.mp4"),
            "event_log": str(tmp_path / "events.csv"), "show_window": False,
        },
    }

    summary = NearMissPipeline(cfg, detector=FakeDetector()).run()

    rows = list(csv.DictReader(open(tmp_path / "events.csv", encoding="utf-8")))
    nm = [r for r in rows if r["type"] == "near_miss"]
    # 쿨다운이 길어서 같은 쌍에 대해 단 1회, 그리고 실제 근접(danger)보다 먼저 warning 으로 예측돼야 함
    assert len(nm) == 1 and nm[0]["severity"] == "warning"
    assert summary["zone_intrusion/danger"] == 1
    assert (tmp_path / "out.mp4").stat().st_size > 0
