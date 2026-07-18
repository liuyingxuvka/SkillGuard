"""Behavior Commitment Ledger for component-scoped validation composition."""

from __future__ import annotations

from flowguard import (
    BCL_ACTOR_AUTOMATION,
    BCL_CHANGE_ADD_BEHAVIOR,
    BCL_COMMITMENT_PROCESS,
    BCL_PLANE_DEVELOPMENT_PROCESS,
    BCL_SCOPE_ROUTINE,
    BCL_SOURCE_CODE,
    BCL_SOURCE_OPENSPEC,
    BCL_SOURCE_TEST,
    BehaviorCommitment,
    BehaviorCommitmentLedger,
    BehaviorSourceSurface,
)

from validation_composition_model import MODEL_ID, MODEL_PATH, PARENT_MODEL_ID


SPEC_PATH = (
    "openspec/changes/separate-skillguard-authoring-from-consumer-runtime/specs/"
    "composable-validation-evidence/spec.md"
)
RUNNER_PATH = ".flowguard/validation_composition/run_checks.py"


COMMITMENT_ROWS = (
    (
        "commitment:content-impact-graph-is-authoritative",
        "intent:content-impact-graph-is-authoritative",
        "maintained SkillGuard content or a validation declaration changes",
        "the compiler assigns every maintained file one semantic role, one installation disposition, and an exact consumer set, then proves owner uniqueness and dependency acyclicity",
        "unmapped, ambiguous, duplicate-owner, invalid-edge, or cyclic rows block before any validation owner starts and never broaden to full",
        ("impact_graph_status", "impact_graph_hash", "impact_graph_gaps"),
    ),
    (
        "commitment:affected-plan-is-minimal",
        "intent:affected-plan-is-minimal",
        "a healthy impact graph is compared with the frozen baseline and current receipt heads",
        "one side-effect-free plan names exactly which owners reuse, execute, aggregate, install, refresh router state, or invalidate Portfolio targets; the public runner consumes that exact plan and resolves only its execute partition",
        "an unrelated component, parent declaration, consumer coverage declaration, report, receipt, log, or checkbox cannot invalidate an owner outside its graph edges",
        (
            "plan_hash",
            "selected_owner_ids",
            "will_reuse_owner_ids",
            "will_execute_owner_ids",
            "will_aggregate_only",
            "required_install_component_ids",
            "required_router_refresh",
            "required_portfolio_target_ids",
        ),
    ),
    (
        "commitment:owner-receipts-cross-runs",
        "intent:owner-receipts-cross-runs",
        "a selected owner is requested in a new run",
        "its execution key binds only the complete behavior declaration, exact input projection, dependency receipts, target inputs, toolchain, environment, domain, and impact policy; a current terminal-success receipt suppresses execution across runs",
        "run, step, attempt, parent, whole-contract, whole-manifest, and whole-inventory metadata never enter the owner key; incomplete or tampered stdout, stderr, result, or termination sidecars are rejected",
        ("owner_execution_keys", "owner_receipt_ids", "receipt_rejection_reasons"),
    ),
    (
        "commitment:parent-aggregation-is-one-way",
        "intent:parent-aggregation-is-one-way",
        "all selected receipts owned by one maintenance unit are current or newly executed",
        "the same-unit parent binds that unit's immutable receipt set, selection, and declaration into its own aggregation identity without copying, rewriting, or re-signing children",
        "another maintenance unit or an external provider cannot consume the aggregation; a same-unit parent/profile/coverage-only change produces aggregation-only work and zero owner executions",
        ("parent_consumed_receipt_ids", "aggregation_identity", "child_receipt_rewritten"),
    ),
    (
        "commitment:install-portfolio-router-share-plan",
        "intent:install-portfolio-router-share-plan",
        "author validation, consumer distribution, Portfolio summary, or private maintainer-prompt maintenance is requested",
        "each author-side subsystem consumes the same frozen impact graph and its exact projection without turning that graph into consumer runtime state",
        "source-only tests do not enter the consumer distribution, unrelated maintenance units remain current, and the private router refreshes only for components on its exact author projection edge",
        (
            "required_install_component_ids",
            "required_portfolio_target_ids",
            "required_router_refresh",
        ),
    ),
    (
        "commitment:full-admission-is-derived",
        "intent:full-admission-is-derived",
        "a final, release, impact-policy, shared-runtime, or all-owner component gate requests full validation",
        "the frozen plan records one allowlisted reason, source and toolchain fixpoint, and exactly one full execution owner before the full parent may start",
        "installation happened, fixture changed, parent manifest changed, uncertainty, or insurance are not full reasons",
        ("full_admitted", "full_admission_reason_codes", "plan_hash"),
    ),
    (
        "commitment:evidence-domains-and-consumers-remain-separated",
        "intent:evidence-domains-and-consumers-remain-separated",
        "author evidence moves through one maintenance unit's source, checks, aggregation, and consumer-distribution gate",
        "the maintenance unit owns its own current receipts while graduated consumers and external providers carry no SkillGuard receipt reference",
        "OpenSpec, another maintenance unit, and a graduated consumer cannot copy, wrap, replay, resume, repair, backfill, or transport owner receipts; resume remains an author-side execution command",
        ("domain_status", "missing_domain_ids", "closure_status"),
    ),
    (
        "commitment:execution-lifecycle-is-controlled",
        "intent:execution-lifecycle-is-controlled",
        "a frozen TestMesh plan is handed to the public owner runner, or an owner process is started, interrupted, timed out, cancelled, or considered for unattended retry",
        "the runner verifies planned reuse read-only and sends only will_execute owners to the existing single-flight authority; only terminal success with complete sidecars enters the persistent success head, and interrupted launchers prove zero descendants before another owner starts",
        "failed attempts, cleanup-unconfirmed state, Scheduled Tasks, background resume, and unattended mutable-worktree retry cannot become reusable evidence",
        ("execution_status", "executed_owner_ids", "interrupted_launcher_cleanup_confirmed_zero"),
    ),
)


