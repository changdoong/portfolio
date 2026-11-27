"""Stage 5: Machine Learning 화면. 수치는 보고서·06·07번 Notebook의 저장된 출력과 대조한다."""

import logging
import re

import numpy as np
import pandas as pd
import pytest
import streamlit as st
from baselines import assert_displayed, notebook_tables, notebook_text, report_table, report_text
from streamlit.testing.v1 import AppTest

from components import layout, model_charts
from core import config, data, evaluation, modeling
from core.evaluation import LR_NAME, METRICS, RF_NAME
from core.exceptions import DataLoadError, ModelLoadError
from views import machine_learning


@pytest.fixture(autouse=True)
def clear_cache():
    st.cache_data.clear()
    yield
    st.cache_data.clear()


@pytest.fixture(scope="module")
def report(model, split):
    return evaluation.build_report(model, split)


def _ml_page():
    from views import machine_learning

    machine_learning.render()


def _html(app: AppTest) -> str:
    return "\n".join(item.proto.body for item in app.main.get("html"))


# 평가 지표 -----------------------------------------------------------------


@pytest.mark.parametrize("name", [LR_NAME, RF_NAME])
def test_metrics_match_report(report, name):
    result = report.baseline if name == LR_NAME else report.forest
    table = report_table("모델", *METRICS)
    row = next(row for row in table.rows if row[0] == name)
    for metric in METRICS:
        assert_displayed(result.metrics[metric], row[table.header.index(metric)])


def test_metrics_match_notebook_06(report):
    rows = [row for t in notebook_tables("06") if "ROC-AUC" in t.header for row in t.rows]
    for name, *values in rows:
        result = report.baseline if name == LR_NAME else report.forest
        for metric, displayed in zip(METRICS, values, strict=True):
            assert_displayed(result.metrics[metric], displayed)


def test_confusion_matrices_are_consistent(report, split):
    positives = int(split.y_test.sum())
    for result in (report.baseline, report.forest):
        assert sum(map(sum, result.confusion)) == len(split.y_test) == report.test_count
        assert result.true_positive + result.false_negative == positives == report.test_attrition_count
        assert result.true_positive / positives == pytest.approx(result.metrics["Recall"])
        flagged = result.true_positive + result.false_positive
        assert result.true_positive / flagged == pytest.approx(result.metrics["Precision"])
        accuracy = (result.true_positive + result.true_negative) / report.test_count
        assert accuracy == pytest.approx(result.metrics["Accuracy"])


def test_baseline_confusion_matches_notebook_report(report):
    # 06번 classification_report: support 247/47, Attrition recall 0.43, precision 0.71
    text = " ".join(notebook_text("06").split())
    assert "No Attrition 0.90 0.97 0.93 247" in text and "Attrition 0.71 0.43 0.53 47" in text
    assert report.baseline.true_negative + report.baseline.false_positive == 247


def test_roc_curve_area_matches_auc(report):
    for result in (report.baseline, report.forest):
        assert result.fpr[0] == 0 and result.tpr[-1] == 1
        assert np.trapezoid(result.tpr, result.fpr) == pytest.approx(result.metrics["ROC-AUC"], abs=1e-12)


def test_split_counts_and_features(report):
    assert (report.train_count, report.test_count, report.test_attrition_count) == (1176, 294, 47)
    assert report.raw_feature_count == 31 and report.processed_feature_count == 56


def test_optuna_values_are_the_saved_outputs(report):
    saved = re.search(r"최적 F1-score: ([\d.]+)", notebook_text("06"))
    assert saved and float(saved[1]) == evaluation.OPTUNA_BEST_CV_F1
    assert f"- 탐색 횟수: {evaluation.OPTUNA_TRIALS}회" in report_text()
    assert f"**최적 교차검증 F1-score:** {evaluation.OPTUNA_BEST_CV_F1:.4f}" in report_text()
    table = report_table("파라미터", "최적값")
    assert {name: str(value) for name, value in report.forest_params.items()} == dict(table.rows)


