"""
图标 v2: 更现代、更规律、更几何
- 256x256 圆角方形
- 中心: 同心圆/六边形代表 "automation core"
- 外围: 8 个等距方块代表 "workflow steps"
- 顶部: 几何箭头
"""
from PIL import Image, ImageDraw
import math

SIZE = 512
img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# 圆角背景
radius = 96

# 渐变背景 (从上到下: 深蓝 -> 紫色)
for y in range(SIZE):
    t = y / SIZE
    # 深蓝 #1E3A8A -> 紫色 #6D28D9
    r = int(30 + (109 - 30) * t)
    g = int(58 + (40 - 58) * t)
    b = int(138 + (217 - 138) * t)
    draw.line([(0, y), (SIZE, y)], fill=(r, g, b, 255))

# 圆角遮罩
mask = Image.new("L", (SIZE, SIZE), 0)
m = ImageDraw.Draw(mask)
m.rounded_rectangle((0, 0, SIZE, SIZE), radius=radius, fill=255)
img.putalpha(mask)
draw = ImageDraw.Draw(img)

# ============================================================
# 1. 外圈: 8 个等距圆角方块(规律几何)
# ============================================================
center_x = SIZE // 2
center_y = SIZE // 2 + 10
orbit_r = 170  # 圆环半径
box_size = 56

# 8 个方块等距环绕
n_boxes = 8
for i in range(n_boxes):
    angle = math.radians(i * 45 - 90)  # 起始在顶部
    bx = center_x + orbit_r * math.cos(angle)
    by = center_y + orbit_r * math.sin(angle)
    # 高亮第一个(代表正在执行)
    if i == 0:
        color = (6, 182, 212, 255)  # cyan
    elif i in (1, 2, 3):
        color = (52, 211, 153, 255)  # green (已完成)
    else:
        color = (255, 255, 255, 80)  # 半透明白(待办)
    draw.rounded_rectangle(
        (bx - box_size//2, by - box_size//2,
         bx + box_size//2, by + box_size//2),
        radius=10, fill=color
    )
    # 方块之间画细连接线(规律感)
    if i < n_boxes - 1:
        next_angle = math.radians((i+1) * 45 - 90)
        nx = center_x + orbit_r * math.cos(next_angle)
        ny = center_y + orbit_r * math.sin(next_angle)
        # 用圆弧连接 (8 段短弧)
        # 简化:用直线
        draw.line([(bx, by), (nx, ny)], fill=(255, 255, 255, 40), width=2)

# ============================================================
# 2. 中心: 同心六边形(automation core)
# ============================================================
core_size = 80

# 大六边形
hex_points = []
for i in range(6):
    angle = math.radians(i * 60 - 30)
    hex_points.append((
        center_x + core_size * math.cos(angle),
        center_y + core_size * math.sin(angle)
    ))
draw.polygon(hex_points, fill=(255, 255, 255, 230))

# 中六边形(深色)
core_size2 = 60
hex_points2 = []
for i in range(6):
    angle = math.radians(i * 60 - 30)
    hex_points2.append((
        center_x + core_size2 * math.cos(angle),
        center_y + core_size2 * math.sin(angle)
    ))
draw.polygon(hex_points2, fill=(99, 102, 241, 255))  # indigo

# 中心小六边形
core_size3 = 30
hex_points3 = []
for i in range(6):
    angle = math.radians(i * 60 - 30)
    hex_points3.append((
        center_x + core_size3 * math.cos(angle),
        center_y + core_size3 * math.sin(angle)
    ))
draw.polygon(hex_points3, fill=(6, 182, 212, 255))  # cyan

# ============================================================
# 3. 中心符号: 三个小方块(代表步骤)
# ============================================================
# 在中心六边形内画三个白色小方块
sq = 14
gap = 6
total_w = 3 * sq + 2 * gap
start_x_sq = center_x - total_w // 2
start_y_sq = center_y - sq // 2
for j in range(3):
    sx = start_x_sq + j * (sq + gap)
    color = (255, 255, 255, 255) if j == 0 else (255, 255, 255, 200)
    draw.rounded_rectangle(
        (sx, start_y_sq, sx + sq, start_y_sq + sq),
        radius=2, fill=color
    )

# ============================================================
# 4. 顶部装饰: 三个渐变小点 (代表发射/启动)
# ============================================================
dot_y = 50
for i, (x_pos, r_size) in enumerate([(SIZE//2 - 30, 6), (SIZE//2, 9), (SIZE//2 + 30, 6)]):
    color_alpha = 200 - i * 50
    draw.ellipse(
        [x_pos - r_size, dot_y - r_size, x_pos + r_size, dot_y + r_size],
        fill=(255, 255, 255, color_alpha)
    )

# ============================================================
# 保存
# ============================================================
img.save("app_icon_512_v2.png", "PNG")
img_256 = img.resize((256, 256), Image.LANCZOS)
img_256.save("app_icon_256_v2.png", "PNG")

# 多尺寸 ICO
sizes = [16, 32, 48, 64, 128, 256]
imgs = [img.resize((s, s), Image.LANCZOS) for s in sizes]
imgs[0].save(
    "app_icon.ico",
    format="ICO",
    sizes=[(s, s) for s in sizes],
    append_images=imgs[1:]
)
print("生成: app_icon.ico + app_icon_512_v2.png")
print("设计:")
print("  - 圆角方形渐变背景 (深蓝 -> 紫色)")
print("  - 8 个等距圆角方块 (规律排列,代表 8 个工作流步骤)")
print("  - 中心: 三层同心六边形 (代表 automation core)")
print("  - 中心符号: 三个白色小方块 (代表步骤)")
print("  - 顶部: 三个递减小点 (代表发射/启动)")
