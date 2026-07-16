"""Current, component-scoped installed-content owner receipts.

The installation owner executes one exact projection comparison.  Portfolio
prepare may persist that immutable receipt once; later close and graduation
stages may only validate and replay its currentness.  A portfolio attempt id,
report, timestamp, log, or whole-tree source hash is never a freshness input.
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .installation import (
    INSTALLATION_PROJECTION_SCHEMA,
    compare_installation_projection_member,
)
from .portable_content import PORTABLE_CONTENT_POLICY_ID
from .runtime_authority import AUTHORITY_CURRENT, resolve_runtime_authority
from .wire_identity import wire_hash


INSTALLED_PARITY_RECEIPT_SCHEMA = (
    "skillguard.portfolio_installed_content_parity.current"
)
INSTALLED_PARITY_OWNER_ID = "owner:installed-content-parity"
MANIFEST_POLICY_ID = PORTABLE_CONTENT_POLICY_ID
VERIFIER_ID = "skillguard-installed-content-parity-current"

_TARGET_KINDS = frozenset({"single_skill", "skill_suite"})
_WIRE_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_PORTABLE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_PORTABLE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_DIAGNOSTIC_RE = re.compile(r"^[A-Za-z0-9._:/<>-]+$")

_RECEIPT_KEYS = frozenset(
    {
        "schema_version",
        "owner_id",
        "verifier_id",
        "manifest_policy_id",
        "portfolio_projection_hash",
        "target",
        "members",
        "status",
        "blockers",
        "claim_boundary",
        "receipt_id",
        "receipt_hash",
    }
)
_TARGET_KEYS = frozenset({"skill_id", "target_kind", "members"})
_TARGET_MEMBER_KEYS = frozenset({"member_skill_id", "skill_path"})
_MEMBER_KEYS = frozenset(
    {
        "member_skill_id",
        "skill_path",
        "projection_schema",
        "canonical_installation_projection",
        "installed_installation_projection",
        "canonical_authority",
        "installed_authority",
        "canonical_file_hashes",
        "installed_file_hashes",
        "missing_in_installed",
        "changed_in_installed",
        "unexpected_in_installed",
        "status",
    }
)
_PROJECTION_KEYS = frozenset(
    {
        "schema_version",
        "skill_id",
        "input_component_ids",
        "projection_declaration_hash",
        "input_projection_hash",
        "consumer_projection_hash",
        "identity_hash",
    }
)


def _wire_hash_ok(value: object) -> bool:
    return isinstance(value, str) and _WIRE_HASH_RE.fullmatch(value) is not None


def _portable_identifier(value: object) -> str | None:
    if not isinstance(value, str) or _PORTABLE_ID_RE.fullmatch(value) is None:
        return None
    return value


def _portable_skill_path(value: object) -> str | None:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        return None
    if value == ".":
        return value
    pure = PurePosixPath(value)
    if pure.is_absolute() or pure.as_posix() != value:
        return None
    if any(
        part in {"", ".", ".."} or _PORTABLE_SEGMENT_RE.fullmatch(part) is None
        for part in pure.parts
    ):
        return None
    return value


def _target_declaration(
    target_identity: object,
) -> tuple[dict[str, Any], tuple[tuple[str, str], ...], list[str]]:
    blockers: list[str] = []
    if not isinstance(target_identity, Mapping):
        return (
            {"skill_id": "", "target_kind": "", "members": []},
            (),
            ["target_identity_not_object"],
        )
    skill_id = _portable_identifier(target_identity.get("skill_id"))
    target_kind_value = target_identity.get("target_kind")
    target_kind = target_kind_value if isinstance(target_kind_value, str) else ""
    if skill_id is None:
        blockers.append("target_skill_id_invalid")
        skill_id = ""
    if target_kind not in _TARGET_KINDS:
        blockers.append("target_kind_invalid")
        target_kind = ""

    raw_members = target_identity.get("member_identities")
    members: list[tuple[str, str]] = []
    if not isinstance(raw_members, list) or not raw_members:
        blockers.append("target_members_missing")
    else:
        for raw_member in raw_members:
            if not isinstance(raw_member, Mapping):
                blockers.append("target_member_invalid")
                continue
            member_id = _portable_identifier(raw_member.get("member_skill_id"))
            skill_path = _portable_skill_path(raw_member.get("skill_path"))
            if member_id is None or skill_path is None:
                blockers.append("target_member_invalid")
                continue
            members.append((member_id, skill_path))
    if len({row[0] for row in members}) != len(members):
        blockers.append("target_member_id_duplicate")
    if len({row[1] for row in members}) != len(members):
        blockers.append("target_member_path_duplicate")
    declared_paths = target_identity.get("skill_paths")
    if not isinstance(declared_paths, list) or declared_paths != [
        path for _member_id, path in members
    ]:
        blockers.append("target_member_path_set_mismatch")
    if target_kind == "single_skill" and len(members) != 1:
        blockers.append("target_single_cardinality_invalid")
    if target_kind == "skill_suite" and len(members) < 2:
        blockers.append("target_suite_cardinality_invalid")
    declaration = {
        "skill_id": skill_id,
        "target_kind": target_kind,
        "members": [
            {"member_skill_id": member_id, "skill_path": skill_path}
            for member_id, skill_path in members
        ],
    }
    return declaration, tuple(members), list(dict.fromkeys(blockers))


def _member_projection(
    member_id: str,
    skill_path: str,
    canonical_root: Path,
    installed_root: Path,
) -> dict[str, Any]:
    comparison = compare_installation_projection_member(
        canonical_root,
        installed_root,
    )
    canonical_authority = resolve_runtime_authority(canonical_root)
    installed_authority = resolve_runtime_authority(installed_root)
    projection_current = comparison["status"] == "current"
    authority_current = (
        canonical_authority.ok
        and canonical_authority.authority == AUTHORITY_CURRENT
        and installed_authority.ok
        and installed_authority.authority == AUTHORITY_CURRENT
    )
    return {
        "member_skill_id": member_id,
        "skill_path": skill_path,
        "projection_schema": comparison["projection_schema"],
        "canonical_installation_projection": comparison[
            "canonical_installation_projection"
        ],
        "installed_installation_projection": comparison[
            "installed_installation_projection"
        ],
        "canonical_authority": canonical_authority.authority,
        "installed_authority": installed_authority.authority,
        "canonical_file_hashes": comparison["canonical_file_hashes"],
        "installed_file_hashes": comparison["installed_file_hashes"],
        "missing_in_installed": comparison["missing_in_installed"],
        "changed_in_installed": comparison["changed_in_installed"],
        "unexpected_in_installed": comparison["unexpected_in_installed"],
        "status": "current" if projection_current and authority_current else "blocked",
    }


def _semantic_receipt_payload(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: receipt[key]
        for key in (
            "schema_version",
            "owner_id",
            "verifier_id",
            "manifest_policy_id",
            "portfolio_projection_hash",
            "target",
            "members",
            "status",
            "blockers",
        )
    }


def _finalize_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    receipt["receipt_id"] = wire_hash(_semantic_receipt_payload(receipt))
    receipt["receipt_hash"] = wire_hash(receipt)
    return receipt


def verify_installed_content_parity(
    canonical_repository_root: Path | str,
    target_identity: Mapping[str, Any] | object,
    installed_target_root: Path | str,
    *,
    portfolio_projection_hash: str,
) -> dict[str, Any]:
    """Execute the one installation-projection owner comparison."""

    target, members, blockers = _target_declaration(target_identity)
    if not _wire_hash_ok(portfolio_projection_hash):
        blockers.append("portfolio_projection_hash_invalid")
    member_results: list[dict[str, Any]] = []
    try:
        canonical_root = Path(canonical_repository_root).resolve(strict=True)
        installed_root = Path(installed_target_root).resolve()
    except (OSError, RuntimeError, TypeError, ValueError):
        canonical_root = Path()
        installed_root = Path()
        blockers.append("root_role_resolution_failed")
    if not blockers:
        for member_id, skill_path in members:
            canonical_member = (canonical_root / Path(*PurePosixPath(skill_path).parts)).resolve()
            try:
                canonical_member.relative_to(canonical_root)
            except ValueError:
                blockers.append("canonical_member_root_escape")
                continue
            installed_member = (
                installed_root
                if target["target_kind"] == "single_skill"
                else (installed_root / member_id).resolve()
            )
            try:
                result = _member_projection(
                    member_id,
                    skill_path,
                    canonical_member,
                    installed_member,
                )
            except (OSError, UnicodeError, ValueError) as exc:
                blockers.append(
                    "installed_member_projection_invalid:"
                    + member_id
                    + ":"
                    + str(exc).split(":", 1)[0]
                )
                continue
            member_results.append(result)
            if result["canonical_authority"] != AUTHORITY_CURRENT:
                blockers.append(f"canonical_authority_blocked:{member_id}")
            if result["installed_authority"] != AUTHORITY_CURRENT:
                blockers.append(f"installed_authority_blocked:{member_id}")
            if result["status"] != "current":
                blockers.append(f"installed_member_not_current:{member_id}")
    blockers = list(dict.fromkeys(blockers))
    receipt: dict[str, Any] = {
        "schema_version": INSTALLED_PARITY_RECEIPT_SCHEMA,
        "owner_id": INSTALLED_PARITY_OWNER_ID,
        "verifier_id": VERIFIER_ID,
        "manifest_policy_id": MANIFEST_POLICY_ID,
        "portfolio_projection_hash": portfolio_projection_hash,
        "target": target,
        "members": member_results,
        "status": "current" if not blockers else "blocked",
        "blockers": blockers,
        "claim_boundary": (
            "This owner receipt proves exact parity only for each declared "
            "projection:installation. Source-only tests, models, notes, reports, "
            "receipts, logs, timestamps, and portfolio attempt ids are excluded."
        ),
    }
    return _finalize_receipt(receipt)


def _validate_projection(value: object, label: str, findings: list[str]) -> None:
    if not isinstance(value, Mapping) or set(value) != _PROJECTION_KEYS:
        findings.append(f"{label}_shape_invalid")
        return
    if value.get("schema_version") != INSTALLATION_PROJECTION_SCHEMA:
        findings.append(f"{label}_schema_invalid")
    if _portable_identifier(value.get("skill_id")) is None:
        findings.append(f"{label}_skill_id_invalid")
    component_ids = value.get("input_component_ids")
    if (
        not isinstance(component_ids, list)
        or not component_ids
        or component_ids != sorted(component_ids)
        or len(component_ids) != len(set(component_ids))
        or any(_portable_identifier(item) is None for item in component_ids)
    ):
        findings.append(f"{label}_component_ids_invalid")
    for field in (
        "projection_declaration_hash",
        "input_projection_hash",
        "consumer_projection_hash",
        "identity_hash",
    ):
        if not _wire_hash_ok(value.get(field)):
            findings.append(f"{label}_{field}_invalid")
    unsigned = dict(value)
    stored_identity = unsigned.pop("identity_hash", None)
    if stored_identity != wire_hash(unsigned):
        findings.append(f"{label}_identity_hash_mismatch")


def _validate_hash_map(value: object, label: str, findings: list[str]) -> dict[str, str]:
    if not isinstance(value, Mapping):
        findings.append(f"{label}_invalid")
        return {}
    normalized: dict[str, str] = {}
    for key, item in value.items():
        path = _portable_skill_path(key)
        if path in {None, "."} or not _wire_hash_ok(item):
            findings.append(f"{label}_entry_invalid")
            continue
        normalized[path] = str(item)
    if list(value) != sorted(value) or len(normalized) != len(value):
        findings.append(f"{label}_ordering_invalid")
    return normalized


def _validate_path_list(value: object, label: str, findings: list[str]) -> list[str]:
    if (
        not isinstance(value, list)
        or value != sorted(value)
        or len(value) != len(set(value))
        or any(_portable_skill_path(item) in {None, "."} for item in value)
    ):
        findings.append(f"{label}_invalid")
        return []
    return [str(item) for item in value]


def validate_installed_parity_receipt(
    receipt: object,
    *,
    portfolio_projection_hash: str | None = None,
) -> list[str]:
    """Validate one immutable current receipt without executing its owner."""

    findings: list[str] = []
    if not isinstance(receipt, Mapping):
        return ["installed_parity_receipt_not_object"]
    if set(receipt) != _RECEIPT_KEYS:
        findings.append("installed_parity_receipt_structure_invalid")
    if receipt.get("schema_version") != INSTALLED_PARITY_RECEIPT_SCHEMA:
        findings.append("installed_parity_receipt_schema_unsupported")
    if receipt.get("owner_id") != INSTALLED_PARITY_OWNER_ID:
        findings.append("installed_parity_receipt_owner_invalid")
    if receipt.get("verifier_id") != VERIFIER_ID:
        findings.append("installed_parity_receipt_verifier_invalid")
    if receipt.get("manifest_policy_id") != MANIFEST_POLICY_ID:
        findings.append("installed_parity_receipt_manifest_policy_invalid")
    stored_portfolio_hash = receipt.get("portfolio_projection_hash")
    if not _wire_hash_ok(stored_portfolio_hash):
        findings.append("installed_parity_receipt_portfolio_projection_invalid")
    if portfolio_projection_hash is not None:
        if not _wire_hash_ok(portfolio_projection_hash):
            findings.append("expected_portfolio_projection_hash_invalid")
        elif stored_portfolio_hash != portfolio_projection_hash:
            findings.append("installed_parity_receipt_portfolio_projection_stale")

    target = receipt.get("target")
    target_members: list[tuple[str, str]] = []
    target_kind = ""
    if not isinstance(target, Mapping) or set(target) != _TARGET_KEYS:
        findings.append("installed_parity_receipt_target_invalid")
    else:
        if _portable_identifier(target.get("skill_id")) is None:
            findings.append("installed_parity_receipt_target_skill_id_invalid")
        target_kind = str(target.get("target_kind", ""))
        if target_kind not in _TARGET_KINDS:
            findings.append("installed_parity_receipt_target_kind_invalid")
        raw_target_members = target.get("members")
        if not isinstance(raw_target_members, list) or not raw_target_members:
            findings.append("installed_parity_receipt_target_members_invalid")
        else:
            for row in raw_target_members:
                if not isinstance(row, Mapping) or set(row) != _TARGET_MEMBER_KEYS:
                    findings.append("installed_parity_receipt_target_member_invalid")
                    continue
                member_id = _portable_identifier(row.get("member_skill_id"))
                skill_path = _portable_skill_path(row.get("skill_path"))
                if member_id is None or skill_path is None:
                    findings.append("installed_parity_receipt_target_member_invalid")
                    continue
                target_members.append((member_id, skill_path))
        if len(target_members) != len(set(target_members)):
            findings.append("installed_parity_receipt_target_member_duplicate")
        if target_kind == "single_skill" and len(target_members) != 1:
            findings.append("installed_parity_receipt_single_cardinality_invalid")
        if target_kind == "skill_suite" and len(target_members) < 2:
            findings.append("installed_parity_receipt_suite_cardinality_invalid")

    members = receipt.get("members")
    validated_members: list[tuple[str, str, str]] = []
    if not isinstance(members, list):
        findings.append("installed_parity_receipt_members_invalid")
    else:
        for index, member in enumerate(members):
            label = f"installed_parity_member_{index}"
            if not isinstance(member, Mapping) or set(member) != _MEMBER_KEYS:
                findings.append(f"{label}_structure_invalid")
                continue
            member_id = _portable_identifier(member.get("member_skill_id"))
            skill_path = _portable_skill_path(member.get("skill_path"))
            if member_id is None or skill_path is None:
                findings.append(f"{label}_declaration_invalid")
                continue
            if member.get("projection_schema") != INSTALLATION_PROJECTION_SCHEMA:
                findings.append(f"{label}_projection_schema_invalid")
            canonical_projection = member.get("canonical_installation_projection")
            installed_projection = member.get("installed_installation_projection")
            canonical_authority = member.get("canonical_authority")
            installed_authority = member.get("installed_authority")
            if canonical_authority not in {AUTHORITY_CURRENT, "blocked"}:
                findings.append(f"{label}_canonical_authority_invalid")
            if installed_authority not in {AUTHORITY_CURRENT, "blocked"}:
                findings.append(f"{label}_installed_authority_invalid")
            _validate_projection(canonical_projection, f"{label}_canonical", findings)
            _validate_projection(installed_projection, f"{label}_installed", findings)
            if isinstance(canonical_projection, Mapping) and canonical_projection.get(
                "skill_id"
            ) != member_id:
                findings.append(f"{label}_canonical_skill_id_mismatch")
            if isinstance(installed_projection, Mapping) and installed_projection.get(
                "skill_id"
            ) != member_id:
                findings.append(f"{label}_installed_skill_id_mismatch")
            canonical_files = _validate_hash_map(
                member.get("canonical_file_hashes"), f"{label}_canonical_files", findings
            )
            installed_files = _validate_hash_map(
                member.get("installed_file_hashes"), f"{label}_installed_files", findings
            )
            missing = _validate_path_list(
                member.get("missing_in_installed"), f"{label}_missing", findings
            )
            changed = _validate_path_list(
                member.get("changed_in_installed"), f"{label}_changed", findings
            )
            unexpected = _validate_path_list(
                member.get("unexpected_in_installed"), f"{label}_unexpected", findings
            )
            expected_missing = sorted(set(canonical_files) - set(installed_files))
            expected_changed = sorted(
                path
                for path in set(canonical_files) & set(installed_files)
                if canonical_files[path] != installed_files[path]
            )
            expected_unexpected = sorted(set(installed_files) - set(canonical_files))
            if missing != expected_missing:
                findings.append(f"{label}_missing_mismatch")
            if changed != expected_changed:
                findings.append(f"{label}_changed_mismatch")
            if unexpected != expected_unexpected:
                findings.append(f"{label}_unexpected_mismatch")
            current = (
                canonical_projection == installed_projection
                and not missing
                and not changed
                and not unexpected
                and canonical_authority == AUTHORITY_CURRENT
                and installed_authority == AUTHORITY_CURRENT
            )
            expected_status = "current" if current else "blocked"
            if member.get("status") != expected_status:
                findings.append(f"{label}_status_mismatch")
            validated_members.append((member_id, skill_path, expected_status))
    if [(row[0], row[1]) for row in validated_members] != target_members:
        findings.append("installed_parity_receipt_member_declaration_mismatch")

    blockers = receipt.get("blockers")
    if (
        not isinstance(blockers, list)
        or len(blockers) != len(set(blockers))
        or any(
            not isinstance(item, str)
            or not item
            or _DIAGNOSTIC_RE.fullmatch(item) is None
            for item in blockers
        )
    ):
        findings.append("installed_parity_receipt_blockers_invalid")
        blockers = []
    expected_current = (
        not blockers
        and bool(validated_members)
        and all(row[2] == "current" for row in validated_members)
        and [(row[0], row[1]) for row in validated_members] == target_members
    )
    expected_status = "current" if expected_current else "blocked"
    if receipt.get("status") != expected_status:
        findings.append("installed_parity_receipt_status_mismatch")
    if not isinstance(receipt.get("claim_boundary"), str) or not str(
        receipt.get("claim_boundary", "")
    ).strip():
        findings.append("installed_parity_receipt_claim_boundary_invalid")
    try:
        if receipt.get("receipt_id") != wire_hash(_semantic_receipt_payload(receipt)):
            findings.append("installed_parity_receipt_id_mismatch")
        unsigned = dict(receipt)
        stored_hash = unsigned.pop("receipt_hash", None)
        if stored_hash != wire_hash(unsigned):
            findings.append("installed_parity_receipt_hash_mismatch")
    except (KeyError, TypeError, ValueError):
        findings.append("installed_parity_receipt_identity_unavailable")
    return list(dict.fromkeys(findings))


def replay_installed_content_parity_currentness(
    receipt: object,
    *,
    canonical_repository_root: Path | str,
    target_identity: Mapping[str, Any] | object,
    installed_target_root: Path | str,
    portfolio_projection_hash: str,
) -> list[str]:
    """Read-only currentness replay; never persists or reissues a receipt."""

    findings = validate_installed_parity_receipt(
        receipt,
        portfolio_projection_hash=portfolio_projection_hash,
    )
    if findings:
        return findings
    assert isinstance(receipt, Mapping)
    fresh = verify_installed_content_parity(
        canonical_repository_root,
        target_identity,
        installed_target_root,
        portfolio_projection_hash=portfolio_projection_hash,
    )
    fresh_findings = validate_installed_parity_receipt(
        fresh,
        portfolio_projection_hash=portfolio_projection_hash,
    )
    findings.extend(fresh_findings)
    if fresh.get("status") != "current":
        findings.extend(str(value) for value in fresh.get("blockers", []))
    if fresh.get("receipt_id") != receipt.get("receipt_id"):
        findings.append("installed_parity_receipt_stale")
    return list(dict.fromkeys(findings))


def installed_parity_receipt_hash_current(receipt: object) -> bool:
    if not isinstance(receipt, Mapping):
        return False
    unsigned = dict(receipt)
    stored_hash = unsigned.pop("receipt_hash", None)
    return _wire_hash_ok(stored_hash) and stored_hash == wire_hash(unsigned)


__all__ = [
    "INSTALLED_PARITY_OWNER_ID",
    "INSTALLED_PARITY_RECEIPT_SCHEMA",
    "MANIFEST_POLICY_ID",
    "installed_parity_receipt_hash_current",
    "replay_installed_content_parity_currentness",
    "validate_installed_parity_receipt",
    "verify_installed_content_parity",
]
