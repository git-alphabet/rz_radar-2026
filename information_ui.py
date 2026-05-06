import time

import cv2
import numpy as np

index_table = {
    1: "R1",
    2: "R2",
    3: "R3",
    4: "R4",
    5: "R7",
    101: "B1",
    102: "B2",
    103: "B3",
    104: "B4",
    105: "B7"
}


# 绘制裁判系统数据的UI
def draw_information_ui(bar_list, camp, image, ally_bar_list=None):
    cv2.line(image, (300, 0), (300, 300), (0, 150, 0), 2)
    height_light = [0, 0, 0, 0, 0, 0]

    # 计算每条线段的长度
    num_lines = len(bar_list)
    max_value = 120
    threshold = 100  # 临界值
    max_length = 300  # 最大长度
    segment_height = int(300 / num_lines)

    # 绘制线段和索引
    for i, value in enumerate(bar_list):

        # 计算线段长度
        if value > threshold:
            line_length = int((value / max_value) * max_length)
            line_height = 8
            height_light[i] = 1
            if camp == 'R':
                color = (255, 0, 0)  # 超过临界值的线段高光处理为蓝色
            else:
                color = (0, 0, 255)
        else:
            line_height = 3
            if camp == 'R':
                color = (200, 0, 0)  # 超过临界值的线段高光处理为蓝色
            else:
                color = (0, 0, 200)
            line_length = int((value / max_value) * max_length)

        # 绘制线段
        start_point = (50, i * segment_height + segment_height // 2)
        end_point = (50 + line_length, i * segment_height + segment_height // 2)
        cv2.line(image, start_point, end_point, color, line_height, lineType=cv2.LINE_AA)

        # 绘制索引
        if camp == 'R':
            index = i + 101
        else:
            index = i + 1
        cv2.putText(image, str(index_table.get(index)), (10, start_point[1] + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(image, str(value), (370, start_point[1] + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2,
                    cv2.LINE_AA)

    # 绘制己方特殊标识 (如果有)
    if ally_bar_list is not None:
        for i, value in enumerate(ally_bar_list):
            if value > 0:
                start_point = (50, i * segment_height + segment_height // 2 + 15)
                cv2.putText(image, "ALLY", (370, start_point[1] + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1,
                            cv2.LINE_AA)

    return height_light


def draw_enemy_info(enemy_hp, enemy_bullet, enemy_boosts, enemy_password, image):
    """绘制敌方信息面板
    Args:
        enemy_hp: 敌方机器人血量 dict
        enemy_bullet: 敌方允许发弹量 dict
        enemy_boosts: 敌方各机器人增益 dict
        enemy_password: 敌方干扰波密钥 str
        image: 图像
    """
    y_offset = 30
    # 绘制标题
    cv2.putText(image, "Enemy Info", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    y_offset += 30

    # 绘制血量
    for robot_id in ('1', '2', '3', '4', '6', '7'):
        hp = enemy_hp.get(robot_id, 0)
        cv2.putText(image, f"HP{robot_id}: {hp}", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        y_offset += 20

    # 绘制发弹量
    y_offset += 10
    for robot_id in ('1', '2', '3', '4', '6', '7'):
        bullet = enemy_bullet.get(robot_id, 0)
        cv2.putText(image, f"Bullet{robot_id}: {bullet}", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        y_offset += 20

    # 绘制密钥
    y_offset += 10
    cv2.putText(image, f"Key: {enemy_password}", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)


# 测试代码
# ts = time.time()
# bar_list = [80, 100, 120, 90, 110, 1]  # 示例数据
# height_l = draw_lines(bar_list, 'B')
# te = time.time()
# print(height_l,te-ts)
# # 显示图像
# cv2.imshow('Lines', image)
# cv2.waitKey(0)
# cv2.destroyAllWindows()
