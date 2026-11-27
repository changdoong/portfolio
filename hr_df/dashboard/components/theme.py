"""디자인 토큰, 전역 스타일, Plotly 공통 레이아웃."""

from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

COLORS = {
    "navy": "#0B1F3A",
    "navy-raised": "#17335A",
    "page": "#F4F7FB",
    "surface": "#FFFFFF",
    "border": "#DCE4EE",
    "grid": "#E9EEF5",
    "ink": "#142033",
    "ink-muted": "#56657A",
    "on-navy": "#FFFFFF",
    "on-navy-muted": "#AFC0D6",
    "retained": "#2F62A8",
    "attrition": "#D9652B",  # 이직을 나타낼 때만 사용
    # 두 계열 구분색(모델 비교 등). 명도·채도·색각이상 ΔE·대비 검사 통과(흰 배경 기준)
    "series-1": "#2F62A8",
    "series-2": "#199E70",
    "tint": "#EAF1FA",  # 순차 색상(혼동행렬)의 가장 옅은 단계, 강조 카드 배경
}
FONT_FAMILY = "'Noto Sans KR', 'Malgun Gothic', 'Segoe UI', sans-serif"
CSS_PATH = Path(__file__).with_name("styles.css")
PLOTLY_CONFIG = {"displayModeBar": False, "responsive": True, "scrollZoom": False}


def build_css() -> str:
    variables = "".join(f"--{name}: {value};" for name, value in COLORS.items())
    return f":root {{{variables}}}\n{CSS_PATH.read_text(encoding='utf-8')}"


def apply_styles() -> None:
    st.html(f"<style>{build_css()}</style>")


def style_figure(figure: go.Figure, *, height: int = 280) -> go.Figure:
    figure.update_layout(
        template="none",
        height=height,
        margin={"l": 116, "r": 24, "t": 40, "b": 36},
        paper_bgcolor=COLORS["surface"],
        plot_bgcolor=COLORS["surface"],
        font={"family": FONT_FAMILY, "size": 12, "color": COLORS["ink"]},
        hoverlabel={
            "bgcolor": COLORS["navy"],
            "bordercolor": COLORS["navy"],
            "font": {"family": FONT_FAMILY, "color": COLORS["on-navy"]},
        },
        separators=".,",
    )
    # fixedrange: 모바일에서 스크롤이 차트 확대로 바뀌는 것을 막는다.
    figure.update_xaxes(
        fixedrange=True,
        gridcolor=COLORS["grid"],
        zeroline=False,
        tickfont={"color": COLORS["ink-muted"]},
    )
    figure.update_yaxes(fixedrange=True, showgrid=False, zeroline=False, ticklabelstandoff=8)
    return figure
