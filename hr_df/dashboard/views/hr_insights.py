"""HR Insights 화면: 분석 결과를 인사관리 관점에서 해석한다.

모든 수치는 전체 직원 데이터에서 계산한다(필터 없음). 문장 속 수치도 계산값으로 만든다.
"""

from collections.abc import Callable
from html import escape

import pandas as pd
import streamlit as st

from components import cards, data_access, formatting, group_chart, insight_charts, kpi, layout, theme
from components.cards import Insight
from core import analytics, config, insights, schema
from core.analytics import AttritionSummary
from core.exceptions import DashboardError

pct = formatting.percent
cnt = formatting.count
pp = insight_charts.signed_pp


def _plot(figure, key: str, alt: str) -> None:
    st.plotly_chart(figure, theme=None, config=theme.PLOTLY_CONFIG, key=key, alt=alt)


def _row(table: pd.DataFrame, column: str, value: str) -> pd.Series:
    matched = table[table[column].astype(str) == value]
    if len(matched) != 1:
        raise ValueError(f"{column}={value} 집단을 찾을 수 없습니다.")
    return matched.iloc[0]


def _ratio(value: float) -> str:
    return f"{value:.2f}배"


def summary_kpis(df: pd.DataFrame, summary: AttritionSummary) -> tuple[kpi.Kpi, ...]:
    early = _row(insights.group_rates(df, schema.TENURE_COLUMN), schema.TENURE_COLUMN, "0-1 Years")
    overtime = _row(insights.group_rates(df, "OverTime"), "OverTime", "Yes")
    return (
        kpi.Kpi("전체 직원 수", cnt(summary.employee_count), "명", "IBM 가상 샘플 데이터"),
        kpi.Kpi("이직자 수", cnt(summary.attrition_count), "명",
                f"전사 이직률 {pct(summary.attrition_rate)}", "attrition"),
        kpi.Kpi("이직자 중 근속 0~1년", pct(early["leaver_share"]), "",
                f"{cnt(int(early['attrition_count']))}명 / 이직자 {cnt(summary.attrition_count)}명", "attrition"),
        kpi.Kpi("이직자 중 초과근무자", pct(overtime["leaver_share"]), "",
                f"{cnt(int(overtime['attrition_count']))}명 · 초과근무자는 전체의 "
                f"{pct(overtime['employee_count'] / summary.employee_count * 100)}", "attrition"),
    )


def headline_points(risk: pd.DataFrame) -> list[str]:
    top = risk[risk["kind"] == "high"].nlargest(3, "diff_pp")
    lines = [
        "전사 평균보다 이직률이 가장 높은 집단: "
        + " · ".join(f"{row.label} {pct(row.attrition_rate)}({cnt(row.employee_count)}명)" for row in top.itertuples())
    ]
    overtime = risk[risk["label"] == "초과근무 함"].iloc[0]
    lines.append(
        f"규모가 큰 집단 중에서는 초과근무자({cnt(overtime.employee_count)}명)의 이직률이 {pct(overtime.attrition_rate)}로, "
        f"전체 이직자의 {pct(overtime.leaver_share)}가 이 집단에 속합니다."
    )
    lines.append("아래 수치는 집단 간 차이(연관성)이며, 원인을 입증하지 않습니다. 집단은 서로 겹칩니다.")
    return lines


def risk_table_html(risk: pd.DataFrame) -> str:
    headers = ("집단", "직원", "이직", "이직률", "전사 대비", "배율", "이직자 중 비중")
    head = "".join(f'<th scope="col">{escape(name)}</th>' for name in headers)
    body = "".join(
        f'<tr><th scope="row">{group_chart.row_label(row.label, row.is_small_sample)}</th>'
        f"<td>{cnt(row.employee_count)}</td><td>{cnt(row.attrition_count)}</td>"
        f"<td>{pct(row.attrition_rate)}</td><td>{pp(row.diff_pp)}</td><td>{_ratio(row.ratio)}</td>"
        f"<td>{pct(row.leaver_share)}</td></tr>"
        for row in risk.itertuples()
    )
    return (
        '<div class="hr-table-scroll"><table class="hr-table">'
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"
    )


