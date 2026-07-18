"""Executable FlowGuard model for SkillGuard's one current authority path."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, replace

import flowguard
from flowguard import (
    FunctionResult,
    Invariant,
    InvariantResult,
    Scenario,
    ScenarioExpectation,
    Workflow,
)
from flowguard.review import review_scenarios


FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"
MODEL_ID = "skillguard.current_runtime_authority.current"
AUTHORITY_CURRENT = "current"
AUTHORITY_BLOCKED = "blocked"
AUTHORITY_DECISIONS = frozenset({AUTHORITY_CURRENT, AUTHORITY_BLOCKED})
CONSUMER_CLEAN = "clean"
CONSUMER_BLOCKED = "blocked"
CONSUMER_DISTRIBUTION_DECISIONS = frozenset({CONSUMER_CLEAN, CONSUMER_BLOCKED})

FORMER_RUN_RECORD_SCHEMA = "skillguard.run_record.v1"
FORMER_EXACT_PATHS = frozenset(
    {
        ".skillguard/work-contract.json",
        ".skillguard/check_manifest.json",
        ".skillguard/v1-retirement-eligibility-receipt.json",
        ".skillguard/v1-retirement-completion-receipt.json",
        "scripts/skillguard_v1_retirement.py",
        "scripts/skillguard_legacy_depth_upgrade.py",
        "scripts/skillguard_v2/field_lifecycle.py",
        "assets/schemas/skillguard_work_contract.schema.json",
        "assets/schemas/skillguard_run_record.schema.json",
        "assets/schemas/skillguard_check_manifest.schema.json",
        "assets/schemas/skillguard_v1_retirement_eligibility_receipt_v1.schema.json",
        "assets/schemas/skillguard_v1_retirement_completion_receipt_v1.schema.json",
    }
)
FORMER_HISTORY_PREFIX = ".skillguard/v1r/"

CLAIM_BOUNDARY = (
    "A passing review proves only the modeled current-or-blocked author "
    "authority, former-surface rejection, direct-replacement gates, clean "
    "consumer-distribution separation, and bounded author claims. It does not "
    "edit files, execute target-domain work, install packages, publish, or "
    "prove future AI behavior."
)


def _normalize(path: str) -> str:
    return path.replace("\\", "/").strip("/").casefold()


def exact_former_runtime_residuals(
    observed_paths: tuple[str, ...],
    flat_run_schema_by_path: tuple[tuple[str, str], ...] = (),
) -> tuple[str, ...]:
    """Return only named former product surfaces and flat old run records."""

    exact = {_normalize(path) for path in FORMER_EXACT_PATHS}
    residuals: set[str] = set()
    for raw_path in observed_paths:
        path = _normalize(raw_path)
        if path in exact or path.startswith(FORMER_HISTORY_PREFIX):
            residuals.add(path)
    for raw_path, schema_id in flat_run_schema_by_path:
        path = _normalize(raw_path)
        parts = path.split("/")
        if (
            len(parts) == 3
            and parts[:2] == [".skillguard", "runs"]
            and path.endswith(".json")
            and schema_id == FORMER_RUN_RECORD_SCHEMA
        ):
            residuals.add(path)
    return tuple(sorted(residuals))


@dataclass(frozen=True)
class CurrentAuthorityCase:
    """One immutable direct-maintenance observation."""

    case_name: str
    authority_decisions: tuple[str, ...] = (AUTHORITY_CURRENT,)
    contract_source_current: bool = True
    compiled_contract_current: bool = True
    exact_manifest_current: bool = True
    identity_bindings_current: bool = True
    impact_plan_current: bool = True
    old_lifecycle_fields_present: bool = False
    old_pair_only: bool = False
    observed_paths: tuple[str, ...] = ()
    flat_run_schema_by_path: tuple[tuple[str, str], ...] = ()
    former_command_requested: bool = False
    former_handler_invoked: bool = False
    former_command_wrote_files: bool = False
    former_command_exit_code: int = 1
    converter_available: bool = False
    old_shape_read_as_conversion_input: bool = False
    direct_replacement_requested: bool = False
    installation_activated: bool = False
    rejection_fixture_changed: bool = False
    fixture_in_owner_identity: bool = False
    fixture_requires_installation: bool = False
    fixture_admits_full: bool = False
    consumer_distribution_decisions: tuple[str, ...] = (CONSUMER_CLEAN,)
    consumer_carries_authority_decision: bool = False
    consumer_contains_skillguard_control_files: bool = False
    consumer_contains_skillguard_prompt: bool = False
    consumer_contains_skillguard_maintenance_section: bool = False
    consumer_contains_skillguard_receipt: bool = False
    consumer_contains_router_state: bool = False
    authority_claimed: bool = True
    claims_domain_correctness: bool = False
    claims_future_ai_behavior: bool = False
    claims_publication: bool = False
    claims_release_readiness: bool = False


@dataclass(frozen=True)
class CurrentAuthorityState(CurrentAuthorityCase):
    case_name: str = ""


class EvaluateCurrentAuthority:
    """CurrentAuthorityCase x State -> Set(Output x State)."""

    name = "EvaluateCurrentAuthority"
    reads = ("CurrentAuthorityState",)
    writes = tuple(CurrentAuthorityState.__dataclass_fields__)
    accepted_input_type = CurrentAuthorityCase
    input_description = "one frozen current-authority maintenance observation"
    output_description = "current-or-blocked authority plus exact invalidation facts"
    idempotency = "the same immutable observation produces the same state"

    def apply(
        self,
        input_obj: CurrentAuthorityCase,
        _state: CurrentAuthorityState,
    ) -> tuple[FunctionResult, ...]:
        return (
            FunctionResult(
                output=input_obj,
                new_state=CurrentAuthorityState(**input_obj.__dict__),
                label=input_obj.case_name,
                reason="projected the frozen current-authority observation",
            ),
        )


def _pass() -> InvariantResult:
    return InvariantResult.pass_()


def _fail(name: str, message: str) -> InvariantResult:
    return InvariantResult.fail(message, {"violation": name})


def _empty(state: CurrentAuthorityState) -> bool:
    return not state.case_name


def authority_is_current_or_blocked(
    state: CurrentAuthorityState, _trace: object
) -> InvariantResult:
    if _empty(state):
        return _pass()
    if (
        len(state.authority_decisions) != 1
        or state.authority_decisions[0] not in AUTHORITY_DECISIONS
    ):
        return _fail(
            "authority_is_current_or_blocked",
            "daily authority must be exactly current or blocked",
        )
    return _pass()


def current_requires_complete_authority(
    state: CurrentAuthorityState, _trace: object
) -> InvariantResult:
    if _empty(state):
        return _pass()
    authority = (
        state.authority_decisions[0]
        if len(state.authority_decisions) == 1
        else ""
    )
    residuals = exact_former_runtime_residuals(
        state.observed_paths,
        state.flat_run_schema_by_path,
    )
    gates = (
        state.contract_source_current,
        state.compiled_contract_current,
        state.exact_manifest_current,
        state.identity_bindings_current,
        state.impact_plan_current,
        not state.old_lifecycle_fields_present,
        not state.old_pair_only,
        not residuals,
    )
    if authority == AUTHORITY_CURRENT and not all(gates):
        return _fail(
            "current_requires_complete_authority",
            "current requires the exact current trio, impact identity, and clean former-surface scan",
        )
    if authority == AUTHORITY_BLOCKED and all(gates):
        return _fail(
            "current_requires_complete_authority",
            "a completely current target must not remain blocked",
        )
    return _pass()


def former_surfaces_are_rejection_only(
    state: CurrentAuthorityState, _trace: object
) -> InvariantResult:
    if _empty(state):
        return _pass()
    if state.converter_available or state.old_shape_read_as_conversion_input:
        return _fail(
            "former_surfaces_are_rejection_only",
            "no converter or old-shape reader may remain as a maintained route",
        )
    if state.former_command_requested and (
        state.former_handler_invoked
        or state.former_command_wrote_files
        or state.former_command_exit_code == 0
    ):
        return _fail(
            "former_surfaces_are_rejection_only",
            "a former command must fail before a handler, write, or success exit",
        )
    return _pass()


def direct_replacement_controls_activation(
    state: CurrentAuthorityState, _trace: object
) -> InvariantResult:
    if _empty(state) or not state.installation_activated:
        return _pass()
    residuals = exact_former_runtime_residuals(
        state.observed_paths,
        state.flat_run_schema_by_path,
    )
    gates = (
        state.direct_replacement_requested,
        state.authority_decisions == (AUTHORITY_CURRENT,),
        state.contract_source_current,
        state.compiled_contract_current,
        state.exact_manifest_current,
        state.identity_bindings_current,
        state.impact_plan_current,
        not state.old_lifecycle_fields_present,
        not state.old_pair_only,
        not residuals,
    )
    if not all(gates):
        return _fail(
            "direct_replacement_controls_activation",
            "installation may activate only a complete direct current replacement",
        )
    return _pass()


def rejection_fixtures_are_source_only(
    state: CurrentAuthorityState, _trace: object
) -> InvariantResult:
    if _empty(state) or not state.rejection_fixture_changed:
        return _pass()
    if (
        state.fixture_in_owner_identity
        or state.fixture_requires_installation
        or state.fixture_admits_full
    ):
        return _fail(
            "rejection_fixtures_are_source_only",
            "former-shape fixtures cannot stale owners, require install, or admit full",
        )
    return _pass()


def consumer_distributions_are_independent(
    state: CurrentAuthorityState, _trace: object
) -> InvariantResult:
    if _empty(state):
        return _pass()
    decisions = state.consumer_distribution_decisions
    if not decisions or any(
        decision not in CONSUMER_DISTRIBUTION_DECISIONS
        for decision in decisions
    ):
        return _fail(
            "consumer_distributions_are_independent",
            "each consumer distribution must report only clean or blocked",
        )
    if CONSUMER_CLEAN in decisions and state.authority_decisions != (
        AUTHORITY_CURRENT,
    ):
        return _fail(
            "consumer_distributions_are_independent",
            "a clean consumer may be built only from current author authority",
        )
    if any(
        (
            state.consumer_carries_authority_decision,
            state.consumer_contains_skillguard_control_files,
            state.consumer_contains_skillguard_prompt,
            state.consumer_contains_skillguard_maintenance_section,
            state.consumer_contains_skillguard_receipt,
            state.consumer_contains_router_state,
        )
    ):
        return _fail(
            "consumer_distributions_are_independent",
            "a consumer cannot carry SkillGuard authority, control files, author-maintenance sections, prompts, receipts, or router state",
        )
    return _pass()


def authority_claim_is_bounded(
    state: CurrentAuthorityState, _trace: object
) -> InvariantResult:
    if _empty(state) or not state.authority_claimed:
        return _pass()
    if state.authority_decisions != (AUTHORITY_CURRENT,) or any(
        (
            state.claims_domain_correctness,
            state.claims_future_ai_behavior,
            state.claims_publication,
            state.claims_release_readiness,
        )
    ):
        return _fail(
            "authority_claim_is_bounded",
            "current contract authority is not domain, future-behavior, publication, or release proof",
        )
    return _pass()


INVARIANTS = (
    Invariant(
        "authority_is_current_or_blocked",
        "Daily authority has exactly one current-or-blocked result.",
        authority_is_current_or_blocked,
    ),
    Invariant(
        "current_requires_complete_authority",
        "Current requires the exact trio and no former surface.",
        current_requires_complete_authority,
    ),
    Invariant(
        "former_surfaces_are_rejection_only",
        "Former commands and shapes are rejection fixtures only.",
        former_surfaces_are_rejection_only,
    ),
    Invariant(
        "direct_replacement_controls_activation",
        "Only a complete direct current replacement may activate.",
        direct_replacement_controls_activation,
    ),
    Invariant(
        "rejection_fixtures_are_source_only",
        "Rejection fixtures cannot broaden functional invalidation.",
        rejection_fixtures_are_source_only,
    ),
    Invariant(
        "consumer_distributions_are_independent",
        "Consumers contain target-owned runtime only and never project SkillGuard authority.",
        consumer_distributions_are_independent,
    ),
    Invariant(
        "authority_claim_is_bounded",
        "Authority currentness is not target-domain or release proof.",
        authority_claim_is_bounded,
    ),
)

WORKFLOW = Workflow((EvaluateCurrentAuthority(),), name=MODEL_ID)


def _ok(summary: str, label: str) -> ScenarioExpectation:
    return ScenarioExpectation(
        expected_status="ok",
        required_trace_labels=(label,),
        summary=summary,
    )


def _violation(
    summary: str, label: str, *names: str
) -> ScenarioExpectation:
    return ScenarioExpectation(
        expected_status="violation",
        expected_violation_names=tuple(names),
        required_trace_labels=(label,),
        summary=summary,
    )


GOOD_CASE = CurrentAuthorityCase("good_current_authority")


def _scenario(
    case: CurrentAuthorityCase,
    expected: ScenarioExpectation,
) -> Scenario:
    return Scenario(
        name=case.case_name,
        description=expected.summary,
        initial_state=CurrentAuthorityState(),
        external_input_sequence=(case,),
        expected=expected,
        workflow=WORKFLOW,
        invariants=INVARIANTS,
    )


SCENARIOS = (
    _scenario(GOOD_CASE, _ok("the exact current trio resolves current", GOOD_CASE.case_name)),
    _scenario(
        replace(GOOD_CASE, case_name="incomplete_trio_cannot_be_current", compiled_contract_current=False),
        _violation("an incomplete trio cannot claim current", "incomplete_trio_cannot_be_current", "current_requires_complete_authority"),
    ),
    _scenario(
        replace(
            GOOD_CASE,
            case_name="incomplete_direct_replacement_remains_blocked",
            authority_decisions=(AUTHORITY_BLOCKED,),
            consumer_distribution_decisions=(CONSUMER_BLOCKED,),
            contract_source_current=False,
            direct_replacement_requested=True,
            authority_claimed=False,
        ),
        _ok("an incomplete direct replacement remains blocked", "incomplete_direct_replacement_remains_blocked"),
    ),
    _scenario(
        replace(GOOD_CASE, case_name="old_pair_cannot_pass", old_pair_only=True),
        _violation("an old pair cannot provide success", "old_pair_cannot_pass", "current_requires_complete_authority"),
    ),
    _scenario(
        replace(
            GOOD_CASE,
            case_name="retirement_receipt_residual_blocks",
            observed_paths=(".skillguard/v1-retirement-completion-receipt.json",),
        ),
        _violation("a former retirement receipt blocks current", "retirement_receipt_residual_blocks", "current_requires_complete_authority"),
    ),
    _scenario(
        replace(
            GOOD_CASE,
            case_name="conversion_tool_residual_blocks",
            observed_paths=("scripts/skillguard_v1_retirement.py",),
        ),
        _violation("a conversion tool is a former surface", "conversion_tool_residual_blocks", "current_requires_complete_authority"),
    ),
    _scenario(
        replace(GOOD_CASE, case_name="current_nested_run_is_preserved", observed_paths=(".skillguard/runs/current-run/run.json",)),
        _ok("a current nested run is not a former flat record", "current_nested_run_is_preserved"),
    ),
    _scenario(
        replace(GOOD_CASE, case_name="rejection_fixture_change_is_nonfunctional", rejection_fixture_changed=True),
        _ok("a rejection fixture does not stale functional owners", "rejection_fixture_change_is_nonfunctional"),
    ),
    _scenario(
        replace(
            GOOD_CASE,
            case_name="rejection_fixture_cannot_admit_full",
            rejection_fixture_changed=True,
            fixture_in_owner_identity=True,
            fixture_requires_installation=True,
            fixture_admits_full=True,
        ),
        _violation("a rejection fixture cannot broaden validation", "rejection_fixture_cannot_admit_full", "rejection_fixtures_are_source_only"),
    ),
    _scenario(
        replace(GOOD_CASE, case_name="former_command_is_rejected", former_command_requested=True),
        _ok("a former command exits before execution", "former_command_is_rejected"),
    ),
    _scenario(
        replace(
            GOOD_CASE,
            case_name="former_command_handler_invocation_blocks",
            former_command_requested=True,
            former_handler_invoked=True,
            former_command_wrote_files=True,
            former_command_exit_code=0,
        ),
        _violation("a former command cannot reach a handler", "former_command_handler_invocation_blocks", "former_surfaces_are_rejection_only"),
    ),
    _scenario(
        replace(GOOD_CASE, case_name="converter_presence_blocks", converter_available=True),
        _violation("a permanent converter is a second route", "converter_presence_blocks", "former_surfaces_are_rejection_only"),
    ),
    _scenario(
        replace(GOOD_CASE, case_name="direct_replacement_can_activate", direct_replacement_requested=True, installation_activated=True),
        _ok("a complete direct current replacement may activate", "direct_replacement_can_activate"),
    ),
    _scenario(
        replace(
            GOOD_CASE,
            case_name="partial_replacement_cannot_activate",
            authority_decisions=(AUTHORITY_BLOCKED,),
            consumer_distribution_decisions=(CONSUMER_BLOCKED,),
            compiled_contract_current=False,
            direct_replacement_requested=True,
            installation_activated=True,
            authority_claimed=False,
        ),
        _violation("partial replacement cannot activate", "partial_replacement_cannot_activate", "direct_replacement_controls_activation"),
    ),
    _scenario(
        replace(
            GOOD_CASE,
            case_name="independent_consumer_builds_may_differ",
            consumer_distribution_decisions=(CONSUMER_CLEAN, CONSUMER_BLOCKED),
        ),
        _ok(
            "independent consumer builds may report different build outcomes without sharing authority",
            "independent_consumer_builds_may_differ",
        ),
    ),
    _scenario(
        replace(
            GOOD_CASE,
            case_name="consumer_skillguard_projection_blocks",
            consumer_carries_authority_decision=True,
            consumer_contains_skillguard_control_files=True,
            consumer_contains_skillguard_prompt=True,
            consumer_contains_skillguard_receipt=True,
            consumer_contains_router_state=True,
        ),
        _violation(
            "a consumer cannot carry the author system",
            "consumer_skillguard_projection_blocks",
            "consumer_distributions_are_independent",
        ),
    ),
    _scenario(
        replace(
            GOOD_CASE,
            case_name="consumer_author_maintenance_section_blocks",
            consumer_contains_skillguard_maintenance_section=True,
        ),
        _violation(
            "a consumer entrypoint cannot carry an author-maintenance section",
            "consumer_author_maintenance_section_blocks",
            "consumer_distributions_are_independent",
        ),
    ),
    _scenario(
        replace(GOOD_CASE, case_name="authority_claim_overreach_blocks", claims_domain_correctness=True),
        _violation("authority currentness is not domain correctness", "authority_claim_overreach_blocks", "authority_claim_is_bounded"),
    ),
)


def run_scenario_review():
    return review_scenarios(SCENARIOS)


def model_summary() -> dict[str, object]:
    return {
        "schema_version": "skillguard.current_runtime_authority_model.current",
        "flowguard_schema_version": str(flowguard.SCHEMA_VERSION),
        "model_id": MODEL_ID,
        "function_block_contract": (
            "CurrentAuthorityCase x CurrentAuthorityState -> "
            "Set(Output x CurrentAuthorityState)"
        ),
        "authority_decisions": sorted(AUTHORITY_DECISIONS),
        "consumer_distribution_decisions": sorted(
            CONSUMER_DISTRIBUTION_DECISIONS
        ),
        "former_exact_paths": sorted(FORMER_EXACT_PATHS),
        "former_shape_disposition": "rejection_fixture_only",
        "replacement_mode": "direct_current_maintenance_only",
        "invariant_ids": [invariant.name for invariant in INVARIANTS],
        "claim_boundary": CLAIM_BOUNDARY,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Review SkillGuard's one current runtime-authority model."
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = run_scenario_review()
    if args.json:
        payload = model_summary()
        payload["status"] = "pass" if report.ok else "fail"
        payload["scenario_review"] = report.to_dict()
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(report.format_text())
        print(f"claim_boundary: {CLAIM_BOUNDARY}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
