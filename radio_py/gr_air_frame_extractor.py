import numpy as np
from gnuradio import gr
import pmt


class AccessCodeBitFrameExtractor(gr.basic_block):
    def __init__(
        self,
        access_code_hex="2F6F4C74B914492E",
        header_hex="000F000F",
        frame_bytes=27,
        bit_order="msb",
        output_mode="bits",
    ):
        gr.basic_block.__init__(
            self,
            name="Access Code Bit Frame Extractor",
            in_sig=[np.uint8],
            out_sig=[np.uint8],
        )
        self.set_tag_propagation_policy(gr.TPP_DONT)

        self.bit_order = self._normalize_choice(bit_order, "bit_order", ("msb", "lsb"))
        self.output_mode = self._normalize_choice(
            output_mode, "output_mode", ("bits", "bytes")
        )
        self.frame_bytes = int(frame_bytes)
        if self.frame_bytes <= 0:
            raise ValueError("frame_bytes must be positive")

        self.access_bits = self._bytes_to_bits(
            bytes.fromhex(self._normalize_hex(access_code_hex))
        )
        self.header_bits = self._bytes_to_bits(
            bytes.fromhex(self._normalize_hex(header_hex))
        )
        self.prefix_bits = np.concatenate((self.access_bits, self.header_bits))
        self.frame_bits = self.frame_bytes * 8
        if len(self.prefix_bits) > self.frame_bits:
            raise ValueError("access_code_hex plus header_hex is longer than frame_bytes")
        self.output_items_per_frame = (
            self.frame_bits if self.output_mode == "bits" else self.frame_bytes
        )
        self.set_min_noutput_items(self.output_items_per_frame)
        self.set_output_multiple(self.output_items_per_frame)
        self.access_len = len(self.access_bits)
        self.header_start = self.access_len
        self.header_end = self.header_start + len(self.header_bits)

        self.max_access_errors = 2
        self.max_header_errors = 2
        self.search_radius = 4
        self.tag_key = pmt.intern("frame_start")

        self.buffer = np.empty(0, dtype=np.uint8)
        self.base_offset = 0
        self.candidates = []
        self.pending = np.empty(0, dtype=np.uint8)
        self.last_output_start = -self.frame_bits

    @staticmethod
    def _normalize_choice(value, name, allowed):
        normalized = str(value).strip().lower()
        if normalized not in allowed:
            raise ValueError("{} must be one of {}".format(name, ", ".join(allowed)))
        return normalized

    @staticmethod
    def _normalize_hex(value):
        text = str(value).strip().replace(" ", "").replace("_", "")
        if text.lower().startswith("0x"):
            text = text[2:]
        if len(text) % 2:
            raise ValueError("hex strings must contain a whole number of bytes")
        return text

    def _bytes_to_bits(self, data):
        bits = []
        for byte in data:
            shifts = range(7, -1, -1) if self.bit_order == "msb" else range(8)
            for shift in shifts:
                bits.append((byte >> shift) & 1)
        return np.array(bits, dtype=np.uint8)

    def _bits_to_bytes(self, bits):
        packed = np.empty(len(bits) // 8, dtype=np.uint8)
        for idx in range(len(packed)):
            value = 0
            chunk = bits[idx * 8:(idx + 1) * 8]
            if self.bit_order == "msb":
                for bit in chunk:
                    value = (value << 1) | int(bit)
            else:
                for shift, bit in enumerate(chunk):
                    value |= int(bit) << shift
            packed[idx] = value
        return packed

    def _hamming(self, abs_start, pattern):
        rel = abs_start - self.base_offset
        end = rel + len(pattern)
        if rel < 0 or end > len(self.buffer):
            return None
        return int(np.count_nonzero(self.buffer[rel:end] != pattern))

    def _add_candidate_from_tag(self, tag_offset):
        hint = int(tag_offset) - self.access_len
        best_start = None
        best_errors = self.max_access_errors + 1

        for start in range(hint - self.search_radius, hint + self.search_radius + 1):
            errors = self._hamming(start, self.access_bits)
            if errors is None or errors > self.max_access_errors:
                continue
            if errors < best_errors:
                best_start = start
                best_errors = errors

        if best_start is None:
            return
        if best_start <= self.last_output_start:
            return
        if best_start not in self.candidates:
            self.candidates.append(best_start)
            self.candidates.sort()

    def _extract_ready_frames(self):
        if not self.candidates:
            return

        abs_end = self.base_offset + len(self.buffer)
        remaining = []
        output_frames = []

        for start in self.candidates:
            if start < self.base_offset:
                continue
            if start + self.frame_bits > abs_end:
                remaining.append(start)
                continue

            rel = start - self.base_offset
            frame = self.buffer[rel:rel + self.frame_bits].copy()
            header_errors = int(np.count_nonzero(
                frame[self.header_start:self.header_end] != self.header_bits
            ))
            if header_errors <= self.max_header_errors:
                frame[:len(self.prefix_bits)] = self.prefix_bits
                if self.output_mode == "bits":
                    output_frames.append(frame)
                else:
                    output_frames.append(self._bits_to_bytes(frame))
                self.last_output_start = start

        self.candidates = remaining
        if output_frames:
            new_bits = np.concatenate(output_frames).astype(np.uint8, copy=False)
            self.pending = np.concatenate((self.pending, new_bits))

    def _prune_buffer(self):
        abs_end = self.base_offset + len(self.buffer)
        if self.candidates:
            keep_from = min(self.candidates)
        else:
            keep_from = abs_end - max(self.frame_bits * 2, 512)

        keep_from = max(self.base_offset, keep_from)
        drop = keep_from - self.base_offset
        if drop > 0:
            self.buffer = self.buffer[drop:]
            self.base_offset = keep_from

    def general_work(self, input_items, output_items):
        data = input_items[0]
        out = output_items[0]

        if len(data):
            tags = self.get_tags_in_window(0, 0, len(data))

            bits = np.asarray(data, dtype=np.uint8) & 1
            self.buffer = np.concatenate((self.buffer, bits))

            for tag in tags:
                if pmt.equal(tag.key, self.tag_key):
                    self._add_candidate_from_tag(tag.offset)

            self._extract_ready_frames()
            self._prune_buffer()
            self.consume(0, len(data))

        nout = min(len(out), len(self.pending))
        if nout:
            out[:nout] = self.pending[:nout]
            self.pending = self.pending[nout:]

        return nout
