"""Durable, hash-bound execution progress and timeout records.

The helpers in this module deliberately separate three authorities:

* progress events are liveness/observation records, never passing evidence;
* timeout receipts prove only the exact failed execution boundary;
* process termination facts report what was attempted and observed without
  upgrading a timeout into a successful check.
"""

from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import uuid
import re
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Iterator, Mapping, Sequence

from .contract_compiler import canonical_hash, canonical_json_bytes


PROGRESS_EVENT_SCHEMA = "skillguard.execution_progress_event.v1"
CHECK_TIMEOUT_SCHEMA = "skillguard.check_timeout_receipt.v1"
TEST_MESH_TIMEOUT_SCHEMA = "skillguard.test_mesh_timeout_receipt.v1"
TIMEOUT_POLICY_VERSION = "skillguard.timeout_policy.v1"

TIMEOUT_RECEIPT_PREFIXES = {
    CHECK_TIMEOUT_SCHEMA: "timeout-",
    TEST_MESH_TIMEOUT_SCHEMA: "test-timeout-",
}


@dataclass
class ExecutionRecordError(RuntimeError):
    code: str
    detail: str = ""

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}" if self.detail else self.code


def utc_now_precise() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _durable_mkdir(path: Path) -> None:
    missing: list[Path] = []
    cursor = path
    while not cursor.exists():
        missing.append(cursor)
        if cursor.parent == cursor:
            break
        cursor = cursor.parent
    if cursor.exists() and not cursor.is_dir():
        raise ExecutionRecordError("record_parent_not_directory", str(cursor))
    for directory in reversed(missing):
        directory.mkdir()
        _fsync_directory(directory.parent)
        _fsync_directory(directory)


def _windows_extended_path(path: Path) -> str:
    resolved = os.path.abspath(os.fspath(path))
    if resolved.startswith("\\\\?\\"):
        return resolved
    if resolved.startswith("\\\\"):
        return "\\\\?\\UNC\\" + resolved[2:]
    return "\\\\?\\" + resolved


def filesystem_path(path: Path) -> Path:
    """Return the one OS-safe path spelling for filesystem operations."""

    if os.name == "nt":
        return Path(_windows_extended_path(path))
    return path


def _windows_move_no_replace(source: Path, destination: Path) -> None:
    import ctypes

    move_file_ex = ctypes.WinDLL("kernel32", use_last_error=True).MoveFileExW
    move_file_ex.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
    move_file_ex.restype = ctypes.c_int
    # MOVEFILE_WRITE_THROUGH, intentionally without MOVEFILE_REPLACE_EXISTING.
    if not move_file_ex(
        _windows_extended_path(source),
        _windows_extended_path(destination),
        0x00000008,
    ):
        raise ctypes.WinError(ctypes.get_last_error())


def _publish_no_replace(source: Path, destination: Path) -> None:
    if os.name == "nt":
        _windows_move_no_replace(source, destination)
        return
    os.link(source, destination)
    source.unlink()
    _fsync_directory(destination.parent)


def _same_bytes(path: Path, payload: bytes) -> bool:
    try:
        return path.read_bytes() == payload
    except OSError:
        return False


