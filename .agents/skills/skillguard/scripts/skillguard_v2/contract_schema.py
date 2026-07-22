"""Schema constants and fail-closed validation for current SkillGuard records."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from .capability_contract import normalize_portfolio_capability_contracts


MODEL_EXPORT_SCHEMA = "skillguard.flowguard_model_export.v2"
BINDING_SOURCE_SCHEMA = "skillguard.contract_source.v2"
COMPILED_CONTRACT_SCHEMA = "skillguard.compiled_contract.v2"
CHECK_MANIFEST_SCHEMA = "skillguard.check_manifest.v2"
RUN_SCHEMA = "skillguard.run.v2"
EVENT_SCHEMA = "skillguard.run_event.v2"
ARTIFACT_SCHEMA = "skillguard.artifact_record.v2"
RECEIPT_SCHEMA = "skillguard.evidence_receipt.v2"
CLOSURE_SCHEMA = "skillguard.closure_receipt.v2"
NATIVE_NOOP_RECEIPT_SCHEMA = "skillguard.native_noop_receipt.v2"
NATIVE_TERMINAL_RECEIPT_SCHEMA = "skillguard.native_terminal_receipt.v2"
OBLIGATION_APPLICABILITY_RECEIPT_SCHEMA = (
    "skillguard.obligation_applicability_receipt.v2"
)
DEPTH_PROFILE_SCHEMA = "skillguard.depth_profile.v2"
TARGET_EXECUTION_RECEIPT_SCHEMA = "skillguard.target_execution_receipt.v2"
TARGET_NATIVE_DEPTH_EVIDENCE_SCHEMA = "skillguard.native_depth_evidence.v2"
PROJECT_ADOPTION_SCHEMA = "skillguard.project_adoption.v1"
CONTENT_IMPACT_PLAN_SCHEMA = "skillguard.content_impact_plan.current"
CONTENT_IMPACT_POLICY_ID = "skillguard.content_impact_policy.current"
CONTENT_IMPACT_OWNER_ROOT = {
    "path_token": "owner_evidence_root",
    "relative_path": "check-executions",
}

SUPPORTED_FLOWGUARD_SCHEMA_VERSIONS = frozenset({"1.0"})
TARGET_KINDS = frozenset({"skill", "internal_route", "helper_api", "external_action"})
EVIDENCE_CLASSES = frozenset({"hard", "witnessed", "judged"})
TERMINAL_KINDS = frozenset({"", "success", "blocked"})
CLOSURE_PROFILE_ORDER = ("enforced",)
DEPTH_INTEGRATION_MODES = frozenset({"native-integrated"})
DEPTH_ENFORCEMENT_LEVELS = frozenset({"enforced"})
DEPTH_DIMENSIONS = frozenset(
    {
        "input",
        "scope",
        "route",
        "workflow",
        "branch",
        "semantic",
        "validation",
        "artifact",
        "side_effect",
        "recovery",
        "closure",
        "reuse",
    }
)
DEPTH_NON_PASS_STATUSES = frozenset(
    {
        "BOUNDED_PARTIAL",
        "BOUNDARY_ONLY",
        "SHALLOW_BLOCKED",
        "NOT_RUN",
        "DEPTH_CONTRACT_MISSING",
        "PROVIDER_UNAVAILABLE",
        "UNMANAGED",
        "STALE",
    }
)
DEPTH_CONTRIBUTION_RANGE_KINDS = frozenset(
    {"record", "rows", "bytes", "sections", "semantic", "full_receipt"}
)
DEPTH_EVIDENCE_DOMAINS = frozenset(
    {"fixture_validation", "capability_validation", "scheduled_production"}
)
SHA256_RE = re.compile(r"^[A-F0-9]{64}$")
WIRE_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
DEPTH_PROFILE_FIELDS = frozenset(
    {
        "schema_version",
        "profile_id",
        "target_skill_id",
        "integration_mode",
        "native_owner_id",
        "native_route_ids",
        "native_check_ids",
        "native_route_absent_confirmed",
        "skillguard_adds_domain_route",
        "enforcement_level",
        "required_closure_profiles",
        "provider_runtime",
        "claim_boundary",
    }
)
DEPTH_CONTRIBUTION_RANGE_FIELDS = frozenset(
    {
        "range_id",
        "kind",
        "start",
        "end",
        "obligation_ids",
        "universe_id",
        "native_observation_locator",
    }
)
CONTENT_ROLES = frozenset(
    {
        "runtime_source",
        "contract_schema",
        "prompt_router",
        "fixture_reference",
        "test_dev",
        "documentation_model",
    }
)
INSTALL_DISPOSITIONS = frozenset({"copy", "source_only", "generate", "exclude"})
FULL_ADMISSION_REASON_CODES = frozenset(
    {
        "explicit_final_gate",
        "explicit_release_gate",
        "impact_policy_or_compiler_changed",
        "shared_validation_runtime_changed",
        "all_owner_component_changed",
    }
)
PLATFORM_BRIDGE_FLAGS = {
    "cmd": frozenset({"/c", "/k"}),
    "cmd.exe": frozenset({"/c", "/k"}),
    "powershell": frozenset({"-command", "-encodedcommand"}),
    "powershell.exe": frozenset({"-command", "-encodedcommand"}),
    "pwsh": frozenset({"-command", "-encodedcommand"}),
    "pwsh.exe": frozenset({"-command", "-encodedcommand"}),
    "bash": frozenset({"-c"}),
    "sh": frozenset({"-c"}),
}
BINDING_SOURCE_FIELDS = frozenset(
    {
        "artifacts",
        "checks",
        "claim_boundary",
        "closure_profiles",
        "confirmed",
        "content_impact_policy",
        "content_role_overrides",
        "depth_profile",
        "default_route_id",
        "implementation_paths",
        "integration_mode",
        "judgment_rubrics",
        "may_define_parallel_execution_route",
        "may_define_skillguard_runtime_route",
        "model_id",
        "model_path",
        "repository_role",
        "maintenance_unit_id",
        "member_skill_ids",
        "consumer_projection",
        "native_check_bindings",
        "native_route_bindings",
        "native_route_owner",
        "portfolio_capability_contracts",
        "portfolio_target_edges",
        "projection_consumers",
        "release_eligible",
        "route_branch_closure_required",
        "schema_version",
        "skill_id",
        "step_bindings",
        "supervision_fragment_refs",
    }
)
COMPILED_CONTRACT_FIELDS = frozenset(
    {
        "artifacts",
        "check_declarations_hash",
        "checks",
        "claim_boundary",
        "closure_profiles",
        "compiler_version",
        "content_impact_plan",
        "contract_hash",
        "depth_profile",
        "flowguard_schema_version",
        "functions",
        "judgment_rubrics",
        "model_id",
        "model_path",
        "repository_role",
        "maintenance_unit_id",
        "member_skill_ids",
        "consumer_projection",
        "obligations",
        "parent_model_id",
        "portfolio_capability_contracts",
        "route_branch_closure_required",
        "routes",
        "schema_version",
        "skill_id",
        "source_fingerprints",
        "steps",
        "supervision_fragments",
        "content_components",
    }
)
CHECK_MANIFEST_FIELDS = frozenset(
    {
        "check_declarations_hash",
        "checks",
        "claim_boundary",
        "compiler_version",
        "content_impact_plan",
        "contract_hash",
        "manifest_hash",
        "model_id",
        "maintenance_unit_id",
        "member_skill_ids",
        "consumer_projection",
        "schema_version",
        "skill_id",
        "source_fingerprints",
        "supervision_fragments",
        "content_components",
    }
)
SOURCE_CHECK_FIELDS = frozenset(
    {
        "args",
        "check_id",
        "command",
        "coverage_rationale",
        "coverage_scope",
        "covers_obligation_ids",
        "cwd_relative",
        "cwd_token",
        "depends_on_check_ids",
        "evidence_class",
        "evidence_domain_id",
        "execution_owner_id",
        "maintenance_unit_id",
        "member_skill_id",
        "evidence_subject_id",
        "environment",
        "expected",
        "input_selectors",
        "kind",
        "native_route_id",
        "semantic_check_id",
        "timeout_seconds",
        "target_input_role_ids",
        "applicable",
    }
)
COMPILED_CHECK_FIELDS = SOURCE_CHECK_FIELDS | frozenset(
    {
        "assertion_scope",
        "input_component_ids",
        "owner_declaration_hash",
        "owner_input_projection_hash",
        "projection_declaration_hash",
    }
)
OWNER_BEHAVIOR_FIELDS = (
    "maintenance_unit_id",
    "member_skill_id",
    "kind",
    "command",
    "args",
    "cwd_token",
    "cwd_relative",
    "environment",
    "expected",
    "timeout_seconds",
    "assertion_scope",
    "native_route_id",
    "applicable",
)


def _wire_hash(payload: object) -> str:
    encoded = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class SchemaFinding:
    code: str
    path: str
    message: str
    severity: str = "blocker"

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "path": self.path,
            "message": self.message,
            "severity": self.severity,
        }


class SchemaValidationError(ValueError):
    def __init__(self, findings: Sequence[SchemaFinding]):
        self.findings = tuple(findings)
        summary = "; ".join(f"{row.code}@{row.path}" for row in self.findings)
        super().__init__(summary or "schema validation failed")


def _finding(code: str, path: str, message: str) -> SchemaFinding:
    return SchemaFinding(code=code, path=path, message=message)


def _mapping(value: object, path: str, findings: list[SchemaFinding]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        findings.append(_finding("expected_object", path, "value must be an object"))
        return {}
    return value


def _rows(value: object, path: str, findings: list[SchemaFinding]) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        findings.append(_finding("expected_array", path, "value must be an array"))
        return []
    rows: list[Mapping[str, Any]] = []
    for index, item in enumerate(value):
        rows.append(_mapping(item, f"{path}[{index}]", findings))
    return rows


def _required_text(payload: Mapping[str, Any], key: str, path: str, findings: list[SchemaFinding]) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        findings.append(_finding("missing_required_text", f"{path}.{key}", "required non-empty string"))
        return ""
    return value


def _string_list(value: object, path: str, findings: list[SchemaFinding]) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        findings.append(_finding("expected_string_array", path, "value must be an array of non-empty strings"))
        return ()
    return tuple(value)


def _unique_ids(
    rows: Sequence[Mapping[str, Any]],
    key: str,
    path: str,
    findings: list[SchemaFinding],
) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    for row_index, row in enumerate(rows):
        value = _required_text(row, key, f"{path}[{row_index}]", findings)
        if value in index:
            findings.append(_finding("duplicate_id", f"{path}[{row_index}].{key}", f"duplicate id: {value}"))
        elif value:
            index[value] = row
    return index


def _route_cycles(routes: Mapping[str, Mapping[str, Any]]) -> tuple[tuple[str, ...], ...]:
    graph = {
        route_id: tuple(
            str(handoff.get("target_id"))
            for handoff in route.get("handoffs", [])
            if isinstance(handoff, Mapping)
            and handoff.get("target_kind") == "internal_route"
            and str(handoff.get("target_id")) in routes
        )
        for route_id, route in routes.items()
    }
    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    components: list[tuple[str, ...]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for target in graph[node]:
            if target not in indices:
                visit(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[target])
        if lowlinks[node] == indices[node]:
            component: list[str] = []
            while stack:
                member = stack.pop()
                on_stack.remove(member)
                component.append(member)
                if member == node:
                    break
            if len(component) > 1 or node in graph[node]:
                components.append(tuple(sorted(component)))

    for node in graph:
        if node not in indices:
            visit(node)
    return tuple(sorted(components))


def validate_model_export(payload: object) -> tuple[SchemaFinding, ...]:
    findings: list[SchemaFinding] = []
    root = _mapping(payload, "$", findings)
    if root.get("schema_version") != MODEL_EXPORT_SCHEMA:
        findings.append(_finding("unsupported_model_export_schema", "$.schema_version", MODEL_EXPORT_SCHEMA))
    flowguard_schema = _required_text(root, "flowguard_schema_version", "$", findings)
    if flowguard_schema and flowguard_schema not in SUPPORTED_FLOWGUARD_SCHEMA_VERSIONS:
        findings.append(
            _finding(
                "unsupported_flowguard_schema",
                "$.flowguard_schema_version",
                f"unsupported FlowGuard schema: {flowguard_schema}",
            )
        )
    _required_text(root, "model_id", "$", findings)
    _required_text(root, "parent_model_id", "$", findings)
    _required_text(root, "claim_boundary", "$", findings)

    function_rows = _rows(root.get("functions"), "$.functions", findings)
    route_rows = _rows(root.get("routes"), "$.routes", findings)
    step_rows = _rows(root.get("steps"), "$.steps", findings)
    obligation_rows = _rows(root.get("obligations"), "$.obligations", findings)
    function_index = _unique_ids(function_rows, "function_id", "$.functions", findings)
    route_index = _unique_ids(route_rows, "route_id", "$.routes", findings)
    step_index = _unique_ids(step_rows, "step_id", "$.steps", findings)
    obligation_index = _unique_ids(obligation_rows, "obligation_id", "$.obligations", findings)
    invariant_ids = set(_string_list(root.get("invariant_ids"), "$.invariant_ids", findings))

    for function_id, row in function_index.items():
        _required_text(row, "business_intent", f"$.functions[{function_id}]", findings)
        _required_text(row, "owner_id", f"$.functions[{function_id}]", findings)
        for route_id in _string_list(row.get("route_ids"), f"$.functions[{function_id}].route_ids", findings):
            if route_id not in route_index:
                findings.append(_finding("dangling_function_route", f"$.functions[{function_id}].route_ids", route_id))

    for route_id, row in route_index.items():
        function_id = _required_text(row, "function_id", f"$.routes[{route_id}]", findings)
        if function_id and function_id not in function_index:
            findings.append(_finding("dangling_route_function", f"$.routes[{route_id}].function_id", function_id))
        _required_text(row, "owner_id", f"$.routes[{route_id}]", findings)
        step_ids = _string_list(row.get("step_ids"), f"$.routes[{route_id}].step_ids", findings)
        for step_id in step_ids:
            if step_id not in step_index:
                findings.append(_finding("dangling_route_step", f"$.routes[{route_id}].step_ids", step_id))
        for key, terminal_kind in (
            ("success_terminal_step_id", "success"),
            ("blocked_terminal_step_id", "blocked"),
        ):
            terminal_id = _required_text(row, key, f"$.routes[{route_id}]", findings)
            terminal = step_index.get(terminal_id)
            if terminal_id and terminal is None:
                findings.append(_finding("uncovered_terminal", f"$.routes[{route_id}].{key}", terminal_id))
            elif terminal is not None and terminal.get("terminal_kind") != terminal_kind:
                findings.append(_finding("terminal_kind_mismatch", f"$.routes[{route_id}].{key}", terminal_id))
        handoffs = _rows(row.get("handoffs", []), f"$.routes[{route_id}].handoffs", findings)
        for handoff_index, handoff in enumerate(handoffs):
            handoff_path = f"$.routes[{route_id}].handoffs[{handoff_index}]"
            target_kind = _required_text(handoff, "target_kind", handoff_path, findings)
            target_id = _required_text(handoff, "target_id", handoff_path, findings)
            _required_text(handoff, "condition", handoff_path, findings)
            _required_text(handoff, "claim_scope", handoff_path, findings)
            if target_kind and target_kind not in TARGET_KINDS:
                findings.append(_finding("invalid_target_kind", f"{handoff_path}.target_kind", target_kind))
            if target_kind == "internal_route" and target_id not in route_index:
                findings.append(_finding("dangling_handoff", f"{handoff_path}.target_id", target_id))

    for step_id, row in step_index.items():
        route_id = _required_text(row, "route_id", f"$.steps[{step_id}]", findings)
        _required_text(row, "owner_id", f"$.steps[{step_id}]", findings)
        _required_text(row, "action_kind", f"$.steps[{step_id}]", findings)
        if route_id and route_id not in route_index:
            findings.append(_finding("dangling_step_route", f"$.steps[{step_id}].route_id", route_id))
        elif route_id and step_id not in route_index[route_id].get("step_ids", []):
            findings.append(_finding("step_not_owned_by_route", f"$.steps[{step_id}]", route_id))
        terminal_kind = row.get("terminal_kind", "")
        if terminal_kind not in TERMINAL_KINDS:
            findings.append(_finding("invalid_terminal_kind", f"$.steps[{step_id}].terminal_kind", str(terminal_kind)))
        for dependency_id in _string_list(
            row.get("prerequisite_step_ids", []),
            f"$.steps[{step_id}].prerequisite_step_ids",
            findings,
        ):
            if dependency_id not in step_index:
                findings.append(_finding("dangling_step_prerequisite", f"$.steps[{step_id}]", dependency_id))
            if dependency_id == step_id:
                findings.append(_finding("self_step_prerequisite", f"$.steps[{step_id}]", dependency_id))

    for obligation_id, row in obligation_index.items():
        if "conditional" in row and not isinstance(row.get("conditional"), bool):
            findings.append(
                _finding(
                    "obligation_conditional_flag_invalid",
                    f"$.obligations[{obligation_id}].conditional",
                    type(row.get("conditional")).__name__,
                )
            )
        invariant_id = _required_text(row, "invariant_id", f"$.obligations[{obligation_id}]", findings)
        if invariant_id and invariant_id not in invariant_ids:
            findings.append(_finding("dangling_obligation_invariant", f"$.obligations[{obligation_id}]", invariant_id))
        owner_steps = _string_list(
            row.get("owner_step_ids"),
            f"$.obligations[{obligation_id}].owner_step_ids",
            findings,
        )
        if not owner_steps:
            findings.append(_finding("obligation_without_owner_step", f"$.obligations[{obligation_id}]", obligation_id))
        for step_id in owner_steps:
            if step_id not in step_index:
                findings.append(_finding("dangling_obligation_step", f"$.obligations[{obligation_id}]", step_id))

    for component in _route_cycles(route_index):
        for route_id in component:
            policy = route_index[route_id].get("loop_policy")
            policy_path = f"$.routes[{route_id}].loop_policy"
            if not isinstance(policy, Mapping):
                findings.append(_finding("unbounded_route_cycle", policy_path, ",".join(component)))
                continue
            for key in ("progress_measure", "allowed_delta", "success_terminal_step_id", "blocked_terminal_step_id"):
                _required_text(policy, key, policy_path, findings)
            max_reentries = policy.get("max_reentries")
            if not isinstance(max_reentries, int) or max_reentries <= 0:
                findings.append(_finding("invalid_loop_bound", f"{policy_path}.max_reentries", str(max_reentries)))

    return tuple(findings)


def _validate_route_branch_closure_profiles(
    root: Mapping[str, Any],
    profiles: Sequence[Mapping[str, Any]],
    findings: list[SchemaFinding],
    *,
    compiled: bool,
    path: str,
) -> None:
    """Validate one monotonic requirement projection for every route/branch."""

    has_route_branch_contract = any(
        bool(row.get("route_branch_requirements")) for row in profiles
    )
    opt_in = root.get("route_branch_closure_required")
    if opt_in is not None and not isinstance(opt_in, bool):
        findings.append(
            _finding(
                "route_branch_closure_opt_in_invalid",
                "$.route_branch_closure_required",
                str(opt_in),
            )
        )
    conditional_obligation_ids = sorted(
        str(row.get("obligation_id", ""))
        for row in root.get("obligations", [])
        if isinstance(row, Mapping)
        and row.get("conditional") is True
        and str(row.get("obligation_id", ""))
    )
    conditional_semantics_declared = bool(conditional_obligation_ids)
    if (conditional_semantics_declared or has_route_branch_contract) and opt_in is not True:
        findings.append(
            _finding(
                (
                    "route_branch_closure_opt_in_missing"
                    if opt_in is None
                    else "route_branch_closure_opt_in_mismatch"
                ),
                "$.route_branch_closure_required",
                ",".join(conditional_obligation_ids) or "route_branch_requirements",
            )
        )
    if (conditional_semantics_declared or opt_in is True) and not has_route_branch_contract:
        findings.append(
            _finding(
                "conditional_obligation_branch_contract_missing",
                path,
                ",".join(conditional_obligation_ids) or "explicit-opt-in",
            )
        )
        return
    if not has_route_branch_contract:
        return
    profile_index = {
        str(row.get("profile_id", "")): row
        for row in profiles
        if str(row.get("profile_id", ""))
    }
    route_ids = {
        str(row.get("route_id", ""))
        for row in root.get("routes", [])
        if isinstance(row, Mapping)
    }
    obligation_rows = {
        str(row.get("obligation_id", "")): row
        for row in root.get("obligations", [])
        if isinstance(row, Mapping)
    }
    obligation_ids = set(obligation_rows)
    declared_check_ids = {
        str(check_id)
        for row in obligation_rows.values()
        for check_id in row.get("required_check_ids", [])
    }
    expected_pairs: set[tuple[str, str]] | None = None
    previous_active: dict[tuple[str, str], set[str]] = {}
    highest_projection: dict[
        tuple[str, str], tuple[set[str], set[str], set[str]]
    ] = {}

    for profile_id in CLOSURE_PROFILE_ORDER:
        profile = profile_index.get(profile_id, {})
        profile_path = f"{path}[{profile_id}]"
        if "route_branch_requirements" not in profile:
            findings.append(
                _finding(
                    "route_branch_requirement_missing",
                    f"{profile_path}.route_branch_requirements",
                    "every closure profile must carry the same route/branch universe",
                )
            )
            rows: tuple[Mapping[str, Any], ...] = ()
        else:
            rows = _rows(
                profile.get("route_branch_requirements"),
                f"{profile_path}.route_branch_requirements",
                findings,
            )
        base_requirements = set(
            _string_list(
                profile.get("required_obligation_ids", []),
                f"{profile_path}.required_obligation_ids",
                findings,
            )
        )
        current_pairs: set[tuple[str, str]] = set()
        current_active: dict[tuple[str, str], set[str]] = {}
        for row_index, row in enumerate(rows):
            row_path = f"{profile_path}.route_branch_requirements[{row_index}]"
            route_id = _required_text(row, "native_route_id", row_path, findings)
            if compiled and route_id and route_id not in route_ids:
                findings.append(
                    _finding(
                        "route_branch_native_route_unknown",
                        f"{row_path}.native_route_id",
                        route_id,
                    )
                )
            branch_ids = _string_list(
                row.get("branch_ids"), f"{row_path}.branch_ids", findings
            )
            if not branch_ids:
                findings.append(
                    _finding(
                        "route_branch_ids_empty",
                        f"{row_path}.branch_ids",
                        route_id,
                    )
                )
            if len(branch_ids) != len(set(branch_ids)):
                findings.append(
                    _finding(
                        "route_branch_ids_duplicate",
                        f"{row_path}.branch_ids",
                        route_id,
                    )
                )
            branch_requirements = set(
                _string_list(
                    row.get("required_obligation_ids"),
                    f"{row_path}.required_obligation_ids",
                    findings,
                )
            )
            if not branch_requirements:
                findings.append(
                    _finding(
                        "route_branch_obligations_empty",
                        f"{row_path}.required_obligation_ids",
                        route_id,
                    )
                )
            if compiled:
                for obligation_id in sorted(branch_requirements - obligation_ids):
                    findings.append(
                        _finding(
                            "route_branch_obligation_unknown",
                            f"{row_path}.required_obligation_ids",
                            obligation_id,
                        )
                    )
            applicability_rows = _rows(
                row.get("applicability_rules", []),
                f"{row_path}.applicability_rules",
                findings,
            )
            not_applicable_ids: set[str] = set()
            for rule_index, rule in enumerate(applicability_rows):
                rule_path = f"{row_path}.applicability_rules[{rule_index}]"
                obligation_id = _required_text(
                    rule, "obligation_id", rule_path, findings
                )
                disposition = _required_text(
                    rule, "allowed_disposition", rule_path, findings
                )
                verifier_check_id = _required_text(
                    rule, "verifier_check_id", rule_path, findings
                )
                if disposition != "not_applicable":
                    findings.append(
                        _finding(
                            "applicability_disposition_invalid",
                            f"{rule_path}.allowed_disposition",
                            disposition,
                        )
                    )
                if obligation_id in not_applicable_ids:
                    findings.append(
                        _finding(
                            "applicability_obligation_duplicate",
                            f"{rule_path}.obligation_id",
                            obligation_id,
                        )
                    )
                not_applicable_ids.add(obligation_id)
                if compiled and obligation_id not in obligation_ids:
                    findings.append(
                        _finding(
                            "applicability_obligation_unknown",
                            f"{rule_path}.obligation_id",
                            obligation_id,
                        )
                    )
                if compiled and verifier_check_id not in declared_check_ids:
                    findings.append(
                        _finding(
                            "applicability_verifier_check_unknown",
                            f"{rule_path}.verifier_check_id",
                            verifier_check_id,
                        )
                    )
            for obligation_id in sorted(branch_requirements & not_applicable_ids):
                findings.append(
                    _finding(
                        "route_branch_obligation_both_required_and_not_applicable",
                        row_path,
                        obligation_id,
                    )
                )
            for branch_id in branch_ids:
                pair = (route_id, branch_id)
                if pair in current_pairs:
                    findings.append(
                        _finding(
                            "route_branch_ownership_overlap",
                            f"{row_path}.branch_ids",
                            f"{route_id}:{branch_id}",
                        )
                    )
                    continue
                current_pairs.add(pair)
                active = (base_requirements | branch_requirements) - not_applicable_ids
                current_active[pair] = active
                if profile_id == "enforced":
                    highest_projection[pair] = (
                        active,
                        branch_requirements,
                        not_applicable_ids,
                    )

        if expected_pairs is None:
            expected_pairs = current_pairs
        elif current_pairs != expected_pairs:
            findings.append(
                _finding(
                    "route_branch_requirement_missing",
                    f"{profile_path}.route_branch_requirements",
                    f"missing={sorted(expected_pairs-current_pairs)};extra={sorted(current_pairs-expected_pairs)}",
                )
            )
        for pair in sorted((expected_pairs or set()) & current_pairs):
            if pair in previous_active and not previous_active[pair].issubset(
                current_active[pair]
            ):
                findings.append(
                    _finding(
                        "route_branch_profile_non_monotonic",
                        profile_path,
                        f"{pair[0]}:{pair[1]}",
                    )
                )
        previous_active = current_active

    conditional_ids = set(conditional_obligation_ids)
    conditional_active: dict[str, set[tuple[str, str]]] = {
        obligation_id: set() for obligation_id in conditional_ids
    }
    conditional_not_applicable: dict[str, set[tuple[str, str]]] = {
        obligation_id: set() for obligation_id in conditional_ids
    }
    for pair, (active, _branch_requirements, not_applicable) in sorted(
        highest_projection.items()
    ):
        missing_dispositions = conditional_ids - active - not_applicable
        for obligation_id in sorted(missing_dispositions):
            findings.append(
                _finding(
                    "conditional_obligation_branch_disposition_missing",
                    path,
                    f"{pair[0]}:{pair[1]}:{obligation_id}",
                )
            )
        for obligation_id in conditional_ids & active:
            conditional_active[obligation_id].add(pair)
        for obligation_id in conditional_ids & not_applicable:
            conditional_not_applicable[obligation_id].add(pair)
    for obligation_id in sorted(conditional_ids):
        if not conditional_active[obligation_id]:
            findings.append(
                _finding(
                    "conditional_obligation_never_applicable",
                    path,
                    obligation_id,
                )
            )
        if not conditional_not_applicable[obligation_id]:
            findings.append(
                _finding(
                    "conditional_obligation_never_not_applicable",
                    path,
                    obligation_id,
                )
            )
    depth_profile = root.get("depth_profile")
    has_not_applicable_branch = any(
        bool(not_applicable)
        for _active, _branch_requirements, not_applicable in highest_projection.values()
    )
    if has_not_applicable_branch and (
        not isinstance(depth_profile, Mapping)
        or "enforced"
        not in {
            str(item)
            for item in depth_profile.get("required_closure_profiles", [])
        }
    ):
        findings.append(
            _finding(
                "native_noop_depth_profile_missing_enforced",
                "$.depth_profile.required_closure_profiles",
                "enforced",
            )
        )

def _validate_content_impact_policy(
    value: object, path: str, findings: list[SchemaFinding]
) -> None:
    row = _mapping(value, path, findings)
    unknown = sorted(
        set(row)
        - {
            "policy_id",
            "owner_receipt_root_ref",
            "unknown_mapping_disposition",
            "full_admission_reason_codes",
        }
    )
    if unknown:
        findings.append(_finding("content_impact_policy_unknown_field", path, ",".join(unknown)))
    if row.get("policy_id") != CONTENT_IMPACT_POLICY_ID:
        findings.append(
            _finding(
                "content_impact_policy_id_invalid",
                f"{path}.policy_id",
                CONTENT_IMPACT_POLICY_ID,
            )
        )
    if row.get("owner_receipt_root_ref") != CONTENT_IMPACT_OWNER_ROOT:
        findings.append(
            _finding(
                "content_impact_owner_root_invalid",
                f"{path}.owner_receipt_root_ref",
                "owner_evidence_root/check-executions is required",
            )
        )
    if row.get("unknown_mapping_disposition") != "block":
        findings.append(
            _finding(
                "content_impact_unknown_mapping_fallback_forbidden",
                f"{path}.unknown_mapping_disposition",
                "block is required; run-all fallback is forbidden",
            )
        )
    reasons = _string_list(
        row.get("full_admission_reason_codes"),
        f"{path}.full_admission_reason_codes",
        findings,
    )
    if len(reasons) != len(set(reasons)) or set(reasons) != FULL_ADMISSION_REASON_CODES:
        findings.append(
            _finding(
                "content_impact_full_reasons_invalid",
                f"{path}.full_admission_reason_codes",
                "the exact current full-admission allowlist is required",
            )
        )


def _validate_input_selectors(
    value: object, path: str, findings: list[SchemaFinding]
) -> None:
    if not isinstance(value, list):
        findings.append(_finding("input_selectors_invalid", path, "value must be an array"))
        return
    if not value:
        findings.append(_finding("input_selectors_empty", path, "at least one selector is required"))
    for index, raw in enumerate(value):
        selector_path = f"{path}[{index}]"
        selector = _mapping(raw, selector_path, findings)
        kind = _required_text(selector, "kind", selector_path, findings)
        allowed_keys = {"kind", "path"} if kind in {"path", "subtree"} else {"kind", kind}
        unknown = sorted(set(selector) - allowed_keys)
        if unknown:
            findings.append(_finding("input_selector_unknown_field", selector_path, ",".join(unknown)))
        if kind in {"path", "subtree"}:
            selected = _required_text(selector, "path", selector_path, findings)
            if selected.startswith(("/", "\\")) or ".." in selected.replace("\\", "/").split("/"):
                findings.append(_finding("input_selector_path_invalid", f"{selector_path}.path", selected))
        elif kind == "role":
            role = _required_text(selector, "role", selector_path, findings)
            if role and role not in CONTENT_ROLES:
                findings.append(_finding("input_selector_role_invalid", f"{selector_path}.role", role))
        elif kind == "install_disposition":
            disposition = _required_text(
                selector, "install_disposition", selector_path, findings
            )
            if disposition and disposition not in INSTALL_DISPOSITIONS:
                findings.append(
                    _finding(
                        "input_selector_disposition_invalid",
                        f"{selector_path}.install_disposition",
                        disposition,
                    )
                )
        else:
            findings.append(_finding("input_selector_kind_invalid", f"{selector_path}.kind", kind))


def validate_binding_source(payload: object) -> tuple[SchemaFinding, ...]:
    findings: list[SchemaFinding] = []
    root = _mapping(payload, "$", findings)
    unknown_root_fields = sorted(set(root) - BINDING_SOURCE_FIELDS)
    if unknown_root_fields:
        findings.append(
            _finding(
                "binding_source_unknown_field",
                "$",
                ",".join(unknown_root_fields),
            )
        )
    if root.get("schema_version") != BINDING_SOURCE_SCHEMA:
        findings.append(_finding("unsupported_binding_schema", "$.schema_version", BINDING_SOURCE_SCHEMA))
    for key in (
        "skill_id",
        "model_id",
        "model_path",
        "claim_boundary",
        "repository_role",
        "maintenance_unit_id",
    ):
        _required_text(root, key, "$", findings)
    if root.get("repository_role") != "skill_maintainer_source":
        findings.append(
            _finding(
                "repository_role_not_author_source",
                "$.repository_role",
                "skill_maintainer_source is required",
            )
        )
    member_skill_ids = _string_list(
        root.get("member_skill_ids"), "$.member_skill_ids", findings
    )
    if (
        not member_skill_ids
        or len(member_skill_ids) != len(set(member_skill_ids))
        or root.get("skill_id") not in member_skill_ids
    ):
        findings.append(
            _finding(
                "member_skill_ids_invalid",
                "$.member_skill_ids",
                "must be unique, non-empty, and contain skill_id",
            )
        )
    consumer_projection = _mapping(
        root.get("consumer_projection"), "$.consumer_projection", findings
    )
    expected_consumer_fields = {
        "projection_id",
        "prohibited_path_prefixes",
        "prohibited_prompt_tokens",
        "release_manifest_path",
    }
    unknown_consumer_fields = sorted(
        set(consumer_projection) - expected_consumer_fields
    )
    if unknown_consumer_fields:
        findings.append(
            _finding(
                "consumer_projection_unknown_field",
                "$.consumer_projection",
                ",".join(unknown_consumer_fields),
            )
        )
    if (
        consumer_projection.get("projection_id")
        != "projection:consumer-distribution"
    ):
        findings.append(
            _finding(
                "consumer_projection_id_invalid",
                "$.consumer_projection.projection_id",
                "projection:consumer-distribution is required",
            )
        )
    prohibited_prefixes = _string_list(
        consumer_projection.get("prohibited_path_prefixes"),
        "$.consumer_projection.prohibited_path_prefixes",
        findings,
    )
    if ".skillguard/" not in prohibited_prefixes:
        findings.append(
            _finding(
                "consumer_projection_skillguard_prefix_missing",
                "$.consumer_projection.prohibited_path_prefixes",
                ".skillguard/ must be prohibited",
            )
        )
    prohibited_tokens = _string_list(
        consumer_projection.get("prohibited_prompt_tokens"),
        "$.consumer_projection.prohibited_prompt_tokens",
        findings,
    )
    if not {"SkillGuard", ".skillguard"}.issubset(set(prohibited_tokens)):
        findings.append(
            _finding(
                "consumer_projection_prompt_tokens_incomplete",
                "$.consumer_projection.prohibited_prompt_tokens",
                "SkillGuard and .skillguard must be prohibited",
            )
        )
    _required_text(
        consumer_projection,
        "release_manifest_path",
        "$.consumer_projection",
        findings,
    )
    if root.get("confirmed") is not True:
        findings.append(_finding("unconfirmed_binding_source", "$.confirmed", "release compilation requires confirmed=true"))
    if "implementation_paths" in root:
        _string_list(root.get("implementation_paths"), "$.implementation_paths", findings)
    fragment_refs = _rows(
        root.get("supervision_fragment_refs", []),
        "$.supervision_fragment_refs",
        findings,
    )
    fragment_ref_ids: set[str] = set()
    fragment_ref_fields = {
        "fragment_id",
        "revision",
        "fragment_digest",
        "slot_bindings",
    }
    for index, row in enumerate(fragment_refs):
        path = f"$.supervision_fragment_refs[{index}]"
        for key in sorted(set(row) - fragment_ref_fields):
            findings.append(
                _finding(
                    "fragment_reference_unknown_field",
                    f"{path}.{key}",
                    "supervision fragments cannot add domain fields or checks",
                )
            )
        fragment_id = _required_text(row, "fragment_id", path, findings)
        if fragment_id in fragment_ref_ids:
            findings.append(
                _finding(
                    "duplicate_fragment_reference",
                    f"{path}.fragment_id",
                    fragment_id,
                )
            )
        fragment_ref_ids.add(fragment_id)
        _required_text(row, "revision", path, findings)
        digest = _required_text(row, "fragment_digest", path, findings)
        if digest and not WIRE_SHA256_RE.fullmatch(digest):
            findings.append(
                _finding(
                    "fragment_digest_invalid",
                    f"{path}.fragment_digest",
                    digest,
                )
            )
        slot_bindings = _mapping(
            row.get("slot_bindings"),
            f"{path}.slot_bindings",
            findings,
        )
        if not slot_bindings:
            findings.append(
                _finding(
                    "fragment_slot_bindings_empty",
                    f"{path}.slot_bindings",
                    "at least one reviewed slot binding is required",
                )
            )
        for slot_id, target_ids in slot_bindings.items():
            if not isinstance(slot_id, str) or not slot_id:
                findings.append(
                    _finding(
                        "fragment_slot_id_invalid",
                        f"{path}.slot_bindings",
                        str(slot_id),
                    )
                )
                continue
            _string_list(
                target_ids,
                f"{path}.slot_bindings.{slot_id}",
                findings,
            )
    if "content_impact_policy" in root:
        _validate_content_impact_policy(
            root.get("content_impact_policy"), "$.content_impact_policy", findings
        )
    if "content_role_overrides" in root:
        _rows(root.get("content_role_overrides"), "$.content_role_overrides", findings)
    if "projection_consumers" in root:
        consumers = _rows(root.get("projection_consumers"), "$.projection_consumers", findings)
        _unique_ids(consumers, "consumer_id", "$.projection_consumers", findings)
        for index, consumer in enumerate(consumers):
            _required_text(consumer, "kind", f"$.projection_consumers[{index}]", findings)
            _validate_input_selectors(
                consumer.get("input_selectors"),
                f"$.projection_consumers[{index}].input_selectors",
                findings,
            )
    if "portfolio_target_edges" in root:
        edges = _rows(
            root.get("portfolio_target_edges"),
            "$.portfolio_target_edges",
            findings,
        )
        _unique_ids(edges, "target_id", "$.portfolio_target_edges", findings)
        for index, edge in enumerate(edges):
            edge_path = f"$.portfolio_target_edges[{index}]"
            unknown = sorted(
                set(edge) - {"target_id", "input_selectors", "member_ids"}
            )
            if unknown:
                findings.append(
                    _finding(
                        "portfolio_target_edge_unknown_field",
                        edge_path,
                        ",".join(unknown),
                    )
                )
            _validate_input_selectors(
                edge.get("input_selectors"),
                f"{edge_path}.input_selectors",
                findings,
            )
            if "member_ids" in edge:
                member_ids = _string_list(
                    edge.get("member_ids"),
                    f"{edge_path}.member_ids",
                    findings,
                )
                if len(member_ids) != len(set(member_ids)):
                    findings.append(
                        _finding(
                            "portfolio_target_edge_member_duplicate",
                            f"{edge_path}.member_ids",
                            str(edge.get("target_id", "")),
                        )
                    )
    if "depth_profile" in root:
        findings.extend(validate_depth_profile(root.get("depth_profile"), path="$.depth_profile"))
    step_bindings = _rows(root.get("step_bindings"), "$.step_bindings", findings)
    checks = _rows(root.get("checks"), "$.checks", findings)
    artifacts = _rows(root.get("artifacts"), "$.artifacts", findings)
    profiles = _rows(root.get("closure_profiles"), "$.closure_profiles", findings)
    _unique_ids(step_bindings, "step_id", "$.step_bindings", findings)
    _unique_ids(checks, "check_id", "$.checks", findings)
    _unique_ids(artifacts, "artifact_id", "$.artifacts", findings)
    _capability_contracts, capability_findings = (
        normalize_portfolio_capability_contracts(
            root.get("portfolio_capability_contracts")
        )
    )
    findings.extend(
        _finding(row.code, row.path, row.message) for row in capability_findings
    )
    profile_index = _unique_ids(profiles, "profile_id", "$.closure_profiles", findings)
    for index, row in enumerate(step_bindings):
        action = _mapping(row.get("action"), f"$.step_bindings[{index}].action", findings)
        _required_text(action, "kind", f"$.step_bindings[{index}].action", findings)
        _string_list(row.get("check_ids"), f"$.step_bindings[{index}].check_ids", findings)
        _string_list(row.get("output_artifact_ids", []), f"$.step_bindings[{index}].output_artifact_ids", findings)
    for index, row in enumerate(checks):
        unknown_check_fields = sorted(set(row) - SOURCE_CHECK_FIELDS)
        if unknown_check_fields:
            findings.append(
                _finding(
                    "check_behavior_field_unknown",
                    f"$.checks[{index}]",
                    ",".join(unknown_check_fields),
                )
            )
        check_path = f"$.checks[{index}]"
        _required_text(row, "kind", check_path, findings)
        for identity_field in (
            "semantic_check_id",
            "maintenance_unit_id",
            "member_skill_id",
            "evidence_subject_id",
        ):
            _required_text(row, identity_field, check_path, findings)
        if "execution_owner_id" in row:
            _required_text(row, "execution_owner_id", check_path, findings)
        if row.get("maintenance_unit_id") != root.get("maintenance_unit_id"):
            findings.append(
                _finding(
                    "check_maintenance_unit_mismatch",
                    f"{check_path}.maintenance_unit_id",
                    str(row.get("maintenance_unit_id", "")),
                )
            )
        if row.get("member_skill_id") not in set(member_skill_ids):
            findings.append(
                _finding(
                    "check_member_skill_unknown",
                    f"{check_path}.member_skill_id",
                    str(row.get("member_skill_id", "")),
                )
            )
        evidence_class = _required_text(row, "evidence_class", f"$.checks[{index}]", findings)
        if evidence_class and evidence_class not in EVIDENCE_CLASSES:
            findings.append(_finding("invalid_evidence_class", f"$.checks[{index}].evidence_class", evidence_class))
        _string_list(row.get("covers_obligation_ids"), f"$.checks[{index}].covers_obligation_ids", findings)
        command = row.get("command")
        args = row.get("args", [])
        if isinstance(command, str) and isinstance(args, list):
            executable = command.replace("\\", "/").rsplit("/", 1)[-1].lower()
            forbidden_flags = PLATFORM_BRIDGE_FLAGS.get(
                executable, frozenset()
            )
            if any(
                isinstance(item, str) and item.lower() in forbidden_flags
                for item in args
            ):
                findings.append(
                    _finding(
                        "platform_bridge_must_use_launch_resolver",
                        f"$.checks[{index}]",
                        (
                            "declare the target program and arguments directly; "
                            "platform shell bridges belong to runtime launch planning"
                        ),
                    )
                )
        if "input_selectors" in row:
            _validate_input_selectors(
                row.get("input_selectors"),
                f"$.checks[{index}].input_selectors",
                findings,
            )
        if "depends_on_check_ids" in row:
            dependencies = _string_list(
                row.get("depends_on_check_ids"),
                f"$.checks[{index}].depends_on_check_ids",
                findings,
            )
            if len(dependencies) != len(set(dependencies)):
                findings.append(
                    _finding(
                        "check_dependency_duplicate",
                        f"$.checks[{index}].depends_on_check_ids",
                        str(row.get("check_id", "")),
                    )
                )
        if "target_input_role_ids" in row:
            roles = _string_list(
                row.get("target_input_role_ids"),
                f"$.checks[{index}].target_input_role_ids",
                findings,
            )
            if len(roles) != len(set(roles)):
                findings.append(
                    _finding(
                        "target_input_role_duplicate",
                        f"$.checks[{index}].target_input_role_ids",
                        str(row.get("check_id", "")),
                    )
                )
        if "evidence_domain_id" in row:
            _required_text(row, "evidence_domain_id", f"$.checks[{index}]", findings)
    for index, row in enumerate(artifacts):
        _required_text(row, "kind", f"$.artifacts[{index}]", findings)
        _required_text(row, "producer_step_id", f"$.artifacts[{index}]", findings)
        _string_list(row.get("validators"), f"$.artifacts[{index}].validators", findings)
    profile_ids = tuple(profile for profile in CLOSURE_PROFILE_ORDER if profile in profile_index)
    if profile_ids != CLOSURE_PROFILE_ORDER or set(profile_index) != set(CLOSURE_PROFILE_ORDER):
        findings.append(
            _finding(
                "closure_profiles_incomplete",
                "$.closure_profiles",
                f"exact required profiles: {', '.join(CLOSURE_PROFILE_ORDER)}",
            )
        )
    _validate_route_branch_closure_profiles(
        root,
        profiles,
        findings,
        compiled=False,
        path="$.closure_profiles",
    )
    return tuple(findings)


def validate_depth_profile(payload: object, *, path: str = "$") -> tuple[SchemaFinding, ...]:
    """Validate the sole current, target-neutral declared-check profile."""

    findings: list[SchemaFinding] = []
    root = _mapping(payload, path, findings)
    unknown = sorted(set(root) - DEPTH_PROFILE_FIELDS)
    if unknown:
        findings.append(_finding("depth_profile_unknown_field", path, ",".join(unknown)))
    if root.get("schema_version") != DEPTH_PROFILE_SCHEMA:
        findings.append(
            _finding(
                "depth_profile_schema_mismatch",
                f"{path}.schema_version",
                DEPTH_PROFILE_SCHEMA,
            )
        )
    for key in (
        "profile_id",
        "target_skill_id",
        "native_owner_id",
        "integration_mode",
        "enforcement_level",
        "claim_boundary",
    ):
        _required_text(root, key, path, findings)
    integration_mode = str(root.get("integration_mode", ""))
    if integration_mode not in DEPTH_INTEGRATION_MODES:
        findings.append(
            _finding(
                "depth_integration_mode_invalid",
                f"{path}.integration_mode",
                integration_mode,
            )
        )
    if root.get("enforcement_level") != "enforced":
        findings.append(
            _finding(
                "depth_enforcement_level_invalid",
                f"{path}.enforcement_level",
                "the sole current behavior is enforced declared-check supervision",
            )
        )
    route_ids = _string_list(root.get("native_route_ids"), f"{path}.native_route_ids", findings)
    check_ids = _string_list(root.get("native_check_ids"), f"{path}.native_check_ids", findings)
    if len(route_ids) != len(set(route_ids)):
        findings.append(_finding("depth_native_route_duplicate", f"{path}.native_route_ids", "route ids must be unique"))
    if len(check_ids) != len(set(check_ids)) or not check_ids:
        findings.append(_finding("depth_native_check_inventory_invalid", f"{path}.native_check_ids", "a non-empty unique declared-check inventory is required"))
    if integration_mode == "native-integrated" and not route_ids:
        findings.append(_finding("depth_native_route_missing", f"{path}.native_route_ids", "the target-native route must remain declared"))
    if root.get("skillguard_adds_domain_route") is not False:
        findings.append(_finding("depth_parallel_domain_route", f"{path}.skillguard_adds_domain_route", "SkillGuard cannot add a target-domain evaluator"))

    required_profiles = _string_list(
        root.get("required_closure_profiles"),
        f"{path}.required_closure_profiles",
        findings,
    )
    if tuple(required_profiles) != CLOSURE_PROFILE_ORDER:
        findings.append(
            _finding(
                "depth_required_closure_profile_invalid",
                f"{path}.required_closure_profiles",
                "the sole current closure profile is enforced",
            )
        )

    provider = _mapping(root.get("provider_runtime"), f"{path}.provider_runtime", findings)
    _required_text(provider, "provider_id", f"{path}.provider_runtime", findings)
    _required_text(provider, "required_runtime_contract_id", f"{path}.provider_runtime", findings)
    capabilities = _string_list(provider.get("required_capability_ids"), f"{path}.provider_runtime.required_capability_ids", findings)
    if not capabilities:
        findings.append(_finding("depth_runtime_capabilities_missing", f"{path}.provider_runtime.required_capability_ids", "at least one generic runtime capability is required"))
    readiness_ids = _string_list(provider.get("readiness_check_ids"), f"{path}.provider_runtime.readiness_check_ids", findings)
    if not readiness_ids:
        findings.append(_finding("depth_runtime_readiness_checks_missing", f"{path}.provider_runtime.readiness_check_ids", "at least one current readiness check is required"))
    for check_id in sorted(set(readiness_ids) - set(check_ids)):
        findings.append(_finding("depth_runtime_readiness_check_not_native", f"{path}.provider_runtime.readiness_check_ids", check_id))
    if provider.get("required_enrollment_status") != "enrolled":
        findings.append(_finding("depth_runtime_enrollment_requirement_invalid", f"{path}.provider_runtime.required_enrollment_status", "enrolled is required"))
    return tuple(findings)


RUNTIME_REQUIRED_FIELDS: Mapping[str, tuple[str, ...]] = {
    RUN_SCHEMA: (
        "run_id",
        "skill_id",
        "maintenance_unit_id",
        "member_skill_id",
        "contract_hash",
        "check_manifest_hash",
        "check_declarations_hash",
        "route_ids",
        "claim_scope",
        "status",
    ),
    EVENT_SCHEMA: ("event_id", "run_id", "sequence", "event_type", "created_at", "payload_hash"),
    ARTIFACT_SCHEMA: ("artifact_id", "run_id", "kind", "producer_step_id", "fingerprint", "status"),
    RECEIPT_SCHEMA: (
        "receipt_id",
        "run_id",
        "maintenance_unit_id",
        "member_skill_id",
        "evidence_subject_id",
        "semantic_check_id",
        "step_id",
        "evidence_class",
        "status",
        "input_fingerprints",
    ),
    CLOSURE_SCHEMA: (
        "closure_receipt_id",
        "run_id",
        "profile",
        "status",
        "consumed_receipt_ids",
        "root_role_bindings_hash",
        "native_terminal_result",
        "applicability_results",
        "safe_claim",
    ),
    TARGET_NATIVE_DEPTH_EVIDENCE_SCHEMA: (
        "run_id",
        "target_skill_id",
        "target_contract_hash",
        "depth_profile_hash",
        "request_fingerprint",
        "target_input_fingerprint",
        "native_owner_id",
        "native_route_id",
        "native_check_id",
        "target_obligation_ids",
        "evidence_domain",
        "scheduled_production_identity",
        "native_receipt_id",
        "native_receipt_hash",
        "native_receipt_artifact_ref",
        "native_receipt_created_at",
        "universes",
        "depth_contribution_ranges",
        "evidence_payload_hash",
    ),
    TARGET_EXECUTION_RECEIPT_SCHEMA: (
        "receipt_id",
        "sequence",
        "receipt_hash",
        "run_id",
        "target_skill_id",
        "contract_hash",
        "profile_id",
        "profile_fingerprint",
        "integration_mode",
        "native_owner_id",
        "native_route_ids",
        "native_check_ids",
        "request_fingerprint",
        "declared_check_inventory",
        "declared_check_results",
        "unresolved_check_ids",
        "evidence_domain",
        "scheduled_production_identity",
        "status",
        "enforcement_decision",
        "dimension_results",
        "coverage_universe_results",
        "obligation_results",
        "evidence_contributions",
        "provider_runtime_audit",
        "observation_binding",
        "root_role_bindings",
        "root_role_bindings_hash",
        "uncovered_obligation_ids",
        "blockers",
        "active_runtime_identity",
        "active_runtime_identity_hash",
        "input_fingerprints",
        "input_fingerprint_hash",
        "target_fingerprint",
        "runtime_fingerprint",
        "evaluation_hash",
        "supersedes_receipt_id",
        "claim_boundary",
        "created_at",
    ),
}

STRICT_RUNTIME_FIELDS: Mapping[str, frozenset[str]] = {
    schema: frozenset(("schema_version", *RUNTIME_REQUIRED_FIELDS[schema]))
    for schema in (
        TARGET_NATIVE_DEPTH_EVIDENCE_SCHEMA,
        TARGET_EXECUTION_RECEIPT_SCHEMA,
    )
}


def validate_runtime_payload(payload: object, expected_schema: str) -> tuple[SchemaFinding, ...]:
    findings: list[SchemaFinding] = []
    root = _mapping(payload, "$", findings)
    if expected_schema not in RUNTIME_REQUIRED_FIELDS:
        return (_finding("unknown_runtime_schema", "$.schema_version", expected_schema),)
    if root.get("schema_version") != expected_schema:
        findings.append(_finding("runtime_schema_mismatch", "$.schema_version", expected_schema))
    allowed_fields = STRICT_RUNTIME_FIELDS.get(expected_schema)
    if allowed_fields is not None:
        unknown_fields = sorted(set(root) - allowed_fields)
        if unknown_fields:
            findings.append(
                _finding(
                    "runtime_unknown_field",
                    "$",
                    ",".join(unknown_fields),
                )
            )
    for key in RUNTIME_REQUIRED_FIELDS[expected_schema]:
        if key not in root:
            findings.append(_finding("runtime_required_field_missing", f"$.{key}", key))
    if expected_schema == TARGET_NATIVE_DEPTH_EVIDENCE_SCHEMA:
        request_fingerprint = str(root.get("request_fingerprint", ""))
        if SHA256_RE.fullmatch(request_fingerprint) is None:
            findings.append(_finding("native_depth_request_fingerprint_invalid", "$.request_fingerprint", request_fingerprint))
        ranges = _rows(root.get("depth_contribution_ranges"), "$.depth_contribution_ranges", findings)
        if not ranges:
            findings.append(_finding("native_depth_contribution_missing", "$.depth_contribution_ranges", "at least one target-owned observation range is required"))
        for index, row in enumerate(ranges):
            row_path = f"$.depth_contribution_ranges[{index}]"
            unknown = sorted(set(row) - DEPTH_CONTRIBUTION_RANGE_FIELDS)
            if unknown:
                findings.append(_finding("depth_contribution_range_unknown_field", row_path, ",".join(unknown)))
            _required_text(row, "range_id", row_path, findings)
            if row.get("kind") not in DEPTH_CONTRIBUTION_RANGE_KINDS:
                findings.append(_finding("depth_contribution_range_kind_invalid", f"{row_path}.kind", str(row.get("kind", ""))))
            obligations = _string_list(row.get("obligation_ids"), f"{row_path}.obligation_ids", findings)
            if not obligations or len(obligations) != len(set(obligations)):
                findings.append(_finding("depth_contribution_obligations_invalid", f"{row_path}.obligation_ids", "non-empty unique obligations required"))
            locator = _mapping(row.get("native_observation_locator"), f"{row_path}.native_observation_locator", findings)
            locator_fields = {
                "schema_version",
                "locator_type",
                "resolver_owner_id",
                "native_object_id",
                "native_coordinate",
                "content_sha256",
                "locator_fingerprint",
            }
            locator_unknown = sorted(set(locator) - locator_fields)
            if locator_unknown:
                findings.append(_finding("native_observation_locator_unknown_field", f"{row_path}.native_observation_locator", ",".join(locator_unknown)))
            if locator.get("schema_version") != "skillguard.native_observation_locator.current":
                findings.append(_finding("native_observation_locator_schema_mismatch", f"{row_path}.native_observation_locator.schema_version", str(locator.get("schema_version", ""))))
    elif expected_schema == TARGET_EXECUTION_RECEIPT_SCHEMA:
        request_fingerprint = str(root.get("request_fingerprint", ""))
        if SHA256_RE.fullmatch(request_fingerprint) is None:
            findings.append(_finding("target_receipt_request_fingerprint_invalid", "$.request_fingerprint", request_fingerprint))
        inventory = _mapping(root.get("declared_check_inventory"), "$.declared_check_inventory", findings)
        if inventory.get("schema_version") != "skillguard.declared_check_inventory.current":
            findings.append(_finding("declared_check_inventory_schema_invalid", "$.declared_check_inventory.schema_version", str(inventory.get("schema_version", ""))))
        _rows(root.get("declared_check_results"), "$.declared_check_results", findings)
        _string_list(root.get("unresolved_check_ids"), "$.unresolved_check_ids", findings)
    return tuple(findings)


def _require_wire_hash(
    row: Mapping[str, Any], key: str, path: str, findings: list[SchemaFinding]
) -> str:
    value = _required_text(row, key, path, findings)
    if value and WIRE_SHA256_RE.fullmatch(value) is None:
        findings.append(_finding("content_hash_wire_shape_invalid", f"{path}.{key}", value))
    return value


def _validate_content_impact_plan(
    payload: object,
    checks_value: object,
    *,
    path: str,
    findings: list[SchemaFinding],
) -> None:
    plan = _mapping(payload, path, findings)
    allowed_plan_fields = {
        "schema_version",
        "member_root_path",
        "policy_id",
        "owner_receipt_root_ref",
        "unknown_mapping_disposition",
        "full_admission_reason_codes",
        "inventory",
        "inventory_hash",
        "components",
        "owners",
        "check_projections",
        "projection_consumers",
        "portfolio_target_edges",
        "all_owner_component_ids",
        "health",
        "impact_graph_hash",
    }
    unknown = sorted(set(plan) - allowed_plan_fields)
    if unknown:
        findings.append(_finding("content_impact_plan_unknown_field", path, ",".join(unknown)))
    if plan.get("schema_version") != CONTENT_IMPACT_PLAN_SCHEMA:
        findings.append(
            _finding(
                "content_impact_plan_schema_invalid",
                f"{path}.schema_version",
                CONTENT_IMPACT_PLAN_SCHEMA,
            )
        )
    member_root_path = _required_text(
        plan, "member_root_path", path, findings
    ).replace("\\", "/")
    if member_root_path != "." and (
        member_root_path.startswith("/")
        or ":/" in member_root_path
        or any(part in {"", ".", ".."} for part in member_root_path.split("/"))
    ):
        findings.append(
            _finding(
                "content_impact_member_root_path_invalid",
                f"{path}.member_root_path",
                member_root_path,
            )
        )
    if plan.get("policy_id") != CONTENT_IMPACT_POLICY_ID:
        findings.append(
            _finding(
                "content_impact_plan_policy_invalid",
                f"{path}.policy_id",
                CONTENT_IMPACT_POLICY_ID,
            )
        )
    if plan.get("owner_receipt_root_ref") != CONTENT_IMPACT_OWNER_ROOT:
        findings.append(
            _finding(
                "content_impact_plan_owner_root_invalid",
                f"{path}.owner_receipt_root_ref",
                "owner_evidence_root/check-executions is required",
            )
        )
    if plan.get("unknown_mapping_disposition") != "block":
        findings.append(
            _finding(
                "content_impact_plan_fallback_forbidden",
                f"{path}.unknown_mapping_disposition",
                "block is required",
            )
        )
    full_reasons = _string_list(
        plan.get("full_admission_reason_codes"),
        f"{path}.full_admission_reason_codes",
        findings,
    )
    if len(full_reasons) != len(set(full_reasons)) or set(full_reasons) != FULL_ADMISSION_REASON_CODES:
        findings.append(
            _finding(
                "content_impact_plan_full_reasons_invalid",
                f"{path}.full_admission_reason_codes",
                "the exact current allowlist is required",
            )
        )

    inventory = _rows(plan.get("inventory"), f"{path}.inventory", findings)
    inventory_index = _unique_ids(inventory, "path", f"{path}.inventory", findings)
    for inventory_path, row in inventory_index.items():
        row_path = f"{path}.inventory[{inventory_path}]"
        unknown_row = sorted(
            set(row)
            - {
                "path",
                "content_hash",
                "role",
                "install_disposition",
                "classification_rule_id",
            }
        )
        if unknown_row:
            findings.append(_finding("content_inventory_unknown_field", row_path, ",".join(unknown_row)))
        _require_wire_hash(row, "content_hash", row_path, findings)
        role = _required_text(row, "role", row_path, findings)
        if role and role not in CONTENT_ROLES:
            findings.append(_finding("content_inventory_role_invalid", f"{row_path}.role", role))
        disposition = _required_text(row, "install_disposition", row_path, findings)
        if disposition and disposition not in INSTALL_DISPOSITIONS:
            findings.append(
                _finding(
                    "content_inventory_disposition_invalid",
                    f"{row_path}.install_disposition",
                    disposition,
                )
            )
        _required_text(row, "classification_rule_id", row_path, findings)
    inventory_hash = _require_wire_hash(plan, "inventory_hash", path, findings)
    if inventory_hash and inventory_hash != _wire_hash(inventory):
        findings.append(
            _finding(
                "content_inventory_hash_mismatch",
                f"{path}.inventory_hash",
                "inventory hash does not match current rows",
            )
        )

    components = _rows(plan.get("components"), f"{path}.components", findings)
    component_index = _unique_ids(
        components, "component_id", f"{path}.components", findings
    )
    component_owner_by_path: dict[str, str] = {}
    for component_id, row in component_index.items():
        row_path = f"{path}.components[{component_id}]"
        unknown_row = sorted(
            set(row)
            - {
                "component_id",
                "role",
                "install_disposition",
                "member_paths",
                "component_hash",
                "consumer_ids",
                "classification_rule_ids",
            }
        )
        if unknown_row:
            findings.append(_finding("content_component_unknown_field", row_path, ",".join(unknown_row)))
        role = _required_text(row, "role", row_path, findings)
        disposition = _required_text(row, "install_disposition", row_path, findings)
        member_paths = _string_list(row.get("member_paths"), f"{row_path}.member_paths", findings)
        consumer_ids = _string_list(row.get("consumer_ids"), f"{row_path}.consumer_ids", findings)
        _string_list(
            row.get("classification_rule_ids"),
            f"{row_path}.classification_rule_ids",
            findings,
        )
        if len(member_paths) != len(set(member_paths)) or not member_paths:
            findings.append(_finding("content_component_members_invalid", f"{row_path}.member_paths", component_id))
        if len(consumer_ids) != len(set(consumer_ids)) or not consumer_ids:
            findings.append(_finding("content_component_consumers_invalid", f"{row_path}.consumer_ids", component_id))
        for member_path in member_paths:
            if member_path not in inventory_index:
                findings.append(_finding("content_component_member_unknown", f"{row_path}.member_paths", member_path))
            if member_path in component_owner_by_path:
                findings.append(
                    _finding(
                        "content_component_member_duplicate",
                        f"{row_path}.member_paths",
                        member_path,
                    )
                )
            component_owner_by_path[member_path] = component_id
        component_hash = _require_wire_hash(row, "component_hash", row_path, findings)
        if member_paths and all(member in inventory_index for member in member_paths):
            expected_component_hash = _wire_hash(
                [
                    {
                        "path": member,
                        "content_hash": inventory_index[member]["content_hash"],
                    }
                    for member in member_paths
                ]
            )
            if component_hash and component_hash != expected_component_hash:
                findings.append(
                    _finding(
                        "content_component_hash_mismatch",
                        f"{row_path}.component_hash",
                        component_id,
                    )
                )
        if role and role not in CONTENT_ROLES:
            findings.append(_finding("content_component_role_invalid", f"{row_path}.role", role))
        if disposition and disposition not in INSTALL_DISPOSITIONS:
            findings.append(
                _finding(
                    "content_component_disposition_invalid",
                    f"{row_path}.install_disposition",
                    disposition,
                )
            )
    missing_component_members = sorted(set(inventory_index) - set(component_owner_by_path))
    if missing_component_members:
        findings.append(
            _finding(
                "content_inventory_not_componentized",
                f"{path}.components",
                ",".join(missing_component_members),
            )
        )

    checks = _rows(checks_value, "$.checks", findings)
    check_index = _unique_ids(checks, "check_id", "$.checks", findings)
    owners = _rows(plan.get("owners"), f"{path}.owners", findings)
    owner_index = _unique_ids(
        owners, "execution_owner_id", f"{path}.owners", findings
    )
    for owner_id, row in owner_index.items():
        row_path = f"{path}.owners[{owner_id}]"
        unknown_row = sorted(
            set(row)
            - {
                "execution_owner_id",
                "check_ids",
                "owner_declaration_hash",
                "input_selectors",
                "input_component_ids",
                "owner_input_projection_hash",
                "depends_on_owner_ids",
                "target_input_role_ids",
            }
        )
        if unknown_row:
            findings.append(_finding("content_owner_unknown_field", row_path, ",".join(unknown_row)))
        check_ids = _string_list(row.get("check_ids"), f"{row_path}.check_ids", findings)
        component_ids = _string_list(
            row.get("input_component_ids"), f"{row_path}.input_component_ids", findings
        )
        dependencies = _string_list(
            row.get("depends_on_owner_ids"), f"{row_path}.depends_on_owner_ids", findings
        )
        target_input_role_ids = _string_list(
            row.get("target_input_role_ids"),
            f"{row_path}.target_input_role_ids",
            findings,
        )
        if len(target_input_role_ids) != len(set(target_input_role_ids)):
            findings.append(
                _finding(
                    "content_owner_target_input_role_duplicate",
                    f"{row_path}.target_input_role_ids",
                    owner_id,
                )
            )
        _validate_input_selectors(row.get("input_selectors"), f"{row_path}.input_selectors", findings)
        owner_declaration_hash = _require_wire_hash(
            row, "owner_declaration_hash", row_path, findings
        )
        projection_hash = _require_wire_hash(
            row, "owner_input_projection_hash", row_path, findings
        )
        for check_id in check_ids:
            if check_id not in check_index:
                findings.append(_finding("content_owner_check_unknown", f"{row_path}.check_ids", check_id))
        for component_id in component_ids:
            if component_id not in component_index:
                findings.append(
                    _finding(
                        "content_owner_component_unknown",
                        f"{row_path}.input_component_ids",
                        component_id,
                    )
                )
        for dependency in dependencies:
            if dependency not in owner_index or dependency == owner_id:
                findings.append(
                    _finding(
                        "content_owner_dependency_invalid",
                        f"{row_path}.depends_on_owner_ids",
                        dependency,
                    )
                )
        if component_ids and all(component_id in component_index for component_id in component_ids):
            expected_projection_hash = _wire_hash(
                [
                    {
                        "component_id": component_id,
                        "component_hash": component_index[component_id]["component_hash"],
                    }
                    for component_id in component_ids
                ]
            )
            if projection_hash and projection_hash != expected_projection_hash:
                findings.append(
                    _finding(
                        "content_owner_projection_hash_mismatch",
                        f"{row_path}.owner_input_projection_hash",
                        owner_id,
                    )
                )
        for check_id in check_ids:
            check = check_index.get(check_id, {})
            declaration = {
                "behavior": {
                    key: check[key] for key in OWNER_BEHAVIOR_FIELDS if key in check
                },
                "input_selectors": list(check.get("input_selectors", [])),
                "target_input_role_ids": list(
                    check.get("target_input_role_ids", [])
                ),
                "impact_policy_id": str(plan.get("policy_id", "")),
            }
            expected_owner_hash = _wire_hash(declaration)
            if owner_declaration_hash and owner_declaration_hash != expected_owner_hash:
                findings.append(
                    _finding(
                        "content_owner_declaration_hash_mismatch",
                        f"{row_path}.owner_declaration_hash",
                        check_id,
                    )
                )

    projections = _rows(
        plan.get("check_projections"), f"{path}.check_projections", findings
    )
    projection_index = _unique_ids(
        projections, "check_id", f"{path}.check_projections", findings
    )
    if set(projection_index) != set(check_index):
        findings.append(
            _finding(
                "content_check_projection_set_mismatch",
                f"{path}.check_projections",
                "every check requires exactly one projection",
            )
        )
    for check_id, row in projection_index.items():
        row_path = f"{path}.check_projections[{check_id}]"
        projection_hash = _require_wire_hash(
            row, "projection_declaration_hash", row_path, findings
        )
        declaration = {
            "check_id": str(row.get("check_id", "")),
            "semantic_check_id": str(row.get("semantic_check_id", "")),
            "execution_owner_id": str(row.get("execution_owner_id", "")),
            "evidence_domain_id": str(row.get("evidence_domain_id", "")),
            "covers_obligation_ids": list(row.get("covers_obligation_ids", [])),
            "evidence_class": str(row.get("evidence_class", "")),
        }
        _required_text(row, "evidence_domain_id", row_path, findings)
        if projection_hash and projection_hash != _wire_hash(declaration):
            findings.append(
                _finding(
                    "content_check_projection_hash_mismatch",
                    f"{row_path}.projection_declaration_hash",
                    check_id,
                )
            )
        if declaration["execution_owner_id"] not in owner_index:
            findings.append(
                _finding(
                    "content_check_projection_owner_unknown",
                    f"{row_path}.execution_owner_id",
                    declaration["execution_owner_id"],
                )
            )

    consumers = _rows(
        plan.get("projection_consumers"), f"{path}.projection_consumers", findings
    )
    consumer_index = _unique_ids(
        consumers, "consumer_id", f"{path}.projection_consumers", findings
    )
    for consumer_id, row in consumer_index.items():
        row_path = f"{path}.projection_consumers[{consumer_id}]"
        unknown_row = sorted(
            set(row)
            - {
                "consumer_id",
                "kind",
                "impact_plan_schema_version",
                "impact_policy_id",
                "input_component_ids",
                "projection_declaration_hash",
                "input_projection_hash",
                "consumer_projection_hash",
            }
        )
        if unknown_row:
            findings.append(
                _finding(
                    "content_consumer_unknown_field",
                    row_path,
                    ",".join(unknown_row),
                )
            )
        projection_hash = _require_wire_hash(
            row, "projection_declaration_hash", row_path, findings
        )
        input_projection_hash = _require_wire_hash(
            row, "input_projection_hash", row_path, findings
        )
        consumer_projection_hash = _require_wire_hash(
            row, "consumer_projection_hash", row_path, findings
        )
        declaration = {
            "consumer_id": consumer_id,
            "kind": str(row.get("kind", "")),
            "impact_plan_schema_version": str(
                row.get("impact_plan_schema_version", "")
            ),
            "impact_policy_id": str(row.get("impact_policy_id", "")),
            "input_component_ids": list(row.get("input_component_ids", [])),
        }
        if declaration["impact_plan_schema_version"] != CONTENT_IMPACT_PLAN_SCHEMA:
            findings.append(
                _finding(
                    "content_consumer_plan_schema_mismatch",
                    f"{row_path}.impact_plan_schema_version",
                    declaration["impact_plan_schema_version"],
                )
            )
        if declaration["impact_policy_id"] != str(plan.get("policy_id", "")):
            findings.append(
                _finding(
                    "content_consumer_policy_mismatch",
                    f"{row_path}.impact_policy_id",
                    declaration["impact_policy_id"],
                )
            )
        if projection_hash and projection_hash != _wire_hash(declaration):
            findings.append(
                _finding(
                    "content_consumer_projection_hash_mismatch",
                    f"{row_path}.projection_declaration_hash",
                    consumer_id,
                )
            )
        expected_input_projection_hash = _wire_hash(
            [
                {
                    "component_id": component_id,
                    "component_hash": component_index[component_id][
                        "component_hash"
                    ],
                }
                for component_id in declaration["input_component_ids"]
                if component_id in component_index
            ]
        )
        if (
            input_projection_hash
            and all(
                component_id in component_index
                for component_id in declaration["input_component_ids"]
            )
            and input_projection_hash != expected_input_projection_hash
        ):
            findings.append(
                _finding(
                    "content_consumer_input_projection_hash_mismatch",
                    f"{row_path}.input_projection_hash",
                    consumer_id,
                )
            )
        expected_consumer_projection_hash = _wire_hash(
            {
                "projection_declaration_hash": projection_hash,
                "input_projection_hash": input_projection_hash,
            }
        )
        if (
            consumer_projection_hash
            and consumer_projection_hash != expected_consumer_projection_hash
        ):
            findings.append(
                _finding(
                    "content_consumer_identity_hash_mismatch",
                    f"{row_path}.consumer_projection_hash",
                    consumer_id,
                )
            )
        for component_id in declaration["input_component_ids"]:
            if component_id not in component_index:
                findings.append(
                    _finding(
                        "content_consumer_component_unknown",
                        f"{row_path}.input_component_ids",
                        str(component_id),
                    )
                )

    portfolio_edges = _rows(
        plan.get("portfolio_target_edges"),
        f"{path}.portfolio_target_edges",
        findings,
    )
    portfolio_edge_index = _unique_ids(
        portfolio_edges,
        "target_id",
        f"{path}.portfolio_target_edges",
        findings,
    )
    for target_id, row in portfolio_edge_index.items():
        row_path = f"{path}.portfolio_target_edges[{target_id}]"
        unknown_row = sorted(
            set(row) - {"target_id", "input_component_ids", "member_ids"}
        )
        if unknown_row:
            findings.append(
                _finding(
                    "content_portfolio_target_edge_unknown_field",
                    row_path,
                    ",".join(unknown_row),
                )
            )
        component_ids = _string_list(
            row.get("input_component_ids"),
            f"{row_path}.input_component_ids",
            findings,
        )
        member_ids = _string_list(
            row.get("member_ids"),
            f"{row_path}.member_ids",
            findings,
        )
        if (
            component_ids != tuple(sorted(set(component_ids)))
            or not component_ids
            or member_ids != tuple(sorted(set(member_ids)))
        ):
            findings.append(
                _finding(
                    "content_portfolio_target_edge_not_canonical",
                    row_path,
                    target_id,
                )
            )
        for component_id in component_ids:
            component = component_index.get(component_id)
            if component is None:
                findings.append(
                    _finding(
                        "content_portfolio_target_component_unknown",
                        f"{row_path}.input_component_ids",
                        component_id,
                    )
                )
            elif f"portfolio-target:{target_id}" not in set(
                component.get("consumer_ids", [])
            ):
                findings.append(
                    _finding(
                        "content_portfolio_target_component_binding_missing",
                        f"{row_path}.input_component_ids",
                        component_id,
                    )
                )

    all_owner_components = _string_list(
        plan.get("all_owner_component_ids"),
        f"{path}.all_owner_component_ids",
        findings,
    )
    for component_id in all_owner_components:
        if component_id not in component_index:
            findings.append(
                _finding(
                    "content_all_owner_component_unknown",
                    f"{path}.all_owner_component_ids",
                    component_id,
                )
            )

    health = _mapping(plan.get("health"), f"{path}.health", findings)
    required_health = {
        "unmapped_paths",
        "ambiguous_role_paths",
        "duplicate_owner_ids",
        "owner_cycles",
        "invalid_dependency_edges",
        "dependency_parse_errors",
    }
    if set(health) != required_health:
        findings.append(
            _finding(
                "content_impact_health_shape_invalid",
                f"{path}.health",
                "exact current health fields are required",
            )
        )
    for key in sorted(required_health):
        values = _string_list(health.get(key), f"{path}.health.{key}", findings)
        if values:
            findings.append(
                _finding(
                    "content_impact_health_blocked",
                    f"{path}.health.{key}",
                    ",".join(values),
                )
            )

    graph_hash = _require_wire_hash(plan, "impact_graph_hash", path, findings)
    expected_graph_hash = _wire_hash(
        {
            "member_root_path": plan.get("member_root_path"),
            "policy_id": plan.get("policy_id"),
            "inventory_hash": plan.get("inventory_hash"),
            "components": components,
            "owners": owners,
            "check_projections": projections,
            "projection_consumers": consumers,
            "portfolio_target_edges": portfolio_edges,
            "health": health,
        }
    )
    if graph_hash and graph_hash != expected_graph_hash:
        findings.append(
            _finding(
                "content_impact_graph_hash_mismatch",
                f"{path}.impact_graph_hash",
                "impact graph hash does not match current rows",
            )
        )

    for index, check in enumerate(checks):
        row_path = f"$.checks[{index}]"
        unknown_check_fields = sorted(set(check) - COMPILED_CHECK_FIELDS)
        if unknown_check_fields:
            findings.append(
                _finding(
                    "compiled_check_behavior_field_unknown",
                    row_path,
                    ",".join(unknown_check_fields),
                )
            )
        for key in (
            "execution_owner_id",
            "evidence_domain_id",
            "owner_declaration_hash",
            "owner_input_projection_hash",
            "projection_declaration_hash",
        ):
            if key.endswith("_hash"):
                _require_wire_hash(check, key, row_path, findings)
            else:
                _required_text(check, key, row_path, findings)
        _validate_input_selectors(check.get("input_selectors"), f"{row_path}.input_selectors", findings)
        _string_list(check.get("input_component_ids"), f"{row_path}.input_component_ids", findings)
        _string_list(
            check.get("target_input_role_ids"),
            f"{row_path}.target_input_role_ids",
            findings,
        )


def validate_compiled_contract(payload: object) -> tuple[SchemaFinding, ...]:
    findings: list[SchemaFinding] = []
    root = _mapping(payload, "$", findings)
    unknown_root_fields = sorted(set(root) - COMPILED_CONTRACT_FIELDS)
    if unknown_root_fields:
        findings.append(
            _finding(
                "compiled_contract_unknown_field",
                "$",
                ",".join(unknown_root_fields),
            )
        )
    if root.get("schema_version") != COMPILED_CONTRACT_SCHEMA:
        findings.append(_finding("compiled_contract_schema_mismatch", "$.schema_version", COMPILED_CONTRACT_SCHEMA))
    for key in (
        "skill_id",
        "model_id",
        "repository_role",
        "maintenance_unit_id",
        "check_declarations_hash",
        "contract_hash",
        "claim_boundary",
    ):
        _required_text(root, key, "$", findings)
    member_skill_ids = _string_list(
        root.get("member_skill_ids"), "$.member_skill_ids", findings
    )
    if root.get("skill_id") not in member_skill_ids:
        findings.append(
            _finding(
                "compiled_member_skill_ids_invalid",
                "$.member_skill_ids",
                str(root.get("skill_id", "")),
            )
        )
    consumer_projection = _mapping(
        root.get("consumer_projection"), "$.consumer_projection", findings
    )
    if (
        consumer_projection.get("projection_id")
        != "projection:consumer-distribution"
    ):
        findings.append(
            _finding(
                "compiled_consumer_projection_invalid",
                "$.consumer_projection.projection_id",
                "projection:consumer-distribution",
            )
        )
    compiled_rows: dict[str, tuple[Mapping[str, Any], ...]] = {}
    for key in (
        "functions",
        "routes",
        "steps",
        "obligations",
        "artifacts",
        "closure_profiles",
    ):
        compiled_rows[key] = _rows(root.get(key), f"$.{key}", findings)
    if "depth_profile" in root:
        findings.extend(validate_depth_profile(root.get("depth_profile"), path="$.depth_profile"))
    if "content_impact_plan" not in root:
        findings.append(
            _finding(
                "content_impact_plan_missing",
                "$.content_impact_plan",
                "compiled contracts require the current generated impact plan",
            )
        )
    else:
        _validate_content_impact_plan(
            root.get("content_impact_plan"),
            root.get("checks", []),
            path="$.content_impact_plan",
            findings=findings,
        )
    if "portfolio_capability_contracts" not in root:
        findings.append(
            _finding(
                "compiled_capability_contracts_missing",
                "$.portfolio_capability_contracts",
                "compiled contracts must project the target capability authority",
            )
        )
    else:
        _capability_contracts, capability_findings = (
            normalize_portfolio_capability_contracts(
                root.get("portfolio_capability_contracts")
            )
        )
        findings.extend(
            _finding(row.code, row.path, row.message)
            for row in capability_findings
        )
    _validate_route_branch_closure_profiles(
        root,
        compiled_rows.get("closure_profiles", ()),
        findings,
        compiled=True,
        path="$.closure_profiles",
    )
    return tuple(findings)


def validate_check_manifest(payload: object) -> tuple[SchemaFinding, ...]:
    findings: list[SchemaFinding] = []
    root = _mapping(payload, "$", findings)
    unknown_root_fields = sorted(set(root) - CHECK_MANIFEST_FIELDS)
    if unknown_root_fields:
        findings.append(
            _finding(
                "check_manifest_unknown_field",
                "$",
                ",".join(unknown_root_fields),
            )
        )
    if root.get("schema_version") != CHECK_MANIFEST_SCHEMA:
        findings.append(_finding("check_manifest_schema_mismatch", "$.schema_version", CHECK_MANIFEST_SCHEMA))
    for key in (
        "skill_id",
        "maintenance_unit_id",
        "contract_hash",
        "check_declarations_hash",
        "manifest_hash",
        "claim_boundary",
    ):
        _required_text(root, key, "$", findings)
    member_skill_ids = _string_list(
        root.get("member_skill_ids"), "$.member_skill_ids", findings
    )
    if root.get("skill_id") not in member_skill_ids:
        findings.append(
            _finding(
                "manifest_member_skill_ids_invalid",
                "$.member_skill_ids",
                str(root.get("skill_id", "")),
            )
        )
    consumer_projection = _mapping(
        root.get("consumer_projection"), "$.consumer_projection", findings
    )
    if (
        consumer_projection.get("projection_id")
        != "projection:consumer-distribution"
    ):
        findings.append(
            _finding(
                "manifest_consumer_projection_invalid",
                "$.consumer_projection.projection_id",
                "projection:consumer-distribution",
            )
        )
    checks = _rows(root.get("checks"), "$.checks", findings)
    _unique_ids(checks, "semantic_check_id", "$.checks", findings)
    if "content_impact_plan" not in root:
        findings.append(
            _finding(
                "content_impact_plan_missing",
                "$.content_impact_plan",
                "check manifests require the current generated impact plan",
            )
        )
    else:
        _validate_content_impact_plan(
            root.get("content_impact_plan"),
            checks,
            path="$.content_impact_plan",
            findings=findings,
        )
    return tuple(findings)


def raise_for_findings(findings: Iterable[SchemaFinding]) -> None:
    rows = tuple(findings)
    if rows:
        raise SchemaValidationError(rows)
