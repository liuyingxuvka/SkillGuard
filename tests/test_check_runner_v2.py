from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from _skillguard_v2_runtime_fixture import SCRIPT_ROOT, runtime_contract  # noqa: F401
from skillguard_v2.check_runner import (
    CheckRunnerError,
    execute_check,
    hard_evidence_from_check,
    store_check_result,
)
from skillguard_v2.route_runtime import select_routes
from skillguard_v2.run_store import claim_run


class CheckRunnerV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.target = self.root / "target"
        self.repo = self.root / "repo"
        self.target.mkdir()
        self.repo.mkdir()
        contract = runtime_contract()
        decision = select_routes(contract, {"function_ids": ["analyze"]})
        claim = claim_run(
            contract,
            {"function_ids": ["analyze"], "write_targets": ["out"], "request": "check runner"},
            self.target,
            decision,
        )
        self.run = claim.run_root

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _execute(self, check):
        return execute_check(
            check,
            target_root=self.target,
            repository_root=self.repo,
            run_root=self.run,
        )

    def test_shell_free_command_captures_exit_and_output(self) -> None:
        result = self._execute(
            {
                "check_id": "check:pass",
                "kind": "command",
                "command": sys.executable,
                "args": ["-c", "print('evidence')"],
                "cwd_token": "target_root",
                "timeout_seconds": 5,
                "expected": {"exit_code": 0},
            }
        )
        self.assertEqual("passed", result["status"])
        self.assertTrue(result["executed"])
        self.assertEqual("evidence", result["stdout"].strip())
        self.assertTrue(result["proof_fingerprint"])
        stored = store_check_result(self.run, "step:intake", result)
        self.assertEqual("native_check", hard_evidence_from_check(stored)["proof_kind"])

    def test_unstored_passing_result_cannot_be_promoted_to_hard_evidence(self) -> None:
        result = self._execute(
            {
                "check_id": "check:unstored",
                "kind": "command",
                "command": sys.executable,
                "args": ["-c", "print('pass')"],
            }
        )
        with self.assertRaises(CheckRunnerError) as raised:
            hard_evidence_from_check(result)
        self.assertEqual("check_result_not_immutably_stored", raised.exception.code)

    def test_nonzero_timeout_missing_and_unsupported_never_pass(self) -> None:
        failed = self._execute(
            {
                "check_id": "check:fail",
                "kind": "command",
                "command": sys.executable,
                "args": ["-c", "raise SystemExit(7)"],
                "expected": {"exit_code": 0},
            }
        )
        self.assertEqual("failed", failed["status"])
        missing = self._execute(
            {
                "check_id": "check:missing",
                "kind": "command",
                "command": "executable-that-does-not-exist-skillguard-v2",
                "args": [],
            }
        )
        self.assertEqual("not_run", missing["status"])
        self.assertFalse(missing["executed"])
        with self.assertRaises(CheckRunnerError) as missing_evidence:
            hard_evidence_from_check(missing)
        self.assertEqual("check_cannot_be_hard_evidence", missing_evidence.exception.code)
        unsupported = self._execute({"check_id": "check:api", "kind": "external_api"})
        self.assertEqual("not_run", unsupported["status"])
        timed_out = self._execute(
            {
                "check_id": "check:timeout",
                "kind": "command",
                "command": sys.executable,
                "args": ["-c", "import time; time.sleep(0.2)"],
                "timeout_seconds": 0.02,
            }
        )
        self.assertEqual("failed", timed_out["status"])
        self.assertEqual("timeout", timed_out["reason"])

    def test_cwd_is_tokenized_and_cannot_escape_its_root(self) -> None:
        with self.assertRaises(CheckRunnerError) as raised:
            self._execute(
                {
                    "check_id": "check:escape",
                    "kind": "command",
                    "command": sys.executable,
                    "args": ["-c", "print('no')"],
                    "cwd_token": "target_root",
                    "cwd_relative": "../repo",
                }
            )
        self.assertEqual("cwd_outside_token_root", raised.exception.code)

    def test_exact_path_argument_tokens_expand_without_shell_interpolation(self) -> None:
        result = self._execute(
            {
                "check_id": "check:path-tokens",
                "kind": "command",
                "command": sys.executable,
                "args": [
                    "-c",
                    "import sys; print('|'.join(sys.argv[1:]))",
                    "{{target_root}}",
                    "{{repository_root}}",
                    "{{run_root}}",
                ],
                "cwd_token": "target_root",
                "timeout_seconds": 5,
                "expected": {"exit_code": 0},
            }
        )
        self.assertEqual("passed", result["status"])
        self.assertEqual(
            [str(self.target.resolve()), str(self.repo.resolve()), str(self.run.resolve())],
            result["stdout"].strip().split("|"),
        )
        self.assertEqual("{{target_root}}", result["declared_args"][2])


if __name__ == "__main__":
    unittest.main()
