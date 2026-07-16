from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _skillguard_v2_runtime_fixture import SCRIPT_ROOT, runtime_check_manifest, runtime_contract  # noqa: F401
from skillguard_v2.receipts import (
    ReceiptError,
    build_action_witness,
    derive_freshness,
    fingerprint_value,
    issue_receipt,
    load_receipts,
)
from skillguard_v2.route_runtime import select_routes
from skillguard_v2.run_store import claim_run


class EvidenceReceiptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.target = Path(self.temp.name)
        self.contract = runtime_contract()
        decision = select_routes(self.contract, {"function_ids": ["analyze"]})
        claim = claim_run(
            self.contract,
            {"function_ids": ["analyze"], "write_targets": ["out"], "request": "receipt fixture"},
            self.target,
            decision,
            check_manifest=runtime_check_manifest(self.contract),
        )
        self.run_root = claim.run_root
        self.fingerprints = {
            "implementation": fingerprint_value("version 1", policy="raw"),
            "prompt": fingerprint_value("hello   world", policy="semantic"),
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _hard(self, step_id="step:intake", **kwargs):
        return issue_receipt(
            self.run_root,
            step_id=step_id,
            evidence_class="hard",
            evidence={"proof_kind": "command", "proof_fingerprint": "proof:fixture"},
            decision="passed",
            verifier_id="hard-verifier",
            input_fingerprints=self.fingerprints,
            **kwargs,
        )

    def test_evidence_cannot_author_pass_or_current(self) -> None:
        with self.assertRaises(ReceiptError) as raised:
            issue_receipt(
                self.run_root,
                step_id="step:intake",
                evidence_class="hard",
                evidence={
                    "proof_kind": "command",
                    "proof_fingerprint": "proof",
                    "current": True,
                },
                decision="passed",
                verifier_id="hard-verifier",
                input_fingerprints=self.fingerprints,
            )
        self.assertEqual("caller_authored_receipt_authority", raised.exception.code)

    def test_unstored_native_check_hash_cannot_self_award_hard_pass(self) -> None:
        with self.assertRaises(ReceiptError) as raised:
            issue_receipt(
                self.run_root,
                step_id="step:intake",
                evidence_class="hard",
                evidence={
                    "proof_kind": "native_check",
                    "proof_fingerprint": "caller-made-hash",
                    "check_id": "check:intake",
                    "check_record_id": "check-record-forged",
                    "check_record_hash": "forged",
                },
                decision="passed",
                verifier_id="claimed-verifier",
                input_fingerprints=self.fingerprints,
            )
        self.assertEqual(
            "legacy_native_check_evidence_rejected", raised.exception.code
        )

    def test_hard_witnessed_and_judged_classes_remain_distinct(self) -> None:
        hard = self._hard()
        witness_evidence = build_action_witness(
            witness_kind="browser",
            target_id="surface:home",
            input_value={"action": "open"},
            output_value={"surface": "home"},
            executor_id="browser-tool",
        )
        witnessed = issue_receipt(
            self.run_root,
            step_id="step:optional-review",
            evidence_class="witnessed",
            evidence=witness_evidence,
            decision="passed",
            verifier_id="witness-verifier",
            input_fingerprints=self.fingerprints,
        )
        judged = issue_receipt(
            self.run_root,
            step_id="step:finish",
            evidence_class="judged",
            evidence={
                "rubric_id": "rubric:quality",
                "rubric_version": "2",
                "evaluator_id": "reviewer-ai",
                "input_fingerprint": "artifact:1",
                "conclusion": "meets declared threshold",
                "limitations": ["single evaluator"],
                "self_review": True,
                "confidence_boundary": "Self-review is advisory and is not hard proof.",
            },
            decision="passed",
            verifier_id="judgment-verifier",
            input_fingerprints=self.fingerprints,
        )
        self.assertEqual({"hard", "witnessed", "judged"}, {hard["evidence_class"], witnessed["evidence_class"], judged["evidence_class"]})
        self.assertIn("judged authority", judged["claim_boundary"])
        self.assertIn("not an independent pass", witness_evidence["claim_boundary"])

    def test_judged_evidence_must_match_declared_rubric_version(self) -> None:
        with self.assertRaises(ReceiptError) as raised:
            issue_receipt(
                self.run_root,
                step_id="step:finish",
                evidence_class="judged",
                evidence={
                    "rubric_id": "rubric:quality",
                    "rubric_version": "1",
                    "evaluator_id": "reviewer",
                    "input_fingerprint": "artifact:1",
                    "conclusion": "good",
                    "limitations": ["fixture"],
                },
                decision="passed",
                verifier_id="judgment-verifier",
                input_fingerprints=self.fingerprints,
            )
        self.assertEqual("judgment_rubric_version_mismatch", raised.exception.code)

    def test_self_review_requires_explicit_confidence_boundary(self) -> None:
        with self.assertRaises(ReceiptError) as raised:
            issue_receipt(
                self.run_root,
                step_id="step:finish",
                evidence_class="judged",
                evidence={
                    "rubric_id": "rubric:quality",
                    "rubric_version": "1",
                    "evaluator_id": "same-ai",
                    "input_fingerprint": "artifact:1",
                    "conclusion": "good",
                    "limitations": ["self review"],
                    "self_review": True,
                },
                decision="passed",
                verifier_id="judgment-verifier",
                input_fingerprints=self.fingerprints,
            )
        self.assertEqual("self_review_boundary_missing", raised.exception.code)

    def test_freshness_uses_declared_policy_and_ignores_unrelated_changes(self) -> None:
        receipt = self._hard()
        current = {
            "implementation": fingerprint_value("version 1", policy="raw"),
            "prompt": fingerprint_value("hello world", policy="semantic"),
            "unrelated": fingerprint_value("changed", policy="raw"),
        }
        self.assertTrue(derive_freshness(receipt, current).current)
        stale = derive_freshness(
            receipt,
            {
                **current,
                "implementation": fingerprint_value("version 2", policy="raw"),
            },
        )
        self.assertFalse(stale.current)
        self.assertEqual(("implementation",), stale.affected_keys)

    def test_parent_becomes_stale_when_exact_child_is_superseded(self) -> None:
        first_child = self._hard()
        parent = issue_receipt(
            self.run_root,
            step_id="step:finish",
            evidence_class="hard",
            evidence={"proof_kind": "aggregate", "proof_fingerprint": "parent:1"},
            decision="passed",
            verifier_id="parent-verifier",
            input_fingerprints=self.fingerprints,
            consumed_child_receipt_ids=[first_child["receipt_id"]],
        )
        self.assertTrue(derive_freshness(parent, self.fingerprints, receipt_roots=[self.run_root]).current)
        second_child = self._hard()
        self.assertEqual(first_child["receipt_id"], second_child["supersedes_receipt_id"])
        stale = derive_freshness(parent, self.fingerprints, receipt_roots=[self.run_root])
        self.assertFalse(stale.current)
        self.assertIn(
            f"consumed_child_superseded:{first_child['receipt_id']}",
            stale.reasons,
        )

    def test_receipt_tampering_is_detected(self) -> None:
        receipt = self._hard()
        path = self.run_root / "receipts" / f"{receipt['receipt_id']}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["status"] = "failed"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(ReceiptError) as raised:
            load_receipts(self.run_root)
        self.assertEqual("receipt_hash_mismatch", raised.exception.code)


if __name__ == "__main__":
    unittest.main()
