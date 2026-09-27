#!/usr/bin/env bash
# Configure an existing UT2003 Linux installation; no game files are bundled.
set -euo pipefail

patch=$(cd -- "$(dirname -- "$0")" && pwd)
game=$(cd -- "$patch/.." && pwd)

if [ "${1:-}" = '--help' ]; then
    cat <<'EOF'
Unreal Tournament 2003 — Linux ultrawide setup
Usage: ./apply.sh [--interactive | --width PIXELS --height PIXELS [options]]
No arguments starts a guided menu in a terminal. Options run non-interactively.
Place this repository directly inside your UT2003 game directory; run from any directory.
  --interactive   Show guided choices (also permits piped input)
  --check         Check installed game and 32-bit runtime dependencies; change nothing
  --display-size  Choose primary X11 output size (may freeze on large displays)
  --fit-workarea  Fit a 16:9 Zink window above desktop panels (X11/Xwayland)
  --native        Use native OpenGL instead of Mesa Zink (fullscreen may clip)
  --proton        Use an isolated Windows game copy and installed Steam Proton
  --proton-fullscreen  Start Proton in fullscreen at the configured width/height
  --proton-windowed    Keep Proton windowed (default; restores from fullscreen)
  --skip-winpatch  Do not extract ut2003-winpatch2225.exe into the private game copy
  --cdkey-from-native  Apply your existing native System/cdkey to Proton only
  --cdkey        Enter your CD key in a hidden terminal prompt for Proton
  --input-fix     Try experimental Escape-on-release binding (may resize on press)
  --no-input-fix  Leave Escape bindings alone (default)
  --sdl-compat    Try Steam's SDL12-compat (experimental)
  --original-sdl  Use the bundled SDL (default)
  --undecorated   Request no titlebar/frame for windowed Zink (not fullscreen)
  --decorated     Keep normal window decorations (default)
  --no-lutris     Do not update a matching Lutris entry
  --openspy       Opt in to OpenSpy master server only (no renderer changes)
  --restore-openspy  Restore previous master-server settings only
  --restore-input | --restore-sdl | --restore-audio   Restore one component
Environment: UT2003_PROTON (path to installed Proton), UT2003_OPENAL_SOFT,
             UT2003_ZINK_DRIVER, UT2003_LIBSTDCXX_SO,
             UT2003_SDL_COMPAT_DIR can specify host 32-bit runtime paths.
See README.md in this repository for limitations, examples and rollback.
EOF
    exit 0
fi

if [ ! -x "$game/System/ut2003-bin" ] || [ ! -f "$game/System/UT2003.ini" ] \
    || [ ! -f "$game/System/Default.ini" ] || [ ! -e "$game/System/libSDL-1.2.so.0" ]; then
    echo 'This patch requires an installed Linux UT2003 (System/ut2003-bin, INIs and bundled SDL 1.2).' >&2
    exit 1
fi
command -v python3 >/dev/null || { echo 'Python 3 is required to edit INI files.' >&2; exit 1; }
command -v file >/dev/null || { echo 'The file utility is required to check 32-bit libraries.' >&2; exit 1; }

# Interactive actions run in child invocations with explicit flags, so the menu
# always survives a failed check/restore and can offer another action.
if [ "$#" -eq 0 ] && [ ! -t 0 ]; then
    echo 'No terminal input available. Run apply.sh in a terminal or pass --check; see --help.' >&2
    exit 2
fi
if [ "$#" -eq 0 ] || [ "${1:-}" = '--interactive' ]; then
    if [ "$#" -gt 1 ]; then
        echo '--interactive cannot be combined with other options.' >&2
        exit 2
    fi
    source "$patch/menu.sh"
    run_menu
    exit 0
fi

