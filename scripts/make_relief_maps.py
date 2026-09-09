#!/usr/bin/env python
"""预处理(改进版)：人物照片 -> albedo(彩色贴图) + height(浮雕高度图)。

方法：以图像四边像素为背景样本集，逐像素求到"最近背景样本"的色距；
色距大 = 前景(凸起)，色距小 = 背景(平坦)。可处理非纯色/渐变背景。
用法：python scripts/make_relief_maps.py --input assets/鹿乃2.jpg
"""
import argparse
import numpy as np
from PIL import Image, ImageFilter


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="assets/鹿乃2.jpg")
    ap.add_argument("--albedo", default="assets/relief_albedo.png")
    ap.add_argument("--height", default="assets/relief_height.png")
    ap.add_argument("--mesh-w", type=int, default=160)
    ap.add_argument("--mesh-h", type=int, default=256)
    ap.add_argument("--lo", type=float, default=14.0)
    ap.add_argument("--hi", type=float, default=70.0)
    args = ap.parse_args()

    img = Image.open(args.input).convert("RGB")
    small = img.resize((args.mesh_w, args.mesh_h))
    arr = np.asarray(small, dtype=np.float32).reshape(-1, 3)
    sw, sh = args.mesh_w, args.mesh_h

    # 四边采样作为背景样本（人物通常居中不触边）
    samp = []
    step = 3
    for x in range(0, sw, step):
        samp.append(arr[x]); samp.append(arr[(sh - 1) * sw + x])
    for y in range(0, sh, step):
        samp.append(arr[y * sw]); samp.append(arr[y * sw + sw - 1])
    S = np.asarray(samp, dtype=np.float32)

    # 每像素 -> 最近背景样本色距（分块避免大内存）
    mind = np.empty(len(arr), dtype=np.float32)
    for st in range(0, len(arr), 8000):
        chunk = arr[st:st + 8000]
        mind[st:st + 8000] = np.sqrt(((chunk[:, None, :] - S[None, :, :]) ** 2).sum(-1)).min(-1)

    depth01 = np.clip((mind - args.lo) / (args.hi - args.lo), 0.0, 1.0)
    depth_img = Image.fromarray((depth01.reshape(sh, sw) * 255).astype(np.uint8), "L")
    depth_img = depth_img.filter(ImageFilter.GaussianBlur(1.0))
    depth_img.save(args.height)
    img.save(args.albedo)
    fg = float((depth01 > 0.05).mean() * 100)
    print("[OK] albedo ->", args.albedo)
    print("[OK] height ->", args.height, "前景占比=%.1f%%" % fg)


main()
