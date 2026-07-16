"""Portable owner model for the SkillGuard executable-contract runtime.

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard

Purpose:
    Model the behavior boundary that turns a target skill contract into a
    claimed, resumable, verifier-owned run and closes it only from current,
    exact evidence.

Guards against:
    prose-only behavior authority, untyped or duplicate routes, unclaimed
    tasks, caller-authored pass, illegal required skips, stale artifacts,
    chat-memory resume, permanent failed/crashed writer locks, no-progress loops, stale child receipts, hidden
    failures, former-authority alternate success paths, and stale portfolio graduates.

Run from an installed SkillGuard root:
    python .skillguard/flowguard_contract_model.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import flowguard as _flowguard

from flowguard import (
    BCL_ACTOR_AI_AGENT,
    BCL_CHANGE_BOOTSTRAP_LEDGER,
    BCL_COMMITMENT_PROCESS,
    BCL_COMMITMENT_WORKFLOW,
    BCL_SCOPE_ROUTINE,
    BCL_PLANE_AGENT_OPERATION,
    BCL_SOURCE_CODE,
    BCL_SOURCE_OPENSPEC,
    BCL_SOURCE_TEST,
    BehaviorCommitment,
    BehaviorCommitmentLedger,
    BehaviorPathAuthorityBinding,
    BehaviorSourceSurface,
    CodeContract,
    ContractDimension,
    ContractExhaustionPlan,
    ContractMutationCase,
    ContractOracle,
    FunctionResult,
    Invariant,
    InvariantResult,
    ModelObligation,
    ModelTestAlignmentPlan,
    PPA_CLAIM_SCOPE_ROUTINE,
    PrimaryPathAuthorityPlan,
    PrimaryPathContract,
    Scenario,
    ScenarioExpectation,
    TestEvidence,
    TestMeshPlan,
    TestPartitionItem,
    TestSuiteEvidence,
    TestTargetSplitDerivation,
    Workflow,
    review_behavior_commitment_ledger,
    review_contract_exhaustion,
    review_model_test_alignment,
    review_primary_path_authority,
    review_test_mesh,
)
from flowguard.review import review_scenarios


MODEL_ID = "skillguard.executable_contract_runtime.v2"
MODEL_PATH = ".skillguard/flowguard_contract_model.py"
TEST_PATH = "tests/test_executable_contract_model.py"
PARENT_MODEL_ID = "skillguard.runtime_contract_executor.v1"
FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"


@dataclass(frozen=True)
class ExecutableContractCase:
    """One externally visible contract-run shape to project into state."""

    case_name: str
    model_current: bool = True
    binding_current: bool = True
    model_authority_read_side_effect_free: bool = True
    route_owner_unique: bool = True
    route_typed: bool = True
    packet_fields_consumed: bool = True
    guard_runtime_changed: bool = False
    guard_compatible_run_claimed: bool = True
    run_claimed: bool = True
    writer_lock_owned: bool = True
    failed_or_dead_writer_lock_recoverable: bool = True
    required_steps_passed: bool = True
    caller_authored_pass: bool = False
    illegal_required_skip: bool = False
    artifacts_current: bool = True
    checks_current: bool = True
    resume_from_events: bool = True
    progress_changed: bool = True
    reentry_count: int = 0
    max_reentries: int = 3
    parent_receipts_current: bool = True
    failure_visible: bool = True
    former_authority_residual: bool = False
    closure_requested: bool = True
    enforced_closure_exact: bool = True
    safe_claim_scoped: bool = True
    graduated_children_current: bool = True
    depth_profile_present: bool = True
    depth_profile_target_neutral: bool = True
    native_route_preserved: bool = True
    parallel_domain_executor: bool = False
    unique_evidence_contribution: bool = True
    execution_depth_status: str = "EXECUTION_DEPTH_PASS"
    depth_receipt_current: bool = True
    depth_receipt_consumed: bool = True
    enforcement_level: str = "enforced"
    declared_check_inventory_frozen: bool = True
    declared_check_results_complete: bool = True
    declared_check_receipts_current: bool = True
    provider_runtime_current: bool = True
    root_role_binding_current: bool = True
    repository_root_supplied: bool = True
    target_root_supplied: bool = True
    canonical_repository_root_bound: bool = True
    member_root_bound: bool = True
    member_within_repository: bool = True
    member_binding_fallback_used: bool = False
    repository_relative_reference_fallback_used: bool = False
    standalone_member_root_path_current: bool = True
    project_adoption_current: bool = True


@dataclass(frozen=True)
class ExecutableContractState:
    """State owned by the executable-contract parent model."""

    case_name: str = ""
    model_current: bool = False
    binding_current: bool = False
    model_authority_read_side_effect_free: bool = False
    route_owner_unique: bool = False
    route_typed: bool = False
    packet_fields_consumed: bool = False
    guard_runtime_changed: bool = False
    guard_compatible_run_claimed: bool = False
    run_claimed: bool = False
    writer_lock_owned: bool = False
    failed_or_dead_writer_lock_recoverable: bool = False
    required_steps_passed: bool = False
    caller_authored_pass: bool = False
    illegal_required_skip: bool = False
    artifacts_current: bool = False
    checks_current: bool = False
    resume_from_events: bool = False
    progress_changed: bool = False
    reentry_count: int = 0
    max_reentries: int = 0
    parent_receipts_current: bool = False
    failure_visible: bool = False
    former_authority_residual: bool = False
    closure_requested: bool = False
    enforced_closure_exact: bool = False
    safe_claim_scoped: bool = False
    graduated_children_current: bool = False
    depth_profile_present: bool = False
    depth_profile_target_neutral: bool = False
    native_route_preserved: bool = False
    parallel_domain_executor: bool = False
    unique_evidence_contribution: bool = False
    execution_depth_status: str = "NOT_RUN"
    depth_receipt_current: bool = False
    depth_receipt_consumed: bool = False
    enforcement_level: str = "unmanaged"
    declared_check_inventory_frozen: bool = False
    declared_check_results_complete: bool = False
    declared_check_receipts_current: bool = False
    provider_runtime_current: bool = False
    root_role_binding_current: bool = False
    repository_root_supplied: bool = False
    target_root_supplied: bool = False
    canonical_repository_root_bound: bool = False
    member_root_bound: bool = False
    member_within_repository: bool = False
    member_binding_fallback_used: bool = False
    repository_relative_reference_fallback_used: bool = False
    standalone_member_root_path_current: bool = False
    project_adoption_current: bool = False


class EvaluateExecutableContract:
    """Input x State -> Set(Output x State) for one contract-run case."""

    name = "EvaluateExecutableContract"
    reads = ("ExecutableContractState",)
    writes = tuple(ExecutableContractState.__dataclass_fields__)
    accepted_input_type = ExecutableContractCase
    input_description = "one SkillGuard executable-contract run case"
    output_description = "projected executable-contract state"
    idempotency = "the same immutable case projects the same state"

    def apply(
        self,
        input_obj: ExecutableContractCase,
        _state: ExecutableContractState,
    ) -> tuple[FunctionResult, ...]:
        new_state = ExecutableContractState(**input_obj.__dict__)
        return (
            FunctionResult(
                output=input_obj,
                new_state=new_state,
                label=input_obj.case_name,
                reason="projected the declared contract-run case into owned state",
            ),
        )


def _pass() -> InvariantResult:
    return InvariantResult.pass_()


def _fail(name: str, message: str) -> InvariantResult:
    return InvariantResult.fail(message, {"violation": name})


def _empty(state: ExecutableContractState) -> bool:
    return not state.case_name


def model_and_binding_are_authoritative(state: ExecutableContractState, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if (
        not state.model_current
        or not state.binding_current
        or not state.model_authority_read_side_effect_free
    ):
        return _fail(
            "model_and_binding_are_authoritative",
            "release behavior requires a current FlowGuard model, a matching target binding, and a side-effect-free authority read",
        )
    return _pass()


def routes_are_typed_and_uniquely_owned(state: ExecutableContractState, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.route_typed or not state.route_owner_unique:
        return _fail(
            "routes_are_typed_and_uniquely_owned",
            "every selected route needs a typed handoff and one canonical owner",
        )
    return _pass()


def packet_fields_are_declared_and_consumed(
    state: ExecutableContractState,
    _trace: object,
) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.packet_fields_consumed:
        return _fail(
            "packet_fields_are_declared_and_consumed",
            "every supervisor packet field must be declared, route-reachable, and consumed",
        )
    return _pass()


def every_task_is_claimed_and_locked(state: ExecutableContractState, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.run_claimed or not state.writer_lock_owned:
        return _fail(
            "every_task_is_claimed_and_locked",
            "a supervised task cannot execute without a claimed run and target lock",
        )
    return _pass()


def failed_or_dead_writer_lock_cannot_block_forever(
    state: ExecutableContractState,
    _trace: object,
) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.failed_or_dead_writer_lock_recoverable:
        return _fail(
            "failed_or_dead_writer_lock_cannot_block_forever",
            "a failed or dead writer lock must be auditable and recoverable while a live writer remains protected",
        )
    return _pass()


def guard_change_claims_a_new_run(
    state: ExecutableContractState,
    _trace: object,
) -> InvariantResult:
    if _empty(state) or not state.guard_runtime_changed:
        return _pass()
    if not state.guard_compatible_run_claimed:
        return _fail(
            "guard_change_claims_a_new_run",
            "a changed Guard runtime must create a new run identity instead of reusing completed old events",
        )
    return _pass()


def pass_and_skip_are_verifier_owned(state: ExecutableContractState, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if state.caller_authored_pass:
        return _fail(
            "pass_and_skip_are_verifier_owned",
            "an AI evidence submission cannot directly author authoritative pass",
        )
    if state.illegal_required_skip:
        return _fail(
            "pass_and_skip_are_verifier_owned",
            "required steps cannot be skipped",
        )
    return _pass()


def artifacts_and_checks_are_current(state: ExecutableContractState, _trace: object) -> InvariantResult:
    if _empty(state) or not state.closure_requested:
        return _pass()
    if not state.required_steps_passed or not state.artifacts_current or not state.checks_current:
        return _fail(
            "artifacts_and_checks_are_current",
            "closure requires passed required steps plus current artifacts and checks",
        )
    return _pass()


def resume_uses_durable_events(state: ExecutableContractState, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.resume_from_events:
        return _fail(
            "resume_uses_durable_events",
            "resume must replay durable events and receipts instead of relying on chat memory",
        )
    return _pass()


def loops_require_progress_and_a_finite_bound(
    state: ExecutableContractState,
    _trace: object,
) -> InvariantResult:
    if _empty(state) or state.reentry_count == 0:
        return _pass()
    if not state.progress_changed:
        return _fail(
            "loops_require_progress_and_a_finite_bound",
            "a re-entered loop without declared progress must terminate blocked",
        )
    if state.max_reentries <= 0 or state.reentry_count > state.max_reentries:
        return _fail(
            "loops_require_progress_and_a_finite_bound",
            "a loop cannot exceed its finite re-entry bound",
        )
    return _pass()


def closure_consumes_current_exact_receipts(
    state: ExecutableContractState,
    _trace: object,
) -> InvariantResult:
    if _empty(state) or not state.closure_requested:
        return _pass()
    if not state.parent_receipts_current:
        return _fail(
            "closure_consumes_current_exact_receipts",
            "parent closure must consume current exact child receipts",
        )
    if not state.enforced_closure_exact:
        return _fail(
            "closure_consumes_current_exact_receipts",
            "the fixed enforced closure cannot be replaced, weakened, or duplicated",
        )
    if not state.safe_claim_scoped:
        return _fail(
            "closure_consumes_current_exact_receipts",
            "closure must return a scoped safe claim and preserve the unsafe boundary",
        )
    return _pass()


def failures_and_former_authority_cannot_hide(
    state: ExecutableContractState,
    _trace: object,
) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.failure_visible:
        return _fail(
            "failures_and_former_authority_cannot_hide",
            "failed, blocked, skipped, stale, and not-run results must remain visible",
        )
    if state.former_authority_residual:
        return _fail(
            "failures_and_former_authority_cannot_hide",
            "any former authority residual blocks the one current execution path",
        )
    return _pass()


def portfolio_children_remain_current(state: ExecutableContractState, _trace: object) -> InvariantResult:
    if _empty(state) or not state.closure_requested:
        return _pass()
    if not state.graduated_children_current:
        return _fail(
            "portfolio_children_remain_current",
            "portfolio graduation cannot hide a stale or revalidation-required prior skill",
        )
    return _pass()


def depth_profile_preserves_native_authority(
    state: ExecutableContractState,
    _trace: object,
) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.depth_profile_present or not state.depth_profile_target_neutral:
        return _fail(
            "depth_profile_preserves_native_authority",
            "a covered non-trivial skill needs a target-authored target-neutral depth profile",
        )
    if not state.native_route_preserved or state.parallel_domain_executor:
        return _fail(
            "depth_profile_preserves_native_authority",
            "SkillGuard must bind the target's native route and must not create a parallel domain executor",
        )
    return _pass()


def execution_depth_is_current_and_consumed(
    state: ExecutableContractState,
    _trace: object,
) -> InvariantResult:
    if _empty(state) or not state.closure_requested:
        return _pass()
    if not state.depth_receipt_current or not state.depth_receipt_consumed:
        return _fail(
            "execution_depth_is_current_and_consumed",
            "closure must consume a current target-local execution-depth receipt",
        )
    if state.execution_depth_status != "EXECUTION_DEPTH_PASS":
        return _fail(
            "execution_depth_is_current_and_consumed",
            "broad closure requires EXECUTION_DEPTH_PASS; contract-only, partial, boundary, unavailable, not-run, unmanaged, or stale status cannot pass",
        )
    if not state.declared_check_inventory_frozen:
        return _fail(
            "execution_depth_is_current_and_consumed",
            "the target's exact declared-check inventory must be frozen before execution",
        )
    if not state.declared_check_results_complete:
        return _fail(
            "execution_depth_is_current_and_consumed",
            "every target-declared check must have exactly one terminal disposition",
        )
    if not state.declared_check_receipts_current:
        return _fail(
            "execution_depth_is_current_and_consumed",
            "every passing target-declared check must carry a current request-bound receipt",
        )
    if not state.provider_runtime_current:
        return _fail(
            "execution_depth_is_current_and_consumed",
            "the active provider runtime must implement the current depth contract",
        )
    if (
        not state.repository_root_supplied
        or not state.target_root_supplied
        or not state.root_role_binding_current
    ):
        return _fail(
            "execution_depth_is_current_and_consumed",
            "closure and replay must preserve distinct repository_root and target_root authority",
        )
    return _pass()


def evidence_contribution_is_unique(
    state: ExecutableContractState,
    _trace: object,
) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.unique_evidence_contribution:
        return _fail(
            "evidence_contribution_is_unique",
            "the same generic receipt cannot count repeatedly as independent proof for unrelated target obligations",
        )
    return _pass()


def external_target_binding_is_explicit(
    state: ExecutableContractState,
    _trace: object,
) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.canonical_repository_root_bound or not state.member_root_bound:
        return _fail(
            "external_target_binding_is_explicit",
            "target checks require one canonical repository root and one exact member root",
        )
    if not state.member_within_repository:
        return _fail(
            "external_target_binding_is_explicit",
            "the target member must remain inside its declared canonical repository root",
        )
    if state.member_binding_fallback_used:
        return _fail(
            "external_target_binding_is_explicit",
            "a failed repository/member binding cannot retry from another root",
        )
    if state.repository_relative_reference_fallback_used:
        return _fail(
            "external_target_binding_is_explicit",
            "a missing repository-relative reference cannot retry from the target member",
        )
    if not state.standalone_member_root_path_current:
        return _fail(
            "external_target_binding_is_explicit",
            "a standalone target must bind the same directory as repository and member with member_root_path '.'",
        )
    return _pass()


def adopted_projects_keep_skillguard_maintenance_visible(
    state: ExecutableContractState,
    _trace: object,
) -> InvariantResult:
    if _empty(state) or not state.closure_requested:
        return _pass()
    if not state.project_adoption_current:
        return _fail(
            "adopted_projects_keep_skillguard_maintenance_visible",
            "a maintained target repository needs a current marker-bounded SkillGuard project prompt and portable adoption record",
        )
    return _pass()


def static_audit_is_current(state: ExecutableContractState, trace: object) -> InvariantResult:
    """Self-host contract owner for current static-audit evidence."""

    return artifacts_and_checks_are_current(state, trace)


def deep_audit_is_target_specific(state: ExecutableContractState, trace: object) -> InvariantResult:
    """Self-host contract owner for target-specific deep-audit coverage."""

    return artifacts_and_checks_are_current(state, trace)


def global_router_handoff_is_current(state: ExecutableContractState, trace: object) -> InvariantResult:
    """Self-host contract owner for a typed, current global-router handoff."""

    return routes_are_typed_and_uniquely_owned(state, trace)


def provenance_is_non_downgrade(state: ExecutableContractState, trace: object) -> InvariantResult:
    """Self-host contract owner for canonical/install/repository provenance."""

    return model_and_binding_are_authoritative(state, trace)


INVARIANTS = (
    Invariant(
        "model_and_binding_are_authoritative",
        "FlowGuard model and target binding jointly own release behavior.",
        model_and_binding_are_authoritative,
    ),
    Invariant(
        "routes_are_typed_and_uniquely_owned",
        "Every route has a typed handoff and one owner.",
        routes_are_typed_and_uniquely_owned,
    ),
    Invariant(
        "packet_fields_are_declared_and_consumed",
        "Every supervisor packet field is declared, route-reachable, and consumed.",
        packet_fields_are_declared_and_consumed,
    ),
    Invariant(
        "every_task_is_claimed_and_locked",
        "Every supervised task is claimed and target-locked.",
        every_task_is_claimed_and_locked,
    ),
    Invariant(
        "failed_or_dead_writer_lock_cannot_block_forever",
        "Failed or dead writer locks are recovered with evidence without weakening live-writer exclusion.",
        failed_or_dead_writer_lock_cannot_block_forever,
    ),
    Invariant(
        "guard_change_claims_a_new_run",
        "A Guard compatibility change creates a fresh claimed-run identity.",
        guard_change_claims_a_new_run,
    ),
    Invariant(
        "pass_and_skip_are_verifier_owned",
        "Only verification derives pass or approves conditional skip.",
        pass_and_skip_are_verifier_owned,
    ),
    Invariant(
        "artifacts_and_checks_are_current",
        "Closure requires current target artifacts and exact checks.",
        artifacts_and_checks_are_current,
    ),
    Invariant(
        "resume_uses_durable_events",
        "Context recovery replays durable events and receipts.",
        resume_uses_durable_events,
    ),
    Invariant(
        "loops_require_progress_and_a_finite_bound",
        "Loops have a progress measure and finite re-entry bound.",
        loops_require_progress_and_a_finite_bound,
    ),
    Invariant(
        "closure_consumes_current_exact_receipts",
        "Closure consumes current exact receipts under a monotonic profile.",
        closure_consumes_current_exact_receipts,
    ),
    Invariant(
        "failures_and_former_authority_cannot_hide",
        "Failures stay visible and every former authority shape remains blocked.",
        failures_and_former_authority_cannot_hide,
    ),
    Invariant(
        "portfolio_children_remain_current",
        "Portfolio graduation consumes current prior-skill evidence.",
        portfolio_children_remain_current,
    ),
    Invariant(
        "depth_profile_preserves_native_authority",
        "Universal depth profiles stay target-neutral and preserve native domain authority.",
        depth_profile_preserves_native_authority,
    ),
    Invariant(
        "execution_depth_is_current_and_consumed",
        "Broad closure consumes a current passing target execution-depth receipt.",
        execution_depth_is_current_and_consumed,
    ),
    Invariant(
        "evidence_contribution_is_unique",
        "Unrelated obligations need independently attributable target evidence.",
        evidence_contribution_is_unique,
    ),
    Invariant(
        "external_target_binding_is_explicit",
        "External checks bind one canonical repository root and one contained member without fallback.",
        external_target_binding_is_explicit,
    ),
    Invariant(
        "adopted_projects_keep_skillguard_maintenance_visible",
        "Adopted repositories keep a current SkillGuard maintenance prompt and record.",
        adopted_projects_keep_skillguard_maintenance_visible,
    ),
)


def build_workflow() -> Workflow:
    return Workflow((EvaluateExecutableContract(),), name="skillguard_executable_contract_runtime")


def _ok(summary: str, label: str) -> ScenarioExpectation:
    return ScenarioExpectation(expected_status="ok", required_trace_labels=(label,), summary=summary)


def _violation(summary: str, *names: str) -> ScenarioExpectation:
    return ScenarioExpectation(
        expected_status="violation",
        expected_violation_names=names,
        summary=summary,
    )


def _scenario(
    name: str,
    description: str,
    case: ExecutableContractCase,
    expectation: ScenarioExpectation,
) -> Scenario:
    return Scenario(
        name=name,
        description=description,
        workflow=build_workflow(),
        initial_state=ExecutableContractState(),
        external_input_sequence=(case,),
        invariants=INVARIANTS,
        expected=expectation,
    )


GOOD_CASE = ExecutableContractCase("good_contract_run")

SCENARIOS = (
    _scenario("good_run_passes", "A fully evidenced run closes safely.", GOOD_CASE, _ok("good run", GOOD_CASE.case_name)),
    _scenario(
        "missing_model_blocks",
        "Prompt prose without a current FlowGuard model cannot compile for release.",
        ExecutableContractCase("missing_model", model_current=False),
        _violation("model missing", "model_and_binding_are_authoritative"),
    ),
    _scenario(
        "model_authority_read_side_effect_blocks",
        "Reading or supervising target authority cannot create bytecode or rewrite an installed projection.",
        ExecutableContractCase(
            "model_authority_read_side_effect",
            model_authority_read_side_effect_free=False,
        ),
        _violation("model read left mutable residue", "model_and_binding_are_authoritative"),
    ),
    _scenario(
        "untyped_route_blocks",
        "A bare or mistyped route handoff cannot execute.",
        ExecutableContractCase("untyped_route", route_typed=False),
        _violation("route untyped", "routes_are_typed_and_uniquely_owned"),
    ),
    _scenario(
        "unknown_packet_field_blocks",
        "A misspelled or unreachable packet field cannot be silently ignored.",
        ExecutableContractCase("unknown_packet_field", packet_fields_consumed=False),
        _violation("packet field unconsumed", "packet_fields_are_declared_and_consumed"),
    ),
    _scenario(
        "unclaimed_run_blocks",
        "Native-integrated work still requires a claimed run.",
        ExecutableContractCase("unclaimed_run", run_claimed=False),
        _violation("run unclaimed", "every_task_is_claimed_and_locked"),
    ),
    _scenario(
        "guard_change_same_run_blocks",
        "A changed Guard runtime cannot reuse a completed run identity and skip re-execution.",
        ExecutableContractCase(
            "guard_change_same_run",
            guard_runtime_changed=True,
            guard_compatible_run_claimed=False,
        ),
        _violation("guard-compatible run missing", "guard_change_claims_a_new_run"),
    ),
    _scenario(
        "conflicting_writer_blocks",
        "A writer without the target lock cannot continue.",
        ExecutableContractCase("conflicting_writer", writer_lock_owned=False),
        _violation("writer conflict", "every_task_is_claimed_and_locked"),
    ),
    _scenario(
        "stale_failed_writer_lock_blocks_progress",
        "A failed or dead prior writer cannot permanently prevent a new compatible claim.",
        ExecutableContractCase(
            "stale_failed_writer_lock",
            failed_or_dead_writer_lock_recoverable=False,
        ),
        _violation(
            "stale lock unrecoverable",
            "failed_or_dead_writer_lock_cannot_block_forever",
        ),
    ),
    _scenario(
        "caller_authored_pass_blocks",
        "An AI cannot set pass directly.",
        ExecutableContractCase("caller_authored_pass", caller_authored_pass=True),
        _violation("self pass", "pass_and_skip_are_verifier_owned"),
    ),
    _scenario(
        "required_skip_blocks",
        "A required step cannot be skipped.",
        ExecutableContractCase("required_skip", illegal_required_skip=True),
        _violation("required skip", "pass_and_skip_are_verifier_owned"),
    ),
    _scenario(
        "stale_artifact_blocks_closure",
        "An old or wrong-surface artifact cannot close a run.",
        ExecutableContractCase("stale_artifact", artifacts_current=False),
        _violation("artifact stale", "artifacts_and_checks_are_current"),
    ),
    _scenario(
        "resume_from_chat_memory_blocks",
        "Unrecorded chat memory cannot restore completion.",
        ExecutableContractCase("chat_memory_resume", resume_from_events=False),
        _violation("resume invalid", "resume_uses_durable_events"),
    ),
    _scenario(
        "no_progress_loop_blocks",
        "A repeated loop without evidence delta terminates blocked.",
        ExecutableContractCase("no_progress_loop", progress_changed=False, reentry_count=1),
        _violation("loop stuck", "loops_require_progress_and_a_finite_bound"),
    ),
    _scenario(
        "over_bound_loop_blocks",
        "A loop cannot exceed its declared re-entry budget.",
        ExecutableContractCase("over_bound_loop", reentry_count=4, max_reentries=3),
        _violation("loop bound", "loops_require_progress_and_a_finite_bound"),
    ),
    _scenario(
        "stale_child_blocks_parent",
        "A parent must reconsume a superseding child receipt.",
        ExecutableContractCase("stale_child", parent_receipts_current=False),
        _violation("child stale", "closure_consumes_current_exact_receipts"),
    ),
    _scenario(
        "hidden_failure_blocks",
        "A parent cannot hide a failed or skipped child.",
        ExecutableContractCase("hidden_failure", failure_visible=False),
        _violation("failure hidden", "failures_and_former_authority_cannot_hide"),
    ),
    _scenario(
        "former_authority_residual_blocks",
        "A former runtime surface cannot remain beside the current authority.",
        ExecutableContractCase(
            "former_authority_residual",
            former_authority_residual=True,
        ),
        _violation(
            "former authority residual",
            "failures_and_former_authority_cannot_hide",
        ),
    ),
    _scenario(
        "non_enforced_closure_blocks",
        "The fixed enforced closure cannot be replaced or weakened.",
        ExecutableContractCase("non_enforced_closure", enforced_closure_exact=False),
        _violation("closure is not exact", "closure_consumes_current_exact_receipts"),
    ),
    _scenario(
        "stale_prior_graduate_blocks",
        "The current target cannot graduate while a prior skill needs revalidation.",
        ExecutableContractCase("stale_prior_graduate", graduated_children_current=False),
        _violation("prior stale", "portfolio_children_remain_current"),
    ),
    _scenario(
        "parallel_domain_executor_blocks",
        "SkillGuard cannot duplicate a target's native domain route.",
        ExecutableContractCase("parallel_domain_executor", parallel_domain_executor=True),
        _violation("parallel domain executor", "depth_profile_preserves_native_authority"),
    ),
    _scenario(
        "contract_only_depth_blocks_closure",
        "A mapped depth contract is not current execution-depth evidence.",
        ExecutableContractCase("contract_only_depth", execution_depth_status="CONTRACT_DEPTH_PASS"),
        _violation("contract only", "execution_depth_is_current_and_consumed"),
    ),
    _scenario(
        "duplicate_generic_evidence_blocks",
        "Repeated generic checks cannot satisfy unrelated target obligations.",
        ExecutableContractCase("duplicate_generic_evidence", unique_evidence_contribution=False),
        _violation("duplicate evidence", "evidence_contribution_is_unique"),
    ),
    _scenario(
        "declared_check_inventory_not_frozen_blocks",
        "Execution cannot start before the exact target-declared check inventory is frozen.",
        ExecutableContractCase(
            "declared_check_inventory_not_frozen",
            declared_check_inventory_frozen=False,
        ),
        _violation("inventory not frozen", "execution_depth_is_current_and_consumed"),
    ),
    _scenario(
        "declared_check_missing_blocks",
        "Every target-declared check needs exactly one terminal result.",
        ExecutableContractCase(
            "declared_check_missing",
            declared_check_results_complete=False,
        ),
        _violation("declared check missing", "execution_depth_is_current_and_consumed"),
    ),
    _scenario(
        "declared_check_stale_blocks",
        "A stale or request-mismatched check receipt cannot support depth closure.",
        ExecutableContractCase(
            "declared_check_stale",
            declared_check_receipts_current=False,
        ),
        _violation("declared check stale", "execution_depth_is_current_and_consumed"),
    ),
    _scenario(
        "prompt_new_runtime_old_blocks",
        "A newer declared-check profile cannot supervise an older runtime without the required capabilities.",
        ExecutableContractCase(
            "prompt_new_runtime_old",
            provider_runtime_current=False,
        ),
        _violation("provider runtime stale", "execution_depth_is_current_and_consumed"),
    ),
    _scenario(
        "separate_repository_and_target_roots_collapsed_blocks",
        "Closure cannot collapse the maintained repository root and concrete task-data root.",
        ExecutableContractCase(
            "separate_repository_and_target_roots_collapsed",
            root_role_binding_current=False,
        ),
        _violation("root roles collapsed", "execution_depth_is_current_and_consumed"),
    ),
    _scenario(
        "external_repository_root_missing_blocks",
        "An external target cannot reinterpret its member directory as repository authority.",
        ExecutableContractCase(
            "external_repository_root_missing",
            canonical_repository_root_bound=False,
        ),
        _violation("canonical repository missing", "external_target_binding_is_explicit"),
    ),
    _scenario(
        "external_member_escape_blocks",
        "A target member outside the declared canonical repository root cannot be checked.",
        ExecutableContractCase(
            "external_member_escape",
            member_within_repository=False,
        ),
        _violation("member escaped", "external_target_binding_is_explicit"),
    ),
    _scenario(
        "external_binding_fallback_blocks",
        "A failed external binding cannot retry from the member or SkillGuard repository.",
        ExecutableContractCase(
            "external_binding_fallback",
            member_binding_fallback_used=True,
        ),
        _violation("binding fallback used", "external_target_binding_is_explicit"),
    ),
    _scenario(
        "external_reference_member_fallback_blocks",
        "A missing repository-relative reference cannot be replaced by a same-named member path.",
        ExecutableContractCase(
            "external_reference_member_fallback",
            repository_relative_reference_fallback_used=True,
        ),
        _violation("reference fallback used", "external_target_binding_is_explicit"),
    ),
    _scenario(
        "standalone_member_path_mismatch_blocks",
        "Standalone dot requires one shared repository/member root and portable member_root_path '.'.",
        ExecutableContractCase(
            "standalone_member_path_mismatch",
            standalone_member_root_path_current=False,
        ),
        _violation("standalone member path stale", "external_target_binding_is_explicit"),
    ),
    _scenario(
        "missing_project_adoption_blocks_maintenance_closure",
        "A maintained repository cannot hide a missing or stale SkillGuard project prompt.",
        ExecutableContractCase("missing_project_adoption", project_adoption_current=False),
        _violation("project adoption stale", "adopted_projects_keep_skillguard_maintenance_visible"),
    ),
)


def run_scenario_review():
    return review_scenarios(SCENARIOS)


def export_contract_model() -> dict[str, object]:
    """Return the canonical machine projection consumed by current SkillGuard.

    FlowGuard owns behavior, state, topology, terminal, invariant, and loop
    truth. Target-specific commands, tools, APIs, artifacts, and rubrics are
    intentionally absent and must come from the separate binding source.
    """

    functions = (
        {
            "function_id": "static_audit",
            "business_intent": "audit skill static boundary",
            "owner_id": "static-audit-v2",
            "route_ids": ["route:static-audit"],
            "composable_with": ["deep_audit", "compile_contract", "audit_provenance"],
        },
        {
            "function_id": "deep_audit",
            "business_intent": "audit skill functional depth",
            "owner_id": "deep-audit-v2",
            "route_ids": ["route:deep-audit"],
            "composable_with": ["static_audit", "compile_contract", "supervise_run"],
        },
        {
            "function_id": "compile_contract",
            "business_intent": "compile executable contract",
            "owner_id": "contract-compiler-v2",
            "route_ids": ["route:compile-contract"],
        },
        {
            "function_id": "supervise_run",
            "business_intent": "supervise target skill task",
            "owner_id": "run-runtime-v2",
            "route_ids": ["route:supervise-run"],
        },
        {
            "function_id": "verify_evidence",
            "business_intent": "verify target evidence",
            "owner_id": "evidence-runtime-v2",
            "route_ids": ["route:verify-evidence"],
        },
        {
            "function_id": "derive_closure",
            "business_intent": "derive skill closure",
            "owner_id": "closure-runtime-v2",
            "route_ids": ["route:derive-closure"],
        },
        {
            "function_id": "graduate_portfolio",
            "business_intent": "graduate skill portfolio",
            "owner_id": "portfolio-runtime-v2",
            "route_ids": ["route:portfolio-graduation"],
        },
        {
            "function_id": "adopt_project",
            "business_intent": "adopt or upgrade a SkillGuard-maintained skill project",
            "owner_id": "project-adoption-v2",
            "route_ids": ["route:project-adoption"],
        },
        {
            "function_id": "global_router_handoff",
            "business_intent": "refresh and verify global skill routing",
            "owner_id": "global-router-handoff-v2",
            "route_ids": ["route:global-router-handoff"],
            "composable_with": ["static_audit", "audit_provenance"],
        },
        {
            "function_id": "audit_provenance",
            "business_intent": "audit canonical installed repository and release provenance",
            "owner_id": "provenance-audit-v2",
            "route_ids": ["route:provenance-audit"],
            "composable_with": ["static_audit", "global_router_handoff"],
        },
    )
    function_ids = tuple(str(row["function_id"]) for row in functions)
    functions = tuple(
        {
            **row,
            "composable_with": [function_id for function_id in function_ids if function_id != row["function_id"]],
        }
        for row in functions
    )
    routes = (
        {
            "route_id": "route:static-audit",
            "function_id": "static_audit",
            "owner_id": "static-audit-v2",
            "start_step_id": "step:inventory-static-surface",
            "step_ids": [
                "step:inventory-static-surface",
                "step:run-native-static-checks",
                "step:issue-static-audit-receipt",
                "terminal:static-audit-closed",
                "terminal:static-audit-blocked",
            ],
            "success_terminal_step_id": "terminal:static-audit-closed",
            "blocked_terminal_step_id": "terminal:static-audit-blocked",
            "handoffs": [],
        },
        {
            "route_id": "route:deep-audit",
            "function_id": "deep_audit",
            "owner_id": "deep-audit-v2",
            "start_step_id": "step:freeze-declared-check-inventory",
            "step_ids": [
                "step:freeze-declared-check-inventory",
                "step:run-declared-checks",
                "step:reconcile-declared-check-results",
                "terminal:deep-audit-closed",
                "terminal:deep-audit-blocked",
            ],
            "success_terminal_step_id": "terminal:deep-audit-closed",
            "blocked_terminal_step_id": "terminal:deep-audit-blocked",
            "handoffs": [],
        },
        {
            "route_id": "route:compile-contract",
            "function_id": "compile_contract",
            "owner_id": "contract-compiler-v2",
            "start_step_id": "step:load-model-export",
            "step_ids": [
                "step:load-model-export",
                "step:validate-binding",
                "step:compile-generated-contract",
                "step:verify-generated-parity",
                "terminal:compiled",
                "terminal:compile-blocked",
            ],
            "success_terminal_step_id": "terminal:compiled",
            "blocked_terminal_step_id": "terminal:compile-blocked",
            "handoffs": [],
        },
        {
            "route_id": "route:supervise-run",
            "function_id": "supervise_run",
            "owner_id": "run-runtime-v2",
            "start_step_id": "step:select-function-route",
            "step_ids": [
                "step:select-function-route",
                "step:claim-run",
                "step:next-ready-step",
                "step:record-step-event",
                "terminal:run-ready-for-closure",
                "terminal:run-blocked",
            ],
            "success_terminal_step_id": "terminal:run-ready-for-closure",
            "blocked_terminal_step_id": "terminal:run-blocked",
            "handoffs": [
                {
                    "target_kind": "internal_route",
                    "target_id": "route:verify-evidence",
                    "condition": "evidence_submitted",
                    "claim_scope": "current step only",
                },
                {
                    "target_kind": "internal_route",
                    "target_id": "route:derive-closure",
                    "condition": "no_ready_required_steps",
                    "claim_scope": "current run only",
                },
            ],
            "loop_policy": {
                "progress_measure": "new_current_step_receipt_ids",
                "allowed_delta": "strictly_adds_or_supersedes_required_receipt",
                "success_terminal_step_id": "terminal:run-ready-for-closure",
                "blocked_terminal_step_id": "terminal:run-blocked",
                "max_reentries": 20,
            },
        },
        {
            "route_id": "route:verify-evidence",
            "function_id": "verify_evidence",
            "owner_id": "evidence-runtime-v2",
            "start_step_id": "step:validate-step-evidence",
            "step_ids": [
                "step:validate-step-evidence",
                "step:issue-step-receipt",
                "terminal:evidence-accepted",
                "terminal:evidence-rejected",
            ],
            "success_terminal_step_id": "terminal:evidence-accepted",
            "blocked_terminal_step_id": "terminal:evidence-rejected",
            "handoffs": [
                {
                    "target_kind": "internal_route",
                    "target_id": "route:supervise-run",
                    "condition": "more_ready_or_rework_steps",
                    "claim_scope": "current run only",
                }
            ],
            "loop_policy": {
                "progress_measure": "new_current_step_receipt_ids",
                "allowed_delta": "strictly_adds_or_supersedes_required_receipt",
                "success_terminal_step_id": "terminal:evidence-accepted",
                "blocked_terminal_step_id": "terminal:evidence-rejected",
                "max_reentries": 20,
            },
        },
        {
            "route_id": "route:derive-closure",
            "function_id": "derive_closure",
            "owner_id": "closure-runtime-v2",
            "start_step_id": "step:check-run-closure",
            "step_ids": [
                "step:check-run-closure",
                "step:issue-closure-receipt",
                "terminal:run-closed",
                "terminal:closure-blocked",
            ],
            "success_terminal_step_id": "terminal:run-closed",
            "blocked_terminal_step_id": "terminal:closure-blocked",
            "handoffs": [],
        },
        {
            "route_id": "route:portfolio-graduation",
            "function_id": "graduate_portfolio",
            "owner_id": "portfolio-runtime-v2",
            "start_step_id": "step:scan-graduate-freshness",
            "step_ids": [
                "step:scan-graduate-freshness",
                "step:revalidate-affected-graduates",
                "step:issue-portfolio-receipt",
                "terminal:portfolio-graduated",
                "terminal:portfolio-revalidation-required",
            ],
            "success_terminal_step_id": "terminal:portfolio-graduated",
            "blocked_terminal_step_id": "terminal:portfolio-revalidation-required",
            "handoffs": [],
        },
        {
            "route_id": "route:project-adoption",
            "function_id": "adopt_project",
            "owner_id": "project-adoption-v2",
            "start_step_id": "step:inspect-project-adoption",
            "step_ids": [
                "step:inspect-project-adoption",
                "step:render-managed-project-prompt",
                "step:install-project-adoption",
                "step:audit-project-adoption",
                "terminal:project-adopted",
                "terminal:project-adoption-blocked",
            ],
            "success_terminal_step_id": "terminal:project-adopted",
            "blocked_terminal_step_id": "terminal:project-adoption-blocked",
            "handoffs": [],
        },
        {
            "route_id": "route:global-router-handoff",
            "function_id": "global_router_handoff",
            "owner_id": "global-router-handoff-v2",
            "start_step_id": "step:refresh-global-router",
            "step_ids": [
                "step:refresh-global-router",
                "step:check-global-registry-and-prompt",
                "step:verify-target-handoff",
                "terminal:global-router-current",
                "terminal:global-router-blocked",
            ],
            "success_terminal_step_id": "terminal:global-router-current",
            "blocked_terminal_step_id": "terminal:global-router-blocked",
            "handoffs": [],
        },
        {
            "route_id": "route:provenance-audit",
            "function_id": "audit_provenance",
            "owner_id": "provenance-audit-v2",
            "start_step_id": "step:resolve-canonical-source",
            "step_ids": [
                "step:resolve-canonical-source",
                "step:compare-installed-and-repository",
                "step:verify-release-provenance",
                "terminal:provenance-current",
                "terminal:provenance-blocked",
            ],
            "success_terminal_step_id": "terminal:provenance-current",
            "blocked_terminal_step_id": "terminal:provenance-blocked",
            "handoffs": [],
        },
    )

    def step(
        step_id: str,
        route_id: str,
        owner_id: str,
        action_kind: str,
        prerequisites: Sequence[str] = (),
        *,
        required: bool = True,
        terminal_kind: str = "",
    ) -> dict[str, object]:
        return {
            "step_id": step_id,
            "route_id": route_id,
            "owner_id": owner_id,
            "action_kind": action_kind,
            "prerequisite_step_ids": list(prerequisites),
            "required": required,
            "terminal_kind": terminal_kind,
        }

    steps = (
        step("step:inventory-static-surface", "route:static-audit", "static-audit-v2", "inventory"),
        step("step:run-native-static-checks", "route:static-audit", "static-audit-v2", "native", ("step:inventory-static-surface",)),
        step("step:issue-static-audit-receipt", "route:static-audit", "static-audit-v2", "receipt", ("step:run-native-static-checks",)),
        step("terminal:static-audit-closed", "route:static-audit", "static-audit-v2", "terminal", ("step:issue-static-audit-receipt",), terminal_kind="success"),
        step("terminal:static-audit-blocked", "route:static-audit", "static-audit-v2", "terminal", terminal_kind="blocked"),
        step("step:freeze-declared-check-inventory", "route:deep-audit", "deep-audit-v2", "inventory"),
        step("step:run-declared-checks", "route:deep-audit", "deep-audit-v2", "native", ("step:freeze-declared-check-inventory",)),
        step("step:reconcile-declared-check-results", "route:deep-audit", "deep-audit-v2", "native", ("step:run-declared-checks",)),
        step("terminal:deep-audit-closed", "route:deep-audit", "deep-audit-v2", "terminal", ("step:reconcile-declared-check-results",), terminal_kind="success"),
        step("terminal:deep-audit-blocked", "route:deep-audit", "deep-audit-v2", "terminal", terminal_kind="blocked"),
        step("step:load-model-export", "route:compile-contract", "contract-compiler-v2", "flowguard_model"),
        step("step:validate-binding", "route:compile-contract", "contract-compiler-v2", "validator", ("step:load-model-export",)),
        step("step:compile-generated-contract", "route:compile-contract", "contract-compiler-v2", "compiler", ("step:validate-binding",)),
        step("step:verify-generated-parity", "route:compile-contract", "contract-compiler-v2", "validator", ("step:compile-generated-contract",)),
        step("terminal:compiled", "route:compile-contract", "contract-compiler-v2", "terminal", ("step:verify-generated-parity",), terminal_kind="success"),
        step("terminal:compile-blocked", "route:compile-contract", "contract-compiler-v2", "terminal", terminal_kind="blocked"),
        step("step:select-function-route", "route:supervise-run", "run-runtime-v2", "router"),
        step("step:claim-run", "route:supervise-run", "run-runtime-v2", "state_write", ("step:select-function-route",)),
        step("step:next-ready-step", "route:supervise-run", "run-runtime-v2", "router", ("step:claim-run",)),
        step("step:record-step-event", "route:supervise-run", "run-runtime-v2", "state_write", ("step:next-ready-step",)),
        step("terminal:run-ready-for-closure", "route:supervise-run", "run-runtime-v2", "terminal", ("step:record-step-event",), terminal_kind="success"),
        step("terminal:run-blocked", "route:supervise-run", "run-runtime-v2", "terminal", terminal_kind="blocked"),
        step("step:validate-step-evidence", "route:verify-evidence", "evidence-runtime-v2", "verifier"),
        step("step:issue-step-receipt", "route:verify-evidence", "evidence-runtime-v2", "receipt", ("step:validate-step-evidence",)),
        step("terminal:evidence-accepted", "route:verify-evidence", "evidence-runtime-v2", "terminal", ("step:issue-step-receipt",), terminal_kind="success"),
        step("terminal:evidence-rejected", "route:verify-evidence", "evidence-runtime-v2", "terminal", terminal_kind="blocked"),
        step("step:check-run-closure", "route:derive-closure", "closure-runtime-v2", "verifier"),
        step("step:issue-closure-receipt", "route:derive-closure", "closure-runtime-v2", "receipt", ("step:check-run-closure",)),
        step("terminal:run-closed", "route:derive-closure", "closure-runtime-v2", "terminal", ("step:issue-closure-receipt",), terminal_kind="success"),
        step("terminal:closure-blocked", "route:derive-closure", "closure-runtime-v2", "terminal", terminal_kind="blocked"),
        step("step:scan-graduate-freshness", "route:portfolio-graduation", "portfolio-runtime-v2", "validator"),
        step("step:revalidate-affected-graduates", "route:portfolio-graduation", "portfolio-runtime-v2", "native", ("step:scan-graduate-freshness",)),
        step("step:issue-portfolio-receipt", "route:portfolio-graduation", "portfolio-runtime-v2", "receipt", ("step:revalidate-affected-graduates",)),
        step("terminal:portfolio-graduated", "route:portfolio-graduation", "portfolio-runtime-v2", "terminal", ("step:issue-portfolio-receipt",), terminal_kind="success"),
        step("terminal:portfolio-revalidation-required", "route:portfolio-graduation", "portfolio-runtime-v2", "terminal", terminal_kind="blocked"),
        step("step:inspect-project-adoption", "route:project-adoption", "project-adoption-v2", "inventory"),
        step("step:render-managed-project-prompt", "route:project-adoption", "project-adoption-v2", "renderer", ("step:inspect-project-adoption",)),
        step("step:install-project-adoption", "route:project-adoption", "project-adoption-v2", "state_write", ("step:render-managed-project-prompt",)),
        step("step:audit-project-adoption", "route:project-adoption", "project-adoption-v2", "verifier", ("step:install-project-adoption",)),
        step("terminal:project-adopted", "route:project-adoption", "project-adoption-v2", "terminal", ("step:audit-project-adoption",), terminal_kind="success"),
        step("terminal:project-adoption-blocked", "route:project-adoption", "project-adoption-v2", "terminal", terminal_kind="blocked"),
        step("step:refresh-global-router", "route:global-router-handoff", "global-router-handoff-v2", "native"),
        step("step:check-global-registry-and-prompt", "route:global-router-handoff", "global-router-handoff-v2", "native", ("step:refresh-global-router",)),
        step("step:verify-target-handoff", "route:global-router-handoff", "global-router-handoff-v2", "verifier", ("step:check-global-registry-and-prompt",)),
        step("terminal:global-router-current", "route:global-router-handoff", "global-router-handoff-v2", "terminal", ("step:verify-target-handoff",), terminal_kind="success"),
        step("terminal:global-router-blocked", "route:global-router-handoff", "global-router-handoff-v2", "terminal", terminal_kind="blocked"),
        step("step:resolve-canonical-source", "route:provenance-audit", "provenance-audit-v2", "inventory"),
        step("step:compare-installed-and-repository", "route:provenance-audit", "provenance-audit-v2", "validator", ("step:resolve-canonical-source",)),
        step("step:verify-release-provenance", "route:provenance-audit", "provenance-audit-v2", "validator", ("step:compare-installed-and-repository",)),
        step("terminal:provenance-current", "route:provenance-audit", "provenance-audit-v2", "terminal", ("step:verify-release-provenance",), terminal_kind="success"),
        step("terminal:provenance-blocked", "route:provenance-audit", "provenance-audit-v2", "terminal", terminal_kind="blocked"),
    )
    obligation_rows = (
        ("obligation:static-audit", "artifacts_and_checks_are_current", ["step:inventory-static-surface", "step:run-native-static-checks", "step:issue-static-audit-receipt"]),
        ("obligation:deep-audit", "artifacts_and_checks_are_current", ["step:freeze-declared-check-inventory", "step:run-declared-checks", "step:reconcile-declared-check-results"]),
        ("obligation:model-authority", "model_and_binding_are_authoritative", ["step:load-model-export", "step:validate-binding"]),
        ("obligation:route-ownership", "routes_are_typed_and_uniquely_owned", ["step:select-function-route"]),
        ("obligation:packet-consumption", "packet_fields_are_declared_and_consumed", ["step:select-function-route"]),
        ("obligation:guard-run-identity", "guard_change_claims_a_new_run", ["step:claim-run"]),
        ("obligation:claimed-run", "every_task_is_claimed_and_locked", ["step:claim-run"]),
        ("obligation:failed-lock-recovery", "failed_or_dead_writer_lock_cannot_block_forever", ["step:claim-run"]),
        ("obligation:verifier-pass", "pass_and_skip_are_verifier_owned", ["step:validate-step-evidence"]),
        ("obligation:artifact-freshness", "artifacts_and_checks_are_current", ["step:validate-step-evidence", "step:check-run-closure"]),
        ("obligation:durable-resume", "resume_uses_durable_events", ["step:record-step-event", "step:next-ready-step"]),
        ("obligation:loop-liveness", "loops_require_progress_and_a_finite_bound", ["step:record-step-event"]),
        ("obligation:exact-closure", "closure_consumes_current_exact_receipts", ["step:check-run-closure", "step:issue-closure-receipt"]),
        ("obligation:no-former-authority-success", "failures_and_former_authority_cannot_hide", ["step:select-function-route", "step:check-run-closure"]),
        ("obligation:portfolio-freshness", "portfolio_children_remain_current", ["step:scan-graduate-freshness", "step:issue-portfolio-receipt"]),
        ("obligation:depth-native-authority", "depth_profile_preserves_native_authority", ["step:freeze-declared-check-inventory", "step:reconcile-declared-check-results"]),
        ("obligation:execution-depth-closure", "execution_depth_is_current_and_consumed", ["step:reconcile-declared-check-results", "step:check-run-closure", "step:issue-closure-receipt"]),
        ("obligation:unique-depth-evidence", "evidence_contribution_is_unique", ["step:reconcile-declared-check-results", "step:validate-step-evidence"]),
        ("obligation:project-adoption", "adopted_projects_keep_skillguard_maintenance_visible", ["step:inspect-project-adoption", "step:render-managed-project-prompt", "step:install-project-adoption", "step:audit-project-adoption"]),
        ("obligation:global-router-handoff", "routes_are_typed_and_uniquely_owned", ["step:refresh-global-router", "step:check-global-registry-and-prompt", "step:verify-target-handoff"]),
        ("obligation:provenance", "model_and_binding_are_authoritative", ["step:resolve-canonical-source", "step:compare-installed-and-repository", "step:verify-release-provenance"]),
    )
    return {
        "schema_version": "skillguard.flowguard_model_export.v2",
        "flowguard_schema_version": str(_flowguard.SCHEMA_VERSION),
        "model_id": MODEL_ID,
        "parent_model_id": PARENT_MODEL_ID,
        "functions": list(functions),
        "routes": list(routes),
        "steps": list(steps),
        "obligations": [
            {
                "obligation_id": obligation_id,
                "invariant_id": invariant_id,
                "owner_step_ids": owner_step_ids,
                "required": True,
            }
            for obligation_id, invariant_id, owner_step_ids in obligation_rows
        ],
        "invariant_ids": [invariant.name for invariant in INVARIANTS],
        "claim_boundary": (
            "This export defines executable-contract behavior and topology. "
            "It does not supply target commands, tools, artifacts, native checks, "
            "current runtime receipts, or publication evidence."
        ),
    }


def _path_binding(
    intent: str,
    primary_path_id: str,
    commitment_id: str,
) -> BehaviorPathAuthorityBinding:
    return BehaviorPathAuthorityBinding(
        path_sensitive=True,
        business_intent=intent,
        business_intent_id=f"intent:{commitment_id.removeprefix('commitment:')}",
        behavior_commitment_id=commitment_id,
        ppa_report_id="skillguard-v2-primary-path-authority",
        ppa_decision="primary_path_authority_green",
        ppa_confidence="full",
        ppa_ok=True,
        primary_path_id=primary_path_id,
        ppa_risk_gate_ids=("risk_gate:skillguard-v2-primary-path-authority",),
        evidence_refs=("model:skillguard-v2-ppa",),
        runtime_observation_ids=(f"runtime:model:{primary_path_id}",),
        proof_artifact_ids=(f"proof:model:{primary_path_id}",),
        evidence_current=True,
    )


def build_behavior_commitment_ledger() -> BehaviorCommitmentLedger:
    commitment_rows = (
        (
            "commitment:compile-model-contract",
            BCL_COMMITMENT_WORKFLOW,
            "a maintained skill declares release behavior",
            "a deterministic compiled contract and exact check manifest are derived from a current model and binding",
            "release compilation blocks on unsupported FlowGuard, drift, topology gaps, or check overbinding",
            "compile executable contract",
            "compile-contract-v2",
            ("surface:compilation-spec", "surface:executable-model"),
        ),
        (
            "commitment:claim-every-run",
            BCL_COMMITMENT_WORKFLOW,
            "AI starts a supervised target-skill task",
            "one route is selected and a target-local run is claimed and locked",
            "execution blocks when the route, claim, or lock is unresolved",
            "supervise target skill task",
            "claimed-run-v2",
            ("surface:run-spec", "surface:executable-model"),
        ),
        (
            "commitment:verifier-owned-evidence",
            BCL_COMMITMENT_WORKFLOW,
            "AI submits work, artifacts, failure, blocker, or skip request",
            "hard, witnessed, or judged verification derives immutable evidence status",
            "caller-authored pass, illegal skip, stale artifact, or unrelated check blocks",
            "verify target evidence",
            "verify-step-v2",
            ("surface:evidence-spec", "surface:executable-model"),
        ),
        (
            "commitment:exact-functional-closure",
            BCL_COMMITMENT_WORKFLOW,
            "a run requests the sole enforced closure",
            "the parent consumes exact current child receipts and emits a scoped safe claim",
            "missing, failed, stale, skipped, partial, or not-run required evidence blocks",
            "derive skill closure",
            "close-run-v2",
            ("surface:closure-spec", "surface:executable-model"),
        ),
        (
            "commitment:current-authority-only",
            BCL_COMMITMENT_PROCESS,
            "a former runtime command remains in the live surface",
            "ordinary maintenance rewrites the target directly into the one current authority and removes the former surface",
            "any former surface, converter, fallback reader, or alternate success path blocks broad confidence",
            "supervise target skill task",
            "claimed-run-v2",
            ("surface:run-spec", "surface:executable-model"),
        ),
        (
            "commitment:portfolio-revalidates-after-guard-change",
            BCL_COMMITMENT_PROCESS,
            "a later target exposes a SkillGuard miss or changes Guard semantics",
            "affected prior graduates become revalidation-required and regain currentness through full evidence or a proof-bound reuse ticket",
            "portfolio graduation blocks while any required child is stale, missing, failed, or blocked",
            "graduate skill portfolio",
            "portfolio-graduation-v2",
            ("surface:portfolio-spec", "surface:executable-model"),
        ),
        (
            "commitment:execution-depth-before-broad-closure",
            BCL_COMMITMENT_WORKFLOW,
            "a maintained target requests enforced closure",
            "the parent consumes a current target-owned EXECUTION_DEPTH_PASS receipt with unique evidence contribution",
            "contract-only, shallow, boundary-only, unavailable, not-run, unmanaged, or stale depth remains non-pass",
            "derive skill closure",
            "close-run-v2",
            ("surface:execution-depth-spec", "surface:executable-model"),
        ),
        (
            "commitment:project-adoption-is-portable",
            BCL_COMMITMENT_PROCESS,
            "SkillGuard adopts or upgrades a target skill repository",
            "one marker-bounded AGENTS block and portable project record name SkillGuard and preserve native route ownership",
            "missing, duplicate, incomplete, stale, or hand-diverged project guidance blocks maintenance confidence",
            "adopt target skill project",
            "project-adoption-v2",
            ("surface:project-adoption-spec", "surface:executable-model"),
        ),
    )
    commitments = tuple(
        BehaviorCommitment(
            row[0],
            business_intent_id=f"intent:{row[0].removeprefix('commitment:')}",
            label=row[0].removeprefix("commitment:").replace("-", " "),
            commitment_kind=row[1],
            behavior_plane=BCL_PLANE_AGENT_OPERATION,
            actor_kind=BCL_ACTOR_AI_AGENT,
            actor="SkillGuard-supervised AI",
            trigger=row[2],
            expected_result=row[3],
            expected_terminal=row[3],
            failure_boundary=row[4],
            source_surface_ids=(
                row[7][0],
                f"surface:model:{row[0].removeprefix('commitment:')}",
                f"surface:test:{row[0].removeprefix('commitment:')}",
            ),
            primary_owner_model_id=MODEL_ID,
            path_authority=_path_binding(row[5], row[6], row[0]),
            validation_boundary="FlowGuard scenario, PPA, CEM, MTA, and TestMesh design evidence",
            rationale="external current SkillGuard behavior promised by the approved OpenSpec change",
        )
        for row in commitment_rows
    )
    base_surfaces = (
        BehaviorSourceSurface(
            "surface:compilation-spec",
            surface_kind=BCL_SOURCE_OPENSPEC,
            source_ref="openspec/changes/build-executable-skill-contract-runtime/specs/executable-skill-contract-compilation/spec.md",
            commitment_ids=("commitment:compile-model-contract",),
            business_intent_ids=("intent:compile-model-contract",),
            primary_path_id="compile-contract-v2",
            owner=MODEL_ID,
            validation_boundary="approved compilation requirements",
            rationale="defines externally visible compiler authority and failures",
        ),
        BehaviorSourceSurface(
            "surface:run-spec",
            surface_kind=BCL_SOURCE_OPENSPEC,
            source_ref="openspec/changes/build-executable-skill-contract-runtime/specs/claimed-skill-run-runtime/spec.md",
            commitment_ids=("commitment:claim-every-run", "commitment:current-authority-only"),
            business_intent_ids=("intent:claim-every-run", "intent:current-authority-only"),
            primary_path_id="claimed-run-v2",
            owner=MODEL_ID,
            validation_boundary="approved claimed-run requirements",
            rationale="defines task claiming, transitions, resume, skip, and loop behavior",
        ),
        BehaviorSourceSurface(
            "surface:evidence-spec",
            surface_kind=BCL_SOURCE_OPENSPEC,
            source_ref="openspec/changes/build-executable-skill-contract-runtime/specs/skill-evidence-receipts/spec.md",
            commitment_ids=("commitment:verifier-owned-evidence",),
            business_intent_ids=("intent:verifier-owned-evidence",),
            primary_path_id="verify-step-v2",
            owner=MODEL_ID,
            validation_boundary="approved evidence requirements",
            rationale="defines evidence classes, immutability, freshness, and artifact identity",
        ),
        BehaviorSourceSurface(
            "surface:closure-spec",
            surface_kind=BCL_SOURCE_OPENSPEC,
            source_ref="openspec/changes/harden-native-depth-evidence-identity/specs/universal-execution-depth/spec.md",
            commitment_ids=("commitment:exact-functional-closure",),
            business_intent_ids=("intent:exact-functional-closure",),
            primary_path_id="close-run-v2",
            owner=MODEL_ID,
            validation_boundary="approved closure requirements",
            rationale="defines the fixed enforced closure, exact receipt consumption, and safe claims",
        ),
        BehaviorSourceSurface(
            "surface:portfolio-spec",
            surface_kind=BCL_SOURCE_OPENSPEC,
            source_ref="openspec/changes/harden-native-depth-evidence-identity/specs/universal-execution-depth/spec.md",
            commitment_ids=("commitment:portfolio-revalidates-after-guard-change",),
            business_intent_ids=("intent:portfolio-revalidates-after-guard-change",),
            primary_path_id="portfolio-graduation-v2",
            owner=MODEL_ID,
            validation_boundary="approved receipt freshness and consumer requirements",
            rationale="defines affected-only staleness and read-only receipt consumption",
        ),
        BehaviorSourceSurface(
            "surface:execution-depth-spec",
            surface_kind=BCL_SOURCE_OPENSPEC,
            source_ref="openspec/changes/harden-native-depth-evidence-identity/specs/universal-execution-depth/spec.md",
            commitment_ids=("commitment:execution-depth-before-broad-closure",),
            business_intent_ids=("intent:execution-depth-before-broad-closure",),
            primary_path_id="close-run-v2",
            owner=MODEL_ID,
            validation_boundary="approved universal execution-depth requirements",
            rationale="defines target-neutral profiles, native authority, unique evidence, statuses, and closure",
        ),
        BehaviorSourceSurface(
            "surface:project-adoption-spec",
            surface_kind=BCL_SOURCE_OPENSPEC,
            source_ref="openspec/changes/harden-native-depth-evidence-identity/specs/universal-execution-depth/spec.md",
            commitment_ids=("commitment:project-adoption-is-portable",),
            business_intent_ids=("intent:project-adoption-is-portable",),
            primary_path_id="project-adoption-v2",
            owner=MODEL_ID,
            validation_boundary="approved project-adoption requirements",
            rationale="defines the portable managed project prompt and safe lifecycle",
        ),
    )
    model_surfaces = tuple(
        BehaviorSourceSurface(
            f"surface:model:{row[0].removeprefix('commitment:')}",
            surface_kind=BCL_SOURCE_CODE,
            source_ref=MODEL_PATH,
            commitment_ids=(row[0],),
            business_intent_ids=(
                f"intent:{row[0].removeprefix('commitment:')}",
            ),
            primary_path_id=row[6],
            owner=MODEL_ID,
            validation_boundary="current executable scenario and governance model",
            rationale="commitment-specific projection of the one current parent model",
        )
        for row in commitment_rows
    )
    test_surfaces = tuple(
        BehaviorSourceSurface(
            f"surface:test:{row[0].removeprefix('commitment:')}",
            surface_kind=BCL_SOURCE_TEST,
            source_ref=TEST_PATH,
            commitment_ids=(row[0],),
            business_intent_ids=(
                f"intent:{row[0].removeprefix('commitment:')}",
            ),
            primary_path_id=row[6],
            delegates_to_primary_path=True,
            owner=MODEL_ID,
            validation_boundary="focused model and known-bad scenario tests",
            rationale="test evidence delegates to the same commitment primary path",
        )
        for row in commitment_rows
    )
    surfaces = (*base_surfaces, *model_surfaces, *test_surfaces)
    return BehaviorCommitmentLedger(
        "skillguard-v2-behavior-ledger",
        project_boundary="SkillGuard executable-contract runtime and portfolio feedback loop",
        current_revision="design-v2-2026-07-10",
        commitments=commitments,
        source_surfaces=surfaces,
        expected_commitment_ids=tuple(commitment.commitment_id for commitment in commitments),
        claim_scope=BCL_SCOPE_ROUTINE,
        change_mode=BCL_CHANGE_BOOTSTRAP_LEDGER,
        require_current_evidence=False,
        owner=MODEL_ID,
        validation_boundary="design-stage BCL structure; runtime evidence is intentionally not claimed yet",
        rationale="register every public current behavior before production implementation",
    )


def build_primary_path_authority_plan() -> PrimaryPathAuthorityPlan:
    primary_paths = (
        PrimaryPathContract(
            "compile-contract-v2",
            business_intent="compile executable contract",
            primary_entrypoint_id="skillguard.compile-contract",
            owner_model_id=MODEL_ID,
            owner_code_contract_id="contract:contract-compiler-v2",
            expected_terminal="compiled_or_visible_blocker",
            failure_policy="fail_closed",
        ),
        PrimaryPathContract(
            "claimed-run-v2",
            business_intent="supervise target skill task",
            primary_entrypoint_id="skillguard.claim-run",
            owner_model_id=MODEL_ID,
            owner_code_contract_id="contract:run-runtime-v2",
            expected_terminal="closed_or_visible_blocker",
            failure_policy="fail_closed",
        ),
        PrimaryPathContract(
            "verify-step-v2",
            business_intent="verify target evidence",
            primary_entrypoint_id="skillguard.check-step",
            owner_model_id=MODEL_ID,
            owner_code_contract_id="contract:evidence-runtime-v2",
            expected_terminal="receipt_or_visible_failure",
            failure_policy="fail_closed",
        ),
        PrimaryPathContract(
            "close-run-v2",
            business_intent="derive skill closure",
            primary_entrypoint_id="skillguard.close-run",
            owner_model_id=MODEL_ID,
            owner_code_contract_id="contract:closure-runtime-v2",
            expected_terminal="closure_receipt_or_visible_blocker",
            failure_policy="fail_closed",
        ),
        PrimaryPathContract(
            "portfolio-graduation-v2",
            business_intent="graduate skill portfolio",
            primary_entrypoint_id="skillguard.audit-portfolio",
            owner_model_id=MODEL_ID,
            owner_code_contract_id="contract:portfolio-runtime-v2",
            expected_terminal="graduated_or_revalidation_required",
            failure_policy="fail_closed",
        ),
        PrimaryPathContract(
            "project-adoption-v2",
            business_intent="adopt target skill project",
            primary_entrypoint_id="skillguard.project-adopt",
            owner_model_id=MODEL_ID,
            owner_code_contract_id="contract:project-adoption-v2",
            expected_terminal="project_adopted_or_visible_blocker",
            failure_policy="fail_closed",
        ),
    )
    return PrimaryPathAuthorityPlan(
        "skillguard-v2-primary-path-authority",
        primary_paths=primary_paths,
        fallback_candidates=(),
        claim_scope=PPA_CLAIM_SCOPE_ROUTINE,
        expected_business_intents=tuple(path.business_intent for path in primary_paths),
    )


def build_contract_exhaustion_plan() -> ContractExhaustionPlan:
    dimensions = (
        ContractDimension(
            "path_shape",
            "route",
            source_route="model_first_function_flow",
            owner_model_id=MODEL_ID,
            values=("single", "multi", "composed", "conditional"),
            mutation_types=("unknown_enum", "malformed_input"),
            description="selected function-path shape",
        ),
        ContractDimension(
            "run_claim",
            "state",
            source_route="model_first_function_flow",
            owner_model_id=MODEL_ID,
            values=("claimed", "unclaimed", "conflicting_writer", "failed_writer", "dead_writer", "recovered_writer"),
            mutation_types=("unknown_enum", "malformed_input"),
            description="run claim and target-lock state",
        ),
        ContractDimension(
            "packet_field_contract",
            "input",
            source_route="model_first_function_flow",
            owner_model_id=MODEL_ID,
            values=(
                "fully_consumed",
                "unknown_top_level",
                "unknown_request",
                "unknown_step",
                "unknown_judgment",
                "unknown_witness",
                "unknown_skip",
                "unknown_artifact_witness",
                "unselected_step",
            ),
            mutation_types=("unknown_enum", "malformed_input"),
            description="declared and route-reachable supervisor packet fields",
        ),
        ContractDimension(
            "step_disposition",
            "state",
            source_route="model_first_function_flow",
            owner_model_id=MODEL_ID,
            values=("passed", "failed", "blocked", "skipped", "stale"),
            mutation_types=("unknown_enum", "malformed_input"),
            description="verifier-derived step disposition",
        ),
        ContractDimension(
            "guard_compatibility",
            "state",
            source_route="model_first_function_flow",
            owner_model_id=MODEL_ID,
            values=("unchanged", "changed_new_run", "changed_same_run"),
            mutation_types=("unknown_enum", "malformed_input"),
            description="Guard runtime compatibility and claimed-run identity",
        ),
        ContractDimension(
            "resume_source",
            "evidence",
            source_route="model_first_function_flow",
            owner_model_id=MODEL_ID,
            values=("events", "chat_memory"),
            mutation_types=("unknown_enum", "malformed_input"),
            description="state recovery source",
        ),
        ContractDimension(
            "loop_progress",
            "transition",
            source_route="model_first_function_flow",
            owner_model_id=MODEL_ID,
            values=("changed", "no_delta", "over_bound"),
            mutation_types=("unknown_enum", "malformed_input"),
            description="bounded retry and refinement progress",
        ),
        ContractDimension(
            "receipt_freshness",
            "evidence",
            source_route="model_test_alignment",
            owner_model_id=MODEL_ID,
            values=("current", "stale", "superseded", "scope_mismatch"),
            mutation_types=("unknown_enum", "malformed_input"),
            description="step and parent receipt currentness",
        ),
    )
    block_oracle = ContractOracle(
        "oracle:block-before-close",
        "blocked",
        expected_message_fields=("findings", "next_actions", "claim_boundary"),
        forbidden_downstream_steps=("close-run", "portfolio-graduate"),
        required_repair_fields=("blocker", "next_action"),
        description="invalid run states block before closure or portfolio graduation",
    )
    stale_oracle = ContractOracle(
        "oracle:stale-revalidate",
        "revalidation_required",
        expected_message_fields=("stale_evidence", "next_actions", "claim_boundary"),
        forbidden_downstream_steps=("portfolio-graduate",),
        required_repair_fields=("affected_feature_tags", "revalidation_target_ids"),
        description="stale evidence requires scoped revalidation",
    )
    seed_cases = (
        ContractMutationCase("case:single:missing-terminal", "path_shape", "missing", oracle_id=block_oracle.oracle_id, input_delta={"path_shape": "single", "terminal": ""}, expected_status="blocked", required_test_cell_id="test:model:single-missing-terminal"),
        ContractMutationCase("case:multi:duplicate-owner", "path_shape", "duplicate", oracle_id=block_oracle.oracle_id, input_delta={"path_shape": "multi", "owner_count": 2}, expected_status="blocked", required_test_cell_id="test:model:multi-duplicate-owner"),
        ContractMutationCase("case:composed:dangling-handoff", "path_shape", "dangling", oracle_id=block_oracle.oracle_id, input_delta={"path_shape": "composed", "target_id": "missing"}, expected_status="blocked", required_test_cell_id="test:model:composed-dangling"),
        ContractMutationCase("case:conditional:skip-without-condition", "path_shape", "missing_condition", oracle_id=block_oracle.oracle_id, input_delta={"path_shape": "conditional", "skip_reason": "not needed"}, expected_status="blocked", required_test_cell_id="test:model:conditional-skip"),
        ContractMutationCase("case:recovery:chat-memory", "resume_source", "wrong_authority", oracle_id=block_oracle.oracle_id, input_delta={"resume_source": "chat_memory"}, expected_status="blocked", required_test_cell_id="test:model:resume-memory"),
        ContractMutationCase("case:skip:required-step", "step_disposition", "illegal_skip", oracle_id=block_oracle.oracle_id, input_delta={"required": True, "status": "skipped"}, expected_status="blocked", required_test_cell_id="test:model:required-skip"),
        ContractMutationCase("case:blocked:missing-unblock-condition", "step_disposition", "missing_repair", oracle_id=block_oracle.oracle_id, input_delta={"status": "blocked", "unblock_condition": ""}, expected_status="blocked", required_test_cell_id="test:model:blocker-shape"),
        ContractMutationCase("case:stale:old-child-receipt", "receipt_freshness", "stale", oracle_id=stale_oracle.oracle_id, input_delta={"receipt": "superseded"}, expected_status="revalidation_required", required_test_cell_id="test:model:stale-child"),
        ContractMutationCase("case:concurrency:double-claim", "run_claim", "conflict", oracle_id=block_oracle.oracle_id, input_delta={"active_writers": 2}, expected_status="blocked", required_test_cell_id="test:model:double-claim"),
        ContractMutationCase("case:concurrency:stale-lock-not-recovered", "run_claim", "stale_lock", oracle_id=block_oracle.oracle_id, input_delta={"prior_writer": "failed_or_dead", "lock_recovered": False}, expected_status="blocked", required_test_cell_id="test:model:stale-lock-recovery"),
        ContractMutationCase("case:packet:unknown-field", "packet_field_contract", "unconsumed", oracle_id=block_oracle.oracle_id, input_delta={"packet_field_contract": "unknown_step"}, expected_status="blocked", required_test_cell_id="test:model:packet-unknown-field"),
        ContractMutationCase("case:project-adoption:wrong-artifact-root", "path_shape", "wrong_root", oracle_id=block_oracle.oracle_id, input_delta={"artifact": ".agents/skills/skillguard/.skillguard/project.json", "required_root": ".skillguard/project.json"}, expected_status="blocked", required_test_cell_id="test:model:project-adoption-wrong-artifact-root"),
        ContractMutationCase("case:guard:changed-same-run", "guard_compatibility", "stale_identity", oracle_id=stale_oracle.oracle_id, input_delta={"guard_runtime": "changed", "run_identity": "old"}, expected_status="revalidation_required", required_test_cell_id="test:model:guard-changed-same-run"),
        ContractMutationCase("case:loop:no-delta", "loop_progress", "no_progress", oracle_id=block_oracle.oracle_id, input_delta={"progress_changed": False, "reentries": 1}, expected_status="blocked", required_test_cell_id="test:model:no-delta"),
        ContractMutationCase("case:loop:over-bound", "loop_progress", "out_of_range", oracle_id=block_oracle.oracle_id, input_delta={"reentries": 4, "max_reentries": 3}, expected_status="blocked", required_test_cell_id="test:model:over-bound"),
        ContractMutationCase("case:portfolio:prior-stale", "receipt_freshness", "stale", oracle_id=stale_oracle.oracle_id, input_delta={"prior_graduate": "revalidation_required"}, expected_status="revalidation_required", required_test_cell_id="test:model:portfolio-prior-stale"),
    )
    return ContractExhaustionPlan(
        "skillguard-v2-contract-exhaustion",
        dimensions=dimensions,
        seed_cases=seed_cases,
        oracles=(block_oracle, stale_oracle),
        claim_scope="enforced",
        source_model_ids=(MODEL_ID,),
        generation_policy="bounded",
        allow_unbounded_scoped=False,
    )


def _obligation(
    obligation_id: str,
    description: str,
    symbol: str,
    happy_test: str,
    failure_test: str,
) -> tuple[ModelObligation, CodeContract, tuple[TestEvidence, TestEvidence]]:
    contract_id = f"contract:model:{symbol}"
    obligation = ModelObligation(
        obligation_id,
        description=description,
        required_test_kinds=("happy_path", "failure_path"),
        allow_shared_evidence=False,
        allow_shared_implementation=False,
    )
    code_contract = CodeContract(
        contract_id,
        path=MODEL_PATH,
        symbol=symbol,
        implements_obligations=(obligation_id,),
        surface_type="model_invariant",
        role="owner",
    )
    evidence = (
        TestEvidence(
            f"evidence:{obligation_id}:happy",
            test_name=happy_test,
            path=TEST_PATH,
            command=f"python -m pytest {TEST_PATH} -q",
            result_status="passed",
            test_kind="happy_path",
            covered_obligations=(obligation_id,),
            covered_code_contracts=(contract_id,),
            assertion_scope="external_contract",
        ),
        TestEvidence(
            f"evidence:{obligation_id}:failure",
            test_name=failure_test,
            path=TEST_PATH,
            command=f"python -m pytest {TEST_PATH} -q",
            result_status="passed",
            test_kind="failure_path",
            covered_obligations=(obligation_id,),
            covered_code_contracts=(contract_id,),
            assertion_scope="external_contract",
        ),
    )
    return obligation, code_contract, evidence


def build_model_test_alignment_plan() -> ModelTestAlignmentPlan:
    rows = (
        ("obligation:static-audit", "static audit binds current native checks", "static_audit_is_current", "test_self_host_functions_have_distinct_routes_and_terminals", "test_known_bad_scenarios_are_required"),
        ("obligation:deep-audit", "deep audit preserves target-specific functional coverage", "deep_audit_is_target_specific", "test_self_host_functions_have_distinct_routes_and_terminals", "test_known_bad_scenarios_are_required"),
        ("obligation:model-authority", "model and binding are current", "model_and_binding_are_authoritative", "test_good_scenario_review_passes", "test_known_bad_scenarios_are_required"),
        ("obligation:route-ownership", "routes are typed and uniquely owned", "routes_are_typed_and_uniquely_owned", "test_good_scenario_review_passes", "test_known_bad_scenarios_are_required"),
        ("obligation:packet-consumption", "supervisor packet fields are declared and consumed", "packet_fields_are_declared_and_consumed", "test_good_scenario_review_passes", "test_known_bad_scenarios_are_required"),
        ("obligation:guard-run-identity", "Guard changes create a fresh claimed-run identity", "guard_change_claims_a_new_run", "test_good_scenario_review_passes", "test_known_bad_scenarios_are_required"),
        ("obligation:claimed-run", "every task is claimed and locked", "every_task_is_claimed_and_locked", "test_good_scenario_review_passes", "test_known_bad_scenarios_are_required"),
        ("obligation:failed-lock-recovery", "failed or dead writer locks recover without weakening live-writer exclusion", "failed_or_dead_writer_lock_cannot_block_forever", "test_good_scenario_review_passes", "test_known_bad_scenarios_are_required"),
        ("obligation:verifier-pass", "pass and skip are verifier-owned", "pass_and_skip_are_verifier_owned", "test_good_scenario_review_passes", "test_known_bad_scenarios_are_required"),
        ("obligation:artifact-freshness", "artifacts and checks are current", "artifacts_and_checks_are_current", "test_good_scenario_review_passes", "test_known_bad_scenarios_are_required"),
        ("obligation:durable-resume", "resume replays durable events", "resume_uses_durable_events", "test_good_scenario_review_passes", "test_known_bad_scenarios_are_required"),
        ("obligation:loop-liveness", "loops require progress and bounds", "loops_require_progress_and_a_finite_bound", "test_good_scenario_review_passes", "test_known_bad_scenarios_are_required"),
        ("obligation:exact-closure", "closure consumes exact current receipts", "closure_consumes_current_exact_receipts", "test_good_scenario_review_passes", "test_known_bad_scenarios_are_required"),
        ("obligation:no-former-authority-success", "failures and former authority residuals stay visible", "failures_and_former_authority_cannot_hide", "test_good_scenario_review_passes", "test_known_bad_scenarios_are_required"),
        ("obligation:portfolio-freshness", "prior graduates remain current", "portfolio_children_remain_current", "test_good_scenario_review_passes", "test_known_bad_scenarios_are_required"),
        ("obligation:depth-native-authority", "depth profiles preserve the target's native owner", "depth_profile_preserves_native_authority", "test_good_scenario_review_passes", "test_known_bad_scenarios_are_required"),
        ("obligation:execution-depth-closure", "closure consumes a current passing execution-depth receipt", "execution_depth_is_current_and_consumed", "test_good_scenario_review_passes", "test_known_bad_scenarios_are_required"),
        ("obligation:unique-depth-evidence", "unrelated depth obligations need unique evidence contribution", "evidence_contribution_is_unique", "test_good_scenario_review_passes", "test_known_bad_scenarios_are_required"),
        ("obligation:project-adoption", "maintained repositories preserve current SkillGuard project guidance", "adopted_projects_keep_skillguard_maintenance_visible", "test_good_scenario_review_passes", "test_known_bad_scenarios_are_required"),
        ("obligation:global-router-handoff", "global routing preserves one typed handoff", "global_router_handoff_is_current", "test_self_host_functions_have_distinct_routes_and_terminals", "test_known_bad_scenarios_are_required"),
        ("obligation:provenance", "canonical installed repository and release provenance stay distinct", "provenance_is_non_downgrade", "test_self_host_functions_have_distinct_routes_and_terminals", "test_known_bad_scenarios_are_required"),
    )
    built = tuple(_obligation(*row) for row in rows)
    return ModelTestAlignmentPlan(
        MODEL_ID,
        obligations=tuple(row[0] for row in built),
        code_contracts=tuple(row[1] for row in built),
        test_evidence=tuple(evidence for row in built for evidence in row[2]),
    )


def build_test_mesh_plan(contract_case_ids: Sequence[str]) -> TestMeshPlan:
    partition_items = (
        TestPartitionItem("scenario-model", "model", owner_suite_id="scenario-suite", ownership="child"),
        TestPartitionItem("behavior-ledger", "behavior", owner_suite_id="bcl-suite", ownership="child"),
        TestPartitionItem("primary-path", "route", owner_suite_id="ppa-suite", ownership="child"),
        TestPartitionItem("contract-exhaustion", "invariant", owner_suite_id="cem-suite", ownership="child"),
        TestPartitionItem("model-test-alignment", "evidence", owner_suite_id="mta-suite", ownership="child"),
    )
    child_suites = (
        TestSuiteEvidence("scenario-suite", command=f"python -m pytest {TEST_PATH} -q", result_status="passed", evidence_tier="abstract_green", test_count=2, selected_count=2, exit_code=0, result_path=TEST_PATH, owns_state=("contract_run_state",)),
        TestSuiteEvidence("bcl-suite", command=f"python -m pytest {TEST_PATH} -q", result_status="passed", evidence_tier="abstract_green", test_count=1, selected_count=1, exit_code=0, result_path=TEST_PATH, owns_state=("behavior_commitments",)),
        TestSuiteEvidence("ppa-suite", command=f"python -m pytest {TEST_PATH} -q", result_status="passed", evidence_tier="abstract_green", test_count=1, selected_count=1, exit_code=0, result_path=TEST_PATH, owns_state=("path_authority",)),
        TestSuiteEvidence("cem-suite", command=f"python -m pytest {TEST_PATH} -q", result_status="passed", evidence_tier="abstract_green", test_count=1, selected_count=1, exit_code=0, result_path=TEST_PATH, owns_state=("contract_case_space",), owned_leaf_cell_ids=tuple(contract_case_ids)),
        TestSuiteEvidence("mta-suite", command=f"python -m pytest {TEST_PATH} -q", result_status="passed", evidence_tier="abstract_green", test_count=1, selected_count=1, exit_code=0, result_path=TEST_PATH, owns_state=("model_test_bindings",)),
    )
    derivation = TestTargetSplitDerivation(
        MODEL_ID,
        target_suite_ids=tuple(suite.suite_id for suite in child_suites),
        covered_partition_item_ids=tuple(item.item_id for item in partition_items),
        state_owner_fields=(
            "contract_run_state",
            "behavior_commitments",
            "path_authority",
            "contract_case_space",
            "model_test_bindings",
        ),
        source_model_path=MODEL_PATH,
        rationale="separate scenario, BCL, PPA, CEM, and MTA evidence owners while the parent consumes their results",
    )
    return TestMeshPlan(
        "skillguard-v2-model-testmesh",
        partition_items=partition_items,
        child_suites=child_suites,
        target_split_derivation=derivation,
        required_leaf_cell_ids=tuple(contract_case_ids),
        required_evidence_tier="abstract_green",
        decision_scope="enforced",
    )


def run_governance_reviews() -> dict[str, object]:
    cem_report = review_contract_exhaustion(build_contract_exhaustion_plan())
    return {
        "behavior_commitment_ledger": review_behavior_commitment_ledger(build_behavior_commitment_ledger()),
        "primary_path_authority": review_primary_path_authority(build_primary_path_authority_plan()),
        "contract_exhaustion": cem_report,
        "model_test_alignment": review_model_test_alignment(build_model_test_alignment_plan()),
        "test_mesh": review_test_mesh(
            build_test_mesh_plan(tuple(case.case_id for case in cem_report.generated_cases))
        ),
    }


def all_reports() -> dict[str, object]:
    return {"scenarios": run_scenario_review(), **run_governance_reviews()}


def reports_ok(reports: Iterable[object]) -> bool:
    return all(bool(getattr(report, "ok", False)) for report in reports)


def main() -> int:
    reports = all_reports()
    for name, report in reports.items():
        print(f"=== {name} ===")
        print(report.format_text())
    return 0 if reports_ok(reports.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