if [ "${1:-}" = '--cdkey' ] || [ "${1:-}" = '--cdkey-from-native' ] || [ "${1:-}" = '--cdkey-stdin' ]; then
    [ "$#" -eq 1 ] || { echo 'CD key actions must be used alone.' >&2; exit 2; }
    case "$1" in
        --cdkey) source_arg=--prompt ;;
        --cdkey-from-native) source_arg=--from-native ;;
        --cdkey-stdin) source_arg=--stdin ;;
    esac
    python3 "$patch/cdkey.py" "$game" "$source_arg"
    exit 0
fi

if [ "${1:-}" = '--openspy' ] || [ "${1:-}" = '--restore-openspy' ]; then
    [ "$#" -eq 1 ] || { echo 'OpenSpy options must be used alone.' >&2; exit 2; }
    if [ "$1" = --restore-openspy ]; then
        python3 "$patch/openspy.py" "$game" --restore
    else
        python3 "$patch/openspy.py" "$game"
    fi
    exit 0
fi

if [ "${1:-}" = '--restore-sdl' ]; then
    original="$game/Backup/libSDL-1.2.so.0.original"
    [ -f "$original" ] || { echo "No original SDL backup: $original" >&2; exit 1; }
    rm -f -- "$game/System/libSDL-1.2.so.0"
    cp -p -- "$original" "$game/System/libSDL-1.2.so.0"
    if [ -L "$game/System/libSDL2-2.0.so.0" ]; then
        rm -f -- "$game/System/libSDL2-2.0.so.0"
    fi
    echo 'Restored bundled SDL 1.2. To retry SDL compatibility, rerun apply.sh.'
    exit 0
fi

if [ "${1:-}" = '--restore-input' ]; then
    python3 "$patch/configure.py" "$game" --restore-input
    exit 0
fi

if [ "${1:-}" = '--restore-audio' ]; then
    original="$game/System/openal.so.pre-linuxpatch"
    [ -e "$original" ] || { echo "No original OpenAL backup: $original" >&2; exit 1; }
    if [ -L "$game/System/libopenal.so" ] && [ "$(readlink -- "$game/System/libopenal.so")" = 'openal.so' ]; then
        rm -f -- "$game/System/libopenal.so"
        if [ -e "$game/System/libopenal.so.pre-linuxpatch" ] || [ -L "$game/System/libopenal.so.pre-linuxpatch" ]; then
            cp -p -- "$game/System/libopenal.so.pre-linuxpatch" "$game/System/libopenal.so"
        fi
    fi
    rm -f -- "$game/System/openal.so"
    cp -p -- "$original" "$game/System/openal.so"
    echo 'Restored the original OpenAL libraries. Audio may be silent again.'
    exit 0
fi

renderer=zink
configure_args=()
width=
height=
use_sdl_compat=false
use_input_fix=false
check_only=false
use_display_size=false
use_fit_workarea=false
use_undecorated=false
skip_winpatch=false
proton_fullscreen=false
proton_video_option=false
while [ "$#" -gt 0 ]; do
    case "$1" in
        --native) renderer=native ;;
        --proton) renderer=proton ;;
        --proton-fullscreen) proton_fullscreen=true; proton_video_option=true ;;
        --proton-windowed) proton_fullscreen=false; proton_video_option=true ;;
        --skip-winpatch) skip_winpatch=true ;;
        --no-lutris) configure_args+=(--no-lutris) ;;
        --sdl-compat) use_sdl_compat=true ;;
        --original-sdl) use_sdl_compat=false ;;
        --undecorated) use_undecorated=true ;;
        --decorated) use_undecorated=false ;;
        --no-input-fix) use_input_fix=false ;;
        --input-fix) use_input_fix=true ;;
        --check) check_only=true ;;
        --display-size) use_display_size=true ;;
        --fit-workarea) use_fit_workarea=true ;;
        --width|--height)
            option=$1
            shift
            [ "$#" -gt 0 ] || { echo "Missing value for $option" >&2; exit 2; }
            if [ "$option" = --width ]; then width=$1; else height=$1; fi
            ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done
