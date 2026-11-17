"""추적 결과 후처리 묶음: ID 병합(D3-4) → 정지 물체 필터(D3-2) → 운전자 구분(D3-3).

설정 `analysis` 가 없거나 모든 하위 기능이 enabled: false 이면 사용되지 않는다 (기존 동작과 동일).

    analysis:
      id_merge:      {enabled: false, max_gap_frames: 30, max_dist_px: 80, use_velocity: true}
      static_filter: {enabled: false, move_px: 25, min_frames: 15, protect_min_h_ratio: 0.2, ignore_zones: []}
      role:          {enabled: false, window: 15, min_frames: 8, ioa_thr: 0.5, cab_ratio_thr: 0.6,
                      foot_margin_ratio: 0.05, co_motion_tol: 0.5, still_px: 1.0}
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from src.risk.object_filter import StaticObjectFilter
from src.risk.role_classifier import RoleClassifier
from src.tracking.id_merger import IdMerger


class TrackView:
    """Track 를 감싸 track_id 를 canonical ID 로 보여준다. 원본 ID 는 raw_track_id 로 보존."""

    def __init__(self, track, canonical_id: int):
        self._track = track
        self.track_id = canonical_id
        self.raw_track_id = track.track_id
        self.vehicle_status: Optional[str] = None
        self.person_role: Optional[str] = None

    def __getattr__(self, name):
        return getattr(self._track, name)


def _opts(cfg: Optional[Dict], key: str) -> Optional[Dict]:
    sub = (cfg or {}).get(key) or {}
    if not sub.get("enabled", False):
        return None
    return {k: v for k, v in sub.items() if k != "enabled"}


class TrackAnalyzer:
    def __init__(self, id_merge: Optional[Dict] = None, static_filter: Optional[Dict] = None,
                 role: Optional[Dict] = None):
        self.merger = IdMerger(**id_merge) if id_merge is not None else None
        self.static = StaticObjectFilter(**static_filter) if static_filter is not None else None
        self.role = RoleClassifier(**role) if role is not None else None

    @classmethod
    def from_config(cls, cfg: Optional[Dict]) -> Optional["TrackAnalyzer"]:
        parts = {k: _opts(cfg, k) for k in ("id_merge", "static_filter", "role")}
        if all(v is None for v in parts.values()):
            return None
        return cls(**parts)

    @property
    def enabled_features(self) -> List[str]:
        return [n for n, o in (("id_merge", self.merger), ("static_filter", self.static), ("role", self.role)) if o]

    def process(self, tracks, frame_idx: int, frame_h: int) -> Tuple[List[TrackView], List[TrackView], Set]:
        """반환: (전체 view, 근접 판정용 view, 제외할 (person,vehicle) 쌍)."""
        mapping = self.merger.update(tracks, frame_idx) if self.merger else {t.track_id: t.track_id for t in tracks}
        views = [TrackView(t, mapping[t.track_id]) for t in tracks]

        risk_views = views
        if self.static:
            status = self.static.update(views, frame_idx, frame_h)
            for v in views:
                if v.category == "vehicle":
                    v.vehicle_status = status.get(v.track_id)
            risk_views = [v for v in views if not (v.category == "vehicle" and self.static.excluded(v.track_id))]

        exclude: Set[Tuple[int, int]] = set()
        if self.role:
            exclude = self.role.update(views, frame_idx)
            drivers = {p for p, _ in exclude}
            for v in views:
                if v.category == "person":
                    v.person_role = "driver" if v.track_id in drivers else "pedestrian"
        return views, risk_views, exclude

    def summary(self) -> Dict:
        out: Dict = {"enabled": self.enabled_features}
        if self.merger:
            out["id_merge"] = {"merges": len(self.merger.merges),
                               "raw_ids": len(self.merger.raw_to_can),
                               "canonical_ids": len(set(self.merger.raw_to_can.values()))}
        if self.static:
            st = self.static.status
            out["static_filter"] = {s: sum(v == s for v in st.values())
                                    for s in ("dynamic", "protected_large", "ignored_zone", "static", "pending")}
        if self.role:
            final = {}
            for r in self.role.log:
                final[(r["person_id"], r["vehicle_id"])] = r["role"]
            out["role"] = {"pairs_evaluated": len(final), "driver_pairs": sum(v == "driver" for v in final.values()),
                           "driver_pairs_ever": len({(r["person_id"], r["vehicle_id"]) for r in self.role.log
                                                     if r["role"] == "driver"})}
        return out
