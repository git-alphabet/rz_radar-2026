"""
Async data recorder for radar station.
Records structured events (JSONL) and video frames (MP4).
Uses queue + background thread to avoid blocking the main loop.

Usage:
    from recorder import init_recorder, get_recorder

    # Initialize (auto-creates .jsonl + .mp4)
    init_recorder("logs/recording")

    # Record events
    recorder = get_recorder()
    recorder.record("vision", {"B1": [1200, 800]})
    recorder.record("send_map", {"x": 100, "y": 200})
    recorder.record("radio_rx", {"cmd": "0x0A01", "seq": 5})

    # Record video frame (call once per loop iteration)
    recorder.record_frame(img0)

    # Stop
    recorder.stop()

    # Playback
    from recorder import play_recording
    player = play_recording("logs/recording")
    for record in player.iter_records():
        print(record["ts"], record["type"], record["data"])
"""

import json
import os
import queue
import threading
import time
from typing import Any, Dict, List, Optional

import cv2
import numpy as np


class AsyncRecorder:
    """Async recorder with queue + background thread."""

    def __init__(self, filepath: str, flush_interval: float = 1.0):
        self._filepath = filepath
        self._flush_interval = flush_interval
        self._running = False
        self._thread = None
        self._file = None
        self._count = 0
        self._queue: queue.Queue = queue.Queue()

        # Video writer (camera)
        self._video_path = filepath.replace(".jsonl", ".mp4")
        self._video_writer: Optional[cv2.VideoWriter] = None
        self._video_fps = 30.0
        self._frame_queue: queue.Queue = queue.Queue(maxsize=300)

        # Video writer (map UI)
        self._map_video_path = filepath.replace(".jsonl", "_map.mp4")
        self._map_video_writer: Optional[cv2.VideoWriter] = None
        self._map_frame_queue: queue.Queue = queue.Queue(maxsize=300)

    def start(self):
        """Start recording."""
        os.makedirs(os.path.dirname(self._filepath) or ".", exist_ok=True)
        self._file = open(self._filepath, "a", encoding="utf-8")
        self._running = True
        self._thread = threading.Thread(target=self._writer_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop recording and flush remaining data."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        # Drain remaining items
        self._drain_queue()
        self._drain_frame_queue()
        if self._file:
            self._file.flush()
            self._file.close()
            self._file = None
        if self._video_writer:
            self._video_writer.release()
            self._video_writer = None
        if self._map_video_writer:
            self._map_video_writer.release()
            self._map_video_writer = None

    def record(self, event_type: str, data: Any):
        """Non-blocking enqueue for structured events."""
        self._queue.put_nowait({
            "ts": time.time(),
            "type": event_type,
            "data": data,
        })

    def record_frame(self, frame: np.ndarray):
        """Non-blocking enqueue for video frame.

        Args:
            frame: BGR image from cv2 (numpy array).
        """
        if frame is None:
            return
        # Initialize video writer on first frame
        if self._video_writer is None:
            h, w = frame.shape[:2]
            fourcc = cv2.VideoWriter_fourcc(*"avc1")
            self._video_writer = cv2.VideoWriter(
                self._video_path, fourcc, self._video_fps, (w, h)
            )
            print(f"Video recording: {self._video_path} ({w}x{h}@{self._video_fps}fps)")
        try:
            self._frame_queue.put_nowait((time.time(), frame))
        except queue.Full:
            pass  # drop frame to avoid blocking main thread

    def record_map_frame(self, frame: np.ndarray):
        """Non-blocking enqueue for map UI frame."""
        if frame is None:
            return
        if self._map_video_writer is None:
            h, w = frame.shape[:2]
            fourcc = cv2.VideoWriter_fourcc(*"avc1")
            self._map_video_writer = cv2.VideoWriter(
                self._map_video_path, fourcc, self._video_fps, (w, h)
            )
            print(f"Map recording: {self._map_video_path} ({w}x{h}@{self._video_fps}fps)")
        try:
            self._map_frame_queue.put_nowait((time.time(), frame))
        except queue.Full:
            pass

    def _writer_loop(self):
        """Background thread: write queued data to file."""
        while self._running:
            self._drain_queue()
            self._drain_frame_queue()
            time.sleep(self._flush_interval)

    def _drain_queue(self):
        """Write all queued items to file."""
        while True:
            try:
                item = self._queue.get_nowait()
                if self._file:
                    self._file.write(json.dumps(item, ensure_ascii=False) + "\n")
                    self._count += 1
            except queue.Empty:
                break
        if self._file and self._count >= 100:
            self._file.flush()
            self._count = 0

    def _drain_frame_queue(self):
        """Write all queued frames to video."""
        while True:
            try:
                _, frame = self._frame_queue.get_nowait()
                if self._video_writer:
                    self._video_writer.write(frame)
            except queue.Empty:
                break
        while True:
            try:
                _, frame = self._map_frame_queue.get_nowait()
                if self._map_video_writer:
                    self._map_video_writer.write(frame)
            except queue.Empty:
                break


class RecordingPlayer:
    """Playback recorded data."""

    def __init__(self, filepath: str):
        self._filepath = filepath
        if filepath.endswith(".jsonl"):
            self._jsonl_path = filepath
        else:
            self._jsonl_path = filepath + ".jsonl"

    def read_all(self) -> List[Dict]:
        """Read all recorded data."""
        records = []
        with open(self._jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def read_by_type(self, event_type: str) -> List[Dict]:
        """Read records of specific type."""
        records = []
        with open(self._jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    record = json.loads(line)
                    if record["type"] == event_type:
                        records.append(record)
        return records

    def read_time_range(self, start: float, end: float) -> List[Dict]:
        """Read records within time range."""
        records = []
        with open(self._jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    record = json.loads(line)
                    if start <= record["ts"] <= end:
                        records.append(record)
        return records

    def iter_records(self):
        """Iterate over records one by one."""
        with open(self._jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)

    def iter_video(self):
        """Iterate over video frames as (timestamp, frame) tuples.

        Yields frames synced with JSONL timestamps.
        """
        video_path = self._jsonl_path.replace(".jsonl", ".mp4")
        if not os.path.exists(video_path):
            return
        cap = cv2.VideoCapture(video_path)
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            ts = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            yield ts, frame
        cap.release()


# Global instance
recorder: Optional[AsyncRecorder] = None


def init_recorder(filepath: str) -> AsyncRecorder:
    """Initialize global recorder.

    Args:
        filepath: Path without extension, e.g. "logs/recording_20260517".
                  Will create .jsonl (events) + .mp4 (video).
    """
    global recorder
    jsonl_path = filepath if filepath.endswith(".jsonl") else filepath + ".jsonl"
    recorder = AsyncRecorder(jsonl_path)
    recorder.start()
    return recorder


def get_recorder() -> Optional[AsyncRecorder]:
    """Get global recorder instance."""
    return recorder


def play_recording(filepath: str) -> RecordingPlayer:
    """Create a player for recorded data."""
    return RecordingPlayer(filepath)
