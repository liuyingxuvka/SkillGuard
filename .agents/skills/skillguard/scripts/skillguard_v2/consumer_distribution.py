"""Build and verify independently usable target-skill consumer distributions."""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .contract_compiler import canonical_hash as _author_record_hash
from .wire_identity import (
    CONSUMER_RELEASE_WIRE_POLICY_ID,
    consumer_release_canonical_json_bytes,
    consumer_release_wire_hash,
    is_consumer_release_wire_hash,
)


CONSUMER_RELEASE_SCHEMA = "consumer.skill_distribution.current"
DEFAULT_RELEASE_MANIFEST = "consumer-release.json"
CONSUMER_RELEASE_MANIFEST_KEYS = frozenset(
    {
        "schema_version",
        "skill_id",
        "projection_id",
        "files",
        "author_control_excluded",
        "release_id",
        "claim_boundary",
        "manifest_hash",
    }
)
TEXT_SUFFIXES = frozenset(
    {
        ".md",
        ".txt",
        ".json",
        ".jsonl",
        ".yaml",
        ".yml",
        ".toml",
        ".py",
        ".ps1",
        ".sh",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".html",
        ".css",
        ".xml",
        ".ini",
        ".cfg",
    }
)
ALWAYS_EXCLUDED_NAMES = frozenset(
    {".git", ".hg", ".svn", "__pycache__", ".pytest_cache", ".mypy_cache"}
)
AUTHOR_CONTROL_PREFIXES = (".skillguard/",)
FORBIDDEN_RUNTIME_PATTERNS = (
    ("consumer_skillguard_path_reference", re.compile(r"(?i)(?:^|[\\/'\"`])\.skillguard(?:[\\/]|$)")),
    # ``\bskillguard\b`` misses structured names such as
    # ``skillguard_version`` because underscore is a word character.  The
    # negative look-behind plus explicit separators covers command text,
    # dotted modules, and author-control identity keys.
    ("consumer_skillguard_command_reference", re.compile(r"(?i)(?<![a-z0-9])skillguard(?:\.py|[_./:-]|\b)")),
    ("consumer_skillguard_import_reference", re.compile(r"(?im)^\s*(?:from|import)\s+skillguard(?:\b|\.)")),
    ("consumer_portfolio_authority_reference", re.compile(r"(?i)\bportfolio[_ -](?:receipt|reuse|evidence|graduation)\b")),
    ("consumer_author_identity_field_reference", re.compile(r"(?i)\b(?:maintenance_unit_id|source_contract_hash|contract_source_hash|contract_hash|contract_source_sha256|check_manifest_hash|check_manifest_sha256|check_declarations_hash|portfolio_(?:receipt|reuse|evidence|graduation)(?:_id|_hash|_ref)?)\b")),
)
_RETIRED_SENTINEL_RE = re.compile(
    r"(?is)(?=.*\b(?:retired|negative|sentinel)\b)(?=.*\bnot[ -]?runtime\b)"
)


def _is_retired_sentinel(path: Path, text: str | None) -> bool:
    """Recognize the one explicit negative fixture allowed to mention SkillGuard.

    A file named ``skillguard_depth.py`` is otherwise forbidden in a consumer
    tree.  It is allowed only when its own text labels it as retired/negative
    and not runtime; import/command references are still rejected by the text
    scanner below.
    """

    return (
        path.name.casefold() == "skillguard_depth.py"
        and text is not None
        and bool(_RETIRED_SENTINEL_RE.search(text))
    )


