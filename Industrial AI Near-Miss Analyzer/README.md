# Industrial AI Near-Miss Analyzer

**산업용 CCTV 기반 실시간 객체 추적 및 위험상황 분석 시스템**

산업 현장 CCTV 영상에서 작업자와 차량을 검출·추적하고,
**위험구역 침입**과 **사람-차량 근접(Near-Miss)** 을 감지해 에피소드 단위로 기록합니다.
사고 이전의 "아차사고" 단계를 데이터로 남기는 것이 목표입니다.

> 🚧 개발 진행 중 (MVP 5일 계획 중 1일차 완료 · 테스트 49 passed). 아래 표의 **검증 상태**는 실제로 실행·확인한 범위만 표시합니다.

---

## 구현 / 검증 상태

| 기능 | 구현 | 검증 |
|---|---|---|
| YOLOv8n(COCO) 객체 검출 – GPU FP16/FP32 | ✅ | ✅ RTX 3060 Ti 실추론 (예제 이미지) |
| ByteTrack 추적 (ultralytics 내장, 1회 실행) | ✅ | ✅ 실추론 ID 유지 확인 (정지 이미지) / 단위·E2E 테스트 |
| 자체 IoU Tracker (비교 실험용) | ✅ | 단위·합성 E2E 테스트만 |
| 위험구역 침입 (에피소드: 유지시간·쿨다운) | ✅ | 단위·합성 E2E 테스트만 |
| 픽셀 기반 근접도 (bbox 하단 중앙, warning/danger) | ✅ | 단위·합성 E2E 테스트만 |
| Inference FPS / Pipeline FPS 분리 측정 | ✅ | Inference: 실측 / Pipeline: 실제 MP4 미측정 |
| MP4 영상 입력·결과 저장 | ✅ | 합성 MP4 만 (실제 CCTV 영상 미검증) |
| RTSP 스트림 입력 | 코드 작성 | ❌ **미검증** |
| 실제 거리(m) / TTC | 실험 코드(픽셀 TTC, 기본 off) | ❌ 호모그래피 적용 후 진행 예정 |
| 지게차 전용 탐지 (파인튜닝) | ❌ | ❌ 후속 단계 |
| ONNX Runtime / TensorRT | ❌ | ❌ 후속 단계 |

## 시스템 구조

```
MP4 ─▶ YOLODetector.track()  ──▶ ByteTrackAdapter ─┬▶ ZoneMonitor ─────┐
       (YOLOv8 + ByteTrack 1회)   (ID→궤적 관리)    └▶ NearMissDetector ┴▶ events.csv / result.mp4 / perf.json
```

- 추적기는 설정으로 선택: `tracking.type: bytetrack`(기본) / `iou`(비교 실험). 프레임당 검출기 호출은 정확히 1회입니다.
- 자세한 설계: [docs/architecture.md](docs/architecture.md)

## 근접위험 판정 (MVP: 픽셀 기반)

- 기준점: 바운딩 박스 **하단 중앙** (지면 접점)
- `거리 ≤ danger_px` → **danger**, `거리 ≤ warning_px` → **warning** (값은 `configs/config.yaml`)
- **에피소드 기록**: 같은 쌍의 연속 위험은 `start` 1건 + 등급 상승 시 `escalate` 1건 + 종료 시 `end` 1건(지속시간·최소거리)
  - `release_frames`: 이 시간 동안 연속으로 안전해야 종료 (검출 깜빡임 무시)
  - `cooldown_frames`: 종료 후 같은 쌍 재기록 억제
- ⚠️ 픽셀 거리는 원근 때문에 실제 거리와 비례하지 않습니다. 현재 결과는 "근접도 지표"이며, 미터 단위 거리와 TTC 는 카메라 보정·호모그래피 적용 후 제공할 예정입니다.

## 설치

검증 환경: Windows 11 · Python 3.11.9 · RTX 3060 Ti (8GB) · NVIDIA driver 610.88

```powershell
# 0) 프로젝트 전용 가상환경 (시스템 Python 과 분리)
py -3.11 -m venv .venv

# 1) PyTorch CUDA 빌드를 **먼저** 설치
.\.venv\Scripts\python.exe -m pip install -r requirements-torch-cu128.txt

# 2) 일반 라이브러리 (torch 미포함)
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 3) CUDA 빌드 유지 확인 (CPU 판이면 종료코드 1)
.\.venv\Scripts\python.exe scripts\check_env.py
```

> ultralytics 는 torch 에 의존하므로 1)을 건너뛰고 2)를 먼저 설치하면 CPU 버전 torch 가 설치될 수 있습니다.
> `pip install -U -r requirements.txt` (일괄 업그레이드)는 사용하지 마세요.

### 모델 가중치 (Git 에 포함하지 않음)

| 파일 | 출처 | 받는 방법 |
|---|---|---|
| `models/yolov8n.pt` (6,549,796 bytes) | Ultralytics 공식 릴리스 <https://github.com/ultralytics/assets/releases/download/v8.4.0/yolov8n.pt> | 아래 명령 |

```powershell
.\.venv\Scripts\python.exe -c "from ultralytics.utils.downloads import attempt_download_asset; attempt_download_asset('models/yolov8n.pt')"
```

- SHA256 (2026-11-17 다운로드본): `f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36`
- COCO 80 클래스 사전학습 모델입니다. **COCO 에는 지게차(forklift) 클래스가 없어** `truck`/`car` 로 검출되거나 누락될 수 있습니다.
- 라이선스: Ultralytics YOLOv8 코드·가중치는 **AGPL-3.0** 입니다.
- `*.pt` 는 `.gitignore` 로 커밋에서 제외됩니다.

