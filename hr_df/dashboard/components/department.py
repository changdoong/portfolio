"""부서별 이직 현황: 이직률, 인원 구성, 수치 표."""

from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components import formatting, layout, theme
from core import analytics
from core.analytics import AttritionSummary

BAR_WIDTH = 0.36  # 막대 두께 24px 이하
AXIS_LABELS = {"Research & Development": "Research &<br>Development"}


def department_summary(df: pd.DataFrame) -> pd.DataFrame:
    result = analytics.attrition_by(df, "Department")
    result["retained_count"] = result["employee_count"] - result["attrition_count"]
    return result.sort_values("attrition_rate", ascending=False, ignore_index=True)


def _axis_labels(table: pd.DataFrame) -> list[str]:
    return [AXIS_LABELS.get(name, name) for name in table["Department"]]


def rate_figure(table: pd.DataFrame, overall_rate: float) -> go.Figure:
    rates = table["attrition_rate"].tolist()
    figure = go.Figure(
        go.Bar(
            x=rates,
            y=_axis_labels(table),
            orientation="h",
            width=BAR_WIDTH,
            marker={"color": theme.COLORS["attrition"]},
            customdata=table[["Department", "employee_count", "attrition_count"]].values.tolist(),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>이직률 %{x:.2f}%<br>"
                "이직 %{customdata[2]:,}명 / 전체 %{customdata[1]:,}명<extra></extra>"
            ),
        )
    )
    theme.style_figure(figure)
    figure.update_layout(barcornerradius=4, showlegend=False)
    figure.update_xaxes(range=[0, max(max(rates), overall_rate) * 1.65], visible=False)
    figure.update_yaxes(autorange="reversed")
    # 막대 끝에 숫자를 두면 전체 평균선과 겹치므로 오른쪽에 정렬한다.
    for label, rate in zip(_axis_labels(table), rates, strict=True):
        figure.add_annotation(
            xref="paper",
            x=1,
            y=label,
            text=formatting.percent(rate),
            xanchor="right",
            showarrow=False,
        )
    figure.add_vline(
        x=overall_rate,
        line={"color": theme.COLORS["ink-muted"], "width": 1, "dash": "dash"},
        annotation={
            "text": f"전체 {formatting.percent(overall_rate)}",
            "font": {"color": theme.COLORS["ink-muted"]},
            "yanchor": "bottom",
            "xanchor": "center",
            "y": 1.02,
        },
    )
    return figure


def composition_figure(table: pd.DataFrame) -> go.Figure:
    labels = _axis_labels(table)
    figure = go.Figure()
    for name, column, color in (
        ("재직", "retained_count", theme.COLORS["retained"]),
        ("이직", "attrition_count", theme.COLORS["attrition"]),
    ):
        figure.add_bar(
            name=name,
            x=table[column].tolist(),
            y=labels,
            orientation="h",
            width=BAR_WIDTH,
            marker={"color": color, "line": {"width": 0}},
            customdata=table[["Department", "employee_count"]].values.tolist(),
            hovertemplate=(
                f"<b>%{{customdata[0]}}</b><br>{name} %{{x:,}}명 / "
                "전체 %{customdata[1]:,}명<extra></extra>"
            ),
        )
    theme.style_figure(figure)
    # 막대 테두리로 간격을 만들면 12명 같은 얇은 구간이 가려지므로 재직 쪽에서만 2px을 비운다.
    for label, retained in zip(labels, table["retained_count"], strict=True):
        figure.add_shape(
            type="rect",
            xsizemode="pixel",
            xanchor=int(retained),
            x0=-2,
            x1=0,
            ysizemode="pixel",
            yanchor=label,
            y0=-14,
            y1=14,
            fillcolor=theme.COLORS["surface"],
            line={"width": 0},
        )
    # 좁은 이직 구간 안에 숫자를 넣으면 잘리므로 막대 끝에 총원을 표시한다.
    for label, total in zip(labels, table["employee_count"], strict=True):
        figure.add_annotation(
            x=int(total),
            y=label,
            text=f"{formatting.count(total)}명",
            xanchor="left",
            xshift=6,
            showarrow=False,
        )
    figure.update_layout(
        barmode="stack",
        legend={
            "orientation": "h",
            "traceorder": "normal",
            "x": 0,
            "y": 1.02,
            "yanchor": "bottom",
            "itemclick": False,
            "itemdoubleclick": False,
        },
    )
    figure.update_xaxes(range=[0, int(table["employee_count"].max()) * 1.32], visible=False)
    figure.update_yaxes(autorange="reversed")
    return figure


def table_html(table: pd.DataFrame, summary: AttritionSummary) -> str:
    def cells(total: int, left: int, retained: int, rate: float | None) -> str:
        values = [*map(formatting.count, (total, left, retained)), formatting.percent(rate)]
        return "".join(f"<td>{value}</td>" for value in values)

    body = "".join(
        f'<tr><th scope="row">{escape(row.Department)}</th>'
        f"{cells(row.employee_count, row.attrition_count, row.retained_count, row.attrition_rate)}"
        "</tr>"
        for row in table.itertuples()
    )
    total_cells = cells(
        summary.employee_count,
        summary.attrition_count,
        summary.retained_count,
        summary.attrition_rate,
    )
    headers = "".join(
        f'<th scope="col">{name}</th>' for name in ("부서", "직원", "이직", "재직", "이직률")
    )
    return (
        '<div class="hr-table-scroll"><table class="hr-table">'
        f"<thead><tr>{headers}</tr></thead><tbody>{body}</tbody>"
        f'<tfoot><tr><th scope="row">전체</th>{total_cells}</tr></tfoot>'
        "</table></div>"
    )


def render(df: pd.DataFrame, summary: AttritionSummary) -> None:
    layout.section_header("부서별 이직 현황", "이직률이 높은 순으로 표시합니다.")
    if df.empty or summary.attrition_rate is None:
        st.info("표시할 직원 데이터가 없습니다.")
        return

    table = department_summary(df)
    with st.container(key="department_charts"):
        left, right = st.columns(2)
        with left, st.container(key="card_department_rate"):
            layout.section_header("부서별 이직률", "점선은 전체 이직률", level=3)
            st.plotly_chart(
                rate_figure(table, summary.attrition_rate),
                theme=None,
                config=theme.PLOTLY_CONFIG,
                key="department_rate",
                alt="부서별 이직률 막대 차트. 수치는 아래 표에도 있습니다.",
            )
        with right, st.container(key="card_department_composition"):
            layout.section_header("부서별 인원 구성", "막대 끝 숫자는 부서 전체 인원", level=3)
            st.plotly_chart(
                composition_figure(table),
                theme=None,
                config=theme.PLOTLY_CONFIG,
                key="department_composition",
                alt="부서별 재직자와 이직자 누적 막대 차트. 수치는 아래 표에도 있습니다.",
            )

    with st.container(key="card_department_table"):
        layout.section_header("부서별 상세", "단위: 명, 이직률은 부서 인원 대비", level=3)
        st.html(table_html(table, summary))

    if table["is_small_sample"].any():
        st.warning("30명 미만인 부서가 있어 이직률 해석에 주의가 필요합니다.")
