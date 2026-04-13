#!/usr/bin/env bash
# Forcefully stop everything the JobTracker dev stack might have spawned.
#
# Handles the nasty case where a previous `npm run dev` was Ctrl-Z'd and left
# stopped (SIGSTOP'd) children squatting on ports 3000/8000/8200. SIGTERM to a
# stopped process is queued but never delivered, so we SIGCONT first, then
# SIGTERM, then SIGKILL anything still alive.
#
# Safe to run when nothing is running.
set -u

PORTS=(3000 8000 8200)
NAMES=(
    'concurrently.*next dev'
    'uv run chroma run'
    'uv run uvicorn src.main'
    'backend/.venv/bin/chroma'
    'node .*next-server'
)

thaw_and_term() {
    local pids="$1"
    [ -z "$pids" ] && return
    # shellcheck disable=SC2086
    kill -CONT $pids 2>/dev/null || true
    # shellcheck disable=SC2086
    kill -TERM $pids 2>/dev/null || true
}

hard_kill() {
    local pids="$1"
    [ -z "$pids" ] && return
    # shellcheck disable=SC2086
    kill -KILL $pids 2>/dev/null || true
}

echo "==> releasing dev ports..."
for port in "${PORTS[@]}"; do
    pids=$(lsof -ti ":$port" 2>/dev/null | tr '\n' ' ' || true)
    if [ -n "$pids" ]; then
        printf '  port %s held by: %s\n' "$port" "$pids"
        thaw_and_term "$pids"
    fi
done

sleep 0.5

for port in "${PORTS[@]}"; do
    pids=$(lsof -ti ":$port" 2>/dev/null | tr '\n' ' ' || true)
    if [ -n "$pids" ]; then
        printf '  hard-killing %s on port %s\n' "$pids" "$port"
        hard_kill "$pids"
    fi
done

echo "==> killing orphaned dev processes by name..."
for pattern in "${NAMES[@]}"; do
    pids=$(pgrep -f "$pattern" 2>/dev/null | tr '\n' ' ' || true)
    if [ -n "$pids" ]; then
        printf '  %s: %s\n' "$pattern" "$pids"
        thaw_and_term "$pids"
    fi
done

sleep 0.3

for pattern in "${NAMES[@]}"; do
    pids=$(pgrep -f "$pattern" 2>/dev/null | tr '\n' ' ' || true)
    if [ -n "$pids" ]; then
        hard_kill "$pids"
    fi
done

echo "==> remaining listeners on dev ports:"
remaining=$(ss -ltn 2>/dev/null | awk '/:3000 |:8000 |:8200 /')
if [ -n "$remaining" ]; then
    echo "$remaining"
    echo "!! something is still holding a port, manual cleanup needed"
    exit 1
fi
echo "  (none)"
echo "done."
