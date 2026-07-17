from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".agents" / "skills" / "skillguard" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from skillguard_v2.launch_plan import LaunchPlanError, resolve_launch_plan  # noqa: E402


class LaunchPlanTest(unittest.TestCase):
    def plan(self, command: str, args: list[str], cwd: Path, *, platform_name: str | None = None, environment: dict[str, str] | None = None):
        return resolve_launch_plan(
            command,
            args,
            cwd=cwd,
            environment=environment or dict(os.environ),
            environment_fingerprint="A" * 64,
            cwd_token="repository_root",
            cwd_relative=".",
            platform_name=platform_name,
        )

    def test_direct_executable_has_no_shell(self) -> None:
        plan = self.plan(sys.executable, ["--version"], ROOT)
        self.assertEqual(plan.record["adapter"], "direct_executable")
        self.assertEqual(plan.record["interpreter"], "")
        self.assertEqual(plan.argv[0], str(Path(sys.executable).resolve()))
        self.assertTrue(plan.record["resolved_program_identity"].startswith("sha256:"))

    def test_unix_executable_plan_remains_direct_and_shell_free(self) -> None:
        plan = self.plan(
            sys.executable,
            ["--version"],
            ROOT,
            platform_name="linux",
        )
        self.assertEqual(plan.record["platform"], "linux")
        self.assertEqual(plan.record["adapter"], "direct_executable")
        self.assertEqual(plan.record["interpreter"], "")
        self.assertEqual(plan.argv[0], str(Path(sys.executable).resolve()))

    def test_windows_command_shim_uses_cmd_and_preserves_space_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="launch plan ", dir=ROOT) as tmp:
            workspace = Path(tmp)
            shim = workspace / "tool with spaces.cmd"
            shim.write_text("@echo off\r\nexit /b 0\r\n", encoding="utf-8")
            environment = dict(os.environ)
            environment["ComSpec"] = str(Path(environment.get("SystemRoot", "C:/Windows")) / "System32" / "cmd.exe")
            plan = self.plan(str(shim), ["alpha", "two words"], workspace, platform_name="win32", environment=environment)
            self.assertEqual(plan.record["adapter"], "windows_command_shim")
            self.assertEqual(Path(plan.record["interpreter"]).name.lower(), "cmd.exe")
            self.assertIn(str(shim.resolve()), plan.argv)
            self.assertEqual(plan.argv[-2:], ("alpha", "two words"))

    def test_windows_powershell_script_uses_resolved_interpreter(self) -> None:
        with tempfile.TemporaryDirectory(prefix="launch-ps1-", dir=ROOT) as tmp:
            workspace = Path(tmp)
            script = workspace / "check.ps1"
            interpreter = workspace / "pwsh.exe"
            script.write_text("exit 0\n", encoding="utf-8")
            interpreter.write_bytes(b"fixture interpreter")
            environment = {**os.environ, "PATH": str(workspace)}
            plan = self.plan(str(script), ["-Name", "fixture"], workspace, platform_name="win32", environment=environment)
            self.assertEqual(plan.record["adapter"], "windows_powershell_script")
            self.assertEqual(Path(plan.record["interpreter"]), interpreter.resolve())
            self.assertIn("-File", plan.argv)
            self.assertTrue(plan.record["interpreter_identity"].startswith("sha256:"))

    def test_changed_resolution_changes_launch_identity(self) -> None:
        with tempfile.TemporaryDirectory(prefix="launch-resolution-", dir=ROOT) as tmp:
            workspace = Path(tmp)
            first = workspace / "first"
            second = workspace / "second"
            first.mkdir()
            second.mkdir()
            first_tool = first / "tool.cmd"
            second_tool = second / "tool.cmd"
            first_tool.write_text("@echo first\n", encoding="utf-8")
            second_tool.write_text("@echo second\n", encoding="utf-8")
            base = dict(os.environ)
            base["PATHEXT"] = ".CMD;.EXE"
            base["ComSpec"] = str(Path(base.get("SystemRoot", "C:/Windows")) / "System32" / "cmd.exe")
            first_plan = self.plan("tool", [], workspace, platform_name="win32", environment={**base, "PATH": str(first)})
            second_plan = self.plan("tool", [], workspace, platform_name="win32", environment={**base, "PATH": str(second)})
            self.assertNotEqual(first_plan.record["resolved_program_identity"], second_plan.record["resolved_program_identity"])
            self.assertNotEqual(first_plan.record["launch_plan_fingerprint"], second_plan.record["launch_plan_fingerprint"])

    def test_physical_cwd_changes_do_not_change_portable_launch_identity(self) -> None:
        with tempfile.TemporaryDirectory(prefix="launch-cwd-", dir=ROOT) as tmp:
            workspace = Path(tmp)
            first = workspace / "first"
            second = workspace / "second"
            first.mkdir()
            second.mkdir()
            first_plan = self.plan(sys.executable, ["--version"], first)
            second_plan = self.plan(sys.executable, ["--version"], second)
            self.assertNotEqual(
                first_plan.record["cwd"]["resolved_identity"],
                second_plan.record["cwd"]["resolved_identity"],
            )
            self.assertEqual(
                first_plan.record["launch_plan_fingerprint"],
                second_plan.record["launch_plan_fingerprint"],
            )

    def test_unresolved_program_fails_closed(self) -> None:
        with self.assertRaises(LaunchPlanError) as caught:
            self.plan("definitely-not-a-current-program", [], ROOT, environment={"PATH": ""})
        self.assertEqual(caught.exception.code, "launch_program_missing")


if __name__ == "__main__":
    unittest.main()
