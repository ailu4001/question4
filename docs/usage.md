# 使用说明（usage.md）

## 环境
- Blender 3.6+（推荐 4.x/5.x；自带 Python）
- 普通 Python（可选，仅浮雕/刀版图预处理用，需 Pillow/numpy）

## A. 查看 3D 结果
```powershell
blender output/housing_view.blend
```
中键旋转 / 滚轮缩放 / Shift+中键平移；着色切换 Material Preview 更直观。

## B. CAD 机械壳体建模（P3 主案例）
```powershell
blender --background --python scripts/build_housing.py -- --out output/housing
```
输出 `housing_front/quarter/top.png` 与 `housing.glb`。
改尺寸：编辑 `scripts/build_housing.py` 中法兰 R55/h8、主体 R40/h50、凸台 R20/h8、内腔 R34、顶孔 R10、安装孔 4×R4 等参数（单位 mm）。

## C. 包装盒（P1）
```powershell
python scripts/make_placeholder_front.py assets/front.png   # 无素材时生成占位正面图
blender --background --python scripts/build_pack.py -- `
  --front assets/front.png --width 0.18 --depth 0.045 --height 0.045 --out output/preview
```
参数：`--front` 正面图（+Y 面向镜头）；`--width/depth/height` 盒尺寸(米)；其余五面可 `--right/--left/--top/--bottom/--back` 指定，缺省纯色兜底；`--engine EEVEE|CYCLES`。

## D. 人物浮雕（P2）
```powershell
python scripts/make_relief_maps.py --input assets/鹿乃2.jpg
blender --background --python scripts/person_relief.py -- `
  --albedo assets/relief_albedo.png --height assets/relief_height.png --out output/person
```
预处理用"最近背景样本色距"抠前景生成高度图；`person_relief.py` 把高度图映射为网格 Z 位移形成浮雕板。

## E. 工业刀版图（FEFCO 0201）
```powershell
python scripts/make_fefco_dieline.py
```
输出 `assets/industrial/fefco0201_dieline.svg/.png`；改 `L,W,H` 可重生成。
真实工业 dieline 在线来源：Templatemaker / PackPaa / Tanur / DieCutTemplates（见 `assets/industrial/README.md`）。

## FAQ
| 问题 | 处理 |
|---|---|
| 浏览器 3D 预览黑屏 | 内嵌/受限浏览器可能禁用 WebGL；改用 Blender 打开 .blend |
| 渲染图文字倒置 | 把输入图垂直翻转或调整 UV |
| glTF 导出 WARN | 不影响渲染，脚本自动尝试启用 io_scene_gltf2 |

## F. 液压缸（P4）
```powershell
blender --background --python scripts/build_hydraulic.py -- --out output/hydraulic
blender output/hydraulic_view.blend   # 或先生成 .blend
```
改尺寸：编辑 `scripts/build_hydraulic.py` 顶部常量（缸筒 BARREL_R/Z、法兰 CAP_R、活塞杆 ROD_R、油口 PORT_R 等，单位 mm）。
