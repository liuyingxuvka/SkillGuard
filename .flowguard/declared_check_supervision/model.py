"""Executable FlowGuard model for generic declared-check supervision.

The target skill owns the meaning and native implementation of every check.
SkillGuard owns only the exact inventory, execution ownership, receipt identity,
result reconciliation, and terminal closure boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Iterable, Mapping

from flowguard import (
    BoundedEventuallyProperty,
    FunctionResult,
    GraphEdge,
    Invariant,
    InvariantResult,
    LoopCheckConfig,
    ProgressCheckConfig,
    Scenario,
    ScenarioExpectation,
    Workflow,
    check_loops,
    check_progress,
)
from flowguard.contract import FunctionContract, check_refinement_projection, check_trace_contracts
from flowguard.review import review_scenarios


FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"
MODEL_ID = "skillguard.declared_check_supervision.current"
PARENT_MODEL_ID = "skillguard.executable_contract_runtime.v2"
MODEL_PATH = ".flowguard/declared_check_supervision/model.py"

STATUS_PASS = "pass"
STATUS_BLOCKED = "blocked"
STATUS_NOT_RUN = "not_run"

CLAIM_BOUNDARY = (
    "A green report proves the finite generic supervision model: a non-empty "
    "target-declared check inventory is frozen exactly, every check has one "
    "declared execution owner, dependencies are valid and acyclic, every result "
    "is a current terminal receipt for the same request and owner, and closure "
    "occurs only after exact reconciliation. It does not judge what a target "
    "check means, invent target checks, or prove a target's domain correctness."
)


@dataclass(frozen=True)
class CheckDeclaration:
    check_id: str
    execution_owner_id: str
    depends_on_check_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    execution_owner_id: str
    request_fingerprint: str
    status: str = STATUS_PASS
    terminal: bool = True
    current: bool = True
    completion_index: int = 1


SINGLE_DECLARATIONS = (CheckDeclaration("check:target:one", "owner:target:one"),)
SINGLE_RESULTS = (
    CheckResult("check:target:one", "owner:target:one", "sha256:request-current", completion_index=1),
)
MULTI_DECLARATIONS = (
    CheckDeclaration("check:target:one", "owner:target:one"),
    CheckDeclaration("check:target:two", "owner:target:two", ("check:target:one",)),
)
MULTI_RESULTS = (
    CheckResult("check:target:one", "owner:target:one", "sha256:request-current", completion_index=1),
    CheckResult("check:target:two", "owner:target:two", "sha256:request-current", completion_index=2),
)
SHARED_OWNER_DECLARATIONS = (
    CheckDeclaration("check:target:one", "owner:target:shared"),
    CheckDeclaration("check:target:two", "owner:target:shared"),
)
SHARED_OWNER_RESULTS = (
    CheckResult("check:target:one", "owner:target:shared", "sha256:request-current", completion_index=1),
    CheckResult("check:target:two", "owner:target:shared", "sha256:request-current", completion_index=1),
)


@dataclass(frozen=True)
class SupervisionCase:
    """One immutable observation of a target skill's declared checks and results."""

    case_name: str
    request_fingerprint: str = "sha256:request-current"
    declared_checks: tuple[CheckDeclaration, ...] = MULTI_DECLARATIONS
    frozen_checks: tuple[CheckDeclaration, ...] = MULTI_DECLARATIONS
    results: tuple[CheckResult, ...] = MULTI_RESULTS
    check_names_interpreted_by_supervisor: bool = False
    force_accept_findings: bool = False


@dataclass(frozen=True)
class SupervisionState:
    """Derived state for the declared-check supervision FunctionBlocks."""

    phase: int = 0
    case: SupervisionCase | None = None
    inventory_status: str = STATUS_NOT_RUN
    ownership_status: str = STATUS_NOT_RUN
    receipt_status: str = STATUS_NOT_RUN
    reconciliation_status: str = STATUS_NOT_RUN
    closure_status: str = STATUS_NOT_RUN
    findings: tuple[str, ...] = ()
    accepted_findings: tuple[str, ...] = ()


@dataclass(frozen=True)
class KnownBadSpec:
    code: str
    family: str
    changes: Mapping[str, Any]


