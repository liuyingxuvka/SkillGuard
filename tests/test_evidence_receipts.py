from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests._skillguard_v2_runtime_fixture import SCRIPT_ROOT, runtime_check_manifest, runtime_contract  # noqa: F401
from skillguard_v2.receipts import (
    ReceiptError,
    ReceiptIndex,
    build_action_witness,
    derive_freshness,
    fingerprint_value,
    issue_receipt,
    load_receipts,
    receipt_functional_key,
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
        receipt_index = ReceiptIndex.from_rows((receipt,))
        self.assertTrue(
            derive_freshness(receipt, current, receipt_index=receipt_index).current
        )
        stale = derive_freshness(
            receipt,
            {
                **current,
                "implementation": fingerprint_value("version 2", policy="raw"),
            },
            receipt_index=receipt_index,
        )
        self.assertFalse(stale.current)
        self.assertEqual(("implementation",), stale.affected_keys)

    def test_parent_stays_current_when_same_child_result_is_reissued(self) -> None:
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
        receipt_index = ReceiptIndex.from_roots((self.run_root,))
        self.assertTrue(
            derive_freshness(
                parent,
                self.fingerprints,
                receipt_index=receipt_index,
            ).current
        )
        second_child = self._hard()
        self.assertEqual(first_child["receipt_id"], second_child["supersedes_receipt_id"])
        self.assertEqual(
            receipt_functional_key(first_child), receipt_functional_key(second_child)
        )
        receipt_index = ReceiptIndex.from_roots((self.run_root,))
        stale = derive_freshness(
            parent,
            self.fingerprints,
            receipt_index=receipt_index,
        )
        self.assertTrue(stale.current)

    def test_parent_stales_when_child_input_or_oracle_changes(self) -> None:
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
        issue_receipt(
            self.run_root,
            step_id="step:intake",
            evidence_class="hard",
            evidence={"proof_kind": "command", "proof_fingerprint": "proof:changed"},
            decision="passed",
            verifier_id="different-oracle",
            input_fingerprints={
                **self.fingerprints,
                "implementation": fingerprint_value("version 2", policy="raw"),
            },
        )
        result = derive_freshness(
            parent,
            self.fingerprints,
            receipt_index=ReceiptIndex.from_roots((self.run_root,)),
        )
        self.assertFalse(result.current)
        self.assertIn(
            f"consumed_child_functional_changed:{first_child['receipt_id']}",
            result.reasons,
        )

    def test_functional_receipt_key_ignores_transport_but_keeps_result(self) -> None:
        receipt = self._hard()
        same_result = dict(receipt)
        same_result.update(
            {
                "run_id": "run:other",
                "receipt_id": "receipt-other",
                "receipt_hash": "hash-other",
                "created_at": "2099-01-01T00:00:00Z",
                "issued_sequence": 999,
                "latest_receipt_id": "receipt-other",
                "install_marker": "install-2",
                "release_tag": "release-2",
            }
        )
        same_result["evidence"] = {
            **dict(receipt["evidence"]),
            "created_at": "2099-01-01T00:00:00Z",
        }
        self.assertEqual(
            receipt_functional_key(receipt), receipt_functional_key(same_result)
        )

        changed_result = dict(same_result)
        changed_result["evidence"] = {
            **dict(receipt["evidence"]),
            "proof_fingerprint": "proof:changed",
        }
        self.assertNotEqual(
            receipt_functional_key(receipt), receipt_functional_key(changed_result)
        )
        changed_oracle = dict(same_result)
        changed_oracle["verifier_id"] = "different-oracle"
        self.assertNotEqual(
            receipt_functional_key(receipt), receipt_functional_key(changed_oracle)
        )

    def test_freshness_does_not_reload_receipts_after_index_is_built(self) -> None:
        receipt = self._hard()
        receipt_index = ReceiptIndex.from_roots((self.run_root,))
        current = dict(self.fingerprints)
        from unittest.mock import patch

        with patch("skillguard_v2.receipts.load_receipts", side_effect=AssertionError("reload")):
            result = derive_freshness(
                receipt,
                current,
                receipt_index=receipt_index,
            )
        self.assertTrue(result.current)

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
