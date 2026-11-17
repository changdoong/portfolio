# 데이터셋 조사 보고서 (다운로드 전)

조사일: 2026-11-17. 아무것도 다운로드하지 않았습니다. NVIDIA 항목은 공개 API 메타데이터와 HTTP Range로 tar·JSON 헤더 일부(약 35 KB, 메모리에서만 처리)를 읽어 확인했습니다.

## 1. 지게차 파인튜닝용 공개 데이터셋

| 데이터셋 / 출처 | 지게차 / 작업자 클래스 | 바운딩 박스 | 수량 | 라이선스 | 상업 이용·파생 모델 학습 | YOLO 학습 지원 | 비고 |
|---|---|---|---|---|---|---|---|
| **forklift-dsitv** (Roboflow Universe `mohamed-traore-2ekkp`, HF 미러 `keremberke/forklift-object-detection`) | `forklift`, `person` ✅ | ✅ (COCO 형식) | 421장 (train 295 / val 84 / test 42) | **CC BY 4.0** (HF 카드 기재. Roboflow 원 페이지는 접근 차단(403)으로 확인하지 못함) | CC BY 4.0이면 출처 표기 시 상업 이용·파생물 허용 | COCO → YOLO 변환 필요 (Roboflow 원 페이지는 YOLO 내보내기 제공, 미확인) | 소규모. 원 페이지 라이선스 재확인 필요 |
| **Construction-PPE** (Ultralytics 공식 문서) | `forklift`, `Person` ✅ (+보호구 10종) | ✅ (YOLO 형식, 14,863 박스) | 1,000장 (train 800 / val 200) | **CC BY 4.0** | 출처 표기 시 허용 | ✅ (yaml + zip 제공) | 건설현장 위주. 지게차 비중 미확인 |
| Roboflow Universe 기타 (`luzuko/forklift-person-detector`, `opop/forkliftdetection`, `zulfa/kp_fullframe`, `gazi-university-6bdmi/forkliftpersondetection` 등) | 검색 결과상 forklift·person 포함 | 확인 불가 | 확인 불가 | **확인 불가** (페이지 403) | 확인 불가 | Roboflow는 일반적으로 YOLO 내보내기를 제공하나 미확인 | 라이선스는 프로젝트마다 업로더가 정함 → 개별 확인 필수 |
| **AI Hub 「물류창고 내 작업 안전 데이터」** (dataSetSn=510, NIA) | `WO-04 지게차` 286,040 · `WO-01/02 작업자` 562,894 · `WO-05 핸드파레트카` 34,856 ✅ | ✅ 바운딩박스 + 폴리곤 (JSON, `[x,y,w,h]` 절대좌표) | 576,908장 (14개 이상 물류창고 CCTV/카메라 + 연출 영상) | AI Hub 이용정책 | 영리·비영리 **연구·개발 목적** 활용 가능. 데이터 판매 등 상업적 이용은 별도 협의. **내국인만 신청 가능**, 국외 반출은 NIA 별도 합의. 학습 모델 이용 조건은 데이터셋 페이지에 명시되지 않음 | JSON → YOLO 변환 필요 | **클래스 구성이 이 프로젝트와 가장 잘 맞음** (지게차·작업자·핸드파렛트카 구분). 다운로드 승인 절차 필요. 공개 포트폴리오에 원본 이미지 게시는 불가로 보는 것이 안전 |

### 평가
- **가장 적합한 데이터**: AI Hub 물류창고 데이터. 지게차와 작업자뿐 아니라 Day 2·3에서 문제가 된 **핸드파렛트카**까지 별도 클래스로 있습니다. 다만 내국인 신청과 승인이 필요하고, 원본 재배포·국외 반출이 제한되며, 학습 모델 공개 조건은 수행기관에 확인해야 합니다.
- **즉시 사용 가능**: forklift-dsitv(421장)와 Construction-PPE(1,000장)는 CC BY 4.0이지만 규모가 작고, 촬영 시점이 이 공장 CCTV(높은 고정 시점)와 다릅니다.
- **대안 (공개 데이터가 부적합할 때)**: Mendeley 86개 영상(CC BY 4.0)에서 프레임을 추출해 직접 라벨링합니다.
  - 대상: 지게차가 육안으로 확인된 73개 영상에서 영상당 5~10프레임, 약 400~700장
  - 클래스: `forklift`, `person`, `hand_pallet_truck`, `driver`(선택)
  - 분할: 같은 영상이 섞이지 않도록 **영상 단위**로 train/val/test 분할
  - 필요 도구: 라벨링 도구(CVAT / Label Studio). **설치 전 승인 필요**
  - 장점: 실제 배치 카메라와 같은 도메인
  - 한계: 카메라가 1대라 일반화가 제한적
