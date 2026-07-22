"""Bounded author-side evidence storage and lifecycle operations.

This module deliberately depends only on the Python standard library.  The
check runner can therefore use the compressed-stream helpers without importing
the contract compiler or creating a compiler/runner cycle.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import stat
import time
import uuid
import zlib
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Iterable, Iterator, Mapping, MutableMapping, Sequence


EVIDENCE_LIFECYCLE_POLICY_ID = "skillguard.evidence_lifecycle.current"
EVIDENCE_AUDIT_SCHEMA = "skillguard.evidence_audit.current"
EVIDENCE_GC_PLAN_SCHEMA = "skillguard.evidence_gc_plan.current"
EVIDENCE_GC_APPLY_RECEIPT_SCHEMA = (
    "skillguard.evidence_gc_apply_receipt.current"
)
EVIDENCE_GC_PURGE_RECEIPT_SCHEMA = (
    "skillguard.evidence_gc_purge_receipt.current"
)
CURRENT_HEAD_AUTHORITY_SCHEMA = (
    "skillguard.evidence_current_head_authority.current"
)
CURRENT_AGGREGATION_AUTHORITY_SCHEMA = (
    "skillguard.evidence_current_aggregation_authority.current"
)
ACTIVE_WRITER_SCHEMA = "skillguard.evidence_active_writer.current"

OWNER_EVIDENCE_PATH_TOKEN = "owner_evidence_root"
DEFAULT_CHUNK_SIZE = 1024 * 1024
DEFAULT_MAX_LOGICAL_BYTES = 1024 * 1024 * 1024
MAX_REFERENCE_JSON_BYTES = 16 * 1024 * 1024
WIRE_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_MUTABLE_REPLACE_MAX_ATTEMPTS = 12
_MUTABLE_REPLACE_INITIAL_DELAY_SECONDS = 0.01
_MUTABLE_REPLACE_MAX_DELAY_SECONDS = 0.25

_STREAM_REFERENCE_FIELDS = frozenset(
    {
        "path_token",
        "relative_path",
        "logical_content_hash",
        "logical_byte_count",
        "logical_media_type",
        "storage_content_hash",
        "storage_byte_count",
        "storage_encoding",
        "storage_media_type",
    }
)
_OPERATION_PREFIXES = (
    "lifecycle/quarantine/",
    "lifecycle/journals/",
    "lifecycle/receipts/",
)
_CLASSIFICATION_PRIORITY = {
    "corrupt_or_ambiguous": 100,
    "current": 90,
    "active": 80,
    "release_pinned": 70,
    "installation_pinned": 60,
    "failed_diagnostic": 50,
    "historical_referenced": 40,
    "quarantined_corrupt": 30,
    "temporary": 20,
    "orphan": 10,
}
_ROOT_CLASSIFICATIONS = {
    "current_head_authority": "current",
    "closure": "current",
    "aggregation": "current",
    "active_attempt": "active",
    "active_writer": "active",
    "release_pin": "release_pinned",
    "installation_pin": "installation_pinned",
    "failed_diagnostic": "failed_diagnostic",
    "historical_pin": "historical_referenced",
    "quarantined_corrupt": "quarantined_corrupt",
}


class EvidenceStoreError(ValueError):
    """Fail-closed evidence-store error with a stable machine-facing code."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


@dataclass(frozen=True)
class VerifiedStreamObject:
    """Verified logical and physical identity of one compressed stream."""

    object_path: Path
    logical_content_hash: str
    logical_byte_count: int
    storage_content_hash: str
    storage_byte_count: int


