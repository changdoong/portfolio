"""표시 형식. 계산값은 여기서만 반올림한다."""

MISSING = "—"


def count(value: int) -> str:
    return f"{value:,}"


def percent(value: float | None) -> str:
    return MISSING if value is None else f"{value:.2f}%"
