"""Projection-exact transactional installation for one maintained target skill.

This module intentionally does not reuse the SkillGuard self-install transaction
cohort.  Each target owns an isolated journal, HEAD, receipt, backup, rollback,
and recovery chain while sharing only the global filesystem installation lock.
It never discovers or executes target repository commands.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any, Mapping

from .contract_compiler import canonical_hash
from .installation import (
    WINDOWS_PATH_BUDGET_ENABLED,
    WINDOWS_STAGE_DIRECTORY_PATH_LIMIT,
    WINDOWS_STAGE_FILE_PATH_LIMIT,
    InstallBusyError,
    UnsafeInstallPathError,
    _InstallMutex,
    _activation_exception_diagnostic,
    _atomic_write_json,
    _comparison_current,
    _durable_mkdir,
    _durable_rename,
    _fsync_tree,
    _is_reparse_point,
    _path_entity_exists,
    _validate_codex_control_paths,
    compare_installation_projection_member,
    installation_member_paths,
    installation_projection_identity,
)
from .portable_content import portable_files, scan_member_boundary
from .runtime_authority import resolve_runtime_authority
from .path_identity import (
    canonical_filesystem_path,
    same_filesystem_object,
)


TARGET_TRANSACTION_SCHEMA = "skillguard.target_install_transaction.current"
TARGET_RECEIPT_SCHEMA = "skillguard.target_install_receipt.current"
TARGET_HEAD_SCHEMA = "skillguard.target_install_head.current"
TARGET_STAGE_SCHEMA = "skillguard.target_install_stage.current"
TARGET_TRANSACTION_DIRECTORY = "target-install-transactions"
TARGET_BACKUP_DIRECTORY = "target-install-backups"
TARGET_TRANSACTION_PATTERN = re.compile(r"^target-install-[0-9a-f]{32}$")
SKILL_ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
TERMINAL_STATUSES = frozenset(
    {
        "committed",
        "blocked_before_activation",
        "rolled_back",
        "recovered_rolled_back",
        "manually_rolled_back",
    }
)


def _wire_record(payload: Mapping[str, Any], hash_field: str) -> dict[str, Any]:
    result = dict(payload)
    result[hash_field] = canonical_hash(
        {key: value for key, value in result.items() if key != hash_field}
    )
    return result


def _safe_skill_id(value: object) -> str:
    skill_id = str(value).strip()
    if not SKILL_ID_PATTERN.fullmatch(skill_id):
        raise ValueError("target_install_skill_id_invalid")
    return skill_id


def _read_json_object(path: Path, error_code: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(error_code)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(error_code) from exc
    if not isinstance(payload, dict):
        raise ValueError(error_code)
    return payload


def _canonical_target(
    repository_root: Path, canonical_skill_root: Path
) -> dict[str, Any]:
    repository = canonical_filesystem_path(repository_root)
    canonical = canonical_filesystem_path(canonical_skill_root)
    if not canonical.is_dir() or not canonical.is_relative_to(repository):
        raise ValueError("target_install_skill_root_outside_repository")
    manifest = _read_json_object(
        canonical / ".skillguard" / "check-manifest.json",
        "target_install_manifest_missing",
    )
    skill_id = _safe_skill_id(manifest.get("skill_id"))
    plan = manifest.get("content_impact_plan")
    if not isinstance(plan, Mapping):
        raise ValueError("target_install_content_impact_plan_missing")
    member_root_path = str(plan.get("member_root_path", "")).replace("\\", "/")
    if not member_root_path:
        raise ValueError("target_install_member_root_path_missing")
    expected = repository if member_root_path == "." else repository / Path(
        *member_root_path.split("/")
    )
    if not same_filesystem_object(expected, canonical):
        raise ValueError("target_install_member_root_path_mismatch")
    if canonical.is_symlink() or _is_reparse_point(canonical):
        raise ValueError("target_install_canonical_root_unsafe")
    boundary = scan_member_boundary(canonical)
    blockers = [
        *(f"canonical_runtime_artifact:{path}" for path in boundary.blocking_runtime_paths),
        *(f"canonical_unsafe_path:{path}" for path in boundary.unsafe_paths),
    ]
    if blockers:
        raise ValueError(";".join(blockers))
    projection = installation_projection_identity(canonical)
    member_paths = installation_member_paths(canonical)
    return {
        "repository_root": repository,
        "canonical_root": canonical,
        "skill_id": skill_id,
        "member_root_path": member_root_path,
        "projection": projection,
        "member_paths": member_paths,
        "member_paths_hash": canonical_hash(list(member_paths)),
    }


def _roots_overlap(*roots: Path) -> bool:
    resolved = [canonical_filesystem_path(root) for root in roots]
    for index, left in enumerate(resolved):
        for right in resolved[index + 1 :]:
            if left == right or left.is_relative_to(right) or right.is_relative_to(left):
                return True
    return False


def _stage_path_budget(stage_root: Path, member_paths: tuple[str, ...]) -> dict[str, Any]:
    file_rows = [
        {"relative_path": path, "projected_length": len(str(stage_root / Path(path)))}
        for path in member_paths
    ]
    directory_rows: dict[str, dict[str, Any]] = {
        ".": {"relative_path": ".", "projected_length": len(str(stage_root))}
    }
    for relative_text in member_paths:
        parent = Path(relative_text).parent
        while parent != Path("."):
            relative = parent.as_posix()
            directory_rows[relative] = {
                "relative_path": relative,
                "projected_length": len(str(stage_root / parent)),
            }
            parent = parent.parent
    longest_file = max(
        file_rows,
        key=lambda row: (int(row["projected_length"]), str(row["relative_path"])),
        default={"relative_path": "", "projected_length": 0},
    )
    longest_directory = max(
        directory_rows.values(),
        key=lambda row: (int(row["projected_length"]), str(row["relative_path"])),
    )
    blockers: list[str] = []
    if WINDOWS_PATH_BUDGET_ENABLED:
        if int(longest_file["projected_length"]) > WINDOWS_STAGE_FILE_PATH_LIMIT:
            blockers.append("target_stage_projected_file_path_too_long")
        if int(longest_directory["projected_length"]) > WINDOWS_STAGE_DIRECTORY_PATH_LIMIT:
            blockers.append("target_stage_projected_directory_path_too_long")
    return {
        "schema_version": "skillguard.target_stage_path_budget.current",
        "status": "blocked" if blockers else "passed",
        "longest_file": longest_file,
        "longest_directory": longest_directory,
        "blockers": blockers,
    }


def _remove_new_tree(path: Path, allowed_parent: Path) -> None:
    lexical = path.absolute()
    parent = allowed_parent.resolve()
    if not lexical.parent.resolve().is_relative_to(parent):
        raise ValueError("target_install_cleanup_path_outside_owner")
    if not _path_entity_exists(lexical):
        return
    if _is_reparse_point(lexical) or not lexical.is_dir():
        raise ValueError("target_install_cleanup_path_unsafe")
    shutil.rmtree(lexical)


def _copy_projection(source_root: Path, destination_root: Path) -> dict[str, Any]:
    source = source_root.resolve(strict=True)
    destination = destination_root.absolute()
    if _path_entity_exists(destination):
        raise FileExistsError("target_install_destination_exists")
    member_paths = installation_member_paths(source)
    destination.mkdir(parents=True, exist_ok=False)
    copied: list[str] = []
    try:
        for relative_text in member_paths:
            relative = Path(*relative_text.split("/"))
            candidate = source / relative
            resolved_candidate = candidate.resolve(strict=True)
            if (
                candidate.is_symlink()
                or not candidate.is_file()
                or not resolved_candidate.is_relative_to(source)
            ):
                raise ValueError("target_install_projection_member_unsafe")
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(candidate, target)
            copied.append(relative_text)
        _fsync_tree(destination)
    except Exception:
        _remove_new_tree(destination, destination.parent)
        raise
    return {
        "status": "passed",
        "member_count": len(copied),
        "member_paths_hash": canonical_hash(copied),
    }


def _portable_relative_files(root: Path) -> tuple[str, ...]:
    return tuple(relative.as_posix() for relative, _path in portable_files(root))


def _target_comparison(canonical_root: Path, projected_root: Path) -> dict[str, Any]:
    comparison = compare_installation_projection_member(
        canonical_root, projected_root
    )
    comparison["canonical_runtime_authority"] = resolve_runtime_authority(
        canonical_root
    ).to_dict()
    comparison["installed_runtime_authority"] = resolve_runtime_authority(
        projected_root
    ).to_dict()
    return comparison


def verify_target_stage(
    repository_root: Path,
    canonical_skill_root: Path,
    stage_skill_root: Path,
) -> dict[str, Any]:
    target = _canonical_target(repository_root, canonical_skill_root)
    lexical_stage = stage_skill_root.absolute()
    if (
        lexical_stage.name != target["skill_id"]
        or not _path_entity_exists(lexical_stage)
        or lexical_stage.is_symlink()
        or _is_reparse_point(lexical_stage)
    ):
        raise ValueError("target_install_stage_root_invalid")
    stage = lexical_stage.resolve(strict=True)
    if _roots_overlap(target["repository_root"], stage):
        raise ValueError("target_install_stage_overlaps_repository")
    boundary = scan_member_boundary(stage)
    blockers = [
        *(f"stage_runtime_artifact:{path}" for path in boundary.blocking_runtime_paths),
        *(f"stage_unsafe_path:{path}" for path in boundary.unsafe_paths),
    ]
    expected_files = tuple(target["member_paths"])
    actual_files = _portable_relative_files(stage)
    missing = sorted(set(expected_files) - set(actual_files))
    unexpected = sorted(set(actual_files) - set(expected_files))
    comparison: dict[str, Any] = {}
    if not blockers and not missing and not unexpected:
        comparison = _target_comparison(
            target["canonical_root"], stage
        )
        if not _comparison_current(comparison):
            blockers.append("target_stage_projection_or_authority_mismatch")
    blockers.extend(f"target_stage_missing:{path}" for path in missing)
    blockers.extend(f"target_stage_unexpected:{path}" for path in unexpected)
    report = {
        "schema_version": TARGET_STAGE_SCHEMA,
        "status": "blocked" if blockers else "passed",
        "skill_id": target["skill_id"],
        "member_root_path": target["member_root_path"],
        "canonical_projection": target["projection"],
        "stage_projection": (
            installation_projection_identity(stage) if not blockers else None
        ),
        "member_count": len(expected_files),
        "member_paths_hash": target["member_paths_hash"],
        "missing": missing,
        "unexpected": unexpected,
        "comparison_current": bool(comparison and _comparison_current(comparison)),
        "comparison": comparison,
        "blockers": sorted(set(blockers)),
        "claim_boundary": "Stage verification proves only exact projected bytes and current static authority; it executes no target command and does not activate the install.",
    }
    report["stage_verification_hash"] = canonical_hash(report)
    return report


def prepare_target_stage(
    repository_root: Path,
    canonical_skill_root: Path,
    stage_skill_root: Path,
) -> dict[str, Any]:
    target = _canonical_target(repository_root, canonical_skill_root)
    stage = stage_skill_root.absolute()
    if stage.name != target["skill_id"]:
        raise ValueError("target_install_stage_skill_id_mismatch")
    if _path_entity_exists(stage):
        raise FileExistsError("target_install_stage_exists")
    if _roots_overlap(target["repository_root"], stage):
        raise ValueError("target_install_stage_overlaps_repository")
    budget = _stage_path_budget(stage, target["member_paths"])
    if budget["status"] != "passed":
        return {
            "schema_version": TARGET_STAGE_SCHEMA,
            "status": "blocked",
            "skill_id": target["skill_id"],
            "path_budget": budget,
            "blockers": list(budget["blockers"]),
        }
    _durable_mkdir(stage.parent)
    copy_result = _copy_projection(target["canonical_root"], stage)
    verification = verify_target_stage(
        target["repository_root"], target["canonical_root"], stage
    )
    return {
        "schema_version": TARGET_STAGE_SCHEMA,
        "status": verification["status"],
        "skill_id": target["skill_id"],
        "path_budget": budget,
        "copy": copy_result,
        "verification": verification,
        "blockers": list(verification["blockers"]),
        "claim_boundary": "Preparation writes only a new isolated stage from the exact installation projection; it does not mutate CODEX_HOME.",
    }


def _target_namespace(codex_home: Path, skill_id: str) -> Path:
    return codex_home / TARGET_TRANSACTION_DIRECTORY / skill_id


def _journal_path(codex_home: Path, skill_id: str, transaction_id: str) -> Path:
    if not TARGET_TRANSACTION_PATTERN.fullmatch(transaction_id):
        raise ValueError("target_install_transaction_id_invalid")
    return _target_namespace(codex_home, skill_id) / f"{transaction_id}.json"


def _receipt_path(codex_home: Path, skill_id: str, transaction_id: str) -> Path:
    return _target_namespace(codex_home, skill_id) / "receipts" / f"{transaction_id}.json"


def _head_path(codex_home: Path, skill_id: str) -> Path:
    return _target_namespace(codex_home, skill_id) / "HEAD.json"


def _validate_target_control_paths(codex_home: Path, skill_id: str) -> None:
    _validate_codex_control_paths(codex_home)
    home = codex_home.resolve()
    for relative in (
        Path(TARGET_TRANSACTION_DIRECTORY),
        Path(TARGET_TRANSACTION_DIRECTORY) / skill_id,
        Path(TARGET_BACKUP_DIRECTORY),
        Path(TARGET_BACKUP_DIRECTORY) / skill_id,
    ):
        candidate = home / relative
        if not _path_entity_exists(candidate):
            continue
        if _is_reparse_point(candidate) or not candidate.is_dir():
            raise UnsafeInstallPathError("target_install_control_path_unsafe")
        if not candidate.resolve().is_relative_to(home):
            raise UnsafeInstallPathError("target_install_control_path_escape")


def _write_journal(codex_home: Path, record: Mapping[str, Any]) -> dict[str, Any]:
    skill_id = _safe_skill_id(record.get("skill_id"))
    transaction_id = str(record.get("transaction_id", ""))
    path = _journal_path(codex_home, skill_id, transaction_id)
    _durable_mkdir(path.parent)
    payload = _wire_record(record, "journal_hash")
    _atomic_write_json(path, payload)
    return payload


def _load_journal(codex_home: Path, skill_id: str, transaction_id: str) -> dict[str, Any]:
    payload = _read_json_object(
        _journal_path(codex_home, skill_id, transaction_id),
        "target_install_journal_invalid",
    )
    if payload.get("schema_version") != TARGET_TRANSACTION_SCHEMA:
        raise ValueError("target_install_journal_schema_invalid")
    if payload.get("skill_id") != skill_id or payload.get("transaction_id") != transaction_id:
        raise ValueError("target_install_journal_identity_mismatch")
    expected = canonical_hash(
        {key: value for key, value in payload.items() if key != "journal_hash"}
    )
    if payload.get("journal_hash") != expected:
        raise ValueError("target_install_journal_hash_mismatch")
    return payload


def _load_head(codex_home: Path, skill_id: str) -> dict[str, Any]:
    path = _head_path(codex_home, skill_id)
    if not path.exists():
        return {
            "schema_version": TARGET_HEAD_SCHEMA,
            "skill_id": skill_id,
            "transaction_id": None,
            "generation": 0,
            "receipt_hash": None,
        }
    payload = _read_json_object(path, "target_install_head_invalid")
    expected = canonical_hash(
        {key: value for key, value in payload.items() if key != "head_hash"}
    )
    if (
        payload.get("schema_version") != TARGET_HEAD_SCHEMA
        or payload.get("skill_id") != skill_id
        or payload.get("head_hash") != expected
    ):
        raise ValueError("target_install_head_invalid")
    return payload


def _write_head(
    codex_home: Path,
    skill_id: str,
    transaction_id: str | None,
    generation: int,
    receipt_hash: str | None,
) -> dict[str, Any]:
    path = _head_path(codex_home, skill_id)
    _durable_mkdir(path.parent)
    payload = _wire_record(
        {
            "schema_version": TARGET_HEAD_SCHEMA,
            "skill_id": skill_id,
            "transaction_id": transaction_id,
            "generation": generation,
            "receipt_hash": receipt_hash,
        },
        "head_hash",
    )
    _atomic_write_json(path, payload)
    return payload


def _write_receipt(codex_home: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    skill_id = _safe_skill_id(payload.get("skill_id"))
    transaction_id = str(payload.get("transaction_id", ""))
    path = _receipt_path(codex_home, skill_id, transaction_id)
    _durable_mkdir(path.parent)
    receipt = _wire_record(payload, "receipt_hash")
    _atomic_write_json(path, receipt)
    return receipt


def _record_paths(codex_home: Path, skill_id: str, transaction_id: str) -> dict[str, str]:
    suffix = transaction_id.removeprefix("target-install-")
    return {
        "active_root": str((codex_home / "skills" / skill_id).absolute()),
        "incoming_root": str((codex_home / "skills" / f".{skill_id}-installing-{suffix}").absolute()),
        "backup_root": str((codex_home / TARGET_BACKUP_DIRECTORY / skill_id / transaction_id).absolute()),
        "quarantine_root": str((codex_home / TARGET_BACKUP_DIRECTORY / skill_id / f"quarantine-{transaction_id}").absolute()),
    }


def _validate_record_paths(codex_home: Path, record: Mapping[str, Any]) -> None:
    home = codex_home.resolve()
    skill_id = _safe_skill_id(record.get("skill_id"))
    transaction_id = str(record.get("transaction_id", ""))
    expected = _record_paths(home, skill_id, transaction_id)
    roots: list[Path] = []
    for key, expected_text in expected.items():
        actual = Path(str(record.get(key, "")))
        if actual.absolute() != Path(expected_text).absolute():
            raise ValueError("target_install_transaction_path_mismatch")
        if not actual.absolute().is_relative_to(home):
            raise ValueError("target_install_transaction_path_escape")
        if _path_entity_exists(actual) and (
            _is_reparse_point(actual) or not actual.is_dir()
        ):
            raise ValueError("target_install_transaction_path_unsafe")
        roots.append(actual.absolute())
    if _roots_overlap(*roots):
        raise ValueError("target_install_transaction_path_overlap")


def _restore_record(
    codex_home: Path,
    record: Mapping[str, Any],
    *,
    terminal_status: str,
) -> dict[str, Any]:
    current = dict(record)
    _validate_record_paths(codex_home, current)
    active = Path(current["active_root"])
    incoming = Path(current["incoming_root"])
    backup = Path(current["backup_root"])
    quarantine = Path(current["quarantine_root"])
    status = str(current.get("status", ""))
    activation_may_have_occurred = status in {
        "activated",
        "post_activation_verifying",
        "receipt_pending",
        "committed",
    } or (
        status == "backup_ready"
        and not _path_entity_exists(incoming)
        and _path_entity_exists(active)
    )
    if activation_may_have_occurred and _path_entity_exists(active):
        if _path_entity_exists(quarantine):
            raise ValueError("target_install_quarantine_exists")
        _durable_mkdir(quarantine.parent)
        _durable_rename(active, quarantine)
    if _path_entity_exists(backup):
        if _path_entity_exists(active):
            raise ValueError("target_install_restore_active_conflict")
        _durable_rename(backup, active)
    if _path_entity_exists(incoming):
        _remove_new_tree(incoming, incoming.parent)
    current["status"] = terminal_status
    current["restored_previous_active"] = bool(current.get("previous_active_present"))
    current = _write_journal(codex_home, current)
    head = _load_head(codex_home, str(current["skill_id"]))
    if head.get("transaction_id") == current.get("transaction_id"):
        previous_id = current.get("previous_transaction_id")
        previous_hash = None
        if previous_id:
            previous = _load_journal(
                codex_home, str(current["skill_id"]), str(previous_id)
            )
            previous_hash = previous.get("receipt_hash")
        _write_head(
            codex_home,
            str(current["skill_id"]),
            str(previous_id) if previous_id else None,
            int(head.get("generation", 0)) + 1,
            str(previous_hash) if previous_hash else None,
        )
    return current


def _recover_locked(codex_home: Path, skill_id: str) -> dict[str, Any]:
    namespace = _target_namespace(codex_home, skill_id)
    if not namespace.exists():
        return {"status": "passed", "skill_id": skill_id, "recovered": [], "blockers": []}
    recovered: list[str] = []
    blockers: list[str] = []
    for path in sorted(namespace.glob("target-install-*.json")):
        try:
            record = _load_journal(codex_home, skill_id, path.stem)
            if record.get("status") in TERMINAL_STATUSES:
                continue
            _restore_record(
                codex_home, record, terminal_status="recovered_rolled_back"
            )
            recovered.append(path.stem)
        except (OSError, ValueError) as exc:
            blockers.append(f"target_recovery_failed:{path.stem}:{type(exc).__name__}")
    return {
        "status": "blocked" if blockers else "passed",
        "skill_id": skill_id,
        "recovered": recovered,
        "blockers": blockers,
    }


def recover_target_installations(codex_home: Path, skill_id: str) -> dict[str, Any]:
    home = codex_home.resolve()
    target_id = _safe_skill_id(skill_id)
    try:
        _validate_target_control_paths(home, target_id)
        with _InstallMutex(home, f"recover-target:{target_id}"):
            return _recover_locked(home, target_id)
    except (InstallBusyError, UnsafeInstallPathError, OSError, ValueError) as exc:
        return {
            "status": "blocked",
            "skill_id": target_id,
            "recovered": [],
            "blockers": [f"target_recovery_preflight:{type(exc).__name__}"],
        }


def activate_target_stage(
    repository_root: Path,
    canonical_skill_root: Path,
    stage_skill_root: Path,
    codex_home: Path,
    *,
    stage_verification: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    target = _canonical_target(repository_root, canonical_skill_root)
    stage = stage_skill_root.resolve(strict=True)
    home = codex_home.resolve()
    active = (home / "skills" / target["skill_id"]).absolute()
    if _roots_overlap(target["repository_root"], stage, active):
        raise ValueError("target_install_source_stage_active_overlap")
    verification = dict(stage_verification) if stage_verification is not None else verify_target_stage(
        target["repository_root"], target["canonical_root"], stage
    )
    if verification.get("status") != "passed":
        return {"status": "blocked", "blockers": ["target_stage_verification_failed"], "verification": verification}
    try:
        _validate_target_control_paths(home, target["skill_id"])
        with _InstallMutex(home, f"activate-target:{target['skill_id']}"):
            recovery = _recover_locked(home, target["skill_id"])
            if recovery["status"] != "passed":
                return {"status": "blocked", "blockers": ["target_recovery_failed"], "recovery": recovery}
            current_verification = verify_target_stage(
                target["repository_root"], target["canonical_root"], stage
            )
            if current_verification.get("stage_verification_hash") != verification.get("stage_verification_hash"):
                return {"status": "blocked", "blockers": ["target_stage_changed_after_verification"]}
            head = _load_head(home, target["skill_id"])
            transaction_id = f"target-install-{uuid.uuid4().hex}"
            active_budget = _stage_path_budget(active, target["member_paths"])
            incoming_budget = _stage_path_budget(
                Path(_record_paths(home, target["skill_id"], transaction_id)["incoming_root"]),
                target["member_paths"],
            )
            if active_budget["status"] != "passed" or incoming_budget["status"] != "passed":
                return {
                    "status": "blocked",
                    "skill_id": target["skill_id"],
                    "blockers": sorted(
                        set(active_budget["blockers"] + incoming_budget["blockers"])
                    ),
                    "active_path_budget": active_budget,
                    "incoming_path_budget": incoming_budget,
                }
            record: dict[str, Any] = {
                "schema_version": TARGET_TRANSACTION_SCHEMA,
                "transaction_id": transaction_id,
                "skill_id": target["skill_id"],
                "status": "prepared",
                "previous_transaction_id": head.get("transaction_id"),
                "previous_active_present": _path_entity_exists(active),
                "canonical_projection": target["projection"],
                "stage_projection": current_verification["stage_projection"],
                "member_paths_hash": target["member_paths_hash"],
                "member_count": len(target["member_paths"]),
                **_record_paths(home, target["skill_id"], transaction_id),
            }
            _validate_record_paths(home, record)
            record = _write_journal(home, record)
            incoming = Path(record["incoming_root"])
            backup = Path(record["backup_root"])
            try:
                _durable_mkdir(active.parent)
                _copy_projection(stage, incoming)
                record["status"] = "incoming_ready"
                record = _write_journal(home, record)
                if _path_entity_exists(active):
                    if _is_reparse_point(active) or not active.is_dir():
                        raise ValueError("target_install_active_root_unsafe")
                    _durable_mkdir(backup.parent)
                    _durable_rename(active, backup)
                record["status"] = "backup_ready"
                record = _write_journal(home, record)
                if os.environ.get("SKILLGUARD_TARGET_INSTALL_FAILPOINT") == "after_backup":
                    raise RuntimeError("target_install_failpoint_after_backup")
                _durable_rename(incoming, active)
                record["status"] = "activated"
                record = _write_journal(home, record)
                if os.environ.get("SKILLGUARD_TARGET_INSTALL_FAILPOINT") == "after_activation":
                    raise RuntimeError("target_install_failpoint_after_activation")
                record["status"] = "post_activation_verifying"
                record = _write_journal(home, record)
                comparison = _target_comparison(
                    target["canonical_root"], active
                )
                active_files = _portable_relative_files(active)
                if (
                    not _comparison_current(comparison)
                    or active_files != tuple(target["member_paths"])
                ):
                    raise ValueError("target_install_active_projection_mismatch")
                active_projection = installation_projection_identity(active)
                record["active_projection"] = active_projection
                record["status"] = "receipt_pending"
                record = _write_journal(home, record)
                receipt = _write_receipt(
                    home,
                    {
                        "schema_version": TARGET_RECEIPT_SCHEMA,
                        "transaction_id": transaction_id,
                        "skill_id": target["skill_id"],
                        "status": "committed",
                        "canonical_projection": target["projection"],
                        "stage_projection": current_verification["stage_projection"],
                        "active_projection": active_projection,
                        "member_paths_hash": target["member_paths_hash"],
                        "member_count": len(target["member_paths"]),
                        "previous_transaction_id": head.get("transaction_id"),
                        "previous_active_present": bool(record["previous_active_present"]),
                        "claim_boundary": "This receipt proves only one local exact-projection target activation and filesystem rollback boundary; it executes no target-native command and proves no release or publication.",
                    },
                )
                record["receipt_hash"] = receipt["receipt_hash"]
                new_head = _write_head(
                    home,
                    target["skill_id"],
                    transaction_id,
                    int(head.get("generation", 0)) + 1,
                    receipt["receipt_hash"],
                )
                record["status"] = "committed"
                record = _write_journal(home, record)
                return {
                    "status": "passed",
                    "skill_id": target["skill_id"],
                    "transaction_id": transaction_id,
                    "receipt": receipt,
                    "head": new_head,
                    "recovery": recovery,
                    "blockers": [],
                }
            except Exception as exc:
                diagnostic = _activation_exception_diagnostic(exc, phase=str(record.get("status", "unknown")))
                try:
                    restored = _restore_record(home, record, terminal_status="rolled_back")
                except Exception as restore_exc:
                    return {
                        "status": "blocked",
                        "skill_id": target["skill_id"],
                        "transaction_id": transaction_id,
                        "blockers": ["target_activation_failed", "target_rollback_failed"],
                        "diagnostic": diagnostic,
                        "rollback_error_kind": type(restore_exc).__name__,
                    }
                return {
                    "status": "blocked",
                    "skill_id": target["skill_id"],
                    "transaction_id": transaction_id,
                    "blockers": ["target_activation_failed"],
                    "diagnostic": diagnostic,
                    "restored_status": restored["status"],
                }
    except (InstallBusyError, UnsafeInstallPathError, OSError, ValueError) as exc:
        return {
            "status": "blocked",
            "skill_id": target["skill_id"],
            "blockers": [f"target_activation_preflight:{type(exc).__name__}"],
        }


def rollback_target_install(
    codex_home: Path, skill_id: str, transaction_id: str
) -> dict[str, Any]:
    home = codex_home.resolve()
    target_id = _safe_skill_id(skill_id)
    try:
        _validate_target_control_paths(home, target_id)
        with _InstallMutex(home, f"rollback-target:{target_id}"):
            record = _load_journal(home, target_id, transaction_id)
            if record.get("status") != "committed":
                return {"status": "blocked", "blockers": ["target_transaction_not_committed"]}
            head = _load_head(home, target_id)
            if head.get("transaction_id") != transaction_id:
                return {"status": "blocked", "blockers": ["target_transaction_not_head"]}
            active = Path(str(record.get("active_root", "")))
            if (
                not active.is_dir()
                or installation_projection_identity(active)
                != record.get("active_projection")
            ):
                return {"status": "blocked", "blockers": ["target_active_projection_drift"]}
            restored = _restore_record(
                home, record, terminal_status="manually_rolled_back"
            )
            return {
                "status": "passed",
                "skill_id": target_id,
                "transaction_id": transaction_id,
                "restored_status": restored["status"],
                "blockers": [],
            }
    except (InstallBusyError, UnsafeInstallPathError, OSError, ValueError) as exc:
        return {
            "status": "blocked",
            "skill_id": target_id,
            "transaction_id": transaction_id,
            "blockers": [f"target_rollback_failed:{type(exc).__name__}"],
        }


__all__ = [
    "activate_target_stage",
    "prepare_target_stage",
    "recover_target_installations",
    "rollback_target_install",
    "verify_target_stage",
]