def durable_write_immutable_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Publish one canonical JSON record without replacing an existing record."""

    display_path = path
    path = filesystem_path(path)
    body = canonical_json_bytes(dict(payload))
    _durable_mkdir(path.parent)
    if path.exists():
        if _same_bytes(path, body):
            return
        raise ExecutionRecordError("immutable_record_collision", path.name)
    # Keep the same-directory staging name independent of the destination name.
    # Repeating a long receipt name in the temporary filename can push an otherwise
    # portable Windows path beyond the legacy MAX_PATH boundary before publication.
    temporary = path.with_name(f".sg-{uuid.uuid4().hex}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)
    try:
        _publish_no_replace(temporary, path)
    except OSError as exc:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        if path.exists() and _same_bytes(path, body):
            return
        if path.exists():
            raise ExecutionRecordError(
                "immutable_record_collision", display_path.name
            ) from exc
        raise ExecutionRecordError("immutable_record_publish_failed", type(exc).__name__) from exc


def durable_copy_immutable_stream(
    path: Path,
    source: BinaryIO,
    *,
    expected_content_hash: str,
) -> None:
    """Publish one immutable byte stream under its verified content address."""

    if not re.fullmatch(r"sha256:[0-9a-f]{64}", str(expected_content_hash)):
        raise ExecutionRecordError(
            "immutable_stream_hash_invalid", str(expected_content_hash)
        )
    display_path = path
    path = filesystem_path(path)
    _durable_mkdir(path.parent)

    def stream_hash(handle: BinaryIO) -> str:
        handle.seek(0)
        digest = hashlib.sha256()
        while True:
            chunk = handle.read(64 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        return "sha256:" + digest.hexdigest()

    if stream_hash(source) != expected_content_hash:
        raise ExecutionRecordError(
            "immutable_stream_source_hash_mismatch", display_path.name
        )
    if path.exists():
        try:
            with path.open("rb") as existing:
                if stream_hash(existing) == expected_content_hash:
                    return
        except OSError as exc:
            raise ExecutionRecordError(
                "immutable_stream_existing_unreadable", display_path.name
            ) from exc
        raise ExecutionRecordError("immutable_record_collision", display_path.name)

    temporary = path.with_name(f".sg-{uuid.uuid4().hex}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        source.seek(0)
        with os.fdopen(descriptor, "wb", closefd=False) as target:
            while True:
                chunk = source.read(64 * 1024)
                if not chunk:
                    break
                target.write(chunk)
            target.flush()
            os.fsync(target.fileno())
    finally:
        os.close(descriptor)
    try:
        _publish_no_replace(temporary, path)
    except OSError as exc:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        if path.exists():
            try:
                with path.open("rb") as existing:
                    if stream_hash(existing) == expected_content_hash:
                        return
            except OSError:
                pass
            raise ExecutionRecordError(
                "immutable_record_collision", display_path.name
            ) from exc
        raise ExecutionRecordError(
            "immutable_record_publish_failed", type(exc).__name__
        ) from exc


@contextmanager
def _portable_file_lock(path: Path, timeout_seconds: float = 5.0) -> Iterator[None]:
    path = filesystem_path(path)
    _durable_mkdir(path.parent)
    handle = path.open("a+b")
    try:
        if path.stat().st_size == 0:
            handle.write(b"\0")
            handle.flush()
            os.fsync(handle.fileno())
        deadline = time.monotonic() + timeout_seconds
        while True:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise ExecutionRecordError("execution_record_lock_timeout", path.name) from exc
                time.sleep(0.02)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


@contextmanager
def execution_single_flight_lock(
    owner_evidence_root: Path,
    execution_key: str,
    *,
    timeout_seconds: float = 30.0,
) -> Iterator[None]:
    """Serialize one exact owner execution across all claimed runs."""

    if not re.fullmatch(r"sha256:[0-9a-f]{64}", str(execution_key)):
        raise ExecutionRecordError(
            "execution_single_flight_key_invalid", str(execution_key)
        )
    digest = str(execution_key).split(":", 1)[1]
    path = (
        owner_evidence_root.resolve()
        / "check-executions"
        / "locks"
        / f"{digest}.lock"
    )
    with _portable_file_lock(path, timeout_seconds=timeout_seconds):
        yield


def _hash_without(payload: Mapping[str, Any], field: str) -> str:
    unsigned = dict(payload)
    unsigned.pop(field, None)
    return canonical_hash(unsigned)


def validate_progress_event(event: Mapping[str, Any]) -> None:
    required = {
        "schema_version",
        "artifact_type",
        "event_id",
        "sequence",
        "previous_event_hash",
        "event_hash",
        "event_type",
        "scope",
        "completed_count",
        "total_count",
        "elapsed_ms",
        "started_at",
        "deadline_at",
        "status",
        "emitted_at",
        "authority",
        "event_log_ref",
    }
    if event.get("schema_version") != PROGRESS_EVENT_SCHEMA:
        raise ExecutionRecordError("progress_event_schema_unsupported")
    missing = sorted(required - set(event))
    if missing:
        raise ExecutionRecordError("progress_event_fields_missing", ",".join(missing))
    if event.get("event_type") not in {"start", "progress", "heartbeat", "end"}:
        raise ExecutionRecordError("progress_event_type_invalid", str(event.get("event_type")))
    sequence = event.get("sequence")
    if not isinstance(sequence, int) or sequence < 1:
        raise ExecutionRecordError("progress_event_sequence_invalid")
    completed = event.get("completed_count")
    total = event.get("total_count")
    if not isinstance(completed, int) or not isinstance(total, int) or completed < 0 or total < completed:
        raise ExecutionRecordError("progress_event_counts_invalid")
    locator = event.get("event_log_ref")
    if not isinstance(locator, Mapping) or not locator.get("path_token") or not locator.get("relative_path"):
        raise ExecutionRecordError("progress_event_locator_invalid")
    if event.get("event_hash") != _hash_without(event, "event_hash"):
        raise ExecutionRecordError("progress_event_hash_mismatch")


def load_progress_events(root: Path, relative_log: Path) -> tuple[Mapping[str, Any], ...]:
    path = filesystem_path(root / relative_log)
    if not path.is_file():
        return ()
    rows: list[Mapping[str, Any]] = []
    previous_hash = ""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ExecutionRecordError("progress_event_log_unreadable", type(exc).__name__) from exc
    for line_number, line in enumerate(lines, start=1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ExecutionRecordError("progress_event_log_malformed", str(line_number)) from exc
        if not isinstance(row, Mapping):
            raise ExecutionRecordError("progress_event_not_object", str(line_number))
        validate_progress_event(row)
        if row["sequence"] != len(rows) + 1:
            raise ExecutionRecordError("progress_event_sequence_gap", str(line_number))
        if row["previous_event_hash"] != previous_hash:
            raise ExecutionRecordError("progress_event_chain_broken", str(line_number))
        previous_hash = str(row["event_hash"])
        rows.append(row)
    return tuple(rows)


def append_progress_event(
    root: Path,
    relative_log: Path,
    payload: Mapping[str, Any],
    *,
    path_token: str,
) -> Mapping[str, Any]:
    path = filesystem_path(root / relative_log)
    lock_path = path.with_suffix(f"{path.suffix}.lock")
    with _portable_file_lock(lock_path):
        events = load_progress_events(root, relative_log)
        previous_hash = str(events[-1]["event_hash"]) if events else ""
        event = dict(payload)
        event.update(
            {
                "schema_version": PROGRESS_EVENT_SCHEMA,
                "artifact_type": "skillguard_execution_progress_event",
                "sequence": len(events) + 1,
                "previous_event_hash": previous_hash,
                "event_log_ref": {
                    "path_token": path_token,
                    "relative_path": relative_log.as_posix(),
                },
            }
        )
        event["event_id"] = (
            f"progress-{event['sequence']:06d}-{canonical_hash(event)[:12].lower()}"
        )
        event["event_hash"] = _hash_without(event, "event_hash")
        validate_progress_event(event)
        _durable_mkdir(path.parent)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(path.parent)
        return event


def _timeout_unsigned_for_id(receipt: Mapping[str, Any]) -> dict[str, Any]:
    unsigned = dict(receipt)
    unsigned.pop("receipt_id", None)
    unsigned.pop("receipt_hash", None)
    return unsigned


def validate_timeout_receipt(receipt: Mapping[str, Any], expected_schema: str) -> None:
    required = {
        "schema_version",
        "artifact_type",
        "receipt_kind",
        "policy_version",
        "receipt_id",
        "receipt_hash",
        "status",
        "owner_ref",
        "step_id",
        "check_id",
        "command_token",
        "command_fingerprint",
        "started_at",
        "deadline_at",
        "finished_at",
        "elapsed_ms",
        "timeout_ms",
        "stdout_content_hash",
        "stderr_content_hash",
        "stdout_total_bytes",
        "stderr_total_bytes",
        "partial_output_content_hash",
        "reason",
        "resume_action",
        "retry_action",
        "terminal_kind",
        "termination_scope",
        "termination_attempted",
        "termination_succeeded",
        "claim_boundary",
    }
    if expected_schema not in TIMEOUT_RECEIPT_PREFIXES:
        raise ExecutionRecordError("timeout_receipt_schema_unknown", expected_schema)
    if receipt.get("schema_version") != expected_schema:
        raise ExecutionRecordError("timeout_receipt_schema_unsupported")
    expected_artifact_types = {
        CHECK_TIMEOUT_SCHEMA: "skillguard_check_timeout_receipt",
        TEST_MESH_TIMEOUT_SCHEMA: "skillguard_test_mesh_timeout_receipt",
    }
    if receipt.get("artifact_type") != expected_artifact_types[expected_schema]:
        raise ExecutionRecordError("timeout_receipt_artifact_type_invalid")
    if receipt.get("receipt_kind") != "execution_timeout":
        raise ExecutionRecordError("timeout_receipt_kind_invalid")
    if receipt.get("policy_version") != TIMEOUT_POLICY_VERSION:
        raise ExecutionRecordError("timeout_receipt_policy_invalid")
    if expected_schema == CHECK_TIMEOUT_SCHEMA:
        required.update(
            {
                "launch_plan_fingerprint",
                "resolved_program_identity",
                "resolved_interpreter_identity",
                "cleanup_confirmed",
                "cleanup_confirmation_method",
                "descendant_count_before",
                "descendant_count_after",
                "remaining_descendant_pids",
            }
        )
    missing = sorted(required - set(receipt))
    if missing:
        raise ExecutionRecordError("timeout_receipt_fields_missing", ",".join(missing))
    if receipt.get("status") != "timed_out" or receipt.get("terminal_kind") != "timeout":
        raise ExecutionRecordError("timeout_receipt_terminal_invalid")
    owner = receipt.get("owner_ref")
    if not isinstance(owner, Mapping) or not owner.get("owner_type") or not owner.get("owner_hash"):
        raise ExecutionRecordError("timeout_receipt_owner_invalid")
    hash_pattern = re.compile(r"^[0-9A-F]{64}$")
    for field in (
        "receipt_hash",
        "command_fingerprint",
    ):
        if not hash_pattern.fullmatch(str(receipt.get(field, ""))):
            raise ExecutionRecordError("timeout_receipt_hash_field_invalid", field)
    content_hash_pattern = re.compile(r"^sha256:[0-9a-f]{64}$")
    for field in (
        "stdout_content_hash",
        "stderr_content_hash",
        "partial_output_content_hash",
    ):
        if not content_hash_pattern.fullmatch(str(receipt.get(field, ""))):
            raise ExecutionRecordError("timeout_receipt_content_hash_invalid", field)
    if not hash_pattern.fullmatch(str(owner.get("owner_hash", ""))):
        raise ExecutionRecordError("timeout_receipt_owner_hash_invalid")
    token = str(receipt.get("command_token", ""))
    if not token or "/" in token or "\\" in token or re.match(r"^[A-Za-z]:", token):
        raise ExecutionRecordError("timeout_receipt_command_token_invalid")
    owner_requirements = {
        CHECK_TIMEOUT_SCHEMA: (
            "manifest_bound_check",
            (
                "run_id",
                "contract_hash",
                "check_manifest_hash",
                "check_declarations_hash",
                "declared_check_hash",
                "execution_environment_fingerprint",
            ),
        ),
        TEST_MESH_TIMEOUT_SCHEMA: (
            "test_mesh_suite",
            (
                "manifest_hash",
                "profile_declaration_hash",
                "suite_declaration_hash",
                "source_fingerprint",
                "environment_fingerprint",
            ),
        ),
    }
    expected_owner_type, owner_fields = owner_requirements[expected_schema]
    if owner.get("owner_type") != expected_owner_type:
        raise ExecutionRecordError("timeout_receipt_owner_type_invalid")
    for field in owner_fields:
        value = str(owner.get(field, ""))
        if field == "run_id":
            if not value:
                raise ExecutionRecordError("timeout_receipt_owner_field_invalid", field)
        elif not hash_pattern.fullmatch(value):
            raise ExecutionRecordError("timeout_receipt_owner_field_invalid", field)
    if expected_schema == CHECK_TIMEOUT_SCHEMA:
        owner_payload = {
            "run_id": owner["run_id"],
            "contract_hash": owner["contract_hash"],
            "check_manifest_hash": owner["check_manifest_hash"],
            "check_declarations_hash": owner["check_declarations_hash"],
            "declared_check_hash": owner["declared_check_hash"],
            "execution_environment_fingerprint": owner[
                "execution_environment_fingerprint"
            ],
            "step_id": receipt["step_id"],
            "check_id": receipt["check_id"],
        }
    else:
        owner_payload = {
            "manifest_hash": owner["manifest_hash"],
            "profile_declaration_hash": owner["profile_declaration_hash"],
            "suite_declaration_hash": owner["suite_declaration_hash"],
            "source_fingerprint": owner["source_fingerprint"],
            "environment_fingerprint": owner["environment_fingerprint"],
        }
    if owner.get("owner_hash") != canonical_hash(owner_payload):
        raise ExecutionRecordError("timeout_receipt_owner_binding_mismatch")
    if receipt.get("termination_scope") != "process_tree" or receipt.get(
        "termination_attempted"
    ) is not True:
        raise ExecutionRecordError("timeout_receipt_termination_invalid")
    expected_reason = (
        "suite_timeout"
        if expected_schema == TEST_MESH_TIMEOUT_SCHEMA
        else "declared_timeout_elapsed"
    )
    if receipt.get("reason") != expected_reason:
        raise ExecutionRecordError("timeout_receipt_reason_invalid")
    prefix = TIMEOUT_RECEIPT_PREFIXES[expected_schema]
    expected_id = f"{prefix}{canonical_hash(_timeout_unsigned_for_id(receipt))[:24].lower()}"
    if receipt.get("receipt_id") != expected_id:
        raise ExecutionRecordError("timeout_receipt_id_mismatch")
    if receipt.get("receipt_hash") != _hash_without(receipt, "receipt_hash"):
        raise ExecutionRecordError("timeout_receipt_hash_mismatch")


def write_timeout_receipt(
    root: Path,
    payload: Mapping[str, Any],
    *,
    expected_schema: str,
    relative_directory: Path = Path("timeouts"),
    path_token: str = "execution_record_root",
) -> Mapping[str, Any]:
    receipt = dict(payload)
    receipt.setdefault("schema_version", expected_schema)
    receipt.setdefault("receipt_kind", "execution_timeout")
    receipt.setdefault("policy_version", TIMEOUT_POLICY_VERSION)
    prefix = TIMEOUT_RECEIPT_PREFIXES[expected_schema]
    receipt["receipt_id"] = (
        f"{prefix}{canonical_hash(_timeout_unsigned_for_id(receipt))[:24].lower()}"
    )
    receipt["receipt_hash"] = _hash_without(receipt, "receipt_hash")
    validate_timeout_receipt(receipt, expected_schema)
    if relative_directory.is_absolute() or ".." in relative_directory.parts:
        raise ExecutionRecordError(
            "timeout_receipt_directory_unsafe", relative_directory.as_posix()
        )
    relative = relative_directory / f"{receipt['receipt_id']}.json"
    durable_write_immutable_json(root / relative, receipt)
    return {
        **receipt,
        "receipt_ref": relative.as_posix(),
        "receipt_locator": {
            "path_token": path_token,
            "relative_path": relative.as_posix(),
        },
        "receipt_write_status": "durable_immutable",
    }


def load_timeout_receipt(
    root: Path,
    receipt_ref: str,
    *,
    expected_schema: str,
    expected_owner_hash: str | None = None,
) -> Mapping[str, Any]:
    relative = Path(receipt_ref)
    if relative.is_absolute() or ".." in relative.parts:
        raise ExecutionRecordError("timeout_receipt_ref_unsafe", receipt_ref)
    path = filesystem_path(root / relative)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExecutionRecordError("timeout_receipt_unreadable", type(exc).__name__) from exc
    if not isinstance(payload, Mapping):
        raise ExecutionRecordError("timeout_receipt_not_object")
    validate_timeout_receipt(payload, expected_schema)
    if expected_owner_hash is not None and payload["owner_ref"].get(
        "owner_hash"
    ) != expected_owner_hash:
        raise ExecutionRecordError("timeout_receipt_cross_owner_replay")
    expected_name = f"{payload['receipt_id']}.json"
    if path.name != expected_name:
        raise ExecutionRecordError("timeout_receipt_filename_mismatch", path.name)
    return payload


def command_token(command: str) -> str:
    path = Path(command)
    name = path.name or command
    if command == sys.executable or name.lower().startswith("python"):
        return "python_runtime"
    if path.is_absolute():
        return f"executable:{name}"
    return command


def command_fingerprint(command: str, args: Sequence[str]) -> str:
    return canonical_hash({"command": command, "args": list(args)})


def redact_runtime_text(text: str, bindings: Mapping[str, Path]) -> str:
    """Replace known local roots and the user home in persisted diagnostics."""

    replacements: list[tuple[str, str]] = []
    for token, path in bindings.items():
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        for form in {str(resolved), resolved.as_posix()}:
            if form:
                replacements.append((form, f"{{{{{token}}}}}"))
    home = Path.home()
    for form in {str(home), home.as_posix()}:
        if form:
            replacements.append((form, "{{user_home}}"))
    redacted = text
    for source, target in sorted(replacements, key=lambda row: len(row[0]), reverse=True):
        redacted = redacted.replace(source, target)
        redacted = redacted.replace(source.replace("\\", "/"), target)
    return redacted


def isolated_process_kwargs() -> dict[str, Any]:
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
    return {"start_new_session": True}


@dataclass
class ProcessTreeContainment:
    """OS-level containment kept alive until the launcher releases the tree."""

    root_pid: int
    attached: bool
    method: str
    error_kind: str = ""
    windows_job_handle: int | None = None
    released: bool = False


def attach_process_tree_containment(
    process: subprocess.Popen[Any],
) -> ProcessTreeContainment:
    """Attach a new process to a kill-on-release tree boundary."""

    if os.name != "nt":
        return ProcessTreeContainment(
            root_pid=process.pid,
            attached=True,
            method="posix_process_group",
        )
    try:
        import ctypes
        from ctypes import wintypes

        class LARGE_INTEGER(ctypes.Structure):
            _fields_ = [("quad_part", ctypes.c_longlong)]

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("read_operation_count", ctypes.c_ulonglong),
                ("write_operation_count", ctypes.c_ulonglong),
                ("other_operation_count", ctypes.c_ulonglong),
                ("read_transfer_count", ctypes.c_ulonglong),
                ("write_transfer_count", ctypes.c_ulonglong),
                ("other_transfer_count", ctypes.c_ulonglong),
            ]

        class BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("per_process_user_time_limit", LARGE_INTEGER),
                ("per_job_user_time_limit", LARGE_INTEGER),
                ("limit_flags", wintypes.DWORD),
                ("minimum_working_set_size", ctypes.c_size_t),
                ("maximum_working_set_size", ctypes.c_size_t),
                ("active_process_limit", wintypes.DWORD),
                ("affinity", ctypes.c_size_t),
                ("priority_class", wintypes.DWORD),
                ("scheduling_class", wintypes.DWORD),
            ]

        class EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("basic_limit_information", BASIC_LIMIT_INFORMATION),
                ("io_info", IO_COUNTERS),
                ("process_memory_limit", ctypes.c_size_t),
                ("job_memory_limit", ctypes.c_size_t),
                ("peak_process_memory_used", ctypes.c_size_t),
                ("peak_job_memory_used", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_job = kernel32.CreateJobObjectW
        create_job.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        create_job.restype = wintypes.HANDLE
        set_information = kernel32.SetInformationJobObject
        set_information.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        set_information.restype = wintypes.BOOL
        assign_process = kernel32.AssignProcessToJobObject
        assign_process.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        assign_process.restype = wintypes.BOOL
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL

        handle = create_job(None, None)
        if not handle:
            raise OSError(ctypes.get_last_error(), "CreateJobObjectW")
        information = EXTENDED_LIMIT_INFORMATION()
        information.basic_limit_information.limit_flags = 0x00002000
        if not set_information(
            handle,
            9,
            ctypes.byref(information),
            ctypes.sizeof(information),
        ):
            error = ctypes.get_last_error()
            close_handle(handle)
            raise OSError(error, "SetInformationJobObject")
        process_handle = wintypes.HANDLE(int(process._handle))  # type: ignore[attr-defined]
        if not assign_process(handle, process_handle):
            error = ctypes.get_last_error()
            close_handle(handle)
            raise OSError(error, "AssignProcessToJobObject")
        return ProcessTreeContainment(
            root_pid=process.pid,
            attached=True,
            method="windows_kill_on_close_job",
            windows_job_handle=int(handle),
        )
    except (AttributeError, OSError, TypeError, ValueError) as exc:
        return ProcessTreeContainment(
            root_pid=process.pid,
            attached=False,
            method="windows_job_attach_failed",
            error_kind=type(exc).__name__,
        )


def release_process_tree_containment(
    process: subprocess.Popen[Any],
    containment: ProcessTreeContainment,
    *,
    timed_out: bool,
) -> Mapping[str, Any]:
    """Release the whole tree and fail closed when cleanup cannot be proven."""

    facts: dict[str, Any] = {
        "termination_scope": "process_tree",
        "termination_attempted": True,
        "termination_succeeded": False,
        "termination_method": containment.method,
        "termination_error_kind": containment.error_kind,
        "cleanup_confirmed": False,
        "containment_attached": containment.attached,
    }
    if containment.released:
        facts["termination_error_kind"] = "containment_already_released"
        return facts
    containment.released = True
    if not containment.attached:
        fallback = terminate_process_tree(process)
        facts.update(fallback)
        facts["cleanup_confirmed"] = bool(
            fallback.get("termination_succeeded")
            and process.poll() is not None
            and not (
                os.name == "nt"
                and fallback.get("termination_method") == "already_exited"
            )
        )
        return facts
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            class LARGE_INTEGER(ctypes.Structure):
                _fields_ = [("quad_part", ctypes.c_longlong)]

            class BASIC_ACCOUNTING_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("total_user_time", LARGE_INTEGER),
                    ("total_kernel_time", LARGE_INTEGER),
                    ("this_period_total_user_time", LARGE_INTEGER),
                    ("this_period_total_kernel_time", LARGE_INTEGER),
                    ("total_page_fault_count", wintypes.DWORD),
                    ("total_processes", wintypes.DWORD),
                    ("active_processes", wintypes.DWORD),
                    ("total_terminated_processes", wintypes.DWORD),
                ]

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            terminate_job = kernel32.TerminateJobObject
            terminate_job.argtypes = [wintypes.HANDLE, wintypes.UINT]
            terminate_job.restype = wintypes.BOOL
            query_job = kernel32.QueryInformationJobObject
            query_job.argtypes = [
                wintypes.HANDLE,
                ctypes.c_int,
                ctypes.c_void_p,
                wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD),
            ]
            query_job.restype = wintypes.BOOL
            close_handle = kernel32.CloseHandle
            close_handle.argtypes = [wintypes.HANDLE]
            close_handle.restype = wintypes.BOOL
            handle = containment.windows_job_handle
            if handle is None:
                raise OSError(0, "missing Windows job handle")
            job_handle = wintypes.HANDLE(handle)
            before_information = BASIC_ACCOUNTING_INFORMATION()
            before_returned = wintypes.DWORD()
            if not query_job(
                job_handle,
                1,
                ctypes.byref(before_information),
                ctypes.sizeof(before_information),
                ctypes.byref(before_returned),
            ):
                raise OSError(
                    ctypes.get_last_error(), "QueryInformationJobObject"
                )
            active_processes_before = int(
                before_information.active_processes
            )
            facts["cleanup_confirmation_method"] = (
                "windows_job_active_process_query"
            )
            facts["descendant_count_before"] = max(
                0, active_processes_before - 1
            )
            # TerminateJobObject is used even when the direct child already
            # exited: a successful parent must not leave grandchildren alive.
            if not terminate_job(job_handle, 0xE0000001):
                raise OSError(ctypes.get_last_error(), "TerminateJobObject")
            deadline = time.monotonic() + 10.0
            active_processes: int | None = None
            while time.monotonic() < deadline:
                information = BASIC_ACCOUNTING_INFORMATION()
                returned = wintypes.DWORD()
                if not query_job(
                    job_handle,
                    1,
                    ctypes.byref(information),
                    ctypes.sizeof(information),
                    ctypes.byref(returned),
                ):
                    raise OSError(
                        ctypes.get_last_error(), "QueryInformationJobObject"
                    )
                active_processes = int(information.active_processes)
                if active_processes == 0:
                    break
                time.sleep(0.05)
            if process.poll() is None:
                process.wait(timeout=2)
            facts["termination_succeeded"] = process.poll() is not None
            facts["cleanup_confirmed"] = bool(
                facts["termination_succeeded"] and active_processes == 0
            )
            facts["descendant_count_after"] = max(
                0, int(active_processes or 0)
            )
            facts["remaining_descendant_pids"] = []
            facts["termination_method"] = "windows_job_terminate_and_query"
            if active_processes != 0:
                facts["termination_error_kind"] = "job_processes_still_active"
            if not close_handle(job_handle):
                facts["cleanup_confirmed"] = False
                facts["termination_error_kind"] = "job_handle_close_failed"
        except (OSError, subprocess.SubprocessError) as exc:
            facts["termination_error_kind"] = type(exc).__name__
            handle = containment.windows_job_handle
            if handle is not None:
                try:
                    ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(
                        wintypes.HANDLE(handle)
                    )
                except (AttributeError, OSError, TypeError, ValueError):
                    pass
        return facts
    try:
        try:
            os.killpg(containment.root_pid, signal.SIGTERM)
        except ProcessLookupError:
            facts["termination_succeeded"] = True
            facts["cleanup_confirmed"] = True
            facts["termination_method"] = "posix_process_group_already_empty"
            return facts
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            try:
                os.killpg(containment.root_pid, 0)
            except ProcessLookupError:
                facts["termination_succeeded"] = True
                facts["cleanup_confirmed"] = True
                return facts
            time.sleep(0.05)
        os.killpg(containment.root_pid, signal.SIGKILL)
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            try:
                os.killpg(containment.root_pid, 0)
            except ProcessLookupError:
                facts["termination_succeeded"] = True
                facts["cleanup_confirmed"] = True
                return facts
            time.sleep(0.05)
        facts["termination_error_kind"] = "process_group_still_alive"
    except (OSError, subprocess.SubprocessError) as exc:
        facts["termination_error_kind"] = type(exc).__name__
    return facts


def terminate_process_tree(process: subprocess.Popen[Any]) -> Mapping[str, Any]:
    before_rows, before_method = _process_parent_rows()
    descendants_before = (
        _descendants(process.pid, before_rows) if before_rows is not None else set()
    )
    facts: dict[str, Any] = {
        "termination_scope": "process_tree",
        "termination_attempted": True,
        "termination_succeeded": False,
        "termination_method": "",
        "termination_error_kind": "",
        "cleanup_confirmed": False,
        "cleanup_confirmation_method": before_method,
        "descendant_count_before": len(descendants_before),
        "descendant_count_after": -1,
        "remaining_descendant_pids": [],
    }
    if process.poll() is not None:
        facts.update(
            {
                "termination_succeeded": True,
                "termination_method": "already_exited",
            }
        )
        after_rows, after_method = _process_parent_rows()
        if before_rows is not None and after_rows is not None:
            remaining = sorted(pid for pid in descendants_before if pid in after_rows)
            facts.update(
                {
                    "cleanup_confirmed": not remaining,
                    "cleanup_confirmation_method": f"{before_method}+{after_method}",
                    "descendant_count_after": len(remaining),
                    "remaining_descendant_pids": remaining,
                }
            )
        return facts
    try:
        if os.name == "nt":
            completed = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=10,
            )
            facts["termination_method"] = "windows_taskkill_tree"
            if completed.returncode != 0 and process.poll() is None:
                process.kill()
                facts["termination_method"] = "windows_parent_kill_fallback"
        else:
            facts["termination_method"] = "posix_process_group"
            os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
        facts["termination_succeeded"] = process.poll() is not None
    except (OSError, subprocess.SubprocessError) as exc:
        facts["termination_error_kind"] = type(exc).__name__
        try:
            process.kill()
            process.wait(timeout=5)
            facts["termination_succeeded"] = process.poll() is not None
            facts["termination_method"] = facts["termination_method"] or "parent_kill_fallback"
        except (OSError, subprocess.SubprocessError) as fallback_exc:
            facts["termination_error_kind"] = (
                f"{type(exc).__name__}:{type(fallback_exc).__name__}"
            )
    after_rows, after_method = _process_parent_rows()
    if before_rows is not None and after_rows is not None:
        newly_attached = _descendants(process.pid, after_rows)
        remaining = sorted(
            pid for pid in descendants_before | newly_attached if pid in after_rows
        )
        facts.update(
            {
                "cleanup_confirmed": process.poll() is not None and not remaining,
                "cleanup_confirmation_method": f"{before_method}+{after_method}",
                "descendant_count_after": len(remaining),
                "remaining_descendant_pids": remaining,
            }
        )
    else:
        facts["cleanup_confirmation_method"] = f"{before_method}+{after_method}"
    facts["termination_succeeded"] = bool(
        facts["termination_succeeded"] and facts["cleanup_confirmed"]
    )
    return facts
