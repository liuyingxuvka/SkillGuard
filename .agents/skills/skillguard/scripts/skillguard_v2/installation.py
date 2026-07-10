"""Staged whole-tree SkillGuard installation with parity and rollback."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .provenance import compare_skill_sources


TRANSIENT_NAMES = frozenset({"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"})
TRANSIENT_CONTROL_DIRS = frozenset({"runs", "locks", "bootstrap", "test-results"})


def _ignore(directory: str, names: list[str]) -> set[str]:
    path = Path(directory)
    ignored = {name for name in names if name in TRANSIENT_NAMES or name.endswith((".pyc", ".pyo"))}
    if path.name == ".skillguard":
        ignored.update(name for name in names if name in TRANSIENT_CONTROL_DIRS)
    return ignored


def _safe_stage_path(stage_root: Path) -> Path:
    stage_root = stage_root.resolve()
    if stage_root.name != "skillguard" or stage_root.parent.name != "skills" or stage_root.parent.parent.name != ".codex":
        raise ValueError("stage root must end with .codex/skills/skillguard")
    return stage_root


def prepare_stage(canonical_skill_root: Path, stage_root: Path) -> dict[str, Any]:
    canonical_skill_root = canonical_skill_root.resolve()
    stage_root = _safe_stage_path(stage_root)
    if stage_root.exists():
        raise FileExistsError("stage root already exists")
    stage_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(canonical_skill_root, stage_root, ignore=_ignore)
    comparison = compare_skill_sources(canonical_skill_root, stage_root)
    blockers = []
    if comparison["missing_in_installed"] or comparison["changed_in_installed"] or comparison["unexpected_in_installed"]:
        blockers.append("staged_source_parity_failed")
    return {
        "artifact_type": "skillguard_stage_prepare_result",
        "status": "passed" if not blockers else "blocked",
        "stage_path_token": "staged_codex_home/.codex/skills/skillguard",
        "comparison": comparison,
        "blockers": blockers,
        "claim_boundary": "Stage preparation copies the complete skill source minus declared runtime transients; it does not activate the user install.",
    }


def _run(command: list[str], cwd: Path, timeout: float) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {"status": "timed_out", "exit_code": None, "stdout_tail": (exc.stdout or "")[-2000:], "stderr_tail": (exc.stderr or "")[-2000:]}
    return {
        "status": "passed" if completed.returncode == 0 else "failed",
        "exit_code": completed.returncode,
        "stdout_tail": completed.stdout[-2000:],
        "stderr_tail": completed.stderr[-2000:],
    }


def smoke_installed_skill(installed_skill_root: Path, *, timeout_seconds: float = 120) -> dict[str, Any]:
    installed_skill_root = _safe_stage_path(installed_skill_root)
    layout_root = installed_skill_root.parents[2]
    relative_skill = installed_skill_root.relative_to(layout_root).as_posix()
    script = installed_skill_root / "scripts" / "skillguard.py"
    v2_script_root = installed_skill_root / "scripts"
    checks = [
        {
            "check_id": "installed:commands",
            "command": [sys.executable, str(script), "commands"],
        },
        {
            "check_id": "installed:self-check",
            "command": [sys.executable, str(script), "self-check", "--target", relative_skill],
        },
        {
            "check_id": "installed:v2-import",
            "command": [
                sys.executable,
                "-c",
                (
                    "import sys; "
                    f"sys.path.insert(0, {str(v2_script_root)!r}); "
                    "from skillguard_v2.runtime_fingerprint import guard_runtime_fingerprint; "
                    "assert guard_runtime_fingerprint()['file_count'] >= 1"
                ),
            ],
        },
        {
            "check_id": "installed:v1-lifecycle",
            "command": [
                sys.executable,
                "-c",
                (
                    "import sys; from pathlib import Path; "
                    f"sys.path.insert(0, {str(v2_script_root)!r}); "
                    "from skillguard_v2.field_lifecycle import build_v1_field_lifecycle_plan; "
                    f"assert build_v1_field_lifecycle_plan(Path({str(installed_skill_root)!r}))['status'] == 'passed'"
                ),
            ],
        },
    ]
    results = []
    for check in checks:
        result = _run(check["command"], layout_root, timeout_seconds)
        result["check_id"] = check["check_id"]
        results.append(result)
        if result["status"] != "passed":
            break
    return {
        "artifact_type": "skillguard_installed_smoke_result",
        "status": "passed" if len(results) == len(checks) and all(row["status"] == "passed" for row in results) else "failed",
        "checks": results,
        "skipped_checks": [row["check_id"] for row in checks[len(results) :]],
        "claim_boundary": "Installed smoke proves local command dispatch, installed-layout self-check, V2 import, and V1 lifecycle expansion only.",
    }


def verify_stage(canonical_skill_root: Path, stage_root: Path) -> dict[str, Any]:
    stage_root = _safe_stage_path(stage_root)
    comparison = compare_skill_sources(canonical_skill_root.resolve(), stage_root)
    parity = not any(
        comparison[key]
        for key in ("missing_in_installed", "changed_in_installed", "unexpected_in_installed")
    )
    smoke = smoke_installed_skill(stage_root)
    blockers = []
    if not parity:
        blockers.append("staged_source_parity_failed")
    if smoke["status"] != "passed":
        blockers.append("staged_installed_smoke_failed")
    return {
        "artifact_type": "skillguard_stage_verification",
        "status": "passed" if not blockers else "blocked",
        "comparison": comparison,
        "smoke": smoke,
        "blockers": blockers,
        "claim_boundary": "Stage verification does not activate or mutate the current user install.",
    }


def activate_stage(canonical_skill_root: Path, stage_root: Path, codex_home: Path) -> dict[str, Any]:
    canonical_skill_root = canonical_skill_root.resolve()
    stage_root = _safe_stage_path(stage_root)
    codex_home = codex_home.resolve()
    active = (codex_home / "skills" / "skillguard").resolve()
    if active == stage_root or stage_root.is_relative_to(active):
        raise ValueError("stage and active roots must be distinct")
    verification = verify_stage(canonical_skill_root, stage_root)
    if verification["status"] != "passed":
        return {
            "artifact_type": "skillguard_install_activation",
            "status": "blocked",
            "blockers": ["stage_verification_failed"],
            "stage_verification": verification,
            "claim_boundary": "No active install mutation occurred.",
        }
    active.parent.mkdir(parents=True, exist_ok=True)
    backup_root = codex_home / "backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = backup_root / f"skillguard-{timestamp}-{uuid.uuid4().hex[:8]}"
    incoming = active.parent / f".skillguard-installing-{uuid.uuid4().hex}"
    shutil.copytree(stage_root, incoming, ignore=_ignore)
    incoming_comparison = compare_skill_sources(canonical_skill_root, incoming)
    if any(incoming_comparison[key] for key in ("missing_in_installed", "changed_in_installed", "unexpected_in_installed")):
        incoming.rename(backup_root / f"failed-incoming-{timestamp}-{uuid.uuid4().hex[:8]}")
        return {
            "artifact_type": "skillguard_install_activation",
            "status": "blocked",
            "blockers": ["incoming_source_parity_failed"],
            "claim_boundary": "The active install was not changed.",
        }
    active_was_present = active.exists()
    try:
        if active_was_present:
            active.rename(backup)
        incoming.rename(active)
        smoke = smoke_installed_skill(active)
        parity = compare_skill_sources(canonical_skill_root, active)
        if smoke["status"] != "passed" or any(
            parity[key] for key in ("missing_in_installed", "changed_in_installed", "unexpected_in_installed")
        ):
            failed = backup_root / f"failed-active-{timestamp}-{uuid.uuid4().hex[:8]}"
            active.rename(failed)
            if active_was_present:
                backup.rename(active)
            return {
                "artifact_type": "skillguard_install_activation",
                "status": "rolled_back",
                "blockers": ["post_activation_verification_failed"],
                "smoke": smoke,
                "active_path_token": "codex_home/skills/skillguard",
                "backup_path_token": "codex_home/backups/skillguard-<timestamp>",
                "claim_boundary": "The prior active install was restored; the failed candidate was retained for diagnosis.",
            }
    except Exception:
        if not active.exists() and active_was_present and backup.exists():
            backup.rename(active)
        raise
    return {
        "artifact_type": "skillguard_install_activation",
        "status": "passed",
        "active_path_token": "codex_home/skills/skillguard",
        "backup_path_token": "codex_home/backups/skillguard-<timestamp>" if active_was_present else "not_applicable",
        "smoke": smoke,
        "comparison": parity,
        "blockers": [],
        "claim_boundary": "Activation proves the current local installed tree and smoke boundary; it does not prove global-router freshness or GitHub publication.",
    }
