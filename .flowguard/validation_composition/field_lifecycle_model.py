"""FieldLifecycleMesh for component-scoped validation records and projections."""

from __future__ import annotations

from flowguard import (
    FIELD_IMPACT_EXTERNAL_CONTRACT,
    FIELD_IMPACT_REPLAY,
    FIELD_IMPACT_ROUTING,
    FIELD_IMPACT_SCHEMA,
    FIELD_IMPACT_STATE,
    FIELD_ROLE_METADATA,
    FIELD_ROLE_ROUTING,
    FIELD_ROLE_SCHEMA_VERSION,
    FIELD_ROLE_STATE,
    TEST_KIND_FAILURE_PATH,
    TEST_KIND_HAPPY_PATH,
    TEST_KIND_NEGATIVE_PATH,
    TEST_KIND_REPLAY,
    FieldLifecycleGroup,
    FieldLifecyclePlan,
    FieldLifecycleRow,
    FieldProjection,
)


POLICY_FIELDS = (
    "field:impact_policy.policy_id",
    "field:impact_policy.classifier_version",
    "field:impact_policy.owner_receipt_root_ref",
)
INVENTORY_FIELDS = (
    "field:source_inventory.rows",
    "field:source_inventory.inventory_hash",
    "field:source_inventory.policy_version",
)
COMPONENT_FIELDS = (
    "field:content_component.component_id",
    "field:content_component.role",
    "field:content_component.install_disposition",
    "field:content_component.member_paths",
    "field:content_component.component_hash",
    "field:content_component.consumer_ids",
    "field:content_component.classification_rule_id",
    "field:content_component.override_reason",
)
GRAPH_HEALTH_FIELDS = (
    "field:impact_graph.impact_graph_hash",
    "field:impact_graph.unmapped_paths",
    "field:impact_graph.ambiguous_role_paths",
    "field:impact_graph.duplicate_owner_ids",
    "field:impact_graph.owner_cycles",
)
OWNER_FIELDS = (
    "field:execution_owner.execution_owner_id",
    "field:execution_owner.semantic_check_id",
    "field:execution_owner.maintenance_unit_id",
    "field:execution_owner.member_skill_id",
    "field:execution_owner.evidence_subject_id",
    "field:execution_owner.input_selectors",
    "field:execution_owner.depends_on_check_ids",
    "field:execution_owner.evidence_domain_id",
    "field:execution_owner.owner_declaration_hash",
    "field:execution_owner.input_component_ids",
    "field:execution_owner.owner_input_projection_hash",
)
PLAN_FIELDS = (
    "field:affected_plan.changed_component_ids",
    "field:affected_plan.will_reuse_owner_ids",
    "field:affected_plan.will_execute_owner_ids",
    "field:affected_plan.will_aggregate_only",
    "field:affected_plan.required_install_component_ids",
    "field:affected_plan.required_router_refresh",
    "field:affected_plan.required_portfolio_target_ids",
    "field:affected_plan.full_admitted",
    "field:affected_plan.full_admission_reason_codes",
    "field:affected_plan.plan_hash",
    "field:affected_plan.owner_check_ids",
    "field:affected_plan.owner_check_projections",
)
OWNER_EXECUTION_RESULT_FIELDS = (
    "field:owner_execution_result.plan_hash",
    "field:owner_execution_result.verified_planned_reuse_owner_ids",
    "field:owner_execution_result.executed_owner_ids",
    "field:owner_execution_result.reused_after_freeze_owner_ids",
    "field:owner_execution_result.failed_owner_ids",
    "field:owner_execution_result.not_run_owner_ids",
    "field:owner_execution_result.execution_count",
    "field:owner_execution_result.process_started_owner_ids",
    "field:owner_execution_result.check_ids",
    "field:owner_execution_result.check_projections",
)
RECEIPT_FIELDS = (
    "field:owner_receipt.execution_key",
    "field:owner_receipt.receipt_id",
    "field:owner_receipt.maintenance_unit_id",
    "field:owner_receipt.member_skill_id",
    "field:owner_receipt.evidence_subject_id",
    "field:owner_receipt.dependency_receipt_ids",
    "field:owner_receipt.stdout_sidecar_ref",
    "field:owner_receipt.stderr_sidecar_ref",
    "field:owner_receipt.result_sidecar_ref",
    "field:owner_receipt.termination_sidecar_ref",
    "field:owner_receipt.attempt_id",
    "field:owner_receipt.disposition",
)
AGGREGATION_FIELDS = (
    "field:parent_aggregation.maintenance_unit_id",
    "field:parent_aggregation.owner_receipt_refs",
    "field:parent_aggregation.owner_receipt_hashes",
    "field:parent_aggregation.selection_hash",
    "field:parent_aggregation.aggregation_declaration_hash",
    "field:parent_aggregation.aggregation_identity",
)
PROJECTION_FIELDS = (
    "field:external_projection.install_plan_hash",
    "field:external_projection.component_parity_hash",
    "field:external_projection.portfolio_projection_hash",
    "field:external_projection.router_projection_hash",
    "field:external_projection.managed_prompt_projection_hash",
)
DOMAIN_FIELDS = (
    "field:evidence_domain.domain_id",
    "field:evidence_domain.receipt_ids",
    "field:evidence_domain.missing_domain_ids",
)
EXECUTION_POLICY_FIELDS = (
    "field:execution_policy.consumer_carries_owner_receipt",
    "field:execution_policy.consumer_carries_owner_command",
    "field:execution_policy.resume_used_as_readonly_audit",
    "field:execution_policy.source_frozen",
    "field:execution_policy.toolchain_frozen",
    "field:execution_policy.full_execution_owner_count",
    "field:execution_policy.cleanup_confirmed_zero",
    "field:execution_policy.unattended_mutable_worktree_mode",
    "field:execution_policy.current_protocol_only",
)
EXTERNAL_TARGET_BINDING_FIELDS = (
    "field:external_target_binding.canonical_repository_root",
    "field:external_target_binding.member_root",
    "field:external_target_binding.member_root_path",
    "field:external_target_binding.binding_mode",
    "field:external_target_binding.fallback_used",
    "field:external_target_binding.retired_target_root_option",
)

