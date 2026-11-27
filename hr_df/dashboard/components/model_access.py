"""저장 모델 평가와 SHAP 계산에 Streamlit 캐시를 연결한다."""

from pathlib import Path

import streamlit as st

from core import config, data, evaluation, modeling
from core.exceptions import ModelLoadError


def _file_version(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except OSError:
        return None  # 안내 메시지는 로더가 만든다.
    return stat.st_mtime_ns, stat.st_size


@st.cache_data(show_spinner="모델을 평가하고 SHAP 값을 계산하는 중입니다.", max_entries=2)
def _build(versions: tuple[tuple[int, int] | None, ...]) -> evaluation.ModelReport:
    # versions는 데이터나 모델 파일이 바뀌면 캐시를 무효화하기 위한 키이다.
    df = data.load_verified_data()
    model = modeling.load_model()
    try:
        return evaluation.build_report(model, modeling.split_dataset(df))
    except ImportError as error:  # shap 등 의존성 누락
        raise ModelLoadError(f"모델 해석에 필요한 패키지를 불러올 수 없습니다: {error.name}") from error


def get_model_report() -> evaluation.ModelReport:
    paths = (config.RAW_DATA_PATH, config.PROCESSED_DATA_PATH, config.MODEL_PATH)
    return _build(tuple(_file_version(path) for path in paths))
