"""Canonical immutable storage for SkillGuard portfolio records.

This module deliberately knows nothing about a target skill's domain semantics.
It stores and resolves hash-bound files; target-native checks remain the sole
owners of what those records mean.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .contract_compiler import canonical_json_bytes


RECORD_REF_RE = re.compile(
    r"^record:(?P<path>[A-Za-z0-9._/-]+)@(?P<hash>[A-F0-9]{64})$"
)


class PortfolioRecordError(ValueError):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _workspace_relative_path(path_text: str, workspace_root: Path) -> Path:
    if "\\" in path_text:
        raise PortfolioRecordError("record_path_not_posix", path_text)
    pure = PurePosixPath(path_text)
    if (
        pure.is_absolute()
        or not pure.parts
        or any(part in {"", ".", ".."} for part in pure.parts)
    ):
        raise PortfolioRecordError("record_path_not_relative", path_text)
    root = workspace_root.resolve()
    path = (root / Path(*pure.parts)).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise PortfolioRecordError("record_path_escape", path_text) from exc
    return path


def reference_existing_file(path: Path, workspace_root: Path) -> str:
    root = workspace_root.resolve()
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise PortfolioRecordError("record_path_outside_workspace", str(path)) from exc
    if not resolved.is_file():
        raise PortfolioRecordError("record_file_missing", relative.as_posix())
    relative_text = relative.as_posix()
    _workspace_relative_path(relative_text, root)
    digest = hashlib.sha256(resolved.read_bytes()).hexdigest().upper()
    return f"record:{relative_text}@{digest}"


def write_hash_bound_json(
    relative_path: str | Path,
    payload: Mapping[str, Any],
    workspace_root: Path,
) -> tuple[Path, str]:
    root = workspace_root.resolve()
    relative_text = (
        relative_path.as_posix()
        if isinstance(relative_path, Path)
        else str(relative_path)
    )
    path = _workspace_relative_path(relative_text, root)
    raw = canonical_json_bytes(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if not path.is_file() or path.read_bytes() != raw:
            raise PortfolioRecordError("record_immutable_collision", relative_text)
    else:
        path.write_bytes(raw)
    return path, reference_existing_file(path, root)


def resolve_record_ref(record_ref: str, workspace_root: Path) -> tuple[Path, bytes]:
    match = RECORD_REF_RE.fullmatch(record_ref)
    if match is None:
        raise PortfolioRecordError("record_ref_invalid", record_ref)
    path = _workspace_relative_path(match.group("path"), workspace_root)
    if not path.is_file():
        raise PortfolioRecordError("record_file_missing", match.group("path"))
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest().upper() != match.group("hash"):
        raise PortfolioRecordError("record_file_hash_mismatch", record_ref)
    return path, raw


__all__ = [
    "PortfolioRecordError",
    "reference_existing_file",
    "resolve_record_ref",
    "write_hash_bound_json",
]