## 실행

```powershell
.\.venv\Scripts\python.exe scripts\run_video.py --source data\sample.mp4
.\.venv\Scripts\python.exe scripts\run_video.py --source data\sample.mp4 --tracker iou      # 비교 실험
.\.venv\Scripts\python.exe scripts\run_video.py --source data\sample.mp4 --no-half --no-show
```

출력: `outputs/result.mp4`, `outputs/events.csv`, `outputs/perf.json`

## 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest tests -v

# GPU 통합 테스트를 skip 없이 강제 실행 (가중치/CUDA 없으면 실패)
$env:REQUIRE_GPU="1"; .\.venv\Scripts\python.exe -m pytest tests\test_yolo_gpu.py -v
```

### 테스트 결과 (실행 기록)

실행 환경: Windows 11 · Python 3.11.9 가상환경 · RTX 3060 Ti · `REQUIRE_GPU=1` (GPU 테스트를 skip 이 아닌 실패로 처리)

| 테스트 파일 | 대상 | 개수 | 결과 |
|---|---|---|---|
| `test_risk.py` | TTC 계산, IoU 추적, 위험구역, P/R 지표 (기존) | 11 | ✅ |
| `test_pipeline.py` | 합성 영상 E2E, 구 설정 형식 (기존) | 1 | ✅ |
| `test_tracking_bytetrack.py` | ByteTrackAdapter, 빈 프레임, track_id 누락, build_tracker | 7 | ✅ |
| `test_near_miss_pixel.py` | 하단 중앙 기준 거리, warning/danger 경계, 에피소드·유지시간·쿨다운 | 15 | ✅ |
| `test_device_and_perf.py` | CUDA 없을 때 FP32 전환, 지연시간 통계 | 8 | ✅ |
| `test_pipeline_bytetrack.py` | ByteTrack 경로 E2E, 프레임당 1회 호출, perf.json | 3 | ✅ |
| `test_yolo_gpu.py` | 실제 YOLOv8n + CUDA FP16 + ByteTrack | 4 | ✅ (skip 0) |
| **합계** | | **49** | **49 passed** |

- 기존 테스트 12개(`test_risk.py`, `test_pipeline.py`)는 검증 조건을 바꾸지 않은 상태로 통과했습니다.
- 실제 CCTV 영상, RTSP 스트림은 아직 테스트 범위에 포함되지 않았습니다.

## 성능 측정 (실측)

**측정 지표 정의**
- **Inference FPS**: 모델 forward 시간만 (ultralytics `result.speed["inference"]`)
- **Pipeline FPS**: 프레임 읽기 → 검출·추적 → 위험 분석 → 시각화 → 저장/출력 전체

**1일차: GPU 스모크 테스트** (`scripts/gpu_smoke_test.py`)
조건: RTX 3060 Ti · YOLOv8n · imgsz 640 · 배치 1 · 예제 이미지 `bus.jpg`(810×1080) 반복 · 워밍업 20회 제외 후 200회 · 단일 실행

| 정밀도 | 모드 | Inference 평균 (p95) | 호출 전체 평균 (p95) |
|---|---|---|---|
| FP16 | detect | 5.92 ms (7.77) → 169 FPS | 8.64 ms (10.70) → 116 FPS |
| FP16 | track (ByteTrack 포함) | 6.10 ms (7.96) → 164 FPS | 9.80 ms (11.91) → 102 FPS |
| FP32 | detect | 5.29 ms (6.61) → 189 FPS | 8.00 ms (9.66) → 125 FPS |
| FP32 | track (ByteTrack 포함) | 5.76 ms (7.57) → 174 FPS | 9.43 ms (11.69) → 106 FPS |

- 이 조건(yolov8n·배치 1)에서는 **FP16 이 FP32 보다 빠르지 않았습니다.** 모델이 작아 연산보다 커널 실행 오버헤드 비중이 큰 것으로 추정되며, 더 큰 모델(v8s/m)·실제 영상에서 재측정할 예정입니다.
- 정지 이미지 반복 측정이므로 **실제 영상의 Pipeline FPS 가 아닙니다.** Pipeline FPS 는 실제 MP4 확보 후 측정합니다.

## 한계 및 향후 계획

- [ ] 실제 CCTV MP4 로 Pipeline FPS 측정, 위험구역·임계값 보정 (2일차)
- [ ] 위험 시점 수동 라벨링 → 이벤트 Precision / Recall / F1
- [ ] 지게차 포함 공개 데이터셋 확보(라이선스 확인) → YOLOv8 파인튜닝 → COCO 모델과 동일 테스트셋으로 mAP·P·R 비교
- [ ] ONNX Runtime 검증 → TensorRT (호환성 확인 후)
- [ ] RTSP 실제 스트림 연결 검증
- [ ] 호모그래피 기반 미터 거리 · TTC
- [ ] ByteTrack ↔ 자체 IoU Tracker 비교 실험
- 알려진 한계: ByteTrack 이 ID 를 잃고 새 ID 를 부여하면 같은 상황이 새 에피소드로 기록될 수 있음

## Tech Stack

Python 3.11 · PyTorch 2.11 (CUDA 12.8) · Ultralytics YOLOv8 (8.4.215) · ByteTrack · OpenCV 5.0 · NumPy · pytest
