"""TestMesh design for impact-plan-derived immutable owner receipts.

The three child rows below are abstract same-maintenance-unit receipt
partitions, not commands owned by TestMesh. Production TestMesh selects the
concrete execution owners from that unit's compiler-generated impact graph and
only plans or aggregates that unit's already-issued receipts.
"""

from __future__ import annotations

from dataclasses import replace
import hashlib

from flowguard import (
    EVIDENCE_ABSTRACT_GREEN,
    PROOF_ARTIFACT_SCOPE_EXTERNAL_CONTRACT,
    ProofArtifactRef,
    TEST_LAYER_CHILD,
    TEST_SCOPE_RELEASE,
    TEST_STATUS_NOT_RUN,
    TEST_STATUS_PASSED,
    TestMeshPlan,
    TestPartitionItem,
    TestResultReuseTicket,
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


def _hash(label: str) -> str:
    return "sha256:" + hashlib.sha256(label.encode("utf-8")).hexdigest()


def _proof(suite_id: str, partitions: tuple[str, ...], result_path: str, result_hash: str) -> ProofArtifactRef:
    return ProofArtifactRef(
        f"proof:{suite_id}:current",
        producer_route="test_mesh_maintenance",
        command=f"skillguard-testmesh-owner:{suite_id}",
        result_path=result_path,
        result_status=TEST_STATUS_PASSED,
        exit_code=0,
        artifact_fingerprints={result_path: result_hash},
        covered_obligation_ids=partitions,
        assertion_scope=PROOF_ARTIFACT_SCOPE_EXTERNAL_CONTRACT,
        current=True,
        route_evidence_current=True,
    )


def _suite(
    suite_id: str,
    partitions: tuple[str, ...],
    command: str,
    *,
    reused: bool,
) -> TestSuiteEvidence:
    result_path = f"work/testmesh/{suite_id}/result.json"
    result_hash = _hash(f"{suite_id}:result")
    ticket = None
    if reused:
        ticket = TestResultReuseTicket(
            suite_id,
            previous_evidence_id=f"owner-receipt:{suite_id}:current",
            reason="the current terminal-success owner receipt matches the exact declaration, input projection, dependencies, toolchain, environment, and evidence domain",
            same_output_proof_id=f"proof:same-owner-receipt:{suite_id}",
            command_fingerprint=_hash(f"{suite_id}:declaration"),
            test_source_fingerprint=_hash(f"{suite_id}:input-projection"),
            tested_artifact_fingerprint=_hash(f"{suite_id}:tested-artifact"),
            dependency_fingerprints={
                "impact_graph": _hash("impact-graph"),
                "impact_policy": _hash("impact-policy"),
                "toolchain": _hash("flowguard-0.55.0"),
            },
            environment_fingerprint=_hash("python-environment"),
            result_fingerprint=result_hash,
            covered_obligation_ids=partitions,
        )
    return TestSuiteEvidence(
        suite_id,
        command=command,
        layer=TEST_LAYER_CHILD,
        result_status=TEST_STATUS_PASSED,
        evidence_tier=EVIDENCE_ABSTRACT_GREEN,
        evidence_current=True,
        test_count=1,
        selected_count=1,
        skipped_count=0,
        exit_code=0,
        result_path=result_path,
        proof_artifact=_proof(suite_id, partitions, result_path, result_hash),
        result_reused=reused,
        reuse_ticket=ticket,
        release_required=True,
        owns_state=(f"{suite_id}_current",),
        owns_side_effects=(),
        inventory_revision=INVENTORY_REVISION,
        owned_inventory_item_ids=partitions,
        run_id=f"run:current:{suite_id}",
        terminal_status=TEST_STATUS_PASSED,
        result_fingerprint=result_hash,
        covered_obligation_ids=partitions,
        artifact_version="skillguard-source:component-impact-current",
        verifier_version="flowguard:0.55.0",
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
        _suite(
            IMPACT_SUITE_ID,
            IMPACT_PARTITIONS,
            "owner-receipt-ref:owner-impact-compiler",
            reused=True,
        ),
        _suite(
            EXECUTION_SUITE_ID,
            EXECUTION_PARTITIONS,
            "owner-receipt-ref:owner-receipt-execution",
            reused=True,
        ),
        _suite(
            PROJECTION_SUITE_ID,
            PROJECTION_PARTITIONS,
            "owner-receipt-ref:owner-external-projections",
            reused=True,
        ),
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
        require_proof_artifacts=True,
        decision_scope=TEST_SCOPE_RELEASE,
        release_deferred_allowed=False,
        inventory_revision=INVENTORY_REVISION,
        required_inventory_item_ids=ALL_PARTITIONS,
        require_complete_inventory=True,
        require_final_receipts=True,
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
