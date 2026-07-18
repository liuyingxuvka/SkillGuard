from __future__ import annotations

import importlib.util
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = (
    ROOT
    / ".flowguard"
    / "development_process_flow"
    / "current_runtime_authority_model.py"
)


def load_model():
    spec = importlib.util.spec_from_file_location(
        "current_runtime_authority_model",
        MODEL_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load model: {MODEL_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CurrentRuntimeAuthorityModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.model = load_model()

    def test_scenario_review_covers_direct_current_and_known_bad_paths(self) -> None:
        report = self.model.run_scenario_review()
        self.assertTrue(report.ok, report.format_text())
        names = {scenario.name for scenario in self.model.SCENARIOS}
        self.assertTrue(
            {
                "good_current_authority",
                "incomplete_direct_replacement_remains_blocked",
                "old_pair_cannot_pass",
                "retirement_receipt_residual_blocks",
                "conversion_tool_residual_blocks",
                "rejection_fixture_change_is_nonfunctional",
                "rejection_fixture_cannot_admit_full",
                "former_command_is_rejected",
                "former_command_handler_invocation_blocks",
                "converter_presence_blocks",
                "direct_replacement_can_activate",
                "partial_replacement_cannot_activate",
                "independent_consumer_builds_may_differ",
                "consumer_skillguard_projection_blocks",
                "consumer_author_maintenance_section_blocks",
                "authority_claim_overreach_blocks",
            }.issubset(names)
        )

    def test_residual_detection_is_exact_and_preserves_current_runs(self) -> None:
        residuals = self.model.exact_former_runtime_residuals(
            (
                ".skillguard/work-contract.json",
                ".SKILLGUARD/V1-RETIREMENT-COMPLETION-RECEIPT.JSON",
                ".skillguard/v1r/old.json",
                ".skillguard/runs/current/run.json",
            ),
            (
                (".skillguard/runs/old.json", "skillguard.run_record.v1"),
                (".skillguard/runs/stable.json", "skillguard.depth_profile.v1"),
            ),
        )
        self.assertIn(".skillguard/work-contract.json", residuals)
        self.assertIn(
            ".skillguard/v1-retirement-completion-receipt.json",
            residuals,
        )
        self.assertIn(".skillguard/v1r/old.json", residuals)
        self.assertIn(".skillguard/runs/old.json", residuals)
        self.assertNotIn(".skillguard/runs/current/run.json", residuals)
        self.assertNotIn(".skillguard/runs/stable.json", residuals)

    def test_model_exposes_no_conversion_success_route(self) -> None:
        summary = self.model.model_summary()
        self.assertEqual(
            ["blocked", "current"],
            summary["authority_decisions"],
        )
        self.assertEqual(
            "rejection_fixture_only",
            summary["former_shape_disposition"],
        )
        self.assertEqual(
            "direct_current_maintenance_only",
            summary["replacement_mode"],
        )
        self.assertEqual(
            ["blocked", "clean"],
            summary["consumer_distribution_decisions"],
        )
        self.assertNotIn("migration", json.dumps(summary).casefold())
        self.assertNotIn("renew", json.dumps(summary).casefold())

    def test_json_cli_payload_is_machine_readable_and_bounded(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = self.model.main(["--json"])
        payload = json.loads(output.getvalue())
        self.assertEqual(0, exit_code)
        self.assertEqual("pass", payload["status"])
        self.assertTrue(payload["scenario_review"]["ok"])
        self.assertIn("does not edit files", payload["claim_boundary"])


if __name__ == "__main__":
    unittest.main()
