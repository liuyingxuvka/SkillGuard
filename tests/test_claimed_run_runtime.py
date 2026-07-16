from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _skillguard_v2_runtime_fixture import SCRIPT_ROOT, runtime_check_manifest, runtime_contract  # noqa: F401
from skillguard_v2.contract_compiler import canonical_hash
from skillguard_v2.route_runtime import select_routes
from skillguard_v2.run_store import claim_run, load_events, release_run_locks
from skillguard_v2.receipts import fingerprint_value, issue_receipt
from skillguard_v2.step_runtime import (
    StepRuntimeError,
    approve_skip,
    begin_step,
    next_ready_steps,
    record_blocker,
    record_failure,
    record_step,
    record_verification,
    reopen_step,
    replay_run,
    request_skip,
)


class ClaimedRunRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.target = Path(self.temp.name)
        self.contract = runtime_contract()
        self.manifest = runtime_check_manifest(self.contract)
        self.decision = select_routes(self.contract, {"function_ids": ["analyze"]})

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _claim(self, request=None):
        request = request or {
            "function_ids": ["analyze"],
            "write_targets": ["src"],
            "request": "audit fixture",
        }
        result = claim_run(
            self.contract,
            request,
            self.target,
            self.decision,
            check_manifest=self.manifest,
        )
        self.assertTrue(result.ok, result.to_dict())
        self.assertIsNotNone(result.run_root)
        return result

    def test_claim_is_idempotent_for_identical_identity(self) -> None:
        first = self._claim()
        second = self._claim()
        self.assertEqual(first.run_id, second.run_id)
        self.assertTrue(second.idempotent)

    def test_idempotent_resume_reacquires_released_write_locks(self) -> None:
        first = self._claim()
        release_run_locks(first.run_root)
        self.assertEqual([], list((self.target / ".skillguard" / "locks").glob("*.json")))
        resumed = self._claim()
        self.assertTrue(resumed.idempotent)
        lock_rows = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in (self.target / ".skillguard" / "locks").glob("*.json")
        ]
        self.assertEqual(1, len(lock_rows))
        self.assertEqual(first.run_id, lock_rows[0]["run_id"])
        self.assertIsInstance(lock_rows[0]["owner_pid"], int)

    def test_guard_runtime_change_claims_a_new_run_instead_of_reusing_completed_identity(self) -> None:
        request = {
            "function_ids": ["analyze"],
            "write_targets": ["src"],
            "request": "guard compatibility fixture",
        }
        first = claim_run(
            self.contract,
            request,
            self.target,
            self.decision,
            check_manifest=self.manifest,
            guard_runtime_identity={"runtime_id": "skillguard-v2", "source_hash": "A"},
        )
        self.assertTrue(first.ok, first.to_dict())
        release_run_locks(first.run_root)
        second = claim_run(
            self.contract,
            request,
            self.target,
            self.decision,
            check_manifest=self.manifest,
            guard_runtime_identity={"runtime_id": "skillguard-v2", "source_hash": "B"},
        )
        self.assertFalse(second.idempotent)
        self.assertNotEqual(first.run_id, second.run_id)
        run_record = json.loads(second.run_root.joinpath("run.json").read_text(encoding="utf-8"))
        self.assertEqual("B", run_record["guard_runtime_identity"]["source_hash"])

    def test_conflicting_writer_is_blocked(self) -> None:
        self._claim()
        conflict = claim_run(
            self.contract,
            {"function_ids": ["analyze"], "write_targets": ["src"], "request": "different"},
            self.target,
            self.decision,
            check_manifest=self.manifest,
        )
        self.assertFalse(conflict.ok)
        self.assertEqual({"conflicting_writer_claim"}, {row.code for row in conflict.findings})

    def test_nested_write_target_conflicts_with_owned_parent(self) -> None:
        self._claim()
        conflict = claim_run(
            self.contract,
            {
                "function_ids": ["analyze"],
                "write_targets": ["src/nested/file.py"],
                "request": "nested writer",
            },
            self.target,
            self.decision,
            check_manifest=self.manifest,
        )
        self.assertFalse(conflict.ok)
        self.assertEqual({"conflicting_writer_claim"}, {row.code for row in conflict.findings})

    def test_dead_owner_lock_is_recovered_with_an_audit_event(self) -> None:
        first = self._claim()
        for path in (self.target / ".skillguard" / "locks").glob("*.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["owner_pid"] = 999999
            path.write_text(json.dumps(payload), encoding="utf-8")
        recovered = claim_run(
            self.contract,
            {"function_ids": ["analyze"], "write_targets": ["src"], "request": "replacement"},
            self.target,
            self.decision,
            check_manifest=self.manifest,
        )
        self.assertTrue(recovered.ok, recovered.to_dict())
        self.assertNotEqual(first.run_id, recovered.run_id)
        recovery_events = [
            row for row in load_events(first.run_root) if row["event_type"] == "stale_locks_recovered"
        ]
        self.assertEqual(1, len(recovery_events))
        self.assertEqual(["owner_process_not_alive"], recovery_events[0]["payload"]["reasons"])

    def test_non_current_lock_without_owner_pid_blocks_without_fallback(self) -> None:
        first = self._claim()
        begin_step(first.run_root, "step:intake")
        record_step(first.run_root, "step:intake", {"check_record_ids": ["fixture"]})
        record_failure(first.run_root, "step:intake", "check passes", "failed", "fixture failure")
        for path in (self.target / ".skillguard" / "locks").glob("*.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload.pop("owner_pid", None)
            path.write_text(json.dumps(payload), encoding="utf-8")
        blocked = claim_run(
            self.contract,
            {"function_ids": ["analyze"], "write_targets": ["src"], "request": "post-failure"},
            self.target,
            self.decision,
            check_manifest=self.manifest,
        )
        self.assertFalse(blocked.ok, blocked.to_dict())
        self.assertEqual(
            {"conflicting_writer_claim"},
            {row.code for row in blocked.findings},
        )
        events = load_events(first.run_root)
        self.assertNotIn(
            "stale_locks_recovered",
            {row["event_type"] for row in events},
        )

    def test_step_progression_rejects_caller_authored_pass_and_supports_verified_skip(self) -> None:
        run_root = self._claim().run_root
        self.assertEqual(["step:intake"], [row["step_id"] for row in next_ready_steps(run_root)])
        begin_step(run_root, "step:intake")
        with self.assertRaises(StepRuntimeError) as forged:
            record_step(run_root, "step:intake", {"passed": True, "note": "trust me"})
        self.assertEqual("caller_authored_authoritative_status", forged.exception.code)
        record_step(run_root, "step:intake", {"artifact_id": "artifact:intake"})
        receipt = issue_receipt(
            run_root,
            step_id="step:intake",
            evidence_class="hard",
            evidence={"proof_kind": "fixture", "proof_fingerprint": "proof:intake"},
            decision="passed",
            verifier_id="fixture-verifier",
            input_fingerprints={"input": fingerprint_value("fixture")},
        )
        record_verification(
            run_root,
            "step:intake",
            "passed",
            receipt["receipt_id"],
            verifier="fixture-verifier",
        )
        self.assertEqual(("step:optional-review",), replay_run(run_root).ready_step_ids)
        request_skip(run_root, "step:optional-review", "not applicable", receipt["receipt_id"])
        approve_skip(run_root, "step:optional-review", receipt["receipt_id"])
        self.assertEqual(("step:finish",), replay_run(run_root).ready_step_ids)

    def test_required_step_cannot_skip(self) -> None:
        run_root = self._claim().run_root
        with self.assertRaises(StepRuntimeError) as raised:
            request_skip(run_root, "step:intake", "wanted", "receipt:condition")
        self.assertEqual("required_step_cannot_skip", raised.exception.code)

    def test_optional_skip_rejects_nonexistent_condition_receipt(self) -> None:
        run_root = self._claim().run_root
        with self.assertRaises(StepRuntimeError) as raised:
            request_skip(run_root, "step:optional-review", "not applicable", "receipt:forged")
        self.assertEqual("skip_condition_receipt_invalid", raised.exception.code)

    def test_failure_block_and_reopen_obey_legal_states(self) -> None:
        run_root = self._claim().run_root
        with self.assertRaises(StepRuntimeError) as premature:
            record_failure(run_root, "step:intake", "expected", "actual", "reason")
        self.assertEqual("failure_state_invalid", premature.exception.code)
        begin_step(run_root, "step:intake")
        record_blocker(run_root, "step:intake", "dependency missing", "install dependency")
        self.assertEqual("blocked", replay_run(run_root).status)
        reopen_step(run_root, "step:intake", "dependency installed")
        state = replay_run(run_root)
        self.assertEqual("claimed", state.status)
        self.assertEqual(("step:intake",), state.ready_step_ids)

    def test_judged_step_rejects_hard_receipt_as_primary_verification(self) -> None:
        judged_contract = runtime_contract()
        intake_step = next(row for row in judged_contract["steps"] if row["step_id"] == "step:intake")
        intake_step["binding"] = {
            "action": {"kind": "judged", "rubric_id": "rubric:quality"},
            "check_ids": ["check:intake"],
        }
        judged_contract["contract_hash"] = canonical_hash(
            {key: value for key, value in judged_contract.items() if key != "contract_hash"}
        )
        target = self.target / "judged"
        decision = select_routes(judged_contract, {"function_ids": ["analyze"]})
        claim = claim_run(
            judged_contract,
            {"function_ids": ["analyze"], "write_targets": ["src"], "request": "judged fixture"},
            target,
            decision,
            check_manifest=runtime_check_manifest(judged_contract),
        )
        begin_step(claim.run_root, "step:intake")
        record_step(claim.run_root, "step:intake", {"work_record": "fixture"})
        hard = issue_receipt(
            claim.run_root,
            step_id="step:intake",
            evidence_class="hard",
            evidence={"proof_kind": "fixture", "proof_fingerprint": "proof:hard"},
            decision="passed",
            verifier_id="fixture-verifier",
            input_fingerprints={"input": fingerprint_value("fixture")},
        )
        with self.assertRaises(StepRuntimeError) as raised:
            record_verification(
                claim.run_root,
                "step:intake",
                "passed",
                hard["receipt_id"],
                verifier="fixture-verifier",
            )
        self.assertEqual("verifier_receipt_wrong_evidence_class", raised.exception.code)
        judged = issue_receipt(
            claim.run_root,
            step_id="step:intake",
            evidence_class="judged",
            evidence={
                "rubric_id": "rubric:quality",
                "rubric_version": "2",
                "evaluator_id": "fixture-evaluator",
                "input_fingerprint": "fixture-input",
                "conclusion": "meets the declared rubric",
                "limitations": ["fixture scope"],
                "self_review": False,
            },
            decision="passed",
            verifier_id="fixture-evaluator",
            input_fingerprints={"input": fingerprint_value("fixture")},
        )
        record_verification(
            claim.run_root,
            "step:intake",
            "passed",
            judged["receipt_id"],
            verifier="fixture-evaluator",
        )
        self.assertEqual("passed", replay_run(claim.run_root).step_statuses["step:intake"])


if __name__ == "__main__":
    unittest.main()
