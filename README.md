# Unreal Tournament 2003 — Linux setup

`ut2003-ultrawide-screen-patch` configures an **existing UT2003 install** for native windowed Zink (OpenGL via Vulkan), or optionally the Windows executable through Proton, plus optional OpenSpy multiplayer. **No game, executable, assets, CD key, or system libraries are included.** Obtain and install the game separately.

## Get started

Place this whole repository folder **inside the game directory**, next to `System/`. Its folder name can be `ut2003-ultrawide-screen-patch` or `LinuxPatch`.

```sh
cd /path/to/UT2003/ut2003-ultrawide-screen-patch
./apply.sh
```

In the menu: **1** configure → **6** test the game for **one minute** → **0** exit. Choose **2** for a read-only dependency check. Actions return to the main menu; changes and the test launch require confirmation. To use Lutris, select `<game directory>/launch-ut2003.sh` as its executable if it was not updated automatically.

**Native needs:** `System/ut2003-bin`, original Linux INIs/SDL, `bash`, Python 3, `file`, 32-bit Mesa Zink/Vulkan (or choose native OpenGL), 32-bit OpenAL Soft and `libstdc++.so.5`, plus X11/Xwayland. `./apply.sh --check` checks files, not gameplay; `./apply.sh --help` lists flags and runtime overrides.

**Window size:** Default is **1280×720**. For a larger window that fits above your taskbar, choose **Configure → Zink → Fit a 16:9 window above desktop panels → Remove decorations**, or run `./apply.sh --fit-workarea --undecorated`. This reads X11's usable work area, leaves a margin, and sets a matching game resolution. It needs `xrandr` and `xprop` for sizing and `xdotool` for window detection; `--decorated` restores the normal frame. Removing decorations is **not fullscreen** and will not hide the panel. A full-height 1920×1080 window cannot fit above a panel on a 1080-high desktop. You can also set a custom resolution (`--width 2560 --height 1080`), but fullscreen can clip or freeze and the menu is **not reliably 4:3**. The Escape and SDL compatibility options are experimental. No Vulkan-native game renderer is provided. Sound, rendering, and online play have not been verified on every system.

## Proton (optional)

Choose **Configure → Proton** or run `./apply.sh --proton`; requires `System/UT2003.exe` and an installed Steam Proton (override with `UT2003_PROTON=/path/to/proton`). This makes a **private Windows game copy** in `Backup/ProtonGame` and a separate prefix in `Backup/ProtonCompatData`, possibly using **several GB**. Neither is in Git. If `ut2003-winpatch2225.exe` is beside `System/`, Configure offers to **extract and apply it directly to the private copy** with `7z` (CLI `--proton` does so by default; `--skip-winpatch` opts out). No Wine installer window or misleading `Z:` free-space check. Replaced private-copy files are saved in `Backup/ProtonWinpatch2225.original`; later runs skip the same patch. The EXE is not bundled here. A matching Lutris entry keeps its script runner and points to `launch-ut2003.sh`; native-only `-opengl` is removed. Use menu **9** to apply your own CD key to the private Proton registry (reuse native key or type one hidden); CLI: `./apply.sh --cdkey-from-native` or `./apply.sh --cdkey`. Your key remains in the private prefix and cdkey file under `Backup/`—never share those. **Proton fullscreen:** choose it in Configure, or run `./apply.sh --proton --proton-fullscreen --width 2560 --height 1080`; use `--proton-windowed` to switch back. Fullscreen/input behavior is unverified: use menu **6** for a one-minute game trial first. Select **Zink** to switch back; the native INIs are not changed by Proton setup. Windows gameplay is not yet verified.

## OpenSpy servers (optional)

Choose **7** in the menu or run `./apply.sh --openspy`. This sets UT2003's master-server INI entries to **`utmaster.openspy.net:28902`** (one active server) for browsing/hosting. Choose **8** or run `./apply.sh --restore-openspy` to restore the previous entries. OpenSpy is an independent online service; enabling it changes no graphics or audio settings and does not fix launch freezes. See [OpenSpy's UT2 guide](https://openspy.net/howto/ut2k-engine/ut2).

## If the game locks your controls

**Use menu option 6 first:** it stops the game after **60 seconds** (TERM, then KILL 3 seconds later if necessary). This is not a guarantee against a GPU/compositor hang. You can also run `./test-launch.sh` directly. If input remains trapped, press **Ctrl+Alt+F3**, log in as the same user, and run:

```sh
cd /path/to/UT2003/ut2003-ultrawide-screen-patch
bash recover-ut2003.sh
```

Return to your graphical session with your desktop's VT shortcut (often Ctrl+Alt+F1 or F2). The recovery script stops this installation's native game and any processes using its private Proton prefix.

## Undo / sharing

The first application keeps backups **outside this repository**, next to changed INIs (`.pre-linuxpatch`) or in the game's `Backup/`. Backups are not refreshed on later runs. The menu restores Escape, SDL, audio, or OpenSpy separately (options **3**, **4**, **5**, **8**); there is **no one-command full uninstall**. Restore other `.pre-linuxpatch` files manually if needed. Do not run the patch as root.

Only publish this repository's scripts and README. **Never commit the parent game directory, `Backup/`, `System/cdkey`, logs, personal INIs, or runtime libraries.** Run `python3 test_patch.py` for offline tests. The `.gitignore` allowlists patch files only.
