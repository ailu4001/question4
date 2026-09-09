#!/usr/bin/env python
"""从 GLB 渲染多视角清晰展示图（修复脚本直出 PNG 全白/全黑问题）。

用法: blender --background --python scripts/render_glb.py -- \
      --glb output/housing.glb --out output/housing_v2 --res 1600
"""
import argparse
import os
import sys

import bpy
from mathutils import Vector


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--glb", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--res", type=int, default=1600)
    p.add_argument("--engine", default="auto", choices=["auto", "EEVEE", "CYCLES"])
    return p.parse_args(argv)


def clean_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def scene_bounds():
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    bbox = None
    for o in meshes:
        for c in o.bound_box:
            wc = o.matrix_world @ Vector(c)
            if bbox is None:
                bbox = [list(wc), list(wc)]
            else:
                for i in range(3):
                    bbox[0][i] = min(bbox[0][i], wc[i])
                    bbox[1][i] = max(bbox[1][i], wc[i])
    mn, mx = Vector(bbox[0]), Vector(bbox[1])
    return mn, mx, (mn + mx) / 2, (mx - mn).length / 2


def setup_lights_world(center, radius):
    scene = bpy.context.scene
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", type="SUN"))
    sun.data.energy = 5.0
    sun.rotation_euler = (0.85, 0.05, 0.55)
    scene.collection.objects.link(sun)

    key = bpy.data.objects.new("Key", bpy.data.lights.new("Key", type="AREA"))
    key.data.energy = 60.0
    key.data.size = 2.0
    scene.collection.objects.link(key)
    key.location = center + Vector((radius * 1.4, -radius * 1.3, radius * 2.6))

    fill = bpy.data.objects.new("Fill", bpy.data.lights.new("Fill", type="AREA"))
    fill.data.energy = 25.0
    fill.data.size = 5.0
    scene.collection.objects.link(fill)
    fill.location = center + Vector((-radius, radius, radius * 1.8))

    world = bpy.data.worlds.new("Studio")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.09, 0.09, 0.11, 1.0)


def add_ground(mn, radius):
    bpy.ops.mesh.primitive_plane_add(size=radius * 3.0, location=(0, 0, mn.z - 0.0005))
    ground = bpy.context.object
    gm = bpy.data.materials.new("mat_ground")
    gm.use_nodes = True
    gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.35, 0.35, 0.38, 1)
    gm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.8
    ground.data.materials.append(gm)
    return ground


def place_camera(cam, center, dist, direction):
    d = Vector(direction).normalized()
    cam.location = center + d * dist
    cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()


def resolve_engine(name):
    if bpy.app.version >= (5, 0, 0):
        return "CYCLES" if name == "CYCLES" else "BLENDER_EEVEE"
    if bpy.app.version >= (4, 2, 0):
        return "CYCLES" if name == "CYCLES" else "BLENDER_EEVEE_NEXT"
    return "CYCLES" if name == "CYCLES" else "BLENDER_EEVEE"


def main():
    args = parse_args()
    clean_scene()
    bpy.ops.import_scene.gltf(filepath=args.glb)
    for o in list(bpy.context.scene.objects):
        nm = o.name.lower()
        if o.type == "MESH" and (nm.startswith("plane") or nm.startswith("ground")):
            bpy.data.objects.remove(o, do_unlink=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"

    mn, mx, center, radius = scene_bounds()
    if radius < 1e-6:
        print("模型包围球为 0，无法取景")
        return
    setup_lights_world(center, radius)
    ground = add_ground(mn, radius)
    ground.hide_viewport = False

    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    scene.render.engine = resolve_engine(args.engine)
    scene.render.resolution_x = args.res
    scene.render.resolution_y = int(args.res * 0.75)
    scene.render.image_settings.file_format = "PNG"

    dist = max(radius * 2.4, 0.06)
    views = [("front", (0.0, 1.0, 0.5)), ("quarter", (1.0, 1.0, 0.8)), ("top", (0.5, 0.9, 1.8))]
    for vname, vdir in views:
        place_camera(cam, center, dist, vdir)
        scene.render.filepath = args.out + "_" + vname + ".png"
        bpy.ops.render.render(write_still=True)
        print("[OK] rendered ->", args.out + "_" + vname + ".png")


main()
