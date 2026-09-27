"""Offline tests; never touch an installed game."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).with_name("configure.py")
OPENSPY = Path(__file__).with_name("openspy.py")
TEMPLATE = """[Engine.Engine]
RenderDevice=old
ViewportManager=old
[SDLDrv.SDLClient]
WindowedViewportX=640
[OpenGLDrv.OpenGLRenderDevice]
VARSize=256
[ALAudio.ALAudioSubsystem]
UseEAX=True
[IpDrv.MasterServerLink]
LANPort=11777
CurrentMasterServer=2
MasterServerPort[0]=28902
MasterServerAddress[0]=ut2003master1.epicgames.com
MasterServerPort[1]=28902
MasterServerAddress[1]=ut2003master2.epicgames.com
MasterServerPort[2]=0
MasterServerAddress[2]=
"""


class PatchTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.game = base / "Game"
        (self.game / "System").mkdir(parents=True)
        (self.game / "Backup").mkdir()
        self.home = base / "home"
        (self.home / ".ut2003/System").mkdir(parents=True)
        for path in (
            self.game / "System/UT2003.ini",
            self.game / "System/Default.ini",
            self.home / ".ut2003/System/UT2003.ini",
        ):
            path.write_text(TEMPLATE)
        self.controls = self.home / ".ut2003/System/User.ini"
        self.controls.write_text("Escape=ShowMenu\nOther=Keep\n")
        (self.game / "Backup/User.ini.original").write_text(self.controls.read_text())
        self.lutris = self.home / ".config/lutris/games"
        self.lutris.mkdir(parents=True)

    def run_config(self, *args):
        env = dict(
            os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config")
        )
        subprocess.run(
            [sys.executable, str(SCRIPT), str(self.game), *args],
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

    def run_openspy(self, *args):
        env = dict(os.environ, HOME=str(self.home))
        return subprocess.run(
            [sys.executable, str(OPENSPY), str(self.game), *args],
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_openspy_apply_restore_preserves_other_settings(self):
        self.run_openspy()
        for path in (
            self.game / "System/UT2003.ini",
            self.game / "System/Default.ini",
            self.home / ".ut2003/System/UT2003.ini",
        ):
            text = path.read_text()
            self.assertIn("CurrentMasterServer=0\n", text)
            self.assertIn("MasterServerAddress[0]=utmaster.openspy.net\n", text)
            self.assertIn("MasterServerPort[0]=28902\n", text)
            self.assertIn("MasterServerPort[1]=0\n", text)
            self.assertIn("MasterServerAddress[1]=\n", text)
            self.assertIn("LANPort=11777\n", text)
        backup = self.game / "Backup/OpenSpy-System-UT2003.ini.original"
        self.assertEqual(backup.read_text(), TEMPLATE)
        self.run_openspy()
        self.assertEqual(backup.read_text(), TEMPLATE)
        path = self.game / "System/UT2003.ini"
        path.write_text(path.read_text().replace("LANPort=11777", "LANPort=12345"))
        self.run_openspy("--restore")
        self.assertIn("LANPort=12345\n", path.read_text())
        self.assertIn("CurrentMasterServer=2\n", path.read_text())
        self.assertIn(
            "MasterServerAddress[0]=ut2003master1.epicgames.com\n", path.read_text()
        )
        self.assertEqual((self.game / "System/Default.ini").read_text(), TEMPLATE)
        self.assertEqual(
            (self.home / ".ut2003/System/UT2003.ini").read_text(), TEMPLATE
        )

    def test_openspy_rejects_missing_section_before_any_edits(self):
        (self.home / ".ut2003/System/UT2003.ini").write_text("[Other]\nValue=keep\n")
        response = subprocess.run(
            [sys.executable, str(OPENSPY), str(self.game)],
            env=dict(os.environ, HOME=str(self.home)),
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(response.returncode, 1)
        self.assertIn("expected exactly one [IpDrv.MasterServerLink]", response.stderr)
        self.assertEqual((self.game / "System/UT2003.ini").read_text(), TEMPLATE)
        self.assertFalse(
            (self.game / "Backup/OpenSpy-System-UT2003.ini.original").exists()
        )

    def test_proton_uses_private_game_copy_and_updates_lutris(self):
        patch_dir = self.game / "LinuxPatch"
        patch_dir.mkdir()
        for name in ("apply.sh", "configure.py", "launch-ut2003.sh", "proton.py"):
            shutil.copy2(Path(__file__).with_name(name), patch_dir / name)
        binary = self.game / "System/ut2003-bin"
        binary.write_text("placeholder")
        binary.chmod(0o700)
        (self.game / "System/UT2003.exe").write_text("windows executable placeholder")
        (self.game / "System/libSDL-1.2.so.0").write_text("placeholder")
        (self.game / "System/User.ini").write_text("Escape=ShowMenu\n")
        (self.game / "Maps").mkdir()
        (self.game / "Maps/demo.ut2").write_text("game asset placeholder")
        for name in ("UT2003.ini", "Default.ini"):
            path = self.game / "System" / name
            path.write_text(
                path.read_text() + "[WinDrv.WindowsClient]\nWindowedViewportX=640\n"
            )
        native_ini = (self.game / "System/UT2003.ini").read_text()
        lutris = self.lutris / "unreal-tournament-2003-own.yml"
        lutris.write_text(f"game:\n  exe: {binary}\n  args: -opengl -nogamma\n")
        steam = self.home / "Steam"
        (steam / "steamapps/common").mkdir(parents=True)
        runner = self.home / "proton"
        runner.write_text(
            '#!/bin/sh\n[ -d "$STEAM_COMPAT_DATA_PATH" ] || exit 42\n'
            'printf "%s\\n" "$@" > "$UT2003_TEST_LOG"\n'
            'printf "prefix=%s\\ncwd=%s\\n" "$STEAM_COMPAT_DATA_PATH" "$PWD" >> "$UT2003_TEST_LOG"\n'
        )
        runner.chmod(0o700)
        log = self.home / "proton-args"
        env = dict(
            os.environ,
            HOME=str(self.home),
            XDG_CONFIG_HOME=str(self.home / ".config"),
            STEAM_COMPAT_CLIENT_INSTALL_PATH=str(steam),
            UT2003_PROTON=str(runner),
            UT2003_TEST_LOG=str(log),
        )
        command = [
            "bash",
            str(patch_dir / "apply.sh"),
            "--proton",
            "--width",
            "1600",
            "--height",
            "900",
        ]
        check = subprocess.run(
            command + ["--check"], env=env, capture_output=True, text=True, check=False
        )
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertFalse((self.game / "Backup/ProtonGame").exists())
        configured = subprocess.run(
            command, env=env, capture_output=True, text=True, check=False, timeout=10
        )
        self.assertEqual(configured.returncode, 0, configured.stderr)
        self.assertEqual((self.game / "System/UT2003.ini").read_text(), native_ini)
        self.assertEqual(
            (self.home / ".ut2003/System/UT2003.ini").read_text(), TEMPLATE
        )
        self.assertFalse((self.game / "System/openal.so").exists())
        private = self.game / "Backup/ProtonGame"
        self.assertEqual(
            (private / "Maps/demo.ut2").read_text(), "game asset placeholder"
        )
        self.assertFalse((private / "Backup").exists())
        self.assertFalse((private / "LinuxPatch").exists())
        win_ini = (private / "System/UT2003.ini").read_text()
        self.assertIn("ViewportManager=WinDrv.WindowsClient", win_ini)
        self.assertIn("RenderDevice=D3DDrv.D3DRenderDevice", win_ini)
        self.assertIn("WindowedViewportX=1600", win_ini)
        self.assertIn("WindowedViewportY=900", win_ini)
        self.assertIn("StartupFullscreen=False", win_ini)
        fullscreen = subprocess.run(
            command + ["--proton-fullscreen"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        self.assertEqual(fullscreen.returncode, 0, fullscreen.stderr)
        for name in ("UT2003.ini", "Default.ini"):
            config = (private / "System" / name).read_text()
            self.assertIn("StartupFullscreen=True", config)
            self.assertIn("UseFullscreen=True", config)
            self.assertIn("FullscreenViewportX=1600", config)
            self.assertIn("FullscreenViewportY=900", config)
        self.assertEqual((self.game / "System/UT2003.ini").read_text(), native_ini)
        windowed = subprocess.run(
            command + ["--proton-windowed"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        self.assertEqual(windowed.returncode, 0, windowed.stderr)
        self.assertIn(
            "StartupFullscreen=False", (private / "System/UT2003.ini").read_text()
        )
        self.assertIn(
            "UseFullscreen=False", (private / "System/Default.ini").read_text()
        )
        self.assertIn("args: -nogamma", lutris.read_text())
        self.assertIn(str(self.game / "launch-ut2003.sh"), lutris.read_text())
        self.assertEqual(
            (self.game / "System/.ut2003-renderer").read_text(), "proton\n"
        )
        compat = self.game / "Backup/ProtonCompatData"
        self.assertFalse(compat.exists())
        env.pop("UT2003_PROTON")
        launch = subprocess.run(
            ["bash", str(self.game / "launch-ut2003.sh")],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        self.assertEqual(launch.returncode, 0, launch.stderr)
        self.assertTrue(compat.is_dir())
        self.assertEqual(compat.stat().st_mode & 0o777, 0o700)
        lines = log.read_text()
        self.assertIn("ini=UT2003.ini\nuserini=User.ini\n", lines)
        self.assertIn(f"prefix={self.game / 'Backup/ProtonCompatData'}", lines)
        self.assertIn(f"cwd={private / 'System'}", lines)

    def test_windows_patch_runs_in_private_prefix_and_is_not_repeated(self):
        patch_dir = self.game / "LinuxPatch"
        patch_dir.mkdir()
        for name in ("apply.sh", "configure.py", "launch-ut2003.sh", "proton.py"):
            shutil.copy2(Path(__file__).with_name(name), patch_dir / name)
        binary = self.game / "System/ut2003-bin"
        binary.write_text("placeholder")
        binary.chmod(0o700)
        (self.game / "System/libSDL-1.2.so.0").write_text("placeholder")
        (self.game / "System/UT2003.exe").write_text("original executable")
        (self.game / "System/User.ini").write_text("Escape=ShowMenu\n")
        for name in ("UT2003.ini", "Default.ini"):
            path = self.game / "System" / name
            path.write_text(path.read_text() + "[WinDrv.WindowsClient]\n")
        if not shutil.which("7z"):
            self.skipTest("7z required for the Windows patch")
        (self.game / "System/Core.dll").write_text("old core")
        installer = self.game / "ut2003-winpatch2225.exe"
        with zipfile.ZipFile(installer, "w") as archive:
            archive.writestr("UT2003-Patch/System/UT2003.exe", "patched executable")
            archive.writestr("UT2003-Patch/System/Core.dll", "patched core")
        runner = self.home / "fake-proton"
        runner.write_text("#!/bin/sh\nexit 99\n")
        runner.chmod(0o700)
        steam = self.home / "Steam/steamapps/common"
        steam.mkdir(parents=True)
        env = dict(
            os.environ,
            HOME=str(self.home),
            UT2003_PROTON=str(runner),
            STEAM_COMPAT_CLIENT_INSTALL_PATH=str(steam.parent.parent),
        )
        command = ["bash", str(patch_dir / "apply.sh"), "--proton", "--no-lutris"]
        for _ in range(2):
            result = subprocess.run(
                command, env=env, check=False, capture_output=True, text=True, timeout=5
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(
                "Extracting Windows 2225 patch into the PRIVATE game copy",
                result.stdout,
            )
        self.assertFalse((self.game / "Backup/ProtonCompatData").exists())
        self.assertEqual(
            (self.game / "System/UT2003.exe").read_text(), "original executable"
        )
        self.assertEqual(
            (self.game / "Backup/ProtonGame/System/UT2003.exe").read_text(),
            "patched executable",
        )
        self.assertFalse((self.game / "Backup/ProtonGame/UT2003-Patch").exists())
        self.assertEqual(
            (self.game / "Backup/ProtonGame/System/Core.dll").read_text(),
            "patched core",
        )
        self.assertEqual(
            (
                self.game / "Backup/ProtonWinpatch2225.original/System/Core.dll"
            ).read_text(),
            "old core",
        )
        self.assertEqual(
            (
                self.game / "Backup/ProtonWinpatch2225.original/System/UT2003.exe"
            ).read_text(),
            "original executable",
        )
        marker = self.game / "Backup/ProtonGame/.ut2003-winpatch2225.sha256"
        self.assertTrue(marker.is_file())
        private_core = self.game / "Backup/ProtonGame/System/Core.dll"
        private_core.unlink()
        private_core.symlink_to(self.game / "System/Core.dll")
        marker.unlink()
        refused = subprocess.run(
            command, env=env, check=False, capture_output=True, text=True, timeout=5
        )
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("Symlink in private patch destination", refused.stderr)
        self.assertEqual((self.game / "System/Core.dll").read_text(), "old core")
        self.assertEqual(
            (self.game / "Backup/ProtonGame/System/UT2003.exe").read_text(),
            "patched executable",
        )
        self.assertFalse(marker.exists())

    def test_cdkey_applicator_is_private_and_opt_in(self):
        patch_dir = self.game / "LinuxPatch"
        patch_dir.mkdir()
        for name in ("apply.sh", "menu.sh", "cdkey.py", "proton.py"):
            shutil.copy2(Path(__file__).with_name(name), patch_dir / name)
        binary = self.game / "System/ut2003-bin"
        binary.write_text("placeholder")
        binary.chmod(0o700)
        (self.game / "System/libSDL-1.2.so.0").write_text("placeholder")
        private = self.game / "Backup/ProtonGame/System"
        private.mkdir(parents=True)
        (private / "UT2003.exe").write_text("windows placeholder")
        native_key = self.game / "System/cdkey"
        native_key.write_text("ABCD-EFGH-IJKL-MNOP\n")
        runner = self.home / "proton"
        runner.write_text(
            "#!/usr/bin/env python3\nimport os, sys\nfrom pathlib import Path\n"
            'assert sys.argv[1:4] == ["run", "regedit", "/S"]\n'
            'path = Path(sys.argv[4][2:].replace("\\\\", "/"))\n'
            'text = path.read_text(encoding="utf-16")\n'
            'assert text.count("\\"CDKey\\"=\\"ABCD-EFGH-IJKL-MNOP\\"") == 2\n'
            'assert "Wow6432Node" in text\n'
            'Path(os.environ["UT2003_TEST_REG_OK"]).write_text("registered")\n'
        )
        runner.chmod(0o700)
        steam = self.home / "Steam"
        (steam / "steamapps/common").mkdir(parents=True)
        ok = self.home / "registry-status"
        env = dict(
            os.environ,
            HOME=str(self.home),
            UT2003_PROTON=str(runner),
            STEAM_COMPAT_CLIENT_INSTALL_PATH=str(steam),
            UT2003_TEST_REG_OK=str(ok),
        )
        command = ["bash", str(patch_dir / "apply.sh")]
        response = subprocess.run(
            command + ["--cdkey-from-native"],
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(response.returncode, 0, response.stderr)
        self.assertNotIn("ABCD-EFGH", response.stdout + response.stderr)
        self.assertEqual(ok.read_text(), "registered")
        self.assertEqual(native_key.read_text(), "ABCD-EFGH-IJKL-MNOP\n")
        self.assertEqual((private / "cdkey").read_text(), native_key.read_text())
        self.assertEqual((private / "cdkey").stat().st_mode & 0o777, 0o600)
        self.assertEqual(list((self.game / "Backup").glob(".ut2003-cdkey-*.reg")), [])
        invalid = subprocess.run(
            command + ["--cdkey-stdin"],
            input="bad key\n",
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(invalid.returncode, 1)
        self.assertNotIn("bad key", invalid.stdout + invalid.stderr)
        self.assertEqual((private / "cdkey").read_text(), native_key.read_text())
        menu = subprocess.run(
            command + ["--interactive"],
            input="9\n1\n0\n",
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(menu.returncode, 0, menu.stderr)
        self.assertIn("CD key applied", menu.stdout)
        self.assertNotIn("ABCD-EFGH", menu.stdout + menu.stderr)
        runner.write_text("#!/bin/sh\nexit 2\n")
        failed = subprocess.run(
            command + ["--cdkey-stdin"],
            input="WXYZ-9876-ABCD-1234\n",
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertNotEqual(failed.returncode, 0)
        self.assertNotIn("WXYZ-9876", failed.stdout + failed.stderr)
        self.assertEqual((private / "cdkey").read_text(), native_key.read_text())
        self.assertEqual(list((self.game / "Backup").glob(".ut2003-cdkey-*.reg")), [])

    def test_proton_menu_selection_is_explicit_and_cancellable(self):
        patch_dir = self.game / "LinuxPatch"
        patch_dir.mkdir()
        for name in ("apply.sh", "menu.sh"):
            shutil.copy2(Path(__file__).with_name(name), patch_dir / name)
        binary = self.game / "System/ut2003-bin"
        binary.write_text("placeholder")
        binary.chmod(0o700)
        (self.game / "System/libSDL-1.2.so.0").write_text("placeholder")
        (self.game / "ut2003-winpatch2225.exe").write_text("installer placeholder")
        response = subprocess.run(
            ["bash", str(patch_dir / "apply.sh"), "--interactive"],
            input="1\n3\n1\nn\ny\nn\nn\n0\n",
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(response.returncode, 0, response.stderr)
        self.assertIn(
            "Selected: --proton --width 1280 --height 720 --no-lutris --proton-fullscreen --skip-winpatch",
            response.stdout,
        )
        self.assertIn("can take several GB", response.stdout)
        self.assertIn(
            f"Apply it directly over the PRIVATE game copy: {self.game / 'Backup/ProtonGame'}",
            response.stdout,
        )
        self.assertFalse((self.game / "Backup/ProtonGame").exists())
        self.assertFalse((self.game / "System/.ut2003-renderer").exists())

    def test_proton_stop_only_targets_own_prefix(self):
        proton = Path(__file__).with_name("proton.py")
        compat = str(self.game / "Backup/ProtonCompatData")
        own = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            env=dict(os.environ, STEAM_COMPAT_DATA_PATH=compat),
        )
        other = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            env=dict(os.environ, STEAM_COMPAT_DATA_PATH=compat + "-other"),
        )
        try:
            stopped = subprocess.run(
                [sys.executable, str(proton), str(self.game), "--stop"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            self.assertEqual(stopped.returncode, 0, stopped.stderr)
            self.assertIsNotNone(own.poll())
            self.assertIsNone(other.poll())
        finally:
            for child in (own, other):
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=5)

    def test_defaults_are_idempotent_and_leave_input_alone(self):
        self.run_config("--no-lutris", "--width", "2560", "--height", "1080")
        ini = (self.game / "System/UT2003.ini").read_text()
        self.assertIn("WindowedViewportX=2560\n", ini)
        self.assertIn("MenuViewportX=1440\n", ini)
        self.assertIn("StartupFullscreen=False\n", ini)
        self.assertEqual(self.controls.read_text(), "Escape=ShowMenu\nOther=Keep\n")
        self.run_config("--no-lutris", "--width", "2560", "--height", "1080")
        self.assertEqual((self.game / "System/UT2003.ini").read_text(), ini)

    def test_experimental_input_is_reversible(self):
        self.run_config(
            "--no-lutris", "--input-fix", "--width", "1280", "--height", "720"
        )
        self.assertIn(
            "Escape=SetRes 1280x720w|OnRelease ShowMenu", self.controls.read_text()
        )
        self.run_config("--restore-input")
        self.assertEqual(self.controls.read_text(), "Escape=ShowMenu\nOther=Keep\n")

    def test_wizard_requires_confirmation_and_never_writes_on_cancel(self):
        patch_dir = self.game / "LinuxPatch"
        patch_dir.mkdir()
        shutil.copy2(Path(__file__).with_name("apply.sh"), patch_dir / "apply.sh")
        shutil.copy2(Path(__file__).with_name("menu.sh"), patch_dir / "menu.sh")
        (self.game / "System/ut2003-bin").write_text("placeholder")
        (self.game / "System/ut2003-bin").chmod(0o700)
        (self.game / "System/libSDL-1.2.so.0").write_text("placeholder")
        # Confirm every prompt except the final apply confirmation. No library
        # checks or configuration edits should occur before that confirmation.
        response = subprocess.run(
            ["bash", str(patch_dir / "apply.sh"), "--interactive"],
            input="1\n1\n3\n1280\n720\nn\nn\nn\nn\nn\n0\n",
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(response.returncode, 0, response.stderr)
        self.assertIn("No changes made. Returning to the main menu.", response.stdout)
        self.assertGreaterEqual(response.stdout.count("Unreal Tournament 2003"), 2)
        self.assertEqual((self.game / "System/UT2003.ini").read_text(), TEMPLATE)
        self.assertFalse((self.game / "System/.ut2003-video").exists())
        response = subprocess.run(
            ["bash", str(patch_dir / "apply.sh")],
            input="",
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(response.returncode, 2)
        self.assertIn("No terminal input available", response.stderr)

    def test_undecorated_menu_option_is_opt_in(self):
        patch_dir = self.game / "LinuxPatch"
        patch_dir.mkdir()
        for name in ("apply.sh", "menu.sh"):
            shutil.copy2(Path(__file__).with_name(name), patch_dir / name)
        (self.game / "System/ut2003-bin").write_text("placeholder")
        (self.game / "System/ut2003-bin").chmod(0o700)
        (self.game / "System/libSDL-1.2.so.0").write_text("placeholder")
        response = subprocess.run(
            ["bash", str(patch_dir / "apply.sh"), "--interactive"],
            input="1\n1\n1\nn\ny\nn\nn\nn\n0\n",
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(response.returncode, 0, response.stderr)
        self.assertIn(
            "Selected: --width 1280 --height 720 --no-lutris --undecorated",
            response.stdout,
        )
        self.assertFalse((self.game / "System/.ut2003-undecorated").exists())

    def test_one_minute_option_returns_to_main_menu(self):
        patch_dir = self.game / "LinuxPatch"
        patch_dir.mkdir()
        shutil.copy2(Path(__file__).with_name("apply.sh"), patch_dir / "apply.sh")
        shutil.copy2(Path(__file__).with_name("menu.sh"), patch_dir / "menu.sh")
        (self.game / "System/ut2003-bin").write_text("placeholder")
        (self.game / "System/ut2003-bin").chmod(0o700)
        (self.game / "System/libSDL-1.2.so.0").write_text("placeholder")
        trial = patch_dir / "test-launch.sh"
        trial.write_text(
            '#!/bin/sh\nprintf "%s\\n" "$UT2003_TEST_SECONDS" > "'
            + str(self.game / "seconds")
            + '"\nexit 124\n'
        )
        response = subprocess.run(
            ["bash", str(patch_dir / "apply.sh"), "--interactive"],
            input="6\ny\n0\n",
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(response.returncode, 0, response.stderr)
        self.assertIn("ONE-MINUTE TEST RUN", response.stdout)
        self.assertIn("wait one minute", response.stdout)
        self.assertIn(
            "One-minute time limit reached; returning to the main menu.",
            response.stdout,
        )
        self.assertGreaterEqual(response.stdout.count("Unreal Tournament 2003"), 2)
        self.assertEqual((self.game / "seconds").read_text().strip(), "60")

    def test_failed_restore_returns_to_main_menu(self):
        patch_dir = self.game / "LinuxPatch"
        patch_dir.mkdir()
        shutil.copy2(Path(__file__).with_name("apply.sh"), patch_dir / "apply.sh")
        shutil.copy2(Path(__file__).with_name("menu.sh"), patch_dir / "menu.sh")
        (self.game / "System/ut2003-bin").write_text("placeholder")
        (self.game / "System/ut2003-bin").chmod(0o700)
        (self.game / "System/libSDL-1.2.so.0").write_text("placeholder")
        response = subprocess.run(
            ["bash", str(patch_dir / "apply.sh"), "--interactive"],
            input="4\ny\n0\n",
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(response.returncode, 0, response.stderr)
        self.assertIn("No original SDL backup", response.stderr)
        self.assertIn("Returning to the main menu", response.stderr)
        self.assertGreaterEqual(response.stdout.count("Unreal Tournament 2003"), 2)

    def test_openspy_menu_applies_and_restores(self):
        patch_dir = self.game / "LinuxPatch"
        patch_dir.mkdir()
        for name in ("apply.sh", "menu.sh", "openspy.py"):
            shutil.copy2(Path(__file__).with_name(name), patch_dir / name)
        (self.game / "System/ut2003-bin").write_text("placeholder")
        (self.game / "System/ut2003-bin").chmod(0o700)
        (self.game / "System/libSDL-1.2.so.0").write_text("placeholder")
        response = subprocess.run(
            ["bash", str(patch_dir / "apply.sh"), "--interactive"],
            input="7\ny\n8\ny\n0\n",
            env=dict(os.environ, HOME=str(self.home)),
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(response.returncode, 0, response.stderr)
        self.assertIn("Configured OpenSpy", response.stdout)
        self.assertIn("Restored master-server settings", response.stdout)
        self.assertGreaterEqual(response.stdout.count("Unreal Tournament 2003"), 3)
        self.assertEqual((self.game / "System/UT2003.ini").read_text(), TEMPLATE)

    def test_undecorated_setting_can_be_applied_and_reversed(self):
        patch_dir = self.game / "LinuxPatch"
        patch_dir.mkdir()
        for name in ("apply.sh", "configure.py", "launch-ut2003.sh", "window-hints.py"):
            shutil.copy2(Path(__file__).with_name(name), patch_dir / name)
        binary = self.game / "System/ut2003-bin"
        binary.write_text("placeholder")
        binary.chmod(0o700)
        (self.game / "System/libSDL-1.2.so.0").write_text("placeholder")
        (self.game / "System/libstdc++.so.5").write_text("placeholder")
        lib = self.game / "lib32.so"
        lib.write_text("placeholder")
        tools = self.game / "tools"
        tools.mkdir()
        tool = tools / "file"
        tool.write_text("#!/bin/sh\necho 'ELF 32-bit'\n")
        tool.chmod(0o700)
        for name in ("xdotool", "xprop", "xrandr"):
            tool = tools / name
            if name == "xprop":
                tool.write_text(
                    "#!/bin/sh\necho '_NET_WORKAREA(CARDINAL) = 0, 36, 2560, 998'\n"
                )
            elif name == "xrandr":
                tool.write_text(
                    "#!/bin/sh\necho 'DP-2 connected primary 2560x1080+0+0'\n"
                )
            else:
                tool.write_text("#!/bin/sh\nexit 0\n")
            tool.chmod(0o700)
        env = dict(
            os.environ,
            HOME=str(self.home),
            PATH=str(tools) + os.pathsep + os.environ["PATH"],
            UT2003_ZINK_DRIVER=str(lib),
            UT2003_OPENAL_SOFT=str(lib),
        )
        marker = self.game / "System/.ut2003-undecorated"
        for option, expected in (("--undecorated", "1\n"), ("--decorated", "0\n")):
            options = (
                ["--fit-workarea", option] if option == "--undecorated" else [option]
            )
            response = subprocess.run(
                ["bash", str(patch_dir / "apply.sh"), "--no-lutris", *options],
                env=env,
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            self.assertEqual(response.returncode, 0, response.stderr)
            self.assertEqual(marker.read_text(), expected)
            if option == "--undecorated":
                self.assertEqual(
                    (self.game / "System/.ut2003-video").read_text(), "1712 963\n"
                )

    def test_undecorated_launcher_requests_frame_removal_only(self):
        launcher = self.game / "launch-ut2003.sh"
        shutil.copy2(Path(__file__).with_name("launch-ut2003.sh"), launcher)
        (self.game / "System/cdkey").write_text("test-key\n")
        (self.game / "System/.ut2003-renderer").write_text("zink\n")
        (self.game / "System/.ut2003-video").write_text("1280 720\n")
        marker = self.game / "System/.ut2003-undecorated"
        marker.write_text("1\n")
        binary = self.game / "System/ut2003-bin"
        binary.write_text("#!/bin/sh\nsleep 0.3\n")
        binary.chmod(0o700)
        tools = self.game / "tools"
        tools.mkdir()
        xdotool = tools / "xdotool"
        xdotool.write_text("#!/bin/sh\necho 12345\n")
        xdotool.chmod(0o700)
        log = self.game / "window-hints-args"
        helper = self.game / "ut2003-window-hints.py"
        helper.write_text(
            'import sys\nfrom pathlib import Path\nPath("'
            + str(log)
            + '").write_text(sys.argv[1])\n'
        )
        env = dict(
            os.environ,
            PATH=str(tools) + os.pathsep + os.environ["PATH"],
            UT2003_BORDERLESS="0",
        )
        env.pop("UT2003_UNDECORATED", None)
        response = subprocess.run(
            ["bash", str(launcher)],
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(response.returncode, 0, response.stderr)
        self.assertEqual(log.read_text(), "12345")
        marker.write_text("0\n")
        log.unlink()
        response = subprocess.run(
            ["bash", str(launcher)],
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(response.returncode, 0, response.stderr)
        self.assertFalse(log.exists())

    def test_bounded_undecorated_launch_kills_term_ignoring_child(self):
        launcher = self.game / "launch-ut2003.sh"
        shutil.copy2(Path(__file__).with_name("launch-ut2003.sh"), launcher)
        patch_dir = self.game / "LinuxPatch"
        patch_dir.mkdir()
        shutil.copy2(
            Path(__file__).with_name("test-launch.sh"), patch_dir / "test-launch.sh"
        )
        (self.game / "System/cdkey").write_text("test-key\n")
        (self.game / "System/.ut2003-renderer").write_text("zink\n")
        (self.game / "System/.ut2003-undecorated").write_text("1\n")
        pidfile = self.game / "child.pid"
        binary = self.game / "System/ut2003-bin"
        binary.write_text(
            '#!/bin/sh\ntrap "" TERM\necho "$$" > "'
            + str(pidfile)
            + '"\nexec sleep 30\n'
        )
        binary.chmod(0o700)
        tools = self.game / "tools"
        tools.mkdir()
        xdotool = tools / "xdotool"
        xdotool.write_text("#!/bin/sh\necho 12345\n")
        xdotool.chmod(0o700)
        (self.game / "ut2003-window-hints.py").write_text("# test helper\n")
        env = dict(
            os.environ,
            PATH=str(tools) + os.pathsep + os.environ["PATH"],
            UT2003_TEST_SECONDS="5",
            UT2003_BORDERLESS="0",
        )
        env.pop("UT2003_UNDECORATED", None)
        try:
            response = subprocess.run(
                ["bash", str(patch_dir / "test-launch.sh")],
                env=env,
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertIn(response.returncode, (124, 137), response.stderr)
            self.assertTrue(pidfile.exists())
            proc = Path("/proc") / pidfile.read_text().strip() / "status"
            # A briefly unreaped zombie is no longer running or capturing input.
            self.assertTrue(not proc.exists() or "State:\tZ" in proc.read_text())
        finally:
            if pidfile.exists():
                try:
                    os.kill(int(pidfile.read_text()), 9)
                except ProcessLookupError:
                    pass

    def test_recovery_only_stops_this_installation(self):
        patch_dir = self.game / "LinuxPatch"
        patch_dir.mkdir()
        shutil.copy2(
            Path(__file__).with_name("recover-ut2003.sh"),
            patch_dir / "recover-ut2003.sh",
        )
        # A real executable at the target path is needed for /proc/PID/exe.
        shutil.copy2("/usr/bin/sleep", self.game / "System/ut2003-bin")
        child = subprocess.Popen([str(self.game / "System/ut2003-bin"), "30"])
        try:
            response = subprocess.run(
                ["bash", str(patch_dir / "recover-ut2003.sh")],
                check=True,
                capture_output=True,
                text=True,
                timeout=6,
            )
            self.assertIn(f"process {child.pid}", response.stdout)
            self.assertIsNotNone(child.wait(timeout=3))
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()

    def test_trial_launch_terminates_hung_game(self):
        patch_dir = self.game / "LinuxPatch"
        patch_dir.mkdir()
        shutil.copy2(
            Path(__file__).with_name("test-launch.sh"), patch_dir / "test-launch.sh"
        )
        launcher = self.game / "launch-ut2003.sh"
        launcher.write_text("#!/bin/sh\nexec sleep 30\n")
        launcher.chmod(0o700)
        response = subprocess.run(
            ["bash", str(patch_dir / "test-launch.sh")],
            env=dict(os.environ, UT2003_TEST_SECONDS="5"),
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(response.returncode, 124, response.stderr)
        self.assertIn("time limit reached", response.stderr)

    def test_lutris_changes_only_matching_absolute_executable(self):
        match = self.lutris / "unreal-tournament-2003-own.yml"
        other = self.lutris / "unreal-tournament-2003-other.yml"
        relative = self.lutris / "unreal-tournament-2003-relative.yml"
        match.write_text(f"game:\n  exe: {self.game / 'System/ut2003-bin'}\n")
        other.write_text("game:\n  exe: /another/UT2003/System/ut2003-bin\n")
        relative.write_text("game:\n  exe: launch-ut2003.sh\n")
        self.run_config()
        self.assertIn(str(self.game / "launch-ut2003.sh"), match.read_text())
        self.assertTrue(match.with_name(match.name + ".pre-linuxpatch").exists())
        self.assertEqual(
            other.read_text(), "game:\n  exe: /another/UT2003/System/ut2003-bin\n"
        )
        self.assertEqual(relative.read_text(), "game:\n  exe: launch-ut2003.sh\n")


if __name__ == "__main__":
    unittest.main()