def test_baseline_is_not_saved(model, split):
    # 기준 모델은 메모리에서만 맞추며 models 폴더에 새 파일을 만들지 않는다.
    before = sorted(path.name for path in (config.PROJECT_ROOT / "models").iterdir())
    evaluation.evaluate_models(model, split)
    assert sorted(path.name for path in (config.PROJECT_ROOT / "models").iterdir()) == before


# 변수 중요도와 SHAP -----------------------------------------------------------


def test_impurity_importance(report, model):
    table = report.impurity_ranking
    assert len(table) == 56 and table["importance"].sum() == pytest.approx(1.0)
    assert table["importance"].is_monotonic_decreasing
    expected = model.named_steps["classifier"].feature_importances_
    assert sorted(table["importance"]) == pytest.approx(sorted(expected))


def test_shap_matches_notebook_07(report):
    tables = [t for t in notebook_tables("07") if "Mean_ABS_SHAP" in t.header]
    assert len(tables) == 1 and len(tables[0].rows) == 20
    for index, (feature, displayed) in enumerate(tables[0].rows):
        assert report.shap_ranking.loc[index, "feature"] == feature
        assert_displayed(report.shap_ranking.loc[index, "mean_abs_shap"], displayed)


def test_shap_matches_report_table(report):
    table = report_table("순위", "변수", "Mean Absolute SHAP")
    assert len(table.rows) == 15
    for rank, feature, displayed in table.rows:
        row = report.shap_ranking.loc[int(rank) - 1]
        assert evaluation.display_name(row["feature"]) == feature
        assert_displayed(row["mean_abs_shap"], displayed)


def test_shap_values_shape(report):
    assert report.shap.values.shape == (294, 56)
    assert list(report.shap.raw_features.index) == list(report.shap.values.index)


def test_report_dependence_claims_hold(report, analysis_df):
    """보고서 7.3절과 화면 설명의 방향이 실제 SHAP 값과 맞는지 확인한다."""
    overtime = evaluation.dependence_frame(report.shap, "cat__OverTime_Yes")
    assert (overtime.loc[overtime["value"] == "Yes", "shap"] > 0).all()
    assert (overtime.loc[overtime["value"] == "No", "shap"] < 0).all()

    stock = evaluation.dependence_frame(report.shap, "num__StockOptionLevel")
    assert set(stock.loc[stock["shap"] > 0, "value"]) == {0}

    income = evaluation.dependence_frame(report.shap, "num__MonthlyIncome")
    # 양의 기여는 전사 기준 월 소득 하위 25%(Q1) 범위 안에서만 나타난다.
    q1_upper = analysis_df.loc[analysis_df["IncomeGroup"] == config.INCOME_LABELS[0], "MonthlyIncome"].max()
    assert income.loc[income["shap"] > 0, "value"].max() <= q1_upper
    low = pd.qcut(income["value"], 4, labels=False) == 0
    assert income.loc[low, "shap"].mean() > 0 > income.loc[~low, "shap"].mean()

    age = evaluation.dependence_frame(report.shap, "num__Age")
    assert (age.loc[age["value"] < 25, "shap"] > 0).all()
    assert (age.loc[(age["value"] >= 35) & (age["value"] < 55), "shap"] < 0).all()


def test_dependence_uses_original_units(report, split):
    frame = evaluation.dependence_frame(report.shap, "num__MonthlyIncome")
    assert frame["value"].tolist() == split.X_test["MonthlyIncome"].tolist()


# 화면 문장 -------------------------------------------------------------------


def test_comparison_summary_is_computed(report):
    lines = machine_learning.comparison_summary(report.baseline, report.forest)
    assert lines[0] == "더 높은 지표 · Logistic Regression: Accuracy, Precision, F1-score, ROC-AUC"
    assert lines[1] == "더 높은 지표 · Random Forest + Optuna: Recall"


def test_confusion_lines(report):
    assert machine_learning.confusion_lines(report.baseline)[0] == (
        "실제 이직자 47명 중 20명을 탐지하고 27명을 놓쳤습니다(Recall 0.4255)."
    )
    assert machine_learning.confusion_lines(report.forest)[0] == (
        "실제 이직자 47명 중 23명을 탐지하고 24명을 놓쳤습니다(Recall 0.4894)."
    )


