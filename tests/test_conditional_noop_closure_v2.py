from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from _skillguard_v2_runtime_fixture import (  # noqa: F401
    SCRIPT_ROOT,
    runtime_check_manifest,
    runtime_contract,
)
from skillguard_v2.closure import ClosureError, close_run, verify_closure
from skillguard_v2.contract_compiler import canonical_hash, canonical_json_bytes
from skillguard_v2.contract_schema import validate_compiled_contract
from skillguard_v2.declared_check_supervision import freeze_declared_check_inventory
from skillguard_v2.execution_depth import EXECUTION_DEPTH_PASS
from skillguard_v2.native_terminal import (
    NATIVE_NOOP_RECEIPT_SCHEMA,
    NATIVE_TERMINAL_RECEIPT_SCHEMA,
    NativeTerminalError,
    _select_current_depth_receipt,
    build_target_native_terminal_receipt,
    resolve_native_terminal_receipt,
    write_target_native_terminal_receipt,
)
from skillguard_v2.receipts import fingerprint_value, issue_receipt
from skillguard_v2.route_runtime import select_routes
from skillguard_v2.run_store import claim_run
from skillguard_v2.step_runtime import (
    approve_skip,
    begin_step,
    record_step,
    record_verification,
    request_skip,
)


NOOP_BRANCHES = ("current-noop", "manual-deferred")
COMPLETING_BRANCH = "manual-apply"
def _branch_contract() -> dict[str, object]:
    contract = runtime_contract()
    contract["route_branch_closure_required"] = True
    obligations = {
        row["obligation_id"]: row for row in contract["obligations"]
    }
    obligations["obligation:intake"]["required_check_ids"] = ["check:update"]
    obligations["obligation:review"]["required_check_ids"] = ["check:update"]
    obligations["obligation:release"]["required_check_ids"] = [
        "check:update",
        "check:finalize",
        "check:applicability",
    ]
    obligations["obligation:release"]["conditional"] = True
    steps = {row["step_id"]: row for row in contract["steps"]}
    steps["step:optional-review"]["prerequisite_step_ids"] = ["step:intake"]
    steps["step:optional-review"]["required"] = True
    steps["step:finish"]["prerequisite_step_ids"] = ["step:optional-review"]
    steps["step:finish"]["required"] = False
    for profile in contract["closure_profiles"]:
        profile["required_obligation_ids"] = []
        prepared_obligation_ids = [
            "obligation:intake",
            "obligation:review",
            "obligation:release",
        ]
        profile["route_branch_requirements"] = [
            {
                "native_route_id": "route:analyze",
                "branch_ids": list(NOOP_BRANCHES),
                "required_obligation_ids": [
                    "obligation:intake",
                    "obligation:review",
                ],
                "applicability_rules": [
                    {
                        "obligation_id": "obligation:release",
                        "allowed_disposition": "not_applicable",
                        "verifier_check_id": "check:applicability",
                    }
                ],
            },
            {
                "native_route_id": "route:analyze",
                "branch_ids": [COMPLETING_BRANCH],
                "required_obligation_ids": prepared_obligation_ids,
                "applicability_rules": [],
            },
        ]
    contract["depth_profile"] = {
        "schema_version": "skillguard.depth_profile.v2",
        "profile_id": "profile:update-depth",
        "target_skill_id": "runtime-fixture",
        "integration_mode": "native-integrated",
        "native_owner_id": "fixture-native-update",
        "native_route_ids": ["route:analyze"],
        "native_check_ids": ["check:update"],
        "skillguard_adds_domain_route": False,
        "enforcement_level": "enforced",
        "required_closure_profiles": ["enforced"],
        "provider_runtime": {
            "provider_id": "fixture-provider",
            "required_runtime_contract_id": "fixture-runtime-v2",
            "required_capability_ids": ["declared-check-receipt-reconciliation.v1"],
            "required_enrollment_status": "enrolled",
            "readiness_check_ids": ["check:update"],
        },
        "claim_boundary": "fixture branch depth",
    }
    contract["contract_hash"] = canonical_hash(
        {key: value for key, value in contract.items() if key != "contract_hash"}
    )
    return contract


