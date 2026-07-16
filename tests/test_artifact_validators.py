from __future__ import annotations

import json
import struct
import tempfile
import unittest
from pathlib import Path

from _skillguard_v2_runtime_fixture import SCRIPT_ROOT, runtime_check_manifest, runtime_contract  # noqa: F401
from skillguard_v2.artifact_validators import (
    ArtifactValidationError,
    hard_evidence_from_artifact,
    load_artifact_record,
    validate_artifact,
)
from skillguard_v2.receipts import fingerprint_value, issue_receipt
from skillguard_v2.route_runtime import select_routes
from skillguard_v2.run_store import claim_run


class ArtifactValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.target = Path(self.temp.name)
        self.contract = runtime_contract()
        decision = select_routes(self.contract, {"function_ids": ["analyze"]})
        claim = claim_run(
            self.contract,
            {"function_ids": ["analyze"], "write_targets": ["outputs"], "request": "artifact fixture"},
            self.target,
            decision,
            check_manifest=runtime_check_manifest(self.contract),
        )
        self.run_root = claim.run_root
        (self.target / "outputs").mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_json_structure_and_producer_are_validated(self) -> None:
        (self.target / "outputs" / "result.json").write_text('{"ok": true}', encoding="utf-8")
        declaration = {
            "artifact_id": "artifact:result",
            "kind": "json",
            "producer_step_id": "step:intake",
            "path_template": "outputs/result.json",
            "required_keys": ["ok"],
        }
        passed = validate_artifact(
            self.run_root,
            self.target,
            declaration,
            producer_step_id="step:intake",
        )
        self.assertEqual("passed", passed["status"])
        loaded = load_artifact_record(self.run_root, passed["artifact_record_id"])
        evidence = hard_evidence_from_artifact(loaded)
        receipt = issue_receipt(
            self.run_root,
            step_id="step:intake",
            evidence_class="hard",
            evidence=evidence,
            decision="passed",
            verifier_id="artifact-verifier",
            input_fingerprints={"artifact": fingerprint_value(passed["fingerprint"])},
            artifact_record_ids=[passed["artifact_record_id"]],
        )
        self.assertEqual([passed["artifact_record_id"]], receipt["artifact_record_ids"])
        failed = validate_artifact(
            self.run_root,
            self.target,
            declaration,
            producer_step_id="step:finish",
        )
        self.assertEqual("failed", failed["status"])
        self.assertIn("producer_step", {row["check_id"] for row in failed["checks"] if row["status"] == "failed"})

    def test_screenshot_requires_matching_surface_state_and_interaction_witness(self) -> None:
        png = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 800, 600)
        (self.target / "outputs" / "screen.png").write_bytes(png)
        declaration = {
            "artifact_id": "artifact:screenshot",
            "kind": "screenshot",
            "producer_step_id": "step:finish",
            "path_template": "outputs/screen.png",
            "minimum_width": 640,
            "minimum_height": 480,
            "surface_id": "surface:settings",
            "state_id": "state:open",
        }
        passed = validate_artifact(
            self.run_root,
            self.target,
            declaration,
            producer_step_id="step:finish",
            witness={
                "surface_id": "surface:settings",
                "state_id": "state:open",
                "interaction_receipt_id": "receipt:interaction",
            },
        )
        self.assertEqual("passed", passed["status"])
        wrong = validate_artifact(
            self.run_root,
            self.target,
            declaration,
            producer_step_id="step:finish",
            witness={
                "surface_id": "surface:other",
                "state_id": "state:open",
                "interaction_receipt_id": "receipt:interaction",
            },
        )
        self.assertEqual("failed", wrong["status"])
        self.assertIn("screenshot_surface", {row["check_id"] for row in wrong["checks"] if row["status"] == "failed"})
        with self.assertRaises(ArtifactValidationError) as raised:
            hard_evidence_from_artifact(wrong)
        self.assertEqual("artifact_cannot_be_hard_evidence", raised.exception.code)

    def test_document_directory_and_ui_witness_have_native_validators(self) -> None:
        (self.target / "outputs" / "report.pdf").write_bytes(b"%PDF-1.4\nfixture")
        (self.target / "outputs" / "receipt.txt").write_text("fixture", encoding="utf-8")
        document = validate_artifact(
            self.run_root,
            self.target,
            {
                "artifact_id": "artifact:document",
                "kind": "document",
                "producer_step_id": "step:finish",
                "path_template": "outputs/report.pdf",
            },
            producer_step_id="step:finish",
        )
        self.assertEqual("passed", document["status"])
        directory = validate_artifact(
            self.run_root,
            self.target,
            {
                "artifact_id": "artifact:directory",
                "kind": "directory",
                "producer_step_id": "step:finish",
                "path_template": "outputs",
                "minimum_files": 2,
            },
            producer_step_id="step:finish",
        )
        self.assertEqual("passed", directory["status"])
        witness = validate_artifact(
            self.run_root,
            self.target,
            {
                "artifact_id": "artifact:ui-launch",
                "kind": "ui_launch",
                "producer_step_id": "step:finish",
            },
            producer_step_id="step:finish",
            witness={
                "witness_id": "witness:launch",
                "target_id": "app:fixture",
                "input_fingerprint": "input:1",
                "output_fingerprint": "output:1",
            },
        )
        self.assertEqual("passed", witness["status"])

    def test_artifact_path_cannot_escape_target(self) -> None:
        with self.assertRaises(ArtifactValidationError) as raised:
            validate_artifact(
                self.run_root,
                self.target,
                {
                    "artifact_id": "artifact:escape",
                    "kind": "file",
                    "producer_step_id": "step:intake",
                    "path_template": "../outside.txt",
                },
                producer_step_id="step:intake",
            )
        self.assertEqual("artifact_path_outside_target", raised.exception.code)


if __name__ == "__main__":
    unittest.main()
