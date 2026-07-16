"""Single portable-versus-runtime path authority for current SkillGuard.

The policy is intentionally path-shape based and checkout independent.  A
consumer may project a runtime path as "ignored" for hashing/copying, but paths
reserved for SkillGuard-owned runtime workspaces remain blocking boundary
findings so they cannot silently become canonical or installed content.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, Iterator

from .path_identity import canonical_filesystem_path, physical_relative_path


PORTABLE_CONTENT_POLICY_ID = "skillguard.portable_content.v2"
RUNTIME_FINGERPRINT_PROJECTION_ID = "skillguard.portable_content.runtime_fingerprint.v1"
OWNED_RUNTIME_CLEANUP_PROJECTION_ID = "skillguard.portable_content.owned_runtime_cleanup.v1"
ACTIVE_INSTALLATION_CURRENTNESS_PROJECTION_ID = (
    "skillguard.portable_content.active_installation_currentness.v1"
)

PORTABLE = "portable_source"
RUNTIME = "runtime_ephemeral"
UNSAFE = "unsafe_or_unknown"

_RESERVED_RUNTIME_DIRECTORY_NAMES = frozenset(
    {
        ".runtime_workspaces",
        ".sg-fixtures",
        ".sg-runtime",
        ".sgf",
        "fixture-generation",
        "fixture-runtime",
        "runtime_workspaces",
    }
)
_GENERIC_TRANSIENT_DIRECTORY_NAMES = frozenset(
    {
        ".cache",
        ".git",
        ".hg",
        ".hypothesis",
        ".ipynb_checkpoints",
        ".mypy_cache",
        ".nox",
        ".pyre",
        ".pytest_cache",
        ".pytype",
        ".ruff_cache",
        ".svn",
        ".tox",
        ".venv",
        "__pycache__",
        "htmlcov",
        "node_modules",
        "venv",
    }
)
_MEMBER_CONTROL_RUNTIME_DIRECTORY_NAMES = frozenset(
    {"bootstrap", "locks", "portfolio-artifacts", "runs", "test-results"}
)
_MEMBER_ROOT_RUNTIME_DIRECTORY_NAMES = frozenset({"work"})
_TRANSIENT_FILE_NAMES = frozenset(
    {".coverage", ".ds_store", "coverage.json", "coverage.xml", "thumbs.db"}
)
_TRANSIENT_FILE_PREFIXES = (".coverage.",)
_TRANSIENT_FILE_SUFFIXES = (".pyc", ".pyo")


@dataclass(frozen=True)
class PortablePathDecision:
    classification: str
    reason: str
    policy_id: str = PORTABLE_CONTENT_POLICY_ID
    boundary_blocking: bool = False

    @property
    def portable(self) -> bool:
        return self.classification == PORTABLE


@dataclass(frozen=True)
class PortableBoundaryReport:
    policy_id: str
    blocking_runtime_paths: tuple[str, ...]
    unsafe_paths: tuple[str, ...]
    excluded_runtime_paths: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.blocking_runtime_paths and not self.unsafe_paths

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_type": "skillguard_portable_content_boundary",
            "policy_id": self.policy_id,
            "status": "passed" if self.ok else "blocked",
            "blocking_runtime_paths": list(self.blocking_runtime_paths),
            "unsafe_paths": list(self.unsafe_paths),
            "excluded_runtime_paths": list(self.excluded_runtime_paths),
            "blockers": [
                *(
                    f"blocking_runtime_path:{path}"
                    for path in self.blocking_runtime_paths
                ),
                *(f"unsafe_path:{path}" for path in self.unsafe_paths),
            ],
            "claim_boundary": (
                "This report classifies current member-root paths with the shared "
                "portable-content policy. It does not prove file-content parity, "
                "runtime authority, tests, installation activation, or target behavior."
            ),
        }


def _portable_relative(value: str | PurePosixPath | Path) -> PurePosixPath | None:
    text = value.as_posix() if isinstance(value, (PurePosixPath, Path)) else str(value)
    text = text.replace("\\", "/").strip()
    if text.startswith("/") or (len(text) >= 2 and text[1] == ":"):
        return None
    text = text.rstrip("/")
    if not text or text == ".":
        return PurePosixPath(".")
    relative = PurePosixPath(text)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        return None
    return relative


def classify_relative_path(
    value: str | PurePosixPath | Path,
) -> PortablePathDecision:
    """Classify one member-root-relative path without touching the filesystem."""

    relative = _portable_relative(value)
    if relative is None:
        return PortablePathDecision(UNSAFE, "path_not_portable", boundary_blocking=True)
    if relative == PurePosixPath("."):
        return PortablePathDecision(PORTABLE, "member_root")

    folded = tuple(part.casefold() for part in relative.parts)
    if any(part in _RESERVED_RUNTIME_DIRECTORY_NAMES for part in folded):
        return PortablePathDecision(
            RUNTIME,
            "reserved_runtime_workspace",
            boundary_blocking=True,
        )
    if any(part in _GENERIC_TRANSIENT_DIRECTORY_NAMES for part in folded):
        return PortablePathDecision(RUNTIME, "generic_transient")
    if folded[0] in _MEMBER_ROOT_RUNTIME_DIRECTORY_NAMES:
        return PortablePathDecision(RUNTIME, "member_root_runtime")
    if (
        len(folded) >= 2
        and folded[0] == ".skillguard"
        and folded[1] in _MEMBER_CONTROL_RUNTIME_DIRECTORY_NAMES
    ):
        return PortablePathDecision(RUNTIME, "member_control_runtime")

    name = folded[-1]
    if (
        name in _TRANSIENT_FILE_NAMES
        or any(name.startswith(prefix) for prefix in _TRANSIENT_FILE_PREFIXES)
        or any(name.endswith(suffix) for suffix in _TRANSIENT_FILE_SUFFIXES)
    ):
        return PortablePathDecision(RUNTIME, "transient_file")
    return PortablePathDecision(PORTABLE, "maintained_content")


def relative_member_path(member_root: Path, candidate: Path) -> PurePosixPath | None:
    """Return a lexical member-relative token without following a candidate link."""

    try:
        return PurePosixPath(
            physical_relative_path(
                candidate,
                member_root,
                preserve_final_component=True,
            ).as_posix()
        )
    except ValueError:
        return None


def _is_link_like(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        return bool(is_junction and is_junction())
    except OSError:
        return True


def classify_member_path(member_root: Path, candidate: Path) -> PortablePathDecision:
    relative = relative_member_path(member_root, candidate)
    if relative is None:
        return PortablePathDecision(UNSAFE, "path_escapes_member", boundary_blocking=True)
    if candidate.exists() and _is_link_like(candidate):
        return PortablePathDecision(UNSAFE, "link_not_portable", boundary_blocking=True)
    return classify_relative_path(relative)


def runtime_fingerprint_excluded(member_root: Path, candidate: Path) -> bool:
    """Project shared path roles onto the executable-runtime fingerprint."""

    relative = relative_member_path(member_root, candidate)
    if relative is None:
        return True
    if relative.parts and relative.parts[0].casefold() == ".skillguard":
        return True
    return classify_member_path(member_root, candidate).classification != PORTABLE


def owned_runtime_parent_may_be_pruned(member_root: Path, candidate: Path) -> bool:
    """Allow cleanup only for a shared-policy reserved runtime workspace root."""

    relative = relative_member_path(member_root, candidate)
    if relative is None or len(relative.parts) != 1:
        return False
    decision = classify_member_path(member_root, candidate)
    return (
        decision.classification == RUNTIME
        and decision.reason == "reserved_runtime_workspace"
        and decision.boundary_blocking
    )


def scan_member_boundary(member_root: Path) -> PortableBoundaryReport:
    """Inspect one current member tree without following links or reading file bodies."""

    root = canonical_filesystem_path(member_root)
    if not root.is_dir():
        return PortableBoundaryReport(
            PORTABLE_CONTENT_POLICY_ID,
            (),
            ("<member-root-unavailable>",),
            (),
        )

    blocking: set[str] = set()
    unsafe: set[str] = set()
    excluded: set[str] = set()

    def onerror(_error: OSError) -> None:
        unsafe.add("<tree-unreadable>")

    for directory_text, directory_names, file_names in os.walk(
        root, topdown=True, followlinks=False, onerror=onerror
    ):
        directory = Path(directory_text)
        retained: list[str] = []
        for name in sorted(directory_names):
            candidate = directory / name
            relative = candidate.relative_to(root).as_posix()
            decision = classify_member_path(root, candidate)
            if decision.classification == UNSAFE:
                unsafe.add(relative)
                continue
            if decision.classification == RUNTIME:
                excluded.add(relative)
                if decision.boundary_blocking:
                    blocking.add(relative)
                continue
            retained.append(name)
        directory_names[:] = retained

        for name in sorted(file_names):
            candidate = directory / name
            relative = candidate.relative_to(root).as_posix()
            decision = classify_member_path(root, candidate)
            if decision.classification == UNSAFE:
                unsafe.add(relative)
            elif decision.classification == RUNTIME:
                excluded.add(relative)
                if decision.boundary_blocking:
                    blocking.add(relative)

    return PortableBoundaryReport(
        PORTABLE_CONTENT_POLICY_ID,
        tuple(sorted(blocking)),
        tuple(sorted(unsafe)),
        tuple(sorted(excluded)),
    )


def scan_active_installation_currentness_boundary(
    member_root: Path,
) -> PortableBoundaryReport:
    """Project only the installed verification-receipt subtree from active state.

    Canonical and staged trees must continue to use :func:`scan_member_boundary`.
    This narrower projection exists solely so an already-installed SkillGuard can
    carry its own ``.sg-runtime/installation`` verification receipts without
    making those runtime bytes part of source or executable-runtime identity.
    Any sibling runtime content, alternate spelling, or link-like entry keeps the
    ordinary reserved-runtime blocker in force.
    """

    root = member_root.resolve()
    ordinary = scan_member_boundary(root)
    runtime_root = root / ".sg-runtime"
    installation_root = runtime_root / "installation"
    exact_projection = False
    projection_unsafe: set[str] = set(ordinary.unsafe_paths)

    if runtime_root.exists() and runtime_root.name == ".sg-runtime":
        try:
            exact_projection = (
                runtime_root.is_dir()
                and not _is_link_like(runtime_root)
                and sorted(child.name for child in runtime_root.iterdir())
                == ["installation"]
                and installation_root.is_dir()
                and not _is_link_like(installation_root)
            )
            if exact_projection:
                for candidate in installation_root.rglob("*"):
                    if _is_link_like(candidate):
                        projection_unsafe.add(
                            candidate.relative_to(root).as_posix()
                        )
                        exact_projection = False
        except OSError:
            projection_unsafe.add(".sg-runtime/installation/<tree-unreadable>")
            exact_projection = False

    blocking = set(ordinary.blocking_runtime_paths)
    excluded = set(ordinary.excluded_runtime_paths)
    if exact_projection:
        blocking.discard(".sg-runtime")
        excluded.add(".sg-runtime/installation")

    return PortableBoundaryReport(
        ACTIVE_INSTALLATION_CURRENTNESS_PROJECTION_ID,
        tuple(sorted(blocking)),
        tuple(sorted(projection_unsafe)),
        tuple(sorted(excluded)),
    )


def portable_files(member_root: Path) -> Iterator[tuple[PurePosixPath, Path]]:
    """Yield deterministic portable regular files; unsafe entries raise ValueError."""

    root = canonical_filesystem_path(member_root)
    rows: list[tuple[PurePosixPath, Path]] = []
    for candidate in root.rglob("*"):
        decision = classify_member_path(root, candidate)
        relative = relative_member_path(root, candidate)
        token = relative.as_posix() if relative is not None else "<outside-member>"
        if decision.classification == UNSAFE:
            raise ValueError(f"unsafe_portable_content:{decision.reason}:{token}")
        if decision.classification != PORTABLE or not candidate.is_file():
            continue
        assert relative is not None
        rows.append((relative, candidate))
    yield from sorted(rows, key=lambda row: row[0].as_posix())


def ignored_copy_names(
    member_root: Path,
    directory: Path,
    names: Iterable[str],
) -> set[str]:
    """Project the shared policy into a ``shutil.copytree`` ignore callback."""

    ignored: set[str] = set()
    for name in names:
        candidate = directory / name
        decision = classify_member_path(member_root, candidate)
        if decision.classification != PORTABLE:
            ignored.add(name)
    return ignored


__all__ = [
    "ACTIVE_INSTALLATION_CURRENTNESS_PROJECTION_ID",
    "PORTABLE",
    "PORTABLE_CONTENT_POLICY_ID",
    "RUNTIME_FINGERPRINT_PROJECTION_ID",
    "OWNED_RUNTIME_CLEANUP_PROJECTION_ID",
    "RUNTIME",
    "UNSAFE",
    "PortableBoundaryReport",
    "PortablePathDecision",
    "classify_member_path",
    "classify_relative_path",
    "ignored_copy_names",
    "owned_runtime_parent_may_be_pruned",
    "portable_files",
    "relative_member_path",
    "scan_active_installation_currentness_boundary",
    "scan_member_boundary",
    "runtime_fingerprint_excluded",
]
