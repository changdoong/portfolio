"""86개 영상 데이터셋 분석 요약 (표 + 차트) 생성.

    python scripts/make_survey_summary.py --survey outputs/dataset_survey/survey.json \
        --review outputs/dataset_survey/visual_review.csv --out outputs/dataset_survey

입력
  survey.json        : scripts/survey_videos.py 가 만든 영상별 자동 통계 (OpenCV + YOLO/ByteTrack)
  visual_review.csv  : 대표 4프레임 육안 판정 (지게차 / 작업자 / 동시 등장 / 근접 후보 등급)
출력
  summary.md, summary.png

※ vehicle 은 COCO car/motorcycle/bus/truck 검출이며 지게차 검출이 아니다.
※ 근접 후보 등급(A/B/C)은 육안 선별용이며 Near-Miss 판정이 아니다. 픽셀 거리 ≠ 실제 거리.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter

CLASSES = [("3_carrying_overload_with_forklift", "Carrying Overload with Forklift (3번)"),
           ("7_safe_carrying", "Safe Carrying (7번)")]
FORK = ["확인", "원거리확인", "미확인"]
FORK_LABEL = {"확인": "확인(근·중거리)", "원거리확인": "원거리·소형으로만 확인", "미확인": "미확인"}
GRADE = ["A", "B", "C", "미확인"]
GRADE_LABEL = {"A": "A: 작업자와 인접","B": "B: 같은 프레임·중간 거리", "C": "C: 원거리·멀어짐", "미확인": "미확인(지게차 미확인)"}

# 참조 팔레트 categorical slot 1, 2 (light) / 텍스트·축 토큰
SERIES = ["#2a78d6", "#eb6834"]
INK, INK2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"


def load(survey_path, review_path):
    survey = json.load(open(survey_path, encoding="utf-8"))
    review = list(csv.DictReader(open(review_path, encoding="utf-8-sig")))
    return survey, review


def tables(survey, review):
    by_cls = {c: [r for r in review if r["class"] == c] for c, _ in CLASSES}
    fork = {c: Counter(r["forklift_visual"] for r in rows) for c, rows in by_cls.items()}
    grade = {c: Counter(r["proximity_candidate"] for r in rows) for c, rows in by_cls.items()}
    auto = {}
    for c, _ in CLASSES:
        s = [x for x in survey if x["class"] == c]
        auto[c] = {"n": len(s), "dur": sum(x["duration_s"] for x in s),
                   "fps": sorted({x["fps"] for x in s}), "res": sorted({x["res"] for x in s}),
                   "frames_match": sum(x["frames_meta"] == x["frames_read"] for x in s),
                   "size_mb": sum(x["size"] for x in s) / 1e6}
    return fork, grade, auto


def render_md(fork, grade, auto) -> str:
    L = ["# 데이터셋 분석 요약 (Mendeley Safe/Unsafe Behaviours, 지게차 관련 2개 클래스)", "",
         "- 출처: Önal & Dandıl (2024), Mendeley Data, DOI 10.17632/xjmtb22pff.1 · CC BY 4.0",
         "- 자동 통계: OpenCV(해상도·FPS·프레임 수) + YOLOv8n(COCO, conf 0.25) + ByteTrack",
         "- 육안 판정: 영상별 대표 4프레임(처음/중간/끝/YOLO 기준 사람-vehicle 최근접)", "",
         "| 클래스 | 영상 수 | 총 길이(s) | 용량(MB) | 해상도 | FPS 범위 | 프레임 수 일치 |", "|---|---|---|---|---|---|---|"]
    for c, name in CLASSES:
        a = auto[c]
        L.append(f"| {name} | {a['n']} | {a['dur']:.1f} | {a['size_mb']:.1f} | {', '.join(a['res'])} | "
                 f"{min(a['fps'])}~{max(a['fps'])} | {a['frames_match']}/{a['n']} |")
    L += ["", "| 지게차 육안 판정 | " + " | ".join(n for _, n in CLASSES) + " | 합계 |", "|---|---|---|---|"]
    for k in FORK:
        v = [fork[c][k] for c, _ in CLASSES]
        L.append(f"| {FORK_LABEL[k]} | " + " | ".join(map(str, v)) + f" | {sum(v)} |")
    L += ["", "| 근접 후보 등급 (육안, Near-Miss 판정 아님) | " + " | ".join(n for _, n in CLASSES) + " | 합계 |",
          "|---|---|---|---|"]
    for k in GRADE:
        v = [grade[c][k] for c, _ in CLASSES]
        L.append(f"| {GRADE_LABEL[k]} | " + " | ".join(map(str, v)) + f" | {sum(v)} |")
    L += ["", "※ vehicle(COCO) 검출 ≠ 지게차 검출. 근접 후보 등급은 화면상 위치 기준이며 실제 거리·Near-Miss 여부를 의미하지 않음.", ""]
    return "\n".join(L)


def render_png(fork, grade, path):
    import matplotlib
    import matplotlib.ticker

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    for f in ("Malgun Gothic", "AppleGothic", "NanumGothic", "Noto Sans CJK KR"):
        if any(f == x.name for x in font_manager.fontManager.ttflist):
            plt.rcParams["font.family"] = f
            break
    plt.rcParams["axes.unicode_minus"] = False

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6), facecolor=SURFACE)
    panels = [("지게차 육안 판정 (86개)", FORK, FORK_LABEL, fork),
              ("근접 후보 등급 — 육안 선별용, Near-Miss 판정 아님", GRADE, GRADE_LABEL, grade)]
    h = 0.36
    for ax, (title, keys, labels, data) in zip(axes, panels):
        ax.set_facecolor(SURFACE)
        ys = list(range(len(keys)))[::-1]
        for si, (c, name) in enumerate(CLASSES):
            vals = [data[c][k] for k in keys]
            pos = [y + (h / 2 + 0.02) * (1 if si == 0 else -1) for y in ys]
            bars = ax.barh(pos, vals, height=h, color=SERIES[si], label=name, zorder=3)
            for b, v in zip(bars, vals):
                ax.text(b.get_width() + 0.6, b.get_y() + b.get_height() / 2, str(v), va="center",
                        fontsize=10, color=INK2)
        ax.set_yticks(ys)
        ax.set_yticklabels([labels[k] for k in keys], color=INK, fontsize=10)
        ax.set_title(title, loc="left", fontsize=12, color=INK, pad=10)
        ax.xaxis.grid(True, color=GRID, linewidth=0.8, zorder=0)
        ax.tick_params(axis="x", colors=MUTED, labelsize=9)
        ax.tick_params(axis="y", length=0)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.spines["bottom"].set_color(AXIS)
        ax.set_xlabel("영상 수", color=MUTED, fontsize=9)
        ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
        ax.set_xlim(0, max(max(data[c][k] for k in keys) for c, _ in CLASSES) * 1.18)
    axes[0].legend(loc="lower right", frameon=False, fontsize=9, labelcolor=INK2)
    fig.text(0.01, 0.01, "Mendeley Safe/Unsafe Behaviours (CC BY 4.0) · 클래스 3·7 전체 86개 · 대표 4프레임 육안 판정. "
             "COCO vehicle 검출은 지게차 검출이 아니며, 픽셀 거리는 실제 거리가 아님.", fontsize=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--survey", default="outputs/dataset_survey/survey.json")
    ap.add_argument("--review", default="outputs/dataset_survey/visual_review.csv")
    ap.add_argument("--out", default="outputs/dataset_survey")
    args = ap.parse_args()
    survey, review = load(args.survey, args.review)
    fork, grade, auto = tables(survey, review)
    os.makedirs(args.out, exist_ok=True)
    md = render_md(fork, grade, auto)
    open(os.path.join(args.out, "summary.md"), "w", encoding="utf-8").write(md)
    render_png(fork, grade, os.path.join(args.out, "summary.png"))
    print(md)


if __name__ == "__main__":
    main()