def simple_table_html(
    headers: tuple[str, ...], rows: list[tuple[str, ...]], *, small: list[bool] | None = None, text: bool = False
) -> str:
    head = "".join(f'<th scope="col">{escape(name)}</th>' for name in headers)
    small = small or [False] * len(rows)
    body = "".join(
        f'<tr><th scope="row">{group_chart.row_label(row[0], flag)}</th>'
        + "".join(f"<td>{escape(cell)}</td>" for cell in row[1:])
        + "</tr>"
        for row, flag in zip(rows, small, strict=True)
    )
    modifier = " hr-table--text" if text else ""
    return (
        f'<div class="hr-table-scroll"><table class="hr-table{modifier}">'
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"
    )


def _render_insight(insight: Insight, evidence: Callable[[], None]) -> None:
    with st.container(key=f"card_insight_{insight.key}"):
        st.html(cards.insight_header(insight))
        evidence()
        st.html(cards.insight_body(insight))


# 인사이트 1: 초기 근속
def tenure_insight(df: pd.DataFrame) -> tuple[Insight, pd.DataFrame]:
    table = insights.tenure_comparison(df)
    company = table[table["basis"].str.startswith("회사")]
    role = table[table["basis"].str.startswith("현 직무")]
    first, last = company.iloc[0], company.iloc[-1]
    role_first = role.iloc[0]
    first_two_share = company.iloc[:2]["leaver_share"].sum()
    insight = Insight(
        key="tenure",
        tag="초기 근속",
        title="입사 초기 직원의 이직률이 가장 높습니다",
        finding=(
            f"회사 근속 0~1년 직원 {cnt(int(first.employee_count))}명 중 {cnt(int(first.attrition_count))}명이 이직해 "
            f"이직률 {pct(first.attrition_rate)}로, 10년 초과 집단({pct(last.attrition_rate)})의 "
            f"{_ratio(first.attrition_rate / last.attrition_rate)}입니다. 근속 3년 이하가 전체 이직자의 "
            f"{pct(first_two_share)}를 차지합니다."
        ),
        interpretation=[
            "근속 구간이 길어질수록 이직률이 매 구간 낮아집니다."
            if company["attrition_rate"].is_monotonic_decreasing
            else "근속이 길수록 대체로 이직률이 낮지만, 모든 구간에서 줄어들지는 않습니다.",
            f"현 직무 근속 0~1년도 {pct(role_first.attrition_rate)}로 높습니다. 회사뿐 아니라 새 직무에 "
            "적응하는 시기도 함께 살펴볼 지점입니다.",
        ],
        actions=[
            "입사 후 첫 1년 동안 온보딩, 멘토링, 정기 면담(예: 30·90·180일)을 운영하는 방안을 검토합니다.",
            "직무 이동·승진 직후 직원에게도 같은 적응 지원을 적용하는 방안을 검토합니다.",
            "확인할 지표: 근속 1년 이하 이직률, 입사 후 이탈 시점 분포.",
        ],
        limits=[
            "데이터에 입·퇴사 시점이 없어, 1년 안 어느 시점에 이탈이 집중되는지 알 수 없습니다.",
            "근속이 짧은 직원은 대체로 나이가 어리고 소득이 낮아, 근속만의 효과로 분리할 수 없습니다.",
        ],
    )
    return insight, table


