"""Apply the user's UT2003 CD key to the isolated Proton game and registry."""

import argparse
import getpass
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from proton import proton_binary, proton_env, steam_root, stop


def apply_key(game: Path, key: str) -> None:
    key = key.strip().upper()
    if not re.fullmatch(r"[A-Z0-9-]{12,40}", key):
        raise ValueError(
            "Invalid CD key format (expected 12–40 letters, digits or hyphens)"
        )
    copy = game / "Backup/ProtonGame/System"
    if not (copy / "UT2003.exe").is_file():
        raise ValueError(
            "Configure Proton first; the private Windows game copy is missing"
        )
    private_key = copy / "cdkey"
    if private_key.is_symlink():
        raise ValueError("Refusing to replace a symlinked private cdkey")
    marker = game / "System/.ut2003-proton-path"
    if "UT2003_PROTON" not in os.environ and marker.is_file():
        os.environ["UT2003_PROTON"] = marker.read_text().strip()
    proton = proton_binary()
    steam = steam_root(proton)
    backup = game / "Backup"
    # Wine's 32-bit registry view can redirect HKLM\Software to Wow6432Node.
    # Write both views so the game's 32-bit Engine.dll can find CDKey.
    reg = (
        "Windows Registry Editor Version 5.00\r\n\r\n"
        "[HKEY_LOCAL_MACHINE\\Software\\Unreal Technology\\Installed Apps\\UT2003]\r\n"
        f'"CDKey"="{key}"\r\n\r\n'
        "[HKEY_LOCAL_MACHINE\\Software\\Wow6432Node\\Unreal Technology\\Installed Apps\\UT2003]\r\n"
        f'"CDKey"="{key}"\r\n'
    )
    fd, name = tempfile.mkstemp(prefix=".ut2003-cdkey-", suffix=".reg", dir=backup)
    try:
        with os.fdopen(fd, "w", encoding="utf-16") as output:
            output.write(reg)
        path = "Z:" + name.replace("/", "\\")
        try:
            result = subprocess.run(
                [str(proton), "run", "regedit", "/S", path],
                cwd=copy,
                env=proton_env(game, steam),
                capture_output=True,
                timeout=60,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            stop(game)
            raise ValueError(
                "Proton registry import timed out; key was not saved to the private game"
            ) from exc
        if result.returncode:
            raise ValueError(
                f"Proton registry import failed (exit {result.returncode}); key was not saved to the private game"
            )
    finally:
        Path(name).unlink(missing_ok=True)
    # Keep the private game's cdkey in sync for tools that read a file instead
    # of the registry. Never touch the native System/cdkey.
    fd, name = tempfile.mkstemp(prefix=".cdkey-", dir=copy)
    try:
        with os.fdopen(fd, "w", encoding="ascii") as output:
            output.write(key + "\n")
        os.replace(name, private_key)
    finally:
        Path(name).unlink(missing_ok=True)
    print("CD key applied to the private Proton registry and game copy (not printed).")
    print("The private prefix and cdkey file contain your key; never publish Backup/.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game", type=Path)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--from-native", action="store_true")
    source.add_argument("--stdin", action="store_true")
    source.add_argument("--prompt", action="store_true")
    args = parser.parse_args()
    game = args.game.resolve()
    try:
        if args.from_native:
            native = game / "System/cdkey"
            if not native.is_file():
                raise ValueError("No native System/cdkey found; use --prompt instead")
            key = native.read_text().strip()
        elif args.stdin:
            key = sys.stdin.readline().strip()
        else:
            if not sys.stdin.isatty():
                raise ValueError("A terminal is required for a hidden prompt")
            key = getpass.getpass("Your UT2003 CD key (hidden): ").strip()
        apply_key(game, key)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"CD key: {exc}\n")


if __name__ == "__main__":
    main()
