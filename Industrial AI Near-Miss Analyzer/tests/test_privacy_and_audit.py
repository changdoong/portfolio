"""비식별 처리(src/utils/privacy.py)와 감사 스크립트 보조 함수 테스트."""
import os
import sys

import numpy as np
import pytest

from src.utils import privacy
from src.utils.privacy import PrivacyError, anonymize, find_people, ioa, privacy_regions

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import audit_events  # noqa: E402
import audit_tracks  # noqa: E402
import make_captures  # noqa: E402


def noise(h=720, w=1280, seed=0):
    return np.random.default_rng(seed).integers(0, 256, (h, w, 3), dtype=np.uint8)


def test_anonymize_mosaics_every_region_and_keeps_rest():
    img = noise()
    person = (600, 300, 660, 450)
    out, regions = anonymize(img, [person], [], static_masks=[])
    hx1, hy1, hx2, hy2 = privacy.clip_box(privacy.head_region(person), 1280, 720)
    assert not np.array_equal(out[hy1:hy2, hx1:hx2], img[hy1:hy2, hx1:hx2])
    assert np.array_equal(out[600:700, 0:200], img[600:700, 0:200])          # 영역 밖은 그대로
    assert [k for k, _ in regions] == ["person_head"]


def test_static_mask_and_large_vehicle_cab():
    regions = privacy_regions([], [(500, 100, 800, 500), (10, 10, 60, 50)], 1280, 720)
    kinds = [k for k, _ in regions]
    assert kinds.count("static_mask") == 1
    assert kinds.count("vehicle_cab") == 1        # 작은 차량(높이 40px)은 운전석 마스크 대상 아님


def test_overlapping_regions_verify_ok():
    img = noise(seed=1)
    out, _ = anonymize(img, [(600, 300, 660, 450), (620, 310, 680, 460)], [(550, 200, 800, 600)])
    assert out.shape == img.shape


def test_verification_failure_raises(monkeypatch):
    monkeypatch.setattr(privacy, "region_mask", lambda regions, w, h: np.zeros((h, w), bool))  # 적용 누락 시뮬레이션
    with pytest.raises(PrivacyError):
        anonymize(noise(seed=2), [(600, 300, 660, 450)], [], static_masks=[])


def test_find_people_requires_detector():
    with pytest.raises(PrivacyError):
        find_people(None, noise(), [])


def test_find_people_maps_crop_coordinates_back():
    class D:
        def __init__(self, bbox):
            self.bbox, self.category = np.array(bbox, float), "person"

    class Det:
        def detect(self, frame):
            return [D((20, 10, 40, 60))] if frame.shape[:2] == (200, 200) else []   # crop(100x100 *2) 에서만 검출

    people = find_people(Det(), noise(), [(300, 200, 400, 300)], crop_scale=2.0)
    assert people == [(310.0, 205.0, 320.0, 230.0)]


def test_ioa():
    assert ioa((0, 0, 10, 10), (0, 0, 20, 20)) == 1.0
    assert ioa((0, 0, 10, 10), (5, 0, 20, 20)) == 0.5
    assert ioa((0, 0, 10, 10), (50, 50, 60, 60)) == 0.0


# ---------------- 감사 스크립트 ----------------
def test_audit_likelihoods():
    assert audit_events.likelihoods(0.9, 0.8, 0.9) == ("높음", "낮음")
    assert audit_events.likelihoods(0.77, 0.5, 0.1) == ("중간", "중간")
    assert audit_events.likelihoods(0.0, 0.0, None) == ("낮음", "높음")


def test_co_motion_detects_moving_together():
    series = {f: ((100 + 3 * f, 100, 120 + 3 * f, 160), (90 + 3 * f, 80, 200 + 3 * f, 170)) for f in range(10)}
    for f in series:                               # 약간의 독립 잡음
        p, v = series[f]
        series[f] = (p, (v[0], v[1], v[2], v[3] + (f % 3)))
    assert audit_events.co_motion(series) > 0.5
    assert audit_events.co_motion({0: series[0]}) is None


def _row(f, tid, x1, y1, x2, y2, cls="car"):
    return {"frame": str(f), "track_id": str(tid), "category": "vehicle", "class_name": cls, "score": "0.4",
            "x1": x1, "y1": y1, "x2": x2, "y2": y2}


def test_audit_tracks_hints():
    by_frame = {}
    for f in range(30):                            # 장기 트랙(실제 차량)
        by_frame.setdefault(f, []).append(_row(f, 1, 100 + 5 * f, 100, 300 + 5 * f, 300, "truck"))
    by_frame[10].append(_row(10, 2, 150, 100, 350, 300, "bus"))          # 중복 박스
    for f in (40, 41, 42):
        by_frame.setdefault(f, []).append(_row(f, 3, 10, 10, 50, 40))      # 정지 물체
    rows = {r["track_id"]: r for r in audit_tracks.analyze(audit_tracks.track_table(by_frame))}
    assert set(rows) == {2, 3}
    assert rows[2]["auto_hint"] == "duplicate_box" and rows[2]["overlap_with_track"] == "1"
    assert rows[3]["auto_hint"] == "static_object" and rows[3]["move_px"] == 0.0


def test_scripts_refuse_existing_output(tmp_path):
    out = tmp_path / "exists"
    out.mkdir()
    assert make_captures.main(["--out", str(out)]) == 1
    assert audit_events.main(["--out", str(out)]) == 1
    assert audit_tracks.main(["--video", "x", "--out", str(out)]) == 1
    assert os.listdir(out) == []
