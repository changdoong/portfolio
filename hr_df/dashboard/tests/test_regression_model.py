"""06번 Notebook과 보고서의 모델 수치를 재현한다. 학습한 객체는 저장하지 않는다."""

import re

import numpy as np
import pytest
from baselines import assert_displayed, notebook_tables, notebook_text, report_table, report_text
from sklearn.base import clone
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score

from core import config

LR = "Logistic Regression"
RF = "Random Forest + Optuna"
METRICS = ("Accuracy", "Precision", "Recall", "F1-score", "ROC-AUC")


@pytest.fixture(scope="module")
def predictions(model, split):
    preprocessor = model.named_steps["preprocessor"]
    baseline = LogisticRegression(max_iter=1000, random_state=config.MODEL_RANDOM_STATE)
    baseline.fit(preprocessor.transform(split.X_train), split.y_train)
    X_test = preprocessor.transform(split.X_test)
    return {
        LR: (baseline.predict(X_test), baseline.predict_proba(X_test)[:, 1]),
        RF: (model.predict(split.X_test), model.predict_proba(split.X_test)[:, 1]),
    }


@pytest.fixture(scope="module")
def scores(predictions, split):
    actual = split.y_test
    return {
        name: {
            "Accuracy": accuracy_score(actual, labels),
            "Precision": precision_score(actual, labels),
            "Recall": recall_score(actual, labels),
            "F1-score": f1_score(actual, labels),
            "ROC-AUC": roc_auc_score(actual, probability),
        }
        for name, (labels, probability) in predictions.items()
    }


@pytest.mark.parametrize("name", [LR, RF])
@pytest.mark.parametrize("metric", METRICS)
def test_report_metrics(scores, name, metric):
    table = report_table("모델", *METRICS)
    row = next(row for row in table.rows if row[0] == name)
    assert_displayed(scores[name][metric], row[table.header.index(metric)])


def test_report_baseline_table(scores):
    table = report_table("평가 지표", "점수")
    assert len(table.rows) == len(METRICS)
    for metric, displayed in table.rows:
        assert_displayed(scores[LR][metric], displayed)


def test_notebook_metrics(scores):
    tables = [table for table in notebook_tables("06") if "ROC-AUC" in table.header]
    rows = [row for table in tables for row in table.rows]
    assert len(rows) == 4  # 개별 결과 2행 + 비교표 2행
    for name, *values in rows:
        for metric, displayed in zip(METRICS, values, strict=True):
            assert_displayed(scores[name][metric], displayed)


def test_notebook_classification_report(predictions, split):
    expected = classification_report(
        split.y_test,
        predictions[LR][0],
        target_names=["No Attrition", "Attrition"],
        zero_division=0,
    )
    assert " ".join(expected.split()) in " ".join(notebook_text("06").split())


def test_notebook_first_ten_probabilities(predictions):
    tables = [table for table in notebook_tables("06") if "Attrition Probability" in table.header]
    assert len(tables) == 1 and len(tables[0].rows) == 10
    labels, probability = predictions[LR]
    for index, (_, predicted, displayed) in enumerate(tables[0].rows):
        assert labels[index] == int(predicted)
        assert_displayed(probability[index], displayed)


def test_split_and_feature_counts(model, split):
    report = report_text()
    assert f"학습 데이터: {len(split.X_train):,}건" in report
    assert f"테스트 데이터: {len(split.X_test):,}건" in report
    feature_count = len(model.named_steps["preprocessor"].get_feature_names_out())
    assert f"전처리 후 입력 변수: {feature_count}개" in report


def test_saved_hyperparameters(model):
    params = model.named_steps["classifier"].get_params()
    table = report_table("파라미터", "최적값")
    assert len(table.rows) == 6
    for name, displayed in table.rows:
        assert str(params[name]) == displayed


def test_best_cross_validation_f1(model, split):
    candidate = clone(model).set_params(classifier__n_jobs=1)
    folds = StratifiedKFold(n_splits=5, shuffle=True, random_state=config.MODEL_RANDOM_STATE)
    actual = cross_val_score(candidate, split.X_train, split.y_train, cv=folds, scoring="f1").mean()
    saved = re.search(r"최적 F1-score: ([\d.]+)", notebook_text("06"))
    assert saved and actual == pytest.approx(float(saved[1]), abs=1e-12)


def test_saved_model_is_reproducible(model, split):
    refitted = clone(model).fit(split.X_train, split.y_train)
    np.testing.assert_allclose(
        refitted.predict_proba(split.X_test),
        model.predict_proba(split.X_test),
        rtol=0,
        atol=1e-12,
    )
