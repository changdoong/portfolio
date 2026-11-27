"""CSV 로드. 모든 로더는 파일을 읽기만 한다."""

from pathlib import Path

import pandas as pd

from core import analytics, config, validation
from core.exceptions import DataLoadError


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise DataLoadError(f"데이터 파일을 찾을 수 없습니다: {path}")
    try:
        df = pd.read_csv(path, encoding="utf-8-sig")
    except (OSError, ValueError) as error:
        # pandas의 EmptyDataError, ParserError와 UnicodeDecodeError는 ValueError의 하위 클래스이다.
        raise DataLoadError(f"데이터 파일을 읽을 수 없습니다: {path} ({error})") from error

    # 모든 행에 필드가 하나 더 있으면 pandas가 첫 열을 index로 바꿔 값이 밀린다.
    if not df.empty and not isinstance(df.index, pd.RangeIndex):
        raise DataLoadError(f"헤더와 데이터의 열 개수가 다릅니다: {path}")
    return df


def load_raw_data(path: Path = config.RAW_DATA_PATH) -> pd.DataFrame:
    df = _read_csv(path)
    validation.validate_raw(df)
    return df


def load_processed_data(path: Path = config.PROCESSED_DATA_PATH) -> pd.DataFrame:
    df = _read_csv(path)
    validation.validate_processed(df)
    return df


def load_verified_data(
    raw_path: Path = config.RAW_DATA_PATH,
    processed_path: Path = config.PROCESSED_DATA_PATH,
) -> pd.DataFrame:
    """원본과 대조를 마친 전처리 데이터. 모델 입력에 사용한다."""
    raw = load_raw_data(raw_path)
    processed = load_processed_data(processed_path)
    validation.validate_lineage(raw, processed)
    return processed


def load_analysis_data(
    raw_path: Path = config.RAW_DATA_PATH,
    processed_path: Path = config.PROCESSED_DATA_PATH,
) -> pd.DataFrame:
    """분석 구간까지 추가한 데이터. 화면의 필터는 이 결과에 적용한다."""
    return analytics.add_analysis_groups(load_verified_data(raw_path, processed_path))
