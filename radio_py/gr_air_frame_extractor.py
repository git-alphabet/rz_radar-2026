import numpy as np
from gnuradio import gr
import pmt


class AccessCodeBitFrameExtractor(gr.basic_block):
    def __init__(self):
        gr.basic_block.__init__(
            self,
            name="Access Code Bit Frame Extractor",
            in_sig=[np.uint8],
            out_sig=[np.uint8],
        )
        self.set_tag_propagation_policy(gr.TPP_DONT)

        self.access_bits = self._bytes_to_bits(bytes.fromhex("2F6F4C74B914492E"))
        self.header_bits = self._bytes_to_bits(bytes.fromhex("000F000F"))
        self.prefix_bits = np.concatenate((self.access_bits, self.header_bits))
        self.frame_bits = 27 * 8
        self.set_min_noutput_items(self.frame_bits)
        self.set_output_multiple(self.frame_bits)
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
    def _bytes_to_bits(data):
        bits = []
        for byte in data:
            for shift in range(7, -1, -1):
                bits.append((byte >> shift) & 1)
        return np.array(bits, dtype=np.uint8)

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
                output_frames.append(frame)
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
