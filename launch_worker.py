"""Step 2-2B: 启动工作线程模块 (从 desktop_auto.py 抽出)

包含:
- ShortcutInfo 数据类
- _get_pyautogui 懒加载 helper
- _resolve_sample_path 模板路径解析 helper (独立实现, 不依赖 desktop_auto 私有符号)
- LaunchWorker QThread 子类, 支持 4 种启动模式 (direct/shell/image/desktop)

注:
- _DiaryWorker / _ChunkWorker 仍嵌在 MainWindow._generate_diary_async / _generate_chunk_async 内
  (护栏测试要求它们在 desktop_auto.py 源中)
- _save_match_coord 改为回调注入模式 (coord_saver 参数), 避免循环 import desktop_auto
"""
from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QMessageBox

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. 懒加载 pyautogui (与 desktop_auto.py:318-323 同源)
# ---------------------------------------------------------------------------
def _get_pyautogui():
    """懒加载 pyautogui,避免启动阶段间接导入 numpy。"""
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.3
    return pyautogui


# ---------------------------------------------------------------------------
# 2. 数据模型 (与 desktop_auto.py:339-349 同源)
# ---------------------------------------------------------------------------
@dataclass
class ShortcutInfo:
    name: str
    target: str
    lnk_path: str
    work_dir: str = ""
    icon_samples: list[str] = field(default_factory=list)  # 多模板路径
    launch_mode: str = ""  # 绑定的启动方式 (desktop/direct/shell/image/coord),空=跟随 UI 单选按钮
    _coord_x: int = 0     # 绑定的坐标 (快捷方式级别,优先于 UI)
    _coord_y: int = 0
    _click_type: str = "left_double"


# ---------------------------------------------------------------------------
# 3. 模板路径解析 (从 desktop_auto.py:455-474 抽出, 改为独立实现)
# ---------------------------------------------------------------------------
def _resolve_sample_path(raw: str | Path) -> Path:
    """兼容旧的 samples 路径,并优先映射到当前数据目录。

    独立实现:不依赖 desktop_auto.py 的私有 helper (_samples_dir / _current_user_data_dir),
    直接走 data_paths.resolve_user_data_dir() 拿当前数据目录。
    """
    from data_paths import resolve_user_data_dir
    p = Path(raw)
    sample_dir = resolve_user_data_dir() / "samples"
    if p.name:
        current_sample = sample_dir / p.name
        if "samples" in p.parts:
            return current_sample
        if current_sample.exists():
            return current_sample
    if p.exists():
        return p
    if not p.is_absolute():
        q = resolve_user_data_dir() / p
        if q.exists():
            return q
        q2 = sample_dir / p.name
        if q2.exists():
            return q2
    return p


# ---------------------------------------------------------------------------
# 4. LaunchWorker 主类
# ---------------------------------------------------------------------------
# coord_saver 回调签名: (info: ShortcutInfo, cx: int, cy: int) -> None
CoordSaver = Callable[[ShortcutInfo, int, int], None]


