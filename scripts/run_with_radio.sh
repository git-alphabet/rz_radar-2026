#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT_DIR"

LOG_DIR="${LOG_DIR:-$ROOT_DIR/logs}"
mkdir -p "$LOG_DIR"

ENABLE_STREAM=true

for arg in "$@"; do
	case "$arg" in
		--stream)
			ENABLE_STREAM=true
			;;
		*)
			;;
	esac
done

ts=$(date +"%Y%m%d_%H%M%S")
RADIO_LOG="$LOG_DIR/radio_$ts.log"
STREAM_LOG="$LOG_DIR/stream_$ts.log"
MAIN_LOG="$LOG_DIR/main_$ts.log"

echo "Radio log: $RADIO_LOG"
if $ENABLE_STREAM; then
	echo "Stream log: $STREAM_LOG"
else
	echo "Stream log: disabled"
fi
echo "Main log: $MAIN_LOG"

RADIO_PID=""
STREAM_PID=""

python3 radio_py/radio.py >"$RADIO_LOG" 2>&1 &
RADIO_PID=$!

if $ENABLE_STREAM; then
	python3 radio_py/data_stream.py >"$STREAM_LOG" 2>&1 &
	STREAM_PID=$!
fi

cleanup() {
	container_id=$(docker compose -f docker/compose.dev.yml ps -q radar 2>/dev/null || true)
	if [[ -n "$container_id" ]]; then
		docker compose -f docker/compose.dev.yml exec -T radar bash -lc "pkill -f 'python3 main.py' || true" >/dev/null 2>&1 || true
	fi
	for pid in "$STREAM_PID" "$RADIO_PID"; do
		if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
			kill "$pid" 2>/dev/null || true
			wait "$pid" 2>/dev/null || true
		fi
	done
}

trap cleanup EXIT INT TERM

container_id=$(docker compose -f docker/compose.dev.yml ps -q radar)
if [[ -z "$container_id" ]]; then
	docker compose -f docker/compose.dev.yml up -d radar
fi

set -o pipefail
docker compose -f docker/compose.dev.yml exec -T radar python3 main.py | tee -a "$MAIN_LOG"