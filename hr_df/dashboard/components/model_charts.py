"""Machine Learning 화면의 차트와 표. 수치는 core.evaluation의 결과만 쓴다."""

from html import escape

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from components import theme
from core.evaluation import LR_NAME, METRICS, RF_NAME, ModelResult, display_name

MODEL_COLORS = {LR_NAME: theme.COLORS["series-1"], RF_NAME: theme.COLORS["series-2"]}
CLASS_LABELS = ("재직(0)", "이직(1)")
ROW_HEIGHT = 30
BAR_WIDTH = 0.6


def metric_text(value: float) -> str:
    return f"{value:.4f}"


def metric_table_html(results: tuple[ModelResult, ...]) -> str:
    """지표별로 더 높은 값을 굵게 표시한다(같으면 둘 다). 색만으로 구분하지 않도록 ▲ 표시를 붙인다."""
    best = {metric: max(result.metrics[metric] for result in results) for metric in METRICS}
    headers = "".join(f'<th scope="col">{escape(name)}</th>' for name in ("모델", *METRICS))
    rows = []
    for result in results:
        cells = []
        for metric in METRICS:
            value = metric_text(result.metrics[metric])
            if metric_text(best[metric]) == value:
                cells.append(f'<td class="hr-best">{value} <span aria-label="더 높음">▲</span></td>')
            else:
                cells.append(f"<td>{value}</td>")
        swatch = f'<span class="hr-swatch hr-swatch--{slug(result.name)}"></span>'
        rows.append(f'<tr><th scope="row">{swatch}{escape(result.name)}</th>{"".join(cells)}</tr>')
    return (
        '<div class="hr-table-scroll"><table class="hr-table">'
        f"<thead><tr>{headers}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
    )


def slug(name: str) -> str:
    return "lr" if name == LR_NAME else "rf"


def metric_figure(results: tuple[ModelResult, ...]) -> go.Figure:
    """지표별 두 모델 비교(묶음 가로 막대). 축은 0~1로 고정한다."""
    figure = go.Figure()
    labels = list(METRICS)
    for result in results:
        values = [result.metrics[metric] for metric in METRICS]
        figure.add_trace(
            go.Bar(
                name=result.name,
                x=values,
                y=labels,
                orientation="h",
                marker={"color": MODEL_COLORS[result.name]},
                text=[metric_text(v) for v in values],
                textposition="outside",
                textfont={"color": theme.COLORS["ink"]},
                hovertemplate=f"<b>{escape(result.name)}</b><br>%{{y}} %{{x:.4f}}<extra></extra>",
            )
        )
    theme.style_figure(figure, height=360)
    figure.update_layout(
        barmode="group",
        bargap=0.3,
        bargroupgap=0.12,
        barcornerradius=4,
        # 좁은 화면에서 범례가 두 줄이 되어도 막대 숫자를 가리지 않도록 그림 영역 위에 고정한다.
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0, "xanchor": "left"},
        margin={"l": 96, "r": 24, "t": 64, "b": 36},
    )
    figure.update_xaxes(range=[0, 1.12], tickvals=[0, 0.25, 0.5, 0.75, 1.0])
    figure.update_yaxes(autorange="reversed")
    return figure


def confusion_figure(result: ModelResult) -> go.Figure:
    """2×2 혼동행렬. 칸마다 건수와 의미를 함께 적는다."""
    matrix = np.array(result.confusion)
    names = np.array([["TN 정상 분류", "FP 오탐"], ["FN 놓친 이직", "TP 탐지한 이직"]])
    peak = matrix.max()
    figure = go.Figure(
        go.Heatmap(
            z=matrix,
            x=list(CLASS_LABELS),
            y=list(CLASS_LABELS),
            colorscale=[[0, theme.COLORS["tint"]], [1, theme.COLORS["navy"]]],
            zmin=0,
            zmax=peak,
            showscale=False,
            xgap=2,
            ygap=2,
            customdata=names,
            hovertemplate="실제 %{y} · 예측 %{x}<br>%{customdata}: %{z:,}명<extra></extra>",
        )
    )
    for row in range(2):
        for col in range(2):
            dark = matrix[row, col] > peak * 0.5
            figure.add_annotation(
                x=CLASS_LABELS[col],
                y=CLASS_LABELS[row],
                text=f"<b>{matrix[row, col]:,}명</b><br>{names[row, col]}",
                showarrow=False,
                font={"color": theme.COLORS["on-navy"] if dark else theme.COLORS["ink"], "size": 13},
            )
    theme.style_figure(figure, height=300)
    figure.update_layout(margin={"l": 84, "r": 16, "t": 16, "b": 56})
    figure.update_xaxes(title={"text": "예측", "font": {"color": theme.COLORS["ink-muted"]}}, side="bottom",
                        showgrid=False)
    figure.update_yaxes(title={"text": "실제", "font": {"color": theme.COLORS["ink-muted"]}},
                        autorange="reversed", tickfont={"color": theme.COLORS["ink-muted"]})
    return figure


