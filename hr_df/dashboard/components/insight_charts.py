"""HR Insights 화면의 차트. Workforce 화면의 막대 차트를 반복하지 않고, 비교·우선순위를 보여 주는 형태를 쓴다."""

from html import escape

import pandas as pd
import plotly.graph_objects as go

from components import formatting, theme
from components.group_chart import SMALL_MARK, SMALL_OPACITY, wrap_label


def signed_pp(value: float) -> str:
    return f"{value:+.2f}%p"


def diverging_figure(table: pd.DataFrame, *, label_column: str, value_column: str, height_per_row: int = 38,
                     hover_extra: str = "") -> go.Figure:
    """전사 평균 대비 차이(%p). 평균보다 높으면 이직색, 낮으면 재직색. 0에 기준선."""
    labels = [
        wrap_label(f"{name} {SMALL_MARK}" if small else name, 22)
        for name, small in zip(table[label_column], table["is_small_sample"], strict=True)
    ]
    values = table[value_column].tolist()
    colors = [theme.COLORS["attrition"] if v > 0 else theme.COLORS["retained"] for v in values]
    figure = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            width=0.56,
            marker={
                "color": colors,
                "opacity": [SMALL_OPACITY if s else 1.0 for s in table["is_small_sample"]],
            },
            text=[signed_pp(v) for v in values],
            textposition="outside",
            textfont={"color": theme.COLORS["ink"]},
            cliponaxis=False,
            customdata=table[["employee_count", "attrition_count", "attrition_rate"]].values.tolist()
            if "employee_count" in table else None,
            hovertemplate=(
                "<b>%{y}</b><br>전사 평균 대비 %{x:+.2f}%p"
                + ("<br>이직 %{customdata[1]:,}명 / 전체 %{customdata[0]:,}명 · 이직률 %{customdata[2]:.2f}%"
                   if "employee_count" in table else "")
                + hover_extra
                + "<extra></extra>"
            ),
        )
    )
    span = max(abs(v) for v in values) * 1.35
    theme.style_figure(figure, height=60 + height_per_row * len(table))
    figure.update_layout(barcornerradius=4, showlegend=False, margin={"l": 190, "r": 32, "t": 16, "b": 36})
    figure.update_xaxes(range=[-span, span], ticksuffix="%p", zeroline=True,
                        zerolinecolor=theme.COLORS["ink-muted"], zerolinewidth=1)
    figure.update_yaxes(autorange="reversed")
    return figure


# 축 이름은 보고서 표기(0~1년 등)를 쓴다. 좁은 화면에서도 기울이지 않고 읽히도록 짧게 쓴다.
TENURE_SHORT = {
    "0-1 Years": "0~1년",
    "2-3 Years": "2~3년",
    "4-5 Years": "4~5년",
    "6-10 Years": "6~10년",
    "Over 10 Years": "10년 초과",
}


def tenure_figure(table: pd.DataFrame, overall_rate: float) -> go.Figure:
    """같은 구간 경계로 본 회사 근속과 현 직무 근속별 이직률(묶음 막대). 수치는 표로 함께 제공한다."""
    figure = go.Figure()
    for basis, color in zip(table["basis"].unique(), (theme.COLORS["series-1"], theme.COLORS["series-2"]),
                            strict=True):
        part = table[table["basis"] == basis]
        figure.add_trace(
            go.Bar(
                name=basis,
                x=[TENURE_SHORT.get(group, group) for group in part["group"]],
                y=part["attrition_rate"],
                marker={"color": color},
                customdata=part[["employee_count", "attrition_count"]].values.tolist(),
                hovertemplate=(
                    f"<b>{escape(basis)}</b><br>%{{x}} · 이직률 %{{y:.2f}}%"
                    "<br>이직 %{customdata[1]:,}명 / 전체 %{customdata[0]:,}명<extra></extra>"
                ),
            )
        )
    theme.style_figure(figure, height=340)
    figure.update_layout(
        barmode="group", bargap=0.28, bargroupgap=0.1, barcornerradius=4,
        legend={"orientation": "h", "y": 1.12, "x": 0, "xanchor": "left"},
        margin={"l": 56, "r": 16, "t": 48, "b": 40},
    )
    figure.update_yaxes(range=[0, max(table["attrition_rate"]) * 1.25], ticksuffix="%", showgrid=True,
                        gridcolor=theme.COLORS["grid"], tickfont={"color": theme.COLORS["ink-muted"]})
    figure.update_xaxes(showgrid=False, tickangle=0)
    figure.add_hline(
        y=overall_rate, line={"color": theme.COLORS["ink-muted"], "width": 1, "dash": "dash"},
        annotation={"text": f"전사 {formatting.percent(overall_rate)}", "xanchor": "right", "x": 1,
                    "font": {"color": theme.COLORS["ink-muted"]}},
    )
    return figure


