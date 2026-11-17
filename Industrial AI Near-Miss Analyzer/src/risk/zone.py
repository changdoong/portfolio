"""위험 구역(ROI) 정의 및 침입 판정."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

import cv2
import numpy as np

from .episode import EpisodeManager

LEVEL_COLORS = {"danger": (0, 0, 255), "warning": (0, 165, 255)}


@dataclass
class Zone:
    name: str
    polygon: np.ndarray       # (K, 2) int32
    level: str = "danger"

    @classmethod
    def from_config(cls, cfg: Dict) -> "Zone":
        return cls(cfg["name"], np.array(cfg["polygon"], dtype=np.int32), cfg.get("level", "danger"))

    def contains(self, point: Sequence[float]) -> bool:
        """점이 다각형 내부(경계 포함)에 있는지."""
        pt = (float(point[0]), float(point[1]))
        return cv2.pointPolygonTest(self.polygon.reshape(-1, 1, 2), pt, False) >= 0

    def draw(self, frame: np.ndarray, alpha: float = 0.25) -> None:
        color = LEVEL_COLORS.get(self.level, (255, 255, 255))
        overlay = frame.copy()
        cv2.fillPoly(overlay, [self.polygon], color)
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, dst=frame)
        cv2.polylines(frame, [self.polygon], True, color, 2)
        x, y = self.polygon[0]
        cv2.putText(frame, f"{self.name} [{self.level}]", (int(x), int(y) - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)


class ZoneMonitor:
    """사람의 지면 접점이 위험구역에 '새로' 진입할 때 이벤트 발생.

    - release_frames=None (기본): 이전 버전 동작. 밖→안 전이마다 이벤트 1건
    - release_frames 지정: EpisodeManager 로 침입을 에피소드화 (start / escalate / end).
      경계선 근처 흔들림으로 인한 반복 기록을 막는다.
    """

    def __init__(self, zones: List[Zone], target_category: str = "person",
                 release_frames: Optional[int] = None, cooldown_frames: int = 0, fps: float = 30.0):
        self.zones = zones
        self.target_category = target_category
        self._inside: Dict[tuple, bool] = {}   # (track_id, zone_name) -> 내부 여부
        self.episodes = None
        if release_frames is not None:
            self.episodes = EpisodeManager("zone_intrusion", "ZI", release_frames, cooldown_frames, fps)

    def set_fps(self, fps: float) -> None:
        if self.episodes is not None:
            self.episodes.fps = fps

    def update(self, tracks, frame_idx: int) -> List[Dict]:
        if self.episodes is not None:
            return self._episode_update(tracks, frame_idx)
        events = []
        for t in tracks:
            if t.category != self.target_category:
                continue
            for z in self.zones:
                key = (t.track_id, z.name)
                inside = z.contains(t.foot_point)
                if inside and not self._inside.get(key, False):
                    events.append({
                        "frame": frame_idx,
                        "type": "zone_intrusion",
                        "severity": z.level,
                        "track_ids": [t.track_id],
                        "zone": z.name,
                    })
                self._inside[key] = inside
        return events

    def _episode_update(self, tracks, frame_idx: int) -> List[Dict]:
        obs = {}
        for t in tracks:
            if t.category != self.target_category:
                continue
            for z in self.zones:
                if z.contains(t.foot_point):
                    obs[(t.track_id, z.name)] = (z.level, None)
        return self._with_fields(self.episodes.update(frame_idx, obs))

    def close(self, frame_idx: int) -> List[Dict]:
        if self.episodes is None:
            return []
        return self._with_fields(self.episodes.close(frame_idx))

    @staticmethod
    def _with_fields(events: List[Dict]) -> List[Dict]:
        for e in events:
            track_id, zone_name = e.pop("key")
            e["track_ids"] = [track_id]
            e["zone"] = zone_name
        return events

    def draw(self, frame: np.ndarray) -> None:
        for z in self.zones:
            z.draw(frame)
