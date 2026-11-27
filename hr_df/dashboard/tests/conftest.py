"""테스트 공통 fixture와 기존 파일 보호.

데이터·모델 파일은 공개 저장소에 포함하지 않을 수 있으므로, 이 파일이 필요한 테스트를 구분한다.

- ``requires_data``: 원본·전처리 CSV가 필요한 테스트
- ``requires_model``: 저장된 모델 파일이 필요한 테스트

경로가 **아예 없을 때만** 해당 테스트를 건너뛴다. 다음 경우는 건너뛰지 않고 실패한다.

- 경로에 파일 대신 디렉터리 등이 있을 때: 데이터가 없는 것이 아니라 잘못 구성된 환경이다.
- 파일이 있지만 손상되었거나 검증에 실패할 때: fixture나 테스트가 실패로 드러낸다.
- ``--require-data``(엄격 모드)를 주었는데 파일이 없을 때.
"""

import hashlib
import os
from pathlib import Path

import pytest

from core import analytics, config, data, modeling

PROTECTED_DIRECTORIES = ("data", "models", "notebooks", "reports")

# 표시 이름 -> 필요한 파일. 경로는 실행 시점에 config에서 읽는다(테스트에서 바꿀 수 있도록).
REQUIREMENTS = {
    "requires_data": ("RAW_DATA_PATH", "PROCESSED_DATA_PATH"),
    "requires_model": ("MODEL_PATH",),
}
# 이 fixture를 쓰는 테스트에는 marker를 자동으로 붙인다.
FIXTURE_MARKERS = {
    "raw_df": ("requires_data",),
    "processed_df": ("requires_data",),
    "analysis_df": ("requires_data",),
    "split": ("requires_data",),
    "model": ("requires_model",),
}


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--require-data",
        action="store_true",
        default=False,
        help="데이터·모델 파일이 없으면 테스트를 건너뛰지 않고 실패로 처리한다.",
    )


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    # 테스트 임시 파일도 프로젝트 내부(Git 제외)에 둔다.
    # basetemp는 매번 폴더 전체를 지워 사용 중이면 실패하므로, 실행별 폴더를 만드는 temproot를 쓴다.
    temp_root = config.rootpath / ".pytest_tmp"
    temp_root.mkdir(exist_ok=True)
    os.environ.setdefault("PYTEST_DEBUG_TEMPROOT", str(temp_root))
    config.addinivalue_line("markers", "requires_data: 원본·전처리 CSV(data/)가 있어야 실행되는 테스트")
    config.addinivalue_line("markers", "requires_model: 저장된 모델(models/)이 있어야 실행되는 테스트")


def display_path(path: Path) -> str:
    """보고용 경로. 프로젝트 안이면 상대 경로, 밖이면 파일 이름만 쓴다(절대 경로를 출력하지 않음)."""
    try:
        return path.resolve().relative_to(config.PROJECT_ROOT).as_posix()
    except ValueError:
        return path.name


def _required_paths(marker: str) -> list[Path]:
    return [getattr(config, name) for name in REQUIREMENTS[marker]]


def missing_files(marker: str) -> list[str]:
    """marker에 필요한 경로 중 아예 존재하지 않는 것. 이 경우에만 건너뛴다."""
    return [display_path(path) for path in _required_paths(marker) if not path.exists()]


def invalid_files(marker: str) -> list[str]:
    """경로는 있지만 일반 파일이 아닌 것(디렉터리 등). 건너뛰지 않고 항상 실패한다."""
    return [display_path(path) for path in _required_paths(marker) if path.exists() and not path.is_file()]


def requirement_message(marker: str, missing: list[str]) -> str:
    return f"{marker}: 필요한 파일이 없습니다: {', '.join(missing)}"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        for fixture in getattr(item, "fixturenames", ()):
            for marker in FIXTURE_MARKERS.get(fixture, ()):
                if item.get_closest_marker(marker) is None:
                    item.add_marker(marker)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    # fixture 준비보다 먼저 실행되므로, 파일이 없을 때 fixture 오류 대신 명확한 사유가 남는다.
    invalid = [
        f"{marker}: 파일이어야 할 경로가 파일이 아닙니다: {', '.join(paths)}"
        for marker in REQUIREMENTS
        if item.get_closest_marker(marker) is not None and (paths := invalid_files(marker))
    ]
    if invalid:
        pytest.fail("; ".join(invalid), pytrace=False)
    reasons = [
        requirement_message(marker, missing)
        for marker in REQUIREMENTS
        if item.get_closest_marker(marker) is not None and (missing := missing_files(marker))
    ]
    if not reasons:
        return
    if item.config.getoption("--require-data"):
        pytest.fail("엄격 모드(--require-data): " + "; ".join(reasons), pytrace=False)
    pytest.skip("; ".join(reasons))


def _protected_hashes() -> dict[str, str]:
    return {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for directory in PROTECTED_DIRECTORIES
        for path in (config.PROJECT_ROOT / directory).rglob("*")
        if path.is_file()
    }


@pytest.fixture(scope="session", autouse=True)
def protected_files_stay_unchanged():
    before = _protected_hashes()
    yield
    assert _protected_hashes() == before, "테스트 중 보호 대상 파일이 변경되었습니다."


@pytest.fixture(scope="session")
def raw_df():
    return data.load_raw_data()


@pytest.fixture(scope="session")
def processed_df():
    return data.load_verified_data()


@pytest.fixture(scope="session")
def analysis_df(processed_df):
    return analytics.add_analysis_groups(processed_df)


@pytest.fixture(scope="session")
def model():
    return modeling.load_model()


@pytest.fixture(scope="session")
def split(processed_df):
    return modeling.split_dataset(processed_df)
