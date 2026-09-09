"""冒烟测试：验证 Blender 无头模式可运行、可建物体。

用法: blender --background --python tests/smoke_test.py --python-exit-code 1
"""
import bpy

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_cube_add(size=1)
print("[SMOKE OK] blender", bpy.app.version_string, "cube_count =", len(bpy.data.objects))
