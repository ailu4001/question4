#!/usr/bin/env python
"""自锁底手提箱：按 Pacdora 官方轮廓还原"互锁底"结构。

数据来源：Pacdora 分享页接口（盒型=自锁底手提箱，L153 x W150 x H180）
实现：
  四壁围成筒（按官方面片尺寸映射）
  6 个底片按官方 dlist 精确轮廓构建，绕壁底折线折 90° 到盒底平面
  不同底片给微小 z 偏移，形成"侧片在下、互锁片居中、主片在上"的搭接层次
运行：blender --background --python scripts/mvp/handbag_lock_bottom.py -- --out output/handbag_lock
"""
import argparse
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

MM = 0.001
L, W, H = 153.0, 150.0, 180.0      # 官方尺寸 mm
FOLD_Y = 330.5                      # 底部折线（展开图坐标）

# 官方面片轮廓（展开图坐标，mm）—— 直接取自 Pacdora 数据
HB = [(25.71,330.50),(179.29,330.50),(171.16,338.63),(171.69,339.16),(104.35,406.50),
      (102.50,406.50),(102.50,408.84),(101.33,411.67),(61.00,452.00),(36.57,452.00),(26.00,331.20)]
HBR = [(171.69,339.16),(177.00,344.47),(177.00,448.00),(173.00,452.00),(149.85,452.00),(104.35,406.50)]
FRB = [(180.71,330.50),(331.29,330.50),(256.00,406.50),(208.38,406.50)]
FB = [(332.71,330.50),(486.29,330.50),(478.16,338.63),(478.69,339.16),(411.35,406.50),
      (409.50,406.50),(409.50,408.84),(408.33,411.67),(368.00,452.00),(343.57,452.00),(333.00,331.20)]
FBR = [(478.69,339.16),(484.00,344.47),(484.00,448.00),(480.00,452.00),(456.85,452.00),(411.35,406.50)]
FLB = [(487.71,330.50),(638.00,330.50),(563.00,406.50),(515.38,406.50)]

# 面片 -> (所属壁, 展开图 x 范围)
PANEL_WALL = {
    "HB": ("front", 25, 180), "HBR": ("front", 25, 180),
    "FB": ("back", 332, 487), "FBR": ("back", 332, 487),
    "FRB": ("right", 180, 332), "FLB": ("left", 487, 638),
}


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    return p.parse_args(argv)


def poly_obj(name, pts3d, thickness=0.5):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    bm = bmesh.new()
    vs = [bm.verts.new(Vector(p)) for p in pts3d]
    try:
        f = bm.faces.new(vs)
    except ValueError:
        bm.free(); return None
    uv = bm.loops.layers.uv.new("UVMap")
    n = len(pts3d)
    for i, loop in enumerate(f.loops):
        loop[uv].uv = (i / max(1, n - 1), 0.0)
    bm.normal_update(); bm.to_mesh(mesh); bm.free()
    md = obj.modifiers.new("solidify", "SOLIDIFY")
    md.thickness = thickness * MM
    return obj


def wall_point(x_exp, y_exp, wall, x0, x1):
    """把展开图坐标映射到盒壁/底部平面（折叠 90° 后）。"""
    d = (y_exp - FOLD_Y) * MM          # 底片伸出的深度
    if wall == "front":                # H 面板 -> y=-W/2，向盒内(+y)
        u = (x_exp - x0) / max(1e-6, (x1 - x0))
        return (-L / 2 * MM + u * L * MM, -W / 2 * MM + d, 0.0)
    if wall == "back":                 # F 面板 -> y=+W/2，向盒内(-y)
        u = (x_exp - x0) / max(1e-6, (x1 - x0))
        return (L / 2 * MM - u * L * MM, W / 2 * MM - d, 0.0)
    if wall == "right":                # FR -> x=+L/2，向盒内(-x)
        u = (x_exp - x0) / max(1e-6, (x1 - x0))
        return (L / 2 * MM - d, -W / 2 * MM + u * W * MM, 0.0)
    # left（FL）-> x=-L/2，向盒内(+x)
    u = (x_exp - x0) / max(1e-6, (x1 - x0))
    return (-L / 2 * MM + d, W / 2 * MM - u * W * MM, 0.0)


