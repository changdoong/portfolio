"""HR Analytics Dashboard 진입점. 실행: python -m streamlit run dashboard/app.py"""

from pathlib import Path

import streamlit as st

from components import navigation, theme
from views import hr_insights, machine_learning, overview, workforce

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
ml_page = st.Page(machine_learning.render, title="Machine Learning", url_path="machine-learning")
insights_page = st.Page(hr_insights.render, title="HR Insights", url_path="hr-insights")
menu = [overview_page, workforce_page, ml_page, insights_page]


def _redirect_to_overview() -> None:
    # 2단계에서 안내한 /overview 주소로 들어와도 Overview를 보여 준다.
    st.switch_page(overview_page)


legacy_overview = st.Page(
    _redirect_to_overview, title="Overview", url_path="overview", visibility="hidden"
)
current_page = st.navigation([*menu, legacy_overview], position="hidden")
navigation.render_sidebar(menu, current_page)
current_page.run()
