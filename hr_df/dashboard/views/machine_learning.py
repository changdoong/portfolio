"""Machine Learning 화면: 06·07번 Notebook의 모델 평가와 SHAP 해석."""

from html import escape

import pandas as pd
import streamlit as st

from components import cards, formatting, kpi, layout, model_access, model_charts, theme
from core import evaluation
from core.evaluation import LR_NAME, METRICS, RF_NAME, ModelReport, ModelResult
from core.exceptions import DashboardError

SHAP_TOP = 15
FEATURE_LABELS = {
    "cat__OverTime_Yes": "초과근무 여부(OverTime)",
    "num__MonthlyIncome": "월 소득(MonthlyIncome)",
    "num__StockOptionLevel": "스톡옵션 수준(StockOptionLevel)",
    "num__Age": "연령(Age)",
}


def _plot(figure, key: str, alt: str) -> None:
    st.plotly_chart(figure, theme=None, config=theme.PLOTLY_CONFIG, key=key, alt=alt)


def overview_kpis(report: ModelReport) -> tuple[kpi.Kpi, ...]:
    rate = report.test_attrition_count / report.test_count * 100
    return (
        kpi.Kpi("학습 데이터", formatting.count(report.train_count), "건", "80% · 층화 추출"),
        kpi.Kpi("테스트 데이터", formatting.count(report.test_count), "건", "모든 지표의 평가 기준"),
        kpi.Kpi(
            "테스트 이직자",
            formatting.count(report.test_attrition_count),
            "명",
            f"테스트 데이터의 {formatting.percent(rate)}",
            "attrition",
        ),
        kpi.Kpi(
            "입력 변수",
            formatting.count(report.raw_feature_count),
            "개",
            f"인코딩 후 {report.processed_feature_count}개",
        ),
    )


def comparison_summary(baseline: ModelResult, forest: ModelResult) -> list[str]:
    """지표별 우열을 계산해 문장으로 만든다(표시 자릿수 기준, 같으면 동률)."""
    higher = {LR_NAME: [], RF_NAME: []}
    for metric in METRICS:
        a = model_charts.metric_text(baseline.metrics[metric])
        b = model_charts.metric_text(forest.metrics[metric])
        if a != b:
            higher[LR_NAME if a > b else RF_NAME].append(metric)
    lines = [f"더 높은 지표 · {name}: {', '.join(found)}" for name, found in higher.items() if found]
    lines.append(
        "Optuna 튜닝은 교차검증 F1을 최적화했지만, 테스트 데이터에서 모든 지표가 기준 모델보다 "
        "나아지지는 않았습니다." if higher[LR_NAME] else "Random Forest + Optuna가 모든 지표에서 높거나 같습니다."
    )
    lines.append(
        "이직 클래스가 적은(불균형) 데이터이므로 Accuracy보다 Recall·Precision·F1을 함께 봐야 합니다. "
        "어느 모델이 낫다고 단정하기보다, 이직자를 놓치는 비용과 오탐 비용을 함께 고려해 선택해야 합니다."
    )
    return lines


def confusion_lines(result: ModelResult) -> list[str]:
    actual_left = result.true_positive + result.false_negative
    actual_stayed = result.true_negative + result.false_positive
    flagged = result.true_positive + result.false_positive
    return [
        f"실제 이직자 {actual_left}명 중 {result.true_positive}명을 탐지하고 "
        f"{result.false_negative}명을 놓쳤습니다(Recall {model_charts.metric_text(result.metrics['Recall'])}).",
        f"이직으로 예측한 {flagged}명 중 {result.true_positive}명이 실제 이직자였습니다"
        f"(Precision {model_charts.metric_text(result.metrics['Precision'])}).",
        f"실제 재직자 {actual_stayed}명 중 {result.false_positive}명을 이직으로 잘못 분류했습니다.",
    ]


def _positive_share(shap: pd.Series) -> float:
    return float((shap > 0).mean() * 100)


