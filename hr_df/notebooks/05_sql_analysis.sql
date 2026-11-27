-- =============================================================================
-- 05. SQL Analysis — HR Attrition
--
-- 엔진: SQLite 3 (Python 표준 라이브러리 sqlite3, 메모리 데이터베이스)
-- 입력: 테이블 hr = data/raw/hr.csv 원본 그대로(1,470행, 35열). 적재는 05_sql_analysis.ipynb가 한다.
-- 데이터 출처: IBM HR Analytics Employee Attrition & Performance(IBM 데이터 과학자가 만든 가상 데이터).
--   배포처(IBM/employee-attrition-aif360, Kaggle)에 ODbL 1.0(데이터베이스)·DbCL 1.0(내용)으로 표기되어 있다.
--   https://opendatacommons.org/licenses/odbl/1-0/  https://opendatacommons.org/licenses/dbcl/1-0/
--   원본·전처리 CSV는 이 저장소에서 위 라이선스로 공개한다(data/README.md). 데이터 표기의 근거와 미확인 사항은 DATASET_REVIEW.md.
--   이 파일의 SQL 쿼리에는 MIT License(LICENSE)가 적용되며, 쿼리 결과(데이터에서 만든 수치)에는 적용되지 않는다.
-- 규칙:
--   * 각 쿼리는 "-- name: <이름>" 줄로 시작하고 세미콜론으로 끝난다(Notebook과 테스트가 이 표시로 나눠 실행).
--   * 이직률(%) = 100 * 이직자 수(attrition_count, 분자) / 직원 수(employee_count, 분모).
--     분모가 0이면 NULLIF로 NULL을 돌려 오류 없이 처리한다. 소수점 둘째 자리로 반올림한다.
--   * 30명 미만 집단은 small_sample = 'Y'로 표시한다(대시보드와 같은 표시 기준이며 통계적 기준이 아님).
--   * 집계값만 반환한다. 직원별 행은 반환하지 않는다.
--   * 구간 정의는 기존 Notebook과 같다.
--       연령대(03·04번): [0,25) [25,35) [35,45) [45,55) [55,∞) — 왼쪽 경계 포함
--       근속 구간(02번 TenureGroup): 0-1, 2-3, 4-5, 6-10, Over 10 Years — 오른쪽 경계 포함
--       YearsInCurrentRole에는 기존 구간 정의가 없어 근속 구간과 같은 경계를 적용한다.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- Q1. 데이터 기본 점검
-- -----------------------------------------------------------------------------

-- name: q1a_row_count
SELECT COUNT(*) AS row_count
FROM hr;

-- name: q1b_columns
SELECT cid + 1 AS position, name AS column_name, type AS sqlite_type
FROM pragma_table_info('hr')
ORDER BY cid;

-- name: q1c_duplicate_employee_number
SELECT
    COUNT(*) AS row_count,
    COUNT(DISTINCT EmployeeNumber) AS distinct_employee_number,
    COUNT(*) - COUNT(DISTINCT EmployeeNumber) AS duplicate_count
FROM hr;

-- name: q1d_missing_values
SELECT 'EmployeeNumber' AS column_name, SUM(EmployeeNumber IS NULL) AS null_count, SUM(TRIM(CAST(EmployeeNumber AS TEXT)) = '') AS blank_count FROM hr
UNION ALL SELECT 'Age', SUM(Age IS NULL), SUM(TRIM(CAST(Age AS TEXT)) = '') FROM hr
UNION ALL SELECT 'Attrition', SUM(Attrition IS NULL), SUM(TRIM(Attrition) = '') FROM hr
UNION ALL SELECT 'Department', SUM(Department IS NULL), SUM(TRIM(Department) = '') FROM hr
UNION ALL SELECT 'Gender', SUM(Gender IS NULL), SUM(TRIM(Gender) = '') FROM hr
UNION ALL SELECT 'JobRole', SUM(JobRole IS NULL), SUM(TRIM(JobRole) = '') FROM hr
UNION ALL SELECT 'OverTime', SUM(OverTime IS NULL), SUM(TRIM(OverTime) = '') FROM hr
UNION ALL SELECT 'YearsAtCompany', SUM(YearsAtCompany IS NULL), SUM(TRIM(CAST(YearsAtCompany AS TEXT)) = '') FROM hr
UNION ALL SELECT 'YearsInCurrentRole', SUM(YearsInCurrentRole IS NULL), SUM(TRIM(CAST(YearsInCurrentRole AS TEXT)) = '') FROM hr;

