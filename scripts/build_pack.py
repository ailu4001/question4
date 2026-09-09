#!/usr/bin/env python
"""最小原型：从一张二维正面设计图生成参数化包装盒并渲染。

依赖：Blender 3.6+（自带 Python），无需额外安装包。
用法（Windows / Linux / macOS 通用）：
    blender --background --python scripts/build_pack.py -- \
        --front assets/front.png --width 0.18 --depth 0.045 --height 0.045 \
        --out output/preview
说明：
    - front 图贴到 +Y 面（相机默认朝向），即"面向镜头"的正面。
    - 未提供图片的面使用纯色材质兜底。
    - 输出 preview_front.png 与 preview.glb。
"""
import argparse
import os
import sys

import bpy
from mathutils import Vector

AXIS_SLOTS = ["+Z", "-Z", "+Y", "-Y", "+X", "-X"]


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser(description="2D 正面图 -> 3D 包装盒渲染")
    p.add_argument("--front", required=True, help="正面设计图路径(PNG/JPG)")
    p.add_argument("--width", type=float, default=180, help="盒宽(毫米)")
    p.add_argument("--depth", type=float, default=45, help="盒深(毫米)")
    p.add_argument("--height", type=float, default=45, help="盒高(毫米)")
    for axis in ["right", "left", "top", "bottom", "back"]:
        p.add_argument("--" + axis, default=None, help=axis + " 面图片(可选)")
    p.add_argument("--engine", default="auto", choices=["auto", "EEVEE", "CYCLES"])
    p.add_argument("--samples", type=int, default=64)
    p.add_argument("--out", required=True, help="输出路径前缀(不含扩展名)")
    return p.parse_args(argv)


def clean_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for m in list(bpy.data.materials):
        bpy.data.materials.remove(m)


def make_material(name, image_path=None, color=(0.92, 0.92, 0.92, 1.0)):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if image_path and os.path.exists(image_path):
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(image_path)
        mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = 0.35  # 覆膜纸质感
    return mat


def axis_key(normal):
    i = max(range(3), key=lambda k: abs(normal[k]))
    return ("+" if normal[i] > 0 else "-") + "XYZ"[i]


def add_box(w, d, h):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, h / 2 + 0.002))
    obj = bpy.context.object
    obj.scale = (w, d, h)
    obj.name = "PackBox"
    return obj


def assign_materials(obj, args):
    paths = {
        "+Y": args.front, "-Y": args.back, "+X": args.right,
        "-X": args.left, "+Z": args.top, "-Z": args.bottom,
    }
    for axis in AXIS_SLOTS:
        mat = make_material("mat_" + axis, paths.get(axis))
        obj.data.materials.append(mat)
    for poly in obj.data.polygons:
        poly.material_index = AXIS_SLOTS.index(axis_key(poly.normal))


def scene_setup(center, size_max):
    # 相机：从 +Y 看向盒子中心
    dist = size_max * 1.25
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    bpy.context.scene.collection.objects.link(cam)
    cam.location = center + Vector((0.0, dist * 0.98, dist * 0.30))
    cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam  # 设为活动相机，否则渲染报 no camera

    # 主光：相机同侧上方（保证正面受光）
    key = bpy.data.objects.new("Key", bpy.data.lights.new("Key", type="AREA"))
    key.data.energy, key.data.size = 60.0, 1.0
    bpy.context.scene.collection.objects.link(key)
    key.location = center + Vector((size_max * 0.6, size_max * 0.9, size_max * 1.6))

    # 补光：正上方柔和环境光
    fill = bpy.data.objects.new("Fill", bpy.data.lights.new("Fill", type="AREA"))
    fill.data.energy, fill.data.size = 12.0, 2.5
    bpy.context.scene.collection.objects.link(fill)
    fill.location = center + Vector((0.0, 0.0, size_max * 2.4))

    # 深灰棚拍背景
    world = bpy.data.worlds.new("Studio")
    bpy.context.scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.05, 0.06, 1.0)


def add_ground(size_max):
    bpy.ops.mesh.primitive_plane_add(size=size_max * 3.0, location=(0, 0, 0))
    ground = bpy.context.object
    ground.name = "Ground"
    mat = make_material("mat_ground", color=(0.82, 0.82, 0.85, 1.0))
    ground.data.materials.append(mat)


def resolve_engine(name):
    # 引擎标识随 Blender 版本变化：
    #   4.2 - 4.x: BLENDER_EEVEE_NEXT；5.0+：恢复为 BLENDER_EEVEE
    if bpy.app.version >= (5, 0, 0):
        eevee = "BLENDER_EEVEE"
    elif bpy.app.version >= (4, 2, 0):
        eevee = "BLENDER_EEVEE_NEXT"
    else:
        eevee = "BLENDER_EEVEE"
    if name == "CYCLES":
        return "CYCLES"
    if name == "EEVEE":
        return eevee
    return eevee


def render(scene, filepath, engine, samples):
    scene.render.engine = engine
    if engine == "CYCLES":
        scene.cycles.samples = samples
    else:
        try:
            scene.eevee.taa_render_samples = samples
        except AttributeError:
            pass
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1200
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = filepath
    bpy.ops.render.render(write_still=True)


def export_glb(obj, filepath):
    try:
        bpy.ops.preferences.addon_enable(module="io_scene_gltf2")
    except Exception:
        pass
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    try:
        bpy.ops.export_scene.gltf(filepath=filepath, export_format="GLB", use_selection=True)
        print("[OK] exported ->", filepath)
    except Exception as exc:  # noqa: BLE001
        print("[WARN] glTF 导出失败(不影响渲染):", exc)


def main():
    args = parse_args()
    # 参数为毫米，此处换算为 Blender 米
    args.width *= 0.001
    args.depth *= 0.001
    args.height *= 0.001
    clean_scene()
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    obj = add_box(args.width, args.depth, args.height)
    assign_materials(obj, args)
    center = Vector((0, 0, args.height / 2))
    size_max = max(args.width, args.depth, args.height)
    add_ground(size_max)
    scene_setup(center, size_max)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    render(scene, args.out + "_front.png", resolve_engine(args.engine), args.samples)
    print("[OK] rendered ->", args.out + "_front.png")
    export_glb(obj, args.out + ".glb")


main()
