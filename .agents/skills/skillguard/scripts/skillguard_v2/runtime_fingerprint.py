"""Deterministic compatibility fingerprint for the SkillGuard V2 runtime."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .contract_compiler import canonical_hash, source_file_hash


def resolve_guard_runtime_root(runtime_root: Path) -> Path:
    """Accept a repository, installed skill, scripts, or package root.

    Portfolio commands are commonly invoked from a repository root. Callers
    should not need to know the internal ``scripts/skillguard_v2`` package
    layout merely to prove which Guard runtime is active. Direct package roots
    and small synthetic roots used by tests remain valid.
    """

    root = runtime_root.resolve()
    candidates = (
        root / ".agents" / "skills" / "skillguard",
        root / ".codex" / "skills" / "skillguard",
        root,
        root.parent if root.name == "scripts" else root,
        root.parent.parent if root.name == "skillguard_v2" and root.parent.name == "scripts" else root,
    )
    for candidate in candidates:
        if (candidate / "scripts" / "skillguard_v2" / "runtime_fingerprint.py").is_file():
            return candidate.resolve()
    return root


def _runtime_source_files(root: Path) -> list[Path]:
    """Return the complete executable Guard surface for a real SkillGuard root."""

    if not (root / "scripts" / "skillguard_v2" / "runtime_fingerprint.py").is_file():
        return sorted(root.rglob("*.py"), key=lambda item: item.relative_to(root).as_posix())

    files = set(root.joinpath("scripts").rglob("*.py"))
    files.update(root.joinpath("assets", "schemas").glob("*.json"))
    files.update(root.joinpath("references").glob("*.md"))
    for relative in (
        "SKILL.md",
        "test-mesh.json",
        "public-export-policy.json",
        "fixtures/checker_change/current-baseline.json",
        ".skillguard/contract-source.json",
        ".skillguard/compiled-contract.json",
        ".skillguard/check-manifest.json",
    ):
        candidate = root / relative
        if candidate.is_file():
            files.add(candidate)
    return sorted(files, key=lambda item: item.relative_to(root).as_posix())


def guard_runtime_fingerprint(runtime_root: Path | None = None) -> dict[str, Any]:
    """Hash the executable V2 Python surface that interprets target contracts."""

    root = resolve_guard_runtime_root(runtime_root or Path(__file__).resolve().parent)
    files = []
    for path in _runtime_source_files(root):
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "content_hash": source_file_hash(path),
            }
        )
    return {
        "runtime_id": "skillguard-v2",
        "file_count": len(files),
        "source_hash": canonical_hash(files),
    }
