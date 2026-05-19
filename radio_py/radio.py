#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Blue radar four-wave receiver
# GNU Radio version: 3.10.1.1

from packaging.version import Version as StrictVersion
import os

if __name__ == '__main__':
    import ctypes
    import sys
    if sys.platform.startswith('linux'):
        try:
            x11 = ctypes.cdll.LoadLibrary('libX11.so')
            x11.XInitThreads()
        except:
            print("Warning: failed to XInitThreads()")

from PyQt5 import Qt
from gnuradio import qtgui
from gnuradio.filter import firdes
import sip
from gnuradio import blocks
from gnuradio import digital
from gnuradio import filter
from gnuradio import gr
from gnuradio.fft import window
import sys
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio import iio
from gnuradio import network
import radio_epy_block_info as epy_block_info  # embedded python block
import radio_epy_block_jam1 as epy_block_jam1  # embedded python block
import radio_epy_block_jam2 as epy_block_jam2  # embedded python block
import radio_epy_block_jam3 as epy_block_jam3  # embedded python block



from gnuradio import qtgui

class radio(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "Blue radar four-wave receiver", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("Blue radar four-wave receiver")
        qtgui.util.check_set_qss()
        try:
            self.setWindowIcon(Qt.QIcon.fromTheme('gnuradio-grc'))
        except:
            pass
        self.top_scroll_layout = Qt.QVBoxLayout()
        self.setLayout(self.top_scroll_layout)
        self.top_scroll = Qt.QScrollArea()
        self.top_scroll.setFrameStyle(Qt.QFrame.NoFrame)
        self.top_scroll_layout.addWidget(self.top_scroll)
        self.top_scroll.setWidgetResizable(True)
        self.top_widget = Qt.QWidget()
        self.top_scroll.setWidget(self.top_widget)
        self.top_layout = Qt.QVBoxLayout(self.top_widget)
        self.top_grid_layout = Qt.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)

        self.settings = Qt.QSettings("GNU Radio", "radio")

        try:
            if StrictVersion(Qt.qVersion()) < StrictVersion("5.0.0"):
                self.restoreGeometry(self.settings.value("geometry").toByteArray())
            else:
                self.restoreGeometry(self.settings.value("geometry"))
        except:
            pass

        ##################################################
        # Variables
        ##################################################
        self.rx_center_freq = rx_center_freq = 434.520e6
        self.jam3_freq = jam3_freq = 434.320e6
        self.jam2_freq = jam2_freq = 434.620e6
        self.jam1_freq = jam1_freq = 434.920e6
        self.info_freq = info_freq = 433.920e6
        self.xlate_decim = xlate_decim = 4
        self.samp_rate = samp_rate = 4e6
        self.rx_rf_bandwidth = rx_rf_bandwidth = 2.0e6
        self.rx_jam_gain = rx_jam_gain = 50
        self.rx_info_gain = rx_info_gain = 35
        self.pluto_uri = pluto_uri = "ip:192.168.1.10"
        self.jam3_sensitivity = jam3_sensitivity = 0.6646
        self.jam3_offset = jam3_offset = jam3_freq - rx_center_freq
        self.jam3_cutoff = jam3_cutoff = 0.125e6
        self.jam2_sensitivity = jam2_sensitivity = 2.5809
        self.jam2_offset = jam2_offset = jam2_freq - rx_center_freq
        self.jam2_cutoff = jam2_cutoff = 0.43e6
        self.jam1_sensitivity = jam1_sensitivity = 2.8323
        self.jam1_offset = jam1_offset = jam1_freq - rx_center_freq
        self.jam1_cutoff = jam1_cutoff = 0.47e6
        self.info_sensitivity = info_sensitivity = 1.5756
        self.info_offset = info_offset = info_freq - rx_center_freq
        self.info_cutoff = info_cutoff = 0.27e6
        self.channel_transition = channel_transition = 20e3
        self.channel_samp_rate = channel_samp_rate = 1e6

        ##################################################
        # Blocks
        ##################################################
        self.qtgui_time_sink_x_0 = qtgui.time_sink_c(
            1024, #size
            samp_rate, #samp_rate
            "", #name
            1, #number of inputs
            None # parent
        )
        self.qtgui_time_sink_x_0.set_update_time(0.10)
        self.qtgui_time_sink_x_0.set_y_axis(-1, 1)

        self.qtgui_time_sink_x_0.set_y_label('Amplitude', "")

        self.qtgui_time_sink_x_0.enable_tags(True)
        self.qtgui_time_sink_x_0.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.qtgui_time_sink_x_0.enable_autoscale(False)
        self.qtgui_time_sink_x_0.enable_grid(False)
        self.qtgui_time_sink_x_0.enable_axis_labels(True)
        self.qtgui_time_sink_x_0.enable_control_panel(False)
        self.qtgui_time_sink_x_0.enable_stem_plot(False)


        labels = ['Signal 1', 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
            'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['blue', 'red', 'green', 'black', 'cyan',
            'magenta', 'yellow', 'dark red', 'dark green', 'dark blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [-1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(2):
            if len(labels[i]) == 0:
                if (i % 2 == 0):
                    self.qtgui_time_sink_x_0.set_line_label(i, "Re{{Data {0}}}".format(i/2))
                else:
                    self.qtgui_time_sink_x_0.set_line_label(i, "Im{{Data {0}}}".format(i/2))
            else:
                self.qtgui_time_sink_x_0.set_line_label(i, labels[i])
            self.qtgui_time_sink_x_0.set_line_width(i, widths[i])
            self.qtgui_time_sink_x_0.set_line_color(i, colors[i])
            self.qtgui_time_sink_x_0.set_line_style(i, styles[i])
            self.qtgui_time_sink_x_0.set_line_marker(i, markers[i])
            self.qtgui_time_sink_x_0.set_line_alpha(i, alphas[i])

        self._qtgui_time_sink_x_0_win = sip.wrapinstance(self.qtgui_time_sink_x_0.qwidget(), Qt.QWidget)
        self.top_layout.addWidget(self._qtgui_time_sink_x_0_win)
        self.network_udp_sink_jam3 = network.udp_sink(gr.sizeof_char, 1, '127.0.0.1', 55560, 0, 27, False)
        self.network_udp_sink_jam2 = network.udp_sink(gr.sizeof_char, 1, '127.0.0.1', 55559, 0, 27, False)
        self.network_udp_sink_jam1 = network.udp_sink(gr.sizeof_char, 1, '127.0.0.1', 55558, 0, 27, False)
        self.network_udp_sink_info = network.udp_sink(gr.sizeof_char, 1, '127.0.0.1', 55557, 0, 27, False)
        self.iio_fmcomms2_source_0 = iio.fmcomms2_source_fc32(pluto_uri, [True, True, True, True], 32768)
        self.iio_fmcomms2_source_0.set_len_tag_key('packet_len')
        self.iio_fmcomms2_source_0.set_frequency(int(rx_center_freq))
        self.iio_fmcomms2_source_0.set_samplerate(int(samp_rate))
        if True:
            self.iio_fmcomms2_source_0.set_gain_mode(0, 'manual')
            self.iio_fmcomms2_source_0.set_gain(0, rx_info_gain)
        if True:
            self.iio_fmcomms2_source_0.set_gain_mode(1, 'manual')
            self.iio_fmcomms2_source_0.set_gain(1, rx_jam_gain)
        self.iio_fmcomms2_source_0.set_quadrature(True)
        self.iio_fmcomms2_source_0.set_rfdc(False)
        self.iio_fmcomms2_source_0.set_bbdc(True)
        self.iio_fmcomms2_source_0.set_filter_params('Design', '', 0.95e6, 1.10e6)
        self.freq_xlating_fir_filter_jam3 = filter.freq_xlating_fir_filter_ccf(xlate_decim, firdes.low_pass(1, samp_rate, jam3_cutoff, channel_transition, window.WIN_HAMMING, 6.76), jam3_offset, samp_rate)
        self.freq_xlating_fir_filter_jam2 = filter.freq_xlating_fir_filter_ccf(xlate_decim, firdes.low_pass(1, samp_rate, jam2_cutoff, channel_transition, window.WIN_HAMMING, 6.76), jam2_offset, samp_rate)
        self.freq_xlating_fir_filter_jam1 = filter.freq_xlating_fir_filter_ccf(xlate_decim, firdes.low_pass(1, samp_rate, jam1_cutoff, channel_transition, window.WIN_HAMMING, 6.76), jam1_offset, samp_rate)
        self.freq_xlating_fir_filter_info = filter.freq_xlating_fir_filter_ccf(xlate_decim, firdes.low_pass(1, samp_rate, info_cutoff, channel_transition, window.WIN_HAMMING, 6.76), info_offset, samp_rate)
        self.epy_block_jam3 = epy_block_jam3.AccessCodeBitFrameExtractor(access_code_hex="16E8D377151C712D", header_hex="000F000F", frame_bytes=27, bit_order="msb", output_mode="bits")
        self.epy_block_jam2 = epy_block_jam2.AccessCodeBitFrameExtractor(access_code_hex="16E8D377151C712D", header_hex="000F000F", frame_bytes=27, bit_order="msb", output_mode="bits")
        self.epy_block_jam1 = epy_block_jam1.AccessCodeBitFrameExtractor(access_code_hex="16E8D377151C712D", header_hex="000F000F", frame_bytes=27, bit_order="msb", output_mode="bits")
        self.epy_block_info = epy_block_info.AccessCodeBitFrameExtractor(access_code_hex="2F6F4C74B914492E", header_hex="000F000F", frame_bytes=27, bit_order="msb", output_mode="bits")
        self.digital_gfsk_demod_jam3 = digital.gfsk_demod(
            samples_per_symbol=52,
            sensitivity=jam3_sensitivity,
            gain_mu=0.175,
            mu=0.5,
            omega_relative_limit=0.005,
            freq_error=0.0,
            verbose=False,
            log=False)
        self.digital_gfsk_demod_jam2 = digital.gfsk_demod(
            samples_per_symbol=52,
            sensitivity=jam2_sensitivity,
            gain_mu=0.175,
            mu=0.5,
            omega_relative_limit=0.005,
            freq_error=0.0,
            verbose=False,
            log=False)
        self.digital_gfsk_demod_jam1 = digital.gfsk_demod(
            samples_per_symbol=52,
            sensitivity=jam1_sensitivity,
            gain_mu=0.175,
            mu=0.5,
            omega_relative_limit=0.005,
            freq_error=0.0,
            verbose=False,
            log=False)
        self.digital_gfsk_demod_info = digital.gfsk_demod(
            samples_per_symbol=52,
            sensitivity=info_sensitivity,
            gain_mu=0.175,
            mu=0.5,
            omega_relative_limit=0.005,
            freq_error=0.0,
            verbose=False,
            log=False)
        self.digital_correlate_access_code_tag_xx_jam3 = digital.correlate_access_code_tag_bb('0001011011101000110100110111011100010101000111000111000100101101', 2, "frame_start")
        self.digital_correlate_access_code_tag_xx_jam2 = digital.correlate_access_code_tag_bb('0001011011101000110100110111011100010101000111000111000100101101', 2, "frame_start")
        self.digital_correlate_access_code_tag_xx_jam1 = digital.correlate_access_code_tag_bb('0001011011101000110100110111011100010101000111000111000100101101', 2, "frame_start")
        self.digital_correlate_access_code_tag_xx_info = digital.correlate_access_code_tag_bb('0010111101101111010011000111010010111001000101000100100100101110', 2, "frame_start")
        self.blocks_repack_bits_bb_jam3 = blocks.repack_bits_bb(1, 8, "", False, gr.GR_MSB_FIRST)
        self.blocks_repack_bits_bb_jam2 = blocks.repack_bits_bb(1, 8, "", False, gr.GR_MSB_FIRST)
        self.blocks_repack_bits_bb_jam1 = blocks.repack_bits_bb(1, 8, "", False, gr.GR_MSB_FIRST)
        self.blocks_repack_bits_bb_info = blocks.repack_bits_bb(1, 8, "", False, gr.GR_MSB_FIRST)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.blocks_repack_bits_bb_info, 0), (self.network_udp_sink_info, 0))
        self.connect((self.blocks_repack_bits_bb_jam1, 0), (self.network_udp_sink_jam1, 0))
        self.connect((self.blocks_repack_bits_bb_jam2, 0), (self.network_udp_sink_jam2, 0))
        self.connect((self.blocks_repack_bits_bb_jam3, 0), (self.network_udp_sink_jam3, 0))
        self.connect((self.digital_correlate_access_code_tag_xx_info, 0), (self.epy_block_info, 0))
        self.connect((self.digital_correlate_access_code_tag_xx_jam1, 0), (self.epy_block_jam1, 0))
        self.connect((self.digital_correlate_access_code_tag_xx_jam2, 0), (self.epy_block_jam2, 0))
        self.connect((self.digital_correlate_access_code_tag_xx_jam3, 0), (self.epy_block_jam3, 0))
        self.connect((self.digital_gfsk_demod_info, 0), (self.digital_correlate_access_code_tag_xx_info, 0))
        self.connect((self.digital_gfsk_demod_jam1, 0), (self.digital_correlate_access_code_tag_xx_jam1, 0))
        self.connect((self.digital_gfsk_demod_jam2, 0), (self.digital_correlate_access_code_tag_xx_jam2, 0))
        self.connect((self.digital_gfsk_demod_jam3, 0), (self.digital_correlate_access_code_tag_xx_jam3, 0))
        self.connect((self.epy_block_info, 0), (self.blocks_repack_bits_bb_info, 0))
        self.connect((self.epy_block_jam1, 0), (self.blocks_repack_bits_bb_jam1, 0))
        self.connect((self.epy_block_jam2, 0), (self.blocks_repack_bits_bb_jam2, 0))
        self.connect((self.epy_block_jam3, 0), (self.blocks_repack_bits_bb_jam3, 0))
        self.connect((self.freq_xlating_fir_filter_info, 0), (self.digital_gfsk_demod_info, 0))
        self.connect((self.freq_xlating_fir_filter_info, 0), (self.qtgui_time_sink_x_0, 0))
        self.connect((self.freq_xlating_fir_filter_jam1, 0), (self.digital_gfsk_demod_jam1, 0))
        self.connect((self.freq_xlating_fir_filter_jam2, 0), (self.digital_gfsk_demod_jam2, 0))
        self.connect((self.freq_xlating_fir_filter_jam3, 0), (self.digital_gfsk_demod_jam3, 0))
        self.connect((self.iio_fmcomms2_source_0, 0), (self.freq_xlating_fir_filter_info, 0))
        self.connect((self.iio_fmcomms2_source_0, 1), (self.freq_xlating_fir_filter_jam1, 0))
        self.connect((self.iio_fmcomms2_source_0, 1), (self.freq_xlating_fir_filter_jam2, 0))
        self.connect((self.iio_fmcomms2_source_0, 1), (self.freq_xlating_fir_filter_jam3, 0))



        # IQ raw recording (set RECORD_IQ=1 to enable)
        if os.environ.get("RECORD_IQ", "0") == "1":
            import datetime
            iq_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bags")
            os.makedirs(iq_dir, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            iq_path = os.path.join(iq_dir, f"iq_raw_{ts}.cf32")
            self.iq_file_sink = blocks.file_sink(gr.sizeof_gr_complex, iq_path, False)
            self.iq_file_sink.set_unbuffered(False)
            self.connect((self.iio_fmcomms2_source_0, 0), (self.iq_file_sink, 0))
            self.iq_file_sink_1 = blocks.file_sink(gr.sizeof_gr_complex, iq_path.replace('.cf32', '_1.cf32'), False)
            self.iq_file_sink_1.set_unbuffered(False)
            self.connect((self.iio_fmcomms2_source_0, 1), (self.iq_file_sink_1, 0))
            print(f"IQ recording: {iq_path} AND ..._1.cf32 (complex64, {int(self.samp_rate/1e3)}kHz)")

    def closeEvent(self, event):
        self.settings = Qt.QSettings("GNU Radio", "radio")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_rx_center_freq(self):
        return self.rx_center_freq

    def set_rx_center_freq(self, rx_center_freq):
        self.rx_center_freq = rx_center_freq
        self.set_info_offset(self.info_freq - self.rx_center_freq)
        self.set_jam1_offset(self.jam1_freq - self.rx_center_freq)
        self.set_jam2_offset(self.jam2_freq - self.rx_center_freq)
        self.set_jam3_offset(self.jam3_freq - self.rx_center_freq)
        self.iio_fmcomms2_source_0.set_frequency(int(self.rx_center_freq))

    def get_jam3_freq(self):
        return self.jam3_freq

    def set_jam3_freq(self, jam3_freq):
        self.jam3_freq = jam3_freq
        self.set_jam3_offset(self.jam3_freq - self.rx_center_freq)

    def get_jam2_freq(self):
        return self.jam2_freq

    def set_jam2_freq(self, jam2_freq):
        self.jam2_freq = jam2_freq
        self.set_jam2_offset(self.jam2_freq - self.rx_center_freq)

    def get_jam1_freq(self):
        return self.jam1_freq

    def set_jam1_freq(self, jam1_freq):
        self.jam1_freq = jam1_freq
        self.set_jam1_offset(self.jam1_freq - self.rx_center_freq)

    def get_info_freq(self):
        return self.info_freq

    def set_info_freq(self, info_freq):
        self.info_freq = info_freq
        self.set_info_offset(self.info_freq - self.rx_center_freq)

    def get_xlate_decim(self):
        return self.xlate_decim

    def set_xlate_decim(self, xlate_decim):
        self.xlate_decim = xlate_decim

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.freq_xlating_fir_filter_info.set_taps(firdes.low_pass(1, self.samp_rate, self.info_cutoff, self.channel_transition, window.WIN_HAMMING, 6.76))
        self.freq_xlating_fir_filter_jam1.set_taps(firdes.low_pass(1, self.samp_rate, self.jam1_cutoff, self.channel_transition, window.WIN_HAMMING, 6.76))
        self.freq_xlating_fir_filter_jam2.set_taps(firdes.low_pass(1, self.samp_rate, self.jam2_cutoff, self.channel_transition, window.WIN_HAMMING, 6.76))
        self.freq_xlating_fir_filter_jam3.set_taps(firdes.low_pass(1, self.samp_rate, self.jam3_cutoff, self.channel_transition, window.WIN_HAMMING, 6.76))
        self.iio_fmcomms2_source_0.set_samplerate(int(self.samp_rate))
        self.qtgui_time_sink_x_0.set_samp_rate(self.samp_rate)

    def get_rx_rf_bandwidth(self):
        return self.rx_rf_bandwidth

    def set_rx_rf_bandwidth(self, rx_rf_bandwidth):
        self.rx_rf_bandwidth = rx_rf_bandwidth

    def get_rx_jam_gain(self):
        return self.rx_jam_gain

    def set_rx_jam_gain(self, rx_jam_gain):
        self.rx_jam_gain = rx_jam_gain
        self.iio_fmcomms2_source_0.set_gain(1, self.rx_jam_gain)

    def get_rx_info_gain(self):
        return self.rx_info_gain

    def set_rx_info_gain(self, rx_info_gain):
        self.rx_info_gain = rx_info_gain
        self.iio_fmcomms2_source_0.set_gain(0, self.rx_info_gain)

    def get_pluto_uri(self):
        return self.pluto_uri

    def set_pluto_uri(self, pluto_uri):
        self.pluto_uri = pluto_uri

    def get_jam3_sensitivity(self):
        return self.jam3_sensitivity

    def set_jam3_sensitivity(self, jam3_sensitivity):
        self.jam3_sensitivity = jam3_sensitivity

    def get_jam3_offset(self):
        return self.jam3_offset

    def set_jam3_offset(self, jam3_offset):
        self.jam3_offset = jam3_offset
        self.freq_xlating_fir_filter_jam3.set_center_freq(self.jam3_offset)

    def get_jam3_cutoff(self):
        return self.jam3_cutoff

    def set_jam3_cutoff(self, jam3_cutoff):
        self.jam3_cutoff = jam3_cutoff
        self.freq_xlating_fir_filter_jam3.set_taps(firdes.low_pass(1, self.samp_rate, self.jam3_cutoff, self.channel_transition, window.WIN_HAMMING, 6.76))

    def get_jam2_sensitivity(self):
        return self.jam2_sensitivity

    def set_jam2_sensitivity(self, jam2_sensitivity):
        self.jam2_sensitivity = jam2_sensitivity

    def get_jam2_offset(self):
        return self.jam2_offset

    def set_jam2_offset(self, jam2_offset):
        self.jam2_offset = jam2_offset
        self.freq_xlating_fir_filter_jam2.set_center_freq(self.jam2_offset)

    def get_jam2_cutoff(self):
        return self.jam2_cutoff

    def set_jam2_cutoff(self, jam2_cutoff):
        self.jam2_cutoff = jam2_cutoff
        self.freq_xlating_fir_filter_jam2.set_taps(firdes.low_pass(1, self.samp_rate, self.jam2_cutoff, self.channel_transition, window.WIN_HAMMING, 6.76))

    def get_jam1_sensitivity(self):
        return self.jam1_sensitivity

    def set_jam1_sensitivity(self, jam1_sensitivity):
        self.jam1_sensitivity = jam1_sensitivity

    def get_jam1_offset(self):
        return self.jam1_offset

    def set_jam1_offset(self, jam1_offset):
        self.jam1_offset = jam1_offset
        self.freq_xlating_fir_filter_jam1.set_center_freq(self.jam1_offset)

    def get_jam1_cutoff(self):
        return self.jam1_cutoff

    def set_jam1_cutoff(self, jam1_cutoff):
        self.jam1_cutoff = jam1_cutoff
        self.freq_xlating_fir_filter_jam1.set_taps(firdes.low_pass(1, self.samp_rate, self.jam1_cutoff, self.channel_transition, window.WIN_HAMMING, 6.76))

    def get_info_sensitivity(self):
        return self.info_sensitivity

    def set_info_sensitivity(self, info_sensitivity):
        self.info_sensitivity = info_sensitivity

    def get_info_offset(self):
        return self.info_offset

    def set_info_offset(self, info_offset):
        self.info_offset = info_offset
        self.freq_xlating_fir_filter_info.set_center_freq(self.info_offset)

    def get_info_cutoff(self):
        return self.info_cutoff

    def set_info_cutoff(self, info_cutoff):
        self.info_cutoff = info_cutoff
        self.freq_xlating_fir_filter_info.set_taps(firdes.low_pass(1, self.samp_rate, self.info_cutoff, self.channel_transition, window.WIN_HAMMING, 6.76))

    def get_channel_transition(self):
        return self.channel_transition

    def set_channel_transition(self, channel_transition):
        self.channel_transition = channel_transition
        self.freq_xlating_fir_filter_info.set_taps(firdes.low_pass(1, self.samp_rate, self.info_cutoff, self.channel_transition, window.WIN_HAMMING, 6.76))
        self.freq_xlating_fir_filter_jam1.set_taps(firdes.low_pass(1, self.samp_rate, self.jam1_cutoff, self.channel_transition, window.WIN_HAMMING, 6.76))
        self.freq_xlating_fir_filter_jam2.set_taps(firdes.low_pass(1, self.samp_rate, self.jam2_cutoff, self.channel_transition, window.WIN_HAMMING, 6.76))
        self.freq_xlating_fir_filter_jam3.set_taps(firdes.low_pass(1, self.samp_rate, self.jam3_cutoff, self.channel_transition, window.WIN_HAMMING, 6.76))

    def get_channel_samp_rate(self):
        return self.channel_samp_rate

    def set_channel_samp_rate(self, channel_samp_rate):
        self.channel_samp_rate = channel_samp_rate




def main(top_block_cls=radio, options=None):

    if StrictVersion("4.5.0") <= StrictVersion(Qt.qVersion()) < StrictVersion("5.0.0"):
        style = gr.prefs().get_string('qtgui', 'style', 'raster')
        Qt.QApplication.setGraphicsSystem(style)
    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls()

    tb.start()

    tb.show()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        Qt.QApplication.quit()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    timer = Qt.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    qapp.exec_()

if __name__ == '__main__':
    main()
