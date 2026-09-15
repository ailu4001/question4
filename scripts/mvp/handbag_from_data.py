#!/usr/bin/env python
"""按 Pacdora 官方数据生成"自锁底手提箱"3D 模型。

官方数据（Pacdora 分享页接口）：
  盒型 = 自锁底手提箱 (cate 112320)
  尺寸 = L153 x W150 x H180 mm（knife.size）
  面片 = 18 个（H/FR/F/FL 四壁、HT/FT 提手片、HB/FB 自锁底、HL 糊口）

结构：四壁围筒 + 自锁底(简化平板) + 顶部提手(两侧提手片对折 + 顶横梁)
运行：blender --background --python scripts/mvp/handbag_from_data.py -- --out output/handbag_final
"""
import argparse
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

MM = 0.001
# 官方尺寸（mm）
L, W, H = 153.0, 150.0, 180.0     # 长 / 宽 / 高
HANDLE_H = 75.0                    # 提手片高（官方 HT1/HT2 各 75）
TOP_FLAP = 20.0                    # 顶部封盖宽
FLOOR = 3.0                        # 底厚度
T = 0.5                            # 纸厚


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    return p.parse_args(argv)


def panel(name, quad, thickness=T):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    bm = bmesh.new()
    vs = [bm.verts.new(Vector(q)) for q in quad]
    try:
        f = bm.faces.new(vs)
    except ValueError:
        return None
    uv = bm.loops.layers.uv.new("UVMap")
    corners = [(0, 0), (1, 0), (1, 1), (0, 1)]
    for i, loop in enumerate(f.loops):
        loop[uv].uv = corners[i]
    bm.normal_update()
    bm.to_mesh(mesh); bm.free()
    md = obj.modifiers.new("solidify", "SOLIDIFY")
    md.thickness = thickness * MM
    return obj


def main():
    args = parse_args()
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.context.scene.unit_settings.system = "METRIC"

    w, d, h = L * MM, W * MM, H * MM
    fh = HANDLE_H * MM
    x0, x1 = -w / 2, w / 2
    y0, y1 = -d / 2, d / 2

    objs = []
    # --- 四壁（围成筒）---
    objs.append(panel("wall_front", [(x0, y0, 0), (x1, y0, 0), (x1, y0, h), (x0, y0, h)]))
    objs.append(panel("wall_back",  [(x0, y1, 0), (x1, y1, 0), (x1, y1, h), (x0, y1, h)]))
    objs.append(panel("wall_left",  [(x0, y0, 0), (x0, y1, 0), (x0, y1, h), (x0, y0, h)]))
    objs.append(panel("wall_right", [(x1, y0, 0), (x1, y1, 0), (x1, y1, h), (x1, y0, h)]))
    # --- 自锁底（官方 HB/FB 折叠后形成底，这里做成底板）---
    objs.append(panel("floor", [(x0, y0, FLOOR * MM), (x1, y0, FLOOR * MM),
                                (x1, y1, FLOOR * MM), (x0, y1, FLOOR * MM)], thickness=3.0))
    # --- 顶部封盖（前后两片向内折 90°）---
    objs.append(panel("top_front", [(x0, y0, h), (x1, y0, h), (x1, y0 + TOP_FLAP * MM, h), (x0, y0 + TOP_FLAP * MM, h)]))
    objs.append(panel("top_back",  [(x0, y1, h), (x1, y1, h), (x1, y1 - TOP_FLAP * MM, h), (x0, y1 - TOP_FLAP * MM, h)]))
    # --- 提手：前后两侧提手片向上折起（官方 HT1+HT2 = 75+75 对折成提手）---
    objs.append(panel("handle_front", [(x0 * 0.55, y0, h), (x1 * 0.55, y0, h),
                                       (x1 * 0.55, y0, h + fh), (x0 * 0.55, y0, h + fh)]))
    objs.append(panel("handle_back",  [(x0 * 0.55, y1, h), (x1 * 0.55, y1, h),
                                       (x1 * 0.55, y1, h + fh), (x0 * 0.55, y1, h + fh)]))
    # --- 提手顶梁（连接两提手片）---
    objs.append(panel("handle_top", [(x0 * 0.55, y0, h + fh), (x1 * 0.55, y0, h + fh),
                                     (x1 * 0.55, y1, h + fh), (x0 * 0.55, y1, h + fh)], thickness=2.0))
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
    print("[结构] 自锁底手提箱 %gx%gx%g mm | 面片=%d" % (L, W, H, len(objs)))
    print("[自检] 包围盒 X=%.3f Y=%.3f Z=%.3f m" % (max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs)))

    try:
        bpy.ops.preferences.addon_enable(module="io_scene_gltf2")
    except Exception:
        pass
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=args.out + ".glb", export_format="GLB")
    bpy.ops.wm.save_as_mainfile(filepath=args.out + ".blend")

    # 相机/灯光/渲染
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
    for tag, off in (("front", (0, -1, 0.3)), ("quarter", (0.9, -1, 0.55)), ("top", (0.3, -0.5, 1.2))):
        dv = Vector(off).normalized()
        cam.location = center + dv * radius * 2.4
        cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = args.out + "_" + tag + ".png"
        bpy.ops.render.render(write_still=True)
        print("[OK] render ->", args.out + "_" + tag + ".png")


main()
