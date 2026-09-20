"""Shared JSON, timestamp, and report helpers for SkillGuard scripts."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, TextIO

from skillguard_v2.path_identity import canonical_filesystem_path, physical_relative_path


REPORT_OUTPUT_DIRECTORIES = (
    "work",
    ".skillguard/runs",
    ".skillguard/reports",
    ".skillguard/test-results",
)

CLI_SUMMARY_SCHEMA = "skillguard.cli_summary.v1"
CLI_SUMMARY_MAX_ITEMS = 10
CLI_SUMMARY_TEXT_LIMIT = 240


def skill_root() -> Path:
    return Path(__file__).resolve().parent.parent


def repository_root_for_skill_root(root: Path) -> Path:
    resolved = canonical_filesystem_path(root)
    if resolved.parent.name == "skills" and resolved.parent.parent.name == ".agents":
        return resolved.parents[2]
    if resolved.parent.name == "skills" and resolved.parent.parent.name == ".codex":
        return resolved.parents[2]
    return resolved


def repository_root() -> Path:
    return repository_root_for_skill_root(skill_root())


def utc_timestamp() -> str:
    """Return a stable UTC timestamp format for machine-readable reports."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_under_root(path_text: str | Path, root: Path | None = None) -> Path:
    base = canonical_filesystem_path(root or repository_root())
    candidate = Path(path_text)
    if not candidate.is_absolute():
        candidate = base / candidate
    try:
        relative = physical_relative_path(candidate, base)
    except ValueError as exc:
        raise ValueError(f"path must stay under configured root: {path_text}") from exc
    return base / relative


def public_relative_path(path_text: str | Path, root: Path | None = None) -> str:
    base = canonical_filesystem_path(root or repository_root())
    candidate = Path(path_text)
    if not candidate.is_absolute():
        candidate = base / candidate
    return physical_relative_path(candidate, base).as_posix()


def load_json(path_text: str | Path, root: Path | None = None) -> Any:
    path = ensure_under_root(path_text, root)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_jsonl(path_text: str | Path, root: Path | None = None) -> list[Any]:
    path = ensure_under_root(path_text, root)
    records: list[Any] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{public_relative_path(path, root)} line {line_number}: {exc}") from exc
    return records


