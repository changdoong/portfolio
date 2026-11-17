# models/

학습된 가중치(`*.pt`, `*.onnx`)는 Git 에 올리지 않습니다.

- 기본: `yolov8n.pt` — 첫 실행 시 ultralytics 가 자동 다운로드합니다.
- 커스텀: 지게차(forklift) 등 산업 장비를 검출하려면 파인튜닝한 가중치를 이곳에 두고
  `configs/config.yaml` 의 `detection.model` 과 `detection.class_map` 을 수정하세요.

```yaml
detection:
  model: "models/forklift_yolov8s.pt"
  class_map:
    person: [0]
    vehicle: [1]     # forklift
```
