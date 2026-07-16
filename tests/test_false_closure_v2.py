from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _skillguard_v2_runtime_fixture import SCRIPT_ROOT, runtime_check_manifest, runtime_contract  # noqa: F401
from skillguard_v2.closure import ClosureError, close_run, evaluate_closure, load_closure, verify_closure
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


class FalseClosureV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.target = Path(self.temp.name)
        self.contract = runtime_contract()
        decision = select_routes(self.contract, {"function_ids": ["analyze"]})
        claim = claim_run(
            self.contract,
            {"function_ids": ["analyze"], "write_targets": ["out"], "request": "negative closure"},
            self.target,
            decision,
            check_manifest=runtime_check_manifest(self.contract),
        )
        self.run_root = claim.run_root
        self.current = {"implementation": fingerprint_value("v1")}

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _pass(self, step_id: str, check_id: str):
        begin_step(self.run_root, step_id)
        record_step(self.run_root, step_id, {"work": step_id})
        receipt = issue_receipt(
            self.run_root,
            step_id=step_id,
            evidence_class="hard",
            evidence={
                "proof_kind": "fixture_assertion",
                "proof_fingerprint": f"proof:{check_id}",
                "check_id": check_id,
            },
            decision="passed",
            verifier_id="verifier",
            input_fingerprints=self.current,
        )
        record_verification(
            self.run_root,
            step_id,
            "passed",
            receipt["receipt_id"],
            verifier="verifier",
        )
        return receipt

    def _complete_enforced(self):
        rows = [
            self._pass("step:intake", "check:intake"),
            self._pass("step:optional-review", "check:review"),
            self._pass("step:finish", "check:finish"),
        ]
        rows.append(
            issue_receipt(
                self.run_root,
                step_id="step:finish",
                evidence_class="hard",
                evidence={
                    "proof_kind": "fixture_assertion",
                    "proof_fingerprint": "proof:check:release",
                    "check_id": "check:release",
                },
                decision="passed",
                verifier_id="verifier",
                input_fingerprints=self.current,
            )
        )
        rows.append(
            issue_receipt(
                self.run_root,
                step_id="step:finish",
                evidence_class="judged",
                evidence={
                    "rubric_id": "rubric:quality",
                    "rubric_version": "2",
                    "evaluator_id": "independent-reviewer",
                    "input_fingerprint": "artifact:quality",
                    "conclusion": "meets the fixture rubric",
                    "limitations": ["fixture scope"],
                    "self_review": False,
                },
                decision="passed",
                verifier_id="judgment-verifier",
                input_fingerprints=self.current,
            )
        )
        return rows

    def test_optional_runtime_skip_cannot_satisfy_required_functional_obligation(self) -> None:
        condition = self._pass("step:intake", "check:intake")
        request_skip(self.run_root, "step:optional-review", "not useful", condition["receipt_id"])
        approve_skip(self.run_root, "step:optional-review", condition["receipt_id"])
        self._pass("step:finish", "check:finish")
        evaluation, closure = close_run(
            self.run_root,
            profile="enforced",
            current_fingerprints=self.current,
        )
        self.assertEqual("incomplete", evaluation.status)
        self.assertIsNone(closure)
        self.assertIn("step:step:optional-review", evaluation.gaps["skipped"])
        self.assertTrue((self.run_root / "reports" / "closure-enforced.json").is_file())

    def test_source_change_makes_previous_pass_stale(self) -> None:
        self._complete_enforced()
        stale = evaluate_closure(
            self.run_root,
            profile="enforced",
            current_fingerprints={"implementation": fingerprint_value("v2")},
        )
        self.assertEqual("stale", stale.status)
        self.assertEqual(
            {
                "obligation:intake",
                "obligation:review",
                "obligation:finish",
                "obligation:release",
                "obligation:quality",
            },
            set(stale.gaps["stale"]),
        )

    def test_tampered_closure_receipt_and_event_history_are_rejected(self) -> None:
        self._complete_enforced()
        _, closure = close_run(
            self.run_root,
            profile="enforced",
            current_fingerprints=self.current,
        )
        path = self.run_root / "closures" / f"{closure['closure_receipt_id']}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["safe_claim"] = "everything everywhere passed"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(ClosureError) as raised:
            load_closure(self.run_root, closure["closure_receipt_id"])
        self.assertEqual("closure_hash_mismatch", raised.exception.code)

        # A fresh run proves event-chain tampering is returned as an invalid verification result.
        other_target = self.target / "event-tamper"
        decision = select_routes(self.contract, {"function_ids": ["analyze"]})
        other_claim = claim_run(
            self.contract,
            {"function_ids": ["analyze"], "write_targets": ["out"], "request": "event tamper"},
            other_target,
            decision,
            check_manifest=runtime_check_manifest(self.contract),
        )
        old_root = self.run_root
        self.run_root = other_claim.run_root
        self._complete_enforced()
        _, other_closure = close_run(
            self.run_root,
            profile="enforced",
            current_fingerprints=self.current,
        )
        events_path = self.run_root / "events.jsonl"
        rows = events_path.read_text(encoding="utf-8").splitlines()
        event = json.loads(rows[0])
        event["payload"]["claim_scope"] = "forged"
        rows[0] = json.dumps(event, sort_keys=True)
        events_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        invalid = verify_closure(
            self.run_root,
            other_closure["closure_receipt_id"],
            current_fingerprints=self.current,
        )
        self.assertFalse(invalid["ok"])
        self.assertIn("event_hash_mismatch", invalid["findings"])
        self.run_root = old_root

    def test_failed_receipt_and_unfinished_terminal_remain_visible(self) -> None:
        begin_step(self.run_root, "step:intake")
        record_step(self.run_root, "step:intake", {"work": "failed"})
        receipt = issue_receipt(
            self.run_root,
            step_id="step:intake",
            evidence_class="hard",
            evidence={
                "proof_kind": "fixture_assertion",
                "proof_fingerprint": "proof:failed",
                "check_id": "check:intake",
            },
            decision="failed",
            verifier_id="verifier",
            input_fingerprints=self.current,
        )
        record_verification(
            self.run_root,
            "step:intake",
            "failed",
            receipt["receipt_id"],
            verifier="verifier",
        )
        evaluation = evaluate_closure(
            self.run_root,
            profile="enforced",
            current_fingerprints=self.current,
        )
        self.assertIn("obligation:intake", evaluation.gaps["failed"])
        self.assertIn("terminal:terminal:analyzed", evaluation.gaps["blocked"])
        self.assertIn("No full enforced completion claim is safe", evaluation.safe_claim)


if __name__ == "__main__":
    unittest.main()
