#!/usr/bin/env python
"""液压缸 外观级参数化建模 + 多视角渲染。

参数(mm)：缸筒 Ø80x260；两端法兰 Ø110(缸底厚20/缸头厚25+Ø32中心孔)；
活塞杆 Ø28 伸出250；侧面两油口 Ø30。
运行: blender --background --python scripts/build_hydraulic.py -- --out output/hydraulic
"""
import argparse
import math
import os
import sys

import bpy

MM = 0.001
BARREL_R = 45.0
BARREL_Z0, BARREL_Z1 = -130.0, 130.0
CAP_R = 55.0
CAP_B_Z0, CAP_B_Z1 = -150.0, -130.0
CAP_T_Z0, CAP_T_Z1 = 130.0, 155.0
ROD_R = 14.0
ROD_Z0, ROD_Z1 = 155.0, 405.0
PORT_R, PORT_LEN = 15.0, 30.0
PORT_Z = [-90.0, 90.0]


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    return p.parse_args(argv)


def clean_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for m in list(bpy.data.materials):
        bpy.data.materials.remove(m)


def add_cyl(name, radius, z0, z1, verts=64):
    # 参数单位 mm，此处换算为 Blender 米
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius * MM,
                                        depth=(z1 - z0) * MM, location=(0, 0, (z0 + z1) / 2 * MM))
    obj = bpy.context.object
    obj.name = name
    return obj


def activate(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def apply_bool(target, other, op):
    activate(target)
    md = target.modifiers.new("bool", "BOOLEAN")
    md.operation = op
    md.object = other
    try:
        bpy.ops.object.modifier_apply(modifier=md.name)
    finally:
        if other.name in bpy.data.objects:
            bpy.data.objects.remove(other, do_unlink=True)


def make_mat(name, color, metal, rough):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bs = mat.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value = color
    bs.inputs["Metallic"].default_value = metal
    bs.inputs["Roughness"].default_value = rough
    return mat


def assign(obj, mat):
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)


def main():
    args = parse_args()
    clean_scene()
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"

    barrel = add_cyl("barrel", BARREL_R, BARREL_Z0, BARREL_Z1)
    cap_b = add_cyl("cap_bottom", CAP_R, CAP_B_Z0, CAP_B_Z1)
    cap_t = add_cyl("cap_top", CAP_R, CAP_T_Z0, CAP_T_Z1)
    hole = add_cyl("cap_hole", 16.0, CAP_T_Z0, CAP_T_Z1 + 0.2)
    apply_bool(cap_t, hole, "DIFFERENCE")
    rod = add_cyl("rod", ROD_R, ROD_Z0, ROD_Z1)

    mat_body = make_mat("alum", (0.72, 0.74, 0.78, 1), 0.75, 0.35)
    mat_rod = make_mat("chrome", (0.9, 0.9, 0.92, 1), 1.0, 0.15)
    for o in (barrel, cap_b, cap_t):
        assign(o, mat_body)
    assign(rod, mat_rod)

    # 油口(水平)
    for z in PORT_Z:
        bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=PORT_R * MM,
                                            depth=PORT_LEN * MM, location=(0, 0, z * MM))
        po = bpy.context.object
        po.name = "port"
        po.rotation_euler = (0, math.pi / 2, 0)
        po.location = ((BARREL_R + PORT_LEN / 2 + 0.5) * MM, 0, z * MM)
        assign(po, mat_body)


    try:
        bpy.ops.preferences.addon_enable(module="io_scene_gltf2")
    except Exception:
        pass
    bpy.ops.object.select_all(action="DESELECT")
    for o in bpy.context.scene.objects:
        if o.type == "MESH" and o.name.lower() not in ("plane", "ground"):
            o.select_set(True)
    try:
        bpy.ops.export_scene.gltf(filepath=args.out + ".glb", export_format="GLB", use_selection=True)
        print("[OK] exported ->", args.out + ".glb")
    except Exception as exc:
        print("[WARN] glTF 导出失败:", exc)


main()
