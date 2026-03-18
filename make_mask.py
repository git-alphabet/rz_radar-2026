# 绘制掩码地图
import cv2
import numpy as np

# 全局变量
drawing = False
current_points = []
mask_image = None
original_image = None
scaled_image = None
scale_factor = 1.0
color_mode = "green"  # 初始模式为绿色


def get_screen_size_fallback(default_w=1920, default_h=1080):
    """尽量获取屏幕分辨率，失败时使用默认值。"""
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        root.destroy()
        return screen_w, screen_h
    except Exception:
        return default_w, default_h

# 鼠标回调函数
def mouse_callback(event, x, y, flags, param):
    global drawing, current_points, mask_image, scaled_image, color_mode, scale_factor

    # 根据缩放比例调整坐标到原图尺度
    real_x, real_y = int(x / scale_factor), int(y / scale_factor)

    if event == cv2.EVENT_LBUTTONDOWN:  # 左键按下开始绘制
        drawing = True
        current_points = [(real_x, real_y)]  # 清空当前点列表，并添加第一个点
        print(f"Starting {color_mode} region at ({real_x}, {real_y})")

    elif event == cv2.EVENT_MOUSEMOVE and drawing:  # 移动时记录点
        current_points.append((real_x, real_y))
        # 更新绘制预览
        preview = scaled_image.copy()
        cv2.polylines(preview, [np.array(current_points)], False, (0, 255, 0) if color_mode == "green" else (255, 0, 0), 2)
        cv2.imshow("Image", preview)

    elif event == cv2.EVENT_LBUTTONUP:  # 左键释放结束绘制
        drawing = False
        current_points.append((real_x, real_y))  # 添加最后一个点

        # 绘制闭合区域到掩码图像
        color = (0, 255, 0) if color_mode == "green" else (255, 0, 0)
        cv2.fillPoly(mask_image, [np.array(current_points)], color)
        print(f"Finished {color_mode} region.")

        # 显示更新后的掩码图
        mask_preview = cv2.addWeighted(original_image, 0.5, mask_image, 0.5, 0)
        cv2.imshow("Image", mask_preview)

# 主函数
def create_irregular_mask(image_path):
    global mask_image, original_image, scaled_image, scale_factor, color_mode

    # 读取图像
    original_image = cv2.imread(image_path)
    if original_image is None:
        print("Failed to load image.")
        return

    # 根据屏幕分辨率自动缩放，避免窗口超出屏幕
    h, w = original_image.shape[:2]
    screen_w, screen_h = get_screen_size_fallback()
    max_preview_w = int(screen_w * 0.85)
    max_preview_h = int(screen_h * 0.85)
    scale_factor = min(max_preview_w / w, max_preview_h / h, 1.0)
    scaled_w, scaled_h = int(w * scale_factor), int(h * scale_factor)
    scaled_image = cv2.resize(original_image, (scaled_w, scaled_h))

    # 创建黑色掩码图像
    mask_image = np.zeros_like(original_image, dtype=np.uint8)

    # 创建窗口并绑定鼠标事件
    cv2.namedWindow("Image", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Image", scaled_w, scaled_h)
    cv2.setMouseCallback("Image", mouse_callback)

    print("Instructions:")
    print("1. Click and drag to define a region (release to finish).")
    print("2. Press 'n' to switch to the next region color (green -> blue).")
    print("3. Press 'q' to quit and save the mask.")
    print(f"Preview size: {scaled_w}x{scaled_h}, scale_factor={scale_factor:.3f}")

    while True:
        # 显示当前图像
        combined_preview = cv2.addWeighted(scaled_image, 0.5, cv2.resize(mask_image, scaled_image.shape[:2][::-1]), 0.5, 0)
        cv2.imshow("Image", combined_preview)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):  # 按 'q' 退出
            break
        elif key == ord('n'):  # 按 'n' 切换颜色模式
            color_mode = "blue" if color_mode == "green" else "green"
            print(f"Switched to {color_mode} mode.")

    cv2.destroyAllWindows()

    # 保存掩码图像
    cv2.imwrite("images-2025/map_mask.jpg", mask_image)
    print("Mask image saved as 'images-2025/map_mask.jpg'.")

# 使用示例
if __name__ == "__main__":
    # 替换为你的图像路径
    create_irregular_mask("map_custom_vertical.jpg")
