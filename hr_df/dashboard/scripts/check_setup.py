"""실행 환경, 데이터, 모델 점검. 실행: python dashboard/scripts/check_setup.py

환경·데이터 문제는 FAIL(종료 코드 1), 모델 문제는 WARN(종료 코드 0)이다.
"""

import sys
from importlib import metadata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def environment_problems(requirements: Path) -> list[str]:
    problems = []
    if sys.version_info[:2] != (3, 12):
        problems.append(f"Python 3.12가 필요합니다 (현재 {sys.version.split()[0]}).")
    if not requirements.is_file():
        return [*problems, f"파일을 찾을 수 없습니다: {requirements}"]

    for line in requirements.read_text(encoding="utf-8").splitlines():
        name, separator, expected = line.strip().partition("==")
        if not separator:
            continue
        try:
            installed = metadata.version(name)
        except metadata.PackageNotFoundError:
            installed = "미설치"
        if installed != expected:
            problems.append(f"{name}=={expected}가 필요합니다 (현재 {installed}).")
    return problems


def main() -> int:
    requirements = Path(__file__).resolve().parents[2] / "requirements.txt"
    if problems := environment_problems(requirements):
        for problem in problems:
            print(f"[FAIL] 환경: {problem}")
        return 1
    print(f"[OK] 환경: Python {sys.version.split()[0]}, 패키지 버전 일치")

    # 패키지가 없을 때도 위의 안내가 출력되도록 환경 점검 후에 import한다.
    from core import analytics, config, data, modeling
    from core.exceptions import DashboardError

    try:
        df = data.load_verified_data()
        print(f"[OK] 데이터: {df.shape[0]:,}행, {df.shape[1]}열, 원본과 일치")

        summary = analytics.summarize_attrition(analytics.add_analysis_groups(df))
        print(
            f"[OK] 집계: 직원 {summary.employee_count:,}명, "
            f"이직 {summary.attrition_count:,}명, 이직률 {summary.attrition_rate:.2f}%"
        )
    except DashboardError as error:
        print(f"[FAIL] {error}")
        return 1

    # 모델은 Machine Learning 화면에만 필요한 선택 항목이다(저장소에 포함하지 않음).
    # 없거나 검증에 실패하면 경고만 하고, 나머지 화면은 실행할 수 있으므로 PASS로 끝낸다.
    try:
        model = modeling.load_model()
        split = modeling.split_dataset(df)
        probabilities = model.predict_proba(split.X_test)
        print(
            f"[OK] 모델: 테스트 {len(probabilities)}건 예측, "
            f"random_state={config.SPLIT_RANDOM_STATE}"
        )
    except DashboardError as error:
        print(f"[WARN] 모델: {error}")
        print(
            "[WARN] Machine Learning 화면은 사용할 수 없습니다. "
            "Overview, Workforce Analysis, HR Insights는 실행할 수 있습니다. "
            "모델 준비 방법은 data/README.md를 참고하세요."
        )

    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
