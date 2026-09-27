# UT2003 Linux configuration patch

This directory is intended to be its **own Git repository**. It contains only scripts and documentation: no game executable, maps, assets, CD key, Linux binary distribution, copied user configuration, or backup. The `.gitignore` allowlists the five files that may be committed. The prior full-game backup was removed from this directory.

## Requirements

- An **existing** Unreal Tournament 2003 installation with the native Linux patch already installed (`System/ut2003-bin`, `System/UT2003.ini`, `System/Default.ini`). This repository does not supply copyrighted game files or the native executable. Install those separately from a source you are authorized to use.
- Python 3, `file`, **32-bit Mesa Zink** and Mesa GLX, **32-bit Vulkan support for your GPU**, **32-bit OpenAL Soft** (`libopenal.so.1`), and a 32-bit `libstdc++.so.5`. Lutris's `Ubuntu-18.04-i686` runtime can supply the latter; an installed system copy works too. Gamescope is optional for the native-renderer fallback. Lutris is optional.

Place `LinuxPatch/` directly inside the UT2003 game directory and run:

```sh
./LinuxPatch/apply.sh
```

Or run `./LinuxPatch/apply.sh --no-lutris` to avoid changing a matching Lutris launcher. The script works with an existing Linux binary; it does **not** download or overwrite executables or game data. It installs `launch-ut2003.sh` in the game root and sets the game's and active user's INIs to the Linux OpenGL renderer at **1280×720 windowed**. Mesa Zink translates the game's OpenGL calls to Vulkan on the GPU; UT2003 itself has no native Vulkan renderer. The tested Zink path uses Xwayland **without Gamescope**: Zink launched successfully windowed on the NVIDIA GTX 1080, but Zink inside Gamescope crashed on this host. Zink has not been proven to fix intermittent element flicker.

To revert to the previous NVIDIA OpenGL and Gamescope fullscreen setup, run `./LinuxPatch/apply.sh --native` (or add `--no-lutris`). This changes the renderer marker and fullscreen settings; no game binaries change. To temporarily run the installed Zink configuration with NVIDIA OpenGL _without_ changing the INIs, launch with `UT2003_RENDERER=native ./launch-ut2003.sh -opengl -nogamma`; expect a window if the INIs are still configured for Zink.

For sound, the script links the game's `System/openal.so` and `System/libopenal.so` to the host's **32-bit OpenAL Soft**, which can output to PulseAudio/PipeWire or ALSA, instead of the bundled legacy OpenAL that reported no devices. It disables EAX and launches without the old `padsp32` preload. It makes a link to Lutris's 32-bit `libstdc++.so.5` in `System/` if needed, so host audio libraries are not mixed with Lutris's obsolete PulseAudio libraries. To choose a different 32-bit OpenAL Soft library, set `UT2003_OPENAL_SOFT` to its absolute path when applying. No libraries are bundled in Git. Run the script again to reapply the settings after changes to the installation.

Before the first application, the script saves each INI, any original `System/openal.so` and `System/libopenal.so`, and any existing launcher **outside `LinuxPatch`**, next to the original with `.pre-linuxpatch` appended. Renderer selection is stored as a small text marker in `System/.ut2003-renderer` (outside Git). If Lutris needs to be changed, `configure.py` likewise saves a `.pre-linuxpatch` copy of its YAML in your Lutris config directory. The Git repository never contains these private backups, CD keys, or game libraries.

To undo **just the OpenAL library replacement**, run `./LinuxPatch/apply.sh --restore-audio`. Restore other settings from their `.pre-linuxpatch` copies if needed. A bounded desktop launch confirmed `ALAudio: subsystem initialized` with OpenAL Soft 1.24.2. The log also reports `Sound is too short for streaming: ..\\Music\\KR-UT2003-Menu.ogg`, so menu music may still be missing even if game sound effects work. Audio output cannot be heard or confirmed by this patch script; test it in-game. The bounded launch stops the game with a signal after the test period.