def dependence_lines(report: ModelReport, feature: str) -> list[str]:
    """보고서 7.3절의 해석을 이 화면의 실제 SHAP 값으로 다시 계산해 문장으로 만든다."""
    frame = evaluation.dependence_frame(report.shap, feature)
    if feature == "cat__OverTime_Yes":
        lines = []
        for value, label in (("Yes", "초과근무 직원"), ("No", "초과근무를 하지 않는 직원")):
            group = frame[frame["value"] == value]["shap"]
            lines.append(
                f"{label} {len(group)}명: SHAP 값이 양수(이직 예측 쪽)인 직원 비율 "
                f"{formatting.percent(_positive_share(group))}"
            )
        lines.append(
            "OverTime_Yes와 OverTime_No는 같은 원본 변수를 원-핫 인코딩한 것이므로 "
            "하나의 초과근무 변수로 해석합니다. EDA의 초과근무 집단 이직률(30.53%)과 같은 방향입니다."
        )
        return lines
    if feature == "num__MonthlyIncome":
        positive = frame[frame["shap"] > 0]["value"]
        quartiles = pd.qcut(frame["value"], 4, labels=["하위 25%", "25~50%", "50~75%", "상위 25%"])
        shares = frame.groupby(quartiles, observed=True)["shap"].apply(_positive_share)
        return [
            f"SHAP 값이 양수인 직원 {len(positive)}명의 월 소득은 모두 "
            f"{formatting.count(int(positive.max()))} 이하였습니다." if len(positive) else
            "SHAP 값이 양수인 직원이 없습니다.",
            "테스트 데이터 소득 구간별 양수 비율: "
            + " · ".join(f"{name} {formatting.percent(value)}" for name, value in shares.items()),
            "소득이 낮을수록 이직 예측 쪽으로, 높을수록 반대쪽으로 기여하는 경향입니다. 통화 단위는 원자료에 없습니다.",
        ]
    if feature == "num__StockOptionLevel":
        shares = frame.groupby("value")["shap"].agg(["size", _positive_share])
        return [
            "수준별 SHAP 양수 비율: "
            + " · ".join(
                f"{int(level)}단계 {formatting.percent(row['_positive_share'])}({int(row['size'])}명)"
                for level, row in shares.iterrows()
            ),
            "가장 낮은 수준(0)에서만 이직 예측 쪽으로 기여했습니다. 스톡옵션이 없다는 것 자체보다, "
            "직급·근속 등 함께 움직이는 변수의 영향이 섞여 있을 수 있습니다.",
        ]
    groups = pd.cut(frame["value"], bins=[0, 25, 35, 45, 55, float("inf")],
                    labels=["25세 미만", "25~34세", "35~44세", "45~54세", "55세 이상"], right=False)
    stats = frame.groupby(groups, observed=True)["shap"].agg(["size", _positive_share])
    return [
        "연령대별 SHAP 양수 비율: "
        + " · ".join(
            f"{name} {formatting.percent(row['_positive_share'])}({int(row['size'])}명)"
            for name, row in stats.iterrows()
        ),
        "낮은 연령에서 이직 예측 쪽으로 기여하고, 35세 이후에는 대부분 반대쪽입니다. 직선적인 관계가 아닙니다.",
    ]


def roc_note(baseline: ModelResult, forest: ModelResult) -> str:
    def leader(metric: str) -> str:
        return baseline.name if baseline.metrics[metric] >= forest.metrics[metric] else forest.name

    return (
        f"ROC-AUC가 더 높은 모델은 {leader('ROC-AUC')}, 분류 기준 {evaluation.THRESHOLD}에서 Recall이 더 높은 모델은 "
        f"{leader('Recall')}입니다. 실무에 쓰려면 이직자 탐지 목표에 맞춰 분류 기준을 따로 정해야 합니다"
        "(이 화면에서는 조정하지 않음)."
    )


def _section_overview(report: ModelReport) -> None:
    layout.section_header(
        "모델 개요",
        "직원 정보로 이직 여부(Attrition)를 예측하는 이진 분류 모델입니다. "
        "06번 Notebook과 같은 분할(random_state=2020158011)의 테스트 데이터로 평가합니다.",
    )
    st.html(kpi.kpi_html(overview_kpis(report)))
    params = " · ".join(f"{name}={value}" for name, value in report.forest_params.items())
    st.html(
        cards.text_grid(
            [
                cards.text_card(
                    "분석 목적",
                    [
                        "어떤 정보가 이직 예측에 쓰이는지 확인하고, 집단별 분석(EDA)과 같은 방향인지 비교합니다.",
                        "개인별 이직 위험 점수는 표시하지 않습니다. 분석 결과를 개인 인사 조치의 근거로 쓰지 않습니다.",
                    ],
                ),
                cards.text_card(
                    "Logistic Regression(기준 모델)",
                    [
                        "선형 모델. max_iter=1000, random_state=42",
                        "06번은 이 모델을 파일로 저장하지 않았습니다. 같은 설정으로 메모리에서만 다시 맞추며, "
                        "결과가 06번 Notebook·보고서 수치와 같은지 테스트로 확인합니다.",
                    ],
                ),
                cards.text_card(
                    "Random Forest + Optuna",
                    [
                        "저장된 모델(models/best_rf_optuna.pkl)을 그대로 사용합니다. 다시 학습하지 않습니다.",
                        f"Optuna {evaluation.OPTUNA_TRIALS}회 탐색, 최적 교차검증 F1 "
                        f"{evaluation.OPTUNA_BEST_CV_F1:.4f}",
                        f"최적 하이퍼파라미터: {params}",
                    ],
                ),
            ]
        )
    )


