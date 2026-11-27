"""06·07번 Notebook의 모델 평가와 SHAP 해석을 재현한다.

- Random Forest + Optuna: 저장된 모델(models/best_rf_optuna.pkl)을 그대로 쓴다. 다시 학습하지 않는다.
- Logistic Regression: 06번은 기준 모델을 저장하지 않았다. 06번과 같은 설정
  (같은 분할, 저장 모델의 전처리기, max_iter=1000, random_state=42)으로 메모리에서만 다시 맞추고,
  파일로 저장하지 않는다. 결과가 보고서·Notebook 수치와 같은지는 테스트가 확인한다.
- SHAP: 07번과 같이 TreeExplainer로 테스트 데이터 294건의 이직 클래스 SHAP 값을 계산한다.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.pipeline import Pipeline

from core import config
from core.modeling import DatasetSplit

LR_NAME = "Logistic Regression"
RF_NAME = "Random Forest + Optuna"
METRICS = ("Accuracy", "Precision", "Recall", "F1-score", "ROC-AUC")
THRESHOLD = 0.5  # predict()의 기본 분류 기준. 06번 평가와 같다.
# 06번 Notebook에 저장된 Optuna 최적 교차검증 F1(30회 탐색, Stratified 5-Fold).
# 탐색을 다시 하지 않고 저장된 출력값을 쓴다. 같은 값인지는 테스트가 확인한다.
OPTUNA_TRIALS = 30
OPTUNA_BEST_CV_F1 = 0.5202174840876617


@dataclass(frozen=True)
class ModelResult:
    name: str
    metrics: dict[str, float]
    confusion: tuple[tuple[int, int], tuple[int, int]]  # [[TN, FP], [FN, TP]]
    fpr: tuple[float, ...]
    tpr: tuple[float, ...]

    @property
    def true_negative(self) -> int:
        return self.confusion[0][0]

    @property
    def false_positive(self) -> int:
        return self.confusion[0][1]

    @property
    def false_negative(self) -> int:
        return self.confusion[1][0]

    @property
    def true_positive(self) -> int:
        return self.confusion[1][1]


@dataclass(frozen=True)
class ShapResult:
    values: pd.DataFrame  # 행: 테스트 직원, 열: 전처리 후 변수, 값: 이직 클래스(1) SHAP
    raw_features: pd.DataFrame  # 같은 직원의 원래 값(표준화 전)
    base_value: float


def _result(name: str, actual: pd.Series, labels: np.ndarray, probability: np.ndarray) -> ModelResult:
    fpr, tpr, _ = roc_curve(actual, probability)
    matrix = confusion_matrix(actual, labels, labels=[0, 1])
    return ModelResult(
        name=name,
        metrics={
            "Accuracy": accuracy_score(actual, labels),
            "Precision": precision_score(actual, labels, zero_division=0),
            "Recall": recall_score(actual, labels, zero_division=0),
            "F1-score": f1_score(actual, labels, zero_division=0),
            "ROC-AUC": roc_auc_score(actual, probability),
        },
        confusion=tuple(tuple(int(value) for value in row) for row in matrix),
        fpr=tuple(float(value) for value in fpr),
        tpr=tuple(float(value) for value in tpr),
    )


def baseline_model(model: Pipeline, split: DatasetSplit) -> LogisticRegression:
    """06번의 Logistic Regression 기준 모델을 같은 설정으로 메모리에서만 다시 맞춘다."""
    preprocessor = model.named_steps["preprocessor"]
    baseline = LogisticRegression(max_iter=1000, random_state=config.MODEL_RANDOM_STATE)
    return baseline.fit(preprocessor.transform(split.X_train), split.y_train)


def evaluate_models(model: Pipeline, split: DatasetSplit) -> tuple[ModelResult, ModelResult]:
    """(Logistic Regression, Random Forest + Optuna) 순서로 테스트 데이터 성능을 계산한다."""
    X_test = model.named_steps["preprocessor"].transform(split.X_test)
    baseline = baseline_model(model, split)
    return (
        _result(LR_NAME, split.y_test, baseline.predict(X_test), baseline.predict_proba(X_test)[:, 1]),
        _result(
            RF_NAME,
            split.y_test,
            model.predict(split.X_test),
            model.predict_proba(split.X_test)[:, 1],
        ),
    )


def feature_names(model: Pipeline) -> list[str]:
    return list(model.named_steps["preprocessor"].get_feature_names_out())


def display_name(feature: str) -> str:
    """'num__Age' → 'Age', 'cat__OverTime_Yes' → 'OverTime_Yes'."""
    return feature.split("__", 1)[-1]


def impurity_importance(model: Pipeline) -> pd.DataFrame:
    """저장된 Random Forest의 불순도 기반 변수 중요도(feature_importances_). 큰 순서."""
    table = pd.DataFrame(
        {
            "feature": feature_names(model),
            "importance": model.named_steps["classifier"].feature_importances_,
        }
    )
    return table.sort_values("importance", ascending=False, kind="mergesort", ignore_index=True)


def shap_explanation(model: Pipeline, split: DatasetSplit) -> ShapResult:
    import shap  # 무거운 패키지이므로 이 계산이 필요할 때만 불러온다.

    preprocessor = model.named_steps["preprocessor"]
    processed = preprocessor.transform(split.X_test)
    if hasattr(processed, "toarray"):
        processed = processed.toarray()
    names = feature_names(model)
    features = pd.DataFrame(processed, columns=names, index=split.X_test.index)
    explainer = shap.TreeExplainer(model.named_steps["classifier"])
    values = np.asarray(explainer.shap_values(features))
    attrition = values[:, :, 1] if values.ndim == 3 else values  # 이직 클래스(1)
    base = np.ravel(explainer.expected_value)
    return ShapResult(
        values=pd.DataFrame(attrition, columns=names, index=split.X_test.index),
        raw_features=split.X_test.copy(),
        base_value=float(base[-1]),
    )


def shap_importance(result: ShapResult) -> pd.DataFrame:
    """평균 절대 SHAP 값. 07번 Notebook의 표와 같은 순서(큰 순서)."""
    table = pd.DataFrame(
        {"feature": result.values.columns, "mean_abs_shap": result.values.abs().mean().to_numpy()}
    )
    return table.sort_values("mean_abs_shap", ascending=False, kind="mergesort", ignore_index=True)


# 07번 Notebook과 보고서 7.3절에서 해석한 변수. (전처리 후 변수, 원래 컬럼)
DEPENDENCE_FEATURES = {
    "cat__OverTime_Yes": "OverTime",
    "num__MonthlyIncome": "MonthlyIncome",
    "num__StockOptionLevel": "StockOptionLevel",
    "num__Age": "Age",
}


@dataclass(frozen=True)
class ModelReport:
    """Machine Learning 화면에 필요한 결과 묶음."""

    baseline: ModelResult
    forest: ModelResult
    shap: ShapResult
    shap_ranking: pd.DataFrame
    impurity_ranking: pd.DataFrame
    train_count: int
    test_count: int
    test_attrition_count: int
    raw_feature_count: int
    processed_feature_count: int
    forest_params: dict[str, object]


TUNED_PARAMS = (
    "n_estimators",
    "max_depth",
    "min_samples_split",
    "min_samples_leaf",
    "max_features",
    "class_weight",
)


def build_report(model: Pipeline, split: DatasetSplit) -> ModelReport:
    baseline, forest = evaluate_models(model, split)
    shap_result = shap_explanation(model, split)
    params = model.named_steps["classifier"].get_params()
    return ModelReport(
        baseline=baseline,
        forest=forest,
        shap=shap_result,
        shap_ranking=shap_importance(shap_result),
        impurity_ranking=impurity_importance(model),
        train_count=len(split.X_train),
        test_count=len(split.X_test),
        test_attrition_count=int(split.y_test.sum()),
        raw_feature_count=split.X_train.shape[1],
        processed_feature_count=len(feature_names(model)),
        forest_params={name: params[name] for name in TUNED_PARAMS},
    )


def dependence_frame(result: ShapResult, feature: str) -> pd.DataFrame:
    """변수의 원래 값(value)과 그 변수의 SHAP 값(shap). 표준화 전 단위로 보여 주기 위해 원래 값을 쓴다."""
    column = DEPENDENCE_FEATURES[feature]
    return pd.DataFrame(
        {"value": result.raw_features[column].to_numpy(), "shap": result.values[feature].to_numpy()},
        index=result.values.index,
    )
