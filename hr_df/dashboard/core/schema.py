"""데이터 컬럼과 허용값의 단일 정의."""

from core.config import TENURE_LABELS

TARGET = "Attrition"
TARGET_BINARY = "AttritionBinary"
ID_COLUMN = "EmployeeNumber"
TENURE_COLUMN = "TenureGroup"

CONSTANT_VALUES = {"EmployeeCount": 1, "Over18": "Y", "StandardHours": 80}

CATEGORIES: dict[str, tuple[str, ...]] = {
    TARGET: ("No", "Yes"),
    "BusinessTravel": ("Non-Travel", "Travel_Frequently", "Travel_Rarely"),
    "Department": ("Human Resources", "Research & Development", "Sales"),
    "EducationField": (
        "Human Resources",
        "Life Sciences",
        "Marketing",
        "Medical",
        "Other",
        "Technical Degree",
    ),
    "Gender": ("Female", "Male"),
    "JobRole": (
        "Healthcare Representative",
        "Human Resources",
        "Laboratory Technician",
        "Manager",
        "Manufacturing Director",
        "Research Director",
        "Research Scientist",
        "Sales Executive",
        "Sales Representative",
    ),
    "MaritalStatus": ("Divorced", "Married", "Single"),
    "OverTime": ("No", "Yes"),
}

# (최솟값, 최댓값). None은 상한 없음.
# 관측 범위가 아니라 값의 의미에 따른 범위이므로 IQR 이상치는 오류로 보지 않는다.
INTEGER_RANGES: dict[str, tuple[int, int | None]] = {
    "Age": (14, 100),
    "DailyRate": (0, None),
    "DistanceFromHome": (0, None),
    "Education": (1, 5),
    ID_COLUMN: (1, None),
    "EnvironmentSatisfaction": (1, 4),
    "HourlyRate": (0, None),
    "JobInvolvement": (1, 4),
    "JobLevel": (1, 5),
    "JobSatisfaction": (1, 4),
    "MonthlyIncome": (0, None),
    "MonthlyRate": (0, None),
    "NumCompaniesWorked": (0, None),
    "PercentSalaryHike": (0, 100),
    "PerformanceRating": (1, 4),
    "RelationshipSatisfaction": (1, 4),
    "StockOptionLevel": (0, 3),
    "TotalWorkingYears": (0, None),
    "TrainingTimesLastYear": (0, None),
    "WorkLifeBalance": (1, 4),
    "YearsAtCompany": (0, None),
    "YearsInCurrentRole": (0, None),
    "YearsSinceLastPromotion": (0, None),
    "YearsWithCurrManager": (0, None),
}

# 왼쪽 값은 오른쪽 값보다 클 수 없다.
NOT_GREATER_THAN = (
    ("TotalWorkingYears", "Age"),
    ("YearsAtCompany", "TotalWorkingYears"),
    ("YearsInCurrentRole", "YearsAtCompany"),
    ("YearsSinceLastPromotion", "YearsAtCompany"),
    ("YearsWithCurrManager", "YearsAtCompany"),
)

RAW_COLUMNS = frozenset([*CATEGORIES, *INTEGER_RANGES, *CONSTANT_VALUES])
PROCESSED_CATEGORIES = {**CATEGORIES, TENURE_COLUMN: TENURE_LABELS}
PROCESSED_INTEGER_RANGES = {**INTEGER_RANGES, TARGET_BINARY: (0, 1)}
PROCESSED_COLUMNS = frozenset([*PROCESSED_CATEGORIES, *PROCESSED_INTEGER_RANGES])

NON_FEATURE_COLUMNS = (TARGET, TARGET_BINARY, ID_COLUMN)
