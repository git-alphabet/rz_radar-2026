#!/usr/bin/env python3
"""
雷达无线链路接收解析脚本。

输入为 GNU Radio UDP Sink 输出的连续恢复字节流：
GFSK Demod -> Repack Bits BB(MSB_FIRST) -> UDP Sink。
脚本按官方空口帧搜索 Access Code，剥离 4B Header，拼接 15B Payload，
再提取裁判系统串口帧并做 CRC8/CRC16 校验。
"""

from __future__ import annotations

import argparse
import socket
import time

from comm_protocol import (
    AirPayloadExtractor,
    DecodedFrame,
    INFO_ACCESS_CODE,
    INFO_CMD_ORDER,
    JAM_ACCESS_CODE,
    SerialFrameExtractor,
    parse_serial_frame,
)

UDP_IP = "127.0.0.1"
UDP_PORT = 55557

# 全局变量存储最新位置数据
radio_positions = {}
last_update_time = {}
# 全局变量存储敌方密钥
enemy_password = ''
enemy_password_time = 0
robot_mapping = {
    "hero": "R1",
    "engineer": "R2",
    "infantry3": "R3",
    "infantry4": "R4",
    "aerial": "R5",
    "sentry": "R7"
}
CN_NAMES = {
    "hero": "英雄",
    "engineer": "工程",
    "infantry3": "步兵3",
    "infantry4": "步兵4",
    "aerial": "空中",
    "sentry": "哨兵",
    "reserved": "保留",
}


def format_decoded(frame: DecodedFrame) -> str:
    cmd = frame.cmd_id
    data = frame.data
    lines = [f"cmd=0x{cmd:04X}, seq={frame.seq}"]

    if cmd == 0x0A01:
        for key in ("hero", "engineer", "infantry3", "infantry4", "aerial", "sentry"):
            value = data[key]
            lines.append(f"  {CN_NAMES[key]}位置: ({value['x_cm']}, {value['y_cm']}) cm")
    elif cmd == 0x0A02:
        for key in ("hero", "engineer", "infantry3", "infantry4", "reserved", "sentry"):
            lines.append(f"  {CN_NAMES[key]}血量: {data[key]}")
    elif cmd == 0x0A03:
        for key in ("hero", "infantry3", "infantry4", "aerial", "sentry"):
            lines.append(f"  {CN_NAMES[key]}允许发弹量: {data[key]}")
    elif cmd == 0x0A04:
        lines.append(f"  剩余金币: {data['remaining_gold']}")
        lines.append(f"  累计金币: {data['total_gold']}")
        lines.append(f"  宏观状态位: 0x{data['macro_state']:08X}")
    elif cmd == 0x0A05:
        for key in ("hero", "engineer", "infantry3", "infantry4", "sentry"):
            value = data[key]
            lines.append(
                f"  {CN_NAMES[key]}增益: 回血{value['hp_recover_percent']}%, "
                f"冷却{value['heat_cooling']}, 防御{value['defense_percent']}%, "
                f"负防御{value['negative_defense_percent']}%, 攻击{value['attack_percent']}%"
            )
        lines.append(f"  哨兵姿态: {data['sentry_posture']} (1进攻,2防御,3移动)")
    elif cmd == 0x0A06:
        lines.append(f"  干扰波密钥: {data['password']}")
    else:
        lines.append(f"  raw: {data['raw']}")

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse recovered RoboMaster radar radio bytes from UDP.")
    parser.add_argument("--host", default=UDP_IP)
    parser.add_argument("--port", type=int, default=UDP_PORT)
    parser.add_argument("--wave", choices=("info", "jam"), default="info")
    parser.add_argument("--quiet", action="store_true", help="only print cycle frequency")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    access_code = INFO_ACCESS_CODE if args.wave == "info" else JAM_ACCESS_CODE
    expected = set(INFO_CMD_ORDER) if args.wave == "info" else {0x0A06}

    air = AirPayloadExtractor(access_code)
    serial = SerialFrameExtractor()
    seen: set[int] = set()
    last_cycle_time: float | None = None

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
    sock.bind((args.host, args.port))

    print(f"监听 UDP {args.host}:{args.port}, wave={args.wave}, access={access_code.hex().upper()}")
    try:
        while True:
            chunk, _ = sock.recvfrom(4096)
            payloads = air.feed(chunk)
            for payload in payloads:
                frames = serial.feed(payload)
                for raw_frame in frames:
                    decoded = parse_serial_frame(raw_frame)
                    seen.add(decoded.cmd_id)
                    if not args.quiet:
                        print(format_decoded(decoded))

                    # 解析敌方位置数据并存储
                    if decoded.cmd_id == 0x0A01:
                        for key in ("hero", "engineer", "infantry3", "infantry4", "aerial", "sentry"):
                            value = decoded.data[key]
                            robot = robot_mapping[key]
                            radio_positions[robot] = (value['x_cm'], value['y_cm'])
                            last_update_time[robot] = time.time()

                    # 解析敌方密钥并存储
                    if decoded.cmd_id == 0x0A06:
                        enemy_password = decoded.data['password']
                        enemy_password_time = time.time()
                        print(f"获取敌方密钥: {enemy_password}")

                    if expected.issubset(seen):
                        now = time.monotonic()
                        if last_cycle_time is not None:
                            interval = now - last_cycle_time
                            freq = 1.0 / interval if interval > 0 else 0.0
                            print(f"完整周期: interval={interval * 1000:.1f} ms, freq={freq:.2f} Hz")
                        else:
                            print("第一个完整周期")
                        last_cycle_time = now
                        seen.clear()
    except KeyboardInterrupt:
        print("\n接收结束。")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
