#!/usr/bin/env python
"""MVP 指标评测：意图解析准确率（20 条固定用例，目标 >= 90%）。"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "mvp"))
from nl_parser import parse, get_path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main():
    with open(os.path.join(ROOT, "tests", "mvp_intent_cases.json"), encoding="utf-8") as f:
        cases = json.load(f)
    ok = 0
    fails = []
    for i, c in enumerate(cases, 1):
        scene, _ = parse(c["text"])
        bad = []
        for group, expects in c["expect"].items():
            for k, v in expects.items():
                got = get_path(scene, "%s.%s" % (group, k))
                if isinstance(v, dict):
                    for k2, v2 in v.items():
                        got2 = get_path(scene, "%s.%s.%s" % (group, k, k2))
                        if got2 != v2:
                            bad.append("%s.%s.%s: 期望%s 实际%s" % (group, k, k2, v2, got2))
                elif got != v:
                    bad.append("%s.%s: 期望%s 实际%s" % (group, k, v, got))
        if bad:
            fails.append((i, c["text"], bad))
        else:
            ok += 1
    rate = ok / len(cases) * 100
    print("意图解析准确率: %d/%d = %.1f%% (目标 >=90%%)" % (ok, len(cases), rate))
    for i, text, bad in fails:
        print("  [FAIL %d] %s" % (i, text))
        for b in bad:
            print("          -", b)
    sys.exit(0 if rate >= 90 else 1)


if __name__ == "__main__":
    main()
