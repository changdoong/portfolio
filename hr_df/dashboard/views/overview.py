"""Overview 화면."""

from components import data_access, department, kpi, layout
from core import analytics
from core.exceptions import DashboardError


def render() -> None:
    layout.page_header("Overview", "전체 인력과 부서별 이직 현황")
    try:
        df = data_access.get_analysis_data()
        summary = analytics.summarize_attrition(df)
    except DashboardError as error:
        layout.load_error(error)
        return

    kpi.render(summary)
    department.render(df, summary)
    layout.footnote(
        "데이터에 기간 정보가 없어 연간 이직률로 해석할 수 없습니다. "
        "부서마다 인원 규모가 다르며, 부서 간 차이는 인과관계나 통계적 유의성을 뜻하지 않습니다."
    )
