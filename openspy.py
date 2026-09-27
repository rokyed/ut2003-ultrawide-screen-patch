"""Opt-in OpenSpy master-server configuration for native UT2003."""

import argparse
import re
import shutil
from collections.abc import Mapping
from pathlib import Path

SECTION = "IpDrv.MasterServerLink"
HOST = "utmaster.openspy.net"
PORT = "28902"
KEYS = ("CurrentMasterServer",) + tuple(
    f"{name}[{index}]"
    for index in range(5)
    for name in ("MasterServerPort", "MasterServerAddress")
)
SETTINGS = {"CurrentMasterServer": "0"}
for index in range(5):
    SETTINGS[f"MasterServerPort[{index}]"] = PORT if index == 0 else "0"
    SETTINGS[f"MasterServerAddress[{index}]"] = HOST if index == 0 else ""


def master_section(text: str, path: Path) -> tuple[list[str], int, int]:
    lines = text.splitlines(keepends=True)
    headers = [
        (i, match.group(1))
        for i, line in enumerate(lines)
        if (match := re.fullmatch(r"\s*\[([^]]+)\]\s*", line))
    ]
    matches = [i for i, name in headers if name.lower() == SECTION.lower()]
    if len(matches) != 1:
        raise ValueError(f"{path}: expected exactly one [{SECTION}] section")
    start = matches[0] + 1
    end = next((i for i, _ in headers if i >= start), len(lines))
    return lines, start, end


def replace_keys(text: str, path: Path, values: Mapping[str, str | None]) -> str:
    lines, start, end = master_section(text, path)
    keys = {key.lower(): key for key in values}
    block = []
    seen = set()
    for line in lines[start:end]:
        match = re.match(r"^\s*([^=]+?)\s*=", line)
        name = match.group(1).strip().lower() if match else ""
        if name not in keys:
            block.append(line)
        elif name not in seen and values[keys[name]] is not None:
            block.append(f"{keys[name]}={values[keys[name]]}\n")
            seen.add(name)
        else:
            # Drop duplicates of managed keys, and keys absent in the backup.
            seen.add(name)
    for key, value in values.items():
        if key.lower() not in seen and value is not None:
            block.append(f"{key}={value}\n")
    lines[start:end] = block
    return "".join(lines)


def saved_keys(text: str, path: Path) -> dict[str, str | None]:
    lines, start, end = master_section(text, path)
    values: dict[str, str | None] = dict.fromkeys(KEYS)
    lookup = {key.lower(): key for key in KEYS}
    for line in lines[start:end]:
        match = re.match(r"^\s*([^=]+?)\s*=\s*(.*?)\s*$", line)
        if match and match.group(1).strip().lower() in lookup:
            values[lookup[match.group(1).strip().lower()]] = match.group(2)
    return values


def locations(game: Path) -> tuple[tuple[Path, Path], ...]:
    backup = game / "Backup"
    return (
        (game / "System/UT2003.ini", backup / "OpenSpy-System-UT2003.ini.original"),
        (game / "System/Default.ini", backup / "OpenSpy-System-Default.ini.original"),
        (
            Path.home() / ".ut2003/System/UT2003.ini",
            backup / "OpenSpy-User-UT2003.ini.original",
        ),
    )


def apply(game: Path) -> None:
    edits = []
    for path, backup in locations(game):
        if not path.exists():
            if path.parent == game / "System":
                raise FileNotFoundError(path)
            continue
        text = path.read_text()
        updated = replace_keys(text, path, SETTINGS)
        if text != updated:
            edits.append((path, backup, updated))
    if not edits:
        print("OpenSpy master server already configured; no files changed.")
        return
    backup_dir = game / "Backup"
    backup_dir.mkdir(mode=0o700, exist_ok=True)
    for path, backup, updated in edits:
        if not backup.exists():
            shutil.copy2(path, backup)
            backup.chmod(0o600)
        path.write_text(updated)
        print(f"Configured OpenSpy in {path} (backup: {backup})")


def restore(game: Path) -> None:
    edits = []
    for path, backup in locations(game):
        if not backup.exists():
            continue
        if not path.exists():
            raise FileNotFoundError(path)
        original = saved_keys(backup.read_text(), backup)
        updated = replace_keys(path.read_text(), path, original)
        edits.append((path, updated))
    if not edits:
        print("No OpenSpy backups found; nothing to restore.")
        return
    for path, updated in edits:
        if path.read_text() != updated:
            path.write_text(updated)
            print(f"Restored master-server settings in {path}")
        else:
            print(f"Master-server settings already restored in {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game", type=Path)
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    game = args.game.resolve()
    try:
        if args.restore:
            restore(game)
        else:
            apply(game)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"OpenSpy: {exc}\n")


if __name__ == "__main__":
    main()
