#!/usr/bin/env python
"""MVP 指标：刀模折线识别召回率评测（自建标准样张，目标 >=85%）。"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "mvp"))
from dieline import analyze  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main():
    d = os.path.join(ROOT, "tests", "mvp_dieline_cases")
    truth = json.load(open(os.path.join(d, "ground_truth.json"), encoding="utf-8"))
    hit = total = 0
    for fn, n_true in sorted(truth.items()):
        got = analyze(os.path.join(d, fn))["crease_candidates"]
        hit += min(got, n_true); total += n_true
        print("%-12s 真实折线=%d 识别=%d %s" % (fn, n_true, got, "OK" if got >= n_true else "MISS"))
    rate = hit / total * 100 if total else 0
    print("折线召回率: %d/%d = %.1f%% (目标 >=85%%)" % (hit, total, rate))
    sys.exit(0 if rate >= 85 else 1)


if __name__ == "__main__":
    main()
