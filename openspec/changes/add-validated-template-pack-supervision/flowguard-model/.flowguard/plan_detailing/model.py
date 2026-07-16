"""FlowGuard PlanDetail for validated template-pack supervision.

Created from FlowGuard's plan-detailing template.  The passing row proves that
the implementation plan is structurally checkable; it does not claim that any
pending implementation, installation, test, or Git synchronization has passed.
"""

from __future__ import annotations

from flowguard import (
    PLAN_DETAIL_CLAIM_SCOPED,
    PlanDetail,
    PlanDetailEvidence,
    PlanDetailFailureBranch,
    PlanDetailFreshnessRule,
    PlanDetailSideEffect,
    PlanDetailSource,
    PlanDetailStateSurface,
    PlanDetailStep,
    PlanDetailSurface,
    PlanDetailValidation,
    ProcessArtifact,
    plan_detail_to_development_process,
    plan_detail_to_plan_intake,
    plan_detail_to_step_contracts,
    review_development_process_flow,
    review_plan_detail,
    review_plan_intake_completeness,
)


def detailed_plan() -> PlanDetail:
    return PlanDetail(
        "validated-template-pack-program",
        task_summary=(
            "Add validated template-pack selection and supervision to SkillGuard, then bind "
            "target-owned template builders across the Guard family without changing OpenSpec."
        ),
        goal=(
            "Replace repeated blank-page skill/model construction with deterministic template search, "
            "preview, composition, native validation, receipts, installation parity, and harvest closure."
        ),
        assumptions=(
            "OpenSpec is an external provider and is not modified by this program.",
            "Peer-owned dirty worktrees are preserved and integrated only after explicit handoff.",
            "Each Guard remains the sole owner of domain semantics and native validation.",
        ),
        sources=(
            PlanDetailSource(
                "source:user-objective",
                "manual",
                supports_surface_ids=(
                    "surface:wrong-template-selection",
                    "surface:duplicate-authority",
                    "surface:peer-write-loss",
                    "surface:stale-installation",
                ),
                summary="User-authorized template-first Guard-family upgrade with installation and Git synchronization.",
            ),
            PlanDetailSource(
                "source:openspec-work-package",
                "spec_work_package",
                supports_surface_ids=(
                    "surface:wrong-template-selection",
                    "surface:duplicate-authority",
                    "surface:stale-installation",
                ),
                summary="Current official OpenSpec planning artifacts for this SkillGuard change.",
                spec_provider_id="provider:openspec-official",
                work_package_id="work-package:add-validated-template-pack-supervision",
                change_id="add-validated-template-pack-supervision",
                spec_task_ids=(
                    "task:protocol",
                    "task:selection",
                    "task:family-packs",
                    "task:installation",
                ),
                spec_obligation_ids=(
                    "obligation:selection-deterministic",
                    "obligation:native-owner-preserved",
                    "obligation:installed-parity",
                ),
                spec_check_ids=(
                    "check:template-protocol",
                    "check:family-native",
                    "check:installation-parity",
                ),
                spec_binding_ids=(
                    "binding:protocol",
                    "binding:selection",
                    "binding:family-packs",
                    "binding:installation",
                ),
            ),
        ),
        surfaces=(
            PlanDetailSurface(
                "surface:wrong-template-selection",
                description="A lexical or tie-break heuristic selects an inapplicable template or hides ambiguity.",
                source_ids=("source:user-objective", "source:openspec-work-package"),
                recurring=True,
                high_risk=True,
                observed_failure_ids=("observed:repeated-ai-template-error",),
                same_class_case_ids=("case:zero-one-many-selection", "case:field-owner-conflict"),
                historical_holdout_ids=("holdout:stale-template-digest",),
            ),
            PlanDetailSurface(
                "surface:duplicate-authority",
                description="SkillGuard or a fragment becomes a second domain router or fourth contract authority.",
                source_ids=("source:user-objective", "source:openspec-work-package"),
                high_risk=True,
                observed_failure_ids=("observed:parallel-contract-authority-risk",),
                same_class_case_ids=("case:fragment-adds-domain-check",),
                historical_holdout_ids=("holdout:former-runtime-residual",),
            ),
            PlanDetailSurface(
                "surface:peer-write-loss",
                description="Integration overwrites another AI's current work or restarts from an older clean snapshot.",
                source_ids=("source:user-objective",),
                high_risk=True,
                observed_failure_ids=("observed:active-peer-worktrees",),
                same_class_case_ids=("case:unknown-writer-change",),
                historical_holdout_ids=("holdout:dirty-worktree-integration",),
            ),
            PlanDetailSurface(
                "surface:stale-installation",
                description="Source, installed skill, package runtime, router prompt, and Git revision are treated as one identity.",
                source_ids=("source:user-objective", "source:openspec-work-package"),
                high_risk=True,
                observed_failure_ids=("observed:source-installed-drift",),
                same_class_case_ids=("case:source-installed-drift",),
                historical_holdout_ids=("holdout:stale-router-projection",),
            ),
        ),
        artifacts=(
            ProcessArtifact("artifact:openspec-plan", "requirement", "1"),
            ProcessArtifact("artifact:flowguard-models", "model", "1", upstream_artifact_ids=("artifact:openspec-plan",)),
            ProcessArtifact("artifact:skillguard-runtime", "code", "planned", upstream_artifact_ids=("artifact:openspec-plan", "artifact:flowguard-models")),
            ProcessArtifact("artifact:guard-family-packs", "code", "planned", upstream_artifact_ids=("artifact:openspec-plan", "artifact:flowguard-models")),
            ProcessArtifact("artifact:focused-tests", "test", "planned"),
            ProcessArtifact("artifact:installed-projections", "adapter", "planned", upstream_artifact_ids=("artifact:skillguard-runtime", "artifact:guard-family-packs")),
            ProcessArtifact("artifact:git-revisions", "release_asset", "planned", upstream_artifact_ids=("artifact:installed-projections",)),
        ),
        state_surfaces=(
            PlanDetailStateSurface(
                "template_selection_identity",
                owner="target catalog plus SkillGuard supervision",
                read_by_step_ids=("implement-supervision", "implement-family-packs", "focused-validation"),
                written_by_step_ids=("implement-supervision",),
            ),
            PlanDetailStateSurface(
                "peer_owned_worktree_identity",
                owner="development_process_flow",
                read_by_step_ids=("freeze-authority", "integrate-peer-work", "sync-install-and-git"),
                written_by_step_ids=("freeze-authority", "integrate-peer-work"),
            ),
            PlanDetailStateSurface(
                "installed_projection_identity",
                owner="SkillGuard installation transaction",
                read_by_step_ids=("sync-install-and-git", "final-verification"),
                written_by_step_ids=("sync-install-and-git",),
            ),
        ),
        side_effects=(
            PlanDetailSideEffect(
                "effect:activate-installed-skills",
                step_id="sync-install-and-git",
                effect_kind="installation_activation",
                required_evidence_ids=("evidence:focused-validation",),
                description="Activate content-exact installed skill projections only after focused native evidence.",
            ),
            PlanDetailSideEffect(
                "effect:commit-and-push-guard-revisions",
                step_id="sync-install-and-git",
                effect_kind="git_publication",
                required_evidence_ids=("evidence:final-verification",),
                description="Commit and push only the verified Guard revisions; OpenSpec remains untouched.",
            ),
        ),
        steps=(
            PlanDetailStep(
                "freeze-authority",
                "Freeze canonical sources, peer worktrees, native routes, provider identities, and edit boundaries.",
                skill_name="flowguard-existing-model-preflight",
                produces_receipts=("receipt:authority-map",),
                writes_artifacts=("artifact:openspec-plan", "artifact:flowguard-models"),
                spec_provider_id="provider:openspec-official",
                work_package_id="work-package:add-validated-template-pack-supervision",
                change_id="add-validated-template-pack-supervision",
                spec_task_ids=("task:protocol",),
                spec_binding_ids=("binding:protocol",),
            ),
            PlanDetailStep(
                "implement-supervision",
                "Implement the target-neutral manifest, selector supervision, receipt, compiler-fragment, prompt, and launch boundaries.",
                skill_name="skillguard",
                order_after=("freeze-authority",),
                requires_receipts=("receipt:authority-map",),
                produces_receipts=("receipt:skillguard-source-updated",),
                reads_artifacts=("artifact:openspec-plan", "artifact:flowguard-models"),
                writes_artifacts=("artifact:skillguard-runtime",),
                spec_provider_id="provider:openspec-official",
                work_package_id="work-package:add-validated-template-pack-supervision",
                change_id="add-validated-template-pack-supervision",
                spec_task_ids=("task:protocol", "task:selection"),
                spec_binding_ids=("binding:protocol", "binding:selection"),
            ),
            PlanDetailStep(
                "implement-family-packs",
                "Implement each Guard-owned catalog, builder, validator binding, fixtures, and skill guidance.",
                skill_name="guard-family-native-owners",
                order_after=("freeze-authority",),
                requires_receipts=("receipt:authority-map",),
                produces_receipts=("receipt:family-source-updated",),
                reads_artifacts=("artifact:openspec-plan", "artifact:flowguard-models"),
                writes_artifacts=("artifact:guard-family-packs",),
                spec_provider_id="provider:openspec-official",
                work_package_id="work-package:add-validated-template-pack-supervision",
                change_id="add-validated-template-pack-supervision",
                spec_task_ids=("task:family-packs",),
                spec_binding_ids=("binding:family-packs",),
            ),
            PlanDetailStep(
                "integrate-peer-work",
                "Re-read and integrate peer-owned source without rollback, then freeze the combined source identity.",
                skill_name="flowguard-development-process-flow",
                order_after=("implement-supervision", "implement-family-packs"),
                requires_receipts=("receipt:skillguard-source-updated", "receipt:family-source-updated"),
                produces_receipts=("receipt:integration-source-frozen",),
                reads_artifacts=("artifact:skillguard-runtime", "artifact:guard-family-packs"),
            ),
            PlanDetailStep(
                "focused-validation",
                "Run frozen affected-owner model, native, contract, platform, and projection checks.",
                skill_name="flowguard-test-mesh",
                order_after=("integrate-peer-work",),
                requires_receipts=("receipt:integration-source-frozen",),
                produces_receipts=("receipt:focused-validation",),
                reads_artifacts=("artifact:skillguard-runtime", "artifact:guard-family-packs", "artifact:focused-tests"),
                produced_evidence_ids=("evidence:focused-validation",),
                continue_evidence_ids=("evidence:focused-validation",),
                validation_required=True,
                rework_step_id="implement-supervision",
                spec_provider_id="provider:openspec-official",
                work_package_id="work-package:add-validated-template-pack-supervision",
                change_id="add-validated-template-pack-supervision",
                spec_task_ids=("task:protocol", "task:selection", "task:family-packs"),
                spec_binding_ids=("binding:protocol", "binding:selection", "binding:family-packs"),
            ),
            PlanDetailStep(
                "sync-install-and-git",
                "Stage and activate target installations, refresh affected routing projections, and synchronize verified Guard Git revisions.",
                skill_name="skillguard",
                order_after=("focused-validation",),
                requires_receipts=("receipt:focused-validation",),
                produces_receipts=("receipt:installation-and-git-synced",),
                reads_artifacts=("artifact:skillguard-runtime", "artifact:guard-family-packs"),
                writes_artifacts=("artifact:installed-projections", "artifact:git-revisions"),
                required_evidence_ids=("evidence:focused-validation",),
                side_effect_ids=("effect:activate-installed-skills", "effect:commit-and-push-guard-revisions"),
                spec_provider_id="provider:openspec-official",
                work_package_id="work-package:add-validated-template-pack-supervision",
                change_id="add-validated-template-pack-supervision",
                spec_task_ids=("task:installation",),
                spec_binding_ids=("binding:installation",),
            ),
            PlanDetailStep(
                "final-verification",
                "Run the one final all-model and full-test owners and audit every original obligation against current evidence.",
                skill_name="flowguard-development-process-flow",
                order_after=("sync-install-and-git",),
                requires_receipts=("receipt:installation-and-git-synced",),
                produces_receipts=("receipt:final-verification",),
                reads_artifacts=(
                    "artifact:skillguard-runtime",
                    "artifact:guard-family-packs",
                    "artifact:installed-projections",
                    "artifact:git-revisions",
                ),
                produced_evidence_ids=("evidence:final-verification",),
                continue_evidence_ids=("evidence:final-verification",),
                validation_required=True,
                rework_step_id="integrate-peer-work",
            ),
        ),
        validations=(
            PlanDetailValidation(
                "validation:template-protocol",
                required_artifact_ids=("artifact:skillguard-runtime", "artifact:focused-tests"),
                required_evidence_kinds=("model_and_test_receipt",),
                evidence_ids=("evidence:focused-validation",),
                command="frozen affected-owner plan",
                spec_provider_id="provider:openspec-official",
                work_package_id="work-package:add-validated-template-pack-supervision",
                change_id="add-validated-template-pack-supervision",
                spec_obligation_ids=("obligation:selection-deterministic", "obligation:native-owner-preserved"),
                spec_check_ids=("check:template-protocol",),
                spec_binding_ids=("binding:protocol", "binding:selection"),
            ),
            PlanDetailValidation(
                "validation:family-native",
                required_artifact_ids=("artifact:guard-family-packs", "artifact:focused-tests"),
                required_evidence_kinds=("native_guard_receipt",),
                evidence_ids=("evidence:focused-validation",),
                command="target-native checks from frozen owner plan",
                spec_provider_id="provider:openspec-official",
                work_package_id="work-package:add-validated-template-pack-supervision",
                change_id="add-validated-template-pack-supervision",
                spec_obligation_ids=("obligation:native-owner-preserved",),
                spec_check_ids=("check:family-native",),
                spec_binding_ids=("binding:family-packs",),
            ),
            PlanDetailValidation(
                "validation:installation-parity",
                required_artifact_ids=("artifact:installed-projections", "artifact:git-revisions"),
                required_evidence_kinds=("installation_and_git_receipt",),
                evidence_ids=("evidence:final-verification",),
                command="final frozen integration owners",
                release_required=True,
                spec_provider_id="provider:openspec-official",
                work_package_id="work-package:add-validated-template-pack-supervision",
                change_id="add-validated-template-pack-supervision",
                spec_obligation_ids=("obligation:installed-parity",),
                spec_check_ids=("check:installation-parity",),
                spec_binding_ids=("binding:installation",),
            ),
        ),
        evidence=(
            PlanDetailEvidence(
                "evidence:focused-validation",
                "model_and_native_test_receipts",
                "not_run",
                produced_by_step_id="focused-validation",
                covers_artifacts=("artifact:skillguard-runtime", "artifact:guard-family-packs"),
                verifier_artifacts=("artifact:focused-tests",),
                validation_ids=("validation:template-protocol", "validation:family-native"),
                covered_versions={
                    "artifact:skillguard-runtime": "planned",
                    "artifact:guard-family-packs": "planned",
                    "artifact:focused-tests": "planned",
                },
                command="frozen affected-owner plan",
                description="Expected evidence; intentionally not claimed as executed by the planning model.",
            ),
            PlanDetailEvidence(
                "evidence:final-verification",
                "installation_and_git_receipt",
                "not_run",
                produced_by_step_id="final-verification",
                covers_artifacts=("artifact:installed-projections", "artifact:git-revisions"),
                verifier_artifacts=("artifact:focused-tests",),
                validation_ids=("validation:installation-parity",),
                covered_versions={
                    "artifact:installed-projections": "planned",
                    "artifact:git-revisions": "planned",
                    "artifact:focused-tests": "planned",
                },
                command="one final all-model owner plus one full-test owner",
                description="Expected final evidence; no completion claim is made by this plan.",
            ),
        ),
        failure_branches=(
            PlanDetailFailureBranch(
                "branch:peer-overlap",
                trigger="A target path is still owned by a concurrent or unmerged worktree.",
                step_id="integrate-peer-work",
                rework_step_id="freeze-authority",
                expected_resolution="Wait for or obtain handoff, re-read the current source, and rederive affected validation.",
            ),
            PlanDetailFailureBranch(
                "branch:selection-or-template-failure",
                trigger="A selection, composition, schema, builder, or native validator check fails.",
                step_id="focused-validation",
                rework_step_id="implement-supervision",
                expected_resolution="Classify the owning layer, repair the primary owner, and rerun affected obligations only.",
            ),
            PlanDetailFailureBranch(
                "branch:installation-or-git-drift",
                trigger="Installed projection, router prompt, runtime, or Git identity differs from the frozen source.",
                step_id="sync-install-and-git",
                rework_step_id="integrate-peer-work",
                expected_resolution="Abort or roll back the target transaction, preserve peer work, refreeze identities, and revalidate.",
            ),
            PlanDetailFailureBranch(
                "branch:final-owner-fails",
                trigger="The final all-model or full-test owner returns non-pass or stale evidence.",
                step_id="final-verification",
                rework_step_id="integrate-peer-work",
                expected_resolution="Repair the primary cause and create a new stable final snapshot; never relabel the failed receipt.",
            ),
        ),
        freshness_rules=(
            PlanDetailFreshnessRule(
                "rule:spec-invalidates-implementation",
                "artifact:openspec-plan",
                invalidates_artifact_ids=("artifact:flowguard-models", "artifact:skillguard-runtime", "artifact:guard-family-packs"),
            ),
            PlanDetailFreshnessRule(
                "rule:runtime-invalidates-install-and-git",
                "artifact:skillguard-runtime",
                invalidates_artifact_ids=("artifact:installed-projections", "artifact:git-revisions"),
                invalidates_evidence_kinds=("installation_and_git_receipt",),
            ),
            PlanDetailFreshnessRule(
                "rule:family-pack-invalidates-install-and-git",
                "artifact:guard-family-packs",
                invalidates_artifact_ids=("artifact:installed-projections", "artifact:git-revisions"),
                invalidates_evidence_kinds=("native_guard_receipt", "installation_and_git_receipt"),
            ),
        ),
        final_claim=PLAN_DETAIL_CLAIM_SCOPED,
        claim_labels=(),
        process_optimization_reasons=(),
        required_process_optimization_evidence_ids=(),
    )


