# UT2003 Linux configuration patch

Scripts for an **already installed, native Linux Unreal Tournament 2003**. This repository does **not** contain or install the game, its native patch, libraries, assets, or a CD key. Obtain those separately from sources you are authorized to use. The patch configures OpenGL-over-Vulkan via Mesa Zink, host 32-bit OpenAL Soft, and a windowed SDL display as a starting point—not a guaranteed fullscreen or input fix.

## Known limits (read before installing)

- The 32-bit UT2003 binary is old and behavior varies by GPU driver, desktop and display server. On the development machine (KDE Wayland/Xwayland, NVIDIA GTX 1080), SDL fullscreen rendered only the **top-left quadrant**; Zink + Gamescope crashed; KWin borderless fullscreen stalled at the intro. A later **windowed** Zink test at 2560×1080 also stalled before the menu. Do **not** expect working fullscreen from these scripts on every machine.
- A custom window size allows ultrawide gameplay _if the game launches_, but `MenuViewport` does not reliably letterbox the menu. 4:3 menus combined with ultrawide gameplay are **not solved**.
- Escape-on-release is an **opt-in experiment**, not a confirmed input fix: it runs a `SetRes` command on key-down, which may resize or stall the game. Default installation does not touch Escape bindings; if a previous version already changed yours, run `./LinuxPatch/apply.sh --restore-input` to undo it.
- Sound initialization with OpenAL Soft was observed, **not audibly verified**. The game's menu music may fail independently (`Sound is too short for streaming`).

## Prerequisites

