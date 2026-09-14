#!/usr/bin/env python
"""M1 素材诊断：OCR 文字识别 + 主视觉识别 + 透明区检测 + 品牌锁定建议。

OCR：Windows.Media.Ocr（系统自带，零依赖，支持 zh-Hans-CN）
主视觉：边缘背景色估计 + 前景色距 + 最大连通域（纯 numpy 实现）
输出：JSON 报告（文字区域/主视觉 bbox/透明比例/锁定建议）
"""
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OCR_PS1 = os.path.join(ROOT, "scripts", "mvp", "win_ocr.ps1")
POWERSHELL = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                          "System32", "WindowsPowerShell", "v1.0", "powershell.exe")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def ocr_text(path, lang="zh-Hans-CN"):
    """调用 Windows 自带 OCR 识别文字，返回 {available, text, lines}。"""
    if not os.path.exists(POWERSHELL) or not os.path.exists(OCR_PS1):
        return {"available": False, "error": "windows ocr 不可用", "text": "", "lines": []}
    try:
        r = subprocess.run([POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass",
                            "-File", OCR_PS1, "-ImagePath", path, "-Lang", lang],
                           capture_output=True, timeout=90)
        out = r.stdout.decode("utf-8", errors="replace")
        start = out.find("{")
        data = json.loads(out[start:]) if start >= 0 else {}
        return {"available": True, "text": data.get("text", ""), "lines": data.get("lines", [])}
    except Exception as e:  # noqa: BLE001
        return {"available": False, "error": str(e), "text": "", "lines": []}


def classify(img):
    """判定素材类型：artwork(白底彩色设计稿) / dieline(线条刀模) / unknown。"""
    a = np.asarray(img.convert("RGB"), dtype=np.float32)
    edge = np.concatenate([a[:5].reshape(-1, 3), a[-5:].reshape(-1, 3),
                           a[:, :5].reshape(-1, 3), a[:, -5:].reshape(-1, 3)])
    bg = np.median(edge, axis=0)
    white = (a > 240).all(-1)
    fg = ~white
    mx = a.max(-1); mn = a.min(-1)
    sat = (mx - mn) / np.maximum(mx, 1e-6)
    sat_fg = float(sat[fg].mean()) if fg.any() else 0.0
    bg_white = bool((bg > 230).all())
    if bg_white and fg.mean() < 0.80 and sat_fg > 0.15:
        kind = "artwork"
    elif fg.mean() < 0.25 and sat_fg < 0.15:
        kind = "dieline"
    else:
        kind = "unknown"
    return {"asset_type": kind, "background_rgb": [int(v) for v in bg],
            "nonwhite_ratio": round(float(fg.mean()), 4),
            "fg_saturation": round(sat_fg, 3)}


def extract_artwork(img, out_path, white_thr=240, margin=2):
    """裁出白底设计稿中的有效彩色区域（去掉外围白板）。"""
    a = np.asarray(img.convert("RGB"))
    fg = ~(a > white_thr).all(-1)
    if not fg.any():
        return None
    ys, xs = np.where(fg)
    x0 = max(0, int(xs.min()) - margin); x1 = min(a.shape[1] - 1, int(xs.max()) + margin)
    y0 = max(0, int(ys.min()) - margin); y1 = min(a.shape[0] - 1, int(ys.max()) + margin)
    crop = img.convert("RGB").crop((x0, y0, x1 + 1, y1 + 1))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    crop.save(out_path)
    return {"extracted": out_path, "bbox": [x0, y0, x1, y1], "size": list(crop.size)}


def transparency(img):
    if img.mode in ("RGBA", "LA"):
        alpha = np.asarray(img.getchannel("A"))
        return {"alpha_available": True, "transparent_ratio": round(float((alpha < 250).mean()), 4)}
    return {"alpha_available": False, "transparent_ratio": None,
            "note": "无 Alpha 通道（未检出透明区）"}


