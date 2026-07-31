"""TestMesh design for impact-plan-derived immutable owner receipts.

The three child rows below are abstract same-maintenance-unit receipt
partitions, not commands owned by TestMesh. Production TestMesh selects the
concrete execution owners from that unit's compiler-generated impact graph and
only plans or aggregates that unit's already-issued receipts.
"""

from __future__ import annotations

from dataclasses import replace

from flowguard import (
    EVIDENCE_ABSTRACT_GREEN,
    TEST_LAYER_CHILD,
    TEST_SCOPE_ROUTINE,
    TEST_STATUS_NOT_RUN,
    TEST_STATUS_PASSED,
    TestMeshPlan,
    TestPartitionItem,
    TestSuiteEvidence,
    TestTargetSplitDerivation,
)


SOURCE_MODEL_ID = "skillguard.validation_composition.current"
SOURCE_MODEL_PATH = ".flowguard/validation_composition/validation_composition_model.py"
PARENT_MESH_ID = "skillguard-component-impact-regression-mesh"
INVENTORY_REVISION = "skillguard-testmesh-current:component-owner-projections"

IMPACT_SUITE_ID = "owner-impact-compiler"
EXECUTION_SUITE_ID = "owner-receipt-execution"
PROJECTION_SUITE_ID = "owner-external-projections"
CURRENT_SUITE_IDS = (IMPACT_SUITE_ID, EXECUTION_SUITE_ID, PROJECTION_SUITE_ID)

IMPACT_PARTITIONS = (
    "complete-inventory",
    "component-role-and-disposition",
    "graph-health",
    "affected-plan",
    "full-admission",
)
EXECUTION_PARTITIONS = (
    "semantic-execution-key",
    "explicit-producer-check-projections",
    "persistent-owner-receipt",
    "compressed-four-sidecar-replay",
    "cross-run-single-flight",
    "process-tree-cleanup",
    "aggregation-only",
    "evidence-reachability-audit",
    "exact-current-head-authority",
    "active-writer-barrier-race",
    "quarantine-before-purge",
    "same-operation-journal-recovery",
    "release-pin-replay",
)
PROJECTION_PARTITIONS = (
    "component-installation-and-parity",
    "exact-portfolio-impact",
    "router-and-managed-prompt-projection",
    "external-provider-receipt-exclusion",
    "current-only-runtime",
)
ALL_PARTITIONS = IMPACT_PARTITIONS + EXECUTION_PARTITIONS + PROJECTION_PARTITIONS


def _suite(
    suite_id: str,
    partitions: tuple[str, ...],
) -> TestSuiteEvidence:
    return TestSuiteEvidence(
        suite_id,
        command="python .flowguard/validation_composition/run_checks.py --json",
        layer=TEST_LAYER_CHILD,
        result_status=TEST_STATUS_PASSED,
        evidence_tier=EVIDENCE_ABSTRACT_GREEN,
        evidence_current=True,
        test_count=1,
        selected_count=1,
        skipped_count=0,
        exit_code=0,
        result_path=SOURCE_MODEL_PATH,
        result_reused=False,
        release_required=True,
        owns_state=(f"{suite_id}_current",),
        owns_side_effects=(),
        inventory_revision=INVENTORY_REVISION,
        owned_inventory_item_ids=partitions,
        covered_obligation_ids=partitions,
        artifact_version="skillguard-source:component-impact-current",
        verifier_version="flowguard:0.65.1",
    )


def build_test_mesh() -> TestMeshPlan:
    partition_owner = {
        **{partition: IMPACT_SUITE_ID for partition in IMPACT_PARTITIONS},
        **{partition: EXECUTION_SUITE_ID for partition in EXECUTION_PARTITIONS},
        **{partition: PROJECTION_SUITE_ID for partition in PROJECTION_PARTITIONS},
    }
    partition_items = tuple(
        TestPartitionItem(
            partition_id,
            "validation_owner_partition",
            owner_suite_id=partition_owner[partition_id],
            ownership="child",
            description="one current component-impact owner partition with no retired daily success route",
            inventory_revision=INVENTORY_REVISION,
        )
        for partition_id in ALL_PARTITIONS
    )
    suites = (
        _suite(IMPACT_SUITE_ID, IMPACT_PARTITIONS),
        _suite(EXECUTION_SUITE_ID, EXECUTION_PARTITIONS),
        _suite(PROJECTION_SUITE_ID, PROJECTION_PARTITIONS),
    )
    return TestMeshPlan(
        PARENT_MESH_ID,
        partition_items=partition_items,
        child_suites=suites,
        target_split_derivation=TestTargetSplitDerivation(
            SOURCE_MODEL_ID,
            target_suite_ids=CURRENT_SUITE_IDS,
            covered_partition_item_ids=ALL_PARTITIONS,
            state_owner_fields=tuple(f"{suite_id}_current" for suite_id in CURRENT_SUITE_IDS),
            side_effect_owner_fields=("no_shared_validation_side_effects",),
            source_model_path=SOURCE_MODEL_PATH,
            rationale="one maintenance unit's impact graph derives exact current owners; its runner may resolve only the immutable plan's execute partition through same-unit single-flight, while aggregation references only that unit's immutable owner receipts and never substitutes parent-level or foreign-unit evidence for a missing child",
        ),
        required_evidence_tier=EVIDENCE_ABSTRACT_GREEN,
        require_proof_artifacts=False,
        decision_scope=TEST_SCOPE_ROUTINE,
        release_deferred_allowed=False,
        inventory_revision=INVENTORY_REVISION,
        required_inventory_item_ids=(),
        require_complete_inventory=False,
        require_final_receipts=False,
    )


def build_bad_parent_level_reuse_mesh() -> TestMeshPlan:
    plan = build_test_mesh()
    missing = replace(
        plan.child_suites[1],
        result_status=TEST_STATUS_NOT_RUN,
        evidence_current=False,
        exit_code=None,
        result_path="",
        proof_artifact=None,
        run_id="",
        terminal_status=TEST_STATUS_NOT_RUN,
        result_fingerprint="",
        covered_obligation_ids=(),
        not_run_reason="parent aggregation was incorrectly offered as owner execution proof",
    )
    return replace(plan, child_suites=(plan.child_suites[0], missing, plan.child_suites[2]))