def _result(
    case: SupervisionCase,
    state: SupervisionState,
    label: str,
    reason: str,
) -> tuple[FunctionResult, ...]:
    return (
        FunctionResult(
            output=case,
            new_state=state,
            label=f"{label}:{case.case_name}",
            reason=reason,
        ),
    )


def _advance(
    case: SupervisionCase,
    state: SupervisionState,
    *,
    phase: int,
    findings: tuple[str, ...],
    status_fields: tuple[str, ...],
    label: str,
    reason: str,
) -> tuple[FunctionResult, ...]:
    previous_blocked = bool(state.findings and not state.accepted_findings)
    values: dict[str, Any] = {field: STATUS_NOT_RUN for field in status_fields}
    if previous_blocked:
        return _result(
            case,
            replace(state, phase=phase, case=case, **values),
            f"{label}-not-run",
            "an earlier exact boundary blocked",
        )
    accepted = bool(findings and case.force_accept_findings)
    status = STATUS_PASS if not findings or accepted else STATUS_BLOCKED
    values = {field: status for field in status_fields}
    return _result(
        case,
        replace(
            state,
            phase=phase,
            case=case,
            findings=state.findings + findings,
            accepted_findings=state.accepted_findings + (findings if accepted else ()),
            **values,
        ),
        label,
        reason,
    )


def _has_dependency_cycle(declarations: tuple[CheckDeclaration, ...]) -> bool:
    graph = {row.check_id: row.depends_on_check_ids for row in declarations}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(check_id: str) -> bool:
        if check_id in visiting:
            return True
        if check_id in visited:
            return False
        visiting.add(check_id)
        for dependency_id in graph.get(check_id, ()):
            if dependency_id in graph and visit(dependency_id):
                return True
        visiting.remove(check_id)
        visited.add(check_id)
        return False

    return any(visit(check_id) for check_id in graph)


def _inventory_findings(case: SupervisionCase) -> tuple[str, ...]:
    check_ids = tuple(row.check_id for row in case.declared_checks)
    findings: list[str] = []
    if not case.request_fingerprint:
        findings.append("request_fingerprint_missing")
    if not case.declared_checks:
        findings.append("declared_check_inventory_empty")
    if len(check_ids) != len(set(check_ids)):
        findings.append("declared_check_id_duplicated")
    if not all(check_id.strip() for check_id in check_ids):
        findings.append("declared_check_id_missing")
    if case.frozen_checks != case.declared_checks:
        findings.append("frozen_check_inventory_drift")
    if case.check_names_interpreted_by_supervisor:
        findings.append("check_name_semantics_interpreted")
    return tuple(findings)


def _ownership_findings(case: SupervisionCase) -> tuple[str, ...]:
    declared_ids = {row.check_id for row in case.declared_checks}
    findings: list[str] = []
    if any(not row.execution_owner_id.strip() for row in case.declared_checks):
        findings.append("execution_owner_missing")
    if any(
        dependency_id not in declared_ids
        for row in case.declared_checks
        for dependency_id in row.depends_on_check_ids
    ):
        findings.append("unknown_check_dependency")
    if any(row.check_id in row.depends_on_check_ids for row in case.declared_checks):
        findings.append("self_check_dependency")
    if _has_dependency_cycle(case.declared_checks):
        findings.append("cyclic_check_dependency")
    return tuple(dict.fromkeys(findings))


def _receipt_findings(case: SupervisionCase) -> tuple[str, ...]:
    declarations = {row.check_id: row for row in case.declared_checks}
    result_ids = tuple(row.check_id for row in case.results)
    results = {row.check_id: row for row in case.results}
    findings: list[str] = []
    if len(result_ids) != len(set(result_ids)):
        findings.append("check_result_duplicated")
    for row in case.results:
        declaration = declarations.get(row.check_id)
        if declaration is None:
            findings.append("undeclared_check_result")
            continue
        if row.execution_owner_id != declaration.execution_owner_id:
            findings.append("check_result_owner_mismatch")
        if row.request_fingerprint != case.request_fingerprint:
            findings.append("check_result_request_mismatch")
        if not row.current:
            findings.append("check_result_stale")
        if not row.terminal:
            findings.append("check_result_nonterminal")
        if row.status != STATUS_PASS:
            findings.append("check_result_not_passed")
        for dependency_id in declaration.depends_on_check_ids:
            dependency = results.get(dependency_id)
            if dependency is not None and dependency.completion_index >= row.completion_index:
                findings.append("check_dependency_order_violated")
    return tuple(dict.fromkeys(findings))


