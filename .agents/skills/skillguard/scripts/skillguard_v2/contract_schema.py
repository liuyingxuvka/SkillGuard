"""Schema constants and fail-closed validation for SkillGuard V2 records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence


MODEL_EXPORT_SCHEMA = "skillguard.flowguard_model_export.v2"
BINDING_SOURCE_SCHEMA = "skillguard.contract_source.v2"
COMPILED_CONTRACT_SCHEMA = "skillguard.compiled_contract.v2"
CHECK_MANIFEST_SCHEMA = "skillguard.check_manifest.v2"
RUN_SCHEMA = "skillguard.run.v2"
EVENT_SCHEMA = "skillguard.run_event.v2"
ARTIFACT_SCHEMA = "skillguard.artifact_record.v2"
RECEIPT_SCHEMA = "skillguard.evidence_receipt.v2"
CLOSURE_SCHEMA = "skillguard.closure_receipt.v2"

SUPPORTED_FLOWGUARD_SCHEMA_VERSIONS = frozenset({"1.0"})
TARGET_KINDS = frozenset({"skill", "internal_route", "helper_api", "external_action"})
EVIDENCE_CLASSES = frozenset({"hard", "witnessed", "judged"})
TERMINAL_KINDS = frozenset({"", "success", "blocked"})
CLOSURE_PROFILE_ORDER = ("routine", "functional", "release", "highest_quality")


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


def validate_binding_source(payload: object) -> tuple[SchemaFinding, ...]:
    findings: list[SchemaFinding] = []
    root = _mapping(payload, "$", findings)
    if root.get("schema_version") != BINDING_SOURCE_SCHEMA:
        findings.append(_finding("unsupported_binding_schema", "$.schema_version", BINDING_SOURCE_SCHEMA))
    for key in ("skill_id", "model_id", "model_path", "claim_boundary"):
        _required_text(root, key, "$", findings)
    if root.get("confirmed") is not True:
        findings.append(_finding("unconfirmed_binding_source", "$.confirmed", "release compilation requires confirmed=true"))
    if "implementation_paths" in root:
        _string_list(root.get("implementation_paths"), "$.implementation_paths", findings)
    step_bindings = _rows(root.get("step_bindings"), "$.step_bindings", findings)
    checks = _rows(root.get("checks"), "$.checks", findings)
    artifacts = _rows(root.get("artifacts"), "$.artifacts", findings)
    profiles = _rows(root.get("closure_profiles"), "$.closure_profiles", findings)
    _unique_ids(step_bindings, "step_id", "$.step_bindings", findings)
    _unique_ids(checks, "check_id", "$.checks", findings)
    _unique_ids(artifacts, "artifact_id", "$.artifacts", findings)
    profile_index = _unique_ids(profiles, "profile_id", "$.closure_profiles", findings)
    for index, row in enumerate(step_bindings):
        action = _mapping(row.get("action"), f"$.step_bindings[{index}].action", findings)
        _required_text(action, "kind", f"$.step_bindings[{index}].action", findings)
        _string_list(row.get("check_ids"), f"$.step_bindings[{index}].check_ids", findings)
        _string_list(row.get("output_artifact_ids", []), f"$.step_bindings[{index}].output_artifact_ids", findings)
    for index, row in enumerate(checks):
        _required_text(row, "kind", f"$.checks[{index}]", findings)
        evidence_class = _required_text(row, "evidence_class", f"$.checks[{index}]", findings)
        if evidence_class and evidence_class not in EVIDENCE_CLASSES:
            findings.append(_finding("invalid_evidence_class", f"$.checks[{index}].evidence_class", evidence_class))
        _string_list(row.get("covers_obligation_ids"), f"$.checks[{index}].covers_obligation_ids", findings)
    for index, row in enumerate(artifacts):
        _required_text(row, "kind", f"$.artifacts[{index}]", findings)
        _required_text(row, "producer_step_id", f"$.artifacts[{index}]", findings)
        _string_list(row.get("validators"), f"$.artifacts[{index}].validators", findings)
    profile_ids = tuple(profile for profile in CLOSURE_PROFILE_ORDER if profile in profile_index)
    if profile_ids != CLOSURE_PROFILE_ORDER:
        findings.append(
            _finding(
                "closure_profiles_incomplete",
                "$.closure_profiles",
                f"required ordered profiles: {', '.join(CLOSURE_PROFILE_ORDER)}",
            )
        )
    return tuple(findings)


RUNTIME_REQUIRED_FIELDS: Mapping[str, tuple[str, ...]] = {
    RUN_SCHEMA: ("run_id", "skill_id", "contract_hash", "route_ids", "claim_scope", "status"),
    EVENT_SCHEMA: ("event_id", "run_id", "sequence", "event_type", "created_at", "payload_hash"),
    ARTIFACT_SCHEMA: ("artifact_id", "run_id", "kind", "producer_step_id", "fingerprint", "status"),
    RECEIPT_SCHEMA: ("receipt_id", "run_id", "step_id", "evidence_class", "status", "input_fingerprints"),
    CLOSURE_SCHEMA: ("closure_receipt_id", "run_id", "profile", "status", "consumed_receipt_ids", "safe_claim"),
}


def validate_runtime_payload(payload: object, expected_schema: str) -> tuple[SchemaFinding, ...]:
    findings: list[SchemaFinding] = []
    root = _mapping(payload, "$", findings)
    if expected_schema not in RUNTIME_REQUIRED_FIELDS:
        return (_finding("unknown_runtime_schema", "$.schema_version", expected_schema),)
    if root.get("schema_version") != expected_schema:
        findings.append(_finding("runtime_schema_mismatch", "$.schema_version", expected_schema))
    for key in RUNTIME_REQUIRED_FIELDS[expected_schema]:
        if key not in root:
            findings.append(_finding("runtime_required_field_missing", f"$.{key}", key))
    return tuple(findings)


def validate_compiled_contract(payload: object) -> tuple[SchemaFinding, ...]:
    findings: list[SchemaFinding] = []
    root = _mapping(payload, "$", findings)
    if root.get("schema_version") != COMPILED_CONTRACT_SCHEMA:
        findings.append(_finding("compiled_contract_schema_mismatch", "$.schema_version", COMPILED_CONTRACT_SCHEMA))
    for key in ("skill_id", "model_id", "contract_hash", "claim_boundary"):
        _required_text(root, key, "$", findings)
    for key in ("functions", "routes", "steps", "obligations", "artifacts", "closure_profiles"):
        _rows(root.get(key), f"$.{key}", findings)
    return tuple(findings)


def validate_check_manifest(payload: object) -> tuple[SchemaFinding, ...]:
    findings: list[SchemaFinding] = []
    root = _mapping(payload, "$", findings)
    if root.get("schema_version") != CHECK_MANIFEST_SCHEMA:
        findings.append(_finding("check_manifest_schema_mismatch", "$.schema_version", CHECK_MANIFEST_SCHEMA))
    for key in ("skill_id", "contract_hash", "manifest_hash", "claim_boundary"):
        _required_text(root, key, "$", findings)
    _rows(root.get("checks"), "$.checks", findings)
    return tuple(findings)


def raise_for_findings(findings: Iterable[SchemaFinding]) -> None:
    rows = tuple(findings)
    if rows:
        raise SchemaValidationError(rows)
