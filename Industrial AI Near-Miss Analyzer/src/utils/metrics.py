"""성능/평가 지표 유틸."""
from __future__ import annotations

import csv
import os
import time
from collections import Counter, deque
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np


class FPSMeter:
    """최근 N 프레임 이동평균 FPS."""

    def __init__(self, window: int = 30):
        self._times = deque(maxlen=window)

    def tick(self) -> float:
        self._times.append(time.perf_counter())
        return self.fps

    @property
    def fps(self) -> float:
        if len(self._times) < 2:
            return 0.0
        return (len(self._times) - 1) / (self._times[-1] - self._times[0])


class LatencyStats:
    """구간 처리 시간(ms) 통계. 처음 warmup 개 샘플은 제외 (CUDA 초기화·cudnn 튜닝 영향 제거)."""

    def __init__(self, warmup: int = 10):
        self.warmup = warmup
        self.seen = 0
        self.samples: List[float] = []

    def add(self, ms: Optional[float]) -> None:
        if ms is None:
            return
        self.seen += 1
        if self.seen > self.warmup:
            self.samples.append(float(ms))

    def summary(self) -> Dict[str, float]:
        if not self.samples:
            return {"count": 0, "warmup": self.warmup}
        arr = np.asarray(self.samples)
        mean = float(arr.mean())
        return {
            "count": int(arr.size),
            "warmup": self.warmup,
            "mean_ms": round(mean, 3),
            "p50_ms": round(float(np.percentile(arr, 50)), 3),
            "p95_ms": round(float(np.percentile(arr, 95)), 3),
            "fps": round(1000.0 / mean, 2) if mean > 0 else None,
        }


class EventLogger:
    """이벤트를 CSV 로 저장하고 유형별 통계를 집계.

    에피소드 방식 이벤트(phase=start/escalate/end)는 start 만 집계하여 '에피소드 수'를 센다.
    phase 가 없는 이전 형식 이벤트는 모두 집계한다.
    """

    FIELDS = ["frame", "time_sec", "type", "phase", "event_id", "severity", "track_ids", "zone",
              "distance_px", "min_distance_px", "max_severity", "duration_sec", "ttc_sec"]

    def __init__(self, path: str, fps: float):
        self.path = path
        self.fps = fps
        self.counter: Counter = Counter()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._f = open(path, "w", newline="", encoding="utf-8")
        self._w = csv.DictWriter(self._f, fieldnames=self.FIELDS, extrasaction="ignore")
        self._w.writeheader()

    def log(self, events: Iterable[Dict]) -> None:
        for e in events:
            row = dict(e)
            row["time_sec"] = round(e["frame"] / self.fps, 2)
            row["track_ids"] = "-".join(map(str, e.get("track_ids", [])))
            self._w.writerow(row)
            if e.get("phase") in (None, "start"):
                self.counter[(e["type"], e["severity"])] += 1

    def close(self) -> None:
        self._f.close()

    def summary(self) -> Dict[str, int]:
        return {f"{t}/{s}": n for (t, s), n in sorted(self.counter.items())}


def event_precision_recall(
    predicted_frames: List[int], gt_frames: List[int], tolerance: int = 15
) -> Tuple[float, float, float]:
    """라벨링된 실제 위험 시점(gt) 대비 이벤트 검출 Precision / Recall / F1.

    예측 이벤트가 gt 프레임 ±tolerance 안에 있으면 TP 로 간주 (1:1 매칭).
    """
    gt_left = sorted(gt_frames)
    tp = 0
    for p in sorted(predicted_frames):
        match = next((g for g in gt_left if abs(g - p) <= tolerance), None)
        if match is not None:
            gt_left.remove(match)
            tp += 1
    precision = tp / len(predicted_frames) if predicted_frames else 0.0
    recall = tp / len(gt_frames) if gt_frames else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1