def _reconciliation_findings(case: SupervisionCase) -> tuple[str, ...]:
    declared_ids = tuple(row.check_id for row in case.declared_checks)
    result_ids = tuple(row.check_id for row in case.results)
    findings: list[str] = []
    if set(result_ids) != set(declared_ids):
        findings.append("declared_check_results_incomplete")
    if len(result_ids) != len(declared_ids):
        findings.append("declared_check_result_count_mismatch")
    return tuple(findings)


class FreezeDeclaredCheckInventory:
    """SupervisionCase x SupervisionState -> Set(SupervisionCase x SupervisionState)."""

    name = "FreezeDeclaredCheckInventory"
    accepted_input_type = SupervisionCase
    reads = ("request_fingerprint", "declared_checks", "frozen_checks")
    writes = ("phase", "case", "inventory_status", "findings", "accepted_findings")
    idempotency = "one exact declaration inventory has one frozen representation"

    def apply(self, case: SupervisionCase, state: SupervisionState) -> tuple[FunctionResult, ...]:
        return _advance(
            case,
            state,
            phase=1,
            findings=_inventory_findings(case),
            status_fields=("inventory_status",),
            label="declared-check-inventory-frozen",
            reason="froze the target's exact declared check inventory without interpreting names",
        )


class ResolveDeclaredOwnersAndDependencies:
    """SupervisionCase x SupervisionState -> Set(SupervisionCase x SupervisionState)."""

    name = "ResolveDeclaredOwnersAndDependencies"
    accepted_input_type = SupervisionCase
    reads = ("inventory_status", "declared_checks")
    writes = ("phase", "ownership_status", "findings", "accepted_findings")
    idempotency = "one frozen inventory yields one owner and dependency graph"

    def apply(self, case: SupervisionCase, state: SupervisionState) -> tuple[FunctionResult, ...]:
        return _advance(
            case,
            state,
            phase=2,
            findings=_ownership_findings(case),
            status_fields=("ownership_status",),
            label="declared-check-owners-resolved",
            reason="resolved exact execution owners and an acyclic dependency graph",
        )


class AdmitExactTerminalResults:
    """SupervisionCase x SupervisionState -> Set(SupervisionCase x SupervisionState)."""

    name = "AdmitExactTerminalResults"
    accepted_input_type = SupervisionCase
    reads = ("ownership_status", "results", "request_fingerprint")
    writes = ("phase", "receipt_status", "findings", "accepted_findings")
    idempotency = "an immutable terminal result has one check, owner, request, and status identity"

    def apply(self, case: SupervisionCase, state: SupervisionState) -> tuple[FunctionResult, ...]:
        return _advance(
            case,
            state,
            phase=3,
            findings=_receipt_findings(case),
            status_fields=("receipt_status",),
            label="terminal-check-results-admitted",
            reason="admitted only current terminal passed results for their declared owners and request",
        )


class ReconcileDeclaredCheckResults:
    """SupervisionCase x SupervisionState -> Set(SupervisionCase x SupervisionState)."""

    name = "ReconcileDeclaredCheckResults"
    accepted_input_type = SupervisionCase
    reads = ("receipt_status", "declared_checks", "results")
    writes = (
        "phase",
        "reconciliation_status",
        "closure_status",
        "findings",
        "accepted_findings",
    )
    idempotency = "one frozen inventory and result set yields one exact terminal disposition"

    def apply(self, case: SupervisionCase, state: SupervisionState) -> tuple[FunctionResult, ...]:
        outcomes = _advance(
            case,
            state,
            phase=4,
            findings=_reconciliation_findings(case),
            status_fields=("reconciliation_status", "closure_status"),
            label="declared-check-results-reconciled",
            reason="closed only after every declared check had exactly one admitted result",
        )
        result = outcomes[0]
        final_state = result.new_state
        if final_state.findings and not final_state.accepted_findings:
            final_state = replace(final_state, closure_status=STATUS_BLOCKED)
        return (
            FunctionResult(
                output=result.output,
                new_state=final_state,
                label=result.label,
                reason=result.reason,
            ),
        )


