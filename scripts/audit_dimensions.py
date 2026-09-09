#!/usr/bin/env python
"""尺寸来源审计：明确说明模型每个尺寸的来源(图纸/一句话/AI默认)。

用法:
  python scripts/audit_dimensions.py --project hydraulic
  python scripts/audit_dimensions.py --project housing
  python scripts/audit_dimensions.py --project hydraulic --md   # 输出 Markdown 报告

说明:
  - from_drawing : 程序从二维图自动读取的尺寸（当前未集成 OCR/图纸解析 => 恒为空）
  - from_nl      : 来自用户一句话/人工补充（自动合并 output/nl_modify_record.json）
  - ai_default   : AI 按典型结构假设的默认值，需人工核对图纸
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 各模型：常量 -> (中文名, 显示口径函数/备注)
HYDRAULIC = [
    ("BARREL_R", "缸筒外径", lambda r: round(2 * r, 1), "Ø80"),
    ("BARREL_Z0/BARREL_Z1", "缸筒长度", lambda v: round(v[1] - v[0], 1), "260"),
    ("CAP_R", "法兰外径", lambda r: round(2 * r, 1), "Ø110"),
    ("ROD_R", "活塞杆直径", lambda r: round(2 * r, 1), "Ø28"),
    ("ROD_Z1-ROD_Z0", "活塞杆伸出长度", lambda v: round(v[1] - v[0], 1), "250"),
    ("PORT_R", "油口直径", lambda r: round(2 * r, 1), "Ø30"),
]
HOUSING = [
    ("flange", "法兰(底)外径/厚度", None, "Ø110 × 8"),
    ("body", "主体外径/高度", None, "Ø80 × 50"),
    ("boss", "顶部凸台外径/高度", None, "Ø40 × 8"),
    ("cavity", "内腔直径", None, "Ø68(壁厚约6)"),
    ("hole", "顶部中心通孔", None, "Ø20"),
    ("mount", "法兰安装孔", None, "4×Ø8(r=45)"),
    ("total", "总高", None, "66"),
]


def read_hydraulic_consts():
    """从 build_hydraulic.py 顶部读常量实际值，避免手写漂移。"""
    path = os.path.join(ROOT, "scripts", "build_hydraulic.py")
    with open(path, encoding="utf-8") as f:
        src = f.read().replace("\r\n", "\n")
    consts = {}
    # 支持同行多常量:  BARREL_Z0, BARREL_Z1 = -130.0, 130.0
    for m in re.finditer(r"^([A-Z_0-9]+(?:,\s*[A-Z_0-9]+)*)\s*=\s*([-0-9.,\s]+)$", src, re.M):
        names = [x.strip() for x in m.group(1).split(",")]
        vals = [float(x.strip()) for x in m.group(2).split(",")]
        for n, v in zip(names, vals):
            consts[n] = v
    return consts


def merge_from_nl():
    """合并用户一句话里改过的尺寸 -> {常量名: 值}。"""
    p = os.path.join(ROOT, "output", "nl_modify_record.json")
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        rec = json.load(f)
    return rec.get("changes", {})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True, choices=["hydraulic", "housing"])
    ap.add_argument("--md", action="store_true", help="输出 Markdown 报告到 output/")
    args = ap.parse_args()

    nl_changes = merge_from_nl()
    from_drawing = []
    from_nl = []
    ai_default = []
    rows = []

    if args.project == "hydraulic":
        c = read_hydraulic_consts()
        # 用户一句话覆盖过的常量，用覆盖值作为当前生效值
        c.update({k: v for k, v in nl_changes.items() if k in c})
        for key, name, fmt, _default in HYDRAULIC:
            if key == "BARREL_Z0/BARREL_Z1":
                val = fmt([c["BARREL_Z0"], c["BARREL_Z1"]])
            elif key == "ROD_Z1-ROD_Z0":
                val = fmt([c["ROD_Z0"], c["ROD_Z1"]])
            else:
                val = fmt(c[key])
            const_note = key
            src = "from_nl" if const_note.split("/")[0] in nl_changes else "ai_default"
            unit = "mm"
            note = "用户一句话覆盖" if src == "from_nl" else "AI 典型默认，需核对图纸"
            if src == "from_nl":
                from_nl.append({"name": name, "value_mm": val, "constant": const_note, "note": note})
            else:
                ai_default.append({"name": name, "value_mm": val, "constant": const_note, "note": note})
            rows.append((name, val, unit, src, note))
    else:
        for key, name, _fmt, dflt in HOUSING:
            src = "ai_default"
            ai_default.append({"name": name, "value": dflt, "note": "AI 典型默认(硬编码于脚本)，需核对图纸"})
            rows.append((name, dflt, "mm", src, "AI 典型默认(硬编码)，需核对图纸"))

    summary = {
        "project": args.project,
        "from_drawing": from_drawing,
        "from_nl": from_nl,
        "ai_default": ai_default,
        "note": "from_drawing 恒为空：当前未集成 CAD 标注 OCR/图纸解析（待实现），见 docs/nl_driven_workflow.md",
    }
    print("=" * 70)
    print("尺寸来源审计: %s" % args.project)
    print("=" * 70)
    for name, val, unit, src, note in rows:
        print("%-14s %-10s %-11s %s" % (name, str(val) + unit, src, note))
    print("-" * 70)
    print("图纸来源(from_drawing): 无（未集成标注OCR）")
    print("一句话来源(from_nl)     : %d 项" % len(from_nl))
    print("AI默认(ai_default)      : %d 项" % len(ai_default))
    print("说明: %s" % summary["note"])

    if args.md:
        os.makedirs(os.path.join(ROOT, "output"), exist_ok=True)
        out = os.path.join(ROOT, "output", "dimension_audit_%s.md" % args.project)
        lines = ["# 尺寸来源审计：%s\n" % args.project, "| 尺寸 | 数值 | 来源 | 说明 |", "|---|---|---|---|"]
        for name, val, unit, src, note in rows:
            lines.append("| %s | %s%s | **%s** | %s |" % (name, val, unit, src, note))
        lines.append("\n> %s" % summary["note"])
        with open(out, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print("\n[OK] Markdown 报告 ->", out)


if __name__ == "__main__":
    main()
