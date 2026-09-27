"""Adjust UT2003's Linux renderer settings without discarding other preferences."""

import argparse
import os
import re
import shutil
from pathlib import Path

SDL = {
    "WindowedViewportX": "1280",
    "WindowedViewportY": "720",
    "FullscreenViewportX": "1280",
    "FullscreenViewportY": "720",
    "MenuViewportX": "1280",
    "MenuViewportY": "720",
    "StartupFullscreen": "True",
    "UseFullscreen": "True",
}


def update_ini(
    path: Path, renderer: str = "zink", width: int = 1280, height: int = 720
) -> None:
    text = path.read_text()
    lines = text.splitlines(keepends=True)
    sections = {}
    current = None
    for index, line in enumerate(lines):
        match = re.fullmatch(r"\[([^]]+)\]\s*", line.strip())
        if match:
            current = match.group(1)
            sections.setdefault(current, []).append(index)
    for section in (
        "Engine.Engine",
        "SDLDrv.SDLClient",
        "OpenGLDrv.OpenGLRenderDevice",
        "ALAudio.ALAudioSubsystem",
    ):
        if section not in sections:
            raise ValueError(f"{path}: missing [{section}]")

    changes = {
        "Engine.Engine": {
            "RenderDevice": "OpenGLDrv.OpenGLRenderDevice",
            "ViewportManager": "SDLDrv.SDLClient",
        },
        "SDLDrv.SDLClient": {
            **SDL,
            "WindowedViewportX": str(width),
            "WindowedViewportY": str(height),
            "FullscreenViewportX": str(width),
            "FullscreenViewportY": str(height),
            "MenuViewportX": str(min(width, height * 4 // 3)),
            "MenuViewportY": str(height),
            "StartupFullscreen": "False" if renderer == "zink" else "True",
            "UseFullscreen": "False" if renderer == "zink" else "True",
        },
        "OpenGLDrv.OpenGLRenderDevice": {"VARSize": "0"},
        "ALAudio.ALAudioSubsystem": {"UseEAX": "False"},
    }
    # Process last sections first to avoid shifting earlier offsets. UT2003.ini
    # can contain two OpenGL sections; the second contains the VARSize setting.
    for section, keys in sorted(
        changes.items(), key=lambda item: sections[item[0]][-1], reverse=True
    ):
        start = sections[section][-1]
        end = next(
            (i for i in range(start + 1, len(lines)) if lines[i].startswith("[")),
            len(lines),
        )
        block = lines[start + 1 : end]
        for key, value in keys.items():
            match = re.compile(rf"^{re.escape(key)}\s*=", re.IGNORECASE)
            positions = [i for i, line in enumerate(block) if match.match(line)]
            if positions:
                for i in positions:
                    block[i] = f"{key}={value}\n"
            else:
                block.append(f"{key}={value}\n")
        lines[start + 1 : end] = block
    updated = "".join(lines)
    if updated != text:
        path.write_text(updated)
    print(f"Configured {path}")


def update_escape(path: Path, width: int, height: int) -> None:
    text = path.read_text()
    replacement = f"Escape=SetRes {width}x{height}w|OnRelease ShowMenu"
    # SetRes runs on key-down and may resize even at the configured dimensions.
    # This experimental binding is opt-in; the engine needs a key-down command
    # before it dispatches OnRelease (as with its ScoreToggle alias).
    pattern = r"(?m)^Escape=(?:ShowMenu|SetRes [0-9]+x[0-9]+w\|OnRelease ShowMenu)$"
    updated = re.sub(pattern, replacement, text, count=1)
    if updated != text:
        path.write_text(updated)
        print(f"Bound Escape on key release in {path}")
    elif not re.search(r"(?m)^Escape=" + re.escape(replacement[7:]) + r"$", text):
        print(f"Kept custom Escape binding in {path}")


def restore_escape(path: Path, backup: Path) -> None:
    if not path.exists() or not backup.exists():
        return
    original = re.search(r"(?m)^Escape=.*$", backup.read_text())
    if original is None:
        return
    text = path.read_text()
    updated = re.sub(r"(?m)^Escape=.*$", lambda _: original.group(), text, count=1)
    if updated != text:
        path.write_text(updated)
        print(f"Restored Escape binding in {path}")


def update_lutris(game: Path, renderer: str = "zink") -> None:
    config_dir = (
        Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        / "lutris/games"
    )
    executables = {str(game / "System/ut2003-bin"), str(game / "launch-ut2003.sh")}
    for path in config_dir.glob("unreal-tournament-2003-*.yml"):
        text = path.read_text()
        # Only alter an absolute executable path belonging to this installation.
        # Relative paths and entries for other installations need manual setup.
        pattern = re.compile(r"(?m)^(\s+exe: )([^\n]+)$")
        match = pattern.search(text)
        if match is None or match.group(2).strip().strip("\"'") not in executables:
            continue
        updated = (
            text[: match.start(2)]
            + str(game / "launch-ut2003.sh")
            + text[match.end(2) :]
        )
        if renderer == "proton":
            # Lutris may pass native-only -opengl; do not force that renderer
            # for the Windows binary (which uses Direct3D through Proton).
            updated = re.sub(
                r"(?m)^(\s+args: )(['\"]?)-opengl( -nogamma)?\2\s*$",
                lambda m: m.group(1) + ("-nogamma" if m.group(3) else "''"),
                updated,
                count=1,
            )
        if updated != text:
            original = path.with_name(path.name + ".pre-linuxpatch")
            if not original.exists():
                shutil.copy2(path, original)
            path.write_text(updated)
            print(f"Updated Lutris: {path} (previous config: {original})")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("game", type=Path)
    parser.add_argument("--no-lutris", action="store_true")
    parser.add_argument("--input-fix", action="store_true")
    parser.add_argument("--no-input-fix", action="store_true")
    parser.add_argument("--restore-input", action="store_true")
    parser.add_argument(
        "--renderer", choices=("zink", "native", "proton"), default="zink"
    )
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    args = parser.parse_args()
    if not (320 <= args.width <= 8192 and 240 <= args.height <= 8192):
        parser.error("width and height must be within 320x240–8192x8192")
    game = args.game.resolve()
    if args.restore_input:
        restore_escape(
            game / "System/User.ini", game / "Backup/System-User.ini.original"
        )
        restore_escape(
            Path.home() / ".ut2003/System/User.ini", game / "Backup/User.ini.original"
        )
        return
    if args.renderer == "proton":
        if not args.no_lutris:
            update_lutris(game, "proton")
        return
    for path in (game / "System/UT2003.ini", game / "System/Default.ini"):
        update_ini(path, args.renderer, args.width, args.height)
    user_ini = Path.home() / ".ut2003/System/UT2003.ini"
    if user_ini.exists():
        update_ini(user_ini, args.renderer, args.width, args.height)
    if args.input_fix and not args.no_input_fix:
        for path in (game / "System/User.ini", Path.home() / ".ut2003/System/User.ini"):
            if path.exists():
                update_escape(path, args.width, args.height)
    if not args.no_lutris:
        update_lutris(game, args.renderer)


if __name__ == "__main__":
    main()
