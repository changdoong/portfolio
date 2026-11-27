"""HR Insights 화면의 집계. 모든 수치는 검증된 전체 데이터(add_analysis_groups 결과)에서 계산한다.

집단 간 차이는 기술통계이며 인과관계나 통계적 유의성을 뜻하지 않는다.
"""

from dataclasses import dataclass

import pandas as pd

from core import analytics, config, schema

ROLE_TENURE_COLUMN = "RoleTenureGroup"


@dataclass(frozen=True)
class RiskGroup:
    label: str
    column: str
    value: object
    kind: str  # "high": 전사 평균보다 높은 쪽 대표 집단, "low": 비교용 낮은 쪽 집단


# 보고서 4장·4.8절에서 이직률 차이가 가장 컸던 집단과, 같은 변수의 반대쪽 집단.
RISK_GROUPS = (
    RiskGroup("초과근무 함", "OverTime", "Yes", "high"),
    RiskGroup("근속 0~1년", schema.TENURE_COLUMN, "0-1 Years", "high"),
    RiskGroup("25세 미만", "AgeGroup", "Under 25", "high"),
    RiskGroup("월 소득 하위 25%(Q1)", "IncomeGroup", "Q1 - Low", "high"),
    RiskGroup("직무: Sales Representative", "JobRole", "Sales Representative", "high"),
    RiskGroup("미혼", "MaritalStatus", "Single", "high"),
    RiskGroup("워라밸 1점", "WorkLifeBalance", 1, "high"),
    RiskGroup("근무 환경 만족도 1점", "EnvironmentSatisfaction", 1, "high"),
    RiskGroup("직무 만족도 1점", "JobSatisfaction", 1, "high"),
    RiskGroup("초과근무 안 함", "OverTime", "No", "low"),
    RiskGroup("근속 10년 초과", schema.TENURE_COLUMN, "Over 10 Years", "low"),
    RiskGroup("35~44세", "AgeGroup", "35-44", "low"),
    RiskGroup("월 소득 상위 25%(Q4)", "IncomeGroup", "Q4 - High", "low"),
)


def company_rate(df: pd.DataFrame) -> float:
    rate = analytics.summarize_attrition(df).attrition_rate
    if rate is None:
        raise ValueError("직원이 없는 데이터로 전사 이직률을 계산할 수 없습니다.")
    return rate


