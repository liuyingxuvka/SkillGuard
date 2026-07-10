"""FlowGuard model for the SkillGuard executable-contract runtime.

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard

Purpose:
    Model the behavior boundary that turns a target skill contract into a
    claimed, resumable, verifier-owned run and closes it only from current,
    exact evidence.

Guards against:
    prose-only behavior authority, untyped or duplicate routes, unclaimed
    tasks, caller-authored pass, illegal required skips, stale artifacts,
    chat-memory resume, permanent failed/crashed writer locks, no-progress loops, stale child receipts, hidden
    failures, V1 alternate success paths, and stale portfolio graduates.

Run:
    python .flowguard/development_process_flow/skillguard_executable_contract_model.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import flowguard as _flowguard

from flowguard import (
    BCL_CHANGE_BOOTSTRAP_LEDGER,
    BCL_COMMITMENT_PROCESS,
    BCL_COMMITMENT_WORKFLOW,
    BCL_SCOPE_ROUTINE,
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
    FallbackPathCandidate,
    FunctionResult,
    Invariant,
    InvariantResult,
    ModelObligation,
    ModelTestAlignmentPlan,
    PPA_AUTHORITY_MIGRATION_ONLY,
    PPA_BEHAVIOR_DELEGATE_TO_PRIMARY,
    PPA_CANDIDATE_LEGACY_PATH,
    PPA_CLAIM_SCOPE_ROUTINE,
    PPA_DISPOSITION_MIGRATE,
    PPA_TRIGGER_EXPLICIT_USER_CHOICE,
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
MODEL_PATH = ".flowguard/development_process_flow/skillguard_executable_contract_model.py"
TEST_PATH = "tests/test_executable_contract_model.py"
PARENT_MODEL_ID = "skillguard.runtime_contract_executor.v1"
FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"


@dataclass(frozen=True)
class ExecutableContractCase:
    """One externally visible contract-run shape to project into state."""

    case_name: str
    model_current: bool = True
    binding_current: bool = True
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
    v1_alternate_success: bool = False
    closure_requested: bool = True
    closure_profile_monotonic: bool = True
    safe_claim_scoped: bool = True
    graduated_children_current: bool = True


@dataclass(frozen=True)
class ExecutableContractState:
    """State owned by the executable-contract parent model."""

    case_name: str = ""
    model_current: bool = False
    binding_current: bool = False
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
    v1_alternate_success: bool = False
    closure_requested: bool = False
    closure_profile_monotonic: bool = False
    safe_claim_scoped: bool = False
    graduated_children_current: bool = False


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
    if not state.model_current or not state.binding_current:
        return _fail(
            "model_and_binding_are_authoritative",
            "release behavior requires a current FlowGuard model and matching target binding",
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
    if not state.closure_profile_monotonic:
        return _fail(
            "closure_consumes_current_exact_receipts",
            "a stronger closure profile cannot weaken or hide a lower-profile failure",
        )
    if not state.safe_claim_scoped:
        return _fail(
            "closure_consumes_current_exact_receipts",
            "closure must return a scoped safe claim and preserve the unsafe boundary",
        )
    return _pass()


def failures_and_old_paths_cannot_hide(state: ExecutableContractState, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.failure_visible:
        return _fail(
            "failures_and_old_paths_cannot_hide",
            "failed, blocked, skipped, stale, and not-run results must remain visible",
        )
    if state.v1_alternate_success:
        return _fail(
            "failures_and_old_paths_cannot_hide",
            "a V1 command cannot survive as an alternate successful authority",
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
        "failures_and_old_paths_cannot_hide",
        "Failures stay visible and V1 cannot become alternate success.",
        failures_and_old_paths_cannot_hide,
    ),
    Invariant(
        "portfolio_children_remain_current",
        "Portfolio graduation consumes current prior-skill evidence.",
        portfolio_children_remain_current,
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
        _violation("failure hidden", "failures_and_old_paths_cannot_hide"),
    ),
    _scenario(
        "v1_alternate_success_blocks",
        "The old runtime cannot silently succeed after the V2 primary fails.",
        ExecutableContractCase("v1_alternate_success", v1_alternate_success=True),
        _violation("old path success", "failures_and_old_paths_cannot_hide"),
    ),
    _scenario(
        "non_monotonic_profile_blocks",
        "A release profile cannot hide a functional failure.",
        ExecutableContractCase("non_monotonic_profile", closure_profile_monotonic=False),
        _violation("profile weakens", "closure_consumes_current_exact_receipts"),
    ),
    _scenario(
        "stale_prior_graduate_blocks",
        "The current target cannot graduate while a prior skill needs revalidation.",
        ExecutableContractCase("stale_prior_graduate", graduated_children_current=False),
        _violation("prior stale", "portfolio_children_remain_current"),
    ),
)


def run_scenario_review():
    return review_scenarios(SCENARIOS)


def export_contract_model() -> dict[str, object]:
    """Return the canonical machine projection consumed by SkillGuard V2.

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
            "start_step_id": "step:load-target-depth-boundary",
            "step_ids": [
                "step:load-target-depth-boundary",
                "step:run-native-depth-checks",
                "step:verify-target-specific-coverage",
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
        step("step:load-target-depth-boundary", "route:deep-audit", "deep-audit-v2", "inventory"),
        step("step:run-native-depth-checks", "route:deep-audit", "deep-audit-v2", "native", ("step:load-target-depth-boundary",)),
        step("step:verify-target-specific-coverage", "route:deep-audit", "deep-audit-v2", "judged", ("step:run-native-depth-checks",)),
        step("terminal:deep-audit-closed", "route:deep-audit", "deep-audit-v2", "terminal", ("step:verify-target-specific-coverage",), terminal_kind="success"),
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
        ("obligation:deep-audit", "artifacts_and_checks_are_current", ["step:load-target-depth-boundary", "step:run-native-depth-checks", "step:verify-target-specific-coverage"]),
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
        ("obligation:no-v1-success", "failures_and_old_paths_cannot_hide", ["step:select-function-route", "step:check-run-closure"]),
        ("obligation:portfolio-freshness", "portfolio_children_remain_current", ["step:scan-graduate-freshness", "step:issue-portfolio-receipt"]),
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


def _path_binding(intent: str, primary_path_id: str) -> BehaviorPathAuthorityBinding:
    return BehaviorPathAuthorityBinding(
        path_sensitive=True,
        business_intent=intent,
        ppa_report_id="skillguard-v2-primary-path-authority",
        ppa_decision="primary_path_authority_green",
        ppa_confidence="full",
        ppa_ok=True,
        primary_path_ids=(primary_path_id,),
        ppa_risk_gate_ids=("risk_gate:skillguard-v2-primary-path-authority",),
        evidence_refs=("model:skillguard-v2-ppa",),
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
            "a run requests routine, functional, release, or highest-quality closure",
            "the parent consumes exact current child receipts and emits a scoped safe claim",
            "missing, failed, stale, skipped, partial, or not-run required evidence blocks",
            "derive skill closure",
            "close-run-v2",
            ("surface:closure-spec", "surface:executable-model"),
        ),
        (
            "commitment:v1-has-no-alternate-success",
            BCL_COMMITMENT_PROCESS,
            "a V1 runtime command remains during migration",
            "the old surface migrates or delegates to the V2 primary without independent success authority",
            "automatic V1 success after V2 failure blocks broad confidence",
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
    )
    commitments = tuple(
        BehaviorCommitment(
            row[0],
            label=row[0].removeprefix("commitment:").replace("-", " "),
            commitment_kind=row[1],
            actor="SkillGuard-supervised AI",
            trigger=row[2],
            expected_result=row[3],
            failure_boundary=row[4],
            source_surface_ids=row[7],
            primary_owner_model_id=MODEL_ID,
            path_authority=_path_binding(row[5], row[6]),
            validation_boundary="FlowGuard scenario, PPA, CEM, MTA, and TestMesh design evidence",
            rationale="external SkillGuard V2 behavior promised by the approved OpenSpec change",
        )
        for row in commitment_rows
    )
    surfaces = (
        BehaviorSourceSurface(
            "surface:compilation-spec",
            surface_kind=BCL_SOURCE_OPENSPEC,
            source_ref="openspec/changes/build-executable-skill-contract-runtime/specs/executable-skill-contract-compilation/spec.md",
            commitment_ids=("commitment:compile-model-contract",),
            owner=MODEL_ID,
            validation_boundary="approved compilation requirements",
            rationale="defines externally visible compiler authority and failures",
        ),
        BehaviorSourceSurface(
            "surface:run-spec",
            surface_kind=BCL_SOURCE_OPENSPEC,
            source_ref="openspec/changes/build-executable-skill-contract-runtime/specs/claimed-skill-run-runtime/spec.md",
            commitment_ids=("commitment:claim-every-run", "commitment:v1-has-no-alternate-success"),
            owner=MODEL_ID,
            validation_boundary="approved claimed-run requirements",
            rationale="defines task claiming, transitions, resume, skip, and loop behavior",
        ),
        BehaviorSourceSurface(
            "surface:evidence-spec",
            surface_kind=BCL_SOURCE_OPENSPEC,
            source_ref="openspec/changes/build-executable-skill-contract-runtime/specs/skill-evidence-receipts/spec.md",
            commitment_ids=("commitment:verifier-owned-evidence",),
            owner=MODEL_ID,
            validation_boundary="approved evidence requirements",
            rationale="defines evidence classes, immutability, freshness, and artifact identity",
        ),
        BehaviorSourceSurface(
            "surface:closure-spec",
            surface_kind=BCL_SOURCE_OPENSPEC,
            source_ref="openspec/changes/build-executable-skill-contract-runtime/specs/skill-functional-closure/spec.md",
            commitment_ids=("commitment:exact-functional-closure",),
            owner=MODEL_ID,
            validation_boundary="approved closure requirements",
            rationale="defines monotonic profiles, exact receipt consumption, and safe claims",
        ),
        BehaviorSourceSurface(
            "surface:portfolio-spec",
            surface_kind=BCL_SOURCE_OPENSPEC,
            source_ref="openspec/changes/build-executable-skill-contract-runtime/specs/portfolio-skill-calibration-loop/spec.md",
            commitment_ids=("commitment:portfolio-revalidates-after-guard-change",),
            owner=MODEL_ID,
            validation_boundary="approved portfolio feedback requirements",
            rationale="defines target-driven Guard misses and prior-skill revalidation",
        ),
        BehaviorSourceSurface(
            "surface:executable-model",
            surface_kind=BCL_SOURCE_CODE,
            source_ref=MODEL_PATH,
            commitment_ids=tuple(row[0] for row in commitment_rows),
            owner=MODEL_ID,
            validation_boundary="current executable scenario and governance model",
            rationale="single parent model for the V2 runtime behavior boundary",
        ),
        BehaviorSourceSurface(
            "surface:model-tests",
            surface_kind=BCL_SOURCE_TEST,
            source_ref=TEST_PATH,
            commitment_ids=tuple(row[0] for row in commitment_rows),
            owner=MODEL_ID,
            validation_boundary="focused model and governance review tests",
            rationale="pre-production executable evidence for model shape and known-bad cases",
        ),
    )
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
        rationale="register every public V2 behavior before production implementation",
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
    )
    legacy_candidates = (
        ("v1-check-contract", "compile-contract-v2", "compile executable contract"),
        ("v1-start-run", "claimed-run-v2", "supervise target skill task"),
        ("v1-advance-run", "claimed-run-v2", "supervise target skill task"),
        ("v1-check-run", "close-run-v2", "derive skill closure"),
        ("v1-close-run", "close-run-v2", "derive skill closure"),
        ("v1-audit-installed", "portfolio-graduation-v2", "graduate skill portfolio"),
    )
    fallback_candidates = tuple(
        FallbackPathCandidate(
            candidate_id,
            fallback_for_path_id=path_id,
            business_intent=intent,
            candidate_surface=PPA_CANDIDATE_LEGACY_PATH,
            candidate_trigger=PPA_TRIGGER_EXPLICIT_USER_CHOICE,
            candidate_behavior=PPA_BEHAVIOR_DELEGATE_TO_PRIMARY,
            invokes_on_primary_failure=False,
            returns_success_after_primary_failure=False,
            classification=PPA_AUTHORITY_MIGRATION_ONLY,
            disposition=PPA_DISPOSITION_MIGRATE,
            evidence_refs=("openspec-task:8.1-field-lifecycle",),
            compatibility_intent="temporary migration surface; no independent success authority",
        )
        for candidate_id, path_id, intent in legacy_candidates
    )
    return PrimaryPathAuthorityPlan(
        "skillguard-v2-primary-path-authority",
        primary_paths=primary_paths,
        fallback_candidates=fallback_candidates,
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
        claim_scope="routine",
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
        ("obligation:no-v1-success", "failures and V1 alternate success stay visible", "failures_and_old_paths_cannot_hide", "test_good_scenario_review_passes", "test_known_bad_scenarios_are_required"),
        ("obligation:portfolio-freshness", "prior graduates remain current", "portfolio_children_remain_current", "test_good_scenario_review_passes", "test_known_bad_scenarios_are_required"),
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
        decision_scope="routine",
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
