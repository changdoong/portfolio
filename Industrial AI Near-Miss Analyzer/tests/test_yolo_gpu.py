"""실제 YOLOv8 + CUDA 통합 테스트.

기본: 가중치(models/yolov8n.pt) 또는 CUDA 가 없으면 skip.
REQUIRE_GPU=1 환경변수를 주면 skip 대신 **실패** 처리한다 (GPU 환경 검증 시 사용).

    $env:REQUIRE_GPU="1"; .\\.venv\\Scripts\\python.exe -m pytest -v tests/test_yolo_gpu.py
"""
import os
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = ROOT / "models" / "yolov8n.pt"
REQUIRE = os.environ.get("REQUIRE_GPU") == "1"


def _unavailable_reason():
    try:
        import torch
        import ultralytics  # noqa: F401
    except ImportError as e:
        return f"패키지 없음: {e}"
    if not torch.cuda.is_available():
        return "CUDA 사용 불가"
    if not WEIGHTS.exists():
        return f"가중치 없음: {WEIGHTS}"
    return None


@pytest.fixture(scope="module")
def detector():
    reason = _unavailable_reason()
    if reason:
        if REQUIRE:
            pytest.fail(f"REQUIRE_GPU=1 인데 실행 불가: {reason}")
        pytest.skip(reason)
    from src.detection.detector import YOLODetector

    return YOLODetector(str(WEIGHTS), device="cuda:0", half=True, tracker_cfg=str(ROOT / "configs" / "bytetrack.yaml"))


@pytest.fixture(scope="module")
def bus_image():
    import cv2
    import ultralytics

    img = cv2.imread(str(Path(ultralytics.__file__).parent / "assets" / "bus.jpg"))
    assert img is not None
    return img


def test_runs_on_cuda_fp16(detector, bus_image):
    import torch

    assert detector.device == "cuda:0" and detector.half is True
    detector.detect(bus_image)
    param = next(detector.torch_module().parameters())
    assert param.device.type == "cuda"
    assert param.dtype == torch.float16
    assert detector.last_speed["inference"] > 0


def test_detects_person_and_vehicle(detector, bus_image):
    dets = detector.detect(bus_image)
    cats = [d.category for d in dets]
    assert cats.count("person") >= 1 and cats.count("vehicle") >= 1
    assert all(d.track_id is None for d in dets)


def test_bytetrack_ids_are_stable(detector, bus_image):
    detector.reset_tracking()
    id_sets = []
    for _ in range(5):
        dets = detector.track(bus_image)
        assert all(d.track_id is not None for d in dets)
        id_sets.append(sorted(d.track_id for d in dets))
    assert len(id_sets[-1]) >= 2
    assert id_sets[-1] == id_sets[-2] == id_sets[-3]     # 정지 영상 → ID 유지


def test_bytetrack_adapter_on_real_output(detector, bus_image):
    from src.tracking.tracker import ByteTrackAdapter

    detector.reset_tracking()
    ad = ByteTrackAdapter()
    for _ in range(3):
        tracks = ad.update(detector.track(bus_image))
    assert {t.category for t in tracks} >= {"person", "vehicle"}
    np.testing.assert_allclose(tracks[0].velocity, [0, 0], atol=1.0)
