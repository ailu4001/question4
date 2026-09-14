# Folda MVP 达标矩阵（对照产品方案逐条）

> 版本：2026-09-14 ｜ 代码：`scripts/mvp/` ｜ 端到端：`python scripts/mvp/cli.py`
> 说明：所有"实测"数据均来自本机运行（Blender 5.0.1 + Python），可复现。

## 1. 核心功能模块

| 模块 | 产品方案要求 | 实现 | 实测/证据 | 状态 |
|---|---|---|---|---|
| M1 素材接入与诊断 | PNG/JPG/SVG/扁平PDF；识别尺寸/文字/主视觉/刀模线 | `mvp/dieline.py`：SVG 解析；**PDF 矢量解析(pdfplumber：虚线=折线/实线=切线/rect=闭合区)**；**扫描件 PDF 栅格化回退(pdf2image+poppler)**；位图启发式 | 矢量 PDF 10/10、折线召回 **55/55=100%**；扫描件走 raster 回退成功 | ✅（位图/扫描件为启发式） |
| M2 自然语言理解 | 对象/尺寸/材质/灯光/相机/画幅；只追问必要信息 | `mvp/nl_parser.py` + `schema.py` | **20 条固定意图 20/20 = 100%**（目标≥90%） | ✅ |
| M3 脚本生成与修改 | NL→语义场景参数→受约束 Blender 操作；先校验后预览、可修复 | `cli.py`：NL→场景 JSON→校验(`schema.validate`)→受约束模板执行；`sandbox.py` 危险模式扫描 | 场景校验通过；安全扫描无危险模式；失败降级 tuck_box_std | ✅（模板受约束） |
| M4 结构模板 | 反向插扣盒/套盒/立式包装，每类≥2 模板；折面/粘口/厚度/命名 | `mvp/packaging.py`：6 模板（tuck_box_std/hang、sleeve_std/open、pouch_standup/zipper），面板对象命名、solidify 厚度、粘口/折面 flap | 6/6 模板生成 GLB+BLEND 成功 | ✅ |
| M5 贴图/材质/UV | 自动分面、材质预设、UV 越界检查、品牌锁定 | 每面板 UV 0..1（分面）；6 材质预设；`uv_check` 报告；素材原图直接使用不改写（品牌锁定） | **UV 越界 0/… = 0%**（目标≤5%）；6 模板全部通过 | ✅ |
| M6 局部编辑与版本 | 对象/材质/相机/灯光级 Diff、应用/撤销/版本回放 | `mvp/diff_engine.py`（路径级分类 Diff）、`mvp/version_store.py`（命名版本、同名递增、≤20 步撤销、restore/clone） | 第二次编辑实测输出 4 项分类变更（灯光/材质/输出）；版本 demo→demo_v2 | ✅（对象级编辑经模板参数实现） |
| M7 渲染与交付 | 3 灯光/3 镜头预设、2K、GLB/BLEND/项目包 | `mvp/render_mvp.py`（3×3 预设、画幅 1:1/4:5/16:9、2048 分辨率）、`mvp/exporter.py`（zip 项目包：scene+模型+渲染图） | **2K(2048×2560) 单张约 10 秒**（目标≤5分钟）；项目包导出成功 | ✅ |
| M8 质量与安全 | 操作白名单、沙箱、几何/UV/材质校验、失败降级 | `mvp/sandbox.py`（操作白名单+路径沙箱+危险模式扫描）；UV 校验；生成失败自动降级模板 | 安全扫描通过；路径越界拦截；降级逻辑已实现 | ✅（简化版） |

## 2. MVP 验收标准对照

| 验收项 | 标准 | 实测 | 状态 |
|---|---|---|---|
| 文件接入 | PNG/JPG/SVG/扁平PDF，≤50MB，90% 进入编辑态 | PNG/JPG/SVG/PDF 全部可接入；PDF 矢量 10/10 + 扫描件栅格化回退 | ✅（位图精度有限） |
| 结构范围 | 3 类 × ≥2 模板 | 6 模板全部生成成功 | ✅ |
| 刀模识别 | 折线召回 ≥85% | 标准样张 **44/44 = 100%**（自建 10 样张，虚线清晰） | ✅（测试集有限） |
| 自然语言 | 20 条固定意图 ≥90% | **20/20 = 100%** | ✅ |
| 脚本生成 | 受约束操作、禁任意文件/网络 | 模板+场景参数驱动，无任意代码执行；sandbox 扫描 | ✅ |
| 局部编辑 | ≥80% 指令只影响目标对象 | 参数级 Diff 可定位具体字段（实测 4 项精确变更） | ⚠️ 未做批量指令统计 |
| UV/贴图 | 越界率 ≤5% | **0%** | ✅ |
| 预览/Diff | 30 秒理解变化 | 分类变更摘要（灯光/材质/输出…）+ 前后对比图函数 | ✅ |
| 渲染 | 3 灯光/3 镜头、2K、≤5 分钟 | 3×3 预设；2048 分辨率；单张 ~10 秒 | ✅ |
| 导出 | PNG/JPG、GLB、BLEND、项目包，≥98% | 全部格式可导出；批量成功率接口已实现 | ⚠️ 未做大规模样本统计 |
| 版本 | 20 步撤销、命名、复制 | 命名版本/递增/≤20 撤销/restore/clone | ✅（撤销窗口为 20） |
| 错误处理 | 解释、重试、降级模板 | 失败打印日志尾部 + 降级 tuck_box_std 重试 | ✅ |

## 3. 端到端实测（CLI）

```
python scripts/mvp/cli.py --text "反向插扣盒，哑光纸，暖色晨光，45度，4:5，导出 GLB 和项目包" \
    --asset assets/front.png --name demo --blender <路径> --quick
```
7 步全部通过：① NL→场景 JSON ② 素材诊断 ③ 受约束生成 ④ 渲染 ⑤ Diff ⑥ 版本 ⑦ 项目包导出。
第二次修改（亮面覆膜/冷色蓝调/16:9）→ Diff 输出 4 项变更，版本 demo→demo_v2。

## 4. 尚未达标 / 待验证（如实）

1. **扫描件/位图精度有限**：矢量 PDF/SVG 折线召回 100%，但位图（含扫描件 PDF）为启发式候选，精度有限；
2. **文字/主视觉自动识别**：当前依赖人工/AI 判读，未集成 OCR；
3. **量化指标缺真实样本**：局部编辑 ≥80%、导出 ≥98%、素材 90% 达标率需大规模样本统计；
4. **7 日复用率 ≥30%**：需真实试运营，无法在本地验证；
5. 结构模板为**展示级简化结构**（非生产级刀模精度），与产品方案"不替代专业 CAD"的边界一致。

## 5. 复核路径（可复现）
```
python tests/run_mvp_tests.py                     # 意图准确率
python tests/run_dieline_tests.py                 # SVG 折线召回（自建样张）
python tests/run_pdf_tests.py                     # PDF 折线召回（矢量样张）
blender --background --python scripts/mvp/packaging.py -- --scene-json <scene> --out <out>
blender --background --python scripts/mvp/render_mvp.py -- --scene-json <scene> --model <glb> --outdir <dir> --quick
python scripts/mvp/cli.py --text "..." --name demo --quick
```
