# HR Analytics Dashboard 3단계 구현 지시서 — Workforce Analysis

Workforce Analysis 화면과 필터를 작업 6개로 나눠 구현합니다. 2단계에서 미해결로 남긴 문제도 함께 처리합니다.

> **3단계 완료 후 안내:** 작업 0~6과 이후 수정까지 모두 끝났고, 최종 전체 테스트는 **239 passed**입니다.
> 작업 2·5의 코드 블록 일부(`group_chart.py`, `filters.py`, `workforce.py`와 그 테스트)는 작업 5의 결정 사항과 이후 수정으로 바뀌었습니다.
> 실제 파일이 기준이며, 바뀐 내용은 문서 끝의 [최종 상태와 변경 이력](#최종-상태와-변경-이력)에 있습니다.

## 목차

| 작업 | 내용 | 변경 파일 | 완료 시 전체 테스트 | 캡처 |
|---|---|--:|--:|---|
| [0](#작업-0-기준-저장과-시작-점검) | 기준 해시 저장(완료), 시작 점검 | 0 | 198 | — |
| [1](#작업-1-페이지-구조와-사이드바) | 페이지 구조, 현재 메뉴 표시, `/overview` 주소, KPI 높이 | 6 | 205 | C3-10~C3-13 |
| [2](#작업-2-집단별-이직률-공통-컴포넌트) | 집단별 이직률 공통 컴포넌트, 0% 기준선, 소표본 | 2 | 218 | C3-20 |
| [3](#작업-3-연령근속소득-분석) | 연령·근속·월 소득 분석 | 2 | 223 | C3-30~C3-32 |
| [4](#작업-4-직무초과근무교차-분석) | 초과근무·직무·직무×초과근무 분석 | 3 | 229 | C3-40~C3-43 |
| [5](#작업-5-필터) | 부서·성별 필터 | 3 | 236 | C3-50~C3-53 |
| [6](#작업-6-최종-점검과-승인-필요-항목) | 최종 점검, 승인 필요 항목 정리 | 0 | 236 | C3-60~C3-62 |

위 표의 테스트 수는 계획값입니다. 실제로는 작업 5에서 237, 작업 6 점검 시 238, 이후 수정 후 최종 239입니다([테스트 수 변화](#테스트-수-변화)).

## 범위와 규칙

**분석 범위:** 연령대, 직무, 월 소득 구간, 근속연수, 초과근무, 직무 × 초과근무.

**필터:** Workforce 화면에만 둡니다. Overview는 계속 전체 인원을 보여 줍니다.

**급여 사분위:** 필터 전 전사 데이터 기준을 유지합니다.

**소표본:** 30명 미만 집단은 흐리게 표시하고 이름 뒤에 `※`를 붙입니다.

**수정 허용 범위:**
- 작업 1에서만 2단계 파일 4개를 수정합니다: `dashboard/app.py`, `dashboard/components/navigation.py`, `dashboard/components/styles.css`, `dashboard/tests/test_stage2_shell.py`
- 그 밖에는 새 파일만 만듭니다. 예외는 작업 1에서 새로 만든 `dashboard/views/workforce.py`이며, 작업 3~5에서 전체 교체합니다.

**수정 금지:** `department.py`, `kpi.py`, `formatting.py`, `theme.py`, `core/`, 데이터, 모델, 노트북, 보고서, 2단계 가이드, 기존 캡처.

**진행 방식:** 한 작업의 테스트와 캡처를 마치고 승인을 받은 뒤 다음 작업으로 넘어갑니다. Git add, commit, reset, checkout은 쓰지 않습니다.

> **주의:** 2단계 가이드(`stage2_guide.md`)의 작업 3·4 코드는 이후 수정이 반영되지 않은 예전 코드입니다. 2단계 파일을 그 가이드에서 다시 복사하지 마세요.

## 완성 구조

```text
hr_df/dashboard/
├─ app.py                         [1] 수정: 페이지 등록, /overview 전환
├─ components/
│  ├─ navigation.py               [1] 수정: 현재 화면 표시(aria-current)
│  ├─ styles.css                  [1] 수정: 메뉴 강조, KPI 높이, 2열 배치
│  ├─ group_chart.py              [2] 새 파일: 집단별 이직률 차트·표
│  ├─ cross_chart.py              [4] 새 파일: 직무 × 초과근무
│  └─ filters.py                  [5] 새 파일: 부서·성별 필터
├─ views/
│  └─ workforce.py                [1] 새 파일 → [3]·[4]·[5] 전체 교체
└─ tests/
   ├─ test_stage2_shell.py        [1] 수정: 메뉴 기준 1개 테스트
   ├─ test_stage3_nav.py          [1]
   ├─ test_stage3_group_chart.py  [2]
   ├─ test_stage3_workforce.py    [3]
   ├─ test_stage3_jobs.py         [4]
   └─ test_stage3_filters.py      [5]
```

의존 방향은 `app → views → components → core` 한 방향입니다.

Workforce는 2단계의 `data_access`, `layout`, `formatting`, `theme`과 `core.analytics`를 재사용하고 계산 로직을 새로 만들지 않습니다.

## 설계 결정

| 항목 | 결정 | 이유 |
|---|---|---|
| 현재 메뉴 | 현재 화면은 링크 대신 `aria-current="page"` 요소로 표시하고, 흰색 3px 왼쪽 선과 배경으로 강조 | Streamlit 링크에는 현재 상태 속성이 없어 CSS로 고를 수 없음. 색만이 아닌 선 모양으로 구분 |
| `/overview` | 숨김 페이지가 `st.switch_page`로 `/`에 보냄 | 기본 페이지의 주소는 항상 `/`임 |
| 공통 차트 | 새 `group_chart.py`를 만들고 `department.py`는 그대로 둠 | 2단계 Overview를 바꾸지 않음. Overview는 필터가 없어 0% 문제가 생기지 않음 |
| 0% 기준선 | 축 끝을 `max(값, 전체, 1.0) × 1.65`로 계산 | 모두 0%여도 범위가 `[0, 0]`이 되지 않음 |
| 기준선 글자 | 기준선이 왼쪽 20% 안이면 글자를 오른쪽으로 펼침 | 0% 근처에서 글자가 잘리지 않음 |
| 소표본 | 막대·점은 투명도 0.45, 이름 뒤 `※`, 아래 각주 | 색에만 의존하지 않음 |
| 교차 분석 | 직무마다 두 점을 잇는 덤벨 차트. 빈 점은 없음, 채운 점은 있음 | 이직 강조색 하나만 쓰고 모양으로 구분해 디자인 규칙 유지 |
| 표 | 상세 수치는 “수치 표 보기”에 접어 둠. 비고 열 없이 이름 뒤 `※` | 6열이면 360px에서 표 안쪽 가로 스크롤이 생김 |
| 필터 | 부서, 성별 다중 선택. 기본값은 전체 | 페이지를 벗어나면 Streamlit이 선택을 초기화함(기본 동작) |

## 2단계 미해결 문제 처리

| 문제 | 처리 | 작업 |
|---|---|---|
| 모든 메뉴 링크가 선택된 것처럼 칠해짐 | 링크 배경 제거, 현재 화면만 강조 | 1 |
| `aria-current` 없음 | 현재 화면 요소에 `aria-current="page"` | 1 |
| `/overview` 접속 시 “Page not found” | 숨김 페이지로 `/`에 전환 | 1 |
| 330~340px에서 KPI 높이 차이 | `grid-auto-rows: 1fr` | 1 |
| 0% 기준선이 가운데에 그려짐 | 새 차트의 축 계산으로 해결. Overview는 필터가 없어 영향 없음 | 2 |
| README 갱신 | 승인 필요 항목으로 문안만 제시 → 3단계 완료 후 문서화 작업에서 갱신 | 6 |
| C11 위치, 2단계 가이드 갱신 | 승인 필요 항목으로 명령과 문안만 제시 → 문서화 작업에서 C11은 옮기지 않고 참조 경로를 바로잡았으며, 2단계 가이드에 변경 이력 추가 | 6 |

## 기존 테스트 변경 기록

`test_stage2_shell.py::test_only_overview_is_a_link` 하나만 바뀝니다. 테스트 함수 수는 그대로이며 단언은 지우지 않고 3단계 기준으로 바꿉니다.

| 이전 단언 | 새 단언 | 이유 |
|---|---|---|
| 링크 목록 == `["Overview"]` | 링크 목록 == `["Workforce Analysis"]` | 현재 화면(Overview)은 링크 대신 표시 요소가 됨 |
| (없음) | `<div class="hr-nav-current" aria-current="page">Overview</div>` 존재 | 현재 화면 표시를 대신 검증 |
| 이름 3개(Workforce, ML, Insights) 존재 | 이름 2개(ML, Insights) 존재 | Workforce가 구현됨 |
| `준비 중` 3개 | `준비 중` 2개 | 같은 이유 |
| 사이드바 HTML에 `<a ` 없음 | 유지 | 준비 중 메뉴는 여전히 링크가 아님 |

`test_no_filters_in_stage2`는 바꾸지 않습니다. Overview에는 필터가 없으므로 계속 통과하며, 필터가 Workforce에만 있다는 것을 지켜 줍니다.

## 데이터 검증 기준

| 대상 | 기준값 |
|---|---|
| 연령대 5행, 직무 9행, 소득 구간 4행, 근속 구간 5행, 초과근무 2행 | 최종 보고서 표와 표시 자릿수까지 일치 |
| 직무 × 초과근무 18칸 | 원본 CSV를 `csv` 모듈로 직접 집계한 값 |
| 필터 결과 | 원본 CSV에서 같은 조건으로 직접 집계한 값 |
| 소득 구간 범위 | 원본 CSV의 정렬된 소득에서 누적 인원 위치의 값 |

화면 수치는 모두 `core.analytics.attrition_by`에서 나오며, 반올림은 표시할 때만 합니다.

## 공통 사용법

명령은 `hr_df` 폴더의 PowerShell에서 실행합니다. 앱은 다음 명령으로 띄우고, 브라우저에서 `http://127.0.0.1:8501`에 접속합니다.

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard\app.py
```

화면 캡처는 2단계와 같이 DevTools 기기 툴바로 크기를 지정한 뒤 `Capture screenshot`을 씁니다.
캡처는 `docs/captures/stage3/`에 표의 파일명으로 저장합니다.
2단계에서 확인했듯 사이드바 접힘 상태가 저장되므로, 모바일 캡처 전에는 사이트 데이터를 지웁니다.

**보존 확인:** 각 작업이 끝날 때 실행합니다. `.pytest_tmp\stage3_baseline.csv`와 비교하며, 작업 1의 허용 파일 4개 외에는 변경이 없어야 합니다.

```powershell
$allowed = @('dashboard/app.py', 'dashboard/components/navigation.py', 'dashboard/components/styles.css', 'dashboard/tests/test_stage2_shell.py')
$root = (Get-Location).Path + '\'
$changed = @(Import-Csv .pytest_tmp\stage3_baseline.csv | Where-Object {
  -not (Test-Path -LiteralPath $_.Path) -or (Get-FileHash -LiteralPath $_.Path).Hash -ne $_.Hash
} | ForEach-Object { $_.Path.Replace($root, '').Replace('\', '/') })
$unexpected = @($changed | Where-Object { $_ -notin $allowed })
"changed: $($changed.Count), unexpected: $($unexpected.Count)"
$unexpected
```

작업 0에서는 `changed: 0`, 작업 1 이후에는 `changed: 4, unexpected: 0`이 정상입니다.

---

## 작업 0. 기준 저장과 시작 점검

### 지시

기준 해시는 가이드 작성 때 저장했습니다(`saved: 82`). **다시 실행하지 않습니다.** 아래 명령은 기록용이며, 파일이 이미 있으면 중단됩니다.

```powershell
$out = '.pytest_tmp\stage3_baseline.csv'
if (Test-Path $out) { throw 'stage3_baseline.csv already exists' }
$files = @(git ls-files --cached --others --exclude-standard | Where-Object { $_ -notlike 'dashboard/docs/stage3_guide.md' })
$rows = $files | ForEach-Object { Get-FileHash -Algorithm SHA256 -LiteralPath $_ }
$csv = $rows | ConvertTo-Csv -NoTypeInformation
$stream = [System.IO.File]::Open((Join-Path (Get-Location) $out), [System.IO.FileMode]::CreateNew)
$writer = New-Object System.IO.StreamWriter($stream, (New-Object System.Text.UTF8Encoding($true)))
$csv | ForEach-Object { $writer.WriteLine($_) }; $writer.Close()
"saved: $(@(Import-Csv $out).Count)"
```

### 테스트

```powershell
.\.venv\Scripts\python.exe dashboard\scripts\check_setup.py
.\.venv\Scripts\python.exe -m pytest -q
```

- [ ] `RESULT: PASS`, `198 passed`
- [ ] 보존 확인 `changed: 0, unexpected: 0`

---

## 작업 1. 페이지 구조와 사이드바

### 지시

| 파일 | 할 일 | 주의 |
|---|---|---|
| `app.py` | **2단계 파일 전체 교체.** Workforce 등록, `/overview` 전환, 기본 페이지 `url_path` 제거 | 계산 로직을 넣지 않음 |
| `components/navigation.py` | **2단계 파일 전체 교체.** 페이지 목록과 현재 페이지를 받아 표시 | 화면 이름은 escape |
| `components/styles.css` | **2단계 파일 전체 교체.** 메뉴 강조, KPI 높이, `grid_` 2열 배치 | 변경 내용은 아래 목록 참고 |
| `tests/test_stage2_shell.py` | **2단계 파일 전체 교체.** 위 “기존 테스트 변경 기록”의 1개 테스트만 바뀜 | 다른 테스트는 동일 |
| `views/workforce.py` | 새 파일. 제목과 데이터 연결 확인 | 작업 3에서 교체 |
| `tests/test_stage3_nav.py` | 새 파일 | |

`styles.css`의 변경점은 다음 네 가지이며, 나머지는 2단계와 같습니다.

1. 메뉴 링크의 배경을 없애고 마우스를 올렸을 때만 표시
2. `.hr-nav-current` 추가
3. 준비 중 메뉴의 왼쪽 여백 `36px` → `12px`로, 모든 메뉴의 글자 시작선 통일
4. `.hr-kpi-grid`에 `grid-auto-rows: 1fr`, `st-key-grid_` 2열 배치 추가

### 코드

#### 1-1. `dashboard/app.py` (2단계 파일 전체 교체)

```python
"""HR Analytics Dashboard 진입점. 실행: python -m streamlit run dashboard/app.py"""

from pathlib import Path

import streamlit as st

from components import navigation, theme
from views import overview, workforce

# :material/...: 파비콘은 Google 서버에 요청하므로 로컬 파일을 쓴다.
FAVICON = Path(__file__).parent / "components" / "favicon.svg"

st.set_page_config(
    page_title="HR Analytics",
    page_icon=str(FAVICON),
    layout="wide",
    initial_sidebar_state="auto",  # 데스크톱은 펼침, 모바일은 접힘
)
theme.apply_styles()

# 기본 페이지의 주소는 항상 "/"이므로 url_path를 주지 않는다.
overview_page = st.Page(overview.render, title="Overview", default=True)
workforce_page = st.Page(workforce.render, title="Workforce Analysis", url_path="workforce")


def _redirect_to_overview() -> None:
    # 2단계에서 안내한 /overview 주소로 들어와도 Overview를 보여 준다.
    st.switch_page(overview_page)


legacy_overview = st.Page(
    _redirect_to_overview, title="Overview", url_path="overview", visibility="hidden"
)
current_page = st.navigation(
    [overview_page, workforce_page, legacy_overview], position="hidden"
)
navigation.render_sidebar([overview_page, workforce_page], current_page)
current_page.run()
```

#### 1-2. `dashboard/components/navigation.py` (2단계 파일 전체 교체)

```python
"""왼쪽 사이드바."""

from collections.abc import Sequence
from html import escape

import streamlit as st
from streamlit.navigation.page import Page

# 구현 전 화면은 링크 없이 표시한다.
PLANNED_PAGES = ("Machine Learning", "HR Insights")


def render_sidebar(pages: Sequence[Page], current: Page) -> None:
    planned = "".join(
        f'<li><span>{escape(name)}</span><span class="hr-badge">준비 중</span></li>'
        for name in PLANNED_PAGES
    )
    with st.sidebar:
        st.html(
            '<div class="hr-brand"><strong>HR Analytics</strong>'
            "<span>Employee Attrition Dashboard</span></div>"
        )
        st.html('<div class="hr-nav-label">분석 메뉴</div>')
        for page in pages:
            if page.url_path == current.url_path:
                # 현재 화면은 링크 대신 표시만 하고, 보조기기에 현재 위치를 알린다.
                st.html(
                    f'<div class="hr-nav-current" aria-current="page">{escape(page.title)}</div>'
                )
            else:
                st.page_link(page, width="stretch")
        st.html(f'<ul class="hr-planned" aria-label="준비 중인 메뉴">{planned}</ul>')
        st.html(
            '<div class="hr-side-note">IBM HR Analytics 공개 샘플 데이터<br>'
            "실제 기업의 인력 현황이 아닙니다.</div>"
        )
```

#### 1-3. `dashboard/components/styles.css` (2단계 파일 전체 교체)

```css
/* 색은 theme.py의 토큰만 사용한다. */

/* 본문 */
[data-testid="stMainBlockContainer"] {
  max-width: 1280px;
  padding: 3.5rem 2rem 2rem;
}
[data-testid="stHeader"] { background: var(--page); }

/* 사이드바 */
/* 링크는 이동 가능한 화면이다. 현재 화면은 .hr-nav-current로만 강조한다. */
[data-testid="stSidebar"] [data-testid="stPageLink"] a {
  min-height: 44px;
  padding: 0 12px;
  border-radius: 8px;
}
[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover { background: var(--navy-raised); }
[data-testid="stSidebar"] [data-testid="stPageLink"] a p {
  color: var(--on-navy);
  font-size: 14px;
  font-weight: 500;
}
.hr-nav-current {
  display: flex;
  align-items: center;
  min-height: 44px;
  padding: 0 12px 0 9px; /* 3px 표시선 + 9px = 링크 글자 시작선 12px */
  border-left: 3px solid var(--on-navy);
  border-radius: 8px;
  background: var(--navy-raised);
  color: var(--on-navy);
  font-size: 14px;
  font-weight: 700;
}
[data-testid="stSidebar"] a:focus-visible {
  outline: 2px solid var(--on-navy);
  outline-offset: 2px;
}
[data-testid="stSidebarCollapseButton"] { visibility: visible; }
.hr-brand { padding: 0 4px 20px; color: var(--on-navy); }
.hr-brand strong { display: block; font-size: 20px; line-height: 1.4; }
.hr-brand span,
.hr-nav-label { color: var(--on-navy-muted); font-size: 12px; }
.hr-nav-label { padding: 0 12px; }
[data-testid="stSidebar"] ul.hr-planned { margin: 0; padding: 0; list-style: none; }
[data-testid="stSidebar"] ul.hr-planned li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-height: 44px;
  margin: 0;
  padding: 0 12px; /* 메뉴 글자 시작선 */
  color: var(--on-navy-muted);
  font-size: 14px;
}
.hr-badge {
  padding: 1px 8px;
  border: 1px solid var(--on-navy-muted);
  border-radius: 999px;
  font-size: 11px;
}
.hr-side-note {
  margin-top: 28px;
  padding: 16px 12px 0;
  border-top: 1px solid var(--navy-raised);
  color: var(--on-navy-muted);
  font-size: 12px;
  line-height: 1.7;
}

/* 제목 */
.hr-page-header h1 {
  margin: 0;
  padding: 0;
  color: var(--navy);
  font-size: 28px;
  font-weight: 700;
  line-height: 1.4;
}
.hr-page-header p,
.hr-section p,
.hr-footnote {
  margin: 4px 0 0;
  color: var(--ink-muted);
  font-size: 13px;
  line-height: 1.6;
}
.hr-section h2,
.hr-section h3 {
  margin: 0;
  padding: 0;
  color: var(--ink);
  font-weight: 700;
  line-height: 1.5;
}
.hr-section h2 { margin-top: 16px; font-size: 20px; }
.hr-section h3 { font-size: 15px; }

/* KPI: 4열, 2열, 1열 순으로 줄어 3+1 배치가 생기지 않는다. */
.hr-kpi-wrap { container-type: inline-size; width: 100%; }
.hr-kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  grid-auto-rows: 1fr; /* 보조 문구가 줄바꿈되어도 카드 높이를 맞춘다. */
  gap: 16px;
}
.hr-kpi {
  padding: 18px 20px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface);
}
.hr-kpi-label {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--ink-muted);
  font-size: 13px;
}
.hr-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--navy); }
.hr-dot--retained { background: var(--retained); }
.hr-dot--attrition { background: var(--attrition); }
.hr-kpi-value {
  margin-top: 6px;
  color: var(--ink);
  font-size: 30px;
  font-weight: 700;
  line-height: 1.4;
  white-space: nowrap;
}
.hr-kpi-unit { margin-left: 3px; font-size: 15px; font-weight: 500; }
.hr-kpi-note { color: var(--ink-muted); font-size: 12px; }
@container (max-width: 820px) {
  .hr-kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@container (max-width: 290px) {
  .hr-kpi-grid { grid-template-columns: minmax(0, 1fr); }
}

/* 카드: st.container(key="card_...") */
[class*="st-key-card_"] {
  padding: 18px 20px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface);
}
/* 사이드바를 뺀 본문이 좁으면 차트를 한 열로 내린다. */
.st-key-department_charts [data-testid="stHorizontalBlock"] { flex-wrap: wrap; }
.st-key-department_charts [data-testid="stColumn"] { min-width: min(100%, 380px); }
/* Workforce: st.container(key="grid_...") 안의 열도 좁으면 한 열로 내린다. */
[class*="st-key-grid_"] [data-testid="stHorizontalBlock"] { flex-wrap: wrap; }
[class*="st-key-grid_"] [data-testid="stColumn"] { min-width: min(100%, 380px); }

/* 표 */
.hr-table-scroll { width: 100%; overflow-x: auto; }
.hr-table {
  width: 100%;
  margin: 0;
  border-collapse: collapse;
  color: var(--ink);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}
.hr-table th,
.hr-table td {
  padding: 10px 8px;
  border: 0;
  border-bottom: 1px solid var(--border);
  text-align: right;
  white-space: nowrap;
}
.hr-table thead th { color: var(--ink-muted); font-weight: 600; }
.hr-table th:first-child { text-align: left; white-space: normal; }
.hr-table tfoot th,
.hr-table tfoot td { border-bottom: 0; font-weight: 700; }

@media (max-width: 640px) {
  [data-testid="stMainBlockContainer"] { padding: 3.5rem 1rem 1.5rem; }
  .hr-page-header h1 { font-size: 24px; }
  .hr-kpi-grid { gap: 10px; }
  .hr-kpi { padding: 12px; }
  .hr-kpi-value { font-size: 24px; }
  [class*="st-key-card_"] { padding: 14px 12px; }
  .hr-table { font-size: 12px; }
  .hr-table th,
  .hr-table td { padding: 8px 4px; }
}
```

#### 1-4. `dashboard/tests/test_stage2_shell.py` (2단계 파일 전체 교체)

```python
"""작업 2: 앱 셸, 사이드바, 오류 화면."""

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from components import data_access
from core import config, data
from core.exceptions import DataLoadError, DataValidationError

APP_PATH = config.PROJECT_ROOT / "dashboard" / "app.py"


@pytest.fixture(autouse=True)
def clear_cache():
    st.cache_data.clear()
    yield
    st.cache_data.clear()


def _run() -> AppTest:
    return AppTest.from_file(APP_PATH, default_timeout=30).run()


def _html(element) -> str:
    return "\n".join(item.proto.body for item in element.get("html"))


def test_app_runs():
    app = _run()
    assert not app.exception
    assert not app.error
    assert "<h1>Overview</h1>" in _html(app.main)


def test_favicon_is_local():
    source = APP_PATH.read_text(encoding="utf-8")
    assert 'page_icon=":material' not in source
    assert (APP_PATH.parent / "components" / "favicon.svg").is_file()


def test_only_overview_is_a_link():
    app = _run()
    # Stage 3: 현재 화면(Overview)은 aria-current 표시로 바뀌고 Workforce가 링크가 된다.
    links = app.sidebar.get("page_link")
    assert [link.proto.label for link in links] == ["Workforce Analysis"]

    sidebar = _html(app.sidebar)
    assert '<div class="hr-nav-current" aria-current="page">Overview</div>' in sidebar
    for name in ("Machine Learning", "HR Insights"):
        assert name in sidebar
    assert sidebar.count("준비 중</span>") == 2
    assert "<a " not in sidebar


def test_no_filters_in_stage2():
    app = _run()
    assert not app.selectbox
    assert not app.multiselect
    assert not app.slider


@pytest.mark.parametrize(
    "error",
    [DataLoadError("파일 없음: C:/data/hr.csv"), DataValidationError(["결측치 1건"])],
)
def test_data_error_shows_no_numbers(monkeypatch, error):
    def fail():
        raise error

    monkeypatch.setattr(data, "load_analysis_data", fail)
    app = _run()
    assert not app.exception
    assert len(app.error) == 1
    assert str(error) in app.code[0].value
    assert "1,470" not in _html(app.main)
    assert not app.success
    assert app.sidebar.get("page_link"), "오류가 나도 사이드바는 유지한다."


def test_cache_follows_file_version(monkeypatch):
    calls = []
    original = data.load_analysis_data

    def counted():
        calls.append(1)
        return original()

    monkeypatch.setattr(data, "load_analysis_data", counted)
    monkeypatch.setattr(data_access, "_file_version", lambda path: (1, 1))
    data_access.get_analysis_data()
    data_access.get_analysis_data()
    assert len(calls) == 1

    monkeypatch.setattr(data_access, "_file_version", lambda path: (2, 1))
    data_access.get_analysis_data()
    assert len(calls) == 2
```

#### 1-5. `dashboard/views/workforce.py` (새 파일)

```python
"""Workforce Analysis 화면."""

import streamlit as st

from components import data_access, layout
from core.exceptions import DashboardError


def render() -> None:
    layout.page_header("Workforce Analysis", "인력 특성별 이직 현황")
    try:
        df = data_access.get_analysis_data()
    except DashboardError as error:
        layout.load_error(error)
        return

    st.info(f"분석 대상 {len(df):,}명. 분석 차트는 다음 작업에서 추가합니다.")
```

#### 1-6. `dashboard/tests/test_stage3_nav.py` (새 파일)

```python
"""Stage 3 작업 1: 페이지 구조와 사이드바."""

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from components import theme
from core import config, data
from core.exceptions import DataLoadError

APP_PATH = config.PROJECT_ROOT / "dashboard" / "app.py"


@pytest.fixture(autouse=True)
def clear_cache():
    st.cache_data.clear()
    yield
    st.cache_data.clear()


def _workforce_app():
    # AppTest는 함수형 페이지로 이동할 수 없으므로 app.py와 같은 구성으로 Workforce를 연다.
    import streamlit as st

    from components import navigation, theme
    from views import overview, workforce

    theme.apply_styles()
    pages = [
        st.Page(overview.render, title="Overview", default=True),
        st.Page(workforce.render, title="Workforce Analysis", url_path="workforce"),
    ]
    st.navigation(pages, position="hidden")
    navigation.render_sidebar(pages, pages[1])
    workforce.render()


def _escaped_title_app():
    import streamlit as st

    from components import navigation
    from views import overview

    pages = [st.Page(overview.render, title="<b>Overview</b>", default=True)]
    st.navigation(pages, position="hidden")
    navigation.render_sidebar(pages, pages[0])


def _html(element) -> str:
    return "\n".join(item.proto.body for item in element.get("html"))


def test_overview_is_current_page():
    app = AppTest.from_file(APP_PATH, default_timeout=30).run()
    sidebar = _html(app.sidebar)
    assert not app.exception
    assert sidebar.count('aria-current="page"') == 1
    assert '<div class="hr-nav-current" aria-current="page">Overview</div>' in sidebar
    assert [link.proto.label for link in app.sidebar.get("page_link")] == ["Workforce Analysis"]


def test_workforce_is_current_page():
    app = AppTest.from_function(_workforce_app, default_timeout=30).run()
    sidebar = _html(app.sidebar)
    assert not app.exception
    assert sidebar.count('aria-current="page"') == 1
    assert '<div class="hr-nav-current" aria-current="page">Workforce Analysis</div>' in sidebar
    assert [link.proto.label for link in app.sidebar.get("page_link")] == ["Overview"]
    assert sidebar.count("준비 중</span>") == 2

    escaped = _html(AppTest.from_function(_escaped_title_app, default_timeout=30).run().sidebar)
    assert "&lt;b&gt;Overview&lt;/b&gt;" in escaped and "<b>Overview" not in escaped


def test_workforce_page_loads_data():
    app = AppTest.from_function(_workforce_app, default_timeout=30).run()
    assert not app.exception
    assert "<h1>Workforce Analysis</h1>" in _html(app.main)
    assert not app.error


def test_workforce_data_error(monkeypatch):
    def fail():
        raise DataLoadError("파일 없음")

    monkeypatch.setattr(data, "load_analysis_data", fail)
    app = AppTest.from_function(_workforce_app, default_timeout=30).run()
    assert not app.exception
    assert len(app.error) == 1
    assert "1,470" not in _html(app.main)
    assert app.sidebar.get("page_link"), "오류가 나도 사이드바는 유지한다."


def test_routes_in_app():
    source = APP_PATH.read_text(encoding="utf-8")
    assert 'url_path="workforce"' in source
    assert 'url_path="overview", visibility="hidden"' in source
    assert "st.switch_page(overview_page)" in source


def test_only_current_menu_is_highlighted():
    css = theme.CSS_PATH.read_text(encoding="utf-8")
    link_rule = css.split('[data-testid="stPageLink"] a {', 1)[1].split("}", 1)[0]
    assert "background" not in link_rule, "모든 링크를 선택된 것처럼 칠하지 않는다."
    current_rule = css.split(".hr-nav-current {", 1)[1].split("}", 1)[0]
    assert "border-left: 3px solid var(--on-navy)" in current_rule, "색 외의 선택 표시"


def test_kpi_rows_have_equal_height():
    css = theme.CSS_PATH.read_text(encoding="utf-8")
    grid_rule = css.split(".hr-kpi-grid {", 1)[1].split("}", 1)[0]
    assert "grid-auto-rows: 1fr" in grid_rule
```

### 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest dashboard\tests\test_stage3_nav.py -v
.\.venv\Scripts\python.exe -m pytest -q
```

- [ ] 새 테스트 `7 passed`, 전체 `205 passed`
- [ ] 보존 확인 `changed: 4, unexpected: 0`

### 브라우저 확인

- [ ] Overview: 현재 메뉴만 흰색 왼쪽 선과 배경, Workforce는 링크
- [ ] Workforce 클릭 시 주소 `/workforce`, 현재 메뉴가 Workforce로 바뀜
- [ ] `http://127.0.0.1:8501/overview` 접속 시 “Page not found” 없이 `/`로 바뀜
- [ ] 메뉴 4개의 글자 시작선이 같음
- [ ] 330px, 340px에서 KPI 카드 높이가 행마다 같음

### 캡처

| ID | 파일명 | 크기 | 보여야 할 것 |
|---|---|---|---|
| C3-10 | `c3_10_nav_test.png` | 터미널 | 205 passed |
| C3-11 | `c3_11_nav_overview.png` | 1440×900 | Overview 강조, Workforce 링크, 준비 중 2개 |
| C3-12 | `c3_12_nav_workforce.png` | 1440×900 | Workforce 강조, 제목, 1,470명 안내 |
| C3-13 | `c3_13_kpi_340.png` | 340×900 | KPI 2×2, 행 높이 동일 |

---

## 작업 2. 집단별 이직률 공통 컴포넌트

### 지시

| 파일 | 할 일 | 주의 |
|---|---|---|
| `components/group_chart.py` | 집단별 표 계산, 이직률 막대 차트, 수치 표, 화면 섹션 | 계산은 `attrition_by`만 사용 |
| `tests/test_stage3_group_chart.py` | 보고서 대조, 0%, 소표본, 줄바꿈, escape | |

이 작업에서는 화면이 바뀌지 않습니다. 작업 3부터 이 컴포넌트를 씁니다.

### 코드

#### 2-1. `dashboard/components/group_chart.py` (새 파일)

```python
"""인력 특성별 이직률: 막대 차트, 수치 표, 화면 섹션."""

from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components import formatting, layout, theme
from core import analytics
from core.analytics import AttritionSummary

ROW_HEIGHT = 44
BAR_WIDTH = 0.5  # 행 높이 44px의 절반, 막대 두께 24px 이하
SMALL_OPACITY = 0.45
SMALL_MARK = "※"
SMALL_NOTE = "※ 30명 미만 집단은 흐리게 표시했습니다. 비율 차이를 해석할 때 주의하세요."


def wrap_label(text: str, width: int = 16) -> str:
    """긴 축 이름을 단어 경계에서 두 줄로 나눈다."""
    words = text.split(" ")
    if len(text) <= width or len(words) == 1:
        return text
    split = min(
        range(1, len(words)),
        key=lambda i: abs(len(" ".join(words[:i])) - len(" ".join(words[i:]))),
    )
    return " ".join(words[:split]) + "<br>" + " ".join(words[split:])


def group_table(df: pd.DataFrame, column: str, *, sort_by_rate: bool = False) -> pd.DataFrame:
    """집단별 직원·이직·재직 수와 이직률. 기본은 범주의 자연 순서다."""
    table = analytics.attrition_by(df, column)
    table["retained_count"] = table["employee_count"] - table["attrition_count"]
    table[column] = table[column].astype(str)
    if sort_by_rate:
        table = table.sort_values(
            ["attrition_rate", "employee_count"], ascending=False, kind="mergesort", ignore_index=True
        )
    return table


def axis_upper(rates: list[float], overall_rate: float) -> float:
    """이직률 축의 끝. 모든 값이 0%여도 범위가 [0, 0]이 되지 않는다."""
    return max([*rates, overall_rate, 1.0]) * 1.65


def axis_labels(table: pd.DataFrame, column: str) -> list[str]:
    return [
        wrap_label(name) + (f" {SMALL_MARK}" if small else "")
        for name, small in zip(table[column], table["is_small_sample"], strict=True)
    ]


def rate_figure(table: pd.DataFrame, column: str, overall_rate: float) -> go.Figure:
    rates = table["attrition_rate"].tolist()
    labels = axis_labels(table, column)
    upper = axis_upper(rates, overall_rate)
    figure = go.Figure(
        go.Bar(
            x=rates,
            y=labels,
            orientation="h",
            width=BAR_WIDTH,
            marker={
                "color": theme.COLORS["attrition"],
                "opacity": [SMALL_OPACITY if s else 1.0 for s in table["is_small_sample"]],
            },
            customdata=table[[column, "employee_count", "attrition_count"]].values.tolist(),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>이직률 %{x:.2f}%<br>"
                "이직 %{customdata[2]:,}명 / 전체 %{customdata[1]:,}명<extra></extra>"
            ),
        )
    )
    theme.style_figure(figure, height=70 + ROW_HEIGHT * len(table))
    figure.update_layout(barcornerradius=4, showlegend=False)
    figure.update_xaxes(range=[0, upper], visible=False)
    figure.update_yaxes(autorange="reversed")
    # 막대 끝에 숫자를 두면 전체 평균선과 겹치므로 오른쪽에 정렬한다.
    for label, rate in zip(labels, rates, strict=True):
        figure.add_annotation(
            xref="paper", x=1, y=label, text=formatting.percent(rate), xanchor="right", showarrow=False
        )
    figure.add_vline(
        x=overall_rate,
        line={"color": theme.COLORS["ink-muted"], "width": 1, "dash": "dash"},
        annotation={
            "text": f"전체 {formatting.percent(overall_rate)}",
            "font": {"color": theme.COLORS["ink-muted"]},
            "yanchor": "bottom",
            # 기준선이 왼쪽 끝 근처면 글자가 잘리지 않도록 오른쪽으로 펼친다.
            "xanchor": "left" if overall_rate / upper < 0.2 else "center",
            "y": 1.0,
        },
    )
    return figure


def row_label(name: str, small: bool) -> str:
    """표의 행 이름. 모바일 폭에 맞추려고 비고 열 대신 차트와 같은 ※ 표시를 붙인다."""
    return f"{escape(name)} {SMALL_MARK}" if small else escape(name)


def table_html(table: pd.DataFrame, column: str, header: str, summary: AttritionSummary) -> str:
    def cells(total: int, left: int, retained: int, rate: float | None) -> str:
        values = [*map(formatting.count, (total, left, retained)), formatting.percent(rate)]
        return "".join(f"<td>{escape(value)}</td>" for value in values)

    body = "".join(
        f'<tr><th scope="row">{row_label(str(getattr(row, column)), row.is_small_sample)}</th>'
        + cells(row.employee_count, row.attrition_count, row.retained_count, row.attrition_rate)
        + "</tr>"
        for row in table.itertuples()
    )
    total = cells(
        summary.employee_count,
        summary.attrition_count,
        summary.retained_count,
        summary.attrition_rate,
    )
    headers = "".join(
        f'<th scope="col">{escape(name)}</th>' for name in (header, "직원", "이직", "재직", "이직률")
    )
    return (
        '<div class="hr-table-scroll"><table class="hr-table">'
        f"<thead><tr>{headers}</tr></thead><tbody>{body}</tbody>"
        f'<tfoot><tr><th scope="row">전체</th>{total}</tr></tfoot>'
        "</table></div>"
    )


def render_section(
    df: pd.DataFrame,
    summary: AttritionSummary,
    *,
    column: str,
    title: str,
    header: str,
    description: str,
    key: str,
    sort_by_rate: bool = False,
) -> None:
    table = group_table(df, column, sort_by_rate=sort_by_rate)
    with st.container(key=f"card_{key}"):
        layout.section_header(title, description, level=3)
        if table.empty or summary.attrition_rate is None:
            st.info("표시할 직원 데이터가 없습니다.")
            return
        st.plotly_chart(
            rate_figure(table, column, summary.attrition_rate),
            theme=None,
            config=theme.PLOTLY_CONFIG,
            key=f"chart_{key}",
            alt=f"{title} 막대 차트. 수치는 아래 표에 있습니다.",
        )
        if table["is_small_sample"].any():
            layout.footnote(SMALL_NOTE)
        with st.expander("수치 표 보기"):
            st.html(table_html(table, column, header, summary))
```

#### 2-2. `dashboard/tests/test_stage3_group_chart.py` (새 파일)

```python
"""Stage 3 작업 2: 집단별 이직률 공통 컴포넌트."""

import pytest
from baselines import assert_displayed, report_table

from components import group_chart
from core import analytics

REPORT_TABLES = {
    "AgeGroup": (report_table("연령대", "직원 수", "이직자 수", "이직률"), False),
    "JobRole": (report_table("직무", "직원 수", "이직자 수", "이직률"), True),
    "IncomeGroup": (report_table("소득 구간", "직원 수", "이직자 수", "이직률"), False),
    "TenureGroup": (report_table("근속 구간", "직원 수", "이직자 수", "이직률"), False),
}


@pytest.mark.parametrize("column", REPORT_TABLES)
def test_group_table_matches_report(analysis_df, column):
    reported, sort_by_rate = REPORT_TABLES[column]
    table = group_chart.group_table(analysis_df, column, sort_by_rate=sort_by_rate)
    assert len(table) == len(reported.rows)
    for row, (_, total, leaver, rate) in zip(table.itertuples(), reported.rows, strict=True):
        assert_displayed(row.employee_count, total)
        assert_displayed(row.attrition_count, leaver)
        assert_displayed(row.attrition_rate, rate)
        assert row.retained_count == row.employee_count - row.attrition_count
    if column == "JobRole":
        assert list(table["JobRole"]) == [row[0] for row in reported.rows]


def test_rate_figure_values(analysis_df):
    table = group_chart.group_table(analysis_df, "JobRole", sort_by_rate=True)
    summary = analytics.summarize_attrition(analysis_df)
    figure = group_chart.rate_figure(table, "JobRole", summary.attrition_rate)
    bar = figure.data[0]
    assert list(bar.x) == pytest.approx(table["attrition_rate"].tolist())
    assert [row[0] for row in bar.customdata] == table["JobRole"].tolist()
    assert [int(row[1]) for row in bar.customdata] == table["employee_count"].tolist()
    assert [int(row[2]) for row in bar.customdata] == table["attrition_count"].tolist()
    assert "이직 %{customdata[2]:,}명 / 전체 %{customdata[1]:,}명" in bar.hovertemplate
    notes = [a.text for a in figure.layout.annotations if a.xref == "paper"]
    assert notes == [f"{rate:.2f}%" for rate in table["attrition_rate"]]
    assert figure.layout.shapes[0].x0 == pytest.approx(summary.attrition_rate)
    assert figure.layout.xaxis.range == (0, pytest.approx(table["attrition_rate"].max() * 1.65))
    assert figure.layout.height == 70 + 44 * len(table)


def test_zero_attrition_axis(analysis_df):
    subset = analysis_df.assign(AttritionBinary=0)
    table = group_chart.group_table(subset, "AgeGroup")
    figure = group_chart.rate_figure(table, "AgeGroup", 0.0)
    assert figure.layout.xaxis.range[1] > 0, "범위가 [0, 0]이면 0% 선이 가운데에 그려진다."
    assert figure.layout.shapes[0].x0 == 0
    line_label = next(a for a in figure.layout.annotations if a.text.startswith("전체"))
    assert line_label.xanchor == "left", "왼쪽 끝 기준선의 글자가 잘리지 않는다."


def test_small_samples_are_marked(analysis_df):
    subset = analysis_df.groupby("JobRole").head(40).iloc[:-15]
    table = group_chart.group_table(subset, "JobRole")
    assert table["is_small_sample"].any() and not table["is_small_sample"].all()
    figure = group_chart.rate_figure(table, "JobRole", 10.0)
    opacity = list(figure.data[0].marker.opacity)
    for label, small, alpha in zip(figure.data[0].y, table["is_small_sample"], opacity, strict=True):
        assert label.endswith(" ※") == small
        assert alpha == (group_chart.SMALL_OPACITY if small else 1.0)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Sales", "Sales"),
        ("Research Scientist", "Research<br>Scientist"),
        ("Healthcare Representative", "Healthcare<br>Representative"),
        ("Q3 - Middle High", "Q3 - Middle High"),
        ("Research Director", "Research<br>Director"),
    ],
)
def test_wrap_label(text, expected):
    assert group_chart.wrap_label(text) == expected


def test_table_html(analysis_df):
    table = group_chart.group_table(analysis_df, "TenureGroup")
    summary = analytics.summarize_attrition(analysis_df)
    html = group_chart.table_html(table, "TenureGroup", "근속", summary)
    for row in report_table("근속 구간", "직원 수", "이직자 수", "이직률").rows[:1]:
        assert f"<td>{row[1]}</td><td>{row[2]}</td>" in html
    first = table.iloc[0]
    assert (
        f'<tr><th scope="row">0-1 Years</th><td>{first.employee_count}</td>'
        f"<td>{first.attrition_count}</td><td>{first.retained_count}</td>"
        f"<td>{first.attrition_rate:.2f}%</td></tr>"
    ) in html
    assert "<td>1,470</td><td>237</td><td>1,233</td><td>16.12%</td>" in html
    small = table.assign(is_small_sample=True)
    assert '<th scope="row">0-1 Years ※</th>' in group_chart.table_html(small, "TenureGroup", "근속", summary)
    changed = table.assign(TenureGroup="<script>")
    assert "<script>" not in group_chart.table_html(changed, "TenureGroup", "<b>", summary)
```

### 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest dashboard\tests\test_stage3_group_chart.py -v
.\.venv\Scripts\python.exe -m pytest -q
```

- [ ] 새 테스트 `13 passed`, 전체 `218 passed`
- [ ] 보존 확인 `changed: 4, unexpected: 0`

### 캡처

| ID | 파일명 | 대상 | 보여야 할 것 |
|---|---|---|---|
| C3-20 | `c3_20_group_chart_test.png` | 터미널 | 새 테스트 13개를 포함한 218 passed |

---

## 작업 3. 연령·근속·소득 분석

### 지시

| 파일 | 할 일 | 주의 |
|---|---|---|
| `views/workforce.py` | **전체 교체.** 요약 문장, 연령대·근속·월 소득 차트 | 소득 구간 범위는 전체 데이터로 계산 |
| `tests/test_stage3_workforce.py` | 새 파일 | 차트는 순서가 아닌 키로 찾음(이후 작업에서도 유지) |

### 코드

#### 3-1. `dashboard/views/workforce.py` (전체 교체)

```python
"""Workforce Analysis 화면."""

import pandas as pd
import streamlit as st

from components import data_access, formatting, group_chart, layout
from core import analytics
from core.exceptions import DashboardError


def income_ranges(df: pd.DataFrame) -> str:
    """전사 기준 월 소득 사분위의 실제 범위. 필터 전 전체 데이터로 계산한다."""
    ranges = df.groupby("IncomeGroup", observed=True)["MonthlyIncome"].agg(["min", "max"])
    return " · ".join(
        f"{group} {formatting.count(row['min'])}~{formatting.count(row['max'])}"
        for group, row in ranges.iterrows()
    )


def render() -> None:
    layout.page_header("Workforce Analysis", "인력 특성별 이직 현황")
    try:
        df = data_access.get_analysis_data()
        summary = analytics.summarize_attrition(df)
    except DashboardError as error:
        layout.load_error(error)
        return

    layout.footnote(
        f"분석 대상 {formatting.count(summary.employee_count)}명 · "
        f"이직 {formatting.count(summary.attrition_count)}명 · "
        f"이직률 {formatting.percent(summary.attrition_rate)}"
    )

    layout.section_header("연령·근속·보상", "범주 순서대로 표시합니다. 점선은 전체 이직률입니다.")
    with st.container(key="grid_profile"):
        left, right = st.columns(2)
        with left:
            group_chart.render_section(
                df, summary, column="AgeGroup", title="연령대별 이직률", header="연령대",
                description="연령 구간은 왼쪽 경계를 포함합니다.", key="age",
            )
        with right:
            group_chart.render_section(
                df, summary, column="TenureGroup", title="근속연수별 이직률", header="근속",
                description="현 회사 근속연수(YearsAtCompany) 기준입니다.", key="tenure",
            )
    with st.container(key="grid_pay"):
        left, _ = st.columns(2)
        with left:
            group_chart.render_section(
                df, summary, column="IncomeGroup", title="월 소득 구간별 이직률", header="소득 구간",
                description="전사 기준 사분위입니다. 통화 단위는 원자료에 없습니다.", key="income",
            )
            layout.footnote(f"구간 범위: {income_ranges(df)}")
```

#### 3-2. `dashboard/tests/test_stage3_workforce.py` (새 파일)

```python
"""Stage 3 작업 3: 연령·근속·소득 화면."""

import csv
import json

import pytest
import streamlit as st
from baselines import report_table
from streamlit.testing.v1 import AppTest

from core import config

REPORTED = {
    "age": report_table("연령대", "직원 수", "이직자 수", "이직률").rows,
    "tenure": report_table("근속 구간", "직원 수", "이직자 수", "이직률").rows,
    "income": report_table("소득 구간", "직원 수", "이직자 수", "이직률").rows,
}


@pytest.fixture(autouse=True)
def clear_cache():
    st.cache_data.clear()
    yield
    st.cache_data.clear()


def _workforce():
    from views import workforce

    workforce.render()


def _run() -> AppTest:
    return AppTest.from_function(_workforce, default_timeout=30).run()


def _spec(app: AppTest, key: str) -> dict:
    # 이후 작업에서 차트가 늘어나도 유지되도록 순서가 아닌 키로 찾는다.
    chart = next(c for c in app.get("plotly_chart") if c.proto.id.endswith(f"chart_{key}"))
    return json.loads(chart.proto.spec)


def test_sections_render():
    app = _run()
    html = "".join(item.proto.body for item in app.main.get("html"))
    assert not app.exception
    assert not app.error and not app.warning
    for key in ("age", "tenure", "income"):
        assert _spec(app, key)["data"], key
    for title in ("연령대별 이직률", "근속연수별 이직률", "월 소득 구간별 이직률"):
        assert title in html
    for text in ("분석 대상 1,470명", "이직 237명", "이직률 16.12%"):
        assert text in html  # 작업 5에서 필터 문구가 앞에 붙어도 유지된다.


@pytest.mark.parametrize("key", ["age", "tenure", "income"])
def test_charts_match_report(key):
    spec = _spec(_run(), key)
    bar = spec["data"][0]
    reported = REPORTED[key]
    assert [row[1] for row in bar["customdata"]] == [int(r[1].replace(",", "")) for r in reported]
    assert [row[2] for row in bar["customdata"]] == [int(r[2]) for r in reported]
    labels = [a["text"] for a in spec["layout"]["annotations"] if a.get("xref") == "paper"]
    assert labels == [r[3] for r in reported]


def test_income_ranges_are_company_wide():
    rows = list(csv.DictReader(open(config.RAW_DATA_PATH, encoding="utf-8-sig")))
    incomes = sorted(int(r["MonthlyIncome"]) for r in rows)
    html = "".join(item.proto.body for item in _run().main.get("html"))
    note = html.split("구간 범위", 1)[1].split(": ", 1)[1].split("</p>", 1)[0]
    parts = note.split(" · ")
    assert len(parts) == 4
    assert parts[0].startswith(f"Q1 - Low {incomes[0]:,}~")
    assert parts[-1].endswith(f"~{incomes[-1]:,}")
    counts = [int(r[1].replace(",", "")) for r in REPORTED["income"]]
    # 각 구간의 최댓값이 정렬된 전체 소득에서 누적 인원 위치와 일치한다.
    position = 0
    for part, count in zip(parts, counts, strict=True):
        position += count
        assert part.endswith(f"~{incomes[position - 1]:,}")
```

### 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest dashboard\tests\test_stage3_workforce.py -v
.\.venv\Scripts\python.exe -m pytest -q
```

- [ ] 새 테스트 `5 passed`, 전체 `223 passed`
- [ ] 보존 확인 `changed: 4, unexpected: 0`

| 차트 | 기대값(보고서) |
|---|---|
| 연령대 | Under 25 39.18%, 25-34 20.22%, 35-44 10.10%, 45-54 10.20%, 55+ 15.94% |
| 근속 | 0-1 Years 34.88%, 2-3 Years 18.43%, 4-5 Years 13.07%, 6-10 Years 12.28%, Over 10 Years 8.13% |
| 월 소득 | Q1 29.27%, Q2 14.21%, Q3 10.63%, Q4 10.33% |

### 캡처

| ID | 파일명 | 크기 | 보여야 할 것 |
|---|---|---|---|
| C3-30 | `c3_30_workforce_test.png` | 터미널 | 223 passed |
| C3-31 | `c3_31_profile_desktop.png` | 1440×900 | 요약 문장, 연령대·근속 차트 2열 |
| C3-32 | `c3_32_profile_mobile.png` | 390×1800 | 차트 1열, 가로 스크롤 없음 |

---

## 작업 4. 직무·초과근무·교차 분석

### 지시

| 파일 | 할 일 | 주의 |
|---|---|---|
| `components/cross_chart.py` | 직무 × 초과근무 덤벨 차트와 표 | 직무 순서는 직무별 이직률 차트와 같음 |
| `views/workforce.py` | **전체 교체.** 초과근무·직무·교차 분석, 해석 주의 문구 | |
| `tests/test_stage3_jobs.py` | 새 파일 | 18칸을 원본 CSV와 대조 |

### 코드

#### 4-1. `dashboard/components/cross_chart.py` (새 파일)

```python
"""직무 × 초과근무 교차 분석: 덤벨 차트와 수치 표."""

from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components import formatting, group_chart, layout, theme
from core import analytics
from core.analytics import AttritionSummary

# (값, 표시 이름, 속이 빈 점 여부). 색은 이직률이므로 모두 이직 색을 쓰고 모양으로 구분한다.
SERIES = (("No", "초과근무 없음", True), ("Yes", "초과근무 있음", False))


def cross_table(df: pd.DataFrame) -> pd.DataFrame:
    table = analytics.attrition_by(df, ["JobRole", "OverTime"])
    table["JobRole"] = table["JobRole"].astype(str)
    table["OverTime"] = table["OverTime"].astype(str)
    return table


def role_order(df: pd.DataFrame) -> list[str]:
    """직무별 이직률 차트와 같은 순서."""
    return group_chart.group_table(df, "JobRole", sort_by_rate=True)["JobRole"].tolist()


def axis_upper(rates: list[float], overall_rate: float) -> float:
    """점 차트는 오른쪽 숫자 칸이 없으므로 막대 차트보다 여백을 적게 둔다. 0%만 있어도 0보다 크다."""
    return max([*rates, overall_rate, 1.0]) * 1.15


def _marker(hollow: bool) -> dict:
    return {
        "size": 12,
        "color": theme.COLORS["surface"] if hollow else theme.COLORS["attrition"],
        "line": {"color": theme.COLORS["attrition"], "width": 2},
    }


def cross_figure(table: pd.DataFrame, order: list[str], overall_rate: float) -> go.Figure:
    labels = {role: group_chart.wrap_label(role) for role in order}
    upper = axis_upper(table["attrition_rate"].tolist(), overall_rate)
    figure = go.Figure()

    xs, ys = [], []
    for role in order:
        rates = table.loc[table["JobRole"] == role, "attrition_rate"].tolist()
        if len(rates) == 2:  # 한쪽만 있는 직무는 선을 긋지 않는다.
            xs += [*rates, None]
            ys += [labels[role], labels[role], None]
    figure.add_scatter(
        x=xs, y=ys, mode="lines", hoverinfo="skip", showlegend=False,
        line={"color": theme.COLORS["ink-muted"], "width": 1.5},
    )

    for value, name, hollow in SERIES:
        rows = table[table["OverTime"] == value].set_index("JobRole")
        roles = [role for role in order if role in rows.index]
        rows = rows.loc[roles]
        figure.add_scatter(
            x=rows["attrition_rate"].tolist(),
            y=[labels[role] for role in roles],
            mode="markers",
            name=name,
            showlegend=False,
            cliponaxis=False,  # 0%인 점이 축에서 반쯤 잘리지 않게 한다.
            marker={
                **_marker(hollow),
                "opacity": [group_chart.SMALL_OPACITY if s else 1.0 for s in rows["is_small_sample"]],
            },
            customdata=[
                [role, int(r.employee_count), int(r.attrition_count), "※ 30명 미만" if r.is_small_sample else ""]
                for role, r in zip(roles, rows.itertuples(), strict=True)
            ],
            hovertemplate=(
                f"<b>%{{customdata[0]}}</b> · {name}<br>이직률 %{{x:.2f}}%<br>"
                "이직 %{customdata[2]:,}명 / 전체 %{customdata[1]:,}명<br>%{customdata[3]}<extra></extra>"
            ),
        )

    # 범례는 첫 점의 투명도를 따라가므로, 범례 전용 항목을 따로 둔다.
    for _, name, hollow in SERIES:
        figure.add_scatter(x=[None], y=[None], mode="markers", name=name, marker=_marker(hollow), hoverinfo="skip")

    theme.style_figure(figure, height=90 + group_chart.ROW_HEIGHT * len(order))
    figure.update_layout(
        legend={
            "orientation": "h", "x": 0, "y": 1.0, "yanchor": "bottom",
            "itemclick": False, "itemdoubleclick": False,
        },
        margin={"t": 56},
    )
    figure.update_xaxes(range=[0, upper], ticksuffix="%", nticks=5)
    figure.update_yaxes(
        categoryorder="array", categoryarray=[labels[role] for role in order], autorange="reversed"
    )
    figure.add_vline(
        x=overall_rate, line={"color": theme.COLORS["ink-muted"], "width": 1, "dash": "dash"}
    )
    return figure


def table_html(table: pd.DataFrame, order: list[str]) -> str:
    rank = {role: i for i, role in enumerate(order)}
    rows = table.sort_values(["JobRole", "OverTime"], key=lambda c: c.map(rank) if c.name == "JobRole" else c)
    body = "".join(
        f'<tr><th scope="row">{escape(r.JobRole)}</th>'
        f"<td>{group_chart.row_label(r.OverTime, r.is_small_sample)}</td>"
        + "".join(
            f"<td>{escape(v)}</td>"
            for v in (
                formatting.count(r.employee_count),
                formatting.count(r.attrition_count),
                formatting.percent(r.attrition_rate),
            )
        )
        + "</tr>"
        for r in rows.itertuples()
    )
    headers = "".join(
        f'<th scope="col">{name}</th>' for name in ("직무", "초과근무", "직원", "이직", "이직률")
    )
    return (
        '<div class="hr-table-scroll"><table class="hr-table">'
        f"<thead><tr>{headers}</tr></thead><tbody>{body}</tbody></table></div>"
    )


def render(df: pd.DataFrame, summary: AttritionSummary) -> None:
    with st.container(key="card_cross"):
        layout.section_header(
            "직무 × 초과근무",
            "같은 직무 안에서 초과근무 여부에 따른 이직률입니다. 빈 점: 없음, 채운 점: 있음. "
            f"점선: 전체 {formatting.percent(summary.attrition_rate)}",
            level=3,
        )
        table = cross_table(df)
        if table.empty or summary.attrition_rate is None:
            st.info("표시할 직원 데이터가 없습니다.")
            return
        order = role_order(df)
        st.plotly_chart(
            cross_figure(table, order, summary.attrition_rate),
            theme=None,
            config=theme.PLOTLY_CONFIG,
            key="chart_cross",
            alt="직무별 초과근무 여부에 따른 이직률 점 차트. 수치는 아래 표에 있습니다.",
        )
        if table["is_small_sample"].any():
            layout.footnote(group_chart.SMALL_NOTE)
        with st.expander("수치 표 보기"):
            st.html(table_html(table, order))
```

#### 4-2. `dashboard/views/workforce.py` (전체 교체)

```python
"""Workforce Analysis 화면."""

import pandas as pd
import streamlit as st

from components import cross_chart, data_access, formatting, group_chart, layout
from core import analytics
from core.exceptions import DashboardError


def income_ranges(df: pd.DataFrame) -> str:
    """전사 기준 월 소득 사분위의 실제 범위. 필터 전 전체 데이터로 계산한다."""
    ranges = df.groupby("IncomeGroup", observed=True)["MonthlyIncome"].agg(["min", "max"])
    return " · ".join(
        f"{group} {formatting.count(row['min'])}~{formatting.count(row['max'])}"
        for group, row in ranges.iterrows()
    )


def render() -> None:
    layout.page_header("Workforce Analysis", "인력 특성별 이직 현황")
    try:
        df = data_access.get_analysis_data()
        summary = analytics.summarize_attrition(df)
    except DashboardError as error:
        layout.load_error(error)
        return

    layout.footnote(
        f"분석 대상 {formatting.count(summary.employee_count)}명 · "
        f"이직 {formatting.count(summary.attrition_count)}명 · "
        f"이직률 {formatting.percent(summary.attrition_rate)}"
    )

    layout.section_header("연령·근속·보상", "범주 순서대로 표시합니다. 점선은 전체 이직률입니다.")
    with st.container(key="grid_profile"):
        left, right = st.columns(2)
        with left:
            group_chart.render_section(
                df, summary, column="AgeGroup", title="연령대별 이직률", header="연령대",
                description="연령 구간은 왼쪽 경계를 포함합니다.", key="age",
            )
        with right:
            group_chart.render_section(
                df, summary, column="TenureGroup", title="근속연수별 이직률", header="근속",
                description="현 회사 근속연수(YearsAtCompany) 기준입니다.", key="tenure",
            )
    with st.container(key="grid_pay"):
        left, right = st.columns(2)
        with left:
            group_chart.render_section(
                df, summary, column="IncomeGroup", title="월 소득 구간별 이직률", header="소득 구간",
                description="전사 기준 사분위입니다. 통화 단위는 원자료에 없습니다.", key="income",
            )
            layout.footnote(f"구간 범위: {income_ranges(df)}")
        with right:
            group_chart.render_section(
                df, summary, column="OverTime", title="초과근무 여부별 이직률", header="초과근무",
                description="OverTime 값(Yes/No) 기준입니다.", key="overtime",
            )

    layout.section_header("직무", "이직률이 높은 순으로 표시합니다.")
    group_chart.render_section(
        df, summary, column="JobRole", title="직무별 이직률", header="직무",
        description="9개 직무를 이직률 순으로 정렬했습니다.", key="jobrole", sort_by_rate=True,
    )
    cross_chart.render(df, summary)
    layout.footnote(
        "집단 간 차이는 연관성이며 인과관계나 통계적 유의성을 뜻하지 않습니다. "
        "데이터에 기간 정보가 없어 연간 이직률로 해석할 수 없습니다."
    )
```

#### 4-3. `dashboard/tests/test_stage3_jobs.py` (새 파일)

```python
"""Stage 3 작업 4: 직무·초과근무·교차 분석."""

import csv
import json
from collections import Counter

import pytest
import streamlit as st
from baselines import report_table
from streamlit.testing.v1 import AppTest

from components import cross_chart, group_chart
from core import analytics, config

ROLES = report_table("직무", "직원 수", "이직자 수", "이직률").rows
OVERTIME = {
    group: row
    for variable, group, *row in report_table("변수", "집단", "직원 수", "이직자 수", "이직률").rows
    if variable == "초과근무"
}


@pytest.fixture(autouse=True)
def clear_cache():
    st.cache_data.clear()
    yield
    st.cache_data.clear()


def _workforce():
    from views import workforce

    workforce.render()


def _spec(app: AppTest, key: str) -> dict:
    chart = next(c for c in app.get("plotly_chart") if c.proto.id.endswith(f"chart_{key}"))
    return json.loads(chart.proto.spec)


@pytest.fixture(scope="module")
def app():
    st.cache_data.clear()
    return AppTest.from_function(_workforce, default_timeout=30).run()


def test_all_sections_render(app):
    html = "".join(item.proto.body for item in app.main.get("html"))
    assert not app.exception and not app.error and not app.warning
    assert len(app.get("plotly_chart")) == 6
    for title in ("초과근무 여부별 이직률", "직무별 이직률", "직무 × 초과근무"):
        assert title in html
    assert "인과관계나 통계적 유의성을 뜻하지 않습니다" in html


def test_job_role_chart_matches_report(app):
    bar = _spec(app, "jobrole")["data"][0]
    assert [row[0] for row in bar["customdata"]] == [r[0] for r in ROLES]
    assert [row[1] for row in bar["customdata"]] == [int(r[1]) for r in ROLES]
    assert [row[2] for row in bar["customdata"]] == [int(r[2]) for r in ROLES]


def test_overtime_chart_matches_report(app):
    spec = _spec(app, "overtime")
    bar = spec["data"][0]
    labels = [a["text"] for a in spec["layout"]["annotations"] if a.get("xref") == "paper"]
    for (group, total, leaver), label in zip(bar["customdata"], labels, strict=True):
        assert [f"{total:,}", f"{leaver:,}", label] == OVERTIME[group]


def _raw_cross() -> dict[tuple[str, str], tuple[int, int]]:
    rows = list(csv.DictReader(open(config.RAW_DATA_PATH, encoding="utf-8-sig")))
    total = Counter((r["JobRole"], r["OverTime"]) for r in rows)
    left = Counter((r["JobRole"], r["OverTime"]) for r in rows if r["Attrition"] == "Yes")
    return {key: (total[key], left[key]) for key in total}


def test_cross_chart_matches_raw_csv(app):
    spec = _spec(app, "cross")
    expected = _raw_cross()
    markers = [trace for trace in spec["data"] if trace.get("customdata")]
    legend = [trace for trace in spec["data"] if trace.get("showlegend", True) and not trace.get("customdata")]
    assert [trace["name"] for trace in markers] == ["초과근무 없음", "초과근무 있음"]
    assert markers[0]["marker"]["color"] == "#FFFFFF" and markers[1]["marker"]["color"] == "#D9652B"
    # 범례는 소표본 투명도와 무관하게 선명해야 한다.
    assert [(t["name"], t["marker"].get("opacity", 1)) for t in legend] == [("초과근무 없음", 1), ("초과근무 있음", 1)]
    assert all(trace["cliponaxis"] is False for trace in markers)
    assert 0 < spec["layout"]["xaxis"]["range"][1] < 100
    seen = 0
    for trace, value in zip(markers, ("No", "Yes"), strict=True):
        assert [row[0] for row in trace["customdata"]] == [r[0] for r in ROLES]
        for (role, total, left, note), x, alpha in zip(
            trace["customdata"], trace["x"], trace["marker"]["opacity"], strict=True
        ):
            assert (total, left) == expected[(role, value)]
            assert x == pytest.approx(left / total * 100)
            assert (note == "※ 30명 미만") == (total < 30) == (alpha == group_chart.SMALL_OPACITY)
            seen += 1
    assert seen == len(expected) == 18


def test_cross_table_html(analysis_df):
    table = cross_chart.cross_table(analysis_df)
    order = cross_chart.role_order(analysis_df)
    html = cross_chart.table_html(table, order)
    expected = _raw_cross()
    for role in order:
        for value in ("No", "Yes"):
            total, left = expected[(role, value)]
            mark = " ※" if total < 30 else ""
            row = (
                f'<tr><th scope="row">{role}</th><td>{value}{mark}</td><td>{total:,}</td>'
                f"<td>{left:,}</td><td>{left / total * 100:.2f}%</td></tr>"
            )
            assert row in html, (role, value)
    assert html.index(f">{order[0]}<") < html.index(f">{order[-1]}<")
    changed = table.assign(JobRole="<script>")
    assert "<script>" not in cross_chart.table_html(changed, ["<script>"])


def test_cross_with_one_sided_role_and_zero_rates(analysis_df):
    subset = analysis_df[~((analysis_df["JobRole"] == "Manager") & (analysis_df["OverTime"] == "Yes"))]
    subset = subset.assign(AttritionBinary=0)
    table = cross_chart.cross_table(subset)
    order = cross_chart.role_order(subset)
    figure = cross_chart.cross_figure(table, order, analytics.summarize_attrition(subset).attrition_rate)
    line = figure.data[0]
    assert "Manager" not in [y for y in line.y if y]
    assert "Manager" in figure.data[1].y and "Manager" not in figure.data[2].y
    assert figure.layout.xaxis.range[1] == pytest.approx(1.15)
    assert figure.layout.xaxis.range[1] > 0
```

### 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest dashboard\tests\test_stage3_jobs.py -v
.\.venv\Scripts\python.exe -m pytest -q
```

- [ ] 새 테스트 `6 passed`, 전체 `229 passed`
- [ ] 보존 확인 `changed: 4, unexpected: 0`
- [ ] 직무 순서: Sales Representative 39.76% → … → Research Director 2.50%
- [ ] 30명 미만 4칸이 흐리게 표시됨: Human Resources·Research Director·Sales Representative·Manager의 초과근무 있음

### 캡처

| ID | 파일명 | 크기 | 보여야 할 것 |
|---|---|---|---|
| C3-40 | `c3_40_jobs_test.png` | 터미널 | 229 passed |
| C3-41 | `c3_41_jobs_desktop.png` | 1440×900 | 직무별 차트와 교차 차트(스크롤) |
| C3-42 | `c3_42_cross_mobile.png` | 390×900 | 교차 차트, 0% 점이 잘리지 않음 |
| C3-43 | `c3_43_cross_tooltip.png` | 1440×900 | 점 툴팁: 직무, 이직률, 이직/전체 인원 |

---

## 작업 5. 필터

### 지시

| 파일 | 할 일 | 주의 |
|---|---|---|
| `components/filters.py` | 부서·성별 다중 선택, 필터 적용, 요약 문구 | 선택지는 `core.schema` 허용값 |
| `views/workforce.py` | **전체 교체.** 필터 적용, 빈 결과 안내 | 소득 구간 범위는 필터 전 전체 데이터 |
| `tests/test_stage3_filters.py` | 새 파일 | |

### 코드

#### 5-1. `dashboard/components/filters.py` (새 파일)

```python
"""Workforce 화면 필터. Overview에는 적용하지 않는다."""

import pandas as pd
import streamlit as st

from core import schema

# (컬럼, 표시 이름). 선택지는 schema의 허용값을 그대로 쓴다.
FILTERS = (("Department", "부서"), ("Gender", "성별"))


def apply_filters(df: pd.DataFrame, selected: dict[str, list[str]]) -> pd.DataFrame:
    """분석 구간을 만든 뒤의 전체 데이터에 적용한다. 급여 사분위는 다시 만들지 않는다."""
    mask = pd.Series(True, index=df.index)
    for column, values in selected.items():
        mask &= df[column].isin(values)
    return df[mask]


def render_filters() -> dict[str, list[str]]:
    selected = {}
    with st.container(key="grid_filters"):
        for column_box, (column, label) in zip(st.columns(len(FILTERS)), FILTERS, strict=True):
            options = list(schema.CATEGORIES[column])
            with column_box:
                selected[column] = st.multiselect(
                    label, options, default=options, key=f"filter_{column}", placeholder="선택 안 함"
                )
    return selected


def describe(selected: dict[str, list[str]]) -> str:
    return " · ".join(
        f"{label} {len(selected[column])}/{len(schema.CATEGORIES[column])}" for column, label in FILTERS
    )
```

#### 5-2. `dashboard/views/workforce.py` (전체 교체)

```python
"""Workforce Analysis 화면."""

import pandas as pd
import streamlit as st

from components import cross_chart, data_access, filters, formatting, group_chart, layout
from core import analytics
from core.exceptions import DashboardError


def income_ranges(df: pd.DataFrame) -> str:
    """전사 기준 월 소득 사분위의 실제 범위. 필터 전 전체 데이터로 계산한다."""
    ranges = df.groupby("IncomeGroup", observed=True)["MonthlyIncome"].agg(["min", "max"])
    return " · ".join(
        f"{group} {formatting.count(row['min'])}~{formatting.count(row['max'])}"
        for group, row in ranges.iterrows()
    )


def render() -> None:
    layout.page_header("Workforce Analysis", "인력 특성별 이직 현황")
    try:
        company = data_access.get_analysis_data()
    except DashboardError as error:
        layout.load_error(error)
        return

    selected = filters.render_filters()
    df = filters.apply_filters(company, selected)
    summary = analytics.summarize_attrition(df)
    layout.footnote(
        f"필터 {filters.describe(selected)} · 분석 대상 {formatting.count(summary.employee_count)}명"
        f"(전체 {formatting.count(len(company))}명 중) · "
        f"이직 {formatting.count(summary.attrition_count)}명 · "
        f"이직률 {formatting.percent(summary.attrition_rate)}"
    )
    if df.empty:
        st.info("선택한 조건에 해당하는 직원이 없습니다. 필터를 하나 이상 선택하세요.")
        return

    layout.section_header("연령·근속·보상", "범주 순서대로 표시합니다. 점선은 전체 이직률입니다.")
    with st.container(key="grid_profile"):
        left, right = st.columns(2)
        with left:
            group_chart.render_section(
                df, summary, column="AgeGroup", title="연령대별 이직률", header="연령대",
                description="연령 구간은 왼쪽 경계를 포함합니다.", key="age",
            )
        with right:
            group_chart.render_section(
                df, summary, column="TenureGroup", title="근속연수별 이직률", header="근속",
                description="현 회사 근속연수(YearsAtCompany) 기준입니다.", key="tenure",
            )
    with st.container(key="grid_pay"):
        left, right = st.columns(2)
        with left:
            group_chart.render_section(
                df, summary, column="IncomeGroup", title="월 소득 구간별 이직률", header="소득 구간",
                description="전사 기준 사분위입니다. 통화 단위는 원자료에 없습니다.", key="income",
            )
            layout.footnote(f"구간 범위(전사 기준): {income_ranges(company)}")
        with right:
            group_chart.render_section(
                df, summary, column="OverTime", title="초과근무 여부별 이직률", header="초과근무",
                description="OverTime 값(Yes/No) 기준입니다.", key="overtime",
            )

    layout.section_header("직무", "이직률이 높은 순으로 표시합니다.")
    group_chart.render_section(
        df, summary, column="JobRole", title="직무별 이직률", header="직무",
        description="9개 직무를 이직률 순으로 정렬했습니다.", key="jobrole", sort_by_rate=True,
    )
    cross_chart.render(df, summary)
    layout.footnote(
        "집단 간 차이는 연관성이며 인과관계나 통계적 유의성을 뜻하지 않습니다. "
        "데이터에 기간 정보가 없어 연간 이직률로 해석할 수 없습니다."
    )
```

#### 5-3. `dashboard/tests/test_stage3_filters.py` (새 파일)

```python
"""Stage 3 작업 5: Workforce 필터."""

import csv
import json
from collections import Counter

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from components import filters, group_chart
from core import config

RAW = list(csv.DictReader(open(config.RAW_DATA_PATH, encoding="utf-8-sig")))


@pytest.fixture(autouse=True)
def clear_cache():
    st.cache_data.clear()
    yield
    st.cache_data.clear()


def _workforce():
    from views import workforce

    workforce.render()


def _html(app: AppTest) -> str:
    return "".join(item.proto.body for item in app.main.get("html"))


def _spec(app: AppTest, key: str) -> dict:
    chart = next(c for c in app.get("plotly_chart") if c.proto.id.endswith(f"chart_{key}"))
    return json.loads(chart.proto.spec)


def _app_with(department: list[str] | None = None, gender: list[str] | None = None) -> AppTest:
    app = AppTest.from_function(_workforce, default_timeout=30).run()
    if department is not None:
        app.multiselect(key="filter_Department").set_value(department)
    if gender is not None:
        app.multiselect(key="filter_Gender").set_value(gender)
    return app.run()


def test_default_selects_everything():
    app = _app_with()
    assert not app.exception
    assert [m.label for m in app.multiselect] == ["부서", "성별"]
    assert app.multiselect(key="filter_Department").value == [
        "Human Resources", "Research & Development", "Sales"
    ]
    assert app.multiselect(key="filter_Gender").value == ["Female", "Male"]
    assert "분석 대상 1,470명(전체 1,470명 중)" in _html(app)


def test_apply_filters_matches_raw_csv(analysis_df):
    view = filters.apply_filters(analysis_df, {"Department": ["Sales"], "Gender": ["Female"]})
    rows = [r for r in RAW if r["Department"] == "Sales" and r["Gender"] == "Female"]
    assert len(view) == len(rows)
    assert int(view["AttritionBinary"].sum()) == sum(r["Attrition"] == "Yes" for r in rows)
    # 급여 사분위는 전사 기준 그대로다. 필터 안에서 다시 4등분하지 않는다.
    assert view["IncomeGroup"].equals(analysis_df.loc[view.index, "IncomeGroup"])
    assert view["IncomeGroup"].value_counts().nunique() > 1


def test_department_filter_updates_charts():
    app = _app_with(department=["Human Resources"])
    rows = [r for r in RAW if r["Department"] == "Human Resources"]
    total, left = len(rows), sum(r["Attrition"] == "Yes" for r in rows)
    html = _html(app)
    assert not app.exception
    assert f"분석 대상 {total}명(전체 1,470명 중)" in html
    assert f"이직률 {left / total * 100:.2f}%" in html
    bar = _spec(app, "jobrole")["data"][0]
    expected_total = Counter(r["JobRole"] for r in rows)
    expected_left = Counter(r["JobRole"] for r in rows if r["Attrition"] == "Yes")
    assert {row[0]: (row[1], row[2]) for row in bar["customdata"]} == {
        role: (expected_total[role], expected_left[role]) for role in expected_total
    }
    # HR Manager는 이직자 0명이다. 막대가 0이어도 축이 정상이어야 한다.
    assert expected_left["Manager"] == 0
    assert _spec(app, "jobrole")["layout"]["xaxis"]["range"][1] > 0
    assert group_chart.SMALL_NOTE.replace("※ ", "") in html


def test_income_ranges_stay_company_wide():
    full = _html(_app_with())
    sales = _html(_app_with(department=["Sales"]))
    note = lambda html: html.split("구간 범위", 1)[1].split("</p>", 1)[0]
    assert note(full) == note(sales)


def test_empty_selection():
    app = _app_with(department=[])
    assert not app.exception
    assert len(app.info) == 1
    assert not app.get("plotly_chart")
    assert "분석 대상 0명" in _html(app)
    assert "이직률 —" in _html(app)


def test_gender_filter():
    app = _app_with(gender=["Female"])
    rows = [r for r in RAW if r["Gender"] == "Female"]
    assert f"분석 대상 {len(rows)}명" in _html(app)
    bar = _spec(app, "overtime")["data"][0]
    assert sum(row[1] for row in bar["customdata"]) == len(rows)


def test_describe():
    assert filters.describe({"Department": ["Sales"], "Gender": ["Female", "Male"]}) == "부서 1/3 · 성별 2/2"
```

### 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest dashboard\tests\test_stage3_filters.py -v
.\.venv\Scripts\python.exe -m pytest -q
```

- [ ] 새 테스트 `7 passed`, 전체 `236 passed`
- [ ] 보존 확인 `changed: 4, unexpected: 0`
- [ ] 부서를 Human Resources만 남기면 “분석 대상 63명”, 이직률 19.05%
- [ ] HR만 선택 시 Manager 막대가 0.00%이고 축이 정상(기준선이 가운데에 그려지지 않음)
- [ ] 부서를 모두 지우면 차트 없이 안내 문구
- [ ] Overview에는 필터가 없음

### 캡처

| ID | 파일명 | 크기 | 보여야 할 것 |
|---|---|---|---|
| C3-50 | `c3_50_filters_test.png` | 터미널 | 236 passed |
| C3-51 | `c3_51_filters_default.png` | 1440×900 | 필터 2개, 전체 선택, 1,470명 |
| C3-52 | `c3_52_filter_hr.png` | 1440×900 | HR만 선택, 63명, 소표본 흐림 표시 |
| C3-52 보완 | `c3_52_filters_updated_job_count.png` | 1440×1897 | 같은 필터에서 직무 차트까지 포함, “2개 직무” 문구와 막대 2개(이후 수정 후 추가) |
| C3-53 | `c3_53_filter_empty.png` | 1440×900 | 빈 선택 안내 |

---

## 작업 6. 최종 점검과 승인 필요 항목

### 6-1. 점검

```powershell
.\.venv\Scripts\python.exe dashboard\scripts\check_setup.py
.\.venv\Scripts\python.exe -m pytest -q
```

- [ ] `RESULT: PASS`, `236 passed`
- [ ] 보존 확인 `changed: 4, unexpected: 0`
- [ ] Overview의 KPI·부서별 차트·표가 2단계와 같음(필터 영향 없음)
- [ ] 360~1920px에서 가로 스크롤, 글자 잘림, 겹침 없음

### 6-2. 승인 필요 항목

**아래 항목은 3단계 허용 범위 밖이므로 실행하지 않습니다.** 승인을 받으면 진행합니다.

| 항목 | 내용 |
|---|---|
| README 갱신 | `dashboard/README.md` 4행을 “현재 **3단계(Workforce Analysis)** 까지 구현되어 있습니다.”로 바꾸고, 단계 표의 상태를 1~3 “완료”로 변경 |
| C11 이동 | `Move-Item dashboard\docs\captures\stage2\c11_theme_files.png docs\captures\stage2\` (대상 위치에 같은 이름이 없을 때만) |
| 2단계 가이드 | `stage2_guide.md` 맨 위에 “작업 3·4 코드는 이후 수정됨. 실제 파일을 기준으로 할 것” 안내 추가 |

처리 결과(문서화 작업): README와 2단계 가이드는 갱신했습니다. C11은 옮기지 않고 문서의 참조 경로를 실제 위치(`dashboard/docs/captures/stage2/`)로 맞췄습니다.

### 캡처

| ID | 파일명 | 대상 | 보여야 할 것 |
|---|---|---|---|
| C3-60 | `c3_60_preserved.png` | 터미널 | `changed: 4, unexpected: 0` |
| C3-61 | `c3_61_final_test.png` | 터미널 | PASS, 236 passed |
| C3-62 | `c3_62_overview_unchanged.png` | 1440×1200 | Overview 전체(2단계 C44와 비교) |

### 완료 보고 양식

```text
[3단계 완료]
- 전체 테스트: ___ passed
- 보존 확인: changed: ___, unexpected: ___
- 캡처: C3-10~C3-62 중 ___개 (누락: ___)
- 지시서와 다르게 구현한 부분: ___
- 승인 필요 항목(README, C11, 2단계 가이드) 처리 여부: 대기
```

---

## 위험 요소

| 위험 | 영향 | 대응 |
|---|---|---|
| 주소로 바로 접속할 때 404 | `/workforce`처럼 하위 주소로 열면 Streamlit이 `/workforce/_stcore/health` 등을 먼저 요청해 콘솔에 404가 2건 남음. 수정하지 않은 2단계 앱도 같음 | 앱 동작에는 영향 없음. 오류로 세지 않되 기록 |
| Streamlit 내부 `data-testid` 의존 | 버전을 올리면 메뉴·2열 배치 CSS가 깨질 수 있음 | `requirements-lock.txt` 버전 유지, 올릴 때 캡처 비교 |
| 필터 상태 초기화 | 다른 화면에 다녀오면 필터가 전체 선택으로 돌아감 | Streamlit 기본 동작. 필요하면 4단계 이후 별도 결정 |
| 소표본 | 필터를 걸면 30명 미만 집단이 많아짐. HR만 선택하면 연령·근속·소득 구간은 모두 소표본이지만, 초과근무 없음(46명)과 직무 Human Resources(52명)는 소표본이 아님 | 흐림, `※`, 각주로 표시. 통계적 결론을 쓰지 않음 |
| 교차 차트 점 겹침 | 두 비율이 비슷하면(Healthcare Representative) 점이 겹침 | 툴팁과 수치 표로 확인 |
| AppTest 한계 | 함수형 페이지로 이동하지 못해 Workforce는 하네스로 테스트 | 실제 이동은 브라우저에서 확인 |

## 문제 해결

| 증상 | 원인 | 조치 |
|---|---|---|
| `AttributeError: 'Page' object has no attribute 'url_path'` | Streamlit 버전 다름 | `requirements-lock.txt`의 1.67.0 사용 |
| 메뉴가 모두 강조됨 | `styles.css` 교체 누락 | 작업 1의 CSS 전체 교체 |
| `test_only_overview_is_a_link` 실패 | `test_stage2_shell.py` 교체 누락 | 작업 1의 테스트 파일 교체 |
| Workforce 차트가 1열로만 보임 | `grid_` CSS 누락 | 작업 1의 CSS 확인 |
| 보존 확인 `unexpected` 발생 | 허용되지 않은 파일 변경 | 코드를 고치기 전에 바뀐 파일 목록부터 확인 |

---

## 최종 상태와 변경 이력

3단계 완료 후 문서화 작업(2026-11-24)에서 이 문서의 코드와 실제 파일을 비교하고, 원본 CSV로 수치를 다시 확인한 결과입니다. 위의 작업 0~6 내용은 당시 지시서 그대로 보존합니다.

### 최종 구현 요약

| 영역 | 최종 구현 | 파일 |
|---|---|---|
| 페이지 구조 | `st.navigation(position="hidden")`으로 `/`(Overview), `/workforce` 등록. `/overview`는 숨김 페이지가 `/`로 전환. 사이드바는 현재 화면을 `aria-current="page"` 요소로 표시 | `app.py`, `components/navigation.py` |
| 공통 차트 | `group_table`(집계, 선택적 이직률 정렬) → `rate_figure`(가로 막대, 오른쪽 정렬 비율 숫자, 점선 기준선) → `table_html`(직원·이직·재직·이직률, “전체” 행) | `components/group_chart.py` |
| Workforce 화면 | 필터 → 요약 문구 → 연령·근속·소득·초과근무 2열 카드 → 직무별 이직률 → 직무 × 초과근무 → 해석 각주. 카드마다 “수치 표 보기” | `views/workforce.py` |
| 연령·근속·소득 | 연령대 5구간(왼쪽 경계 포함), 근속 5구간(`YearsAtCompany`), 월 소득 전사 사분위 4구간과 각 구간의 실제 범위 각주 | `views/workforce.py`, `core/analytics.py` |
| 직무·교차 분석 | 직무별 이직률(이직률 내림차순, 같으면 인원 순). 직무 × 초과근무 덤벨 차트(빈 점: 없음, 채운 점: 있음, 직무 순서는 직무별 차트와 같음) | `components/group_chart.py`, `components/cross_chart.py` |
| 필터 | 부서·성별 다중 선택(기본값 전체), 필터 초기화 버튼, 요약 문구 `필터 부서 n/3 · 성별 n/2 · 분석 대상 …`. Overview에는 필터 없음 | `components/filters.py` |
| 소표본 | `config.SMALL_SAMPLE_THRESHOLD = 30`. 30명 미만이면 막대·점 투명도 0.45, 이름 뒤 `※`, 카드 아래 각주. 화면 표시 기준이며 통계적 기준이 아님 | `core/config.py`, `core/analytics.py` |
| 전사 평균 기준선 | 모든 Workforce 차트의 점선과 설명 문구는 필터와 무관하게 전사 평균 16.12%(237 ÷ 1,470). 필터 결과의 이직률은 요약 문구와 표의 “전체” 행 | `views/workforce.py` |
| 월 소득 사분위 | 필터 전 전체 데이터로 `pd.qcut`한 구간을 유지. `apply_filters`는 행만 고름. 구간 범위 각주도 전사 기준 | `core/analytics.py`, `components/filters.py` |

### 작업 5에서 결정한 사항

작업 5 진행 중 지시서와 다르게 결정해 구현한 내용입니다.

| 항목 | 지시서 | 결정과 구현 |
|---|---|---|
| 기준선 | `render_section(df, summary)`로 필터 결과의 평균을 점선으로 사용 | 전사 평균 16.12%로 고정. `workforce.py`에 `_section`을 두고 `rate_figure`에 전사 이직률을 넘김. 교차 차트에는 `company_summary`를 넘김 |
| 표의 “전체” 행 | (기준선과 같은 summary) | 필터 결과(선택 집단) 기준 유지 |
| 섹션 설명 | “점선은 전체 이직률입니다.” | “점선은 전사 평균 이직률(16.12%)입니다.” |
| 필터 초기화 | 없음 | “필터 초기화” 버튼(`on_click=reset_filters`). 초깃값은 `default` 인자 대신 `session_state.setdefault` |
| 요약 문구 | 있음 | 유지 |

`group_chart.render_section`은 남아 있지만 현재 화면에서는 호출하지 않습니다. 삭제는 코드 수정이므로 별도 승인 항목입니다.

### 작업 6 이후 수정

**1. Female 필터에서 Human Resources 직무명 잘림** (`group_chart.py`)

성별을 Female만 선택하면 직무 Human Resources가 16명이라 소표본 `※`가 붙습니다.
지시서 코드는 `※`를 붙이기 전 길이(15자)로 줄바꿈을 판단해 `Human Resources ※`(17자)가 한 줄로 남았고, 축 왼쪽에서 잘렸습니다.
`※`까지 포함한 문자열로 `wrap_label`을 호출하도록 바꿔 `Human<br>Resources ※`로 두 줄 표시됩니다.

```python
# 지시서
wrap_label(name) + (f" {SMALL_MARK}" if small else "")
# 실제
wrap_label(f"{name} {SMALL_MARK}" if small else name)
```

테스트 `test_small_mark_counts_toward_wrap`이 추가되었습니다(모든 줄 16자 이하 확인).

**2. 직무 설명 문구의 직무 수** (`workforce.py`)

지시서는 “9개 직무를 이직률 순으로 정렬했습니다.”로 고정되어 있어, 필터로 직무가 줄어도 9개로 표시되었습니다.
필터 후 실제로 남은 직무 수를 쓰도록 바꿨습니다.

```python
description=f"{df['JobRole'].nunique()}개 직무를 이직률 순으로 정렬했습니다.",  # 필터 후 남은 직무 수
```

테스트 `test_job_role_description_matches_filtered_roles`가 21개 필터 조합 전부에서 문구의 직무 수와 차트 항목 수를 원본 CSV의 직무 수와 대조합니다.

### 필터 조합별 실제 직무 수

원본 CSV(`data/raw/hr.csv`)에서 직접 집계했습니다. 소표본 직무는 30명 미만인 직무 수입니다. 부서 또는 성별을 하나도 선택하지 않으면 0명이므로 차트 대신 안내 문구가 나옵니다.

| 부서 | 성별 | 인원 | 이직 | 이직률 | 직무 수 | 소표본 직무 |
|---|---|--:|--:|--:|--:|--:|
| Human Resources | Female | 20 | 6 | 30.00% | 2 | 2 |
| Human Resources | Male | 43 | 6 | 13.95% | 2 | 1 |
| Human Resources | Female + Male | 63 | 12 | 19.05% | 2 | 1 |
| Research & Development | Female | 379 | 43 | 11.35% | 6 | 1 |
| Research & Development | Male | 582 | 90 | 15.46% | 6 | 0 |
| Research & Development | Female + Male | 961 | 133 | 13.84% | 6 | 0 |
| Sales | Female | 189 | 38 | 20.11% | 3 | 1 |
| Sales | Male | 257 | 54 | 21.01% | 3 | 1 |
| Sales | Female + Male | 446 | 92 | 20.63% | 3 | 0 |
| HR + R&D | Female | 399 | 49 | 12.28% | 7 | 2 |
| HR + R&D | Male | 625 | 96 | 15.36% | 7 | 0 |
| HR + R&D | Female + Male | 1,024 | 145 | 14.16% | 7 | 0 |
| HR + Sales | Female | 209 | 44 | 21.05% | 4 | 2 |
| HR + Sales | Male | 300 | 60 | 20.00% | 4 | 1 |
| HR + Sales | Female + Male | 509 | 104 | 20.43% | 4 | 0 |
| R&D + Sales | Female | 568 | 81 | 14.26% | 8 | 0 |
| R&D + Sales | Male | 839 | 144 | 17.16% | 8 | 0 |
| R&D + Sales | Female + Male | 1,407 | 225 | 15.99% | 8 | 0 |
| 전체 | Female | 588 | 87 | 14.80% | 9 | 1 |
| 전체 | Male | 882 | 150 | 17.01% | 9 | 0 |
| 전체 | Female + Male | 1,470 | 237 | 16.12% | 9 | 0 |

예: HR + Female은 직무 2개(Human Resources 16명 중 이직 6명, Manager 4명 중 이직 0명)이고 둘 다 소표본입니다. HR만 선택하면 직무 2개(Human Resources 52명 · 이직 12명, Manager 11명 · 이직 0명)입니다.
모든 조합에서 점선은 16.12%입니다.

### 지시서 코드와 실제 파일의 차이

| 파일 | 지시서 위치 | 차이 |
|---|---|---|
| `components/group_chart.py` | 2-1 | `axis_labels`의 줄바꿈 판단(위 수정 1) |
| `tests/test_stage3_group_chart.py` | 2-2 | `test_small_mark_counts_toward_wrap` 추가(13 → 14개) |
| `components/filters.py` | 5-1 | `_options`, `reset_filters` 추가, `session_state.setdefault` 초깃값, “필터 초기화” 버튼 |
| `views/workforce.py` | 5-2 | `_section` 추가(전사 기준선), `company_summary`, 섹션 설명 문구, 직무 수 동적 문구, `cross_chart.render(df, company_summary)` |
| `tests/test_stage3_filters.py` | 5-3 | 기준선·표 합계 단언 추가, `test_reset_restores_all`, `test_job_role_description_matches_filtered_roles` 추가(7 → 9개) |

그 밖의 3단계 파일(`app.py`, `navigation.py`, `styles.css`, `cross_chart.py`, `test_stage2_shell.py`, `test_stage3_nav.py`, `test_stage3_workforce.py`, `test_stage3_jobs.py`)은 이 문서의 코드와 같습니다.
3단계 기준(`stage3_baseline.csv`) 대비 바뀐 기존 파일은 작업 1의 허용 파일 4개뿐입니다(`changed: 4, unexpected: 0`).

### 테스트 수 변화

| 시점 | 전체 | 내용 |
|---|--:|---|
| 지시서 계획(작업 5·6) | 236 | 필터 테스트 7개 |
| 작업 5 완료 | 237 | `test_reset_restores_all` 추가 |
| 작업 6 점검(C3-61) | 238 | `test_small_mark_counts_toward_wrap` 추가 |
| 최종 | **239** | `test_job_role_description_matches_filtered_roles` 추가 |

2026-11-24 문서화 작업 중 다시 실행한 결과도 `239 passed`, `check_setup.py`는 `RESULT: PASS`였습니다.
3단계 테스트는 5개 파일 41개입니다(nav 7, group_chart 14, workforce 5, jobs 6, filters 9).

### 최종 캡처

모두 `docs/captures/stage3/`에 있습니다. C3-31·C3-41의 보완 캡처는 필터 추가 전(작업 3·4 시점) 화면입니다.

| 화면 | 대표 캡처 | 크기 |
|---|---|---|
| Overview(2단계 C44와 본문 동일) | `c3_62_overview_unchanged.png` | 1440×1200 |
| 연령·근속·소득 전체 | `c3_31_profile_desktop_full.png` | 1440×1216 |
| 직무·교차 분석 전체(섹션 제목 포함) | `c3_41_jobs_desktop_full_title.png` | 1440×1535 |
| 필터 기본값 | `c3_51_filters_default.png` | 1440×900 |
| HR만 선택, 직무 수 “2개” | `c3_52_filters_updated_job_count.png` | 1440×1897 |
| 빈 선택 안내 | `c3_53_filter_empty.png` | 1440×900 |
| 최종 점검 테스트 | `c3_61_final_test.png` | 238 passed 시점 |

브라우저 점검(실제 Chrome): 360~1920px에서 가로 스크롤·글자 잘림·겹침 없음, 콘솔 오류 없음, 외부 요청 없음.
주소창에 `/workforce`를 직접 입력할 때 생기는 404 2건은 [위험 요소](#위험-요소)에 적은 Streamlit 동작이며 사이드바로 이동하면 생기지 않습니다.
