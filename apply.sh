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
for argument in "$@"; do
    case "$argument" in
        --native) renderer=native ;;
        --no-lutris) configure_args+=(--no-lutris) ;;
        *) echo "Unknown option: $argument (use --native, --no-lutris, or --restore-audio)" >&2; exit 2 ;;
    esac
done
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
cp -p -- "$patch/launch-ut2003.sh" "$game/launch-ut2003.sh"
chmod u+x "$game/launch-ut2003.sh"
python3 "$patch/configure.py" "$game" --renderer "$renderer" "${configure_args[@]}"
printf '%s\n' "$renderer" > "$game/System/.ut2003-renderer"
echo "Installed 32-bit OpenAL Soft from $openal; renderer: $renderer."
echo 'Launch via launch-ut2003.sh or Lutris; use --native to restore NVIDIA OpenGL/Gamescope.'
