"""정지 물체 필터 (D3-2). vehicle 트랙을 근접 판정에서 제외할지 결정한다.

정지 상태라는 이유만으로 vehicle 을 제거하지 않는다. 판정 순서 (canonical track 기준, 상태는 누적):
  1) dynamic         : 한 번이라도 move_px 이상 이동한 트랙 → 이후 정차해도 계속 보호 (정차 지게차)
  2) protected_large : 박스 높이 ≥ protect_min_h_ratio × 프레임 높이 → 보호 (카메라 근처에 정차한 지게차 가능성)
  3) ignored_zone    : 이동 이력 없음 + 하단 중앙점이 무시 구역 안 → 제외
  4) static          : 이동 이력 없음 + min_frames 이상 관측 → 제외
  5) pending         : 관측 프레임 부족 → 포함 (위험 누락 방지 우선)
"""
from __future__ import annotations

from typing import Dict, List, Sequence

import cv2
import numpy as np

EXCLUDED = ("ignored_zone", "static")


class StaticObjectFilter:
    def __init__(self, move_px: float = 25.0, min_frames: int = 15, protect_min_h_ratio: float = 0.2,
                 ignore_zones: Sequence[Sequence[Sequence[float]]] = (), category: str = "vehicle"):
        if move_px <= 0 or min_frames < 1:
            raise ValueError("move_px > 0, min_frames ≥ 1 이어야 합니다.")
        self.move_px = float(move_px)
        self.min_frames = int(min_frames)
        self.protect_h = float(protect_min_h_ratio)
        self.zones = [np.asarray(z, dtype=np.float32).reshape(-1, 1, 2) for z in ignore_zones]
        self.category = category
        self._state: Dict[int, Dict] = {}
        self.status: Dict[int, str] = {}
        self.log: List[Dict] = []

    def _in_zone(self, foot) -> bool:
        pt = (float(foot[0]), float(foot[1]))
        return any(cv2.pointPolygonTest(z, pt, False) >= 0 for z in self.zones)

    def update(self, views, frame_idx: int, frame_h: int) -> Dict[int, str]:
        for v in views:
            if v.category != self.category:
                continue
            foot = np.asarray(v.foot_point, float)
            s = self._state.setdefault(v.track_id, {"origin": foot.copy(), "max_disp": 0.0, "frames": 0, "moved": False})
            s["frames"] += 1
            s["max_disp"] = max(s["max_disp"], float(np.linalg.norm(foot - s["origin"])))
            s["moved"] = s["moved"] or s["max_disp"] >= self.move_px
            h = float(v.bbox[3] - v.bbox[1])
            if s["moved"]:
                st = "dynamic"
            elif h >= self.protect_h * frame_h:
                st = "protected_large"
            elif self._in_zone(foot):
                st = "ignored_zone"
            elif s["frames"] >= self.min_frames:
                st = "static"
            else:
                st = "pending"
            if self.status.get(v.track_id) != st:
                self.log.append({"frame": frame_idx, "canonical_track_id": v.track_id, "status": st,
                                 "max_disp_px": round(s["max_disp"], 1), "frames_seen": s["frames"],
                                 "bbox_h": round(h, 1), "excluded": st in EXCLUDED})
            self.status[v.track_id] = st
        return self.status

    def excluded(self, track_id: int) -> bool:
        return self.status.get(track_id) in EXCLUDED
