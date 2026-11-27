"""05번 SQL 분석: SQL 파일, pandas 집계, 보고서, Notebook의 일치."""

import json
import re
import sqlite3

import pandas as pd
import pytest
from baselines import report_table, report_text

from core import analytics, config

SQL_PATH = config.PROJECT_ROOT / "notebooks" / "05_sql_analysis.sql"
NOTEBOOK_PATH = config.PROJECT_ROOT / "notebooks" / "05_sql_analysis.ipynb"
QUERY_NAMES = [
    "q1a_row_count", "q1b_columns", "q1c_duplicate_employee_number", "q1d_missing_values",
    "q1e_attrition_values", "q2_overall", "q3_department", "q4_gender", "q5_job_role",
    "q6a_overtime", "q6b_overtime_comparison", "q7_age_group", "q8a_tenure_years_at_company",
    "q8b_years_in_current_role", "q8c_tenure_mean_by_attrition", "q9_job_role_overtime",
]
# SQL 결과 열 -> analysis_df 열(구간 이름이 같다)
GROUPS = {
    "q3_department": "Department",
    "q4_gender": "Gender",
    "q5_job_role": "JobRole",
    "q6a_overtime": "OverTime",
    "q7_age_group": "AgeGroup",
    "q8a_tenure_years_at_company": "TenureGroup",
}


def _queries() -> dict[str, str]:
    parts = re.split(r"^-- name: (\w+)\s*$", SQL_PATH.read_text(encoding="utf-8"), flags=re.M)
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


