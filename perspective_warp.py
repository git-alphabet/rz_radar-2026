"""
perspective_warp.py — 透视变换工具（考核地图制作）

使用方法：
  直接修改下方「配置参数」区域，然后运行：
    python perspective_warp.py

操作：
    鼠标左键 — 按顺序点 4 个角点（1→2 映射Y方向，2→3 映射X方向）
  R        — 重置重新点
    S        — 同时保存竖图和横图
  Q / ESC  — 退出
"""

import cv2
import numpy as np
import yaml



INPUT_IMAGE   = "images/1.jpg"        # 拍的图片路径
OUTPUT_IMAGE_VERTICAL   = "map_custom_vertical.jpg"    # 输出竖图（长边竖向）
OUTPUT_IMAGE_HORIZONTAL = "map_custom_horizontal.jpg"  # 输出横图（长边横向）

CONFIG_YAML = "config.yaml"  # 读取原项目地图像素基准（global.map_size）
DEFAULT_PROJECT_MAP_SIZE = (2800, 1500)  # 兜底像素基准（与原项目一致）

# 原项目地图对应的真实尺寸（cm）
PROJECT_FIELD_WIDTH_CM = 2800.0
PROJECT_FIELD_HEIGHT_CM = 1500.0

# 当前要裁切区域的实测尺寸（cm）
MEASURED_GROUND_WIDTH_CM = 420.0
MEASURED_GROUND_HEIGHT_CM = 166.0

# 在“按项目基准换算”的基础上整体放大，提升清晰度（保持比例不变）
OUTPUT_UPSCALE = 10.0

# 输出镜像模式：none / horizontal / vertical / both
MIRROR_MODE = "horizontal"

# 是否对横图额外旋转 180°（用于单独修正 warp_horizontal 方向）
HORIZONTAL_EXTRA_ROTATE_180 = True

MIN_OUTPUT_SIDE_PX = 2


def sort_quad(pts):
    """将任意顺序 4 点排列为 [TL, TR, BR, BL]。"""
    pts = np.array(pts, dtype=np.float32)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).flatten()
    return np.array([
        pts[np.argmin(s)],   # TL: x+y 最小
        pts[np.argmin(d)],   # TR: x-y 最小
        pts[np.argmax(s)],   # BR: x+y 最大
        pts[np.argmax(d)],   # BL: x-y 最大
    ], dtype=np.float32)


