from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / ".agents" / "skills" / "skillguard" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from skillguard_v2.field_lifecycle import (  # noqa: E402
    COMMAND_DISPOSITIONS,
    V1_RUNTIME_AUTHORITY_COMMANDS,
    build_v1_field_lifecycle_plan,
)


class V1LifecycleTests(unittest.TestCase):
    def test_every_discovered_v1_runtime_field_has_a_closing_disposition(self) -> None:
        plan = build_v1_field_lifecycle_plan(ROOT / ".agents" / "skills" / "skillguard")
        self.assertEqual("passed", plan["status"], plan["blockers"])
        self.assertGreater(plan["field_row_count"], 100)
        self.assertFalse([row for row in plan["field_rows"] if row["disposition"] == "unknown"])
        self.assertTrue(all(row["replacement"] for row in plan["field_rows"]))

    def test_every_v1_runtime_authority_command_has_an_explicit_blocking_disposition(self) -> None:
        self.assertEqual(
            {
                "compile-contract",
                "select-route",
                "start-run",
                "advance-run",
                "check-run",
                "close-run",
            },
            set(V1_RUNTIME_AUTHORITY_COMMANDS),
        )
        for command in V1_RUNTIME_AUTHORITY_COMMANDS:
            self.assertIn("blocked_when_v2_authority_present", COMMAND_DISPOSITIONS[command])

    def test_v1_runtime_authority_is_blocked_on_the_v2_self_target(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_ROOT / "skillguard.py"),
                "compile-contract",
                "--target",
                ".agents/skills/skillguard",
                "--dry-run",
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(1, completed.returncode, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual("block", payload["decision"])
        self.assertIn("v2_authority_present", payload["blockers"][0])


if __name__ == "__main__":
    unittest.main()
