"""Executable FlowGuard model for the reviewed portfolio replacement boundary."""

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


MODEL_ID = "skillguard.portfolio_scope_lifecycle.current"
ACTIVE_LIFECYCLES = frozenset(
    {"active_owned", "active_adopted", "pending_adoption"}
)
CLAIM_BOUNDARY = (
    "A pass proves only the modeled user-confirmed portfolio replacement, "
    "superseded-skill installation/router absence, preserved exclusion, and "
    "direct current-registry replacement, maintenance-unit isolation, and "
    "single-writer boundary. It does not rewrite or transfer a receipt, run "
    "target checks, install a skill, refresh a router, graduate the portfolio, "
    "or prove release readiness."
)


@dataclass(frozen=True)
class PortfolioScopeObservation:
    """One immutable reviewed-scope observation."""

    case_name: str
    replacement_skill_id: str = "logic-writing"
    replacement_lifecycle: str = "active_owned"
    superseded_skill_ids: tuple[str, ...] = (
        "research-investigation-workflow",
        "academic-thesis-revision-workflow",
    )
    retired_skill_ids: tuple[str, ...] = (
        "research-investigation-workflow",
        "academic-thesis-revision-workflow",
    )
    superseded_by_pairs: tuple[tuple[str, str], ...] = (
        ("research-investigation-workflow", "logic-writing"),
        ("academic-thesis-revision-workflow", "logic-writing"),
    )
    installation_absent_skill_ids: tuple[str, ...] = (
        "research-investigation-workflow",
        "academic-thesis-revision-workflow",
    )
    router_blocked_skill_ids: tuple[str, ...] = (
        "research-investigation-workflow",
        "academic-thesis-revision-workflow",
    )
    preserved_excluded_skill_ids: tuple[str, ...] = ("databank-workflow",)
    active_skill_ids: tuple[str, ...] = ("logic-writing",)
    scope_revision: int = 2
    downstream_registry_scope_revision: int = 1
    downstream_evidence_rewritten: bool = False
    direct_registry_replacement: bool = True
    replacement_registry_revision: int = 1
    replacement_registry_scope_revision: int = 2
    prior_registry_consumed: bool = False
    historical_green_evidence_carried: bool = False
    cross_unit_reuse_ticket_present: bool = False
    shared_evidence_root_present: bool = False
    prior_unit_graduation_gate_enabled: bool = False
    maintenance_unit_ids: tuple[str, ...] = ("unit:logic-writing",)
    active_entries_require_fresh_evidence: bool = True
    registry_lock_acquired_before_write: bool = True
    live_registry_writer_present: bool = False
    registry_write_committed: bool = True


@dataclass(frozen=True)
class PortfolioScopeState(PortfolioScopeObservation):
    case_name: str = ""


class EvaluatePortfolioScope:
    """PortfolioScopeObservation x State -> Set(Output x State)."""

    name = "EvaluatePortfolioScope"
    reads = ("PortfolioScopeState",)
    writes = tuple(PortfolioScopeState.__dataclass_fields__)
    accepted_input_type = PortfolioScopeObservation
    input_description = "one frozen reviewed portfolio-scope observation"
    output_description = "replacement lifecycle and downstream freshness facts"
    idempotency = "the same immutable observation produces the same state"

    def apply(
        self,
        input_obj: PortfolioScopeObservation,
        _state: PortfolioScopeState,
    ) -> tuple[FunctionResult, ...]:
        return (
            FunctionResult(
                output=input_obj,
                new_state=PortfolioScopeState(**input_obj.__dict__),
                label=input_obj.case_name,
                reason="projected the reviewed portfolio replacement boundary",
            ),
        )


def _pass() -> InvariantResult:
    return InvariantResult.pass_()


def _fail(name: str, message: str) -> InvariantResult:
    return InvariantResult.fail(message, {"violation": name})


def _empty(state: PortfolioScopeState) -> bool:
    return not state.case_name


def replacement_is_the_only_active_owner(
    state: PortfolioScopeState, _trace: object
) -> InvariantResult:
    if _empty(state):
        return _pass()
    if (
        state.replacement_lifecycle not in ACTIVE_LIFECYCLES
        or state.replacement_skill_id not in state.active_skill_ids
        or any(skill_id in state.active_skill_ids for skill_id in state.superseded_skill_ids)
    ):
        return _fail(
            "replacement_is_the_only_active_owner",
            "the replacement must be active and every superseded skill must be non-active",
        )
    return _pass()


