# notebooks — 분석 Notebook 실행 안내

이 폴더의 Notebook 01~07과 SQL 파일로 데이터 점검부터 SHAP 해석까지 분석을 진행했습니다.
분석 결과는 [최종 보고서](../reports/HR_Analytics_final_report.md)에 정리되어 있습니다.

> **먼저 알아둘 점**
> - 저장된 출력은 실행하지 않고도 GitHub에서 볼 수 있습니다.
> - 다시 실행하려면 데이터 파일이 필요합니다. 원본·전처리 CSV는 이 저장소에 들어 있고(ODbL 1.0 / DbCL 1.0), 모델 파일은 들어 있지 않습니다([데이터 준비](#데이터와-모델-파일)).
> - **02번과 06번은 실행하면 프로젝트의 데이터·모델 파일을 덮어씁니다.** [덮어쓰기 주의](#덮어쓰기-주의-02번06번)를 먼저 읽으세요.

## Notebook 목록

| 순서 | 파일 | 내용 | Notebook 전용 패키지 | 읽는 파일 | 쓰는 파일 |
|--:|---|---|---|---|---|
| 1 | ` 01_data_overview.ipynb` | 데이터 구조와 품질 확인 | matplotlib, seaborn | `data/raw/hr.csv` | 없음 |
| 2 | `02_data_preprocessing.ipynb` | 전처리, 파생변수(`TenureGroup`, `AttritionBinary`) | 없음 | `data/raw/hr.csv` | **`data/processed/hr_preprocessed.csv`** |
| 3 | `03_eda.ipynb` | 탐색적 분석(EDA) | matplotlib, seaborn | `data/processed/hr_preprocessed.csv` | 없음 |
| 4 | `04_statistical_analysis.ipynb` | 인구통계 집단별 이직률(기술통계) | matplotlib, seaborn | `data/processed/hr_preprocessed.csv` | 없음 |
| 5 | `05_sql_analysis.ipynb` + `05_sql_analysis.sql` | SQLite로 집계 재현·교차 검증 | 없음(표준 라이브러리 `sqlite3`) | `data/raw/hr.csv`, `05_sql_analysis.sql` | 없음(메모리 DB) |
| 6 | `06_machine_learning.ipynb` | Logistic Regression, Optuna Random Forest | matplotlib, seaborn, optuna | `data/processed/hr_preprocessed.csv` | **`models/best_rf_optuna.pkl`** |
| 7 | `07_shap_analysis.ipynb` | SHAP 해석(06번과 같은 분할 `random_state=2020158011`) | matplotlib, seaborn | `data/processed/hr_preprocessed.csv`, `models/best_rf_optuna.pkl` | 없음 |

- 모든 Notebook은 pandas, numpy를 쓰고, 06·07은 scikit-learn과 joblib, 07은 shap도 씁니다. 이 패키지들은 대시보드 의존성(`requirements.txt`)에 포함되어 있습니다.
- 첫 Notebook의 파일명은 공백으로 시작합니다(` 01_data_overview.ipynb`). 원본 보존을 위해 이름을 바꾸지 않았습니다.
- 경로는 모두 `notebooks` 폴더 기준 상대 경로(`../data/...`)이므로, Jupyter의 작업 폴더가 `notebooks`여야 합니다.

## 실행 환경

- **Python:** 3.12(Notebook 메타데이터 3.12.4)
- **패키지:** [`requirements-notebooks.txt`](../requirements-notebooks.txt) = 대시보드 의존성(`requirements.txt`, 고정 버전 포함) + matplotlib, seaborn, optuna, JupyterLab, ipykernel

대시보드용 `.venv`를 바꾸지 않도록 **별도의 가상환경**을 권장합니다. 아래 명령은 Windows PowerShell 기준이며 저장소 루트에서 실행합니다.

```powershell
py -3.12 -m venv .venv-notebooks
.\.venv-notebooks\Scripts\python.exe -m pip install -r requirements-notebooks.txt
.\.venv-notebooks\Scripts\python.exe -m jupyter lab --notebook-dir notebooks
```

`.venv-notebooks/` 폴더는 `.gitignore`로 Git에서 제외됩니다.

## 실행 순서

01 → 02 → 03 → 04 → 05 → 06 → 07 순서를 권장합니다.

- 03·04·06·07은 02번이 만든 전처리 CSV를 읽습니다.
- 07은 06번이 저장한 모델을 읽습니다.
- 05는 원본 CSV만 읽으므로 01 이후 언제든 실행할 수 있습니다.
- 저장된 출력을 확인하는 것만이 목적이라면 실행하지 않아도 됩니다.

## 덮어쓰기 주의 (02번·06번)

| Notebook | 덮어쓰는 파일 | 영향 |
|---|---|---|
| 02 | `data/processed/hr_preprocessed.csv` | 같은 내용이 저장되어도 줄바꿈이나 인코딩이 달라지면 파일 해시가 바뀝니다. 테스트는 원본과 전처리 데이터의 일치를 다시 검증합니다. |
| 06 | `models/best_rf_optuna.pkl` | Optuna 탐색 결과에 따라 다른 모델이 저장될 수 있습니다. 모델 해시가 `dashboard/core/config.py`의 값과 달라져 `check_setup.py`에서 모델 경고(`WARN`, Machine Learning 화면 사용 불가)가 나고, 모델 관련 테스트와 07번 결과 재현이 실패할 수 있습니다. |

**권장 방법:**
1. 저장소를 **별도 폴더에 복사한 사본**에서 Notebook을 실행합니다. 대시보드와 테스트에 쓰는 원래 폴더의 파일은 그대로 둡니다.
2. 같은 폴더에서 실행해야 한다면, 실행 전에 두 파일을 다른 곳에 백업하고 실행 후 되돌립니다.
3. 02·06을 실행하지 않고 저장된 파일로 03·04·05·07만 실행할 수도 있습니다.

## 데이터와 모델 파일

| 파일 | 저장소 포함 여부 | 라이선스 |
|---|---|---|
| `data/raw/hr.csv` | 포함(Git 추적) | ODbL 1.0(데이터베이스), DbCL 1.0(개별 내용) |
| `data/processed/hr_preprocessed.csv` | 포함(Git 추적) | 파생 데이터베이스로 보고 ODbL 1.0으로 배포. 전처리 방법은 02번 Notebook과 `dashboard/core/preprocessing.py` |
| `models/best_rf_optuna.pkl` | **포함하지 않음**(Git 추적 해제, 이전 커밋에는 남아 있음) | 라이선스상 성격이 확정되지 않음 |

파일이 없거나 새로 준비해야 할 때는 다음 방법을 따릅니다.

| 파일 | 준비 방법 |
|---|---|
| `data/raw/hr.csv` | [IBM/employee-attrition-aif360](https://github.com/IBM/employee-attrition-aif360)의 `data/emp_attrition.csv`(이 프로젝트의 파일과 바이트 단위로 동일) 또는 [Kaggle](https://www.kaggle.com/datasets/pavansubhasht/ibm-hr-analytics-attrition-dataset)에서 받아 저장 |
| `data/processed/hr_preprocessed.csv` | 02번 Notebook 실행 |
| `models/best_rf_optuna.pkl` | 06번 Notebook 실행. 단, 다시 학습한 모델은 프로젝트의 모델과 같다는 보장이 없음(위 표) |

자세한 내용은 [최상위 README의 실행 방법](../README.md#11-설치-및-실행-방법)과 [DATASET_REVIEW.md](../DATASET_REVIEW.md)에 있습니다.

## 검증 상태

| 항목 | 상태 |
|---|---|
| 의존성 해결 | 2026-11-26에 `pip install --dry-run --ignore-installed -r requirements-notebooks.txt`로 확인했습니다. Windows, Python 3.12.4 환경에서 128개 패키지로 충돌 없이 해결되었고, 고정 버전이 모두 유지되었습니다. 실제 설치는 하지 않았습니다. |
| Notebook 실제 실행 | 05·07은 2026-11-24에 `requirements-notebooks.txt`와 같은 버전(matplotlib 3.10.1, seaborn 0.13.2, ipykernel 6.29.5)의 환경에서 처음부터 다시 실행했습니다. 그 환경의 tqdm은 4.67.1로, 이 파일로 설치되는 버전(4.70.1)과 다릅니다. |
| 01~04·06 | 저장된 출력은 이전 실행 결과이며, 그때 쓴 패키지 버전은 기록되어 있지 않습니다. 이 파일로 만든 환경에서 다시 실행해 확인하지는 않았습니다. |

## 데이터 출처와 라이선스

분석 데이터는 IBM 데이터 과학자가 만든 가상 데이터 “IBM HR Analytics Employee Attrition & Performance”입니다.
- 배포처인 IBM/employee-attrition-aif360 저장소와 Kaggle은 이 데이터를 [Open Database License(ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/)(데이터베이스)과 [Database Contents License(DbCL) 1.0](https://opendatacommons.org/licenses/dbcl/1-0/)(내용)으로 표기합니다.
- 이 폴더의 Notebook 출력과 그래프는 이 데이터에서 만든 결과물입니다(03·04·06·07번은 전처리 CSV에서 만듦).
- IBM 저장소는 데이터 출처를 Kaggle로 밝히며, IBM이 처음 배포한 곳의 이용 조건은 확인하지 못했습니다.
- Notebook의 코드와 SQL 쿼리에는 [MIT License](../LICENSE)가 적용되며, 데이터와 Notebook 출력에는 MIT가 적용되지 않습니다.

> Contains information from the [IBM HR Analytics Employee Attrition & Performance](https://www.kaggle.com/datasets/pavansubhasht/ibm-hr-analytics-attrition-dataset) dataset (also published in [IBM/employee-attrition-aif360](https://github.com/IBM/employee-attrition-aif360)), which is made available here under the [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/).

자세한 검토 기록은 [DATASET_REVIEW.md](../DATASET_REVIEW.md)와 [data/README.md](../data/README.md)에 있습니다.
