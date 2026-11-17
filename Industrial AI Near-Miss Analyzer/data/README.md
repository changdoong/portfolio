# data/

영상/데이터셋은 용량·라이선스 문제로 Git 에 올리지 않습니다 (`data/*` 는 `.gitignore` 대상, 이 README 만 커밋).

## 1. 사용 중인 데이터셋

### Video Dataset for Safe and Unsafe Behaviours (실제 공장 CCTV)

| 항목 | 내용 |
|---|---|
| 출처 | Önal, O., Dandıl, E. (2024). *Video Dataset for Safe and Unsafe Behaviours*. Mendeley Data, V1 |
| DOI / URL | `10.17632/xjmtb22pff.1` · <https://data.mendeley.com/datasets/xjmtb22pff/1> |
| 라이선스 | **CC BY 4.0** — 재사용 시 출처 표기, 변경했다면 변경 사실 표시 |
| 내용 | 튀르키예 공장 CCTV, 8개 행동 클래스(안전 4 / 불안전 4), 691개 MP4 (약 10.0 GB), 1920×1080 |
| 이 프로젝트에서 받은 범위 | 지게차 관련 2개 클래스만: `3_carrying_overload_with_forklift` (56개) + `7_safe_carrying` (30개) = **86개, 1,091.7 MB (10⁶ 기준) / 1,041.1 MiB** |
| 개인정보 | 실제 작업자가 촬영되어 있음 → 공개용 캡처는 얼굴(머리 영역) 블러 처리 후 사용, 블러 전 원본 캡처는 공개하지 않음 |

실측으로 확인한 사항 (2026-11-17, OpenCV 5.0):
- 86개 모두 1920×1080, FPS 는 데이터셋 설명(24fps)과 달리 **24.6 ~ 25.25**
- 메타데이터 프레임 수 = 실제 읽은 프레임 수 (86/86)
- 이번에 확인한 86개는 모두 같은 고정 카메라 시점으로 보임

## 2. 다운로드 방법

`scripts/fetch_mendeley.py` 는 **인자 없이 실행하면 도움말만 출력하고 아무것도 받지 않습니다.**

```powershell
# 목록·용량만 조회 (공식 Public API 메타데이터, 영상 다운로드 없음)
.\.venv\Scripts\python.exe scripts\fetch_mendeley.py list --classes 3_ 7_

# 명시적 download 명령으로만 다운로드 (파일별 sha256 검증, 이미 받은 파일은 건너뜀)
.\.venv\Scripts\python.exe scripts\fetch_mendeley.py download --classes 3_ 7_ --dest data\raw\mendeley_safe_unsafe
```

- 다운로드 URL 은 Mendeley Public API (`data.mendeley.com/public-api/datasets/xjmtb22pff/...`)가 발급하는 서명 URL 이며 만료되므로, 스크립트가 파일마다 다시 조회합니다.
- 완료 후 `data/raw/mendeley_safe_unsafe/manifest.json` 에 파일별 크기·sha256·경로가 기록됩니다.

## 3. 폴더 구성

```
data/
└── raw/
    └── mendeley_safe_unsafe/
        ├── manifest.json
        ├── train/
        │   ├── 3_carrying_overload_with_forklift/3_tr*.mp4   (48)
        │   └── 7_safe_carrying/7_tr*.mp4                     (22)
        └── test/
            ├── 3_carrying_overload_with_forklift/3_te*.mp4   (8)
            └── 7_safe_carrying/7_te*.mp4                     (8)
```

## 4. 사전 조사 도구

```powershell
# 영상별 통계 + 대표 4프레임 Contact Sheet (outputs/dataset_survey/)
.\.venv\Scripts\python.exe scripts\survey_videos.py --manifest data\raw\mendeley_safe_unsafe\manifest.json --out outputs\dataset_survey

# 육안 판정(visual_review.csv)과 합쳐 요약 표·차트 생성
.\.venv\Scripts\python.exe scripts\make_survey_summary.py
```

※ COCO 에는 forklift 클래스가 없으므로 vehicle(car/motorcycle/bus/truck) 검출은 지게차 검출이 아닙니다.
※ 근접 후보 등급(A/B/C)은 육안 선별용이며 Near-Miss 판정이 아닙니다. 픽셀 거리는 실제 거리가 아닙니다.

## 5. 검토했지만 아직 받지 않은 데이터셋

| 데이터셋 | 상태 |
|---|---|
| NVIDIA PhysicalAI SDG-Warehouse (Hugging Face, 합성, **OpenMDW 1.1**) | 메타데이터만 조사. near-miss RGB 샤드 113개(샤드당 약 5.3 GB). 개별 MP4 Range 추출은 미검증 |
| AI Hub 산업안전 영상, SODA | 지게차 파인튜닝 후보 (라이선스 확인 필요) |
