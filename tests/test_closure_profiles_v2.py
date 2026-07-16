from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _skillguard_v2_runtime_fixture import SCRIPT_ROOT, runtime_check_manifest, runtime_contract  # noqa: F401
from skillguard_v2.closure import ClosureError, close_run, evaluate_closure, verify_closure
from skillguard_v2.contract_compiler import canonical_hash
from skillguard_v2.receipts import fingerprint_value, issue_receipt
from skillguard_v2.route_runtime import select_routes
from skillguard_v2.run_store import claim_run
from skillguard_v2.step_runtime import begin_step, record_step, record_verification


class ClosureProfilesV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.target = Path(self.temp.name)
        self.contract = runtime_contract()
        decision = select_routes(self.contract, {"function_ids": ["analyze"]})
        claim = claim_run(
            self.contract,
            {
                "function_ids": ["analyze"],
                "claim_scope": "enforced",
                "write_targets": ["out"],
                "request": "closure fixture",
            },
            self.target,
            decision,
            check_manifest=runtime_check_manifest(self.contract),
        )
        self.assertTrue(claim.ok, claim)
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

    def _complete_steps(self):
        intake = self._complete_step("step:intake", "check:intake")
        self._complete_step("step:optional-review", "check:review")
        self._complete_step("step:finish", "check:finish")
        return intake

    def _issue_independent_quality(self) -> None:
        issue_receipt(
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

    def _complete_enforced(self):
        intake = self._complete_steps()
        self._hard_receipt("step:finish", "check:release")
        self._issue_independent_quality()
        return intake

    def test_enforced_closure_cannot_skip_later_declared_evidence(self) -> None:
        self._complete_steps()
        evaluation = evaluate_closure(
            self.run_root,
            profile="enforced",
            current_fingerprints=self.current,
        )
        self.assertEqual("incomplete", evaluation.status)
        self.assertIn("obligation:release", evaluation.gaps["missing"])
        self.assertIn("obligation:quality", evaluation.gaps["missing"])

    def test_enforced_closure_rejects_self_review_and_accepts_independent_judgment(self) -> None:
        self._complete_steps()
        self._hard_receipt("step:finish", "check:release")
        issue_receipt(
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
        blocked = evaluate_closure(
            self.run_root,
            profile="enforced",
            current_fingerprints=self.current,
        )
        self.assertEqual("incomplete", blocked.status)
        self.assertIn("obligation:quality", blocked.gaps["uncertain"])
        self._issue_independent_quality()
        closed = evaluate_closure(
            self.run_root,
            profile="enforced",
            current_fingerprints=self.current,
        )
        self.assertEqual("closed", closed.status)

    def test_closure_is_replay_verifiable_and_supersession_invalidates_old_closure(self) -> None:
        intake = self._complete_enforced()
        _evaluation, closure = close_run(
            self.run_root,
            profile="enforced",
            current_fingerprints=self.current,
        )
        self.assertIsNotNone(closure)
        verified = verify_closure(
            self.run_root,
            closure["closure_receipt_id"],
            current_fingerprints=self.current,
        )
        self.assertTrue(verified["ok"], verified)
        _repeated, repeated_closure = close_run(
            self.run_root,
            profile="enforced",
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

    def test_non_enforced_profile_is_rejected(self) -> None:
        with self.assertRaises(ClosureError) as raised:
            evaluate_closure(
                self.run_root,
                profile="functional",
                current_fingerprints=self.current,
            )
        self.assertEqual("closure_profile_unknown", raised.exception.code)

    def test_conditional_obligation_rejects_generic_skip_without_native_terminal(self) -> None:
        conditional = runtime_contract()
        next(
            row
            for row in conditional["obligations"]
            if row["obligation_id"] == "obligation:review"
        )["conditional"] = True
        conditional["route_branch_closure_required"] = True
        conditional["closure_profiles"][0]["route_branch_requirements"] = [
            {
                "native_route_id": "route:analyze",
                "branch_ids": ["fixture-default"],
                "required_obligation_ids": ["obligation:intake"],
                "applicability_rules": [
                    {
                        "obligation_id": "obligation:review",
                        "allowed_disposition": "not_applicable",
                        "verifier_check_id": "check:intake",
                    }
                ],
            }
        ]
        conditional["contract_hash"] = canonical_hash(
            {key: value for key, value in conditional.items() if key != "contract_hash"}
        )
        target = self.target / "conditional"
        decision = select_routes(
            conditional,
            {"function_ids": ["analyze"], "claim_scope": "enforced"},
        )
        claim = claim_run(
            conditional,
            {
                "function_ids": ["analyze"],
                "claim_scope": "enforced",
                "write_targets": ["out"],
                "request": "conditional",
            },
            target,
            decision,
            check_manifest=runtime_check_manifest(conditional),
        )
        self.assertTrue(claim.ok, claim)
        old_root = self.run_root
        self.run_root = claim.run_root
        intake = self._complete_step("step:intake", "check:intake")
        from skillguard_v2.step_runtime import approve_skip, request_skip

        request_skip(self.run_root, "step:optional-review", "not applicable", intake["receipt_id"])
        approve_skip(self.run_root, "step:optional-review", intake["receipt_id"])
        self._complete_step("step:finish", "check:finish")
        with self.assertRaises(ClosureError) as raised:
            evaluate_closure(
                self.run_root,
                profile="enforced",
                current_fingerprints=self.current,
            )
        self.assertEqual("native_terminal_receipt_missing", raised.exception.code)
        self.run_root = old_root


if __name__ == "__main__":
    unittest.main()
