#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline decoder for the RX_BLUE_ganrao_3 recording.

Reads the complex64 IQ recording directly, demodulates the blue level-3 jamming
wave, validates CRC, and can optionally replay recovered 27-byte air frames to
UDP for parser testing.
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
import time

import pmt
from gnuradio import blocks, digital, filter, gr
from gnuradio.fft import window
from gnuradio.filter import firdes

from gr_air_frame_extractor import AccessCodeBitFrameExtractor
from radar_protocol import (
    AIR_FRAME_BYTES,
    AirPayloadExtractor,
    JAM_ACCESS_CODE,
    SerialFrameExtractor,
    parse_serial_frame,
)


DEFAULT_RECORDING = "C:/Users/GMD777/Desktop/radio_py/RX_BLUE_ganrao_3"
SAMPLE_RATE = 2_000_000
XLATE_DECIM = 2
CHANNEL_RATE = SAMPLE_RATE // XLATE_DECIM
JAM3_CUTOFF = 180_000
TRANSITION = 20_000
JAM3_SPS = 52
JAM3_SENSITIVITY = 0.6646
JAM_ACCESS_BITS = "".join(f"{byte:08b}" for byte in JAM_ACCESS_CODE)


class BlueJam3OfflineDecoder(gr.top_block):
    def __init__(self, recording: str, max_samples: int):
        gr.top_block.__init__(self, "Blue jam3 offline decoder", catch_exceptions=True)

        self.file_source = blocks.file_source(gr.sizeof_gr_complex, recording, False, 0, 0)
        self.file_source.set_begin_tag(pmt.PMT_NIL)
        self.channel_filter = filter.freq_xlating_fir_filter_ccf(
            XLATE_DECIM,
            firdes.low_pass(
                1,
                SAMPLE_RATE,
                JAM3_CUTOFF,
                TRANSITION,
                window.WIN_HAMMING,
                6.76,
            ),
            0.0,
            SAMPLE_RATE,
        )
        self.demod = digital.gfsk_demod(
            samples_per_symbol=JAM3_SPS,
            sensitivity=JAM3_SENSITIVITY,
            gain_mu=0.175,
            mu=0.5,
            omega_relative_limit=0.005,
            freq_error=0.0,
            verbose=False,
            log=False,
        )
        self.correlator = digital.correlate_access_code_tag_bb(
            JAM_ACCESS_BITS, 2, "frame_start"
        )
        self.frame_extractor = AccessCodeBitFrameExtractor(
            access_code_hex=JAM_ACCESS_CODE.hex(),
            header_hex="000F000F",
            frame_bytes=AIR_FRAME_BYTES,
            bit_order="msb",
            output_mode="bits",
        )
        self.repack = blocks.repack_bits_bb(1, 8, "", False, gr.GR_MSB_FIRST)
        self.sink = blocks.vector_sink_b()

        if max_samples > 0:
            self.head = blocks.head(gr.sizeof_gr_complex, max_samples)
            self.connect(self.file_source, self.head)
            self.connect(self.head, self.channel_filter)
        else:
            self.connect(self.file_source, self.channel_filter)

        self.connect(self.channel_filter, self.demod)
        self.connect(self.demod, self.correlator)
        self.connect(self.correlator, self.frame_extractor)
        self.connect(self.frame_extractor, self.repack)
        self.connect(self.repack, self.sink)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Decode the RX_BLUE_ganrao_3 complex64 recording without RF hardware."
    )
    parser.add_argument("--recording", default=DEFAULT_RECORDING)
    parser.add_argument(
        "--max-samples",
        type=int,
        default=0,
        help="0 means decode the whole file. Use e.g. 8000000 for a faster partial check.",
    )
    parser.add_argument(
        "--udp-port",
        type=int,
        default=0,
        help="Optionally replay recovered 27-byte air frames to this UDP port.",
    )
    parser.add_argument("--udp-host", default="127.0.0.1")
    parser.add_argument("--udp-delay", type=float, default=0.002)
    return parser.parse_args()


def decode_recording(recording: str, max_samples: int) -> bytes:
    if not os.path.isfile(recording):
        raise FileNotFoundError(f"recording not found: {recording}")

    tb = BlueJam3OfflineDecoder(recording, max_samples)
    tb.run()
    return bytes(tb.sink.data())


def iter_air_frames(air_bytes: bytes):
    for offset in range(0, len(air_bytes) - AIR_FRAME_BYTES + 1, AIR_FRAME_BYTES):
        frame = air_bytes[offset:offset + AIR_FRAME_BYTES]
        if frame.startswith(JAM_ACCESS_CODE):
            yield frame


def send_udp(frames: list[bytes], host: str, port: int, delay: float) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        for frame in frames:
            sock.sendto(frame, (host, port))
            if delay > 0:
                time.sleep(delay)
    finally:
        sock.close()


def main() -> int:
    args = parse_args()
    print(
        f"Offline decoding {args.recording} at 2MS/s -> 1MS/s, "
        f"SPS={JAM3_SPS}, sensitivity={JAM3_SENSITIVITY}"
    )

    try:
        air_bytes = decode_recording(args.recording, args.max_samples)
    except Exception as exc:
        print(f"DECODE_ERROR: {exc}", file=sys.stderr)
        return 2
    frames = list(iter_air_frames(air_bytes))

    air = AirPayloadExtractor(JAM_ACCESS_CODE)
    serial = SerialFrameExtractor()
    decoded = []
    payload_count = 0
    for payload in air.feed(b"".join(frames)):
        payload_count += 1
        for raw in serial.feed(payload):
            decoded.append(parse_serial_frame(raw))

    print(
        f"recovered_air_frames={len(frames)} air_payloads={payload_count} "
        f"decoded_frames={len(decoded)}"
    )

    if args.udp_port:
        send_udp(frames, args.udp_host, args.udp_port, args.udp_delay)
        print(f"sent_udp_air_frames={len(frames)} to {args.udp_host}:{args.udp_port}")

    for frame in decoded:
        if frame.cmd_id == 0x0A06:
            print(
                "PARSE_OK 解析通过: "
                f"blue jam3 cmd=0x0A06 password={frame.data['password']}"
            )
            return 0

    print("PARSE_FAIL: no CRC-valid cmd=0x0A06 frame decoded", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
