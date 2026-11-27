"""Stage 3 작업 3: 연령·근속·소득 화면."""

import csv
import json

import pytest
import streamlit as st
from baselines import report_table
from streamlit.testing.v1 import AppTest

from core import config

REPORTED = {
    "age": report_table("연령대", "직원 수", "이직자 수", "이직률").rows,
    "tenure": report_table("근속 구간", "직원 수", "이직자 수", "이직률").rows,
    "income": report_table("소득 구간", "직원 수", "이직자 수", "이직률").rows,
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


def _run() -> AppTest:
    return AppTest.from_function(_workforce, default_timeout=30).run()


def _spec(app: AppTest, key: str) -> dict:
    # 이후 작업에서 차트가 늘어나도 유지되도록 순서가 아닌 키로 찾는다.
    chart = next(c for c in app.get("plotly_chart") if c.proto.id.endswith(f"chart_{key}"))
    return json.loads(chart.proto.spec)


def test_sections_render():
    app = _run()
    html = "".join(item.proto.body for item in app.main.get("html"))
    assert not app.exception
    assert not app.error and not app.warning
    for key in ("age", "tenure", "income"):
        assert _spec(app, key)["data"], key
    for title in ("연령대별 이직률", "근속연수별 이직률", "월 소득 구간별 이직률"):
        assert title in html
    for text in ("분석 대상 1,470명", "이직 237명", "이직률 16.12%"):
        assert text in html  # 작업 5에서 필터 문구가 앞에 붙어도 유지된다.


@pytest.mark.parametrize("key", ["age", "tenure", "income"])
def test_charts_match_report(key):
    spec = _spec(_run(), key)
    bar = spec["data"][0]
    reported = REPORTED[key]
    assert [row[1] for row in bar["customdata"]] == [int(r[1].replace(",", "")) for r in reported]
    assert [row[2] for row in bar["customdata"]] == [int(r[2]) for r in reported]
    labels = [a["text"] for a in spec["layout"]["annotations"] if a.get("xref") == "paper"]
    assert labels == [r[3] for r in reported]


def test_income_ranges_are_company_wide():
    rows = list(csv.DictReader(open(config.RAW_DATA_PATH, encoding="utf-8-sig")))
    incomes = sorted(int(r["MonthlyIncome"]) for r in rows)
    html = "".join(item.proto.body for item in _run().main.get("html"))
    note = html.split("구간 범위", 1)[1].split(": ", 1)[1].split("</p>", 1)[0]
    parts = note.split(" · ")
    assert len(parts) == 4
    assert parts[0].startswith(f"Q1 - Low {incomes[0]:,}~")
    assert parts[-1].endswith(f"~{incomes[-1]:,}")
    counts = [int(r[1].replace(",", "")) for r in REPORTED["income"]]
    # 각 구간의 최댓값이 정렬된 전체 소득에서 누적 인원 위치와 일치한다.
    position = 0
    for part, count in zip(parts, counts, strict=True):
        position += count
        assert part.endswith(f"~{incomes[position - 1]:,}")
