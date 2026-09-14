#!/usr/bin/env python
"""从刀模图提取结构尺寸，生成正确的纸盒（礼盒：盒身 + 盒盖）+ 图案贴图。

与"盲目折叠"不同：先解析刀模的折线分布，提取真实尺寸(宽/深/高)，
再按纸盒结构生成几何（盒身 4 壁 + 底，盒盖 4 壁 + 顶），保证成品是正确纸盒。

运行：blender --background --python scripts/mvp/box_from_dieline.py -- \
      --svg assets/industrial/templatemaker_giftbox.svg --out output/box_model \
      --texture output/dieline_artwork_alpha.png [--gap 10] [--lid-h 60]
"""
import argparse
import math
import os
import re
import sys

import bpy

MM = 0.001


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--svg", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--texture", default=None)
    p.add_argument("--gap", type=float, default=10.0, help="盒盖抬起距离(mm)")
    p.add_argument("--lid-h", type=float, default=60.0, help="盒盖高度(mm)")
    p.add_argument("--wall", type=float, default=2.0, help="盖与盒身间隙(mm)")
    return p.parse_args(argv)


def extract_dims(svg_path):
    """从刀模折线提取结构尺寸(mm)。"""
    s = open(svg_path, encoding="utf-8", errors="ignore").read()
    fold = []
    for m in re.finditer(r"<g\b([^>]*)>(.*?)</g>", s, re.S | re.I):
        attrs, body = m.group(1), m.group(2)
        if not re.search(r"fold|crease|score", attrs, re.I):
            continue
        for d in re.findall(r"<path\b[^>]*\bd=[\"']([^\"']+)[\"']", body, re.I):
            pts = [(float(x), float(y)) for _, x, y in
                   re.findall(r"([ML])\s*([-\d.]+)[ ,]+([-\d.]+)", d, re.I)]
            fold += [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    vx, hy = [], []
    for (x1, y1), (x2, y2) in fold:
        if abs(x1 - x2) < 1:
            vx.append(round((x1 + x2) / 2, 1))
        elif abs(y1 - y2) < 1:
            hy.append(round((y1 + y2) / 2, 1))
    vx, hy = sorted(set(vx)), sorted(set(hy))
    vgaps = [round(b - a, 1) for a, b in zip(vx, vx[1:])]
    hgaps = [round(b - a, 1) for a, b in zip(hy, hy[1:])]
    W = max(vgaps) if vgaps else 300.0                 # 正面宽度
    D = min(vgaps) if vgaps else 200.0                 # 侧板深度(取较小主段)
    H = sorted(hgaps)[len(hgaps) // 2] if hgaps else 170.0   # 盒高中位段
    return {"width": W, "depth": D, "height": H, "vgaps": vgaps, "hgaps": hgaps}


def clean():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def make_mat(texture):
    mat = bpy.data.materials.new("box_mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if texture and os.path.exists(texture):
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(texture)
        mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        if tex.image.channels == 4:
            mat.node_tree.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
            for attr, val in (("blend_method", "BLEND"), ("surface_render_method", "BLENDED")):
                try:
                    setattr(mat, attr, val)
                except Exception:
                    pass
    else:
        bsdf.inputs["Base Color"].default_value = (0.85, 0.72, 0.5, 1)
    bsdf.inputs["Roughness"].default_value = 0.6
    return mat


def add_box(name, w, d, h, z0, mat):
    """用 bmesh 逐面构建盒体（每面 UV 0..1，图案完整显示）。"""
    import bmesh
    from mathutils import Vector
    W, D, H, Z = w * MM, d * MM, h * MM, z0 * MM
    x0, x1 = -W / 2, W / 2
    y0, y1 = -D / 2, D / 2
    z0m, z1m = Z, Z + H
    quads = {
        "front": [(x0, y0, z0m), (x1, y0, z0m), (x1, y0, z1m), (x0, y0, z1m)],
        "back":  [(x0, y1, z0m), (x1, y1, z0m), (x1, y1, z1m), (x0, y1, z1m)],
        "left":  [(x0, y0, z0m), (x0, y1, z0m), (x0, y1, z1m), (x0, y0, z1m)],
        "right": [(x1, y0, z0m), (x1, y1, z0m), (x1, y1, z1m), (x1, y0, z1m)],
        "top":   [(x0, y0, z1m), (x1, y0, z1m), (x1, y1, z1m), (x0, y1, z1m)],
        "bottom":[(x0, y0, z0m), (x1, y0, z0m), (x1, y1, z0m), (x0, y1, z0m)],
    }
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    corners = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    for tag, quad in quads.items():
        vs = [bm.verts.new(Vector(q)) for q in quad]
        try:
            f = bm.faces.new(vs)
        except ValueError:
            continue
        for i, loop in enumerate(f.loops):
            loop[uv].uv = corners[i]
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    obj.data.materials.append(mat)
    return obj

def main():
    args = parse_args()
    dims = extract_dims(args.svg)
    W, D, H = dims["width"], dims["depth"], dims["height"]
    print("[尺寸提取] W=%.1f D=%.1f H=%.1f mm  (垂直段%s / 水平段%s)"
          % (W, D, H, dims["vgaps"], dims["hgaps"]))

    clean()
    bpy.context.scene.unit_settings.system = "METRIC"
    mat = make_mat(args.texture)

    # 盒身：4 壁 + 底（用一个封闭立方体表示）
    body = add_box("Box_Body", W, D, H, 0.0, mat)
    # 盒盖：略大，抬起 gap 形成"打开的礼盒"
    lid = add_box("Box_Lid", W + 2 * args.wall, D + 2 * args.wall, args.lid_h,
                  H + args.gap, mat)

    try:
        bpy.ops.preferences.addon_enable(module="io_scene_gltf2")
    except Exception:
        pass
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=args.out + ".glb", export_format="GLB")
    bpy.ops.wm.save_as_mainfile(filepath=args.out + ".blend")

    # ---- 直接渲染（不经过 GLB 往返，确保贴图生效）----
    from mathutils import Vector
    scene = bpy.context.scene
    total_h = H + args.gap + args.lid_h
    center = Vector((0, 0, total_h / 2 * MM))
    radius = max(W, D, total_h) * MM

    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.location = center + Vector((radius * 2.2, -radius * 2.6, radius * 1.8))
    cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()

    key = bpy.data.objects.new("Key", bpy.data.lights.new("Key", type="AREA"))
    key.data.energy, key.data.size = 80.0, radius * 4
    scene.collection.objects.link(key)
    key.location = center + Vector((radius * 2, -radius * 2, radius * 3))

    fill = bpy.data.objects.new("Fill", bpy.data.lights.new("Fill", type="AREA"))
    fill.data.energy, fill.data.size = 30.0, radius * 6
    scene.collection.objects.link(fill)
    fill.location = center + Vector((-radius, radius, radius * 2))

    world = bpy.data.worlds.new("W")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.35, 0.35, 0.38, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.6

    bpy.ops.mesh.primitive_plane_add(size=radius * 12, location=(0, 0, 0))
    ground = bpy.context.object
    gm = bpy.data.materials.new("ground")
    gm.use_nodes = True
    gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.5, 0.5, 0.52, 1)
    ground.data.materials.append(gm)

    scene.render.engine = "BLENDER_EEVEE" if bpy.app.version >= (5, 0, 0) else "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x, scene.render.resolution_y = 1200, 1200
    scene.render.image_settings.file_format = "PNG"
    for tag, off in (("front", (0, -1, 0.35)), ("quarter", (0.9, -1, 0.5)), ("top", (0.3, -0.6, 1.4))):
        d = Vector(off).normalized()
        cam.location = center + d * radius * 3.0
        cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = args.out + "_" + tag + ".png"
        bpy.ops.render.render(write_still=True)
        print("[OK] render ->", args.out + "_" + tag + ".png")

    print("[OK] 纸盒模型: %s.glb (盒身 %.0fx%.0fx%.0f + 盒盖)" % (args.out, W, D, H))


main()
