#!/usr/bin/env python
"""M6 局部编辑与 Diff：场景级变更对比（对象/结构/材质/灯光/相机/输出）。

提供：diff_scenes(a,b) -> 变更列表 + 摘要；make_compare(before_png, after_png, out) 前后对比图。
"""
import json


def _walk(a, b, path=""):
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            out += _walk(a.get(k), b.get(k), path + "." + k if path else k)
    elif a != b:
        out.append((path, a, b))
    return out


def categorize(path):
    if path.startswith("structure"):
        return "结构/对象"
    if path.startswith("material"):
        return "材质"
    if path.startswith("lighting"):
        return "灯光"
    if path.startswith("camera"):
        return "相机"
    if path.startswith("output"):
        return "输出"
    return "其他"


def diff_scenes(a, b):
    changes = _walk(a, b)
    items = [{"path": p, "category": categorize(p), "before": x, "after": y}
             for p, x, y in changes]
    summary = {}
    for it in items:
        summary[it["category"]] = summary.get(it["category"], 0) + 1
    return items, summary


def summarize_text(items):
    if not items:
        return "无变更"
    lines = []
    for it in items:
        lines.append("[%s] %s: %s -> %s" % (it["category"], it["path"], it["before"], it["after"]))
    return "\n".join(lines)


def compare_scenes(a_json, b_json, out_json):
    with open(a_json, encoding="utf-8") as f:
        a = json.load(f)
    with open(b_json, encoding="utf-8") as f:
        b = json.load(f)
    items, summary = diff_scenes(a, b)
    text = summarize_text(items)
    result = {"changes": items, "summary": summary, "text": text}
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return result


def make_compare(before_png, after_png, out_png):
    """拼前后对比图（左=修改前，右=修改后）。"""
    from PIL import Image, ImageDraw
    a = Image.open(before_png).convert("RGB")
    b = Image.open(after_png).convert("RGB")
    h = min(a.height, b.height, 900)
    a = a.resize((int(a.width * h / a.height), h))
    b = b.resize((int(b.width * h / b.height), h))
    canvas = Image.new("RGB", (a.width + b.width + 12, h + 34), (24, 24, 28))
    canvas.paste(a, (0, 34)); canvas.paste(b, (a.width + 12, 34))
    d = ImageDraw.Draw(canvas)
    d.text((8, 8), "BEFORE", fill=(230, 230, 230))
    d.text((a.width + 20, 8), "AFTER", fill=(120, 255, 160))
    canvas.save(out_png)
    return out_png
