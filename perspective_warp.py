"""
perspective_warp.py — 透视变换工具（考核地图制作）

使用方法：
  直接修改下方「配置参数」区域，然后运行：
    python perspective_warp.py

操作：
  鼠标左键 — 依次点 4 个角点（任意顺序，自动排列为 左上/右上/右下/左下）
  R        — 重置重新点
  S        — 保存结果到 OUTPUT_IMAGE
  Q / ESC  — 退出
"""

import cv2
import numpy as np

# ══════════════════════════════════════════════════════════════
#  配置参数（直接在这里改，不用命令行传参）
# ══════════════════════════════════════════════════════════════

INPUT_IMAGE   = "test.jpg"        # 你拍的图片路径
OUTPUT_IMAGE  = "map_custom.jpg"  # 输出保存路径

OUTPUT_WIDTH  = 2800              # 输出图宽度（px）横向
OUTPUT_HEIGHT = 1500              # 输出图高度（px）纵向
# 输出比例与 RM 标准地图一致: 2800×1500，显示时 900×480

# ══════════════════════════════════════════════════════════════


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


def warp_image(img, quad_orig):
    """透视变换：quad_orig 四点 → OUTPUT_WIDTH × OUTPUT_HEIGHT 矩形。"""
    W, H = OUTPUT_WIDTH, OUTPUT_HEIGHT
    dst = np.array([
        [0,     0    ],
        [W - 1, 0    ],
        [W - 1, H - 1],
        [0,     H - 1],
    ], dtype=np.float32)
    M = cv2.getPerspectiveTransform(quad_orig, dst)
    return cv2.warpPerspective(img, M, (W, H))


def draw_overlay(canvas, points, scale, hover=None):
    """在显示画布上绘制点、连线、标签、提示文字。"""
    colors = [(0, 255, 0), (0, 200, 255), (255, 100, 0), (180, 0, 255)]
    labels = ['TL', 'TR', 'BR', 'BL']
    n = len(points)

    # 预览线（未满4点）
    if hover and 0 < n < 4:
        cv2.line(canvas, points[-1], hover, (180, 180, 180), 1, cv2.LINE_AA)

    if n == 4:
        quad = sort_quad(points)
        cv2.polylines(canvas, [quad.astype(np.int32)], True, (0, 255, 255), 2, cv2.LINE_AA)
        for i, pt in enumerate(quad):
            p = tuple(pt.astype(int))
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
    hint = f"已选 {n}/4 点  |  输出尺寸 {OUTPUT_WIDTH}x{OUTPUT_HEIGHT}  |  R=重置  S=保存  Q=退出"
    cv2.rectangle(canvas, (0, 0), (canvas.shape[1], 30), (0, 0, 0), -1)
    cv2.putText(canvas, hint, (8, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)


def main():
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
    warped = None
    hover_pt = None

    WIN_SRC  = f"透视变换 — 点击4个角点  [{INPUT_IMAGE}]"
    WIN_WARP = f"俯视结果  {OUTPUT_WIDTH}x{OUTPUT_HEIGHT}  (S保存 Q退出)"

    cv2.namedWindow(WIN_SRC, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WIN_SRC, disp_w, disp_h)

    def apply_warp():
        nonlocal warped
        quad_disp = sort_quad(points_disp)
        quad_orig = quad_disp / scale      # 映射回原图坐标
        warped = warp_image(img_orig, quad_orig)

        # 结果窗口以不超过 1200px 宽显示
        ws = min(1200 / OUTPUT_WIDTH, 700 / OUTPUT_HEIGHT, 1.0)
        preview = cv2.resize(warped, (int(OUTPUT_WIDTH * ws), int(OUTPUT_HEIGHT * ws)))
        cv2.namedWindow(WIN_WARP, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WIN_WARP, preview.shape[1], preview.shape[0])
        cv2.imshow(WIN_WARP, preview)

    def save():
        if warped is None:
            print("[提示] 还没有生成结果，请先选点。")
            return
        cv2.imwrite(OUTPUT_IMAGE, warped)
        print(f"[保存] {OUTPUT_IMAGE}  ({OUTPUT_WIDTH}x{OUTPUT_HEIGHT})")

    def on_mouse(event, x, y, flags, _):
        nonlocal hover_pt
        hover_pt = (x, y)
        if event == cv2.EVENT_LBUTTONDOWN and len(points_disp) < 4:
            points_disp.append((x, y))
            if len(points_disp) == 4:
                apply_warp()

    cv2.setMouseCallback(WIN_SRC, on_mouse)

    while True:
        canvas = img_disp_base.copy()
        draw_overlay(canvas, points_disp, scale, hover_pt)
        cv2.imshow(WIN_SRC, canvas)

        key = cv2.waitKey(16) & 0xFF
        if key in (ord('q'), 27):
            break
        elif key == ord('r'):
            points_disp.clear()
            warped = None
            if cv2.getWindowProperty(WIN_WARP, cv2.WND_PROP_VISIBLE) >= 1:
                cv2.destroyWindow(WIN_WARP)
        elif key == ord('s'):
            save()

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
