#!/usr/bin/env python
"""生成一张占位"包装正面"设计图（纯 Python 标准库，无需 Pillow）。

用法（普通 Python）:
    python scripts/make_placeholder_front.py assets/front.png
用法（在 Blender 内运行时参数在 -- 之后）:
    blender --background --python scripts/make_placeholder_front.py -- assets/front.png
"""
import argparse
import struct
import sys
import zlib


def write_png(path, w, h, pixel):
    raw = bytearray()
    for y in range(h):
        raw.append(0)  # filter: None
        for x in range(w):
            raw.extend(pixel(x, y))

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)  # 8bit RGB
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


def main():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?", default="assets/front.png")
    ap.add_argument("--size", type=int, default=800)
    args = ap.parse_args(argv)
    w = h = args.size

    def pixel(x, y):
        # 米白背景
        r, g, b = 245, 240, 230
        # 顶部品牌色带
        if y < int(h * 0.18):
            r, g, b = 30, 120, 180
        # 中部主视觉方块
        if int(h * 0.28) < y < int(h * 0.74) and int(w * 0.18) < x < int(w * 0.82):
            r, g, b = 255, 214, 120
            # 方块内装饰条纹
            if int(h * 0.34) < y < int(h * 0.40) and (x + y) // 24 % 2 == 0:
                r, g, b = 200, 90, 70
        # 底部信息条
        if y > int(h * 0.86):
            r, g, b = 60, 60, 70
        return bytes((r, g, b))

    write_png(args.out, w, h, pixel)
    print("[OK] placeholder front ->", args.out)


main()
