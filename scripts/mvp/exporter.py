#!/usr/bin/env python
"""M7 导出：项目包（zip：场景 JSON + GLB + BLEND + 渲染图 + 说明），并统计导出成功率。"""
import json
import os
import zipfile


def export_package(scene, files, out_zip, name="folda_package"):
    os.makedirs(os.path.dirname(os.path.abspath(out_zip)), exist_ok=True)
    manifest = {"name": name, "scene": scene, "files": [os.path.basename(f) for f in files if os.path.exists(f)]}
    try:
        with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
            for p in files:
                if os.path.exists(p):
                    z.write(p, arcname=os.path.basename(p))
            z.writestr("scene.json", json.dumps(scene, ensure_ascii=False, indent=2))
            z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            z.writestr("README.txt", "折影 Folda 项目包：scene.json（场景事实源）+ 模型 + 渲染图。")
        return True, out_zip
    except Exception as e:
        return False, str(e)


def export_batch(scene, file_sets, outdir):
    """批量导出多个项目包，返回成功率。"""
    ok = 0
    results = []
    for i, files in enumerate(file_sets):
        z = os.path.join(outdir, "package_%02d.zip" % (i + 1))
        good, info = export_package(scene, files, z)
        ok += 1 if good else 0
        results.append((z, good, info))
    return ok, len(file_sets), results
