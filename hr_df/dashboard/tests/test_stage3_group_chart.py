"""Stage 3 작업 2: 집단별 이직률 공통 컴포넌트."""

import pytest
from baselines import assert_displayed, report_table

from components import group_chart
from core import analytics

REPORT_TABLES = {
    "AgeGroup": (report_table("연령대", "직원 수", "이직자 수", "이직률"), False),
    "JobRole": (report_table("직무", "직원 수", "이직자 수", "이직률"), True),
    "IncomeGroup": (report_table("소득 구간", "직원 수", "이직자 수", "이직률"), False),
    "TenureGroup": (report_table("근속 구간", "직원 수", "이직자 수", "이직률"), False),
}


@pytest.mark.parametrize("column", REPORT_TABLES)
def test_group_table_matches_report(analysis_df, column):
    reported, sort_by_rate = REPORT_TABLES[column]
    table = group_chart.group_table(analysis_df, column, sort_by_rate=sort_by_rate)
    assert len(table) == len(reported.rows)
    for row, (_, total, leaver, rate) in zip(table.itertuples(), reported.rows, strict=True):
        assert_displayed(row.employee_count, total)
        assert_displayed(row.attrition_count, leaver)
        assert_displayed(row.attrition_rate, rate)
        assert row.retained_count == row.employee_count - row.attrition_count
    if column == "JobRole":
        assert list(table["JobRole"]) == [row[0] for row in reported.rows]


def test_rate_figure_values(analysis_df):
    table = group_chart.group_table(analysis_df, "JobRole", sort_by_rate=True)
    summary = analytics.summarize_attrition(analysis_df)
    figure = group_chart.rate_figure(table, "JobRole", summary.attrition_rate)
    bar = figure.data[0]
    assert list(bar.x) == pytest.approx(table["attrition_rate"].tolist())
    assert [row[0] for row in bar.customdata] == table["JobRole"].tolist()
    assert [int(row[1]) for row in bar.customdata] == table["employee_count"].tolist()
    assert [int(row[2]) for row in bar.customdata] == table["attrition_count"].tolist()
    assert "이직 %{customdata[2]:,}명 / 전체 %{customdata[1]:,}명" in bar.hovertemplate
    notes = [a.text for a in figure.layout.annotations if a.xref == "paper"]
    assert notes == [f"{rate:.2f}%" for rate in table["attrition_rate"]]
    assert figure.layout.shapes[0].x0 == pytest.approx(summary.attrition_rate)
    assert figure.layout.xaxis.range == (0, pytest.approx(table["attrition_rate"].max() * 1.65))
    assert figure.layout.height == 70 + 44 * len(table)


def test_zero_attrition_axis(analysis_df):
    subset = analysis_df.assign(AttritionBinary=0)
    table = group_chart.group_table(subset, "AgeGroup")
    figure = group_chart.rate_figure(table, "AgeGroup", 0.0)
    assert figure.layout.xaxis.range[1] > 0, "범위가 [0, 0]이면 0% 선이 가운데에 그려진다."
    assert figure.layout.shapes[0].x0 == 0
    line_label = next(a for a in figure.layout.annotations if a.text.startswith("전체"))
    assert line_label.xanchor == "left", "왼쪽 끝 기준선의 글자가 잘리지 않는다."


def test_small_samples_are_marked(analysis_df):
    subset = analysis_df.groupby("JobRole").head(40).iloc[:-15]
    table = group_chart.group_table(subset, "JobRole")
    assert table["is_small_sample"].any() and not table["is_small_sample"].all()
    figure = group_chart.rate_figure(table, "JobRole", 10.0)
    opacity = list(figure.data[0].marker.opacity)
    for label, small, alpha in zip(figure.data[0].y, table["is_small_sample"], opacity, strict=True):
        assert label.endswith(" ※") == small
        assert alpha == (group_chart.SMALL_OPACITY if small else 1.0)


def test_small_mark_counts_toward_wrap(analysis_df):
    # 여성만 선택하면 Human Resources 직무가 16명이라 ※가 붙는다. ※까지 포함한 길이로 줄바꿈해야 잘리지 않는다.
    female = analysis_df[analysis_df["Gender"] == "Female"]
    table = group_chart.group_table(female, "JobRole", sort_by_rate=True)
    labels = dict(zip(table["JobRole"], group_chart.axis_labels(table, "JobRole"), strict=True))
    assert labels["Human Resources"] == "Human<br>Resources ※"
    for label in labels.values():
        assert all(len(line) <= 16 for line in label.split("<br>")), label


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Sales", "Sales"),
        ("Research Scientist", "Research<br>Scientist"),
        ("Healthcare Representative", "Healthcare<br>Representative"),
        ("Q3 - Middle High", "Q3 - Middle High"),
        ("Research Director", "Research<br>Director"),
    ],
)
def test_wrap_label(text, expected):
    assert group_chart.wrap_label(text) == expected


def test_table_html(analysis_df):
    table = group_chart.group_table(analysis_df, "TenureGroup")
    summary = analytics.summarize_attrition(analysis_df)
    html = group_chart.table_html(table, "TenureGroup", "근속", summary)
    for row in report_table("근속 구간", "직원 수", "이직자 수", "이직률").rows[:1]:
        assert f"<td>{row[1]}</td><td>{row[2]}</td>" in html
    first = table.iloc[0]
    assert (
        f'<tr><th scope="row">0-1 Years</th><td>{first.employee_count}</td>'
        f"<td>{first.attrition_count}</td><td>{first.retained_count}</td>"
        f"<td>{first.attrition_rate:.2f}%</td></tr>"
    ) in html
    assert "<td>1,470</td><td>237</td><td>1,233</td><td>16.12%</td>" in html
    small = table.assign(is_small_sample=True)
    assert '<th scope="row">0-1 Years ※</th>' in group_chart.table_html(small, "TenureGroup", "근속", summary)
    changed = table.assign(TenureGroup="<script>")
    assert "<script>" not in group_chart.table_html(changed, "TenureGroup", "<b>", summary)
