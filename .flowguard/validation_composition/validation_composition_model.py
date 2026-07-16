"""Executable FlowGuard model for component-scoped validation composition.

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard

The model extends the existing SkillGuard validation-composition owner.  It
keeps a complete repository inventory for omission detection, but derives
execution, installation, Portfolio, router, and aggregation effects from one
content-impact graph.  It does not replace a target executor, TestMesh, the
installer, Portfolio, the global router, or the OpenSpec verifier.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
from typing import Iterable

from flowguard import (
    BoundedEventuallyProperty,
    FunctionResult,
    GraphEdge,
    Invariant,
    InvariantResult,
    LoopCheckConfig,
    ProgressCheckConfig,
    Scenario,
    ScenarioExpectation,
    Workflow,
    check_loops,
    check_progress,
)
from flowguard.contract import (
    FunctionContract,
    check_refinement_projection,
    check_trace_contracts,
)
from flowguard.review import review_scenarios


FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"
MODEL_ID = "skillguard.validation_composition.current"
PARENT_MODEL_ID = "skillguard.executable_contract_runtime.current"
MODEL_PATH = ".flowguard/validation_composition/model.py"
POLICY_VERSION = "skillguard.content_impact_policy.current"
CURRENT_PARENT_SCHEMA = "skillguard.test_mesh_aggregation.current"

DOMAIN_SOURCE = "canonical_source"
DOMAIN_STAGE = "staged_install"
DOMAIN_ACTIVE = "active_installation"
DOMAIN_TARGET = "synchronized_target"
DOMAIN_PROMPT = "global_prompt"
DOMAIN_OPENSPEC = "openspec_report"
EVIDENCE_DOMAINS = (
    DOMAIN_SOURCE,
    DOMAIN_STAGE,
    DOMAIN_ACTIVE,
    DOMAIN_TARGET,
    DOMAIN_PROMPT,
    DOMAIN_OPENSPEC,
)

ROLE_RUNTIME = "runtime_source"
ROLE_SCHEMA = "contract_schema"
ROLE_PROMPT = "prompt_router"
ROLE_FIXTURE = "fixture_reference"
ROLE_TEST = "test_dev"
ROLE_DOCUMENT = "documentation_model"
CONTENT_ROLES = (
    ROLE_RUNTIME,
    ROLE_SCHEMA,
    ROLE_PROMPT,
    ROLE_FIXTURE,
    ROLE_TEST,
    ROLE_DOCUMENT,
)
INSTALL_COPY = "copy"
INSTALL_SOURCE_ONLY = "source_only"
INSTALL_GENERATE = "generate"
INSTALL_EXCLUDE = "exclude"
INSTALL_DISPOSITIONS = (
    INSTALL_COPY,
    INSTALL_SOURCE_ONLY,
    INSTALL_GENERATE,
    INSTALL_EXCLUDE,
)

PROOF_DIRECT = "executed_terminal_success"
PROOF_REUSED = "reused_terminal_success"
PROOF_NOT_RUN = "not_run"

STATUS_PASS = "pass"
STATUS_BLOCKED = "blocked"
STATUS_NOT_RUN = "not_run"

SUBJECT_SKILL_RUNTIME = "skill_runtime"
SUBJECT_ORDINARY_SOFTWARE = "ordinary_software"
SUBJECT_CLASSES = (SUBJECT_SKILL_RUNTIME, SUBJECT_ORDINARY_SOFTWARE)

FULL_REASON_FINAL_GATE = "explicit_final_gate"
FULL_REASON_RELEASE_GATE = "explicit_release_gate"
FULL_REASON_IMPACT_POLICY = "impact_policy_or_compiler_changed"
FULL_REASON_SHARED_RUNTIME = "shared_validation_runtime_changed"
FULL_REASON_ALL_OWNER_COMPONENT = "all_owner_component_changed"
ALLOWED_FULL_REASONS = frozenset(
    {
        FULL_REASON_FINAL_GATE,
        FULL_REASON_RELEASE_GATE,
        FULL_REASON_IMPACT_POLICY,
        FULL_REASON_SHARED_RUNTIME,
        FULL_REASON_ALL_OWNER_COMPONENT,
    }
)

CLAIM_BOUNDARY = (
    "A green report proves the finite component-impact model, function contracts, "
    "refinement projection, lifecycle progress graph, and declared known-bad variants. "
    "It does not prove production implementation, current command results, installation "
    "parity, synchronized targets, publication, target-domain correctness, or future AI behavior."
)


def _sha(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _dependency_cycle(owner_ids: tuple[str, ...], edges: tuple[tuple[str, str], ...]) -> bool:
    outgoing: dict[str, set[str]] = {owner_id: set() for owner_id in owner_ids}
    indegree: dict[str, int] = {owner_id: 0 for owner_id in owner_ids}
    for owner_id, dependency_id in edges:
        if owner_id not in outgoing or dependency_id not in outgoing:
            return True
        if dependency_id not in outgoing[owner_id]:
            outgoing[owner_id].add(dependency_id)
            indegree[dependency_id] += 1
    ready = [owner_id for owner_id, count in indegree.items() if count == 0]
    visited = 0
    while ready:
        current = ready.pop()
        visited += 1
        for dependency_id in outgoing[current]:
            indegree[dependency_id] -= 1
            if indegree[dependency_id] == 0:
                ready.append(dependency_id)
    return visited != len(owner_ids)


@dataclass(frozen=True)
class ValidationCase:
    """One immutable validation-composition observation and requested claim."""

    case_name: str

    # Cheap portable/source preflight.
    runtime_artifact_paths: tuple[str, ...] = ()
    unsafe_paths: tuple[str, ...] = ()
    report_self_watch: bool = False
    evidence_output_in_freshness_watch: bool = False
    progress_checkbox_in_test_identity: bool = False
    ordinary_report_written_into_source: bool = False
    installed_projection_recompiled_as_source: bool = False
    declared_regular_file_count: int = 12
    inventoried_regular_file_count: int = 12
    declared_non_python_count: int = 7
    inventoried_non_python_count: int = 7
    generated_contract_current: bool = True
    runtime_authority_current: bool = True

    # DevelopmentProcessFlow current-authority/compatibility admission.
    subject_class: str = SUBJECT_SKILL_RUNTIME
    compatibility_branch_enabled: bool = False
    compatibility_requirement_id: str = ""
    historical_input_identity: str = ""
    compatibility_reader_owner: str = ""
    compatibility_claim_boundary: str = ""
    compatibility_good_bad_cases_present: bool = False

    # Compiler-owned content graph. Rows are deliberately concrete rather than
    # caller-supplied booleans so uniqueness and dependency checks are executable.
    component_ids: tuple[str, ...] = (
        "component.runtime",
        "component.tests",
        "component.prompt",
    )
    component_roles: tuple[tuple[str, str], ...] = (
        ("component.runtime", ROLE_RUNTIME),
        ("component.tests", ROLE_TEST),
        ("component.prompt", ROLE_PROMPT),
    )
    component_install_dispositions: tuple[tuple[str, str], ...] = (
        ("component.runtime", INSTALL_COPY),
        ("component.tests", INSTALL_SOURCE_ONLY),
        ("component.prompt", INSTALL_GENERATE),
    )
    component_consumers: tuple[tuple[str, str], ...] = (
        ("component.runtime", "owner.runtime"),
        ("component.tests", "owner.tests"),
        ("component.prompt", "owner.router"),
    )
    owner_ids: tuple[str, ...] = (
        "owner.runtime",
        "owner.tests",
        "owner.router",
    )
    owner_input_components: tuple[tuple[str, str], ...] = (
        ("owner.runtime", "component.runtime"),
        ("owner.tests", "component.tests"),
        ("owner.router", "component.prompt"),
    )
    owner_dependency_edges: tuple[tuple[str, str], ...] = ()
    portfolio_target_edges: tuple[tuple[str, str], ...] = (
        ("component.runtime", "target.skillguard"),
    )
    router_projection_component_ids: tuple[str, ...] = (
        "component.prompt",
    )
    unmapped_paths: tuple[str, ...] = ()
    ambiguous_role_paths: tuple[str, ...] = ()
    duplicate_owner_ids: tuple[str, ...] = ()
    declared_override_descendant_count: int = 0
    classified_override_descendant_count: int = 0
    installation_member_root_path: str = ".agents/skills/skillguard"
    installation_repository_paths: tuple[str, ...] = (
        ".agents/skills/skillguard/SKILL.md",
    )
    target_install_projection_exact: bool = True
    target_install_transaction_namespace_isolated: bool = True

    # Plan inputs and current receipt pool.
    changed_component_ids: tuple[str, ...] = ("component.runtime",)
    current_receipt_owner_ids: tuple[str, ...] = ()
    tampered_receipt_owner_ids: tuple[str, ...] = ()
    parent_declaration_changed: bool = False
    consumer_projection_changed: bool = False
    validation_scope: str = "focused"
    full_admission_reason_codes: tuple[str, ...] = ()
    validation_plan_frozen: bool = True
    plan_source_current: bool = True
    source_frozen: bool = True
    toolchain_frozen: bool = True
    full_execution_owner_count: int = 1

    # Exact receipt/execution identity inputs.
    owner_declarations_current: bool = True
    owner_input_projections_current: bool = True
    dependency_receipts_current: bool = True
    toolchain_current: bool = True
    environment_current: bool = True
    persistent_receipt_root: bool = True
    sidecars_complete: bool = True
    sidecar_hashes_match: bool = True
    direct_execution_passes: bool = True
    post_launch_persistence_failure: bool = False
    forced_reported_execution_count: int = -1
    terminal_success_receipt_present: bool = True
    failed_attempt_reused: bool = False
    owner_identity_includes_run_id: bool = False
    owner_identity_includes_parent_hash: bool = False
    owner_identity_includes_whole_inventory: bool = False
    owner_identity_includes_broad_subtree: bool = False

    # Parent and evidence-domain boundaries.
    parent_schema_version: str = CURRENT_PARENT_SCHEMA
    legacy_success_route_enabled: bool = False
    evidence_metadata_refresh_route_enabled: bool = False
    noncurrent_project_manifest_read_for_rewrite: bool = False
    parent_receipt_valid: bool = True
    parent_receipt_consumer_read_only: bool = True
    parent_consumer_execution_count: int = 0
    consumer_carries_owner_command: bool = False
    required_evidence_domains: tuple[str, ...] = (DOMAIN_SOURCE,)
    domain_receipts: tuple[tuple[str, str], ...] = (
        (DOMAIN_SOURCE, "receipt:canonical-source"),
    )
    claim_complete: bool = True
    ordinary_check_selected_as_depth_producer: bool = False
    resume_used_as_readonly_audit: bool = False
    interrupted_launcher_cleanup_confirmed_zero: bool = True
    unattended_mutable_worktree_mode: str = "none"
    production_source_separate_from_evidence: bool = True
    production_target_snapshot_inside_evidence: bool = True
    production_ref_root_consistent: bool = True

    # Fault injection for generalized bad implementations.
    force_classifier_accept_runtime: bool = False
    force_allow_report_self_watch: bool = False
    force_allow_installed_source_recompile: bool = False
    force_inventory_ignore_non_python: bool = False
    force_graph_accept_gap: bool = False
    force_execute_owner_ids: tuple[str, ...] = ()
    force_install_component_ids: tuple[str, ...] = ()
    force_router_refresh: bool = False
    force_portfolio_target_ids: tuple[str, ...] = ()
    force_full_admitted: bool = False
    force_accept_invalid_receipt: bool = False
    force_hide_not_run: bool = False
    force_parent_consume_old_receipt: bool = False
    force_rewrite_child_receipt: bool = False
    force_cross_domain_reuse: bool = False


@dataclass(frozen=True)
class ValidationState:
    """Derived state for the eight component-scoped FunctionBlocks."""

    phase: int = 0
    case: ValidationCase | None = None
    artifact_policy_version: str = ""
    artifact_boundary_status: str = STATUS_NOT_RUN
    artifact_classifications: tuple[tuple[str, str], ...] = ()
    report_collision_status: str = STATUS_NOT_RUN
    preflight_status: str = STATUS_NOT_RUN
    inventory_status: str = STATUS_NOT_RUN
    inventory_row_count: int = 0
    inventory_non_python_count: int = 0
    inventory_hash: str = ""
    impact_graph_status: str = STATUS_NOT_RUN
    impact_graph_hash: str = ""
    impact_graph_gaps: tuple[str, ...] = ()
    plan_status: str = STATUS_NOT_RUN
    plan_hash: str = ""
    selected_owner_ids: tuple[str, ...] = ()
    will_reuse_owner_ids: tuple[str, ...] = ()
    will_execute_owner_ids: tuple[str, ...] = ()
    will_aggregate_only: bool = False
    required_install_component_ids: tuple[str, ...] = ()
    required_router_refresh: bool = False
    required_portfolio_target_ids: tuple[str, ...] = ()
    full_admitted: bool = False
    owner_receipt_status: str = STATUS_NOT_RUN
    receipt_rejection_reasons: tuple[str, ...] = ()
    owner_execution_keys: tuple[tuple[str, str], ...] = ()
    owner_receipt_ids: tuple[tuple[str, str], ...] = ()
    execution_status: str = STATUS_NOT_RUN
    proof_kind: str = PROOF_NOT_RUN
    executed_owner_ids: tuple[str, ...] = ()
    process_started_owner_ids: tuple[str, ...] = ()
    execution_count: int = 0
    reused_owner_ids: tuple[str, ...] = ()
    not_run_owner_ids: tuple[str, ...] = ()
    parent_status: str = STATUS_NOT_RUN
    parent_consumed_receipt_ids: tuple[str, ...] = ()
    aggregation_identity: str = ""
    child_receipt_rewritten: bool = False
    parent_profile_id: str = ""
    domain_status: str = STATUS_NOT_RUN
    missing_domain_ids: tuple[str, ...] = ()
    closure_status: str = STATUS_NOT_RUN


def _result(case: ValidationCase, state: ValidationState, label: str, reason: str) -> tuple[FunctionResult, ...]:
    return (
        FunctionResult(
            output=case,
            new_state=state,
            label=f"{label}:{case.case_name}",
            reason=reason,
        ),
    )


def _graph_gaps(case: ValidationCase) -> tuple[str, ...]:
    component_set = set(case.component_ids)
    owner_set = set(case.owner_ids)
    role_rows = {component_id: role for component_id, role in case.component_roles}
    disposition_rows = {
        component_id: disposition
        for component_id, disposition in case.component_install_dispositions
    }
    consumer_components = {component_id for component_id, _owner_id in case.component_consumers}
    input_owners = {owner_id for owner_id, _component_id in case.owner_input_components}
    gaps: list[str] = []
    gaps.extend(f"unmapped:{path}" for path in case.unmapped_paths)
    gaps.extend(f"ambiguous:{path}" for path in case.ambiguous_role_paths)
    gaps.extend(f"duplicate-owner:{owner_id}" for owner_id in case.duplicate_owner_ids)
    if (
        case.declared_override_descendant_count < 0
        or case.classified_override_descendant_count
        != case.declared_override_descendant_count
    ):
        gaps.append("reviewed-override-subtree-incomplete")
    member_root = case.installation_member_root_path.strip("/")
    for path in case.installation_repository_paths:
        normalized = str(path).replace("\\", "/")
        prefix = "" if member_root == "." else f"{member_root}/"
        if prefix and normalized.startswith(prefix):
            continue
        if member_root == "." and not normalized.startswith("/") and ":/" not in normalized:
            if all(part not in {"", ".", ".."} for part in normalized.split("/")):
                continue
        if (
            normalized.startswith("/")
            or ":/" in normalized
            or not prefix
            or not normalized.startswith(prefix)
        ):
            gaps.append(f"installation-member-outside-skill-root:{normalized}")
    if not case.target_install_projection_exact:
        gaps.append("target-install-projection-not-exact")
    if not case.target_install_transaction_namespace_isolated:
        gaps.append("target-install-transaction-namespace-not-isolated")
    if len(component_set) != len(case.component_ids):
        gaps.append("duplicate-component-id")
    if len(owner_set) != len(case.owner_ids):
        gaps.append("duplicate-owner-id")
    for component_id in case.component_ids:
        if role_rows.get(component_id) not in CONTENT_ROLES:
            gaps.append(f"role-missing-or-unknown:{component_id}")
        if disposition_rows.get(component_id) not in INSTALL_DISPOSITIONS:
            gaps.append(f"disposition-missing-or-unknown:{component_id}")
        if component_id not in consumer_components:
            gaps.append(f"consumer-missing:{component_id}")
    for component_id, owner_id in case.component_consumers:
        if component_id not in component_set or owner_id not in owner_set:
            gaps.append(f"invalid-consumer-edge:{component_id}:{owner_id}")
    for owner_id, component_id in case.owner_input_components:
        if owner_id not in owner_set or component_id not in component_set:
            gaps.append(f"invalid-owner-input:{owner_id}:{component_id}")
    for owner_id in case.owner_ids:
        if owner_id not in input_owners:
            gaps.append(f"owner-without-input:{owner_id}")
    for component_id in case.router_projection_component_ids:
        if component_id not in component_set:
            gaps.append(f"invalid-router-projection-edge:{component_id}")
    if _dependency_cycle(case.owner_ids, case.owner_dependency_edges):
        gaps.append("owner-dependency-cycle")
    return tuple(sorted(set(gaps)))


def _affected_owner_ids(case: ValidationCase) -> tuple[str, ...]:
    changed = set(case.changed_component_ids)
    affected = {
        owner_id
        for component_id, owner_id in case.component_consumers
        if component_id in changed
    }
    # owner -> dependency means owner consumes dependency receipt. A dependency
    # change therefore stales the consuming owner as well.
    changed_any = True
    while changed_any:
        changed_any = False
        for owner_id, dependency_id in case.owner_dependency_edges:
            if dependency_id in affected and owner_id not in affected:
                affected.add(owner_id)
                changed_any = True
    return tuple(owner_id for owner_id in case.owner_ids if owner_id in affected)


def _selected_owner_ids(case: ValidationCase) -> tuple[str, ...]:
    if case.validation_scope == "full":
        return case.owner_ids
    affected = _affected_owner_ids(case)
    if not affected and (case.parent_declaration_changed or case.consumer_projection_changed):
        return case.owner_ids
    return affected


def _owner_key(case: ValidationCase, owner_id: str) -> str:
    input_components = tuple(
        component_id
        for candidate_owner, component_id in case.owner_input_components
        if candidate_owner == owner_id
    )
    dependencies = tuple(
        dependency_id
        for candidate_owner, dependency_id in case.owner_dependency_edges
        if candidate_owner == owner_id
    )
    return _sha(
        {
            "execution_owner_id": owner_id,
            "owner_declaration": "current" if case.owner_declarations_current else "stale",
            "input_components": input_components,
            "owner_input_projection": "current" if case.owner_input_projections_current else "stale",
            "dependency_receipts": dependencies,
            "dependency_current": case.dependency_receipts_current,
            "toolchain_current": case.toolchain_current,
            "environment_current": case.environment_current,
            "evidence_domain_id": DOMAIN_SOURCE,
            "impact_policy": POLICY_VERSION,
        }
    )


def _expected_reuse_and_execute(
    case: ValidationCase, selected: tuple[str, ...]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    invalid_receipt = set(case.tampered_receipt_owner_ids)
    receipt_globally_current = all(
        (
            case.owner_declarations_current,
            case.owner_input_projections_current,
            case.dependency_receipts_current,
            case.toolchain_current,
            case.environment_current,
            case.persistent_receipt_root,
            case.sidecars_complete,
            case.sidecar_hashes_match,
            case.terminal_success_receipt_present,
            not case.failed_attempt_reused,
        )
    )
    reusable = tuple(
        owner_id
        for owner_id in selected
        if owner_id in set(case.current_receipt_owner_ids)
        and owner_id not in invalid_receipt
        and receipt_globally_current
    )
    executable = tuple(owner_id for owner_id in selected if owner_id not in set(reusable))
    return reusable, executable


class ClassifyPortableArtifacts:
    """ValidationCase x ValidationState -> Set(ValidationCase x ValidationState)."""

    name = "ClassifyPortableArtifacts"
    accepted_input_type = ValidationCase
    reads = ("case",)
    writes = (
        "phase",
        "case",
        "artifact_policy_version",
        "artifact_boundary_status",
        "artifact_classifications",
        "report_collision_status",
        "preflight_status",
    )
    input_description = "one immutable source boundary and receipt-consumer declaration"
    output_description = "typed portable/runtime classifications and cheap preflight status"
    idempotency = "the same case and policy version produce the same classifications"

    def apply(self, case: ValidationCase, state: ValidationState) -> tuple[FunctionResult, ...]:
        classifications = tuple((path, "runtime_evidence_output") for path in case.runtime_artifact_paths)
        classifications += tuple((path, "unsafe_or_unknown") for path in case.unsafe_paths)
        boundary_pass = not case.runtime_artifact_paths and not case.unsafe_paths
        if case.force_classifier_accept_runtime:
            boundary_pass = True
        report_blocked = case.report_self_watch and not case.force_allow_report_self_watch
        evidence_collision = (
            case.evidence_output_in_freshness_watch
            or case.progress_checkbox_in_test_identity
            or case.ordinary_report_written_into_source
            or (
                case.installed_projection_recompiled_as_source
                and not case.force_allow_installed_source_recompile
            )
        )
        preflight_pass = all(
            (
                boundary_pass,
                not report_blocked,
                not evidence_collision,
                case.generated_contract_current,
                case.runtime_authority_current,
            )
        )
        return _result(
            case,
            replace(
                state,
                phase=1,
                case=case,
                artifact_policy_version=POLICY_VERSION,
                artifact_boundary_status=STATUS_PASS if boundary_pass else STATUS_BLOCKED,
                artifact_classifications=classifications,
                report_collision_status=STATUS_BLOCKED if report_blocked else STATUS_PASS,
                preflight_status=STATUS_PASS if preflight_pass else STATUS_BLOCKED,
            ),
            "artifact-classified",
            "classified maintained inputs separately from evidence outputs and unsafe paths",
        )


class FreezeCompleteInventory:
    """ValidationCase x ValidationState -> Set(ValidationCase x ValidationState)."""

    name = "FreezeCompleteInventory"
    accepted_input_type = ValidationCase
    reads = ("preflight_status", "artifact_policy_version")
    writes = (
        "phase",
        "inventory_status",
        "inventory_row_count",
        "inventory_non_python_count",
        "inventory_hash",
    )
    input_description = "a classified source boundary"
    output_description = "one complete deterministic inventory used only for omission detection"
    idempotency = "identical bytes, paths, root context, and policy produce one inventory hash"

    def apply(self, case: ValidationCase, state: ValidationState) -> tuple[FunctionResult, ...]:
        if state.preflight_status != STATUS_PASS:
            return _result(case, replace(state, phase=2, inventory_status=STATUS_NOT_RUN), "inventory-not-run", "cheap preflight blocked inventory expansion")
        rows = case.inventoried_regular_file_count
        non_python = case.inventoried_non_python_count
        if case.force_inventory_ignore_non_python:
            rows = max(0, rows - non_python)
            non_python = 0
        complete = rows == case.declared_regular_file_count and non_python == case.declared_non_python_count and rows > 0
        return _result(
            case,
            replace(
                state,
                phase=2,
                inventory_status=STATUS_PASS if complete else STATUS_BLOCKED,
                inventory_row_count=rows,
                inventory_non_python_count=non_python,
                inventory_hash=_sha({"rows": rows, "non_python": non_python, "policy": POLICY_VERSION}) if complete else "",
            ),
            "inventory-frozen",
            "froze the complete inventory without making it every owner's execution input",
        )


class CompileContentImpactGraph:
    """ValidationCase x ValidationState -> Set(ValidationCase x ValidationState)."""

    name = "CompileContentImpactGraph"
    accepted_input_type = ValidationCase
    reads = ("preflight_status", "inventory_status", "inventory_hash")
    writes = ("phase", "impact_graph_status", "impact_graph_hash", "impact_graph_gaps")
    input_description = "one complete inventory plus semantic roles, dispositions, consumers, and owner dependencies"
    output_description = "one deterministic healthy content-impact graph or explicit graph gaps"
    idempotency = "the same normalized component and owner rows produce the same impact graph hash"

    def apply(self, case: ValidationCase, state: ValidationState) -> tuple[FunctionResult, ...]:
        if state.preflight_status != STATUS_PASS or state.inventory_status != STATUS_PASS:
            return _result(case, replace(state, phase=3, impact_graph_status=STATUS_NOT_RUN), "impact-graph-not-run", "preflight or inventory blocked graph compilation")
        gaps = _graph_gaps(case)
        passed = not gaps or case.force_graph_accept_gap
        graph_payload = {
            "components": case.component_ids,
            "roles": case.component_roles,
            "dispositions": case.component_install_dispositions,
            "consumers": case.component_consumers,
            "owners": case.owner_ids,
            "inputs": case.owner_input_components,
            "dependencies": case.owner_dependency_edges,
            "portfolio": case.portfolio_target_edges,
            "router_projection_components": case.router_projection_component_ids,
            "policy": POLICY_VERSION,
        }
        return _result(
            case,
            replace(
                state,
                phase=3,
                impact_graph_status=STATUS_PASS if passed else STATUS_BLOCKED,
                impact_graph_hash=_sha(graph_payload) if passed else "",
                impact_graph_gaps=gaps,
            ),
            "impact-graph-compiled",
            "compiled roles, installation dispositions, exact consumers, and dependency edges",
        )


class DeriveAffectedPlan:
    """ValidationCase x ValidationState -> Set(ValidationCase x ValidationState)."""

    name = "DeriveAffectedPlan"
    accepted_input_type = ValidationCase
    reads = ("impact_graph_status", "impact_graph_hash")
    writes = (
        "phase",
        "plan_status",
        "plan_hash",
        "selected_owner_ids",
        "will_reuse_owner_ids",
        "will_execute_owner_ids",
        "will_aggregate_only",
        "required_install_component_ids",
        "required_router_refresh",
        "required_portfolio_target_ids",
        "full_admitted",
    )
    input_description = "a healthy graph, changed component set, receipt heads, and requested validation scope"
    output_description = "one frozen side-effect-free reuse/execute/aggregate/install/router/Portfolio/full plan"
    idempotency = "the same graph, baseline, receipt heads, and request produce the same plan hash"

    def apply(self, case: ValidationCase, state: ValidationState) -> tuple[FunctionResult, ...]:
        if state.impact_graph_status != STATUS_PASS:
            not_run = () if case.force_hide_not_run else case.owner_ids
            return _result(
                case,
                replace(state, phase=4, plan_status=STATUS_NOT_RUN, not_run_owner_ids=not_run),
                "affected-plan-not-run",
                "graph health blocked side-effect planning",
            )
        selected = _selected_owner_ids(case)
        reusable, executable = _expected_reuse_and_execute(case, selected)
        if case.force_accept_invalid_receipt:
            reusable = tuple(
                owner_id
                for owner_id in selected
                if owner_id in set(case.current_receipt_owner_ids)
            )
            executable = tuple(owner_id for owner_id in selected if owner_id not in set(reusable))
        if case.force_execute_owner_ids:
            executable = tuple(dict.fromkeys((*executable, *case.force_execute_owner_ids)))
            reusable = tuple(owner_id for owner_id in reusable if owner_id not in set(executable))
        disposition = dict(case.component_install_dispositions)
        install_components = tuple(
            component_id
            for component_id in case.changed_component_ids
            if disposition.get(component_id) in {INSTALL_COPY, INSTALL_GENERATE}
        )
        if case.force_install_component_ids:
            install_components = tuple(dict.fromkeys((*install_components, *case.force_install_component_ids)))
        router_refresh = bool(
            set(case.changed_component_ids)
            & set(case.router_projection_component_ids)
        )
        router_refresh = router_refresh or case.force_router_refresh
        portfolio_targets = tuple(
            dict.fromkeys(
                target_id
                for component_id, target_id in case.portfolio_target_edges
                if component_id in set(case.changed_component_ids)
            )
        )
        if case.force_portfolio_target_ids:
            portfolio_targets = tuple(dict.fromkeys((*portfolio_targets, *case.force_portfolio_target_ids)))
        full_reasons = set(case.full_admission_reason_codes)
        full_admitted = (
            case.validation_scope == "full"
            and bool(full_reasons)
            and full_reasons.issubset(ALLOWED_FULL_REASONS)
            and case.validation_plan_frozen
            and case.plan_source_current
            and case.source_frozen
            and case.toolchain_frozen
            and case.full_execution_owner_count == 1
        )
        if case.force_full_admitted:
            full_admitted = True
        aggregate_only = (
            not case.changed_component_ids
            and (case.parent_declaration_changed or case.consumer_projection_changed)
            and not executable
        )
        plan_pass = case.validation_plan_frozen and case.plan_source_current
        plan_payload = {
            "impact_graph_hash": state.impact_graph_hash,
            "changed_component_ids": case.changed_component_ids,
            "selected_owner_ids": selected,
            "will_reuse_owner_ids": reusable,
            "will_execute_owner_ids": executable,
            "will_aggregate_only": aggregate_only,
            "required_install_component_ids": install_components,
            "required_router_refresh": router_refresh,
            "required_portfolio_target_ids": portfolio_targets,
            "validation_scope": case.validation_scope,
            "full_admitted": full_admitted,
            "full_reason_codes": case.full_admission_reason_codes,
        }
        return _result(
            case,
            replace(
                state,
                phase=4,
                plan_status=STATUS_PASS if plan_pass else STATUS_BLOCKED,
                plan_hash=_sha(plan_payload) if plan_pass else "",
                selected_owner_ids=selected,
                will_reuse_owner_ids=reusable,
                will_execute_owner_ids=executable,
                will_aggregate_only=aggregate_only,
                required_install_component_ids=install_components,
                required_router_refresh=router_refresh,
                required_portfolio_target_ids=portfolio_targets,
                full_admitted=full_admitted,
            ),
            "affected-plan-derived",
            "derived exact reusable and stale owners plus non-validation projections before side effects",
        )


class ResolveOwnerReceipts:
    """ValidationCase x ValidationState -> Set(ValidationCase x ValidationState)."""

    name = "ResolveOwnerReceipts"
    accepted_input_type = ValidationCase
    reads = ("plan_status", "selected_owner_ids", "will_reuse_owner_ids", "will_execute_owner_ids")
    writes = (
        "phase",
        "owner_receipt_status",
        "receipt_rejection_reasons",
        "owner_execution_keys",
        "owner_receipt_ids",
    )
    input_description = "a frozen affected plan and persistent success heads"
    output_description = "recomputed owner execution keys and independently replayed immutable receipts"
    idempotency = "run, step, attempt, parent, and whole-inventory metadata do not alter an owner execution key"

    def apply(self, case: ValidationCase, state: ValidationState) -> tuple[FunctionResult, ...]:
        if state.plan_status != STATUS_PASS:
            return _result(case, replace(state, phase=5, owner_receipt_status=STATUS_NOT_RUN), "receipt-resolution-not-run", "the frozen plan was unavailable")
        reasons: list[str] = []
        if not case.persistent_receipt_root:
            reasons.append("receipt-root-not-persistent")
        if not case.sidecars_complete:
            reasons.append("sidecars-incomplete")
        if not case.sidecar_hashes_match:
            reasons.append("sidecar-hash-mismatch")
        if case.failed_attempt_reused or not case.terminal_success_receipt_present:
            reasons.append("terminal-success-missing")
        reasons.extend(f"tampered:{owner_id}" for owner_id in case.tampered_receipt_owner_ids)
        keys = tuple((owner_id, _owner_key(case, owner_id)) for owner_id in state.selected_owner_ids)
        receipts = tuple(
            (owner_id, _sha({"schema": "skillguard.owner_receipt.current", "execution_key": key}))
            for owner_id, key in keys
            if owner_id in set(state.will_reuse_owner_ids)
        )
        passed = not reasons or not state.will_reuse_owner_ids or case.force_accept_invalid_receipt
        return _result(
            case,
            replace(
                state,
                phase=5,
                owner_receipt_status=STATUS_PASS if passed else STATUS_BLOCKED,
                receipt_rejection_reasons=tuple(reasons),
                owner_execution_keys=keys,
                owner_receipt_ids=receipts,
            ),
            "owner-receipts-resolved",
            "resolved exact persistent owner receipts without using run or parent identity",
        )


class ExecuteStaleOwners:
    """ValidationCase x ValidationState -> Set(ValidationCase x ValidationState)."""

    name = "ExecuteStaleOwners"
    accepted_input_type = ValidationCase
    reads = ("plan_status", "owner_receipt_status", "will_execute_owner_ids", "will_reuse_owner_ids")
    writes = (
        "phase",
        "execution_status",
        "proof_kind",
        "executed_owner_ids",
        "process_started_owner_ids",
        "execution_count",
        "reused_owner_ids",
        "not_run_owner_ids",
        "owner_receipt_ids",
    )
    input_description = "one frozen owner plan after persistent receipt replay"
    output_description = "only stale owner attempts plus unchanged reused success heads"
    idempotency = "a current owner receipt suppresses execution and an invalid owner affects only its dependency closure"

    def apply(self, case: ValidationCase, state: ValidationState) -> tuple[FunctionResult, ...]:
        if state.plan_status != STATUS_PASS or state.owner_receipt_status == STATUS_BLOCKED:
            not_run = () if case.force_hide_not_run else state.selected_owner_ids
            return _result(
                case,
                replace(
                    state,
                    phase=6,
                    execution_status=STATUS_NOT_RUN,
                    proof_kind=PROOF_NOT_RUN,
                    not_run_owner_ids=not_run,
                ),
                "owners-not-run",
                "graph, plan, or receipt blocker preserved every selected owner as not run",
            )
        executed = state.will_execute_owner_ids
        reused = state.will_reuse_owner_ids
        if executed and (
            not case.direct_execution_passes
            or case.post_launch_persistence_failure
        ):
            reported_count = (
                case.forced_reported_execution_count
                if case.forced_reported_execution_count >= 0
                else len(executed)
            )
            return _result(
                case,
                replace(
                    state,
                    phase=6,
                    execution_status="failed",
                    proof_kind="failed_terminal",
                    executed_owner_ids=executed,
                    process_started_owner_ids=executed,
                    execution_count=reported_count,
                    reused_owner_ids=reused,
                ),
                "owners-executed",
                "an affected owner failed and no success head was published",
            )
        key_map = dict(state.owner_execution_keys)
        receipts = dict(state.owner_receipt_ids)
        for owner_id in executed:
            owner_key = key_map.get(owner_id, _owner_key(case, owner_id))
            receipts[owner_id] = _sha(
                {
                    "schema": "skillguard.owner_receipt.current",
                    "execution_key": owner_key,
                    "sidecars": ("stdout", "stderr", "result", "termination"),
                }
            )
        proof_kind = PROOF_DIRECT if executed else PROOF_REUSED
        reported_count = (
            case.forced_reported_execution_count
            if case.forced_reported_execution_count >= 0
            else len(executed)
        )
        return _result(
            case,
            replace(
                state,
                phase=6,
                execution_status=STATUS_PASS,
                proof_kind=proof_kind,
                executed_owner_ids=executed,
                process_started_owner_ids=executed,
                execution_count=reported_count,
                reused_owner_ids=reused,
                owner_receipt_ids=tuple((owner_id, receipts[owner_id]) for owner_id in state.selected_owner_ids if owner_id in receipts),
            ),
            "owners-resolved",
            "executed only stale owners and reused exact current success heads",
        )


class AggregateParentEvidence:
    """ValidationCase x ValidationState -> Set(ValidationCase x ValidationState)."""

    name = "AggregateParentEvidence"
    accepted_input_type = ValidationCase
    reads = ("execution_status", "owner_receipt_ids", "selected_owner_ids", "will_aggregate_only")
    writes = (
        "phase",
        "parent_status",
        "parent_consumed_receipt_ids",
        "aggregation_identity",
        "child_receipt_rewritten",
        "parent_profile_id",
    )
    input_description = "an immutable selected owner receipt set and parent projection declaration"
    output_description = "a new parent aggregation identity that never rewrites or re-executes children"
    idempotency = "the same child receipts, selection, and parent declaration produce the same aggregation identity"

    def apply(self, case: ValidationCase, state: ValidationState) -> tuple[FunctionResult, ...]:
        receipt_rows = dict(state.owner_receipt_ids)
        complete = set(receipt_rows) == set(state.selected_owner_ids)
        consumed = tuple(receipt_rows[owner_id] for owner_id in state.selected_owner_ids if owner_id in receipt_rows)
        if case.force_parent_consume_old_receipt and consumed:
            consumed = ("sha256:" + "0" * 64, *consumed[1:])
        full_current = case.validation_scope != "full" or state.full_admitted
        schema_current = case.parent_schema_version == CURRENT_PARENT_SCHEMA and not case.legacy_success_route_enabled
        parent_pass = all(
            (
                state.execution_status == STATUS_PASS,
                complete,
                not state.not_run_owner_ids,
                full_current,
                schema_current,
            )
        )
        aggregation = _sha(
            {
                "schema": CURRENT_PARENT_SCHEMA,
                "owner_receipt_ids": consumed,
                "selection": state.selected_owner_ids,
                "parent_declaration_changed": case.parent_declaration_changed,
                "consumer_projection_changed": case.consumer_projection_changed,
                "profile": case.validation_scope,
            }
        ) if parent_pass else ""
        return _result(
            case,
            replace(
                state,
                phase=7,
                parent_status=STATUS_PASS if parent_pass else STATUS_BLOCKED,
                parent_consumed_receipt_ids=consumed,
                aggregation_identity=aggregation,
                child_receipt_rewritten=case.force_rewrite_child_receipt,
                parent_profile_id=case.validation_scope,
            ),
            "parent-aggregated",
            "bound the immutable child receipt set, selection, and parent declaration",
        )


class HandoffEvidenceDomains:
    """ValidationCase x ValidationState -> Set(ValidationCase x ValidationState)."""

    name = "HandoffEvidenceDomains"
    accepted_input_type = ValidationCase
    reads = ("parent_status", "aggregation_identity")
    writes = ("phase", "domain_status", "missing_domain_ids", "closure_status")
    input_description = "one source aggregation plus explicitly scoped downstream evidence domains"
    output_description = "a domain-separated closure decision with every missing domain visible"
    idempotency = "the same required domains and current receipts produce the same scoped closure"

    def apply(self, case: ValidationCase, state: ValidationState) -> tuple[FunctionResult, ...]:
        receipt_domains = {domain for domain, receipt in case.domain_receipts if receipt}
        missing = tuple(domain for domain in case.required_evidence_domains if domain not in receipt_domains)
        domain_pass = not missing or case.force_cross_domain_reuse
        closure_pass = case.claim_complete and state.parent_status == STATUS_PASS and domain_pass
        return _result(
            case,
            replace(
                state,
                phase=8,
                domain_status=STATUS_PASS if domain_pass else STATUS_BLOCKED,
                missing_domain_ids=missing,
                closure_status=STATUS_PASS if closure_pass else STATUS_BLOCKED,
            ),
            "domain-handoff",
            "kept source, stage, active, target, prompt, and OpenSpec evidence separate",
        )


BLOCKS = (
    ClassifyPortableArtifacts(),
    FreezeCompleteInventory(),
    CompileContentImpactGraph(),
    DeriveAffectedPlan(),
    ResolveOwnerReceipts(),
    ExecuteStaleOwners(),
    AggregateParentEvidence(),
    HandoffEvidenceDomains(),
)
WORKFLOW = Workflow(BLOCKS, name=MODEL_ID)


def _pass() -> InvariantResult:
    return InvariantResult.pass_()


def _fail(name: str, message: str) -> InvariantResult:
    return InvariantResult.fail(message, {"violation": name})


def portable_boundary_is_fail_closed(state: ValidationState, _trace: object) -> InvariantResult:
    if state.phase < 1 or state.case is None:
        return _pass()
    case = state.case
    if (case.runtime_artifact_paths or case.unsafe_paths) and state.artifact_boundary_status == STATUS_PASS:
        return _fail("portable_boundary_is_fail_closed", "runtime evidence and unsafe paths cannot pass the maintained-source boundary")
    if case.report_self_watch and state.report_collision_status != STATUS_BLOCKED:
        return _fail("portable_boundary_is_fail_closed", "a report included by its own freshness watch must block")
    if (
        case.evidence_output_in_freshness_watch
        or case.progress_checkbox_in_test_identity
        or case.ordinary_report_written_into_source
        or case.installed_projection_recompiled_as_source
    ):
        return _fail("portable_boundary_is_fail_closed", "reports, receipts, logs, progress, checkbox state, and installed projections cannot become canonical-source compiler inputs")
    return _pass()


def inventory_is_complete_but_not_owner_identity(state: ValidationState, _trace: object) -> InvariantResult:
    if state.phase < 2 or state.case is None or state.preflight_status != STATUS_PASS:
        return _pass()
    case = state.case
    complete = (
        state.inventory_status == STATUS_PASS
        and state.inventory_row_count == case.declared_regular_file_count
        and state.inventory_non_python_count == case.declared_non_python_count
        and bool(state.inventory_hash)
    )
    if not complete:
        return _fail("inventory_is_complete_but_not_owner_identity", "the omission inventory must include every declared regular and non-Python file")
    if case.owner_identity_includes_whole_inventory or case.owner_identity_includes_broad_subtree:
        return _fail("inventory_is_complete_but_not_owner_identity", "the complete inventory or a broad skill subtree protects omission detection but cannot enter an exact owner execution key")
    return _pass()


def impact_graph_is_complete_and_acyclic(state: ValidationState, _trace: object) -> InvariantResult:
    if state.phase < 3 or state.case is None or state.inventory_status != STATUS_PASS:
        return _pass()
    if state.impact_graph_gaps and state.impact_graph_status == STATUS_PASS:
        return _fail("impact_graph_is_complete_and_acyclic", "unmapped, ambiguous, duplicate-owner, invalid-edge, or cyclic graph rows must block before execution")
    if not state.impact_graph_gaps and (state.impact_graph_status != STATUS_PASS or not state.impact_graph_hash):
        return _fail("impact_graph_is_complete_and_acyclic", "a healthy normalized impact graph requires one deterministic content hash")
    return _pass()


def affected_plan_is_exact_and_frozen(state: ValidationState, _trace: object) -> InvariantResult:
    if state.phase < 4 or state.case is None or state.impact_graph_status != STATUS_PASS:
        return _pass()
    case = state.case
    expected_selected = _selected_owner_ids(case)
    if state.plan_status != STATUS_PASS or not state.plan_hash or not case.validation_plan_frozen or not case.plan_source_current:
        return _fail("affected_plan_is_exact_and_frozen", "owner execution must start from one current frozen plan")
    if state.selected_owner_ids != expected_selected:
        return _fail("affected_plan_is_exact_and_frozen", "selected owners must be derived from changed component and dependency edges")
    if set(state.will_execute_owner_ids) & set(state.will_reuse_owner_ids):
        return _fail("affected_plan_is_exact_and_frozen", "an owner cannot be both reused and executed")
    if set(state.will_execute_owner_ids) | set(state.will_reuse_owner_ids) != set(state.selected_owner_ids):
        return _fail("affected_plan_is_exact_and_frozen", "reuse and execution rows must account for every selected owner exactly once")
    expected_reuse, expected_execute = _expected_reuse_and_execute(case, expected_selected)
    if set(state.will_reuse_owner_ids) != set(expected_reuse) or set(state.will_execute_owner_ids) != set(expected_execute):
        return _fail("affected_plan_is_exact_and_frozen", "receipt replay must reuse every exact current owner and execute only the remaining stale owners")
    disposition = dict(case.component_install_dispositions)
    expected_install = {
        component_id
        for component_id in case.changed_component_ids
        if disposition.get(component_id) in {INSTALL_COPY, INSTALL_GENERATE}
    }
    if set(state.required_install_component_ids) != expected_install:
        return _fail("affected_plan_is_exact_and_frozen", "only changed copy/generate components may enter the install plan")
    expected_router = bool(
        set(case.changed_component_ids)
        & set(case.router_projection_component_ids)
    )
    if state.required_router_refresh != expected_router:
        return _fail("affected_plan_is_exact_and_frozen", "router refresh must be derived only from the exact router consumer edge")
    expected_targets = {
        target_id
        for component_id, target_id in case.portfolio_target_edges
        if component_id in set(case.changed_component_ids)
    }
    if set(state.required_portfolio_target_ids) != expected_targets:
        return _fail("affected_plan_is_exact_and_frozen", "Portfolio invalidation must name only graph-reached targets")
    return _pass()


def owner_identity_is_semantic_and_persistent(state: ValidationState, _trace: object) -> InvariantResult:
    if state.phase < 5 or state.case is None or state.plan_status != STATUS_PASS:
        return _pass()
    case = state.case
    if (
        case.owner_identity_includes_run_id
        or case.owner_identity_includes_parent_hash
        or case.owner_identity_includes_whole_inventory
        or case.owner_identity_includes_broad_subtree
    ):
        return _fail("owner_identity_is_semantic_and_persistent", "run, step, parent, whole-contract, whole-manifest, whole-inventory, and broad-subtree metadata cannot enter an owner key")
    if not case.persistent_receipt_root:
        return _fail("owner_identity_is_semantic_and_persistent", "owner success heads and single-flight locks require one persistent evidence root")
    if state.will_reuse_owner_ids and state.receipt_rejection_reasons:
        return _fail("owner_identity_is_semantic_and_persistent", "missing, tampered, incomplete, or nonterminal sidecars cannot satisfy reuse")
    if len({key for _owner_id, key in state.owner_execution_keys}) != len(state.owner_execution_keys):
        return _fail("owner_identity_is_semantic_and_persistent", "distinct owners require distinct semantic execution keys")
    return _pass()


def execution_matches_frozen_owner_plan(state: ValidationState, _trace: object) -> InvariantResult:
    if state.phase < 6 or state.case is None:
        return _pass()
    if state.execution_status == STATUS_NOT_RUN and state.plan_status == STATUS_PASS and state.owner_receipt_status != STATUS_BLOCKED:
        return _fail("execution_matches_frozen_owner_plan", "a valid plan must resolve every selected owner")
    if set(state.executed_owner_ids) != set(state.will_execute_owner_ids):
        return _fail("execution_matches_frozen_owner_plan", "only owners declared stale in the frozen plan may execute")
    if set(state.reused_owner_ids) != set(state.will_reuse_owner_ids):
        return _fail("execution_matches_frozen_owner_plan", "current receipt heads must be reused without a second execution")
    if state.case.failed_attempt_reused or not state.case.terminal_success_receipt_present:
        return _fail("execution_matches_frozen_owner_plan", "failed, cancelled, cleanup-unconfirmed, or nonterminal attempts cannot enter a success head")
    return _pass()


def execution_report_matches_process_start(state: ValidationState, _trace: object) -> InvariantResult:
    if state.phase < 6:
        return _pass()
    if set(state.process_started_owner_ids) != set(state.executed_owner_ids):
        return _fail(
            "execution_report_matches_process_start",
            "every started owner process must remain visible even when post-launch persistence fails",
        )
    if state.execution_count != len(state.process_started_owner_ids):
        return _fail(
            "execution_report_matches_process_start",
            "execution_count must equal the observed owner process-start count",
        )
    return _pass()


def parent_aggregation_is_one_way(state: ValidationState, _trace: object) -> InvariantResult:
    if state.phase < 7 or state.case is None:
        return _pass()
    case = state.case
    if state.child_receipt_rewritten:
        return _fail("parent_aggregation_is_one_way", "a parent may reference immutable child receipts but cannot copy, rewrite, or re-sign them")
    if state.will_aggregate_only and state.executed_owner_ids:
        return _fail("parent_aggregation_is_one_way", "parent or consumer projection changes must aggregate with zero child execution")
    if case.force_parent_consume_old_receipt:
        return _fail("parent_aggregation_is_one_way", "parent aggregation must bind the exact current selected receipt set")
    if state.parent_status == STATUS_PASS and not state.aggregation_identity:
        return _fail("parent_aggregation_is_one_way", "a passing parent requires an independent aggregation identity")
    return _pass()


def full_admission_is_explicit_and_frozen(state: ValidationState, _trace: object) -> InvariantResult:
    if state.phase < 7 or state.case is None:
        return _pass()
    case = state.case
    if case.validation_scope != "full":
        if state.full_admitted:
            return _fail("full_admission_is_explicit_and_frozen", "focused, installation, fixture, parent, or uncertainty changes cannot silently become full")
        return _pass()
    reasons = set(case.full_admission_reason_codes)
    exact = (
        bool(reasons)
        and reasons.issubset(ALLOWED_FULL_REASONS)
        and case.source_frozen
        and case.toolchain_frozen
        and case.validation_plan_frozen
        and case.full_execution_owner_count == 1
        and state.full_admitted
    )
    if not exact:
        return _fail("full_admission_is_explicit_and_frozen", "full requires an allowlisted graph-derived reason, frozen source/toolchain/plan, and one execution owner")
    return _pass()


def current_protocol_has_no_success_fallback(state: ValidationState, _trace: object) -> InvariantResult:
    if state.phase < 7 or state.case is None:
        return _pass()
    if (
        state.case.parent_schema_version != CURRENT_PARENT_SCHEMA
        or state.case.legacy_success_route_enabled
        or state.case.evidence_metadata_refresh_route_enabled
        or state.case.noncurrent_project_manifest_read_for_rewrite
    ):
        return _fail("current_protocol_has_no_success_fallback", "only the current runtime shape may succeed; retired shapes remain rejection fixtures")
    return _pass()


def compatibility_admission_is_explicit(state: ValidationState, _trace: object) -> InvariantResult:
    if state.phase < 7 or state.case is None:
        return _pass()
    case = state.case
    if case.subject_class not in SUBJECT_CLASSES:
        return _fail("compatibility_admission_is_explicit", "the change subject must be classified before compatibility is considered")
    if case.subject_class == SUBJECT_SKILL_RUNTIME:
        if case.compatibility_branch_enabled or any(
            (
                case.compatibility_requirement_id,
                case.historical_input_identity,
                case.compatibility_reader_owner,
                case.compatibility_claim_boundary,
            )
        ):
            return _fail("compatibility_admission_is_explicit", "a skill runtime has one current authority; former shapes are rejection fixtures only")
        return _pass()
    if not case.compatibility_branch_enabled:
        return _pass()
    if not all(
        (
            case.compatibility_requirement_id,
            case.historical_input_identity,
            case.compatibility_reader_owner,
            case.compatibility_claim_boundary,
            case.compatibility_good_bad_cases_present,
        )
    ):
        return _fail("compatibility_admission_is_explicit", "ordinary-software compatibility requires an explicit historical-input requirement, bounded owner, claim boundary, and good/bad cases")
    return _pass()


def evidence_domains_do_not_substitute(state: ValidationState, _trace: object) -> InvariantResult:
    if state.phase < 8 or state.case is None:
        return _pass()
    if state.case.ordinary_check_selected_as_depth_producer:
        return _fail("evidence_domains_do_not_substitute", "an ordinary check cannot become typed depth evidence by selection alone")
    if state.missing_domain_ids and (state.domain_status == STATUS_PASS or state.closure_status == STATUS_PASS):
        return _fail("evidence_domains_do_not_substitute", "one evidence domain cannot satisfy a missing stage, active, target, prompt, or OpenSpec obligation")
    return _pass()


def receipt_consumers_are_read_only(state: ValidationState, _trace: object) -> InvariantResult:
    if state.phase < 8 or state.case is None:
        return _pass()
    case = state.case
    if (
        not case.parent_receipt_consumer_read_only
        or case.parent_consumer_execution_count
        or case.consumer_carries_owner_command
    ):
        return _fail(
            "receipt_consumers_are_read_only",
            "OpenSpec and other receipt consumers cannot carry, execute, resume, repair, or backfill owner commands",
        )
    if case.resume_used_as_readonly_audit:
        return _fail("receipt_consumers_are_read_only", "resume may execute missing owners and is never a read-only audit")
    if not case.parent_receipt_valid and state.closure_status == STATUS_PASS:
        return _fail("receipt_consumers_are_read_only", "an invalid parent receipt must block without execution")
    return _pass()


def interrupted_or_unattended_execution_is_not_evidence(state: ValidationState, _trace: object) -> InvariantResult:
    if state.phase < 8 or state.case is None:
        return _pass()
    case = state.case
    if not case.interrupted_launcher_cleanup_confirmed_zero:
        return _fail("interrupted_or_unattended_execution_is_not_evidence", "timeout or interruption is invalid until the descendant process count is confirmed zero")
    if case.unattended_mutable_worktree_mode != "none":
        return _fail("interrupted_or_unattended_execution_is_not_evidence", "Scheduled Task, background resume, or unattended mutable-worktree retry is forbidden")
    return _pass()


def production_roots_preserve_roles(state: ValidationState, _trace: object) -> InvariantResult:
    if state.phase < 8 or state.case is None:
        return _pass()
    case = state.case
    if not case.production_source_separate_from_evidence or not case.production_target_snapshot_inside_evidence or not case.production_ref_root_consistent:
        return _fail("production_roots_preserve_roles", "maintained source, frozen target snapshot, persistent evidence, and portable ref roots must retain distinct stable roles")
    return _pass()


INVARIANTS = (
    Invariant("portable_boundary_is_fail_closed", "Runtime evidence, unsafe paths, and self-refreshing outputs block before planning.", portable_boundary_is_fail_closed),
    Invariant("inventory_is_complete_but_not_owner_identity", "The complete inventory prevents omissions without invalidating every owner.", inventory_is_complete_but_not_owner_identity),
    Invariant("impact_graph_is_complete_and_acyclic", "Every maintained component has one role, disposition, exact consumer set, and acyclic ownership.", impact_graph_is_complete_and_acyclic),
    Invariant("affected_plan_is_exact_and_frozen", "Reuse, execution, aggregation, install, router, Portfolio, and full decisions derive from one frozen graph.", affected_plan_is_exact_and_frozen),
    Invariant("owner_identity_is_semantic_and_persistent", "Owner keys bind exact behavior and inputs while persistent receipts bind complete sidecars.", owner_identity_is_semantic_and_persistent),
    Invariant("execution_matches_frozen_owner_plan", "Only stale owners execute and only terminal success becomes reusable.", execution_matches_frozen_owner_plan),
    Invariant("execution_report_matches_process_start", "Post-launch failures preserve the true process-start count.", execution_report_matches_process_start),
    Invariant("parent_aggregation_is_one_way", "Parent and consumer projection changes aggregate immutable child receipts with zero reverse execution.", parent_aggregation_is_one_way),
    Invariant("full_admission_is_explicit_and_frozen", "Full requires one allowlisted derived reason, frozen identities, and one owner.", full_admission_is_explicit_and_frozen),
    Invariant("current_protocol_has_no_success_fallback", "One current runtime path succeeds and retired shapes are rejection fixtures only.", current_protocol_has_no_success_fallback),
    Invariant("compatibility_admission_is_explicit", "Skills use direct current replacement; ordinary-software compatibility requires an explicit bounded historical-input contract.", compatibility_admission_is_explicit),
    Invariant("evidence_domains_do_not_substitute", "Source, install, target, prompt, and OpenSpec evidence remain distinct.", evidence_domains_do_not_substitute),
    Invariant("receipt_consumers_are_read_only", "Receipt consumers never execute or resume owners.", receipt_consumers_are_read_only),
    Invariant("interrupted_or_unattended_execution_is_not_evidence", "Interrupted descendants and unattended mutable retries cannot yield evidence.", interrupted_or_unattended_execution_is_not_evidence),
    Invariant("production_roots_preserve_roles", "Source, target snapshot, evidence, and portable refs keep stable roles.", production_roots_preserve_roles),
)


GOOD_DIRECT = ValidationCase("good-one-component-one-owner")
GOOD_REUSE = replace(
    GOOD_DIRECT,
    case_name="good-cross-run-owner-reuse",
    current_receipt_owner_ids=("owner.runtime",),
)
GOOD_POST_LAUNCH_PERSISTENCE_FAILURE = replace(
    GOOD_DIRECT,
    case_name="good-post-launch-persistence-failure-remains-counted",
    post_launch_persistence_failure=True,
)
GOOD_PARENT_ONLY = replace(
    GOOD_DIRECT,
    case_name="good-parent-only-aggregation",
    changed_component_ids=(),
    current_receipt_owner_ids=GOOD_DIRECT.owner_ids,
    parent_declaration_changed=True,
)
GOOD_CONSUMER_ONLY = replace(
    GOOD_PARENT_ONLY,
    case_name="good-consumer-projection-only",
    parent_declaration_changed=False,
    consumer_projection_changed=True,
)
GOOD_TEST_ONLY = replace(
    GOOD_DIRECT,
    case_name="good-test-only-no-install",
    changed_component_ids=("component.tests",),
)
GOOD_SUBTREE_OVERRIDE = replace(
    GOOD_TEST_ONLY,
    case_name="good-reviewed-subtree-override-covers-new-fixture",
    declared_override_descendant_count=3,
    classified_override_descendant_count=3,
)
GOOD_NESTED_SKILL_LAYOUT = replace(
    GOOD_DIRECT,
    case_name="good-current-nested-skill-installation-layout",
    installation_member_root_path="skills/storyline-design",
    installation_repository_paths=(
        "skills/storyline-design/SKILL.md",
        "skills/storyline-design/scripts/storyline_route_check.py",
    ),
)
GOOD_SINGLE_SKILL_TRANSACTION = replace(
    GOOD_NESTED_SKILL_LAYOUT,
    case_name="good-single-skill-transaction-isolated-from-guard-self-install",
)
GOOD_ROUTER_ONLY = replace(
    GOOD_DIRECT,
    case_name="good-router-only-refresh",
    changed_component_ids=("component.prompt",),
)
GOOD_PROMPT_ROLE_WITHOUT_ROUTER_EDGE = replace(
    GOOD_DIRECT,
    case_name="good-prompt-role-without-router-edge",
    changed_component_ids=("component.prompt",),
    router_projection_component_ids=(),
)
GOOD_ROUTER_EDGE_WITHOUT_PROMPT_ROLE = replace(
    GOOD_DIRECT,
    case_name="good-router-edge-without-prompt-role",
    changed_component_ids=("component.runtime",),
    router_projection_component_ids=("component.runtime",),
)
GOOD_FULL = replace(
    GOOD_DIRECT,
    case_name="good-explicit-frozen-full-parent",
    validation_scope="full",
    full_admission_reason_codes=(FULL_REASON_FINAL_GATE,),
    current_receipt_owner_ids=GOOD_DIRECT.owner_ids,
    required_evidence_domains=(DOMAIN_SOURCE, DOMAIN_ACTIVE, DOMAIN_PROMPT),
    domain_receipts=(
        (DOMAIN_SOURCE, "receipt:canonical-source"),
        (DOMAIN_ACTIVE, "receipt:current-installation"),
        (DOMAIN_PROMPT, "receipt:global-prompt"),
    ),
)
GOOD_SOFTWARE_COMPATIBILITY = replace(
    GOOD_DIRECT,
    case_name="good-explicit-ordinary-software-compatibility",
    subject_class=SUBJECT_ORDINARY_SOFTWARE,
    compatibility_branch_enabled=True,
    compatibility_requirement_id="req:historical-document-read",
    historical_input_identity="document-schema:historical-export",
    compatibility_reader_owner="owner.historical-document-reader",
    compatibility_claim_boundary="read-only historical document import",
    compatibility_good_bad_cases_present=True,
)


def _ok(case: ValidationCase, summary: str) -> Scenario:
    return Scenario(
        name=case.case_name,
        description=summary,
        initial_state=ValidationState(),
        external_input_sequence=(case,),
        expected=ScenarioExpectation(expected_status="ok", summary=summary),
        workflow=WORKFLOW,
        invariants=INVARIANTS,
    )


def _bad(case: ValidationCase, violation: str, summary: str) -> Scenario:
    return Scenario(
        name=case.case_name,
        description=summary,
        initial_state=ValidationState(),
        external_input_sequence=(case,),
        expected=ScenarioExpectation(
            expected_status="violation",
            expected_violation_names=(violation,),
            summary=summary,
        ),
        workflow=WORKFLOW,
        invariants=INVARIANTS,
    )


SCENARIOS = (
    _ok(GOOD_DIRECT, "one runtime component change executes only its owner"),
    _ok(GOOD_REUSE, "a different run reuses the same exact persistent owner receipt"),
    _ok(
        GOOD_POST_LAUNCH_PERSISTENCE_FAILURE,
        "a post-launch persistence failure remains failed evidence with one visible process start",
    ),
    _ok(GOOD_PARENT_ONLY, "a parent declaration change aggregates with zero child execution"),
    _ok(GOOD_CONSUMER_ONLY, "a consumer coverage change refreshes projection but not the owner"),
    _ok(GOOD_TEST_ONLY, "a test-only component executes its test owner without installation"),
    _ok(
        GOOD_SUBTREE_OVERRIDE,
        "a reviewed directory override classifies every maintained descendant without installation",
    ),
    _ok(
        GOOD_NESTED_SKILL_LAYOUT,
        "a current nested skill root projects exact member-relative installation paths",
    ),
    _ok(
        GOOD_SINGLE_SKILL_TRANSACTION,
        "a single-skill activation uses only its exact projection and an isolated transaction head",
    ),
    _ok(GOOD_ROUTER_ONLY, "a prompt-router component refreshes only the router projection"),
    _ok(
        GOOD_PROMPT_ROLE_WITHOUT_ROUTER_EDGE,
        "a prompt-classified component without the router consumer edge does not refresh the router",
    ),
    _ok(
        GOOD_ROUTER_EDGE_WITHOUT_PROMPT_ROLE,
        "an exact router consumer edge refreshes the router regardless of a broad file role",
    ),
    _ok(GOOD_FULL, "an explicit final gate admits one frozen full parent under one owner"),
    _ok(GOOD_SOFTWARE_COMPATIBILITY, "an explicit ordinary-software historical reader stays bounded outside skill runtime authority"),
    _bad(
        replace(GOOD_DIRECT, case_name="bad-runtime-classified-portable", runtime_artifact_paths=(".skillguard/derived-evidence/result.json",), force_classifier_accept_runtime=True),
        "portable_boundary_is_fail_closed",
        "a persistent receipt output cannot become maintained source",
    ),
    _bad(
        replace(GOOD_DIRECT, case_name="bad-report-watches-itself", report_self_watch=True, force_allow_report_self_watch=True),
        "portable_boundary_is_fail_closed",
        "a verification report cannot refresh its own producer",
    ),
    _bad(
        replace(GOOD_DIRECT, case_name="bad-receipt-output-in-freshness-watch", evidence_output_in_freshness_watch=True),
        "portable_boundary_is_fail_closed",
        "writing an owner receipt cannot stale the owner it records",
    ),
    _bad(
        replace(GOOD_DIRECT, case_name="bad-openspec-task-checkbox-in-test-identity", progress_checkbox_in_test_identity=True),
        "portable_boundary_is_fail_closed",
        "checking an OpenSpec task cannot invalidate a test receipt",
    ),
    _bad(
        replace(GOOD_DIRECT, case_name="bad-ordinary-report-written-into-source", ordinary_report_written_into_source=True),
        "portable_boundary_is_fail_closed",
        "ordinary validation reports must be written only to a runtime evidence root or stdout",
    ),
    _bad(
        replace(GOOD_DIRECT, case_name="bad-python-only-inventory", force_inventory_ignore_non_python=True),
        "inventory_is_complete_but_not_owner_identity",
        "the omission inventory cannot drop JSON, schema, prompt, or model inputs",
    ),
    _bad(
        replace(GOOD_DIRECT, case_name="bad-whole-inventory-in-owner-key", owner_identity_includes_whole_inventory=True),
        "inventory_is_complete_but_not_owner_identity",
        "an unrelated file cannot stale every owner through the complete inventory hash",
    ),
    _bad(
        replace(GOOD_DIRECT, case_name="bad-broad-skill-subtree-in-owner-key", owner_identity_includes_broad_subtree=True),
        "inventory_is_complete_but_not_owner_identity",
        "one owner cannot bind the whole skill subtree when the command consumes a smaller exact input set",
    ),
    _bad(
        replace(GOOD_DIRECT, case_name="bad-unmapped-component-falls-back-full", unmapped_paths=("new-file.py",), force_graph_accept_gap=True),
        "impact_graph_is_complete_and_acyclic",
        "an unmapped file must block rather than broaden to full",
    ),
    _bad(
        replace(GOOD_DIRECT, case_name="bad-ambiguous-component-role", ambiguous_role_paths=("mixed.json",), force_graph_accept_gap=True),
        "impact_graph_is_complete_and_acyclic",
        "an ambiguous primary role must be repaired before execution",
    ),
    _bad(
        replace(
            GOOD_TEST_ONLY,
            case_name="bad-subtree-override-misses-new-descendant",
            declared_override_descendant_count=3,
            classified_override_descendant_count=2,
            force_graph_accept_gap=True,
        ),
        "impact_graph_is_complete_and_acyclic",
        "a reviewed directory override cannot omit a newly inventoried descendant",
    ),
    _bad(
        replace(
            GOOD_NESTED_SKILL_LAYOUT,
            case_name="bad-installation-path-names-a-different-skill",
            installation_repository_paths=("skills/other-skill/SKILL.md",),
            force_graph_accept_gap=True,
        ),
        "impact_graph_is_complete_and_acyclic",
        "an installation member under a different skill id must block before projection",
    ),
    _bad(
        replace(
            GOOD_SINGLE_SKILL_TRANSACTION,
            case_name="bad-target-install-reuses-skillguard-self-head",
            target_install_transaction_namespace_isolated=False,
            force_graph_accept_gap=True,
        ),
        "impact_graph_is_complete_and_acyclic",
        "a target activation cannot share the SkillGuard self-install HEAD or recovery chain",
    ),
    _bad(
        replace(
            GOOD_SINGLE_SKILL_TRANSACTION,
            case_name="bad-target-install-copies-beyond-projection",
            target_install_projection_exact=False,
            force_graph_accept_gap=True,
        ),
        "impact_graph_is_complete_and_acyclic",
        "a target activation cannot copy source-only files or any path outside projection:installation",
    ),
    _bad(
        replace(GOOD_DIRECT, case_name="bad-duplicate-owner", duplicate_owner_ids=("owner.runtime",), force_graph_accept_gap=True),
        "impact_graph_is_complete_and_acyclic",
        "one execution may not have two primary owners",
    ),
    _bad(
        replace(GOOD_DIRECT, case_name="bad-owner-dependency-cycle", owner_dependency_edges=(("owner.runtime", "owner.tests"), ("owner.tests", "owner.runtime")), force_graph_accept_gap=True),
        "impact_graph_is_complete_and_acyclic",
        "owner dependencies cannot cycle",
    ),
    _bad(
        replace(GOOD_DIRECT, case_name="bad-validation-plan-not-frozen", validation_plan_frozen=False),
        "affected_plan_is_exact_and_frozen",
        "execution cannot discover or rewrite its plan while running",
    ),
    _bad(
        replace(GOOD_DIRECT, case_name="bad-unrelated-sibling-executed", force_execute_owner_ids=("owner.tests",)),
        "affected_plan_is_exact_and_frozen",
        "a runtime component change cannot execute an unrelated test owner",
    ),
    _bad(
        replace(GOOD_PARENT_ONLY, case_name="bad-parent-only-reruns-owner", force_execute_owner_ids=("owner.runtime",)),
        "affected_plan_is_exact_and_frozen",
        "a parent-only change must aggregate with zero child execution",
    ),
    _bad(
        replace(GOOD_CONSUMER_ONLY, case_name="bad-consumer-covers-reruns-owner", force_execute_owner_ids=("owner.runtime",)),
        "affected_plan_is_exact_and_frozen",
        "consumer coverage drift cannot reverse-invalidate the owner",
    ),
    _bad(
        replace(GOOD_TEST_ONLY, case_name="bad-test-only-triggers-install", force_install_component_ids=("component.tests",)),
        "affected_plan_is_exact_and_frozen",
        "source-only test changes cannot enter an installation plan",
    ),
    _bad(
        replace(GOOD_DIRECT, case_name="bad-runtime-change-refreshes-router", force_router_refresh=True),
        "affected_plan_is_exact_and_frozen",
        "runtime changes cannot refresh the global prompt without a prompt-router edge",
    ),
    _bad(
        replace(GOOD_DIRECT, case_name="bad-runtime-change-invalidates-unrelated-target", force_portfolio_target_ids=("target.other",)),
        "affected_plan_is_exact_and_frozen",
        "Portfolio may stale only exact graph-reached targets",
    ),
    _bad(
        replace(GOOD_REUSE, case_name="bad-invalid-sidecar-reused", sidecar_hashes_match=False, force_accept_invalid_receipt=True),
        "owner_identity_is_semantic_and_persistent",
        "a sidecar hash mismatch cannot satisfy reuse",
    ),
    _bad(
        replace(GOOD_REUSE, case_name="bad-validation-receipt-only-in-temp-copy", persistent_receipt_root=False, force_accept_invalid_receipt=True),
        "owner_identity_is_semantic_and_persistent",
        "a receipt that exists only in a temporary execution copy is not reusable",
    ),
    _bad(
        replace(GOOD_DIRECT, case_name="bad-run-id-in-owner-key", owner_identity_includes_run_id=True),
        "owner_identity_is_semantic_and_persistent",
        "run id changes must not destroy cross-run receipt reuse",
    ),
    _bad(
        replace(GOOD_DIRECT, case_name="bad-parent-hash-in-owner-key", owner_identity_includes_parent_hash=True),
        "owner_identity_is_semantic_and_persistent",
        "parent aggregation identity cannot enter a child execution key",
    ),
    _bad(
        replace(GOOD_DIRECT, case_name="bad-failed-check-attempt-reused", terminal_success_receipt_present=False, failed_attempt_reused=True),
        "execution_matches_frozen_owner_plan",
        "a failed or nonterminal attempt cannot populate the success head",
    ),
    _bad(
        replace(
            GOOD_POST_LAUNCH_PERSISTENCE_FAILURE,
            case_name="bad-post-launch-persistence-failure-reports-zero-execution",
            forced_reported_execution_count=0,
        ),
        "execution_report_matches_process_start",
        "a process that started cannot be reported as zero execution after persistence fails",
    ),
    _bad(
        replace(GOOD_PARENT_ONLY, case_name="bad-parent-rewrites-child-receipt", force_rewrite_child_receipt=True),
        "parent_aggregation_is_one_way",
        "a parent can reference but never rewrite a child receipt",
    ),
    _bad(
        replace(GOOD_DIRECT, case_name="bad-installation-implies-full", force_full_admitted=True),
        "full_admission_is_explicit_and_frozen",
        "installation alone is not a full-admission reason",
    ),
    _bad(
        replace(GOOD_DIRECT, case_name="bad-uncertainty-admits-full", validation_scope="full", full_admission_reason_codes=("uncertainty",), force_full_admitted=True),
        "full_admission_is_explicit_and_frozen",
        "uncertainty or insurance cannot authorize full",
    ),
    _bad(
        replace(GOOD_FULL, case_name="bad-full-started-before-source-fixpoint", source_frozen=False, force_full_admitted=True),
        "full_admission_is_explicit_and_frozen",
        "full against mutable source is stale by construction",
    ),
    _bad(
        replace(GOOD_FULL, case_name="bad-full-has-two-execution-owners", full_execution_owner_count=2, force_full_admitted=True),
        "full_admission_is_explicit_and_frozen",
        "two full owners create duplicate execution and competing evidence",
    ),
    _bad(
        replace(GOOD_DIRECT, case_name="bad-old-wire-auto-accepted", parent_schema_version="skillguard.test_mesh_result.retired", legacy_success_route_enabled=True),
        "current_protocol_has_no_success_fallback",
        "retired shapes cannot be converted or accepted as current success",
    ),
    _bad(
        replace(GOOD_DIRECT, case_name="bad-stale-evidence-metadata-refreshed", evidence_metadata_refresh_route_enabled=True),
        "current_protocol_has_no_success_fallback",
        "stale evidence must be replaced by its owner and cannot be edited into current evidence",
    ),
    _bad(
        replace(GOOD_DIRECT, case_name="bad-noncurrent-project-manifest-read-for-rewrite", noncurrent_project_manifest_read_for_rewrite=True),
        "current_protocol_has_no_success_fallback",
        "project maintenance accepts explicit current inputs and cannot read a former shape as rewrite input",
    ),
    _bad(
        replace(GOOD_DIRECT, case_name="bad-skill-runtime-compatibility-branch", compatibility_branch_enabled=True),
        "compatibility_admission_is_explicit",
        "a covered skill cannot retain a fallback, compatibility reader, converter, alias, or parallel authority",
    ),
    _bad(
        replace(
            GOOD_DIRECT,
            case_name="bad-unapproved-software-compatibility",
            subject_class=SUBJECT_ORDINARY_SOFTWARE,
            compatibility_branch_enabled=True,
        ),
        "compatibility_admission_is_explicit",
        "ordinary-software compatibility needs an explicit historical-input requirement and bounded reader contract",
    ),
    _bad(
        replace(GOOD_DIRECT, case_name="bad-invalid-parent-consumer-reruns-owner", parent_receipt_valid=False, parent_receipt_consumer_read_only=False, parent_consumer_execution_count=1),
        "receipt_consumers_are_read_only",
        "a missing or stale parent receipt blocks without owner execution",
    ),
    _bad(
        replace(
            GOOD_DIRECT,
            case_name="bad-consumer-copies-owner-command",
            consumer_carries_owner_command=True,
        ),
        "receipt_consumers_are_read_only",
        "a consumer may carry only the immutable owner receipt and its own projection identity",
    ),
    _bad(
        replace(GOOD_DIRECT, case_name="bad-resume-used-as-readonly-audit", resume_used_as_readonly_audit=True),
        "receipt_consumers_are_read_only",
        "resume is an executor and cannot audit a receipt read-only",
    ),
    _bad(
        replace(GOOD_DIRECT, case_name="bad-timeout-cleanup-unconfirmed", interrupted_launcher_cleanup_confirmed_zero=False),
        "interrupted_or_unattended_execution_is_not_evidence",
        "cleanup-unconfirmed output cannot become evidence or precede another owner",
    ),
    _bad(
        replace(GOOD_DIRECT, case_name="bad-scheduled-task-resumes-mutable-full", unattended_mutable_worktree_mode="windows_scheduled_task"),
        "interrupted_or_unattended_execution_is_not_evidence",
        "a Scheduled Task cannot resume a mutable validation tree",
    ),
    _bad(
        replace(GOOD_DIRECT, case_name="bad-source-overlaps-evidence", production_source_separate_from_evidence=False),
        "production_roots_preserve_roles",
        "maintained source cannot double as a mutable evidence workspace",
    ),
    _bad(
        replace(
            GOOD_DIRECT,
            case_name="bad-installed-projection-recompiled-as-source",
            installed_projection_recompiled_as_source=True,
            force_allow_installed_source_recompile=True,
        ),
        "portable_boundary_is_fail_closed",
        "an installed projection must consume its persisted current authority instead of recompiling source-only repository inputs",
    ),
    _bad(
        replace(GOOD_DIRECT, case_name="bad-target-outside-evidence-root", production_target_snapshot_inside_evidence=False),
        "production_roots_preserve_roles",
        "the frozen target snapshot and receipts require one bounded evidence root",
    ),
    _bad(
        replace(GOOD_DIRECT, case_name="bad-portable-ref-root-drift", production_ref_root_consistent=False),
        "production_roots_preserve_roles",
        "portable refs must be produced and replayed against one root identity",
    ),
)


def run_scenario_review():
    return review_scenarios(SCENARIOS)


def run_contract_review():
    run = WORKFLOW.execute(ValidationState(), GOOD_REUSE)
    if len(run.completed_paths) != 1 or run.dead_branches or run.exception_branches:
        raise RuntimeError("good validation workflow did not produce one complete trace")
    contracts = tuple(
        FunctionContract(
            function_name=block.name,
            accepted_input_type=ValidationCase,
            output_type=ValidationCase,
            reads=block.reads,
            writes=block.writes,
            idempotency_rule=block.idempotency,
            traceability_rule="every transition label binds the case name",
        )
        for block in BLOCKS
    )
    return check_trace_contracts(run.completed_paths[0].trace, contracts)


@dataclass(frozen=True)
class ValidationProjection:
    artifact_boundary_status: str
    inventory_status: str
    impact_graph_status: str
    plan_status: str
    owner_receipt_status: str
    execution_status: str
    parent_status: str
    domain_status: str
    closure_status: str


def run_refinement_review():
    run = WORKFLOW.execute(ValidationState(), GOOD_REUSE)
    final = run.completed_paths[0].state
    expected = ValidationProjection(
        final.artifact_boundary_status,
        final.inventory_status,
        final.impact_graph_status,
        final.plan_status,
        final.owner_receipt_status,
        final.execution_status,
        final.parent_status,
        final.domain_status,
        final.closure_status,
    )
    real_state = {field: getattr(final, field) for field in ValidationProjection.__dataclass_fields__}
    real_state["private_diagnostics"] = ("not part of the abstract contract",)
    return check_refinement_projection(
        expected_abstract_state=expected,
        real_state=real_state,
        projection=lambda raw: ValidationProjection(
            raw["artifact_boundary_status"],
            raw["inventory_status"],
            raw["impact_graph_status"],
            raw["plan_status"],
            raw["owner_receipt_status"],
            raw["execution_status"],
            raw["parent_status"],
            raw["domain_status"],
            raw["closure_status"],
        ),
        function_name="HandoffEvidenceDomains",
    )


def _lifecycle_edges(phase: int) -> Iterable[GraphEdge]:
    if phase >= 8:
        return ()
    return (GraphEdge(phase, phase + 1, f"phase-{phase}-to-{phase + 1}"),)


def _bad_lifecycle_edges(phase: int) -> Iterable[GraphEdge]:
    if phase == 0:
        return (GraphEdge(0, 1, "start"),)
    return (GraphEdge(1, 1, "progress-only-retry"),)


def run_loop_reviews():
    good_loop = check_loops(
        LoopCheckConfig(
            initial_states=(0,),
            transition_fn=_lifecycle_edges,
            is_terminal=lambda phase: phase == 8,
            is_success=lambda phase: phase == 8,
            required_success=True,
            max_states=9,
        )
    )
    good_progress = check_progress(
        ProgressCheckConfig(
            initial_states=(0,),
            transition_fn=_lifecycle_edges,
            is_terminal=lambda phase: phase == 8,
            is_success=lambda phase: phase == 8,
            bounded_eventually=(
                BoundedEventuallyProperty(
                    "validation-reaches-domain-handoff",
                    trigger=lambda _phase: True,
                    target=lambda phase: phase == 8,
                    max_steps=8,
                ),
            ),
            max_states=9,
        )
    )
    bad_loop = check_loops(
        LoopCheckConfig(
            initial_states=(0,),
            transition_fn=_bad_lifecycle_edges,
            is_terminal=lambda phase: phase == 8,
            is_success=lambda phase: phase == 8,
            required_success=True,
            max_states=3,
        )
    )
    return good_loop, good_progress, bad_loop


def model_summary() -> dict[str, object]:
    return {
        "model_id": MODEL_ID,
        "parent_model_id": PARENT_MODEL_ID,
        "model_path": MODEL_PATH,
        "policy_version": POLICY_VERSION,
        "current_parent_schema": CURRENT_PARENT_SCHEMA,
        "function_block_contracts": [
            f"ValidationCase x ValidationState -> Set(ValidationCase x ValidationState) [{block.name}]"
            for block in BLOCKS
        ],
        "invariant_ids": [invariant.name for invariant in INVARIANTS],
        "scenario_ids": [scenario.name for scenario in SCENARIOS],
        "known_bad_scenario_ids": [
            scenario.name for scenario in SCENARIOS if scenario.expected.expected_status == "violation"
        ],
        "allowed_full_reason_codes": sorted(ALLOWED_FULL_REASONS),
        "evidence_domains": list(EVIDENCE_DOMAINS),
        "claim_boundary": CLAIM_BOUNDARY,
    }
