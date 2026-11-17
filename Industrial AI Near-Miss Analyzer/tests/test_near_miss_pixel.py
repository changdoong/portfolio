"""픽셀 기반 근접도 판정 + 에피소드(유지 시간/쿨다운) 테스트."""
import csv
from dataclasses import dataclass, field

import numpy as np
import pytest

from src.risk.episode import EpisodeManager
from src.risk.near_miss import NearMissDetector, pixel_severity
from src.risk.zone import Zone, ZoneMonitor
from src.utils.metrics import EventLogger


@dataclass
class FakeTrack:
    track_id: int
    category: str
    bbox: np.ndarray
    velocity: np.ndarray = field(default_factory=lambda: np.zeros(2))

    @property
    def foot_point(self):
        x1, y1, x2, y2 = self.bbox
        return np.array([(x1 + x2) / 2.0, y2])


def person(x, y=300, h=80, tid=1, vel=(0, 0)):
    return FakeTrack(tid, "person", np.array([x - 10, y - h, x + 10, y], float), np.array(vel, float))


def vehicle(x, y=300, h=60, tid=2, vel=(0, 0)):
    return FakeTrack(tid, "vehicle", np.array([x - 30, y - h, x + 30, y], float), np.array(vel, float))


def nm(**kw):
    args = dict(fps=30, danger_px=50, warning_px=100, release_frames=5, cooldown_frames=20)
    args.update(kw)
    return NearMissDetector(**args)


# ---------------- 판정 ----------------
def test_pixel_severity_boundaries():
    assert pixel_severity(50, 50, 100) == "danger"
    assert pixel_severity(50.01, 50, 100) == "warning"
    assert pixel_severity(100, 50, 100) == "warning"
    assert pixel_severity(100.01, 50, 100) is None


def test_distance_uses_bbox_bottom_center():
    # 박스 높이가 크게 달라도 하단 중앙점이 같으면 거리 동일
    d = nm()
    r_short = d.evaluate([person(100, h=20), vehicle(170, h=20)])[0]
    r_tall = d.evaluate([person(100, h=300), vehicle(170, h=150)])[0]
    assert r_short.distance == pytest.approx(70) == r_tall.distance
    assert r_short.severity == "warning"


def test_thresholds_from_config_and_validation():
    d = nm(danger_px=10, warning_px=20)
    assert d.evaluate([person(100), vehicle(115)])[0].severity == "warning"
    with pytest.raises(ValueError):
        nm(danger_px=100, warning_px=50)           # warning < danger
    with pytest.raises(ValueError):
        NearMissDetector(fps=30, danger_px=50)     # warning_px 누락
    with pytest.raises(ValueError):
        nm(danger_px=0)


def test_mode_selection():
    assert nm().mode == "pixel" and nm().enable_ttc is False
    assert NearMissDetector(fps=30, distance_px=50).mode == "legacy"


def test_ttc_disabled_by_default():
    # 빠르게 접근(300px/s) 하지만 아직 warning_px 밖 → 기본 설정에서는 경고 없음
    tracks = [person(0), vehicle(150, vel=(-10, 0))]   # 10px/frame * 30fps
    assert nm().evaluate(tracks)[0].severity is None
    assert nm(enable_ttc=True).evaluate(tracks)[0].severity == "warning"


# ---------------- 에피소드 ----------------
def run(d, frames):
    """frames: 프레임별 track 목록 → 모든 이벤트"""
    events = []
    for i, tracks in enumerate(frames):
        events += d.update(tracks, i)[1]
    return events


def phases(events):
    return [(e["phase"], e["severity"]) for e in events]


def test_sustained_risk_is_one_episode():
    events = run(nm(), [[person(0), vehicle(30)]] * 40)
    assert phases(events) == [("start", "danger")]
    assert events[0]["track_ids"] == [1, 2] and events[0]["event_id"] == "NM-00001"


