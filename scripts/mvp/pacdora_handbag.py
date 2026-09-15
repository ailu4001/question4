#!/usr/bin/env python
"""按 Pacdora 刀模 SVG 的精确折线生成手提盒 3D 模型。

结构（从 SVG 红色虚线折线解析）：
  四壁 x=25,180,332,487,638（4 个等宽面板 155mm）
  顶部提手 y=0..75，顶盖 y=75..150，盒身 y=150..330.5，底部 y=330.5..406.5
折叠：垂直折线围成筒(+90°)；顶盖/提手向下折(-90°)；底部向内折(+90°)

运行：blender --background --python scripts/mvp/pacdora_handbag.py -- --out output/handbag
"""
import argparse
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

MM = 0.001


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    p.add_argument("--angle", type=float, default=90.0)
    p.add_argument("--scale-mm", type=float, default=1.0)
    p.add_argument("--texture", default=None)
    p.add_argument("--sv", type=float, default=1.0, help="垂直折向符号")
    p.add_argument("--sh", type=float, default=-1.0, help="水平折向符号")
    return p.parse_args(argv)


# 从 Pacdora 刀模解析出的结构（单位与 SVG 一致 = mm）
XS = [25, 180, 332, 487, 638]          # 四壁边界（4 个面板）
YS = [0, 75, 150, 330.5, 452.0]        # 提手 / 顶盖 / 盒身 / 底部(官方数据 y=452)
WALL_ROW = 2                            # 盒身所在行（y 150..330.5）


def build_panels():
    panels = []
    for j in range(len(YS) - 1):
        for i in range(len(XS) - 1):
            panels.append({"i": i, "j": j,
                           "x0": XS[i], "x1": XS[i + 1],
                           "y0": YS[j], "y1": YS[j + 1]})
    return panels


def fold(panels, angle_deg, sv=1.0, sh=-1.0):
    idx = {(p["i"], p["j"]): p for p in panels}
    base_key = (1, WALL_ROW)
    transforms = {base_key: Matrix.Identity(4)}
    depth = {base_key: 0}
    queue = [base_key]
    ang = math.radians(angle_deg)
    wall_y0, wall_y1 = YS[WALL_ROW], YS[WALL_ROW + 1]
    while queue:
        key = queue.pop(0)
        i, j = key
        M = transforms[key]
        d = depth[key]
        for (ni, nj, vertical) in ((i + 1, j, True), (i - 1, j, True),
                                   (i, j + 1, False), (i, j - 1, False)):
            nk = (ni, nj)
            if nk not in idx or nk in transforms:
                continue
            if vertical:
                fold_x = XS[max(i, ni)]
                p1 = (fold_x, YS[j]); p2 = (fold_x, YS[j + 1])
                sign = sv           # 四壁
            else:
                fold_y = YS[max(j, nj)]
                p1 = (XS[i], fold_y); p2 = (XS[i + 1], fold_y)
                sign = sh           # 顶/底折片
            a = M @ Vector((p1[0] * MM, -p1[1] * MM, 0.0))
            b = M @ Vector((p2[0] * MM, -p2[1] * MM, 0.0))
            axis = b - a
            if axis.length < 1e-9:
                continue
            R = Matrix.Rotation(sign * ang, 4, axis.normalized())
            transforms[nk] = Matrix.Translation(a) @ R @ Matrix.Translation(-a) @ M
            depth[nk] = d + 1
            queue.append(nk)
    return transforms


def main():
    args = parse_args()
    panels = build_panels()
    transforms = fold(panels, args.angle, args.sv, args.sh)
    print("[结构] 四壁 x=%s | 行 y=%s | 面板=%d 折叠=%d" % (XS, YS, len(panels), len(transforms)))

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.context.scene.unit_settings.system = "METRIC"

    mesh = bpy.data.meshes.new("Handbag")
    obj = bpy.data.objects.new("Handbag", mesh)
    bpy.context.scene.collection.objects.link(obj)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    W_img, H_img = XS[-1], YS[-1]
    for p in panels:
        M = transforms.get((p["i"], p["j"]))
        if M is None:
            continue
        pts = [(p["x0"], p["y0"]), (p["x1"], p["y0"]), (p["x1"], p["y1"]), (p["x0"], p["y1"])]
        vs = [bm.verts.new(M @ Vector((x * args.scale_mm * MM, -y * args.scale_mm * MM, 0.0))) for (x, y) in pts]
        try:
            f = bm.faces.new(vs)
        except ValueError:
            continue
        for li, loop in enumerate(f.loops):
            loop[uv].uv = (pts[li][0] / W_img, 1.0 - pts[li][1] / H_img)
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()

    mat = bpy.data.materials.new("handbag_mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if args.texture and os.path.exists(args.texture):
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(args.texture)
        mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = (0.82, 0.85, 0.88, 1)
    bsdf.inputs["Roughness"].default_value = 0.55
    obj.data.materials.append(mat)

    zs = [v.co.z for v in obj.data.vertices]
    xs = [v.co.x for v in obj.data.vertices]; ys = [v.co.y for v in obj.data.vertices]
    print("[自检] 3D 包围盒 X=%.3f Y=%.3f Z=%.3f m (面=%d)" % (
        max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), len(obj.data.polygons)))

    try:
        bpy.ops.preferences.addon_enable(module="io_scene_gltf2")
    except Exception:
        pass
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(filepath=args.out + ".glb", export_format="GLB", use_selection=True)
    bpy.ops.wm.save_as_mainfile(filepath=args.out + ".blend")

    # 相机/灯光/渲染
    scene = bpy.context.scene
    center = Vector(((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2, (max(zs) + min(zs)) / 2))
    radius = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam); scene.camera = cam
    key = bpy.data.objects.new("Key", bpy.data.lights.new("Key", type="AREA"))
    key.data.energy, key.data.size = 70.0, radius * 4
    scene.collection.objects.link(key); key.location = center + Vector((radius, -radius, radius * 2))
    fill = bpy.data.objects.new("Fill", bpy.data.lights.new("Fill", type="AREA"))
    fill.data.energy, fill.data.size = 25.0, radius * 6
    scene.collection.objects.link(fill); fill.location = center + Vector((-radius, radius, radius * 2))
    world = bpy.data.worlds.new("W"); scene.world = world; world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.35, 0.35, 0.38, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.7
    scene.render.engine = "BLENDER_EEVEE" if bpy.app.version >= (5, 0, 0) else "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = scene.render.resolution_y = 1000
    scene.render.image_settings.file_format = "PNG"
    for tag, off in (("front", (0, -1, 0.35)), ("quarter", (0.9, -1, 0.6)), ("top", (0.3, -0.5, 1.3))):
        d = Vector(off).normalized()
        cam.location = center + d * radius * 2.4
        cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = args.out + "_" + tag + ".png"
        bpy.ops.render.render(write_still=True)
        print("[OK] render ->", args.out + "_" + tag + ".png")


main()
