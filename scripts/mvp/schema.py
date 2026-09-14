#!/usr/bin/env python
"""MVP 语义场景图 Schema：结构、尺寸、材质、灯光、相机、输出、版本。

场景 JSON 是全流程的唯一事实源：
  自然语言 -> 场景 JSON -> 受约束 Blender 操作 -> 预览/Diff -> 渲染 -> 导出
"""
from copy import deepcopy

TEMPLATES = {
    # M4 结构模板：3 类 × 2 变体（尺寸为 mm）
    "tuck_box_std":     {"class": "反向插扣盒", "variant": "标准", "dims": ["width", "depth", "height"]},
    "tuck_box_hang":    {"class": "反向插扣盒", "variant": "带挂孔", "dims": ["width", "depth", "height"]},
    "sleeve_std":       {"class": "套盒/卡套", "variant": "标准", "dims": ["width", "depth", "height"]},
    "sleeve_open":      {"class": "套盒/卡套", "variant": "开窗", "dims": ["width", "depth", "height"]},
    "pouch_standup":    {"class": "立式包装", "variant": "自立袋", "dims": ["width", "depth", "height"]},
    "pouch_zipper":     {"class": "立式包装", "variant": "自立拉链袋", "dims": ["width", "depth", "height"]},
}

MATERIAL_PRESETS = {
    "matte_paper":  {"base_color": "#F2EFE8", "roughness": 0.78, "metallic": 0.0, "label": "哑光纸"},
    "gloss_film":   {"base_color": "#F7F7F7", "roughness": 0.18, "metallic": 0.0, "label": "亮面覆膜"},
    "foil_silver":  {"base_color": "#DDDDDD", "roughness": 0.22, "metallic": 1.0, "label": "烫银"},
    "foil_gold":    {"base_color": "#E8C56A", "roughness": 0.25, "metallic": 1.0, "label": "烫金"},
    "uncoated":     {"base_color": "#EFEAE0", "roughness": 0.9,  "metallic": 0.0, "label": "未涂布"},
    "transparent":  {"base_color": "#FFFFFF", "roughness": 0.1,  "metallic": 0.0, "label": "透明"},
}

LIGHT_PRESETS = {
    "warm_morning": {"label": "暖色晨光", "temperature": 5200, "intensity": 1.0, "angle_deg": 35},
    "soft_studio":  {"label": "柔光棚拍", "temperature": 6500, "intensity": 1.2, "angle_deg": 50},
    "cool_blue":    {"label": "冷色蓝调", "temperature": 8000, "intensity": 0.9, "angle_deg": 25},
}

CAMERA_PRESETS = {
    "front":        {"label": "正面", "orbit_deg": 0,  "elevation_deg": 5,  "zoom": 1.0},
    "three_quarter":{"label": "45度", "orbit_deg": 45, "elevation_deg": 30, "zoom": 1.0},
    "top":          {"label": "俯视", "orbit_deg": 20, "elevation_deg": 75, "zoom": 1.0},
}

ASPECTS = {"1:1": (2048, 2048), "4:5": (2048, 2560), "16:9": (2048, 1152)}

DEFAULT_SCENE = {
    "version": "v1",
    "structure": {
        "template": "tuck_box_std",
        "dimensions_mm": {"width": 180.0, "depth": 60.0, "height": 260.0},
        "paper_thickness_mm": 0.45,
        "show_creases": True,
        "show_glue_tab": True,
        "object_naming": True,
    },
    "material": {"preset": "matte_paper", "brand_color": None},
    "brand": {"lock_text": True, "lock_logo": True, "texture": None},
    "lighting": {"preset": "soft_studio"},
    "camera": {"preset": "three_quarter", "orbit_deg": 45, "elevation_deg": 30, "zoom": 1.0},
    "output": {
        "aspect": "4:5", "resolution": 2048,
        "formats": ["PNG", "JPG", "GLB", "BLEND", "PACKAGE"],
        "views": ["front", "three_quarter", "top"],
    },
}


def default_scene():
    return deepcopy(DEFAULT_SCENE)


ALLOWED_KEYS = {
    "version", "structure", "material", "brand", "lighting", "camera", "output",
}


def validate(scene):
    """校验场景 JSON，返回 (ok, errors)。"""
    errs = []
    if not isinstance(scene, dict):
        return False, ["scene 不是对象"]
    for k in scene:
        if k not in ALLOWED_KEYS:
            errs.append("未知顶层字段: %s" % k)
    st = scene.get("structure", {})
    if st.get("template") not in TEMPLATES:
        errs.append("未知模板: %s" % st.get("template"))
    d = st.get("dimensions_mm", {})
    for k in ("width", "depth", "height"):
        v = d.get(k)
        if not isinstance(v, (int, float)) or v <= 0 or v > 5000:
            errs.append("尺寸异常 %s=%s" % (k, v))
    if scene.get("material", {}).get("preset") not in MATERIAL_PRESETS:
        errs.append("未知材质预设: %s" % scene.get("material", {}).get("preset"))
    if scene.get("lighting", {}).get("preset") not in LIGHT_PRESETS:
        errs.append("未知灯光预设: %s" % scene.get("lighting", {}).get("preset"))
    if scene.get("output", {}).get("aspect") not in ASPECTS:
        errs.append("未知画幅: %s" % scene.get("output", {}).get("aspect"))
    return (len(errs) == 0), errs


def merge(base, patch):
    """深合并 patch 到 base（仅覆盖提供的字段）。"""
    out = deepcopy(base)
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = v
    return out
