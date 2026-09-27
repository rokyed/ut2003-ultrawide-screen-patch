"""Offline tests; never touch an installed game."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("configure.py")
TEMPLATE = """[Engine.Engine]
RenderDevice=old
ViewportManager=old
[SDLDrv.SDLClient]
WindowedViewportX=640
[OpenGLDrv.OpenGLRenderDevice]
VARSize=256
[ALAudio.ALAudioSubsystem]
UseEAX=True
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
        (self.game / "System/ut2003-bin").write_text("placeholder")
        (self.game / "System/ut2003-bin").chmod(0o700)
        (self.game / "System/libSDL-1.2.so.0").write_text("placeholder")
        # Confirm every prompt except the final apply confirmation. No library
        # checks or configuration edits should occur before that confirmation.
        response = subprocess.run(
            ["bash", str(patch_dir / "apply.sh"), "--interactive"],
            input="1\n1\n3\n1280\n720\nn\nn\nn\nn\n",
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(response.returncode, 0, response.stderr)
        self.assertIn("Cancelled; no changes made.", response.stdout)
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
