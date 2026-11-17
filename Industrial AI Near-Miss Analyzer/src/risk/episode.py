"""위험 이벤트 에피소드 관리 (중복 기록 방지).

같은 대상(사람-차량 쌍, 사람-구역)의 위험 상태를 하나의 "에피소드"로 묶는다.

    [안전] ──위험 관측──▶ [진행 중] ──release_frames 연속 미관측──▶ [종료] ──cooldown_frames──▶ [안전]
            phase=start      위험 등급 상승 시 phase=escalate (1회)        phase=end

- release_frames : 잠깐 위험이 끊기는 깜빡임(검출 누락, 경계선 흔들림)을 무시하는 유지 시간
- cooldown_frames: 에피소드 종료 후 같은 대상의 새 에피소드 시작을 억제하는 시간
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Hashable, List, Optional, Tuple

SEVERITY_RANK = {"warning": 1, "danger": 2}

# key -> (severity, distance_px 또는 None)
Observation = Tuple[str, Optional[float]]


@dataclass
class Episode:
    event_id: str
    key: Hashable
    start_frame: int
    last_risk_frame: int
    max_severity: str
    min_distance: Optional[float]
    missing: int = 0


class EpisodeManager:
    def __init__(self, event_type: str, id_prefix: str, release_frames: int = 15,
                 cooldown_frames: int = 90, fps: float = 30.0):
        if release_frames < 1:
            raise ValueError("release_frames 는 1 이상이어야 합니다.")
        if cooldown_frames < 0:
            raise ValueError("cooldown_frames 는 0 이상이어야 합니다.")
        self.event_type = event_type
        self.id_prefix = id_prefix
        self.release_frames = release_frames
        self.cooldown_frames = cooldown_frames
        self.fps = fps
        self.active: Dict[Hashable, Episode] = {}
        self._last_end: Dict[Hashable, int] = {}
        self._counter = 0

    # ------------------------------------------------------------------
    def update(self, frame_idx: int, observations: Dict[Hashable, Observation]) -> List[Dict]:
        """이번 프레임에서 위험한 대상만 observations 로 전달한다."""
        events: List[Dict] = []
        for key, (severity, dist) in observations.items():
            ep = self.active.get(key)
            if ep is None:
                last_end = self._last_end.get(key)
                if last_end is not None and frame_idx - last_end < self.cooldown_frames:
                    continue
                self._counter += 1
                ep = Episode(f"{self.id_prefix}-{self._counter:05d}", key, frame_idx, frame_idx, severity, dist)
                self.active[key] = ep
                events.append(self._event(ep, frame_idx, "start", severity, dist))
                continue

            ep.missing = 0
            ep.last_risk_frame = frame_idx
            if dist is not None:
                ep.min_distance = dist if ep.min_distance is None else min(ep.min_distance, dist)
            if SEVERITY_RANK.get(severity, 0) > SEVERITY_RANK.get(ep.max_severity, 0):
                ep.max_severity = severity
                events.append(self._event(ep, frame_idx, "escalate", severity, dist))

        for key in [k for k in self.active if k not in observations]:
            ep = self.active[key]
            ep.missing += 1
            if ep.missing >= self.release_frames:
                events.append(self._end(ep, frame_idx))
        return events

    def close(self, frame_idx: int) -> List[Dict]:
        """영상 종료 시 진행 중인 에피소드를 모두 종료 기록."""
        return [self._end(ep, frame_idx) for ep in list(self.active.values())]

    # ------------------------------------------------------------------
    def _end(self, ep: Episode, frame_idx: int) -> Dict:
        del self.active[ep.key]
        self._last_end[ep.key] = frame_idx
        e = self._event(ep, frame_idx, "end", ep.max_severity, None)
        e["duration_sec"] = round((ep.last_risk_frame - ep.start_frame + 1) / self.fps, 2)
        e["min_distance_px"] = None if ep.min_distance is None else round(ep.min_distance, 1)
        e["max_severity"] = ep.max_severity
        return e

    def _event(self, ep: Episode, frame_idx: int, phase: str, severity: str, dist: Optional[float]) -> Dict:
        return {
            "key": ep.key,            # 호출 측에서 track_ids / zone 으로 변환 후 제거
            "frame": frame_idx,
            "type": self.event_type,
            "phase": phase,
            "event_id": ep.event_id,
            "severity": severity,
            "distance_px": None if dist is None else round(dist, 1),
        }
