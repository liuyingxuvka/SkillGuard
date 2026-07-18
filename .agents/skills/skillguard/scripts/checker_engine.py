"""Checker-engine functions used by the SkillGuard CLI dispatch surface."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import re
import shutil
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

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
from skillguard_v2.contract_schema import (
    BINDING_SOURCE_SCHEMA,
    MODEL_EXPORT_SCHEMA,
    validate_binding_source,
    validate_check_manifest as validate_v2_check_manifest,
    validate_compiled_contract,
)
from skillguard_v2.contract_compiler import (
    canonical_hash,
    compile_skill_contract,
)
from skillguard_v2.content_projection import (
    current_content_projection_from_files,
    impact_file_hash,
)
from skillguard_v2 import global_router_projection as current_global_router
from skillguard_v2 import global_router_discovery as current_global_discovery
from skillguard_v2.global_router_transaction import (
    GlobalRouterTransactionError,
    apply_global_router_transaction,
)
from skillguard_v2.portfolio_cli import PORTFOLIO_COMMANDS
from skillguard_v2.portable_content import (
    RUNTIME,
    classify_relative_path,
    owned_runtime_parent_may_be_pruned,
    portable_files,
)
from skillguard_v2.path_identity import (
    canonical_filesystem_path,
    physical_relative_path,
)
from skillguard_v2.validation_execution_policy import (
    VALIDATION_EXECUTION_POLICY_ID,
    VALIDATION_EXECUTION_POLICY_LINES,
)
from skillguard_v2.runtime_authority import (
    AUTHORITY_CURRENT,
    resolve_runtime_authority,
)
from skillguard_v2.template_packs import (
    TemplatePackError,
    build_instance_receipt,
    seal_builder_receipt,
    seal_validator_receipt,
    sha256_identity,
    unresolved_placeholders,
    validate_template_catalog,
)
from skillguard_v2.template_adapters import compile_target_template_projection
from skillguard_v2.template_profiles import (
    TEMPLATE_PROFILE_SCHEMA,
    TemplateProfileError,
    build_builtin_scaffold_profile,
    build_external_selection_profile,
    validate_builtin_profile_current,
    validate_template_profile,
)


CHECKER_VERSION = "skillguard.local_cli_dispatch.v1"
SCHEMA_DIR = skill_root() / "assets" / "schemas"
MARKER_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
GLOBAL_REGISTRY_SCHEMA_VERSION = current_global_router.GLOBAL_REGISTRY_SCHEMA_VERSION
GLOBAL_PROMPT_PROJECTION_SCHEMA_VERSION = (
    current_global_router.GLOBAL_PROMPT_PROJECTION_SCHEMA_VERSION
)
GLOBAL_PROMPT_BEGIN = current_global_router.GLOBAL_PROMPT_BEGIN
GLOBAL_PROMPT_END = current_global_router.GLOBAL_PROMPT_END
GLOBAL_ROUTER_SKILL_ID = current_global_router.GLOBAL_ROUTER_SKILL_ID
GLOBAL_ROUTE_STOPWORDS = {"and", "are", "for", "from", "into", "the", "this", "that", "with"}
MARKER_STATUSES = ("checked", "needs-review", "blocked", "stale", "accepted")
REFERENCE_SPAN_RE = re.compile(r"`([^`]+)`")
FENCED_CODE_BLOCK_RE = re.compile(
    r"^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*(?:\r?\n|$)",
    re.DOTALL | re.MULTILINE,
)
MARKDOWN_LINK_RE = re.compile(
    r"!?\[[^\]\n]*\]\(\s*(?:<([^>\n]+)>|([^\s)]+))"
    r"(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)"
)
MARKDOWN_LINK_DEFINITION_RE = re.compile(
    r"^[ \t]{0,3}\[[^\]\n]+\]:\s*(?:<([^>\n]+)>|([^\s]+))",
    re.MULTILINE,
)
DATABASE_URI_RE = re.compile(
    r"(?:^|[=\s])(?:sqlite|postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|mssql|oracle|duckdb|jdbc):",
    re.IGNORECASE,
)
SQL_EXPRESSION_RE = re.compile(
    r"^(?:SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|WITH|PRAGMA|ATTACH|VACUUM|REPLACE|UPSERT|MERGE|EXPLAIN)\b",
    re.IGNORECASE,
)
INLINE_CLI_ARGUMENT_RE = re.compile(r"(?:^|\s)--?[A-Za-z0-9]")
SHELL_OPERATOR_RE = re.compile(r"(?:&&|\|\||[|;<>])")
COMMAND_LAUNCHER_RE = re.compile(
    r"^(?:python(?:\d+(?:\.\d+)*)?|py|node|deno|bun|bash|sh|zsh|fish|pwsh|powershell|cmd(?:\.exe)?|"
    r"git|docker|podman|make|ninja|cargo|go|java|dotnet|npm|npx|pnpm|yarn|pip|pipx|uv|pytest|"
    r"sqlite3|psql|mysql|openspec|skillguard)\b",
    re.IGNORECASE,
)
INLINE_COMMAND_CONTEXT_RE = re.compile(r"(?:\brun|\bexecute|\binvoke|\bcall)\s*$", re.IGNORECASE)
INLINE_CLI_VALUE_BEFORE_RE = re.compile(
    r"(?:`--?[A-Za-z0-9][^`]*`|--?[A-Za-z0-9][A-Za-z0-9_-]*)\s*(?:=|,|and|with)?\s*$",
    re.IGNORECASE,
)
INLINE_CLI_VALUE_AFTER_RE = re.compile(
    r"^\s*(?:(?:as|for|to)\s+(?:the\s+)?)?(?:`--?[A-Za-z0-9][^`]*`|--?[A-Za-z0-9][A-Za-z0-9_-]*|"
    r"CLI\b|command\b|argument\b|option\b|flag\b)",
    re.IGNORECASE,
)
DECLARED_REFERENCE_CONTEXT_RE = re.compile(
    r"(?:\b(?:declared|required)\s+(?:local\s+)?(?:reference|script|schema|artifact|file|path)|"
    r"\b(?:reference|script|schema|artifact|file|path)(?:\s+under\s+test)?\s*:)\s*$",
    re.IGNORECASE,
)
DATABASE_CONTEXT_RE = re.compile(
    r"\b(?:database|sqlite|postgres(?:ql)?|mysql|mariadb|mongodb|mssql|oracle|duckdb|jdbc)\b",
    re.IGNORECASE,
)
DATABASE_RUNTIME_SEGMENT_RE = re.compile(
    r"(?:^|[\\/])(?:runtime|data|var|state|cache|tmp|database|databases|db)(?:[\\/]|$)",
    re.IGNORECASE,
)
DATABASE_FILE_SUFFIX_RE = re.compile(r"\.(?:db|sqlite3?|duckdb|mdb|accdb)(?:[?#].*)?$", re.IGNORECASE)
PLAIN_LOCAL_FILENAME_RE = re.compile(r"^[A-Za-z0-9_.][A-Za-z0-9_. -]*\.[A-Za-z0-9_-]{1,32}$")
SLASH_VALUE_SEQUENCE_RE = re.compile(
    r"^[0-9]+(?:\.[0-9]+)?(?:ms|s|m|h|kb|mb|gb)"
    r"(?:/[0-9]+(?:\.[0-9]+)?(?:ms|s|m|h|kb|mb|gb))+$",
    re.IGNORECASE,
)
TRANSIENT_SKILLGUARD_RUNTIME_PREFIXES = (
    ".skillguard/runs",
    ".skillguard/locks",
    ".skillguard/bootstrap",
    ".skillguard/test-results",
)
DECLARED_REFERENCE_PREFIXES = (
    ".agents/",
    ".skillguard/",
    "references/",
    "scripts/",
    "assets/",
    "schemas/",
    "artifacts/",
    "fixtures/",
    "tests/",
)
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
    ("private-local-path", re.compile(r"(?<![A-Za-z])(?:[A-Za-z]:[\\/][^\\s`\"']+|/[Uu]sers/|\\\\[^\\s`\"']+)")),
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
    "check-suite-map": "skillguard_suite_map.schema.json",
    "check-suite-contract": "skillguard_suite_contract.schema.json",
    "check-fixture-manifest": "skillguard_fixture_manifest.schema.json",
    "check-ai-judgment": "skillguard_ai_judgment.schema.json",
    "check-report": "skillguard_check_report.schema.json",
    "check-workflow-report": "skillguard_workflow_report.schema.json",
}
FIXTURE_TARGET_RUNTIME_COMMANDS = {
    "check-runtime-authority",
    "check-contract",
    "check-depth",
    "check-readme-release",
    "check-skill",
    "check-suite",
    "build-global-registry",
    "check-global-registry",
    "generate-skill",
    "refresh-global-router",
    "audit-portfolio",
    "mark-portfolio-impact",
    "graduate-portfolio",
    "route-task",
    "self-check",
    "scan-global-skills",
}
FIXTURE_EXPECTED_DECISIONS = {"pass", "fail", "block"}
EXTERNAL_TARGET_BINDING_SCHEMA_NAME = "skillguard_external_target_binding_v1.schema.json"
EXTERNAL_TARGET_BINDING_SCHEMA_VERSION = "skillguard.external_target_binding.v1"
REVIEW_CHECKER_CHANGE_BASELINE_SCHEMA = "skillguard.checker_change_baseline.v1"
REVIEW_CHECKER_CHANGE_RESULT_SCHEMA = "skillguard.review_checker_change_result.v1"
MAINTENANCE_RECORD_SCHEMA_VERSION = "skillguard.maintenance_record.v1"
MAINTENANCE_RECORD_RESULT_SCHEMA = "skillguard.maintenance_record_check_result.v1"
MAINTENANCE_RECORD_REQUIRED_FIELDS = (
    "schema_version",
    "record_id",
    "record_kind",
    "artifact_id",
    "route_node_id",
    "route_version",
    "route_registry_version",
    "command_surface",
    "content_hash",
    "evidence_timestamp",
    "status",
    "blockers",
    "owner_action",
)
MAINTENANCE_RECORD_KINDS = {
    "checker_change_review",
    "command_surface",
    "fixture_evidence",
    "route_task_metadata",
    "self_check",
    "stale_evidence_review",
    "target_check",
    "workflow_evidence",
}
MAINTENANCE_RECORD_FORBIDDEN_LEGACY_ALIASES = {
    "changes_directory_found",
    "checkerCommand",
    "maintenanceRefresh",
    "pass_or_block",
    "result",
    "routeVersion",
    "stale_bindings",
    "validation_status",
}
MAINTENANCE_RECORD_PRIVATE_MARKERS = (
    "PRIVATE_ROUTE_BODY_TEXT_DO_NOT_ECHO",
    "sealed_body",
    "sealed packet body text",
    "role-only packet body",
    "sibling role-only result text",
)
VALIDATION_REGISTRY_SCHEMA_VERSION = "skillguard.validation_registry.v1"
VALIDATION_REGISTRY_COMMANDS = {"route-task", "generate-skill", "generate-suite"}
VALIDATION_REGISTRY_STRUCTURED_BLOCKER_FIELDS = (
    "routing_conflict_blockers",
    "stale_evidence_blockers",
    "checker_change_blockers",
    "checker_change_suite_guard_blockers",
    "maintenance_record_blockers",
)
VALIDATION_REGISTRY_INVALID_INPUT_CODES = {
    "ambiguous_task_sources",
    "conflicting_input_sources",
    "conflicting_task_sources",
    "input_file_not_found",
    "invalid_config_shape",
    "invalid_input_path",
    "invalid_path_config",
    "invalid_responsibility_field",
    "invalid_route_hint_field",
    "invalid_task_field",
    "malformed_json",
    "missing_task_text",
    "stale_route_identifier",
    "unsupported_requested_responsibility",
    "unsupported_route_hint",
}
VALIDATION_REGISTRY_GENERATION_BLOCKER_CODES = {
    "command_path_requires_explicit_route_hint",
    "generator_execution_forbidden_by_no_write_flag",
    "missing_command_input",
    "unsupported_command_path",
}
VALIDATION_REGISTRY_CONFLICT_CODES = {
    "conflicting_responsibility_sources",
    "incompatible_route_hint",
    "incompatible_route_identifiers",
    "multiple_equal_route_candidates",
    "mutually_exclusive_flags",
    "responsibility_route_conflict",
}
PLAN_SKILL_SUPPORTED_WORKFLOW_MODES = ("create",)
PLAN_SKILL_SUPPORTED_SAFE_EDIT_MODES = ("no_write",)
SKILL_BLUEPRINT_SCHEMA_VERSION = "skillguard.skill_blueprint.v2"
TEMPLATE_REQUEST_FIELDS = frozenset(
    {
        "adapter_projection_path",
        "parameters",
    }
)
TEMPLATE_PROFILE_PROMPT_PATHS = {
    "prompt_selection": "assets/templates/template_selection_supervision.md.template",
    "prompt_instance": "assets/templates/template_instance_supervision.md.template",
    "prompt_installation": "assets/templates/template_installation_supervision.md.template",
}
PLAN_SKILL_DEFAULT_LISTS = {
    "use_when": ["Use when the declared skill purpose and activation boundary match the requested work."],
    "do_not_use_when": ["Do not use when the request falls outside the declared activation boundary or required evidence is unavailable."],
    "required_workflow": [
        "Inspect current target scope before creating files.",
        "Preserve deterministic evidence separately from reviewer judgment.",
        "Report blockers, skipped checks, residual risk, and claim boundary before closure.",
    ],
    "hard_gates": [
        "Target path remains inside the repository and is not written by plan-skill.",
        "Required activation, workflow, hard-gate, output, evidence, and claim-boundary fields remain visible.",
        "Future acceptance depends on current direct evidence and reviewer judgment.",
    ],
    "output_requirements": [
        "evidence",
        "failures",
        "blockers",
        "skipped_checks",
        "residual_risk",
        "claim_boundary",
    ],
}
GENERATE_SKILL_REQUIRED_BLUEPRINT_FIELDS = (
    "blueprint_id",
    "source_command",
    "source_input",
    "target",
    "skill",
    "workflow_mode",
    "closure_scope",
    "evidence_policy",
    "safe_edit_scope",
    "phase_plan",
    "evidence_gates",
    "handoffs",
    "closure_report",
    "residual_risk",
    "claim_boundary",
    "template_profile",
)
GENERATE_SKILL_BLUEPRINT_FIELDS = frozenset(
    {"schema_version", *GENERATE_SKILL_REQUIRED_BLUEPRINT_FIELDS}
)
GENERATE_SKILL_SKILL_FIELDS = frozenset(
    {"name", "description", "purpose", "target_path", "use_when", "do_not_use_when"}
)
GENERATE_SKILL_REQUIRED_DIRECTORIES = (
    ".skillguard",
    ".skillguard/runs",
    "assets/schemas",
    "assets/templates",
    "fixtures",
    "references",
    "scripts",
    "tests",
)
GENERATE_SKILL_REQUIRED_DIRECTORY_ROLES = {
    ".skillguard": "SkillGuard control root",
    ".skillguard/runs": "runtime run-record directory",
    "assets": "generated asset parent directory",
    "assets/schemas": "schema directory",
    "assets/templates": "template directory",
    "fixtures": "fixture directory",
    "references": "reference directory",
    "scripts": "script directory",
    "tests": "test directory",
}
GENERATE_SKILL_REQUIRED_FILES = (
    "SKILL.md",
    "README.md",
    "references/README.md",
    "assets/schemas/generated_record.schema.json",
    "assets/templates/check_report.template.json",
    "scripts/README.md",
    "scripts/run_checks.py",
    "fixtures/README.md",
    "fixtures/fixture-manifest.json",
    "tests/README.md",
    "tests/test_smoke.py",
    ".skillguard/flowguard_contract_model.py",
    ".skillguard/contract-source.json",
    ".skillguard/author-guidance.md",
    ".skillguard/compiled-contract.json",
    ".skillguard/check-manifest.json",
)
GENERATE_SUITE_REQUIRED_BLUEPRINT_FIELDS = (
    "suite_name",
    "target",
    "workflow_mode",
    "member_skills",
    "safe_edit_scope",
    "evidence_policy",
    "claim_boundary",
)
GENERATE_SUITE_REQUIRED_DIRECTORIES = (
    ".skillguard",
    ".skillguard/suite",
    ".skillguard/suite/evidence",
    ".skillguard/suite/markers",
    ".skillguard/suite/members",
    ".skillguard/suite/reports",
    "members",
)
GENERATE_SUITE_REQUIRED_DIRECTORY_ROLES = {
    ".skillguard": "SkillGuard control root",
    ".skillguard/suite": "suite control root",
    ".skillguard/suite/evidence": "suite evidence directory",
    ".skillguard/suite/markers": "suite marker directory",
    ".skillguard/suite/members": "suite member record directory",
    ".skillguard/suite/reports": "suite report directory",
    "members": "child skill member root",
}
GENERATE_SUITE_REQUIRED_FILES = (
    "README.md",
    ".skillguard/suite/suite-map.json",
    ".skillguard/suite/suite-contract.json",
    ".skillguard/suite/evidence/source_blueprint_trace.json",
    ".skillguard/suite/evidence/suite_closure.json",
    ".skillguard/suite/reports/suite_generation_report.json",
)
ROUTE_TASK_REGISTRY_VERSION = "skillguard.route_registry.v3"
ROUTE_TASK_PATH_FIELDS = {
    "blueprint",
    "blueprint_path",
    "checker_change_review",
    "checker_change_review_path",
    "checker_change_reviews",
    "checker_change_review_paths",
    "command_input",
    "command_input_path",
    "generator_input",
    "generator_input_path",
    "input",
    "input_path",
    "manifest",
    "member_root",
    "output",
    "path",
    "policy_root",
    "report",
    "suite_contract",
    "suite_map",
    "suite_root",
    "target",
    "target_path",
}
ROUTE_TASK_REPAIR_OR_LEGACY_HINTS = {
    "old-router",
    "old-router-v0",
    "legacy-router",
    "route-task-v0",
    "fg-04b-generate-skill-repair-v3",
    "fg-04c-generate-suite-repair-v4",
}
ROUTE_TASK_ROUTE_HINT_FIELDS = ("route_hint", "route_id", "route_node_id", "command_family")
ROUTE_TASK_RESPONSIBILITY_FIELDS = ("responsibility", "requested_responsibility", "requested_owner")
ROUTE_TASK_MUTUALLY_EXCLUSIVE_FLAG_GROUPS = (
    ("execute", "dry_run"),
    ("write_files", "no_write"),
    ("mutate_project", "no_mutation"),
    ("invoke_generators", "no_generators"),
)
ROUTE_TASK_GENERATOR_COMMANDS = {"generate-skill", "generate-suite"}
ROUTE_TASK_GENERATOR_INPUT_FIELDS = (
    "command_input",
    "command_input_path",
    "generator_input",
    "generator_input_path",
    "blueprint",
    "blueprint_path",
    "input",
    "input_path",
)
ROUTE_TASK_CHECKER_CHANGE_REVIEW_FIELDS = (
    "checker_change_review",
    "checker_change_review_path",
    "checker_change_reviews",
    "checker_change_review_paths",
)
ROUTE_TASK_CHECKER_SUITE_FIELDS = (
    "checker_suite",
    "checker_suites",
    "checker_suite_selection",
    "selected_checker_suite",
    "selected_checker_suites",
)
ROUTE_TASK_GENERATOR_EXECUTE_FLAGS = ("execute", "invoke_generators", "write_files")
ROUTE_TASK_GENERATOR_NO_WRITE_FLAGS = ("dry_run", "no_write", "no_mutation", "no_generators")
ROUTE_TASK_ROUTE_REGISTRY: tuple[dict[str, Any], ...] = (
    {
        "route_id": "skillguard.route.route-task.v1",
        "route_node_id": "route-task",
        "command_family": "route-task",
        "responsibility": "router",
        "next_step": "Return a deterministic SkillGuard route decision.",
        "status": "current",
        "hints": ("route-task", "router", "route", "routing"),
        "keywords": ("route task", "route request", "routing decision", "choose route", "dispatch task"),
    },
    {
        "route_id": "skillguard.route.plan-skill.v1",
        "route_node_id": "plan-skill",
        "command_family": "plan-skill",
        "responsibility": "planner",
        "next_step": "Run plan-skill with a repository-local skill idea JSON file.",
        "status": "current",
        "hints": ("plan-skill", "skill-plan", "skill-blueprint-preview", "blueprint-preview"),
        "keywords": ("plan skill", "skill idea", "blueprint preview", "no-write preview", "skill blueprint preview"),
    },
    {
        "route_id": "skillguard.route.generate-skill.v1",
        "route_node_id": "generate-skill",
        "command_family": "generate-skill",
        "responsibility": "generator",
        "next_step": "Run generate-skill with a valid Skill Blueprint after review.",
        "status": "current",
        "hints": ("generate-skill", "skill-scaffold", "skill-generator"),
        "keywords": ("generate skill", "create skill scaffold", "skill scaffold", "draft skill scaffold", "skill blueprint"),
    },
    {
        "route_id": "skillguard.route.generate-suite.v1",
        "route_node_id": "generate-suite",
        "command_family": "generate-suite",
        "responsibility": "generator",
        "next_step": "Run generate-suite with a valid Suite Blueprint after review.",
        "status": "current",
        "hints": ("generate-suite", "suite-scaffold", "suite-generator"),
        "keywords": ("generate suite", "suite scaffold", "suite blueprint", "multi-skill suite", "child skill scaffold"),
    },
    {
        "route_id": "skillguard.route.check-contract.v1",
        "route_node_id": "check-contract",
        "command_family": "check-contract",
        "responsibility": "checker",
        "next_step": "Run check-contract against the target skill work contract.",
        "status": "current",
        "hints": ("check-contract", "contract-check"),
        "keywords": (
            "check contract",
            "validate contract",
            "work contract schema",
            "contract hash",
            "contract closure rule",
        ),
    },
    {
        "route_id": "skillguard.route.check-depth.v1",
        "route_node_id": "check-depth",
        "command_family": "check-depth",
        "responsibility": "checker",
        "next_step": "Run check-depth when a target skill contract must prove source-specific obligations, current run evidence, and non-parallel route binding.",
        "status": "current",
        "hints": ("check-depth", "deep-contract-check", "source-requirement-check", "non-parallel-route-proof"),
        "keywords": (
            "check depth",
            "deep contract",
            "shallow contract",
            "source requirements",
            "acceptance obligations",
            "skill specific checks",
            "closure blockers",
            "parallel route risk",
        ),
    },
    {
        "route_id": "skillguard.route.check-readme-release.v1",
        "route_node_id": "check-readme-release",
        "command_family": "check-readme-release",
        "responsibility": "checker",
        "next_step": "Run check-readme-release before publishing README-facing SkillGuard releases.",
        "status": "current",
        "hints": ("check-readme-release", "readme-release-gate", "readme-gates"),
        "keywords": (
            "readme release",
            "readme gate",
            "bilingual readme",
            "hero provenance",
            "version consistency",
            "public boundary",
            "readme model evidence",
        ),
    },
    {
        "route_id": "skillguard.route.maintainer-adopt.current",
        "route_node_id": "maintainer-adopt",
        "command_family": "maintainer-adopt",
        "responsibility": "author-repository-adoption",
        "next_step": "Run maintainer-adopt only after every declared member proves the explicit skill_maintainer_source role and maintenance-unit binding.",
        "status": "current",
        "hints": ("maintainer-adopt", "skillguard-author-adoption", "author-maintenance-prompt"),
        "keywords": (
            "adopt maintainer repository",
            "skillguard author repository",
            "author prompt",
            "maintainer agents block",
            "skill author maintenance",
        ),
    },
    {
        "route_id": "skillguard.route.maintainer-audit.current",
        "route_node_id": "maintainer-audit",
        "command_family": "maintainer-audit",
        "responsibility": "author-repository-audit",
        "next_step": "Run maintainer-audit before claiming that an explicit author repository carries current maintenance instructions.",
        "status": "current",
        "hints": ("maintainer-audit", "skillguard-author-audit", "author-prompt-audit"),
        "keywords": (
            "audit maintainer adoption",
            "check skillguard author prompt",
            "verify author agents block",
            "skillguard repository link",
            "native route evidence",
        ),
    },
    {
        "route_id": "skillguard.route.build-current-portfolio-registry.v1",
        "route_node_id": "build-current-portfolio-registry",
        "command_family": "build-current-portfolio-registry",
        "responsibility": "portfolio-runtime",
        "next_step": "Build revision one directly from the exact reviewed current scope without consuming prior registry authority.",
        "status": "current",
        "hints": (
            "build-current-portfolio-registry",
            "direct-portfolio-registry-replacement",
            "portfolio-scope-replacement",
        ),
        "keywords": (
            "build current portfolio registry",
            "direct portfolio registry replacement",
            "replace stale portfolio registry from scope",
            "portfolio scope replacement",
        ),
    },
    {
        "route_id": "skillguard.route.audit-portfolio.v1",
        "route_node_id": "audit-portfolio",
        "command_family": "audit-portfolio",
        "responsibility": "portfolio-runtime",
        "next_step": "Audit the private portfolio registry before impact propagation or one-unit graduation.",
        "status": "current",
        "hints": ("audit-portfolio", "portfolio-audit", "portfolio-currentness"),
        "keywords": (
            "audit portfolio",
            "portfolio registry",
            "maintenance unit revalidation",
            "portfolio currentness",
            "skillguard current runtime identity",
        ),
    },
    {
        "route_id": "skillguard.route.prepare-portfolio-run.v1",
        "route_node_id": "prepare-portfolio-run",
        "command_family": "prepare-portfolio-run",
        "responsibility": "portfolio-runner",
        "next_step": "Freeze one complete ordered portfolio plan and every exact job specification before any representative run is claimed.",
        "status": "current",
        "hints": (
            "prepare-portfolio-run",
            "portfolio-run-prepare",
            "portfolio-preparation",
        ),
        "keywords": (
            "prepare portfolio run",
            "freeze portfolio plan",
            "global portfolio job plan",
            "job specs before claim",
            "portfolio preparation",
        ),
    },
    {
        "route_id": "skillguard.route.execute-portfolio-run.v1",
        "route_node_id": "execute-portfolio-run",
        "command_family": "execute-portfolio-run",
        "responsibility": "portfolio-runner",
        "next_step": "Execute every frozen representative job through ordinary claimed current SkillGuard runs under the preparation identity.",
        "status": "current",
        "hints": (
            "execute-portfolio-run",
            "portfolio-run-execute",
            "portfolio-execution",
        ),
        "keywords": (
            "execute portfolio run",
            "run prepared portfolio jobs",
            "claimed v2 portfolio jobs",
            "portfolio execution",
        ),
    },
    {
        "route_id": "skillguard.route.capture-portfolio-production-revalidation.v1",
        "route_node_id": "capture-portfolio-production-revalidation",
        "command_family": "capture-portfolio-production-revalidation",
        "responsibility": "portfolio-production-recorder",
        "next_step": "Capture one exact member scheduled-production declared-check depth, terminal, closure, and installed-runtime binding after execution and before assembly.",
        "status": "current",
        "hints": (
            "capture-portfolio-production-revalidation",
            "portfolio-production-capture",
            "capture-production-binding",
        ),
        "keywords": (
            "capture portfolio production revalidation",
            "capture member production binding",
            "scheduled production portfolio receipt",
            "production evidence before assembly",
        ),
    },
    {
        "route_id": "skillguard.route.assemble-portfolio-run.v1",
        "route_node_id": "assemble-portfolio-run",
        "command_family": "assemble-portfolio-run",
        "responsibility": "portfolio-runner",
        "next_step": "Replay the prepared executions and assemble a verifier-owned graduation candidate without writing the registry.",
        "status": "current",
        "hints": (
            "assemble-portfolio-run",
            "portfolio-run-assemble",
            "portfolio-assembly",
        ),
        "keywords": (
            "assemble portfolio run",
            "assemble portfolio evidence",
            "replay portfolio receipts",
            "portfolio graduation dry run",
            "portfolio assembly",
        ),
    },
    {
        "route_id": "skillguard.route.graduate-portfolio.v1",
        "route_node_id": "graduate-portfolio",
        "command_family": "graduate-portfolio",
        "responsibility": "portfolio-graduation-verifier",
        "next_step": "Graduate exactly one maintenance unit only from that unit's current source-maintenance and consumer-isolation evidence; other units remain independent status rows.",
        "status": "current",
        "hints": (
            "graduate-portfolio",
            "portfolio-graduation",
            "graduate-skill-portfolio",
        ),
        "keywords": (
            "graduate portfolio",
            "graduate skill portfolio",
            "authorize portfolio graduation",
            "update portfolio current status",
        ),
    },
    {
        "route_id": "skillguard.route.check-skill.v1",
        "route_node_id": "check-skill",
        "command_family": "check-skill",
        "responsibility": "checker",
        "next_step": "Run check-skill against the target skill directory.",
        "status": "current",
        "hints": ("check-skill", "skill-check", "single-skill-check"),
        "keywords": ("check skill", "single skill", "skill directory", "skill entrypoint", "skillguard records"),
    },
    {
        "route_id": "skillguard.route.check-suite.v1",
        "route_node_id": "check-suite",
        "command_family": "check-suite",
        "responsibility": "checker",
        "next_step": "Run check-suite against suite records and member paths.",
        "status": "current",
        "hints": ("check-suite", "suite-check", "suite-record-check"),
        "keywords": ("check suite", "suite map", "suite contract", "suite member", "child closure"),
    },
    {
        "route_id": "skillguard.route.fixture-test.v1",
        "route_node_id": "fixture-test",
        "command_family": "fixture-test",
        "responsibility": "checker",
        "next_step": "Run fixture-test against an explicit fixture manifest.",
        "status": "current",
        "hints": ("fixture-test", "fixtures", "fixture-manifest"),
        "keywords": ("fixture", "fixture manifest", "expected fail", "expected block", "negative fixture"),
    },
    {
        "route_id": "skillguard.route.detect-stale-evidence.v1",
        "route_node_id": "detect-stale-evidence",
        "command_family": "detect-stale-evidence",
        "responsibility": "checker",
        "next_step": "Run detect-stale-evidence against current evidence-bearing JSON artifacts.",
        "status": "current",
        "hints": ("detect-stale-evidence", "stale-evidence", "freshness-check", "evidence-freshness"),
        "keywords": (
            "detect stale evidence",
            "stale evidence",
            "evidence freshness",
            "freshness check",
            "source fingerprint",
            "route version",
        ),
    },
    {
        "route_id": "skillguard.route.review-checker-change.v1",
        "route_node_id": "review-checker-change",
        "command_family": "review-checker-change",
        "responsibility": "reviewer",
        "next_step": "Run review-checker-change against the approved checker-change baseline and current evidence metadata.",
        "status": "current",
        "hints": ("review-checker-change", "checker-change", "checker-baseline", "checker-review"),
        "keywords": (
            "review checker change",
            "checker change",
            "checker baseline",
            "checker binding",
            "validation drift",
            "review validation change",
            "stale checker evidence",
        ),
    },
    {
        "route_id": "skillguard.route.check-maintenance-record.v1",
        "route_node_id": "check-maintenance-record",
        "command_family": "check-maintenance-record",
        "responsibility": "checker",
        "next_step": "Run check-maintenance-record against a current maintenance record JSON artifact.",
        "status": "current",
        "hints": ("check-maintenance-record", "maintenance-record", "record-schema", "maintenance-schema"),
        "keywords": (
            "check maintenance record",
            "maintenance record schema",
            "record schema",
            "canonical maintenance schema",
            "validate maintenance record",
            "rejected former maintenance record",
        ),
    },
    {
        "route_id": "skillguard.route.make-closure.v1",
        "route_node_id": "make-closure",
        "command_family": "make-closure",
        "responsibility": "closure",
        "next_step": "Run make-closure with current reports and direct evidence references.",
        "status": "current",
        "hints": ("make-closure", "closure", "closure-report"),
        "keywords": ("make closure", "closure report", "closure record", "current evidence", "close with evidence"),
    },
    {
        "route_id": "skillguard.route.self-check.v1",
        "route_node_id": "self-check",
        "command_family": "self-check",
        "responsibility": "checker",
        "next_step": "Run self-check against the SkillGuard skill target.",
        "status": "current",
        "hints": ("self-check", "repository-self-check", "skillguard-self-check"),
        "keywords": ("self check", "self-check", "skillguard repository", "public boundary", "command boundary"),
    },
    {
        "route_id": "skillguard.route.inventory.v1",
        "route_node_id": "inventory",
        "command_family": "inventory",
        "responsibility": "inventory",
        "next_step": "Run inventory against the target path.",
        "status": "current",
        "hints": ("inventory", "file-inventory", "repository-inventory"),
        "keywords": ("inventory", "list files", "repository inventory", "file listing", "path inventory"),
    },
)
DETECT_STALE_EXPECTED_ROUTE_VERSION = "5"
MAINTENANCE_MISSING_BLOCKER_CODES = {
    "invalid_evidence_path",
    "missing_evidence_artifact",
    "missing_evidence_metadata",
}
MAINTENANCE_FRESHNESS_STATES = {
    "fresh",
    "stale_or_missing",
    "missing",
}
CHECKER_CHANGE_SUITE_GUARD_SCHEMA = "skillguard.checker_change_suite_guard.v1"
CHECKER_CHANGE_SUITE_IMPACT_CLASSES = {
    "none",
    "checker_change",
    "suite_change",
    "checker_and_suite_change",
}
CHECKER_CHANGE_SUITE_GUARD_STATES = {
    "not_required",
    "fresh",
    "stale_or_missing",
    "missing",
    "invalid_selection",
    "inconsistent_selection",
}
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


def require_directory(path: Path, command: str, root: Path | None = None) -> None:
    if not path.exists():
        raise SkillGuardCliError(command, f"target directory does not exist: {public_relative_path(path, root)}", "missing_file")
    if not path.is_dir():
        raise SkillGuardCliError(command, f"target is not a directory: {public_relative_path(path, root)}", "validation_error")


def resolve_skillguard_self_layout_path(path_text: str | Path) -> Path:
    normalized = str(path_text).replace("\\", "/")
    root = repository_root().resolve()
    current_skill_root = skill_root().resolve()
    source_layout_prefix = f".agents/skills/{current_skill_root.name}"
    installed_skill_layout = current_skill_root.parent.name == "skills" and current_skill_root.parent.parent.name == ".codex"
    if installed_skill_layout and (normalized == ".agents/skills" or normalized.startswith(".agents/skills/")):
        suffix = normalized[len(".agents/skills") :].lstrip("/")
        return ensure_under_root(current_skill_root.parent / suffix, root)
    if (root == current_skill_root or installed_skill_layout) and (
        normalized == source_layout_prefix or normalized.startswith(f"{source_layout_prefix}/")
    ):
        suffix = normalized[len(source_layout_prefix) :].lstrip("/")
        return ensure_under_root(current_skill_root / suffix, root)
    return ensure_under_root(path_text, root)


def resolve_target_argument(path_text: str | Path, root: Path | None = None) -> Path:
    if root is not None:
        return ensure_under_root(path_text, root)
    return resolve_skillguard_self_layout_path(path_text)


def resolve_check_target_binding(
    command: str,
    target_text: str | Path,
    repository_root_text: str | Path | None = None,
) -> tuple[Path, Path, Path, dict[str, Any]]:
    """Resolve one canonical repository/member pair without retry or inference.

    The returned roots are ``(repository_root, member_root, report_root)``.
    ``report_root`` preserves repository-relative labels for embedded self
    checks while the binding projection remains the sole compilation and
    reference authority.
    """

    configured_root = canonical_filesystem_path(repository_root())
    configured_skill = canonical_filesystem_path(skill_root())
    normalized_target = str(target_text).replace("\\", "/").strip()
    explicit_repository = repository_root_text is not None

    if explicit_repository:
        canonical_root = canonical_filesystem_path(Path(str(repository_root_text)))
        if not canonical_root.is_dir():
            raise SkillGuardCliError(
                command,
                f"--repository-root is missing or not a directory: {repository_root_text}",
                "missing_file",
            )
        candidate = Path(target_text)
        if not candidate.is_absolute():
            candidate = canonical_root / candidate
        member_root = canonical_filesystem_path(candidate)
        report_root = canonical_root
        binding_mode = "explicit_repository"
    elif normalized_target in {".", "./"}:
        canonical_root = canonical_filesystem_path(Path.cwd())
        member_root = canonical_root
        report_root = canonical_root
        binding_mode = "standalone_dot"
    else:
        try:
            member_root = resolve_target_argument(target_text)
        except ValueError as exc:
            raise SkillGuardCliError(
                command,
                "--repository-root is required for a non-self target; a standalone skill must be checked from its own directory with --target .",
                "target_binding_invalid",
            ) from exc
        if member_root.resolve() == configured_skill:
            canonical_root = configured_root
            binding_mode = "skillguard_self"
        else:
            raise SkillGuardCliError(
                command,
                "--repository-root is required for a non-self target; a standalone skill must be checked from its own directory with --target .",
                "target_binding_invalid",
            )
        report_root = configured_root

    try:
        member_root_path = physical_relative_path(
            member_root, canonical_root
        ).as_posix()
    except ValueError as exc:
        raise SkillGuardCliError(
            command,
            "--target must resolve inside the declared canonical --repository-root",
            "target_binding_invalid",
        ) from exc

    binding = {
        "schema_version": EXTERNAL_TARGET_BINDING_SCHEMA_VERSION,
        "artifact_type": "skillguard_external_target_binding",
        "binding_mode": binding_mode,
        "repository_root_role": "canonical_repository_root",
        "member_root_role": "target_skill_member_root",
        "member_root_path": member_root_path or ".",
        "repository_root_explicit": explicit_repository,
        "repository_root_verified": canonical_root.is_dir(),
        "member_root_verified": member_root.is_dir(),
        "member_within_repository": True,
        "fallback_used": False,
        "claim_boundary": (
            "This projection proves only the declared canonical repository/member path binding. "
            "It stores no absolute local path and does not prove contract, static, execution, installation, or release success."
        ),
    }
    schema = load_json(schema_path(EXTERNAL_TARGET_BINDING_SCHEMA_NAME))
    schema_failures = validate_schema_subset(binding, schema)
    if schema_failures:
        raise SkillGuardCliError(
            command,
            "generated target binding does not satisfy the current binding schema: "
            + "; ".join(schema_failures),
            "target_binding_invalid",
        )
    return canonical_root, member_root, report_root, binding


def is_installed_skill_projection(target: Path) -> bool:
    """Return whether *target* is one direct member of a .codex/skills tree."""

    resolved = target.resolve()
    return (
        resolved.parent.name == "skills"
        and resolved.parent.parent.name == ".codex"
    )


def control_root_for(target: Path, root: Path | None = None) -> Path:
    return ensure_under_root(target / ".skillguard", root)


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


def validation_registry_hash(value: dict[str, Any]) -> str:
    stable = json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()[:16]


def validation_registry_blocker_category(blocker_code: str, blocker_class: str) -> str:
    if blocker_code in VALIDATION_REGISTRY_GENERATION_BLOCKER_CODES:
        return "blocked_generation_request"
    if blocker_code in VALIDATION_REGISTRY_INVALID_INPUT_CODES or blocker_class == "routing_config_error":
        return "invalid_input"
    if blocker_code in VALIDATION_REGISTRY_CONFLICT_CODES:
        return "routing_conflict"
    return "blocker"


def validation_registry_structured_blockers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_field in VALIDATION_REGISTRY_STRUCTURED_BLOCKER_FIELDS:
        value = payload.get(source_field)
        if not isinstance(value, list):
            continue
        for index, item in enumerate(value):
            if not isinstance(item, dict):
                continue
            blocker_code = str(item.get("blocker_code") or item.get("code") or f"{source_field}_{index + 1}")
            blocker_class = str(item.get("blocker_class") or "validation_blocker")
            message = str(
                item.get("message")
                or item.get("stale_reason")
                or item.get("failure_reason")
                or item.get("recommended_resolution")
                or item.get("recommended_owner_action")
                or item.get("recommended_repair_action")
                or blocker_code
            )[:300]
            row = {
                "blocker_class": blocker_class,
                "blocker_code": blocker_code,
                "blocker_category": validation_registry_blocker_category(blocker_code, blocker_class),
                "message": message,
                "source_field": source_field,
                "field_path": str(item.get("field_path") or ""),
                "conflicting_fields": item.get("conflicting_fields", [])
                if isinstance(item.get("conflicting_fields"), list)
                else [],
                "recommended_resolution": str(
                    item.get("recommended_resolution")
                    or item.get("recommended_owner_action")
                    or item.get("recommended_repair_action")
                    or ""
                )[:300],
            }
            if isinstance(item.get("public_context"), dict):
                row["public_context"] = item["public_context"]
            rows.append(row)
    return rows


def validation_registry_blocker_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = validation_registry_structured_blockers(payload)
    structured_messages = {row.get("message") for row in rows}
    blockers = payload.get("blockers", [])
    if isinstance(blockers, list):
        for index, item in enumerate(blockers):
            if not isinstance(item, str) or not item.strip():
                continue
            message = item.strip()[:300]
            if message in structured_messages:
                continue
            rows.append(
                {
                    "blocker_class": "text_blocker",
                    "blocker_code": f"text_blocker_{index + 1}",
                    "blocker_category": "blocker",
                    "message": message,
                    "source_field": "blockers",
                    "field_path": "",
                    "conflicting_fields": [],
                    "recommended_resolution": "Inspect the owning command output and repair the blocker before accepting this result.",
                }
            )
    return rows


def validation_registry_evidence_rows(
    payload: dict[str, Any],
    blocker_rows: list[dict[str, Any]],
    post_generation_checks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    existing = payload.get("evidence", [])
    if isinstance(existing, list):
        for index, item in enumerate(existing):
            if not isinstance(item, dict):
                continue
            row = dict(item)
            evidence_id = str(row.get("evidence_id") or f"evidence-{index + 1}")
            row["evidence_id"] = evidence_id
            rows.append(row)
            seen_ids.add(evidence_id)

    for blocker in blocker_rows:
        blocker_code = str(blocker.get("blocker_code") or "blocker")
        evidence_id = f"blocker:{blocker_code}"
        if evidence_id in seen_ids:
            continue
        rows.append(
            {
                "evidence_id": evidence_id,
                "kind": "blocker_evidence",
                "fresh": True,
                "blocker_class": blocker.get("blocker_class"),
                "blocker_code": blocker_code,
                "blocker_category": blocker.get("blocker_category"),
                "summary": blocker.get("message"),
                "source_path": str(payload.get("command") or ""),
            }
        )
        seen_ids.add(evidence_id)

    for check in post_generation_checks:
        check_id = str(check.get("check_id") or "post-generation-check")
        evidence_id = f"post-generation:{check_id}"
        if evidence_id in seen_ids:
            continue
        rows.append(
            {
                "evidence_id": evidence_id,
                "kind": "command_validation",
                "fresh": True,
                "summary": (
                    f"{check.get('command')} for {check.get('artifact_path')} "
                    f"reported {check.get('reported_decision') or check.get('status')}."
                ),
                "source_path": str(check.get("artifact_path") or ""),
                "status": str(check.get("status") or ""),
                "reported_decision": str(check.get("reported_decision") or ""),
            }
        )
        seen_ids.add(evidence_id)
    return rows


def validation_registry_check_rows(
    checks: list[dict[str, Any]],
    blocker_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    blocker_codes = [str(row.get("blocker_code")) for row in blocker_rows if row.get("blocker_code")]
    rows: list[dict[str, Any]] = []
    for index, check in enumerate(checks):
        if not isinstance(check, dict):
            continue
        check_id = str(check.get("check_id") or f"check-{index + 1}")
        status = str(check.get("status") or "")
        evidence_ids = [
            str(item)
            for item in check.get("evidence_ids", [])
            if isinstance(check.get("evidence_ids"), list) and str(item)
        ]
        rows.append(
            {
                "validation_id": check_id,
                "validation_kind": "check",
                "status": status,
                "required": bool(check.get("required", False)),
                "evidence_ids": evidence_ids,
                "blocker_codes": blocker_codes if status == "block" else [],
                "source_field": "checks",
            }
        )
    return rows


def validation_registry_post_generation_rows(
    post_generation_checks: list[dict[str, Any]],
    blocker_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    blocker_codes = [str(row.get("blocker_code")) for row in blocker_rows if row.get("blocker_code")]
    rows: list[dict[str, Any]] = []
    for index, check in enumerate(post_generation_checks):
        if not isinstance(check, dict):
            continue
        check_id = str(check.get("check_id") or f"post-generation-check-{index + 1}")
        status = str(check.get("status") or "")
        rows.append(
            {
                "validation_id": check_id,
                "validation_kind": "post_generation_check",
                "status": status,
                "required": True,
                "command": str(check.get("command") or ""),
                "artifact_path": str(check.get("artifact_path") or ""),
                "reported_decision": str(check.get("reported_decision") or ""),
                "reason": str(check.get("reason") or ""),
                "evidence_ids": [f"post-generation:{check_id}"],
                "blocker_codes": blocker_codes if status == "block" else [],
                "source_field": "post_generation_checks",
            }
        )
    return rows


def validation_registry_status_summary(rows: list[dict[str, Any]], evidence_rows: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "validation_count": len(rows),
        "evidence_count": len(evidence_rows),
        "status_counts": status_counts,
    }


def apply_validation_registry(payload: dict[str, Any]) -> None:
    command = str(payload.get("command") or "")
    if command not in VALIDATION_REGISTRY_COMMANDS:
        return
    checks = [dict(item) for item in payload.get("checks", []) if isinstance(item, dict)]
    post_generation_checks = [
        dict(item) for item in payload.get("post_generation_checks", []) if isinstance(item, dict)
    ]
    blocker_rows = validation_registry_blocker_rows(payload)
    evidence_rows = validation_registry_evidence_rows(payload, blocker_rows, post_generation_checks)
    validation_rows = [
        *validation_registry_check_rows(checks, blocker_rows),
        *validation_registry_post_generation_rows(post_generation_checks, blocker_rows),
    ]
    seed = {
        "command": command,
        "decision": str(payload.get("decision") or ""),
        "validation_ids": [row.get("validation_id") for row in validation_rows],
        "blocker_codes": [row.get("blocker_code") for row in blocker_rows],
        "evidence_ids": [row.get("evidence_id") for row in evidence_rows],
    }
    source_fields = ["checks", "evidence", "blockers"]
    if post_generation_checks:
        source_fields.append("post_generation_checks")
    if "checker_change_suite_guard" in payload:
        source_fields.append("checker_change_suite_guard")
    if payload.get("checker_change_suite_guard_blockers"):
        source_fields.append("checker_change_suite_guard_blockers")
    payload["validation_registry_schema_version"] = VALIDATION_REGISTRY_SCHEMA_VERSION
    payload["validation_registry"] = {
        "schema_version": VALIDATION_REGISTRY_SCHEMA_VERSION,
        "registry_id": f"{command}:{validation_registry_hash(seed)}",
        "command": command,
        "decision": str(payload.get("decision") or ""),
        "source_of_truth_for": source_fields,
        "validation_rows": validation_rows,
        "evidence": evidence_rows,
        "blocker_evidence": blocker_rows,
        "summary": validation_registry_status_summary(validation_rows, evidence_rows),
    }
    payload["checks"] = checks
    payload["evidence"] = evidence_rows


def write_and_exit(payload: dict[str, Any], output: str | None = None) -> int:
    apply_validation_registry(payload)
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




def canonical_json_hash(value: Any, length: int | None = None) -> str:
    stable = json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    digest = hashlib.sha256(stable.encode("utf-8")).hexdigest().upper()
    return digest[:length] if length is not None else digest






def require_skill_target(target: Path, command: str, root: Path | None = None) -> None:
    require_directory(target, command, root)
    if not (target / "SKILL.md").is_file():
        raise SkillGuardCliError(command, f"target skill is missing SKILL.md: {public_relative_path(target, root)}", "missing_file")




















def check_json_schema(argv: list[str]) -> int:
    parser = JsonArgumentParser(prog="skillguard.py check-json-schema", description="Check an input JSON file against a schema file.")
    parser.add_argument("--schema", required=True, help="Schema JSON file under the repository root.")
    parser.add_argument("--input", required=True, help="Input JSON file under the repository root.")
    parser.add_argument("--output", default="-", help="Output report path under the skill root, or '-' for stdout.")
    args = parser.parse_args(argv)
    schema_file = ensure_under_root(args.schema)
    input_path = ensure_under_root(args.input)
    schema = load_json(schema_file)
    data = load_json(input_path)
    failures = validate_schema_subset(data, schema)
    payload = base_result("check-json-schema", public_relative_path(input_path))
    payload["decision"] = "pass" if not failures else "fail"
    payload["checks"] = [
        {
            "check_id": "check-json-schema:json-load",
            "name": "Input and schema JSON load",
            "required": True,
            "status": "pass",
            "summary": "Loaded both files with the Python standard library json module.",
        },
        {
            "check_id": "check-json-schema:schema-subset",
            "name": "Standard-library schema subset check",
            "required": True,
            "status": payload["decision"],
            "summary": "Checked required fields, basic types, const, enum, minLength, minimum, and additionalProperties where declared.",
        },
    ]
    payload["evidence"] = [
        {
            "evidence_id": "input-json",
            "kind": "parser_output",
            "fresh": True,
            "summary": f"Parsed {public_relative_path(input_path)}; sha256={file_sha256(input_path)}.",
            "source_path": public_relative_path(input_path),
        },
        {
            "evidence_id": "schema-json",
            "kind": "parser_output",
            "fresh": True,
            "summary": f"Parsed {public_relative_path(schema_file)}; sha256={file_sha256(schema_file)}.",
            "source_path": public_relative_path(schema_file),
        },
    ]
    payload["failures"] = failures
    return write_and_exit(payload, args.output)


def check_contract(argv: list[str]) -> int:
    parser = JsonArgumentParser(prog="skillguard.py check-contract", description="Check the target's single current SkillGuard contract authority.")
    parser.add_argument("--target", required=True, help="Target skill member directory. External members are resolved only inside --repository-root; standalone '.' binds the current directory.")
    parser.add_argument("--repository-root", help="Canonical repository root for an external target member. Repository-relative contract paths resolve only from this root.")
    parser.add_argument("--output", default="-", help="Output report path under the skill root, or '-' for stdout.")
    args = parser.parse_args(argv)
    canonical_root, target, report_root, target_binding = resolve_check_target_binding(
        "check-contract",
        args.target,
        args.repository_root,
    )
    require_skill_target(target, "check-contract", report_root)
    from skillguard_v2.runtime_authority import (
        AUTHORITY_BLOCKED,
        AUTHORITY_CURRENT,
        resolve_runtime_authority,
    )

    authority = resolve_runtime_authority(target)
    if authority.authority == AUTHORITY_BLOCKED:
        payload = base_result("check-contract", public_relative_path(target, report_root))
        payload["target_binding"] = target_binding
        payload["contract_path"] = authority.compiled_contract_path
        payload["authority_decision"] = authority.authority
        payload["checks"] = []
        payload["evidence"] = []
        payload["files_inspected"] = []
        payload["failures"] = [
            f"{finding.code}: {finding.path}: {finding.message}"
            for finding in authority.findings
        ]
        payload["blockers"] = list(authority.blockers)
        payload["decision"] = "block"
        payload["claim_boundary"] = authority.claim_boundary
        return write_and_exit(payload, args.output)
    if authority.authority == AUTHORITY_CURRENT:
        if is_installed_skill_projection(target):
            source_path = target / ".skillguard" / "contract-source.json"
            compiled_path = target / ".skillguard" / "compiled-contract.json"
            manifest_path = target / ".skillguard" / "check-manifest.json"
            contract = load_json(compiled_path, canonical_root)
            manifest = load_json(manifest_path, canonical_root)
            payload = base_result("check-contract", public_relative_path(target, report_root))
            payload["target_binding"] = target_binding
            payload["contract_path"] = public_relative_path(compiled_path, report_root)
            payload["contract_hash"] = str(contract.get("contract_hash") or "")
            payload["manifest_hash"] = str(manifest.get("manifest_hash") or "")
            payload["authority_decision"] = authority.authority
            payload["verification_scope"] = "installed-current-authority"
            payload["checks"] = [
                {
                    "check_id": "check-contract:installed-current-authority",
                    "name": "Current installed contract trio authority",
                    "required": True,
                    "status": "pass",
                    "summary": (
                        "Validated the installed source, compiled contract, and exact manifest "
                        "through the current runtime-authority owner without pretending that "
                        "source-only model files are installed."
                    ),
                }
            ]
            payload["evidence"] = [
                {
                    "evidence_id": "installed-current-contract-trio",
                    "kind": "installed_runtime_authority",
                    "fresh": True,
                    "summary": (
                        f"Checked installed contract hash {contract.get('contract_hash', '')} "
                        f"and manifest hash {manifest.get('manifest_hash', '')}."
                    ),
                    "source_path": public_relative_path(compiled_path, report_root),
                }
            ]
            payload["files_inspected"] = [
                checked_file(source_path, "json", report_root),
                checked_file(compiled_path, "json", report_root),
                checked_file(manifest_path, "json", report_root),
            ]
            payload["failures"] = []
            payload["blockers"] = []
            payload["decision"] = "pass"
            payload["claim_boundary"] = (
                "This installed check proves the current contract trio's structure, schema, "
                "internal hashes, and absence of former runtime authority. Exact canonical-to-installed "
                "content parity remains owned by the installation receipt; target checks have not run."
            )
            return write_and_exit(payload, args.output)

        from skillguard_v2.contract_compiler import compile_skill_contract

        result = compile_skill_contract(
            target,
            repository_root=canonical_root,
            write=False,
        )
        contract = result.compiled_contract if isinstance(result.compiled_contract, dict) else {}
        failures = [
            f"{finding.code}: {finding.path}: {finding.message}"
            for finding in result.findings
        ]
        compiled_path = target / ".skillguard" / "compiled-contract.json"
        manifest_path = target / ".skillguard" / "check-manifest.json"
        payload = base_result("check-contract", public_relative_path(target, report_root))
        payload["target_binding"] = target_binding
        payload["contract_path"] = public_relative_path(compiled_path, report_root)
        payload["contract_hash"] = str(contract.get("contract_hash") or "")
        payload["authority_decision"] = authority.authority
        payload["checks"] = [
            {
                "check_id": "check-contract:current-authority",
                "name": "Current source, compiled contract, and exact manifest authority",
                "required": True,
                "status": "pass" if result.ok else "fail",
                "summary": "Recompiled from the portable target root and checked deterministic generated parity.",
            }
        ]
        payload["evidence"] = [
            {
                "evidence_id": "current-compiled-contract",
                "kind": "compiled_contract",
                "fresh": bool(result.ok),
                "summary": f"Checked current contract hash {contract.get('contract_hash', '')}.",
                "source_path": public_relative_path(compiled_path, report_root),
            }
        ]
        payload["files_inspected"] = [
            checked_file(target / ".skillguard" / "contract-source.json", "json", report_root),
            checked_file(compiled_path, "json", report_root),
            checked_file(manifest_path, "json", report_root),
        ]
        payload["failures"] = failures
        payload["blockers"] = []
        payload["decision"] = "pass" if not failures else "fail"
        payload["claim_boundary"] = (
            "A current contract check proves source/compiled/manifest structure and parity only; it does not prove target execution depth."
        )
        return write_and_exit(payload, args.output)
    raise SkillGuardCliError(
        "check-contract",
        f"unsupported runtime authority: {authority.authority}",
        "runtime_authority_blocked",
    )
















def check_depth(argv: list[str]) -> int:
    parser = JsonArgumentParser(prog="skillguard.py check-depth", description="Check deep target-specific coverage under the single current authority.")
    parser.add_argument("--target", required=True, help="Target skill directory.")
    parser.add_argument("--target-root", help="Explicit root for read-only external target checks.")
    parser.add_argument("--output", default="-", help="Output report path under the skill root, or '-' for stdout.")
    args = parser.parse_args(argv)
    target_root = Path(args.target_root).resolve() if args.target_root else None
    if target_root is not None and not target_root.is_dir():
        raise SkillGuardCliError("check-depth", f"--target-root is missing or not a directory: {args.target_root}", "missing_file")
    target_candidate = resolve_target_argument(args.target, target_root)
    current_source = target_candidate / ".skillguard" / "contract-source.json"
    if not target_candidate.is_dir():
        raise SkillGuardCliError(
            "check-depth",
            "--target must be a current skill directory; former contract-file targets are not executable authority",
            "runtime_authority_blocked",
        )
    authority = None
    if target_candidate.is_dir():
        from skillguard_v2.runtime_authority import (
            AUTHORITY_BLOCKED,
            AUTHORITY_CURRENT,
            resolve_runtime_authority,
        )

        authority = resolve_runtime_authority(target_candidate)
        if authority.authority == AUTHORITY_BLOCKED:
            payload = base_result("check-depth", public_relative_path(target_candidate, target_root))
            payload["contract_path"] = public_relative_path(current_source, target_root) if current_source.is_file() else ""
            payload["authority_decision"] = authority.authority
            payload["depth_classification"] = "blocked"
            payload["coverage_rows"] = []
            payload["checks"] = [
                {
                    "check_id": "check-depth:runtime-authority",
                    "name": "Singular runtime authority",
                    "required": True,
                    "status": "block",
                    "summary": "Runtime authority is incomplete, ambiguous, stale, or contains a retired residual.",
                }
            ]
            payload["evidence"] = []
            payload["failures"] = [
                f"{finding.code}: {finding.path}: {finding.message}"
                for finding in authority.findings
            ]
            payload["blockers"] = list(authority.blockers)
            payload["decision"] = "block"
            payload["claim_boundary"] = authority.claim_boundary
            return write_and_exit(payload, args.output)
    if (
        target_candidate.is_dir()
        and authority is not None
        and authority.authority == AUTHORITY_CURRENT
    ):
        authority_root = target_root or repository_root().resolve()
        contract = load_json(target_candidate / ".skillguard" / "compiled-contract.json", authority_root)
        manifest = load_json(target_candidate / ".skillguard" / "check-manifest.json", authority_root)
        depth_profile = contract.get("depth_profile") if isinstance(contract, dict) else None
        failures: list[str] = []
        if not isinstance(depth_profile, dict):
            failures.append("depth_profile_missing: current contract does not declare universal execution-depth coverage")
        coverage_rows = []
        if isinstance(depth_profile, dict):
            coverage_rows = [
                {
                    "dimension_id": row.get("dimension_id"),
                    "required": bool(row.get("required", False)),
                    "minimum_coverage": row.get("minimum_coverage"),
                    "obligation_count": len(row.get("obligation_ids", []))
                    if isinstance(row.get("obligation_ids"), list)
                    else 0,
                    "important_obligation_count": len(row.get("important_obligation_ids", []))
                    if isinstance(row.get("important_obligation_ids"), list)
                    else 0,
                }
                for row in depth_profile.get("dimensions", [])
                if isinstance(row, dict)
            ]
        payload = base_result("check-depth", public_relative_path(target_candidate, target_root))
        payload["contract_path"] = public_relative_path(current_source, target_root)
        payload["authority_decision"] = authority.authority
        payload["contract_hash"] = str(contract.get("contract_hash", ""))
        payload["target_contract_hash"] = str(contract.get("contract_hash", ""))
        payload["manifest_hash"] = str(manifest.get("manifest_hash", ""))
        payload["contract_source_sha256"] = file_sha256(current_source)
        payload["depth_classification"] = "contract-depth-pass" if not failures else "shallow-contract"
        payload["coverage_rows"] = coverage_rows
        payload["checks"] = [
            {
                "check_id": "check-depth:current-authority",
                "name": "Current persisted contract authority",
                "required": True,
                "status": "pass",
                "summary": "Consumed the validated current contract trio; compilation parity remains owned by its separate compile owner.",
            },
            {
                "check_id": "check-depth:current-profile",
                "name": "Universal execution-depth profile",
                "required": True,
                "status": "pass" if isinstance(depth_profile, dict) and not failures else "fail",
                "summary": "Checked native-route authority, exact declared-check inventory, execution ownership, receipt reconciliation, and closure bindings.",
            },
        ]
        payload["evidence"] = [
            {
                "evidence_id": "current-depth-contract-source",
                "kind": "current_contract_authority",
                "fresh": True,
                "summary": f"Consumed current contract authority; contract_hash={contract.get('contract_hash', '')}.",
                "source_path": public_relative_path(current_source, target_root),
            }
        ]
        payload["failures"] = failures
        payload["blockers"] = []
        payload["decision"] = "pass" if not failures else "fail"
        payload["claim_boundary"] = (
            "A check-depth pass proves the sole current contract/profile depth and native-route bindings only. "
            "It does not prove that target work ran deeply; that requires a current target execution-depth receipt consumed by closure."
        )
        return write_and_exit(payload, args.output)
    raise SkillGuardCliError(
        "check-depth",
        f"unsupported runtime authority: {authority.authority if authority else 'blocked'}",
        "runtime_authority_blocked",
    )


README_RELEASE_HEADING_PAIRS = (
    ("## Why It Exists", "## \u4e3a\u4ec0\u4e48\u9700\u8981\u5b83"),
    ("## What It Can Do", "## \u5b83\u73b0\u5728\u80fd\u505a\u4ec0\u4e48"),
    ("## Current Status", "## \u5f53\u524d\u72b6\u6001"),
    ("## Command Surface", "## \u547d\u4ee4\u9762"),
    ("## Runtime Contract Executor", "## \u8fd0\u884c\u5408\u540c\u6267\u884c\u5668"),
    ("## Native-Owned Integration", "## \u76ee\u6807\u539f\u751f\u8def\u7ebf"),
    ("## Typical Workflows", "## \u5e38\u89c1\u5de5\u4f5c\u6d41"),
    ("## README And Release Gates", "## README \u548c\u53d1\u5e03\u95e8\u7981"),
    ("## Validation", "## \u9a8c\u8bc1"),
    ("## What SkillGuard Is Not", "## SkillGuard \u4e0d\u662f\u4ec0\u4e48"),
    ("## Public Boundary", "## \u516c\u5f00\u8fb9\u754c"),
    ("## Repository Layout", "## \u4ed3\u5e93\u7ed3\u6784"),
    ("## Release History", "## \u53d1\u5e03\u5386\u53f2"),
    ("## License", "## \u8bb8\u53ef\u8bc1"),
)


README_MODEL_REQUIRED_SECTIONS = {
    "Repository Fact Ledger": (
        "product surface",
        "entry points",
        "release/version facts",
        "privacy-sensitive exclusions",
    ),
    "Capability Claim Matrix": (
        "claim",
        "problem",
        "mechanism",
        "evidence",
        "warrant",
        "reader value",
        "boundary",
        "objection",
    ),
    "Narrative Structure Plan": (
        "first-screen promise",
        "section order",
        "visual proof placement",
        "quick-start placement",
        "public/private boundary placement",
    ),
    "Gap Ledger": (
        "unsupported claims",
        "missing evidence",
        "maturity",
        "privacy risks",
    ),
}


def markdown_section_body(text: str, heading: str) -> str:
    pattern = re.compile(rf"(?ms)^##+\s+{re.escape(heading)}\s*$\n(?P<body>.*?)(?=^##+\s+|\Z)")
    match = pattern.search(text)
    return match.group("body").strip() if match else ""


def readme_model_evidence_failures(model_text: str, version_text: str) -> list[str]:
    failures: list[str] = []
    model_lower = model_text.lower()
    for term in ("logicguard", "capability model", "mechanism", "evidence", "boundary", "objection"):
        if term not in model_lower:
            failures.append(f"missing-readme-model-evidence: readme_model_evidence.md missing {term!r}")

    current_version = version_text.strip()
    if current_version:
        current_tag = f"v{current_version}"
        version_mentions = sorted(set(re.findall(r"\bv\d+\.\d+\.\d+\b", model_text)))
        if current_tag not in version_mentions:
            failures.append(
                f"stale-readme-model-evidence: readme_model_evidence.md must explicitly name current release `{current_tag}`"
            )
        stale_mentions = [item for item in version_mentions if item != current_tag]
        if stale_mentions:
            failures.append(
                "stale-readme-model-evidence: readme_model_evidence.md references non-current release tag(s): "
                + ", ".join(stale_mentions)
            )

    for heading, required_terms in README_MODEL_REQUIRED_SECTIONS.items():
        body = markdown_section_body(model_text, heading)
        if not body:
            failures.append(f"missing-readme-model-artifact: readme_model_evidence.md missing section `## {heading}`")
            continue
        body_lower = body.lower()
        if len([line for line in body.splitlines() if line.strip()]) < 2:
            failures.append(f"missing-readme-model-artifact: section `## {heading}` must contain concrete model rows")
        for term in required_terms:
            if term.lower() not in body_lower:
                failures.append(
                    f"missing-readme-model-artifact: section `## {heading}` missing required term {term!r}"
                )
    return failures


def read_text_if_file(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def pyproject_version_value(text: str, key: str) -> str:
    match = re.search(rf"(?m)^{re.escape(key)}\s*=\s*\"([^\"]+)\"", text)
    return match.group(1) if match else ""


def pyproject_project_name(text: str) -> str:
    project_match = re.search(r"(?ms)^\[project\]\s*$\n(?P<body>.*?)(?=^\[|\Z)", text)
    if project_match is None:
        return ""
    name_match = re.search(r'(?m)^name\s*=\s*"([^\"]+)"', project_match.group("body"))
    return name_match.group(1).strip() if name_match else ""


def check_readme_release(argv: list[str]) -> int:
    parser = JsonArgumentParser(
        prog="skillguard.py check-readme-release",
        description="Check SkillGuard README release gates for bilingual, hero, model, public-boundary, and version evidence.",
    )
    parser.add_argument("--repo", default=".", help="Repository root to check. Relative paths resolve from the caller's current working directory.")
    parser.add_argument("--output", default="-", help="Output report path under the skill root, or '-' for stdout.")
    args = parser.parse_args(argv)

    repo_candidate = Path(args.repo)
    if not repo_candidate.is_absolute():
        repo_candidate = Path.cwd() / repo_candidate
    repo = repo_candidate.resolve()
    if repo == Path(repo.anchor).resolve():
        raise ValueError("--repo must identify a repository directory, not a filesystem root")
    require_directory(repo, "check-readme-release", root=repo)
    member_paths: dict[str, Path] = {}
    escaped_members: list[str] = []
    for relative in (
        "README.md",
        "VERSION",
        "pyproject.toml",
        "CHANGELOG.md",
        "assets/readme-hero/hero.png",
        "assets/readme-hero/hero_prompt.md",
        "assets/readme-hero/hero_design_note.md",
        "assets/readme-hero/readme_model_evidence.md",
        ".agents/skills/skillguard/SKILL.md",
    ):
        try:
            member_paths[relative] = ensure_under_root(repo / relative, repo)
        except ValueError:
            escaped_members.append(relative)
    readme_path = member_paths.get("README.md", repo / "__blocked_readme__")
    version_path = member_paths.get("VERSION", repo / "__blocked_version__")
    pyproject_path = member_paths.get("pyproject.toml", repo / "__blocked_pyproject__")
    changelog_path = member_paths.get("CHANGELOG.md", repo / "__blocked_changelog__")
    hero_path = member_paths.get("assets/readme-hero/hero.png", repo / "__blocked_hero__")
    hero_prompt_path = member_paths.get("assets/readme-hero/hero_prompt.md", repo / "__blocked_hero_prompt__")
    hero_design_path = member_paths.get("assets/readme-hero/hero_design_note.md", repo / "__blocked_hero_design__")
    model_evidence_path = member_paths.get(
        "assets/readme-hero/readme_model_evidence.md", repo / "__blocked_model_evidence__"
    )
    skill_entrypoint_path = member_paths.get(
        ".agents/skills/skillguard/SKILL.md", repo / "__blocked_skill_entrypoint__"
    )
    required_paths = [
        readme_path,
        version_path,
        pyproject_path,
        changelog_path,
        hero_path,
        hero_prompt_path,
        hero_design_path,
        model_evidence_path,
    ]

    payload = base_result("check-readme-release", ".")
    payload["claim_boundary"] = (
        "This README release gate checks the current local README, version files, hero evidence, model evidence, "
        "command-surface wording, and public-safety scans. It does not prove package publication, GitHub release creation, "
        "external links beyond local path checks, or future AI behavior."
    )
    failures: list[str] = []
    blockers: list[str] = []
    files_inspected: list[dict[str, Any]] = []
    public_safety: list[dict[str, Any]] = []
    unsafe_claim_findings: list[dict[str, Any]] = []

    before_failures, before_blockers = len(failures), len(blockers)
    blockers.extend(f"target-member-path-escape:{relative}" for relative in escaped_members)
    readme_identity_text = read_text_if_file(readme_path)
    pyproject_identity_text = read_text_if_file(pyproject_path)
    target_identity_ok = (
        pyproject_project_name(pyproject_identity_text).casefold() == "skillguard"
        and bool(re.search(r"(?m)^# SkillGuard\s*$", readme_identity_text))
        and skill_entrypoint_path.is_file()
    )
    if not target_identity_ok:
        blockers.append(
            "wrong_target_profile: check-readme-release accepts only a SkillGuard source repository; "
            "use the target repository's native release verifier or a declared target-local README contract"
        )
    append_check(
        payload,
        "check-readme-release:target-profile",
        "SkillGuard target profile",
        check_status(failures, blockers, before_failures, before_blockers),
        "Confirmed the authorized target is a SkillGuard source repository before applying SkillGuard-specific README rules.",
    )
    if blockers:
        payload["failures"] = failures
        payload["blockers"] = blockers
        payload["decision"] = "block"
        return write_and_exit(payload, args.output)

    before_failures, before_blockers = len(failures), len(blockers)
    for path in required_paths:
        if not path.is_file():
            failures.append(f"required README release file missing: {public_relative_path(path, repo)}")
        else:
            if path.suffix.lower() == ".png":
                files_inspected.append(
                    {
                        "path": public_relative_path(path, repo),
                        "kind": "image",
                        "sha256": file_sha256(path),
                        "byte_count": path.stat().st_size,
                    }
                )
            else:
                files_inspected.append(
                    checked_file(
                        path,
                        "markdown" if path.suffix.lower() == ".md" else "file",
                        root=repo,
                    )
                )
    append_check(
        payload,
        "check-readme-release:required-files",
        "README release files",
        check_status(failures, blockers, before_failures, before_blockers),
        "Checked README, version, changelog, hero image, hero notes, and README model evidence files.",
    )

    readme_text = read_text_if_file(readme_path)
    hero_prompt_text = read_text_if_file(hero_prompt_path)
    hero_design_text = read_text_if_file(hero_design_path)
    model_text = read_text_if_file(model_evidence_path)
    pyproject_text = read_text_if_file(pyproject_path)
    changelog_text = read_text_if_file(changelog_path)
    version_text = read_text_if_file(version_path).strip()

    before_failures, before_blockers = len(failures), len(blockers)
    if readme_text:
        if "English comes first; the second half is a full Chinese mirror." not in readme_text:
            failures.append("missing-bilingual-mirror: README is missing the English-first Chinese-mirror note")
        chinese_marker = "# SkillGuard \u4e2d\u6587\u8bf4\u660e"
        if chinese_marker not in readme_text:
            failures.append("missing-bilingual-mirror: README is missing the Chinese mirror section")
        elif readme_text.index(chinese_marker) <= readme_text.find("## Why It Exists"):
            failures.append("bilingual-drift: Chinese mirror must appear after the English section")
        for english_heading, chinese_heading in README_RELEASE_HEADING_PAIRS:
            if english_heading not in readme_text:
                failures.append(f"bilingual-drift: English heading missing from README mirror set: {english_heading}")
            if chinese_heading not in readme_text:
                failures.append(f"bilingual-drift: Chinese mirror heading missing for {english_heading}")
        if chinese_marker in readme_text:
            english_part = readme_text[: readme_text.index(chinese_marker)]
            chinese_part = readme_text[readme_text.index(chinese_marker) :]
            if len(chinese_part.splitlines()) < max(20, int(len(english_part.splitlines()) * 0.55)):
                failures.append("bilingual-drift: Chinese mirror is too short compared with the English section")
    append_check(
        payload,
        "check-readme-release:bilingual-mirror",
        "English-first Chinese mirror",
        check_status(failures, blockers, before_failures, before_blockers),
        "Checked the README language note, Chinese mirror section, paired headings, order, and mirror length.",
    )

    before_failures, before_blockers = len(failures), len(blockers)
    if readme_text:
        if readme_text.count("<!-- README HERO START -->") != 1 or readme_text.count("<!-- README HERO END -->") != 1:
            failures.append("missing-hero-evidence: README must contain exactly one hero block")
        if "./assets/readme-hero/hero.png" not in readme_text:
            failures.append("missing-hero-evidence: README hero block must reference ./assets/readme-hero/hero.png")
    if hero_path.is_file() and hero_path.stat().st_size < 10_000:
        failures.append("missing-hero-evidence: hero.png is too small to be a rendered concept hero image")
    prompt_lower = hero_prompt_text.lower()
    design_lower = hero_design_text.lower()
    if "text-to-image" not in prompt_lower:
        failures.append("invalid-hero-provenance: hero_prompt.md must state text-to-image generation")
    if "prompt" not in prompt_lower or "visual" not in prompt_lower:
        failures.append("missing-hero-evidence: hero_prompt.md must preserve a project-specific visual prompt")
    if "visual concept" not in design_lower or "core workflow" not in design_lower:
        failures.append("missing-hero-evidence: hero_design_note.md must record visual concept and core workflow evidence")
    deterministic_pattern = re.compile(r"(?i)\b(?:deterministic\s+svg|deterministic\s+html|deterministic\s+canvas|pillow\s+composition|canvas\s+composition)\b")
    for path, text in ((hero_prompt_path, hero_prompt_text), (hero_design_path, hero_design_text)):
        if text and deterministic_pattern.search(text):
            failures.append(f"invalid-hero-provenance: deterministic main hero provenance found in {public_relative_path(path, repo)}")
    append_check(
        payload,
        "check-readme-release:hero-provenance",
        "Text-to-image hero evidence",
        check_status(failures, blockers, before_failures, before_blockers),
        "Checked hero block count, renderable raster asset size, prompt evidence, design note, and deterministic-hero exclusions.",
    )

    before_failures, before_blockers = len(failures), len(blockers)
    failures.extend(readme_model_evidence_failures(model_text, version_text))
    append_check(
        payload,
        "check-readme-release:model-evidence",
        "README model evidence",
        check_status(failures, blockers, before_failures, before_blockers),
        "Checked for current-version LogicGuard-backed README model evidence, fact ledger, capability matrix, narrative plan, and gap ledger.",
    )

    before_failures, before_blockers = len(failures), len(blockers)
    pyproject_version = pyproject_version_value(pyproject_text, "version")
    baseline_version = pyproject_version_value(pyproject_text, "baseline_version")
    if not version_text:
        failures.append("version-consistency: VERSION is empty")
    if version_text and pyproject_version != version_text:
        failures.append("version-consistency: pyproject.toml project version does not match VERSION")
    if version_text and baseline_version != version_text:
        failures.append("version-consistency: pyproject.toml SkillGuard baseline_version does not match VERSION")
    readme_version_markers = (
        f"Current release: `v{version_text}`",
        f"Current source version: `v{version_text}`",
    )
    if version_text and not any(marker in readme_text for marker in readme_version_markers):
        failures.append("version-consistency: README source/release version line does not match VERSION")
    if version_text and f"## v{version_text} -" not in changelog_text:
        failures.append("version-consistency: CHANGELOG is missing the current version entry")
    append_check(
        payload,
        "check-readme-release:version-consistency",
        "Version consistency",
        check_status(failures, blockers, before_failures, before_blockers),
        "Checked VERSION, pyproject.toml, README source/release version line, and CHANGELOG entry.",
    )

    before_failures, before_blockers = len(failures), len(blockers)
    if readme_text:
        for command_name in COMMANDS:
            if f"`{command_name}`" not in readme_text:
                failures.append(f"README command surface missing `{command_name}`")
    for path in [readme_path, changelog_path, hero_prompt_path, hero_design_path, model_evidence_path]:
        if not path.is_file():
            continue
        for finding in public_safety_findings(path, root=repo):
            public_safety.append(finding)
            failures.append(f"{finding['path']}: public-safety scan found {finding['finding_id']} on line {finding['line']}")
        unsafe_claim_findings.extend(scan_text_for_unsafe_claims(path, failures, root=repo))
    append_check(
        payload,
        "check-readme-release:public-boundary",
        "Command surface and public boundary",
        check_status(failures, blockers, before_failures, before_blockers),
        "Checked README command surface wording and scanned public-facing README release files for private paths and unsafe overclaims.",
    )

    payload["files_inspected"] = files_inspected
    payload["public_safety_findings"] = public_safety
    payload["unsafe_claim_findings"] = unsafe_claim_findings
    payload["evidence"] = [
        {
            "evidence_id": "readme-release-file-set",
            "kind": "filesystem_check",
            "fresh": True,
            "summary": f"Inspected {len(files_inspected)} README release files.",
            "source_path": public_relative_path(readme_path, repo),
        },
        {
            "evidence_id": "readme-release-version",
            "kind": "version_consistency",
            "fresh": True,
            "summary": f"VERSION={version_text or 'missing'}; pyproject.version={pyproject_version or 'missing'}; baseline_version={baseline_version or 'missing'}.",
            "source_path": public_relative_path(version_path, repo),
        },
        {
            "evidence_id": "readme-release-hero",
            "kind": "hero_provenance",
            "fresh": True,
            "summary": "Checked text-to-image hero prompt, design note, README hero block, and raster asset.",
            "source_path": public_relative_path(hero_prompt_path, repo),
        },
    ]
    payload["failures"] = failures
    payload["blockers"] = blockers
    payload["decision"] = "block" if blockers else "fail" if failures else "pass"
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


def slugify_identifier(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "planned-skill"


def string_field(data: dict[str, Any], field: str, blockers: list[str], alias: str | None = None) -> str:
    value = data.get(field)
    if value is None and alias is not None:
        value = data.get(alias)
    if not isinstance(value, str) or not value.strip():
        blockers.append(f"missing required non-empty string field: {field}")
        return ""
    return value.strip()


def string_list_field(data: dict[str, Any], field: str, blockers: list[str]) -> list[str]:
    value = data.get(field, PLAN_SKILL_DEFAULT_LISTS[field])
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or not value:
        blockers.append(f"{field} must be a non-empty string list when supplied")
        return []
    normalized: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            blockers.append(f"{field}[{index}] must be a non-empty string")
            continue
        normalized.append(item.strip())
    return normalized


def resolve_plan_skill_target(target_text: str, blockers: list[str]) -> str:
    if Path(target_text).is_absolute():
        blockers.append("target_path must be repository-relative and stay under the repository root")
        return ""
    try:
        return public_relative_path(ensure_under_root(target_text))
    except ValueError:
        blockers.append("target_path must stay under the repository root")
        return ""


def template_source_identity(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_template_request(data: dict[str, Any], blockers: list[str]) -> dict[str, Any]:
    request = data.get("template_request")
    if request is None:
        return {"profile_kind": "skillguard_validated_base"}
    if not isinstance(request, dict):
        blockers.append("template_request must be an object when supplied")
        return {}
    unknown = set(request) - TEMPLATE_REQUEST_FIELDS
    blockers.extend(f"template_request contains unknown field: {field}" for field in sorted(unknown))
    normalized: dict[str, Any] = {"profile_kind": "target_owned_selection"}
    for field in ("adapter_projection_path",):
        value = request.get(field)
        if not isinstance(value, str) or not value.strip():
            blockers.append(f"template_request.{field} must be a non-empty repository-relative path")
            continue
        if Path(value).is_absolute():
            blockers.append(f"template_request.{field} must be repository-relative")
            continue
        try:
            normalized[field] = public_relative_path(ensure_under_root(value))
        except ValueError:
            blockers.append(f"template_request.{field} must stay under the repository root")
    parameters = request.get("parameters", {})
    if not isinstance(parameters, dict):
        blockers.append("template_request.parameters must be an object when supplied")
        parameters = {}
    normalized["parameters"] = parameters
    return normalized


def normalize_plan_skill_input(data: Any) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    if not isinstance(data, dict):
        return {}, ["plan-skill input must be a JSON object"]

    normalized: dict[str, Any] = {}
    normalized["skill_name"] = string_field(data, "skill_name", blockers, alias="name")
    normalized["description"] = string_field(data, "description", blockers)
    normalized["target_path"] = string_field(data, "target_path", blockers)
    normalized["purpose"] = string_field(data, "purpose", blockers)
    normalized["template_request"] = normalize_template_request(data, blockers)
    for field in PLAN_SKILL_DEFAULT_LISTS:
        normalized[field] = string_list_field(data, field, blockers)

    workflow_mode = data.get("workflow_mode", "create")
    if workflow_mode not in PLAN_SKILL_SUPPORTED_WORKFLOW_MODES:
        blockers.append(
            f"unsupported workflow_mode {workflow_mode!r}; plan-skill supports {', '.join(PLAN_SKILL_SUPPORTED_WORKFLOW_MODES)} only"
        )
    normalized["workflow_mode"] = workflow_mode

    safe_edit_mode = data.get("safe_edit_mode", "no_write")
    if safe_edit_mode not in PLAN_SKILL_SUPPORTED_SAFE_EDIT_MODES:
        blockers.append("safe_edit_mode must be no_write; plan-skill does not write target files")
    normalized["safe_edit_mode"] = safe_edit_mode

    for flag in ("write_target_files", "create_target_files", "mutate_target"):
        if data.get(flag) is True:
            blockers.append(f"{flag} must be false or omitted; plan-skill is preview-only")

    target_relative = resolve_plan_skill_target(normalized.get("target_path", ""), blockers) if normalized.get("target_path") else ""
    normalized["target_path"] = target_relative
    normalized["closure_scope"] = clean_scalar(str(data.get("closure_scope", "skill blueprint preview only")))
    evidence_policy = data.get("evidence_policy", "current direct evidence required before acceptance or closure")
    if isinstance(evidence_policy, dict):
        normalized["evidence_policy"] = evidence_policy
    elif isinstance(evidence_policy, str) and evidence_policy.strip():
        normalized["evidence_policy"] = {
            "policy": evidence_policy.strip(),
            "direct_evidence_required": True,
            "report_only_evidence_allowed": False,
            "stale_evidence_blocks_acceptance": True,
        }
    else:
        blockers.append("evidence_policy must be a non-empty string or object when supplied")
        normalized["evidence_policy"] = {}

    return normalized, blockers


def plan_skill_gate(gate: str, status: str, evidence: list[str], notes: str, required: bool = True) -> dict[str, Any]:
    return {
        "gate": gate,
        "status": status,
        "required": required,
        "evidence": evidence,
        "notes": notes,
    }


def build_plan_skill_blueprint(input_data: dict[str, Any], input_relative: str) -> dict[str, Any]:
    slug = slugify_identifier(input_data["skill_name"])
    target_path = input_data["target_path"]
    no_write_note = "plan-skill emits a blueprint preview only and does not create or modify target files."
    return {
        "schema_version": SKILL_BLUEPRINT_SCHEMA_VERSION,
        "blueprint_id": f"skillguard.skill_blueprint.{slug}.v2",
        "source_command": "plan-skill",
        "source_input": input_relative,
        "target": target_path,
        "skill": {
            "name": input_data["skill_name"],
            "description": input_data["description"],
            "purpose": input_data["purpose"],
            "target_path": target_path,
            "use_when": input_data["use_when"],
            "do_not_use_when": input_data["do_not_use_when"],
        },
        "workflow_mode": input_data["workflow_mode"],
        "closure_scope": input_data["closure_scope"],
        "evidence_policy": input_data["evidence_policy"],
        "safe_edit_scope": {
            "mode": input_data["safe_edit_mode"],
            "target_file_writes_allowed": False,
            "allowed_write_paths": [],
            "preservation_rule": no_write_note,
        },
        "phase_plan": [
            {
                "phase_id": "intake",
                "owner": "maintainer",
                "inputs": ["skill_name", "description", "target_path", "purpose"],
                "allowed_paths": [input_relative],
                "expected_outputs": ["normalized skill idea contract"],
                "evidence": ["input-json"],
                "blockers": [],
                "skipped_checks": [],
                "next_action": "inventory",
            },
            {
                "phase_id": "inventory",
                "owner": "worker",
                "inputs": ["target_path", "safe_edit_scope"],
                "allowed_paths": [target_path],
                "expected_outputs": ["current target inventory before any file creation"],
                "evidence": [],
                "blockers": [],
                "skipped_checks": ["Target inventory is future work; plan-skill is preview-only."],
                "next_action": "deterministic-evidence",
            },
            {
                "phase_id": "deterministic-evidence",
                "owner": "worker",
                "inputs": ["current target files", "standards", "schemas", "templates"],
                "allowed_paths": [target_path],
                "expected_outputs": ["parser, command, fixture, or file evidence for the declared scope"],
                "evidence": [],
                "blockers": [],
                "skipped_checks": ["Target deterministic checks are not run by plan-skill."],
                "next_action": "judgment",
            },
            {
                "phase_id": "judgment",
                "owner": "reviewer",
                "inputs": ["deterministic evidence", "activation boundary", "claim boundary"],
                "allowed_paths": [target_path],
                "expected_outputs": ["semantic review record with uncertainty and residual risk"],
                "evidence": [],
                "blockers": [],
                "skipped_checks": ["Reviewer judgment is future work after target evidence exists."],
                "next_action": "closure",
            },
            {
                "phase_id": "closure",
                "owner": "pm-or-reviewer",
                "inputs": ["current evidence", "reviewer record", "blocker disposition"],
                "allowed_paths": [target_path],
                "expected_outputs": ["bounded closure report for the declared scope"],
                "evidence": [],
                "blockers": [],
                "skipped_checks": ["Closure is not performed by plan-skill."],
                "next_action": "create or audit target only after explicit authorization",
            },
        ],
        "evidence_gates": [
            plan_skill_gate(
                "input-contract",
                "pass",
                ["input-json"],
                "The input JSON was parsed and normalized into a blueprint preview.",
            ),
            plan_skill_gate(
                "target-files-not-written",
                "pass",
                ["no-write-command-design"],
                no_write_note,
            ),
            plan_skill_gate(
                "future-target-validation",
                "not_checked",
                [],
                "Target skill files must be inspected and checked after they exist or change.",
            ),
            plan_skill_gate(
                "claim-boundary",
                "pass",
                ["blueprint-claim-boundary"],
                "The blueprint limits this command to planning output and leaves acceptance to later evidence.",
            ),
        ],
        "handoffs": [
            {
                "handoff_id": "worker-create-or-audit",
                "recipient": "worker",
                "current_artifacts": [input_relative],
                "target_path": target_path,
                "claim_boundary": "Use this blueprint as planning input only; inspect current target files before any edit or acceptance claim.",
                "next_action": "collect inventory and deterministic evidence for the declared target scope.",
            },
            {
                "handoff_id": "reviewer",
                "recipient": "reviewer",
                "current_artifacts": [input_relative],
                "unresolved_questions": [
                    "Does the activation boundary match the intended maintainer workflow?",
                    "Do future deterministic checks support the requested closure scope?",
                ],
                "claim_boundary": "Reviewer acceptance must be tied to current target evidence, not this blueprint alone.",
            },
        ],
        "closure_report": {
            "decision": "checked",
            "scope": "skill blueprint preview only",
            "evidence": ["input-json", "plan-skill-command-output"],
            "deterministic_checks": ["input JSON parse", "target path repository-boundary check", "no-write safe-edit check"],
            "judgment_checks": [],
            "skipped_checks": [
                "Target file inspection, fixture execution, reviewer judgment, and closure are outside this preview command."
            ],
            "blockers": [],
            "residual_risk": [
                "The blueprint does not prove that the target skill exists, activates correctly, or satisfies SkillGuard standards."
            ],
            "claim_boundary": (
                "This closure report covers only the plan-skill blueprint preview. It does not prove runtime checker execution, "
                "fixture coverage, CLI checks beyond this command, tests, suite automation, package publication, release readiness, "
                "code-contract validation, external services, or future AI behavior."
            ),
            "next_action": "Use the blueprint as input to a separately authorized create, audit, repair, or closure workflow.",
        },
        "residual_risk": [
            "This blueprint is a planning artifact; target file creation, deterministic checks, reviewer judgment, and acceptance remain future work.",
            "Defaults in this blueprint should be reviewed before creating a real skill target.",
        ],
        "claim_boundary": (
            "This Skill Blueprint is generated from current input JSON and is a preview artifact only. It does not write target files, "
            "prove target correctness, fixture coverage, tests, suite automation, package publication, release readiness, "
            "code-contract validation, external integrations, or future AI behavior."
        ),
    }


def single_line(value: Any, default: str = "") -> str:
    text = value if isinstance(value, str) else default
    return " ".join(text.strip().split()) or default


def markdown_list(items: Any, default_items: list[str] | None = None) -> str:
    values = items if isinstance(items, list) and items else default_items or ["Not declared."]
    lines: list[str] = []
    for item in values:
        text = single_line(item, "Not declared.")
        lines.append(f"- {text}")
    return "\n".join(lines)


def json_block(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def common_claim_boundary(scope: str) -> str:
    return (
        f"This {scope} records only generated scaffold state and current local files. It does not prove runtime checker execution, "
        "fixture coverage, CLI checks, tests, suite automation, package publication, code-contract validation, release readiness, "
        "external services, or future AI behavior without separate current evidence."
    )


def expand_global_path(path_text: str | Path) -> Path:
    text = os.path.expandvars(str(path_text))
    return Path(text).expanduser().resolve()


def global_public_path(path_text: str | Path) -> str:
    path = expand_global_path(path_text)
    # Global router identities must not depend on whether the checker is
    # running from the source repository or from ~/.codex/skills/skillguard.
    # Paths inside the managed Codex home therefore use one canonical token
    # before any repository-relative projection is considered.
    home = Path.home().resolve()
    try:
        home_relative = path.relative_to(home)
        if home_relative.parts and home_relative.parts[0] == ".codex":
            return home_relative.as_posix()
    except ValueError:
        home_relative = None
    repo = repository_root().resolve()
    try:
        return path.relative_to(repo).as_posix()
    except ValueError:
        pass
    if home_relative is not None:
        return "~/" + home_relative.as_posix()
    return f"<external:{hashlib.sha256(str(path).encode('utf-8')).hexdigest()[:12]}>/{path.name}"


def global_read_json(path_text: str | Path) -> Any:
    with expand_global_path(path_text).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def global_write_json(path_text: str | Path, payload: Any) -> Path:
    path = expand_global_path(path_text)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    data = json_block(payload).encode("utf-8")
    try:
        temporary.write_bytes(data)
        with temporary.open("r+b") as handle:
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return path


def global_write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(text, encoding="utf-8")
        with temporary.open("r+b") as handle:
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _reuse_unchanged_generated_json(
    path: Path, candidate: dict[str, Any]
) -> tuple[dict[str, Any], bool]:
    """Reuse byte-stable generated evidence when only observation time differs."""

    if not path.is_file():
        return candidate, False
    try:
        existing = global_read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return candidate, False
    if not current_global_router.reuse_unchanged_generated(existing, candidate):
        return candidate, False
    return existing, True


def global_checked_file(path_text: str | Path, kind: str = "file") -> dict[str, Any]:
    path = expand_global_path(path_text)
    return {
        "path": global_public_path(path),
        "kind": kind,
        "sha256": file_sha256(path),
        "line_count": line_count(path),
    }


def global_resolvable_relative_path(path_label: str) -> Path | None:
    if not path_label or path_label.startswith("<external:") or path_label.startswith("~/"):
        return None
    candidate = (repository_root() / path_label).resolve()
    try:
        candidate.relative_to(repository_root().resolve())
    except ValueError:
        return None
    return candidate


def global_resolvable_scan_root_path(path_label: str, codex_home: str | None = None) -> Path | None:
    if not path_label or path_label.startswith("<external:"):
        return None
    normalized = path_label.replace("\\", "/")
    if normalized == ".codex" or normalized.startswith(".codex/"):
        codex_root = expand_global_path(codex_home) if codex_home else (Path.home() / ".codex").resolve()
        suffix = normalized[len(".codex") :].lstrip("/")
        return (codex_root / suffix).resolve()
    if normalized.startswith("~/") or Path(path_label).is_absolute():
        return expand_global_path(path_label)
    return global_resolvable_relative_path(path_label)


def global_skill_roots_from_args(skill_roots: list[str], codex_home: str | None = None) -> tuple[list[Path], list[str]]:
    roots: list[Path] = []
    blockers: list[str] = []
    for root_text in skill_roots:
        root = expand_global_path(root_text)
        if not root.is_dir():
            blockers.append(f"skill root is missing or not a directory: {global_public_path(root)}")
            continue
        roots.append(root)
    if not roots and not blockers:
        blockers.append(
            "no explicit author-side --skill-root supplied; installed consumer "
            "skills are not a SkillGuard maintenance registry source"
        )
    return roots, blockers


def parse_global_skill_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    data: dict[str, str] = {}
    for raw_line in text[3:end].splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        data[key.strip().lower()] = clean_scalar(value.strip())
    return data


def global_contract_semantic_root(skill_dir: Path) -> Path:
    resolved = skill_dir.resolve()
    repo = repository_root().resolve()
    try:
        resolved.relative_to(repo)
        return repo
    except ValueError:
        pass
    if resolved.parent.name == "skills":
        return resolved.parent.parent
    return resolved


# The exact current discovery module is the sole registry builder. Old authority
# shapes are rejected by that module and have no discovery or prompt fallback.
def global_contract_projection(skill_dir: Path) -> tuple[dict[str, Any], list[str]]:
    return current_global_discovery.contract_projection(
        skill_dir,
        repository_root=repository_root(),
        codex_home=(Path.home() / ".codex").resolve(),
    )


def discover_global_skill_items(
    skill_roots: list[Path],
) -> tuple[list[dict[str, Any]], list[str]]:
    return current_global_discovery.discover_skill_items(
        skill_roots,
        repository_root=repository_root(),
        codex_home=(Path.home() / ".codex").resolve(),
    )


def build_global_registry_payload(skill_roots: list[Path]) -> dict[str, Any]:
    return current_global_discovery.build_registry_payload(
        skill_roots,
        repository_root=repository_root(),
        codex_home=(Path.home() / ".codex").resolve(),
        generated_at=utc_timestamp(),
    )


def global_registry_hash(payload: dict[str, Any]) -> str:
    return current_global_router.registry_hash(payload)


def global_diagnostic_inventory_hash(payload: dict[str, Any]) -> str:
    return current_global_router.diagnostic_inventory_hash(payload)


def global_registry_integrity_failures(payload: object) -> list[str]:
    return current_global_router.registry_integrity_failures(payload)


def registry_roots_for_check(registry: dict[str, Any], supplied_roots: list[str], codex_home: str | None = None) -> tuple[list[Path], list[str]]:
    if supplied_roots:
        return global_skill_roots_from_args(supplied_roots, codex_home)
    roots: list[Path] = []
    blockers: list[str] = []
    for row in registry.get("scan_roots", []) if isinstance(registry.get("scan_roots"), list) else []:
        if not isinstance(row, dict):
            continue
        path_label = str(row.get("path") or "")
        candidate = global_resolvable_scan_root_path(path_label, codex_home)
        if candidate is None:
            blockers.append(f"scan root is not re-checkable without --skill-root: {path_label}")
            continue
        roots.append(candidate)
    if not roots and not blockers:
        blockers.append("registry does not declare any re-checkable scan roots")
    return roots, blockers


def global_registry_current_route_failures(
    registry: dict[str, Any],
    *,
    codex_home: str | None = None,
) -> tuple[list[str], list[str]]:
    """Rebuild only the current route projection for a supplied registry.

    Diagnostic-only skill changes remain outside this decision; they may make
    the registry artifact's diagnostic inventory stale, but they do not make
    an unchanged current route or managed prompt stale.
    """

    roots, blockers = registry_roots_for_check(registry, [], codex_home)
    if blockers:
        return [], blockers
    current = build_global_registry_payload(roots)
    failures = []
    if current.get("registry_hash") != registry.get("registry_hash"):
        failures.append("registry current route projection is stale")
    return failures, []


task_tokens = current_global_router.task_tokens
global_skill_route_score = current_global_router.skill_route_score
global_route_candidates = current_global_router.route_candidates
global_candidate_handoff_blockers = (
    current_global_router.candidate_handoff_blockers
)


def template_lifecycle_prompt_bundle() -> tuple[str, str]:
    content = "\n\n".join(
        ensure_under_root(skill_root() / relative_path).read_text(encoding="utf-8").strip()
        for relative_path in TEMPLATE_PROFILE_PROMPT_PATHS.values()
    )
    return content, sha256_identity(content)


def render_global_prompt_block(registry: dict[str, Any], registry_path: str = "") -> str:
    template_path = (
        skill_root()
        / "assets"
        / "templates"
        / "global_skillguard_prompt_block.md.template"
    )
    block = current_global_router.render_prompt_block(
        registry,
        registry_path=registry_path,
        template=template_path.read_text(encoding="utf-8"),
        policy_id=VALIDATION_EXECUTION_POLICY_ID,
        policy_lines=VALIDATION_EXECUTION_POLICY_LINES,
    )
    lifecycle, lifecycle_hash = template_lifecycle_prompt_bundle()
    insertion = "\n".join(
        [
            lifecycle,
            "",
            f"- template_lifecycle_hash: {lifecycle_hash}",
            "- template_domain_selection_owner: selected_target_skill",
            "- global_router_selects_domain_template: false",
        ]
    )
    marker = "\n### Current Route Index"
    if block.count(marker) != 1:
        raise ValueError("global_prompt_route_index_marker_invalid")
    return block.replace(marker, f"\n{insertion}\n\n### Current Route Index", 1)


def build_global_prompt_projection(registry: dict[str, Any], registry_path: str = "") -> dict[str, Any]:
    block = render_global_prompt_block(registry, registry_path)
    manifest_path = skill_root() / ".skillguard" / "check-manifest.json"
    compiled_path = skill_root() / ".skillguard" / "compiled-contract.json"
    manifest = global_read_json(manifest_path)
    compiled = global_read_json(compiled_path)
    if not isinstance(manifest, dict) or not isinstance(
        manifest.get("content_impact_plan"), dict
    ):
        raise ValueError("global_prompt_content_impact_plan_missing")
    if not isinstance(compiled, dict):
        raise ValueError("global_prompt_compiled_contract_missing")
    schema_findings = [
        *validate_v2_check_manifest(manifest),
        *validate_compiled_contract(compiled),
    ]
    if schema_findings:
        raise ValueError("global_prompt_contract_authority_invalid")
    unsigned_contract = dict(compiled)
    stored_contract_hash = unsigned_contract.pop("contract_hash", None)
    unsigned_manifest = dict(manifest)
    stored_manifest_hash = unsigned_manifest.pop("manifest_hash", None)
    if (
        stored_contract_hash != canonical_hash(unsigned_contract)
        or stored_manifest_hash != canonical_hash(unsigned_manifest)
        or manifest.get("contract_hash") != stored_contract_hash
        or manifest.get("check_declarations_hash")
        != compiled.get("check_declarations_hash")
        or manifest.get("content_impact_plan")
        != compiled.get("content_impact_plan")
    ):
        raise ValueError("global_prompt_contract_authority_hash_invalid")
    authority = resolve_runtime_authority(skill_root())
    if not authority.ok or authority.authority != AUTHORITY_CURRENT:
        raise ValueError("global_prompt_runtime_authority_not_current")
    skill_id = str(manifest.get("skill_id", "")).strip()
    if not skill_id:
        raise ValueError("global_prompt_content_impact_skill_id_missing")
    content_projection = current_content_projection_from_files(
        manifest["content_impact_plan"],
        "projection:global-router",
        repository_root=repository_root(),
        member_roots={
            f".agents/skills/{skill_id}/": skill_root(),
            f".codex/skills/{skill_id}/": skill_root(),
        },
    )
    plan = manifest["content_impact_plan"]
    component_index = {
        str(row.get("component_id", "")): row
        for row in plan.get("components", [])
        if isinstance(row, dict)
    }
    declared_paths = {
        str(path).replace("\\", "/")
        for component_id in content_projection["input_component_ids"]
        for path in component_index.get(component_id, {}).get("member_paths", [])
    }
    suffix = "/scripts/skillguard_v2/global_router_projection.py"
    prefixes = {
        path[: -len(suffix)]
        for path in declared_paths
        if path.endswith(suffix)
    }
    if len(prefixes) != 1:
        raise ValueError("global_prompt_router_member_prefix_invalid")
    skill_prefix = next(iter(prefixes))
    expected_paths = {
        f"{skill_prefix}/{relative.as_posix()}"
        for relative, _candidate in portable_files(skill_root())
        if current_global_router.is_global_router_projection_path(
            f"{skill_prefix}/{relative.as_posix()}", skill_prefix
        )
    }
    if declared_paths != expected_paths:
        raise ValueError("global_prompt_router_member_inventory_stale")
    template_path = (
        skill_root()
        / "assets"
        / "templates"
        / "global_skillguard_prompt_block.md.template"
    )
    return current_global_router.build_prompt_projection(
        registry,
        registry_path=registry_path,
        managed_block=block,
        template_content_hash=impact_file_hash(template_path),
        content_projection=content_projection,
        generated_at=utc_timestamp(),
    )


def build_global_prompt_projection_or_block(
    registry: dict[str, Any],
    registry_path: str,
    blockers: list[str],
) -> dict[str, Any]:
    try:
        return build_global_prompt_projection(registry, registry_path)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        blockers.append(f"global prompt projection is unavailable: {exc}")
        return {}


def replace_managed_global_prompt_block(existing: str, block: str) -> tuple[str, str]:
    return current_global_router.replace_managed_block(existing, block)


def check_global_prompt_text(
    text: str,
    registry_hash: str,
    expected_block: str | None = None,
) -> tuple[list[str], list[str]]:
    return current_global_router.check_prompt_text(
        text,
        registry_hash,
        expected_block=expected_block,
        policy_id=VALIDATION_EXECUTION_POLICY_ID,
        policy_lines=VALIDATION_EXECUTION_POLICY_LINES,
    )


def extract_skill_blueprint(data: Any) -> tuple[dict[str, Any], list[str]]:
    if not isinstance(data, dict):
        return {}, ["generate-skill input must be a JSON object"]
    if data.get("schema_version") == SKILL_BLUEPRINT_SCHEMA_VERSION:
        return data, []
    nested = data.get("skill_blueprint")
    if isinstance(nested, dict) and nested.get("schema_version") == SKILL_BLUEPRINT_SCHEMA_VERSION:
        return nested, []
    return {}, [
        f"input must be a current {SKILL_BLUEPRINT_SCHEMA_VERSION} object or a current plan-skill result containing skill_blueprint"
    ]


def resolve_generate_skill_target(blueprint: dict[str, Any], blockers: list[str]) -> Path | None:
    target_text = blueprint.get("target") or (blueprint.get("skill") if isinstance(blueprint.get("skill"), dict) else {}).get("target_path")
    if not isinstance(target_text, str) or not target_text.strip():
        blockers.append("Skill Blueprint must declare a non-empty target path")
        return None
    if Path(target_text).is_absolute():
        blockers.append("target path must be repository-relative; absolute target paths are blocked")
        return None
    try:
        target = ensure_under_root(target_text)
    except ValueError:
        blockers.append("target path must stay under the repository root")
        return None
    repo = repository_root().resolve()
    if target.resolve() == repo:
        blockers.append("target path must not be the repository root")
        return None
    if target.exists() and not target.is_dir():
        blockers.append(f"target path exists but is not a directory: {public_relative_path(target)}")
        return None
    return target


def relative_to_any(path: Path, roots: list[Path]) -> bool:
    resolved = path.resolve()
    for root in roots:
        try:
            resolved.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False


def validate_generate_skill_blueprint(blueprint: dict[str, Any]) -> tuple[Path | None, list[str]]:
    blockers: list[str] = []
    if blueprint.get("schema_version") != SKILL_BLUEPRINT_SCHEMA_VERSION:
        blockers.append(f"Skill Blueprint schema_version must be {SKILL_BLUEPRINT_SCHEMA_VERSION}")
    blockers.extend(
        f"Skill Blueprint contains unknown field: {field}"
        for field in sorted(set(blueprint) - GENERATE_SKILL_BLUEPRINT_FIELDS)
    )
    for field in GENERATE_SKILL_REQUIRED_BLUEPRINT_FIELDS:
        if field not in blueprint:
            blockers.append(f"Skill Blueprint missing required field: {field}")
    if blueprint.get("source_command") != "plan-skill":
        blockers.append("Skill Blueprint source_command must be plan-skill")
    if not isinstance(blueprint.get("source_input"), str) or not blueprint.get("source_input", "").strip():
        blockers.append("Skill Blueprint source_input must be a non-empty repository-relative path")
    if blueprint.get("workflow_mode") != "create":
        blockers.append("generate-skill only supports Skill Blueprints with workflow_mode=create")

    skill = blueprint.get("skill")
    if not isinstance(skill, dict):
        blockers.append("Skill Blueprint field skill must be an object")
        skill = {}
    blockers.extend(
        f"Skill Blueprint skill object contains unknown field: {field}"
        for field in sorted(set(skill) - GENERATE_SKILL_SKILL_FIELDS)
    )
    for field in ("name", "description", "purpose", "use_when", "do_not_use_when"):
        if field not in skill:
            blockers.append(f"Skill Blueprint skill object missing required field: {field}")

    for field in ("phase_plan", "evidence_gates", "handoffs", "residual_risk"):
        if field in blueprint and not isinstance(blueprint[field], list):
            blockers.append(f"Skill Blueprint field {field} must be an array")
    if "closure_report" in blueprint and not isinstance(blueprint["closure_report"], dict):
        blockers.append("Skill Blueprint field closure_report must be an object")
    if "template_profile" in blueprint:
        try:
            validate_template_profile(blueprint["template_profile"])
        except TemplateProfileError as exc:
            blockers.extend(f"Skill Blueprint template_profile invalid: {finding}" for finding in exc.findings)
    safe_edit_scope = blueprint.get("safe_edit_scope")
    if not isinstance(safe_edit_scope, dict):
        blockers.append("Skill Blueprint field safe_edit_scope must be an object")
        safe_edit_scope = {}

    target = resolve_generate_skill_target(blueprint, blockers)
    if target is not None:
        skill_name = single_line(skill.get("name"), target.name)
        if slugify_identifier(skill_name) != target.name and skill_name != target.name:
            blockers.append("Skill Blueprint skill.name must match the target directory name")
        allowed_write_paths = safe_edit_scope.get("allowed_write_paths", [])
        if isinstance(allowed_write_paths, list) and allowed_write_paths:
            allowed_roots: list[Path] = []
            for path_text in allowed_write_paths:
                if not isinstance(path_text, str):
                    blockers.append("safe_edit_scope.allowed_write_paths entries must be strings")
                    continue
                try:
                    allowed_roots.append(ensure_under_root(path_text))
                except ValueError:
                    blockers.append(f"safe_edit_scope.allowed_write_paths entry escapes repository boundary: {path_text}")
            if allowed_roots and not relative_to_any(target, allowed_roots):
                blockers.append("target path is outside safe_edit_scope.allowed_write_paths")
        elif allowed_write_paths not in ([], None):
            blockers.append("safe_edit_scope.allowed_write_paths must be an array when supplied")
    return target, blockers


def scaffold_path(target: Path, relative: str) -> Path:
    path = (target / relative).resolve()
    path.relative_to(target.resolve())
    ensure_under_root(path)
    return path


def generate_skill_required_directory_entries(target: Path) -> list[tuple[str, Path, str]]:
    entries: list[tuple[str, Path, str]] = [("", target, "target scaffold root")]
    seen = {""}
    for relative in GENERATE_SKILL_REQUIRED_DIRECTORIES:
        parts = relative.split("/")
        for index in range(1, len(parts)):
            parent_relative = "/".join(parts[:index])
            if parent_relative not in seen:
                role = GENERATE_SKILL_REQUIRED_DIRECTORY_ROLES.get(
                    parent_relative, f"parent directory for {relative}"
                )
                entries.append((parent_relative, scaffold_path(target, parent_relative), role))
                seen.add(parent_relative)
        if relative not in seen:
            role = GENERATE_SKILL_REQUIRED_DIRECTORY_ROLES.get(relative, f"required scaffold directory {relative}")
            entries.append((relative, scaffold_path(target, relative), role))
            seen.add(relative)
    return entries


def expected_scaffold_directory_set(directory_entries: list[tuple[str, Path, str]], files: dict[str, str]) -> set[str]:
    expected_dirs = {relative for relative, _path, _role in directory_entries if relative}
    for relative in files:
        parent = Path(relative).parent
        parts = [] if str(parent) == "." else parent.as_posix().split("/")
        for index in range(1, len(parts) + 1):
            expected_dirs.add("/".join(parts[:index]))
    return expected_dirs


def preflight_output_tree_ownership(
    *,
    command_name: str,
    target: Path,
    files: dict[str, str],
    directory_entries: list[tuple[str, Path, str]],
) -> list[dict[str, str]]:
    if not target.exists() or not target.is_dir():
        return []

    expected_files = set(files)
    expected_dirs = expected_scaffold_directory_set(directory_entries, files)
    existing_files: set[str] = set()
    existing_dirs: set[str] = set()
    conflicts: list[dict[str, str]] = []

    for item in sorted(target.rglob("*")):
        relative = item.relative_to(target).as_posix()
        path_decision = classify_relative_path(relative)
        if path_decision.classification == RUNTIME and not path_decision.boundary_blocking:
            # Preserve but ignore generated caches, current runs, receipts, and
            # other non-authoritative runtime output.  They must not make an
            # otherwise identical scaffold appear user-modified.
            continue
        if item.is_file():
            existing_files.add(relative)
            if relative not in expected_files:
                conflicts.append(
                    {
                        "conflict_kind": "unexpected_existing_file",
                        "conflicting_path": public_relative_path(item),
                        "expected_generated_owner": command_name,
                        "safe_remediation_path": public_relative_path(item),
                        "safe_remediation": (
                            f"Move, rename, or remove {public_relative_path(item)} before rerunning {command_name}; "
                            "the generator does not merge into user or peer-agent files."
                        ),
                    }
                )
        elif item.is_dir():
            existing_dirs.add(relative)
            if relative not in expected_dirs:
                conflicts.append(
                    {
                        "conflict_kind": "unexpected_existing_directory",
                        "conflicting_path": public_relative_path(item),
                        "expected_generated_owner": command_name,
                        "safe_remediation_path": public_relative_path(item),
                        "safe_remediation": (
                            f"Move, rename, or remove {public_relative_path(item)} before rerunning {command_name}; "
                            "the generator does not merge into user or peer-agent directories."
                        ),
                    }
                )
        else:
            conflicts.append(
                {
                    "conflict_kind": "unsupported_existing_path_type",
                    "conflicting_path": public_relative_path(item),
                    "expected_generated_owner": command_name,
                    "safe_remediation_path": public_relative_path(item),
                    "safe_remediation": f"Replace {public_relative_path(item)} with an ordinary file or directory before rerunning {command_name}.",
                }
            )

    existing_entries = existing_files | existing_dirs
    if existing_entries and not conflicts:
        expected_existing_files = existing_files & expected_files
        if not expected_existing_files or expected_existing_files != expected_files:
            conflicts.append(
                {
                    "conflict_kind": "incomplete_generated_ownership",
                    "conflicting_path": public_relative_path(target),
                    "expected_generated_owner": command_name,
                    "safe_remediation_path": public_relative_path(target),
                    "safe_remediation": (
                        f"Use an empty target path or restore the complete generated output set before rerunning {command_name}; "
                        "partial generated trees and unowned directories are blocked before writes."
                    ),
                }
            )
    return conflicts


def preflight_conflict_blocker(conflict: dict[str, str], command_name: str) -> str:
    conflict_kind = conflict.get("conflict_kind", "write_preflight_conflict")
    conflict_path = conflict.get("conflicting_path", "<unknown>")
    remediation_path = conflict.get("safe_remediation_path", conflict_path)
    return (
        f"{conflict_kind}: {conflict_path} is not safe for {command_name}; "
        f"safe remediation path: {remediation_path}"
    )


def structured_file_preflight_conflict(
    *,
    command_name: str,
    path: Path,
    conflict_kind: str,
    safe_remediation: str,
) -> dict[str, str]:
    path_text = public_relative_path(path)
    return {
        "conflict_kind": conflict_kind,
        "conflicting_path": path_text,
        "expected_generated_owner": command_name,
        "safe_remediation_path": path_text,
        "safe_remediation": safe_remediation,
    }


def generated_common_record(
    *,
    schema_version: str,
    target_relative: str,
    target_type: str,
    status: str,
    evidence: list[Any] | None = None,
    skipped_checks: list[dict[str, str]] | None = None,
    residual_risk: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema_version": schema_version,
        "target_path": target_relative,
        "target_type": target_type,
        "status": status,
        "evidence": evidence or ["generate-skill-command-output"],
        "failures": [],
        "blockers": [],
        "skipped_checks": skipped_checks
        or [
            {
                "reason": "Generated scaffold has not yet run target-specific semantic review.",
                "impact": "Acceptance remains blocked until current target checks and reviewer judgment run.",
            }
        ],
        "residual_risk": residual_risk
        or ["Generated scaffold content still needs maintainer review before any accepted status can be claimed."],
        "claim_boundary": common_claim_boundary("record"),
    }
    if extra:
        record.update(extra)
    return record


def generated_current_contract_sources(skill_id: str) -> tuple[str, dict[str, Any]]:
    """Build one small current contract owner for a new generated skill.

    The generated skill remains a draft.  This model and binding establish the
    current contract path and exact owner inputs; they do not manufacture
    execution-depth or release evidence.
    """

    model_id = f"{skill_id}.generated_current_authority.current"
    owner_id = f"owner:{skill_id}"
    function_id = "function:maintain-generated-skill"
    route_id = "route:maintain-generated-skill"
    action_step_id = "step:run-generated-current-check"
    success_step_id = "terminal:current"
    blocked_step_id = "terminal:blocked"
    obligation_id = "obligation:generated-current-check"
    invariant_id = "invariant:generated-current-check"
    check_id = "check:generated-current"
    model: dict[str, Any] = {
        "schema_version": MODEL_EXPORT_SCHEMA,
        "flowguard_schema_version": "1.0",
        "model_id": model_id,
        "parent_model_id": "skillguard.generated_skill.current",
        "functions": [
            {
                "function_id": function_id,
                "business_intent": "maintain the generated skill under one current SkillGuard contract",
                "owner_id": owner_id,
                "route_ids": [route_id],
            }
        ],
        "routes": [
            {
                "route_id": route_id,
                "function_id": function_id,
                "owner_id": owner_id,
                "step_ids": [action_step_id, success_step_id, blocked_step_id],
                "success_terminal_step_id": success_step_id,
                "blocked_terminal_step_id": blocked_step_id,
                "handoffs": [],
            }
        ],
        "steps": [
            {
                "step_id": action_step_id,
                "route_id": route_id,
                "owner_id": owner_id,
                "action_kind": "native",
                "terminal_kind": "",
                "prerequisite_step_ids": [],
            },
            {
                "step_id": success_step_id,
                "route_id": route_id,
                "owner_id": owner_id,
                "action_kind": "terminal",
                "terminal_kind": "success",
                "prerequisite_step_ids": [action_step_id],
            },
            {
                "step_id": blocked_step_id,
                "route_id": route_id,
                "owner_id": owner_id,
                "action_kind": "terminal",
                "terminal_kind": "blocked",
                "prerequisite_step_ids": [],
            },
        ],
        "obligations": [
            {
                "obligation_id": obligation_id,
                "invariant_id": invariant_id,
                "owner_step_ids": [action_step_id],
                "required": True,
            }
        ],
        "invariant_ids": [invariant_id],
        "claim_boundary": (
            "This portable model establishes the generated skill's current contract owner only; "
            "it does not prove target execution depth, semantic quality, installation, or release."
        ),
    }
    model_source = (
        '"""Portable FlowGuard export for the generated current contract scaffold."""\n\n'
        "FLOWGUARD_MODEL_MARKER = 'flowguard-executable-model'\n"
        f"EXPORT = {model!r}\n\n"
        "def export_contract_model():\n"
        "    return EXPORT\n"
    )
    binding = {
        "schema_version": BINDING_SOURCE_SCHEMA,
        "skill_id": skill_id,
        "repository_role": "skill_maintainer_source",
        "maintenance_unit_id": f"unit:{skill_id}",
        "member_skill_ids": [skill_id],
        "consumer_projection": {
            "projection_id": "projection:consumer-distribution",
            "prohibited_path_prefixes": [".skillguard/"],
            "prohibited_prompt_tokens": [
                "SkillGuard",
                ".skillguard",
                "skillguard.py",
            ],
            "release_manifest_path": "consumer-release.json",
        },
        "model_id": model_id,
        "model_path": ".skillguard/flowguard_contract_model.py",
        "confirmed": True,
        "integration_mode": "native-integrated",
        "native_route_owner": owner_id,
        "may_define_parallel_execution_route": False,
        "may_define_skillguard_runtime_route": False,
        "native_route_bindings": [
            {
                "binding_id": f"native:{skill_id}:generated-current",
                "native_route_id": route_id,
                "required_before_closure": True,
                "source": "SKILL.md",
            }
        ],
        "native_check_bindings": [
            {
                "binding_id": f"native-check:{skill_id}:generated-current",
                "native_check_id": check_id,
                "required": True,
                "evidence_source": "scripts/run_checks.py",
            }
        ],
        "implementation_paths": ["SKILL.md", "scripts/run_checks.py"],
        "step_bindings": [
            {
                "step_id": action_step_id,
                "action": {
                    "kind": "native",
                    "summary": "run the generated target-owned current check",
                },
                "check_ids": [check_id],
                "output_artifact_ids": [],
            }
        ],
        "checks": [
            {
                "check_id": check_id,
                "maintenance_unit_id": f"unit:{skill_id}",
                "member_skill_id": skill_id,
                "evidence_subject_id": f"subject:{skill_id}:generated-current",
                "semantic_check_id": f"semantic:{skill_id}:generated-current",
                "kind": "command",
                "command": "python",
                "args": ["scripts/run_checks.py"],
                "cwd_token": "repository_root",
                "input_selectors": [
                    {"kind": "path", "path": "SKILL.md"},
                    {"kind": "path", "path": "scripts/run_checks.py"},
                ],
                "expected": {"exit_code": 0},
                "timeout_seconds": 30,
                "evidence_class": "hard",
                "evidence_domain_id": "generated_skill_current",
                "execution_owner_id": owner_id,
                "covers_obligation_ids": [obligation_id],
            }
        ],
        "artifacts": [],
        "closure_profiles": [
            {
                "profile_id": "enforced",
                "required_obligation_ids": [obligation_id],
            }
        ],
        "judgment_rubrics": [],
        "claim_boundary": (
            "This generated binding proves only deterministic current contract structure. "
            "It does not prove target execution, semantic acceptance, installation, or release."
        ),
    }
    return model_source, binding


def compile_generated_current_contract(files: dict[str, str]) -> None:
    """Compile the generated current trio in an isolated portable root."""

    with tempfile.TemporaryDirectory(prefix="skillguard-generated-current-") as temp_dir:
        staged_root = Path(temp_dir)
        for relative, content in files.items():
            path = staged_root / Path(relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content.encode("utf-8"))
        result = compile_skill_contract(
            staged_root,
            repository_root=staged_root,
            write=True,
        )
        if not result.ok:
            details = "; ".join(
                f"{finding.code}@{finding.path}:{finding.message}"
                for finding in result.findings
            )
            raise SkillGuardCliError(
                "generate-skill",
                f"generated current contract did not compile: {details or result.status}",
                "generated_current_contract_blocked",
            )
        for relative in (
            ".skillguard/compiled-contract.json",
            ".skillguard/check-manifest.json",
        ):
            files[relative] = (staged_root / relative).read_text(encoding="utf-8")


def build_generate_skill_scaffold(blueprint: dict[str, Any], target: Path, input_relative: str) -> dict[str, str]:
    skill = blueprint.get("skill") if isinstance(blueprint.get("skill"), dict) else {}
    target_relative = public_relative_path(target)
    name = target.name
    description = single_line(skill.get("description"), f"Use when work falls inside the {name} skill boundary.")
    purpose = single_line(skill.get("purpose"), f"Maintain the {name} skill with explicit evidence and claim boundaries.")
    use_when = skill.get("use_when") if isinstance(skill.get("use_when"), list) else ["The request matches this generated skill scope."]
    do_not_use_when = (
        skill.get("do_not_use_when")
        if isinstance(skill.get("do_not_use_when"), list)
        else ["The request needs unsupported release, package, or external-service claims."]
    )
    workflow_steps = [
        "Inspect the current target files before making claims.",
        "Run deterministic checks that are available for the declared scope.",
        "Record reviewer judgment separately from deterministic evidence.",
        "Report blockers, skipped checks, residual risk, and claim boundary before closure.",
    ]
    hard_gates = [
        "Do not overwrite peer or maintainer work without an explicit repair scope.",
        "Do not treat generated scaffold files as acceptance evidence.",
        "Do not claim fixture coverage, packaged CLI support, suite automation, release readiness, or code-contract validation without current proof.",
    ]
    output_terms = ["evidence", "failures", "blockers", "skipped_checks", "residual_risk", "claim_boundary"]
    generated_at = "generated-scaffold-draft"
    claim_boundary = common_claim_boundary("generated scaffold")
    template_routing_guidance = "\n".join(
        ensure_under_root(skill_root() / relative_path)
        .read_text(encoding="utf-8")
        .strip()
        for relative_path in TEMPLATE_PROFILE_PROMPT_PATHS.values()
    )
    blueprint_trace = {
        "blueprint_id": blueprint.get("blueprint_id"),
        "source_input": input_relative,
        "workflow_mode": blueprint.get("workflow_mode"),
        "closure_scope": blueprint.get("closure_scope"),
        "evidence_policy": blueprint.get("evidence_policy"),
        "safe_edit_scope": blueprint.get("safe_edit_scope"),
        "phase_plan": blueprint.get("phase_plan"),
        "evidence_gates": blueprint.get("evidence_gates"),
        "handoffs": blueprint.get("handoffs"),
        "closure_report": blueprint.get("closure_report"),
        "residual_risk": blueprint.get("residual_risk"),
        "claim_boundary": blueprint.get("claim_boundary"),
    }

    skill_md = f"""---
name: {name}
description: {description}
---

# {name}

## Purpose

{purpose}

## Entrypoint Scope

This generated entrypoint is a scaffold for `{target_relative}`. It is not accepted until current target checks and reviewer judgment support that exact scope.

## Local Material Routing

- Use `references/README.md` for local reference notes.
- Use `assets/schemas/generated_record.schema.json` for scaffold record-shape notes.
- Use `assets/templates/check_report.template.json` for report-drafting notes.
- Use `scripts/run_checks.py` only as a local placeholder script.
- Use `fixtures/fixture-manifest.json` and `tests/test_smoke.py` as draft scaffolding inputs.
- Keep all ordinary runtime, data, imports, checks, and recovery instructions inside this target-owned tree.
- Run the target's own declared checks when the task requires validation.
- Do not depend on an author-maintenance package, receipt store, router, or hidden project state.

{template_routing_guidance}

## Entrypoint Acceptance Map

- `checked` requires current deterministic evidence for the declared scope.
- `needs-review` means semantic judgment is still required.
- `accepted` requires current evidence, visible skipped checks, no unresolved blockers, and reviewer acceptance.

## Use When

{markdown_list(use_when)}

## Do Not Use When

{markdown_list(do_not_use_when)}

## Required Workflow

{markdown_list(workflow_steps)}

## Hard Gates

{markdown_list(hard_gates)}

## Output Requirements

Every result must include these fields: {", ".join(output_terms)}.

## SkillGuard Maintenance

This directory is maintained as author source. Its `.skillguard` records are
private graduation evidence for the maintainer and are never part of the
consumer distribution. Ordinary use must rely only on the target-owned files
outside `.skillguard`.

## Provenance

Generated at `{generated_at}` from `{input_relative}`. {claim_boundary}
"""

    model_source, current_binding = generated_current_contract_sources(name)

    readme = f"""# {name}

This is a generated standalone skill scaffold for `{target_relative}`.

## Current Status

Status: draft scaffold only. The generated files do not prove activation, semantic correctness, fixture coverage, tests, suite automation, package publication, release readiness, code-contract validation, external services, or future AI behavior.

## Scaffold Contents

- `SKILL.md`
- `README.md`
- `references/`
- `assets/schemas/`
- `assets/templates/`
- `scripts/`
- `fixtures/`
- `tests/`

## Next Action

Inspect the generated target-owned files and replace every placeholder with native behavior and native checks before distribution.
"""

    fixture_manifest = {
        "schema_version": "skillguard.fixture_manifest.v1",
        "fixture_version": "draft",
        "checker_version": CHECKER_VERSION,
        "current_status": {
            "status": "needs-review",
            "notes": ["Generated fixture manifest is a placeholder and has not been executed."],
        },
        "fixtures": [
            {
                "fixture_id": "draft-smoke",
                "fixture_type": "positive",
                "target_rule": "Generated target contains SKILL.md.",
                "expected_decision": "pass",
                "status": "draft",
                "path": "tests/test_smoke.py",
                "known_limitations": ["This fixture is a scaffold placeholder only."],
            }
        ],
        "evidence": ["generate-skill-command-output"],
        "skipped_checks": ["Fixture execution is not performed by generate-skill."],
        "residual_risk": ["Fixture adequacy needs reviewer judgment before acceptance."],
        "claim_boundary": common_claim_boundary("fixture manifest"),
    }

    files: dict[str, str] = {
        "SKILL.md": skill_md,
        "README.md": readme,
        "references/README.md": f"# References\n\nDraft reference notes for `{name}`. Add current evidence before making acceptance claims.\n",
        "assets/schemas/generated_record.schema.json": json_block(
            {
                "title": f"{name} Generated Record",
                "type": "object",
                "required": ["schema_version", "target_path", "status", "evidence", "claim_boundary"],
                "properties": {
                    "schema_version": {"type": "string"},
                    "target_path": {"type": "string"},
                    "status": {"type": "string"},
                    "evidence": {"type": "array"},
                    "claim_boundary": {"type": "string"},
                },
                "additionalProperties": True,
            }
        ),
        "assets/templates/check_report.template.json": json_block(
            {
                "schema_version": "skillguard.check_report.v1",
                "target_path": target_relative,
                "target_type": "skill",
                "status": "draft",
                "decision": "block",
                "evidence": [],
                "failures": [],
                "blockers": ["replace this template with current evidence before closure"],
                "skipped_checks": [{"reason": "template only", "impact": "not passing evidence"}],
                "residual_risk": ["template must be replaced with current evidence"],
                "claim_boundary": common_claim_boundary("report template"),
            }
        ),
        "scripts/README.md": f"# Scripts\n\nPlaceholder scripts for `{name}`. Script output is not acceptance evidence until current checks run.\n",
        "scripts/run_checks.py": (
            '"""Generated local smoke-check placeholder."""\n\n'
            "from __future__ import annotations\n\n"
            "import json\n"
            "from pathlib import Path\n\n"
            "ROOT = Path(__file__).resolve().parents[1]\n"
            "payload = {\n"
            '    "schema_version": "generated.skill_smoke.current",\n'
            '    "decision": "pass" if (ROOT / "SKILL.md").is_file() else "block",\n'
            '    "target_path": ROOT.name,\n'
            '    "evidence": ["local SKILL.md existence check"],\n'
            '    "claim_boundary": "This generated smoke check only verifies SKILL.md presence and does not prove runtime checker execution, fixture coverage, CLI checks, tests, suite automation, package publication, code-contract validation, release readiness, external services, or future AI behavior."\n'
            "}\n"
            "print(json.dumps(payload, indent=2, sort_keys=True))\n"
        ),
        "fixtures/README.md": f"# Fixtures\n\nDraft fixture area for `{name}`. Add positive, negative, stale, privacy, and regression cases before claiming coverage.\n",
        "fixtures/fixture-manifest.json": json_block(fixture_manifest),
        "tests/README.md": f"# Tests\n\nDraft test area for `{name}`. Tests in this scaffold are placeholders until current behavior is implemented.\n",
        "tests/test_smoke.py": (
            '"""Generated placeholder smoke test."""\n\n'
            "from pathlib import Path\n\n"
            "def test_skill_md_exists():\n"
            "    assert (Path(__file__).resolve().parents[1] / 'SKILL.md').is_file()\n"
        ),
        ".skillguard/flowguard_contract_model.py": model_source,
        ".skillguard/contract-source.json": json_block(current_binding),
        ".skillguard/author-guidance.md": (
            "# Author maintenance\n\n"
            f"Generated from `{input_relative}` by the local maintenance command.\n\n"
            "This author-only record owns contract compilation, declared-check supervision, "
            "receipts, template selection, and graduation. It is excluded from every consumer distribution.\n"
        ),
    }
    compile_generated_current_contract(files)
    return files


def template_profile_parameters(blueprint: dict[str, Any]) -> dict[str, Any]:
    skill = blueprint.get("skill") if isinstance(blueprint.get("skill"), dict) else {}
    return {
        "skill_name": str(skill.get("name") or ""),
        "description": str(skill.get("description") or ""),
        "purpose": str(skill.get("purpose") or ""),
        "target_path": str(blueprint.get("target") or skill.get("target_path") or ""),
    }


def template_source_binding(role: str, path: Path) -> dict[str, str]:
    resolved = ensure_under_root(path)
    return {
        "role": role,
        "path": public_relative_path(resolved),
        "sha256": template_source_identity(resolved),
    }


def builtin_template_source_bindings(source_input_path: Path) -> list[dict[str, str]]:
    checker_path = Path(__file__).resolve()
    bindings = [
        template_source_binding("builder", checker_path),
        template_source_binding("source_input", source_input_path),
        template_source_binding("validator", checker_path),
    ]
    bindings.extend(
        template_source_binding(role, ensure_under_root(skill_root() / relative_path))
        for role, relative_path in TEMPLATE_PROFILE_PROMPT_PATHS.items()
    )
    return bindings


def template_prompt_bundle_hash(binding_index: dict[str, dict[str, str]]) -> str:
    return sha256_identity(
        {
            role: binding_index[role]["sha256"]
            for role in sorted(TEMPLATE_PROFILE_PROMPT_PATHS)
        }
    )


def template_profile_projection(profile: dict[str, Any]) -> dict[str, Any]:
    catalog = profile.get("catalog") if isinstance(profile.get("catalog"), dict) else {}
    selection = profile.get("selection_receipt") if isinstance(profile.get("selection_receipt"), dict) else {}
    applicability = profile.get("applicability_receipt") if isinstance(profile.get("applicability_receipt"), dict) else {}
    manifests = catalog.get("templates") if isinstance(catalog.get("templates"), list) else []
    return {
        "template_capability_inventory": [
            {
                "template_id": item.get("template_id"),
                "template_kind": item.get("template_kind"),
                "native_owner_id": item.get("native_owner_id"),
                "family_id": item.get("family_id"),
                "route_ids": item.get("route_ids", []),
                "builder_id": (item.get("builder") or {}).get("builder_id") if isinstance(item.get("builder"), dict) else None,
                "validator_ids": [
                    row.get("validator_id")
                    for row in item.get("validators", [])
                    if isinstance(row, dict)
                ],
            }
            for item in manifests
            if isinstance(item, dict)
        ],
        "template_candidates": selection.get("candidate_accounting", []),
        "template_applicability": applicability.get("results", []),
        "template_selection": {
            "status": selection.get("status"),
            "disposition": selection.get("disposition"),
            "selected_template_ids": selection.get("selected_template_ids", []),
            "composition_order": selection.get("composition_order", []),
            "field_owner_map": selection.get("field_owner_map", {}),
            "findings": selection.get("findings", []),
            "receipt_id": selection.get("receipt_id"),
            "receipt_hash": selection.get("receipt_hash"),
        },
        "template_preview": profile.get("materialized_preview", {}),
        "affected_components": profile.get("content_components", {}),
    }


def build_plan_template_profile(
    normalized: dict[str, Any],
    blueprint: dict[str, Any],
    input_path: Path,
    input_relative: str,
) -> dict[str, Any]:
    request = normalized.get("template_request") if isinstance(normalized.get("template_request"), dict) else {}
    if request.get("profile_kind") == "target_owned_selection":
        adapter_path = ensure_under_root(request["adapter_projection_path"])
        if not adapter_path.is_file():
            raise TemplateProfileError((f"template_source_missing:{public_relative_path(adapter_path)}",))
        records = compile_target_template_projection(load_json(adapter_path))
        return build_external_selection_profile(
            catalog_payload=records.catalog,
            native_route_receipt=records.native_route_receipt,
            applicability_receipt=records.applicability_receipt,
            parameters=request.get("parameters", {}),
            source_bindings=[
                template_source_binding("adapter_projection", adapter_path),
            ],
        )

    target = ensure_under_root(blueprint["target"])
    scaffold_files = build_generate_skill_scaffold(blueprint, target, input_relative)
    bindings = builtin_template_source_bindings(input_path)
    binding_index = {item["role"]: item for item in bindings}
    return build_builtin_scaffold_profile(
        parameters=template_profile_parameters(blueprint),
        artifact_paths=sorted(scaffold_files),
        scaffold_files=scaffold_files,
        source_input_hash=binding_index["source_input"]["sha256"],
        builder_content_hash=binding_index["builder"]["sha256"],
        validator_content_hash=binding_index["validator"]["sha256"],
        prompt_content_hash=template_prompt_bundle_hash(binding_index),
        source_bindings=bindings,
    )


def validate_template_profile_source_bindings(profile: dict[str, Any]) -> tuple[dict[str, dict[str, str]], list[str]]:
    bindings = profile.get("source_bindings") if isinstance(profile.get("source_bindings"), list) else []
    index: dict[str, dict[str, str]] = {}
    blockers: list[str] = []
    for item in bindings:
        if not isinstance(item, dict):
            blockers.append("template source binding must be an object")
            continue
        role = item.get("role")
        path_text = item.get("path")
        if not isinstance(role, str) or not isinstance(path_text, str):
            blockers.append("template source binding must declare string role and path")
            continue
        try:
            path = ensure_under_root(path_text)
        except ValueError:
            blockers.append(f"template source escapes repository boundary: {role}")
            continue
        if not path.is_file():
            blockers.append(f"template source is missing: {path_text}")
            continue
        current_hash = template_source_identity(path)
        if current_hash != item.get("sha256"):
            blockers.append(f"template source is stale: {role}:{path_text}")
        index[role] = {"role": role, "path": path_text, "sha256": current_hash}
    return index, blockers


def validate_generate_skill_template_profile(
    blueprint: dict[str, Any],
    target: Path,
) -> tuple[dict[str, Any], dict[str, str], list[str]]:
    blockers: list[str] = []
    scaffold_files: dict[str, str] = {}
    try:
        profile = validate_template_profile(blueprint.get("template_profile"))
    except TemplateProfileError as exc:
        return {}, {}, [f"template profile invalid: {finding}" for finding in exc.findings]
    source_index, source_blockers = validate_template_profile_source_bindings(profile)
    blockers.extend(source_blockers)
    if blockers:
        return profile, {}, blockers

    if profile.get("profile_kind") == "target_owned_selection":
        required_roles = {"adapter_projection"}
        if set(source_index) != required_roles:
            blockers.append("target-owned template profile source roles must equal adapter_projection")
        else:
            records = compile_target_template_projection(
                load_json(ensure_under_root(source_index["adapter_projection"]["path"]))
            )
            rebuilt = build_external_selection_profile(
                catalog_payload=records.catalog,
                native_route_receipt=records.native_route_receipt,
                applicability_receipt=records.applicability_receipt,
                parameters=profile.get("parameters", {}),
                source_bindings=list(source_index.values()),
            )
            if rebuilt.get("profile_hash") != profile.get("profile_hash"):
                blockers.append("target-owned template profile is stale after current source recomputation")
        blockers.append("target_native_builder_required: generic generate-skill cannot execute a target-owned template builder")
        return profile, {}, blockers

    required_roles = {"builder", "source_input", "validator", *TEMPLATE_PROFILE_PROMPT_PATHS}
    if set(source_index) != required_roles:
        return profile, {}, ["SkillGuard validated-base profile source roles are incomplete"]
    stable_input = str(blueprint.get("source_input") or source_index["source_input"]["path"])
    scaffold_files = build_generate_skill_scaffold(blueprint, target, stable_input)
    try:
        validate_builtin_profile_current(
            profile,
            parameters=template_profile_parameters(blueprint),
            artifact_paths=sorted(scaffold_files),
            scaffold_files=scaffold_files,
            source_input_hash=source_index["source_input"]["sha256"],
            builder_content_hash=source_index["builder"]["sha256"],
            validator_content_hash=source_index["validator"]["sha256"],
            prompt_content_hash=template_prompt_bundle_hash(source_index),
            source_bindings=list(source_index.values()),
        )
    except TemplateProfileError as exc:
        blockers.extend(f"template profile stale: {finding}" for finding in exc.findings)
    return profile, scaffold_files, blockers


def build_generate_skill_instance_receipt(
    template_profile: dict[str, Any],
    scaffold_files: dict[str, str],
    post_generation_checks: list[dict[str, Any]],
) -> dict[str, Any]:
    catalog = validate_template_catalog(template_profile["catalog"])
    selection = template_profile["selection_receipt"]
    selected_ids = list(selection.get("selected_template_ids", []))
    check_status_by_command = {
        str(item.get("command")): str(item.get("status"))
        for item in post_generation_checks
        if isinstance(item, dict)
    }
    builder_receipts: list[dict[str, Any]] = []
    validator_receipts: list[dict[str, Any]] = []
    generated_artifacts: list[dict[str, Any]] = []
    manifests = catalog.manifest_index()
    validator_command = {
        "check:generated-skill-static": "check-skill",
        "check:generated-skill-contract": "check-contract",
    }
    for template_id in selected_ids:
        manifest = manifests[template_id]
        builder = manifest.payload["builder"]
        builder_receipts.append(
            seal_builder_receipt(
                {
                    "template_id": template_id,
                    "manifest_digest": manifest.digest,
                    "builder_id": builder["builder_id"],
                    "builder_content_hash": builder["content_hash"],
                    "status": "passed",
                    "claim_boundary": "The generic scaffold was materialized; target acceptance remains separate.",
                }
            )
        )
        for artifact in manifest.payload["artifacts"]:
            relative_path = artifact["path_template"]
            content = scaffold_files.get(relative_path, "")
            generated_artifacts.append(
                {
                    "template_id": template_id,
                    "artifact_id": artifact["artifact_id"],
                    "manifest_digest": manifest.digest,
                    "relative_path": relative_path,
                    "sha256": sha256_identity(
                        content.replace("\r\n", "\n").replace("\r", "\n")
                    ),
                }
            )
        for validator in manifest.payload["validators"]:
            command = validator_command.get(validator["check_id"], "")
            observed = check_status_by_command.get(command, "not_run")
            validator_status = {
                "pass": "passed",
                "fail": "failed",
                "block": "blocked",
                "skip": "skipped",
            }.get(observed, observed)
            validator_receipts.append(
                seal_validator_receipt(
                    {
                        "template_id": template_id,
                        "manifest_digest": manifest.digest,
                        "validator_id": validator["validator_id"],
                        "check_id": validator["check_id"],
                        "validator_content_hash": validator["content_hash"],
                        "status": validator_status,
                        "claim_boundary": "This receipt covers only the mapped generated-skill native check.",
                    }
                )
            )
    return build_instance_receipt(
        selection_receipt_payload=selection,
        catalog_payload=catalog.payload,
        route_receipt_payload=template_profile["native_route_receipt"],
        applicability_receipt_payload=template_profile["applicability_receipt"],
        parameters={template_id: template_profile.get("parameters", {}) for template_id in selected_ids},
        builder_receipts=builder_receipts,
        generated_artifacts=generated_artifacts,
        unresolved_placeholders=unresolved_placeholders(scaffold_files),
        validator_receipts=validator_receipts,
    )


def preflight_generate_skill_writes(
    target: Path, files: dict[str, str]
) -> tuple[list[str], list[str], list[str], list[dict[str, str]]]:
    command_name = "generate-skill"
    created_files: list[str] = []
    existing_files: list[str] = []
    conflicts: list[str] = []
    directory_conflicts: list[dict[str, str]] = []
    directory_entries = generate_skill_required_directory_entries(target)
    for relative, path, role in directory_entries:
        if path.exists() and not path.is_dir():
            path_text = public_relative_path(path)
            conflict = {
                "conflict_kind": "required_directory_type_conflict",
                "conflicting_path": path_text,
                "expected_generated_owner": command_name,
                "expected_directory_role": role,
                "required_directory": relative or ".",
                "safe_remediation_path": path_text,
                "safe_remediation": (
                    f"Move, rename, or remove {path_text} before rerunning {command_name}; "
                    "no scaffold files were written."
                ),
            }
            directory_conflicts.append(conflict)
            conflicts.append(
                f"required scaffold directory conflict: {path_text} exists but must be a directory for {role}; "
                f"safe remediation path: {path_text}"
            )
    if directory_conflicts:
        return created_files, existing_files, conflicts, directory_conflicts

    ownership_conflicts = preflight_output_tree_ownership(
        command_name=command_name,
        target=target,
        files=files,
        directory_entries=directory_entries,
    )
    directory_conflicts.extend(ownership_conflicts)
    conflicts.extend(preflight_conflict_blocker(conflict, command_name) for conflict in ownership_conflicts)

    for relative, content in files.items():
        path = scaffold_path(target, relative)
        if path.exists():
            if not path.is_file():
                conflict = structured_file_preflight_conflict(
                    command_name=command_name,
                    path=path,
                    conflict_kind="existing_output_type_mismatch",
                    safe_remediation=(
                        f"Move, rename, or remove {public_relative_path(path)} before rerunning {command_name}; "
                        "the generator expected a file and wrote nothing."
                    ),
                )
                directory_conflicts.append(conflict)
                conflicts.append(f"{public_relative_path(path)} exists but is not a file")
            elif path.read_text(encoding="utf-8") == content:
                existing_files.append(public_relative_path(path))
            else:
                conflict = structured_file_preflight_conflict(
                    command_name=command_name,
                    path=path,
                    conflict_kind="existing_file_content_mismatch",
                    safe_remediation=(
                        f"Move, rename, or remove {public_relative_path(path)} before rerunning {command_name}; "
                        "the generator does not overwrite or merge differing file content."
                    ),
                )
                directory_conflicts.append(conflict)
                conflicts.append(f"{public_relative_path(path)} exists with different content")
        else:
            created_files.append(public_relative_path(path))
    if target.exists() and created_files and not conflicts:
        conflict = {
            "conflict_kind": "existing_target_requires_atomic_replacement",
            "conflicting_path": public_relative_path(target),
            "expected_generated_owner": command_name,
            "safe_remediation_path": public_relative_path(target),
            "safe_remediation": (
                "Move or rename the existing target before generation. A new scaffold is activated only by one atomic "
                "directory replacement; SkillGuard does not partially fill an existing directory."
            ),
        }
        directory_conflicts.append(conflict)
        conflicts.append(
            f"existing target requires atomic direct-current replacement: {public_relative_path(target)}"
        )
    if conflicts:
        return [], existing_files, conflicts, directory_conflicts
    return created_files, existing_files, conflicts, directory_conflicts


def write_generate_skill_scaffold(target: Path, files: dict[str, str]) -> tuple[list[str], list[str]]:
    created_dirs: list[str] = []
    created_files: list[str] = []
    required_dirs = [scaffold_path(target, relative) for relative in GENERATE_SKILL_REQUIRED_DIRECTORIES]
    for directory in [target, *required_dirs]:
        if not directory.exists():
            directory.mkdir(parents=True)
            created_dirs.append(public_relative_path(directory))
    for relative, content in files.items():
        path = scaffold_path(target, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            # Generated authority uses canonical LF bytes on every platform.
            # Windows text-mode newline translation must not make a freshly
            # compiled contract stale immediately after installation.
            path.write_bytes(content.encode("utf-8"))
            created_files.append(public_relative_path(path))
    return created_dirs, created_files


def extract_suite_blueprint(raw_input: Any) -> tuple[dict[str, Any], list[str]]:
    if isinstance(raw_input, dict) and raw_input.get("schema_version") == "skillguard.suite_blueprint.v1":
        return raw_input, []
    if isinstance(raw_input, dict):
        nested = raw_input.get("suite_blueprint")
        if isinstance(nested, dict):
            return nested, []
    return {}, ["input must be a Suite Blueprint object or a result containing suite_blueprint"]


def resolve_generate_suite_target(blueprint: dict[str, Any], blockers: list[str]) -> Path | None:
    target_text = blueprint.get("target") or blueprint.get("target_path")
    if not isinstance(target_text, str) or not target_text.strip():
        blockers.append("Suite Blueprint must declare a non-empty target path")
        return None
    if Path(target_text).is_absolute():
        blockers.append("suite target path must be repository-relative; absolute target paths are blocked")
        return None
    try:
        target = ensure_under_root(target_text)
    except ValueError:
        blockers.append("suite target path must stay under the repository root")
        return None
    repo = repository_root().resolve()
    if target.resolve() == repo:
        blockers.append("suite target path must not be the repository root")
        return None
    if target.exists() and not target.is_dir():
        blockers.append(f"suite target path exists but is not a directory: {public_relative_path(target)}")
        return None
    return target


def normalized_suite_members(blueprint: dict[str, Any], target: Path | None, blockers: list[str]) -> list[dict[str, str]]:
    raw_members = blueprint.get("member_skills")
    if raw_members is None:
        raw_members = blueprint.get("members") or blueprint.get("included_skills")
    if not isinstance(raw_members, list) or not raw_members:
        blockers.append("Suite Blueprint member_skills must be a non-empty array")
        return []

    members: list[dict[str, str]] = []
    seen_names: set[str] = set()
    seen_paths: set[str] = set()
    member_root = target / "members" if target is not None else None
    for index, item in enumerate(raw_members):
        if not isinstance(item, dict):
            blockers.append(f"member_skills[{index}] must be an object")
            continue
        raw_name = item.get("name") or item.get("skill_name")
        if not isinstance(raw_name, str) or not raw_name.strip():
            blockers.append(f"member_skills[{index}] must declare a non-empty name")
            continue
        name = slugify_identifier(raw_name)
        if not name:
            blockers.append(f"member_skills[{index}] name does not contain a safe identifier")
            continue
        if name != raw_name.strip():
            blockers.append(f"member_skills[{index}] name must already be a safe slug: {name}")
            continue
        if name in seen_names:
            blockers.append(f"duplicate suite member name: {name}")
            continue
        child_target = member_root / name if member_root is not None else None
        raw_path = item.get("path") or item.get("target") or item.get("target_path")
        if isinstance(raw_path, str) and raw_path.strip() and child_target is not None:
            if Path(raw_path).is_absolute():
                blockers.append(f"member {name}: absolute member paths are not allowed")
                continue
            try:
                declared_path = ensure_under_root(raw_path)
            except ValueError:
                blockers.append(f"member {name}: path escapes repository boundary")
                continue
            try:
                declared_path.resolve().relative_to(member_root.resolve())
            except ValueError:
                blockers.append(f"member {name}: path must stay under the suite members directory")
                continue
            if declared_path.name != name:
                blockers.append(f"member {name}: path directory name must match member name")
                continue
            child_target = declared_path
        if child_target is None:
            continue
        child_relative = public_relative_path(child_target)
        if child_relative in seen_paths:
            blockers.append(f"duplicate suite member path: {child_relative}")
            continue
        suite_relative = child_target.resolve().relative_to(target.resolve()).as_posix() if target is not None else f"members/{name}"
        seen_names.add(name)
        seen_paths.add(child_relative)
        members.append(
            {
                "name": name,
                "path": child_relative,
                "suite_relative": suite_relative,
                "role": single_line(item.get("role"), "suite member"),
                "description": single_line(
                    item.get("description"), f"Use when work falls inside the {name} suite member boundary."
                ),
                "purpose": single_line(
                    item.get("purpose"), f"Maintain the {name} suite member with current evidence and bounded claims."
                ),
            }
        )
    return members


def validate_generate_suite_blueprint(blueprint: dict[str, Any]) -> tuple[Path | None, list[dict[str, str]], list[str]]:
    blockers: list[str] = []
    if blueprint.get("schema_version") != "skillguard.suite_blueprint.v1":
        blockers.append("Suite Blueprint schema_version must be skillguard.suite_blueprint.v1")
    for field in GENERATE_SUITE_REQUIRED_BLUEPRINT_FIELDS:
        if field not in blueprint:
            blockers.append(f"Suite Blueprint missing required field: {field}")
    if blueprint.get("workflow_mode") not in {"suite", "create"}:
        blockers.append("generate-suite supports Suite Blueprints with workflow_mode=suite or workflow_mode=create")

    suite_name = blueprint.get("suite_name")
    if not isinstance(suite_name, str) or not suite_name.strip():
        blockers.append("Suite Blueprint suite_name must be a non-empty string")
        suite_name = ""
    safe_edit_scope = blueprint.get("safe_edit_scope")
    if not isinstance(safe_edit_scope, dict):
        blockers.append("Suite Blueprint field safe_edit_scope must be an object")
        safe_edit_scope = {}

    target = resolve_generate_suite_target(blueprint, blockers)
    if target is not None and suite_name:
        if slugify_identifier(suite_name) != target.name and suite_name != target.name:
            blockers.append("Suite Blueprint suite_name must match the target directory name")
        allowed_write_paths = safe_edit_scope.get("allowed_write_paths", [])
        if isinstance(allowed_write_paths, list) and allowed_write_paths:
            allowed_roots: list[Path] = []
            for path_text in allowed_write_paths:
                if not isinstance(path_text, str):
                    blockers.append("safe_edit_scope.allowed_write_paths entries must be strings")
                    continue
                try:
                    allowed_roots.append(ensure_under_root(path_text))
                except ValueError:
                    blockers.append(f"safe_edit_scope.allowed_write_paths entry escapes repository boundary: {path_text}")
            if allowed_roots and not relative_to_any(target, allowed_roots):
                blockers.append("suite target path is outside safe_edit_scope.allowed_write_paths")
        elif allowed_write_paths not in ([], None):
            blockers.append("safe_edit_scope.allowed_write_paths must be an array when supplied")

    members = normalized_suite_members(blueprint, target, blockers)
    return target, members, blockers


def suite_required_directory_entries(target: Path, members: list[dict[str, str]]) -> list[tuple[str, Path, str]]:
    entries: list[tuple[str, Path, str]] = [("", target, "suite scaffold root")]
    seen = {""}

    def add_directory(relative: str, role: str) -> None:
        parts = relative.split("/")
        for index in range(1, len(parts)):
            parent_relative = "/".join(parts[:index])
            if parent_relative not in seen:
                entries.append((parent_relative, scaffold_path(target, parent_relative), "suite scaffold parent directory"))
                seen.add(parent_relative)
        if relative not in seen:
            entries.append((relative, scaffold_path(target, relative), role))
            seen.add(relative)

    for relative in GENERATE_SUITE_REQUIRED_DIRECTORIES:
        role = GENERATE_SUITE_REQUIRED_DIRECTORY_ROLES.get(relative, f"required suite scaffold directory {relative}")
        add_directory(relative, role)
    for member in members:
        child_relative = member.get("suite_relative", f"members/{member['name']}")
        add_directory(child_relative, f"child skill root for {member['name']}")
        child_target = scaffold_path(target, child_relative)
        for _relative, path, role in generate_skill_required_directory_entries(child_target):
            path_relative = public_relative_path(path)
            try:
                suite_relative = path.relative_to(target.resolve()).as_posix()
            except ValueError:
                suite_relative = path_relative
            if suite_relative not in seen:
                entries.append((suite_relative, path, f"child {member['name']} {role}"))
                seen.add(suite_relative)
    return entries


def build_suite_child_blueprint(
    suite_blueprint: dict[str, Any],
    member: dict[str, str],
    source_input: str,
) -> dict[str, Any]:
    member_name = member["name"]
    target_path = member["path"]
    return {
        "schema_version": "skillguard.skill_blueprint.v1",
        "blueprint_id": f"{suite_blueprint.get('suite_name', 'suite')}.{member_name}.skill_blueprint.v1",
        "target": target_path,
        "workflow_mode": "create",
        "closure_scope": "generated suite child scaffold only",
        "evidence_policy": suite_blueprint.get("evidence_policy"),
        "safe_edit_scope": {
            "target_file_writes_allowed": True,
            "allowed_write_paths": [target_path],
            "source": "generate-suite child scaffold",
        },
        "phase_plan": [
            "Create draft child skill scaffold.",
            "Record generated child check evidence for suite-level review.",
            "Run current child skill checks before acceptance.",
        ],
        "evidence_gates": [
            "Child SKILL.md exists under the suite member root.",
            "Child .skillguard records remain draft until current checks run.",
            "Suite-level acceptance must consume current child evidence.",
        ],
        "handoffs": [
            {
                "from": "generate-suite",
                "to": "child skill maintainer",
                "reason": "Generated child scaffold needs current review before acceptance.",
            }
        ],
        "closure_report": {
            "status": "draft",
            "source_input": source_input,
            "suite_name": suite_blueprint.get("suite_name"),
        },
        "residual_risk": [
            "Generated child skill scaffold still needs current target checks and reviewer judgment before acceptance."
        ],
        "claim_boundary": common_claim_boundary("generated suite child scaffold"),
        "skill": {
            "name": member_name,
            "description": member["description"],
            "purpose": member["purpose"],
            "use_when": [f"The request falls inside the {member_name} suite member boundary."],
            "do_not_use_when": [
                "The request needs unsupported suite automation, release, package, external-service, or future-AI claims."
            ],
        },
    }


def suite_child_check_report(member: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": "skillguard.check_report.v1",
        "target_path": member["path"],
        "target_type": "skill",
        "status": "pass",
        "checker_version": CHECKER_VERSION,
        "current_identity": {
            "checker_version": CHECKER_VERSION,
            "fixture_version": "generated-suite-draft",
            "notes": "Generated child entrypoint presence evidence only.",
        },
        "checks": [
            {
                "check_id": "generate-suite:child-skill-entrypoint",
                "name": "Generated child SKILL.md",
                "required": True,
                "status": "pass",
                "evidence_ids": [f"{member['name']}-skill-md"],
                "summary": "Child skill entrypoint is planned and generated under the suite member root.",
            }
        ],
        "evidence": [
            {
                "evidence_id": f"{member['name']}-skill-md",
                "kind": "file",
                "fresh": True,
                "summary": "Generated child skill entrypoint file.",
                "source_path": f"{member['path']}/SKILL.md",
            }
        ],
        "failures": [],
        "blockers": [],
        "skipped_checks": [
            {
                "check_id": "child-semantic-review",
                "reason": "generate-suite creates a draft scaffold and does not perform semantic child skill acceptance.",
                "required": False,
                "status_impact": "Not a pass claim for target acceptance.",
            }
        ],
        "residual_risk": [
            "This report only supports generated child entrypoint presence; current child checks and reviewer judgment remain required."
        ],
        "claim_boundary": common_claim_boundary("generated child check report"),
    }


def build_generate_suite_scaffold(
    blueprint: dict[str, Any],
    target: Path,
    members: list[dict[str, str]],
    input_relative: str,
) -> dict[str, str]:
    suite_name = str(blueprint.get("suite_name") or target.name)
    target_relative = public_relative_path(target)
    suite_root_relative = f"{target_relative}/.skillguard/suite"
    member_root_relative = f"{target_relative}/members"
    child_check_paths = {member["name"]: f"evidence/{member['name']}_check_report.json" for member in members}
    claim_boundary = common_claim_boundary("generated suite scaffold")

    suite_readme = f"""# {suite_name}

This is a generated SkillGuard suite scaffold for `{target_relative}`.

## Current Status

Status: draft suite scaffold only. The generated files do not prove child skill acceptance, runtime checker execution, fixture coverage, tests, suite automation, package publication, release readiness, code-contract validation, external services, or future AI behavior.

## Scaffold Contents

- `.skillguard/suite/suite-map.json`
- `.skillguard/suite/suite-contract.json`
- `.skillguard/suite/evidence/`
- `.skillguard/suite/reports/`
- `members/`

## Next Action

Run current child skill checks and suite checks before making any suite acceptance claim.
"""

    included_for_map = [
        {
            "name": member["name"],
            "path": member["path"],
            "role": member["role"],
            "status": "checked",
            "evidence_location": child_check_paths[member["name"]],
            "required": True,
            "owner": "generated-suite",
            "residual_risk": [
                "Generated child status is bounded to entrypoint presence until current checks and review run."
            ],
        }
        for member in members
    ]
    included_for_contract = [
        {
            "name": member["name"],
            "path": member["path"],
            "role": member["role"],
            "status": "checked",
            "evidence_source": child_check_paths[member["name"]],
            "owner": "generated-suite",
            "residual_risk": [
                "Generated child status is bounded to entrypoint presence until current checks and review run."
            ],
        }
        for member in members
    ]
    relationships = [
        {
            "from_skill": "suite",
            "to_skill": member["name"],
            "relationship_type": "parent_child",
            "notes": "Generated suite parent tracks child evidence without promoting draft child work to acceptance.",
        }
        for member in members
    ]
    routing_hints = [
        {
            "task_shape": f"{member['name']} scoped maintenance",
            "preferred_skill": member["name"],
            "non_use_boundary": "Do not use this generated suite scaffold for release, package, automation, or future AI claims.",
            "conflict_rule": "Use direct child evidence and report missing, stale, blocked, or skipped child work visibly.",
        }
        for member in members
    ]
    suite_map = {
        "schema_version": "skillguard.suite_map.v1",
        "suite_name": suite_name,
        "target_path": suite_root_relative,
        "status": "checked",
        "included_skills": included_for_map,
        "relationships": relationships,
        "routing_hints": routing_hints,
        "evidence_expectations": [
            "Checked child status requires a direct generated child check report.",
            "Suite closure requires current child evidence and must not use progress ledgers or runtime ids as closure proof.",
        ],
        "maintenance_ownership": [
            "Regenerate or review suite records after child skill, checker, evidence, or suite contract changes."
        ],
        "current_identity": {
            "schema_boundary": f"{suite_name}.generated-suite-draft with {CHECKER_VERSION}",
            "rejected_noncurrent_shapes": [],
        },
        "evidence": ["evidence/source_blueprint_trace.json", "evidence/suite_closure.json"],
        "blockers": [],
        "residual_risk": [
            "Generated suite records support scaffold review only; child skill acceptance remains separate."
        ],
        "claim_boundary": claim_boundary,
    }
    suite_contract = {
        "schema_version": "skillguard.suite_contract.v2",
        "suite_name": suite_name,
        "purpose": single_line(
            blueprint.get("purpose"), f"Maintain the {suite_name} generated suite with explicit child evidence boundaries."
        ),
        "target_path": suite_root_relative,
        "status": "checked",
        "included_skills": included_for_contract,
        "routing": [
            {
                "use_case": f"{member['name']} scoped maintenance",
                "skill": member["name"],
                "conflict_resolution": "Use direct child evidence and keep suite summaries bounded to current child status.",
            }
            for member in members
        ],
        "dependencies": [
            {
                "name": member["name"],
                "dependency_type": "skill",
                "required": True,
                "status": "checked",
            }
            for member in members
        ],
        "independent_evidence_rules": [
            "Each child requires its own direct check report for checked status.",
            "No child or suite summary may borrow another child's test result.",
            "Progress ledgers, runtime ids, and chat text cannot satisfy suite closure.",
        ],
        "current_identity": {
            "suite_version": "generated-suite-draft",
            "checker_version": CHECKER_VERSION,
            "current_notes": [
                "The generated suite uses current suite map and suite contract schema shapes.",
                "The generated suite intentionally avoids broad release, package, automation, and future-AI claims.",
            ],
        },
        "validation_layers": [
            "Schema validation through local suite record commands.",
            "Suite member path and evidence checks through local check-suite command.",
            "Separate child check-skill invocations before acceptance.",
        ],
        "maintenance_ownership": [
            "Refresh generated suite records after child path, evidence, checker, or claim-boundary changes."
        ],
        "evidence": ["evidence/source_blueprint_trace.json", "evidence/suite_closure.json"],
        "blockers": [],
        "skipped_checks": [
            "generate-suite does not run semantic child review, fixture execution, package installation, release checks, suite automation, or code-contract validation."
        ],
        "residual_risk": [
            "Generated suite contract remains draft-scaffold evidence until current child checks and reviewer judgment run."
        ],
        "claim_boundary": claim_boundary,
    }
    source_trace = {
        "schema_version": "skillguard.suite_blueprint_trace.v1",
        "suite_name": suite_name,
        "target_path": target_relative,
        "source_input": input_relative,
        "workflow_mode": blueprint.get("workflow_mode"),
        "evidence_policy": blueprint.get("evidence_policy"),
        "member_skills": [{"name": member["name"], "path": member["path"], "role": member["role"]} for member in members],
        "claim_boundary": claim_boundary,
    }
    suite_closure = {
        "schema_version": "skillguard.closure.v1",
        "target_path": suite_root_relative,
        "target_type": "suite",
        "status": "closed_with_evidence",
        "closure_decision": "closed_with_evidence",
        "decision_reason": "Generated suite scaffold includes child skill entrypoint evidence records for the declared members.",
        "closure_scope": "generated suite scaffold only",
        "checks": [
            {
                "check_id": "generate-suite:child-entrypoint-evidence",
                "name": "Generated child evidence",
                "required": True,
                "status": "pass",
                "summary": "Each declared child has a generated check report and SKILL.md scaffold path.",
            }
        ],
        "evidence": [
            {
                "evidence_id": f"{member['name']}-check-report",
                "kind": "json",
                "fresh": True,
                "summary": "Generated child entrypoint check report.",
                "source_path": child_check_paths[member["name"]],
            }
            for member in members
        ],
        "failures": [],
        "blockers": [],
        "skipped_checks": [],
        "residual_risk": [
            "Closure is bounded to generated scaffold presence and does not accept child skill semantics."
        ],
        "claim_boundary": claim_boundary,
    }
    suite_generation_report = {
        "schema_version": "skillguard.check_report.v1",
        "target_path": suite_root_relative,
        "target_type": "suite",
        "status": "pass",
        "checker_version": CHECKER_VERSION,
        "current_identity": {
            "checker_version": CHECKER_VERSION,
            "fixture_version": "generated-suite-draft",
            "notes": "Generated suite scaffold presence evidence only.",
        },
        "checks": [
            {
                "check_id": "generate-suite:suite-records",
                "name": "Generated suite records",
                "required": True,
                "status": "pass",
                "evidence_ids": ["suite-map", "suite-contract"],
                "summary": "Suite map and suite contract are generated for static suite review.",
            },
            {
                "check_id": "generate-suite:child-records",
                "name": "Generated child records",
                "required": True,
                "status": "pass",
                "evidence_ids": [f"{member['name']}-check-report" for member in members],
                "summary": "Generated child check records are present for declared members.",
            },
        ],
        "evidence": [
            {
                "evidence_id": "suite-map",
                "kind": "json",
                "fresh": True,
                "summary": "Generated suite map.",
                "source_path": f"{suite_root_relative}/suite-map.json",
            },
            {
                "evidence_id": "suite-contract",
                "kind": "json",
                "fresh": True,
                "summary": "Generated suite contract.",
                "source_path": f"{suite_root_relative}/suite-contract.json",
            },
        ]
        + [
            {
                "evidence_id": f"{member['name']}-check-report",
                "kind": "json",
                "fresh": True,
                "summary": "Generated child entrypoint check report.",
                "source_path": f"{suite_root_relative}/{child_check_paths[member['name']]}",
            }
            for member in members
        ],
        "failures": [],
        "blockers": [],
        "skipped_checks": [
            {
                "check_id": "suite-semantic-acceptance",
                "reason": "generate-suite creates a draft scaffold and does not run semantic suite acceptance.",
                "required": False,
                "status_impact": "Not a pass claim for suite acceptance.",
            }
        ],
        "residual_risk": [
            "Generated suite scaffold still needs current check-suite and child check-skill evidence before acceptance."
        ],
        "claim_boundary": claim_boundary,
    }

    files: dict[str, str] = {
        "README.md": suite_readme,
        ".skillguard/suite/suite-map.json": json_block(suite_map),
        ".skillguard/suite/suite-contract.json": json_block(suite_contract),
        ".skillguard/suite/evidence/source_blueprint_trace.json": json_block(source_trace),
        ".skillguard/suite/evidence/suite_closure.json": json_block(suite_closure),
        ".skillguard/suite/reports/suite_generation_report.json": json_block(suite_generation_report),
    }
    for member in members:
        child_target = repository_root() / member["path"]
        child_blueprint = build_suite_child_blueprint(blueprint, member, input_relative)
        child_files = build_generate_skill_scaffold(child_blueprint, child_target, input_relative)
        child_relative = member.get("suite_relative", f"members/{member['name']}")
        for relative, content in child_files.items():
            files[f"{child_relative}/{relative}"] = content
        files[f".skillguard/suite/evidence/{member['name']}_check_report.json"] = json_block(suite_child_check_report(member))
    return files


def preflight_generate_suite_writes(
    target: Path, members: list[dict[str, str]], files: dict[str, str]
) -> tuple[list[str], list[str], list[str], list[dict[str, str]]]:
    command_name = "generate-suite"
    created_files: list[str] = []
    existing_files: list[str] = []
    conflicts: list[str] = []
    directory_conflicts: list[dict[str, str]] = []
    directory_entries = suite_required_directory_entries(target, members)
    for relative, path, role in directory_entries:
        if path.exists() and not path.is_dir():
            path_text = public_relative_path(path)
            conflict = {
                "conflict_kind": "required_directory_type_conflict",
                "conflicting_path": path_text,
                "expected_generated_owner": command_name,
                "expected_directory_role": role,
                "required_directory": relative or ".",
                "safe_remediation_path": path_text,
                "safe_remediation": (
                    f"Move, rename, or remove {path_text} before rerunning {command_name}; "
                    "no suite or child scaffold files were written."
                ),
            }
            directory_conflicts.append(conflict)
            conflicts.append(
                f"required suite scaffold directory conflict: {path_text} exists but must be a directory for {role}; "
                f"safe remediation path: {path_text}"
            )
    if directory_conflicts:
        return created_files, existing_files, conflicts, directory_conflicts

    ownership_conflicts = preflight_output_tree_ownership(
        command_name=command_name,
        target=target,
        files=files,
        directory_entries=directory_entries,
    )
    directory_conflicts.extend(ownership_conflicts)
    conflicts.extend(preflight_conflict_blocker(conflict, command_name) for conflict in ownership_conflicts)

    for relative, content in files.items():
        path = scaffold_path(target, relative)
        if path.exists():
            if not path.is_file():
                conflict = structured_file_preflight_conflict(
                    command_name=command_name,
                    path=path,
                    conflict_kind="existing_output_type_mismatch",
                    safe_remediation=(
                        f"Move, rename, or remove {public_relative_path(path)} before rerunning {command_name}; "
                        "the generator expected a file and wrote nothing."
                    ),
                )
                directory_conflicts.append(conflict)
                conflicts.append(f"{public_relative_path(path)} exists but is not a file")
            elif path.read_text(encoding="utf-8") == content:
                existing_files.append(public_relative_path(path))
            else:
                conflict = structured_file_preflight_conflict(
                    command_name=command_name,
                    path=path,
                    conflict_kind="existing_file_content_mismatch",
                    safe_remediation=(
                        f"Move, rename, or remove {public_relative_path(path)} before rerunning {command_name}; "
                        "the generator does not overwrite or merge differing file content."
                    ),
                )
                directory_conflicts.append(conflict)
                conflicts.append(f"{public_relative_path(path)} exists with different content")
        else:
            created_files.append(public_relative_path(path))
    if conflicts:
        return [], existing_files, conflicts, directory_conflicts
    return created_files, existing_files, conflicts, directory_conflicts


def write_generate_suite_scaffold(
    target: Path, members: list[dict[str, str]], files: dict[str, str]
) -> tuple[list[str], list[str]]:
    created_dirs: list[str] = []
    created_files: list[str] = []
    for _relative, directory, _role in suite_required_directory_entries(target, members):
        if not directory.exists():
            directory.mkdir(parents=True)
            created_dirs.append(public_relative_path(directory))
    for relative, content in files.items():
        path = scaffold_path(target, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(content, encoding="utf-8")
            created_files.append(public_relative_path(path))
    return created_dirs, created_files


def invoke_post_generation_check(command_name: str, argv: list[str]) -> tuple[int, dict[str, Any] | None, str]:
    if command_name == "check-skill":
        command = check_skill
    elif command_name == "check-contract":
        command = check_contract
    elif command_name == "check-suite":
        command = check_suite
    else:
        return 1, None, f"unsupported post-generation command: {command_name}"

    stdout = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout):
            exit_code = command(argv)
    except Exception as exc:  # pragma: no cover - defensive around generated-artifact validation
        return 1, None, f"{type(exc).__name__}: {exc}"

    raw_output = stdout.getvalue().strip()
    if not raw_output:
        return exit_code, None, "post-generation command produced no JSON output"
    try:
        parsed = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        return exit_code, None, f"post-generation command JSON parse failed: {exc}"
    if not isinstance(parsed, dict):
        return exit_code, None, "post-generation command output was not a JSON object"
    return exit_code, parsed, ""


def build_post_generation_check_result(
    *,
    check_id: str,
    command_name: str,
    argv: list[str],
    artifact_path: str,
    expected_report_target: str | None = None,
) -> dict[str, Any]:
    expected_target = expected_report_target or artifact_path
    entry: dict[str, Any] = {
        "check_id": check_id,
        "command": command_name,
        "argv": argv,
        "artifact_path": artifact_path,
        "expected_report_target": expected_target,
        "skipped": False,
    }
    exit_code, report, invocation_error = invoke_post_generation_check(command_name, argv)
    entry["exit_code"] = exit_code
    if invocation_error:
        entry["status"] = "block"
        entry["reason"] = invocation_error
        return entry
    assert report is not None

    reported_decision = str(report.get("decision", ""))
    reported_target = str(report.get("target_path", ""))
    report_checks = report.get("checks", [])
    entry["reported_decision"] = reported_decision
    entry["reported_target_path"] = reported_target
    entry["reported_failures"] = report.get("failures", []) if isinstance(report.get("failures"), list) else []
    entry["reported_blockers"] = report.get("blockers", []) if isinstance(report.get("blockers"), list) else []
    entry["reported_check_statuses"] = [
        {
            "check_id": check.get("check_id"),
            "status": check.get("status"),
        }
        for check in report_checks
        if isinstance(check, dict)
    ]
    entry["files_inspected"] = report.get("files_inspected", []) if isinstance(report.get("files_inspected"), list) else []

    if reported_target != expected_target:
        entry["status"] = "fail"
        entry["reason"] = "reported_target_path_mismatch"
    elif reported_decision != "pass" or exit_code != 0:
        entry["status"] = "block" if reported_decision == "block" or entry["reported_blockers"] else "fail"
        entry["reason"] = "post_generation_check_did_not_pass"
    else:
        entry["status"] = "pass"
        entry["reason"] = "post_generation_check_passed"
    return entry


def post_generation_check_messages(checks: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    blockers: list[str] = []
    if not checks:
        blockers.append("post-generation validation was not run")
        return failures, blockers
    for check in checks:
        if check.get("status") == "pass":
            continue
        reported_problems = check.get("reported_blockers") or check.get("reported_failures") or []
        problem_text = "; ".join(str(problem) for problem in reported_problems[:3]) if isinstance(reported_problems, list) else ""
        reason = check.get("reason") or "post_generation_check_failed"
        message = (
            f"post-generation check {check.get('check_id')} for {check.get('artifact_path')} "
            f"did not pass: {reason}"
        )
        if problem_text:
            message = f"{message}; {problem_text}"
        if check.get("status") == "block":
            blockers.append(message)
        else:
            failures.append(message)
    return failures, blockers


def post_generation_overall_status(checks: list[dict[str, Any]]) -> str:
    if not checks:
        return "block"
    statuses = {str(check.get("status")) for check in checks}
    if "block" in statuses:
        return "block"
    if statuses - {"pass"}:
        return "fail"
    return "pass"


def run_generate_skill_post_generation_checks(target_relative: str) -> list[dict[str, Any]]:
    return [
        build_post_generation_check_result(
            check_id="generate-skill:post-check-skill",
            command_name="check-skill",
            argv=[
                "--repository-root",
                ".",
                "--target",
                target_relative,
            ],
            artifact_path=target_relative,
        ),
        build_post_generation_check_result(
            check_id="generate-skill:post-check-contract",
            command_name="check-contract",
            argv=[
                "--repository-root",
                target_relative,
                "--target",
                ".",
            ],
            artifact_path=f"{target_relative}/.skillguard/contract-source.json",
            expected_report_target=".",
        ),
    ]


def run_generate_suite_post_generation_checks(
    *,
    suite_root_relative: str,
    suite_map_relative: str,
    suite_contract_relative: str,
    member_root_relative: str,
    members: list[dict[str, str]],
) -> list[dict[str, Any]]:
    checks = [
        build_post_generation_check_result(
            check_id="generate-suite:post-check-suite",
            command_name="check-suite",
            argv=[
                "--suite-root",
                suite_root_relative,
                "--suite-map",
                suite_map_relative,
                "--suite-contract",
                suite_contract_relative,
                "--member-root",
                member_root_relative,
            ],
            artifact_path=suite_root_relative,
        )
    ]
    for member in members:
        checks.append(
            build_post_generation_check_result(
                check_id=f"generate-suite:post-check-child:{member['name']}",
                command_name="check-skill",
                argv=[
                    "--repository-root",
                    ".",
                    "--target",
                    member["path"],
                ],
                artifact_path=member["path"],
            )
        )
    return checks


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


def inline_reference_context(text: str, start: int) -> str:
    line_start = max(text.rfind("\n", 0, start), text.rfind("\r", 0, start)) + 1
    return text[line_start:start][-240:]


def inline_reference_after_context(text: str, end: int) -> str:
    line_ends = [position for position in (text.find("\n", end), text.find("\r", end)) if position >= 0]
    line_end = min(line_ends) if line_ends else len(text)
    return text[end:line_end][:240]


def has_declared_reference_context(context_before: str) -> bool:
    return bool(DECLARED_REFERENCE_CONTEXT_RE.search(context_before))


def looks_like_path_atom(value: str) -> bool:
    candidate = value.strip("'\"()[]{}.,")
    return bool(
        candidate in ROOT_REFERENCE_NAMES
        or candidate == "SKILL.md"
        or candidate.startswith(".")
        or "/" in candidate
        or "\\" in candidate
        or candidate.endswith((".md", ".json", ".toml", ".py", ".txt"))
    )


def looks_like_inline_command(
    reference_text: str,
    context_before: str,
    context_after: str,
    *,
    declared_context: bool,
) -> bool:
    if INLINE_CLI_ARGUMENT_RE.search(reference_text) or SHELL_OPERATOR_RE.search(reference_text):
        return True
    if COMMAND_LAUNCHER_RE.match(reference_text):
        return True
    if not declared_context and (
        INLINE_CLI_VALUE_BEFORE_RE.search(context_before)
        or INLINE_CLI_VALUE_AFTER_RE.search(context_after)
    ):
        return True
    parts = reference_text.split()
    if len(parts) <= 1 or declared_context:
        return False
    if INLINE_COMMAND_CONTEXT_RE.search(context_before):
        return True
    return not looks_like_path_atom(parts[0]) and any(looks_like_path_atom(part) for part in parts[1:])


def looks_like_database_runtime_path(
    reference_text: str,
    context_before: str,
    context_after: str,
    *,
    declared_context: bool,
) -> bool:
    normalized = reference_text.replace("\\", "/")
    if declared_context or normalized.startswith(DECLARED_REFERENCE_PREFIXES):
        return False
    runtime_scoped = bool(DATABASE_RUNTIME_SEGMENT_RE.search(reference_text))
    database_hint = bool(
        DATABASE_FILE_SUFFIX_RE.search(reference_text)
        or DATABASE_CONTEXT_RE.search(context_before)
        or DATABASE_CONTEXT_RE.search(context_after)
        or DATABASE_CONTEXT_RE.search(reference_text)
    )
    return runtime_scoped and database_hint


def looks_like_transient_skillguard_runtime_output(
    reference_text: str,
    *,
    declared_context: bool,
) -> bool:
    """Distinguish generated SkillGuard runtime locations from maintained inputs."""

    if declared_context:
        return False
    normalized = reference_text.replace("\\", "/").strip().rstrip("/")
    return classify_relative_path(normalized).classification == RUNTIME


def normalized_markdown_link_destination(match: re.Match[str]) -> str:
    destination = (match.group(1) or match.group(2) or "").strip()
    if not destination or destination.startswith(("#", "//")):
        return ""
    windows_absolute = bool(re.match(r"^[A-Za-z]:[\\/]", destination))
    if not windows_absolute and re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", destination):
        return ""
    destination = destination.split("#", 1)[0].split("?", 1)[0].strip()
    return destination


def looks_like_reference_span(
    reference_text: str,
    *,
    context_before: str = "",
    context_after: str = "",
    source_kind: str = "inline-code",
) -> bool:
    reference_text = reference_text.strip()
    if not reference_text or "\n" in reference_text or "\r" in reference_text:
        return False
    if source_kind == "markdown-link":
        return True
    declared_context = has_declared_reference_context(context_before)
    # Slash-delimited unit values such as fast/focused/full timeout budgets are
    # data tuples, not local paths.  They still remain references when a link or
    # explicit declared-path context says otherwise.
    if not declared_context and SLASH_VALUE_SEQUENCE_RE.fullmatch(reference_text):
        return False
    if DATABASE_URI_RE.search(reference_text) or SQL_EXPRESSION_RE.match(reference_text):
        return False
    if looks_like_inline_command(
        reference_text,
        context_before,
        context_after,
        declared_context=declared_context,
    ):
        return False
    if looks_like_database_runtime_path(
        reference_text,
        context_before,
        context_after,
        declared_context=declared_context,
    ):
        return False
    if looks_like_transient_skillguard_runtime_output(
        reference_text,
        declared_context=declared_context,
    ):
        return False
    if reference_text.startswith("/") and not reference_text.startswith(("/home/", "/Users/", "/tmp/", "/var/", "/etc/", "/opt/", "/mnt/")):
        return False
    if reference_text in ROOT_REFERENCE_NAMES or reference_text == "SKILL.md":
        return True
    if declared_context and (
        looks_like_path_atom(reference_text)
        or PLAIN_LOCAL_FILENAME_RE.fullmatch(reference_text)
    ):
        return True
    if reference_text.endswith((".md", ".json", ".toml", ".py", ".txt")):
        return True
    return "/" in reference_text or "\\" in reference_text or reference_text.startswith(".")


def extract_reference_tokens(text: str) -> list[str]:
    references: list[str] = []
    seen: set[str] = set()
    candidates: list[tuple[int, str]] = []
    reference_source = FENCED_CODE_BLOCK_RE.sub(
        lambda match: "\n" * match.group(0).count("\n"),
        text,
    )
    link_ranges: list[tuple[int, int]] = []
    for match in MARKDOWN_LINK_RE.finditer(reference_source):
        link_ranges.append((match.start(), match.end()))
        destination = normalized_markdown_link_destination(match)
        if destination and looks_like_reference_span(destination, source_kind="markdown-link"):
            candidates.append((match.start(), destination))
    for match in MARKDOWN_LINK_DEFINITION_RE.finditer(reference_source):
        destination = normalized_markdown_link_destination(match)
        if destination and looks_like_reference_span(destination, source_kind="markdown-link"):
            candidates.append((match.start(), destination))
    for match in REFERENCE_SPAN_RE.finditer(reference_source):
        if any(match.start() >= start and match.end() <= end for start, end in link_ranges):
            continue
        reference_text = match.group(1).strip()
        context_before = inline_reference_context(reference_source, match.start())
        context_after = inline_reference_after_context(reference_source, match.end())
        if reference_text and looks_like_reference_span(
            reference_text,
            context_before=context_before,
            context_after=context_after,
        ):
            candidates.append((match.start(), reference_text))
    for _, reference_text in sorted(candidates, key=lambda item: item[0]):
        if reference_text not in seen:
            seen.add(reference_text)
            references.append(reference_text)
    return references


def reference_label(reference: str) -> str:
    return "<absolute-path-redacted>" if Path(reference).is_absolute() else reference


def is_optional_reference(reference: str) -> bool:
    normalized = reference.replace("\\", "/")
    return normalized in OPTIONAL_TARGET_REFERENCES


def source_layout_projection_allowed(target: Path) -> bool:
    """Return whether source-layout references deterministically project to *target*."""

    resolved_target = target.resolve()
    return (
        resolved_target == skill_root().resolve()
        or is_installed_skill_projection(resolved_target)
    )


def resolve_declared_reference(
    target: Path,
    reference: str,
    root: Path | None = None,
) -> Path:
    repo = (root or repository_root()).resolve()
    project_source_layout = source_layout_projection_allowed(target)
    normalized = reference.replace("\\", "/")
    if normalized == "SKILL.md":
        return target / "SKILL.md"
    source_layout_prefix = f".agents/skills/{target.name}/"
    if normalized == f".agents/skills/{target.name}":
        return target if project_source_layout else repo / normalized
    if normalized.startswith(source_layout_prefix):
        if project_source_layout:
            return target / normalized[len(source_layout_prefix):]
        return repo / normalized
    if normalized in ROOT_REFERENCE_NAMES or normalized.startswith(".agents/"):
        return repo / normalized
    return target / normalized


def validate_reference(
    target: Path,
    reference: str,
    failures: list[str],
    blockers: list[str],
    *,
    allow_project_boundary: bool,
    root: Path | None = None,
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

    candidate = (
        resolve_declared_reference(target, reference, root)
        if allow_project_boundary
        else target / reference
    )
    resolved = candidate.resolve()
    repo = (root or repository_root()).resolve()
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
            entry["resolved_path"] = public_relative_path(resolved, repo)
            return entry

    entry["resolved_path"] = public_relative_path(resolved, repo)
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
    source_layout_prefix = f".agents/skills/{target.name}/"
    if normalized == f".agents/skills/{target.name}":
        return target if source_layout_projection_allowed(target) else repository_root() / normalized
    if normalized.startswith(source_layout_prefix):
        if source_layout_projection_allowed(target):
            return target / normalized[len(source_layout_prefix):]
        return repository_root() / normalized
    if normalized.startswith(".agents/") or normalized in ROOT_REFERENCE_NAMES:
        return repository_root() / normalized
    return control_root / normalized


def contract_target_matches_target(contract_target: Any, target: Path, root: Path | None = None) -> bool:
    if not isinstance(contract_target, str) or not contract_target.strip():
        return False
    try:
        if contract_target == public_relative_path(target, root):
            return True
    except ValueError:
        pass
    normalized_contract_target = contract_target.replace("\\", "/").strip("/")
    installed_target = f".codex/skills/{target.name}"
    source_target = f".agents/skills/{target.name}"
    if normalized_contract_target in {installed_target, source_target} and (target / "SKILL.md").is_file():
        return True
    try:
        resolved = resolve_declared_reference(target, contract_target).resolve()
    except (OSError, RuntimeError, ValueError):
        return False
    return resolved == target.resolve()


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


def find_suite_record(suite_root: Path, explicit_path: str | None, record_kind: str) -> Path | None:
    if explicit_path:
        return resolve_skillguard_self_layout_path(explicit_path)
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


def public_safety_findings(
    path: Path,
    *,
    root: Path | None = None,
) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    findings: list[dict[str, Any]] = []
    for finding_id, pattern in PUBLIC_SAFETY_PATTERNS:
        for match in pattern.finditer(text):
            findings.append(
                {
                    "finding_id": finding_id,
                    "path": public_relative_path(path, root),
                    "line": text[: match.start()].count("\n") + 1,
                }
            )
    return findings


def checked_file(path: Path, kind: str = "file", root: Path | None = None) -> dict[str, Any]:
    return {
        "path": public_relative_path(path, root),
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
    resolved = resolve_skillguard_self_layout_path(raw_path)
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
        for key in ("evidence", "independent_evidence_rules", "validation_layers"):
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


def scan_text_for_unsafe_claims(
    path: Path,
    failures: list[str],
    *,
    root: Path | None = None,
) -> list[dict[str, Any]]:
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
                "path": public_relative_path(path, root),
                "line": text[: match.start()].count("\n") + 1,
                "safe_context": safe_context,
            }
            if not safe_context:
                failures.append(
                    f"{public_relative_path(path, root)} line {finding['line']}: unsafe claim phrase {claim_id}"
                )
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
    parser.add_argument("--target", default=".agents/skills/skillguard", help="Target skill member directory. External members are resolved only inside --repository-root; standalone '.' binds the current directory.")
    parser.add_argument("--repository-root", help="Canonical repository root for an external target member. Repository-relative references resolve only from this root.")
    parser.add_argument(
        "--reference",
        action="append",
        default=[],
        help="Additional target-skill-relative reference to resolve inside the target boundary. Repeat as needed.",
    )
    parser.add_argument("--output", default="-", help="Output report path under the skill root, or '-' for stdout.")
    args = parser.parse_args(argv)

    canonical_root, target, report_root, target_binding = resolve_check_target_binding(
        "check-skill",
        args.target,
        args.repository_root,
    )
    target_relative = public_relative_path(target, report_root)
    payload = base_result("check-skill", target_relative)
    payload["target_binding"] = target_binding
    payload["claim_boundary"] = (
        "This static single-skill check covers SKILL.md metadata and sections, declared local references, the exact "
        "current contract-source/compiled-contract/check-manifest authority, former-surface absence, and conservative "
        "no-claim wording from functional files inspected during this invocation. It does not prove target check execution, fixture "
        "coverage, CLI checks, tests, suite automation, package publication, code-contract validation, release readiness, "
        "or future AI behavior."
    )
    payload["residual_risk"] = [
        "This command is a static local check; semantic adequacy still needs reviewer judgment where the target contract requires it.",
        "Reports, receipts, progress logs, and other runtime outputs are deliberately outside this static owner identity.",
    ]

    failures: list[str] = []
    blockers: list[str] = []
    inspected_files: list[dict[str, Any]] = []
    declared_reference_entries: list[dict[str, Any]] = []
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
                    "path": public_relative_path(skill_md, report_root),
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
        unsafe_claim_findings.extend(
            scan_text_for_unsafe_claims(skill_md, failures, root=report_root)
        )
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
                validate_reference(
                    target,
                    reference,
                    failures,
                    blockers,
                    allow_project_boundary=True,
                    root=canonical_root,
                )
            )
        for reference in args.reference:
            declared_reference_entries.append(
                validate_reference(
                    target,
                    reference,
                    failures,
                    blockers,
                    allow_project_boundary=False,
                    root=canonical_root,
                )
            )
        append_check(
            payload,
            "check-skill:declared-references",
            "Declared reference resolution",
            check_status(failures, blockers, before_failures, before_blockers),
            "Resolved SKILL.md declared references and any extra --reference values with explicit repository/target boundaries.",
        )

    authority = resolve_runtime_authority(target)
    authority_files = [
        target / ".skillguard" / "contract-source.json",
        target / ".skillguard" / "compiled-contract.json",
        target / ".skillguard" / "check-manifest.json",
    ]
    before_failures, before_blockers = len(failures), len(blockers)
    for path in authority_files:
        if path.is_file():
            inspected_files.append(
                {
                    "path": public_relative_path(path, report_root),
                    "kind": "json",
                    "sha256": file_sha256(path),
                    "line_count": line_count(path),
                }
            )
    if not authority.ok or authority.authority != AUTHORITY_CURRENT:
        blockers.extend(
            f"{finding.code}: {finding.path}: {finding.message}"
            for finding in authority.findings
        )
    append_check(
        payload,
        "check-skill:current-runtime-authority",
        "Current runtime authority",
        check_status(failures, blockers, before_failures, before_blockers),
        "Validated the sole current contract source, compiled contract, and exact check manifest with no former-runtime residual.",
    )

    payload["runtime_authority"] = {
        "authority": authority.authority,
        "ok": authority.ok,
        "blockers": list(authority.blockers),
    }
    payload["files_inspected"] = inspected_files
    payload["declared_references"] = declared_reference_entries
    payload["unsafe_claim_findings"] = unsafe_claim_findings
    payload["evidence"] = [
        {
            "evidence_id": "skill-entrypoint-static-read",
            "kind": "file_inspection",
            "fresh": True,
            "summary": f"Read SKILL.md for {target_relative} when present and checked frontmatter, sections, references, and public-safety patterns.",
            "source_path": f"{target_relative}/SKILL.md",
        },
        {
            "evidence_id": "current-runtime-authority",
            "kind": "runtime_authority_resolution",
            "fresh": authority.ok and authority.authority == AUTHORITY_CURRENT,
            "summary": "Resolved exactly one current contract trio and rejected any former runtime surface.",
            "source_path": f"{target_relative}/.skillguard/contract-source.json",
        },
    ]
    payload["failures"] = failures
    payload["blockers"] = blockers
    payload["decision"] = "block" if blockers else "fail" if failures else "pass"
    attach_maintenance_record(
        payload,
        record_kind="target_check",
        artifact_id=target_relative,
        route_node_id="check-skill",
        checker_name="check-skill",
        blockers=blockers + failures,
        owner_action={"action": "not_applicable", "status": "target_check"},
        content_seed={"files_inspected": len(inspected_files), "runtime_authority": authority.authority},
    )
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
    attach_maintenance_record(
        payload,
        record_kind="target_check",
        artifact_id=suite_relative,
        route_node_id="check-suite",
        checker_name="check-suite",
        blockers=blockers + failures,
        owner_action={"action": "not_applicable", "status": "target_check"},
        content_seed={"files_inspected": len(inspected_files), "suite_records": len(records)},
    )
    return write_and_exit(payload, args.output)


def inventory(argv: list[str]) -> int:
    parser = JsonArgumentParser(prog="skillguard.py inventory", description="Build a local SkillGuard inventory record.")
    parser.add_argument("--target", default=".", help="Target path under the repository root.")
    parser.add_argument("--output", default="-", help="Output record path under the skill root, or '-' for stdout.")
    args = parser.parse_args(argv)
    repo = repository_root()
    target = resolve_target_argument(args.target)
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
            ".agents/skills/skillguard/.skillguard/contract-source.json",
            ".agents/skills/skillguard/.skillguard/compiled-contract.json",
            ".agents/skills/skillguard/.skillguard/check-manifest.json",
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


def plan_skill(argv: list[str]) -> int:
    parser = JsonArgumentParser(
        prog="skillguard.py plan-skill",
        description="Convert a skill idea JSON file into a no-write Skill Blueprint preview.",
    )
    parser.add_argument("--input", help="Skill idea JSON file under the repository root.")
    args = parser.parse_args(argv)

    payload = base_result("plan-skill")
    if not args.input:
        payload["decision"] = "block"
        payload["blockers"] = ["plan-skill requires --input pointing to a skill idea JSON object under the repository root"]
        payload["checks"] = [
            {
                "check_id": "plan-skill:input-required",
                "name": "Skill idea input",
                "required": True,
                "status": "block",
                "summary": "No input JSON file was supplied.",
            }
        ]
        return write_and_exit(payload)

    try:
        input_path = ensure_under_root(args.input)
        input_relative = public_relative_path(input_path)
    except ValueError:
        payload["decision"] = "block"
        payload["blockers"] = ["input path must stay under the repository root"]
        payload["checks"] = [
            {
                "check_id": "plan-skill:input-boundary",
                "name": "Input path boundary",
                "required": True,
                "status": "block",
                "summary": "The supplied input path is outside the repository root.",
            }
        ]
        return write_and_exit(payload)

    payload["target_path"] = input_relative
    payload["input_path"] = input_relative
    if not input_path.is_file():
        payload["decision"] = "block"
        payload["blockers"] = [f"input file not found: {input_relative}"]
        payload["checks"] = [
            {
                "check_id": "plan-skill:input-file",
                "name": "Input file exists",
                "required": True,
                "status": "block",
                "summary": "The supplied input path does not point to a current file.",
            }
        ]
        return write_and_exit(payload)

    try:
        raw_input = load_json(input_path)
    except ValueError as exc:
        payload["decision"] = "block"
        payload["blockers"] = [str(exc)]
        payload["checks"] = [
            {
                "check_id": "plan-skill:input-json",
                "name": "Input JSON parse",
                "required": True,
                "status": "block",
                "summary": "The supplied input file is not parseable JSON.",
            }
        ]
        return write_and_exit(payload)

    normalized, blockers = normalize_plan_skill_input(raw_input)
    target_relative = normalized.get("target_path") or input_relative
    payload["target_path"] = target_relative
    payload["checks"] = [
        {
            "check_id": "plan-skill:input-json",
            "name": "Input JSON parse",
            "required": True,
            "status": "pass",
            "summary": f"Loaded {input_relative} with the Python standard library json module.",
        },
        {
            "check_id": "plan-skill:input-contract",
            "name": "Skill idea contract",
            "required": True,
            "status": "block" if blockers else "pass",
            "summary": "Checked required idea fields, supported workflow mode, repository target boundary, and no-write safe-edit mode.",
        },
        {
            "check_id": "plan-skill:no-target-write",
            "name": "No target file writes",
            "required": True,
            "status": "pass",
            "summary": "Generated only stdout JSON in this invocation; the command has no target artifact write path.",
        },
    ]
    payload["evidence"] = [
        {
            "evidence_id": "input-json",
            "kind": "parser_output",
            "fresh": True,
            "summary": f"Parsed {input_relative}; sha256={file_sha256(input_path)}.",
            "source_path": input_relative,
        },
        {
            "evidence_id": "no-write-command-design",
            "kind": "command_behavior",
            "fresh": True,
            "summary": "plan-skill emits its preview through the normal stdout report path and does not call dump_json or target directory creation helpers for target artifacts.",
            "source_path": ".agents/skills/skillguard/scripts/checker_engine.py",
        },
    ]

    if blockers:
        payload["decision"] = "block"
        payload["blockers"] = blockers
        payload["supported_workflow_modes"] = list(PLAN_SKILL_SUPPORTED_WORKFLOW_MODES)
        payload["supported_safe_edit_modes"] = list(PLAN_SKILL_SUPPORTED_SAFE_EDIT_MODES)
        return write_and_exit(payload)

    blueprint = build_plan_skill_blueprint(normalized, input_relative)
    try:
        template_profile = build_plan_template_profile(
            normalized,
            blueprint,
            input_path,
            input_relative,
        )
    except TemplateProfileError as exc:
        payload["decision"] = "block"
        payload["blockers"] = [f"template profile planning failed: {finding}" for finding in exc.findings]
        payload["skipped_checks"] = [
            "No target files were written and no template builder was invoked because template profile planning blocked."
        ]
        return write_and_exit(payload)
    except TemplatePackError as exc:
        payload["decision"] = "block"
        payload["blockers"] = [
            f"template protocol planning failed: {finding.code}:{finding.path}:{finding.message}"
            for finding in exc.findings
        ]
        payload["skipped_checks"] = [
            "No target files were written and no template builder was invoked because target template inputs were invalid."
        ]
        return write_and_exit(payload)
    except (OSError, ValueError) as exc:
        payload["decision"] = "block"
        payload["blockers"] = [f"template profile planning failed: {exc}"]
        payload["skipped_checks"] = [
            "No target files were written because current template source material could not be loaded."
        ]
        return write_and_exit(payload)

    blueprint["template_profile"] = template_profile
    payload["skill_blueprint"] = blueprint
    payload.update(template_profile_projection(template_profile))
    selection = template_profile.get("selection_receipt", {})
    selection_blocked = selection.get("status") != "selected"
    payload["checks"].append(
        {
            "check_id": "plan-skill:template-profile",
            "name": "Validated template profile",
            "required": True,
            "status": "block" if selection_blocked else "pass",
            "summary": (
                "Resolved the complete target-authored candidate set, applicability evidence, deterministic selection, "
                "materialized preview, and affected components without writing target files."
            ),
        }
    )
    payload["evidence"].append(
        {
            "evidence_id": "template-selection-receipt",
            "kind": "immutable_template_selection",
            "fresh": not selection_blocked,
            "summary": (
                f"disposition={selection.get('disposition')} status={selection.get('status')} "
                f"receipt={selection.get('receipt_id')}"
            ),
            "source_path": input_relative,
        }
    )
    payload["decision"] = "block" if selection_blocked else "pass"
    if selection_blocked:
        payload["blockers"] = [
            "ambiguous_template_selection: target-owned candidates cannot be safely composed or uniquely dominated",
            *[str(item) for item in selection.get("findings", [])],
        ]
    payload["skipped_checks"] = [
        "Target file creation, target validation, reviewer judgment, and closure are outside plan-skill's no-write preview scope."
    ]
    payload["residual_risk"] = [
        "The generated Skill Blueprint is a planning artifact and does not prove that the target skill exists, activates correctly, or satisfies SkillGuard standards."
    ]
    payload["claim_boundary"] = (
        "This plan-skill result covers only JSON input parsing, blueprint preview generation, target path boundary validation, "
        "and the no-write command path. It does not prove target file creation, runtime checker execution, fixture coverage, "
        "tests, suite automation, package publication, release readiness, code-contract validation, external services, or future AI behavior."
    )
    return write_and_exit(payload)


def generate_skill(argv: list[str]) -> int:
    parser = JsonArgumentParser(
        prog="skillguard.py generate-skill",
        description="Create a SkillGuard skill scaffold from a valid Skill Blueprint within a controlled write boundary.",
    )
    parser.add_argument("--input", help="Skill Blueprint JSON file, or current plan-skill JSON output, under the repository root.")
    parser.add_argument("--output", default="-", help="Output report path under the skill root, or '-' for stdout.")
    add_checker_change_suite_guard_arguments(parser)
    args = parser.parse_args(argv)

    payload = base_result("generate-skill")
    if not args.input:
        payload["decision"] = "block"
        payload["blockers"] = ["generate-skill requires --input pointing to a Skill Blueprint JSON file under the repository root"]
        payload["checks"] = [
            {
                "check_id": "generate-skill:input-required",
                "name": "Skill Blueprint input",
                "required": True,
                "status": "block",
                "summary": "No input JSON file was supplied.",
            }
        ]
        return write_and_exit(payload, args.output)

    try:
        input_path = ensure_under_root(args.input)
        input_relative = public_relative_path(input_path)
    except ValueError:
        payload["decision"] = "block"
        payload["blockers"] = ["input path must stay under the repository root"]
        payload["checks"] = [
            {
                "check_id": "generate-skill:input-boundary",
                "name": "Input path boundary",
                "required": True,
                "status": "block",
                "summary": "The supplied input path is outside the repository root.",
            }
        ]
        return write_and_exit(payload, args.output)

    payload["input_path"] = input_relative
    if not input_path.is_file():
        payload["decision"] = "block"
        payload["blockers"] = [f"input file not found: {input_relative}"]
        payload["checks"] = [
            {
                "check_id": "generate-skill:input-file",
                "name": "Input file exists",
                "required": True,
                "status": "block",
                "summary": "The supplied input path does not point to a current file.",
            }
        ]
        return write_and_exit(payload, args.output)

    try:
        raw_input = load_json(input_path)
    except ValueError as exc:
        payload["decision"] = "block"
        payload["blockers"] = [str(exc)]
        payload["checks"] = [
            {
                "check_id": "generate-skill:input-json",
                "name": "Input JSON parse",
                "required": True,
                "status": "block",
                "summary": "The supplied input file is not parseable JSON.",
            }
        ]
        return write_and_exit(payload, args.output)

    blueprint, extraction_blockers = extract_skill_blueprint(raw_input)
    target, validation_blockers = validate_generate_skill_blueprint(blueprint) if blueprint else (None, [])
    target_relative = public_relative_path(target) if target is not None else ""
    payload["target_path"] = target_relative
    blockers = [*extraction_blockers, *validation_blockers]
    template_profile: dict[str, Any] = {}
    scaffold_files: dict[str, str] = {}
    template_blockers: list[str] = []
    if target is not None and not blockers:
        try:
            template_profile, scaffold_files, template_blockers = validate_generate_skill_template_profile(
                blueprint,
                target,
            )
        except TemplatePackError as exc:
            template_blockers = [
                f"template protocol validation failed: {finding.code}:{finding.path}:{finding.message}"
                for finding in exc.findings
            ]
        except (OSError, ValueError) as exc:
            template_blockers = [f"template profile currentness validation failed: {exc}"]
    blockers.extend(template_blockers)
    planned_created, planned_existing, conflict_blockers, directory_conflicts = (
        preflight_generate_skill_writes(target, scaffold_files)
        if target is not None and scaffold_files and not blockers
        else ([], [], [], [])
    )
    blockers.extend(conflict_blockers)

    payload["checks"] = [
        {
            "check_id": "generate-skill:input-json",
            "name": "Input JSON parse",
            "required": True,
            "status": "pass",
            "summary": f"Loaded {input_relative} with the Python standard library json module.",
        },
        {
            "check_id": "generate-skill:blueprint-contract",
            "name": "Skill Blueprint contract",
            "required": True,
            "status": "block" if extraction_blockers or validation_blockers else "pass",
            "summary": "Checked current Skill Blueprint schema, required fields, workflow mode, skill identity, target boundary, and safe-edit boundary.",
        },
        {
            "check_id": "generate-skill:template-profile",
            "name": "Current validated template profile",
            "required": True,
            "status": "block" if extraction_blockers or validation_blockers or template_blockers else "pass",
            "summary": (
                "Recomputed source, catalog, route, applicability, selection, builder, validator, prompt, and materialized preview identities. "
                "Target-owned profiles are handed to their native builder instead of the generic scaffold writer."
            ),
        },
        {
            "check_id": "generate-skill:write-preflight",
            "name": "Controlled write preflight",
            "required": True,
            "status": "block" if blockers or conflict_blockers else "pass",
            "summary": (
                "Planned scaffold writes before creating files; required directory path conflicts and differing existing files "
                "block generation while identical files are preserved."
            ),
        },
    ]
    payload["evidence"] = [
        {
            "evidence_id": "blueprint-json",
            "kind": "parser_output",
            "fresh": True,
            "summary": f"Parsed {input_relative}; sha256={file_sha256(input_path)}.",
            "source_path": input_relative,
        },
        {
            "evidence_id": "write-preflight",
            "kind": "filesystem_check",
            "fresh": True,
            "summary": (
                f"planned_new_files={len(planned_created)} existing_identical={len(planned_existing)} "
                f"conflicts={len(conflict_blockers)} directory_conflicts={len(directory_conflicts)}."
            ),
            "source_path": target_relative,
        },
    ]
    if template_profile:
        payload.update(template_profile_projection(template_profile))
        payload["evidence"].append(
            {
                "evidence_id": "template-profile-currentness",
                "kind": "template_profile_recomputation",
                "fresh": not template_blockers,
                "summary": (
                    f"profile_kind={template_profile.get('profile_kind')} "
                    f"profile_hash={template_profile.get('profile_hash')} blockers={len(template_blockers)}"
                ),
                "source_path": str(blueprint.get("source_input") or input_relative),
            }
        )
    payload["planned_created_files"] = planned_created
    payload["existing_files"] = planned_existing
    payload["write_preflight_conflicts"] = directory_conflicts
    payload["required_scaffold_files"] = [f"{target_relative}/{relative}" for relative in GENERATE_SKILL_REQUIRED_FILES] if target_relative else []
    payload["required_scaffold_directories"] = [
        f"{target_relative}/{relative}" for relative in GENERATE_SKILL_REQUIRED_DIRECTORIES
    ] if target_relative else []
    attach_checker_change_suite_guard(
        payload,
        blockers,
        build_checker_change_suite_guard(
            command_name="generate-skill",
            target_path=target_relative or input_relative,
            review_paths=args.checker_change_review,
            selected_suites=args.checker_suite,
            suite_impact_class=args.checker_suite_impact,
            required=args.checker_suite_required,
        ),
    )

    if blockers:
        payload["decision"] = "block"
        payload["blockers"] = blockers
        payload["skipped_checks"] = [
            "No scaffold files were written because required input, blueprint, target, or conflict checks blocked generation."
        ]
        attach_maintenance_record(
            payload,
            record_kind="workflow_evidence",
            artifact_id=target_relative or input_relative,
            route_node_id="generate-skill",
            checker_name="generate-skill",
            blockers=blockers,
            owner_action={"action": "generate_skill", "status": "blocked"},
            content_seed={
                "input_path": input_relative,
                "target_path": target_relative,
                "decision": payload["decision"],
                "blocker_count": len(blockers),
            },
        )
        return write_and_exit(payload, args.output)

    assert target is not None
    created_dirs, created_files = write_generate_skill_scaffold(target, scaffold_files)
    all_files = sorted(public_relative_path(scaffold_path(target, relative)) for relative in scaffold_files)
    missing_after_write = [path for path in all_files if not (repository_root() / path).is_file()]
    payload["checks"].append(
        {
            "check_id": "generate-skill:scaffold-completeness",
            "name": "Scaffold completeness",
            "required": True,
            "status": "fail" if missing_after_write else "pass",
            "summary": "Verified required scaffold files after controlled creation.",
        }
    )
    payload["created_directories"] = created_dirs
    payload["created_files"] = created_files
    payload["all_scaffold_files"] = all_files
    payload["missing_after_write"] = missing_after_write
    post_generation_checks = run_generate_skill_post_generation_checks(target_relative)
    post_generation_failures, post_generation_blockers = post_generation_check_messages(post_generation_checks)
    payload["post_generation_checks"] = post_generation_checks
    payload["evidence"].append(
        {
            "evidence_id": "scaffold-filesystem-state",
            "kind": "filesystem_check",
            "fresh": True,
            "summary": f"created_files={len(created_files)} created_directories={len(created_dirs)} missing_after_write={len(missing_after_write)}.",
            "source_path": target_relative,
        }
    )
    payload["checks"].append(
        {
            "check_id": "generate-skill:post-generation-checks",
            "name": "Generated skill validation",
            "required": True,
            "status": post_generation_overall_status(post_generation_checks),
            "summary": "Ran check-skill and check-contract against the final generated skill path after scaffold writes completed.",
        }
    )
    template_instance_failures: list[str] = []
    try:
        template_instance_receipt = build_generate_skill_instance_receipt(
            template_profile,
            scaffold_files,
            post_generation_checks,
        )
        payload["template_instance_receipt"] = template_instance_receipt
        if template_instance_receipt.get("status") != "passed":
            template_instance_failures = [
                f"template instance validation remained open: {finding}"
                for finding in template_instance_receipt.get("findings", [])
            ] or ["template instance validation remained open"]
    except TemplatePackError as exc:
        template_instance_receipt = {}
        template_instance_failures = [
            f"template instance receipt invalid: {finding.code}:{finding.path}:{finding.message}"
            for finding in exc.findings
        ]
    payload["checks"].append(
        {
            "check_id": "generate-skill:template-instance",
            "name": "Validated template instance receipt",
            "required": True,
            "status": "fail" if template_instance_failures else "pass",
            "summary": (
                "Bound the current selection, exact parameters, builder identity, generated artifact inventory, "
                "placeholder scan, and mapped native validator receipts."
            ),
        }
    )
    payload["evidence"].append(
        {
            "evidence_id": "template-instance-receipt",
            "kind": "immutable_template_instance",
            "fresh": not template_instance_failures,
            "summary": (
                f"status={template_instance_receipt.get('status')} "
                f"receipt={template_instance_receipt.get('receipt_id')} "
                f"fingerprint={template_instance_receipt.get('instance_fingerprint')}"
            ),
            "source_path": target_relative,
        }
    )
    payload["template_harvest_review"] = {
        "required": True,
        "disposition": "not_harvestable",
        "reason": (
            "The SkillGuard validated base generated only a generic skill scaffold and did not create or materially deepen "
            "a target-domain model. A later target-owned model task must issue its own harvest disposition."
        ),
        "allowed_dispositions": template_profile.get("catalog", {})
        .get("harvest_policy", {})
        .get("allowed_dispositions", []),
        "claim_boundary": "This review covers only the generic scaffold instance; it does not decide target-domain reuse.",
    }
    payload["checks"].append(
        {
            "check_id": "generate-skill:template-harvest-review",
            "name": "Template harvest disposition",
            "required": True,
            "status": "pass",
            "summary": "Recorded an explicit disposition instead of silently turning a one-off generated scaffold into a domain template.",
        }
    )
    payload["global_router_refresh"] = {
        "required": True,
        "status": "required_after_generation",
        "reason": "A newly generated real skill is not part of default global routing until the global registry and managed prompt block are refreshed.",
        "command": "refresh-global-router",
        "suggested_arguments": [
            "--skill-root",
            "<skill-root>",
            "--codex-home",
            "<codex-home>",
            "--output-dir",
            "<global-router-output-dir>",
        ],
        "claim_boundary": (
            "This record requires global-router refresh but does not prove the user-level AGENTS.md block or installed registry was updated."
        ),
    }
    payload["checks"].append(
        {
            "check_id": "generate-skill:global-router-refresh-required",
            "name": "Global router refresh requirement",
            "required": True,
            "status": "pass",
            "summary": "Recorded that a successful new skill generation requires refresh-global-router before claiming default global routing is current.",
        }
    )
    payload["evidence"].append(
        {
            "evidence_id": "post-generation-check-skill",
            "kind": "command_output",
            "fresh": True,
            "summary": (
                f"Ran {len(post_generation_checks)} required post-generation check(s) against final generated artifacts; "
                f"non_pass={len(post_generation_failures) + len(post_generation_blockers)}."
            ),
            "source_path": target_relative,
        }
    )
    payload["skipped_checks"] = [
        "generate-skill does not run target semantic review, fixture execution, package installation, release checks, suite automation, code-contract validation, or user-level global prompt installation."
    ]
    payload["residual_risk"] = [
        "Generated scaffold files remain draft until current target checks and reviewer judgment run.",
        "Idempotent identical files are preserved, but differing existing files require a separate repair or overwrite decision.",
        "The generated skill is not available through default global routing until refresh-global-router updates the registry and managed AGENTS.md block.",
    ]
    payload["claim_boundary"] = (
        "This generate-skill result covers only the current Skill Blueprint input, repository-local write preflight, scaffold file creation, "
        "and post-write file-presence checks. It does not prove target acceptance, runtime checker execution, fixture coverage, tests, "
        "suite automation, package publication, release readiness, code-contract validation, external services, or future AI behavior."
    )
    payload["decision"] = (
        "block"
        if post_generation_blockers
        else "fail"
        if missing_after_write or post_generation_failures or template_instance_failures
        else "pass"
    )
    payload["failures"] = [
        *[f"required scaffold file missing after write: {path}" for path in missing_after_write],
        *post_generation_failures,
        *template_instance_failures,
    ]
    payload["blockers"] = post_generation_blockers
    attach_maintenance_record(
        payload,
        record_kind="workflow_evidence",
        artifact_id=target_relative,
        route_node_id="generate-skill",
        checker_name="generate-skill",
        blockers=payload["blockers"] + payload["failures"],
        owner_action={"action": "generate_skill", "status": payload["decision"]},
        content_seed={
            "input_path": input_relative,
            "target_path": target_relative,
            "decision": payload["decision"],
            "required_scaffold_file_count": len(payload.get("required_scaffold_files", [])),
            "post_generation_checks": [
                {
                    "command": item.get("command"),
                    "artifact_path": item.get("artifact_path"),
                    "status": item.get("status"),
                    "reported_decision": item.get("reported_decision"),
                }
                for item in post_generation_checks
            ],
        },
    )
    return write_and_exit(payload, args.output)


def generate_suite(argv: list[str]) -> int:
    parser = JsonArgumentParser(
        prog="skillguard.py generate-suite",
        description="Create a draft multi-skill SkillGuard suite scaffold from a valid Suite Blueprint.",
    )
    parser.add_argument("--input", help="Suite Blueprint JSON file, or a result containing suite_blueprint, under the repository root.")
    parser.add_argument("--output", default="-", help="Output report path under the skill root, or '-' for stdout.")
    add_checker_change_suite_guard_arguments(parser)
    args = parser.parse_args(argv)

    payload = base_result("generate-suite")
    if not args.input:
        payload["decision"] = "block"
        payload["blockers"] = ["generate-suite requires --input pointing to a Suite Blueprint JSON file under the repository root"]
        payload["checks"] = [
            {
                "check_id": "generate-suite:input-required",
                "name": "Suite Blueprint input",
                "required": True,
                "status": "block",
                "summary": "No input JSON file was supplied.",
            }
        ]
        return write_and_exit(payload, args.output)

    try:
        input_path = ensure_under_root(args.input)
        input_relative = public_relative_path(input_path)
    except ValueError:
        payload["decision"] = "block"
        payload["blockers"] = ["input path must stay under the repository root"]
        payload["checks"] = [
            {
                "check_id": "generate-suite:input-boundary",
                "name": "Input path boundary",
                "required": True,
                "status": "block",
                "summary": "The supplied input path is outside the repository root.",
            }
        ]
        return write_and_exit(payload, args.output)

    payload["input_path"] = input_relative
    if not input_path.is_file():
        payload["decision"] = "block"
        payload["blockers"] = [f"input file not found: {input_relative}"]
        payload["checks"] = [
            {
                "check_id": "generate-suite:input-file",
                "name": "Input file exists",
                "required": True,
                "status": "block",
                "summary": "The supplied input path does not point to a current file.",
            }
        ]
        return write_and_exit(payload, args.output)

    try:
        raw_input = load_json(input_path)
    except ValueError as exc:
        payload["decision"] = "block"
        payload["blockers"] = [str(exc)]
        payload["checks"] = [
            {
                "check_id": "generate-suite:input-json",
                "name": "Input JSON parse",
                "required": True,
                "status": "block",
                "summary": "The supplied input file is not parseable JSON.",
            }
        ]
        return write_and_exit(payload, args.output)

    blueprint, extraction_blockers = extract_suite_blueprint(raw_input)
    target, members, validation_blockers = validate_generate_suite_blueprint(blueprint) if blueprint else (None, [], [])
    target_relative = public_relative_path(target) if target is not None else ""
    suite_root_relative = f"{target_relative}/.skillguard/suite" if target_relative else ""
    member_root_relative = f"{target_relative}/members" if target_relative else ""
    payload["target_path"] = target_relative
    payload["suite_root"] = suite_root_relative
    payload["member_root"] = member_root_relative
    payload["child_skill_paths"] = [member["path"] for member in members]

    blockers = [*extraction_blockers, *validation_blockers]
    scaffold_files = build_generate_suite_scaffold(blueprint, target, members, input_relative) if target is not None and members and not blockers else {}
    planned_created, planned_existing, conflict_blockers, directory_conflicts = (
        preflight_generate_suite_writes(target, members, scaffold_files)
        if target is not None and scaffold_files
        else ([], [], [], [])
    )
    blockers.extend(conflict_blockers)

    payload["checks"] = [
        {
            "check_id": "generate-suite:input-json",
            "name": "Input JSON parse",
            "required": True,
            "status": "pass",
            "summary": f"Loaded {input_relative} with the Python standard library json module.",
        },
        {
            "check_id": "generate-suite:blueprint-contract",
            "name": "Suite Blueprint contract",
            "required": True,
            "status": "block" if extraction_blockers or validation_blockers else "pass",
            "summary": "Checked suite schema, workflow mode, suite identity, member list, target boundary, and safe-edit boundary.",
        },
        {
            "check_id": "generate-suite:write-preflight",
            "name": "Controlled suite write preflight",
            "required": True,
            "status": "block" if conflict_blockers else "pass",
            "summary": (
                "Planned suite and child scaffold writes before creating files; required directory path conflicts and "
                "differing existing files block generation while identical files are preserved."
            ),
        },
    ]
    payload["evidence"] = [
        {
            "evidence_id": "suite-blueprint-json",
            "kind": "parser_output",
            "fresh": True,
            "summary": f"Parsed {input_relative}; sha256={file_sha256(input_path)}.",
            "source_path": input_relative,
        },
        {
            "evidence_id": "suite-write-preflight",
            "kind": "filesystem_check",
            "fresh": True,
            "summary": (
                f"planned_new_files={len(planned_created)} existing_identical={len(planned_existing)} "
                f"conflicts={len(conflict_blockers)} directory_conflicts={len(directory_conflicts)}."
            ),
            "source_path": target_relative,
        },
    ]
    payload["planned_created_files"] = planned_created
    payload["existing_files"] = planned_existing
    payload["write_preflight_conflicts"] = directory_conflicts
    payload["required_suite_files"] = [f"{target_relative}/{relative}" for relative in GENERATE_SUITE_REQUIRED_FILES] if target_relative else []
    payload["required_suite_directories"] = [
        f"{target_relative}/{relative}" for relative in GENERATE_SUITE_REQUIRED_DIRECTORIES
    ] if target_relative else []
    attach_checker_change_suite_guard(
        payload,
        blockers,
        build_checker_change_suite_guard(
            command_name="generate-suite",
            target_path=target_relative or input_relative,
            review_paths=args.checker_change_review,
            selected_suites=args.checker_suite,
            suite_impact_class=args.checker_suite_impact,
            required=args.checker_suite_required,
        ),
    )

    if blockers:
        payload["decision"] = "block"
        payload["blockers"] = blockers
        payload["skipped_checks"] = [
            "No suite or child scaffold files were written because required input, blueprint, target, member, or conflict checks blocked generation."
        ]
        return write_and_exit(payload, args.output)

    assert target is not None
    created_dirs, created_files = write_generate_suite_scaffold(target, members, scaffold_files)
    all_files = sorted(public_relative_path(scaffold_path(target, relative)) for relative in scaffold_files)
    missing_after_write = [path for path in all_files if not (repository_root() / path).is_file()]
    payload["checks"].append(
        {
            "check_id": "generate-suite:scaffold-completeness",
            "name": "Suite scaffold completeness",
            "required": True,
            "status": "fail" if missing_after_write else "pass",
            "summary": "Verified suite records, child skill scaffold files, and child check records after controlled creation.",
        }
    )
    payload["created_directories"] = created_dirs
    payload["created_files"] = created_files
    payload["all_scaffold_files"] = all_files
    payload["missing_after_write"] = missing_after_write
    suite_map_relative = f"{suite_root_relative}/suite-map.json"
    suite_contract_relative = f"{suite_root_relative}/suite-contract.json"
    post_generation_checks = run_generate_suite_post_generation_checks(
        suite_root_relative=suite_root_relative,
        suite_map_relative=suite_map_relative,
        suite_contract_relative=suite_contract_relative,
        member_root_relative=member_root_relative,
        members=members,
    )
    post_generation_failures, post_generation_blockers = post_generation_check_messages(post_generation_checks)
    payload["post_generation_checks"] = post_generation_checks
    payload["suite_records"] = [
        suite_map_relative,
        suite_contract_relative,
        f"{suite_root_relative}/evidence/source_blueprint_trace.json",
        f"{suite_root_relative}/evidence/suite_closure.json",
        f"{suite_root_relative}/reports/suite_generation_report.json",
    ]
    payload["child_check_records"] = [
        f"{suite_root_relative}/evidence/{member['name']}_check_report.json" for member in members
    ]
    payload["child_skill_paths"] = [member["path"] for member in members]
    payload["evidence"].append(
        {
            "evidence_id": "suite-scaffold-filesystem-state",
            "kind": "filesystem_check",
            "fresh": True,
            "summary": (
                f"created_files={len(created_files)} created_directories={len(created_dirs)} "
                f"members={len(members)} missing_after_write={len(missing_after_write)}."
            ),
            "source_path": target_relative,
        }
    )
    payload["checks"].append(
        {
            "check_id": "generate-suite:post-generation-checks",
            "name": "Generated suite and child validation",
            "required": True,
            "status": post_generation_overall_status(post_generation_checks),
            "summary": "Ran check-suite plus child check-skill commands against final generated suite and child paths after writes completed.",
        }
    )
    payload["evidence"].append(
        {
            "evidence_id": "post-generation-suite-and-child-checks",
            "kind": "command_output",
            "fresh": True,
            "summary": (
                f"Ran {len(post_generation_checks)} required post-generation check(s) against final suite and child artifacts; "
                f"non_pass={len(post_generation_failures) + len(post_generation_blockers)}."
            ),
            "source_path": target_relative,
        }
    )
    payload["skipped_checks"] = [
        "generate-suite does not run semantic child review, fixture execution, package installation, release checks, suite automation, or code-contract validation."
    ]
    payload["residual_risk"] = [
        "Generated suite and child skill scaffold files remain draft until current check-suite, child check-skill, and reviewer judgment run.",
        "Idempotent identical files are preserved, but differing existing files require a separate repair or overwrite decision.",
    ]
    payload["claim_boundary"] = (
        "This generate-suite result covers only the current Suite Blueprint input, repository-local write preflight, suite and child "
        "scaffold file creation, suite record generation, child entrypoint check-record generation, and post-write file-presence checks. "
        "It does not prove child skill acceptance, runtime checker execution, fixture coverage, tests, suite automation, package "
        "publication, release readiness, code-contract validation, external services, or future AI behavior."
    )
    payload["decision"] = (
        "block"
        if post_generation_blockers
        else "fail"
        if missing_after_write or post_generation_failures
        else "pass"
    )
    payload["failures"] = [
        *[f"required suite scaffold file missing after write: {path}" for path in missing_after_write],
        *post_generation_failures,
    ]
    payload["blockers"] = post_generation_blockers
    return write_and_exit(payload, args.output)


def init_target(argv: list[str]) -> int:
    parser = JsonArgumentParser(prog="skillguard.py init-target", description="Create missing target SkillGuard structure.")
    parser.add_argument("--target", default=".", help="Existing target directory under the repository root.")
    parser.add_argument("--output", default="-", help="Output report path under the skill root, or '-' for stdout.")
    args = parser.parse_args(argv)
    target = resolve_target_argument(args.target)
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
    target = resolve_target_argument(args.target)
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
    target = resolve_target_argument(args.target)
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


def normalize_route_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")


def public_route_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "route_id": entry["route_id"],
        "route_node_id": entry["route_node_id"],
        "command_family": entry["command_family"],
        "responsibility": entry["responsibility"],
        "next_step": entry["next_step"],
        "status": entry["status"],
    }


def route_task_fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest().upper()


def add_route_task_blocker(
    blockers: list[str],
    structured_blockers: list[dict[str, Any]],
    *,
    blocker_code: str,
    message: str,
    recommended_resolution: str,
    conflicting_fields: list[str] | None = None,
    conflicting_candidates: list[dict[str, Any]] | None = None,
    blocker_class: str = "routing_conflict",
    public_context: dict[str, Any] | None = None,
) -> None:
    blockers.append(message)
    record: dict[str, Any] = {
        "blocker_class": blocker_class,
        "blocker_code": blocker_code,
        "message": message,
        "conflicting_fields": conflicting_fields or [],
        "conflicting_candidates": conflicting_candidates or [],
        "recommended_resolution": recommended_resolution,
    }
    if public_context:
        record["public_context"] = public_context
    structured_blockers.append(record)


def current_route_entries() -> list[dict[str, Any]]:
    return [entry for entry in ROUTE_TASK_ROUTE_REGISTRY if entry.get("status") == "current"]


def find_route_by_hint(route_hint: str) -> dict[str, Any] | None:
    normalized_hint = normalize_route_token(route_hint)
    if not normalized_hint:
        return None
    for entry in current_route_entries():
        values = {
            normalize_route_token(entry["route_id"]),
            normalize_route_token(entry["route_node_id"]),
            normalize_route_token(entry["command_family"]),
            *{normalize_route_token(hint) for hint in entry.get("hints", ())},
        }
        if normalized_hint in values:
            return entry
    return None


def route_task_keyword_score(task_text: str, entry: dict[str, Any]) -> int:
    lowered = task_text.lower()
    score = 0
    for keyword in entry.get("keywords", ()):
        keyword_text = str(keyword).lower()
        if keyword_text in lowered:
            score += 3 if " " in keyword_text else 1
    command_text = str(entry.get("command_family", "")).replace("-", " ")
    if command_text and command_text in lowered:
        score += 4
    return score


def route_task_candidates(task_text: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for entry in current_route_entries():
        score = route_task_keyword_score(task_text, entry)
        if score > 0:
            candidate = public_route_entry(entry)
            candidate["score"] = score
            candidates.append(candidate)
    return sorted(candidates, key=lambda item: (-int(item["score"]), item["route_id"]))


def route_task_enabled_flag(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def validate_route_task_flag_conflicts(
    config: dict[str, Any], blockers: list[str], structured_blockers: list[dict[str, Any]]
) -> None:
    for flag_group in ROUTE_TASK_MUTUALLY_EXCLUSIVE_FLAG_GROUPS:
        enabled_fields = [f"$.{field}" for field in flag_group if route_task_enabled_flag(config.get(field))]
        if len(enabled_fields) > 1:
            add_route_task_blocker(
                blockers,
                structured_blockers,
                blocker_code="mutually_exclusive_flags",
                message="route-task input contains mutually exclusive routing flags; keep only one mode flag.",
                conflicting_fields=enabled_fields,
                recommended_resolution="Remove one of the conflicting mode flags before asking route-task for a route decision.",
            )


def route_task_requested_responsibility(
    config: dict[str, Any], blockers: list[str], structured_blockers: list[dict[str, Any]]
) -> str:
    values: list[tuple[str, str]] = []
    for field in ROUTE_TASK_RESPONSIBILITY_FIELDS:
        if field not in config or config.get(field) in (None, ""):
            continue
        value = config.get(field)
        if not isinstance(value, str) or not value.strip():
            add_route_task_blocker(
                blockers,
                structured_blockers,
                blocker_code="invalid_responsibility_field",
                message="route-task requested responsibility must be a non-empty string when supplied.",
                conflicting_fields=[f"$.{field}"],
                recommended_resolution="Use one current public responsibility value from the route registry or omit the field.",
                blocker_class="routing_config_error",
            )
            continue
        values.append((f"$.{field}", normalize_route_token(value)))

    distinct = sorted({value for _, value in values})
    if len(distinct) > 1:
        add_route_task_blocker(
            blockers,
            structured_blockers,
            blocker_code="conflicting_responsibility_sources",
            message="route-task input names conflicting requested responsibilities.",
            conflicting_fields=[field for field, _ in values],
            recommended_resolution="Keep only one requested responsibility value, or omit it and let the selected route declare ownership.",
        )
        return ""
    if not distinct:
        return ""

    known = {normalize_route_token(entry["responsibility"]) for entry in current_route_entries()}
    requested = distinct[0]
    if requested not in known:
        add_route_task_blocker(
            blockers,
            structured_blockers,
            blocker_code="unsupported_requested_responsibility",
            message="route-task requested responsibility is not owned by any current public route.",
            conflicting_fields=[field for field, _ in values],
            recommended_resolution="Use a responsibility value from the current route registry, or remove the requested responsibility.",
            blocker_class="routing_config_error",
        )
        return ""
    return requested


def route_task_route_hint(
    config: dict[str, Any], blockers: list[str], structured_blockers: list[dict[str, Any]]
) -> str:
    route_fields: list[tuple[str, str, dict[str, Any]]] = []
    for field in ROUTE_TASK_ROUTE_HINT_FIELDS:
        if field not in config or config.get(field) in (None, ""):
            continue
        value = config.get(field)
        field_path = f"$.{field}"
        if not isinstance(value, str) or not value.strip():
            add_route_task_blocker(
                blockers,
                structured_blockers,
                blocker_code="invalid_route_hint_field",
                message="route-task route identifier fields must be non-empty strings when supplied.",
                conflicting_fields=[field_path],
                recommended_resolution="Use one current public route id, route node id, or command family.",
                blocker_class="routing_config_error",
            )
            continue

        value_text = value.strip()
        public_context = {
            "hint_fingerprint": route_task_fingerprint(value_text),
            "hint_character_count": len(value_text),
        }
        if normalize_route_token(value_text) in ROUTE_TASK_REPAIR_OR_LEGACY_HINTS:
            add_route_task_blocker(
                blockers,
                structured_blockers,
                blocker_code="stale_route_identifier",
                message="route-task route hint is not a current public route: it names a stale or superseded route.",
                conflicting_fields=[field_path],
                recommended_resolution="Replace the stale route identifier with a route id, route node id, or command family from current_route_registry.",
                public_context=public_context,
            )
            continue

        route_entry = find_route_by_hint(value_text)
        if route_entry is None:
            add_route_task_blocker(
                blockers,
                structured_blockers,
                blocker_code="unsupported_route_hint",
                message="route-task route hint does not name a current public route.",
                conflicting_fields=[field_path],
                recommended_resolution="Use a route id, route node id, or command family from current_route_registry.",
                blocker_class="routing_config_error",
                public_context=public_context,
            )
            continue
        route_fields.append((field_path, value_text, route_entry))

    route_ids = {entry["route_id"] for _, _, entry in route_fields}
    if len(route_ids) > 1:
        add_route_task_blocker(
            blockers,
            structured_blockers,
            blocker_code="incompatible_route_identifiers",
            message="route-task input names multiple current routes; use one route identifier.",
            conflicting_fields=[field_path for field_path, _, _ in route_fields],
            conflicting_candidates=[public_route_entry(entry) for _, _, entry in route_fields],
            recommended_resolution="Remove the extra route identifier fields or make every supplied route identifier point to the same current route.",
        )
        return ""
    if route_fields:
        return route_fields[0][1]
    return ""


def route_task_path_values(value: Any, prefix: str = "$") -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}"
            key_normalized = key.replace("-", "_")
            if key_normalized in ROUTE_TASK_PATH_FIELDS:
                if isinstance(child, str):
                    findings.append((child_prefix, child))
                elif isinstance(child, list):
                    for index, item in enumerate(child):
                        if isinstance(item, str):
                            findings.append((f"{child_prefix}[{index}]", item))
            findings.extend(route_task_path_values(child, child_prefix))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(route_task_path_values(child, f"{prefix}[{index}]"))
    return findings


def validate_route_task_paths(
    config: dict[str, Any], blockers: list[str], structured_blockers: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    path_checks: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for field_path, path_text in route_task_path_values(config):
        if path_text == "-":
            continue
        key = (field_path, path_text)
        if key in seen:
            continue
        seen.add(key)
        entry: dict[str, Any] = {"field": field_path, "path": reference_label(path_text)}
        if Path(path_text).is_absolute():
            entry["status"] = "block"
            entry["reason"] = "absolute paths are not allowed in route-task input"
            add_route_task_blocker(
                blockers,
                structured_blockers,
                blocker_code="invalid_path_config",
                message="route-task input path must be repository-relative and stay under the repository root.",
                conflicting_fields=[field_path],
                recommended_resolution="Use a repository-relative path under the repository root.",
                blocker_class="routing_config_error",
            )
        else:
            try:
                resolved = ensure_under_root(path_text)
            except ValueError:
                entry["status"] = "block"
                entry["reason"] = "path escapes repository boundary"
                add_route_task_blocker(
                    blockers,
                    structured_blockers,
                    blocker_code="invalid_path_config",
                    message="route-task input path escapes repository boundary; use a repository-relative path under the repository root.",
                    conflicting_fields=[field_path],
                    recommended_resolution="Use a repository-relative path under the repository root.",
                    blocker_class="routing_config_error",
                )
            else:
                entry["status"] = "pass"
                entry["resolved_path"] = public_relative_path(resolved)
                entry["exists"] = resolved.exists()
                entry["kind"] = "directory" if resolved.is_dir() else "file" if resolved.is_file() else "missing"
        path_checks.append(entry)
    return path_checks


def route_task_config_from_args(
    args: argparse.Namespace, blockers: list[str], structured_blockers: list[dict[str, Any]]
) -> tuple[dict[str, Any], str, list[dict[str, Any]]]:
    if args.input and (args.task or args.route_hint):
        fields = ["--input"]
        if args.task:
            fields.append("--task")
        if args.route_hint:
            fields.append("--route-hint")
        add_route_task_blocker(
            blockers,
            structured_blockers,
            blocker_code="conflicting_input_sources",
            message="--input cannot be combined with --task or --route-hint; put task and route_hint in the JSON input.",
            conflicting_fields=fields,
            recommended_resolution="Use either --input with all route-task fields in JSON, or direct --task/--route-hint arguments.",
        )
        return {}, "", []

    if args.input:
        try:
            input_path = ensure_under_root(args.input)
        except ValueError:
            add_route_task_blocker(
                blockers,
                structured_blockers,
                blocker_code="invalid_input_path",
                message="route-task input path must stay under the repository root.",
                conflicting_fields=["--input"],
                recommended_resolution="Use a repository-relative JSON input file under the repository root.",
                blocker_class="routing_config_error",
            )
            return {}, "", []
        input_relative = public_relative_path(input_path)
        if not input_path.is_file():
            add_route_task_blocker(
                blockers,
                structured_blockers,
                blocker_code="input_file_not_found",
                message="route-task input file was not found under the repository root.",
                conflicting_fields=["--input"],
                recommended_resolution="Create the JSON input file first or point --input at an existing repository-local JSON file.",
                blocker_class="routing_config_error",
                public_context={"input_path": input_relative},
            )
            return {}, input_relative, []
        try:
            config = load_json(input_path)
        except ValueError as exc:
            add_route_task_blocker(
                blockers,
                structured_blockers,
                blocker_code="malformed_json",
                message="malformed route-task JSON input: invalid JSON parse.",
                conflicting_fields=["--input"],
                recommended_resolution="Repair the JSON syntax before rerunning route-task.",
                blocker_class="routing_config_error",
                public_context={"input_path": input_relative},
            )
            return {}, input_relative, []
        if not isinstance(config, dict):
            add_route_task_blocker(
                blockers,
                structured_blockers,
                blocker_code="invalid_config_shape",
                message="route-task input JSON must be an object.",
                conflicting_fields=["$"],
                recommended_resolution="Supply one JSON object with task and optional route_hint fields.",
                blocker_class="routing_config_error",
            )
            return {}, input_relative, []
        return config, input_relative, validate_route_task_paths(config, blockers, structured_blockers)

    config = {}
    if args.task is not None:
        config["task"] = args.task
    if args.route_hint is not None:
        config["route_hint"] = args.route_hint
    return config, "", validate_route_task_paths(config, blockers, structured_blockers)


def validate_route_task_config(
    config: dict[str, Any], blockers: list[str], structured_blockers: list[dict[str, Any]]
) -> tuple[str, str, str]:
    validate_route_task_flag_conflicts(config, blockers, structured_blockers)
    if "tasks" in config:
        add_route_task_blocker(
            blockers,
            structured_blockers,
            blocker_code="ambiguous_task_sources",
            message="route-task input is ambiguous: use one string field named task, not tasks.",
            conflicting_fields=["$.tasks", "$.task"],
            recommended_resolution="Replace tasks with one public-safe task string in the task field.",
        )
    task_values: list[tuple[str, str]] = []
    for field in ("task", "task_text"):
        value = config.get(field)
        if value is not None:
            if not isinstance(value, str) or not value.strip():
                add_route_task_blocker(
                    blockers,
                    structured_blockers,
                    blocker_code="invalid_task_field",
                    message=f"route-task field {field} must be a non-empty string.",
                    conflicting_fields=[f"$.{field}"],
                    recommended_resolution="Supply exactly one public-safe non-empty task string.",
                    blocker_class="routing_config_error",
                )
            else:
                task_values.append((f"$.{field}", value.strip()))
    if len({value for _, value in task_values}) > 1:
        add_route_task_blocker(
            blockers,
            structured_blockers,
            blocker_code="conflicting_task_sources",
            message="route-task input is ambiguous: task and task_text disagree.",
            conflicting_fields=[field for field, _ in task_values],
            recommended_resolution="Keep one task field, or make the task and task_text values identical.",
        )
    task_text = task_values[0][1] if task_values else ""
    if not task_text:
        add_route_task_blocker(
            blockers,
            structured_blockers,
            blocker_code="missing_task_text",
            message="route-task requires non-empty task text.",
            conflicting_fields=["$.task"],
            recommended_resolution="Supply one public-safe task string through --task or the JSON task field.",
            blocker_class="routing_config_error",
        )

    route_hint = route_task_route_hint(config, blockers, structured_blockers)
    requested_responsibility = route_task_requested_responsibility(config, blockers, structured_blockers)
    return task_text, route_hint, requested_responsibility


def select_route_task_decision(
    task_text: str, route_hint: str, blockers: list[str], structured_blockers: list[dict[str, Any]]
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    task_candidates = route_task_candidates(task_text)
    if route_hint:
        route_entry = find_route_by_hint(route_hint)
        if route_entry is None:
            add_route_task_blocker(
                blockers,
                structured_blockers,
                blocker_code="unsupported_route_hint",
                message="unsupported route_hint: route-task route hint does not name a current public route.",
                conflicting_fields=["$.route_hint"],
                recommended_resolution="Use a route id, route node id, or command family from current_route_registry.",
                blocker_class="routing_config_error",
                public_context={"hint_fingerprint": route_task_fingerprint(route_hint), "hint_character_count": len(route_hint)},
            )
            return None, []
        hinted = public_route_entry(route_entry) | {"score": 100}
        if task_candidates:
            top_score = int(task_candidates[0]["score"])
            top_candidates = [candidate for candidate in task_candidates if int(candidate["score"]) == top_score]
            if all(candidate["route_id"] != route_entry["route_id"] for candidate in top_candidates):
                add_route_task_blocker(
                    blockers,
                    structured_blockers,
                    blocker_code="incompatible_route_hint",
                    message="route-task route hint conflicts with the task's strongest current route match.",
                    conflicting_fields=["$.task", "$.route_hint"],
                    conflicting_candidates=[hinted, *top_candidates],
                    recommended_resolution="Change the route hint to match the task, rewrite the task for the hinted route, or remove the hint and handle the unhinted route decision.",
                )
                return None, [hinted, *task_candidates]
        return public_route_entry(route_entry) | {"selection_reason": "explicit_route_hint", "confidence": "high"}, [hinted]

    candidates = task_candidates
    if not candidates:
        add_route_task_blocker(
            blockers,
            structured_blockers,
            blocker_code="no_supported_route",
            message="no supported SkillGuard route matched the task text.",
            conflicting_fields=["$.task"],
            recommended_resolution="Rewrite the task with a current command-family cue or supply an explicit current route_hint.",
            blocker_class="routing_config_error",
        )
        return None, []
    top_score = int(candidates[0]["score"])
    top_candidates = [candidate for candidate in candidates if int(candidate["score"]) == top_score]
    if len(top_candidates) > 1:
        add_route_task_blocker(
            blockers,
            structured_blockers,
            blocker_code="multiple_equal_route_candidates",
            message="ambiguous route-task input matched multiple current routes with equal score.",
            conflicting_fields=["$.task"],
            conflicting_candidates=top_candidates,
            recommended_resolution="Add an explicit current route_hint or rewrite the task so only one current route is the strongest match.",
        )
        return None, candidates
    selected = dict(candidates[0])
    selected["selection_reason"] = "keyword_match"
    selected["confidence"] = "medium" if top_score < 5 else "high"
    return selected, candidates


def route_task_generator_input(config: dict[str, Any]) -> tuple[str, str]:
    for field in ROUTE_TASK_GENERATOR_INPUT_FIELDS:
        if field not in config or config.get(field) in (None, ""):
            continue
        value = config.get(field)
        return field, value.strip() if isinstance(value, str) else ""
    return "", ""


def route_task_config_string_values(config: dict[str, Any], fields: tuple[str, ...]) -> list[str]:
    values: list[str] = []
    for field in fields:
        if field not in config:
            continue
        values.extend(checker_change_suite_guard_values(config.get(field)))
    return values


def route_task_checker_change_guard_argv(config: dict[str, Any]) -> list[str]:
    argv: list[str] = []
    for path in route_task_config_string_values(config, ROUTE_TASK_CHECKER_CHANGE_REVIEW_FIELDS):
        argv.extend(["--checker-change-review", path])
    for suite in route_task_config_string_values(config, ROUTE_TASK_CHECKER_SUITE_FIELDS):
        argv.extend(["--checker-suite", suite])
    for field in ("checker_suite_impact", "suite_impact_class", "checker_change_impact"):
        value = config.get(field)
        if isinstance(value, str) and value.strip():
            argv.extend(["--checker-suite-impact", value.strip()])
            break
    if route_task_enabled_flag(config.get("checker_suite_required")) or route_task_enabled_flag(config.get("checker_change_suite_required")):
        argv.append("--checker-suite-required")
    return argv


def route_task_checker_change_guard_from_config(
    *,
    config: dict[str, Any],
    command_name: str,
    target_path: str,
) -> dict[str, Any]:
    review_paths = route_task_config_string_values(config, ROUTE_TASK_CHECKER_CHANGE_REVIEW_FIELDS)
    selected_suites = route_task_config_string_values(config, ROUTE_TASK_CHECKER_SUITE_FIELDS)
    suite_impact_class = ""
    for field in ("checker_suite_impact", "suite_impact_class", "checker_change_impact"):
        value = config.get(field)
        if isinstance(value, str) and value.strip():
            suite_impact_class = value.strip()
            break
    required = route_task_enabled_flag(config.get("checker_suite_required")) or route_task_enabled_flag(config.get("checker_change_suite_required"))
    return build_checker_change_suite_guard(
        command_name=command_name,
        target_path=target_path,
        review_paths=review_paths,
        selected_suites=selected_suites,
        suite_impact_class=suite_impact_class,
        required=required,
    )


def route_task_generation_requested(config: dict[str, Any], selected_route: dict[str, Any] | None) -> bool:
    if selected_route is None:
        return any(route_task_enabled_flag(config.get(field)) for field in ROUTE_TASK_GENERATOR_EXECUTE_FLAGS)
    command_family = str(selected_route.get("command_family", ""))
    if command_family not in ROUTE_TASK_GENERATOR_COMMANDS:
        return any(route_task_enabled_flag(config.get(field)) for field in ROUTE_TASK_GENERATOR_EXECUTE_FLAGS)
    _, generator_input = route_task_generator_input(config)
    return bool(generator_input) or any(route_task_enabled_flag(config.get(field)) for field in ROUTE_TASK_GENERATOR_EXECUTE_FLAGS)


def validate_route_task_generation_request(
    config: dict[str, Any],
    selected_route: dict[str, Any] | None,
    route_hint: str,
    blockers: list[str],
    structured_blockers: list[dict[str, Any]],
) -> tuple[str, str]:
    if not route_task_generation_requested(config, selected_route):
        return "", ""

    command_family = str(selected_route.get("command_family", "")) if selected_route is not None else ""
    if command_family not in ROUTE_TASK_GENERATOR_COMMANDS:
        add_route_task_blocker(
            blockers,
            structured_blockers,
            blocker_code="unsupported_command_path",
            message="route-task command execution is currently limited to generate-skill and generate-suite routes.",
            conflicting_fields=[f"$.{field}" for field in ROUTE_TASK_GENERATOR_EXECUTE_FLAGS if route_task_enabled_flag(config.get(field))],
            conflicting_candidates=[selected_route] if selected_route is not None else [],
            recommended_resolution="Use route-task as a route-only command for this route, or select generate-skill/generate-suite with an explicit route hint.",
            blocker_class="routing_config_error",
        )
        return "", ""

    if not route_hint:
        add_route_task_blocker(
            blockers,
            structured_blockers,
            blocker_code="command_path_requires_explicit_route_hint",
            message="route-task generation command paths require an explicit current generate-skill or generate-suite route hint.",
            conflicting_fields=["$.route_hint"],
            conflicting_candidates=[selected_route],
            recommended_resolution="Add route_hint=generate-skill or route_hint=generate-suite before requesting generator execution.",
            blocker_class="routing_config_error",
        )
        return "", ""

    input_field, input_path = route_task_generator_input(config)
    if not input_field or not input_path:
        add_route_task_blocker(
            blockers,
            structured_blockers,
            blocker_code="missing_command_input",
            message="route-task generation command paths require a repository-local blueprint input path.",
            conflicting_fields=["$.input"],
            conflicting_candidates=[selected_route],
            recommended_resolution="Provide input, input_path, blueprint_path, or command_input_path pointing to the generator blueprint JSON.",
            blocker_class="routing_config_error",
        )
        return "", ""

    blocked_mode_fields = [f"$.{field}" for field in ROUTE_TASK_GENERATOR_NO_WRITE_FLAGS if route_task_enabled_flag(config.get(field))]
    if blocked_mode_fields:
        add_route_task_blocker(
            blockers,
            structured_blockers,
            blocker_code="generator_execution_forbidden_by_no_write_flag",
            message="route-task generation command path conflicts with an explicit no-write, dry-run, no-mutation, or no-generators flag.",
            conflicting_fields=blocked_mode_fields,
            conflicting_candidates=[selected_route],
            recommended_resolution="Remove the no-write/no-generator flag to execute the generator, or omit the generator input for route-only metadata.",
        )
        return "", ""

    return command_family, input_path


def route_task(argv: list[str]) -> int:
    parser = JsonArgumentParser(
        prog="skillguard.py route-task",
        description="Route one task request to a current SkillGuard command family without mutating project files.",
    )
    parser.add_argument("--task", help="Task text to route. Use exactly one task.")
    parser.add_argument("--input", help="Repository-local route-task JSON config with task and optional route_hint.")
    parser.add_argument("--route-hint", help="Optional current route id, route node id, or command family.")
    parser.add_argument("--output", default="-", help="Output path under the skill root, or '-' for stdout.")
    args = parser.parse_args(argv)

    payload = base_result("route-task")
    payload["claim_boundary"] = (
        "This route-task result covers only deterministic routing metadata from the current public SkillGuard route registry. "
        "It does not execute generators, inspect sealed FlowPilot packet bodies, read sibling role materials, mutate project files, "
        "or prove target acceptance, fixture coverage, suite automation, package publication, release readiness, code-contract validation, "
        "external services, or future AI behavior."
    )
    blockers: list[str] = []
    routing_conflict_blockers: list[dict[str, Any]] = []
    failures: list[str] = []

    config, input_relative, path_checks = route_task_config_from_args(args, blockers, routing_conflict_blockers)
    task_text, route_hint, requested_responsibility = (
        validate_route_task_config(config, blockers, routing_conflict_blockers) if config or not blockers else ("", "", "")
    )
    selected_route: dict[str, Any] | None = None
    candidates: list[dict[str, Any]] = []
    if not blockers:
        selected_route, candidates = select_route_task_decision(task_text, route_hint, blockers, routing_conflict_blockers)
    if selected_route is not None and requested_responsibility:
        selected_responsibility = normalize_route_token(str(selected_route.get("responsibility", "")))
        if selected_responsibility != requested_responsibility:
            add_route_task_blocker(
                blockers,
                routing_conflict_blockers,
                blocker_code="responsibility_route_conflict",
                message="route-task requested responsibility conflicts with selected route ownership.",
                conflicting_fields=["$.requested_responsibility", "routing_decision.responsibility"],
                conflicting_candidates=[selected_route],
                recommended_resolution="Use the selected route's responsibility, choose a route owned by the requested responsibility, or remove the requested responsibility.",
            )

    command_family = ""
    command_input = ""
    if selected_route is not None and not blockers:
        command_family, command_input = validate_route_task_generation_request(
            config,
            selected_route,
            route_hint,
            blockers,
            routing_conflict_blockers,
        )
    if command_family and command_input and not blockers:
        delegated_argv = ["--input", command_input, "--output", args.output, *route_task_checker_change_guard_argv(config)]
        if command_family == "generate-skill":
            return generate_skill(delegated_argv)
        if command_family == "generate-suite":
            return generate_suite(delegated_argv)

    payload["input_path"] = input_relative
    payload["route_registry_version"] = ROUTE_TASK_REGISTRY_VERSION
    payload["current_route_registry"] = [public_route_entry(entry) for entry in current_route_entries()]
    payload["task_fingerprint"] = route_task_fingerprint(task_text) if task_text else ""
    payload["task_character_count"] = len(task_text)
    route_hint_entry = find_route_by_hint(route_hint) if route_hint else None
    payload["route_hint"] = route_hint if route_hint_entry is not None else ""
    payload["route_hint_fingerprint"] = route_task_fingerprint(route_hint) if route_hint else ""
    payload["route_hint_character_count"] = len(route_hint)
    payload["requested_responsibility"] = requested_responsibility
    payload["path_checks"] = path_checks
    payload["candidate_routes"] = candidates
    payload["routing_conflict_blockers"] = routing_conflict_blockers
    if selected_route is not None and not blockers:
        payload["routing_decision"] = selected_route
        payload["target_path"] = selected_route["route_id"]
    else:
        payload["routing_decision"] = {}

    payload["checks"] = [
        {
            "check_id": "route-task:input-contract",
            "name": "Route-task input contract",
            "required": True,
            "status": "block" if blockers else "pass",
            "summary": "Checked task/config shape, mutually exclusive input modes, repository path boundaries, and route hint support.",
        },
        {
            "check_id": "route-task:route-registry",
            "name": "Current route registry",
            "required": True,
            "status": "pass",
            "summary": f"Loaded {len(current_route_entries())} current public SkillGuard route entries from {ROUTE_TASK_REGISTRY_VERSION}.",
        },
        {
            "check_id": "route-task:selection",
            "name": "Route selection",
            "required": True,
            "status": "block" if blockers else "pass",
            "summary": "Selected one current public route when task text and optional route hint identified an unambiguous supported route.",
        },
        {
            "check_id": "route-task:no-mutation",
            "name": "No project mutation",
            "required": True,
            "status": "pass",
            "summary": "route-task only parsed input and returned routing metadata; it did not invoke generators or write project files.",
        },
    ]
    payload["evidence"] = [
        {
            "evidence_id": "route-task-input-parse",
            "kind": "parser_output",
            "fresh": True,
            "summary": "Parsed route-task CLI/config input with standard-library argparse and json helpers.",
            "source_path": input_relative or "argv",
        },
        {
            "evidence_id": "route-task-current-route-registry",
            "kind": "static_registry",
            "fresh": True,
            "summary": f"Used {ROUTE_TASK_REGISTRY_VERSION} current route entries; repair-only and legacy aliases are not authoritative routes.",
            "source_path": ".agents/skills/skillguard/scripts/checker_engine.py",
        },
    ]
    attach_checker_change_suite_guard(
        payload,
        blockers,
        route_task_checker_change_guard_from_config(
            config=config,
            command_name="route-task",
            target_path=payload.get("target_path") or "route-task",
        ),
    )
    payload["failures"] = failures
    payload["blockers"] = blockers
    payload["skipped_checks"] = [
        "route-task does not execute the selected command, run target checks, invoke generators, or make closure decisions."
    ]
    payload["residual_risk"] = [
        "Keyword routing is deterministic but conservative; unusual task wording may require an explicit current route hint.",
        "Routing metadata is public and handoff-oriented; private task details should stay outside route-task input when public output is required.",
    ]
    payload["decision"] = "block" if blockers else "pass"
    attach_maintenance_record(
        payload,
        record_kind="route_task_metadata",
        artifact_id=payload.get("target_path") or "route-task",
        route_node_id="route-task",
        checker_name="route-task",
        blockers=routing_conflict_blockers,
        owner_action={"action": "not_applicable", "status": "route_only"},
        content_seed={"route_hint_present": bool(route_hint), "selected_route": payload.get("routing_decision", {})},
    )
    return write_and_exit(payload, args.output)


def normalized_recorded_sha256(value: Any) -> str:
    return str(value or "").strip().upper()


def public_binding_path_label(path_text: Any, base_dir: Path | None = None) -> str:
    if not isinstance(path_text, str) or not path_text.strip():
        return ""
    if Path(path_text).is_absolute():
        return "<absolute-path-redacted>"
    try:
        return public_relative_path(resolve_repository_reference(path_text, base_dir))
    except ValueError:
        return path_text.replace("\\", "/")[:160]


def add_stale_evidence_blocker(
    stale_blockers: list[dict[str, Any]],
    *,
    artifact_id: str,
    blocker_code: str,
    binding_kind: str,
    binding_id: str,
    expected_current_binding: dict[str, Any],
    observed_stale_binding: dict[str, Any],
    stale_reason: str,
    recommended_owner_action: str,
) -> None:
    stale_blockers.append(
        {
            "blocker_class": "stale_or_unverifiable_evidence",
            "blocker_code": blocker_code,
            "artifact_id": artifact_id,
            "binding_kind": binding_kind,
            "binding_id": binding_id,
            "expected_current_binding": expected_current_binding,
            "observed_stale_binding": observed_stale_binding,
            "stale_reason": stale_reason,
            "recommended_owner_action": recommended_owner_action,
        }
    )


def maintenance_record_path_label(path_text: Any) -> str:
    return public_binding_path_label(path_text) or str(path_text or "")[:160]


def maintenance_record_blocker(
    *,
    blocker_code: str,
    artifact_id: str,
    field_path: str,
    observed_shape: Any,
    recommended_repair_action: str,
) -> dict[str, Any]:
    return {
        "blocker_class": "maintenance_record_schema",
        "blocker_code": blocker_code,
        "artifact_id": artifact_id,
        "field_path": field_path,
        "observed_shape": observed_shape,
        "expected_schema_version": MAINTENANCE_RECORD_SCHEMA_VERSION,
        "recommended_repair_action": recommended_repair_action,
    }


def maintenance_record_kind_for_command(command: str) -> str:
    mapping = {
        "commands": "command_surface",
        "route-task": "route_task_metadata",
        "fixture-test": "fixture_evidence",
        "detect-stale-evidence": "stale_evidence_review",
        "review-checker-change": "checker_change_review",
        "self-check": "self_check",
        "check-skill": "target_check",
        "check-suite": "target_check",
    }
    return mapping.get(command, "workflow_evidence")


def maintenance_record_command_surface(checker_name: str) -> dict[str, Any]:
    return {
        "checker_name": checker_name,
        "checker_version": CHECKER_VERSION,
        "command_names": list(COMMANDS),
        "current_route_registry": [public_route_entry(entry) for entry in current_route_entries()],
    }


def normalize_maintenance_blocker_row(item: Any, artifact_id: str, index: int = 0) -> dict[str, Any]:
    if isinstance(item, str):
        return {
            "blocker_class": "text_blocker",
            "blocker_code": "text_blocker",
            "artifact_id": artifact_id,
            "message": item[:240],
            "recommended_repair_action": "Inspect the owning command output and repair the blocker before accepting this maintenance record.",
        }
    if not isinstance(item, dict):
        return {
            "blocker_class": "malformed_blocker",
            "blocker_code": "malformed_blocker",
            "artifact_id": artifact_id,
            "message": f"blockers[{index}] is {type(item).__name__}",
            "recommended_repair_action": "Regenerate the maintenance record with structured blocker rows.",
        }
    message = (
        item.get("message")
        or item.get("stale_reason")
        or item.get("failure_reason")
        or item.get("recommended_resolution")
        or item.get("recommended_owner_action")
        or item.get("recommended_repair_action")
        or str(item.get("blocker_code") or "blocker")
    )
    return {
        "blocker_class": str(item.get("blocker_class") or "maintenance_blocker"),
        "blocker_code": str(item.get("blocker_code") or item.get("code") or "maintenance_blocker"),
        "artifact_id": str(item.get("artifact_id") or artifact_id),
        "message": str(message)[:240],
        "recommended_repair_action": str(
            item.get("recommended_repair_action")
            or item.get("recommended_owner_action")
            or item.get("recommended_resolution")
            or "Repair the owning maintenance artifact and regenerate current evidence."
        )[:300],
    }


def maintenance_content_hash(seed: dict[str, Any]) -> str:
    stable = json.dumps(seed, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(stable.encode("utf-8")).hexdigest().upper()


def build_maintenance_record(
    *,
    record_kind: str,
    artifact_id: str,
    route_node_id: str,
    checker_name: str,
    status: str,
    blockers: list[Any] | None = None,
    evidence_timestamp: str | None = None,
    owner_action: dict[str, Any] | None = None,
    content_seed: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blocker_rows = [
        normalize_maintenance_blocker_row(item, artifact_id, index)
        for index, item in enumerate(blockers or [])
    ]
    timestamp = evidence_timestamp or utc_timestamp()
    seed = {
        "artifact_id": artifact_id,
        "blocker_codes": [row["blocker_code"] for row in blocker_rows],
        "checker_name": checker_name,
        "content_seed": content_seed or {},
        "record_kind": record_kind,
        "route_node_id": route_node_id,
        "status": status,
    }
    content_hash = maintenance_content_hash(seed)
    return {
        "schema_version": MAINTENANCE_RECORD_SCHEMA_VERSION,
        "record_id": f"{record_kind}:{maintenance_content_hash({'artifact_id': artifact_id, 'content_hash': content_hash})[:16]}",
        "record_kind": record_kind,
        "artifact_id": artifact_id,
        "route_node_id": route_node_id,
        "route_version": DETECT_STALE_EXPECTED_ROUTE_VERSION,
        "route_registry_version": ROUTE_TASK_REGISTRY_VERSION,
        "command_surface": maintenance_record_command_surface(checker_name),
        "content_hash": content_hash,
        "evidence_timestamp": timestamp,
        "status": status,
        "blockers": blocker_rows,
        "owner_action": owner_action or {"action": "not_applicable", "status": "not_applicable"},
    }


def attach_maintenance_record(
    payload: dict[str, Any],
    *,
    record_kind: str,
    artifact_id: str,
    route_node_id: str,
    checker_name: str,
    blockers: list[Any] | None = None,
    owner_action: dict[str, Any] | None = None,
    content_seed: dict[str, Any] | None = None,
) -> None:
    record = build_maintenance_record(
        record_kind=record_kind,
        artifact_id=artifact_id,
        route_node_id=route_node_id,
        checker_name=checker_name,
        status=str(payload.get("decision") or ""),
        blockers=blockers,
        evidence_timestamp=str(payload.get("checked_at") or utc_timestamp()),
        owner_action=owner_action,
        content_seed=content_seed,
    )
    payload["maintenance_record_schema_version"] = MAINTENANCE_RECORD_SCHEMA_VERSION
    payload["maintenance_record"] = record


def maintenance_record_contains_forbidden_alias(value: Any, path: str = "$") -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in MAINTENANCE_RECORD_FORBIDDEN_LEGACY_ALIASES:
                findings.append({"field_path": child_path, "alias": key})
            findings.extend(maintenance_record_contains_forbidden_alias(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(maintenance_record_contains_forbidden_alias(child, f"{path}[{index}]"))
    return findings


def maintenance_record_public_boundary_findings(record: dict[str, Any]) -> list[dict[str, Any]]:
    text = json.dumps(record, sort_keys=True, ensure_ascii=True)
    findings: list[dict[str, Any]] = []
    for finding_id, pattern in PUBLIC_SAFETY_PATTERNS:
        if pattern.search(text):
            findings.append({"finding_id": finding_id, "field_path": "$"})
    lowered = text.lower()
    for marker in MAINTENANCE_RECORD_PRIVATE_MARKERS:
        if marker.lower() in lowered:
            findings.append({"finding_id": "sealed-body-or-private-payload", "field_path": "$", "marker": marker})
    return findings


def validate_maintenance_record(
    record: Any,
    *,
    artifact_id: str,
    expected_route_version: str = DETECT_STALE_EXPECTED_ROUTE_VERSION,
    expected_route_registry_version: str = ROUTE_TASK_REGISTRY_VERSION,
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if not isinstance(record, dict):
        return [
            maintenance_record_blocker(
                blocker_code="malformed_maintenance_record",
                artifact_id=artifact_id,
                field_path="$",
                observed_shape=type(record).__name__,
                recommended_repair_action="Regenerate the maintenance artifact as a JSON object.",
            )
        ]
    for field in MAINTENANCE_RECORD_REQUIRED_FIELDS:
        if field not in record:
            blockers.append(
                maintenance_record_blocker(
                    blocker_code="missing_required_field",
                    artifact_id=artifact_id,
                    field_path=f"$.{field}",
                    observed_shape="missing",
                    recommended_repair_action="Regenerate the maintenance record with the canonical public field set.",
                )
            )
    schema_version = str(record.get("schema_version") or "")
    if schema_version != MAINTENANCE_RECORD_SCHEMA_VERSION:
        blockers.append(
            maintenance_record_blocker(
                blocker_code="incompatible_schema_version",
                artifact_id=artifact_id,
                field_path="$.schema_version",
                observed_shape=schema_version or "missing",
                recommended_repair_action="Rewrite the record directly in the current canonical maintenance record shape.",
            )
        )
    record_kind = str(record.get("record_kind") or "")
    if record_kind and record_kind not in MAINTENANCE_RECORD_KINDS:
        blockers.append(
            maintenance_record_blocker(
                blocker_code="unsupported_record_kind",
                artifact_id=artifact_id,
                field_path="$.record_kind",
                observed_shape=record_kind,
                recommended_repair_action="Use a supported canonical maintenance record kind.",
            )
        )
    if str(record.get("route_version") or "") != expected_route_version:
        blockers.append(
            maintenance_record_blocker(
                blocker_code="route_version_mismatch",
                artifact_id=artifact_id,
                field_path="$.route_version",
                observed_shape=str(record.get("route_version") or ""),
                recommended_repair_action="Regenerate the record with the current route version before accepting it.",
            )
        )
    if str(record.get("route_registry_version") or "") != expected_route_registry_version:
        blockers.append(
            maintenance_record_blocker(
                blocker_code="route_registry_version_mismatch",
                artifact_id=artifact_id,
                field_path="$.route_registry_version",
                observed_shape=str(record.get("route_registry_version") or ""),
                recommended_repair_action="Regenerate the record with the current route-task registry version.",
            )
        )
    command_surface = record.get("command_surface")
    if not isinstance(command_surface, dict):
        blockers.append(
            maintenance_record_blocker(
                blocker_code="command_binding_mismatch",
                artifact_id=artifact_id,
                field_path="$.command_surface",
                observed_shape=type(command_surface).__name__,
                recommended_repair_action="Regenerate command_surface with checker_name, command_names, checker_version, and current_route_registry.",
            )
        )
    else:
        checker_name = str(command_surface.get("checker_name") or "")
        command_names = command_surface.get("command_names")
        current_names = list(COMMANDS)
        observed_names = [str(item) for item in command_names] if isinstance(command_names, list) else []
        if checker_name and checker_name not in current_names:
            blockers.append(
                maintenance_record_blocker(
                    blocker_code="command_binding_mismatch",
                    artifact_id=artifact_id,
                    field_path="$.command_surface.checker_name",
                    observed_shape=checker_name,
                    recommended_repair_action="Use a current SkillGuard checker command name.",
                )
            )
        if observed_names != current_names:
            blockers.append(
                maintenance_record_blocker(
                    blocker_code="command_binding_mismatch",
                    artifact_id=artifact_id,
                    field_path="$.command_surface.command_names",
                    observed_shape={"count": len(observed_names)},
                    recommended_repair_action="Regenerate the record after refreshing the current command dispatch surface.",
                )
            )
        if str(command_surface.get("checker_version") or "") != CHECKER_VERSION:
            blockers.append(
                maintenance_record_blocker(
                    blocker_code="command_binding_mismatch",
                    artifact_id=artifact_id,
                    field_path="$.command_surface.checker_version",
                    observed_shape=str(command_surface.get("checker_version") or ""),
                    recommended_repair_action="Regenerate the record with the current checker version.",
                )
            )
        recorded_registry = command_surface.get("current_route_registry")
        current_registry = [public_route_entry(entry) for entry in current_route_entries()]
        if recorded_registry != current_registry:
            blockers.append(
                maintenance_record_blocker(
                    blocker_code="route_binding_mismatch",
                    artifact_id=artifact_id,
                    field_path="$.command_surface.current_route_registry",
                    observed_shape={"count": len(recorded_registry) if isinstance(recorded_registry, list) else type(recorded_registry).__name__},
                    recommended_repair_action="Regenerate the record with the current route-task registry projection.",
                )
            )
    blockers_value = record.get("blockers")
    if not isinstance(blockers_value, list):
        blockers.append(
            maintenance_record_blocker(
                blocker_code="malformed_blocker_row",
                artifact_id=artifact_id,
                field_path="$.blockers",
                observed_shape=type(blockers_value).__name__,
                recommended_repair_action="Use a list of structured public blocker rows.",
            )
        )
    else:
        for index, row in enumerate(blockers_value):
            if not isinstance(row, dict):
                blockers.append(
                    maintenance_record_blocker(
                        blocker_code="malformed_blocker_row",
                        artifact_id=artifact_id,
                        field_path=f"$.blockers[{index}]",
                        observed_shape=type(row).__name__,
                        recommended_repair_action="Replace malformed blocker entries with structured blocker objects.",
                    )
                )
                continue
            missing = [
                field
                for field in ("blocker_class", "blocker_code", "artifact_id", "message", "recommended_repair_action")
                if not isinstance(row.get(field), str) or not str(row.get(field)).strip()
            ]
            if missing:
                blockers.append(
                    maintenance_record_blocker(
                        blocker_code="malformed_blocker_row",
                        artifact_id=artifact_id,
                        field_path=f"$.blockers[{index}]",
                        observed_shape={"missing_fields": missing},
                        recommended_repair_action="Regenerate blocker rows with class, code, artifact id, message, and repair action.",
                    )
                )
    for alias in maintenance_record_contains_forbidden_alias(record):
        blockers.append(
            maintenance_record_blocker(
                blocker_code="unknown_legacy_alias",
                artifact_id=artifact_id,
                field_path=alias["field_path"],
                observed_shape=alias["alias"],
                recommended_repair_action="Remove former aliases and rewrite the record in the sole current shape.",
            )
        )
    for finding in maintenance_record_public_boundary_findings(record):
        blockers.append(
            maintenance_record_blocker(
                blocker_code="public_boundary_leakage",
                artifact_id=artifact_id,
                field_path=str(finding.get("field_path") or "$"),
                observed_shape=str(finding.get("finding_id") or ""),
                recommended_repair_action="Remove sealed, private, credential-like, or local-machine content from public maintenance fields.",
            )
        )
    owner_action = record.get("owner_action")
    if not isinstance(owner_action, dict):
        blockers.append(
            maintenance_record_blocker(
                blocker_code="malformed_owner_action",
                artifact_id=artifact_id,
                field_path="$.owner_action",
                observed_shape=type(owner_action).__name__,
                recommended_repair_action="Regenerate owner_action as a structured object.",
            )
        )
    return blockers


def extract_current_maintenance_record(data: dict[str, Any], artifact_id: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]], str]:
    if isinstance(data.get("maintenance_record"), dict):
        return data["maintenance_record"], [], "current_nested"
    if data.get("schema_version") == MAINTENANCE_RECORD_SCHEMA_VERSION:
        return data, [], "current_direct"
    return None, [
        maintenance_record_blocker(
            blocker_code="non_current_maintenance_record",
            artifact_id=artifact_id,
            field_path="$.schema_version",
            observed_shape=data.get("schema_version"),
            recommended_repair_action="Rewrite the artifact directly as a current maintenance record before validation.",
        )
    ], "blocked_non_current"


def stale_hash_code_for(record: dict[str, Any], binding_kind: str) -> str:
    command = str(record.get("command") or "").strip()
    if binding_kind == "fixture_manifest":
        return "stale_fixture_manifest"
    if binding_kind == "fixture_case":
        return "stale_fixture_output"
    if binding_kind == "generated_artifact_hash":
        return "stale_generated_artifact_hash"
    if command in {"self-check", "commands"}:
        return "stale_command_or_self_check_record"
    return "stale_source_fingerprint"


def compare_recorded_hash_binding(
    *,
    record: dict[str, Any],
    record_path: Path,
    stale_blockers: list[dict[str, Any]],
    artifact_id: str,
    binding_kind: str,
    binding_id: str,
    path_text: Any,
    recorded_sha: Any,
    base_dir: Path | None = None,
) -> bool:
    label = public_binding_path_label(path_text, base_dir)
    recorded_hash = normalized_recorded_sha256(recorded_sha)
    if not isinstance(path_text, str) or not path_text.strip() or not recorded_hash:
        missing_fields = []
        if not isinstance(path_text, str) or not path_text.strip():
            missing_fields.append("path")
        if not recorded_hash:
            missing_fields.append("sha256")
        add_stale_evidence_blocker(
            stale_blockers,
            artifact_id=artifact_id,
            blocker_code="missing_evidence_metadata",
            binding_kind=binding_kind,
            binding_id=binding_id,
            expected_current_binding={"required_fields": ["path", "sha256"], "record": public_relative_path(record_path)},
            observed_stale_binding={"path": label, "missing_fields": missing_fields},
            stale_reason="evidence binding is missing metadata required for a current hash comparison.",
            recommended_owner_action="Regenerate the evidence artifact with repository-relative path and sha256 metadata.",
        )
        return False
    try:
        resolved = resolve_repository_reference(path_text, base_dir)
    except ValueError:
        add_stale_evidence_blocker(
            stale_blockers,
            artifact_id=artifact_id,
            blocker_code="invalid_evidence_path",
            binding_kind=binding_kind,
            binding_id=binding_id,
            expected_current_binding={"path_boundary": "repository-relative path under the repository root"},
            observed_stale_binding={"path": label, "sha256": recorded_hash},
            stale_reason="recorded evidence path is outside the repository boundary or cannot be resolved safely.",
            recommended_owner_action="Regenerate the evidence artifact with repository-local paths only.",
        )
        return False

    relative = public_relative_path(resolved)
    if not resolved.is_file():
        add_stale_evidence_blocker(
            stale_blockers,
            artifact_id=artifact_id,
            blocker_code="missing_evidence_artifact",
            binding_kind=binding_kind,
            binding_id=binding_id,
            expected_current_binding={"path": relative, "exists": True, "kind": "file"},
            observed_stale_binding={"path": relative, "exists": resolved.exists(), "sha256": recorded_hash},
            stale_reason="recorded evidence path no longer points to a current file.",
            recommended_owner_action="Restore the referenced artifact or regenerate the evidence record from current files.",
        )
        return True

    current_sha = file_sha256(resolved)
    if current_sha != recorded_hash:
        add_stale_evidence_blocker(
            stale_blockers,
            artifact_id=artifact_id,
            blocker_code=stale_hash_code_for(record, binding_kind),
            binding_kind=binding_kind,
            binding_id=binding_id,
            expected_current_binding={"path": relative, "sha256": current_sha},
            observed_stale_binding={"path": relative, "sha256": recorded_hash},
            stale_reason="recorded sha256 differs from the current file sha256.",
            recommended_owner_action="Rerun the command or fixture that produced this evidence against current files.",
        )
    return True


def check_recorded_hash_entries(
    *,
    record: dict[str, Any],
    record_path: Path,
    stale_blockers: list[dict[str, Any]],
    artifact_id: str,
    field_name: str,
    binding_kind: str,
) -> int:
    entries = record.get(field_name)
    if entries is None:
        return 0
    if not isinstance(entries, list):
        add_stale_evidence_blocker(
            stale_blockers,
            artifact_id=artifact_id,
            blocker_code="missing_evidence_metadata",
            binding_kind=binding_kind,
            binding_id=field_name,
            expected_current_binding={field_name: "list of path/sha256 bindings"},
            observed_stale_binding={field_name: type(entries).__name__},
            stale_reason="evidence metadata field has an unsupported shape.",
            recommended_owner_action="Regenerate the evidence artifact with a list-shaped metadata field.",
        )
        return 0

    checked = 0
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            add_stale_evidence_blocker(
                stale_blockers,
                artifact_id=artifact_id,
                blocker_code="missing_evidence_metadata",
                binding_kind=binding_kind,
                binding_id=f"{field_name}[{index}]",
                expected_current_binding={"entry": "object with path and sha256"},
                observed_stale_binding={"entry_type": type(entry).__name__},
                stale_reason="evidence metadata entry is not an object.",
                recommended_owner_action="Regenerate the evidence artifact with structured path/hash entries.",
            )
            continue
        path_text = entry.get("resolved_path") or entry.get("path") or entry.get("source_path")
        if compare_recorded_hash_binding(
            record=record,
            record_path=record_path,
            stale_blockers=stale_blockers,
            artifact_id=artifact_id,
            binding_kind=binding_kind,
            binding_id=f"{field_name}[{index}]",
            path_text=path_text,
            recorded_sha=entry.get("sha256"),
            base_dir=None,
        ):
            checked += 1
    return checked


def check_fixture_result_hashes(
    *,
    record: dict[str, Any],
    record_path: Path,
    stale_blockers: list[dict[str, Any]],
    artifact_id: str,
) -> int:
    results = record.get("fixture_results")
    if results is None:
        return 0
    if not isinstance(results, list):
        add_stale_evidence_blocker(
            stale_blockers,
            artifact_id=artifact_id,
            blocker_code="missing_evidence_metadata",
            binding_kind="fixture_case",
            binding_id="fixture_results",
            expected_current_binding={"fixture_results": "list of fixture case result bindings"},
            observed_stale_binding={"fixture_results": type(results).__name__},
            stale_reason="fixture output metadata has an unsupported shape.",
            recommended_owner_action="Rerun fixture-test to regenerate structured fixture results.",
        )
        return 0
    checked = 0
    for index, result in enumerate(results):
        if not isinstance(result, dict):
            continue
        fixture_path = result.get("fixture_path")
        if compare_recorded_hash_binding(
            record=record,
            record_path=record_path,
            stale_blockers=stale_blockers,
            artifact_id=artifact_id,
            binding_kind="fixture_case",
            binding_id=f"fixture_results[{index}]",
            path_text=fixture_path,
            recorded_sha=result.get("sha256"),
            base_dir=None,
        ):
            checked += 1
    return checked


def check_fixture_manifest_binding(
    *,
    record: dict[str, Any],
    record_path: Path,
    stale_blockers: list[dict[str, Any]],
    artifact_id: str,
) -> int:
    if record.get("command") != "fixture-test":
        return 0
    target_path = record.get("target_path")
    if not isinstance(target_path, str) or not target_path:
        add_stale_evidence_blocker(
            stale_blockers,
            artifact_id=artifact_id,
            blocker_code="missing_evidence_metadata",
            binding_kind="fixture_manifest",
            binding_id="target_path",
            expected_current_binding={"target_path": "repository-relative fixture manifest path"},
            observed_stale_binding={"target_path": str(target_path or "")},
            stale_reason="fixture-test output does not identify the fixture manifest it claims to cover.",
            recommended_owner_action="Rerun fixture-test with a current explicit fixture manifest.",
        )
        return 0
    manifest_entries = [
        item
        for item in record.get("files_inspected", [])
        if isinstance(item, dict) and (item.get("path") == target_path or item.get("resolved_path") == target_path)
    ]
    if not manifest_entries:
        add_stale_evidence_blocker(
            stale_blockers,
            artifact_id=artifact_id,
            blocker_code="missing_evidence_metadata",
            binding_kind="fixture_manifest",
            binding_id="files_inspected[target_path]",
            expected_current_binding={"path": target_path, "sha256": "current fixture manifest hash"},
            observed_stale_binding={"path": target_path, "sha256": ""},
            stale_reason="fixture-test output is missing hash metadata for its target manifest.",
            recommended_owner_action="Rerun fixture-test so the target manifest hash is recorded.",
        )
        return 0
    entry = manifest_entries[0]
    return 1 if compare_recorded_hash_binding(
        record=record,
        record_path=record_path,
        stale_blockers=stale_blockers,
        artifact_id=artifact_id,
        binding_kind="fixture_manifest",
        binding_id="files_inspected[target_path]",
        path_text=target_path,
        recorded_sha=entry.get("sha256"),
        base_dir=None,
    ) else 0


def check_generated_artifact_paths(
    *,
    record: dict[str, Any],
    record_path: Path,
    stale_blockers: list[dict[str, Any]],
    artifact_id: str,
) -> int:
    checked = 0
    path_fields = (
        "all_scaffold_files",
        "all_suite_files",
        "created_files",
        "required_scaffold_files",
        "required_suite_files",
        "child_skill_paths",
    )
    for field_name in path_fields:
        values = record.get(field_name)
        if values is None:
            continue
        if not isinstance(values, list):
            add_stale_evidence_blocker(
                stale_blockers,
                artifact_id=artifact_id,
                blocker_code="missing_evidence_metadata",
                binding_kind="generated_artifact_path",
                binding_id=field_name,
                expected_current_binding={field_name: "list of repository-relative generated artifact paths"},
                observed_stale_binding={field_name: type(values).__name__},
                stale_reason="generated artifact metadata has an unsupported shape.",
                recommended_owner_action="Regenerate the scaffold command output with structured path lists.",
            )
            continue
        for index, value in enumerate(values):
            if not isinstance(value, str) or not value:
                continue
            try:
                path = resolve_repository_reference(value)
            except ValueError:
                add_stale_evidence_blocker(
                    stale_blockers,
                    artifact_id=artifact_id,
                    blocker_code="invalid_evidence_path",
                    binding_kind="generated_artifact_path",
                    binding_id=f"{field_name}[{index}]",
                    expected_current_binding={"path_boundary": "repository-relative path under the repository root"},
                    observed_stale_binding={"path": public_binding_path_label(value)},
                    stale_reason="generated artifact path is outside the repository boundary.",
                    recommended_owner_action="Regenerate the scaffold command output with repository-local generated artifact paths.",
                )
                continue
            relative = public_relative_path(path)
            checked += 1
            if not path.exists():
                add_stale_evidence_blocker(
                    stale_blockers,
                    artifact_id=artifact_id,
                    blocker_code="stale_generated_artifact_path",
                    binding_kind="generated_artifact_path",
                    binding_id=f"{field_name}[{index}]",
                    expected_current_binding={"path": relative, "exists": True},
                    observed_stale_binding={"path": relative, "exists": False},
                    stale_reason="generated artifact path recorded by evidence output is no longer present.",
                    recommended_owner_action="Restore the generated artifact or rerun the generator/check that owns this evidence.",
                )
    for index, check in enumerate(record.get("post_generation_checks", []) if isinstance(record.get("post_generation_checks"), list) else []):
        if not isinstance(check, dict):
            continue
        artifact_path = check.get("artifact_path")
        if not isinstance(artifact_path, str) or not artifact_path:
            continue
        try:
            path = resolve_repository_reference(artifact_path)
        except ValueError:
            continue
        checked += 1
        if not path.exists():
            add_stale_evidence_blocker(
                stale_blockers,
                artifact_id=artifact_id,
                blocker_code="stale_generated_artifact_path",
                binding_kind="post_generation_artifact",
                binding_id=f"post_generation_checks[{index}].artifact_path",
                expected_current_binding={"path": public_relative_path(path), "exists": True},
                observed_stale_binding={"path": public_relative_path(path), "exists": False},
                stale_reason="post-generation check artifact path is no longer present.",
                recommended_owner_action="Restore the generated artifact or rerun the generator/check that owns this evidence.",
            )
    checked += check_recorded_hash_entries(
        record=record,
        record_path=record_path,
        stale_blockers=stale_blockers,
        artifact_id=artifact_id,
        field_name="generated_artifact_hashes",
        binding_kind="generated_artifact_hash",
    )
    return checked


def current_openspec_changes_present() -> bool:
    return (repository_root() / "openspec" / "changes").exists() or (repository_root() / "specs").exists()


def check_route_and_command_metadata(
    *,
    record: dict[str, Any],
    record_path: Path,
    stale_blockers: list[dict[str, Any]],
    artifact_id: str,
    expected_route_version: str,
    expected_route_registry_version: str,
) -> int:
    checked = 0
    route_version = record.get("route_version")
    if route_version is not None:
        checked += 1
        if str(route_version) != expected_route_version:
            add_stale_evidence_blocker(
                stale_blockers,
                artifact_id=artifact_id,
                blocker_code="stale_route_version",
                binding_kind="route_version",
                binding_id="route_version",
                expected_current_binding={"route_version": expected_route_version},
                observed_stale_binding={"route_version": str(route_version)},
                stale_reason="recorded route version differs from the current expected route version.",
                recommended_owner_action="Regenerate the evidence against the current route version before using it for acceptance.",
            )

    registry_version = record.get("route_registry_version")
    if registry_version is not None:
        checked += 1
        if str(registry_version) != expected_route_registry_version:
            add_stale_evidence_blocker(
                stale_blockers,
                artifact_id=artifact_id,
                blocker_code="stale_route_registry_version",
                binding_kind="route_registry_version",
                binding_id="route_registry_version",
                expected_current_binding={"route_registry_version": expected_route_registry_version},
                observed_stale_binding={"route_registry_version": str(registry_version)},
                stale_reason="recorded route registry version differs from the current route-task registry version.",
                recommended_owner_action="Rerun route-task or fixture-test outputs that captured the older route registry.",
            )

    command_names = record.get("command_names")
    if command_names is not None:
        checked += 1
        current_names = list(COMMANDS)
        observed_names = [str(item) for item in command_names] if isinstance(command_names, list) else []
        if observed_names != current_names:
            add_stale_evidence_blocker(
                stale_blockers,
                artifact_id=artifact_id,
                blocker_code="stale_command_surface",
                binding_kind="command_surface",
                binding_id="command_names",
                expected_current_binding={"command_names": current_names},
                observed_stale_binding={
                    "command_names": observed_names,
                    "missing_commands": sorted(set(current_names) - set(observed_names)),
                    "extra_commands": sorted(set(observed_names) - set(current_names)),
                },
                stale_reason="recorded command surface differs from the current SkillGuard dispatch table.",
                recommended_owner_action="Rerun self-check or commands after command dispatch changes.",
            )

    recorded_registry = record.get("current_route_registry")
    if recorded_registry is not None:
        checked += 1
        current_registry = [public_route_entry(entry) for entry in current_route_entries()]
        if recorded_registry != current_registry:
            add_stale_evidence_blocker(
                stale_blockers,
                artifact_id=artifact_id,
                blocker_code="stale_route_registry",
                binding_kind="route_registry",
                binding_id="current_route_registry",
                expected_current_binding={"route_ids": [entry["route_id"] for entry in current_registry]},
                observed_stale_binding={
                    "route_ids": [
                        str(entry.get("route_id"))
                        for entry in recorded_registry
                        if isinstance(entry, dict) and entry.get("route_id")
                    ]
                },
                stale_reason="recorded route registry entries differ from current route-task registry entries.",
                recommended_owner_action="Rerun route-task or fixture-test outputs that captured the older route registry.",
            )
    return checked


def check_openspec_status_metadata(
    *,
    record: dict[str, Any],
    stale_blockers: list[dict[str, Any]],
    artifact_id: str,
) -> int:
    status = record.get("openspec_status") or record.get("openspec")
    if status is None:
        return 0
    if not isinstance(status, dict):
        add_stale_evidence_blocker(
            stale_blockers,
            artifact_id=artifact_id,
            blocker_code="missing_evidence_metadata",
            binding_kind="openspec_status",
            binding_id="openspec_status",
            expected_current_binding={"openspec_status": "object with changes_directory_present metadata"},
            observed_stale_binding={"openspec_status": type(status).__name__},
            stale_reason="OpenSpec status metadata has an unsupported shape.",
            recommended_owner_action="Regenerate the evidence with structured OpenSpec status metadata.",
        )
        return 0
    checked = 1
    current_changes_present = current_openspec_changes_present()
    observed = status.get("changes_directory_present")
    if observed is None:
        observed = status.get("changes_directory_found")
    if observed is None:
        add_stale_evidence_blocker(
            stale_blockers,
            artifact_id=artifact_id,
            blocker_code="missing_evidence_metadata",
            binding_kind="openspec_status",
            binding_id="openspec_status.changes_directory_present",
            expected_current_binding={"changes_directory_present": current_changes_present},
            observed_stale_binding={"changes_directory_present": ""},
            stale_reason="OpenSpec status metadata cannot be compared without the recorded changes-directory state.",
            recommended_owner_action="Regenerate the evidence with current OpenSpec list/validate status metadata.",
        )
    elif bool(observed) != current_changes_present:
        add_stale_evidence_blocker(
            stale_blockers,
            artifact_id=artifact_id,
            blocker_code="stale_openspec_status",
            binding_kind="openspec_status",
            binding_id="openspec_status.changes_directory_present",
            expected_current_binding={"changes_directory_present": current_changes_present},
            observed_stale_binding={"changes_directory_present": bool(observed)},
            stale_reason="recorded OpenSpec changes-directory status differs from the current repository state.",
            recommended_owner_action="Rerun OpenSpec status/validation and regenerate the evidence record.",
        )
    return checked


def check_nested_maintenance_record_metadata(
    *,
    record: dict[str, Any],
    stale_blockers: list[dict[str, Any]],
    artifact_id: str,
    expected_route_version: str,
    expected_route_registry_version: str,
) -> int:
    maintenance_record = record.get("maintenance_record")
    if maintenance_record is None:
        return 0
    blockers = validate_maintenance_record(
        maintenance_record,
        artifact_id=artifact_id,
        expected_route_version=expected_route_version,
        expected_route_registry_version=expected_route_registry_version,
    )
    for blocker in blockers:
        add_stale_evidence_blocker(
            stale_blockers,
            artifact_id=artifact_id,
            blocker_code=str(blocker.get("blocker_code") or "maintenance_record_schema_blocker"),
            binding_kind="maintenance_record",
            binding_id=str(blocker.get("field_path") or "maintenance_record"),
            expected_current_binding={"schema_version": MAINTENANCE_RECORD_SCHEMA_VERSION},
            observed_stale_binding={
                "observed_shape": blocker.get("observed_shape"),
                "field_path": blocker.get("field_path"),
            },
            stale_reason="nested maintenance_record does not match the canonical public maintenance record schema or current route/command bindings.",
            recommended_owner_action=str(blocker.get("recommended_repair_action") or "Regenerate the maintenance record with current canonical metadata."),
        )
    return 1


def inspect_stale_evidence_record(
    *,
    record: dict[str, Any],
    record_path: Path,
    expected_route_version: str,
    expected_route_registry_version: str,
) -> tuple[list[dict[str, Any]], int]:
    artifact_id = public_relative_path(record_path)
    stale_blockers: list[dict[str, Any]] = []
    checked = 0
    checked += check_recorded_hash_entries(
        record=record,
        record_path=record_path,
        stale_blockers=stale_blockers,
        artifact_id=artifact_id,
        field_name="files_inspected",
        binding_kind="source_fingerprint",
    )
    checked += check_recorded_hash_entries(
        record=record,
        record_path=record_path,
        stale_blockers=stale_blockers,
        artifact_id=artifact_id,
        field_name="evidence_references",
        binding_kind="evidence_reference",
    )
    checked += check_recorded_hash_entries(
        record=record,
        record_path=record_path,
        stale_blockers=stale_blockers,
        artifact_id=artifact_id,
        field_name="reports_inspected",
        binding_kind="report_input",
    )
    checked += check_fixture_manifest_binding(
        record=record,
        record_path=record_path,
        stale_blockers=stale_blockers,
        artifact_id=artifact_id,
    )
    checked += check_fixture_result_hashes(
        record=record,
        record_path=record_path,
        stale_blockers=stale_blockers,
        artifact_id=artifact_id,
    )
    checked += check_generated_artifact_paths(
        record=record,
        record_path=record_path,
        stale_blockers=stale_blockers,
        artifact_id=artifact_id,
    )
    checked += check_route_and_command_metadata(
        record=record,
        record_path=record_path,
        stale_blockers=stale_blockers,
        artifact_id=artifact_id,
        expected_route_version=expected_route_version,
        expected_route_registry_version=expected_route_registry_version,
    )
    checked += check_openspec_status_metadata(record=record, stale_blockers=stale_blockers, artifact_id=artifact_id)
    checked += check_nested_maintenance_record_metadata(
        record=record,
        stale_blockers=stale_blockers,
        artifact_id=artifact_id,
        expected_route_version=expected_route_version,
        expected_route_registry_version=expected_route_registry_version,
    )
    if checked == 0:
        add_stale_evidence_blocker(
            stale_blockers,
            artifact_id=artifact_id,
            blocker_code="missing_evidence_metadata",
            binding_kind="record_metadata",
            binding_id="record",
            expected_current_binding={
                "accepted_binding_metadata": [
                    "files_inspected.path+sha256",
                    "evidence_references.path+sha256",
                    "fixture_results.fixture_path+sha256",
                    "route_version",
                    "route_registry_version",
                    "command_names",
                    "generated artifact paths",
                    "openspec_status",
                    "maintenance_record",
                ]
            },
            observed_stale_binding={"metadata_bindings_checked": 0},
            stale_reason="record has no comparable freshness metadata, so it cannot support a current evidence claim.",
            recommended_owner_action="Regenerate the evidence with source fingerprints, route/command metadata, fixture bindings, or generated artifact paths.",
        )
    return stale_blockers, checked


def freshness_blocker_counts(stale_blockers: list[dict[str, Any]]) -> dict[str, int]:
    missing_count = 0
    for blocker in stale_blockers:
        code = str(blocker.get("blocker_code") or "")
        if code in MAINTENANCE_MISSING_BLOCKER_CODES:
            missing_count += 1
    return {
        "missing_count": missing_count,
        "stale_count": len(stale_blockers) - missing_count,
        "owner_rerun_required_count": len(stale_blockers),
    }


def maintenance_freshness_summary(
    *,
    input_requested: bool,
    inspected_artifacts: list[dict[str, Any]],
    stale_blockers: list[dict[str, Any]],
    freshness_bindings_checked: int,
) -> dict[str, Any]:
    counts = freshness_blocker_counts(stale_blockers)
    state = "fresh" if input_requested and not stale_blockers else "stale_or_missing"
    if not input_requested:
        state = "missing"
    return {
        "schema_version": "skillguard.maintenance_freshness_state.v1",
        "state": state,
        "states_supported": sorted(MAINTENANCE_FRESHNESS_STATES),
        "current_evidence_can_pass": state == "fresh",
        "input_artifact_count": len(inspected_artifacts),
        "freshness_bindings_checked": freshness_bindings_checked,
        "stale_count": counts["stale_count"],
        "missing_count": counts["missing_count"],
        "owner_rerun_required_count": counts["owner_rerun_required_count"],
        "recorded_source_status_fields": [
            "inspected_artifacts[].path",
            "inspected_artifacts[].sha256",
            "freshness_bindings_checked",
            "stale_evidence_blockers[].expected_current_binding",
            "stale_evidence_blockers[].observed_stale_binding",
            "stale_evidence_blockers[].recommended_owner_action",
        ],
        "stale_or_missing_blocker_codes": sorted({str(item.get("blocker_code") or "") for item in stale_blockers}),
    }


def detect_stale_evidence(argv: list[str]) -> int:
    parser = JsonArgumentParser(
        prog="skillguard.py detect-stale-evidence",
        description="Detect stale or unverifiable SkillGuard evidence records without mutating source artifacts.",
    )
    parser.add_argument("--input", action="append", default=[], help="Evidence-bearing JSON artifact under the repository root. Repeatable.")
    parser.add_argument("--target", default=".agents/skills/skillguard", help="Target skill root used for claim boundary and reporting.")
    parser.add_argument("--expected-route-version", default=DETECT_STALE_EXPECTED_ROUTE_VERSION, help="Current FlowPilot route version expected in evidence metadata.")
    parser.add_argument(
        "--expected-route-registry-version",
        default=ROUTE_TASK_REGISTRY_VERSION,
        help="Current route-task registry version expected in evidence metadata.",
    )
    parser.add_argument("--output", default="-", help="Output report path under the skill root, or '-' for stdout.")
    args = parser.parse_args(argv)

    try:
        target = resolve_target_argument(args.target)
        target_relative = public_relative_path(target)
    except ValueError:
        payload = base_result("detect-stale-evidence")
        payload["decision"] = "block"
        payload["blockers"] = ["target path must stay under the repository root"]
        return write_and_exit(payload, args.output)

    payload = base_result("detect-stale-evidence", target_relative)
    payload["claim_boundary"] = (
        "This detect-stale-evidence result covers only the evidence-bearing JSON artifacts supplied through --input and "
        "the current repository files, route metadata, command table, fixture bindings, generated artifact paths, and OpenSpec "
        "status metadata they explicitly record. It does not inspect sealed FlowPilot packet bodies, sibling role result text, "
        "external services, release readiness, package publication, suite automation, code-contract validation, or future AI behavior."
    )
    payload["expected_route_version"] = str(args.expected_route_version)
    payload["expected_route_registry_version"] = str(args.expected_route_registry_version)

    input_paths: list[Path] = []
    blockers: list[str] = []
    stale_evidence_blockers: list[dict[str, Any]] = []
    inspected_artifacts: list[dict[str, Any]] = []
    checked_bindings = 0

    if not args.input:
        blockers.append("detect-stale-evidence requires at least one --input evidence JSON artifact under the repository root")

    for input_value in args.input:
        try:
            input_path = ensure_under_root(input_value)
        except ValueError:
            add_stale_evidence_blocker(
                stale_evidence_blockers,
                artifact_id="<input>",
                blocker_code="invalid_evidence_path",
                binding_kind="input_artifact",
                binding_id="--input",
                expected_current_binding={"path_boundary": "repository-relative path under the repository root"},
                observed_stale_binding={"path": public_binding_path_label(input_value)},
                stale_reason="input evidence artifact path is outside the repository boundary.",
                recommended_owner_action="Supply repository-local evidence artifact paths only.",
            )
            continue
        input_paths.append(input_path)

    for input_path in input_paths:
        input_relative = public_relative_path(input_path)
        if not input_path.is_file():
            add_stale_evidence_blocker(
                stale_evidence_blockers,
                artifact_id=input_relative,
                blocker_code="missing_evidence_artifact",
                binding_kind="input_artifact",
                binding_id="--input",
                expected_current_binding={"path": input_relative, "exists": True, "kind": "file"},
                observed_stale_binding={"path": input_relative, "exists": input_path.exists()},
                stale_reason="input evidence artifact is missing or not a file.",
                recommended_owner_action="Restore the evidence artifact or rerun the command that should produce it.",
            )
            continue
        inspected_artifacts.append(checked_file(input_path, "json"))
        try:
            record = load_json(input_path)
        except ValueError:
            add_stale_evidence_blocker(
                stale_evidence_blockers,
                artifact_id=input_relative,
                blocker_code="missing_evidence_metadata",
                binding_kind="input_artifact",
                binding_id="json",
                expected_current_binding={"json_parse": "valid JSON object"},
                observed_stale_binding={"json_parse": "failed"},
                stale_reason="input evidence artifact is not parseable JSON.",
                recommended_owner_action="Regenerate the evidence artifact as valid JSON.",
            )
            continue
        if not isinstance(record, dict):
            add_stale_evidence_blocker(
                stale_evidence_blockers,
                artifact_id=input_relative,
                blocker_code="missing_evidence_metadata",
                binding_kind="input_artifact",
                binding_id="json",
                expected_current_binding={"json_root": "object"},
                observed_stale_binding={"json_root": type(record).__name__},
                stale_reason="input evidence artifact root is not a JSON object.",
                recommended_owner_action="Regenerate the evidence artifact as a structured JSON object.",
            )
            continue
        record_blockers, record_checked = inspect_stale_evidence_record(
            record=record,
            record_path=input_path,
            expected_route_version=str(args.expected_route_version),
            expected_route_registry_version=str(args.expected_route_registry_version),
        )
        checked_bindings += record_checked
        stale_evidence_blockers.extend(record_blockers)

    if stale_evidence_blockers:
        blockers.extend(
            f"{item['artifact_id']}: {item['blocker_code']} at {item['binding_id']}"
            for item in stale_evidence_blockers
        )

    payload["inspected_artifacts"] = inspected_artifacts
    payload["stale_evidence_blockers"] = stale_evidence_blockers
    payload["stale_evidence_count"] = len(stale_evidence_blockers)
    payload["freshness_bindings_checked"] = checked_bindings
    payload["maintenance_freshness"] = maintenance_freshness_summary(
        input_requested=bool(args.input),
        inspected_artifacts=inspected_artifacts,
        stale_blockers=stale_evidence_blockers,
        freshness_bindings_checked=checked_bindings,
    )
    payload["checks"] = [
        {
            "check_id": "detect-stale-evidence:input-artifacts",
            "name": "Evidence artifact inputs",
            "required": True,
            "status": "block" if not args.input or any(item["blocker_code"] in {"invalid_evidence_path", "missing_evidence_artifact"} for item in stale_evidence_blockers) else "pass",
            "summary": f"Loaded {len(inspected_artifacts)} evidence JSON artifact(s) supplied by --input.",
        },
        {
            "check_id": "detect-stale-evidence:freshness-bindings",
            "name": "Freshness bindings",
            "required": True,
            "status": "block" if stale_evidence_blockers else "pass",
            "summary": (
                "Compared recorded source fingerprints, fixture bindings, generated artifact paths, route metadata, command surface, "
                "and OpenSpec status metadata against current repository state."
            ),
        },
        {
            "check_id": "detect-stale-evidence:no-mutation",
            "name": "Read-only source artifact inspection",
            "required": True,
            "status": "pass",
            "summary": "The command reads input evidence and referenced files only; it does not delete, rewrite, regenerate, or normalize source artifacts.",
        },
    ]
    payload["evidence"] = [
        {
            "evidence_id": "detect-stale-input-artifacts",
            "kind": "parser_output",
            "fresh": True,
            "summary": f"Parsed {len(inspected_artifacts)} evidence artifact(s); checked {checked_bindings} freshness binding(s).",
            "source_path": target_relative,
        },
        {
            "evidence_id": "detect-stale-current-command-surface",
            "kind": "command_table_check",
            "fresh": True,
            "summary": f"Compared any recorded command_names against {len(COMMANDS)} current dispatch command(s).",
            "source_path": ".agents/skills/skillguard/scripts/checker_engine.py",
        },
    ]
    payload["blockers"] = blockers
    payload["decision"] = "block" if blockers else "pass"
    payload["skipped_checks"] = [
        "detect-stale-evidence does not refresh stale artifacts, execute target commands, run OpenSpec itself, run fixture-test, or perform closure."
    ]
    payload["residual_risk"] = [
        "Evidence artifacts without explicit comparable metadata are intentionally blocked as unverifiable rather than accepted.",
        "This stale detector checks declared path/hash/route/command bindings; semantic adequacy still requires the owning checker or reviewer.",
    ]
    attach_maintenance_record(
        payload,
        record_kind="stale_evidence_review",
        artifact_id=target_relative,
        route_node_id="detect-stale-evidence",
        checker_name="detect-stale-evidence",
        blockers=stale_evidence_blockers,
        owner_action={"action": "detect_only", "status": "not_applicable", "stale_evidence_count": len(stale_evidence_blockers)},
        content_seed={"inspected_artifacts": [item.get("path") for item in inspected_artifacts], "checked_bindings": checked_bindings},
    )
    return write_and_exit(payload, args.output)


def check_maintenance_record(argv: list[str]) -> int:
    parser = JsonArgumentParser(
        prog="skillguard.py check-maintenance-record",
        description="Validate or normalize one public SkillGuard maintenance record against the canonical schema.",
    )
    parser.add_argument("--input", required=True, help="Current maintenance record JSON under the repository root.")
    parser.add_argument("--target", default=".agents/skills/skillguard", help="Target skill root used for claim boundary and reporting.")
    parser.add_argument("--expected-route-version", default=DETECT_STALE_EXPECTED_ROUTE_VERSION, help="Current route version expected in the maintenance record.")
    parser.add_argument(
        "--expected-route-registry-version",
        default=ROUTE_TASK_REGISTRY_VERSION,
        help="Current route-task registry version expected in the maintenance record.",
    )
    parser.add_argument("--output", default="-", help="Output report path under the skill root, or '-' for stdout.")
    args = parser.parse_args(argv)

    try:
        target = resolve_target_argument(args.target)
        target_relative = public_relative_path(target)
    except ValueError:
        payload = base_result("check-maintenance-record")
        payload["decision"] = "block"
        payload["blockers"] = ["target path must stay under the repository root"]
        return write_and_exit(payload, args.output)

    payload = base_result("check-maintenance-record", target_relative)
    payload["schema_version"] = MAINTENANCE_RECORD_RESULT_SCHEMA
    payload["claim_boundary"] = (
        "This check-maintenance-record result validates only the sole current public maintenance record shape. "
        "It does not expose sealed FlowPilot packet bodies, private task text, sibling role result text, "
        "release readiness, package publication, suite automation, code-contract validation, or future AI behavior."
    )
    payload["expected_schema_version"] = MAINTENANCE_RECORD_SCHEMA_VERSION
    payload["expected_route_version"] = str(args.expected_route_version)
    payload["expected_route_registry_version"] = str(args.expected_route_registry_version)
    blockers: list[str] = []
    maintenance_record_blockers: list[dict[str, Any]] = []
    input_relative = ""
    normalized_record: dict[str, Any] | None = None
    record_shape = "unread"

    try:
        input_path = ensure_under_root(args.input)
        input_relative = public_relative_path(input_path)
        payload["files_inspected"] = [checked_file(input_path, "json")] if input_path.is_file() else []
        data = load_json(input_path)
        if not isinstance(data, dict):
            raise ValueError("input JSON root must be an object")
        normalized_record, shape_blockers, record_shape = extract_current_maintenance_record(data, input_relative)
        maintenance_record_blockers.extend(shape_blockers)
        if normalized_record is not None and not shape_blockers:
            maintenance_record_blockers.extend(
                validate_maintenance_record(
                    normalized_record,
                    artifact_id=input_relative,
                    expected_route_version=str(args.expected_route_version),
                    expected_route_registry_version=str(args.expected_route_registry_version),
                )
            )
    except (OSError, ValueError) as exc:
        maintenance_record_blockers.append(
            maintenance_record_blocker(
                blocker_code="missing_required_field",
                artifact_id=maintenance_record_path_label(args.input),
                field_path="$",
                observed_shape=str(exc),
                recommended_repair_action="Provide a parseable repository-local JSON object for maintenance record validation.",
            )
        )

    blockers.extend(f"{item['artifact_id']}: {item['blocker_code']} at {item['field_path']}" for item in maintenance_record_blockers)
    payload["input_path"] = input_relative or maintenance_record_path_label(args.input)
    payload["record_shape"] = record_shape
    payload["normalized_record"] = normalized_record if normalized_record is not None and not maintenance_record_blockers else {}
    payload["maintenance_record_blockers"] = maintenance_record_blockers
    payload["checks"] = [
        {
            "check_id": "check-maintenance-record:input-json",
            "name": "Maintenance record input JSON",
            "required": True,
            "status": "block" if not input_relative else "pass",
            "summary": "Loaded a repository-local JSON object for maintenance record validation.",
        },
        {
            "check_id": "check-maintenance-record:schema",
            "name": "Canonical maintenance record schema",
            "required": True,
            "status": "block" if maintenance_record_blockers else "pass",
            "summary": "Checked current required fields, exact schema version, blocker rows, route metadata, command bindings, forbidden former aliases, and public-boundary safety.",
        },
    ]
    payload["evidence"] = [
        {
            "evidence_id": "maintenance-record-input",
            "kind": "parser_output",
            "fresh": True,
            "summary": f"Parsed maintenance record input {input_relative or '<unloaded>'}.",
            "source_path": input_relative,
        },
        {
            "evidence_id": "maintenance-record-current-bindings",
            "kind": "command_table_check",
            "fresh": True,
            "summary": f"Validated against {MAINTENANCE_RECORD_SCHEMA_VERSION}, route version {args.expected_route_version}, and {len(COMMANDS)} command(s).",
            "source_path": ".agents/skills/skillguard/scripts/checker_engine.py",
        },
    ]
    payload["skipped_checks"] = [
        "check-maintenance-record is read-only; it does not rewrite non-current artifacts, refresh stale evidence, inspect sealed FlowPilot bodies, or make closure decisions."
    ]
    payload["residual_risk"] = [
        "A current record shape does not by itself prove semantic adequacy; the owning command or reviewer evidence is still required."
    ]
    payload["blockers"] = blockers
    payload["decision"] = "block" if blockers else "pass"
    attach_maintenance_record(
        payload,
        record_kind="workflow_evidence",
        artifact_id=input_relative or maintenance_record_path_label(args.input),
        route_node_id="check-maintenance-record",
        checker_name="check-maintenance-record",
        blockers=maintenance_record_blockers,
        owner_action={"action": "validate_current", "status": record_shape},
        content_seed={"input_path": input_relative, "record_shape": record_shape},
    )
    return write_and_exit(payload, args.output)


def review_string_list(value: Any) -> list[str]:
    if isinstance(value, str) and value:
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if isinstance(item, (str, int, float))]
    return []


def checker_change_suite_guard_values(value: Any) -> list[str]:
    values = review_string_list(value)
    return [item.strip() for item in values if item.strip()]


def checker_change_suite_guard_blocker(
    *,
    blocker_code: str,
    message: str,
    suite_impact_class: str,
    selected_suites: list[str],
    evidence_path: str = "",
    evidence_state: str = "",
    recommended_resolution: str,
) -> dict[str, Any]:
    return {
        "blocker_class": "checker_change_suite_guard",
        "blocker_code": blocker_code,
        "message": message[:300],
        "suite_impact_class": suite_impact_class,
        "selected_suites": selected_suites,
        "evidence_path": evidence_path,
        "evidence_state": evidence_state,
        "recommended_resolution": recommended_resolution[:300],
    }


def checker_change_guard_add_blocker(blockers: list[dict[str, Any]], **kwargs: Any) -> None:
    blockers.append(checker_change_suite_guard_blocker(**kwargs))


def checker_change_suite_guard_enabled(
    *,
    review_paths: list[str],
    selected_suites: list[str],
    suite_impact_class: str,
    required: bool,
) -> bool:
    return bool(required or review_paths or selected_suites or suite_impact_class not in {"", "none"})


def checker_change_review_evidence_summary(
    *,
    path_text: str,
    suite_impact_class: str,
    selected_suites: list[str],
    expected_route_version: str,
    expected_route_registry_version: str,
    blockers: list[dict[str, Any]],
) -> dict[str, Any]:
    summary: dict[str, Any] = {"path": public_binding_path_label(path_text), "kind": "review_checker_change"}
    try:
        evidence_path = ensure_under_root(path_text)
    except ValueError:
        checker_change_guard_add_blocker(
            blockers,
            blocker_code="invalid_checker_change_review_evidence",
            message="checker-change review evidence path must stay under the repository root.",
            suite_impact_class=suite_impact_class,
            selected_suites=selected_suites,
            evidence_path=summary["path"],
            evidence_state="invalid_path",
            recommended_resolution="Supply repository-local review-checker-change evidence.",
        )
        summary["state"] = "invalid_path"
        return summary

    summary["path"] = public_relative_path(evidence_path)
    if not evidence_path.is_file():
        checker_change_guard_add_blocker(
            blockers,
            blocker_code="missing_checker_change_review_evidence",
            message="required checker-change review evidence is missing.",
            suite_impact_class=suite_impact_class,
            selected_suites=selected_suites,
            evidence_path=summary["path"],
            evidence_state="missing",
            recommended_resolution="Run review-checker-change and provide its current JSON output before accepting the selected suite impact.",
        )
        summary["state"] = "missing"
        return summary

    summary["sha256"] = file_sha256(evidence_path)
    try:
        record = load_json(evidence_path)
    except ValueError as exc:
        checker_change_guard_add_blocker(
            blockers,
            blocker_code="missing_checker_change_review_evidence",
            message="checker-change review evidence is not parseable JSON.",
            suite_impact_class=suite_impact_class,
            selected_suites=selected_suites,
            evidence_path=summary["path"],
            evidence_state="parse_failed",
            recommended_resolution=f"Regenerate the review-checker-change output as parseable JSON: {exc}",
        )
        summary["state"] = "parse_failed"
        return summary

    if not isinstance(record, dict):
        checker_change_guard_add_blocker(
            blockers,
            blocker_code="missing_checker_change_review_evidence",
            message="checker-change review evidence root is not a JSON object.",
            suite_impact_class=suite_impact_class,
            selected_suites=selected_suites,
            evidence_path=summary["path"],
            evidence_state=type(record).__name__,
            recommended_resolution="Regenerate the review-checker-change output as a structured JSON object.",
        )
        summary["state"] = "malformed"
        return summary

    command = str(record.get("command") or "")
    decision = str(record.get("decision") or "")
    schema_version = str(record.get("schema_version") or "")
    checker_blockers = record.get("checker_change_blockers", [])
    checker_blocker_count = len(checker_blockers) if isinstance(checker_blockers, list) else 0
    summary.update(
        {
            "command": command,
            "decision": decision,
            "schema_version": schema_version,
            "checker_change_blocker_count": checker_blocker_count,
        }
    )
    if command != "review-checker-change" or schema_version != REVIEW_CHECKER_CHANGE_RESULT_SCHEMA:
        checker_change_guard_add_blocker(
            blockers,
            blocker_code="invalid_checker_change_review_evidence",
            message="checker-change suite guard requires current review-checker-change output.",
            suite_impact_class=suite_impact_class,
            selected_suites=selected_suites,
            evidence_path=summary["path"],
            evidence_state="invalid_review_shape",
            recommended_resolution="Provide a review-checker-change output with the current review result schema.",
        )
    if decision != "pass" or checker_blocker_count:
        checker_change_guard_add_blocker(
            blockers,
            blocker_code="checker_change_review_not_passed",
            message="checker-change review evidence did not pass cleanly.",
            suite_impact_class=suite_impact_class,
            selected_suites=selected_suites,
            evidence_path=summary["path"],
            evidence_state=decision or "missing_decision",
            recommended_resolution="Repair the checker-change blockers and rerun review-checker-change before accepting this suite impact.",
        )

    stale_blockers, checked_count = inspect_stale_evidence_record(
        record=record,
        record_path=evidence_path,
        expected_route_version=expected_route_version,
        expected_route_registry_version=expected_route_registry_version,
    )
    summary["checked_binding_count"] = checked_count
    summary["stale_blocker_codes"] = sorted({str(item.get("blocker_code") or "") for item in stale_blockers})
    summary["state"] = "stale_or_missing" if stale_blockers else "fresh"
    if stale_blockers:
        checker_change_guard_add_blocker(
            blockers,
            blocker_code="stale_checker_change_review_evidence",
            message="checker-change review evidence is stale or unverifiable.",
            suite_impact_class=suite_impact_class,
            selected_suites=selected_suites,
            evidence_path=summary["path"],
            evidence_state="stale_or_missing",
            recommended_resolution="Refresh or regenerate the review-checker-change evidence before downstream pass claims.",
        )
    return summary


def checker_change_suite_guard_state(
    blockers: list[dict[str, Any]],
    review_evidence: list[dict[str, Any]],
) -> str:
    codes = {str(item.get("blocker_code") or "") for item in blockers}
    if "invalid_checker_suite_selection" in codes:
        return "invalid_selection"
    if "inconsistent_checker_suite_impact" in codes:
        return "inconsistent_selection"
    if any(code.startswith("invalid_checker_change") for code in codes):
        return "missing"
    if any(code.startswith("missing_checker_change") or code == "empty_checker_suite_selection" for code in codes):
        return "missing"
    if "checker_change_review_not_passed" in codes:
        return "stale_or_missing"
    if "stale_checker_change_review_evidence" in codes:
        return "stale_or_missing"
    if review_evidence:
        return "fresh"
    return "not_required"


def build_checker_change_suite_guard(
    *,
    command_name: str,
    target_path: str,
    review_paths: list[str],
    selected_suites: list[str],
    suite_impact_class: str,
    required: bool,
    expected_route_version: str = DETECT_STALE_EXPECTED_ROUTE_VERSION,
    expected_route_registry_version: str = ROUTE_TASK_REGISTRY_VERSION,
) -> dict[str, Any]:
    review_paths = checker_change_suite_guard_values(review_paths)
    selected_suites = checker_change_suite_guard_values(selected_suites)
    suite_impact_class = (suite_impact_class or "").strip() or ("checker_change" if required or review_paths or selected_suites else "none")
    blockers: list[dict[str, Any]] = []
    guard_applies = checker_change_suite_guard_enabled(
        review_paths=review_paths,
        selected_suites=selected_suites,
        suite_impact_class=suite_impact_class,
        required=required,
    )
    if suite_impact_class not in CHECKER_CHANGE_SUITE_IMPACT_CLASSES:
        checker_change_guard_add_blocker(
            blockers,
            blocker_code="invalid_checker_suite_selection",
            message="checker-change suite impact class is not supported.",
            suite_impact_class=suite_impact_class,
            selected_suites=selected_suites,
            evidence_state="invalid_selection",
            recommended_resolution="Use one of: checker_change, suite_change, checker_and_suite_change, none.",
        )
    if guard_applies and suite_impact_class == "none":
        checker_change_guard_add_blocker(
            blockers,
            blocker_code="inconsistent_checker_suite_impact",
            message="checker-change guard inputs were supplied while suite impact is none.",
            suite_impact_class=suite_impact_class,
            selected_suites=selected_suites,
            evidence_state="inconsistent_selection",
            recommended_resolution="Remove guard inputs for no-impact work or select the matching checker/suite impact class.",
        )
    if guard_applies and suite_impact_class != "none" and not selected_suites:
        checker_change_guard_add_blocker(
            blockers,
            blocker_code="empty_checker_suite_selection",
            message="checker-change suite guard requires at least one selected checker or suite surface.",
            suite_impact_class=suite_impact_class,
            selected_suites=selected_suites,
            evidence_state="missing",
            recommended_resolution="Provide --checker-suite for every checker or suite surface affected by the change.",
        )
    invalid_suites = [item for item in selected_suites if not MARKER_NAME_RE.match(item)]
    if invalid_suites:
        checker_change_guard_add_blocker(
            blockers,
            blocker_code="invalid_checker_suite_selection",
            message="checker-change suite selection contains unsupported identifiers.",
            suite_impact_class=suite_impact_class,
            selected_suites=selected_suites,
            evidence_state="invalid_selection",
            recommended_resolution="Use simple checker or suite identifiers made from letters, numbers, dots, underscores, or hyphens.",
        )

    review_evidence: list[dict[str, Any]] = []
    if guard_applies and suite_impact_class != "none" and not review_paths:
        checker_change_guard_add_blocker(
            blockers,
            blocker_code="missing_checker_change_review_evidence",
            message="selected checker/suite impact requires checker-change review evidence.",
            suite_impact_class=suite_impact_class,
            selected_suites=selected_suites,
            evidence_state="missing",
            recommended_resolution="Run review-checker-change and provide its current JSON output before accepting the selected suite impact.",
        )
    for path_text in review_paths:
        review_evidence.append(
            checker_change_review_evidence_summary(
                path_text=path_text,
                suite_impact_class=suite_impact_class,
                selected_suites=selected_suites,
                expected_route_version=expected_route_version,
                expected_route_registry_version=expected_route_registry_version,
                blockers=blockers,
            )
        )
    state = checker_change_suite_guard_state(blockers, review_evidence)
    return {
        "schema_version": CHECKER_CHANGE_SUITE_GUARD_SCHEMA,
        "command": command_name,
        "target_path": target_path,
        "required": guard_applies,
        "suite_impact_class": suite_impact_class,
        "selected_suites": selected_suites,
        "states_supported": sorted(CHECKER_CHANGE_SUITE_GUARD_STATES),
        "state": state,
        "current_evidence_can_pass": state in {"not_required", "fresh"} and not blockers,
        "review_evidence": review_evidence,
        "blockers": blockers,
    }


def checker_change_suite_guard_evidence_rows(guard: dict[str, Any]) -> list[dict[str, Any]]:
    if not guard.get("required"):
        return []
    rows = [
        {
            "evidence_id": "checker-change-suite-guard",
            "kind": "checker_change_suite_guard",
            "fresh": bool(guard.get("current_evidence_can_pass")),
            "summary": (
                f"state={guard.get('state')} impact={guard.get('suite_impact_class')} "
                f"selected_suites={len(guard.get('selected_suites', []))} blockers={len(guard.get('blockers', []))}."
            ),
            "source_path": str(guard.get("target_path") or ""),
            "state": str(guard.get("state") or ""),
            "selected_suites": guard.get("selected_suites", []),
        }
    ]
    for index, item in enumerate(guard.get("review_evidence", [])):
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "evidence_id": f"checker-change-review:{index + 1}",
                "kind": "review_checker_change",
                "fresh": item.get("state") == "fresh",
                "summary": f"review-checker-change evidence state={item.get('state')} decision={item.get('decision', '')}.",
                "source_path": str(item.get("path") or ""),
                "status": str(item.get("state") or ""),
                "reported_decision": str(item.get("decision") or ""),
            }
        )
    return rows


def attach_checker_change_suite_guard(payload: dict[str, Any], blockers: list[str], guard: dict[str, Any]) -> None:
    if not guard.get("required"):
        return
    guard_blockers = [item for item in guard.get("blockers", []) if isinstance(item, dict)]
    payload["checker_change_suite_guard"] = guard
    payload["checker_change_suite_guard_blockers"] = guard_blockers
    payload.setdefault("checks", []).append(
        {
            "check_id": f"{payload.get('command', 'skillguard')}:checker-change-suite-guard",
            "name": "Checker-change suite guard",
            "required": True,
            "status": "pass" if guard.get("current_evidence_can_pass") else "block",
            "summary": (
                "Evaluated current checker-change review evidence, selected checker/suite surfaces, "
                "and downstream pass eligibility without metadata renewal."
            ),
        }
    )
    payload.setdefault("evidence", []).extend(checker_change_suite_guard_evidence_rows(guard))
    if guard_blockers:
        blockers.extend(str(item.get("message") or item.get("blocker_code") or "checker-change suite guard blocked") for item in guard_blockers)


def add_checker_change_suite_guard_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--checker-change-review", action="append", default=[], help="Current review-checker-change JSON output required for checker/suite-impact work. Repeatable.")
    parser.add_argument("--checker-suite", action="append", default=[], help="Changed checker or suite surface selected for guard evaluation. Repeatable.")
    parser.add_argument("--checker-suite-impact", default="", help="Checker/suite impact class: checker_change, suite_change, checker_and_suite_change, or none.")
    parser.add_argument("--checker-suite-required", action="store_true", help="Require checker-change suite guard evidence even when no guard path was supplied.")


def checker_command_required_checks(command_name: str) -> list[str]:
    required_checks = {
        "commands": ["commands:dispatch-table"],
        "route-task": ["route-task:input-shape", "route-task:registry-match", "route-task:conflict-blockers"],
        "fixture-test": ["fixture-test:manifest-load", "fixture-test:case-execution", "fixture-test:expected-outcomes"],
        "detect-stale-evidence": [
            "detect-stale-evidence:input-artifacts",
            "detect-stale-evidence:freshness-bindings",
            "detect-stale-evidence:no-mutation",
        ],
        "review-checker-change": [
            "review-checker-change:baseline-metadata",
            "review-checker-change:command-bindings",
            "review-checker-change:route-bindings",
            "review-checker-change:evidence-freshness",
            "review-checker-change:public-boundary",
            "review-checker-change:no-mutation",
        ],
        "check-maintenance-record": [
            "check-maintenance-record:input-json",
            "check-maintenance-record:schema",
            "check-maintenance-record:current-shape",
        ],
        "self-check": [
            "self-check:required-files",
            "self-check:json-parse",
            "self-check:public-boundary",
            "self-check:policy-artifacts",
            "self-check:public-safety",
        ],
    }
    return list(required_checks.get(command_name, []))


def checker_command_output_schema(command_name: str) -> str:
    if command_name == "build-current-portfolio-registry":
        return "skillguard.portfolio_registry.v2"
    if command_name == "review-checker-change":
        return REVIEW_CHECKER_CHANGE_RESULT_SCHEMA
    if command_name == "check-maintenance-record":
        return MAINTENANCE_RECORD_RESULT_SCHEMA
    return "skillguard.cli_result.v1"


def current_checker_command_surface() -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "dispatch_function": f"checker_engine.{handler.__name__}",
            "summary": COMMAND_SUMMARIES[name],
            "required_checks": checker_command_required_checks(name),
            "output_schema": checker_command_output_schema(name),
        }
        for name, handler in COMMANDS.items()
    ]


def review_baseline_command_surface(baseline: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    entries = baseline.get("command_surface") or baseline.get("commands")
    problems: list[str] = []
    normalized: list[dict[str, Any]] = []
    if isinstance(entries, list):
        for index, item in enumerate(entries):
            if isinstance(item, str):
                normalized.append({"name": item})
                continue
            if not isinstance(item, dict):
                problems.append(f"command_surface[{index}] must be a command object or command name")
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                problems.append(f"command_surface[{index}] is missing name")
                continue
            normalized.append(
                {
                    "name": name,
                    "dispatch_function": str(item.get("dispatch_function") or ""),
                    "summary": str(item.get("summary") or ""),
                    "required_checks": sorted(set(review_string_list(item.get("required_checks")))),
                    "output_schema": str(item.get("output_schema") or checker_command_output_schema(name)),
                }
            )
    elif isinstance(baseline.get("command_names"), list):
        for name in review_string_list(baseline.get("command_names")):
            normalized.append(
                {
                    "name": name,
                    "dispatch_function": "",
                    "summary": "",
                    "required_checks": [],
                    "output_schema": checker_command_output_schema(name),
                }
            )
    else:
        problems.append("baseline must include command_surface or command_names")
    return normalized, problems


def review_baseline_route_entries(baseline: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    entries = baseline.get("route_registry") or baseline.get("current_route_registry")
    if not isinstance(entries, list):
        return [], ["baseline must include route_registry or current_route_registry"]
    normalized: list[dict[str, Any]] = []
    problems: list[str] = []
    for index, item in enumerate(entries):
        if not isinstance(item, dict):
            problems.append(f"route_registry[{index}] must be an object")
            continue
        route_id = str(item.get("route_id") or "").strip()
        if not route_id:
            problems.append(f"route_registry[{index}] is missing route_id")
            continue
        normalized.append(
            {
                "route_id": route_id,
                "route_node_id": str(item.get("route_node_id") or ""),
                "command_family": str(item.get("command_family") or ""),
                "responsibility": str(item.get("responsibility") or ""),
                "status": str(item.get("status") or "current"),
            }
        )
    return normalized, problems


def review_baseline_fixture_entries(baseline: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    entries = baseline.get("fixture_manifests", [])
    if entries in (None, ""):
        return [], []
    if not isinstance(entries, list):
        return [], ["fixture_manifests must be a list when provided"]
    normalized: list[dict[str, Any]] = []
    problems: list[str] = []
    for index, item in enumerate(entries):
        if not isinstance(item, dict):
            problems.append(f"fixture_manifests[{index}] must be an object")
            continue
        path = str(item.get("path") or item.get("source_path") or "").strip()
        if not path:
            problems.append(f"fixture_manifests[{index}] is missing path")
            continue
        normalized.append(
            {
                "path": path,
                "sha256": str(item.get("sha256") or ""),
                "fixture_ids": sorted(set(review_string_list(item.get("fixture_ids")))),
            }
        )
    return normalized, problems


def review_baseline_evidence_entries(baseline: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    entries = baseline.get("evidence_records", [])
    if entries in (None, ""):
        return [], []
    if not isinstance(entries, list):
        return [], ["evidence_records must be a list when provided"]
    normalized: list[dict[str, Any]] = []
    problems: list[str] = []
    for index, item in enumerate(entries):
        if not isinstance(item, dict):
            problems.append(f"evidence_records[{index}] must be an object")
            continue
        path = str(item.get("path") or item.get("source_path") or "").strip()
        if not path:
            problems.append(f"evidence_records[{index}] is missing path")
            continue
        normalized.append({"path": path, "sha256": str(item.get("sha256") or "")})
    return normalized, problems


def review_fixture_manifest_summary(path: Path) -> dict[str, Any]:
    data = load_json(path)
    fixtures = data.get("fixtures", []) if isinstance(data, dict) else []
    fixture_ids: list[str] = []
    target_commands: list[str] = []
    expected_decisions: list[str] = []
    if isinstance(fixtures, list):
        for index, fixture in enumerate(fixtures):
            if isinstance(fixture, dict):
                fixture_ids.append(str(fixture.get("fixture_id") or f"fixture-{index}"))
                target_commands.extend(review_string_list(fixture.get("target_command")))
                expected_decisions.extend(review_string_list(fixture.get("expected_decision")))
            else:
                fixture_ids.append(str(fixture))
    return {
        "path": public_relative_path(path),
        "sha256": file_sha256(path),
        "fixture_ids": sorted(set(fixture_ids)),
        "target_commands": sorted(set(target_commands)),
        "expected_decisions": sorted(set(expected_decisions)),
        "schema_version": str(data.get("schema_version") or "") if isinstance(data, dict) else "",
    }


def review_public_paths(target: Path) -> list[Path]:
    candidates = [
        repository_root() / "README.md",
        repository_root() / "AGENTS.md",
        target / "SKILL.md",
        repository_root() / "references" / "06-evidence-freshness-and-closure-boundaries.md",
        repository_root() / "references" / "08-checker-change-fixture-policy.md",
        repository_root() / "references" / "09-skillguard-self-check.md",
        repository_root() / "examples" / "README.md",
    ]
    seen: set[Path] = set()
    paths: list[Path] = []
    for path in candidates:
        resolved = path.resolve()
        if resolved not in seen and resolved.is_file():
            seen.add(resolved)
            paths.append(resolved)
    return paths


def review_path_snapshot(paths: list[Path]) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for path in paths:
        if path.is_file():
            snapshot[public_relative_path(path)] = file_sha256(path)
    return snapshot


def add_checker_change_blocker(
    blockers: list[str],
    structured_blockers: list[dict[str, Any]],
    *,
    blocker_code: str,
    changed_checker: str,
    old_binding: dict[str, Any],
    new_binding: dict[str, Any],
    impact_class: str,
    affected_evidence_kinds: list[str],
    required_revalidation: str,
    repair_action: str,
) -> None:
    message = f"{changed_checker}: {blocker_code} ({impact_class})"
    blockers.append(message)
    structured_blockers.append(
        {
            "blocker_class": "checker_change_review",
            "blocker_code": blocker_code,
            "changed_checker": changed_checker,
            "old_binding": old_binding,
            "new_binding": new_binding,
            "impact_class": impact_class,
            "affected_evidence_kinds": sorted(set(affected_evidence_kinds)),
            "required_revalidation": required_revalidation,
            "recommended_repair_action": repair_action,
        }
    )


def compare_checker_command_surface(
    baseline_commands: list[dict[str, Any]],
    current_commands: list[dict[str, Any]],
    blockers: list[str],
    structured_blockers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    safe_additions: list[dict[str, Any]] = []
    baseline_by_name = {item["name"]: item for item in baseline_commands}
    current_by_name = {item["name"]: item for item in current_commands}
    current_by_dispatch: dict[str, list[dict[str, Any]]] = {}
    for item in current_commands:
        dispatch = str(item.get("dispatch_function") or "")
        if dispatch:
            current_by_dispatch.setdefault(dispatch, []).append(item)

    for name, baseline in baseline_by_name.items():
        current = current_by_name.get(name)
        if current is None:
            dispatch = str(baseline.get("dispatch_function") or "")
            renamed = current_by_dispatch.get(dispatch, []) if dispatch else []
            if renamed:
                add_checker_change_blocker(
                    blockers,
                    structured_blockers,
                    blocker_code="checker_command_renamed",
                    changed_checker=name,
                    old_binding={"name": name, "dispatch_function": dispatch},
                    new_binding={"name": renamed[0]["name"], "dispatch_function": dispatch},
                    impact_class="renamed",
                    affected_evidence_kinds=["command_surface", "routing", "fixture_output"],
                    required_revalidation="Rerun command dispatch, route-task, fixture-test, self-check, and stale-evidence checks.",
                    repair_action="Update the baseline and public docs only after revalidating all affected evidence with the current command name.",
                )
            else:
                add_checker_change_blocker(
                    blockers,
                    structured_blockers,
                    blocker_code="checker_command_removed",
                    changed_checker=name,
                    old_binding={"name": name, "dispatch_function": dispatch},
                    new_binding={"present": False},
                    impact_class="deleted",
                    affected_evidence_kinds=["command_surface", "routing", "fixture_output"],
                    required_revalidation="Repair or replace evidence that depended on the removed checker before accepting the change.",
                    repair_action="Restore the checker command or update route and fixture metadata with fresh evidence.",
                )
            continue

        baseline_dispatch = str(baseline.get("dispatch_function") or "")
        current_dispatch = str(current.get("dispatch_function") or "")
        if baseline_dispatch and baseline_dispatch != current_dispatch:
            add_checker_change_blocker(
                blockers,
                structured_blockers,
                blocker_code="checker_dispatch_changed",
                changed_checker=name,
                old_binding={"dispatch_function": baseline_dispatch},
                new_binding={"dispatch_function": current_dispatch},
                impact_class="behavior_changed",
                affected_evidence_kinds=["command_surface", "checker_output"],
                required_revalidation="Rerun the changed checker and all fixture or stale-evidence records that cite it.",
                repair_action="Explain the dispatch change and refresh affected evidence before accepting.",
            )

        missing_checks = sorted(set(review_string_list(baseline.get("required_checks"))) - set(review_string_list(current.get("required_checks"))))
        if missing_checks:
            add_checker_change_blocker(
                blockers,
                structured_blockers,
                blocker_code="checker_required_check_removed",
                changed_checker=name,
                old_binding={"required_checks": sorted(review_string_list(baseline.get("required_checks")))},
                new_binding={"required_checks": sorted(review_string_list(current.get("required_checks")))},
                impact_class="weakened",
                affected_evidence_kinds=["checker_output", "fixture_output", "public_boundary"],
                required_revalidation="Restore the missing hard checks or rerun reviewer acceptance with explicit weakened-check approval.",
                repair_action="Do not accept the checker change until the removed checks are restored or replaced with current evidence.",
            )

        baseline_schema = str(baseline.get("output_schema") or "")
        current_schema = str(current.get("output_schema") or "")
        if baseline_schema and baseline_schema != current_schema:
            add_checker_change_blocker(
                blockers,
                structured_blockers,
                blocker_code="checker_output_schema_changed",
                changed_checker=name,
                old_binding={"output_schema": baseline_schema},
                new_binding={"output_schema": current_schema},
                impact_class="output_schema_changed",
                affected_evidence_kinds=["checker_output", "stale_evidence", "fixture_output"],
                required_revalidation="Regenerate consumers and evidence records directly from the current checker output schema.",
                repair_action="Replace non-current checker outputs; do not admit them through a compatibility path.",
            )

    for name in sorted(set(current_by_name) - set(baseline_by_name)):
        safe_additions.append(
            {
                "change_class": "additive_command",
                "checker": name,
                "addition_reason": "Current command is present in dispatch but absent from the baseline; no baseline checker was removed or weakened.",
            }
        )
    return safe_additions


def compare_checker_route_registry(
    baseline_routes: list[dict[str, Any]],
    current_routes: list[dict[str, Any]],
    blockers: list[str],
    structured_blockers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    safe_additions: list[dict[str, Any]] = []
    baseline_by_id = {item["route_id"]: item for item in baseline_routes}
    current_by_id = {item["route_id"]: item for item in current_routes}
    for route_id, baseline in baseline_by_id.items():
        current = current_by_id.get(route_id)
        if current is None:
            add_checker_change_blocker(
                blockers,
                structured_blockers,
                blocker_code="route_binding_removed",
                changed_checker=str(baseline.get("command_family") or route_id),
                old_binding={"route_id": route_id},
                new_binding={"present": False},
                impact_class="deleted",
                affected_evidence_kinds=["routing", "command_surface"],
                required_revalidation="Rerun route-task and all route-bound checker evidence before accepting the change.",
                repair_action="Restore the route binding or replace the baseline with fresh current route-task evidence.",
            )
            continue
        changed_fields = [
            field
            for field in ("route_node_id", "command_family", "responsibility", "status")
            if str(baseline.get(field) or "") and str(baseline.get(field) or "") != str(current.get(field) or "")
        ]
        if changed_fields:
            add_checker_change_blocker(
                blockers,
                structured_blockers,
                blocker_code="route_binding_changed",
                changed_checker=str(baseline.get("command_family") or route_id),
                old_binding={field: baseline.get(field) for field in changed_fields},
                new_binding={field: current.get(field) for field in changed_fields},
                impact_class="behavior_changed",
                affected_evidence_kinds=["routing", "command_surface"],
                required_revalidation="Rerun route-task conflict fixtures and affected command evidence before accepting.",
                repair_action="Document and refresh route metadata after the behavior change is validated.",
            )
    for route_id in sorted(set(current_by_id) - set(baseline_by_id)):
        safe_additions.append(
            {
                "change_class": "additive_route",
                "route_id": route_id,
                "checker": current_by_id[route_id].get("command_family"),
                "addition_reason": "Current route is additive relative to the baseline and did not remove a recorded route binding.",
            }
        )
    return safe_additions


def review_checker_change(argv: list[str]) -> int:
    parser = JsonArgumentParser(
        prog="skillguard.py review-checker-change",
        description="Review current checker bindings against an approved public-safe checker-change baseline.",
    )
    parser.add_argument("--baseline", default="", help="Approved checker-change baseline JSON under the repository root.")
    parser.add_argument("--target", default=".agents/skills/skillguard", help="Target skill root used for public-boundary scans.")
    parser.add_argument("--evidence", action="append", default=[], help="Current evidence-bearing JSON artifact to freshness-check. Repeatable.")
    parser.add_argument("--fixture-manifest", action="append", default=[], help="Current fixture manifest to compare with baseline expectations. Repeatable.")
    parser.add_argument("--expected-route-version", default=DETECT_STALE_EXPECTED_ROUTE_VERSION, help="Current route version expected by freshness checks.")
    parser.add_argument(
        "--expected-route-registry-version",
        default=ROUTE_TASK_REGISTRY_VERSION,
        help="Current route-task registry version expected by freshness checks.",
    )
    parser.add_argument("--output", default="-", help="Output report path under the skill root, or '-' for stdout.")
    args = parser.parse_args(argv)

    payload = base_result("review-checker-change")
    payload["schema_version"] = REVIEW_CHECKER_CHANGE_RESULT_SCHEMA
    payload["expected_route_version"] = str(args.expected_route_version)
    payload["expected_route_registry_version"] = str(args.expected_route_registry_version)
    payload["claim_boundary"] = (
        "This review-checker-change result compares approved public checker-change metadata with the current local dispatch, "
        "route registry, supplied fixture manifests, supplied evidence records, and public-boundary scans. It is read-only for "
        "input artifacts and does not rewrite checker baselines, refresh evidence, inspect sealed FlowPilot packet bodies, expose "
        "sibling role text, make closure decisions, prove release readiness, or validate future AI behavior."
    )

    blockers: list[str] = []
    structured_blockers: list[dict[str, Any]] = []
    baseline: dict[str, Any] = {}
    baseline_path: Path | None = None
    baseline_sha = ""
    watch_paths: list[Path] = []

    try:
        target = resolve_target_argument(args.target)
        payload["target_path"] = public_relative_path(target)
    except ValueError:
        add_checker_change_blocker(
            blockers,
            structured_blockers,
            blocker_code="invalid_target_path",
            changed_checker="review-checker-change",
            old_binding={"path_boundary": "repository-local target"},
            new_binding={"target": public_binding_path_label(args.target)},
            impact_class="public_boundary",
            affected_evidence_kinds=["public_boundary"],
            required_revalidation="Supply a repository-local target path before reviewing checker changes.",
            repair_action="Use a target path under the repository root.",
        )
        target = repository_root() / ".agents" / "skills" / "skillguard"

    if not args.baseline:
        add_checker_change_blocker(
            blockers,
            structured_blockers,
            blocker_code="missing_baseline_metadata",
            changed_checker="review-checker-change",
            old_binding={"baseline": "required"},
            new_binding={"baseline": "missing"},
            impact_class="missing_metadata",
            affected_evidence_kinds=["checker_baseline"],
            required_revalidation="Provide the approved checker-change baseline before accepting a checker change.",
            repair_action="Create or restore a public-safe checker-change baseline and rerun this review.",
        )
    else:
        try:
            baseline_path = ensure_under_root(args.baseline)
            watch_paths.append(baseline_path)
            baseline_sha = file_sha256(baseline_path) if baseline_path.is_file() else ""
            loaded = load_json(baseline_path)
            if not isinstance(loaded, dict):
                raise ValueError("baseline JSON root must be an object")
            baseline = loaded
        except (ValueError, OSError) as exc:
            add_checker_change_blocker(
                blockers,
                structured_blockers,
                blocker_code="missing_baseline_metadata",
                changed_checker="review-checker-change",
                old_binding={"baseline": public_binding_path_label(args.baseline)},
                new_binding={"parse": "failed"},
                impact_class="missing_metadata",
                affected_evidence_kinds=["checker_baseline"],
                required_revalidation="Repair or restore the approved checker-change baseline before accepting.",
                repair_action=f"Load a parseable repository-local baseline JSON object: {exc}",
            )

    current_commands = current_checker_command_surface()
    current_routes = [public_route_entry(entry) for entry in current_route_entries()]
    baseline_commands: list[dict[str, Any]] = []
    baseline_routes: list[dict[str, Any]] = []
    baseline_fixtures: list[dict[str, Any]] = []
    baseline_evidence: list[dict[str, Any]] = []
    metadata_problems: list[str] = []
    safe_additions: list[dict[str, Any]] = []

    if baseline:
        for field, expected in (
            ("schema_version", REVIEW_CHECKER_CHANGE_BASELINE_SCHEMA),
            ("checker_version", CHECKER_VERSION),
            ("route_version", str(args.expected_route_version)),
            ("route_registry_version", str(args.expected_route_registry_version)),
        ):
            observed = str(baseline.get(field) or "")
            if not observed:
                metadata_problems.append(f"baseline is missing {field}")
            elif field == "schema_version" and observed != expected:
                metadata_problems.append(f"baseline schema_version must be {expected}")
            elif field != "schema_version" and observed != expected:
                add_checker_change_blocker(
                    blockers,
                    structured_blockers,
                    blocker_code=f"stale_{field}",
                    changed_checker="review-checker-change",
                    old_binding={field: observed},
                    new_binding={field: expected},
                    impact_class="stale_metadata",
                    affected_evidence_kinds=["checker_baseline", "routing", "command_surface"],
                    required_revalidation="Refresh the checker-change baseline after current route and checker metadata are validated.",
                    repair_action="Regenerate the baseline metadata from current local command and route evidence.",
                )

        baseline_commands, command_problems = review_baseline_command_surface(baseline)
        baseline_routes, route_problems = review_baseline_route_entries(baseline)
        baseline_fixtures, fixture_problems = review_baseline_fixture_entries(baseline)
        baseline_evidence, evidence_problems = review_baseline_evidence_entries(baseline)
        metadata_problems.extend(command_problems)
        metadata_problems.extend(route_problems)
        metadata_problems.extend(fixture_problems)
        metadata_problems.extend(evidence_problems)
        for problem in metadata_problems:
            add_checker_change_blocker(
                blockers,
                structured_blockers,
                blocker_code="missing_baseline_metadata",
                changed_checker="review-checker-change",
                old_binding={"baseline_field": problem},
                new_binding={"baseline": "unusable"},
                impact_class="missing_metadata",
                affected_evidence_kinds=["checker_baseline"],
                required_revalidation="Provide complete baseline command, route, fixture, and evidence metadata before accepting.",
                repair_action="Repair the baseline metadata and rerun review-checker-change.",
            )

    if baseline and not metadata_problems:
        safe_additions.extend(compare_checker_command_surface(baseline_commands, current_commands, blockers, structured_blockers))
        safe_additions.extend(compare_checker_route_registry(baseline_routes, current_routes, blockers, structured_blockers))

    fixture_reviews: list[dict[str, Any]] = []
    fixture_paths: dict[str, Path] = {}
    for value in args.fixture_manifest:
        try:
            fixture_path = ensure_under_root(value)
            fixture_paths[public_relative_path(fixture_path)] = fixture_path
            watch_paths.append(fixture_path)
        except ValueError:
            add_checker_change_blocker(
                blockers,
                structured_blockers,
                blocker_code="fixture_expectation_changed",
                changed_checker="fixture-manifest",
                old_binding={"path_boundary": "repository-local fixture manifest"},
                new_binding={"path": public_binding_path_label(value)},
                impact_class="public_boundary",
                affected_evidence_kinds=["fixture_manifest"],
                required_revalidation="Use repository-local fixture manifests only.",
                repair_action="Move the fixture manifest under the repository root and rerun.",
            )
    for baseline_fixture in baseline_fixtures:
        try:
            fixture_path = ensure_under_root(baseline_fixture["path"])
            fixture_paths.setdefault(public_relative_path(fixture_path), fixture_path)
            watch_paths.append(fixture_path)
        except ValueError:
            add_checker_change_blocker(
                blockers,
                structured_blockers,
                blocker_code="fixture_expectation_changed",
                changed_checker="fixture-manifest",
                old_binding={"path": baseline_fixture["path"]},
                new_binding={"path_boundary": "outside repository"},
                impact_class="public_boundary",
                affected_evidence_kinds=["fixture_manifest"],
                required_revalidation="Repair baseline fixture manifest paths before accepting.",
                repair_action="Use repository-local fixture manifest paths in the baseline.",
            )

    for relative, fixture_path in sorted(fixture_paths.items()):
        if not fixture_path.is_file():
            add_checker_change_blocker(
                blockers,
                structured_blockers,
                blocker_code="fixture_manifest_missing",
                changed_checker="fixture-manifest",
                old_binding={"path": relative, "exists": True},
                new_binding={"path": relative, "exists": False},
                impact_class="missing_metadata",
                affected_evidence_kinds=["fixture_manifest"],
                required_revalidation="Restore the fixture manifest before accepting checker changes.",
                repair_action="Restore or regenerate the fixture manifest with current fixture expectations.",
            )
            continue
        summary = review_fixture_manifest_summary(fixture_path)
        matching_baselines = [item for item in baseline_fixtures if public_binding_path_label(item["path"]) == relative or item["path"] == relative]
        baseline_fixture = matching_baselines[0] if matching_baselines else {}
        if baseline_fixture.get("sha256") and baseline_fixture["sha256"] != summary["sha256"]:
            add_checker_change_blocker(
                blockers,
                structured_blockers,
                blocker_code="fixture_expectation_changed",
                changed_checker="fixture-manifest",
                old_binding={"path": relative, "sha256": baseline_fixture["sha256"]},
                new_binding={"path": relative, "sha256": summary["sha256"]},
                impact_class="fixture_expectation_changed",
                affected_evidence_kinds=["fixture_manifest", "fixture_output"],
                required_revalidation="Rerun fixture-test and stale-evidence checks after fixture expectation changes.",
                repair_action="Update the baseline only after fixture changes have fresh evidence.",
            )
        if baseline_fixture.get("fixture_ids") and sorted(baseline_fixture["fixture_ids"]) != summary["fixture_ids"]:
            add_checker_change_blocker(
                blockers,
                structured_blockers,
                blocker_code="fixture_expectation_changed",
                changed_checker="fixture-manifest",
                old_binding={"path": relative, "fixture_ids": baseline_fixture["fixture_ids"]},
                new_binding={"path": relative, "fixture_ids": summary["fixture_ids"]},
                impact_class="fixture_expectation_changed",
                affected_evidence_kinds=["fixture_manifest", "fixture_output"],
                required_revalidation="Rerun fixture-test after fixture case identity changes.",
                repair_action="Preserve fixture identity or regenerate fixture evidence before acceptance.",
            )
        fixture_reviews.append({"baseline": baseline_fixture, "current": summary})

    evidence_reviews: list[dict[str, Any]] = []
    evidence_paths: dict[str, Path] = {}
    for value in args.evidence:
        try:
            evidence_path = ensure_under_root(value)
            evidence_paths[public_relative_path(evidence_path)] = evidence_path
            watch_paths.append(evidence_path)
        except ValueError:
            add_checker_change_blocker(
                blockers,
                structured_blockers,
                blocker_code="invalid_evidence_path",
                changed_checker="evidence-record",
                old_binding={"path_boundary": "repository-local evidence artifact"},
                new_binding={"path": public_binding_path_label(value)},
                impact_class="public_boundary",
                affected_evidence_kinds=["stale_evidence"],
                required_revalidation="Use repository-local evidence artifacts only.",
                repair_action="Move evidence under the repository root or omit it from this review.",
            )
    for baseline_record in baseline_evidence:
        try:
            evidence_path = ensure_under_root(baseline_record["path"])
            evidence_paths.setdefault(public_relative_path(evidence_path), evidence_path)
            watch_paths.append(evidence_path)
        except ValueError:
            add_checker_change_blocker(
                blockers,
                structured_blockers,
                blocker_code="invalid_evidence_path",
                changed_checker="evidence-record",
                old_binding={"path": baseline_record["path"]},
                new_binding={"path_boundary": "outside repository"},
                impact_class="public_boundary",
                affected_evidence_kinds=["stale_evidence"],
                required_revalidation="Repair baseline evidence paths before accepting checker changes.",
                repair_action="Use repository-local evidence paths in the baseline.",
            )

    before_snapshot = review_path_snapshot(watch_paths)

    for relative, evidence_path in sorted(evidence_paths.items()):
        if not evidence_path.is_file():
            add_checker_change_blocker(
                blockers,
                structured_blockers,
                blocker_code="missing_evidence_artifact",
                changed_checker="evidence-record",
                old_binding={"path": relative, "exists": True},
                new_binding={"path": relative, "exists": False},
                impact_class="missing_metadata",
                affected_evidence_kinds=["stale_evidence"],
                required_revalidation="Restore the evidence artifact before using it for checker-change acceptance.",
                repair_action="Restore or regenerate the evidence artifact.",
            )
            continue
        try:
            record = load_json(evidence_path)
        except ValueError:
            add_checker_change_blocker(
                blockers,
                structured_blockers,
                blocker_code="missing_evidence_metadata",
                changed_checker="evidence-record",
                old_binding={"path": relative, "json": "valid object"},
                new_binding={"path": relative, "json": "parse_failed"},
                impact_class="missing_metadata",
                affected_evidence_kinds=["stale_evidence"],
                required_revalidation="Regenerate parseable evidence before accepting checker changes.",
                repair_action="Rewrite the evidence artifact using its owning command.",
            )
            continue
        if not isinstance(record, dict):
            add_checker_change_blocker(
                blockers,
                structured_blockers,
                blocker_code="missing_evidence_metadata",
                changed_checker="evidence-record",
                old_binding={"path": relative, "json_root": "object"},
                new_binding={"path": relative, "json_root": type(record).__name__},
                impact_class="missing_metadata",
                affected_evidence_kinds=["stale_evidence"],
                required_revalidation="Regenerate structured evidence before accepting checker changes.",
                repair_action="Rewrite the evidence artifact as a JSON object using its owning command.",
            )
            continue
        record_blockers, checked_count = inspect_stale_evidence_record(
            record=record,
            record_path=evidence_path,
            expected_route_version=str(args.expected_route_version),
            expected_route_registry_version=str(args.expected_route_registry_version),
        )
        matching_baselines = [item for item in baseline_evidence if public_binding_path_label(item["path"]) == relative or item["path"] == relative]
        baseline_record = matching_baselines[0] if matching_baselines else {}
        current_sha = file_sha256(evidence_path)
        if baseline_record.get("sha256") and baseline_record["sha256"] != current_sha:
            add_checker_change_blocker(
                blockers,
                structured_blockers,
                blocker_code="evidence_record_changed_after_baseline",
                changed_checker="evidence-record",
                old_binding={"path": relative, "sha256": baseline_record["sha256"]},
                new_binding={"path": relative, "sha256": current_sha},
                impact_class="stale_metadata",
                affected_evidence_kinds=["stale_evidence"],
                required_revalidation="Rerun freshness checks after evidence changes before accepting checker changes.",
                repair_action="Regenerate the baseline after evidence records have current fingerprints.",
            )
        if record_blockers:
            add_checker_change_blocker(
                blockers,
                structured_blockers,
                blocker_code="stale_evidence_after_checker_change",
                changed_checker=str(record.get("command") or "evidence-record"),
                old_binding={"path": relative, "stale_count": 0},
                new_binding={"path": relative, "stale_count": len(record_blockers)},
                impact_class="stale_evidence",
                affected_evidence_kinds=sorted({str(item.get("binding_kind") or "evidence") for item in record_blockers}),
                required_revalidation="Regenerate stale evidence with its declared owner before using it to accept checker changes.",
                repair_action="Run detect-stale-evidence, then rerun only the exact owning check on current functional inputs.",
            )
        evidence_reviews.append(
            {
                "path": relative,
                "sha256": current_sha,
                "checked_binding_count": checked_count,
                "stale_blocker_codes": sorted({str(item.get("blocker_code") or "") for item in record_blockers}),
            }
        )

    public_findings: list[dict[str, Any]] = []
    unsafe_claim_findings: list[dict[str, Any]] = []
    public_scan_failures: list[str] = []
    public_paths = review_public_paths(target)
    for public_path in public_paths:
        public_findings.extend(public_safety_findings(public_path))
        unsafe_claim_findings.extend(scan_text_for_unsafe_claims(public_path, public_scan_failures))
    unsafe_public_claims = [item for item in unsafe_claim_findings if item.get("decision") == "fail"]
    if public_findings or unsafe_public_claims:
        add_checker_change_blocker(
            blockers,
            structured_blockers,
            blocker_code="public_boundary_leakage",
            changed_checker="public-boundary",
            old_binding={"public_files": "safe"},
            new_binding={"public_safety_findings": len(public_findings), "unsafe_claim_findings": len(unsafe_public_claims)},
            impact_class="public_boundary",
            affected_evidence_kinds=["public_boundary"],
            required_revalidation="Remove private or unsupported public wording before accepting checker changes.",
            repair_action="Repair public files and rerun self-check plus review-checker-change.",
        )

    after_snapshot = review_path_snapshot(watch_paths)
    mutated_inputs = sorted(path for path, before_sha in before_snapshot.items() if after_snapshot.get(path) != before_sha)
    if mutated_inputs:
        add_checker_change_blocker(
            blockers,
            structured_blockers,
            blocker_code="no_mutation_violation",
            changed_checker="review-checker-change",
            old_binding={"input_hashes": "unchanged"},
            new_binding={"mutated_paths": mutated_inputs},
            impact_class="no_mutation_violation",
            affected_evidence_kinds=["checker_baseline", "fixture_manifest", "stale_evidence"],
            required_revalidation="Rerun in read-only mode after restoring input artifacts.",
            repair_action="Do not accept a checker-change review that rewrites baselines, fixtures, or evidence artifacts.",
        )

    baseline_relative = public_relative_path(baseline_path) if baseline_path is not None and baseline_path.exists() else ""
    payload["baseline_binding"] = {
        "path": baseline_relative,
        "sha256": baseline_sha,
        "schema_version": str(baseline.get("schema_version") or ""),
        "checker_version": str(baseline.get("checker_version") or ""),
        "route_version": str(baseline.get("route_version") or ""),
        "route_registry_version": str(baseline.get("route_registry_version") or ""),
        "command_count": len(baseline_commands),
        "route_count": len(baseline_routes),
        "fixture_manifest_count": len(baseline_fixtures),
        "evidence_record_count": len(baseline_evidence),
    }
    inspected_files: list[dict[str, Any]] = []
    for inspected_path in [path for path in [baseline_path, *fixture_paths.values(), *evidence_paths.values()] if path is not None]:
        if inspected_path.is_file():
            inspected_files.append(checked_file(inspected_path, "json"))
    payload["files_inspected"] = inspected_files
    payload["route_version"] = str(args.expected_route_version)
    payload["route_registry_version"] = str(args.expected_route_registry_version)
    payload["command_names"] = list(COMMANDS)
    payload["current_route_registry"] = current_routes
    payload["current_binding"] = {
        "checker_version": CHECKER_VERSION,
        "route_version": str(args.expected_route_version),
        "route_registry_version": str(args.expected_route_registry_version),
        "command_count": len(current_commands),
        "route_count": len(current_routes),
        "public_safety_checks": [finding_id for finding_id, _pattern in PUBLIC_SAFETY_PATTERNS],
        "openspec_status": {"changes_directory_present": current_openspec_changes_present()},
    }
    payload["safe_additions"] = safe_additions
    payload["checker_change_blockers"] = structured_blockers
    payload["fixture_reviews"] = fixture_reviews
    payload["evidence_freshness_reviews"] = evidence_reviews
    payload["public_safety_findings"] = public_findings
    payload["unsafe_claim_findings"] = unsafe_claim_findings
    payload["mutation_check"] = {
        "read_only": not mutated_inputs,
        "watched_input_count": len(before_snapshot),
        "mutated_input_paths": mutated_inputs,
    }
    payload["checks"] = [
        {
            "check_id": "review-checker-change:baseline-metadata",
            "name": "Baseline metadata",
            "required": True,
            "status": "block" if metadata_problems or not baseline else "pass",
            "summary": f"Loaded checker-change baseline with {len(baseline_commands)} command binding(s) and {len(baseline_routes)} route binding(s).",
        },
        {
            "check_id": "review-checker-change:command-bindings",
            "name": "Checker command bindings",
            "required": True,
            "status": "block" if any(item.get("affected_evidence_kinds") and "command_surface" in item.get("affected_evidence_kinds", []) for item in structured_blockers) else "pass",
            "summary": f"Compared baseline command bindings with {len(current_commands)} current dispatch command(s).",
        },
        {
            "check_id": "review-checker-change:route-bindings",
            "name": "Route-task bindings",
            "required": True,
            "status": "block" if any(item.get("affected_evidence_kinds") and "routing" in item.get("affected_evidence_kinds", []) for item in structured_blockers) else "pass",
            "summary": f"Compared baseline route bindings with {len(current_routes)} current route-task binding(s).",
        },
        {
            "check_id": "review-checker-change:evidence-freshness",
            "name": "Evidence freshness",
            "required": True,
            "status": "block" if any(item.get("blocker_code") in {"stale_evidence_after_checker_change", "evidence_record_changed_after_baseline"} for item in structured_blockers) else "pass",
            "summary": f"Checked {len(evidence_reviews)} evidence artifact(s) for current freshness metadata.",
        },
        {
            "check_id": "review-checker-change:fixture-expectations",
            "name": "Fixture expectation bindings",
            "required": True,
            "status": "block" if any(item.get("blocker_code") in {"fixture_expectation_changed", "fixture_manifest_missing"} for item in structured_blockers) else "pass",
            "summary": f"Compared {len(fixture_reviews)} fixture manifest binding(s) against baseline expectations.",
        },
        {
            "check_id": "review-checker-change:public-boundary",
            "name": "Public boundary",
            "required": True,
            "status": "block" if public_findings or unsafe_public_claims else "pass",
            "summary": f"Scanned {len(public_paths)} public file(s) for private identifiers, credentials, and unsupported public claims.",
        },
        {
            "check_id": "review-checker-change:no-mutation",
            "name": "Read-only input behavior",
            "required": True,
            "status": "block" if mutated_inputs else "pass",
            "summary": f"Watched {len(before_snapshot)} input artifact(s) and detected {len(mutated_inputs)} input mutation(s).",
        },
    ]
    payload["evidence"] = [
        {
            "evidence_id": "review-checker-change-baseline",
            "kind": "parser_output",
            "fresh": bool(baseline) and not metadata_problems,
            "summary": f"Loaded baseline metadata from {baseline_relative or '<missing>'}.",
            "source_path": baseline_relative,
        },
        {
            "evidence_id": "review-checker-change-current-bindings",
            "kind": "command_table_check",
            "fresh": True,
            "summary": f"Compared current checker version {CHECKER_VERSION}, route registry {ROUTE_TASK_REGISTRY_VERSION}, and {len(current_commands)} command(s).",
            "source_path": ".agents/skills/skillguard/scripts/checker_engine.py",
        },
        {
            "evidence_id": "review-checker-change-public-boundary",
            "kind": "text_scan",
            "fresh": True,
            "summary": f"Scanned {len(public_paths)} public file(s) for public-safe checker-change reporting.",
            "source_path": "README.md",
        },
    ]
    payload["skipped_checks"] = [
        "review-checker-change does not rewrite checker baselines, refresh stale evidence, rerun target checker commands, inspect sealed FlowPilot packet bodies, or make closure decisions."
    ]
    payload["residual_risk"] = [
        "This command checks explicit checker-change bindings and supplied evidence artifacts; semantic adequacy of a checker change still requires responsible reviewer judgment.",
        "Additive command or route rows are only baseline-diff observations and still require their own direct evidence before supporting broader claims.",
    ]
    payload["blockers"] = blockers
    payload["decision"] = "block" if blockers else "pass"
    attach_maintenance_record(
        payload,
        record_kind="checker_change_review",
        artifact_id=payload.get("target_path") or "review-checker-change",
        route_node_id="review-checker-change",
        checker_name="review-checker-change",
        blockers=structured_blockers,
        owner_action={"action": "review_only", "status": "not_applicable", "safe_addition_count": len(safe_additions)},
        content_seed={"baseline_path": baseline_relative, "evidence_count": len(evidence_reviews), "fixture_count": len(fixture_reviews)},
    )
    return write_and_exit(payload, args.output)


def commands(argv: list[str]) -> int:
    parser = JsonArgumentParser(prog="skillguard.py commands", description="List SkillGuard CLI commands.")
    parser.add_argument("--output", default="-", help="Output path under the skill root, or '-' for stdout.")
    args = parser.parse_args(argv)
    payload = base_result("commands")
    payload["decision"] = "pass"
    payload["commands"] = current_checker_command_surface()
    payload["checks"] = [
        {
            "check_id": "commands:dispatch-table",
            "name": "Dispatch table enumeration",
            "required": True,
            "status": "pass",
            "summary": "Every public command is mapped to a checker-engine function.",
        }
    ]
    attach_maintenance_record(
        payload,
        record_kind="command_surface",
        artifact_id=".agents/skills/skillguard/scripts/checker_engine.py",
        route_node_id="commands",
        checker_name="commands",
        blockers=[],
        owner_action={"action": "not_applicable", "status": "command_surface"},
        content_seed={"command_count": len(COMMANDS)},
    )
    return write_and_exit(payload, args.output)


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


def parse_global_roots_args(parser: JsonArgumentParser) -> None:
    parser.add_argument(
        "--skill-root",
        action="append",
        default=[],
        help=(
            "Explicit author-side maintained skill root. Repeatable. Installed "
            "consumer skill directories are not inferred."
        ),
    )
    parser.add_argument(
        "--codex-home",
        help="Codex home used only to resolve/redact paths; it is not scanned implicitly.",
    )


def scan_global_skills(argv: list[str]) -> int:
    parser = JsonArgumentParser(prog="skillguard.py scan-global-skills", description="Scan explicit author-side skill roots for maintained SKILL.md files.")
    parse_global_roots_args(parser)
    parser.add_argument("--output", default="-", help="Output report path under the skill root, or '-' for stdout.")
    args = parser.parse_args(argv)
    roots, root_blockers = global_skill_roots_from_args(args.skill_root, args.codex_home)
    items, warnings = discover_global_skill_items(roots) if roots else ([], [])
    payload = base_result("scan-global-skills")
    payload["target_path"] = ", ".join(global_public_path(root) for root in roots)
    payload["skill_roots"] = [global_public_path(root) for root in roots]
    payload["skill_items"] = items
    payload["warnings"] = warnings
    payload["blockers"] = root_blockers
    payload["decision"] = "block" if root_blockers else "pass"
    payload["claim_boundary"] = (
        "This scan records only explicit author-side maintained SKILL.md files and adjacent SkillGuard maintenance contracts under the requested roots. "
        "It does not scan or govern ordinary installed consumer skills. "
        "It does not install prompt routing, execute target skills, prove fixture coverage, tests, suite automation, package publication, "
        "code-contract validation, release readiness, or future AI behavior."
    )
    append_check(
        payload,
        "scan-global-skills:roots",
        "Skill roots",
        "block" if root_blockers else "pass",
        "Resolved the requested skill roots before recursive SKILL.md discovery.",
    )
    append_check(
        payload,
        "scan-global-skills:skill-docs",
        "Skill document discovery",
        "pass" if items or root_blockers else "fail",
        f"Discovered {len(items)} SKILL.md file(s) and projected adjacent route documents when present.",
    )
    payload["evidence"] = [
        {
            "evidence_id": "global-skill-scan",
            "kind": "file_inventory",
            "fresh": True,
            "summary": f"Scanned {len(roots)} root(s) and discovered {len(items)} skill item(s).",
            "source_path": payload["target_path"],
        }
    ]
    if not items and not root_blockers:
        payload["failures"] = ["no SKILL.md files were discovered under the supplied roots"]
        payload["decision"] = "fail"
    return write_and_exit(payload, args.output)


def check_runtime_authority(argv: list[str]) -> int:
    parser = JsonArgumentParser(
        prog="skillguard.py check-runtime-authority",
        description="Resolve one target's current or blocked runtime authority.",
    )
    parser.add_argument("--target", required=True, help="Target skill directory.")
    parser.add_argument("--target-root", help="Explicit root for a portable external target check.")
    parser.add_argument(
        "--require-authority",
        choices=["current"],
        help="Optionally require the exact current authority decision.",
    )
    parser.add_argument("--output", default="-", help="Output report path under the skill root, or '-' for stdout.")
    args = parser.parse_args(argv)
    target_root = Path(args.target_root).resolve() if args.target_root else None
    if target_root is not None and not target_root.is_dir():
        raise SkillGuardCliError(
            "check-runtime-authority",
            f"--target-root is missing or not a directory: {args.target_root}",
            "missing_file",
        )
    target = resolve_target_argument(args.target, target_root)
    from skillguard_v2.runtime_authority import resolve_runtime_authority

    authority = resolve_runtime_authority(target)
    required_mismatch = bool(
        args.require_authority and authority.authority != args.require_authority
    )
    payload = base_result(
        "check-runtime-authority",
        public_relative_path(target, target_root),
    )
    authority_payload = authority.to_dict()
    authority_payload["skill_root"] = public_relative_path(target, target_root)
    payload.update(authority_payload)
    payload["required_authority"] = args.require_authority or ""
    payload["failures"] = [
        f"required authority {args.require_authority}, observed {authority.authority}"
    ] if required_mismatch else []
    payload["blockers"] = list(authority.blockers)
    payload["decision"] = (
        "pass" if authority.ok and not required_mismatch else "block" if authority.blockers else "fail"
    )
    payload["checks"] = [
        {
            "check_id": "check-runtime-authority:singular",
            "name": "Singular runtime authority",
            "required": True,
            "status": "pass" if authority.ok else "block",
            "summary": f"Resolved authority={authority.authority}.",
        },
        {
            "check_id": "check-runtime-authority:required",
            "name": "Required authority match",
            "required": bool(args.require_authority),
            "status": "pass" if not required_mismatch else "fail",
            "summary": "Checked the optional exact authority requirement.",
        },
    ]
    return write_and_exit(payload, args.output)


def build_global_registry(argv: list[str]) -> int:
    parser = JsonArgumentParser(prog="skillguard.py build-global-registry", description="Build a private author-side SkillGuard maintenance routing registry.")
    parse_global_roots_args(parser)
    parser.add_argument("--registry-output", "--registry", dest="registry_output", help="Registry JSON output path.")
    parser.add_argument("--output", default="-", help="Output report path under the skill root, or '-' for stdout.")
    args = parser.parse_args(argv)
    roots, root_blockers = global_skill_roots_from_args(args.skill_root, args.codex_home)
    registry = build_global_registry_payload(roots) if roots else {
        "schema_version": GLOBAL_REGISTRY_SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "router_skill_id": GLOBAL_ROUTER_SKILL_ID,
        "scan_roots": [],
        "item_count": 0,
        "current_item_count": 0,
        "items": [],
        "warnings": [],
        "claim_boundary": "No registry was built because no scan roots were available.",
    }
    registry["diagnostic_inventory_hash"] = global_diagnostic_inventory_hash(
        registry
    )
    registry["registry_hash"] = global_registry_hash(registry)
    schema_failures = validate_schema_subset(registry, load_json(schema_path("skillguard_global_registry.schema.json")))
    schema_failures.extend(global_registry_integrity_failures(registry))
    write_path = None
    if args.registry_output and not root_blockers and not schema_failures:
        write_path = global_write_json(args.registry_output, registry)
    payload = base_result("build-global-registry", global_public_path(write_path) if write_path else "")
    payload["registry"] = registry
    payload["registry_path"] = global_public_path(write_path) if write_path else ""
    payload["failures"] = schema_failures
    payload["blockers"] = root_blockers
    payload["decision"] = "block" if root_blockers else "fail" if schema_failures else "pass"
    append_check(
        payload,
        "build-global-registry:schema",
        "Registry schema",
        "fail" if schema_failures else "pass",
        "Built the registry and checked it against the bundled global registry schema.",
    )
    append_check(
        payload,
        "build-global-registry:write",
        "Registry write",
        "pass" if write_path or not args.registry_output else "block" if root_blockers else "fail" if schema_failures else "pass",
        "Wrote the registry only after root and schema checks passed, or returned it without writing when no output path was requested.",
    )
    payload["evidence"] = [
        {
            "evidence_id": "global-registry-json",
            "kind": "generated_registry",
            "fresh": True,
            "summary": f"Registry hash {registry.get('registry_hash')} covers {registry.get('item_count')} skill item(s).",
            "source_path": payload["registry_path"] or "stdout",
        }
    ]
    return write_and_exit(payload, args.output)


def check_global_registry(argv: list[str]) -> int:
    parser = JsonArgumentParser(prog="skillguard.py check-global-registry", description="Check that a global registry is schema-valid and fresh against current skill roots.")
    parser.add_argument("--registry", required=True, help="Registry JSON path.")
    parse_global_roots_args(parser)
    parser.add_argument("--output", default="-", help="Output report path under the skill root, or '-' for stdout.")
    args = parser.parse_args(argv)
    registry_path = expand_global_path(args.registry)
    failures: list[str] = []
    blockers: list[str] = []
    inspected_files: list[dict[str, Any]] = []
    try:
        registry = global_read_json(registry_path)
        inspected_files.append(global_checked_file(registry_path, "json"))
    except FileNotFoundError:
        registry = {}
        blockers.append(f"registry file is missing: {global_public_path(registry_path)}")
    except (ValueError, json.JSONDecodeError) as exc:
        registry = {}
        blockers.append(f"registry JSON could not be loaded: {exc}")
    if isinstance(registry, dict) and registry:
        failures.extend(validate_schema_subset(registry, load_json(schema_path("skillguard_global_registry.schema.json"))))
        failures.extend(global_registry_integrity_failures(registry))
    elif not blockers:
        blockers.append("registry JSON root must be an object")

    roots, root_blockers = registry_roots_for_check(registry if isinstance(registry, dict) else {}, args.skill_root, args.codex_home)
    blockers.extend(root_blockers)
    current_registry: dict[str, Any] = {}
    if roots and not blockers:
        current_registry = build_global_registry_payload(roots)
        if current_registry.get("registry_hash") != registry.get("registry_hash"):
            failures.append("registry hash is stale against current skill root scan")
        if current_registry.get("diagnostic_inventory_hash") != registry.get(
            "diagnostic_inventory_hash"
        ):
            failures.append(
                "registry diagnostic inventory is stale against current skill root scan"
            )
    payload = base_result("check-global-registry", global_public_path(registry_path))
    payload["registry_hash"] = registry.get("registry_hash", "") if isinstance(registry, dict) else ""
    payload["current_registry_hash"] = current_registry.get("registry_hash", "")
    payload["files_inspected"] = inspected_files
    payload["failures"] = failures
    payload["blockers"] = blockers
    payload["decision"] = "block" if blockers else "fail" if failures else "pass"
    append_check(
        payload,
        "check-global-registry:schema",
        "Registry schema",
        "block" if blockers and not registry else "fail" if failures and not current_registry else "pass",
        "Loaded the registry JSON and checked its bundled schema subset.",
    )
    append_check(
        payload,
        "check-global-registry:freshness",
        "Registry freshness",
        "block" if root_blockers else "fail" if current_registry and current_registry.get("registry_hash") != registry.get("registry_hash") else "pass",
        "Rebuilt a current registry projection from the same roots when the roots were re-checkable.",
    )
    payload["evidence"] = [
        {
            "evidence_id": "checked-global-registry",
            "kind": "registry_freshness_check",
            "fresh": not failures and not blockers,
            "summary": f"Compared registry hash {payload['registry_hash']} to current hash {payload['current_registry_hash']}.",
            "source_path": global_public_path(registry_path),
        }
    ]
    return write_and_exit(payload, args.output)


def refresh_global_router(argv: list[str]) -> int:
    parser = JsonArgumentParser(prog="skillguard.py refresh-global-router", description="Scan skills, rebuild registry, render prompt projection, install AGENTS.md, and verify freshness.")
    parse_global_roots_args(parser)
    parser.add_argument("--output-dir", help="Directory for registry/projection artifacts. Defaults to --codex-home/.skillguard/global-router.")
    parser.add_argument("--agents-file", help="AGENTS.md file to update. Defaults to --codex-home/AGENTS.md.")
    parser.add_argument("--dry-run", action="store_true", help="Build artifacts and check projected content without writing AGENTS.md.")
    parser.add_argument("--output", default="-", help="Output report path under the skill root, or '-' for stdout.")
    args = parser.parse_args(argv)
    roots, root_blockers = global_skill_roots_from_args(args.skill_root, args.codex_home)
    codex_home = expand_global_path(args.codex_home) if args.codex_home else Path.home() / ".codex"
    output_dir = (
        expand_global_path(args.output_dir)
        if args.output_dir
        else (codex_home / ".skillguard" / "global-router").resolve()
    )
    registry_path = output_dir / "global_registry.json"
    projection_path = output_dir / "global_prompt_projection.json"
    failures: list[str] = []
    blockers: list[str] = list(root_blockers)
    registry = build_global_registry_payload(roots) if roots else {}
    registry_unchanged = False
    if registry:
        registry, registry_unchanged = _reuse_unchanged_generated_json(
            registry_path, registry
        )
    if registry:
        failures.extend(validate_schema_subset(registry, load_json(schema_path("skillguard_global_registry.schema.json"))))
        failures.extend(global_registry_integrity_failures(registry))
    projection = (
        build_global_prompt_projection_or_block(
            registry, global_public_path(registry_path), blockers
        )
        if registry
        else {}
    )
    projection_unchanged = False
    if projection:
        projection, projection_unchanged = _reuse_unchanged_generated_json(
            projection_path, projection
        )
    if projection:
        failures.extend(validate_schema_subset(projection, load_json(schema_path("skillguard_global_prompt_projection.schema.json"))))
        failures.extend(
            current_global_router.prompt_projection_integrity_failures(
                projection
            )
        )
    agents_file = expand_global_path(args.agents_file) if args.agents_file else (codex_home / "AGENTS.md").resolve()
    install_status = "not-written"
    if not blockers and not failures and registry and projection:
        existing = agents_file.read_text(encoding="utf-8") if agents_file.is_file() else ""
        try:
            updated, install_status = replace_managed_global_prompt_block(existing, str(projection.get("managed_block") or ""))
        except ValueError as exc:
            blockers.append(str(exc))
            updated = existing
        if not blockers:
            prompt_failures, prompt_blockers = check_global_prompt_text(
                updated,
                str(registry.get("registry_hash") or ""),
                str(projection.get("managed_block") or ""),
            )
            failures.extend(prompt_failures)
            blockers.extend(prompt_blockers)
        if not blockers and not failures and not args.dry_run:
            try:
                transaction = apply_global_router_transaction(
                    {
                        registry_path: json_block(registry).encode("utf-8"),
                        projection_path: json_block(projection).encode("utf-8"),
                        agents_file: updated.encode("utf-8"),
                    }
                )
            except GlobalRouterTransactionError as exc:
                blockers.append(str(exc))
            else:
                install_status = str(transaction["status"])
        elif not blockers and not failures and args.dry_run:
            install_status = "unchanged" if updated == existing else install_status
    payload = base_result("refresh-global-router", global_public_path(output_dir))
    payload["skill_roots"] = [global_public_path(root) for root in roots]
    payload["registry_path"] = global_public_path(registry_path)
    payload["projection_path"] = global_public_path(projection_path)
    payload["agents_file"] = global_public_path(agents_file)
    payload["registry_hash"] = registry.get("registry_hash", "") if registry else ""
    payload["install_status"] = "dry-run-" + install_status if args.dry_run else install_status
    payload["registry_item_count"] = registry.get("item_count", 0) if registry else 0
    payload["current_item_count"] = registry.get("current_item_count", 0) if registry else 0
    payload["failures"] = failures
    payload["blockers"] = blockers
    payload["decision"] = "block" if blockers else "fail" if failures else "pass"
    append_check(
        payload,
        "refresh-global-router:registry",
        "Registry refresh",
        "block" if root_blockers else "fail" if failures else "pass",
        "Scanned skill roots, rebuilt the global registry, and checked the registry/projection schemas.",
    )
    append_check(
        payload,
        "refresh-global-router:prompt",
        "Prompt install and freshness",
        payload["decision"],
        "Installed or dry-ran the managed AGENTS.md block and immediately checked it against the registry hash.",
    )
    payload["evidence"] = [
        {
            "evidence_id": "global-router-refresh-registry",
            "kind": "generated_registry",
            "fresh": payload["decision"] == "pass",
            "summary": f"Registry hash {payload['registry_hash']} covers {payload['registry_item_count']} skill item(s).",
            "source_path": payload["registry_path"],
        },
        {
            "evidence_id": "global-router-refresh-prompt",
            "kind": "prompt_installation",
            "fresh": payload["decision"] == "pass",
            "summary": f"{payload['install_status']} in {payload['agents_file']}.",
            "source_path": payload["agents_file"],
        },
    ]
    return write_and_exit(payload, args.output)


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
    normalized = value.replace("\\", "/")
    source_layout_prefix = f".agents/skills/{skill_root().name}"
    installed_skill_layout = skill_root().parent.name == "skills" and skill_root().parent.parent.name == ".codex"
    if installed_skill_layout and (normalized == ".agents/skills" or normalized.startswith(".agents/skills/")):
        return public_relative_path(resolve_skillguard_self_layout_path(value))
    return public_relative_path(resolve_repository_reference(value, fixture_path.parent))


def fixture_string_list(value: Any) -> list[str]:
    if isinstance(value, str) and value:
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if isinstance(item, (str, int, float))]
    return []


def build_route_task_fixture_argv(fixture_path: Path, case_data: dict[str, Any]) -> list[str]:
    argv: list[str] = []
    config_path = case_data.get("config_path") or case_data.get("input_path")
    if isinstance(config_path, str) and config_path:
        argv.extend(["--input", fixture_path_argument(fixture_path, config_path)])
    else:
        task_text = case_data.get("task")
        if isinstance(task_text, str):
            argv.extend(["--task", task_text])
        route_hint = case_data.get("route_hint")
        if isinstance(route_hint, str) and route_hint:
            argv.extend(["--route-hint", route_hint])

    for item in case_data.get("extra_arguments", []) if isinstance(case_data.get("extra_arguments"), list) else []:
        if isinstance(item, (str, int, float)):
            argv.append(str(item))
    return argv


def run_fixture_handler(handler: Callable[[list[str]], int], argv: list[str]) -> tuple[int, dict[str, Any]]:
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        exit_code = handler(argv)
    return exit_code, json.loads(stream.getvalue())


MUTATING_RUNTIME_FIXTURE_COMMANDS = {
    "build-global-registry",
    "mark-portfolio-impact",
    "graduate-portfolio",
    "refresh-global-router",
}


def bounded_fixture_workspace_name(parent: Path, fixture_id: str) -> str:
    """Keep marker paths below the legacy Windows path ceiling."""

    slug = slugify_identifier(fixture_id)
    marker_name = ".skillguard_fixture_workspace_marker"
    maximum_path_length = 240
    available = min(16, maximum_path_length - len(str(parent.resolve())) - len(marker_name) - 2)
    if len(slug) <= available:
        return slug
    return hashlib.sha256(fixture_id.encode("utf-8")).hexdigest()[: max(8, available)]


def reset_owned_fixture_workspace(fixture_path: Path, fixture_id: str) -> Path:
    parent = repository_root().resolve() / ".agents" / "skills" / ".sgf"
    workspace = (parent / bounded_fixture_workspace_name(parent, fixture_id)).resolve()
    workspace.relative_to(repository_root().resolve())
    marker = workspace / ".skillguard_fixture_workspace_marker"
    if workspace.exists():
        if not marker.is_file():
            raise ValueError(f"fixture workspace exists without SkillGuard ownership marker: {public_relative_path(workspace)}")
        for attempt in range(20):
            try:
                shutil.rmtree(workspace)
                break
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(0.05)
    workspace.mkdir(parents=True, exist_ok=True)
    marker.write_text("owned by SkillGuard fixture-test; safe to remove\n", encoding="utf-8")
    return workspace


def cleanup_owned_fixture_workspace(workspace: Path) -> bool:
    marker = workspace / ".skillguard_fixture_workspace_marker"
    if workspace.exists() and marker.is_file():
        parent = workspace.parent
        for attempt in range(20):
            try:
                shutil.rmtree(workspace)
                break
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(0.05)
        for _ in range(10):
            if not workspace.exists():
                break
            time.sleep(0.05)
        if owned_runtime_parent_may_be_pruned(repository_root().resolve(), parent) and parent.exists():
            for _ in range(10):
                if any(parent.iterdir()):
                    break
                try:
                    parent.rmdir()
                except OSError:
                    time.sleep(0.05)
                    continue
                break
        return not workspace.exists()
    return not workspace.exists()


def reset_owned_runtime_fixture_workspace(fixture_path: Path, fixture_id: str) -> Path:
    parent = repository_root().resolve() / ".sg-runtime"
    workspace = (parent / bounded_fixture_workspace_name(parent, fixture_id)).resolve()
    workspace.relative_to(repository_root().resolve())
    marker = workspace / ".skillguard_fixture_workspace_marker"
    if workspace.exists():
        if not marker.is_file():
            raise ValueError(f"fixture runtime workspace exists without SkillGuard ownership marker: {public_relative_path(workspace)}")
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    marker.write_text("owned by SkillGuard runtime fixture-test; safe to remove\n", encoding="utf-8")
    return workspace


def resolve_fixture_runtime_argument_path(fixture_path: Path, value: str) -> Path:
    normalized = value.replace("\\", "/")
    if normalized.startswith(".agents/skills"):
        return resolve_skillguard_self_layout_path(value)
    return resolve_repository_reference(value, fixture_path.parent)


def sandbox_mutating_runtime_fixture_argv(fixture_path: Path, fixture_id: str, argv: list[str]) -> tuple[list[str], Path | None]:
    fixture_root = fixture_path.parent.parent.resolve()
    source_workspace = (fixture_root / "workspace").resolve()
    if not source_workspace.is_dir():
        return argv, None

    sandbox_root = reset_owned_runtime_fixture_workspace(fixture_path, f"{fixture_id}-runtime")
    sandbox_workspace = sandbox_root / "workspace"
    shutil.copytree(source_workspace, sandbox_workspace, dirs_exist_ok=True)

    mapped_argv: list[str] = []
    for item in argv:
        try:
            candidate = resolve_fixture_runtime_argument_path(fixture_path, item).resolve()
            suffix = candidate.relative_to(source_workspace)
        except (OSError, ValueError):
            mapped_argv.append(item)
            continue
        mapped_argv.append(public_relative_path(sandbox_workspace / suffix))
    return mapped_argv, sandbox_root


def default_generation_fixture_idea(case_data: dict[str, Any], target: Path) -> dict[str, Any]:
    name = target.name
    idea = case_data.get("skill_idea")
    if isinstance(idea, dict):
        payload = json.loads(json.dumps(idea))
    else:
        payload = {
            "description": "Use when a maintainer needs a bounded simple generated fixture helper.",
            "purpose": "Create a minimal SkillGuard generation fixture with current evidence and claim boundaries.",
            "closure_scope": "simple generation fixture only",
            "evidence_policy": "current direct evidence required before target acceptance",
            "use_when": ["A maintainer needs to exercise the public simple generation path."],
            "do_not_use_when": ["The request needs package publication, release readiness, or private task material."],
            "required_workflow": ["Run the public generation command.", "Validate generated scaffold files before closure."],
            "hard_gates": ["Do not overwrite existing user-authored files.", "Keep generated evidence public-safe."],
            "output_requirements": ["evidence", "failures", "blockers", "skipped_checks", "residual_risk", "claim_boundary"],
        }
    payload["skill_name"] = str(payload.get("skill_name") or name)
    payload["target_path"] = public_relative_path(target)
    payload["workflow_mode"] = "create"
    payload["safe_edit_mode"] = "no_write"
    return payload


def write_generation_fixture_preexisting_files(target: Path, case_data: dict[str, Any]) -> list[str]:
    written: list[str] = []
    entries = case_data.get("preexisting_files", [])
    if not isinstance(entries, list):
        return written
    for index, item in enumerate(entries):
        if not isinstance(item, dict):
            raise ValueError(f"preexisting_files[{index}] must be an object")
        relative = item.get("path")
        if not isinstance(relative, str) or not relative:
            raise ValueError(f"preexisting_files[{index}].path must be a non-empty string")
        path = scaffold_path(target, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = str(item.get("content") if item.get("content") is not None else "user-authored fixture file\n")
        path.write_text(content, encoding="utf-8")
        written.append(public_relative_path(path))
    return written


def apply_generation_fixture_post_mutations(target: Path, case_data: dict[str, Any]) -> list[dict[str, str]]:
    mutations: list[dict[str, str]] = []
    for relative in fixture_string_list(case_data.get("post_generation_remove_files")):
        path = scaffold_path(target, relative)
        if path.exists() and path.is_file():
            path.unlink()
            mutations.append({"action": "remove_file", "path": public_relative_path(path)})
        else:
            mutations.append({"action": "remove_file_missing", "path": public_relative_path(path)})

    entries = case_data.get("post_generation_file_overrides", [])
    if isinstance(entries, list):
        for index, item in enumerate(entries):
            if not isinstance(item, dict):
                raise ValueError(f"post_generation_file_overrides[{index}] must be an object")
            relative = item.get("path")
            if not isinstance(relative, str) or not relative:
                raise ValueError(f"post_generation_file_overrides[{index}].path must be a non-empty string")
            path = scaffold_path(target, relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            content = str(item.get("content") if item.get("content") is not None else "")
            path.write_text(content, encoding="utf-8")
            mutations.append({"action": "override_file", "path": public_relative_path(path)})
    return mutations


def generate_skill_stable_projection(report: dict[str, Any]) -> dict[str, Any]:
    maintenance_record = report.get("maintenance_record") if isinstance(report.get("maintenance_record"), dict) else {}
    return {
        "decision": report.get("decision"),
        "target_path": report.get("target_path"),
        "missing_after_write": report.get("missing_after_write", []),
        "required_scaffold_files": report.get("required_scaffold_files", []),
        "all_scaffold_files": report.get("all_scaffold_files", []),
        "post_generation_checks": [
            {
                "command": item.get("command"),
                "artifact_path": item.get("artifact_path"),
                "status": item.get("status"),
                "reported_decision": item.get("reported_decision"),
            }
            for item in report.get("post_generation_checks", [])
            if isinstance(item, dict)
        ],
        "maintenance_record_schema_version": maintenance_record.get("schema_version"),
        "maintenance_record_content_hash": maintenance_record.get("content_hash"),
        "maintenance_record_status": maintenance_record.get("status"),
    }


def generation_fixture_default_required_files() -> list[str]:
    return list(GENERATE_SKILL_REQUIRED_FILES)


def generated_tree_public_boundary_problems(target: Path) -> list[str]:
    problems: list[str] = []
    for path in sorted(target.rglob("*")) if target.exists() else []:
        if not path.is_file():
            continue
        for finding in public_safety_findings(path):
            problems.append(f"{finding['path']} public-safety finding {finding['finding_id']}")
        unsafe_failures: list[str] = []
        scan_text_for_unsafe_claims(path, unsafe_failures)
        problems.extend(unsafe_failures)
    return problems


def expected_generated_file_content_problems(target: Path, expected: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    problems: list[str] = []
    checks: list[dict[str, Any]] = []
    expected_content = expected.get("generated_file_contains")
    if not isinstance(expected_content, dict):
        return problems, checks
    for relative, needles in expected_content.items():
        if not isinstance(relative, str) or not relative:
            problems.append("generated_file_contains keys must be non-empty relative paths")
            continue
        path = scaffold_path(target, relative)
        needle_list = fixture_string_list(needles)
        check = {
            "path": public_relative_path(path),
            "expected_substring_count": len(needle_list),
            "missing_substrings": [],
        }
        if not path.is_file():
            check["missing_file"] = True
            problems.append(f"generated content assertion file missing: {relative}")
        else:
            text = path.read_text(encoding="utf-8")
            missing = [needle for needle in needle_list if needle not in text]
            check["missing_substrings"] = missing
            if missing:
                problems.append(f"{relative} missing expected generated content: {missing}")
        checks.append(check)
    return problems, checks


def validate_generation_fixture_surfaces(
    *,
    case_data: dict[str, Any],
    target: Path,
    plan_report: dict[str, Any],
    generate_report: dict[str, Any],
    repeat_report: dict[str, Any] | None,
    generate_report_path: Path,
) -> tuple[list[str], dict[str, Any]]:
    expected = case_data.get("expected_result") if isinstance(case_data.get("expected_result"), dict) else {}
    problems: list[str] = []
    summary: dict[str, Any] = {
        "plan_decision": plan_report.get("decision"),
        "generate_decision": generate_report.get("decision"),
        "target_path": public_relative_path(target),
        "cleanup_expected": case_data.get("cleanup_workspace", True) is not False,
    }
    if plan_report.get("decision") != "pass":
        problems.append("plan-skill did not produce a pass decision before generation")

    required_files = expected.get("required_files")
    if not isinstance(required_files, list) or not required_files:
        required_files = generation_fixture_default_required_files()
    missing_required = [
        relative
        for relative in required_files
        if not (target / Path(str(relative))).is_file()
    ]
    summary["required_file_count"] = len(required_files)
    summary["missing_required_files"] = missing_required
    if generate_report.get("decision") == "pass" and missing_required:
        problems.append(f"generated scaffold is missing required files: {missing_required}")

    if generate_report.get("decision") == "pass":
        content_problems, content_checks = expected_generated_file_content_problems(target, expected)
        summary["generated_content_checks"] = content_checks
        problems.extend(content_problems)

    if expected.get("validate_generated_manifest", True) and generate_report.get("decision") == "pass":
        manifest_path = target / "fixtures" / "fixture-manifest.json"
        try:
            manifest_data = load_json(manifest_path)
            manifest_failures = validate_schema_subset(manifest_data, load_json(schema_path("skillguard_fixture_manifest.schema.json")))
        except ValueError as exc:
            manifest_failures = [str(exc)]
        summary["generated_manifest_schema_failures"] = manifest_failures
        if manifest_failures:
            problems.append("generated fixture manifest is not schema compliant")

    if expected.get("public_boundary_scan", True) and generate_report.get("decision") == "pass":
        public_problems = generated_tree_public_boundary_problems(target)
        summary["public_boundary_problem_count"] = len(public_problems)
        if public_problems:
            problems.extend(public_problems[:10])

    post_checks = generate_report.get("post_generation_checks", [])
    post_statuses = [
        {
            "command": item.get("command"),
            "status": item.get("status"),
            "reported_decision": item.get("reported_decision"),
        }
        for item in post_checks
        if isinstance(item, dict)
    ]
    summary["post_generation_checks"] = post_statuses
    if expected.get("post_generation_checks_pass", True) and generate_report.get("decision") == "pass":
        if not post_statuses or any(item.get("status") != "pass" for item in post_statuses):
            problems.append("post-generation checks did not all pass")

    if expected.get("deterministic_repeat") is True and generate_report.get("decision") == "pass":
        if repeat_report is None:
            problems.append("deterministic repeat requested but no repeat report was captured")
        else:
            first_projection = generate_skill_stable_projection(generate_report)
            repeat_projection = generate_skill_stable_projection(repeat_report)
            summary["deterministic_repeat_checked"] = True
            summary["repeat_created_file_count"] = len(repeat_report.get("created_files", [])) if isinstance(repeat_report.get("created_files"), list) else -1
            if first_projection != repeat_projection:
                problems.append("generate-skill stable projection changed on repeat generation")
            if repeat_report.get("created_files") not in ([], None):
                problems.append("repeat generation created files instead of preserving existing generated files")

    if expected.get("check_maintenance_record", True):
        exit_code, maintenance_report = run_fixture_handler(
            check_maintenance_record,
            ["--input", public_relative_path(generate_report_path)],
        )
        summary["check_maintenance_record_decision"] = maintenance_report.get("decision")
        summary["check_maintenance_record_exit_code"] = exit_code
        if maintenance_report.get("decision") != "pass":
            problems.append("check-maintenance-record did not pass for generate-skill output")

    if expected.get("detect_stale_evidence", True) and generate_report.get("decision") == "pass":
        exit_code, stale_report = run_fixture_handler(
            detect_stale_evidence,
            ["--input", public_relative_path(generate_report_path)],
        )
        summary["detect_stale_evidence_decision"] = stale_report.get("decision")
        summary["detect_stale_evidence_exit_code"] = exit_code
        summary["detect_stale_evidence_count"] = stale_report.get("stale_evidence_count")
        if stale_report.get("decision") != "pass":
            problems.append("detect-stale-evidence did not pass for current generated evidence")

    output_text = json.dumps({"plan": plan_report, "generate": generate_report}, sort_keys=True, ensure_ascii=False)
    for forbidden in fixture_string_list(expected.get("forbidden_output_substrings")):
        if forbidden and forbidden in output_text:
            problems.append("generate-skill output contained a disallowed public-boundary substring")
    for needle in fixture_string_list(expected.get("observed_blocker_contains")):
        observed_blockers = [str(item) for item in generate_report.get("blockers", []) if isinstance(item, str)]
        if needle and not any(needle in blocker for blocker in observed_blockers):
            problems.append(f"missing expected public blocker fragment: {needle}")
    return problems, summary


def evaluate_generate_skill_fixture_case(
    fixture_path: Path,
    case_data: dict[str, Any],
    fixture_id: str,
    expected_decision: str,
    failures: list[str],
    blockers: list[str],
) -> dict[str, Any]:
    workspace: Path | None = None
    cleanup_ok = False
    try:
        workspace = reset_owned_fixture_workspace(fixture_path, fixture_id)
        target_name = slugify_identifier(str(case_data.get("generated_skill_name") or f"{fixture_id}-skill"))
        target = workspace / target_name
        idea_path = workspace / "skill-idea.json"
        plan_path = workspace / "skill-blueprint.json"
        report_path = workspace / "generate-skill-report.json"
        idea = default_generation_fixture_idea(case_data, target)
        dump_json(idea, idea_path)
        _plan_exit, plan_report = run_fixture_handler(plan_skill, ["--input", public_relative_path(idea_path)])
        blueprint = plan_report
        for field in fixture_string_list(case_data.get("blueprint_remove_fields")):
            cursor: Any = blueprint
            parts = field.split(".")
            for part in parts[:-1]:
                cursor = cursor.get(part) if isinstance(cursor, dict) else None
            if isinstance(cursor, dict):
                cursor.pop(parts[-1], None)
        dump_json(plan_report, plan_path)
        preexisting_files = write_generation_fixture_preexisting_files(target, case_data)
        mutation_before = route_task_fixture_mutation_snapshot(fixture_path, case_data)
        exit_code, report = run_fixture_handler(generate_skill, ["--input", public_relative_path(plan_path)])
        dump_json(report, report_path)
        post_mutations = apply_generation_fixture_post_mutations(target, case_data)
        mutation_after = route_task_fixture_mutation_snapshot(fixture_path, case_data)

        repeat_report: dict[str, Any] | None = None
        expected = case_data.get("expected_result") if isinstance(case_data.get("expected_result"), dict) else {}
        if expected.get("deterministic_repeat") is True and str(report.get("decision")) == "pass":
            _repeat_exit, repeat_report = run_fixture_handler(generate_skill, ["--input", public_relative_path(plan_path)])

        observed = str(report.get("decision") or ("pass" if exit_code == 0 else "fail")).strip().lower()
        if observed not in FIXTURE_EXPECTED_DECISIONS:
            observed = "block"
        observed_failures = [str(item) for item in report.get("failures", []) if isinstance(item, str)]
        observed_blockers = [str(item) for item in report.get("blockers", []) if isinstance(item, str)]
        problems = observed_failures + [f"blocker: {item}" for item in observed_blockers]
        expectation_problems, validation_summary = validate_generation_fixture_surfaces(
            case_data=case_data,
            target=target,
            plan_report=plan_report,
            generate_report=report,
            repeat_report=repeat_report,
            generate_report_path=report_path,
        )
        mutation_problems = route_task_fixture_mutation_problems(mutation_before, mutation_after)
        expectation_problems.extend(mutation_problems)
        problems.extend(expectation_problems)
        if observed == "pass" and expectation_problems:
            observed = "fail"
        case_class = "expected_fail" if observed == "fail" else "expected_pass" if observed == "pass" else "blocker_condition"
        result = fixture_case_result(fixture_id, fixture_path, expected_decision, observed, case_class, problems, "generate-skill")
        result["command_arguments"] = ["--input", public_relative_path(plan_path)]
        result["target_path"] = str(report.get("target_path") or public_relative_path(target))
        result["command_exit_code"] = exit_code
        result["preexisting_files"] = preexisting_files
        result["observed_failure_count"] = len(observed_failures)
        result["observed_blocker_count"] = len(observed_blockers)
        result["observed_failures"] = observed_failures[:10]
        result["observed_blockers"] = observed_blockers[:10]
        result["post_generation_mutations"] = post_mutations
        result["generation_validation"] = validation_summary
        result["no_mutation_paths"] = mutation_after
        if repeat_report is not None:
            result["deterministic_repeat_checked"] = True
        if expected_decision != observed:
            failures.append(f"fixture {fixture_id}: expected {expected_decision} but observed {observed}")
        if expectation_problems and expected_decision != "fail":
            result["case_status"] = "fail"
            failures.append(f"fixture {fixture_id}: generate-skill structured expectations failed")
        return result
    except Exception as exc:
        observed = "block"
        result = fixture_case_result(
            fixture_id,
            fixture_path,
            expected_decision,
            observed,
            "blocker_condition",
            [f"generate-skill fixture execution failed: {public_safe_exception_message(exc)}"],
            "generate-skill",
        )
        if expected_decision != observed:
            failures.append(f"fixture {fixture_id}: generate-skill execution did not match expected decision {expected_decision}")
        return result
    finally:
        if workspace is not None and case_data.get("cleanup_workspace", True) is not False:
            cleanup_ok = cleanup_owned_fixture_workspace(workspace)
            if not cleanup_ok:
                failures.append(f"fixture {fixture_id}: generated workspace cleanup did not complete")


def build_runtime_fixture_argv(fixture_path: Path, case_data: dict[str, Any], target_command: str) -> list[str]:
    explicit_arguments = case_data.get("arguments")
    if isinstance(explicit_arguments, list):
        return [str(item) for item in explicit_arguments if isinstance(item, (str, int, float))]

    if target_command in {
        "scan-global-skills",
        "build-global-registry",
        "check-global-registry",
        "refresh-global-router",
    }:
        argv: list[str] = []
        for root in fixture_string_list(case_data.get("skill_roots") or case_data.get("skill_root")):
            argv.extend(["--skill-root", fixture_path_argument(fixture_path, root)])
        codex_home = case_data.get("codex_home")
        if isinstance(codex_home, str) and codex_home:
            argv.extend(["--codex-home", fixture_path_argument(fixture_path, codex_home)])
        registry_path = case_data.get("registry_path") or case_data.get("registry")
        if isinstance(registry_path, str) and registry_path and target_command in {
            "check-global-registry",
        }:
            argv.extend(["--registry", fixture_path_argument(fixture_path, registry_path)])
        registry_output = case_data.get("registry_output")
        if isinstance(registry_output, str) and registry_output and target_command == "build-global-registry":
            argv.extend(["--registry-output", fixture_path_argument(fixture_path, registry_output)])
        projection_output = case_data.get("projection_output")
        output_dir = case_data.get("output_dir")
        if isinstance(output_dir, str) and output_dir and target_command == "refresh-global-router":
            argv.extend(["--output-dir", fixture_path_argument(fixture_path, output_dir)])
        agents_file = case_data.get("agents_file")
        if isinstance(agents_file, str) and agents_file and target_command in {
            "refresh-global-router",
        }:
            argv.extend(["--agents-file", fixture_path_argument(fixture_path, agents_file)])
        task_text = case_data.get("task")
        if case_data.get("dry_run") is True and target_command == "refresh-global-router":
            argv.append("--dry-run")
        for item in case_data.get("extra_arguments", []) if isinstance(case_data.get("extra_arguments"), list) else []:
            if isinstance(item, (str, int, float)):
                argv.append(str(item))
        return argv

    if target_command == "route-task":
        return build_route_task_fixture_argv(fixture_path, case_data)

    if target_command in {"check-runtime-authority", "check-contract", "check-depth"}:
        target_path_text = case_data.get("target_path") or case_data.get("skill_path")
        if not isinstance(target_path_text, str) or not target_path_text:
            raise ValueError(f"{target_command} fixture must provide target_path")
        argv = ["--target", fixture_path_argument(fixture_path, target_path_text)]
        contract_path_text = case_data.get("contract_path") or case_data.get("contract")
        if isinstance(contract_path_text, str) and contract_path_text:
            raise ValueError(f"{target_command} fixture cannot declare a former contract path")
        for item in case_data.get("extra_arguments", []) if isinstance(case_data.get("extra_arguments"), list) else []:
            if isinstance(item, (str, int, float)):
                argv.append(str(item))
        return argv

    if target_command == "check-skill":
        target_path_text = case_data.get("target_path") or case_data.get("skill_path")
        if not isinstance(target_path_text, str) or not target_path_text:
            raise ValueError("check-skill fixture must provide target_path")
        argv = [
            "--repository-root",
            ".",
            "--target",
            fixture_path_argument(fixture_path, target_path_text),
        ]
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


def route_task_stable_projection(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision": report.get("decision"),
        "routing_decision": report.get("routing_decision"),
        "target_path": report.get("target_path"),
        "task_fingerprint": report.get("task_fingerprint"),
        "task_character_count": report.get("task_character_count"),
        "route_hint_fingerprint": report.get("route_hint_fingerprint"),
        "route_hint_character_count": report.get("route_hint_character_count"),
        "requested_responsibility": report.get("requested_responsibility"),
        "candidate_routes": report.get("candidate_routes"),
        "routing_conflict_blockers": report.get("routing_conflict_blockers"),
        "blockers": report.get("blockers"),
        "path_checks": report.get("path_checks"),
    }


def public_fixture_command_arguments(target_command: str, argv: list[str]) -> list[str]:
    if target_command != "route-task":
        return argv
    public_args: list[str] = []
    redact_next = False
    for item in argv:
        if redact_next:
            public_args.append("<task-redacted>")
            redact_next = False
            continue
        public_args.append(item)
        if item == "--task":
            redact_next = True
    return public_args


def public_safe_exception_message(exc: Exception) -> str:
    message = str(exc)
    replacement_pairs: list[tuple[str, str]] = []
    for base in (repository_root(), skill_root(), Path.home()):
        try:
            resolved = base.resolve()
        except OSError:
            resolved = base
        if base == Path.home():
            replacement = "<home>"
        else:
            replacement = public_relative_path(resolved)
        replacement_pairs.append((str(resolved), replacement))
        replacement_pairs.append((str(resolved).replace("\\", "/"), replacement))
        replacement_pairs.append((str(resolved).replace("\\", "\\\\"), replacement))
    for old, new in replacement_pairs:
        if old:
            message = message.replace(old, new)
    return message


def route_task_fixture_mutation_snapshot(fixture_path: Path, case_data: dict[str, Any]) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    for path_text in fixture_string_list(case_data.get("no_mutation_paths")):
        try:
            path = resolve_repository_reference(path_text, fixture_path.parent)
        except ValueError:
            snapshot[path_text] = {"valid": False}
            continue
        entry: dict[str, Any] = {
            "valid": True,
            "exists": path.exists(),
            "kind": "directory" if path.is_dir() else "file" if path.is_file() else "missing",
        }
        if path.is_file():
            entry["sha256"] = file_sha256(path)
        snapshot[public_relative_path(path)] = entry
    return snapshot


def route_task_fixture_mutation_problems(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for path_text, before_entry in before.items():
        after_entry = after.get(path_text, {})
        if not before_entry.get("valid"):
            problems.append(f"no_mutation_paths entry is outside the repository: {path_text}")
            continue
        if before_entry.get("exists") != after_entry.get("exists"):
            problems.append(f"no-mutation path existence changed: {path_text}")
        if before_entry.get("kind") != after_entry.get("kind"):
            problems.append(f"no-mutation path type changed: {path_text}")
        if before_entry.get("sha256") != after_entry.get("sha256"):
            problems.append(f"no-mutation file content changed: {path_text}")
    return problems


def route_task_fixture_expected_codes(expected: dict[str, Any]) -> set[str]:
    codes: set[str] = set()
    for field in ("blocker_code", "blocker_codes"):
        value = expected.get(field)
        if isinstance(value, str) and value:
            codes.add(value)
        elif isinstance(value, list):
            codes.update(str(item) for item in value if isinstance(item, str) and item)
    return codes


def evaluate_route_task_expectations(
    *,
    fixture_path: Path,
    case_data: dict[str, Any],
    report: dict[str, Any],
    repeat_report: dict[str, Any] | None,
    mutation_before: dict[str, Any],
    mutation_after: dict[str, Any],
) -> list[str]:
    problems: list[str] = []
    expected = case_data.get("expected_result")
    if not isinstance(expected, dict):
        expected = {}

    structured = report.get("routing_conflict_blockers", [])
    if not isinstance(structured, list):
        problems.append("routing_conflict_blockers must be a list")
        structured = []
    structured_items = [item for item in structured if isinstance(item, dict)]
    structured_codes = {str(item.get("blocker_code")) for item in structured_items if item.get("blocker_code")}
    for blocker_code in sorted(route_task_fixture_expected_codes(expected)):
        if blocker_code not in structured_codes:
            problems.append(f"missing routing_conflict_blockers blocker_code {blocker_code}")

    expected_class = expected.get("blocker_class")
    if isinstance(expected_class, str) and expected_class:
        if not any(item.get("blocker_class") == expected_class for item in structured_items):
            problems.append(f"missing routing_conflict_blockers blocker_class {expected_class}")

    expected_fields = {str(item) for item in expected.get("conflicting_fields", []) if isinstance(item, str)}
    if expected_fields:
        observed_fields: set[str] = set()
        for item in structured_items:
            observed_fields.update(str(field) for field in item.get("conflicting_fields", []) if isinstance(field, str))
        missing_fields = sorted(expected_fields - observed_fields)
        if missing_fields:
            problems.append(f"missing conflicting_fields: {missing_fields}")

    expected_candidate_commands = {
        str(item) for item in expected.get("candidate_command_families", []) if isinstance(item, str)
    }
    if expected_candidate_commands:
        observed_candidate_commands: set[str] = set()
        for candidate in report.get("candidate_routes", []) if isinstance(report.get("candidate_routes"), list) else []:
            if isinstance(candidate, dict) and isinstance(candidate.get("command_family"), str):
                observed_candidate_commands.add(candidate["command_family"])
        for item in structured_items:
            for candidate in item.get("conflicting_candidates", []) if isinstance(item.get("conflicting_candidates"), list) else []:
                if isinstance(candidate, dict) and isinstance(candidate.get("command_family"), str):
                    observed_candidate_commands.add(candidate["command_family"])
        missing_candidates = sorted(expected_candidate_commands - observed_candidate_commands)
        if missing_candidates:
            problems.append(f"missing candidate command families: {missing_candidates}")

    for needle in fixture_string_list(expected.get("message_contains")):
        messages = [str(item.get("message", "")) for item in structured_items]
        messages.extend(str(item) for item in report.get("blockers", []) if isinstance(item, str))
        if not any(needle in message for message in messages):
            problems.append(f"missing public-safe message fragment: {needle}")

    if expected.get("no_route_selected") is True and report.get("routing_decision") not in ({}, None):
        problems.append("routing_decision must be empty when the route-task fixture expects no route selection")
    if expected.get("empty_target_path_when_blocked") is True and report.get("decision") == "block" and report.get("target_path"):
        problems.append("target_path must be empty when route-task blocks")

    output_text = json.dumps(report, sort_keys=True, ensure_ascii=False)
    forbidden_substrings = fixture_string_list(expected.get("forbidden_output_substrings"))
    if expected.get("no_task_echo") is True:
        for task_field in ("task", "task_text"):
            value = case_data.get(task_field)
            if isinstance(value, str) and value:
                forbidden_substrings.append(value)
    for forbidden in forbidden_substrings:
        if forbidden and forbidden in output_text:
            problems.append("route-task output echoed a forbidden fixture substring")

    problems.extend(route_task_fixture_mutation_problems(mutation_before, mutation_after))

    if expected.get("deterministic_repeat") is True:
        if repeat_report is None:
            problems.append("deterministic repeat was requested but no repeat report was captured")
        elif route_task_stable_projection(report) != route_task_stable_projection(repeat_report):
            problems.append("deterministic repeat produced a different stable route-task projection")

    for term in fixture_string_list(expected.get("must_not_contain")):
        if term and term in output_text:
            problems.append("route-task output contained a disallowed public-safety term")

    if expected.get("path_checks_block") is True:
        path_checks = report.get("path_checks", [])
        path_check_items = path_checks if isinstance(path_checks, list) else []
        if not any(isinstance(item, dict) and item.get("status") == "block" for item in path_check_items):
            problems.append("expected at least one blocking path_checks entry")

    return problems


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
    if target_command == "generate-skill":
        return evaluate_generate_skill_fixture_case(fixture_path, case_data, fixture_id, expected_decision, failures, blockers)
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
        "build-global-registry": build_global_registry,
        "check-global-registry": check_global_registry,
        "check-runtime-authority": check_runtime_authority,
        "check-contract": check_contract,
        "check-depth": check_depth,
        "check-readme-release": check_readme_release,
        "check-skill": check_skill,
        "check-suite": check_suite,
        "audit-portfolio": PORTFOLIO_COMMANDS["audit-portfolio"],
        "mark-portfolio-impact": PORTFOLIO_COMMANDS["mark-portfolio-impact"],
        "graduate-portfolio": PORTFOLIO_COMMANDS["graduate-portfolio"],
        "refresh-global-router": refresh_global_router,
        "route-task": route_task,
        "scan-global-skills": scan_global_skills,
        "self-check": self_check,
    }
    handler = handler_map[target_command]

    stream = io.StringIO()
    sandbox_workspace: Path | None = None
    mutation_before = route_task_fixture_mutation_snapshot(fixture_path, case_data) if target_command == "route-task" else {}
    repeat_report: dict[str, Any] | None = None
    expected_result = case_data.get("expected_result")
    deterministic_repeat = isinstance(expected_result, dict) and expected_result.get("deterministic_repeat") is True
    try:
        run_argv = argv
        if target_command in MUTATING_RUNTIME_FIXTURE_COMMANDS and case_data.get("sandbox_workspace", True) is not False:
            run_argv, sandbox_workspace = sandbox_mutating_runtime_fixture_argv(fixture_path, fixture_id, argv)
        with contextlib.redirect_stdout(stream):
            exit_code = handler(run_argv)
        report = json.loads(stream.getvalue())
        if target_command == "route-task" and deterministic_repeat:
            repeat_stream = io.StringIO()
            with contextlib.redirect_stdout(repeat_stream):
                repeat_exit_code = handler(run_argv)
            repeat_report = json.loads(repeat_stream.getvalue())
            if repeat_exit_code != exit_code:
                report.setdefault("fixture_repeat_findings", []).append("deterministic repeat exit code changed")
    except Exception as exc:
        observed = "block"
        result = fixture_case_result(
            fixture_id,
            fixture_path,
            expected_decision,
            observed,
            "blocker_condition",
            [f"{target_command} fixture execution failed: {public_safe_exception_message(exc)}"],
            target_command,
        )
        if expected_decision != observed:
            failures.append(f"fixture {fixture_id}: {target_command} execution did not match expected decision {expected_decision}")
        return result
    finally:
        if sandbox_workspace is not None and case_data.get("cleanup_workspace", True) is not False:
            cleanup_ok = cleanup_owned_fixture_workspace(sandbox_workspace)
            if not cleanup_ok:
                failures.append(f"fixture {fixture_id}: runtime fixture sandbox cleanup did not complete")

    mutation_after = route_task_fixture_mutation_snapshot(fixture_path, case_data) if target_command == "route-task" else {}
    observed = str(report.get("decision") or ("pass" if exit_code == 0 else "fail")).strip().lower()
    if observed not in FIXTURE_EXPECTED_DECISIONS:
        observed = "block"
    observed_failures = [str(item) for item in report.get("failures", []) if isinstance(item, str)]
    observed_blockers = [str(item) for item in report.get("blockers", []) if isinstance(item, str)]
    problems = observed_failures + [f"blocker: {item}" for item in observed_blockers]
    case_class = "expected_fail" if observed == "fail" else "expected_pass" if observed == "pass" else "blocker_condition"
    result = fixture_case_result(fixture_id, fixture_path, expected_decision, observed, case_class, problems, target_command)
    result["command_arguments"] = public_fixture_command_arguments(target_command, argv)
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
    if target_command == "route-task":
        route_task_problems = evaluate_route_task_expectations(
            fixture_path=fixture_path,
            case_data=case_data,
            report=report,
            repeat_report=repeat_report,
            mutation_before=mutation_before,
            mutation_after=mutation_after,
        )
        result["routing_conflict_blocker_codes"] = [
            item.get("blocker_code")
            for item in report.get("routing_conflict_blockers", [])
            if isinstance(item, dict) and item.get("blocker_code")
        ]
        result["routing_decision_present"] = bool(report.get("routing_decision"))
        result["task_fingerprint"] = report.get("task_fingerprint", "")
        result["route_task_stable_projection"] = route_task_stable_projection(report)
        result["no_mutation_paths"] = mutation_after
        if repeat_report is not None:
            result["deterministic_repeat_checked"] = True
        if route_task_problems:
            result["case_status"] = "fail"
            result["problems"].extend(route_task_problems)
            failures.append(f"fixture {fixture_id}: route-task structured expectations failed")
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
    parser.add_argument("--fixture-id", action="append", default=[], help="Restrict a manifest-based run to the named fixture id. Repeatable.")
    parser.add_argument("--fixture", action="append", default=[], help="Additional fixture case JSON path under the repository root.")
    parser.add_argument("--output", default="-", help="Output report path under the skill root, or '-' for stdout.")
    args = parser.parse_args(argv)
    if not args.manifest and not args.fixture:
        parser.error("fixture-test requires --manifest or at least one --fixture")
    if args.fixture_id and not args.manifest:
        parser.error("--fixture-id requires --manifest")
    if args.fixture_id and args.fixture:
        parser.error("--fixture-id cannot be combined with --fixture")

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
    requested_fixture_ids = set(args.fixture_id or [])
    matched_fixture_ids: set[str] = set()
    for index, fixture in enumerate(manifest_fixtures):
        fixture_id = str(fixture.get("fixture_id") or f"manifest-fixture-{index + 1}")
        if requested_fixture_ids and fixture_id not in requested_fixture_ids:
            continue
        if requested_fixture_ids:
            matched_fixture_ids.add(fixture_id)
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
    for missing_fixture_id in sorted(requested_fixture_ids - matched_fixture_ids):
        failures.append(f"fixture-id {missing_fixture_id!r} was not found in the supplied manifest")
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
    attach_maintenance_record(
        payload,
        record_kind="fixture_evidence",
        artifact_id=payload.get("target_path") or "fixture-test",
        route_node_id="fixture-test",
        checker_name="fixture-test",
        blockers=blockers + failures,
        owner_action={"action": "fixture_test", "status": payload["decision"], "fixture_result_count": len(fixture_results)},
        content_seed={
            "target_path": payload.get("target_path"),
            "fixture_ids": [item.get("fixture_id") for item in fixture_results if isinstance(item, dict)],
            "class_counts": class_counts,
            "decision": payload["decision"],
        },
    )
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

    repo = repository_root()
    default_source_target = ".agents/skills/skillguard"
    default_source_target_path = repo / default_source_target
    if (
        args.target == default_source_target
        and not (default_source_target_path / "SKILL.md").is_file()
        and (skill_root() / "SKILL.md").is_file()
    ):
        target = skill_root()
    else:
        target = resolve_target_argument(args.target)
    source_layout = target.resolve() == default_source_target_path.resolve() and (default_source_target_path / "SKILL.md").is_file()
    layout = "source_repository" if source_layout else "installed_skill"
    policy_root_supplied = bool(args.policy_root)
    policy_root = ensure_under_root(args.policy_root) if policy_root_supplied else repo
    policy_relative_paths = {
        "README.md",
        "AGENTS.md",
        "references/06-evidence-freshness-and-closure-boundaries.md",
        "references/08-checker-change-fixture-policy.md",
        "references/09-skillguard-self-check.md",
    }

    def self_check_path(relative: str) -> Path:
        normalized = relative.replace("\\", "/")
        source_layout_prefix = ".agents/skills/skillguard/"
        if source_layout:
            if normalized in policy_relative_paths:
                return policy_root / normalized
            return repo / normalized
        if normalized.startswith(source_layout_prefix):
            return target / normalized[len(source_layout_prefix):]
        if normalized in policy_relative_paths or normalized in {"LICENSE", "VERSION", "pyproject.toml"}:
            return (policy_root / normalized) if policy_root_supplied else target / normalized
        return target / normalized

    skipped_checks: list[dict[str, Any]] = []
    source_required_paths = [
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
        ".agents/skills/skillguard/assets/schemas/skillguard_maintenance_record.schema.json",
        ".agents/skills/skillguard/assets/schemas/skillguard_global_registry.schema.json",
        ".agents/skills/skillguard/assets/schemas/skillguard_global_prompt_projection.schema.json",
        ".agents/skills/skillguard/assets/templates/skillguard_checker_change.template.json",
        ".agents/skills/skillguard/assets/templates/skillguard_fixture_manifest.template.json",
        ".agents/skills/skillguard/assets/templates/skillguard_closure.template.json",
        ".agents/skills/skillguard/assets/templates/global_skillguard_prompt_block.md.template",
        ".agents/skills/skillguard/fixtures/checker_change/current-baseline.json",
        ".agents/skills/skillguard/fixtures/bad_routing/fixture-manifest.json",
        ".agents/skills/skillguard/fixtures/global_router/fixture-manifest.json",
        ".agents/skills/skillguard/fixtures/simple_generation/fixture-manifest.json",
        ".agents/skills/skillguard/fixtures/complex_generation/fixture-manifest.json",
        ".agents/skills/skillguard/.skillguard/flowguard_contract_model.py",
        ".agents/skills/skillguard/.skillguard/contract-source.json",
        ".agents/skills/skillguard/.skillguard/compiled-contract.json",
        ".agents/skills/skillguard/.skillguard/check-manifest.json",
        "references/06-evidence-freshness-and-closure-boundaries.md",
        "references/08-checker-change-fixture-policy.md",
        "references/09-skillguard-self-check.md",
    ]
    installed_required_paths = [
        "SKILL.md",
        "scripts/skillguard.py",
        "scripts/checker_engine.py",
        "scripts/skillguard_utils.py",
        "assets/schemas/skillguard_fixture_manifest.schema.json",
        "assets/schemas/skillguard_check_report.schema.json",
        "assets/schemas/skillguard_workflow_report.schema.json",
        "assets/schemas/skillguard_maintenance_record.schema.json",
        "assets/schemas/skillguard_global_registry.schema.json",
        "assets/schemas/skillguard_global_prompt_projection.schema.json",
        "assets/templates/skillguard_checker_change.template.json",
        "assets/templates/skillguard_fixture_manifest.template.json",
        "assets/templates/skillguard_closure.template.json",
        "assets/templates/global_skillguard_prompt_block.md.template",
        ".skillguard/flowguard_contract_model.py",
        ".skillguard/contract-source.json",
        ".skillguard/compiled-contract.json",
        ".skillguard/check-manifest.json",
    ]
    if policy_root_supplied and not source_layout:
        installed_required_paths.extend(sorted(policy_relative_paths))
    required_paths = source_required_paths if source_layout else installed_required_paths

    def self_check_json_paths() -> list[str]:
        source_json_paths = [
            ".agents/skills/skillguard/assets/schemas/skillguard_fixture_manifest.schema.json",
            ".agents/skills/skillguard/assets/schemas/skillguard_check_report.schema.json",
            ".agents/skills/skillguard/assets/schemas/skillguard_workflow_report.schema.json",
            ".agents/skills/skillguard/assets/schemas/skillguard_maintenance_record.schema.json",
            ".agents/skills/skillguard/assets/schemas/skillguard_global_registry.schema.json",
            ".agents/skills/skillguard/assets/schemas/skillguard_global_prompt_projection.schema.json",
            ".agents/skills/skillguard/fixtures/checker_change/current-baseline.json",
            ".agents/skills/skillguard/fixtures/bad_routing/fixture-manifest.json",
            ".agents/skills/skillguard/fixtures/global_router/fixture-manifest.json",
            ".agents/skills/skillguard/fixtures/simple_generation/fixture-manifest.json",
            ".agents/skills/skillguard/fixtures/complex_generation/fixture-manifest.json",
            ".agents/skills/skillguard/.skillguard/contract-source.json",
            ".agents/skills/skillguard/.skillguard/compiled-contract.json",
            ".agents/skills/skillguard/.skillguard/check-manifest.json",
        ]
        if source_layout:
            return source_json_paths
        prefix = ".agents/skills/skillguard/"
        return [
            path[len(prefix):]
            for path in source_json_paths
            if not path.startswith(prefix + "fixtures/")
        ]

    target_relative = public_relative_path(target)
    payload = base_result("self-check", target_relative)
    payload["layout"] = layout
    payload["claim_boundary"] = (
        "This self-check covers the current local SkillGuard source-repository layout or installed-skill layout, "
        "the SkillGuard skill entrypoint, checker policy artifacts when present for that layout, control records, "
        "report/evidence conventions, public-boundary wording, and local CLI dispatch. It does not prove full fixture coverage, "
        "suite automation, package publication, release readiness, code-contract validation, external publication, or future AI behavior."
    )
    failures: list[str] = []
    blockers: list[str] = []
    inspected_files: list[dict[str, Any]] = []
    public_safety: list[dict[str, Any]] = []
    unsafe_claim_findings: list[dict[str, Any]] = []

    before_failures, before_blockers = len(failures), len(blockers)
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
        f"Checked current SkillGuard {layout} files needed for self-check.",
    )

    before_failures, before_blockers = len(failures), len(blockers)
    for json_relative in self_check_json_paths():
        try:
            load_json(self_check_path(json_relative))
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
    if readme_text:
        for command_name in command_names:
            if f"`{command_name}`" not in readme_text:
                failures.append(f"README command surface missing `{command_name}`")
        for term in ("fixture coverage", "suite automation", "package publication", "release readiness", "code-contract validation"):
            if term not in readme_text.lower():
                failures.append(f"README public boundary missing {term!r}")
    elif source_layout or policy_root_supplied:
        failures.append("README.md missing for source-repository public-boundary check")
    else:
        skipped_checks.append(
            {
                "check_id": "self-check:source-readme-public-boundary",
                "reason": "Installed SkillGuard layout does not ship the source repository README; source-repository self-check covers README wording.",
                "required": False,
                "status_impact": "Not a pass claim for source README command-surface wording.",
            }
        )
    append_check(
        payload,
        "self-check:public-boundary",
        "README and command boundary",
        check_status(failures, blockers, before_failures, before_blockers),
        "Checked local command dispatch entries and, when available for this layout, README command wording and conservative public-boundary terms.",
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
    ref08_available = ref08_path.is_file()
    ref09_available = ref09_path.is_file()
    if ref08_available and ref09_available:
        ref08 = ref08_path.read_text(encoding="utf-8").lower()
        ref09 = ref09_path.read_text(encoding="utf-8").lower()
        for term in ("positive fixtures", "negative fixtures", "stale fixture", "absent fixture", "current identity", "public-safety"):
            if term not in ref08:
                failures.append(f"checker-change fixture policy missing term {term!r}")
        for term in ("required inputs", "deterministic checks", "public-safety checks", "closure boundaries", "pass, fail, and block"):
            if term not in ref09:
                failures.append(f"self-check reference missing term {term!r}")
    elif source_layout or policy_root_supplied:
        if not ref08_available:
            failures.append("references/08-checker-change-fixture-policy.md missing for policy artifact check")
        if not ref09_available:
            failures.append("references/09-skillguard-self-check.md missing for policy artifact check")
    else:
        skipped_checks.append(
            {
                "check_id": "self-check:source-policy-reference-docs",
                "reason": "Installed SkillGuard layout does not ship the source repository policy reference documents; source-repository self-check covers them.",
                "required": False,
                "status_impact": "Not a pass claim for source policy reference wording.",
            }
        )
    append_check(
        payload,
        "self-check:policy-artifacts",
        "Checker-change and self-check policy artifacts",
        check_status(failures, blockers, before_failures, before_blockers),
        "Checked checker-change fixture policy and self-check reference documents when available for this layout.",
    )

    before_failures, before_blockers = len(failures), len(blockers)
    public_paths = [
        path
        for path in [
            readme_path,
            self_check_path("AGENTS.md"),
            target / "SKILL.md",
            self_check_path("references/06-evidence-freshness-and-closure-boundaries.md"),
            self_check_path("references/08-checker-change-fixture-policy.md"),
            self_check_path("references/09-skillguard-self-check.md"),
        ]
        if path.is_file()
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
        "Scanned available public SkillGuard files for private paths, runtime ids, credentials, private keys, and declared unsafe overclaim phrases.",
    )

    checker_engine_path = self_check_path(".agents/skills/skillguard/scripts/checker_engine.py")
    public_safety_source_path = readme_path if readme_path.is_file() else target / "SKILL.md"
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
            "summary": f"Checked {len(command_names)} local command dispatch entries against available public boundary wording.",
            "source_path": public_relative_path(checker_engine_path),
        },
        {
            "evidence_id": "self-check-public-safety",
            "kind": "text_scan",
            "fresh": True,
            "summary": f"Scanned {len(public_paths)} public files for public-safety and unsafe-claim patterns.",
            "source_path": public_relative_path(public_safety_source_path),
        },
    ]
    payload["skipped_checks"] = skipped_checks + [
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
    attach_maintenance_record(
        payload,
        record_kind="self_check",
        artifact_id=target_relative,
        route_node_id="self-check",
        checker_name="self-check",
        blockers=blockers + failures,
        owner_action={"action": "not_applicable", "status": "self_check"},
        content_seed={"files_inspected": len(inspected_files), "command_count": len(command_names), "layout": layout},
    )
    return write_and_exit(payload, args.output)


from skillguard_v2.project_adoption import (  # noqa: E402
    maintainer_adopt_command,
    maintainer_audit_command,
)


CommandHandler = Callable[[list[str]], int]


COMMAND_SUMMARIES: dict[str, str] = {
    "commands": "List command dispatch targets.",
    "route-task": "Route one task request to a current SkillGuard command family.",
    "inventory": "Generate a repository inventory record.",
    "plan-skill": "Convert a skill idea JSON file into a no-write Skill Blueprint preview.",
    "generate-skill": "Create a draft SkillGuard skill scaffold from a valid Skill Blueprint.",
    "generate-suite": "Create a draft multi-skill SkillGuard suite scaffold from a valid Suite Blueprint.",
    "scan-global-skills": "Scan skill roots for SKILL.md files and SkillGuard route documents.",
    "build-global-registry": "Build a global SkillGuard skill registry artifact from scanned roots.",
    "check-global-registry": "Check a global SkillGuard registry schema and freshness against current roots.",
    "refresh-global-router": "Author-side refresh of the maintained-skill registry and managed maintainer prompt projection.",
    "check-runtime-authority": "Resolve one target's current-or-blocked runtime authority.",
    "maintainer-adopt": "Adopt an explicit skill-authoring repository with an author-only prompt and manifest.",
    "maintainer-audit": "Audit the author-only repository prompt, manifest, maintenance units, routes, and repository link.",
    "build-current-portfolio-registry": "Directly replace portfolio authority from one reviewed hash-valid current scope without reading or migrating a prior registry.",
    "audit-portfolio": "Audit private portfolio structure, current Guard runtime identity, child evidence currentness, and prior-skill visibility.",
    "mark-portfolio-impact": "Invalidate current portfolio evidence after a declared Guard change without silently preserving old green status.",
    "verify-portfolio-impact-receipt": "Replay an immutable model-miss impact receipt against the exact current portfolio registry and required target set.",
    "capture-installation-receipt": "Capture canonical, transactional-install, active-tree, parity, and installed-runtime identities into one immutable installation receipt.",
    "verify-installation-receipt": "Replay an immutable installation receipt against the current canonical and installed SkillGuard trees.",
    "prepare-portfolio-run": "Atomically freeze one complete portfolio job plan and every job specification before any representative run is claimed.",
    "execute-portfolio-run": "Execute every prepared representative job through ordinary claimed current runs under one preparation identity.",
    "capture-portfolio-production-revalidation": "Capture one target member's exact scheduled-production declared-check depth, terminal, closure, and current installed-runtime binding.",
    "assemble-portfolio-run": "Replay prepared execution evidence and assemble a verifier-owned graduation candidate without mutating the portfolio registry.",
    "graduate-portfolio": "Graduate one maintenance unit only from that unit's complete current evidence; no other unit's proof is consumed.",
    "check-json-schema": "Check one JSON file against an explicit local schema file.",
    "check-contract": "Check a target work contract for schema, hash, references, scripts, and closure-rule readiness.",
    "check-depth": "Check target-specific deep contract coverage against source requirements, checks, run records, and closure blockers.",
    "check-readme-release": "Check README release gates for bilingual mirror, hero provenance, current-version model artifacts, public boundary, and version consistency.",
    "init-target": "Create missing target .skillguard directories without rewriting existing files.",
    "init-suite": "Create missing suite-level .skillguard directories without rewriting existing files.",
    "mark": "Create, update, or report an already-present marker record for one target or suite scope.",
    "check-skill": "Check one target skill directory for static SkillGuard contract and control-record readiness.",
    "check-suite": "Check suite records, member relations, child closure evidence, stale evidence, and unsafe claims.",
    "check-suite-map": "Check one suite map JSON record.",
    "check-suite-contract": "Check one suite contract JSON record.",
    "check-fixture-manifest": "Check one fixture manifest JSON record.",
    "fixture-test": "Run explicit fixture cases and compare expected pass, fail, block, and invalid-input outcomes.",
    "detect-stale-evidence": "Detect stale or unverifiable evidence records before they support current claims.",
    "review-checker-change": "Review checker-change bindings against an approved baseline without mutating evidence.",
    "check-maintenance-record": "Validate one current public maintenance record without converting any other shape.",
    "check-ai-judgment": "Check one AI judgment JSON record.",
    "check-report": "Check one deterministic check-report JSON record.",
    "check-workflow-report": "Check one workflow-report JSON record.",
    "make-closure": "Derive a bounded closure record from current report data and declared direct evidence references.",
    "self-check": "Check the current SkillGuard repository, skill entrypoint, checker policy, evidence conventions, and public boundaries.",
    "write-report": "Load JSON and write stable parseable JSON to stdout or a skill-root-local file.",
}


COMMANDS: dict[str, CommandHandler] = {
    "commands": commands,
    "route-task": route_task,
    "inventory": inventory,
    "plan-skill": plan_skill,
    "generate-skill": generate_skill,
    "generate-suite": generate_suite,
    "scan-global-skills": scan_global_skills,
    "build-global-registry": build_global_registry,
    "check-global-registry": check_global_registry,
    "refresh-global-router": refresh_global_router,
    "check-runtime-authority": check_runtime_authority,
    "maintainer-adopt": maintainer_adopt_command,
    "maintainer-audit": maintainer_audit_command,
    **PORTFOLIO_COMMANDS,
    "check-json-schema": check_json_schema,
    "check-contract": check_contract,
    "check-depth": check_depth,
    "check-readme-release": check_readme_release,
    "init-target": init_target,
    "init-suite": init_suite,
    "mark": mark,
    "check-skill": check_skill,
    "check-suite": check_suite,
    "check-suite-map": check_suite_map,
    "check-suite-contract": check_suite_contract,
    "check-fixture-manifest": check_fixture_manifest,
    "fixture-test": fixture_test,
    "detect-stale-evidence": detect_stale_evidence,
    "review-checker-change": review_checker_change,
    "check-maintenance-record": check_maintenance_record,
    "check-ai-judgment": check_ai_judgment,
    "check-report": check_report,
    "check-workflow-report": check_workflow_report,
    "make-closure": make_closure,
    "self-check": self_check,
    "write-report": write_report_command,
}
