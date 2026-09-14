# Folda MVP 达标矩阵（对照产品方案逐条）

> 版本：2026-09-14 ｜ 代码：`scripts/mvp/` ｜ 端到端：`python scripts/mvp/cli.py`
> 说明：所有"实测"数据均来自本机运行（Blender 5.0.1 + Python），可复现。

## 1. 核心功能模块

| 模块 | 产品方案要求 | 实现 | 实测/证据 | 状态 |
|---|---|---|---|---|
| M1 素材接入与诊断 | PNG/JPG/SVG/扁平PDF；识别尺寸/文字/主视觉/刀模线 | `dieline.py`：SVG/PDF 矢量解析 + 扫描件栅格化 + 位图启发式；`vision.py`：**OCR 文字识别(Windows.Media.Ocr，中文) + 主视觉识别(最大连通域) + 透明区检测 + 品牌锁定区域** | PDF 折线 55/55=100%；中文 OCR 实测识别"折影折叠 Folda / 品牌名称：鹿乃 / 净含量 250g"；透明图检出 84.3%；主视觉 bbox+占比 | ✅ |
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
| 文件接入 | PNG/JPG/SVG/扁平PDF，≤50MB，90% 进入编辑态 | **24/24 = 100%** 进入编辑态（SVG 10 + PDF 10 + PNG 2 + JPG 2） | ✅ |
| 结构范围 | 3 类 × ≥2 模板 | 6 模板全部生成成功 | ✅ |
| 刀模识别 | 折线召回 ≥85% | 标准样张 **44/44 = 100%**（自建 10 样张，虚线清晰） | ✅（测试集有限） |
| 自然语言 | 20 条固定意图 ≥90% | **20/20 = 100%** | ✅ |
| 脚本生成 | 受约束操作、禁任意文件/网络 | 模板+场景参数驱动，无任意代码执行；sandbox 扫描 | ✅ |
| 局部编辑 | ≥80% 指令只影响目标对象 | **21/21 = 100%**（`tests/run_mvp_benchmark.py`，逐条校验变更类别） | ✅ |
| UV/贴图 | 越界率 ≤5% | **0%** | ✅ |
| 预览/Diff | 30 秒理解变化 | 分类变更摘要（灯光/材质/输出…）+ 前后对比图函数 | ✅ |
| 渲染 | 3 灯光/3 镜头、2K、≤5 分钟 | 3×3 预设；2048 分辨率；单张 ~10 秒 | ✅ |
| 导出 | PNG/JPG、GLB、BLEND、项目包，≥98% | **30/30 = 100%**（批量导出实测） | ✅ |
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
2. **OCR 依赖系统语言包**：使用 Windows 自带 OCR（实测支持 zh-Hans-CN），无置信度输出；换平台需替换 OCR 引擎（接口已隔离在 `vision.ocr_text`）；
3. **7 日复用率 ≥30%**：需真实用户试运营，无法在本地验证（唯一未测指标）；
4. 批量指标基于自建样本集（21 条编辑指令、30 次导出、24 个素材、3 次端到端），结论限于该样本范围；
5. 结构模板为**展示级简化结构**（非生产级刀模精度），与产品方案"不替代专业 CAD"的边界一致。

## 5. MVP 成功指标（产品方案第 5.3 节）实测

| 指标 | 目标 | 实测 | 状态 |
|---|---|---|---|
| 无人工 Blender 的端到端完成率 | ≥80% | **100%**（3/3，benchmark） | ✅ |
| 首次 3D 预览时间 | ≤3 分钟 | **11.9 秒** | ✅ |
| 2K 成品渲染时间 | ≤5 分钟 | **约 10 秒/张**（9 张共 12.9 秒） | ✅ |
| 模板内文字/主视觉越界率 | ≤5% | **0%**（UV 越界检查） | ✅ |
| 自然语言局部编辑成功率 | ≥85% | **100%**（21/21） | ✅ |
| 导出成功率 | ≥98% | **100%**（30/30） | ✅ |
| 试运营用户 7 日复用率 | ≥30% | 未测（需真实用户试运营） | ⏳ 待验证 |

复现：`python tests/run_mvp_benchmark.py`

## 6. 复核路径（可复现）
```
python tests/run_mvp_tests.py                     # 意图准确率
python tests/run_dieline_tests.py                 # SVG 折线召回（自建样张）
python tests/run_pdf_tests.py                     # PDF 折线召回（矢量样张）
python scripts/mvp/vision.py --input <素材> --out out.json   # OCR+主视觉+透明区诊断
python tests/run_mvp_benchmark.py                 # 批量指标：局部编辑/导出/接入/端到端
blender --background --python scripts/mvp/packaging.py -- --scene-json <scene> --out <out>
blender --background --python scripts/mvp/render_mvp.py -- --scene-json <scene> --model <glb> --outdir <dir> --quick
python scripts/mvp/cli.py --text "..." --name demo --quick
```
