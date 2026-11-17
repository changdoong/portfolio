# Architecture

## 전체 흐름

```mermaid
flowchart LR
    A[Video Source<br/>MP4 · (RTSP 미검증)] --> B{tracking.type}
    B -- bytetrack --> C1[YOLODetector.track<br/>YOLOv8 + ByteTrack 1회]
    B -- iou --> C2[YOLODetector.detect<br/>YOLOv8]
    C1 --> D1[ByteTrackAdapter<br/>ID → 궤적 관리만]
    C2 --> D2[IoUTracker<br/>비교 실험용]
    D1 --> E1[ZoneMonitor<br/>구역 침입]
    D2 --> E1
    D1 --> E2[NearMissDetector<br/>픽셀 근접도]
    D2 --> E2
    E1 --> F[EpisodeManager<br/>start / escalate / end]
    E2 --> F
    F --> G[EventLogger<br/>events.csv]
    D1 --> H[Visualizer<br/>result.mp4]
    C1 --> P[LatencyStats<br/>perf.json]
```

## 모듈별 책임

| 모듈 | 파일 | 역할 |
|---|---|---|
| Video | `src/video/video_source.py` | 파일/웹캠 입력, 리사이즈, `create_source()` |
| | `src/video/rtsp_source.py` | 최신 프레임 유지 스레드, 자동 재연결 (**미검증**) |
| Detection | `src/detection/detector.py` | YOLO 래퍼. `detect()`(predict) / `track()`(내장 ByteTrack), `resolve_device()` 로 CUDA·FP16 자동 결정 |
| Tracking | `src/tracking/tracker.py` | `ByteTrackAdapter`(ID 수용·궤적), `IoUTracker`(자체 구현), `build_tracker()` |
| Risk | `src/risk/zone.py` | 다각형 위험구역, 침입 에피소드 |
| | `src/risk/near_miss.py` | 하단 중앙점 픽셀 거리 → warning/danger, (실험) 픽셀 TTC |
| | `src/risk/episode.py` | 이벤트 에피소드화: 유지시간(release)·쿨다운 |
| Pipeline | `src/pipeline.py` | 오케스트레이션, Inference/Pipeline 시간 측정, 시각화·저장 |
| Utils | `src/utils/metrics.py` | `LatencyStats`, `EventLogger`, 이벤트 P/R/F1 |

## 설계 포인트

### 1. ByteTrack 단일 실행
- ByteTrack 은 `model.track(persist=True, tracker=configs/bytetrack.yaml)` 안에서만 실행된다.
- `ByteTrackAdapter` 는 연관(association) 계산을 하지 않고, 받은 `track_id` 로 궤적·속도·마지막 관측만 관리한다.
- 파이프라인은 `tracking.type` 에 따라 `track()` 또는 `detect()` 중 **하나만** 프레임당 1회 호출한다 (테스트로 검증).

### 2. 빈 프레임과 track_id 누락
- 검출 없음 → 빈 목록 (정상)
- ultralytics 는 ByteTrack 이 확정한 트랙이 없으면 검출을 ID 없이(`boxes.id=None`) 반환한다
  (예: 점수 < `new_track_thresh`). 이것은 정상 상태이므로 빈 목록으로 처리하고 `frames_with_untracked_detections` 로 집계한다.
- 어댑터에 `track_id` 없는 검출이 실제로 전달되면 → `ValueError` (detect 결과를 잘못 전달한 프로그래밍 오류)

### 3. 근접도 = 하단 중앙점 픽셀 거리
bbox 중심은 객체 높이에 따라 달라지므로(사람 vs 트럭) 하단 중앙(지면 접점)을 사용한다.
원근 왜곡으로 픽셀 거리 ≠ 실제 거리 → 미터 단위는 호모그래피 이후.

### 4. 이벤트 에피소드
```
[안전] ─위험─▶ [진행 중: start] ─등급 상승─▶ escalate ─release_frames 연속 안전─▶ [end] ─cooldown─▶ [안전]
```
위험구역 침입에도 동일하게 적용되어 경계선 흔들림에 의한 반복 기록을 막는다.

### 5. 성능 측정
| 지표 | 구간 |
|---|---|
| Inference | ultralytics `speed["inference"]` – 모델 forward 만 (pre/post 별도 기록) |
| Pipeline | `source.read()` 시작 ~ 저장/화면 출력 종료 (wall-clock) |
처음 `warmup_frames` 는 제외, 평균·p50·p95 를 `perf.json` 에 실행 조건과 함께 저장.

### 6. 장치·정밀도
`resolve_device()` : CUDA 요청 + 미사용 가능 → CPU/FP32 폴백, CPU 에서는 항상 FP32.
ultralytics 8.4 에서 `half` 인자가 deprecated 되어 내부적으로 `quantize=16|None` 으로 전달한다.

### 7. 설정 호환성
구 설정 형식(`tracking` 에 type 없음, `near_miss.distance_px`)은 이전 동작(IoUTracker, TTC+쿨다운)을 유지한다.

## 한계 및 개선 방향
- **원근 왜곡**: 바닥 4점 호모그래피 → 미터 단위 거리·TTC
- **지게차 클래스 부재**: 공개 산업 데이터셋으로 파인튜닝, COCO 모델과 동일 테스트셋 비교
- **ID 전환**: ByteTrack ID 교체 시 새 에피소드로 기록됨
- **배포**: ONNX Runtime → TensorRT, RTSP 실연결 검증
