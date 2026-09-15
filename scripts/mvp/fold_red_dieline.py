#!/usr/bin/env python
"""按"红色虚线=折线"折叠位图展开图为盒形。

流程：检测红色虚线 → 聚类出垂直/水平折线 → 构建网格面板 → 以中央面板为底、
按相邻层级交替折向(±90°) → 生成 3D(每面板 UV 对应原图区域，非整图贴图) → 渲染。

运行：blender --background --python scripts/mvp/fold_red_dieline.py -- \
      --image assets/dieline_2018.jpg --out output/box_red --scale-mm 1.0 [--angle 90]
"""
import argparse
import collections
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

MM = 0.001


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--image", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--angle", type=float, default=90.0)
    p.add_argument("--scale-mm", type=float, default=1.0, help="像素->毫米比例")
    p.add_argument("--min-gap", type=int, default=25, help="折线最小间距(像素)")
    p.add_argument("--cols", type=int, default=4, help="盒壁面板数(垂直折线=cols-1)")
    p.add_argument("--rows", type=int, default=3, help="行数(上片/盒身/下片)")
    p.add_argument("--vbounds", default="", help="指定垂直折线x,逗号分隔")
    p.add_argument("--hbounds", default="", help="指定水平折线y,逗号分隔")
    return p.parse_args(argv)


def detect_folds(img_path, min_gap=25):
    """用 Blender 原生图像读取（无需 PIL），检测红色虚线。"""
    import numpy as np
    img = bpy.data.images.load(img_path)
    w, h = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
    rgb = (px[:, :, :3] * 255.0)[::-1, :, :]      # y 翻转为常规图像坐标
    R, G, B = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    red = (R > 130) & (R - np.maximum(G, B) > 40)
    h, w = red.shape

    def runs(line):
        out = []; cur = 0
        for v in line:
            if v: cur += 1
            elif cur: out.append(cur); cur = 0
        if cur: out.append(cur)
        return out

    def dashish(line, min_px=40):
        idx = np.where(line)[0]
        if len(idx) < min_px:
            return False
        cov = (idx.max() - idx.min() + 1) / len(line)
        r = runs(line)
        if not r:
            return False
        short = sum(1 for x in r if 2 <= x <= 40)
        return cov > 0.5 and short >= max(3, len(r) * 0.5)

    row_hits = [y for y in range(h) if dashish(red[y])]
    col_hits = [x for x in range(w) if dashish(red[:, x])]

    def cluster(idxs, gap=3):
        """聚类相邻行/列；返回 (中心, 厚度)。厚度大的簇是实心块/图案，不是折线。"""
        if not idxs: return []
        groups = [[idxs[0]]]
        for v in idxs[1:]:
            if v - groups[-1][-1] <= gap: groups[-1].append(v)
            else: groups.append([v])
        return [(int(sum(g) / len(g)), len(g)) for g in groups]

    def thin(items, gap, max_thick=4):
        """只保留细线(厚度<=max_thick)并去重(间距>=gap)。"""
        out = []
        for c, t in items:
            if t > max_thick:
                continue
            if not out or c - out[-1] >= gap:
                out.append(c)
        return out

    yc = cluster(row_hits)
    xc = cluster(col_hits)
    print("[簇] 水平簇(中心,厚度):", yc)
    print("[簇] 垂直簇(中心,厚度):", xc)
    ys = thin(yc, min_gap)
    xs = thin(xc, min_gap)
    return xs, ys, (w, h), red


def pick_uniform(values, n):
    """从候选折线中选出 n 个最接近均匀分布的边界（结构折线）。"""
    if len(values) <= n:
        return values
    v0, v1 = values[0], values[-1]
    targets = [v0 + (v1 - v0) * i / (n - 1) for i in range(n)]
    picked = []
    for t in targets:
        best = min(values, key=lambda v: abs(v - t))
        if best not in picked:
            picked.append(best)
    return sorted(picked)


def build_panels(xs, ys, red, min_gap):
    """用折线网格构建面板；只保留含红色(虚线/内容)或处于包围盒内的单元。"""
    import numpy as np
    panels = []
    for j in range(len(ys) - 1):
        for i in range(len(xs) - 1):
            x0, x1 = xs[i], xs[i + 1]
            y0, y1 = ys[j], ys[j + 1]
            if x1 - x0 < min_gap or y1 - y0 < min_gap:
                continue
            sub = red[y0:y1, x0:x1]
            keep = True
            panels.append({"x0": x0, "y0": y0, "x1": x1, "y1": y1, "i": i, "j": j})
    return panels


