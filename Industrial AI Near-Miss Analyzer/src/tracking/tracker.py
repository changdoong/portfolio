"""IoU 기반 다중 객체 추적기 (SORT 계열 경량 구현).

- 같은 카테고리끼리만 매칭 (사람 ↔ 차량 ID 스위칭 방지)
- IoU 행렬에서 탐욕적(greedy) 매칭: 높은 IoU 쌍부터 확정
- 트랙마다 지면 접점(foot point) 궤적을 저장하고, 최근 궤적의
  선형 회귀로 속도(px/frame)를 추정 → 근접위험(TTC) 계산에 사용
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, List, Optional

import numpy as np

from src.detection.detector import Detection


def iou_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """a: (N,4), b: (M,4) xyxy → (N,M) IoU."""
    if len(a) == 0 or len(b) == 0:
        return np.zeros((len(a), len(b)))
    a = a[:, None, :]
    b = b[None, :, :]
    ix1 = np.maximum(a[..., 0], b[..., 0])
    iy1 = np.maximum(a[..., 1], b[..., 1])
    ix2 = np.minimum(a[..., 2], b[..., 2])
    iy2 = np.minimum(a[..., 3], b[..., 3])
    inter = np.clip(ix2 - ix1, 0, None) * np.clip(iy2 - iy1, 0, None)
    area_a = (a[..., 2] - a[..., 0]) * (a[..., 3] - a[..., 1])
    area_b = (b[..., 2] - b[..., 0]) * (b[..., 3] - b[..., 1])
    return inter / np.maximum(area_a + area_b - inter, 1e-9)


@dataclass
class Track:
    track_id: int
    bbox: np.ndarray
    category: str
    score: float
    history_len: int = 30
    hits: int = 1
    age: int = 0                       # 마지막 매칭 이후 경과 프레임
    history: Deque[np.ndarray] = field(default_factory=deque)

    def __post_init__(self):
        self.history = deque(maxlen=self.history_len)
        self.history.append(self.foot_point)

    @property
    def foot_point(self) -> np.ndarray:
        x1, y1, x2, y2 = self.bbox
        return np.array([(x1 + x2) / 2.0, y2], dtype=float)

    @property
    def velocity(self) -> np.ndarray:
        """최근 궤적의 최소제곱 기울기 (px/frame). 노이즈에 강함."""
        n = min(len(self.history), 10)
        if n < 2:
            return np.zeros(2)
        pts = np.array(list(self.history)[-n:])
        t = np.arange(n, dtype=float)
        t -= t.mean()
        return (t[:, None] * (pts - pts.mean(axis=0))).sum(axis=0) / (t ** 2).sum()

    def update(self, det: Detection) -> None:
        self.bbox = det.bbox.astype(float)
        self.score = det.score
        self.hits += 1
        self.age = 0
        self.history.append(self.foot_point)

    def mark_missed(self) -> None:
        self.age += 1


class IoUTracker:
    def __init__(self, iou_threshold: float = 0.3, max_age: int = 30, min_hits: int = 3, history_len: int = 30):
        self.iou_threshold = iou_threshold
        self.max_age = max_age
        self.min_hits = min_hits
        self.history_len = history_len
        self.tracks: List[Track] = []
        self._next_id = 1

    def update(self, detections: List[Detection]) -> List[Track]:
        unmatched_dets = set(range(len(detections)))
        unmatched_trks = set(range(len(self.tracks)))

        if self.tracks and detections:
            ious = iou_matrix(
                np.array([t.bbox for t in self.tracks]),
                np.array([d.bbox for d in detections]),
            )
            # 다른 카테고리끼리는 매칭 금지
            for i, t in enumerate(self.tracks):
                for j, d in enumerate(detections):
                    if t.category != d.category:
                        ious[i, j] = 0.0

            for flat in np.argsort(-ious, axis=None):
                i, j = np.unravel_index(flat, ious.shape)
                if ious[i, j] < self.iou_threshold:
                    break
                if i in unmatched_trks and j in unmatched_dets:
                    self.tracks[i].update(detections[j])
                    unmatched_trks.discard(i)
                    unmatched_dets.discard(j)

        for i in unmatched_trks:
            self.tracks[i].mark_missed()

        for j in sorted(unmatched_dets):
            d = detections[j]
            self.tracks.append(
                Track(self._next_id, d.bbox.astype(float), d.category, d.score, history_len=self.history_len)
            )
            self._next_id += 1

        self.tracks = [t for t in self.tracks if t.age <= self.max_age]
        return self.active_tracks()

    def active_tracks(self) -> List[Track]:
        """현재 프레임에서 보이고, 충분히 확정된 트랙만 반환."""
        return [t for t in self.tracks if t.age == 0 and t.hits >= self.min_hits]

    def get(self, track_id: int) -> Optional[Track]:
        return next((t for t in self.tracks if t.track_id == track_id), None)


# ======================================================================
# ByteTrack 어댑터
# ======================================================================
class ByteTrackAdapter:
    """ultralytics 내장 ByteTrack 이 부여한 track_id 를 Track 객체로 변환·관리한다.

    **추적(연관) 계산은 하지 않는다.** ByteTrack 은 YOLODetector.track() 안에서
    한 번만 실행되고, 이 클래스는 그 결과의 궤적(history)·속도·마지막 관측 시점만 관리한다.

    - 빈 목록(검출 없음 / 추적 확정 전) → 정상. 모든 트랙을 미관측 처리 후 [] 반환
    - track_id 가 없는 Detection 이 들어오면 → ValueError (detect() 결과를 잘못 넘긴 경우)
    """

    def __init__(self, max_age: int = 30, history_len: int = 30, min_hits: int = 1):
        self.max_age = max_age
        self.history_len = history_len
        self.min_hits = min_hits
        self._tracks: dict = {}

    @property
    def tracks(self) -> List[Track]:
        return list(self._tracks.values())

    def update(self, detections: List[Detection]) -> List[Track]:
        missing = [d for d in detections if d.track_id is None]
        if missing:
            raise ValueError(
                f"ByteTrackAdapter: track_id 가 없는 검출 {len(missing)}/{len(detections)}개. "
                "detect() 가 아닌 track() 결과를 전달해야 합니다."
            )
        ids = [d.track_id for d in detections]
        if len(ids) != len(set(ids)):
            raise ValueError(f"ByteTrackAdapter: 한 프레임에 중복 track_id {ids}")

        for d in detections:
            t = self._tracks.get(d.track_id)
            if t is None:
                self._tracks[d.track_id] = Track(
                    d.track_id, d.bbox.astype(float), d.category, d.score, history_len=self.history_len
                )
            else:
                t.update(d)
                t.category = d.category  # ByteTrack 은 클래스 변경을 허용하므로 최신 값 반영

        seen = set(ids)
        for tid, t in self._tracks.items():
            if tid not in seen:
                t.mark_missed()
        self._tracks = {tid: t for tid, t in self._tracks.items() if t.age <= self.max_age}
        return self.active_tracks()

    def active_tracks(self) -> List[Track]:
        return [t for t in self._tracks.values() if t.age == 0 and t.hits >= self.min_hits]

    def get(self, track_id: int) -> Optional[Track]:
        return self._tracks.get(track_id)


def build_tracker(tracking_cfg: dict):
    """설정으로 추적기를 만든다. 반환: (tracker_type, tracker)

    - 구 형식 (type 키 없음, IoUTracker 인자가 평평하게 나열) → ("iou", IoUTracker(**cfg))
    - type: bytetrack → ByteTrackAdapter  (detector.track() 과 짝)
    - type: iou       → IoUTracker        (detector.detect() 와 짝)
    """
    cfg = dict(tracking_cfg or {})
    if "type" not in cfg:
        return "iou", IoUTracker(**cfg)

    ttype = cfg["type"].lower()
    history_len = cfg.get("history_len", 30)
    max_age = cfg.get("max_age", 30)
    if ttype == "bytetrack":
        return "bytetrack", ByteTrackAdapter(max_age=max_age, history_len=history_len)
    if ttype == "iou":
        return "iou", IoUTracker(max_age=max_age, history_len=history_len, **cfg.get("iou", {}))
    raise ValueError(f"지원하지 않는 tracking.type: {cfg['type']} (bytetrack | iou)")
