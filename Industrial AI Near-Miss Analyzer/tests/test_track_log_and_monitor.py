"""2일차 추가 기능 테스트: 트랙/프레임 로그, 구간 시간, meta, 리소스 모니터, 일괄 실행, 다운로드 도구 안전장치."""
import csv
import json
import os
import sys

import pytest

from src.pipeline import NearMissPipeline
from src.utils.resource_monitor import ResourceMonitor
from tests.test_pipeline_bytetrack import N_FRAMES, FakeTrackingDetector, make_cfg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import fetch_mendeley  # noqa: E402
import run_batch  # noqa: E402


def _enable_logs(cfg, tmp_path):
    cfg["output"]["track_log"] = str(tmp_path / "tracks.csv")
    cfg["output"]["frame_log"] = str(tmp_path / "frames.csv")
    cfg["perf"]["stage_timing"] = True
    cfg["meta"] = {"domain": "synthetic", "dataset": "unit-test", "clip": "fake"}
    return cfg


# ---------------- pipeline 선택 기능 ----------------
def test_optional_logs_are_disabled_by_default(tmp_path):
    cfg = make_cfg(tmp_path)
    pipe = NearMissPipeline(cfg, detector=FakeTrackingDetector())
    pipe.run()
    assert not (tmp_path / "tracks.csv").exists() and not (tmp_path / "frames.csv").exists()
    assert "stage_ms" not in pipe.perf
    assert "domain" not in pipe.perf["conditions"]


def test_track_and_frame_logs(tmp_path):
    cfg = _enable_logs(make_cfg(tmp_path), tmp_path)
    pipe = NearMissPipeline(cfg, detector=FakeTrackingDetector())
    pipe.run()

    frames = list(csv.DictReader(open(tmp_path / "frames.csv", encoding="utf-8")))
    assert len(frames) == N_FRAMES
    assert [int(r["det_person"]) for r in frames[:5]] == [0, 0, 0, 0, 0]   # 빈 프레임 + 미확정 프레임
    assert int(frames[10]["det_person"]) == 1 and int(frames[10]["track_vehicle"]) == 1
    assert int(frames[3]["untracked"]) == 2
    assert all(float(r["pipeline_ms"]) >= float(r["detector_ms"]) for r in frames)

    tracks = list(csv.DictReader(open(tmp_path / "tracks.csv", encoding="utf-8")))
    assert {r["category"] for r in tracks} == {"person", "vehicle"}
    assert {int(r["track_id"]) for r in tracks} == {1, 2}
    assert len(tracks) == 2 * (N_FRAMES - 5)
    # 하단 중앙점 = ((x1+x2)/2, y2)
    r = tracks[0]
    assert float(r["foot_x"]) == pytest.approx((float(r["x1"]) + float(r["x2"])) / 2)
    assert float(r["foot_y"]) == pytest.approx(float(r["y2"]))

    assert set(pipe.perf["stage_ms"]) == {"read", "detector", "track_risk", "draw", "encode", "display"}
    assert pipe.perf["stage_ms"]["encode"]["count"] == N_FRAMES - 10
    assert pipe.perf["conditions"]["domain"] == "synthetic" and pipe.perf["conditions"]["clip"] == "fake"
    saved = json.load(open(tmp_path / "perf.json", encoding="utf-8"))
    assert saved["conditions"]["domain"] == "synthetic"


# ---------------- 리소스 모니터 ----------------
def test_resource_monitor_without_gpu():
    mon = ResourceMonitor(interval=0.05, gpu_index=None)
    with mon:
        sum(i * i for i in range(200000))
        import time
        time.sleep(0.3)
    s = mon.summary()
    assert s["gpu_util_pct"] == "N/A" and s["gpu_mem_used_mib"] == "N/A"
    assert s["cpu_system_pct"]["count"] >= 2 and s["cpu_system_pct"]["max"] >= s["cpu_system_pct"]["mean"]
    assert any("GPU 측정 비활성화" in n for n in s["notes"])
    mon.close()


