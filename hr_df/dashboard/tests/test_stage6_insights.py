"""Stage 6: HR Insights 화면. 집계는 보고서 4장·4.8절의 표와 대조한다."""

import pytest
import streamlit as st
from baselines import assert_displayed, report_table, report_text
from streamlit.testing.v1 import AppTest

from components import cards, layout
from core import data, insights
from core.exceptions import DataLoadError
from views import hr_insights


@pytest.fixture(autouse=True)
def clear_cache():
    st.cache_data.clear()
    yield
    st.cache_data.clear()


def _insights_page():
    from views import hr_insights

    hr_insights.render()


def _html(app: AppTest) -> str:
    return "\n".join(item.proto.body for item in app.main.get("html"))


# 화면 집단 이름 -> (보고서 표 머리글, 행을 찾는 앞쪽 칸)
REPORT_ROWS = {
    "초과근무 함": (("변수", "집단", "직원 수", "이직자 수", "이직률"), ("초과근무", "Yes")),
    "초과근무 안 함": (("변수", "집단", "직원 수", "이직자 수", "이직률"), ("초과근무", "No")),
    "근속 0~1년": (("근속 구간", "직원 수", "이직자 수", "이직률"), ("0~1년",)),
    "근속 10년 초과": (("근속 구간", "직원 수", "이직자 수", "이직률"), ("10년 초과",)),
    "25세 미만": (("연령대", "직원 수", "이직자 수", "이직률"), ("25세 미만",)),
    "35~44세": (("연령대", "직원 수", "이직자 수", "이직률"), ("35~44세",)),
    "월 소득 하위 25%(Q1)": (("소득 구간", "직원 수", "이직자 수", "이직률"), ("Q1 - Low",)),
    "월 소득 상위 25%(Q4)": (("소득 구간", "직원 수", "이직자 수", "이직률"), ("Q4 - High",)),
    "직무: Sales Representative": (("직무", "직원 수", "이직자 수", "이직률"), ("Sales Representative",)),
    "미혼": (("구분", "집단", "직원 수", "이직자 수", "이직률"), ("결혼 여부", "미혼")),
    "워라밸 1점": (("변수", "집단", "직원 수", "이직자 수", "이직률"), ("워라밸", "1")),
    "근무 환경 만족도 1점": (("변수", "집단", "직원 수", "이직자 수", "이직률"), ("근무 환경 만족도", "1")),
    "직무 만족도 1점": (("변수", "집단", "직원 수", "이직자 수", "이직률"), ("직무 만족도", "1")),
}


def test_risk_groups_match_report(analysis_df):
    risk = insights.risk_table(analysis_df)
    assert set(risk["label"]) == set(REPORT_ROWS)
    for row in risk.itertuples():
        header, key = REPORT_ROWS[row.label]
        table = report_table(*header)
        matched = [r for r in table.rows if tuple(r[: len(key)]) == key]
        assert len(matched) == 1, row.label
        employees, leavers, rate = matched[0][len(key):]
        assert_displayed(row.employee_count, employees)
        assert_displayed(row.attrition_count, leavers)
        assert_displayed(row.attrition_rate, rate)


def test_risk_context_columns(analysis_df):
    risk = insights.risk_table(analysis_df).set_index("label")
    overall = 237 / 1470 * 100
    row = risk.loc["초과근무 함"]
    assert row["diff_pp"] == pytest.approx(127 / 416 * 100 - overall)
    assert row["ratio"] == pytest.approx((127 / 416 * 100) / overall)
    assert row["leaver_share"] == pytest.approx(127 / 237 * 100)
    assert (risk.loc[risk["kind"] == "high", "diff_pp"] > 0).all()
    assert (risk.loc[risk["kind"] == "low", "diff_pp"] < 0).all()


def test_role_tenure_matches_report_4_8(analysis_df):
    table = insights.tenure_comparison(analysis_df)
    role = table[table["basis"].str.startswith("현 직무")].reset_index(drop=True)
    company = table[table["basis"].str.startswith("회사")].reset_index(drop=True)
    expected = report_table("현 직무 근속", "직원 수", "이직자 수", "이직률", "같은 구간의 회사 근속 이직률(4.4)")
    assert len(expected.rows) == len(role) == 5
    for index, (_, employees, leavers, rate, company_rate) in enumerate(expected.rows):
        assert_displayed(role.loc[index, "employee_count"], employees)
        assert_displayed(role.loc[index, "attrition_count"], leavers)
        assert_displayed(role.loc[index, "attrition_rate"], rate)
        assert_displayed(company.loc[index, "attrition_rate"], company_rate)


def test_overtime_gap_matches_report_cross_table(analysis_df):
    gaps = insights.overtime_gap_by_role(analysis_df).set_index("JobRole")
    table = report_table("직무", "초과근무", "직원 수", "이직자 수", "이직률", "비고")
    assert len(table.rows) == 18
    for role, overtime, employees, leavers, rate, note in table.rows:
        suffix = "yes" if overtime == "Yes" else "no"
        assert_displayed(gaps.loc[role, f"count_{suffix}"], employees)
        assert_displayed(gaps.loc[role, f"left_{suffix}"], leavers)
        assert_displayed(gaps.loc[role, f"rate_{suffix}"], rate)
        if note == "30명 미만":
            assert gaps.loc[role, "is_small_sample"]
    # 보고서 4.8: 9개 직무 중 8개에서 초과근무 집단이 더 높고, 예외는 Healthcare Representative
    assert int((gaps["gap_pp"] > 0).sum()) == 8
    assert gaps.index[gaps["gap_pp"] <= 0].tolist() == ["Healthcare Representative"]
    assert gaps["gap_pp"].is_monotonic_decreasing