def fold_and_build(panels, xs, ys, angle_deg, out, scale_mm):
    # 以含面板行/列最多的中心单元作为基准
    if not panels:
        print("[错误] 未构建出面板"); return None
    cx = sum((p["x0"] + p["x1"]) / 2 for p in panels) / len(panels)
    cy = sum((p["y0"] + p["y1"]) / 2 for p in panels) / len(panels)
    base = min(panels, key=lambda p: (abs((p["x0"] + p["x1"]) / 2 - cx) + abs((p["y0"] + p["y1"]) / 2 - cy)))
    print("[基准] 中央面板:", base)

    idx = {(p["i"], p["j"]): p for p in panels}
    # 壁区 = 中间行（用于判定上下折片的折向）
    mid = max(1, (len(ys) - 2) // 2)
    wall_y0, wall_y1 = ys[mid], ys[mid + 1]
    print("[壁区] y ∈ [%d, %d]（中间行为四壁）" % (wall_y0, wall_y1))
    transforms = {(base["i"], base["j"]): Matrix.Identity(4)}
    depth = {(base["i"], base["j"]): 0}
    queue = collections.deque([(base["i"], base["j"])])
    ang = math.radians(angle_deg)

    def fold_axis(a, b, vertical):
        """返回折叠轴的两个端点(图像坐标)。"""
        if vertical:
            x = xs[max(a[0], b[0])]
            y0 = max(a[1], b[1]) and min(a[1], b[1])
            # 折线竖向：用两个面板的公共 x，y 范围取两者并集
            ya = ys[a[1]]; yb = ys[a[1] + 1]
            yc = ys[b[1]]; yd = ys[b[1] + 1]
            return (x, max(ya, yc)), (x, min(yb, yd))
        else:
            y = ys[max(a[1], b[1])]
            xa = xs[a[0]]; xb = xs[a[0] + 1]
            xc = xs[b[0]]; xd = xs[b[0] + 1]
            return (max(xa, xc), y), (min(xb, xd), y)

    while queue:
        key = queue.popleft()
        M = transforms[key]
        d = depth[key]
        i, j = key
        for (ni, nj, vertical) in ((i + 1, j, True), (i - 1, j, True), (i, j + 1, False), (i, j - 1, False)):
            nk = (ni, nj)
            if nk not in idx or nk in transforms:
                continue
            p1img, p2img = fold_axis(key, nk, vertical)
            p1 = M @ Vector((p1img[0] * scale_mm * MM, -p1img[1] * scale_mm * MM, 0.0))
            p2 = M @ Vector((p2img[0] * scale_mm * MM, -p2img[1] * scale_mm * MM, 0.0))
            axis = p2 - p1
            if axis.length < 1e-9:
                continue
            if vertical:
                sign = 1.0                      # 垂直折线：围成筒
            else:
                fy = ys[max(i, ni) if False else max(j, nj)]
                if fy <= wall_y0:
                    sign = -1.0                 # 上部折片(盖/插舌)：向下折
                elif fy >= wall_y1:
                    sign = 1.0                  # 下部折片(底/插舌)：向上折
                else:
                    sign = -1.0
            R = Matrix.Rotation(sign * ang, 4, axis.normalized())
            transforms[nk] = Matrix.Translation(p1) @ R @ Matrix.Translation(-p1) @ M
            depth[nk] = d + 1
            queue.append(nk)

    # 建网格
    mesh = bpy.data.meshes.new("RedFold")
    obj = bpy.data.objects.new("RedFold", mesh)
    bpy.context.scene.collection.objects.link(obj)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    corners_uv = [(0, 0), (1, 0), (1, 1), (0, 1)]
    W = xs[-1]; H = ys[-1]
    for p in panels:
        k = (p["i"], p["j"])
        M = transforms.get(k)
        if M is None:
            continue
        pts = [(p["x0"], p["y0"]), (p["x1"], p["y0"]), (p["x1"], p["y1"]), (p["x0"], p["y1"])]
        vs = [bm.verts.new(M @ Vector((x * scale_mm * MM, -y * scale_mm * MM, 0.0))) for (x, y) in pts]
        try:
            f = bm.faces.new(vs)
        except ValueError:
            continue
        for li, loop in enumerate(f.loops):
            u = pts[li][0] / W
            v = 1.0 - pts[li][1] / H
            loop[uv].uv = (u, v)
    bm.normal_update(); bm.to_mesh(mesh); bm.free()
    print("[OK] 面板=%d 折叠深度=%d 最大层=%d" % (len(obj.data.polygons), len(transforms), max(depth.values())))

    zs = [v.co.z for v in obj.data.vertices]
    xs3 = [v.co.x for v in obj.data.vertices]; ys3 = [v.co.y for v in obj.data.vertices]
    print("[自检] 3D 包围盒 X=%.3f Y=%.3f Z=%.3f m" % (max(xs3) - min(xs3), max(ys3) - min(ys3), max(zs) - min(zs)))
    return obj


def main():
    args = parse_args()
    xs, ys, (w, h), red = detect_folds(args.image, args.min_gap)
    print("[折线] 垂直 x:", xs)
    print("[折线] 水平 y:", ys)
    if args.vbounds:
        xs = [int(v) for v in args.vbounds.split(",") if v.strip()]
    else:
        xs = pick_uniform(xs, args.cols + 1)
    if args.hbounds:
        ys = [int(v) for v in args.hbounds.split(",") if v.strip()]
    else:
        ys = pick_uniform(ys, args.rows + 1)
    print("[结构折线] 垂直 x:", xs)
    print("[结构折线] 水平 y:", ys)
    panels = build_panels(xs, ys, red, args.min_gap)
    print("[面板] 构建 %d 个面板" % len(panels))
    obj = fold_and_build(panels, xs, ys, args.angle, args.out, args.scale_mm)
    if obj is None:
        return
    # 贴图（原图）
    mat = bpy.data.materials.new("dieline_mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(args.image)
    mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.6
    obj.data.materials.append(mat)

    # 导出模型（GLB + BLEND）
    try:
        bpy.ops.preferences.addon_enable(module="io_scene_gltf2")
    except Exception:
        pass
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(filepath=args.out + ".glb", export_format="GLB", use_selection=True)
    bpy.ops.wm.save_as_mainfile(filepath=args.out + ".blend")
    print("[OK] 导出 ->", args.out + ".glb")

    # 相机/灯光/渲染
    from mathutils import Vector as V
    scene = bpy.context.scene
    zs = [v.co.z for v in obj.data.vertices]
    xs3 = [v.co.x for v in obj.data.vertices]; ys3 = [v.co.y for v in obj.data.vertices]
    center = V(((max(xs3) + min(xs3)) / 2, (max(ys3) + min(ys3)) / 2, (max(zs) + min(zs)) / 2))
    radius = max(max(xs3) - min(xs3), max(ys3) - min(ys3), max(zs) - min(zs))
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam); scene.camera = cam
    key = bpy.data.objects.new("Key", bpy.data.lights.new("Key", type="AREA"))
    key.data.energy, key.data.size = 60.0, radius * 4
    scene.collection.objects.link(key); key.location = center + V((radius, -radius, radius * 2))
    fill = bpy.data.objects.new("Fill", bpy.data.lights.new("Fill", type="AREA"))
    fill.data.energy, fill.data.size = 25.0, radius * 6
    scene.collection.objects.link(fill); fill.location = center + V((-radius, radius, radius * 2))
    world = bpy.data.worlds.new("W"); scene.world = world; world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.35, 0.35, 0.38, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.7
    scene.render.engine = "BLENDER_EEVEE" if bpy.app.version >= (5, 0, 0) else "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = scene.render.resolution_y = 1000
    scene.render.image_settings.file_format = "PNG"
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    for tag, off in (("front", (0, -1, 0.4)), ("quarter", (0.9, -1, 0.65)), ("top", (0.3, -0.5, 1.3))):
        d = V(off).normalized()
        cam.location = center + d * radius * 2.6
        cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = args.out + "_" + tag + ".png"
        bpy.ops.render.render(write_still=True)
        print("[OK] render ->", args.out + "_" + tag + ".png")


main()
