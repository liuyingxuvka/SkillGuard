"""Controlled, shell-free native check execution with explicit non-run states."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, BinaryIO, Callable, Mapping, Sequence

from .contract_compiler import (
    canonical_hash,
    canonical_json_bytes,
    impact_file_hash,
    path_fingerprint,
    source_file_hash,
    wire_hash,
)
from .execution_records import (
    CHECK_TIMEOUT_SCHEMA,
    ExecutionRecordError,
    append_progress_event,
    attach_process_tree_containment,
    command_fingerprint,
    command_token,
    durable_copy_immutable_stream,
    durable_write_immutable_json,
    execution_single_flight_lock,
    filesystem_path,
    isolated_process_kwargs,
    redact_runtime_text,
    release_process_tree_containment,
    utc_now_precise,
    write_timeout_receipt,
)
from .provenance import active_installation_source_manifest
from .receipts import fingerprint_value
from .target_inputs import fingerprint_target_input_roles, fingerprint_target_inputs
from .launch_plan import LaunchPlanError, ResolvedLaunchPlan, resolve_launch_plan
from .run_store import (
    load_check_manifest_snapshot,
    load_contract_snapshot,
    load_run,
    utc_now,
)


MAX_CAPTURE_BYTES = 256_000
SUPPORTED_CHECK_KINDS = frozenset({"command", "native", "model_assertion"})
ProgressCallback = Callable[[Mapping[str, Any]], None]
ProcessStartedCallback = Callable[[], None]

CONTENT_IMPACT_PLAN_SCHEMA = "skillguard.content_impact_plan.current"
CHECK_EXECUTION_HEAD_SCHEMA = "skillguard.check_execution_head.current"
CHECK_EXECUTION_RECEIPT_SCHEMA = "skillguard.check_execution_receipt.current"
CHECK_EXECUTION_RESULT_SIDECAR_SCHEMA = (
    "skillguard.check_execution_result_sidecar.current"
)
CHECK_EXECUTION_TERMINATION_SIDECAR_SCHEMA = (
    "skillguard.check_execution_termination_sidecar.current"
)
OWNER_EVIDENCE_PATH_TOKEN = "owner_evidence_root"
WIRE_HASH_PATTERN = r"sha256:[0-9a-f]{64}"
RECEIPT_SIDECAR_KINDS = frozenset(
    {"stdout", "stderr", "result", "termination"}
)


@dataclass
class CheckRunnerError(ValueError):
    code: str
    message: str
    check_id: str = ""

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def _under(path: Path, root: Path, code: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise CheckRunnerError(code, str(path)) from exc
    return resolved


def _resolve_cwd(
    token: str,
    *,
    target_root: Path,
    repository_root: Path,
    run_root: Path,
    relative: str = ".",
) -> Path:
    roots = {
        "target_root": target_root.resolve(),
        "repository_root": repository_root.resolve(),
        "run_root": run_root.resolve(),
    }
    if token not in roots:
        raise CheckRunnerError("cwd_token_unknown", token)
    relative_path = Path(relative)
    if relative_path.is_absolute():
        raise CheckRunnerError("cwd_relative_absolute", relative)
    return _under(roots[token] / relative_path, roots[token], "cwd_outside_token_root")


def _resolve_check_launch_plan(
    check: Mapping[str, Any],
    *,
    target_root: Path,
    repository_root: Path,
    run_root: Path,
) -> tuple[
    ResolvedLaunchPlan,
    list[str],
    list[str],
    Path,
    dict[str, str],
    dict[str, Any],
    str,
]:
    check_id = str(check.get("check_id", ""))
    command = check.get("command")
    args = check.get("args", [])
    if not isinstance(command, str) or not command:
        raise CheckRunnerError(
            "check_command_missing", "command is required", check_id
        )
    if not isinstance(args, list) or any(not isinstance(item, str) for item in args):
        raise CheckRunnerError(
            "check_args_invalid", "args must be an array of strings", check_id
        )
    declared_args = list(args)
    argument_tokens = {
        "{{target_root}}": str(target_root.resolve()),
        "{{repository_root}}": str(repository_root.resolve()),
        "{{run_root}}": str(run_root.resolve()),
    }
    resolved_args = [argument_tokens.get(item, item) for item in declared_args]
    cwd_token = str(check.get("cwd_token", "target_root"))
    cwd_relative = str(check.get("cwd_relative", "."))
    cwd = _resolve_cwd(
        cwd_token,
        target_root=target_root,
        repository_root=repository_root,
        run_root=run_root,
        relative=cwd_relative,
    )
    environment = os.environ.copy()
    declared_environment = check.get("environment", {})
    if declared_environment:
        if not isinstance(declared_environment, Mapping) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in declared_environment.items()
        ):
            raise CheckRunnerError(
                "check_environment_invalid",
                "environment must map strings",
                check_id,
            )
        environment.update(declared_environment)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    execution_environment: dict[str, Any] = {
        "os_name": os.name,
        "platform": sys.platform,
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "declared_environment_value_hashes": {
            str(key): wire_hash(str(value))
            for key, value in sorted(
                declared_environment.items()
                if isinstance(declared_environment, Mapping)
                else ()
            )
        },
        "python_dont_write_bytecode": "1",
    }
    execution_environment_fingerprint = canonical_hash(execution_environment)
    try:
        launch_plan = resolve_launch_plan(
            command,
            resolved_args,
            cwd=cwd,
            environment=environment,
            environment_fingerprint=execution_environment_fingerprint,
            cwd_token=cwd_token,
            cwd_relative=cwd_relative,
        )
    except LaunchPlanError as exc:
        semantic = {
            "schema_version": "skillguard.launch_plan.v1",
            "status": "blocked",
            "requested_command": command,
            "requested_args": resolved_args,
            "resolved_program": "",
            "resolved_program_identity": "",
            "adapter": "unresolved",
            "interpreter": "",
            "interpreter_identity": "",
            "argv": [],
            "cwd": {
                "token": cwd_token,
                "relative": cwd_relative,
                "resolved_identity": canonical_hash(str(cwd.resolve())),
            },
            "platform": sys.platform,
            "environment_fingerprint": execution_environment_fingerprint,
            "resolution_error_code": exc.code,
            "resolution_error_kind": type(exc).__name__,
            "claim_boundary": (
                "Blocked command resolution is non-run evidence and cannot "
                "authorize a receipt."
            ),
        }
        launch_plan = ResolvedLaunchPlan(
            record={
                **semantic,
                "launch_plan_fingerprint": canonical_hash(semantic),
            },
            argv=(),
            popen_args=(),
        )
    return (
        launch_plan,
        declared_args,
        resolved_args,
        cwd,
        environment,
        execution_environment,
        execution_environment_fingerprint,
    )


def _capture_file(handle: BinaryIO) -> tuple[str, str, bool, int, int]:
    handle.seek(0)
    digest = hashlib.sha256()
    captured = bytearray()
    total = 0
    while True:
        chunk = handle.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        digest.update(chunk)
        if len(captured) < MAX_CAPTURE_BYTES:
            captured.extend(chunk[: MAX_CAPTURE_BYTES - len(captured)])
    return (
        bytes(captured).decode("utf-8", errors="replace"),
        "sha256:" + digest.hexdigest(),
        total > MAX_CAPTURE_BYTES,
        total,
        len(captured),
    )


def _wire_bytes_hash(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _owner_evidence_root(
    repository_root: Path,
    configured_root: Path | None,
) -> Path:
    root = (
        configured_root
        if configured_root is not None
        else repository_root / "work" / "verification" / "owner-evidence"
    ).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve_owner_evidence_root(
    repository_root: Path,
    configured_root: Path | None = None,
) -> Path:
    """Return the one persistent owner-evidence authority for this repository."""

    return _owner_evidence_root(repository_root, configured_root)


def _blob_relative_path(content_hash: str, suffix: str) -> Path:
    if not re.fullmatch(WIRE_HASH_PATTERN, content_hash):
        raise CheckRunnerError("check_execution_content_hash_invalid", content_hash)
    digest = content_hash.split(":", 1)[1]
    return Path("check-executions") / "blobs" / f"{digest}.{suffix}"


def _persist_stream_sidecar(
    owner_evidence_root: Path,
    handle: BinaryIO,
    *,
    media_type: str,
) -> dict[str, Any]:
    handle.seek(0)
    digest = hashlib.sha256()
    byte_count = 0
    while True:
        chunk = handle.read(64 * 1024)
        if not chunk:
            break
        byte_count += len(chunk)
        digest.update(chunk)
    content_hash = "sha256:" + digest.hexdigest()
    relative_path = _blob_relative_path(content_hash, "bin")
    durable_copy_immutable_stream(
        owner_evidence_root / relative_path,
        handle,
        expected_content_hash=content_hash,
    )
    return {
        "path_token": OWNER_EVIDENCE_PATH_TOKEN,
        "relative_path": relative_path.as_posix(),
        "content_hash": content_hash,
        "media_type": media_type,
        "byte_count": byte_count,
    }


def _persist_json_sidecar(
    owner_evidence_root: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    body = canonical_json_bytes(dict(payload))
    content_hash = _wire_bytes_hash(body)
    relative_path = _blob_relative_path(content_hash, "json")
    durable_write_immutable_json(owner_evidence_root / relative_path, dict(payload))
    return {
        "path_token": OWNER_EVIDENCE_PATH_TOKEN,
        "relative_path": relative_path.as_posix(),
        "content_hash": content_hash,
        "media_type": "application/json",
        "byte_count": len(body),
    }


def _resolve_owner_ref(
    owner_evidence_root: Path,
    reference: Mapping[str, Any],
    *,
    code: str,
) -> Path:
    if set(reference) != {
        "path_token",
        "relative_path",
        "content_hash",
        "media_type",
        "byte_count",
    }:
        raise CheckRunnerError(code, "sidecar reference shape")
    if reference.get("path_token") != OWNER_EVIDENCE_PATH_TOKEN:
        raise CheckRunnerError(code, "path_token")
    content_hash = str(reference.get("content_hash", ""))
    if not re.fullmatch(WIRE_HASH_PATTERN, content_hash):
        raise CheckRunnerError(code, "content_hash")
    relative_text = str(reference.get("relative_path", ""))
    relative = Path(relative_text)
    if not relative_text or relative.is_absolute():
        raise CheckRunnerError(code, "relative_path")
    resolved = (owner_evidence_root / relative).resolve()
    try:
        resolved.relative_to(owner_evidence_root.resolve())
    except ValueError as exc:
        raise CheckRunnerError(code, "reference escape") from exc
    io_resolved = filesystem_path(resolved)
    if not io_resolved.is_file():
        raise CheckRunnerError(code, f"missing:{relative_text}")
    try:
        body = io_resolved.read_bytes()
    except OSError as exc:
        raise CheckRunnerError(code, f"unreadable:{relative_text}") from exc
    if _wire_bytes_hash(body) != content_hash:
        raise CheckRunnerError(code, f"hash:{relative_text}")
    if len(body) != reference.get("byte_count"):
        raise CheckRunnerError(code, f"byte_count:{relative_text}")
    return io_resolved


def _emit_execution_event(
    run_root: Path,
    *,
    event_type: str,
    step_id: str,
    check_id: str,
    completed_count: int,
    total_count: int,
    elapsed_seconds: float,
    started_at: str,
    deadline_at: str,
    callback: ProgressCallback | None,
    status: str = "running",
    stdout_total_bytes: int | None = None,
    stderr_total_bytes: int | None = None,
    progress_delta_bytes: int | None = None,
    no_progress_ms: int | None = None,
) -> Mapping[str, Any]:
    payload: dict[str, Any] = {
        "event_type": event_type,
        "scope": "manifest_bound_check",
        "current_step_id": step_id,
        "current_check_id": check_id,
        "completed_count": completed_count,
        "total_count": total_count,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "elapsed_ms": max(0, round(elapsed_seconds * 1000)),
        "started_at": started_at,
        "deadline_at": deadline_at,
        "status": status,
        "emitted_at": utc_now_precise(),
        "authority": "liveness_only" if event_type != "end" else "execution_status_only",
    }
    if stdout_total_bytes is not None:
        payload["stdout_total_bytes"] = stdout_total_bytes
    if stderr_total_bytes is not None:
        payload["stderr_total_bytes"] = stderr_total_bytes
    if stdout_total_bytes is not None or stderr_total_bytes is not None:
        payload["observed_output_bytes"] = int(stdout_total_bytes or 0) + int(
            stderr_total_bytes or 0
        )
    if progress_delta_bytes is not None:
        payload["progress_delta_bytes"] = progress_delta_bytes
    if no_progress_ms is not None:
        payload["no_progress_ms"] = no_progress_ms
    event = append_progress_event(
        run_root,
        Path("progress") / "check-events.jsonl",
        payload,
        path_token="run_root",
    )
    if callback is not None:
        try:
            callback(event)
        except Exception:
            # Progress display is observational and must not change check truth.
            pass
    return event


def _declared_check_for_run(
    run_root: Path,
    check: Mapping[str, Any],
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    """Return the immutable declared check or fail before process execution."""

    check_id = str(check.get("check_id") or check.get("id") or "")
    if not check_id:
        raise CheckRunnerError("check_id_missing", "check declaration needs check_id")
    manifest = load_check_manifest_snapshot(run_root)
    declared = next(
        (
            row
            for row in manifest.get("checks", [])
            if isinstance(row, Mapping) and row.get("check_id") == check_id
        ),
        None,
    )
    if declared is None:
        raise CheckRunnerError(
            "check_not_declared_in_run_manifest",
            "the claimed manifest does not declare this check",
            check_id,
        )
    supplied = dict(check)
    supplied.setdefault(
        "semantic_check_id", str(supplied.get("check_id", check_id))
    )
    if canonical_hash(supplied) != canonical_hash(dict(declared)):
        raise CheckRunnerError(
            "check_manifest_binding_mismatch",
            "executed check differs from the immutable run manifest",
            check_id,
        )
    return declared, manifest


def _execution_proof_fingerprint(result: Mapping[str, Any]) -> str:
    owner_receipt_id = str(result.get("owner_receipt_id", ""))
    owner_receipt_hash = str(result.get("owner_receipt_hash", ""))
    projection_hash = str(result.get("projection_declaration_hash", ""))
    if owner_receipt_id and owner_receipt_hash and projection_hash:
        return wire_hash(
            {
                "check_id": str(result.get("check_id", "")),
                "execution_owner_id": str(
                    result.get("execution_owner_id", "")
                ),
                "owner_receipt_id": owner_receipt_id,
                "owner_receipt_hash": owner_receipt_hash,
                "projection_declaration_hash": projection_hash,
                "status": str(result.get("status", "")),
            }
        )
    return canonical_hash(
        {
            "check_id": str(result.get("check_id", "")),
            "semantic_check_id": str(result.get("semantic_check_id", "")),
            "execution_id": str(result.get("execution_id", "")),
            "execution_key": str(result.get("execution_key", "")),
            "source_authority_hash": str(
                result.get("source_authority_hash", "")
            ),
            "command": str(result.get("command", "")),
            "launch_plan_fingerprint": str(result.get("launch_plan_fingerprint", "")),
            "args": result.get("args", []),
            "declared_args": result.get("declared_args", []),
            "cwd_token": str(result.get("cwd_token", "")),
            "cwd_relative": str(result.get("cwd_relative", "")),
            "exit_code": result.get("exit_code"),
            "stdout_content_hash": str(result.get("stdout_content_hash", "")),
            "stderr_content_hash": str(result.get("stderr_content_hash", "")),
            "execution_environment_fingerprint": str(
                result.get("execution_environment_fingerprint", "")
            ),
            "check_manifest_hash": str(result.get("check_manifest_hash", "")),
            "declared_check_hash": str(result.get("declared_check_hash", "")),
            "step_id": str(result.get("step_id", "")),
            "started_at": str(result.get("started_at", "")),
            "deadline_at": str(result.get("deadline_at", "")),
            "finished_at": str(result.get("finished_at", "")),
            "timeout_receipt_hash": str(result.get("timeout_receipt_hash", "")),
            "status": str(result.get("status", "")),
            "reason": str(result.get("reason", "")),
        }
    )


def execution_proof_fingerprint(result: Mapping[str, Any]) -> str:
    """Public single owner for native-check proof derivation and replay."""

    return _execution_proof_fingerprint(result)


def _stable_persisted_result(result: Mapping[str, Any]) -> dict[str, Any]:
    stable = dict(result)
    defaults: dict[str, Any] = {
        "schema_version": "skillguard.check_execution_result.v1",
        "artifact_type": "skillguard_check_execution_result",
        "reason": "",
        "semantic_check_id": "",
        "execution_id": "",
        "execution_key": "",
        "execution_owner_id": "",
        "projection_declaration_hash": "",
        "execution_disposition": "",
        "command_executed_in_this_call": False,
        "owner_receipt_id": "",
        "owner_receipt_hash": "",
        "owner_receipt_ref": None,
        "source_authority_hash": "",
        "executed": False,
        "process_started": False,
        "launch_error_kind": "",
        "terminal_kind": "not_run",
        "command": "",
        "command_token": "",
        "command_fingerprint": "",
        "launch_plan": {},
        "launch_plan_fingerprint": "",
        "args": [],
        "declared_args": [],
        "cwd_token": "",
        "cwd_relative": "",
        "timeout_seconds": 0.0,
        "timeout_ms": 0,
        "exit_code": None,
        "expected_exit_code": None,
        "stdout": "",
        "stderr": "",
        "stdout_content_hash": _wire_bytes_hash(b""),
        "stderr_content_hash": _wire_bytes_hash(b""),
        "stdout_total_bytes": 0,
        "stderr_total_bytes": 0,
        "stdout_captured_bytes": 0,
        "stderr_captured_bytes": 0,
        "output_truncated": False,
        "stdout_sidecar_ref": None,
        "stderr_sidecar_ref": None,
        "execution_environment": {},
        "execution_environment_fingerprint": "",
        "step_id": "",
        "started_at": "",
        "deadline_at": "",
        "finished_at": "",
        "elapsed_seconds": 0.0,
        "elapsed_ms": 0,
        "termination_scope": "none",
        "termination_attempted": False,
        "termination_succeeded": False,
        "termination_method": "not_required",
        "termination_error_kind": "",
        "cleanup_confirmed": False,
        "cleanup_confirmation_method": "not_required",
        "descendant_count_before": 0,
        "descendant_count_after": 0,
        "remaining_descendant_pids": [],
        "cleanup_blocker_ref": "",
        "cleanup_blocker_hash": "",
        "proof_fingerprint": "",
        "timeout_receipt_write_status": "not_applicable",
        "timeout_receipt_error_kind": "",
        "timeout_receipt_id": "",
        "timeout_receipt_ref": "",
        "timeout_receipt_hash": "",
        "diagnostic_ref": None,
        "diagnostic_hash": "",
        "claim_boundary": "A non-passing or non-run result supplies no completion authority.",
    }
    for key, value in defaults.items():
        stable.setdefault(key, value)
    return stable


def _semantic_result_sidecar(result: Mapping[str, Any]) -> dict[str, Any]:
    excluded = {
        "schema_version",
        "artifact_type",
        "check_id",
        "semantic_check_id",
        "kind",
        "covers_obligation_ids",
        "check_manifest_hash",
        "check_declarations_hash",
        "declared_check_hash",
        "created_at",
        "step_id",
        "execution_id",
        "execution_key",
        "source_authority_hash",
        "started_at",
        "deadline_at",
        "finished_at",
        "elapsed_seconds",
        "elapsed_ms",
        "stdout",
        "stderr",
        "_persisted_stdout",
        "_persisted_stderr",
        "diagnostic_ref",
        "diagnostic_hash",
        "proof_fingerprint",
        "claim_boundary",
        "termination_scope",
        "termination_attempted",
        "termination_succeeded",
        "termination_method",
        "termination_error_kind",
        "timeout_receipt_write_status",
        "timeout_receipt_error_kind",
        "timeout_receipt_id",
        "timeout_receipt_ref",
        "timeout_receipt_hash",
    }
    payload = {
        str(key): value
        for key, value in result.items()
        if key not in excluded and not str(key).startswith("_runtime_")
    }
    return {
        "schema_version": CHECK_EXECUTION_RESULT_SIDECAR_SCHEMA,
        "result": payload,
        "claim_boundary": (
            "Non-semantic timestamps, run/check projection fields, display text, and "
            "termination facts are deliberately outside this owner result identity."
        ),
    }


def _semantic_termination_sidecar(result: Mapping[str, Any]) -> dict[str, Any]:
    termination_succeeded = bool(result.get("termination_succeeded", False))
    cleanup_confirmed = bool(result.get("cleanup_confirmed", False))
    return {
        "schema_version": CHECK_EXECUTION_TERMINATION_SIDECAR_SCHEMA,
        "terminal_kind": str(result.get("terminal_kind", "")),
        "termination_scope": str(result.get("termination_scope", "none")),
        "termination_attempted": bool(result.get("termination_attempted", False)),
        "termination_succeeded": termination_succeeded,
        "termination_method": str(result.get("termination_method", "not_required")),
        "termination_error_kind": str(
            result.get("termination_error_kind", "")
        ),
        "cleanup_confirmed": cleanup_confirmed,
        "claim_boundary": (
            "A timeout, cancellation, or interruption is reusable only after whole-tree "
            "cleanup is confirmed; terminal success receipts are never written for those states."
        ),
    }


def _content_impact_owner(
    contract: Mapping[str, Any],
    check: Mapping[str, Any],
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    plan = contract.get("content_impact_plan")
    if not isinstance(plan, Mapping) or plan.get("schema_version") != CONTENT_IMPACT_PLAN_SCHEMA:
        raise CheckRunnerError(
            "check_content_impact_plan_missing_or_unsupported",
            str(plan.get("schema_version", "missing")) if isinstance(plan, Mapping) else "missing",
        )
    health = plan.get("health")
    if not isinstance(health, Mapping) or any(health.get(key) for key in health):
        raise CheckRunnerError("check_content_impact_plan_unhealthy", "health gate")
    owner_id = str(check.get("execution_owner_id", ""))
    owner = next(
        (
            row
            for row in plan.get("owners", [])
            if isinstance(row, Mapping)
            and str(row.get("execution_owner_id", "")) == owner_id
        ),
        None,
    )
    if owner is None:
        raise CheckRunnerError("check_execution_owner_missing", owner_id or "missing")
    for field in (
        "owner_declaration_hash",
        "owner_input_projection_hash",
        "evidence_domain_id",
    ):
        if str(check.get(field, "")) != str(owner.get(field, "")):
            raise CheckRunnerError("check_execution_owner_binding_mismatch", field)
    check_components = sorted(str(value) for value in check.get("input_component_ids", []))
    owner_components = sorted(str(value) for value in owner.get("input_component_ids", []))
    if check_components != owner_components:
        raise CheckRunnerError(
            "check_execution_owner_binding_mismatch", "input_component_ids"
        )
    return plan, owner


def _current_owner_input_projection(
    *,
    repository_root: Path,
    plan: Mapping[str, Any],
    owner: Mapping[str, Any],
) -> dict[str, Any]:
    root = repository_root.resolve()
    inventory = {
        str(row.get("path", "")): row
        for row in plan.get("inventory", [])
        if isinstance(row, Mapping) and str(row.get("path", ""))
    }
    components = {
        str(row.get("component_id", "")): row
        for row in plan.get("components", [])
        if isinstance(row, Mapping) and str(row.get("component_id", ""))
    }
    current_components: list[dict[str, str]] = []
    for component_id_value in owner.get("input_component_ids", []):
        component_id = str(component_id_value)
        component = components.get(component_id)
        if component is None:
            raise CheckRunnerError(
                "check_owner_input_component_missing", component_id
            )
        members: list[dict[str, str]] = []
        for path_value in component.get("member_paths", []):
            relative_text = str(path_value)
            inventory_row = inventory.get(relative_text)
            relative = Path(relative_text)
            if inventory_row is None or not relative_text or relative.is_absolute():
                raise CheckRunnerError(
                    "check_owner_input_member_invalid", relative_text or "missing"
                )
            candidate = (root / relative).resolve()
            try:
                candidate.relative_to(root)
            except ValueError as exc:
                raise CheckRunnerError(
                    "check_owner_input_member_escape", relative_text
                ) from exc
            if not candidate.is_file():
                raise CheckRunnerError(
                    "check_owner_input_member_missing", relative_text
                )
            actual_hash = impact_file_hash(candidate)
            if actual_hash != str(inventory_row.get("content_hash", "")):
                raise CheckRunnerError(
                    "check_owner_input_component_stale", relative_text
                )
            members.append({"path": relative_text, "content_hash": actual_hash})
        component_hash = wire_hash(members)
        if component_hash != str(component.get("component_hash", "")):
            raise CheckRunnerError(
                "check_owner_input_component_hash_mismatch", component_id
            )
        current_components.append(
            {"component_id": component_id, "component_hash": component_hash}
        )
    current_components.sort(key=lambda row: row["component_id"])
    projection_hash = wire_hash(current_components)
    if projection_hash != str(owner.get("owner_input_projection_hash", "")):
        raise CheckRunnerError(
            "check_owner_input_projection_stale",
            str(owner.get("execution_owner_id", "")),
        )
    return {
        "components": current_components,
        "owner_input_projection_hash": projection_hash,
    }


def inspect_current_owner_input_projection(
    *,
    repository_root: Path,
    content_impact_plan: Mapping[str, Any],
    owner: Mapping[str, Any],
) -> dict[str, Any]:
    """Public read-only owner input projection used by impact planning."""

    return _current_owner_input_projection(
        repository_root=repository_root,
        plan=content_impact_plan,
        owner=owner,
    )


def _toolchain_fingerprint(command: str) -> str:
    resolved_text = shutil.which(command) or command
    candidate = Path(resolved_text)
    executable_hash = ""
    if candidate.is_file():
        try:
            executable_hash = "sha256:" + hashlib.sha256(
                candidate.read_bytes()
            ).hexdigest()
        except OSError as exc:
            if command_token(command) != "python_runtime":
                raise CheckRunnerError(
                    "check_toolchain_unreadable", command_token(command)
                ) from exc
    if command_token(command) == "python_runtime" and not executable_hash:
        for runtime_value in (
            getattr(sys, "_base_executable", ""),
            sys.executable,
        ):
            runtime_path = Path(str(runtime_value))
            try:
                if runtime_path.is_file():
                    executable_hash = "sha256:" + hashlib.sha256(
                        runtime_path.read_bytes()
                    ).hexdigest()
                    break
            except OSError:
                continue
    return wire_hash(
        {
            "command_token": command_token(command),
            "executable_hash": executable_hash,
            "platform_machine": platform.machine(),
            "runtime_version": (
                platform.python_version()
                if command_token(command) == "python_runtime"
                else ""
            ),
        }
    )


def check_toolchain_identity(check: Mapping[str, Any]) -> dict[str, str]:
    """Return the exact read-only toolchain/environment projection for a check."""

    execution_environment = {
        "os_name": os.name,
        "platform": sys.platform,
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
    }
    return {
        "toolchain_fingerprint": _toolchain_fingerprint(
            str(check.get("command", ""))
        ),
        "execution_environment_fingerprint": wire_hash(
            execution_environment
        ),
    }


def _wire_target_input_fingerprint(value: object) -> str:
    """Project the native target-input hash into the one current wire shape."""

    text = str(value or "")
    if not text:
        return ""
    if re.fullmatch(r"[A-F0-9]{64}", text) is None:
        raise CheckRunnerError(
            "check_target_input_fingerprint_invalid", text
        )
    return "sha256:" + text.lower()


def _run_bound_output_component(
    declared: Mapping[str, Any],
    run: Mapping[str, Any],
) -> dict[str, str] | None:
    """Bind checks that read from or write evidence into the current run.

    A command that receives ``{{run_root}}`` can read request/run state even
    when it does not emit a depth-specific envelope.  Reusing its owner receipt
    across a different request would therefore be unsound.
    """

    raw_args = declared.get("args", [])
    reads_run_root = (
        isinstance(raw_args, Sequence)
        and not isinstance(raw_args, (str, bytes))
        and any(str(value) == "{{run_root}}" for value in raw_args)
    )
    if not reads_run_root:
        return None
    return {
        "component_id": "component:run_bound_output_context",
        "component_hash": wire_hash(
            {
                "policy_id": "skillguard.run_bound_output.current",
                "run_id": str(run.get("run_id", "")),
                "contract_hash": str(run.get("contract_hash", "")),
                "check_manifest_hash": str(run.get("check_manifest_hash", "")),
                "check_declarations_hash": str(
                    run.get("check_declarations_hash", "")
                ),
                "request_fingerprint": str(run.get("request_fingerprint", "")),
            }
        ),
    }


def _installed_runtime_input_component(
    declared: Mapping[str, Any],
    *,
    plan: Mapping[str, Any],
    owner: Mapping[str, Any],
) -> dict[str, str] | None:
    """Bind installation-sensitive checks to the active installed skill trees.

    Receipt, report, and other currentness-output subtrees remain outside the
    active installation manifest.  Only checks that explicitly select an
    install disposition receive this component, so ordinary source checks do
    not inherit a broad installation invalidation boundary.
    """

    dispositions = {
        str(selector.get("install_disposition", ""))
        for selector in declared.get("input_selectors", [])
        if isinstance(selector, Mapping)
        and selector.get("kind") == "install_disposition"
    }
    dispositions.discard("")
    if not dispositions:
        return None
    components = {
        str(row.get("component_id", "")): row
        for row in plan.get("components", [])
        if isinstance(row, Mapping) and str(row.get("component_id", ""))
    }
    skill_ids: set[str] = set()
    for component_id_value in owner.get("input_component_ids", []):
        component = components.get(str(component_id_value))
        if not isinstance(component, Mapping) or str(
            component.get("install_disposition", "")
        ) not in dispositions:
            continue
        for path_value in component.get("member_paths", []):
            parts = str(path_value).replace("\\", "/").split("/")
            if len(parts) < 4 or parts[0] != ".agents" or parts[1] != "skills":
                raise CheckRunnerError(
                    "check_installed_input_member_invalid", str(path_value)
                )
            skill_ids.add(parts[2])
    if not skill_ids:
        raise CheckRunnerError(
            "check_installed_input_skill_missing",
            str(declared.get("check_id", "")),
        )
    codex_home = Path(
        os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
    ).resolve()
    installed_rows: list[dict[str, Any]] = []
    for skill_id in sorted(skill_ids):
        installed_root = codex_home / "skills" / skill_id
        if not installed_root.is_dir() or installed_root.is_symlink():
            installed_rows.append(
                {
                    "skill_id": skill_id,
                    "status": "missing_or_unsafe",
                    "manifest_hash": "",
                    "file_count": 0,
                }
            )
            continue
        try:
            manifest = active_installation_source_manifest(installed_root)
        except (OSError, UnicodeError, ValueError):
            installed_rows.append(
                {
                    "skill_id": skill_id,
                    "status": "unreadable_or_blocked",
                    "manifest_hash": "",
                    "file_count": 0,
                }
            )
            continue
        installed_rows.append(
            {
                "skill_id": skill_id,
                "status": "available",
                "manifest_hash": wire_hash(
                    [
                        {"path": path, "content_hash": content_hash}
                        for path, content_hash in sorted(manifest.items())
                    ]
                ),
                "file_count": len(manifest),
            }
        )
    return {
        "component_id": "component:active_installed_skill_trees",
        "component_hash": wire_hash(installed_rows),
    }


def _check_execution_identity(
    check: Mapping[str, Any],
    *,
    skill_root: Path,
    target_root: Path,
    repository_root: Path,
    run_root: Path,
    owner_evidence_root: Path,
    dependency_receipts: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    declared, manifest = _declared_check_for_run(run_root, check)
    run = load_run(run_root)
    contract = load_contract_snapshot(run_root)
    plan, owner = _content_impact_owner(contract, declared)
    owner_input = _current_owner_input_projection(
        repository_root=repository_root,
        plan=plan,
        owner=owner,
    )
    owner_input_components = list(owner_input["components"])
    run_bound_component = _run_bound_output_component(declared, run)
    if run_bound_component is not None:
        owner_input_components.append(run_bound_component)
    installed_component = _installed_runtime_input_component(
        declared,
        plan=plan,
        owner=owner,
    )
    if installed_component is not None:
        owner_input_components.append(installed_component)
    owner_input_components.sort(key=lambda row: str(row["component_id"]))
    owner_input_projection_hash = wire_hash(owner_input_components)
    expected_dependency_owner_ids = sorted(
        str(value) for value in owner.get("depends_on_owner_ids", [])
    )
    supplied_dependency_owner_ids = sorted(str(value) for value in dependency_receipts)
    if expected_dependency_owner_ids != supplied_dependency_owner_ids:
        raise CheckRunnerError(
            "check_dependency_receipt_set_mismatch",
            f"expected={expected_dependency_owner_ids};actual={supplied_dependency_owner_ids}",
        )
    dependency_identities: list[dict[str, str]] = []
    for dependency_owner_id in expected_dependency_owner_ids:
        receipt = dependency_receipts[dependency_owner_id]
        _validate_owner_receipt(
            owner_evidence_root,
            receipt,
            expected_owner_id=dependency_owner_id,
        )
        dependency_identities.append(
            {
                "execution_owner_id": dependency_owner_id,
                "receipt_id": str(receipt.get("receipt_id", "")),
                "receipt_hash": str(receipt.get("receipt_hash", "")),
            }
        )
    request = run.get("request", {})
    if not isinstance(request, Mapping):
        raise CheckRunnerError("check_run_request_invalid", str(run_root))
    target_input_fingerprint = str(request.get("target_input_fingerprint", ""))
    target_input_paths = request.get("target_input_paths")
    if target_input_paths is not None:
        current_target_inputs = fingerprint_target_inputs(
            target_root, target_input_paths
        )
        if current_target_inputs.get("fingerprint") != target_input_fingerprint:
            raise CheckRunnerError(
                "check_target_input_authority_stale", str(declared.get("check_id", ""))
            )
    target_input_role_fingerprints: dict[str, str] = {}
    target_input_roles = request.get("target_input_roles")
    if target_input_roles is not None:
        current_role_inputs = fingerprint_target_input_roles(
            target_root, target_input_roles
        )
        target_input_role_fingerprints = {
            role: str(fingerprint_value(inventory)["raw"])
            for role, inventory in sorted(current_role_inputs.items())
        }
    toolchain_identity = check_toolchain_identity(declared)
    launch_plan, *_launch_details = _resolve_check_launch_plan(
        declared,
        target_root=target_root,
        repository_root=repository_root,
        run_root=run_root,
    )
    semantic_identity = {
        "execution_owner_id": str(owner.get("execution_owner_id", "")),
        "owner_declaration_hash": str(owner.get("owner_declaration_hash", "")),
        "owner_input_projection_hash": owner_input_projection_hash,
        "dependency_receipts": dependency_identities,
        "target_input_fingerprint": _wire_target_input_fingerprint(
            target_input_fingerprint
        ),
        "target_input_role_fingerprints": target_input_role_fingerprints,
        **toolchain_identity,
        "launch_plan_fingerprint": str(
            launch_plan.record.get("launch_plan_fingerprint", "")
        ),
        "resolved_program_identity": str(
            launch_plan.record.get("resolved_program_identity", "")
        ),
        "resolved_interpreter_identity": str(
            launch_plan.record.get("interpreter_identity", "")
        ),
        "evidence_domain_id": str(owner.get("evidence_domain_id", "")),
        "impact_policy_id": str(plan.get("policy_id", "")),
    }
    return {
        **semantic_identity,
        "execution_key": wire_hash(semantic_identity),
        "owner_input_components": owner_input_components,
        "check_manifest_hash": str(manifest.get("manifest_hash", "")),
        "_resolved_launch_plan": launch_plan,
    }


def _current_run_target_fingerprints(
    run: Mapping[str, Any],
    target_root: Path,
    profile: Mapping[str, Any],
) -> dict[str, Any]:
    """Recompute verifier-owned target inputs for native protocol validation."""

    request = run.get("request", {})
    if not isinstance(request, Mapping):
        raise CheckRunnerError("check_run_request_invalid", str(target_root))
    fingerprints: dict[str, Any] = {}
    target_input_paths = request.get("target_input_paths")
    if target_input_paths is not None:
        fingerprints["target_inputs"] = fingerprint_value(
            fingerprint_target_inputs(target_root, target_input_paths)
        )
    target_input_roles = request.get("target_input_roles")
    if target_input_roles is not None:
        for role, inventory in sorted(
            fingerprint_target_input_roles(target_root, target_input_roles).items()
        ):
            fingerprints[f"target_role:{role}"] = fingerprint_value(inventory)
    return fingerprints


def _load_json_mapping(path: Path, code: str) -> dict[str, Any]:
    path = filesystem_path(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CheckRunnerError(code, f"{path.name}:{type(exc).__name__}") from exc
    if not isinstance(payload, Mapping):
        raise CheckRunnerError(code, f"{path.name}:object required")
    return dict(payload)


def _canonical_success_slot(
    owner_evidence_root: Path,
    *,
    execution_key: str,
) -> Path:
    if not re.fullmatch(WIRE_HASH_PATTERN, execution_key):
        raise CheckRunnerError("check_execution_key_invalid", execution_key)
    digest = execution_key.split(":", 1)[1]
    return (
        owner_evidence_root
        / "check-executions"
        / "heads"
        / f"{digest}.json"
    )


def _receipt_identity_payload(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": str(receipt.get("schema_version", "")),
        "execution_owner_id": str(receipt.get("execution_owner_id", "")),
        "execution_key": str(receipt.get("execution_key", "")),
        "owner_declaration_hash": str(receipt.get("owner_declaration_hash", "")),
        "owner_input_projection_hash": str(
            receipt.get("owner_input_projection_hash", "")
        ),
        "input_components": list(receipt.get("input_components", [])),
        "dependency_receipts": list(receipt.get("dependency_receipts", [])),
        "target_input_fingerprint": str(
            receipt.get("target_input_fingerprint", "")
        ),
        "toolchain_fingerprint": str(receipt.get("toolchain_fingerprint", "")),
        "execution_environment_fingerprint": str(
            receipt.get("execution_environment_fingerprint", "")
        ),
        "evidence_domain_id": str(receipt.get("evidence_domain_id", "")),
        "impact_policy_id": str(receipt.get("impact_policy_id", "")),
        "status": str(receipt.get("status", "")),
        "sidecars": dict(receipt.get("sidecars", {})),
    }


def _validate_owner_receipt(
    owner_evidence_root: Path,
    receipt: Mapping[str, Any],
    *,
    expected_owner_id: str | None = None,
) -> dict[str, Mapping[str, Any]]:
    required = {
        "schema_version",
        "execution_owner_id",
        "execution_key",
        "owner_declaration_hash",
        "owner_input_projection_hash",
        "input_components",
        "dependency_receipts",
        "target_input_fingerprint",
        "toolchain_fingerprint",
        "execution_environment_fingerprint",
        "evidence_domain_id",
        "impact_policy_id",
        "status",
        "sidecars",
        "receipt_id",
        "receipt_hash",
        "claim_boundary",
    }
    if set(receipt) != required:
        raise CheckRunnerError(
            "check_execution_receipt_invalid", "field set"
        )
    if receipt.get("schema_version") != CHECK_EXECUTION_RECEIPT_SCHEMA:
        raise CheckRunnerError(
            "check_execution_receipt_invalid", "schema_version"
        )
    if expected_owner_id is not None and receipt.get("execution_owner_id") != expected_owner_id:
        raise CheckRunnerError(
            "check_execution_receipt_invalid", "execution_owner_id"
        )
    for field in (
        "execution_key",
        "owner_declaration_hash",
        "owner_input_projection_hash",
        "toolchain_fingerprint",
        "execution_environment_fingerprint",
        "receipt_id",
        "receipt_hash",
    ):
        if not re.fullmatch(WIRE_HASH_PATTERN, str(receipt.get(field, ""))):
            raise CheckRunnerError(
                "check_execution_receipt_invalid", field
            )
    if receipt.get("status") != "passed":
        raise CheckRunnerError("check_execution_receipt_invalid", "status")
    target_input_fingerprint = str(
        receipt.get("target_input_fingerprint", "")
    )
    if target_input_fingerprint and re.fullmatch(
        WIRE_HASH_PATTERN, target_input_fingerprint
    ) is None:
        raise CheckRunnerError(
            "check_execution_receipt_invalid", "target_input_fingerprint"
        )
    input_components = receipt.get("input_components")
    if (
        not isinstance(input_components, list)
        or input_components
        != sorted(
            input_components,
            key=lambda row: str(row.get("component_id", ""))
            if isinstance(row, Mapping)
            else "",
        )
        or len(
            {
                str(row.get("component_id", ""))
                for row in input_components
                if isinstance(row, Mapping)
            }
        )
        != len(input_components)
    ):
        raise CheckRunnerError(
            "check_execution_receipt_invalid", "input_components"
        )
    for component in input_components:
        if not isinstance(component, Mapping) or set(component) != {
            "component_id",
            "component_hash",
        }:
            raise CheckRunnerError(
                "check_execution_receipt_invalid", "input_component"
            )
        if not str(component.get("component_id", "")) or not re.fullmatch(
            WIRE_HASH_PATTERN, str(component.get("component_hash", ""))
        ):
            raise CheckRunnerError(
                "check_execution_receipt_invalid",
                "input_component_identity",
            )
    if wire_hash(input_components) != receipt.get(
        "owner_input_projection_hash"
    ):
        raise CheckRunnerError(
            "check_execution_receipt_invalid",
            "input_component_projection",
        )
    dependencies = receipt.get("dependency_receipts")
    if not isinstance(dependencies, list) or dependencies != sorted(
        dependencies, key=lambda row: str(row.get("execution_owner_id", ""))
    ):
        raise CheckRunnerError(
            "check_execution_receipt_invalid", "dependency_receipts"
        )
    for dependency in dependencies:
        if not isinstance(dependency, Mapping) or set(dependency) != {
            "execution_owner_id",
            "receipt_id",
            "receipt_hash",
        }:
            raise CheckRunnerError(
                "check_execution_receipt_invalid", "dependency_receipt"
            )
        for field in ("receipt_id", "receipt_hash"):
            if not re.fullmatch(WIRE_HASH_PATTERN, str(dependency.get(field, ""))):
                raise CheckRunnerError(
                    "check_execution_receipt_invalid", f"dependency_{field}"
                )
    sidecars = receipt.get("sidecars")
    if not isinstance(sidecars, Mapping) or set(sidecars) != RECEIPT_SIDECAR_KINDS:
        raise CheckRunnerError(
            "check_execution_receipt_invalid", "sidecars"
        )
    loaded: dict[str, Mapping[str, Any]] = {}
    for kind in sorted(RECEIPT_SIDECAR_KINDS):
        reference = sidecars[kind]
        if not isinstance(reference, Mapping):
            raise CheckRunnerError(
                "check_execution_receipt_invalid", f"{kind}_sidecar_ref"
            )
        path = _resolve_owner_ref(
            owner_evidence_root,
            reference,
            code="check_execution_sidecar_invalid",
        )
        if kind in {"result", "termination"}:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise CheckRunnerError(
                    "check_execution_sidecar_invalid", f"{kind}:json"
                ) from exc
            if not isinstance(payload, Mapping):
                raise CheckRunnerError(
                    "check_execution_sidecar_invalid", f"{kind}:object"
                )
            loaded[kind] = dict(payload)
    if loaded["result"].get("schema_version") != CHECK_EXECUTION_RESULT_SIDECAR_SCHEMA:
        raise CheckRunnerError(
            "check_execution_sidecar_invalid", "result:schema"
        )
    if loaded["termination"].get("schema_version") != CHECK_EXECUTION_TERMINATION_SIDECAR_SCHEMA:
        raise CheckRunnerError(
            "check_execution_sidecar_invalid", "termination:schema"
        )
    result_payload = loaded["result"].get("result")
    if (
        not isinstance(result_payload, Mapping)
        or result_payload.get("status") != "passed"
        or result_payload.get("executed") is not True
        or result_payload.get("stdout_sidecar_ref") != sidecars.get("stdout")
        or result_payload.get("stderr_sidecar_ref") != sidecars.get("stderr")
    ):
        raise CheckRunnerError(
            "check_execution_sidecar_invalid", "result:terminal_binding"
        )
    for kind in ("stdout", "stderr"):
        observed_content_hash = str(result_payload.get(f"{kind}_content_hash", ""))
        expected_content_hash = str(sidecars[kind].get("content_hash", ""))
        if observed_content_hash != expected_content_hash:
            raise CheckRunnerError(
                "check_execution_sidecar_invalid", f"{kind}:result_content_hash"
            )
    if loaded["termination"].get("cleanup_confirmed") is not True:
        raise CheckRunnerError(
            "check_execution_sidecar_invalid", "termination:cleanup"
        )
    identity_payload = _receipt_identity_payload(receipt)
    if receipt.get("receipt_id") != wire_hash(identity_payload):
        raise CheckRunnerError(
            "check_execution_receipt_invalid", "receipt_id"
        )
    unsigned = dict(receipt)
    unsigned.pop("receipt_hash", None)
    if receipt.get("receipt_hash") != wire_hash(unsigned):
        raise CheckRunnerError(
            "check_execution_receipt_invalid", "receipt_hash"
        )
    return loaded


def _load_canonical_success(
    owner_evidence_root: Path, identity: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Mapping[str, Any]]] | None:
    head_path = _canonical_success_slot(
        owner_evidence_root,
        execution_key=str(identity["execution_key"]),
    )
    if not filesystem_path(head_path).is_file():
        return None
    head = _load_json_mapping(head_path, "check_execution_head_unreadable")
    unsigned_head = dict(head)
    stored_head_hash = unsigned_head.pop("head_hash", None)
    if set(head) != {
        "schema_version",
        "execution_owner_id",
        "execution_key",
        "receipt_id",
        "receipt_hash",
        "receipt_ref",
        "observed_at",
        "claim_boundary",
        "head_hash",
    } or head.get("schema_version") != CHECK_EXECUTION_HEAD_SCHEMA or (
        stored_head_hash != wire_hash(unsigned_head)
    ):
        raise CheckRunnerError("check_execution_head_invalid", head_path.name)
    if head.get("execution_key") != identity.get("execution_key"):
        raise CheckRunnerError("check_execution_head_invalid", "execution_key")
    if head.get("execution_owner_id") != identity.get("execution_owner_id"):
        raise CheckRunnerError("check_execution_head_invalid", "execution_owner_id")
    receipt_ref = head.get("receipt_ref", {})
    if not isinstance(receipt_ref, Mapping):
        raise CheckRunnerError("check_execution_receipt_ref_invalid", head_path.name)
    receipt_path = _resolve_owner_ref(
        owner_evidence_root,
        receipt_ref,
        code="check_execution_receipt_ref_invalid",
    )
    receipt = _load_json_mapping(
        receipt_path, "check_execution_receipt_unreadable"
    )
    sidecars = _validate_owner_receipt(
        owner_evidence_root,
        receipt,
        expected_owner_id=str(identity["execution_owner_id"]),
    )
    if (
        receipt.get("receipt_id") != head.get("receipt_id")
        or receipt.get("receipt_hash") != head.get("receipt_hash")
        or receipt.get("execution_key") != identity.get("execution_key")
        or receipt.get("input_components")
        != identity.get("owner_input_components")
        or any(
            receipt.get(field) != identity.get(field)
            for field in (
                "execution_owner_id",
                "execution_key",
                "owner_declaration_hash",
                "owner_input_projection_hash",
                "dependency_receipts",
                "target_input_fingerprint",
                "toolchain_fingerprint",
                "execution_environment_fingerprint",
                "evidence_domain_id",
                "impact_policy_id",
            )
        )
    ):
        raise CheckRunnerError(
            "check_execution_receipt_invalid", receipt_path.name
        )
    return receipt, sidecars


def inspect_current_owner_execution(
    check: Mapping[str, Any],
    *,
    skill_root: Path,
    target_root: Path,
    repository_root: Path,
    run_root: Path,
    owner_evidence_root: Path | None = None,
    dependency_execution_receipts: Mapping[
        str, Mapping[str, Any]
    ] | None = None,
) -> dict[str, Any]:
    """Resolve one exact owner receipt without locks, writes, or execution."""

    declared, _manifest = _declared_check_for_run(run_root, check)
    persistent_root = _owner_evidence_root(
        repository_root, owner_evidence_root
    )
    identity = _check_execution_identity(
        declared,
        skill_root=skill_root,
        target_root=target_root,
        repository_root=repository_root,
        run_root=run_root,
        owner_evidence_root=persistent_root,
        dependency_receipts=dict(dependency_execution_receipts or {}),
    )
    try:
        current = _load_canonical_success(persistent_root, identity)
    except CheckRunnerError as exc:
        if exc.code not in {
            "check_execution_head_invalid",
            "check_execution_receipt_ref_invalid",
            "check_execution_receipt_unreadable",
            "check_execution_receipt_invalid",
            "check_execution_sidecar_invalid",
        }:
            raise
        return {
            "identity": identity,
            "receipt": None,
            "sidecars": None,
            "disposition": "execute_owner",
            "reason": exc.code,
        }
    if current is None:
        return {
            "identity": identity,
            "receipt": None,
            "sidecars": None,
            "disposition": "execute_owner",
            "reason": "current_owner_receipt_missing",
        }
    receipt, sidecars = current
    return {
        "identity": identity,
        "receipt": receipt,
        "sidecars": sidecars,
        "disposition": "reuse_owner_receipt",
        "reason": "current_owner_receipt_exact",
    }


def inspect_owner_receipt_history(
    owner_evidence_root: Path,
    *,
    execution_owner_id: str,
    owner_declaration_hash: str,
) -> list[Mapping[str, Any]]:
    """Return valid historical receipts for component-diff planning only."""

    root = owner_evidence_root.resolve()
    heads_root = filesystem_path(root / "check-executions" / "heads")
    receipts: dict[str, Mapping[str, Any]] = {}
    if not heads_root.is_dir():
        return []
    expected_head_fields = {
        "schema_version",
        "execution_owner_id",
        "execution_key",
        "receipt_id",
        "receipt_hash",
        "receipt_ref",
        "observed_at",
        "claim_boundary",
        "head_hash",
    }
    for head_path in sorted(heads_root.glob("*.json")):
        try:
            head = _load_json_mapping(
                head_path, "check_execution_head_unreadable"
            )
            unsigned = dict(head)
            stored_hash = unsigned.pop("head_hash", None)
            if (
                set(head) != expected_head_fields
                or head.get("schema_version") != CHECK_EXECUTION_HEAD_SCHEMA
                or stored_hash != wire_hash(unsigned)
                or head.get("execution_owner_id") != execution_owner_id
                or not isinstance(head.get("receipt_ref"), Mapping)
            ):
                continue
            receipt_path = _resolve_owner_ref(
                root,
                head["receipt_ref"],
                code="check_execution_receipt_ref_invalid",
            )
            receipt = _load_json_mapping(
                receipt_path, "check_execution_receipt_unreadable"
            )
            _validate_owner_receipt(
                root,
                receipt,
                expected_owner_id=execution_owner_id,
            )
            if (
                receipt.get("owner_declaration_hash")
                != owner_declaration_hash
                or receipt.get("receipt_id") != head.get("receipt_id")
                or receipt.get("receipt_hash") != head.get("receipt_hash")
            ):
                continue
            receipts[str(receipt["receipt_hash"])] = receipt
        except (CheckRunnerError, OSError, UnicodeError):
            continue
    return [receipts[key] for key in sorted(receipts)]


def _write_canonical_success(
    owner_evidence_root: Path,
    identity: Mapping[str, Any],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    result_sidecar = _semantic_result_sidecar(result)
    termination_sidecar = _semantic_termination_sidecar(result)
    stdout_ref = result.get("stdout_sidecar_ref")
    stderr_ref = result.get("stderr_sidecar_ref")
    if not isinstance(stdout_ref, Mapping) or not isinstance(stderr_ref, Mapping):
        raise CheckRunnerError(
            "check_execution_output_sidecars_missing",
            str(identity.get("execution_owner_id", "")),
        )
    sidecars = {
        "stdout": dict(stdout_ref),
        "stderr": dict(stderr_ref),
        "result": _persist_json_sidecar(owner_evidence_root, result_sidecar),
        "termination": _persist_json_sidecar(
            owner_evidence_root, termination_sidecar
        ),
    }
    receipt: dict[str, Any] = {
        "schema_version": CHECK_EXECUTION_RECEIPT_SCHEMA,
        "execution_owner_id": str(identity["execution_owner_id"]),
        "execution_key": str(identity["execution_key"]),
        "owner_declaration_hash": str(identity["owner_declaration_hash"]),
        "owner_input_projection_hash": str(
            identity["owner_input_projection_hash"]
        ),
        "input_components": list(identity["owner_input_components"]),
        "dependency_receipts": list(identity["dependency_receipts"]),
        "target_input_fingerprint": str(
            identity["target_input_fingerprint"]
        ),
        "toolchain_fingerprint": str(identity["toolchain_fingerprint"]),
        "execution_environment_fingerprint": str(
            identity["execution_environment_fingerprint"]
        ),
        "evidence_domain_id": str(identity["evidence_domain_id"]),
        "impact_policy_id": str(identity["impact_policy_id"]),
        "status": "passed",
        "sidecars": sidecars,
        "claim_boundary": (
            "This immutable owner receipt covers only its exact declaration, input components, "
            "dependency receipts, target inputs, toolchain, environment, and four verified sidecars."
        ),
    }
    receipt["receipt_id"] = wire_hash(_receipt_identity_payload(receipt))
    receipt["receipt_hash"] = wire_hash(receipt)
    receipt_body = canonical_json_bytes(receipt)
    receipt_content_hash = _wire_bytes_hash(receipt_body)
    receipt_relative = _blob_relative_path(receipt_content_hash, "json")
    durable_write_immutable_json(owner_evidence_root / receipt_relative, receipt)
    head: dict[str, Any] = {
        "schema_version": CHECK_EXECUTION_HEAD_SCHEMA,
        "execution_owner_id": str(identity["execution_owner_id"]),
        "execution_key": str(identity["execution_key"]),
        "receipt_id": str(receipt["receipt_id"]),
        "receipt_hash": str(receipt["receipt_hash"]),
        "receipt_ref": {
            "path_token": OWNER_EVIDENCE_PATH_TOKEN,
            "relative_path": receipt_relative.as_posix(),
            "content_hash": receipt_content_hash,
            "media_type": "application/json",
            "byte_count": len(receipt_body),
        },
        "observed_at": utc_now_precise(),
        "claim_boundary": "This mutable discovery head points to one immutable owner receipt.",
    }
    head["head_hash"] = wire_hash(head)
    durable_write_immutable_json(
        _canonical_success_slot(
            owner_evidence_root,
            execution_key=str(identity["execution_key"]),
        ),
        head,
    )
    return receipt


def _owner_receipt_document_ref(receipt: Mapping[str, Any]) -> dict[str, Any]:
    body = canonical_json_bytes(dict(receipt))
    content_hash = _wire_bytes_hash(body)
    return {
        "path_token": OWNER_EVIDENCE_PATH_TOKEN,
        "relative_path": _blob_relative_path(content_hash, "json").as_posix(),
        "content_hash": content_hash,
        "media_type": "application/json",
        "byte_count": len(body),
    }


def owner_receipt_document_ref(receipt: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return the portable content-addressed locator for one owner receipt."""

    return _owner_receipt_document_ref(receipt)


