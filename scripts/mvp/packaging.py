#!/usr/bin/env python
"""M4/M5：参数化包装结构模板 + 贴图/材质 + UV 越界检查（Blender 脚本）。

模板：tuck_box_std / tuck_box_hang / sleeve_std / sleeve_open / pouch_standup / pouch_zipper
输入：场景 JSON（scripts/mvp/schema.py 定义）
输出：GLB + BLEND + UV 检查报告 JSON
运行：blender --background --python scripts/mvp/packaging.py -- --scene-json <scene.json> --out output/mvp/product
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
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MATERIALS = {
    "matte_paper": ((0.95, 0.94, 0.91, 1), 0.78, 0.0),
    "gloss_film": ((0.97, 0.97, 0.97, 1), 0.18, 0.0),
    "foil_silver": ((0.87, 0.87, 0.87, 1), 0.22, 1.0),
    "foil_gold": ((0.91, 0.77, 0.42, 1), 0.25, 1.0),
    "uncoated": ((0.94, 0.92, 0.88, 1), 0.9, 0.0),
    "transparent": ((1, 1, 1, 1), 0.1, 0.0),
    "metal_steel": ((0.79, 0.80, 0.82, 1), 0.28, 1.0),
    "metal_brushed": ((0.71, 0.73, 0.76, 1), 0.45, 1.0),
}


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--scene-json", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--texture", help="贴图素材（png/jpg/webp），保持原图不改写")
    return p.parse_args(argv)


def clean_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def make_panel(name, quad, thickness_mm):
    """quad: 4 个世界坐标(米)。生成带厚度的面板对象。"""
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    bm = bmesh.new()
    verts = [bm.verts.new(Vector(q)) for q in quad]
    bm.faces.new(verts)
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    uv = mesh.uv_layers.new(name="UVMap")
    for i, loop in enumerate(mesh.loops):
        uv.data[i].uv = [(0, 0), (1, 0), (1, 1), (0, 1)][loop.vertex_index % 4]
    md = obj.modifiers.new("solidify", "SOLIDIFY")
    md.thickness = max(thickness_mm * MM, 0.0002)
    return obj


def make_material(name, preset, texture_path=None):
    color, rough, metal = MATERIALS.get(preset, MATERIALS["matte_paper"])
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    print("  material=%s texture=%s" % (preset, texture_path or "-"))
    if texture_path and os.path.exists(texture_path):
        # 品牌锁定：直接使用原图作为贴图，不做任何像素改写
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(texture_path)
        mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    return mat


def box_structure(W, D, H, t):
    """反向插扣盒：4 侧板 + 半开顶 flap + 底 flap + 粘口。返回 (name, quad) 列表。"""
    w, d, h = W * MM, D * MM, H * MM
    f = d / 2 * math.cos(math.radians(45))   # 45° 半开 flap 投影
    fz = d / 2 * math.sin(math.radians(45))
    panels = [
        ("front_panel", [(-w/2, -d/2, 0), (w/2, -d/2, 0), (w/2, -d/2, h), (-w/2, -d/2, h)]),
        ("back_panel",  [(-w/2, d/2, 0), (w/2, d/2, 0), (w/2, d/2, h), (-w/2, d/2, h)]),
        ("left_panel",  [(-w/2, -d/2, 0), (-w/2, d/2, 0), (-w/2, d/2, h), (-w/2, -d/2, h)]),
        ("right_panel", [(w/2, -d/2, 0), (w/2, d/2, 0), (w/2, d/2, h), (w/2, -d/2, h)]),
        # 顶部 flap（45° 半开，前后各一）
        ("top_flap_front", [(-w/2, -d/2, h), (w/2, -d/2, h), (w/2, -d/2 - f, h + fz), (-w/2, -d/2 - f, h + fz)]),
        ("top_flap_back",  [(-w/2, d/2, h), (w/2, d/2, h), (w/2, d/2 + f, h + fz), (-w/2, d/2 + f, h + fz)]),
        # 底部 flap（水平，向内折）
        ("bottom_flap_front", [(-w/2, -d/2, 0), (w/2, -d/2, 0), (w/2, 0, 0), (-w/2, 0, 0)]),
        ("bottom_flap_back",  [(-w/2, d/2, 0), (w/2, d/2, 0), (w/2, 0, 0), (-w/2, 0, 0)]),
        # 粘口（贴在右侧板内侧前缘）
        ("glue_tab", [(w/2 - 0.002, -d/2, 0.01), (w/2 - 0.002, -d/2 + 0.012, 0.01),
                      (w/2 - 0.002, -d/2 + 0.012, h - 0.01), (w/2 - 0.002, -d/2, h - 0.01)]),
    ]
    return panels


def milk_carton_structure(W, D, H, t):
    """牛奶盒（屋顶盒 gable-top）：4 侧板 + 前后斜面屋顶 + 脊封口 + 底封。"""
    w, d, h = W * MM, D * MM, H * MM
    roof = d / 2
    zr = h + roof
    return [
        ("front_panel", [(-w/2, -d/2, 0), (w/2, -d/2, 0), (w/2, -d/2, h), (-w/2, -d/2, h)]),
        ("back_panel",  [(-w/2, d/2, 0), (w/2, d/2, 0), (w/2, d/2, h), (-w/2, d/2, h)]),
        ("left_panel",  [(-w/2, -d/2, 0), (-w/2, d/2, 0), (-w/2, d/2, h), (-w/2, -d/2, h)]),
        ("right_panel", [(w/2, -d/2, 0), (w/2, d/2, 0), (w/2, d/2, h), (w/2, -d/2, h)]),
        ("roof_front", [(-w/2, -d/2, h), (w/2, -d/2, h), (w/2, 0, zr), (-w/2, 0, zr)]),
        ("roof_back",  [(-w/2, d/2, h), (w/2, d/2, h), (w/2, 0, zr), (-w/2, 0, zr)]),
        ("roof_ridge", [(-w/2, -0.004, zr), (w/2, -0.004, zr), (w/2, 0.004, zr), (-w/2, 0.004, zr)]),
        ("bottom_seal", [(-w/2, -d/2, 0), (w/2, -d/2, 0), (w/2, d/2, 0), (-w/2, d/2, 0)]),
    ]


def sleeve_structure(W, D, H, t):
    w, d, h = W * MM, D * MM, H * MM
    return [
        ("front_panel", [(-w/2, -d/2, 0), (w/2, -d/2, 0), (w/2, -d/2, h), (-w/2, -d/2, h)]),
        ("back_panel",  [(-w/2, d/2, 0), (w/2, d/2, 0), (w/2, d/2, h), (-w/2, d/2, h)]),
        ("left_panel",  [(-w/2, -d/2, 0), (-w/2, d/2, 0), (-w/2, d/2, h), (-w/2, -d/2, h)]),
        ("right_panel", [(w/2, -d/2, 0), (w/2, d/2, 0), (w/2, d/2, h), (w/2, -d/2, h)]),
        ("inner_box",   [(-w/2 + 0.003, -d/2 + 0.003, 0.005), (w/2 - 0.003, -d/2 + 0.003, 0.005),
                         (w/2 - 0.003, d/2 - 0.003, 0.005), (-w/2 + 0.003, d/2 - 0.003, 0.005)]),
    ]


def pouch_structure(W, D, H, t):
    """立式袋：前后片 + 底片 + 两侧折片 + 顶部封口条。"""
    w, d, h = W * MM, D * MM, H * MM
    return [
        ("front_panel", [(-w/2, -d/2, 0), (w/2, -d/2, 0), (w/2, -d/2, h), (-w/2, -d/2, h)]),
        ("back_panel",  [(-w/2, d/2, 0), (w/2, d/2, 0), (w/2, d/2, h), (-w/2, d/2, h)]),
        ("bottom_gusset", [(-w/2, -d/2, 0), (w/2, -d/2, 0), (w/2, d/2, 0), (-w/2, d/2, 0)]),
        ("side_gusset_left", [(-w/2, -d/2, 0), (-w/2, 0, 0), (-w/2, 0, h), (-w/2, -d/2, h)]),
        ("side_gusset_right", [(w/2, -d/2, 0), (w/2, 0, 0), (w/2, 0, h), (w/2, -d/2, h)]),
        ("top_seal", [(-w/2, -d/2, h), (w/2, -d/2, h), (w/2, d/2, h), (-w/2, d/2, h)]),
    ]


def build_structure(template, W, D, H, t):
    if template == "milk_carton":
        return milk_carton_structure(W, D, H, t)
    if template.startswith("tuck_box"):
        return box_structure(W, D, H, t)
    if template.startswith("sleeve"):
        return sleeve_structure(W, D, H, t)
    return pouch_structure(W, D, H, t)


def uv_check(objects):
    total = out = 0
    for o in objects:
        if o.type != "MESH" or not o.data.uv_layers:
            continue
        uv = o.data.uv_layers.active.data
        for loop in uv:
            total += 1
            u, v = loop.uv
            if not (-0.001 <= u <= 1.001 and -0.001 <= v <= 1.001):
                out += 1
    return {"total_uv": total, "out_of_range": out,
            "ratio": (out / total if total else 0.0)}


def main():
    args = parse_args()
    with open(args.scene_json, encoding="utf-8") as f:
        scene = json.load(f)
    clean_scene()
    bpy.context.scene.unit_settings.system = "METRIC"

    st = scene["structure"]
    W = st["dimensions_mm"]["width"]
    D = st["dimensions_mm"]["depth"]
    H = st["dimensions_mm"]["height"]
    t = st.get("paper_thickness_mm", 0.45)
    template = st["template"]

    mat = make_material("mat_" + scene["material"]["preset"], scene["material"]["preset"],
                        getattr(args, "texture", None))
    objs = []
    for name, quad in build_structure(template, W, D, H, t):
        o = make_panel(name, quad, t)
        o.data.materials.append(mat)
        objs.append(o)

    # 挂孔（tuck_box_hang）：顶部 flap 上开圆孔
    if template == "tuck_box_hang":
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.004,
                                            depth=D * MM, location=(0, -D * MM / 2, H * MM + 0.02))
        hole = bpy.context.object
        hole.rotation_euler = (math.pi / 2, 0, 0)
        target = bpy.data.objects.get("top_flap_front")
        if target:
            bpy.context.view_layer.objects.active = target
            md = target.modifiers.new("hole", "BOOLEAN")
            md.operation = "DIFFERENCE"; md.object = hole
            bpy.ops.object.modifier_apply(modifier=md.name)
        bpy.data.objects.remove(hole, do_unlink=True)

    # 开窗（sleeve_open）：前面板开窗
    if template == "sleeve_open":
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -D * MM / 2, H * MM / 2))
        win = bpy.context.object
        win.scale = (W * MM * 0.5, 0.004, H * MM * 0.5)
        target = bpy.data.objects.get("front_panel")
        if target:
            bpy.context.view_layer.objects.active = target
            md = target.modifiers.new("window", "BOOLEAN")
            md.operation = "DIFFERENCE"; md.object = win
            bpy.ops.object.modifier_apply(modifier=md.name)
        bpy.data.objects.remove(win, do_unlink=True)

    # 拉链条（pouch_zipper）
    if template == "pouch_zipper":
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, H * MM + 0.004))
        z = bpy.context.object
        z.name = "zipper_strip"
        z.scale = (W * MM, D * MM * 0.25, 0.003)
        z.data.materials.append(mat)
        objs.append(z)

    report = uv_check(objs)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out + "_uv_check.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    try:
        bpy.ops.preferences.addon_enable(module="io_scene_gltf2")
    except Exception:
        pass
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=args.out + ".glb", export_format="GLB")
    bpy.ops.wm.save_as_mainfile(filepath=args.out + ".blend")
    print("[OK] template=%s objects=%d UV越界=%d/%d(%.2f%%)" % (
        template, len(objs), report["out_of_range"], report["total_uv"], report["ratio"] * 100))


main()