BLOCKS = (
    FreezeDeclaredCheckInventory(),
    ResolveDeclaredOwnersAndDependencies(),
    AdmitExactTerminalResults(),
    ReconcileDeclaredCheckResults(),
)
WORKFLOW = Workflow(BLOCKS, name=MODEL_ID)

GOOD_SINGLE = SupervisionCase(
    "good-single-check-target",
    declared_checks=SINGLE_DECLARATIONS,
    frozen_checks=SINGLE_DECLARATIONS,
    results=SINGLE_RESULTS,
)
GOOD_MULTI = SupervisionCase("good-multi-check-target")
GOOD_SHARED_OWNER = SupervisionCase(
    "good-shared-owner-retains-two-semantic-checks",
    declared_checks=SHARED_OWNER_DECLARATIONS,
    frozen_checks=SHARED_OWNER_DECLARATIONS,
    results=SHARED_OWNER_RESULTS,
)

KNOWN_BAD_SPECS = (
    KnownBadSpec("request_fingerprint_missing", "inventory", {"request_fingerprint": ""}),
    KnownBadSpec("declared_check_inventory_empty", "inventory", {"declared_checks": (), "frozen_checks": (), "results": ()}),
    KnownBadSpec("declared_check_id_duplicated", "inventory", {"declared_checks": (MULTI_DECLARATIONS[0], MULTI_DECLARATIONS[0]), "frozen_checks": (MULTI_DECLARATIONS[0], MULTI_DECLARATIONS[0])}),
    KnownBadSpec("declared_check_id_missing", "inventory", {"declared_checks": (CheckDeclaration("", "owner:target:one"),), "frozen_checks": (CheckDeclaration("", "owner:target:one"),), "results": ()}),
    KnownBadSpec("frozen_check_inventory_drift", "inventory", {"frozen_checks": SINGLE_DECLARATIONS}),
    KnownBadSpec("check_name_semantics_interpreted", "inventory", {"check_names_interpreted_by_supervisor": True}),
    KnownBadSpec("execution_owner_missing", "ownership", {"declared_checks": (CheckDeclaration("check:target:one", ""),), "frozen_checks": (CheckDeclaration("check:target:one", ""),), "results": ()}),
    KnownBadSpec("unknown_check_dependency", "ownership", {"declared_checks": (CheckDeclaration("check:target:one", "owner:target:one", ("check:missing",)),), "frozen_checks": (CheckDeclaration("check:target:one", "owner:target:one", ("check:missing",)),), "results": SINGLE_RESULTS}),
    KnownBadSpec("self_check_dependency", "ownership", {"declared_checks": (CheckDeclaration("check:target:one", "owner:target:one", ("check:target:one",)),), "frozen_checks": (CheckDeclaration("check:target:one", "owner:target:one", ("check:target:one",)),), "results": SINGLE_RESULTS}),
    KnownBadSpec("cyclic_check_dependency", "ownership", {"declared_checks": (CheckDeclaration("check:target:one", "owner:target:one", ("check:target:two",)), CheckDeclaration("check:target:two", "owner:target:two", ("check:target:one",))), "frozen_checks": (CheckDeclaration("check:target:one", "owner:target:one", ("check:target:two",)), CheckDeclaration("check:target:two", "owner:target:two", ("check:target:one",)))}),
    KnownBadSpec("check_result_duplicated", "receipt", {"results": (MULTI_RESULTS[0], MULTI_RESULTS[0], MULTI_RESULTS[1])}),
    KnownBadSpec("undeclared_check_result", "receipt", {"results": MULTI_RESULTS + (CheckResult("check:target:extra", "owner:target:extra", "sha256:request-current", completion_index=3),)}),
    KnownBadSpec("check_result_owner_mismatch", "receipt", {"results": (replace(MULTI_RESULTS[0], execution_owner_id="owner:wrong"), MULTI_RESULTS[1])}),
    KnownBadSpec("check_result_request_mismatch", "receipt", {"results": (replace(MULTI_RESULTS[0], request_fingerprint="sha256:wrong"), MULTI_RESULTS[1])}),
    KnownBadSpec("check_result_stale", "receipt", {"results": (replace(MULTI_RESULTS[0], current=False), MULTI_RESULTS[1])}),
    KnownBadSpec("check_result_nonterminal", "receipt", {"results": (replace(MULTI_RESULTS[0], terminal=False), MULTI_RESULTS[1])}),
    KnownBadSpec("check_result_not_passed", "receipt", {"results": (replace(MULTI_RESULTS[0], status=STATUS_BLOCKED), MULTI_RESULTS[1])}),
    KnownBadSpec("check_dependency_order_violated", "receipt", {"results": (replace(MULTI_RESULTS[0], completion_index=2), replace(MULTI_RESULTS[1], completion_index=1))}),
    KnownBadSpec("declared_check_results_incomplete", "reconciliation", {"results": (MULTI_RESULTS[0],)}),
)


