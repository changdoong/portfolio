"""상단 KPI 카드."""

from dataclasses import dataclass
from html import escape
from typing import Literal

import streamlit as st

from components import formatting
from core.analytics import AttritionSummary


@dataclass(frozen=True)
class Kpi:
    label: str
    value: str
    unit: str
    note: str
    tone: Literal["neutral", "retained", "attrition"] = "neutral"


def build_kpis(summary: AttritionSummary) -> tuple[Kpi, ...]:
    total = summary.employee_count
    retained_rate = summary.retained_count / total * 100 if total else None
    # 데이터에 기간 정보가 없으므로 증감률과 추세선은 넣지 않는다.
    return (
        Kpi("전체 직원 수", formatting.count(total), "명", "재직자와 이직자 합계"),
        Kpi(
            "이직자 수",
            formatting.count(summary.attrition_count),
            "명",
            "Attrition = Yes",
            "attrition",
        ),
        Kpi(
            "재직자 수",
            formatting.count(summary.retained_count),
            "명",
            f"전체의 {formatting.percent(retained_rate)}",
            "retained",
        ),
        Kpi(
            "이직률",
            formatting.percent(summary.attrition_rate),
            "",
            "이직자 수 ÷ 전체 직원 수",
            "attrition",
        ),
    )


def kpi_html(items: tuple[Kpi, ...]) -> str:
    cards = []
    for item in items:
        unit = f'<span class="hr-kpi-unit">{escape(item.unit)}</span>' if item.unit else ""
        cards.append(
            '<div class="hr-kpi">'
            f'<div class="hr-kpi-label"><span class="hr-dot hr-dot--{escape(item.tone)}"></span>'
            f"{escape(item.label)}</div>"
            f'<div class="hr-kpi-value">{escape(item.value)}{unit}</div>'
            f'<div class="hr-kpi-note">{escape(item.note)}</div>'
            "</div>"
        )
    return f'<div class="hr-kpi-wrap"><div class="hr-kpi-grid">{"".join(cards)}</div></div>'


def render(summary: AttritionSummary) -> None:
    st.html(kpi_html(build_kpis(summary)))
