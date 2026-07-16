"""FlowGuard Risk Purpose Header

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Review whether an agent grounded an existing-system change in the FlowGuard models that already exist.
Guards against: proposing new modules, rules, workflows, or ownership boundaries before checking existing FunctionBlocks, state owners, side-effect owners, public entrypoints, and model responsibilities.
Use before editing: Run this before implementation, OpenSpec proposals, major architecture changes, or risky behavior changes in an existing modeled system.
Run: python .flowguard/existing_model_preflight/run_checks.py
"""

from __future__ import annotations

from flowguard import (
    DuplicateBoundaryRisk,
    ExistingIntentSurface,
    ExistingModelPreflight,
    ExistingOwnershipSnapshot,
    ModelContextHit,
    REUSE_DECISION_ADD_CHILD_MODEL,
    REUSE_DECISION_EXTEND_EXISTING,
    review_existing_model_preflight,
)


def correct_preflight():
    return ExistingModelPreflight(
        "validated-template-pack-supervision-preflight",
        "Extend SkillGuard's current executable-contract runtime with target-owned template-pack supervision",
        mode="full",
        model_search_performed=True,
        search_paths=(
            ".flowguard/development_process_flow",
            ".agents/skills/skillguard",
            "openspec/changes/build-executable-skill-contract-runtime",
            "openspec/changes/add-validated-template-pack-supervision",
        ),
        relevant_models=(
            ModelContextHit(
                "skillguard-executable-contract-runtime",
                model_path=".flowguard/development_process_flow/skillguard_executable_contract_model.py",
                evidence_id="skillguard-executable-contract-runtime:current-source",
                evidence_tier="abstract_green",
                responsibilities=(
                    "compile the sole current contract authority",
                    "select declared routes and supervise target-native checks",
                    "issue immutable evidence and closure receipts",
                    "install and project current target skills",
                ),
                function_blocks=("EvaluateExecutableContract",),
                state_owned=("contract_authority", "run_state", "receipt_identity"),
                fields_owned=(
                    "field:native_route_binding",
                    "field:native_check_inventory",
                    "field:content_impact_component",
                ),
                side_effects_owned=("write_current_contract", "activate_target_installation"),
                public_entrypoints=(
                    "skillguard plan-skill",
                    "skillguard generate-skill",
                    "skillguard supervise",
                ),
                validation_evidence=(
                    "current FlowGuard executable-contract model",
                    "current source/compiled/manifest contract tests",
                ),
            ),
        ),
        ownership_snapshot=ExistingOwnershipSnapshot(
            function_block_owners=(("EvaluateExecutableContract", "skillguard-executable-contract-runtime"),),
            state_owners=(
                ("contract_authority", "skillguard-executable-contract-runtime"),
                ("run_state", "skillguard-executable-contract-runtime"),
                ("receipt_identity", "skillguard-executable-contract-runtime"),
            ),
            field_owners=(
                ("field:native_route_binding", "skillguard-executable-contract-runtime"),
                ("field:native_check_inventory", "skillguard-executable-contract-runtime"),
                ("field:content_impact_component", "skillguard-executable-contract-runtime"),
            ),
            side_effect_owners=(
                ("write_current_contract", "skillguard-executable-contract-runtime"),
                ("activate_target_installation", "skillguard-executable-contract-runtime"),
            ),
            public_entrypoint_owners=(
                ("skillguard plan-skill", "skillguard-executable-contract-runtime"),
                ("skillguard generate-skill", "skillguard-executable-contract-runtime"),
                ("skillguard supervise", "skillguard-executable-contract-runtime"),
            ),
        ),
        reuse_decision=REUSE_DECISION_EXTEND_EXISTING,
        downstream_routes=(
            "field_lifecycle_mesh",
            "development_process_flow",
            "model_test_alignment",
            "test_mesh_maintenance",
        ),
        behavior_field_ids=(
            "field:template_manifest_identity",
            "field:template_selection_receipt",
            "field:template_instance_receipt",
        ),
        field_lifecycle_model_ids=("skillguard-executable-contract-runtime",),
        affected_business_intent_id="intent:template-first-skill-maintenance",
        selected_commitment_id="commitment:supervise-target-owned-template-pack",
        selected_primary_path_id="path:skillguard-current-contract-runtime",
        expected_surface_ids=(
            "surface:plan-skill",
            "surface:generate-skill",
            "surface:supervise-template-instance",
        ),
        intent_surfaces=(
            ExistingIntentSurface(
                "surface:plan-skill",
                surface_kind="cli",
                business_intent_id="intent:template-first-skill-maintenance",
                behavior_commitment_id="commitment:supervise-target-owned-template-pack",
                business_path_id="skillguard.plan-skill",
                primary_path_id="path:skillguard-current-contract-runtime",
                expected_terminal="candidate_plan_or_visible_blocker",
                state_writes=("selection_plan",),
                owner_id="skillguard-executable-contract-runtime",
                evidence_ids=("inventory:skillguard-plan-skill",),
            ),
            ExistingIntentSurface(
                "surface:generate-skill",
                surface_kind="cli",
                business_intent_id="intent:template-first-skill-maintenance",
                behavior_commitment_id="commitment:supervise-target-owned-template-pack",
                business_path_id="skillguard.generate-skill",
                primary_path_id="path:skillguard-current-contract-runtime",
                expected_terminal="current_contract_written_or_visible_blocker",
                state_writes=("contract_authority",),
                side_effects=("write_current_contract",),
                owner_id="skillguard-executable-contract-runtime",
                evidence_ids=("inventory:skillguard-generate-skill",),
            ),
            ExistingIntentSurface(
                "surface:supervise-template-instance",
                surface_kind="api",
                business_intent_id="intent:template-first-skill-maintenance",
                behavior_commitment_id="commitment:supervise-target-owned-template-pack",
                business_path_id="skillguard.supervise",
                primary_path_id="path:skillguard-current-contract-runtime",
                expected_terminal="enforced_closure_or_visible_blocker",
                state_writes=("run_state", "receipt_identity"),
                owner_id="skillguard-executable-contract-runtime",
                evidence_ids=("inventory:skillguard-supervisor",),
            ),
        ),
        surface_inventory_revision="template-pack-supervision-surfaces:v1",
        surface_inventory_evidence_ids=("inventory:template-pack-supervision:v1",),
        require_complete_surface_inventory=True,
        rationale=(
            "The current executable-contract runtime already owns compilation, route/check supervision, receipts, "
            "closure, installation, and global handoff. Extend that boundary with target-neutral template identity "
            "and selection supervision; keep every Guard family's applicability, builder, validator, and semantics native."
        ),
    )


def broken_duplicate_preflight():
    return ExistingModelPreflight(
        "broken-parallel-template-runtime",
        "Create a second SkillGuard template execution authority",
        mode="full",
        model_search_performed=True,
        search_paths=(".flowguard/development_process_flow",),
        relevant_models=(correct_preflight().relevant_models[0],),
        ownership_snapshot=ExistingOwnershipSnapshot(
            state_owners=(("contract_authority", "skillguard-executable-contract-runtime"),),
        ),
        reuse_decision=REUSE_DECISION_ADD_CHILD_MODEL,
        downstream_routes=("model_mesh_maintenance",),
        proposed_new_boundaries=("parallel-template-runtime",),
        rationale="A second executor would duplicate the sole current contract and receipt authority.",
        duplicate_risks=(
            DuplicateBoundaryRisk(
                "state",
                "contract_authority",
                "skillguard-executable-contract-runtime",
                proposed_owner_id="parallel-template-runtime",
            ),
        ),
    )


def run_checks():
    return (
        review_existing_model_preflight(correct_preflight()),
        review_existing_model_preflight(broken_duplicate_preflight()),
    )