- **권장 순서**:
  1. AI Hub 이용 조건 확인 (신청 자격, 학습 모델 공개 범위)
  2. CC BY 4.0 공개셋과 Mendeley 직접 라벨로 1차 파인튜닝
  3. COCO 모델과 같은 Mendeley test 세트로 mAP·P·R 비교

## 2. NVIDIA PhysicalAI SDG-Warehouse 샘플 수집 계획 (카메라 보정 검증용)

### 확인한 사항
| 항목 | 내용 |
|---|---|
| 라이선스 | 현재 Dataset Card 기준 **OpenMDW 1.1** (`license_name: openmdw-1.1`). 카드에 "commercial or non-commercial uses" 가능이라고 적혀 있음. 세부 조항은 https://openmdw.ai/ 원문 확인 필요 |
| 시나리오 | `forklift_human_nearmiss`: 작업자가 서 있고 지게차가 접근. 회피 거리 파라미터로 near-miss와 실제 접촉을 구분해 생성 |
| RGB tier | `rgb/forklift_human_nearmiss/` 113 샤드, 1.10~5.37 GB, 합계 **589.6 GB**. 실행(run)당 카메라 10대(ceiling 5 + eye 5), 1920×1080, 10.0초 (MP4 헤더 실측) |
| Artifacts tier | `artifacts/forklift_human_nearmiss/` 547 샤드, 2.78~79.18 GB, 합계 **2,637 GB**. 실행 1개(샤드 00546 첫 샘플)가 약 1.19 GB(69개 멤버)이며, 대부분 instance-id npz와 매핑 파일 |
| 카메라 파라미터 | `<cam>.camera_params.jsonl` (카메라당 0.22~0.33 MB, 프레임당 1줄): `cameraProjection`, `cameraViewTransform`(월드→카메라), `cameraFocalLength`, `cameraAperture`, `metersPerSceneUnit: 1.0`, `renderProductResolution [1920,1080]`, `cameraModel: pinhole` ✅ |
| 3D 박스 | `<cam>.object_detection.jsonl` (카메라당 0.97~2.29 MB): 작업자(`class: character`)와 **지게차(`class: robot`, `/World/Robots/forklift/Forklift`)**에 대해 `bounding_box_2d_tight/loose_fast`, `bounding_box_3d_fast` 제공 ✅ |
| near-miss / 접촉 구분 | `metadata/runs.parquet`(1.79 MB)에 있을 것으로 보이나 **확인하지 못함**. 읽으려면 `pyarrow` 설치가 필요 (**승인 필요**) |
| 개별 추출 | Range 요청 지원(206)을 확인했고, tar 헤더로 멤버의 offset·크기를 계산할 수 있습니다. **실제 MP4·JSONL 구간 추출은 아직 하지 않았습니다** |

### 수집 계획 (승인 후 진행)

| 단계 | 내용 | 예상 다운로드 |
|---|---|---|
| N0 | `pyarrow` 설치 승인 → `runs.parquet`·`clips.parquet`으로 near-miss/접촉 구분, 실행별 샤드 위치 확인 | 6.2 MB (메타데이터) |
| N1 | 실행 3개 × 천장 카메라 2대 × (`rgb.mp4` 약 16 MB + `camera_params.jsonl` 약 0.3 MB + `object_detection.jsonl` 약 2.2 MB)를 artifacts 샤드에서 **Range로 멤버만 추출**. 받은 크기를 tar 헤더 크기와 대조하고 OpenCV로 열어 검증 | 약 **111 MB** (3 × 2 × 18.5 MB) |
| N1 실패 시 | 가장 작은 artifacts 샤드(00546) 전체. **받기 전에 다시 승인 요청** | 2.78 GB |
| 참고 | 일반적인 artifacts 샤드 1개 / RGB 샤드 1개 | 약 4.8 GB / 약 5.3 GB |

### 검증 방법 (합성 데이터 결과는 실제 CCTV 결과와 분리 기록)
1. GT 카메라 파라미터로 바닥(z=0) 평면 호모그래피를 계산 → 기준값
2. 영상에서 바닥 기준점 4개 이상을 사람이 선택해 호모그래피를 추정 (`scripts/calibrate_ground.py`, Day 4 예정)
3. 작업자·지게차의 하단 중앙점을 미터로 변환해 GT 3D 박스 중심 간 거리와 비교 → 거리 오차(평균·최대·거리 구간별)
4. 결과는 `domain: synthetic`으로 기록하고, Mendeley 실제 CCTV의 추정 보정 결과와 **같은 표에 섞지 않음**
