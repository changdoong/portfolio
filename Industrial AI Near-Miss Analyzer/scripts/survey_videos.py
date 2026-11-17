"""다운로드한 영상별 통계 + 육안 확인용 Contact Sheet 생성 (데이터셋 사전 조사용).

    python scripts/survey_videos.py --manifest data/raw/mendeley_safe_unsafe/manifest.json --out outputs/dataset_survey

- OpenCV 로 frames / fps / 해상도 확인 (메타데이터 프레임 수 vs 실제 읽은 프레임 수)
- YOLOv8n(COCO) + ByteTrack (YOLODetector.track) 전 프레임 실행
  person / vehicle(COCO car, motorcycle, bus, truck) 검출 프레임 비율, 동시 검출 비율,
  사람-vehicle 하단 중앙 최소 '픽셀' 거리, 사람 트랙별 이동 범위(px)
- 대표 프레임 4장(처음 / 중간 / 끝 / 사람-vehicle 최근접 또는 사람 최다)에 박스를 그려 시트 저장

※ COCO 에는 forklift 클래스가 없으므로 vehicle 검출 ≠ 지게차 검출. 최종 판정은 시트 육안 확인으로 한다.
※ 픽셀 거리는 실제 거리가 아니다. Near-Miss 여부는 이 스크립트로 판정하지 않는다.
※ 조사용 통계를 위해 track() 이 빈 결과를 낸 프레임은 detect() 를 한 번 더 호출한다(성능 측정용 아님).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from src.detection.detector import YOLODetector  # noqa: E402

COCO = {0: "person", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
TILE_W, TILE_H = 480, 270


def foot(b):
    return np.array([(b[0] + b[2]) / 2, b[3]])


def survey_one(det: YOLODetector, it: dict, sheet_dir: str) -> dict:
    cap = cv2.VideoCapture(it["path"])
    n_meta = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    det.reset_tracking()
    n = p_frames = v_frames = both = max_p = maxp_frame = 0
    min_dist = min_dist_frame = None
    tracks, vclasses, per_frame = {}, {}, []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        dets = det.track(frame) or det.detect(frame)
        ps = [d for d in dets if d.category == "person"]
        vs = [d for d in dets if d.category == "vehicle"]
        for d in vs:
            vclasses[COCO[d.class_id]] = vclasses.get(COCO[d.class_id], 0) + 1
        p_frames += bool(ps)
        v_frames += bool(vs)
        if len(ps) > max_p:
            max_p, maxp_frame = len(ps), n
        if ps and vs:
            both += 1
            dmin = min(np.linalg.norm(foot(a.bbox) - foot(b.bbox)) for a in ps for b in vs)
            if min_dist is None or dmin < min_dist:
                min_dist, min_dist_frame = float(dmin), n
        for d in ps:
            if d.track_id is not None:
                tracks.setdefault(d.track_id, []).append(foot(d.bbox))
        per_frame.append([(d.bbox.copy(), d.category, COCO[d.class_id], d.score) for d in dets])
        n += 1
    cap.release()

    sel = sorted({0, n // 2, max(n - 1, 0), min_dist_frame if min_dist_frame is not None else maxp_frame})
    cap = cv2.VideoCapture(it["path"])
    tiles = []
    for idx in sel:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, fr = cap.read()
        if not ok:
            continue
        for b, cat, cname, s in per_frame[idx]:
            x1, y1, x2, y2 = b.astype(int)
            col = (60, 230, 60) if cat == "person" else (0, 140, 255)
            cv2.rectangle(fr, (x1, y1), (x2, y2), col, 6)
            cv2.putText(fr, f"{cname} {s:.2f}", (x1, max(y1 - 10, 30)), cv2.FONT_HERSHEY_SIMPLEX, 1.4, col, 4)
        fr = cv2.resize(fr, (TILE_W, TILE_H))
        tag = "closest" if idx == min_dist_frame else ("max-person" if idx == maxp_frame else "")
        cv2.rectangle(fr, (0, 0), (TILE_W, 22), (0, 0, 0), -1)
        cv2.putText(fr, f"f{idx}/{n} t={idx / fps:.1f}s {tag}", (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        tiles.append(fr)
    cap.release()
    while len(tiles) < 4:
        tiles.append(np.zeros((TILE_H, TILE_W, 3), np.uint8))
    row = np.hstack(tiles[:4])
    label = np.zeros((26, row.shape[1], 3), np.uint8)
    cv2.putText(label, f"{it['split']}/{it['class']}/{it['filename']}  {n} frames {fps:.1f}fps {w}x{h}",
                (6, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    cv2.imwrite(os.path.join(sheet_dir, f"{it['class'][:1]}_{it['split']}_{it['filename'][:-4]}.jpg"),
                np.vstack([label, row]), [cv2.IMWRITE_JPEG_QUALITY, 85])

    moves = sorted((float(np.linalg.norm(np.ptp(np.array(p), axis=0))) for p in tracks.values() if len(p) >= 5),
                   reverse=True)
    return {**{k: it[k] for k in ("split", "class", "filename", "size")},
            "frames_meta": n_meta, "frames_read": n, "fps": round(fps, 2), "res": f"{w}x{h}",
            "duration_s": round(n / fps, 2) if fps else None,
            "person_frame_ratio": round(p_frames / n, 3) if n else 0,
            "vehicle_frame_ratio": round(v_frames / n, 3) if n else 0,
            "both_frame_ratio": round(both / n, 3) if n else 0,
            "max_persons": max_p, "vehicle_classes": vclasses,
            "min_person_vehicle_px": None if min_dist is None else round(min_dist, 1),
            "person_tracks_ge5": len(moves), "person_max_move_px": round(moves[0], 1) if moves else 0.0,
            "sheet_frames": sel}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default=os.path.join(ROOT, "models", "yolov8n.pt"))
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--device", default="cuda:0")
    args = ap.parse_args()

    sheet_dir = os.path.join(args.out, "sheets")
    os.makedirs(sheet_dir, exist_ok=True)
    det = YOLODetector(args.model, conf=args.conf, device=args.device, half=False,
                       class_map={"person": [0], "vehicle": [2, 3, 5, 7]},
                       tracker_cfg=os.path.join(ROOT, "configs", "bytetrack.yaml"))
    items = json.load(open(args.manifest, encoding="utf-8"))
    results = []
    for k, it in enumerate(items, 1):
        r = survey_one(det, it, sheet_dir)
        results.append(r)
        print(f"[{k:3d}/{len(items)}] {it['split']:5s} {it['filename']:10s} n={r['frames_read']:4d} "
              f"P={r['person_frame_ratio']:.2f} V={r['vehicle_frame_ratio']:.2f} both={r['both_frame_ratio']:.2f}",
              flush=True)
    json.dump(results, open(os.path.join(args.out, "survey.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
