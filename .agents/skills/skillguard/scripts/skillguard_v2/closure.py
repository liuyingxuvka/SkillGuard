"""Fixed enforced evaluation, exact-receipt closure, and replay verification."""

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
from .execution_records import filesystem_path
from .execution_depth import (
    BOUNDARY_ONLY,
    BOUNDED_PARTIAL,
    DepthError,
    NOT_RUN,
    PROVIDER_UNAVAILABLE,
    STALE,
    evaluate_depth_receipt_gate,
    load_target_execution_receipts,
)
from .installation_receipt import (
    VerifiedInstallationContext,
    validate_verified_installation_context,
)
from .native_terminal import (
    NativeTerminalError,
    NativeTerminalResolution,
    contract_has_branch_requirements,
    persist_applicability_receipts,
    placeholder_or_caller_applicability,
    resolve_native_terminal_receipt,
    verify_persisted_applicability_receipts,
)
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


@dataclass
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
    execution_depth_result: Mapping[str, Any]
    native_terminal_result: Mapping[str, Any]
    applicability_results: tuple[Mapping[str, Any], ...]
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
            "execution_depth_result": dict(self.execution_depth_result),
            "native_terminal_result": dict(self.native_terminal_result),
            "applicability_results": [dict(row) for row in self.applicability_results],
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


def _closure_installation_context(
    run_root: Path,
    verified_installation_context: VerifiedInstallationContext | None,
) -> VerifiedInstallationContext | None:
    """Reuse the one sealed context supplied by the top-level operation."""

    if verified_installation_context is not None:
        return validate_verified_installation_context(
            verified_installation_context
        )
    try:
        depth_receipts = load_target_execution_receipts(run_root)
    except DepthError as exc:
        raise ClosureError(exc.code, exc.message, "installation") from exc
    if not depth_receipts:
        return None
    latest = depth_receipts[-1]
    if latest.get("evidence_domain") != "scheduled_production":
        return None
    scheduled_identity = latest.get("scheduled_production_identity")
    if not isinstance(scheduled_identity, Mapping):
        raise ClosureError(
            "scheduled_production_identity_missing",
            "latest scheduled-production depth receipt has no identity",
            "installation",
        )
    raise ClosureError(
        "verified_installation_context_required",
        "scheduled-production closure requires its top-level sealed context",
        "installation",
    )


