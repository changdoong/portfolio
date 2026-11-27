"""1단계 로더에 Streamlit 캐시를 연결한다."""

from pathlib import Path

import pandas as pd
import streamlit as st

from core import config, data


def _file_version(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except OSError:
        return None  # 안내 메시지는 1단계 로더가 만든다.
    return stat.st_mtime_ns, stat.st_size


@st.cache_data(show_spinner="데이터를 검증하는 중입니다.", max_entries=2)
def _load(versions: tuple[tuple[int, int] | None, ...]) -> pd.DataFrame:
    # versions는 파일이 바뀌면 캐시를 무효화하기 위한 키이다.
    return data.load_analysis_data()


def get_analysis_data() -> pd.DataFrame:
    paths = (config.RAW_DATA_PATH, config.PROCESSED_DATA_PATH)
    return _load(tuple(_file_version(path) for path in paths))
