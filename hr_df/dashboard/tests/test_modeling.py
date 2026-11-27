"""모델 로드와 데이터 누수 방지."""

import hashlib
import warnings
from io import BytesIO

import joblib
import numpy as np
import pytest
import sklearn

from core import config, modeling, schema
from core.exceptions import DataValidationError, ModelLoadError


@pytest.mark.requires_model
def test_loads_without_version_warning():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        modeling.load_model()


def test_split_has_no_overlap(split, processed_df):
    train, test = set(split.X_train.index), set(split.X_test.index)
    assert not train & test
    assert train | test == set(processed_df.index)


def test_target_and_id_are_not_features(split):
    assert not set(schema.NON_FEATURE_COLUMNS) & set(split.X_train.columns)


def test_split_is_the_one_the_model_was_fitted_on(model, split):
    numeric = model.named_steps["preprocessor"].named_transformers_["num"].named_steps["scaler"]
    expected = split.X_train[list(numeric.feature_names_in_)].mean().to_numpy()
    np.testing.assert_allclose(numeric.mean_, expected, rtol=0, atol=1e-10)


def test_feature_order_matches_model(model, split):
    assert list(model.feature_names_in_) == list(split.X_test.columns)


def test_split_rejects_filtered_data(processed_df):
    with pytest.raises(DataValidationError, match="필터링하지 않은"):
        modeling.split_dataset(processed_df[processed_df["Department"] == "Sales"])


def test_split_rejects_analysis_columns(analysis_df):
    with pytest.raises(DataValidationError, match="필터링하지 않은"):
        modeling.split_dataset(analysis_df)


def test_missing_model(tmp_path):
    with pytest.raises(ModelLoadError, match="찾을 수 없습니다"):
        modeling.load_model(tmp_path / "missing.pkl")


@pytest.mark.requires_model
def test_changed_model_is_never_deserialized(tmp_path, monkeypatch):
    path = tmp_path / "changed.pkl"
    path.write_bytes(config.MODEL_PATH.read_bytes() + b"x")

    def must_not_run(*args, **kwargs):
        pytest.fail("해시가 다른 파일을 역직렬화했습니다.")

    monkeypatch.setattr(joblib, "load", must_not_run)
    with pytest.raises(ModelLoadError, match="검증된 버전과 다릅니다"):
        modeling.load_model(path)


def test_wrong_sklearn_version(monkeypatch):
    monkeypatch.setattr(sklearn, "__version__", "1.3.0")
    with pytest.raises(ModelLoadError, match="1.6.1"):
        modeling.load_model()


def test_corrupt_model(tmp_path):
    content = b"not a model"
    path = tmp_path / "corrupt.pkl"
    path.write_bytes(content)
    with pytest.raises(ModelLoadError, match="복원할 수 없습니다"):
        modeling.load_model(path, hashlib.sha256(content).hexdigest())


def test_wrong_object(tmp_path):
    buffer = BytesIO()
    joblib.dump({"not": "pipeline"}, buffer)
    path = tmp_path / "other.pkl"
    path.write_bytes(buffer.getvalue())
    with pytest.raises(ModelLoadError, match="Pipeline"):
        modeling.load_model(path, hashlib.sha256(buffer.getvalue()).hexdigest())


@pytest.mark.requires_model
def test_unreadable_model(monkeypatch):
    def deny(self):
        raise PermissionError("locked")

    monkeypatch.setattr(type(config.MODEL_PATH), "read_bytes", deny)
    with pytest.raises(ModelLoadError, match="읽을 수 없습니다"):
        modeling.load_model()
