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

# Preserve existing configuration outside this Git directory on the first run.
for file in System/UT2003.ini System/Default.ini launch-ut2003.sh; do
    if [ -f "$game/$file" ] && [ ! -e "$game/$file.pre-linuxpatch" ]; then
        cp -p -- "$game/$file" "$game/$file.pre-linuxpatch"
    fi
done
user_ini="$HOME/.ut2003/System/UT2003.ini"
if [ -f "$user_ini" ] && [ ! -e "$user_ini.pre-linuxpatch" ]; then
    cp -p -- "$user_ini" "$user_ini.pre-linuxpatch"
fi

cp -p -- "$patch/launch-ut2003.sh" "$game/launch-ut2003.sh"
chmod u+x "$game/launch-ut2003.sh"
python3 "$patch/configure.py" "$game" "$@"
echo 'Linux video settings applied. Launch via launch-ut2003.sh or its Lutris entry.'
echo 'Audio is not fixed by this patch; see LinuxPatch/README.md.'
