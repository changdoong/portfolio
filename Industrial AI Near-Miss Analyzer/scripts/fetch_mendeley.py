"""Mendeley "Video Dataset for Safe and Unsafe Behaviours" 선택 다운로드 도구.

출처   : Önal, O., Dandıl, E. (2024). Video Dataset for Safe and Unsafe Behaviours. Mendeley Data, V1.
         DOI 10.17632/xjmtb22pff.1  https://data.mendeley.com/datasets/xjmtb22pff/1
라이선스: CC BY 4.0 (출처 표기 필요, 변경 시 변경 사실 표시)

**인자 없이 실행하면 아무것도 다운로드하지 않고 도움말만 출력한다.**

    # 1) 목록/용량만 조회 (공식 Public API 메타데이터, 영상 다운로드 없음)
    python scripts/fetch_mendeley.py list --classes 3_ 7_

    # 2) 명시적 download 명령으로만 다운로드 (sha256 검증, 이미 받은 파일은 건너뜀)
    python scripts/fetch_mendeley.py download --classes 3_ 7_ --dest data/raw/mendeley_safe_unsafe

클래스 접두어: 0_safe_walkway_violation 1_unauthorized_intervention 2_opened_panel cover
              3_carrying_overload_with_forklift 4_safe_walkway 5_authorized_intervention
              6_closed_panel_cover 7_safe_carrying
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.request
from typing import Dict, List, Sequence, Tuple

API = "https://data.mendeley.com/public-api/datasets/xjmtb22pff"
HEADERS = {"User-Agent": "industrial-near-miss-analyzer/fetch"}


def _get(url: str):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60) as r:
        return json.load(r)


def list_files(prefixes: Sequence[str]) -> List[Tuple[str, str, Dict]]:
    """(split, class, file_entry) 목록. 공식 Public API 메타데이터만 조회한다."""
    folders = _get(API + "/folders/1")
    byid = {f["id"]: f for f in folders}
    out = []
    for f in folders:
        p = f.get("parent_id")
        if p in byid and byid[p]["name"] in ("train", "test") and f["name"].startswith(tuple(prefixes)):
            for x in _get(f"{API}/files?folder_id={f['id']}&version=1"):
                out.append((byid[p]["name"], f["name"], x))
    return sorted(out, key=lambda t: (t[1], t[0], t[2]["filename"]))


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while b := f.read(1 << 20):
            h.update(b)
    return h.hexdigest()


def download(targets: List[Tuple[str, str, Dict]], dest: str) -> List[Dict]:
    manifest = []
    for i, (split, cls, x) in enumerate(targets, 1):
        d = os.path.join(dest, split, cls)
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, x["filename"])
        exp = x["content_details"]["sha256_hash"]
        if os.path.exists(path) and os.path.getsize(path) == x["size"] and sha256(path) == exp:
            status = "skip(existing ok)"
        else:
            for attempt in range(3):
                try:
                    # 서명 URL 은 만료되므로 매번 재발급
                    fresh = next(y for y in _get(f"{API}/files?folder_id={x['folder_id']}&version=1") if y["id"] == x["id"])
                    req = urllib.request.Request(fresh["content_details"]["download_url"], headers=HEADERS)
                    with urllib.request.urlopen(req, timeout=120) as r, open(path + ".part", "wb") as fo:
                        while chunk := r.read(1 << 20):
                            fo.write(chunk)
                    os.replace(path + ".part", path)
                    break
                except Exception as e:  # noqa: BLE001
                    print(f"   retry {attempt + 1}: {e}", flush=True)
                    time.sleep(3)
            ok = os.path.exists(path) and os.path.getsize(path) == x["size"] and sha256(path) == exp
            status = "OK" if ok else "MISMATCH"
        manifest.append({"split": split, "class": cls, "filename": x["filename"], "size": x["size"],
                         "sha256": exp, "file_id": x["id"], "path": path})
        print(f"[{i:3d}/{len(targets)}] {split}/{cls}/{x['filename']} {x['size'] / 1e6:.1f}MB {status}", flush=True)
    with open(os.path.join(dest, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    p_list = sub.add_parser("list", help="파일 목록·용량 조회 (다운로드 없음)")
    p_list.add_argument("--classes", nargs="+", required=True, help="클래스 접두어 (예: 3_ 7_)")
    p_dl = sub.add_parser("download", help="지정 클래스만 다운로드 + sha256 검증")
    p_dl.add_argument("--classes", nargs="+", required=True)
    p_dl.add_argument("--dest", required=True, help="저장 위치 (예: data/raw/mendeley_safe_unsafe)")
    return ap


def main(argv=None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    if args.cmd is None:
        ap.print_help()
        return 2
    targets = list_files(args.classes)
    total = sum(x["size"] for _, _, x in targets)
    print(f"대상 {len(targets)}개, {total / 1e6:.1f} MB ({total / 2**20:.1f} MiB)")
    if args.cmd == "list":
        for split, cls, x in targets:
            print(f"  {split:5s} {cls:36s} {x['filename']:12s} {x['size'] / 1e6:7.1f} MB")
        return 0
    manifest = download(targets, args.dest)
    bad = [m for m in manifest if not (os.path.exists(m["path"]) and os.path.getsize(m["path"]) == m["size"])]
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
