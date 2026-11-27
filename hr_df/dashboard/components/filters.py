"""Workforce 화면 필터. Overview에는 적용하지 않는다."""

import pandas as pd
import streamlit as st

from core import schema

# (컬럼, 표시 이름). 선택지는 schema의 허용값을 그대로 쓴다.
FILTERS = (("Department", "부서"), ("Gender", "성별"))


def apply_filters(df: pd.DataFrame, selected: dict[str, list[str]]) -> pd.DataFrame:
    """분석 구간을 만든 뒤의 전체 데이터에 적용한다. 급여 사분위는 다시 만들지 않는다."""
    mask = pd.Series(True, index=df.index)
    for column, values in selected.items():
        mask &= df[column].isin(values)
    return df[mask]


def _options(column: str) -> list[str]:
    return list(schema.CATEGORIES[column])


def reset_filters() -> None:
    """모든 필터를 전체 선택으로 되돌린다. 버튼 콜백이라 위젯을 그리기 전에 실행된다."""
    for column, _ in FILTERS:
        st.session_state[f"filter_{column}"] = _options(column)


def render_filters() -> dict[str, list[str]]:
    selected = {}
    with st.container(key="grid_filters"):
        for column_box, (column, label) in zip(st.columns(len(FILTERS)), FILTERS, strict=True):
            key = f"filter_{column}"
            # 기본값 인자 대신 세션 상태로 초깃값을 둔다. 둘을 함께 쓰면 초기화 후 경고가 뜬다.
            st.session_state.setdefault(key, _options(column))
            with column_box:
                selected[column] = st.multiselect(
                    label, _options(column), key=key, placeholder="선택 안 함"
                )
    st.button("필터 초기화", key="filter_reset", on_click=reset_filters)
    return selected


def describe(selected: dict[str, list[str]]) -> str:
    return " · ".join(
        f"{label} {len(selected[column])}/{len(schema.CATEGORIES[column])}" for column, label in FILTERS
    )
