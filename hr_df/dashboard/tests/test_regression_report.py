"""최종 보고서의 수치와 일치하는지 검사한다. SHAP 표는 5단계에서 별도로 다룬다."""

import pytest
from baselines import assert_displayed, report_table, report_tables

from core import analytics, preprocessing, schema

COLUMN_BY_NAME = {
    "연령대": "AgeGroup",
    "성별": "Gender",
    "결혼 여부": "MaritalStatus",
    "부서": "Department",
    "직무": "JobRole",
    "소득 구간": "IncomeGroup",
    "근속 구간": "TenureGroup",
    "초과근무": "OverTime",
    "직무 만족도": "JobSatisfaction",
    "근무 환경 만족도": "EnvironmentSatisfaction",
    "워라밸": "WorkLifeBalance",
}
VALUE_BY_LABEL = {
    "25세 미만": "Under 25",
    "25~34세": "25-34",
    "35~44세": "35-44",
    "45~54세": "45-54",
    "55세 이상": "55+",
    "남성": "Male",
    "여성": "Female",
    "미혼": "Single",
    "기혼": "Married",
    "이혼": "Divorced",
    "0~1년": "0-1 Years",
    "2~3년": "2-3 Years",
    "4~5년": "4-5 Years",
    "6~10년": "6-10 Years",
    "10년 초과": "Over 10 Years",
}


def _group_rows():
    for table in report_tables():
        if table.header[-3:] != ["직원 수", "이직자 수", "이직률"]:
            continue
        for row in table.rows:
            *labels, employees, leavers, rate = row
            name, group = labels if len(labels) == 2 else (table.header[0], labels[0])
            column = COLUMN_BY_NAME[name]
            value = VALUE_BY_LABEL.get(group, group)
            yield pytest.param(column, value, employees, leavers, rate, id=f"{column}={value}")


GROUP_ROWS = list(_group_rows())


def test_all_45_group_rows_are_covered():
    assert len(GROUP_ROWS) == 45
    assert len({row.id for row in GROUP_ROWS}) == 45


@pytest.mark.parametrize("column,value,employees,leavers,rate", GROUP_ROWS)
def test_group_attrition(analysis_df, column, value, employees, leavers, rate):
    result = analytics.attrition_by(analysis_df, column)
    matched = result[result[column].astype(str) == value]
    assert len(matched) == 1
    row = matched.iloc[0]
    assert_displayed(row["employee_count"], employees)
    assert_displayed(row["attrition_count"], leavers)
    assert_displayed(row["attrition_rate"], rate)


def test_headline_numbers(processed_df):
    summary = analytics.summarize_attrition(processed_df)
    total = summary.employee_count
    expected = {
        "재직": (summary.retained_count, summary.retained_count / total * 100),
        "이직": (summary.attrition_count, summary.attrition_rate),
        "합계": (total, 100.0),
    }
    table = report_table("구분", "직원 수", "비율")
    assert len(table.rows) == 3
    for label, count, rate in table.rows:
        assert_displayed(expected[label][0], count)
        assert_displayed(expected[label][1], rate)


def test_dataset_overview(raw_df):
    summary = analytics.summarize_attrition(preprocessing.preprocess(raw_df))
    reported = dict(report_table("항목", "내용").rows)
    assert_displayed(summary.employee_count, reported["전체 관측치"])
    assert_displayed(raw_df.shape[1], reported["원본 변수"])
    assert_displayed(summary.attrition_count, reported["이직 직원"])
    assert_displayed(summary.retained_count, reported["재직 직원"])
    assert_displayed(summary.attrition_rate, reported["전체 이직률"])


def test_data_quality(raw_df):
    expected = {
        "결측치": raw_df.isna().sum().sum(),
        "완전 중복 행": raw_df.duplicated().sum(),
        "EmployeeNumber 중복": raw_df[schema.ID_COLUMN].duplicated().sum(),
        "상수형 변수": (raw_df.nunique() == 1).sum(),
    }
    table = report_table("점검 항목", "결과")
    assert len(table.rows) == len(expected)
    for label, value in table.rows:
        assert_displayed(expected[label], value)


def test_preprocessing_summary(raw_df, processed_df):
    table = report_table("항목", "원본", "전처리 후")
    assert len(table.rows) == 4
    for label, raw_value, processed_value in table.rows:
        for df, displayed in ((raw_df, raw_value), (processed_df, processed_value)):
            actual = {
                "행 수": len(df),
                "열 수": df.shape[1],
                "결측치": df.isna().sum().sum(),
                "완전 중복 행": df.duplicated().sum(),
            }[label]
            assert_displayed(actual, displayed)


def test_numeric_comparison(processed_df):
    table = report_table(
        "변수", "재직 직원 평균", "이직 직원 평균", "재직 직원 중앙값", "이직 직원 중앙값"
    )
    assert len(table.rows) == 5
    result = analytics.compare_by_attrition(processed_df, [row[0] for row in table.rows])
    keys = [("No", "mean"), ("Yes", "mean"), ("No", "median"), ("Yes", "median")]
    for column, *values in table.rows:
        for (group, statistic), displayed in zip(keys, values, strict=True):
            assert_displayed(result.loc[group, (column, statistic)], displayed)