def evaluate_closure(
    run_root: Path,
    *,
    profile: str,
    current_fingerprints: Mapping[str, object],
    receipt_roots: Sequence[Path] = (),
    target_root: Path | None = None,
    repository_root: Path | None = None,
    owner_evidence_root: Path | None = None,
    native_terminal_receipt_ref: str | Mapping[str, Any] | None = None,
    expected_route_id: str = "",
    expected_branch_id: str = "",
    verified_installation_context: VerifiedInstallationContext | None = None,
) -> ClosureEvaluation:
    verified_installation_context = _closure_installation_context(
        run_root, verified_installation_context
    )
    run = load_run(run_root)
    contract = load_contract_snapshot(run_root)
    state = replay_run(run_root)
    base_requirements = _profile_requirements(contract, profile)
    branch_contract_active = contract_has_branch_requirements(
        contract, profile, [str(item) for item in run.get("route_ids", [])]
    )
    native_terminal: NativeTerminalResolution | None = None
    if native_terminal_receipt_ref is not None:
        if not branch_contract_active:
            raise ClosureError(
                "native_terminal_not_declared",
                "the selected route/profile has no branch-conditional closure contract",
                profile,
            )
        try:
            native_terminal = resolve_native_terminal_receipt(
                run_root,
                contract,
                run,
                profile=profile,
                artifact_ref=native_terminal_receipt_ref,
                expected_route_id=expected_route_id,
                expected_branch_id=expected_branch_id,
                verified_installation_context=verified_installation_context,
            )
        except NativeTerminalError as exc:
            raise ClosureError(exc.code, exc.message, exc.field or profile) from exc
    elif branch_contract_active:
        code = (
            "bare_branch_label_rejected"
            if expected_route_id or expected_branch_id
            else "native_terminal_receipt_missing"
        )
        raise ClosureError(
            code,
            "route/branch closure requires a current portable native terminal receipt",
            profile,
        )
    elif expected_route_id or expected_branch_id:
        raise ClosureError(
            "bare_branch_label_rejected",
            "caller route/branch values are assertions only",
            profile,
        )
    not_applicable_obligation_ids = set(
        native_terminal.not_applicable_obligation_ids if native_terminal else ()
    )
    prepared_protected_obligation_ids: set[str] = set()
    if native_terminal is not None and native_terminal.branch_id == "prepared-update":
        profile_row = next(
            (
                row
                for row in contract.get("closure_profiles", [])
                if isinstance(row, Mapping) and row.get("profile_id") == profile
            ),
            {},
        )
        for requirement_row in profile_row.get("route_branch_requirements", []):
            if (
                not isinstance(requirement_row, Mapping)
                or requirement_row.get("native_route_id") != native_terminal.route_id
                or "prepared-update" in requirement_row.get("branch_ids", [])
            ):
                continue
            prepared_protected_obligation_ids.update(
                str(rule.get("obligation_id", ""))
                for rule in requirement_row.get("applicability_rules", [])
                if isinstance(rule, Mapping)
                and rule.get("allowed_disposition") == "not_applicable"
            )
    requirements = tuple(
        sorted(
            (
                set(base_requirements)
                | set(
                    native_terminal.branch_required_obligation_ids
                    if native_terminal
                    else ()
                )
            )
            - not_applicable_obligation_ids
        )
    )
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
    effective_target_root = (target_root or run_root.parents[2]).resolve()
    gaps: dict[str, list[str]] = {key: [] for key in sorted(UNSAFE_FULL_STATUSES)}
    obligation_results: list[Mapping[str, Any]] = []
    artifact_results: dict[str, Mapping[str, Any]] = {}
    consumed: list[str] = []
    required_steps: set[str] = set()

    applicability_results: list[Mapping[str, Any]] = []
    if native_terminal is not None:
        for applicability in native_terminal.applicability_receipts:
            obligation_id = str(applicability.get("obligation_id", ""))
            obligation = obligations.get(obligation_id)
            if obligation is None:
                raise ClosureError(
                    "applicability_obligation_unknown", obligation_id, obligation_id
                )
            invalid_witness_codes = {
                placeholder_or_caller_applicability(receipt)
                for receipt in receipts
                if receipt.get("step_id") in obligation.get("owner_step_ids", [])
            } - {""}
            if invalid_witness_codes:
                for code in sorted(invalid_witness_codes):
                    gaps["blocked"].append(f"{code}:{obligation_id}")
                result_status = "blocked"
            else:
                result_status = "not_applicable"
                consumed.append(str(applicability.get("receipt_id", "")))
            applicability_results.append(
                {
                    "obligation_id": obligation_id,
                    "status": result_status,
                    "disposition": "not_applicable",
                    "receipt_id": str(applicability.get("receipt_id", "")),
                    "receipt_hash": str(applicability.get("receipt_hash", "")),
                    "verifier_id": str(applicability.get("verifier_id", "")),
                    "evidence_witness_consumed": False,
                }
            )
            obligation_results.append(
                {
                    "obligation_id": obligation_id,
                    "status": result_status,
                    "receipt_id": str(applicability.get("receipt_id", "")),
                    "detail": (
                        "verifier-owned branch applicability; no evidence witness consumed"
                        if result_status == "not_applicable"
                        else "placeholder or caller-authored applicability was rejected"
                    ),
                }
            )

    for obligation_id in requirements:
        obligation = obligations[obligation_id]
        owner_steps = tuple(
            str(item)
            for item in obligation.get("owner_step_ids", [])
            if str(item) in state.step_statuses
        )
        if (
            obligation_id not in prepared_protected_obligation_ids
            and bool(obligation.get("conditional"))
            and owner_steps
            and all(
            state.step_statuses.get(step_id) == STEP_SKIPPED for step_id in owner_steps
            )
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
            if obligation_id in prepared_protected_obligation_ids:
                invalid_applicability = placeholder_or_caller_applicability(candidate)
                if invalid_applicability:
                    status = "blocked"
                    detail = invalid_applicability
                    continue
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
                candidate.get("evidence_class") == "judged"
                and isinstance(evidence, Mapping)
                and bool(evidence.get("self_review"))
            ):
                status = "uncertain"
                detail = "enforced closure requires non-self review for judged obligations"
                continue
            candidate_artifacts_ok = True
            for artifact_record_id in candidate.get("artifact_record_ids", []):
                try:
                    artifact_record = load_artifact_record(run_root, str(artifact_record_id))
                    artifact_current, artifact_reason = artifact_record_is_current(
                        artifact_record, effective_target_root
                    )
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
        if status != "passed":
            gaps[_gap_bucket(status)].append(f"terminal:{terminal_id or route_id}")
        terminal_results.append(
            {"route_id": str(route_id), "terminal_step_id": terminal_id, "status": status, "detail": detail}
        )

    execution_depth_result = evaluate_depth_receipt_gate(
        run_root,
        contract,
        closure_profile=profile,
        current_fingerprints=current_fingerprints,
        repository_root=repository_root,
        target_root=target_root,
        owner_evidence_root=owner_evidence_root,
        verified_installation_context=verified_installation_context,
    )
    if execution_depth_result.get("required"):
        depth_receipt_id = str(execution_depth_result.get("receipt_id", ""))
        if execution_depth_result.get("ok"):
            if depth_receipt_id:
                consumed.append(depth_receipt_id)
        else:
            depth_status = str(execution_depth_result.get("status", ""))
            if depth_status == STALE:
                bucket = "stale"
            elif depth_status in {NOT_RUN, PROVIDER_UNAVAILABLE}:
                bucket = "not_run"
            elif depth_status in {BOUNDED_PARTIAL, BOUNDARY_ONLY}:
                bucket = "partial"
            else:
                bucket = "blocked"
            gaps[bucket].append(f"execution_depth:{depth_status or 'missing'}")
    if native_terminal is not None:
        terminal_depth_receipt_id = str(
            native_terminal.receipt.get("depth_receipt_id", "")
        )
        if not execution_depth_result.get("required"):
            gaps["blocked"].append("native_noop_depth_gate_not_required")
        elif execution_depth_result.get("receipt_id") != terminal_depth_receipt_id:
            gaps["blocked"].append("native_terminal_depth_receipt_mismatch")
        elif not execution_depth_result.get("ok"):
            gaps["blocked"].append("native_noop_depth_receipt_not_current")
        else:
            consumed.append(str(native_terminal.receipt.get("receipt_id", "")))

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
    unsafe = (
        "This assessment does not prove work outside the contract, "
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
    return ClosureEvaluation(
        profile=profile,
        status=status,
        consumed_receipt_ids=tuple(sorted(dict.fromkeys(consumed))),
        obligation_results=tuple(obligation_results),
        step_results=tuple(step_results),
        terminal_results=tuple(terminal_results),
        artifact_results=tuple(artifact_results[key] for key in sorted(artifact_results)),
        execution_depth_result=execution_depth_result,
        native_terminal_result=(
            native_terminal.to_dict()
            if native_terminal is not None
            else {"status": "not_applicable"}
        ),
        applicability_results=tuple(applicability_results),
        gaps={key: tuple(values) for key, values in gaps.items()},
        next_actions=next_actions,
        residual_risk=tuple(residual),
        safe_claim=safe_claim,
        unsafe_claim_boundary=unsafe,
    )


def _write_report(run_root: Path, evaluation: ClosureEvaluation) -> Path:
    path = filesystem_path(
        run_root / "reports" / f"closure-{evaluation.profile}.json"
    )
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
    target_root: Path | None = None,
    repository_root: Path | None = None,
    owner_evidence_root: Path | None = None,
    native_terminal_receipt_ref: str | Mapping[str, Any] | None = None,
    expected_route_id: str = "",
    expected_branch_id: str = "",
    verified_installation_context: VerifiedInstallationContext | None = None,
) -> tuple[ClosureEvaluation, Mapping[str, Any] | None]:
    verified_installation_context = _closure_installation_context(
        run_root, verified_installation_context
    )
    evaluation = evaluate_closure(
        run_root,
        profile=profile,
        current_fingerprints=current_fingerprints,
        receipt_roots=receipt_roots,
        target_root=target_root,
        repository_root=repository_root,
        owner_evidence_root=owner_evidence_root,
        native_terminal_receipt_ref=native_terminal_receipt_ref,
        expected_route_id=expected_route_id,
        expected_branch_id=expected_branch_id,
        verified_installation_context=verified_installation_context,
    )
    if evaluation.status != "closed":
        _write_report(run_root, evaluation)
        return evaluation, None
    if evaluation.applicability_results:
        terminal_ref = evaluation.native_terminal_result.get(
            "native_terminal_receipt_ref", {}
        )
        try:
            terminal_resolution = resolve_native_terminal_receipt(
                run_root,
                load_contract_snapshot(run_root),
                load_run(run_root),
                profile=profile,
                artifact_ref=(
                    terminal_ref
                    if isinstance(terminal_ref, Mapping)
                    else native_terminal_receipt_ref or ""
                ),
                expected_route_id=expected_route_id,
                expected_branch_id=expected_branch_id,
                verified_installation_context=verified_installation_context,
            )
            persist_applicability_receipts(
                run_root, terminal_resolution.applicability_receipts
            )
        except NativeTerminalError as exc:
            raise ClosureError(exc.code, exc.message, exc.field or profile) from exc
    _write_report(run_root, evaluation)
    run = load_run(run_root)
    assessment = evaluation.to_dict()
    closures_root = filesystem_path(run_root / "closures")
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
        "root_role_bindings_hash": str(
            evaluation.execution_depth_result.get("root_role_bindings_hash", "")
        ),
        "native_terminal_result": dict(evaluation.native_terminal_result),
        "applicability_results": [
            dict(row) for row in evaluation.applicability_results
        ],
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
    root = filesystem_path(run_root / "closures")
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
    path = filesystem_path(
        run_root / "closures" / f"{closure_receipt_id}.json"
    )
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
    target_root: Path | None = None,
    repository_root: Path | None = None,
    owner_evidence_root: Path | None = None,
    verified_installation_context: VerifiedInstallationContext | None = None,
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
        verified_installation_context = _closure_installation_context(
            run_root, verified_installation_context
        )
        stored_native_terminal = closure.get("native_terminal_result", {})
        stored_terminal_ref = (
            stored_native_terminal.get("native_terminal_receipt_ref")
            if isinstance(stored_native_terminal, Mapping)
            else None
        )
        current = evaluate_closure(
            run_root,
            profile=str(closure.get("profile", "")),
            current_fingerprints=current_fingerprints,
            receipt_roots=receipt_roots,
            target_root=target_root,
            repository_root=repository_root,
            owner_evidence_root=owner_evidence_root,
            native_terminal_receipt_ref=(
                stored_terminal_ref
                if isinstance(stored_terminal_ref, Mapping)
                else None
            ),
            expected_route_id=(
                str(stored_native_terminal.get("native_route_id", ""))
                if isinstance(stored_native_terminal, Mapping)
                else ""
            ),
            expected_branch_id=(
                str(stored_native_terminal.get("branch_id", ""))
                if isinstance(stored_native_terminal, Mapping)
                else ""
            ),
            verified_installation_context=verified_installation_context,
        )
        current_payload = current.to_dict()
        if current.status != "closed":
            findings.append("closure_no_longer_current")
        if list(current.consumed_receipt_ids) != list(closure.get("consumed_receipt_ids", [])):
            findings.append("closure_consumed_receipts_changed")
        if current_payload["assessment_hash"] != closure.get("assessment_hash"):
            findings.append("closure_assessment_changed")
        if str(
            current.execution_depth_result.get("root_role_bindings_hash", "")
        ) != str(closure.get("root_role_bindings_hash", "")):
            findings.append("closure_root_role_bindings_changed")
        if current.native_terminal_result != closure.get(
            "native_terminal_result", {"status": "not_applicable"}
        ):
            findings.append("closure_native_terminal_changed")
        if [dict(row) for row in current.applicability_results] != list(
            closure.get("applicability_results", [])
        ):
            findings.append("closure_applicability_changed")
        if stored_terminal_ref is not None:
            try:
                resolved_terminal = resolve_native_terminal_receipt(
                    run_root,
                    load_contract_snapshot(run_root),
                    load_run(run_root),
                    profile=str(closure.get("profile", "")),
                    artifact_ref=stored_terminal_ref,
                    expected_route_id=str(
                        stored_native_terminal.get("native_route_id", "")
                    ),
                    expected_branch_id=str(
                        stored_native_terminal.get("branch_id", "")
                    ),
                    verified_installation_context=verified_installation_context,
                )
            except NativeTerminalError as exc:
                findings.append(f"applicability_replay_error:{exc.code}")
            else:
                findings.extend(
                    verify_persisted_applicability_receipts(
                        run_root, resolved_terminal.applicability_receipts
                    )
                )
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
