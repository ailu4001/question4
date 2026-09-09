# 二维输入素材说明（assets）

## 当前素材

| 文件 | 用途 | 来源 |
|---|---|---|
| `front.png` | 最小原型「正面设计图」（必填） | 自行设计 / `scripts/make_placeholder_front.py` 生成 |
| （可选）`back/left/right/top/bottom.png` | 其余五面贴图 | 自行设计 |

## 规格建议

- 格式 PNG / JPG，建议正方形（1024x1024 或更高）。
- `front.png` 最终会贴在盒体 +Y 面并面向镜头；请把主视觉与文字按「正面观看」方向排版。
- 缺省面使用纯色材质兜底，不影响跑通。

## v2 展开图布局规范（预留）

若要实现「单张展开图整贴六面」，需先约定 UV 布局：
把六面（front/right/back/left/top/bottom）的 UV island 按统一坐标表排布到一张纹理上，
素材与脚本共用同一张坐标表（见 docs/analysis.md §5 的演进说明）。
