"""장치/정밀도 자동 결정 + 지연시간 통계 테스트."""
import pytest

from src.detection.detector import resolve_device
from src.utils.metrics import LatencyStats


@pytest.mark.parametrize("device, half, cuda, expected", [
    ("cuda:0", True, True, ("cuda:0", True)),
    ("cuda:0", False, True, ("cuda:0", False)),
    ("0", True, True, ("0", True)),
    ("cuda:0", True, False, ("cpu", False)),    # CUDA 없음 → CPU + FP32 폴백
    ("cpu", True, True, ("cpu", False)),        # CPU 에서는 항상 FP32
    ("CPU", False, False, ("cpu", False)),
])
def test_resolve_device(device, half, cuda, expected):
    assert resolve_device(device, half, cuda_available=cuda) == expected


def test_latency_stats_excludes_warmup():
    s = LatencyStats(warmup=3)
    for ms in [100, 100, 100] + [10] * 9 + [20]:
        s.add(ms)
    s.add(None)                                  # 측정 불가 값은 무시
    r = s.summary()
    assert r["count"] == 10 and r["warmup"] == 3
    assert r["mean_ms"] == pytest.approx(11.0)
    assert r["p50_ms"] == pytest.approx(10.0)
    assert r["fps"] == pytest.approx(1000 / 11, abs=0.01)


def test_latency_stats_empty():
    assert LatencyStats(warmup=5).summary() == {"count": 0, "warmup": 5}
