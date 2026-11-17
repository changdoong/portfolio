# data/

영상/데이터셋은 용량 문제로 Git 에 올리지 않습니다. 이 폴더에 직접 내려받아 사용하세요.

## 권장 데이터셋

| 데이터셋 | 내용 | 용도 |
|---|---|---|
| AI Hub – 공사현장 안전장비 / 산업안전 CCTV 영상 | 국내 산업현장 CCTV, 사람·장비 bbox | 검출 모델 파인튜닝, 시나리오 테스트 |
| SODA (Site Object Detection dAtaset) | 건설현장 15종 객체 | 지게차·중장비 클래스 학습 |
| MOT17 / MOT20 | 보행자 다중객체추적 벤치마크 | 트래커 성능(MOTA, IDF1) 평가 |
| 직접 촬영 / 공개 CCTV 샘플 | 지게차-작업자 교차 장면 | 데모 영상 |

## 폴더 구성 (예시)

```
data/
├── sample.mp4            # 데모용 영상 (config 의 video.source 기본값)
├── raw/                  # 원본 영상
└── labels/
    └── near_miss_gt.csv  # 수동 라벨링한 위험 시점 (frame) → utils/metrics.py 평가용
```
