# assets/charts — 분석 그래프 출처와 라이선스

이 폴더의 PNG 8개는 Notebook에 저장된 그래프 출력을 바이트 그대로 추출한 것입니다. Notebook은 수정하거나 다시 실행하지 않았습니다.

| 파일 | 출처 Notebook | 만든 데이터 |
|---|---|---|
| `eda_attrition_by_age_group.png`, `eda_attrition_by_department_jobrole.png`, `eda_attrition_by_income_tenure.png`, `eda_attrition_by_overtime.png` | `notebooks/03_eda.ipynb` | 전처리 CSV |
| `ml_model_performance_comparison.png`, `ml_logistic_regression_confusion_matrix.png` | `notebooks/06_machine_learning.ipynb` | 전처리 CSV |
| `shap_top15_feature_importance.png`, `shap_summary_plot.png` | `notebooks/07_shap_analysis.ipynb` | 전처리 CSV |

## 데이터 출처와 라이선스

이 그래프들은 아래 데이터에서 만든 결과물(ODbL의 Produced Work)입니다.

> Contains information from the [IBM HR Analytics Employee Attrition & Performance](https://www.kaggle.com/datasets/pavansubhasht/ibm-hr-analytics-attrition-dataset) dataset (also published in [IBM/employee-attrition-aif360](https://github.com/IBM/employee-attrition-aif360)), which is made available here under the [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/). Individual contents are licensed under the [Database Contents License (DbCL) 1.0](https://opendatacommons.org/licenses/dbcl/1-0/).

- 그래프를 만든 전처리 CSV(`data/processed/hr_preprocessed.csv`)는 ODbL 1.0으로 이 저장소에 함께 공개합니다.
- 전처리 방법은 `notebooks/02_data_preprocessing.ipynb`와 `dashboard/core/preprocessing.py`에 있습니다.
- 저장소 코드에 적용되는 MIT License(`../../LICENSE`)는 이 그래프에 적용되지 않습니다.
- 데이터 라이선스 표기의 근거와 확인하지 못한 사항은 [data/README.md](../../data/README.md)와 [DATASET_REVIEW.md](../../DATASET_REVIEW.md)에 있습니다.