def _section_metrics(report: ModelReport) -> None:
    results = (report.baseline, report.forest)
    layout.section_header(
        "모델 성능 비교",
        f"테스트 데이터 {report.test_count}건 기준, 분류 기준 확률 {evaluation.THRESHOLD}입니다. "
        "표에서 더 높은 값에 ▲를 표시했습니다.",
    )
    with st.container(key="card_ml_metrics"):
        st.html(model_charts.metric_table_html(results))
        _plot(model_charts.metric_figure(results), "chart_ml_metrics",
              "두 모델의 지표별 점수 막대 차트. 수치는 위 표에 있습니다.")
        st.html(cards.callout("결과 요약", comparison_summary(*results)))


def _section_confusion(report: ModelReport) -> None:
    layout.section_header(
        "Confusion Matrix",
        "행은 실제, 열은 예측입니다. 이직(1)을 놓친 FN과 재직자를 이직으로 본 FP를 함께 확인합니다.",
    )
    with st.container(key="grid_ml_confusion"):
        columns = st.columns(2)
        for column, result in zip(columns, (report.baseline, report.forest), strict=True):
            with column, st.container(key=f"card_cm_{model_charts.slug(result.name)}"):
                layout.section_header(result.name, f"테스트 데이터 {report.test_count}건", level=3)
                _plot(model_charts.confusion_figure(result), f"chart_cm_{model_charts.slug(result.name)}",
                      f"{result.name} 혼동행렬. 설명은 아래 목록에 있습니다.")
                items = "".join(f"<li>{escape(line)}</li>" for line in confusion_lines(result))
                st.html(f'<ul class="hr-plain-list">{items}</ul>')


def _section_roc(report: ModelReport) -> None:
    layout.section_header(
        "ROC Curve",
        "분류 기준 확률을 바꿀 때 재현율과 위양성률이 함께 변하는 모습입니다. 곡선 아래 면적이 ROC-AUC입니다.",
    )
    with st.container(key="card_ml_roc"):
        _plot(model_charts.roc_figure((report.baseline, report.forest)), "chart_ml_roc",
              "두 모델의 ROC 곡선. AUC 값은 범례에 있습니다.")
        layout.footnote(roc_note(report.baseline, report.forest))


def _section_importance(report: ModelReport) -> None:
    layout.section_header(
        "Feature Importance",
        "저장된 Random Forest의 불순도 기반 중요도(feature_importances_)입니다. 상위 15개를 표시합니다.",
    )
    with st.container(key="card_ml_importance"):
        _plot(
            model_charts.ranking_figure(
                report.impurity_ranking, "importance", top=SHAP_TOP, color=theme.COLORS["series-2"],
                value_label="불순도 감소 기여(합계 1)", decimals=4,
            ),
            "chart_ml_importance",
            "Random Forest 변수 중요도 상위 15개 막대 차트.",
        )
        layout.footnote(
            "불순도 기반 중요도는 학습 데이터에서 계산되며, 값의 종류가 많은 연속형 변수(DailyRate, MonthlyRate 등)를 "
            "높게 평가하는 경향이 있습니다. 예측 방향(이직 쪽/재직 쪽)은 알려 주지 않으므로 아래 SHAP과 함께 봅니다. "
            "보고서와 Notebook에는 없는 보조 지표입니다."
        )


