"""02, 03, 04번 Notebook의 저장된 출력과 일치하는지 검사한다."""

import re

import pytest
from baselines import assert_displayed, notebook_tables, notebook_text

from core import analytics


@pytest.mark.parametrize("prefix,table_count,row_count", [("03", 12, 49), ("04", 3, 10)])
def test_group_tables(analysis_df, prefix, table_count, row_count):
    tables = [table for table in notebook_tables(prefix) if "attrition_rate" in table.header]
    assert len(tables) == table_count
    assert sum(len(table.rows) for table in tables) == row_count

    for table in tables:
        column = table.header[0]
        result = analytics.attrition_by(analysis_df, column)
        assert len(result) == len(table.rows)
        for value, employees, leavers, rate in table.rows:
            matched = result[result[column].astype(str) == value]
            assert len(matched) == 1, f"{column}={value}"
            row = matched.iloc[0]
            assert_displayed(row["employee_count"], employees)
            assert_displayed(row["attrition_count"], leavers)
            assert_displayed(row["attrition_rate"], rate)


def test_group_statistics(processed_df):
    columns = [
        "Age",
        "MonthlyIncome",
        "YearsAtCompany",
        "YearsInCurrentRole",
        "YearsWithCurrManager",
    ]
    tables = [table for table in notebook_tables("03") if "median" in table.header]
    assert len(tables) == 1

    result = analytics.compare_by_attrition(processed_df, columns)
    for group, row in zip(("No", "Yes"), tables[0].rows, strict=True):
        for actual, displayed in zip(result.loc[group], row, strict=True):
            # Notebook은 .round(2) 후 표시해 '36.0'처럼 자릿수가 줄어든다.
            assert round(actual, 2) == pytest.approx(float(displayed), abs=1e-9)


def test_headline_output(processed_df):
    summary = analytics.summarize_attrition(processed_df)
    output = notebook_text("03")
    for label, value in (
        ("전체 직원 수", f"{summary.employee_count:,}명"),
        ("이직 직원 수", f"{summary.attrition_count:,}명"),
        ("재직 직원 수", f"{summary.retained_count:,}명"),
        ("전체 이직률", f"{summary.attrition_rate:.2f}%"),
    ):
        assert f"{label}: {value}" in output


def test_tenure_distribution(analysis_df):
    output = notebook_text("02")
    result = analytics.attrition_by(analysis_df, "TenureGroup")
    assert len(result) == 5
    for label, count in zip(result["TenureGroup"], result["employee_count"], strict=True):
        assert re.search(rf"^{re.escape(str(label))}\s+{count}$", output, re.MULTILINE), label
