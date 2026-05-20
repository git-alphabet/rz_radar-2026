#!/usr/bin/env python3
"""Short UDP probe for recovered radar air frames.

Use this as a quick diagnostic to count UDP packets, recovered air payloads, and
CRC-valid referee frames on a chosen info/jam port.
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

from radar_protocol import (
    AirPayloadExtractor,
    INFO_ACCESS_CODE,
    JAM_ACCESS_CODE,
    SerialFrameExtractor,
    parse_serial_frame,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe GNU Radio recovered radar air frames on UDP.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--wave", choices=("info", "jam"), required=True)
    parser.add_argument("--seconds", type=float, default=5.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    access_code = INFO_ACCESS_CODE if args.wave == "info" else JAM_ACCESS_CODE
    air = AirPayloadExtractor(access_code)
    serial = SerialFrameExtractor()

    udp_packets = 0
    udp_bytes = 0
    air_payloads = 0
    decoded_frames = 0
    first_packet = b""

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.5)
    sock.bind((args.host, args.port))

    deadline = time.monotonic() + args.seconds
    while time.monotonic() < deadline:
        try:
            chunk, _ = sock.recvfrom(4096)
        except socket.timeout:
            continue

        udp_packets += 1
        udp_bytes += len(chunk)
        if not first_packet:
            first_packet = chunk

        for payload in air.feed(chunk):
            air_payloads += 1
            for raw in serial.feed(payload):
                decoded = parse_serial_frame(raw)
                decoded_frames += 1
                print(f"decoded cmd=0x{decoded.cmd_id:04X} seq={decoded.seq} data={decoded.data}")
                if args.wave == "jam" and decoded.cmd_id == 0x0A06:
                    print(
                        "PARSE_OK 解析通过: "
                        f"blue jam3 cmd=0x0A06 password={decoded.data['password']}"
                    )

    sock.close()
    print(
        f"udp_packets={udp_packets} udp_bytes={udp_bytes} "
        f"air_payloads={air_payloads} decoded_frames={decoded_frames}"
    )
    if first_packet:
        print(f"first_udp_len={len(first_packet)} first_udp_hex={first_packet[:64].hex().upper()}")


if __name__ == "__main__":
    main()
