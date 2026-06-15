"""
诊断 EXE 模式下的单实例锁行为
"""
import sys, os
sys.stdout.reconfigure(encoding="utf-8")

# 模拟 PyInstaller EXE 环境
sys.frozen = True
sys._MEIPASS = os.path.dirname(sys.executable)

print(f"[诊断] 模拟 EXE 模式")
print(f"  sys.frozen = {sys.frozen}")
print(f"  sys._MEIPASS = {sys._MEIPASS}")

# 模拟 desktop_auto 模块加载
import desktop_auto as da
print(f"\n[诊断] desktop_auto 已加载")

# 测试单实例锁
print(f"\n[诊断] 测试 _try_acquire_single_instance() ...")
result = da._try_acquire_single_instance()
print(f"  结果: {result}")
print(f"  _SINGLE_INSTANCE_MEMORY: {da._SINGLE_INSTANCE_MEMORY}")
print(f"  类型: {type(da._SINGLE_INSTANCE_MEMORY)}")

# 第二次调用（模拟第二个进程）
print(f"\n[诊断] 第二次调用（模拟第二个进程）...")
result2 = da._try_acquire_single_instance()
print(f"  结果: {result2}")
print(f"  _SINGLE_INSTANCE_MEMORY: {da._SINGLE_INSTANCE_MEMORY}")

if result and result2:
    print(f"\n⚠️ 两次都返回 True，说明锁没拦住！")
elif result and not result2:
    print(f"\n✅ 单实例锁正常：第一次 True，第二次 False")
else:
    print(f"\n❓ 第一次返回 False，说明立即检测到已有实例")