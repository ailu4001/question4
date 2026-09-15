#!/usr/bin/env python
"""自锁底手提箱（完整版）：官方轮廓还原 —— 四壁 + 互锁底 + 侧顶片 + 提手(含提手孔)。

上部（按官方数据）：
  HT1/FT1 (155x75 矩形)  : 提手竖直段（从壁顶向上折 90°）
  HT2/FT2 (155x75 带弧顶): 提手顶部（再水平向内折 90°，两片在中间相接）
  x       (52x30)        : 提手孔
  FRT/FLT (152x80.8 斜边): 侧顶片
运行：blender --background --python scripts/mvp/handbag_full.py -- --out output/handbag_full
"""
import argparse
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

MM = 0.001
L, W, H = 153.0, 150.0, 180.0
FOLD_Y = 330.5

# ---- 官方轮廓（展开图坐标 mm）----
HT1 = [(25,150),(26.5,148.5),(26.5,75),(178.5,75),(178.5,148.5),(180,150)]
HT2 = [(26.5,75),(26.5,25),(46.15,22.39),(47.57,22.49),(57.11,0),(147.89,0),
       (157.43,22.49),(158.85,22.39),(178.5,25),(178.5,75)]
FT1 = [(332,150),(333.5,148.5),(333.5,75),(485.5,75),(485.5,148.5),(487,150)]
FT2 = [(333.5,75),(333.5,25),(353.15,22.39),(354.57,22.49),(364.11,0),(454.89,0),
       (464.43,22.49),(465.85,22.39),(485.5,25),(485.5,75)]
HANDLE_HOLE = [(398.5,23),(420.5,23),(420.5,53),(398.5,53)]
# 底片（互锁）
HB = [(25.71,330.50),(179.29,330.50),(171.16,338.63),(171.69,339.16),(104.35,406.50),
      (102.50,406.50),(102.50,408.84),(101.33,411.67),(61.00,452.00),(36.57,452.00),(26.00,331.20)]
HBR = [(171.69,339.16),(177.00,344.47),(177.00,448.00),(173.00,452.00),(149.85,452.00),(104.35,406.50)]
FRB = [(180.71,330.50),(331.29,330.50),(256.00,406.50),(208.38,406.50)]
FB = [(332.71,330.50),(486.29,330.50),(478.16,338.63),(478.69,339.16),(411.35,406.50),
      (409.50,406.50),(409.50,408.84),(408.33,411.67),(368.00,452.00),(343.57,452.00),(333.00,331.20)]
FBR = [(478.69,339.16),(484.00,344.47),(484.00,448.00),(480.00,452.00),(456.85,452.00),(411.35,406.50)]
FLB = [(487.71,330.50),(638.00,330.50),(563.00,406.50),(515.38,406.50)]


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    return p.parse_args(argv)


def poly_obj(name, pts3d, thickness=0.5):
    mesh = bpy.data.meshes.new(name); obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    bm = bmesh.new()
    vs = [bm.verts.new(Vector(p)) for p in pts3d]
    try:
        f = bm.faces.new(vs)
    except ValueError:
        bm.free(); return None
    uv = bm.loops.layers.uv.new("UVMap")
    n = max(1, len(pts3d))
    for i, loop in enumerate(f.loops):
        loop[uv].uv = (i / n, 0.0)
    bm.normal_update(); bm.to_mesh(mesh); bm.free()
    md = obj.modifiers.new("solidify", "SOLIDIFY"); md.thickness = thickness * MM
    return obj


def map_x(x_exp, x0=25, x1=180):
    """前面板展开 x -> 盒体 x（-L/2..L/2）"""
    return (-L / 2 + (x_exp - x0) / max(1e-6, x1 - x0) * L) * MM


