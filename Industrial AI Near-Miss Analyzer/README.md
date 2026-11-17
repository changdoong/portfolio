# Industrial AI Near-Miss Analyzer

**산업용 CCTV 기반 실시간 객체 추적 및 위험상황 분석 시스템**

산업 현장 CCTV 영상에서 작업자와 차량을 검출·추적하고,
**위험구역 침입**과 **사람-차량 근접(Near-Miss)** 을 감지해 에피소드 단위로 기록합니다.
사고 이전의 "아차사고" 단계를 데이터로 남기는 것이 목표입니다.

> 🚧 개발 진행 중 (MVP 5일 계획 중 3일차 진행). 아래 표의 **검증 상태**는 실제로 실행·확인한 범위만 표시합니다.

---

## 구현 / 검증 상태

| 기능 | 구현 | 검증 |
|---|---|---|
| YOLOv8n(COCO) 객체 검출 – GPU FP16/FP32 | ✅ | ✅ RTX 3060 Ti 실추론 (예제 이미지) |
| ByteTrack 추적 (ultralytics 내장, 1회 실행) | ✅ | ✅ 실추론 ID 유지 확인 (정지 이미지) / 단위·E2E 테스트 |
| 자체 IoU Tracker (비교 실험용) | ✅ | 단위·합성 E2E 테스트만 |
| 위험구역 침입 (에피소드: 유지시간·쿨다운) | ✅ | 단위·합성 E2E 테스트만 |
| 픽셀 기반 근접도 (bbox 하단 중앙, warning/danger) | ✅ | 단위·합성 E2E 테스트만 |
| Inference FPS / Pipeline FPS 분리 측정 | ✅ | ✅ 실제 CCTV MP4 5개 × 4조건 실측 (조건별 1회) |
| MP4 영상 입력·결과 저장 | ✅ | ✅ 실제 CCTV MP4 (OpenCV 5.0 읽기·쓰기, 프레임 수 일치 확인) |
| CPU/GPU 리소스 모니터링 | ✅ | ✅ 실측 |
| 공개 캡처 자동 비식별 (모자이크 + 검증) | ✅ | ✅ 육안 확인 (자동 처리는 완전하지 않음) |
| 정지 물체 필터 (이동 이력 보호 + 무시 구역) – 기본 비활성 | ✅ | ✅ 실제 CCTV 11개: 고정 설비 원인 후보 4건 제거, 지게차 보호 확인 |
| 운전자/보행자 구분 (IoA + 운전석 위치 + 순변위 동시 이동) – 기본 비활성 | ✅ | ⚠️ 7_tr21 보행자 회귀 통과·7_te6 운전자 판정, 짧게 검출된 운전자 2건은 미판정 |
| ByteTrack ID 병합 (canonical_track_id, 원본 ID 보존) – 기본 비활성 | ✅ | ⚠️ 중복 에피소드 1건 제거, 일부 병합은 육안 미검증 |
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
| `test_track_log_and_monitor.py` | 트랙/프레임 로그, 구간 시간, 리소스 모니터, 일괄 실행, 다운로드 안전장치 | 9 | ✅ |
| `test_privacy_and_audit.py` | 비식별 처리·검증 실패 시 중단, 이벤트/트랙 감사 보조 함수, 덮어쓰기 거부 | 11 | ✅ |
| `test_day3_analysis.py` | ID 병합·정지 물체 필터·운전자 구분, 7_tr21 보행자 회귀, 기본 비활성 | 20 | ✅ |
| **합계** | | **89** | **89 passed** |

- 1일차 테스트 49개는 파일·검증 조건을 바꾸지 않은 상태로 통과했습니다.
- 실제 CCTV 영상은 성능 측정(`run_batch.py`)으로 검증했고, 자동 테스트는 합성 영상과 정지 이미지를 사용합니다. RTSP 스트림은 테스트 범위에 포함되지 않았습니다.

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
- 정지 이미지 반복 측정이므로 **실제 영상의 Pipeline FPS 가 아닙니다.**

### 2일차: 실제 CCTV MP4 (domain: real_cctv)

`scripts/run_batch.py --videos configs/day2_videos.yaml` · 결과 원본: `outputs/day2/summary.md` (Git 제외)

**측정 환경과 조건**

