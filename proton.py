"""Prepare and launch an isolated Windows UT2003 copy with an installed Proton."""

import argparse
import hashlib
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def proton_binary() -> Path:
    override = os.environ.get("UT2003_PROTON")
    if override:
        candidate = Path(override).expanduser()
        if candidate.is_dir():
            candidate /= "proton"
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
        raise ValueError(
            f"UT2003_PROTON does not point to an executable Proton: {candidate}"
        )
    steam = Path.home() / ".local/share/Steam/steamapps/common"
    for name in (
        "Proton 10.0",
        "Proton 11.0",
        "Proton - Experimental",
        "Proton 9.0 (Beta)",
    ):
        candidate = steam / name / "proton"
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    raise ValueError(
        "No Steam Proton found. Install Proton in Steam or set UT2003_PROTON to its proton script."
    )


def steam_root(proton: Path) -> Path:
    override = os.environ.get("STEAM_COMPAT_CLIENT_INSTALL_PATH")
    candidates = (
        [Path(override).expanduser()]
        if override
        else [Path.home() / ".local/share/Steam", Path.home() / ".steam/root"]
    )
    for candidate in candidates:
        if (candidate / "steamapps/common").is_dir():
            return candidate.resolve()
    raise ValueError(
        f"Steam installation not found for {proton}; set STEAM_COMPAT_CLIENT_INSTALL_PATH."
    )


def validate(game: Path) -> tuple[Path, Path]:
    for name in (
        "System/UT2003.exe",
        "System/UT2003.ini",
        "System/Default.ini",
        "System/User.ini",
    ):
        if not (game / name).is_file():
            raise ValueError(f"Windows UT2003 needs {game / name}")
    proton = proton_binary()
    return proton, steam_root(proton)


def win_ini(path: Path, width: int, height: int, fullscreen: bool = False) -> None:
    text = path.read_text()
    lines = text.splitlines(keepends=True)
    sections = {}
    for index, line in enumerate(lines):
        match = re.fullmatch(r"\s*\[([^]]+)\]\s*", line)
        if match:
            sections[match.group(1).lower()] = index
    for name in ("Engine.Engine", "WinDrv.WindowsClient"):
        if name.lower() not in sections:
            raise ValueError(f"{path}: missing [{name}]")
    changes = {
        "Engine.Engine": {
            "RenderDevice": "D3DDrv.D3DRenderDevice",
            "ViewportManager": "WinDrv.WindowsClient",
        },
        "WinDrv.WindowsClient": {
            "WindowedViewportX": str(width),
            "WindowedViewportY": str(height),
            "FullscreenViewportX": str(width),
            "FullscreenViewportY": str(height),
            "StartupFullscreen": str(fullscreen),
            "UseFullscreen": str(fullscreen),
        },
    }
    for section, values in sorted(
        changes.items(), key=lambda item: sections[item[0].lower()], reverse=True
    ):
        start = sections[section.lower()] + 1
        end = next(
            (i for i in range(start, len(lines)) if lines[i].startswith("[")),
            len(lines),
        )
        block = lines[start:end]
        for key, value in values.items():
            matches = [
                i
                for i, line in enumerate(block)
                if re.match(rf"^{re.escape(key)}\s*=", line, re.IGNORECASE)
            ]
            if matches:
                for i in matches:
                    block[i] = f"{key}={value}\n"
            else:
                block.append(f"{key}={value}\n")
        lines[start:end] = block
    if "".join(lines) != text:
        path.write_text("".join(lines))


