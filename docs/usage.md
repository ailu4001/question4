# 使用说明（usage.md）

## 环境要求

| 项 | 要求 |
|---|---|
| Blender | 3.6 或更高（4.x 推荐；自带 Python，无需安装第三方包） |
| 生成占位素材 | 可选；Python 3 标准库即可（`scripts/make_placeholder_front.py`） |
| 系统 | Windows / macOS / Linux 均可（以下命令以 Windows PowerShell 为例） |

## 1. 冒烟测试（先确认 Blender 可无头运行）

```powershell
blender --background --python tests/smoke_test.py --python-exit-code 1
```

正常输出末尾包含 `[SMOKE OK] blender 4.x.x`。

## 2. 生成占位正面素材（可选）

```powershell
python scripts/make_placeholder_front.py assets/front.png
```

生成 800x800 的示意「包装正面」图（米白底 + 品牌色带 + 主视觉方块）。

## 3. 运行最小原型

```powershell
blender --background --python scripts/build_pack.py -- `
  --front assets/front.png `
  --width 0.18 --depth 0.045 --height 0.045 `
  --out output/preview
```

### 参数说明

| 参数 | 必填 | 默认 | 说明 |
|---|---|---|---|
| `--front` | 是 | — | 正面设计图（贴到 +Y，面向镜头） |
| `--width / --depth / --height` | 否 | 0.18 / 0.045 / 0.045 | 盒宽/深/高（米） |
| `--right/--left/--top/--bottom/--back` | 否 | 无 | 对应面图片；缺省为纯色兜底 |
| `--engine` | 否 | auto | `auto`（EEVEE）/ `EEVEE` / `CYCLES` |
| `--samples` | 否 | 64 | 采样数（Cycles 有效） |
| `--out` | 是 | — | 输出前缀，如 `output/preview` |

### 输出

- `output/preview_front.png`：正面视角渲染图
- `output/preview.glb`：glTF 模型（可拖进任何 3D 查看器 / 网页展示）

## 4. 常见问题（FAQ）

| 问题 | 处理 |
|---|---|
| 渲染图里文字上下/左右颠倒 | 说明素材方向与 Blender UV 不一致：把图片垂直翻转后重试；或反馈给作者调整 UV 方向 |
| glTF 导出报 WARN | 不影响渲染；多为插件未启用，脚本会自动尝试启用 `io_scene_gltf2` |
| Cycles 太慢 | 先用默认 EEVEE 迭代，最终出图再 `--engine CYCLES` |
| 想换对象（罐/瓶） | 属于 v2；当前模板面向长方体包装盒，可参照 `build_pack.py` 的 `add_box` 自行扩展旋转体 |
| 控制台中文乱码 | 仅影响打印信息，不影响出图；可将终端代码页切到 UTF-8 |

## 5. 素材规格建议（assets）

- 格式：PNG / JPG；建议正方形（如 1024x1024），正面素材主体居中。
- 可选六面图命名：`front/back/left/right/top/bottom.png`，对应 `--front/--back/...` 参数。
- 展示级渲染时贴图分辨率建议不低于 1024；手机壳/包装类 2048 更佳。
