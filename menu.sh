#!/usr/bin/env bash
# Sourced by apply.sh after locating the game and checking basic prerequisites.

menu_choice() {
    local prompt=$1 allowed=$2 default=$3 answer
    while :; do
        printf '%s [%s]: ' "$prompt" "$default" >&2
        if ! IFS= read -r answer; then
            echo 'Input closed; leaving menu.' >&2
            exit 0
        fi
        answer=${answer:-$default}
        case " $allowed " in
            *" $answer "*) REPLY=$answer; return ;;
            *) echo "Choose one of: $allowed" >&2 ;;
        esac
    done
}

menu_operation() {
    local status
    if bash "$patch/apply.sh" "$@"; then
        echo 'Operation complete. Returning to the main menu.'
    else
        status=$?
        echo "Operation failed (exit $status). No further actions were started. Returning to the main menu." >&2
    fi
}

menu_restore() {
    local label=$1 option=$2
    echo "Restore $label from this installation's backup. Other settings remain unchanged."
    menu_choice 'Restore now? y/n' 'y n' n
    if [ "$REPLY" = y ]; then
        menu_operation "$option"
    else
        echo 'No changes made. Returning to the main menu.'
    fi
}

menu_settings() {
    local action=$1 dimension min answer confirm_default
    local -a choices=()
    echo
    echo '--- Renderer ---'
    echo '1) Mesa Zink: windowed OpenGL-over-Vulkan (requires 32-bit Vulkan)'
    echo '2) Native OpenGL: SDL fullscreen may clip the viewport'
    echo '0) Back to main menu'
    menu_choice 'Select renderer' '0 1 2' 1
    case "$REPLY" in
        0) return ;;
        2) choices+=(--native) ;;
    esac
    echo
    echo '--- Resolution ---'
    echo '1) 1280x720: recommended first try'
    echo '2) Primary display size: may freeze on large displays'
    echo '3) Custom width and height'
    echo '0) Back to main menu'
    menu_choice 'Select resolution' '0 1 2 3' 1
    case "$REPLY" in
        0) return ;;
        1) choices+=(--width 1280 --height 720) ;;
        2) choices+=(--display-size) ;;
        3)
            for dimension in width height; do
                if [ "$dimension" = width ]; then min=320; else min=240; fi
                while :; do
                    printf '%s (pixels, %s–8192; 0 to main menu): ' "$dimension" "$min" >&2
                    if ! IFS= read -r answer; then
                        echo 'Input closed; leaving menu.' >&2
                        exit 0
                    fi
                    [ "$answer" = 0 ] && return
                    if [[ $answer =~ ^[0-9]{1,4}$ ]] && (( 10#$answer >= min && 10#$answer <= 8192 )); then
                        choices+=("--$dimension" "$((10#$answer))")
                        break
                    fi
                    echo 'Enter a valid positive pixel count, or 0 for the main menu.' >&2
                done
            done
            ;;
    esac
    if [ "$action" = configure ]; then
        echo
        echo '--- Optional changes (experimental features default to No) ---'
        menu_choice 'Update a matching Lutris entry? y/n/0=back' 'y n 0' y
        [ "$REPLY" = 0 ] && return
        [ "$REPLY" = y ] || choices+=(--no-lutris)
        menu_choice 'Try Escape-on-release? May resize or stall. y/n/0=back' 'y n 0' n
        [ "$REPLY" = 0 ] && return
        [ "$REPLY" = n ] || choices+=(--input-fix)
        menu_choice 'Try Steam SDL12-compat? May stall. y/n/0=back' 'y n 0' n
        [ "$REPLY" = 0 ] && return
        [ "$REPLY" = n ] || choices+=(--sdl-compat)
        echo 'Configuration edits game/user INIs, audio links and launcher. First-run backups remain outside this repository.'
        confirm_default=n
    else
        choices+=(--check)
        echo 'Dependency check reads files only; it will not configure or start the game.'
        confirm_default=y
    fi
    echo "Selected: ${choices[*]}"
    menu_choice 'Proceed? y/n/0=back' 'y n 0' "$confirm_default"
    if [ "$REPLY" = y ]; then
        menu_operation "${choices[@]}"
    else
        echo 'No changes made. Returning to the main menu.'
    fi
}

menu_test() {
    echo
    echo 'ONE-MINUTE TEST RUN: the game will be stopped after 60 seconds.'
    echo 'If the UI breaks or controls are lost, wait one minute; TERM is sent,'
    echo 'then KILL 3 seconds later if needed. GPU/compositor hangs may persist.'
    echo 'If you can switch to Ctrl+Alt+F3, run the recovery script from there:'
    printf '  bash %q\n' "$patch/recover-ut2003.sh"
    echo 'The menu returns after the game exits or the timer ends.'
    menu_choice 'Start the one-minute test? y/n' 'y n' n
    if [ "$REPLY" != y ]; then
        echo 'Test cancelled. Returning to the main menu.'
        return
    fi
    local status
    if UT2003_TEST_SECONDS=60 bash "$patch/test-launch.sh"; then
        echo 'Game exited before the minute elapsed. Returning to the main menu.'
    else
        status=$?
        if [ "$status" -eq 124 ] || [ "$status" -eq 137 ]; then
            echo 'One-minute time limit reached; returning to the main menu.'
        else
            echo "Test launch exited with status $status; returning to the main menu." >&2
        fi
    fi
}

run_menu() {
    while :; do
        echo
        echo '========================================================'
        echo '   Unreal Tournament 2003  |  Linux setup'
        echo '========================================================'
        echo "Game: $game"
        echo "Patch: $patch"
        echo 'Fullscreen and Escape fixes are experimental; a GPU freeze is possible.'
        echo '  1) Configure game (confirmation required)'
        echo '  2) Check 32-bit dependencies (read-only)'
        echo '  3) Restore original Escape binding'
        echo '  4) Restore bundled SDL 1.2'
        echo '  5) Restore original audio'
        echo '  6) Test launch for ONE MINUTE, then return to this menu'
        echo '  0) Exit'
        menu_choice 'Main menu' '0 1 2 3 4 5 6' 0
        case "$REPLY" in
            0) echo 'Exiting setup.'; return ;;
            1) menu_settings configure ;;
            2) menu_settings check ;;
            3) menu_restore 'Escape binding' --restore-input ;;
            4) menu_restore 'bundled SDL' --restore-sdl ;;
            5) menu_restore 'original audio' --restore-audio ;;
            6) menu_test ;;
        esac
    done
}
