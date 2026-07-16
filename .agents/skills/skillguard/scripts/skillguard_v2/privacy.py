"""Privacy and repository-boundary checks for public SkillGuard exports."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from .contract_compiler import file_hash
from .portable_content import RUNTIME, classify_relative_path
from .provenance import _git


SECRET_PATTERNS = (
    ("private_key_material", re.compile(r"BEGIN (?:RSA |OPENSSH |DSA |EC |PGP )?PRIVATE\s+KEY")),
    ("credential_assignment", re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?token|secret|password)\b\s*[:=]\s*['\"]?[^\s'\"]{8,}")),
    ("github_token", re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b")),
)


def public_path_token(path: Path, repository_root: Path, installed_root: Path | None = None) -> str:
    resolved = path.resolve()
    repository_root = repository_root.resolve()
    try:
        relative = resolved.relative_to(repository_root)
        return f"repository_root/{relative.as_posix()}"
    except ValueError:
        pass
    if installed_root is not None:
        installed_root = installed_root.resolve()
        try:
            relative = resolved.relative_to(installed_root)
            return f"installed_skill_root/{relative.as_posix()}"
        except ValueError:
            pass
    return "external_path_redacted"


def git_public_candidates(repository_root: Path) -> list[str]:
    output = _git(repository_root, "ls-files", "--cached", "--others", "--exclude-standard")
    candidates = {
        row.strip().replace("\\", "/")
        for row in output.splitlines()
        if row.strip()
    }
    return sorted(
        path_text
        for path_text in candidates
        if (repository_root / path_text).is_file()
    )


def _line_findings(path_text: str, text: str, sensitive_literals: Iterable[str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    normalized_literals = {item for value in sensitive_literals for item in (value, value.replace("\\", "/")) if item}
    for line_number, line in enumerate(text.splitlines(), 1):
        for code, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append({"code": code, "path": path_text, "line": line_number})
        if any(literal in line for literal in normalized_literals):
            findings.append({"code": "machine_specific_absolute_path", "path": path_text, "line": line_number})
    return findings


def audit_public_export(
    repository_root: Path,
    policy_path: Path,
    *,
    candidate_paths: Iterable[str] | None = None,
    sensitive_roots: Iterable[Path] = (),
) -> dict[str, Any]:
    repository_root = repository_root.resolve()
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    candidates = list(candidate_paths) if candidate_paths is not None else git_public_candidates(repository_root)
    blocked_extensions = {str(item).lower() for item in policy.get("blocked_extensions", [])}
    blocked_names = {str(item).lower() for item in policy.get("blocked_names", [])}
    runtime_prefixes = tuple(str(item) for item in policy.get("runtime_path_prefixes", []))
    allowed_binary = {str(item).lower() for item in policy.get("allowed_binary_extensions", [])}
    visual_reviews = {
        str(row.get("asset_path", "")): str(row.get("review_path", ""))
        for row in policy.get("visual_review_records", [])
        if isinstance(row, Mapping) and row.get("asset_path")
    }
    sensitive_literals = [str(repository_root), str(Path.home()), *[str(path.resolve()) for path in sensitive_roots]]
    findings: list[dict[str, Any]] = []
    scanned_text = 0
    scanned_binary = 0
    for path_text in sorted(set(str(item).replace("\\", "/") for item in candidates)):
        path = (repository_root / path_text).resolve()
        try:
            path.relative_to(repository_root)
        except ValueError:
            findings.append({"code": "candidate_outside_repository", "path": "external_path_redacted", "line": 0})
            continue
        if not path.is_file():
            findings.append({"code": "candidate_missing", "path": path_text, "line": 0})
            continue
        lower_name = path.name.lower()
        suffix = path.suffix.lower()
        portable_decision = classify_relative_path(path_text)
        if portable_decision.classification == RUNTIME:
            findings.append(
                {
                    "code": "runtime_state_in_public_export",
                    "path": path_text,
                    "line": 0,
                }
            )
        if lower_name in blocked_names or suffix in blocked_extensions:
            findings.append({"code": "blocked_private_file_type", "path": path_text, "line": 0})
        if any(path_text.startswith(prefix) for prefix in runtime_prefixes):
            findings.append({"code": "runtime_state_in_public_export", "path": path_text, "line": 0})
        try:
            data = path.read_bytes()
        except OSError:
            findings.append(
                {"code": "candidate_unreadable", "path": path_text, "line": 0}
            )
            continue
        if b"\x00" in data[:4096] or suffix in allowed_binary:
            scanned_binary += 1
            if suffix in allowed_binary:
                review_text = visual_reviews.get(path_text, "")
                review_path = (repository_root / review_text).resolve() if review_text else None
                if review_path is None or not review_path.is_file():
                    findings.append({"code": "visual_privacy_review_missing", "path": path_text, "line": 0})
                else:
                    try:
                        review = json.loads(review_path.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        findings.append({"code": "visual_privacy_review_invalid", "path": path_text, "line": 0})
                    else:
                        checks = review.get("checks", {}) if isinstance(review, Mapping) else {}
                        required_visual_checks = {
                            "local_paths_visible",
                            "personal_accounts_visible",
                            "real_user_or_customer_data_visible",
                            "credentials_or_tokens_visible",
                        }
                        if (
                            review.get("asset_path") != path_text
                            or review.get("asset_sha256") != file_hash(path)
                            or review.get("status") != "passed"
                            or not isinstance(checks, Mapping)
                            or not required_visual_checks.issubset(checks)
                            or any(checks.get(key) is not False for key in required_visual_checks)
                        ):
                            findings.append({"code": "visual_privacy_review_stale_or_failed", "path": path_text, "line": 0})
            continue
        if len(data) > 2_000_000:
            findings.append({"code": "oversized_unreviewed_text", "path": path_text, "line": 0})
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            scanned_binary += 1
            findings.append({"code": "unapproved_binary_file", "path": path_text, "line": 0})
            continue
        scanned_text += 1
        findings.extend(_line_findings(path_text, text, sensitive_literals))
    blockers = sorted({f"{row['code']}:{row['path']}:{row['line']}" for row in findings})
    return {
        "artifact_type": "skillguard_public_export_audit",
        "status": "passed" if not blockers else "blocked",
        "candidate_count": len(candidates),
        "scanned_text_count": scanned_text,
        "scanned_binary_count": scanned_binary,
        "findings": findings,
        "evidence": [
            "tracked and unignored untracked candidate inventory",
            "runtime-state path policy",
            "blocked private file types",
            "redacted secret and machine-path line findings",
            "hash-bound visual privacy review records for allowed images",
        ],
        "failures": [],
        "blockers": blockers,
        "skipped_checks": [],
        "residual_risk": [
            "Any replacement or additional image requires its own current hash-bound visual privacy review."
        ],
        "claim_boundary": "This audit covers current repository candidate files and emits no matched secret or absolute-path content. It does not inspect future archives or remote-rendered pages.",
        "typed_next_actions": [
            "Remove or sanitize every blocked candidate and rerun before staging or packaging.",
            "Inspect allowed public screenshots visually before release.",
        ],
    }
