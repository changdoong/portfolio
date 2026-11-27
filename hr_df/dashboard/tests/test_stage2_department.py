"""작업 4: 부서별 이직 현황."""

import pytest
from baselines import assert_displayed, report_table
from streamlit.testing.v1 import AppTest

from components import department, theme
from core import analytics, config

REPORTED = report_table("부서", "직원 수", "이직자 수", "이직률").rows


def _render_edge_cases():
    from components import department
    from core import analytics, data

    df = data.load_analysis_data()
    for subset in (df.iloc[:0], df.head(5)):  # 분모 0, 30명 미만
        department.render(subset, analytics.summarize_attrition(subset))


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
    assert figure.layout.xaxis.range[1] >= max(bar.x) * 1.6, "320px에서 숫자와 막대가 겹치지 않을 여백"
    assert figure.layout.shapes[0].x0 == pytest.approx(summary.attrition_rate)
    assert f"전체 {summary.attrition_rate:.2f}%" in [note.text for note in figure.layout.annotations]
    assert [list(row) for row in bar.customdata] == [
        [name, int(total), int(leaver)] for name, total, leaver, _ in REPORTED
    ]
    assert "이직 %{customdata[2]:,}명 / 전체 %{customdata[1]:,}명" in bar.hovertemplate
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
    assert [note.text for note in figure.layout.annotations] == [f"{row[1]}명" for row in REPORTED]
    for bar in figure.data:
        assert [list(row) for row in bar.customdata] == [[row[0], int(row[1])] for row in REPORTED]
        assert f"{bar.name} %{{x:,}}명 / 전체 %{{customdata[1]:,}}명" in bar.hovertemplate
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
    # 값의 존재만으로는 열이 뒤바뀐 것을 잡지 못하므로 행 단위로 비교한다.
    headers = "".join(f'<th scope="col">{title}</th>' for title in ("부서", "직원", "이직", "재직", "이직률"))
    assert headers in html
    for name, total, leaver, rate in REPORTED:
        cells = (total, leaver, str(int(total) - int(leaver)), rate)
        row = "".join(f"<td>{value}</td>" for value in cells)
        assert f'<tr><th scope="row">{name.replace("&", "&amp;")}</th>{row}</tr>' in html, name


def test_html_table_is_escaped(table, summary):
    changed = table.assign(Department="<script>")
    assert "<script>" not in department.table_html(changed, summary)


@pytest.mark.requires_data
def test_overview_renders_everything():
    app = AppTest.from_file(config.PROJECT_ROOT / "dashboard" / "app.py", default_timeout=30).run()
    html = "".join(item.proto.body for item in app.main.get("html"))
    assert not app.exception
    assert not app.warning
    assert len(app.get("plotly_chart")) == 2
    assert html.count('class="hr-kpi"') == 4
    assert html.count('class="hr-table"') == 1
    assert "연간 이직률로 해석할 수 없습니다" in html

    edge = AppTest.from_function(_render_edge_cases, default_timeout=30).run()
    assert not edge.exception
    assert len(edge.info) == 1, "0명이면 안내만 표시한다."
    assert len(edge.warning) == 1, "30명 미만이면 주의를 표시한다."
    assert len(edge.get("plotly_chart")) == 2