def test_department_profiles_match_report(analysis_df):
    profiles = {p.name: p for p in insights.department_profiles(analysis_df)}
    text = report_text()
    for name, profile in profiles.items():
        shown = f"{profile.diff_pp:+.2f}%p".replace("-", "−")
        assert f"{name} {shown}" in text, name
    # 부서 안 30명 이상 직무 중 이직률 1위와 근속 0~1년 소집단
    assert profiles["Sales"].top_role == "Sales Representative"
    assert profiles["Research & Development"].top_role == "Laboratory Technician"
    assert profiles["Human Resources"].early_count == 5


def test_income_medians_match_report(analysis_df):
    medians = insights.income_medians(analysis_df)
    table = report_table("변수", "재직 직원 평균", "이직 직원 평균", "재직 직원 중앙값", "이직 직원 중앙값")
    row = next(r for r in table.rows if r[0] == "MonthlyIncome")
    assert_displayed(medians["No"], row[3])
    assert_displayed(medians["Yes"], row[4])


def test_insight_sentences_use_data(analysis_df):
    tenure, _ = hr_insights.tenure_insight(analysis_df)
    assert "215명 중 75명이 이직해 이직률 34.88%" in tenure.finding
    assert "4.29배" in tenure.finding  # 34.88 / 8.13
    income, _ = hr_insights.income_insight(analysis_df)
    assert "1,009~2,911" in income.finding and "3,202" in income.finding and "5,204" in income.finding
    overtime, _ = hr_insights.overtime_insight(analysis_df)
    assert "9개 직무 중 8개" in overtime.finding
    assert any("Healthcare Representative" in line for line in overtime.interpretation)
    assert set(overtime.small_groups) == {"Sales Representative", "Human Resources", "Manager", "Research Director"}


def test_every_insight_has_required_parts(analysis_df):
    built = [
        hr_insights.tenure_insight(analysis_df)[0],
        hr_insights.age_role_insight(analysis_df)[0],
        hr_insights.income_insight(analysis_df)[0],
        hr_insights.overtime_insight(analysis_df)[0],
    ]
    for insight in built:
        assert insight.finding and insight.interpretation and insight.actions and insight.limits
        body = cards.insight_body(insight)
        for heading in ("해석", "실무 개선 제안", "분석의 한계"):
            assert f"<h4>{heading}</h4>" in body
        assert "분석 결과" in cards.insight_header(insight)


def test_small_group_flag_is_escaped():
    insight = cards.Insight("x", "<b>", "<i>t</i>", "f", ["a"], ["b"], ["c"], small_groups=("<s>",))
    html = cards.insight_header(insight) + cards.insight_body(insight)
    assert "<i>" not in html and "<s>" not in html and "&lt;s&gt;" in html


def test_no_causal_wording(analysis_df):
    """해석 문장에 인과를 단정하는 표현을 쓰지 않는다."""
    built = [
        hr_insights.tenure_insight(analysis_df)[0],
        hr_insights.age_role_insight(analysis_df)[0],
        hr_insights.income_insight(analysis_df)[0],
        hr_insights.overtime_insight(analysis_df)[0],
    ]
    for insight in built:
        text = " ".join([insight.finding, *insight.interpretation, *insight.actions])
        for phrase in ("때문에 이직", "원인이다", "원인입니다", "이직을 줄일 수 있습니다", "이직이 줄어듭니다"):
            assert phrase not in text, phrase


@pytest.mark.requires_data
def test_insights_page_renders():
    app = AppTest.from_function(_insights_page, default_timeout=60).run()
    html = _html(app)
    assert not app.exception and not app.error
    assert "<h1>HR Insights</h1>" in html
    assert len(app.get("plotly_chart")) == 5
    assert html.count('<span class="hr-tag">') == 4
    assert html.count("<h4>실무 개선 제안</h4>") == 4 and html.count("<h4>분석의 한계</h4>") == 4
    for text in ("전체 이직 현황 요약", "주요 이직 관련 지표", "부서별 인력관리 시사점", "데이터에 근거한 개선 제안"):
        assert text in html
    share = 75 / 237 * 100
    assert f"{share:.2f}%" in html  # 이직자 중 근속 0~1년 비중
    assert "※ 30명 미만 소집단 포함" in html
    assert "80.00%(5명) ※" in html  # HR 부서 근속 0~1년 소집단 표시


def test_insights_data_error(monkeypatch):
    def fail():
        raise DataLoadError("데이터 파일을 찾을 수 없습니다: C:\\외부\\hr.csv")

    monkeypatch.setattr(data, "load_analysis_data", fail)
    app = AppTest.from_function(_insights_page, default_timeout=30).run()
    shown = "\n".join([c.value for c in app.code] + [_html(app)])
    assert not app.exception and len(app.error) == 1
    assert "외부" not in shown and layout.DATA_HINT in shown
    assert "1,470" not in shown and not app.get("plotly_chart")
