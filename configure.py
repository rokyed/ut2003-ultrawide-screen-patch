#!/usr/bin/env python3
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


def update_ini(path: Path, renderer: str = "zink") -> None:
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
            match = re.compile(rf"^{re.escape(key)}\s*=", re.I)
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


def update_lutris(game: Path) -> None:
    config_dir = (
        Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        / "lutris/games"
    )
    for path in config_dir.glob("unreal-tournament-2003-*.yml"):
        text = path.read_text()
        pattern = re.compile(
            r"(?m)^(  exe: )(.*(?:/System/ut2003-bin|/launch-ut2003\.sh))\s*$"
        )
        if not pattern.search(text) or "/UT2003/" not in text:
            continue
        updated = pattern.sub(
            lambda match: match.group(1) + str(game / "launch-ut2003.sh"), text, count=1
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
    parser.add_argument("--renderer", choices=("zink", "native"), default="zink")
    args = parser.parse_args()
    game = args.game.resolve()
    for path in (game / "System/UT2003.ini", game / "System/Default.ini"):
        update_ini(path, args.renderer)
    user_ini = Path.home() / ".ut2003/System/UT2003.ini"
    if user_ini.exists():
        update_ini(user_ini, args.renderer)
    if not args.no_lutris:
        update_lutris(game)


if __name__ == "__main__":
    main()