def _canonical_json_bytes(payload: object) -> bytes:
    """Use the current SkillGuard wire shape without importing its compiler."""

    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _wire_bytes_hash(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _wire_hash(payload: object) -> str:
    return _wire_bytes_hash(_canonical_json_bytes(payload))


def _stream_file_hash(path: Path, *, chunk_size: int = DEFAULT_CHUNK_SIZE) -> str:
    digest = hashlib.sha256()
    with _filesystem_path(path).open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _require_wire_hash(value: object, code: str) -> str:
    text = str(value)
    if WIRE_HASH_RE.fullmatch(text) is None:
        raise EvidenceStoreError(code, text)
    return text


def _is_link_or_reparse(path: Path) -> bool:
    try:
        details = os.lstat(_filesystem_path(path))
    except FileNotFoundError:
        return False
    if stat.S_ISLNK(details.st_mode):
        return True
    attributes = getattr(details, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse_flag)


def _canonical_root(root: Path, *, must_exist: bool = True) -> Path:
    declared = Path(root)
    if _is_link_or_reparse(declared):
        raise EvidenceStoreError("evidence_root_is_link_or_reparse")
    resolved = declared.resolve()
    filesystem_root = _filesystem_path(resolved)
    if must_exist and (
        not filesystem_root.exists() or not filesystem_root.is_dir()
    ):
        raise EvidenceStoreError("evidence_root_missing_or_not_directory")
    return resolved


def _portable_relative_path(value: object) -> PurePosixPath:
    text = str(value)
    if not text or "\\" in text or "\x00" in text:
        raise EvidenceStoreError("evidence_relative_path_invalid", text)
    relative = PurePosixPath(text)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise EvidenceStoreError("evidence_relative_path_invalid", text)
    if relative.parts and ":" in relative.parts[0]:
        raise EvidenceStoreError("evidence_relative_path_invalid", text)
    return relative


def _contained_path(
    root: Path,
    relative_path: object,
    *,
    reject_links: bool = True,
) -> Path:
    relative = _portable_relative_path(relative_path)
    candidate = root.joinpath(*relative.parts)
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise EvidenceStoreError(
            "evidence_path_escape", relative.as_posix()
        ) from exc
    if reject_links:
        cursor = root
        for part in relative.parts:
            cursor /= part
            if _path_exists(cursor) and _is_link_or_reparse(cursor):
                raise EvidenceStoreError(
                    "evidence_path_link_or_reparse", relative.as_posix()
                )
    return resolved


def _durable_mkdir(path: Path, root: Path) -> None:
    try:
        path.resolve(strict=False).relative_to(root)
    except ValueError as exc:
        raise EvidenceStoreError("evidence_directory_escape") from exc
    missing: list[Path] = []
    cursor = path
    while not _path_exists(cursor):
        missing.append(cursor)
        cursor = cursor.parent
    if _is_link_or_reparse(cursor):
        raise EvidenceStoreError("evidence_directory_link_or_reparse")
    for item in reversed(missing):
        _filesystem_path(item).mkdir()
        if _is_link_or_reparse(item):
            raise EvidenceStoreError("evidence_directory_link_or_reparse")


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _windows_extended_path(path: Path) -> str:
    """Return one absolute Win32 extended-length path for native file APIs."""

    resolved = os.path.abspath(os.fspath(path))
    if resolved.startswith("\\\\?\\"):
        return resolved
    if resolved.startswith("\\\\"):
        return "\\\\?\\UNC\\" + resolved[2:]
    return "\\\\?\\" + resolved


def _filesystem_path(path: Path) -> Path:
    if os.name == "nt":
        return Path(_windows_extended_path(path))
    return path


def _path_exists(path: Path) -> bool:
    return _filesystem_path(path).exists()


def _path_is_file(path: Path) -> bool:
    return _filesystem_path(path).is_file()


def _path_stat(path: Path) -> os.stat_result:
    return _filesystem_path(path).stat()


def _path_read_bytes(path: Path) -> bytes:
    return _filesystem_path(path).read_bytes()


def _path_unlink(path: Path, *, missing_ok: bool = False) -> None:
    _filesystem_path(path).unlink(missing_ok=missing_ok)


def _windows_move_no_replace(source: Path, destination: Path) -> None:
    import ctypes

    move_file_ex = ctypes.WinDLL("kernel32", use_last_error=True).MoveFileExW
    move_file_ex.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
    move_file_ex.restype = ctypes.c_int
    if not move_file_ex(
        _windows_extended_path(source),
        _windows_extended_path(destination),
        0x00000008,
    ):
        raise ctypes.WinError(ctypes.get_last_error())


def _atomic_move_no_replace(source: Path, destination: Path) -> None:
    """Move within one filesystem without replacing an existing object."""

    if _path_exists(destination):
        raise EvidenceStoreError(
            "immutable_destination_exists", destination.name
        )
    if os.name == "nt":
        try:
            _windows_move_no_replace(source, destination)
        except OSError as exc:
            raise EvidenceStoreError(
                "atomic_move_failed", type(exc).__name__
            ) from exc
        return
    try:
        os.link(_filesystem_path(source), _filesystem_path(destination))
        _path_unlink(source)
        _fsync_directory(destination.parent)
    except OSError as exc:
        try:
            _path_unlink(destination)
        except FileNotFoundError:
            pass
        raise EvidenceStoreError("atomic_move_failed", type(exc).__name__) from exc


def _atomic_publish_file(source: Path, destination: Path) -> None:
    if _path_exists(destination):
        raise EvidenceStoreError("immutable_destination_exists", destination.name)
    _atomic_move_no_replace(source, destination)


def _replace_mutable_file(source: Path, destination: Path) -> None:
    """Replace one mutable control file with bounded transient-error recovery.

    Windows scanners and readers can briefly hold a journal between the durable
    temporary write and ``os.replace``.  A lifecycle operation must keep the
    same operation identity and retry only that atomic publish step; starting a
    new cleanup owner would lose the prepared/deleted recovery boundary.
    """

    delay = _MUTABLE_REPLACE_INITIAL_DELAY_SECONDS
    for attempt in range(_MUTABLE_REPLACE_MAX_ATTEMPTS):
        try:
            os.replace(_filesystem_path(source), _filesystem_path(destination))
            return
        except PermissionError as exc:
            if attempt + 1 == _MUTABLE_REPLACE_MAX_ATTEMPTS:
                raise EvidenceStoreError(
                    "mutable_record_replace_failed",
                    f"{destination.name}:{type(exc).__name__}",
                ) from exc
            time.sleep(delay)
            delay = min(delay * 2, _MUTABLE_REPLACE_MAX_DELAY_SECONDS)


def _write_json_atomic(
    path: Path,
    payload: Mapping[str, Any],
    *,
    root: Path,
    immutable: bool,
) -> None:
    _durable_mkdir(path.parent, root)
    body = _canonical_json_bytes(dict(payload))
    if immutable and _path_exists(path):
        try:
            existing = _path_read_bytes(path)
        except OSError as exc:
            raise EvidenceStoreError(
                "immutable_record_unreadable", path.name
            ) from exc
        if existing == body:
            return
        raise EvidenceStoreError("immutable_record_collision", path.name)
    temporary = path.with_name(f".sg-{uuid.uuid4().hex}.tmp")
    descriptor = os.open(
        _filesystem_path(temporary),
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)
    try:
        if immutable:
            try:
                _atomic_publish_file(temporary, path)
            except EvidenceStoreError:
                if _path_exists(path) and _path_read_bytes(path) == body:
                    _path_unlink(temporary, missing_ok=True)
                    return
                raise
        else:
            _replace_mutable_file(temporary, path)
            _fsync_directory(path.parent)
    finally:
        _path_unlink(temporary, missing_ok=True)


@contextmanager
def evidence_lifecycle_barrier(
    owner_evidence_root: Path,
    *,
    timeout_seconds: float = 10.0,
) -> Iterator[None]:
    """Hold the short store-wide barrier used only for lifecycle transitions."""

    root = _canonical_root(owner_evidence_root)
    if timeout_seconds <= 0:
        raise EvidenceStoreError("lifecycle_barrier_timeout_invalid")
    lock_path = _contained_path(root, "lifecycle/barrier.lock")
    _durable_mkdir(lock_path.parent, root)
    handle = _filesystem_path(lock_path).open("a+b")
    locked = False
    try:
        if _path_stat(lock_path).st_size == 0:
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
                locked = True
                break
            except (BlockingIOError, OSError):
                if time.monotonic() >= deadline:
                    raise EvidenceStoreError("lifecycle_barrier_timeout")
                time.sleep(0.05)
        yield
    finally:
        if locked:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _load_json_mapping(path: Path, code: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(_filesystem_path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceStoreError(code, path.name) from exc
    if not isinstance(payload, Mapping):
        raise EvidenceStoreError(code, path.name)
    return payload


def _json_file_reference(root: Path, path: Path) -> dict[str, Any]:
    body = _path_read_bytes(path)
    return {
        "path_token": OWNER_EVIDENCE_PATH_TOKEN,
        "relative_path": path.relative_to(root).as_posix(),
        "content_hash": _wire_bytes_hash(body),
        "media_type": "application/json",
        "byte_count": len(body),
    }


def _current_head_slot(
    maintenance_unit_id: str,
    member_skill_id: str,
    execution_owner_id: str,
) -> str:
    return _wire_hash(
        {
            "maintenance_unit_id": maintenance_unit_id,
            "member_skill_id": member_skill_id,
            "execution_owner_id": execution_owner_id,
        }
    ).removeprefix("sha256:")


def publish_current_head_authority(
    owner_evidence_root: Path,
    head_path: Path,
) -> dict[str, Any]:
    """Replace one owner's current pointer with an exact current head reference."""

    root = _canonical_root(owner_evidence_root)
    declared_head = Path(head_path)
    if not declared_head.is_absolute():
        declared_head = _contained_path(root, declared_head.as_posix())
    else:
        declared_head = declared_head.resolve()
        try:
            declared_head.relative_to(root)
        except ValueError as exc:
            raise EvidenceStoreError("current_head_outside_evidence_root") from exc
    head_relative = declared_head.relative_to(root).as_posix()
    if not head_relative.startswith("check-executions/heads/"):
        raise EvidenceStoreError("current_head_path_invalid", head_relative)
    if not _path_is_file(declared_head) or _is_link_or_reparse(declared_head):
        raise EvidenceStoreError("current_head_missing", head_relative)
    head = dict(_load_json_mapping(declared_head, "current_head_invalid"))
    if head.get("schema_version") != "skillguard.check_execution_head.current":
        raise EvidenceStoreError("current_head_schema_non_current")
    hash_findings = _validate_known_document(head, head_relative)
    if hash_findings:
        raise EvidenceStoreError("current_head_hash_mismatch")
    required = (
        "maintenance_unit_id",
        "member_skill_id",
        "execution_owner_id",
        "execution_key",
        "observed_at",
    )
    if any(not str(head.get(field, "")) for field in required):
        raise EvidenceStoreError("current_head_identity_incomplete")
    execution_key = _require_wire_hash(
        head["execution_key"], "current_head_execution_key_invalid"
    )
    if declared_head.name != f"{execution_key.removeprefix('sha256:')}.json":
        raise EvidenceStoreError("current_head_filename_mismatch")
    slot = _current_head_slot(
        str(head["maintenance_unit_id"]),
        str(head["member_skill_id"]),
        str(head["execution_owner_id"]),
    )
    authority: dict[str, Any] = {
        "schema_version": CURRENT_HEAD_AUTHORITY_SCHEMA,
        "policy_id": EVIDENCE_LIFECYCLE_POLICY_ID,
        "maintenance_unit_id": str(head["maintenance_unit_id"]),
        "member_skill_id": str(head["member_skill_id"]),
        "execution_owner_id": str(head["execution_owner_id"]),
        "execution_key": execution_key,
        "head_ref": _json_file_reference(root, declared_head),
        "observed_at": str(head["observed_at"]),
        "claim_boundary": (
            "This mutable authority selects exactly one current execution head "
            "for one maintenance-unit producer. Historical heads are not roots."
        ),
    }
    authority["authority_hash"] = _wire_hash(authority)
    authority_path = _contained_path(
        root, f"lifecycle/current-heads/{slot}.json"
    )
    _write_json_atomic(authority_path, authority, root=root, immutable=False)
    return authority


def _current_aggregation_slot(
    maintenance_unit_id: str,
    member_skill_id: str,
    profile_id: str,
) -> str:
    return _wire_hash(
        {
            "maintenance_unit_id": maintenance_unit_id,
            "member_skill_id": member_skill_id,
            "profile_id": profile_id,
        }
    ).removeprefix("sha256:")


def publish_current_aggregation_authority(
    owner_evidence_root: Path,
    aggregation_path: Path,
) -> dict[str, Any]:
    """Select one current immutable aggregation for one unit/member/profile."""

    root = _canonical_root(owner_evidence_root)
    declared = Path(aggregation_path)
    if not declared.is_absolute():
        declared = _contained_path(root, declared.as_posix())
    else:
        declared = declared.resolve()
        try:
            declared.relative_to(root)
        except ValueError as exc:
            raise EvidenceStoreError(
                "current_aggregation_outside_evidence_root"
            ) from exc
    relative = declared.relative_to(root).as_posix()
    if not relative.startswith("test-mesh/aggregations/"):
        raise EvidenceStoreError("current_aggregation_path_invalid", relative)
    if not _path_is_file(declared) or _is_link_or_reparse(declared):
        raise EvidenceStoreError("current_aggregation_missing", relative)
    payload = dict(_load_json_mapping(declared, "current_aggregation_invalid"))
    if payload.get("schema_version") != "skillguard.test_mesh_aggregation.current":
        raise EvidenceStoreError("current_aggregation_schema_non_current")
    required = (
        "maintenance_unit_id",
        "member_skill_id",
        "profile_id",
        "aggregation_id",
    )
    if any(not str(payload.get(field, "")) for field in required):
        raise EvidenceStoreError("current_aggregation_identity_incomplete")
    aggregation_id = _require_wire_hash(
        payload["aggregation_id"], "current_aggregation_id_invalid"
    )
    slot = _current_aggregation_slot(
        str(payload["maintenance_unit_id"]),
        str(payload["member_skill_id"]),
        str(payload["profile_id"]),
    )
    authority: dict[str, Any] = {
        "schema_version": CURRENT_AGGREGATION_AUTHORITY_SCHEMA,
        "policy_id": EVIDENCE_LIFECYCLE_POLICY_ID,
        "maintenance_unit_id": str(payload["maintenance_unit_id"]),
        "member_skill_id": str(payload["member_skill_id"]),
        "profile_id": str(payload["profile_id"]),
        "aggregation_id": aggregation_id,
        "aggregation_ref": _json_file_reference(root, declared),
        "observed_at": _utc_now(),
        "claim_boundary": (
            "This mutable authority selects exactly one current immutable TestMesh "
            "aggregation for one maintenance-unit member/profile. Older aggregations "
            "are historical objects, not implicit roots."
        ),
    }
    authority["authority_hash"] = _wire_hash(authority)
    authority_path = _contained_path(
        root, f"lifecycle/current-aggregations/{slot}.json"
    )
    _write_json_atomic(authority_path, authority, root=root, immutable=False)
    return authority


def _active_writer_id(
    maintenance_unit_id: str,
    member_skill_id: str,
    execution_owner_id: str,
    attempt_id: str,
) -> str:
    return "writer-" + _wire_hash(
        {
            "maintenance_unit_id": maintenance_unit_id,
            "member_skill_id": member_skill_id,
            "execution_owner_id": execution_owner_id,
            "attempt_id": attempt_id,
        }
    ).removeprefix("sha256:")[:24]


def begin_evidence_writer(
    owner_evidence_root: Path,
    *,
    maintenance_unit_id: str,
    member_skill_id: str,
    execution_owner_id: str,
    attempt_id: str,
) -> dict[str, Any]:
    """Create one active-writer marker while holding the short barrier."""

    values = (
        maintenance_unit_id,
        member_skill_id,
        execution_owner_id,
        attempt_id,
    )
    if any(not str(value) for value in values):
        raise EvidenceStoreError("active_writer_identity_incomplete")
    root = _canonical_root(owner_evidence_root)
    writer_id = _active_writer_id(*map(str, values))
    marker: dict[str, Any] = {
        "schema_version": ACTIVE_WRITER_SCHEMA,
        "policy_id": EVIDENCE_LIFECYCLE_POLICY_ID,
        "writer_id": writer_id,
        "maintenance_unit_id": str(maintenance_unit_id),
        "member_skill_id": str(member_skill_id),
        "execution_owner_id": str(execution_owner_id),
        "attempt_id": str(attempt_id),
        "created_at": _utc_now(),
        "claim_boundary": (
            "This marker proves only that one evidence writer may publish under "
            "the canonical store. It is liveness state, not success evidence."
        ),
    }
    marker["marker_hash"] = _wire_hash(marker)
    marker_path = _contained_path(
        root, f"lifecycle/active-writers/{writer_id}.json"
    )
    with evidence_lifecycle_barrier(root):
        _write_json_atomic(marker_path, marker, root=root, immutable=True)
    return marker


def _validate_active_writer_marker(marker: Mapping[str, Any]) -> None:
    if marker.get("schema_version") != ACTIVE_WRITER_SCHEMA:
        raise EvidenceStoreError("active_writer_schema_non_current")
    if marker.get("policy_id") != EVIDENCE_LIFECYCLE_POLICY_ID:
        raise EvidenceStoreError("active_writer_policy_mismatch")
    unsigned = dict(marker)
    stored = unsigned.pop("marker_hash", None)
    if stored != _wire_hash(unsigned):
        raise EvidenceStoreError("active_writer_marker_hash_mismatch")
    expected = _active_writer_id(
        str(marker.get("maintenance_unit_id", "")),
        str(marker.get("member_skill_id", "")),
        str(marker.get("execution_owner_id", "")),
        str(marker.get("attempt_id", "")),
    )
    if marker.get("writer_id") != expected:
        raise EvidenceStoreError("active_writer_identity_mismatch")


def end_evidence_writer(
    owner_evidence_root: Path,
    marker: Mapping[str, Any],
) -> None:
    """Remove exactly one active marker under the lifecycle barrier."""

    _validate_active_writer_marker(marker)
    root = _canonical_root(owner_evidence_root)
    marker_path = _contained_path(
        root, f"lifecycle/active-writers/{marker['writer_id']}.json"
    )
    with evidence_lifecycle_barrier(root):
        if not _path_is_file(marker_path):
            raise EvidenceStoreError("active_writer_marker_missing")
        current = _load_json_mapping(marker_path, "active_writer_marker_invalid")
        if dict(current) != dict(marker):
            raise EvidenceStoreError("active_writer_marker_identity_mismatch")
        _path_unlink(marker_path)
        _fsync_directory(marker_path.parent)


@contextmanager
def active_evidence_writer(
    owner_evidence_root: Path,
    *,
    maintenance_unit_id: str,
    member_skill_id: str,
    execution_owner_id: str,
    attempt_id: str,
) -> Iterator[dict[str, Any]]:
    """Mark a writer active without holding the global barrier while it runs."""

    marker = begin_evidence_writer(
        owner_evidence_root,
        maintenance_unit_id=maintenance_unit_id,
        member_skill_id=member_skill_id,
        execution_owner_id=execution_owner_id,
        attempt_id=attempt_id,
    )
    try:
        yield marker
    finally:
        end_evidence_writer(owner_evidence_root, marker)


def persist_compressed_stream(
    owner_evidence_root: Path,
    source: BinaryIO,
    *,
    logical_media_type: str = "application/octet-stream",
    max_logical_bytes: int | None = None,
) -> dict[str, Any]:
    """Persist one complete stream as a deterministic immutable gzip object."""

    root = _canonical_root(owner_evidence_root)
    if not logical_media_type:
        raise EvidenceStoreError("logical_media_type_missing")
    if max_logical_bytes is not None and max_logical_bytes < 0:
        raise EvidenceStoreError("logical_byte_limit_invalid")
    blobs = _contained_path(root, "check-executions/blobs")
    _durable_mkdir(blobs, root)
    temporary = blobs / f".sg-{uuid.uuid4().hex}.tmp"
    logical_digest = hashlib.sha256()
    logical_count = 0
    descriptor = os.open(
        _filesystem_path(temporary),
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    try:
        try:
            source.seek(0)
        except (AttributeError, OSError):
            pass
        with os.fdopen(descriptor, "wb", closefd=False) as raw:
            with gzip.GzipFile(
                filename="",
                mode="wb",
                compresslevel=9,
                fileobj=raw,
                mtime=0,
            ) as compressed:
                while True:
                    chunk = source.read(DEFAULT_CHUNK_SIZE)
                    if not chunk:
                        break
                    if not isinstance(chunk, (bytes, bytearray)):
                        raise EvidenceStoreError("stream_source_not_binary")
                    logical_count += len(chunk)
                    if (
                        max_logical_bytes is not None
                        and logical_count > max_logical_bytes
                    ):
                        raise EvidenceStoreError(
                            "logical_byte_limit_exceeded", str(max_logical_bytes)
                        )
                    logical_digest.update(chunk)
                    compressed.write(chunk)
            raw.flush()
            os.fsync(raw.fileno())
    except Exception:
        _path_unlink(temporary, missing_ok=True)
        raise
    finally:
        os.close(descriptor)

    storage_count = _path_stat(temporary).st_size
    storage_hash = _stream_file_hash(temporary)
    logical_hash = "sha256:" + logical_digest.hexdigest()
    destination = blobs / f"{storage_hash.removeprefix('sha256:')}.gz"
    if _path_exists(destination):
        if (
            _path_stat(destination).st_size != storage_count
            or _stream_file_hash(destination) != storage_hash
        ):
            _path_unlink(temporary, missing_ok=True)
            raise EvidenceStoreError(
                "immutable_stream_collision", destination.name
            )
        _path_unlink(temporary)
    else:
        try:
            _atomic_publish_file(temporary, destination)
        except EvidenceStoreError:
            if _path_exists(destination) and (
                _path_stat(destination).st_size == storage_count
                and _stream_file_hash(destination) == storage_hash
            ):
                _path_unlink(temporary, missing_ok=True)
            else:
                _path_unlink(temporary, missing_ok=True)
                raise
    return {
        "path_token": OWNER_EVIDENCE_PATH_TOKEN,
        "relative_path": destination.relative_to(root).as_posix(),
        "logical_content_hash": logical_hash,
        "logical_byte_count": logical_count,
        "logical_media_type": logical_media_type,
        "storage_content_hash": storage_hash,
        "storage_byte_count": storage_count,
        "storage_encoding": "gzip",
        "storage_media_type": "application/gzip",
    }


def verify_compressed_stream(
    owner_evidence_root: Path,
    reference: Mapping[str, Any],
    *,
    max_logical_bytes: int,
    output: BinaryIO | None = None,
) -> VerifiedStreamObject:
    """Verify both identities and optionally stream the logical bytes to output."""

    root = _canonical_root(owner_evidence_root)
    if set(reference) != _STREAM_REFERENCE_FIELDS:
        raise EvidenceStoreError("compressed_stream_reference_shape_invalid")
    if reference.get("path_token") != OWNER_EVIDENCE_PATH_TOKEN:
        raise EvidenceStoreError("compressed_stream_authority_invalid")
    if reference.get("storage_encoding") != "gzip":
        raise EvidenceStoreError("compressed_stream_encoding_invalid")
    if reference.get("storage_media_type") != "application/gzip":
        raise EvidenceStoreError("compressed_stream_media_type_invalid")
    if not str(reference.get("logical_media_type", "")):
        raise EvidenceStoreError("compressed_stream_logical_media_type_missing")
    storage_hash = _require_wire_hash(
        reference.get("storage_content_hash"), "storage_hash_invalid"
    )
    logical_hash = _require_wire_hash(
        reference.get("logical_content_hash"), "logical_hash_invalid"
    )
    try:
        storage_count = int(reference.get("storage_byte_count"))
        logical_count_expected = int(reference.get("logical_byte_count"))
    except (TypeError, ValueError) as exc:
        raise EvidenceStoreError("compressed_stream_byte_count_invalid") from exc
    if storage_count < 0 or logical_count_expected < 0 or max_logical_bytes < 0:
        raise EvidenceStoreError("compressed_stream_byte_count_invalid")
    if logical_count_expected > max_logical_bytes:
        raise EvidenceStoreError(
            "logical_byte_limit_exceeded", str(max_logical_bytes)
        )
    path = _contained_path(root, reference.get("relative_path"))
    expected_name = f"{storage_hash.removeprefix('sha256:')}.gz"
    if path.name != expected_name:
        raise EvidenceStoreError("compressed_stream_storage_path_invalid")
    if not _path_is_file(path) or _is_link_or_reparse(path):
        raise EvidenceStoreError("compressed_stream_object_missing")
    if _path_stat(path).st_size != storage_count:
        raise EvidenceStoreError("compressed_stream_storage_length_mismatch")
    if _stream_file_hash(path) != storage_hash:
        raise EvidenceStoreError("compressed_stream_storage_hash_mismatch")

    logical_digest = hashlib.sha256()
    logical_count = 0
    try:
        with _filesystem_path(path).open("rb") as raw, gzip.GzipFile(
            fileobj=raw, mode="rb"
        ) as decoded:
            while True:
                chunk = decoded.read(DEFAULT_CHUNK_SIZE)
                if not chunk:
                    break
                logical_count += len(chunk)
                if (
                    logical_count > logical_count_expected
                    or logical_count > max_logical_bytes
                ):
                    raise EvidenceStoreError(
                        "logical_byte_limit_exceeded", str(max_logical_bytes)
                    )
                logical_digest.update(chunk)
                if output is not None:
                    output.write(chunk)
    except EvidenceStoreError:
        raise
    except (OSError, EOFError, gzip.BadGzipFile, zlib.error) as exc:
        raise EvidenceStoreError(
            "compressed_stream_decompression_failed", type(exc).__name__
        ) from exc
    if logical_count != logical_count_expected:
        raise EvidenceStoreError("compressed_stream_logical_length_mismatch")
    observed_logical_hash = "sha256:" + logical_digest.hexdigest()
    if observed_logical_hash != logical_hash:
        raise EvidenceStoreError("compressed_stream_logical_hash_mismatch")
    return VerifiedStreamObject(
        object_path=path,
        logical_content_hash=logical_hash,
        logical_byte_count=logical_count,
        storage_content_hash=storage_hash,
        storage_byte_count=storage_count,
    )


def _root_identity(root: Path) -> dict[str, str]:
    identity = _wire_hash(
        {
            "path_token": OWNER_EVIDENCE_PATH_TOKEN,
            "canonical_path": os.path.normcase(str(root)),
        }
    )
    return {"path_token": OWNER_EVIDENCE_PATH_TOKEN, "identity_hash": identity}


def _operation_path(relative_path: str) -> bool:
    if relative_path == "lifecycle/barrier.lock":
        return True
    normalized = relative_path.rstrip("/") + "/"
    return any(normalized.startswith(prefix) for prefix in _OPERATION_PREFIXES)


def _temporary_path(relative_path: str) -> bool:
    name = PurePosixPath(relative_path).name
    return (
        relative_path.startswith("check-executions/staging/")
        or relative_path.startswith("check-executions/locks/")
        or name.endswith(".tmp")
        or name.startswith(".sg-")
    )


def _finding(
    code: str,
    *,
    relative_path: str = "",
    detail: str = "",
    severity: str = "blocker",
) -> dict[str, str]:
    return {
        "code": code,
        "severity": severity,
        "relative_path": relative_path,
        "detail": detail,
    }


def _inventory_files(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    rows: list[dict[str, Any]] = []
    findings: list[dict[str, str]] = []
    filesystem_root = _filesystem_path(root)
    for current_text, directory_names, file_names in os.walk(
        filesystem_root, topdown=True, followlinks=False
    ):
        filesystem_current = Path(current_text)
        current = root / filesystem_current.relative_to(filesystem_root)
        kept_directories: list[str] = []
        for name in sorted(directory_names):
            path = current / name
            relative = path.relative_to(root).as_posix()
            if _operation_path(relative):
                continue
            if _is_link_or_reparse(path):
                findings.append(
                    _finding("inventory_link_or_reparse", relative_path=relative)
                )
                continue
            kept_directories.append(name)
        directory_names[:] = kept_directories
        for name in sorted(file_names):
            path = current / name
            relative = path.relative_to(root).as_posix()
            if _operation_path(relative):
                continue
            if _is_link_or_reparse(path):
                findings.append(
                    _finding("inventory_link_or_reparse", relative_path=relative)
                )
                continue
            before = _path_stat(path)
            if not stat.S_ISREG(before.st_mode):
                findings.append(
                    _finding("inventory_non_regular_file", relative_path=relative)
                )
                continue
            content_hash = _stream_file_hash(path)
            after = _path_stat(path)
            if (
                before.st_size != after.st_size
                or before.st_mtime_ns != after.st_mtime_ns
            ):
                findings.append(
                    _finding(
                        "inventory_file_changed_during_audit",
                        relative_path=relative,
                    )
                )
            rows.append(
                {
                    "relative_path": relative,
                    "byte_count": after.st_size,
                    "content_hash": content_hash,
                }
            )
    rows.sort(key=lambda row: row["relative_path"])
    findings.sort(key=lambda row: (row["code"], row["relative_path"], row["detail"]))
    return rows, findings


def _root_kind(relative_path: str) -> str | None:
    rules = (
        ("lifecycle/current-heads/", "current_head_authority"),
        ("lifecycle/current-aggregations/", "aggregation"),
        ("closures/", "closure"),
        ("lifecycle/roots/closures/", "closure"),
        ("lifecycle/roots/aggregations/", "aggregation"),
        ("lifecycle/active-attempts/", "active_attempt"),
        ("lifecycle/active-writers/", "active_writer"),
        ("lifecycle/pins/release/", "release_pin"),
        ("lifecycle/pins/installation/", "installation_pin"),
        ("lifecycle/pins/historical/", "historical_pin"),
        ("lifecycle/retained-failures/", "failed_diagnostic"),
        ("check-executions/corrupt/", "quarantined_corrupt"),
    )
    for prefix, kind in rules:
        if relative_path.startswith(prefix) and relative_path.endswith(".json"):
            return kind
    return None


def _classification_for_root(root_kind: str) -> str:
    return _ROOT_CLASSIFICATIONS[root_kind]


def _prefer_classification(current: str, candidate: str) -> str:
    if _CLASSIFICATION_PRIORITY[candidate] > _CLASSIFICATION_PRIORITY[current]:
        return candidate
    return current


def _json_references(payload: object) -> list[Mapping[str, Any]]:
    references: list[Mapping[str, Any]] = []
    aggregation_schema = (
        isinstance(payload, Mapping)
        and payload.get("schema_version")
        == "skillguard.test_mesh_aggregation.current"
    )

    def is_declared_external_binding(
        location: tuple[object, ...], value: Mapping[str, Any]
    ) -> bool:
        if not aggregation_schema or value.get("path_token") != "codex_home":
            return False
        if location == (
            "installation_verification_identity",
            "installation_receipt_root_ref",
        ):
            return value.get("relative_path") == (
                "skills/skillguard/.sg-runtime/installation"
            )
        return bool(
            len(location) == 3
            and location[0] == "typed_domain_bindings"
            and isinstance(location[1], int)
            and location[2] in {"registry_ref", "projection_ref", "prompt_ref"}
            and value.get("relative_path")
            in {
                ".skillguard/global-router/global_registry.json",
                ".skillguard/global-router/global_prompt_projection.json",
                "AGENTS.md",
            }
        )

    def visit(value: object, location: tuple[object, ...] = ()) -> None:
        if isinstance(value, Mapping):
            if "path_token" in value and "relative_path" in value:
                if not is_declared_external_binding(location, value):
                    references.append(value)
            for key, child in value.items():
                visit(child, (*location, key))
        elif isinstance(value, Sequence) and not isinstance(
            value, (str, bytes, bytearray)
        ):
            for index, child in enumerate(value):
                visit(child, (*location, index))

    visit(payload)
    return references


def _read_reference_json(path: Path, relative_path: str) -> Mapping[str, Any]:
    if _path_stat(path).st_size > MAX_REFERENCE_JSON_BYTES:
        raise EvidenceStoreError("reference_json_too_large", relative_path)
    return _load_json_mapping(path, "reference_json_invalid")


def _validate_known_document(
    payload: Mapping[str, Any], relative_path: str
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    schema = payload.get("schema_version")
    hash_field = None
    if schema == "skillguard.check_execution_head.current":
        hash_field = "head_hash"
    elif schema == "skillguard.check_execution_receipt.current":
        hash_field = "receipt_hash"
    if hash_field is not None:
        unsigned = dict(payload)
        stored = unsigned.pop(hash_field, None)
        if stored != _wire_hash(unsigned):
            findings.append(
                _finding(
                    "referenced_document_hash_mismatch",
                    relative_path=relative_path,
                    detail=hash_field,
                )
            )
    return findings


def _validate_current_head_authority_document(
    root: Path,
    payload: Mapping[str, Any],
    relative_path: str,
    inventory: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    expected_fields = {
        "schema_version",
        "policy_id",
        "maintenance_unit_id",
        "member_skill_id",
        "execution_owner_id",
        "execution_key",
        "head_ref",
        "observed_at",
        "claim_boundary",
        "authority_hash",
    }
    if set(payload) != expected_fields:
        findings.append(
            _finding(
                "current_head_authority_shape_invalid",
                relative_path=relative_path,
            )
        )
        return findings
    if payload.get("schema_version") != CURRENT_HEAD_AUTHORITY_SCHEMA:
        findings.append(
            _finding(
                "current_head_authority_schema_non_current",
                relative_path=relative_path,
            )
        )
    if payload.get("policy_id") != EVIDENCE_LIFECYCLE_POLICY_ID:
        findings.append(
            _finding(
                "current_head_authority_policy_mismatch",
                relative_path=relative_path,
            )
        )
    unsigned = dict(payload)
    stored_hash = unsigned.pop("authority_hash", None)
    if stored_hash != _wire_hash(unsigned):
        findings.append(
            _finding(
                "current_head_authority_hash_mismatch",
                relative_path=relative_path,
            )
        )
    identity_values = (
        str(payload.get("maintenance_unit_id", "")),
        str(payload.get("member_skill_id", "")),
        str(payload.get("execution_owner_id", "")),
    )
    if any(not value for value in identity_values):
        findings.append(
            _finding(
                "current_head_authority_identity_incomplete",
                relative_path=relative_path,
            )
        )
        return findings
    expected_slot = _current_head_slot(*identity_values)
    if relative_path != f"lifecycle/current-heads/{expected_slot}.json":
        findings.append(
            _finding(
                "current_head_authority_slot_mismatch",
                relative_path=relative_path,
            )
        )
    head_ref = payload.get("head_ref")
    if not isinstance(head_ref, Mapping):
        findings.append(
            _finding(
                "current_head_authority_ref_missing",
                relative_path=relative_path,
            )
        )
        return findings
    try:
        head_relative = _portable_relative_path(
            head_ref.get("relative_path")
        ).as_posix()
    except EvidenceStoreError as exc:
        findings.append(
            _finding(exc.code, relative_path=relative_path, detail=exc.detail)
        )
        return findings
    if not head_relative.startswith("check-executions/heads/"):
        findings.append(
            _finding(
                "current_head_authority_target_invalid",
                relative_path=head_relative,
            )
        )
        return findings
    if head_relative not in inventory:
        return findings
    try:
        head = _read_reference_json(_contained_path(root, head_relative), head_relative)
    except EvidenceStoreError as exc:
        findings.append(
            _finding(exc.code, relative_path=head_relative, detail=exc.detail)
        )
        return findings
    if head.get("schema_version") != "skillguard.check_execution_head.current":
        findings.append(
            _finding(
                "current_head_schema_non_current", relative_path=head_relative
            )
        )
        return findings
    for field in (
        "maintenance_unit_id",
        "member_skill_id",
        "execution_owner_id",
        "execution_key",
    ):
        if head.get(field) != payload.get(field):
            findings.append(
                _finding(
                    "current_head_authority_binding_mismatch",
                    relative_path=head_relative,
                    detail=field,
                )
            )
    return findings


def _validate_current_aggregation_authority_document(
    root: Path,
    payload: Mapping[str, Any],
    relative_path: str,
    inventory: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    expected_fields = {
        "schema_version",
        "policy_id",
        "maintenance_unit_id",
        "member_skill_id",
        "profile_id",
        "aggregation_id",
        "aggregation_ref",
        "observed_at",
        "claim_boundary",
        "authority_hash",
    }
    if set(payload) != expected_fields:
        return [
            _finding(
                "current_aggregation_authority_shape_invalid",
                relative_path=relative_path,
            )
        ]
    if payload.get("schema_version") != CURRENT_AGGREGATION_AUTHORITY_SCHEMA:
        findings.append(
            _finding(
                "current_aggregation_authority_schema_non_current",
                relative_path=relative_path,
            )
        )
    if payload.get("policy_id") != EVIDENCE_LIFECYCLE_POLICY_ID:
        findings.append(
            _finding(
                "current_aggregation_authority_policy_mismatch",
                relative_path=relative_path,
            )
        )
    unsigned = dict(payload)
    stored_hash = unsigned.pop("authority_hash", None)
    if stored_hash != _wire_hash(unsigned):
        findings.append(
            _finding(
                "current_aggregation_authority_hash_mismatch",
                relative_path=relative_path,
            )
        )
    identity = (
        str(payload.get("maintenance_unit_id", "")),
        str(payload.get("member_skill_id", "")),
        str(payload.get("profile_id", "")),
    )
    if any(not value for value in identity):
        findings.append(
            _finding(
                "current_aggregation_authority_identity_incomplete",
                relative_path=relative_path,
            )
        )
        return findings
    expected_slot = _current_aggregation_slot(*identity)
    if relative_path != f"lifecycle/current-aggregations/{expected_slot}.json":
        findings.append(
            _finding(
                "current_aggregation_authority_slot_mismatch",
                relative_path=relative_path,
            )
        )
    reference = payload.get("aggregation_ref")
    if not isinstance(reference, Mapping):
        findings.append(
            _finding(
                "current_aggregation_authority_ref_missing",
                relative_path=relative_path,
            )
        )
        return findings
    try:
        target = _portable_relative_path(reference.get("relative_path")).as_posix()
    except EvidenceStoreError as exc:
        findings.append(
            _finding(exc.code, relative_path=relative_path, detail=exc.detail)
        )
        return findings
    if not target.startswith("test-mesh/aggregations/"):
        findings.append(
            _finding(
                "current_aggregation_authority_target_invalid",
                relative_path=target,
            )
        )
        return findings
    if target not in inventory:
        return findings
    try:
        aggregation = _read_reference_json(_contained_path(root, target), target)
    except EvidenceStoreError as exc:
        findings.append(_finding(exc.code, relative_path=target, detail=exc.detail))
        return findings
    if (
        aggregation.get("schema_version")
        != "skillguard.test_mesh_aggregation.current"
        or aggregation.get("aggregation_id") != payload.get("aggregation_id")
    ):
        findings.append(
            _finding(
                "current_aggregation_authority_binding_mismatch",
                relative_path=target,
            )
        )
    for field in ("maintenance_unit_id", "member_skill_id", "profile_id"):
        if aggregation.get(field) != payload.get(field):
            findings.append(
                _finding(
                    "current_aggregation_authority_binding_mismatch",
                    relative_path=target,
                    detail=field,
                )
            )
    return findings


def _verify_raw_reference(
    root: Path,
    reference: Mapping[str, Any],
    inventory: Mapping[str, Mapping[str, Any]],
    *,
    max_logical_bytes: int,
) -> tuple[str | None, str | None, list[dict[str, str]]]:
    findings: list[dict[str, str]] = []
    path_token = reference.get("path_token")
    relative_text = str(reference.get("relative_path", ""))
    if path_token != OWNER_EVIDENCE_PATH_TOKEN:
        return None, None, [
            _finding(
                "multiple_or_foreign_evidence_authority",
                relative_path=relative_text,
                detail=str(path_token),
            )
        ]
    try:
        relative = _portable_relative_path(relative_text).as_posix()
        path = _contained_path(root, relative)
    except EvidenceStoreError as exc:
        return None, None, [
            _finding(exc.code, relative_path=relative_text, detail=exc.detail)
        ]
    inventory_row = inventory.get(relative)
    if inventory_row is None or not _path_is_file(path):
        return relative, None, [
            _finding("referenced_object_missing", relative_path=relative)
        ]
    if "storage_encoding" in reference or "storage_content_hash" in reference:
        try:
            verify_compressed_stream(
                root,
                reference,
                max_logical_bytes=max_logical_bytes,
            )
        except EvidenceStoreError as exc:
            findings.append(
                _finding(exc.code, relative_path=relative, detail=exc.detail)
            )
        return relative, "application/gzip", findings
    if "content_hash" not in reference or "byte_count" not in reference:
        findings.append(
            _finding("reference_shape_unsupported", relative_path=relative)
        )
        return relative, None, findings
    try:
        expected_hash = _require_wire_hash(
            reference.get("content_hash"), "reference_content_hash_invalid"
        )
        expected_count = int(reference.get("byte_count"))
    except EvidenceStoreError as exc:
        findings.append(
            _finding(exc.code, relative_path=relative, detail=exc.detail)
        )
        return relative, str(reference.get("media_type", "")), findings
    except (TypeError, ValueError):
        findings.append(
            _finding("reference_byte_count_invalid", relative_path=relative)
        )
        return relative, str(reference.get("media_type", "")), findings
    if expected_count < 0 or inventory_row["byte_count"] != expected_count:
        findings.append(
            _finding("reference_byte_count_mismatch", relative_path=relative)
        )
    if inventory_row["content_hash"] != expected_hash:
        findings.append(
            _finding("reference_content_hash_mismatch", relative_path=relative)
        )
    media_type = str(reference.get("media_type", ""))
    if media_type == "application/octet-stream":
        findings.append(
            _finding(
                "legacy_uncompressed_stream_reference_non_current",
                relative_path=relative,
            )
        )
    return relative, media_type, findings


def _graph_cycles(edges: Mapping[str, set[str]]) -> list[tuple[str, ...]]:
    cycles: set[tuple[str, ...]] = set()
    visiting: list[str] = []
    positions: dict[str, int] = {}
    visited: set[str] = set()

    def walk(node: str) -> None:
        if node in positions:
            cycle = visiting[positions[node] :] + [node]
            cycles.add(tuple(cycle))
            return
        if node in visited:
            return
        positions[node] = len(visiting)
        visiting.append(node)
        for child in sorted(edges.get(node, set())):
            walk(child)
        visiting.pop()
        positions.pop(node, None)
        visited.add(node)

    for node in sorted(edges):
        walk(node)
    return sorted(cycles)


def _inventory_identity_rows(
    rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return sorted(
        [
            {
                "relative_path": str(row["relative_path"]),
                "byte_count": int(row["byte_count"]),
                "content_hash": str(row["content_hash"]),
            }
            for row in rows
        ],
        key=lambda row: row["relative_path"],
    )


def audit_evidence_store(
    owner_evidence_root: Path,
    *,
    max_logical_bytes: int = DEFAULT_MAX_LOGICAL_BYTES,
) -> dict[str, Any]:
    """Read and classify one canonical store without writing to it."""

    root = _canonical_root(owner_evidence_root)
    if max_logical_bytes < 0:
        raise EvidenceStoreError("logical_byte_limit_invalid")
    inventory_rows, findings = _inventory_files(root)
    inventory_map: dict[str, Mapping[str, Any]] = {
        str(row["relative_path"]): row for row in inventory_rows
    }
    classifications = {
        relative: "temporary" if _temporary_path(relative) else "orphan"
        for relative in inventory_map
    }
    root_kinds: dict[str, set[str]] = {relative: set() for relative in inventory_map}
    referenced_by: dict[str, set[str]] = {relative: set() for relative in inventory_map}
    roots: list[dict[str, str]] = []
    edges: dict[str, set[str]] = {}
    queue: list[tuple[str, str]] = []
    for relative in sorted(inventory_map):
        kind = _root_kind(relative)
        if kind is None:
            continue
        roots.append({"relative_path": relative, "root_kind": kind})
        queue.append((relative, kind))
        classifications[relative] = _prefer_classification(
            classifications[relative], _classification_for_root(kind)
        )
        root_kinds[relative].add(kind)
        if kind == "active_writer":
            findings.append(
                _finding("active_writer_present", relative_path=relative)
            )
        if kind == "quarantined_corrupt":
            findings.append(
                _finding("corrupt_quarantine_present", relative_path=relative)
            )

    historical_head_paths = [
        relative
        for relative in inventory_map
        if relative.startswith("check-executions/heads/")
        and relative.endswith(".json")
    ]
    current_authority_paths = [
        row["relative_path"]
        for row in roots
        if row["root_kind"] == "current_head_authority"
    ]
    if historical_head_paths and not current_authority_paths:
        findings.append(
            _finding(
                "current_head_authority_missing",
                detail=(
                    "historical execution heads exist but no direct-current "
                    "lifecycle authority selects the active producer set"
                ),
            )
        )

    processed: set[tuple[str, str]] = set()
    payload_cache: dict[str, Mapping[str, Any]] = {}
    current_authority_owners: dict[tuple[str, str, str], str] = {}
    while queue:
        relative, originating_kind = queue.pop(0)
        marker = (relative, originating_kind)
        if marker in processed:
            continue
        processed.add(marker)
        row = inventory_map.get(relative)
        if row is None:
            continue
        path = _contained_path(root, relative)
        if path.suffix.lower() != ".json":
            continue
        try:
            payload = payload_cache.get(relative)
            if payload is None:
                payload = _read_reference_json(path, relative)
                payload_cache[relative] = payload
        except EvidenceStoreError as exc:
            findings.append(
                _finding(exc.code, relative_path=relative, detail=exc.detail)
            )
            continue
        findings.extend(_validate_known_document(payload, relative))
        direct_root_kind = _root_kind(relative)
        if direct_root_kind == "current_head_authority":
            findings.extend(
                _validate_current_head_authority_document(
                    root, payload, relative, inventory_map
                )
            )
            owner_key = (
                str(payload.get("maintenance_unit_id", "")),
                str(payload.get("member_skill_id", "")),
                str(payload.get("execution_owner_id", "")),
            )
            prior = current_authority_owners.get(owner_key)
            if prior is not None and prior != relative:
                findings.append(
                    _finding(
                        "duplicate_current_head_authority",
                        relative_path=relative,
                        detail=prior,
                    )
                )
            else:
                current_authority_owners[owner_key] = relative
        elif (
            direct_root_kind == "aggregation"
            and relative.startswith("lifecycle/current-aggregations/")
        ):
            findings.extend(
                _validate_current_aggregation_authority_document(
                    root, payload, relative, inventory_map
                )
            )
        elif direct_root_kind == "active_writer":
            try:
                _validate_active_writer_marker(payload)
            except EvidenceStoreError as exc:
                findings.append(
                    _finding(exc.code, relative_path=relative, detail=exc.detail)
                )
            expected_marker_path = (
                f"lifecycle/active-writers/{payload.get('writer_id', '')}.json"
            )
            if relative != expected_marker_path:
                findings.append(
                    _finding(
                        "active_writer_marker_path_mismatch",
                        relative_path=relative,
                    )
                )
        declared_root = payload.get("owner_evidence_root")
        if isinstance(declared_root, Mapping):
            declared_identity = declared_root.get("identity_hash")
            if (
                declared_identity is not None
                and declared_identity != _root_identity(root)["identity_hash"]
            ):
                findings.append(
                    _finding(
                        "evidence_root_identity_mismatch",
                        relative_path=relative,
                    )
                )
        for reference in _json_references(payload):
            child, media_type, reference_findings = _verify_raw_reference(
                root,
                reference,
                inventory_map,
                max_logical_bytes=max_logical_bytes,
            )
            findings.extend(reference_findings)
            if child is None:
                continue
            edges.setdefault(relative, set()).add(child)
            if child not in inventory_map:
                continue
            referenced_by[child].add(relative)
            child_classification = _classification_for_root(originating_kind)
            classifications[child] = _prefer_classification(
                classifications[child], child_classification
            )
            root_kinds[child].add(originating_kind)
            if media_type == "application/json" or child.endswith(".json"):
                queue.append((child, originating_kind))

    for cycle in _graph_cycles(edges):
        findings.append(
            _finding(
                "unsupported_reference_cycle",
                relative_path=cycle[0],
                detail=" -> ".join(cycle),
            )
        )
    corrupt_paths = {
        row["relative_path"]
        for row in findings
        if row["severity"] == "blocker" and row["relative_path"] in inventory_map
    }
    for relative in corrupt_paths:
        classifications[relative] = "corrupt_or_ambiguous"

    findings = sorted(
        {
            (row["code"], row["severity"], row["relative_path"], row["detail"]): row
            for row in findings
        }.values(),
        key=lambda row: (
            row["code"],
            row["relative_path"],
            row["detail"],
            row["severity"],
        ),
    )
    inventory = [
        {
            **dict(row),
            "classification": classifications[str(row["relative_path"])],
            "root_kinds": sorted(root_kinds[str(row["relative_path"])]),
            "referenced_by": sorted(referenced_by[str(row["relative_path"])]),
        }
        for row in inventory_rows
    ]
    identity_rows = _inventory_identity_rows(inventory)
    snapshot_hash = _wire_hash(
        {
            "policy_id": EVIDENCE_LIFECYCLE_POLICY_ID,
            "inventory": identity_rows,
        }
    )
    counts: MutableMapping[str, int] = {
        name: 0 for name in _CLASSIFICATION_PRIORITY
    }
    for row in inventory:
        counts[str(row["classification"])] += 1
    payload: dict[str, Any] = {
        "schema_version": EVIDENCE_AUDIT_SCHEMA,
        "policy_id": EVIDENCE_LIFECYCLE_POLICY_ID,
        "status": "blocked" if findings else "passed",
        "owner_evidence_root": _root_identity(root),
        "inventory_snapshot_hash": snapshot_hash,
        "inventory": inventory,
        "roots": roots,
        "findings": findings,
        "counts": dict(counts),
        "collectible_byte_count": sum(
            int(row["byte_count"])
            for row in inventory
            if row["classification"] == "orphan"
        ),
        "claim_boundary": (
            "This read-only audit classifies the exact current owner-evidence "
            "snapshot. It does not execute checks, mutate evidence, authorize "
            "collection, or prove target-domain correctness."
        ),
    }
    payload["audit_hash"] = _wire_hash(payload)
    return payload


def plan_evidence_gc(
    owner_evidence_root: Path,
    *,
    max_logical_bytes: int = DEFAULT_MAX_LOGICAL_BYTES,
) -> dict[str, Any]:
    """Produce a complete, read-only GC plan for one exact audit snapshot."""

    audit = audit_evidence_store(
        owner_evidence_root, max_logical_bytes=max_logical_bytes
    )
    inventory = [
        {
            "relative_path": row["relative_path"],
            "byte_count": row["byte_count"],
            "content_hash": row["content_hash"],
            "classification": row["classification"],
        }
        for row in audit["inventory"]
    ]
    candidates = []
    if audit["status"] == "passed":
        candidates = [
            {
                "relative_path": row["relative_path"],
                "byte_count": row["byte_count"],
                "content_hash": row["content_hash"],
                "reason": "unreachable_from_declared_lifecycle_roots",
            }
            for row in inventory
            if row["classification"] == "orphan"
        ]
    payload: dict[str, Any] = {
        "schema_version": EVIDENCE_GC_PLAN_SCHEMA,
        "policy_id": EVIDENCE_LIFECYCLE_POLICY_ID,
        "status": "ready" if audit["status"] == "passed" else "blocked",
        "owner_evidence_root": dict(audit["owner_evidence_root"]),
        "inventory_snapshot_hash": audit["inventory_snapshot_hash"],
        "audit_hash": audit["audit_hash"],
        "inventory": inventory,
        "candidates": candidates,
        "candidate_byte_count": sum(row["byte_count"] for row in candidates),
        "findings": list(audit["findings"]),
        "claim_boundary": (
            "This read-only plan names exact unreachable candidates for one "
            "snapshot. It performs no move or deletion and grants no authority "
            "after any inventory, root, pin, or policy change."
        ),
    }
    payload["plan_hash"] = _wire_hash(payload)
    return payload


def _validate_plan(plan: Mapping[str, Any]) -> None:
    if plan.get("schema_version") != EVIDENCE_GC_PLAN_SCHEMA:
        raise EvidenceStoreError("gc_plan_schema_non_current")
    if plan.get("policy_id") != EVIDENCE_LIFECYCLE_POLICY_ID:
        raise EvidenceStoreError("gc_plan_policy_mismatch")
    if plan.get("status") != "ready":
        raise EvidenceStoreError("gc_plan_not_ready")
    unsigned = dict(plan)
    stored_hash = unsigned.pop("plan_hash", None)
    if stored_hash != _wire_hash(unsigned):
        raise EvidenceStoreError("gc_plan_hash_mismatch")
    inventory = plan.get("inventory")
    candidates = plan.get("candidates")
    if not isinstance(inventory, Sequence) or isinstance(inventory, (str, bytes)):
        raise EvidenceStoreError("gc_plan_inventory_invalid")
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        raise EvidenceStoreError("gc_plan_candidates_invalid")
    inventory_paths: dict[str, Mapping[str, Any]] = {}
    for row in inventory:
        if not isinstance(row, Mapping):
            raise EvidenceStoreError("gc_plan_inventory_invalid")
        relative = _portable_relative_path(row.get("relative_path")).as_posix()
        if relative in inventory_paths:
            raise EvidenceStoreError("gc_plan_duplicate_inventory_path", relative)
        _require_wire_hash(row.get("content_hash"), "gc_plan_content_hash_invalid")
        if int(row.get("byte_count", -1)) < 0:
            raise EvidenceStoreError("gc_plan_byte_count_invalid", relative)
        inventory_paths[relative] = row
    candidate_paths: set[str] = set()
    for row in candidates:
        if not isinstance(row, Mapping):
            raise EvidenceStoreError("gc_plan_candidates_invalid")
        relative = _portable_relative_path(row.get("relative_path")).as_posix()
        if relative in candidate_paths:
            raise EvidenceStoreError("gc_plan_duplicate_candidate_path", relative)
        source = inventory_paths.get(relative)
        if source is None or source.get("classification") != "orphan":
            raise EvidenceStoreError("gc_plan_candidate_not_orphan", relative)
        if (
            source.get("content_hash") != row.get("content_hash")
            or int(source.get("byte_count", -1)) != int(row.get("byte_count", -2))
            or row.get("reason") != "unreachable_from_declared_lifecycle_roots"
        ):
            raise EvidenceStoreError("gc_plan_candidate_identity_mismatch", relative)
        candidate_paths.add(relative)


def _quarantine_root(root: Path, quarantine_root: Path) -> tuple[Path, str]:
    declared = Path(quarantine_root)
    resolved = declared.resolve(strict=False)
    try:
        relative = resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise EvidenceStoreError("quarantine_root_outside_evidence_root") from exc
    if not (
        relative == "lifecycle/quarantine"
        or relative.startswith("lifecycle/quarantine/")
    ):
        raise EvidenceStoreError("quarantine_root_not_lifecycle_quarantine")
    _contained_path(root, relative)
    return resolved, relative


def _plan_inventory_identity(plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    return _inventory_identity_rows(plan.get("inventory", []))


def _journal_hash(payload: Mapping[str, Any]) -> str:
    unsigned = dict(payload)
    unsigned.pop("journal_hash", None)
    return _wire_hash(unsigned)


def _load_valid_journal(path: Path, *, operation_id: str, plan_hash: str) -> dict[str, Any]:
    payload = dict(_load_json_mapping(path, "gc_journal_invalid"))
    if (
        payload.get("operation_id") != operation_id
        or payload.get("plan_hash") != plan_hash
        or payload.get("journal_hash") != _journal_hash(payload)
    ):
        raise EvidenceStoreError("gc_journal_identity_mismatch")
    return payload


def _write_journal(path: Path, payload: dict[str, Any], root: Path) -> None:
    payload["journal_hash"] = _journal_hash(payload)
    _write_json_atomic(path, payload, root=root, immutable=False)


def _validate_file_identity(path: Path, row: Mapping[str, Any], code: str) -> None:
    if not _path_is_file(path) or _is_link_or_reparse(path):
        raise EvidenceStoreError(code, str(row.get("relative_path", path.name)))
    if _path_stat(path).st_size != int(row["byte_count"]):
        raise EvidenceStoreError(code, str(row.get("relative_path", path.name)))
    if _stream_file_hash(path) != row["content_hash"]:
        raise EvidenceStoreError(code, str(row.get("relative_path", path.name)))


def _apply_receipt_path(root: Path, apply_id: str) -> Path:
    return _contained_path(
        root, f"lifecycle/receipts/apply/{apply_id}.json"
    )


def _purge_receipt_path(root: Path, purge_id: str) -> Path:
    return _contained_path(
        root, f"lifecycle/receipts/purge/{purge_id}.json"
    )


def _validate_hashed_receipt(
    payload: Mapping[str, Any], *, schema: str, hash_field: str
) -> None:
    if payload.get("schema_version") != schema:
        raise EvidenceStoreError("lifecycle_receipt_schema_non_current")
    unsigned = dict(payload)
    stored = unsigned.pop(hash_field, None)
    if stored != _wire_hash(unsigned):
        raise EvidenceStoreError("lifecycle_receipt_hash_mismatch")


def _apply_evidence_gc_plan_locked(
    owner_evidence_root: Path,
    plan: Mapping[str, Any],
    *,
    quarantine_root: Path,
) -> dict[str, Any]:
    """Quarantine exact current plan candidates; never permanently delete."""

    _validate_plan(plan)
    root = _canonical_root(owner_evidence_root)
    if plan.get("owner_evidence_root") != _root_identity(root):
        raise EvidenceStoreError("gc_plan_evidence_root_mismatch")
    quarantine, quarantine_relative = _quarantine_root(root, quarantine_root)
    apply_id = "evidence-apply-" + _wire_hash(
        {
            "plan_hash": plan["plan_hash"],
            "root_identity": _root_identity(root),
            "quarantine_root": quarantine_relative,
        }
    ).removeprefix("sha256:")[:24]
    receipt_path = _apply_receipt_path(root, apply_id)
    if _path_is_file(receipt_path):
        existing = dict(
            _load_json_mapping(receipt_path, "gc_apply_receipt_invalid")
        )
        _validate_hashed_receipt(
            existing,
            schema=EVIDENCE_GC_APPLY_RECEIPT_SCHEMA,
            hash_field="receipt_hash",
        )
        if (
            existing.get("plan_hash") != plan["plan_hash"]
            or existing.get("quarantine_root", {}).get("relative_path")
            != quarantine_relative
        ):
            raise EvidenceStoreError("gc_apply_receipt_identity_mismatch")
        return existing

    journal_path = _contained_path(
        root, f"lifecycle/journals/{apply_id}.json"
    )
    operation_root = quarantine / apply_id
    candidate_rows = [dict(row) for row in plan["candidates"]]
    candidate_by_path = {row["relative_path"]: row for row in candidate_rows}
    if _path_is_file(journal_path):
        journal = _load_valid_journal(
            journal_path,
            operation_id=apply_id,
            plan_hash=str(plan["plan_hash"]),
        )
    else:
        audit = audit_evidence_store(root)
        if audit["status"] != "passed":
            raise EvidenceStoreError("gc_apply_current_audit_blocked")
        if (
            audit["inventory_snapshot_hash"] != plan["inventory_snapshot_hash"]
            or _inventory_identity_rows(audit["inventory"])
            != _plan_inventory_identity(plan)
        ):
            raise EvidenceStoreError("gc_plan_stale")
        journal = {
            "schema_version": "skillguard.evidence_gc_apply_journal.current",
            "operation_id": apply_id,
            "plan_hash": plan["plan_hash"],
            "status": "in_progress",
            "items": [
                {
                    "source_relative_path": row["relative_path"],
                    "quarantine_relative_path": (
                        f"{quarantine_relative}/{apply_id}/{row['relative_path']}"
                    ),
                    "content_hash": row["content_hash"],
                    "byte_count": row["byte_count"],
                    "status": "pending",
                }
                for row in candidate_rows
            ],
        }
        _write_journal(journal_path, journal, root)

    planned_inventory = {
        row["relative_path"]: row for row in plan.get("inventory", [])
    }
    current_audit = audit_evidence_store(root)
    if current_audit["status"] != "passed":
        raise EvidenceStoreError("gc_apply_current_audit_blocked")
    current_inventory = {
        row["relative_path"]: row for row in current_audit["inventory"]
    }
    if set(current_inventory) - set(planned_inventory):
        raise EvidenceStoreError("gc_plan_stale")
    for relative, planned in planned_inventory.items():
        current = current_inventory.get(relative)
        if relative not in candidate_by_path:
            if current is None or (
                current["content_hash"] != planned["content_hash"]
                or current["byte_count"] != planned["byte_count"]
            ):
                raise EvidenceStoreError("gc_plan_stale", relative)
        elif current is not None and (
            current["content_hash"] != planned["content_hash"]
            or current["byte_count"] != planned["byte_count"]
        ):
            raise EvidenceStoreError("gc_plan_stale", relative)

    _durable_mkdir(operation_root, root)
    dispositions: list[dict[str, Any]] = []
    journal_items = journal.get("items")
    if not isinstance(journal_items, list):
        raise EvidenceStoreError("gc_journal_items_invalid")
    for item in journal_items:
        if not isinstance(item, dict):
            raise EvidenceStoreError("gc_journal_items_invalid")
        relative = str(item["source_relative_path"])
        planned = candidate_by_path.get(relative)
        if planned is None:
            raise EvidenceStoreError("gc_journal_candidate_mismatch", relative)
        source = _contained_path(root, relative)
        destination = _contained_path(root, item["quarantine_relative_path"])
        _durable_mkdir(destination.parent, root)
        source_exists = _path_exists(source)
        destination_exists = _path_exists(destination)
        if source_exists and destination_exists:
            raise EvidenceStoreError("gc_apply_source_and_destination_both_exist", relative)
        disposition = "quarantined"
        if source_exists:
            _validate_file_identity(source, planned, "gc_apply_source_identity_mismatch")
            _atomic_move_no_replace(source, destination)
        elif destination_exists:
            _validate_file_identity(
                destination, planned, "gc_apply_quarantine_identity_mismatch"
            )
            disposition = "recovered"
        else:
            raise EvidenceStoreError("gc_apply_candidate_missing", relative)
        item["status"] = "quarantined"
        item["disposition"] = disposition
        _write_journal(journal_path, journal, root)
        dispositions.append(
            {
                "source_relative_path": relative,
                "quarantine_relative_path": item["quarantine_relative_path"],
                "content_hash": planned["content_hash"],
                "byte_count": planned["byte_count"],
                "disposition": disposition,
            }
        )

    journal["status"] = "complete"
    journal["receipt_relative_path"] = receipt_path.relative_to(root).as_posix()
    _write_journal(journal_path, journal, root)
    applied_at = _utc_now()
    receipt: dict[str, Any] = {
        "schema_version": EVIDENCE_GC_APPLY_RECEIPT_SCHEMA,
        "policy_id": EVIDENCE_LIFECYCLE_POLICY_ID,
        "status": "applied",
        "apply_id": apply_id,
        "owner_evidence_root": _root_identity(root),
        "plan_hash": plan["plan_hash"],
        "inventory_snapshot_hash": plan["inventory_snapshot_hash"],
        "quarantine_root": {
            "path_token": OWNER_EVIDENCE_PATH_TOKEN,
            "relative_path": quarantine_relative,
        },
        "applied_at": applied_at,
        "items": dispositions,
        "journal_ref": _json_file_reference(root, journal_path),
        "claim_boundary": (
            "This receipt proves only that the exact planned unreachable "
            "objects were moved into quarantine. No object was permanently deleted."
        ),
    }
    receipt["receipt_hash"] = _wire_hash(receipt)
    _write_json_atomic(receipt_path, receipt, root=root, immutable=True)
    return receipt


def apply_evidence_gc_plan(
    owner_evidence_root: Path,
    plan: Mapping[str, Any],
    *,
    quarantine_root: Path,
) -> dict[str, Any]:
    """Quarantine under the same barrier used to register active writers."""

    root = _canonical_root(owner_evidence_root)
    _validate_plan(plan)
    if plan.get("owner_evidence_root") != _root_identity(root):
        raise EvidenceStoreError("gc_plan_evidence_root_mismatch")
    _quarantine_root(root, quarantine_root)
    barrier_path = _contained_path(root, "lifecycle/barrier.lock")
    if not _path_exists(barrier_path):
        preflight = audit_evidence_store(root)
        if preflight["status"] != "passed":
            raise EvidenceStoreError("gc_apply_current_audit_blocked")
        if (
            preflight["inventory_snapshot_hash"]
            != plan.get("inventory_snapshot_hash")
            or _inventory_identity_rows(preflight["inventory"])
            != _plan_inventory_identity(plan)
        ):
            raise EvidenceStoreError("gc_plan_stale")
    with evidence_lifecycle_barrier(root):
        return _apply_evidence_gc_plan_locked(
            root, plan, quarantine_root=quarantine_root
        )


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _parse_utc(value: object) -> datetime:
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise EvidenceStoreError("lifecycle_timestamp_invalid") from exc
    if parsed.tzinfo is None:
        raise EvidenceStoreError("lifecycle_timestamp_invalid")
    return parsed.astimezone(timezone.utc)


def _purge_evidence_quarantine_locked(
    owner_evidence_root: Path,
    apply_receipt: Mapping[str, Any],
    *,
    quarantine_root: Path,
    confirm_plan_hash: str,
    grace_seconds: int,
) -> dict[str, Any]:
    """Permanently delete only exact, grace-qualified quarantine objects."""

    root = _canonical_root(owner_evidence_root)
    _validate_hashed_receipt(
        apply_receipt,
        schema=EVIDENCE_GC_APPLY_RECEIPT_SCHEMA,
        hash_field="receipt_hash",
    )
    if apply_receipt.get("owner_evidence_root") != _root_identity(root):
        raise EvidenceStoreError("gc_purge_evidence_root_mismatch")
    if confirm_plan_hash != apply_receipt.get("plan_hash"):
        raise EvidenceStoreError("gc_purge_plan_confirmation_mismatch")
    if grace_seconds < 0:
        raise EvidenceStoreError("gc_purge_grace_invalid")
    quarantine, quarantine_relative = _quarantine_root(root, quarantine_root)
    receipt_quarantine = apply_receipt.get("quarantine_root")
    if (
        not isinstance(receipt_quarantine, Mapping)
        or receipt_quarantine.get("path_token") != OWNER_EVIDENCE_PATH_TOKEN
        or receipt_quarantine.get("relative_path") != quarantine_relative
    ):
        raise EvidenceStoreError("gc_purge_quarantine_root_mismatch")
    applied_at = _parse_utc(apply_receipt.get("applied_at"))
    now = datetime.now(timezone.utc)
    if (now - applied_at).total_seconds() < grace_seconds:
        raise EvidenceStoreError("gc_purge_grace_not_satisfied")
    fresh_audit = audit_evidence_store(root)
    if fresh_audit["status"] != "passed":
        raise EvidenceStoreError("gc_purge_fresh_audit_blocked")
    items = apply_receipt.get("items")
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        raise EvidenceStoreError("gc_purge_apply_items_invalid")
    current_paths = {row["relative_path"] for row in fresh_audit["inventory"]}
    for item in items:
        if not isinstance(item, Mapping):
            raise EvidenceStoreError("gc_purge_apply_items_invalid")
        if item.get("source_relative_path") in current_paths:
            raise EvidenceStoreError(
                "gc_purge_source_reappeared", str(item.get("source_relative_path"))
            )

    purge_id = "evidence-purge-" + _wire_hash(
        {
            "apply_receipt_hash": apply_receipt["receipt_hash"],
            "plan_hash": confirm_plan_hash,
            "grace_seconds": grace_seconds,
        }
    ).removeprefix("sha256:")[:24]
    receipt_path = _purge_receipt_path(root, purge_id)
    if _path_is_file(receipt_path):
        existing = dict(
            _load_json_mapping(receipt_path, "gc_purge_receipt_invalid")
        )
        _validate_hashed_receipt(
            existing,
            schema=EVIDENCE_GC_PURGE_RECEIPT_SCHEMA,
            hash_field="receipt_hash",
        )
        return existing

    journal_path = _contained_path(
        root, f"lifecycle/journals/{purge_id}.json"
    )
    if _path_is_file(journal_path):
        journal = _load_valid_journal(
            journal_path,
            operation_id=purge_id,
            plan_hash=confirm_plan_hash,
        )
    else:
        journal = {
            "schema_version": "skillguard.evidence_gc_purge_journal.current",
            "operation_id": purge_id,
            "plan_hash": confirm_plan_hash,
            "status": "in_progress",
            "items": [
                {
                    "source_relative_path": item["source_relative_path"],
                    "quarantine_relative_path": item["quarantine_relative_path"],
                    "content_hash": item["content_hash"],
                    "byte_count": item["byte_count"],
                    "status": "pending",
                }
                for item in items
            ],
        }
        _write_journal(journal_path, journal, root)
    journal_items = journal.get("items")
    if not isinstance(journal_items, list):
        raise EvidenceStoreError("gc_journal_items_invalid")
    purged: list[dict[str, Any]] = []
    for item in journal_items:
        if not isinstance(item, dict):
            raise EvidenceStoreError("gc_journal_items_invalid")
        relative = str(item["quarantine_relative_path"])
        path = _contained_path(root, relative)
        if not (
            path == quarantine
            or path.is_relative_to(quarantine)
        ):
            raise EvidenceStoreError("gc_purge_target_outside_quarantine", relative)
        if item.get("status") == "deleted":
            if _path_exists(path):
                raise EvidenceStoreError("gc_purge_deleted_item_reappeared", relative)
        else:
            if _path_exists(path):
                _validate_file_identity(
                    path, item, "gc_purge_quarantine_identity_mismatch"
                )
                item["status"] = "prepared"
                _write_journal(journal_path, journal, root)
                _path_unlink(path)
                _fsync_directory(path.parent)
            elif item.get("status") != "prepared":
                raise EvidenceStoreError("gc_purge_quarantine_item_missing", relative)
            item["status"] = "deleted"
            _write_journal(journal_path, journal, root)
        purged.append(
            {
                "source_relative_path": item["source_relative_path"],
                "quarantine_relative_path": relative,
                "content_hash": item["content_hash"],
                "byte_count": item["byte_count"],
            }
        )
    journal["status"] = "complete"
    journal["receipt_relative_path"] = receipt_path.relative_to(root).as_posix()
    _write_journal(journal_path, journal, root)
    receipt: dict[str, Any] = {
        "schema_version": EVIDENCE_GC_PURGE_RECEIPT_SCHEMA,
        "policy_id": EVIDENCE_LIFECYCLE_POLICY_ID,
        "status": "purged",
        "purge_id": purge_id,
        "owner_evidence_root": _root_identity(root),
        "apply_receipt_hash": apply_receipt["receipt_hash"],
        "plan_hash": confirm_plan_hash,
        "quarantine_root": {
            "path_token": OWNER_EVIDENCE_PATH_TOKEN,
            "relative_path": quarantine_relative,
        },
        "grace_seconds": grace_seconds,
        "fresh_audit_hash": fresh_audit["audit_hash"],
        "fresh_inventory_snapshot_hash": fresh_audit["inventory_snapshot_hash"],
        "purged_at": _utc_now(),
        "items": purged,
        "journal_ref": _json_file_reference(root, journal_path),
        "claim_boundary": (
            "This receipt proves permanent deletion only for the exact "
            "quarantined objects named here after the fresh audit and grace gates."
        ),
    }
    receipt["receipt_hash"] = _wire_hash(receipt)
    _write_json_atomic(receipt_path, receipt, root=root, immutable=True)
    return receipt


def purge_evidence_quarantine(
    owner_evidence_root: Path,
    apply_receipt: Mapping[str, Any],
    *,
    quarantine_root: Path,
    confirm_plan_hash: str,
    grace_seconds: int,
) -> dict[str, Any]:
    """Purge under the same barrier used to register active writers."""

    root = _canonical_root(owner_evidence_root)
    _validate_hashed_receipt(
        apply_receipt,
        schema=EVIDENCE_GC_APPLY_RECEIPT_SCHEMA,
        hash_field="receipt_hash",
    )
    if apply_receipt.get("owner_evidence_root") != _root_identity(root):
        raise EvidenceStoreError("gc_purge_evidence_root_mismatch")
    if confirm_plan_hash != apply_receipt.get("plan_hash"):
        raise EvidenceStoreError("gc_purge_plan_confirmation_mismatch")
    if grace_seconds < 0:
        raise EvidenceStoreError("gc_purge_grace_invalid")
    _quarantine_root(root, quarantine_root)
    barrier_path = _contained_path(root, "lifecycle/barrier.lock")
    if (
        not _path_exists(barrier_path)
        and audit_evidence_store(root)["status"] != "passed"
    ):
        raise EvidenceStoreError("gc_purge_fresh_audit_blocked")
    with evidence_lifecycle_barrier(root):
        return _purge_evidence_quarantine_locked(
            root,
            apply_receipt,
            quarantine_root=quarantine_root,
            confirm_plan_hash=confirm_plan_hash,
            grace_seconds=grace_seconds,
        )


__all__ = [
    "ACTIVE_WRITER_SCHEMA",
    "CURRENT_AGGREGATION_AUTHORITY_SCHEMA",
    "CURRENT_HEAD_AUTHORITY_SCHEMA",
    "DEFAULT_MAX_LOGICAL_BYTES",
    "EVIDENCE_AUDIT_SCHEMA",
    "EVIDENCE_GC_APPLY_RECEIPT_SCHEMA",
    "EVIDENCE_GC_PLAN_SCHEMA",
    "EVIDENCE_GC_PURGE_RECEIPT_SCHEMA",
    "EVIDENCE_LIFECYCLE_POLICY_ID",
    "EvidenceStoreError",
    "VerifiedStreamObject",
    "active_evidence_writer",
    "apply_evidence_gc_plan",
    "audit_evidence_store",
    "begin_evidence_writer",
    "end_evidence_writer",
    "evidence_lifecycle_barrier",
    "persist_compressed_stream",
    "plan_evidence_gc",
    "publish_current_head_authority",
    "publish_current_aggregation_authority",
    "purge_evidence_quarantine",
    "verify_compressed_stream",
]
