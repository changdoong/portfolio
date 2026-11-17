"""ByteTrackAdapter / build_tracker 테스트 (ultralytics 불필요)."""
import numpy as np
import pytest

from src.detection.detector import Detection
from src.tracking.tracker import ByteTrackAdapter, IoUTracker, build_tracker


def det(x, y, tid, cat="person", w=20, h=40):
    return Detection(np.array([x - w / 2, y - h, x + w / 2, y], dtype=float), 0.9, 0, cat, track_id=tid)


def test_empty_detections_are_normal():
    ad = ByteTrackAdapter(max_age=5)
    assert ad.update([]) == []                      # 검출 없음 → 정상 빈 목록
    ad.update([det(100, 100, 1)])
    assert ad.update([]) == []                      # 사라진 프레임도 정상
    assert ad.get(1).age == 1                       # 미관측 처리됨


def test_missing_track_id_raises_only_when_detections_exist():
    ad = ByteTrackAdapter()
    with pytest.raises(ValueError, match="track_id"):
        ad.update([det(100, 100, 1), det(200, 100, None)])


def test_duplicate_track_id_raises():
    with pytest.raises(ValueError, match="중복"):
        ByteTrackAdapter().update([det(100, 100, 7), det(300, 100, 7)])


def test_keeps_external_ids_and_estimates_velocity():
    ad = ByteTrackAdapter()
    for i in range(10):
        tracks = ad.update([det(100 + 3 * i, 200, 42), det(400, 200, 9, "vehicle")])
    ids = sorted(t.track_id for t in tracks)
    assert ids == [9, 42]
    np.testing.assert_allclose(ad.get(42).velocity, [3, 0], atol=1e-6)
    np.testing.assert_allclose(ad.get(9).velocity, [0, 0], atol=1e-6)


def test_category_follows_latest_detection():
    ad = ByteTrackAdapter()
    ad.update([det(100, 100, 1, "person")])
    ad.update([det(100, 100, 1, "vehicle")])
    assert ad.get(1).category == "vehicle"


def test_drops_tracks_after_max_age():
    ad = ByteTrackAdapter(max_age=2)
    ad.update([det(100, 100, 1)])
    for _ in range(3):
        ad.update([])
    assert ad.get(1) is None and ad.tracks == []


def test_build_tracker_types():
    t, tr = build_tracker({"iou_threshold": 0.3, "max_age": 5, "min_hits": 2, "history_len": 30})
    assert t == "iou" and isinstance(tr, IoUTracker) and tr.min_hits == 2      # 구 형식 호환

    t, tr = build_tracker({"type": "bytetrack", "max_age": 7, "history_len": 20})
    assert t == "bytetrack" and isinstance(tr, ByteTrackAdapter) and tr.max_age == 7

    t, tr = build_tracker({"type": "iou", "max_age": 7, "iou": {"iou_threshold": 0.4, "min_hits": 1}})
    assert t == "iou" and isinstance(tr, IoUTracker) and tr.iou_threshold == 0.4 and tr.max_age == 7

    with pytest.raises(ValueError):
        build_tracker({"type": "sort"})