| 항목 | 값 |
|---|---|
| 하드웨어 / SW | RTX 3060 Ti 8GB (driver 610.88), 12 논리 CPU · Windows 11 · Python 3.11.9 · torch 2.11.0+cu128 · ultralytics 8.4.215 · OpenCV 5.0 |
| 데이터 | Mendeley *Safe and Unsafe Behaviours* (CC BY 4.0) 실제 공장 CCTV 5개: `7_tr21`, `3_tr6`, `3_tr2`, `3_tr19`, `7_te2` (각 151~300 프레임, 원본 1920×1080 · 약 25fps) |
| 처리 | 1280×720 리사이즈 → YOLOv8n(COCO, imgsz 640, conf 0.35) + ByteTrack → 픽셀 근접도(위험구역 비활성) → 시각화 |
| 조건 | 정밀도 FP16 / FP32 × 결과 영상 저장 OFF / ON = 4조건 × 5영상 = **20회, 조건별 1회 측정** |
| 워밍업 | 전체 실행 전 1회(첫 영상 30프레임, 결과 미사용) + 각 실행의 처음 10프레임은 통계 제외 |
| 기타 | 화면 출력 OFF. 파일 입력은 실시간 속도 제한 없이 처리 → Pipeline FPS 는 **최대 처리량** |

**FP16 vs FP32 · 저장 ON/OFF (5개 영상 평균)**

| 정밀도 | 결과 영상 저장 | Inference ms (FPS) | Pipeline ms (FPS) | 인코딩 구간 ms | GPU 사용률 평균 (최대) | GPU 메모리 (장치) | PyTorch 최대 할당 |
|---|---|---|---|---|---|---|---|
| FP16 | OFF | 7.06 (141.6) | 19.89 (50.4) | — | 35.3% (41) | 1,199 MiB | 25.1 MiB |
| FP32 | OFF | **6.55 (152.7)** | **19.36 (51.7)** | — | 36.9% (42) | 1,205 MiB | 36.1 MiB |
| FP16 | ON | 7.09 (141.1) | 25.00 (40.0) | 4.73 | 32.9% (39) | 1,199 MiB | 22.9 MiB |
| FP32 | ON | 6.58 (152.1) | 24.70 (40.5) | 4.78 | 35.0% (40) | 1,206 MiB | 37.8 MiB |
| (측정 전 유휴) | | | | | 20.8% | 1,200 MiB | |

**영상별 (저장 OFF)**

| 영상 | Inference ms FP16 / FP32 | Pipeline ms FP16 / FP32 | Pipeline FPS FP16 / FP32 |
|---|---|---|---|
| 7_tr21 | 6.89 / 6.52 | 20.09 / 19.93 | 49.8 / 50.2 |
| 3_tr6 | 7.11 / 6.48 | 20.38 / 18.93 | 49.1 / 52.8 |
| 3_tr2 | 6.99 / 6.59 | 19.80 / 18.52 | 50.5 / 54.0 |
| 3_tr19 | 7.20 / 6.66 | 20.78 / 20.28 | 48.1 / 49.3 |
| 7_te2 | 7.14 / 6.51 | 18.43 / 19.11 | 54.3 / 52.3 |

**해석**
- 원본 영상(약 25fps) 대비 저장 OFF 약 50 FPS, 저장 ON 약 40 FPS 로 **실시간보다 빠르게 처리**했습니다.
- YOLOv8n·배치 1 에서는 1일차와 같이 **FP32 가 Inference 약 0.5ms 빠르고**, FP16 은 PyTorch 메모리를 약 11~15 MiB 덜 사용했습니다. 조건별 1회 측정이므로 Pipeline 의 0.5ms 안팎 차이는 측정 편차 범위일 수 있습니다.
- 결과 영상 저장(mp4v 인코딩)은 프레임당 약 **+5 ms**(약 50→40 FPS)를 추가합니다.
- Pipeline 20ms 의 구성(저장 OFF): 프레임 읽기(1080p 디코드+리사이즈) 약 7.2ms · 검출기 호출 약 11.4ms(이 중 모델 forward 6.5~7.2ms) · 추적·위험분석 0.1ms · 그리기 1.0ms → **모델 추론보다 디코딩·전후처리 비중이 큼**.
- GPU 사용률·메모리는 **장치 전체 기준**(다른 프로세스 포함)이며, 유휴 상태 대비 사용률 증가분은 약 +12~16%p 입니다.

