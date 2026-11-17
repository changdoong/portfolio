"""짧은 vehicle 트랙(추적 실패 후보) 감사 → track_audit.csv + 비식별 확대 캡처.

    .\\.venv\\Scripts\\python.exe scripts\\audit_tracks.py --video 3_tr6 --out outputs\\day2\\track_audit\\3_tr6
    .\\.venv\\Scripts\\python.exe scripts\\audit_tracks.py --video 3_tr6 --out <새 폴더> --notes <notes.csv>

자동 단서 (분류 확정 아님, 최종 분류는 육안 검토)
  - lifetime_frames, bbox 크기, 이동량(px), COCO 클래스, 평균 score
  - overlap_with_track : 같은 프레임에서 IoU ≥ 0.2 로 겹치는 다른 vehicle 트랙 (적재물/차체 중복 검출 가능성)
  - handoff_track      : ±gap 프레임 안에 근처(하단중앙 120px 이내)에서 끝나거나 시작한 다른 vehicle 트랙 (ID 단절 가능성)
  - auto_hint          : static_object / duplicate_box / id_fragment / unknown
※ ByteTrack 파라미터는 변경하지 않는다. 이 스크립트는 기존 실행 결과(tracks.csv)만 읽는다.
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
from src.tracking.tracker import iou_matrix  # noqa: E402
from src.utils.privacy import PrivacyError  # noqa: E402

FIELDS = ["video", "track_id", "lifetime_frames", "first_frame", "last_frame", "coco_classes", "mean_score",
          "bbox_w_mean", "bbox_h_mean", "foot_x_mean", "foot_y_mean", "move_px", "overlap_with_track", "handoff_track",
          "auto_hint", "capture", "visual_class", "visual_review"]
VISUAL = ("visual_class", "visual_review")


def track_table(by_frame, category="vehicle"):
    t = defaultdict(list)
    for f, rows in by_frame.items():
        for r in rows:
            if r["category"] == category:
                t[int(r["track_id"])].append((f, r))
    return {k: sorted(v, key=lambda x: x[0]) for k, v in t.items()}


def _box(r):
    return np.array([float(r[k]) for k in ("x1", "y1", "x2", "y2")])


def _foot(b):
    return np.array([(b[0] + b[2]) / 2, b[3]])


def analyze(tracks, short_len=10, gap=5, near_px=120, static_move_px=15):
    out = []
    for tid, seq in tracks.items():
        if len(seq) >= short_len:
            continue
        frames = [f for f, _ in seq]
        boxes = np.array([_box(r) for _, r in seq])
        feet = np.array([_foot(b) for b in boxes])
        move = float(np.linalg.norm(np.ptp(feet, axis=0)))
        overlaps, handoffs = set(), set()
        for oid, oseq in tracks.items():
            if oid == tid:
                continue
            ob = {f: _box(r) for f, r in oseq}
            for f, r in seq:
                if f in ob and iou_matrix(_box(r)[None], ob[f][None])[0, 0] >= 0.2:
                    overlaps.add(oid)
            of = [f for f, _ in oseq]
            ends_before = [f for f in of if frames[0] - gap <= f < frames[0]]
            starts_after = [f for f in of if frames[-1] < f <= frames[-1] + gap]
            if (ends_before and max(of) < frames[0] and np.linalg.norm(_foot(ob[max(ends_before)]) - feet[0]) <= near_px) or \
               (starts_after and min(of) > frames[-1] and np.linalg.norm(_foot(ob[min(starts_after)]) - feet[-1]) <= near_px):
                handoffs.add(oid)
        if overlaps:
            hint = "duplicate_box"
        elif handoffs:
            hint = "id_fragment"
        elif move <= static_move_px:
            hint = "static_object"
        else:
            hint = "unknown"
        out.append({
            "track_id": tid, "lifetime_frames": len(seq), "first_frame": frames[0], "last_frame": frames[-1],
            "coco_classes": ";".join(sorted({r["class_name"] for _, r in seq if r["class_name"]})),
            "mean_score": round(float(np.mean([float(r["score"]) for _, r in seq])), 3),
            "bbox_w_mean": round(float((boxes[:, 2] - boxes[:, 0]).mean()), 1),
            "bbox_h_mean": round(float((boxes[:, 3] - boxes[:, 1]).mean()), 1),
            "foot_x_mean": round(float(feet[:, 0].mean()), 1), "foot_y_mean": round(float(feet[:, 1].mean()), 1),
            "move_px": round(move, 1), "overlap_with_track": ";".join(map(str, sorted(overlaps))),
            "handoff_track": ";".join(map(str, sorted(handoffs))), "auto_hint": hint,
        })
    return sorted(out, key=lambda r: r["first_frame"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True)
    ap.add_argument("--videos", default="configs/day2_videos.yaml")
    ap.add_argument("--runs-root", default="outputs/day2")
    ap.add_argument("--run-tag", default="fp16_save_on")
    ap.add_argument("--out", required=True)
    ap.add_argument("--short-len", type=int, default=10)
    ap.add_argument("--model", default="models/yolov8n.pt")
    ap.add_argument("--notes", default=None, help="육안 검토 CSV (track_id,visual_class,visual_review)")
    args = ap.parse_args(argv)
    os.chdir(ROOT)
    if os.path.exists(args.out):
        print(f"[중단] 출력 폴더가 이미 존재합니다 (덮어쓰기 금지): {args.out}")
        return 1
    src = next(v["path"] for v in yaml.safe_load(open(args.videos, encoding="utf-8"))["videos"] if v["id"] == args.video)
    run = os.path.join(args.runs_root, args.video, args.run_tag)
    by_frame = load_tracks(os.path.join(run, "tracks.csv"))
    tracks = track_table(by_frame)
    rows = analyze(tracks, short_len=args.short_len)
    notes = {}
    if args.notes:
        notes = {int(r["track_id"]): r for r in csv.DictReader(open(args.notes, encoding="utf-8-sig"))}

    anon = Anonymizer(args.model)
    images = {}
    try:
        for r in rows:
            seq = tracks[r["track_id"]]
            f, tr = seq[len(seq) // 2]
            img, _ = anon(read_frame(os.path.join(run, "result.mp4"), f), read_frame(src, f, SIZE), by_frame[f])
            b = _box(tr)
            x1, y1 = int(max(0, b[0] - 120)), int(max(0, b[1] - 80))
            x2, y2 = int(min(SIZE[0], b[2] + 120)), int(min(SIZE[1], b[3] + 80))
            crop = img[y1:y2, x1:x2].copy()
            s = 320 / crop.shape[0]
            crop = cv2.resize(crop, (int(crop.shape[1] * s), 320))
            ctx = cv2.resize(img, (569, 320))
            cv2.rectangle(ctx, (int(x1 * 569 / 1280), int(y1 * 320 / 720)), (int(x2 * 569 / 1280), int(y2 * 320 / 720)),
                          (0, 0, 255), 2)
            tile = np.hstack([ctx, crop])
            cv2.putText(tile, f"{args.video} vehicle #{r['track_id']} f{f} ({r['lifetime_frames']} frames, {r['coco_classes']})",
                        (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
            name = f"{args.video}_vehicle_{r['track_id']}.jpg"
            images[name] = tile
            r.update({"video": args.video, "capture": name,
                      **{k: notes.get(r["track_id"], {}).get(k, "미검토") for k in VISUAL}})
    except PrivacyError as e:
        print(f"[중단] 비식별 처리 실패 → 캡처를 생성하지 않습니다: {e}")
        return 1

    os.makedirs(args.out)
    for name, img in images.items():
        cv2.imwrite(os.path.join(args.out, name), img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    with open(os.path.join(args.out, "track_audit.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    all_v = {k: len(v) for k, v in tracks.items()}
    print(f"vehicle 트랙 전체 {len(all_v)}개 (수명: {dict(sorted(all_v.items()))}), <{args.short_len}프레임 {len(rows)}개")
    for r in rows:
        print({k: r[k] for k in FIELDS[1:15]})
    return 0


if __name__ == "__main__":
    sys.exit(main())