def test_escalation_logged_once():
    frames = [[person(0), vehicle(80)]] * 5 + [[person(0), vehicle(30)]] * 5 + [[person(0), vehicle(80)]] * 5
    assert phases(run(nm(), frames)) == [("start", "warning"), ("escalate", "danger")]


def test_flicker_shorter_than_release_does_not_split():
    risky, safe = [person(0), vehicle(30)], [person(0), vehicle(500)]
    frames = [risky] * 5 + [safe] * 4 + [risky] * 5          # release_frames=5 → 4프레임 끊김은 무시
    assert phases(run(nm(), frames)) == [("start", "danger")]


def test_end_after_release_with_summary_fields():
    risky, safe = [person(0), vehicle(30)], [person(0), vehicle(500)]
    events = run(nm(), [[person(0), vehicle(40)]] + [risky] * 9 + [safe] * 5)
    end = events[-1]
    assert end["phase"] == "end" and end["frame"] == 14
    assert end["duration_sec"] == pytest.approx(10 / 30, abs=0.01)
    assert end["min_distance_px"] == 30 and end["max_severity"] == "danger"


def test_track_disappearance_ends_episode():
    events = run(nm(), [[person(0), vehicle(30)]] * 3 + [[person(0)]] * 5)
    assert [e["phase"] for e in events] == ["start", "end"]


def test_cooldown_blocks_restart():
    risky, safe = [person(0), vehicle(30)], [person(0), vehicle(500)]
    # 종료(frame 9) 후 10프레임 뒤 재위험 → cooldown 20 이내라 무시, 이후 재위험은 새 에피소드
    frames = [risky] * 5 + [safe] * 5 + [risky] * 3 + [safe] * 30 + [risky] * 3
    events = run(nm(), frames)
    starts = [e for e in events if e["phase"] == "start"]
    assert [s["frame"] for s in starts] == [0, 43]
    assert starts[1]["event_id"] == "NM-00002"


def test_close_ends_open_episodes():
    d = nm()
    run(d, [[person(0), vehicle(30)]] * 3)
    ends = d.close(2)
    assert len(ends) == 1 and ends[0]["phase"] == "end" and ends[0]["track_ids"] == [1, 2]


def test_episode_manager_validation():
    with pytest.raises(ValueError):
        EpisodeManager("x", "X", release_frames=0)


# ---------------- 위험구역 에피소드 ----------------
def test_zone_boundary_flicker_is_single_episode():
    zone = Zone("dock", np.array([[0, 0], [100, 0], [100, 400], [0, 400]], dtype=np.int32))
    xs = [95, 105, 95, 105, 95, 105, 95]          # 경계선에서 들락날락
    legacy, episodic = ZoneMonitor([zone]), ZoneMonitor([zone], release_frames=5, cooldown_frames=30)
    ev_legacy, ev_epi = [], []
    for i, x in enumerate(xs):
        ev_legacy += legacy.update([person(x)], i)
        ev_epi += episodic.update([person(x)], i)
    assert len(ev_legacy) == 4                     # 이전 방식: 진입마다 기록
    assert phases(ev_epi) == [("start", "danger")] and ev_epi[0]["zone"] == "dock"
    assert ev_epi[0]["track_ids"] == [1]


# ---------------- 로깅 ----------------
def test_event_logger_counts_only_starts(tmp_path):
    d = nm()
    risky, safe = [person(0), vehicle(30)], [person(0), vehicle(80)]
    events = run(d, [safe] * 2 + [risky] * 3 + [[person(0)]] * 5)
    log = EventLogger(str(tmp_path / "e.csv"), fps=30)
    log.log(events)
    log.close()
    rows = list(csv.DictReader(open(tmp_path / "e.csv", encoding="utf-8")))
    assert [r["phase"] for r in rows] == ["start", "escalate", "end"]
    assert log.summary() == {"near_miss/warning": 1}
