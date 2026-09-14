#!/usr/bin/env python
"""MVP 批量指标测试基准：把产品方案的量化验收标准变成实测数据。

覆盖：
  1) 局部编辑准确率（指令只影响目标类别，目标 >=80%）
  2) 导出成功率（>=98%）
  3) 素材接入进入编辑态比例（>=90%）
  4) 端到端完成率（>=80%）与首次预览耗时（<=3 分钟）
输出：output/mvp_benchmark.json + 控制台表格；全部达标返回 0。
"""
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "mvp"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from schema import default_scene                      # noqa: E402
from nl_parser import parse                           # noqa: E402
from diff_engine import diff_scenes                   # noqa: E402
from dieline import analyze as dieline_analyze        # noqa: E402
from exporter import export_package                   # noqa: E402
from blender_utils import find_blender                # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---- 1) 局部编辑：单意图指令 -> 期望只改动指定类别 ----
EDIT_CASES = [
    ("把材质换成亮面覆膜", "材质"),
    ("材质改成烫金", "材质"),
    ("换成未涂布纸", "材质"),
    ("用透明材质", "材质"),
    ("灯光换成冷色蓝调", "灯光"),
    ("改成暖色晨光", "灯光"),
    ("导出 JPG 和 PNG", "输出"),
    ("镜头拉近一点", "相机"),
    ("改成俯视角度", "相机"),
    ("用正面展示", "相机"),
    ("改成 16:9", "输出"),
    ("输出改成 1:1 画幅", "输出"),
    ("输出 4K 分辨率", "输出"),
    ("导出 GLB 和 BLEND", "输出"),
    ("换成套盒", "结构/对象"),
    ("模板改成立式拉链袋", "结构/对象"),
    ("换成开窗套盒", "结构/对象"),
    ("改成带挂孔的插扣盒", "结构/对象"),
    ("尺寸改为 200x100x300 mm", "结构/对象"),
    ("纸厚改成 0.6mm", "结构/对象"),
    ("不要锁定文字和 Logo", "其他"),
]


def bench_edit():
    ok = 0
    details = []
    for text, target in EDIT_CASES:
        sc, _ = parse(text, default_scene())
        items, _ = diff_scenes(default_scene(), sc)
        cats = {it["category"] for it in items}
        good = bool(items) and cats == {target} if target != "其他" else bool(items)
        ok += 1 if good else 0
        details.append({"text": text, "target": target, "actual_categories": sorted(cats),
                        "pass": good})
    return ok, len(EDIT_CASES), details


# ---- 2) 导出成功率 ----
def bench_export(n=30):
    files = [os.path.join(ROOT, "assets", "front.png")]
    for extra in (os.path.join(ROOT, "tests", "mvp_vision_cases", "text_mainvisual.png"),
                  os.path.join(ROOT, "output", "mvp_cli", "demo.scene.json")):
        if os.path.exists(extra):
            files.append(extra)
    outdir = os.path.join(ROOT, "output", "bench_export")
    os.makedirs(outdir, exist_ok=True)
    scene = default_scene()
    ok = 0
    for i in range(n):
        z = os.path.join(outdir, "pkg_%02d.zip" % i)
        good, _ = export_package(scene, files, z)
        ok += 1 if good else 0
    return ok, n


# ---- 3) 素材接入率 ----
def bench_assets():
    dirs = [("tests/mvp_dieline_cases", ".svg"), ("tests/mvp_pdf_cases", ".pdf"),
            ("tests/mvp_vision_cases", ".png")]
    files = []
    for d, ext in dirs:
        p = os.path.join(ROOT, d)
        if os.path.isdir(p):
            files += [os.path.join(p, f) for f in os.listdir(p) if f.endswith(ext)]
    for f in ("cad_8191871.jpg", "cad2_kAmpQGMUEd7t9Zok.jpg"):
        fp = os.path.join(ROOT, "assets", f)
        if os.path.exists(fp):
            files.append(fp)
    ok = 0
    details = []
    for f in files:
        r = dieline_analyze(f)
        good = str(r.get("status", "")).startswith("ok")
        ok += 1 if good else 0
        details.append({"file": os.path.basename(f), "status": r.get("status"), "pass": good})
    return ok, len(files), details


# ---- 4) 端到端完成率 + 首次预览耗时 ----
def bench_e2e(blender, n=3):
    outdir = os.path.join(ROOT, "output", "bench_e2e")
    os.makedirs(outdir, exist_ok=True)
    cases = ["反向插扣盒，哑光纸，暖色晨光，45度，4:5",
             "立式袋，亮面覆膜，冷色蓝调，正面，1:1",
             "套盒，烫金，柔光棚拍，俯视，16:9"]
    ok = 0
    times = []
    for i in range(min(n, len(cases))):
        t0 = time.time()
        cmd = [sys.executable, os.path.join(ROOT, "scripts", "mvp", "cli.py"),
               "--text", cases[i], "--name", "bench_%d" % i, "--quick", "--blender", blender]
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True)
        dt = time.time() - t0
        times.append(round(dt, 1))
        good = r.returncode == 0 and os.path.exists(
            os.path.join(ROOT, "output", "mvp_cli", "bench_%d_model.glb" % i))
        ok += 1 if good else 0
    return ok, min(n, len(cases)), times


def main():
    results = {}
    print("=" * 72)
    print("Folda MVP 批量指标测试")
    print("=" * 72)

    ok, total, details = bench_edit()
    rate = ok / total * 100
    results["local_edit"] = {"pass": ok, "total": total, "rate": round(rate, 1),
                             "target": 80, "details": details}
    print("[1] 局部编辑准确率: %d/%d = %.1f%% (目标 >=80%%) -> %s"
          % (ok, total, rate, "达标" if rate >= 80 else "未达标"))
    for d in details:
        if not d["pass"]:
            print("    未达标: %s -> 实际类别 %s (期望 %s)" % (d["text"], d["actual_categories"], d["target"]))

    ok2, total2 = bench_export()
    rate2 = ok2 / total2 * 100
    results["export"] = {"pass": ok2, "total": total2, "rate": round(rate2, 1), "target": 98}
    print("[2] 导出成功率: %d/%d = %.1f%% (目标 >=98%%) -> %s"
          % (ok2, total2, rate2, "达标" if rate2 >= 98 else "未达标"))

    ok3, total3, det3 = bench_assets()
    rate3 = ok3 / total3 * 100 if total3 else 0
    results["asset_intake"] = {"pass": ok3, "total": total3, "rate": round(rate3, 1), "target": 90,
                               "details": det3}
    print("[3] 素材接入率: %d/%d = %.1f%% (目标 >=90%%) -> %s"
          % (ok3, total3, rate3, "达标" if rate3 >= 90 else "未达标"))

    blender = find_blender()
    if blender:
        ok4, total4, times = bench_e2e(blender)
        rate4 = ok4 / total4 * 100
        results["e2e"] = {"pass": ok4, "total": total4, "rate": round(rate4, 1),
                          "target": 80, "times_sec": times}
        print("[4] 端到端完成率: %d/%d = %.1f%% (目标 >=80%%) -> %s"
              % (ok4, total4, rate4, "达标" if rate4 >= 80 else "未达标"))
        print("    首次预览耗时: %s 秒 (目标 <=180 秒) -> %s"
              % (times[0] if times else "N/A", "达标" if times and times[0] <= 180 else "未达标"))
    else:
        print("[4] 跳过：未找到 Blender")

    out = os.path.join(ROOT, "output", "mvp_benchmark.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("-" * 72)
    print("报告 ->", out)
    all_ok = rate >= 80 and rate2 >= 98 and rate3 >= 90
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
