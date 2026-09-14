#!/usr/bin/env python
"""M7 渲染与交付：3 套灯光预设 × 3 套镜头预设，支持 2K 与多画幅输出。

运行：blender --background --python scripts/mvp/render_mvp.py -- \
        --scene-json <scene.json> --model <model.glb> --outdir output/mvp_render --quick
"""
import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LIGHTS = {
    "warm_morning": {"temp": (1.0, 0.88, 0.72), "energy": 260.0, "elev": 35, "label": "暖色晨光"},
    "soft_studio":  {"temp": (1.0, 0.98, 0.95), "energy": 300.0, "elev": 50, "label": "柔光棚拍"},
    "cool_blue":    {"temp": (0.82, 0.90, 1.0),  "energy": 240.0, "elev": 25, "label": "冷色蓝调"},
}
CAMS = {
    "front":         {"orbit": 0,  "elev": 5,  "label": "正面"},
    "three_quarter": {"orbit": 45, "elev": 30, "label": "45度"},
    "top":           {"orbit": 20, "elev": 75, "label": "俯视"},
}
ASPECTS = {"1:1": (2048, 2048), "4:5": (2048, 2560), "16:9": (2048, 1152)}


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--scene-json", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--outdir", required=True)
    p.add_argument("--quick", action="store_true", help="只渲染 1 灯 1 镜（快速验证）")
    return p.parse_args(argv)


def clean_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def scene_bounds():
    ms = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    bb = None
    for o in ms:
        for c in o.bound_box:
            wc = o.matrix_world @ Vector(c)
            if bb is None:
                bb = [list(wc), list(wc)]
            else:
                for i in range(3):
                    bb[0][i] = min(bb[0][i], wc[i]); bb[1][i] = max(bb[1][i], wc[i])
    mn, mx = Vector(bb[0]), Vector(bb[1])
    return mn, mx, (mn + mx) / 2, (mx - mn).length / 2


def setup_light(center, radius, preset):
    cfg = LIGHTS[preset]
    sun = bpy.data.objects.new("KeySun", bpy.data.lights.new("KeySun", type="SUN"))
    sun.data.energy = 4.0
    a = math.radians(cfg["elev"])
    sun.rotation_euler = (a, 0.1, math.radians(40))
    bpy.context.scene.collection.objects.link(sun)
    key = bpy.data.objects.new("Key", bpy.data.lights.new("Key", type="AREA"))
    key.data.energy = cfg["energy"]
    key.data.size = radius * 3
    key.color = tuple(list(cfg["temp"]) + [1.0])
    key.location = center + Vector((radius * 1.4, -radius * 1.2, radius * 2.4))
    bpy.context.scene.collection.objects.link(key)
    w = bpy.context.scene.world or bpy.data.worlds.new("W")
    bpy.context.scene.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = tuple(list(cfg["temp"]) + [1])
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.25


def place_camera(cam, center, radius, preset):
    cfg = CAMS[preset]
    d = radius * 3.0
    o, e = math.radians(cfg["orbit"]), math.radians(cfg["elev"])
    cam.location = center + Vector((math.sin(o) * math.cos(e), -math.cos(o) * math.cos(e), math.sin(e))) * d
    cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()


def main():
    args = parse_args()
    with open(args.scene_json, encoding="utf-8") as f:
        scene = json.load(f)
    clean_scene()
    bpy.ops.import_scene.gltf(filepath=args.model)
    # 移除导入的残留地面
    for o in list(bpy.context.scene.objects):
        nm = o.name.lower()
        if o.type == "MESH" and (nm.startswith("plane") or nm.startswith("ground")):
            bpy.data.objects.remove(o, do_unlink=True)

    mn, mx, center, radius = scene_bounds()
    ground_z = mn.z - 0.0005
    bpy.ops.mesh.primitive_plane_add(size=radius * 6, location=(0, 0, ground_z))
    gm = bpy.data.materials.new("ground")
    gm.use_nodes = True
    gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.55, 0.52, 0.48, 1)
    bpy.context.object.data.materials.append(gm)

    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam

    aspect = scene["output"].get("aspect", "4:5")
    res = ASPECTS.get(aspect, (2048, 2560))
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE" if bpy.app.version >= (5, 0, 0) else (
        "BLENDER_EEVEE_NEXT" if bpy.app.version >= (4, 2, 0) else "BLENDER_EEVEE")
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.image_settings.file_format = "PNG"
    os.makedirs(args.outdir, exist_ok=True)

    light_sets = ["soft_studio"] if args.quick else list(LIGHTS)
    cam_sets = ["three_quarter"] if args.quick else list(CAMS)
    count = 0
    for lp in light_sets:
        setup_light(center, radius, lp)
        for cp in cam_sets:
            place_camera(cam, center, radius, cp)
            fn = os.path.join(args.outdir, "%s_%s_%s.png" % (os.path.basename(args.model).replace(".glb", ""), lp, cp))
            sc.render.filepath = fn
            bpy.ops.render.render(write_still=True)
            count += 1
            print("[OK] render ->", fn)
    print("[OK] 共渲染 %d 张（画幅 %s, %dx%d）" % (count, aspect, res[0], res[1]))


main()
