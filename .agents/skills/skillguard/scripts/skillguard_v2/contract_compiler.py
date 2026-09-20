"""Deterministic compiler for the standalone SkillGuard contract.

The current compiler consumes exactly one ``skillguard.skill_contract.v3``
source. It does not import, inspect, or execute a second model system.
Small identity helpers remain here because the native check/evidence modules
use the same author-record wire format.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .compact_contract import SCHEMA_VERSION, compile_direct_contract
from .content_projection import (
    current_content_projection,
    current_content_projection_from_files,
    impact_file_hash,
    source_file_hash,
)
from .path_identity import canonical_filesystem_path, physical_relative_path
from .portable_content import (
    PORTABLE,
    classify_member_path,
    portable_files,
    scan_member_boundary,
)
from .wire_identity import canonical_json_bytes, wire_hash
from .contract_schema import SchemaFinding


BINDING_SOURCE_FILE = "contract-source.json"
COMPILED_CONTRACT_FILE = "compiled-contract.json"
CHECK_MANIFEST_FILE = "check-manifest.json"
COMPILER_VERSION = "skillguard.contract_compiler.v3"
OWNER_BEHAVIOR_FIELDS = (
    "maintenance_unit_id",
    "member_skill_id",
    "kind",
    "command",
    "args",
    "cwd_token",
    "cwd_relative",
    "environment",
    "expected",
    "assertion_scope",
    "native_route_id",
    "applicable",
)


def _is_transient_implementation_output(relative: Path) -> bool:
    transient_parts = {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".skillguard",
        "__pycache__",
        "node_modules",
    }
    if set(relative.parts) & transient_parts:
        return True
    if any(part.casefold().endswith(".egg-info") for part in relative.parts):
        return True
    if relative.suffix.lower() in {".pyc", ".pyo"}:
        return True
    if relative.name in {".DS_Store", "Thumbs.db"}:
        return True
    return "openspec" in relative.parts and "changes" in relative.parts and (
        relative.name == "tasks.md" or "evidence" in relative.parts
    )


@dataclass(frozen=True)
class CompileResult:
    ok: bool
    status: str
    findings: tuple[SchemaFinding, ...]
    compiled_contract: Mapping[str, Any] | None = None
    check_manifest: Mapping[str, Any] | None = None
    written_files: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "skillguard_compact_compile_report",
            "ok": self.ok,
            "status": self.status,
            "findings": [row.to_dict() for row in self.findings],
            "contract_hash": str(self.compiled_contract.get("contract_hash", ""))
            if self.compiled_contract
            else "",
            "manifest_hash": str(self.check_manifest.get("manifest_hash", ""))
            if self.check_manifest
            else "",
            "written_files": list(self.written_files),
            "claim_boundary": (
                "Compilation derives one explicit contract. It does not execute checks "
                "or prove installation or publication closure."
            ),
        }


def canonical_hash(payload: object) -> str:
    """Return the uppercase author-record hash used by existing receipts."""

    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest().upper()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def path_fingerprint(path: Path, *, member_root: Path | None = None) -> str:
    """Fingerprint one portable file or directory without loading a model."""

    path = path.resolve()
    if path.is_file():
        root = (member_root or path.parent).resolve(strict=True)
        decision = classify_member_path(root, path)
        if decision.classification != PORTABLE:
            raise ValueError(
                f"implementation file portable boundary is blocked: {decision.reason}:{path.name}"
            )
        return source_file_hash(path)
    if path.is_dir():
        boundary = scan_member_boundary(path)
        if not boundary.ok:
            raise ValueError("implementation path portable boundary is blocked")
        rows = [
            {"path": relative.as_posix(), "sha256": source_file_hash(child)}
            for relative, child in portable_files(path)
            if not _is_transient_implementation_output(relative)
        ]
        return canonical_hash(rows)
    raise ValueError(f"implementation path is missing: {path}")


def compile_skill_contract(
    skill_root: Path,
    *,
    repository_root: Path | None = None,
    write: bool = False,
) -> CompileResult:
    """Compile the one current source contract and nothing else."""

    del repository_root
    skill_root = skill_root.resolve()
    binding_path = skill_root / ".skillguard" / BINDING_SOURCE_FILE
    try:
        source = json.loads(binding_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return CompileResult(
            False,
            "blocked",
            (SchemaFinding("binding_source_missing", "$.binding", str(binding_path)),),
        )
    except (OSError, json.JSONDecodeError) as exc:
        return CompileResult(
            False,
            "blocked",
            (SchemaFinding("binding_source_unreadable", "$.binding", str(exc)),),
        )
    if not isinstance(source, Mapping) or source.get("schema_version") != SCHEMA_VERSION:
        return CompileResult(
            False,
            "blocked",
            (
                SchemaFinding(
                    "unsupported_contract_schema",
                    "$.schema_version",
                    f"only {SCHEMA_VERSION} is accepted",
                ),
            ),
        )
    ok, status, raw_findings, contract, manifest, written = compile_direct_contract(
        skill_root,
        binding_path,
        write=write,
    )
    findings = tuple(
        SchemaFinding(
            str(row.get("code", "contract_invalid")),
            str(row.get("path", "$")),
            str(row.get("message", "contract invalid")),
            str(row.get("severity", "blocker")),
        )
        for row in raw_findings
    )
    return CompileResult(ok, status, findings, contract, manifest, written)


__all__ = [
    "BINDING_SOURCE_FILE",
    "CHECK_MANIFEST_FILE",
    "COMPILED_CONTRACT_FILE",
    "COMPILER_VERSION",
    "CompileResult",
    "OWNER_BEHAVIOR_FIELDS",
    "canonical_hash",
    "canonical_json_bytes",
    "compile_skill_contract",
    "current_content_projection",
    "current_content_projection_from_files",
    "file_hash",
    "impact_file_hash",
    "path_fingerprint",
    "source_file_hash",
    "wire_hash",
]