# 인사이트 2: 연령·직무
def age_role_insight(df: pd.DataFrame) -> tuple[Insight, pd.DataFrame, pd.DataFrame]:
    ages = insights.group_rates(df, "AgeGroup")
    roles = insights.group_rates(df, "JobRole").sort_values(
        ["attrition_rate", "employee_count"], ascending=False, kind="mergesort", ignore_index=True
    )
    young = _row(ages, "AgeGroup", "Under 25")
    lowest_age = ages.loc[ages["attrition_rate"].idxmin()]
    highest_age = ages.loc[ages["attrition_rate"].idxmax()]
    oldest = ages.iloc[-1]
    smallest_age = ages.loc[ages["employee_count"].idxmin()]
    top_role, low_role = roles.iloc[0], roles.iloc[-1]
    big = roles[roles["employee_count"] >= 200].sort_values("attrition_rate", ascending=False).iloc[0]
    insight = Insight(
        key="age_role",
        tag="연령·직무",
        title="젊은 직원과 일부 직무에 이직이 집중됩니다",
        finding=(
            f"25세 미만 {cnt(int(young.employee_count))}명의 이직률은 {pct(young.attrition_rate)}, "
            f"{top_role.JobRole} {cnt(int(top_role.employee_count))}명은 {pct(top_role.attrition_rate)}입니다. "
            f"규모가 큰 직무 중에서는 {big.JobRole}({cnt(int(big.employee_count))}명)가 {pct(big.attrition_rate)}로 "
            f"이직자 {cnt(int(big.attrition_count))}명을 차지합니다."
        ),
        interpretation=[
            f"연령대별 이직률은 {highest_age.AgeGroup}에서 가장 높고 {lowest_age.AgeGroup}에서 가장 낮습니다"
            f"({pct(lowest_age.attrition_rate)})."
            + (f" 다만 {oldest.AgeGroup}에서 다시 {pct(oldest.attrition_rate)}로 올라, 나이에 따라 일정하게 "
               "줄어드는 관계는 아닙니다." if oldest.attrition_rate > lowest_age.attrition_rate else ""),
            f"직무 간 차이가 큽니다({top_role.JobRole} {pct(top_role.attrition_rate)} ~ "
            f"{low_role.JobRole} {pct(low_role.attrition_rate)}). 비율이 높은 직무와 이직자 수가 많은 직무를 "
            "구분해서 봐야 합니다(차트의 가로축).",
        ],
        actions=[
            f"{top_role.JobRole}: 성과 목표, 보상 구조, 근무 시간, 승진 경로를 직무 단위로 점검합니다.",
            f"{big.JobRole}: 인원이 많아 이직자 수 기준 영향이 큽니다. 초과근무 비율과 함께 확인합니다.",
            "젊은 직원: 경력 개발 경로와 내부 이동 기회를 안내하는 방안을 검토합니다.",
        ],
        limits=[
            "연령과 직무, 직급, 소득은 서로 강하게 관련되어 있어 각각의 효과를 분리하지 않았습니다.",
            f"직무별 비율은 인원이 적을수록 크게 흔들립니다. 가장 작은 연령대는 {smallest_age.AgeGroup}"
            f"({cnt(int(smallest_age.employee_count))}명)입니다.",
        ],
        small_groups=tuple(roles.loc[roles["is_small_sample"], "JobRole"]),
    )
    return insight, ages, roles


