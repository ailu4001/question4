#!/usr/bin/env python
"""M8 质量与安全：操作白名单 + 路径沙箱（禁止任意文件/网络访问）。

设计要点：
  - 只允许预定义的"场景操作"（改尺寸/材质/灯光/相机/输出）；
  - 所有输出路径必须位于项目目录内；
  - 拒绝任何执行任意代码/网络访问的意图。
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ALLOWED_OPS = {"set_dimension", "set_template", "set_material", "set_lighting",
               "set_camera", "set_aspect", "set_output", "set_brand_lock"}

FORBIDDEN_PATTERNS = ("exec(", "eval(", "__import__", "socket", "urllib", "requests",
                      "subprocess", "os.system", "shutil.rmtree", "open('/", 'open("C:')


def check_operation(op):
    return op in ALLOWED_OPS


def safe_path(path):
    """校验路径在项目目录内，返回绝对路径或抛错。"""
    p = os.path.abspath(path)
    if not p.startswith(os.path.abspath(ROOT)):
        raise PermissionError("路径越界（仅允许项目目录内）: %s" % p)
    return p


def scan_script_text(text):
    """扫描生成的脚本文本，发现禁止模式则返回问题列表。"""
    hits = [pat for pat in FORBIDDEN_PATTERNS if pat in text]
    return hits
