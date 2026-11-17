"""Day 3: ID 병합(D3-4) / 정지 물체 필터(D3-2) / 운전자 구분(D3-3) 테스트."""
import csv
import json
import os
from dataclasses import dataclass, field
from typing import List

import numpy as np
import pytest
import yaml

from src.detection.detector import Detection
from src.pipeline import NearMissPipeline
from src.risk.near_miss import NearMissDetector
from src.risk.object_filter import StaticObjectFilter
from src.risk.role_classifier import RoleClassifier
from src.risk.track_analysis import TrackAnalyzer, TrackView
from src.tracking.id_merger import IdMerger
from tests.test_pipeline_bytetrack import make_video

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "7_tr21_p1_v3_tracks.csv")


@dataclass
class T:
    track_id: int
    category: str
    bbox: np.ndarray
    velocity: np.ndarray = field(default_factory=lambda: np.zeros(2))
    history: List = field(default_factory=list)
    score: float = 0.9

    @property
    def foot_point(self):
        x1, y1, x2, y2 = self.bbox
        return np.array([(x1 + x2) / 2.0, y2])


def box(cx, bottom, w, h):
    return np.array([cx - w / 2, bottom - h, cx + w / 2, bottom], float)


# ====================== D3-4 ID 병합 ======================
def test_merge_reappearing_track_keeps_raw_id():
    m = IdMerger(max_gap_frames=10, max_dist_px=50, use_velocity=False)
    for f in range(5):
        assert m.update([T(3, "vehicle", box(100 + f, 300, 80, 60))], f) == {3: 3}
    assert m.update([], 5) == {}
    out = m.update([T(9, "vehicle", box(110, 302, 80, 60))], 8)        # gap 4, 거리 ~6px
    assert out == {9: 3}
    assert m.raw_to_can[9] == 3 and m.raw_to_can[3] == 3               # 원본 raw ID 는 그대로 매핑 키로 보존
    assert m.merges == [{"frame": 8, "category": "vehicle", "raw_track_id": 9, "canonical_track_id": 3,
                         "gap_frames": 4, "dist_px": pytest.approx(m.merges[0]["dist_px"])}]


@pytest.mark.parametrize("new, frame", [
    (T(9, "vehicle", box(400, 300, 80, 60)), 8),      # 너무 멂
    (T(9, "vehicle", box(104, 300, 80, 60)), 20),     # gap 초과
    (T(9, "person", box(104, 300, 30, 80)), 8),       # 다른 카테고리
])
def test_merge_rejected(new, frame):
    m = IdMerger(max_gap_frames=10, max_dist_px=50, use_velocity=False)
    m.update([T(3, "vehicle", box(100, 300, 80, 60))], 4)
    assert m.update([new], frame) == {9: 9} and m.merges == []


def test_merge_never_reuses_active_canonical():
    m = IdMerger(max_gap_frames=10, max_dist_px=50)
    m.update([T(3, "vehicle", box(100, 300, 80, 60))], 0)
    out = m.update([T(3, "vehicle", box(100, 300, 80, 60)), T(9, "vehicle", box(105, 300, 80, 60))], 1)
    assert out == {3: 3, 9: 9}


def test_merge_uses_velocity_prediction():
    m = IdMerger(max_gap_frames=20, max_dist_px=30, use_velocity=True, min_history_for_velocity=1)
    m.update([T(3, "vehicle", box(100, 300, 80, 60), velocity=np.array([10.0, 0]), history=[0] * 5)], 0)
    assert m.update([T(9, "vehicle", box(200, 300, 80, 60))], 10) == {9: 3}   # 100 + 10*10 = 200


# ====================== D3-2 정지 물체 필터 ======================
def V(tid, cx, bottom, w=40, h=30):
    return T(tid, "vehicle", box(cx, bottom, w, h))


def test_small_static_object_excluded_after_min_frames():
    f = StaticObjectFilter(move_px=25, min_frames=5, protect_min_h_ratio=0.2)
    for i in range(4):
        f.update([V(1, 100 + (i % 2), 90)], i, 720)
        assert f.status[1] == "pending" and not f.excluded(1)            # 관측 부족 → 포함(누락 방지)
    f.update([V(1, 100, 90)], 4, 720)
    assert f.status[1] == "static" and f.excluded(1)