def handle_pts(pts, side, part):
    """提手折叠：part='v'(竖直段) / 'h'(顶部水平段)。side='front'(y=-W/2) / 'back'(y=+W/2)"""
    out = []
    for (xe, ye) in pts:
        px = map_x(xe if xe < 200 else xe - 307)     # FT 系列 x 平移回 H 面板范围
        if side == "front":
            ybase = -W / 2 * MM
            if part == "v":
                z = H * MM + (150 - ye) * MM      # 75..150 -> 255..180
                out.append((px, ybase, z))
            else:
                d = (75 - ye) * MM                 # 0..75 -> 向内延伸
                out.append((px, ybase + d, (H + 75) * MM))
        else:
            ybase = W / 2 * MM
            if part == "v":
                z = H * MM + (150 - ye) * MM
                out.append((px, ybase, z))
            else:
                d = (75 - ye) * MM
                out.append((px, ybase - d, (H + 75) * MM))
    return out


def bottom_pts(pts, wall, x0e, x1e, zoff):
    out = []
    for (xe, ye) in pts:
        d = (ye - FOLD_Y) * MM
        if wall == "front":
            u = (xe - x0e) / max(1e-6, x1e - x0e)
            out.append((-L/2*MM + u*L*MM, -W/2*MM + d, zoff*MM))
        elif wall == "back":
            u = (xe - x0e) / max(1e-6, x1e - x0e)
            out.append((L/2*MM - u*L*MM, W/2*MM - d, zoff*MM))
        elif wall == "right":
            u = (xe - x0e) / max(1e-6, x1e - x0e)
            out.append((L/2*MM - d, -W/2*MM + u*W*MM, zoff*MM))
        else:
            u = (xe - x0e) / max(1e-6, x1e - x0e)
            out.append((-L/2*MM + d, W/2*MM - u*W*MM, zoff*MM))
    return out


