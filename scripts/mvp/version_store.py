#!/usr/bin/env python
"""M6 版本管理：命名快照、最多 20 步撤销、版本回放。"""
import json
import os
import shutil

MAX_UNDO = 20


class VersionStore:
    def __init__(self, root):
        self.dir = root
        os.makedirs(self.dir, exist_ok=True)
        self.index_path = os.path.join(self.dir, "index.json")
        self.index = self._load()

    def _load(self):
        if os.path.exists(self.index_path):
            with open(self.index_path, encoding="utf-8") as f:
                return json.load(f)
        return {"versions": [], "current": None}

    def _save_index(self):
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(self.index, f, ensure_ascii=False, indent=2)

    def save(self, name, scene, extra_files=None):
        """保存一个命名版本（scene JSON + 可选附件）；同名则自动递增版本号。"""
        if name in self.index["versions"]:
            base, i = name, 2
            while ("%s_v%d" % (base, i)) in self.index["versions"]:
                i += 1
            name = "%s_v%d" % (base, i)
        vdir = os.path.join(self.dir, name)
        os.makedirs(vdir, exist_ok=True)
        with open(os.path.join(vdir, "scene.json"), "w", encoding="utf-8") as f:
            json.dump(scene, f, ensure_ascii=False, indent=2)
        for p in (extra_files or []):
            if os.path.exists(p):
                shutil.copy2(p, os.path.join(vdir, os.path.basename(p)))
        if name not in self.index["versions"]:
            self.index["versions"].append(name)
        # 撤销栈最多 20
        if len(self.index["versions"]) > MAX_UNDO:
            drop = self.index["versions"].pop(0)
            shutil.rmtree(os.path.join(self.dir, drop), ignore_errors=True)
        self.index["current"] = name
        self._save_index()
        return vdir

    def list(self):
        return list(self.index["versions"])

    def undo(self):
        """回退到上一个版本（并返回该版本名）。"""
        vs = self.index["versions"]
        if len(vs) < 2:
            return None
        vs.pop()
        self.index["current"] = vs[-1]
        self._save_index()
        return vs[-1]

    def restore(self, name):
        p = os.path.join(self.dir, name, "scene.json")
        if not os.path.exists(p):
            return None
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def clone_scene(self, name, new_name):
        sc = self.restore(name)
        if sc is None:
            return None
        return self.save(new_name, sc)