def main():
    args = parse_args()
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.context.scene.unit_settings.system = "METRIC"
    w, d, h = L * MM, W * MM, H * MM
    x0, x1 = -w / 2, w / 2
    y0, y1 = -d / 2, d / 2

    objs = []
    # 四壁
    for name, quad in (
        ("wall_front", [(x0, y0, 0), (x1, y0, 0), (x1, y0, h), (x0, y0, h)]),
        ("wall_back",  [(x0, y1, 0), (x1, y1, 0), (x1, y1, h), (x0, y1, h)]),
        ("wall_right", [(x1, y0, 0), (x1, y1, 0), (x1, y1, h), (x1, y0, h)]),
        ("wall_left",  [(x0, y0, 0), (x0, y1, 0), (x0, y1, h), (x0, y0, h)]),
    ):
        objs.append(poly_obj(name, quad))

    # 底部互锁：层次 z_offset（侧片下 -> 互锁片 -> 主片）
    layers = [(FRB, "FRB", 2.0), (FLB, "FLB", 2.0),
              (HBR, "HBR", 2.8), (FBR, "FBR", 2.8),
              (HB, "HB", 3.6), (FB, "FB", 3.6)]
    for pts, name, zoff in layers:
        wall, x0e, x1e = PANEL_WALL[name]
        pts3d = []
        for (xe, ye) in pts:
            px, py, _ = wall_point(xe, ye, wall, x0e, x1e)
            pts3d.append((px, py, zoff * MM))
        o = poly_obj("bottom_" + name, pts3d, thickness=0.5)
        if o:
            objs.append(o)

    objs = [o for o in objs if o]
    mat = bpy.data.materials.new("card")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.88, 0.84, 0.76, 1)
    bsdf.inputs["Roughness"].default_value = 0.7
    for o in objs:
        o.data.materials.append(mat)

    xs = [v.co.x for o in objs for v in o.data.vertices]
    ys = [v.co.y for o in objs for v in o.data.vertices]
    zs = [v.co.z for o in objs for v in o.data.vertices]
    print("[结构] 自锁底手提箱 %gx%gx%g mm | 四壁4 + 底片6 = %d 个面片" % (L, W, H, len(objs)))
    print("[自检] 包围盒 X=%.3f Y=%.3f Z=%.3f m" % (max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs)))

    try:
        bpy.ops.preferences.addon_enable(module="io_scene_gltf2")
    except Exception:
        pass
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=args.out + ".glb", export_format="GLB")
    bpy.ops.wm.save_as_mainfile(filepath=args.out + ".blend")

    # 相机/灯光/渲染（俯视图能看到互锁底）
    center = Vector(((max(xs)+min(xs))/2, (max(ys)+min(ys))/2, (max(zs)+min(zs))/2))
    radius = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    bpy.context.scene.collection.objects.link(cam); bpy.context.scene.camera = cam
    key = bpy.data.objects.new("Key", bpy.data.lights.new("Key", type="AREA"))
    key.data.energy, key.data.size = 60.0, radius * 4
    bpy.context.scene.collection.objects.link(key); key.location = center + Vector((radius, -radius, radius * 2))
    fill = bpy.data.objects.new("Fill", bpy.data.lights.new("Fill", type="AREA"))
    fill.data.energy, fill.data.size = 25.0, radius * 6
    bpy.context.scene.collection.objects.link(fill); fill.location = center + Vector((-radius, radius, radius * 2))
    world = bpy.data.worlds.new("W"); bpy.context.scene.world = world; world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.35, 0.35, 0.38, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.7
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE" if bpy.app.version >= (5, 0, 0) else "BLENDER_EEVEE_NEXT"
    sc.render.resolution_x = sc.render.resolution_y = 1000
    sc.render.image_settings.file_format = "PNG"
    for tag, off in (("quarter", (0.9, -1, 0.6)), ("bottom", (0.2, -0.6, -1.1)), ("top", (0.3, -0.5, 1.2))):
        dv = Vector(off).normalized()
        cam.location = center + dv * radius * 2.2
        cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = args.out + "_" + tag + ".png"
        bpy.ops.render.render(write_still=True)
        print("[OK] render ->", args.out + "_" + tag + ".png")


main()