def _run(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    con = sqlite3.connect(":memory:")
    try:
        frame.to_sql("hr", con, index=False)
        return {name: pd.read_sql_query(sql, con) for name, sql in _queries().items()}
    finally:
        con.close()


@pytest.fixture(scope="module")
def sql_results(raw_df):
    return _run(raw_df)


def test_sql_file_is_plain_sql():
    text = SQL_PATH.read_text(encoding="utf-8")
    assert not text.lstrip().startswith("{"), "Notebook JSON이 아니라 SQL이어야 한다."
    assert list(_queries()) == QUERY_NAMES
    # 각 쿼리 블록의 주석을 뺀 마지막 문장은 세미콜론으로 끝난다(뒤따르는 절 제목 주석은 제외).
    for name, sql in _queries().items():
        body = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--")).rstrip()
        assert body.endswith(";") and body.count(";") == 1, name


def test_basic_checks(sql_results, raw_df):
    assert sql_results["q1a_row_count"].iloc[0, 0] == len(raw_df) == 1470
    assert sql_results["q1b_columns"]["column_name"].tolist() == list(raw_df.columns)
    assert sql_results["q1c_duplicate_employee_number"]["duplicate_count"].iloc[0] == 0
    missing = sql_results["q1d_missing_values"]
    assert len(missing) == 9 and missing[["null_count", "blank_count"]].eq(0).all().all()
    counts = dict(zip(*sql_results["q1e_attrition_values"].to_dict("list").values(), strict=True))
    assert counts == {"No": 1233, "Yes": 237}


def test_overall_matches_pandas(sql_results, analysis_df):
    row = sql_results["q2_overall"].iloc[0]
    summary = analytics.summarize_attrition(analysis_df)
    assert (row.employee_count, row.attrition_count, row.retained_count) == (
        summary.employee_count, summary.attrition_count, summary.retained_count
    )
    assert row.attrition_rate == round(summary.attrition_rate, 2) == 16.12


@pytest.mark.parametrize("query", list(GROUPS))
def test_group_rates_match_pandas(sql_results, analysis_df, query):
    column = GROUPS[query]
    expected = analytics.attrition_by(analysis_df, column)
    expected[column] = expected[column].astype(str)
    actual = sql_results[query].set_index(column)
    assert sorted(actual.index) == sorted(expected[column])
    for row in expected.itertuples():
        group = getattr(row, column)
        assert actual.loc[group, "employee_count"] == row.employee_count, group
        assert actual.loc[group, "attrition_count"] == row.attrition_count, group
        assert actual.loc[group, "attrition_rate"] == round(row.attrition_rate, 2), group
        if "small_sample" in actual.columns:
            assert (actual.loc[group, "small_sample"] == "Y") == bool(row.is_small_sample), group


def test_cross_matches_pandas(sql_results, analysis_df):
    expected = analytics.attrition_by(analysis_df, ["JobRole", "OverTime"])
    actual = sql_results["q9_job_role_overtime"].set_index(["JobRole", "OverTime"])
    assert len(actual) == len(expected) == 18
    for row in expected.itertuples():
        key = (str(row.JobRole), str(row.OverTime))
        assert actual.loc[key, "employee_count"] == row.employee_count, key
        assert actual.loc[key, "attrition_count"] == row.attrition_count, key
        assert actual.loc[key, "attrition_rate"] == round(row.attrition_rate, 2), key
        assert (actual.loc[key, "small_sample"] == "Y") == bool(row.is_small_sample), key


def test_overtime_comparison(sql_results):
    row = sql_results["q6b_overtime_comparison"].iloc[0]
    assert (row.overtime_rate, row.no_overtime_rate, row.diff_pp) == (30.53, 10.44, 20.09)


def test_department_gap_to_overall(sql_results):
    table = sql_results["q3_department"]
    assert table["overall_rate"].eq(16.12).all()
    assert (table["attrition_rate"] - table["overall_rate"]).round(2).tolist() == table["diff_pp"].tolist()


def test_tenure_means_match_report(sql_results):
    reported = {row[0]: row for row in report_table("변수", "재직 직원 평균", "이직 직원 평균", "재직 직원 중앙값", "이직 직원 중앙값").rows}
    means = sql_results["q8c_tenure_mean_by_attrition"].set_index("Attrition")
    for column, variable in (("mean_years_at_company", "YearsAtCompany"), ("mean_years_in_current_role", "YearsInCurrentRole")):
        assert f"{means.loc['No', column]:.2f}" == reported[variable][1]
        assert f"{means.loc['Yes', column]:.2f}" == reported[variable][2]


def test_empty_table_has_no_division_error(raw_df):
    results = _run(raw_df.iloc[:0])
    assert results["q2_overall"]["attrition_rate"].isna().all()
    assert results["q6b_overtime_comparison"].isna().all().all()


def test_results_are_aggregates_only(sql_results, raw_df):
    for name, frame in sql_results.items():
        assert "EmployeeNumber" not in frame.columns, name
        assert len(frame) <= len(raw_df.columns), name


def test_report_sql_section_matches_sql(sql_results):
    text = report_text()
    assert "### 4.8 SQL 기반 집계 재현과 교차 검증 (05번)" in text
    cross = report_table("직무", "초과근무", "직원 수", "이직자 수", "이직률", "비고").rows
    actual = sql_results["q9_job_role_overtime"].set_index(["JobRole", "OverTime"])
    assert len(cross) == 18
    for role, overtime, total, left, rate, note in cross:
        row = actual.loc[(role, overtime)]
        assert (int(total), int(left), rate) == (row.employee_count, row.attrition_count, f"{row.attrition_rate:.2f}%")
        assert (note == "30명 미만") == (row.small_sample == "Y"), (role, overtime)
    role_tenure = report_table("현 직무 근속", "직원 수", "이직자 수", "이직률", "같은 구간의 회사 근속 이직률(4.4)").rows
    role = sql_results["q8b_years_in_current_role"]
    company = sql_results["q8a_tenure_years_at_company"]
    assert [(int(t.replace(",", "")), int(l), r, c) for _, t, l, r, c in role_tenure] == [
        (a.employee_count, a.attrition_count, f"{a.attrition_rate:.2f}%", f"{b.attrition_rate:.2f}%")
        for a, b in zip(role.itertuples(), company.itertuples(), strict=True)
    ]


def test_notebook_runs_the_sql_file():
    nb = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    code = "\n".join("".join(cell["source"]) for cell in nb["cells"] if cell["cell_type"] == "code")
    assert '"05_sql_analysis.sql"' in code
    assert "GROUP BY" not in code, "쿼리는 SQL 파일에만 둔다."
    outputs = [output for cell in nb["cells"] for output in cell.get("outputs", [])]
    assert not [output for output in outputs if output["output_type"] == "error"]
    printed = "".join("".join(output.get("text", [])) for output in outputs)
    assert f"실행한 쿼리: {len(QUERY_NAMES)}" in printed
    assert "비교 27개 집단 중 일치 27개" in printed