def test_metric_table_marks_higher_value_without_color_only(report):
    html = model_charts.metric_table_html((report.baseline, report.forest))
    assert html.count("▲") == len(METRICS)  # 지표마다 높은 쪽 하나(동률 없음)
    assert '<td class="hr-best">0.4894 <span aria-label="더 높음">▲</span></td>' in html


# 화면 ------------------------------------------------------------------------


@pytest.mark.requires_data
@pytest.mark.requires_model
def test_ml_page_renders():
    app = AppTest.from_function(_ml_page, default_timeout=120).run()
    html = _html(app)
    assert not app.exception and not app.error
    assert "<h1>Machine Learning</h1>" in html
    assert len(app.get("plotly_chart")) == 7
    for value in ("0.8810", "0.7143", "0.4255", "0.5333", "0.8842", "0.8537", "0.5476", "0.4894", "0.5169", "0.8093"):
        assert value in html, value
    assert "개인별 이직 위험 점수는 표시하지 않습니다" in html


@pytest.mark.requires_data
@pytest.mark.requires_model
def test_ml_dependence_selector():
    app = AppTest.from_function(_ml_page, default_timeout=120).run()
    for feature in machine_learning.FEATURE_LABELS:
        app.selectbox(key="shap_feature").set_value(feature).run()
        assert not app.exception
        assert len(app.get("plotly_chart")) == 7
        assert "이 화면의 SHAP 값으로 확인한 패턴" in _html(app)


@pytest.mark.requires_data
def test_missing_model_shows_error_without_path(monkeypatch, caplog, tmp_path):
    missing = tmp_path / "숨길 폴더" / "best_rf_optuna.pkl"
    original = modeling.load_model
    monkeypatch.setattr(modeling, "load_model", lambda: original(missing))
    with caplog.at_level(logging.ERROR, logger=layout.__name__):
        app = AppTest.from_function(_ml_page, default_timeout=60).run()
    shown = "\n".join([e.value for e in app.error] + [c.value for c in app.code] + [_html(app)])
    assert not app.exception
    assert len(app.error) == 1 and "모델을 불러오지 못해" in app.error[0].value
    assert "모델 파일을 찾을 수 없습니다: best_rf_optuna.pkl" in app.code[0].value
    assert layout.MODEL_HINT in shown
    assert str(tmp_path) not in shown and "숨길 폴더" not in shown
    assert "0.8810" not in shown and not app.get("plotly_chart")
    assert str(missing) in caplog.text  # 상세 경로는 서버 로그에만


@pytest.mark.requires_data
def test_tampered_model_is_rejected(monkeypatch):
    def fail(*args, **kwargs):
        raise ModelLoadError("모델 파일이 검증된 버전과 다릅니다: best_rf_optuna.pkl.")

    monkeypatch.setattr(modeling, "load_model", fail)
    app = AppTest.from_function(_ml_page, default_timeout=60).run()
    assert not app.exception and len(app.error) == 1
    assert "검증된 버전과 다릅니다" in app.code[0].value


def test_missing_data_shows_data_hint(monkeypatch):
    def fail():
        raise DataLoadError(f"데이터 파일을 찾을 수 없습니다: {config.PROCESSED_DATA_PATH}")

    monkeypatch.setattr(data, "load_verified_data", fail)
    app = AppTest.from_function(_ml_page, default_timeout=60).run()
    shown = "\n".join([c.value for c in app.code] + [_html(app)])
    assert not app.exception and len(app.error) == 1
    assert "데이터를 불러오지 못해" in app.error[0].value
    assert "hr_preprocessed.csv" in shown and str(config.PROJECT_ROOT) not in shown
    assert layout.DATA_HINT in shown


def test_chart_colors_use_tokens():
    from components import theme

    assert model_charts.MODEL_COLORS == {LR_NAME: theme.COLORS["series-1"], RF_NAME: theme.COLORS["series-2"]}
