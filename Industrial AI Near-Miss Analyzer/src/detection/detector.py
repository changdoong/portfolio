"""YOLO 기반 객체 검출기 (ultralytics).

- detect(): model.predict()  → 검출만 (자체 IoUTracker 와 함께 사용)
- track():  model.track()    → 검출 + ultralytics 내장 ByteTrack (ID 부여)

한 프레임에는 둘 중 하나만 호출한다 (ByteTrack 중복 실행 방지는 pipeline 에서 보장).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Detection:
    bbox: np.ndarray          # [x1, y1, x2, y2]
    score: float
    class_id: int
    category: str             # "person" / "vehicle" ...
    track_id: Optional[int] = None   # ByteTrack 이 부여한 ID (detect() 결과는 None)

    @property
    def foot_point(self) -> np.ndarray:
        """바운딩 박스 하단 중앙 = 지면 접점 (거리 계산 기준)."""
        x1, y1, x2, y2 = self.bbox
        return np.array([(x1 + x2) / 2.0, y2], dtype=float)


def resolve_device(device: str, half: bool, cuda_available: Optional[bool] = None) -> Tuple[str, bool]:
    """요청한 device/half 를 실제 환경에 맞게 확정.

    - CUDA 요청 + CUDA 사용 불가 → ("cpu", False) 로 폴백 (경고 로그)
    - CPU 에서는 항상 FP32 (half=False)
    """
    if cuda_available is None:
        try:
            import torch

            cuda_available = torch.cuda.is_available()
        except ImportError:
            cuda_available = False

    dev = str(device).strip().lower()
    wants_cuda = dev.startswith("cuda") or dev.isdigit()
    if not wants_cuda:
        if half:
            logger.info("CPU 환경이므로 half=True 를 무시하고 FP32 로 실행합니다.")
        return "cpu", False
    if not cuda_available:
        logger.warning("device=%s 요청했지만 CUDA 를 사용할 수 없어 CPU(FP32)로 전환합니다.", device)
        return "cpu", False
    return str(device), bool(half)


class YOLODetector:
    def __init__(
        self,
        model: str = "yolov8n.pt",
        class_map: Optional[Dict[str, List[int]]] = None,
        conf: float = 0.35,
        iou: float = 0.5,
        device: str = "cpu",
        imgsz: int = 640,
        half: bool = False,
        tracker_cfg: str = "bytetrack.yaml",
    ):
        from ultralytics import YOLO  # 무거운 의존성은 지연 import

        self.model_path = model
        self.model = YOLO(model)
        self.conf = conf
        self.iou = iou
        self.imgsz = imgsz
        self.device, self.half = resolve_device(device, half)
        self.tracker_cfg = tracker_cfg

        class_map = class_map or {"person": [0], "vehicle": [2, 3, 5, 7]}
        self.id_to_category = {cid: cat for cat, ids in class_map.items() for cid in ids}
        self.target_classes = sorted(self.id_to_category)

        # 마지막 호출의 ultralytics 측정 시간(ms): preprocess / inference / postprocess
        self.last_speed: Dict[str, Optional[float]] = {}
        # 마지막 track() 에서 검출은 있었지만 ByteTrack 이 아직 ID 를 확정하지 않은 개수
        self.last_untracked = 0
        logger.info("YOLODetector: model=%s device=%s half=%s", model, self.device, self.half)

    # ------------------------------------------------------------------
    def _kwargs(self) -> Dict:
        # ultralytics 8.4+: 'half' 인자는 deprecated → 'quantize' (16=FP16, None=FP32) 로 전달
        return dict(conf=self.conf, iou=self.iou, device=self.device, quantize=16 if self.half else None,
                    imgsz=self.imgsz, classes=self.target_classes, verbose=False)

    def torch_module(self):
        """실제 추론에 사용되는 torch nn.Module (GPU/정밀도 검증용). 첫 추론 이후에 유효."""
        backend = getattr(getattr(self.model, "predictor", None), "model", None)
        inner = getattr(backend, "backend", None)          # ultralytics 8.4: AutoBackend.backend.model
        return getattr(inner, "model", None) or getattr(backend, "model", None)

    def detect(self, frame: np.ndarray) -> List[Detection]:
        """검출만 수행 (track_id=None)."""
        result = self.model.predict(frame, **self._kwargs())[0]
        self.last_speed = dict(result.speed)
        self.last_untracked = 0
        return self._to_detections(result.boxes, ids=None)

    def track(self, frame: np.ndarray) -> List[Detection]:
        """검출 + ultralytics 내장 ByteTrack. 반환되는 모든 Detection 은 track_id 를 가진다.

        ultralytics 는 ByteTrack 이 확정한 트랙이 하나도 없으면 원본 검출을 ID 없이(boxes.id=None)
        반환한다 (예: 점수가 new_track_thresh 미만, 신규 트랙 확정 대기). 이는 정상 상태이므로
        빈 목록을 반환하고 개수만 last_untracked 에 기록한다.
        """
        result = self.model.track(frame, persist=True, tracker=self.tracker_cfg, **self._kwargs())[0]
        self.last_speed = dict(result.speed)
        boxes = result.boxes
        self.last_untracked = 0
        if boxes is None or len(boxes) == 0:
            return []
        if boxes.id is None:
            self.last_untracked = len(boxes)
            return []
        ids = boxes.id.cpu().numpy().astype(int)
        if len(ids) != len(boxes):
            raise RuntimeError(f"ByteTrack 결과 불일치: boxes={len(boxes)}, ids={len(ids)}")
        return self._to_detections(boxes, ids=ids)

    def reset_tracking(self) -> None:
        """새 영상을 시작할 때 ByteTrack 내부 상태 초기화."""
        predictor = getattr(self.model, "predictor", None)
        for t in getattr(predictor, "trackers", None) or []:
            t.reset()

    # ------------------------------------------------------------------
    def _to_detections(self, boxes, ids: Optional[np.ndarray]) -> List[Detection]:
        if boxes is None or len(boxes) == 0:
            return []
        xyxy = boxes.xyxy.cpu().numpy()
        scores = boxes.conf.cpu().numpy()
        cls = boxes.cls.cpu().numpy().astype(int)
        dets = []
        for k, (b, s, c) in enumerate(zip(xyxy, scores, cls)):
            cat = self.id_to_category.get(int(c))
            if cat is None:
                continue
            dets.append(Detection(bbox=b.astype(float), score=float(s), class_id=int(c), category=cat,
                                  track_id=None if ids is None else int(ids[k])))
        return dets