ALL_FIELDS = (
    POLICY_FIELDS
    + INVENTORY_FIELDS
    + COMPONENT_FIELDS
    + GRAPH_HEALTH_FIELDS
    + OWNER_FIELDS
    + PLAN_FIELDS
    + OWNER_EXECUTION_RESULT_FIELDS
    + RECEIPT_FIELDS
    + AGGREGATION_FIELDS
    + PROJECTION_FIELDS
    + DOMAIN_FIELDS
    + EXECUTION_POLICY_FIELDS
    + EXTERNAL_TARGET_BINDING_FIELDS
)

GROUPS = (
    ("impact-policy", POLICY_FIELDS, "classification and persistent receipt policy"),
    ("source-inventory", INVENTORY_FIELDS, "complete omission-detection inventory that is not an owner key"),
    ("content-component", COMPONENT_FIELDS, "semantic roles, installation disposition, members, hashes, and consumers"),
    ("impact-graph", GRAPH_HEALTH_FIELDS, "fail-closed graph health and deterministic identity"),
    ("execution-owner", OWNER_FIELDS, "exact maintenance-unit owner, semantic check, member, subject, selectors, dependencies, and input projection"),
    ("affected-plan", PLAN_FIELDS, "frozen reuse, execution, aggregation, install, router, Portfolio, and full decisions"),
    ("owner-execution-result", OWNER_EXECUTION_RESULT_FIELDS, "exact frozen-plan resolution with visible reuse, execution, failure, and not-run outcomes"),
    ("owner-receipt", RECEIPT_FIELDS, "same-unit cross-run terminal-success identity with four complete sidecars"),
    ("parent-aggregation", AGGREGATION_FIELDS, "same-unit immutable child refs and independent aggregation identity"),
    ("external-projection", PROJECTION_FIELDS, "consumer distribution, parity, Portfolio summary, private router, and author-prompt projections"),
    ("evidence-domain", DOMAIN_FIELDS, "author source, owner, aggregation, and distribution-gate evidence separation"),
    ("execution-policy", EXECUTION_POLICY_FIELDS, "full fixpoint, one owner, cleanup, resume, and current-only boundaries"),
    ("external-target-binding", EXTERNAL_TARGET_BINDING_FIELDS, "canonical repository/member roles and direct replacement of the ambiguous old option"),
)


