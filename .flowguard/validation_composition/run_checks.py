"""Run the SkillGuard component-scoped validation FlowGuard evidence mesh."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
from typing import Any

import flowguard
from flowguard import (
    field_lifecycle_to_code_contracts,
    field_lifecycle_to_model_obligations,
    review_behavior_commitment_ledger,
    review_development_process_flow,
    review_field_lifecycle,
    review_hierarchical_mesh,
    review_test_mesh,
)

from behavior_commitments import build_behavior_commitment_ledger
from development_process import build_bad_out_of_order_process, build_development_process
from field_lifecycle_model import ALL_FIELDS, build_field_lifecycle
from hierarchy_mesh import (
    DEPTH_EVIDENCE_ID,
    RETIREMENT_EVIDENCE_ID,
    VALIDATION_EVIDENCE_ID,
    build_bad_stale_reattachment_mesh,
    build_hierarchy_mesh,
)
from test_mesh_model import (
    ALL_PARTITIONS,
    CURRENT_SUITE_IDS,
    SOURCE_MODEL_ID,
    SOURCE_MODEL_PATH,
    build_bad_parent_level_reuse_mesh,
    build_test_mesh,
)
from validation_composition_model import (
    ALLOWED_FULL_REASONS,
    BLOCKS,
    CLAIM_BOUNDARY,
    CURRENT_PARENT_SCHEMA,
    INVARIANTS,
    MODEL_ID,
    SCENARIOS,
    model_summary,
    run_contract_review,
    run_loop_reviews,
    run_refinement_review,
    run_scenario_review,
)


EVIDENCE_IDS = {
    "scenarios": "evidence:model:validation-composition-scenarios-current",
    "contracts": "evidence:model:validation-composition-function-contracts-current",
    "refinement": "evidence:model:validation-composition-refinement-current",
    "loop_stuck": "evidence:model:validation-composition-loop-stuck-current",
    "progress": "evidence:model:validation-composition-progress-current",
    "behavior_commitments": "evidence:model:validation-composition-bcl-current",
    "model_mesh": VALIDATION_EVIDENCE_ID,
    "test_mesh": "evidence:model:validation-composition-testmesh-current",
    "field_lifecycle": "evidence:model:validation-composition-fields-current",
    "development_process": "evidence:model:validation-composition-process-current",
    "retired_shape_rejection_fixture": RETIREMENT_EVIDENCE_ID,
    "execution_depth_sibling": DEPTH_EVIDENCE_ID,
}

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _repository_manifest_alignment() -> dict[str, Any]:
    """Check the current plan/aggregate-only runtime manifest boundary."""

    manifest_path = REPOSITORY_ROOT / ".agents" / "skills" / "skillguard" / "test-mesh.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    profiles = {
        str(row.get("profile_id", "")): {
            "closure_profile_id": str(row.get("closure_profile_id", "")),
            "full_admission_required": row.get("full_admission_required"),
        }
        for row in manifest.get("profiles", ())
        if isinstance(row, dict)
    }
    expected_profiles = {
        "fast": {"closure_profile_id": "enforced", "full_admission_required": False},
        "focused": {"closure_profile_id": "enforced", "full_admission_required": False},
        "full": {"closure_profile_id": "enforced", "full_admission_required": True},
    }
    checks = {
        "current_manifest_schema": manifest.get("schema_version") == "skillguard.test_mesh_manifest.current",
        "source_model_file_exists": (REPOSITORY_ROOT / SOURCE_MODEL_PATH).is_file(),
        "source_model_id_current": manifest.get("source_model_id") == SOURCE_MODEL_ID,
        "exact_profile_projection": profiles == expected_profiles,
        "no_runtime_commands": "suites" not in manifest and "commands" not in manifest,
        "no_runtime_source_selectors": "source_paths" not in manifest and "reuse_edges" not in manifest,
        "plan_and_aggregation_only_claim": all(
            phrase in str(manifest.get("claim_boundary", "")).lower()
            for phrase in ("plans", "aggregates", "declares no commands")
        ),
    }
    return {
        "ok": all(checks.values()),
        "status": "aligned" if all(checks.values()) else "runtime_manifest_alignment_failed",
        "manifest_path": ".agents/skills/skillguard/test-mesh.json",
        "profiles": profiles,
        "checks": checks,
        "claim_boundary": "This proves only that the repository manifest exposes plan/aggregation selection; owner execution and receipt currentness require separate runtime evidence.",
    }


def _dict(report: Any) -> dict[str, Any]:
    if hasattr(report, "to_dict"):
        return report.to_dict()
    raise TypeError(f"report {type(report).__name__} has no to_dict()")


def run_all() -> tuple[bool, dict[str, Any]]:
    scenario = run_scenario_review()
    contracts = run_contract_review()
    refinement = run_refinement_review()
    loop_good, progress_good, loop_bad = run_loop_reviews()
    bcl = review_behavior_commitment_ledger(build_behavior_commitment_ledger())
    hierarchy = review_hierarchical_mesh(build_hierarchy_mesh())
    hierarchy_bad = review_hierarchical_mesh(build_bad_stale_reattachment_mesh())
    test_mesh = review_test_mesh(build_test_mesh())
    test_mesh_bad = review_test_mesh(build_bad_parent_level_reuse_mesh())
    field_lifecycle = review_field_lifecycle(build_field_lifecycle())
    process = review_development_process_flow(build_development_process())
    process_bad = review_development_process_flow(build_bad_out_of_order_process())
    manifest_alignment = _repository_manifest_alignment()

    field_obligations = field_lifecycle_to_model_obligations(field_lifecycle)
    field_contracts = field_lifecycle_to_code_contracts(field_lifecycle)
    known_bad_scenario_ids = {
        scenario_row.name
        for scenario_row in SCENARIOS
        if scenario_row.expected.expected_status == "violation"
    }
    required_scope_known_bads = {
        "bad-whole-inventory-in-owner-key",
        "bad-broad-skill-subtree-in-owner-key",
        "bad-unmapped-component-falls-back-full",
        "bad-ambiguous-component-role",
        "bad-subtree-override-misses-new-descendant",
        "bad-duplicate-owner",
        "bad-owner-dependency-cycle",
        "bad-validation-plan-not-frozen",
        "bad-unrelated-sibling-executed",
        "bad-parent-only-reruns-owner",
        "bad-consumer-covers-reruns-owner",
        "bad-test-only-triggers-install",
        "bad-runtime-change-refreshes-router",
        "bad-runtime-change-invalidates-unrelated-target",
        "bad-installation-implies-full",
        "bad-uncertainty-admits-full",
    }
    required_receipt_known_bads = {
        "bad-invalid-sidecar-reused",
        "bad-validation-receipt-only-in-temp-copy",
        "bad-run-id-in-owner-key",
        "bad-parent-hash-in-owner-key",
        "bad-failed-check-attempt-reused",
        "bad-post-launch-persistence-failure-reports-zero-execution",
        "bad-parent-rewrites-child-receipt",
        "bad-invalid-parent-consumer-reruns-owner",
        "bad-resume-used-as-readonly-audit",
        "bad-old-wire-auto-accepted",
        "bad-stale-evidence-metadata-refreshed",
        "bad-noncurrent-project-manifest-read-for-rewrite",
    }
    required_lifecycle_known_bads = {
        "bad-full-started-before-source-fixpoint",
        "bad-full-has-two-execution-owners",
        "bad-timeout-cleanup-unconfirmed",
        "bad-scheduled-task-resumes-mutable-full",
        "bad-receipt-output-in-freshness-watch",
        "bad-openspec-task-checkbox-in-test-identity",
        "bad-ordinary-report-written-into-source",
        "bad-installed-projection-recompiled-as-source",
        "bad-source-overlaps-evidence",
        "bad-target-outside-evidence-root",
        "bad-portable-ref-root-drift",
        "bad-skill-runtime-compatibility-branch",
        "bad-unapproved-software-compatibility",
    }
    current_mesh = build_test_mesh()
    positive = {
        "scenario_review": scenario.ok,
        "function_contract_review": contracts.ok,
        "refinement_review": refinement.ok,
        "loop_stuck_review": loop_good.ok,
        "progress_review": progress_good.ok,
        "behavior_commitment_review": bcl.ok,
        "hierarchy_mesh_review": hierarchy.ok,
        "test_mesh_review": test_mesh.ok,
        "field_lifecycle_review": field_lifecycle.ok,
        "development_process_review": process.ok,
        "field_obligation_projection_complete": len(field_obligations) == len(ALL_FIELDS),
        "field_contract_projection_complete": len(field_contracts) == len(ALL_FIELDS),
        "function_blocks_use_input_state_set_contract": all("x" in block.__doc__ and "Set(" in block.__doc__ for block in BLOCKS),
        "eight_component_scoped_function_blocks": len(BLOCKS) == 8,
        "current_test_mesh_has_exact_owner_suites": tuple(suite.suite_id for suite in current_mesh.child_suites) == CURRENT_SUITE_IDS,
        "current_test_mesh_parent_executes_no_owner_commands": all(
            suite.result_reused and suite.command.startswith("owner-receipt-ref:")
            for suite in current_mesh.child_suites
        ),
        "current_test_mesh_has_no_retired_success_suite": all("v1" not in suite_id.lower() and "legacy" not in suite_id.lower() for suite_id in CURRENT_SUITE_IDS),
        "current_parent_schema_has_no_generation_label": "v1" not in CURRENT_PARENT_SCHEMA.lower() and "v2" not in CURRENT_PARENT_SCHEMA.lower(),
        "full_reason_allowlist_excludes_uncertainty_and_installation": "uncertainty" not in ALLOWED_FULL_REASONS and "installation" not in ALLOWED_FULL_REASONS,
    }
    expected_bad = {
        "nonterminating_progress_only_loop_rejected": not loop_bad.ok,
        "stale_child_reattachment_rejected": not hierarchy_bad.ok,
        "parent_level_reuse_cannot_hide_missing_owner": not test_mesh_bad.ok,
        "unknown_process_dependency_rejected": not process_bad.ok,
        "component_scope_known_bads_complete": required_scope_known_bads.issubset(known_bad_scenario_ids),
        "receipt_identity_known_bads_complete": required_receipt_known_bads.issubset(known_bad_scenario_ids),
        "execution_lifecycle_known_bads_complete": required_lifecycle_known_bads.issubset(known_bad_scenario_ids),
    }
    ok = all(positive.values()) and all(expected_bad.values())
    if not manifest_alignment["ok"]:
        ok = False
    skipped_checks = []

    payload = {
        "schema_version": "skillguard.validation_composition_flowguard_report.current",
        "status": "pass" if ok else "fail",
        "flowguard": {
            "schema_version": str(flowguard.SCHEMA_VERSION),
            "package_version": importlib.metadata.version("flowguard"),
        },
        "model": model_summary(),
        "ownership": {
            "portable_parent_model_id": "skillguard.executable_contract_runtime.current",
            "validation_child_model_id": MODEL_ID,
            "retired_shape_boundary": "negative-fixtures-only",
            "execution_depth_sibling_model_id": "skillguard.execution_depth_rollout.current",
            "duplicate_boundary_risk": "none_after_component_owner_partition",
            "current_testmesh_owner_suites": list(CURRENT_SUITE_IDS),
            "required_partition_ids": list(ALL_PARTITIONS),
        },
        "repository_manifest_alignment": manifest_alignment,
        "evidence_ids": EVIDENCE_IDS,
        "positive_gate_status": positive,
        "known_bad_gate_status": expected_bad,
        "known_bad_scenario_ids": sorted(known_bad_scenario_ids),
        "reports": {
            "scenario_review": _dict(scenario),
            "function_contract_review": _dict(contracts),
            "refinement_review": _dict(refinement),
            "loop_stuck_review": _dict(loop_good),
            "progress_review": _dict(progress_good),
            "behavior_commitment_review": _dict(bcl),
            "hierarchy_mesh_review": _dict(hierarchy),
            "test_mesh_review": _dict(test_mesh),
            "field_lifecycle_review": _dict(field_lifecycle),
            "development_process_review": _dict(process),
        },
        "expected_bad_reports": {
            "nonterminating_loop": _dict(loop_bad),
            "stale_reattachment": _dict(hierarchy_bad),
            "parent_level_reuse": _dict(test_mesh_bad),
            "out_of_order_process": _dict(process_bad),
        },
        "skipped_checks": skipped_checks,
        "residual_risk": [
            "production compiler, same-unit owner receipt, TestMesh, consumer distribution, Portfolio summary, private author router, and external-provider exclusion require focused implementation regressions",
            "manifest alignment does not prove that every selected owner has a current independently replayable receipt",
        ],
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return ok, payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run all component-scoped validation FlowGuard models and expected bad variants.")
    parser.add_argument("--json", action="store_true", help="Emit one machine-readable JSON payload.")
    args = parser.parse_args(argv)
    ok, payload = run_all()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"status: {payload['status']}")
        print(f"model_id: {MODEL_ID}")
        print(f"positive_gates: {sum(payload['positive_gate_status'].values())}/{len(payload['positive_gate_status'])}")
        print(f"known_bad_gates: {sum(payload['known_bad_gate_status'].values())}/{len(payload['known_bad_gate_status'])}")
        print(f"claim_boundary: {CLAIM_BOUNDARY}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