def _quarantine_corrupt_success(
    owner_evidence_root: Path,
    identity: Mapping[str, Any],
    error: CheckRunnerError,
) -> Mapping[str, Any]:
    head_path = _canonical_success_slot(
        owner_evidence_root,
        execution_key=str(identity["execution_key"]),
    )
    quarantine_root = (
        owner_evidence_root
        / "check-executions"
        / "corrupt"
        / uuid.uuid4().hex
    )
    quarantine_root.mkdir(parents=True, exist_ok=False)
    candidates: dict[Path, str] = {}
    head: Mapping[str, Any] = {}
    if head_path.is_file():
        candidates[head_path] = "head"
        try:
            loaded_head = json.loads(head_path.read_text(encoding="utf-8"))
            if isinstance(loaded_head, Mapping):
                head = loaded_head
        except (OSError, UnicodeError, json.JSONDecodeError):
            pass
    receipt: Mapping[str, Any] = {}
    receipt_ref = head.get("receipt_ref") if isinstance(head, Mapping) else None
    if isinstance(receipt_ref, Mapping):
        relative_text = str(receipt_ref.get("relative_path", ""))
        relative = Path(relative_text)
        if relative_text and not relative.is_absolute():
            receipt_path = (owner_evidence_root / relative).resolve()
            try:
                receipt_path.relative_to(owner_evidence_root.resolve())
            except ValueError:
                receipt_path = Path()
            if receipt_path and receipt_path.is_file():
                candidates[receipt_path] = "receipt"
                try:
                    loaded_receipt = json.loads(
                        receipt_path.read_text(encoding="utf-8")
                    )
                    if isinstance(loaded_receipt, Mapping):
                        receipt = loaded_receipt
                except (OSError, UnicodeError, json.JSONDecodeError):
                    pass
    sidecars = receipt.get("sidecars") if isinstance(receipt, Mapping) else None
    if isinstance(sidecars, Mapping):
        for kind, reference in sidecars.items():
            if not isinstance(reference, Mapping):
                continue
            relative_text = str(reference.get("relative_path", ""))
            relative = Path(relative_text)
            if not relative_text or relative.is_absolute():
                continue
            candidate = (owner_evidence_root / relative).resolve()
            try:
                candidate.relative_to(owner_evidence_root.resolve())
            except ValueError:
                continue
            if not candidate.is_file():
                continue
            expected = str(reference.get("content_hash", ""))
            try:
                actual = _wire_bytes_hash(candidate.read_bytes())
            except OSError:
                actual = ""
            if actual != expected or (
                error.code == "check_execution_sidecar_invalid"
                and str(kind) in {"result", "termination"}
            ):
                candidates[candidate] = f"sidecar:{kind}"
    quarantined: list[dict[str, str]] = []
    for source, role in sorted(candidates.items(), key=lambda row: str(row[0])):
        if not source.is_file():
            continue
        destination = quarantine_root / f"{role.replace(':', '-')}-{source.name}"
        os.replace(source, destination)
        quarantined.append(
            {
                "role": role,
                "original_relative_path": source.relative_to(
                    owner_evidence_root
                ).as_posix(),
                "quarantine_relative_path": destination.relative_to(
                    owner_evidence_root
                ).as_posix(),
            }
        )
    finding: dict[str, Any] = {
        "schema_version": "skillguard.check_execution_corruption_finding.current",
        "execution_owner_id": str(identity.get("execution_owner_id", "")),
        "execution_key": str(identity.get("execution_key", "")),
        "error_code": error.code,
        "error_detail": error.message,
        "quarantined": quarantined,
        "observed_at": utc_now_precise(),
        "claim_boundary": (
            "The previous discovery head was removed from current authority; only a fresh "
            "owner-authorized execution may publish a replacement success."
        ),
    }
    finding_identity = dict(finding)
    finding_identity.pop("observed_at", None)
    finding["finding_id"] = wire_hash(finding_identity)
    finding["finding_hash"] = wire_hash(finding)
    finding_relative = (
        Path("check-executions")
        / "findings"
        / f"{finding['finding_hash'].split(':', 1)[1]}.json"
    )
    durable_write_immutable_json(
        owner_evidence_root / finding_relative,
        finding,
    )
    return finding


