"""작업 3: KPI 4개."""

import pytest
from baselines import report_table
from streamlit.testing.v1 import AppTest

from components import kpi
from core import analytics, config


def test_kpis_match_report(analysis_df):
    rows = report_table("구분", "직원 수", "비율").rows
    reported = {label: (count.rstrip("명"), rate) for label, count, rate in rows}
    total, leaver, retained, rate = kpi.build_kpis(analytics.summarize_attrition(analysis_df))

    assert total.value == reported["합계"][0]
    assert leaver.value == reported["이직"][0]
    assert retained.value == reported["재직"][0]
    assert retained.note == f"전체의 {reported['재직'][1]}"
    assert rate.value == reported["이직"][1]


def test_labels_and_order(analysis_df):
    items = kpi.build_kpis(analytics.summarize_attrition(analysis_df))
    assert [item.label for item in items] == ["전체 직원 수", "이직자 수", "재직자 수", "이직률"]
    assert [item.tone for item in items] == ["neutral", "attrition", "retained", "attrition"]


def test_empty_is_not_zero_percent():
    total, _, retained, rate = kpi.build_kpis(analytics.AttritionSummary(0, 0, 0, None))
    assert total.value == "0"
    assert rate.value == "—"
    assert retained.note == "전체의 —"


def test_html_is_escaped():
    tone = 'neutral" onmouseover="alert(1)'
    html = kpi.kpi_html((kpi.Kpi("<script>", "<b>", "&", "<i>", tone),))
    for unsafe in ("<script>", "<b>", "<i>", tone):
        assert unsafe not in html
    assert '<span class="hr-kpi-unit">&amp;</span>' in html
    # 따옴표가 변환되어 class 속성 안에 남아야 새 속성이 만들어지지 않는다.
    assert 'class="hr-dot hr-dot--neutral&quot; onmouseover=&quot;alert(1)"></span>' in html


@pytest.mark.requires_data
def test_four_cards_on_screen():
    app = AppTest.from_file(config.PROJECT_ROOT / "dashboard" / "app.py", default_timeout=30).run()
    html = "".join(item.proto.body for item in app.main.get("html"))
    assert not app.exception
    assert html.count('class="hr-kpi"') == 4
    for value in ("1,470", "237", "1,233", "16.12%"):
        assert value in html