def json_text(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _short_text(value: Any, limit: int = CLI_SUMMARY_TEXT_LIMIT) -> str:
    text = str(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _compact_value(value: Any, *, depth: int = 0) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _short_text(value)
    if depth >= 2:
        return _short_text(value)
    if isinstance(value, Mapping):
        preferred = (
            "id",
            "name",
            "status",
            "decision",
            "state",
            "required",
            "summary",
            "code",
            "path",
            "source_path",
            "kind",
            "fresh",
            "evidence_id",
            "check_id",
            "route_id",
            "route_node_id",
            "command_family",
            "confidence",
            "blocker_code",
            "blocker_class",
            "message",
            "recommended_resolution",
            "record_kind",
            "artifact_id",
            "observed_shape",
            "expected_schema_version",
            "recommended_repair_action",
            "schema_version",
            "relative_path",
            "content_hash",
            "logical_content_hash",
            "execution_count",
            "run_root",
            "full_report_path",
        )
        keys = [key for key in preferred if key in value]
        if not keys:
            keys = [key for key in sorted(value) if not str(key).startswith("_")][:8]
        return {str(key): _compact_value(value[key], depth=depth + 1) for key in keys}
    if isinstance(value, (list, tuple)):
        return [_compact_value(item, depth=depth + 1) for item in list(value)[:CLI_SUMMARY_MAX_ITEMS]]
    return _short_text(value)


def _compact_list(value: Any) -> list[Any]:
    if not isinstance(value, (list, tuple)):
        return []
    return [_compact_value(item) for item in list(value)[:CLI_SUMMARY_MAX_ITEMS]]


def _compact_maintenance_record(value: Any) -> Any:
    if not isinstance(value, Mapping):
        return None
    keys = (
        "schema_version",
        "record_kind",
        "artifact_id",
        "route_node_id",
        "checker_name",
        "route_version",
        "route_registry_version",
        "decision",
        "status",
    )
    return {key: _compact_value(value[key]) for key in keys if key in value}


def summarize_payload(payload: Any, *, full_report_path: str = "") -> dict[str, Any]:
    """Project one bounded CLI summary without changing the machine report."""

    if not isinstance(payload, Mapping):
        return {
            "schema_version": CLI_SUMMARY_SCHEMA,
            "artifact_type": "skillguard_cli_summary",
            "status": "failed",
            "decision": "fail",
            "scope": "",
            "counts": {},
            "truncated_count": 0,
            "issues": [{"source": "payload", "index": 0, "text": _short_text(payload)}],
            "claim_boundary": "This summary represents a non-object CLI result and proves no target work.",
            "full_report_path": full_report_path,
        }

    command = str(payload.get("command") or "")
    status = payload.get("status")
    decision = payload.get("decision")
    if status is None:
        status = decision or "unknown"
    if decision is None:
        decision = status
    scope = payload.get("target_path") or payload.get("scope") or payload.get("profile") or ""
    counts: dict[str, int | float] = {}
    for key, value in payload.items():
        if isinstance(value, (list, tuple)) and key not in {"commands"}:
            counts[key] = len(value)
        elif isinstance(value, (int, float)) and not isinstance(value, bool) and (
            key.endswith("_count") or key == "count"
        ):
            counts[key] = value

    blockers = list(payload.get("blockers") or []) if isinstance(payload.get("blockers"), list) else []
    failures = list(payload.get("failures") or []) if isinstance(payload.get("failures"), list) else []
    findings = list(payload.get("findings") or []) if isinstance(payload.get("findings"), list) else []
    indexed_issues = [
        {"source": "blockers", "index": index, "text": _short_text(item)}
        for index, item in enumerate(blockers)
    ]
    indexed_issues.extend(
        {"source": "failures", "index": index, "text": _short_text(item)}
        for index, item in enumerate(failures)
    )
    if not indexed_issues:
        indexed_issues.extend(
            {"source": "findings", "index": index, "text": _short_text(item)}
            for index, item in enumerate(findings)
        )
    issues = indexed_issues[:CLI_SUMMARY_MAX_ITEMS]

    base: dict[str, Any] = {
        "schema_version": CLI_SUMMARY_SCHEMA,
        "source_schema_version": str(payload.get("schema_version") or ""),
        "artifact_type": "skillguard_cli_summary",
        "command": command,
        "status": _short_text(status),
        "decision": _short_text(decision),
        "scope": _short_text(scope),
        "counts": counts,
        "truncated_count": max(0, len(indexed_issues) - len(issues)),
        "issues": issues,
        "blockers": _compact_list(blockers),
        "failures": _compact_list(failures),
        "finding_count": len(findings),
        "finding_codes": [
            _short_text(item.get("code") if isinstance(item, Mapping) else item)
            for item in findings[:CLI_SUMMARY_MAX_ITEMS]
        ],
        "checks": _compact_list(payload.get("checks")),
        "evidence": _compact_list(payload.get("evidence")),
        "skipped_checks": _compact_list(payload.get("skipped_checks")),
        "residual_risk": _compact_list(payload.get("residual_risk")),
        "primary_blocker": _short_text(blockers[0]) if blockers else "",
        "claim_boundary": _short_text(payload.get("claim_boundary") or ""),
        "full_report_path": full_report_path or _short_text(payload.get("full_report_path") or ""),
        "full_report_hint": "Use --output <path> to save the complete machine report." if not full_report_path else "",
    }
    reserved = set(base) | {"maintenance_record"}
    for key, value in payload.items():
        if key in reserved or key in {"commands", "reports", "suite", "current_route_registry"}:
            continue
        if isinstance(value, (str, bool, int, float)) or value is None:
            base[str(key)] = _compact_value(value)
        elif isinstance(value, list):
            base[str(key)] = _compact_list(value)
        elif isinstance(value, Mapping):
            base[str(key)] = _compact_value(value)
    maintenance_record = _compact_maintenance_record(payload.get("maintenance_record"))
    if maintenance_record:
        base["maintenance_record"] = maintenance_record
    for key in (
        "routing_decision",
        "target_binding",
        "runtime_authority",
        "surface_inventory",
        "validation_registry",
        "aggregation_ref",
    ):
        if key in payload:
            base[key] = _compact_value(payload[key])
    for key in (
        "run_root",
        "aggregation_ref_path",
        "execution_count",
        "executed_count",
        "reused_count",
        "not_run",
    ):
        if key in payload:
            base[key] = _compact_value(payload[key])

    if command == "commands" and isinstance(payload.get("commands"), list):
        rows = payload["commands"]
        base = {
            "schema_version": CLI_SUMMARY_SCHEMA,
            "source_schema_version": str(payload.get("schema_version") or ""),
            "artifact_type": "skillguard_command_surface_summary",
            "command": command,
            "status": _short_text(status),
            "decision": _short_text(decision),
            "command_count": len(rows),
            "truncated_count": 0,
            "query": "skillguard.py <command> --help",
            "commands": [
                {
                    "name": str(row.get("name") or ""),
                    "purpose": _short_text(row.get("summary") or "", 40),
                }
                for row in rows[:CLI_SUMMARY_MAX_ITEMS * 6]
                if isinstance(row, Mapping)
            ],
            "claim_boundary": _short_text(payload.get("claim_boundary") or ""),
            "full_report_path": full_report_path,
            "full_report_hint": "Use --output <path> to save the complete command surface.",
            "failures": [],
            "blockers": [],
        }
        base["truncated_count"] = max(0, len(rows) - len(base["commands"]))
        if maintenance_record:
            base["maintenance_record"] = maintenance_record
    return base


def emit_json(
    payload: Any,
    stream: TextIO | None = None,
    *,
    full_output: bool = False,
    output: str | Path | None = None,
    root: Path | None = None,
    full_report_path: str = "",
) -> None:
    """Write a complete report to an explicit file and a bounded summary to stdout."""

    if output is not None and str(output) != "-":
        path = dump_json(payload, output, root)
        full_report_path = str(path)
    elif full_output:
        raise ValueError("--full-output requires --output PATH")
    if stream is None:
        stream = sys.stdout
    stream.write(json_text(summarize_payload(payload, full_report_path=full_report_path)))
    stream.flush()


def dump_json(payload: Any, path_text: str | Path, root: Path | None = None) -> Path:
    path = ensure_under_root(path_text, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_text(payload), encoding="utf-8")
    return path


def write_report(payload: Any, output: str | Path | None = None, root: Path | None = None) -> Path | None:
    if output is None or str(output) == "-":
        emit_json(payload)
        return None
    base = canonical_filesystem_path(root or skill_root())
    path = ensure_under_root(output, base)
    allowed_roots = [(base / relative).resolve() for relative in REPORT_OUTPUT_DIRECTORIES]
    if not any(path == allowed or path.is_relative_to(allowed) for allowed in allowed_roots):
        allowed_text = ", ".join(REPORT_OUTPUT_DIRECTORIES)
        raise ValueError(
            f"report output must be stdout or stay under a runtime evidence directory ({allowed_text}); "
            "maintained source and fixture trees are not report destinations"
        )
    written = dump_json(payload, path, base)
    emit_json(payload, full_report_path=str(written))
    return written