def missing_failure_branch_plan() -> PlanDetail:
    base = detailed_plan()
    return PlanDetail(
        "missing-failure-branch",
        task_summary=base.task_summary,
        goal=base.goal,
        sources=base.sources,
        surfaces=base.surfaces,
        artifacts=base.artifacts,
        state_surfaces=base.state_surfaces,
        side_effects=base.side_effects,
        steps=base.steps,
        validations=base.validations,
        evidence=base.evidence,
        freshness_rules=base.freshness_rules,
        final_claim=PLAN_DETAIL_CLAIM_SCOPED,
        claim_labels=(),
    )


def missing_rework_plan() -> PlanDetail:
    base = detailed_plan()
    steps = tuple(
        PlanDetailStep(
            step.step_id,
            step.action,
            skill_name=step.skill_name,
            step_type=step.step_type,
            order_after=step.order_after,
            requires_receipts=step.requires_receipts,
            produces_receipts=step.produces_receipts,
            reads_artifacts=step.reads_artifacts,
            writes_artifacts=step.writes_artifacts,
            required_evidence_ids=step.required_evidence_ids,
            produced_evidence_ids=step.produced_evidence_ids,
            continue_evidence_ids=step.continue_evidence_ids,
            validation_required=step.validation_required,
            rework_step_id="" if step.step_id == "focused-validation" else step.rework_step_id,
            side_effect_ids=step.side_effect_ids,
            spec_provider_id=step.spec_provider_id,
            work_package_id=step.work_package_id,
            change_id=step.change_id,
            spec_task_ids=step.spec_task_ids,
            spec_binding_ids=step.spec_binding_ids,
        )
        for step in base.steps
    )
    return PlanDetail(
        "missing-rework",
        task_summary=base.task_summary,
        goal=base.goal,
        sources=base.sources,
        surfaces=base.surfaces,
        artifacts=base.artifacts,
        state_surfaces=base.state_surfaces,
        side_effects=base.side_effects,
        steps=steps,
        validations=base.validations,
        evidence=base.evidence,
        failure_branches=base.failure_branches,
        freshness_rules=base.freshness_rules,
        final_claim=PLAN_DETAIL_CLAIM_SCOPED,
        claim_labels=(),
    )


def missing_validation_plan() -> PlanDetail:
    base = detailed_plan()
    return PlanDetail(
        "missing-validation",
        task_summary=base.task_summary,
        goal=base.goal,
        sources=base.sources,
        surfaces=base.surfaces,
        artifacts=base.artifacts,
        state_surfaces=base.state_surfaces,
        steps=base.steps,
        failure_branches=base.failure_branches,
        freshness_rules=base.freshness_rules,
        final_claim=PLAN_DETAIL_CLAIM_SCOPED,
        claim_labels=(),
    )


def run_checks():
    good = detailed_plan()
    missing_failure = missing_failure_branch_plan()
    missing_rework = missing_rework_plan()
    missing_validation = missing_validation_plan()
    detail_reports = (
        review_plan_detail(good),
        review_plan_detail(missing_failure),
        review_plan_detail(missing_rework),
        review_plan_detail(missing_validation),
    )
    intake = review_plan_intake_completeness(plan_detail_to_plan_intake(good))
    process = review_development_process_flow(plan_detail_to_development_process(good))
    contracts = plan_detail_to_step_contracts(good)
    return detail_reports, intake, process, contracts
