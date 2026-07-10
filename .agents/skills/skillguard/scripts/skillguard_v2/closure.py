"""Monotonic profile evaluation, exact-receipt closure, and replay verification."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .artifact_validators import (
    ArtifactValidationError,
    artifact_record_is_current,
    load_artifact_record,
)
from .contract_compiler import canonical_hash, canonical_json_bytes
from .contract_schema import CLOSURE_PROFILE_ORDER, CLOSURE_SCHEMA, validate_runtime_payload
from .receipts import ReceiptError, derive_freshness, load_receipts
from .run_store import (
    RunStoreError,
    append_event,
    load_contract_snapshot,
    load_events,
    load_run,
    release_run_locks,
    utc_now,
)
from .step_runtime import STEP_BLOCKED, STEP_FAILED, STEP_PASSED, STEP_SKIPPED, STEP_STALE, replay_run


UNSAFE_FULL_STATUSES = frozenset(
    {"missing", "failed", "blocked", "skipped", "stale", "uncertain", "not_run", "partial", "progress_only"}
)


@dataclass(frozen=True)
class ClosureError(ValueError):
    code: str
    message: str
    target_id: str = ""

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


@dataclass(frozen=True)
class ClosureEvaluation:
    profile: str
    status: str
    consumed_receipt_ids: tuple[str, ...]
    obligation_results: tuple[Mapping[str, Any], ...]
    step_results: tuple[Mapping[str, Any], ...]
    terminal_results: tuple[Mapping[str, Any], ...]
    artifact_results: tuple[Mapping[str, Any], ...]
    gaps: Mapping[str, tuple[str, ...]]
    next_actions: tuple[str, ...]
    residual_risk: tuple[str, ...]
    safe_claim: str
    unsafe_claim_boundary: str

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "artifact_type": "skillguard_v2_closure_evaluation",
            "profile": self.profile,
            "status": self.status,
            "consumed_receipt_ids": list(self.consumed_receipt_ids),
            "obligation_results": [dict(row) for row in self.obligation_results],
            "step_results": [dict(row) for row in self.step_results],
            "terminal_results": [dict(row) for row in self.terminal_results],
            "artifact_results": [dict(row) for row in self.artifact_results],
            "gaps": {key: list(value) for key, value in self.gaps.items()},
            "next_actions": list(self.next_actions),
            "residual_risk": list(self.residual_risk),
            "safe_claim": self.safe_claim,
            "unsafe_claim_boundary": self.unsafe_claim_boundary,
        }
        payload["assessment_hash"] = canonical_hash(payload)
        return payload


def _index(rows: Sequence[Mapping[str, Any]], key: str) -> dict[str, Mapping[str, Any]]:
    return {str(row.get(key, "")): row for row in rows if str(row.get(key, ""))}


def _profile_requirements(contract: Mapping[str, Any], profile: str) -> tuple[str, ...]:
    if profile not in CLOSURE_PROFILE_ORDER:
        raise ClosureError("closure_profile_unknown", profile, profile)
    profiles = _index(
        [row for row in contract.get("closure_profiles", []) if isinstance(row, Mapping)],
        "profile_id",
    )
    previous: set[str] = set()
    for profile_id in CLOSURE_PROFILE_ORDER:
        row = profiles.get(profile_id)
        if row is None:
            raise ClosureError("closure_profile_missing", profile_id, profile_id)
        requirements = {str(item) for item in row.get("required_obligation_ids", [])}
        if not previous.issubset(requirements):
            raise ClosureError("closure_profiles_non_monotonic", profile_id, profile_id)
        if profile_id == profile:
            return tuple(sorted(requirements))
        previous = requirements
    raise ClosureError("closure_profile_unknown", profile, profile)


def _latest_by_subject(receipts: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str, str], Mapping[str, Any]]:
    latest: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    for receipt in receipts:
        latest[
            (
                str(receipt.get("step_id", "")),
                str(receipt.get("evidence_class", "")),
                str(receipt.get("subject_id", "")),
            )
        ] = receipt
    return latest


def _gap_bucket(status: str) -> str:
    return status if status in UNSAFE_FULL_STATUSES else "missing"


def evaluate_closure(
    run_root: Path,
    *,
    profile: str,
    current_fingerprints: Mapping[str, object],
    receipt_roots: Sequence[Path] = (),
) -> ClosureEvaluation:
    run = load_run(run_root)
    contract = load_contract_snapshot(run_root)
    state = replay_run(run_root)
    requirements = _profile_requirements(contract, profile)
    obligations = _index(
        [row for row in contract.get("obligations", []) if isinstance(row, Mapping)],
        "obligation_id",
    )
    missing_obligations = [obligation_id for obligation_id in requirements if obligation_id not in obligations]
    if missing_obligations:
        raise ClosureError("profile_unknown_obligation", ",".join(missing_obligations), profile)
    receipts = load_receipts(run_root)
    latest = _latest_by_subject(receipts)
    roots = tuple(dict.fromkeys([run_root, *receipt_roots]))
    target_root = run_root.parents[2]
    gaps: dict[str, list[str]] = {key: [] for key in sorted(UNSAFE_FULL_STATUSES)}
    obligation_results: list[Mapping[str, Any]] = []
    artifact_results: dict[str, Mapping[str, Any]] = {}
    consumed: list[str] = []
    required_steps: set[str] = set()

    for obligation_id in requirements:
        obligation = obligations[obligation_id]
        owner_steps = tuple(str(item) for item in obligation.get("owner_step_ids", []))
        if bool(obligation.get("conditional")) and owner_steps and all(
            state.step_statuses.get(step_id) == STEP_SKIPPED for step_id in owner_steps
        ):
            obligation_results.append(
                {
                    "obligation_id": obligation_id,
                    "status": "not_applicable",
                    "receipt_id": "",
                    "detail": "conditional owner steps were verifier-approved as not applicable",
                }
            )
            continue
        required_steps.update(owner_steps)
        allowed_classes = {
            str(item) for item in obligation.get("evidence_classes", [])
        } or {"hard", "witnessed", "judged"}
        required_checks = {str(item) for item in obligation.get("required_check_ids", [])}
        candidates: list[Mapping[str, Any]] = []
        for receipt in receipts:
            if receipt.get("step_id") not in owner_steps or receipt.get("evidence_class") not in allowed_classes:
                continue
            check_id = str(receipt.get("evidence", {}).get("check_id", "")) if isinstance(receipt.get("evidence"), Mapping) else ""
            if required_checks and check_id not in required_checks:
                continue
            if latest.get(
                (
                    str(receipt.get("step_id", "")),
                    str(receipt.get("evidence_class", "")),
                    str(receipt.get("subject_id", "")),
                )
            ) is not receipt:
                continue
            candidates.append(receipt)
        selected: Mapping[str, Any] | None = None
        status = "missing"
        detail = "no matching receipt"
        for candidate in candidates:
            candidate_status = str(candidate.get("status", "missing"))
            if candidate_status != "passed":
                status = _gap_bucket(candidate_status)
                detail = f"receipt {candidate.get('receipt_id')} status={candidate_status}"
                continue
            freshness = derive_freshness(candidate, current_fingerprints, receipt_roots=roots)
            if not freshness.current:
                status = "stale"
                detail = ",".join(freshness.reasons)
                continue
            evidence = candidate.get("evidence", {})
            if (
                profile == "highest_quality"
                and candidate.get("evidence_class") == "judged"
                and isinstance(evidence, Mapping)
                and bool(evidence.get("self_review"))
            ):
                status = "uncertain"
                detail = "highest-quality closure requires non-self review for judged obligations"
                continue
            candidate_artifacts_ok = True
            for artifact_record_id in candidate.get("artifact_record_ids", []):
                try:
                    artifact_record = load_artifact_record(run_root, str(artifact_record_id))
                    artifact_current, artifact_reason = artifact_record_is_current(artifact_record, target_root)
                except ArtifactValidationError as exc:
                    artifact_current, artifact_reason = False, exc.code
                    artifact_record = {"artifact_id": "", "artifact_record_id": artifact_record_id}
                artifact_results[str(artifact_record_id)] = {
                    "artifact_record_id": str(artifact_record_id),
                    "artifact_id": str(artifact_record.get("artifact_id", "")),
                    "status": "current" if artifact_current else "stale",
                    "detail": artifact_reason,
                }
                if not artifact_current:
                    candidate_artifacts_ok = False
            if not candidate_artifacts_ok:
                status = "stale"
                detail = "one or more consumed artifacts are not current"
                continue
            selected = candidate
            status = "passed"
            detail = "current exact receipt"
            break
        if selected is not None:
            consumed.append(str(selected["receipt_id"]))
        else:
            gaps[_gap_bucket(status)].append(obligation_id)
        obligation_results.append(
            {
                "obligation_id": obligation_id,
                "status": status,
                "receipt_id": str(selected.get("receipt_id", "")) if selected else "",
                "detail": detail,
            }
        )

    step_results: list[Mapping[str, Any]] = []
    for step_id in sorted(required_steps):
        status = str(state.step_statuses.get(step_id, "missing"))
        safe_status = "passed" if status == STEP_PASSED else _gap_bucket(status)
        if safe_status != "passed":
            gaps[safe_status].append(f"step:{step_id}")
        step_results.append({"step_id": step_id, "status": safe_status, "runtime_status": status})

    step_index = _index(
        [row for row in contract.get("steps", []) if isinstance(row, Mapping)],
        "step_id",
    )
    route_index = _index(
        [row for row in contract.get("routes", []) if isinstance(row, Mapping)],
        "route_id",
    )
    terminal_results: list[Mapping[str, Any]] = []
    for route_id in run.get("route_ids", []):
        route = route_index.get(str(route_id), {})
        terminal_id = str(route.get("success_terminal_step_id", ""))
        terminal = step_index.get(terminal_id)
        if terminal is None or terminal.get("terminal_kind") != "success":
            status, detail = "missing", "declared success terminal unavailable"
        else:
            prerequisites = tuple(str(item) for item in terminal.get("prerequisite_step_ids", []))
            terminal_ok = all(state.step_statuses.get(item) in {STEP_PASSED, STEP_SKIPPED} for item in prerequisites)
            status = "passed" if terminal_ok else "blocked"
            detail = "terminal prerequisites satisfied" if terminal_ok else "terminal prerequisites incomplete"
        if status != "passed" and profile != "routine":
            gaps[_gap_bucket(status)].append(f"terminal:{terminal_id or route_id}")
        terminal_results.append(
            {"route_id": str(route_id), "terminal_step_id": terminal_id, "status": status, "detail": detail}
        )

    gaps = {key: sorted(dict.fromkeys(values)) for key, values in gaps.items() if values}
    status = "closed" if not gaps else ("stale" if set(gaps) == {"stale"} else "incomplete")
    if status == "closed":
        safe_claim = (
            f"{profile} closure is current for skill {run.get('skill_id')} run {run.get('run_id')} "
            f"across {len(requirements)} required obligation(s)."
        )
    else:
        safe_claim = (
            f"No full {profile} completion claim is safe for run {run.get('run_id')}; "
            f"{sum(len(items) for items in gaps.values())} explicit gap(s) remain."
        )
    higher_profiles = CLOSURE_PROFILE_ORDER[CLOSURE_PROFILE_ORDER.index(profile) + 1 :]
    unsafe = (
        f"This assessment does not prove {', '.join(higher_profiles) if higher_profiles else 'work outside the contract'}, "
        "unselected routes, undeclared artifacts, external publication, or future behavior."
    )
    next_actions = tuple(
        f"Resolve {gap_status}: {target}"
        for gap_status, targets in sorted(gaps.items())
        for target in targets
    )
    residual = ["Only the selected contract routes and declared fingerprints are covered."]
    if any(receipt.get("evidence_class") == "judged" for receipt in receipts):
        residual.append("Judged evidence remains evaluator-bound and is not promoted to hard proof.")
    if higher_profiles:
        residual.append(f"Higher profiles not claimed: {', '.join(higher_profiles)}.")
    return ClosureEvaluation(
        profile=profile,
        status=status,
        consumed_receipt_ids=tuple(sorted(dict.fromkeys(consumed))),
        obligation_results=tuple(obligation_results),
        step_results=tuple(step_results),
        terminal_results=tuple(terminal_results),
        artifact_results=tuple(artifact_results[key] for key in sorted(artifact_results)),
        gaps={key: tuple(values) for key, values in gaps.items()},
        next_actions=next_actions,
        residual_risk=tuple(residual),
        safe_claim=safe_claim,
        unsafe_claim_boundary=unsafe,
    )


def _write_report(run_root: Path, evaluation: ClosureEvaluation) -> Path:
    path = run_root / "reports" / f"closure-{evaluation.profile}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(canonical_json_bytes(evaluation.to_dict()))
    os.replace(temporary, path)
    return path


def close_run(
    run_root: Path,
    *,
    profile: str,
    current_fingerprints: Mapping[str, object],
    receipt_roots: Sequence[Path] = (),
) -> tuple[ClosureEvaluation, Mapping[str, Any] | None]:
    evaluation = evaluate_closure(
        run_root,
        profile=profile,
        current_fingerprints=current_fingerprints,
        receipt_roots=receipt_roots,
    )
    _write_report(run_root, evaluation)
    if evaluation.status != "closed":
        return evaluation, None
    run = load_run(run_root)
    assessment = evaluation.to_dict()
    closures_root = run_root / "closures"
    if closures_root.is_dir():
        for existing_path in sorted(closures_root.glob("closure-*.json")):
            existing_id = existing_path.stem
            try:
                existing = load_closure(run_root, existing_id)
            except ClosureError:
                continue
            if (
                existing.get("profile") == profile
                and existing.get("assessment_hash") == assessment["assessment_hash"]
                and list(existing.get("consumed_receipt_ids", [])) == list(evaluation.consumed_receipt_ids)
            ):
                return evaluation, existing
    events = load_events(run_root)
    evidence_head = str(events[-1]["event_hash"]) if events else ""
    closure: dict[str, Any] = {
        "schema_version": CLOSURE_SCHEMA,
        "run_id": str(run["run_id"]),
        "contract_hash": str(run["contract_hash"]),
        "profile": profile,
        "status": "closed",
        "consumed_receipt_ids": list(evaluation.consumed_receipt_ids),
        "evidence_event_head_hash": evidence_head,
        "assessment_hash": assessment["assessment_hash"],
        "safe_claim": evaluation.safe_claim,
        "unsafe_claim_boundary": evaluation.unsafe_claim_boundary,
        "created_at": utc_now(),
    }
    closure_id_source = dict(closure)
    closure_id_source.pop("created_at", None)
    closure["closure_receipt_id"] = f"closure-{canonical_hash(closure_id_source)[:24].lower()}"
    closure["closure_hash"] = canonical_hash(closure)
    findings = validate_runtime_payload(closure, CLOSURE_SCHEMA)
    if findings:
        raise ClosureError(findings[0].code, findings[0].message, profile)
    root = run_root / "closures"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{closure['closure_receipt_id']}.json"
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError as exc:
        raise ClosureError("closure_receipt_collision", path.name, str(closure["closure_receipt_id"])) from exc
    try:
        os.write(descriptor, canonical_json_bytes(closure))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    append_event(
        run_root,
        "closure_issued",
        {
            "closure_receipt_id": closure["closure_receipt_id"],
            "closure_hash": closure["closure_hash"],
            "profile": profile,
            "status": "closed",
        },
    )
    release_run_locks(run_root)
    return evaluation, closure


def load_closure(run_root: Path, closure_receipt_id: str) -> Mapping[str, Any]:
    path = run_root / "closures" / f"{closure_receipt_id}.json"
    try:
        closure = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ClosureError("closure_receipt_unreadable", type(exc).__name__, closure_receipt_id) from exc
    if not isinstance(closure, Mapping):
        raise ClosureError("closure_receipt_not_object", path.name, closure_receipt_id)
    findings = validate_runtime_payload(closure, CLOSURE_SCHEMA)
    if findings:
        raise ClosureError(findings[0].code, findings[0].message, closure_receipt_id)
    unsigned = dict(closure)
    stored_hash = str(unsigned.pop("closure_hash", ""))
    if not stored_hash or stored_hash != canonical_hash(unsigned):
        raise ClosureError("closure_hash_mismatch", path.name, closure_receipt_id)
    return closure


def verify_closure(
    run_root: Path,
    closure_receipt_id: str,
    *,
    current_fingerprints: Mapping[str, object],
    receipt_roots: Sequence[Path] = (),
) -> Mapping[str, Any]:
    try:
        closure = load_closure(run_root, closure_receipt_id)
    except ClosureError as exc:
        return {
            "artifact_type": "skillguard_v2_closure_verification",
            "closure_receipt_id": closure_receipt_id,
            "ok": False,
            "status": "invalid",
            "findings": [exc.code],
            "claim_boundary": "Closure receipt integrity failed before replay.",
        }
    try:
        events = load_events(run_root)
    except RunStoreError as exc:
        return {
            "artifact_type": "skillguard_v2_closure_verification",
            "closure_receipt_id": closure_receipt_id,
            "ok": False,
            "status": "invalid",
            "findings": [exc.code],
            "claim_boundary": "Event history integrity failed before closure replay.",
        }
    closure_event = next(
        (
            event
            for event in events
            if event.get("event_type") == "closure_issued"
            and isinstance(event.get("payload"), Mapping)
            and event["payload"].get("closure_receipt_id") == closure_receipt_id
        ),
        None,
    )
    findings: list[str] = []
    if closure_event is None:
        findings.append("closure_event_missing")
    else:
        if closure_event.get("previous_event_hash") != closure.get("evidence_event_head_hash"):
            findings.append("closure_evidence_head_mismatch")
        if closure_event["payload"].get("closure_hash") != closure.get("closure_hash"):
            findings.append("closure_event_hash_reference_mismatch")
    run = load_run(run_root)
    if closure.get("contract_hash") != run.get("contract_hash"):
        findings.append("closure_contract_hash_mismatch")
    try:
        current = evaluate_closure(
            run_root,
            profile=str(closure.get("profile", "")),
            current_fingerprints=current_fingerprints,
            receipt_roots=receipt_roots,
        )
        current_payload = current.to_dict()
        if current.status != "closed":
            findings.append("closure_no_longer_current")
        if list(current.consumed_receipt_ids) != list(closure.get("consumed_receipt_ids", [])):
            findings.append("closure_consumed_receipts_changed")
        if current_payload["assessment_hash"] != closure.get("assessment_hash"):
            findings.append("closure_assessment_changed")
    except (ClosureError, ReceiptError, ArtifactValidationError) as exc:
        findings.append(f"closure_replay_error:{getattr(exc, 'code', type(exc).__name__)}")
    return {
        "artifact_type": "skillguard_v2_closure_verification",
        "closure_receipt_id": closure_receipt_id,
        "ok": not findings,
        "status": "current" if not findings else "invalid",
        "findings": findings,
        "claim_boundary": "Verification covers the exact closure receipt, immutable history, and supplied current fingerprints.",
    }
