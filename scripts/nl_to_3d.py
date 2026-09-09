#!/usr/bin/env python
"""自然语言 → 3D 演示管线：一句话 → 结构化参数 JSON → 自动调用 Blender。

示例:
  python scripts/nl_to_3d.py --text "做一个包装盒 180x45x45 mm" --blender <blender路径>
  python scripts/nl_to_3d.py --text "液压缸 缸筒外径80 长260" --blender <blender路径>
  python scripts/nl_to_3d.py --text "壳体" --demo-only

说明:
- 离线解析器(PARSER=demo)用于可复现演示；真实对话中的理解由大语言模型完成，
  完整 AI 决策实录见 docs/nl_driven_workflow.md。
- 输出 JSON 含 dimension_source 标注：from_drawing / from_nl / ai_default。
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARSER = "demo"  # demo=离线规则；接入真实 LLM 时替换 parse_nl() 即可

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

NUM = r"(\d+(?:\.\d+)?)\s*(?:mm|毫米|厘米|cm)?"


def find_blender():
    exe = os.environ.get("BLENDER_EXE")
    if exe and os.path.exists(exe):
        return exe
    w = shutil.which("blender")
    if w:
        return w
    cands = []
    for base in [r"C:\Program Files\Blender Foundation",
                 r"C:\Program Files (x86)\Blender Foundation",
                 os.path.expandvars(r"%LOCALAPPDATA%\Programs\Blender Foundation")]:
        if os.path.isdir(base):
            for d in glob.glob(os.path.join(base, "Blender*")):
                p = os.path.join(d, "blender.exe")
                if os.path.exists(p):
                    try:
                        ver = tuple(int(x) for x in os.path.basename(d).split()[1].split("."))
                    except Exception:
                        ver = (0,)
                    cands.append((ver, p))
    if cands:
        cands.sort(key=lambda x: x[0])
        return cands[-1][1]
    return None


def parse_nl(text):
    """离线规则解析（演示）。返回 (project, params, notes)"""
    t = text.lower()
    if any(k in t for k in ("液压缸", "油缸", "hydraulic")):
        proj = "hydraulic"
        m = re.search(r"(?:缸筒)?外径\s*" + NUM, t)
        barrel_r = round(float(m.group(1)) / 2, 2) if m else 40.0
        m = re.search(r"长(?:度)?\s*" + NUM + r"|缸筒长" + NUM, t)
        length = float(m.group(1)) if m else 260.0
        return proj, {"barrel_radius_mm": barrel_r, "barrel_length_mm": length}, []
    if any(k in t for k in ("壳体", "外壳", "housing")):
        return "housing", {"note": "阶梯回转壳体，使用脚本默认参数(法兰Ø110/主体Ø80/凸台Ø40/总高66)"}, []
    if any(k in t for k in ("盒", "包装", "箱子", "pack")):
        m = re.search(r"(\d+(?:\.\d+)?)\s*[xX×*]\s*(\d+(?:\.\d+)?)\s*[xX×*]\s*(\d+(?:\.\d+)?)", text)
        if m:
            return "pack", {"width_mm": float(m.group(1)),
                            "depth_mm": float(m.group(2)),
                            "height_mm": float(m.group(3))}, []
        w = re.search(r"长(?:度)?\s*" + NUM, t)
        d = re.search(r"宽(?:度)?\s*" + NUM, t)
        h = re.search(r"高(?:度)?\s*" + NUM, t)
        return "pack", {"width_mm": float(w.group(1)) if w else 180.0,
                        "depth_mm": float(d.group(1)) if d else 45.0,
                        "height_mm": float(h.group(1)) if h else 45.0}, []
    return None, {}, ["未能识别对象类型，请包含：液压缸/壳体/包装盒"]


def build_json(text, proj, params):
    src = {"from_drawing": [], "from_nl": [], "ai_default": []}
    if proj == "hydraulic":
        if "barrel_radius_mm" in params and "外径" in text:
            src["from_nl"].append("缸筒外径")
            src["ai_default"].extend(["法兰Ø110", "活塞杆Ø28伸250", "油口Ø30", "壁厚/内腔"])
        else:
            src["ai_default"] = ["缸筒Ø80×260", "法兰Ø110", "杆Ø28伸250", "油口Ø30"]
    elif proj == "housing":
        src["ai_default"] = ["法兰Ø110×8", "主体Ø80×50", "凸台Ø40×8", "内腔Ø68", "4×Ø8孔", "总高66"]
    elif proj == "pack":
        if "x" in text.lower() or "长" in text:
            src["from_nl"] = ["长×宽×高"]
        else:
            src["ai_default"] = ["180×45×45(演示默认)"]
    return {"text": text, "parser": PARSER, "project": proj, "params_mm": params,
            "dimension_source": src,
            "note": "图纸标注未自动读取(无OCR)；CAD案例尺寸为AI默认+一句话补充，需按图纸核对。见 docs/nl_driven_workflow.md"}


def run_blender(blender, script, extra, out):
    # 统一用 "--" 分隔 Blender 参数与脚本参数，且脚本报错时返回非 0
    cmd = [blender, "--background", "--factory-startup", "--python-exit-code", "1",
           "--python", os.path.join(ROOT, script), "--"]
    if extra:
        cmd += extra
    cmd += ["--out", out]
    log = os.path.join(ROOT, "logs", "nl_%s_%s.log" % (os.path.splitext(os.path.basename(script))[0], os.path.basename(out)))
    os.makedirs(os.path.dirname(log), exist_ok=True)
    with open(log, "w", encoding="utf-8") as f:
        r = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    if r.returncode != 0:
        try:
            with open(log, encoding="utf-8", errors="ignore") as f:
                print("----- " + script + " 日志尾部 -----")
                print("".join(f.readlines()[-15:]))
        except Exception:
            pass
    return r.returncode


def main():
    ap = argparse.ArgumentParser(description="自然语言→3D 演示")
    ap.add_argument("--text", required=True, help='一句话，如 "包装盒 180x45x45mm"')
    ap.add_argument("--blender", help="Blender 可执行文件路径")
    ap.add_argument("--demo-only", action="store_true", help="只输出解析 JSON，不调用 Blender")
    args = ap.parse_args()

    blender = args.blender or find_blender()
    proj, params, notes = parse_nl(args.text)
    if proj is None:
        print("解析失败:", "; ".join(notes)); sys.exit(2)
    data = build_json(args.text, proj, params)
    os.makedirs(os.path.join(ROOT, "output"), exist_ok=True)
    jpath = os.path.join(ROOT, "output", "nl_%s.json" % proj)
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print("JSON ->", jpath)

    if args.demo_only:
        return
    if not blender:
        print("未找到 Blender，请 --blender 指定"); sys.exit(2)
    if proj == "pack":
        w, d, h = params["width_mm"], params["depth_mm"], params["height_mm"]
        run_blender(blender, "scripts/build_pack.py",
                    ["--front", os.path.join("assets", "front.png"),
                     "--width", str(w), "--depth", str(d), "--height", str(h)],
                    os.path.join(ROOT, "output", "nl_pack"))
        run_blender(blender, "scripts/render_glb.py",
                    ["--glb", os.path.join(ROOT, "output", "nl_pack.glb"), "--res", "800"],
                    os.path.join(ROOT, "output", "nl_pack"))
    else:
        run_blender(blender, "scripts/build_" + proj + ".py", [], os.path.join(ROOT, "output", "nl_" + proj))
        run_blender(blender, "scripts/render_glb.py",
                    ["--glb", os.path.join(ROOT, "output", "nl_" + proj + ".glb"), "--res", "800"],
                    os.path.join(ROOT, "output", "nl_" + proj))
    print("[OK] 已完成 NL->Blender 闭环，产物在 output/nl_%s*" % proj)


if __name__ == "__main__":
    main()