def build_behavior_commitment_ledger() -> BehaviorCommitmentLedger:
    commitment_ids = tuple(row[0] for row in COMMITMENT_ROWS)
    intent_ids = tuple(row[1] for row in COMMITMENT_ROWS)
    source_ids = (
        "surface:validation-composition-spec",
        "surface:validation-composition-model",
        "surface:validation-composition-checks",
    )
    commitments = tuple(
        BehaviorCommitment(
            commitment_id,
            business_intent_id=intent_id,
            label=commitment_id.removeprefix("commitment:").replace("-", " "),
            commitment_kind=BCL_COMMITMENT_PROCESS,
            behavior_plane=BCL_PLANE_DEVELOPMENT_PROCESS,
            actor_kind=BCL_ACTOR_AUTOMATION,
            actor="SkillGuard validation composer",
            trigger=trigger,
            expected_result=result,
            expected_terminal=result,
            failure_boundary=failure,
            state_writes=state_writes,
            source_surface_ids=source_ids,
            primary_owner_model_id=MODEL_ID,
            supporting_model_ids=(PARENT_MODEL_ID,),
            owner=MODEL_ID,
            validation_boundary="executable scenarios, contracts, refinement, TestMesh, ModelMesh, field lifecycle, and process flow",
            rationale="the existing child owns validation composition while concrete executors and downstream consumers retain their typed boundaries",
        )
        for commitment_id, intent_id, trigger, result, failure, state_writes in COMMITMENT_ROWS
    )
    surfaces = (
        BehaviorSourceSurface(
            source_ids[0],
            surface_kind=BCL_SOURCE_OPENSPEC,
            source_ref=SPEC_PATH,
            commitment_ids=commitment_ids,
            business_intent_ids=intent_ids,
            owner=MODEL_ID,
            validation_boundary="approved component-scoped validation requirements",
            rationale="the existing OpenSpec change declares the maintained process commitments",
        ),
        BehaviorSourceSurface(
            source_ids[1],
            surface_kind=BCL_SOURCE_CODE,
            source_ref=MODEL_PATH,
            commitment_ids=commitment_ids,
            business_intent_ids=intent_ids,
            owner=MODEL_ID,
            validation_boundary="finite executable FunctionBlocks and invariants",
            rationale="the existing validation-composition model remains the single abstract owner",
        ),
        BehaviorSourceSurface(
            source_ids[2],
            surface_kind=BCL_SOURCE_TEST,
            source_ref=RUNNER_PATH,
            commitment_ids=commitment_ids,
            business_intent_ids=intent_ids,
            owner=MODEL_ID,
            validation_boundary="normal and adversarial executable model review",
            rationale="the unified runner consumes all model reports without replacing production tests",
        ),
    )
    return BehaviorCommitmentLedger(
        "skillguard-validation-composition-ledger",
        project_boundary="SkillGuard component-scoped validation evidence composition beneath the existing portable semantic parent",
        current_revision="compose-validation-evidence-component-impact-current",
        commitments=commitments,
        source_surfaces=surfaces,
        expected_commitment_ids=commitment_ids,
        expected_business_intent_ids=intent_ids,
        claim_scope=BCL_SCOPE_ROUTINE,
        change_mode=BCL_CHANGE_ADD_BEHAVIOR,
        require_current_evidence=False,
        owner=MODEL_ID,
        validation_boundary="design-stage executable evidence only; production receipts remain separately required",
        rationale="upgrade the existing process promises without a second validation framework",
    )
