"""Stage 3 작업 5: Workforce 필터."""

import csv
import json
from collections import Counter

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from components import filters, group_chart
from core import config

COMPANY_RATE = 237 / 1470 * 100

@pytest.fixture(scope="module")
def raw_rows():
    """원본 CSV 행. 모듈을 불러올 때가 아니라 테스트가 요청할 때 읽는다(데이터 없는 환경의 수집 오류 방지)."""
    with open(config.RAW_DATA_PATH, encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


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


@pytest.mark.requires_data
def test_default_selects_everything():
    app = _app_with()
    assert not app.exception
    assert [m.label for m in app.multiselect] == ["부서", "성별"]
    assert app.multiselect(key="filter_Department").value == [
        "Human Resources", "Research & Development", "Sales"
    ]
    assert app.multiselect(key="filter_Gender").value == ["Female", "Male"]
    assert "분석 대상 1,470명(전체 1,470명 중)" in _html(app)


@pytest.mark.requires_data
def test_apply_filters_matches_raw_csv(analysis_df, raw_rows):
    view = filters.apply_filters(analysis_df, {"Department": ["Sales"], "Gender": ["Female"]})
    rows = [r for r in raw_rows if r["Department"] == "Sales" and r["Gender"] == "Female"]
    assert len(view) == len(rows)
    assert int(view["AttritionBinary"].sum()) == sum(r["Attrition"] == "Yes" for r in rows)
    # 급여 사분위는 전사 기준 그대로다. 필터 안에서 다시 4등분하지 않는다.
    assert view["IncomeGroup"].equals(analysis_df.loc[view.index, "IncomeGroup"])
    assert view["IncomeGroup"].value_counts().nunique() > 1


@pytest.mark.requires_data
def test_department_filter_updates_charts(raw_rows):
    app = _app_with(department=["Human Resources"])
    rows = [r for r in raw_rows if r["Department"] == "Human Resources"]
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
    # 점선은 필터와 무관하게 전사 평균이고, 표의 합계 행은 선택 집단이다.
    for key in ("age", "jobrole", "cross"):
        assert _spec(app, key)["layout"]["shapes"][0]["x0"] == pytest.approx(COMPANY_RATE), key
    assert "점선은 전사 평균 이직률(16.12%)" in html and "점선: 전체 16.12%" in html
    assert f"<td>{total}</td><td>{left}</td><td>{total - left}</td><td>{left / total * 100:.2f}%</td>" in html
    # HR Manager는 이직자 0명이다. 막대가 0이어도 축이 정상이어야 한다.
    assert expected_left["Manager"] == 0
    assert _spec(app, "jobrole")["layout"]["xaxis"]["range"][1] > 0
    assert group_chart.SMALL_NOTE.replace("※ ", "") in html


@pytest.mark.requires_data
def test_income_ranges_stay_company_wide():
    full = _html(_app_with())
    sales = _html(_app_with(department=["Sales"]))
    note = lambda html: html.split("구간 범위", 1)[1].split("</p>", 1)[0]
    assert note(full) == note(sales)


@pytest.mark.requires_data
def test_empty_selection():
    app = _app_with(department=[])
    assert not app.exception
    assert len(app.info) == 1
    assert not app.get("plotly_chart")
    assert "분석 대상 0명" in _html(app)
    assert "이직률 —" in _html(app)


@pytest.mark.requires_data
def test_gender_filter(raw_rows):
    app = _app_with(gender=["Female"])
    rows = [r for r in raw_rows if r["Gender"] == "Female"]
    assert f"분석 대상 {len(rows)}명" in _html(app)
    bar = _spec(app, "overtime")["data"][0]
    assert sum(row[1] for row in bar["customdata"]) == len(rows)


@pytest.mark.requires_data
def test_reset_restores_all():
    app = _app_with(department=["Sales"], gender=["Female"])
    assert "분석 대상 1,470명" not in _html(app)
    app.button(key="filter_reset").click().run()
    assert not app.exception and not app.warning
    assert app.multiselect(key="filter_Department").value == ["Human Resources", "Research & Development", "Sales"]
    assert app.multiselect(key="filter_Gender").value == ["Female", "Male"]
    assert "분석 대상 1,470명(전체 1,470명 중)" in _html(app)


@pytest.mark.requires_data
def test_job_role_description_matches_filtered_roles(raw_rows):
    # 설명 문구의 직무 수는 필터 후 실제로 남은 직무 수와 같아야 한다(21개 조합 전수).
    departments = ["Human Resources", "Research & Development", "Sales"]
    genders = ["Female", "Male"]
    named = {(("Human Resources",), ("Female",)): 2, (("Sales",), ("Female", "Male")): 3,
             (("Research & Development",), ("Female", "Male")): 6, (tuple(departments), tuple(genders)): 9}
    checked = 0
    for d_mask in range(1, 8):
        for g_mask in range(1, 4):
            dept = [d for i, d in enumerate(departments) if d_mask >> i & 1]
            gender = [g for i, g in enumerate(genders) if g_mask >> i & 1]
            roles = {r["JobRole"] for r in raw_rows if r["Department"] in dept and r["Gender"] in gender}
            app = _app_with(department=dept, gender=gender)
            assert f"{len(roles)}개 직무를 이직률 순으로 정렬했습니다." in _html(app), (dept, gender)
            assert len(_spec(app, "jobrole")["data"][0]["customdata"]) == len(roles)
            if (tuple(dept), tuple(gender)) in named:
                assert len(roles) == named[(tuple(dept), tuple(gender))]
            checked += 1
    assert checked == 21


def test_describe():
    assert filters.describe({"Department": ["Sales"], "Gender": ["Female", "Male"]}) == "부서 1/3 · 성별 2/2"