def roc_figure(results: tuple[ModelResult, ...]) -> go.Figure:
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=[0, 1],
            y=[0, 1],
            mode="lines",
            name="무작위 분류(AUC 0.5)",
            line={"color": theme.COLORS["ink-muted"], "width": 1, "dash": "dash"},
            hoverinfo="skip",
        )
    )
    for result in results:
        figure.add_trace(
            go.Scatter(
                x=result.fpr,
                y=result.tpr,
                mode="lines",
                name=f"{result.name} (AUC {metric_text(result.metrics['ROC-AUC'])})",
                line={"color": MODEL_COLORS[result.name], "width": 2, "shape": "hv"},
                hovertemplate=(
                    f"<b>{escape(result.name)}</b><br>"
                    "위양성률(FPR) %{x:.3f}<br>재현율(TPR) %{y:.3f}<extra></extra>"
                ),
            )
        )
    theme.style_figure(figure, height=380)
    figure.update_layout(
        legend={"orientation": "h", "y": -0.2, "x": 0, "xanchor": "left"},
        margin={"l": 64, "r": 24, "t": 16, "b": 96},
        hovermode="closest",
    )
    figure.update_xaxes(range=[0, 1], title={"text": "위양성률(FPR): 재직자를 이직으로 잘못 분류한 비율"},
                        tickformat=".1f")
    figure.update_yaxes(range=[0, 1.02], title={"text": "재현율(TPR)"}, showgrid=True,
                        gridcolor=theme.COLORS["grid"], tickformat=".1f",
                        tickfont={"color": theme.COLORS["ink-muted"]})
    return figure


def ranking_figure(table: pd.DataFrame, value_column: str, *, top: int, color: str, value_label: str,
                   decimals: int) -> go.Figure:
    """변수 중요도 가로 막대(위에서부터 큰 순서). 막대 끝에 값을 적는다."""
    rows = table.head(top)
    labels = [display_name(name) for name in rows["feature"]]
    values = rows[value_column].tolist()
    figure = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            width=0.62,
            marker={"color": color},
            text=[f"{v:.{decimals}f}" for v in values],
            textposition="outside",
            textfont={"color": theme.COLORS["ink"]},
            hovertemplate=f"<b>%{{y}}</b><br>{escape(value_label)} %{{x:.{decimals}f}}<extra></extra>",
        )
    )
    theme.style_figure(figure, height=60 + ROW_HEIGHT * len(rows))
    figure.update_layout(barcornerradius=4, showlegend=False, margin={"l": 210, "r": 24, "t": 16, "b": 36})
    figure.update_xaxes(range=[0, max(values) * 1.22], title={"text": value_label})
    figure.update_yaxes(autorange="reversed")
    return figure


def dependence_figure(frame: pd.DataFrame, *, x_label: str, binary: bool) -> go.Figure:
    """변수의 원래 값과 SHAP 값. 0보다 크면 이직 예측 쪽으로 기여한다."""
    x = frame["value"]
    if binary:
        # Yes/No 두 범주는 점이 겹치므로 가로로 조금 흩뜨린다(고정 시드).
        order = {"No": 0, "Yes": 1}
        jitter = np.random.default_rng(0).uniform(-0.18, 0.18, len(frame))
        x = frame["value"].map(order) + jitter
    figure = go.Figure(
        go.Scatter(
            x=x,
            y=frame["shap"],
            mode="markers",
            marker={
                "size": 8,
                "color": theme.COLORS["series-2"],
                "opacity": 0.7,
                "line": {"width": 1, "color": theme.COLORS["surface"]},
            },
            customdata=np.stack([frame["value"].astype(str), frame["shap"]], axis=1),
            hovertemplate=f"{escape(x_label)} %{{customdata[0]}}<br>SHAP %{{y:+.4f}}<extra></extra>",
        )
    )
    theme.style_figure(figure, height=340)
    figure.add_hline(y=0, line={"color": theme.COLORS["ink-muted"], "width": 1})
    figure.update_layout(showlegend=False, margin={"l": 72, "r": 24, "t": 16, "b": 56}, hovermode="closest")
    figure.update_yaxes(title={"text": "SHAP 값(이직 예측 기여)"}, showgrid=True, gridcolor=theme.COLORS["grid"],
                        tickformat="+.2f", tickfont={"color": theme.COLORS["ink-muted"]})
    figure.update_xaxes(title={"text": x_label})
    if binary:
        figure.update_xaxes(tickvals=[0, 1], ticktext=["No", "Yes"], range=[-0.6, 1.6], showgrid=False)
    return figure
