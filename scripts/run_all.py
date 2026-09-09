#!/usr/bin/env python
"""一键复现：按依赖顺序运行仓库全部程序并汇总结果。

用法:
    python scripts/run_all.py                      # 自动探测 Blender/Python
    python scripts/run_all.py --blender <路径>      # 指定 Blender
    python scripts/run_all.py --keep-going          # 某步失败仍继续

前置：Python 需安装 Pillow、numpy（预处理用）；Blender 3.6+。
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(ROOT, 'logs')


def find_blender():
    exe = os.environ.get('BLENDER_EXE')
    if exe and os.path.exists(exe):
        return exe
    w = shutil.which('blender')
    if w:
        return w
    cands = []
    bases = [r'C:\Program Files\Blender Foundation',
             r'C:\Program Files (x86)\Blender Foundation',
             os.path.expandvars(r'%LOCALAPPDATA%\Programs\Blender Foundation')]
    for base in bases:
        if os.path.isdir(base):
            for d in glob.glob(os.path.join(base, 'Blender*')):
                p = os.path.join(d, 'blender.exe')
                if os.path.exists(p):
                    name = os.path.basename(d).lower()
                    try:
                        ver = tuple(int(x) for x in name.split('blender')[1].strip().split('.'))
                    except Exception:
                        ver = (0,)
                    cands.append((ver, p))
    if cands:
        cands.sort(key=lambda x: x[0])
        return cands[-1][1]
    return None


def _python_ok(exe):
    try:
        r = subprocess.run([exe, '-c', 'import sys'], capture_output=True, timeout=15)
        return r.returncode == 0
    except Exception:
        return False


def find_python():
    exe = os.environ.get('PYTHON_EXE')
    if exe and os.path.exists(exe):
        return exe
    for name in ('python', 'python3', 'py'):
        w = shutil.which(name)
        if not w:
            continue
        if 'windowsapps' in w.lower():  # 微软商店占位符，跳过
            continue
        if _python_ok(w):
            return w
    return None


def run(cmd, name):
    os.makedirs(LOG_DIR, exist_ok=True)
    log = os.path.join(LOG_DIR, 'run_all_%s.log' % name)
    print('\n[%s] 开始...' % name)
    with open(log, 'w', encoding='utf-8') as f:
        t0 = time.time()
        cp = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
        dt = time.time() - t0
    ok = cp.returncode == 0
    print('[%s] exit=%s 耗时%.1fs -> %s' % (name, cp.returncode, dt, 'OK' if ok else 'FAIL'))
    if not ok:
        try:
            with open(log, encoding='utf-8', errors='ignore') as f:
                tail = ''.join(f.readlines()[-18:])
        except Exception:
            tail = ''
        print('----- 日志尾部 -----')
        print(tail)
        print('-------------------')
    return ok


def main():
    ap = argparse.ArgumentParser(description='一键复现仓库全部程序')
    ap.add_argument('--blender', help='Blender 可执行文件路径')
    ap.add_argument('--python', dest='python_exe', help='Python 可执行文件路径(需含 Pillow/numpy)')
    ap.add_argument('--keep-going', action='store_true', help='某步失败后继续')
    args = ap.parse_args()

    blender = args.blender or find_blender()
    pyexe = args.python_exe or find_python()
    if not blender:
        print('[错误] 未找到 Blender。请 --blender <路径> 指定。')
        sys.exit(2)
    if not pyexe:
        print('[错误] 未找到 Python。请 --python <路径> 指定(需含 Pillow/numpy)。')
        sys.exit(2)
    print('Blender :', blender)
    print('Python  :', pyexe)

    S = os.path.join(ROOT, 'scripts')
    T = os.path.join(ROOT, 'tests')
    BL = [blender, '--background', '--factory-startup']

    def b(script, *extra):
        return BL + ['--python', os.path.join(ROOT, script)] + (['--'] + list(extra) if extra else [])

    def p(script, *extra):
        return [pyexe, os.path.join(ROOT, script)] + list(extra)

    steps = [
        ('smoke_test', BL + ['--python', os.path.join(T, 'smoke_test.py'), '--python-exit-code', '1']),
        ('make_placeholder_front', p(S + '/make_placeholder_front.py', os.path.join('assets', 'front.png'))),
        ('make_fefco_dieline', p(S + '/make_fefco_dieline.py')),
        ('make_relief_maps', p(S + '/make_relief_maps.py', '--input', os.path.join('assets', '鹿乃2.jpg'),
                               '--albedo', os.path.join('assets', 'relief_albedo.png'),
                               '--height', os.path.join('assets', 'relief_height.png'))),
        ('P1_build_pack', b(S + '/build_pack.py', '--front', os.path.join('assets', 'front.png'),
                            '--out', os.path.join('output', 'preview'))),
        ('P2_person_relief', b(S + '/person_relief.py',
                               '--albedo', os.path.join('assets', 'relief_albedo.png'),
                               '--height', os.path.join('assets', 'relief_height.png'),
                               '--out', os.path.join('output', 'person'))),
        ('P3_build_housing', b(S + '/build_housing.py', '--out', os.path.join('output', 'housing'))),
        ('P4_build_hydraulic', b(S + '/build_hydraulic.py', '--out', os.path.join('output', 'hydraulic'))),
    ]
    for tag, glb in [('preview', 'preview'), ('person', 'person'), ('housing', 'housing'), ('hydraulic', 'hydraulic')]:
        steps.append(('blend_' + tag, b(S + '/make_blend_view.py',
                                        '--glb', os.path.join('output', glb + '.glb'),
                                        '--out', os.path.join('output', glb + '_view.blend'))))
    for tag, glb in [('preview', 'preview'), ('person', 'person'), ('housing', 'housing'), ('hydraulic', 'hydraulic')]:
        steps.append(('render_' + tag, b(S + '/render_glb.py',
                                         '--glb', os.path.join('output', glb + '.glb'),
                                         '--out', os.path.join('output', tag),
                                         '--res', '1600')))

    fails = []
    for name, cmd in steps:
        ok = run(cmd, name)
        if not ok:
            fails.append(name)
            if not args.keep_going:
                print('\n[停止] 步骤 %s 失败。修复后重跑，或用 --keep-going 继续后续步骤。' % name)
                break

    print('\n================ 汇总 ================')
    total = len(steps)
    done = total if not fails or args.keep_going else steps.index((fails[0], None)) if False else (total - len(fails)) if fails else total
    print('通过 %d/%d 步' % (done, total))
    if fails:
        print('失败步骤:', ', '.join(fails))
        sys.exit(1)
    print('全部成功！产物见 output/ 与 assets/。')


if __name__ == '__main__':
    main()
