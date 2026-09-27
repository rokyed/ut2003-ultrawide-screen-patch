#!/usr/bin/env bash
set -e

root=$(cd -- "$(dirname -- "$0")" && pwd)
cd "$root/System"

if [ ! -s cdkey ]; then
    if ! command -v zenity >/dev/null 2>&1; then
        echo 'Missing System/cdkey; enter your own key there before launching.' >&2
        exit 1
    fi
    key=$(zenity --entry --title='Unreal Tournament 2003' --text='Enter your UT2003 CD key') || exit 1
    [ -n "$key" ] || exit 1
    printf '%s\n' "$key" > cdkey
    chmod 600 cdkey
fi

# The old Lutris runtime contains obsolete PulseAudio libraries. With OpenAL
# Soft, prefer the host's matching 32-bit audio libraries instead. apply.sh
# places only the legacy libstdc++.so.5 needed by the game in System/.
if [ -n "${WAYLAND_DISPLAY:-}" ] && command -v gamescope >/dev/null 2>&1; then
    exec gamescope -f -w 1280 -h 720 -S fit -- env LD_LIBRARY_PATH= LD_PRELOAD= ALSOFT_DRIVERS=pulse,pipewire,alsa ./ut2003-bin "$@"
fi
exec env LD_LIBRARY_PATH= LD_PRELOAD= ALSOFT_DRIVERS=pulse,pipewire,alsa ./ut2003-bin "$@"