def labeled_roles(table: pd.DataFrame) -> set[str]:
    """이름을 직접 적을 직무: 30명 이상 중 이직률 상위 3개와 인원이 가장 많은 직무. 나머지는 툴팁과 표로 본다."""
    solid = table[~table["is_small_sample"]]
    top = solid.nlargest(3, "attrition_rate")["JobRole"]
    return {*top, str(table.loc[table["employee_count"].idxmax(), "JobRole"])}


def role_bubble_figure(table: pd.DataFrame, overall_rate: float) -> go.Figure:
    """직무별 인원(가로)과 이직률(세로). 규모와 비율을 함께 본다. 30명 미만은 속이 빈 점."""
    small = table["is_small_sample"]
    shown = labeled_roles(table)
    labels = [
        (f"{name} {SMALL_MARK}" if s else name) if name in shown else ""
        for name, s in zip(table["JobRole"], small, strict=True)
    ]
    figure = go.Figure(
        go.Scatter(
            x=table["employee_count"],
            y=table["attrition_rate"],
            mode="markers+text",
            text=labels,
            textposition="top center",
            textfont={"color": theme.COLORS["ink"], "size": 11},
            marker={
                "size": 12,
                "color": [theme.COLORS["surface"] if s else theme.COLORS["attrition"] for s in small],
                "line": {"width": 2, "color": theme.COLORS["attrition"]},
            },
            customdata=table[["JobRole", "attrition_count"]].values.tolist(),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>이직률 %{y:.2f}%<br>이직 %{customdata[1]:,}명 / 전체 %{x:,}명"
                "<extra></extra>"
            ),
        )
    )
    theme.style_figure(figure, height=380)
    figure.update_layout(showlegend=False, margin={"l": 56, "r": 24, "t": 16, "b": 52}, hovermode="closest")
    # 왼쪽에 놓인 직무 이름이 좁은 화면에서 잘리지 않도록 0 왼쪽에 여백을 두고, 눈금은 0 이상만 표시한다.
    upper = max(table["employee_count"]) * 1.3  # 오른쪽 끝 점의 이름이 잘리지 않을 여백
    figure.update_xaxes(title={"text": "직원 수(명)"}, range=[-30, upper],
                        tickvals=list(range(0, int(upper) + 1, 100)))
    figure.update_yaxes(title={"text": "이직률"}, ticksuffix="%", showgrid=True, gridcolor=theme.COLORS["grid"],
                        range=[0, max(table["attrition_rate"]) * 1.2],
                        tickfont={"color": theme.COLORS["ink-muted"]})
    figure.add_hline(
        y=overall_rate, line={"color": theme.COLORS["ink-muted"], "width": 1, "dash": "dash"},
        annotation={"text": f"전사 {formatting.percent(overall_rate)}", "xanchor": "left", "x": 0,
                    "font": {"color": theme.COLORS["ink-muted"]}},
    )
    return figure