class LaunchWorker(QThread):
    """执行启动 + 等待窗口 + 键鼠交互的工作线程

    新增参数 (Step 2-2B):
        coord_saver: 模板匹配成功后的回调, 由 desktop_auto.py 注入以写入 shortcut_meta.json
                     若为 None 则不保存 (向后兼容)

    4 种启动模式: direct / shell / image / desktop
    """
    log_signal = Signal(str)
    finished_signal = Signal(bool, str)

    def __init__(self, info: ShortcutInfo, mode: str, do_notepad: bool,
                 extra_args: str = "", coord: dict = None,
                 coord_saver: Optional[CoordSaver] = None):
        super().__init__()
        self.info = info
        self.mode = mode          # "direct" | "shell" | "image" | "desktop"
        self.do_notepad = do_notepad
        self.extra_args = self._parse_args(extra_args)
        self.coord = coord or {}  # 坐标点击参数: {"x", "y", "click_type"}
        self.coord_saver = coord_saver  # Step 2-2B: 抽出后用回调注入代替 desktop_auto 私有 helper
        self._cancel = False

    @staticmethod
    def _parse_args(text: str) -> list[str]:
        """按空格分隔,但保留引号里的整体。简单实现: shlex.split"""
        import shlex
        try:
            return shlex.split(text) if text.strip() else []
        except Exception:
            return text.split()

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        try:
            if self.mode == "direct":
                self._launch_direct()
            elif self.mode == "shell":
                self._launch_shell()
            elif self.mode == "image":
                self._launch_by_image()
            elif self.mode == "desktop":
                self._launch_desktop_click()
            else:
                raise ValueError(f"未知模式: {self.mode}")
            if self.do_notepad and not self._cancel:
                self._interact_notepad()
            self.finished_signal.emit(True, "执行完成")
        except Exception as e:
            log.exception("执行失败")
            self.finished_signal.emit(False, str(e))

    # ---- 5.1 直接启动 (Popen 方式) ----
    def _launch_direct(self) -> None:
        info = self.info
        if not info.target:
            QMessageBox.warning(None, "提示", f"快捷方式目标路径为空: {info.name}\n请重新扫描或检查快捷方式是否有效。")
            return
        if not Path(info.target).exists():
            QMessageBox.warning(None, "提示", f"目标程序不存在: {info.target}\n请检查快捷方式是否指向有效路径。")
            return
        self.log_signal.emit(f"🚀 直接启动 (Popen): {info.target}")
        # Electron / 资源敏感型应用必须传 cwd,否则找不到资源崩
        # 优先用快捷方式里的 WorkingDirectory,退化用 target 所在目录
        cwd = info.work_dir if info.work_dir and Path(info.work_dir).is_dir() else str(Path(info.target).parent)
        if cwd != info.work_dir:
            self.log_signal.emit(f"   📂 使用工作目录: {cwd}")
        # CREATE_NO_WINDOW=0x08000000 避免控制台程序弹黑窗;GUI 客户端会正常弹窗口
        # 不要用 DETACHED_PROCESS(0x00000008),会启动但不显示 GUI
        subprocess.Popen(
            [info.target],
            cwd=cwd,
            creationflags=0x08000000,
        )
        self._wait_window_ready(info.name, timeout=20)

    # ---- 5.1b Shell 启动 (走 cmd /c start,完全脱离 Python 进程上下文) ----
    def _launch_shell(self) -> None:
        info = self.info
        if not info.target or not Path(info.target).exists():
            raise FileNotFoundError(f"目标程序不存在: {info.target}")
        self.log_signal.emit(f"🚀 Shell 启动: {info.target}")
        cwd = info.work_dir if info.work_dir and Path(info.work_dir).is_dir() else str(Path(info.target).parent)
        self.log_signal.emit(f"   📂 工作目录: {cwd}")
        # 每个参数独立加引号
        args_parts = ['"{}"'.format(info.target)]
        for a in self.extra_args:
            args_parts.append('"{}"'.format(a) if " " in a else a)
        args_str = " ".join(args_parts)
        if self.extra_args:
            self.log_signal.emit(f"   🎛️ 启动参数: {' '.join(self.extra_args)}")
        cmd_str = 'cd /d "{}" && {}'.format(cwd, args_str)
        self.log_signal.emit(f"   🔧 执行: cmd /c {cmd_str}")
        # CREATE_NEW_CONSOLE = 0x00000010,给 GUI 应用一个独立控制台
        subprocess.Popen(
            ["cmd", "/c", cmd_str],
            creationflags=0x00000010,
        )
        self._wait_window_ready(info.name, timeout=20)

    # ---- 5.2 图像识别启动 ----
    def _launch_by_image(self) -> None:
        info = self.info
        # 优先使用用户输入的坐标 (从 MainWindow 传入)
        x = self.coord.get("x", 0)
        y = self.coord.get("y", 0)
        click_type = self.coord.get("click_type", "left_double")
        samples = [str(_resolve_sample_path(s)) for s in info.icon_samples if _resolve_sample_path(s).exists()]

        # 如果有坐标,优先按坐标点击
        if x > 0 or y > 0:
            self.log_signal.emit(f"🎯 坐标点击模式: ({x}, {y}) 类型={click_type}")
            import pyautogui as pa
            self.log_signal.emit(f"   按 Win+D 显示桌面...")
            pa.hotkey('win', 'd')
            time.sleep(0.5)
            if click_type == "left_double":
                pa.doubleClick(x, y)
            elif click_type == "right_single":
                pa.click(x, y, button="right")
            else:
                pa.click(x, y)
            self.log_signal.emit(f"   ✅ 已点击")
            self._wait_window_ready(info.name, timeout=20)
            return

        # 退化: 有模板就报模板 (已不一定能匹配了)
        if not samples:
            raise FileNotFoundError("请先设置坐标(X>0 或 Y>0)或加载图标模板")
        self.log_signal.emit(f"⚠️ 未设置坐标,使用模板匹配 (可能失败)")
        pyautogui = _get_pyautogui()
        # 后面的逻辑保留作为兑底
        center = None
        for sample in samples:
            try:
                box = pyautogui.locateOnScreen(sample, confidence=0.7, grayscale=False)
                if box:
                    center = pyautogui.center(box)
                    self.log_signal.emit(f"✅ 命中模板: {Path(sample).name} @ {center}")
                    break
            except Exception as e:
                self.log_signal.emit(f"⚠️ 模板 {Path(sample).name} 识别失败: {e}")
        if not center:
            raise RuntimeError("屏幕上找不到该图标,请设置坐标 (X>0 或 Y>0)")
        pyautogui.click(center)
        self._wait_window_ready(info.name, timeout=20)

    # ---- 5.2b 双击桌面快捷方式 (仅模板匹配, 不再走多段兜底) ----
    def _launch_desktop_click(self) -> None:
        info = self.info
        self.log_signal.emit(f"🖱️ 鼠标双击桌面图标: {info.name}")

        # B. 仅使用截图模板匹配 (最精准) - 不再走 A/C/explorer 兜底
        try:
            self._launch_desktop_click_by_image(info)
            self._wait_window_ready(info.name, timeout=20)
            return
        except Exception as e:
            self.log_signal.emit(f"   ❌ 模板匹配失败: {e}")

        # B'. 仅在用户手动设置了坐标时才采用 (用户主动指定, 不算自动兜底)
        x = self.coord.get("x", 0) if self.coord else 0
        y = self.coord.get("y", 0) if self.coord else 0
        click_type = self.coord.get("click_type", "left_double") if self.coord else "left_double"
        if x > 0 or y > 0:
            self.log_signal.emit(f"   🎯 使用用户手动设置的坐标 ({x}, {y}) 类型={click_type}")
            import pyautogui as pa
            import time as _t
            pa.hotkey('win', 'd')
            _t.sleep(0.3)
            if click_type == "right_single":
                pa.click(x, y, button="right")
            elif click_type == "left_single":
                pa.click(x, y)
            else:
                pa.doubleClick(x, y)
            self.log_signal.emit(f"   ✅ 已点击")
            self._wait_window_ready(info.name, timeout=20)
            return

        raise RuntimeError("模板匹配失败且未设置坐标，请重新采集模板或手动设置坐标。")

    def _launch_desktop_click_via_shell(self, info):
        """A 段: 走 IShellFolder + ListView 拿真实坐标"""
        # 最小化所有窗口,露出干净桌面
        self.log_signal.emit(f"   🪟 最小化所有窗口露出桌面...")
        import pyautogui
        import time
        pyautogui.hotkey('win', 'd')  # Win+D 显示桌面
        time.sleep(0.3)

        # 1) 枚举桌面项目,按 name 拿到 PIDL 的"逻辑位置"
        from win32com.shell import shell as win32shell

        self.log_signal.emit(f"   📂 枚举桌面 IShellFolder...")
        try:
            desktop_folder = win32shell.SHGetDesktopFolder()
        except Exception as e:
            raise RuntimeError(f"拿不到 desktop folder: {e}")

        # flag = 0x70 = FOLDERS(0x20) | NONFOLDERS(0x40) | CHECKING_FOR_CHILDREN(0x10)
        # 0x30 漏掉了 .lnk 以外的快捷方式,必须用 0x70
        enum = desktop_folder.EnumObjects(0, 0x70)
        # pywin32 的 Next 返回 [[pidl_bytes]],pidl 在 [0][0]
        items = []
        i = 0
        while True:
            wrapped = enum.Next(1)
            if not wrapped:
                break
            pidl = wrapped[0][0]
            # GetDisplayNameOf 需要 wrapped[0] 整体
            name_obj = desktop_folder.GetDisplayNameOf(wrapped[0], 0x1)
            if isinstance(name_obj, list):
                name_obj = name_obj[0]
            items.append((str(name_obj), i))
            i += 1

        self.log_signal.emit(f"   共 {len(items)} 个桌面项目")

        # 找匹配项
        target_logical_idx = -1
        for name, idx in items:
            n = name.lower().strip().rstrip('.lnk')
            want = info.name.lower().strip().rstrip('.lnk')
            if n == want or want in n or n in want:
                target_logical_idx = idx
                self.log_signal.emit(f"   🎯 匹配 {idx}: {name}")
                break

        if target_logical_idx < 0:
            raise RuntimeError(f"桌面 IShellFolder 找不到 {info.name}")

        # 2) 找 ListView,按逻辑 idx 拿位置 (每次都重新枚举,不缓存)
        self._desktop_listview = None
        import ctypes
        import ctypes.wintypes
        user32 = ctypes.windll.user32
        GetClassNameW = user32.GetClassNameW
        GetWindowRect = user32.GetWindowRect
        FindWindowW = user32.FindWindowW
        SendMessage = user32.SendMessageW
        EnumChildWindows = user32.EnumChildWindows

        # 用可变对象实现闭包变量修改(避免 global 问题)
        defvw_container = {'hwnd': None}

        def cb_child(hwnd, l):
            cls = ctypes.create_unicode_buffer(256)
            GetClassNameW(hwnd, cls, 256)
            if cls.value == "SysListView32":
                defvw_container['hwnd'] = hwnd
                return False
            return True

        EnumChildProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        cb_fn = EnumChildProc(cb_child)

        self.log_signal.emit(f"   🔍 查找 Progman...")
        progman = FindWindowW("Progman", None)
        if progman:
            self.log_signal.emit(f"   ✅ 找到 Progman,枚举子窗口...")
            EnumChildWindows(progman, cb_fn, 0)
        else:
            self.log_signal.emit(f"   ⚠️ Progman 未找到")

        if not defvw_container['hwnd']:
            self.log_signal.emit(f"   🔍 Progman 下没找到 SysListView32,枚举 WorkerW...")

            def cb_top(hwnd, l):
                cls = ctypes.create_unicode_buffer(256)
                GetClassNameW(hwnd, cls, 256)
                if cls.value == "WorkerW":
                    EnumChildWindows(hwnd, cb_fn, 0)
                return not bool(defvw_container['hwnd'])

            user32.EnumWindows(EnumChildProc(cb_top), 0)

        defvw = defvw_container['hwnd']
        self.log_signal.emit(f"   📋 ListView 查找结果: hwnd={defvw}")
        if not defvw:
            # ListView 找不到,但 logical_idx 仍然有效 -> 交给调用者走网格兜底
            self.log_signal.emit(f"   ⚠️ 桌面 ListView 找不到,退到网格估算 (idx={target_logical_idx})")
            raise RuntimeError("ListView 找不到,logical_idx 仍可用")
        else:
            self.log_signal.emit(f"   ✅ 找到 ListView hwnd={defvw}, idx={target_logical_idx}")

        # 3) 纯后台点击: 给 SysListView32 发送 WM_LBUTTONDBLCLK 消息
        # LVM_GETITEMPOSITION 经常返回 0,0,用网格估算图标在 ListView 内的客户区坐标
        LVM_GETITEMPOSITION = 0x1010
        WM_LBUTTONDOWN = 0x0201
        WM_LBUTTONUP = 0x0202
        WM_LBUTTONDBLCLK = 0x0203
        MK_LBUTTON = 0x0001

        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        pt = POINT()
        SendMessage(defvw, LVM_GETITEMPOSITION, target_logical_idx, ctypes.byref(pt))

        if pt.x == 0 and pt.y == 0:
            # 兜底: 用桌面图标常见网格 (Win10 默认: 75x95 网格)
            self.log_signal.emit(f"   ⚠️ LVM_GETITEMPOSITION 返回 0,0,改用网格估算")
            col = target_logical_idx % 8
            row = target_logical_idx // 8
            pt.x = 30 + col * 95 + 16  # 图标中心
            pt.y = 30 + row * 100 + 16
            self.log_signal.emit(f"   📍 A段网格估算(客户区坐标): ({pt.x}, {pt.y}) (idx={target_logical_idx})")
        else:
            pt.x += 16  # 图标中心
            pt.y += 16
            self.log_signal.emit(f"   📍 A段真实坐标(客户区坐标): ({pt.x}, {pt.y})")

        # 计算 lParam: 低位 x,高位 y
        lparam = (pt.y << 16) | (pt.x & 0xFFFF)

        # 纯后台点击: 发送消息到 SysListView32 窗口
        self.log_signal.emit(f"   🖱️ 后台双击 (SendMessage) hwnd={hex(defvw)}")
        # 发送双击消息序列 (模拟真实双击)
        SendMessage(defvw, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
        time.sleep(0.05)
        SendMessage(defvw, WM_LBUTTONUP, 0, lparam)
        time.sleep(0.05)
        SendMessage(defvw, WM_LBUTTONDBLCLK, MK_LBUTTON, lparam)
        time.sleep(0.05)
        SendMessage(defvw, WM_LBUTTONUP, 0, lparam)

        self.log_signal.emit(f"   ✅ 后台双击完成")
        return target_logical_idx

    def _launch_via_explorer(self, info) -> None:
        """备选: 通过 explorer.exe 间接打开快捷方式,绕过 runtime 环境限制"""
        import subprocess
        self.log_signal.emit(f"   🚀 通过 explorer.exe 启动: {info.name}")
        try:
            # 走 shell=True 调用 explorer.exe 去打开快捷方式
            cmd = f'explorer.exe "{info.lnk_path}"'
            subprocess.Popen(cmd, shell=True)
            self.log_signal.emit(f"   ✅ explorer 调用完成")
        except Exception as e:
            self.log_signal.emit(f"   ⚠️ explorer 启动失败: {e}")
            raise

    def _launch_desktop_click_by_image(self, info) -> None:
        """B 段: 从 samples/ 找 info.name 开头的 PNG 作为模板,locateOnScreen 后双击"""
        self.log_signal.emit(f"   📸 找桌面截图模板...")
        from data_paths import resolve_user_data_dir
        sample_dir = resolve_user_data_dir() / "samples"
        candidates = list(sample_dir.glob(f"{info.name}_*.png")) if sample_dir.exists() else []
        if not candidates:
            raise FileNotFoundError(
                f"请先用「截图框选」工具对桌面 {info.name} 图标截一张图,保存到 samples/ 目录"
            )

        # 最小化所有窗口,露出干净桌面
        self.log_signal.emit(f"   🪟 最小化所有窗口露出桌面...")
        import pyautogui
        pyautogui.hotkey('win', 'd')  # Win+D 显示桌面
        import time
        time.sleep(0.5)

        self.log_signal.emit(f"   找到 {len(candidates)} 个模板,开始匹配...")
        for c in candidates:
            try:
                self.log_signal.emit(f"   🔍 匹配模板: {c.name}")
                # 先截全屏保存调试
                screen = pyautogui.screenshot()
                debug_path = sample_dir / "_debug_screen.png"
                debug_path.parent.mkdir(parents=True, exist_ok=True)
                screen.save(str(debug_path))
                self.log_signal.emit(f"   📸 全屏截图已保存: {debug_path}")

                # 优先用 OpenCV 匹配（快 10-50x），PIL 作为最后兜底
                matched = False
                try:
                    import cv2
                    import numpy as np
                    screen_np = np.array(screen)
                    screen_gray = cv2.cvtColor(screen_np, cv2.COLOR_RGB2GRAY)
                    # cv2.imread 不支持非 ASCII 路径,改用 np.fromfile + cv2.imdecode
                    tpl_bgr = cv2.imdecode(np.fromfile(str(c), dtype=np.uint8), cv2.IMREAD_COLOR)
                    if tpl_bgr is None:
                        raise RuntimeError(f"无法读取模板: {c}")
                    tpl_gray = cv2.cvtColor(tpl_bgr, cv2.COLOR_BGR2GRAY)
                    th, tw = tpl_gray.shape
                    sh, sw = screen_gray.shape
                    if tw > sw or th > sh:
                        raise RuntimeError("模板大于屏幕")
                    # 多尺度匹配 (含 0.8x 125% DPI)
                    best_overall = 0.0
                    best_pos = None
                    best_scale = 1.0
                    for scale in [0.6, 0.8, 1.0, 1.2, 1.5]:
                        nw, nh = int(tw * scale), int(th * scale)
                        if nw < 8 or nh < 8 or nw > sw or nh > sh:
                            continue
                        scaled = cv2.resize(tpl_gray, (nw, nh), interpolation=cv2.INTER_AREA)
                        result = cv2.matchTemplate(screen_gray, scaled, cv2.TM_CCOEFF_NORMED)
                        _, mv, _, ml = cv2.minMaxLoc(result)
                        if mv > best_overall:
                            best_overall = mv
                            best_pos = (ml[0], ml[1], nw, nh)
                            best_scale = scale
                    if best_pos and best_overall >= 0.35:
                        cx = best_pos[0] + best_pos[2] // 2
                        cy = best_pos[1] + best_pos[3] // 2
                        self.log_signal.emit(f"   ✅ OpenCV 找到: 缩放={best_scale} 置信度={best_overall:.3f} @ ({cx}, {cy})")
                        self._save_match_coord(info, cx, cy)
                        pyautogui.doubleClick(cx, cy)
                        self.log_signal.emit(f"   ✅ 双击完成")
                        return  # 匹配成功，直接返回，不走兜底
                    else:
                        self.log_signal.emit(f"   ⚠️ OpenCV 置信度低: {best_overall:.3f}, 尝试 PIL...")
                except ImportError:
                    self.log_signal.emit(f"   ⚠️ OpenCV 未安装, 用 PIL 兜底...")
                except Exception as e:
                    self.log_signal.emit(f"   ⚠️ OpenCV 异常: {e}, 用 PIL 兜底...")

                if not matched:
                    # PIL 兜底（仅在 OpenCV 不可用时）
                    try:
                        from image_match import locate_on_screen, get_center
                        box = locate_on_screen(str(c), confidence=0.6, screenshot=screen)
                        if box:
                            cx, cy = get_center(box)
                            self.log_signal.emit(f"   ✅ PIL 找到: ({cx}, {cy})")
                            self._save_match_coord(info, cx, cy)
                            time.sleep(0.2)
                            pyautogui.doubleClick(cx, cy)
                            self.log_signal.emit(f"   ✅ 双击完成")
                            return  # 匹配成功，直接返回
                        else:
                            self.log_signal.emit(f"   ❌ PIL 也未匹配")
                    except Exception as e:
                        self.log_signal.emit(f"   ⚠️ PIL 匹配异常: {e}")
            except Exception as e:
                self.log_signal.emit(f"   ⚠️ 匹配异常 {c.name}: {e}")
                continue
        raise RuntimeError("截图匹配也没找到")

    def _fetch_logical_idx_only(self, info) -> Optional[int]:
        """只走 IShellFolder 枚举,拿到目标在 ListView 中的逻辑 idx,不调 ListView"""
        from win32com.shell import shell as win32shell

        self.log_signal.emit(f"   📂 C 段: 仅枚举 IShellFolder...")
        try:
            desktop_folder = win32shell.SHGetDesktopFolder()
        except Exception as e:
            self.log_signal.emit(f"   ⚠️ 拿不到 desktop folder: {e}")
            return None

        enum = desktop_folder.EnumObjects(0, 0x70)
        i = 0
        while True:
            wrapped = enum.Next(1)
            if not wrapped:
                break
            name_obj = desktop_folder.GetDisplayNameOf(wrapped[0], 0x1)
            if isinstance(name_obj, list):
                name_obj = name_obj[0]
            name = str(name_obj).lower().strip().rstrip('.lnk')
            want = info.name.lower().strip().rstrip('.lnk')
            if name == want or want in name or name in want:
                self.log_signal.emit(f"   🎯 C 段匹配 idx={i}: {name_obj}")
                return i
            i += 1
        return None

    def _click_at_logical_idx(self, logical_idx: int) -> None:
        """拿到 logical_idx 后,用网格估算屏幕坐标并双击"""
        import ctypes
        import ctypes.wintypes
        user32 = ctypes.windll.user32
        GetClassNameW = user32.GetClassNameW
        GetWindowRect = user32.GetWindowRect
        FindWindowW = user32.FindWindowW
        SendMessage = user32.SendMessageW
        EnumChildWindows = user32.EnumChildWindows

        # 找 ListView (用可变对象修复闭包变量问题)
        defvw_container = {'hwnd': None}
        EnumChildProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

        def cb_child(hwnd, l):
            cls = ctypes.create_unicode_buffer(256)
            GetClassNameW(hwnd, cls, 256)
            if cls.value == "SysListView32":
                defvw_container['hwnd'] = hwnd
                return False
            return True

        cb_fn = EnumChildProc(cb_child)
        progman = FindWindowW("Progman", None)
        if progman:
            EnumChildWindows(progman, cb_fn, 0)
        if not defvw_container['hwnd']:
            def cb_top(hwnd, l):
                cls = ctypes.create_unicode_buffer(256)
                GetClassNameW(hwnd, cls, 256)
                if cls.value == "WorkerW":
                    EnumChildWindows(hwnd, cb_fn, 0)
                return not bool(defvw_container['hwnd'])
            user32.EnumWindows(EnumChildProc(cb_top), 0)

        defvw = defvw_container['hwnd']

        # 拿 ListView 屏幕坐标
        rect = ctypes.wintypes.RECT()
        if defvw:
            GetWindowRect(defvw, ctypes.byref(rect))
        else:
            # 完全没 ListView,用主屏
            user32.GetWindowRect(FindWindowW("Shell_TrayWnd", None), ctypes.byref(rect))
            rect.left = 0
            rect.top = 0
            rect.right = 1920
            rect.bottom = 1080

        # 网格估算 (Win10 默认: 75x95, 8 列) - 客户区坐标
        COLS = 8
        COL_W = 95
        ROW_H = 100
        col = logical_idx % COLS
        row = logical_idx // COLS
        pt_x = 20 + col * COL_W + 16  # 客户区坐标(图标中心)
        pt_y = 20 + row * ROW_H + 16
        self.log_signal.emit(f"   📍 网格估算 (idx={logical_idx}, col={col}, row={row})")

        if defvw:
            # 纯后台点击: 给 SysListView32 发送 WM_LBUTTONDBLCLK 消息
            WM_LBUTTONDOWN = 0x0201
            WM_LBUTTONUP = 0x0202
            WM_LBUTTONDBLCLK = 0x0203
            MK_LBUTTON = 0x0001
            lparam = (pt_y << 16) | (pt_x & 0xFFFF)

            self.log_signal.emit(f"   🖱️ C段后台双击 (SendMessage) hwnd={hex(defvw)}")
            SendMessage(defvw, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
            time.sleep(0.05)
            SendMessage(defvw, WM_LBUTTONUP, 0, lparam)
            time.sleep(0.05)
            SendMessage(defvw, WM_LBUTTONDBLCLK, MK_LBUTTON, lparam)
            time.sleep(0.05)
            SendMessage(defvw, WM_LBUTTONUP, 0, lparam)
            self.log_signal.emit(f"   ✅ 后台双击完成")
        else:
            # 退化: 鼠标移动点击
            pyautogui = _get_pyautogui()
            click_x = rect.left + pt_x
            click_y = rect.top + pt_y
            self.log_signal.emit(f"   🖱️ 鼠标双击坐标: ({click_x}, {click_y})")
            time.sleep(0.3)
            pyautogui.moveTo(click_x, click_y, duration=0.2)
            time.sleep(0.2)
            pyautogui.doubleClick()
            self.log_signal.emit(f"   ✅ 双击完成")

    # ---- 5.3 等窗口就绪 (三段式: psutil 找进程 > pywinauto 找窗口 > 退化等待) ----
    def _wait_window_ready(self, hint: str, timeout: float) -> None:
        self.log_signal.emit(f"⏳ 等待窗口就绪 (hint={hint})...")

        # 解析快捷方式目标路径 (如果是 .lnk)
        target_exe = hint.lower() + ".exe"
        if self.info.lnk_path and str(self.info.lnk_path).lower().endswith('.lnk'):
            try:
                import win32com.client
                shell = win32com.client.Dispatch('WScript.Shell')
                shortcut = shell.CreateShortCut(str(self.info.lnk_path))
                if shortcut.TargetPath:
                    target_exe = Path(shortcut.TargetPath).name.lower()
                    self.log_signal.emit(f"   📝 解析快捷方式目标: {target_exe}")
            except Exception as e:
                self.log_signal.emit(f"   ⚠️ 快捷方式解析失败: {e}")
        elif self.info.target:
            target_exe = Path(self.info.target).name.lower()

        self.log_signal.emit(f"   🔍 查找进程名: {target_exe}")

        # 1) 首选: 用 psutil 按可执行文件名找进程,且需要「持续存活」才算
        deadline = time.time() + timeout
        STABLE_SECONDS = 1.5  # 进程必须持续存在 1.5s 才算真就绪
        try:
            import psutil
            first_seen = None
            while time.time() < deadline:
                alive = [
                    (p.info["pid"], p.info["name"])
                    for p in psutil.process_iter(["pid", "name"])
                    if (p.info["name"] or "").lower() == target_exe
                ]
                if alive:
                    if first_seen is None:
                        first_seen = time.time()
                    elif time.time() - first_seen >= STABLE_SECONDS:
                        pid, name = alive[0]
                        self.log_signal.emit(
                            f"✅ 进程已运行 {STABLE_SECONDS}s+: {name} (PID={pid})"
                        )
                        return
                else:
                    # 中途消失了 -> 秒退
                    if first_seen is not None:
                        self.log_signal.emit(
                            f"❌ 进程 {target_exe} 启动后秒退!请手动双击该 exe 验证能否起起。"
                        )
                        return
                    first_seen = None
                time.sleep(0.3)
            # 超时
            if first_seen is not None:
                self.log_signal.emit(
                    f"⚠️ 进程 {target_exe} 存在但未达稳定阈值,可能仍在加载中..."
                )
            else:
                self.log_signal.emit(
                    f"❌ {timeout}s 内未发现进程 {target_exe} 运行。\n"
                    f"   可能原因: exe 自身崩溃 / 缺 DLL / 杀毒拦截 / 需管理员权限。\n"
                    f"   建议: 手动双击该快捷方式测试是否能起来。"
                )
        except Exception as e:
            self.log_signal.emit(f"⚠️ psutil 检查失败: {e}")

        # 2) 备选: pywinauto 找窗口 (app 实际启动但窗口可能被延后)
        self.log_signal.emit("🔎 未按进程名命中,退化用 pywinauto 找窗口标题...")
        try:
            from pywinauto import Application, timings
            timings.wait_until_passes(
                min(timeout, 5), 0.5,
                lambda: Application(backend="win32").connect(
                    title_re=f".*{hint}.*", timeout=0.5
                ),
            )
            self.log_signal.emit("✅ 窗口标题已就绪")
            return
        except Exception:
            pass

        # 3) 最后退化: 固定等一下,让用户感知"程序启动了"
        self.log_signal.emit("⚠️ 未命中进程/窗口,固定等待 2s")
        time.sleep(2)

    # ---- 5.4 记事本交互(中文走剪贴板) ----
    def _interact_notepad(self) -> None:
        pyautogui = _get_pyautogui()
        self.log_signal.emit("📝 开始键鼠交互(记事本)")
        time.sleep(1)
        import pyperclip
        pyperclip.copy(
            "这是通过 Python 自动模拟键鼠输入的测试文本!\n"
            "支持中文、换行、快捷键 Ctrl+S / Ctrl+V"
        )
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.5)
        pyautogui.hotkey("ctrl", "s")
        time.sleep(0.8)
        pyautogui.typewrite("auto_test.txt", interval=0.05)
        pyautogui.press("enter")
        self.log_signal.emit("✅ 交互完成")

    def _save_match_coord(self, info, cx: int, cy: int) -> None:
        """模板匹配坐标保存 (Step 2-2B: 改为回调注入, 不再直接调 desktop_auto helper)

        若构造时传入了 coord_saver, 调用它; 否则仅记录日志 (向后兼容)。
        """
        if self.coord_saver is None:
            self.log_signal.emit(f"   💾 匹配坐标 ({cx}, {cy}) 未保存 (无 coord_saver 回调)")
            return
        try:
            self.coord_saver(info, cx, cy)
            self.log_signal.emit(f"   💾 已保存匹配坐标: ({cx}, {cy})")
        except Exception as e:
            self.log_signal.emit(f"   ⚠️ 保存坐标失败: {e}")