**검출·추적 관찰 (근접 후보 이벤트 감사, `scripts/audit_events.py`)**
- 5개 영상에서 픽셀 근접 후보 이벤트 6건 중 **5건은 지게차가 아닌 물체가 원인**이었습니다: 좌상단 정지 설비(파란 카트/적재함)의 COCO `car` 오검출 3건, 작업자가 직접 끄는 수동 핸드 파렛트 트럭 2건.
- 보행자와 실제 지게차가 화면상 근접한 후보는 1건(`7_tr21`)이며, 실제 거리·위험 여부는 확인하지 않았습니다. **모든 이벤트는 후보이며 Near-Miss 로 확정하지 않았습니다.**
- `3_tr6` 의 짧은 vehicle 트랙(10프레임 미만) 7개: 정지 물체 오검출 4 · 실제 지게차 중복 박스(단기 ID 분리) 2 · 적재물 오검출 1 (`scripts/audit_tracks.py`). ByteTrack 파라미터는 아직 변경하지 않았습니다.
- 위 결과는 COCO 모델의 한계(지게차 클래스 없음, 정지 물체 오검출)를 보여주며, 지게차 파인튜닝·정지 물체 필터링의 근거로 사용합니다.

> 공개 캡처는 `scripts/make_captures.py` 로 머리 영역·작업대·지게차 운전석을 모자이크 처리한 이미지만 사용합니다. 블러 검증에 실패하면 이미지를 생성하지 않습니다.
> ⚠️ 자동 검증은 **검출된 영역에 모자이크가 적용되었는지**만 확인합니다. 사람 검출 자체가 누락되면 그 사람은 처리되지 않으므로, 모든 사람의 비식별을 보장하지 않습니다. 공개 전 사람의 육안 확인이 필요합니다.

상세 분석(근접 후보 이벤트 감사, 짧은 트랙 감사, COCO 기반 탐지 한계): [docs/day2_findings.md](docs/day2_findings.md)

### 3일차: 오탐 감소 후처리 (domain: real_cctv)

`configs/day3_eval.yaml` 로 정지 물체 필터·운전자 구분·ID 병합을 켜고 실제 CCTV 11개 영상을 실행(조건별 1회)한 결과, 근접 후보 에피소드가 **9건 → 4건**으로 줄었습니다. 제거된 5건은 고정 설비 오검출 4건, 같은 장비의 ID 단절로 생긴 중복 1건입니다. 7_tr21의 보행자–지게차 후보는 유지됐습니다. 남은 4건 중 2건은 짧게 검출된 운전자, 1건은 수동 핸드 파렛트 트럭이 원인입니다. 모든 이벤트는 후보이며 Near-Miss 로 확정하지 않았습니다. 상세: [docs/day3_report.md](docs/day3_report.md) · 데이터셋 조사: [docs/dataset_research.md](docs/dataset_research.md)

## 한계 및 향후 계획

- [x] 실제 CCTV MP4 로 Pipeline FPS 측정 (2일차)
- [x] 정지 물체 필터링, 운전자 오검출 제외, ID 병합 (3일차, 기본 비활성)
- [ ] 위험구역·픽셀 임계값 보정, 운전자 판정 전 이벤트 보류
- [ ] 위험 시점 수동 라벨링 → 이벤트 Precision / Recall / F1
- [ ] 지게차 포함 공개 데이터셋 확보(라이선스 확인) → YOLOv8 파인튜닝 → COCO 모델과 동일 테스트셋으로 mAP·P·R 비교
- [ ] ONNX Runtime 검증 → TensorRT (호환성 확인 후)
- [ ] RTSP 실제 스트림 연결 검증
- [ ] 호모그래피 기반 미터 거리 · TTC
- [ ] ByteTrack ↔ 자체 IoU Tracker 비교 실험
- 알려진 한계: ByteTrack 이 ID 를 잃고 새 ID 를 부여하면 같은 상황이 새 에피소드로 기록될 수 있음

## Tech Stack

Python 3.11 · PyTorch 2.11 (CUDA 12.8) · Ultralytics YOLOv8 (8.4.215) · ByteTrack · OpenCV 5.0 · NumPy · pytest