def case_from_spec(spec: KnownBadSpec, *, force_accept: bool) -> SupervisionCase:
    return replace(
        GOOD_MULTI,
        case_name=f"bad-{spec.code}",
        force_accept_findings=force_accept,
        **dict(spec.changes),
    )


def _pass() -> InvariantResult:
    return InvariantResult.pass_()


def _make_fault_invariant(code: str) -> Invariant:
    def check(state: SupervisionState, _trace: object) -> InvariantResult:
        if state.phase < len(BLOCKS) or state.closure_status != STATUS_PASS:
            return _pass()
        if code in state.accepted_findings:
            return InvariantResult.fail(
                f"historical acceptance of {code} would overclaim declared-check supervision",
                {"violation": code},
            )
        return _pass()

    return Invariant(code, f"{code} must block before closure.", check)


INVARIANTS = tuple(_make_fault_invariant(spec.code) for spec in KNOWN_BAD_SPECS)


def _good_scenario(case: SupervisionCase) -> Scenario:
    return Scenario(
        name=case.case_name,
        description="all target-declared checks have exact current terminal passed results",
        initial_state=SupervisionState(),
        external_input_sequence=(case,),
        expected=ScenarioExpectation(
            expected_status="ok",
            required_trace_labels=(f"declared-check-results-reconciled:{case.case_name}",),
            summary="exact declared-check supervision reaches terminal closure",
        ),
        workflow=WORKFLOW,
        invariants=INVARIANTS,
    )


def _bad_scenario(spec: KnownBadSpec) -> Scenario:
    return Scenario(
        name=f"bad-{spec.code}",
        description=f"historical acceptance of {spec.code} must be exposed",
        initial_state=SupervisionState(),
        external_input_sequence=(case_from_spec(spec, force_accept=True),),
        expected=ScenarioExpectation(
            expected_status="violation",
            expected_violation_names=(spec.code,),
            summary=f"{spec.family} defect blocks with {spec.code}",
        ),
        workflow=WORKFLOW,
        invariants=INVARIANTS,
    )


SCENARIOS = (
    _good_scenario(GOOD_SINGLE),
    _good_scenario(GOOD_MULTI),
    _good_scenario(GOOD_SHARED_OWNER),
    *(_bad_scenario(spec) for spec in KNOWN_BAD_SPECS),
)


def run_scenario_review():
    return review_scenarios(SCENARIOS)


def run_known_bad_rejection_review() -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for spec in KNOWN_BAD_SPECS:
        run = WORKFLOW.execute(SupervisionState(), case_from_spec(spec, force_accept=False))
        if len(run.completed_paths) != 1 or run.dead_branches or run.exception_branches:
            rows[spec.code] = {"ok": False, "observed_findings": [], "closure_status": "execution_failed"}
            continue
        final = run.completed_paths[0].state
        rows[spec.code] = {
            "ok": spec.code in final.findings and final.closure_status != STATUS_PASS,
            "family": spec.family,
            "observed_findings": list(final.findings),
            "closure_status": final.closure_status,
        }
    return {"ok": all(row["ok"] for row in rows.values()), "count": len(rows), "rows": rows}


