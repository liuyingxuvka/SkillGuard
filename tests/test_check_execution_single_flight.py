from __future__ import annotations

import copy
import ctypes
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

from _skillguard_v2_runtime_fixture import (  # noqa: F401
    SCRIPT_ROOT,
    runtime_contract_with_checks,
)
from skillguard_v2.check_runner import (
    CheckRunnerError,
    _run_bound_output_component,
    check_toolchain_identity,
    get_or_execute_check,
    load_owner_receipt_from_projection,
)
from skillguard_v2.contract_compiler import (
    OWNER_BEHAVIOR_FIELDS,
    canonical_hash,
    source_file_hash,
    wire_hash,
)
from skillguard_v2.execution_records import filesystem_path
from skillguard_v2.route_runtime import select_routes
from skillguard_v2.run_store import claim_run


class CheckExecutionSingleFlightTests(unittest.TestCase):
    def test_only_declared_run_root_inputs_receive_a_run_component(self) -> None:
        first_run = {
            "run_id": "run-one",
            "contract_hash": "A" * 64,
            "check_manifest_hash": "B" * 64,
            "check_declarations_hash": "C" * 64,
            "request_fingerprint": "D" * 64,
        }
        second_run = {**first_run, "run_id": "run-two"}

        self.assertIsNone(
            _run_bound_output_component(
                {"check_id": "check:portable"}, first_run
            )
        )
        run_reader_first = _run_bound_output_component(
            {"args": ["reader.py", "{{run_root}}"]}, first_run
        )
        run_reader_second = _run_bound_output_component(
            {"args": ["reader.py", "{{run_root}}"]}, second_run
        )
        self.assertIsNotNone(run_reader_first)
        self.assertIsNotNone(run_reader_second)
        self.assertNotEqual(
            run_reader_first["component_hash"],
            run_reader_second["component_hash"],
        )
        for retired_field in (
            "depth_evidence_output",
            "calibration_evidence_output",
        ):
            self.assertIsNone(
                _run_bound_output_component(
                    {
                        retired_field: {
                            "path_token": "run_root",
                            "relative_path": "out.json",
                        }
                    },
                    first_run,
                )
            )

    def test_toolchain_identity_returns_both_current_hashes(self) -> None:
        identity = check_toolchain_identity({"command": sys.executable})

        self.assertEqual(
            {"toolchain_fingerprint", "execution_environment_fingerprint"},
            set(identity),
        )
        for value in identity.values():
            self.assertRegex(value, r"^sha256:[0-9a-f]{64}$")

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repository_root = self.root / "repository"
        self.skill_root = self.repository_root / "skill"
        self.target_root = self.root / "target"
        self.repository_root.mkdir()
        self.skill_root.mkdir()
        self.target_root.mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _claim(
        self,
        check: dict[str, object],
        *,
        implementation_path: Path | None = None,
        target_root: Path | None = None,
        maintenance_unit_id: str = "unit:runtime-fixture",
    ) -> tuple[dict[str, object], Path]:
        declared = dict(check)
        declared.setdefault("maintenance_unit_id", maintenance_unit_id)
        declared.setdefault("member_skill_id", "runtime-fixture")
        declared.setdefault(
            "evidence_subject_id",
            f"subject:{str(declared['check_id']).removeprefix('check:')}",
        )
        declared.setdefault("semantic_check_id", str(declared["check_id"]))
        contract, manifest = runtime_contract_with_checks([declared])
        if maintenance_unit_id != contract["maintenance_unit_id"]:
            contract["maintenance_unit_id"] = maintenance_unit_id
            contract["contract_hash"] = canonical_hash(
                {
                    key: value
                    for key, value in contract.items()
                    if key != "contract_hash"
                }
            )
            manifest["maintenance_unit_id"] = maintenance_unit_id
            manifest["contract_hash"] = contract["contract_hash"]
            manifest.pop("manifest_hash", None)
            manifest["manifest_hash"] = canonical_hash(manifest)
        if implementation_path is not None:
            relative_path = implementation_path.relative_to(
                self.repository_root
            ).as_posix()
            content_hash = "sha256:" + source_file_hash(implementation_path).lower()
            component_id = "component:runtime_source:fixture"
            component = {
                "component_id": component_id,
                "role": "runtime_source",
                "install_disposition": "source_only",
                "member_paths": [relative_path],
                "component_hash": wire_hash(
                    [{"path": relative_path, "content_hash": content_hash}]
                ),
                "consumer_ids": ["owner:source-bound"],
                "classification_rule_ids": ["fixture:runtime_source"],
            }
            check_row = contract["checks"][0]
            check_row["input_selectors"] = [
                {"kind": "path", "path": relative_path}
            ]
            check_row["input_component_ids"] = [component_id]
            check_row["owner_input_projection_hash"] = wire_hash(
                [
                    {
                        "component_id": component_id,
                        "component_hash": component["component_hash"],
                    }
                ]
            )
            check_row["owner_declaration_hash"] = wire_hash(
                {
                    "behavior": {
                        key: check_row[key]
                        for key in OWNER_BEHAVIOR_FIELDS
                        if key in check_row
                    },
                    "input_selectors": check_row["input_selectors"],
                    "evidence_domain_id": check_row["evidence_domain_id"],
                    "impact_policy_id": "skillguard.content_impact_policy.current",
                }
            )
            plan = contract["content_impact_plan"]
            plan["inventory"] = [
                {
                    "path": relative_path,
                    "content_hash": content_hash,
                    "role": "runtime_source",
                    "install_disposition": "source_only",
                    "classification_rule_id": "fixture:runtime_source",
                }
            ]
            plan["inventory_hash"] = wire_hash(plan["inventory"])
            plan["components"] = [component]
            plan["owners"][0].update(
                {
                    "owner_declaration_hash": check_row[
                        "owner_declaration_hash"
                    ],
                    "input_selectors": check_row["input_selectors"],
                    "input_component_ids": [component_id],
                    "owner_input_projection_hash": check_row[
                        "owner_input_projection_hash"
                    ],
                }
            )
            plan["impact_graph_hash"] = wire_hash(
                {
                    "policy_id": plan["policy_id"],
                    "member_root_path": plan["member_root_path"],
                    "inventory_hash": plan["inventory_hash"],
                    "components": plan["components"],
                    "owners": plan["owners"],
                    "check_projections": plan["check_projections"],
                    "projection_consumers": plan["projection_consumers"],
                    "portfolio_target_edges": plan["portfolio_target_edges"],
                    "health": plan["health"],
                }
            )
            contract["check_declarations_hash"] = canonical_hash(
                {"checks": contract["checks"]}
            )
            contract["contract_hash"] = canonical_hash(
                {
                    key: value
                    for key, value in contract.items()
                    if key != "contract_hash"
                }
            )
            manifest["contract_hash"] = contract["contract_hash"]
            manifest["check_declarations_hash"] = contract[
                "check_declarations_hash"
            ]
            manifest["checks"] = copy.deepcopy(contract["checks"])
            manifest["content_impact_plan"] = copy.deepcopy(plan)
            manifest.pop("manifest_hash", None)
            manifest["manifest_hash"] = canonical_hash(manifest)
        request = {
            "function_ids": ["analyze"],
            "write_targets": ["out"],
            "request": "single-flight exact check",
        }
        decision = select_routes(contract, request)
        active_target = target_root or self.target_root
        claim = claim_run(
            contract,
            request,
            active_target,
            decision,
            check_manifest=manifest,
        )
        self.assertTrue(claim.ok, claim.to_dict())
        assert claim.run_root is not None
        return dict(manifest["checks"][0]), claim.run_root

    def _run(
        self,
        check: dict[str, object],
        run_root: Path,
        *,
        target_root: Path | None = None,
        dependency_execution_receipts: dict[str, dict[str, object]] | None = None,
        owner_evidence_root: Path | None = None,
    ):
        return get_or_execute_check(
            check,
            skill_root=self.skill_root,
            target_root=target_root or self.target_root,
            repository_root=self.repository_root,
            run_root=run_root,
            step_id="step:intake",
            dependency_execution_receipts=dependency_execution_receipts,
            owner_evidence_root=owner_evidence_root,
        )

    @unittest.skipUnless(os.name == "nt", "Windows extended-length path regression")
    def test_long_owner_receipt_is_read_back_from_projection(self) -> None:
        check, run_root = self._claim(
            {
                "check_id": "check:long-owner-receipt",
                "kind": "command",
                "command": sys.executable,
                "args": ["-c", "print('owner receipt')"],
                "cwd_token": "target_root",
                "timeout_seconds": 5,
                "expected": {"exit_code": 0},
            }
        )
        long_root = self.root / "long-owner-root"
        owner_root = long_root
        representative_blob = (
            owner_root
            / "check-executions"
            / "blobs"
            / (("a" * 64) + ".json")
        )
        while len(str(representative_blob)) <= 260:
            owner_root /= "segment-abcdefghij"
            representative_blob = (
                owner_root
                / "check-executions"
                / "blobs"
                / (("a" * 64) + ".json")
            )
        owner_root.mkdir(parents=True)
        try:
            execution = self._run(
                check,
                run_root,
                owner_evidence_root=owner_root,
            )
            self.assertEqual("passed", execution["record"]["status"])
            receipt = load_owner_receipt_from_projection(
                owner_root,
                execution["record"],
            )
            self.assertEqual(
                execution["record"]["owner_receipt_id"],
                receipt["receipt_id"],
            )
        finally:
            shutil.rmtree(filesystem_path(long_root))

    @staticmethod
    def _pid_is_running(pid: int) -> bool:
        if os.name != "nt":
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return False
            except PermissionError:
                return True
            return True
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        open_process = kernel32.OpenProcess
        open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        open_process.restype = wintypes.HANDLE
        get_exit_code = kernel32.GetExitCodeProcess
        get_exit_code.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        get_exit_code.restype = wintypes.BOOL
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL
        handle = open_process(0x1000, False, pid)
        if not handle:
            return False
        try:
            exit_code = wintypes.DWORD()
            return bool(get_exit_code(handle, ctypes.byref(exit_code))) and exit_code.value == 259
        finally:
            close_handle(handle)

    def test_terminal_success_is_reused_and_identities_remain_distinct(self) -> None:
        counter = "check-output/counter.txt"
        script = (
            "import pathlib,sys; p=pathlib.Path(sys.argv[1])/sys.argv[2]; "
            "p.parent.mkdir(parents=True,exist_ok=True); "
            "n=int(p.read_text())+1 if p.exists() else 1; "
            "p.write_text(str(n)); print(n)"
        )
        check, run_root = self._claim(
            {
                "check_id": "check:single-flight",
                "kind": "command",
                "command": sys.executable,
                "args": ["-c", script, "{{run_root}}", counter],
                "expected": {"exit_code": 0},
                "covers_obligation_ids": ["obligation:intake"],
            }
        )
        first = self._run(check, run_root)
        second = self._run(check, run_root)
        self.assertEqual("executed_terminal_success", first["disposition"])
        self.assertEqual("reused_terminal_success", second["disposition"])
        self.assertEqual("1", (run_root / counter).read_text(encoding="utf-8"))
        receipt = first["execution_receipt"]
        self.assertEqual(
            receipt["receipt_id"], second["execution_receipt"]["receipt_id"]
        )
        self.assertEqual("owner:single-flight", receipt["execution_owner_id"])
        self.assertRegex(receipt["execution_key"], r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(receipt["receipt_id"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(
            ["component:run_bound_output_context"],
            [row["component_id"] for row in receipt["input_components"]],
        )
        self.assertEqual(
            wire_hash(receipt["input_components"]),
            receipt["owner_input_projection_hash"],
        )
        self.assertEqual(
            {"stdout", "stderr", "result", "termination"},
            set(receipt["sidecars"]),
        )
        result_ref = receipt["sidecars"]["result"]
        result_sidecar = json.loads(
            (
                self.repository_root
                / "work"
                / "verification"
                / "owner-evidence"
                / result_ref["relative_path"]
            ).read_text(encoding="utf-8")
        )["result"]
        for kind in ("stdout", "stderr"):
            self.assertEqual(
                receipt["sidecars"][kind]["content_hash"],
                result_sidecar[f"{kind}_content_hash"],
            )
            self.assertNotIn(f"{kind}_hash", result_sidecar)

    def test_failed_attempt_never_hits_and_retry_can_succeed(self) -> None:
        marker = "check-output/first-attempt.txt"
        script = (
            "import pathlib,sys; p=pathlib.Path(sys.argv[1])/sys.argv[2]; "
            "p.parent.mkdir(parents=True,exist_ok=True); "
            "first=not p.exists(); p.write_text('attempted'); "
            "raise SystemExit(9 if first else 0)"
        )
        check, run_root = self._claim(
            {
                "check_id": "check:retry",
                "kind": "command",
                "command": sys.executable,
                "args": ["-c", script, "{{run_root}}", marker],
                "expected": {"exit_code": 0},
                "covers_obligation_ids": ["obligation:intake"],
            }
        )
        failed = self._run(check, run_root)
        passed = self._run(check, run_root)
        reused = self._run(check, run_root)
        self.assertEqual("executed_failed_attempt", failed["disposition"])
        self.assertIsNone(failed["execution_receipt"])
        self.assertEqual("executed_terminal_success", passed["disposition"])
        self.assertEqual("reused_terminal_success", reused["disposition"])
        self.assertNotEqual(
            failed["record"]["execution_id"], passed["record"]["execution_id"]
        )

    def test_terminal_success_is_reused_across_claimed_runs(self) -> None:
        counter = "cross-run-counter.txt"
        script = (
            "import pathlib,sys; p=pathlib.Path(sys.argv[1])/sys.argv[2]; "
            "n=int(p.read_text())+1 if p.exists() else 1; "
            "p.write_text(str(n)); print(n)"
        )
        declaration = {
            "check_id": "check:cross-run",
            "kind": "command",
            "command": sys.executable,
            "args": ["-c", script, "{{repository_root}}", counter],
            "expected": {"exit_code": 0},
            "covers_obligation_ids": ["obligation:intake"],
        }
        target_one = self.root / "target-one"
        target_two = self.root / "target-two"
        target_one.mkdir()
        target_two.mkdir()
        check_one, run_one = self._claim(declaration, target_root=target_one)
        first = self._run(check_one, run_one, target_root=target_one)
        check_two, run_two = self._claim(declaration, target_root=target_two)
        second = self._run(check_two, run_two, target_root=target_two)
        self.assertEqual("executed_terminal_success", first["disposition"])
        self.assertEqual("reused_terminal_success", second["disposition"])
        self.assertEqual("1", (self.repository_root / counter).read_text())
        self.assertFalse(second["record"]["command_executed_in_this_call"])
        self.assertFalse(second["record"]["executed"])
        self.assertEqual(
            first["execution_receipt"]["receipt_id"],
            second["execution_receipt"]["receipt_id"],
        )

    def test_distinct_semantic_checks_do_not_reuse_one_owner_receipt(self) -> None:
        counter = "projection-counter.txt"
        script = (
            "import pathlib,sys; p=pathlib.Path(sys.argv[1])/sys.argv[2]; "
            "n=int(p.read_text())+1 if p.exists() else 1; "
            "p.write_text(str(n))"
        )
        common = {
            "check_id": "check:projection",
            "kind": "command",
            "command": sys.executable,
            "args": ["-c", script, "{{repository_root}}", counter],
            "expected": {"exit_code": 0},
            "covers_obligation_ids": ["obligation:intake"],
        }
        target_one = self.root / "projection-one"
        target_two = self.root / "projection-two"
        target_one.mkdir()
        target_two.mkdir()
        first_check, first_run = self._claim(
            {**common, "semantic_check_id": "projection:one"},
            target_root=target_one,
        )
        first = self._run(first_check, first_run, target_root=target_one)
        second_check, second_run = self._claim(
            {**common, "semantic_check_id": "projection:two"},
            target_root=target_two,
        )
        second = self._run(second_check, second_run, target_root=target_two)
        self.assertNotEqual(
            first_check["projection_declaration_hash"],
            second_check["projection_declaration_hash"],
        )
        self.assertNotEqual(
            first["execution_receipt"]["receipt_id"],
            second["execution_receipt"]["receipt_id"],
        )
        self.assertEqual("executed_terminal_success", second["disposition"])
        self.assertEqual("2", (self.repository_root / counter).read_text())

    def test_identical_checks_in_different_units_keep_independent_receipts(self) -> None:
        counter = "cross-unit-counter.txt"
        declaration = {
            "check_id": "check:unit-local",
            "semantic_check_id": "semantic:unit-local",
            "evidence_subject_id": "subject:unit-local",
            "kind": "command",
            "command": sys.executable,
            "args": [
                "-c",
                (
                    "import pathlib,sys; p=pathlib.Path(sys.argv[1])/sys.argv[2]; "
                    "n=int(p.read_text())+1 if p.exists() else 1; "
                    "p.write_text(str(n))"
                ),
                "{{repository_root}}",
                counter,
            ],
            "expected": {"exit_code": 0},
            "covers_obligation_ids": ["obligation:intake"],
        }
        first_target = self.root / "unit-one-target"
        second_target = self.root / "unit-two-target"
        first_target.mkdir()
        second_target.mkdir()
        first_check, first_run = self._claim(
            declaration,
            target_root=first_target,
            maintenance_unit_id="unit:one",
        )
        second_check, second_run = self._claim(
            declaration,
            target_root=second_target,
            maintenance_unit_id="unit:two",
        )

        first = self._run(first_check, first_run, target_root=first_target)
        second = self._run(second_check, second_run, target_root=second_target)

        self.assertEqual("executed_terminal_success", first["disposition"])
        self.assertEqual("executed_terminal_success", second["disposition"])
        self.assertNotEqual(
            first["execution_receipt"]["receipt_id"],
            second["execution_receipt"]["receipt_id"],
        )
        self.assertEqual("2", (self.repository_root / counter).read_text())

    def test_changed_dependency_receipt_invalidates_only_dependent_owner(self) -> None:
        counter = "dependent-counter.txt"
        dependent_script = (
            "import pathlib,sys; p=pathlib.Path(sys.argv[1])/sys.argv[2]; "
            "n=int(p.read_text())+1 if p.exists() else 1; p.write_text(str(n))"
        )

        def claim_pair(target: Path, source_text: str):
            checks = [
                {
                    "check_id": "check:source",
                    "kind": "command",
                    "command": sys.executable,
                    "args": ["-c", f"print({source_text!r})"],
                    "expected": {"exit_code": 0},
                },
                {
                    "check_id": "check:dependent",
                    "kind": "command",
                    "command": sys.executable,
                    "args": [
                        "-c",
                        dependent_script,
                        "{{repository_root}}",
                        counter,
                    ],
                    "expected": {"exit_code": 0},
                    "depends_on_check_ids": ["check:source"],
                },
            ]
            contract, manifest = runtime_contract_with_checks(checks)
            decision = select_routes(contract, {"function_ids": ["analyze"]})
            claim = claim_run(
                contract,
                {
                    "function_ids": ["analyze"],
                    "write_targets": ["out"],
                    "request": f"dependency {source_text}",
                },
                target,
                decision,
                check_manifest=manifest,
            )
            self.assertTrue(claim.ok, claim.to_dict())
            assert claim.run_root is not None
            return {
                str(row["check_id"]): row for row in manifest["checks"]
            }, claim.run_root

        target_one = self.root / "dependency-one"
        target_two = self.root / "dependency-two"
        target_one.mkdir()
        target_two.mkdir()
        checks_one, run_one = claim_pair(target_one, "source-one")
        source_one = self._run(
            checks_one["check:source"], run_one, target_root=target_one
        )
        dependent_one = self._run(
            checks_one["check:dependent"],
            run_one,
            target_root=target_one,
            dependency_execution_receipts={
                "owner:source": source_one["execution_receipt"]
            },
        )
        checks_two, run_two = claim_pair(target_two, "source-two")
        source_two = self._run(
            checks_two["check:source"], run_two, target_root=target_two
        )
        dependent_two = self._run(
            checks_two["check:dependent"],
            run_two,
            target_root=target_two,
            dependency_execution_receipts={
                "owner:source": source_two["execution_receipt"]
            },
        )
        self.assertNotEqual(
            source_one["execution_receipt"]["receipt_id"],
            source_two["execution_receipt"]["receipt_id"],
        )
        self.assertEqual("executed_terminal_success", dependent_one["disposition"])
        self.assertEqual("executed_terminal_success", dependent_two["disposition"])
        self.assertEqual("2", (self.repository_root / counter).read_text())

    def test_declared_source_change_makes_success_stale(self) -> None:
        implementation = self.repository_root / "implementation.py"
        implementation.write_text("VALUE = 1\n", encoding="utf-8")
        check, run_root = self._claim(
            {
                "check_id": "check:source-bound",
                "kind": "command",
                "command": sys.executable,
                "args": ["-c", "raise SystemExit(0)"],
                "expected": {"exit_code": 0},
                "covers_obligation_ids": ["obligation:intake"],
            },
            implementation_path=implementation,
        )
        self.assertEqual(
            "executed_terminal_success", self._run(check, run_root)["disposition"]
        )
        implementation.write_text("VALUE = 2\n", encoding="utf-8")
        with self.assertRaisesRegex(CheckRunnerError, "check_owner_input_component_stale"):
            self._run(check, run_root)

    def test_tampered_success_receipt_is_quarantined_before_owner_reexecution(self) -> None:
        check, run_root = self._claim(
            {
                "check_id": "check:tamper",
                "kind": "command",
                "command": sys.executable,
                "args": ["-c", "raise SystemExit(0)"],
                "expected": {"exit_code": 0},
                "covers_obligation_ids": ["obligation:intake"],
            }
        )
        first = self._run(check, run_root)
        receipt = first["execution_receipt"]
        receipt_path = (
            self.repository_root
            / "work"
            / "verification"
            / "owner-evidence"
            / first["execution_receipt_ref"]["relative_path"]
        )
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        payload["execution_id"] = "execution-tampered"
        receipt_path.write_text(json.dumps(payload), encoding="utf-8")
        replacement = self._run(check, run_root)
        self.assertEqual("executed_terminal_success", replacement["disposition"])
        findings = list(
            (
                self.repository_root
                / "work"
                / "verification"
                / "owner-evidence"
                / "check-executions"
                / "findings"
            ).glob("*.json")
        )
        self.assertEqual(1, len(findings))
        self.assertTrue(receipt["receipt_hash"])

    def test_tampered_full_output_sidecar_cannot_be_reused(self) -> None:
        counter = "sidecar-counter.txt"
        script = (
            "import pathlib,sys; p=pathlib.Path(sys.argv[1])/sys.argv[2]; "
            "n=int(p.read_text())+1 if p.exists() else 1; "
            "p.write_text(str(n)); print(n)"
        )
        check, run_root = self._claim(
            {
                "check_id": "check:sidecar-tamper",
                "kind": "command",
                "command": sys.executable,
                "args": ["-c", script, "{{repository_root}}", counter],
                "expected": {"exit_code": 0},
            }
        )
        first = self._run(check, run_root)
        stdout_ref = first["execution_receipt"]["sidecars"]["stdout"]
        stdout_path = (
            self.repository_root
            / "work"
            / "verification"
            / "owner-evidence"
            / stdout_ref["relative_path"]
        )
        stdout_path.write_bytes(b"tampered")
        replacement = self._run(check, run_root)
        self.assertEqual("executed_terminal_success", replacement["disposition"])
        self.assertEqual("2", (self.repository_root / counter).read_text())
        self.assertNotEqual(
            stdout_ref["content_hash"],
            replacement["execution_receipt"]["sidecars"]["stdout"][
                "content_hash"
            ],
        )

    def test_timeout_terminates_descendant_tree_before_any_receipt(self) -> None:
        ready = "process-tree/child-ready.txt"
        escaped = "process-tree/child-terminal.txt"
        child = (
            "import os,pathlib,sys,time; "
            "pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); "
            "time.sleep(1.5); pathlib.Path(sys.argv[2]).write_text('escaped')"
        )
        parent = (
            "import pathlib,subprocess,sys,time; "
            "root=pathlib.Path(sys.argv[1]); "
            "ready=root/sys.argv[2]; terminal=root/sys.argv[3]; "
            "ready.parent.mkdir(parents=True,exist_ok=True); "
            "time.sleep(0.15); "
            "subprocess.Popen([sys.executable,'-c',sys.argv[4],str(ready),str(terminal)]); "
            "deadline=time.monotonic()+5; "
            "\nwhile not ready.exists() and time.monotonic()<deadline: time.sleep(0.01)\n"
            "time.sleep(30)"
        )
        check, run_root = self._claim(
            {
                "check_id": "check:process-tree-timeout",
                "kind": "command",
                "command": sys.executable,
                "args": [
                    "-c",
                    parent,
                    "{{repository_root}}",
                    ready,
                    escaped,
                    child,
                ],
                "timeout_seconds": 0.75,
                "expected": {"exit_code": 0},
            }
        )
        result = self._run(check, run_root)
        self.assertEqual("executed_failed_attempt", result["disposition"])
        self.assertIsNone(result["execution_receipt"])
        attempt = result["record"]["result"]
        self.assertEqual("timeout", attempt["reason"])
        self.assertTrue(attempt["cleanup_confirmed"])
        ready_path = self.repository_root / ready
        self.assertTrue(ready_path.is_file())
        child_pid = int(ready_path.read_text(encoding="utf-8"))
        deadline = time.monotonic() + 2.0
        while self._pid_is_running(child_pid) and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertFalse(self._pid_is_running(child_pid))
        time.sleep(1.55)
        self.assertFalse((self.repository_root / escaped).exists())


if __name__ == "__main__":
    unittest.main()
