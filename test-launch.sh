#!/usr/bin/env bash
# Use before a normal launch: forcibly end a hung game after a short trial.
set -euo pipefail
patch=$(cd -- "$(dirname -- "$0")" && pwd)
game=$(cd -- "$patch/.." && pwd)
seconds=${UT2003_TEST_SECONDS:-60}
if [[ ! $seconds =~ ^[0-9]{1,3}$ ]] || (( 10#$seconds < 5 || 10#$seconds > 600 )); then
    echo 'UT2003_TEST_SECONDS must be an integer between 5 and 600.' >&2
    exit 2
fi
seconds=$((10#$seconds))
command -v timeout >/dev/null || { echo 'GNU timeout (coreutils) is required.' >&2; exit 1; }
echo "Time-limited UT2003 test: stopping after ${seconds}s (TERM, then KILL 3s later)."
echo "If input remains trapped, press Ctrl+Alt+F3 and run: bash '$patch/recover-ut2003.sh'"
set +e
timeout --signal=TERM --kill-after=3s "${seconds}s" "$game/launch-ut2003.sh" "$@"
status=$?
set -e
# Proton can leave Wine children behind even when its launcher exits early.
renderer=${UT2003_RENDERER:-}
if [ -z "$renderer" ] && [ -f "$game/System/.ut2003-renderer" ]; then
    renderer=$(cat "$game/System/.ut2003-renderer")
fi
if [ "$renderer" = proton ]; then
    python3 "$patch/proton.py" "$game" --stop || true
fi
if [ "$status" -eq 124 ] || [ "$status" -eq 137 ]; then
    echo "Test time limit reached; game terminated (exit $status)." >&2
    exit "$status"
fi
exit "$status"
