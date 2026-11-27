# dashboard — 개발자 안내

대시보드 코드를 수정하거나 기능을 추가하는 개발자를 위한 문서입니다.
프로젝트 소개, 화면 캡처, 설치 절차는 [최상위 README](../README.md)에 있습니다.

## 실행과 점검

명령은 모두 저장소 루트 폴더의 PowerShell에서 실행합니다. 설치는 [최상위 README의 실행 방법](../README.md#11-설치-및-실행-방법)을 따릅니다.

```powershell
.\.venv\Scripts\python.exe dashboard\scripts\check_setup.py      # 환경·데이터·모델 점검, RESULT: PASS
.\.venv\Scripts\python.exe -m streamlit run dashboard\app.py     # http://127.0.0.1:8501
.\.venv\Scripts\python.exe -m pytest -q                          # 전체 테스트
```

- 브라우저는 자동으로 열리지 않습니다(`headless = true`). 서버는 `127.0.0.1`에만 묶여 있습니다.
- 화면에 처리하지 못한 예외가 생기면 예외 종류만 표시됩니다(`showErrorDetails = "type"`). 상세 traceback은 실행한 터미널에서 확인합니다.
- 저장된 모델은 scikit-learn 1.6.1에서만 로드하므로 반드시 `.venv`의 Python으로 실행합니다.

## 화면 구조

| 주소 | 화면 | 파일 | 내용 |
|---|---|---|---|
| `/` | Overview | `views/overview.py` | KPI 4개, 부서별 이직률·인원 구성 차트, 부서별 상세 표. 필터 없음 |
| `/workforce` | Workforce Analysis | `views/workforce.py` | 부서·성별 필터, 요약 문구, 연령·근속·소득·초과근무 2열 카드, 직무별 이직률, 직무 × 초과근무 |
| `/machine-learning` | Machine Learning | `views/machine_learning.py` | 모델 개요 KPI, 두 모델 지표 표·차트, 혼동행렬 2개, ROC Curve, Random Forest 변수 중요도, SHAP 전역 중요도, 주요 변수 SHAP 해석(변수 선택), 한계 |
| `/hr-insights` | HR Insights | `views/hr_insights.py` | 요약 KPI, 전사 평균 대비 지표(발산형 막대), 인사이트 카드 4개, 부서별 시사점, 개선 제안 표. 필터 없음 |
| `/overview` | (숨김) | `app.py` | 2단계에서 안내한 주소. `st.switch_page`로 `/`에 보냄 |

`app.py`는 `st.navigation(..., position="hidden")`으로 페이지를 등록하고, 사이드바는 `components/navigation.py`가 직접 그립니다.
현재 화면은 링크 대신 `aria-current="page"` 요소로 표시합니다. 네 화면 모두 구현되어 나머지 세 화면이 링크로 표시됩니다(5·6단계에서 “준비 중” 배지 제거).

Workforce 화면의 구성 순서는 다음과 같습니다.

1. 제목 → 필터(부서, 성별) → “필터 초기화” 버튼
2. 요약 문구: `필터 부서 1/3 · 성별 2/2 · 분석 대상 63명(전체 1,470명 중) · 이직 12명 · 이직률 19.05%`
3. 선택 결과가 0명이면 안내 문구 하나만 표시하고 차트는 그리지 않음
4. “연령·근속·보상”: 연령대 | 근속연수, 월 소득 구간 | 초과근무(각 2열, 좁으면 1열)
5. 월 소득 구간 아래 각주: 전사 기준 구간 범위
6. “직무”: 직무별 이직률(이직률 순), 직무 × 초과근무 덤벨 차트
7. 해석 주의 각주

## 데이터 흐름

```text
data/raw/hr.csv ───────────┐
                           ├─ core/data.load_verified_data()   원본·전처리 스키마 검증, 원본 대조
data/processed/hr_preprocessed.csv ┘
          │
          ▼
core/analytics.add_analysis_groups()   AgeGroup, IncomeGroup(전사 사분위), TenureGroup 순서 지정
          │
          ▼
components/data_access.get_analysis_data()   st.cache_data. 두 CSV의 수정 시각·크기가 캐시 키
          │
          ├─ Overview: summarize_attrition(전체) → kpi, department
          │
          └─ Workforce: filters.apply_filters(전체, 선택) → df
                ├─ summarize_attrition(df)      요약 문구, 표의 “전체” 행
                ├─ summarize_attrition(전체)    점선(전사 평균 16.12%), 교차 차트 설명 문구
                └─ group_table(df, 컬럼) / cross_table(df) → 차트·표
```

- `core`는 Streamlit을 import하지 않습니다. 의존 방향은 `app → views → components → core`입니다.
- 데이터 로드나 검증에 실패하면 `DashboardError`가 발생하고, 화면은 `layout.load_error`로 오류 안내를 보여 줍니다.
  - 화면의 오류 문장은 `layout.public_message`가 절대 경로(Windows, UNC, POSIX, `~/`)를 파일 이름으로 바꾼 것입니다. 해결 방법 안내가 함께 표시됩니다.
  - 원래 메시지(전체 경로 포함)는 서버 로그(`components.layout` 로거, ERROR)에 남습니다.
- 모델 분할(`core/modeling.split_dataset`)에는 구간을 추가하지 않은 `load_verified_data()` 결과를 씁니다.

Machine Learning 화면의 흐름입니다.

```text
components/model_access.get_model_report()   st.cache_data. 두 CSV와 모델 파일의 수정 시각·크기가 캐시 키
   ├─ core/data.load_verified_data()
   ├─ core/modeling.load_model()            SHA256 확인 후 로드(재학습 없음)
   └─ core/evaluation.build_report(model, split_dataset(df))
         ├─ evaluate_models()   LR(메모리에서만 재현, 저장 안 함)·RF 지표, 혼동행렬, ROC
         ├─ shap_explanation()  TreeExplainer, 테스트 294건, 이직 클래스
         └─ impurity_importance(), shap_importance()
```

- 모델 파일이 없거나 해시가 다르면 `ModelLoadError` → `layout.load_error`가 모델 전용 안내(`MODEL_HINT`)를 표시합니다.
- HR Insights는 `data_access.get_analysis_data()` 결과(전체 데이터)를 `core/insights.py`로 집계합니다.

## 모듈

### core

| 파일 | 역할 |
|---|---|
| `config.py` | 경로(파일 위치 기준), 연령·근속 구간 경계, 소득 사분위 이름, 분할 seed, 모델 SHA256, `SMALL_SAMPLE_THRESHOLD = 30` |
| `schema.py` | 컬럼, 범주 허용값(`CATEGORIES`), 정수 범위 |
| `data.py` | CSV 읽기(`utf-8-sig`), 열 개수 불일치 감지, 검증 호출 |
| `validation.py` | 스키마·값 범위·관계 검증, 원본과 전처리 데이터 대조 |
| `preprocessing.py` | 02번 Notebook 전처리 규칙을 메모리에서 재현(파일 저장 없음) |
| `analytics.py` | `add_analysis_groups`, `summarize_attrition`, `attrition_by`, `compare_by_attrition` |
| `modeling.py` | 해시를 확인한 뒤 모델 로드, 테스트 데이터 분할 재현 |
| `evaluation.py` | 06·07번 재현: 두 모델 평가(`evaluate_models`), 불순도 중요도, SHAP 계산·순위, 변수별 SHAP(`dependence_frame`), 화면용 묶음 `build_report` |
| `insights.py` | HR Insights 집계: 전사 평균 대비 지표(`risk_table`), 회사·현 직무 근속 비교, 직무별 초과근무 격차, 부서 프로필, 소득 중앙값 |
| `exceptions.py` | `DashboardError`, `DataLoadError`, `DataValidationError` 등 |

### components

| 파일 | 역할 |
|---|---|
| `theme.py` | 색 토큰(`COLORS`), Plotly 공통 스타일(`style_figure`), `PLOTLY_CONFIG`, CSS 적용 |
| `styles.css` | 전역 스타일, 사이드바 메뉴, KPI 그리드, 2열 카드(`grid_` 컨테이너), 반응형 규칙 |
| `navigation.py` | 사이드바 메뉴 |
| `layout.py` | `page_header`, `section_header`, `footnote`, `load_error`, `public_message`(오류 문장에서 절대 경로 제거) |
| `data_access.py` | 1단계 로더에 Streamlit 캐시 연결 |
| `formatting.py` | `count`(천 단위 쉼표), `percent`(소수 둘째 자리, 값이 없으면 “—”) |
| `kpi.py` | Overview KPI 카드 HTML(모든 값 escape) |
| `department.py` | Overview 부서별 이직률·인원 구성 차트, 상세 표, 30명 미만 부서 경고 |
| `group_chart.py` | 집단별 이직률 공통 부품: `group_table`, `rate_figure`, `axis_labels`, `table_html` |
| `cross_chart.py` | 직무 × 초과근무: `cross_table`, `role_order`, `cross_figure`, `table_html`, `render` |
| `filters.py` | `render_filters`, `apply_filters`, `reset_filters`, `describe` |
| `model_access.py` | 모델 평가·SHAP 결과에 Streamlit 캐시 연결 |
| `model_charts.py` | 지표 표(높은 값 ▲ 표시)·묶음 막대, 혼동행렬, ROC, 중요도 막대, SHAP 산점도 |
| `insight_charts.py` | 전사 평균 대비 발산형 막대, 근속 비교 묶음 막대, 직무 규모·이직률 산점도 |
| `cards.py` | 요약 박스(`callout`), 목록 카드, 인사이트 카드(`Insight`: 분석 결과·해석·제안·한계) |

색 토큰 `series-1`(#2F62A8)과 `series-2`(#199E70)는 두 계열 구분색입니다(LR·RF, 회사·현 직무 근속). dataviz 검사 기준(명도 대역, 채도, 색각이상 ΔE, 흰 배경 대비)을 통과한 조합입니다.

`group_chart.render_section`은 3단계 작업 2에서 만든 함수입니다. 필터의 전사 평균 기준선 결정 이후 Workforce는 `views/workforce.py`의 `_section`을 쓰므로 현재 화면에서는 호출하지 않습니다.

## 분석 로직

| 항목 | 구현 |
|---|---|
| 이직률 | `attrition_by`: 집단별 `AttritionBinary` 합 ÷ 인원 × 100. 반올림은 `formatting.percent`에서만 |
| 0명 집단 | `summarize_attrition`의 이직률은 0%가 아니라 `None`, 화면에는 “—” |
| 연령대 | `pd.cut(Age, [0, 25, 35, 45, 55, inf), right=False)` |
| 근속 구간 | 전처리 데이터의 `TenureGroup`(0-1, 2-3, 4-5, 6-10, Over 10 Years) |
| 월 소득 사분위 | `pd.qcut(MonthlyIncome, 4)`을 **필터 전 전체 데이터**에 적용. `apply_filters`는 행만 고르고 구간을 다시 만들지 않음 |
| 정렬 | 기본은 범주의 자연 순서. 직무는 이직률 내림차순, 같으면 인원 내림차순(안정 정렬) |
| 소표본 | 인원 < 30이면 `is_small_sample`. 막대·점 투명도 0.45, 이름 뒤 `※`, 각주 |
| 기준선 | Workforce의 모든 점선은 `summarize_attrition(전체)`의 16.12%. 필터 결과는 요약 문구와 표의 “전체” 행 |
| 축 범위 | 막대 차트 `max(값, 기준선, 1.0) × 1.65`, 덤벨 차트 `× 1.15`. 모든 값이 0%여도 범위가 `[0, 0]`이 되지 않음 |
| 축 이름 | 16자를 넘으면 단어 경계에서 두 줄. `※`까지 포함한 길이로 판단 |
| 직무 설명 문구 | `f"{df['JobRole'].nunique()}개 직무를 …"`. 필터 후 남은 직무 수(예: HR만 선택 시 2개) |

## 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest -q                                       # 전체
.\.venv\Scripts\python.exe -m pytest dashboard\tests\test_stage3_filters.py -v   # 파일 하나
```

`pytest.ini`가 `dashboard`와 `dashboard/tests`를 import 경로에 넣으므로 저장소 루트에서 실행해야 합니다.

| 파일 | 내용 |
|---|---|
| `conftest.py` | 공용 fixture(`raw_df`, `analysis_df`, `model` 등), 테스트 전후 원본 파일 해시가 바뀌지 않았는지 확인, `requires_data`·`requires_model` marker와 `--require-data` 옵션 |
| `baselines.py` | 보고서 표와 Notebook 출력에서 기대 수치를 읽는 파서 |
| `test_setup.py`, `test_data.py`, `test_analytics.py`, `test_modeling.py` | 1단계: 환경, 로드·검증 실패 경로, 집계, 모델 |
| `test_regression_*.py` | 보고서 표, Notebook 출력, 모델 예측과 수치 대조 |
| `test_stage2_*.py` | 테마 색·대비, 사이드바, KPI, 부서별 차트·표 |
| `test_stage3_nav.py` | 메뉴, 현재 화면 표시, `/overview` 전환 |
| `test_stage3_group_chart.py` | 공통 차트: 0% 축, 소표본, 줄바꿈 |
| `test_stage3_workforce.py`, `test_stage3_jobs.py` | 연령·근속·소득, 직무·교차 분석 수치를 보고서·원본 CSV와 대조 |
| `test_stage3_filters.py` | 필터 적용, 초기화, 빈 선택, 기준선, 21개 필터 조합의 직무 수 |
| `test_sql_analysis.py` | `notebooks/05_sql_analysis.sql` 16개 쿼리를 메모리 SQLite에서 실행해 `core.analytics` 집계, 보고서 4.8 표, 05번 Notebook 출력과 대조 |
| `test_error_privacy.py` | 오류 화면에 절대 경로가 보이지 않는지(Windows·UNC·POSIX 경로, 실제 로더 예외), 서버 로그에는 원문이 남는지 |
| `test_data_requirements.py` | 데이터·모델 의존 테스트 구분 장치: marker 등록, 파일 판정, fixture 사용 테스트의 marker 부착 |
| `test_stage5_ml.py` | Machine Learning: 지표를 보고서·06번과 대조, 혼동행렬·ROC 일관성, SHAP을 07번·보고서와 대조, 보고서 7.3절 방향, 모델 누락·변조·데이터 누락 안내 |
| `test_stage6_insights.py` | HR Insights: 집계를 보고서 4장·4.8절 표와 대조, 문장 속 수치, 소집단 표시, 인과 단정 표현 금지, 데이터 오류 안내 |

**데이터·모델이 필요한 테스트:**
- `requires_data`(원본·전처리 CSV)와 `requires_model`(모델 파일) marker로 구분합니다.
- `raw_df`·`processed_df`·`analysis_df`·`split` fixture를 쓰면 `requires_data`, `model` fixture를 쓰면 `requires_model`이 자동으로 붙습니다. fixture 없이 파일을 직접 읽거나 화면에서 데이터를 불러오는 테스트에는 marker를 직접 붙입니다.
- 파일이 **없을 때만** 건너뜁니다(사유에 없는 파일의 상대 경로 표시). 파일이 있지만 손상되었거나 검증에 실패하면 건너뛰지 않고 실패합니다.
- `--require-data`를 주면 파일이 없을 때도 실패로 처리합니다(데이터가 있어야 하는 환경의 확인용).
- 모듈을 불러올 때 데이터 파일을 읽지 마세요. 데이터가 없는 환경에서 테스트 수집 자체가 중단됩니다. fixture에서 읽습니다.

보고서에 `직원 수 | 이직자 수 | 이직률`로 끝나는 표를 새로 넣으면 `test_regression_report.py`가 그 표를 4장 집단 표로 읽습니다. 그래서 보고서 4.8의 SQL 추가 표는 마지막 열을 다르게 두었습니다.

Workforce, Machine Learning, HR Insights는 `AppTest`가 함수형 페이지로 이동하지 못하므로 각 `render`를 직접 실행하는 하네스로 테스트합니다. 실제 페이지 이동은 브라우저에서 확인했습니다.

## 유지보수 시 주의사항

- **원본 보존:** `data/`, `models/`, `notebooks/`, `reports/`는 읽기만 합니다. 테스트가 이 파일들에서 기대 수치를 읽으므로, Notebook 출력을 지우거나 보고서 표 형식을 바꾸면 테스트가 실패합니다.
- **모델 해시:** 06번 Notebook을 다시 실행해 모델 파일이 바뀌면 로드가 거부됩니다. 해시를 바꾸지 말고 Git의 모델 파일과 비교합니다.
- **색:** `.streamlit/config.toml`과 `components/theme.py`의 색은 함께 바꿉니다. 테스트가 일치 여부와 대비를 검사합니다.
- **Streamlit 버전:** `styles.css` 일부가 Streamlit 내부 `data-testid`와 `st-key-*` 클래스를 사용합니다. `requirements-lock.txt`의 1.67.0을 유지하고, 올릴 때는 화면을 다시 캡처해 비교합니다.
- **필터 초깃값:** `st.multiselect`에 `default`를 주지 말고 `session_state.setdefault`를 유지합니다. 둘을 함께 쓰면 초기화 버튼을 누른 뒤 경고가 표시됩니다.
- **필터 상태:** 다른 화면에 다녀오면 Streamlit 기본 동작으로 필터가 전체 선택으로 돌아갑니다.
- **기준선:** Workforce 차트에 필터 결과의 평균을 점선으로 넘기지 않습니다. 기준선은 항상 전사 평균입니다.
- **소득 구간:** 필터 후 데이터로 `add_analysis_groups`를 다시 호출하지 않습니다.
- **하위 주소 직접 접속:** `/workforce`를 주소창에 직접 입력하면 Streamlit이 `/workforce/_stcore/health`와 `host-config`를 요청해 브라우저 콘솔에 404가 2건 남습니다. 화면 동작에는 영향이 없습니다.
- **Git:** `git add .`는 커밋되지 않은 07번 Notebook 변경까지 포함하므로 파일을 지정해서 추가합니다.
- **오류 메시지의 경로:** 사용자 화면에 예외 문장을 보일 때는 `layout.public_message`를 거칩니다. 경로를 화면에 그대로 출력하지 않습니다.

## 개발 원칙

- **해석:** 데이터에 없는 기간, 통화, 추세를 만들지 않고 연관성을 인과로 표현하지 않습니다. 예측 결과를 개인별 인사 조치의 근거로 제시하지 않습니다.
- **SHAP(5단계 구현):** `random_state=2020158011`의 테스트 데이터로 계산합니다. 07번 Notebook과 보고서 7장도 이 분할로 다시 계산되었습니다(보고서 9.4). 이전 결과는 `random_state=42` 분할에서 계산되어 294건 중 243건이 학습 데이터였습니다.
- **모델 표시(5단계 구현):** Logistic Regression과 Random Forest를 같은 표·차트에서 비교하고, 변수 중요도와 SHAP은 Random Forest 기준임을 표시합니다.
- **50회 반복 분할(미구현):** 참고용 민감도 분석으로, 구현할 때는 단일 테스트셋 평가와 분리해 표시합니다. 공식 교차검증 결과로 표현하지 않습니다.

## 단계별 문서

| 문서 | 내용 |
|---|---|
| [docs/stage2_guide.md](docs/stage2_guide.md) | 2단계: 디자인 시스템, 사이드바, Overview |
| [docs/stage3_guide.md](docs/stage3_guide.md) | 3단계: Workforce Analysis, 필터 |

각 가이드의 코드 블록은 작업 당시 지시 코드입니다. 이후 바뀐 부분은 각 가이드 끝의 “최종 상태와 변경 이력”에 기록했으며, 항상 실제 파일이 기준입니다.