# Default to a smaller window. Full display resolution has stalled on this host.
if [ "$use_fit_workarea" = true ]; then
    [ "$renderer" = zink ] && [ "$use_display_size" = false ] && [ -z "$width" ] && [ -z "$height" ] || {
        echo '--fit-workarea requires windowed Zink and cannot be combined with other size options.' >&2
        exit 2
    }
    command -v xrandr >/dev/null 2>&1 && command -v xprop >/dev/null 2>&1 || {
        echo '--fit-workarea requires xrandr and xprop on X11/Xwayland.' >&2
        exit 1
    }
    display_mode=$(xrandr --current 2>/dev/null | awk '$2 == "connected" && $3 == "primary" {split($4, p, "+"); print p[1]; exit}') || true
    work_area=$(xprop -root _NET_WORKAREA 2>/dev/null | sed -n 's/^[^=]*= *//p') || true
    if [[ $display_mode =~ ^([0-9]+)x([0-9]+)$ ]]; then
        primary_width=${BASH_REMATCH[1]}
    else
        echo 'No primary X11 output detected; choose --width and --height instead.' >&2
        exit 1
    fi
    if [[ $work_area =~ ^[0-9]+,[[:space:]]*[0-9]+,[[:space:]]*([0-9]+),[[:space:]]*([0-9]+) ]]; then
        work_width=${BASH_REMATCH[1]}
        work_height=${BASH_REMATCH[2]}
    else
        echo 'No desktop work area detected; choose --width and --height instead.' >&2
        exit 1
    fi
    (( work_width < primary_width )) && primary_width=$work_width
    scale=$(( (work_height - 32) / 9 ))
    width_scale=$(( (primary_width - 32) / 16 ))
    (( width_scale < scale )) && scale=$width_scale
    (( scale >= 27 )) || { echo 'Desktop work area is too small.' >&2; exit 1; }
    width=$((scale * 16))
    height=$((scale * 9))
    echo "Fitting 16:9 window to work area: ${width}x${height} (available ${work_width}x${work_height})."
fi
if [ "$use_display_size" = true ]; then
    [ -z "$width" ] && [ -z "$height" ] || { echo '--display-size cannot be combined with --width/--height.' >&2; exit 2; }
    display_mode=
    if command -v xrandr >/dev/null 2>&1; then
        display_mode=$(xrandr --current 2>/dev/null | awk '$2 == "connected" && $3 == "primary" {split($4, p, "+"); print p[1]; exit}') || true
    fi
    if [[ ${display_mode:-} =~ ^([0-9]+)x([0-9]+)$ ]]; then
        width=${BASH_REMATCH[1]}
        height=${BASH_REMATCH[2]}
    else
        echo 'No primary X11 output detected; use --width and --height instead.' >&2
        exit 1
    fi
fi
width=${width:-1280}
height=${height:-720}
[[ $width =~ ^[0-9]+$ && $height =~ ^[0-9]+$ ]] || { echo 'Width and height must be positive integers.' >&2; exit 2; }
(( width >= 320 && width <= 8192 && height >= 240 && height <= 8192 )) || { echo 'Unsupported width or height.' >&2; exit 2; }
if [ "$renderer" != proton ] && { [ "$skip_winpatch" = true ] || [ "$proton_video_option" = true ]; }; then
    echo '--skip-winpatch and --proton-fullscreen/--proton-windowed apply only to --proton.' >&2
    exit 2
