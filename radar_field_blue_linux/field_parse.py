#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Field parser for radio.py outputs.

Listens to the info wave and jam1/jam2/jam3 UDP ports in parallel, validates
official air frames, and prints decoded info data plus the active 0x0A06
jamming password. This is the practical field script to run beside radio.py.
"""

from __future__ import annotations

import argparse
import select
import socket
import time
from dataclasses import dataclass, field

from radar_protocol import (
    AirPayloadExtractor,
    DecodedFrame,
    INFO_ACCESS_CODE,
    INFO_CMD_ORDER,
    JAM_ACCESS_CODE,
    JAM_CMD_ID,
    SerialFrameExtractor,
    parse_serial_frame,
)


DEFAULT_HOST = "127.0.0.1"
INFO_PORT = 55557
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


@dataclass
class InfoChannel:
    port: int
    sock: socket.socket
    air: AirPayloadExtractor
    serial: SerialFrameExtractor
    udp_packets: int = 0
    air_payloads: int = 0
    decoded_frames: int = 0
    complete_cycles: int = 0
    seen_cmds: set[int] | None = None
    last_data: dict[int, dict] | None = None
    first_cycle_printed: bool = False


@dataclass
class JamUploadState:
    """Gate decoded jamming passwords into the required 1 -> 2 -> 3 order."""

    next_level: int = 1
    highest_decoded_level: int = 0
    cached_passwords: dict[int, str] = field(default_factory=dict)
    ready_passwords: dict[int, str] = field(default_factory=dict)


def format_info_frame(frame: DecodedFrame) -> str:
    cmd = frame.cmd_id
    data = frame.data

    if cmd == 0x0A01:
        items = [
            f"{name}=({value['x_cm']},{value['y_cm']})cm"
            for name, value in data.items()
        ]
        return f"INFO cmd=0x{cmd:04X} seq={frame.seq} positions " + " ".join(items)
    if cmd == 0x0A02:
        return f"INFO cmd=0x{cmd:04X} seq={frame.seq} hp {data}"
    if cmd == 0x0A03:
        return f"INFO cmd=0x{cmd:04X} seq={frame.seq} bullet {data}"
    if cmd == 0x0A04:
        return (
            f"INFO cmd=0x{cmd:04X} seq={frame.seq} gold={data['remaining_gold']} "
            f"total={data['total_gold']} macro=0x{data['macro_state']:08X}"
        )
    if cmd == 0x0A05:
        return f"INFO cmd=0x{cmd:04X} seq={frame.seq} boosts {data}"
    return f"INFO cmd=0x{cmd:04X} seq={frame.seq} raw={data.get('raw')}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Field parser for the info + three jamming-wave UDP outputs from radio.py."
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--info-port", type=int, default=INFO_PORT)
    parser.add_argument("--jam1-port", type=int, default=JAM_PORTS[1])
    parser.add_argument("--jam2-port", type=int, default=JAM_PORTS[2])
    parser.add_argument("--jam3-port", type=int, default=JAM_PORTS[3])
    parser.add_argument(
        "--no-info",
        action="store_true",
        help="Do not bind/listen to the info-wave port.",
    )
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
        help="Exit after level-3 has been emitted as UPLOAD_READY.",
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


def open_info_channel(host: str, port: int) -> InfoChannel:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
    sock.bind((host, port))
    sock.setblocking(False)
    return InfoChannel(
        port=port,
        sock=sock,
        air=AirPayloadExtractor(INFO_ACCESS_CODE),
        serial=SerialFrameExtractor(),
        seen_cmds=set(),
        last_data={},
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


def format_info_counts(channel: InfoChannel | None) -> str:
    if channel is None:
        return "INFO:disabled"
    return (
        "INFO:udp={} air={} dec={} cycles={}".format(
            channel.udp_packets,
            channel.air_payloads,
            channel.decoded_frames,
            channel.complete_cycles,
        )
    )


def format_upload_state(state: JamUploadState) -> str:
    next_level = "done" if state.next_level > 3 else str(state.next_level)
    cached = ",".join(
        f"L{level}" for level in sorted(state.cached_passwords)
    ) or "none"
    return (
        f"upload_next={next_level} "
        f"decoded_level={state.highest_decoded_level} "
        f"cached={cached}"
    )


def emit_upload_ready(state: JamUploadState) -> None:
    while state.next_level <= 3 and state.next_level in state.cached_passwords:
        level = state.next_level
        password = state.cached_passwords[level]
        if state.ready_passwords.get(level) != password:
            print(f"UPLOAD_READY level={level} password={password}")
            state.ready_passwords[level] = password
        state.next_level += 1


def handle_chunk(
    channel: JamChannel,
    chunk: bytes,
    upload_state: JamUploadState,
    verbose: bool,
) -> None:
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
            decoded_higher = channel.level > upload_state.highest_decoded_level
            password_changed = password != channel.last_password
            first_pass = not channel.first_ok_printed

            if first_pass or decoded_higher or password_changed or verbose:
                print(
                    "PARSE_OK "
                    f"level={channel.level} cmd=0x{decoded.cmd_id:04X} "
                    f"seq={decoded.seq} password={password}"
                )

            if decoded_higher:
                print(
                    "DECODED_LEVEL "
                    f"level={channel.level} password={password}"
                )
                upload_state.highest_decoded_level = channel.level

            upload_state.cached_passwords[channel.level] = password
            emit_upload_ready(upload_state)
            channel.first_ok_printed = True
            channel.last_password = password


def handle_info_chunk(
    channel: InfoChannel,
    chunk: bytes,
    verbose: bool,
) -> None:
    channel.udp_packets += 1
    assert channel.seen_cmds is not None
    assert channel.last_data is not None

    for payload in channel.air.feed(chunk):
        channel.air_payloads += 1
        for raw_frame in channel.serial.feed(payload):
            decoded = parse_serial_frame(raw_frame)
            channel.decoded_frames += 1

            if decoded.cmd_id not in INFO_CMD_ORDER:
                if verbose:
                    print(
                        f"INFO_OTHER cmd=0x{decoded.cmd_id:04X} "
                        f"seq={decoded.seq} data={decoded.data}"
                    )
                continue

            old_data = channel.last_data.get(decoded.cmd_id)
            changed = old_data != decoded.data
            first_cmd = old_data is None
            if verbose or first_cmd or changed:
                print(format_info_frame(decoded))

            channel.last_data[decoded.cmd_id] = decoded.data
            channel.seen_cmds.add(decoded.cmd_id)

            if set(INFO_CMD_ORDER).issubset(channel.seen_cmds):
                channel.complete_cycles += 1
                if verbose or not channel.first_cycle_printed:
                    print(
                        "INFO_OK "
                        f"complete_cycle={channel.complete_cycles} "
                        f"decoded_frames={channel.decoded_frames}"
                    )
                channel.first_cycle_printed = True
                channel.seen_cmds.clear()


def main() -> None:
    args = parse_args()
    info_channel = None if args.no_info else open_info_channel(args.host, args.info_port)
    jam_channels = [
        open_channel(args.host, 1, args.jam1_port),
        open_channel(args.host, 2, args.jam2_port),
        open_channel(args.host, 3, args.jam3_port),
    ]
    sockets = [channel.sock for channel in jam_channels]
    by_socket: dict[socket.socket, JamChannel | InfoChannel] = {
        channel.sock: channel for channel in jam_channels
    }
    if info_channel is not None:
        sockets.insert(0, info_channel.sock)
        by_socket[info_channel.sock] = info_channel

    upload_state = JamUploadState()
    last_status = time.monotonic()

    print(
        "Field parser listening: "
        f"INFO={args.host}:{args.info_port} "
        f"L1={args.host}:{args.jam1_port} "
        f"L2={args.host}:{args.jam2_port} "
        f"L3={args.host}:{args.jam3_port}"
    )
    print("Info and all jamming levels are parsed in parallel.")
    print("Upload output is gated as UPLOAD_READY level=1 -> level=2 -> level=3.")

    try:
        while True:
            readable, _, _ = select.select(sockets, [], [], 0.5)
            if not readable:
                now = time.monotonic()
                if args.status_interval > 0 and now - last_status >= args.status_interval:
                    print(
                        f"status {format_upload_state(upload_state)} "
                        f"{format_info_counts(info_channel)} "
                        f"{format_counts(jam_channels)}"
                    )
                    last_status = now
                continue

            for sock in readable:
                channel = by_socket[sock]
                while True:
                    try:
                        chunk, _ = sock.recvfrom(4096)
                    except BlockingIOError:
                        break
                    if isinstance(channel, InfoChannel):
                        handle_info_chunk(channel, chunk, args.verbose)
                    else:
                        handle_chunk(
                            channel,
                            chunk,
                            upload_state,
                            args.verbose,
                        )
                        if args.exit_on_level3 and upload_state.next_level > 3:
                            return
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        for channel in jam_channels:
            channel.sock.close()
        if info_channel is not None:
            info_channel.sock.close()


if __name__ == "__main__":
    main()
