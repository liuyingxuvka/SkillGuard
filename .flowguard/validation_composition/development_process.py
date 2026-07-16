"""DevelopmentProcessFlow for component-scoped validation and projections."""

from __future__ import annotations

from dataclasses import replace

from flowguard import (
    BCL_PLANE_DEVELOPMENT_PROCESS,
    PROCESS_ARTIFACT_CODE,
    PROCESS_ARTIFACT_DESIGN,
    PROCESS_ARTIFACT_FIELD_LIFECYCLE,
    PROCESS_ARTIFACT_MODEL,
    PROCESS_ARTIFACT_RELEASE,
    PROCESS_ARTIFACT_REPORT,
    PROCESS_ARTIFACT_REQUIREMENT,
    PROCESS_ARTIFACT_TEST,
    DevelopmentProcessPlan,
    FreshnessRule,
    ProcessAction,
    ProcessArtifact,
)


def build_development_process() -> DevelopmentProcessPlan:
    artifacts = (
        ProcessArtifact(
            "openspec.validation-composition",
            PROCESS_ARTIFACT_REQUIREMENT,
            "component-impact-current",
            path="openspec/changes/compose-validation-evidence",
            owner="openspec",
        ),
        ProcessArtifact(
            "design.validation-composition",
            PROCESS_ARTIFACT_DESIGN,
            "component-impact-current",
            path="openspec/changes/compose-validation-evidence/design.md",
            owner="openspec",
            upstream_artifact_ids=("openspec.validation-composition",),
        ),
        ProcessArtifact(
            "model.validation-composition",
            PROCESS_ARTIFACT_MODEL,
            "component-impact-current",
            path=".flowguard/validation_composition/validation_composition_model.py",
            owner="model-first-function-flow",
            upstream_artifact_ids=("design.validation-composition",),
        ),
        ProcessArtifact(
            "model.validation-fields",
            PROCESS_ARTIFACT_FIELD_LIFECYCLE,
            "component-impact-current",
            path=".flowguard/validation_composition/field_lifecycle_model.py",
            owner="field_lifecycle_mesh",
            upstream_artifact_ids=("design.validation-composition",),
        ),
        ProcessArtifact(
            "code.impact-compiler",
            PROCESS_ARTIFACT_CODE,
            "planned",
            owner="skillguard-contract-compiler",
            upstream_artifact_ids=("model.validation-composition", "model.validation-fields"),
        ),
        ProcessArtifact(
            "report.impact-graph-health",
            PROCESS_ARTIFACT_REPORT,
            "not-run",
            owner="skillguard-contract-compiler",
            upstream_artifact_ids=("code.impact-compiler",),
        ),
        ProcessArtifact(
            "report.affected-plan",
            PROCESS_ARTIFACT_REPORT,
            "not-run",
            owner="skillguard-testmesh-planner",
            upstream_artifact_ids=("report.impact-graph-health",),
        ),
        ProcessArtifact(
            "component.runtime",
            PROCESS_ARTIFACT_CODE,
            "current",
            owner="owner.runtime",
            upstream_artifact_ids=("report.impact-graph-health",),
        ),
        ProcessArtifact(
            "component.tests",
            PROCESS_ARTIFACT_TEST,
            "current",
            owner="owner.tests",
            upstream_artifact_ids=("report.impact-graph-health",),
        ),
        ProcessArtifact(
            "component.prompt-router",
            PROCESS_ARTIFACT_CODE,
            "current",
            owner="owner.router",
            upstream_artifact_ids=("report.impact-graph-health",),
        ),
        ProcessArtifact(
            "receipt.owner-runtime",
            PROCESS_ARTIFACT_REPORT,
            "not-run",
            owner="owner.runtime",
            upstream_artifact_ids=("component.runtime", "report.affected-plan"),
        ),
        ProcessArtifact(
            "receipt.owner-tests",
            PROCESS_ARTIFACT_REPORT,
            "not-run",
            owner="owner.tests",
            upstream_artifact_ids=("component.tests", "report.affected-plan"),
        ),
        ProcessArtifact(
            "receipt.owner-router",
            PROCESS_ARTIFACT_REPORT,
            "not-run",
            owner="owner.router",
            upstream_artifact_ids=("component.prompt-router", "report.affected-plan"),
        ),
        ProcessArtifact(
            "report.parent-aggregation",
            PROCESS_ARTIFACT_REPORT,
            "not-run",
            owner="skillguard-testmesh-aggregator",
            upstream_artifact_ids=(
                "receipt.owner-runtime",
                "receipt.owner-tests",
                "receipt.owner-router",
                "report.affected-plan",
            ),
        ),
        ProcessArtifact(
            "release.installation-projection",
            PROCESS_ARTIFACT_RELEASE,
            "not-run",
            owner="skillguard-installer",
            upstream_artifact_ids=("report.affected-plan",),
        ),
        ProcessArtifact(
            "report.portfolio-projection",
            PROCESS_ARTIFACT_REPORT,
            "not-run",
            owner="skillguard-portfolio",
            upstream_artifact_ids=("report.affected-plan",),
        ),
        ProcessArtifact(
            "report.router-projection",
            PROCESS_ARTIFACT_REPORT,
            "not-run",
            owner="skillguard-global-router",
            upstream_artifact_ids=("report.affected-plan",),
        ),
        ProcessArtifact(
            "report.full-parent",
            PROCESS_ARTIFACT_REPORT,
            "not-run",
            owner="skillguard-final-full-owner",
            upstream_artifact_ids=(
                "report.parent-aggregation",
                "release.installation-projection",
                "report.router-projection",
            ),
        ),
        ProcessArtifact(
            "report.openspec-consumption",
            PROCESS_ARTIFACT_REPORT,
            "not-run",
            owner="openspec",
            upstream_artifact_ids=("report.full-parent",),
        ),
    )
    actions = (
        ProcessAction(
            "freeze-requirement-decision",
            writes_artifacts=("openspec.validation-composition", "design.validation-composition"),
            status="done",
            behavior_plane=BCL_PLANE_DEVELOPMENT_PROCESS,
        ),
        ProcessAction(
            "extend-existing-flowguard-model",
            reads_artifacts=("design.validation-composition",),
            writes_artifacts=("model.validation-composition", "model.validation-fields"),
            order_after=("freeze-requirement-decision",),
            status="done",
            behavior_plane=BCL_PLANE_DEVELOPMENT_PROCESS,
        ),
        ProcessAction(
            "compile-content-impact-graph",
            reads_artifacts=("model.validation-composition", "model.validation-fields"),
            writes_artifacts=("code.impact-compiler", "report.impact-graph-health"),
            order_after=("extend-existing-flowguard-model",),
            status="planned",
            behavior_plane=BCL_PLANE_DEVELOPMENT_PROCESS,
        ),
        ProcessAction(
            "derive-plan-only-preview",
            reads_artifacts=("report.impact-graph-health",),
            writes_artifacts=("report.affected-plan",),
            order_after=("compile-content-impact-graph",),
            status="planned",
            behavior_plane=BCL_PLANE_DEVELOPMENT_PROCESS,
        ),
        ProcessAction(
            "freeze-plan-source-toolchain",
            reads_artifacts=("report.affected-plan",),
            writes_artifacts=("report.affected-plan",),
            order_after=("derive-plan-only-preview",),
            status="planned",
            behavior_plane=BCL_PLANE_DEVELOPMENT_PROCESS,
        ),
        ProcessAction(
            "resolve-owner-receipts",
            reads_artifacts=("report.affected-plan", "component.runtime", "component.tests", "component.prompt-router"),
            writes_artifacts=("receipt.owner-runtime", "receipt.owner-tests", "receipt.owner-router"),
            order_after=("freeze-plan-source-toolchain",),
            status="planned",
            behavior_plane=BCL_PLANE_DEVELOPMENT_PROCESS,
        ),
        ProcessAction(
            "execute-only-stale-owners",
            reads_artifacts=("report.affected-plan", "receipt.owner-runtime", "receipt.owner-tests", "receipt.owner-router"),
            writes_artifacts=("receipt.owner-runtime", "receipt.owner-tests", "receipt.owner-router"),
            order_after=("resolve-owner-receipts",),
            status="planned",
            behavior_plane=BCL_PLANE_DEVELOPMENT_PROCESS,
        ),
        ProcessAction(
            "aggregate-immutable-owner-receipts",
            reads_artifacts=("report.affected-plan", "receipt.owner-runtime", "receipt.owner-tests", "receipt.owner-router"),
            writes_artifacts=("report.parent-aggregation",),
            order_after=("execute-only-stale-owners",),
            status="planned",
            behavior_plane=BCL_PLANE_DEVELOPMENT_PROCESS,
        ),
        ProcessAction(
            "install-affected-components",
            reads_artifacts=("report.affected-plan", "report.parent-aggregation"),
            writes_artifacts=("release.installation-projection",),
            order_after=("aggregate-immutable-owner-receipts",),
            status="planned",
            behavior_plane=BCL_PLANE_DEVELOPMENT_PROCESS,
        ),
        ProcessAction(
            "project-exact-portfolio-targets",
            reads_artifacts=("report.affected-plan",),
            writes_artifacts=("report.portfolio-projection",),
            order_after=("aggregate-immutable-owner-receipts",),
            status="planned",
            behavior_plane=BCL_PLANE_DEVELOPMENT_PROCESS,
        ),
        ProcessAction(
            "refresh-router-only-when-required",
            reads_artifacts=("report.affected-plan", "release.installation-projection"),
            writes_artifacts=("report.router-projection",),
            order_after=("install-affected-components",),
            status="planned",
            behavior_plane=BCL_PLANE_DEVELOPMENT_PROCESS,
        ),
        ProcessAction(
            "run-one-admitted-full-parent",
            reads_artifacts=("report.affected-plan", "report.parent-aggregation", "release.installation-projection", "report.router-projection"),
            writes_artifacts=("report.full-parent",),
            order_after=("refresh-router-only-when-required", "project-exact-portfolio-targets"),
            status="planned",
            behavior_plane=BCL_PLANE_DEVELOPMENT_PROCESS,
        ),
        ProcessAction(
            "consume-final-parent-read-only",
            reads_artifacts=("report.full-parent",),
            writes_artifacts=("report.openspec-consumption",),
            order_after=("run-one-admitted-full-parent",),
            status="planned",
            behavior_plane=BCL_PLANE_DEVELOPMENT_PROCESS,
        ),
    )
    return DevelopmentProcessPlan(
        "skillguard-component-impact-validation-lifecycle",
        artifacts=artifacts,
        actions=actions,
        freshness_rules=(
            FreshnessRule(
                "requirements-stale-model-and-impact-plan",
                "openspec.validation-composition",
                invalidates_artifact_ids=("design.validation-composition", "model.validation-composition", "model.validation-fields", "report.impact-graph-health", "report.affected-plan"),
                description="requirement changes rebuild the model and graph; the graph then derives exact owner effects",
            ),
            FreshnessRule(
                "impact-graph-stales-plan-and-aggregation",
                "report.impact-graph-health",
                invalidates_artifact_ids=("report.affected-plan", "report.parent-aggregation"),
            ),
            FreshnessRule(
                "runtime-component-stales-runtime-owner-and-install",
                "component.runtime",
                invalidates_artifact_ids=("receipt.owner-runtime", "report.parent-aggregation", "release.installation-projection"),
            ),
            FreshnessRule(
                "test-component-stales-test-owner-only",
                "component.tests",
                invalidates_artifact_ids=("receipt.owner-tests", "report.parent-aggregation"),
                description="test source is source-only and cannot invalidate installation",
            ),
            FreshnessRule(
                "prompt-component-stales-router-owner-and-projection",
                "component.prompt-router",
                invalidates_artifact_ids=("receipt.owner-router", "report.parent-aggregation", "report.router-projection"),
            ),
            FreshnessRule(
                "parent-declaration-stales-aggregation-only",
                "report.parent-aggregation",
                invalidates_artifact_ids=("report.full-parent", "report.openspec-consumption"),
                description="parent changes do not reverse-invalidate child owner receipts",
            ),
            FreshnessRule(
                "installation-projection-stales-only-install-bound-parent",
                "release.installation-projection",
                invalidates_artifact_ids=("report.full-parent",),
            ),
            FreshnessRule(
                "router-projection-stales-only-prompt-bound-parent",
                "report.router-projection",
                invalidates_artifact_ids=("report.full-parent",),
            ),
        ),
        decision_scope="enforced",
        require_proof_artifacts=False,
        behavior_plane=BCL_PLANE_DEVELOPMENT_PROCESS,
        require_behavior_plane_boundary=True,
    )


def build_bad_out_of_order_process() -> DevelopmentProcessPlan:
    plan = build_development_process()
    by_id = {action.action_id: action for action in plan.actions}
    by_id["execute-only-stale-owners"] = replace(
        by_id["execute-only-stale-owners"],
        order_after=("missing-frozen-plan",),
    )
    return replace(
        plan,
        process_id="skillguard-component-impact-bad-order",
        actions=tuple(by_id[action.action_id] for action in plan.actions),
    )
