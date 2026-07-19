"""Canonical, installed, repository, and release provenance gates."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tomllib
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from .contract_compiler import canonical_hash, file_hash
from .installation import compare_installation_projection_member
from .portable_content import (
    PORTABLE,
    classify_member_path,
    portable_files,
    scan_active_installation_currentness_boundary,
    scan_member_boundary,
)
from .runtime_authority import AUTHORITY_CURRENT, resolve_runtime_authority


PRIMARY_SUITE_MEMBER_ID = "skillguard"
GLOBAL_ROUTER_SUITE_MEMBER_ID = "skillguard-global-router"
MAINTAINED_SUITE_MEMBER_IDS = (
    PRIMARY_SUITE_MEMBER_ID,
    GLOBAL_ROUTER_SUITE_MEMBER_ID,
)


def normalize_remote_identity(value: str) -> str:
    text = value.strip()
    if re.match(r"^[^/@:]+@[^/:]+:", text):
        user_host, path = text.split(":", 1)
        host = user_host.rsplit("@", 1)[-1]
        text = f"ssh://{host}/{path}"
    parsed = urlsplit(text)
    if parsed.hostname:
        host = parsed.hostname.lower()
        path = parsed.path.strip("/")
        if path.lower().endswith(".git"):
            path = path[:-4]
        return f"{host}/{path.lower()}"
    normalized = text.replace("\\", "/").rstrip("/")
    return normalized[:-4] if normalized.lower().endswith(".git") else normalized


def project_version(pyproject_path: Path) -> str:
    text = pyproject_path.read_text(encoding="utf-8")
    payload = tomllib.loads(text)
    return str(payload.get("project", {}).get("version", ""))


def _included(path: Path, root: Path) -> bool:
    return classify_member_path(root, path).classification == PORTABLE and path.is_file()


def _source_manifest_with_boundary(
    root: Path,
    *,
    active_installation_currentness: bool,
) -> dict[str, str]:
    root = root.resolve()
    boundary = (
        scan_active_installation_currentness_boundary(root)
        if active_installation_currentness
        else scan_member_boundary(root)
    )
    if not boundary.ok:
        codes = [
            *(f"blocking_runtime_path:{path}" for path in boundary.blocking_runtime_paths),
            *(f"unsafe_path:{path}" for path in boundary.unsafe_paths),
        ]
        raise ValueError("portable_content_boundary_blocked:" + ",".join(codes))
    return {
        relative.as_posix(): file_hash(path)
        for relative, path in portable_files(root)
    }


def skill_source_manifest(root: Path) -> dict[str, str]:
    return _source_manifest_with_boundary(
        root,
        active_installation_currentness=False,
    )


def active_installation_source_manifest(root: Path) -> dict[str, str]:
    """Hash active installed source while excluding only its receipt subtree."""

    return _source_manifest_with_boundary(
        root,
        active_installation_currentness=True,
    )


def _runtime_authority_projection(root: Path) -> dict[str, Any]:
    """Resolve authority before any manifest policy can hide runtime transients."""

    try:
        return resolve_runtime_authority(root).to_dict()
    except Exception as exc:
        # Provenance reports are deliberately path-private.  Preserve the
        # failure class without leaking a local absolute path or allowing the
        # manifest comparison to become fallback authority.
        return {
            "artifact_type": "skillguard_runtime_authority_decision",
            "ok": False,
            "authority": "blocked",
            "skill_id": root.name,
            "skill_root": root.name,
            "contract_source_path": "",
            "compiled_contract_path": "",
            "check_manifest_path": "",
            "former_runtime_residuals": [],
            "findings": [],
            "blockers": ["runtime_authority_resolution_failed"],
            "error_kind": type(exc).__name__,
            "claim_boundary": (
                "Authority resolution failed before transient-filtered provenance comparison."
            ),
        }


def _runtime_authority_blockers(projection: Mapping[str, Any]) -> list[str]:
    if (
        projection.get("ok") is True
        and projection.get("authority") == AUTHORITY_CURRENT
    ):
        return []
    blockers = projection.get("blockers")
    if isinstance(blockers, list):
        values = [str(value) for value in blockers if str(value)]
        if values:
            return values
    return ["runtime_authority_blocked"]


def _stable_runtime_authority_projection(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    if before == after:
        return after
    blockers = list(
        dict.fromkeys(
            [
                *_runtime_authority_blockers(before),
                *_runtime_authority_blockers(after),
                "runtime_authority_changed_during_manifest_scan",
            ]
        )
    )
    projection = dict(after)
    projection["ok"] = False
    projection["authority"] = "blocked"
    projection["blockers"] = blockers
    return projection


def compare_skill_sources(canonical_root: Path, installed_root: Path) -> dict[str, Any]:
    canonical_authority_before = _runtime_authority_projection(canonical_root)
    installed_authority_before = _runtime_authority_projection(installed_root)
    canonical = skill_source_manifest(canonical_root)
    installed = skill_source_manifest(installed_root) if installed_root.is_dir() else {}
    canonical_authority = _stable_runtime_authority_projection(
        canonical_authority_before,
        _runtime_authority_projection(canonical_root),
    )
    installed_authority = _stable_runtime_authority_projection(
        installed_authority_before,
        _runtime_authority_projection(installed_root),
    )
    canonical_paths = set(canonical)
    installed_paths = set(installed)
    return {
        "canonical_manifest_hash": canonical_hash(canonical),
        "installed_manifest_hash": canonical_hash(installed),
        "canonical_file_count": len(canonical),
        "installed_file_count": len(installed),
        "missing_in_installed": sorted(canonical_paths - installed_paths),
        "changed_in_installed": sorted(path for path in canonical_paths & installed_paths if canonical[path] != installed[path]),
        "unexpected_in_installed": sorted(installed_paths - canonical_paths),
        "canonical_runtime_authority": canonical_authority,
        "installed_runtime_authority": installed_authority,
    }


def _suite_member_roots(
    canonical_skill_root: Path,
    installed_skill_root: Path,
) -> tuple[tuple[str, Path, Path], ...]:
    canonical_skill_root = canonical_skill_root.resolve()
    installed_skill_root = installed_skill_root.resolve()
    canonical_roots = {
        PRIMARY_SUITE_MEMBER_ID: canonical_skill_root,
        GLOBAL_ROUTER_SUITE_MEMBER_ID: (
            canonical_skill_root.parent / GLOBAL_ROUTER_SUITE_MEMBER_ID
        ),
    }
    installed_roots = {
        PRIMARY_SUITE_MEMBER_ID: installed_skill_root,
        GLOBAL_ROUTER_SUITE_MEMBER_ID: (
            installed_skill_root.parent / GLOBAL_ROUTER_SUITE_MEMBER_ID
        ),
    }
    return tuple(
        (member_id, canonical_roots[member_id], installed_roots[member_id])
        for member_id in MAINTAINED_SUITE_MEMBER_IDS
    )


def _manifest_with_status(root: Path) -> tuple[dict[str, str], bool, str | None]:
    if not root.is_dir():
        return {}, False, None
    try:
        return skill_source_manifest(root), True, None
    except (OSError, UnicodeError, ValueError):
        # Keep public reports path-free while still failing closed on an
        # unreadable member tree.
        return {}, True, "manifest_unreadable"


def _member_path_token(side: str, member_id: str) -> str:
    if member_id == PRIMARY_SUITE_MEMBER_ID:
        return "repository_skill_root" if side == "canonical" else "installed_skill_root"
    return (
        f"repository_skill_root_sibling/{member_id}"
        if side == "canonical"
        else f"installed_skill_root_sibling/{member_id}"
    )


def compare_skill_suite_sources(
    canonical_skill_root: Path,
    installed_skill_root: Path,
) -> dict[str, Any]:
    """Compare each maintained member's exact installation projection."""

    comparisons: dict[str, dict[str, Any]] = {}
    canonical_projections: dict[str, dict[str, Any]] = {}
    installed_projections: dict[str, dict[str, Any]] = {}
    installed_member_ids: list[str] = []
    for member_id, canonical_root, installed_root in _suite_member_roots(
        canonical_skill_root,
        installed_skill_root,
    ):
        canonical_present = canonical_root.is_dir()
        installed_present = installed_root.is_dir()
        canonical_authority_before = _runtime_authority_projection(canonical_root)
        installed_authority_before = _runtime_authority_projection(installed_root)
        try:
            comparison = compare_installation_projection_member(
                canonical_root,
                installed_root,
            )
            comparison_error = str(comparison.get("projection_error", "")) or None
            canonical_projection_error = (
                str(comparison.get("canonical_projection_error", "")) or None
            )
            installed_projection_error = (
                str(comparison.get("installed_projection_error", "")) or None
            )
        except (OSError, UnicodeError, ValueError) as exc:
            comparison_error = type(exc).__name__
            canonical_projection_error = comparison_error
            installed_projection_error = comparison_error
            comparison = {
                "projection_schema": "",
                "canonical_installation_projection": None,
                "installed_installation_projection": None,
                "projection_error": comparison_error,
                "canonical_file_hashes": {},
                "installed_file_hashes": {},
                "missing_in_installed": [],
                "changed_in_installed": [],
                "unexpected_in_installed": [],
                "status": "blocked",
            }
        canonical_authority = _stable_runtime_authority_projection(
            canonical_authority_before,
            _runtime_authority_projection(canonical_root),
        )
        installed_authority = _stable_runtime_authority_projection(
            installed_authority_before,
            _runtime_authority_projection(installed_root),
        )
        canonical_projection = comparison.get("canonical_installation_projection")
        installed_projection = comparison.get("installed_installation_projection")
        comparison.update(
            {
                "canonical_projection_hash": (
                    str(canonical_projection.get("identity_hash", ""))
                    if isinstance(canonical_projection, Mapping)
                    else ""
                ),
                "installed_projection_hash": (
                    str(installed_projection.get("identity_hash", ""))
                    if isinstance(installed_projection, Mapping)
                    else ""
                ),
                "canonical_file_count": len(comparison["canonical_file_hashes"]),
                "installed_file_count": len(comparison["installed_file_hashes"]),
                "canonical_member_present": canonical_present,
                "installed_member_present": installed_present,
                "canonical_projection_error": (
                    canonical_projection_error if canonical_present else "member_missing"
                ),
                "installed_projection_error": (
                    installed_projection_error if installed_present else "member_missing"
                ),
                "canonical_runtime_authority": canonical_authority,
                "installed_runtime_authority": installed_authority,
            }
        )
        comparisons[member_id] = comparison
        canonical_projections[member_id] = {
            "path_token": _member_path_token("canonical", member_id),
            "status": (
                "unreadable"
                if comparison["canonical_projection_error"]
                else "available"
                if canonical_present
                else "missing"
            ),
            "projection_hash": comparison["canonical_projection_hash"],
            "file_count": comparison["canonical_file_count"],
        }
        installed_projections[member_id] = {
            "path_token": _member_path_token("installed", member_id),
            "status": (
                "unreadable"
                if comparison["installed_projection_error"]
                else "available"
                if installed_present
                else "missing"
            ),
            "projection_hash": comparison["installed_projection_hash"],
            "file_count": comparison["installed_file_count"],
        }
        if installed_present:
            installed_member_ids.append(member_id)
    return {
        "member_comparisons": comparisons,
        "member_projections": {
            "canonical": canonical_projections,
            "installed": installed_projections,
        },
        "installed_member_ids": installed_member_ids,
    }


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _git_executable() -> str:
    configured = os.environ.get("GIT_EXECUTABLE", "")
    if configured and Path(configured).is_file():
        return configured
    discovered = shutil.which("git") or "git"
    if Path(discovered).suffix.lower() not in {".cmd", ".bat"}:
        return discovered
    program_files = Path(os.environ.get("ProgramFiles", "C:" + "/Program Files"))
    for candidate in (program_files / "Git" / "cmd" / "git.exe", program_files / "Git" / "bin" / "git.exe"):
        if candidate.is_file():
            return str(candidate)
    return discovered