# 인사이트 3: 급여
def income_insight(df: pd.DataFrame) -> tuple[Insight, pd.DataFrame]:
    table = insights.group_rates(df, "IncomeGroup")
    low, high = table.iloc[0], table.iloc[-1]
    medians = insights.income_medians(df)
    ranges = insights.income_ranges(df)
    q1 = ranges.iloc[0]
    insight = Insight(
        key="income",
        tag="급여",
        title="월 소득 하위 25% 집단의 이직률이 가장 높습니다",
        finding=(
            f"월 소득 하위 25%(Q1, {cnt(int(q1['min']))}~{cnt(int(q1['max']))}) {cnt(int(low.employee_count))}명의 "
            f"이직률은 {pct(low.attrition_rate)}로 상위 25%(Q4, {pct(high.attrition_rate)})의 "
            f"{_ratio(low.attrition_rate / high.attrition_rate)}입니다. 이직자의 월 소득 중앙값은 "
            f"{cnt(int(medians['Yes']))}로 재직자({cnt(int(medians['No']))})보다 낮습니다."
        ),
        interpretation=[
            f"Q1에서 Q2로 넘어가며 이직률이 {pct(low.attrition_rate)}에서 {pct(table.iloc[1].attrition_rate)}로 "
            f"가장 크게 낮아집니다. Q3({pct(table.iloc[2].attrition_rate)})와 Q4({pct(high.attrition_rate)})의 "
            f"차이는 {abs(table.iloc[2].attrition_rate - high.attrition_rate):.2f}%p로, 차이가 하위 구간에 몰려 있습니다.",
            "모델 해석(SHAP)에서도 낮은 월 소득이 이직 예측 쪽으로 기여했습니다(Machine Learning 화면).",
        ],
        actions=[
            "하위 소득 구간 직원의 보상 수준을 같은 직무·직급·근속의 내부 기준과 비교해 적정성을 점검합니다.",
            "급여 외에 경력 개발, 승급 기회 등 보상 전체(Total Rewards) 관점에서 검토합니다.",
            "확인할 지표: 소득 구간별 이직률, 직급 내 보상 분포.",
        ],
        limits=[
            "소득은 직급·연령·근속과 함께 움직이므로, 급여만 올리면 이직이 줄어든다는 뜻이 아닙니다.",
            "원자료에 통화 단위와 지급 기준 시점이 없습니다. 사분위는 전사 기준으로 나눈 구간입니다.",
        ],
    )
    return insight, table


# 인사이트 4: 초과근무
def overtime_insight(df: pd.DataFrame) -> tuple[Insight, pd.DataFrame]:
    overall = insights.group_rates(df, "OverTime")
    yes, no = _row(overall, "OverTime", "Yes"), _row(overall, "OverTime", "No")
    gaps = insights.overtime_gap_by_role(df)
    higher = int((gaps["gap_pp"] > 0).sum())
    reversed_roles = gaps[gaps["gap_pp"] <= 0]["JobRole"].tolist()
    solid = gaps[~gaps["is_small_sample"]].iloc[0]
    insight = Insight(
        key="overtime",
        tag="초과근무",
        title="초과근무 집단의 이직률은 같은 직무 안에서도 대체로 높습니다",
        finding=(
            f"초과근무자 {cnt(int(yes.employee_count))}명의 이직률은 {pct(yes.attrition_rate)}, "
            f"비초과근무자 {cnt(int(no.employee_count))}명은 {pct(no.attrition_rate)}입니다"
            f"({_ratio(yes.attrition_rate / no.attrition_rate)}). {len(gaps)}개 직무 중 {higher}개에서 "
            "초과근무 집단의 이직률이 더 높았습니다."
        ),
        interpretation=[
            (f"직무를 나눠 봐도 대부분 같은 방향이므로, 직무 구성 차이만으로 나타난 결과로 보기는 어렵습니다. "
             if higher > len(gaps) / 2 else "직무에 따라 방향이 다릅니다. ")
            + f"예: {solid.JobRole} {pct(solid.rate_yes)}(초과근무) 대 {pct(solid.rate_no)}(비초과근무).",
            ("예외: " + ", ".join(reversed_roles) + "는 초과근무 집단의 이직률이 더 낮았습니다.")
            if reversed_roles else "모든 직무에서 초과근무 집단의 이직률이 더 높았습니다.",
            "모델 해석(SHAP)에서도 초과근무 여부가 가장 큰 기여 변수였습니다.",
        ],
        actions=[
            "초과근무가 특정 직무·팀에 반복적으로 몰리는지 점검하고, 업무량 배분과 인력 계획을 검토합니다.",
            "차이가 큰 직무부터 초과근무 사유(인력 부족, 일정, 업무 방식)를 파악합니다.",
            "확인할 지표: 직무별 초과근무 비율, 초과근무 집단 이직률.",
        ],
        limits=[
            "OverTime은 예/아니오 값뿐이며 초과근무 시간이나 빈도는 알 수 없습니다.",
            "초과근무를 줄이면 이직이 줄어든다는 인과관계는 이 데이터로 확인할 수 없습니다.",
        ],
        small_groups=tuple(gaps.loc[gaps["is_small_sample"], "JobRole"]),
    )
    return insight, gaps


