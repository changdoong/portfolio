"""화면 공통 제목과 안내."""

import logging
import re
from html import escape

import streamlit as st

from core.exceptions import DashboardError, DataValidationError, ModelLoadError

logger = logging.getLogger(__name__)

# 사용자 화면에 서버의 절대 경로가 보이지 않도록, 메시지 속 절대 경로를 파일 이름만 남기고 바꾼다.
# 경로 구성 문자: 경로 구분자와 Windows에서 파일 이름에 쓸 수 없는 문자를 뺀 모든 문자(공백 포함).
_PART = r"[^\\/\r\n:*?\"<>|]"
_WINDOWS_PATH = re.compile(
    # 드라이브 경로(C:\, C:/)와 UNC 경로(\\server\share). 앞 글자가 영문이면 URL(https:// 등)로 보고 제외한다.
    rf"(?:(?<![A-Za-z])[A-Za-z]:[\\/]+|\\\\(?={_PART}))(?:{_PART}+[\\/]+)*(?P<name>{_PART}*)"
)
_POSIX_PATH = re.compile(
    # /home/user/..., ~/... 형태. 1/3처럼 앞에 글자나 숫자가 붙은 슬래시는 경로로 보지 않는다.
    rf"(?<![\w.~:/\\])~?/(?:{_PART}+/+)+(?P<name>{_PART}*)"
)
DATA_HINT = (
    "해결 방법: 프로젝트의 data/raw/hr.csv와 data/processed/hr_preprocessed.csv가 있고 "
    "읽을 수 있는 CSV인지 확인하세요. 데이터 준비 방법은 README를 참고하세요. "
    "자세한 경로와 원인은 서버 로그에 기록됩니다."
)
VALIDATION_HINT = (
    "해결 방법: 원본(data/raw/hr.csv)과 전처리 데이터(data/processed/hr_preprocessed.csv)가 "
    "프로젝트와 같은 버전인지 확인하세요. 자세한 원인은 서버 로그에 기록됩니다."
)

MODEL_HINT = (
    "해결 방법: 프로젝트의 models/best_rf_optuna.pkl이 06번 Notebook에서 저장한 검증된 파일인지, "
    "프로젝트의 .venv(scikit-learn 1.6.1)로 실행했는지 확인하세요. 모델 준비 방법은 README를 참고하세요. "
    "자세한 경로와 원인은 서버 로그에 기록됩니다."
)


def public_message(text: str) -> str:
    """사용자에게 보여 줄 오류 문장. 절대 경로는 파일 이름만 남기고, 그 밖의 내용은 그대로 둔다."""
    text = _WINDOWS_PATH.sub(lambda m: m.group("name"), text)
    return _POSIX_PATH.sub(lambda m: m.group("name"), text)


def page_header(title: str, description: str) -> None:
    st.html(
        f'<header class="hr-page-header"><h1>{escape(title)}</h1>'
        f"<p>{escape(description)}</p></header>"
    )


def section_header(title: str, description: str, *, level: int = 2) -> None:
    st.html(
        f'<div class="hr-section"><h{level}>{escape(title)}</h{level}>'
        f"<p>{escape(description)}</p></div>"
    )


def footnote(text: str) -> None:
    st.html(f'<p class="hr-footnote">{escape(text)}</p>')


def load_error(error: DashboardError) -> None:
    # 개발자용 상세 정보(절대 경로 포함)는 서버 로그에만 남기고, 화면에는 경로를 뺀 문장을 보인다.
    if isinstance(error, ModelLoadError):
        logger.error("모델을 불러오지 못했습니다: %s", error)
        st.error("모델을 불러오지 못해 모델 지표를 표시하지 않았습니다.", icon=":material/error:")
        hint = MODEL_HINT
    else:
        logger.error("데이터를 불러오지 못했습니다: %s", error)
        st.error("데이터를 불러오지 못해 지표를 표시하지 않았습니다.", icon=":material/error:")
        hint = VALIDATION_HINT if isinstance(error, DataValidationError) else DATA_HINT
    # 경로 이외의 특수문자가 Markdown으로 해석되지 않도록 코드 블록으로 표시한다.
    st.code(public_message(str(error)), language=None, wrap_lines=True)
    footnote(hint)