fi
if [ "$renderer" = proton ]; then
    [ "$use_sdl_compat" = false ] && [ "$use_input_fix" = false ] && [ "$use_undecorated" = false ] || {
        echo 'SDL compatibility, native Escape and undecorated options cannot be used with Proton.' >&2
        exit 2
    }
    python3 "$patch/proton.py" "$game" --check
    if [ "$skip_winpatch" = false ] && [ -f "$game/ut2003-winpatch2225.exe" ]; then
        command -v 7z >/dev/null || { echo 'Install 7-Zip (7z) to apply the Windows 2225 patch, or pass --skip-winpatch.' >&2; exit 1; }
    fi
    if [ "$check_only" = true ]; then exit 0; fi
    winpatch_args=()
    if [ "$skip_winpatch" = false ] && [ -f "$game/ut2003-winpatch2225.exe" ]; then
        echo "Extracting Windows 2225 patch into the PRIVATE game copy: $game/Backup/ProtonGame"
        echo 'The original game is untouched; no Wine installer window or Z: drive is needed.'
        winpatch_args+=(--install-winpatch)
    fi
    [ "$proton_fullscreen" = false ] || winpatch_args+=(--fullscreen)
    python3 "$patch/proton.py" "$game" --patch "$patch" --width "$width" --height "$height" "${winpatch_args[@]}"
    for file in launch-ut2003.sh ut2003-proton.py; do
        if [ -e "$game/$file" ] && [ ! -e "$game/$file.pre-linuxpatch" ]; then
            cp -p -- "$game/$file" "$game/$file.pre-linuxpatch"
        fi
    done
    cp -p -- "$patch/launch-ut2003.sh" "$game/launch-ut2003.sh"
    cp -p -- "$patch/proton.py" "$game/ut2003-proton.py"
    chmod u+x "$game/launch-ut2003.sh"
    python3 "$patch/configure.py" "$game" --renderer proton "${configure_args[@]}"
    printf 'proton\n' > "$game/System/.ut2003-renderer"
    printf '%s %s\n' "$width" "$height" > "$game/System/.ut2003-video"
    if [ "$proton_fullscreen" = true ]; then
        echo "Proton fullscreen selected at ${width}x${height}; test with the ONE-MINUTE menu option before normal launch."
    else
        echo "Proton windowed mode selected at ${width}x${height}."
    fi
    echo 'Native Zink files are unchanged; choose Zink in Configure Game to switch back.'
    exit 0
fi
if [ "$use_undecorated" = true ]; then
    [ "$renderer" = zink ] || { echo '--undecorated is for windowed Zink only.' >&2; exit 2; }
    command -v xdotool >/dev/null 2>&1 && [ -f "$patch/window-hints.py" ] || {
        echo 'Undecorated mode requires xdotool and the included window-hints helper.' >&2
        exit 1
    }
fi
if [ "$renderer" = zink ]; then
    zink_available=false
    for driver in "${UT2003_ZINK_DRIVER:-}" /usr/lib/dri/zink_dri.so /usr/lib/i386-linux-gnu/dri/zink_dri.so /usr/lib32/dri/zink_dri.so; do
        if [ -f "$driver" ] && file -Lb -- "$driver" | grep -q 'ELF 32-bit'; then
            zink_available=true
            break
        fi
    done
    if [ "$zink_available" != true ]; then
        echo 'The 32-bit Mesa Zink OpenGL driver is required; use --native for NVIDIA OpenGL instead.' >&2
        exit 1
    fi
fi

# Use the host's 32-bit OpenAL Soft, not the bundled OSS-era OpenAL backend.
openal="${UT2003_OPENAL_SOFT:-}"
if [ -z "$openal" ]; then
    for candidate in /usr/lib/libopenal.so.1 /usr/lib/i386-linux-gnu/libopenal.so.1 /usr/lib32/libopenal.so.1; do
        if [ -f "$candidate" ] && file -Lb -- "$candidate" | grep -q 'ELF 32-bit'; then
            openal="$candidate"
            break
        fi
    done
fi
if [ -z "$openal" ] || [ ! -f "$openal" ] || ! file -Lb -- "$openal" | grep -q 'ELF 32-bit'; then
    echo 'Install 32-bit OpenAL Soft (libopenal.so.1), or set UT2003_OPENAL_SOFT to its path.' >&2
    exit 1
fi

legacy_cxx="$game/System/libstdc++.so.5"
runtime="${UT2003_LIBSTDCXX_SO:-$HOME/.local/share/lutris/runtime/Ubuntu-18.04-i686/libstdc++.so.5}"
if [ ! -e "$legacy_cxx" ] && { [ ! -f "$runtime" ] || ! file -Lb -- "$runtime" | grep -q 'ELF 32-bit'; } \
    && ! ldconfig -p 2>/dev/null | grep -q 'libstdc++.so.5.*libc6'; then
    echo 'A 32-bit libstdc++.so.5 is required; set UT2003_LIBSTDCXX_SO to its path.' >&2
    exit 1
