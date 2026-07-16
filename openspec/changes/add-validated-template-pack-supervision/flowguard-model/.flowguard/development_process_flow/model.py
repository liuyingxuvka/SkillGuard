"""DevelopmentProcessFlow for the validated Template Pack programme.

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard

Purpose:
Prove only that the official-OpenSpec work package, ownership preflight, and
executable programme plan form a current planning baseline.  Production code,
installed projections, full validation, release, and Git publication are
deliberately outside this planning-ready claim until their own evidence exists.

Guards against:
- treating an apply-ready OpenSpec change as implemented work;
- reusing planning-model evidence after the OpenSpec obligations change;
- claiming broad completion while family builders, installations, or tests are
  still planned/not-run;
- allowing peer-owned files to disappear from the handoff boundary.

Run:
python .flowguard/development_process_flow/run_checks.py
"""

from __future__ import annotations

from flowguard import (
    PROCESS_ARTIFACT_MODEL,
    PROCESS_ARTIFACT_REQUIREMENT,
    PROCESS_ARTIFACT_TEST,
    PROCESS_EVIDENCE_PASSED,
    PROCESS_SCOPE_RELEASE,
    DevelopmentProcessPlan,
    FreshnessRule,
    ProcessAction,
    ProcessArtifact,
    ProcessEvidence,
    ValidationRequirement,
    review_development_process_flow,
)


CHANGE_ID = "add-validated-template-pack-supervision"


def planning_artifacts(*, specification_version: str = "1") -> tuple[ProcessArtifact, ...]:
    """Return only artifacts that are already part of the planning claim."""

    return (
        ProcessArtifact(
            "openspec.template-pack-work-package",
            PROCESS_ARTIFACT_REQUIREMENT,
            specification_version,
            path=f"openspec/changes/{CHANGE_ID}",
            owner="official-openspec-provider",
            description=(
                "Apply-ready proposal, design, delta specifications, and tasks. "
                "The provider implementation is external and frozen read-only."
            ),
            spec_provider_id="official-openspec-cli-1.6.0",
            work_package_id=f"openspec:{CHANGE_ID}",
            spec_task_ids=("tasks:1.1", "tasks:1.2", "tasks:1.4", "tasks:1.5"),
            spec_obligation_ids=(
                "template-pack-protocol",
                "template-profile-compilation",
                "template-first-skill-maintenance",
                "portable-declared-check-launch",
            ),
        ),
        ProcessArtifact(
            "flowguard.existing-owner-preflight",
            PROCESS_ARTIFACT_MODEL,
            "1",
            path=".flowguard/existing_model_preflight/model.py",
            owner="flowguard-existing-model-preflight",
            upstream_artifact_ids=("openspec.template-pack-work-package",),
            description="Current owner and duplicate-boundary model.",
        ),
        ProcessArtifact(
            "flowguard.programme-plan",
            PROCESS_ARTIFACT_MODEL,
            "1",
            path=".flowguard/plan_detailing/model.py",
            owner="flowguard-plan-detailing-compiler",
            upstream_artifact_ids=(
                "openspec.template-pack-work-package",
                "flowguard.existing-owner-preflight",
            ),
            description="Cross-repository steps, receipts, failures, and claim boundaries.",
        ),
        ProcessArtifact(
            "flowguard.planning-checks",
            PROCESS_ARTIFACT_TEST,
            "1",
            path=".flowguard",
            owner="flowguard",
            upstream_artifact_ids=(
                "flowguard.existing-owner-preflight",
                "flowguard.programme-plan",
            ),
            description="Executable preflight and plan-detail model check entrypoints.",
        ),
    )


