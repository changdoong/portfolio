# data — 데이터 출처와 준비 방법

## 데이터 출처

| 항목 | 내용 |
|---|---|
| 데이터셋 | IBM HR Analytics Employee Attrition & Performance |
| 성격 | IBM 데이터 과학자가 만든 **가상(fictional) 직원 데이터**입니다. 실제 기업의 인력 현황이나 실제 개인정보가 아닙니다. |
| 배포처 | [IBM/employee-attrition-aif360](https://github.com/IBM/employee-attrition-aif360)의 `data/emp_attrition.csv`, [Kaggle](https://www.kaggle.com/datasets/pavansubhasht/ibm-hr-analytics-attrition-dataset)의 `WA_Fn-UseC_-HR-Employee-Attrition.csv` |
| 규모 | 1,470행, 35열(헤더 제외) |

## 라이선스

이 폴더의 데이터 파일에는 아래 데이터 라이선스가 적용됩니다. 저장소의 코드에 적용되는 MIT License(`../LICENSE`)는 이 폴더의 데이터에 적용되지 않습니다.

| 파일 | 적용 라이선스 |
|---|---|
| `raw/hr.csv` | 데이터베이스: [Open Database License(ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/), 개별 내용: [Database Contents License(DbCL) 1.0](https://opendatacommons.org/licenses/dbcl/1-0/) |
| `processed/hr_preprocessed.csv` | 원본의 파생 데이터베이스일 가능성이 높아 **ODbL 1.0으로 배포**합니다(개별 내용은 DbCL 1.0). |

> This project contains information from the [IBM HR Analytics Employee Attrition & Performance](https://www.kaggle.com/datasets/pavansubhasht/ibm-hr-analytics-attrition-dataset) dataset (also published in [IBM/employee-attrition-aif360](https://github.com/IBM/employee-attrition-aif360)), which is made available here under the [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/). Individual contents are licensed under the [Database Contents License (DbCL) 1.0](https://opendatacommons.org/licenses/dbcl/1-0/).
> `processed/hr_preprocessed.csv` is a derivative of the original database and is made available under the ODbL 1.0. The preprocessing method is provided in `notebooks/02_data_preprocessing.ipynb` and `dashboard/core/preprocessing.py`.

**출처와 라이선스 표기의 근거:**
- IBM 공식 저장소 README는 이 데이터를 ODbL(데이터베이스)·DbCL(내용)로 표기하고, 데이터 출처를 Kaggle로 밝힙니다.
- Kaggle 데이터셋 페이지도 "Database: Open Database, Contents: Database Contents"로 표기합니다.
- IBM이 처음 배포한 곳(Watson Analytics 샘플)의 이용 조건은 확인하지 못했습니다. 따라서 위 표기는 두 배포처의 표기를 따른 것이며, 권리 관계가 완전히 확정되었다는 뜻은 아닙니다.

**전처리 방법(ODbL 4.6):** 원본과의 차이는 상수형 변수 3개 제거와 파생변수 2개 추가뿐이며, 그 방법은 [`notebooks/02_data_preprocessing.ipynb`](../notebooks/02_data_preprocessing.ipynb)와 [`dashboard/core/preprocessing.py`](../dashboard/core/preprocessing.py)에 있습니다.

라이선스 원문 대조 결과와 미확정 항목은 [DATASET_REVIEW.md](../DATASET_REVIEW.md)에 있습니다. 법률 자문이 아니라 공개 자료를 대조한 기록입니다.

## 파일 구성

| 파일 | 내용 | 만드는 방법 |
|---|---|---|
| `raw/hr.csv` | 원본 데이터(227,977바이트). IBM 저장소의 `data/emp_attrition.csv`와 바이트 단위로 같습니다. | 배포처에서 내려받아 이 이름으로 저장 |
| `processed/hr_preprocessed.csv` | 전처리 결과(1,470행, 34열). 상수형 변수 3개를 제거하고 파생변수 `TenureGroup`, `AttritionBinary`를 추가했습니다. | `notebooks/02_data_preprocessing.ipynb` 실행 |
| `../models/best_rf_optuna.pkl` | 06번 Notebook에서 저장한 Random Forest 모델(이 폴더 밖, Git 추적 안 함) | `notebooks/06_machine_learning.ipynb` 실행 |

**현재 저장소 상태:**
- `raw/hr.csv`와 `processed/hr_preprocessed.csv`는 이 저장소에서 Git으로 추적되며 위 라이선스로 공개합니다.
- 모델 파일 `models/best_rf_optuna.pkl`은 라이선스상 성격과 배포 가능 여부가 확정되지 않아 Git 추적을 해제했습니다(로컬 실행용 파일로만 사용). 다만 **이전 커밋에는 모델 파일이 남아 있습니다.** Git 이력은 재작성하지 않았습니다.
- `.gitignore`에는 모델 파일의 제외 규칙만 있습니다. 추적을 해제한 모델 파일이 다시 추가되지 않도록 하며, 두 CSV는 제외하지 않습니다.

## 데이터를 새로 준비할 때

1. 원본 CSV를 위 배포처에서 받아 `data/raw/hr.csv`로 저장합니다.
2. `notebooks/02_data_preprocessing.ipynb`를 실행해 전처리 CSV를 만듭니다.
3. 모델이 필요하면 `notebooks/06_machine_learning.ipynb`를 실행합니다.
4. 저장소 루트(`hr_df`)에서 점검 스크립트를 실행합니다.

```powershell
.\.venv\Scripts\python.exe dashboard\scripts\check_setup.py
```

**주의할 점:**
- **02번과 06번 Notebook은 실행하면 이 파일들을 덮어씁니다.** 실행 전에 [notebooks/README.md](../notebooks/README.md#덮어쓰기-주의-02번06번)를 먼저 읽으세요.
- 다시 학습한 모델은 프로젝트의 모델과 같다는 보장이 없습니다. 모델 해시가 `dashboard/core/config.py`의 값과 다르면 `check_setup.py`는 모델 경고(`WARN`)를 표시하고(Machine Learning 화면 사용 불가), 모델 관련 테스트가 실패할 수 있습니다. 모델이 없을 때는 `check_setup.py`가 `WARN`과 함께 `RESULT: PASS`로 끝납니다.
- Overview, Workforce Analysis, HR Insights 화면은 두 CSV만 있으면 실행됩니다. Machine Learning 화면은 모델 파일이 필요하며, 없으면 차트 대신 준비 방법 안내를 표시합니다.
