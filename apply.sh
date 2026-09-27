#!/usr/bin/env bash
# Configure an existing UT2003 Linux installation; no game files are bundled.
set -euo pipefail

patch=$(cd -- "$(dirname -- "$0")" && pwd)
game=$(cd -- "$patch/.." && pwd)

if [ ! -x "$game/System/ut2003-bin" ] || [ ! -f "$game/System/UT2003.ini" ] || [ ! -f "$game/System/Default.ini" ]; then
    echo 'This patch requires an installed Linux UT2003 (System/ut2003-bin and INIs).' >&2
    exit 1
fi
command -v python3 >/dev/null || { echo 'Python 3 is required to edit INI files.' >&2; exit 1; }
command -v file >/dev/null || { echo 'The file utility is required to check 32-bit libraries.' >&2; exit 1; }

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
use_input_fix=true
while [ "$#" -gt 0 ]; do
    case "$1" in
        --native) renderer=native ;;
        --no-lutris) configure_args+=(--no-lutris) ;;
        --sdl-compat) use_sdl_compat=true ;;
        --original-sdl) use_sdl_compat=false ;;
        --no-input-fix) use_input_fix=false ;;
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
# Match the primary output by default. The game runs windowed: SDL exclusive
# fullscreen clips the viewport, and KWin borderless stalled on this host.
if [ -z "$width" ] || [ -z "$height" ]; then
    display_mode=$(xrandr --current 2>/dev/null | awk '$2 == "connected" && $3 == "primary" {split($4, p, "+"); print p[1]; exit}') || true
    if [[ ${display_mode:-} =~ ^([0-9]+)x([0-9]+)$ ]]; then
        [ -n "$width" ] || width=${BASH_REMATCH[1]}
        [ -n "$height" ] || height=${BASH_REMATCH[2]}
    fi
fi
width=${width:-1280}
height=${height:-720}
[[ $width =~ ^[0-9]+$ && $height =~ ^[0-9]+$ ]] || { echo 'Width and height must be positive integers.' >&2; exit 2; }
(( width >= 320 && width <= 8192 && height >= 240 && height <= 8192 )) || { echo 'Unsupported width or height.' >&2; exit 2; }
if [ "$renderer" = zink ]; then
    zink_available=false
    for driver in /usr/lib/dri/zink_dri.so /usr/lib/i386-linux-gnu/dri/zink_dri.so /usr/lib32/dri/zink_dri.so; do
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

# Preserve existing configuration outside this Git directory on the first run.
for file in System/UT2003.ini System/Default.ini System/openal.so System/libopenal.so launch-ut2003.sh; do
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
legacy_cxx="$game/System/libstdc++.so.5"
if [ ! -e "$legacy_cxx" ]; then
    runtime="$HOME/.local/share/lutris/runtime/Ubuntu-18.04-i686/libstdc++.so.5"
    if [ -f "$runtime" ] && file -Lb -- "$runtime" | grep -q 'ELF 32-bit'; then
        ln -sfn -- "$runtime" "$legacy_cxx"
    elif ! ldconfig -p 2>/dev/null | grep -q 'libstdc++.so.5.*libc6'; then
        echo 'A 32-bit libstdc++.so.5 is required (e.g. the Lutris Ubuntu-18.04-i686 runtime).' >&2
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
    steam_sdl="$HOME/.local/share/Steam/ubuntu12_32/steam-runtime/usr/lib/i386-linux-gnu"
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
        echo 'No 32-bit SDL12-compat/SDL2 found in the Steam runtime; retaining bundled SDL.' >&2
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
chmod u+x "$game/launch-ut2003.sh"
if [ "$use_input_fix" = true ]; then
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
echo "Installed 32-bit OpenAL Soft from $openal; renderer: $renderer; game size: ${width}x${height}."
echo 'Zink stays windowed by default. UT2003_BORDERLESS=1 is experimental and stalled on this host.'
echo 'SDL12-compat is opt-in (--sdl-compat); it stalled at 2560x1080 on this host.'
echo 'MenuViewport alone does not preserve the menu aspect ratio at ultrawide resolutions.'
echo 'Escape release binding is experimental; if it misbehaves, run ./LinuxPatch/apply.sh --restore-input.'