def main():
    args = parse_args()
    bpy.ops.object.select_all(action="SELECT"); bpy.ops.object.delete(use_global=False)
    bpy.context.scene.unit_settings.system = "METRIC"
    w, d, h = L * MM, W * MM, H * MM
    x0, x1 = -w/2, w/2; y0, y1 = -d/2, d/2
    objs = []
    # 四壁
    for name, quad in (
        ("wall_front", [(x0,y0,0),(x1,y0,0),(x1,y0,h),(x0,y0,h)]),
        ("wall_back",  [(x0,y1,0),(x1,y1,0),(x1,y1,h),(x0,y1,h)]),
        ("wall_right", [(x1,y0,0),(x1,y1,0),(x1,y1,h),(x1,y0,h)]),
        ("wall_left",  [(x0,y0,0),(x0,y1,0),(x0,y1,h),(x0,y0,h)]),
    ):
        objs.append(poly_obj(name, quad))
    # 互锁底
    for pts, name, wall, xr, zoff in (
        (FRB,"FRB","right",(180,332),2.0), (FLB,"FLB","left",(487,638),2.0),
        (HBR,"HBR","front",(25,180),2.8), (FBR,"FBR","back",(332,487),2.8),
        (HB,"HB","front",(25,180),3.6), (FB,"FB","back",(332,487),3.6),
    ):
        objs.append(poly_obj("bottom_"+name, bottom_pts(pts, wall, xr[0], xr[1], zoff)))
    # 侧顶片（简化为水平顶片，位于顶部内侧）
    objs.append(poly_obj("top_right", [(x1-0.02,y0,h),(x1-0.02,y1,h),(x1,y1,h),(x1,y0,h)]))
    objs.append(poly_obj("top_left",  [(x0+0.02,y0,h),(x0+0.02,y1,h),(x0,y1,h),(x0,y0,h)]))
    # 提手：竖直段 + 顶部水平段（前后各一组）
    hfv = poly_obj("handle_front_v", handle_pts(HT1, "front", "v"))
    hfh = poly_obj("handle_front_h", handle_pts(HT2, "front", "h"))
    hbv = poly_obj("handle_back_v", handle_pts(FT1, "back", "v"))
    hbh = poly_obj("handle_back_h", handle_pts(FT2, "back", "h"))
    objs += [o for o in (hfv, hfh, hbv, hbh) if o]

    # --- 提手孔（官方 x 面片 52x30 → 实孔 22x30，位于提手顶部中央）---
    for target, hy in ((hfh, -W/2*MM + 0.037), (hbh, W/2*MM - 0.037)):
        if target is None:
            continue
        # 先应用 solidify，再做布尔
        for md in list(target.modifiers):
            bpy.context.view_layer.objects.active = target
            try:
                bpy.ops.object.modifier_apply(modifier=md.name)
            except Exception:
                pass
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0.0, hy, (H + 75) * MM))
        hole = bpy.context.object
        hole.scale = (0.011, 0.015, 0.006)     # 22 x 30 x 12 mm（穿透）
        md = target.modifiers.new("hole", "BOOLEAN")
        md.operation = "DIFFERENCE"
        md.object = hole
        bpy.context.view_layer.objects.active = target
        try:
            bpy.ops.object.modifier_apply(modifier=md.name)
        except Exception as e:
            print("[WARN] 提手孔布尔失败:", e)
        bpy.data.objects.remove(hole, do_unlink=True)
    objs = [o for o in objs if o]

    mat = bpy.data.materials.new("card"); mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.88,0.84,0.76,1)
    bsdf.inputs["Roughness"].default_value = 0.7
    for o in objs:
        o.data.materials.append(mat)

    xs=[v.co.x for o in objs for v in o.data.vertices]; ys=[v.co.y for o in objs for v in o.data.vertices]
    zs=[v.co.z for o in objs for v in o.data.vertices]
    print("[结构] 完整手提箱: 四壁4 + 互锁底6 + 侧顶2 + 提手4 = %d" % len(objs))
    print("[自检] 包围盒 X=%.3f Y=%.3f Z=%.3f m (含提手)" % (max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs)))

    try: bpy.ops.preferences.addon_enable(module="io_scene_gltf2")
    except Exception: pass
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=args.out+".glb", export_format="GLB")
    bpy.ops.wm.save_as_mainfile(filepath=args.out+".blend")

    center = Vector(((max(xs)+min(xs))/2,(max(ys)+min(ys))/2,(max(zs)+min(zs))/2))
    radius = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    bpy.context.scene.collection.objects.link(cam); bpy.context.scene.camera = cam
    key = bpy.data.objects.new("Key", bpy.data.lights.new("Key", type="AREA"))
    key.data.energy, key.data.size = 60.0, radius*4
    bpy.context.scene.collection.objects.link(key); key.location = center + Vector((radius,-radius,radius*2))
    fill = bpy.data.objects.new("Fill", bpy.data.lights.new("Fill", type="AREA"))
    fill.data.energy, fill.data.size = 25.0, radius*6
    bpy.context.scene.collection.objects.link(fill); fill.location = center + Vector((-radius,radius,radius*2))
    world = bpy.data.worlds.new("W"); bpy.context.scene.world = world; world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value=(0.35,0.35,0.38,1)
    world.node_tree.nodes["Background"].inputs[1].default_value=0.7
    sc=bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE" if bpy.app.version>=(5,0,0) else "BLENDER_EEVEE_NEXT"
    sc.render.resolution_x = sc.render.resolution_y = 1000
    sc.render.image_settings.file_format="PNG"
    for tag, off in (("quarter",(0.9,-1,0.5)),("front",(0,-1,0.25)),("bottom",(0.2,-0.6,-1.1))):
        dv=Vector(off).normalized()
        cam.location=center+dv*radius*2.2
        cam.rotation_euler=(center-cam.location).to_track_quat("-Z","Y").to_euler()
        sc.render.filepath=args.out+"_"+tag+".png"
        bpy.ops.render.render(write_still=True)
        print("[OK] render ->", args.out+"_"+tag+".png")


main()
