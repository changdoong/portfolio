"""대시보드에서 사용자에게 안내할 수 있는 예외."""


class DashboardError(Exception):
    """화면과 CLI에서 공통으로 처리하는 최상위 예외."""


class DataLoadError(DashboardError):
    """데이터 파일을 읽을 수 없음."""


class DataValidationError(DashboardError):
    """데이터가 스키마 또는 전처리 규칙과 다름."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        details = "\n".join(f"- {problem}" for problem in problems)
        super().__init__(f"데이터 검증에 실패했습니다.\n{details}")


class ModelLoadError(DashboardError):
    """모델 파일을 안전하게 불러올 수 없음."""
