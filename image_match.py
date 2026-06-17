"""
纯 PIL 模板匹配 - 不依赖 OpenCV
- 截图后用 PIL.Image 加载
- 用 numpy 向量化 NCC 计算
- 不受 OpenCV DLL 缺失影响
"""
import numpy as np
from PIL import Image
from typing import Optional, Tuple


def _compute_ncc_map(screen: np.ndarray, template: np.ndarray, step: int = 4) -> Tuple[np.ndarray, np.ndarray]:
    """向量化 NCC 计算 - 一次算出所有位置的 NCC 分数

    Args:
        screen: 屏幕截图数组 (H, W, C) float32 或 (H, W) float32
        template: 模板数组 (h, w, C) float32 或 (h, w) float32
        step: 步长 (粗搜索用,精细搜索用 1)

    Returns:
        (ncc_map, positions): NCC 分数矩阵 (Y, X) 和对应的位置数组
    """
    # 转灰度简化计算 (单通道足够匹配)
    if screen.ndim == 3:
        screen = screen.mean(axis=2)
    if template.ndim == 3:
        template = template.mean(axis=2)

    s_h, s_w = screen.shape
    t_h, t_w = template.shape

    if t_h > s_h or t_w > s_w:
        return np.array([[]]), np.array([])

    # 模板预计算
    t_mean = template.mean()
    t_norm = (template - t_mean).ravel()
    t_std = np.sqrt((t_norm ** 2).sum()) + 1e-6

    # 用 stride_tricks 创建滑动窗口视图
    # screen shape: (H, W) -> sliding_window_view((), (t_h, t_w))
    # -> shape: (H-t_h+1, W-t_w+1, t_h, t_w)
    windows = np.lib.stride_tricks.sliding_window_view(screen, (t_h, t_w))

    # 提取所有候选位置 (带步长)
    if step > 1:
        windows = windows[::step, ::step]  # 子采样

    n_y, n_x = windows.shape[:2]

    # 向量化计算
    flat = windows.reshape(n_y, n_x, -1).astype(np.float32)  # (n_y, n_x, t_h*t_w)
    w_mean = flat.mean(axis=2, keepdims=True)                 # (n_y, n_x, 1)
    w_norm = flat - w_mean
    w_std = np.sqrt((w_norm ** 2).sum(axis=2, keepdims=True)) + 1e-6  # (n_y, n_x, 1)

    # NCC = sum(t_norm * w_norm) / (t_std * w_std)
    dot = (w_norm * t_norm).sum(axis=2)                       # (n_y, n_x)
    ncc = dot / (t_std * w_std.squeeze(axis=2))

    return ncc, np.array([[y * step, x * step] for y in range(n_y) for x in range(n_x)])


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

    # 4. 模板大于屏幕,直接返回
    if t_w > s_w or t_h > s_h:
        return None

    # 5. 粗搜索 - 步长 4 (速度优先)
    ncc_map, positions = _compute_ncc_map(s_arr, t_arr, step=4)
    if ncc_map.size == 0:
        return None

    # 找最佳位置
    best_idx = np.argmax(ncc_map)
    best_y, best_x = positions[best_idx]
    best_score = ncc_map.flat[best_idx]

    # 6. 精细搜索 - 在 best_pos 周围 step=1 搜索
    margin = 8
    y_start = max(0, best_y - margin)
    y_end = min(s_h - t_h, best_y + margin)
    x_start = max(0, best_x - margin)
    x_end = min(s_w - t_w, best_x + margin)

    if y_end > y_start and x_end > x_start:
        crop = s_arr[y_start:y_end + t_h, x_start:x_end + t_w]
        ncc_fine, fine_pos = _compute_ncc_map(crop, t_arr, step=1)
        if ncc_fine.size > 0:
            fine_idx = np.argmax(ncc_fine)
            fine_score = ncc_fine.flat[fine_idx]
            if fine_score > best_score:
                best_score = fine_score
                best_y = y_start + fine_pos[fine_idx][0]
                best_x = x_start + fine_pos[fine_idx][1]

    if best_score >= confidence:
        return (int(best_x), int(best_y), t_w, t_h)
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
