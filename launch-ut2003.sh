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

# Lutris supplies this obsolete 32-bit C++ library to the native game. Gamescope
# does not inherit its library path, so supply the same runtime to its child.
runtime="$HOME/.local/share/lutris/runtime/Ubuntu-18.04-i686"
if [ -f "$runtime/libstdc++.so.5" ]; then
    library_path="$runtime${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
else
    library_path="${LD_LIBRARY_PATH:-}"
fi

# Preserve an existing padsp32 wrapper if the installation has one. Do not
# force a new audio preload: the host's 32-bit bridge crashed this build.
command=(./ut2003-bin)
if [ -x ../padsp32 ]; then
    command=(../padsp32 "${command[@]}")
fi
if [ -n "${WAYLAND_DISPLAY:-}" ] && command -v gamescope >/dev/null 2>&1; then
    exec gamescope -f -w 1280 -h 720 -S fit -- env LD_LIBRARY_PATH="$library_path" "${command[@]}" "$@"
fi
exec env LD_LIBRARY_PATH="$library_path" "${command[@]}" "$@"
