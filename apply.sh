#!/usr/bin/env bash
# Configure an existing UT2003 Linux installation; no game files are bundled.
set -euo pipefail

patch=$(cd -- "$(dirname -- "$0")" && pwd)
game=$(cd -- "$patch/.." && pwd)

if [ "${1:-}" = '--help' ]; then
    cat <<'EOF'
Usage: ./LinuxPatch/apply.sh [--interactive | --width PIXELS --height PIXELS [options]]
No arguments starts a guided wizard in a terminal. Options run non-interactively.
Run from any directory; LinuxPatch must sit directly inside your UT2003 directory.
  --interactive   Show guided choices (also permits piped input)
  --check         Check installed game and 32-bit runtime dependencies; change nothing
  --display-size  Choose primary X11 output size (may freeze on large displays)
  --native        Use native OpenGL instead of Mesa Zink (fullscreen may clip)
  --input-fix     Try experimental Escape-on-release binding (may resize on press)
  --no-input-fix  Leave Escape bindings alone (default)
  --sdl-compat    Try Steam's SDL12-compat (experimental)
  --original-sdl  Use the bundled SDL (default)
  --no-lutris     Do not update a matching Lutris entry
  --restore-input | --restore-sdl | --restore-audio   Restore one component
Environment: UT2003_OPENAL_SOFT, UT2003_ZINK_DRIVER, UT2003_LIBSTDCXX_SO,
             UT2003_SDL_COMPAT_DIR can specify host 32-bit runtime paths.
See LinuxPatch/README.md for limitations, examples and rollback.
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

# No-argument invocations are guided only when a terminal is attached.
if [ "$#" -eq 0 ] && [ ! -t 0 ]; then
    echo 'No terminal input available. Run in a terminal or pass --check; see --help.' >&2
    exit 2
fi
if [ "$#" -eq 0 ] || [ "${1:-}" = '--interactive' ]; then
    if [ "$#" -gt 1 ]; then
        echo '--interactive cannot be combined with other options.' >&2
        exit 2
    fi
    ask_choice() {
        local prompt=$1 allowed=$2 default=$3 answer
        while :; do
            printf '%s [%s]: ' "$prompt" "$default" >&2
            if ! IFS= read -r answer; then echo 'Cancelled (input closed).' >&2; exit 1; fi
            answer=${answer:-$default}
            case " $allowed " in
                *" $answer "*) REPLY=$answer; return ;;
                *) echo "Choose one of: $allowed" >&2 ;;
            esac
        done
    }
    echo 'UT2003 Linux patch — game files are not included.'
    echo 'Known limits: fullscreen may clip or stall; 4:3 menus and Escape are not fully fixed.'
    echo "Game directory: $game"
    ask_choice 'Action: 1) Configure  2) Check dependencies  3) Restore Escape  4) Restore SDL  5) Restore audio  0) Cancel' '0 1 2 3 4 5' 1
    case "$REPLY" in
        0) echo 'Cancelled; no changes made.'; exit 0 ;;
        3|4|5)
            case "$REPLY" in
                3) target='Escape binding'; set -- --restore-input ;;
                4) target='bundled SDL'; set -- --restore-sdl ;;
                5) target='original audio'; set -- --restore-audio ;;
            esac
            echo "Restore $target from this installation's backup? Other settings remain unchanged."
            ask_choice 'Proceed? y/n' 'y n' n
            [ "$REPLY" = y ] || { echo 'Cancelled; no changes made.'; exit 0; }
            ;;
        1|2)
            action=$REPLY
            ask_choice 'Renderer: 1) Zink (windowed, needs 32-bit Vulkan)  2) Native OpenGL (fullscreen may clip)' '1 2' 1
            wizard_args=()
            [ "$REPLY" = 1 ] || wizard_args+=(--native)
            ask_choice 'Size: 1) 1280x720 (recommended)  2) Primary display  3) Custom' '1 2 3' 1
            case "$REPLY" in
                1) wizard_args+=(--width 1280 --height 720) ;;
                2) wizard_args+=(--display-size) ;;
                3)
                    for dimension in width height; do
                        if [ "$dimension" = width ]; then min=320; else min=240; fi
                        while :; do
                            printf '%s (pixels, %s–8192): ' "$dimension" "$min" >&2
                            if ! IFS= read -r answer; then echo 'Cancelled (input closed).' >&2; exit 1; fi
                            if [[ $answer =~ ^[0-9]{1,4}$ ]] && (( 10#$answer >= min && 10#$answer <= 8192 )); then
                                wizard_args+=("--$dimension" "$((10#$answer))")
                                break
                            fi
                            echo 'Enter a valid positive pixel count.' >&2
                        done
                    done
                    ;;
            esac
            if [ "$action" = 1 ]; then
                ask_choice 'Update a Lutris entry pointing to this game? y/n' 'y n' y
                [ "$REPLY" = y ] || wizard_args+=(--no-lutris)
                ask_choice 'Try experimental Escape binding? May resize or stall. y/n' 'y n' n
                [ "$REPLY" = n ] || wizard_args+=(--input-fix)
                ask_choice 'Try experimental Steam SDL12-compat? May stall. y/n' 'y n' n
                [ "$REPLY" = n ] || wizard_args+=(--sdl-compat)
                echo 'This will edit game/user INIs, link host audio and install a launcher; first-run backups stay outside LinuxPatch.'
                confirm_default=n
            else
                wizard_args+=(--check)
                echo 'This checks available dependencies without making changes.'
                confirm_default=y
            fi
            echo 'Selected options:' "${wizard_args[*]:-(defaults)}"
            ask_choice 'Proceed? y/n' 'y n' "$confirm_default"
            [ "$REPLY" = y ] || { echo 'Cancelled; no changes made.'; exit 0; }
            set -- "${wizard_args[@]}"
            ;;
    esac
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
while [ "$#" -gt 0 ]; do
    case "$1" in
        --native) renderer=native ;;
        --no-lutris) configure_args+=(--no-lutris) ;;
        --sdl-compat) use_sdl_compat=true ;;
        --original-sdl) use_sdl_compat=false ;;
        --no-input-fix) use_input_fix=false ;;
        --input-fix) use_input_fix=true ;;
        --check) check_only=true ;;
        --display-size) use_display_size=true ;;
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
echo "Installed 32-bit OpenAL Soft from $openal; renderer: $renderer; game size: ${width}x${height}."
echo 'Zink stays windowed by default. UT2003_BORDERLESS=1 is experimental and stalled on this host.'
echo 'SDL12-compat is opt-in (--sdl-compat); it stalled at 2560x1080 on this host.'
echo 'MenuViewport alone does not preserve the menu aspect ratio at ultrawide resolutions.'
if [ "$use_input_fix" = true ]; then
    echo 'Experimental Escape binding enabled. If it misbehaves, run ./LinuxPatch/apply.sh --restore-input.'
else
    echo 'Escape bindings unchanged; --input-fix enables the experimental release binding.'
fi