-- name: q1e_attrition_values
SELECT Attrition, COUNT(*) AS employee_count
FROM hr
GROUP BY Attrition
ORDER BY Attrition;


-- -----------------------------------------------------------------------------
-- Q2. 전체 이직률
-- -----------------------------------------------------------------------------

-- name: q2_overall
SELECT
    COUNT(*) AS employee_count,
    SUM(Attrition = 'Yes') AS attrition_count,
    SUM(Attrition = 'No') AS retained_count,
    ROUND(100.0 * SUM(Attrition = 'Yes') / NULLIF(COUNT(*), 0), 2) AS attrition_rate
FROM hr;


-- -----------------------------------------------------------------------------
-- Q3. 부서별 이직률과 전체 평균 비교
-- -----------------------------------------------------------------------------

-- name: q3_department
WITH overall AS (
    SELECT 100.0 * SUM(Attrition = 'Yes') / NULLIF(COUNT(*), 0) AS rate FROM hr
),
grouped AS (
    SELECT
        Department,
        COUNT(*) AS employee_count,
        SUM(Attrition = 'Yes') AS attrition_count,
        100.0 * SUM(Attrition = 'Yes') / NULLIF(COUNT(*), 0) AS rate
    FROM hr
    GROUP BY Department
)
SELECT
    g.Department,
    g.employee_count,
    g.attrition_count,
    ROUND(g.rate, 2) AS attrition_rate,
    ROUND(o.rate, 2) AS overall_rate,
    ROUND(g.rate - o.rate, 2) AS diff_pp,
    CASE WHEN g.employee_count < 30 THEN 'Y' ELSE 'N' END AS small_sample
FROM grouped AS g CROSS JOIN overall AS o
ORDER BY g.rate DESC, g.employee_count DESC;


-- -----------------------------------------------------------------------------
-- Q4. 성별 이직률
-- -----------------------------------------------------------------------------

-- name: q4_gender
SELECT
    Gender,
    COUNT(*) AS employee_count,
    SUM(Attrition = 'Yes') AS attrition_count,
    ROUND(100.0 * SUM(Attrition = 'Yes') / NULLIF(COUNT(*), 0), 2) AS attrition_rate
FROM hr
GROUP BY Gender
ORDER BY attrition_rate DESC;


-- -----------------------------------------------------------------------------
-- Q5. 직무별 이직률(소표본 표시)
-- -----------------------------------------------------------------------------

-- name: q5_job_role
SELECT
    JobRole,
    COUNT(*) AS employee_count,
    SUM(Attrition = 'Yes') AS attrition_count,
    ROUND(100.0 * SUM(Attrition = 'Yes') / NULLIF(COUNT(*), 0), 2) AS attrition_rate,
    CASE WHEN COUNT(*) < 30 THEN 'Y' ELSE 'N' END AS small_sample
FROM hr
GROUP BY JobRole
ORDER BY 100.0 * SUM(Attrition = 'Yes') / NULLIF(COUNT(*), 0) DESC, COUNT(*) DESC;


-- -----------------------------------------------------------------------------
-- Q6. 초과근무 분석
-- -----------------------------------------------------------------------------

-- name: q6a_overtime
SELECT
    OverTime,
    COUNT(*) AS employee_count,
    SUM(Attrition = 'Yes') AS attrition_count,
    ROUND(100.0 * SUM(Attrition = 'Yes') / NULLIF(COUNT(*), 0), 2) AS attrition_rate
FROM hr
GROUP BY OverTime
ORDER BY OverTime DESC;

-- name: q6b_overtime_comparison
WITH rates AS (
    SELECT
        100.0 * SUM(OverTime = 'Yes' AND Attrition = 'Yes') / NULLIF(SUM(OverTime = 'Yes'), 0) AS rate_yes,
        100.0 * SUM(OverTime = 'No' AND Attrition = 'Yes') / NULLIF(SUM(OverTime = 'No'), 0) AS rate_no
    FROM hr
)
SELECT
    ROUND(rate_yes, 2) AS overtime_rate,
    ROUND(rate_no, 2) AS no_overtime_rate,
    ROUND(rate_yes - rate_no, 2) AS diff_pp,
    ROUND(rate_yes / NULLIF(rate_no, 0), 2) AS rate_ratio
FROM rates;


-- -----------------------------------------------------------------------------
-- Q7. 연령대별 이직률(03·04번 Notebook과 같은 구간)
-- -----------------------------------------------------------------------------

