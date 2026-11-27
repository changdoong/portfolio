# docs/captures — 대시보드 화면 캡처 출처와 라이선스

이 폴더에는 대시보드 개발 단계별 화면·테스트 캡처가 있습니다.

| 폴더 | 내용 |
|---|---|
| `stage2/` | Overview, 사이드바, KPI, 부서별 현황 |
| `stage3/` | Workforce Analysis, 필터 |
| `stage4/` | 데이터 파일이 없을 때의 오류 안내 |
| `stage5/` | Machine Learning |
| `stage6/` | HR Insights |
| `stage7/` | 공개 준비: 데이터 출처·라이선스 고지, 모델 파일이 없는 환경 |

2단계 C11 캡처 하나만 `dashboard/docs/captures/stage2/`에 있습니다.

Stage 2~6 캡처는 촬영 당시 화면이라 사이드바에 라이선스 문구가 없습니다. 현재 사이드바는 Stage 7 캡처에서 볼 수 있습니다.

### Stage 7 캡처(2026-11-27, headless Chrome, 너비 1440px)

| 파일 | 내용 |
|---|---|
| `stage7/s7_01_license_notice.png` | Overview 화면(1440×1000). 사이드바에 데이터 출처(Kaggle, IBM/employee-attrition-aif360), ODbL 1.0·DbCL 1.0, 코드 MIT 구분 표시. 출처·ODbL·DbCL은 공식 주소로 가는 새 탭 링크(Stage 7-7 재촬영) |
| `stage7/s7_02_model_optional.png` | 모델 파일을 포함하지 않은 새 clone 환경의 Machine Learning 화면(1440×900). 모델 파일을 찾을 수 없다는 안내와 해결 방법 표시(파일 이름만 표시, 절대 경로 없음) |

## 데이터 출처와 라이선스

캡처에 보이는 수치, 표, 차트는 아래 데이터에서 만든 결과물(ODbL의 Produced Work)입니다.

> Contains information from the [IBM HR Analytics Employee Attrition & Performance](https://www.kaggle.com/datasets/pavansubhasht/ibm-hr-analytics-attrition-dataset) dataset (also published in [IBM/employee-attrition-aif360](https://github.com/IBM/employee-attrition-aif360)), which is made available here under the [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/). Individual contents are licensed under the [Database Contents License (DbCL) 1.0](https://opendatacommons.org/licenses/dbcl/1-0/).

- 대시보드는 원본 CSV와 전처리 CSV를 읽습니다. 두 파일은 이 저장소에 함께 공개합니다(원본: ODbL 1.0·DbCL 1.0, 전처리: ODbL 1.0).
- 전처리 방법은 `notebooks/02_data_preprocessing.ipynb`와 `dashboard/core/preprocessing.py`에 있습니다.
- 저장소 코드에 적용되는 MIT License(`../../LICENSE`)는 이 캡처에 담긴 데이터 결과물에 적용되지 않습니다.
- 데이터 라이선스 표기의 근거와 확인하지 못한 사항은 [data/README.md](../../data/README.md)와 [DATASET_REVIEW.md](../../DATASET_REVIEW.md)에 있습니다.
