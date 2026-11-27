"""데이터 검증. 값을 고치지 않고, 발견한 문제를 한 번에 보고한다."""

from collections.abc import Collection, Mapping

import pandas as pd
from pandas.api.types import is_integer_dtype

from core import preprocessing, schema
from core.exceptions import DataValidationError


def _structure_problems(df: pd.DataFrame, expected: Collection[str]) -> list[str]:
    if df.empty:
        return ["데이터 행이 없습니다."]

    problems = []
    if missing := sorted(set(expected) - set(df.columns)):
        problems.append(f"누락된 컬럼: {missing}")
    if extra := sorted(set(df.columns) - set(expected)):
        problems.append(f"정의되지 않은 컬럼: {extra}")
    return problems


def _value_problems(
    df: pd.DataFrame,
    categories: Mapping[str, tuple[str, ...]],
    ranges: Mapping[str, tuple[int, int | None]],
) -> list[str]:
    problems = []

    nulls = df.isna().sum()
    if nulls.any():
        problems.append(f"결측치: {nulls[nulls > 0].to_dict()}")

    for column, allowed in categories.items():
        values = df[column].dropna()
        invalid = values[~values.isin(allowed)].unique()
        if len(invalid):
            problems.append(f"{column}: 허용되지 않은 값 {sorted(map(str, invalid))[:5]}")

    for column, (low, high) in ranges.items():
        values = df[column]
        if not is_integer_dtype(values):
            problems.append(f"{column}: 정수형이 아닙니다 (현재 {values.dtype}).")
            continue
        outside = values < low
        if high is not None:
            outside |= values > high
        if outside.any():
            upper = "제한 없음" if high is None else high
            problems.append(f"{column}: 범위({low}~{upper})를 벗어난 값 {int(outside.sum())}건")

    if count := int(df.duplicated().sum()):
        problems.append(f"완전 중복 행 {count}건")
    if count := int(df[schema.ID_COLUMN].duplicated().sum()):
        problems.append(f"{schema.ID_COLUMN} 중복 {count}건")

    return problems


def _relation_problems(df: pd.DataFrame) -> list[str]:
    return [
        f"{left} > {right}인 모순된 행 {count}건"
        for left, right in schema.NOT_GREATER_THAN
        if (count := int((df[left] > df[right]).sum()))
    ]


def _raise_if_any(problems: list[str]) -> None:
    if problems:
        raise DataValidationError(problems)


def validate_raw(df: pd.DataFrame) -> None:
    _raise_if_any(_structure_problems(df, schema.RAW_COLUMNS))

    problems = _value_problems(df, schema.CATEGORIES, schema.INTEGER_RANGES)
    for column, expected in schema.CONSTANT_VALUES.items():
        if not df[column].eq(expected).all():
            problems.append(f"{column}: 모든 값이 {expected!r}이어야 합니다.")
    _raise_if_any(problems)
    _raise_if_any(_relation_problems(df))


def validate_processed(df: pd.DataFrame) -> None:
    _raise_if_any(_structure_problems(df, schema.PROCESSED_COLUMNS))
    _raise_if_any(
        _value_problems(df, schema.PROCESSED_CATEGORIES, schema.PROCESSED_INTEGER_RANGES)
    )

    problems = _relation_problems(df)
    derived = {
        schema.TENURE_COLUMN: preprocessing.tenure_group(df["YearsAtCompany"]),
        schema.TARGET_BINARY: preprocessing.attrition_binary(df[schema.TARGET]),
    }
    for column, expected in derived.items():
        if count := int(df[column].ne(expected).sum()):
            problems.append(f"{column}: 파생 규칙과 다른 행 {count}건")
    _raise_if_any(problems)


def validate_lineage(raw: pd.DataFrame, processed: pd.DataFrame) -> None:
    """스키마만으로는 알 수 없는 행 누락, 순서 변경, 값 변경을 원본과 대조해 찾는다."""
    expected = preprocessing.preprocess(raw)
    if len(expected) != len(processed):
        raise DataValidationError(
            [f"원본({len(expected)}행)과 전처리 데이터({len(processed)}행)의 행 수가 다릅니다."]
        )
    # 컬럼 순서는 모델 입력 순서이고, 행 순서는 train/test 분할을 결정한다.
    if list(expected.columns) != list(processed.columns):
        raise DataValidationError(["전처리 데이터의 컬럼 순서가 기존 분석과 다릅니다."])

    changed = [column for column in expected if not expected[column].eq(processed[column]).all()]
    if changed:
        raise DataValidationError([f"원본을 전처리한 결과와 다른 컬럼: {changed}"])
