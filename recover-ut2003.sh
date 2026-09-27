#!/usr/bin/env bash
# From another TTY, stop this installation's native or private Proton game.
set -euo pipefail

patch=$(cd -- "$(dirname -- "$0")" && pwd)
game=$(cd -- "$patch/.." && pwd)
target="$game/System/ut2003-bin"
found=0
for process in /proc/[0-9]*; do
    pid=${process##*/}
    executable=$(readlink -f -- "$process/exe" 2>/dev/null) || continue
    [ "$executable" = "$target" ] || continue
    found=1
    echo "Stopping UT2003 process $pid from $game"
    kill -TERM "$pid" 2>/dev/null || continue
    for ((attempt=0; attempt<20; attempt++)); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.1
    done
    # Recheck the executable before SIGKILL in case the PID was reused.
    if [ "$(readlink -f -- "$process/exe" 2>/dev/null || :)" = "$target" ]; then
        echo "Process $pid ignored TERM; sending KILL."
        kill -KILL "$pid" 2>/dev/null || :
    fi
done
if [ "$found" = 0 ]; then
    echo "No native UT2003 process from $game is running."
fi
if [ -f "$patch/proton.py" ] && command -v python3 >/dev/null 2>&1; then
    python3 "$patch/proton.py" "$game" --stop
fi
