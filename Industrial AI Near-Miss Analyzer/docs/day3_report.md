# Day 3 보고서: 정지 물체 필터 · 운전자 구분 · ID 병합

> 모든 결과는 **실제 CCTV (domain: real_cctv)** 영상 기준입니다. 이벤트는 **후보**이며 Near-Miss 로 확정하지 않았고, 거리는 미보정 픽셀 거리입니다.
> 세 기능은 `configs/config.yaml` 에서 **기본 비활성**이며, ByteTrack 설정(`configs/bytetrack.yaml`)은 변경하지 않았습니다.

## 1. 구현 요약

| 기능 | 파일 | 판정 방식 | 기록 |
|---|---|---|---|
| D3-4 ID 병합 | `src/tracking/id_merger.py` | 새 raw ID 가 등장할 때, 같은 카테고리이고 `max_gap_frames` 안에 사라졌으며 현재 비활성인 canonical 트랙의 마지막 위치(+속도 외삽)와 `max_dist_px` 이내이면 그 canonical ID 로 연결. **원본 track_id 는 그대로 보존** | `merge_log.csv`, `tracks.csv` 의 `canonical_track_id` 열 |
| D3-2 정지 물체 필터 | `src/risk/object_filter.py` | ① 한 번이라도 `move_px` 이상 이동 → `dynamic` (정차해도 계속 보호) ② 박스 높이 ≥ 프레임의 20% → `protected_large` ③ 이동 이력 없음 + 무시 구역 → `ignored_zone` (제외) ④ 이동 이력 없음 + `min_frames` 이상 관측 → `static` (제외) ⑤ 그 외 `pending` (포함) | `static_log.csv`, `tracks.csv` 의 `vehicle_status` |
| D3-3 운전자 구분 | `src/risk/role_classifier.py` | 최근 `window` 프레임에서 **세 조건 모두**: IoA 중앙값 ≥ 0.5 · 운전석 영역 안 + 발이 차량 하단보다 위인 프레임 비율 ≥ 0.6 · 순변위 동시 이동 (차량 이동 시 상대오차 ≤ 0.5, 차량 정지 시 사람도 정지). 관측 < `min_frames` 이면 판정하지 않음(보행자로 취급) | `role_log.csv` (판정 변경 시점·지표·사유) |
| 연결 | `src/risk/track_analysis.py`, `src/pipeline.py` | `TrackView` 가 canonical ID 를 노출. 정지 물체는 근접 판정에서 제외, 운전자–자기 차량 쌍은 `exclude_pairs` 로 제외 | `perf.json` 의 `analysis` |

## 2. 실제 영상 검증 (`configs/day3_eval.yaml`, FP16 · 결과 저장 ON · 조건별 1회)

기준선: Day 2 결과(5개) + `configs/day3_baseline.yaml`(운전자 오검출 관찰 영상 6개, 분석 비활성)

| 영상 | 기준선 근접 에피소드 | Day 3 근접 에피소드 | ID (raw→canonical, 병합 수) | vehicle 상태 | 운전자 판정 쌍 |
|---|---|---|---|---|---|
| 7_tr21 | 1 (1-3) | **1 (1-3) 유지** | 11→6 (5) | dynamic 2 | 0 |
| 3_tr6 | 1 (4-9) | **0** | 15→15 (0) | dynamic 2 · large 3 · ignored 4 | 0 |
| 3_tr2 | 2 (10-9, 10-14) | **0** | 12→10 (2) | dynamic 2 · ignored 4 | 0 |
| 3_tr19 | 2 (2-8, 2-10) | **1 (2-8)** | 7→6 (1) | dynamic 1 · large 1 | 0 |
| 7_te2 | 0 | 0 | 4→4 | dynamic 1 | 0 |
| 7_te6 | 1 (22-25) | **0** | 14→8 (6) | dynamic 1 · large 2 · ignored 1 | **1** |
| 7_te7 | 1 (2-3) | 1 (1-3) | 6→5 (1) | dynamic 1 · ignored 2 | 0 |
| 7_tr3 | 0 | 0 | 5→5 | dynamic 1 · ignored 2 | 0 |
| 7_tr13 | 0 | 0 | 3→3 | dynamic 1 | 0 |
| 7_tr15 | 0 | 0 | 4→4 | dynamic 2 | 0 |
| 3_tr36 | 1 (5-3) | 1 (5-3) | 3→3 | dynamic 1 | 0 |
| **합계** | **9** | **4** | | | |

### 기능별 판단 (비식별 캡처 육안 확인 포함)