class ConditionalNoopClosureV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.installation_verifier = patch(
            "skillguard_v2.native_terminal.verify_scheduled_production_installation_identity",
            return_value={"receipt": {"status": "current_installed_parity"}},
        )
        self.installation_verifier_mock = self.installation_verifier.start()
        self.closure_installation_context = patch(
            "skillguard_v2.closure._closure_installation_context",
            return_value=object(),
        )
        self.closure_installation_context_mock = (
            self.closure_installation_context.start()
        )
        self.target = Path(self.temp.name)
        self.contract = _branch_contract()
        decision = select_routes(self.contract, {"function_ids": ["analyze"]})
        claim = claim_run(
            self.contract,
            {
                "function_ids": ["analyze"],
                "write_targets": ["out"],
                "request": "conditional native terminal fixture",
            },
            self.target,
            decision,
            check_manifest=runtime_check_manifest(self.contract),
        )
        self.run_root = claim.run_root
        self.current = {
            "implementation": fingerprint_value("conditional-v1"),
            "contract-input": fingerprint_value("fixture"),
        }
        self._complete("step:intake", "check:update")
        self._complete("step:optional-review", "check:update")

    def tearDown(self) -> None:
        self.closure_installation_context.stop()
        self.installation_verifier.stop()
        self.temp.cleanup()

    def _complete(self, step_id: str, check_id: str, **evidence):
        begin_step(self.run_root, step_id)
        record_step(self.run_root, step_id, {"work_record": f"work:{step_id}"})
        receipt = issue_receipt(
            self.run_root,
            step_id=step_id,
            evidence_class="hard",
            evidence={
                "proof_kind": "fixture_assertion",
                "proof_fingerprint": f"proof:{check_id}",
                "check_id": check_id,
                **evidence,
            },
            decision="passed",
            verifier_id="fixture-verifier",
            input_fingerprints=self.current,
        )
        record_verification(
            self.run_root,
            step_id,
            "passed",
            receipt["receipt_id"],
            verifier="fixture-verifier",
        )
        return receipt

    def _skip_finalize(self) -> None:
        intake_receipt = next(
            json.loads(path.read_text(encoding="utf-8"))
            for path in (self.run_root / "receipts").glob("receipt-*.json")
            if json.loads(path.read_text(encoding="utf-8")).get("step_id")
            == "step:intake"
        )
        request_skip(
            self.run_root,
            "step:finish",
            "verified native no-op branch",
            intake_receipt["receipt_id"],
        )
        approve_skip(
            self.run_root, "step:finish", intake_receipt["receipt_id"]
        )

    def _depth_receipt(
        self,
        branch_id: str,
        *,
        evidence_domain: str = "scheduled_production",
    ) -> dict[str, object]:
        run = json.loads(
            (self.run_root / "run.json").read_text(encoding="utf-8")
        )
        inventory = freeze_declared_check_inventory(
            [
                {
                    "check_id": "check:update",
                    "execution_owner_id": "fixture-native-update",
                    "evidence_domain_id": evidence_domain,
                    "depends_on_check_ids": [],
                }
            ],
            required_check_ids=["check:update"],
        )
        check_result = {
            "check_id": "check:update",
            "execution_owner_id": "fixture-native-update",
            "disposition": "passed",
            "current": True,
            "receipt_id": f"native-check:{branch_id}",
            "receipt_hash": "9" * 64,
        }
        payload: dict[str, object] = {
            "schema_version": "skillguard.target_execution_receipt.v2",
            "sequence": 1,
            "run_id": self.run_root.name,
            "target_skill_id": self.contract["skill_id"],
            "contract_hash": self.contract["contract_hash"],
            "profile_id": "profile:update-depth",
            "profile_fingerprint": canonical_hash(self.contract["depth_profile"]),
            "integration_mode": "native-integrated",
            "native_owner_id": "fixture-native-update",
            "native_route_ids": ["route:analyze"],
            "native_check_ids": ["check:update"],
            "request_fingerprint": run["request_fingerprint"],
            "declared_check_inventory": inventory,
            "declared_check_results": [check_result],
            "unresolved_check_ids": [],
            "evidence_domain": evidence_domain,
            "scheduled_production_identity": (
                {
                    "scheduler_or_trigger_id": "scheduler:update",
                    "scheduled_execution_id": f"scheduled:{branch_id}",
                    "installation_receipt_id": "installation:fixture",
                    "installation_receipt_hash": "D" * 64,
                    "installation_receipt_root_ref": {
                        "path_token": "active_skill_root",
                        "relative_path": ".sg-runtime/installation",
                    },
                    "installed_runtime_fingerprint": "E" * 64,
                }
                if evidence_domain == "scheduled_production"
                else {}
            ),
            "status": EXECUTION_DEPTH_PASS,
            "enforcement_decision": "allow",
            "dimension_results": [],
            "coverage_universe_results": [],
            "obligation_results": [],
            "evidence_contributions": [],
            "provider_runtime_audit": {"status": "passed"},
            "observation_binding": {"source": "declared_check_receipts"},
            "root_role_bindings": {"roots_distinct": False},
            "root_role_bindings_hash": "A" * 64,
            "uncovered_obligation_ids": [],
            "blockers": [],
            "input_fingerprints": self.current,
            "input_fingerprint_hash": canonical_hash(self.current),
            "target_fingerprint": self.contract["contract_hash"],
            "runtime_fingerprint": "7" * 64,
            "active_runtime_identity": {"runtime": "fixture"},
            "active_runtime_identity_hash": "B" * 64,
            "evaluation_hash": canonical_hash(
                {"branch_id": branch_id, "status": EXECUTION_DEPTH_PASS}
            ),
            "supersedes_receipt_id": "",
            "claim_boundary": "exact branch fixture only",
            "created_at": "2026-07-12T00:00:00Z",
            "receipt_id": f"depth-fixture-{branch_id}",
        }
        payload["receipt_hash"] = canonical_hash(payload)
        root = self.run_root / "depth-receipts"
        root.mkdir(parents=True, exist_ok=True)
        (root / f"depth-fixture-{branch_id}.json").write_bytes(
            canonical_json_bytes(payload)
        )
        return payload

    def _terminal_receipt(
        self,
        branch_id: str,
        *,
        profile: str = "enforced",
        evidence_domain: str = "scheduled_production",
        mutate: dict[str, object] | None = None,
    ) -> tuple[str, dict[str, object], dict[str, object]]:
        depth = self._depth_receipt(branch_id, evidence_domain=evidence_domain)
        native_raw = canonical_json_bytes(
            {"native_update_result": branch_id, "observed": True}
        )
        raw_path = self.run_root / "native-terminal" / f"raw-{branch_id}.json"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(native_raw)
        is_noop = branch_id in NOOP_BRANCHES
        payload: dict[str, object] = {
            "schema_version": (
                NATIVE_NOOP_RECEIPT_SCHEMA
                if is_noop
                else NATIVE_TERMINAL_RECEIPT_SCHEMA
            ),
            "target_skill_id": self.contract["skill_id"],
            "target_contract_hash": self.contract["contract_hash"],
            "depth_profile_hash": canonical_hash(self.contract["depth_profile"]),
            "native_owner_id": "fixture-native-update",
            "native_route_id": "route:analyze",
            "native_check_id": "check:update",
            "run_id": self.run_root.name,
            "branch_id": branch_id,
            "terminal_kind": "conditional_noop" if is_noop else "completed_branch",
            "closure_profile": profile,
            "closure_disposition": (
                "terminal_completion"
                if profile == "enforced"
                else "non_terminal_authorization"
            ),
            "reason_code": branch_id,
            "observed_state_fingerprint": "C" * 64,
            "target_obligation_ids": (
                ["obligation:intake", "obligation:review"]
                if is_noop
                else [
                    "obligation:intake",
                    "obligation:review",
                    "obligation:release",
                ]
            ),
            "evidence_domain": evidence_domain,
            "scheduled_production_identity": dict(
                depth["scheduled_production_identity"]
            ),
            "depth_receipt_id": depth["receipt_id"],
            "depth_receipt_hash": depth["receipt_hash"],
            "native_receipt_artifact_ref": {
                "path_token": "run_root",
                "relative_path": raw_path.relative_to(self.run_root).as_posix(),
            },
            "native_receipt_hash": hashlib.sha256(native_raw).hexdigest().upper(),
            "created_at": "2026-07-12T00:00:00Z",
        }
        if mutate:
            payload.update(mutate)
        prefix = "native-noop" if is_noop else "native-terminal"
        payload["receipt_id"] = f"{prefix}-{canonical_hash(payload)[:24].lower()}"
        payload["receipt_hash"] = canonical_hash(payload)
        path = self.run_root / "native-terminal" / f"terminal-{branch_id}.json"
        path.write_bytes(canonical_json_bytes(payload))
        return path.relative_to(self.run_root).as_posix(), payload, depth

    @staticmethod
    def _gate(depth: dict[str, object]) -> dict[str, object]:
        return {
            "required": True,
            "ok": True,
            "status": EXECUTION_DEPTH_PASS,
            "receipt_id": depth["receipt_id"],
            "detail": "current execution-depth receipt",
            "root_role_bindings_hash": "A" * 64,
        }

    def test_target_owned_builder_consumes_exact_depth_without_finalize_placeholder(self) -> None:
        self._skip_finalize()
        depth = self._depth_receipt("current-noop")
        native_path = self.run_root / "native-terminal" / "builder-native.json"
        native_path.parent.mkdir(parents=True, exist_ok=True)
        native_path.write_bytes(
            canonical_json_bytes(
                {"branch_id": "current-noop", "update_available": False}
            )
        )
        built = build_target_native_terminal_receipt(
            self.run_root,
            self.contract,
            profile="enforced",
            native_route_id="route:analyze",
            branch_id="current-noop",
            native_check_id="check:update",
            native_receipt_artifact_ref={
                "path_token": "run_root",
                "relative_path": native_path.relative_to(
                    self.run_root
                ).as_posix(),
            },
            observed_state={"update_available": False},
            created_at="2026-07-12T00:00:00Z",
        )
        persisted = write_target_native_terminal_receipt(
            self.run_root, built
        )
        self.assertEqual(depth["receipt_id"], built["depth_receipt_id"])
        self.assertEqual(depth["receipt_hash"], built["depth_receipt_hash"])
        self.assertEqual("enforced", built["closure_profile"])
        self.assertEqual("terminal_completion", built["closure_disposition"])
        self.assertEqual(
            ["obligation:intake", "obligation:review"],
            built["target_obligation_ids"],
        )
        self.assertNotIn("obligation:release", built["target_obligation_ids"])
        self.assertEqual(
            "active_skill_root",
            built["scheduled_production_identity"][
                "installation_receipt_root_ref"
            ]["path_token"],
        )
        with patch(
            "skillguard_v2.closure.evaluate_depth_receipt_gate",
            return_value=self._gate(depth),
        ):
            evaluation, closure = close_run(
                self.run_root,
                profile="enforced",
                current_fingerprints=self.current,
                repository_root=self.target,
                target_root=self.target,
                native_terminal_receipt_ref=persisted["receipt_ref"],
                expected_route_id="route:analyze",
                expected_branch_id="current-noop",
            )
        self.assertEqual("closed", evaluation.status)
        self.assertIsNotNone(closure)

    def test_non_scheduled_terminal_inherits_depth_domain_without_scheduler_identity(self) -> None:
        self._skip_finalize()
        depth = self._depth_receipt(
            "current-noop", evidence_domain="capability_validation"
        )
        native_path = self.run_root / "native-terminal" / "manual-native.json"
        native_path.parent.mkdir(parents=True, exist_ok=True)
        native_path.write_bytes(
            canonical_json_bytes(
                {"branch_id": "current-noop", "manual_execution": True}
            )
        )
        built = build_target_native_terminal_receipt(
            self.run_root,
            self.contract,
            profile="enforced",
            native_route_id="route:analyze",
            branch_id="current-noop",
            native_check_id="check:update",
            native_receipt_artifact_ref={
                "path_token": "run_root",
                "relative_path": native_path.relative_to(self.run_root).as_posix(),
            },
            observed_state={"manual_execution": True},
            created_at="2026-07-12T00:00:00Z",
        )
        persisted = write_target_native_terminal_receipt(self.run_root, built)
        run = json.loads((self.run_root / "run.json").read_text(encoding="utf-8"))
        resolved = resolve_native_terminal_receipt(
            self.run_root,
            self.contract,
            run,
            profile="enforced",
            artifact_ref=persisted["receipt_ref"],
            expected_route_id="route:analyze",
            expected_branch_id="current-noop",
        )
        self.assertEqual("capability_validation", built["evidence_domain"])
        self.assertEqual({}, built["scheduled_production_identity"])
        self.assertEqual("current-noop", resolved.branch_id)
        self.assertTrue(resolved.is_noop)
        self.installation_verifier_mock.assert_not_called()

    def test_production_depth_selection_ignores_later_nonproduction_result(self) -> None:
        passed = self._depth_receipt("current-noop")
        shallow = {
            **passed,
            "receipt_id": "depth-capability-only",
            "status": "BOUNDED_PARTIAL",
            "evidence_domain": "capability_validation",
        }
        selected = _select_current_depth_receipt(
            [passed, shallow],
            target_skill_id=str(self.contract["skill_id"]),
            contract_hash=str(self.contract["contract_hash"]),
            native_owner_id="fixture-native-update",
            run_id=self.run_root.name,
            native_check_id="check:update",
        )
        self.assertIs(passed, selected)

    def test_duplicate_production_depth_passes_block_terminal_selection(self) -> None:
        passed = self._depth_receipt("current-noop")
        duplicate = {**passed, "receipt_id": "depth-duplicate-pass"}
        with self.assertRaises(NativeTerminalError) as ambiguity:
            _select_current_depth_receipt(
                [passed, duplicate],
                target_skill_id=str(self.contract["skill_id"]),
                contract_hash=str(self.contract["contract_hash"]),
                native_owner_id="fixture-native-update",
                run_id=self.run_root.name,
                native_check_id="check:update",
            )
        self.assertEqual(
            "native_noop_depth_receipt_ambiguous", ambiguity.exception.code
        )

    def test_missing_production_depth_pass_blocks_terminal_selection(self) -> None:
        passed = self._depth_receipt("current-noop")
        shallow = {
            **passed,
            "receipt_id": "depth-shallow-only",
            "status": "SHALLOW_BLOCKED",
        }
        with self.assertRaises(NativeTerminalError) as missing:
            _select_current_depth_receipt(
                [shallow],
                target_skill_id=str(self.contract["skill_id"]),
                contract_hash=str(self.contract["contract_hash"]),
                native_owner_id="fixture-native-update",
                run_id=self.run_root.name,
                native_check_id="check:update",
            )
        self.assertEqual("native_noop_depth_receipt_missing", missing.exception.code)

    def test_target_owned_builder_keeps_prepared_finalize_active(self) -> None:
        self._complete("step:finish", "check:finalize")
        depth = self._depth_receipt(COMPLETING_BRANCH)
        native_path = self.run_root / "native-terminal" / "prepared-native.json"
        native_path.parent.mkdir(parents=True, exist_ok=True)
        native_path.write_bytes(
            canonical_json_bytes(
                {"branch_id": COMPLETING_BRANCH, "completed": True}
            )
        )
        built = build_target_native_terminal_receipt(
            self.run_root,
            self.contract,
            profile="enforced",
            native_route_id="route:analyze",
            branch_id=COMPLETING_BRANCH,
            native_check_id="check:update",
            native_receipt_artifact_ref={
                "path_token": "run_root",
                "relative_path": native_path.relative_to(
                    self.run_root
                ).as_posix(),
            },
            observed_state={"prepared": True},
            created_at="2026-07-12T00:00:00Z",
        )
        persisted = write_target_native_terminal_receipt(
            self.run_root, built
        )
        self.assertEqual(NATIVE_TERMINAL_RECEIPT_SCHEMA, built["schema_version"])
        self.assertEqual("completed_branch", built["terminal_kind"])
        self.assertEqual("enforced", built["closure_profile"])
        self.assertEqual("terminal_completion", built["closure_disposition"])
        self.assertEqual(depth["receipt_id"], built["depth_receipt_id"])
        self.assertIn("obligation:release", built["target_obligation_ids"])
        with patch(
            "skillguard_v2.closure.evaluate_depth_receipt_gate",
            return_value=self._gate(depth),
        ):
            evaluation, closure = close_run(
                self.run_root,
                profile="enforced",
                current_fingerprints=self.current,
                repository_root=self.target,
                target_root=self.target,
                native_terminal_receipt_ref=persisted["receipt_ref"],
                expected_route_id="route:analyze",
                expected_branch_id=COMPLETING_BRANCH,
            )
        self.assertEqual("closed", evaluation.status)
        self.assertIsNotNone(closure)
        self.assertFalse(evaluation.applicability_results)

    def test_non_enforced_terminal_profile_is_rejected(self) -> None:
        self._depth_receipt(COMPLETING_BRANCH)
        native_path = self.run_root / "native-terminal" / "prepared-authorize-native.json"
        native_path.parent.mkdir(parents=True, exist_ok=True)
        native_path.write_bytes(
            canonical_json_bytes(
                {"branch_id": COMPLETING_BRANCH, "authorized": True, "finalized": False}
            )
        )
        with self.assertRaises(NativeTerminalError) as rejected:
            build_target_native_terminal_receipt(
                self.run_root,
                self.contract,
                profile="routine",
                native_route_id="route:analyze",
                branch_id=COMPLETING_BRANCH,
                native_check_id="check:update",
                native_receipt_artifact_ref={
                    "path_token": "run_root",
                    "relative_path": native_path.relative_to(self.run_root).as_posix(),
                },
                observed_state={"authorized": True, "finalized": False},
            )
        self.assertEqual(
            "native_terminal_closure_profile_invalid", rejected.exception.code
        )

    def test_terminal_closure_replays_installation_currentness(self) -> None:
        self._skip_finalize()
        ref, _terminal, _depth = self._terminal_receipt("current-noop")
        self.closure_installation_context.stop()
        try:
            with self.assertRaises(ClosureError) as missing_context:
                close_run(
                    self.run_root,
                    profile="enforced",
                    current_fingerprints=self.current,
                    repository_root=self.target,
                    target_root=self.target,
                    native_terminal_receipt_ref=ref,
                )
            self.assertEqual(
                "verified_installation_context_required",
                missing_context.exception.code,
            )
        finally:
            self.closure_installation_context_mock = (
                self.closure_installation_context.start()
            )
        self.installation_verifier_mock.side_effect = ValueError(
            "scheduled_installation_receipt_not_current"
        )
        with self.assertRaises(ClosureError) as stale:
            close_run(
                self.run_root,
                profile="enforced",
                current_fingerprints=self.current,
                repository_root=self.target,
                target_root=self.target,
                native_terminal_receipt_ref=ref,
            )
        self.assertEqual(
            "scheduled_production_installation_not_current",
            stale.exception.code,
        )

    def test_each_legal_noop_closes_enforced_without_finalize_witness(self) -> None:
        for branch_id in NOOP_BRANCHES:
            with self.subTest(branch_id=branch_id):
                if branch_id != NOOP_BRANCHES[0]:
                    self.tearDown()
                    self.setUp()
                self._skip_finalize()
                ref, _terminal, depth = self._terminal_receipt(branch_id)
                with patch(
                    "skillguard_v2.closure.evaluate_depth_receipt_gate",
                    return_value=self._gate(depth),
                ):
                    evaluation, closure = close_run(
                        self.run_root,
                        profile="enforced",
                        current_fingerprints=self.current,
                        repository_root=self.target,
                        target_root=self.target,
                        native_terminal_receipt_ref=ref,
                        expected_route_id="route:analyze",
                        expected_branch_id=branch_id,
                    )
                    verified = verify_closure(
                        self.run_root,
                        closure["closure_receipt_id"],
                        current_fingerprints=self.current,
                        repository_root=self.target,
                        target_root=self.target,
                    )
                self.assertEqual("closed", evaluation.status)
                finalize = next(
                    row
                    for row in evaluation.obligation_results
                    if row["obligation_id"] == "obligation:release"
                )
                self.assertEqual("not_applicable", finalize["status"])
                self.assertFalse(
                    evaluation.applicability_results[0][
                        "evidence_witness_consumed"
                    ]
                )
                self.assertTrue(verified["ok"], verified)
                self.assertTrue(
                    list((self.run_root / "applicability-receipts").glob("*.json"))
                )

    def test_non_enforced_and_bare_branch_shortcuts_are_rejected(self) -> None:
        self._skip_finalize()
        ref, _terminal, _depth = self._terminal_receipt("current-noop")
        with self.assertRaises(ClosureError) as routine:
            close_run(
                self.run_root,
                profile="routine",
                current_fingerprints=self.current,
                native_terminal_receipt_ref=ref,
            )
        self.assertEqual("closure_profile_unknown", routine.exception.code)
        with self.assertRaises(ClosureError) as bare:
            close_run(
                self.run_root,
                profile="enforced",
                current_fingerprints=self.current,
                expected_branch_id="current-noop",
            )
        self.assertEqual("bare_branch_label_rejected", bare.exception.code)

    def test_wrong_target_run_and_expected_branch_fail_with_specific_codes(self) -> None:
        self._skip_finalize()
        cases = (
            ({"target_skill_id": "foreign-target"}, "native_terminal_target_skill_mismatch"),
            ({"run_id": "foreign-run"}, "native_terminal_run_mismatch"),
        )
        for mutate, expected in cases:
            with self.subTest(expected=expected):
                if expected != cases[0][1]:
                    self.tearDown()
                    self.setUp()
                    self._skip_finalize()
                ref, _terminal, _depth = self._terminal_receipt(
                    "current-noop", mutate=mutate
                )
                with self.assertRaises(ClosureError) as raised:
                    close_run(
                        self.run_root,
                        profile="enforced",
                        current_fingerprints=self.current,
                        native_terminal_receipt_ref=ref,
                    )
                self.assertEqual(expected, raised.exception.code)
        self.tearDown()
        self.setUp()
        self._skip_finalize()
        ref, _terminal, _depth = self._terminal_receipt("current-noop")
        with self.assertRaises(ClosureError) as mismatch:
            close_run(
                self.run_root,
                profile="enforced",
                current_fingerprints=self.current,
                native_terminal_receipt_ref=ref,
                expected_branch_id="another-target-branch",
            )
        self.assertEqual(
            "native_terminal_expected_branch_mismatch", mismatch.exception.code
        )

    def test_wrong_native_receipt_and_missing_depth_receipt_are_rejected(self) -> None:
        self._skip_finalize()
        ref, _terminal, _depth = self._terminal_receipt(
            "current-noop", mutate={"native_receipt_hash": "9" * 64}
        )
        with self.assertRaises(ClosureError) as native_hash:
            close_run(
                self.run_root,
                profile="enforced",
                current_fingerprints=self.current,
                native_terminal_receipt_ref=ref,
            )
        self.assertEqual(
            "native_terminal_native_receipt_hash_mismatch",
            native_hash.exception.code,
        )

        self.tearDown()
        self.setUp()
        self._skip_finalize()
        ref, _terminal, _depth = self._terminal_receipt("current-noop")
        for path in (self.run_root / "depth-receipts").glob("*.json"):
            path.unlink()
        with self.assertRaises(ClosureError) as missing_depth:
            close_run(
                self.run_root,
                profile="enforced",
                current_fingerprints=self.current,
                native_terminal_receipt_ref=ref,
            )
        self.assertEqual(
            "native_noop_depth_receipt_missing", missing_depth.exception.code
        )

    def test_placeholder_and_caller_applicability_cannot_satisfy_finalize(self) -> None:
        for evidence, expected in (
            ({"placeholder": True}, "placeholder_finalize_witness_rejected"),
            (
                {"disposition": "not_applicable"},
                "caller_authored_applicability_rejected",
            ),
        ):
            with self.subTest(expected=expected):
                if expected != "placeholder_finalize_witness_rejected":
                    self.tearDown()
                    self.setUp()
                issue_receipt(
                    self.run_root,
                    step_id="step:finish",
                    evidence_class="hard",
                    evidence={
                        "proof_kind": "fixture_assertion",
                        "proof_fingerprint": "placeholder-finalize",
                        "check_id": "check:finalize",
                        **evidence,
                    },
                    decision="passed",
                    verifier_id="caller",
                    input_fingerprints=self.current,
                )
                self._skip_finalize()
                ref, _terminal, depth = self._terminal_receipt("current-noop")
                with patch(
                    "skillguard_v2.closure.evaluate_depth_receipt_gate",
                    return_value=self._gate(depth),
                ):
                    evaluation, closure = close_run(
                        self.run_root,
                        profile="enforced",
                        current_fingerprints=self.current,
                        repository_root=self.target,
                        target_root=self.target,
                        native_terminal_receipt_ref=ref,
                    )
                self.assertIsNone(closure)
                self.assertTrue(
                    any(
                        target.startswith(expected)
                        for target in evaluation.gaps.get("blocked", ())
                    ),
                    evaluation.gaps,
                )

    def test_completed_branch_keeps_finalize_active(self) -> None:
        ref, _terminal, depth = self._terminal_receipt(COMPLETING_BRANCH)
        with patch(
            "skillguard_v2.closure.evaluate_depth_receipt_gate",
            return_value=self._gate(depth),
        ):
            missing, closure = close_run(
                self.run_root,
                profile="enforced",
                current_fingerprints=self.current,
                repository_root=self.target,
                target_root=self.target,
                native_terminal_receipt_ref=ref,
            )
        self.assertIsNone(closure)
        self.assertIn("obligation:release", missing.gaps["missing"])

        self.tearDown()
        self.setUp()
        self._complete("step:finish", "check:finalize")
        ref, _terminal, depth = self._terminal_receipt(COMPLETING_BRANCH)
        with patch(
            "skillguard_v2.closure.evaluate_depth_receipt_gate",
            return_value=self._gate(depth),
        ):
            complete, closure = close_run(
                self.run_root,
                profile="enforced",
                current_fingerprints=self.current,
                repository_root=self.target,
                target_root=self.target,
                native_terminal_receipt_ref=ref,
            )
        self.assertEqual("closed", complete.status)
        self.assertIsNotNone(closure)
        self.assertFalse(complete.applicability_results)
        self.assertEqual(
            "passed",
            next(
                row
                for row in complete.obligation_results
                if row["obligation_id"] == "obligation:release"
            )["status"],
        )

    def test_compiler_accepts_arbitrary_branch_map_and_rejects_unreachable_condition(self) -> None:
        valid = _branch_contract()
        valid_codes = {row.code for row in validate_compiled_contract(valid)}
        self.assertEqual(["enforced"], [row["profile_id"] for row in valid["closure_profiles"]])
        self.assertNotIn("closure_profiles_incomplete", valid_codes)

        never_applicable = _branch_contract()
        completing = never_applicable["closure_profiles"][-1][
            "route_branch_requirements"
        ][1]
        completing["required_obligation_ids"] = [
            "obligation:intake",
            "obligation:review",
        ]
        completing[
            "applicability_rules"
        ] = [
            {
                "obligation_id": "obligation:release",
                "allowed_disposition": "not_applicable",
                "verifier_check_id": "check:applicability",
            }
        ]
        invalid_codes = {
            row.code for row in validate_compiled_contract(never_applicable)
        }
        self.assertIn(
            "conditional_obligation_never_applicable", invalid_codes
        )

    def test_compiler_rejects_missing_and_never_conditional_dispositions(self) -> None:
        missing = _branch_contract()
        missing["closure_profiles"][-1]["route_branch_requirements"][0][
            "applicability_rules"
        ] = []
        missing_codes = {row.code for row in validate_compiled_contract(missing)}
        self.assertIn(
            "conditional_obligation_branch_disposition_missing", missing_codes
        )

        always_active = _branch_contract()
        noop = always_active["closure_profiles"][-1]["route_branch_requirements"][0]
        noop["required_obligation_ids"] = [
            "obligation:intake",
            "obligation:review",
            "obligation:release",
        ]
        noop["applicability_rules"] = []
        always_codes = {
            row.code for row in validate_compiled_contract(always_active)
        }
        self.assertIn(
            "conditional_obligation_never_not_applicable", always_codes
        )

    def test_conditional_obligation_cannot_opt_out_by_omitting_branch_contract(self) -> None:
        missing = _branch_contract()
        for profile in missing["closure_profiles"]:
            profile.pop("route_branch_requirements", None)
        codes = {row.code for row in validate_compiled_contract(missing)}
        self.assertIn("conditional_obligation_branch_contract_missing", codes)

    def test_conditional_branch_contract_requires_explicit_opt_in(self) -> None:
        missing_opt_in = _branch_contract()
        missing_opt_in.pop("route_branch_closure_required")
        codes = {row.code for row in validate_compiled_contract(missing_opt_in)}
        self.assertIn("route_branch_closure_opt_in_missing", codes)

        mismatched_opt_in = _branch_contract()
        mismatched_opt_in["route_branch_closure_required"] = False
        codes = {row.code for row in validate_compiled_contract(mismatched_opt_in)}
        self.assertIn("route_branch_closure_opt_in_mismatch", codes)


if __name__ == "__main__":
    unittest.main()