def _text_reference_findings(path: Path, text: str) -> list[tuple[str, str]]:
    """Return forbidden consumer references, including structured keys.

    A retired ``skillguard_depth.py`` sentinel is an explicit negative-path
    fixture, not a runtime dependency.  It is allowed only when its own text
    declares that status and it has no actual SkillGuard import.
    """

    findings: list[tuple[str, str]] = []
    sentinel = _is_retired_sentinel(path, text)
    for code, pattern in FORBIDDEN_RUNTIME_PATTERNS:
        if sentinel and code == "consumer_skillguard_command_reference":
            continue
        if pattern.search(text):
            findings.append((code, "consumer files must not require or instruct use of author-side SkillGuard state"))
    if path.suffix.casefold() == ".json":
        try:
            payload = json.loads(text)
        except (TypeError, ValueError):
            payload = None

        def visit(value: object, location: str = "$") -> None:
            if isinstance(value, Mapping):
                for key, child in value.items():
                    key_text = str(key)
                    if "skillguard" in key_text.casefold() and not sentinel:
                        findings.append(("consumer_author_identity_field_reference", f"author-control key {location}.{key_text}"))
                    visit(child, f"{location}.{key_text}")
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    visit(child, f"{location}[{index}]")

        visit(payload)
    return findings


@dataclass(frozen=True)
class ConsumerDistributionFinding:
    code: str
    path: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "detail": self.detail}


def _relative_files(root: Path) -> tuple[tuple[str, Path], ...]:
    rows: list[tuple[str, Path]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in ALWAYS_EXCLUDED_NAMES for part in relative.parts):
            continue
        if path.is_symlink():
            rows.append((relative.as_posix(), path))
        elif path.is_file():
            rows.append((relative.as_posix(), path))
    return tuple(rows)