**D3-2 정지 물체 필터**
- 제거된 4건(3_tr6 1, 3_tr2 2, 7_te6 1)은 모두 좌상단 고정 설비(파란 카트/적재함)와의 쌍이었습니다(Day 2 감사와 일치).
- 제거 근거는 모두 **무시 구역(`ignored_zone`)**이었습니다. 관측 시간 기반 `static` 판정은 한 번도 발생하지 않았습니다. 해당 오검출 트랙이 1~8프레임으로 짧아 `min_frames=15`에 도달하지 못했기 때문입니다. 따라서 이 카메라에서 효과를 낸 것은 **카메라별 무시 구역 설정**이고, 무시 구역 없이 다른 카메라에 적용하면 효과가 작을 수 있습니다.
- 보호 확인: 실제 지게차는 모든 영상에서 `dynamic`이었습니다. 7_tr21의 보행자–지게차 후보는 유지됐습니다.

**D3-3 운전자 구분**
- 7_tr21 보행자(#1)는 IoA 0.71이지만 **운전석 비율 0.00**으로 보행자 판정이 유지됐습니다. 회귀 테스트로도 고정했습니다.
- 7_te6: 운전석 안 person #19가 운전자로 판정됐습니다(IoA 1.0, 운전석 1.0, 순변위 상대오차 0.34). 프레임 228에서 한 번 보행자로 바뀌었다가 229에 다시 운전자로 판정됐고, 이 과정이 로그에 남아 있습니다.
- **한계**: 남은 4건 중 2건(7_te7 1-3, 3_tr36 5-3)은 육안으로 **운전석 안의 운전자**가 원인이었습니다. 운전자 person이 각각 2프레임, 5프레임만 추적돼 `min_frames=8`에 못 미쳤고, 근접 이벤트가 판정보다 먼저 기록됐습니다.
- 개발 중 수정 1건: 동시 이동 판정을 프레임별 변위에서 **창 전체의 순변위** 비교로 바꿨습니다. 프레임별 박스 흔들림 때문에 7_te6 운전자가 보행자로 판정되던 문제(상대오차 0.68)를 이 수정으로 해결했습니다.

**D3-4 ID 병합**
- 3_tr19: 같은 수동 핸드 파렛트 트럭의 ID 단절(8→10)이 병합되어 중복 에피소드 1건이 사라졌습니다.
- 3_tr2: 정지 설비의 ID 단절(9→6)이 병합됐습니다.
- 7_tr21(5건), 7_te6(6건)의 vehicle 병합과 3_tr2·7_te7의 person 병합 각 1건은 **병합이 맞았는지 육안으로 확인하지 않았습니다.** 잘못 병합하면 다른 객체가 같은 ID로 묶입니다. 그래서 기본값은 꺼져 있고, 영상별 `merge_log.csv`로 검토할 수 있습니다.

### 남은 후보 이벤트 4건

| 영상 | 쌍 | 육안 원인 | 향후 대응 |
|---|---|---|---|
| 7_tr21 | 1-3 | 보행자와 실제 지게차의 화면상 근접 (재검토 우선 후보) | 카메라 보정 후 실제 거리 확인 |
| 3_tr19 | 2-8 | 작업자가 직접 끄는 핸드 파렛트 트럭 | 수동 운반 장비 클래스 학습 (파인튜닝) |
| 7_te7 | 1-3 | 운전자를 person 으로 오검출 (2프레임) | 판정 확정 전 이벤트 보류 또는 파인튜닝 |
| 3_tr36 | 5-3 | 운전자를 person 으로 오검출 (5프레임) | 같음 |

### 처리 시간
Pipeline 평균 시간은 기준선 대비 증가하지 않았습니다(영상별 19.97~23.34 ms, 기준선 21.29~25.59 ms). 다만 실행 시점이 달라 GPU·시스템 부하가 같지 않았습니다. 따라서 이 차이를 "속도 향상"으로 해석하지 않으며, 분석 기능의 오버헤드는 이 측정으로 구분할 수 없는 수준이라고만 판단합니다.

## 3. 재현

```powershell
.\.venv\Scripts\python.exe scripts\run_batch.py --videos configs\day3_baseline.yaml --out outputs\day3\baseline
.\.venv\Scripts\python.exe scripts\run_batch.py --videos configs\day3_eval.yaml --out outputs\day3\filtered_v2
```
`outputs/day3/filtered/`는 동시 이동 판정 수정 **전** 결과이며 비교용으로 보존했습니다.
