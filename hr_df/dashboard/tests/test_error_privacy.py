"""데이터 오류 화면에 서버의 절대 경로가 보이지 않는지 검사한다(Stage 4C.1)."""

import logging

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from components import layout
from core import config, data
from core.exceptions import DataLoadError, DataValidationError

ABSOLUTE = {
    "windows_backslash": (r"데이터 파일을 찾을 수 없습니다: C:\Users\someone\proj\data\raw\hr.csv", "hr.csv"),
    "windows_slash": ("파일 없음: C:/data/hr.csv", "hr.csv"),
    "windows_spaces": (r"데이터 파일을 읽을 수 없습니다: D:\Program Files\HR Data\hr.csv (C error)", "hr.csv (C error)"),
    "windows_repr": (r"[Errno 2] No such file or directory: 'C:\\Users\\someone\\data\\hr.csv'", "hr.csv'"),
    "unc": (r"공유 폴더: \\fileserver\share\hr\hr.csv", "hr.csv"),
    "posix": ("데이터 파일을 찾을 수 없습니다: /home/someone/project/data/raw/hr.csv", "hr.csv"),
    "posix_spaces": ("읽을 수 없습니다: /srv/My Data/hr.csv (bad)", "hr.csv (bad)"),
    "posix_home": ("경로: ~/work/hr/hr.csv", "hr.csv"),
}
LEAKS = ("C:", "D:", "Users", "someone", "fileserver", "/home", "/srv", "~/", "Program Files", "My Data")


@pytest.fixture(autouse=True)
def clear_cache():
    st.cache_data.clear()
    yield
    st.cache_data.clear()


@pytest.mark.parametrize("message,kept", ABSOLUTE.values(), ids=ABSOLUTE.keys())
def test_absolute_paths_become_file_names(message, kept):
    shown = layout.public_message(message)
    assert shown.endswith(kept), shown
    for leak in LEAKS:
        assert leak not in shown, (leak, shown)


@pytest.mark.parametrize(
    "message",
    ["data/raw/hr.csv", "필터 부서 1/3 · 성별 2/2", "결측치 1건", "https://example.com/a/b.csv", "열 개수가 다릅니다"],
)
def test_text_without_absolute_path_is_unchanged(message):
    assert layout.public_message(message) == message


def test_real_loader_message_hides_its_path(tmp_path):
    missing = tmp_path / "숨길 폴더" / "hr.csv"
    with pytest.raises(DataLoadError) as raised:
        data.load_raw_data(missing)
    assert str(tmp_path) in str(raised.value), "로더의 원래 메시지에는 경로가 있다(core는 바꾸지 않음)."
    shown = layout.public_message(str(raised.value))
    assert shown == "데이터 파일을 찾을 수 없습니다: hr.csv"
    assert str(tmp_path) not in shown and "숨길 폴더" not in shown


def _overview():
    from views import overview

    overview.render()


def _workforce():
    from views import workforce

    workforce.render()


def _texts(app: AppTest) -> str:
    parts = [e.value for e in app.error] + [c.value for c in app.code]
    parts += [item.proto.body for item in app.main.get("html")]
    return "\n".join(parts)


@pytest.mark.parametrize("page", [_overview, _workforce], ids=["overview", "workforce"])
@pytest.mark.parametrize(
    "error",
    [
        DataLoadError(f"데이터 파일을 찾을 수 없습니다: {config.RAW_DATA_PATH}"),
        DataLoadError(r"데이터 파일을 찾을 수 없습니다: C:\외부 서버\공유\hr.csv"),
        DataLoadError("데이터 파일을 찾을 수 없습니다: /srv/hr-app/data/raw/hr.csv"),
    ],
    ids=["project_path", "external_windows", "external_posix"],
)
def test_error_screen_shows_no_absolute_path(monkeypatch, caplog, page, error):
    def fail():
        raise error

    monkeypatch.setattr(data, "load_analysis_data", fail)
    with caplog.at_level(logging.ERROR, logger=layout.__name__):
        app = AppTest.from_function(page, default_timeout=30).run()
    shown = _texts(app)
    assert not app.exception
    assert len(app.error) == 1
    assert "데이터 파일을 찾을 수 없습니다: hr.csv" in app.code[0].value
    assert layout.DATA_HINT in shown
    for leak in (str(config.PROJECT_ROOT), "외부 서버", "/srv/"):
        assert leak not in shown, leak
    assert "1,470" not in shown, "오류 화면에는 지표를 표시하지 않는다."
    # 개발자용 상세 정보는 서버 로그에 원문 그대로 남는다.
    assert str(error) in caplog.text


def test_validation_error_shows_validation_hint(monkeypatch):
    def fail():
        raise DataValidationError(["결측치 1건"])

    monkeypatch.setattr(data, "load_analysis_data", fail)
    app = AppTest.from_function(_overview, default_timeout=30).run()
    assert app.code[0].value == str(DataValidationError(["결측치 1건"]))
    assert layout.VALIDATION_HINT in _texts(app)
