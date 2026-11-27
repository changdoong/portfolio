# 데이터셋 라이선스 검토

이 저장소에 포함된 데이터와 모델을 공개 배포해도 되는지, 그리고 그 조건이 무엇인지 확인한 기록입니다.
처음 확인한 날짜는 2026-11-24이고, 같은 날 라이선스 원문으로 다시 대조했습니다(Stage 4B).
**법률 자문이 아니라 공개 자료를 대조한 결과입니다.** 해석이 필요한 항목은 **미확정**, 확인하지 못한 항목은 **미확인**으로 표시했습니다.

## 1. 결론

| 항목 | 결과 |
|---|---|
| 원본 데이터 | IBM 데이터 과학자가 만든 **가상(fictional) 직원 데이터**. 실제 개인정보가 아닙니다. |
| 라이선스 | 데이터베이스는 **ODbL 1.0**, 내용(Contents)은 **DbCL 1.0**. Kaggle 표기와 IBM 공식 저장소 표기가 일치합니다. |
| 사용 중인 CSV | IBM 공식 저장소의 `data/emp_attrition.csv`와 **바이트 단위로 동일** |
| 원본 CSV 재배포 | ODbL 4.2 고지(라이선스, URI, 기존 고지 유지)를 지키면 가능 |
| 전처리 CSV | ODbL의 파생 데이터베이스(Derivative Database). 공개하면 **ODbL로 배포**해야 함(4.4) |
| 화면·그림·보고서 | 산출물(Produced Work). 공개하면 **출처·라이선스 고지** 필요(4.3) |
| 전처리 데이터에서 만든 산출물 | 산출물을 공개하면 그 파생 데이터베이스도 공개 사용한 것으로 봅니다(4.4c). **파생 데이터베이스 전체나 변경 방법을 제공**해야 합니다(4.6). |
| 모델 파일 | 파생 데이터베이스인지 산출물인지, 또는 둘 다 아닌지 **미확정(법률 판단 필요)** |
| 코드 라이선스 | **MIT License**(`LICENSE`, 2026-11-27 결정). 직접 작성한 코드에만 적용되며 데이터·모델·데이터 산출물에는 적용되지 않습니다. |

## 2. 출처

