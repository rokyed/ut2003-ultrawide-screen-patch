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

# Do not mix Lutris's old PulseAudio libraries with host OpenAL Soft.
renderer=${UT2003_RENDERER:-zink}
if [ -z "${UT2003_RENDERER:-}" ] && [ -f .ut2003-renderer ]; then
    renderer=$(< .ut2003-renderer)
fi
case "$renderer" in
    zink)
        # Zink works windowed on Xwayland here; Zink inside Gamescope crashed.
        exec env WAYLAND_DISPLAY= SDL_VIDEODRIVER=x11 LD_LIBRARY_PATH= LD_PRELOAD= \
            ALSOFT_DRIVERS=pulse,pipewire,alsa __GLX_VENDOR_LIBRARY_NAME=mesa \
            MESA_LOADER_DRIVER_OVERRIDE=zink GALLIUM_DRIVER=zink ./ut2003-bin "$@"
        ;;
    native)
        if [ -n "${WAYLAND_DISPLAY:-}" ] && command -v gamescope >/dev/null 2>&1; then
            exec gamescope -f -w 1280 -h 720 -S fit -- env -u __GLX_VENDOR_LIBRARY_NAME \
                -u MESA_LOADER_DRIVER_OVERRIDE -u GALLIUM_DRIVER LD_LIBRARY_PATH= LD_PRELOAD= \
                ALSOFT_DRIVERS=pulse,pipewire,alsa ./ut2003-bin "$@"
        fi
        exec env -u __GLX_VENDOR_LIBRARY_NAME -u MESA_LOADER_DRIVER_OVERRIDE \
            -u GALLIUM_DRIVER LD_LIBRARY_PATH= LD_PRELOAD= \
            ALSOFT_DRIVERS=pulse,pipewire,alsa ./ut2003-bin "$@"
        ;;
    *) echo "Unknown renderer: $renderer (expected zink or native)" >&2; exit 2 ;;
esac
