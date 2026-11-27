"""02_data_preprocessing의 규칙을 메모리에서 재현한다. 파일은 저장하지 않는다."""

import pandas as pd

from core import config, schema


def tenure_group(years: pd.Series) -> pd.Series:
    return pd.cut(years, bins=config.TENURE_BINS, labels=config.TENURE_LABELS).astype(str)


def attrition_binary(attrition: pd.Series) -> pd.Series:
    return attrition.map({"Yes": 1, "No": 0})


def preprocess(raw: pd.DataFrame) -> pd.DataFrame:
    result = raw.drop(columns=list(schema.CONSTANT_VALUES))
    for column in schema.CATEGORIES:
        result[column] = result[column].str.strip()
    result[schema.TENURE_COLUMN] = tenure_group(result["YearsAtCompany"])
    result[schema.TARGET_BINARY] = attrition_binary(result[schema.TARGET])
    return result
