"""데이터·모델 의존 테스트 구분 장치(conftest)를 검사한다(Stage 4C.1).

파일이 없을 때의 skip과 --require-data 실패는 데이터·모델을 뺀 임시 사본에서 실제로 실행해 확인했다.
이 파일은 그 판단에 쓰는 함수와 marker 부착 규칙을 검사한다.
"""

from pathlib import Path

import pytest
from conftest import FIXTURE_MARKERS, REQUIREMENTS, display_path, invalid_files, missing_files, requirement_message

from core import config


def test_markers_are_registered(request):
    registered = "\n".join(request.config.getini("markers"))
    assert "requires_data:" in registered
    assert "requires_model:" in registered


def test_requirements_cover_data_and_model():
    assert REQUIREMENTS == {
        "requires_data": ("RAW_DATA_PATH", "PROCESSED_DATA_PATH"),
        "requires_model": ("MODEL_PATH",),
    }


def test_existing_files_are_not_missing(monkeypatch, tmp_path):
    for name in ("RAW_DATA_PATH", "PROCESSED_DATA_PATH", "MODEL_PATH"):
        path = tmp_path / f"{name}.bin"
        path.write_bytes(b"x")
        monkeypatch.setattr(config, name, path)
    assert missing_files("requires_data") == [] and invalid_files("requires_data") == []
    assert missing_files("requires_model") == [] and invalid_files("requires_model") == []


def test_missing_files_are_reported_without_absolute_path(monkeypatch):
    # tmp_path는 conftest 설정에 따라 프로젝트 안(.pytest_tmp)에 생기므로, '프로젝트 밖' 경우는
    # 프로젝트와 겹치지 않는 가상의 경로(만들지 않음)로 확인한다.
    outside = Path(config.PROJECT_ROOT.anchor) / "hr-dashboard-test-없는 폴더" / "hr.csv"
    assert not outside.exists() and not outside.is_relative_to(config.PROJECT_ROOT)
    monkeypatch.setattr(config, "RAW_DATA_PATH", outside)
    monkeypatch.setattr(config, "PROCESSED_DATA_PATH", config.PROJECT_ROOT / "data" / "processed" / "없는.csv")
    missing = missing_files("requires_data")
    assert missing == ["hr.csv", "data/processed/없는.csv"]
    assert invalid_files("requires_data") == [], "없는 경로는 '잘못된 파일'이 아니라 '없음'이다."
    message = requirement_message("requires_data", missing)
    assert message == "requires_data: 필요한 파일이 없습니다: hr.csv, data/processed/없는.csv"
    assert str(outside.parent) not in message and str(config.PROJECT_ROOT) not in message


def test_directory_instead_of_file_is_invalid_not_missing(monkeypatch, tmp_path):
    # 파일 자리에 디렉터리가 있으면 '없음'(skip)이 아니라 '잘못된 구성'(항상 fail)으로 구분한다.
    folder = tmp_path / "best_rf_optuna.pkl"
    folder.mkdir()
    monkeypatch.setattr(config, "MODEL_PATH", folder)
    assert missing_files("requires_model") == []
    invalid = invalid_files("requires_model")
    # 임시 폴더 위치(프로젝트 안/밖)에 따라 상대 경로 또는 파일 이름으로 표시되며, 절대 경로는 아니다.
    assert invalid == [display_path(folder)]
    assert invalid[0].endswith("best_rf_optuna.pkl") and not Path(invalid[0]).is_absolute()
    assert str(tmp_path) not in invalid[0]


def test_display_path():
    assert display_path(config.RAW_DATA_PATH) == "data/raw/hr.csv"
    assert display_path(config.MODEL_PATH) == "models/best_rf_optuna.pkl"


def test_fixture_users_are_marked(request):
    # 데이터·모델 fixture를 쓰는 모든 테스트에 해당 marker가 붙었는지 수집된 전체 테스트에서 확인한다.
    unmarked = [
        (item.nodeid, marker)
        for item in request.session.items
        for fixture in getattr(item, "fixturenames", ())
        for marker in FIXTURE_MARKERS.get(fixture, ())
        if item.get_closest_marker(marker) is None
    ]
    assert not unmarked


def test_this_module_needs_no_data(request):
    # 아래 확인용 테스트 하나를 빼면, 이 파일의 테스트는 데이터 없이 실행된다.
    for item in request.session.items:
        if item.path == request.node.path and item.name != "test_marked_test_runs_when_data_exists":
            assert item.get_closest_marker("requires_data") is None, item.nodeid
            assert item.get_closest_marker("requires_model") is None, item.nodeid


@pytest.mark.requires_data
def test_marked_test_runs_when_data_exists():
    # 데이터가 있는 환경에서는 건너뛰지 않고 실행된다(0 skipped 확인용).
    assert config.RAW_DATA_PATH.is_file() and config.PROCESSED_DATA_PATH.is_file()
