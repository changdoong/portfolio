"""인력 특성별 이직률: 막대 차트, 수치 표, 화면 섹션."""

from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components import formatting, layout, theme
from core import analytics
from core.analytics import AttritionSummary

ROW_HEIGHT = 44
BAR_WIDTH = 0.5  # 행 높이 44px의 절반, 막대 두께 24px 이하
SMALL_OPACITY = 0.45
SMALL_MARK = "※"
SMALL_NOTE = "※ 30명 미만 집단은 흐리게 표시했습니다. 비율 차이를 해석할 때 주의하세요."


def wrap_label(text: str, width: int = 16) -> str:
    """긴 축 이름을 단어 경계에서 두 줄로 나눈다."""
    words = text.split(" ")
    if len(text) <= width or len(words) == 1:
        return text
    split = min(
        range(1, len(words)),
        key=lambda i: abs(len(" ".join(words[:i])) - len(" ".join(words[i:]))),
    )
    return " ".join(words[:split]) + "<br>" + " ".join(words[split:])


def group_table(df: pd.DataFrame, column: str, *, sort_by_rate: bool = False) -> pd.DataFrame:
    """집단별 직원·이직·재직 수와 이직률. 기본은 범주의 자연 순서다."""
    table = analytics.attrition_by(df, column)
    table["retained_count"] = table["employee_count"] - table["attrition_count"]
    table[column] = table[column].astype(str)
    if sort_by_rate:
        table = table.sort_values(
            ["attrition_rate", "employee_count"], ascending=False, kind="mergesort", ignore_index=True
        )
    return table


def axis_upper(rates: list[float], overall_rate: float) -> float:
    """이직률 축의 끝. 모든 값이 0%여도 범위가 [0, 0]이 되지 않는다."""
    return max([*rates, overall_rate, 1.0]) * 1.65


def axis_labels(table: pd.DataFrame, column: str) -> list[str]:
    # ※까지 포함한 길이로 줄바꿈을 정한다. 붙이기 전 길이로 정하면 긴 이름이 축 왼쪽에서 잘린다.
    return [
        wrap_label(f"{name} {SMALL_MARK}" if small else name)
        for name, small in zip(table[column], table["is_small_sample"], strict=True)
    ]


def rate_figure(table: pd.DataFrame, column: str, overall_rate: float) -> go.Figure:
    rates = table["attrition_rate"].tolist()
    labels = axis_labels(table, column)
    upper = axis_upper(rates, overall_rate)
    figure = go.Figure(
        go.Bar(
            x=rates,
            y=labels,
            orientation="h",
            width=BAR_WIDTH,
            marker={
                "color": theme.COLORS["attrition"],
                "opacity": [SMALL_OPACITY if s else 1.0 for s in table["is_small_sample"]],
            },
            customdata=table[[column, "employee_count", "attrition_count"]].values.tolist(),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>이직률 %{x:.2f}%<br>"
                "이직 %{customdata[2]:,}명 / 전체 %{customdata[1]:,}명<extra></extra>"
            ),
        )
    )
    theme.style_figure(figure, height=70 + ROW_HEIGHT * len(table))
    figure.update_layout(barcornerradius=4, showlegend=False)
    figure.update_xaxes(range=[0, upper], visible=False)
    figure.update_yaxes(autorange="reversed")
    # 막대 끝에 숫자를 두면 전체 평균선과 겹치므로 오른쪽에 정렬한다.
    for label, rate in zip(labels, rates, strict=True):
        figure.add_annotation(
            xref="paper", x=1, y=label, text=formatting.percent(rate), xanchor="right", showarrow=False
        )
    figure.add_vline(
        x=overall_rate,
        line={"color": theme.COLORS["ink-muted"], "width": 1, "dash": "dash"},
        annotation={
            "text": f"전체 {formatting.percent(overall_rate)}",
            "font": {"color": theme.COLORS["ink-muted"]},
            "yanchor": "bottom",
            # 기준선이 왼쪽 끝 근처면 글자가 잘리지 않도록 오른쪽으로 펼친다.
            "xanchor": "left" if overall_rate / upper < 0.2 else "center",
            "y": 1.0,
        },
    )
    return figure


def row_label(name: str, small: bool) -> str:
    """표의 행 이름. 모바일 폭에 맞추려고 비고 열 대신 차트와 같은 ※ 표시를 붙인다."""
    return f"{escape(name)} {SMALL_MARK}" if small else escape(name)


def table_html(table: pd.DataFrame, column: str, header: str, summary: AttritionSummary) -> str:
    def cells(total: int, left: int, retained: int, rate: float | None) -> str:
        values = [*map(formatting.count, (total, left, retained)), formatting.percent(rate)]
        return "".join(f"<td>{escape(value)}</td>" for value in values)

    body = "".join(
        f'<tr><th scope="row">{row_label(str(getattr(row, column)), row.is_small_sample)}</th>'
        + cells(row.employee_count, row.attrition_count, row.retained_count, row.attrition_rate)
        + "</tr>"
        for row in table.itertuples()
    )
    total = cells(
        summary.employee_count,
        summary.attrition_count,
        summary.retained_count,
        summary.attrition_rate,
    )
    headers = "".join(
        f'<th scope="col">{escape(name)}</th>' for name in (header, "직원", "이직", "재직", "이직률")
    )
    return (
        '<div class="hr-table-scroll"><table class="hr-table">'
        f"<thead><tr>{headers}</tr></thead><tbody>{body}</tbody>"
        f'<tfoot><tr><th scope="row">전체</th>{total}</tr></tfoot>'
        "</table></div>"
    )


def render_section(
    df: pd.DataFrame,
    summary: AttritionSummary,
    *,
    column: str,
    title: str,
    header: str,
    description: str,
    key: str,
    sort_by_rate: bool = False,
) -> None:
    table = group_table(df, column, sort_by_rate=sort_by_rate)
    with st.container(key=f"card_{key}"):
        layout.section_header(title, description, level=3)
        if table.empty or summary.attrition_rate is None:
            st.info("표시할 직원 데이터가 없습니다.")
            return
        st.plotly_chart(
            rate_figure(table, column, summary.attrition_rate),
            theme=None,
            config=theme.PLOTLY_CONFIG,
            key=f"chart_{key}",
            alt=f"{title} 막대 차트. 수치는 아래 표에 있습니다.",
        )
        if table["is_small_sample"].any():
            layout.footnote(SMALL_NOTE)
        with st.expander("수치 표 보기"):
            st.html(table_html(table, column, header, summary))
