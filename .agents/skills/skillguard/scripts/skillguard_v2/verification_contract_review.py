"""Pre-execution review for SkillGuard-maintained OpenSpec contracts."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import posixpath
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

from .portable_content import RUNTIME, classify_relative_path


REVIEW_SCHEMA = "skillguard.verification_contract_review.v1"
REPORT_COLLISION_CODE = "verification_report_in_freshness_watch"
EVIDENCE_OUTPUT_COLLISION_CODE = "verification_evidence_output_in_freshness_watch"
_EVIDENCE_ROOT_FLAGS = frozenset(
    {
        "--closure-receipt-root",
        "--receipt-root",
        "--replay-receipt-root",
        "--result-root",
    }
)
_RUNTIME_CONTROL_PARTS = frozenset(
    {
        "bootstrap",
        "evidence",
        "locks",
        "portfolio-artifacts",
        "progress",
        "receipts",
        "reports",
        "reuse-sources",
        "reuse-tickets",
        "runs",
        "test-results",
    }
)


@dataclass(frozen=True)
class VerificationContractFinding:
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


def _scalar(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        try:
            return str(json.loads(text)) if text[0] == '"' else text[1:-1].replace("''", "'")
        except json.JSONDecodeError:
            return text[1:-1]
    return text


def _contract_projection(text: str) -> dict[str, Any]:
    """Parse the bounded contract fields needed for a pre-execution review.

    OpenSpec remains the full YAML/schema authority. This deliberately small
    projection refuses ambiguous tabs and observes only checks plus freshness
    watch entries, so it cannot silently reinterpret the execution contract.
    """

    if "\t" in text:
        raise ValueError("verification_contract_tabs_not_supported")
    section = ""
    active_list = ""
    current: dict[str, Any] | None = None
    checks: list[dict[str, Any]] = []
    watch: list[str] = []
    for raw in text.splitlines():
        line = raw.split(" #", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        body = line.strip()
        if indent == 0 and body.endswith(":"):
            section = body[:-1]
            active_list = ""
            current = None
            continue
        if section == "checks":
            if indent == 2 and body.startswith("- id:"):
                current = {"id": _scalar(body.split(":", 1)[1]), "args": [], "covers": []}
                checks.append(current)
                active_list = ""
                continue
            if current is None:
                continue
            if indent == 4 and body.endswith(":"):
                active_list = body[:-1]
                continue
            if indent == 4 and ":" in body:
                key, value = body.split(":", 1)
                current[key] = _scalar(value)
                active_list = ""
                continue
            if indent == 6 and body.startswith("- ") and active_list in {"args", "covers"}:
                current.setdefault(active_list, []).append(_scalar(body[2:]))
                continue
        if section == "freshness":
            if indent == 2 and body == "watch:":
                active_list = "watch"
                continue
            if indent == 4 and body.startswith("- ") and active_list == "watch":
                watch.append(_scalar(body[2:]))
    return {"checks": checks, "watch": watch}


def _portable_repo_token(value: str) -> PurePosixPath | None:
    text = value.replace("\\", "/").strip()
    if not text or text.startswith("/") or (len(text) > 1 and text[1] == ":"):
        return None
    normalized = posixpath.normpath(text)
    token = PurePosixPath(normalized)
    if normalized in {".", ".."} or any(part == ".." for part in token.parts):
        return None
    return token


def _glob_matches(relative: str, pattern: str) -> bool:
    # fnmatch covers future files; PurePath.match makes ** directory intent
    # explicit on Python versions where fnmatch treats it as ordinary stars.
    return fnmatch.fnmatchcase(relative, pattern) or PurePosixPath(relative).match(pattern)


def _link_equivalent(left: Path, right: Path) -> bool:
    try:
        if left.exists() and right.exists() and os.path.samefile(left, right):
            return True
        return os.path.normcase(str(left.resolve(strict=False))) == os.path.normcase(
            str(right.resolve(strict=False))
        )
    except (OSError, ValueError):
        return False


def _normalized_command(check: Mapping[str, Any]) -> str:
    command = str(check.get("command", "")).strip().casefold()
    tokens = [command]
    for raw in check.get("args", []):
        token = str(raw).strip().replace("\\", "/")
        if "/" in token or token.startswith("."):
            token = posixpath.normpath(token)
        tokens.append(token)
    return "\u0000".join(tokens)


def _declared_evidence_roots(checks: Iterable[Mapping[str, Any]]) -> tuple[str, ...]:
    roots: set[str] = set()
    for check in checks:
        args = [str(value) for value in check.get("args", [])]
        for index, value in enumerate(args[:-1]):
            if value not in _EVIDENCE_ROOT_FLAGS:
                continue
            token = _portable_repo_token(args[index + 1])
            if token is not None:
                roots.add(token.as_posix())
    return tuple(sorted(roots))


def _static_glob_prefix(pattern: str) -> str:
    parts: list[str] = []
    for part in PurePosixPath(pattern).parts:
        if any(character in part for character in "*?["):
            break
        parts.append(part)
    return PurePosixPath(*parts).as_posix() if parts else ""


def _freshness_output_reason(
    pattern: str,
    *,
    declared_evidence_roots: Iterable[str],
) -> str:
    folded_parts = tuple(part.casefold() for part in PurePosixPath(pattern).parts)
    prefix = _static_glob_prefix(pattern).rstrip("/")
    for root in declared_evidence_roots:
        normalized_root = root.rstrip("/")
        if (
            _glob_matches(normalized_root, pattern)
            or (prefix and normalized_root.startswith(prefix + "/"))
            or normalized_root == prefix
            or pattern == normalized_root
            or pattern.startswith(normalized_root + "/")
        ):
            return f"declared_evidence_root:{normalized_root}"
    if any(
        left == "work" and right == "verification"
        for left, right in zip(folded_parts, folded_parts[1:])
    ):
        return "verification_work_root"
    if ".sg-runtime" in folded_parts:
        return "reserved_runtime_workspace"
    if ".skillguard" in folded_parts:
        control_index = folded_parts.index(".skillguard")
        remainder = folded_parts[control_index + 1 :]
        if any(part in _RUNTIME_CONTROL_PARTS for part in remainder):
            return "skillguard_runtime_control"
        final_name = remainder[-1] if remainder else ""
        if "receipt" in final_name or final_name == "head.json":
            return "skillguard_receipt_output"
        if any(any(character in part for character in "*?[") for part in remainder):
            return "ambiguous_skillguard_control_glob"
    if not any(character in pattern for character in "*?["):
        decision = classify_relative_path(pattern)
        if decision.classification == RUNTIME:
            return decision.reason
    return ""


def review_verification_contract(
    contract_path: Path,
    *,
    repository_root: Path,
    report_path: Path | None = None,
) -> dict[str, Any]:
    repo = repository_root.resolve(strict=True)
    contract = contract_path.resolve(strict=True)
    try:
        contract.relative_to(repo)
    except ValueError as exc:
        raise ValueError("verification_contract_escapes_repository") from exc
    report = (report_path or contract.parent / "verification-report.json").resolve(strict=False)
    findings: list[VerificationContractFinding] = []
    try:
        report_relative = report.relative_to(repo).as_posix()
    except ValueError:
        report_relative = "<outside-repository>"
        findings.append(
            VerificationContractFinding(
                "verification_report_escapes_repository",
                "$.report_path",
                str(report_path or report),
            )
        )

    try:
        projection = _contract_projection(contract.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        projection = {"checks": [], "watch": []}
        findings.append(
            VerificationContractFinding(
                "verification_contract_projection_invalid", "$.contract", str(exc)
            )
        )

    evidence_roots = _declared_evidence_roots(projection["checks"])
    for index, raw in enumerate(projection["watch"]):
        token = _portable_repo_token(str(raw))
        path = f"$.freshness.watch[{index}]"
        if token is None:
            findings.append(
                VerificationContractFinding("freshness_watch_path_invalid", path, str(raw))
            )
            continue
        pattern = token.as_posix()
        lexical_collision = (
            report_relative != "<outside-repository>"
            and _glob_matches(report_relative, pattern)
        )
        watch_candidate = repo / Path(*token.parts)
        exact_or_link_collision = not any(char in pattern for char in "*?[") and (
            pattern == report_relative or _link_equivalent(watch_candidate, report)
        )
        if lexical_collision or exact_or_link_collision:
            findings.append(
                VerificationContractFinding(REPORT_COLLISION_CODE, path, pattern)
            )
        output_reason = _freshness_output_reason(
            pattern,
            declared_evidence_roots=evidence_roots,
        )
        if output_reason:
            findings.append(
                VerificationContractFinding(
                    EVIDENCE_OUTPUT_COLLISION_CODE,
                    path,
                    f"{output_reason}:{pattern}",
                )
            )

    owners: dict[tuple[str, str, str], str] = {}
    for index, check in enumerate(projection["checks"]):
        check_id = str(check.get("id", ""))
        normalized = _normalized_command(check)
        domain = str(check.get("evidence_domain", "default"))
        if not check_id or not normalized.split("\u0000", 1)[0]:
            continue
        for obligation in check.get("covers", []):
            key = (normalized, str(obligation), domain)
            owner = owners.get(key)
            if owner is not None and owner != check_id:
                findings.append(
                    VerificationContractFinding(
                        "duplicate_normalized_command_obligation_owner",
                        f"$.checks[{index}]",
                        f"{owner}|{check_id}|{obligation}|{domain}",
                    )
                )
            else:
                owners[key] = check_id

    payload = {
        "schema_version": REVIEW_SCHEMA,
        "status": "blocked" if findings else "passed",
        "contract_path": contract.relative_to(repo).as_posix(),
        "report_path": report_relative,
        "watch_count": len(projection["watch"]),
        "check_count": len(projection["checks"]),
        "declared_evidence_roots": list(evidence_roots),
        "findings": [finding.to_dict() for finding in findings],
        "claim_boundary": (
            "This pre-execution projection checks report/evidence-output freshness collisions and duplicate "
            "normalized command-obligation owners. OpenSpec remains the full verification-contract authority."
        ),
    }
    payload["review_hash"] = hashlib.sha256(
        (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    ).hexdigest().upper()
    return payload


def audit_active_verification_contracts(repository_root: Path) -> dict[str, Any]:
    repo = repository_root.resolve(strict=True)
    changes = repo / "openspec" / "changes"
    reports = []
    if changes.is_dir():
        for contract in sorted(changes.glob("*/verification-contract.yaml")):
            reports.append(review_verification_contract(contract, repository_root=repo))
    return {
        "schema_version": "skillguard.verification_contract_audit.v1",
        "status": "passed" if all(row["status"] == "passed" for row in reports) else "blocked",
        "reports": reports,
    }


__all__ = [
    "EVIDENCE_OUTPUT_COLLISION_CODE",
    "REPORT_COLLISION_CODE",
    "REVIEW_SCHEMA",
    "VerificationContractFinding",
    "audit_active_verification_contracts",
    "review_verification_contract",
]
