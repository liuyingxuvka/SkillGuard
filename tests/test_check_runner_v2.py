from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from _skillguard_v2_runtime_fixture import (  # noqa: F401
    SCRIPT_ROOT,
    runtime_check_manifest,
    runtime_checks,
    runtime_contract,
    runtime_contract_with_checks,
)
from skillguard_v2.check_runner import (
    CheckRunnerError,
    _installed_runtime_input_component,
    execute_check,
    get_or_execute_check,
    hard_evidence_from_check,
    load_check_result,
    store_check_result,
)
from skillguard_v2.contract_compiler import canonical_hash
from skillguard_v2.execution_records import filesystem_path
from skillguard_v2.route_runtime import select_routes
from skillguard_v2.run_store import claim_run


class CheckRunnerV2Tests(unittest.TestCase):
    def test_installation_selector_identity_changes_only_with_installed_source(self) -> None:
        codex_home = self.root / "codex-home"
        installed = codex_home / "skills" / "demo"
        installed.mkdir(parents=True)
        (installed / "SKILL.md").write_text("first\n", encoding="utf-8")
        declared = {
            "check_id": "check:installed",
            "input_selectors": [
                {"kind": "install_disposition", "install_disposition": "copy"}
            ],
        }
        plan = {
            "components": [
                {
                    "component_id": "component:demo",
                    "install_disposition": "copy",
                    "member_paths": [".agents/skills/demo/SKILL.md"],
                }
            ]
        }
        owner = {"input_component_ids": ["component:demo"]}
        with patch.dict("os.environ", {"CODEX_HOME": str(codex_home)}):
            first = _installed_runtime_input_component(
                declared, plan=plan, owner=owner
            )
            receipts = installed / ".sg-runtime" / "installation"
            receipts.mkdir(parents=True)
            (receipts / "runtime.json").write_text("{}\n", encoding="utf-8")
            evidence_only = _installed_runtime_input_component(
                declared, plan=plan, owner=owner
            )
            (installed / "SKILL.md").write_text("second\n", encoding="utf-8")
            changed = _installed_runtime_input_component(
                declared, plan=plan, owner=owner
            )
        self.assertEqual(first, evidence_only)
        self.assertNotEqual(first["component_hash"], changed["component_hash"])

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.run_counter = 0

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _execute(self, check, *, request_extra=None):
        self.run_counter += 1
        self.target = self.root / f"target-{self.run_counter}"
        self.target.mkdir()
        contract, manifest = runtime_contract_with_checks([dict(check)])
        decision = select_routes(contract, {"function_ids": ["analyze"]})
        request = {
            "function_ids": ["analyze"],
            "write_targets": ["out"],
            "request": f"check runner {self.run_counter}",
            **dict(request_extra or {}),
        }
        claim = claim_run(
            contract,
            request,
            self.target,
            decision,
            check_manifest=manifest,
        )
        self.assertTrue(claim.ok, claim.to_dict())
        self.run = claim.run_root
        return execute_check(
            manifest["checks"][0],
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
        with self.assertRaisesRegex(
            CheckRunnerError, "check_execution_disposition_invalid"
        ):
            hard_evidence_from_check(stored)

    def test_python_check_cannot_leave_bytecode_in_validated_repository(self) -> None:
        (self.repo / "validated_module.py").write_text(
            "VALUE = 'validated'\n", encoding="utf-8"
        )
        result = self._execute(
            {
                "check_id": "check:no-bytecode-side-effect",
                "kind": "command",
                "command": sys.executable,
                "args": [
                    "-c",
                    "import validated_module; print(validated_module.VALUE)",
                ],
                "cwd_token": "repository_root",
                "environment": {"PYTHONDONTWRITEBYTECODE": "0"},
                "timeout_seconds": 5,
                "expected": {"exit_code": 0},
            }
        )
        self.assertEqual("passed", result["status"])
        self.assertEqual("validated", result["stdout"].strip())
        self.assertFalse((self.repo / "__pycache__").exists())

    @unittest.skipUnless(os.name == "nt", "Windows extended-length path regression")
    def test_store_and_load_check_result_beyond_max_path(self) -> None:
        result = self._execute(
            {
                "check_id": "check:long-path",
                "kind": "command",
                "command": sys.executable,
                "args": ["-c", "print('long path evidence')"],
                "cwd_token": "target_root",
                "timeout_seconds": 5,
                "expected": {"exit_code": 0},
            }
        )
        long_root = self.root / "long-run-root"
        long_parent = long_root
        representative_name = "check-record-" + ("a" * 24) + ".json"
        while len(
            str(long_parent / self.run.name / "checks" / representative_name)
        ) <= 260:
            long_parent /= "segment-abcdefghij"
        long_parent.mkdir(parents=True)
        long_run = long_parent / self.run.name
        shutil.copytree(self.run, long_run)
        try:
            stored = store_check_result(long_run, "step:intake", result)
            record_path = (
                long_run / "checks" / f"{stored['check_record_id']}.json"
            )
            self.assertGreater(len(str(record_path)), 260)
            self.assertTrue(filesystem_path(record_path).is_file())
            self.assertEqual(
                stored,
                load_check_result(long_run, str(stored["check_record_id"])),
            )
        finally:
            shutil.rmtree(filesystem_path(long_root))

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

    def test_static_manifest_runtime_facts_are_rejected_as_unknown_behavior(self) -> None:
        contract, manifest = runtime_contract_with_checks(
            [
                {
                    "check_id": "check:static-facts",
                    "kind": "command",
                    "command": sys.executable,
                    "args": ["-c", "print('pass')"],
                    "coverage_universe_results": [{"eligible_count": 999}],
                    "depth_contribution_ranges": [{"range_id": "renamed"}],
                }
            ]
        )
        target = self.root / "target-static-facts"
        target.mkdir()
        decision = select_routes(contract, {"function_ids": ["analyze"]})
        claim = claim_run(
            contract,
            {
                "function_ids": ["analyze"],
                "write_targets": ["out"],
                "request": "unknown runtime facts",
            },
            target,
            decision,
            check_manifest=manifest,
        )
        self.assertFalse(claim.ok)
        self.assertIn(
            "compiled_check_behavior_field_unknown",
            {finding.code for finding in claim.findings},
        )



if __name__ == "__main__":
    unittest.main()