def run_contract_review():
    run = WORKFLOW.execute(SupervisionState(), GOOD_MULTI)
    contracts = tuple(
        FunctionContract(
            function_name=block.name,
            accepted_input_type=SupervisionCase,
            output_type=SupervisionCase,
            reads=block.reads,
            writes=block.writes,
            idempotency_rule=block.idempotency,
            traceability_rule="every transition label binds the exact supervision case",
        )
        for block in BLOCKS
    )
    return check_trace_contracts(run.completed_paths[0].trace, contracts)


@dataclass(frozen=True)
class SupervisionProjection:
    inventory_status: str
    ownership_status: str
    receipt_status: str
    reconciliation_status: str
    closure_status: str


def run_refinement_review():
    final = WORKFLOW.execute(SupervisionState(), GOOD_MULTI).completed_paths[0].state
    expected = SupervisionProjection(
        inventory_status=final.inventory_status,
        ownership_status=final.ownership_status,
        receipt_status=final.receipt_status,
        reconciliation_status=final.reconciliation_status,
        closure_status=final.closure_status,
    )
    raw = {name: getattr(final, name) for name in expected.__dataclass_fields__}
    raw["target_private_payload"] = "opaque"
    return check_refinement_projection(
        expected_abstract_state=expected,
        real_state=raw,
        projection=lambda value: SupervisionProjection(
            inventory_status=value["inventory_status"],
            ownership_status=value["ownership_status"],
            receipt_status=value["receipt_status"],
            reconciliation_status=value["reconciliation_status"],
            closure_status=value["closure_status"],
        ),
        function_name="ReconcileDeclaredCheckResults",
    )


def _lifecycle_edges(phase: int) -> Iterable[GraphEdge]:
    if phase >= len(BLOCKS):
        return ()
    return (GraphEdge(phase, phase + 1, f"phase-{phase}-to-{phase + 1}"),)


def _bad_lifecycle_edges(phase: int) -> Iterable[GraphEdge]:
    if phase == 0:
        return (GraphEdge(0, 1, "start"),)
    return (GraphEdge(1, 1, "result-wait-without-terminal"),)


def run_loop_reviews():
    maximum = len(BLOCKS) + 1
    good_loop = check_loops(
        LoopCheckConfig(
            initial_states=(0,),
            transition_fn=_lifecycle_edges,
            is_terminal=lambda phase: phase == len(BLOCKS),
            is_success=lambda phase: phase == len(BLOCKS),
            required_success=True,
            max_states=maximum,
        )
    )
    good_progress = check_progress(
        ProgressCheckConfig(
            initial_states=(0,),
            transition_fn=_lifecycle_edges,
            is_terminal=lambda phase: phase == len(BLOCKS),
            is_success=lambda phase: phase == len(BLOCKS),
            bounded_eventually=(
                BoundedEventuallyProperty(
                    "declared-check-supervision-reaches-reconciliation",
                    trigger=lambda _phase: True,
                    target=lambda phase: phase == len(BLOCKS),
                    max_steps=len(BLOCKS),
                ),
            ),
            max_states=maximum,
        )
    )
    bad_loop = check_loops(
        LoopCheckConfig(
            initial_states=(0,),
            transition_fn=_bad_lifecycle_edges,
            is_terminal=lambda phase: phase == len(BLOCKS),
            is_success=lambda phase: phase == len(BLOCKS),
            required_success=True,
            max_states=3,
        )
    )
    return good_loop, good_progress, bad_loop


def known_bad_family_inventory() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for spec in KNOWN_BAD_SPECS:
        result.setdefault(spec.family, []).append(spec.code)
    return result


def model_summary() -> dict[str, Any]:
    return {
        "model_id": MODEL_ID,
        "parent_model_id": PARENT_MODEL_ID,
        "function_blocks": [block.name for block in BLOCKS],
        "known_bad_count": len(KNOWN_BAD_SPECS),
        "known_bad_families": known_bad_family_inventory(),
        "fixed_workflow": [
            "freeze exact declared check inventory",
            "resolve one owner and valid dependencies per check",
            "admit current terminal results for the same request",
            "reconcile every declared check before closure",
        ],
        "claim_boundary": CLAIM_BOUNDARY,
    }