def test_stopped_forklift_stays_protected():
    f = StaticObjectFilter(move_px=25, min_frames=5)
    for i in range(10):
        f.update([V(1, 100 + 10 * i, 400)], i, 720)                       # 90px 이동
    for i in range(10, 60):
        f.update([V(1, 190, 400)], i, 720)                                # 이후 50프레임 정차
    assert f.status[1] == "dynamic" and not f.excluded(1)


def test_large_stationary_vehicle_protected():
    f = StaticObjectFilter(move_px=25, min_frames=5, protect_min_h_ratio=0.2)
    for i in range(30):
        f.update([V(1, 600, 600, w=300, h=200)], i, 720)                  # 높이 200 ≥ 0.2*720
    assert f.status[1] == "protected_large" and not f.excluded(1)


def test_ignore_zone_excludes_only_unmoved_vehicles():
    zone = [[40, 40], [200, 40], [200, 115], [40, 115]]
    f = StaticObjectFilter(move_px=25, min_frames=15, ignore_zones=[zone])
    f.update([V(1, 130, 90)], 0, 720)
    assert f.status[1] == "ignored_zone" and f.excluded(1)                # 첫 프레임부터 제외
    for i in range(6):                                                    # 구역 밖에서 출발해 구역으로 진입
        f.update([V(2, 300 - 25 * i, 100, w=60, h=50)], i, 720)
    assert f.status[2] == "dynamic" and not f.excluded(2)


# ====================== D3-3 운전자 구분 ======================
def load_fixture():
    rows = list(csv.DictReader(line for line in open(FIXTURE, encoding="utf-8") if not line.startswith("#")))
    by = {}
    for r in rows:
        by.setdefault(int(r["frame"]), []).append(
            T(int(r["track_id"]), r["category"], np.array([float(r[k]) for k in ("x1", "y1", "x2", "y2")])))
    return by


def test_regression_7_tr21_pedestrian_is_never_driver():
    """7_tr21 실제 보행자(person#1)는 지게차(vehicle#3)와 IoA 가 높아도 운전자로 분류되면 안 된다."""
    rc = RoleClassifier()
    by = load_fixture()
    assert len(by) > 200
    for f in sorted(by):
        assert rc.update(by[f], f) == set(), f"frame {f} 에서 운전자로 오분류"
    assert rc.log and all(r["role"] == "pedestrian" for r in rc.log)
    assert any("운전석 비율" in r["reason"] for r in rc.log)            # 판정 근거 기록


def driver_frames(n=20, dx=4.0, still=False, seed=0):
    rng = np.random.default_rng(seed)
    out = []
    for f in range(n):
        x = 300 + (0 if still else dx * f)
        vb = box(x, 400, 200, 240)                                        # 지게차
        j = rng.normal(0, 1.5, 4)
        pb = box(x, 300, 50, 90) + j                                      # 운전석 안 (하단 300 < 400)
        out.append([T(1, "person", pb), T(2, "vehicle", vb)])
    return out


@pytest.mark.parametrize("still", [False, True])
def test_driver_detected_with_cab_and_co_motion(still):
    rc = RoleClassifier(window=15, min_frames=8)
    res = [rc.update(fr, f) for f, fr in enumerate(driver_frames(still=still))]
    assert res[6] == set() and res[-1] == {(1, 2)}                       # min_frames 전에는 판정하지 않음
    assert rc.log[-1]["role"] == "driver" and rc.log[-1]["reason"] == "모든 조건 충족"


def test_person_in_cab_area_but_moving_differently_is_not_driver():
    rc = RoleClassifier(window=15, min_frames=8)
    for f in range(20):
        vb = box(300 + 4 * f, 400, 200, 240)
        pb = box(380 - 4 * f, 300, 50, 90)                               # 반대 방향 이동
        rc.update([T(1, "person", pb), T(2, "vehicle", vb)], f)
    assert all(r["role"] == "pedestrian" for r in rc.log)


def test_short_overlap_is_not_judged():
    rc = RoleClassifier(min_frames=8)
    frames = driver_frames(n=5)
    assert all(rc.update(fr, f) == set() for f, fr in enumerate(frames)) and rc.log == []


def test_near_miss_exclude_pairs():
    nm = NearMissDetector(fps=25, danger_px=80, warning_px=150)
    tracks = [T(1, "person", box(100, 300, 30, 80)), T(2, "vehicle", box(150, 300, 100, 80))]
    assert len(nm.evaluate(tracks)) == 1
    assert nm.evaluate(tracks, exclude_pairs={(1, 2)}) == []