def _git(repository_root: Path, *args: str) -> str:
    completed = subprocess.run(
        [_git_executable(), *args],
        cwd=repository_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {completed.stderr.strip()}")
    return completed.stdout.strip()


def github_release_snapshot(repository: str) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [
                "gh",
                "release",
                "view",
                "--repo",
                repository,
                "--json",
                "tagName,targetCommitish,isDraft,isPrerelease,url,publishedAt",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError:
        return {
            "status": "unavailable",
            "error_kind": "executable_missing",
            "reason": "GitHub CLI executable 'gh' is unavailable.",
        }
    except OSError:
        return {
            "status": "unavailable",
            "error_kind": "os_error",
            "reason": "GitHub CLI could not be started by the operating system.",
        }
    if completed.returncode != 0:
        return {
            "status": "unavailable",
            "error_kind": "nonzero_exit",
            "reason": (completed.stderr or "").strip() or "gh release view failed",
        }
    try:
        payload = json.loads(completed.stdout)
    except (json.JSONDecodeError, TypeError):
        return {
            "status": "unavailable",
            "error_kind": "invalid_json",
            "reason": "gh release view returned invalid JSON.",
        }
    if not isinstance(payload, dict):
        return {
            "status": "unavailable",
            "error_kind": "invalid_json",
            "reason": "gh release view returned a non-object JSON payload.",
        }
    payload["status"] = "available"
    return payload


def audit_release_provenance(
    repository_root: Path,
    canonical_skill_root: Path,
    installed_skill_root: Path,
    *,
    expected_origin: str,
    release_snapshot: Mapping[str, Any] | None = None,
    require_clean: bool = True,
    require_installed_parity: bool = True,
    require_release_alignment: bool = True,
) -> dict[str, Any]:
    repository_root = repository_root.resolve()
    canonical_skill_root = canonical_skill_root.resolve()
    installed_skill_root = installed_skill_root.resolve()
    blockers: list[str] = []
    failures: list[str] = []
    branch = _git(repository_root, "branch", "--show-current")
    commit = _git(repository_root, "rev-parse", "HEAD")
    origin = _git(repository_root, "remote", "get-url", "origin")
    status_rows = [row for row in _git(repository_root, "status", "--short").splitlines() if row]
    tags_at_head = [row for row in _git(repository_root, "tag", "--points-at", "HEAD").splitlines() if row]
    version = (repository_root / "VERSION").read_text(encoding="utf-8").strip()
    package_version = project_version(repository_root / "pyproject.toml")
    expected_tag = f"v{version}"
    suite_comparison = compare_skill_suite_sources(
        canonical_skill_root,
        installed_skill_root,
    )
    member_comparisons = suite_comparison["member_comparisons"]
    member_projections = suite_comparison["member_projections"]
    installed_member_ids = suite_comparison["installed_member_ids"]
    source_comparison = member_comparisons[PRIMARY_SUITE_MEMBER_ID]

    if normalize_remote_identity(origin) != normalize_remote_identity(expected_origin):
        blockers.append("origin_identity_mismatch")
    if version != package_version:
        blockers.append("version_sources_mismatch")
    if require_clean and status_rows:
        blockers.append("canonical_worktree_dirty")
    for comparison in member_comparisons.values():
        if not comparison["canonical_member_present"]:
            _append_unique(blockers, "canonical_suite_member_missing")
        if comparison["canonical_projection_error"]:
            _append_unique(blockers, "canonical_suite_member_unreadable")
        for code in _runtime_authority_blockers(
            comparison["canonical_runtime_authority"]
        ):
            _append_unique(blockers, code)
            _append_unique(blockers, "canonical_runtime_authority_blocked")
    if require_installed_parity:
        if not installed_skill_root.is_dir():
            blockers.append("installed_skill_missing")
        for key, code in (
            ("missing_in_installed", "installed_projection_missing_files"),
            ("changed_in_installed", "installed_projection_changed_files"),
            ("unexpected_in_installed", "installed_projection_unexpected_files"),
        ):
            if any(comparison[key] for comparison in member_comparisons.values()):
                _append_unique(blockers, code)
        if any(
            not comparison["installed_member_present"]
            for comparison in member_comparisons.values()
        ):
            _append_unique(blockers, "installed_suite_member_missing")
        if any(
            comparison["installed_projection_error"]
            for comparison in member_comparisons.values()
        ):
            _append_unique(blockers, "installed_suite_member_unreadable")
        if any(
            comparison["changed_in_installed"]
            for comparison in member_comparisons.values()
        ):
            _append_unique(blockers, "installed_suite_member_changed")
        if any(
            comparison["unexpected_in_installed"]
            for comparison in member_comparisons.values()
        ):
            _append_unique(blockers, "installed_suite_member_unexpected_surface")
        for comparison in member_comparisons.values():
            for code in _runtime_authority_blockers(
                comparison["installed_runtime_authority"]
            ):
                _append_unique(blockers, code)
                _append_unique(blockers, "installed_runtime_authority_blocked")
    release = dict(release_snapshot or {})
    if require_release_alignment:
        if release.get("status") != "available":
            blockers.append("github_release_unavailable")
        else:
            if release.get("tagName") != expected_tag:
                blockers.append("github_release_version_mismatch")
            if release.get("isDraft") is True or release.get("isPrerelease") is True:
                blockers.append("github_release_not_final")
            if expected_tag not in tags_at_head:
                blockers.append("version_tag_not_at_head")
    return {
        "artifact_type": "skillguard_release_provenance_audit",
        "status": "passed" if not blockers and not failures else "blocked" if blockers else "failed",
        "canonical_source": {
            "path_token": "repository_skill_root",
            "branch": branch,
            "commit": commit,
            "origin": origin,
            "dirty_paths": status_rows,
            "version": version,
            "package_version": package_version,
            "tags_at_head": tags_at_head,
            "installation_projection_hash": source_comparison["canonical_projection_hash"],
            "file_count": source_comparison["canonical_file_count"],
            "member_projections": member_projections["canonical"],
        },
        "installed_source": {
            "path_token": "installed_skill_root",
            "installation_projection_hash": source_comparison["installed_projection_hash"],
            "file_count": source_comparison["installed_file_count"],
            "missing_files": source_comparison["missing_in_installed"],
            "changed_files": source_comparison["changed_in_installed"],
            "unexpected_files": source_comparison["unexpected_in_installed"],
            "member_projections": member_projections["installed"],
            "installed_member_ids": installed_member_ids,
        },
        "member_comparisons": member_comparisons,
        "member_projections": member_projections,
        "runtime_authority": {
            "canonical": {
                member_id: comparison["canonical_runtime_authority"]
                for member_id, comparison in member_comparisons.items()
            },
            "installed": {
                member_id: comparison["installed_runtime_authority"]
                for member_id, comparison in member_comparisons.items()
            },
        },
        "installed_member_ids": installed_member_ids,
        "repository_source": {
            "remote_identity": origin,
            "expected_remote_identity": expected_origin,
            "normalized_remote_identity": normalize_remote_identity(origin),
            "expected_normalized_remote_identity": normalize_remote_identity(expected_origin),
            "expected_tag": expected_tag,
        },
        "release_source": release,
        "evidence": [
            "git branch, commit, origin, status, and tags",
            "VERSION and pyproject project.version",
            "canonical-to-installed exact two-member installation projections",
            "typed runtime-authority decisions captured before transient filtering",
            "GitHub Release metadata when required",
        ],
        "failures": failures,
        "blockers": blockers,
        "skipped_checks": [],
        "residual_risk": [
            "A passing provenance audit does not replace native tests, clean-install smoke, privacy review, or publication verification."
        ],
        "claim_boundary": "This audit proves only the named runtime-authority, canonical, installed, Git, and release identity relations at the current fingerprints. It does not prove target execution depth and does not publish or mutate any remote.",
        "typed_next_actions": [
            "Synchronize each changed installation component through the staged transactional installer.",
            "Bump version only after the release scope is frozen and rerun this audit after tag and GitHub Release creation.",
        ],
    }
