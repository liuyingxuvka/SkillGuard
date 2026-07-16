"""Staged component-projected SkillGuard installation with parity and rollback."""

from __future__ import annotations

import json
import errno
import os
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .contract_compiler import (
    canonical_hash,
    canonical_json_bytes,
    current_content_projection,
    file_hash,
    impact_file_hash,
    source_file_hash,
    wire_hash,
)
from .execution_records import (
    attach_process_tree_containment,
    isolated_process_kwargs,
    release_process_tree_containment,
)
from .portable_content import (
    ACTIVE_INSTALLATION_CURRENTNESS_PROJECTION_ID,
    PORTABLE_CONTENT_POLICY_ID,
    ignored_copy_names,
    portable_files,
    scan_active_installation_currentness_boundary,
    scan_member_boundary,
)
from .runtime_authority import AUTHORITY_CURRENT, resolve_runtime_authority


GLOBAL_ROUTER_MEMBER = "skillguard-global-router"
RUNTIME_SENTINEL = Path("scripts/skillguard_v2/runtime_fingerprint.py")
WINDOWS_PATH_BUDGET_ENABLED = os.name == "nt"
WINDOWS_STAGE_FILE_PATH_LIMIT = 259
WINDOWS_STAGE_DIRECTORY_PATH_LIMIT = 247
INSTALL_LOCK_NAME = ".skillguard-install.lock"
TRANSACTION_DIRECTORY = "install-transactions"
INSTALL_HEAD_FILE = "HEAD.json"
TRANSACTION_SCHEMA = "skillguard.install_transaction.v1"
TRANSACTION_ID_PATTERN = re.compile(r"^install-[0-9a-f]{32}$")
TERMINAL_TRANSACTION_STATUSES = frozenset(
    {
        "committed",
        "blocked_before_activation",
        "rolled_back",
        "recovered_rolled_back",
        "manually_rolled_back",
    }
)
INSTALLATION_PROJECTION_SCHEMA = "skillguard.installation_projection.current"
GENERATED_INSTALL_AUTHORITIES = (
    ".skillguard/check-manifest.json",
    ".skillguard/compiled-contract.json",
)


def _installation_member_relative_path(
    member_root_path: object, value: object
) -> str:
    """Project a canonical or isolated member path into one skill root."""

    root_path = str(member_root_path).replace("\\", "/").strip().strip("/")
    repository_path = str(value).replace("\\", "/").strip()
    if not root_path or any(
        part in {"", ".."} for part in root_path.split("/")
    ):
        raise ValueError("installation_projection_member_root_invalid")
    if root_path == ".":
        relative = repository_path
    else:
        prefix = f"{root_path}/"
        if not repository_path.startswith(prefix):
            raise ValueError("installation_projection_path_outside_member")
        relative = repository_path[len(prefix) :]
    if (
        not relative
        or relative.startswith("/")
        or any(part in {"", ".", ".."} for part in relative.split("/"))
    ):
        raise ValueError("installation_projection_member_path_invalid")
    return relative


def installation_projection_identity(skill_root: Path) -> dict[str, Any]:
    """Recompute the exact installable component projection for one member.

    Source-only tests, models, and notes are intentionally outside this
    identity, so they cannot make an otherwise current installation stale.
    """

    root = skill_root.resolve(strict=True)
    manifest_path = root / ".skillguard" / "check-manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("installation_projection_manifest_missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, Mapping):
        raise ValueError("installation_projection_manifest_invalid")
    skill_id = str(manifest.get("skill_id", "")).strip()
    if not skill_id:
        raise ValueError("installation_projection_skill_id_mismatch")
    plan = manifest.get("content_impact_plan")
    if not isinstance(plan, Mapping):
        raise ValueError("installation_projection_plan_missing")
    member_root_path = plan.get("member_root_path")
    projection = current_content_projection(plan, "projection:installation")
    components = {
        str(row.get("component_id", "")): row
        for row in plan.get("components", [])
        if isinstance(row, Mapping)
    }
    component_rows: list[dict[str, Any]] = []
    for component_id in projection["input_component_ids"]:
        component = components.get(component_id)
        if not isinstance(component, Mapping):
            raise ValueError("installation_projection_component_missing")
        members: list[dict[str, str]] = []
        for repository_path in component.get("member_paths", []):
            repository_path = str(repository_path).replace("\\", "/")
            relative = _installation_member_relative_path(
                member_root_path, repository_path
            )
            candidate = root / Path(*relative.split("/"))
            if candidate.is_symlink() or not candidate.is_file():
                raise ValueError("installation_projection_member_missing")
            members.append(
                {
                    "path": repository_path,
                    "content_hash": impact_file_hash(candidate),
                }
            )
        actual_component_hash = wire_hash(members)
        if actual_component_hash != component.get("component_hash"):
            raise ValueError("installation_projection_component_hash_mismatch")
        component_rows.append(
            {
                "component_id": component_id,
                "component_hash": actual_component_hash,
            }
        )
    input_projection_hash = wire_hash(component_rows)
    if input_projection_hash != projection["input_projection_hash"]:
        raise ValueError("installation_projection_input_hash_mismatch")
    identity = {
        "schema_version": INSTALLATION_PROJECTION_SCHEMA,
        "skill_id": skill_id,
        "input_component_ids": list(projection["input_component_ids"]),
        "projection_declaration_hash": projection["projection_declaration_hash"],
        "input_projection_hash": input_projection_hash,
        "consumer_projection_hash": projection["consumer_projection_hash"],
    }
    identity["identity_hash"] = wire_hash(identity)
    return identity


def installation_member_paths(skill_root: Path) -> tuple[str, ...]:
    """Return the exact relative files admitted to one installed member."""

    root = skill_root.resolve(strict=True)
    manifest_path = root / ".skillguard" / "check-manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("installation_projection_manifest_missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, Mapping):
        raise ValueError("installation_projection_manifest_invalid")
    skill_id = str(manifest.get("skill_id", "")).strip()
    plan = manifest.get("content_impact_plan")
    if not skill_id or not isinstance(plan, Mapping):
        raise ValueError("installation_projection_plan_missing")
    member_root_path = plan.get("member_root_path")
    projection = current_content_projection(plan, "projection:installation")
    components = {
        str(row.get("component_id", "")): row
        for row in plan.get("components", [])
        if isinstance(row, Mapping)
    }
    paths: set[str] = set()
    for component_id in projection["input_component_ids"]:
        component = components.get(component_id)
        if not isinstance(component, Mapping) or component.get(
            "install_disposition"
        ) not in {"copy", "generate"}:
            raise ValueError("installation_projection_component_invalid")
        for repository_path_value in component.get("member_paths", []):
            repository_path = str(repository_path_value).replace("\\", "/")
            relative = _installation_member_relative_path(
                member_root_path, repository_path
            )
            paths.add(relative)
    paths.update(GENERATED_INSTALL_AUTHORITIES)
    if not paths:
        raise ValueError("installation_projection_empty")
    return tuple(sorted(paths))


class InstallBusyError(RuntimeError):
    """Raised when another process or thread owns the installation mutex."""


class UnsafeInstallPathError(ValueError):
    """Raised when a CODEX_HOME control path escapes through a link or junction."""


def _activation_exception_diagnostic(
    exc: Exception, *, phase: str
) -> dict[str, Any]:
    """Return path-free machine diagnostics for a rolled-back activation."""

    nested: list[object] = []
    if isinstance(exc, shutil.Error) and exc.args and isinstance(exc.args[0], list):
        nested.extend(exc.args[0])
    os_error_codes: set[int] = set()
    messages: list[str] = [str(exc)]
    for row in nested:
        detail = row[2] if isinstance(row, tuple) and len(row) >= 3 else row
        messages.append(str(detail))
        if isinstance(detail, OSError):
            for value in (detail.errno, getattr(detail, "winerror", None)):
                if isinstance(value, int):
                    os_error_codes.add(value)
    if isinstance(exc, OSError):
        for value in (exc.errno, getattr(exc, "winerror", None)):
            if isinstance(value, int):
                os_error_codes.add(value)
    for message in messages:
        os_error_codes.update(
            int(value)
            for value in re.findall(r"(?:WinError|Errno)\s+(\d+)", message)
        )
    if 206 in os_error_codes or errno.ENAMETOOLONG in os_error_codes:
        code = "activation_destination_path_too_long"
    elif isinstance(exc, shutil.Error):
        code = "activation_incoming_copy_failed"
    elif isinstance(exc, OSError):
        code = "activation_os_error"
    else:
        code = "activation_internal_error"
    return {
        "exception_code": code,
        "exception_detail": {
            "phase": str(phase),
            "exception_kind": type(exc).__name__,
            "nested_error_count": len(nested),
            "os_error_codes": sorted(os_error_codes),
        },
        "exception_message_hash": canonical_hash(
            {"exception_kind": type(exc).__name__, "message": str(exc)}
        ),
    }


_PROCESS_LOCK_GUARD = threading.Lock()
_PROCESS_LOCKED_PATHS: set[str] = set()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _maybe_failpoint(name: str) -> None:
    if os.environ.get("SKILLGUARD_INSTALL_FAILPOINT") == name:
        os._exit(97)


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _durable_mkdir(path: Path) -> None:
    path = path.resolve()
    missing: list[Path] = []
    cursor = path
    while not cursor.exists():
        missing.append(cursor)
        if cursor.parent == cursor:
            break
        cursor = cursor.parent
    if cursor.exists() and not cursor.is_dir():
        raise NotADirectoryError(str(cursor))
    for directory in reversed(missing):
        directory.mkdir()
        if os.name != "nt":
            _fsync_directory(directory.parent)
            _fsync_directory(directory)


def _windows_move(source: Path, destination: Path, *, replace: bool) -> None:
    import ctypes

    move_file_ex = ctypes.WinDLL("kernel32", use_last_error=True).MoveFileExW
    move_file_ex.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
    move_file_ex.restype = ctypes.c_int
    flags = 0x00000008 | (0x00000001 if replace else 0)
    if not move_file_ex(str(source), str(destination), flags):
        raise ctypes.WinError(ctypes.get_last_error())


def _durable_replace(source: Path, destination: Path) -> None:
    source_parent = source.parent.resolve()
    destination_parent = destination.parent.resolve()
    if os.name == "nt":
        _windows_move(source, destination, replace=True)
        return
    os.replace(source, destination)
    _fsync_directory(destination_parent)
    if source_parent != destination_parent:
        _fsync_directory(source_parent)


def _durable_rename(source: Path, destination: Path) -> Path:
    source_parent = source.parent.resolve()
    destination_parent = destination.parent.resolve()
    if os.name == "nt":
        _windows_move(source, destination, replace=False)
    else:
        source.rename(destination)
        _fsync_directory(destination_parent)
        if source_parent != destination_parent:
            _fsync_directory(source_parent)
    return destination


def _fsync_tree(root: Path) -> None:
    for path in sorted(root.rglob("*")):
        if path.is_file():
            mode = "r+b" if os.name == "nt" else "rb"
            with path.open(mode) as handle:
                os.fsync(handle.fileno())
    if os.name != "nt":
        directories = [path for path in root.rglob("*") if path.is_dir()]
        for directory in sorted(directories, key=lambda value: len(value.parts), reverse=True):
            _fsync_directory(directory)
        _fsync_directory(root)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    _durable_mkdir(path.parent)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    with temporary.open("wb") as handle:
        handle.write(canonical_json_bytes(payload))
        handle.flush()
        os.fsync(handle.fileno())
    _durable_replace(temporary, path)


def _is_reparse_point(path: Path) -> bool:
    try:
        attributes = path.lstat().st_file_attributes
    except AttributeError:
        attributes = 0
    except FileNotFoundError:
        return path.is_symlink()
    if attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
        return True
    is_junction = getattr(path, "is_junction", None)
    return path.is_symlink() or bool(is_junction and is_junction())


def _path_entity_exists(path: Path) -> bool:
    return os.path.lexists(path)


def _validate_codex_control_paths(codex_home: Path) -> None:
    home = codex_home.resolve()
    for relative in (Path("skills"), Path("backups"), Path(TRANSACTION_DIRECTORY)):
        path = home / relative
        if not _path_entity_exists(path):
            continue
        if _is_reparse_point(path):
            raise UnsafeInstallPathError(f"CODEX_HOME control path is a reparse point: {relative}")
        if not path.is_dir() or not _path_within(path, home):
            raise UnsafeInstallPathError(f"CODEX_HOME control path escapes: {relative}")
    lock_path = home / INSTALL_LOCK_NAME
    if _path_entity_exists(lock_path) and (
        _is_reparse_point(lock_path)
        or not lock_path.is_file()
        or not _path_within(lock_path, home)
    ):
        raise UnsafeInstallPathError("CODEX_HOME installation lock path is unsafe")


def _lock_handle(handle: Any) -> None:
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"\x00")
        handle.flush()
        os.fsync(handle.fileno())
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise InstallBusyError("install_lock_busy") from exc
    else:
        import fcntl

        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise InstallBusyError("install_lock_busy") from exc


def _unlock_handle(handle: Any) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class _InstallMutex:
    def __init__(self, codex_home: Path, operation: str) -> None:
        self.codex_home = codex_home.resolve()
        self.path = self.codex_home / INSTALL_LOCK_NAME
        self.operation = operation
        self.handle: Any | None = None
        self.key = str(self.path).casefold()

    def __enter__(self) -> "_InstallMutex":
        _durable_mkdir(self.codex_home)
        _validate_codex_control_paths(self.codex_home)
        with _PROCESS_LOCK_GUARD:
            if self.key in _PROCESS_LOCKED_PATHS:
                raise InstallBusyError("install_lock_busy")
            _PROCESS_LOCKED_PATHS.add(self.key)
        try:
            flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0)
            flags |= getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(self.path, flags, 0o600)
            self.handle = os.fdopen(descriptor, "a+b")
            _lock_handle(self.handle)
            metadata = canonical_json_bytes(
                {
                    "schema_version": "skillguard.install_lock.v1",
                    "pid": os.getpid(),
                    "host": socket.gethostname(),
                    "operation": self.operation,
                    "acquired_at": _utc_now(),
                }
            )
            self.handle.seek(1)
            self.handle.truncate(1)
            self.handle.write(metadata)
            self.handle.flush()
            os.fsync(self.handle.fileno())
        except Exception:
            if self.handle is not None:
                self.handle.close()
                self.handle = None
            with _PROCESS_LOCK_GUARD:
                _PROCESS_LOCKED_PATHS.discard(self.key)
            raise
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        try:
            if self.handle is not None:
                _unlock_handle(self.handle)
                self.handle.close()
        finally:
            self.handle = None
            with _PROCESS_LOCK_GUARD:
                _PROCESS_LOCKED_PATHS.discard(self.key)