def load_project_map_size():
    """优先从 config.yaml 读取 map_size，失败时回退默认值。"""
    try:
        with open(CONFIG_YAML, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        map_size = cfg.get("global", {}).get("map_size", None)
        if isinstance(map_size, (list, tuple)) and len(map_size) == 2:
            w, h = int(map_size[0]), int(map_size[1])
            if w > 0 and h > 0:
                return w, h
    except Exception:
        pass
    return DEFAULT_PROJECT_MAP_SIZE


def resolve_output_size():
    """按“实测cm + 项目地图像素基准”换算输出像素尺寸。"""
    map_w_px, map_h_px = load_project_map_size()
    sx = map_w_px / PROJECT_FIELD_WIDTH_CM
    sy = map_h_px / PROJECT_FIELD_HEIGHT_CM

    base_w = MEASURED_GROUND_WIDTH_CM * sx
    base_h = MEASURED_GROUND_HEIGHT_CM * sy

    out_w = max(int(round(base_w * OUTPUT_UPSCALE)), MIN_OUTPUT_SIDE_PX)
    out_h = max(int(round(base_h * OUTPUT_UPSCALE)), MIN_OUTPUT_SIDE_PX)
    return out_w, out_h, sx, sy, map_w_px, map_h_px


def warp_image(img, quad_orig, out_w, out_h):
    """透视变换：quad_orig 四点 → out_w × out_h 矩形。"""
    W, H = int(out_w), int(out_h)
    dst = np.array([
        [0,     0    ],
        [0,     H - 1],
        [W - 1, H - 1],
        [W - 1, 0    ],
    ], dtype=np.float32)
    M = cv2.getPerspectiveTransform(quad_orig, dst)
    return cv2.warpPerspective(img, M, (W, H))


def make_portrait_from_landscape(img_landscape):
    """由横图生成竖图（逆时针旋转 90°）。"""
    return cv2.rotate(img_landscape, cv2.ROTATE_90_COUNTERCLOCKWISE)


def rotate_180(img):
    """图像旋转 180°。"""
    return cv2.rotate(img, cv2.ROTATE_180)


def mirror_image(img, mode="horizontal"):
    """按模式镜像图像。"""
    if mode == "none":
        return img
    if mode == "horizontal":
        return cv2.flip(img, 1)
    if mode == "vertical":
        return cv2.flip(img, 0)
    if mode == "both":
        return cv2.flip(img, -1)
    return img


def draw_overlay(canvas, points, scale, output_width_px, output_height_px, hover=None):
    """在显示画布上绘制点、连线、标签、提示文字。"""
    colors = [(0, 255, 0), (0, 200, 255), (255, 100, 0), (180, 0, 255)]
    labels = ['1', '2', '3', '4']
    n = len(points)

    # 预览线（未满4点）
    if hover and 0 < n < 4:
        cv2.line(canvas, points[-1], hover, (180, 180, 180), 1, cv2.LINE_AA)

    if n == 4:
        quad = np.array(points, dtype=np.int32)
        cv2.polylines(canvas, [quad], True, (0, 255, 255), 2, cv2.LINE_AA)
        for i, p in enumerate(points):
            cv2.circle(canvas, p, 7, colors[i], -1, cv2.LINE_AA)
            cv2.putText(canvas, labels[i], (p[0] + 8, p[1] - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, colors[i], 2)
    else:
        for i, pt in enumerate(points):
            cv2.circle(canvas, pt, 7, colors[i], -1, cv2.LINE_AA)
            cv2.putText(canvas, str(i + 1), (pt[0] + 8, pt[1] - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, colors[i], 2)
        if n > 1:
            cv2.polylines(canvas, [np.array(points, dtype=np.int32)], False,
                          (180, 180, 180), 1, cv2.LINE_AA)

    # 状态栏
    hint = (
        f"已选 {n}/4 点 | 1-2=Y 2-3=X | 横图 {output_width_px}x{output_height_px}"
        f" + 竖图 {output_height_px}x{output_width_px}"
    )
    cv2.rectangle(canvas, (0, 0), (canvas.shape[1], 30), (0, 0, 0), -1)
    cv2.putText(canvas, hint, (8, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)


def main():
    output_width_px, output_height_px, px_per_cm_x, px_per_cm_y, map_w_px, map_h_px = resolve_output_size()
    print(
        f"[尺寸] 地图基准={map_w_px}x{map_h_px}px, "
        f"比例=({px_per_cm_x:.4f}, {px_per_cm_y:.4f}) px/cm, "
        f"放大系数={OUTPUT_UPSCALE:.2f}, 输出={output_width_px}x{output_height_px}px "
        f"(来自 {MEASURED_GROUND_WIDTH_CM}x{MEASURED_GROUND_HEIGHT_CM} cm)"
    )

    img_orig = cv2.imread(INPUT_IMAGE)
    if img_orig is None:
        print(f"[错误] 无法读取图片: {INPUT_IMAGE}")
        print("请修改脚本顶部的 INPUT_IMAGE 路径后重新运行。")
        return

    H0, W0 = img_orig.shape[:2]
    # 缩放到显示窗口（最长边不超过 1400px）
    scale = min(1400 / W0, 1000 / H0, 1.0)
    disp_w, disp_h = int(W0 * scale), int(H0 * scale)
    img_disp_base = cv2.resize(img_orig, (disp_w, disp_h)) if scale < 1.0 else img_orig.copy()

    points_disp = []   # 显示坐标下的点击点
    warped_horizontal = None
    warped_vertical = None
    hover_pt = None

    WIN_SRC = "perspective_src"
    WIN_WARP_H = "warp_horizontal"
    WIN_WARP_V = "warp_vertical"

    try:
        cv2.namedWindow(WIN_SRC, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WIN_SRC, disp_w, disp_h)
    except cv2.error as e:
        print(f"[错误] 创建窗口失败: {e}")
        print("请检查 DISPLAY、X11 转发与 OpenCV 高GUI环境。")
        return

    def apply_warp():
        nonlocal warped_horizontal, warped_vertical
        quad_orig = np.array(points_disp, dtype=np.float32) / scale  # 映射回原图坐标（按点击顺序）
        warped_horizontal_raw = warp_image(img_orig, quad_orig, output_width_px, output_height_px)
        warped_vertical_raw = make_portrait_from_landscape(warped_horizontal_raw)

        # 两个输出都在原有基础上旋转 180°（预览与保存一致）
        warped_horizontal = mirror_image(rotate_180(warped_horizontal_raw), MIRROR_MODE)
        warped_vertical = mirror_image(rotate_180(warped_vertical_raw), MIRROR_MODE)

        if HORIZONTAL_EXTRA_ROTATE_180:
            warped_horizontal = rotate_180(warped_horizontal)

        # 横图预览
        ws_h = min(1200 / output_width_px, 700 / output_height_px, 1.0)
        preview_h = cv2.resize(
            warped_horizontal,
            (int(output_width_px * ws_h), int(output_height_px * ws_h))
        )
        cv2.namedWindow(WIN_WARP_H, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WIN_WARP_H, preview_h.shape[1], preview_h.shape[0])
        cv2.imshow(WIN_WARP_H, preview_h)

        # 竖图预览
        H_v, W_v = warped_vertical.shape[:2]
        ws_v = min(700 / W_v, 900 / H_v, 1.0)
        preview_v = cv2.resize(warped_vertical, (int(W_v * ws_v), int(H_v * ws_v)))
        cv2.namedWindow(WIN_WARP_V, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WIN_WARP_V, preview_v.shape[1], preview_v.shape[0])
        cv2.imshow(WIN_WARP_V, preview_v)

    def save():
        if warped_horizontal is None or warped_vertical is None:
            print("[提示] 还没有生成结果，请先选点。")
            return
        cv2.imwrite(OUTPUT_IMAGE_HORIZONTAL, warped_horizontal)
        cv2.imwrite(OUTPUT_IMAGE_VERTICAL, warped_vertical)
        print(f"[保存-横图] {OUTPUT_IMAGE_HORIZONTAL}  ({output_width_px}x{output_height_px})")
        print(f"[保存-竖图] {OUTPUT_IMAGE_VERTICAL}  ({output_height_px}x{output_width_px})")

    def on_mouse(event, x, y, flags, _):
        nonlocal hover_pt
        hover_pt = (x, y)
        if event == cv2.EVENT_LBUTTONDOWN and len(points_disp) < 4:
            points_disp.append((x, y))
            if len(points_disp) == 4:
                apply_warp()

    canvas_init = img_disp_base.copy()
    draw_overlay(canvas_init, points_disp, scale, output_width_px, output_height_px, hover_pt)
    cv2.imshow(WIN_SRC, canvas_init)
    cv2.waitKey(1)

    try:
        cv2.setMouseCallback(WIN_SRC, on_mouse)
    except cv2.error as e:
        print(f"[错误] 绑定鼠标回调失败: {e}")
        print("窗口句柄无效，请确认图形窗口可正常弹出。")
        cv2.destroyAllWindows()
        return

    while True:
        canvas = img_disp_base.copy()
        draw_overlay(canvas, points_disp, scale, output_width_px, output_height_px, hover_pt)
        cv2.imshow(WIN_SRC, canvas)

        key = cv2.waitKey(16) & 0xFF
        if key in (ord('q'), 27):
            break
        elif key == ord('r'):
            points_disp.clear()
            warped_horizontal = None
            warped_vertical = None
            if cv2.getWindowProperty(WIN_WARP_H, cv2.WND_PROP_VISIBLE) >= 1:
                cv2.destroyWindow(WIN_WARP_H)
            if cv2.getWindowProperty(WIN_WARP_V, cv2.WND_PROP_VISIBLE) >= 1:
                cv2.destroyWindow(WIN_WARP_V)
        elif key == ord('s'):
            save()

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
