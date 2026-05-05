#!/usr/bin/env python3
"""
RoboMaster 2026 radar radio protocol helpers.

This module keeps the official air-frame and referee serial-frame rules in one
place:
- Air frame: Access Code 8B + Header 4B + Payload 15B = 27B
- Info wave serial data: 0x0A01..0x0A05, 135B per nominal 10 Hz cycle
- Recovered GNU Radio byte stream is MSB-first bytes after GFSK demod + repack
"""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass
from typing import Iterable

from ser_api import Get_CRC8_Check_Sum, Get_CRC16_Check_Sum

INFO_ACCESS_CODE = bytes.fromhex("2F6F4C74B914492E")
JAM_ACCESS_CODE = bytes.fromhex("16E8D377151C712D")

AIR_PAYLOAD_BYTES = 15
AIR_HEADER_BYTES = 4
AIR_FRAME_BYTES = 8 + AIR_HEADER_BYTES + AIR_PAYLOAD_BYTES
AIR_HEADER = struct.pack(">HH", AIR_PAYLOAD_BYTES, AIR_PAYLOAD_BYTES)

SERIAL_HEADER_BYTES = 5
SERIAL_CMD_BYTES = 2
SERIAL_TAIL_BYTES = 2
SERIAL_OVERHEAD_BYTES = SERIAL_HEADER_BYTES + SERIAL_CMD_BYTES + SERIAL_TAIL_BYTES

INFO_CMD_ORDER = (0x0A01, 0x0A02, 0x0A03, 0x0A04, 0x0A05)
INFO_DATA_LENGTHS = {
    0x0A01: 24,
    0x0A02: 12,
    0x0A03: 10,
    0x0A04: 8,
    0x0A05: 36,
}
JAM_CMD_ID = 0x0A06
JAM_DATA_LENGTH = 6

INFO_SERIAL_CYCLE_BYTES = sum(INFO_DATA_LENGTHS.values()) + len(INFO_CMD_ORDER) * SERIAL_OVERHEAD_BYTES
INFO_AIR_FRAMES_PER_CYCLE = INFO_SERIAL_CYCLE_BYTES // AIR_PAYLOAD_BYTES
NOMINAL_INFO_CYCLE_HZ = 10
NOMINAL_AIR_FRAMES_PER_SECOND = INFO_AIR_FRAMES_PER_CYCLE * NOMINAL_INFO_CYCLE_HZ

SAMPLE_RATE = 1_000_000
SAMPLES_PER_SYMBOL = 52
AIR_BITS_PER_FRAME = AIR_FRAME_BYTES * 8
PHYSICAL_AIR_FRAME_SECONDS = AIR_BITS_PER_FRAME * SAMPLES_PER_SYMBOL / SAMPLE_RATE


def build_serial_frame(cmd_id: int, data: bytes | bytearray, seq: int) -> bytes:
    data = bytes(data)
    header = bytearray([0xA5])
    header.extend(struct.pack("<H", len(data)))
    header.append(seq & 0xFF)
    header.append(Get_CRC8_Check_Sum(header, 4))

    body = struct.pack("<H", cmd_id) + data
    crc16 = Get_CRC16_Check_Sum(header + body, len(header) + len(body))
    return bytes(header + body + struct.pack("<H", crc16))


def validate_serial_frame(frame: bytes) -> tuple[bool, str]:
    if len(frame) < SERIAL_OVERHEAD_BYTES:
        return False, "too short"
    if frame[0] != 0xA5:
        return False, "missing SOF"

    data_len = struct.unpack("<H", frame[1:3])[0]
    expected_len = SERIAL_OVERHEAD_BYTES + data_len
    if len(frame) != expected_len:
        return False, f"length {len(frame)} != {expected_len}"

    if Get_CRC8_Check_Sum(frame[:4], 4) != frame[4]:
        return False, "CRC8 mismatch"

    calc_crc16 = Get_CRC16_Check_Sum(frame[:-2], len(frame) - 2)
    recv_crc16 = struct.unpack("<H", frame[-2:])[0]
    if calc_crc16 != recv_crc16:
        return False, "CRC16 mismatch"

    return True, "ok"


