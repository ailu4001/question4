#!/usr/bin/env python
"""生成一个可直接用 Blender 打开查看的 .blend（导入 glb + 相机 + 灯光 + 地面）。"""
import argparse
import sys
import bpy
from mathutils import Vector


def main():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=a.glb)

    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    print("imported meshes:", len(meshes))
    bbox = None
    for o in meshes:
        box = o.bound_box  # local 8 corners
        for c in box:
            wc = o.matrix_world @ Vector(c)
            if bbox is None:
                bbox = [list(wc), list(wc)]
            else:
                for i in range(3):
                    bbox[0][i] = min(bbox[0][i], wc[i])
                    bbox[1][i] = max(bbox[1][i], wc[i])
    if bbox is None:
        print("no mesh"); return
    mn, mx = Vector(bbox[0]), Vector(bbox[1])
    center = (mn + mx) / 2
    radius = (mx - mn).length / 2
    print("center", center, "radius", radius)

    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    # 相机
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    dist = max(radius * 3.0, 0.1)
    cam.location = center + Vector((dist * 0.8, dist * 1.2, dist * 0.9))
    cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
    # 灯光
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", type="SUN"))
    sun.data.energy = 3.0
    sun.rotation_euler = (0.8, 0.2, 0.5)
    scene.collection.objects.link(sun)
    fill = bpy.data.objects.new("Fill", bpy.data.lights.new("Fill", type="AREA"))
    fill.data.energy, fill.data.size = 60.0, 2.0
    scene.collection.objects.link(fill)
    fill.location = center + Vector((0, 0, radius * 3))
    # 世界背景
    if scene.world is None:
        scene.world = bpy.data.worlds.new("W")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.05, 0.06, 1)
    # 地面
    bpy.ops.mesh.primitive_plane_add(size=radius * 10, location=(mn.x, mn.y, mn.z - 0.0001))
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    bpy.ops.wm.save_as_mainfile(filepath=a.out)
    print("[OK] saved ->", a.out)


main()
