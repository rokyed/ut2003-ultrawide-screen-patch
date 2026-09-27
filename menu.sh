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
    local action=$1 dimension min answer confirm_default renderer_choice resolution_choices
    local -a choices=()
    echo
    echo '--- Renderer ---'
    echo '1) Mesa Zink: windowed OpenGL-over-Vulkan (requires 32-bit Vulkan)'
    echo '2) Native OpenGL: SDL fullscreen may clip the viewport'
    echo '3) Proton: Windows executable + installed Steam Proton (private game copy)'
    echo '0) Back to main menu'
    menu_choice 'Select renderer' '0 1 2 3' 1
    renderer_choice=$REPLY
    case "$renderer_choice" in
        0) return ;;
        2) choices+=(--native) ;;
        3) choices+=(--proton) ;;
    esac
    echo
    echo '--- Resolution ---'
    echo '1) 1280x720: recommended first try'
    echo '2) Primary display size: may freeze on large displays'
    echo '3) Custom width and height'
    resolution_choices='0 1 2 3'
    if [ "$renderer_choice" = 1 ]; then
        echo '4) Fit a 16:9 window above desktop panels (recommended for no decorations)'
        resolution_choices='0 1 2 3 4'
    fi
    echo '0) Back to main menu'
    menu_choice 'Select resolution' "$resolution_choices" 1
    case "$REPLY" in
        0) return ;;
        1) choices+=(--width 1280 --height 720) ;;
        2) choices+=(--display-size) ;;
        4) choices+=(--fit-workarea) ;;
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
        if [ "$renderer_choice" = 1 ]; then
            echo 'No decorations removes the titlebar/frame only; it is NOT fullscreen and does not hide panels.'
            menu_choice 'Remove Zink window decorations? y/n/0=back' 'y n 0' n
            [ "$REPLY" = 0 ] && return
            [ "$REPLY" = n ] || choices+=(--undecorated)
        fi
        if [ "$renderer_choice" = 3 ]; then
            echo 'Proton copies the installed game into Backup/ProtonGame (can take several GB) and uses a separate Wine prefix.'
            echo 'Your native Zink settings remain unchanged. Windows rendering/gameplay are experimental.'
            echo 'Fullscreen can still clip or trap input on some displays; use the ONE-MINUTE test first.'
            menu_choice 'Start Proton fullscreen at this resolution? y/n/0=back' 'y n 0' n
            [ "$REPLY" = 0 ] && return
            [ "$REPLY" = y ] && choices+=(--proton-fullscreen)
            if [ -f "$game/ut2003-winpatch2225.exe" ]; then
                echo 'Found the Windows 2225 self-extracting patch next to System/.'
                echo "Apply it directly over the PRIVATE game copy: $game/Backup/ProtonGame"
                echo 'Uses 7z; no Wine installer or Z: drive space check. Original game stays untouched.'
                echo 'Files replaced in the private copy are backed up under Backup/ProtonWinpatch2225.original.'
                menu_choice 'Apply the Windows 2225 patch to the private copy? y/n/0=back' 'y n 0' n
                [ "$REPLY" = 0 ] && return
                [ "$REPLY" = y ] || choices+=(--skip-winpatch)
            fi
        else
            menu_choice 'Try Escape-on-release? May resize or stall. y/n/0=back' 'y n 0' n
            [ "$REPLY" = 0 ] && return
            [ "$REPLY" = n ] || choices+=(--input-fix)
            menu_choice 'Try Steam SDL12-compat? May stall. y/n/0=back' 'y n 0' n
            [ "$REPLY" = 0 ] && return
            [ "$REPLY" = n ] || choices+=(--sdl-compat)
            echo 'Configuration edits game/user INIs, audio links and launcher. First-run backups remain outside this repository.'
        fi
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

menu_cdkey() {
    local key status
    echo 'Apply your own CD key to the PRIVATE Proton game and registry (not the native game).'
    echo 'The Wine prefix and private cdkey will contain the key; keep Backup/ private.'
    menu_choice '1) Reuse native System/cdkey  2) Enter another key (hidden)  0) Back' '0 1 2' 0
    case "$REPLY" in
        0) return ;;
        1) menu_operation --cdkey-from-native ;;
        2)
            printf 'Enter your own UT2003 CD key (hidden): ' >&2
            if ! IFS= read -rs key; then echo 'Input closed; no key applied.' >&2; return; fi
            echo >&2
            [ -n "$key" ] || { echo 'Empty key; no changes made.' >&2; return; }
            if printf '%s\n' "$key" | bash "$patch/apply.sh" --cdkey-stdin; then
                echo 'CD key applied. Returning to the main menu.'
            else
                status=$?
                echo "CD key application failed (exit $status). Returning to the main menu." >&2
            fi
            unset key
            ;;
    esac
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
        if [ -f "$game/System/.ut2003-renderer" ]; then
            echo "Selected start mode: $(cat "$game/System/.ut2003-renderer")"
        fi
        echo 'Fullscreen and Escape fixes are experimental; a GPU freeze is possible.'
        echo '  1) Configure game (confirmation required)'
        echo '  2) Check 32-bit dependencies (read-only)'
        echo '  3) Restore original Escape binding'
        echo '  4) Restore bundled SDL 1.2'
        echo '  5) Restore original audio'
        echo '  6) Test launch for ONE MINUTE, then return to this menu'
        echo '  7) Use OpenSpy server list (changes only master-server INIs)'
        echo '  8) Restore previous master-server settings'
        echo '  9) Apply your CD key to Proton (private, optional)'
        echo '  0) Exit'
        menu_choice 'Main menu' '0 1 2 3 4 5 6 7 8 9' 0
        case "$REPLY" in
            0) echo 'Exiting setup.'; return ;;
            1) menu_settings configure ;;
            2) menu_settings check ;;
            3) menu_restore 'Escape binding' --restore-input ;;
            4) menu_restore 'bundled SDL' --restore-sdl ;;
            5) menu_restore 'original audio' --restore-audio ;;
            6) menu_test ;;
            7)
                echo 'OpenSpy is an external service. The game will contact utmaster.openspy.net:28902 for server listings (and server advertising).'
                echo 'Only master-server INI keys change; game files and graphics/audio settings stay as they are.'
                menu_choice 'Enable OpenSpy? y/n' 'y n' n
                if [ "$REPLY" = y ]; then menu_operation --openspy; else echo 'No changes made.'; fi
                ;;
            8) menu_restore 'previous master-server settings' --restore-openspy ;;
            9) menu_cdkey ;;
        esac
    done
}
