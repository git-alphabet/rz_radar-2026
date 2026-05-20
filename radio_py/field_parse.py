#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Field jamming parser for radio.py outputs.

Listens to jam1/jam2/jam3 UDP ports in parallel, validates official air frames,
and prints the active decoded 0x0A06 password. This is the practical script for
checking which jamming level is currently decodable.
"""

from __future__ import annotations

import argparse
import select
import socket
import time
from dataclasses import dataclass

from radar_protocol import (
    AirPayloadExtractor,
    JAM_ACCESS_CODE,
    JAM_CMD_ID,
    SerialFrameExtractor,
    parse_serial_frame,
)


DEFAULT_HOST = "127.0.0.1"
JAM_PORTS = {
    1: 55558,
    2: 55559,
    3: 55560,
}


@dataclass
class JamChannel:
    level: int
    port: int
    sock: socket.socket
    air: AirPayloadExtractor
    serial: SerialFrameExtractor
    udp_packets: int = 0
    air_payloads: int = 0
    decoded_frames: int = 0
    last_password: str = ""
    first_ok_printed: bool = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Field parser for the three jamming-wave UDP outputs from radio.py."
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--jam1-port", type=int, default=JAM_PORTS[1])
    parser.add_argument("--jam2-port", type=int, default=JAM_PORTS[2])
    parser.add_argument("--jam3-port", type=int, default=JAM_PORTS[3])
    parser.add_argument(
        "--status-interval",
        type=float,
        default=2.0,
        help="Seconds between no-data/progress status lines. 0 disables status.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print every decoded frame instead of only first pass/password changes.",
    )
    parser.add_argument(
        "--exit-on-level3",
        action="store_true",
        help="Exit after a level-3 jamming password is decoded.",
    )
    return parser.parse_args()


def open_channel(host: str, level: int, port: int) -> JamChannel:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
    sock.bind((host, port))
    sock.setblocking(False)
    return JamChannel(
        level=level,
        port=port,
        sock=sock,
        air=AirPayloadExtractor(JAM_ACCESS_CODE),
        serial=SerialFrameExtractor(),
    )


def format_counts(channels: list[JamChannel]) -> str:
    parts = []
    for channel in channels:
        parts.append(
            "L{}:udp={} air={} dec={}".format(
                channel.level,
                channel.udp_packets,
                channel.air_payloads,
                channel.decoded_frames,
            )
        )
    return " ".join(parts)


def handle_chunk(
    channel: JamChannel,
    chunk: bytes,
    current_level: int,
    verbose: bool,
) -> int:
    channel.udp_packets += 1
    for payload in channel.air.feed(chunk):
        channel.air_payloads += 1
        for raw_frame in channel.serial.feed(payload):
            decoded = parse_serial_frame(raw_frame)
            channel.decoded_frames += 1

            if decoded.cmd_id != JAM_CMD_ID:
                if verbose:
                    print(
                        f"decoded level={channel.level} cmd=0x{decoded.cmd_id:04X} "
                        f"seq={decoded.seq} data={decoded.data}"
                    )
                continue

            password = decoded.data["password"]
            upgraded = channel.level > current_level
            password_changed = password != channel.last_password
            first_pass = not channel.first_ok_printed

            if first_pass or upgraded or password_changed or verbose:
                print(
                    "PARSE_OK "
                    f"level={channel.level} cmd=0x{decoded.cmd_id:04X} "
                    f"seq={decoded.seq} password={password}"
                )

            if upgraded:
                print(
                    "ACTIVE_LEVEL "
                    f"level={channel.level} password={password}"
                )
                current_level = channel.level

            channel.first_ok_printed = True
            channel.last_password = password

    return current_level


def main() -> None:
    args = parse_args()
    channels = [
        open_channel(args.host, 1, args.jam1_port),
        open_channel(args.host, 2, args.jam2_port),
        open_channel(args.host, 3, args.jam3_port),
    ]
    sockets = [channel.sock for channel in channels]
    by_socket = {channel.sock: channel for channel in channels}
    current_level = 0
    last_status = time.monotonic()

    print(
        "Field parser listening: "
        f"L1={args.host}:{args.jam1_port} "
        f"L2={args.host}:{args.jam2_port} "
        f"L3={args.host}:{args.jam3_port}"
    )
    print("Each level is parsed in parallel; level 1 is never gated by level 2/3.")

    try:
        while True:
            readable, _, _ = select.select(sockets, [], [], 0.5)
            if not readable:
                now = time.monotonic()
                if args.status_interval > 0 and now - last_status >= args.status_interval:
                    print(f"status active_level={current_level} {format_counts(channels)}")
                    last_status = now
                continue

            for sock in readable:
                channel = by_socket[sock]
                while True:
                    try:
                        chunk, _ = sock.recvfrom(4096)
                    except BlockingIOError:
                        break
                    current_level = handle_chunk(
                        channel,
                        chunk,
                        current_level,
                        args.verbose,
                    )
                    if args.exit_on_level3 and current_level >= 3:
                        return
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        for channel in channels:
            channel.sock.close()


if __name__ == "__main__":
    main()