def main_visual(img, max_side=280, thr=45.0):
    """背景估计 + 最大连通域 -> 主视觉 bbox 与占比。"""
    im = img.convert("RGB")
    scale = max_side / max(im.size)
    sm = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))))
    a = np.asarray(sm, dtype=np.float32)
    edge = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]], axis=0)
    bg = np.median(edge, axis=0)
    dist = np.sqrt(((a - bg) ** 2).sum(-1))
    mask = dist > thr
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    best_area, best_box = 0, None
    for y in range(h):
        for x in range(w):
            if not mask[y, x] or seen[y, x]:
                continue
            stack = [(y, x)]; seen[y, x] = True; area = 0
            miny = maxy = y; minx = maxx = x
            while stack:
                cy, cx = stack.pop(); area += 1
                miny = min(miny, cy); maxy = max(maxy, cy)
                minx = min(minx, cx); maxx = max(maxx, cx)
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True; stack.append((ny, nx))
            if area > best_area:
                best_area, best_box = area, (minx, miny, maxx, maxy)
    if best_box is None:
        return {"found": False}
    inv = 1.0 / scale
    x0, y0, x1, y1 = best_box
    return {"found": True, "ratio": round(best_area / float(mask.size), 4),
            "bbox": [int(x0 * inv), int(y0 * inv), int((x1 + 1) * inv), int((y1 + 1) * inv)]}


def analyze(path, lang="zh-Hans-CN"):
    ext = os.path.splitext(path)[1].lower()
    ocr_path = path
    if ext == ".pdf":
        import tempfile
        from pdf2image import convert_from_path
        pages = convert_from_path(path, dpi=150, first_page=1, last_page=1)
        ocr_path = os.path.join(tempfile.gettempdir(), "folda_vision_page1.png")
        pages[0].save(ocr_path)
    try:
        img = Image.open(ocr_path)
    except Exception as e:  # noqa: BLE001
        return {"file": os.path.basename(path), "supported": False,
                "reason": "该格式(%s)无法直接做像素分析，需先栅格化：%s" % (ext, e),
                "ocr": {"available": False, "text": "", "lines": []},
                "transparency": {"alpha_available": False, "transparent_ratio": None},
                "main_visual": {"found": False}, "lock_regions": []}
    report = {"file": os.path.basename(path), "size": list(img.size), "source_ext": ext}
    report["asset_class"] = classify(img)
    if report["asset_class"]["asset_type"] == "artwork":
        art_png = os.path.join(ROOT, "output", os.path.splitext(os.path.basename(path))[0] + "_artwork.png")
        art = extract_artwork(img, art_png)
        if art:
            report["artwork"] = art
    ocr = ocr_text(ocr_path, lang)
    report["ocr"] = ocr
    report["transparency"] = transparency(img)
    report["main_visual"] = main_visual(img)
    locks = []
    for ln in ocr.get("lines", []):
        if ln.get("words"):
            xs = [w["x"] for w in ln["words"]]; ys = [w["y"] for w in ln["words"]]
            xe = [w["x"] + w["w"] for w in ln["words"]]; ye = [w["y"] + w["h"] for w in ln["words"]]
            locks.append({"type": "text", "text": ln.get("text", ""),
                          "bbox": [min(xs), min(ys), max(xe), max(ye)], "lock": True})
    if report["main_visual"].get("found"):
        locks.append({"type": "main_visual", "bbox": report["main_visual"]["bbox"], "lock": True})
    report["lock_regions"] = locks
    return report


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", help="输出 JSON 报告路径")
    ap.add_argument("--no-ocr", action="store_true")
    args = ap.parse_args()
    if args.no_ocr:
        img = Image.open(args.input)
        rep = {"file": os.path.basename(args.input), "size": list(img.size),
               "transparency": transparency(img), "main_visual": main_visual(img), "ocr": {"available": False}}
    else:
        rep = analyze(args.input)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=2)
        print("[OK] 报告 ->", args.out)


if __name__ == "__main__":
    main()
