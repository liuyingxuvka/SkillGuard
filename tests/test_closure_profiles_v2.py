from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _skillguard_v2_runtime_fixture import SCRIPT_ROOT, runtime_contract  # noqa: F401
from skillguard_v2.closure import ClosureError, close_run, evaluate_closure, verify_closure
from skillguard_v2.contract_compiler import canonical_hash
from skillguard_v2.receipts import fingerprint_value, issue_receipt
from skillguard_v2.route_runtime import select_routes
from skillguard_v2.run_store import claim_run
from skillguard_v2.step_runtime import begin_step, record_step, record_verification, replay_run


class ClosureProfilesV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.target = Path(self.temp.name)
        self.contract = runtime_contract()
        decision = select_routes(self.contract, {"function_ids": ["analyze"]})
        claim = claim_run(
            self.contract,
            {"function_ids": ["analyze"], "write_targets": ["out"], "request": "closure fixture"},
            self.target,
            decision,
        )
        self.run_root = claim.run_root
        self.current = {
            "implementation": fingerprint_value("version 1"),
            "contract-input": fingerprint_value("fixture"),
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _hard_receipt(self, step_id: str, check_id: str, decision: str = "passed"):
        return issue_receipt(
            self.run_root,
            step_id=step_id,
            evidence_class="hard",
            evidence={
                "proof_kind": "fixture_assertion",
                "proof_fingerprint": f"proof:{check_id}:{decision}",
                "check_id": check_id,
            },
            decision=decision,
            verifier_id="fixture-verifier",
            input_fingerprints=self.current,
        )

    def _complete_step(self, step_id: str, check_id: str):
        begin_step(self.run_root, step_id)
        record_step(self.run_root, step_id, {"work_record": f"work:{step_id}"})
        receipt = self._hard_receipt(step_id, check_id)
        record_verification(
            self.run_root,
            step_id,
            "passed",
            receipt["receipt_id"],
            verifier="fixture-verifier",
        )
        return receipt

    def _complete_functional(self):
        intake = self._complete_step("step:intake", "check:intake")
        review = self._complete_step("step:optional-review", "check:review")
        finish = self._complete_step("step:finish", "check:finish")
        return intake, review, finish

    def test_functional_can_close_while_release_names_missing_release_evidence(self) -> None:
        self._complete_functional()
        functional, closure = close_run(
            self.run_root,
            profile="functional",
            current_fingerprints=self.current,
        )
        self.assertEqual("closed", functional.status)
        self.assertIsNotNone(closure)
        release = evaluate_closure(
            self.run_root,
            profile="release",
            current_fingerprints=self.current,
        )
        self.assertEqual("incomplete", release.status)
        self.assertIn("obligation:release", release.gaps["missing"])
        self.assertIn("Resolve missing: obligation:release", release.next_actions)

    def test_release_and_highest_quality_are_monotonic_and_judgment_bounded(self) -> None:
        self._complete_functional()
        release_receipt = self._hard_receipt("step:finish", "check:release")
        release, release_closure = close_run(
            self.run_root,
            profile="release",
            current_fingerprints=self.current,
        )
        self.assertEqual("closed", release.status)
        self.assertIn(release_receipt["receipt_id"], release.consumed_receipt_ids)
        self.assertIsNotNone(release_closure)
        self_review = issue_receipt(
            self.run_root,
            step_id="step:finish",
            evidence_class="judged",
            evidence={
                "rubric_id": "rubric:quality",
                "rubric_version": "2",
                "evaluator_id": "same-ai",
                "input_fingerprint": "artifact:quality",
                "conclusion": "looks good",
                "limitations": ["self review"],
                "self_review": True,
                "confidence_boundary": "Advisory self-review only.",
            },
            decision="passed",
            verifier_id="judgment-verifier",
            input_fingerprints=self.current,
        )
        highest = evaluate_closure(
            self.run_root,
            profile="highest_quality",
            current_fingerprints=self.current,
        )
        self.assertEqual("incomplete", highest.status)
        self.assertIn("obligation:quality", highest.gaps["uncertain"])
        independent = issue_receipt(
            self.run_root,
            step_id="step:finish",
            evidence_class="judged",
            evidence={
                "rubric_id": "rubric:quality",
                "rubric_version": "2",
                "evaluator_id": "independent-reviewer",
                "input_fingerprint": "artifact:quality",
                "conclusion": "meets the versioned rubric",
                "limitations": ["fixture scope"],
                "self_review": False,
            },
            decision="passed",
            verifier_id="judgment-verifier",
            input_fingerprints=self.current,
        )
        self.assertEqual(self_review["receipt_id"], independent["supersedes_receipt_id"])
        closed = evaluate_closure(
            self.run_root,
            profile="highest_quality",
            current_fingerprints=self.current,
        )
        self.assertEqual("closed", closed.status)

    def test_closure_is_replay_verifiable_and_supersession_invalidates_old_closure(self) -> None:
        intake, _, _ = self._complete_functional()
        evaluation, closure = close_run(
            self.run_root,
            profile="functional",
            current_fingerprints=self.current,
        )
        verified = verify_closure(
            self.run_root,
            closure["closure_receipt_id"],
            current_fingerprints=self.current,
        )
        self.assertTrue(verified["ok"], verified)
        repeated_evaluation, repeated_closure = close_run(
            self.run_root,
            profile="functional",
            current_fingerprints=self.current,
        )
        self.assertEqual(closure["closure_receipt_id"], repeated_closure["closure_receipt_id"])
        replacement = self._hard_receipt("step:intake", "check:intake")
        self.assertEqual(intake["receipt_id"], replacement["supersedes_receipt_id"])
        stale = verify_closure(
            self.run_root,
            closure["closure_receipt_id"],
            current_fingerprints=self.current,
        )
        self.assertFalse(stale["ok"])
        self.assertIn("closure_consumed_receipts_changed", stale["findings"])

    def test_non_monotonic_contract_profiles_fail_closed(self) -> None:
        broken = runtime_contract()
        broken["closure_profiles"][2]["required_obligation_ids"] = ["obligation:release"]
        broken["contract_hash"] = canonical_hash({key: value for key, value in broken.items() if key != "contract_hash"})
        target = self.target / "broken"
        decision = select_routes(broken, {"function_ids": ["analyze"]})
        claim = claim_run(
            broken,
            {"function_ids": ["analyze"], "write_targets": ["out"], "request": "broken"},
            target,
            decision,
        )
        with self.assertRaises(ClosureError) as raised:
            evaluate_closure(claim.run_root, profile="release", current_fingerprints=self.current)
        self.assertEqual("closure_profiles_non_monotonic", raised.exception.code)

    def test_conditional_obligation_accepts_only_verifier_approved_not_applicable_step(self) -> None:
        conditional = runtime_contract()
        next(row for row in conditional["obligations"] if row["obligation_id"] == "obligation:review")["conditional"] = True
        conditional["contract_hash"] = canonical_hash(
            {key: value for key, value in conditional.items() if key != "contract_hash"}
        )
        target = self.target / "conditional"
        decision = select_routes(conditional, {"function_ids": ["analyze"]})
        claim = claim_run(
            conditional,
            {"function_ids": ["analyze"], "write_targets": ["out"], "request": "conditional"},
            target,
            decision,
        )
        old_root = self.run_root
        self.run_root = claim.run_root
        intake = self._complete_step("step:intake", "check:intake")
        from skillguard_v2.step_runtime import approve_skip, request_skip

        request_skip(self.run_root, "step:optional-review", "not applicable", intake["receipt_id"])
        approve_skip(self.run_root, "step:optional-review", intake["receipt_id"])
        self._complete_step("step:finish", "check:finish")
        evaluation = evaluate_closure(
            self.run_root,
            profile="functional",
            current_fingerprints=self.current,
        )
        self.assertEqual("closed", evaluation.status)
        self.assertEqual(
            "not_applicable",
            next(row for row in evaluation.obligation_results if row["obligation_id"] == "obligation:review")["status"],
        )
        self.run_root = old_root


if __name__ == "__main__":
    unittest.main()
