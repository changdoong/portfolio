"""경로와 분석 규칙. 분석 규칙은 기존 Notebook과 동일하게 유지한다."""

import math
from pathlib import Path

# 실행 위치(cwd)와 무관하게 이 파일의 위치에서 경로를 계산한다.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_PATH = PROJECT_ROOT / "data" / "raw" / "hr.csv"
PROCESSED_DATA_PATH = PROJECT_ROOT / "data" / "processed" / "hr_preprocessed.csv"
MODEL_PATH = PROJECT_ROOT / "models" / "best_rf_optuna.pkl"

# 02_data_preprocessing
TENURE_BINS = (-1, 1, 3, 5, 10, math.inf)
TENURE_LABELS = ("0-1 Years", "2-3 Years", "4-5 Years", "6-10 Years", "Over 10 Years")

# 03_eda, 04_statistical_analysis (왼쪽 경계 포함)
AGE_BINS = (0, 25, 35, 45, 55, math.inf)
AGE_LABELS = ("Under 25", "25-34", "35-44", "45-54", "55+")

# 03_eda (전사 기준 사분위)
INCOME_LABELS = ("Q1 - Low", "Q2 - Middle Low", "Q3 - Middle High", "Q4 - High")

# 06_machine_learning
SPLIT_RANDOM_STATE = 2020158011
MODEL_RANDOM_STATE = 42
TEST_SIZE = 0.2

# joblib.load는 코드를 실행할 수 있으므로 검증된 파일만 로드한다.
MODEL_SHA256 = "1abf5042fd6d3df5a69f3b785b1a5390f083ec6cdbed4edb29fb1bd68e034854"
MODEL_SKLEARN_VERSION = "1.6.1"

# 대시보드의 표시 기준이며 통계적 유의성 기준이 아니다.
SMALL_SAMPLE_THRESHOLD = 30
