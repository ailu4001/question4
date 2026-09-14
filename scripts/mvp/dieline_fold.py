#!/usr/bin/env python
"""刀模图 → 3D 折叠模型（识别 dieline 的切线/折线并沿折线折叠拼装）。

流程：解析 SVG(线段) → 平面图找最小面(面板) → 折线邻接 → BFS 沿折线旋转折叠 → Blender 网格 + UV → GLB

运行：blender --background --python scripts/mvp/dieline_fold.py -- \
        --svg assets/industrial/templatemaker_giftbox.svg --out output/fold_model [--angle 90]
"""
import argparse
import collections
import math
import os
import re
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

TOL = 1.5          # 顶点合并容差(SVG 单位=mm)


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--svg", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--angle", type=float, default=90.0, help="折线折叠角度(度)")
    p.add_argument("--texture", default=None)
    p.add_argument("--uv-mode", default="planar", choices=["planar", "panel"])
    return p.parse_args(argv)


def parse_svg(path):
    """提取 cut/fold 线段（支持 M/L 路径）。"""
    s = open(path, encoding="utf-8", errors="ignore").read()
    cut, fold = [], []
    for m in re.finditer(r"<g\b([^>]*)>(.*?)</g>", s, re.S | re.I):
        attrs, body = m.group(1), m.group(2)
        if re.search(r"fold|crease|score", attrs, re.I):
            kind = fold
        elif re.search(r"cut|trim|die", attrs, re.I):
            kind = cut
        else:
            continue
        for d in re.findall(r"<path\b[^>]*\bd=[\"']([^\"']+)[\"']", body, re.I):
            pts = [(float(x), float(y)) for _, x, y in
                   re.findall(r"([ML])\s*([-\d.]+)[ ,]+([-\d.]+)", d, re.I)]
            kind.extend((pts[i], pts[i + 1]) for i in range(len(pts) - 1))
    return cut, fold


def on_seg(p, a, b, tol=TOL):
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 < 1e-9:
        return False
    t = ((px - ax) * dx + (py - ay) * dy) / L2
    if t < -0.02 or t > 1.02:
        return False
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy) <= tol


def split_segments(segments, all_points):
    """平面细分：把所有落在该线段上的节点(含 T 型交点)插入并拆分子段。"""
    out = []
    for a, b in segments:
        ka, kb = k(a), k(b)
        on = [p for p in all_points if on_seg(p, ka, kb)]
        on.sort(key=lambda p: (p[0] - ka[0]) ** 2 + (p[1] - ka[1]) ** 2)
        for i in range(len(on) - 1):
            if on[i] != on[i + 1]:
                out.append((on[i], on[i + 1]))
    if not out:
        out = [(k(a), k(b)) for a, b in segments]
    return out


def k(p):
    return (round(p[0] / TOL) * TOL, round(p[1] / TOL) * TOL)


def build_adj(segments):
    adj = collections.defaultdict(set)
    for a, b in segments:
        ka, kb = k(a), k(b)
        if ka != kb:
            adj[ka].add(kb); adj[kb].add(ka)
    return adj


def extract_faces(adj):
    """平面图最小环提取（右手最小转角遍历）。"""
    def ang(u, v):
        return math.atan2(v[1] - u[1], v[0] - u[0])

    visited = set()
    faces = []
    for u in list(adj.keys()):
        for v in list(adj[u]):
            if (u, v) in visited:
                continue
            face = []; cu, cv = u, v
            while (cu, cv) not in visited:
                visited.add((cu, cv)); face.append(cu)
                back = ang(cv, cu)
                nxt = None; best = None
                for w in adj[cv]:
                    if w == cu:
                        continue
                    turn = (ang(cv, w) - back) % (2 * math.pi)
                    if best is None or turn < best:
                        best, nxt = turn, w
                if nxt is None:
                    break
                cu, cv = cv, nxt
                if (cu, cv) == (u, v):
                    break
            if len(face) >= 3:
                faces.append(face)

    def area(f):
        s = 0.0
        for i in range(len(f)):
            x1, y1 = f[i]; x2, y2 = f[(i + 1) % len(f)]
            s += x1 * y2 - x2 * y1
        return abs(s) / 2.0

    uniq = {}
    for f in faces:
        sig = frozenset(f)
        if sig not in uniq or area(f) > area(uniq[sig]):
            uniq[sig] = f
    faces = list(uniq.values())
    faces.sort(key=area, reverse=True)
    # 最大环=外轮廓（无限面），其余为面板
    inner = faces[1:] if len(faces) > 1 else []
    return inner, area