def _projection_result_from_receipt(
    declared: Mapping[str, Any],
    manifest: Mapping[str, Any],
    receipt: Mapping[str, Any],
    sidecars: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    result_sidecar = sidecars.get("result", {})
    owner_result = result_sidecar.get("result", {})
    if not isinstance(owner_result, Mapping):
        raise CheckRunnerError(
            "check_execution_sidecar_invalid", "result:payload"
        )
    projected = dict(owner_result)
    projected.update(
        {
            "check_id": str(declared.get("check_id", "")),
            "semantic_check_id": str(
                declared.get("semantic_check_id") or declared.get("check_id", "")
            ),
            "kind": str(declared.get("kind", "")),
            "covers_obligation_ids": list(
                declared.get("covers_obligation_ids")
                or declared.get("covers")
                or []
            ),
            "check_manifest_hash": str(manifest.get("manifest_hash", "")),
            "check_declarations_hash": str(
                manifest.get("check_declarations_hash", "")
            ),
            "declared_check_hash": canonical_hash(dict(declared)),
            "created_at": utc_now(),
            "status": "passed",
            "reason": "verified_owner_receipt_reused",
            "executed": False,
            "process_started": False,
            "command_executed_in_this_call": False,
            "execution_disposition": "reused_terminal_success",
            "execution_owner_id": str(receipt.get("execution_owner_id", "")),
            "execution_key": str(receipt.get("execution_key", "")),
            "projection_declaration_hash": str(
                declared.get("projection_declaration_hash", "")
            ),
            "owner_receipt_id": str(receipt.get("receipt_id", "")),
            "owner_receipt_hash": str(receipt.get("receipt_hash", "")),
            "owner_receipt_ref": _owner_receipt_document_ref(receipt),
            "stdout_sidecar_ref": dict(receipt.get("sidecars", {}).get("stdout", {})),
            "stderr_sidecar_ref": dict(receipt.get("sidecars", {}).get("stderr", {})),
            "claim_boundary": (
                "This current-run projection reuses a verified immutable owner receipt; "
                "it does not claim that the command ran in this call."
            ),
        }
    )
    projected["proof_fingerprint"] = _execution_proof_fingerprint(projected)
    return projected


def get_or_execute_check(
    check: Mapping[str, Any],
    *,
    skill_root: Path,
    target_root: Path,
    repository_root: Path,
    run_root: Path,
    step_id: str,
    owner_evidence_root: Path | None = None,
    dependency_execution_receipts: Mapping[str, Mapping[str, Any]] | None = None,
    progress_context: Mapping[str, Any] | None = None,
    progress_callback: ProgressCallback | None = None,
    process_started_callback: ProcessStartedCallback | None = None,
    heartbeat_interval_seconds: float = 5.0,
) -> dict[str, Any]:
    """Reuse one exact terminal success or execute one new isolated attempt."""

    declared, _manifest = _declared_check_for_run(run_root, check)
    semantic_check_id = str(
        declared.get("semantic_check_id") or declared.get("check_id", "")
    )
    persistent_root = _owner_evidence_root(
        repository_root,
        owner_evidence_root,
    )
    dependency_receipts = dict(dependency_execution_receipts or {})
    tentative_identity = _check_execution_identity(
        declared,
        skill_root=skill_root,
        target_root=target_root,
        repository_root=repository_root,
        run_root=run_root,
        owner_evidence_root=persistent_root,
        dependency_receipts=dependency_receipts,
    )
    try:
        with execution_single_flight_lock(
            persistent_root,
            str(tentative_identity["execution_key"]),
        ):
            identity = _check_execution_identity(
                declared,
                skill_root=skill_root,
                target_root=target_root,
                repository_root=repository_root,
                run_root=run_root,
                owner_evidence_root=persistent_root,
                dependency_receipts=dependency_receipts,
            )
            if identity["execution_key"] != tentative_identity["execution_key"]:
                raise CheckRunnerError(
                    "check_execution_identity_changed_before_lock",
                    semantic_check_id,
                )
            try:
                current = _load_canonical_success(persistent_root, identity)
            except CheckRunnerError as exc:
                if exc.code not in {
                    "check_execution_head_invalid",
                    "check_execution_receipt_ref_invalid",
                    "check_execution_receipt_unreadable",
                    "check_execution_receipt_invalid",
                    "check_execution_sidecar_invalid",
                }:
                    raise
                _quarantine_corrupt_success(persistent_root, identity, exc)
                current = None
            if current is not None:
                receipt, sidecars = current
                raw = _projection_result_from_receipt(
                    declared,
                    _manifest,
                    receipt,
                    sidecars,
                )
                raw["step_id"] = step_id
                record = dict(store_check_result(run_root, step_id, raw))
                return {
                    "disposition": "reused_terminal_success",
                    "record": record,
                    "execution_receipt": receipt,
                    "execution_receipt_ref": _owner_receipt_document_ref(receipt),
                }
            execution_id = "execution-" + canonical_hash(
                {
                    "execution_key": identity["execution_key"],
                    "nonce": uuid.uuid4().hex,
                    "pid": os.getpid(),
                    "started_at": utc_now_precise(),
                }
            )[:24].lower()
            raw = dict(
                execute_check(
                    declared,
                    target_root=target_root,
                    repository_root=repository_root,
                    run_root=run_root,
                    step_id=step_id,
                    owner_evidence_root=persistent_root,
                    progress_context=progress_context,
                    progress_callback=progress_callback,
                    process_started_callback=process_started_callback,
                    heartbeat_interval_seconds=heartbeat_interval_seconds,
                    resolved_launch_plan=identity["_resolved_launch_plan"],
                )
            )
            raw.update(
                {
                    "semantic_check_id": semantic_check_id,
                    "execution_id": execution_id,
                    "execution_key": str(identity["execution_key"]),
                    "execution_owner_id": str(identity["execution_owner_id"]),
                    "projection_declaration_hash": str(
                        declared.get("projection_declaration_hash", "")
                    ),
                    "command_executed_in_this_call": True,
                }
            )
            if raw.get("status") == "passed" and raw.get("executed") is True:
                receipt = _write_canonical_success(
                    persistent_root, identity, raw
                )
                raw.update(
                    {
                        "execution_disposition": "executed_terminal_success",
                        "owner_receipt_id": str(receipt["receipt_id"]),
                        "owner_receipt_hash": str(receipt["receipt_hash"]),
                        "owner_receipt_ref": _owner_receipt_document_ref(receipt),
                    }
                )
                raw["proof_fingerprint"] = _execution_proof_fingerprint(raw)
                record = dict(store_check_result(run_root, step_id, raw))
                return {
                    "disposition": "executed_terminal_success",
                    "record": record,
                    "execution_receipt": receipt,
                    "execution_receipt_ref": _owner_receipt_document_ref(receipt),
                }
            raw["execution_disposition"] = "executed_failed_attempt"
            raw["proof_fingerprint"] = _execution_proof_fingerprint(raw)
            record = dict(store_check_result(run_root, step_id, raw))
            return {
                "disposition": "executed_failed_attempt",
                "record": record,
                "execution_receipt": None,
                "execution_receipt_ref": None,
            }
    except ExecutionRecordError as exc:
        raise CheckRunnerError(exc.code, exc.detail, semantic_check_id) from exc


def execute_check(
    check: Mapping[str, Any],
    *,
    target_root: Path,
    repository_root: Path,
    run_root: Path,
    step_id: str = "",
    owner_evidence_root: Path | None = None,
    progress_context: Mapping[str, Any] | None = None,
    progress_callback: ProgressCallback | None = None,
    process_started_callback: ProcessStartedCallback | None = None,
    heartbeat_interval_seconds: float = 5.0,
    resolved_launch_plan: ResolvedLaunchPlan | None = None,
) -> Mapping[str, Any]:
    check, manifest = _declared_check_for_run(run_root, check)
    check_id = str(check["check_id"])
    kind = str(check.get("kind", ""))
    declared_check_hash = canonical_hash(dict(check))
    base: dict[str, Any] = {
        "check_id": check_id,
        "kind": kind,
        "covers_obligation_ids": list(check.get("covers_obligation_ids") or check.get("covers") or []),
        "check_manifest_hash": str(manifest["manifest_hash"]),
        "check_declarations_hash": str(manifest["check_declarations_hash"]),
        "declared_check_hash": declared_check_hash,
        "created_at": utc_now(),
        "evidence_class": "hard",
    }
    # Runtime depth facts are never copied from the manifest.  An enforced
    # native check must emit a current content-addressed evidence artifact.
    if check.get("applicable") is False:
        return {
            **base,
            "status": "not_run",
            "reason": "declared_not_applicable",
            "executed": False,
            "claim_boundary": "A non-run check provides no passing evidence.",
        }
    if kind not in SUPPORTED_CHECK_KINDS:
        return {
            **base,
            "status": "not_run",
            "reason": "unsupported_check_kind",
            "executed": False,
            "claim_boundary": "Unsupported checks remain not-run and cannot pass.",
        }
    (
        current_launch_plan,
        declared_args,
        args,
        cwd,
        environment,
        execution_environment,
        execution_environment_fingerprint,
    ) = _resolve_check_launch_plan(
        check,
        target_root=target_root,
        repository_root=repository_root,
        run_root=run_root,
    )
    command = str(check.get("command", ""))
    if (
        resolved_launch_plan is not None
        and resolved_launch_plan.record.get("launch_plan_fingerprint")
        != current_launch_plan.record.get("launch_plan_fingerprint")
    ):
        raise CheckRunnerError(
            "launch_plan_changed_after_execution_key",
            "command resolution changed between receipt lookup and process launch",
            check_id,
        )
    launch_plan = resolved_launch_plan or current_launch_plan
    projected_declared_args = [
        redact_runtime_text(
            item,
            {
                "target_root": target_root,
                "repository_root": repository_root,
                "run_root": run_root,
            },
        )
        for item in declared_args
    ]
    cwd_token = str(check.get("cwd_token", "target_root"))
    cwd_relative = str(check.get("cwd_relative", "."))
    if not cwd.is_dir():
        return {
            **base,
            "status": "not_run",
            "reason": "cwd_missing",
            "executed": False,
            "cwd_token": cwd_token,
            "cwd_relative": cwd_relative,
            "claim_boundary": "Missing working directories are not passing executions.",
        }
    retired_target_evidence_fields = sorted(
        field
        for field in (
            "depth_evidence_protocol",
            "depth_evidence_domain",
            "depth_evidence_output",
            "depth_universe_policy_fingerprints",
            "calibration_evidence_protocol",
            "calibration_evidence_domain",
            "calibration_evidence_output",
        )
        if field in check
    )
    if retired_target_evidence_fields:
        raise CheckRunnerError(
            "retired_target_evidence_field",
            ",".join(retired_target_evidence_fields),
            check_id,
        )
    timeout = float(check.get("timeout_seconds", 30))
    if timeout <= 0 or timeout > 3600:
        raise CheckRunnerError("check_timeout_invalid", str(timeout), check_id)
    expected = check.get("expected", {})
    expected_exit = int(expected.get("exit_code", 0)) if isinstance(expected, Mapping) else 0
    context = dict(progress_context or {})
    current_step_id = step_id or str(context.get("step_id", ""))
    completed_before = max(0, int(context.get("completed_count", 0)))
    total_count = max(completed_before + 1, int(context.get("total_count", 1)))
    started_wall = datetime.now(timezone.utc)
    started = started_wall.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    deadline_at = (started_wall + timedelta(seconds=timeout)).isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")
    started_monotonic = time.monotonic()
    heartbeat_interval = max(float(heartbeat_interval_seconds), 0.1)
    _emit_execution_event(
        run_root,
        event_type="start",
        step_id=current_step_id,
        check_id=check_id,
        completed_count=completed_before,
        total_count=total_count,
        elapsed_seconds=0.0,
        started_at=started,
        deadline_at=deadline_at,
        callback=progress_callback,
    )
    if not launch_plan.argv:
        _emit_execution_event(
            run_root,
            event_type="end",
            step_id=current_step_id,
            check_id=check_id,
            completed_count=completed_before,
            total_count=total_count,
            elapsed_seconds=time.monotonic() - started_monotonic,
            started_at=started,
            deadline_at=deadline_at,
            callback=progress_callback,
            status="not_run",
        )
        return {
            **base,
            "status": "not_run",
            "reason": str(launch_plan.record.get("resolution_error_code", "launch_resolution_failed")),
            "executed": False,
            "process_started": False,
            "launch_error_kind": str(launch_plan.record.get("resolution_error_kind", "LaunchPlanError")),
            "terminal_kind": "launch_error",
            "command": command_token(command),
            "command_token": command_token(command),
            "command_fingerprint": command_fingerprint(command, args),
            "args": projected_declared_args,
            "declared_args": projected_declared_args,
            "cwd_token": cwd_token,
            "cwd_relative": cwd_relative,
            "launch_plan": dict(launch_plan.record),
            "launch_plan_fingerprint": str(launch_plan.record.get("launch_plan_fingerprint", "")),
            "step_id": current_step_id,
            "started_at": started,
            "deadline_at": deadline_at,
            "finished_at": utc_now_precise(),
            "claim_boundary": "A blocked launch plan is a non-run and never passing evidence.",
        }
    timed_out = False
    cancelled = False
    exit_code: int | None = None
    termination_facts: Mapping[str, Any] = {
        "termination_scope": "none",
        "termination_attempted": False,
        "termination_succeeded": False,
        "termination_method": "not_required",
        "termination_error_kind": "",
        "cleanup_confirmed": True,
        "cleanup_confirmation_method": "not_required",
        "descendant_count_before": 0,
        "descendant_count_after": 0,
        "remaining_descendant_pids": [],
    }
    with tempfile.TemporaryFile(mode="w+b") as stdout_file, tempfile.TemporaryFile(
        mode="w+b"
    ) as stderr_file:
        try:
            process = subprocess.Popen(
                launch_plan.popen_args,
                cwd=cwd,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=stdout_file,
                stderr=stderr_file,
                shell=False,
                **isolated_process_kwargs(),
            )
            if process_started_callback is not None:
                process_started_callback()
            containment = attach_process_tree_containment(process)
        except OSError as exc:
            launch_error_kind = (
                "executable_missing" if isinstance(exc, FileNotFoundError) else type(exc).__name__
            )
            _emit_execution_event(
                run_root,
                event_type="end",
                step_id=current_step_id,
                check_id=check_id,
                completed_count=completed_before,
                total_count=total_count,
                elapsed_seconds=time.monotonic() - started_monotonic,
                started_at=started,
                deadline_at=deadline_at,
                callback=progress_callback,
                status="not_run",
            )
            return {
                **base,
                "status": "not_run",
                "reason": "executable_missing" if isinstance(exc, FileNotFoundError) else "launch_os_error",
                "executed": False,
                "process_started": False,
                "launch_error_kind": launch_error_kind,
                "terminal_kind": "launch_error",
                "command": command_token(command),
                "command_token": command_token(command),
                "command_fingerprint": command_fingerprint(command, args),
                "launch_plan": dict(launch_plan.record),
                "launch_plan_fingerprint": str(launch_plan.record["launch_plan_fingerprint"]),
                "args": projected_declared_args,
                "declared_args": projected_declared_args,
                "cwd_token": cwd_token,
                "cwd_relative": cwd_relative,
                "step_id": current_step_id,
                "started_at": started,
                "deadline_at": deadline_at,
                "finished_at": utc_now_precise(),
                "claim_boundary": "A process launch error is a non-run, never a pass.",
            }
        next_heartbeat = started_monotonic + heartbeat_interval
        last_output_bytes = 0
        last_progress_at = started_monotonic
        try:
            while process.poll() is None:
                now = time.monotonic()
                elapsed = now - started_monotonic
                if now >= next_heartbeat:
                    stdout_bytes = os.fstat(stdout_file.fileno()).st_size
                    stderr_bytes = os.fstat(stderr_file.fileno()).st_size
                    output_bytes = stdout_bytes + stderr_bytes
                    if output_bytes > last_output_bytes:
                        _emit_execution_event(
                            run_root,
                            event_type="progress",
                            step_id=current_step_id,
                            check_id=check_id,
                            completed_count=completed_before,
                            total_count=total_count,
                            elapsed_seconds=elapsed,
                            started_at=started,
                            deadline_at=deadline_at,
                            callback=progress_callback,
                            stdout_total_bytes=stdout_bytes,
                            stderr_total_bytes=stderr_bytes,
                            progress_delta_bytes=output_bytes - last_output_bytes,
                            no_progress_ms=0,
                        )
                        last_output_bytes = output_bytes
                        last_progress_at = now
                    _emit_execution_event(
                        run_root,
                        event_type="heartbeat",
                        step_id=current_step_id,
                        check_id=check_id,
                        completed_count=completed_before,
                        total_count=total_count,
                        elapsed_seconds=elapsed,
                        started_at=started,
                        deadline_at=deadline_at,
                        callback=progress_callback,
                        stdout_total_bytes=stdout_bytes,
                        stderr_total_bytes=stderr_bytes,
                        progress_delta_bytes=0,
                        no_progress_ms=max(0, round((now - last_progress_at) * 1000)),
                    )
                    next_heartbeat = now + heartbeat_interval
                if elapsed >= timeout:
                    timed_out = True
                    break
                time.sleep(0.05)
        except (KeyboardInterrupt, SystemExit):
            cancelled = True
        finally:
            termination_facts = release_process_tree_containment(
                process,
                containment,
                timed_out=timed_out,
            )
        exit_code = process.returncode
        stdout, stdout_content_hash, stdout_truncated, stdout_total_bytes, stdout_captured_bytes = _capture_file(stdout_file)
        stderr, stderr_content_hash, stderr_truncated, stderr_total_bytes, stderr_captured_bytes = _capture_file(stderr_file)
        stdout_sidecar_ref = (
            _persist_stream_sidecar(
                owner_evidence_root,
                stdout_file,
                media_type="application/octet-stream",
            )
            if owner_evidence_root is not None
            else None
        )
        stderr_sidecar_ref = (
            _persist_stream_sidecar(
                owner_evidence_root,
                stderr_file,
                media_type="application/octet-stream",
            )
            if owner_evidence_root is not None
            else None
        )
    captured_output_bytes = stdout_captured_bytes + stderr_captured_bytes
    final_output_bytes = stdout_total_bytes + stderr_total_bytes
    if timed_out and final_output_bytes > last_output_bytes:
        _emit_execution_event(
            run_root,
            event_type="progress",
            step_id=current_step_id,
            check_id=check_id,
            completed_count=completed_before,
            total_count=total_count,
            elapsed_seconds=time.monotonic() - started_monotonic,
            started_at=started,
            deadline_at=deadline_at,
            callback=progress_callback,
            status="timed_out",
            stdout_total_bytes=stdout_total_bytes,
            stderr_total_bytes=stderr_total_bytes,
            progress_delta_bytes=final_output_bytes - last_output_bytes,
            no_progress_ms=0,
        )
    finished_at = utc_now_precise()
    elapsed_seconds = round(time.monotonic() - started_monotonic, 3)
    elapsed_ms = max(0, round(elapsed_seconds * 1000))
    cleanup_confirmed = bool(termination_facts.get("cleanup_confirmed", False))
    status = (
        "failed"
        if timed_out or not cleanup_confirmed
        else "passed"
        if exit_code == expected_exit
        else "failed"
    )
    reason = (
        "cleanup_unconfirmed"
        if (timed_out or cancelled) and not cleanup_confirmed
        else "cancelled"
        if cancelled
        else "timeout"
        if timed_out
        else "cleanup_unconfirmed"
        if not cleanup_confirmed
        else "expected_exit_observed"
        if status == "passed"
        else "unexpected_exit_code"
    )
    result = {
        **base,
        "status": status,
        "reason": reason,
        "executed": True,
        "process_started": True,
        "launch_error_kind": "",
        "terminal_kind": (
            "timeout"
            if timed_out
            else "cleanup_unconfirmed"
            if not cleanup_confirmed
            else "exit"
        ),
        "command": command_token(command),
        "command_token": command_token(command),
        "command_fingerprint": command_fingerprint(command, args),
        "launch_plan": dict(launch_plan.record),
        "launch_plan_fingerprint": str(launch_plan.record["launch_plan_fingerprint"]),
        "args": projected_declared_args,
        "declared_args": projected_declared_args,
        "cwd_token": cwd_token,
        "cwd_relative": cwd_relative,
        "timeout_seconds": timeout,
        "exit_code": exit_code,
        "expected_exit_code": expected_exit,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_content_hash": stdout_content_hash,
        "stderr_content_hash": stderr_content_hash,
        "stdout_total_bytes": stdout_total_bytes,
        "stderr_total_bytes": stderr_total_bytes,
        "stdout_captured_bytes": stdout_captured_bytes,
        "stderr_captured_bytes": stderr_captured_bytes,
        "output_truncated": stdout_truncated or stderr_truncated,
        "stdout_sidecar_ref": stdout_sidecar_ref,
        "stderr_sidecar_ref": stderr_sidecar_ref,
        "execution_environment": execution_environment,
        "execution_environment_fingerprint": execution_environment_fingerprint,
        "step_id": current_step_id,
        "started_at": started,
        "deadline_at": deadline_at,
        "finished_at": finished_at,
        "elapsed_seconds": elapsed_seconds,
        "elapsed_ms": elapsed_ms,
        **dict(termination_facts),
        "claim_boundary": (
            "A timed-out execution is failed evidence with a private timeout receipt."
            if timed_out
            else "Process-tree cleanup was not confirmed, so this execution cannot pass."
            if not cleanup_confirmed
            else "This result covers only the exact declared shell-free execution."
        ),
    }
    result["_persisted_stdout"] = redact_runtime_text(
        stdout,
        {
            "target_root": target_root,
            "repository_root": repository_root,
            "run_root": run_root,
        },
    )
    result["_persisted_stderr"] = redact_runtime_text(
        stderr,
        {
            "target_root": target_root,
            "repository_root": repository_root,
            "run_root": run_root,
        },
    )
    if timed_out:
        partial_output_content_hash = wire_hash(
            {"stdout_content_hash": stdout_content_hash, "stderr_content_hash": stderr_content_hash}
        )
        run_record = load_run(run_root)
        receipt_payload = {
                "schema_version": CHECK_TIMEOUT_SCHEMA,
                "artifact_type": "skillguard_check_timeout_receipt",
                "status": "timed_out",
                "owner_ref": {
                    "owner_type": "manifest_bound_check",
                    "owner_hash": canonical_hash(
                        {
                            "run_id": run_record["run_id"],
                            "contract_hash": run_record["contract_hash"],
                            "check_manifest_hash": run_record["check_manifest_hash"],
                            "check_declarations_hash": run_record["check_declarations_hash"],
                            "declared_check_hash": declared_check_hash,
                            "execution_environment_fingerprint": execution_environment_fingerprint,
                            "step_id": current_step_id,
                            "check_id": check_id,
                        }
                    ),
                    "run_id": str(run_record["run_id"]),
                    "contract_hash": str(run_record["contract_hash"]),
                    "check_manifest_hash": str(run_record["check_manifest_hash"]),
                    "check_declarations_hash": str(run_record["check_declarations_hash"]),
                    "declared_check_hash": declared_check_hash,
                    "execution_environment_fingerprint": execution_environment_fingerprint,
                },
                "step_id": current_step_id,
                "check_id": check_id,
                "command_token": command_token(command),
                "command_fingerprint": command_fingerprint(command, args),
                "launch_plan_fingerprint": str(launch_plan.record["launch_plan_fingerprint"]),
                "resolved_program_identity": str(launch_plan.record["resolved_program_identity"]),
                "resolved_interpreter_identity": str(launch_plan.record["interpreter_identity"]),
                "started_at": started,
                "deadline_at": deadline_at,
                "finished_at": finished_at,
                "elapsed_ms": elapsed_ms,
                "timeout_ms": round(timeout * 1000),
                "stdout_content_hash": stdout_content_hash,
                "stderr_content_hash": stderr_content_hash,
                "stdout_total_bytes": stdout_total_bytes,
                "stderr_total_bytes": stderr_total_bytes,
                "stdout_captured_bytes": stdout_captured_bytes,
                "stderr_captured_bytes": stderr_captured_bytes,
                "output_truncated": stdout_truncated or stderr_truncated,
                "partial_output_content_hash": partial_output_content_hash,
                "reason": "declared_timeout_elapsed",
                "resume_action": "resume the claimed run and replay this step before closure",
                "retry_action": "diagnose duration/output, then retry the same manifest-bound check",
                "terminal_kind": "timeout",
                **dict(termination_facts),
                "claim_boundary": "This private runtime receipt proves timeout facts only; it is not passing evidence.",
            }
        try:
            timeout_receipt = write_timeout_receipt(
                run_root,
                receipt_payload,
                expected_schema=CHECK_TIMEOUT_SCHEMA,
            )
        except (ExecutionRecordError, OSError) as exc:
            result["timeout_receipt_write_status"] = "failed"
            result["timeout_receipt_error_kind"] = type(exc).__name__
        else:
            result["timeout_receipt_write_status"] = str(
                timeout_receipt["receipt_write_status"]
            )
            result["timeout_receipt_id"] = timeout_receipt["receipt_id"]
            result["timeout_receipt_ref"] = timeout_receipt["receipt_ref"]
            result["timeout_receipt_hash"] = timeout_receipt["receipt_hash"]
    result["proof_fingerprint"] = _execution_proof_fingerprint(result)
    _emit_execution_event(
        run_root,
        event_type="end",
        step_id=current_step_id,
        check_id=check_id,
        completed_count=completed_before + 1,
        total_count=total_count,
        elapsed_seconds=elapsed_seconds,
        started_at=started,
        deadline_at=deadline_at,
        callback=progress_callback,
        status="timed_out" if timed_out else str(result.get("status", status)),
        stdout_total_bytes=stdout_total_bytes,
        stderr_total_bytes=stderr_total_bytes,
        progress_delta_bytes=0,
        no_progress_ms=max(0, round((time.monotonic() - last_progress_at) * 1000)),
    )
    return result


def store_check_result(run_root: Path, step_id: str, result: Mapping[str, Any]) -> Mapping[str, Any]:
    run = load_run(run_root)
    contract = load_contract_snapshot(run_root)
    manifest = load_check_manifest_snapshot(run_root)
    declared_steps = {
        str(row.get("step_id", ""))
        for row in contract.get("steps", [])
        if isinstance(row, Mapping)
    }
    if step_id not in declared_steps:
        raise CheckRunnerError("check_result_step_unknown", step_id, str(result.get("check_id", "")))
    check_id = str(result.get("check_id", ""))
    declared = next(
        (
            row
            for row in manifest.get("checks", [])
            if isinstance(row, Mapping) and row.get("check_id") == check_id
        ),
        None,
    )
    declared_check_hash = canonical_hash(dict(declared)) if declared is not None else ""
    if (
        declared is None
        or result.get("check_manifest_hash") != run.get("check_manifest_hash")
        or result.get("check_declarations_hash")
        != run.get("check_declarations_hash")
        or result.get("declared_check_hash") != declared_check_hash
    ):
        raise CheckRunnerError(
            "check_result_manifest_binding_invalid",
            "check result is not bound to the immutable declared check",
            check_id,
        )
    if result.get("executed") is True or result.get("status") == "passed":
        expected_proof = _execution_proof_fingerprint(result)
        if result.get("proof_fingerprint") != expected_proof:
            raise CheckRunnerError(
                "check_result_proof_fingerprint_invalid",
                "stored check result proof does not match its execution payload",
                check_id,
            )
    persisted_result = _stable_persisted_result(result)
    diagnostic_stdout = str(persisted_result.pop("_persisted_stdout", ""))
    diagnostic_stderr = str(persisted_result.pop("_persisted_stderr", ""))
    if "stdout" in persisted_result or "stderr" in persisted_result:
        diagnostic: dict[str, Any] = {
            "schema_version": "skillguard.check_output_diagnostic.v1",
            "artifact_type": "skillguard_check_output_diagnostic",
            "run_id": str(run["run_id"]),
            "step_id": step_id,
            "check_id": check_id,
            "stdout": diagnostic_stdout,
            "stderr": diagnostic_stderr,
            "stdout_content_hash": str(result.get("stdout_content_hash", "")),
            "stderr_content_hash": str(result.get("stderr_content_hash", "")),
            "stdout_total_bytes": int(result.get("stdout_total_bytes", 0)),
            "stderr_total_bytes": int(result.get("stderr_total_bytes", 0)),
            "stdout_captured_bytes": int(result.get("stdout_captured_bytes", 0)),
            "stderr_captured_bytes": int(result.get("stderr_captured_bytes", 0)),
            "output_truncated": bool(result.get("output_truncated", False)),
            "privacy": "private_run_diagnostic_redacted",
            "claim_boundary": "Bounded redacted diagnostics are not passing evidence.",
        }
        diagnostic["diagnostic_hash"] = canonical_hash(diagnostic)
        diagnostic_relative = Path("diagnostics") / (
            f"check-output-{diagnostic['diagnostic_hash'][:24].lower()}.json"
        )
        durable_write_immutable_json(run_root / diagnostic_relative, diagnostic)
        persisted_result["stdout"] = ""
        persisted_result["stderr"] = ""
        persisted_result["diagnostic_ref"] = {
            "path_token": "run_root",
            "relative_path": diagnostic_relative.as_posix(),
        }
        persisted_result["diagnostic_hash"] = diagnostic["diagnostic_hash"]
    record: dict[str, Any] = {
        "schema_version": "skillguard.check_result.v2",
        "record_role": (
            "current_run_projection"
            if result.get("status") == "passed"
            else "failed_attempt"
        ),
        "run_id": str(run["run_id"]),
        "contract_hash": str(run["contract_hash"]),
        "check_manifest_hash": str(run["check_manifest_hash"]),
        "check_declarations_hash": str(run["check_declarations_hash"]),
        "declared_check_hash": declared_check_hash,
        "step_id": step_id,
        "check_id": str(result.get("check_id", "")),
        "semantic_check_id": str(
            result.get("semantic_check_id") or result.get("check_id", "")
        ),
        "execution_id": str(result.get("execution_id", "")),
        "execution_key": str(result.get("execution_key", "")),
        "execution_owner_id": str(result.get("execution_owner_id", "")),
        "projection_declaration_hash": str(
            result.get("projection_declaration_hash", "")
        ),
        "execution_disposition": str(
            result.get("execution_disposition", "")
        ),
        "command_executed_in_this_call": bool(
            result.get("command_executed_in_this_call", False)
        ),
        "owner_receipt_id": str(result.get("owner_receipt_id", "")),
        "owner_receipt_hash": str(result.get("owner_receipt_hash", "")),
        "owner_receipt_ref": result.get("owner_receipt_ref"),
        "source_authority_hash": str(
            result.get("source_authority_hash", "")
        ),
        "status": str(result.get("status", "")),
        "executed": bool(result.get("executed", False)),
        "proof_fingerprint": str(result.get("proof_fingerprint", "")),
        "result": persisted_result,
        "created_at": utc_now(),
    }
    record_id_source = dict(record)
    record_id_source.pop("created_at", None)
    record["check_record_id"] = f"check-record-{canonical_hash(record_id_source)[:24].lower()}"
    record["record_hash"] = canonical_hash(record)
    root = filesystem_path(run_root / "checks")
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{record['check_record_id']}.json"
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError as exc:
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as read_exc:
            raise CheckRunnerError(
                "check_record_collision", path.name, str(result.get("check_id", ""))
            ) from read_exc
        existing_identity = dict(existing) if isinstance(existing, Mapping) else {}
        existing_identity.pop("created_at", None)
        existing_identity.pop("record_hash", None)
        candidate_identity = dict(record)
        candidate_identity.pop("created_at", None)
        candidate_identity.pop("record_hash", None)
        if existing_identity == candidate_identity:
            return existing
        raise CheckRunnerError("check_record_collision", path.name, str(result.get("check_id", ""))) from exc
    try:
        os.write(descriptor, canonical_json_bytes(record))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return record


def load_check_result(run_root: Path, check_record_id: str) -> Mapping[str, Any]:
    path = filesystem_path(
        run_root / "checks" / f"{check_record_id}.json"
    )
    try:
        import json

        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CheckRunnerError("check_record_unreadable", type(exc).__name__, check_record_id) from exc
    if not isinstance(record, Mapping):
        raise CheckRunnerError("check_record_not_object", path.name, check_record_id)
    unsigned = dict(record)
    stored_hash = str(unsigned.pop("record_hash", ""))
    if not stored_hash or stored_hash != canonical_hash(unsigned):
        raise CheckRunnerError("check_record_hash_mismatch", path.name, check_record_id)
    if record.get("check_record_id") != check_record_id:
        raise CheckRunnerError("check_record_id_mismatch", path.name, check_record_id)
    run = load_run(run_root)
    manifest = load_check_manifest_snapshot(run_root)
    declared = next(
        (
            row
            for row in manifest.get("checks", [])
            if isinstance(row, Mapping) and row.get("check_id") == record.get("check_id")
        ),
        None,
    )
    if (
        declared is None
        or record.get("check_manifest_hash") != run.get("check_manifest_hash")
        or record.get("check_declarations_hash")
        != run.get("check_declarations_hash")
        or record.get("declared_check_hash") != canonical_hash(dict(declared))
    ):
        raise CheckRunnerError(
            "check_record_manifest_binding_invalid",
            path.name,
            check_record_id,
        )
    return record


def load_owner_receipt_from_projection(
    owner_evidence_root: Path,
    projection_record: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Recompute and verify the persistent owner receipt named by one run projection."""

    reference = projection_record.get("owner_receipt_ref")
    if not isinstance(reference, Mapping):
        raise CheckRunnerError(
            "check_owner_receipt_projection_missing",
            str(projection_record.get("check_id", "")),
        )
    path = _resolve_owner_ref(
        owner_evidence_root.resolve(),
        reference,
        code="check_owner_receipt_projection_invalid",
    )
    receipt = _load_json_mapping(
        path, "check_owner_receipt_projection_unreadable"
    )
    _validate_owner_receipt(
        owner_evidence_root.resolve(),
        receipt,
        expected_owner_id=str(projection_record.get("execution_owner_id", "")),
    )
    if (
        projection_record.get("owner_receipt_id") != receipt.get("receipt_id")
        or projection_record.get("owner_receipt_hash")
        != receipt.get("receipt_hash")
        or projection_record.get("execution_key")
        != receipt.get("execution_key")
    ):
        raise CheckRunnerError(
            "check_owner_receipt_projection_mismatch",
            str(projection_record.get("check_id", "")),
        )
    return receipt


def load_owner_receipt_from_ref(
    owner_evidence_root: Path,
    reference: Mapping[str, Any],
    *,
    expected_owner_id: str | None = None,
) -> Mapping[str, Any]:
    """Read and fully verify one portable owner receipt reference."""

    path = _resolve_owner_ref(
        owner_evidence_root.resolve(),
        reference,
        code="check_owner_receipt_ref_invalid",
    )
    receipt = _load_json_mapping(path, "check_owner_receipt_ref_unreadable")
    _validate_owner_receipt(
        owner_evidence_root.resolve(),
        receipt,
        expected_owner_id=expected_owner_id,
    )
    return receipt


def load_run_owner_receipt_index(
    run_root: Path,
    owner_evidence_root: Path,
) -> dict[str, Mapping[str, Any]]:
    """Rebuild the verified owner receipt index from current-run projections."""

    index: dict[str, Mapping[str, Any]] = {}
    checks_root = run_root / "checks"
    if not checks_root.is_dir():
        return index
    for path in sorted(checks_root.glob("check-record-*.json")):
        record = load_check_result(run_root, path.stem)
        if record.get("status") != "passed":
            continue
        owner_id = str(record.get("execution_owner_id", ""))
        if not owner_id:
            continue
        receipt = load_owner_receipt_from_projection(
            owner_evidence_root,
            record,
        )
        previous = index.get(owner_id)
        if previous is not None and (
            previous.get("receipt_id") != receipt.get("receipt_id")
            or previous.get("receipt_hash") != receipt.get("receipt_hash")
        ):
            raise CheckRunnerError(
                "check_owner_receipt_index_conflict", owner_id
            )
        index[owner_id] = receipt
    return index


def hard_evidence_from_check(result: Mapping[str, Any]) -> Mapping[str, Any]:
    if result.get("status") != "passed":
        raise CheckRunnerError(
            "check_cannot_be_hard_evidence",
            str(result.get("status", "missing")),
            str(result.get("check_id", "")),
        )
    check_record_id = str(result.get("check_record_id", ""))
    check_record_hash = str(result.get("record_hash", ""))
    if not check_record_id or not check_record_hash:
        raise CheckRunnerError(
            "check_result_not_immutably_stored",
            "store the current check result before deriving hard evidence",
            str(result.get("check_id", "")),
        )
    disposition = str(result.get("execution_disposition", ""))
    if disposition not in {
        "executed_terminal_success",
        "reused_terminal_success",
    }:
        raise CheckRunnerError(
            "check_execution_disposition_invalid",
            disposition or "missing",
            str(result.get("check_id", "")),
        )
    if not all(
        re.fullmatch(WIRE_HASH_PATTERN, str(result.get(field, "")))
        for field in (
            "execution_key",
            "projection_declaration_hash",
            "owner_receipt_id",
            "owner_receipt_hash",
        )
    ) or not isinstance(result.get("owner_receipt_ref"), Mapping):
        raise CheckRunnerError(
            "check_owner_receipt_projection_missing",
            str(result.get("check_id", "")),
            str(result.get("check_id", "")),
        )
    proof_fingerprint = str(result.get("proof_fingerprint", ""))
    if not proof_fingerprint:
        raise CheckRunnerError(
            "check_proof_fingerprint_missing",
            "passed check result lacks proof fingerprint",
            str(result.get("check_id", "")),
        )
    execution = result.get("result") if isinstance(result.get("result"), Mapping) else result
    evidence = {
        "proof_kind": "owner_receipt_projection",
        "proof_fingerprint": proof_fingerprint,
        "check_id": str(result.get("check_id", "")),
        "check_record_id": check_record_id,
        "check_record_hash": check_record_hash,
        "check_manifest_hash": str(result.get("check_manifest_hash", "")),
        "check_declarations_hash": str(result.get("check_declarations_hash", "")),
        "declared_check_hash": str(result.get("declared_check_hash", "")),
        "execution_owner_id": str(result.get("execution_owner_id", "")),
        "execution_key": str(result.get("execution_key", "")),
        "projection_declaration_hash": str(
            result.get("projection_declaration_hash", "")
        ),
        "execution_disposition": disposition,
        "command_executed_in_this_call": bool(
            result.get("command_executed_in_this_call", False)
        ),
        "owner_receipt_id": str(result.get("owner_receipt_id", "")),
        "owner_receipt_hash": str(result.get("owner_receipt_hash", "")),
        "owner_receipt_ref": dict(result.get("owner_receipt_ref", {})),
        "exit_code": execution.get("exit_code"),
        "stdout_content_hash": str(execution.get("stdout_content_hash", "")),
        "stderr_content_hash": str(execution.get("stderr_content_hash", "")),
        "execution_environment_fingerprint": str(
            execution.get("execution_environment_fingerprint", "")
        ),
        "claim_boundary": (
            "This hard evidence is a current check projection over one independently "
            "verified immutable owner receipt; reuse does not claim a new command execution."
        ),
    }
    return evidence