def _source_identity(
    root: Path,
    *,
    active_installation_currentness: bool = False,
) -> dict[str, Any]:
    root = Path(os.path.abspath(root))
    if not _path_entity_exists(root):
        return {
            "exists": False,
            "kind": "absent",
            "manifest_hash": canonical_hash({}),
            "file_count": 0,
        }
    if _is_reparse_point(root):
        return {
            "exists": True,
            "kind": "reparse_point",
            "manifest_hash": canonical_hash(
                {"kind": "reparse_point", "name": root.name}
            ),
            "file_count": 0,
        }
    if not root.is_dir():
        return {
            "exists": True,
            "kind": "file",
            "manifest_hash": canonical_hash(
                {"kind": "file", "name": root.name, "size": root.stat().st_size}
            ),
            "file_count": 1,
        }
    try:
        projection = installation_projection_identity(root)
        member_paths = installation_member_paths(root)
    except (OSError, UnicodeError, ValueError) as exc:
        try:
            recovery_identity = _raw_recovery_tree_identity(root)
        except (OSError, UnicodeError, ValueError):
            return {
                "exists": True,
                "kind": "unsupported_directory_authority",
                "manifest_hash": canonical_hash(
                    {
                        "policy": INSTALLATION_PROJECTION_SCHEMA,
                        "error": str(exc),
                    }
                ),
                "file_count": 0,
            }
        recovery_identity["projection_error"] = str(exc)
        return recovery_identity
    return {
        "exists": True,
        "kind": "directory",
        "manifest_hash": canonical_hash(projection),
        "file_count": len(member_paths),
    }


def _identity_matches(
    root: Path,
    expected: dict[str, Any],
    *,
    active_installation_currentness: bool = False,
) -> bool:
    actual = _source_identity(
        root,
        active_installation_currentness=active_installation_currentness,
    )
    return _identities_equal(actual, expected)


