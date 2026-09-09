#!/usr/bin/env python
"""阶梯回转壳体(电机/泵外壳式) 参数化建模 + 多角度渲染。

结构(mm)：
  法兰  R55  h8   | 主体 R40 h50 | 凸台 R20 h8 | 内腔 R34 | 顶孔 R10 | 4xR4 安装孔
运行: blender --background --python scripts/build_housing.py -- --out output/housing
"""
import argparse
import math
import os
import sys

import bpy
from mathutils import Vector

MM = 0.001


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    p.add_argument("--engine", default="auto", choices=["auto", "EEVEE", "CYCLES"])
    p.add_argument("--samples", type=int, default=64)
    return p.parse_args(argv)


def clean_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for m in list(bpy.data.materials):
        bpy.data.materials.remove(m)


def add_cyl(name, radius, z0, z1, verts=72):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius,
                                        depth=z1 - z0, location=(0, 0, (z0 + z1) / 2))
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


def resolve_engine(name):
    if bpy.app.version >= (5, 0, 0):
        return "CYCLES" if name == "CYCLES" else "BLENDER_EEVEE"
    if bpy.app.version >= (4, 2, 0):
        return "CYCLES" if name == "CYCLES" else "BLENDER_EEVEE_NEXT"
    return "CYCLES" if name == "CYCLES" else "BLENDER_EEVEE"


def setup_scene(radius_max, height):
    scene = bpy.context.scene
    center = Vector((0, 0, height / 2 * MM))
    dist = radius_max * 2 * MM * 2.6

    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam

    key = bpy.data.objects.new("Key", bpy.data.lights.new("Key", type="AREA"))
    key.data.energy, key.data.size = 120.0, 1.5
    scene.collection.objects.link(key)
    key.location = Vector((dist, -dist * 0.8, dist * 1.6))

    fill = bpy.data.objects.new("Fill", bpy.data.lights.new("Fill", type="AREA"))
    fill.data.energy, fill.data.size = 30.0, 3.0
    scene.collection.objects.link(fill)
    fill.location = Vector((0, 0, dist * 2.2))

    world = bpy.data.worlds.new("Studio")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.03, 0.03, 0.04, 1)

    bpy.ops.mesh.primitive_plane_add(size=dist * 8, location=(0, 0, 0))
    ground = bpy.context.object
    gm = bpy.data.materials.new("mat_ground")
    gm.use_nodes = True
    gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.85, 0.85, 0.87, 1)
    ground.data.materials.append(gm)
    return cam, center


def make_material(obj, color=(0.72, 0.74, 0.78, 1), metal=0.75, rough=0.35):
    mat = bpy.data.materials.new("mat_housing")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Roughness"].default_value = rough
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)


def place_camera(cam, center, dist, direction):
    d = Vector(direction).normalized()
    cam.location = center + d * dist
    cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()


def main():
    args = parse_args()
    clean_scene()
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"

    flange = add_cyl("flange", 55, 0, 8)
    body = add_cyl("body", 40, 7.5, 58)
    boss = add_cyl("boss", 20, 57.5, 66)
    apply_bool(flange, body, "UNION")
    apply_bool(flange, boss, "UNION")
    housing = flange
    housing.name = "Housing"

    cavity = add_cyl("cavity", 34, 7.9, 58)
    apply_bool(housing, cavity, "DIFFERENCE")
    hole = add_cyl("hole_top", 10, 58, 66.2)
    apply_bool(housing, hole, "DIFFERENCE")
    for k in range(4):
        ang = math.radians(90 * k)
        m = add_cyl("mount", 4, -0.2, 8.2)
        m.location = (math.cos(ang) * 45, math.sin(ang) * 45, m.location.z)
        apply_bool(housing, m, "DIFFERENCE")

    make_material(housing)
    cam, center = setup_scene(55, 66)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    scene.render.engine = resolve_engine(args.engine)
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1200
    scene.render.image_settings.file_format = "PNG"
    dist = 55 * 2 * MM * 2.6
    views = [("front", (0.0, 1.0, 0.5)), ("quarter", (1.1, 1.0, 0.85)), ("top", (0.4, 0.9, 1.8))]
    for vname, vdir in views:
        place_camera(cam, center, dist, vdir)
        scene.render.filepath = args.out + "_" + vname + ".png"
        bpy.ops.render.render(write_still=True)
        print("[OK] rendered ->", args.out + "_" + vname + ".png")

    try:
        bpy.ops.preferences.addon_enable(module="io_scene_gltf2")
    except Exception:
        pass
    bpy.ops.object.select_all(action="DESELECT")
    housing.select_set(True)
    bpy.context.view_layer.objects.active = housing
    try:
        bpy.ops.export_scene.gltf(filepath=args.out + ".glb", export_format="GLB", use_selection=True)
        print("[OK] exported ->", args.out + ".glb")
    except Exception as exc:
        print("[WARN] glTF 导出失败:", exc)


main()