fi
if [ "$use_sdl_compat" = true ]; then
    steam_sdl="${UT2003_SDL_COMPAT_DIR:-$HOME/.local/share/Steam/ubuntu12_32/steam-runtime/usr/lib/i386-linux-gnu}"
    if [ ! -f "$steam_sdl/libSDL-1.2.so.0" ] || [ ! -f "$steam_sdl/libSDL2-2.0.so.0" ] \
        || ! file -Lb -- "$steam_sdl/libSDL-1.2.so.0" | grep -q 'ELF 32-bit' \
        || ! file -Lb -- "$steam_sdl/libSDL2-2.0.so.0" | grep -q 'ELF 32-bit'; then
        echo 'No 32-bit SDL12-compat/SDL2 found; set UT2003_SDL_COMPAT_DIR or use --original-sdl.' >&2
        exit 1
    fi
    if [ ! -e "$game/Backup/libSDL-1.2.so.0.original" ] && [ -L "$game/System/libSDL-1.2.so.0" ]; then
        echo 'Cannot replace an existing SDL link without an original backup in Backup/.' >&2
        exit 1
    fi
fi
if [ "$check_only" = true ]; then
    echo "OK: UT2003 game files, $renderer renderer, 32-bit OpenAL Soft, and libstdc++.so.5."
    echo 'This checks file availability, not GPU compatibility or in-game behavior.'
    exit 0
fi

# Preserve existing configuration outside this Git directory on the first run.
for file in System/UT2003.ini System/Default.ini System/openal.so System/libopenal.so launch-ut2003.sh ut2003-window-hints.py; do
    if { [ -f "$game/$file" ] || [ -L "$game/$file" ]; } && [ ! -e "$game/$file.pre-linuxpatch" ]; then
        cp -p -- "$game/$file" "$game/$file.pre-linuxpatch"
    fi
done
user_ini="$HOME/.ut2003/System/UT2003.ini"
if [ -f "$user_ini" ] && [ ! -e "$user_ini.pre-linuxpatch" ]; then
    cp -p -- "$user_ini" "$user_ini.pre-linuxpatch"
fi

# Resolve the game's libstdc++5 without exposing OpenAL Soft to Lutris's old
# libpulse/libwrap libraries through LD_LIBRARY_PATH.
if [ ! -e "$legacy_cxx" ]; then
    if [ -f "$runtime" ] && file -Lb -- "$runtime" | grep -q 'ELF 32-bit'; then
        ln -sfn -- "$runtime" "$legacy_cxx"
    elif ! ldconfig -p 2>/dev/null | grep -q 'libstdc++.so.5.*libc6'; then
        echo 'A 32-bit libstdc++.so.5 is required; set UT2003_LIBSTDCXX_SO to its path.' >&2
        exit 1
    fi
fi

