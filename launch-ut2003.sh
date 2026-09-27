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
width=1280
height=720
if [ -f .ut2003-video ]; then
    read -r width height < .ut2003-video
fi
renderer=${UT2003_RENDERER:-zink}
if [ -z "${UT2003_RENDERER:-}" ] && [ -f .ut2003-renderer ]; then
    renderer=$(< .ut2003-renderer)
fi
case "$renderer" in
    zink)
        # SDL fullscreen clips the viewport or crashes during SetRes. KWin
        # borderless mode is opt-in: it stalled during intro on this host.
        game_env=(env WAYLAND_DISPLAY= SDL_VIDEODRIVER=x11 LD_LIBRARY_PATH= LD_PRELOAD=
            ALSOFT_DRIVERS=pulse,pipewire,alsa __GLX_VENDOR_LIBRARY_NAME=mesa
            MESA_LOADER_DRIVER_OVERRIDE=zink GALLIUM_DRIVER=zink)
        if [ -n "${UT2003_ZINK_DRIVER:-}" ]; then
            game_env+=("LIBGL_DRIVERS_PATH=$(dirname -- "$UT2003_ZINK_DRIVER")")
        fi
        undecorated=${UT2003_UNDECORATED:-}
        if [ -z "$undecorated" ] && [ -f .ut2003-undecorated ]; then
            undecorated=$(< .ut2003-undecorated)
        fi
        if [ "$undecorated" = 1 ]; then
            command -v xdotool >/dev/null 2>&1 && command -v python3 >/dev/null 2>&1 \
                && [ -f "$root/ut2003-window-hints.py" ] || {
                echo 'Undecorated mode requires xdotool, Python 3 and the installed window-hints helper; reapply the patch or use --decorated.' >&2
                exit 1
            }
            # Ask the X11 window manager to hide the frame; never change the
            # SDL client size or request fullscreen. This is not fullscreen.
            "${game_env[@]}" ./ut2003-bin "$@" &
            game_pid=$!
            trap 'kill -KILL "$game_pid" 2>/dev/null || :' INT TERM
            for ((attempt=0; attempt<100; attempt++)); do
                kill -0 "$game_pid" 2>/dev/null || break
                window=$(xdotool search --onlyvisible --pid "$game_pid" --class ut2003 2>/dev/null | sed -n '$p') || true
                if [ -z "$window" ]; then
                    # Old SDL may omit _NET_WM_PID. Only fall back when there
                    # is exactly one matching game window on this display.
                    candidates=$(xdotool search --onlyvisible --class ut2003 2>/dev/null) || true
                    if [ -n "$candidates" ] && [ "$(printf '%s\n' "$candidates" | wc -l)" -eq 1 ]; then
                        window=$candidates
                    fi
                fi
                if [ -n "$window" ]; then
                    python3 "$root/ut2003-window-hints.py" "$window" || \
                        echo 'Could not remove decorations; game is still windowed.' >&2
                    break
                fi
                sleep 0.1
            done
            [ -n "${window:-}" ] || echo 'No unique UT2003 window found; decorations were not changed.' >&2
            wait "$game_pid"
            exit $?
        fi
        if [ "${UT2003_BORDERLESS:-0}" = 1 ] && command -v xrandr >/dev/null 2>&1 \
            && command -v wmctrl >/dev/null 2>&1 && command -v xdotool >/dev/null 2>&1; then
            display_mode=$(xrandr --current 2>/dev/null | awk '$2 == "connected" && $3 == "primary" {split($4, p, "+"); print p[1]; exit}')
            if [ "$display_mode" = "${width}x${height}" ]; then
                "${game_env[@]}" ./ut2003-bin "$@" &
                game_pid=$!
                trap 'kill -KILL "$game_pid" 2>/dev/null || :' INT TERM
                for ((attempt=0; attempt<60; attempt++)); do
                    kill -0 "$game_pid" 2>/dev/null || break
                    window=$(xdotool search --onlyvisible --pid "$game_pid" --class ut2003 2>/dev/null | sed -n '$p') || true
                    if [ -n "$window" ]; then
                        geometry=$(xdotool getwindowgeometry --shell "$window" 2>/dev/null) || true
                        if [[ $geometry == *"WIDTH=$width"* && $geometry == *"HEIGHT=$height"* ]]; then
                            wmctrl -ir "$window" -b add,fullscreen || true
                            break
                        fi
                    fi
                    sleep 0.1
                done
                wait "$game_pid"
                exit $?
            fi
            echo "${width}x${height} does not match primary output $display_mode; staying windowed to avoid viewport clipping." >&2
        fi
        exec "${game_env[@]}" ./ut2003-bin "$@"
        ;;
    native)
        # Gamescope's Wayland backend crashed on this host; opt in to an
        # experimental SDL-backend test rather than silently hiding the window.
        if [ "${UT2003_GAMESCOPE_SDL:-0}" = 1 ]; then
            command -v gamescope >/dev/null 2>&1 || { echo 'gamescope is required' >&2; exit 1; }
            exec gamescope --backend sdl -f -w "$width" -h "$height" -W "$width" -H "$height" -- env \
                -u __GLX_VENDOR_LIBRARY_NAME -u MESA_LOADER_DRIVER_OVERRIDE -u GALLIUM_DRIVER \
                LD_LIBRARY_PATH= LD_PRELOAD= ALSOFT_DRIVERS=pulse,pipewire,alsa ./ut2003-bin "$@"
        fi
        exec env -u __GLX_VENDOR_LIBRARY_NAME -u MESA_LOADER_DRIVER_OVERRIDE \
            -u GALLIUM_DRIVER LD_LIBRARY_PATH= LD_PRELOAD= \
            ALSOFT_DRIVERS=pulse,pipewire,alsa ./ut2003-bin "$@"
        ;;
    *) echo "Unknown renderer: $renderer (expected zink or native)" >&2; exit 2 ;;
esac
