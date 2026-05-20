#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
modules = [
    "gnuradio",
    "gnuradio.iio",
    "PyQt5",
    "numpy",
]
for name in modules:
    try:
        __import__(name)
        print(f"OK {name}")
    except Exception as exc:
        print(f"FAIL {name}: {exc}")
PY