def fold_faces(faces, fold_segments, angle_deg):
    """BFS：以最大面板为基准，沿共享折线旋转子面板。"""
    fold_edges = set()
    for a, b in fold_segments:
        fold_edges.add(frozenset((k(a), k(b))))

    def fedges(f):
        return [frozenset((f[i], f[(i + 1) % len(f)])) for i in range(len(f))]

    n = len(faces)

    def point_in_poly(pt, poly):
        x, y = pt
        inside = False
        m = len(poly)
        for a in range(m):
            x1, y1 = poly[a]; x2, y2 = poly[(a + 1) % m]
            if (y1 > y) != (y2 > y):
                xin = (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1
                if x < xin:
                    inside = not inside
        return inside

    # 邻接：沿每条折线的法向两侧探测所属面板（比边重叠更鲁棒）
    fold_list = [(k(a), k(b)) for a, b in fold_segments]
    adj = collections.defaultdict(list)
    for (f1, f2) in fold_list:
        mx, my = (f1[0] + f2[0]) / 2.0, (f1[1] + f2[1]) / 2.0
        dx, dy = f2[0] - f1[0], f2[1] - f1[1]
        L = math.hypot(dx, dy)
        if L < 1e-6:
            continue
        nx, ny = -dy / L, dx / L
        iA = iB = None
        for i in range(n):
            if point_in_poly((mx + nx * 2.0, my + ny * 2.0), faces[i]):
                iA = i
            if point_in_poly((mx - nx * 2.0, my - ny * 2.0), faces[i]):
                iB = i
        if iA is not None and iB is not None and iA != iB:
            if not any(j == iB for j, _ in adj[iA]):
                adj[iA].append((iB, (f1, f2)))
                adj[iB].append((iA, (f1, f2)))

    if n == 0:
        return [], adj
    all_pts = [p for f in faces for p in f]
    cx0 = sum(p[0] for p in all_pts) / len(all_pts)
    cy0 = sum(p[1] for p in all_pts) / len(all_pts)

    def rank(i):
        f = faces[i]
        cx = sum(p[0] for p in f) / len(f)
        cy = sum(p[1] for p in f) / len(f)
        return math.hypot(cx - cx0, cy - cy0) / (1.0 + len(f))

    base = min(range(n), key=rank)
    print("[基准] base=%d (顶点=%d)" % (base, len(faces[base])))
    transforms = {base: Matrix.Identity(4)}
    depth = {base: 0}
    queue = collections.deque([base])
    ang = math.radians(angle_deg)
    while queue:
        i = queue.popleft()
        Mi = transforms[i]
        d = depth[i]
        sign = 1.0 if (d + 1) % 2 == 1 else -1.0
        for (j, e) in adj[i]:
            if j in transforms:
                continue
            ev = list(e)
            p1 = Mi @ Vector((ev[0][0], -ev[0][1], 0.0))
            p2 = Mi @ Vector((ev[1][0], -ev[1][1], 0.0))
            axis = (p2 - p1)
            if axis.length < 1e-9:
                continue
            R = Matrix.Rotation(sign * ang, 4, axis.normalized())
            M = Matrix.Translation(p1) @ R @ Matrix.Translation(-p1)
            transforms[j] = M @ Mi
            depth[j] = d + 1
            queue.append(j)
    print("[折叠] 层级分布:", dict(sorted(collections.Counter(depth.values()).items())))
    return transforms, adj


def make_mesh(faces, transforms, out_path, texture, bounds, uv_mode="planar"):
    x_min, y_min, x_max, y_max = bounds
    svg_w = max(1e-6, x_max - x_min)
    svg_h = max(1e-6, y_max - y_min)
    for o in list(bpy.context.scene.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    mesh = bpy.data.meshes.new("DielineFold")
    obj = bpy.data.objects.new("DielineFold", mesh)
    bpy.context.scene.collection.objects.link(obj)

    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")
    for idx, f in enumerate(faces):
        M = transforms.get(idx)
        if M is None:
            continue
        verts = []
        for (x, y) in f:
            v3 = M @ Vector((x, -y, 0.0)) * 0.001     # mm -> m
            verts.append(bm.verts.new(v3))
        try:
            face = bm.faces.new(verts)
        except ValueError:
            continue
        bm.normal_update()
        for li, loop in enumerate(face.loops):
            x, y = faces[idx][li % len(faces[idx])]
            if uv_mode == "panel":
                px = [q[0] for q in faces[idx]]; py = [q[1] for q in faces[idx]]
                u = (x - min(px)) / max(1e-6, max(px) - min(px))
                v = 1.0 - (y - min(py)) / max(1e-6, max(py) - min(py))
            else:
                u = (x - x_min) / svg_w
                v = 1.0 - (y - y_min) / svg_h
            loop[uv_layer].uv = (u, v)
    bm.to_mesh(mesh); bm.free()

    mat = bpy.data.materials.new("fold_mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if texture and os.path.exists(texture):
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(texture)
        mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        if tex.image.channels == 4:                    # 带 alpha：白底透明
            mat.node_tree.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
            try:
                mat.blend_method = "BLEND"
            except Exception:
                pass
            try:
                mat.surface_render_method = "BLENDED"
            except Exception:
                pass
    else:
        bsdf.inputs["Base Color"].default_value = (0.82, 0.84, 0.88, 1)
    bsdf.inputs["Roughness"].default_value = 0.45
    obj.data.materials.append(mat)

    try:
        bpy.ops.preferences.addon_enable(module="io_scene_gltf2")
    except Exception:
        pass
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(filepath=out_path + ".glb", export_format="GLB", use_selection=True)
    bpy.ops.wm.save_as_mainfile(filepath=out_path + ".blend")
    return obj


def main():
    args = parse_args()
    cut, fold = parse_svg(args.svg)
    print("[解析] cut 线段=%d, fold 线段=%d" % (len(cut), len(fold)))
    allpts = list({k(p) for seg in (cut + fold) for p in seg})
    cut = split_segments(cut, allpts)
    fold = split_segments(fold, allpts)
    print("[细分] 拆分后 cut=%d, fold=%d 段, 节点=%d" % (len(cut), len(fold), len(allpts)))
    adj = build_adj(cut + fold)
    faces, area = extract_faces(adj)
    print("[面板] 提取到 %d 个面板" % len(faces))
    for i, f in enumerate(sorted(faces, key=area, reverse=True)[:12]):
        print("   面板%d: 顶点=%d 面积=%.0f" % (i, len(f), area(f)))
    if not faces:
        print("[错误] 未提取到面板"); return
    transforms, adjacency = fold_faces(faces, fold, args.angle)
    print("[邻接] %d 个面板有折线邻接, 已折叠 %d 个" % (sum(len(v) for v in adjacency.values()) // 2, len(transforms)))
    xs = [p[0] for f in faces for p in f]; ys = [p[1] for f in faces for p in f]
    bounds = (min(xs), min(ys), max(xs), max(ys))
    obj = make_mesh(faces, transforms, args.out, args.texture, bounds, args.uv_mode)
    zs = [v.co.z for v in obj.data.vertices]
    xs2 = [v.co.x for v in obj.data.vertices]; ys2 = [v.co.y for v in obj.data.vertices]
    print("[自检] 3D 包围盒: X=%.3f Y=%.3f Z=%.3f m (Z>0.01 表示已折成立体)"
          % (max(xs2) - min(xs2), max(ys2) - min(ys2), max(zs) - min(zs)))
    print("[OK] 折叠模型: 面=%d 顶点=%d -> %s.glb" % (len(obj.data.polygons), len(obj.data.vertices), args.out))


main()
