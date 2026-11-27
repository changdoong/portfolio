"""이직 현황 집계. 반올림은 표시 단계에서만 한다."""

from collections.abc import Sequence
from dataclasses import dataclass

import pandas as pd

from core import config, schema
from core.exceptions import DataValidationError


@dataclass(frozen=True)
class AttritionSummary:
    employee_count: int
    attrition_count: int
    retained_count: int
    attrition_rate: float | None  # 대상이 0명이면 0%가 아니라 None


def add_analysis_groups(df: pd.DataFrame) -> pd.DataFrame:
    """연령대와 급여 사분위를 추가한다. 반드시 필터 적용 전 전체 데이터로 호출한다."""
    result = df.copy()
    result["AgeGroup"] = pd.cut(
        result["Age"], bins=config.AGE_BINS, labels=config.AGE_LABELS, right=False
    )
    try:
        result["IncomeGroup"] = pd.qcut(result["MonthlyIncome"], q=4, labels=config.INCOME_LABELS)
    except ValueError as error:
        raise DataValidationError(["MonthlyIncome을 4개 구간으로 나눌 수 없습니다."]) from error
    result[schema.TENURE_COLUMN] = pd.Categorical(
        result[schema.TENURE_COLUMN], categories=config.TENURE_LABELS, ordered=True
    )
    return result


def summarize_attrition(df: pd.DataFrame) -> AttritionSummary:
    total = len(df)
    left = int(df[schema.TARGET_BINARY].sum())
    return AttritionSummary(
        employee_count=total,
        attrition_count=left,
        retained_count=total - left,
        attrition_rate=left / total * 100 if total else None,
    )


def attrition_by(df: pd.DataFrame, by: str | Sequence[str]) -> pd.DataFrame:
    """집단별 직원 수, 이직자 수, 이직률. 범주의 자연 순서로 반환한다."""
    keys = [by] if isinstance(by, str) else list(by)
    if unknown := [key for key in keys if key not in df.columns]:
        raise DataValidationError([f"집계할 컬럼이 없습니다: {unknown}"])

    result = df.groupby(keys, observed=True, as_index=False).agg(
        employee_count=(schema.TARGET_BINARY, "size"),
        attrition_count=(schema.TARGET_BINARY, "sum"),
    )
    result["attrition_rate"] = result["attrition_count"] / result["employee_count"] * 100
    result["is_small_sample"] = result["employee_count"] < config.SMALL_SAMPLE_THRESHOLD
    return result


def compare_by_attrition(df: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
    """재직·이직 집단의 평균, 중앙값, 표본 표준편차."""
    return df.groupby(schema.TARGET)[list(columns)].agg(["mean", "median", "std"])
