from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / ".agents" / "skills" / "skillguard" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import checker_engine  # noqa: E402
import skillguard  # noqa: E402


FORMER_RUNTIME_COMMANDS = (
    "compile-contract",
    "select-route",
    "start-run",
    "advance-run",
    "check-run",
    "close-run",
    "check-work-contract",
    "check-skill-contract",
    "check-run-record",
    "check-check-manifest",
    "migrate-portfolio-registry",
)


class FormerRuntimeCommandRejectionTests(unittest.TestCase):
    def test_former_commands_have_no_handler_or_public_route(self) -> None:
        contract = json.loads(
            (ROOT / ".skillguard" / "contract-source.json").read_text(encoding="utf-8")
        )
        public_route_commands = {
            str(row.get("route_id") or "")
            for row in contract.get("routes", [])
            if isinstance(row, dict)
        }
        for command in FORMER_RUNTIME_COMMANDS:
            with self.subTest(command=command):
                self.assertNotIn(command, checker_engine.COMMANDS)
                self.assertNotIn(command, public_route_commands)
                self.assertFalse(
                    hasattr(checker_engine, command.replace("-", "_")),
                    f"former daily handler still exists: {command}",
                )

    def test_facade_rejects_former_commands_before_parser_or_write(self) -> None:
        with tempfile.TemporaryDirectory(prefix="skillguard-retired-command-") as raw:
            target = Path(raw)
            marker = target / "must-not-change.txt"
            marker.write_text("unchanged", encoding="utf-8")
            before = marker.read_bytes()

            for command in FORMER_RUNTIME_COMMANDS:
                with self.subTest(command=command):
                    output = io.StringIO()
                    with contextlib.redirect_stdout(output):
                        exit_code = skillguard.main(
                            [command, "--target", str(target), "--write"]
                        )
                    self.assertEqual(2, exit_code)
                    payload = json.loads(output.getvalue())
                    self.assertEqual("blocked", payload["status"])
                    self.assertEqual("block", payload["decision"])
                    self.assertEqual(0, payload["producer_count"])
                    self.assertEqual(f"unknown command: {command}", payload["error"]["message"])
                    self.assertEqual(before, marker.read_bytes())
                    self.assertEqual([marker.name], sorted(p.name for p in target.iterdir()))


if __name__ == "__main__":
    unittest.main()
