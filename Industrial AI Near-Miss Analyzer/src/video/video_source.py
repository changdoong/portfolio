"""영상 입력 소스 (파일 / 웹캠)."""
from __future__ import annotations

from typing import Iterator, Optional, Union

import cv2
import numpy as np


class VideoSource:
    """OpenCV 기반 동기식 영상 소스.

    파일 경로 또는 웹캠 인덱스를 받는다. RTSP 는 :class:`RTSPSource` 사용.
    """

    def __init__(self, source: Union[str, int], resize_width: Optional[int] = None):
        if isinstance(source, str) and source.isdigit():
            source = int(source)
        self.source = source
        self.resize_width = resize_width
        self.cap: Optional[cv2.VideoCapture] = None

    # ------------------------------------------------------------------
    def open(self) -> "VideoSource":
        self.cap = cv2.VideoCapture(self.source)
        if not self.cap.isOpened():
            raise IOError(f"영상 소스를 열 수 없습니다: {self.source}")
        return self

    def read(self) -> Optional[np.ndarray]:
        if self.cap is None:
            self.open()
        ok, frame = self.cap.read()
        if not ok:
            return None
        return self._resize(frame)

    def release(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    # ------------------------------------------------------------------
    @property
    def fps(self) -> float:
        if self.cap is None:
            return 30.0
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        return fps if fps and fps > 1 else 30.0

    def _resize(self, frame: np.ndarray) -> np.ndarray:
        if not self.resize_width or frame.shape[1] == self.resize_width:
            return frame
        h, w = frame.shape[:2]
        scale = self.resize_width / w
        return cv2.resize(frame, (self.resize_width, int(h * scale)))

    def __iter__(self) -> Iterator[np.ndarray]:
        while True:
            frame = self.read()
            if frame is None:
                break
            yield frame

    def __enter__(self) -> "VideoSource":
        return self.open()

    def __exit__(self, *exc) -> None:
        self.release()


def create_source(source: Union[str, int], resize_width: Optional[int] = None, **rtsp_kwargs) -> VideoSource:
    """RTSP/HTTP 스트림이면 RTSPSource, 아니면 VideoSource. rtsp_kwargs 는 스트림에만 적용."""
    if isinstance(source, str) and source.lower().startswith(("rtsp://", "rtsps://", "http://", "https://")):
        from .rtsp_source import RTSPSource

        return RTSPSource(source, resize_width=resize_width, **rtsp_kwargs)
    return VideoSource(source, resize_width=resize_width)