-- name: q7_age_group
WITH banded AS (
    SELECT
        CASE
            WHEN Age < 25 THEN 1
            WHEN Age < 35 THEN 2
            WHEN Age < 45 THEN 3
            WHEN Age < 55 THEN 4
            ELSE 5
        END AS band_order,
        Attrition
    FROM hr
)
SELECT
    CASE band_order
        WHEN 1 THEN 'Under 25' WHEN 2 THEN '25-34' WHEN 3 THEN '35-44' WHEN 4 THEN '45-54' ELSE '55+'
    END AS AgeGroup,
    COUNT(*) AS employee_count,
    SUM(Attrition = 'Yes') AS attrition_count,
    ROUND(100.0 * SUM(Attrition = 'Yes') / NULLIF(COUNT(*), 0), 2) AS attrition_rate,
    CASE WHEN COUNT(*) < 30 THEN 'Y' ELSE 'N' END AS small_sample
FROM banded
GROUP BY band_order
ORDER BY band_order;


-- -----------------------------------------------------------------------------
-- Q8. 근속기간별 이직률
-- -----------------------------------------------------------------------------

-- name: q8a_tenure_years_at_company
WITH banded AS (
    SELECT
        CASE
            WHEN YearsAtCompany <= 1 THEN 1
            WHEN YearsAtCompany <= 3 THEN 2
            WHEN YearsAtCompany <= 5 THEN 3
            WHEN YearsAtCompany <= 10 THEN 4
            ELSE 5
        END AS band_order,
        Attrition
    FROM hr
)
SELECT
    CASE band_order
        WHEN 1 THEN '0-1 Years' WHEN 2 THEN '2-3 Years' WHEN 3 THEN '4-5 Years' WHEN 4 THEN '6-10 Years' ELSE 'Over 10 Years'
    END AS TenureGroup,
    COUNT(*) AS employee_count,
    SUM(Attrition = 'Yes') AS attrition_count,
    ROUND(100.0 * SUM(Attrition = 'Yes') / NULLIF(COUNT(*), 0), 2) AS attrition_rate,
    CASE WHEN COUNT(*) < 30 THEN 'Y' ELSE 'N' END AS small_sample
FROM banded
GROUP BY band_order
ORDER BY band_order;

-- name: q8b_years_in_current_role
WITH banded AS (
    SELECT
        CASE
            WHEN YearsInCurrentRole <= 1 THEN 1
            WHEN YearsInCurrentRole <= 3 THEN 2
            WHEN YearsInCurrentRole <= 5 THEN 3
            WHEN YearsInCurrentRole <= 10 THEN 4
            ELSE 5
        END AS band_order,
        Attrition
    FROM hr
)
SELECT
    CASE band_order
        WHEN 1 THEN '0-1 Years' WHEN 2 THEN '2-3 Years' WHEN 3 THEN '4-5 Years' WHEN 4 THEN '6-10 Years' ELSE 'Over 10 Years'
    END AS RoleTenureGroup,
    COUNT(*) AS employee_count,
    SUM(Attrition = 'Yes') AS attrition_count,
    ROUND(100.0 * SUM(Attrition = 'Yes') / NULLIF(COUNT(*), 0), 2) AS attrition_rate,
    CASE WHEN COUNT(*) < 30 THEN 'Y' ELSE 'N' END AS small_sample
FROM banded
GROUP BY band_order
ORDER BY band_order;

-- name: q8c_tenure_mean_by_attrition
SELECT
    Attrition,
    COUNT(*) AS employee_count,
    ROUND(AVG(YearsAtCompany), 2) AS mean_years_at_company,
    ROUND(AVG(YearsInCurrentRole), 2) AS mean_years_in_current_role
FROM hr
GROUP BY Attrition
ORDER BY Attrition;


-- -----------------------------------------------------------------------------
-- Q9. 직무 × 초과근무 교차 분석
-- -----------------------------------------------------------------------------

-- name: q9_job_role_overtime
SELECT
    JobRole,
    OverTime,
    COUNT(*) AS employee_count,
    SUM(Attrition = 'Yes') AS attrition_count,
    ROUND(100.0 * SUM(Attrition = 'Yes') / NULLIF(COUNT(*), 0), 2) AS attrition_rate,
    CASE WHEN COUNT(*) < 30 THEN 'Y' ELSE 'N' END AS small_sample
FROM hr
GROUP BY JobRole, OverTime
ORDER BY JobRole, OverTime;
