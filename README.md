# 一句话生成三维模型 · 2D 设计稿 → 3D 展示（技术向最小原型）

> 考题四「交互式设计：一句话生成三维模型」技术向仓库。
> 目标：从一张二维设计素材出发，用「自然语言/参数 + Blender Python 脚本」自动化完成
> **建模 → 贴图 → 材质 → 渲染 → 导出**，输出三维展示渲染图与 glTF 模型。

## 一句话示例

上传正面设计图后运行一条命令：

```
blender --background --python scripts/build_pack.py -- ^
  --front assets/front.png --width 0.18 --depth 0.045 --height 0.045 --out output/preview
```

即可得到 `output/preview_front.png`（渲染图）与 `output/preview.glb`（模型）。

## 快速开始（3 步）

1. **安装 Blender 3.6+**（自带 Python，无需另装依赖）。
2. **准备素材**：把正面设计图放到 `assets/front.png`；没有素材可运行
   `python scripts/make_placeholder_front.py assets/front.png` 生成一张占位图。
3. **运行**：
   ```
   blender --background --python scripts/build_pack.py -- ^
     --front assets/front.png --out output/preview
   ```
   冒烟测试：`blender --background --python tests/smoke_test.py --python-exit-code 1`

## 技术路线（要点）

- **几何走参数化模板**：包装盒由宽/深/高参数生成，不依赖 LLM 自由造点，几何正确性可控。
- **贴图分面映射**：front 贴到 +Y（面向镜头），其余面可选贴图、缺省用纯色兜底。
- **材质**：Principled BSDF + 图像纹理，粗糙度预设为覆膜纸质感。
- **渲染**：无头（headless）执行；EEVEE 快速迭代 / Cycles 出正式图；棚拍深灰背景 + 区域光。
- **可复现**：一切脚本化，Git 记录脚本版本，输出带路径可复现。

详见 `docs/usage.md`（使用说明）与 `docs/analysis.md`（分析报告）。

## 目录结构

```
assets/        二维输入素材（front.png 及可选各面图）
docs/          分析报告 analysis.md、使用说明 usage.md
scripts/       build_pack.py（主脚本）、make_placeholder_front.py（占位素材）
tests/         smoke_test.py（冒烟测试）
output/        渲染成果（PNG / GLB）
logs/          开发日志 dev_log.md、日程记录 schedule.md
```

## 验收清单

- [ ] 一条命令从 PNG 输入到 PNG 渲染输出，无报错（退出码 0）
- [ ] 输出图可辨认正面设计、比例正确、无破面
- [ ] 修改尺寸 / 换素材可复现
- [ ] 仓库含素材、脚本、渲染成果、分析报告、开发日志

## 进阶路线（v2，待实现）

- 单张「展开图」整贴六面：把六面 UV island 重排到展开图指定矩形区域（UV 布局规范见 `assets/README.md`）。
- dieline（刀版图）识别与自动折叠（PackFold 思路）。
- LLM 多轮对话 + 执行错误回填 + 渲染自检闭环。