| 출처 | 확인 내용 |
|---|---|
| IBM 공식 저장소 [IBM/employee-attrition-aif360](https://github.com/IBM/employee-attrition-aif360) | 데이터 파일 `data/emp_attrition.csv`. README의 “Dataset License Details” 표에 Database License는 ODbL, Content License는 DbCL로 적혀 있고 출처 링크는 Kaggle입니다. 저장소는 보관(archived) 상태이고 마지막 push는 2019-06-19입니다. 저장소 자체의 `LICENSE`(Apache-2.0)는 코드 패턴에 대한 것이며, README는 데이터 라이선스를 따로 적고 있습니다. |
| Kaggle [pavansubhasht/ibm-hr-analytics-attrition-dataset](https://www.kaggle.com/datasets/pavansubhasht/ibm-hr-analytics-attrition-dataset) | 제목 “IBM HR Analytics Employee Attrition & Performance”, 업로더 pavansubhash, 버전 1(2017-03-31). 라이선스 표기는 “Database: Open Database, Contents: Database Contents”. 설명에 “This is a fictional data set created by IBM data scientists.”라고 적혀 있습니다. 파일명 `WA_Fn-UseC_-HR-Employee-Attrition.csv`, 전체 크기 227,977바이트, 컬럼 35개. |

Kaggle 정보는 Kaggle 공개 API(`/api/v1/datasets/view/...`)와 Croissant 메타데이터에서 읽었습니다. 웹 페이지 화면은 직접 보지 않았습니다.

## 3. 사용 중인 파일과의 동일성

| 비교 | 결과 |
|---|---|
| `data/raw/hr.csv` 크기 | 227,977바이트 |
| `data/raw/hr.csv` SHA-256 | `a5c31e38bd7fafc9bc333884eb181b06b41b8e5e488e8f7ccb27199fb3be7659` |
| IBM `data/emp_attrition.csv` | 크기와 SHA-256이 같음 → **바이트 단위로 동일** |
| 행과 열 | 1,470행, 35열 (헤더 제외. IBM 파일을 직접 파싱해 확인) |
| Kaggle 파일 | 크기 227,977바이트와 컬럼 35개가 일치합니다. 파일 다운로드에는 로그인이 필요해 **해시는 미확인**입니다. |

참고: portfolio GitHub 저장소의 Git 객체 크기는 226,506바이트입니다. 줄바꿈 변환(CRLF/LF) 차이로 보이며, 확인하지는 않았습니다.

## 4. 라이선스 원문 대조

원문은 [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/)과 [DbCL 1.0](https://opendatacommons.org/licenses/dbcl/1-0/)입니다.

### 4.1 두 라이선스의 관계

| 확인 항목 | 원문 근거 | 결과 |
|---|---|---|
| DbCL은 개별 내용(Contents)에 대한 저작권 이용허락을 준다 | DbCL 2.1: 내용 안의 저작권 대상에 대해 전 세계적·무상·비독점·영구·취소 불가의 저작권 이용허락. 상업적 이용과 재허락 포함 | 확인 |
| DbCL은 ODbL 준수를 요구한다 | DbCL 2.2: “You must comply with the ODbL.” | 확인 |
| DbCL은 데이터베이스 권리 자체를 다루지 않는다 | DbCL 2.3: Database Rights, 데이터베이스 저작권, 데이터베이스의 일부로서 내용에 대한 계약은 다루지 않으며 ODbL을 보라고 함 | 확인 |
| ODbL은 개별 내용의 권리를 다루지 않는다 | ODbL 2.4: Database Rights와 계약 외에 개별 내용의 권리는 다루지 않음 | 확인. 그래서 내용은 DbCL로 따로 허락됨 |
| 용어 정의 | DbCL 1.0은 ODbL 1.0의 정의를 그대로 가져옴 | 확인 |

정리하면 다음과 같습니다.
- **데이터베이스로서의 권리:** ODbL이 다룹니다.
- **개별 값(내용)의 저작권:** DbCL이 허락합니다.
- **DbCL의 조건:** ODbL을 지키는 것입니다.

따라서 이 데이터를 공개할 때의 의무는 사실상 ODbL 조항에서 나옵니다.

### 4.2 ODbL 의무 조항

| 조항 | 원문 요약 | 이 저장소에서 할 일 |
|---|---|---|
| 4.2 Notices | 데이터베이스나 파생 데이터베이스를 공개 전달(Publicly Convey)하면 (a) ODbL(또는 4.4가 허용하는 라이선스)로만 배포하고, (b) 라이선스 사본이나 URI를 데이터와 관련 문서에 포함하고, (c) 기존 저작권·Database Right·라이선스 고지를 유지하고, (d) 파일 구조상 넣을 수 없으면 사용자가 볼 만한 위치(예: 해당 폴더)에 고지 | `data/` 폴더에 고지 파일, README에 출처·라이선스 URI |
| 4.3 Notice for using output | 산출물을 공개 사용하면 내용이 데이터베이스에서 왔고 ODbL로 이용 가능하다는 고지 필요. 원문 예시 문안: “Contains information from DATABASE NAME, which is made available here under the Open Database License (ODbL).” (데이터베이스 이름과 라이선스에 링크) | README, 보고서, 대시보드 화면, 캡처 설명에 고지 |
| 4.4 Share alike | (a) 공개 사용하는 파생 데이터베이스는 ODbL, 이후 버전, 또는 호환 라이선스로만. (b) 내용 전체나 상당 부분을 새 데이터베이스로 추출하면 파생 데이터베이스. (c) 파생 데이터베이스로 만든 산출물을 공개 사용하면 그 파생 데이터베이스도 공개 사용한 것으로 봄 | 전처리 CSV를 공개하면 ODbL. 공개하지 않더라도 그것으로 만든 화면·그림을 공개하면 4.4c와 4.6이 적용될 수 있음 |
| 4.6 Access to Derivative Databases | 파생 데이터베이스나 그 산출물을 공개 사용하면 받는 사람에게 기계 판독 가능한 형태로 (a) 파생 데이터베이스 전체, 또는 (b) 원본과의 모든 차이를 만드는 변경 내용이나 변경 방법(예: 알고리즘)을 제공. 인터넷 배포라면 무료 | (a) 전처리 CSV를 공개하거나, (b) 변경 방법인 `notebooks/02_data_preprocessing.ipynb`와 `dashboard/core/preprocessing.py`, `dashboard/core/analytics.py`(구간 생성)를 공개 |

**미확정(법률 판단 필요):**
- 대시보드가 실행 중에 만드는 구간 열(연령대, 소득 사분위)이 파생 데이터베이스에 해당하는지
- 4.6(b)의 “변경 방법”으로 위 코드 공개가 충분한지
- 모델 파일의 성격

## 5. 파일별 판단

| 파일 | 성격 | 공개 조건 | 현재 상태 |
|---|---|---|---|
| `data/raw/hr.csv` | 원본 데이터베이스 | ODbL 4.2 고지 | **공개 유지**(Git 추적). ODbL·DbCL 고지는 `data/README.md`와 `README.md`에 둠 |
| `data/processed/hr_preprocessed.csv` | 파생 데이터베이스 | ODbL 배포(4.4), 4.2 고지 | **공개 유지**(Git 추적), ODbL 1.0으로 배포한다고 명시. 전처리 방법(4.6): 02번 Notebook, `dashboard/core/preprocessing.py` |
| `models/best_rf_optuna.pkl` | 학습된 모델 | **미확정**. 최소한 출처·라이선스 고지 권장 | **Git 추적 해제**(로컬 파일만 유지). 이전 커밋에는 남아 있음 |
| `notebooks/`, `reports/`, `docs/captures/` | 산출물(그림, 글, 표) | 4.3 고지. 전처리 데이터에서 만든 것이면 4.4c·4.6도 검토 | 고지 추가 필요 |
| `dashboard/` 코드 | 코드 | 데이터 라이선스와 별개. 4.6(b)의 변경 방법 역할도 함 | MIT License 적용 |

“현재 상태” 열은 2026-11-27에 확정한 공개 방침입니다.
- `.gitignore`에는 모델 파일의 제외 규칙만 있습니다(추적을 해제한 모델이 다시 추가되지 않게 함). 두 CSV는 공개 대상이라 제외하지 않습니다.
- 데이터 라이선스 표기는 두 배포처를 따른 것이며, IBM이 처음 배포한 곳의 이용 조건은 확인하지 못했습니다.
- 코드에는 MIT License(`LICENSE`)가 적용되며, 데이터·모델·데이터에서 만든 산출물에는 적용되지 않습니다.

데이터와 모델을 공개하지 않으면 받는 사람은 IBM 저장소나 Kaggle에서 원본을 받아야 합니다. 이때 전처리 CSV와 모델은 02·06번 Notebook으로 다시 만들어야 하고, 모델 해시 검사(`core/config.py`)를 통과하지 못할 수 있습니다(재학습 결과가 같다는 보장이 없음).

## 6. 공개 시 출처 표시 문안(초안, 미확정)

ODbL 4.3의 예시 문안을 바탕으로 한 초안입니다.

> This project contains information from the [IBM HR Analytics Employee Attrition & Performance](https://www.kaggle.com/datasets/pavansubhasht/ibm-hr-analytics-attrition-dataset) dataset (a fictional dataset created by IBM data scientists; also published in [IBM/employee-attrition-aif360](https://github.com/IBM/employee-attrition-aif360)), which is made available under the [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/). Individual contents are licensed under the [Database Contents License (DbCL) 1.0](https://opendatacommons.org/licenses/dbcl/1-0/).
> `data/processed/hr_preprocessed.csv` is a derivative database of the original and, if distributed, is made available under ODbL 1.0. The preprocessing method is in `notebooks/02_data_preprocessing.ipynb` and `dashboard/core/preprocessing.py`.

## 7. 추가로 확인할 사항

- [ ] Kaggle 파일과의 해시 비교(로그인 후 다운로드)
- [ ] Kaggle 업로더가 IBM이 아닌 개인입니다. IBM이 처음 배포한 원래 경로(파일명 `WA_Fn-UseC_`는 IBM Watson Analytics 샘플에서 온 것으로 보임)와 그 이용 조건은 **미확인**입니다.
- [ ] 모델 파일(`.pkl`)의 성격 판단(미확정)
- [ ] 4.6(b)를 코드 공개로 충족하는지 판단(미확정)
- [x] ODbL 라이선스 사본을 저장소에 둘지, URI 고지로 할지 결정(4.2(b)는 둘 다 허용) → URI 고지(`data/README.md`, `README.md` 등)
- [x] 대시보드 화면의 고지 문구 보강 → 사이드바에 출처, ODbL 1.0·DbCL 1.0, 라이선스 주소, 코드 MIT 구분을 추가(2026-11-27). 이어서 출처·ODbL 1.0·DbCL 1.0을 공식 주소 링크로 바꿈(Stage 7-7)
- [x] 코드 라이선스 결정 → MIT License. 데이터 라이선스와 별도로 표기
