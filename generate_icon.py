"""
生成桌面自动化助手的应用图标
- 256x256 PNG
- 几何规律感设计
- 深蓝渐变 + 白色几何形状
"""
from PIL import Image, ImageDraw
import math

SIZE = 256
img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# ============================================================
# 1. 圆角矩形背景 (深蓝渐变)
# ============================================================
radius = 48
# 模拟渐变: 画多个矩形
for y in range(SIZE):
    t = y / SIZE
    r = int(30 + (37 - 30) * t)    # 1E -> 25 (深蓝)
    g = int(64 + (99 - 64) * t)    # 40 -> 63
    b = int(175 + (235 - 175) * t) # AF -> EB
    draw.line([(0, y), (SIZE, y)], fill=(r, g, b, 255))

# 圆角遮罩
mask = Image.new("L", (SIZE, SIZE), 0)
m_draw = ImageDraw.Draw(mask)
m_draw.rounded_rectangle((0, 0, SIZE, SIZE), radius=radius, fill=255)
img.putalpha(mask)

draw = ImageDraw.Draw(img)

# ============================================================
# 2. 几何网格 - 4 个工作流步骤方块
# ============================================================
# 4x2 网格,代表工作流步骤序列
cell_size = 38
gap = 12
grid_w = 4 * cell_size + 3 * gap
grid_h = 2 * cell_size + 1 * gap
start_x = (SIZE - grid_w) // 2
start_y = (SIZE - grid_h) // 2 + 18  # 稍微下移

# 激活步骤颜色 (高亮)
active_color = (6, 182, 212, 255)   # cyan
pending_color = (255, 255, 255, 90) # 白色半透明
done_color = (52, 211, 153, 255)    # green

# 画 8 个方块 (4 列 2 行),前 3 个 done, 第 4 个 active, 后 4 个 pending
positions = []
for row in range(2):
    for col in range(4):
        x = start_x + col * (cell_size + gap)
        y = start_y + row * (cell_size + gap)
        idx = row * 4 + col
        if idx < 3:
            color = done_color
        elif idx == 3:
            color = active_color
        else:
            color = pending_color
        # 圆角方块
        draw.rounded_rectangle(
            (x, y, x + cell_size, y + cell_size),
            radius=6, fill=color
        )
        positions.append((x + cell_size // 2, y + cell_size // 2))

# ============================================================
# 3. 顶部: 几何"火箭"形状 (代表自动化加速)
# ============================================================
rocket_cx = SIZE // 2
rocket_cy = 50

# 火箭由三角形组成
# 主体: 上指三角形
rocket_h = 30
rocket_w = 22
draw.polygon([
    (rocket_cx, rocket_cy - rocket_h // 2),
    (rocket_cx - rocket_w // 2, rocket_cy + rocket_h // 2),
    (rocket_cx + rocket_w // 2, rocket_cy + rocket_h // 2),
], fill=(255, 255, 255, 230))

# 火箭底部: 两条侧翼小三角
draw.polygon([
    (rocket_cx - rocket_w // 2, rocket_cy + rocket_h // 2 - 2),
    (rocket_cx - rocket_w // 2 - 6, rocket_cy + rocket_h // 2 + 6),
    (rocket_cx - rocket_w // 2, rocket_cy + rocket_h // 2 + 4),
], fill=(255, 255, 255, 180))
draw.polygon([
    (rocket_cx + rocket_w // 2, rocket_cy + rocket_h // 2 - 2),
    (rocket_cx + rocket_w // 2 + 6, rocket_cy + rocket_h // 2 + 6),
    (rocket_cx + rocket_w // 2, rocket_cy + rocket_h // 2 + 4),
], fill=(255, 255, 255, 180))

# 火箭中心圆点
draw.ellipse([
    rocket_cx - 4, rocket_cy - 2,
    rocket_cx + 4, rocket_cy + 6,
], fill=(6, 182, 212, 255))

# ============================================================
# 4. 底部: 几何"基座" 标志 (代表桌面)
# ============================================================
base_y = SIZE - 50
base_x = SIZE // 2

# 两条平行线 + 三个圆点
draw.line([
    (base_x - 50, base_y - 5),
    (base_x + 50, base_y - 5)
], fill=(255, 255, 255, 200), width=2)
for i, x_offset in enumerate([-30, 0, 30]):
    r = 5
    draw.ellipse([
        base_x + x_offset - r, base_y - r,
        base_x + x_offset + r, base_y + r,
    ], fill=(255, 255, 255, 220 - i * 30))

# ============================================================
# 保存
# ============================================================
# 256x256 PNG
img.save("app_icon_256.png", "PNG")
print(f"生成: app_icon_256.png ({SIZE}x{SIZE})")

# 缩放成多个尺寸
sizes = [16, 32, 48, 64, 128, 256]
imgs = [img.resize((s, s), Image.LANCZOS) for s in sizes]

# 保存多尺寸 ICO
imgs[0].save(
    "app_icon.ico",
    format="ICO",
    sizes=[(s, s) for s in sizes],
    append_images=imgs[1:]
)
print(f"生成: app_icon.ico (多尺寸)")

# 单独 512x512 版本(给 README 用)
img_512 = img.resize((512, 512), Image.LANCZOS)
img_512.save("app_icon_512.png", "PNG")
print(f"生成: app_icon_512.png (512x512)")

print("\n图标设计:")
print("  • 圆角方形 + 深蓝渐变背景")
print("  • 顶部: 几何火箭(代表自动化)")
print("  • 中部: 4x2 工作流方块(已激活cyan / 完成green / 待办白)")
print("  • 底部: 桌面基座(三条线 + 圆点)")
