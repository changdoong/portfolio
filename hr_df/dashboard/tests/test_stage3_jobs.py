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


# 이 파일의 모든 테스트는 실제 데이터로 화면을 그리거나 보고서·원본과 대조한다.
pytestmark = pytest.mark.requires_data


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
