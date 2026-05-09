#!/usr/bin/env python3
"""
雷达信息波/干扰波 UDP 输入源。

发送给 GNU Radio 的每个 UDP 包都是完整官方空口包：
Access Code 8B + Header 4B + Payload 15B = 27B。
GNU Radio 发射链应为 UDP Source(byte) -> GFSK Mod(do_unpack=True) -> PlutoSink。
"""

from __future__ import annotations

import argparse
import socket
import time

from radar_protocol import (
    INFO_AIR_FRAMES_PER_CYCLE,
    INFO_SERIAL_CYCLE_BYTES,
    NOMINAL_AIR_FRAMES_PER_SECOND,
    PHYSICAL_AIR_FRAME_SECONDS,
    build_info_cycle,
    build_jam_cycle,
    serial_to_air_frames,
    INFO_ACCESS_CODE,
    JAM_ACCESS_CODE,
)

UDP_IP = "127.0.0.1"
UDP_PORT = 55555


def build_cycle_frames(mode: str, seq: int, password: str) -> list[bytes]:
    if mode == "info":
        serial_data = build_info_cycle(seq)
        access_code = INFO_ACCESS_CODE
    else:
        serial_data = build_jam_cycle(password, seq)
        access_code = JAM_ACCESS_CODE
    return serial_to_air_frames(serial_data, access_code)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send official RoboMaster radar air frames to GNU Radio UDP Source.")
    parser.add_argument("--host", default=UDP_IP)
    parser.add_argument("--port", type=int, default=UDP_PORT)
    parser.add_argument("--mode", choices=("info", "jam"), default="info")
    parser.add_argument("--password", default="ABC123", help="6 ASCII letters/digits for --mode jam")
    parser.add_argument(
        "--pace",
        choices=("official", "physical"),
        default="physical",
        help="official: 90 air frames/s nominal; physical: 216 bits * 52 us per air frame",
    )
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    frame_interval = (
        1.0 / NOMINAL_AIR_FRAMES_PER_SECOND
        if args.pace == "official"
        else PHYSICAL_AIR_FRAME_SECONDS
    )

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1024 * 1024)
    addr = (args.host, args.port)
    seq = 0
    cycle_count = 0

    print(
        f"发送 {args.mode} 波到 {args.host}:{args.port}: "
        f"{INFO_SERIAL_CYCLE_BYTES}B/cycle, {INFO_AIR_FRAMES_PER_CYCLE} air frames/cycle, "
        f"{frame_interval * 1000:.3f} ms/frame"
    )

    next_send = time.monotonic()
    try:
        while True:
            frames = build_cycle_frames(args.mode, seq, args.password)
            if len(frames) != INFO_AIR_FRAMES_PER_CYCLE:
                raise RuntimeError(f"unexpected air frame count: {len(frames)}")

            for frame in frames:
                sock.sendto(frame, addr)
                next_send += frame_interval
                delay = next_send - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                elif delay < -0.5:
                    next_send = time.monotonic()

            seq = (seq + 5) % 256 if args.mode == "info" else (seq + 1) % 256
            cycle_count += 1
            if not args.quiet and cycle_count % 10 == 0:
                print(f"已发送 {cycle_count} cycles, seq=0x{seq:02X}")
    except KeyboardInterrupt:
        print("\n停止发送。")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
