# 工业二维设计图素材（assets/industrial）

## 内容

| 文件 | 说明 |
|---|---|
| `fefco0201_dieline.svg` | 按 FEFCO 0201（RSC 普通开槽纸箱）标准生成的刀版展开图（矢量） |
| `fefco0201_dieline.png` | 同一刀版图的 PNG 预览 |

示例尺寸：L=200 × W=150 × H=100 mm，接舌 45 mm，摇盖深 W/2。
线型约定（与印刷包装行业一致）：**红实线 = 切线(cut)**，**蓝虚线 = 折线(score)**。
生成脚本：`scripts/make_fefco_dieline.py`（可改尺寸重新生成）。

## 工业用途说明

FEFCO 0201 是最常用的工业运输/销售包装箱型（RSC），
该展开图可直接用于：结构打样、刀模制作、UV 贴图与"展开图→3D 折叠"实验（考题 v2 路线）。

## 真实工业 dieline 在线来源（免费、可输出 PDF/SVG/DXF）

- Templatemaker（纸盒/礼品盒展开图，可商用）: https://www.templatemaker.nl
- PackPaa Box Dieline Calculator: https://packpaa.com/box-dieline-generator/
- Tanur Graphics Dieline Generator: https://tanur.graphics/dieline-generator/
- DieCutTemplates（海量盒型模板库）: https://www.diecuttemplates.com
- CefBox FEFCO Dieline Generator: https://www.cefbox.com/dielines

## 版权说明

本目录刀版图由脚本按 FEFCO 0201 结构标准程序生成，无第三方版权。
真实品牌在售包装的刀版图/设计稿通常受版权保护，如需使用请从授权渠道获取
（如 Dieline 社区、包装设计素材库或客户提供的源文件）。
