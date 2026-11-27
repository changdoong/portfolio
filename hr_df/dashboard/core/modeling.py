"""저장 모델 로드와 06_machine_learning의 데이터 분할 재현."""

import hashlib
from io import BytesIO
from pathlib import Path
from typing import NamedTuple

import joblib
import pandas as pd
import sklearn
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from core import config, schema
from core.exceptions import DataValidationError, ModelLoadError


class DatasetSplit(NamedTuple):
    X_train: pd.DataFrame
    X_test: pd.DataFrame
    y_train: pd.Series
    y_test: pd.Series


def split_dataset(df: pd.DataFrame) -> DatasetSplit:
    """load_verified_data의 결과를 받는다."""
    if list(df.index) != list(range(len(df))) or set(df.columns) != schema.PROCESSED_COLUMNS:
        # 필터링되거나 분석용 컬럼이 추가된 데이터로 분할하면 누수 또는 입력 불일치가 생긴다.
        raise DataValidationError(["모델 분할에는 필터링하지 않은 전처리 데이터가 필요합니다."])

    features = df.drop(columns=list(schema.NON_FEATURE_COLUMNS))
    target = df[schema.TARGET_BINARY]
    return DatasetSplit(
        *train_test_split(
            features,
            target,
            test_size=config.TEST_SIZE,
            random_state=config.SPLIT_RANDOM_STATE,
            stratify=target,
        )
    )


def load_model(
    path: Path = config.MODEL_PATH,
    expected_sha256: str = config.MODEL_SHA256,
) -> Pipeline:
    if sklearn.__version__ != config.MODEL_SKLEARN_VERSION:
        raise ModelLoadError(
            f"scikit-learn {config.MODEL_SKLEARN_VERSION}이 필요합니다 "
            f"(현재 {sklearn.__version__}). 프로젝트의 .venv로 실행하세요."
        )
    if not path.is_file():
        raise ModelLoadError(f"모델 파일을 찾을 수 없습니다: {path}")

    try:
        content = path.read_bytes()
    except OSError as error:
        raise ModelLoadError(f"모델 파일을 읽을 수 없습니다: {path} ({error})") from error

    # 해시를 확인한 바로 그 bytes를 역직렬화한다.
    if hashlib.sha256(content).hexdigest() != expected_sha256:
        raise ModelLoadError(
            f"모델 파일이 검증된 버전과 다릅니다: {path}. "
            "의도한 교체라면 평가를 다시 검증한 뒤 MODEL_SHA256을 갱신하세요."
        )

    try:
        model = joblib.load(BytesIO(content))
    except Exception as error:  # pickle 역직렬화는 다양한 예외를 발생시킨다.
        raise ModelLoadError(f"모델을 복원할 수 없습니다: {path} ({error})") from error

    if not isinstance(model, Pipeline) or not {"preprocessor", "classifier"} <= set(
        model.named_steps
    ):
        raise ModelLoadError("모델이 preprocessor와 classifier로 구성된 Pipeline이 아닙니다.")
    return model
