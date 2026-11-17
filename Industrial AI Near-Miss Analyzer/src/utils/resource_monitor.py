"""CPU / GPU 사용률 백그라운드 샘플러.

    with ResourceMonitor(interval=0.5) as mon:
        ... 측정 대상 작업 ...
    print(mon.summary())

- CPU : psutil.cpu_percent (시스템 전체, %) + 현재 프로세스 CPU (%; 코어 수로 나눈 값)
- GPU : NVML(nvidia-ml-py) 장치 사용률(%) / 장치 메모리 사용량(MiB)
        ※ 장치 단위 값이므로 다른 프로세스(데스크톱 등)의 사용분이 포함된다.
          baseline() 으로 측정 전 유휴 상태를 함께 기록해 비교한다.
- psutil / pynvml 이 없거나 GPU 를 읽을 수 없으면 해당 항목은 "N/A" 로 기록한다.
"""
from __future__ import annotations

import threading
import time
from typing import Dict, List, Optional


def _stats(values: List[float]) -> Dict:
    if not values:
        return {"count": 0}
    return {"count": len(values), "mean": round(sum(values) / len(values), 2), "max": round(max(values), 2)}


class ResourceMonitor:
    def __init__(self, interval: float = 0.5, gpu_index: Optional[int] = 0):
        self.interval = interval
        self.gpu_index = gpu_index
        self.samples: Dict[str, List[float]] = {"cpu_system_pct": [], "cpu_process_pct": [],
                                                 "gpu_util_pct": [], "gpu_mem_used_mib": []}
        self.notes: List[str] = []
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._psutil = self._proc = self._nvml = self._handle = None
        self._ncpu = 1
        self.gpu_name: Optional[str] = None
        self.gpu_mem_total_mib: Optional[float] = None
        self._init_backends()

    # ------------------------------------------------------------------
    def _init_backends(self) -> None:
        try:
            import psutil

            self._psutil = psutil
            self._proc = psutil.Process()
            self._ncpu = psutil.cpu_count() or 1
            psutil.cpu_percent(interval=None)       # 첫 호출은 기준점 설정용
            self._proc.cpu_percent(interval=None)
        except Exception as e:  # noqa: BLE001
            self.notes.append(f"CPU 측정 불가: {e}")
        if self.gpu_index is None:
            self.notes.append("GPU 측정 비활성화 (gpu_index=None)")
            return
        try:
            import pynvml

            pynvml.nvmlInit()
            self._nvml = pynvml
            self._handle = pynvml.nvmlDeviceGetHandleByIndex(self.gpu_index)
            name = pynvml.nvmlDeviceGetName(self._handle)
            self.gpu_name = name.decode() if isinstance(name, bytes) else name
            self.gpu_mem_total_mib = round(pynvml.nvmlDeviceGetMemoryInfo(self._handle).total / 2**20, 1)
        except Exception as e:  # noqa: BLE001
            self._nvml = self._handle = None
            self.notes.append(f"GPU 측정 불가: {e}")

    def sample_once(self) -> Dict[str, Optional[float]]:
        s: Dict[str, Optional[float]] = {}
        if self._psutil is not None:
            s["cpu_system_pct"] = self._psutil.cpu_percent(interval=None)
            s["cpu_process_pct"] = self._proc.cpu_percent(interval=None) / self._ncpu
        if self._handle is not None:
            s["gpu_util_pct"] = float(self._nvml.nvmlDeviceGetUtilizationRates(self._handle).gpu)
            s["gpu_mem_used_mib"] = self._nvml.nvmlDeviceGetMemoryInfo(self._handle).used / 2**20
        return s

    def baseline(self, duration: float = 1.0) -> Dict:
        """측정 전 유휴 상태를 duration 초 동안 샘플링한 평균/최대."""
        vals: Dict[str, List[float]] = {k: [] for k in self.samples}
        end = time.time() + duration
        while time.time() < end:
            time.sleep(self.interval)
            for k, v in self.sample_once().items():
                vals[k].append(v)
        return {k: _stats(v) if v else "N/A" for k, v in vals.items()}

    # ------------------------------------------------------------------
    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            for k, v in self.sample_once().items():
                self.samples[k].append(v)

    def start(self) -> "ResourceMonitor":
        self.sample_once()  # 기준점 갱신
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2 * self.interval + 1)
            self._thread = None

    def summary(self) -> Dict:
        out = {k: _stats(v) if v else "N/A" for k, v in self.samples.items()}
        out.update({"interval_sec": self.interval, "cpu_count": self._ncpu, "gpu_name": self.gpu_name,
                    "gpu_mem_total_mib": self.gpu_mem_total_mib, "notes": self.notes,
                    "scope": "GPU 값은 장치 전체 기준(다른 프로세스 포함)"})
        return out

    def close(self) -> None:
        if self._nvml is not None:
            try:
                self._nvml.nvmlShutdown()
            except Exception:  # noqa: BLE001
                pass
            self._nvml = self._handle = None

    def __enter__(self) -> "ResourceMonitor":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()
