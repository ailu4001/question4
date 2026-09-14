#!/usr/bin/env python
"""M2 自然语言理解：一句话 -> 场景 JSON（对象/尺寸/材质/灯光/相机/画幅/输出）。

离线规则解析器(PARSER=demo)：可复现、可评测；接入 LLM 时替换 parse() 内部的规则即可，
输出结构（场景 JSON）保持不变。设计目标：20 条固定意图解析准确率 >= 90%。
"""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from schema import default_scene, merge, ASPECTS

NUM = r"(\d+(?:\.\d+)?)"

TEMPLATE_RULES = [
    (("拉链", "zip"), "pouch_zipper"),
    (("立式袋", "自立袋", "包装袋", "立式包装", "袋"), "pouch_standup"),
    (("挂孔", "吊挂", "挂卡"), "tuck_box_hang"),
    (("开窗", "镂空"), "sleeve_open"),
    (("套盒", "卡套", "腰封", "套壳"), "sleeve_std"),
    (("插扣盒", "插扣", "纸盒", "盒"), "tuck_box_std"),
]

MATERIAL_RULES = [
    (("烫金",), "foil_gold"),
    (("烫银",), "foil_silver"),
    (("亮面", "覆膜", "亮膜", "镜面"), "gloss_film"),
    (("透明", "PVC"), "transparent"),
    (("未涂布", "原纸"), "uncoated"),
    (("哑光", "哑膜", "哑光纸"), "matte_paper"),
]

LIGHT_RULES = [
    (("冷色", "蓝调", "冷光"), "cool_blue"),
    (("暖色", "暖光", "晨光"), "warm_morning"),
    (("柔光", "棚拍", "影棚"), "soft_studio"),
]


def parse(text, base=None):
    scene = base or default_scene()
    notes = []
    t = text.lower()

    # --- 结构/对象 ---
    for kws, tpl in TEMPLATE_RULES:
        if any(k.lower() in t for k in kws):
            scene = merge(scene, {"structure": {"template": tpl}})
            notes.append("模板 -> %s" % tpl)
            break

    # --- 尺寸: 180x260x60 / 宽180 高260 底宽60 ---
    m = re.search(NUM + r"\s*[x×*]\s*" + NUM + r"\s*[x×*]\s*" + NUM, t)
    if m:
        w, d, h = (float(m.group(i)) for i in (1, 2, 3))
        scene = merge(scene, {"structure": {"dimensions_mm": {"width": w, "depth": d, "height": h}}})
        notes.append("尺寸 -> %.0fx%.0fx%.0f mm" % (w, d, h))
    else:
        dims = {}
        for key, kws in (("width", ("宽", "阔")), ("height", ("高",)), ("depth", ("底宽", "深", "厚底"))):
            for kw in kws:
                mm = re.search(kw + r"\s*[:：]?\s*" + NUM + r"\s*(?:mm|毫米)?", t)
                if mm:
                    dims[key] = float(mm.group(1)); break
        if dims:
            scene = merge(scene, {"structure": {"dimensions_mm": dims}})
            notes.append("尺寸 -> %s" % dims)

    # --- 纸厚 ---
    v = None
    m1 = re.search(NUM + r"\s*mm\s*(?:白卡|纸|卡纸|厚度)", t)
    if m1:
        v = float(m1.group(1))
    else:
        m2 = re.search(r"(?:纸厚|厚度)[^0-9]{0,8}" + NUM, t)
        if m2:
            v = float(m2.group(1))
    if v is not None:
        scene = merge(scene, {"structure": {"paper_thickness_mm": v}})
        notes.append("纸厚 -> %.2f mm" % v)

    # --- 材质 ---
    for kws, preset in MATERIAL_RULES:
        if any(k.lower() in t for k in kws):
            scene = merge(scene, {"material": {"preset": preset}})
            notes.append("材质 -> %s" % preset)
            break

    # --- 灯光 ---
    for kws, preset in LIGHT_RULES:
        if any(k.lower() in t for k in kws):
            scene = merge(scene, {"lighting": {"preset": preset}})
            notes.append("灯光 -> %s" % preset)
            break

    # --- 相机/镜头 ---
    cam = {}
    has45 = bool(re.search(r"45\s*(?:度|°)", t)) or any(k in t for k in ("斜", "四分之三"))
    has_top = any(k in t for k in ("俯视", "顶视"))
    has_front = any(k in t for k in ("正面", "正视图"))
    if has45 and has_top:      # "45 度俯视" = 45° 斜上视角
        cam.update({"preset": "three_quarter", "orbit_deg": 45, "elevation_deg": 45})
    elif has_top:
        cam.update({"preset": "top", "orbit_deg": 20, "elevation_deg": 75})
    elif has45:
        cam.update({"preset": "three_quarter", "orbit_deg": 45, "elevation_deg": 30})
    if has_front and not has_top and not has45:
        cam.update({"preset": "front", "orbit_deg": 0, "elevation_deg": 5})
    if any(k in t for k in ("拉近", "特写", "近景")):
        cam["zoom"] = 1.3
    if cam:
        scene = merge(scene, {"camera": cam})
        notes.append("相机 -> %s" % cam)

    # --- 画幅 / 分辨率 ---
    am = re.search(r"(\d+)\s*[:：]\s*(\d+)", t)
    if am:
        a = "%s:%s" % (am.group(1), am.group(2))
        if a in ASPECTS:
            scene = merge(scene, {"output": {"aspect": a}})
            notes.append("画幅 -> %s" % a)
    if "2k" in t or "2048" in t:
        scene = merge(scene, {"output": {"resolution": 2048}})
        notes.append("分辨率 -> 2048")
    elif "4k" in t or "4096" in t:
        scene = merge(scene, {"output": {"resolution": 4096}})
        notes.append("分辨率 -> 4096")

    # --- 输出格式 ---
    fmts = []
    if "glb" in t: fmts.append("GLB")
    if "blend" in t or "blender" in t: fmts.append("BLEND")
    if "jpg" in t or "jpeg" in t: fmts.append("JPG")
    if "png" in t: fmts.append("PNG")
    if "项目包" in t or "打包" in t: fmts.append("PACKAGE")
    if fmts:
        scene = merge(scene, {"output": {"formats": fmts}})
        notes.append("输出 -> %s" % fmts)

    # --- 品牌锁定 ---
    if any(k in t for k in ("不锁定", "解锁", "取消锁定", "不要锁定")):
        scene = merge(scene, {"brand": {"lock_text": False, "lock_logo": False}})
        notes.append("品牌锁定 -> 已解除")
    elif any(k in t for k in ("禁止改动文字", "不改文字", "锁定", "保持文字", "文字位置")):
        scene = merge(scene, {"brand": {"lock_text": True, "lock_logo": True}})
        notes.append("品牌锁定 -> 文字/Logo")

    return scene, notes


def get_path(scene, path):
    cur = scene
    for part in path.split('.'):
        cur = cur.get(part) if isinstance(cur, dict) else None
        if cur is None:
            return None
    return cur


if __name__ == "__main__":
    txt = " ".join(sys.argv[1:]) or "做成立式袋，哑光纸，暖色晨光，45 度俯视，4:5"
    sc, nt = parse(txt)
    import json
    print(json.dumps(sc, ensure_ascii=False, indent=2))
    print("解析说明:", "; ".join(nt))
