from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _skillguard_v2_runtime_fixture import (  # noqa: F401
    ROOT,
    SCRIPT_ROOT,
    runtime_check_manifest,
    runtime_contract,
)
from skillguard_v2.artifact_validators import validate_artifact
from skillguard_v2.closure import evaluate_closure
from skillguard_v2.receipts import ReceiptError, fingerprint_value, issue_receipt
from skillguard_v2.route_runtime import select_routes
from skillguard_v2.run_store import claim_run
from skillguard_v2.step_runtime import (
    StepRuntimeError,
    begin_step,
    record_loop_reentry,
    record_step,
    record_verification,
    replay_run,
    request_skip,
    resume_run,
)


class SelfHostFailureMatrixV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        path = ROOT / ".agents" / "skills" / "skillguard" / "fixtures" / "v2_self_host_failure_matrix" / "fixture-manifest.json"
        cls.manifest = json.loads(path.read_text(encoding="utf-8"))

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.target = Path(self.temp.name)
        self.contract = runtime_contract()
        self.check_manifest = runtime_check_manifest(self.contract)
        self.decision = select_routes(self.contract, {"function_ids": ["analyze"]})
        self.request = {"function_ids": ["analyze"], "write_targets": ["out"], "request": "matrix"}
        self.claim = claim_run(
            self.contract,
            self.request,
            self.target,
            self.decision,
            check_manifest=self.check_manifest,
        )
        self.run_root = self.claim.run_root
        self.current = {"implementation": fingerprint_value("v1")}

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _complete(self, step_id: str, check_id: str, *, artifact_record_ids=()):
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
            verifier_id="fixture-verifier",
            input_fingerprints=self.current,
            artifact_record_ids=artifact_record_ids,
        )
        record_verification(
            self.run_root,
            step_id,
            "passed",
            receipt["receipt_id"],
            verifier="fixture-verifier",
        )
        return receipt

    def test_manifest_declares_the_complete_failure_matrix(self) -> None:
        self.assertEqual(
            {
                "false-pass",
                "illegal-required-skip",
                "stale-artifact",
                "unrelated-check",
                "forged-evidence",
                "crash-replay",
                "context-loss",
                "concurrent-writer",
                "no-progress-loop",
            },
            {row["case_id"] for row in self.manifest["cases"]},
        )

    def test_false_pass_and_illegal_required_skip_block(self) -> None:
        begin_step(self.run_root, "step:intake")
        with self.assertRaises(StepRuntimeError) as false_pass:
            record_step(self.run_root, "step:intake", {"passed": True})
        self.assertEqual("caller_authored_authoritative_status", false_pass.exception.code)
        other_target = self.target / "skip"
        other = claim_run(
            self.contract,
            {**self.request, "request": "skip"},
            other_target,
            self.decision,
            check_manifest=self.check_manifest,
        )
        with self.assertRaises(StepRuntimeError) as illegal_skip:
            request_skip(other.run_root, "step:intake", "skip", "receipt:condition")
        self.assertEqual("required_step_cannot_skip", illegal_skip.exception.code)

    def test_stale_artifact_and_unrelated_check_cannot_close(self) -> None:
        output = self.target / "out" / "result.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('{"ok": true}', encoding="utf-8")
        artifact = validate_artifact(
            self.run_root,
            self.target,
            {
                "artifact_id": "artifact:result",
                "kind": "json",
                "producer_step_id": "step:intake",
                "path_template": "out/result.json",
                "required_keys": ["ok"],
            },
            producer_step_id="step:intake",
        )
        self._complete("step:intake", "check:intake", artifact_record_ids=[artifact["artifact_record_id"]])
        self._complete("step:optional-review", "check:review")
        self._complete("step:finish", "check:finish")
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
            verifier_id="fixture-verifier",
            input_fingerprints=self.current,
        )
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
        output.write_text('{"ok": false}', encoding="utf-8")
        stale = evaluate_closure(self.run_root, profile="enforced", current_fingerprints=self.current)
        self.assertEqual("stale", stale.status)

        unrelated_target = self.target / "unrelated"
        unrelated = claim_run(
            self.contract,
            {**self.request, "request": "unrelated"},
            unrelated_target,
            self.decision,
            check_manifest=self.check_manifest,
        )
        old_root = self.run_root
        self.run_root = unrelated.run_root
        self._complete("step:intake", "check:not-intake")
        incomplete = evaluate_closure(self.run_root, profile="enforced", current_fingerprints=self.current)
        self.assertIn("obligation:intake", incomplete.gaps["missing"])
        self.run_root = old_root

    def test_forged_native_check_record_is_rejected(self) -> None:
        with self.assertRaises(ReceiptError) as forged:
            issue_receipt(
                self.run_root,
                step_id="step:intake",
                evidence_class="hard",
                evidence={
                    "proof_kind": "native_check",
                    "proof_fingerprint": "forged",
                    "check_id": "check:intake",
                    "check_record_id": "check-record-forged",
                    "check_record_hash": "forged",
                },
                decision="passed",
                verifier_id="forged-verifier",
                input_fingerprints=self.current,
            )
        self.assertEqual("legacy_native_check_evidence_rejected", forged.exception.code)

    def test_crash_replay_and_context_loss_resume_from_events(self) -> None:
        begin_step(self.run_root, "step:intake")
        record_step(self.run_root, "step:intake", {"work": "durable"})
        before = replay_run(self.run_root).to_dict()
        after = resume_run(Path(str(self.run_root))).to_dict()
        self.assertEqual(before, after)
        self.assertEqual("evidence_submitted", after["step_statuses"]["step:intake"])

    def test_concurrent_writer_and_no_progress_loop_block(self) -> None:
        conflict = claim_run(
            self.contract,
            {**self.request, "request": "other"},
            self.target,
            self.decision,
            check_manifest=self.check_manifest,
        )
        self.assertFalse(conflict.ok)
        self.assertEqual({"conflicting_writer_claim"}, {row.code for row in conflict.findings})
        record_loop_reentry(self.run_root, "route:analyze", "receipt:1")
        with self.assertRaises(StepRuntimeError) as no_progress:
            record_loop_reentry(self.run_root, "route:analyze", "receipt:1")
        self.assertEqual("loop_progress_unchanged", no_progress.exception.code)


if __name__ == "__main__":
    unittest.main()