def prepare(
    game: Path, patch: Path, width: int, height: int, fullscreen: bool = False
) -> Path:
    backup = game / "Backup"
    backup.mkdir(mode=0o700, exist_ok=True)
    backup.chmod(0o700)
    target = backup / "ProtonGame"
    staging = backup / "ProtonGame.incomplete"
    if staging.exists():
        raise ValueError(
            f"Incomplete copy at {staging}; inspect/remove it before retrying"
        )
    if not target.exists():
        staging.mkdir(mode=0o700)
        print(
            f"Copying game to {target} (can require several GB; never included in Git).",
            flush=True,
        )
        try:
            for item in game.iterdir():
                if item.name in ("Backup", patch.name, "GLCache"):
                    continue
                subprocess.run(
                    [
                        "cp",
                        "-a",
                        "--reflink=auto",
                        "--",
                        str(item),
                        str(staging / item.name),
                    ],
                    check=True,
                )
            for name in ("System/UT2003.ini", "System/Default.ini"):
                win_ini(staging / name, width, height, fullscreen)
            staging.rename(target)
        except Exception:
            print(f"Copy failed; inspect/remove {staging} to retry.", file=sys.stderr)
            raise
    else:
        for name in ("System/UT2003.exe", "System/UT2003.ini", "System/Default.ini"):
            if not (target / name).is_file():
                raise ValueError(f"Incomplete Proton copy: {target / name}")
        for name in ("System/UT2003.ini", "System/Default.ini"):
            win_ini(target / name, width, height, fullscreen)
    print(f"Proton game copy: {target} (native game files unchanged)")
    return target


def proton_env(game: Path, steam: Path) -> dict[str, str]:
    compat = game / "Backup/ProtonCompatData"
    # Proton locks pfx.lock in this directory before it creates the prefix.
    compat.mkdir(mode=0o700, parents=True, exist_ok=True)
    env = os.environ.copy()
    for key in ("LD_LIBRARY_PATH", "LD_PRELOAD", "WINEPREFIX", "WINEDLLOVERRIDES"):
        env.pop(key, None)
    env.update(
        STEAM_COMPAT_DATA_PATH=str(compat),
        STEAM_COMPAT_CLIENT_INSTALL_PATH=str(steam),
        STEAM_COMPAT_APP_ID="0",
    )
    return env


