"""새 설정 형식(ByteTrack + 픽셀 근접도 + 에피소드) 파이프라인 E2E. 가짜 검출기 사용."""
import csv
import json

import cv2
import numpy as np
import pytest

from src.detection.detector import Detection
from src.pipeline import NearMissPipeline

N_FRAMES, FPS, W, H = 60, 30, 640, 360
EMPTY_FRAMES = {0, 1, 2}        # 검출 없음
UNTRACKED_FRAMES = {3, 4}       # 검출은 있으나 ByteTrack 확정 전 (ultralytics 가 id=None 반환하는 상황)


def person_box(i):
    return np.array([300, 200, 320, 260], dtype=float)          # 하단 중앙 (310, 260)


def vehicle_box(i):
    x = 40 + 5 * i                                               # 5px/frame 접근
    return np.array([x, 210, x + 60, 260], dtype=float)          # 하단 중앙 (x+30, 260)


class FakeTrackingDetector:
    """ultralytics model.track() 동작을 흉내 낸다."""

    def __init__(self):
        self.i = 0
        self.track_calls = 0
        self.detect_calls = 0
        self.last_speed = {}
        self.last_untracked = 0

    def track(self, frame):
        self.track_calls += 1
        i, self.i = self.i, self.i + 1
        self.last_speed = {"preprocess": 1.0, "inference": 5.0, "postprocess": 2.0}
        self.last_untracked = 0
        if i in EMPTY_FRAMES:
            return []
        if i in UNTRACKED_FRAMES:
            self.last_untracked = 2
            return []
        return [Detection(person_box(i), 0.9, 0, "person", track_id=1),
                Detection(vehicle_box(i), 0.9, 7, "vehicle", track_id=2)]

    def detect(self, frame):
        self.detect_calls += 1
        raise AssertionError("bytetrack 모드에서 detect() 가 호출되면 안 됨")

    def reset_tracking(self):
        pass


class FakeDetectOnly:
    def __init__(self):
        self.i = 0
        self.detect_calls = 0

    def detect(self, frame):
        self.detect_calls += 1
        i, self.i = self.i, self.i + 1
        return [Detection(person_box(i), 0.9, 0, "person"), Detection(vehicle_box(i), 0.9, 7, "vehicle")]

    def track(self, frame):
        raise AssertionError("iou 모드에서 track() 이 호출되면 안 됨")


def make_video(path):
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    for _ in range(N_FRAMES):
        vw.write(np.zeros((H, W, 3), np.uint8))
    vw.release()


def make_cfg(tmp_path, tracker_type="bytetrack"):
    video = tmp_path / "synthetic.mp4"
    make_video(video)
    return {
        "video": {"source": str(video), "resize_width": None},
        "tracking": {"type": tracker_type, "history_len": 30, "max_age": 30,
                     "iou": {"iou_threshold": 0.3, "min_hits": 1}},
        "risk": {
            "zones": [{"name": "dock", "level": "danger", "polygon": [[280, 180], [360, 180], [360, 300], [280, 300]]}],
            "zone_events": {"release_frames": 10, "cooldown_frames": 30},
            "near_miss": {"danger_px": 60, "warning_px": 150, "release_frames": 10, "cooldown_frames": 30},
        },
        "perf": {"warmup_frames": 10},
        "output": {"save_video": True, "video_path": str(tmp_path / "out.mp4"),
                   "event_log": str(tmp_path / "events.csv"), "perf_path": str(tmp_path / "perf.json"),
                   "show_window": False},
    }


def test_bytetrack_pipeline_end_to_end(tmp_path):
    cfg = make_cfg(tmp_path)
    det = FakeTrackingDetector()
    pipe = NearMissPipeline(cfg, detector=det)
    summary = pipe.run()

    # ByteTrack 은 프레임당 정확히 1회, detect() 는 0회
    assert det.track_calls == N_FRAMES and det.detect_calls == 0

    rows = list(csv.DictReader(open(tmp_path / "events.csv", encoding="utf-8")))
    nm = [(r["phase"], r["severity"]) for r in rows if r["type"] == "near_miss"]
    # 차량 접근: warning 시작 → danger 상승 → 영상 종료 시 end. 중복 기록 없음
    assert nm == [("start", "warning"), ("escalate", "danger"), ("end", "danger")]
    zi = [r["phase"] for r in rows if r["type"] == "zone_intrusion"]
    assert zi == ["start", "end"]
    assert summary == {"near_miss/warning": 1, "zone_intrusion/danger": 1}

    perf = json.load(open(tmp_path / "perf.json", encoding="utf-8"))
    assert perf["frames"] == N_FRAMES
    assert perf["inference_ms"]["mean_ms"] == pytest.approx(5.0)
    assert perf["inference_ms"]["count"] == N_FRAMES - 10
    assert perf["pipeline_ms"]["count"] == N_FRAMES - 10 and perf["pipeline_ms"]["mean_ms"] > 0
    assert perf["frames_with_untracked_detections"] == len(UNTRACKED_FRAMES)
    assert perf["conditions"]["tracker"] == "bytetrack"
    assert (tmp_path / "out.mp4").stat().st_size > 0


def test_iou_mode_calls_detect_only(tmp_path):
    cfg = make_cfg(tmp_path, tracker_type="iou")
    det = FakeDetectOnly()
    pipe = NearMissPipeline(cfg, detector=det)
    pipe.run()
    assert det.detect_calls == N_FRAMES
    perf = json.load(open(tmp_path / "perf.json", encoding="utf-8"))
    assert perf["conditions"]["tracker"] == "iou"
    assert str(perf["inference_ms"]).startswith("N/A")      # 측정 안 된 값은 기록하지 않음


def test_bytetrack_requires_track_method(tmp_path):
    class DetectOnly:
        def detect(self, frame):
            return []

    with pytest.raises(TypeError):
        NearMissPipeline(make_cfg(tmp_path), detector=DetectOnly())
