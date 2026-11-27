"""Workforce Analysis 화면."""

import pandas as pd
import streamlit as st

from components import cross_chart, data_access, filters, formatting, group_chart, layout, theme
from core import analytics
from core.analytics import AttritionSummary
from core.exceptions import DashboardError


def income_ranges(df: pd.DataFrame) -> str:
    """전사 기준 월 소득 사분위의 실제 범위. 필터 전 전체 데이터로 계산한다."""
    ranges = df.groupby("IncomeGroup", observed=True)["MonthlyIncome"].agg(["min", "max"])
    return " · ".join(
        f"{group} {formatting.count(row['min'])}~{formatting.count(row['max'])}"
        for group, row in ranges.iterrows()
    )


def _section(
    df: pd.DataFrame,
    summary: AttritionSummary,
    reference_rate: float,
    *,
    column: str,
    title: str,
    header: str,
    description: str,
    key: str,
    sort_by_rate: bool = False,
) -> None:
    """group_chart.render_section과 같은 구성이다.
    점선은 전사 평균(reference_rate)으로 고정하고, 표의 합계 행은 선택한 집단(summary)으로 둔다.
    """
    table = group_chart.group_table(df, column, sort_by_rate=sort_by_rate)
    with st.container(key=f"card_{key}"):
        layout.section_header(title, description, level=3)
        if table.empty:
            st.info("표시할 직원 데이터가 없습니다.")
            return
        st.plotly_chart(
            group_chart.rate_figure(table, column, reference_rate),
            theme=None,
            config=theme.PLOTLY_CONFIG,
            key=f"chart_{key}",
            alt=f"{title} 막대 차트. 수치는 아래 표에 있습니다.",
        )
        if table["is_small_sample"].any():
            layout.footnote(group_chart.SMALL_NOTE)
        with st.expander("수치 표 보기"):
            st.html(group_chart.table_html(table, column, header, summary))


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
    # 점선은 필터와 무관하게 전사 평균이다.
    company_summary = analytics.summarize_attrition(company)
    reference = company_summary.attrition_rate
    layout.footnote(
        f"필터 {filters.describe(selected)} · 분석 대상 {formatting.count(summary.employee_count)}명"
        f"(전체 {formatting.count(len(company))}명 중) · "
        f"이직 {formatting.count(summary.attrition_count)}명 · "
        f"이직률 {formatting.percent(summary.attrition_rate)}"
    )
    if df.empty:
        st.info("선택한 조건에 해당하는 직원이 없습니다. 필터를 하나 이상 선택하세요.")
        return

    layout.section_header(
        "연령·근속·보상",
        f"범주 순서대로 표시합니다. 점선은 전사 평균 이직률({formatting.percent(reference)})입니다.",
    )
    with st.container(key="grid_profile"):
        left, right = st.columns(2)
        with left:
            _section(
                df, summary, reference, column="AgeGroup", title="연령대별 이직률", header="연령대",
                description="연령 구간은 왼쪽 경계를 포함합니다.", key="age",
            )
        with right:
            _section(
                df, summary, reference, column="TenureGroup", title="근속연수별 이직률", header="근속",
                description="현 회사 근속연수(YearsAtCompany) 기준입니다.", key="tenure",
            )
    with st.container(key="grid_pay"):
        left, right = st.columns(2)
        with left:
            _section(
                df, summary, reference, column="IncomeGroup", title="월 소득 구간별 이직률", header="소득 구간",
                description="전사 기준 사분위입니다. 통화 단위는 원자료에 없습니다.", key="income",
            )
            layout.footnote(f"구간 범위(전사 기준): {income_ranges(company)}")
        with right:
            _section(
                df, summary, reference, column="OverTime", title="초과근무 여부별 이직률", header="초과근무",
                description="OverTime 값(Yes/No) 기준입니다.", key="overtime",
            )

    layout.section_header("직무", "이직률이 높은 순으로 표시합니다.")
    _section(
        df, summary, reference, column="JobRole", title="직무별 이직률", header="직무",
        description=f"{df['JobRole'].nunique()}개 직무를 이직률 순으로 정렬했습니다.",  # 필터 후 남은 직무 수
        key="jobrole", sort_by_rate=True,
    )
    cross_chart.render(df, company_summary)  # 점선과 설명 문구의 평균은 전사 기준
    layout.footnote(
        "집단 간 차이는 연관성이며 인과관계나 통계적 유의성을 뜻하지 않습니다. "
        "데이터에 기간 정보가 없어 연간 이직률로 해석할 수 없습니다."
    )
