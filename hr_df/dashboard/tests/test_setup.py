"""실제 프로세스로 경로와 점검 스크립트를 검사한다."""

import os
import shutil
import subprocess
import sys
from importlib import import_module

import pytest

from core import config


def _run_check(root, cwd):
    return subprocess.run(
        [sys.executable, str(root / "dashboard" / "scripts" / "check_setup.py")],
        cwd=cwd,
        capture_output=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        timeout=180,
        check=False,
    )


@pytest.fixture
def relocated_project(tmp_path):
    root = tmp_path / "한글 경로 (테스트)" / "hr df"
    ignore = shutil.ignore_patterns("__pycache__")
    for directory in ("data", "models", "dashboard"):
        # 모델은 저장소에 포함하지 않으므로 새로 clone한 환경에는 models 폴더가 없을 수 있다.
        if (config.PROJECT_ROOT / directory).exists():
            shutil.copytree(config.PROJECT_ROOT / directory, root / directory, ignore=ignore)
    shutil.copy(config.PROJECT_ROOT / "requirements.txt", root)
    return root


@pytest.mark.requires_data
@pytest.mark.requires_model
@pytest.mark.parametrize("cwd", [".", "notebooks", "dashboard", ".."])
def test_works_from_any_working_directory(cwd):
    result = _run_check(config.PROJECT_ROOT, config.PROJECT_ROOT / cwd)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.requires_data
@pytest.mark.requires_model
def test_works_in_path_with_korean_and_spaces(relocated_project, tmp_path):
    result = _run_check(relocated_project, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.requires_data
@pytest.mark.parametrize("missing", ["data/raw/hr.csv", "data/processed/hr_preprocessed.csv"])
def test_missing_file_fails_without_traceback(relocated_project, tmp_path, missing):
    # 데이터는 필수 항목이므로 없으면 FAIL이다.
    (relocated_project / missing).unlink()
    result = _run_check(relocated_project, tmp_path)
    assert result.returncode == 1
    assert "[FAIL]" in result.stdout
    assert "RESULT: PASS" not in result.stdout
    assert "Traceback" not in result.stderr


@pytest.mark.requires_data
@pytest.mark.requires_model
def test_model_present_reports_ok(relocated_project, tmp_path):
    result = _run_check(relocated_project, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "[OK] 모델" in result.stdout and "[WARN]" not in result.stdout
    assert result.stdout.strip().splitlines()[-1] == "RESULT: PASS"


@pytest.mark.requires_data
def test_missing_model_is_warning_not_failure(relocated_project, tmp_path):
    # 모델은 저장소에 포함하지 않는 선택 항목이다(Machine Learning 화면 전용).
    (relocated_project / "models" / "best_rf_optuna.pkl").unlink(missing_ok=True)
    result = _run_check(relocated_project, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "[FAIL]" not in result.stdout
    assert "[WARN] 모델: 모델 파일을 찾을 수 없습니다" in result.stdout
    assert "Machine Learning 화면은 사용할 수 없습니다" in result.stdout
    assert "[OK] 데이터" in result.stdout
    assert result.stdout.strip().splitlines()[-1] == "RESULT: PASS"
    assert "Traceback" not in result.stderr


@pytest.mark.requires_data
def test_tampered_model_is_warning_not_failure(relocated_project, tmp_path):
    # 손상되었거나 해시가 다른 모델은 로드하지 않고 경고한다(Machine Learning 화면 사용 불가).
    path = relocated_project / "models" / "best_rf_optuna.pkl"
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(b"not a verified model")
    result = _run_check(relocated_project, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "[WARN] 모델: 모델 파일이 검증된 버전과 다릅니다" in result.stdout
    assert "Machine Learning 화면은 사용할 수 없습니다" in result.stdout
    assert result.stdout.strip().splitlines()[-1] == "RESULT: PASS"
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("package", ["streamlit", "plotly", "shap"])
def test_dashboard_dependency_imports(package):
    import_module(package)
