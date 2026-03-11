#  Kaggle Project: [외향적인 사람과 내향적인 사람을 예측하라]

##  대회 개요
- 대회 링크: [[Kaggle URL](https://www.kaggle.com/competitions/playground-series-s5e7/overview)]
- 목표: [당신의 목표는 사회적 행동과 성격 특성을 고려하여 사람이 내향적인지 외향적인지 예측하는 것입니다.]
- 데이터: [이 대회의 데이터 세트(학습 및 테스트 모두)는 외향적 행동 대 내향적 행동 데이터 세트에서 훈련된 딥 러닝 모델에서 생성되었습니다.
   기능 분포는 원본과 비슷하지만 정확히 동일하지는 않습니다.
  이 대회의 일부로 원본 데이터 세트를 자유롭게 사용하여 차이점을 탐색하고 원본이 학습에 통합되면 모델 성능이 향상되는지 확인할 수 있습니다.]

##  분석 및 접근 방식
- 데이터 전처리
  - F-검정을 사용해 범주형컬럼의 결측값 처리 
  - 수치형 결측값 처리
  - 범주형 변수 인코딩
- 탐색적 데이터 분석 (EDA)
  - 주요 시각화 및 인사이트

##  모델링
- LazyPredict로 모델 비교
- 상위 모델 2개 선정 (perceptron, LGBM)
- Optuna로 하이퍼파라미터 튜닝
- H20 AUTOML 사용해 Optuna 사용 모델과 비교

##  성능 평가
- 사용한 평가 지표: `log_loss`, `f1_score`
- 과적합 여부 확인: 학습 vs 검증 손실 비교

##  캐글 제출 결과
- Public Leaderboard 순위: 811등 / 3093명
<img width="1090" height="63" alt="image" src="https://github.com/user-attachments/assets/dec7890e-0ab1-4d00-8999-aed607d1b041" />


- 제출 파일: `person1.csv`

##  배운 점 & 개선 방향
- Lazypredict를 사용해 모델에 가장 적합한 상위 2개의 알고리즘을 찾을 수 있었고 optuna를 사용해 최적의 하이퍼파라미터를 구할 수 있었다
- AUTOML인 H2O를 사용해보았는데 동일한 전처리 데이터였는데 직접 학습시킨 모델보다 정확도가 낮게 나왔다.
  AUTOML이 편하긴 하지만 당분간은 직접 학습 시킬 것 같다.