def department_section(df: pd.DataFrame) -> None:
    profiles = insights.department_profiles(df)
    layout.section_header(
        "부서별 인력관리 시사점",
        "부서별 이직률과 함께, 부서 안에서 이직률이 높은 지점을 찾았습니다. 직무는 30명 이상인 직무만 비교했습니다.",
    )
    rows, small = [], []
    for p in profiles:
        rows.append((
            p.name, cnt(p.employee_count), cnt(p.attrition_count), pct(p.attrition_rate), pp(p.diff_pp),
            pct(p.overtime_share), pct(p.overtime_rate), pct(p.no_overtime_rate),
            f"{pct(p.early_rate)}({cnt(p.early_count)}명)"
            + (f" {group_chart.SMALL_MARK}" if p.early_count < config.SMALL_SAMPLE_THRESHOLD else ""),
        ))
        small.append(p.employee_count < config.SMALL_SAMPLE_THRESHOLD)
    with st.container(key="card_insight_department"):
        st.html(simple_table_html(
            ("부서", "직원", "이직", "이직률", "전사 대비", "초과근무 비율", "초과근무 이직률",
             "비초과근무 이직률", "근속 0~1년 이직률"),
            rows, small=small,
        ))
        department_cards = []
        for p in profiles:
            points = [
                f"{p.employee_count:,}명 중 {p.attrition_count:,}명 이직({pct(p.attrition_rate)}, 전사 대비 {pp(p.diff_pp)})",
                f"30명 이상 직무 중 이직률이 가장 높은 직무: {p.top_role}({cnt(p.top_role_count)}명, "
                f"{pct(p.top_role_rate)})",
                f"부서 안 초과근무 집단 {pct(p.overtime_rate)} 대 비초과근무 {pct(p.no_overtime_rate)}",
            ]
            if p.early_count < config.SMALL_SAMPLE_THRESHOLD:
                points.append(
                    f"※ 근속 0~1년은 {p.early_count}명뿐이라 이 집단의 이직률({pct(p.early_rate)})은 해석하기 어렵습니다."
                )
            else:
                points.append(f"근속 0~1년 {cnt(p.early_count)}명의 이직률 {pct(p.early_rate)}")
            if p.employee_count < 100:
                points.append(f"부서 인원이 {p.employee_count}명으로 적어, 몇 명의 이직으로도 비율이 크게 바뀝니다.")
            department_cards.append(cards.text_card(p.name, points))
        st.html(cards.text_grid(department_cards))
        st.html(cards.callout(
            "부서 관점 제안",
            [
                "부서 평균만 보지 말고, 부서 안의 직무·초과근무·근속 조합에서 이직이 집중되는 지점을 먼저 점검합니다.",
                f"{len(profiles)}개 부서 모두 초과근무 집단의 이직률이 비초과근무 집단보다 높았습니다. "
                "부서장과 업무량 배분을 함께 검토합니다."
                if all((p.overtime_rate or 0) > (p.no_overtime_rate or 0) for p in profiles)
                else "부서에 따라 초과근무 집단과 비초과근무 집단의 차이 방향이 다릅니다.",
                "한계: 부서 간 차이는 직무 구성 차이를 포함하며, 통계적 유의성을 검정하지 않았습니다.",
            ],
        ))


