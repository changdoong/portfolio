import numpy as np

from src.detection.detector import Detection
from src.risk.near_miss import NearMissDetector, compute_pair_risk
from src.risk.zone import Zone, ZoneMonitor
from src.tracking.tracker import IoUTracker, iou_matrix
from src.utils.metrics import event_precision_recall

KW = dict(distance_px=50, ttc_sec=2.0, min_closing_speed=10.0)


def det(x, y, cat="person", w=20, h=40):
    return Detection(np.array([x - w / 2, y - h, x + w / 2, y], dtype=float), 0.9, 0, cat)


# ---------------- near-miss ----------------
def test_already_close_is_danger():
    *_, sev = compute_pair_risk(np.array([0, 0.]), np.zeros(2), np.array([30, 0.]), np.zeros(2), **KW)
    assert sev == "danger"


def test_head_on_approach_is_warning_with_correct_ttc():
    # 150px 떨어진 차량이 100px/s 로 정면 접근 → TTC 1.5s, 최소거리 0
    dist, ttc, d_min, closing, sev = compute_pair_risk(
        np.array([0, 0.]), np.zeros(2), np.array([150, 0.]), np.array([-100, 0.]), **KW
    )
    assert abs(ttc - 1.5) < 1e-6 and d_min < 1e-6 and closing == 100
    assert sev == "warning"


def test_moving_away_is_safe():
    *_, ttc, _, closing, sev = compute_pair_risk(
        np.array([0, 0.]), np.zeros(2), np.array([150, 0.]), np.array([100, 0.]), **KW
    )
    assert ttc is None and closing < 0 and sev is None


def test_passing_by_far_is_safe():
    # 수직 방향으로 200px 떨어진 채 지나감 → 최소거리 200 > 50
    *_, d_min, _, sev = compute_pair_risk(
        np.array([0, 0.]), np.zeros(2), np.array([100, 200.]), np.array([-100, 0.]), **KW
    )
    assert abs(d_min - 200) < 1e-6 and sev is None


def test_near_miss_cooldown():
    tracker = IoUTracker(min_hits=1)
    nm = NearMissDetector(fps=30, cooldown_frames=10, **KW)
    tracks = tracker.update([det(100, 100), det(120, 100, "vehicle", w=60)])
    _, e0 = nm.update(tracks, 0)
    _, e1 = nm.update(tracks, 5)
    _, e2 = nm.update(tracks, 12)
    assert len(e0) == 1 and len(e1) == 0 and len(e2) == 1


# ---------------- tracker ----------------
def test_iou_matrix():
    a = np.array([[0, 0, 10, 10.]])
    b = np.array([[0, 0, 10, 10.], [5, 0, 15, 10.], [20, 20, 30, 30.]])
    np.testing.assert_allclose(iou_matrix(a, b), [[1.0, 1 / 3, 0.0]])


def test_tracker_keeps_id_and_estimates_velocity():
    tr = IoUTracker(min_hits=1)
    for i in range(10):
        tracks = tr.update([det(100 + 3 * i, 200)])
    assert len(tracks) == 1 and tracks[0].track_id == 1
    np.testing.assert_allclose(tracks[0].velocity, [3, 0], atol=1e-6)


def test_tracker_does_not_match_across_categories():
    tr = IoUTracker(min_hits=1)
    tr.update([det(100, 100, "person")])
    tracks = tr.update([det(100, 100, "vehicle")])
    assert [t.track_id for t in tracks] == [2]


def test_tracker_drops_old_tracks():
    tr = IoUTracker(min_hits=1, max_age=2)
    tr.update([det(100, 100)])
    for _ in range(3):
        tr.update([])
    assert tr.tracks == []


# ---------------- zone ----------------
def test_zone_intrusion_fires_once_on_entry():
    zone = Zone("dock", np.array([[0, 0], [100, 0], [100, 100], [0, 100]], dtype=np.int32))
    mon = ZoneMonitor([zone])
    tr = IoUTracker(min_hits=1)
    events = []
    for i, x in enumerate([125, 115, 105, 95, 85]):   # 밖 → 안으로 이동 (10px/frame)
        events += mon.update(tr.update([det(x, 50)]), i)
    assert len(events) == 1 and events[0]["frame"] == 3


# ---------------- metrics ----------------
def test_event_precision_recall():
    p, r, f1 = event_precision_recall([10, 100, 300], [12, 105, 500], tolerance=10)
    assert (p, r) == (2 / 3, 2 / 3) and abs(f1 - 2 / 3) < 1e-9