def _section_shap(report: ModelReport) -> None:
    layout.section_header(
        "SHAP Global Feature Importance",
        "테스트 데이터 294건의 평균 절대 SHAP 값(이직 클래스)입니다. 07번 Notebook의 결과와 같습니다.",
    )
    with st.container(key="card_ml_shap"):
        _plot(
            model_charts.ranking_figure(
                report.shap_ranking, "mean_abs_shap", top=SHAP_TOP, color=theme.COLORS["series-2"],
                value_label="평균 절대 SHAP 값", decimals=5,
            ),
            "chart_ml_shap",
            "평균 절대 SHAP 값 상위 15개 막대 차트.",
        )
        top = [evaluation.display_name(name) for name in report.shap_ranking["feature"].head(5)]
        st.html(
            cards.callout(
                "해석",
                [
                    f"상위 5개: {', '.join(top)}",
                    "OverTime_Yes와 OverTime_No는 같은 초과근무 변수의 두 인코딩입니다.",
                    "SHAP 값은 모델의 예측 확률에 대한 변수별 기여입니다. 변수의 인과적 영향을 뜻하지 않습니다.",
                ],
            )
        )


def _section_dependence(report: ModelReport) -> None:
    layout.section_header(
        "주요 변수의 SHAP 해석",
        "보고서 7.3절에서 해석한 4개 변수입니다. 가로축은 표준화 전 원래 값입니다.",
    )
    with st.container(key="card_ml_dependence"):
        feature = st.selectbox(
            "변수 선택",
            list(FEATURE_LABELS),
            format_func=FEATURE_LABELS.get,
            key="shap_feature",
        )
        frame = evaluation.dependence_frame(report.shap, feature)
        with st.container(key="grid_ml_dependence"):
            left, right = st.columns([3, 2])
            with left:
                _plot(
                    model_charts.dependence_figure(
                        frame, x_label=FEATURE_LABELS[feature], binary=feature == "cat__OverTime_Yes"
                    ),
                    f"chart_dependence_{feature}",
                    f"{FEATURE_LABELS[feature]}의 값과 SHAP 값 산점도. 요약은 오른쪽에 있습니다.",
                )
            with right:
                st.html(cards.text_card("이 화면의 SHAP 값으로 확인한 패턴", dependence_lines(report, feature)))
        layout.footnote("0보다 위의 점은 그 직원의 예측을 이직 쪽으로, 아래의 점은 재직 쪽으로 움직인 기여입니다.")


def _section_limits(report: ModelReport) -> None:
    recalls = [report.baseline.metrics["Recall"], report.forest.metrics["Recall"]]
    recall_line = (
        f"두 모델 모두 Recall이 {max(recalls):.4f} 이하로, 실제 이직자의 절반 이상을 놓칩니다."
        if max(recalls) < 0.5
        else f"Recall은 {min(recalls):.4f}~{max(recalls):.4f}입니다. 놓치는 이직자가 있습니다."
    )
    layout.section_header("모델의 한계와 해석 시 주의사항", "결과를 실무에 쓰기 전에 확인해야 할 사항입니다.")
    st.html(
        cards.text_grid(
            [
                cards.text_card(
                    "평가의 한계",
                    [
                        f"단일 학습/테스트 분할(테스트 {report.test_count}건, 이직 {report.test_attrition_count}명)의 "
                        "결과입니다. 분할이 바뀌면 수치가 달라질 수 있습니다.",
                        recall_line,
                        "시간 기준 검증이나 외부 데이터 검증은 하지 않았습니다.",
                    ],
                    tone="limit",
                ),
                cards.text_card(
                    "해석의 한계",
                    [
                        "SHAP과 변수 중요도는 모델의 예측 구조를 설명할 뿐, 인과관계를 입증하지 않습니다.",
                        "데이터는 IBM이 만든 가상 샘플이며, 실제 기업에 그대로 적용할 수 없습니다.",
                        "예측 결과를 개인별 인사 조치의 근거로 쓰지 않습니다.",
                    ],
                    tone="limit",
                ),
                cards.text_card(
                    "다음 단계(미구현)",
                    [
                        "분류 기준 조정과 Precision-Recall Curve 분석",
                        "교차검증 기반 모델 비교",
                        "추가 모델 검토와 성능 모니터링",
                    ],
                ),
            ]
        )
    )


def render() -> None:
    layout.page_header("Machine Learning", "이직 예측 모델의 성능과 해석")
    try:
        report = model_access.get_model_report()
    except DashboardError as error:
        layout.load_error(error)
        return

    _section_overview(report)
    _section_metrics(report)
    _section_confusion(report)
    _section_roc(report)
    _section_importance(report)
    _section_shap(report)
    _section_dependence(report)
    _section_limits(report)