def proposals_section(risk: pd.DataFrame) -> None:
    layout.section_header(
        "데이터에 근거한 개선 제안",
        "영향 범위는 해당 집단에 속한 이직자가 전체 이직자에서 차지하는 비중입니다. 집단이 겹치므로 합계는 100%가 아닙니다.",
    )

    def evidence(label: str) -> tuple[str, str]:
        row = risk[risk["label"] == label].iloc[0]
        return (
            f"{label}: {pct(row.attrition_rate)}({cnt(row.attrition_count)}/{cnt(row.employee_count)}명), "
            f"전사 대비 {pp(row.diff_pp)}",
            pct(row.leaver_share),
        )

    items = [
        ("초과근무·업무량 점검", "초과근무 함", "직무별 초과근무 비율, 초과근무 집단 이직률"),
        ("보상 적정성 검토", "월 소득 하위 25%(Q1)", "소득 구간별 이직률, 직급 내 보상 분포"),
        ("입사 초기 정착 지원", "근속 0~1년", "근속 1년 이하 이직률, 이탈 시점"),
        ("고이직 직무 세부 진단", "직무: Sales Representative", "직무별 이직률, 목표·보상 구조"),
        ("만족도 관리", "근무 환경 만족도 1점", "만족도 점수별 이직률, 설문 응답 추이"),
    ]
    order = {label: risk.loc[risk["label"] == label, "leaver_share"].iloc[0] for _, label, _ in items}
    rows = []
    for title, label, metric in sorted(items, key=lambda item: order[item[1]], reverse=True):
        text, share = evidence(label)
        rows.append((title, text, share, metric))
    with st.container(key="card_insight_proposals"):
        st.html(simple_table_html(("제안", "근거", "영향 범위", "확인할 지표"), rows, text=True))
        layout.footnote(
            "영향 범위가 큰 순서로 정렬했습니다. 영향 범위는 집단 크기를 반영할 뿐 개선 효과를 뜻하지 않습니다. "
            "실제 조직에 적용하려면 자체 HR 데이터로 다시 확인하고, 효과는 시범 운영 등으로 검증해야 합니다."
        )


