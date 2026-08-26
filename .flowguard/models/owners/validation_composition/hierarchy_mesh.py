"""Parent/child ModelMesh for SkillGuard validation composition."""

from __future__ import annotations

from dataclasses import replace

from flowguard import (
    ChildModelEvidence,
    ChildReattachmentContract,
    HierarchyCoverageItem,
    HierarchyPartitionMap,
    MeshClosureJoin,
    MeshClosureModel,
    MeshClosureTerminal,
    MeshClosureTransition,
    ModelTargetSplitDerivation,
)

from validation_composition_model import MODEL_ID, MODEL_PATH, PARENT_MODEL_ID


PARENT_MODEL_PATH = ".agents/skills/skillguard/.skillguard/flowguard_contract_model.py"
RETIREMENT_MODEL_ID = "skillguard.retired_runtime_rejection_fixtures"
DEPTH_LIFECYCLE_MODEL_ID = "skillguard.execution_depth_rollout.current"

VALIDATION_EVIDENCE_ID = "evidence:model:validation-composition-current"
RETIREMENT_EVIDENCE_ID = "evidence:model:retired-runtime-rejection-fixtures"
DEPTH_EVIDENCE_ID = "evidence:model:execution-depth-lifecycle-current"


def _children() -> tuple[ChildModelEvidence, ...]:
    return (
        ChildModelEvidence(
            MODEL_ID,
            evidence_id=VALIDATION_EVIDENCE_ID,
            risk_boundary="complete inventory, component impact, exact owner receipts, minimal execution, one-way aggregation, and evidence-domain separation",
            functions_owned=(
                "ClassifyPortableArtifacts",
                "FreezeCompleteInventory",
                "CompileContentImpactGraph",
                "DeriveAffectedPlan",
                "ResolveOwnerReceipts",
                "ExecuteStaleOwners",
                "AggregateParentEvidence",
                "HandoffEvidenceDomains",
            ),
            inputs_accepted=("validation_composition_request",),
            outputs_emitted=("validation_parent_projection",),
            state_owned=(
                "artifact_policy_version",
                "inventory_hash",
                "impact_graph_hash",
                "plan_hash",
                "owner_execution_keys",
                "owner_receipt_ids",
                "aggregation_identity",
                "domain_status",
            ),
            side_effects_owned=(),
            functional_areas=("validation_composition",),
            invariants_owned=(
                "runtime_artifact_is_never_portable",
                "inventory_is_complete_and_content_addressed",
                "impact_graph_is_complete_and_acyclic",
                "affected_plan_is_exact_and_frozen",
                "owner_identity_is_semantic_and_persistent",
                "parent_aggregation_is_one_way",
                "evidence_domains_do_not_substitute",
            ),
            contracts_in=("contract:skillguard-parent-validation-request",),
            contracts_out=("contract:validation-composition-result",),
            depends_on=(PARENT_MODEL_ID,),
            evidence_tier="abstract_green",
            validation_evidence=(VALIDATION_EVIDENCE_ID,),
        ),
        ChildModelEvidence(
            DEPTH_LIFECYCLE_MODEL_ID,
            evidence_id=DEPTH_EVIDENCE_ID,
            risk_boundary="universal execution-depth and project-adoption rollout freshness",
            functions_owned=("ReviewExecutionDepthRollout",),
            inputs_accepted=("depth_rollout_change",),
            outputs_emitted=("depth_rollout_freshness_projection",),
            state_owned=("depth_rollout_freshness", "project_adoption_freshness"),
            side_effects_owned=(),
            functional_areas=("execution_depth_rollout",),
            invariants_owned=("depth_evidence_remains_current",),
            contracts_in=("contract:execution-depth-change",),
            contracts_out=("contract:execution-depth-freshness",),
            depends_on=(PARENT_MODEL_ID,),
            evidence_tier="abstract_green",
            validation_evidence=(DEPTH_EVIDENCE_ID,),
        ),
    )


def _reattachments() -> tuple[ChildReattachmentContract, ...]:
    return (
        ChildReattachmentContract(
            MODEL_ID,
            consumed_evidence_id=VALIDATION_EVIDENCE_ID,
            expected_inputs=("validation_composition_request",),
            expected_outputs=("validation_parent_projection",),
            expected_state_owned=(
                "artifact_policy_version",
                "inventory_hash",
                "impact_graph_hash",
                "plan_hash",
                "owner_execution_keys",
                "owner_receipt_ids",
                "aggregation_identity",
                "domain_status",
            ),
            expected_side_effects_owned=(),
            expected_contracts_out=("contract:validation-composition-result",),
            rationale="the existing portable parent consumes only the child's typed result and current evidence id",
        ),
        ChildReattachmentContract(
            DEPTH_LIFECYCLE_MODEL_ID,
            consumed_evidence_id=DEPTH_EVIDENCE_ID,
            expected_inputs=("depth_rollout_change",),
            expected_outputs=("depth_rollout_freshness_projection",),
            expected_state_owned=("depth_rollout_freshness", "project_adoption_freshness"),
            expected_side_effects_owned=(),
            expected_contracts_out=("contract:execution-depth-freshness",),
            rationale="execution-depth rollout freshness stays in its existing child boundary",
        ),
    )


