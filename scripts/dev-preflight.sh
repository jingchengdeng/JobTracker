#!/usr/bin/env bash
# Fail-fast preflight for `npm run dev`: refuse to start if any of the dev
# ports (3000 next, 8000 uvicorn, 8200 chroma) is already bound.
#
# Without this, concurrently silently gives up on a conflicting slot and the
# resulting dev session is subtly broken -- e.g. a frozen chroma keeps 8200
# and the resume pipeline hangs hours later with no visible error.
set -u

PORTS=(3000 8000 8200)
held=()

for port in "${PORTS[@]}"; do
    if lsof -ti ":$port" >/dev/null 2>&1; then
        held+=("$port")
    fi
done

if [ ${#held[@]} -eq 0 ]; then
    exit 0
fi

echo "dev ports already in use: ${held[*]}" >&2
echo >&2
for port in "${held[@]}"; do
    holder=$(lsof -i ":$port" 2>/dev/null | awk 'NR==2 {printf "%s (pid %s)", $1, $2}')
    printf '  %s: %s\n' "$port" "${holder:-unknown}" >&2
done
echo >&2
echo "run \`npm run dev:stop\` to clean up, then retry." >&2
exit 1
