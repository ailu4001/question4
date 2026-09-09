"""Blender/Python 工具（跨脚本复用，避免重复代码）。"""
import glob
import os
import shutil


def find_blender():
    """自动探测 Blender 可执行文件：环境变量 > PATH > 常见安装路径。"""
    exe = os.environ.get("BLENDER_EXE")
    if exe and os.path.exists(exe):
        return exe
    w = shutil.which("blender")
    if w:
        return w
    cands = []
    for base in [r"C:\Program Files\Blender Foundation",
                 r"C:\Program Files (x86)\Blender Foundation",
                 os.path.expandvars(r"%LOCALAPPDATA%\Programs\Blender Foundation")]:
        if os.path.isdir(base):
            for d in glob.glob(os.path.join(base, "Blender*")):
                p = os.path.join(d, "blender.exe")
                if os.path.exists(p):
                    try:
                        ver = tuple(int(x) for x in os.path.basename(d).split()[1].split("."))
                    except Exception:
                        ver = (0,)
                    cands.append((ver, p))
    if cands:
        cands.sort(key=lambda x: x[0])
        return cands[-1][1]
    return None
