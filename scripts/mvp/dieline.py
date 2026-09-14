#!/usr/bin/env python
"""M1 素材接入与诊断：SVG / PNG / JPG / PDF 接入，折线(折痕)与切线(裁切)候选识别。

能力：
  - SVG：解析 line/path/rect 元素与 stroke-dasharray（虚线=折线候选，实线=切线候选），闭合区域=rect/path Z
  - 位图(PNG/JPG)：numpy 行列投影检测长直线（切线候选）与短线段（折线候选启发式）
  - PDF：检测签名并给出接入状态（未集成栅格化时标注部分支持）
输出：JSON 报告（候选数量、闭合区域、置信度、接入状态）
"""
import argparse
import json
import os
import re
import sys

import numpy as np
from PIL import Image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def parse_svg(path):
    with open(path, encoding="utf-8", errors="ignore") as f:
        s = f.read()
    cut, crease, closed = [], [], []
    for m in re.finditer(r"<(line|path|rect)\b([^>]*)>", s, re.I):
        tag, attrs = m.group(1).lower(), m.group(2)
        dashed = re.search(r"stroke-dasharray\s*[:=]\s*[\"']?\s*([0-9.,\s]+)", attrs, re.I)
        if tag == "rect":
            closed.append(attrs.strip()[:120])
            (crease if dashed else cut).append(attrs.strip()[:120])
        else:
            d = re.search(r'\bd\s*=\s*["\']([^"\']+)["\']', attrs)
            n = 0
            if d:
                n = len(re.findall(r"[MLCZmlcz]", d.group(1))) - 1
            n = max(n, 1)
            (crease if dashed else cut).extend([attrs.strip()[:80]] * n)
    return {"format": "SVG", "cut_candidates": len(cut), "crease_candidates": len(crease),
            "closed_regions": len(closed), "status": "ok"}


def parse_bitmap(path):
    im = Image.open(path).convert("L")
    W = min(im.width, 1200)
    a = np.asarray(im.resize((W, max(1, int(W * im.height / im.width)))), dtype=np.float32)
    dark = a < 200
    # 切线候选：贯穿性长直线（整行/整列暗像素占比 > 80%）
    cut = int((dark.mean(axis=1) > 0.8).sum() + (dark.mean(axis=0) > 0.8).sum())
    # 折线候选：短线段(连续暗像素 4~40)每采样行的中位数
    step = max(1, dark.shape[0] // 120)
    counts = []
    for y in range(0, dark.shape[0], step):
        line = dark[y]; cnt = 0; run = 0
        for v in line:
            if v:
                run += 1
            else:
                if 4 <= run <= 40: cnt += 1
                run = 0
        if 4 <= run <= 40: cnt += 1
        counts.append(cnt)
    crease = int(round(float(np.median(counts)) if counts else 0))
    return {"format": "BITMAP", "cut_candidates": cut, "crease_candidates": crease,
            "closed_regions": 0, "status": "ok(启发式)"}


def parse_pdf(path):
    with open(path, "rb") as f:
        head = f.read(8)
    ok = head.startswith(b"%PDF")
    return {"format": "PDF", "cut_candidates": 0, "crease_candidates": 0, "closed_regions": 0,
            "status": "detected(需栅格化/矢量解析, 部分支持)" if ok else "invalid"}


def analyze(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".svg":
        return parse_svg(path)
    if ext == ".pdf":
        return parse_pdf(path)
    return parse_bitmap(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", help="输出 JSON 报告路径")
    args = ap.parse_args()
    report = analyze(args.input)
    report["file"] = os.path.basename(args.input)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print("[OK] 报告 ->", args.out)


if __name__ == "__main__":
    main()
