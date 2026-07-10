"""Legal step transitions, deterministic replay, resume, and loop liveness."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .contract_compiler import canonical_hash
from .evidence_policy import required_evidence_class
from .run_store import RunStoreError, append_event, load_contract_snapshot, load_events, load_run


STEP_PENDING = "pending"
STEP_READY = "ready"
STEP_IN_PROGRESS = "in_progress"
STEP_EVIDENCE_SUBMITTED = "evidence_submitted"
STEP_PASSED = "passed"
STEP_FAILED = "failed"
STEP_BLOCKED = "blocked"
STEP_SKIP_REQUESTED = "skip_requested"
STEP_SKIPPED = "skipped"
STEP_STALE = "stale"

AUTHORITATIVE_CALLER_FIELDS = frozenset({"pass", "passed", "current", "status", "authoritative_status"})


@dataclass(frozen=True)
class StepRuntimeError(ValueError):
    code: str
    message: str
    step_id: str = ""

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


@dataclass(frozen=True)
class ReplayedRun:
    run_id: str
    status: str
    step_statuses: Mapping[str, str]
    ready_step_ids: tuple[str, ...]
    loop_state: Mapping[str, Mapping[str, Any]]
    last_event_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "skillguard_v2_replayed_run",
            "run_id": self.run_id,
            "status": self.status,
            "step_statuses": dict(self.step_statuses),
            "ready_step_ids": list(self.ready_step_ids),
            "loop_state": {key: dict(value) for key, value in self.loop_state.items()},
            "last_event_hash": self.last_event_hash,
        }


def _step_index(contract: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(row.get("step_id", "")): row
        for row in contract.get("steps", [])
        if isinstance(row, Mapping) and row.get("step_id")
    }


def _route_index(contract: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(row.get("route_id", "")): row
        for row in contract.get("routes", [])
        if isinstance(row, Mapping) and row.get("route_id")
    }


def _derive_ready(
    contract: Mapping[str, Any],
    statuses: Mapping[str, str],
    selected_route_ids: Sequence[str],
) -> tuple[str, ...]:
    selected = set(selected_route_ids)
    ready: list[str] = []
    for step_id, step in _step_index(contract).items():
        if step.get("route_id") not in selected or step.get("terminal_kind"):
            continue
        if statuses.get(step_id, STEP_PENDING) != STEP_PENDING:
            continue
        prerequisites = tuple(str(item) for item in step.get("prerequisite_step_ids", []))
        if all(statuses.get(item) in {STEP_PASSED, STEP_SKIPPED} for item in prerequisites):
            ready.append(step_id)
    return tuple(ready)


def replay_run(run_root) -> ReplayedRun:
    run = load_run(run_root)
    contract = load_contract_snapshot(run_root)
    if canonical_hash({key: value for key, value in contract.items() if key != "contract_hash"}) != contract.get(
        "contract_hash"
    ):
        raise StepRuntimeError("contract_snapshot_hash_mismatch", "contract snapshot was modified")
    statuses = {
        step_id: STEP_PENDING
        for step_id, step in _step_index(contract).items()
        if not step.get("terminal_kind")
    }
    run_status = "claimed"
    hard_run_blocked = False
    closure_issued = False
    loop_state: dict[str, dict[str, Any]] = {}
    events = load_events(run_root)
    for event in events:
        event_type = str(event.get("event_type", ""))
        payload = event.get("payload", {})
        if not isinstance(payload, Mapping):
            raise StepRuntimeError("event_payload_not_object", event_type)
        step_id = str(payload.get("step_id", ""))
        if event_type == "run_claimed":
            run_status = "claimed"
        elif event_type == "step_started":
            statuses[step_id] = STEP_IN_PROGRESS
            run_status = "running"
        elif event_type == "evidence_submitted":
            statuses[step_id] = STEP_EVIDENCE_SUBMITTED
        elif event_type == "step_verified":
            status = str(payload.get("verification_status", ""))
            if status not in {STEP_PASSED, STEP_FAILED, STEP_STALE}:
                raise StepRuntimeError("invalid_verifier_status", status, step_id)
            statuses[step_id] = status
        elif event_type == "step_failed":
            statuses[step_id] = STEP_FAILED
        elif event_type == "step_blocked":
            statuses[step_id] = STEP_BLOCKED
        elif event_type == "skip_requested":
            statuses[step_id] = STEP_SKIP_REQUESTED
        elif event_type == "skip_approved":
            statuses[step_id] = STEP_SKIPPED
        elif event_type == "step_reopened":
            statuses[step_id] = STEP_PENDING
        elif event_type == "loop_reentered":
            route_id = str(payload.get("route_id", ""))
            loop_state[route_id] = {
                "progress_token": str(payload.get("progress_token", "")),
                "reentries": int(payload.get("reentries", 0)),
            }
        elif event_type == "run_blocked":
            hard_run_blocked = True
        elif event_type == "closure_issued":
            closure_issued = True
    ready = _derive_ready(contract, statuses, run.get("route_ids", []))
    for step_id in ready:
        statuses[step_id] = STEP_READY
    if hard_run_blocked or any(value == STEP_BLOCKED for value in statuses.values()):
        run_status = "blocked"
    elif closure_issued:
        run_status = "closed"
    elif any(value in {STEP_IN_PROGRESS, STEP_EVIDENCE_SUBMITTED} for value in statuses.values()):
        run_status = "running"
    else:
        run_status = "claimed"
    return ReplayedRun(
        run_id=str(run["run_id"]),
        status=run_status,
        step_statuses=statuses,
        ready_step_ids=ready,
        loop_state=loop_state,
        last_event_hash=str(events[-1]["event_hash"]) if events else "",
    )


def next_ready_steps(run_root) -> tuple[Mapping[str, Any], ...]:
    state = replay_run(run_root)
    contract = load_contract_snapshot(run_root)
    steps = _step_index(contract)
    return tuple(steps[step_id] for step_id in state.ready_step_ids)


def begin_step(run_root, step_id: str) -> Mapping[str, Any]:
    state = replay_run(run_root)
    if step_id not in state.ready_step_ids:
        raise StepRuntimeError("step_not_ready", "step prerequisites are not satisfied", step_id)
    return append_event(run_root, "step_started", {"step_id": step_id})


def record_step(run_root, step_id: str, evidence: Mapping[str, Any]) -> Mapping[str, Any]:
    state = replay_run(run_root)
    if state.step_statuses.get(step_id) != STEP_IN_PROGRESS:
        raise StepRuntimeError("step_not_in_progress", "begin the step before submitting evidence", step_id)
    forbidden = AUTHORITATIVE_CALLER_FIELDS & set(evidence)
    if forbidden:
        raise StepRuntimeError(
            "caller_authored_authoritative_status",
            f"remove caller-owned fields: {', '.join(sorted(forbidden))}",
            step_id,
        )
    if not evidence:
        raise StepRuntimeError("empty_evidence_submission", "evidence submission cannot be empty", step_id)
    return append_event(
        run_root,
        "evidence_submitted",
        {"step_id": step_id, "evidence": dict(evidence), "evidence_hash": canonical_hash(evidence)},
    )


def record_verification(
    run_root,
    step_id: str,
    verification_status: str,
    receipt_id: str,
    *,
    verifier: str,
) -> Mapping[str, Any]:
    state = replay_run(run_root)
    if state.step_statuses.get(step_id) != STEP_EVIDENCE_SUBMITTED:
        raise StepRuntimeError("step_has_no_submitted_evidence", "verification requires submitted evidence", step_id)
    if verification_status not in {STEP_PASSED, STEP_FAILED, STEP_STALE}:
        raise StepRuntimeError("invalid_verifier_status", verification_status, step_id)
    if not receipt_id or not verifier:
        raise StepRuntimeError("verifier_receipt_missing", "receipt_id and verifier are required", step_id)
    from .receipts import ReceiptError, load_receipt

    try:
        receipt = load_receipt(run_root, receipt_id)
    except ReceiptError as exc:
        raise StepRuntimeError("verifier_receipt_invalid", exc.code, step_id) from exc
    if receipt.get("step_id") != step_id:
        raise StepRuntimeError("verifier_receipt_wrong_step", receipt_id, step_id)
    if receipt.get("status") != verification_status:
        raise StepRuntimeError("verifier_receipt_status_mismatch", receipt_id, step_id)
    if receipt.get("verifier_id") != verifier:
        raise StepRuntimeError("verifier_identity_mismatch", receipt_id, step_id)
    contract = load_contract_snapshot(run_root)
    step = _step_index(contract).get(step_id)
    if step is None:
        raise StepRuntimeError("unknown_step", "step is not in the contract", step_id)
    try:
        required_class = required_evidence_class(step)
    except ValueError as exc:
        raise StepRuntimeError("step_evidence_policy_invalid", str(exc), step_id) from exc
    if receipt.get("evidence_class") != required_class:
        raise StepRuntimeError(
            "verifier_receipt_wrong_evidence_class",
            f"expected {required_class}; actual {receipt.get('evidence_class', '')}",
            step_id,
        )
    binding = step.get("binding", {}) if isinstance(step.get("binding"), Mapping) else {}
    action = binding.get("action", {}) if isinstance(binding.get("action"), Mapping) else {}
    receipt_evidence = receipt.get("evidence", {}) if isinstance(receipt.get("evidence"), Mapping) else {}
    if required_class == "judged":
        rubric_id = str(action.get("rubric_id", ""))
        if not rubric_id:
            raise StepRuntimeError("judged_step_rubric_missing", "action.rubric_id is required", step_id)
        if receipt_evidence.get("rubric_id") != rubric_id:
            raise StepRuntimeError(
                "verifier_receipt_wrong_rubric",
                f"expected {rubric_id}; actual {receipt_evidence.get('rubric_id', '')}",
                step_id,
            )
    if required_class == "witnessed" and action.get("witness_kind"):
        expected_witness_kind = str(action["witness_kind"])
        if receipt_evidence.get("witness_kind") != expected_witness_kind:
            raise StepRuntimeError(
                "verifier_receipt_wrong_witness_kind",
                f"expected {expected_witness_kind}; actual {receipt_evidence.get('witness_kind', '')}",
                step_id,
            )
    run = load_run(run_root)
    if receipt.get("run_id") != run.get("run_id") or receipt.get("contract_hash") != run.get("contract_hash"):
        raise StepRuntimeError("verifier_receipt_wrong_run", receipt_id, step_id)
    return append_event(
        run_root,
        "step_verified",
        {
            "step_id": step_id,
            "verification_status": verification_status,
            "receipt_id": receipt_id,
            "verifier": verifier,
        },
    )


def request_skip(run_root, step_id: str, reason: str, condition_evidence_id: str) -> Mapping[str, Any]:
    contract = load_contract_snapshot(run_root)
    step = _step_index(contract).get(step_id)
    if step is None:
        raise StepRuntimeError("unknown_step", "step is not in the contract", step_id)
    if bool(step.get("required", True)):
        raise StepRuntimeError("required_step_cannot_skip", "required steps cannot be skipped", step_id)
    if not reason.strip() or not condition_evidence_id.strip():
        raise StepRuntimeError(
            "skip_justification_incomplete",
            "skip requires a reason and condition evidence",
            step_id,
        )
    from .receipts import ReceiptError, load_receipt

    try:
        condition_receipt = load_receipt(run_root, condition_evidence_id)
    except ReceiptError as exc:
        raise StepRuntimeError("skip_condition_receipt_invalid", exc.code, step_id) from exc
    if condition_receipt.get("status") != STEP_PASSED:
        raise StepRuntimeError(
            "skip_condition_receipt_not_passed",
            condition_evidence_id,
            step_id,
        )
    state = replay_run(run_root)
    if state.step_statuses.get(step_id) not in {STEP_READY, STEP_PENDING}:
        raise StepRuntimeError("skip_state_invalid", "step cannot request skip from its current state", step_id)
    return append_event(
        run_root,
        "skip_requested",
        {"step_id": step_id, "reason": reason, "condition_evidence_id": condition_evidence_id},
    )


def approve_skip(run_root, step_id: str, verifier_receipt_id: str) -> Mapping[str, Any]:
    state = replay_run(run_root)
    if state.step_statuses.get(step_id) != STEP_SKIP_REQUESTED:
        raise StepRuntimeError("skip_not_requested", "verifier can approve only a requested skip", step_id)
    if not verifier_receipt_id:
        raise StepRuntimeError("skip_receipt_missing", "skip approval requires verifier receipt", step_id)
    from .receipts import ReceiptError, load_receipt

    try:
        verifier_receipt = load_receipt(run_root, verifier_receipt_id)
    except ReceiptError as exc:
        raise StepRuntimeError("skip_verifier_receipt_invalid", exc.code, step_id) from exc
    if verifier_receipt.get("status") != STEP_PASSED:
        raise StepRuntimeError("skip_verifier_receipt_not_passed", verifier_receipt_id, step_id)
    return append_event(
        run_root,
        "skip_approved",
        {"step_id": step_id, "verifier_receipt_id": verifier_receipt_id},
    )


def record_failure(run_root, step_id: str, expected: str, actual: str, reason: str) -> Mapping[str, Any]:
    if not expected or not actual or not reason:
        raise StepRuntimeError("failure_shape_incomplete", "expected, actual, and reason are required", step_id)
    state = replay_run(run_root)
    if state.step_statuses.get(step_id) not in {STEP_IN_PROGRESS, STEP_EVIDENCE_SUBMITTED}:
        raise StepRuntimeError(
            "failure_state_invalid",
            "failure can be recorded only after the step starts",
            step_id,
        )
    return append_event(
        run_root,
        "step_failed",
        {"step_id": step_id, "expected": expected, "actual": actual, "reason": reason},
    )


def record_blocker(run_root, step_id: str, blocker: str, unblock_condition: str) -> Mapping[str, Any]:
    if not blocker or not unblock_condition:
        raise StepRuntimeError("blocker_shape_incomplete", "blocker and unblock_condition are required", step_id)
    state = replay_run(run_root)
    if state.step_statuses.get(step_id) not in {STEP_READY, STEP_IN_PROGRESS, STEP_EVIDENCE_SUBMITTED}:
        raise StepRuntimeError(
            "blocker_state_invalid",
            "blocker can be recorded only for a ready or started step",
            step_id,
        )
    return append_event(
        run_root,
        "step_blocked",
        {"step_id": step_id, "blocker": blocker, "unblock_condition": unblock_condition},
    )


def reopen_step(run_root, step_id: str, reason: str) -> Mapping[str, Any]:
    if not reason:
        raise StepRuntimeError("reopen_reason_missing", "reopen requires a reason", step_id)
    state = replay_run(run_root)
    if state.step_statuses.get(step_id) not in {STEP_FAILED, STEP_BLOCKED, STEP_STALE}:
        raise StepRuntimeError(
            "reopen_state_invalid",
            "only a failed, blocked, or stale step can be reopened",
            step_id,
        )
    return append_event(run_root, "step_reopened", {"step_id": step_id, "reason": reason})


def record_loop_reentry(run_root, route_id: str, progress_token: str) -> Mapping[str, Any]:
    contract = load_contract_snapshot(run_root)
    route = _route_index(contract).get(route_id)
    if route is None:
        raise StepRuntimeError("unknown_loop_route", "route is not declared", route_id)
    policy = route.get("loop_policy")
    if not isinstance(policy, Mapping):
        raise StepRuntimeError("loop_policy_missing", "re-entry requires a declared loop policy", route_id)
    if not progress_token:
        raise StepRuntimeError("progress_token_missing", "loop re-entry needs a progress token", route_id)
    state = replay_run(run_root)
    previous = state.loop_state.get(route_id, {})
    previous_token = str(previous.get("progress_token", ""))
    reentries = int(previous.get("reentries", 0)) + 1
    max_reentries = int(policy.get("max_reentries", 0))
    if progress_token == previous_token and previous_token:
        append_event(
            run_root,
            "run_blocked",
            {"route_id": route_id, "reason": "unchanged_progress", "reentries": reentries},
        )
        raise StepRuntimeError("loop_progress_unchanged", "loop re-entry made no progress", route_id)
    if max_reentries <= 0 or reentries > max_reentries:
        append_event(
            run_root,
            "run_blocked",
            {"route_id": route_id, "reason": "reentry_bound_exceeded", "reentries": reentries},
        )
        raise StepRuntimeError("loop_reentry_bound_exceeded", "loop exceeded its finite bound", route_id)
    return append_event(
        run_root,
        "loop_reentered",
        {"route_id": route_id, "progress_token": progress_token, "reentries": reentries},
    )


def resume_run(run_root) -> ReplayedRun:
    """Rehydrate the run from contract snapshot and append-only events only."""

    return replay_run(run_root)
