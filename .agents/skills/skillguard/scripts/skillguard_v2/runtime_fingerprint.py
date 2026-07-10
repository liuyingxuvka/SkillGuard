"""Deterministic compatibility fingerprint for the SkillGuard V2 runtime."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .contract_compiler import canonical_hash, file_hash


def guard_runtime_fingerprint(runtime_root: Path | None = None) -> dict[str, Any]:
    """Hash the executable V2 Python surface that interprets target contracts."""

    root = (runtime_root or Path(__file__).resolve().parent).resolve()
    files = []
    for path in sorted(root.rglob("*.py"), key=lambda item: item.relative_to(root).as_posix()):
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "content_hash": file_hash(path),
            }
        )
    return {
        "runtime_id": "skillguard-v2",
        "file_count": len(files),
        "source_hash": canonical_hash(files),
    }
