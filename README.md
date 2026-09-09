# 一句话生成三维模型 · 二维设计稿/图纸 → 3D（考题四技术向）

> 目标：用「自然语言/参数 + Blender Python 脚本」自动化完成
> **建模 → 贴图 → 材质 → 渲染 → 导出**，把二维素材变成可查看、可旋转的三维结果。

## 核心成果（三个原型）

| 原型 | 二维输入 | 三维结果 | 说明 |
|---|---|---|---|
| **P3 CAD 机械壳体（主案例）** | `assets/cad_8191871.jpg` 机械零件工程图 | `output/housing_view.blend` / `housing.glb` / 三视角 PNG | 按"阶梯回转壳体"参数化建模（法兰+主体+凸台+内腔+安装孔），**用 Blender 直接打开查看** |
| P1 包装盒 | `assets/front.png` 正面设计图 | `output/preview_front.png` / `preview.glb` | 六面贴图长方体包装盒 |
| P2 人物浮雕 | `assets/鹿乃人设图.jpg` 等 | `output/person_front.png` / `person.glb` | 最近背景样本抠图 + 高度图浮雕（2.5D） |
| 工业刀版图 | — | `assets/industrial/fefco0201_dieline.svg/png` | 按 FEFCO 0201 标准生成的展开刀版图（v2 折叠素材） |

## 最快查看 3D 结果（推荐）

**用 Blender 打开**（不依赖浏览器 WebGL）：

```
blender output/housing_view.blend
```

操作：中键旋转、滚轮缩放、Shift+中键平移；小键盘 1/3/7 切换前/右/顶视图。

## 命令行复现

```powershell
# 1) 冒烟测试
blender --background --python tests/smoke_test.py --python-exit-code 1

# 2) CAD 机械壳体建模（阶梯回转壳体，参数见脚本头部）
blender --background --python scripts/build_housing.py -- --out output/housing

# 3) 包装盒（单张正面图 -> 盒）
blender --background --python scripts/build_pack.py -- --front assets/front.png --out output/preview

# 4) 人物浮雕
python scripts/make_relief_maps.py --input assets/鹿乃2.jpg
blender --background --python scripts/person_relief.py -- --albedo assets/relief_albedo.png --height assets/relief_height.png --out output/person

# 5) FEFCO 0201 工业刀版图
python scripts/make_fefco_dieline.py
```

## 提交内容对照（考题要求）

| 考题要求 | 位置 |
|---|---|
| 二维输入素材 | `assets/`（CAD 图纸、包装正面图、人物图、工业刀版图） |
| Blender 脚本 | `scripts/`（build_housing / build_pack / person_relief 等） |
| 模型或渲染成果 | `output/`（.blend / .glb / 多视角 PNG / 预览页） |
| 实验截图 | `output/*.png`（渲染即实验截图） |
| 简单分析报告 | `docs/analysis.md` |
| 使用说明 | `docs/usage.md` |
| 开发日志与日程记录 | `logs/dev_log.md`、`logs/schedule.md` |

## 技术路线要点

- 几何走**参数化模板/脚本**（回转体、盒体），LLM 一句话 + 迭代修改即可重建；
- 贴图用**分面映射**（包装盒）或**最近背景样本抠图 + 高度图**（人物浮雕）；
- 全部**无头(headless)可复现**，脚本化、Git 可追溯；
- 3D 查看：浏览器预览页（three.js，需 WebGL）或 **Blender 直接打开 .blend**（最可靠）。
