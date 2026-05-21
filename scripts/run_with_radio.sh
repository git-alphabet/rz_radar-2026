#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT_DIR"

LOG_DIR="${LOG_DIR:-$ROOT_DIR/logs}"
mkdir -p "$LOG_DIR"

ts=$(TZ=Asia/Shanghai date +"%Y%m%d_%H%M")
RADIO_LOG="$LOG_DIR/radio_$ts.log"
MAIN_LOG="$LOG_DIR/main_$ts.log"

# Read record_iq from config.yaml
_record_iq=$(python3 -c "import yaml; print(yaml.safe_load(open('config.yaml'))['global'].get('record_iq', False))" 2>/dev/null || echo "False")
export RECORD_IQ=$([ "$_record_iq" = "True" ] && echo "1" || echo "0")

echo "Radio log: $RADIO_LOG"
echo "Main log: $MAIN_LOG"

RADIO_PID=""
PARSER_PID=""

python3 radar_field_blue_linux/radio.py >"$RADIO_LOG" 2>&1 &
RADIO_PID=$!
sleep 1

PARSER_LOG="$LOG_DIR/field_parse_$ts.log"
python3 radar_field_blue_linux/field_parse.py >"$PARSER_LOG" 2>&1 &
PARSER_PID=$!
echo "Field parse log: $PARSER_LOG"

all_local_dead() {
	for pid in "$PARSER_PID" "$RADIO_PID"; do
		if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
			return 1
		fi
	done
	return 0
}

cleanup() {
	echo -e "\nShutting down all started processes..."

	# Send SIGTERM to all local processes at once
	for pid in "$PARSER_PID" "$RADIO_PID"; do
		if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
			kill "$pid" 2>/dev/null || true
		fi
	done

	# Graceful stop main.py in container (SIGTERM first, then SIGKILL)
	container_id=$(docker compose -f docker/compose.dev.yml ps -q radar 2>/dev/null || true)
	if [[ -n "$container_id" ]]; then
		(docker compose -f docker/compose.dev.yml exec -T radar bash -lc "
			pkill -2 -f 'python3 main.py' || true
			for i in \$(seq 1 10); do
				pgrep -f 'python3 main.py' >/dev/null 2>&1 || exit 0
				sleep 0.1
			done
			pkill -9 -f 'python3 main.py' || true
		" >/dev/null 2>&1 || true) &
	fi

	# Poll until all local processes exit, up to 3 seconds
	for i in $(seq 1 30); do
		all_local_dead && break
		sleep 0.1
	done

	# Force kill any stragglers
	for pid in "$PARSER_PID" "$RADIO_PID"; do
		if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
			kill -9 "$pid" 2>/dev/null || true
		fi
	done

	wait
}

trap cleanup EXIT INT TERM

container_id=$(docker compose -f docker/compose.dev.yml ps -q radar 2>/dev/null || true)
if [[ -z "$container_id" ]]; then
	docker compose -f docker/compose.dev.yml up -d radar
fi

# SKIP_RADIO_GR=1: radio runs on host via radar_field_blue_linux/radio.py,
# skip the radio thread inside the container to avoid conflicts.
docker compose -f docker/compose.dev.yml exec -T radar bash -lc "SKIP_RADIO_GR=1 python3 main.py" | tee -a "$MAIN_LOG"
