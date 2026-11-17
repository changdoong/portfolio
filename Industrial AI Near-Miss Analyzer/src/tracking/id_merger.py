"""ByteTrack ID 단절 병합 (D3-4). ByteTrack 설정·원본 track_id 는 변경하지 않는다.

ByteTrack 이 객체를 놓쳤다가 새 ID 로 다시 잡는 경우, 새 raw track_id 를 직전에 사라진 트랙의
canonical_track_id 로 연결한다. 원본 track_id 는 그대로 보존되고, 병합 결과는 별도 매핑으로 관리한다.

병합 조건 (모두 만족)
  - 새 raw ID 가 처음 등장
  - 같은 카테고리의 canonical 트랙이 max_gap_frames 이내에 마지막으로 관측되었고, 현재 프레임에 활성 상태가 아님
  - 마지막 하단 중앙점(+ 선택적으로 속도 외삽) 과의 거리 ≤ max_dist_px
  - 후보가 여럿이면 가장 가까운 canonical 선택
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np


class IdMerger:
    def __init__(self, max_gap_frames: int = 30, max_dist_px: float = 80.0, use_velocity: bool = True,
                 min_history_for_velocity: int = 5):
        if max_gap_frames < 1 or max_dist_px <= 0:
            raise ValueError("max_gap_frames ≥ 1, max_dist_px > 0 이어야 합니다.")
        self.max_gap = max_gap_frames
        self.max_dist = float(max_dist_px)
        self.use_velocity = use_velocity
        self.min_hist = min_history_for_velocity
        self.raw_to_can: Dict[int, int] = {}
        self._last: Dict[int, Tuple[int, np.ndarray, np.ndarray, str]] = {}   # can -> (frame, foot, vel, category)
        self.merges: List[Dict] = []

    def _vel(self, t) -> np.ndarray:
        if not self.use_velocity or len(getattr(t, "history", ())) < self.min_hist:
            return np.zeros(2)
        return np.asarray(t.velocity, dtype=float)

    def update(self, tracks, frame_idx: int) -> Dict[int, int]:
        """raw track_id → canonical_track_id 매핑 (현재 프레임 트랙만) 반환."""
        active = {self.raw_to_can[t.track_id] for t in tracks if t.track_id in self.raw_to_can}
        for t in tracks:
            if t.track_id in self.raw_to_can:
                continue
            best = None
            for can, (lf, foot, vel, cat) in self._last.items():
                gap = frame_idx - lf
                if cat != t.category or can in active or gap <= 0 or gap > self.max_gap:
                    continue
                d = float(np.linalg.norm(np.asarray(t.foot_point) - (foot + vel * gap)))
                if d <= self.max_dist and (best is None or d < best[1]):
                    best = (can, d, gap)
            can = t.track_id
            if best is not None:
                can = best[0]
                self.merges.append({"frame": frame_idx, "category": t.category, "raw_track_id": t.track_id,
                                    "canonical_track_id": can, "gap_frames": best[2], "dist_px": round(best[1], 1)})
            self.raw_to_can[t.track_id] = can
            active.add(can)
        for t in tracks:
            self._last[self.raw_to_can[t.track_id]] = (frame_idx, np.asarray(t.foot_point, float).copy(),
                                                       self._vel(t).copy(), t.category)
        self._last = {c: v for c, v in self._last.items() if frame_idx - v[0] <= self.max_gap}
        return {t.track_id: self.raw_to_can[t.track_id] for t in tracks}