# ====================== 통합 ======================
def test_trackview_exposes_canonical_and_raw():
    t = T(9, "vehicle", box(100, 300, 80, 60))
    v = TrackView(t, 3)
    assert v.track_id == 3 and v.raw_track_id == 9 and v.category == "vehicle"
    np.testing.assert_allclose(v.foot_point, t.foot_point)


def test_default_config_keeps_analysis_disabled():
    cfg = yaml.safe_load(open(os.path.join(ROOT, "configs", "config.yaml"), encoding="utf-8"))
    assert TrackAnalyzer.from_config(cfg.get("analysis")) is None
    assert TrackAnalyzer.from_config(None) is None


class SwitchingIdDetector:
    """vehicle 이 프레임 20~23 동안 검출되지 않았다가 새 ID(5)로 재등장하는 상황."""

    def __init__(self):
        self.i = 0
        self.last_speed, self.last_untracked = {}, 0

    def track(self, frame):
        i, self.i = self.i, self.i + 1
        p = Detection(np.array([300, 200, 320, 260], float), 0.9, 0, "person", track_id=1)
        if 20 <= i < 24:
            return [p]
        vx = 120 + 2 * i
        return [p, Detection(np.array([vx, 210, vx + 60, 260], float), 0.9, 7, "vehicle",
                             track_id=2 if i < 20 else 5)]

    def detect(self, frame):
        raise AssertionError("detect() 호출 금지")


def _cfg(tmp_path, analysis=None):
    video = tmp_path / "v.mp4"
    make_video(video)
    cfg = {"video": {"source": str(video), "resize_width": None},
           "tracking": {"type": "bytetrack", "history_len": 30, "max_age": 30},
           "risk": {"zones": [], "near_miss": {"danger_px": 60, "warning_px": 150,
                                                "release_frames": 10, "cooldown_frames": 0}},
           "perf": {"warmup_frames": 5},
           "output": {"save_video": False, "event_log": str(tmp_path / "events.csv"),
                      "perf_path": str(tmp_path / "perf.json"), "track_log": str(tmp_path / "tracks.csv"),
                      "merge_log": str(tmp_path / "merge.csv"), "static_log": str(tmp_path / "static.csv"),
                      "role_log": str(tmp_path / "role.csv"), "show_window": False}}
    if analysis:
        cfg["analysis"] = analysis
    return cfg


def _starts(tmp_path):
    return [r for r in csv.DictReader(open(tmp_path / "events.csv", encoding="utf-8")) if r["phase"] == "start"]


def test_pipeline_without_analysis_is_unchanged(tmp_path):
    NearMissPipeline(_cfg(tmp_path), detector=SwitchingIdDetector()).run()
    header = open(tmp_path / "tracks.csv", encoding="utf-8").readline().strip().split(",")
    assert "canonical_track_id" not in header
    assert not (tmp_path / "merge.csv").exists()
    assert "analysis" not in json.load(open(tmp_path / "perf.json", encoding="utf-8"))
    assert len(_starts(tmp_path)) == 2                                   # ID 단절 → 에피소드 2개 (기존 동작)


def test_pipeline_with_id_merge_dedups_episode(tmp_path):
    analysis = {"id_merge": {"enabled": True, "max_gap_frames": 10, "max_dist_px": 80},
                "static_filter": {"enabled": True}, "role": {"enabled": True}}
    NearMissPipeline(_cfg(tmp_path, analysis), detector=SwitchingIdDetector()).run()
    starts = _starts(tmp_path)
    assert len(starts) == 1 and starts[0]["track_ids"] == "1-2"
    rows = list(csv.DictReader(open(tmp_path / "tracks.csv", encoding="utf-8")))
    v = [r for r in rows if r["category"] == "vehicle"]
    assert {r["track_id"] for r in v} == {"2", "5"}                       # 원본 ID 보존
    assert {r["canonical_track_id"] for r in v} == {"2"}                  # 병합 ID
    merges = list(csv.DictReader(open(tmp_path / "merge.csv", encoding="utf-8")))
    assert [(m["raw_track_id"], m["canonical_track_id"]) for m in merges] == [("5", "2")]
    perf = json.load(open(tmp_path / "perf.json", encoding="utf-8"))
    assert perf["analysis"]["id_merge"] == {"merges": 1, "raw_ids": 3, "canonical_ids": 2}
    assert (tmp_path / "static.csv").exists() and (tmp_path / "role.csv").exists()
