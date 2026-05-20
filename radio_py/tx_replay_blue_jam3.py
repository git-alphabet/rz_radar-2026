#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Blue level-3 jamming replay transmitter
# GNU Radio version: 3.10.12.0

from gnuradio import blocks
import pmt
from gnuradio import gr
from gnuradio.filter import firdes
from gnuradio.fft import window
import os
import sys
import signal
import time
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio import iio
import threading




class tx_replay_blue_jam3(gr.top_block):

    def __init__(
        self,
        recording_path="C:/Users/GMD777/Desktop/radio_py/RX_BLUE_ganrao_3",
        tx_attenuation=10.0,
        tx_scale=1.0,
        tx_rf_bandwidth=1.0e6,
        tx_center_freq=434.320e6,
        samp_rate=2e6,
        pluto_uri="ip:192.168.1.10",
        tx2=False,
    ):
        gr.top_block.__init__(self, "Blue level-3 jamming replay transmitter", catch_exceptions=True)
        self.flowgraph_started = threading.Event()

        ##################################################
        # Variables
        ##################################################
        self.tx2 = tx2
        self.tx_scale = tx_scale = float(tx_scale)
        self.tx_rf_bandwidth = tx_rf_bandwidth = float(tx_rf_bandwidth)
        self.tx_center_freq = tx_center_freq = float(tx_center_freq)
        self.tx_attenuation = tx_attenuation = float(tx_attenuation)
        self.samp_rate = samp_rate = float(samp_rate)
        self.recording_path = recording_path = os.path.abspath(recording_path)
        self.pluto_uri = pluto_uri = str(pluto_uri)
        if not os.path.isfile(recording_path):
            raise FileNotFoundError(f"recording file not found: {recording_path}")

        ##################################################
        # Blocks
        ##################################################

        enabled_channels = [False, False, True, True] if tx2 else [True, True, False, False]
        self.iio_fmcomms2_sink_0 = iio.fmcomms2_sink_fc32(pluto_uri, enabled_channels, 32768, False)
        self.iio_fmcomms2_sink_0.set_len_tag_key("")
        self.iio_fmcomms2_sink_0.set_bandwidth(int(tx_rf_bandwidth))
        self.iio_fmcomms2_sink_0.set_frequency(int(tx_center_freq))
        self.iio_fmcomms2_sink_0.set_samplerate(int(samp_rate))
        try:
            self.iio_fmcomms2_sink_0.set_attenuation(0, tx_attenuation)
            self.iio_fmcomms2_sink_0.set_attenuation(1, tx_attenuation)
        except Exception:
            self.iio_fmcomms2_sink_0.set_attenuation(0 if not tx2 else 1, tx_attenuation)
        self.iio_fmcomms2_sink_0.set_filter_params('Design', '', 0.45e6, 0.60e6)
        self.blocks_multiply_const_vxx_0 = blocks.multiply_const_cc(tx_scale)
        self.blocks_file_source_0 = blocks.file_source(gr.sizeof_gr_complex*1, recording_path, True, 0, 0)
        self.blocks_file_source_0.set_begin_tag(pmt.PMT_NIL)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.blocks_file_source_0, 0), (self.blocks_multiply_const_vxx_0, 0))
        self.connect((self.blocks_multiply_const_vxx_0, 0), (self.iio_fmcomms2_sink_0, 0))


    def get_tx_scale(self):
        return self.tx_scale

    def set_tx_scale(self, tx_scale):
        self.tx_scale = tx_scale
        self.blocks_multiply_const_vxx_0.set_k(self.tx_scale)

    def get_tx_rf_bandwidth(self):
        return self.tx_rf_bandwidth

    def set_tx_rf_bandwidth(self, tx_rf_bandwidth):
        self.tx_rf_bandwidth = tx_rf_bandwidth
        self.iio_fmcomms2_sink_0.set_bandwidth(int(self.tx_rf_bandwidth))

    def get_tx_center_freq(self):
        return self.tx_center_freq

    def set_tx_center_freq(self, tx_center_freq):
        self.tx_center_freq = tx_center_freq
        self.iio_fmcomms2_sink_0.set_frequency(int(self.tx_center_freq))

    def get_tx_attenuation(self):
        return self.tx_attenuation

    def set_tx_attenuation(self, tx_attenuation):
        self.tx_attenuation = tx_attenuation
        self.iio_fmcomms2_sink_0.set_attenuation(0, self.tx_attenuation)
        self.iio_fmcomms2_sink_0.set_attenuation(1, self.tx_attenuation)

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.iio_fmcomms2_sink_0.set_samplerate(int(self.samp_rate))

    def get_recording_path(self):
        return self.recording_path

    def set_recording_path(self, recording_path):
        self.recording_path = recording_path
        self.blocks_file_source_0.open(self.recording_path, True)

    def get_pluto_uri(self):
        return self.pluto_uri

    def set_pluto_uri(self, pluto_uri):
        self.pluto_uri = pluto_uri




def main(top_block_cls=tx_replay_blue_jam3, options=None):
    parser = ArgumentParser(description="Replay RX_BLUE_ganrao_3 on the blue level-3 jam frequency.")
    parser.add_argument("--recording", default="C:/Users/GMD777/Desktop/radio_py/RX_BLUE_ganrao_3")
    parser.add_argument("--attenuation", type=float, default=10.0, help="TX attenuation in dB; lower means stronger.")
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--bandwidth", type=float, default=1.0e6)
    parser.add_argument("--center-freq", type=float, default=434.320e6)
    parser.add_argument("--samp-rate", type=float, default=2e6)
    parser.add_argument("--uri", default="ip:192.168.1.10")
    parser.add_argument("--tx2", action="store_true", help="Transmit on TX2 instead of TX1.")
    parser.add_argument("--duration", type=float, default=0.0, help="Seconds to run; 0 waits for Enter.")
    args = parser.parse_args()

    tb = top_block_cls(
        recording_path=args.recording,
        tx_attenuation=args.attenuation,
        tx_scale=args.scale,
        tx_rf_bandwidth=args.bandwidth,
        tx_center_freq=args.center_freq,
        samp_rate=args.samp_rate,
        pluto_uri=args.uri,
        tx2=args.tx2,
    )

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    tb.start()
    tb.flowgraph_started.set()
    print(
        "TX replay running: "
        f"file={tb.recording_path} freq={tb.tx_center_freq/1e6:.3f}MHz "
        f"samp_rate={tb.samp_rate/1e6:.3f}MS/s attenuation={tb.tx_attenuation:.1f}dB "
        f"bandwidth={tb.tx_rf_bandwidth/1e6:.3f}MHz channel={'TX2' if tb.tx2 else 'TX1'}"
    )

    if args.duration > 0:
        time.sleep(args.duration)
    else:
        try:
            input('Press Enter to quit: ')
        except EOFError:
            pass
    tb.stop()
    tb.wait()


if __name__ == '__main__':
    main()