def split_serial_frames(serial_bytes: bytes) -> list[bytes]:
    frames: list[bytes] = []
    offset = 0
    while offset < len(serial_bytes):
        if len(serial_bytes) - offset < SERIAL_OVERHEAD_BYTES:
            raise ValueError("truncated serial frame")
        if serial_bytes[offset] != 0xA5:
            raise ValueError(f"missing SOF at offset {offset}")
        data_len = struct.unpack("<H", serial_bytes[offset + 1:offset + 3])[0]
        total_len = SERIAL_OVERHEAD_BYTES + data_len
        frame = serial_bytes[offset:offset + total_len]
        ok, reason = validate_serial_frame(frame)
        if not ok:
            raise ValueError(f"invalid serial frame at offset {offset}: {reason}")
        frames.append(frame)
        offset += total_len
    return frames


def build_info_cycle(seq_start: int = 0) -> bytes:
    """Build one nominal 10 Hz information-wave serial-data cycle, 135 bytes."""
    frames = bytearray()

    positions = [1500, 800, 1300, 700, 1400, 750, 1600, 750, 1450, 900, 1550, 1000]
    frames.extend(build_serial_frame(0x0A01, struct.pack("<12H", *positions), seq_start + 0))

    health = [400, 400, 400, 400, 0, 400]
    frames.extend(build_serial_frame(0x0A02, struct.pack("<6H", *health), seq_start + 1))

    ammo = [50, 500, 500, 750, 300]
    frames.extend(build_serial_frame(0x0A03, struct.pack("<5H", *ammo), seq_start + 2))

    gold, total_gold = 2000, 5000
    # 32-bit macro-state bitfield from the communication protocol.
    macro_state = 0b00010101
    frames.extend(build_serial_frame(0x0A04, struct.pack("<HHI", gold, total_gold, macro_state), seq_start + 3))

    buffs = [(0, 0, 0, 0, 100)] * 5  # hero, engineer, infantry3, infantry4, sentry
    buff_payload = bytearray()
    for rec, cool, defense, vuln, attack in buffs:
        buff_payload.extend(struct.pack("<BHBBH", rec, cool, defense, vuln, attack))
    buff_payload.append(2)
    frames.extend(build_serial_frame(0x0A05, buff_payload, seq_start + 4))

    if len(frames) != INFO_SERIAL_CYCLE_BYTES:
        raise AssertionError(f"info cycle length {len(frames)} != {INFO_SERIAL_CYCLE_BYTES}")
    return bytes(frames)


def build_jam_cycle(password: str | bytes, seq: int = 0) -> bytes:
    """Build one 135-byte jamming-wave serial-data cycle with 0x0A06 plus random fill."""
    if isinstance(password, str):
        password_bytes = password.encode("ascii")
    else:
        password_bytes = bytes(password)
    if len(password_bytes) != JAM_DATA_LENGTH or not password_bytes.isalnum():
        raise ValueError("jamming password must be exactly 6 ASCII letters/digits")

    frame = build_serial_frame(JAM_CMD_ID, password_bytes, seq)
    fill_len = INFO_SERIAL_CYCLE_BYTES - len(frame)
    return frame + os.urandom(fill_len)


def serial_to_air_frames(serial_bytes: bytes, access_code: bytes = INFO_ACCESS_CODE) -> list[bytes]:
    if len(serial_bytes) % AIR_PAYLOAD_BYTES != 0:
        raise ValueError("serial byte stream length must be a multiple of 15")
    prefix = access_code + AIR_HEADER
    return [
        prefix + serial_bytes[i:i + AIR_PAYLOAD_BYTES]
        for i in range(0, len(serial_bytes), AIR_PAYLOAD_BYTES)
    ]


@dataclass
class DecodedFrame:
    cmd_id: int
    seq: int
    data: dict


class AirPayloadExtractor:
    """Extract 15-byte Payload chunks from a recovered continuous air byte stream."""

    def __init__(self, access_code: bytes = INFO_ACCESS_CODE):
        self.access_code = access_code
        self.buffer = bytearray()

    def feed(self, data: bytes) -> list[bytes]:
        self.buffer.extend(data)
        payloads: list[bytes] = []
        code_len = len(self.access_code)

        while True:
            pos = self.buffer.find(self.access_code)
            if pos < 0:
                keep = max(code_len - 1, 0)
                if len(self.buffer) > keep:
                    del self.buffer[:-keep]
                return payloads

            if pos > 0:
                del self.buffer[:pos]

            if len(self.buffer) < AIR_FRAME_BYTES:
                return payloads

            length_a, length_b = struct.unpack(">HH", self.buffer[code_len:code_len + AIR_HEADER_BYTES])
            if length_a != AIR_PAYLOAD_BYTES or length_b != AIR_PAYLOAD_BYTES:
                del self.buffer[0]
                continue

            start = code_len + AIR_HEADER_BYTES
            payloads.append(bytes(self.buffer[start:start + AIR_PAYLOAD_BYTES]))
            del self.buffer[:AIR_FRAME_BYTES]