1. A complete UT2003 installation with the **native Linux executable** `System/ut2003-bin`, `System/UT2003.ini`, `System/Default.ini`, and the game's original SDL 1.2 library. A Windows-only install is insufficient. Do not distribute these files with this patch.
2. Linux x86 32-bit (i686) runtime support; `bash`, Python 3, `file`, and a working X11/Xwayland session for the bundled SDL. You must be able to run 32-bit applications; a 64-bit library cannot replace a 32-bit one.
3. 32-bit OpenAL Soft (`libopenal.so.1`) and 32-bit `libstdc++.so.5` (the latter may come from Lutris's `Ubuntu-18.04-i686` runtime). For default Zink rendering, also install the **32-bit** Mesa Zink/GLX driver and working **32-bit Vulkan driver** for your GPU. Package names vary by distribution; installing 64-bit Mesa/Vulkan alone is not enough.
4. Optional: `xrandr` for automatic primary-display resolution detection (otherwise 1280×720); `zenity` for an interactive CD-key prompt (otherwise enter your own key in `System/cdkey`); Lutris if you want its entry updated. Experimental borderless mode additionally needs `wmctrl` and `xdotool`; experimental Gamescope SDL mode requires `gamescope`.

The installer checks the existence and ELF architecture of candidate Zink and OpenAL libraries; it **cannot** check actual Vulkan compatibility or visual/audio correctness. Library search defaults cover `/usr/lib`, `/usr/lib/i386-linux-gnu`, `/usr/lib32` (as appropriate). Override nonstandard paths with `UT2003_ZINK_DRIVER=/absolute/path/to/zink_dri.so`, `UT2003_OPENAL_SOFT=/absolute/path/to/libopenal.so.1`, or `UT2003_LIBSTDCXX_SO=/absolute/path/to/libstdc++.so.5` when running `apply.sh`. The latter normally comes from `~/.local/share/lutris/runtime/Ubuntu-18.04-i686/`. If preflight reports a missing library, install it from your distribution or pass the correct 32-bit path; no runtime is downloaded by this patch.

## Install and launch

Put this **entire** `LinuxPatch/` directory directly under the game directory, alongside `System/`. From a terminal, run the guided installer (replace the directory with your own path):

```sh
cd /path/to/UT2003
./LinuxPatch/apply.sh
./launch-ut2003.sh
```

The wizard explains known limitations, offers a **read-only dependency check**, a recommended 1280×720 starting size or custom dimensions, renderer choice, optional Lutris integration, and experimental input/SDL options. It shows a summary before proceeding. **Configure and restore actions default to No at the confirmation prompt; pressing Enter will not apply changes.** A closed input stream cancels the operation. Restoration of individual components is also available in the wizard. If launched without arguments from a script without terminal input, it exits rather than silently modifying files. Use `--help` for all flags; to automate, supply flags explicitly, for example:

```sh
./LinuxPatch/apply.sh --check
./LinuxPatch/apply.sh --width 1280 --height 720 --no-lutris
```

`--interactive` starts the wizard even if standard input is piped, primarily for testing. Flags otherwise bypass the wizard and make changes **without a confirmation prompt**; use `--check` first in automation.

Use `--width 2560 --height 1080` (or any width 320–8192 and height 240–8192) for a custom window. Without dimensions, `apply.sh` uses the primary `xrandr` output if available, otherwise 1280×720. **Start with a modest window size** if a large one stalls. The launcher starts the game from `System/` so its relative asset paths work. Pass game arguments after the launcher name if needed. The script can be rerun; it saves originals on the first application, not on each subsequent run. Use `--no-lutris` to avoid changing a matching Lutris entry. For Lutris, select `<game directory>/launch-ut2003.sh` as the executable yourself if its existing entry was not updated (only entries with an absolute executable path to **this installation** are changed).

The launcher prompts for your **own** CD key only if `System/cdkey` is missing/empty and `zenity` is available. Never commit or share that file. It clears inherited `LD_LIBRARY_PATH` and `LD_PRELOAD` to avoid mixing host audio with older Lutris libraries; if your system needs a custom library path, install dependencies where the dynamic loader can find them instead.

| Option / environment                        | Effect                                                                                                                                                                                                      |
| ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--check`                                   | Check essential files and libraries; do not change anything. Add `--native` to check without Zink.                                                                                                          |
| `--native`                                  | Use host OpenGL and request SDL fullscreen; **may clip**. Default is Zink in SDL windowed mode.                                                                                                             |
| `--no-lutris`                               | Leave Lutris configurations alone.                                                                                                                                                                          |
| `--input-fix`                               | Opt into experimental Escape binding; `--no-input-fix` (default) leaves it alone.                                                                                                                           |
| `--sdl-compat`                              | Experiment with Steam's 32-bit SDL12-compat/SDL2; `--original-sdl` (default) keeps bundled SDL. Set `UT2003_SDL_COMPAT_DIR` to a directory containing both 32-bit libraries if Steam uses a different path. |
| `UT2003_BORDERLESS=1 ./launch-ut2003.sh`    | Experimental KWin borderless mode **only at the primary output's exact resolution**; stalled on the development host.                                                                                       |
| `UT2003_RENDERER=native ./launch-ut2003.sh` | Temporarily change launch environment; does _not_ change the saved INI fullscreen setting.                                                                                                                  |
| `UT2003_GAMESCOPE_SDL=1 ./launch-ut2003.sh` | Experimental native-renderer Gamescope SDL backend. Use with `--native` configuration; unverified visually.                                                                                                 |

Mesa Zink translates OpenGL to Vulkan; UT2003 has **no native Vulkan renderer**. The default Zink launcher sets `SDL_VIDEODRIVER=x11` and clears `WAYLAND_DISPLAY` to use Xwayland on Wayland desktops. For a native OpenGL trial, run `./LinuxPatch/apply.sh --native` and relaunch. This changes saved settings and can trigger the fullscreen viewport issue. Reapply without `--native` to return to windowed Zink.

## Changes and rollback

`apply.sh` writes the game's `System/UT2003.ini` and `System/Default.ini`, any existing `~/.ut2003/System/UT2003.ini`, replaces `System/openal.so` / `System/libopenal.so` with symlinks to host OpenAL Soft, may link `System/libstdc++.so.5` to Lutris's runtime, installs `<game directory>/launch-ut2003.sh`, and stores renderer/resolution markers under `System/`. It modifies **only an exact matching Lutris executable entry**, unless `--no-lutris` is used. No game executable or asset is modified. Avoid running as root; files are edited under your user account.

The first run saves INIs, audio libraries, the launcher, and an updated Lutris YAML as adjacent `.pre-linuxpatch` files **outside this repository**. Experimental SDL and input originals are saved under `<game directory>/Backup/` (which must also remain outside Git). Back up your own installation and user configuration before trying optional features; backups are not refreshed on subsequent runs.

- `./LinuxPatch/apply.sh --restore-input` restores only the original Escape bindings from `Backup/`. Reapplying with `--no-input-fix` does _not_ undo an already changed binding.
- `./LinuxPatch/apply.sh --restore-sdl` restores the backed-up bundled SDL after trying `--sdl-compat`.
- `./LinuxPatch/apply.sh --restore-audio` restores the backed-up legacy audio library; sound may stop working. These commands do **not** undo all other settings.
- For full manual rollback, stop the game, restore the relevant `.pre-linuxpatch` files to their original names (including your home-directory INI and Lutris YAML if changed), remove the patch-created renderer/resolution markers, and restore any SDL/input backup from `Backup/`. Only remove symlinks you have confirmed this patch created. There is no automatic one-command full uninstall.

## Troubleshooting

- **Game does not start / taskbar icon only:** run `./LinuxPatch/apply.sh --check`; try `--width 1280 --height 720`, launch from a terminal, and inspect `~/.ut2003/System/UT2003.log`. A log ending at `Init: Name subsystem initialized` was observed on the development machine; this patch does not yet have a verified fix. Check that the 32-bit GPU driver works in the current session.
- **Top-left-quarter viewport:** do not use SDL exclusive fullscreen on affected setups. Reapply without `--native` and keep `UT2003_BORDERLESS` unset. Do not force a smaller game window to fullscreen in your compositor.
- **No audio:** verify the target of `System/openal.so` is a 32-bit library and check `ALAudio` messages in the log. OpenAL initialization does not guarantee audible sound; confirm your system's default audio output and game sound settings.
- **Escape toggles twice or stalls:** if you used `--input-fix`, run `./LinuxPatch/apply.sh --restore-input` and test the original binding. GUI handling of Escape can differ from in-game key bindings.
- **Lutris launches another executable:** change _that installation's_ Lutris executable to the generated `launch-ut2003.sh`. The patch deliberately avoids editing ambiguous/relative executable paths.

## Sharing safely

Treat `LinuxPatch/` as a standalone Git repository. Its `.gitignore` allowlists only patch scripts, the offline `test_patch.py`, README, and ignore file. Run `python3 LinuxPatch/test_patch.py` from the game directory (or `python3 test_patch.py` from inside `LinuxPatch/`) to test configuration changes in temporary fixtures without touching an installed game. Check `git status --short` and `git ls-files` inside `LinuxPatch/` before publishing. **Do not commit** the parent game directory, `Backup/`, `System/cdkey`, screenshots/logs, personal INIs, or any third-party runtime binaries. A clone of this repo is self-contained as a _configuration patch_, but it cannot run without each recipient's separately installed, legally obtained game and system libraries.
