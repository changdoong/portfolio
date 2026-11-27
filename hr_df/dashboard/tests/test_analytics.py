"""집계 경계값과 예외 상황."""

import pandas as pd
import pytest

from core import analytics, config, preprocessing
from core.exceptions import DataValidationError


@pytest.mark.parametrize(
    "age,label",
    [
        (24, "Under 25"),
        (25, "25-34"),
        (34, "25-34"),
        (35, "35-44"),
        (44, "35-44"),
        (45, "45-54"),
        (54, "45-54"),
        (55, "55+"),
    ],
)
def test_age_boundaries(processed_df, age, label):
    changed = processed_df.copy()
    changed.loc[0, "Age"] = age
    assert analytics.add_analysis_groups(changed).loc[0, "AgeGroup"] == label


@pytest.mark.parametrize(
    "years,label",
    [
        (0, "0-1 Years"),
        (1, "0-1 Years"),
        (2, "2-3 Years"),
        (3, "2-3 Years"),
        (4, "4-5 Years"),
        (5, "4-5 Years"),
        (6, "6-10 Years"),
        (10, "6-10 Years"),
        (11, "Over 10 Years"),
    ],
)
def test_tenure_boundaries(years, label):
    assert preprocessing.tenure_group(pd.Series([years])).iloc[0] == label


def test_natural_category_order(analysis_df):
    for column, labels in (
        ("AgeGroup", config.AGE_LABELS),
        ("IncomeGroup", config.INCOME_LABELS),
        ("TenureGroup", config.TENURE_LABELS),
    ):
        assert tuple(analytics.attrition_by(analysis_df, column)[column]) == labels


def test_add_groups_does_not_mutate_input(processed_df):
    before = processed_df.copy()
    analytics.add_analysis_groups(processed_df)
    pd.testing.assert_frame_equal(processed_df, before)


def test_filter_keeps_company_wide_income_groups(analysis_df):
    selected = analysis_df["Department"] == "Sales"
    filtered = analysis_df[selected]
    counts = analytics.attrition_by(filtered, "IncomeGroup")["employee_count"]
    assert counts.max() - counts.min() > 2  # 부서 내부에서 다시 4등분하지 않는다.
    assert counts.sum() == selected.sum()


def test_empty_selection(analysis_df):
    empty = analysis_df.iloc[:0]
    assert analytics.summarize_attrition(empty) == analytics.AttritionSummary(0, 0, 0, None)
    for by in ("Department", "AgeGroup", ["JobRole", "OverTime"]):
        result = analytics.attrition_by(empty, by)
        assert result.empty
        assert "attrition_rate" in result


@pytest.mark.parametrize("size,flagged", [(1, True), (29, True), (30, False), (31, False)])
def test_small_sample_boundary(analysis_df, size, flagged):
    subset = analysis_df[analysis_df["Department"] == "Sales"].head(size)
    assert analytics.attrition_by(subset, "Department")["is_small_sample"].item() is flagged


def test_cross_tab_preserves_totals(analysis_df):
    result = analytics.attrition_by(analysis_df, ["JobRole", "OverTime"])
    assert result["employee_count"].sum() == len(analysis_df)
    assert result["attrition_count"].sum() == analysis_df["AttritionBinary"].sum()


def test_unknown_column(analysis_df):
    with pytest.raises(DataValidationError, match="HireDate"):
        analytics.attrition_by(analysis_df, "HireDate")


def test_income_that_cannot_be_split(processed_df):
    with pytest.raises(DataValidationError, match="4개 구간"):
        analytics.add_analysis_groups(processed_df.assign(MonthlyIncome=1000))
