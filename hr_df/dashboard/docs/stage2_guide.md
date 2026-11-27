# HR Analytics Dashboard 2단계 구현 지시서

디자인 시스템, 왼쪽 사이드바, Overview(KPI 4개, 부서별 이직 현황)를 작업 4개로 나눠 구현합니다.

> **2단계 완료 후 안내:** 이 문서의 코드 블록은 작업 당시의 지시 코드입니다. 작업 3·4 코드는 2단계 진행 중에 수정되었고, 작업 1·2의 일부 파일은 3단계에서 교체되었습니다.
> 파일을 다시 만들 때는 이 문서가 아니라 실제 파일을 기준으로 하세요. 바뀐 내용은 문서 끝의 [최종 상태와 변경 이력](#최종-상태와-변경-이력)에 있습니다.

## 목차

| 작업 | 내용 | 파일 수 | 완료 시 전체 테스트 | 캡처 |
|---|---|--:|--:|---|
| [0](#작업-0-시작-전-점검) | 시작 전 점검, 해시 저장 | 0 | 164 | C00 |
| [1](#작업-1-디자인-시스템) | 네이비·화이트 디자인 시스템 | 6 | 178 | C10~C11 |
| [2](#작업-2-앱과-사이드바) | 앱, 사이드바, 오류 처리 | 8 | 185 | C20~C23 |
| [3](#작업-3-kpi-카드-4개) | KPI 카드 4개 | 4 | 190 | C30~C32 |
| [4](#작업-4-부서별-이직-현황) | 부서별 차트 2개, 표 | 3 | 198 | C40~C44 |
| [5](#작업-5-최종-점검) | 반응형, 보존 확인 | 0 | 198 | C50~C52 |

## 범위와 규칙

- **새 파일만 만든다.** 기존 파일과 1단계 코드는 수정하지 않는다.
  예외는 2단계에서 새로 만든 `dashboard/views/overview.py` 하나이며, 작업 3과 4에서 전체 교체한다.
- 필터, Workforce Analysis, Machine Learning, HR Insights는 구현하지 않는다.
- 수치는 1단계의 `load_analysis_data`, `summarize_attrition`, `attrition_by`로만 계산한다.
  화면 코드에 수치를 직접 쓰지 않는다.
- 데이터에 없는 증감률, 추세, 기간을 표시하지 않는다.
- 한 작업의 테스트와 캡처를 마친 뒤 다음 작업으로 넘어간다.

## 완성 구조

```text
hr_df/dashboard/
├─ .streamlit/
│  ├─ config.toml              [1] 테마, 로컬 전용 서버
│  └─ .gitignore               [1] secrets 제외
├─ app.py                      [2] 진입점
├─ components/
│  ├─ __init__.py              [1]
│  ├─ theme.py                 [1] 색상 토큰, Plotly 공통 스타일
│  ├─ styles.css               [1] 전역 스타일
│  ├─ favicon.svg              [2] 로컬 파비콘
│  ├─ navigation.py            [2] 사이드바
│  ├─ layout.py                [2] 제목, 오류 안내
│  ├─ data_access.py           [2] 1단계 로더 + 캐시
│  ├─ formatting.py            [3] 숫자 형식
│  ├─ kpi.py                   [3] KPI 카드
│  └─ department.py            [4] 부서별 차트, 표
├─ views/
│  ├─ __init__.py              [2]
│  └─ overview.py              [2] → [3] → [4] 전체 교체
└─ tests/
   ├─ test_stage2_theme.py      [1]
   ├─ test_stage2_shell.py      [2]
   ├─ test_stage2_kpi.py        [3]
   └─ test_stage2_department.py [4]
```

의존 방향은 `app → views → components → core` 한 방향이다. `core`는 1단계 코드이며 읽기만 한다.

## 디자인 시스템

| 토큰 | 색 | 용도 |
|---|---|---|
| `navy` | `#0B1F3A` | 사이드바, 제목 |
| `navy-raised` | `#17335A` | 선택된 메뉴 |
| `page` | `#F4F7FB` | 본문 배경 |
| `surface` | `#FFFFFF` | 카드, 차트 배경 |
| `border` | `#DCE4EE` | 카드와 표의 경계 |
| `ink` / `ink-muted` | `#142033` / `#56657A` | 본문 / 보조 글자 |
| `retained` | `#2F62A8` | 재직 |
| `attrition` | `#D9652B` | 이직에만 사용 |

- 글꼴은 PC에 설치된 Noto Sans KR, 맑은 고딕 순으로 쓰고 웹 폰트는 받지 않는다.
- 카드는 모서리 12px, 테두리 1px이고 그림자는 없다.
- KPI는 본문 폭에 따라 4열, 2열, 1열로 바뀐다.
- 차트는 본문이 좁으면 1열로 내려간다.

## 공통 사용법

**파일 만들기:** VS Code 탐색기에서 `hr_df`를 우클릭하고 New File에 경로 전체(예: `dashboard/components/theme.py`)를 입력하면 폴더도 함께 생긴다.
코드 블록 전체를 붙여넣고 UTF-8로 저장한다.

**명령:** 모든 명령은 `hr_df` 폴더의 PowerShell에서 실행한다.

**앱 실행:** 브라우저는 자동으로 열리지 않으므로 `http://127.0.0.1:8501`에 직접 접속한다.
종료는 `Ctrl+C`이며, 작업마다 다시 실행한다.

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard\app.py
```

**화면 캡처:**

1. Chrome 또는 Edge에서 `F12`, `Ctrl+Shift+M`으로 기기 툴바를 연다.
2. Responsive를 선택하고 캡처 표에 적힌 가로×세로를 입력한 뒤 새로고침한다.
3. DevTools에서 `Ctrl+Shift+P`, `Capture screenshot`을 실행한다.

본문이 내부 스크롤이라 `Capture full size screenshot`으로는 아래쪽이 잘린다. 그래서 세로 크기를 크게 지정한다.
터미널과 탐색기는 `Win+Shift+S`로 캡처한다.

**보관:** `docs/captures/stage2/`에 표의 파일명으로 저장한다.
터미널과 오류 화면에는 Windows 사용자 경로가 보이므로 공개 전에 가린다.

---

## 작업 0. 시작 전 점검

### 지시

1단계가 정상인지 확인하고, 보존 대상 파일의 해시를 저장한다. 작업 1을 시작하기 전에 한 번만 실행한다.

```powershell
.\.venv\Scripts\python.exe dashboard\scripts\check_setup.py
.\.venv\Scripts\python.exe -m pytest -q
```

```powershell
New-Item -ItemType Directory -Force .pytest_tmp, docs\captures\stage2 | Out-Null
git ls-files --cached --others --exclude-standard |
  Where-Object { $_ -notlike 'dashboard/docs/*' -and $_ -notlike 'docs/captures/*' } |
  ForEach-Object { Get-FileHash -LiteralPath $_ } |
  Export-Csv .pytest_tmp\stage2_baseline.csv -NoTypeInformation -Encoding UTF8
"saved: $(@(Import-Csv .pytest_tmp\stage2_baseline.csv).Count)"
```

### 테스트

- [ ] `RESULT: PASS`
- [ ] `164 passed`
- [ ] `saved: 44`

### 캡처

| ID | 파일명 | 대상 | 보여야 할 것 |
|---|---|---|---|
| C00 | `c00_baseline.png` | 터미널 | PASS, 164 passed, saved: 44 |

---

## 작업 1. 디자인 시스템

### 지시

| 파일 | 할 일 | 주의 |
|---|---|---|
| `.streamlit/config.toml` | 테마와 서버 보안 설정 | 반드시 `dashboard` 안에 둔다. 그래야 실행 위치와 무관하게 적용된다 |
| `.streamlit/.gitignore` | `secrets.toml` 제외 | 루트 `.gitignore`는 수정하지 않는다 |
| `components/__init__.py` | 패키지 선언 | |
| `components/theme.py` | 색상 토큰의 기준, Plotly 공통 스타일 | 다른 Python 파일에 색을 직접 쓰지 않는다 |
| `components/styles.css` | 사이드바, 카드, 표, 반응형 | `var(--토큰)`만 쓴다 |
| `tests/test_stage2_theme.py` | 대비, 설정 일치, 보안 검사 | |

### 코드

#### 1-1. `dashboard/.streamlit/config.toml` (새 파일)

```toml
# 색을 바꿀 때는 components/theme.py와 함께 바꾼다. (테스트로 일치 여부 검사)

[server]
# 인사 데이터가 같은 네트워크에 노출되지 않도록 이 PC에서만 접속한다.
address = "127.0.0.1"
headless = true

[browser]
gatherUsageStats = false

[client]
toolbarMode = "minimal"
# 처리하지 못한 예외의 경로와 소스 코드를 화면에 노출하지 않는다.
showErrorDetails = "type"

[theme]
base = "light"
primaryColor = "#0B1F3A"
backgroundColor = "#F4F7FB"
secondaryBackgroundColor = "#FFFFFF"
textColor = "#142033"
borderColor = "#DCE4EE"
font = "'Noto Sans KR', 'Malgun Gothic', 'Segoe UI', sans-serif"

[theme.sidebar]
primaryColor = "#FFFFFF"
backgroundColor = "#0B1F3A"
secondaryBackgroundColor = "#17335A"
textColor = "#FFFFFF"
borderColor = "#17335A"
```

#### 1-2. `dashboard/.streamlit/.gitignore` (새 파일)

```text
# 루트 .gitignore의 규칙은 이 폴더에 적용되지 않으므로 별도로 제외한다.
secrets.toml
```

#### 1-3. `dashboard/components/__init__.py` (새 파일)

```python
"""대시보드 UI 구성 요소."""
```

#### 1-4. `dashboard/components/theme.py` (새 파일)

```python
"""디자인 토큰, 전역 스타일, Plotly 공통 레이아웃."""

from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

COLORS = {
    "navy": "#0B1F3A",
    "navy-raised": "#17335A",
    "page": "#F4F7FB",
    "surface": "#FFFFFF",
    "border": "#DCE4EE",
    "grid": "#E9EEF5",
    "ink": "#142033",
    "ink-muted": "#56657A",
    "on-navy": "#FFFFFF",
    "on-navy-muted": "#AFC0D6",
    "retained": "#2F62A8",
    "attrition": "#D9652B",  # 이직을 나타낼 때만 사용
}
FONT_FAMILY = "'Noto Sans KR', 'Malgun Gothic', 'Segoe UI', sans-serif"
CSS_PATH = Path(__file__).with_name("styles.css")
PLOTLY_CONFIG = {"displayModeBar": False, "responsive": True, "scrollZoom": False}


def build_css() -> str:
    variables = "".join(f"--{name}: {value};" for name, value in COLORS.items())
    return f":root {{{variables}}}\n{CSS_PATH.read_text(encoding='utf-8')}"


def apply_styles() -> None:
    st.html(f"<style>{build_css()}</style>")


def style_figure(figure: go.Figure, *, height: int = 280) -> go.Figure:
    figure.update_layout(
        template="none",
        height=height,
        margin={"l": 116, "r": 24, "t": 40, "b": 36},
        paper_bgcolor=COLORS["surface"],
        plot_bgcolor=COLORS["surface"],
        font={"family": FONT_FAMILY, "size": 12, "color": COLORS["ink"]},
        hoverlabel={
            "bgcolor": COLORS["navy"],
            "bordercolor": COLORS["navy"],
            "font": {"family": FONT_FAMILY, "color": COLORS["on-navy"]},
        },
        separators=".,",
    )
    # fixedrange: 모바일에서 스크롤이 차트 확대로 바뀌는 것을 막는다.
    figure.update_xaxes(
        fixedrange=True,
        gridcolor=COLORS["grid"],
        zeroline=False,
        tickfont={"color": COLORS["ink-muted"]},
    )
    figure.update_yaxes(fixedrange=True, showgrid=False, zeroline=False, ticklabelstandoff=8)
    return figure
```

#### 1-5. `dashboard/components/styles.css` (새 파일)

```css
/* 색은 theme.py의 토큰만 사용한다. */

/* 본문 */
[data-testid="stMainBlockContainer"] {
  max-width: 1280px;
  padding: 3.5rem 2rem 2rem;
}
[data-testid="stHeader"] { background: var(--page); }

/* 사이드바 */
[data-testid="stSidebar"] [data-testid="stPageLink"] a {
  min-height: 44px;
  padding: 0 12px;
  border-radius: 8px;
  background: var(--navy-raised);
}
[data-testid="stSidebar"] [data-testid="stPageLink"] a p {
  color: var(--on-navy);
  font-weight: 600;
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
  padding: 0 12px 0 36px; /* Overview 글자 시작선 */
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

#### 1-6. `dashboard/tests/test_stage2_theme.py` (새 파일)

```python
"""작업 1: 디자인 시스템."""

import re
import tomllib

import pytest

from components import theme
from core import config

SETTINGS = tomllib.loads(
    (config.PROJECT_ROOT / "dashboard" / ".streamlit" / "config.toml").read_text(encoding="utf-8")
)


def _luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    red, green, blue = [
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
        for value in channels
    ]
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


@pytest.mark.parametrize(
    "foreground,background,minimum",
    [
        ("ink", "surface", 4.5),
        ("ink", "page", 4.5),
        ("ink-muted", "surface", 4.5),
        ("ink-muted", "page", 4.5),
        ("on-navy", "navy", 4.5),
        ("on-navy", "navy-raised", 4.5),
        ("on-navy-muted", "navy", 4.5),
        ("retained", "surface", 3.0),
        ("attrition", "surface", 3.0),
    ],
)
def test_contrast(foreground, background, minimum):
    low, high = sorted([_luminance(theme.COLORS[name]) for name in (foreground, background)])
    assert (high + 0.05) / (low + 0.05) >= minimum


def test_config_matches_tokens():
    main, sidebar = SETTINGS["theme"], SETTINGS["theme"]["sidebar"]
    assert main["primaryColor"] == theme.COLORS["navy"]
    assert main["backgroundColor"] == theme.COLORS["page"]
    assert main["secondaryBackgroundColor"] == theme.COLORS["surface"]
    assert main["textColor"] == theme.COLORS["ink"]
    assert main["borderColor"] == theme.COLORS["border"]
    assert main["font"] == theme.FONT_FAMILY
    assert sidebar["backgroundColor"] == theme.COLORS["navy"]
    assert sidebar["textColor"] == theme.COLORS["on-navy"]


def test_server_is_private():
    assert SETTINGS["server"]["address"] == "127.0.0.1"
    assert SETTINGS["browser"]["gatherUsageStats"] is False
    assert SETTINGS["client"]["showErrorDetails"] == "type"


def test_css_uses_only_defined_tokens():
    source = theme.CSS_PATH.read_text(encoding="utf-8")
    assert set(re.findall(r"var\(--([\w-]+)\)", source)) <= set(theme.COLORS)
    assert not re.search(r"#[0-9a-fA-F]{6}\b", source), "CSS에 색상을 직접 쓰지 않는다."


def test_css_loads_nothing_external():
    css = theme.build_css()
    assert "http" not in css
    assert "@import" not in css


def test_secrets_are_ignored():
    path = config.PROJECT_ROOT / "dashboard" / ".streamlit" / ".gitignore"
    assert "secrets.toml" in path.read_text(encoding="utf-8").splitlines()
```

### 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest dashboard\tests\test_stage2_theme.py -v
.\.venv\Scripts\python.exe -m pytest -q
```

- [ ] 새 테스트 `14 passed`
- [ ] 전체 `178 passed`

### 캡처

이 작업에는 아직 화면이 없다.

| ID | 파일명 | 대상 | 보여야 할 것 |
|---|---|---|---|
| C10 | `c10_theme_test.png` | 터미널 | 대비 검사 9개를 포함한 14 passed |
| C11 | `c11_theme_files.png` | VS Code 탐색기 | `.streamlit`, `components` 폴더와 파일. 실제 저장 위치는 `dashboard/docs/captures/stage2/c11_theme_files.png` |

---

## 작업 2. 앱과 사이드바

### 지시

| 파일 | 할 일 | 주의 |
|---|---|---|
| `components/favicon.svg` | 로컬 파비콘 | `:material/...:` 파비콘은 Google 서버에 요청하므로 쓰지 않는다 |
| `components/navigation.py` | 브랜드, 메뉴, 데이터 출처 | 미구현 3개 화면은 링크 없이 “준비 중” |
| `components/layout.py` | 제목, 각주, 오류 안내 | 외부 문자열은 escape |
| `components/data_access.py` | 1단계 로더에 캐시 연결 | CSV가 바뀌면 다시 검증 |
| `views/__init__.py` | 패키지 선언 | 폴더명을 `pages`로 하지 않는다. Streamlit 자동 메뉴와 충돌한다 |
| `views/overview.py` | 제목과 데이터 연결 확인 | 임시 본문이며 작업 3에서 교체 |
| `app.py` | 페이지 설정, 스타일, 라우팅 | 계산 로직을 넣지 않는다 |
| `tests/test_stage2_shell.py` | 실행, 메뉴, 오류, 캐시 검사 | |

### 코드

#### 2-1. `dashboard/components/favicon.svg` (새 파일)

```xml
<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="7" fill="#0B1F3A"/>
  <rect x="7" y="16" width="4" height="9" rx="1" fill="#FFFFFF"/>
  <rect x="14" y="11" width="4" height="14" rx="1" fill="#FFFFFF"/>
  <rect x="21" y="7" width="4" height="18" rx="1" fill="#D9652B"/>
</svg>
```

#### 2-2. `dashboard/components/navigation.py` (새 파일)

```python
"""왼쪽 사이드바."""

from html import escape

import streamlit as st
from streamlit.navigation.page import Page

# 구현 전 화면은 링크 없이 표시한다.
PLANNED_PAGES = ("Workforce Analysis", "Machine Learning", "HR Insights")


def render_sidebar(overview_page: Page) -> None:
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
        st.page_link(overview_page, width="stretch")
        st.html(f'<ul class="hr-planned" aria-label="준비 중인 메뉴">{planned}</ul>')
        st.html(
            '<div class="hr-side-note">IBM HR Analytics 공개 샘플 데이터<br>'
            "실제 기업의 인력 현황이 아닙니다.</div>"
        )
```

#### 2-3. `dashboard/components/layout.py` (새 파일)

```python
"""화면 공통 제목과 안내."""

from html import escape

import streamlit as st

from core.exceptions import DashboardError


def page_header(title: str, description: str) -> None:
    st.html(
        f'<header class="hr-page-header"><h1>{escape(title)}</h1>'
        f"<p>{escape(description)}</p></header>"
    )


def section_header(title: str, description: str, *, level: int = 2) -> None:
    st.html(
        f'<div class="hr-section"><h{level}>{escape(title)}</h{level}>'
        f"<p>{escape(description)}</p></div>"
    )


def footnote(text: str) -> None:
    st.html(f'<p class="hr-footnote">{escape(text)}</p>')


def load_error(error: DashboardError) -> None:
    st.error("데이터를 불러오지 못해 지표를 표시하지 않았습니다.", icon=":material/error:")
    # 경로의 특수문자가 Markdown으로 해석되지 않도록 코드 블록으로 표시한다.
    st.code(str(error), language=None, wrap_lines=True)
```

#### 2-4. `dashboard/components/data_access.py` (새 파일)

```python
"""1단계 로더에 Streamlit 캐시를 연결한다."""

from pathlib import Path

import pandas as pd
import streamlit as st

from core import config, data


def _file_version(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except OSError:
        return None  # 안내 메시지는 1단계 로더가 만든다.
    return stat.st_mtime_ns, stat.st_size


@st.cache_data(show_spinner="데이터를 검증하는 중입니다.", max_entries=2)
def _load(versions: tuple[tuple[int, int] | None, ...]) -> pd.DataFrame:
    # versions는 파일이 바뀌면 캐시를 무효화하기 위한 키이다.
    return data.load_analysis_data()


def get_analysis_data() -> pd.DataFrame:
    paths = (config.RAW_DATA_PATH, config.PROCESSED_DATA_PATH)
    return _load(tuple(_file_version(path) for path in paths))
```

#### 2-5. `dashboard/views/__init__.py` (새 파일)

```python
"""대시보드 화면."""
```

#### 2-6. `dashboard/views/overview.py` (새 파일)

```python
"""Overview 화면."""

import streamlit as st

from components import data_access, layout
from core.exceptions import DashboardError


def render() -> None:
    layout.page_header("Overview", "전체 인력과 부서별 이직 현황")
    try:
        df = data_access.get_analysis_data()
    except DashboardError as error:
        layout.load_error(error)
        return

    st.success(f"데이터 검증 완료: {len(df):,}명", icon=":material/check_circle:")
```

#### 2-7. `dashboard/app.py` (새 파일)

```python
"""HR Analytics Dashboard 진입점. 실행: python -m streamlit run dashboard/app.py"""

from pathlib import Path

import streamlit as st

from components import navigation, theme
from views import overview

# :material/...: 파비콘은 Google 서버에 요청하므로 로컬 파일을 쓴다.
FAVICON = Path(__file__).parent / "components" / "favicon.svg"

st.set_page_config(
    page_title="HR Analytics",
    page_icon=str(FAVICON),
    layout="wide",
    initial_sidebar_state="auto",  # 데스크톱은 펼침, 모바일은 접힘
)
theme.apply_styles()

overview_page = st.Page(
    overview.render,
    title="Overview",
    icon=":material/dashboard:",
    url_path="overview",
    default=True,
)
current_page = st.navigation([overview_page], position="hidden")
navigation.render_sidebar(overview_page)
current_page.run()
```

#### 2-8. `dashboard/tests/test_stage2_shell.py` (새 파일)

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
    links = app.sidebar.get("page_link")
    assert [link.proto.label for link in links] == ["Overview"]

    sidebar = _html(app.sidebar)
    for name in ("Workforce Analysis", "Machine Learning", "HR Insights"):
        assert name in sidebar
    assert sidebar.count("준비 중</span>") == 3
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

### 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest dashboard\tests\test_stage2_shell.py -v
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m streamlit run dashboard\app.py
```

- [ ] 새 테스트 `7 passed`
- [ ] 전체 `185 passed`
- [ ] 실행 로그의 주소가 `127.0.0.1`이고 Network URL과 External URL이 없음
- [ ] “준비 중” 메뉴를 눌러도 이동하지 않음
- [ ] 사이드바 접기와 펼치기가 동작함

### 캡처

| ID | 파일명 | 크기 | 보여야 할 것 |
|---|---|---|---|
| C20 | `c20_shell_test.png` | 터미널 | 185 passed |
| C21 | `c21_shell_desktop.png` | 1440×900 | 네이비 사이드바, Overview 선택, 준비 중 3개, 검증 완료 1,470명 |
| C22 | `c22_shell_mobile.png` | 390×844 | 사이드바가 접힌 본문 |
| C23 | `c23_sidebar_mobile.png` | 390×844 | 왼쪽 위 `>>`로 펼친 사이드바 |

---

## 작업 3. KPI 카드 4개

### 지시

| 파일 | 할 일 | 주의 |
|---|---|---|
| `components/formatting.py` | 천 단위, 소수 2자리 | 반올림은 표시할 때만 |
| `components/kpi.py` | KPI 4개 | 증감률과 추세선 없음. 0명이면 이직률은 `—` |
| `views/overview.py` | **전체 교체** | 2단계에서 만든 파일이다 |
| `tests/test_stage2_kpi.py` | 보고서 수치와 대조 | |

| KPI | 계산 | 기대값 |
|---|---|--:|
| 전체 직원 수 | `employee_count` | 1,470명 |
| 이직자 수 | `attrition_count` | 237명 |
| 재직자 수 | `retained_count` | 1,233명 |
| 이직률 | `attrition_rate` | 16.12% |

### 코드

#### 3-1. `dashboard/components/formatting.py` (새 파일)

```python
"""표시 형식. 계산값은 여기서만 반올림한다."""

MISSING = "—"


def count(value: int) -> str:
    return f"{value:,}"


def percent(value: float | None) -> str:
    return MISSING if value is None else f"{value:.2f}%"
```

#### 3-2. `dashboard/components/kpi.py` (새 파일)

```python
"""상단 KPI 카드."""

from dataclasses import dataclass
from html import escape
from typing import Literal

import streamlit as st

from components import formatting
from core.analytics import AttritionSummary


@dataclass(frozen=True)
class Kpi:
    label: str
    value: str
    unit: str
    note: str
    tone: Literal["neutral", "retained", "attrition"] = "neutral"


def build_kpis(summary: AttritionSummary) -> tuple[Kpi, ...]:
    total = summary.employee_count
    retained_rate = summary.retained_count / total * 100 if total else None
    # 데이터에 기간 정보가 없으므로 증감률과 추세선은 넣지 않는다.
    return (
        Kpi("전체 직원 수", formatting.count(total), "명", "재직자와 이직자 합계"),
        Kpi(
            "이직자 수",
            formatting.count(summary.attrition_count),
            "명",
            "Attrition = Yes",
            "attrition",
        ),
        Kpi(
            "재직자 수",
            formatting.count(summary.retained_count),
            "명",
            f"전체의 {formatting.percent(retained_rate)}",
            "retained",
        ),
        Kpi(
            "이직률",
            formatting.percent(summary.attrition_rate),
            "",
            "이직자 수 ÷ 전체 직원 수",
            "attrition",
        ),
    )


def kpi_html(items: tuple[Kpi, ...]) -> str:
    cards = []
    for item in items:
        unit = f'<span class="hr-kpi-unit">{escape(item.unit)}</span>' if item.unit else ""
        cards.append(
            '<div class="hr-kpi">'
            f'<div class="hr-kpi-label"><span class="hr-dot hr-dot--{item.tone}"></span>'
            f"{escape(item.label)}</div>"
            f'<div class="hr-kpi-value">{escape(item.value)}{unit}</div>'
            f'<div class="hr-kpi-note">{escape(item.note)}</div>'
            "</div>"
        )
    return f'<div class="hr-kpi-wrap"><div class="hr-kpi-grid">{"".join(cards)}</div></div>'


def render(summary: AttritionSummary) -> None:
    st.html(kpi_html(build_kpis(summary)))
```

#### 3-3. `dashboard/views/overview.py` (전체 교체)

```python
"""Overview 화면."""

from components import data_access, kpi, layout
from core import analytics
from core.exceptions import DashboardError


def render() -> None:
    layout.page_header("Overview", "전체 인력과 부서별 이직 현황")
    try:
        df = data_access.get_analysis_data()
        summary = analytics.summarize_attrition(df)
    except DashboardError as error:
        layout.load_error(error)
        return

    kpi.render(summary)
```

#### 3-4. `dashboard/tests/test_stage2_kpi.py` (새 파일)

```python
"""작업 3: KPI 4개."""

from baselines import report_table
from streamlit.testing.v1 import AppTest

from components import kpi
from core import analytics, config


def test_kpis_match_report(analysis_df):
    rows = report_table("구분", "직원 수", "비율").rows
    reported = {label: (count.rstrip("명"), rate) for label, count, rate in rows}
    total, leaver, retained, rate = kpi.build_kpis(analytics.summarize_attrition(analysis_df))

    assert total.value == reported["합계"][0]
    assert leaver.value == reported["이직"][0]
    assert retained.value == reported["재직"][0]
    assert retained.note == f"전체의 {reported['재직'][1]}"
    assert rate.value == reported["이직"][1]


def test_labels_and_order(analysis_df):
    items = kpi.build_kpis(analytics.summarize_attrition(analysis_df))
    assert [item.label for item in items] == ["전체 직원 수", "이직자 수", "재직자 수", "이직률"]
    assert [item.tone for item in items] == ["neutral", "attrition", "retained", "attrition"]


def test_empty_is_not_zero_percent():
    total, _, retained, rate = kpi.build_kpis(analytics.AttritionSummary(0, 0, 0, None))
    assert total.value == "0"
    assert rate.value == "—"
    assert retained.note == "전체의 —"


def test_html_is_escaped():
    html = kpi.kpi_html((kpi.Kpi("<script>", "<b>", "&", "<i>"),))
    for unsafe in ("<script>", "<b>", "<i>"):
        assert unsafe not in html


def test_four_cards_on_screen():
    app = AppTest.from_file(config.PROJECT_ROOT / "dashboard" / "app.py", default_timeout=30).run()
    html = "".join(item.proto.body for item in app.main.get("html"))
    assert not app.exception
    assert html.count('class="hr-kpi"') == 4
    for value in ("1,470", "237", "1,233", "16.12%"):
        assert value in html
```

### 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest dashboard\tests\test_stage2_kpi.py -v
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m streamlit run dashboard\app.py
```

- [ ] 새 테스트 `5 passed`
- [ ] 전체 `190 passed`
- [ ] 1440px에서 4열, 1024px과 390px에서 2열
- [ ] 작업 2의 초록색 확인 문구가 사라짐

### 캡처

| ID | 파일명 | 크기 | 보여야 할 것 |
|---|---|---|---|
| C30 | `c30_kpi_test.png` | 터미널 | 190 passed |
| C31 | `c31_kpi_desktop.png` | 1440×900 | 4열, 1,470 / 237 / 1,233 / 16.12% |
| C32 | `c32_kpi_mobile.png` | 390×844 | 2×2, 숫자 잘림 없음 |

---

## 작업 4. 부서별 이직 현황

### 지시

| 파일 | 할 일 | 주의 |
|---|---|---|
| `components/department.py` | 이직률 차트, 인원 구성 차트, 표 | 단위가 다르므로 이중 축으로 합치지 않는다 |
| `views/overview.py` | **전체 교체** | 해석 주의 문구 포함 |
| `tests/test_stage2_department.py` | 보고서 수치와 대조 | |

- 두 차트와 표는 모두 이직률 내림차순으로 정렬한다.
- 이직률 숫자는 오른쪽에 정렬한다. 막대 끝에 두면 전체 평균선과 겹친다.
- 누적 막대의 구분 간격은 재직 쪽에서만 2px을 뺀다. 테두리로 만들면 모바일에서 HR의 이직 12명 구간이 사라진다.

| 부서 | 직원 | 이직 | 재직 | 이직률 |
|---|--:|--:|--:|--:|
| Sales | 446 | 92 | 354 | 20.63% |
| Human Resources | 63 | 12 | 51 | 19.05% |
| Research & Development | 961 | 133 | 828 | 13.84% |
| 전체 | 1,470 | 237 | 1,233 | 16.12% |

### 코드

#### 4-1. `dashboard/components/department.py` (새 파일)

```python
"""부서별 이직 현황: 이직률, 인원 구성, 수치 표."""

from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components import formatting, layout, theme
from core import analytics
from core.analytics import AttritionSummary

BAR_WIDTH = 0.36  # 막대 두께 24px 이하
AXIS_LABELS = {"Research & Development": "Research &<br>Development"}


def department_summary(df: pd.DataFrame) -> pd.DataFrame:
    result = analytics.attrition_by(df, "Department")
    result["retained_count"] = result["employee_count"] - result["attrition_count"]
    return result.sort_values("attrition_rate", ascending=False, ignore_index=True)


def _axis_labels(table: pd.DataFrame) -> list[str]:
    return [AXIS_LABELS.get(name, name) for name in table["Department"]]


def rate_figure(table: pd.DataFrame, overall_rate: float) -> go.Figure:
    rates = table["attrition_rate"].tolist()
    figure = go.Figure(
        go.Bar(
            x=rates,
            y=_axis_labels(table),
            orientation="h",
            width=BAR_WIDTH,
            marker={"color": theme.COLORS["attrition"]},
            customdata=table[["Department", "employee_count", "attrition_count"]].values.tolist(),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>이직률 %{x:.2f}%<br>"
                "이직 %{customdata[2]:,}명 / 전체 %{customdata[1]:,}명<extra></extra>"
            ),
        )
    )
    theme.style_figure(figure)
    figure.update_layout(barcornerradius=4, showlegend=False)
    figure.update_xaxes(range=[0, max(max(rates), overall_rate) * 1.5], visible=False)
    figure.update_yaxes(autorange="reversed")
    # 막대 끝에 숫자를 두면 전체 평균선과 겹치므로 오른쪽에 정렬한다.
    for label, rate in zip(_axis_labels(table), rates, strict=True):
        figure.add_annotation(
            xref="paper",
            x=1,
            y=label,
            text=formatting.percent(rate),
            xanchor="right",
            showarrow=False,
        )
    figure.add_vline(
        x=overall_rate,
        line={"color": theme.COLORS["ink-muted"], "width": 1, "dash": "dash"},
        annotation={
            "text": f"전체 {formatting.percent(overall_rate)}",
            "font": {"color": theme.COLORS["ink-muted"]},
            "yanchor": "bottom",
            "xanchor": "center",
            "y": 1.02,
        },
    )
    return figure


def composition_figure(table: pd.DataFrame) -> go.Figure:
    labels = _axis_labels(table)
    figure = go.Figure()
    for name, column, color in (
        ("재직", "retained_count", theme.COLORS["retained"]),
        ("이직", "attrition_count", theme.COLORS["attrition"]),
    ):
        figure.add_bar(
            name=name,
            x=table[column].tolist(),
            y=labels,
            orientation="h",
            width=BAR_WIDTH,
            marker={"color": color, "line": {"width": 0}},
            customdata=table[["Department", "employee_count"]].values.tolist(),
            hovertemplate=(
                f"<b>%{{customdata[0]}}</b><br>{name} %{{x:,}}명 / "
                "전체 %{customdata[1]:,}명<extra></extra>"
            ),
        )
    theme.style_figure(figure)
    # 막대 테두리로 간격을 만들면 12명 같은 얇은 구간이 가려지므로 재직 쪽에서만 2px을 비운다.
    for label, retained in zip(labels, table["retained_count"], strict=True):
        figure.add_shape(
            type="rect",
            xsizemode="pixel",
            xanchor=int(retained),
            x0=-2,
            x1=0,
            ysizemode="pixel",
            yanchor=label,
            y0=-14,
            y1=14,
            fillcolor=theme.COLORS["surface"],
            line={"width": 0},
        )
    # 좁은 이직 구간 안에 숫자를 넣으면 잘리므로 막대 끝에 총원을 표시한다.
    for label, total in zip(labels, table["employee_count"], strict=True):
        figure.add_annotation(
            x=int(total),
            y=label,
            text=f"{formatting.count(total)}명",
            xanchor="left",
            xshift=6,
            showarrow=False,
        )
    figure.update_layout(
        barmode="stack",
        legend={
            "orientation": "h",
            "traceorder": "normal",
            "x": 0,
            "y": 1.02,
            "yanchor": "bottom",
            "itemclick": False,
            "itemdoubleclick": False,
        },
    )
    figure.update_xaxes(range=[0, int(table["employee_count"].max()) * 1.32], visible=False)
    figure.update_yaxes(autorange="reversed")
    return figure


def table_html(table: pd.DataFrame, summary: AttritionSummary) -> str:
    def cells(total: int, left: int, retained: int, rate: float | None) -> str:
        values = [*map(formatting.count, (total, left, retained)), formatting.percent(rate)]
        return "".join(f"<td>{value}</td>" for value in values)

    body = "".join(
        f'<tr><th scope="row">{escape(row.Department)}</th>'
        f"{cells(row.employee_count, row.attrition_count, row.retained_count, row.attrition_rate)}"
        "</tr>"
        for row in table.itertuples()
    )
    total_cells = cells(
        summary.employee_count,
        summary.attrition_count,
        summary.retained_count,
        summary.attrition_rate,
    )
    headers = "".join(
        f'<th scope="col">{name}</th>' for name in ("부서", "직원", "이직", "재직", "이직률")
    )
    return (
        '<div class="hr-table-scroll"><table class="hr-table">'
        f"<thead><tr>{headers}</tr></thead><tbody>{body}</tbody>"
        f'<tfoot><tr><th scope="row">전체</th>{total_cells}</tr></tfoot>'
        "</table></div>"
    )


def render(df: pd.DataFrame, summary: AttritionSummary) -> None:
    layout.section_header("부서별 이직 현황", "이직률이 높은 순으로 표시합니다.")
    if df.empty or summary.attrition_rate is None:
        st.info("표시할 직원 데이터가 없습니다.")
        return

    table = department_summary(df)
    with st.container(key="department_charts"):
        left, right = st.columns(2)
        with left, st.container(key="card_department_rate"):
            layout.section_header("부서별 이직률", "점선은 전체 이직률", level=3)
            st.plotly_chart(
                rate_figure(table, summary.attrition_rate),
                theme=None,
                config=theme.PLOTLY_CONFIG,
                key="department_rate",
                alt="부서별 이직률 막대 차트. 수치는 아래 표에도 있습니다.",
            )
        with right, st.container(key="card_department_composition"):
            layout.section_header("부서별 인원 구성", "막대 끝 숫자는 부서 전체 인원", level=3)
            st.plotly_chart(
                composition_figure(table),
                theme=None,
                config=theme.PLOTLY_CONFIG,
                key="department_composition",
                alt="부서별 재직자와 이직자 누적 막대 차트. 수치는 아래 표에도 있습니다.",
            )

    with st.container(key="card_department_table"):
        layout.section_header("부서별 상세", "단위: 명, 이직률은 부서 인원 대비", level=3)
        st.html(table_html(table, summary))

    if table["is_small_sample"].any():
        st.warning("30명 미만인 부서가 있어 이직률 해석에 주의가 필요합니다.")
```

#### 4-2. `dashboard/views/overview.py` (전체 교체)

```python
"""Overview 화면."""

from components import data_access, department, kpi, layout
from core import analytics
from core.exceptions import DashboardError


def render() -> None:
    layout.page_header("Overview", "전체 인력과 부서별 이직 현황")
    try:
        df = data_access.get_analysis_data()
        summary = analytics.summarize_attrition(df)
    except DashboardError as error:
        layout.load_error(error)
        return

    kpi.render(summary)
    department.render(df, summary)
    layout.footnote(
        "데이터에 기간 정보가 없어 연간 이직률로 해석할 수 없습니다. "
        "부서마다 인원 규모가 다르며, 부서 간 차이는 인과관계나 통계적 유의성을 뜻하지 않습니다."
    )
```

#### 4-3. `dashboard/tests/test_stage2_department.py` (새 파일)

```python
"""작업 4: 부서별 이직 현황."""

import pytest
from baselines import assert_displayed, report_table
from streamlit.testing.v1 import AppTest

from components import department, theme
from core import analytics, config

REPORTED = report_table("부서", "직원 수", "이직자 수", "이직률").rows


@pytest.fixture
def table(analysis_df):
    return department.department_summary(analysis_df)


@pytest.fixture
def summary(analysis_df):
    return analytics.summarize_attrition(analysis_df)


def test_table_matches_report(table):
    assert list(table["Department"]) == [row[0] for row in REPORTED]
    for row, (_, total, leaver, rate) in zip(table.itertuples(), REPORTED, strict=True):
        assert_displayed(row.employee_count, total)
        assert_displayed(row.attrition_count, leaver)
        assert_displayed(row.attrition_rate, rate)
        assert row.retained_count + row.attrition_count == row.employee_count


def test_rate_figure_matches_report(table, summary):
    figure = department.rate_figure(table, summary.attrition_rate)
    bar = figure.data[0]
    assert [row[0] for row in bar.customdata] == [row[0] for row in REPORTED]
    labels = [note.text for note in figure.layout.annotations if note.xref == "paper"]
    assert labels == [row[3] for row in REPORTED]
    assert list(bar.x) == pytest.approx(table["attrition_rate"].tolist())
    assert bar.marker.color == theme.COLORS["attrition"]
    assert figure.layout.shapes[0].x0 == pytest.approx(summary.attrition_rate)
    assert figure.layout.xaxis.range[0] == 0


def test_composition_matches_table(table):
    figure = department.composition_figure(table)
    retained, leaver = figure.data
    assert (retained.name, leaver.name) == ("재직", "이직")
    assert list(retained.x) == table["retained_count"].tolist()
    assert list(leaver.x) == table["attrition_count"].tolist()
    assert retained.marker.color == theme.COLORS["retained"]
    assert leaver.marker.color == theme.COLORS["attrition"]
    assert figure.layout.barmode == "stack"
    assert figure.layout.xaxis.range[0] == 0


def test_thin_segment_is_not_covered_by_outline(table):
    figure = department.composition_figure(table)
    assert figure.data[1].marker.line.width == 0
    assert [gap.xanchor for gap in figure.layout.shapes] == table["retained_count"].tolist()
    assert all(gap.x0 < 0 and gap.x1 == 0 for gap in figure.layout.shapes)


def test_charts_share_order(table, summary):
    rate = department.rate_figure(table, summary.attrition_rate)
    composition = department.composition_figure(table)
    assert rate.data[0].y == composition.data[0].y == composition.data[1].y
    assert rate.layout.yaxis.autorange == composition.layout.yaxis.autorange == "reversed"


def test_html_table(table, summary):
    html = department.table_html(table, summary)
    assert "Research &amp; Development" in html
    for name, total, leaver, rate in REPORTED:
        for value in (f"<td>{total}</td>", f"<td>{leaver}</td>", f"<td>{rate}</td>"):
            assert value in html, name
    assert "<td>1,470</td><td>237</td><td>1,233</td><td>16.12%</td>" in html


def test_html_table_is_escaped(table, summary):
    changed = table.assign(Department="<script>")
    assert "<script>" not in department.table_html(changed, summary)


def test_overview_renders_everything():
    app = AppTest.from_file(config.PROJECT_ROOT / "dashboard" / "app.py", default_timeout=30).run()
    html = "".join(item.proto.body for item in app.main.get("html"))
    assert not app.exception
    assert not app.warning
    assert len(app.get("plotly_chart")) == 2
    assert html.count('class="hr-kpi"') == 4
    assert html.count('class="hr-table"') == 1
    assert "연간 이직률로 해석할 수 없습니다" in html
```

### 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest dashboard\tests\test_stage2_department.py -v
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m streamlit run dashboard\app.py
```

- [ ] 새 테스트 `8 passed`
- [ ] 전체 `198 passed`
- [ ] 화면 수치가 위 표와 일치
- [ ] 막대에 마우스를 올리면 부서, 비율, 인원이 표시됨
- [ ] 모바일에서 HR의 주황색 이직 구간이 보임

### 캡처

| ID | 파일명 | 크기 | 보여야 할 것 |
|---|---|---|---|
| C40 | `c40_department_test.png` | 터미널 | 198 passed |
| C41 | `c41_overview_desktop.png` | 1440×1200 | KPI, 차트 2열, 표, 주의 문구 |
| C42 | `c42_overview_tablet.png` | 1024×1760 | KPI 2열, 차트 1열 |
| C43 | `c43_overview_mobile.png` | 390×1700 | 가로 스크롤 없음, HR 이직 구간 보임 |
| C44 | `c44_tooltip.png` | 1440×900 | Sales 툴팁: 20.63%, 92명 / 446명. `Win+Shift+S`로 캡처 |

---

## 작업 5. 최종 점검

### 5-1. 보존 확인

```powershell
$changed = @(Import-Csv .pytest_tmp\stage2_baseline.csv | Where-Object {
  -not (Test-Path -LiteralPath $_.Path) -or (Get-FileHash -LiteralPath $_.Path).Hash -ne $_.Hash
})
"changed: $($changed.Count)"
$changed | ForEach-Object { $_.Path }
```

- [ ] `changed: 0`

Jupyter에 열어 둔 노트북이 자동 저장되면 여기에 나타날 수 있으므로, 작업 중에는 해당 탭을 닫아 둔다.

### 5-2. 전체 테스트

```powershell
.\.venv\Scripts\python.exe dashboard\scripts\check_setup.py
.\.venv\Scripts\python.exe -m pytest -q
```

- [ ] `RESULT: PASS`
- [ ] `198 passed`

### 5-3. 오류 화면

원본을 건드리지 않도록 `hr.csv`가 없는 사본으로 확인한다. `http://127.0.0.1:8502`에 접속하고, 확인 후 `Ctrl+C`로 종료한다.

```powershell
$demo = ".pytest_tmp\error_demo_$(Get-Date -Format HHmmss)"
New-Item -ItemType Directory -Force "$demo\data" | Out-Null
Copy-Item dashboard -Destination $demo -Recurse
Copy-Item data\processed -Destination "$demo\data" -Recurse
.\.venv\Scripts\python.exe -m streamlit run "$demo\dashboard\app.py" --server.port 8502
```

- [ ] 오류 안내와 누락된 파일 경로가 보이고, KPI와 차트는 보이지 않음
- [ ] 사이드바는 유지됨

### 캡처

| ID | 파일명 | 크기 | 보여야 할 것 |
|---|---|---|---|
| C50 | `c50_preserved.png` | 터미널 | changed: 0 |
| C51 | `c51_final_test.png` | 터미널 | PASS, 198 passed |
| C52 | `c52_error_state.png` | 1440×900 | 오류 안내. 경로는 공개 전 가림 |

### 완료 보고 양식

```text
[2단계 완료]
- 전체 테스트: ___ passed
- 보존 확인: changed: ___
- 캡처: C00~C52 중 ___개 (누락: ___)
- 지시서와 다르게 구현한 부분: ___
- 3단계 승인 여부: 대기
```

---

## 문제 해결

| 증상 | 원인 | 조치 |
|---|---|---|
| `No module named streamlit` | 전역 Python 또는 Anaconda로 실행 | `.\.venv\Scripts\python.exe -m ...`로 실행 |
| `No module named components` | 파일 위치 오류 | `dashboard/components/__init__.py` 확인 |
| 테마가 기본색 | 설정 파일 위치 오류 | `dashboard/.streamlit/config.toml`로 옮기고 재시작 |
| `Port 8501 is not available` | 이전 서버가 실행 중 | 해당 터미널에서 `Ctrl+C` 또는 `--server.port 8503` |
| 화면에 예외 종류만 표시 | 보안 설정 | 상세 traceback은 실행한 터미널에서 확인 |
| 보고서·노트북 대조 테스트 실패 | 기준 파일 변경 | 코드를 고치기 전에 5-1로 변경된 파일 확인 |
| 모델 해시 오류 | 06번 노트북 재실행으로 모델 덮어씀 | 해시를 바꾸지 말고 Git의 모델 파일과 비교 |

## 알아둘 점

- 1단계 `dashboard/README.md`에는 “화면은 아직 없습니다”가 남는다. 수정 금지 원칙에 따라 그대로 두며, 갱신하려면 별도 승인이 필요하다. (3단계 완료 후 문서화 작업에서 갱신함)
- 초기 계획의 Overview 필터와 “주요 관찰”은 이번 승인 범위가 아니어서 제외했다.
- `git add .`는 커밋 전인 07번 노트북 변경까지 포함하므로 쓰지 않는다.
- CSS 일부가 Streamlit 내부 `data-testid`를 사용한다. Streamlit 버전을 올리면 캡처를 다시 비교한다.

---

## 최종 상태와 변경 이력

3단계 완료 후 문서화 작업(2026-11-24)에서 이 문서의 코드와 실제 파일을 한 줄씩 비교한 결과입니다. 위의 작업 0~5 내용은 당시 지시서 그대로 보존합니다.

### 2단계 진행 중 수정된 코드

3단계 시작 전 기준(`.pytest_tmp/stage3_baseline.csv`)에 이미 반영되어 있던 변경입니다. 기능은 같고 안전성과 검증이 강화되었습니다.

| 파일 | 지시서(작업 3·4) | 실제 파일 | 이유 |
|---|---|---|---|
| `components/kpi.py` | `hr-dot--{item.tone}` | `hr-dot--{escape(item.tone)}` | class 속성에 들어가는 값도 escape |
| `components/department.py` | 이직률 축 끝 `× 1.5` | `× 1.65` | 좁은 화면(320px)에서 오른쪽 숫자와 막대가 겹치지 않도록 여백 확보 |
| `tests/test_stage2_kpi.py` | 라벨·값·단위 escape 확인 | `tone`에 따옴표를 넣어 새 속성이 생기지 않는지까지 확인 | 위 `kpi.py` 수정 검증 |
| `tests/test_stage2_department.py` | 수치·축 범위 확인 | 축 여백(최대값 × 1.6 이상), 기준선 글자, `customdata`, 툴팁 문구, 표 행 단위 대조, 0명·30명 미만 처리 추가 | 열이 뒤바뀌거나 빈 데이터일 때의 오류를 잡기 위함 |

테스트 함수 수는 바뀌지 않았습니다(2단계 테스트 34개, 2단계 완료 시 전체 198 passed).

### 3단계에서 교체된 2단계 파일

아래 4개는 3단계 작업 1에서 전체 교체되었습니다. 최신 코드는 [3단계 지시서](stage3_guide.md#작업-1-페이지-구조와-사이드바)와 실제 파일을 봅니다.

| 파일 | 바뀐 내용 |
|---|---|
| `dashboard/app.py` | `st.navigation`으로 Overview·Workforce 페이지 등록, `/overview` 숨김 페이지 |
| `components/navigation.py` | 현재 화면을 `aria-current="page"` 요소로 표시, Workforce 링크 |
| `components/styles.css` | 현재 메뉴만 강조, KPI 높이 통일, Workforce 2열 카드 |
| `tests/test_stage2_shell.py` | `test_only_overview_is_a_link`의 단언을 3단계 메뉴 기준으로 변경(함수 수 유지) |

그 밖의 2단계 파일(`theme.py`, `layout.py`, `data_access.py`, `formatting.py`, `views/overview.py`, `.streamlit/` 등)은 이 문서의 코드와 같습니다.
Overview 본문은 3단계 이후에도 2단계와 픽셀 단위로 같습니다(C3-62와 C44 비교).

### 실제 캡처 파일

작업 4의 캡처는 계획과 다른 이름·구성으로 저장되었습니다. 계획에 있던 툴팁 캡처(`c44_tooltip.png`)와 태블릿 캡처(`c42_overview_tablet.png`)는 파일로 남아 있지 않습니다.

| ID | 계획한 파일 | 실제 파일 | 크기 |
|---|---|---|---|
| C41 | `c41_overview_desktop.png` | `c41_department_desktop.png` | 1440×900 |
| C42 | `c42_overview_tablet.png` | `c42_department_mobile.png` | 390×1700 |
| C43 | `c43_overview_mobile.png` | `c43_department_table.png` | 1076×309 |
| C44 | `c44_tooltip.png` | `c44_overview_full.png` | 1440×1200 |

C11은 다른 캡처와 달리 `dashboard/docs/captures/stage2/c11_theme_files.png`에 저장되어 있습니다. 파일은 옮기지 않았고, 문서의 참조 경로를 실제 위치로 맞췄습니다.
나머지 2단계 캡처는 모두 `docs/captures/stage2/`에 계획한 이름으로 있습니다.

공개용 저장소의 `c52_error_state.png`와 `c10_theme_test.png`는 로컬 경로 부분을 가린 이미지입니다. 경로 외의 내용은 원본 캡처와 같습니다.
