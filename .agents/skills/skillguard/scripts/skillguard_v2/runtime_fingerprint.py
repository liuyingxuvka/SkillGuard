"""Deterministic fingerprint for the sole current SkillGuard runtime."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Mapping

from .portable_content import (
    runtime_fingerprint_excluded,
    scan_active_installation_currentness_boundary,
    scan_member_boundary,
)
from .wire_identity import canonical_json_bytes, wire_hash


def _canonical_hash(payload: object) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest().upper()


def _raw_source_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class GuardRuntimeFingerprintError(RuntimeError):
    """Raised when the declared Guard behavior surface is incomplete or unsafe."""


_CURRENT_EXECUTION_FILES = (
    Path("checker_engine.py"),
    Path("skillguard_v2/execution_records.py"),
    Path("skillguard_v2/wire_identity.py"),
    Path("skillguard_v2/path_identity.py"),
    Path("skillguard_v2/runtime_fingerprint.py"),
)


def current_execution_runtime(runtime_root: Path) -> dict[str, Any]:
    """Hash only the fixed files that govern compact leaf execution."""

    root = Path(runtime_root)
    if not root.is_absolute():
        raise GuardRuntimeFingerprintError("execution runtime root must be absolute")
    root = root.resolve(strict=True)
    rows: list[dict[str, str]] = []
    for relative in _CURRENT_EXECUTION_FILES:
        path = (root / relative).resolve(strict=True)
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise GuardRuntimeFingerprintError(f"execution runtime file escapes root: {relative}") from exc
        if not path.is_file():
            raise GuardRuntimeFingerprintError(f"execution runtime file is missing: {relative}")
        rows.append({"path": relative.as_posix(), "sha256": _raw_source_hash(path)})
    return {"schema_version": "skillguard.execution_runtime.v1", "files": rows, "runtime_hash": wire_hash(rows)}


_RUNTIME_SENTINEL = Path("scripts/skillguard_v2/runtime_fingerprint.py")
_GLOBAL_ROUTER_MEMBER = "skillguard-global-router"
_GLOBAL_ROUTER_REQUIRED_FILES = (
    Path("SKILL.md"),
    Path(".skillguard/contract-source.json"),
    Path(".skillguard/compiled-contract.json"),
    Path(".skillguard/check-manifest.json"),
)
_GLOBAL_ROUTER_REQUIRED_TREES = (Path("scripts"), Path("references"))
RUNTIME_PROVIDER_ID = "skillguard-local-provider"
RUNTIME_CONTRACT_ID = "skillguard-declared-check-supervision-current"
RUNTIME_CAPABILITY_IDS = (
    "declared-check-inventory.v1",
    "declared-check-receipt-reconciliation.v1",
    "installation-receipt-binding.v1",
    "installation-currentness-replay.v1",
    "provider-runtime-enrollment.v1",
    "single-flight-check-execution.v1",
)
_RUNTIME_FUNCTIONAL_FIELDS = (
    "runtime_id",
    "provider_id",
    "runtime_contract_id",
    "capability_ids",
    "source_hash",
)


def runtime_functional_projection(
    fingerprint: Mapping[str, Any],
) -> dict[str, Any]:
    """Project runtime identity onto maintained behavior, not enrollment metadata."""

    if not isinstance(fingerprint, Mapping):
        raise GuardRuntimeFingerprintError(
            "runtime fingerprint must be an object"
        )
    missing = [
        field for field in _RUNTIME_FUNCTIONAL_FIELDS if field not in fingerprint
    ]
    if missing:
        raise GuardRuntimeFingerprintError(
            "runtime functional identity is incomplete: " + ",".join(missing)
        )
    capabilities = fingerprint.get("capability_ids")
    if not isinstance(capabilities, (list, tuple)) or any(
        not isinstance(value, str) or not value for value in capabilities
    ) or not capabilities:
        raise GuardRuntimeFingerprintError(
            "runtime functional capability identity is invalid"
        )
    for field in ("runtime_id", "provider_id", "runtime_contract_id", "source_hash"):
        if not str(fingerprint[field]):
            raise GuardRuntimeFingerprintError(
                f"runtime functional {field} is missing"
            )
    return {
        "runtime_id": str(fingerprint["runtime_id"]),
        "provider_id": str(fingerprint["provider_id"]),
        "runtime_contract_id": str(fingerprint["runtime_contract_id"]),
        "capability_ids": sorted(str(value) for value in capabilities),
        "source_hash": str(fingerprint["source_hash"]),
    }


def runtime_functional_key(fingerprint: Mapping[str, Any]) -> str:
    """Return the stable behavior identity for one runtime fingerprint."""

    return _canonical_hash(runtime_functional_projection(fingerprint))


def _existing_directory(path: Path, *, label: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise GuardRuntimeFingerprintError(f"{label} is missing: {path}") from exc
    if not resolved.is_dir():
        raise GuardRuntimeFingerprintError(f"{label} is not a directory: {path}")
    return resolved


def resolve_guard_runtime_root(runtime_root: Path) -> Path:
    """Accept a repository, installed skill, scripts, or package root.

    Portfolio commands are commonly invoked from a repository root. Callers
    should not need to know the internal ``scripts/skillguard_v2`` package
    layout merely to prove which Guard runtime is active. Direct package roots
    and small synthetic roots used by tests remain valid.
    """

    root = _existing_directory(Path(runtime_root), label="Guard runtime root")
    candidates = (
        root / ".agents" / "skills" / "skillguard",
        root / ".codex" / "skills" / "skillguard",
        root,
        root.parent if root.name == "scripts" else root,
        root.parent.parent if root.name == "skillguard_v2" and root.parent.name == "scripts" else root,
    )
    for candidate in candidates:
        if candidate.joinpath(_RUNTIME_SENTINEL).is_file():
            return candidate.resolve()
    return root


def _checked_member_file(path: Path, *, member_root: Path, label: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise GuardRuntimeFingerprintError(f"{label} is missing: {path}") from exc
    if not resolved.is_file():
        raise GuardRuntimeFingerprintError(f"{label} is not a regular file: {path}")
    try:
        resolved.relative_to(member_root)
    except ValueError as exc:
        raise GuardRuntimeFingerprintError(
            f"{label} resolves outside the {_GLOBAL_ROUTER_MEMBER} member: {path}"
        ) from exc
    return resolved


def _checked_member_directory(path: Path, *, member_root: Path, label: str) -> Path:
    resolved = _existing_directory(path, label=label)
    try:
        resolved.relative_to(member_root)
    except ValueError as exc:
        raise GuardRuntimeFingerprintError(
            f"{label} resolves outside the {_GLOBAL_ROUTER_MEMBER} member: {path}"
        ) from exc
    return resolved


def _is_transient_member_file(path: Path, *, member_root: Path) -> bool:
    return runtime_fingerprint_excluded(member_root, path)


def _global_router_source_entries(root: Path) -> list[tuple[str, Path]]:
    member_root = _existing_directory(
        root.parent / _GLOBAL_ROUTER_MEMBER,
        label=f"required sibling {_GLOBAL_ROUTER_MEMBER} member",
    )
    entries: list[tuple[str, Path]] = []
    for relative in _GLOBAL_ROUTER_REQUIRED_FILES:
        path = _checked_member_file(
            member_root / relative,
            member_root=member_root,
            label=f"required {_GLOBAL_ROUTER_MEMBER} surface {relative.as_posix()}",
        )
        entries.append((f"{_GLOBAL_ROUTER_MEMBER}/{relative.as_posix()}", path))

    for relative_tree in _GLOBAL_ROUTER_REQUIRED_TREES:
        tree_root = _checked_member_directory(
            member_root / relative_tree,
            member_root=member_root,
            label=f"required {_GLOBAL_ROUTER_MEMBER} tree {relative_tree.as_posix()}",
        )
        tree_files: list[Path] = []
        for candidate in tree_root.rglob("*"):
            if not candidate.is_file() or _is_transient_member_file(candidate, member_root=member_root):
                continue
            tree_files.append(
                _checked_member_file(
                    candidate,
                    member_root=member_root,
                    label=f"{_GLOBAL_ROUTER_MEMBER} behavior surface",
                )
            )
        if not tree_files:
            raise GuardRuntimeFingerprintError(
                f"required {_GLOBAL_ROUTER_MEMBER} tree has no behavior files: {relative_tree.as_posix()}"
            )
        for path in tree_files:
            relative = path.relative_to(member_root).as_posix()
            entries.append((f"{_GLOBAL_ROUTER_MEMBER}/{relative}", path))
    return entries


def _runtime_source_files(root: Path) -> list[Path]:
    """Return the complete executable Guard surface for a real SkillGuard root."""

    return [path for _, path in _runtime_source_entries(root)]


def _runtime_source_entries(root: Path) -> list[tuple[str, Path]]:
    """Return checkout-independent logical paths and their concrete source files."""

    if not root.joinpath(_RUNTIME_SENTINEL).is_file():
        synthetic = sorted(root.rglob("*.py"), key=lambda item: item.relative_to(root).as_posix())
        if not synthetic:
            raise GuardRuntimeFingerprintError(
                f"Guard runtime root has no fingerprintable Python source: {root}"
            )
        return [(path.relative_to(root).as_posix(), path) for path in synthetic]

    files = set(root.joinpath("scripts").rglob("*.py"))
    files.update(root.joinpath("assets", "schemas").glob("*.json"))
    files.update(root.joinpath("references").glob("*.md"))
    for relative in (
        "SKILL.md",
        "test-mesh.json",
        "public-export-policy.json",
        ".skillguard/contract-source.json",
        ".skillguard/compiled-contract.json",
        ".skillguard/check-manifest.json",
    ):
        candidate = root / relative
        if candidate.is_file():
            files.add(candidate)
    entries = [(path.relative_to(root).as_posix(), path) for path in files]
    entries.extend(_global_router_source_entries(root))
    entries.sort(key=lambda item: item[0])
    logical_paths = [logical_path for logical_path, _ in entries]
    if len(logical_paths) != len(set(logical_paths)):
        raise GuardRuntimeFingerprintError("Guard runtime surface contains duplicate logical paths")
    return entries


def _guard_runtime_fingerprint(
    runtime_root: Path | None,
    *,
    active_installation_currentness: bool,
) -> dict[str, Any]:
    root = resolve_guard_runtime_root(runtime_root or Path(__file__).resolve().parent)
    for member_id, member_root in (
        ("skillguard", root),
        (_GLOBAL_ROUTER_MEMBER, root.parent / _GLOBAL_ROUTER_MEMBER),
    ):
        if not member_root.is_dir():
            continue
        boundary = (
            scan_active_installation_currentness_boundary(member_root)
            if active_installation_currentness and member_id == "skillguard"
            else scan_member_boundary(member_root)
        )
        if not boundary.ok:
            raise GuardRuntimeFingerprintError(
                f"{member_id} portable boundary blocked: "
                + ",".join(
                    [
                        *(f"runtime:{path}" for path in boundary.blocking_runtime_paths),
                        *(f"unsafe:{path}" for path in boundary.unsafe_paths),
                    ]
                )
            )
    files = []
    for logical_path, path in _runtime_source_entries(root):
        files.append(
            {
                "path": logical_path,
                "content_hash": _raw_source_hash(path),
            }
        )
    fingerprint = {
        "runtime_id": "skillguard-v2",
        "provider_id": RUNTIME_PROVIDER_ID,
        "runtime_contract_id": RUNTIME_CONTRACT_ID,
        "capability_ids": list(RUNTIME_CAPABILITY_IDS),
        "enrollment_status": "enrolled",
        "file_count": len(files),
        "source_hash": _canonical_hash(files),
    }
    # Validate the exact projection used by functional freshness while
    # keeping enrollment/file-count metadata available to their own consumers.
    runtime_functional_key(fingerprint)
    return fingerprint


def guard_runtime_fingerprint(runtime_root: Path | None = None) -> dict[str, Any]:
    """Hash the maintained SkillGuard suite surface that governs current evidence."""

    return _guard_runtime_fingerprint(
        runtime_root,
        active_installation_currentness=False,
    )


def guard_active_installation_runtime_fingerprint(
    runtime_root: Path | None = None,
) -> dict[str, Any]:
    """Hash an active install while projecting only its verification receipts."""

    return _guard_runtime_fingerprint(
        runtime_root,
        active_installation_currentness=True,
    )


def guard_execution_runtime_fingerprint(
    runtime_root: Path | None = None,
) -> dict[str, Any]:
    """Hash the executing runtime under its one location-derived boundary.

    The active ``CODEX_HOME/skills/skillguard`` installation is allowed to
    carry only its exact installation-verification receipt subtree. Every
    other location is canonical or staged content and therefore keeps the
    ordinary reserved-runtime blocker. The caller cannot select a looser
    interpretation.
    """

    root = resolve_guard_runtime_root(
        runtime_root or Path(__file__).resolve().parent
    )
    codex_home = Path(
        os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
    ).expanduser().resolve()
    active_root = (codex_home / "skills" / "skillguard").resolve()
    return _guard_runtime_fingerprint(
        root,
        active_installation_currentness=root == active_root,
    )