def supersession_tuple_is_complete(
    state: PortfolioScopeState, _trace: object
) -> InvariantResult:
    if _empty(state):
        return _pass()
    superseded = set(state.superseded_skill_ids)
    pairs = dict(state.superseded_by_pairs)
    if (
        set(state.retired_skill_ids) != superseded
        or set(pairs) != superseded
        or any(pairs[skill_id] != state.replacement_skill_id for skill_id in superseded)
        or set(state.installation_absent_skill_ids) != superseded
        or set(state.router_blocked_skill_ids) != superseded
    ):
        return _fail(
            "supersession_tuple_is_complete",
            "every superseded skill must be retired, point to the replacement, and have no install/router authority",
        )
    return _pass()


def exclusions_do_not_enter_active_order(
    state: PortfolioScopeState, _trace: object
) -> InvariantResult:
    if _empty(state):
        return _pass()
    if set(state.preserved_excluded_skill_ids) & set(state.active_skill_ids):
        return _fail(
            "exclusions_do_not_enter_active_order",
            "an explicitly excluded target cannot enter the active order",
        )
    return _pass()


def changed_scope_stales_downstream_evidence(
    state: PortfolioScopeState, _trace: object
) -> InvariantResult:
    if _empty(state):
        return _pass()
    if state.scope_revision <= state.downstream_registry_scope_revision:
        return _fail(
            "changed_scope_stales_downstream_evidence",
            "the modeled replacement requires a newer reviewed scope revision",
        )
    if state.downstream_evidence_rewritten:
        return _fail(
            "changed_scope_stales_downstream_evidence",
            "the scope owner must not rewrite registry, impact, or frozen-plan evidence",
        )
    return _pass()


def current_registry_is_direct_replacement(
    state: PortfolioScopeState, _trace: object
) -> InvariantResult:
    if _empty(state):
        return _pass()
    if (
        not state.direct_registry_replacement
        or state.replacement_registry_revision != 1
        or state.replacement_registry_scope_revision != state.scope_revision
        or state.prior_registry_consumed
        or state.historical_green_evidence_carried
        or not state.active_entries_require_fresh_evidence
    ):
        return _fail(
            "current_registry_is_direct_replacement",
            "the current registry must be revision one from the exact current scope, consume no prior registry, and require fresh active-target evidence",
        )
    return _pass()


def registry_replacement_is_single_writer(
    state: PortfolioScopeState, _trace: object
) -> InvariantResult:
    if _empty(state):
        return _pass()
    if state.registry_write_committed and (
        not state.registry_lock_acquired_before_write
        or state.live_registry_writer_present
    ):
        return _fail(
            "registry_replacement_is_single_writer",
            "a direct registry replacement may commit only after acquiring the sole writer lock and never while another live writer owns it",
        )
    return _pass()


def maintenance_units_own_their_evidence(
    state: PortfolioScopeState, _trace: object
) -> InvariantResult:
    if _empty(state):
        return _pass()
    if (
        not state.maintenance_unit_ids
        or len(set(state.maintenance_unit_ids)) != len(state.maintenance_unit_ids)
        or state.cross_unit_reuse_ticket_present
        or state.shared_evidence_root_present
        or state.prior_unit_graduation_gate_enabled
    ):
        return _fail(
            "maintenance_units_own_their_evidence",
            "Portfolio may summarize independent units but cannot share evidence, issue reuse tickets, or gate one unit on prior graduates",
        )
    return _pass()


INVARIANTS = (
    Invariant(
        "replacement_is_the_only_active_owner",
        "Only the merged replacement remains active.",
        replacement_is_the_only_active_owner,
    ),
    Invariant(
        "supersession_tuple_is_complete",
        "Superseded skills are retired and have zero install/router authority.",
        supersession_tuple_is_complete,
    ),
    Invariant(
        "exclusions_do_not_enter_active_order",
        "Explicit exclusions remain outside the active order.",
        exclusions_do_not_enter_active_order,
    ),
    Invariant(
        "changed_scope_stales_downstream_evidence",
        "A new scope revision stales rather than rewrites downstream evidence.",
        changed_scope_stales_downstream_evidence,
    ),
    Invariant(
        "current_registry_is_direct_replacement",
        "Current registry authority is rebuilt directly without old green evidence.",
        current_registry_is_direct_replacement,
    ),
    Invariant(
        "registry_replacement_is_single_writer",
        "Direct replacement cannot overwrite a live registry writer.",
        registry_replacement_is_single_writer,
    ),
    Invariant(
        "maintenance_units_own_their_evidence",
        "Every maintenance unit graduates from its own evidence.",
        maintenance_units_own_their_evidence,
    ),
)

WORKFLOW = Workflow((EvaluatePortfolioScope(),), name=MODEL_ID)


