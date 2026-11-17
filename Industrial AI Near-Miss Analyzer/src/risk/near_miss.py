"""사람-차량 근접위험(Near-Miss) 판정.

모든 거리는 바운딩 박스 **하단 중앙점(지면 접점)** 사이의 픽셀 거리이다.

[pixel 모드 - 기본, MVP]
  거리 ≤ danger_px  → "danger"
  거리 ≤ warning_px → "warning"
  이벤트는 EpisodeManager 로 묶어 중복 기록을 막는다 (start / escalate / end).
  ※ 원근 때문에 픽셀 거리는 실제 거리(m)와 비례하지 않는다. 결과는 "근접도 지표"로만 해석한다.

[TTC - 실험용, enable_ttc=False 기본]
  두 객체의 상대 위치 r, 상대 속도 u 로 등속 가정 하의 최근접 시각
      t* = - (r · u) / |u|²,   최소 거리 d_min = |r + u t*|
  픽셀 좌표 기반이라 정확하지 않다. 호모그래피(미터 좌표) 적용 후 정식 사용 예정.

[legacy 모드 - 구 설정 형식 호환]
  distance_px 만 주어지고 danger_px/warning_px 가 없으면 이전 버전 동작
  (현재 거리 ≤ distance_px → danger, TTC 예측 → warning, 쌍별 쿨다운)을 그대로 유지한다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from .episode import EpisodeManager

logger = logging.getLogger(__name__)


@dataclass
class PairRisk:
    person_id: int
    vehicle_id: int
    distance: float           # 현재 거리 (px)
    ttc: Optional[float]      # 최근접까지 시간 (sec), 멀어지는 중이면 None
    min_distance: float       # 예상 최소 거리 (px)
    closing_speed: float      # 접근 속도 (px/sec, +면 가까워지는 중)
    severity: Optional[str]   # "danger" / "warning" / None


def compute_pair_risk(
    p_pos: np.ndarray, p_vel: np.ndarray,
    v_pos: np.ndarray, v_vel: np.ndarray,
    distance_px: float, ttc_sec: float, min_closing_speed: float,
) -> Tuple[float, Optional[float], float, float, Optional[str]]:
    """위치(px), 속도(px/sec) 로 위험도를 계산하는 순수 함수."""
    r = v_pos - p_pos
    u = v_vel - p_vel
    dist = float(np.linalg.norm(r))
    closing = float(-(r @ u) / dist) if dist > 1e-9 else 0.0

    uu = float(u @ u)
    if uu < 1e-9 or closing <= 0:
        ttc, d_min = None, dist
    else:
        ttc = float(-(r @ u) / uu)
        d_min = float(np.linalg.norm(r + u * ttc))

    if dist <= distance_px:
        severity = "danger"
    elif (ttc is not None and ttc <= ttc_sec and d_min <= distance_px
          and closing >= min_closing_speed):
        severity = "warning"
    else:
        severity = None
    return dist, ttc, d_min, closing, severity


def pixel_severity(distance: float, danger_px: float, warning_px: float) -> Optional[str]:
    """하단 중앙점 간 픽셀 거리 → 위험 등급 (경계값 포함)."""
    if distance <= danger_px:
        return "danger"
    if distance <= warning_px:
        return "warning"
    return None


class NearMissDetector:
    def __init__(
        self,
        fps: float,
        danger_px: Optional[float] = None,
        warning_px: Optional[float] = None,
        enable_ttc: bool = False,
        release_frames: int = 15,
        cooldown_frames: int = 45,
        ttc_sec: float = 1.5,
        min_closing_speed: float = 20.0,
        distance_px: Optional[float] = None,   # legacy 설정 호환용
        person_category: str = "person",
        vehicle_category: str = "vehicle",
    ):
        self.fps = fps
        self.ttc_sec = ttc_sec
        self.min_closing_speed = min_closing_speed
        self.cooldown_frames = cooldown_frames
        self.person_category = person_category
        self.vehicle_category = vehicle_category

        if danger_px is None and warning_px is None and distance_px is not None:
            # ---- legacy 모드: 이전 버전과 동일한 판정/쿨다운 ----
            logger.warning("near_miss: 구 설정(distance_px) 감지 → legacy 모드(TTC+쿨다운). "
                           "danger_px / warning_px 사용을 권장합니다.")
            self.mode = "legacy"
            self.distance_px = distance_px
            self.enable_ttc = True
            self._last_event: Dict[Tuple[int, int], int] = {}
            self.episodes = None
            return

        if danger_px is None or warning_px is None:
            raise ValueError("near_miss: danger_px 와 warning_px 를 모두 설정해야 합니다.")
        if danger_px <= 0 or warning_px < danger_px:
            raise ValueError(f"near_miss: 0 < danger_px({danger_px}) ≤ warning_px({warning_px}) 이어야 합니다.")
        self.mode = "pixel"
        self.danger_px = float(danger_px)
        self.warning_px = float(warning_px)
        self.distance_px = self.danger_px
        self.enable_ttc = bool(enable_ttc)
        self.episodes = EpisodeManager("near_miss", "NM", release_frames, cooldown_frames, fps)

    # ------------------------------------------------------------------
    def evaluate(self, tracks) -> List[PairRisk]:
        persons = [t for t in tracks if t.category == self.person_category]
        vehicles = [t for t in tracks if t.category == self.vehicle_category]
        risks = []
        for p in persons:
            for v in vehicles:
                dist, ttc, d_min, closing, sev = compute_pair_risk(
                    p.foot_point, p.velocity * self.fps,
                    v.foot_point, v.velocity * self.fps,
                    self.distance_px, self.ttc_sec, self.min_closing_speed,
                )
                if self.mode == "pixel":
                    ttc_sev = sev
                    sev = pixel_severity(dist, self.danger_px, self.warning_px)
                    if sev is None and self.enable_ttc and ttc_sev == "warning":
                        sev = "warning"   # 실험용: 픽셀 TTC 예측 경고
                risks.append(PairRisk(p.track_id, v.track_id, dist, ttc, d_min, closing, sev))
        return risks

    def update(self, tracks, frame_idx: int) -> Tuple[List[PairRisk], List[Dict]]:
        """위험 쌍 목록과, 이번 프레임에 새로 기록할 이벤트 목록을 반환."""
        risks = self.evaluate(tracks)
        if self.mode == "legacy":
            return risks, self._legacy_events(risks, frame_idx)

        obs = {(r.person_id, r.vehicle_id): (r.severity, r.distance) for r in risks if r.severity}
        return risks, self._with_track_ids(self.episodes.update(frame_idx, obs))

    def close(self, frame_idx: int) -> List[Dict]:
        """영상 종료 시 진행 중인 에피소드 종료 기록 (legacy 모드는 없음)."""
        if self.mode == "legacy":
            return []
        return self._with_track_ids(self.episodes.close(frame_idx))

    # ------------------------------------------------------------------
    @staticmethod
    def _with_track_ids(events: List[Dict]) -> List[Dict]:
        for e in events:
            e["track_ids"] = list(e.pop("key"))
        return events

    def _legacy_events(self, risks: List[PairRisk], frame_idx: int) -> List[Dict]:
        events = []
        for r in risks:
            if r.severity is None:
                continue
            key = (r.person_id, r.vehicle_id)
            last = self._last_event.get(key)
            if last is not None and frame_idx - last < self.cooldown_frames:
                continue
            self._last_event[key] = frame_idx
            events.append({
                "frame": frame_idx,
                "type": "near_miss",
                "severity": r.severity,
                "track_ids": [r.person_id, r.vehicle_id],
                "distance_px": round(r.distance, 1),
                "ttc_sec": None if r.ttc is None else round(r.ttc, 2),
            })
        return events
