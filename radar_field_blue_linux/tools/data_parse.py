#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parse one GNU Radio UDP output stream into radar protocol data.

Use this for one wave at a time: info defaults to port 55557, jam defaults to
the level-3 port 55560. For field use across all jamming levels, use
field_parse.py instead.
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
import time

PACKAGE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, PACKAGE_ROOT)

try:
    from radar_protocol import (
        AirPayloadExtractor,
        DecodedFrame,
        INFO_ACCESS_CODE,
        INFO_CMD_ORDER,
        JAM_ACCESS_CODE,
        SerialFrameExtractor,
        parse_serial_frame,
    )
except ImportError:
    from radio_py.radar_protocol import (
        AirPayloadExtractor,
        DecodedFrame,
        INFO_ACCESS_CODE,
        INFO_CMD_ORDER,
        JAM_ACCESS_CODE,
        SerialFrameExtractor,
        parse_serial_frame,
    )


DEFAULT_HOST = "127.0.0.1"
INFO_UDP_PORT = 55557
JAM3_UDP_PORT = 55560

enemy_password = ""
enemy_password_time = 0.0
enemy_hp: dict[str, int] = {}
enemy_bullet: dict[str, int] = {}
enemy_boosts: dict[str, object] = {}
enemy_macro_state: int | None = None
radio_positions: dict[str, tuple[int, int]] = {}
last_update_time: dict[str, float] = {}

ROBOT_MAPPING = {
    "hero": "R1",
    "engineer": "R2",
    "infantry3": "R3",
    "infantry4": "R4",
    "aerial": "R5",
    "sentry": "R7",
}


def format_decoded(frame: DecodedFrame) -> str:
    cmd = frame.cmd_id
    data = frame.data

    if cmd == 0x0A01:
        items = [
            f"{name}=({value['x_cm']},{value['y_cm']})cm"
            for name, value in data.items()
        ]
        return f"cmd=0x{cmd:04X} seq={frame.seq} positions " + " ".join(items)
    if cmd == 0x0A02:
        return f"cmd=0x{cmd:04X} seq={frame.seq} hp {data}"
    if cmd == 0x0A03:
        return f"cmd=0x{cmd:04X} seq={frame.seq} bullet {data}"
    if cmd == 0x0A04:
        return (
            f"cmd=0x{cmd:04X} seq={frame.seq} gold={data['remaining_gold']} "
            f"total={data['total_gold']} macro=0x{data['macro_state']:08X}"
        )
    if cmd == 0x0A05:
        return f"cmd=0x{cmd:04X} seq={frame.seq} boosts {data}"
    if cmd == 0x0A06:
        return f"cmd=0x{cmd:04X} seq={frame.seq} password={data['password']}"
    return f"cmd=0x{cmd:04X} seq={frame.seq} raw={data.get('raw')}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Parse recovered RoboMaster radar air frames from GNU Radio UDP."
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="UDP port. Defaults to 55557 for info and 55560 for jam.",
    )
    parser.add_argument("--wave", choices=("info", "jam"), default="info")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--exit-after-pass", action="store_true")
    parser.add_argument("--status-interval", type=float, default=2.0)
    return parser.parse_args()


def update_state(decoded: DecodedFrame) -> None:
    global enemy_password, enemy_password_time, enemy_macro_state

    now = time.time()
    if decoded.cmd_id == 0x0A01:
        for key in ("hero", "engineer", "infantry3", "infantry4", "aerial", "sentry"):
            value = decoded.data[key]
            robot = ROBOT_MAPPING[key]
            radio_positions[robot] = (value["x_cm"], value["y_cm"])
            last_update_time[robot] = now
    elif decoded.cmd_id == 0x0A02:
        enemy_hp.update(
            {
                "1": decoded.data["hero"],
                "2": decoded.data["engineer"],
                "3": decoded.data["infantry3"],
                "4": decoded.data["infantry4"],
                "7": decoded.data["sentry"],
            }
        )
    elif decoded.cmd_id == 0x0A03:
        enemy_bullet.update(
            {
                "1": decoded.data["hero"],
                "3": decoded.data["infantry3"],
                "4": decoded.data["infantry4"],
                "6": decoded.data["aerial"],
                "7": decoded.data["sentry"],
            }
        )
    elif decoded.cmd_id == 0x0A04:
        enemy_macro_state = decoded.data["macro_state"]
    elif decoded.cmd_id == 0x0A05:
        enemy_boosts.update(
            {
                "1": decoded.data["hero"],
                "2": decoded.data["engineer"],
                "3": decoded.data["infantry3"],
                "4": decoded.data["infantry4"],
                "7": decoded.data["sentry"],
                "sentry_posture": decoded.data["sentry_posture"],
            }
        )
    elif decoded.cmd_id == 0x0A06:
        enemy_password = decoded.data["password"]
        enemy_password_time = now


def main() -> None:
    args = parse_args()
    port = args.port if args.port is not None else (
        JAM3_UDP_PORT if args.wave == "jam" else INFO_UDP_PORT
    )
    access_code = INFO_ACCESS_CODE if args.wave == "info" else JAM_ACCESS_CODE
    expected = set(INFO_CMD_ORDER) if args.wave == "info" else {0x0A06}

    air = AirPayloadExtractor(access_code)
    serial = SerialFrameExtractor()
    seen: set[int] = set()
    last_cycle_time: float | None = None
    udp_packets = 0
    air_payloads = 0
    decoded_frames = 0
    last_status = time.monotonic()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
    sock.settimeout(0.5)
    sock.bind((args.host, port))

    print(
        f"Listening UDP {args.host}:{port}, wave={args.wave}, "
        f"access={access_code.hex().upper()}"
    )
    if args.wave == "jam":
        print("Waiting for blue level-3 jam frames on port 55560.")

    try:
        while True:
            try:
                chunk, _ = sock.recvfrom(4096)
            except socket.timeout:
                now = time.monotonic()
                if args.status_interval > 0 and now - last_status >= args.status_interval:
                    print(
                        "status "
                        f"udp_packets={udp_packets} air_payloads={air_payloads} "
                        f"decoded_frames={decoded_frames}"
                    )
                    last_status = now
                continue

            udp_packets += 1
            for payload in air.feed(chunk):
                air_payloads += 1
                for raw_frame in serial.feed(payload):
                    decoded = parse_serial_frame(raw_frame)
                    decoded_frames += 1
                    seen.add(decoded.cmd_id)
                    update_state(decoded)

                    if not args.quiet:
                        print(format_decoded(decoded))

                    if args.wave == "jam" and decoded.cmd_id == 0x0A06:
                        print(
                            "PARSE_OK 解析通过: "
                            f"blue jam3 cmd=0x0A06 password={decoded.data['password']}"
                        )
                        if args.exit_after_pass:
                            return

                    if args.wave == "info" and expected.issubset(seen):
                        now = time.monotonic()
                        if last_cycle_time is None:
                            print("PARSE_OK 解析通过: first complete info cycle")
                        else:
                            interval = now - last_cycle_time
                            freq = 1.0 / interval if interval > 0 else 0.0
                            print(
                                "PARSE_OK 解析通过: "
                                f"complete info cycle interval={interval * 1000:.1f}ms "
                                f"freq={freq:.2f}Hz"
                            )
                        last_cycle_time = now
                        seen.clear()
                        if args.exit_after_pass:
                            return
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