def test_resource_monitor_handles_missing_nvml(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "pynvml":
            raise ImportError("no nvml")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    mon = ResourceMonitor(interval=0.05, gpu_index=0)
    assert any("GPU 측정 불가" in n for n in mon.notes)
    assert "gpu_util_pct" not in mon.sample_once()


# ---------------- 일괄 실행 ----------------
def test_build_run_cfg_separates_outputs(tmp_path):
    base = make_cfg(tmp_path)
    base["detection"] = {"half": True}
    batch = {"meta": {"domain": "real_cctv"}, "overrides": {"risk": {"zones": []}, "perf": {"stage_timing": True}}}
    video = {"id": "v1", "path": "x.mp4"}
    c1, d1 = run_batch.build_run_cfg(base, batch, video, "fp16", False, str(tmp_path / "out"))
    c2, d2 = run_batch.build_run_cfg(base, batch, video, "fp32", True, str(tmp_path / "out"))
    assert d1 != d2 and d1.endswith(os.path.join("v1", "fp16_save_off")) and d2.endswith(os.path.join("v1", "fp32_save_on"))
    assert c1["detection"]["half"] is True and c2["detection"]["half"] is False
    assert c1["output"]["save_video"] is False and c2["output"]["save_video"] is True
    assert c1["risk"]["zones"] == [] and c1["meta"] == {"domain": "real_cctv", "clip": "v1"}
    assert base["risk"]["zones"]                       # 원본 설정은 변경되지 않음
    with pytest.raises(ValueError):
        run_batch.build_run_cfg(base, batch, video, "int8", False, str(tmp_path))


def test_run_batch_end_to_end_with_fake_detector(tmp_path):
    base = make_cfg(tmp_path)
    video_path = base["video"]["source"]
    batch = {"meta": {"domain": "synthetic", "dataset": "unit-test"},
             "videos": [{"id": "syn", "path": video_path}],
             "conditions": {"precisions": ["fp16", "fp32"], "save_video": [False, True]},
             "overrides": {"perf": {"warmup_frames": 10, "stage_timing": True}}}
    out = tmp_path / "batch"
    summary = run_batch.run_batch(base, batch, str(out), global_warmup=False,
                                  detector_factory=FakeTrackingDetector, monitor=False)
    assert len(summary["runs"]) == 4
    for r in summary["runs"]:
        files = set(r["files"])
        assert {"perf.json", "events.csv", "tracks.csv", "frames.csv", "resource.json", "run.json"} <= files
        assert ("result.mp4" in files) == r["save_video"]
        assert r["tracks"]["person"]["unique_ids"] == 1 and r["tracks"]["vehicle"]["unique_ids"] == 1
        assert r["frames"]["det_person"]["frames_with"] == N_FRAMES - 5
    on = next(r for r in summary["runs"] if r["save_video"] and r["precision"] == "fp16")
    assert on["perf"]["stage_ms"]["encode"]["mean_ms"] > 0
    md = (out / "summary.md").read_text(encoding="utf-8")
    assert "FP16 vs FP32" in md and "지게차 검출이 아님" in md


def test_track_stats_counts_short_and_long_tracks(tmp_path):
    p = tmp_path / "t.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["frame", "track_id", "category", "class_name", "score", "x1", "y1", "x2", "y2", "foot_x", "foot_y"])
        for i in range(40):
            w.writerow([i, 1, "person", "person", 0.9, 0, 0, 1, 1, 0.5, 1])
        for i in range(5):
            w.writerow([i, 2, "person", "person", 0.9, 0, 0, 1, 1, 0.5, 1])
        for i in list(range(10)) + list(range(20, 30)):           # 중간에 끊긴 트랙
            w.writerow([i, 7, "vehicle", "truck", 0.9, 0, 0, 1, 1, 0.5, 1])
    s = run_batch.track_stats(str(p))
    assert s["person"]["unique_ids"] == 2 and s["person"]["tracks_ge_30f"] == 1 and s["person"]["tracks_lt_10f"] == 1
    assert s["vehicle"]["tracks_with_gaps"] == 1 and s["vehicle"]["coco_classes"] == ["truck"]


# ---------------- 다운로드 도구 안전장치 ----------------
def test_fetch_mendeley_does_not_download_without_command(monkeypatch, capsys):
    called = []
    monkeypatch.setattr(fetch_mendeley, "list_files", lambda *a, **k: called.append("list") or [])
    monkeypatch.setattr(fetch_mendeley, "download", lambda *a, **k: called.append("download") or [])
    assert fetch_mendeley.main([]) == 2
    assert called == []                                   # 네트워크 호출도, 다운로드도 없음
    assert "download" in capsys.readouterr().out
    assert fetch_mendeley.main(["list", "--classes", "3_"]) == 0
    assert called == ["list"]                              # list 는 메타데이터 조회만


def test_fetch_mendeley_download_requires_dest():
    with pytest.raises(SystemExit):
        fetch_mendeley.main(["download", "--classes", "3_"])
