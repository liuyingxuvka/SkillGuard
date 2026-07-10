"""Target-local claimed-run storage with atomic locks and hash-chained events."""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contract_compiler import canonical_hash, canonical_json_bytes
from .contract_schema import EVENT_SCHEMA, RUN_SCHEMA, SchemaFinding, validate_runtime_payload
from .route_runtime import RouteDecision


@dataclass(frozen=True)
class RunStoreError(ValueError):
    code: str
    message: str
    path: str = ""

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


@dataclass(frozen=True)
class RunClaimResult:
    ok: bool
    status: str
    run_id: str
    run_root: Path | None
    idempotent: bool = False
    findings: tuple[SchemaFinding, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "skillguard_v2_run_claim",
            "ok": self.ok,
            "status": self.status,
            "run_id": self.run_id,
            "run_root": self.run_root.as_posix() if self.run_root else "",
            "idempotent": self.idempotent,
            "findings": [row.to_dict() for row in self.findings],
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_load(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RunStoreError("run_record_unreadable", type(exc).__name__, path.name) from exc
    if not isinstance(payload, Mapping):
        raise RunStoreError("run_record_not_object", path.name, path.name)
    return payload


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(canonical_json_bytes(payload))
    os.replace(temporary, path)


def _normalize_write_targets(target_root: Path, values: Sequence[object]) -> tuple[str, ...]:
    normalized: list[str] = []
    root = target_root.resolve()
    for value in values:
        candidate = Path(str(value))
        resolved = (root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
        try:
            relative = resolved.relative_to(root).as_posix()
        except ValueError as exc:
            raise RunStoreError("write_target_outside_target", str(value), str(value)) from exc
        normalized.append(relative or ".")
    return tuple(sorted(dict.fromkeys(normalized))) or (".",)


def _run_id(
    contract: Mapping[str, Any],
    request: Mapping[str, Any],
    write_targets: Sequence[str],
    guard_compatibility: Mapping[str, Any] | None = None,
) -> str:
    identity = {
        "skill_id": contract.get("skill_id"),
        "contract_hash": contract.get("contract_hash"),
        "request": request,
        "write_targets": list(write_targets),
        "guard_compatibility": dict(guard_compatibility or {}),
    }
    return f"run-{canonical_hash(identity)[:20].lower()}"


def _lock_path(lock_root: Path, write_target: str) -> Path:
    digest = hashlib.sha256(write_target.encode("utf-8")).hexdigest()[:24]
    return lock_root / f"{digest}.json"


def _claim_lock(path: Path, payload: Mapping[str, Any]) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError:
        existing = _json_load(path)
        return existing.get("run_id") == payload.get("run_id")
    try:
        os.write(descriptor, canonical_json_bytes(payload))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return True


def _write_targets_overlap(left: str, right: str) -> bool:
    if left == "." or right == ".":
        return True
    return left == right or left.startswith(f"{right}/") or right.startswith(f"{left}/")


def _process_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (OSError, OverflowError):
        return False
    return True


def _recoverable_lock_reason(control_root: Path, lock: Mapping[str, Any]) -> str:
    owner_pid = lock.get("owner_pid")
    if isinstance(owner_pid, int):
        if owner_pid == os.getpid() or _process_is_alive(owner_pid):
            return ""
        return "owner_process_not_alive"
    run_id = str(lock.get("run_id", ""))
    run_root = control_root / "runs" / run_id
    if not run_root.is_dir():
        return ""
    try:
        events = load_events(run_root)
    except RunStoreError:
        return ""
    if events and str(events[-1].get("event_type", "")) in {
        "step_failed",
        "locks_released",
        "closure_issued",
    }:
        return f"legacy_terminal_event:{events[-1]['event_type']}"
    return ""


def _recover_stale_locks(
    control_root: Path,
    lock_root: Path,
    candidate_run_id: str,
) -> tuple[tuple[Path, Mapping[str, Any]], ...]:
    rows = tuple((path, _json_load(path)) for path in sorted(lock_root.glob("*.json")))
    recoveries: dict[str, list[tuple[Path, Mapping[str, Any], str]]] = {}
    for path, lock in rows:
        run_id = str(lock.get("run_id", ""))
        if not run_id or run_id == candidate_run_id:
            continue
        reason = _recoverable_lock_reason(control_root, lock)
        if reason:
            recoveries.setdefault(run_id, []).append((path, lock, reason))
    for run_id, recovered_rows in sorted(recoveries.items()):
        run_root = control_root / "runs" / run_id
        if not run_root.is_dir():
            continue
        append_event(
            run_root,
            "stale_locks_recovered",
            {
                "recovered_by_run_id": candidate_run_id,
                "write_targets": sorted(str(lock.get("write_target", ".")) for _, lock, _ in recovered_rows),
                "reasons": sorted({reason for _, _, reason in recovered_rows}),
            },
        )
        for path, lock, _ in recovered_rows:
            if path.is_file() and _json_load(path).get("run_id") == lock.get("run_id"):
                path.unlink()
    return tuple((path, _json_load(path)) for path in sorted(lock_root.glob("*.json")))


def _acquire_run_locks(
    control_root: Path,
    run_id: str,
    write_targets: Sequence[str],
) -> tuple[list[Path], list[tuple[Path, Mapping[str, Any]]], SchemaFinding | None]:
    lock_root = control_root / "locks"
    acquired: list[Path] = []
    lock_payloads: list[tuple[Path, Mapping[str, Any]]] = []
    claim_guard = _acquire_claim_guard(lock_root)
    try:
        existing_locks = _recover_stale_locks(control_root, lock_root, run_id)
        for write_target in write_targets:
            conflict = next(
                (
                    row
                    for _, row in existing_locks
                    if row.get("run_id") != run_id
                    and _write_targets_overlap(write_target, str(row.get("write_target", ".")))
                ),
                None,
            )
            if conflict is not None:
                return (
                    [],
                    [],
                    SchemaFinding(
                        "conflicting_writer_claim",
                        "$.write_targets",
                        f"{write_target} overlaps {conflict.get('write_target')} owned by "
                        f"{conflict.get('run_id', 'unknown')}",
                    ),
                )
        for write_target in write_targets:
            path = _lock_path(lock_root, write_target)
            payload = {
                "run_id": run_id,
                "write_target": write_target,
                "claimed_at": utc_now(),
                "owner_pid": os.getpid(),
            }
            lock_payloads.append((path, payload))
            if path.is_file() and _json_load(path).get("run_id") == run_id:
                _atomic_write(path, payload)
                acquired.append(path)
                continue
            if not _claim_lock(path, payload):
                existing = _json_load(path)
                for acquired_path in acquired:
                    if acquired_path.is_file() and _json_load(acquired_path).get("run_id") == run_id:
                        acquired_path.unlink()
                return (
                    [],
                    [],
                    SchemaFinding(
                        "conflicting_writer_claim",
                        "$.write_targets",
                        f"{write_target} owned by {existing.get('run_id', 'unknown')}",
                    ),
                )
            acquired.append(path)
    finally:
        try:
            claim_guard.unlink()
        except FileNotFoundError:
            pass
    return acquired, lock_payloads, None


def _acquire_claim_guard(lock_root: Path) -> Path:
    lock_root.mkdir(parents=True, exist_ok=True)
    guard = lock_root / ".claim.lock"
    deadline = time.monotonic() + 5.0
    while True:
        try:
            descriptor = os.open(guard, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            os.close(descriptor)
            return guard
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise RunStoreError("claim_lock_timeout", "another writer is resolving target claims", guard.name)
            time.sleep(0.02)


def _event_hash(event: Mapping[str, Any]) -> str:
    unsigned = dict(event)
    unsigned.pop("event_hash", None)
    return canonical_hash(unsigned)


def load_events(run_root: Path) -> tuple[Mapping[str, Any], ...]:
    path = run_root / "events.jsonl"
    if not path.is_file():
        raise RunStoreError("events_missing", "events.jsonl is missing", path.name)
    rows: list[Mapping[str, Any]] = []
    previous_hash = ""
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RunStoreError("event_log_malformed", f"line {line_number}", path.name) from exc
        if not isinstance(row, Mapping):
            raise RunStoreError("event_not_object", f"line {line_number}", path.name)
        findings = validate_runtime_payload(row, EVENT_SCHEMA)
        if findings:
            raise RunStoreError(findings[0].code, findings[0].message, path.name)
        if int(row.get("sequence", 0)) != len(rows) + 1:
            raise RunStoreError("event_sequence_gap", f"line {line_number}", path.name)
        if str(row.get("previous_event_hash", "")) != previous_hash:
            raise RunStoreError("event_hash_chain_broken", f"line {line_number}", path.name)
        if str(row.get("event_hash", "")) != _event_hash(row):
            raise RunStoreError("event_hash_mismatch", f"line {line_number}", path.name)
        previous_hash = str(row["event_hash"])
        rows.append(row)
    return tuple(rows)


def append_event(run_root: Path, event_type: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    events_path = run_root / "events.jsonl"
    event_lock = run_root / ".events.lock"
    deadline = time.monotonic() + 5.0
    while True:
        try:
            descriptor = os.open(event_lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            os.close(descriptor)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise RunStoreError("event_lock_timeout", "another writer owns the event log", event_lock.name)
            time.sleep(0.02)
    try:
        events = load_events(run_root) if events_path.is_file() else ()
        previous_hash = str(events[-1]["event_hash"]) if events else ""
        event: dict[str, Any] = {
            "schema_version": EVENT_SCHEMA,
            "event_id": f"event-{len(events) + 1:06d}-{canonical_hash(payload)[:12].lower()}",
            "run_id": str(_json_load(run_root / "run.json")["run_id"]),
            "sequence": len(events) + 1,
            "event_type": event_type,
            "created_at": utc_now(),
            "payload": dict(payload),
            "payload_hash": canonical_hash(payload),
            "previous_event_hash": previous_hash,
        }
        event["event_hash"] = _event_hash(event)
        with events_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return event
    finally:
        try:
            event_lock.unlink()
        except FileNotFoundError:
            pass


def claim_run(
    contract: Mapping[str, Any],
    request: Mapping[str, Any],
    target_root: Path,
    decision: RouteDecision,
    *,
    guard_compatibility: Mapping[str, Any] | None = None,
) -> RunClaimResult:
    target_root = target_root.resolve()
    target_root.mkdir(parents=True, exist_ok=True)
    if not decision.ok:
        return RunClaimResult(
            False,
            "blocked",
            "",
            None,
            findings=tuple(
                SchemaFinding(row.code, "$.route", row.message) for row in decision.findings
            ),
        )
    contract_hash = str(contract.get("contract_hash", ""))
    if not contract_hash:
        return RunClaimResult(
            False,
            "blocked",
            "",
            None,
            findings=(SchemaFinding("contract_hash_missing", "$.contract_hash", "compiled contract hash required"),),
        )
    write_targets = _normalize_write_targets(target_root, request.get("write_targets", ["."]))
    guard_compatibility = dict(guard_compatibility or {})
    guard_compatibility_fingerprint = canonical_hash(guard_compatibility)
    run_id = _run_id(contract, request, write_targets, guard_compatibility)
    control_root = target_root / ".skillguard"
    run_root = control_root / "runs" / run_id
    run_path = run_root / "run.json"
    if run_path.is_file():
        existing = _json_load(run_path)
        if (
            existing.get("contract_hash") == contract_hash
            and existing.get("request_fingerprint") == canonical_hash(request)
            and tuple(existing.get("write_targets", [])) == write_targets
            and existing.get("guard_compatibility_fingerprint") == guard_compatibility_fingerprint
        ):
            _acquired, _lock_payloads, lock_finding = _acquire_run_locks(
                control_root,
                run_id,
                write_targets,
            )
            if lock_finding is not None:
                return RunClaimResult(False, "blocked", run_id, run_root, findings=(lock_finding,))
            return RunClaimResult(True, "claimed", run_id, run_root, idempotent=True)
        return RunClaimResult(
            False,
            "blocked",
            run_id,
            run_root,
            findings=(SchemaFinding("run_identity_collision", "$.run_id", run_id),),
        )
    acquired, lock_payloads, lock_finding = _acquire_run_locks(control_root, run_id, write_targets)
    if lock_finding is not None:
        return RunClaimResult(False, "blocked", run_id, None, findings=(lock_finding,))
    run_record: dict[str, Any] = {
        "schema_version": RUN_SCHEMA,
        "run_id": run_id,
        "skill_id": str(contract.get("skill_id", "")),
        "contract_hash": contract_hash,
        "request_fingerprint": canonical_hash(request),
        "guard_compatibility": guard_compatibility,
        "guard_compatibility_fingerprint": guard_compatibility_fingerprint,
        "request": dict(request),
        "function_ids": list(decision.function_ids),
        "route_ids": list(decision.route_ids),
        "claim_scope": decision.claim_scope,
        "write_targets": list(write_targets),
        "lock_files": [path.relative_to(control_root).as_posix() for path, _ in lock_payloads],
        "status": "claimed",
        "claimed_at": utc_now(),
    }
    findings = validate_runtime_payload(run_record, RUN_SCHEMA)
    if findings:
        for acquired_path in acquired:
            if acquired_path.is_file() and _json_load(acquired_path).get("run_id") == run_id:
                acquired_path.unlink()
        return RunClaimResult(False, "blocked", run_id, None, findings=findings)
    run_root.mkdir(parents=True, exist_ok=False)
    _atomic_write(run_root / "contract.json", dict(contract))
    _atomic_write(run_path, run_record)
    append_event(
        run_root,
        "run_claimed",
        {
            "route_ids": list(decision.route_ids),
            "function_ids": list(decision.function_ids),
            "claim_scope": decision.claim_scope,
            "write_targets": list(write_targets),
        },
    )
    return RunClaimResult(True, "claimed", run_id, run_root)


def load_run(run_root: Path) -> Mapping[str, Any]:
    payload = _json_load(run_root / "run.json")
    findings = validate_runtime_payload(payload, RUN_SCHEMA)
    if findings:
        raise RunStoreError(findings[0].code, findings[0].message, "run.json")
    return payload


def load_contract_snapshot(run_root: Path) -> Mapping[str, Any]:
    return _json_load(run_root / "contract.json")


def release_run_locks(run_root: Path) -> None:
    run = load_run(run_root)
    control_root = run_root.parents[1]
    for relative in run.get("lock_files", []):
        path = (control_root / str(relative)).resolve()
        try:
            path.relative_to(control_root.resolve())
        except ValueError as exc:
            raise RunStoreError("lock_path_outside_control_root", str(relative), str(relative)) from exc
        if path.is_file() and _json_load(path).get("run_id") == run["run_id"]:
            path.unlink()
    append_event(run_root, "locks_released", {})