rm -f -- "$game/System/openal.so" "$game/System/libopenal.so"
ln -s -- "$openal" "$game/System/openal.so"
ln -s -- openal.so "$game/System/libopenal.so"
# SDL12-compat uses SDL2's event handling and avoids the game's bundled SDL
# 1.2 input path. Both libraries come from an installed Steam runtime; neither
# is copied into this Git repository. The bundled library stays in Backup/.
if [ "$use_sdl_compat" = true ]; then
    steam_sdl="${UT2003_SDL_COMPAT_DIR:-$HOME/.local/share/Steam/ubuntu12_32/steam-runtime/usr/lib/i386-linux-gnu}"
    if [ -f "$steam_sdl/libSDL-1.2.so.0" ] && [ -f "$steam_sdl/libSDL2-2.0.so.0" ] \
        && file -Lb -- "$steam_sdl/libSDL-1.2.so.0" | grep -q 'ELF 32-bit' \
        && file -Lb -- "$steam_sdl/libSDL2-2.0.so.0" | grep -q 'ELF 32-bit'; then
        mkdir -p -- "$game/Backup"
        backup_sdl="$game/Backup/libSDL-1.2.so.0.original"
        if [ ! -e "$backup_sdl" ]; then
            if [ -L "$game/System/libSDL-1.2.so.0" ]; then
                echo 'Cannot replace an existing SDL link without an original backup in Backup/.' >&2
                exit 1
            fi
            cp -p -- "$game/System/libSDL-1.2.so.0" "$backup_sdl"
        fi
        ln -sfn -- "$steam_sdl/libSDL-1.2.so.0" "$game/System/libSDL-1.2.so.0"
        ln -sfn -- "$steam_sdl/libSDL2-2.0.so.0" "$game/System/libSDL2-2.0.so.0"
        echo 'Using 32-bit SDL12-compat from the installed Steam runtime.'
    else
        echo 'No 32-bit SDL12-compat/SDL2 found; set UT2003_SDL_COMPAT_DIR or use --original-sdl.' >&2
        exit 1
    fi
else
    backup_sdl="$game/Backup/libSDL-1.2.so.0.original"
    if [ -f "$backup_sdl" ] && [ -L "$game/System/libSDL-1.2.so.0" ]; then
        rm -f -- "$game/System/libSDL-1.2.so.0"
        cp -p -- "$backup_sdl" "$game/System/libSDL-1.2.so.0"
        [ ! -L "$game/System/libSDL2-2.0.so.0" ] || rm -f -- "$game/System/libSDL2-2.0.so.0"
    fi
fi

cp -p -- "$patch/launch-ut2003.sh" "$game/launch-ut2003.sh"
cp -p -- "$patch/window-hints.py" "$game/ut2003-window-hints.py"
chmod u+x "$game/launch-ut2003.sh"
if [ "$use_input_fix" = true ]; then
    configure_args+=(--input-fix)
    mkdir -p -- "$game/Backup"
    chmod 700 "$game/Backup"
    user_controls="$HOME/.ut2003/System/User.ini"
    if [ -f "$user_controls" ] && [ ! -e "$game/Backup/User.ini.original" ]; then
        cp -p -- "$user_controls" "$game/Backup/User.ini.original"
    fi
    if [ -f "$game/System/User.ini" ] && [ ! -e "$game/Backup/System-User.ini.original" ]; then
        cp -p -- "$game/System/User.ini" "$game/Backup/System-User.ini.original"
    fi
else
    configure_args+=(--no-input-fix)
fi
python3 "$patch/configure.py" "$game" --renderer "$renderer" --width "$width" --height "$height" "${configure_args[@]}"
printf '%s\n' "$renderer" > "$game/System/.ut2003-renderer"
printf '%s %s\n' "$width" "$height" > "$game/System/.ut2003-video"
if [ "$use_undecorated" = true ]; then
    printf '1\n' > "$game/System/.ut2003-undecorated"
else
    printf '0\n' > "$game/System/.ut2003-undecorated"
fi
echo "Installed 32-bit OpenAL Soft from $openal; renderer: $renderer; game size: ${width}x${height}."
echo 'Zink stays windowed by default. UT2003_BORDERLESS=1 is experimental and stalled on this host.'
echo 'SDL12-compat is opt-in (--sdl-compat); it stalled at 2560x1080 on this host.'
echo 'MenuViewport alone does not preserve the menu aspect ratio at ultrawide resolutions.'
if [ "$use_undecorated" = true ]; then
    echo 'Undecorated window requested; this removes the frame only, not fullscreen or compositor panels.'
fi
if [ "$use_input_fix" = true ]; then
    echo "Experimental Escape binding enabled. If it misbehaves, run '$patch/apply.sh' --restore-input."
else
    echo 'Escape bindings unchanged; --input-fix enables the experimental release binding.'
fi
