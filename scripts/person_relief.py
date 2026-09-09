#!/usr/bin/env python
"""Blender 演示级(C)：把人物照片做成 2.5D 浮雕板（可旋转、可导出 GLB）。

依赖预处理生成的 assets/relief_albedo.png 与 assets/relief_height.png：
    python scripts/make_relief_maps.py --input assets/鹿乃2.jpg
运行：
    blender --background --python scripts/person_relief.py -- \
        --albedo assets/relief_albedo.png --height assets/relief_height.png --out output/person
说明：单面浮雕 + 竖直立板；相机从 +Y 前上方观看。
"""
import argparse
import os
import sys

import bmesh
import bpy
from mathutils import Vector

WIDTH = 0.24      # 板宽(米)
THICK = 0.035     # 最大浮雕厚度(米)


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--albedo", required=True)
    p.add_argument("--height", required=True)
    p.add_argument("--engine", default="auto", choices=["auto", "EEVEE", "CYCLES"])
    p.add_argument("--samples", type=int, default=64)
    p.add_argument("--out", required=True)
    return p.parse_args(argv)


def clean_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for m in list(bpy.data.materials):
        bpy.data.materials.remove(m)


def resolve_engine(name):
    if bpy.app.version >= (5, 0, 0):
        eevee = "BLENDER_EEVEE"
    elif bpy.app.version >= (4, 2, 0):
        eevee = "BLENDER_EEVEE_NEXT"
    else:
        eevee = "BLENDER_EEVEE"
    if name == "CYCLES":
        return "CYCLES"
    return eevee


def make_textured_material(name, image_path, base_color=(1, 1, 1, 1)):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(image_path)
    mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.6
    return mat


def build_relief(args):
    img = bpy.data.images.load(args.height)
    gw, gh = img.size
    px = list(img.pixels)  # RGBA, 0..1

    def depth_at(col, row):
        return px[(row * gw + col) * 4]

    bpy.ops.mesh.primitive_grid_add(size=2.0, x_subdivisions=gw - 1,
                                    y_subdivisions=gh - 1, location=(0, 0, 0))
    obj = bpy.context.object
    obj.name = "PersonRelief"

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    uv_layer = bm.loops.layers.uv.get("UVMap")
    if uv_layer is None:
        uv_layer = bm.loops.layers.uv.new("UVMap")

    H = WIDTH * (gh / gw)  # 板高按图片比例
    for v in bm.verts:
        u = v.co.x / 2.0 + 0.5            # 0..1 横向
        vv = v.co.y / 2.0 + 0.5           # 0 底 .. 1 顶
        col = int(round(u * (gw - 1)))
        row = int(round((1.0 - vv) * (gh - 1)))
        col = max(0, min(gw - 1, col))
        row = max(0, min(gh - 1, row))
        d = depth_at(col, row)
        nx = (v.co.x / 2.0) * WIDTH
        ny = d * THICK
        nz = (v.co.y / 2.0) * H + H / 2.0  # 底在 z=0
        v.co = Vector((nx, ny, nz))
        for loop in v.link_loops:
            loop[uv_layer].uv = (u, vv)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    bm.to_mesh(obj.data)
    bm.free()

    mat = make_textured_material("mat_relief", args.albedo)
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
    return obj, H


def setup(obj, H):
    scene = bpy.context.scene
    center = Vector((0, 0, H / 2))
    dist = max(WIDTH, H) * 1.5

    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    cam.location = center + Vector((0.0, dist * 1.0, dist * 0.55))
    cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam

    key = bpy.data.objects.new("Key", bpy.data.lights.new("Key", type="AREA"))
    key.data.energy, key.data.size = 90.0, 1.2
    scene.collection.objects.link(key)
    key.location = center + Vector((dist * 0.5, dist * 0.8, dist * 1.3))

    fill = bpy.data.objects.new("Fill", bpy.data.lights.new("Fill", type="AREA"))
    fill.data.energy, fill.data.size = 20.0, 2.0
    scene.collection.objects.link(fill)
    fill.location = center + Vector((0.0, -dist * 0.6, dist * 1.2))

    world = bpy.data.worlds.new("Studio")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.04, 0.04, 0.05, 1.0)

    # 地面
    bpy.ops.mesh.primitive_plane_add(size=dist * 6, location=(0, 0, 0))
    ground = bpy.context.object
    gm = bpy.data.materials.new("mat_ground")
    gm.use_nodes = True
    gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.8, 0.8, 0.82, 1)
    ground.data.materials.append(gm)


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
    except Exception as exc:
        print("[WARN] glTF 导出失败:", exc)


def main():
    args = parse_args()
    clean_scene()
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    obj, H = build_relief(args)
    setup(obj, H)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    render(scene, args.out + "_front.png", resolve_engine(args.engine), args.samples)
    print("[OK] rendered ->", args.out + "_front.png")
    export_glb(obj, args.out + ".glb")


main()