def current_planning_plan() -> DevelopmentProcessPlan:
    """A green plan whose claim is exactly planning-ready, never done/release."""

    return DevelopmentProcessPlan(
        "validated-template-pack-planning-baseline",
        artifacts=planning_artifacts(),
        actions=(
            ProcessAction(
                "freeze-official-openspec-work-package",
                reads_artifacts=("openspec.template-pack-work-package",),
                description="Read the provider-owned work package without modifying OpenSpec.",
            ),
            ProcessAction(
                "run-existing-owner-preflight",
                reads_artifacts=(
                    "openspec.template-pack-work-package",
                    "flowguard.existing-owner-preflight",
                ),
                produced_evidence_ids=("existing-owner-preflight-pass",),
                order_after=("freeze-official-openspec-work-package",),
            ),
            ProcessAction(
                "run-plan-detail-checks",
                reads_artifacts=(
                    "openspec.template-pack-work-package",
                    "flowguard.programme-plan",
                    "flowguard.planning-checks",
                ),
                produced_evidence_ids=("programme-plan-pass",),
                order_after=("run-existing-owner-preflight",),
            ),
            ProcessAction(
                "claim-planning-ready-only",
                action_type="work",
                required_validation_ids=(
                    "existing-owner-preflight-current",
                    "programme-plan-current",
                ),
                order_after=("run-plan-detail-checks",),
                description=(
                    "Permit implementation to start. This is not an implementation, "
                    "installation, release, archive, or publication claim."
                ),
            ),
        ),
        evidence=(
            ProcessEvidence(
                "existing-owner-preflight-pass",
                evidence_kind="existing_model_preflight",
                producer_route="existing_model_preflight",
                status=PROCESS_EVIDENCE_PASSED,
                covers_artifacts=(
                    "openspec.template-pack-work-package",
                    "flowguard.existing-owner-preflight",
                ),
                verifier_artifacts=("flowguard.planning-checks",),
                covered_versions={
                    "openspec.template-pack-work-package": "1",
                    "flowguard.existing-owner-preflight": "1",
                    "flowguard.planning-checks": "1",
                },
                validation_requirement_ids=("existing-owner-preflight-current",),
                produced_by_action_id="run-existing-owner-preflight",
                command="python .flowguard/existing_model_preflight/run_checks.py",
            ),
            ProcessEvidence(
                "programme-plan-pass",
                evidence_kind="plan_detail",
                producer_route="plan_detailing_compiler",
                status=PROCESS_EVIDENCE_PASSED,
                covers_artifacts=(
                    "openspec.template-pack-work-package",
                    "flowguard.programme-plan",
                ),
                verifier_artifacts=("flowguard.planning-checks",),
                covered_versions={
                    "openspec.template-pack-work-package": "1",
                    "flowguard.programme-plan": "1",
                    "flowguard.planning-checks": "1",
                },
                validation_requirement_ids=("programme-plan-current",),
                produced_by_action_id="run-plan-detail-checks",
                command="python .flowguard/plan_detailing/run_checks.py",
            ),
        ),
        validation_requirements=(
            ValidationRequirement(
                "existing-owner-preflight-current",
                required_artifact_ids=(
                    "openspec.template-pack-work-package",
                    "flowguard.existing-owner-preflight",
                ),
                required_evidence_kinds=("existing_model_preflight",),
                evidence_ids=("existing-owner-preflight-pass",),
                v_model_pair=True,
                command="python .flowguard/existing_model_preflight/run_checks.py",
            ),
            ValidationRequirement(
                "programme-plan-current",
                required_artifact_ids=(
                    "openspec.template-pack-work-package",
                    "flowguard.programme-plan",
                ),
                required_evidence_kinds=("plan_detail",),
                evidence_ids=("programme-plan-pass",),
                v_model_pair=True,
                command="python .flowguard/plan_detailing/run_checks.py",
            ),
        ),
        freshness_rules=(
            FreshnessRule(
                "openspec-change-invalidates-planning-models",
                upstream_artifact_id="openspec.template-pack-work-package",
                invalidates_artifact_ids=(
                    "flowguard.existing-owner-preflight",
                    "flowguard.programme-plan",
                ),
            ),
        ),
        decision_scope="routine",
    )


def stale_broad_claim_plan() -> DevelopmentProcessPlan:
    """A known-bad variant: obligations change after evidence, then release is claimed."""

    return DevelopmentProcessPlan(
        "validated-template-pack-stale-broad-claim",
        artifacts=planning_artifacts(specification_version="2"),
        actions=(
            ProcessAction(
                "run-old-owner-preflight",
                produced_evidence_ids=("old-preflight-pass",),
            ),
            ProcessAction(
                "change-template-pack-obligations",
                writes_artifacts=("openspec.template-pack-work-package",),
                order_after=("run-old-owner-preflight",),
            ),
            ProcessAction(
                "claim-release-from-planning-only",
                action_type="claim_release",
                required_validation_ids=("old-preflight-current",),
                order_after=("change-template-pack-obligations",),
                decision_scope=PROCESS_SCOPE_RELEASE,
            ),
        ),
        evidence=(
            ProcessEvidence(
                "old-preflight-pass",
                evidence_kind="existing_model_preflight",
                status=PROCESS_EVIDENCE_PASSED,
                covers_artifacts=("openspec.template-pack-work-package",),
                covered_versions={"openspec.template-pack-work-package": "1"},
                validation_requirement_ids=("old-preflight-current",),
                produced_by_action_id="run-old-owner-preflight",
            ),
        ),
        validation_requirements=(
            ValidationRequirement(
                "old-preflight-current",
                required_artifact_ids=("openspec.template-pack-work-package",),
                required_evidence_kinds=("existing_model_preflight",),
                evidence_ids=("old-preflight-pass",),
                v_model_pair=True,
            ),
        ),
        freshness_rules=(
            FreshnessRule(
                "openspec-change-invalidates-all-planning-evidence",
                upstream_artifact_id="openspec.template-pack-work-package",
                invalidates_artifact_ids=(
                    "flowguard.existing-owner-preflight",
                    "flowguard.programme-plan",
                ),
            ),
        ),
        decision_scope=PROCESS_SCOPE_RELEASE,
    )


def run_checks():
    return (
        review_development_process_flow(current_planning_plan()),
        review_development_process_flow(stale_broad_claim_plan()),
    )
