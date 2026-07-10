from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / ".flowguard" / "development_process_flow" / "skillguard_executable_contract_model.py"


def load_model():
    spec = importlib.util.spec_from_file_location("skillguard_executable_contract_model", MODEL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load model: {MODEL_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ExecutableContractModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.model = load_model()

    def test_good_scenario_review_passes(self) -> None:
        report = self.model.run_scenario_review()
        self.assertTrue(report.ok, report.format_text())

    def test_known_bad_scenarios_are_required(self) -> None:
        scenario_names = {scenario.name for scenario in self.model.SCENARIOS}
        expected = {
            "missing_model_blocks",
            "untyped_route_blocks",
            "unknown_packet_field_blocks",
            "guard_change_same_run_blocks",
            "unclaimed_run_blocks",
            "conflicting_writer_blocks",
            "stale_failed_writer_lock_blocks_progress",
            "caller_authored_pass_blocks",
            "required_skip_blocks",
            "stale_artifact_blocks_closure",
            "resume_from_chat_memory_blocks",
            "no_progress_loop_blocks",
            "over_bound_loop_blocks",
            "stale_child_blocks_parent",
            "hidden_failure_blocks",
            "v1_alternate_success_blocks",
            "non_monotonic_profile_blocks",
            "stale_prior_graduate_blocks",
            "undeclared_guard_change_blocks_portfolio",
            "old_green_after_guard_change_blocks_portfolio",
            "broad_or_changed_identity_reuse_blocks_portfolio",
            "portfolio_receipt_without_prior_evidence_blocks",
            "partial_capability_coverage_blocks_portfolio",
            "concurrent_portfolio_writer_blocks",
        }
        self.assertTrue(expected.issubset(scenario_names))

    def test_behavior_commitment_ledger_passes(self) -> None:
        report = self.model.run_governance_reviews()["behavior_commitment_ledger"]
        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(6, len(self.model.build_behavior_commitment_ledger().commitments))

    def test_primary_path_authority_passes(self) -> None:
        report = self.model.run_governance_reviews()["primary_path_authority"]
        self.assertTrue(report.ok, report.format_text())
        plan = self.model.build_primary_path_authority_plan()
        self.assertTrue(all(not row.returns_success_after_primary_failure for row in plan.fallback_candidates))

    def test_contract_exhaustion_covers_required_families(self) -> None:
        report = self.model.run_governance_reviews()["contract_exhaustion"]
        self.assertTrue(report.ok, report.format_text())
        case_ids = {case.case_id for case in report.generated_cases}
        expected = {
            "case:single:missing-terminal",
            "case:multi:duplicate-owner",
            "case:composed:dangling-handoff",
            "case:conditional:skip-without-condition",
            "case:recovery:chat-memory",
            "case:skip:required-step",
            "case:blocked:missing-unblock-condition",
            "case:stale:old-child-receipt",
            "case:concurrency:double-claim",
            "case:concurrency:stale-lock-not-recovered",
            "case:packet:unknown-field",
            "case:guard:changed-same-run",
            "case:loop:no-delta",
            "case:loop:over-bound",
            "case:portfolio:prior-stale",
            "case:portfolio:guard-change-unregistered",
            "case:portfolio:old-green-preserved",
            "case:portfolio:broad-reuse",
            "case:portfolio:affected-reuse",
            "case:portfolio:identity-changed-reuse",
            "case:portfolio:inexact-parent-receipt",
            "case:portfolio:capability-gap",
            "case:portfolio:concurrent-writer",
        }
        self.assertTrue(expected.issubset(case_ids))

    def test_model_test_alignment_passes(self) -> None:
        report = self.model.run_governance_reviews()["model_test_alignment"]
        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(17, len(self.model.build_model_test_alignment_plan().obligations))

    def test_self_host_functions_have_distinct_routes_and_terminals(self) -> None:
        export = self.model.export_contract_model()
        functions = {row["function_id"]: row for row in export["functions"]}
        required = {
            "static_audit",
            "compile_contract",
            "supervise_run",
            "deep_audit",
            "global_router_handoff",
            "audit_provenance",
        }
        self.assertTrue(required.issubset(functions))
        routes = {row["route_id"]: row for row in export["routes"]}
        for function_id in required:
            for route_id in functions[function_id]["route_ids"]:
                self.assertIn(route_id, routes)
                self.assertTrue(routes[route_id]["success_terminal_step_id"])

    def test_test_mesh_passes_and_owns_generated_cases(self) -> None:
        reports = self.model.run_governance_reviews()
        mesh = reports["test_mesh"]
        self.assertTrue(mesh.ok, mesh.format_text())
        cem = reports["contract_exhaustion"]
        plan = self.model.build_test_mesh_plan(tuple(case.case_id for case in cem.generated_cases))
        self.assertEqual(set(plan.required_leaf_cell_ids), set(plan.child_suites[3].owned_leaf_cell_ids))

    def test_main_passes(self) -> None:
        self.assertEqual(0, self.model.main())


if __name__ == "__main__":
    unittest.main()