def _projection(field_id: str) -> FieldProjection:
    suffix = field_id.removeprefix("field:").replace(".", "-")
    return FieldProjection(
        f"projection:{suffix}",
        field_id,
        model_obligation_id=f"obligation:{suffix}",
        code_contract_id=f"contract:{suffix}",
        required_test_kinds=(
            TEST_KIND_HAPPY_PATH,
            TEST_KIND_FAILURE_PATH,
            TEST_KIND_NEGATIVE_PATH,
            TEST_KIND_REPLAY,
        ),
        external_inputs=(field_id,),
        external_outputs=("typed component, owner, receipt, plan, or visible blocker",),
        state_reads=(field_id,),
        state_writes=(field_id,),
        side_effects=("persist immutable owner or aggregation evidence only when the field owns such output",),
        error_paths=("missing", "malformed", "stale", "foreign", "tampered", "ambiguous", "cyclic"),
        evidence_refs=(f"gate:{suffix}", f"test:{suffix}:negative", f"replay:{suffix}:current"),
        rationale="the field affects exact routing, identity, replay, projection scope, or a fail-closed decision",
    )


def _role_and_impacts(field_id: str) -> tuple[str, tuple[str, ...]]:
    if field_id.endswith("version") or field_id.endswith("protocol_only"):
        return FIELD_ROLE_SCHEMA_VERSION, (FIELD_IMPACT_SCHEMA, FIELD_IMPACT_REPLAY)
    if any(token in field_id for token in ("role", "disposition", "consumer_ids", "selectors", "depends_on", "will_", "required_", "domain_id", "disposition")):
        return FIELD_ROLE_ROUTING, (FIELD_IMPACT_ROUTING, FIELD_IMPACT_STATE, FIELD_IMPACT_EXTERNAL_CONTRACT)
    if any(token in field_id for token in ("path", "ref", "reason", "attempt_id", "member_paths")):
        return FIELD_ROLE_METADATA, (FIELD_IMPACT_REPLAY, FIELD_IMPACT_EXTERNAL_CONTRACT)
    return FIELD_ROLE_STATE, (FIELD_IMPACT_STATE, FIELD_IMPACT_REPLAY, FIELD_IMPACT_EXTERNAL_CONTRACT)


def _group_id(field_id: str) -> str:
    for group_id, field_ids, _boundary in GROUPS:
        if field_id in field_ids:
            return f"{group_id}:leaf"
    raise KeyError(field_id)


def build_field_lifecycle() -> FieldLifecyclePlan:
    fields = tuple(
        FieldLifecycleRow(
            field_id,
            field_name=field_id.removeprefix("field:"),
            locations=(
                ".agents/skills/skillguard/.skillguard/contract-source.json",
                ".agents/skills/skillguard/.skillguard/compiled-contract.json",
                ".agents/skills/skillguard/.skillguard/check-manifest.json",
                ".agents/skills/skillguard/scripts/skillguard_v2",
                ".flowguard/validation_composition",
            ),
            group_id=_group_id(field_id),
            role=_role_and_impacts(field_id)[0],
            lifecycle=(
                "blocked"
                if field_id.endswith("retired_target_root_option")
                else "active"
            ),
            behavior_impacts=_role_and_impacts(field_id)[1],
            reader_ids=(
                "skillguard.impact_planner",
                "skillguard.check_runner",
                "skillguard.testmesh",
                "skillguard.installer",
                "skillguard.portfolio",
                "skillguard.global_router",
                "skillguard.consumer_distribution",
            ),
            writer_ids=(
                "skillguard.contract_compiler",
                "skillguard.owner_executor",
                "skillguard.parent_aggregator",
            ),
            projection=_projection(field_id),
        )
        for field_id in ALL_FIELDS
    )
    groups = []
    for group_id, field_ids, boundary in GROUPS:
        groups.extend(
            (
                FieldLifecycleGroup(
                    group_id,
                    boundary_kind=boundary,
                    field_ids=field_ids,
                    child_group_ids=(f"{group_id}:leaf",),
                    owner_route="field_lifecycle_mesh",
                ),
                FieldLifecycleGroup(
                    f"{group_id}:leaf",
                    boundary_kind="leaf_fields",
                    parent_group_id=group_id,
                    field_ids=field_ids,
                    owner_route="field_lifecycle_mesh",
                ),
            )
        )
    return FieldLifecyclePlan(
        "skillguard-validation-composition-fields",
        discovered_field_ids=ALL_FIELDS,
        claim_scope="full",
        groups=tuple(groups),
        fields=fields,
        notes=(
            "The complete source inventory remains active for omission detection but its former execution_identity role is retired from owner keys. "
            "Broad source_authority_hash, run-bound success slots, caller-authored broad_semantic_change, and daily retired-runtime success fields are replaced, not aliased. "
            "Retired wire shapes remain exact rejection fixtures only; one current field path is accepted."
            " External target checks bind canonical_repository_root, member_root, member_root_path, and binding_mode explicitly; "
            "fallback_used is fixed false and the former check-contract target_root option is blocked rather than aliased."
        ),
    )
