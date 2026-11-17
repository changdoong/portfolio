"""근접 에피소드(후보 이벤트) 개별 감사 → event_audit.csv + 비식별 캡처.

    .\\.venv\\Scripts\\python.exe scripts\\audit_events.py --out outputs\\day2\\event_audit
    # 육안 검토 메모(video,event_id,visual_vehicle_identity,visual_driver_misdetection,
    #                 visual_pedestrian_proximity,visual_review)를 합칠 때
    .\\.venv\\Scripts\\python.exe scripts\\audit_events.py --out outputs\\day2\\event_audit_reviewed --notes <notes.csv>

입력 : outputs/day2/<video>/<run_tag>/events.csv, tracks.csv, result.mp4  (run_batch.py 결과)
판정 보조 지표 (자동, 확정 아님)
  - person_in_vehicle_ioa : person 박스 면적 중 vehicle 박스와 겹치는 비율 (최근접 프레임 / 구간 중앙값)
  - co_motion_corr        : person 과 vehicle 하단 중앙점 이동(프레임 간 변위)의 상관계수 → 1 에 가까우면 함께 움직임
  - driver_misdetection_likelihood : IoA·동반 이동 기반 높음/중간/낮음
  - pedestrian_proximity_likelihood: 운전자 가능성이 낮고 person 이 독립적으로 존재하면 높음
※ 모든 이벤트는 '후보 이벤트'이며 Near-Miss 로 확정하지 않는다. 거리는 미보정 픽셀 거리다.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import defaultdict

import cv2
import numpy as np
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from make_captures import SIZE, Anonymizer, load_tracks, read_frame  # noqa: E402
from src.utils.privacy import PrivacyError, ioa  # noqa: E402

FIELDS = ["video", "event_id", "candidate_type", "start_frame", "escalate_frame", "last_risk_frame", "end_logged_frame",
          "duration_sec", "max_severity", "person_track_id", "vehicle_track_id", "min_distance_px", "min_distance_frame",
          "frames_both_present", "person_in_vehicle_ioa_at_min", "person_in_vehicle_ioa_median", "co_motion_corr",
          "driver_misdetection_likelihood", "pedestrian_proximity_likelihood", "capture",
          "visual_vehicle_identity", "visual_driver_misdetection", "visual_pedestrian_proximity", "visual_review",
          "near_miss_confirmed"]
VISUAL_FIELDS = ("visual_vehicle_identity", "visual_driver_misdetection", "visual_pedestrian_proximity", "visual_review")


def group_events(events_csv: str):
    ev = defaultdict(dict)
    for r in csv.DictReader(open(events_csv, encoding="utf-8")):
        if r["type"] != "near_miss" or not r.get("event_id"):
            continue
        ev[r["event_id"]][r["phase"]] = r
    return ev


def pair_series(by_frame, pid: int, vid: int):
    """프레임별 (person box, vehicle box) – 둘 다 확정 트랙으로 존재하는 프레임만."""
    out = {}
    for f, rows in by_frame.items():
        p = [r for r in rows if r["category"] == "person" and int(r["track_id"]) == pid]
        v = [r for r in rows if r["category"] == "vehicle" and int(r["track_id"]) == vid]
        if p and v:
            out[f] = tuple(tuple(float(x[k]) for k in ("x1", "y1", "x2", "y2")) for x in (p[0], v[0]))
    return dict(sorted(out.items()))


def foot(b):
    return np.array([(b[0] + b[2]) / 2, b[3]])


def co_motion(series) -> float | None:
    fs = list(series)
    dp, dv = [], []
    for a, b in zip(fs, fs[1:]):
        if b - a == 1:
            dp.append(foot(series[b][0]) - foot(series[a][0]))
            dv.append(foot(series[b][1]) - foot(series[a][1]))
    if len(dp) < 5:
        return None
    dp, dv = np.array(dp).ravel(), np.array(dv).ravel()
    if dp.std() < 1e-6 or dv.std() < 1e-6:
        return None
    return float(np.corrcoef(dp, dv)[0, 1])


def likelihoods(ioa_min: float, ioa_med: float, corr) -> tuple[str, str]:
    if ioa_med >= 0.6 and (corr is None or corr >= 0.5):
        driver = "높음"
    elif ioa_min >= 0.6 or ioa_med >= 0.3:
        driver = "중간"
    else:
        driver = "낮음"
    ped = {"높음": "낮음", "중간": "중간", "낮음": "높음"}[driver]
    return driver, ped


def audit(videos, runs_root, run_tag, out_dir, anonymizer, fps_default=25.0, notes=None):
    rows, images = [], {}
    for v in videos:
        run = os.path.join(runs_root, v["id"], run_tag)
        by_frame = load_tracks(os.path.join(run, "tracks.csv"))
        fps = fps_default
        perf = os.path.join(run, "perf.json")
        for eid, ph in group_events(os.path.join(run, "events.csv")).items():
            st, en, esc = ph.get("start"), ph.get("end"), ph.get("escalate")
            pid, vid = map(int, st["track_ids"].split("-"))
            series = pair_series(by_frame, pid, vid)
            start = int(st["frame"])
            dur = float(en["duration_sec"]) if en and en.get("duration_sec") else None
            last_risk = start + int(round(dur * fps)) - 1 if dur else None
            window = {f: s for f, s in series.items() if start <= f <= (last_risk or max(series))}
            dists = {f: float(np.linalg.norm(foot(p) - foot(q))) for f, (p, q) in window.items()}
            fmin = min(dists, key=dists.get)
            ioas = [ioa(p, q) for p, q in window.values()]
            ioa_min = ioa(*window[fmin])
            corr = co_motion(window)
            driver, ped = likelihoods(ioa_min, float(np.median(ioas)), corr)

            name = f"{v['id']}_{eid}.jpg"
            picks = sorted({start, fmin, last_risk if last_risk in window else max(window)})
            tiles = []
            for f in picks:
                shown = read_frame(os.path.join(run, "result.mp4"), f)
                img, _ = anonymizer(shown, read_frame(v["path"], f, SIZE), by_frame[f])
                im = cv2.resize(img, (640, 360))
                cv2.rectangle(im, (0, 330), (640, 360), (0, 0, 0), -1)
                d = dists.get(f)
                cv2.putText(im, f"{v['id']} {eid} f{f}  P#{pid}-V#{vid}  {'' if d is None else f'{d:.0f}px (pixel)'}",
                            (8, 351), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                tiles.append(im)
            images[name] = np.hstack(tiles)

            key = (v["id"], eid)
            rows.append({
                "video": v["id"], "event_id": eid, "candidate_type": "근접 후보 이벤트 (미보정 픽셀 거리)",
                "start_frame": start, "escalate_frame": esc["frame"] if esc else "",
                "last_risk_frame": last_risk if last_risk is not None else "",
                "end_logged_frame": en["frame"] if en else "", "duration_sec": dur if dur is not None else "",
                "max_severity": (en or st).get("max_severity") or st["severity"],
                "person_track_id": pid, "vehicle_track_id": vid,
                "min_distance_px": round(dists[fmin], 1), "min_distance_frame": fmin,
                "frames_both_present": len(window),
                "person_in_vehicle_ioa_at_min": round(ioa_min, 3),
                "person_in_vehicle_ioa_median": round(float(np.median(ioas)), 3),
                "co_motion_corr": "" if corr is None else round(corr, 3),
                "driver_misdetection_likelihood": driver, "pedestrian_proximity_likelihood": ped,
                "capture": name,
                **{k: (notes or {}).get(key, {}).get(k, "미검토") for k in VISUAL_FIELDS},
                "near_miss_confirmed": "확정하지 않음 (후보)",
            })
    return rows, images


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--videos", default="configs/day2_videos.yaml")
    ap.add_argument("--runs-root", default="outputs/day2")
    ap.add_argument("--run-tag", default="fp16_save_on")
    ap.add_argument("--out", default="outputs/day2/event_audit")
    ap.add_argument("--model", default="models/yolov8n.pt")
    ap.add_argument("--notes", default=None, help="육안 검토 메모 CSV (video,event_id,visual_review)")
    args = ap.parse_args(argv)
    os.chdir(ROOT)
    if os.path.exists(args.out):
        print(f"[중단] 출력 폴더가 이미 존재합니다 (덮어쓰기 금지): {args.out}")
        return 1
    notes = None
    if args.notes:
        notes = {(r["video"], r["event_id"]): r for r in csv.DictReader(open(args.notes, encoding="utf-8-sig"))}
    videos = yaml.safe_load(open(args.videos, encoding="utf-8"))["videos"]
    try:
        rows, images = audit(videos, args.runs_root, args.run_tag, args.out, Anonymizer(args.model), notes=notes)
    except PrivacyError as e:
        print(f"[중단] 비식별 처리 실패 → 캡처를 생성하지 않습니다: {e}")
        return 1
    os.makedirs(args.out)
    for name, img in images.items():
        cv2.imwrite(os.path.join(args.out, name), img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    with open(os.path.join(args.out, "event_audit.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print({k: r[k] for k in ("video", "event_id", "start_frame", "last_risk_frame", "max_severity", "person_track_id",
                                 "vehicle_track_id", "min_distance_px", "min_distance_frame", "person_in_vehicle_ioa_at_min",
                                 "person_in_vehicle_ioa_median", "co_motion_corr", "driver_misdetection_likelihood")})
    return 0


if __name__ == "__main__":
    sys.exit(main())
