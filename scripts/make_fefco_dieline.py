#!/usr/bin/env python
"""按 FEFCO 0201 (RSC 普通开槽纸箱) 标准生成工业刀版展开图。

线型约定(与印刷包装行业一致)：实线=切线(cut) 虚线=折线(score)。
布局：接舌(joint) + 4 面板(L,W,L,W) + 上下摇盖(flap, 深 W/2)。
输出：assets/industrial/fefco0201_dieline.svg 与 .png
"""
import os
from PIL import Image, ImageDraw, ImageFont

L, W, H = 200, 150, 100   # mm 示例尺寸
JOINT = 45                # 接舌宽 mm
FLAP = W / 2              # 摇盖深 mm
B = JOINT + 2 * (L + W)   # 纸板总宽 = 45 + 2*(200+150) = 745
A = FLAP + H + FLAP       # 纸板总高 = 250

# 面板 x 分界(右边缘)：joint 之后依次 L,W,L,W
edges = []
x = JOINT
for wdt in (L, W, L, W):
    x += wdt
    edges.append(x)  # [245, 395, 595, 745]

CUT, SCORE = "cut", "score"
segs = []  # (x1,y1,x2,y2,type)


def hline(y, x0, x1, t):
    segs.append((x0, y, x1, y, t))


def vline(x, y0, y1, t):
    segs.append((x, y0, x, y1, t))


# --- 外轮廓(切线) ---
# joint 左侧边仅在 body 高度(flap 区被切掉)
vline(0, FLAP, FLAP + H, CUT)
hline(FLAP, 0, JOINT, CUT)          # joint 上沿
hline(FLAP + H, 0, JOINT, CUT)      # joint 下沿
# 主体+flap 外轮廓
vline(JOINT, 0, A, CUT)             # P1 左(与 joint 相接) 全高
vline(B, 0, A, CUT)                 # 最右侧
hline(0, JOINT, B, CUT)             # 顶部 flap 外沿
hline(A, JOINT, B, CUT)             # 底部 flap 外沿

# --- 面板之间：body 段折线, flap 段切线(flap 彼此分离) ---
for ex in edges[:-1]:  # 245,395,595
    vline(ex, 0, FLAP, CUT)
    vline(ex, FLAP, FLAP + H, SCORE)
    vline(ex, FLAP + H, A, CUT)

# --- body 与 flap 分界：水平折线(贯穿除 joint 区) ---
hline(FLAP, JOINT, B, SCORE)
hline(FLAP + H, JOINT, B, SCORE)

# ===== SVG =====
svg = []
svg.append('<svg xmlns="http://www.w3.org/2000/svg" width="%.1fmm" height="%.1fmm" viewBox="-30 -30 %.1f %.1f">' % (B, A, B + 60, A + 60))
svg.append('<rect x="-30" y="-30" width="%.1f" height="%.1f" fill="#fafafa"/>' % (B + 60, A + 60))
svg.append('<style>.cut{stroke:#d32f2f;stroke-width:1.2;fill:none}.score{stroke:#1565c0;stroke-width:1.2;stroke-dasharray:6 4;fill:none}.txt{font:11px sans-serif;fill:#333}</style>')
for (x1, y1, x2, y2, t) in segs:
    svg.append('<line class="%s" x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>' % (t, x1, y1, x2, y2))
# 面板标注
cx = JOINT
for i, wdt in enumerate((L, W, L, W)):
    cx += wdt / 2
    svg.append('<text class="txt" x="%.1f" y="%.1f" text-anchor="middle">%d</text>' % (cx, FLAP + H / 2 + 4, wdt))
    cx += wdt / 2
svg.append('<text class="txt" x="22" y="%.1f" text-anchor="middle">接舌45</text>' % (FLAP + H / 2 + 4))
svg.append('<text class="txt" x="%.1f" y="%.1f" text-anchor="middle">H=%d</text>' % (JOINT - 8, FLAP + H / 2, H))
svg.append('<text class="txt" x="%.1f" y="14">FEFCO 0201 (RSC)  L=%.0f W=%.0f H=%.0f  mm   实线=切线  虚线=折线</text>' % (JOINT, L, W, H))
svg.append('</svg>')
os.makedirs(os.path.join(os.path.dirname(__file__), '..', 'assets', 'industrial'), exist_ok=True)

outdir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'assets', 'industrial'))
svg_path = os.path.join(outdir, 'fefco0201_dieline.svg')
with open(svg_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(svg))
print('[OK] SVG ->', svg_path)

# ===== PNG 预览(Pillow) =====
SC = 2.2
iw, ih = int(B * SC) + 60, int(A * SC) + 60
img = Image.new('RGB', (iw, ih), '#fafafa')
d = ImageDraw.Draw(img)
ox, oy = 30, 30


def px(x, y):
    return ox + x * SC, oy + y * SC


def dashed(d, x1, y1, x2, y2, color, w=2, dash=8, gap=5):
    import math
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length == 0:
        return
    ux, uy = dx / length, dy / length
    pos = 0.0
    while pos < length:
        e = min(pos + dash, length)
        d.line([(x1 + ux * pos, y1 + uy * pos), (x1 + ux * e, y1 + uy * e)], fill=color, width=w)
        pos = e + gap


for (x1, y1, x2, y2, t) in segs:
    a, b = px(x1, y1), px(x2, y2)
    if t == CUT:
        d.line([a, b], fill=(211, 47, 47), width=3)
    else:
        dashed(d, a[0], a[1], b[0], b[1], (21, 101, 192), w=3)

# 图例
try:
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 16)
except Exception:
    font = ImageFont.load_default()
d.text((ox, ih - 26), 'FEFCO 0201 (RSC)  L=200 W=150 H=100 mm    红实线=切线  蓝虚线=折线', fill=(60, 60, 60), font=font)
png_path = os.path.join(outdir, 'fefco0201_dieline.png')
img.save(png_path)
print('[OK] PNG ->', png_path)
