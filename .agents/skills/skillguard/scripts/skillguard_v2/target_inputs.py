"""Safe target-input inventory and byte-derived fingerprints."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contract_compiler import canonical_hash


class TargetInputError(ValueError):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


_ROLE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


def fingerprint_target_inputs(
    target_root: Path,
    relative_paths: object,
) -> Mapping[str, Any]:
    root = target_root.resolve()
    if isinstance(relative_paths, (str, bytes)) or not isinstance(relative_paths, Sequence):
        raise TargetInputError("target_input_paths_invalid", "array required")
    normalized: list[str] = []
    records: list[dict[str, Any]] = []
    for raw in relative_paths:
        if not isinstance(raw, str) or not raw.strip():
            raise TargetInputError("target_input_path_invalid", str(raw))
        path_text = Path(raw).as_posix()
        relative = Path(path_text)
        if relative.is_absolute() or ".." in relative.parts:
            raise TargetInputError("target_input_path_outside_target", path_text)
        resolved = (root / relative).resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise TargetInputError("target_input_path_outside_target", path_text) from exc
        canonical_relative = resolved.relative_to(root).as_posix()
        if canonical_relative in normalized:
            raise TargetInputError("target_input_path_duplicate", canonical_relative)
        if not resolved.exists():
            raise TargetInputError("target_input_path_missing", canonical_relative)
        if not resolved.is_file():
            raise TargetInputError("target_input_path_not_file", canonical_relative)
        payload = resolved.read_bytes()
        normalized.append(canonical_relative)
        records.append(
            {
                "path": canonical_relative,
                "size": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest().upper(),
            }
        )
    if not records:
        raise TargetInputError("target_input_paths_empty", "at least one file is required")
    records.sort(key=lambda row: row["path"])
    return {
        "paths": [row["path"] for row in records],
        "files": records,
        "fingerprint": canonical_hash({"files": records}),
    }


def fingerprint_target_input_roles(
    target_root: Path,
    role_paths: object,
) -> Mapping[str, Mapping[str, Any]]:
    """Derive verifier-owned file inventories for declared target input roles."""

    if not isinstance(role_paths, Mapping) or not role_paths:
        raise TargetInputError("target_input_roles_invalid", "non-empty mapping required")
    normalized: dict[str, Mapping[str, Any]] = {}
    for raw_role, relative_paths in sorted(role_paths.items(), key=lambda row: str(row[0])):
        role = str(raw_role or "").strip()
        if not _ROLE_ID.fullmatch(role):
            raise TargetInputError("target_input_role_invalid", role)
        if role in normalized:
            raise TargetInputError("target_input_role_duplicate", role)
        normalized[role] = fingerprint_target_inputs(target_root, relative_paths)
    return normalized
