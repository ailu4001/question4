#!/usr/bin/env python
"""NL → 脚本修改 → Blender 执行 引擎（程序设计能力演示）。

核心：一句话里的尺寸 → 参数 JSON → 自动修改 Blender 建模脚本（常量级）→ 运行修改版 → 出图。
与 nl_to_3d.py（参数化调用）不同，本工具真正"修改脚本文件"，并保留修改证据(diff)。

示例:
  python scripts/nl_modify_script.py --text "液压缸 缸筒外径100 法兰直径130 活塞杆直径36"
  python scripts/nl_modify_script.py --text "液压缸 缸筒外径90 油口直径40" --dry-run

说明:
  - 目前对象=液压缸(build_hydraulic.py)。可被一句话修改的"独立尺寸"见 SCHEMA；
  - 长度/位置类参数(缸长、各段Z坐标)相互耦合，属于"AI改脚本难点"，此处演示仅支持直径类；
  - 真实流程中由 LLM 决定改哪些常量/如何联动（见 docs/nl_driven_workflow.md）。
"""
import argparse
import json
import os
import re
import subprocess
import sys

from blender_utils import find_blender

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_SRC = os.path.join(ROOT, "scripts", "build_hydraulic.py")
OUT_DIR = os.path.join(ROOT, "output", "nl_scripts")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 对象可被一句话修改的尺寸 schema: 中文关键词 -> (常量名, 直径转半径?)
SCHEMA = {
    "缸筒外径": ("BARREL_R", True),
    "缸径": ("BARREL_R", True),
    "法兰直径": ("CAP_R", True),
    "活塞杆直径": ("ROD_R", True),
    "杆径": ("ROD_R", True),
    "油口直径": ("PORT_R", True),
}


def parse_changes(text):
    """从一句话提取尺寸修改。返回 {常量名: 数值(mm)} 与说明。"""
    changes = {}
    notes = []
    for kw, (const, div2) in SCHEMA.items():
        # 匹配 "关键词 + 数字(+单位)"
        m = re.search(kw + r"\s*[:：]?\s*(\d+(?:\.\d+)?)\s*(?:mm|毫米)?", text)
        if m:
            val = float(m.group(1)) / 2 if div2 else float(m.group(1))
            changes[const] = round(val, 2)
            notes.append("%s %smm -> %s=%s(半径)" % (kw, m.group(1), const, changes[const]) if div2 else
                         "%s %smm -> %s=%s" % (kw, m.group(1), const, changes[const]))
    return changes, notes


def modify_script(changes):
    """读取原脚本，把命中的常量行替换为新值，写修改版副本。返回(副本路径, diff行列表)。"""
    with open(SCRIPT_SRC, encoding="utf-8") as f:
        lines = f.read().replace("\r\n", "\n").split("\n")
    out_lines = []
    diff = []
    for ln in lines:
        matched = None
        for const, val in changes.items():
            if re.match(r"^\s*" + const + r"\s*=\s*[0-9.]+", ln):
                new_ln = re.sub(r"^(?P<pre>\s*" + const + r"\s*=\s*)[0-9.]+",
                                lambda m: m.group("pre") + repr(val), ln)
                diff.append("- " + ln.strip())
                diff.append("+ " + new_ln.strip())
                matched = new_ln
                break
        out_lines.append(matched if matched is not None else ln)
    os.makedirs(OUT_DIR, exist_ok=True)
    copy_path = os.path.join(OUT_DIR, "build_hydraulic_nl.py")
    with open(copy_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out_lines))
    return copy_path, diff


def run_blender(blender, script, out, extra=None):
    cmd = [blender, "--background", "--factory-startup", "--python-exit-code", "1",
           "--python", script, "--"]
    if extra:
        cmd += extra
    cmd += ["--out", out]
    log = os.path.join(ROOT, "logs", "nlmod_%s.log" % os.path.basename(out))
    os.makedirs(os.path.dirname(log), exist_ok=True)
    with open(log, "w", encoding="utf-8") as f:
        r = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    if r.returncode != 0:
        with open(log, encoding="utf-8", errors="ignore") as f:
            print("".join(f.readlines()[-15:]))
    return r.returncode


def main():
    ap = argparse.ArgumentParser(description="NL→脚本修改→Blender 引擎")
    ap.add_argument("--text", required=True, help='一句话，如 "液压缸 缸筒外径100 法兰直径130"')
    ap.add_argument("--blender", help="Blender 路径")
    ap.add_argument("--dry-run", action="store_true", help="只生成脚本副本与 diff，不运行 Blender")
    args = ap.parse_args()

    changes, notes = parse_changes(args.text)
    if not changes:
        print("未从句中识别到可修改尺寸。支持的词:", " / ".join(SCHEMA))
        sys.exit(2)
    copy_path, diff = modify_script(changes)

    record = {
        "text": args.text,
        "object": "hydraulic (build_hydraulic.py)",
        "changes": changes,
        "notes": notes,
        "modified_script": copy_path,
        "diff": diff,
    }
    os.makedirs(os.path.join(ROOT, "output"), exist_ok=True)
    jpath = os.path.join(ROOT, "output", "nl_modify_record.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    print(json.dumps(record, ensure_ascii=False, indent=2))
    print("\n[INFO] 修改版脚本 ->", copy_path)
    if args.dry_run:
        print("[DRY-RUN] 未调用 Blender。")
        return
    blender = args.blender or find_blender()
    if not blender:
        print("未找到 Blender"); sys.exit(2)
    print("\n[STEP] 用修改版脚本运行 Blender 建模...")
    out = os.path.join(ROOT, "output", "nl_modified_hydraulic")
    if run_blender(blender, copy_path, out) != 0:
        sys.exit(1)
    print("[STEP] 渲染多视角...")
    run_blender(blender, os.path.join(ROOT, "scripts", "render_glb.py"), out,
                extra=["--glb", out + ".glb", "--res", "800"])
    print("[OK] 完成：修改后模型 ->", out + ".glb")


if __name__ == "__main__":
    main()