def build_hierarchy_mesh() -> HierarchyPartitionMap:
    coverage_items = (
        HierarchyCoverageItem(
            "portable-semantic-runtime",
            "function",
            PARENT_MODEL_ID,
            ownership="parent",
            description="contract compilation, target run supervision, verifier-owned evidence, and semantic closure remain in the portable parent",
        ),
        HierarchyCoverageItem(
            "validation-composition",
            "function",
            MODEL_ID,
            description="portable classification, complete inventory, content-impact graph, frozen plan, exact owner receipt reuse/execution, aggregation, and domain handoff",
        ),
        HierarchyCoverageItem(
            "execution-depth-rollout",
            "function",
            DEPTH_LIFECYCLE_MODEL_ID,
            description="universal depth and project-adoption rollout freshness",
        ),
    )
    children = _children()
    return HierarchyPartitionMap(
        parent_model_id=PARENT_MODEL_ID,
        coverage_items=coverage_items,
        child_models=children,
        target_split_derivation=ModelTargetSplitDerivation(
            PARENT_MODEL_ID,
            target_child_model_ids=tuple(child.model_id for child in children),
            covered_partition_item_ids=tuple(item.item_id for item in coverage_items),
            state_owner_fields=(
                "artifact_policy_version",
                "inventory_hash",
                "impact_graph_hash",
                "plan_hash",
                "owner_receipt_ids",
                "aggregation_identity",
                "depth_rollout_freshness",
            ),
            side_effect_owner_fields=("none_owned_by_abstract_children",),
            source_model_path=PARENT_MODEL_PATH,
            rationale="the portable parent delegates current validation composition and execution-depth rollout while retired runtime shapes remain rejection fixtures outside the daily mesh",
        ),
        reattachment_contracts=_reattachments(),
        required_evidence_tier="abstract_green",
        closure_model=MeshClosureModel(
            PARENT_MODEL_ID,
            root_entries=("skillguard-maintenance-request",),
            transitions=(
                MeshClosureTransition(
                    "parent-semantic-boundary",
                    consumes=("skillguard-maintenance-request",),
                    emits=("portable-parent-ready",),
                    consumer_model_id=PARENT_MODEL_ID,
                    code_contract_id="contract:portable-semantic-parent",
                    rationale="the parent selects the semantic route before child process evidence is consumed",
                ),
                MeshClosureTransition(
                    "validation-composition-handoff",
                    consumes=("portable-parent-ready",),
                    emits=("validation_parent_projection",),
                    consumer_model_id=MODEL_ID,
                    code_contract_id="contract:validation-composition-result",
                ),
                MeshClosureTransition(
                    "depth-rollout-handoff",
                    consumes=("portable-parent-ready",),
                    emits=("depth_rollout_freshness_projection",),
                    consumer_model_id=DEPTH_LIFECYCLE_MODEL_ID,
                    code_contract_id="contract:execution-depth-freshness",
                ),
            ),
            joins=(
                MeshClosureJoin(
                    "skillguard-parent-mesh-join",
                    required_inputs=(
                        "validation_parent_projection",
                        "depth_rollout_freshness_projection",
                    ),
                    emits=("skillguard-parent-mesh-ready",),
                    rationale="the parent must consume all changed child identities before a mesh claim",
                ),
            ),
            terminals=(
                MeshClosureTerminal(
                    "skillguard-parent-mesh-terminal",
                    consumes=("skillguard-parent-mesh-ready",),
                ),
            ),
            required_outputs=("skillguard-parent-mesh-ready",),
            rationale="whole-parent design closure without expanding child state graphs",
        ),
    )


def build_bad_stale_reattachment_mesh() -> HierarchyPartitionMap:
    mesh = build_hierarchy_mesh()
    first = replace(
        mesh.reattachment_contracts[0],
        consumed_evidence_id="evidence:model:validation-composition-stale",
    )
    return replace(mesh, reattachment_contracts=(first, *mesh.reattachment_contracts[1:]))
