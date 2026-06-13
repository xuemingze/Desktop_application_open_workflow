"""
纯 PIL 模板匹配 - 不依赖 OpenCV
- 截图后用 PIL.Image 加载
- 用 numpy 做像素级匹配
- 不受 OpenCV DLL 缺失影响
"""
import numpy as np
from PIL import Image
from typing import Optional, Tuple


def locate_on_screen(template_path: str, confidence: float = 0.7, screenshot: Optional[Image.Image] = None) -> Optional[Tuple[int, int, int, int]]:
    """
    在屏幕上找模板位置
    返回 (x, y, w, h) 或 None
    """
    import pyautogui

    # 1. 加载模板
    template = Image.open(template_path).convert("RGB")
    t_w, t_h = template.size

    # 2. 截图(全屏)
    if screenshot is None:
        screenshot = pyautogui.screenshot()
    s_w, s_h = screenshot.size

    # 3. 转 numpy 数组
    t_arr = np.array(template, dtype=np.float32)
    s_arr = np.array(screenshot, dtype=np.float32)

    # 4. 简单滑窗匹配 (用 SSD 反向 = 越接近 1 越像)
    if t_w > s_w or t_h > s_h:
        return None

    # 简单方法: 逐位置计算归一化互相关
    best_score = -1
    best_pos = (0, 0)

    # 步长优化: 实际生产用 numpy 的 stride_tricks,但为了简单用 for
    # 用 1/4 子采样加速
    step = 2
    t_norm = t_arr - t_arr.mean()
    t_std = t_norm.std() + 1e-6

    for y in range(0, s_h - t_h + 1, step):
        for x in range(0, s_w - t_w + 1, step):
            window = s_arr[y:y+t_h, x:x+t_w]
            w_mean = window.mean()
            w_norm = window - w_mean
            w_std = w_norm.std() + 1e-6
            # NCC
            ncc = (t_norm * w_norm).mean() / (t_std * w_std)
            if ncc > best_score:
                best_score = ncc
                best_pos = (x, y)

    # 5. 在 best_pos 附近做精细搜索
    bx, by = best_pos
    for y in range(max(0, by-step), min(s_h - t_h, by+step) + 1):
        for x in range(max(0, bx-step), min(s_w - t_w, bx+step) + 1):
            window = s_arr[y:y+t_h, x:x+t_w]
            w_mean = window.mean()
            w_norm = window - w_mean
            w_std = w_norm.std() + 1e-6
            ncc = (t_norm * w_norm).mean() / (t_std * w_std)
            if ncc > best_score:
                best_score = ncc
                best_pos = (x, y)

    if best_score >= confidence:
        x, y = best_pos
        return (x, y, t_w, t_h)
    return None


def get_center(box):
    """(x, y, w, h) -> (cx, cy)"""
    x, y, w, h = box
    return (x + w // 2, y + h // 2)


# 兼容 pyautogui.locateOnScreen 接口
class Locator:
    def __init__(self, box):
        self._box = box

    def __bool__(self):
        return self._box is not None


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python image_match.py <template.png>")
        sys.exit(1)
    template = sys.argv[1]
    print(f"查找模板: {template}")
    box = locate_on_screen(template, confidence=0.7)
    if box:
        print(f"找到: {box}, 中心: {get_center(box)}")
    else:
        print("未找到")