def render() -> None:
    layout.page_header("HR Insights", "분석 결과를 인사관리 관점에서 해석한 요약")
    try:
        df = data_access.get_analysis_data()
        summary = analytics.summarize_attrition(df)
        risk = insights.risk_table(df)
    except DashboardError as error:
        layout.load_error(error)
        return
    overall = summary.attrition_rate

    layout.footnote(
        f"전체 직원 {cnt(summary.employee_count)}명 기준(필터 없음). 집단 간 차이는 연관성이며 인과관계나 "
        "통계적 유의성을 뜻하지 않습니다. ※ 표시는 30명 미만 소집단입니다."
    )
    layout.section_header("전체 이직 현황 요약", "이직이 어디에 집중되는지 한눈에 봅니다.")
    st.html(kpi.kpi_html(summary_kpis(df, summary)))
    st.html(cards.callout("핵심 요약", headline_points(risk)))

    layout.section_header(
        "주요 이직 관련 지표",
        f"전사 평균 이직률({pct(overall)}) 대비 차이(%p)입니다. 주황은 평균보다 높고, 파랑은 낮은 집단입니다.",
    )
    with st.container(key="card_insight_risk"):
        ordered = risk.sort_values("diff_pp", ascending=False, ignore_index=True)
        _plot(insight_charts.diverging_figure(ordered, label_column="label", value_column="diff_pp"),
              "chart_insight_risk", "집단별 전사 평균 대비 이직률 차이 막대 차트. 수치는 아래 표에 있습니다.")
        with st.expander("수치 표 보기"):
            st.html(risk_table_html(ordered))

    layout.section_header("인사이트", "각 인사이트는 분석 결과, 근거 수치, 해석, 개선 제안, 한계 순서로 정리했습니다.")

    insight, tenure = tenure_insight(df)

    def tenure_evidence() -> None:
        _plot(insight_charts.tenure_figure(tenure, overall), "chart_insight_tenure",
              "회사 근속과 현 직무 근속 구간별 이직률 묶음 막대 차트. 수치는 아래 표에 있습니다.")
        with st.expander("수치 표 보기"):
            st.html(simple_table_html(
                ("근속 구간", "기준", "직원", "이직", "이직률", "이직자 중 비중"),
                [(insight_charts.TENURE_SHORT.get(r.group, r.group), r.basis.split("(")[0], cnt(r.employee_count),
                  cnt(r.attrition_count), pct(r.attrition_rate), pct(r.leaver_share)) for r in tenure.itertuples()],
                small=tenure["is_small_sample"].tolist(),
            ))

    _render_insight(insight, tenure_evidence)

    insight, ages, roles = age_role_insight(df)

    def age_role_evidence() -> None:
        with st.container(key="grid_insight_age_role"):
            left, right = st.columns([3, 2])
            with left:
                _plot(insight_charts.role_bubble_figure(roles, overall), "chart_insight_roles",
                      "직무별 직원 수와 이직률 산점도. 모든 직무의 수치는 아래 표에 있습니다.")
                layout.footnote("이직률 상위 직무와 인원이 가장 많은 직무만 이름을 적었습니다. "
                                "다른 점은 마우스를 올리거나 아래 표에서 확인하세요.")
                with st.expander("직무별 수치 표 보기"):
                    st.html(simple_table_html(
                        ("직무", "직원", "이직", "이직률", "전사 대비"),
                        [(r.JobRole, cnt(r.employee_count), cnt(r.attrition_count), pct(r.attrition_rate),
                          pp(r.diff_pp)) for r in roles.itertuples()],
                        small=roles["is_small_sample"].tolist(),
                    ))
            with right:
                st.html(simple_table_html(
                    ("연령대", "직원", "이직", "이직률"),
                    [(str(r.AgeGroup), cnt(r.employee_count), cnt(r.attrition_count), pct(r.attrition_rate))
                     for r in ages.itertuples()],
                    small=ages["is_small_sample"].tolist(),
                ))

    _render_insight(insight, age_role_evidence)

    insight, income = income_insight(df)

    def income_evidence() -> None:
        table = group_chart.group_table(df, "IncomeGroup")
        _plot(group_chart.rate_figure(table, "IncomeGroup", overall), "chart_insight_income",
              "월 소득 사분위별 이직률 막대 차트.")

    _render_insight(insight, income_evidence)

    insight, gaps = overtime_insight(df)

    def overtime_evidence() -> None:
        shown = gaps.assign(label=gaps["JobRole"])
        _plot(
            insight_charts.diverging_figure(shown, label_column="label", value_column="gap_pp"),
            "chart_insight_overtime",
            "직무별 초과근무 집단과 비초과근무 집단의 이직률 차이 막대 차트. 수치는 아래 표에 있습니다.",
        )
        with st.expander("수치 표 보기"):
            st.html(simple_table_html(
                ("직무", "초과근무 이직률", "비초과근무 이직률", "차이"),
                [(r.JobRole, f"{pct(r.rate_yes)} ({cnt(r.left_yes)}/{cnt(r.count_yes)})",
                  f"{pct(r.rate_no)} ({cnt(r.left_no)}/{cnt(r.count_no)})", pp(r.gap_pp)) for r in gaps.itertuples()],
                small=gaps["is_small_sample"].tolist(),
            ))
        layout.footnote("막대는 같은 직무 안에서 '초과근무 이직률 − 비초과근무 이직률'입니다. "
                        "※ 표시 직무는 두 집단 중 하나가 30명 미만입니다.")

    _render_insight(insight, overtime_evidence)

    department_section(df)
    proposals_section(risk)
    layout.footnote(
        "데이터는 IBM이 만든 가상 샘플이며 기간 정보가 없어 연간 이직률로 해석할 수 없습니다. "
        "분석 결과를 개인별 인사 조치의 근거로 사용하지 않습니다."
    )
