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
    from views import hr_insights, machine_learning, overview, workforce

    theme.apply_styles()
    pages = [
        st.Page(overview.render, title="Overview", default=True),
        st.Page(workforce.render, title="Workforce Analysis", url_path="workforce"),
        st.Page(machine_learning.render, title="Machine Learning", url_path="machine-learning"),
        st.Page(hr_insights.render, title="HR Insights", url_path="hr-insights"),
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
    assert [link.proto.label for link in app.sidebar.get("page_link")] == [
        "Workforce Analysis",
        "Machine Learning",
        "HR Insights",
    ]


def test_workforce_is_current_page():
    app = AppTest.from_function(_workforce_app, default_timeout=30).run()
    sidebar = _html(app.sidebar)
    assert not app.exception
    assert sidebar.count('aria-current="page"') == 1
    assert '<div class="hr-nav-current" aria-current="page">Workforce Analysis</div>' in sidebar
    assert [link.proto.label for link in app.sidebar.get("page_link")] == [
        "Overview",
        "Machine Learning",
        "HR Insights",
    ]
    assert "준비 중" not in sidebar  # Stage 5·6에서 두 화면을 구현했다.

    escaped = _html(AppTest.from_function(_escaped_title_app, default_timeout=30).run().sidebar)
    assert "&lt;b&gt;Overview&lt;/b&gt;" in escaped and "<b>Overview" not in escaped


@pytest.mark.requires_data
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
    assert 'url_path="machine-learning"' in source
    assert 'url_path="hr-insights"' in source
    assert "st.switch_page(overview_page)" in source


def test_only_current_menu_is_highlighted():
    css = theme.CSS_PATH.read_text(encoding="utf-8")
    link_rule = css.split('[data-testid="stPageLink"] a {', 1)[1].split("}", 1)[0]
    assert "background" not in link_rule, "모든 링크를 선택된 것처럼 칠하지 않는다."
    current_rule = css.split(".hr-nav-current {", 1)[1].split("}", 1)[0]
    assert "border-left: 3px solid var(--on-navy)" in current_rule, "색 외의 선택 표시"


def test_sidebar_license_links():
    # Stage 7-7: 출처와 두 데이터 라이선스는 공식 주소로 새 탭에서 연다. 코드 라이선스 범위는 그대로다.
    app = AppTest.from_file(APP_PATH, default_timeout=30).run()
    sidebar = _html(app.sidebar)
    assert not app.exception
    for url, label in [
        ("https://github.com/IBM/employee-attrition-aif360", "IBM/employee-attrition-aif360"),
        ("https://opendatacommons.org/licenses/odbl/1-0/", "ODbL 1.0"),
        ("https://opendatacommons.org/licenses/dbcl/1-0/", "DbCL 1.0"),
    ]:
        assert (
            f'<a href="{url}" target="_blank" rel="noopener noreferrer">{label}</a>' in sidebar
        )
    assert "출처: Kaggle, " in sidebar
    assert "코드: MIT License(데이터 제외)" in sidebar
    css = theme.CSS_PATH.read_text(encoding="utf-8")
    link_rule = css.split(".hr-side-license a {", 1)[1].split("}", 1)[0]
    assert "color: var(--on-navy)" in link_rule and "underline" in link_rule


def test_kpi_rows_have_equal_height():
    css = theme.CSS_PATH.read_text(encoding="utf-8")
    grid_rule = css.split(".hr-kpi-grid {", 1)[1].split("}", 1)[0]
    assert "grid-auto-rows: 1fr" in grid_rule
