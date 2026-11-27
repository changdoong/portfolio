# HR Analytics: 직원 이직 분석과 인터랙티브 대시보드

IBM HR Analytics 공개 샘플 데이터(직원 1,470명)로 직원 이직 현황을 분석한 데이터 분석 프로젝트입니다.

**분석 과정:** 데이터 품질 점검 → 전처리 → EDA → 집단별 이직률 비교 → SQL 교차 검증 → 머신러닝 → SHAP 해석

**결과물:**
- Notebook 분석
- [최종 분석 보고서](reports/HR_Analytics_final_report.md)
- Streamlit 대시보드

> 이 데이터는 IBM이 만든 가상 데이터이며 실제 기업의 인력 현황이 아닙니다.

| 핵심 수치 | 값 |
|---|---|
| 분석 대상 | 직원 1,470명, 원본 변수 35개 |
| 이직 직원 / 전체 이직률 | 237명 / 16.12% |
| 가장 큰 이직률 차이(EDA) | 초과근무 30.53% vs 비초과근무 10.44% |
| 모델 성능(테스트 294건) | Logistic Regression F1 0.5333 · ROC-AUC 0.8842 / Random Forest + Optuna F1 0.5169 · Recall 0.4894 |
| SHAP 상위 변수 | 초과근무 여부, 월 소득, 스톡옵션 수준, 직무 등급, 연령 |
| 테스트 | pytest 325개 통과(2026-11-27, 데이터·모델이 있는 환경) |

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [분석 목표 및 문제 정의](#2-분석-목표-및-문제-정의)
3. [데이터 출처 및 구성](#3-데이터-출처-및-구성)
4. [EDA 및 통계 분석](#4-eda-및-통계-분석)
5. [SQL 분석](#5-sql-분석)
6. [머신러닝 모델링 및 평가](#6-머신러닝-모델링-및-평가)
7. [SHAP 해석](#7-shap-해석)
8. [Dashboard 주요 기능](#8-dashboard-주요-기능)
9. [주요 분석 결과와 실무적 인사이트](#9-주요-분석-결과와-실무적-인사이트)
10. [프로젝트 구조](#10-프로젝트-구조)
11. [설치 및 실행 방법](#11-설치-및-실행-방법)
12. [테스트 및 품질 검증](#12-테스트-및-품질-검증)
13. [프로젝트 한계와 향후 개선 방향](#13-프로젝트-한계와-향후-개선-방향)

## 1. 프로젝트 개요

직원 이직은 인력 운영과 업무 연속성에 영향을 주는 주요 인사 지표입니다. 이 프로젝트는 두 부분으로 구성됩니다.

| 구분 | 내용 | 상태 |
|---|---|---|
| Notebook 분석(01~07) | 데이터 점검, 전처리, EDA, 집단별 이직률 비교, SQL 교차 검증, 머신러닝, SHAP 해석 | 완료 |
| 최종 보고서 | 분석 결과, 해석, 한계, 비즈니스 시사점 정리 | 완료 |
| 대시보드: Overview, Workforce Analysis | 전사 KPI, 부서별 현황, 부서·성별 필터와 인력 특성별 이직률 | 구현 |
| 대시보드: Machine Learning | 저장 모델의 성능 지표, 혼동행렬, ROC Curve, 변수 중요도, SHAP 해석 | 구현 |
| 대시보드: HR Insights | 분석 결과를 인사관리 관점에서 해석한 인사이트와 개선 제안 | 구현 |

**사용 기술:**

| 영역 | 기술 |
|---|---|
| 분석 | Python 3.12, pandas, NumPy, Matplotlib, Seaborn |
| SQL | SQLite(Python 표준 라이브러리 `sqlite3`) |
| 머신러닝 | scikit-learn(Pipeline, Logistic Regression, Random Forest), Optuna, SHAP |
| 대시보드 | Streamlit, Plotly, HTML/CSS |
| 테스트 | pytest, Streamlit `AppTest` |

## 2. 분석 목표 및 문제 정의

**문제:** 어떤 직원 집단에서 이직이 많이 나타나는지, 그리고 이직 여부를 예측할 때 어떤 정보가 중요하게 쓰이는지 확인합니다.

**분석 목표:**
- 연령, 성별, 결혼 여부, 부서, 직무, 소득, 근속, 초과근무, 만족도에 따른 이직률 차이를 탐색합니다.
- pandas 집계를 SQL로 다시 계산해 결과를 교차 검증합니다.
- 이직 여부(`Attrition`)를 예측하는 이진 분류 문제로 정의하고, Logistic Regression과 Optuna로 튜닝한 Random Forest를 비교합니다.
- SHAP으로 모델 예측에 기여한 변수를 해석합니다.
- 분석 결과를 원하는 집단으로 좁혀 다시 볼 수 있도록 대시보드로 제공합니다.

**해석 원칙:**
- 집단 간 이직률 차이는 연관성입니다. 인과관계나 통계적 유의성을 뜻하지 않습니다.
- 데이터에 기간 정보가 없으므로 연간 이직률로 해석하지 않습니다.
- 분석 결과를 개인별 인사 조치의 근거로 사용하지 않습니다.

## 3. 데이터 출처 및 구성

| 항목 | 내용 |
|---|---|
| 데이터셋 | [IBM HR Analytics Employee Attrition & Performance](https://www.kaggle.com/datasets/pavansubhasht/ibm-hr-analytics-attrition-dataset)(IBM 데이터 과학자가 만든 가상 데이터. [IBM/employee-attrition-aif360](https://github.com/IBM/employee-attrition-aif360)에도 같은 파일이 있습니다) |
| 규모 | 1,470행, 35열 |
| 타깃 | `Attrition`(Yes 237명, No 1,233명) |
| 품질 점검 | 결측치 0, 완전 중복 행 0, `EmployeeNumber` 중복 0, 상수형 변수 3개(`EmployeeCount`, `Over18`, `StandardHours`) |
| 전처리 | 상수형 변수 3개를 제거하고 파생변수 2개(`TenureGroup`, `AttritionBinary`)를 추가했습니다(35열 → 34열, 행 삭제 없음). IQR 이상치 후보는 실제 값일 수 있어 삭제하지 않았습니다. |

**라이선스(데이터와 코드는 따로 적용됩니다):**

| 대상 | 라이선스 |
|---|---|
| 직접 작성한 코드(`dashboard/`, Notebook의 코드, SQL 쿼리 등) | [MIT License](LICENSE) |
| 원본 CSV `data/raw/hr.csv` | 데이터베이스 [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/), 개별 내용 [DbCL 1.0](https://opendatacommons.org/licenses/dbcl/1-0/) |
| 전처리 CSV `data/processed/hr_preprocessed.csv` | 원본의 파생 데이터베이스로 보고 ODbL 1.0으로 배포. 전처리 방법은 `notebooks/02_data_preprocessing.ipynb`, `dashboard/core/preprocessing.py` |
| 학습 모델 `models/best_rf_optuna.pkl` | 라이선스상 성격이 확정되지 않아 저장소에 포함하지 않음(Git 추적 해제. 이전 커밋에는 남아 있음) |
| 그래프, 화면 캡처, 보고서, Notebook 출력 | 위 데이터에서 만든 결과물. MIT가 적용되지 않으며 아래 데이터 출처 고지를 따름 |

> Contains information from the [IBM HR Analytics Employee Attrition & Performance](https://www.kaggle.com/datasets/pavansubhasht/ibm-hr-analytics-attrition-dataset) dataset (also published in [IBM/employee-attrition-aif360](https://github.com/IBM/employee-attrition-aif360)), which is made available here under the [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/). Individual contents are licensed under the [Database Contents License (DbCL) 1.0](https://opendatacommons.org/licenses/dbcl/1-0/).

- 위 데이터 라이선스 표기는 IBM 공식 저장소와 Kaggle의 표기를 따른 것입니다. IBM 저장소는 데이터 출처를 Kaggle로 밝히며, IBM이 처음 배포한 곳의 이용 조건은 확인하지 못했습니다.
- IBM 저장소의 Apache License 2.0은 그 저장소의 코드에 대한 것이며 데이터에는 적용되지 않습니다.
- 자세한 내용은 [data/README.md](data/README.md)와 [DATASET_REVIEW.md](DATASET_REVIEW.md)에 있습니다. 법률 자문이 아니라 공개 자료를 대조한 기록입니다.

## 4. EDA 및 통계 분석

Notebook: [`03_eda.ipynb`](notebooks/03_eda.ipynb), [`04_statistical_analysis.ipynb`](notebooks/04_statistical_analysis.ipynb)

| 관점 | 가장 높은 집단 | 비교 집단 |
|---|---|---|
| 초과근무 | 초과근무 30.53%(416명 중 127명) | 비초과근무 10.44% |
| 근속연수 | 0~1년 34.88% | 10년 초과 8.13% |
| 월 소득 사분위 | Q1(하위) 29.27% | Q4(상위) 10.33% |
| 연령대 | 25세 미만 39.18% | 35~44세 10.10% |
| 직무 | Sales Representative 39.76% | Research Director 2.50% |
| 부서 | Sales 20.63% | Research & Development 13.84% |
| 결혼 여부 | 미혼 25.53% | 이혼 10.09% |

| 부서·직무별 이직률 | 소득·근속별 이직률 |
|---|---|
| ![부서·직무별 이직률](assets/charts/eda_attrition_by_department_jobrole.png) | ![소득·근속별 이직률](assets/charts/eda_attrition_by_income_tenure.png) |

| 초과근무 여부별 이직률 | 연령대별 이직률 |
|---|---|
| ![초과근무 여부별 이직률](assets/charts/eda_attrition_by_overtime.png) | ![연령대별 이직률](assets/charts/eda_attrition_by_age_group.png) |

**04번 Notebook의 범위:**
- 연령대·성별·결혼 여부별 이직률을 계산해 비교한 **기술통계 분석**입니다.
- 카이제곱 검정, t-test 같은 추론통계 검정과 p-value는 포함하지 않았습니다.
- 따라서 집단 간 차이가 통계적으로 유의하다고 결론 내리지 않습니다.

## 5. SQL 분석

파일: [`05_sql_analysis.sql`](notebooks/05_sql_analysis.sql)(쿼리 16개), [`05_sql_analysis.ipynb`](notebooks/05_sql_analysis.ipynb)(SQL 파일을 읽어 실행)

**방법:**
- 원본 CSV를 SQLite 메모리 데이터베이스(`:memory:`)에 그대로 적재했습니다.
- 집계 내용: 데이터 점검, 전체·부서·성별·직무·초과근무·연령대·근속 구간별 이직률
- 모든 이직률은 분자와 분모를 함께 출력하고, 분모가 0이면 `NULL`을 반환합니다.

```sql
ROUND(100.0 * SUM(Attrition = 'Yes') / NULLIF(COUNT(*), 0), 2) AS attrition_rate
```

**교차 검증:** SQL 결과의 직원 수, 이직자 수, 이직률(소수 둘째 자리)이 pandas 분석과 보고서 표의 모든 비교 항목에서 같았습니다.

**SQL로 추가한 집계:**
- 현 직무 근속연수 구간별 이직률: 0~1년 27.91% → 10년 초과 6.41%
- 직무 × 초과근무 교차 이직률:
  - 9개 직무 중 8개에서 초과근무 집단의 이직률이 더 높았습니다. 예: Laboratory Technician 50.00% 대 15.74%
  - 예외는 Healthcare Representative(5.41% 대 7.45%)입니다.
  - 30명 미만인 4개 칸은 비율이 크게 흔들릴 수 있습니다.

## 6. 머신러닝 모델링 및 평가

Notebook: [`06_machine_learning.ipynb`](notebooks/06_machine_learning.ipynb)

**설정:**

| 항목 | 내용 |
|---|---|
| 문제 | 이직 여부 이진 분류. `Attrition`, `AttritionBinary`, `EmployeeNumber`는 입력에서 제외 |
| 분할 | 학습 1,176건 / 테스트 294건(80:20, `stratify=y`, `random_state=2020158011`) |
| 전처리 | Pipeline 안에서 수치형 StandardScaler, 범주형 OneHotEncoder(전처리 후 입력 변수 56개) |
| 튜닝 | Random Forest를 Optuna로 30회 탐색(Stratified 5-Fold, F1 최적화). 최적 교차검증 F1 0.5202 |

**테스트 결과:**

| 모델 | Accuracy | Precision | Recall | F1-score | ROC-AUC |
|---|---:|---:|---:|---:|---:|
| Logistic Regression | 0.8810 | 0.7143 | 0.4255 | **0.5333** | **0.8842** |
| Random Forest + Optuna | 0.8537 | 0.5476 | **0.4894** | 0.5169 | 0.8093 |

| 모델 성능 비교 | Logistic Regression 혼동행렬 |
|---|---|
| ![모델 성능 비교](assets/charts/ml_model_performance_comparison.png) | ![Logistic Regression 혼동행렬](assets/charts/ml_logistic_regression_confusion_matrix.png) |

**해석:**
- 이직 클래스가 16.12%인 불균형 데이터이므로 Accuracy만으로 판단하지 않았습니다.
- Logistic Regression이 F1과 ROC-AUC에서 높았습니다.
- Random Forest + Optuna는 Recall만 높았습니다(0.4255 → 0.4894).
- 튜닝한 모델이 모든 지표에서 나았던 것은 아니므로, 모델 선택은 이직자 탐지의 중요도와 오탐 비용을 함께 고려해야 합니다.
- 비교는 단일 학습/테스트 분할에 기반합니다.

## 7. SHAP 해석

Notebook: [`07_shap_analysis.ipynb`](notebooks/07_shap_analysis.ipynb)

**분석 대상:** 저장된 Random Forest 모델에 대해, 06번과 같은 테스트 데이터 294건의 SHAP 값을 계산했습니다.

| 상위 15개 변수(평균 절대 SHAP) | SHAP Summary Plot |
|---|---|
| ![SHAP 상위 15개 변수](assets/charts/shap_top15_feature_importance.png) | ![SHAP Summary Plot](assets/charts/shap_summary_plot.png) |

**주요 패턴:**

| 변수 | 패턴 |
|---|---|
| 초과근무 | `OverTime_Yes` 0.04719, `OverTime_No` 0.04688로 1·2위. 두 변수는 같은 원본 변수의 원-핫 인코딩이므로 하나의 초과근무 변수로 해석합니다. 초과근무 관측치는 모두 양의 SHAP 값이었습니다. |
| 월 소득 | 낮은 소득에서 양의 기여가 나타나고, 소득이 높을수록 기여도가 낮아졌습니다. |
| 스톡옵션 수준 | 가장 낮은 수준(0)에서만 양의 SHAP 값이 나타났습니다. |
| 연령 | 낮은 연령에서 양의 기여가 나타나는 비선형 패턴이었습니다. |

**재현성 점검과 수정:**
- 처음 작성한 07번 Notebook은 06번과 다른 분할(`random_state=42`)을 써서, SHAP용 테스트 데이터 294건 중 243건이 모델의 학습 데이터였습니다.
- 분할 설정을 06번과 같게 바꾸고 Notebook을 처음부터 다시 실행했습니다.
- **모델은 재학습하지 않았습니다.** 저장된 모델이 이미 06번에서 같은 분할로 학습되었기 때문입니다.
- 다시 실행한 결과 1~9위 순서는 같았고 10~15위 일부가 바뀌었습니다(보고서 9.4절).

**해석할 때 주의할 점:**
- SHAP은 학습된 모델의 예측 구조를 설명합니다. 변수의 인과적 영향을 입증하지 않습니다.
- 수치형 변수는 표준화되었으므로 Dependence Plot의 가로축은 원래 단위가 아닙니다.

## 8. Dashboard 주요 기능

Notebook의 분석 규칙을 코드(`dashboard/core/`)로 재현하고, 원하는 집단을 골라 다시 볼 수 있게 만든 Streamlit 대시보드입니다.

**구현 현황:**

| 화면 | 상태 | 내용 |
|---|---|---|
| Overview | 구현 | KPI 4개(전체 직원 수, 이직자 수, 재직자 수, 이직률), 부서별 이직률, 부서별 인원 구성, 부서별 상세 표 |
| Workforce Analysis | 구현 | 부서·성별 다중 선택 필터와 초기화 버튼, 필터 결과 요약, 연령대·근속연수·월 소득 사분위·초과근무·직무별 이직률, 직무 × 초과근무 덤벨 차트, 차트별 수치 표 |
| Machine Learning | 구현 | 모델 개요, 두 모델의 Accuracy·Precision·Recall·F1·ROC-AUC 비교, 혼동행렬, ROC Curve, Random Forest 변수 중요도, SHAP 전역 중요도, 주요 변수 4개의 SHAP 해석(변수 선택), 한계와 주의사항 |
| HR Insights | 구현 | 이직 현황 요약 KPI, 전사 평균 대비 주요 이직 관련 지표, 인사이트 4개(초기 근속, 연령·직무, 급여, 초과근무), 부서별 시사점, 데이터 근거와 영향 범위를 붙인 개선 제안 |

**Machine Learning 화면의 계산 방식:**
- **Random Forest + Optuna:** 저장된 모델(`models/best_rf_optuna.pkl`)을 해시 확인 후 그대로 씁니다. 다시 학습하지 않습니다.
- **Logistic Regression:** 06번은 기준 모델을 저장하지 않았습니다. 같은 분할과 설정으로 메모리에서만 다시 맞추고 파일로 저장하지 않습니다. 결과가 보고서·06번 Notebook 수치와 같은지 테스트로 확인합니다.
- **SHAP:** 07번과 같은 방식(TreeExplainer, 테스트 데이터 294건)으로 계산합니다. 상위 20개 값이 07번 Notebook에 저장된 표와 순서·소수 다섯째 자리까지 같은지 테스트로 확인합니다.
- **SHAP 해석:** 산점도의 가로축은 표준화 전 원래 값입니다. 설명 문장의 비율은 화면에서 계산한 SHAP 값으로 만듭니다.
- **표시하지 않는 것:** 개인별 이직 위험 점수와 실시간 예측은 표시하지 않습니다. 분류 기준(0.5)도 조정하지 않습니다.
- **첫 접속 시간:** SHAP 계산 때문에 첫 접속에 시간이 걸립니다(측정 환경에서 약 15초). 이후에는 캐시를 씁니다.

**HR Insights 화면의 구성:**
- 각 인사이트는 분석 결과, 실제 직원 수와 이직률, 해석, 실무 개선 제안, 분석의 한계 순서로 보여 줍니다.
- 문장 속 수치는 모두 데이터에서 계산하며, 보고서 4장·4.8절 표와 같은지 테스트로 확인합니다.
- 30명 미만 집단은 `※`로 표시하고, 인사이트 머리에 소집단 이름을 따로 적습니다.
- 제안은 관찰된 연관성에서 나온 검토 과제입니다. 개선 효과를 보장하지 않습니다.

**해석 보조 장치:**
- 30명 미만 집단은 흐리게 표시하고 이름 뒤에 `※`를 붙입니다. 이 기준은 화면 표시 기준이며 통계적 유의성 기준이 아닙니다.
- 전사 평균(16.12%) 기준선은 필터와 관계없이 유지합니다.
- 월 소득 사분위는 필터 전 전사 기준으로 나눈 구간을 그대로 씁니다.
- 통화 단위, 기간, 추세처럼 데이터에 없는 정보는 표시하지 않습니다.

**안전장치:**
- 대시보드는 데이터, Notebook, 보고서, 모델을 읽기만 합니다.
- 서버는 `127.0.0.1`에서만 접속을 받습니다.
- 데이터나 모델 파일이 없거나 검증에 실패하면 차트 대신 안내를 표시합니다. 이때 절대 경로는 표시하지 않고 파일 이름만 표시합니다.

### 화면

모든 캡처는 1440px 너비의 데스크톱 화면입니다.

**Overview**

![Overview 화면](docs/captures/stage3/c3_62_overview_unchanged.png)

**Workforce Analysis(Human Resources 부서 필터 적용)**
- 분석 대상 요약은 63명 · 이직 12명 · 19.05%입니다.
- 직무 차트는 남은 직무 2개만 표시합니다.
- 기준 점선은 전사 평균 16.12%입니다.

![Workforce 필터 적용 화면](docs/captures/stage3/c3_52_filters_updated_job_count.png)

**직무별 이직률과 직무 × 초과근무 교차 분석**

이 캡처는 필터를 추가하기 전에 찍었습니다. 차트 구성은 현재와 같습니다.

![직무 및 교차 분석](docs/captures/stage3/c3_41_jobs_desktop_full_title.png)

**Machine Learning**

![Machine Learning 화면](docs/captures/stage5/c5_00_ml_desktop.png)

| 혼동행렬과 ROC Curve | 변수 중요도와 SHAP |
|---|---|
| ![혼동행렬과 ROC Curve](docs/captures/stage5/c5_02_ml_confusion_roc.png) | ![변수 중요도와 SHAP](docs/captures/stage5/c5_03_ml_importance_shap.png) |

**HR Insights**

![HR Insights 화면](docs/captures/stage6/c6_01_insights_summary.png)

| 인사이트 카드(초기 근속) | 부서별 시사점과 개선 제안 |
|---|---|
| ![초기 근속 인사이트](docs/captures/stage6/c6_02_insight_tenure.png) | ![부서별 시사점과 개선 제안](docs/captures/stage6/c6_04_department_proposals.png) |

<details>
<summary>그 밖의 캡처(연령·근속·소득, 모바일, 데이터·모델 오류 안내)</summary>

연령대·근속연수·월 소득 사분위별 이직률입니다. 필터를 추가하기 전 화면입니다.

![연령·근속·소득 분석](docs/captures/stage3/c3_31_profile_desktop_full.png)

| 직무 × 초과근무 (390px) | 연령·근속 (390px) |
|---|---|
| ![모바일 교차 분석](docs/captures/stage3/c3_42_cross_mobile.png) | ![모바일 연령·근속](docs/captures/stage3/c3_32_profile_mobile.png) |

데이터 파일이 없을 때의 안내 화면입니다. 파일 이름만 표시하고 해결 방법을 안내합니다.

![데이터 오류 안내](docs/captures/stage4/c4_21_error_overview.png)

Machine Learning의 SHAP 해석·한계 부분, HR Insights의 초과근무 인사이트, 두 화면의 모바일(390px) 캡처, 모델 파일이 없을 때의 안내입니다.

![SHAP 해석과 한계](docs/captures/stage5/c5_04_ml_dependence_limits.png)

![초과근무 인사이트](docs/captures/stage6/c6_03_insight_overtime.png)

| Machine Learning (390px) | HR Insights (390px) |
|---|---|
| ![Machine Learning 모바일](docs/captures/stage5/c5_05_ml_mobile.png) | ![HR Insights 모바일](docs/captures/stage6/c6_05_insights_mobile.png) |

![모델 오류 안내](docs/captures/stage5/c5_06_ml_model_missing.png)

전체 캡처(2단계 18개, 3단계 23개, 4단계 2개, 5단계 7개, 6단계 6개, 7단계 2개)와 폴더 설명은 [`docs/captures/`](docs/captures/)에 있습니다. 2단계 C11 캡처만 [`dashboard/docs/captures/stage2/`](dashboard/docs/captures/stage2/)에 있습니다.
- 2·3단계 캡처 설명: [dashboard/docs/stage2_guide.md](dashboard/docs/stage2_guide.md), [stage3_guide.md](dashboard/docs/stage3_guide.md)
- 4단계 캡처: 위 Overview 오류 안내(`c4_21_error_overview.png`)와 같은 상황의 Workforce Analysis 화면(`c4_22_error_workforce.png`)
- 5·6단계 캡처: Machine Learning(`stage5/`), HR Insights(`stage6/`). 2026-11-27 headless Chrome에서 촬영했습니다.

</details>

## 9. 주요 분석 결과와 실무적 인사이트

| 관찰 | 근거 | 검토 과제(제안) |
|---|---|---|
| 입사 초기 이직률이 높다 | 근속 0~1년 34.88%, 현 직무 근속 0~1년 27.91% | 온보딩, 멘토링, 수습 기간 피드백 등 정착 지원. 초기 이탈이 집중되는 시점 추가 분석 |
| 초과근무 집단의 이직률이 높다 | 30.53% vs 10.44%. 9개 직무 중 8개에서 같은 방향. SHAP 1위 | 부서·직무별 초과근무 빈도와 업무 집중 여부 점검 |
| 소득 하위 구간의 이직률이 높다 | Q1 29.27% vs Q4 10.33%. SHAP에서 낮은 소득·낮은 스톡옵션 수준의 양의 기여 | 직무·직급·근속을 함께 고려한 보상 적정성과 경력 개발 기회 검토 |
| 특정 직무의 이직률이 높다 | Sales Representative 39.76%, Laboratory Technician 23.94% | 해당 직무의 업무 강도, 성과 목표, 보상 구조, 승진 경로 세부 진단 |
| 만족도가 낮은 집단의 이직률이 높다 | 직무 만족도 1점 22.84%, 근무 환경 만족도 1점 25.35% | 정기 설문과 팀 단위 면담으로 불만 요인 추적 |

위 과제는 관찰된 연관성에서 나온 검토 제안입니다. 해당 조치를 하면 이직이 줄어든다는 인과적 결론이 아닙니다.

**모델 활용 관점:**
- 현재 모델의 Recall은 0.43~0.49로, 실제 이직자의 절반 이상을 놓칩니다.
- 실무에 쓰려면 임계값 조정, 교차검증 기반 비교, 시간 기준 검증이 먼저 필요합니다.

## 10. 프로젝트 구조

명령은 모두 이 README가 있는 `hr_df` 폴더(프로젝트 루트)에서 실행합니다.

```text
hr_df/
├─ README.md                      이 문서
├─ DATASET_REVIEW.md              데이터 출처·라이선스 검토 기록
├─ requirements.txt               대시보드 실행 의존성
├─ requirements-dev.txt           실행 + 테스트(pytest)
├─ requirements-lock.txt          전체 의존성 고정 버전(Python 3.12)
├─ requirements-notebooks.txt     Notebook 실행용 의존성
├─ pytest.ini                     테스트 경로, import 경로 설정
├─ data/                          데이터와 안내(data/README.md)
│  ├─ raw/hr.csv                  원본 데이터(1,470행)
│  └─ processed/hr_preprocessed.csv  02번 Notebook의 전처리 결과
├─ LICENSE                        코드에 적용되는 MIT License(데이터·모델 제외)
├─ models/best_rf_optuna.pkl      06번 Notebook에서 저장한 Random Forest 모델(Git 추적 안 함, 로컬에서 생성)
├─ notebooks/                     분석 Notebook 01~07과 실행 안내(notebooks/README.md)
├─ reports/HR_Analytics_final_report.md  최종 분석 보고서
├─ assets/charts/                 README용 분석 그래프(Notebook에 저장된 출력에서 추출)
├─ docs/captures/                 대시보드 화면·테스트 캡처(stage2~stage6)
└─ dashboard/
   ├─ app.py                      진입점: 페이지 등록, 사이드바
   ├─ .streamlit/config.toml      테마, 로컬 전용 서버, 오류 상세 숨김
   ├─ core/                       데이터 계층(Streamlit 미사용): 로드, 검증, 전처리 재현, 집계, 모델 로더,
   │                              모델 평가·SHAP(evaluation.py), HR 인사이트 집계(insights.py)
   ├─ components/                 차트, 표, 필터, KPI·설명 카드, 스타일, 모델·인사이트 차트
   ├─ views/                      overview.py, workforce.py, machine_learning.py, hr_insights.py
   ├─ scripts/check_setup.py      환경·데이터·모델 점검
   ├─ tests/                      pytest 테스트 21개 파일
   └─ docs/                       단계별 구현 지시서와 변경 이력
```

**대시보드 의존 방향:** `app.py → views → components → core`

Overview·Workforce·HR Insights의 수치는 `core.analytics`와 `core.insights`, Machine Learning의 수치는 `core.evaluation`에서 나옵니다. 개발자용 상세 설명은 [dashboard/README.md](dashboard/README.md)에 있습니다.

**`assets/charts/` 그래프 출처:** Notebook에 저장된 출력 이미지를 바이트 그대로 추출했습니다. Notebook은 수정하거나 다시 실행하지 않았습니다.

| 파일 | 출처 |
|---|---|
| `eda_attrition_by_age_group.png` | `03_eda.ipynb` |
| `eda_attrition_by_department_jobrole.png` | `03_eda.ipynb` |
| `eda_attrition_by_income_tenure.png` | `03_eda.ipynb` |
| `eda_attrition_by_overtime.png` | `03_eda.ipynb` |
| `ml_model_performance_comparison.png` | `06_machine_learning.ipynb` |
| `ml_logistic_regression_confusion_matrix.png` | `06_machine_learning.ipynb` |
| `shap_top15_feature_importance.png` | `07_shap_analysis.ipynb` |
| `shap_summary_plot.png` | `07_shap_analysis.ipynb` |

첫 Notebook의 파일명은 공백으로 시작합니다(`notebooks/ 01_data_overview.ipynb`). 원본 보존 원칙에 따라 이름을 바꾸지 않았습니다.

## 11. 설치 및 실행 방법

Windows PowerShell 기준이며, 모든 명령은 `hr_df` 폴더에서 실행합니다.

**1. Python 3.12 가상환경 생성과 의존성 설치**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Windows에서 긴 경로 지원이 꺼져 있으면(기본값), 프로젝트 폴더의 절대 경로가 85자 이내인 위치를 쓰세요. Streamlit 패키지 내부 경로가 길어서 더 깊은 위치에서는 설치가 `WinError 206`으로 실패할 수 있습니다.

**2. 데이터 확인**

필요한 파일은 `data/raw/hr.csv`, `data/processed/hr_preprocessed.csv`, `models/best_rf_optuna.pkl`입니다. 파일이 없을 때의 준비 방법은 [data/README.md](data/README.md)에 있습니다.

두 CSV는 저장소에 들어 있지만 모델 파일은 들어 있지 않습니다. 모델이 없으면 `check_setup.py`는 모델 항목에서 `[WARN]`을 표시하고 `RESULT: PASS`로 끝납니다(환경·데이터 문제만 `FAIL`). Machine Learning 화면은 준비 방법 안내를 표시하고, 모델이 필요한 테스트는 건너뜁니다. 나머지 세 화면은 두 CSV만으로 실행됩니다. 모델은 `notebooks/06_machine_learning.ipynb`로 만들 수 있지만, 다시 학습한 모델은 해시가 달라 `check_setup.py`에서 `[WARN]`(Machine Learning 화면 사용 불가)이 되고 모델 테스트가 실패할 수 있습니다.

```powershell
.\.venv\Scripts\python.exe dashboard\scripts\check_setup.py
```

마지막 줄이 `RESULT: PASS`이면 준비가 끝난 것입니다. `[WARN] 모델` 줄이 있으면 Machine Learning 화면만 사용할 수 없습니다.

**3. 대시보드 실행**

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard\app.py
```

브라우저는 자동으로 열리지 않습니다. 브라우저에서 `http://127.0.0.1:8501`에 접속하고, 종료는 터미널에서 `Ctrl+C`입니다.

저장된 모델은 scikit-learn 1.6.1에서만 로드하도록 고정되어 있으므로, 다른 Python 환경으로 실행하지 마세요.

**4. Notebook 실행(선택)**

Notebook은 Matplotlib, Seaborn, Optuna, JupyterLab이 추가로 필요합니다. 대시보드 환경과 분리하기 위해 별도 가상환경을 권장합니다.

```powershell
py -3.12 -m venv .venv-notebooks
.\.venv-notebooks\Scripts\python.exe -m pip install -r requirements-notebooks.txt
.\.venv-notebooks\Scripts\python.exe -m jupyter lab --notebook-dir notebooks
```

**02번과 06번은 실행하면 데이터·모델 파일을 덮어씁니다.** 실행 순서와 주의사항은 [notebooks/README.md](notebooks/README.md)에 있습니다.

## 12. 테스트 및 품질 검증

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

**2026-11-27 실행 결과:**

| 환경 | 결과 |
|---|---|
| 데이터·모델이 있는 이 프로젝트 | **325 passed**(skip 0, 실패 0) |
| 새로 clone한 상태(두 CSV 포함, 모델 없음) | 276 passed, 49 skipped(실패 0). skip은 모두 모델이 필요한 테스트 |

**테스트 구성:**

| 구분 | 테스트 파일 | 테스트 수 | 검증 내용 |
|---|---|--:|---|
| 데이터·분석 | `test_analytics`, `test_data`, `test_modeling`, `test_setup`, `test_regression_*` | 167 | 로드·검증·집계, 원본과 전처리 데이터 대조, 보고서 표와 Notebook 출력 수치 대조, 모델 해시 |
| Overview | `test_stage2_*` (4개) | 34 | 테마 색·대비, 사이드바, KPI, 부서별 차트·표 |
| Workforce | `test_stage3_*` (5개) | 41 | 메뉴, 공통 차트, Workforce 분석, 직무·교차 분석, 필터 21개 조합 |
| SQL | `test_sql_analysis` | 17 | SQL 쿼리 16개 실행, pandas 집계·보고서 표·Notebook 출력과 대조, 분모 0 처리 |
| 공개 준비 | `test_error_privacy`, `test_data_requirements` | 30 | 오류 화면의 절대 경로 미노출, 데이터·모델 의존 테스트 구분 |
| Machine Learning | `test_stage5_ml` | 24 | 두 모델 지표를 보고서·06번 Notebook과 대조, 혼동행렬·ROC 일관성, SHAP 값을 07번 Notebook·보고서와 대조, 보고서 7.3절 해석 방향, 모델 파일 누락·변조 시 오류 안내 |
| HR Insights | `test_stage6_insights` | 12 | 인사이트 집계를 보고서 4장·4.8절 표와 대조, 문장 속 수치, 소집단 표시, 인과 단정 표현 금지, 데이터 오류 안내 |
| 합계 | 21개 파일 | **325** | |

**데이터·모델 파일과 테스트:**
- 데이터·모델이 필요한 테스트에는 `requires_data`·`requires_model` 표시가 있어, 파일이 없으면 그 테스트만 건너뜁니다.
- 파일 자리에 디렉터리가 있거나 파일이 손상되었으면 건너뛰지 않고 실패합니다.
- `--require-data`를 붙이면 파일이 없을 때도 실패로 처리합니다.
- 테스트가 끝나면 `data/`, `models/`, `notebooks/`, `reports/`의 파일이 바뀌지 않았는지 해시로 확인합니다.

**그 밖의 검증:**
- `check_setup.py`는 Python 버전과 패키지, 데이터 파일 존재, 원본과 전처리 데이터의 일치(필수, 실패하면 `FAIL`), 모델 해시(선택, 실패하면 `WARN`)를 점검합니다.
- 대시보드 네 화면은 headless Chrome(1440px, 390px)에서 표시, 사이드바 이동, 필터 동작, 콘솔·서버 오류를 확인했습니다.

## 13. 프로젝트 한계와 향후 개선 방향

**한계:**
- **데이터:** IBM이 만든 가상 샘플 데이터라 실제 기업을 대표하지 않습니다. 기간 정보가 없어 시간에 따른 변화나 연간 이직률을 분석할 수 없습니다.
- **통계:** 집단별 비교와 SQL 집계는 기술통계입니다. 다른 변수를 통제하지 않았고 추론통계 검정을 하지 않았습니다.
- **모델:**
  - 비교가 단일 학습/테스트 분할에 기반합니다.
  - 튜닝한 Random Forest의 테스트 F1이 기준 모델보다 낮았습니다.
  - 두 모델 모두 Recall이 0.5 미만입니다.
- **SHAP:** 모델의 예측 구조를 설명할 뿐, 인과관계를 입증하지 않습니다.
- **대시보드:**
  - Machine Learning 화면은 분류 기준 조정, 민감도 분석, Precision-Recall Curve를 제공하지 않습니다.
  - 첫 접속 때 SHAP 계산 시간이 걸립니다.
- **재현성:**
  - Notebook 01~04·06의 저장된 출력은 이전 실행 결과이며, 그때의 패키지 버전은 기록되어 있지 않습니다.
  - 06번을 다시 실행하면 다른 모델이 저장될 수 있습니다.
- **라이선스:** 데이터 라이선스는 배포처 표기를 따른 것으로, IBM이 처음 배포한 곳의 조건은 확인하지 못했습니다. 모델 파일의 라이선스상 성격은 확정되지 않았습니다.

**향후 개선 방향:**

| 과제 | 상태 |
|---|---|
| 대시보드 Machine Learning 화면(모델 성능, SHAP 해석) | 완료 |
| 대시보드 HR Insights 화면(인사이트, 개선 제안) | 완료 |
| Machine Learning 화면의 민감도 분석, 분류 기준 조정 | 미착수 |
| 추론통계 검정과 효과크기 추가 | 미착수 |
| 분류 임계값 조정, Precision-Recall Curve, 교차검증 기반 모델 비교 | 미착수 |
| 데이터 출처·라이선스 고지, 코드 라이선스(MIT) | 완료 |
| 최초 배포처 이용 조건, 모델 파일의 라이선스상 성격 확인 | 미확인 |
| 실제 기업 데이터 확보 시 외부 검증 | 해당 없음(데이터 없음) |
