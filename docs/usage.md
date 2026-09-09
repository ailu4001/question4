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
  --front assets/front.png --width 180 --depth 45 --height 45 --out output/preview
```
参数：`--front` 正面图（+Y 面向镜头）；`--width/depth/height` 盒尺寸(毫米)；其余五面可 `--right/--left/--top/--bottom/--back` 指定，缺省纯色兜底；`--engine EEVEE|CYCLES`。

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


## G. 本方法（二维素材/图纸 → 3D）的优势、局限与已知问题

### 优势
1. **可复现、可追溯**：全流程脚本化（Blender 无头执行），Git 记录每次脚本与输出，换机器/换参数可重跑；
2. **几何正确性可控**：几何由参数化模板/脚本承接（回转体、盒体、浮雕），不依赖模型自由"造点"，出错面小；
3. **迭代成本低**：用一句话/几个参数描述即可出初版，改参数重跑即可迭代（对应考题"一句话生成+修改"）；
4. **查看与交付方便**：产出 `.blend`（Blender 直接打开）、`.glb`（网页/游戏/AR 通用）、多视角 PNG；
5. **免费开源、可扩展**：Blender 开源免费；新增对象类型只需仿照 `build_housing.py / build_hydraulic.py` 写一个参数化脚本；
6. **跨版本适配**：脚本已处理 Blender 4.2/5.0 的引擎枚举与 API 差异。

### 局限（能力边界，请如实认知）
1. **只擅长"可参数化的规整几何"**：回转体（壳体/缸/瓶罐）、长方体包装等效果好；对**自由曲面/复杂有机造型**（人物、汽车外壳、雕塑）效果差，需 image-to-3D 或手工建模；
2. **不能自动读图**：流程**不会解析 CAD 尺寸标注/三视图重建**，几何信息靠用户一句话+参数补充（这正是"一句话生成"的前提，也是当前主要人工环节）；
3. **演示级而非生产级**：模型未含公差、圆角、螺纹、退刀槽等工艺特征，**不能直接用于 CNC/3D 打印生产**，需工艺细化；
4. **细节需人工目检**：贴图文字方向、孔位是否合理、比例是否接近图纸，仍需人工在 Blender 中确认。

### 已知问题与注意事项
1. **Blender 版本差异**：4.2 前后 EEVEE 引擎标识不同、5.0 移除部分 API（如 `transform.rotate` 参数变化、`use_nodes` 弃用告警，预计 6.0 移除）；脚本已做版本判断，但**升级 Blender 大版本后需回归测试**，未来需迁移到新材质/节点系统；
2. **布尔建模**：共面易产生退化，脚本用微小重叠规避；孔/特征过多会明显变慢；
3. **浏览器预览**：three.js 预览需 WebGL；在受限/内嵌浏览器中可能黑屏（本机 Codex 内嵌浏览器即如此），**最可靠查看方式是 Blender 打开 .blend**；`file://` 直接双击 HTML 会因 CORS 限制无法加载 glb，请用本地 http 服务；
4. **无头渲染**：渲染引擎名称错误会直接报错（脚本有兜底）；首次运行 Blender 需联网/写用户配置；
5. **中文路径**：含中文的路径/文件名在部分工具链可能产生编码问题，建议工程路径尽量用英文。

## H. 一键复现全部程序
```powershell
python scripts/run_all.py [--blender <路径>] [--python <路径>] [--keep-going]
```
- 自动完成：冒烟测试、素材/中间贴图生成、P1–P4 建模导出、生成 4 个 `.blend`、统一渲染 12 张展示图；
- 每步独立日志：`logs/run_all_<步骤名>.log`；
- 说明：`--python` 需为含 Pillow/numpy 的真实 Python（Windows 商店占位 python 会被自动跳过）；
- 已本地验证：16/16 步通过。

## I. 自然语言驱动（一句话 → 3D）
```powershell
python scripts/nl_to_3d.py --text "做一个包装盒 200x120x80 mm" --blender "<blender路径>"
python scripts/nl_to_3d.py --text "生成液压缸 缸筒外径80 长260" --blender "<blender路径>"
python scripts/nl_to_3d.py --text "做一个阶梯回转壳体" --blender "<blender路径>"
python scripts/nl_to_3d.py --text "壳体" --demo-only
```
- 离线解析器（PARSER=demo）用于可复现演示；真实理解由 LLM 完成（实录见 docs/nl_driven_workflow.md）；
- 每步输出结构化 JSON（含 dimension_source 尺寸来源标注）到 output/nl_<项目>.json，并自动调用 Blender 建模+渲染。