class SerialFrameExtractor:
    """Extract and CRC-check referee serial frames from a continuous byte stream."""

    def __init__(self):
        self.buffer = bytearray()

    def feed(self, data: bytes) -> list[bytes]:
        self.buffer.extend(data)
        frames: list[bytes] = []

        while True:
            sof = self.buffer.find(b"\xA5")
            if sof < 0:
                self.buffer.clear()
                return frames
            if sof > 0:
                del self.buffer[:sof]

            if len(self.buffer) < SERIAL_HEADER_BYTES:
                return frames

            if Get_CRC8_Check_Sum(self.buffer[:4], 4) != self.buffer[4]:
                del self.buffer[0]
                continue

            data_len = struct.unpack("<H", self.buffer[1:3])[0]
            total_len = SERIAL_OVERHEAD_BYTES + data_len
            if total_len > INFO_SERIAL_CYCLE_BYTES:
                del self.buffer[0]
                continue
            if len(self.buffer) < total_len:
                return frames

            frame = bytes(self.buffer[:total_len])
            ok, _ = validate_serial_frame(frame)
            if ok:
                frames.append(frame)
                del self.buffer[:total_len]
            else:
                del self.buffer[0]


def parse_serial_frame(frame: bytes) -> DecodedFrame:
    ok, reason = validate_serial_frame(frame)
    if not ok:
        raise ValueError(reason)

    data_len = struct.unpack("<H", frame[1:3])[0]
    seq = frame[3]
    cmd_id = struct.unpack("<H", frame[5:7])[0]
    payload = frame[7:7 + data_len]

    if cmd_id == 0x0A01:
        values = struct.unpack("<12H", payload)
        names = ("hero", "engineer", "infantry3", "infantry4", "aerial", "sentry")
        data = {
            name: {"x_cm": values[i * 2], "y_cm": values[i * 2 + 1]}
            for i, name in enumerate(names)
        }
    elif cmd_id == 0x0A02:
        values = struct.unpack("<6H", payload)
        names = ("hero", "engineer", "infantry3", "infantry4", "reserved", "sentry")
        data = dict(zip(names, values))
    elif cmd_id == 0x0A03:
        values = struct.unpack("<5H", payload)
        names = ("hero", "infantry3", "infantry4", "aerial", "sentry")
        data = dict(zip(names, values))
    elif cmd_id == 0x0A04:
        gold, total_gold, macro_state = struct.unpack("<HHI", payload)
        data = {"remaining_gold": gold, "total_gold": total_gold, "macro_state": macro_state}
    elif cmd_id == 0x0A05:
        names = ("hero", "engineer", "infantry3", "infantry4", "sentry")
        data = {}
        offset = 0
        for name in names:
            rec, cool, defense, vuln, attack = struct.unpack_from("<BHBBH", payload, offset)
            data[name] = {
                "hp_recover_percent": rec,
                "heat_cooling": cool,
                "defense_percent": defense,
                "negative_defense_percent": vuln,
                "attack_percent": attack,
            }
            offset += 7
        data["sentry_posture"] = payload[offset]
    elif cmd_id == 0x0A06:
        data = {"password": payload.decode("ascii", errors="replace")}
    else:
        data = {"raw": payload.hex()}

    return DecodedFrame(cmd_id=cmd_id, seq=seq, data=data)


def iter_decoded_frames_from_air_chunks(chunks: Iterable[bytes], access_code: bytes = INFO_ACCESS_CODE):
    air = AirPayloadExtractor(access_code)
    serial = SerialFrameExtractor()
    for chunk in chunks:
        for payload in air.feed(chunk):
            for frame in serial.feed(payload):
                yield parse_serial_frame(frame)
