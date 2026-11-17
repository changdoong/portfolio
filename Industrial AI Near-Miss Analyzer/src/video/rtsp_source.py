"""RTSP 스트림 소스.

실시간 CCTV 는 추론 속도보다 프레임이 빨리 들어오기 때문에, 버퍼에 쌓인
오래된 프레임을 처리하면 지연(latency)이 계속 늘어난다. 이를 막기 위해
별도 스레드에서 계속 grab 하고 **가장 최신 프레임 1장만** 유지한다.
연결이 끊기면 자동으로 재연결을 시도한다.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional

import cv2
import numpy as np

from .video_source import VideoSource

logger = logging.getLogger(__name__)


class RTSPSource(VideoSource):
    def __init__(
        self,
        url: str,
        resize_width: Optional[int] = None,
        reconnect_delay_sec: float = 2.0,
        max_reconnect: int = 10,
    ):
        super().__init__(url, resize_width)
        self.reconnect_delay_sec = reconnect_delay_sec
        self.max_reconnect = max_reconnect

        self._frame: Optional[np.ndarray] = None
        self._frame_id = 0
        self._last_read_id = 0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    def open(self) -> "RTSPSource":
        self._connect()
        self._stop.clear()
        self._thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._thread.start()
        return self

    def _connect(self) -> None:
        self.cap = cv2.VideoCapture(self.source, cv2.CAP_FFMPEG)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not self.cap.isOpened():
            raise IOError(f"RTSP 연결 실패: {self.source}")
        logger.info("RTSP connected: %s", self.source)

    def _reader_loop(self) -> None:
        retries = 0
        while not self._stop.is_set():
            ok, frame = self.cap.read() if self.cap is not None else (False, None)
            if ok:
                retries = 0
                with self._lock:
                    self._frame = frame
                    self._frame_id += 1
                continue

            retries += 1
            if retries > self.max_reconnect:
                logger.error("RTSP 재연결 한도 초과, 중단합니다.")
                self._stop.set()
                break
            logger.warning("RTSP 프레임 수신 실패 → 재연결 시도 %d/%d", retries, self.max_reconnect)
            if self.cap is not None:
                self.cap.release()
            time.sleep(self.reconnect_delay_sec)
            try:
                self._connect()
            except IOError:
                continue

    # ------------------------------------------------------------------
    def read(self, timeout: float = 5.0) -> Optional[np.ndarray]:
        """새 프레임이 들어올 때까지 대기 후 최신 프레임 반환."""
        if self._thread is None:
            self.open()
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._stop.is_set():
                return None
            with self._lock:
                if self._frame is not None and self._frame_id != self._last_read_id:
                    self._last_read_id = self._frame_id
                    return self._resize(self._frame.copy())
            time.sleep(0.002)
        return None

    def release(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        super().release()
