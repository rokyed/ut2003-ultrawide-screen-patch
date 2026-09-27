"""Offline tests; never touch an installed game."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
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
