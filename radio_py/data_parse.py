"""Adapter: bridges radar_field_blue_linux protocol to the interface main.py expects.

Provides run_listener() and the shared global state variables (radio_positions,
last_update_time, enemy_hp, enemy_bullet, enemy_boosts, enemy_macro_state,
enemy_password) that main.py imports.
"""

import socket
import time
from typing import Optional

from radar_field_blue_linux.radar_protocol import (
    AirPayloadExtractor,
    SerialFrameExtractor,
    parse_serial_frame,
    INFO_ACCESS_CODE,
    JAM_ACCESS_CODE,
    INFO_CMD_ORDER,
)

# --- shared mutable state (populated by listener threads) ---

radio_positions: dict[str, tuple[int, int]] = {}   # "R1"-"R7" -> (x_cm, y_cm)
last_update_time: dict[str, float] = {}             # "R1"-"R7" -> timestamp
enemy_hp: dict[str, int] = {}                       # "1"-"7" -> HP
enemy_bullet: dict[str, int] = {}                   # "1","3","4","6","7" -> ammo
enemy_boosts: dict[str, object] = {}                # "1"-"7" + "sentry_posture"
enemy_macro_state: Optional[int] = None              # 32-bit bitfield from 0x0A04
enemy_password: str = ""                            # last decoded 0x0A06 password
enemy_password_time: float = 0.0

# protocol field name -> robot ID
ROBOT_MAPPING = {
    "hero": "R1",
    "engineer": "R2",
    "infantry3": "R3",
    "infantry4": "R4",
    "aerial": "R5",
    "sentry": "R7",
}

# cmd_ids handled by info vs jam listeners
_INFO_CMDS = set(INFO_CMD_ORDER)  # 0x0A01..0x0A05
_JAM_CMD = 0x0A06


def _update_state(decoded) -> None:
    """Dispatch a DecodedFrame into the module-level globals."""
    global enemy_macro_state, enemy_password, enemy_password_time

    cmd = decoded.cmd_id
    data = decoded.data

    if cmd == 0x0A01:
        for field_name, robot_id in ROBOT_MAPPING.items():
            entry = data.get(field_name)
            if entry is not None:
                radio_positions[robot_id] = (entry["x_cm"], entry["y_cm"])
                last_update_time[robot_id] = time.time()

    elif cmd == 0x0A02:
        for key in ("hero", "engineer", "infantry3", "infantry4", "sentry"):
            idx_map = {"hero": "1", "engineer": "2", "infantry3": "3",
                       "infantry4": "4", "sentry": "7"}
            val = data.get(key)
            if val is not None:
                enemy_hp[idx_map[key]] = val

    elif cmd == 0x0A03:
        idx_map = {"hero": "1", "infantry3": "3", "infantry4": "4",
                   "aerial": "6", "sentry": "7"}
        for key, idx in idx_map.items():
            val = data.get(key)
            if val is not None:
                enemy_bullet[idx] = val

    elif cmd == 0x0A04:
        enemy_macro_state = data.get("macro_state")

    elif cmd == 0x0A05:
        for key in ("hero", "engineer", "infantry3", "infantry4", "sentry"):
            idx_map = {"hero": "1", "engineer": "2", "infantry3": "3",
                       "infantry4": "4", "sentry": "7"}
            val = data.get(key)
            if val is not None:
                enemy_boosts[idx_map[key]] = val
        sp = data.get("sentry_posture")
        if sp is not None:
            enemy_boosts["sentry_posture"] = sp

    elif cmd == 0x0A06:
        enemy_password = data.get("password", "")
        enemy_password_time = time.time()


def run_listener(host: str, port: int, wave: str, quiet: bool) -> None:
    """Listen on a single UDP port and update shared globals.

    wave: 'info' processes 0x0A01..0x0A05, 'jam' processes 0x0A06.
    Designed to run as a daemon thread from main.py.
    """
    access_code = INFO_ACCESS_CODE if wave == "info" else JAM_ACCESS_CODE
    air = AirPayloadExtractor(access_code)
    serial = SerialFrameExtractor()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
    sock.bind((host, port))

    try:
        _rec = None
        try:
            from recorder import get_recorder
            _rec = get_recorder()
        except Exception:
            pass

        while True:
            chunk, _ = sock.recvfrom(4096)
            for payload in air.feed(chunk):
                for raw_frame in serial.feed(payload):
                    decoded = parse_serial_frame(raw_frame)

                    # filter by wave type
                    if wave == "info" and decoded.cmd_id not in _INFO_CMDS:
                        continue
                    if wave == "jam" and decoded.cmd_id != _JAM_CMD:
                        continue

                    _update_state(decoded)

                    if not quiet or decoded.cmd_id == _JAM_CMD:
                        print(f"[radio] cmd=0x{decoded.cmd_id:04X} "
                              f"seq={decoded.seq} data={decoded.data}")

                    if _rec:
                        _rec.record("radio_rx", {
                            "cmd": decoded.cmd_id,
                            "seq": decoded.seq,
                            "data": decoded.data,
                        })
    except Exception as e:
        print(f"[radio] listener error on port {port}: {e}")
    finally:
        sock.close()
