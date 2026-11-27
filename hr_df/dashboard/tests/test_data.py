"""데이터 로드와 검증의 실패 경로."""

import pandas as pd
import pytest

from core import config, data, validation
from core.exceptions import DataLoadError, DataValidationError


def test_real_files_load(analysis_df):
    loaded = data.load_analysis_data()
    pd.testing.assert_frame_equal(loaded, analysis_df)


@pytest.mark.parametrize("loader", [data.load_verified_data, data.load_analysis_data])
def test_loaders_compare_with_raw(tmp_path, processed_df, loader):
    path = tmp_path / "truncated.csv"
    processed_df.iloc[:-1].to_csv(path, index=False)
    with pytest.raises(DataValidationError, match="행 수"):
        loader(processed_path=path)


def test_missing_file(tmp_path):
    with pytest.raises(DataLoadError, match="찾을 수 없습니다"):
        data.load_processed_data(tmp_path / "missing.csv")


def test_directory_instead_of_file(tmp_path):
    with pytest.raises(DataLoadError, match="찾을 수 없습니다"):
        data.load_processed_data(tmp_path)


def test_unreadable_file(tmp_path, monkeypatch):
    path = tmp_path / "locked.csv"
    path.write_text("a\n1\n", encoding="utf-8")

    def deny(*args, **kwargs):
        raise PermissionError("locked")

    monkeypatch.setattr(pd, "read_csv", deny)
    with pytest.raises(DataLoadError, match="읽을 수 없습니다"):
        data.load_processed_data(path)


@pytest.mark.parametrize(
    "content",
    [b"", b"a,b\n1,2\n1,2,3,4\n", b'a,b\n"unclosed,2\n', b"a,b\n\xff\xfe\xfa,1\n"],
    ids=["empty", "field-count", "quote", "encoding"],
)
def test_broken_csv(tmp_path, content):
    path = tmp_path / "broken.csv"
    path.write_bytes(content)
    with pytest.raises(DataLoadError):
        data.load_processed_data(path)


@pytest.mark.requires_data
def test_extra_field_in_every_row(tmp_path):
    header, *rows = config.PROCESSED_DATA_PATH.read_text(encoding="utf-8-sig").splitlines()
    path = tmp_path / "shifted.csv"
    path.write_text("\n".join([header, *(row + ",extra" for row in rows)]), encoding="utf-8")
    with pytest.raises(DataLoadError, match="열 개수"):
        data.load_processed_data(path)


@pytest.mark.requires_data
def test_header_only(tmp_path):
    path = tmp_path / "header.csv"
    header = config.PROCESSED_DATA_PATH.read_text(encoding="utf-8-sig").splitlines()[0]
    path.write_text(header + "\n", encoding="utf-8")
    with pytest.raises(DataValidationError, match="행이 없습니다"):
        data.load_processed_data(path)


@pytest.mark.parametrize("newline", ["\n", "\r\n"], ids=["LF", "CRLF"])
@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig"])
def test_line_endings_and_bom(tmp_path, processed_df, newline, encoding):
    lines = config.PROCESSED_DATA_PATH.read_text(encoding="utf-8-sig").splitlines()
    path = tmp_path / "copy.csv"
    path.write_bytes((newline.join(lines) + newline).encode(encoding))
    pd.testing.assert_frame_equal(data.load_processed_data(path), processed_df)


@pytest.mark.parametrize(
    "column,value,message",
    [
        ("Age", None, "결측치"),
        ("Age", 34.5, "정수형"),
        ("Age", "unknown", "정수형"),
        ("Age", -1, "범위"),
        ("JobSatisfaction", 5, "범위"),
        ("StockOptionLevel", 4, "범위"),
        ("AttritionBinary", 2, "범위"),
        ("Department", "Finance", "허용되지 않은 값"),
        ("OverTime", "yes", "허용되지 않은 값"),
        ("Gender", " Male", "허용되지 않은 값"),
        ("TenureGroup", "Over 10 Years", "파생 규칙"),
        ("AttritionBinary", 0, "파생 규칙"),
        ("YearsInCurrentRole", 99, "모순된 행"),
        ("EmployeeNumber", 2, "중복"),
    ],
)
def test_invalid_value(processed_df, column, value, message):
    broken = processed_df.copy()
    if value is None or isinstance(value, float):
        broken[column] = broken[column].astype(float)
    elif isinstance(value, str):
        broken[column] = broken[column].astype(object)
    broken.loc[0, column] = value
    with pytest.raises(DataValidationError, match=message):
        validation.validate_processed(broken)


def test_missing_column(processed_df):
    with pytest.raises(DataValidationError, match="누락된 컬럼"):
        validation.validate_processed(processed_df.drop(columns="MonthlyIncome"))


def test_unknown_column(processed_df):
    with pytest.raises(DataValidationError, match="정의되지 않은 컬럼"):
        validation.validate_processed(processed_df.assign(HireDate="2026-01-01"))


def test_duplicate_row(processed_df):
    broken = pd.concat([processed_df, processed_df.head(1)], ignore_index=True)
    with pytest.raises(DataValidationError, match="완전 중복 행"):
        validation.validate_processed(broken)


def test_multiple_problems_are_reported_together(processed_df):
    broken = processed_df.copy()
    broken.loc[0, "Age"] = -1
    broken.loc[0, "OverTime"] = "?"
    with pytest.raises(DataValidationError) as caught:
        validation.validate_processed(broken)
    assert len(caught.value.problems) >= 2


def test_raw_constant_changed(raw_df):
    broken = raw_df.copy()
    broken.loc[0, "StandardHours"] = 40
    with pytest.raises(DataValidationError, match="StandardHours"):
        validation.validate_raw(broken)


@pytest.mark.parametrize(
    "mutate,message",
    [
        (lambda df: df.iloc[:-1], "행 수"),
        (lambda df: df.iloc[::-1].reset_index(drop=True), "다른 컬럼"),
        (lambda df: df[df.columns[::-1]], "컬럼 순서"),
        (lambda df: df.assign(MonthlyIncome=df["MonthlyIncome"] + 1), "MonthlyIncome"),
    ],
    ids=["truncated", "row-order", "column-order", "plausible-edit"],
)
def test_lineage_detects_schema_valid_tampering(raw_df, processed_df, mutate, message):
    broken = mutate(processed_df)
    validation.validate_processed(broken)  # 스키마 검증만으로는 통과한다.
    with pytest.raises(DataValidationError, match=message):
        validation.validate_lineage(raw_df, broken)
