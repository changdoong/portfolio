"""운전자 / 보행자 구분 (D3-3). IoA 하나만으로 판정하지 않는다.

person–vehicle 쌍마다 최근 window 프레임(둘 다 관측된 프레임)을 모아, 다음을 **모두** 만족하면 driver:
  1) 겹침     : person 박스 중 vehicle 박스와 겹치는 비율(IoA) 중앙값 ≥ ioa_thr
  2) 운전석   : person 중심이 운전석 추정 영역(가운데 70% 폭, 위쪽 60%) 안이고
                person 하단이 vehicle 하단보다 foot_margin_ratio × 차량 높이 이상 위에 있는 프레임 비율 ≥ cab_ratio_thr
                (차량 앞에 서 있는 보행자는 발이 차량 하단 근처/아래에 있어 여기서 걸러진다)
  3) 동시 이동: vehicle 이 움직이면 창 전체의 person 순변위가 vehicle 순변위와 같아야 함
                (|Δp_net−Δv_net| / |Δv_net| ≤ co_motion_tol), vehicle 이 정지면 person 도 정지
관측 프레임이 min_frames 미만이면 판정하지 않는다(= 보행자로 취급, 위험 판정 유지).
"""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Deque, Dict, List, Set, Tuple

import numpy as np

from src.utils.privacy import cab_region, ioa


def _foot(b):
    return np.array([(b[0] + b[2]) / 2.0, b[3]])


class RoleClassifier:
    def __init__(self, window: int = 15, min_frames: int = 8, ioa_thr: float = 0.5, cab_ratio_thr: float = 0.6,
                 foot_margin_ratio: float = 0.05, co_motion_tol: float = 0.5, still_px: float = 1.0):
        self.window, self.min_frames = int(window), int(min_frames)
        self.ioa_thr, self.cab_thr = float(ioa_thr), float(cab_ratio_thr)
        self.margin, self.tol, self.still = float(foot_margin_ratio), float(co_motion_tol), float(still_px)
        self._hist: Dict[Tuple[int, int], Deque] = defaultdict(lambda: deque(maxlen=self.window))
        self._decision: Dict[Tuple[int, int], bool] = {}
        self.log: List[Dict] = []

    @staticmethod
    def _in_cab(p, v, margin) -> bool:
        cx1, cy1, cx2, cy2 = cab_region(tuple(v))
        pcx, pcy = (p[0] + p[2]) / 2, (p[1] + p[3]) / 2
        return cx1 <= pcx <= cx2 and cy1 <= pcy <= cy2 and p[3] <= v[3] - margin * (v[3] - v[1])

    def metrics(self, hist) -> Dict:
        frames = [h[0] for h in hist]
        ps = [h[1] for h in hist]
        vs = [h[2] for h in hist]
        ioas = [ioa(tuple(p), tuple(v)) for p, v in zip(ps, vs)]
        cab = [self._in_cab(p, v, self.margin) for p, v in zip(ps, vs)]
        dp, dv = [], []
        for i in range(1, len(hist)):
            if frames[i] - frames[i - 1] == 1:
                dp.append(_foot(ps[i]) - _foot(ps[i - 1]))
                dv.append(_foot(vs[i]) - _foot(vs[i - 1]))
        v_speed = float(np.mean([np.linalg.norm(d) for d in dv])) if dv else 0.0
        p_speed = float(np.mean([np.linalg.norm(d) for d in dp])) if dp else 0.0
        # 동시 이동은 창 전체의 '순 변위'로 비교 (프레임별 박스 흔들림의 영향을 줄임)
        span = max(frames[-1] - frames[0], 1)
        dp_net = _foot(ps[-1]) - _foot(ps[0])
        dv_net = _foot(vs[-1]) - _foot(vs[0])
        v_net_speed = float(np.linalg.norm(dv_net)) / span
        p_net_speed = float(np.linalg.norm(dp_net)) / span
        rel = float(np.linalg.norm(dp_net - dv_net) / (np.linalg.norm(dv_net) + 1e-9)) if len(hist) > 1 else None
        if len(hist) < 2:
            co_ok, co_note = False, "프레임 부족"
        elif v_net_speed >= self.still:
            co_ok, co_note = rel <= self.tol, f"vehicle 이동, 순변위 상대오차 {rel:.2f}"
        else:
            co_ok, co_note = p_net_speed < self.still, f"vehicle 정지, person 순속도 {p_net_speed:.2f}px/f"
        return {"n": len(hist), "ioa_median": float(np.median(ioas)), "cab_ratio": float(np.mean(cab)),
                "vehicle_speed_px_f": v_speed, "person_speed_px_f": p_speed,
                "rel_motion": rel, "co_motion_ok": co_ok, "co_motion_note": co_note}

    def update(self, views, frame_idx: int) -> Set[Tuple[int, int]]:
        """현재 프레임에서 driver 로 판정된 (person_id, vehicle_id) 쌍 집합."""
        persons = [v for v in views if v.category == "person"]
        vehicles = [v for v in views if v.category == "vehicle"]
        drivers = set()
        for p in persons:
            pb = np.asarray(p.bbox, float)
            for v in vehicles:
                vb = np.asarray(v.bbox, float)
                key = (p.track_id, v.track_id)
                if ioa(tuple(pb), tuple(vb)) <= 0 and key not in self._hist:
                    continue
                h = self._hist[key]
                while h and frame_idx - h[0][0] >= self.window:
                    h.popleft()
                h.append((frame_idx, pb, vb))
                if len(h) < self.min_frames:
                    continue
                m = self.metrics(h)
                is_driver = m["ioa_median"] >= self.ioa_thr and m["cab_ratio"] >= self.cab_thr and m["co_motion_ok"]
                if is_driver:
                    drivers.add(key)
                if self._decision.get(key) != is_driver:
                    reasons = []
                    if m["ioa_median"] < self.ioa_thr:
                        reasons.append(f"IoA {m['ioa_median']:.2f}<{self.ioa_thr}")
                    if m["cab_ratio"] < self.cab_thr:
                        reasons.append(f"운전석 비율 {m['cab_ratio']:.2f}<{self.cab_thr}")
                    if not m["co_motion_ok"]:
                        reasons.append(f"동시이동 불충족({m['co_motion_note']})")
                    self.log.append({"frame": frame_idx, "person_id": p.track_id, "vehicle_id": v.track_id,
                                     "role": "driver" if is_driver else "pedestrian",
                                     "ioa_median": round(m["ioa_median"], 3), "cab_ratio": round(m["cab_ratio"], 3),
                                     "vehicle_speed_px_f": round(m["vehicle_speed_px_f"], 2),
                                     "person_speed_px_f": round(m["person_speed_px_f"], 2),
                                     "rel_motion": None if m["rel_motion"] is None else round(m["rel_motion"], 3),
                                     "reason": "모든 조건 충족" if is_driver else "; ".join(reasons)})
                    self._decision[key] = is_driver
        return drivers
