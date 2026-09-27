# UT2003 Linux configuration patch

This directory is intended to be its **own Git repository**. It contains only scripts and documentation: no game executable, maps, assets, CD key, Linux binary distribution, copied user configuration, or backup. The `.gitignore` allowlists the five files that may be committed. The prior full-game backup was removed from this directory.

## Requirements

- An **existing** Unreal Tournament 2003 installation with the native Linux patch already installed (`System/ut2003-bin`, `System/UT2003.ini`, `System/Default.ini`). This repository does not supply copyrighted game files or the native executable. Install those separately from a source you are authorized to use.
- Python 3. For fullscreen under Wayland: Gamescope. Lutris is optional; if used, its `Ubuntu-18.04-i686` runtime supplies the legacy 32-bit `libstdc++.so.5` needed by the game. Launching outside Lutris requires an equivalent 32-bit library.

Place `LinuxPatch/` directly inside the UT2003 game directory and run:

```sh
./LinuxPatch/apply.sh
```

Or run `./LinuxPatch/apply.sh --no-lutris` to avoid changing a matching Lutris launcher. The script works with an existing Linux binary; it does **not** download or overwrite executables or game data. It installs `launch-ut2003.sh` in the game root and sets the game's and active user's INIs to OpenGL and 1280×720 fullscreen. On Wayland the launcher uses Gamescope to fit the game image to the screen; a wider monitor may show side bars. It preserves the current CD key, saves, maps, mods, other user settings, and any existing `padsp32` audio wrapper. Running it twice is safe.

Before the first application, the script saves each INI and any existing launcher **outside `LinuxPatch`**, next to the original with `.pre-linuxpatch` appended. If Lutris needs to be changed, `configure.py` likewise saves a `.pre-linuxpatch` copy of its YAML in your Lutris config directory. Restore those files from their `.pre-linuxpatch` copies if you want to undo the settings. The Git repository never contains these private backups.

**Audio remains unresolved.** The legacy OpenAL backend reported no devices on the tested host; forcing a 32-bit PulseAudio preload caused a crash. This patch does not claim to fix sound or change the installed audio libraries. Graphical launching has to be checked in a desktop session.