def install_winpatch(game: Path, copy: Path) -> None:
    installer = game / "ut2003-winpatch2225.exe"
    if not installer.is_file():
        print(f"No {installer.name} next to System/; skipping optional Windows patch.")
        return
    if not shutil.which("7z"):
        raise ValueError(
            "7z is required to apply the Windows 2225 archive without Wine"
        )
    digest = hashlib.sha256(installer.read_bytes()).hexdigest()
    marker = copy / ".ut2003-winpatch2225.sha256"
    if marker.is_file() and marker.read_text().strip() == digest:
        print("Windows 2225 patch already applied to the private copy; skipping.")
        return
    # This WinZip self-extractor embeds UT2003-Patch/. Extract it without
    # launching the EXE: Wine's Z: drive incorrectly reports 0 MB free.
    with tempfile.TemporaryDirectory(
        prefix="Winpatch2225-", dir=game / "Backup"
    ) as tmp:
        result = subprocess.run(
            ["7z", "x", "-y", "-bd", f"-o{tmp}", str(installer)],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        if result.returncode:
            raise ValueError(
                f"Could not extract Windows patch: {(result.stdout + result.stderr)[-2000:]}"
            )
        extracted = Path(tmp) / "UT2003-Patch"
        allowed = {"System", "Benchmark", "Help", "Textures", "Web"}
        if not extracted.is_dir() or not (extracted / "System/UT2003.exe").is_file():
            raise ValueError(
                "Windows patch archive is missing UT2003-Patch/System/UT2003.exe"
            )
        if {item.name for item in Path(tmp).iterdir()} != {"UT2003-Patch"}:
            raise ValueError("Unexpected top-level files in Windows patch archive")
        if any(
            item.name not in allowed or not item.is_dir() or item.is_symlink()
            for item in extracted.iterdir()
        ):
            raise ValueError("Unexpected folder in Windows patch archive")
        files = []
        for source in extracted.rglob("*"):
            if source.is_symlink() or not (source.is_dir() or source.is_file()):
                raise ValueError(f"Unexpected file in Windows patch archive: {source}")
            relative = source.relative_to(extracted)
            for part in (relative, *relative.parents):
                if part != Path(".") and (copy / part).is_symlink():
                    raise ValueError(
                        f"Symlink in private patch destination: {copy / part}"
                    )
            target = copy / relative
            if source.is_dir() and target.exists() and not target.is_dir():
                raise ValueError(f"Not a directory in private game: {target}")
            if source.is_file():
                if target.exists() and not target.is_file():
                    raise ValueError(f"Not a file in private game: {target}")
                files.append((source, relative))
        # Preserve the original private-copy files outside Git before overwriting.
        backup = game / "Backup/ProtonWinpatch2225.original"
        if backup.is_symlink():
            raise ValueError(f"Refusing symlinked backup directory: {backup}")
        backup.mkdir(mode=0o700, exist_ok=True)
        backup.chmod(0o700)
        for _, relative in files:
            original = copy / relative
            saved = backup / relative
            if original.is_file() and not saved.exists():
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(original, saved)
        for source, relative in files:
            target = copy / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        marker.write_text(digest + "\n")
    print(f"Windows 2225 patch applied to {copy} (original game unchanged).")
    print(f"Previous private-copy files: {backup}")


def run(game: Path, args: list[str]) -> None:
    copy = game / "Backup/ProtonGame/System"
    if not (copy / "UT2003.exe").is_file():
        raise ValueError("Proton copy missing. Select Proton in Configure Game first.")
    marker = game / "System/.ut2003-proton-path"
    if "UT2003_PROTON" not in os.environ and marker.is_file():
        os.environ["UT2003_PROTON"] = marker.read_text().strip()
    proton = proton_binary()
    steam = steam_root(proton)
    env = proton_env(game, steam)
    os.chdir(copy)
    os.execve(
        str(proton),
        [
            str(proton),
            "run",
            "./UT2003.exe",
            "ini=UT2003.ini",
            "userini=User.ini",
            *args,
        ],
        env,
    )


def stop(game: Path) -> None:
    """End only Wine/Proton processes belonging to this game's private prefix."""
    compat = str((game / "Backup/ProtonCompatData").resolve())
    prefix = str(Path(compat) / "pfx")

    def matches(pid: int) -> bool:
        try:
            values = (Path("/proc") / str(pid) / "environ").read_bytes().split(b"\0")
        except (OSError, PermissionError):
            return False
        return (
            f"WINEPREFIX={prefix}".encode() in values
            or f"STEAM_COMPAT_DATA_PATH={compat}".encode() in values
        )

    found = []
    for proc in Path("/proc").iterdir():
        if (
            proc.name.isdecimal()
            and int(proc.name) != os.getpid()
            and matches(int(proc.name))
        ):
            found.append(int(proc.name))
    for pid in found:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    if found:
        time.sleep(1)
    for pid in found:
        if matches(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    print(f"Stopped {len(found)} Proton/Wine processes in the UT2003 prefix.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game", type=Path)
    parser.add_argument("--patch", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--install-winpatch", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--stop", action="store_true")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--fullscreen", action="store_true")
    args, game_args = parser.parse_known_args()
    game = args.game.resolve()
    try:
        if args.stop:
            stop(game)
        elif args.run:
            if game_args[:1] == ["--"]:
                game_args.pop(0)
            run(game, game_args)
        else:
            proton, steam = validate(game)
            print(f"Proton: {proton} (Steam: {steam})")
            if not args.check:
                if args.patch is None:
                    parser.error("--patch is required to prepare Proton")
                copy = prepare(
                    game, args.patch.resolve(), args.width, args.height, args.fullscreen
                )
                if args.install_winpatch:
                    install_winpatch(game, copy)
                    for name in ("System/UT2003.ini", "System/Default.ini"):
                        win_ini(copy / name, args.width, args.height, args.fullscreen)
                (game / "System/.ut2003-proton-path").write_text(str(proton) + "\n")
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Proton: {exc}\n")


if __name__ == "__main__":
    main()
