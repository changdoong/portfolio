"""공개용 캡처 비식별(얼굴/머리 영역) 처리.

원칙
  - 공개 이미지는 모든 비식별 영역이 검증을 통과했을 때만 생성한다 (실패 시 PrivacyError).
  - 대상 영역 = 사람 머리 영역 ∪ 고정 카메라 작업대 마스크 ∪ 큰 차량의 운전석 추정 영역
  - 사람 박스 = 추적 결과 ∪ 원본 프레임 저신뢰도(conf) 재검출 ∪ 차량 박스 확대 crop 재검출(운전자)

※ YOLO 사람 검출 기반이므로 완전하지 않다. 공개 전 사람이 직접 확인해야 한다.
"""
from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple

import cv2
import numpy as np

Box = Tuple[float, float, float, float]

# 고정 카메라(1280x720 기준) 우측 작업대에 앉은 작업자 머리 위치 (YOLO 미검출 대비)
STATIC_MASKS_1280: List[Box] = [(1020, 250, 1140, 340)]
LARGE_VEHICLE_MIN_H = 0.25      # 프레임 높이 대비 이 이상인 차량은 운전석 마스크 적용


class PrivacyError(RuntimeError):
    """비식별 처리를 보장할 수 없을 때 발생. 공개 이미지 생성을 중단해야 한다."""


def clip_box(b: Box, w: int, h: int) -> Tuple[int, int, int, int]:
    x1, y1, x2, y2 = b
    return max(0, int(x1)), max(0, int(y1)), min(w, int(np.ceil(x2))), min(h, int(np.ceil(y2)))


def head_region(b: Box) -> Box:
    """사람 박스의 위쪽 40% (+좌우 15%, 위 8% 여백)."""
    x1, y1, x2, y2 = b
    bw, bh = x2 - x1, y2 - y1
    return (x1 - 0.15 * bw, y1 - 0.08 * bh, x2 + 0.15 * bw, y1 + 0.40 * bh)


def cab_region(b: Box) -> Box:
    """지게차 등 차량 박스에서 운전석 추정 영역 (가운데 70% 폭, 위쪽 60%)."""
    x1, y1, x2, y2 = b
    bw, bh = x2 - x1, y2 - y1
    return (x1 + 0.15 * bw, y1, x2 - 0.15 * bw, y1 + 0.60 * bh)


def mosaic(img: np.ndarray, b: Box, block: int = 6) -> bool:
    h, w = img.shape[:2]
    x1, y1, x2, y2 = clip_box(b, w, h)
    if x2 - x1 < 2 or y2 - y1 < 2:
        return False
    roi = img[y1:y2, x1:x2]
    small = cv2.resize(roi, (max(1, (x2 - x1) // block), max(1, (y2 - y1) // block)), interpolation=cv2.INTER_LINEAR)
    img[y1:y2, x1:x2] = cv2.resize(small, (x2 - x1, y2 - y1), interpolation=cv2.INTER_NEAREST)
    return True


def privacy_regions(person_boxes: Iterable[Box], vehicle_boxes: Iterable[Box], frame_w: int, frame_h: int,
                    static_masks: Sequence[Box] = STATIC_MASKS_1280, cab_mask: bool = True) -> List[Tuple[str, Box]]:
    sx, sy = frame_w / 1280, frame_h / 720
    regions = [("person_head", head_region(b)) for b in person_boxes]
    regions += [("static_mask", (x1 * sx, y1 * sy, x2 * sx, y2 * sy)) for x1, y1, x2, y2 in static_masks]
    if cab_mask:
        regions += [("vehicle_cab", cab_region(b)) for b in vehicle_boxes
                    if (b[3] - b[1]) >= LARGE_VEHICLE_MIN_H * frame_h]
    return regions


def global_mosaic(img: np.ndarray, block: int = 6) -> np.ndarray:
    """이미지 전체를 하나의 고정 격자로 모자이크 (영역이 겹쳐도 결과가 결정적)."""
    h, w = img.shape[:2]
    small = cv2.resize(img, (max(1, w // block), max(1, h // block)), interpolation=cv2.INTER_AREA)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)


def region_mask(regions: Sequence[Tuple[str, Box]], w: int, h: int) -> np.ndarray:
    m = np.zeros((h, w), bool)
    for _, b in regions:
        x1, y1, x2, y2 = clip_box(b, w, h)
        if x2 > x1 and y2 > y1:
            m[y1:y2, x1:x2] = True
    return m


def verify_blurred(out: np.ndarray, mosaic_img: np.ndarray, regions: Sequence[Tuple[str, Box]]) -> None:
    """모든 영역의 모든 픽셀이 모자이크 이미지와 동일한지 확인. 실패 시 PrivacyError."""
    h, w = out.shape[:2]
    for kind, b in regions:
        x1, y1, x2, y2 = clip_box(b, w, h)
        if x2 <= x1 or y2 <= y1:
            continue                       # 화면 밖 영역
        if not np.array_equal(out[y1:y2, x1:x2], mosaic_img[y1:y2, x1:x2]):
            raise PrivacyError(f"{kind} 영역 {x1, y1, x2, y2} 모자이크 미적용")


def anonymize(img: np.ndarray, person_boxes: Iterable[Box], vehicle_boxes: Iterable[Box] = (),
              static_masks: Sequence[Box] = STATIC_MASKS_1280, cab_mask: bool = True,
              block: int = 6) -> Tuple[np.ndarray, List]:
    """비식별 이미지와 적용 영역 목록을 반환. 검증 실패 시 PrivacyError."""
    h, w = img.shape[:2]
    regions = privacy_regions(list(person_boxes), list(vehicle_boxes), w, h, static_masks, cab_mask)
    mos = global_mosaic(img, block)
    mask = region_mask(regions, w, h)
    out = img.copy()
    out[mask] = mos[mask]
    verify_blurred(out, mos, regions)
    return out, regions


def find_people(detector, frame: np.ndarray, vehicle_boxes: Iterable[Box], crop_scale: float = 2.0) -> List[Box]:
    """원본 프레임 재검출 + 차량 박스 확대 crop 재검출(운전자). detector 는 YOLODetector(person 포함)."""
    if detector is None:
        raise PrivacyError("사람 재검출기가 없어 비식별을 보장할 수 없습니다.")
    h, w = frame.shape[:2]
    people = [tuple(map(float, d.bbox)) for d in detector.detect(frame) if d.category == "person"]
    for b in vehicle_boxes:
        x1, y1, x2, y2 = clip_box(b, w, h)
        if x2 - x1 < 8 or y2 - y1 < 8:
            continue
        crop = cv2.resize(frame[y1:y2, x1:x2], None, fx=crop_scale, fy=crop_scale)
        for d in detector.detect(crop):
            if d.category == "person":
                cx1, cy1, cx2, cy2 = d.bbox / crop_scale
                people.append((x1 + cx1, y1 + cy1, x1 + cx2, y1 + cy2))
    return people


def ioa(inner: Box, outer: Box) -> float:
    """inner 박스 면적 중 outer 와 겹치는 비율 (운전자 오검출 판단용)."""
    ix1, iy1 = max(inner[0], outer[0]), max(inner[1], outer[1])
    ix2, iy2 = min(inner[2], outer[2]), min(inner[3], outer[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area = max(1e-9, (inner[2] - inner[0]) * (inner[3] - inner[1]))
    return inter / area
