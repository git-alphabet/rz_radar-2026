import os
import sys

_module_file = globals().get(
    "__file__",
    os.path.join(os.getcwd(), "radio_epy_block_jam1.py"),
)
_module_dir = os.path.dirname(os.path.abspath(_module_file))
if _module_dir not in sys.path:
    sys.path.insert(0, _module_dir)

from gr_air_frame_extractor import AccessCodeBitFrameExtractor