def _identities_equal(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    return (
        bool(actual["exists"]) == bool(expected.get("exists"))
        and str(actual.get("kind")) == str(expected.get("kind"))
        and str(actual["manifest_hash"]) == str(expected.get("manifest_hash"))
        and int(actual["file_count"]) == int(expected.get("file_count", -1))
    )


def _raw_recovery_tree_identity(root: Path) -> dict[str, Any]:
    """Hash one whole non-link tree for replacement rollback only."""

    rows: list[dict[str, Any]] = []
    for directory_text, directory_names, file_names in os.walk(
        root, topdown=True, followlinks=False
    ):
        directory = Path(directory_text)
        retained: list[str] = []
        for name in sorted(directory_names):
            candidate = directory / name
            relative = candidate.relative_to(root).as_posix()
            if _is_reparse_point(candidate) or not candidate.is_dir():
                raise ValueError(f"recovery_tree_directory_unsafe:{relative}")
            rows.append({"path": relative, "kind": "directory"})
            retained.append(name)
        directory_names[:] = retained
        for name in sorted(file_names):
            candidate = directory / name
            relative = candidate.relative_to(root).as_posix()
            if _is_reparse_point(candidate) or not candidate.is_file():
                raise ValueError(f"recovery_tree_file_unsafe:{relative}")
            rows.append(
                {
                    "path": relative,
                    "kind": "file",
                    "sha256": file_hash(candidate),
                    "byte_count": candidate.stat().st_size,
                }
            )
    return {
        "exists": True,
        "kind": "recovery_directory",
        "manifest_hash": canonical_hash(rows),
        "file_count": sum(row["kind"] == "file" for row in rows),
    }


def _transaction_root(codex_home: Path) -> Path:
    return codex_home.resolve() / TRANSACTION_DIRECTORY


def _head_path(codex_home: Path) -> Path:
    return _transaction_root(codex_home) / INSTALL_HEAD_FILE


def _empty_install_head() -> dict[str, Any]:
    return {
        "schema_version": "skillguard.install_head.v1",
        "transaction_id": None,
        "previous_transaction_id": None,
        "generation": 0,
    }


def _load_install_head(codex_home: Path) -> dict[str, Any]:
    path = _head_path(codex_home)
    if _path_entity_exists(path) and (_is_reparse_point(path) or not path.is_file()):
        raise ValueError("installation HEAD path is unsafe")
    if not path.is_file():
        return _empty_install_head()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != "skillguard.install_head.v1":
        raise ValueError("invalid installation HEAD")
    expected_hash = canonical_hash({key: value for key, value in payload.items() if key != "head_hash"})
    if payload.get("head_hash") != expected_hash:
        raise ValueError("installation HEAD hash mismatch")
    transaction_id = payload.get("transaction_id")
    previous_id = payload.get("previous_transaction_id")
    if transaction_id is not None and not TRANSACTION_ID_PATTERN.fullmatch(str(transaction_id)):
        raise ValueError("installation HEAD transaction id is invalid")
    if previous_id is not None and not TRANSACTION_ID_PATTERN.fullmatch(str(previous_id)):
        raise ValueError("installation HEAD previous transaction id is invalid")
    if not isinstance(payload.get("generation"), int) or int(payload["generation"]) < 0:
        raise ValueError("installation HEAD generation is invalid")
    return payload


def _write_install_head(
    codex_home: Path,
    *,
    transaction_id: str | None,
    previous_transaction_id: str | None,
    generation: int,
) -> dict[str, Any]:
    if transaction_id is not None and not TRANSACTION_ID_PATTERN.fullmatch(transaction_id):
        raise ValueError("installation HEAD transaction id is invalid")
    if previous_transaction_id is not None and not TRANSACTION_ID_PATTERN.fullmatch(
        previous_transaction_id
    ):
        raise ValueError("installation HEAD previous transaction id is invalid")
    payload: dict[str, Any] = {
        "schema_version": "skillguard.install_head.v1",
        "transaction_id": transaction_id,
        "previous_transaction_id": previous_transaction_id,
        "generation": generation,
        "updated_at": _utc_now(),
    }
    payload["head_hash"] = canonical_hash(payload)
    _atomic_write_json(_head_path(codex_home), payload)
    return payload


def _journal_path(codex_home: Path, transaction_id: str) -> Path:
    if not TRANSACTION_ID_PATTERN.fullmatch(transaction_id):
        raise ValueError("invalid installation transaction id")
    return _transaction_root(codex_home) / f"{transaction_id}.json"


def _receipt_path(codex_home: Path, transaction_id: str, suffix: str = "activation") -> Path:
    if not TRANSACTION_ID_PATTERN.fullmatch(transaction_id):
        raise ValueError("invalid installation transaction id")
    return _transaction_root(codex_home) / "receipts" / f"{transaction_id}-{suffix}.json"


def _persist_transaction(codex_home: Path, record: dict[str, Any]) -> Path:
    transaction_id = str(record["transaction_id"])
    record["updated_at"] = _utc_now()
    hash_payload = {key: value for key, value in record.items() if key != "journal_hash"}
    record["journal_hash"] = canonical_hash(hash_payload)
    path = _journal_path(codex_home, transaction_id)
    _atomic_write_json(path, record)
    return path


def _write_receipt(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    receipt = dict(payload)
    receipt["receipt_hash"] = canonical_hash(
        {key: value for key, value in receipt.items() if key != "receipt_hash"}
    )
    _atomic_write_json(path, receipt)
    return receipt


def _path_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _validate_transaction_paths(
    codex_home: Path,
    transaction_id: str,
    payload: dict[str, Any],
) -> None:
    members = payload.get("members")
    if not isinstance(members, dict) or set(members) != {"skillguard", GLOBAL_ROUTER_MEMBER}:
        raise ValueError("installation transaction member set is incomplete")
    home = codex_home.resolve()
    role_paths: list[tuple[str, Path]] = []
    for member_id, member in members.items():
        if not isinstance(member, dict):
            raise ValueError("invalid installation transaction member")
        for key in ("active_root", "incoming_root", "backup_root"):
            value = member.get(key)
            if not isinstance(value, str) or not _path_within(Path(value), home):
                raise ValueError(f"installation transaction {key} escapes CODEX_HOME")
        active_path = Path(member["active_root"])
        incoming_path = Path(member["incoming_root"])
        backup_path = Path(member["backup_root"])
        active_root = active_path.resolve()
        incoming_root = incoming_path.resolve()
        backup_root = backup_path.resolve()
        if active_root != (home / "skills" / member_id).resolve():
            raise ValueError("installation transaction active root is not a suite member root")
        if (
            incoming_root.parent != (home / "skills").resolve()
            or incoming_root.name != f".{member_id}-installing-{transaction_id[8:]}"
        ):
            raise ValueError("installation transaction incoming root is invalid")
        expected_backup = (home / "backups" / f"{member_id}-{transaction_id[8:]}").resolve()
        if backup_root != expected_backup:
            raise ValueError("installation transaction backup root is invalid")
        for role, lexical_root, resolved_root in (
            (f"active:{member_id}", active_path, active_root),
            (f"incoming:{member_id}", incoming_path, incoming_root),
            (f"backup:{member_id}", backup_path, backup_root),
        ):
            if _path_entity_exists(lexical_root) and (
                _is_reparse_point(lexical_root) or not lexical_root.is_dir()
            ):
                raise ValueError(
                    f"installation transaction {role} is not a real directory"
                )
            role_paths.append((role, resolved_root))
    receipt_value = payload.get("activation_receipt_path")
    if not isinstance(receipt_value, str) or not _path_within(Path(receipt_value), home):
        raise ValueError("installation transaction receipt escapes CODEX_HOME")
    if Path(receipt_value).resolve() != _receipt_path(home, transaction_id).resolve():
        raise ValueError("installation transaction activation receipt path is invalid")
    for index, (left_role, left) in enumerate(role_paths):
        for right_role, right in role_paths[index + 1 :]:
            if left == right or left.is_relative_to(right) or right.is_relative_to(left):
                raise ValueError(
                    f"installation transaction path overlap: {left_role} vs {right_role}"
                )


def _load_transaction(codex_home: Path, transaction_id: str) -> dict[str, Any]:
    path = _journal_path(codex_home, transaction_id)
    if _path_entity_exists(path) and (_is_reparse_point(path) or not path.is_file()):
        raise ValueError("installation transaction journal path is unsafe")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != TRANSACTION_SCHEMA:
        raise ValueError("invalid installation transaction journal")
    expected_hash = canonical_hash({key: value for key, value in payload.items() if key != "journal_hash"})
    if payload.get("journal_hash") != expected_hash:
        raise ValueError("installation transaction journal hash mismatch")
    if payload.get("transaction_id") != transaction_id:
        raise ValueError("installation transaction id mismatch")
    _validate_transaction_paths(codex_home, transaction_id, payload)
    return payload


def _activation_receipt_payload(record: dict[str, Any]) -> dict[str, Any] | None:
    receipt_path = Path(str(record.get("activation_receipt_path", "")))
    if _path_entity_exists(receipt_path) and _is_reparse_point(receipt_path):
        return None
    if not receipt_path.is_file():
        return None
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(receipt, dict):
        return None
    return receipt


def _installed_smoke_evidence_complete(
    value: object,
    member_order: list[str],
) -> bool:
    expected_smoke_check_ids = {
        f"installed:runtime-authority:{member_id}" for member_id in member_order
    } | {
        "installed:commands",
        "installed:check-contract:skillguard",
        "installed:check-contract:skillguard-global-router",
        "installed:self-check",
        "installed:check-skill",
        "installed:runtime-import",
    }
    if not isinstance(value, dict):
        return False
    checks = value.get("checks")
    return bool(
        value.get("status") == "passed"
        and value.get("skipped_checks") == []
        and isinstance(checks, list)
        and len(checks) == len(expected_smoke_check_ids)
        and {
            str(row.get("check_id", ""))
            for row in checks
            if isinstance(row, dict) and row.get("status") == "passed"
        }
        == expected_smoke_check_ids
    )


def _hardened_activation_receipt_stored_integrity(
    record: dict[str, Any],
    receipt: dict[str, Any],
) -> bool:
    expected_hash = canonical_hash(
        {key: value for key, value in receipt.items() if key != "receipt_hash"}
    )
    base_current = (
        receipt.get("schema_version") == "skillguard.install_activation_receipt.v1"
        and receipt.get("artifact_type") == "skillguard_install_activation_receipt"
        and TRANSACTION_ID_PATTERN.fullmatch(str(record.get("transaction_id", "")))
        and receipt.get("transaction_id") == record.get("transaction_id")
        and receipt.get("status") == "activation_verified"
        and receipt.get("receipt_hash") == expected_hash
        and record.get("activation_receipt_hash") == expected_hash
        and receipt.get("journal_hash")
        == record.get("activation_verification_journal_hash")
        and receipt.get("stage_verification_hash")
        == canonical_hash(record.get("stage_verification", {}))
        and receipt.get("post_activation_smoke_hash")
        == canonical_hash(record.get("post_activation_smoke", {}))
        and receipt.get("post_activation_member_comparisons_hash")
        == canonical_hash(record.get("post_activation_member_comparisons", {}))
        and receipt.get("rollback_disposition") == "not_required"
        and record.get("rollback_disposition") == "not_required"
    )
    if not base_current:
        return False
    member_order = record.get("member_order", [])
    if member_order != ["skillguard", GLOBAL_ROUTER_MEMBER]:
        return False
    members = record.get("members")
    if not isinstance(members, dict) or set(members) != set(member_order):
        return False
    required_member_fields = {
        "backup_root",
        "canonical_identity",
        "stage_identity",
        "previous_identity",
        "backup_identity",
        "installed_identity",
        "canonical_installation_projection",
        "stage_installation_projection",
        "installed_installation_projection",
    }
    if any(
        not isinstance(members.get(member_id), dict)
        or not required_member_fields.issubset(members[member_id])
        for member_id in member_order
    ):
        return False
    if receipt.get("installed_member_ids") != member_order:
        return False
    if receipt.get("backup_roots") != {
        member_id: members[member_id]["backup_root"] for member_id in member_order
    }:
        return False
    expected_fields = {
        "canonical_identities": "canonical_identity",
        "stage_identities": "stage_identity",
        "previous_identities": "previous_identity",
        "backup_identities": "backup_identity",
        "installed_identities": "installed_identity",
        "canonical_installation_projections": "canonical_installation_projection",
        "stage_installation_projections": "stage_installation_projection",
        "installed_installation_projections": "installed_installation_projection",
    }
    for receipt_field, member_field in expected_fields.items():
        expected = {
            member_id: members[member_id][member_field]
            for member_id in member_order
        }
        if receipt.get(receipt_field) != expected:
            return False
    stage_verification = record.get("stage_verification")
    post_activation_smoke = record.get("post_activation_smoke")
    post_activation_comparisons = record.get("post_activation_member_comparisons")
    if (
        not isinstance(stage_verification, dict)
        or stage_verification.get("status") != "passed"
        or stage_verification.get("blockers") != []
        or not _installed_smoke_evidence_complete(
            stage_verification.get("smoke"), member_order
        )
        or not isinstance(stage_verification.get("member_comparisons"), dict)
        or any(
            not isinstance(value, dict) or not _comparison_current(value)
            for value in stage_verification["member_comparisons"].values()
        )
        or set(stage_verification["member_comparisons"]) != set(member_order)
        or not _installed_smoke_evidence_complete(post_activation_smoke, member_order)
        or not isinstance(post_activation_comparisons, dict)
        or set(post_activation_comparisons) != set(member_order)
        or any(
            not isinstance(value, dict) or not _comparison_current(value)
            for value in post_activation_comparisons.values()
        )
    ):
        return False
    for member_id in member_order:
        member = members[member_id]
        if not (
            _identities_equal(member["canonical_identity"], member["stage_identity"])
            and _identities_equal(member["stage_identity"], member["installed_identity"])
            and member["canonical_installation_projection"]
            == member["stage_installation_projection"]
            and member["stage_installation_projection"]
            == member["installed_installation_projection"]
        ):
            return False
    return True


def _hardened_activation_receipt_historical_integrity(
    record: dict[str, Any],
) -> bool:
    """Validate non-HEAD hardened history without consulting a live tree.

    This recovery-only helper is deliberately absent from installation receipt
    and scheduled-production currentness paths.
    """

    receipt = _activation_receipt_payload(record)
    return bool(
        receipt is not None
        and record.get("status") == "committed"
        and record.get("phase") == "committed"
        and _hardened_activation_receipt_stored_integrity(record, receipt)
    )


def _terminal_record_uses_current_projection(record: Mapping[str, Any]) -> bool:
    member_order = record.get("member_order")
    members = record.get("members")
    return bool(
        member_order == ["skillguard", GLOBAL_ROUTER_MEMBER]
        and isinstance(members, Mapping)
        and all(
            isinstance(members.get(member_id), Mapping)
            and "canonical_installation_projection" in members[member_id]
            and "stage_installation_projection" in members[member_id]
            and "installed_installation_projection" in members[member_id]
            for member_id in member_order
        )
    )


def _activation_receipt_active_current(record: dict[str, Any]) -> bool:
    """Replay a committed head against its active install, not a future source tree."""

    receipt = _activation_receipt_payload(record)
    if receipt is None or not _hardened_activation_receipt_stored_integrity(
        record, receipt
    ):
        return False
    try:
        return all(
            installation_projection_identity(
                Path(record["members"][member_id]["active_root"])
            )
            == record["members"][member_id]["installed_installation_projection"]
            and _identity_matches(
                Path(record["members"][member_id]["active_root"]),
                record["members"][member_id]["installed_identity"],
                active_installation_currentness=True,
            )
            for member_id in record["member_order"]
        )
    except (OSError, UnicodeError, ValueError):
        # Projection-policy drift or active-byte drift makes the committed head
        # non-current and therefore recoverable. It must never crash recovery
        # or be promoted to a valid active receipt.
        return False


def _activation_receipt_active_recoverable(record: dict[str, Any]) -> bool:
    """Check rollback eligibility from stored bytes without future policy replay."""

    receipt = _activation_receipt_payload(record)
    if receipt is None or not _hardened_activation_receipt_stored_integrity(
        record, receipt
    ):
        return False
    return all(
        _identity_matches(
            Path(record["members"][member_id]["active_root"]),
            record["members"][member_id]["installed_identity"],
            active_installation_currentness=True,
        )
        for member_id in record["member_order"]
    )


def _activation_receipt_active_replacement_eligible(
    record: dict[str, Any],
) -> bool:
    """Admit a safe non-empty snapshot only while a verified replacement is pending.

    A historical head may have both active and backup drift after an interrupted
    recovery. The ordinary restore path must remain blocked in that state. A
    separately verified replacement may still proceed because the next
    transaction snapshots the exact current active trees as its own backups
    before activation. This never promotes the drifted tree to current evidence.
    """

    receipt = _activation_receipt_payload(record)
    if receipt is None or not _hardened_activation_receipt_stored_integrity(
        record, receipt
    ):
        return False
    for member_id in record["member_order"]:
        member = record["members"][member_id]
        actual = _source_identity(
            Path(member["active_root"]),
            active_installation_currentness=True,
        )
        if _identities_equal(actual, member["installed_identity"]):
            continue
        if (
            actual.get("exists") is not True
            or actual.get("kind") not in {"directory", "recovery_directory"}
            or int(actual.get("file_count", 0)) <= 0
        ):
            return False
    return True


def _activation_receipt_current(record: dict[str, Any]) -> bool:
    """Replay active integrity plus parity with the currently maintained source."""

    return _activation_receipt_active_current(record) and all(
        installation_projection_identity(
            Path(record["members"][member_id]["canonical_root"])
        )
        == record["members"][member_id]["canonical_installation_projection"]
        for member_id in record["member_order"]
    )


def _recovery_receipt_current(record: dict[str, Any]) -> bool:
    receipt_path = Path(str(record.get("recovery_receipt_path", "")))
    if _path_entity_exists(receipt_path) and _is_reparse_point(receipt_path):
        return False
    if not receipt_path.is_file():
        return False
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(receipt, dict):
        return False
    expected_hash = canonical_hash(
        {key: value for key, value in receipt.items() if key != "receipt_hash"}
    )
    return (
        receipt.get("transaction_id") == record.get("transaction_id")
        and receipt.get("terminal_status") == record.get("status")
        and receipt.get("receipt_hash") == expected_hash
        and record.get("recovery_receipt_hash") == expected_hash
        and receipt.get("journal_hash")
        == record.get("recovery_verification_journal_hash")
    )


def _ignore_for_member(member_root: Path):
    """Project the shared context-aware portable-content policy into copytree."""

    member_root = member_root.resolve()

    def ignore(directory: str, names: list[str]) -> set[str]:
        return ignored_copy_names(member_root, Path(directory), names)

    return ignore
def _runtime_authority_projection(root: Path) -> dict[str, Any]:
    try:
        return resolve_runtime_authority(root).to_dict()
    except Exception as exc:
        return {
            "artifact_type": "skillguard_runtime_authority_decision",
            "ok": False,
            "authority": "blocked",
            "skill_id": root.name,
            "skill_root": root.name,
            "blockers": ["runtime_authority_resolution_failed"],
            "error_kind": type(exc).__name__,
        }


def _authority_blockers(projection: dict[str, Any]) -> list[str]:
    if (
        projection.get("ok") is True
        and projection.get("authority") == AUTHORITY_CURRENT
    ):
        return []
    raw = projection.get("blockers")
    blockers = (
        [str(value) for value in raw if str(value)]
        if isinstance(raw, list)
        else []
    )
    return blockers or ["runtime_authority_blocked"]


def _canonical_suite_runtime_authority(
    canonical_skill_root: Path,
) -> dict[str, dict[str, Any]]:
    return {
        member_id: _runtime_authority_projection(member_root)
        for member_id, member_root, _installed_root in _suite_member_roots(
            canonical_skill_root, canonical_skill_root
        )
    }


def _safe_stage_path(stage_root: Path) -> Path:
    stage_root = stage_root.resolve()
    if stage_root.name != "skillguard" or stage_root.parent.name != "skills" or stage_root.parent.parent.name != ".codex":
        raise ValueError("stage root must end with .codex/skills/skillguard")
    return stage_root


def _suite_member_roots(
    canonical_skill_root: Path,
    installed_skill_root: Path,
) -> tuple[tuple[str, Path, Path], ...]:
    canonical_skill_root = canonical_skill_root.resolve()
    installed_skill_root = installed_skill_root.resolve()
    if not canonical_skill_root.joinpath(RUNTIME_SENTINEL).is_file():
        raise FileNotFoundError(
            f"required SkillGuard runtime sentinel is missing: {canonical_skill_root / RUNTIME_SENTINEL}"
        )
    canonical_router = canonical_skill_root.parent / GLOBAL_ROUTER_MEMBER
    if not canonical_router.is_dir():
        raise FileNotFoundError(
            f"required sibling {GLOBAL_ROUTER_MEMBER} is missing: {canonical_router}"
        )
    members: list[tuple[str, Path, Path]] = [
        ("skillguard", canonical_skill_root, installed_skill_root)
    ]
    members.append(
        (
            GLOBAL_ROUTER_MEMBER,
            canonical_router.resolve(),
            (installed_skill_root.parent / GLOBAL_ROUTER_MEMBER).resolve(),
        )
    )
    return tuple(members)


def _assert_suite_roots_disjoint(
    canonical_skill_root: Path,
    stage_root: Path,
    active_root: Path | None = None,
) -> None:
    roles: list[tuple[str, Path]] = [
        ("canonical:skillguard", canonical_skill_root.resolve()),
        (
            f"canonical:{GLOBAL_ROUTER_MEMBER}",
            (canonical_skill_root.parent / GLOBAL_ROUTER_MEMBER).resolve(),
        ),
        ("stage:skillguard", stage_root.resolve()),
        (f"stage:{GLOBAL_ROUTER_MEMBER}", (stage_root.parent / GLOBAL_ROUTER_MEMBER).resolve()),
    ]
    if active_root is not None:
        roles.extend(
            [
                ("active:skillguard", active_root.resolve()),
                (
                    f"active:{GLOBAL_ROUTER_MEMBER}",
                    (active_root.parent / GLOBAL_ROUTER_MEMBER).resolve(),
                ),
            ]
        )
    for index, (left_role, left) in enumerate(roles):
        for right_role, right in roles[index + 1 :]:
            if left == right or left.is_relative_to(right) or right.is_relative_to(left):
                raise ValueError(f"suite root overlap: {left_role} vs {right_role}")


def _stage_path_budget(
    canonical_skill_root: Path,
    stage_root: Path,
) -> dict[str, Any]:
    """Preflight portable Windows destination lengths without creating the stage."""

    stage_root = stage_root.resolve()
    file_rows: list[dict[str, Any]] = []
    directory_rows: dict[tuple[str, str], dict[str, Any]] = {}
    for member_id, canonical_root, installed_root in _suite_member_roots(
        canonical_skill_root,
        stage_root,
    ):
        for relative_text in installation_member_paths(canonical_root):
            relative = Path(relative_text)
            projected = installed_root / relative
            file_rows.append(
                {
                    "member_id": member_id,
                    "relative_path": relative.as_posix(),
                    "projected_length": len(str(projected)),
                }
            )
            parent = relative.parent
            while parent != Path("."):
                key = (member_id, parent.as_posix())
                directory_rows[key] = {
                    "member_id": member_id,
                    "relative_path": parent.as_posix(),
                    "projected_length": len(str(installed_root / parent)),
                }
                parent = parent.parent
        directory_rows[(member_id, ".")] = {
            "member_id": member_id,
            "relative_path": ".",
            "projected_length": len(str(installed_root)),
        }

    longest_file = max(
        file_rows,
        key=lambda row: (int(row["projected_length"]), str(row["relative_path"])),
        default={"member_id": "", "relative_path": "", "projected_length": 0},
    )
    longest_directory = max(
        directory_rows.values(),
        key=lambda row: (int(row["projected_length"]), str(row["relative_path"])),
        default={"member_id": "", "relative_path": "", "projected_length": 0},
    )
    blockers: list[str] = []
    if WINDOWS_PATH_BUDGET_ENABLED:
        if int(longest_file["projected_length"]) > WINDOWS_STAGE_FILE_PATH_LIMIT:
            blockers.append("staged_projected_file_path_too_long")
        if (
            int(longest_directory["projected_length"])
            > WINDOWS_STAGE_DIRECTORY_PATH_LIMIT
        ):
            blockers.append("staged_projected_directory_path_too_long")
    excess = max(
        0,
        int(longest_file["projected_length"]) - WINDOWS_STAGE_FILE_PATH_LIMIT,
        int(longest_directory["projected_length"])
        - WINDOWS_STAGE_DIRECTORY_PATH_LIMIT,
    )
    return {
        "artifact_type": "skillguard_stage_path_budget",
        "schema_version": "skillguard.stage_path_budget.v1",
        "status": "blocked" if blockers else "passed",
        "platform_policy": (
            "windows_portable_path_budget"
            if WINDOWS_PATH_BUDGET_ENABLED
            else "not_applicable"
        ),
        "stage_path_token": "staged_codex_home/.codex/skills/skillguard",
        "stage_root_length": len(str(stage_root)),
        "file_path_limit": WINDOWS_STAGE_FILE_PATH_LIMIT,
        "directory_path_limit": WINDOWS_STAGE_DIRECTORY_PATH_LIMIT,
        "longest_file": longest_file,
        "longest_directory": longest_directory,
        "recommended_max_stage_root_length": max(1, len(str(stage_root)) - excess),
        "blockers": blockers,
        "claim_boundary": (
            "This preflight projects portable destination lengths before stage mutation. "
            "It reports only member ids, relative paths, and lengths; it does not prove copy, "
            "parity, smoke, activation, or live installation."
        ),
    }


def _copy_stage_members(
    members: tuple[tuple[str, Path, Path], ...],
) -> dict[str, Any]:
    """Copy a new suite stage and remove every new member after a copy failure."""

    failed_member_id = ""
    try:
        for member_id, source_root, installed_root in members:
            failed_member_id = member_id
            installed_root.mkdir(parents=True, exist_ok=False)
            for relative_text in installation_member_paths(source_root):
                relative = Path(*relative_text.split("/"))
                source = source_root / relative
                destination = installed_root / relative
                if source.is_symlink() or not source.is_file():
                    raise ValueError(
                        f"installation projection member unavailable: {relative_text}"
                    )
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
    except (OSError, shutil.Error, ValueError) as exc:
        cleanup_failures: list[str] = []
        for member_id, _source_root, installed_root in reversed(members):
            if not _path_entity_exists(installed_root):
                continue
            try:
                shutil.rmtree(installed_root)
            except OSError:
                cleanup_failures.append(member_id)
        blockers = ["staged_copy_failed"]
        if cleanup_failures:
            blockers.append("staged_copy_cleanup_failed")
        return {
            "artifact_type": "skillguard_stage_copy_result",
            "status": "blocked",
            "failed_member_id": failed_member_id,
            "copy_error_kind": type(exc).__name__,
            "cleanup_status": "blocked" if cleanup_failures else "passed",
            "cleanup_failed_member_ids": sorted(cleanup_failures),
            "blockers": blockers,
            "claim_boundary": (
                "A failed stage copy has no activation authority. Cleanup covers only the "
                "new exact suite-member roots and does not mutate the active install."
            ),
        }
    return {
        "artifact_type": "skillguard_stage_copy_result",
        "status": "passed",
        "failed_member_id": "",
        "copy_error_kind": "",
        "cleanup_status": "not_required",
        "cleanup_failed_member_ids": [],
        "blockers": [],
        "claim_boundary": "Copy completion does not prove stage parity, smoke, or activation.",
    }


def compare_installation_projection_member(
    canonical_member_root: Path,
    installed_member_root: Path,
) -> dict[str, Any]:
    """Compare only one member's declared installation projection.

    The result deliberately excludes source-only tests, models, notes, receipts,
    logs, and timestamps.  Those files may be useful elsewhere, but they are not
    inputs to installed-content currentness and therefore cannot invalidate it.
    """

    canonical_root = canonical_member_root.resolve(strict=True)
    installed_root = installed_member_root.resolve()
    declared_paths = installation_member_paths(canonical_root)
    canonical_manifest = {
        path: impact_file_hash(canonical_root / Path(*path.split("/")))
        for path in declared_paths
    }
    installed_manifest: dict[str, str] = {}
    missing: list[str] = []
    changed: list[str] = []
    if installed_root.is_dir():
        for path in declared_paths:
            candidate = installed_root / Path(*path.split("/"))
            if candidate.is_symlink() or not candidate.is_file():
                missing.append(path)
                continue
            actual_hash = impact_file_hash(candidate)
            installed_manifest[path] = actual_hash
            if actual_hash != canonical_manifest[path]:
                changed.append(path)
        installed_portable = {
            relative.as_posix()
            for relative, _candidate in portable_files(installed_root)
        }
        unexpected = sorted(installed_portable - set(declared_paths))
    else:
        missing = list(declared_paths)
        unexpected = []
    canonical_projection_error = ""
    installed_projection_error = ""
    try:
        canonical_projection = installation_projection_identity(canonical_root)
    except (OSError, UnicodeError, ValueError) as exc:
        canonical_projection = None
        canonical_projection_error = str(exc)
    if installed_root.is_dir():
        try:
            installed_projection = installation_projection_identity(installed_root)
        except (OSError, UnicodeError, ValueError) as exc:
            installed_projection = None
            installed_projection_error = str(exc)
    else:
        installed_projection = None
        installed_projection_error = "installed_member_root_missing"
    projection_error = canonical_projection_error or installed_projection_error
    current = (
        not projection_error
        and canonical_projection == installed_projection
        and not missing
        and not changed
        and not unexpected
    )
    return {
        "projection_schema": INSTALLATION_PROJECTION_SCHEMA,
        "canonical_installation_projection": canonical_projection,
        "installed_installation_projection": installed_projection,
        "canonical_projection_error": canonical_projection_error,
        "installed_projection_error": installed_projection_error,
        "projection_error": projection_error,
        "canonical_file_hashes": dict(sorted(canonical_manifest.items())),
        "installed_file_hashes": dict(sorted(installed_manifest.items())),
        "missing_in_installed": sorted(missing),
        "changed_in_installed": sorted(changed),
        "unexpected_in_installed": unexpected,
        "status": "current" if current else "blocked",
        "claim_boundary": (
            "Parity covers only projection:installation. Source-only tests, models, "
            "notes, receipts, logs, and timestamps are outside install currentness."
        ),
    }


def _member_comparisons(
    canonical_skill_root: Path,
    installed_skill_root: Path,
) -> dict[str, dict[str, Any]]:
    comparisons: dict[str, dict[str, Any]] = {}
    for member_id, canonical_root, installed_root in _suite_member_roots(
        canonical_skill_root,
        installed_skill_root,
    ):
        comparison = compare_installation_projection_member(
            canonical_root,
            installed_root,
        )
        comparison["canonical_runtime_authority"] = resolve_runtime_authority(
            canonical_root
        ).to_dict()
        comparison["installed_runtime_authority"] = resolve_runtime_authority(
            installed_root
        ).to_dict()
        comparison["claim_boundary"] = (
            "Parity covers only projection:installation plus runtime authority; "
            "source-only tests, fixtures, models, notes, receipts, logs, and "
            "timestamps are outside install currentness."
        )
        comparisons[member_id] = comparison
    return comparisons


def _comparison_current(comparison: dict[str, Any]) -> bool:
    if any(
        comparison.get(key, [])
        for key in (
            "missing_in_installed",
            "changed_in_installed",
            "unexpected_in_installed",
        )
    ):
        return False
    if comparison.get("projection_error"):
        return False
    if (
        comparison.get("canonical_installation_projection")
        != comparison.get("installed_installation_projection")
    ):
        return False
    canonical_authority = comparison.get("canonical_runtime_authority")
    installed_authority = comparison.get("installed_runtime_authority")
    if not isinstance(canonical_authority, dict) or not isinstance(
        installed_authority, dict
    ):
        return False
    if _authority_blockers(canonical_authority) or _authority_blockers(
        installed_authority
    ):
        return False
    return all(
        canonical_authority.get(key) == installed_authority.get(key)
        for key in ("authority", "skill_id")
    )


def prepare_stage(canonical_skill_root: Path, stage_root: Path) -> dict[str, Any]:
    canonical_skill_root = canonical_skill_root.resolve()
    stage_root = _safe_stage_path(stage_root)
    _assert_suite_roots_disjoint(canonical_skill_root, stage_root)
    members = _suite_member_roots(canonical_skill_root, stage_root)
    existing_members = [str(installed) for _id, _source, installed in members if installed.exists()]
    if existing_members:
        raise FileExistsError(
            f"stage member already exists: {', '.join(existing_members)}"
        )
    runtime_authority = _canonical_suite_runtime_authority(canonical_skill_root)
    authority_blockers: list[str] = []
    for projection in runtime_authority.values():
        for code in _authority_blockers(projection):
            if code not in authority_blockers:
                authority_blockers.append(code)
    if authority_blockers:
        return {
            "artifact_type": "skillguard_stage_prepare_result",
            "status": "blocked",
            "stage_path_token": "staged_codex_home/.codex/skills/skillguard",
            "comparison": {},
            "member_comparisons": {},
            "staged_member_ids": [],
            "runtime_authority": runtime_authority,
            "path_budget": None,
            "copy": None,
            "blockers": [
                *authority_blockers,
                "canonical_runtime_authority_blocked",
            ],
            "claim_boundary": (
                "Canonical authority resolution blocked before path projection, stage creation, "
                "transient filtering, or copy."
            ),
        }
    portable_boundaries: dict[str, dict[str, object]] = {}
    portable_boundary_blockers: list[str] = []
    for member_id, source_root, _installed_root in members:
        boundary = scan_member_boundary(source_root)
        portable_boundaries[member_id] = boundary.to_dict()
        for path in boundary.blocking_runtime_paths:
            portable_boundary_blockers.append(
                f"canonical_runtime_artifact_present:{member_id}:{path}"
            )
        for path in boundary.unsafe_paths:
            portable_boundary_blockers.append(
                f"canonical_portable_path_unsafe:{member_id}:{path}"
            )
    if portable_boundary_blockers:
        return {
            "artifact_type": "skillguard_stage_prepare_result",
            "status": "blocked",
            "stage_path_token": "staged_codex_home/.codex/skills/skillguard",
            "comparison": {},
            "member_comparisons": {},
            "staged_member_ids": [],
            "runtime_authority": runtime_authority,
            "portable_content_policy_id": PORTABLE_CONTENT_POLICY_ID,
            "portable_content_boundaries": portable_boundaries,
            "path_budget": None,
            "copy": None,
            "blockers": sorted(set(portable_boundary_blockers)),
            "claim_boundary": (
                "The shared portable-content boundary blocked before path projection, "
                "stage creation, transient filtering, or copy."
            ),
        }
    path_budget = _stage_path_budget(canonical_skill_root, stage_root)
    if path_budget["status"] != "passed":
        return {
            "artifact_type": "skillguard_stage_prepare_result",
            "status": "blocked",
            "stage_path_token": "staged_codex_home/.codex/skills/skillguard",
            "comparison": {},
            "member_comparisons": {},
            "staged_member_ids": [],
            "runtime_authority": runtime_authority,
            "path_budget": path_budget,
            "copy": None,
            "blockers": list(path_budget["blockers"]),
            "claim_boundary": (
                "Stage path-budget preflight blocked before creating either suite member. "
                "Use a shorter isolated stage root and retry preparation."
            ),
        }
    _durable_mkdir(stage_root.parent)
    copy_result = _copy_stage_members(members)
    if copy_result["status"] != "passed":
        return {
            "artifact_type": "skillguard_stage_prepare_result",
            "status": "blocked",
            "stage_path_token": "staged_codex_home/.codex/skills/skillguard",
            "comparison": {},
            "member_comparisons": {},
            "staged_member_ids": [],
            "runtime_authority": runtime_authority,
            "path_budget": path_budget,
            "copy": copy_result,
            "blockers": list(copy_result["blockers"]),
            "claim_boundary": (
                "Stage copy failed and cannot authorize activation. Newly created suite-member "
                "roots were removed unless cleanup_failed_member_ids says otherwise."
            ),
        }
    member_comparisons = _member_comparisons(canonical_skill_root, stage_root)
    comparison = member_comparisons["skillguard"]
    blockers = []
    if not _comparison_current(comparison):
        blockers.append("staged_source_parity_failed")
    if any(not _comparison_current(value) for value in member_comparisons.values()):
        blockers.append("staged_suite_member_parity_failed")
    return {
        "artifact_type": "skillguard_stage_prepare_result",
        "status": "passed" if not blockers else "blocked",
        "stage_path_token": "staged_codex_home/.codex/skills/skillguard",
        "comparison": comparison,
        "member_comparisons": member_comparisons,
        "staged_member_ids": list(member_comparisons),
        "runtime_authority": runtime_authority,
        "portable_content_policy_id": PORTABLE_CONTENT_POLICY_ID,
        "portable_content_boundaries": portable_boundaries,
        "path_budget": path_budget,
        "copy": copy_result,
        "blockers": blockers,
        "claim_boundary": "Stage preparation copies only each member's declared installation projection; it does not activate the user install.",
    }


def _run(command: list[str], cwd: Path, timeout: float) -> dict[str, Any]:
    started = time.monotonic()
    timed_out = False
    with tempfile.TemporaryFile(mode="w+b") as stdout_file, tempfile.TemporaryFile(
        mode="w+b"
    ) as stderr_file:
        try:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=stdout_file,
                stderr=stderr_file,
                shell=False,
                **isolated_process_kwargs(),
            )
            containment = attach_process_tree_containment(process)
        except OSError as exc:
            return {
                "status": "failed",
                "exit_code": None,
                "stdout_tail": "",
                "stderr_tail": str(exc)[-2000:],
                "cleanup_confirmed": False,
                "termination_method": "launch_error",
                "termination_error_kind": type(exc).__name__,
            }
        while process.poll() is None:
            if time.monotonic() - started >= timeout:
                timed_out = True
                break
            time.sleep(0.05)
        termination = dict(
            release_process_tree_containment(
                process,
                containment,
                timed_out=timed_out,
            )
        )
        stdout_file.seek(0)
        stderr_file.seek(0)
        stdout = stdout_file.read().decode("utf-8", errors="replace")
        stderr = stderr_file.read().decode("utf-8", errors="replace")
    cleanup_confirmed = termination.get("cleanup_confirmed") is True
    status = (
        "timed_out"
        if timed_out
        else "passed"
        if process.returncode == 0 and cleanup_confirmed
        else "failed"
    )
    return {
        "status": status,
        "exit_code": process.returncode,
        "stdout_tail": stdout[-2000:],
        "stderr_tail": stderr[-2000:],
        **termination,
    }


def _installed_smoke_plan(
    installed_skill_root: Path,
    *,
    active_installation_currentness: bool,
) -> tuple[Path, list[dict[str, Any]]]:
    installed_skill_root = _safe_stage_path(installed_skill_root)
    layout_root = installed_skill_root.parents[2]
    relative_skill = installed_skill_root.relative_to(layout_root).as_posix()
    script = installed_skill_root / "scripts" / "skillguard.py"
    v2_script_root = installed_skill_root / "scripts"
    installed_members = (
        ("skillguard", installed_skill_root),
        (
            GLOBAL_ROUTER_MEMBER,
            installed_skill_root.parent / GLOBAL_ROUTER_MEMBER,
        ),
    )
    runtime_fingerprint_function = (
        "guard_active_installation_runtime_fingerprint"
        if active_installation_currentness
        else "guard_runtime_fingerprint"
    )
    checks: list[dict[str, Any]] = [
        {
            "check_id": f"installed:runtime-authority:{member_id}",
            "command": [
                sys.executable,
                "-c",
                (
                    "import json, sys; from pathlib import Path; "
                    f"sys.path.insert(0, {str(v2_script_root)!r}); "
                    "from skillguard_v2.runtime_authority import resolve_runtime_authority; "
                    f"decision = resolve_runtime_authority(Path({str(member_root)!r})); "
                    "print(json.dumps(decision.to_dict(), sort_keys=True)); "
                    "raise SystemExit(0 if decision.ok else 1)"
                ),
            ],
        }
        for member_id, member_root in installed_members
    ] + [
        {
            "check_id": f"installed:check-contract:{member_id}",
            "command": [
                sys.executable,
                str(script),
                "check-contract",
                "--repository-root",
                str(layout_root),
                "--target",
                member_root.relative_to(layout_root).as_posix(),
            ],
        }
        for member_id, member_root in installed_members
    ] + [
        {
            "check_id": "installed:commands",
            "command": [sys.executable, str(script), "commands"],
        },
        {
            "check_id": "installed:self-check",
            "command": [sys.executable, str(script), "self-check", "--target", relative_skill],
        },
        {
            "check_id": "installed:check-skill",
            "command": [sys.executable, str(script), "check-skill", "--target", relative_skill],
        },
        {
            "check_id": "installed:runtime-import",
            "command": [
                sys.executable,
                "-c",
                (
                    "import sys; "
                    f"sys.path.insert(0, {str(v2_script_root)!r}); "
                    "from skillguard_v2.runtime_fingerprint import "
                    f"{runtime_fingerprint_function}; "
                    f"assert {runtime_fingerprint_function}()['file_count'] >= 1"
                ),
            ],
        },
    ]
    return layout_root, checks


def _installed_smoke_command_environment_identity(
    installed_skill_root: Path,
    *,
    active_installation_currentness: bool,
) -> dict[str, str]:
    _layout_root, checks = _installed_smoke_plan(
        installed_skill_root,
        active_installation_currentness=active_installation_currentness,
    )
    command_projection = [
        {
            "check_id": str(check["check_id"]),
            "command": [str(part) for part in check["command"]],
        }
        for check in checks
    ]
    environment_projection = {
        "python_executable": str(Path(sys.executable).resolve()),
        "python_implementation": sys.implementation.name,
        "python_version": list(sys.version_info[:3]),
        "platform": sys.platform,
        "os_name": os.name,
        "selected_environment": {
            name: os.environ.get(name)
            for name in ("PYTHONHASHSEED", "PYTHONPATH", "VIRTUAL_ENV")
        },
        "portable_projection_id": (
            ACTIVE_INSTALLATION_CURRENTNESS_PROJECTION_ID
            if active_installation_currentness
            else PORTABLE_CONTENT_POLICY_ID
        ),
    }
    return {
        "command_fingerprint": canonical_hash(command_projection),
        "environment_fingerprint": canonical_hash(environment_projection),
    }


def smoke_installed_skill(
    installed_skill_root: Path,
    *,
    timeout_seconds: float = 120,
    active_installation_currentness: bool = False,
) -> dict[str, Any]:
    layout_root, checks = _installed_smoke_plan(
        installed_skill_root,
        active_installation_currentness=active_installation_currentness,
    )
    results = []
    for check in checks:
        result = _run(check["command"], layout_root, timeout_seconds)
        result["check_id"] = check["check_id"]
        results.append(result)
        if result["status"] != "passed":
            break
    return {
        "artifact_type": "skillguard_installed_smoke_result",
        "status": "passed" if len(results) == len(checks) and all(row["status"] == "passed" for row in results) else "failed",
        "checks": results,
        "skipped_checks": [row["check_id"] for row in checks[len(results) :]],
        "claim_boundary": "Installed smoke proves both suite members resolve current authority before command dispatch, self-check, and runtime import. It does not prove target execution depth or publication.",
    }


def replay_installed_smoke_currentness(
    installed_skill_root: Path,
    *,
    recorded_smoke: Mapping[str, Any],
) -> dict[str, Any]:
    """Recompute current bindings around an already-executed installation smoke.

    This function is deliberately process-free.  Installation owns the one
    smoke execution; every later currentness consumer validates that immutable
    result together with current source, command, and environment identities.
    """

    _layout_root, expected_checks = _installed_smoke_plan(
        installed_skill_root,
        active_installation_currentness=True,
    )
    expected_ids = [str(row["check_id"]) for row in expected_checks]
    recorded_checks = recorded_smoke.get("checks")
    if (
        recorded_smoke.get("status") != "passed"
        or recorded_smoke.get("skipped_checks") != []
        or not isinstance(recorded_checks, list)
        or [str(row.get("check_id", "")) for row in recorded_checks] != expected_ids
        or any(
            not isinstance(row, Mapping)
            or row.get("status") != "passed"
            or row.get("exit_code") != 0
            for row in recorded_checks
        )
    ):
        return {
            "artifact_type": "skillguard_installed_smoke_currentness_projection",
            "status": "blocked",
            "blockers": ["recorded_installed_smoke_not_current"],
            "claim_boundary": (
                "Read-only currentness never executes missing or stale installation smoke."
            ),
        }
    identity = _installed_smoke_command_environment_identity(
        installed_skill_root,
        active_installation_currentness=True,
    )
    result_projection = {
        "status": recorded_smoke.get("status"),
        "checks": [
            {
                "check_id": str(row.get("check_id", "")),
                "status": str(row.get("status", "")),
                "exit_code": row.get("exit_code"),
            }
            for row in recorded_checks
            if isinstance(row, dict)
        ],
        "skipped_checks": list(recorded_smoke.get("skipped_checks", [])),
    }
    return {
        "artifact_type": "skillguard_installed_smoke_currentness_projection",
        "status": "passed",
        "blockers": [],
        "current_installed_smoke_hash": canonical_hash(result_projection),
        "current_installed_smoke_command_fingerprint": identity[
            "command_fingerprint"
        ],
        "current_installed_smoke_environment_fingerprint": identity[
            "environment_fingerprint"
        ],
        "smoke": dict(recorded_smoke),
        "claim_boundary": (
            "This read-only projection verifies the installation-owned smoke result and "
            "its current command/environment identity without starting a process. It does "
            "not authorize historical transactions or prove external target behavior."
        ),
    }


def verify_stage(canonical_skill_root: Path, stage_root: Path) -> dict[str, Any]:
    canonical_skill_root = canonical_skill_root.resolve()
    stage_root = _safe_stage_path(stage_root)
    _assert_suite_roots_disjoint(canonical_skill_root, stage_root)
    member_comparisons = _member_comparisons(
        canonical_skill_root, stage_root
    )
    canonical_projection_roots = {
        member_id: canonical_root
        for member_id, canonical_root, _active_root in _suite_member_roots(
            canonical_skill_root, stage_root
        )
    }
    staged_projection_roots = {
        member_id: staged_root
        for member_id, _canonical_root, staged_root in _suite_member_roots(
            canonical_skill_root, stage_root
        )
    }
    canonical_installation_projections = {
        member_id: member_comparisons[member_id].get(
            "canonical_installation_projection"
        )
        for member_id in canonical_projection_roots
    }
    stage_installation_projections = {
        member_id: member_comparisons[member_id].get(
            "installed_installation_projection"
        )
        for member_id in staged_projection_roots
    }
    comparison = member_comparisons["skillguard"]
    parity = all(
        _comparison_current(value) for value in member_comparisons.values()
    )
    smoke = smoke_installed_skill(stage_root)
    blockers = []
    if not parity:
        blockers.append("staged_source_parity_failed")
        blockers.append("staged_suite_member_parity_failed")
    if smoke["status"] != "passed":
        blockers.append("staged_installed_smoke_failed")
    if canonical_installation_projections != stage_installation_projections:
        blockers.append("staged_installation_projection_mismatch")
    return {
        "artifact_type": "skillguard_stage_verification",
        "status": "passed" if not blockers else "blocked",
        "comparison": comparison,
        "member_comparisons": member_comparisons,
        "canonical_installation_projections": canonical_installation_projections,
        "stage_installation_projections": stage_installation_projections,
        "smoke": smoke,
        "blockers": blockers,
        "claim_boundary": "Stage verification does not activate or mutate the current user install.",
    }


def _revalidate_stage_without_execution(
    canonical_skill_root: Path,
    stage_root: Path,
    verification: Mapping[str, Any],
) -> dict[str, Any]:
    """Rehash a previously verified stage without starting its smoke owner."""

    member_comparisons = _member_comparisons(canonical_skill_root, stage_root)
    canonical_roots = {
        member_id: canonical_root
        for member_id, canonical_root, _active_root in _suite_member_roots(
            canonical_skill_root, stage_root
        )
    }
    stage_roots = {
        member_id: staged_root
        for member_id, _canonical_root, staged_root in _suite_member_roots(
            canonical_skill_root, stage_root
        )
    }
    canonical_projections = {
        member_id: installation_projection_identity(root)
        for member_id, root in canonical_roots.items()
    }
    stage_projections = {
        member_id: installation_projection_identity(root)
        for member_id, root in stage_roots.items()
    }
    member_order = ["skillguard", GLOBAL_ROUTER_MEMBER]
    blockers: list[str] = []
    if verification.get("status") != "passed":
        blockers.append("stage_verification_not_passed")
    if not _installed_smoke_evidence_complete(
        verification.get("smoke"), member_order
    ):
        blockers.append("stage_smoke_receipt_invalid")
    if verification.get("member_comparisons") != member_comparisons:
        blockers.append("stage_member_comparison_changed")
    if verification.get("canonical_installation_projections") != canonical_projections:
        blockers.append("canonical_installation_projection_changed")
    if verification.get("stage_installation_projections") != stage_projections:
        blockers.append("stage_installation_projection_changed")
    if any(not _comparison_current(value) for value in member_comparisons.values()):
        blockers.append("stage_member_parity_failed")
    if canonical_projections != stage_projections:
        blockers.append("stage_installation_projection_mismatch")
    return {
        "artifact_type": "skillguard_stage_readonly_revalidation",
        "status": "passed" if not blockers else "blocked",
        "blockers": blockers,
        "member_comparisons": member_comparisons,
        "canonical_installation_projections": canonical_projections,
        "stage_installation_projections": stage_projections,
        "execution_count": 0,
        "claim_boundary": (
            "This operation only rehashes the frozen stage and consumes the existing "
            "stage smoke evidence; it never starts a smoke command."
        ),
    }


def _quarantine_path(
    path: Path,
    codex_home: Path,
    transaction_id: str,
    label: str,
) -> str | None:
    if not path.exists():
        return None
    short_transaction = transaction_id.removeprefix("install-")[:8]
    safe_label = re.sub(r"[^a-zA-Z0-9_.-]+", "-", label).strip("-._")[:24] or "candidate"
    destination_root = codex_home / "backups" / "failed" / short_transaction
    _durable_mkdir(destination_root)
    destination = destination_root / f"{safe_label}-{uuid.uuid4().hex[:8]}"
    _durable_rename(path, destination)
    return str(destination.resolve())


def _restore_transaction_locked(
    codex_home: Path,
    record: dict[str, Any],
    *,
    terminal_status: str,
    reason: str,
) -> dict[str, Any]:
    members = record["members"]
    member_order = [str(value) for value in record.get("member_order", [])]
    if member_order != ["skillguard", GLOBAL_ROUTER_MEMBER]:
        return {
            "status": "blocked",
            "blockers": ["transaction_member_order_invalid"],
            "transaction_id": record.get("transaction_id"),
        }
    blockers: list[str] = []
    for member_id in member_order:
        member = members[member_id]
        active_root = Path(member["active_root"])
        backup_root = Path(member["backup_root"])
        previous_identity = member["previous_identity"]
        if bool(previous_identity.get("exists")):
            if backup_root.exists():
                if not _identity_matches(
                    backup_root,
                    previous_identity,
                    active_installation_currentness=True,
                ):
                    blockers.append(f"backup_identity_mismatch:{member_id}")
            elif not _identity_matches(
                active_root,
                previous_identity,
                active_installation_currentness=True,
            ):
                blockers.append(f"previous_source_unrecoverable:{member_id}")
        elif backup_root.exists():
            blockers.append(f"unexpected_backup_for_absent_member:{member_id}")
    if blockers:
        record["status"] = "recovery_blocked"
        record["phase"] = "recovery_preflight_blocked"
        record["recovery_blockers"] = blockers
        _persist_transaction(codex_home, record)
        return {
            "status": "blocked",
            "blockers": blockers,
            "transaction_id": record["transaction_id"],
            "journal_path": str(_journal_path(codex_home, record["transaction_id"])),
        }

    record["status"] = "rollback_in_progress"
    record["phase"] = "restore_pending"
    record["restore_reason"] = reason
    _persist_transaction(codex_home, record)
    quarantined: dict[str, list[str]] = {member_id: [] for member_id in member_order}
    for member_id in reversed(member_order):
        member = members[member_id]
        active_root = Path(member["active_root"])
        incoming_root = Path(member["incoming_root"])
        backup_root = Path(member["backup_root"])
        previous_identity = member["previous_identity"]
        record["phase"] = f"restore_pending:{member_id}"
        _persist_transaction(codex_home, record)
        _maybe_failpoint(f"restore:{member_id}:before")
        if backup_root.exists():
            quarantined_path = _quarantine_path(
                active_root,
                codex_home,
                record["transaction_id"],
                f"failed-active-{member_id}",
            )
            if quarantined_path:
                quarantined[member_id].append(quarantined_path)
            _durable_rename(backup_root, active_root)
        elif not bool(previous_identity.get("exists")):
            quarantined_path = _quarantine_path(
                active_root,
                codex_home,
                record["transaction_id"],
                f"new-active-{member_id}",
            )
            if quarantined_path:
                quarantined[member_id].append(quarantined_path)
        quarantined_path = _quarantine_path(
            incoming_root,
            codex_home,
            record["transaction_id"],
            f"pending-incoming-{member_id}",
        )
        if quarantined_path:
            quarantined[member_id].append(quarantined_path)
        member["restored_identity"] = _source_identity(
            active_root,
            active_installation_currentness=True,
        )
        _maybe_failpoint(f"restore:{member_id}:after")
        record["phase"] = f"restored:{member_id}"
        _persist_transaction(codex_home, record)

    restore_failures = [
        member_id
        for member_id in member_order
        if not _identity_matches(
            Path(members[member_id]["active_root"]),
            members[member_id]["previous_identity"],
            active_installation_currentness=True,
        )
    ]
    restore_status = "passed" if not restore_failures else "failed"
    receipt_path = _receipt_path(
        codex_home,
        record["transaction_id"],
        terminal_status.replace("_", "-"),
    )
    intended_status = terminal_status if not restore_failures else "recovery_failed"
    record["status"] = "recovery_receipt_pending"
    record["phase"] = (
        "recovery_receipt_pending"
        if not restore_failures
        else "failed_recovery_receipt_pending"
    )
    record["intended_recovery_terminal_status"] = intended_status
    record["quarantined_roots"] = quarantined
    record["restore_verification"] = {
        "status": restore_status,
        "failed_member_ids": restore_failures,
        "member_identities": {
            member_id: _source_identity(
                Path(members[member_id]["active_root"]),
                active_installation_currentness=True,
            )
            for member_id in member_order
        },
    }
    record["recovery_receipt_path"] = str(receipt_path.resolve())
    journal_path = _persist_transaction(codex_home, record)
    recovery_verification_journal_hash = record["journal_hash"]
    try:
        receipt = _write_receipt(
            receipt_path,
            {
                "schema_version": "skillguard.install_recovery_receipt.v1",
                "artifact_type": "skillguard_install_recovery_receipt",
                "status": restore_status,
                "transaction_id": record["transaction_id"],
                "terminal_status": intended_status,
                "reason": reason,
                "journal_hash": recovery_verification_journal_hash,
                "restored_member_ids": member_order if not restore_failures else [],
                "restored_identities": record["restore_verification"]["member_identities"],
                "quarantined_roots": quarantined,
                "created_at": _utc_now(),
                "claim_boundary": (
                    "This receipt proves only the exact local member identities restored "
                    "when the transaction journal subsequently records its hash and intended "
                    "terminal status."
                ),
            },
        )
        _maybe_failpoint("recovery_receipt:after")
    except OSError as exc:
        record["recovery_receipt_error"] = type(exc).__name__
        journal_path = _persist_transaction(codex_home, record)
        return {
            "artifact_type": "skillguard_install_recovery",
            "status": "blocked",
            "transaction_id": record["transaction_id"],
            "journal_path": str(journal_path.resolve()),
            "receipt_path": str(receipt_path.resolve()),
            "backup_roots": {
                member_id: members[member_id]["backup_root"] for member_id in member_order
            },
            "restore_verification": record["restore_verification"],
            "quarantined_roots": quarantined,
            "blockers": ["recovery_receipt_write_failed"],
        }
    record["recovery_verification_journal_hash"] = recovery_verification_journal_hash
    record["recovery_receipt_hash"] = receipt["receipt_hash"]
    head_after_rollback = record.get("head_after_rollback")
    if isinstance(head_after_rollback, dict):
        record["status"] = "rollback_head_pending"
        record["phase"] = "rollback_head_pending"
        _persist_transaction(codex_home, record)
        updated_head = _write_install_head(
            codex_home,
            transaction_id=head_after_rollback.get("transaction_id"),
            previous_transaction_id=head_after_rollback.get(
                "previous_transaction_id"
            ),
            generation=int(head_after_rollback.get("generation", 0)),
        )
        _maybe_failpoint("rollback_head:after")
        record["rollback_head_hash"] = updated_head["head_hash"]
    record["status"] = intended_status
    record["phase"] = "restored" if not restore_failures else "restore_verification_failed"
    journal_path = _persist_transaction(codex_home, record)
    _maybe_failpoint("recovery_terminal_journal:after")
    return {
        "artifact_type": "skillguard_install_recovery",
        "status": terminal_status if not restore_failures else "failed",
        "transaction_id": record["transaction_id"],
        "journal_path": str(journal_path.resolve()),
        "receipt_path": str(receipt_path.resolve()),
        "receipt_hash": receipt["receipt_hash"],
        "backup_roots": {
            member_id: members[member_id]["backup_root"] for member_id in member_order
        },
        "restore_verification": record["restore_verification"],
        "quarantined_roots": quarantined,
        "blockers": (
            [] if not restore_failures else ["restore_identity_verification_failed"]
        ),
    }


def _recover_incomplete_installations_locked(
    codex_home: Path,
    *,
    allow_replacement_only_head: bool = False,
) -> dict[str, Any]:
    transaction_root = _transaction_root(codex_home)
    if not transaction_root.is_dir():
        return {
            "artifact_type": "skillguard_install_recovery_scan",
            "status": "passed",
            "recovered_transaction_ids": [],
            "reports": [],
            "blockers": [],
        }
    reports: list[dict[str, Any]] = []
    blockers: list[str] = []
    records: dict[str, dict[str, Any]] = {}
    for path in sorted(transaction_root.glob("install-*.json")):
        transaction_id = path.stem
        try:
            records[transaction_id] = _load_transaction(codex_home, transaction_id)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            blockers.append(
                f"invalid_transaction_journal:{transaction_id}:{type(exc).__name__}"
            )
    try:
        install_head = _load_install_head(codex_home)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        blockers.append(f"invalid_install_head:{type(exc).__name__}")
        install_head = _empty_install_head()

    for transaction_id, record in records.items():
        previous_id = record.get("previous_committed_transaction_id")
        generation = int(record.get("generation", -1))
        if generation < 1:
            blockers.append(f"invalid_transaction_generation:{transaction_id}")
        if previous_id is not None:
            previous = records.get(str(previous_id))
            if previous is None:
                blockers.append(f"missing_previous_transaction:{transaction_id}")
            elif int(previous.get("generation", -1)) >= generation:
                blockers.append(f"non_monotonic_transaction_chain:{transaction_id}")

    head_id = install_head.get("transaction_id")
    committed_ids = {
        transaction_id
        for transaction_id, record in records.items()
        if record.get("status") in {"committed", "commit_head_pending"}
    }
    if head_id is None and committed_ids:
        blockers.append("committed_transaction_without_install_head")
    elif head_id is not None:
        head_record = records.get(str(head_id))
        if head_record is None:
            blockers.append("install_head_target_missing")
        elif int(head_record.get("generation", -1)) != int(
            install_head.get("generation", -2)
        ):
            blockers.append("install_head_generation_mismatch")

    if blockers:
        return {
            "artifact_type": "skillguard_install_recovery_scan",
            "status": "blocked",
            "recovered_transaction_ids": [],
            "reports": [],
            "blockers": blockers,
            "claim_boundary": (
                "No recovery mutation occurred because the complete journal inventory or "
                "durable transaction chain was invalid."
            ),
        }

    plans: list[tuple[int, str, str, str]] = []
    former_terminal_record_ids: list[str] = []
    for transaction_id, record in records.items():
        status = str(record.get("status", ""))
        generation = int(record.get("generation", 0))
        if (
            allow_replacement_only_head
            and head_id == transaction_id
            and status == "recovery_blocked"
            and record.get("phase") == "recovery_preflight_blocked"
            and _activation_receipt_active_replacement_eligible(record)
        ):
            record["status"] = "committed"
            record["phase"] = "committed"
            record["replacement_recovery_provenance"] = {
                "recovery_kind": "restore_historical_commit_for_replacement",
                "recovered_from_status": "recovery_blocked",
                "recovered_from_phase": "recovery_preflight_blocked",
                "recovered_at": _utc_now(),
            }
            record.pop("recovery_blockers", None)
            journal_path = _persist_transaction(codex_home, record)
            reports.append(
                {
                    "status": "committed",
                    "transaction_id": transaction_id,
                    "journal_path": str(journal_path),
                    "recovery_kind": (
                        "restore_historical_commit_for_replacement"
                    ),
                    "blockers": [],
                }
            )
            status = "committed"
        if (
            status in TERMINAL_TRANSACTION_STATUSES
            and not _terminal_record_uses_current_projection(record)
        ):
            former_terminal_record_ids.append(transaction_id)
            continue
        if status == "commit_head_pending":
            active_current = all(
                _identity_matches(
                    Path(record["members"][member_id]["active_root"]),
                    record["members"][member_id]["installed_identity"],
                    active_installation_currentness=True,
                )
                for member_id in record["member_order"]
            )
            if (
                head_id == transaction_id
                and (
                    _activation_receipt_active_current(record)
                )
                and active_current
            ):
                plans.append((generation, transaction_id, "finalize_commit", "committed"))
                continue
            if head_id == transaction_id:
                previous_id = record.get("previous_committed_transaction_id")
                previous_record = records.get(str(previous_id)) if previous_id else None
                record["head_after_rollback"] = {
                    "transaction_id": previous_id,
                    "previous_transaction_id": (
                        previous_record.get("previous_committed_transaction_id")
                        if previous_record
                        else None
                    ),
                    "generation": int(previous_record.get("generation", 0))
                    if previous_record
                    else 0,
                }
            plans.append(
                (generation, transaction_id, "restore", "recovered_rolled_back")
            )
        elif status == "committed":
            if head_id != transaction_id:
                if _hardened_activation_receipt_historical_integrity(record):
                    continue
                blockers.append(f"non_head_committed_receipt_invalid:{transaction_id}")
                continue
            if _activation_receipt_active_recoverable(record):
                continue
            if (
                allow_replacement_only_head
                and _activation_receipt_active_replacement_eligible(record)
            ):
                continue
            previous_id = record.get("previous_committed_transaction_id")
            previous_record = records.get(str(previous_id)) if previous_id else None
            record["head_after_rollback"] = {
                "transaction_id": previous_id,
                "previous_transaction_id": (
                    previous_record.get("previous_committed_transaction_id")
                    if previous_record
                    else None
                ),
                "generation": int(previous_record.get("generation", 0))
                if previous_record
                else 0,
            }
            plans.append(
                (generation, transaction_id, "restore", "recovered_rolled_back")
            )
        elif status in {"rolled_back", "recovered_rolled_back", "manually_rolled_back"}:
            if not _recovery_receipt_current(record):
                plans.append((generation, transaction_id, "restore", status))
        elif status in TERMINAL_TRANSACTION_STATUSES:
            continue
        else:
            if head_id == transaction_id:
                previous_id = record.get("previous_committed_transaction_id")
                previous_record = records.get(str(previous_id)) if previous_id else None
                record["head_after_rollback"] = {
                    "transaction_id": previous_id,
                    "previous_transaction_id": (
                        previous_record.get("previous_committed_transaction_id")
                        if previous_record
                        else None
                    ),
                    "generation": int(previous_record.get("generation", 0))
                    if previous_record
                    else 0,
                }
            plans.append(
                (generation, transaction_id, "restore", "recovered_rolled_back")
            )

    if blockers:
        return {
            "artifact_type": "skillguard_install_recovery_scan",
            "status": "blocked",
            "recovered_transaction_ids": [],
            "reports": [],
            "blockers": blockers,
            "claim_boundary": "No recovery mutation occurred because terminal evidence was inconsistent.",
        }

    for _generation, transaction_id, action, target_terminal_status in sorted(
        plans, reverse=True
    ):
        record = records[transaction_id]
        if action == "finalize_commit":
            recovered_from_phase = str(record.get("phase", ""))
            record["install_head_hash"] = install_head.get("head_hash")
            record["status"] = "committed"
            record["phase"] = "committed"
            record["recovery_provenance"] = {
                "recovery_kind": "commit_head_finalize",
                "recovered_from_status": "commit_head_pending",
                "recovered_from_phase": recovered_from_phase,
                "install_head_hash": str(install_head.get("head_hash", "")),
                "recovered_at": _utc_now(),
            }
            journal_path = _persist_transaction(codex_home, record)
            reports.append(
                {
                    "artifact_type": "skillguard_install_commit_recovery",
                    "status": "committed",
                    "transaction_id": transaction_id,
                    "journal_path": str(journal_path.resolve()),
                    "blockers": [],
                }
            )
            continue
        report = _restore_transaction_locked(
            codex_home,
            record,
            terminal_status=target_terminal_status,
            reason="incomplete_installation_recovered_on_next_entry",
        )
        reports.append(report)
        if report.get("status") != target_terminal_status:
            blockers.append(f"transaction_recovery_failed:{transaction_id}")
            break
    recovered_ids = [
        str(report["transaction_id"])
        for report in reports
        if report.get("status")
        in {"committed", "rolled_back", "recovered_rolled_back", "manually_rolled_back"}
    ]
    return {
        "artifact_type": "skillguard_install_recovery_scan",
        "status": "blocked" if blockers else "recovered" if recovered_ids else "passed",
        "recovered_transaction_ids": recovered_ids,
        "former_terminal_record_ids": sorted(former_terminal_record_ids),
        "reports": reports,
        "blockers": blockers,
        "claim_boundary": (
            "Recovery scans only durable SkillGuard installation journals under the "
            "named CODEX_HOME and restores exact pre-transaction member identities."
        ),
    }


def recover_incomplete_installations(codex_home: Path) -> dict[str, Any]:
    codex_home = codex_home.resolve()
    try:
        with _InstallMutex(codex_home, "recover"):
            return _recover_incomplete_installations_locked(codex_home)
    except InstallBusyError:
        return {
            "artifact_type": "skillguard_install_recovery_scan",
            "status": "blocked",
            "recovered_transaction_ids": [],
            "reports": [],
            "blockers": ["install_lock_busy"],
            "claim_boundary": "No recovery mutation occurred because another installer owns the mutex.",
        }
    except UnsafeInstallPathError as exc:
        return {
            "artifact_type": "skillguard_install_recovery_scan",
            "status": "blocked",
            "recovered_transaction_ids": [],
            "reports": [],
            "blockers": ["unsafe_codex_control_path"],
            "reason": str(exc),
            "claim_boundary": "No recovery mutation occurred.",
        }


def activate_stage(
    canonical_skill_root: Path,
    stage_root: Path,
    codex_home: Path,
    *,
    stage_verification: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    canonical_skill_root = canonical_skill_root.resolve()
    stage_root = _safe_stage_path(stage_root)
    codex_home = codex_home.resolve()
    try:
        _validate_codex_control_paths(codex_home)
    except UnsafeInstallPathError as exc:
        return {
            "artifact_type": "skillguard_install_activation",
            "status": "blocked",
            "blockers": ["unsafe_codex_control_path"],
            "reason": str(exc),
            "claim_boundary": "No stage or active install mutation occurred.",
        }
    for member_id in ("skillguard", GLOBAL_ROUTER_MEMBER):
        lexical_active = codex_home / "skills" / member_id
        if _path_entity_exists(lexical_active) and (
            _is_reparse_point(lexical_active) or not lexical_active.is_dir()
        ):
            return {
                "artifact_type": "skillguard_install_activation",
                "status": "blocked",
                "blockers": ["unsafe_active_suite_member_root"],
                "member_id": member_id,
                "claim_boundary": "No stage or active install mutation occurred.",
            }
    active = (codex_home / "skills" / "skillguard").resolve()
    _assert_suite_roots_disjoint(canonical_skill_root, stage_root, active)
    if (
        active == stage_root
        or stage_root.is_relative_to(active)
        or active.is_relative_to(stage_root)
    ):
        raise ValueError("stage and active roots must be distinct")
    verification = (
        dict(stage_verification)
        if stage_verification is not None
        else verify_stage(canonical_skill_root, stage_root)
    )
    stage_revalidation = _revalidate_stage_without_execution(
        canonical_skill_root,
        stage_root,
        verification,
    )
    if stage_revalidation["status"] != "passed":
        return {
            "artifact_type": "skillguard_install_activation",
            "status": "blocked",
            "blockers": ["stage_verification_failed"],
            "stage_verification": verification,
            "stage_revalidation": stage_revalidation,
            "claim_boundary": "No active install mutation occurred.",
        }
    try:
        with _InstallMutex(codex_home, "activate"):
            recovery = _recover_incomplete_installations_locked(
                codex_home,
                allow_replacement_only_head=True,
            )
            if recovery["status"] == "blocked":
                return {
                    "artifact_type": "skillguard_install_activation",
                    "status": "blocked",
                    "blockers": ["incomplete_transaction_recovery_failed"],
                    "recovery": recovery,
                    "claim_boundary": "No new activation mutation occurred.",
                }
            try:
                install_head = _load_install_head(codex_home)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                return {
                    "artifact_type": "skillguard_install_activation",
                    "status": "blocked",
                    "blockers": [f"invalid_install_head:{type(exc).__name__}"],
                    "claim_boundary": "No new activation mutation occurred.",
                }
            head_transaction_id = install_head.get("transaction_id")
            if head_transaction_id is None:
                committed_without_head: list[str] = []
                for transaction_path in sorted(
                    _transaction_root(codex_home).glob("install-*.json")
                ):
                    try:
                        candidate = _load_transaction(codex_home, transaction_path.stem)
                    except (OSError, ValueError, json.JSONDecodeError):
                        continue
                    if candidate.get("status") in {"committed", "commit_head_pending"}:
                        committed_without_head.append(str(candidate["transaction_id"]))
                if committed_without_head:
                    return {
                        "artifact_type": "skillguard_install_activation",
                        "status": "blocked",
                        "blockers": ["committed_transaction_without_install_head"],
                        "transaction_ids": committed_without_head,
                        "claim_boundary": "No new activation mutation occurred.",
                    }
            else:
                try:
                    head_record = _load_transaction(codex_home, str(head_transaction_id))
                except (OSError, ValueError, json.JSONDecodeError) as exc:
                    return {
                        "artifact_type": "skillguard_install_activation",
                        "status": "blocked",
                        "blockers": [f"install_head_target_invalid:{type(exc).__name__}"],
                        "claim_boundary": "No new activation mutation occurred.",
                    }
                head_status_and_generation_current = bool(
                    head_record.get("status") == "committed"
                    and int(head_record.get("generation", -1))
                    == int(install_head.get("generation", -2))
                )
                if not head_status_and_generation_current or (
                    _terminal_record_uses_current_projection(head_record)
                    and not _activation_receipt_active_replacement_eligible(
                        head_record
                    )
                ):
                    return {
                        "artifact_type": "skillguard_install_activation",
                        "status": "blocked",
                        "blockers": ["install_head_target_not_current"],
                        "claim_boundary": "No new activation mutation occurred.",
                    }
            stage_revalidation = _revalidate_stage_without_execution(
                canonical_skill_root,
                stage_root,
                verification,
            )
            if stage_revalidation["status"] != "passed":
                return {
                    "artifact_type": "skillguard_install_activation",
                    "status": "blocked",
                    "blockers": ["stage_changed_after_initial_verification"],
                    "stage_verification": verification,
                    "stage_revalidation": stage_revalidation,
                    "claim_boundary": "No active install mutation occurred.",
                }
            _durable_mkdir(active.parent)
            backup_root = codex_home / "backups"
            _durable_mkdir(backup_root)
            transaction_id = f"install-{uuid.uuid4().hex}"
            canonical_members = _suite_member_roots(canonical_skill_root, active)
            member_order = [member_id for member_id, _source, _active in canonical_members]
            staged_members = {
                member_id: staged_member_root
                for member_id, _canonical_root, staged_member_root in _suite_member_roots(
                    canonical_skill_root, stage_root
                )
            }
            incoming_roots = {
                member_id: active.parent / f".{member_id}-installing-{transaction_id[8:]}"
                for member_id in member_order
            }
            backup_roots = {
                member_id: backup_root / f"{member_id}-{transaction_id[8:]}"
                for member_id in member_order
            }
            activation_receipt_path = _receipt_path(codex_home, transaction_id)
            record: dict[str, Any] = {
                "schema_version": TRANSACTION_SCHEMA,
                "artifact_type": "skillguard_install_transaction",
                "transaction_id": transaction_id,
                "status": "in_progress",
                "phase": "incoming_copy_pending",
                "created_at": _utc_now(),
                "created_at_epoch_ns": time.time_ns(),
                "generation": int(install_head.get("generation", 0)) + 1,
                "previous_committed_transaction_id": head_transaction_id,
                "member_order": member_order,
                "members": {},
                "activation_receipt_path": str(activation_receipt_path.resolve()),
                "recovered_before_activation": recovery["recovered_transaction_ids"],
                "stage_verification": verification,
                "rollback_disposition": "pending",
            }
            for member_id, canonical_root, active_root in canonical_members:
                record["members"][member_id] = {
                    "canonical_root": str(canonical_root.resolve()),
                    "stage_root": str(staged_members[member_id].resolve()),
                    "active_root": str(active_root.resolve()),
                    "incoming_root": str(incoming_roots[member_id].resolve()),
                    "backup_root": str(backup_roots[member_id].resolve()),
                    "canonical_identity": _source_identity(canonical_root),
                    "canonical_installation_projection": installation_projection_identity(
                        canonical_root
                    ),
                    "previous_identity": _source_identity(
                        active_root,
                        active_installation_currentness=True,
                    ),
                    "stage_identity": _source_identity(staged_members[member_id]),
                    "stage_installation_projection": installation_projection_identity(
                        staged_members[member_id]
                    ),
                    "backup_created": False,
                    "activated": False,
                }
            _validate_codex_control_paths(codex_home)
            _validate_transaction_paths(codex_home, transaction_id, record)
            journal_path = _persist_transaction(codex_home, record)
            try:
                for member_id, _canonical_root, _active_root in canonical_members:
                    record["phase"] = f"incoming_copy_pending:{member_id}"
                    _persist_transaction(codex_home, record)
                    shutil.copytree(
                        staged_members[member_id],
                        incoming_roots[member_id],
                        ignore=_ignore_for_member(staged_members[member_id]),
                    )
                    _fsync_tree(incoming_roots[member_id])
                    record["members"][member_id]["incoming_identity"] = _source_identity(
                        incoming_roots[member_id]
                    )
                    record["phase"] = f"incoming_copied:{member_id}"
                    _persist_transaction(codex_home, record)
                incoming_comparisons: dict[str, dict[str, Any]] = {}
                for member_id, canonical_root, _active_root in canonical_members:
                    comparison = compare_installation_projection_member(
                        canonical_root,
                        incoming_roots[member_id],
                    )
                    comparison["canonical_runtime_authority"] = (
                        resolve_runtime_authority(canonical_root).to_dict()
                    )
                    comparison["installed_runtime_authority"] = (
                        resolve_runtime_authority(
                            incoming_roots[member_id]
                        ).to_dict()
                    )
                    incoming_comparisons[member_id] = comparison
                if any(
                    not _comparison_current(value) for value in incoming_comparisons.values()
                ):
                    quarantined = {
                        member_id: _quarantine_path(
                            incoming_roots[member_id],
                            codex_home,
                            transaction_id,
                            f"failed-incoming-{member_id}",
                        )
                        for member_id in member_order
                    }
                    record["status"] = "blocked_before_activation"
                    record["phase"] = "incoming_source_parity_failed"
                    record["incoming_comparisons"] = incoming_comparisons
                    record["quarantined_roots"] = quarantined
                    _persist_transaction(codex_home, record)
                    return {
                        "artifact_type": "skillguard_install_activation",
                        "status": "blocked",
                        "transaction_id": transaction_id,
                        "journal_path": str(journal_path.resolve()),
                        "blockers": [
                            "incoming_source_parity_failed",
                            "incoming_suite_member_parity_failed",
                        ],
                        "member_comparisons": incoming_comparisons,
                        "claim_boundary": "The active install was not changed.",
                    }
                record["incoming_comparisons"] = incoming_comparisons
                prebackup_drifted: list[str] = []
                for member_id, _canonical_root, active_root in canonical_members:
                    current_identity = _source_identity(
                        active_root,
                        active_installation_currentness=True,
                    )
                    expected_identity = record["members"][member_id]["previous_identity"]
                    if not _identities_equal(current_identity, expected_identity):
                        record["members"][member_id]["claimed_previous_identity"] = (
                            expected_identity
                        )
                        record["members"][member_id]["previous_identity"] = current_identity
                        record["members"][member_id]["prebackup_drift_detected"] = True
                        prebackup_drifted.append(member_id)
                if prebackup_drifted:
                    record["prebackup_drifted_member_ids"] = prebackup_drifted
                    _persist_transaction(codex_home, record)
                    restored = _restore_transaction_locked(
                        codex_home,
                        record,
                        terminal_status="rolled_back",
                        reason="active_source_drift_before_backup",
                    )
                    return {
                        **restored,
                        "artifact_type": "skillguard_install_activation",
                        "status": (
                            "rolled_back"
                            if restored.get("status") == "rolled_back"
                            else "failed"
                        ),
                        "blockers": [
                            "active_source_drift_before_backup",
                            *restored.get("blockers", []),
                        ],
                        "drifted_member_ids": prebackup_drifted,
                        "claim_boundary": (
                            "Activation did not pass because the active suite changed after "
                            "transaction identity capture; the latest observed identity was preserved."
                        ),
                    }
                backup_drifted: list[str] = []
                for member_id, _canonical_root, active_root in canonical_members:
                    record["phase"] = f"backup_pending:{member_id}"
                    _persist_transaction(codex_home, record)
                    current_identity = _source_identity(
                        active_root,
                        active_installation_currentness=True,
                    )
                    expected_identity = record["members"][member_id]["previous_identity"]
                    if not _identities_equal(current_identity, expected_identity):
                        record["members"][member_id]["claimed_previous_identity"] = (
                            expected_identity
                        )
                        record["members"][member_id]["previous_identity"] = current_identity
                        record["members"][member_id]["pre_rename_drift_detected"] = True
                        backup_drifted.append(member_id)
                        break
                    if _path_entity_exists(active_root):
                        _maybe_failpoint(f"backup:{member_id}:before")
                        _durable_rename(active_root, backup_roots[member_id])
                        _maybe_failpoint(f"backup:{member_id}:after")
                        record["members"][member_id]["backup_created"] = True
                    backup_identity = _source_identity(
                        backup_roots[member_id],
                        active_installation_currentness=True,
                    )
                    record["members"][member_id]["backup_identity"] = backup_identity
                    if not _identities_equal(backup_identity, expected_identity):
                        record["members"][member_id]["claimed_previous_identity"] = (
                            expected_identity
                        )
                        record["members"][member_id]["previous_identity"] = backup_identity
                        record["members"][member_id]["rename_window_drift_detected"] = True
                        backup_drifted.append(member_id)
                        record["phase"] = f"backup_drift_detected:{member_id}"
                        _persist_transaction(codex_home, record)
                        break
                    record["phase"] = f"backup_complete:{member_id}"
                    _persist_transaction(codex_home, record)
                if backup_drifted:
                    record["backup_drifted_member_ids"] = backup_drifted
                    _persist_transaction(codex_home, record)
                    restored = _restore_transaction_locked(
                        codex_home,
                        record,
                        terminal_status="rolled_back",
                        reason="active_source_drift_during_backup",
                    )
                    return {
                        **restored,
                        "artifact_type": "skillguard_install_activation",
                        "status": (
                            "rolled_back"
                            if restored.get("status") == "rolled_back"
                            else "failed"
                        ),
                        "blockers": [
                            "active_source_drift_during_backup",
                            *restored.get("blockers", []),
                        ],
                        "drifted_member_ids": backup_drifted,
                        "claim_boundary": (
                            "Activation did not pass because an active member changed during "
                            "backup capture; the actual preserved bytes became rollback authority."
                        ),
                    }
                for member_id, _canonical_root, active_root in canonical_members:
                    record["phase"] = f"activation_pending:{member_id}"
                    _persist_transaction(codex_home, record)
                    _maybe_failpoint(f"activate:{member_id}:before")
                    _durable_rename(incoming_roots[member_id], active_root)
                    _maybe_failpoint(f"activate:{member_id}:after")
                    record["members"][member_id]["activated"] = True
                    record["members"][member_id]["installed_identity"] = _source_identity(
                        active_root,
                        active_installation_currentness=True,
                    )
                    record["members"][member_id][
                        "installed_installation_projection"
                    ] = installation_projection_identity(active_root)
                    record["phase"] = f"activated:{member_id}"
                    _persist_transaction(codex_home, record)
                smoke = smoke_installed_skill(
                    active,
                    active_installation_currentness=True,
                )
                member_comparisons = _member_comparisons(canonical_skill_root, active)
                postbackup_drifted: list[str] = []
                for member_id in member_order:
                    member = record["members"][member_id]
                    actual_backup_identity = _source_identity(
                        Path(member["backup_root"]),
                        active_installation_currentness=True,
                    )
                    expected_backup_identity = member["previous_identity"]
                    if not _identities_equal(
                        actual_backup_identity, expected_backup_identity
                    ):
                        member["postbackup_claimed_identity"] = expected_backup_identity
                        member["postbackup_actual_identity"] = actual_backup_identity
                        if bool(actual_backup_identity.get("exists")):
                            member["previous_identity"] = actual_backup_identity
                        postbackup_drifted.append(member_id)
                if postbackup_drifted:
                    record["postbackup_drifted_member_ids"] = postbackup_drifted
                    record["post_activation_smoke"] = smoke
                    record["post_activation_member_comparisons"] = member_comparisons
                    _persist_transaction(codex_home, record)
                    restored = _restore_transaction_locked(
                        codex_home,
                        record,
                        terminal_status="rolled_back",
                        reason="backup_identity_drift_before_commit",
                    )
                    return {
                        **restored,
                        "artifact_type": "skillguard_install_activation",
                        "status": (
                            "rolled_back"
                            if restored.get("status") == "rolled_back"
                            else "failed"
                        ),
                        "blockers": [
                            "backup_identity_drift_before_commit",
                            *restored.get("blockers", []),
                        ],
                        "drifted_member_ids": postbackup_drifted,
                        "claim_boundary": (
                            "Activation did not pass because rollback authority changed before "
                            "commit; exact restoration is claimed only when verification passed."
                        ),
                    }
                if smoke["status"] != "passed" or any(
                    not _comparison_current(value) for value in member_comparisons.values()
                ):
                    record["post_activation_smoke"] = smoke
                    record["post_activation_member_comparisons"] = member_comparisons
                    _persist_transaction(codex_home, record)
                    restored = _restore_transaction_locked(
                        codex_home,
                        record,
                        terminal_status="rolled_back",
                        reason="post_activation_verification_failed",
                    )
                    return {
                        **restored,
                        "artifact_type": "skillguard_install_activation",
                        "status": "rolled_back" if restored.get("status") == "rolled_back" else "failed",
                        "blockers": ["post_activation_verification_failed", *restored.get("blockers", [])],
                        "smoke": smoke,
                        "member_comparisons": member_comparisons,
                        "claim_boundary": (
                            "Post-activation verification failed; the exact prior two-member "
                            "identity was restored when restore_verification passed."
                        ),
                    }
                for member_id in member_order:
                    record["members"][member_id]["installed_identity"] = _source_identity(
                        Path(record["members"][member_id]["active_root"]),
                        active_installation_currentness=True,
                    )
                record["status"] = "commit_pending"
                record["phase"] = "activation_receipt_pending"
                record["post_activation_smoke"] = smoke
                record["post_activation_member_comparisons"] = member_comparisons
                record["rollback_disposition"] = "not_required"
                journal_path = _persist_transaction(codex_home, record)
                activation_verification_journal_hash = record["journal_hash"]
                receipt = _write_receipt(
                    activation_receipt_path,
                    {
                        "schema_version": "skillguard.install_activation_receipt.v1",
                        "artifact_type": "skillguard_install_activation_receipt",
                        "status": "activation_verified",
                        "transaction_id": transaction_id,
                        "journal_hash": activation_verification_journal_hash,
                        "stage_verification_hash": canonical_hash(
                            record["stage_verification"]
                        ),
                        "post_activation_smoke_hash": canonical_hash(smoke),
                        "post_activation_member_comparisons_hash": canonical_hash(
                            member_comparisons
                        ),
                        "rollback_disposition": "not_required",
                        "installed_member_ids": member_order,
                        "backup_roots": {
                            member_id: record["members"][member_id]["backup_root"]
                            for member_id in member_order
                        },
                        "canonical_identities": {
                            member_id: record["members"][member_id]["canonical_identity"]
                            for member_id in member_order
                        },
                        "stage_identities": {
                            member_id: record["members"][member_id]["stage_identity"]
                            for member_id in member_order
                        },
                        "previous_identities": {
                            member_id: record["members"][member_id]["previous_identity"]
                            for member_id in member_order
                        },
                        "backup_identities": {
                            member_id: record["members"][member_id]["backup_identity"]
                            for member_id in member_order
                        },
                        "installed_identities": {
                            member_id: record["members"][member_id]["installed_identity"]
                            for member_id in member_order
                        },
                        "canonical_installation_projections": {
                            member_id: record["members"][member_id][
                                "canonical_installation_projection"
                            ]
                            for member_id in member_order
                        },
                        "stage_installation_projections": {
                            member_id: record["members"][member_id][
                                "stage_installation_projection"
                            ]
                            for member_id in member_order
                        },
                        "installed_installation_projections": {
                            member_id: record["members"][member_id][
                                "installed_installation_projection"
                            ]
                            for member_id in member_order
                        },
                        "created_at": _utc_now(),
                        "claim_boundary": (
                            "This receipt proves the named local two-member activation verification "
                            "and exact backup identities only when its journal subsequently records "
                            "committed with this receipt hash; it does not prove publication."
                        ),
                    },
                )
                _maybe_failpoint("activation_receipt:after")
                record["activation_verification_journal_hash"] = (
                    activation_verification_journal_hash
                )
                record["activation_receipt_hash"] = receipt["receipt_hash"]
                record["status"] = "commit_head_pending"
                record["phase"] = "commit_head_pending"
                journal_path = _persist_transaction(codex_home, record)
                install_head = _write_install_head(
                    codex_home,
                    transaction_id=transaction_id,
                    previous_transaction_id=record["previous_committed_transaction_id"],
                    generation=int(record["generation"]),
                )
                _maybe_failpoint("install_head:after")
                record["install_head_hash"] = install_head["head_hash"]
                record["status"] = "committed"
                record["phase"] = "committed"
                journal_path = _persist_transaction(codex_home, record)
                _maybe_failpoint("commit_journal:after")
                return {
                    "artifact_type": "skillguard_install_activation",
                    "status": "passed",
                    "transaction_id": transaction_id,
                    "journal_path": str(journal_path.resolve()),
                    "receipt_path": str(activation_receipt_path.resolve()),
                    "receipt_hash": receipt["receipt_hash"],
                    "active_path_token": "codex_home/skills/skillguard",
                    "backup_path_token": "codex_home/backups/<suite-member>-<transaction>",
                    "backup_roots": {
                        member_id: record["members"][member_id]["backup_root"]
                        for member_id in member_order
                    },
                    "smoke": smoke,
                    "comparison": member_comparisons["skillguard"],
                    "member_comparisons": member_comparisons,
                    "installed_member_ids": member_order,
                    "recovered_before_activation": recovery["recovered_transaction_ids"],
                    "blockers": [],
                    "claim_boundary": (
                        "Activation proves the current local two-member SkillGuard suite, durable "
                        "transaction receipt, exact backup identities, and smoke boundary; it does "
                        "not prove GitHub publication."
                    ),
                }
            except Exception as exc:
                diagnostic = _activation_exception_diagnostic(
                    exc, phase=str(record.get("phase", ""))
                )
                record["activation_exception"] = {
                    "type": type(exc).__name__,
                    "message": str(exc),
                    **diagnostic,
                }
                _persist_transaction(codex_home, record)
                restored = _restore_transaction_locked(
                    codex_home,
                    record,
                    terminal_status="rolled_back",
                    reason=f"activation_exception:{type(exc).__name__}",
                )
                return {
                    **restored,
                    "artifact_type": "skillguard_install_activation",
                    "status": "rolled_back" if restored.get("status") == "rolled_back" else "failed",
                    "blockers": ["activation_exception", *restored.get("blockers", [])],
                    "exception_type": type(exc).__name__,
                    **diagnostic,
                    "claim_boundary": (
                        "Activation raised an exception; the exact prior two-member identity was "
                        "restored only when restore_verification passed."
                    ),
                }
    except InstallBusyError:
        return {
            "artifact_type": "skillguard_install_activation",
            "status": "blocked",
            "blockers": ["install_lock_busy"],
            "claim_boundary": "No activation mutation occurred because another installer owns the mutex.",
        }
    except UnsafeInstallPathError as exc:
        return {
            "artifact_type": "skillguard_install_activation",
            "status": "blocked",
            "blockers": ["unsafe_codex_control_path"],
            "reason": str(exc),
            "claim_boundary": "No active install mutation occurred.",
        }


def rollback_install(codex_home: Path, transaction_id: str) -> dict[str, Any]:
    codex_home = codex_home.resolve()
    try:
        with _InstallMutex(codex_home, "rollback"):
            recovery = _recover_incomplete_installations_locked(codex_home)
            if recovery["status"] == "blocked":
                return {
                    "artifact_type": "skillguard_install_manual_rollback",
                    "status": "blocked",
                    "transaction_id": transaction_id,
                    "blockers": ["incomplete_transaction_recovery_failed"],
                    "recovery": recovery,
                }
            try:
                record = _load_transaction(codex_home, transaction_id)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                return {
                    "artifact_type": "skillguard_install_manual_rollback",
                    "status": "blocked",
                    "transaction_id": transaction_id,
                    "blockers": [f"invalid_transaction_receipt:{type(exc).__name__}"],
                }
            if record.get("status") != "committed":
                return {
                    "artifact_type": "skillguard_install_manual_rollback",
                    "status": "blocked",
                    "transaction_id": transaction_id,
                    "blockers": ["transaction_not_committed"],
                }
            try:
                install_head = _load_install_head(codex_home)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                return {
                    "artifact_type": "skillguard_install_manual_rollback",
                    "status": "blocked",
                    "transaction_id": transaction_id,
                    "blockers": [f"invalid_install_head:{type(exc).__name__}"],
                }
            if install_head.get("transaction_id") != transaction_id:
                return {
                    "artifact_type": "skillguard_install_manual_rollback",
                    "status": "blocked",
                    "transaction_id": transaction_id,
                    "blockers": ["newer_committed_transaction_exists"],
                }
            drifted = [
                member_id
                for member_id in record["member_order"]
                if not _identity_matches(
                    Path(record["members"][member_id]["active_root"]),
                    record["members"][member_id]["installed_identity"],
                    active_installation_currentness=True,
                )
            ]
            if drifted:
                return {
                    "artifact_type": "skillguard_install_manual_rollback",
                    "status": "blocked",
                    "transaction_id": transaction_id,
                    "blockers": [f"active_install_drift:{member_id}" for member_id in drifted],
                    "drifted_member_ids": drifted,
                    "claim_boundary": "No rollback mutation occurred because active identity drifted.",
                }
            previous_transaction_id = record.get("previous_committed_transaction_id")
            if previous_transaction_id is None:
                record["head_after_rollback"] = {
                    "transaction_id": None,
                    "previous_transaction_id": None,
                    "generation": 0,
                }
            else:
                try:
                    previous_record = _load_transaction(
                        codex_home, str(previous_transaction_id)
                    )
                except (OSError, ValueError, json.JSONDecodeError) as exc:
                    return {
                        "artifact_type": "skillguard_install_manual_rollback",
                        "status": "blocked",
                        "transaction_id": transaction_id,
                        "blockers": [
                            f"previous_transaction_invalid:{type(exc).__name__}"
                        ],
                    }
                if previous_record.get("status") != "committed":
                    return {
                        "artifact_type": "skillguard_install_manual_rollback",
                        "status": "blocked",
                        "transaction_id": transaction_id,
                        "blockers": ["previous_transaction_not_committed"],
                    }
                record["head_after_rollback"] = {
                    "transaction_id": previous_transaction_id,
                    "previous_transaction_id": previous_record.get(
                        "previous_committed_transaction_id"
                    ),
                    "generation": int(previous_record.get("generation", 0)),
                }
            record["intended_recovery_terminal_status"] = "manually_rolled_back"
            _persist_transaction(codex_home, record)
            restored = _restore_transaction_locked(
                codex_home,
                record,
                terminal_status="manually_rolled_back",
                reason="explicit_manual_rollback",
            )
            return {
                **restored,
                "artifact_type": "skillguard_install_manual_rollback",
                "status": (
                    "rolled_back"
                    if restored.get("status") == "manually_rolled_back"
                    else restored.get("status", "failed")
                ),
                "claim_boundary": (
                    "Manual rollback restored only the exact pre-transaction two-member identity "
                    "named by the current, non-drifted transaction receipt."
                ),
            }
    except InstallBusyError:
        return {
            "artifact_type": "skillguard_install_manual_rollback",
            "status": "blocked",
            "transaction_id": transaction_id,
            "blockers": ["install_lock_busy"],
            "claim_boundary": "No rollback mutation occurred because another installer owns the mutex.",
        }
    except UnsafeInstallPathError as exc:
        return {
            "artifact_type": "skillguard_install_manual_rollback",
            "status": "blocked",
            "transaction_id": transaction_id,
            "blockers": ["unsafe_codex_control_path"],
            "reason": str(exc),
            "claim_boundary": "No rollback mutation occurred.",
        }