def _file_hash(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _consumer_release_identity(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": manifest.get("schema_version"),
        "skill_id": manifest.get("skill_id"),
        "projection_id": manifest.get("projection_id"),
        "files": manifest.get("files"),
        "author_control_excluded": manifest.get("author_control_excluded"),
    }


def _manifest_file_rows(
    manifest: Mapping[str, Any], findings: list[ConsumerDistributionFinding]
) -> list[dict[str, str]]:
    """Validate the manifest's file inventory before using it as authority.

    A self-resealed manifest is not automatically trustworthy: its member list
    must itself be a canonical, safe, one-row-per-path inventory.  Otherwise a
    producer can make a malformed or author-controlled projection look current
    merely by recomputing both hashes.
    """

    value = manifest.get("files")
    if not isinstance(value, list):
        findings.append(
            ConsumerDistributionFinding(
                "consumer_release_manifest_files_invalid",
                DEFAULT_RELEASE_MANIFEST,
                "files must be a list of canonical path/hash rows",
            )
        )
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    previous_path = ""
    for index, item in enumerate(value):
        row_path = f"{DEFAULT_RELEASE_MANIFEST}.files[{index}]"
        if not isinstance(item, Mapping) or set(item) != {"path", "content_hash"}:
            findings.append(
                ConsumerDistributionFinding(
                    "consumer_release_manifest_file_row_invalid",
                    row_path,
                    "each files entry must contain exactly path and content_hash",
                )
            )
            continue
        path_value = item.get("path")
        content_hash = item.get("content_hash")
        if not isinstance(path_value, str) or not path_value:
            findings.append(
                ConsumerDistributionFinding(
                    "consumer_release_manifest_file_path_invalid",
                    row_path,
                    "file paths must be non-empty relative POSIX paths",
                )
            )
            path_value = str(path_value or "")
        normalized = path_value.replace("\\", "/")
        path_parts = normalized.split("/")
        if (
            normalized != path_value
            or normalized.startswith("/")
            or bool(re.match(r"^[A-Za-z]:", normalized))
            or any(part in {"", ".", ".."} for part in path_parts)
        ):
            findings.append(
                ConsumerDistributionFinding(
                    "consumer_release_manifest_file_path_invalid",
                    row_path,
                    "file paths must be normalized, relative, and traversal-free",
                )
            )
        if normalized in seen:
            findings.append(
                ConsumerDistributionFinding(
                    "consumer_release_manifest_file_duplicate",
                    row_path,
                    normalized,
                )
            )
        seen.add(normalized)
        if previous_path and normalized < previous_path:
            findings.append(
                ConsumerDistributionFinding(
                    "consumer_release_manifest_files_noncanonical",
                    row_path,
                    "file rows must be sorted by path",
                )
            )
        previous_path = normalized
        if not is_consumer_release_wire_hash(content_hash):
            findings.append(
                ConsumerDistributionFinding(
                    "consumer_release_file_hash_format_invalid",
                    normalized,
                    "content_hash must be lowercase sha256:<64 hex> wire identity",
                )
            )
        rows.append({"path": normalized, "content_hash": str(content_hash or "")})
    return rows


def _read_text(path: Path) -> str | None:
    if path.suffix.lower() not in TEXT_SUFFIXES and path.name != "SKILL.md":
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


def consumer_distribution_plan(
    skill_root: Path,
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the exact consumer file inventory and all pre-copy blockers."""

    root = skill_root.resolve()
    projection = contract.get("consumer_projection", {})
    if not isinstance(projection, Mapping):
        projection = {}
    release_manifest_path = str(
        projection.get("release_manifest_path", DEFAULT_RELEASE_MANIFEST)
    )
    impact_plan = contract.get("content_impact_plan", {})
    inventory_dispositions: dict[str, str] = {}
    member_root_path = "."
    if isinstance(impact_plan, Mapping):
        member_root_path = str(impact_plan.get("member_root_path", ".")).strip("/")
        inventory_dispositions = {
            str(row.get("path", "")).replace("\\", "/"): str(
                row.get("install_disposition", "")
            )
            for row in impact_plan.get("inventory", [])
            if isinstance(row, Mapping)
        }
    findings: list[ConsumerDistributionFinding] = []
    files: list[dict[str, str]] = []
    stranded_runtime_root = root / ".skillguard" / "runtime"
    if stranded_runtime_root.is_dir():
        for relative, path in _relative_files(stranded_runtime_root):
            findings.append(
                ConsumerDistributionFinding(
                    "target_runtime_stranded_in_author_control",
                    f".skillguard/runtime/{relative}",
                    "move target-domain runtime into a target-owned namespace before graduation",
                )
            )
    for relative, path in _relative_files(root):
        normalized = relative.replace("\\", "/")
        if normalized == release_manifest_path:
            findings.append(
                ConsumerDistributionFinding(
                    "consumer_release_manifest_source_collision",
                    normalized,
                    "the release manifest is generated by the consumer builder",
                )
            )
            continue
        if any(normalized == prefix.rstrip("/") or normalized.startswith(prefix) for prefix in AUTHOR_CONTROL_PREFIXES):
            continue
        inventory_path = (
            normalized
            if member_root_path in {"", "."}
            else f"{member_root_path}/{normalized}"
        )
        if inventory_dispositions.get(inventory_path) == "source_only":
            continue
        text = _read_text(path)
        if "skillguard" in normalized.lower() and not _is_retired_sentinel(path, text):
            findings.append(
                ConsumerDistributionFinding(
                    "consumer_author_control_name_present",
                    normalized,
                    "consumer paths must use target-owned names",
                )
            )
        if path.is_symlink():
            findings.append(
                ConsumerDistributionFinding(
                    "consumer_symlink_forbidden",
                    normalized,
                    "consumer distributions contain regular files only",
                )
            )
            continue
        if text is not None:
            for code, detail in _text_reference_findings(path, text):
                findings.append(ConsumerDistributionFinding(code, normalized, detail))
        files.append({"path": normalized, "content_hash": _file_hash(path)})
    files.sort(key=lambda row: row["path"])
    identity = {
        "schema_version": CONSUMER_RELEASE_SCHEMA,
        "skill_id": str(contract.get("skill_id", "")),
        "projection_id": "projection:consumer-distribution",
        "files": files,
        "author_control_excluded": True,
    }
    release_id = consumer_release_wire_hash(identity)
    return {
        **identity,
        "release_id": release_id,
        "release_manifest_path": release_manifest_path,
        "author_maintenance_binding": {
            "maintenance_unit_id": str(contract.get("maintenance_unit_id", "")),
            "source_contract_hash": str(contract.get("contract_hash", "")),
        },
        "status": "blocked" if findings else "passed",
        "findings": [finding.to_dict() for finding in findings],
    }


def build_consumer_distribution(
    skill_root: Path,
    destination_root: Path,
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Create a new consumer tree only after a complete no-author-control preflight."""

    source = skill_root.resolve()
    destination = destination_root.absolute()
    plan = consumer_distribution_plan(source, contract)
    if plan["status"] != "passed":
        return plan
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("consumer_distribution_destination_exists")
    destination.mkdir(parents=True, exist_ok=False)
    try:
        for row in plan["files"]:
            relative = Path(*str(row["path"]).split("/"))
            source_path = (source / relative).resolve(strict=True)
            if not source_path.is_relative_to(source) or not source_path.is_file():
                raise ValueError("consumer_distribution_source_member_unsafe")
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target)
        manifest = {
            key: plan[key]
            for key in (
                "schema_version",
                "skill_id",
                "projection_id",
                "release_id",
                "files",
                "author_control_excluded",
            )
        }
        manifest["claim_boundary"] = (
            "This manifest identifies target-owned consumer files only. It carries no "
            "author contract, receipt, router, session, cache, or execution authority."
        )
        manifest["manifest_hash"] = consumer_release_wire_hash(manifest)
        manifest_path = destination / str(plan["release_manifest_path"])
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = manifest_path.with_name(
            f".{manifest_path.name}.{os.getpid()}.tmp"
        )
        temporary.write_bytes(consumer_release_canonical_json_bytes(manifest) + b"\n")
        os.replace(temporary, manifest_path)
    except Exception:
        shutil.rmtree(destination)
        raise
    return audit_consumer_distribution(destination)


def audit_consumer_distribution(root: Path) -> dict[str, Any]:
    """Verify one built or installed consumer tree without executing it."""

    tree = root.resolve()
    manifest_path = tree / DEFAULT_RELEASE_MANIFEST
    findings: list[ConsumerDistributionFinding] = []
    if not manifest_path.is_file():
        return {
            "schema_version": CONSUMER_RELEASE_SCHEMA,
            "status": "blocked",
            "findings": [
                ConsumerDistributionFinding(
                    "consumer_release_manifest_missing",
                    DEFAULT_RELEASE_MANIFEST,
                    "consumer distribution identity is absent",
                ).to_dict()
            ],
        }
    try:
        manifest_raw = manifest_path.read_bytes()
        manifest = json.loads(manifest_raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        manifest_raw = b""
        manifest = {}
    if not isinstance(manifest, dict):
        manifest = {}
    unsigned = dict(manifest)
    stored_hash = unsigned.pop("manifest_hash", None)
    identity = _consumer_release_identity(manifest)
    expected_release_id = consumer_release_wire_hash(identity)
    expected_manifest_hash = consumer_release_wire_hash(unsigned)
    if (
        manifest.get("schema_version") != CONSUMER_RELEASE_SCHEMA
        or manifest.get("projection_id") != "projection:consumer-distribution"
        or manifest.get("author_control_excluded") is not True
    ):
        findings.append(
            ConsumerDistributionFinding(
                "consumer_release_manifest_invalid",
                DEFAULT_RELEASE_MANIFEST,
                "manifest schema, projection, or immutable hash is invalid",
            )
        )
    if set(manifest) != CONSUMER_RELEASE_MANIFEST_KEYS:
        findings.append(
            ConsumerDistributionFinding(
                "consumer_release_manifest_fields_invalid",
                DEFAULT_RELEASE_MANIFEST,
                "manifest fields must contain only the current target-owned release identity",
            )
        )
    if not isinstance(manifest.get("skill_id"), str) or not str(
        manifest.get("skill_id", "")
    ).strip():
        findings.append(
            ConsumerDistributionFinding(
                "consumer_release_manifest_skill_id_invalid",
                DEFAULT_RELEASE_MANIFEST,
                "skill_id must be a non-empty target-owned identifier",
            )
        )
    if not isinstance(manifest.get("claim_boundary"), str) or not str(
        manifest.get("claim_boundary", "")
    ).strip():
        findings.append(
            ConsumerDistributionFinding(
                "consumer_release_manifest_claim_boundary_invalid",
                DEFAULT_RELEASE_MANIFEST,
                "claim_boundary must state the consumer-only evidence boundary",
            )
        )
    if manifest_raw != consumer_release_canonical_json_bytes(manifest) + b"\n":
        findings.append(
            ConsumerDistributionFinding(
                "consumer_release_manifest_noncanonical",
                DEFAULT_RELEASE_MANIFEST,
                "manifest bytes must be compact canonical JSON followed by exactly one LF newline",
            )
        )
    if not is_consumer_release_wire_hash(stored_hash):
        findings.append(
            ConsumerDistributionFinding(
                "consumer_release_manifest_hash_format_invalid",
                DEFAULT_RELEASE_MANIFEST,
                "manifest_hash must be lowercase sha256:<64 hex> wire identity",
            )
        )
    elif stored_hash != expected_manifest_hash:
        findings.append(
            ConsumerDistributionFinding(
                "consumer_release_manifest_hash_invalid",
                DEFAULT_RELEASE_MANIFEST,
                "manifest_hash does not match the canonical unsigned manifest",
            )
        )
    stored_release_id = manifest.get("release_id")
    if not is_consumer_release_wire_hash(stored_release_id):
        findings.append(
            ConsumerDistributionFinding(
                "consumer_release_release_id_format_invalid",
                DEFAULT_RELEASE_MANIFEST,
                "release_id must be lowercase sha256:<64 hex> wire identity",
            )
        )
    elif stored_release_id != expected_release_id:
        findings.append(
            ConsumerDistributionFinding(
                "consumer_release_release_id_invalid",
                DEFAULT_RELEASE_MANIFEST,
                "release_id does not match the canonical consumer identity",
            )
        )
    expected = {
        row["path"]: row["content_hash"]
        for row in _manifest_file_rows(manifest, findings)
    }
    actual: dict[str, str] = {}
    for relative, path in _relative_files(tree):
        normalized = relative.replace("\\", "/")
        if normalized == DEFAULT_RELEASE_MANIFEST:
            continue
        if normalized.startswith(".skillguard/") or normalized == ".skillguard":
            findings.append(
                ConsumerDistributionFinding(
                    "consumer_author_control_path_present",
                    normalized,
                    "consumer trees must contain zero .skillguard paths",
                )
            )
            continue
        text = _read_text(path)
        if "skillguard" in normalized.lower() and not _is_retired_sentinel(path, text):
            findings.append(
                ConsumerDistributionFinding(
                    "consumer_author_control_name_present",
                    normalized,
                    "consumer paths must use target-owned names",
                )
            )
        if path.is_symlink():
            findings.append(
                ConsumerDistributionFinding(
                    "consumer_symlink_forbidden",
                    normalized,
                    "consumer distributions contain regular files only",
                )
            )
            continue
        actual[normalized] = _file_hash(path)
        if text is not None:
            for code, detail in _text_reference_findings(path, text):
                findings.append(ConsumerDistributionFinding(code, normalized, detail))
    for missing in sorted(set(expected) - set(actual)):
        findings.append(
            ConsumerDistributionFinding(
                "consumer_file_missing",
                missing,
                "declared consumer file is absent",
            )
        )
    for unexpected in sorted(set(actual) - set(expected)):
        findings.append(
            ConsumerDistributionFinding(
                "consumer_file_unexpected",
                unexpected,
                "file is outside the frozen consumer release",
            )
        )
    for path in sorted(set(expected) & set(actual)):
        if expected[path] != actual[path]:
            findings.append(
                ConsumerDistributionFinding(
                    "consumer_file_hash_mismatch",
                    path,
                    "consumer file differs from the frozen release",
                )
            )
    return {
        "schema_version": CONSUMER_RELEASE_SCHEMA,
        "status": "blocked" if findings else "passed",
        "skill_id": str(manifest.get("skill_id", "")),
        "release_id": str(manifest.get("release_id", "")),
        "member_count": len(actual),
        # This is a SkillGuard diagnostic projection, not a consumer-release
        # identity.  Keep it on the author-record hash authority so it cannot
        # accidentally become part of the cross-project wire protocol.
        "member_paths_hash": _author_record_hash(sorted(actual)),
        "findings": [finding.to_dict() for finding in findings],
        "manifest": manifest,
    }
