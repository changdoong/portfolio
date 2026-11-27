"""직무 × 초과근무 교차 분석: 덤벨 차트와 수치 표."""

from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components import formatting, group_chart, layout, theme
from core import analytics
from core.analytics import AttritionSummary

# (값, 표시 이름, 속이 빈 점 여부). 색은 이직률이므로 모두 이직 색을 쓰고 모양으로 구분한다.
SERIES = (("No", "초과근무 없음", True), ("Yes", "초과근무 있음", False))


def cross_table(df: pd.DataFrame) -> pd.DataFrame:
    table = analytics.attrition_by(df, ["JobRole", "OverTime"])
    table["JobRole"] = table["JobRole"].astype(str)
    table["OverTime"] = table["OverTime"].astype(str)
    return table


def role_order(df: pd.DataFrame) -> list[str]:
    """직무별 이직률 차트와 같은 순서."""
    return group_chart.group_table(df, "JobRole", sort_by_rate=True)["JobRole"].tolist()


def axis_upper(rates: list[float], overall_rate: float) -> float:
    """점 차트는 오른쪽 숫자 칸이 없으므로 막대 차트보다 여백을 적게 둔다. 0%만 있어도 0보다 크다."""
    return max([*rates, overall_rate, 1.0]) * 1.15


def _marker(hollow: bool) -> dict:
    return {
        "size": 12,
        "color": theme.COLORS["surface"] if hollow else theme.COLORS["attrition"],
        "line": {"color": theme.COLORS["attrition"], "width": 2},
    }


def cross_figure(table: pd.DataFrame, order: list[str], overall_rate: float) -> go.Figure:
    labels = {role: group_chart.wrap_label(role) for role in order}
    upper = axis_upper(table["attrition_rate"].tolist(), overall_rate)
    figure = go.Figure()

    xs, ys = [], []
    for role in order:
        rates = table.loc[table["JobRole"] == role, "attrition_rate"].tolist()
        if len(rates) == 2:  # 한쪽만 있는 직무는 선을 긋지 않는다.
            xs += [*rates, None]
            ys += [labels[role], labels[role], None]
    figure.add_scatter(
        x=xs, y=ys, mode="lines", hoverinfo="skip", showlegend=False,
        line={"color": theme.COLORS["ink-muted"], "width": 1.5},
    )

    for value, name, hollow in SERIES:
        rows = table[table["OverTime"] == value].set_index("JobRole")
        roles = [role for role in order if role in rows.index]
        rows = rows.loc[roles]
        figure.add_scatter(
            x=rows["attrition_rate"].tolist(),
            y=[labels[role] for role in roles],
            mode="markers",
            name=name,
            showlegend=False,
            cliponaxis=False,  # 0%인 점이 축에서 반쯤 잘리지 않게 한다.
            marker={
                **_marker(hollow),
                "opacity": [group_chart.SMALL_OPACITY if s else 1.0 for s in rows["is_small_sample"]],
            },
            customdata=[
                [role, int(r.employee_count), int(r.attrition_count), "※ 30명 미만" if r.is_small_sample else ""]
                for role, r in zip(roles, rows.itertuples(), strict=True)
            ],
            hovertemplate=(
                f"<b>%{{customdata[0]}}</b> · {name}<br>이직률 %{{x:.2f}}%<br>"
                "이직 %{customdata[2]:,}명 / 전체 %{customdata[1]:,}명<br>%{customdata[3]}<extra></extra>"
            ),
        )

    # 범례는 첫 점의 투명도를 따라가므로, 범례 전용 항목을 따로 둔다.
    for _, name, hollow in SERIES:
        figure.add_scatter(x=[None], y=[None], mode="markers", name=name, marker=_marker(hollow), hoverinfo="skip")

    theme.style_figure(figure, height=90 + group_chart.ROW_HEIGHT * len(order))
    figure.update_layout(
        legend={
            "orientation": "h", "x": 0, "y": 1.0, "yanchor": "bottom",
            "itemclick": False, "itemdoubleclick": False,
        },
        margin={"t": 56},
    )
    figure.update_xaxes(range=[0, upper], ticksuffix="%", nticks=5)
    figure.update_yaxes(
        categoryorder="array", categoryarray=[labels[role] for role in order], autorange="reversed"
    )
    figure.add_vline(
        x=overall_rate, line={"color": theme.COLORS["ink-muted"], "width": 1, "dash": "dash"}
    )
    return figure


def table_html(table: pd.DataFrame, order: list[str]) -> str:
    rank = {role: i for i, role in enumerate(order)}
    rows = table.sort_values(["JobRole", "OverTime"], key=lambda c: c.map(rank) if c.name == "JobRole" else c)
    body = "".join(
        f'<tr><th scope="row">{escape(r.JobRole)}</th>'
        f"<td>{group_chart.row_label(r.OverTime, r.is_small_sample)}</td>"
        + "".join(
            f"<td>{escape(v)}</td>"
            for v in (
                formatting.count(r.employee_count),
                formatting.count(r.attrition_count),
                formatting.percent(r.attrition_rate),
            )
        )
        + "</tr>"
        for r in rows.itertuples()
    )
    headers = "".join(
        f'<th scope="col">{name}</th>' for name in ("직무", "초과근무", "직원", "이직", "이직률")
    )
    return (
        '<div class="hr-table-scroll"><table class="hr-table">'
        f"<thead><tr>{headers}</tr></thead><tbody>{body}</tbody></table></div>"
    )


def render(df: pd.DataFrame, summary: AttritionSummary) -> None:
    with st.container(key="card_cross"):
        layout.section_header(
            "직무 × 초과근무",
            "같은 직무 안에서 초과근무 여부에 따른 이직률입니다. 빈 점: 없음, 채운 점: 있음. "
            f"점선: 전체 {formatting.percent(summary.attrition_rate)}",
            level=3,
        )
        table = cross_table(df)
        if table.empty or summary.attrition_rate is None:
            st.info("표시할 직원 데이터가 없습니다.")
            return
        order = role_order(df)
        st.plotly_chart(
            cross_figure(table, order, summary.attrition_rate),
            theme=None,
            config=theme.PLOTLY_CONFIG,
            key="chart_cross",
            alt="직무별 초과근무 여부에 따른 이직률 점 차트. 수치는 아래 표에 있습니다.",
        )
        if table["is_small_sample"].any():
            layout.footnote(group_chart.SMALL_NOTE)
        with st.expander("수치 표 보기"):
            st.html(table_html(table, order))
