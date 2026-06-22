"""Checker-engine functions used by the SkillGuard CLI dispatch surface."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from skillguard_utils import (
    dump_json,
    ensure_under_root,
    load_json,
    load_jsonl,
    public_relative_path,
    repository_root,
    skill_root,
    utc_timestamp,
    write_report,
)


CHECKER_VERSION = "skillguard.local_cli_dispatch.v1"
SCHEMA_DIR = skill_root() / "assets" / "schemas"
MARKER_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
MARKER_STATUSES = ("checked", "needs-review", "blocked", "stale", "accepted")
REFERENCE_SPAN_RE = re.compile(r"`([^`]+)`")
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
REQUIRED_SKILL_SECTIONS = (
    "Purpose",
    "Entrypoint Scope",
    "Local Material Routing",
    "Entrypoint Acceptance Map",
    "Use When",
    "Do Not Use When",
    "Required Workflow",
    "Hard Gates",
    "Output Requirements",
    "SkillGuard Maintenance",
)
OUTPUT_REQUIREMENT_TERMS = {
    "evidence": ("evidence",),
    "failures": ("failures",),
    "blockers": ("blockers",),
    "skipped_checks": ("skipped_checks", "skipped checks", "skipped-check"),
    "residual_risk": ("residual_risk", "residual risk", "residual-risk"),
    "claim_boundary": ("claim_boundary", "claim boundary", "claim-boundary"),
}
ROOT_REFERENCE_NAMES = {"README.md", "AGENTS.md", "LICENSE", "VERSION", "pyproject.toml"}
OPTIONAL_TARGET_REFERENCES = {"fixtures/", "tests/", "examples/"}
CONTROL_JSON_RECORDS = (
    "skillguard_profile.json",
    "skillguard_skill_contract.json",
    "skillguard_evidence_rules.json",
    "skillguard_closure_policy.json",
    "skillguard_manifest.json",
)
CONTROL_RECORD_DIRS = ("ai_judgments", "evidence", "reports")
COMMON_CONTROL_FIELDS = (
    "schema_version",
    "target_path",
    "target_type",
    "status",
    "evidence",
    "failures",
    "blockers",
    "skipped_checks",
    "residual_risk",
    "claim_boundary",
)
COMMON_LIST_FIELDS = ("evidence", "failures", "blockers", "skipped_checks", "residual_risk")
CLAIM_BOUNDARY_REQUIRED_TERMS = (
    "runtime checker execution",
    "fixture coverage",
    "cli checks",
    "tests",
    "suite automation",
    "package publication",
    "code-contract validation",
)
SUPPORTED_STATUS_VALUES = {
    "accepted",
    "blocked",
    "checked",
    "closed_with_evidence",
    "draft",
    "initial_contract_record",
    "initial_judgment_record",
    "initial_policy_record",
    "initial_record",
    "initial_record_created",
    "initial_report",
    "needs-review",
    "not_run",
    "open",
    "stale",
}
SUPPORTED_AI_DECISIONS = {
    "bounded_support_only",
    "blocked",
    "fail",
    "needs_human_review",
    "not_run",
    "pass",
    "unsupported",
}
PUBLIC_SAFETY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private-local-path", re.compile(r"(?i)([A-Z]:[\\/][^\\s`\"']+|/Users/|\\\\[^\\s`\"']+)")),
    ("private-runtime-id", re.compile(r"\b(?:packet|lease|result)-\d{4,}\b")),
    ("private-key-material", re.compile(r"BEGIN (?:RSA |OPENSSH |DSA |EC |PGP )?" + "PRIVATE" + r"\s+KEY")),
    ("credential-assignment", re.compile(r"(?i)\b(?:api[_-]?key|secret|token|password)\b\s*[:=]")),
)
SUITE_RECORD_CANDIDATES = {
    "map": ("skillguard_suite_map.json", "suite_map.json"),
    "contract": ("skillguard_suite_contract.json", "suite_contract.json"),
}
SUITE_MEMBER_STATUS_VALUES = {
    "accepted",
    "block",
    "blocked",
    "checked",
    "draft",
    "fail",
    "incomplete",
    "needs-review",
    "not_run",
    "pass",
    "stale",
    "unsupported",
    "waived",
}
SUITE_RELATION_TYPES = {
    "dependency",
    "follow_up",
    "parent_child",
    "prerequisite",
    "release_group",
    "shared_evidence",
    "shared_fixture",
    "shared_reference",
    "shared_schema",
    "suite_member",
    "mutual_exclusion",
    "other",
}
UNSAFE_CLAIM_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("fixture-coverage", re.compile(r"(?i)\bfixture\s+" + "coverage" + r"\s+(?:passed|complete|validated|proven)\b")),
    ("full-suite-automation", re.compile(r"(?i)\b(?:full|complete|end-to-end)\s+suite\s+" + "automation" + r"\b")),
    ("package-publication", re.compile(r"(?i)\bpackage\s+" + "publication" + r"\s+(?:complete|ready|done|validated|proven)\b")),
    ("release-readiness", re.compile(r"(?i)\brelease\s+" + "readiness" + r"\s+(?:complete|ready|validated|proven)\b")),
    ("code-contract-validation", re.compile(r"(?i)\bcode-contract\s+" + "validation" + r"\s+(?:passed|complete|validated|proven)\b")),
    ("tests-passed", re.compile(r"(?i)\btests\s+" + "passed" + r"\b")),
)
SAFE_UNSAFE_CLAIM_CONTEXT = (
    "does not prove",
    "do not claim",
    "not claim",
    "not a substitute",
    "without separate current evidence",
    "unless current evidence",
    "unless separate current evidence",
)
FIXTURE_TARGET_SCHEMAS = {
    "check-skill-contract": "skillguard_skill_contract.schema.json",
    "check-suite-map": "skillguard_suite_map.schema.json",
    "check-suite-contract": "skillguard_suite_contract.schema.json",
    "check-fixture-manifest": "skillguard_fixture_manifest.schema.json",
    "check-ai-judgment": "skillguard_ai_judgment.schema.json",
    "check-report": "skillguard_check_report.schema.json",
    "check-workflow-report": "skillguard_workflow_report.schema.json",
}
FIXTURE_TARGET_RUNTIME_COMMANDS = {"check-skill", "check-suite", "self-check"}
FIXTURE_EXPECTED_DECISIONS = {"pass", "fail", "block"}
CLOSURE_FORBIDDEN_REFERENCE_MARKERS = (
    "acceptance_registry",
    "skillguard_progress_ledger.jsonl",
    "progress_ledger",
    "packet-",
    "lease-",
    "result-",
    "pm_visible",
    "pm text",
    "chat transcript",
)


class SkillGuardCliError(Exception):
    def __init__(self, command: str, message: str, category: str = "usage_error") -> None:
        super().__init__(message)
        self.command = command
        self.message = message
        self.category = category


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise SkillGuardCliError(self.prog, message)


def schema_path(name: str) -> Path:
    return ensure_under_root(SCHEMA_DIR / name)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def require_directory(path: Path, command: str) -> None:
    if not path.exists():
        raise SkillGuardCliError(command, f"target directory does not exist: {public_relative_path(path)}", "missing_file")
    if not path.is_dir():
        raise SkillGuardCliError(command, f"target is not a directory: {public_relative_path(path)}", "validation_error")


def control_root_for(target: Path) -> Path:
    return ensure_under_root(target / ".skillguard")


def suite_root_for(target: Path) -> Path:
    return ensure_under_root(control_root_for(target) / "suite")


def directory_state(path: Path) -> str:
    if path.is_dir():
        return "existing"
    if path.exists():
        return "blocked_non_directory"
    return "missing"


def file_state(path: Path) -> str:
    if path.is_file():
        return "existing"
    if path.exists():
        return "blocked_non_file"
    return "missing"


def marker_path(target: Path, scope: str, marker_name: str) -> Path:
    if not MARKER_NAME_RE.fullmatch(marker_name):
        raise SkillGuardCliError(
            "mark",
            "marker name must start with an ASCII letter or digit and contain only letters, digits, underscore, dot, or hyphen",
        )
    base = suite_root_for(target) if scope == "suite" else control_root_for(target)
    return ensure_under_root(base / "markers" / f"{marker_name}.json")


def marker_semantic_payload(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: record.get(key)
        for key in ("schema_version", "target_path", "scope", "marker", "status", "summary", "checker_version")
    }


def create_missing_directories(paths: list[Path]) -> tuple[list[str], list[str], list[str]]:
    created: list[str] = []
    existing: list[str] = []
    skipped: list[str] = []
    for path in paths:
        if path.is_dir():
            existing.append(public_relative_path(path))
            continue
        if path.exists():
            skipped.append(f"{public_relative_path(path)}: exists but is not a directory")
            continue
        path.mkdir(parents=True)
        created.append(public_relative_path(path))
    return created, existing, skipped


def marker_state_entries(target: Path) -> list[tuple[str, str, str, bool]]:
    control_root = control_root_for(target)
    suite_root = suite_root_for(target)
    entries: list[tuple[str, str, str, bool]] = [
        (public_relative_path(control_root), "directory", "report", False),
        (public_relative_path(control_root / "evidence"), "directory", "report", False),
        (public_relative_path(control_root / "ai_judgments"), "directory", "report", False),
        (public_relative_path(control_root / "reports"), "directory", "report", False),
        (public_relative_path(control_root / "markers"), "directory", "report", False),
        (public_relative_path(suite_root), "directory", "report", False),
        (public_relative_path(suite_root / "members"), "directory", "report", False),
        (public_relative_path(suite_root / "reports"), "directory", "report", False),
        (public_relative_path(suite_root / "markers"), "directory", "report", False),
    ]
    for marker_dir in (control_root / "markers", suite_root / "markers"):
        if marker_dir.is_dir():
            for marker in sorted(marker_dir.glob("*.json")):
                entries.append((public_relative_path(marker), "file", "report", False))
    return entries


def type_matches(value: Any, expected_type: str) -> bool:
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return (isinstance(value, int | float)) and not isinstance(value, bool)
    return True


def validate_schema_subset(value: Any, schema: dict[str, Any], location: str = "$") -> list[str]:
    failures: list[str] = []
    expected_type = schema.get("type")
    if isinstance(expected_type, str) and not type_matches(value, expected_type):
        return [f"{location}: expected {expected_type}"]

    if "const" in schema and value != schema["const"]:
        failures.append(f"{location}: expected const {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        failures.append(f"{location}: expected one of {schema['enum']!r}")
    if isinstance(value, str) and "minLength" in schema and len(value) < schema["minLength"]:
        failures.append(f"{location}: shorter than minLength {schema['minLength']}")
    if isinstance(value, int) and "minimum" in schema and value < schema["minimum"]:
        failures.append(f"{location}: smaller than minimum {schema['minimum']}")

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                failures.append(f"{location}.{key}: missing required field")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extra = sorted(set(value) - set(properties))
            for key in extra:
                failures.append(f"{location}.{key}: additional property is not allowed")
        for key, child_schema in properties.items():
            if key in value and isinstance(child_schema, dict):
                failures.extend(validate_schema_subset(value[key], child_schema, f"{location}.{key}"))

    if isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                failures.extend(validate_schema_subset(item, item_schema, f"{location}[{index}]"))

    return failures


def base_result(command: str, target_path: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": "skillguard.cli_result.v1",
        "checker_version": CHECKER_VERSION,
        "command": command,
        "checked_at": utc_timestamp(),
        "target_path": target_path or "",
        "checks": [],
        "evidence": [],
        "failures": [],
        "blockers": [],
        "skipped_checks": [],
        "residual_risk": [
            "This local command does not provide fixture coverage, suite automation, package publication, or code-contract validation."
        ],
        "claim_boundary": (
            "This result covers only the named local CLI invocation and the current files it loaded. "
            "It does not prove fixture coverage, tests, suite automation, package publication, "
            "code-contract validation, release readiness, or future AI behavior."
        ),
    }


def error_payload(command: str, message: str, category: str = "usage_error") -> dict[str, Any]:
    payload = base_result(command)
    payload["decision"] = "block" if category != "usage_error" else "fail"
    payload["failures"] = [message] if category == "usage_error" else []
    payload["blockers"] = [message] if category != "usage_error" else []
    payload["checks"] = [
        {
            "check_id": "cli-dispatch",
            "name": "CLI dispatch",
            "required": True,
            "status": payload["decision"],
            "summary": message,
        }
    ]
    return payload


def write_and_exit(payload: dict[str, Any], output: str | None = None) -> int:
    write_report(payload, output, skill_root())
    return 0 if payload.get("decision") == "pass" else 1


def parse_input_output(command: str, argv: list[str], description: str) -> argparse.Namespace:
    parser = JsonArgumentParser(prog=f"skillguard.py {command}", description=description)
    parser.add_argument("--input", required=True, help="Input JSON file under the repository root.")
    parser.add_argument("--output", default="-", help="Output report path under the skill root, or '-' for stdout.")
    return parser.parse_args(argv)


def check_json_record(command: str, argv: list[str], schema_name: str) -> int:
    args = parse_input_output(command, argv, f"Check an input JSON record against {schema_name}.")
    input_path = ensure_under_root(args.input)
    schema = load_json(schema_path(schema_name))
    data = load_json(input_path)
    failures = validate_schema_subset(data, schema)
    relative_input = public_relative_path(input_path)
    payload = base_result(command, relative_input)
    payload["decision"] = "pass" if not failures else "fail"
    payload["checks"] = [
        {
            "check_id": f"{command}:json-load",
            "name": "Input JSON load",
            "required": True,
            "status": "pass",
            "summary": f"Loaded {relative_input} with the Python standard library json module.",
        },
        {
            "check_id": f"{command}:schema-subset",
            "name": "Standard-library schema subset check",
            "required": True,
            "status": "pass" if not failures else "fail",
            "summary": "Checked required fields, basic types, const, enum, minLength, minimum, and additionalProperties where declared.",
        },
    ]
    payload["evidence"] = [
        {
            "evidence_id": "input-json",
            "kind": "parser_output",
            "fresh": True,
            "summary": f"Parsed {relative_input}; sha256={file_sha256(input_path)}.",
            "source_path": relative_input,
        },
        {
            "evidence_id": "schema-json",
            "kind": "parser_output",
            "fresh": True,
            "summary": f"Parsed schema assets/schemas/{schema_name}; sha256={file_sha256(schema_path(schema_name))}.",
            "source_path": f".agents/skills/skillguard/assets/schemas/{schema_name}",
        },
    ]
    payload["failures"] = failures
    return write_and_exit(payload, args.output)


def check_status(failures: list[str], blockers: list[str], failure_count: int, blocker_count: int) -> str:
    if len(blockers) > blocker_count:
        return "block"
    if len(failures) > failure_count:
        return "fail"
    return "pass"


def append_check(payload: dict[str, Any], check_id: str, name: str, status: str, summary: str) -> None:
    payload["checks"].append(
        {
            "check_id": check_id,
            "name": name,
            "required": True,
            "status": status,
            "summary": summary,
        }
    )


def clean_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_skill_frontmatter(text: str) -> tuple[dict[str, str], list[str]]:
    failures: list[str] = []
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, ["SKILL.md frontmatter must start at the first line"]

    closing_index: int | None = None
    for index, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            closing_index = index
            break
    if closing_index is None:
        return {}, ["SKILL.md frontmatter must have a closing delimiter"]

    frontmatter: dict[str, str] = {}
    for line_number, line in enumerate(lines[1:closing_index], 2):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            failures.append(f"SKILL.md frontmatter line {line_number}: expected key: value")
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        if not key:
            failures.append(f"SKILL.md frontmatter line {line_number}: empty key")
            continue
        frontmatter[key] = clean_scalar(value)
    for required_key in ("name", "description"):
        if not frontmatter.get(required_key):
            failures.append(f"SKILL.md frontmatter missing non-empty {required_key!r}")
    return frontmatter, failures


def looks_like_reference_span(reference_text: str) -> bool:
    reference_text = reference_text.strip()
    if reference_text in ROOT_REFERENCE_NAMES or reference_text == "SKILL.md":
        return True
    if reference_text.endswith((".md", ".json", ".toml", ".py", ".txt")):
        return True
    return "/" in reference_text or "\\" in reference_text or reference_text.startswith(".")


def extract_reference_tokens(text: str) -> list[str]:
    references: list[str] = []
    seen: set[str] = set()
    for match in REFERENCE_SPAN_RE.finditer(text):
        reference_text = match.group(1).strip()
        if reference_text and looks_like_reference_span(reference_text) and reference_text not in seen:
            seen.add(reference_text)
            references.append(reference_text)
    return references


def reference_label(reference: str) -> str:
    return "<absolute-path-redacted>" if Path(reference).is_absolute() else reference


def is_optional_reference(reference: str) -> bool:
    normalized = reference.replace("\\", "/")
    return normalized in OPTIONAL_TARGET_REFERENCES


def resolve_declared_reference(target: Path, reference: str) -> Path:
    repo = repository_root()
    normalized = reference.replace("\\", "/")
    if normalized == "SKILL.md":
        return target / "SKILL.md"
    if normalized in ROOT_REFERENCE_NAMES or normalized.startswith(".agents/") or normalized.startswith("references/"):
        return repo / normalized
    return target / normalized


def validate_reference(
    target: Path,
    reference: str,
    failures: list[str],
    blockers: list[str],
    *,
    allow_project_boundary: bool,
) -> dict[str, Any]:
    label = reference_label(reference)
    entry: dict[str, Any] = {
        "reference": label,
        "boundary": "repository" if allow_project_boundary else "target-skill",
        "required": not is_optional_reference(reference),
        "exists": False,
    }
    if Path(reference).is_absolute():
        blockers.append(f"{label}: absolute references are not allowed")
        entry["status"] = "block"
        entry["reason"] = "absolute reference"
        return entry

    candidate = resolve_declared_reference(target, reference) if allow_project_boundary else target / reference
    resolved = candidate.resolve()
    repo = repository_root().resolve()
    try:
        resolved.relative_to(repo)
    except ValueError:
        blockers.append(f"{label}: reference escapes repository boundary")
        entry["status"] = "block"
        entry["reason"] = "repository escape"
        return entry

    if not allow_project_boundary:
        try:
            resolved.relative_to(target.resolve())
        except ValueError:
            blockers.append(f"{label}: reference escapes target skill boundary")
            entry["status"] = "block"
            entry["reason"] = "target escape"
            entry["resolved_path"] = public_relative_path(resolved)
            return entry

    entry["resolved_path"] = public_relative_path(resolved)
    entry["kind"] = "directory" if resolved.is_dir() else "file" if resolved.is_file() else "missing"
    entry["exists"] = resolved.exists()
    if not resolved.exists() and not is_optional_reference(reference):
        failures.append(f"{label}: referenced path is missing")
        entry["status"] = "fail"
    else:
        entry["status"] = "pass"
        if not resolved.exists():
            entry["reason"] = "optional absent path declared as absent"
    return entry


def claim_boundary_missing_terms(claim_boundary: Any) -> list[str]:
    if not isinstance(claim_boundary, str) or not claim_boundary.strip():
        return list(CLAIM_BOUNDARY_REQUIRED_TERMS)
    lowered = claim_boundary.lower()
    return [term for term in CLAIM_BOUNDARY_REQUIRED_TERMS if term not in lowered]


def is_supported_status(status: Any) -> bool:
    return isinstance(status, str) and (status in SUPPORTED_STATUS_VALUES or status.startswith("initial_"))


def looks_like_record_path(value: str) -> bool:
    normalized = value.replace("\\", "/")
    return (
        normalized in ROOT_REFERENCE_NAMES
        or normalized == ".skillguard"
        or normalized.startswith(".")
        or normalized.startswith("assets/")
        or normalized.startswith("evidence/")
        or normalized.startswith("reports/")
        or normalized.startswith("ai_judgments/")
        or "/" in normalized
        or normalized.endswith((".md", ".json", ".toml", ".py"))
    )


def iter_record_path_fields(value: Any, prefix: str = "$") -> list[tuple[str, str]]:
    references: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}"
            if key in {"path", "source", "source_path", "target_path", "control_root"} and isinstance(child, str):
                if looks_like_record_path(child):
                    references.append((child_prefix, child))
            references.extend(iter_record_path_fields(child, child_prefix))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            references.extend(iter_record_path_fields(child, f"{prefix}[{index}]"))
    return references


def resolve_record_reference(target: Path, control_root: Path, value: str) -> Path:
    normalized = value.replace("\\", "/")
    if normalized.startswith(".skillguard"):
        return target / normalized
    if normalized.startswith(".agents/") or normalized.startswith("references/") or normalized in ROOT_REFERENCE_NAMES:
        return repository_root() / normalized
    return control_root / normalized


def validate_record_references(
    record: dict[str, Any],
    label: str,
    target: Path,
    control_root: Path,
    failures: list[str],
    blockers: list[str],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for context, value in iter_record_path_fields(record):
        entry: dict[str, Any] = {"record": label, "field": context, "reference": reference_label(value), "exists": False}
        if Path(value).is_absolute():
            blockers.append(f"{label} {context}: absolute path references are not allowed")
            entry["status"] = "block"
            entries.append(entry)
            continue
        resolved = resolve_record_reference(target, control_root, value).resolve()
        try:
            resolved.relative_to(repository_root().resolve())
        except ValueError:
            blockers.append(f"{label} {context}: path reference escapes repository boundary")
            entry["status"] = "block"
            entries.append(entry)
            continue
        entry["resolved_path"] = public_relative_path(resolved)
        entry["kind"] = "directory" if resolved.is_dir() else "file" if resolved.is_file() else "missing"
        entry["exists"] = resolved.exists()
        if not resolved.exists():
            failures.append(f"{label} {context}: referenced path is missing")
            entry["status"] = "fail"
        else:
            entry["status"] = "pass"
        entries.append(entry)
    return entries


def validate_common_record(
    record: Any,
    label: str,
    target: Path,
    control_root: Path,
    failures: list[str],
    blockers: list[str],
) -> list[dict[str, Any]]:
    if not isinstance(record, dict):
        failures.append(f"{label}: record must be a JSON object")
        return []

    for field in COMMON_CONTROL_FIELDS:
        if field not in record:
            failures.append(f"{label}: missing required field {field}")
    for field in ("schema_version", "target_path", "target_type", "status", "claim_boundary"):
        if field in record and not isinstance(record[field], str):
            failures.append(f"{label}: field {field} must be a string")
    for field in COMMON_LIST_FIELDS:
        if field in record and not isinstance(record[field], list):
            failures.append(f"{label}: field {field} must be an array")
    if "status" in record and not is_supported_status(record["status"]):
        failures.append(f"{label}: unsupported status value {record['status']!r}")
    for term in claim_boundary_missing_terms(record.get("claim_boundary")):
        failures.append(f"{label}: claim_boundary missing conservative term {term!r}")
    if isinstance(record.get("failures"), list) and record["failures"]:
        failures.append(f"{label}: record declares unresolved failures")
    if isinstance(record.get("blockers"), list) and record["blockers"]:
        blockers.append(f"{label}: record declares unresolved blockers")
    for index, skipped in enumerate(record.get("skipped_checks", []) if isinstance(record.get("skipped_checks"), list) else []):
        if not isinstance(skipped, dict):
            failures.append(f"{label}: skipped_checks[{index}] must be an object")
            continue
        for field in ("reason", "impact"):
            if not skipped.get(field):
                failures.append(f"{label}: skipped_checks[{index}] missing {field}")
    return validate_record_references(record, label, target, control_root, failures, blockers)


def validate_ai_judgment_record(record: Any, label: str, failures: list[str]) -> None:
    if not isinstance(record, dict):
        return
    for field in ("decision", "input_evidence", "confidence", "uncertainty", "human_review"):
        if field not in record:
            failures.append(f"{label}: AI judgment missing required field {field}")
    if "decision" in record and record["decision"] not in SUPPORTED_AI_DECISIONS:
        failures.append(f"{label}: unsupported AI judgment decision {record['decision']!r}")
    if "input_evidence" in record and not isinstance(record["input_evidence"], list):
        failures.append(f"{label}: input_evidence must be an array")
    if isinstance(record.get("input_evidence"), list) and not record["input_evidence"]:
        failures.append(f"{label}: input_evidence must not be empty")
    if "confidence" in record and not isinstance(record["confidence"], dict):
        failures.append(f"{label}: confidence must be an object")
    if "uncertainty" in record and not isinstance(record["uncertainty"], list):
        failures.append(f"{label}: uncertainty must be an array")
    human_review = record.get("human_review")
    if not isinstance(human_review, dict):
        failures.append(f"{label}: human_review must be an object")
    elif human_review.get("required") is not True:
        failures.append(f"{label}: human_review.required must be true for AI judgment records")


def validate_closure_policy_record(record: Any, label: str, failures: list[str]) -> None:
    if not isinstance(record, dict):
        return
    closure_states = record.get("closure_states")
    if not isinstance(closure_states, list):
        failures.append(f"{label}: closure_states must be an array")
        return
    required_states = {"open", "blocked", "closed_with_evidence", "not_run"}
    missing_states = sorted(required_states - set(closure_states))
    for state in missing_states:
        failures.append(f"{label}: closure_states missing {state!r}")
    if not isinstance(record.get("hard_gates"), list) or not record.get("hard_gates"):
        failures.append(f"{label}: hard_gates must be a non-empty array")


def inspect_control_json_file(
    path: Path,
    target: Path,
    control_root: Path,
    failures: list[str],
    blockers: list[str],
    inspected_files: list[dict[str, Any]],
    reference_entries: list[dict[str, Any]],
) -> dict[str, Any] | None:
    label = public_relative_path(path)
    try:
        record = load_json(path)
    except ValueError as exc:
        failures.append(f"{label}: invalid JSON: {exc}")
        return None
    inspected_files.append(
        {
            "path": label,
            "kind": "json",
            "sha256": file_sha256(path),
            "line_count": line_count(path),
        }
    )
    reference_entries.extend(validate_common_record(record, label, target, control_root, failures, blockers))
    if path.name == "skillguard_closure_policy.json":
        validate_closure_policy_record(record, label, failures)
    if path.parent.name == "ai_judgments" or record.get("target_type") == "ai_judgment":
        validate_ai_judgment_record(record, label, failures)
    return record if isinstance(record, dict) else None


def find_suite_record(suite_root: Path, explicit_path: str | None, record_kind: str) -> Path | None:
    if explicit_path:
        return ensure_under_root(explicit_path)
    for file_name in SUITE_RECORD_CANDIDATES[record_kind]:
        candidate = suite_root / file_name
        if candidate.is_file():
            return candidate
    return None


def read_json_record(path: Path, failures: list[str], inspected_files: list[dict[str, Any]]) -> Any:
    label = public_relative_path(path)
    try:
        data = load_json(path)
    except ValueError as exc:
        failures.append(f"{label}: invalid JSON: {exc}")
        return None
    inspected_files.append(
        {
            "path": label,
            "kind": "json",
            "sha256": file_sha256(path),
            "line_count": line_count(path),
        }
    )
    return data


def resolve_repository_reference(path_text: str, base_dir: Path | None = None) -> Path:
    value = Path(path_text)
    if value.is_absolute():
        candidate = value
    elif base_dir is not None and not path_text.replace("\\", "/").startswith((".agents/", "references/")) and path_text not in ROOT_REFERENCE_NAMES:
        candidate = base_dir / value
    else:
        candidate = repository_root() / value
    candidate = candidate.resolve()
    candidate.relative_to(repository_root().resolve())
    return candidate


def public_safety_findings(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    findings: list[dict[str, Any]] = []
    for finding_id, pattern in PUBLIC_SAFETY_PATTERNS:
        for match in pattern.finditer(text):
            findings.append(
                {
                    "finding_id": finding_id,
                    "path": public_relative_path(path),
                    "line": text[: match.start()].count("\n") + 1,
                }
            )
    return findings


def checked_file(path: Path, kind: str = "file") -> dict[str, Any]:
    return {
        "path": public_relative_path(path),
        "kind": kind,
        "sha256": file_sha256(path),
        "line_count": line_count(path),
    }


def stable_report_status(report: dict[str, Any]) -> str:
    value = report.get("decision", report.get("status", ""))
    return str(value).strip().lower()


def skipped_check_is_required(skipped: Any) -> bool:
    if not isinstance(skipped, dict):
        return True
    if skipped.get("required") is False:
        return False
    impact = str(skipped.get("status_impact") or skipped.get("impact") or "").lower()
    return not any(marker in impact for marker in ("not applicable", "out of scope", "does not affect", "not a pass claim"))


def closure_reference_forbidden(path_text: str) -> bool:
    lowered = path_text.replace("\\", "/").lower()
    return any(marker in lowered for marker in CLOSURE_FORBIDDEN_REFERENCE_MARKERS)


def collect_report_evidence_references(report: dict[str, Any], source_path: Path) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    for index, item in enumerate(report.get("evidence", []) if isinstance(report.get("evidence"), list) else []):
        if not isinstance(item, dict):
            continue
        path_text = item.get("source_path") or item.get("path") or item.get("source")
        if not isinstance(path_text, str) or not path_text:
            continue
        references.append(
            {
                "source": public_relative_path(source_path),
                "context": f"evidence[{index}]",
                "path": path_text,
                "sha256": item.get("sha256") or item.get("expected_sha256") or item.get("hash"),
                "line_count": item.get("line_count") or item.get("expected_line_count"),
                "fresh": item.get("fresh"),
            }
        )
    return references


def validate_closure_reference(ref: dict[str, Any], base_dir: Path, failures: list[str], blockers: list[str]) -> dict[str, Any]:
    path_text = ref.get("path", "")
    finding = dict(ref)
    finding["decision"] = "fail"
    if not isinstance(path_text, str) or not path_text:
        failures.append(f"{ref.get('source')} {ref.get('context')}: evidence reference missing path")
        return finding
    finding["path"] = reference_label(path_text)
    if closure_reference_forbidden(path_text):
        failures.append(f"{reference_label(path_text)}: stale history, PM text, runtime ids, or progress ledgers cannot support closure")
        return finding
    try:
        resolved = resolve_repository_reference(path_text, base_dir)
    except ValueError:
        blockers.append(f"{reference_label(path_text)}: evidence reference escapes repository boundary")
        finding["decision"] = "block"
        return finding
    finding["resolved_path"] = public_relative_path(resolved)
    finding["exists"] = resolved.exists()
    finding["kind"] = "directory" if resolved.is_dir() else "file" if resolved.is_file() else "missing"
    if not resolved.is_file():
        failures.append(f"{reference_label(path_text)}: closure evidence reference is missing or not a file")
        return finding
    actual_hash = file_sha256(resolved)
    actual_lines = line_count(resolved)
    finding["sha256"] = actual_hash
    finding["line_count"] = actual_lines
    problems: list[str] = []
    expected_hash = ref.get("sha256")
    expected_lines = ref.get("line_count")
    if isinstance(expected_hash, str) and expected_hash and expected_hash.upper() != actual_hash:
        problems.append("sha256 mismatch")
    if isinstance(expected_lines, int) and expected_lines != actual_lines:
        problems.append("line_count mismatch")
    if ref.get("fresh") is False:
        problems.append("evidence is explicitly marked not fresh")
    if problems:
        for problem in problems:
            failures.append(f"{reference_label(path_text)}: {problem}")
        finding["problems"] = problems
        return finding
    finding["decision"] = "pass"
    return finding


def coerce_required_flag(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"false", "no", "optional", "waived"}
    return default


def member_from_record(raw: Any, source: str, index: int) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    name = raw.get("name") or raw.get("skill_name") or raw.get("skill") or raw.get("target_skill")
    path = raw.get("path") or raw.get("skill_path")
    if not isinstance(name, str) or not isinstance(path, str):
        return None
    return {
        "name": name,
        "path": path,
        "role": raw.get("role") or raw.get("responsibility") or "",
        "status": raw.get("status") or "draft",
        "required": coerce_required_flag(raw.get("required"), True),
        "evidence_source": raw.get("evidence_source") or raw.get("evidence_location") or raw.get("evidence_path") or "",
        "source": source,
        "index": index,
        "raw": raw,
    }


def collect_suite_members(records: list[tuple[str, dict[str, Any]]], cli_members: list[str]) -> list[dict[str, Any]]:
    members: list[dict[str, Any]] = []
    for source, record in records:
        included = record.get("included_skills", [])
        if isinstance(included, list):
            for index, item in enumerate(included):
                member = member_from_record(item, source, index)
                if member is not None:
                    members.append(member)
    for index, member_arg in enumerate(cli_members):
        if "=" in member_arg:
            name, path = member_arg.split("=", 1)
        else:
            path = member_arg
            name = Path(path).name
        members.append(
            {
                "name": name.strip(),
                "path": path.strip(),
                "role": "cli-member",
                "status": "checked",
                "required": True,
                "evidence_source": "",
                "source": "cli",
                "index": index,
                "raw": {},
            }
        )
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for member in members:
        key = (member["name"], member["path"].replace("\\", "/"))
        if key not in merged:
            merged[key] = member
            continue
        existing = merged[key]
        existing["source"] = f"{existing['source']};{member['source']}"
        existing["required"] = existing["required"] or member["required"]
        if not existing.get("evidence_source") and member.get("evidence_source"):
            existing["evidence_source"] = member["evidence_source"]
        if existing.get("status") in {"draft", "needs-review"} and member.get("status"):
            existing["status"] = member["status"]
    return list(merged.values())


def validate_suite_member_path(
    member: dict[str, Any],
    suite_member_root: Path,
    failures: list[str],
    blockers: list[str],
) -> dict[str, Any]:
    name = member["name"]
    raw_path = member["path"]
    entry: dict[str, Any] = {
        "name": name,
        "path": reference_label(raw_path),
        "source": member["source"],
        "status": member["status"],
        "required": member["required"],
    }
    if Path(raw_path).is_absolute():
        blockers.append(f"member {name}: absolute member paths are not allowed")
        entry["decision"] = "block"
        return entry
    resolved = (repository_root() / raw_path).resolve()
    try:
        resolved.relative_to(suite_member_root.resolve())
    except ValueError:
        blockers.append(f"member {name}: path escapes suite member root")
        entry["decision"] = "block"
        if resolved.is_relative_to(repository_root().resolve()):
            entry["resolved_path"] = public_relative_path(resolved)
        return entry

    entry["resolved_path"] = public_relative_path(resolved)
    entry["kind"] = "directory" if resolved.is_dir() else "file" if resolved.is_file() else "missing"
    entry["skill_entrypoint"] = public_relative_path(resolved / "SKILL.md") if resolved.is_dir() else ""
    if not resolved.exists():
        failures.append(f"member {name}: member path is missing")
        entry["decision"] = "fail"
    elif not resolved.is_dir():
        failures.append(f"member {name}: member path is not a directory")
        entry["decision"] = "fail"
    elif not (resolved / "SKILL.md").is_file():
        failures.append(f"member {name}: member path is not a skill directory with SKILL.md")
        entry["decision"] = "fail"
    else:
        entry["decision"] = "pass"
        entry["skill_sha256"] = file_sha256(resolved / "SKILL.md")
        entry["skill_line_count"] = line_count(resolved / "SKILL.md")
    if member["status"] not in SUITE_MEMBER_STATUS_VALUES and not str(member["status"]).startswith("initial_"):
        failures.append(f"member {name}: unsupported member status {member['status']!r}")
        entry["decision"] = "fail"
    return entry


def extract_relationships(records: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    relationships: list[dict[str, Any]] = []
    for source, record in records:
        for index, item in enumerate(record.get("relationships", []) if isinstance(record.get("relationships"), list) else []):
            if not isinstance(item, dict):
                relationships.append({"source": source, "index": index, "raw": item})
                continue
            from_skill = item.get("from_skill") or item.get("from") or item.get("parent") or item.get("source")
            to_skill = item.get("to_skill") or item.get("to") or item.get("child") or item.get("target")
            relation_type = item.get("relationship_type") or item.get("relationship") or item.get("type") or "other"
            relationships.append(
                {
                    "source": source,
                    "index": index,
                    "from_skill": from_skill,
                    "to_skill": to_skill,
                    "relationship_type": relation_type,
                }
            )
        for index, item in enumerate(record.get("dependencies", []) if isinstance(record.get("dependencies"), list) else []):
            if not isinstance(item, dict):
                relationships.append({"source": source, "index": index, "raw": item})
                continue
            name = item.get("name") or item.get("dependency_name")
            if item.get("dependency_type") == "skill" or item.get("required") is True:
                relationships.append(
                    {
                        "source": source,
                        "index": index,
                        "from_skill": "suite",
                        "to_skill": name,
                        "relationship_type": "dependency",
                        "required": item.get("required"),
                    }
                )
    return relationships


def validate_suite_relationships(
    relationships: list[dict[str, Any]],
    member_names: set[str],
    failures: list[str],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for relation in relationships:
        finding = dict(relation)
        from_skill = relation.get("from_skill")
        to_skill = relation.get("to_skill")
        relation_type = relation.get("relationship_type")
        problems: list[str] = []
        if not isinstance(from_skill, str) or not from_skill:
            problems.append("missing from_skill")
        elif from_skill != "suite" and from_skill not in member_names:
            problems.append(f"unknown from_skill {from_skill!r}")
        if not isinstance(to_skill, str) or not to_skill:
            problems.append("missing to_skill")
        elif to_skill not in member_names:
            problems.append(f"unknown to_skill {to_skill!r}")
        if relation_type not in SUITE_RELATION_TYPES:
            problems.append(f"unsupported relationship_type {relation_type!r}")
        if from_skill == to_skill and relation_type not in {"other", "release_group"}:
            problems.append("relationship points to itself")
        if problems:
            for problem in problems:
                failures.append(f"relationship {relation.get('source')}[{relation.get('index')}]: {problem}")
            finding["decision"] = "fail"
            finding["problems"] = problems
        else:
            finding["decision"] = "pass"
        findings.append(finding)
    return findings


def current_timestamp_from_text(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def evidence_reference_from_value(value: Any, source: str, context: str) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    if isinstance(value, str) and looks_like_record_path(value):
        refs.append({"source": source, "context": context, "path": value})
    elif isinstance(value, dict):
        path = value.get("path") or value.get("source") or value.get("source_path") or value.get("evidence_source")
        if isinstance(path, str) and looks_like_record_path(path):
            refs.append(
                {
                    "source": source,
                    "context": context,
                    "path": path,
                    "sha256": value.get("sha256") or value.get("expected_sha256") or value.get("hash"),
                    "line_count": value.get("line_count") or value.get("expected_line_count"),
                    "checked_at": value.get("checked_at") or value.get("captured_at") or value.get("generated_at"),
                    "stale_after": value.get("stale_after") or value.get("expires_at"),
                }
            )
        for key, child in value.items():
            refs.extend(evidence_reference_from_value(child, source, f"{context}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            refs.extend(evidence_reference_from_value(child, source, f"{context}[{index}]"))
    return refs


def collect_evidence_references(records: list[tuple[str, dict[str, Any]]], members: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for source, record in records:
        for key in ("evidence", "shared_evidence_rules", "validation_layers"):
            refs.extend(evidence_reference_from_value(record.get(key), source, f"$.{key}"))
    for member in members:
        if member.get("evidence_source"):
            refs.append(
                {
                    "source": member["source"],
                    "context": f"member:{member['name']}.evidence_source",
                    "path": member["evidence_source"],
                }
            )
    return refs


def resolve_evidence_path(suite_root: Path, value: str) -> Path:
    normalized = value.replace("\\", "/")
    if normalized.startswith(".agents/") or normalized.startswith("references/") or normalized in ROOT_REFERENCE_NAMES:
        return repository_root() / normalized
    if normalized.startswith(".skillguard/"):
        return skill_root() / normalized
    return suite_root / normalized


def validate_evidence_references(
    refs: list[dict[str, Any]],
    suite_root: Path,
    max_age_days: int,
    failures: list[str],
    blockers: list[str],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    for ref in refs:
        path_text = ref.get("path", "")
        label = reference_label(path_text)
        finding = dict(ref)
        finding["path"] = label
        if not isinstance(path_text, str) or not path_text:
            failures.append(f"{ref.get('source')} {ref.get('context')}: evidence reference missing path")
            finding["decision"] = "fail"
            findings.append(finding)
            continue
        if Path(path_text).is_absolute():
            blockers.append(f"{label}: absolute evidence paths are not allowed")
            finding["decision"] = "block"
            findings.append(finding)
            continue
        resolved = resolve_evidence_path(suite_root, path_text).resolve()
        try:
            resolved.relative_to(repository_root().resolve())
        except ValueError:
            blockers.append(f"{label}: evidence path escapes repository boundary")
            finding["decision"] = "block"
            findings.append(finding)
            continue
        finding["resolved_path"] = public_relative_path(resolved)
        finding["exists"] = resolved.exists()
        finding["kind"] = "directory" if resolved.is_dir() else "file" if resolved.is_file() else "missing"
        if normalized_progress_ledger_path(path_text):
            failures.append(f"{label}: progress ledger is historical progress, not current child closure evidence")
            finding["decision"] = "fail"
        elif not resolved.is_file():
            failures.append(f"{label}: evidence path is missing or not a file")
            finding["decision"] = "fail"
        else:
            actual_hash = file_sha256(resolved)
            actual_line_count = line_count(resolved)
            finding["sha256"] = actual_hash
            finding["line_count"] = actual_line_count
            expected_hash = ref.get("sha256")
            expected_lines = ref.get("line_count")
            problems: list[str] = []
            if isinstance(expected_hash, str) and expected_hash and expected_hash.upper() != actual_hash:
                problems.append("sha256 mismatch")
            if isinstance(expected_lines, int) and expected_lines != actual_line_count:
                problems.append("line_count mismatch")
            checked_at = current_timestamp_from_text(ref.get("checked_at"))
            stale_after = current_timestamp_from_text(ref.get("stale_after"))
            if checked_at is not None and (now - checked_at).days > max_age_days:
                problems.append(f"checked_at older than {max_age_days} days")
            if stale_after is not None and now > stale_after:
                problems.append("stale_after timestamp has passed")
            if resolved.suffix.lower() == ".json":
                try:
                    nested = load_json(resolved)
                except ValueError:
                    nested = None
                if isinstance(nested, dict):
                    nested_checked_at = current_timestamp_from_text(nested.get("checked_at"))
                    if nested_checked_at is not None and (now - nested_checked_at).days > max_age_days:
                        problems.append(f"referenced evidence checked_at older than {max_age_days} days")
                    if nested.get("schema_version") == "skillguard.check_report.v1":
                        nested_evidence = nested.get("evidence")
                        if not isinstance(nested_evidence, list) or not nested_evidence:
                            problems.append("referenced check report declares no direct evidence entries")
                        elif any(isinstance(item, dict) and item.get("fresh") is False for item in nested_evidence):
                            problems.append("referenced check report contains explicitly stale evidence")
            if problems:
                for problem in problems:
                    failures.append(f"{label}: {problem}")
                finding["decision"] = "fail"
                finding["problems"] = problems
            else:
                finding["decision"] = "pass"
        findings.append(finding)
    return findings


def normalized_progress_ledger_path(path_text: str) -> bool:
    normalized = path_text.replace("\\", "/").lower()
    return normalized.endswith("skillguard_progress_ledger.jsonl") or "/progress" in normalized


def validate_child_closure(
    members: list[dict[str, Any]],
    member_path_findings: list[dict[str, Any]],
    evidence_findings: list[dict[str, Any]],
    failures: list[str],
) -> list[dict[str, Any]]:
    evidence_by_member: dict[str, list[dict[str, Any]]] = {}
    for finding in evidence_findings:
        context = str(finding.get("context", ""))
        if context.startswith("member:"):
            member_name = context.split(":", 1)[1].split(".", 1)[0]
            evidence_by_member.setdefault(member_name, []).append(finding)
    path_by_member = {finding.get("name"): finding for finding in member_path_findings}
    closure_findings: list[dict[str, Any]] = []
    for member in members:
        name = member["name"]
        status = str(member.get("status", "draft"))
        required = member.get("required", True)
        path_finding = path_by_member.get(name, {})
        evidence = evidence_by_member.get(name, [])
        current_evidence = [item for item in evidence if item.get("decision") == "pass"]
        finding = {
            "name": name,
            "required": required,
            "member_status": status,
            "member_path_decision": path_finding.get("decision", "missing"),
            "current_evidence_count": len(current_evidence),
            "uses_progress_ledger_as_current_closure_evidence": False,
        }
        if path_finding.get("decision") != "pass":
            finding["decision"] = "block" if path_finding.get("decision") == "block" else "fail"
        elif status in {"blocked", "block"}:
            failures.append(f"member {name}: blocked child cannot support suite closure")
            finding["decision"] = "fail"
        elif status in {"stale", "incomplete", "unsupported", "not_run", "needs-review"} and required:
            failures.append(f"member {name}: child status {status!r} does not support suite closure")
            finding["decision"] = "fail"
        elif status == "waived" and required:
            failures.append(f"member {name}: required child cannot be waived for suite closure")
            finding["decision"] = "fail"
        elif status in {"accepted", "checked", "pass"} and not current_evidence:
            failures.append(f"member {name}: accepted/checked child status requires current evidence_source")
            finding["decision"] = "fail"
        else:
            finding["decision"] = "pass"
        closure_findings.append(finding)
    return closure_findings


def scan_text_for_unsafe_claims(path: Path, failures: list[str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if not path.is_file():
        return findings
    text = path.read_text(encoding="utf-8")
    lower_text = text.lower()
    for claim_id, pattern in UNSAFE_CLAIM_RULES:
        for match in pattern.finditer(text):
            window = lower_text[max(0, match.start() - 180) : min(len(text), match.end() + 180)]
            safe_context = any(marker in window for marker in SAFE_UNSAFE_CLAIM_CONTEXT)
            finding = {
                "claim_id": claim_id,
                "path": public_relative_path(path),
                "line": text[: match.start()].count("\n") + 1,
                "safe_context": safe_context,
            }
            if not safe_context:
                failures.append(f"{public_relative_path(path)} line {finding['line']}: unsafe claim phrase {claim_id}")
                finding["decision"] = "fail"
            else:
                finding["decision"] = "pass"
            findings.append(finding)
    return findings


def scan_suite_files_for_unsafe_claims(paths: list[Path], failures: list[str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved in seen or not resolved.is_file():
            continue
        seen.add(resolved)
        findings.extend(scan_text_for_unsafe_claims(resolved, failures))
    return findings


def check_skill(argv: list[str]) -> int:
    parser = JsonArgumentParser(
        prog="skillguard.py check-skill",
        description="Check one target skill directory for static SkillGuard contract and control-record readiness.",
    )
    parser.add_argument("--target", default=".agents/skills/skillguard", help="Target skill directory under the repository root.")
    parser.add_argument(
        "--reference",
        action="append",
        default=[],
        help="Additional target-skill-relative reference to resolve inside the target boundary. Repeat as needed.",
    )
    parser.add_argument("--output", default="-", help="Output report path under the skill root, or '-' for stdout.")
    args = parser.parse_args(argv)

    target = ensure_under_root(args.target)
    target_relative = public_relative_path(target)
    payload = base_result("check-skill", target_relative)
    payload["claim_boundary"] = (
        "This static single-skill check covers SKILL.md metadata and sections, declared local references, target "
        ".skillguard control records, progress JSONL parsing, AI-judgment structure, evidence references, and conservative "
        "no-claim wording from files inspected during this invocation. It does not prove runtime checker execution, fixture "
        "coverage, CLI checks, tests, suite automation, package publication, code-contract validation, release readiness, "
        "or future AI behavior."
    )
    payload["residual_risk"] = [
        "This command is a static local check; semantic adequacy still needs reviewer judgment where the target contract requires it.",
        "Progress ledger entries are parsed and reported as historical records only, not as current closure evidence for this invocation.",
    ]

    failures: list[str] = []
    blockers: list[str] = []
    inspected_files: list[dict[str, Any]] = []
    declared_reference_entries: list[dict[str, Any]] = []
    control_reference_entries: list[dict[str, Any]] = []
    control_records: list[dict[str, Any]] = []
    progress_entries: list[dict[str, Any]] = []
    unsafe_claim_findings: list[dict[str, Any]] = []

    before_failures, before_blockers = len(failures), len(blockers)
    if not target.exists():
        blockers.append(f"target directory does not exist: {target_relative}")
    elif not target.is_dir():
        blockers.append(f"target is not a directory: {target_relative}")
    append_check(
        payload,
        "check-skill:target-directory",
        "Target directory",
        check_status(failures, blockers, before_failures, before_blockers),
        f"Resolved target as {target_relative}.",
    )
    if blockers:
        payload["decision"] = "block"
        payload["failures"] = failures
        payload["blockers"] = blockers
        return write_and_exit(payload, args.output)

    skill_md = target / "SKILL.md"
    before_failures, before_blockers = len(failures), len(blockers)
    skill_text = ""
    if not skill_md.is_file():
        blockers.append(f"SKILL.md missing under target: {target_relative}")
    else:
        skill_text = skill_md.read_text(encoding="utf-8")
        inspected_files.append(
            {
                "path": public_relative_path(skill_md),
                "kind": "markdown",
                "sha256": file_sha256(skill_md),
                "line_count": line_count(skill_md),
            }
        )
    append_check(
        payload,
        "check-skill:entrypoint-read",
        "SKILL.md readability",
        check_status(failures, blockers, before_failures, before_blockers),
        "Read the target skill entrypoint without rewriting it." if skill_text else "Could not read the target skill entrypoint.",
    )

    if skill_text:
        before_failures, before_blockers = len(failures), len(blockers)
        frontmatter, frontmatter_failures = parse_skill_frontmatter(skill_text)
        failures.extend(frontmatter_failures)
        if frontmatter.get("name") != target.name:
            failures.append("SKILL.md frontmatter name must match the target skill directory name")
        append_check(
            payload,
            "check-skill:frontmatter",
            "SKILL.md frontmatter",
            check_status(failures, blockers, before_failures, before_blockers),
            "Parsed scalar frontmatter and checked name/description fields.",
        )

        before_failures, before_blockers = len(failures), len(blockers)
        headings = {match.group(1).strip() for match in HEADING_RE.finditer(skill_text)}
        for section in REQUIRED_SKILL_SECTIONS:
            if section not in headings:
                failures.append(f"SKILL.md missing required section: {section}")
        lowered_skill = skill_text.lower()
        for field, variants in OUTPUT_REQUIREMENT_TERMS.items():
            if not any(variant.lower() in lowered_skill for variant in variants):
                failures.append(f"SKILL.md output requirements missing {field}")
        append_check(
            payload,
            "check-skill:required-sections",
            "Required SKILL.md sections",
            check_status(failures, blockers, before_failures, before_blockers),
            "Checked required operational body sections and output-field terms.",
        )

        before_failures, before_blockers = len(failures), len(blockers)
        for finding_id, pattern in PUBLIC_SAFETY_PATTERNS:
            if pattern.search(skill_text):
                failures.append(f"SKILL.md public-safety scan found {finding_id}")
        append_check(
            payload,
            "check-skill:public-safety",
            "SKILL.md public-safety scan",
            check_status(failures, blockers, before_failures, before_blockers),
            "Scanned SKILL.md for private local paths, runtime ids, and credential-like assignments.",
        )

        before_failures, before_blockers = len(failures), len(blockers)
        unsafe_claim_findings.extend(scan_text_for_unsafe_claims(skill_md, failures))
        append_check(
            payload,
            "check-skill:unsafe-claims",
            "SKILL.md unsafe claim scan",
            check_status(failures, blockers, before_failures, before_blockers),
            "Scanned SKILL.md for unsupported broad-claim phrases and allowed only conservative no-claim contexts.",
        )

        before_failures, before_blockers = len(failures), len(blockers)
        declared_references = extract_reference_tokens(skill_text)
        for reference in declared_references:
            declared_reference_entries.append(
                validate_reference(target, reference, failures, blockers, allow_project_boundary=True)
            )
        for reference in args.reference:
            declared_reference_entries.append(
                validate_reference(target, reference, failures, blockers, allow_project_boundary=False)
            )
        append_check(
            payload,
            "check-skill:declared-references",
            "Declared reference resolution",
            check_status(failures, blockers, before_failures, before_blockers),
            "Resolved SKILL.md declared references and any extra --reference values with explicit repository/target boundaries.",
        )

    control_root = target / ".skillguard"
    before_failures, before_blockers = len(failures), len(blockers)
    if not control_root.is_dir():
        failures.append(f"target control root missing: {public_relative_path(control_root)}")
    append_check(
        payload,
        "check-skill:control-root",
        "Target .skillguard root",
        check_status(failures, blockers, before_failures, before_blockers),
        "Checked that the target .skillguard control root is present.",
    )

    if control_root.is_dir():
        before_failures, before_blockers = len(failures), len(blockers)
        for file_name in CONTROL_JSON_RECORDS:
            path = control_root / file_name
            if not path.is_file():
                failures.append(f"required control record missing: {public_relative_path(path)}")
                continue
            record = inspect_control_json_file(
                path,
                target,
                control_root,
                failures,
                blockers,
                inspected_files,
                control_reference_entries,
            )
            if record is not None:
                control_records.append(
                    {
                        "path": public_relative_path(path),
                        "schema_version": record.get("schema_version"),
                        "target_type": record.get("target_type"),
                        "status": record.get("status"),
                    }
                )
        for directory_name in CONTROL_RECORD_DIRS:
            directory = control_root / directory_name
            if not directory.is_dir():
                failures.append(f"required control directory missing: {public_relative_path(directory)}")
                continue
            json_files = sorted(directory.glob("*.json"))
            if not json_files:
                failures.append(f"required control directory has no JSON records: {public_relative_path(directory)}")
                continue
            for path in json_files:
                record = inspect_control_json_file(
                    path,
                    target,
                    control_root,
                    failures,
                    blockers,
                    inspected_files,
                    control_reference_entries,
                )
                if record is not None:
                    control_records.append(
                        {
                            "path": public_relative_path(path),
                            "schema_version": record.get("schema_version"),
                            "target_type": record.get("target_type"),
                            "status": record.get("status"),
                        }
                    )
        append_check(
            payload,
            "check-skill:control-json-records",
            "Control JSON records",
            check_status(failures, blockers, before_failures, before_blockers),
            "Parsed required root records and present ai_judgments/evidence/reports records, then checked common fields and references.",
        )

        before_failures, before_blockers = len(failures), len(blockers)
        ledger_path = control_root / "skillguard_progress_ledger.jsonl"
        if not ledger_path.is_file():
            failures.append(f"required progress ledger missing: {public_relative_path(ledger_path)}")
        else:
            try:
                ledger_records = load_jsonl(ledger_path)
            except ValueError as exc:
                failures.append(f"progress ledger invalid JSONL: {exc}")
                ledger_records = []
            inspected_files.append(
                {
                    "path": public_relative_path(ledger_path),
                    "kind": "jsonl",
                    "sha256": file_sha256(ledger_path),
                    "line_count": line_count(ledger_path),
                }
            )
            for index, record in enumerate(ledger_records, 1):
                line_label = f"{public_relative_path(ledger_path)} line {index}"
                if not isinstance(record, dict):
                    failures.append(f"{line_label}: ledger line must be a JSON object")
                    continue
                for field in ("event_id", "event_time"):
                    if not record.get(field):
                        failures.append(f"{line_label}: missing {field}")
                control_reference_entries.extend(
                    validate_common_record(record, line_label, target, control_root, failures, blockers)
                )
                progress_entries.append(
                    {
                        "line": index,
                        "event_id": record.get("event_id"),
                        "status": record.get("status"),
                        "event_time": record.get("event_time"),
                    }
                )
        append_check(
            payload,
            "check-skill:progress-ledger",
            "Progress ledger JSONL",
            check_status(failures, blockers, before_failures, before_blockers),
            "Parsed progress ledger line by line and reported ledger entries as historical progress, not current closure evidence.",
        )

    payload["files_inspected"] = inspected_files
    payload["declared_references"] = declared_reference_entries
    payload["control_records"] = control_records
    payload["control_reference_checks"] = control_reference_entries
    payload["progress_ledger_entries"] = progress_entries
    payload["unsafe_claim_findings"] = unsafe_claim_findings
    payload["current_closure_evidence"] = {
        "uses_progress_ledger_as_current_closure_evidence": False,
        "summary": "Ledger entries are parsed for structure and context only; this command bases its decision on fresh inspection in this invocation.",
    }
    payload["evidence"] = [
        {
            "evidence_id": "skill-entrypoint-static-read",
            "kind": "file_inspection",
            "fresh": True,
            "summary": f"Read SKILL.md for {target_relative} when present and checked frontmatter, sections, references, and public-safety patterns.",
            "source_path": f"{target_relative}/SKILL.md",
        },
        {
            "evidence_id": "control-record-parse",
            "kind": "parser_output",
            "fresh": True,
            "summary": f"Parsed {len(control_records)} target .skillguard JSON records with Python json helpers.",
            "source_path": f"{target_relative}/.skillguard",
        },
        {
            "evidence_id": "progress-ledger-jsonl-parse",
            "kind": "parser_output",
            "fresh": True,
            "summary": f"Parsed {len(progress_entries)} progress ledger entries line by line without treating them as current closure evidence.",
            "source_path": f"{target_relative}/.skillguard/skillguard_progress_ledger.jsonl",
        },
    ]
    payload["failures"] = failures
    payload["blockers"] = blockers
    payload["decision"] = "block" if blockers else "fail" if failures else "pass"
    return write_and_exit(payload, args.output)


def check_suite(argv: list[str]) -> int:
    parser = JsonArgumentParser(
        prog="skillguard.py check-suite",
        description="Check a suite root, suite records, member skills, evidence freshness, and unsafe suite claims.",
    )
    parser.add_argument("--suite-root", default=".agents/skills/skillguard/.skillguard/suite", help="Suite control root under the repository root.")
    parser.add_argument("--suite-map", help="Suite map JSON file under the repository root.")
    parser.add_argument("--suite-contract", help="Suite contract JSON file under the repository root.")
    parser.add_argument("--member-root", default=".agents/skills", help="Allowed suite member root under the repository root.")
    parser.add_argument(
        "--member",
        action="append",
        default=[],
        help="Additional member as name=path or path. Member paths must stay under --member-root.",
    )
    parser.add_argument(
        "--scan",
        action="append",
        default=[],
        help="Additional suite-facing text or JSON file to scan for unsafe claims.",
    )
    parser.add_argument("--max-evidence-age-days", type=int, default=30, help="Maximum age for evidence timestamps when present.")
    parser.add_argument("--output", default="-", help="Output report path under the skill root, or '-' for stdout.")
    args = parser.parse_args(argv)

    suite_root = ensure_under_root(args.suite_root)
    suite_member_root = ensure_under_root(args.member_root)
    suite_relative = public_relative_path(suite_root)
    payload = base_result("check-suite", suite_relative)
    payload["claim_boundary"] = (
        "This static suite check covers only the suite records, member paths, relationship declarations, child closure "
        "evidence references, stale-evidence indicators, and unsafe-claim phrases loaded during this invocation. It does "
        "not prove runtime checker execution, fixture coverage, CLI checks, tests, suite automation, package publication, "
        "code-contract validation, release readiness, or future AI behavior."
    )
    payload["residual_risk"] = [
        "Unsafe-claim scanning uses a declared phrase set and may miss paraphrased overclaims.",
        "This command validates current file structure and evidence references; it does not run child skill workflows or suite automation.",
    ]

    failures: list[str] = []
    blockers: list[str] = []
    inspected_files: list[dict[str, Any]] = []
    records: list[tuple[str, dict[str, Any]]] = []
    loaded_record_paths: list[Path] = []

    before_failures, before_blockers = len(failures), len(blockers)
    if not suite_root.exists():
        failures.append(f"suite root missing: {suite_relative}")
    elif not suite_root.is_dir():
        blockers.append(f"suite root is not a directory: {suite_relative}")
    if not suite_member_root.is_dir():
        blockers.append(f"suite member root is not a directory: {public_relative_path(suite_member_root)}")
    append_check(
        payload,
        "check-suite:suite-root",
        "Suite and member roots",
        check_status(failures, blockers, before_failures, before_blockers),
        "Resolved suite root and bounded suite member root.",
    )

    before_failures, before_blockers = len(failures), len(blockers)
    suite_map_path = find_suite_record(suite_root, args.suite_map, "map")
    suite_contract_path = find_suite_record(suite_root, args.suite_contract, "contract")
    suite_map_record: dict[str, Any] | None = None
    suite_contract_record: dict[str, Any] | None = None
    if suite_map_path is None:
        failures.append("suite map record is missing")
    else:
        suite_map_data = read_json_record(suite_map_path, failures, inspected_files)
        loaded_record_paths.append(suite_map_path)
        if isinstance(suite_map_data, dict):
            suite_map_record = suite_map_data
            records.append((public_relative_path(suite_map_path), suite_map_data))
            failures.extend(validate_schema_subset(suite_map_data, load_json(schema_path("skillguard_suite_map.schema.json"))))
    if suite_contract_path is None:
        failures.append("suite contract record is missing")
    else:
        suite_contract_data = read_json_record(suite_contract_path, failures, inspected_files)
        loaded_record_paths.append(suite_contract_path)
        if isinstance(suite_contract_data, dict):
            suite_contract_record = suite_contract_data
            records.append((public_relative_path(suite_contract_path), suite_contract_data))
            failures.extend(validate_schema_subset(suite_contract_data, load_json(schema_path("skillguard_suite_contract.schema.json"))))
    append_check(
        payload,
        "check-suite:suite-records",
        "Suite map and contract records",
        check_status(failures, blockers, before_failures, before_blockers),
        "Loaded suite map and suite contract JSON records when available and checked their declared schema subsets.",
    )

    before_failures, before_blockers = len(failures), len(blockers)
    members = collect_suite_members(records, args.member)
    member_path_findings: list[dict[str, Any]] = []
    seen_member_names: set[str] = set()
    seen_member_paths: set[str] = set()
    for member in members:
        name = member["name"]
        normalized_path = member["path"].replace("\\", "/")
        if name in seen_member_names:
            failures.append(f"duplicate suite member name: {name}")
        if normalized_path in seen_member_paths:
            failures.append(f"duplicate suite member path: {member['path']}")
        seen_member_names.add(name)
        seen_member_paths.add(normalized_path)
        member_path_findings.append(validate_suite_member_path(member, suite_member_root, failures, blockers))
    if not members:
        failures.append("suite has no declared members")
    append_check(
        payload,
        "check-suite:members",
        "Suite member inventory",
        check_status(failures, blockers, before_failures, before_blockers),
        "Validated member list uniqueness, path confinement, and SKILL.md entrypoints.",
    )

    before_failures, before_blockers = len(failures), len(blockers)
    relationships = extract_relationships(records)
    relationship_findings = validate_suite_relationships(relationships, seen_member_names, failures)
    append_check(
        payload,
        "check-suite:relationships",
        "Suite relationships and dependencies",
        check_status(failures, blockers, before_failures, before_blockers),
        "Checked relationship and skill-dependency endpoints against declared members.",
    )

    before_failures, before_blockers = len(failures), len(blockers)
    evidence_refs = collect_evidence_references(records, members)
    evidence_findings = validate_evidence_references(evidence_refs, suite_root, args.max_evidence_age_days, failures, blockers)
    append_check(
        payload,
        "check-suite:evidence",
        "Suite evidence references",
        check_status(failures, blockers, before_failures, before_blockers),
        "Resolved suite and child evidence references, checked missing paths, stale timestamps, and hash or line-count mismatches when present.",
    )

    before_failures, before_blockers = len(failures), len(blockers)
    child_closure_findings = validate_child_closure(members, member_path_findings, evidence_findings, failures)
    append_check(
        payload,
        "check-suite:child-closure",
        "Child closure rollup",
        check_status(failures, blockers, before_failures, before_blockers),
        "Checked that accepted, checked, or passing children have current evidence and that historical progress is not promoted to closure proof.",
    )

    before_failures, before_blockers = len(failures), len(blockers)
    scan_paths: list[Path] = []
    scan_paths.extend(loaded_record_paths)
    for finding in member_path_findings:
        entrypoint = finding.get("skill_entrypoint")
        if isinstance(entrypoint, str) and entrypoint:
            scan_paths.append(repository_root() / entrypoint)
    for finding in evidence_findings:
        resolved_path = finding.get("resolved_path")
        if isinstance(resolved_path, str) and resolved_path.endswith((".json", ".md", ".txt")):
            scan_paths.append(repository_root() / resolved_path)
    for scan_arg in args.scan:
        scan_paths.append(ensure_under_root(scan_arg))
    unsafe_claim_findings = scan_suite_files_for_unsafe_claims(scan_paths, failures)
    append_check(
        payload,
        "check-suite:unsafe-claims",
        "Unsafe suite claim scan",
        check_status(failures, blockers, before_failures, before_blockers),
        "Scanned suite-facing records, member entrypoints, evidence files, and explicit --scan files for declared unsafe claim phrases.",
    )

    before_failures, before_blockers = len(failures), len(blockers)
    if suite_map_record is not None:
        missing_terms = claim_boundary_missing_terms(suite_map_record.get("claim_boundary"))
        for term in missing_terms:
            failures.append(f"suite map claim_boundary missing conservative term {term!r}")
    if suite_contract_record is not None:
        missing_terms = claim_boundary_missing_terms(suite_contract_record.get("claim_boundary"))
        for term in missing_terms:
            failures.append(f"suite contract claim_boundary missing conservative term {term!r}")
    append_check(
        payload,
        "check-suite:claim-boundaries",
        "Suite claim boundaries",
        check_status(failures, blockers, before_failures, before_blockers),
        "Checked suite map and suite contract claim boundaries for conservative no-claim categories.",
    )

    payload["suite_records"] = [
        {
            "path": public_relative_path(path),
            "sha256": file_sha256(path) if path.is_file() else "",
            "line_count": line_count(path) if path.is_file() else 0,
        }
        for path in loaded_record_paths
    ]
    payload["files_inspected"] = inspected_files
    payload["members"] = member_path_findings
    payload["relationships"] = relationship_findings
    payload["evidence_references"] = evidence_findings
    payload["child_closure"] = child_closure_findings
    payload["unsafe_claim_phrase_set"] = [claim_id for claim_id, _pattern in UNSAFE_CLAIM_RULES]
    payload["unsafe_claim_findings"] = unsafe_claim_findings
    payload["current_closure_evidence"] = {
        "uses_progress_ledger_as_current_closure_evidence": False,
        "summary": "Progress ledger references are treated as historical progress and cannot satisfy suite or child closure evidence.",
    }
    payload["evidence"] = [
        {
            "evidence_id": "suite-record-parse",
            "kind": "parser_output",
            "fresh": True,
            "summary": f"Loaded {len(records)} suite records and inspected {len(inspected_files)} JSON files.",
            "source_path": suite_relative,
        },
        {
            "evidence_id": "suite-member-path-check",
            "kind": "filesystem_check",
            "fresh": True,
            "summary": f"Checked {len(member_path_findings)} suite member declarations under {public_relative_path(suite_member_root)}.",
            "source_path": public_relative_path(suite_member_root),
        },
        {
            "evidence_id": "suite-evidence-freshness-check",
            "kind": "filesystem_check",
            "fresh": True,
            "summary": f"Checked {len(evidence_findings)} suite evidence references for existence, stale markers, hashes, and line counts where declared.",
            "source_path": suite_relative,
        },
        {
            "evidence_id": "suite-unsafe-claim-scan",
            "kind": "text_scan",
            "fresh": True,
            "summary": f"Scanned {len(scan_paths)} suite-facing files against {len(UNSAFE_CLAIM_RULES)} unsafe claim phrase rules.",
            "source_path": suite_relative,
        },
    ]
    payload["failures"] = failures
    payload["blockers"] = blockers
    payload["decision"] = "block" if blockers else "fail" if failures else "pass"
    return write_and_exit(payload, args.output)


def inventory(argv: list[str]) -> int:
    parser = JsonArgumentParser(prog="skillguard.py inventory", description="Build a local SkillGuard inventory record.")
    parser.add_argument("--target", default=".", help="Target path under the repository root.")
    parser.add_argument("--output", default="-", help="Output record path under the skill root, or '-' for stdout.")
    args = parser.parse_args(argv)
    repo = repository_root()
    target = ensure_under_root(args.target)
    target_relative = public_relative_path(target)
    expected = [
        ("README.md", "file", "readme", True),
        ("AGENTS.md", "file", "metadata", True),
        ("LICENSE", "file", "metadata", True),
        ("VERSION", "file", "metadata", True),
        ("pyproject.toml", "file", "metadata", True),
        ("references", "directory", "reference", True),
        (".agents/skills/skillguard/SKILL.md", "file", "skill_contract", True),
        (".agents/skills/skillguard/assets/schemas", "directory", "schema", True),
        (".agents/skills/skillguard/assets/templates", "directory", "schema", True),
        (".agents/skills/skillguard/.skillguard", "directory", "report", True),
        (".agents/skills/skillguard/scripts/skillguard.py", "file", "script", True),
        (".agents/skills/skillguard/scripts/checker_engine.py", "file", "script", True),
        (".agents/skills/skillguard/scripts/skillguard_utils.py", "file", "script", True),
        (".agents/skills/skillguard/fixtures", "missing", "fixture", False),
        ("tests", "missing", "test", False),
        ("examples", "missing", "other", False),
    ]
    expected.extend(marker_state_entries(target))
    discovered: list[dict[str, Any]] = []
    failures: list[str] = []
    for relative, expected_kind, role, required in expected:
        path = repo / relative
        exists = path.exists()
        if path.is_file():
            kind = "file"
        elif path.is_dir():
            kind = "directory"
        else:
            kind = "missing"
        if required and not exists:
            failures.append(f"required path missing: {relative}")
        item: dict[str, Any] = {
            "path": relative,
            "kind": kind,
            "role": role,
            "required": required,
            "exists": exists,
        }
        if path.is_file():
            item["sha256"] = file_sha256(path)
            item["line_count"] = line_count(path)
        discovered.append(item)
    record = {
        "schema_version": "skillguard.inventory.v1",
        "target_path": target_relative,
        "target_type": "skill_repository",
        "status": "checked" if not failures else "fail",
        "discovered_files": discovered,
        "referenced_paths": [item[0] for item in expected],
        "declared_commands": list(COMMANDS),
        "maintained_records": [
            ".agents/skills/skillguard/.skillguard/skillguard_profile.json",
            ".agents/skills/skillguard/.skillguard/skillguard_skill_contract.json",
            ".agents/skills/skillguard/.skillguard/skillguard_manifest.json",
        ],
        "evidence": [
            {
                "evidence_id": "inventory-file-listing",
                "kind": "file_listing",
                "summary": "Inventory generated from current repository paths with the Python standard library.",
                "fresh": True,
            }
        ],
        "failures": failures,
        "blockers": [],
        "skipped_checks": [
            "Inventory is read-only and does not initialize missing paths or marker records.",
            "Fixture execution, tests, suite automation, package publication, and code-contract validation are outside this inventory command."
        ],
        "residual_risk": [
            "The inventory records path presence and file hashes only; it does not perform semantic AI judgment."
        ],
        "claim_boundary": (
            "This inventory records current local files and declared local commands. It does not prove fixture coverage, "
            "tests, suite automation, package publication, code-contract validation, release readiness, or future AI behavior."
        ),
    }
    schema = load_json(schema_path("skillguard_inventory.schema.json"))
    schema_failures = validate_schema_subset(record, schema)
    if schema_failures:
        record["status"] = "fail"
        record["failures"].extend(schema_failures)
    write_report(record, args.output, skill_root())
    return 0 if not record["failures"] else 1


def init_target(argv: list[str]) -> int:
    parser = JsonArgumentParser(prog="skillguard.py init-target", description="Create missing target SkillGuard structure.")
    parser.add_argument("--target", default=".", help="Existing target directory under the repository root.")
    parser.add_argument("--output", default="-", help="Output report path under the skill root, or '-' for stdout.")
    args = parser.parse_args(argv)
    target = ensure_under_root(args.target)
    require_directory(target, "init-target")
    control_root = control_root_for(target)
    created, existing, skipped = create_missing_directories(
        [
            control_root,
            control_root / "evidence",
            control_root / "ai_judgments",
            control_root / "reports",
            control_root / "markers",
        ]
    )
    payload = base_result("init-target", public_relative_path(target))
    payload["decision"] = "pass" if not skipped else "block"
    payload["created_paths"] = created
    payload["existing_paths"] = existing
    payload["skipped_paths"] = skipped
    payload["checks"] = [
        {
            "check_id": "init-target:create-only",
            "name": "Create-only target initialization",
            "required": True,
            "status": "pass" if not skipped else "block",
            "summary": "Created only missing target .skillguard directories and preserved existing paths.",
        }
    ]
    payload["evidence"] = [
        {
            "evidence_id": "init-target-paths",
            "kind": "command_output",
            "fresh": True,
            "summary": f"created={len(created)} existing={len(existing)} skipped={len(skipped)}",
        }
    ]
    payload["blockers"] = skipped
    return write_and_exit(payload, args.output)


def init_suite(argv: list[str]) -> int:
    parser = JsonArgumentParser(prog="skillguard.py init-suite", description="Create missing suite-level SkillGuard structure.")
    parser.add_argument("--target", default=".", help="Existing suite root directory under the repository root.")
    parser.add_argument("--output", default="-", help="Output report path under the skill root, or '-' for stdout.")
    args = parser.parse_args(argv)
    target = ensure_under_root(args.target)
    require_directory(target, "init-suite")
    suite_root = suite_root_for(target)
    created, existing, skipped = create_missing_directories(
        [
            control_root_for(target),
            suite_root,
            suite_root / "members",
            suite_root / "reports",
            suite_root / "markers",
        ]
    )
    payload = base_result("init-suite", public_relative_path(target))
    payload["decision"] = "pass" if not skipped else "block"
    payload["created_paths"] = created
    payload["existing_paths"] = existing
    payload["skipped_paths"] = skipped
    payload["checks"] = [
        {
            "check_id": "init-suite:create-only",
            "name": "Create-only suite initialization",
            "required": True,
            "status": "pass" if not skipped else "block",
            "summary": "Created only missing suite-level .skillguard directories and preserved existing paths.",
        }
    ]
    payload["evidence"] = [
        {
            "evidence_id": "init-suite-paths",
            "kind": "command_output",
            "fresh": True,
            "summary": f"created={len(created)} existing={len(existing)} skipped={len(skipped)}",
        }
    ]
    payload["blockers"] = skipped
    return write_and_exit(payload, args.output)


def mark(argv: list[str]) -> int:
    parser = JsonArgumentParser(prog="skillguard.py mark", description="Create or update one SkillGuard marker record.")
    parser.add_argument("--target", default=".", help="Existing target or suite root directory under the repository root.")
    parser.add_argument("--scope", choices=("target", "suite"), default="target", help="Marker scope.")
    parser.add_argument("--marker", required=True, help="Marker identifier.")
    parser.add_argument("--status", choices=MARKER_STATUSES, default="checked", help="Marker status.")
    parser.add_argument("--summary", required=True, help="Public-safe marker summary.")
    parser.add_argument("--output", default="-", help="Output report path under the skill root, or '-' for stdout.")
    args = parser.parse_args(argv)
    target = ensure_under_root(args.target)
    require_directory(target, "mark")
    path = marker_path(target, args.scope, args.marker)
    marker_dir = path.parent
    created, existing, skipped = create_missing_directories([marker_dir])
    if skipped:
        payload = base_result("mark", public_relative_path(target))
        payload["decision"] = "block"
        payload["blockers"] = skipped
        payload["created_paths"] = created
        payload["existing_paths"] = existing
        payload["skipped_paths"] = skipped
        return write_and_exit(payload, args.output)

    desired = {
        "schema_version": "skillguard.marker.v1",
        "target_path": public_relative_path(target),
        "scope": args.scope,
        "marker": args.marker,
        "status": args.status,
        "summary": args.summary,
        "checker_version": CHECKER_VERSION,
        "updated_at": utc_timestamp(),
        "claim_boundary": (
            "This marker records one local SkillGuard marker state. It does not prove fixture coverage, tests, "
            "suite automation, package publication, code-contract validation, release readiness, or future AI behavior."
        ),
    }
    action = "created"
    if path.exists():
        if not path.is_file():
            raise SkillGuardCliError("mark", f"marker path exists but is not a file: {public_relative_path(path)}", "validation_error")
        existing_record = load_json(path)
        if not isinstance(existing_record, dict):
            raise SkillGuardCliError("mark", f"existing marker is not a JSON object: {public_relative_path(path)}", "validation_error")
        if marker_semantic_payload(existing_record) == marker_semantic_payload(desired):
            desired = existing_record
            action = "already_present"
        else:
            action = "updated"
    if action != "already_present":
        dump_json(desired, path)

    payload = base_result("mark", public_relative_path(target))
    payload["decision"] = "pass"
    payload["marker_path"] = public_relative_path(path)
    payload["marker_action"] = action
    payload["created_paths"] = created
    payload["existing_paths"] = existing
    payload["skipped_paths"] = [] if action != "already_present" else [f"{public_relative_path(path)}: already present"]
    payload["checks"] = [
        {
            "check_id": "mark:single-marker",
            "name": "Single marker mutation",
            "required": True,
            "status": "pass",
            "summary": f"Marker {args.marker} for {args.scope} scope was {action}.",
        }
    ]
    payload["evidence"] = [
        {
            "evidence_id": "marker-record",
            "kind": "command_output",
            "fresh": True,
            "summary": f"{action}: {public_relative_path(path)}",
            "source_path": public_relative_path(path),
        }
    ]
    return write_and_exit(payload, args.output)


def write_report_command(argv: list[str]) -> int:
    args = parse_input_output("write-report", argv, "Load a JSON report and write it as stable formatted JSON.")
    input_path = ensure_under_root(args.input)
    payload = load_json(input_path)
    write_report(payload, args.output, skill_root())
    return 0


def commands(argv: list[str]) -> int:
    parser = JsonArgumentParser(prog="skillguard.py commands", description="List SkillGuard CLI commands.")
    parser.add_argument("--output", default="-", help="Output path under the skill root, or '-' for stdout.")
    args = parser.parse_args(argv)
    payload = base_result("commands")
    payload["decision"] = "pass"
    payload["commands"] = [
        {
            "name": name,
            "dispatch_function": f"checker_engine.{handler.__name__}",
            "summary": COMMAND_SUMMARIES[name],
        }
        for name, handler in COMMANDS.items()
    ]
    payload["checks"] = [
        {
            "check_id": "commands:dispatch-table",
            "name": "Dispatch table enumeration",
            "required": True,
            "status": "pass",
            "summary": "Every public command is mapped to a checker-engine function.",
        }
    ]
    return write_and_exit(payload, args.output)


def check_skill_contract(argv: list[str]) -> int:
    return check_json_record("check-skill-contract", argv, "skillguard_skill_contract.schema.json")


def check_suite_map(argv: list[str]) -> int:
    return check_json_record("check-suite-map", argv, "skillguard_suite_map.schema.json")


def check_suite_contract(argv: list[str]) -> int:
    return check_json_record("check-suite-contract", argv, "skillguard_suite_contract.schema.json")


def check_fixture_manifest(argv: list[str]) -> int:
    return check_json_record("check-fixture-manifest", argv, "skillguard_fixture_manifest.schema.json")


def check_ai_judgment(argv: list[str]) -> int:
    return check_json_record("check-ai-judgment", argv, "skillguard_ai_judgment.schema.json")


def check_report(argv: list[str]) -> int:
    return check_json_record("check-report", argv, "skillguard_check_report.schema.json")


def check_workflow_report(argv: list[str]) -> int:
    return check_json_record("check-workflow-report", argv, "skillguard_workflow_report.schema.json")


def normalize_expected_decision(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    lowered = value.strip().lower()
    if lowered in FIXTURE_EXPECTED_DECISIONS:
        return lowered
    for decision in ("pass", "fail", "block"):
        if decision in lowered:
            return decision
    return ""


def fixture_case_result(
    fixture_id: str,
    fixture_path: Path | None,
    expected_decision: str,
    observed_decision: str,
    case_class: str,
    problems: list[str],
    target_command: str = "",
) -> dict[str, Any]:
    case_status = "pass" if expected_decision == observed_decision else "fail"
    result: dict[str, Any] = {
        "fixture_id": fixture_id,
        "fixture_path": public_relative_path(fixture_path) if fixture_path is not None else "",
        "target_command": target_command,
        "expected_decision": expected_decision,
        "observed_decision": observed_decision,
        "case_class": case_class,
        "case_status": case_status,
        "problems": problems,
    }
    if fixture_path is not None and fixture_path.is_file():
        result["sha256"] = file_sha256(fixture_path)
        result["line_count"] = line_count(fixture_path)
    return result


def fixture_path_argument(fixture_path: Path, value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("fixture path argument must be a non-empty string")
    return public_relative_path(resolve_repository_reference(value, fixture_path.parent))


def fixture_string_list(value: Any) -> list[str]:
    if isinstance(value, str) and value:
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if isinstance(item, (str, int, float))]
    return []


def build_runtime_fixture_argv(fixture_path: Path, case_data: dict[str, Any], target_command: str) -> list[str]:
    explicit_arguments = case_data.get("arguments")
    if isinstance(explicit_arguments, list):
        return [str(item) for item in explicit_arguments if isinstance(item, (str, int, float))]

    if target_command == "check-skill":
        target_path_text = case_data.get("target_path") or case_data.get("skill_path")
        if not isinstance(target_path_text, str) or not target_path_text:
            raise ValueError("check-skill fixture must provide target_path")
        argv = ["--target", fixture_path_argument(fixture_path, target_path_text)]
        for reference in fixture_string_list(case_data.get("references") or case_data.get("reference")):
            argv.extend(["--reference", reference])
        return argv

    if target_command == "check-suite":
        argv: list[str] = []
        for field_name, flag in (
            ("suite_root", "--suite-root"),
            ("suite_map", "--suite-map"),
            ("suite_contract", "--suite-contract"),
            ("member_root", "--member-root"),
        ):
            value = case_data.get(field_name)
            if isinstance(value, str) and value:
                argv.extend([flag, fixture_path_argument(fixture_path, value)])
        for member in fixture_string_list(case_data.get("members") or case_data.get("member")):
            argv.extend(["--member", member])
        for scan in fixture_string_list(case_data.get("scans") or case_data.get("scan")):
            argv.extend(["--scan", fixture_path_argument(fixture_path, scan)])
        if isinstance(case_data.get("max_evidence_age_days"), int):
            argv.extend(["--max-evidence-age-days", str(case_data["max_evidence_age_days"])])
        return argv

    if target_command == "self-check":
        argv = []
        target_path_text = case_data.get("target_path") or case_data.get("target")
        if isinstance(target_path_text, str) and target_path_text:
            argv.extend(["--target", fixture_path_argument(fixture_path, target_path_text)])
        policy_root = case_data.get("policy_root")
        if isinstance(policy_root, str) and policy_root:
            argv.extend(["--policy-root", fixture_path_argument(fixture_path, policy_root)])
        return argv

    raise ValueError(f"unsupported runtime fixture command {target_command!r}")


def evaluate_runtime_fixture_case(
    fixture_path: Path,
    case_data: dict[str, Any],
    fixture_id: str,
    expected_decision: str,
    failures: list[str],
    blockers: list[str],
) -> dict[str, Any]:
    target_command = str(case_data.get("target_command") or case_data.get("check_command") or case_data.get("command") or "")
    if target_command not in FIXTURE_TARGET_RUNTIME_COMMANDS:
        target_command = "check-skill"
    try:
        argv = build_runtime_fixture_argv(fixture_path, case_data, target_command)
    except ValueError as exc:
        observed = "block"
        result = fixture_case_result(
            fixture_id,
            fixture_path,
            expected_decision,
            observed,
            "blocker_condition",
            [f"invalid fixture command arguments: {exc}"],
            target_command,
        )
        blockers.append(f"fixture {fixture_id}: fixture command arguments are invalid")
        return result

    handler_map = {
        "check-skill": check_skill,
        "check-suite": check_suite,
        "self-check": self_check,
    }
    handler = handler_map[target_command]

    stream = io.StringIO()
    try:
        with contextlib.redirect_stdout(stream):
            exit_code = handler(argv)
        report = json.loads(stream.getvalue())
    except Exception as exc:
        observed = "block"
        result = fixture_case_result(
            fixture_id,
            fixture_path,
            expected_decision,
            observed,
            "blocker_condition",
            [f"{target_command} fixture execution failed: {exc}"],
            target_command,
        )
        if expected_decision != observed:
            failures.append(f"fixture {fixture_id}: {target_command} execution did not match expected decision {expected_decision}")
        return result

    observed = str(report.get("decision") or ("pass" if exit_code == 0 else "fail")).strip().lower()
    if observed not in FIXTURE_EXPECTED_DECISIONS:
        observed = "block"
    observed_failures = [str(item) for item in report.get("failures", []) if isinstance(item, str)]
    observed_blockers = [str(item) for item in report.get("blockers", []) if isinstance(item, str)]
    problems = observed_failures + [f"blocker: {item}" for item in observed_blockers]
    case_class = "expected_fail" if observed == "fail" else "expected_pass" if observed == "pass" else "blocker_condition"
    result = fixture_case_result(fixture_id, fixture_path, expected_decision, observed, case_class, problems, target_command)
    result["command_arguments"] = argv
    result["target_path"] = str(report.get("target_path") or "")
    result["command_exit_code"] = exit_code
    result["observed_failure_count"] = len(observed_failures)
    result["observed_blocker_count"] = len(observed_blockers)
    result["observed_failures"] = observed_failures[:10]
    result["observed_blockers"] = observed_blockers[:10]
    result["observed_checks"] = [
        {
            "check_id": check.get("check_id"),
            "status": check.get("status"),
        }
        for check in report.get("checks", [])
        if isinstance(check, dict)
    ]
    if expected_decision != observed:
        failures.append(f"fixture {fixture_id}: expected {expected_decision} but observed {observed}")
    return result


def evaluate_fixture_case(
    fixture_path: Path,
    manifest_fixture: dict[str, Any] | None,
    failures: list[str],
    blockers: list[str],
) -> dict[str, Any]:
    manifest_fixture = manifest_fixture or {}
    fixture_id = str(manifest_fixture.get("fixture_id") or fixture_path.stem)
    expected_decision = normalize_expected_decision(manifest_fixture.get("expected_decision"))
    if not fixture_path.is_file():
        observed = "block"
        result = fixture_case_result(fixture_id, fixture_path, expected_decision, observed, "blocker_condition", ["fixture file is missing"])
        if expected_decision != observed:
            failures.append(f"fixture {fixture_id}: expected {expected_decision or 'unknown'} but observed block for missing fixture file")
        return result
    try:
        case_data = load_json(fixture_path)
    except ValueError as exc:
        observed = "block"
        result = fixture_case_result(fixture_id, fixture_path, expected_decision, observed, "invalid_fixture_input", [f"invalid fixture JSON: {exc}"])
        if expected_decision != observed:
            failures.append(f"fixture {fixture_id}: invalid fixture JSON did not match expected decision {expected_decision or 'unknown'}")
        return result
    if not isinstance(case_data, dict):
        observed = "block"
        result = fixture_case_result(fixture_id, fixture_path, expected_decision, observed, "invalid_fixture_input", ["fixture case must be a JSON object"])
        if expected_decision != observed:
            failures.append(f"fixture {fixture_id}: non-object fixture did not match expected decision {expected_decision or 'unknown'}")
        return result

    fixture_id = str(case_data.get("fixture_id") or fixture_id)
    expected_decision = expected_decision or normalize_expected_decision(case_data.get("expected_decision"))
    target_command = str(case_data.get("target_command") or case_data.get("check_command") or case_data.get("command") or "")
    if expected_decision not in FIXTURE_EXPECTED_DECISIONS:
        observed = "block"
        result = fixture_case_result(fixture_id, fixture_path, expected_decision, observed, "invalid_fixture_input", ["expected_decision must be pass, fail, or block"], target_command)
        failures.append(f"fixture {fixture_id}: expected_decision must be pass, fail, or block")
        return result
    if target_command not in FIXTURE_TARGET_SCHEMAS:
        if target_command in FIXTURE_TARGET_RUNTIME_COMMANDS:
            return evaluate_runtime_fixture_case(fixture_path, case_data, fixture_id, expected_decision, failures, blockers)
        observed = "block"
        result = fixture_case_result(fixture_id, fixture_path, expected_decision, observed, "blocker_condition", [f"unsupported target_command {target_command!r}"], target_command)
        if expected_decision != observed:
            failures.append(f"fixture {fixture_id}: expected {expected_decision} but observed block for unsupported target_command")
        return result

    input_data: Any = None
    input_path_text = case_data.get("input_path") or case_data.get("record_path")
    if isinstance(case_data.get("input"), dict):
        input_data = case_data["input"]
    elif isinstance(case_data.get("record"), dict):
        input_data = case_data["record"]
    elif isinstance(input_path_text, str) and input_path_text:
        try:
            input_path = resolve_repository_reference(input_path_text, fixture_path.parent)
            input_data = load_json(input_path)
        except ValueError as exc:
            observed = "block"
            result = fixture_case_result(fixture_id, fixture_path, expected_decision, observed, "invalid_fixture_input", [f"invalid input_path: {exc}"], target_command)
            if expected_decision != observed:
                failures.append(f"fixture {fixture_id}: invalid input_path did not match expected decision {expected_decision}")
            return result
    else:
        observed = "block"
        result = fixture_case_result(fixture_id, fixture_path, expected_decision, observed, "invalid_fixture_input", ["fixture must provide input, record, input_path, or record_path"], target_command)
        if expected_decision != observed:
            failures.append(f"fixture {fixture_id}: missing fixture input did not match expected decision {expected_decision}")
        return result

    if not isinstance(input_data, dict):
        observed = "block"
        result = fixture_case_result(fixture_id, fixture_path, expected_decision, observed, "invalid_fixture_input", ["fixture input must be a JSON object"], target_command)
        if expected_decision != observed:
            failures.append(f"fixture {fixture_id}: non-object fixture input did not match expected decision {expected_decision}")
        return result

    schema_name = FIXTURE_TARGET_SCHEMAS[target_command]
    schema_failures = validate_schema_subset(input_data, load_json(schema_path(schema_name)))
    observed = "fail" if schema_failures else "pass"
    case_class = "expected_fail" if observed == "fail" else "expected_pass"
    result = fixture_case_result(fixture_id, fixture_path, expected_decision, observed, case_class, schema_failures, target_command)
    result["schema_name"] = schema_name
    if expected_decision != observed:
        failures.append(f"fixture {fixture_id}: expected {expected_decision} but observed {observed}")
    return result


def fixture_test(argv: list[str]) -> int:
    parser = JsonArgumentParser(
        prog="skillguard.py fixture-test",
        description="Run explicit fixture cases against standard-library schema-backed SkillGuard check behavior.",
    )
    parser.add_argument("--manifest", help="Fixture manifest JSON under the repository root.")
    parser.add_argument("--fixture-root", help="Directory used to resolve manifest fixture paths. Defaults to the manifest directory.")
    parser.add_argument("--fixture", action="append", default=[], help="Additional fixture case JSON path under the repository root.")
    parser.add_argument("--output", default="-", help="Output report path under the skill root, or '-' for stdout.")
    args = parser.parse_args(argv)
    if not args.manifest and not args.fixture:
        parser.error("fixture-test requires --manifest or at least one --fixture")

    failures: list[str] = []
    blockers: list[str] = []
    inspected_files: list[dict[str, Any]] = []
    fixture_results: list[dict[str, Any]] = []
    manifest_path: Path | None = None
    manifest_fixtures: list[dict[str, Any]] = []

    payload = base_result("fixture-test")
    payload["claim_boundary"] = (
        "This fixture-test result covers only the explicit fixture manifest and fixture case files loaded during this invocation. "
        "It does not prove broad fixture coverage, tests, suite automation, package publication, code-contract validation, release readiness, or future AI behavior."
    )

    before_failures, before_blockers = len(failures), len(blockers)
    fixture_root = repository_root()
    if args.manifest:
        manifest_path = ensure_under_root(args.manifest)
        payload["target_path"] = public_relative_path(manifest_path)
        manifest_data = read_json_record(manifest_path, failures, inspected_files)
        if isinstance(manifest_data, dict):
            failures.extend(validate_schema_subset(manifest_data, load_json(schema_path("skillguard_fixture_manifest.schema.json"))))
            for term in claim_boundary_missing_terms(manifest_data.get("claim_boundary")):
                failures.append(f"fixture manifest claim_boundary missing conservative term {term!r}")
            raw_fixtures = manifest_data.get("fixtures", [])
            if isinstance(raw_fixtures, list):
                manifest_fixtures = [item for item in raw_fixtures if isinstance(item, dict)]
            else:
                failures.append("fixture manifest fixtures field must be an array")
        fixture_root = ensure_under_root(args.fixture_root) if args.fixture_root else manifest_path.parent
    append_check(
        payload,
        "fixture-test:manifest",
        "Fixture manifest",
        check_status(failures, blockers, before_failures, before_blockers),
        "Loaded the fixture manifest when supplied, checked its schema subset, and kept its claim boundary conservative.",
    )

    before_failures, before_blockers = len(failures), len(blockers)
    for index, fixture in enumerate(manifest_fixtures):
        fixture_id = str(fixture.get("fixture_id") or f"manifest-fixture-{index + 1}")
        path_text = fixture.get("path") or fixture.get("fixture_path")
        if not isinstance(path_text, str) or not path_text:
            observed = "block"
            expected = normalize_expected_decision(fixture.get("expected_decision"))
            result = fixture_case_result(fixture_id, None, expected, observed, "invalid_fixture_input", ["fixture manifest entry is missing path"])
            fixture_results.append(result)
            if expected != observed:
                failures.append(f"fixture {fixture_id}: manifest entry missing path")
            continue
        if fixture.get("status") == "stale":
            failures.append(f"fixture {fixture_id}: stale fixtures cannot count as current fixture-test evidence")
        try:
            fixture_path = resolve_repository_reference(path_text, fixture_root)
        except ValueError:
            blockers.append(f"fixture {fixture_id}: fixture path escapes repository boundary")
            fixture_results.append(fixture_case_result(fixture_id, None, normalize_expected_decision(fixture.get("expected_decision")), "block", "blocker_condition", ["fixture path escapes repository boundary"]))
            continue
        fixture_results.append(evaluate_fixture_case(fixture_path, fixture, failures, blockers))
    for path_text in args.fixture:
        try:
            fixture_path = ensure_under_root(path_text)
        except ValueError:
            blockers.append(f"fixture path escapes repository boundary: {path_text}")
            continue
        fixture_results.append(evaluate_fixture_case(fixture_path, None, failures, blockers))
    if not fixture_results:
        failures.append("fixture-test found no fixture cases to execute")
    append_check(
        payload,
        "fixture-test:cases",
        "Fixture cases",
        check_status(failures, blockers, before_failures, before_blockers),
        "Executed explicit fixture cases and compared observed pass/fail/block decisions with expected decisions.",
    )

    class_counts: dict[str, int] = {}
    for result in fixture_results:
        class_counts[result["case_class"]] = class_counts.get(result["case_class"], 0) + 1
    payload["fixture_results"] = fixture_results
    payload["fixture_class_counts"] = class_counts
    payload["files_inspected"] = inspected_files
    payload["evidence"] = [
        {
            "evidence_id": "fixture-manifest-parse",
            "kind": "parser_output",
            "fresh": True,
            "summary": f"Inspected {len(inspected_files)} manifest JSON file(s) and executed {len(fixture_results)} fixture case(s).",
            "source_path": public_relative_path(manifest_path) if manifest_path is not None else "",
        },
        {
            "evidence_id": "fixture-case-results",
            "kind": "command_output",
            "fresh": True,
            "summary": f"Observed fixture result classes: {class_counts}.",
            "source_path": public_relative_path(fixture_root) if fixture_root.exists() else "",
        },
    ]
    payload["failures"] = failures
    payload["blockers"] = blockers
    payload["decision"] = "block" if blockers else "fail" if failures else "pass"
    return write_and_exit(payload, args.output)


def make_closure(argv: list[str]) -> int:
    parser = JsonArgumentParser(
        prog="skillguard.py make-closure",
        description="Derive a bounded closure record from current report data and declared evidence references.",
    )
    parser.add_argument("--report", action="append", required=True, help="Current report JSON path under the repository root.")
    parser.add_argument("--evidence", action="append", default=[], help="Additional direct evidence reference path under the repository root.")
    parser.add_argument("--target", default="", help="Target path for the derived closure record. Defaults to the first report target_path.")
    parser.add_argument("--target-type", default="", help="Target type for the derived closure record. Defaults to the first report target_type.")
    parser.add_argument("--closure-scope", default="current-report-data", help="Human-readable bounded closure scope.")
    parser.add_argument("--max-evidence-age-days", type=int, default=30, help="Maximum age for report checked_at timestamps when present.")
    parser.add_argument("--output", default="-", help="Output report path under the skill root, or '-' for stdout.")
    args = parser.parse_args(argv)

    failures: list[str] = []
    blockers: list[str] = []
    inspected_files: list[dict[str, Any]] = []
    reports: list[tuple[Path, dict[str, Any]]] = []
    evidence_refs: list[dict[str, Any]] = []
    evidence_findings: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    first_report_target = ""
    first_report_type = ""
    payload = base_result("make-closure")
    payload["claim_boundary"] = (
        "This make-closure result derives only a bounded closure record from current report JSON and declared direct evidence references. "
        "It does not treat progress ledgers, acceptance registries, PM text, runtime ids, stale history, or chat summaries as closure proof."
    )

    before_failures, before_blockers = len(failures), len(blockers)
    for report_text in args.report:
        report_path = ensure_under_root(report_text)
        if closure_reference_forbidden(public_relative_path(report_path)):
            failures.append(f"{public_relative_path(report_path)}: forbidden stale-history reference for closure input")
        report = read_json_record(report_path, failures, inspected_files)
        if not isinstance(report, dict):
            failures.append(f"{public_relative_path(report_path)}: report must be a JSON object")
            continue
        reports.append((report_path, report))
        if not first_report_target and isinstance(report.get("target_path"), str):
            first_report_target = report["target_path"]
        if not first_report_type and isinstance(report.get("target_type"), str):
            first_report_type = report["target_type"]
        status = stable_report_status(report)
        if status in {"block", "blocked"} or report.get("blockers"):
            failures.append(f"{public_relative_path(report_path)}: report has blockers and cannot support closed_with_evidence")
        if status in {"fail", "failed"} or report.get("failures"):
            failures.append(f"{public_relative_path(report_path)}: report has failures and cannot support closed_with_evidence")
        for index, skipped in enumerate(report.get("skipped_checks", []) if isinstance(report.get("skipped_checks"), list) else []):
            if skipped_check_is_required(skipped):
                failures.append(f"{public_relative_path(report_path)}: skipped_checks[{index}] is required or has closure impact")
        for term in claim_boundary_missing_terms(report.get("claim_boundary")):
            failures.append(f"{public_relative_path(report_path)}: claim_boundary missing conservative term {term!r}")
        checked_at = current_timestamp_from_text(report.get("checked_at"))
        if checked_at is None:
            failures.append(f"{public_relative_path(report_path)}: report checked_at timestamp is missing or unparsable")
        elif (now - checked_at).days > args.max_evidence_age_days:
            failures.append(f"{public_relative_path(report_path)}: report checked_at older than {args.max_evidence_age_days} days")
        evidence_refs.extend(collect_report_evidence_references(report, report_path))
    append_check(
        payload,
        "make-closure:reports",
        "Current report data",
        check_status(failures, blockers, before_failures, before_blockers),
        "Loaded current report JSON records and checked failures, blockers, skipped checks, timestamps, and conservative claim boundaries.",
    )

    before_failures, before_blockers = len(failures), len(blockers)
    for index, path_text in enumerate(args.evidence):
        evidence_refs.append({"source": "cli", "context": f"--evidence[{index}]", "path": path_text})
    for report_path, _report in reports:
        evidence_refs.append({"source": public_relative_path(report_path), "context": "report-file", "path": public_relative_path(report_path)})
    if not evidence_refs:
        failures.append("make-closure requires at least one declared direct evidence reference")
    for ref in evidence_refs:
        evidence_findings.append(validate_closure_reference(ref, repository_root(), failures, blockers))
    append_check(
        payload,
        "make-closure:evidence",
        "Declared evidence references",
        check_status(failures, blockers, before_failures, before_blockers),
        "Resolved declared evidence references and rejected stale-history, PM-text, acceptance-registry, progress-ledger, or runtime-id references as closure proof.",
    )

    target_path = args.target or first_report_target or (public_relative_path(reports[0][0]) if reports else "")
    target_type = args.target_type or first_report_type or "repository"
    closure_decision = "closed_with_evidence"
    closure_status = "closed_with_evidence"
    decision_reason = "All supplied current reports and direct evidence references support bounded closure."
    if blockers:
        closure_decision = "blocked"
        closure_status = "blocked"
        decision_reason = "A blocker prevented deriving supported closure."
    elif failures:
        closure_decision = "open"
        closure_status = "open"
        decision_reason = "Current report or evidence findings prevent closed_with_evidence."

    closure_record = {
        "schema_version": "skillguard.closure.v1",
        "target_path": target_path,
        "target_type": target_type,
        "status": closure_status,
        "closure_decision": closure_decision,
        "decision_reason": decision_reason,
        "closure_scope": args.closure_scope,
        "checks": payload["checks"],
        "evidence": [
            {
                "evidence_id": "current-report-data",
                "summary": f"Loaded {len(reports)} report JSON record(s) in this invocation.",
                "freshness": "Fresh only for the current files loaded during this command.",
            },
            {
                "evidence_id": "declared-direct-evidence",
                "summary": f"Checked {len(evidence_findings)} evidence reference(s) without using progress ledgers or runtime packet text as closure proof.",
                "freshness": "Fresh only for the current filesystem state.",
            },
        ],
        "failures": failures,
        "blockers": blockers,
        "skipped_checks": [],
        "residual_risk": [
            {
                "risk_id": "bounded-closure-only",
                "description": "Closure is limited to current report data and declared evidence references.",
                "disposition": "Carry as claim boundary.",
            }
        ],
        "claim_boundary": (
            "This closure record is bounded to current report JSON and direct evidence references inspected in this invocation. "
            "It does not prove runtime checker execution, fixture coverage, CLI checks, tests, suite automation, package publication, or code-contract validation without separate current evidence."
        ),
        "next_action": "accept bounded closure" if closure_decision == "closed_with_evidence" else "refresh or repair current report and evidence inputs before closure",
    }
    payload["target_path"] = target_path
    payload["closure_record"] = closure_record
    payload["reports_inspected"] = inspected_files
    payload["evidence_references"] = evidence_findings
    payload["evidence"] = [
        {
            "evidence_id": "closure-report-parse",
            "kind": "parser_output",
            "fresh": True,
            "summary": f"Parsed {len(reports)} report file(s) and derived closure_decision={closure_decision}.",
            "source_path": target_path,
        }
    ]
    payload["failures"] = failures
    payload["blockers"] = blockers
    payload["decision"] = "block" if blockers else "fail" if failures else "pass"
    return write_and_exit(payload, args.output)


def self_check(argv: list[str]) -> int:
    parser = JsonArgumentParser(
        prog="skillguard.py self-check",
        description="Run a static self-check over current SkillGuard repository, skill, checker-change policy, and evidence conventions.",
    )
    parser.add_argument("--target", default=".agents/skills/skillguard", help="SkillGuard skill target under the repository root.")
    parser.add_argument("--policy-root", default="", help="Optional fixture-local root for README, AGENTS, and policy reference docs.")
    parser.add_argument("--output", default="-", help="Output report path under the skill root, or '-' for stdout.")
    args = parser.parse_args(argv)

    target = ensure_under_root(args.target)
    policy_root = ensure_under_root(args.policy_root) if args.policy_root else repository_root()
    policy_relative_paths = {
        "README.md",
        "AGENTS.md",
        "references/06-evidence-freshness-and-closure-boundaries.md",
        "references/08-checker-change-fixture-policy.md",
        "references/09-skillguard-self-check.md",
    }

    def self_check_path(relative: str) -> Path:
        if relative in policy_relative_paths:
            return policy_root / relative
        return repository_root() / relative

    target_relative = public_relative_path(target)
    payload = base_result("self-check", target_relative)
    payload["claim_boundary"] = (
        "This self-check covers current local SkillGuard repository files, the SkillGuard skill entrypoint, checker-change policy artifacts, "
        "control records, report/evidence conventions, public-boundary wording, and local CLI dispatch. It does not prove full fixture coverage, "
        "suite automation, package publication, release readiness, code-contract validation, external publication, or future AI behavior."
    )
    failures: list[str] = []
    blockers: list[str] = []
    inspected_files: list[dict[str, Any]] = []
    public_safety: list[dict[str, Any]] = []
    unsafe_claim_findings: list[dict[str, Any]] = []

    before_failures, before_blockers = len(failures), len(blockers)
    required_paths = [
        "README.md",
        "AGENTS.md",
        "LICENSE",
        "VERSION",
        "pyproject.toml",
        ".agents/skills/skillguard/SKILL.md",
        ".agents/skills/skillguard/scripts/skillguard.py",
        ".agents/skills/skillguard/scripts/checker_engine.py",
        ".agents/skills/skillguard/scripts/skillguard_utils.py",
        ".agents/skills/skillguard/assets/schemas/skillguard_fixture_manifest.schema.json",
        ".agents/skills/skillguard/assets/schemas/skillguard_check_report.schema.json",
        ".agents/skills/skillguard/assets/schemas/skillguard_workflow_report.schema.json",
        ".agents/skills/skillguard/assets/templates/skillguard_checker_change.template.json",
        ".agents/skills/skillguard/assets/templates/skillguard_fixture_manifest.template.json",
        ".agents/skills/skillguard/assets/templates/skillguard_closure.template.json",
        ".agents/skills/skillguard/.skillguard/skillguard_evidence_rules.json",
        ".agents/skills/skillguard/.skillguard/skillguard_closure_policy.json",
        ".agents/skills/skillguard/.skillguard/skillguard_manifest.json",
        "references/06-evidence-freshness-and-closure-boundaries.md",
        "references/08-checker-change-fixture-policy.md",
        "references/09-skillguard-self-check.md",
    ]
    for relative in required_paths:
        path = self_check_path(relative)
        if not path.is_file():
            failures.append(f"required self-check file missing: {relative}")
            continue
        inspected_files.append(checked_file(path, "markdown" if path.suffix.lower() == ".md" else "json" if path.suffix.lower() == ".json" else "file"))
    append_check(
        payload,
        "self-check:required-files",
        "Required self-check files",
        check_status(failures, blockers, before_failures, before_blockers),
        "Checked current SkillGuard repository, skill, script, policy, schema, template, and reference files needed for self-check.",
    )

    before_failures, before_blockers = len(failures), len(blockers)
    for json_relative in [
        ".agents/skills/skillguard/assets/schemas/skillguard_fixture_manifest.schema.json",
        ".agents/skills/skillguard/assets/schemas/skillguard_check_report.schema.json",
        ".agents/skills/skillguard/assets/schemas/skillguard_workflow_report.schema.json",
        ".agents/skills/skillguard/.skillguard/skillguard_evidence_rules.json",
        ".agents/skills/skillguard/.skillguard/skillguard_closure_policy.json",
        ".agents/skills/skillguard/.skillguard/skillguard_manifest.json",
    ]:
        try:
            load_json(repository_root() / json_relative)
        except ValueError as exc:
            failures.append(f"{json_relative}: JSON parse failed: {exc}")
    append_check(
        payload,
        "self-check:json-parse",
        "Policy and schema JSON parse",
        check_status(failures, blockers, before_failures, before_blockers),
        "Parsed required local schema, policy, and manifest JSON files with the Python standard library.",
    )

    before_failures, before_blockers = len(failures), len(blockers)
    command_names = list(COMMANDS)
    required_commands = {"fixture-test", "make-closure", "self-check"}
    for command_name in sorted(required_commands):
        if command_name not in COMMANDS:
            failures.append(f"CLI dispatch missing required command {command_name}")
    readme_path = self_check_path("README.md")
    readme_text = readme_path.read_text(encoding="utf-8") if readme_path.is_file() else ""
    for command_name in command_names:
        if f"`{command_name}`" not in readme_text:
            failures.append(f"README command surface missing `{command_name}`")
    for term in ("fixture coverage", "suite automation", "package publication", "release readiness", "code-contract validation"):
        if term not in readme_text.lower():
            failures.append(f"README public boundary missing {term!r}")
    append_check(
        payload,
        "self-check:public-boundary",
        "README and command boundary",
        check_status(failures, blockers, before_failures, before_blockers),
        "Checked local command dispatch entries against README command wording and conservative public-boundary terms.",
    )

    before_failures, before_blockers = len(failures), len(blockers)
    skill_text = (target / "SKILL.md").read_text(encoding="utf-8") if (target / "SKILL.md").is_file() else ""
    frontmatter, frontmatter_failures = parse_skill_frontmatter(skill_text) if skill_text else ({}, ["SKILL.md missing"])
    failures.extend(frontmatter_failures)
    if frontmatter.get("name") != target.name:
        failures.append("SkillGuard SKILL.md frontmatter name must match target directory")
    headings = {match.group(1).strip() for match in HEADING_RE.finditer(skill_text)}
    for section in REQUIRED_SKILL_SECTIONS:
        if section not in headings:
            failures.append(f"SkillGuard SKILL.md missing required section {section}")
    append_check(
        payload,
        "self-check:skill-entrypoint",
        "SkillGuard skill entrypoint",
        check_status(failures, blockers, before_failures, before_blockers),
        "Parsed SkillGuard SKILL.md frontmatter and checked required entrypoint sections.",
    )

    before_failures, before_blockers = len(failures), len(blockers)
    ref08_path = self_check_path("references/08-checker-change-fixture-policy.md")
    ref09_path = self_check_path("references/09-skillguard-self-check.md")
    ref08 = ref08_path.read_text(encoding="utf-8").lower() if ref08_path.is_file() else ""
    ref09 = ref09_path.read_text(encoding="utf-8").lower() if ref09_path.is_file() else ""
    for term in ("positive fixtures", "negative fixtures", "stale fixture", "absent fixture", "compatibility", "public-safety"):
        if term not in ref08:
            failures.append(f"checker-change fixture policy missing term {term!r}")
    for term in ("required inputs", "deterministic checks", "public-safety checks", "closure boundaries", "pass, fail, and block"):
        if term not in ref09:
            failures.append(f"self-check reference missing term {term!r}")
    append_check(
        payload,
        "self-check:policy-artifacts",
        "Checker-change and self-check policy artifacts",
        check_status(failures, blockers, before_failures, before_blockers),
        "Checked checker-change fixture policy and self-check reference documents for required policy surfaces.",
    )

    before_failures, before_blockers = len(failures), len(blockers)
    public_paths = [
        self_check_path("README.md"),
        self_check_path("AGENTS.md"),
        target / "SKILL.md",
        self_check_path("references/06-evidence-freshness-and-closure-boundaries.md"),
        self_check_path("references/08-checker-change-fixture-policy.md"),
        self_check_path("references/09-skillguard-self-check.md"),
    ]
    for path in public_paths:
        for finding in public_safety_findings(path):
            public_safety.append(finding)
            failures.append(f"{finding['path']}: public-safety scan found {finding['finding_id']} on line {finding['line']}")
        unsafe_claim_findings.extend(scan_text_for_unsafe_claims(path, failures))
    append_check(
        payload,
        "self-check:public-safety",
        "Public safety and unsafe-claim scans",
        check_status(failures, blockers, before_failures, before_blockers),
        "Scanned public SkillGuard files for private paths, runtime ids, credentials, private keys, and declared unsafe overclaim phrases.",
    )

    payload["files_inspected"] = inspected_files
    payload["public_safety_findings"] = public_safety
    payload["unsafe_claim_findings"] = unsafe_claim_findings
    payload["command_names"] = command_names
    payload["evidence"] = [
        {
            "evidence_id": "self-check-file-inventory",
            "kind": "filesystem_check",
            "fresh": True,
            "summary": f"Inspected {len(inspected_files)} current SkillGuard files for self-check.",
            "source_path": target_relative,
        },
        {
            "evidence_id": "self-check-command-boundary",
            "kind": "command_table_check",
            "fresh": True,
            "summary": f"Checked {len(command_names)} local command dispatch entries against README command wording.",
            "source_path": ".agents/skills/skillguard/scripts/checker_engine.py",
        },
        {
            "evidence_id": "self-check-public-safety",
            "kind": "text_scan",
            "fresh": True,
            "summary": f"Scanned {len(public_paths)} public files for public-safety and unsafe-claim patterns.",
            "source_path": "README.md",
        },
    ]
    payload["skipped_checks"] = [
        {
            "check_id": "persistent-fixture-corpus",
            "reason": "No persistent fixture corpus is required for this self-check command; fixture-test accepts explicit supplied fixture cases.",
            "required": False,
            "status_impact": "Not a pass claim for broad fixture coverage.",
        }
    ]
    payload["residual_risk"] = [
        "This self-check is static and local; it does not replace separate fixture coverage, package installation, release, or code-contract validation evidence.",
        "Semantic adequacy of policy wording may still need human review for release decisions.",
    ]
    payload["failures"] = failures
    payload["blockers"] = blockers
    payload["decision"] = "block" if blockers else "fail" if failures else "pass"
    return write_and_exit(payload, args.output)


CommandHandler = Callable[[list[str]], int]


COMMAND_SUMMARIES: dict[str, str] = {
    "commands": "List command dispatch targets.",
    "inventory": "Generate a repository inventory record.",
    "init-target": "Create missing target .skillguard directories without rewriting existing files.",
    "init-suite": "Create missing suite-level .skillguard directories without rewriting existing files.",
    "mark": "Create, update, or report an already-present marker record for one target or suite scope.",
    "check-skill": "Check one target skill directory for static SkillGuard contract and control-record readiness.",
    "check-suite": "Check suite records, member relations, child closure evidence, stale evidence, and unsafe claims.",
    "check-skill-contract": "Check one skill contract JSON record.",
    "check-suite-map": "Check one suite map JSON record.",
    "check-suite-contract": "Check one suite contract JSON record.",
    "check-fixture-manifest": "Check one fixture manifest JSON record.",
    "fixture-test": "Run explicit fixture cases and compare expected pass, fail, block, and invalid-input outcomes.",
    "check-ai-judgment": "Check one AI judgment JSON record.",
    "check-report": "Check one deterministic check-report JSON record.",
    "check-workflow-report": "Check one workflow-report JSON record.",
    "make-closure": "Derive a bounded closure record from current report data and declared direct evidence references.",
    "self-check": "Check the current SkillGuard repository, skill entrypoint, checker policy, evidence conventions, and public boundaries.",
    "write-report": "Load JSON and write stable parseable JSON to stdout or a skill-root-local file.",
}


COMMANDS: dict[str, CommandHandler] = {
    "commands": commands,
    "inventory": inventory,
    "init-target": init_target,
    "init-suite": init_suite,
    "mark": mark,
    "check-skill": check_skill,
    "check-suite": check_suite,
    "check-skill-contract": check_skill_contract,
    "check-suite-map": check_suite_map,
    "check-suite-contract": check_suite_contract,
    "check-fixture-manifest": check_fixture_manifest,
    "fixture-test": fixture_test,
    "check-ai-judgment": check_ai_judgment,
    "check-report": check_report,
    "check-workflow-report": check_workflow_report,
    "make-closure": make_closure,
    "self-check": self_check,
    "write-report": write_report_command,
}
