#!/usr/bin/env python
"""折影 Folda MVP 端到端 CLI。

一句话 + 可选素材 -> 场景 JSON -> 受约束生成 -> 渲染 -> Diff -> 版本 -> 项目包导出。

运行：
  python scripts/mvp/cli.py --text "反向插扣盒，哑光纸，暖色晨光，45度，4:5，导出 GLB 和项目包" \
      --asset assets/front.png --name demo --blender <blender路径> --quick
"""
import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts", "mvp"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from schema import validate                         # noqa: E402
from nl_parser import parse                          # noqa: E402
from sandbox import scan_script_text, safe_path      # noqa: E402
from dieline import analyze as dieline_analyze       # noqa: E402
from diff_engine import summarize_text              # noqa: E402
from version_store import VersionStore               # noqa: E402
from exporter import export_package                  # noqa: E402
from blender_utils import find_blender               # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def run_blender(blender, script, extra, log_name):
    cmd = [blender, "--background", "--factory-startup", "--python-exit-code", "1",
           "--python", os.path.join(ROOT, script), "--"] + extra
    log = os.path.join(ROOT, "logs", "mvp_%s.log" % log_name)
    os.makedirs(os.path.dirname(log), exist_ok=True)
    with open(log, "w", encoding="utf-8") as f:
        r = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    if r.returncode != 0:
        with open(log, encoding="utf-8", errors="ignore") as f:
            print("----- %s 失败日志尾部 -----" % script)
            print("".join(f.readlines()[-15:]))
    return r.returncode == 0


def main():
    ap = argparse.ArgumentParser(description="Folda MVP 端到端")
    ap.add_argument("--text", required=True)
    ap.add_argument("--asset", help="二维素材(PNG/JPG/SVG/PDF)")
    ap.add_argument("--name", default="demo")
    ap.add_argument("--blender")
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()

    blender = args.blender or find_blender()
    if not blender:
        print("未找到 Blender"); sys.exit(2)

    outdir = os.path.join(ROOT, "output", "mvp_cli")
    os.makedirs(outdir, exist_ok=True)
    version = VersionStore(os.path.join(ROOT, "output", "mvp_versions"))

    print("=== 1) 自然语言 -> 场景 JSON ===")
    scene, notes = parse(args.text)
    ok, errs = validate(scene)
    print("解析:", "; ".join(notes))
    print("场景校验:", "通过" if ok else errs)
    if not ok:
        sys.exit(1)

    # 安全扫描（受约束：生成过程不执行任意代码/不访问网络）
    hits = scan_script_text(json.dumps(scene, ensure_ascii=False))
    print("安全扫描:", "通过（无危险模式）" if not hits else hits)

    prev = version.restore(version.list()[-1]) if version.list() else None
    scene_path = os.path.join(outdir, args.name + ".scene.json")
    with open(scene_path, "w", encoding="utf-8") as f:
        json.dump(scene, f, ensure_ascii=False, indent=2)
    print("场景文件 ->", scene_path)

    if args.asset:
        print("=== 2) 素材接入与诊断 ===")
        rep = dieline_analyze(safe_path(args.asset))
        print("素材诊断:", json.dumps(rep, ensure_ascii=False))
        with open(os.path.join(outdir, args.name + ".dieline.json"), "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=2)

    print("=== 3) 生成结构（受约束模板）===")
    model = os.path.join(outdir, args.name + "_model")
    good = run_blender(blender, "scripts/mvp/packaging.py",
                       ["--scene-json", scene_path, "--out", model], "build")
    if not good:
        print("[降级] 生成失败，回退到 tuck_box_std 模板重试")
        scene["structure"]["template"] = "tuck_box_std"
        with open(scene_path, "w", encoding="utf-8") as f:
            json.dump(scene, f, ensure_ascii=False, indent=2)
        good = run_blender(blender, "scripts/mvp/packaging.py",
                           ["--scene-json", scene_path, "--out", model], "build_fallback")
        if not good:
            sys.exit(1)

    print("=== 4) 渲染（预设灯光/镜头/画幅）===")
    render_dir = os.path.join(outdir, args.name + "_render")
    rextra = ["--scene-json", scene_path, "--model", model + ".glb", "--outdir", render_dir]
    if args.quick:
        rextra.append("--quick")
    if not run_blender(blender, "scripts/mvp/render_mvp.py", rextra, "render"):
        print("[错误] 渲染失败，请查看 logs/mvp_render.log")
        sys.exit(1)

    print("=== 5) Diff（相对上一版本）===")
    if prev:
        diff_out = os.path.join(outdir, args.name + ".diff.json")
        from diff_engine import diff_scenes
        items, summary = diff_scenes(prev, scene)
        with open(diff_out, "w", encoding="utf-8") as f:
            json.dump({"changes": items, "summary": summary, "text": summarize_text(items)},
                      f, ensure_ascii=False, indent=2)
        print("变更摘要:", summarize_text(items) or "无变更")
    else:
        print("首个版本，无对比基线")

    print("=== 6) 保存版本 ===")
    files = [model + ".glb", model + ".blend"]
    if os.path.isdir(render_dir):
        files += [os.path.join(render_dir, x) for x in os.listdir(render_dir)]
    vdir = version.save(args.name, scene, extra_files=files)
    print("版本目录:", vdir, "| 历史版本:", version.list())

    print("=== 7) 导出项目包 ===")
    zip_path = os.path.join(outdir, args.name + "_package.zip")
    good, info = export_package(scene, files + [scene_path], zip_path, name=args.name)
    print("项目包:", "OK -> " + info if good else "失败 " + info)

    print("\n=== 完成 ===")
    print("产物目录:", outdir)
    sys.exit(0 if good else 1)


if __name__ == "__main__":
    main()