def _scenario(
    case: PortfolioScopeObservation,
    *,
    expected_status: str,
    violation_names: tuple[str, ...] = (),
) -> Scenario:
    return Scenario(
        name=case.case_name,
        description=case.case_name.replace("_", " "),
        initial_state=PortfolioScopeState(),
        external_input_sequence=(case,),
        expected=ScenarioExpectation(
            expected_status=expected_status,
            expected_violation_names=violation_names,
            required_trace_labels=(case.case_name,),
            summary=case.case_name.replace("_", " "),
        ),
        workflow=WORKFLOW,
        invariants=INVARIANTS,
    )


GOOD = PortfolioScopeObservation("merged_writing_scope_is_current")
SCENARIOS = (
    _scenario(GOOD, expected_status="ok"),
    _scenario(
        replace(
            GOOD,
            case_name="old_skill_cannot_remain_active",
            active_skill_ids=("logic-writing", "research-investigation-workflow"),
        ),
        expected_status="violation",
        violation_names=("replacement_is_the_only_active_owner",),
    ),
    _scenario(
        replace(
            GOOD,
            case_name="superseded_skill_cannot_remain_installed",
            installation_absent_skill_ids=("research-investigation-workflow",),
        ),
        expected_status="violation",
        violation_names=("supersession_tuple_is_complete",),
    ),
    _scenario(
        replace(
            GOOD,
            case_name="superseded_skill_cannot_keep_router_authority",
            router_blocked_skill_ids=("academic-thesis-revision-workflow",),
        ),
        expected_status="violation",
        violation_names=("supersession_tuple_is_complete",),
    ),
    _scenario(
        replace(
            GOOD,
            case_name="databank_cannot_enter_active_order",
            active_skill_ids=("logic-writing", "databank-workflow"),
        ),
        expected_status="violation",
        violation_names=("exclusions_do_not_enter_active_order",),
    ),
    _scenario(
        replace(
            GOOD,
            case_name="scope_owner_cannot_rewrite_downstream_evidence",
            downstream_evidence_rewritten=True,
        ),
        expected_status="violation",
        violation_names=("changed_scope_stales_downstream_evidence",),
    ),
    _scenario(
        replace(
            GOOD,
            case_name="old_registry_cannot_be_migration_authority",
            prior_registry_consumed=True,
        ),
        expected_status="violation",
        violation_names=("current_registry_is_direct_replacement",),
    ),
    _scenario(
        replace(
            GOOD,
            case_name="old_green_evidence_cannot_cross_replacement",
            historical_green_evidence_carried=True,
        ),
        expected_status="violation",
        violation_names=("current_registry_is_direct_replacement",),
    ),
    _scenario(
        replace(
            GOOD,
            case_name="replacement_must_bind_exact_current_scope",
            replacement_registry_scope_revision=1,
        ),
        expected_status="violation",
        violation_names=("current_registry_is_direct_replacement",),
    ),
    _scenario(
        replace(
            GOOD,
            case_name="live_registry_writer_cannot_be_overwritten",
            registry_lock_acquired_before_write=False,
            live_registry_writer_present=True,
            registry_write_committed=True,
        ),
        expected_status="violation",
        violation_names=("registry_replacement_is_single_writer",),
    ),
    _scenario(
        replace(
            GOOD,
            case_name="cross_unit_proof_transfer_blocks",
            cross_unit_reuse_ticket_present=True,
            shared_evidence_root_present=True,
            prior_unit_graduation_gate_enabled=True,
        ),
        expected_status="violation",
        violation_names=("maintenance_units_own_their_evidence",),
    ),
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = review_scenarios(SCENARIOS)
    if args.json:
        print(
            json.dumps(
                {
                    "schema_version": "skillguard.portfolio_scope_lifecycle_model.current",
                    "flowguard_schema_version": str(flowguard.SCHEMA_VERSION),
                    "model_id": MODEL_ID,
                    "status": "pass" if report.ok else "fail",
                    "function_block_contract": (
                        "PortfolioScopeObservation x PortfolioScopeState -> "
                        "Set(Output x PortfolioScopeState)"
                    ),
                    "field_lifecycle": {
                        "logic-writing": "active_owned replacement",
                        "research-investigation-workflow": "retired/superseded",
                        "academic-thesis-revision-workflow": "retired/superseded",
                        "databank-workflow": "preserved excluded",
                        "previous-registry": "disposed residual, never input authority",
                        "replacement-registry": "revision one bound to current scope",
                        "replacement-registry-writer": "sole lock owner before commit",
                        "active-target-evidence": "pending or revalidation required",
                        "maintenance-unit-evidence": "independent; no reuse ticket or shared proof root",
                        "impact-frozen-plans": "stale downstream evidence",
                    },
                    "scenario_review": report.to_dict(),
                    "claim_boundary": CLAIM_BOUNDARY,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(report.format_text())
        print(f"claim_boundary: {CLAIM_BOUNDARY}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
