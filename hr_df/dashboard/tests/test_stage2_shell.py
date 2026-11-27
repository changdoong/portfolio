"""작업 2: 앱 셸, 사이드바, 오류 화면."""

import re

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from components import data_access, layout
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


@pytest.mark.requires_data
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
    # Stage 5·6: Machine Learning과 HR Insights도 구현되어 링크가 되고 "준비 중" 표시는 없어졌다.
    links = app.sidebar.get("page_link")
    assert [link.proto.label for link in links] == ["Workforce Analysis", "Machine Learning", "HR Insights"]

    sidebar = _html(app.sidebar)
    assert '<div class="hr-nav-current" aria-current="page">Overview</div>' in sidebar
    assert "준비 중" not in sidebar
    # 메뉴 이동은 page_link로만 한다. Stage 7-7부터 사이드바의 <a>는 출처·라이선스 공식 외부 링크 3개뿐이다.
    anchors = re.findall(r"<a [^>]*>", sidebar)
    assert anchors == [
        f'<a href="{url}" target="_blank" rel="noopener noreferrer">'
        for url in (
            "https://github.com/IBM/employee-attrition-aif360",
            "https://opendatacommons.org/licenses/odbl/1-0/",
            "https://opendatacommons.org/licenses/dbcl/1-0/",
        )
    ]
    nav_html = sidebar.split('<div class="hr-side-note">', 1)[0]
    assert "<a " not in nav_html


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
    # Stage 4C.1: 화면에는 절대 경로를 파일 이름으로 바꾼 문장을 보인다. 경로 외 내용은 그대로다.
    assert layout.public_message(str(error)) in app.code[0].value
    assert "C:/data" not in app.code[0].value
    assert "1,470" not in _html(app.main)
    assert not app.success
    assert app.sidebar.get("page_link"), "오류가 나도 사이드바는 유지한다."


@pytest.mark.requires_data
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
