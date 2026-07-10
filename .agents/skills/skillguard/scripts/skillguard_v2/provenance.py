"""Canonical, installed, repository, and release provenance gates."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tomllib
from pathlib import Path
from typing import Any, Mapping

from .contract_compiler import canonical_hash, file_hash


TRANSIENT_PARTS = frozenset({"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "node_modules"})


def _included(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    if any(part in TRANSIENT_PARTS for part in relative.parts):
        return False
    if len(relative.parts) >= 2 and relative.parts[0] == ".skillguard" and relative.parts[1] in {
        "runs",
        "locks",
        "bootstrap",
        "test-results",
    }:
        return False
    return path.is_file()


def skill_source_manifest(root: Path) -> dict[str, str]:
    root = root.resolve()
    return {
        path.relative_to(root).as_posix(): file_hash(path)
        for path in sorted(root.rglob("*"))
        if _included(path, root)
    }


def compare_skill_sources(canonical_root: Path, installed_root: Path) -> dict[str, Any]:
    canonical = skill_source_manifest(canonical_root)
    installed = skill_source_manifest(installed_root) if installed_root.is_dir() else {}
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
    }


def _git_executable() -> str:
    configured = os.environ.get("GIT_EXECUTABLE", "")
    if configured and Path(configured).is_file():
        return configured
    discovered = shutil.which("git") or "git"
    if Path(discovered).suffix.lower() not in {".cmd", ".bat"}:
        return discovered
    program_files = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
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
    if completed.returncode != 0:
        return {"status": "unavailable", "reason": completed.stderr.strip() or "gh release view failed"}
    payload = json.loads(completed.stdout)
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
    pyproject = tomllib.loads((repository_root / "pyproject.toml").read_text(encoding="utf-8"))
    package_version = str(pyproject.get("project", {}).get("version", ""))
    expected_tag = f"v{version}"
    source_comparison = compare_skill_sources(canonical_skill_root, installed_skill_root)

    if origin != expected_origin:
        blockers.append("origin_identity_mismatch")
    if version != package_version:
        blockers.append("version_sources_mismatch")
    if require_clean and status_rows:
        blockers.append("canonical_worktree_dirty")
    if require_installed_parity:
        if not installed_skill_root.is_dir():
            blockers.append("installed_skill_missing")
        for key, code in (
            ("missing_in_installed", "installed_source_downgrade_missing_files"),
            ("changed_in_installed", "installed_source_downgrade_changed_files"),
            ("unexpected_in_installed", "installed_source_has_untracked_surface"),
        ):
            if source_comparison[key]:
                blockers.append(code)
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
            "manifest_hash": source_comparison["canonical_manifest_hash"],
            "file_count": source_comparison["canonical_file_count"],
        },
        "installed_source": {
            "path_token": "installed_skill_root",
            "manifest_hash": source_comparison["installed_manifest_hash"],
            "file_count": source_comparison["installed_file_count"],
            "missing_files": source_comparison["missing_in_installed"],
            "changed_files": source_comparison["changed_in_installed"],
            "unexpected_files": source_comparison["unexpected_in_installed"],
        },
        "repository_source": {
            "remote_identity": origin,
            "expected_remote_identity": expected_origin,
            "expected_tag": expected_tag,
        },
        "release_source": release,
        "evidence": [
            "git branch, commit, origin, status, and tags",
            "VERSION and pyproject project.version",
            "canonical-to-installed complete source manifests",
            "GitHub Release metadata when required",
        ],
        "failures": failures,
        "blockers": blockers,
        "skipped_checks": [],
        "residual_risk": [
            "A passing provenance audit does not replace native tests, clean-install smoke, privacy review, or publication verification."
        ],
        "claim_boundary": "This audit proves only the named canonical, installed, Git, and release identity relations at the current fingerprints. It does not publish or mutate any remote.",
        "typed_next_actions": [
            "Synchronize the complete skill source into a staged installed location before replacing the active install.",
            "Bump version only after the release scope is frozen and rerun this audit after tag and GitHub Release creation.",
        ],
    }