def with_context(table: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    """attrition_by 결과에 전사 평균 대비 차이(%p), 배율, 전체 이직자 중 비중(%)을 더한다."""
    overall = company_rate(df)
    leavers = int(df[schema.TARGET_BINARY].sum())
    result = table.copy()
    result["diff_pp"] = result["attrition_rate"] - overall
    result["ratio"] = result["attrition_rate"] / overall
    result["leaver_share"] = result["attrition_count"] / leavers * 100 if leavers else float("nan")
    return result


def group_rates(df: pd.DataFrame, column: str) -> pd.DataFrame:
    return with_context(analytics.attrition_by(df, column), df)


def risk_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for group in RISK_GROUPS:
        table = group_rates(df, group.column)
        matched = table[table[group.column].astype(str) == str(group.value)]
        if len(matched) != 1:
            raise ValueError(f"집단을 찾을 수 없습니다: {group.label}")
        row = matched.iloc[0]
        rows.append(
            {
                "label": group.label,
                "kind": group.kind,
                "employee_count": int(row["employee_count"]),
                "attrition_count": int(row["attrition_count"]),
                "attrition_rate": float(row["attrition_rate"]),
                "diff_pp": float(row["diff_pp"]),
                "ratio": float(row["ratio"]),
                "leaver_share": float(row["leaver_share"]),
                "is_small_sample": bool(row["is_small_sample"]),
            }
        )
    return pd.DataFrame(rows)


def add_role_tenure(df: pd.DataFrame) -> pd.DataFrame:
    """현 직무 근속연수 구간. 회사 근속 구간(02번)과 같은 경계를 쓴다(보고서 4.8절)."""
    result = df.copy()
    result[ROLE_TENURE_COLUMN] = pd.cut(
        result["YearsInCurrentRole"], bins=config.TENURE_BINS, labels=config.TENURE_LABELS
    )
    return result


def tenure_comparison(df: pd.DataFrame) -> pd.DataFrame:
    """같은 구간 경계로 본 회사 근속과 현 직무 근속별 이직률."""
    company = group_rates(df, schema.TENURE_COLUMN).rename(columns={schema.TENURE_COLUMN: "group"})
    role = group_rates(add_role_tenure(df), ROLE_TENURE_COLUMN).rename(columns={ROLE_TENURE_COLUMN: "group"})
    company["basis"] = "회사 근속(YearsAtCompany)"
    role["basis"] = "현 직무 근속(YearsInCurrentRole)"
    result = pd.concat([company, role], ignore_index=True)
    result["group"] = result["group"].astype(str)
    return result


def overtime_gap_by_role(df: pd.DataFrame) -> pd.DataFrame:
    """직무별 초과근무 여부 이직률과 차이(%p). 차이가 큰 순서."""
    cross = analytics.attrition_by(df, ["JobRole", "OverTime"])
    wide = cross.pivot(index="JobRole", columns="OverTime")
    result = pd.DataFrame(
        {
            "JobRole": wide.index,
            "count_no": wide[("employee_count", "No")].to_numpy(),
            "count_yes": wide[("employee_count", "Yes")].to_numpy(),
            "left_no": wide[("attrition_count", "No")].to_numpy(),
            "left_yes": wide[("attrition_count", "Yes")].to_numpy(),
            "rate_no": wide[("attrition_rate", "No")].to_numpy(),
            "rate_yes": wide[("attrition_rate", "Yes")].to_numpy(),
        }
    )
    result["gap_pp"] = result["rate_yes"] - result["rate_no"]
    threshold = config.SMALL_SAMPLE_THRESHOLD
    result["is_small_sample"] = (result["count_no"] < threshold) | (result["count_yes"] < threshold)
    return result.sort_values("gap_pp", ascending=False, kind="mergesort", ignore_index=True)


def income_medians(df: pd.DataFrame) -> dict[str, float]:
    """이직 여부별 월 소득 중앙값(재직 'No', 이직 'Yes')."""
    medians = df.groupby(schema.TARGET)["MonthlyIncome"].median()
    return {str(key): float(value) for key, value in medians.items()}


def income_ranges(df: pd.DataFrame) -> pd.DataFrame:
    return df.groupby("IncomeGroup", observed=True)["MonthlyIncome"].agg(["min", "max"]).reset_index()


@dataclass(frozen=True)
class DepartmentProfile:
    name: str
    employee_count: int
    attrition_count: int
    attrition_rate: float
    diff_pp: float
    overtime_share: float  # 부서 인원 중 초과근무 비율(%)
    overtime_rate: float | None  # 부서 안 초과근무 집단 이직률
    no_overtime_rate: float | None
    early_count: int  # 근속 0~1년 인원
    early_rate: float | None  # 근속 0~1년 이직률
    top_role: str  # 30명 이상 직무 중 이직률이 가장 높은 직무
    top_role_count: int
    top_role_rate: float


def _rate(part: pd.DataFrame) -> float | None:
    return analytics.summarize_attrition(part).attrition_rate


def department_profiles(df: pd.DataFrame) -> list[DepartmentProfile]:
    overall = company_rate(df)
    profiles = []
    for name, part in df.groupby("Department", observed=True):
        summary = analytics.summarize_attrition(part)
        roles = analytics.attrition_by(part, "JobRole")
        roles = roles[~roles["is_small_sample"]].sort_values(
            ["attrition_rate", "employee_count"], ascending=False, kind="mergesort"
        )
        top = roles.iloc[0]
        early = part[part[schema.TENURE_COLUMN] == config.TENURE_LABELS[0]]
        profiles.append(
            DepartmentProfile(
                name=str(name),
                employee_count=summary.employee_count,
                attrition_count=summary.attrition_count,
                attrition_rate=summary.attrition_rate,
                diff_pp=summary.attrition_rate - overall,
                overtime_share=(part["OverTime"] == "Yes").mean() * 100,
                overtime_rate=_rate(part[part["OverTime"] == "Yes"]),
                no_overtime_rate=_rate(part[part["OverTime"] == "No"]),
                early_count=len(early),
                early_rate=_rate(early),
                top_role=str(top["JobRole"]),
                top_role_count=int(top["employee_count"]),
                top_role_rate=float(top["attrition_rate"]),
            )
        )
    return sorted(profiles, key=lambda p: p.attrition_rate, reverse=True)
