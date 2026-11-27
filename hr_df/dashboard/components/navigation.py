"""왼쪽 사이드바."""

from collections.abc import Sequence
from html import escape

import streamlit as st
from streamlit.navigation.page import Page

SOURCE_URL = "https://github.com/IBM/employee-attrition-aif360"
ODBL_URL = "https://opendatacommons.org/licenses/odbl/1-0/"
DBCL_URL = "https://opendatacommons.org/licenses/dbcl/1-0/"


def render_sidebar(pages: Sequence[Page], current: Page) -> None:
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
        # 데이터 출처·라이선스 고지(ODbL 4.3). 공식 주소는 새 탭 링크로 연다.
        st.html(
            '<div class="hr-side-note">IBM HR Analytics 공개 샘플 데이터<br>'
            "실제 기업의 인력 현황이 아닙니다."
            '<p class="hr-side-license">출처: Kaggle, '
            f"{_external_link(SOURCE_URL, 'IBM/employee-attrition-aif360')}<br>"
            f"데이터 라이선스: {_external_link(ODBL_URL, 'ODbL 1.0')} · "
            f"{_external_link(DBCL_URL, 'DbCL 1.0')}<br>"
            "코드: MIT License(데이터 제외)</p></div>"
        )


def _external_link(url: str, label: str) -> str:
    return (
        f'<a href="{escape(url)}" target="_blank" rel="noopener noreferrer">'
        f"{escape(label)}</a>"
    )
