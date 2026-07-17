"""Private portfolio registry, impact propagation, reuse, and graduation gates."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import socket
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from .contract_compiler import (
    canonical_hash,
    canonical_json_bytes,
    check_declarations_payload,
    compile_skill_contract,
    current_content_projection,
)
from .check_runner import execution_proof_fingerprint, resolve_owner_evidence_root
from .capability_contract import capability_binding_matches_contract
from .run_store import utc_now
from .runtime_fingerprint import (
    guard_active_installation_runtime_fingerprint,
    guard_runtime_fingerprint,
    resolve_guard_runtime_root,
)
from .installed_parity import (
    replay_installed_content_parity_currentness,
    validate_installed_parity_receipt,
)
from .portfolio_records import (
    PortfolioRecordError,
    reference_existing_file,
    resolve_record_ref,
)
from .wire_identity import wire_hash


PORTFOLIO_REGISTRY_SCHEMA = "skillguard.portfolio_registry.v2"
PORTFOLIO_SCOPE_SCHEMA = "skillguard.portfolio_scope_manifest.v1"
GUARD_CHANGE_SCHEMA = "skillguard.guard_change.v2"
GRADUATION_EVIDENCE_SCHEMA = "skillguard.portfolio_graduation_evidence.v2"
REUSE_REQUEST_SCHEMA = "skillguard.test_result_reuse_request.v2"
REUSE_TICKET_SCHEMA = "skillguard.test_result_reuse_ticket.v2"
PORTFOLIO_RECEIPT_SCHEMA = "skillguard.portfolio_graduation_receipt.v2"
PORTFOLIO_JOB_EVIDENCE_SCHEMA = "skillguard.portfolio_job_evidence_record.v2"
PORTFOLIO_JOB_PLAN_SCHEMA = "skillguard.portfolio_job_plan.v1"
PORTFOLIO_JOB_SPEC_SCHEMA = "skillguard.portfolio_job_spec.v2"
TARGET_IDENTITY_SCAN_SCHEMA = "skillguard.target_identity_scan_receipt.v1"
PORTFOLIO_PREPARATION_SCHEMA = "skillguard.portfolio_preparation_receipt.v1"
PORTFOLIO_TERMINAL_OBSERVATION_SCHEMA = (
    "skillguard.portfolio_terminal_observation.v1"
)
PORTFOLIO_MUTATION_OBSERVATION_SCHEMA = (
    "skillguard.portfolio_mutation_observation.v1"
)
PORTFOLIO_PRODUCTION_REVALIDATION_SCHEMA = (
    "skillguard.portfolio_production_revalidation_binding.v1"
)
PORTFOLIO_CAPABILITY_STAGE_RECEIPT_SCHEMA = (
    "skillguard.portfolio_capability_stage_receipt.v1"
)

ACTIVE_LIFECYCLES = frozenset({"active_owned", "active_adopted", "pending_adoption"})
EXCLUDED_LIFECYCLES = frozenset({"retired_private", "excluded_private", "excluded_system"})
SUPPORTING_LIFECYCLE = "supporting_repository"
GRADUATION_STATUSES = frozenset(
    {"pending", "baseline", "current", "revalidation_required", "blocked", "excluded", "supporting"}
)
ACTIVE_GRADUATION_STATUSES = frozenset(
    {"pending", "baseline", "current", "revalidation_required", "blocked"}
)
CAPABILITY_INVENTORY_STATUSES = frozenset({"pending", "current"})
FAILURE_CLASSIFICATIONS = frozenset(
    {
        "target_implementation_gap",
        "target_contract_binding_gap",
        "skillguard_model_miss",
        "skillguard_runtime_or_validator_gap",
        "environment_or_external_blocker",
    }
)
IDENTITY_FIELDS = (
    "source_fingerprint",
    "contract_hash",
    "command_fingerprint",
    "environment_fingerprint",
    "coverage_fingerprint",
)
HASH_RE = re.compile(r"^[A-F0-9]{64}$")
WIRE_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
EVIDENCE_REF_RE = re.compile(
    r"^record:(?P<path>[A-Za-z0-9._/-]+)@(?P<hash>[A-F0-9]{64})$"
)
JOB_CLASS_IDS = frozenset(
    {
        "positive",
        "invalid_input",
        "recovery_or_resume",
        "out_of_scope",
        "native_check",
        "artifact_check",
        "judged_quality",
    }
)
DEFAULT_REQUIRED_JOB_CLASS_IDS = (
    "positive",
    "invalid_input",
    "recovery_or_resume",
    "out_of_scope",
    "native_check",
    "artifact_check",
)
EVIDENCE_CLASSES = frozenset({"hard", "witnessed", "judged"})
TARGET_KINDS = frozenset({"single_skill", "skill_suite"})
NON_REUSABLE_GUARD_FEATURE_TAGS = frozenset(
    {"route", "receipt", "schema", "closure", "portfolio", "runtime"}
)
JOB_CLASS_EXPECTED_OUTCOMES = {
    "positive": "closed",
    "invalid_input": "expected_rejection_observed",
    "recovery_or_resume": "resume_replay_closed",
    "out_of_scope": "declined_without_mutation",
    "native_check": "native_check_current",
    "artifact_check": "artifact_current",
    "judged_quality": "judged_quality_current",
}
CAPABILITY_EVIDENCE_REQUIREMENTS = frozenset(
    {
        "manifest_check_passed",
        "closure_replay_current",
        "resume_replay_current",
        "artifact_current",
        "no_mutation",
        "judgment_current",
    }
)


def _finding(code: str, *, skill_id: str = "", detail: str = "") -> dict[str, str]:
    return {"code": code, "skill_id": skill_id, "detail": detail}


def _hash_ok(value: object) -> bool:
    return isinstance(value, str) and bool(HASH_RE.fullmatch(value))


def _content_hash_ok(value: object) -> bool:
    return isinstance(value, str) and bool(WIRE_HASH_RE.fullmatch(value))


def _portable_workspace_path_token(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        return False
    path = Path(value)
    return (
        not path.is_absolute()
        and not path.drive
        and all(part not in {"", ".", ".."} for part in path.parts)
        and path.as_posix() == value
    )


def _string_list(value: object) -> list[str] | None:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        return None
    return [str(item) for item in value]


def _unique_string_list(value: object) -> list[str] | None:
    values = _string_list(value)
    if values is None or len(values) != len(set(values)):
        return None
    return values


def _normalized_required_member_ids_by_suite(
    value: object,
) -> tuple[dict[str, list[str]], list[str]]:
    if value is None:
        return {}, []
    if not isinstance(value, Mapping):
        return {}, ["guard_change_required_members_not_object"]
    normalized: dict[str, list[str]] = {}
    findings: list[str] = []
    member_owners: dict[str, str] = {}
    for raw_suite_id, raw_member_ids in value.items():
        suite_id = str(raw_suite_id).strip()
        member_ids = _unique_string_list(raw_member_ids)
        if not suite_id:
            findings.append("guard_change_required_member_suite_id_missing")
            continue
        if not member_ids:
            findings.append(f"guard_change_required_member_ids_invalid:{suite_id}")
            continue
        for member_id in member_ids:
            prior_suite = member_owners.get(member_id)
            if prior_suite is not None and prior_suite != suite_id:
                findings.append(
                    f"guard_change_required_member_owner_ambiguous:{member_id}"
                )
            member_owners[member_id] = suite_id
        normalized[suite_id] = sorted(member_ids)
    return dict(sorted(normalized.items())), findings


def _guard_change_required_scope(
    change: Mapping[str, Any],
) -> tuple[list[str], dict[str, list[str]], list[str], list[str]]:
    raw_targets = change.get("required_target_ids")
    if raw_targets is None:
        required_target_ids: list[str] = []
        findings: list[str] = []
    else:
        normalized_targets = _unique_string_list(raw_targets)
        required_target_ids = sorted(normalized_targets or [])
        findings = (
            []
            if normalized_targets is not None
            else ["guard_change_required_target_ids_invalid"]
        )
    required_members, member_findings = _normalized_required_member_ids_by_suite(
        change.get("required_member_ids_by_suite")
    )
    findings.extend(member_findings)
    flat_member_ids = sorted(
        member_id
        for member_ids in required_members.values()
        for member_id in member_ids
    )
    overlap = sorted(set(required_target_ids) & set(flat_member_ids))
    if overlap:
        findings.append(
            "guard_change_required_target_member_overlap:" + ",".join(overlap)
        )
    return (
        required_target_ids,
        required_members,
        sorted(set(required_target_ids) | set(flat_member_ids)),
        findings,
    )


def _derive_guard_change_scope(
    change: Mapping[str, Any],
    content_impact_plan: object,
) -> tuple[list[str], dict[str, list[str]], list[str], list[str]]:
    """Derive Portfolio invalidation solely from the compiled component graph."""

    findings: list[str] = []
    if not isinstance(content_impact_plan, Mapping):
        return [], {}, [], ["guard_change_impact_plan_missing"]
    if (
        content_impact_plan.get("schema_version")
        != "skillguard.content_impact_plan.current"
    ):
        findings.append("guard_change_impact_plan_schema_unsupported")
    impact_graph_hash = str(content_impact_plan.get("impact_graph_hash", ""))
    if WIRE_HASH_RE.fullmatch(impact_graph_hash) is None:
        findings.append("guard_change_impact_graph_hash_invalid")
    elif change.get("impact_graph_hash") != impact_graph_hash:
        findings.append("guard_change_impact_graph_hash_mismatch")

    components = content_impact_plan.get("components")
    component_index = {
        str(row.get("component_id", "")): row
        for row in components
        if isinstance(row, Mapping) and str(row.get("component_id", ""))
    } if isinstance(components, list) else {}
    if not component_index or len(component_index) != len(components or []):
        findings.append("guard_change_impact_components_invalid")

    changed = _unique_string_list(change.get("changed_component_ids"))
    if (
        changed is None
        or not changed
        or changed != sorted(changed)
    ):
        findings.append("guard_change_changed_component_ids_invalid")
        changed_ids: set[str] = set()
    else:
        changed_ids = set(changed)
        unknown = sorted(changed_ids - set(component_index))
        if unknown:
            findings.append(
                "guard_change_changed_component_unknown:" + ",".join(unknown)
            )

    health = content_impact_plan.get("health")
    if not isinstance(health, Mapping) or any(
        not isinstance(values, list) or values
        for values in health.values()
    ):
        findings.append("guard_change_impact_graph_unhealthy")

    graph_payload = {
        "member_root_path": content_impact_plan.get("member_root_path"),
        "policy_id": content_impact_plan.get("policy_id"),
        "inventory_hash": content_impact_plan.get("inventory_hash"),
        "components": content_impact_plan.get("components"),
        "owners": content_impact_plan.get("owners"),
        "check_projections": content_impact_plan.get("check_projections"),
        "projection_consumers": content_impact_plan.get(
            "projection_consumers"
        ),
        "portfolio_target_edges": content_impact_plan.get(
            "portfolio_target_edges"
        ),
        "health": content_impact_plan.get("health"),
    }
    if impact_graph_hash and wire_hash(graph_payload) != impact_graph_hash:
        findings.append("guard_change_impact_graph_content_mismatch")

    edges = content_impact_plan.get("portfolio_target_edges")
    if not isinstance(edges, list):
        findings.append("guard_change_portfolio_target_edges_invalid")
        edges = []
    target_ids: set[str] = set()
    member_ids_by_suite: dict[str, set[str]] = {}
    seen_targets: set[str] = set()
    for index, row in enumerate(edges):
        if not isinstance(row, Mapping):
            findings.append(f"guard_change_portfolio_target_edge_invalid:{index}")
            continue
        target_id = str(row.get("target_id", ""))
        input_ids = _unique_string_list(row.get("input_component_ids"))
        member_ids = _unique_string_list(row.get("member_ids"))
        if (
            not target_id
            or target_id in seen_targets
            or not input_ids
            or input_ids != sorted(input_ids)
            or member_ids is None
            or member_ids != sorted(member_ids)
            or set(input_ids) - set(component_index)
        ):
            findings.append(
                f"guard_change_portfolio_target_edge_invalid:{target_id or index}"
            )
            continue
        seen_targets.add(target_id)
        for component_id in input_ids:
            consumers = component_index[component_id].get("consumer_ids", [])
            if f"portfolio-target:{target_id}" not in consumers:
                findings.append(
                    "guard_change_portfolio_target_binding_missing:"
                    f"{target_id}:{component_id}"
                )
        if changed_ids & set(input_ids):
            target_ids.add(target_id)
            if member_ids:
                member_ids_by_suite.setdefault(target_id, set()).update(
                    member_ids
                )

    normalized_members = {
        suite_id: sorted(member_ids)
        for suite_id, member_ids in sorted(member_ids_by_suite.items())
    }
    required_targets = sorted(target_ids)
    required_impact = sorted(
        target_ids
        | {
            member_id
            for member_ids in normalized_members.values()
            for member_id in member_ids
        }
    )
    return required_targets, normalized_members, required_impact, findings


def _normalized_member_revalidation_statuses(
    value: object,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    if value is None:
        return {}, []
    if not isinstance(value, Mapping):
        return {}, ["member_revalidation_statuses_not_object"]
    normalized: dict[str, dict[str, Any]] = {}
    findings: list[str] = []
    allowed_fields = {
        "graduation_status",
        "pending_guard_change_id",
        "reuse_ticket_absent",
    }
    for raw_member_id, raw_status in value.items():
        member_id = str(raw_member_id).strip()
        if not member_id or not isinstance(raw_status, Mapping):
            findings.append(
                f"member_revalidation_status_invalid:{member_id or '<missing>'}"
            )
            continue
        unknown = sorted(str(key) for key in raw_status if key not in allowed_fields)
        if unknown:
            findings.append(
                f"member_revalidation_status_unknown_field:{member_id}:{','.join(unknown)}"
            )
            continue
        pending_change_id = str(raw_status.get("pending_guard_change_id", ""))
        if (
            raw_status.get("graduation_status") != "revalidation_required"
            or not pending_change_id
            or raw_status.get("reuse_ticket_absent") is not True
        ):
            findings.append(f"member_revalidation_status_invalid:{member_id}")
            continue
        normalized[member_id] = {
            "graduation_status": "revalidation_required",
            "pending_guard_change_id": pending_change_id,
            "reuse_ticket_absent": True,
        }
    return dict(sorted(normalized.items())), findings


def _clear_member_revalidation_state(entry: dict[str, Any]) -> None:
    """Clear suite-member invalidation only after full target graduation."""

    entry.pop("member_revalidation_statuses", None)


def _target_source_configuration(
    target: object,
    *,
    skill_id: str,
) -> tuple[str, str, list[str], list[dict[str, str]]]:
    """Normalize a target's single-skill or multi-skill repository boundary."""

    if not isinstance(target, Mapping):
        return "", "", [], [_finding("portfolio_target_source_not_object", skill_id=skill_id)]
    source = (
        target.get("canonical_source")
        if isinstance(target.get("canonical_source"), Mapping)
        else target
    )
    assert isinstance(source, Mapping)
    target_kind = str(target.get("target_kind", source.get("target_kind", "single_skill")))
    primary_path = str(source.get("skill_path", ""))
    raw_paths = target.get("skill_paths", source.get("skill_paths"))
    if raw_paths is None:
        skill_paths = [primary_path] if primary_path else []
    else:
        parsed_paths = _unique_string_list(raw_paths)
        skill_paths = parsed_paths or []

    findings: list[dict[str, str]] = []
    if target_kind not in TARGET_KINDS:
        findings.append(_finding("portfolio_target_kind_invalid", skill_id=skill_id))
    if not primary_path:
        findings.append(_finding("portfolio_target_primary_skill_path_missing", skill_id=skill_id))
    if raw_paths is not None and _unique_string_list(raw_paths) is None:
        findings.append(_finding("portfolio_target_skill_paths_invalid", skill_id=skill_id))
    if primary_path and primary_path not in skill_paths:
        findings.append(_finding("portfolio_target_primary_skill_path_unlisted", skill_id=skill_id))
    if target_kind == "single_skill" and (
        len(skill_paths) != 1 or (skill_paths and skill_paths[0] != primary_path)
    ):
        findings.append(_finding("portfolio_single_skill_path_cardinality_invalid", skill_id=skill_id))
    if target_kind == "skill_suite" and len(skill_paths) < 2:
        findings.append(_finding("portfolio_skill_suite_path_cardinality_invalid", skill_id=skill_id))
    for value in skill_paths:
        path = Path(value)
        if path.is_absolute() or path.drive or ".." in path.parts:
            findings.append(
                _finding("portfolio_target_skill_path_invalid", skill_id=skill_id, detail=value)
            )
    return target_kind, primary_path, skill_paths, findings


def _normalized_member_capability_inventory(
    value: object,
) -> tuple[list[dict[str, Any]], list[str]]:
    findings: list[str] = []
    if not isinstance(value, list) or not value:
        return [], ["member_capability_inventory_missing"]
    rows: list[dict[str, Any]] = []
    seen_members: set[str] = set()
    seen_paths: set[str] = set()
    capability_owners: dict[str, str] = {}
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            findings.append(f"member_capability_row_not_object:{index}")
            continue
        member_skill_id = str(item.get("member_skill_id", ""))
        skill_path = str(item.get("skill_path", ""))
        path = Path(skill_path)
        path_invalid = (
            not skill_path or path.is_absolute() or bool(path.drive) or ".." in path.parts
        )
        capabilities = _unique_string_list(item.get("required_capability_ids"))
        if not member_skill_id or member_skill_id in seen_members:
            findings.append(
                f"member_capability_member_invalid:{member_skill_id or index}"
            )
        if path_invalid or skill_path in seen_paths:
            findings.append(
                f"member_capability_path_invalid:{skill_path or index}"
            )
        if not capabilities:
            findings.append(
                f"member_capability_ids_invalid:{member_skill_id or index}"
            )
            capabilities = []
        for capability_id in capabilities:
            prior_owner = capability_owners.get(capability_id)
            if prior_owner is not None and prior_owner != member_skill_id:
                findings.append(
                    f"member_capability_owner_duplicate:{capability_id}"
                )
            capability_owners[capability_id] = member_skill_id
        if member_skill_id:
            seen_members.add(member_skill_id)
        if not path_invalid:
            seen_paths.add(skill_path)
        if member_skill_id and not path_invalid and capabilities:
            rows.append(
                {
                    "member_skill_id": member_skill_id,
                    "skill_path": Path(skill_path).as_posix(),
                    "required_capability_ids": sorted(capabilities),
                }
            )
    rows.sort(key=lambda row: (row["skill_path"], row["member_skill_id"]))
    return rows, findings


def _member_capability_inventory_findings(
    target: Mapping[str, Any],
    *,
    target_identity: Mapping[str, Any] | None = None,
) -> list[dict[str, str]]:
    skill_id = str(target.get("skill_id", ""))
    rows, row_findings = _normalized_member_capability_inventory(
        target.get("member_capability_inventory")
    )
    findings = [
        _finding(code.split(":", 1)[0], skill_id=skill_id, detail=code)
        for code in row_findings
    ]
    required_capabilities = set(
        _unique_string_list(target.get("required_capability_ids")) or []
    )
    owned_capabilities = {
        capability_id
        for row in rows
        for capability_id in row["required_capability_ids"]
    }
    if owned_capabilities != required_capabilities:
        findings.append(
            _finding(
                "member_capability_inventory_union_mismatch",
                skill_id=skill_id,
                detail=(
                    f"missing={','.join(sorted(required_capabilities - owned_capabilities))};"
                    f"extra={','.join(sorted(owned_capabilities - required_capabilities))}"
                ),
            )
        )
    declared_paths = set(_unique_string_list(target.get("skill_paths")) or [])
    inventory_paths = {str(row["skill_path"]) for row in rows}
    if inventory_paths != declared_paths:
        findings.append(
            _finding(
                "member_capability_inventory_path_mismatch",
                skill_id=skill_id,
                detail=(
                    f"missing={','.join(sorted(declared_paths - inventory_paths))};"
                    f"extra={','.join(sorted(inventory_paths - declared_paths))}"
                ),
            )
        )
    if str(target.get("target_kind", "")) == "single_skill" and len(rows) != 1:
        findings.append(
            _finding(
                "single_skill_member_capability_inventory_invalid",
                skill_id=skill_id,
            )
        )
    if target_identity is not None:
        expected_members = {
            (
                str(row.get("member_skill_id", "")),
                str(row.get("skill_path", "")),
            )
            for row in target_identity.get("member_identities", [])
            if isinstance(row, Mapping)
        }
        inventory_members = {
            (str(row["member_skill_id"]), str(row["skill_path"])) for row in rows
        }
        if inventory_members != expected_members:
            findings.append(
                _finding(
                    "member_capability_inventory_identity_mismatch",
                    skill_id=skill_id,
                )
            )
    return findings


def _normalized_capability_bindings(
    value: object,
) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(value, list) or not value:
        return [], ["capability_bindings_missing"]
    rows: list[dict[str, Any]] = []
    findings: list[str] = []
    seen_capabilities: set[str] = set()
    id_fields = (
        "function_ids",
        "route_ids",
        "step_ids",
        "obligation_ids",
        "check_ids",
    )
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            findings.append(f"capability_binding_not_object:{index}")
            continue
        capability_id = str(item.get("capability_id", ""))
        if not capability_id or capability_id in seen_capabilities:
            findings.append(
                f"capability_binding_id_invalid:{capability_id or index}"
            )
        seen_capabilities.add(capability_id)
        normalized: dict[str, Any] = {"capability_id": capability_id}
        valid = bool(capability_id)
        for field in id_fields:
            identifiers = _unique_string_list(item.get(field))
            if not identifiers:
                findings.append(
                    f"capability_binding_{field}_invalid:{capability_id or index}"
                )
                valid = False
                identifiers = []
            normalized[field] = sorted(identifiers)
        artifact_ids = _unique_string_list(item.get("artifact_ids", []))
        if artifact_ids is None:
            findings.append(
                f"capability_binding_artifact_ids_invalid:{capability_id or index}"
            )
            valid = False
            artifact_ids = []
        requirements = _unique_string_list(item.get("evidence_requirements"))
        if (
            not requirements
            or any(
                requirement not in CAPABILITY_EVIDENCE_REQUIREMENTS
                for requirement in requirements
            )
        ):
            findings.append(
                f"capability_binding_evidence_requirements_invalid:{capability_id or index}"
            )
            valid = False
            requirements = []
        normalized["artifact_ids"] = sorted(artifact_ids)
        normalized["evidence_requirements"] = sorted(requirements)
        if valid:
            rows.append(normalized)
    return sorted(rows, key=lambda row: row["capability_id"]), findings


def _job_contract_path_findings(
    job_spec: Mapping[str, Any],
    contract: Mapping[str, Any],
    check_manifest: Mapping[str, Any],
) -> list[dict[str, str]]:
    job_id = str(job_spec.get("job_id", ""))
    bindings, binding_findings = _normalized_capability_bindings(
        job_spec.get("capability_bindings")
    )
    findings = [
        _finding(code.split(":", 1)[0], detail=f"{job_id}:{code}")
        for code in binding_findings
    ]
    covered = set(_unique_string_list(job_spec.get("covered_capability_ids")) or [])
    bound = {str(row["capability_id"]) for row in bindings}
    if covered != bound:
        findings.append(
            _finding(
                "portfolio_job_capability_contract_binding_incomplete",
                detail=(
                    f"{job_id}:missing={','.join(sorted(covered - bound))};"
                    f"extra={','.join(sorted(bound - covered))}"
                ),
            )
        )
    functions = {
        str(row.get("function_id", "")): row
        for row in contract.get("functions", [])
        if isinstance(row, Mapping)
    }
    routes = {
        str(row.get("route_id", "")): row
        for row in contract.get("routes", [])
        if isinstance(row, Mapping)
    }
    steps = {
        str(row.get("step_id", "")): row
        for row in contract.get("steps", [])
        if isinstance(row, Mapping)
    }
    obligations = {
        str(row.get("obligation_id", "")): row
        for row in contract.get("obligations", [])
        if isinstance(row, Mapping)
    }
    checks = {
        str(row.get("check_id", "")): row
        for row in check_manifest.get("checks", [])
        if isinstance(row, Mapping)
    }
    artifacts = {
        str(row.get("artifact_id", "")): row
        for row in contract.get("artifacts", [])
        if isinstance(row, Mapping)
    }
    capability_contracts = [
        row
        for row in contract.get("portfolio_capability_contracts", [])
        if isinstance(row, Mapping)
    ]
    job_class_id = str(job_spec.get("job_class_id", ""))
    for binding in bindings:
        capability_id = str(binding["capability_id"])
        function_ids = set(binding["function_ids"])
        route_ids = set(binding["route_ids"])
        step_ids = set(binding["step_ids"])
        obligation_ids = set(binding["obligation_ids"])
        check_ids = set(binding["check_ids"])
        artifact_ids = set(binding["artifact_ids"])
        if not capability_binding_matches_contract(
            binding,
            job_class_id=job_class_id,
            capability_contracts=capability_contracts,
        ):
            findings.append(
                _finding(
                    "portfolio_job_capability_semantics_invalid",
                    detail=f"{job_id}:{capability_id}",
                )
            )
        owner_complete = all(
            any(
                check_id
                in set(
                    steps[step_id].get("binding", {}).get("check_ids", [])
                )
                and any(
                    obligation_id
                    in set(checks[check_id].get("covers_obligation_ids", []))
                    and step_id
                    in set(obligations[obligation_id].get("owner_step_ids", []))
                    for obligation_id in obligation_ids
                    if obligation_id in obligations
                )
                for step_id in step_ids
                if step_id in steps
            )
            for check_id in check_ids
            if check_id in checks
        ) and all(check_id in checks for check_id in check_ids)
        if not owner_complete:
            findings.append(
                _finding(
                    "portfolio_job_check_obligation_owner_step_binding_invalid",
                    detail=f"{job_id}:{capability_id}",
                )
            )
        path_ok = (
            function_ids.issubset(functions)
            and route_ids.issubset(routes)
            and step_ids.issubset(steps)
            and obligation_ids.issubset(obligations)
            and check_ids.issubset(checks)
            and artifact_ids.issubset(artifacts)
            and all(
                str(routes[route_id].get("function_id", "")) in function_ids
                for route_id in route_ids
            )
            and all(
                str(steps[step_id].get("route_id", "")) in route_ids
                for step_id in step_ids
            )
            and all(
                bool(
                    set(
                        str(value)
                        for value in obligations[obligation_id].get(
                            "owner_step_ids", []
                        )
                    )
                    & step_ids
                )
                for obligation_id in obligation_ids
            )
            and all(
                bool(
                    set(
                        str(value)
                        for value in checks[check_id].get(
                            "covers_obligation_ids", []
                        )
                    )
                    & obligation_ids
                )
                for check_id in check_ids
            )
            and all(
                any(
                    check_id
                    in set(
                        str(value)
                        for value in steps[step_id]
                        .get("binding", {})
                        .get("check_ids", [])
                    )
                    for step_id in step_ids
                )
                for check_id in check_ids
            )
            and all(
                str(artifacts[artifact_id].get("producer_step_id", ""))
                in step_ids
                for artifact_id in artifact_ids
            )
        )
        if not path_ok:
            findings.append(
                _finding(
                    "portfolio_job_contract_path_binding_invalid",
                    detail=f"{job_id}:{capability_id}",
                )
            )
    required_check_ids = set(
        _unique_string_list(job_spec.get("required_check_ids")) or []
    )
    bound_check_ids = {
        check_id for row in bindings for check_id in row["check_ids"]
    }
    if required_check_ids != bound_check_ids:
        findings.append(
            _finding(
                "portfolio_job_required_checks_binding_invalid",
                detail=job_id,
            )
        )
    required_evidence = {
        requirement
        for row in bindings
        for requirement in row["evidence_requirements"]
    }
    required_for_class = {
        "manifest_check_passed",
        "closure_replay_current",
    }
    if job_class_id == "recovery_or_resume":
        required_for_class.add("resume_replay_current")
    elif job_class_id == "artifact_check":
        required_for_class.add("artifact_current")
    elif job_class_id in {"invalid_input", "out_of_scope"}:
        required_for_class.add("no_mutation")
    elif job_class_id == "judged_quality":
        required_for_class.add("judgment_current")
    if not required_for_class.issubset(required_evidence):
        findings.append(
            _finding(
                "portfolio_job_evidence_requirements_incomplete",
                detail=(
                    f"{job_id}:missing="
                    f"{','.join(sorted(required_for_class - required_evidence))}"
                ),
            )
        )
    return findings


def _timestamp_not_after(left: object, right: object) -> bool:
    if not _timestamp_ok(left) or not _timestamp_ok(right):
        return False
    assert isinstance(left, str) and isinstance(right, str)
    return datetime.fromisoformat(left.replace("Z", "+00:00")) <= datetime.fromisoformat(
        right.replace("Z", "+00:00")
    )


def _job_plan_findings(
    plan: object,
    *,
    record: Mapping[str, Any] | None = None,
    representative_jobs: Sequence[Mapping[str, Any]] | None = None,
) -> list[dict[str, str]]:
    if not isinstance(plan, Mapping):
        return [_finding("portfolio_job_plan_not_object")]
    skill_id = str(plan.get("skill_id", ""))
    findings: list[dict[str, str]] = []
    if (
        plan.get("schema_version") != PORTFOLIO_JOB_PLAN_SCHEMA
        or not _internal_hash_matches(plan, "job_plan_hash")
        or not _timestamp_ok(plan.get("created_at"))
    ):
        findings.append(
            _finding("portfolio_job_plan_integrity_invalid", skill_id=skill_id)
        )
    plan_jobs = plan.get("jobs")
    if not isinstance(plan_jobs, list) or not plan_jobs:
        findings.append(
            _finding("portfolio_job_plan_jobs_missing", skill_id=skill_id)
        )
        return findings
    normalized_rows: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(plan_jobs):
        if not isinstance(item, Mapping):
            findings.append(
                _finding(
                    "portfolio_job_plan_job_invalid",
                    skill_id=skill_id,
                    detail=str(index),
                )
            )
            continue
        job_id = str(item.get("job_id", ""))
        capabilities = _unique_string_list(item.get("covered_capability_ids"))
        if (
            not job_id
            or job_id in normalized_rows
            or not isinstance(item.get("member_skill_id"), str)
            or not item.get("member_skill_id")
            or not _hash_ok(item.get("member_contract_hash"))
            or str(item.get("job_class_id", "")) not in JOB_CLASS_IDS
            or not isinstance(item.get("job_spec_ref"), str)
            or EVIDENCE_REF_RE.fullmatch(str(item.get("job_spec_ref", "")))
            is None
            or not _hash_ok(item.get("job_spec_hash"))
            or not capabilities
        ):
            findings.append(
                _finding(
                    "portfolio_job_plan_job_invalid",
                    skill_id=skill_id,
                    detail=job_id or str(index),
                )
            )
            continue
        normalized_rows[job_id] = {
            "job_id": job_id,
            "job_class_id": str(item["job_class_id"]),
            "member_skill_id": str(item["member_skill_id"]),
            "member_contract_hash": str(item["member_contract_hash"]),
            "job_spec_ref": str(item["job_spec_ref"]),
            "job_spec_hash": str(item["job_spec_hash"]),
            "covered_capability_ids": sorted(capabilities),
        }
    if record is not None:
        job_id = str(record.get("job_id", ""))
        planned = normalized_rows.get(job_id)
        observed = {
            "job_id": job_id,
            "job_class_id": str(record.get("job_class_id", "")),
            "member_skill_id": str(record.get("member_skill_id", "")),
            "member_contract_hash": str(record.get("member_contract_hash", "")),
            "job_spec_ref": str(record.get("job_spec_ref", "")),
            "job_spec_hash": str(record.get("job_spec_hash", "")),
            "covered_capability_ids": sorted(
                str(value) for value in record.get("covered_capability_ids", [])
            ),
        }
        if planned != observed:
            findings.append(
                _finding(
                    "portfolio_job_plan_record_binding_invalid",
                    skill_id=skill_id,
                    detail=job_id,
                )
            )
    if representative_jobs is not None:
        expected_rows: dict[str, dict[str, Any]] = {}
        invalid_expected_rows = False
        for job in representative_jobs:
            job_id = str(job.get("job_id", ""))
            job_classes = _unique_string_list(job.get("job_class_ids"))
            capabilities = _unique_string_list(job.get("covered_capability_ids"))
            if (
                not job_id
                or job_id in expected_rows
                or not job_classes
                or len(job_classes) != 1
                or not capabilities
                or not isinstance(job.get("member_skill_id"), str)
                or not job.get("member_skill_id")
                or not _hash_ok(job.get("member_contract_hash"))
                or not isinstance(job.get("job_spec_ref"), str)
                or EVIDENCE_REF_RE.fullmatch(str(job.get("job_spec_ref", "")))
                is None
                or not _hash_ok(job.get("job_spec_hash"))
            ):
                invalid_expected_rows = True
                continue
            expected_rows[job_id] = {
                "job_id": job_id,
                "job_class_id": job_classes[0],
                "member_skill_id": str(job["member_skill_id"]),
                "member_contract_hash": str(job["member_contract_hash"]),
                "job_spec_ref": str(job["job_spec_ref"]),
                "job_spec_hash": str(job["job_spec_hash"]),
                "covered_capability_ids": sorted(capabilities),
            }
        if invalid_expected_rows or normalized_rows != expected_rows:
            findings.append(
                _finding(
                    "portfolio_job_plan_representative_jobs_mismatch",
                    skill_id=skill_id,
                    detail=(
                        f"missing={','.join(sorted(set(expected_rows) - set(normalized_rows)))};"
                        f"extra={','.join(sorted(set(normalized_rows) - set(expected_rows)))};"
                        f"changed={','.join(sorted(job_id for job_id in set(expected_rows) & set(normalized_rows) if expected_rows[job_id] != normalized_rows[job_id]))}"
                    ),
                )
            )
    return findings


def _guard_ok(value: object) -> bool:
    return (
        isinstance(value, Mapping)
        and value.get("runtime_id") == "skillguard-v2"
        and isinstance(value.get("file_count"), int)
        and int(value["file_count"]) > 0
        and _hash_ok(value.get("source_hash"))
        and re.fullmatch(
            r"sha256:[0-9a-f]{64}",
            str(value.get("portfolio_projection_hash", "")),
        )
        is not None
    )


def _timestamp_ok(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _same_guard(left: object, right: object) -> bool:
    if not _guard_ok(left) or not _guard_ok(right):
        return False
    assert isinstance(left, Mapping) and isinstance(right, Mapping)
    return (
        left["runtime_id"] == right["runtime_id"]
        and left["file_count"] == right["file_count"]
        and left["source_hash"] == right["source_hash"]
        and left["portfolio_projection_hash"]
        == right["portfolio_projection_hash"]
    )


def _identity_ok(value: object) -> bool:
    return isinstance(value, Mapping) and all(_hash_ok(value.get(field)) for field in IDENTITY_FIELDS)


def _receipt_identity(receipt: Mapping[str, Any]) -> dict[str, str]:
    return {field: str(receipt.get(field, "")) for field in IDENTITY_FIELDS}


def _full_receipt_identity_complete(receipt: object) -> bool:
    if not (
        isinstance(receipt, Mapping)
        and receipt.get("status") == "current"
        and _identity_ok(receipt)
        and isinstance(receipt.get("receipt_id"), str)
        and bool(receipt.get("receipt_id"))
        and _timestamp_ok(receipt.get("completed_at"))
        and _hash_ok(receipt.get("result_hash"))
        and _hash_ok(receipt.get("production_revalidation_fingerprint"))
        and isinstance(receipt.get("production_revalidation_bindings"), list)
        and bool(receipt.get("production_revalidation_bindings"))
        and _guard_ok(receipt.get("guard_runtime"))
        and _hash_ok(receipt.get("receipt_hash"))
    ):
        return False
    assert isinstance(receipt, Mapping)
    unsigned = dict(receipt)
    stored = unsigned.pop("receipt_hash", None)
    return stored == canonical_hash(unsigned)


def _normalized_representative_jobs(
    value: object,
    *,
    require_job_classes: bool = False,
) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(value, list) or not value:
        return [], ["representative_jobs_missing"]
    jobs: list[dict[str, Any]] = []
    findings: list[str] = []
    seen_job_ids: set[str] = set()
    for index, row in enumerate(value):
        if not isinstance(row, Mapping):
            findings.append(f"representative_job_not_object:{index}")
            continue
        job_id = str(row.get("job_id", ""))
        capabilities = _unique_string_list(row.get("covered_capability_ids"))
        evidence_refs = _unique_string_list(row.get("evidence_refs"))
        job_classes = _unique_string_list(row.get("job_class_ids", []))
        job_spec_ref = row.get("job_spec_ref")
        job_spec_hash = row.get("job_spec_hash")
        member_skill_id = str(row.get("member_skill_id", ""))
        member_contract_hash = row.get("member_contract_hash")
        expected_outcome = str(row.get("expected_outcome", ""))
        observed_outcome = str(row.get("observed_outcome", ""))
        if not job_id:
            findings.append(f"representative_job_id_missing:{index}")
        elif job_id in seen_job_ids:
            findings.append(f"representative_job_id_duplicate:{job_id}")
        seen_job_ids.add(job_id)
        if capabilities is None or not capabilities:
            findings.append(f"representative_job_capabilities_invalid:{job_id or index}")
        if evidence_refs is None or not evidence_refs:
            findings.append(f"representative_job_evidence_invalid:{job_id or index}")
        if job_classes is None:
            findings.append(f"representative_job_classes_invalid:{job_id or index}")
        elif require_job_classes and not job_classes:
            findings.append(f"representative_job_classes_missing:{job_id or index}")
        elif any(job_class not in JOB_CLASS_IDS for job_class in job_classes):
            findings.append(f"representative_job_class_unknown:{job_id or index}")
        elif require_job_classes and len(job_classes) != 1:
            findings.append(f"representative_job_must_have_one_class:{job_id or index}")
        if (
            require_job_classes
            and (
                not isinstance(job_spec_ref, str)
                or EVIDENCE_REF_RE.fullmatch(job_spec_ref) is None
                or not _hash_ok(job_spec_hash)
            )
        ):
            findings.append(f"representative_job_spec_invalid:{job_id or index}")
        if require_job_classes and (
            not member_skill_id or not _hash_ok(member_contract_hash)
        ):
            findings.append(f"representative_job_member_binding_invalid:{job_id or index}")
        if require_job_classes and job_classes and len(job_classes) == 1:
            class_outcome = JOB_CLASS_EXPECTED_OUTCOMES.get(job_classes[0], "")
            if expected_outcome != class_outcome or observed_outcome != class_outcome:
                findings.append(f"representative_job_outcome_invalid:{job_id or index}")
        if job_id and capabilities and evidence_refs and job_classes is not None:
            normalized = {
                "job_id": job_id,
                "covered_capability_ids": sorted(capabilities),
                "evidence_refs": sorted(evidence_refs),
            }
            if job_classes:
                normalized["job_class_ids"] = sorted(job_classes)
            if isinstance(job_spec_ref, str) and _hash_ok(job_spec_hash):
                normalized["job_spec_ref"] = job_spec_ref
                normalized["job_spec_hash"] = str(job_spec_hash)
            if member_skill_id and _hash_ok(member_contract_hash):
                normalized["member_skill_id"] = member_skill_id
                normalized["member_contract_hash"] = str(member_contract_hash)
            if expected_outcome:
                normalized["expected_outcome"] = expected_outcome
            if observed_outcome:
                normalized["observed_outcome"] = observed_outcome
            jobs.append(normalized)
    return sorted(jobs, key=lambda item: item["job_id"]), findings


def representative_jobs_coverage_fingerprint(value: object) -> str:
    jobs, findings = _normalized_representative_jobs(value)
    if findings:
        return ""
    return canonical_hash({"representative_jobs": jobs})


def _raw_file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _load_hash_bound_json(
    record_ref: str,
    *,
    evidence_root: Path | None,
    finding_prefix: str,
) -> tuple[Mapping[str, Any] | None, Path | None, list[dict[str, str]]]:
    match = EVIDENCE_REF_RE.fullmatch(record_ref)
    if match is None:
        return None, None, [_finding(f"{finding_prefix}_ref_invalid", detail=record_ref)]
    if evidence_root is None:
        return None, None, [_finding(f"{finding_prefix}_root_missing", detail=record_ref)]
    root = evidence_root.resolve()
    relative = Path(match.group("path"))
    if relative.is_absolute() or relative.drive or ".." in relative.parts:
        return None, None, [_finding(f"{finding_prefix}_path_not_relative", detail=record_ref)]
    path = (root / relative).resolve()
    try:
        normalized_relative = path.relative_to(root)
    except ValueError:
        return None, None, [_finding(f"{finding_prefix}_path_escape", detail=record_ref)]
    if not path.is_file():
        return None, normalized_relative, [_finding(f"{finding_prefix}_missing", detail=record_ref)]
    try:
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest().upper() != match.group("hash"):
            return (
                None,
                normalized_relative,
                [_finding(f"{finding_prefix}_file_hash_mismatch", detail=record_ref)],
            )
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return (
            None,
            normalized_relative,
            [_finding(f"{finding_prefix}_unreadable", detail=f"{record_ref}:{type(exc).__name__}")],
        )
    if not isinstance(payload, Mapping):
        return (
            None,
            normalized_relative,
            [_finding(f"{finding_prefix}_not_object", detail=record_ref)],
        )
    return payload, normalized_relative, []


def _load_hash_bound_bytes(
    record_ref: str,
    *,
    evidence_root: Path | None,
    finding_prefix: str,
) -> tuple[bytes | None, Path | None, list[dict[str, str]]]:
    match = EVIDENCE_REF_RE.fullmatch(record_ref)
    if match is None:
        return None, None, [_finding(f"{finding_prefix}_ref_invalid", detail=record_ref)]
    if evidence_root is None:
        return None, None, [_finding(f"{finding_prefix}_root_missing", detail=record_ref)]
    root = evidence_root.resolve()
    relative = Path(match.group("path"))
    if relative.is_absolute() or relative.drive or ".." in relative.parts:
        return None, None, [_finding(f"{finding_prefix}_path_not_relative", detail=record_ref)]
    path = (root / relative).resolve()
    try:
        normalized_relative = path.relative_to(root)
    except ValueError:
        return None, None, [_finding(f"{finding_prefix}_path_escape", detail=record_ref)]
    if not path.is_file():
        return None, normalized_relative, [_finding(f"{finding_prefix}_missing", detail=record_ref)]
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return None, normalized_relative, [
            _finding(f"{finding_prefix}_unreadable", detail=f"{record_ref}:{type(exc).__name__}")
        ]
    if hashlib.sha256(raw).hexdigest().upper() != match.group("hash"):
        return None, normalized_relative, [
            _finding(f"{finding_prefix}_file_hash_mismatch", detail=record_ref)
        ]
    return raw, normalized_relative, []


def _workspace_directory_token(
    path: Path, workspace_root: Path, *, code: str
) -> str:
    root = workspace_root.resolve()
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise PortfolioRecordError(code, str(path)) from exc
    token = relative.as_posix()
    if not _portable_workspace_path_token(token) or not resolved.is_dir():
        raise PortfolioRecordError(code, token)
    return token


def _run_root_artifact_record_ref(
    run_root: Path,
    artifact_ref: object,
    workspace_root: Path,
    *,
    code: str,
) -> str:
    if (
        not isinstance(artifact_ref, Mapping)
        or artifact_ref.get("path_token") != "run_root"
    ):
        raise PortfolioRecordError(code, "run_root artifact ref required")
    relative = str(artifact_ref.get("relative_path", ""))
    if (
        not relative
        or "\\" in relative
        or Path(relative).is_absolute()
        or ".." in Path(relative).parts
    ):
        raise PortfolioRecordError(code, relative)
    path = (run_root.resolve() / Path(relative)).resolve()
    try:
        path.relative_to(run_root.resolve())
    except ValueError as exc:
        raise PortfolioRecordError(code, relative) from exc
    return reference_existing_file(path, workspace_root)


def _check_artifact_record_ref(
    run_root: Path,
    owner_evidence_root: Path,
    artifact_ref: object,
    workspace_root: Path,
    *,
    code: str,
) -> str:
    """Project one immutable check artifact from its declared evidence root."""

    if not isinstance(artifact_ref, Mapping):
        raise PortfolioRecordError(code, "check artifact ref required")
    path_token = str(artifact_ref.get("path_token", ""))
    roots = {
        "run_root": run_root.resolve(),
        "owner_evidence_root": owner_evidence_root.resolve(),
    }
    root = roots.get(path_token)
    if root is None:
        raise PortfolioRecordError(code, path_token or "path token missing")
    relative = str(artifact_ref.get("relative_path", ""))
    if (
        not relative
        or "\\" in relative
        or Path(relative).is_absolute()
        or ".." in Path(relative).parts
    ):
        raise PortfolioRecordError(code, relative)
    path = (root / Path(relative)).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise PortfolioRecordError(code, relative) from exc
    return reference_existing_file(path, workspace_root)


def _current_run_fingerprints(run_root: Path) -> dict[str, object]:
    from .receipts import load_receipts

    current: dict[str, object] = {}
    for receipt in load_receipts(run_root):
        values = receipt.get("input_fingerprints")
        if not isinstance(values, Mapping):
            raise PortfolioRecordError(
                "portfolio_production_fingerprint_history_invalid",
                str(receipt.get("receipt_id", "")),
            )
        for key, value in values.items():
            normalized_key = str(key)
            if normalized_key in current and current[normalized_key] != value:
                raise PortfolioRecordError(
                    "portfolio_production_fingerprint_history_conflict",
                    normalized_key,
                )
            current[normalized_key] = value
    if not current:
        raise PortfolioRecordError(
            "portfolio_production_current_fingerprints_missing", run_root.name
        )
    return current


def _production_revalidation_binding_shape_findings(
    binding: object,
    *,
    expected_member_skill_id: str = "",
) -> list[dict[str, str]]:
    if not isinstance(binding, Mapping):
        return [_finding("portfolio_production_binding_not_object")]
    member_skill_id = str(binding.get("member_skill_id", ""))
    findings: list[dict[str, str]] = []
    if binding.get("schema_version") != PORTFOLIO_PRODUCTION_REVALIDATION_SCHEMA:
        findings.append(
            _finding(
                "portfolio_production_binding_schema_unsupported",
                skill_id=member_skill_id,
            )
        )
    if not member_skill_id:
        findings.append(_finding("portfolio_production_member_missing"))
    elif expected_member_skill_id and member_skill_id != expected_member_skill_id:
        findings.append(
            _finding(
                "portfolio_production_wrong_member",
                skill_id=member_skill_id,
                detail=f"expected={expected_member_skill_id}",
            )
        )
    for field in (
        "member_skill_path",
        "run_root_token",
        "target_root_token",
        "run_id",
        "target_skill_id",
        "native_owner_id",
        "native_route_id",
        "native_check_id",
        "captured_at",
        "claim_boundary",
    ):
        if not isinstance(binding.get(field), str) or not str(
            binding.get(field)
        ).strip():
            findings.append(
                _finding(
                    f"portfolio_production_field_missing:{field}",
                    skill_id=member_skill_id,
                )
            )
    for field in (
        "source_fingerprint",
        "member_contract_hash",
        "member_manifest_hash",
        "depth_profile_hash",
        "binding_hash",
    ):
        if not _hash_ok(binding.get(field)):
            findings.append(
                _finding(
                    f"portfolio_production_hash_invalid:{field}",
                    skill_id=member_skill_id,
                )
            )
    if binding.get("target_skill_id") != member_skill_id:
        findings.append(
            _finding(
                "portfolio_production_wrong_target",
                skill_id=member_skill_id,
                detail=str(binding.get("target_skill_id", "")),
            )
        )
    domain = str(binding.get("evidence_domain", ""))
    if domain != "scheduled_production":
        code = (
            "portfolio_production_fixture_as_production"
            if domain == "fixture_validation"
            else (
                "portfolio_production_capability_as_production"
                if domain == "capability_validation"
                else "portfolio_production_evidence_domain_invalid"
            )
        )
        findings.append(_finding(code, skill_id=member_skill_id, detail=domain))
    depth = binding.get("depth_receipt")
    if not isinstance(depth, Mapping):
        findings.append(
            _finding("portfolio_production_depth_receipt_missing", skill_id=member_skill_id)
        )
    else:
        if (
            EVIDENCE_REF_RE.fullmatch(str(depth.get("ref", ""))) is None
            or not str(depth.get("receipt_id", ""))
            or not _hash_ok(depth.get("receipt_hash"))
        ):
            findings.append(
                _finding(
                    "portfolio_production_depth_receipt_identity_invalid",
                    skill_id=member_skill_id,
                )
            )
        if depth.get("status") != "EXECUTION_DEPTH_PASS":
            findings.append(
                _finding(
                    "portfolio_production_depth_not_passed",
                    skill_id=member_skill_id,
                    detail=str(depth.get("status", "")),
                )
            )
        if depth.get("evidence_domain") != "scheduled_production":
            findings.append(
                _finding(
                    "portfolio_production_depth_domain_invalid",
                    skill_id=member_skill_id,
                    detail=str(depth.get("evidence_domain", "")),
                )
            )
    closure = binding.get("enforced_closure")
    if not isinstance(closure, Mapping):
        findings.append(
            _finding(
                "portfolio_production_enforced_closure_missing",
                skill_id=member_skill_id,
            )
        )
    else:
        if (
            EVIDENCE_REF_RE.fullmatch(str(closure.get("ref", ""))) is None
            or not str(closure.get("receipt_id", ""))
            or not _hash_ok(closure.get("receipt_hash"))
        ):
            findings.append(
                _finding(
                    "portfolio_production_closure_receipt_identity_invalid",
                    skill_id=member_skill_id,
                )
            )
        profile = str(closure.get("profile", ""))
        if profile != "enforced":
            findings.append(
                _finding(
                    "portfolio_production_enforced_closure_required",
                    skill_id=member_skill_id,
                    detail=profile,
                )
            )
        if closure.get("status") != "closed":
            findings.append(
                _finding(
                    "portfolio_production_closure_not_closed",
                    skill_id=member_skill_id,
                )
            )
        consumed_receipt_ids = _unique_string_list(
            closure.get("consumed_receipt_ids")
        )
        if consumed_receipt_ids is None or len(consumed_receipt_ids) < 2:
            findings.append(
                _finding(
                    "portfolio_production_closure_consumed_receipts_invalid",
                    skill_id=member_skill_id,
                )
            )
    terminal = binding.get("native_terminal")
    if not isinstance(terminal, Mapping):
        findings.append(
            _finding(
                "portfolio_production_native_terminal_missing",
                skill_id=member_skill_id,
            )
        )
    else:
        if (
            EVIDENCE_REF_RE.fullmatch(str(terminal.get("ref", ""))) is None
            or not str(terminal.get("receipt_id", ""))
            or not _hash_ok(terminal.get("receipt_hash"))
        ):
            findings.append(
                _finding(
                    "portfolio_production_terminal_receipt_identity_invalid",
                    skill_id=member_skill_id,
                )
            )
        if terminal.get("closure_profile") != "enforced":
            findings.append(
                _finding(
                    "portfolio_production_native_terminal_profile_invalid",
                    skill_id=member_skill_id,
                )
            )
        if terminal.get("closure_disposition") != "terminal_completion":
            code = (
                "portfolio_production_nonterminal_closure_cannot_promote"
                if terminal.get("closure_disposition")
                == "non_terminal_authorization"
                else "portfolio_production_terminal_completion_required"
            )
            findings.append(_finding(code, skill_id=member_skill_id))
        if terminal.get("evidence_domain") != "scheduled_production":
            findings.append(
                _finding(
                    "portfolio_production_terminal_domain_invalid",
                    skill_id=member_skill_id,
                )
            )
        if terminal.get("native_route_id") != binding.get("native_route_id"):
            findings.append(
                _finding(
                    "portfolio_production_terminal_route_mismatch",
                    skill_id=member_skill_id,
                )
            )
        if terminal.get("conditional") is True and not str(
            terminal.get("branch_id", "")
        ):
            findings.append(
                _finding(
                    "portfolio_production_conditional_branch_missing",
                    skill_id=member_skill_id,
                )
            )
        consumed = (
            closure.get("consumed_receipt_ids", [])
            if isinstance(closure, Mapping)
            else []
        )
        if (
            not isinstance(consumed, list)
            or not isinstance(depth, Mapping)
            or depth.get("receipt_id") not in consumed
            or terminal.get("receipt_id") not in consumed
        ):
            findings.append(
                _finding(
                    "portfolio_production_terminal_or_depth_not_consumed",
                    skill_id=member_skill_id,
                )
            )
    installation = binding.get("installation_identity")
    if not isinstance(installation, Mapping):
        findings.append(
            _finding(
                "portfolio_production_installation_identity_missing",
                skill_id=member_skill_id,
            )
        )
    else:
        for field in (
            "scheduler_or_trigger_id",
            "scheduled_execution_id",
            "installation_receipt_id",
            "installation_receipt_hash",
            "installed_runtime_fingerprint",
            "transaction_id",
            "stage_verification_hash",
            "post_activation_smoke_hash",
            "post_activation_member_comparisons_hash",
            "current_installed_smoke_hash",
            "current_installed_smoke_command_fingerprint",
            "current_installed_smoke_environment_fingerprint",
        ):
            if not isinstance(installation.get(field), str) or not str(
                installation.get(field)
            ):
                findings.append(
                    _finding(
                        f"portfolio_production_installation_field_missing:{field}",
                        skill_id=member_skill_id,
                    )
                )
        for field in (
            "installation_receipt_hash",
            "installed_runtime_fingerprint",
            "stage_verification_hash",
            "post_activation_smoke_hash",
            "post_activation_member_comparisons_hash",
            "current_installed_smoke_hash",
            "current_installed_smoke_command_fingerprint",
            "current_installed_smoke_environment_fingerprint",
        ):
            if not _hash_ok(installation.get(field)):
                findings.append(
                    _finding(
                        f"portfolio_production_installation_hash_invalid:{field}",
                        skill_id=member_skill_id,
                    )
                )
        if re.fullmatch(
            r"install-[a-f0-9]{32}",
            str(installation.get("transaction_id", "")),
        ) is None:
            findings.append(
                _finding(
                    "portfolio_production_installation_transaction_invalid",
                    skill_id=member_skill_id,
                )
            )
        root_ref = installation.get("installation_receipt_root_ref")
        if (
            not isinstance(root_ref, Mapping)
            or root_ref.get("path_token") != "active_skill_root"
            or not _portable_workspace_path_token(root_ref.get("relative_path"))
        ):
            findings.append(
                _finding(
                    "portfolio_production_installation_root_ref_invalid",
                    skill_id=member_skill_id,
                )
            )
        if installation.get("rollback_disposition") != "not_required":
            findings.append(
                _finding(
                    "portfolio_production_installation_rollback_invalid",
                    skill_id=member_skill_id,
                )
            )
    unsigned = dict(binding)
    stored_hash = unsigned.pop("binding_hash", None)
    if stored_hash != canonical_hash(unsigned):
        findings.append(
            _finding(
                "portfolio_production_binding_hash_mismatch",
                skill_id=member_skill_id,
            )
        )
    return findings


def build_portfolio_production_revalidation_binding(
    *,
    member_skill_id: str,
    member_skill_path: str,
    source_fingerprint: str,
    member_contract_hash: str,
    member_manifest_hash: str,
    member_repository_root: Path,
    run_root: Path,
    target_root: Path,
    workspace_root: Path,
    closure_receipt_id: str,
    owner_evidence_root: Path | None = None,
    verified_installation_context: object | None = None,
) -> dict[str, Any]:
    """Compose one member's production graduation authority from native receipts."""

    from .closure import load_closure, verify_closure
    from .execution_depth import (
        EXECUTION_DEPTH_PASS,
        evaluate_depth_receipt_gate,
        load_target_execution_receipts,
    )
    from .installation_receipt import (
        INSTALL_VERIFICATION_SCHEMA,
        verify_scheduled_production_installation_identity,
    )
    from .native_terminal import resolve_native_terminal_receipt
    from .run_store import (
        load_check_manifest_snapshot,
        load_contract_snapshot,
        load_run,
    )

    workspace_root = workspace_root.resolve()
    member_repository_root = member_repository_root.resolve()
    run_root = run_root.resolve()
    target_root = target_root.resolve()
    persistent_owner_root = resolve_owner_evidence_root(
        member_repository_root,
        owner_evidence_root,
    )
    run_root_token = _workspace_directory_token(
        run_root,
        workspace_root,
        code="portfolio_production_run_root_outside_workspace",
    )
    target_root_token = _workspace_directory_token(
        target_root,
        workspace_root,
        code="portfolio_production_target_root_outside_workspace",
    )
    if member_skill_path != "." and not _portable_workspace_path_token(
        member_skill_path
    ):
        raise PortfolioRecordError(
            "portfolio_production_member_skill_path_invalid", member_skill_path
        )
    contract = load_contract_snapshot(run_root)
    check_manifest = load_check_manifest_snapshot(run_root)
    run = load_run(run_root)
    if contract.get("skill_id") != member_skill_id:
        raise PortfolioRecordError(
            "portfolio_production_wrong_member",
            f"expected={member_skill_id};actual={contract.get('skill_id', '')}",
        )
    if (
        contract.get("contract_hash") != member_contract_hash
        or run.get("contract_hash") != member_contract_hash
    ):
        raise PortfolioRecordError(
            "portfolio_production_contract_mismatch", member_skill_id
        )
    if check_manifest.get("manifest_hash") != member_manifest_hash:
        raise PortfolioRecordError(
            "portfolio_production_manifest_mismatch", member_skill_id
        )
    depth_receipts = load_target_execution_receipts(run_root)
    if not depth_receipts:
        raise PortfolioRecordError(
            "portfolio_production_depth_receipt_missing", member_skill_id
        )
    depth_receipt = depth_receipts[-1]
    scheduled_identity = depth_receipt.get("scheduled_production_identity")
    if not isinstance(scheduled_identity, Mapping):
        raise PortfolioRecordError(
            "portfolio_production_installation_identity_missing", member_skill_id
        )
    if verified_installation_context is None:
        raise PortfolioRecordError(
            "portfolio_production_verified_installation_context_required",
            member_skill_id,
        )
    try:
        installation_verification = (
            verify_scheduled_production_installation_identity(
                scheduled_identity,
                verified_context=verified_installation_context,
            )
        )
    except (OSError, TypeError, ValueError) as exc:
        raise PortfolioRecordError(
            "portfolio_production_installation_not_current", str(exc)
        ) from exc
    current_fingerprints = _current_run_fingerprints(run_root)
    depth_gate = evaluate_depth_receipt_gate(
        run_root,
        contract,
        closure_profile="enforced",
        current_fingerprints=current_fingerprints,
        repository_root=member_repository_root,
        target_root=target_root,
        owner_evidence_root=persistent_owner_root,
        verified_installation_context=verified_installation_context,
    )
    if (
        depth_gate.get("ok") is not True
        or depth_gate.get("status") != EXECUTION_DEPTH_PASS
        or depth_gate.get("receipt_id") != depth_receipt.get("receipt_id")
        or depth_receipt.get("evidence_domain") != "scheduled_production"
    ):
        raise PortfolioRecordError(
            "portfolio_production_depth_not_current",
            str(depth_gate.get("detail", "")),
        )
    closure = load_closure(run_root, closure_receipt_id)
    if closure.get("profile") != "enforced":
        raise PortfolioRecordError(
            "portfolio_production_enforced_closure_required",
            str(closure.get("profile", "")),
        )
    closure_verification = verify_closure(
        run_root,
        closure_receipt_id,
        current_fingerprints=current_fingerprints,
        receipt_roots=(run_root,),
        target_root=target_root,
        repository_root=member_repository_root,
        owner_evidence_root=persistent_owner_root,
        verified_installation_context=verified_installation_context,
    )
    if (
        closure_verification.get("ok") is not True
        or closure_verification.get("status") != "current"
    ):
        raise PortfolioRecordError(
            "portfolio_production_enforced_closure_not_current",
            ",".join(
                str(item) for item in closure_verification.get("findings", [])
            ),
        )
    terminal_result = closure.get("native_terminal_result")
    if not isinstance(terminal_result, Mapping) or terminal_result.get(
        "status"
    ) != "verified":
        raise PortfolioRecordError(
            "portfolio_production_native_terminal_missing", member_skill_id
        )
    terminal_ref = terminal_result.get("native_terminal_receipt_ref")
    if not isinstance(terminal_ref, Mapping):
        raise PortfolioRecordError(
            "portfolio_production_native_terminal_missing", member_skill_id
        )
    terminal = resolve_native_terminal_receipt(
        run_root,
        contract,
        run,
        profile="enforced",
        artifact_ref=terminal_ref,
        expected_route_id=str(terminal_result.get("native_route_id", "")),
        expected_branch_id=str(terminal_result.get("branch_id", "")),
        verified_installation_context=verified_installation_context,
    )
    if terminal.receipt.get("closure_disposition") != "terminal_completion":
        code = (
            "portfolio_production_nonterminal_closure_cannot_promote"
            if terminal.receipt.get("closure_disposition")
            == "non_terminal_authorization"
            else "portfolio_production_terminal_completion_required"
        )
        raise PortfolioRecordError(code, member_skill_id)
    consumed = {str(item) for item in closure.get("consumed_receipt_ids", [])}
    if str(depth_receipt.get("receipt_id", "")) not in consumed:
        raise PortfolioRecordError(
            "portfolio_production_depth_not_consumed", member_skill_id
        )
    if str(terminal.receipt.get("receipt_id", "")) not in consumed:
        raise PortfolioRecordError(
            "portfolio_production_terminal_not_consumed", member_skill_id
        )

    profile = contract.get("depth_profile")
    if not isinstance(profile, Mapping):
        raise PortfolioRecordError(
            "portfolio_production_depth_profile_missing", member_skill_id
        )
    installation_receipt = installation_verification.get("receipt")
    if (
        not isinstance(installation_receipt, Mapping)
        or installation_receipt.get("schema_version")
        != INSTALL_VERIFICATION_SCHEMA
        or installation_receipt.get("status") != "current_installed_parity"
    ):
        raise PortfolioRecordError(
            "portfolio_production_installation_receipt_invalid", member_skill_id
        )
    runtime_fingerprint = str(
        scheduled_identity.get("installed_runtime_fingerprint", "")
    )
    depth_ref = reference_existing_file(
        run_root
        / "depth-receipts"
        / f"{str(depth_receipt.get('receipt_id', ''))}.json",
        workspace_root,
    )
    closure_ref = reference_existing_file(
        run_root / "closures" / f"{closure_receipt_id}.json", workspace_root
    )
    terminal_record_ref = _run_root_artifact_record_ref(
        run_root,
        terminal.receipt_ref,
        workspace_root,
        code="portfolio_production_native_terminal_ref_invalid",
    )
    conditional = bool(
        contract.get("route_branch_closure_required") is True
        or any(
            isinstance(row, Mapping) and row.get("conditional") is True
            for row in contract.get("obligations", [])
        )
    )
    binding: dict[str, Any] = {
        "schema_version": PORTFOLIO_PRODUCTION_REVALIDATION_SCHEMA,
        "member_skill_id": member_skill_id,
        "member_skill_path": member_skill_path,
        "source_fingerprint": source_fingerprint,
        "member_contract_hash": member_contract_hash,
        "member_manifest_hash": member_manifest_hash,
        "run_root_token": run_root_token,
        "target_root_token": target_root_token,
        "run_id": str(run.get("run_id", "")),
        "target_skill_id": str(contract.get("skill_id", "")),
        "depth_profile_hash": canonical_hash(profile),
        "native_owner_id": str(profile.get("native_owner_id", "")),
        "native_route_id": terminal.route_id,
        "native_check_id": str(terminal.receipt.get("native_check_id", "")),
        "evidence_domain": "scheduled_production",
        "depth_receipt": {
            "ref": depth_ref,
            "receipt_id": str(depth_receipt.get("receipt_id", "")),
            "receipt_hash": str(depth_receipt.get("receipt_hash", "")),
            "status": str(depth_receipt.get("status", "")),
            "evidence_domain": str(depth_receipt.get("evidence_domain", "")),
        },
        "enforced_closure": {
            "ref": closure_ref,
            "receipt_id": str(closure.get("closure_receipt_id", "")),
            "receipt_hash": str(closure.get("closure_hash", "")),
            "profile": str(closure.get("profile", "")),
            "status": str(closure.get("status", "")),
            "consumed_receipt_ids": sorted(consumed),
        },
        "native_terminal": {
            "ref": terminal_record_ref,
            "receipt_id": str(terminal.receipt.get("receipt_id", "")),
            "receipt_hash": str(terminal.receipt.get("receipt_hash", "")),
            "closure_profile": str(
                terminal.receipt.get("closure_profile", "")
            ),
            "closure_disposition": str(
                terminal.receipt.get("closure_disposition", "")
            ),
            "evidence_domain": str(
                terminal.receipt.get("evidence_domain", "")
            ),
            "conditional": conditional,
            "native_route_id": terminal.route_id,
            "branch_id": terminal.branch_id,
        },
        "installation_identity": {
            "scheduler_or_trigger_id": str(
                scheduled_identity.get("scheduler_or_trigger_id", "")
            ),
            "scheduled_execution_id": str(
                scheduled_identity.get("scheduled_execution_id", "")
            ),
            "installation_receipt_id": str(
                scheduled_identity.get("installation_receipt_id", "")
            ),
            "installation_receipt_hash": str(
                scheduled_identity.get("installation_receipt_hash", "")
            ),
            "installation_receipt_root_ref": dict(
                scheduled_identity.get("installation_receipt_root_ref", {})
            ),
            "installed_runtime_fingerprint": runtime_fingerprint,
            "transaction_id": str(installation_receipt.get("transaction_id", "")),
            "stage_verification_hash": str(
                installation_receipt.get("stage_verification_hash", "")
            ),
            "post_activation_smoke_hash": str(
                installation_receipt.get("post_activation_smoke_hash", "")
            ),
            "post_activation_member_comparisons_hash": str(
                installation_receipt.get(
                    "post_activation_member_comparisons_hash", ""
                )
            ),
            "current_installed_smoke_hash": str(
                installation_receipt.get("current_installed_smoke_hash", "")
            ),
            "current_installed_smoke_command_fingerprint": str(
                installation_receipt.get(
                    "current_installed_smoke_command_fingerprint", ""
                )
            ),
            "current_installed_smoke_environment_fingerprint": str(
                installation_receipt.get(
                    "current_installed_smoke_environment_fingerprint", ""
                )
            ),
            "rollback_disposition": str(
                installation_receipt.get("rollback_disposition", "")
            ),
        },
        "captured_at": max(
            str(depth_receipt.get("created_at", "")),
            str(closure.get("created_at", "")),
        ),
        "claim_boundary": (
            "This member binding proves one current scheduled-production declared-check receipt, "
            "terminal-completion native outcome, enforced closure, and current installed SkillGuard identity. "
            "It does not substitute for capability inventory jobs or another suite member."
        ),
    }
    binding["binding_hash"] = canonical_hash(binding)
    shape_findings = _production_revalidation_binding_shape_findings(
        binding, expected_member_skill_id=member_skill_id
    )
    if shape_findings:
        raise PortfolioRecordError(
            "portfolio_production_binding_invalid",
            ",".join(str(row.get("code", "")) for row in shape_findings),
        )
    return binding


def replay_portfolio_production_revalidation_binding(
    binding: Mapping[str, Any],
    *,
    expected_member_skill_id: str,
    expected_member_skill_path: str,
    expected_source_fingerprint: str,
    expected_member_contract_hash: str,
    expected_member_manifest_hash: str,
    member_repository_root: Path,
    workspace_root: Path,
    verified_installation_context: object | None = None,
) -> list[dict[str, str]]:
    """Rebuild one production binding; caller labels never authorize graduation."""

    findings = _production_revalidation_binding_shape_findings(
        binding, expected_member_skill_id=expected_member_skill_id
    )
    if findings:
        return findings
    member_skill_id = str(binding.get("member_skill_id", ""))
    for field, expected in (
        ("member_skill_path", expected_member_skill_path),
        ("source_fingerprint", expected_source_fingerprint),
        ("member_contract_hash", expected_member_contract_hash),
        ("member_manifest_hash", expected_member_manifest_hash),
    ):
        if binding.get(field) != expected:
            findings.append(
                _finding(
                    f"portfolio_production_{field}_mismatch",
                    skill_id=member_skill_id,
                )
            )
    if findings:
        return findings
    workspace_root = workspace_root.resolve()
    run_root = workspace_root / str(binding.get("run_root_token", ""))
    target_root = workspace_root / str(binding.get("target_root_token", ""))
    closure = binding.get("enforced_closure", {})
    if not isinstance(closure, Mapping):
        return [
            _finding(
                "portfolio_production_enforced_closure_missing",
                skill_id=member_skill_id,
            )
        ]
    try:
        rebuilt = build_portfolio_production_revalidation_binding(
            member_skill_id=member_skill_id,
            member_skill_path=expected_member_skill_path,
            source_fingerprint=expected_source_fingerprint,
            member_contract_hash=expected_member_contract_hash,
            member_manifest_hash=expected_member_manifest_hash,
            member_repository_root=member_repository_root,
            run_root=run_root,
            target_root=target_root,
            workspace_root=workspace_root,
            closure_receipt_id=str(closure.get("receipt_id", "")),
            verified_installation_context=verified_installation_context,
        )
    except Exception as exc:
        findings.append(
            _finding(
                getattr(exc, "code", "portfolio_production_replay_failed"),
                skill_id=member_skill_id,
                detail=str(exc),
            )
        )
        return findings
    if dict(rebuilt) != dict(binding):
        findings.append(
            _finding(
                "portfolio_production_binding_not_verifier_derived",
                skill_id=member_skill_id,
            )
        )
    return findings


def _verify_shared_portfolio_installation_context(
    bindings: Sequence[Mapping[str, Any]],
    *,
    verifier: Any | None = None,
    verified_installation_context: object | None = None,
) -> object:
    """Replay one installation identity once, then share its exact snapshot."""

    from .installation_receipt import (
        load_scheduled_production_installation_context,
        validate_verified_installation_context,
        verify_scheduled_production_installation_identity,
    )

    identities: dict[str, Mapping[str, Any]] = {}
    scheduled_identities: list[Mapping[str, Any]] = []
    for binding in bindings:
        installation = binding.get("installation_identity")
        if not isinstance(installation, Mapping):
            raise PortfolioRecordError(
                "portfolio_production_installation_identity_missing",
                str(binding.get("member_skill_id", "")),
            )
        identity = {
            key: installation.get(key)
            for key in (
                "installation_receipt_id",
                "installation_receipt_hash",
                "installation_receipt_root_ref",
                "installed_runtime_fingerprint",
            )
        }
        identities[canonical_hash(identity)] = identity
        scheduled_identities.append(
            {
                "scheduler_or_trigger_id": installation.get(
                    "scheduler_or_trigger_id"
                ),
                "scheduled_execution_id": installation.get(
                    "scheduled_execution_id"
                ),
                **identity,
            }
        )
    if len(identities) != 1:
        raise PortfolioRecordError(
            "portfolio_production_multiple_installation_identities",
            ",".join(sorted(identities)),
        )
    try:
        if verified_installation_context is not None:
            context = validate_verified_installation_context(
                verified_installation_context
            )
            verify_scheduled_production_installation_identity(
                scheduled_identities[0],
                verified_context=context,
            )
        else:
            selected_verifier = (
                verifier or load_scheduled_production_installation_context
            )
            context = selected_verifier(scheduled_identities[0])
            context = validate_verified_installation_context(context)
    except (OSError, TypeError, ValueError) as exc:
        raise PortfolioRecordError(
            "portfolio_production_installation_not_current", str(exc)
        ) from exc
    receipt = context.receipt
    if not isinstance(receipt, Mapping):
        raise PortfolioRecordError(
            "portfolio_production_installation_receipt_invalid", "receipt"
        )
    for binding in bindings:
        installation = binding.get("installation_identity", {})
        if not isinstance(installation, Mapping):
            continue
        for field in (
            "transaction_id",
            "stage_verification_hash",
            "post_activation_smoke_hash",
            "post_activation_member_comparisons_hash",
            "current_installed_smoke_hash",
            "current_installed_smoke_command_fingerprint",
            "current_installed_smoke_environment_fingerprint",
            "rollback_disposition",
        ):
            if installation.get(field) != receipt.get(field):
                raise PortfolioRecordError(
                    f"portfolio_production_installation_{field}_mismatch",
                    str(binding.get("member_skill_id", "")),
                )
    return context


def _load_portfolio_production_revalidation_bindings(
    value: object,
    *,
    target_identity: Mapping[str, Any] | None,
    target_repository_root: Path | None,
    evidence_root: Path | None,
    verified_installation_context: object | None = None,
) -> tuple[
    list[dict[str, str]], list[dict[str, str]], object | None
]:
    findings: list[dict[str, str]] = []
    if not isinstance(value, list) or not value:
        return [], [_finding("graduation_production_revalidation_bindings_missing")], None
    refs = [str(item) for item in value if isinstance(item, str)]
    if len(refs) != len(value) or len(refs) != len(set(refs)):
        return [], [_finding("graduation_production_revalidation_refs_invalid")], None
    if target_identity is None or target_repository_root is None:
        return [], [_finding("graduation_production_target_identity_missing")], None
    if evidence_root is None:
        return [], [_finding("graduation_production_evidence_root_missing")], None
    members = [
        row
        for row in target_identity.get("member_identities", [])
        if isinstance(row, Mapping)
    ]
    required_members = {str(row.get("member_skill_id", "")): row for row in members}
    observed_members: dict[str, dict[str, str]] = {}
    loaded_bindings: list[
        tuple[Mapping[str, Any], Mapping[str, Any], Path]
    ] = []
    for binding_ref in refs:
        binding, _relative, load_findings = _load_hash_bound_json(
            binding_ref,
            evidence_root=evidence_root,
            finding_prefix="graduation_production_binding",
        )
        findings.extend(load_findings)
        if binding is None:
            continue
        member_skill_id = str(binding.get("member_skill_id", ""))
        if not member_skill_id or member_skill_id not in required_members:
            findings.append(
                _finding(
                    "graduation_production_wrong_member",
                    skill_id=member_skill_id,
                    detail=binding_ref,
                )
            )
            continue
        if member_skill_id in observed_members:
            findings.append(
                _finding(
                    "graduation_production_member_binding_duplicate",
                    skill_id=member_skill_id,
                )
            )
            continue
        member = required_members[member_skill_id]
        member_path = str(member.get("skill_path", ""))
        member_repository_root = (
            target_repository_root.resolve() / Path(member_path)
        ).resolve()
        try:
            member_repository_root.relative_to(target_repository_root.resolve())
        except ValueError:
            findings.append(
                _finding(
                    "graduation_production_member_path_escape",
                    skill_id=member_skill_id,
                )
            )
            continue
        loaded_bindings.append((binding, member, member_repository_root))
        observed_members[member_skill_id] = {
            "member_skill_id": member_skill_id,
            "binding_ref": binding_ref,
            "binding_hash": str(binding.get("binding_hash", "")),
        }
    if loaded_bindings:
        try:
            verified_installation_context = (
                _verify_shared_portfolio_installation_context(
                    [row[0] for row in loaded_bindings],
                    verified_installation_context=(
                        verified_installation_context
                    ),
                )
            )
        except PortfolioRecordError as exc:
            findings.append(_finding(exc.code, detail=exc.detail))
    if verified_installation_context is not None:
        for binding, member, member_repository_root in loaded_bindings:
            member_skill_id = str(binding.get("member_skill_id", ""))
            member_path = str(member.get("skill_path", ""))
            findings.extend(
                replay_portfolio_production_revalidation_binding(
                    binding,
                    expected_member_skill_id=member_skill_id,
                    expected_member_skill_path=member_path,
                    expected_source_fingerprint=str(
                        member.get("source_fingerprint", "")
                    ),
                    expected_member_contract_hash=str(
                        member.get("contract_hash", "")
                    ),
                    expected_member_manifest_hash=str(
                        member.get("manifest_hash", "")
                    ),
                    member_repository_root=member_repository_root,
                    workspace_root=evidence_root,
                    verified_installation_context=verified_installation_context,
                )
            )
    for member_skill_id in sorted(set(required_members) - set(observed_members)):
        findings.append(
            _finding(
                "graduation_production_member_binding_missing",
                skill_id=member_skill_id,
            )
        )
    normalized = sorted(
        observed_members.values(), key=lambda row: row["member_skill_id"]
    )
    return normalized, findings, verified_installation_context


def portfolio_production_revalidation_fingerprint(value: object) -> str:
    if not isinstance(value, list) or not value:
        return ""
    rows: list[dict[str, str]] = []
    for row in value:
        if (
            not isinstance(row, Mapping)
            or not str(row.get("member_skill_id", ""))
            or EVIDENCE_REF_RE.fullmatch(str(row.get("binding_ref", ""))) is None
            or not _hash_ok(row.get("binding_hash"))
        ):
            return ""
        rows.append(
            {
                "member_skill_id": str(row["member_skill_id"]),
                "binding_ref": str(row["binding_ref"]),
                "binding_hash": str(row["binding_hash"]),
            }
        )
    rows.sort(key=lambda row: row["member_skill_id"])
    if len({row["member_skill_id"] for row in rows}) != len(rows):
        return ""
    return canonical_hash({"production_revalidation_bindings": rows})


def _internal_hash_matches(record: Mapping[str, Any], field: str) -> bool:
    unsigned = dict(record)
    stored = unsigned.pop(field, None)
    return _hash_ok(stored) and stored == canonical_hash(unsigned)


def _aggregate_member_contract_hash(
    target_skill_id: str,
    members: Sequence[Mapping[str, Any]],
) -> str:
    rows = [
        {
            "member_skill_id": str(member.get("member_skill_id", "")),
            "skill_path": str(member.get("skill_path", "")),
            "contract_hash": str(member.get("contract_hash", "")),
        }
        for member in members
    ]
    rows.sort(key=lambda row: (row["skill_path"], row["member_skill_id"]))
    return canonical_hash(
        {
            "schema_version": "skillguard.target_contract_aggregate.v1",
            "target_skill_id": target_skill_id,
            "target_kind": "skill_suite",
            "members": rows,
        }
    )


def _aggregate_member_manifest_hash(
    target_skill_id: str,
    members: Sequence[Mapping[str, Any]],
) -> str:
    rows = [
        {
            "member_skill_id": str(member.get("member_skill_id", "")),
            "skill_path": str(member.get("skill_path", "")),
            "contract_hash": str(member.get("contract_hash", "")),
            "manifest_hash": str(member.get("manifest_hash", "")),
        }
        for member in members
    ]
    rows.sort(key=lambda row: (row["skill_path"], row["member_skill_id"]))
    return canonical_hash(
        {
            "schema_version": "skillguard.target_manifest_aggregate.v1",
            "target_skill_id": target_skill_id,
            "target_kind": "skill_suite",
            "members": rows,
        }
    )


def _target_identity_findings(identity: object) -> list[dict[str, str]]:
    if not isinstance(identity, Mapping):
        return [_finding("portfolio_target_identity_not_object")]
    skill_id = str(identity.get("skill_id", ""))
    findings: list[dict[str, str]] = []
    if identity.get("schema_version") != TARGET_IDENTITY_SCAN_SCHEMA:
        findings.append(_finding("portfolio_target_identity_schema_unsupported", skill_id=skill_id))
    target_kind = str(identity.get("target_kind", ""))
    if target_kind not in TARGET_KINDS:
        findings.append(_finding("portfolio_target_identity_kind_invalid", skill_id=skill_id))
    members = identity.get("member_identities")
    if not isinstance(members, list) or not members:
        return findings + [_finding("portfolio_target_identity_members_missing", skill_id=skill_id)]
    member_rows = [member for member in members if isinstance(member, Mapping)]
    if len(member_rows) != len(members):
        findings.append(_finding("portfolio_target_identity_member_invalid", skill_id=skill_id))
    member_ids = [str(member.get("member_skill_id", "")) for member in member_rows]
    member_paths = [str(member.get("skill_path", "")) for member in member_rows]
    for member in member_rows:
        if (
            not str(member.get("member_skill_id", ""))
            or not str(member.get("skill_path", ""))
            or not _hash_ok(member.get("source_fingerprint"))
            or not _hash_ok(member.get("contract_hash"))
            or not _hash_ok(member.get("manifest_hash"))
            or re.fullmatch(
                r"sha256:[0-9a-f]{64}",
                str(member.get("portfolio_projection_hash", "")),
            )
            is None
        ):
            findings.append(
                _finding(
                    "portfolio_target_identity_member_invalid",
                    skill_id=skill_id,
                    detail=str(member.get("member_skill_id", "")),
                )
            )
    if len(member_ids) != len(set(member_ids)) or any(not value for value in member_ids):
        findings.append(_finding("portfolio_target_identity_member_id_duplicate", skill_id=skill_id))
    if len(member_paths) != len(set(member_paths)) or any(not value for value in member_paths):
        findings.append(_finding("portfolio_target_identity_member_path_duplicate", skill_id=skill_id))
    declared_paths = _unique_string_list(identity.get("skill_paths"))
    if declared_paths is None or sorted(declared_paths) != sorted(member_paths):
        findings.append(_finding("portfolio_target_identity_member_path_set_mismatch", skill_id=skill_id))
    primary_path = str(identity.get("skill_root_token", ""))
    primary_member = next(
        (member for member in member_rows if member.get("skill_path") == primary_path),
        None,
    )
    if primary_member is None:
        findings.append(_finding("portfolio_target_identity_primary_member_invalid", skill_id=skill_id))
    if target_kind == "single_skill":
        if len(member_rows) != 1:
            findings.append(_finding("portfolio_target_identity_single_cardinality_invalid", skill_id=skill_id))
        elif (
            identity.get("contract_hash") != member_rows[0].get("contract_hash")
            or identity.get("manifest_hash") != member_rows[0].get("manifest_hash")
        ):
            findings.append(_finding("portfolio_target_identity_single_projection_invalid", skill_id=skill_id))
    elif target_kind == "skill_suite":
        if len(member_rows) < 2:
            findings.append(_finding("portfolio_target_identity_suite_cardinality_invalid", skill_id=skill_id))
        elif (
            identity.get("contract_hash")
            != _aggregate_member_contract_hash(skill_id, member_rows)
            or identity.get("manifest_hash")
            != _aggregate_member_manifest_hash(skill_id, member_rows)
        ):
            findings.append(_finding("portfolio_target_identity_suite_projection_invalid", skill_id=skill_id))
    if (
        not skill_id
        or not _hash_ok(identity.get("source_fingerprint"))
        or not _hash_ok(identity.get("contract_hash"))
        or not _hash_ok(identity.get("manifest_hash"))
        or not _guard_ok(identity.get("guard_runtime"))
        or not _internal_hash_matches(identity, "receipt_hash")
    ):
        findings.append(_finding("portfolio_target_identity_integrity_invalid", skill_id=skill_id))
    return findings


def _target_identity_member(
    identity: Mapping[str, Any],
    member_skill_id: str,
) -> Mapping[str, Any] | None:
    members = identity.get("member_identities")
    if not isinstance(members, list):
        return None
    return next(
        (
            member
            for member in members
            if isinstance(member, Mapping)
            and member.get("member_skill_id") == member_skill_id
        ),
        None,
    )


def _evidence_record_findings(
    record: object,
    *,
    evidence_ref: str,
) -> list[dict[str, str]]:
    if not isinstance(record, Mapping):
        return [_finding("portfolio_evidence_record_not_object", detail=evidence_ref)]
    findings: list[dict[str, str]] = []
    if record.get("schema_version") != PORTFOLIO_JOB_EVIDENCE_SCHEMA:
        findings.append(_finding("portfolio_evidence_record_schema_unsupported", detail=evidence_ref))
    if not isinstance(record.get("record_id"), str) or not record.get("record_id"):
        findings.append(_finding("portfolio_evidence_record_id_missing", detail=evidence_ref))
    if not isinstance(record.get("registry_id"), str) or not record.get("registry_id"):
        findings.append(_finding("portfolio_evidence_record_registry_missing", detail=evidence_ref))
    if (
        not isinstance(record.get("scope_manifest_id"), str)
        or not record.get("scope_manifest_id")
        or not _hash_ok(record.get("scope_manifest_hash"))
    ):
        findings.append(_finding("portfolio_evidence_record_scope_missing", detail=evidence_ref))
    if not isinstance(record.get("skill_id"), str) or not record.get("skill_id"):
        findings.append(_finding("portfolio_evidence_record_skill_missing", detail=evidence_ref))
    if (
        not isinstance(record.get("member_skill_id"), str)
        or not record.get("member_skill_id")
        or not _hash_ok(record.get("member_contract_hash"))
    ):
        findings.append(
            _finding("portfolio_evidence_record_member_binding_invalid", detail=evidence_ref)
        )
    target_kind = str(record.get("target_kind", ""))
    skill_paths = _unique_string_list(record.get("skill_paths"))
    if (
        target_kind not in TARGET_KINDS
        or not skill_paths
        or (target_kind == "single_skill" and len(skill_paths) != 1)
        or (target_kind == "skill_suite" and len(skill_paths) < 2)
    ):
        findings.append(
            _finding("portfolio_evidence_record_target_topology_invalid", detail=evidence_ref)
        )
    if not isinstance(record.get("job_id"), str) or not record.get("job_id"):
        findings.append(_finding("portfolio_evidence_record_job_missing", detail=evidence_ref))
    job_class_id = str(record.get("job_class_id", ""))
    if job_class_id not in JOB_CLASS_IDS:
        findings.append(_finding("portfolio_evidence_record_job_class_invalid", detail=evidence_ref))
    if (
        not isinstance(record.get("preparation_id"), str)
        or not record.get("preparation_id")
        or not isinstance(record.get("preparation_receipt_ref"), str)
        or EVIDENCE_REF_RE.fullmatch(
            str(record.get("preparation_receipt_ref", ""))
        )
        is None
        or not _hash_ok(record.get("preparation_receipt_hash"))
    ):
        findings.append(
            _finding(
                "portfolio_evidence_record_preparation_invalid",
                detail=evidence_ref,
            )
        )
    if (
        not isinstance(record.get("job_plan_ref"), str)
        or EVIDENCE_REF_RE.fullmatch(str(record.get("job_plan_ref", ""))) is None
        or not _hash_ok(record.get("job_plan_hash"))
    ):
        findings.append(_finding("portfolio_evidence_record_job_plan_invalid", detail=evidence_ref))
    if (
        not isinstance(record.get("job_spec_ref"), str)
        or EVIDENCE_REF_RE.fullmatch(str(record.get("job_spec_ref", ""))) is None
        or not _hash_ok(record.get("job_spec_hash"))
    ):
        findings.append(_finding("portfolio_evidence_record_job_spec_invalid", detail=evidence_ref))
    capabilities = _unique_string_list(record.get("covered_capability_ids"))
    if capabilities is None or not capabilities:
        findings.append(_finding("portfolio_evidence_record_capabilities_invalid", detail=evidence_ref))
    evidence_class = str(record.get("evidence_class", ""))
    if evidence_class not in EVIDENCE_CLASSES:
        findings.append(_finding("portfolio_evidence_record_class_invalid", detail=evidence_ref))
    if record.get("status") != "current":
        findings.append(_finding("portfolio_evidence_record_not_current", detail=evidence_ref))
    expected_outcome = JOB_CLASS_EXPECTED_OUTCOMES.get(job_class_id, "")
    if (
        not expected_outcome
        or record.get("expected_outcome") != expected_outcome
        or record.get("observed_outcome") != expected_outcome
    ):
        findings.append(_finding("portfolio_evidence_record_outcome_invalid", detail=evidence_ref))
    target_identity = record.get("target_identity_receipt")
    if (
        not isinstance(target_identity, Mapping)
        or not isinstance(target_identity.get("ref"), str)
        or EVIDENCE_REF_RE.fullmatch(str(target_identity.get("ref", ""))) is None
        or not isinstance(target_identity.get("receipt_id"), str)
        or not target_identity.get("receipt_id")
        or not _hash_ok(target_identity.get("receipt_hash"))
    ):
        findings.append(
            _finding("portfolio_evidence_record_target_identity_invalid", detail=evidence_ref)
        )
    if not _guard_ok(record.get("guard_runtime")):
        findings.append(_finding("portfolio_evidence_record_guard_invalid", detail=evidence_ref))
    if not _hash_ok(record.get("source_fingerprint")) or not _hash_ok(record.get("contract_hash")):
        findings.append(_finding("portfolio_evidence_record_identity_invalid", detail=evidence_ref))
    payload = record.get("payload")
    if not isinstance(payload, Mapping) or not payload:
        findings.append(_finding("portfolio_evidence_record_payload_missing", detail=evidence_ref))
    elif record.get("payload_hash") != canonical_hash(payload):
        findings.append(_finding("portfolio_evidence_record_payload_hash_mismatch", detail=evidence_ref))
    if isinstance(payload, Mapping):
        required_refs = (
            "run_record_ref",
            "contract_snapshot_ref",
            "check_manifest_snapshot_ref",
            "job_plan_snapshot_ref",
            "job_spec_snapshot_ref",
            "event_log_ref",
            "runtime_receipt_ref",
            "closure_receipt_ref",
        )
        if evidence_class == "hard":
            required_refs = (*required_refs, "check_record_ref")
        if record.get("job_class_id") == "artifact_check":
            required_refs = (*required_refs, "artifact_record_ref")
        if record.get("preparation_id"):
            required_refs = (*required_refs, "preparation_snapshot_ref")
        if record.get("job_class_id") in {"invalid_input", "out_of_scope"} and (
            payload.get("terminal_observation_ref")
            or payload.get("mutation_observation_ref")
        ):
            required_refs = (
                *required_refs,
                "terminal_observation_ref",
                "mutation_observation_ref",
            )
        for field in required_refs:
            value = payload.get(field)
            if not isinstance(value, str) or EVIDENCE_REF_RE.fullmatch(value) is None:
                findings.append(
                    _finding("portfolio_runtime_evidence_ref_invalid", detail=f"{evidence_ref}:{field}")
                )
        target_root_token = payload.get("target_root_token")
        if target_root_token is not None and not _portable_workspace_path_token(
            target_root_token
        ):
            findings.append(
                _finding(
                    "portfolio_runtime_target_root_token_invalid",
                    detail=evidence_ref,
                )
            )
    if not _timestamp_ok(record.get("created_at")):
        findings.append(_finding("portfolio_evidence_record_timestamp_invalid", detail=evidence_ref))
    if not _internal_hash_matches(record, "record_hash"):
        findings.append(_finding("portfolio_evidence_record_hash_mismatch", detail=evidence_ref))
    return findings


def _runtime_execution_coverage_findings(
    run: Mapping[str, Any],
    job_spec: Mapping[str, Any],
    *,
    run_root: Path,
    owner_evidence_root: Path,
) -> list[dict[str, str]]:
    """Bind a claimed capability path to the route and every check actually run."""

    from .check_runner import (
        CheckRunnerError,
        load_check_result,
        load_owner_receipt_from_projection,
    )
    from .receipts import load_receipts
    from .step_runtime import resume_run

    job_id = str(job_spec.get("job_id", ""))
    bindings, binding_findings = _normalized_capability_bindings(
        job_spec.get("capability_bindings")
    )
    if binding_findings:
        return [
            _finding(
                "portfolio_runtime_capability_binding_invalid",
                detail=f"{job_id}:{code}",
            )
            for code in binding_findings
        ]
    bound_function_ids = {
        function_id for row in bindings for function_id in row["function_ids"]
    }
    bound_route_ids = {
        route_id for row in bindings for route_id in row["route_ids"]
    }
    bound_step_ids = {step_id for row in bindings for step_id in row["step_ids"]}
    required_check_ids = set(
        _unique_string_list(job_spec.get("required_check_ids")) or []
    )
    request = run.get("request") if isinstance(run.get("request"), Mapping) else {}
    actual_function_ids = set(_unique_string_list(request.get("function_ids")) or [])
    actual_route_ids = set(_unique_string_list(run.get("route_ids")) or [])
    findings: list[dict[str, str]] = []
    if actual_function_ids != bound_function_ids:
        findings.append(
            _finding(
                "portfolio_runtime_selected_function_binding_invalid",
                detail=(
                    f"{job_id}:expected={','.join(sorted(bound_function_ids))};"
                    f"actual={','.join(sorted(actual_function_ids))}"
                ),
            )
        )
    if actual_route_ids != bound_route_ids:
        findings.append(
            _finding(
                "portfolio_runtime_selected_route_binding_invalid",
                detail=(
                    f"{job_id}:expected={','.join(sorted(bound_route_ids))};"
                    f"actual={','.join(sorted(actual_route_ids))}"
                ),
            )
        )

    state = resume_run(run_root)
    passed_or_skipped_steps = {
        str(step_id)
        for step_id, status in state.step_statuses.items()
        if status in {"passed", "skipped"}
    }
    if not bound_step_ids.issubset(passed_or_skipped_steps):
        findings.append(
            _finding(
                "portfolio_runtime_selected_step_binding_incomplete",
                detail=(
                    f"{job_id}:missing="
                    f"{','.join(sorted(bound_step_ids - passed_or_skipped_steps))}"
                ),
            )
        )

    check_records: list[Mapping[str, Any]] = []
    checks_root = run_root / "checks"
    if checks_root.is_dir():
        for path in sorted(checks_root.glob("check-record-*.json")):
            check_records.append(load_check_result(run_root, path.stem))
    passed_check_records: list[Mapping[str, Any]] = []
    for record in check_records:
        if record.get("status") != "passed" or record.get(
            "execution_disposition"
        ) not in {"executed_terminal_success", "reused_terminal_success"}:
            continue
        try:
            load_owner_receipt_from_projection(owner_evidence_root, record)
        except (CheckRunnerError, OSError, ValueError) as exc:
            findings.append(
                _finding(
                    "portfolio_runtime_owner_receipt_invalid",
                    detail=f"{job_id}:{getattr(exc, 'code', type(exc).__name__)}",
                )
            )
            continue
        passed_check_records.append(record)
    actual_check_ids = {
        str(record.get("check_id") or record.get("result", {}).get("check_id", ""))
        for record in passed_check_records
    }
    if not required_check_ids.issubset(actual_check_ids):
        findings.append(
            _finding(
                "portfolio_runtime_required_check_execution_incomplete",
                detail=(
                    f"{job_id}:missing="
                    f"{','.join(sorted(required_check_ids - actual_check_ids))}"
                ),
            )
        )
    receipts = load_receipts(run_root)
    receipted_check_record_ids = {
        str(receipt.get("evidence", {}).get("check_record_id", ""))
        for receipt in receipts
        if receipt.get("status") == "passed"
        and receipt.get("evidence_class") == "hard"
        and isinstance(receipt.get("evidence"), Mapping)
        and receipt.get("evidence", {}).get("proof_kind")
        == "owner_receipt_projection"
    }
    required_record_ids = {
        str(record.get("check_record_id", ""))
        for record in passed_check_records
        if str(record.get("check_id") or record.get("result", {}).get("check_id", ""))
        in required_check_ids
    }
    if not required_record_ids or not required_record_ids.issubset(
        receipted_check_record_ids
    ):
        findings.append(
            _finding(
                "portfolio_runtime_required_check_receipt_incomplete",
                detail=(
                    f"{job_id}:missing="
                    f"{','.join(sorted(required_record_ids - receipted_check_record_ids))}"
                ),
            )
        )
    return findings


def _runtime_evidence_findings(
    record: Mapping[str, Any],
    *,
    evidence_ref: str,
    evidence_root: Path | None,
) -> list[dict[str, str]]:
    payload = record.get("payload")
    if not isinstance(payload, Mapping):
        return [_finding("portfolio_runtime_evidence_payload_missing", detail=evidence_ref)]
    loaded: dict[str, Mapping[str, Any]] = {}
    paths: dict[str, Path] = {}
    findings: list[dict[str, str]] = []
    job_plan, _job_plan_relative, job_plan_findings = _load_hash_bound_json(
        str(record.get("job_plan_ref", "")),
        evidence_root=evidence_root,
        finding_prefix="portfolio_job_plan",
    )
    findings.extend(job_plan_findings)
    job_spec, _job_spec_relative, job_spec_findings = _load_hash_bound_json(
        str(record.get("job_spec_ref", "")),
        evidence_root=evidence_root,
        finding_prefix="portfolio_job_spec",
    )
    findings.extend(job_spec_findings)
    preparation_ref = str(record.get("preparation_receipt_ref", ""))
    preparation, _preparation_relative, preparation_findings = (
        _load_hash_bound_json(
            preparation_ref,
            evidence_root=evidence_root,
            finding_prefix="portfolio_preparation_receipt",
        )
    )
    findings.extend(preparation_findings)
    identity_binding = record.get("target_identity_receipt")
    identity_ref = (
        str(identity_binding.get("ref", ""))
        if isinstance(identity_binding, Mapping)
        else ""
    )
    target_identity, _identity_relative, identity_findings = _load_hash_bound_json(
        identity_ref,
        evidence_root=evidence_root,
        finding_prefix="portfolio_target_identity_receipt",
    )
    findings.extend(identity_findings)
    if job_plan is not None:
        findings.extend(_job_plan_findings(job_plan, record=record))
        if (
            job_plan.get("job_plan_hash") != record.get("job_plan_hash")
            or job_plan.get("registry_id") != record.get("registry_id")
            or job_plan.get("scope_manifest_id") != record.get("scope_manifest_id")
            or job_plan.get("scope_manifest_hash") != record.get("scope_manifest_hash")
            or job_plan.get("skill_id") != record.get("skill_id")
            or job_plan.get("target_kind") != record.get("target_kind")
            or sorted(job_plan.get("skill_paths", []))
            != sorted(record.get("skill_paths", []))
        ):
            findings.append(
                _finding("portfolio_job_plan_binding_invalid", detail=evidence_ref)
            )
    if job_spec is not None:
        if (
            job_spec.get("schema_version") != PORTFOLIO_JOB_SPEC_SCHEMA
            or not _internal_hash_matches(job_spec, "job_spec_hash")
            or job_spec.get("job_spec_hash") != record.get("job_spec_hash")
            or job_spec.get("registry_id") != record.get("registry_id")
            or job_spec.get("scope_manifest_id") != record.get("scope_manifest_id")
            or job_spec.get("scope_manifest_hash") != record.get("scope_manifest_hash")
            or job_spec.get("skill_id") != record.get("skill_id")
            or job_spec.get("target_kind") != record.get("target_kind")
            or sorted(job_spec.get("skill_paths", []))
            != sorted(record.get("skill_paths", []))
            or job_spec.get("member_skill_id") != record.get("member_skill_id")
            or job_spec.get("member_contract_hash") != record.get("member_contract_hash")
            or job_spec.get("job_id") != record.get("job_id")
            or job_spec.get("job_class_id") != record.get("job_class_id")
            or sorted(job_spec.get("covered_capability_ids", []))
            != sorted(record.get("covered_capability_ids", []))
            or job_spec.get("expected_outcome") != record.get("expected_outcome")
        ):
            findings.append(_finding("portfolio_job_spec_binding_invalid", detail=evidence_ref))
    if preparation is not None:
        unsigned_preparation = dict(preparation)
        stored_preparation_hash = unsigned_preparation.pop("receipt_hash", None)
        preparation_specs = {
            str(row.get("job_id", "")): row
            for row in preparation.get("job_specs", [])
            if isinstance(row, Mapping)
        }
        prepared_spec = preparation_specs.get(str(record.get("job_id", "")))
        target_binding = preparation.get("target_identity_receipt")
        if (
            preparation.get("schema_version") != PORTFOLIO_PREPARATION_SCHEMA
            or preparation.get("status") != "prepared"
            or preparation.get("receipt_id") != record.get("preparation_id")
            or preparation.get("preparation_id") != record.get("preparation_id")
            or stored_preparation_hash != record.get("preparation_receipt_hash")
            or stored_preparation_hash != canonical_hash(unsigned_preparation)
            or preparation.get("registry_id") != record.get("registry_id")
            or preparation.get("scope_manifest_id")
            != record.get("scope_manifest_id")
            or preparation.get("scope_manifest_hash")
            != record.get("scope_manifest_hash")
            or preparation.get("skill_id") != record.get("skill_id")
            or preparation.get("target_kind") != record.get("target_kind")
            or sorted(preparation.get("skill_paths", []))
            != sorted(record.get("skill_paths", []))
            or not _same_guard(
                preparation.get("guard_runtime"), record.get("guard_runtime")
            )
            or preparation.get("job_plan_ref") != record.get("job_plan_ref")
            or preparation.get("job_plan_hash") != record.get("job_plan_hash")
            or not isinstance(prepared_spec, Mapping)
            or prepared_spec.get("job_spec_ref") != record.get("job_spec_ref")
            or prepared_spec.get("job_spec_hash") != record.get("job_spec_hash")
            or not isinstance(target_binding, Mapping)
            or not isinstance(identity_binding, Mapping)
            or dict(target_binding) != dict(identity_binding)
        ):
            findings.append(
                _finding(
                    "portfolio_preparation_receipt_binding_invalid",
                    detail=evidence_ref,
                )
            )
    if target_identity is not None:
        target_identity_shape_findings = _target_identity_findings(target_identity)
        findings.extend(target_identity_shape_findings)
        member_identity = _target_identity_member(
            target_identity,
            str(record.get("member_skill_id", "")),
        )
        if (
            target_identity_shape_findings
            or not isinstance(identity_binding, Mapping)
            or target_identity.get("receipt_id") != identity_binding.get("receipt_id")
            or target_identity.get("receipt_hash") != identity_binding.get("receipt_hash")
            or target_identity.get("skill_id") != record.get("skill_id")
            or target_identity.get("target_kind") != record.get("target_kind")
            or sorted(target_identity.get("skill_paths", []))
            != sorted(record.get("skill_paths", []))
            or target_identity.get("source_fingerprint")
            != record.get("source_fingerprint")
            or target_identity.get("contract_hash") != record.get("contract_hash")
            or not _same_guard(
                target_identity.get("guard_runtime"), record.get("guard_runtime")
            )
            or member_identity is None
            or member_identity.get("contract_hash")
            != record.get("member_contract_hash")
        ):
            findings.append(
                _finding("portfolio_target_identity_binding_invalid", detail=evidence_ref)
            )
    required_refs = [
        "run_record_ref",
        "contract_snapshot_ref",
        "check_manifest_snapshot_ref",
        "preparation_snapshot_ref",
        "job_plan_snapshot_ref",
        "job_spec_snapshot_ref",
        "runtime_receipt_ref",
        "closure_receipt_ref",
    ]
    if record.get("evidence_class") == "hard":
        required_refs.append("check_record_ref")
    if record.get("job_class_id") == "artifact_check":
        required_refs.append("artifact_record_ref")
    if record.get("job_class_id") in {"invalid_input", "out_of_scope"}:
        required_refs.extend(
            ["terminal_observation_ref", "mutation_observation_ref"]
        )
    for field in required_refs:
        ref = payload.get(field)
        if not isinstance(ref, str) or EVIDENCE_REF_RE.fullmatch(ref) is None:
            findings.append(
                _finding(
                    f"portfolio_{field.removesuffix('_ref')}_ref_invalid",
                    detail=evidence_ref,
                )
            )
            continue
        item, relative, item_findings = _load_hash_bound_json(
            ref,
            evidence_root=evidence_root,
            finding_prefix=f"portfolio_{field.removesuffix('_ref')}",
        )
        findings.extend(item_findings)
        if item is not None and relative is not None:
            loaded[field] = item
            paths[field] = relative
    event_ref = payload.get("event_log_ref")
    if isinstance(event_ref, str):
        _event_bytes, event_relative, event_findings = _load_hash_bound_bytes(
            event_ref,
            evidence_root=evidence_root,
            finding_prefix="portfolio_event_log",
        )
        findings.extend(event_findings)
        if event_relative is not None and not event_findings:
            paths["event_log_ref"] = event_relative
    else:
        findings.append(_finding("portfolio_event_log_ref_invalid", detail=evidence_ref))
    if findings or any(field not in loaded for field in required_refs):
        return findings

    run = loaded["run_record_ref"]
    contract = loaded["contract_snapshot_ref"]
    check_manifest = loaded["check_manifest_snapshot_ref"]
    job_plan_snapshot = loaded["job_plan_snapshot_ref"]
    job_spec_snapshot = loaded["job_spec_snapshot_ref"]
    preparation_snapshot = loaded.get("preparation_snapshot_ref")
    terminal_observation = loaded.get("terminal_observation_ref")
    mutation_observation = loaded.get("mutation_observation_ref")
    receipt = loaded["runtime_receipt_ref"]
    closure = loaded["closure_receipt_ref"]
    run_id = str(run.get("run_id", ""))
    skill_id = str(record.get("member_skill_id", ""))
    contract_hash = str(record.get("member_contract_hash", ""))

    run_root = paths["run_record_ref"].parent
    absolute_target_root: Path | None = None
    target_root_token = payload.get("target_root_token")
    if target_root_token is not None:
        if (
            evidence_root is None
            or not _portable_workspace_path_token(target_root_token)
        ):
            findings.append(
                _finding(
                    "portfolio_runtime_target_root_token_invalid",
                    detail=evidence_ref,
                )
            )
        else:
            candidate = (evidence_root.resolve() / Path(str(target_root_token))).resolve()
            try:
                candidate.relative_to(evidence_root.resolve())
            except ValueError:
                findings.append(
                    _finding(
                        "portfolio_runtime_target_root_token_escape",
                        detail=evidence_ref,
                    )
                )
            else:
                if not candidate.is_dir():
                    findings.append(
                        _finding(
                            "portfolio_runtime_target_root_missing",
                            detail=evidence_ref,
                        )
                    )
                else:
                    absolute_target_root = candidate
    topology_ok = (
        paths["run_record_ref"].name == "run.json"
        and paths["contract_snapshot_ref"] == run_root / "contract.json"
        and paths["check_manifest_snapshot_ref"]
        == run_root / "check-manifest.json"
        and paths["job_plan_snapshot_ref"]
        == run_root / "claim" / "portfolio-job-plan.json"
        and paths["job_spec_snapshot_ref"]
        == run_root / "claim" / "portfolio-job-spec.json"
        and paths.get("event_log_ref") == run_root / "events.jsonl"
        and paths["runtime_receipt_ref"].parent == run_root / "receipts"
        and paths["closure_receipt_ref"].parent == run_root / "closures"
    )
    if preparation_snapshot is not None:
        topology_ok = (
            topology_ok
            and paths["preparation_snapshot_ref"]
            == run_root / "claim" / "portfolio-preparation.json"
        )
    if record.get("evidence_class") == "hard":
        topology_ok = topology_ok and paths["check_record_ref"].parent == run_root / "checks"
    if record.get("job_class_id") == "artifact_check":
        topology_ok = topology_ok and paths["artifact_record_ref"].parent == run_root / "artifacts"
    if not topology_ok:
        findings.append(_finding("portfolio_runtime_record_topology_mismatch", detail=evidence_ref))

    if (
        run.get("schema_version") != "skillguard.run.v2"
        or not run_id
        or run.get("skill_id") != skill_id
        or run.get("contract_hash") != contract_hash
        or run.get("status") not in {"claimed", "running", "closed"}
    ):
        findings.append(_finding("portfolio_runtime_run_record_invalid", detail=evidence_ref))
    if (
        contract.get("schema_version") != "skillguard.compiled_contract.v2"
        or contract.get("skill_id") != skill_id
        or contract.get("contract_hash") != contract_hash
        or not _internal_hash_matches(contract, "contract_hash")
    ):
        findings.append(_finding("portfolio_runtime_contract_snapshot_invalid", detail=evidence_ref))
    target_member_identity = (
        _target_identity_member(
            target_identity,
            str(record.get("member_skill_id", "")),
        )
        if isinstance(target_identity, Mapping)
        else None
    )
    unsigned_manifest = dict(check_manifest)
    stored_manifest_hash = str(unsigned_manifest.pop("manifest_hash", ""))
    declarations_hash = canonical_hash(check_declarations_payload(check_manifest))
    if (
        check_manifest.get("schema_version") != "skillguard.check_manifest.v2"
        or check_manifest.get("skill_id") != skill_id
        or check_manifest.get("contract_hash") != contract_hash
        or stored_manifest_hash != canonical_hash(unsigned_manifest)
        or check_manifest.get("check_declarations_hash") != declarations_hash
        or contract.get("check_declarations_hash") != declarations_hash
        or run.get("check_manifest_hash") != stored_manifest_hash
        or run.get("check_declarations_hash") != declarations_hash
        or target_member_identity is None
        or target_member_identity.get("manifest_hash") != stored_manifest_hash
    ):
        findings.append(
            _finding(
                "portfolio_runtime_check_manifest_snapshot_invalid",
                detail=evidence_ref,
            )
        )
    snapshot_hashes = run.get("claim_snapshot_hashes", {})
    snapshot_files = run.get("claim_snapshot_files", {})
    job_plan_hash = canonical_hash(job_plan_snapshot)
    job_spec_hash = canonical_hash(job_spec_snapshot)
    request = run.get("request") if isinstance(run.get("request"), Mapping) else {}
    preparation_snapshot_hash = (
        canonical_hash(preparation_snapshot)
        if isinstance(preparation_snapshot, Mapping)
        else ""
    )
    preparation_claim_invalid = bool(
        not isinstance(preparation, Mapping)
        or not isinstance(preparation_snapshot, Mapping)
        or dict(preparation_snapshot) != dict(preparation)
        or snapshot_hashes.get("portfolio-preparation")
        != preparation_snapshot_hash
        or snapshot_files.get("portfolio-preparation")
        != "claim/portfolio-preparation.json"
        or request.get("portfolio_preparation_id")
        != record.get("preparation_id")
        or request.get("portfolio_preparation_ref")
        != record.get("preparation_receipt_ref")
        or request.get("portfolio_preparation_hash")
        != record.get("preparation_receipt_hash")
        or not _timestamp_not_after(
            preparation.get("prepared_at") if isinstance(preparation, Mapping) else None,
            run.get("claimed_at"),
        )
    )
    if (
        not isinstance(snapshot_hashes, Mapping)
        or not isinstance(snapshot_files, Mapping)
        or snapshot_hashes.get("portfolio-job-plan") != job_plan_hash
        or snapshot_hashes.get("portfolio-job-spec") != job_spec_hash
        or snapshot_files.get("portfolio-job-plan")
        != "claim/portfolio-job-plan.json"
        or snapshot_files.get("portfolio-job-spec")
        != "claim/portfolio-job-spec.json"
        or job_plan is None
        or dict(job_plan_snapshot) != dict(job_plan)
        or job_spec is None
        or dict(job_spec_snapshot) != dict(job_spec)
        or request.get("portfolio_job_plan_ref") != record.get("job_plan_ref")
        or request.get("portfolio_job_plan_hash") != record.get("job_plan_hash")
        or request.get("portfolio_job_spec_ref") != record.get("job_spec_ref")
        or request.get("portfolio_job_spec_hash") != record.get("job_spec_hash")
        or request.get("portfolio_job_id") != record.get("job_id")
        or request.get("portfolio_job_class_id") != record.get("job_class_id")
        or request.get("portfolio_member_skill_id") != record.get("member_skill_id")
        or request.get("portfolio_member_contract_hash")
        != record.get("member_contract_hash")
        or sorted(request.get("portfolio_covered_capability_ids", []))
        != sorted(record.get("covered_capability_ids", []))
        or not _timestamp_not_after(
            job_plan_snapshot.get("created_at"), run.get("claimed_at")
        )
        or not _timestamp_not_after(
            job_spec_snapshot.get("created_at"), run.get("claimed_at")
        )
        or preparation_claim_invalid
    ):
        findings.append(
            _finding("portfolio_job_claim_snapshot_binding_invalid", detail=evidence_ref)
        )
    if isinstance(job_spec_snapshot, Mapping):
        findings.extend(
            _job_contract_path_findings(
                job_spec_snapshot,
                contract,
                check_manifest,
            )
        )
    if (
        receipt.get("schema_version") != "skillguard.evidence_receipt.v2"
        or receipt.get("run_id") != run_id
        or receipt.get("contract_hash") != contract_hash
        or receipt.get("status") != "passed"
        or receipt.get("evidence_class") != record.get("evidence_class")
        or not _internal_hash_matches(receipt, "receipt_hash")
    ):
        findings.append(_finding("portfolio_runtime_receipt_invalid", detail=evidence_ref))
    closure_shape_current = (
        closure.get("schema_version") == "skillguard.closure_receipt.v2"
        and closure.get("run_id") == run_id
        and closure.get("contract_hash") == contract_hash
        and closure.get("status") == "closed"
        and closure.get("profile") == "enforced"
        and receipt.get("receipt_id") in closure.get("consumed_receipt_ids", [])
        and _internal_hash_matches(closure, "closure_hash")
    )
    if not closure_shape_current:
        findings.append(_finding("portfolio_runtime_closure_receipt_invalid", detail=evidence_ref))

    receipt_evidence = receipt.get("evidence")
    manifest_check_current = False
    closure_replay_current = False
    artifact_current_verified = False
    resume_replay_current = False
    judgment_current = False
    terminal_observation_current = False
    mutation_observation_current = False
    if record.get("evidence_class") == "hard":
        check_record = loaded["check_record_ref"]
        result = check_record.get("result") if isinstance(check_record.get("result"), Mapping) else {}
        declared_check = next(
            (
                row
                for row in check_manifest.get("checks", [])
                if isinstance(row, Mapping)
                and row.get("check_id") == result.get("check_id")
            ),
            None,
        )
        declared_check_hash = (
            canonical_hash(dict(declared_check))
            if isinstance(declared_check, Mapping)
            else ""
        )
        if (
            check_record.get("schema_version") != "skillguard.check_result.v2"
            or check_record.get("run_id") != run_id
            or check_record.get("contract_hash") != contract_hash
            or check_record.get("check_manifest_hash") != stored_manifest_hash
            or check_record.get("check_declarations_hash") != declarations_hash
            or check_record.get("step_id") != receipt.get("step_id")
            or check_record.get("status") != "passed"
            or check_record.get("execution_disposition")
            not in {"executed_terminal_success", "reused_terminal_success"}
            or check_record.get("declared_check_hash")
            != result.get("declared_check_hash")
            or not _internal_hash_matches(check_record, "record_hash")
        ):
            findings.append(_finding("portfolio_runtime_check_record_invalid", detail=evidence_ref))
        expected_proof = execution_proof_fingerprint(result)
        execution_environment = result.get("execution_environment")
        result_shape_ok = (
            isinstance(result.get("command"), str)
            and bool(result.get("command", "").strip())
            and isinstance(result.get("args"), list)
            and all(isinstance(item, str) for item in result.get("args", []))
            and result.get("status") == "passed"
            and result.get("execution_disposition")
            in {"executed_terminal_success", "reused_terminal_success"}
            and result.get("exit_code") == result.get("expected_exit_code")
            and _content_hash_ok(result.get("stdout_content_hash"))
            and _content_hash_ok(result.get("stderr_content_hash"))
            and isinstance(execution_environment, Mapping)
            and bool(execution_environment)
            and result.get("execution_environment_fingerprint")
            == canonical_hash(execution_environment)
            and result.get("check_manifest_hash") == stored_manifest_hash
            and result.get("check_declarations_hash") == declarations_hash
            and result.get("declared_check_hash") == declared_check_hash
            and result.get("proof_fingerprint") == expected_proof
            and check_record.get("proof_fingerprint") == expected_proof
        )
        if not result_shape_ok:
            findings.append(_finding("portfolio_runtime_check_execution_invalid", detail=evidence_ref))
        hard_receipt_binding_invalid = (
            not isinstance(receipt_evidence, Mapping)
            or receipt_evidence.get("proof_kind")
            != "owner_receipt_projection"
            or receipt_evidence.get("check_record_id") != check_record.get("check_record_id")
            or receipt_evidence.get("check_record_hash") != check_record.get("record_hash")
            or receipt_evidence.get("proof_fingerprint") != expected_proof
            or receipt_evidence.get("execution_environment_fingerprint")
            != result.get("execution_environment_fingerprint")
            or receipt_evidence.get("check_manifest_hash")
            != stored_manifest_hash
            or receipt_evidence.get("check_declarations_hash")
            != declarations_hash
            or receipt_evidence.get("declared_check_hash")
            != result.get("declared_check_hash")
            or receipt_evidence.get("execution_owner_id")
            != check_record.get("execution_owner_id")
            or receipt_evidence.get("owner_receipt_id")
            != check_record.get("owner_receipt_id")
            or receipt_evidence.get("owner_receipt_hash")
            != check_record.get("owner_receipt_hash")
            or receipt_evidence.get("owner_receipt_ref")
            != check_record.get("owner_receipt_ref")
        )
        owner_receipt_current = False
        if evidence_root is not None:
            try:
                from .check_runner import load_owner_receipt_from_projection

                load_owner_receipt_from_projection(
                    evidence_root / "owner-evidence",
                    check_record,
                )
                owner_receipt_current = True
            except (OSError, ValueError, RuntimeError):
                owner_receipt_current = False
        if not owner_receipt_current:
            findings.append(
                _finding(
                    "portfolio_runtime_owner_receipt_invalid",
                    detail=evidence_ref,
                )
            )
        if hard_receipt_binding_invalid:
            findings.append(_finding("portfolio_runtime_hard_receipt_binding_invalid", detail=evidence_ref))
        required_check_ids = set(
            str(value)
            for value in job_spec_snapshot.get("required_check_ids", [])
        )
        if result.get("check_id") not in required_check_ids:
            findings.append(
                _finding(
                    "portfolio_runtime_check_not_in_job_contract",
                    detail=evidence_ref,
                )
            )
        manifest_check_current = bool(
            result_shape_ok
            and not hard_receipt_binding_invalid
            and owner_receipt_current
            and result.get("check_id") in required_check_ids
        )
    elif record.get("evidence_class") == "witnessed":
        required = ("witness_kind", "target_id", "input_fingerprint", "output_fingerprint")
        if not isinstance(receipt_evidence, Mapping) or any(
            not isinstance(receipt_evidence.get(field), str) or not receipt_evidence.get(field)
            for field in required
        ):
            findings.append(_finding("portfolio_runtime_witness_receipt_invalid", detail=evidence_ref))
    elif record.get("evidence_class") == "judged":
        required = ("rubric_id", "rubric_version", "evaluator_id", "input_fingerprint", "conclusion")
        if not isinstance(receipt_evidence, Mapping) or any(
            not isinstance(receipt_evidence.get(field), str) or not receipt_evidence.get(field)
            for field in required
        ) or not isinstance(receipt_evidence.get("limitations"), list) or not receipt_evidence.get("limitations"):
            findings.append(_finding("portfolio_runtime_judged_receipt_invalid", detail=evidence_ref))
        else:
            judgment_current = True

    if (
        run.get("guard_runtime_identity") != record.get("guard_runtime")
        or run.get("guard_runtime_identity_hash")
        != canonical_hash(record.get("guard_runtime"))
    ):
        findings.append(_finding("portfolio_runtime_guard_binding_invalid", detail=evidence_ref))

    if evidence_root is not None:
        absolute_run_root = evidence_root.resolve() / run_root
        try:
            from .check_runner import load_check_result
            from .artifact_validators import artifact_record_is_current, load_artifact_record
            from .closure import load_closure, verify_closure
            from .receipts import load_receipt, load_receipts
            from .run_store import (
                load_claim_snapshot,
                load_check_manifest_snapshot,
                load_contract_snapshot,
                load_events,
                load_run,
            )
            from .step_runtime import resume_run

            loaded_run = load_run(absolute_run_root)
            loaded_contract = load_contract_snapshot(absolute_run_root)
            loaded_manifest = load_check_manifest_snapshot(absolute_run_root)
            loaded_job_plan_snapshot = load_claim_snapshot(
                absolute_run_root, "portfolio-job-plan"
            )
            loaded_job_spec_snapshot = load_claim_snapshot(
                absolute_run_root, "portfolio-job-spec"
            )
            loaded_preparation_snapshot = load_claim_snapshot(
                absolute_run_root, "portfolio-preparation"
            )
            loaded_receipt = load_receipt(
                absolute_run_root, str(receipt.get("receipt_id", ""))
            )
            loaded_closure = load_closure(
                absolute_run_root, str(closure.get("closure_receipt_id", ""))
            )
            load_events(absolute_run_root)
            if (
                dict(loaded_run) != dict(run)
                or dict(loaded_contract) != dict(contract)
                or dict(loaded_manifest) != dict(check_manifest)
                or dict(loaded_job_plan_snapshot) != dict(job_plan_snapshot)
                or dict(loaded_job_spec_snapshot) != dict(job_spec_snapshot)
                or not isinstance(loaded_preparation_snapshot, Mapping)
                or not isinstance(preparation_snapshot, Mapping)
                or dict(loaded_preparation_snapshot) != dict(preparation_snapshot)
                or dict(loaded_receipt) != dict(receipt)
                or dict(loaded_closure) != dict(closure)
            ):
                findings.append(_finding("portfolio_runtime_loader_projection_mismatch", detail=evidence_ref))
            findings.extend(
                _runtime_execution_coverage_findings(
                    loaded_run,
                    loaded_job_spec_snapshot,
                    run_root=absolute_run_root,
                    owner_evidence_root=(
                        evidence_root / "owner-evidence"
                        if evidence_root is not None
                        else absolute_run_root.parents[3] / "owner-evidence"
                    ),
                )
            )
            if record.get("evidence_class") == "hard":
                loaded_check = load_check_result(
                    absolute_run_root, str(loaded["check_record_ref"].get("check_record_id", ""))
                )
                if dict(loaded_check) != dict(loaded["check_record_ref"]):
                    findings.append(
                        _finding("portfolio_runtime_check_loader_mismatch", detail=evidence_ref)
                    )
            if record.get("job_class_id") == "artifact_check":
                expected_artifact = loaded["artifact_record_ref"]
                artifact_id = str(expected_artifact.get("artifact_record_id", ""))
                loaded_artifact = load_artifact_record(absolute_run_root, artifact_id)
                target_root = absolute_target_root or absolute_run_root.parents[2]
                artifact_current, artifact_reason = artifact_record_is_current(
                    loaded_artifact, target_root
                )
                if (
                    dict(loaded_artifact) != dict(expected_artifact)
                    or not artifact_current
                    or artifact_id not in receipt.get("artifact_record_ids", [])
                    or expected_artifact.get("producer_step_id") != receipt.get("step_id")
                ):
                    findings.append(
                        _finding(
                            "portfolio_runtime_artifact_receipt_invalid",
                            detail=f"{evidence_ref}:{artifact_reason}",
                        )
                    )
                else:
                    artifact_current_verified = True
            current_fingerprints: dict[str, object] = {}
            fingerprint_conflict = False
            for runtime_receipt in load_receipts(absolute_run_root):
                receipt_fingerprints = runtime_receipt.get("input_fingerprints", {})
                if not isinstance(receipt_fingerprints, Mapping):
                    fingerprint_conflict = True
                    continue
                for key, value in receipt_fingerprints.items():
                    if key in current_fingerprints and current_fingerprints[key] != value:
                        fingerprint_conflict = True
                    current_fingerprints[str(key)] = value
            if fingerprint_conflict:
                findings.append(
                    _finding("portfolio_runtime_fingerprint_history_conflict", detail=evidence_ref)
                )
            verification = verify_closure(
                absolute_run_root,
                str(closure.get("closure_receipt_id", "")),
                current_fingerprints=current_fingerprints,
                receipt_roots=(absolute_run_root,),
                target_root=absolute_target_root,
            )
            if verification.get("ok") is not True or verification.get("status") != "current":
                findings.append(
                    _finding(
                        "portfolio_runtime_closure_replay_failed",
                        detail=f"{evidence_ref}:{','.join(str(item) for item in verification.get('findings', []))}",
                    )
                )
            else:
                closure_replay_current = True
            if record.get("job_class_id") == "recovery_or_resume":
                resumed_state_hash = canonical_hash(resume_run(absolute_run_root).to_dict())
                if payload.get("resume_state_hash") != resumed_state_hash:
                    findings.append(
                        _finding("portfolio_runtime_resume_replay_invalid", detail=evidence_ref)
                    )
                else:
                    resume_replay_current = True
        except Exception as exc:  # Runtime loaders normalize their own exact failure families.
            findings.append(
                _finding(
                    "portfolio_runtime_loader_failed",
                    detail=f"{evidence_ref}:{getattr(exc, 'code', type(exc).__name__)}",
                )
            )
    if record.get("job_class_id") in {"invalid_input", "out_of_scope"}:
        expected_terminal = (
            "expected_rejection"
            if record.get("job_class_id") == "invalid_input"
            else "out_of_scope_decline"
        )
        if isinstance(terminal_observation, Mapping):
            unsigned_terminal = dict(terminal_observation)
            stored_terminal_hash = unsigned_terminal.pop("observation_hash", None)
            terminal_observation_current = bool(
                terminal_observation.get("schema_version")
                == PORTFOLIO_TERMINAL_OBSERVATION_SCHEMA
                and terminal_observation.get("preparation_id")
                == record.get("preparation_id")
                and terminal_observation.get("job_id") == record.get("job_id")
                and terminal_observation.get("job_class_id")
                == record.get("job_class_id")
                and terminal_observation.get("run_id") == run_id
                and terminal_observation.get("terminal_kind") == expected_terminal
                and terminal_observation.get("status") == "observed"
                and stored_terminal_hash == canonical_hash(unsigned_terminal)
                and _timestamp_not_after(
                    run.get("claimed_at"), terminal_observation.get("observed_at")
                )
            )
        if isinstance(mutation_observation, Mapping):
            unsigned_mutation = dict(mutation_observation)
            stored_mutation_hash = unsigned_mutation.pop("observation_hash", None)
            mutation_observation_current = bool(
                mutation_observation.get("schema_version")
                == PORTFOLIO_MUTATION_OBSERVATION_SCHEMA
                and mutation_observation.get("preparation_id")
                == record.get("preparation_id")
                and mutation_observation.get("job_id") == record.get("job_id")
                and mutation_observation.get("run_id") == run_id
                and mutation_observation.get("terminal_observation_ref")
                == payload.get("terminal_observation_ref")
                and mutation_observation.get("mutation_boundary")
                == "canonical-maintainable-source"
                and mutation_observation.get("before_fingerprint")
                == payload.get("mutation_fingerprint_before")
                and mutation_observation.get("after_fingerprint")
                == payload.get("mutation_fingerprint_after")
                and mutation_observation.get("ordered") is True
                and mutation_observation.get("equal") is True
                and stored_mutation_hash == canonical_hash(unsigned_mutation)
                and _timestamp_not_after(
                    mutation_observation.get("before_observed_at"),
                    run.get("claimed_at"),
                )
                and isinstance(terminal_observation, Mapping)
                and _timestamp_not_after(
                    terminal_observation.get("observed_at"),
                    mutation_observation.get("after_observed_at"),
                )
                and mutation_observation.get("observed_at")
                == mutation_observation.get("after_observed_at")
            )
        if not terminal_observation_current:
            findings.append(
                _finding(
                    "portfolio_runtime_negative_terminal_observation_invalid",
                    detail=evidence_ref,
                )
            )
        if not mutation_observation_current:
            findings.append(
                _finding(
                    "portfolio_runtime_mutation_observation_invalid",
                    detail=evidence_ref,
                )
            )
    job_class_id = str(record.get("job_class_id", ""))
    no_mutation_current = bool(
        payload.get("mutation_fingerprint_before") == record.get("source_fingerprint")
        and payload.get("mutation_fingerprint_after")
        == record.get("source_fingerprint")
        and isinstance(target_identity, Mapping)
        and target_identity.get("source_fingerprint")
        == record.get("source_fingerprint")
    )
    if job_class_id == "invalid_input":
        no_mutation_current = bool(
            no_mutation_current
            and payload.get("outcome_observation") == "expected_rejection"
            and terminal_observation_current
            and mutation_observation_current
        )
    elif job_class_id == "out_of_scope":
        no_mutation_current = bool(
            no_mutation_current
            and payload.get("outcome_observation") == "out_of_scope_decline"
            and terminal_observation_current
            and mutation_observation_current
        )
    requirement_status = {
        "manifest_check_passed": manifest_check_current,
        "closure_replay_current": closure_shape_current
        and closure_replay_current,
        "resume_replay_current": resume_replay_current,
        "artifact_current": artifact_current_verified,
        "no_mutation": no_mutation_current,
        "judgment_current": judgment_current,
    }
    required_evidence = {
        str(requirement)
        for binding in job_spec_snapshot.get("capability_bindings", [])
        if isinstance(binding, Mapping)
        for requirement in binding.get("evidence_requirements", [])
    }
    verifier_outcome = (
        JOB_CLASS_EXPECTED_OUTCOMES.get(job_class_id, "")
        if required_evidence
        and all(requirement_status.get(requirement, False) for requirement in required_evidence)
        else ""
    )
    if (
        not verifier_outcome
        or record.get("expected_outcome") != verifier_outcome
        or record.get("observed_outcome") != verifier_outcome
    ):
        findings.append(
            _finding("portfolio_runtime_verifier_outcome_invalid", detail=evidence_ref)
        )
    return findings


def _load_evidence_record(
    evidence_ref: str,
    *,
    evidence_root: Path | None,
) -> tuple[Mapping[str, Any] | None, list[dict[str, str]]]:
    record, _relative, load_findings = _load_hash_bound_json(
        evidence_ref,
        evidence_root=evidence_root,
        finding_prefix="portfolio_evidence_record",
    )
    if load_findings:
        return None, load_findings
    findings = _evidence_record_findings(record, evidence_ref=evidence_ref)
    return record, findings


def _representative_job_evidence_findings(
    jobs: Sequence[Mapping[str, Any]],
    evidence: Mapping[str, Any],
    *,
    evidence_root: Path | None,
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for job in jobs:
        job_id = str(job["job_id"])
        declared_capabilities = set(str(item) for item in job["covered_capability_ids"])
        evidenced_capabilities: set[str] = set()
        evidence_classes: set[str] = set()
        for evidence_ref in job["evidence_refs"]:
            record, record_findings = _load_evidence_record(
                str(evidence_ref), evidence_root=evidence_root
            )
            findings.extend(record_findings)
            if record is None or record_findings:
                continue
            runtime_findings = _runtime_evidence_findings(
                record,
                evidence_ref=str(evidence_ref),
                evidence_root=evidence_root,
            )
            findings.extend(runtime_findings)
            if runtime_findings:
                continue
            record_capabilities = set(
                str(item) for item in record.get("covered_capability_ids", [])
            )
            if record.get("job_id") != job_id:
                findings.append(
                    _finding("portfolio_evidence_job_mismatch", detail=f"{job_id}:{evidence_ref}")
                )
            if record.get("registry_id") != evidence.get("registry_id"):
                findings.append(
                    _finding("portfolio_evidence_registry_mismatch", detail=f"{job_id}:{evidence_ref}")
                )
            preparation_binding = evidence.get("preparation_receipt")
            if (
                not isinstance(preparation_binding, Mapping)
                or record.get("preparation_id")
                != preparation_binding.get("receipt_id")
                or record.get("preparation_receipt_ref")
                != preparation_binding.get("ref")
                or record.get("preparation_receipt_hash")
                != preparation_binding.get("receipt_hash")
            ):
                findings.append(
                    _finding(
                        "portfolio_evidence_preparation_mismatch",
                        detail=f"{job_id}:{evidence_ref}",
                    )
                )
            if (
                record.get("scope_manifest_id") != evidence.get("scope_manifest_id")
                or record.get("scope_manifest_hash")
                != evidence.get("scope_manifest_hash")
            ):
                findings.append(
                    _finding("portfolio_evidence_scope_mismatch", detail=f"{job_id}:{evidence_ref}")
                )
            if record.get("skill_id") != evidence.get("skill_id"):
                findings.append(
                    _finding("portfolio_evidence_skill_mismatch", detail=f"{job_id}:{evidence_ref}")
                )
            if (
                record.get("member_skill_id") != job.get("member_skill_id")
                or record.get("member_contract_hash")
                != job.get("member_contract_hash")
            ):
                findings.append(
                    _finding(
                        "portfolio_evidence_member_binding_mismatch",
                        detail=f"{job_id}:{evidence_ref}",
                    )
                )
            declared_job_classes = set(str(item) for item in job.get("job_class_ids", []))
            if record.get("job_class_id") not in declared_job_classes:
                findings.append(
                    _finding("portfolio_evidence_job_class_mismatch", detail=f"{job_id}:{evidence_ref}")
                )
            if not record_capabilities.issubset(declared_capabilities):
                findings.append(
                    _finding("portfolio_evidence_capability_overreach", detail=f"{job_id}:{evidence_ref}")
                )
            if not _same_guard(record.get("guard_runtime"), evidence.get("guard_runtime")):
                findings.append(
                    _finding("portfolio_evidence_guard_mismatch", detail=f"{job_id}:{evidence_ref}")
                )
            if record.get("source_fingerprint") != evidence.get("source_fingerprint"):
                findings.append(
                    _finding("portfolio_evidence_source_mismatch", detail=f"{job_id}:{evidence_ref}")
                )
            if record.get("contract_hash") != evidence.get("contract_hash"):
                findings.append(
                    _finding("portfolio_evidence_contract_mismatch", detail=f"{job_id}:{evidence_ref}")
                )
            evidence_classes.add(str(record.get("evidence_class", "")))
            evidenced_capabilities.update(record_capabilities)
        if evidenced_capabilities != declared_capabilities:
            missing = sorted(declared_capabilities - evidenced_capabilities)
            extra = sorted(evidenced_capabilities - declared_capabilities)
            findings.append(
                _finding(
                    "portfolio_job_evidence_coverage_mismatch",
                    detail=f"{job_id}:missing={','.join(missing)};extra={','.join(extra)}",
                )
            )
        if "hard" not in evidence_classes:
            findings.append(
                _finding("portfolio_job_hard_evidence_missing", detail=job_id)
            )
        if "judged_quality" in job.get("job_class_ids", []) and "judged" not in evidence_classes:
            findings.append(
                _finding("portfolio_job_judged_evidence_missing", detail=job_id)
            )
    return findings


def _global_plan_claim_findings(
    jobs: Sequence[Mapping[str, Any]],
    *,
    global_plan_ref: str,
    global_plan_hash: str,
    global_plan: Mapping[str, Any],
    job_specs: Mapping[str, Mapping[str, Any]],
    evidence_root: Path | None,
    skill_id: str,
) -> list[dict[str, str]]:
    """Prove one complete prepare boundary preceded every representative claim."""

    findings: list[dict[str, str]] = []
    claimed_at_values: list[str] = []
    unproved_claims: set[str] = set()
    for job in jobs:
        job_id = str(job.get("job_id", ""))
        expected_spec_ref = str(job.get("job_spec_ref", ""))
        expected_spec_hash = str(job.get("job_spec_hash", ""))
        for evidence_ref in job.get("evidence_refs", []):
            record, _record_relative, record_load_findings = _load_hash_bound_json(
                str(evidence_ref),
                evidence_root=evidence_root,
                finding_prefix="graduation_global_plan_evidence_record",
            )
            if record is None or record_load_findings:
                unproved_claims.add(job_id)
                continue
            if (
                record.get("job_plan_ref") != global_plan_ref
                or record.get("job_plan_hash") != global_plan_hash
                or record.get("job_spec_ref") != expected_spec_ref
                or record.get("job_spec_hash") != expected_spec_hash
            ):
                findings.append(
                    _finding(
                        "graduation_global_plan_evidence_binding_invalid",
                        skill_id=skill_id,
                        detail=f"{job_id}:{evidence_ref}",
                    )
                )
            payload = record.get("payload")
            run_ref = (
                str(payload.get("run_record_ref", ""))
                if isinstance(payload, Mapping)
                else ""
            )
            run, _run_relative, run_load_findings = _load_hash_bound_json(
                run_ref,
                evidence_root=evidence_root,
                finding_prefix="graduation_global_plan_run_record",
            )
            if run is None or run_load_findings:
                unproved_claims.add(job_id)
                continue
            request = run.get("request")
            if (
                not isinstance(request, Mapping)
                or request.get("portfolio_job_plan_ref") != global_plan_ref
                or request.get("portfolio_job_plan_hash") != global_plan_hash
                or request.get("portfolio_job_spec_ref") != expected_spec_ref
                or request.get("portfolio_job_spec_hash") != expected_spec_hash
            ):
                findings.append(
                    _finding(
                        "graduation_global_plan_run_binding_invalid",
                        skill_id=skill_id,
                        detail=f"{job_id}:{run_ref}",
                    )
                )
            claimed_at = run.get("claimed_at")
            if not _timestamp_ok(claimed_at):
                unproved_claims.add(job_id)
            else:
                assert isinstance(claimed_at, str)
                claimed_at_values.append(claimed_at)

    if unproved_claims or not claimed_at_values:
        findings.append(
            _finding(
                "graduation_global_plan_claim_order_unproved",
                skill_id=skill_id,
                detail=",".join(sorted(unproved_claims)),
            )
        )
        return findings

    earliest_claimed_at = min(
        claimed_at_values,
        key=lambda value: datetime.fromisoformat(value.replace("Z", "+00:00")),
    )
    created_at_rows = [("global-plan", global_plan.get("created_at"))]
    created_at_rows.extend(
        (f"job-spec:{record_ref}", spec.get("created_at"))
        for record_ref, spec in sorted(job_specs.items())
    )
    for owner, created_at in created_at_rows:
        if not _timestamp_not_after(created_at, earliest_claimed_at):
            findings.append(
                _finding(
                    "graduation_global_prepare_order_invalid",
                    skill_id=skill_id,
                    detail=(
                        f"{owner}:created_at={created_at};"
                        f"earliest_claimed_at={earliest_claimed_at}"
                    ),
                )
            )
    return findings


def _normalized_result_job_rows(value: object) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(value, list) or not value:
        return [], ["result_job_rows_missing"]
    normalized: list[dict[str, Any]] = []
    findings: list[str] = []
    seen: set[str] = set()
    for index, row in enumerate(value):
        if not isinstance(row, Mapping):
            findings.append(f"result_job_row_not_object:{index}")
            continue
        job_id = str(row.get("job_id", ""))
        capabilities = _unique_string_list(row.get("covered_capability_ids"))
        evidence_refs = _unique_string_list(row.get("evidence_refs"))
        job_classes = _unique_string_list(row.get("job_class_ids"))
        member_skill_id = str(row.get("member_skill_id", ""))
        member_contract_hash = row.get("member_contract_hash")
        outcome = str(row.get("outcome", ""))
        if not job_id or job_id in seen:
            findings.append(f"result_job_id_invalid:{job_id or index}")
        seen.add(job_id)
        if capabilities is None or not capabilities or evidence_refs is None or not evidence_refs:
            findings.append(f"result_job_binding_invalid:{job_id or index}")
        if job_classes is None or not job_classes:
            findings.append(f"result_job_classes_invalid:{job_id or index}")
        if not member_skill_id or not _hash_ok(member_contract_hash):
            findings.append(f"result_job_member_binding_invalid:{job_id or index}")
        expected_outcome = (
            JOB_CLASS_EXPECTED_OUTCOMES.get(job_classes[0], "")
            if job_classes and len(job_classes) == 1
            else ""
        )
        if row.get("status") != "verified":
            findings.append(f"result_job_not_passed:{job_id or index}")
        if not expected_outcome or outcome != expected_outcome:
            findings.append(f"result_job_outcome_invalid:{job_id or index}")
        if job_id and capabilities and evidence_refs and job_classes:
            normalized.append(
                {
                    "job_id": job_id,
                    "job_class_ids": sorted(job_classes),
                    "member_skill_id": member_skill_id,
                    "member_contract_hash": str(member_contract_hash),
                    "covered_capability_ids": sorted(capabilities),
                    "evidence_refs": sorted(evidence_refs),
                    "outcome": outcome,
                    "status": "verified",
                }
            )
    return sorted(normalized, key=lambda item: item["job_id"]), findings


def _derived_execution_payloads(
    jobs: Sequence[Mapping[str, Any]],
    *,
    evidence_root: Path | None,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, str]]]:
    findings: list[dict[str, str]] = []
    command_jobs: list[dict[str, Any]] = []
    environment_rows: list[dict[str, Any]] = []
    for job in jobs:
        job_id = str(job.get("job_id", ""))
        executions: list[dict[str, Any]] = []
        job_spec, _spec_relative, spec_findings = _load_hash_bound_json(
            str(job.get("job_spec_ref", "")),
            evidence_root=evidence_root,
            finding_prefix="graduation_job_spec",
        )
        findings.extend(spec_findings)
        required_check_ids = {
            str(value)
            for value in (
                job_spec.get("required_check_ids", [])
                if isinstance(job_spec, Mapping)
                else []
            )
        }
        executed_required_check_ids: set[str] = set()
        seen_run_roots: set[Path] = set()
        seen_record_ids: set[str] = set()
        for evidence_ref in job.get("evidence_refs", []):
            record, record_findings = _load_evidence_record(
                str(evidence_ref), evidence_root=evidence_root
            )
            findings.extend(record_findings)
            if record is None or record_findings or record.get("evidence_class") != "hard":
                continue
            runtime_findings = _runtime_evidence_findings(
                record,
                evidence_ref=str(evidence_ref),
                evidence_root=evidence_root,
            )
            findings.extend(runtime_findings)
            if runtime_findings:
                continue
            payload = record.get("payload")
            assert isinstance(payload, Mapping)
            _run, run_relative, run_findings = _load_hash_bound_json(
                str(payload.get("run_record_ref", "")),
                evidence_root=evidence_root,
                finding_prefix="portfolio_run_record",
            )
            findings.extend(run_findings)
            if run_relative is None or run_findings or evidence_root is None:
                continue
            absolute_run_root = evidence_root.resolve() / run_relative.parent
            if absolute_run_root in seen_run_roots:
                continue
            seen_run_roots.add(absolute_run_root)
            try:
                from .check_runner import load_check_result

                for check_path in sorted(
                    (absolute_run_root / "checks").glob("check-record-*.json")
                ):
                    check_record = load_check_result(
                        absolute_run_root, check_path.stem
                    )
                    check_id = str(
                        check_record.get("check_id")
                        or check_record.get("result", {}).get("check_id", "")
                    )
                    record_id = str(check_record.get("check_record_id", ""))
                    if (
                        check_id not in required_check_ids
                        or record_id in seen_record_ids
                    ):
                        continue
                    seen_record_ids.add(record_id)
                    executed_required_check_ids.add(check_id)
                    result = check_record.get("result")
                    if not isinstance(result, Mapping):
                        findings.append(
                            _finding(
                                "portfolio_check_result_missing", detail=job_id
                            )
                        )
                        continue
                    execution = {
                        "check_record_id": record_id,
                        "check_record_hash": str(
                            check_record.get("record_hash", "")
                        ),
                        "command": str(result.get("command", "")),
                        "args": list(result.get("args", [])),
                        "cwd_token": str(result.get("cwd_token", "")),
                        "cwd_relative": str(result.get("cwd_relative", "")),
                        "exit_code": result.get("exit_code"),
                        "expected_exit_code": result.get("expected_exit_code"),
                        "stdout_content_hash": str(result.get("stdout_content_hash", "")),
                        "stderr_content_hash": str(result.get("stderr_content_hash", "")),
                        "execution_environment_fingerprint": str(
                            result.get("execution_environment_fingerprint", "")
                        ),
                    }
                    executions.append(execution)
                    environment_rows.append(
                        {
                            "job_id": job_id,
                            "check_record_id": record_id,
                            "environment": dict(
                                result.get("execution_environment", {})
                            ),
                            "environment_fingerprint": execution[
                                "execution_environment_fingerprint"
                            ],
                        }
                    )
            except Exception as exc:
                findings.append(
                    _finding(
                        "graduation_job_execution_load_failed",
                        detail=f"{job_id}:{getattr(exc, 'code', type(exc).__name__)}",
                    )
                )
        executions.sort(key=lambda item: (item["check_record_id"], item["check_record_hash"]))
        if not executions:
            findings.append(_finding("graduation_job_execution_missing", detail=job_id))
        elif executed_required_check_ids != required_check_ids:
            findings.append(
                _finding(
                    "graduation_job_execution_coverage_incomplete",
                    detail=(
                        f"{job_id}:missing="
                        f"{','.join(sorted(required_check_ids-executed_required_check_ids))};"
                        f"extra={','.join(sorted(executed_required_check_ids-required_check_ids))}"
                    ),
                )
            )
        command_jobs.append({"job_id": job_id, "executions": executions})
    command_jobs.sort(key=lambda item: item["job_id"])
    environment_rows.sort(key=lambda item: (item["job_id"], item["check_record_id"]))
    return {"jobs": command_jobs}, {"executions": environment_rows}, findings


def _assemble_portfolio_run_receipt(
    *,
    skill_id: str,
    guard_runtime: Mapping[str, Any],
    source_fingerprint: str,
    contract_hash: str,
    representative_jobs: object,
    evidence_root: Path | None,
    production_revalidation_bindings: object = None,
    require_production_revalidation: bool,
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    """Internal shared assembler for typed capability and production domains."""

    jobs, job_findings = _normalized_representative_jobs(
        representative_jobs, require_job_classes=True
    )
    findings = [
        _finding(value.split(":", 1)[0], skill_id=skill_id, detail=value)
        for value in job_findings
    ]
    if not _guard_ok(guard_runtime):
        findings.append(_finding("graduation_guard_invalid", skill_id=skill_id))
    if not _hash_ok(source_fingerprint) or not _hash_ok(contract_hash):
        findings.append(_finding("graduation_source_or_contract_invalid", skill_id=skill_id))
    production_rows = (
        [dict(row) for row in production_revalidation_bindings]
        if isinstance(production_revalidation_bindings, list)
        and all(isinstance(row, Mapping) for row in production_revalidation_bindings)
        else []
    )
    production_fingerprint = portfolio_production_revalidation_fingerprint(
        production_rows
    )
    if require_production_revalidation and not production_fingerprint:
        findings.append(
            _finding(
                "graduation_production_revalidation_bindings_missing",
                skill_id=skill_id,
            )
        )
    command_set, environment, execution_findings = _derived_execution_payloads(
        jobs, evidence_root=evidence_root
    )
    findings.extend(execution_findings)
    completion_times: list[str] = []
    for job in jobs:
        for evidence_ref in job.get("evidence_refs", []):
            record, record_findings = _load_evidence_record(
                str(evidence_ref), evidence_root=evidence_root
            )
            findings.extend(record_findings)
            if record is None or record_findings:
                continue
            payload = record.get("payload")
            if not isinstance(payload, Mapping):
                continue
            check_record, _relative, check_findings = _load_hash_bound_json(
                str(payload.get("check_record_ref", "")),
                evidence_root=evidence_root,
                finding_prefix="portfolio_check_record",
            )
            findings.extend(check_findings)
            result = (
                check_record.get("result")
                if isinstance(check_record, Mapping)
                and isinstance(check_record.get("result"), Mapping)
                else None
            )
            if isinstance(result, Mapping) and _timestamp_ok(result.get("finished_at")):
                completion_times.append(str(result["finished_at"]))
    for production_row in production_rows:
        binding, _relative, binding_findings = _load_hash_bound_json(
            str(production_row.get("binding_ref", "")),
            evidence_root=evidence_root,
            finding_prefix="graduation_production_binding",
        )
        findings.extend(binding_findings)
        if (
            isinstance(binding, Mapping)
            and binding.get("binding_hash") == production_row.get("binding_hash")
            and _timestamp_ok(binding.get("captured_at"))
        ):
            completion_times.append(str(binding["captured_at"]))
        elif isinstance(binding, Mapping):
            findings.append(
                _finding(
                    "graduation_production_binding_completion_invalid",
                    skill_id=str(production_row.get("member_skill_id", "")),
                )
            )
    if not completion_times:
        findings.append(_finding("graduation_completion_time_missing", skill_id=skill_id))
    if findings:
        return None, findings
    completed_at = max(
        completion_times,
        key=lambda value: datetime.fromisoformat(value.replace("Z", "+00:00")),
    )
    result_rows = [
        {
            "job_id": str(job["job_id"]),
            "job_class_ids": sorted(str(item) for item in job.get("job_class_ids", [])),
            "member_skill_id": str(job.get("member_skill_id", "")),
            "member_contract_hash": str(job.get("member_contract_hash", "")),
            "covered_capability_ids": sorted(
                str(item) for item in job["covered_capability_ids"]
            ),
            "evidence_refs": sorted(str(item) for item in job["evidence_refs"]),
            "outcome": JOB_CLASS_EXPECTED_OUTCOMES[
                str(next(iter(job.get("job_class_ids", [])), ""))
            ],
            "status": "verified",
        }
        for job in jobs
    ]
    result_rows.sort(key=lambda item: item["job_id"])
    result_bundle = {"representative_job_results": result_rows}
    seed = {
        "skill_id": skill_id,
        "guard_runtime": dict(guard_runtime),
        "source_fingerprint": source_fingerprint,
        "contract_hash": contract_hash,
        "coverage_fingerprint": representative_jobs_coverage_fingerprint(jobs),
        "production_revalidation_fingerprint": production_fingerprint,
        "command_fingerprint": canonical_hash(command_set),
        "environment_fingerprint": canonical_hash(environment),
        "result_hash": canonical_hash(result_bundle),
        "completed_at": completed_at,
    }
    receipt: dict[str, Any] = {
        "receipt_id": f"portfolio-run-{canonical_hash(seed)[:24].lower()}",
        "status": "current",
        "guard_runtime": dict(guard_runtime),
        "source_fingerprint": source_fingerprint,
        "contract_hash": contract_hash,
        "command_set": command_set,
        "command_fingerprint": seed["command_fingerprint"],
        "environment": environment,
        "environment_fingerprint": seed["environment_fingerprint"],
        "coverage_fingerprint": seed["coverage_fingerprint"],
        "production_revalidation_bindings": production_rows,
        "production_revalidation_fingerprint": seed[
            "production_revalidation_fingerprint"
        ],
        "result_bundle": result_bundle,
        "result_hash": seed["result_hash"],
        "completed_at": completed_at,
        "claim_boundary": (
            (
                "Verifier-assembled from exact current capability child execution plus one replayed scheduled-production "
                "binding for every target member, including exact declared-check receipts, enforced terminal completion, "
                "and the shared current installed runtime identity."
            )
            if production_rows
            else (
                "Capability-stage verifier output only. It is not a graduation receipt and cannot substitute for "
                "per-member scheduled-production revalidation."
            )
        ),
    }
    receipt["receipt_hash"] = canonical_hash(receipt)
    return receipt, []


def assemble_full_run_receipt(
    *,
    skill_id: str,
    guard_runtime: Mapping[str, Any],
    source_fingerprint: str,
    contract_hash: str,
    representative_jobs: object,
    evidence_root: Path | None,
    production_revalidation_bindings: object,
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    """Assemble production-authoritative evidence; bindings are mandatory."""

    return _assemble_portfolio_run_receipt(
        skill_id=skill_id,
        guard_runtime=guard_runtime,
        source_fingerprint=source_fingerprint,
        contract_hash=contract_hash,
        representative_jobs=representative_jobs,
        evidence_root=evidence_root,
        production_revalidation_bindings=production_revalidation_bindings,
        require_production_revalidation=True,
    )


def assemble_capability_stage_receipt(
    *,
    skill_id: str,
    guard_runtime: Mapping[str, Any],
    source_fingerprint: str,
    contract_hash: str,
    representative_jobs: object,
    evidence_root: Path | None,
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    """Assemble source-only capability evidence with no graduation authority."""

    receipt, findings = _assemble_portfolio_run_receipt(
        skill_id=skill_id,
        guard_runtime=guard_runtime,
        source_fingerprint=source_fingerprint,
        contract_hash=contract_hash,
        representative_jobs=representative_jobs,
        evidence_root=evidence_root,
        production_revalidation_bindings=[],
        require_production_revalidation=False,
    )
    if receipt is None:
        return None, findings
    capability = dict(receipt)
    capability.pop("receipt_hash", None)
    capability["schema_version"] = PORTFOLIO_CAPABILITY_STAGE_RECEIPT_SCHEMA
    capability["status"] = "capability_validated"
    capability["authority_domain"] = "capability_validation"
    capability["claim_boundary"] = (
        "Capability-stage verifier output only. It proves the exact ephemeral "
        "representative jobs but cannot authorize graduation, current portfolio "
        "status, reuse, scheduled production, or installation closure."
    )
    semantic = dict(capability)
    semantic.pop("receipt_id", None)
    capability["receipt_id"] = (
        "portfolio-capability-" + canonical_hash(semantic)[:24].lower()
    )
    capability["receipt_hash"] = canonical_hash(capability)
    return capability, []


def _full_receipt_payload_findings(
    receipt: Mapping[str, Any],
    jobs: Sequence[Mapping[str, Any]],
    *,
    skill_id: str,
    evidence_root: Path | None,
    production_revalidation_bindings: object,
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    expected_command_set, expected_environment, execution_findings = _derived_execution_payloads(
        jobs,
        evidence_root=evidence_root,
    )
    findings.extend(execution_findings)
    expected_production_rows = (
        [dict(row) for row in production_revalidation_bindings]
        if isinstance(production_revalidation_bindings, list)
        and all(isinstance(row, Mapping) for row in production_revalidation_bindings)
        else []
    )
    expected_production_fingerprint = (
        portfolio_production_revalidation_fingerprint(expected_production_rows)
    )
    if not expected_production_fingerprint:
        findings.append(
            _finding(
                "graduation_production_revalidation_bindings_missing",
                skill_id=skill_id,
            )
        )
    if receipt.get("production_revalidation_bindings") != expected_production_rows:
        findings.append(
            _finding(
                "graduation_production_revalidation_binding_mismatch",
                skill_id=skill_id,
            )
        )
    if (
        receipt.get("production_revalidation_fingerprint")
        != expected_production_fingerprint
    ):
        findings.append(
            _finding(
                "graduation_production_revalidation_fingerprint_mismatch",
                skill_id=skill_id,
            )
        )
    command_set = receipt.get("command_set")
    if not isinstance(command_set, Mapping) or not command_set:
        findings.append(_finding("graduation_command_set_missing", skill_id=skill_id))
    else:
        command_jobs = command_set.get("jobs")
        command_job_ids: set[str] = set()
        if not isinstance(command_jobs, list) or not command_jobs:
            findings.append(_finding("graduation_command_jobs_missing", skill_id=skill_id))
        else:
            for row in command_jobs:
                if not isinstance(row, Mapping):
                    findings.append(_finding("graduation_command_job_invalid", skill_id=skill_id))
                    continue
                job_id = str(row.get("job_id", ""))
                executions = row.get("executions")
                if (
                    not job_id
                    or job_id in command_job_ids
                    or not isinstance(executions, list)
                    or not executions
                ):
                    findings.append(
                        _finding("graduation_command_job_invalid", skill_id=skill_id, detail=job_id)
                    )
                command_job_ids.add(job_id)
            expected_job_ids = {str(job["job_id"]) for job in jobs}
            if command_job_ids != expected_job_ids:
                findings.append(
                    _finding(
                        "graduation_command_job_coverage_mismatch",
                        skill_id=skill_id,
                        detail=",".join(sorted(expected_job_ids - command_job_ids)),
                    )
                )
        if command_set != expected_command_set:
            findings.append(_finding("graduation_command_payload_mismatch", skill_id=skill_id))
        if receipt.get("command_fingerprint") != canonical_hash(command_set):
            findings.append(_finding("graduation_command_fingerprint_mismatch", skill_id=skill_id))
    environment = receipt.get("environment")
    if not isinstance(environment, Mapping) or not environment:
        findings.append(_finding("graduation_environment_missing", skill_id=skill_id))
    else:
        if environment != expected_environment:
            findings.append(_finding("graduation_environment_payload_mismatch", skill_id=skill_id))
        if receipt.get("environment_fingerprint") != canonical_hash(environment):
            findings.append(_finding("graduation_environment_fingerprint_mismatch", skill_id=skill_id))
    result_bundle = receipt.get("result_bundle")
    if not isinstance(result_bundle, Mapping) or not result_bundle:
        findings.append(_finding("graduation_result_bundle_missing", skill_id=skill_id))
    else:
        actual_rows, result_findings = _normalized_result_job_rows(
            result_bundle.get("representative_job_results")
        )
        expected_rows = [
            {
                "job_id": str(job["job_id"]),
                "job_class_ids": sorted(str(item) for item in job.get("job_class_ids", [])),
                "member_skill_id": str(job.get("member_skill_id", "")),
                "member_contract_hash": str(job.get("member_contract_hash", "")),
                "covered_capability_ids": sorted(
                    str(item) for item in job["covered_capability_ids"]
                ),
                "evidence_refs": sorted(str(item) for item in job["evidence_refs"]),
                "outcome": JOB_CLASS_EXPECTED_OUTCOMES[
                    str(next(iter(job.get("job_class_ids", [])), ""))
                ],
                "status": "verified",
            }
            for job in jobs
        ]
        expected_rows.sort(key=lambda item: item["job_id"])
        if result_findings or actual_rows != expected_rows:
            findings.append(
                _finding(
                    "graduation_result_job_binding_mismatch",
                    skill_id=skill_id,
                    detail=",".join(result_findings),
                )
            )
        if receipt.get("result_hash") != canonical_hash(result_bundle):
            findings.append(_finding("graduation_result_hash_mismatch", skill_id=skill_id))
    assembled, assembly_findings = assemble_full_run_receipt(
        skill_id=skill_id,
        guard_runtime=(
            receipt.get("guard_runtime")
            if isinstance(receipt.get("guard_runtime"), Mapping)
            else {}
        ),
        source_fingerprint=str(receipt.get("source_fingerprint", "")),
        contract_hash=str(receipt.get("contract_hash", "")),
        representative_jobs=jobs,
        evidence_root=evidence_root,
        production_revalidation_bindings=expected_production_rows,
    )
    findings.extend(assembly_findings)
    if assembled is not None and dict(receipt) != assembled:
        findings.append(
            _finding("full_run_receipt_not_verifier_assembled", skill_id=skill_id)
        )
    return findings


def _ticket_hash(ticket: Mapping[str, Any]) -> str:
    payload = dict(ticket)
    payload.pop("ticket_hash", None)
    return canonical_hash(payload)


def _guard_change_record_hash(change: Mapping[str, Any]) -> str:
    payload = dict(change)
    payload.pop("change_hash", None)
    return canonical_hash(payload)


def portfolio_scope_hash(scope: Mapping[str, Any]) -> str:
    unsigned = dict(scope)
    unsigned.pop("manifest_hash", None)
    return canonical_hash(unsigned)


def portfolio_registry_hash(registry: Mapping[str, Any]) -> str:
    unsigned = dict(registry)
    unsigned.pop("registry_hash", None)
    return canonical_hash(unsigned)


def build_current_portfolio_registry(
    scope: Mapping[str, Any],
    *,
    registry_id: str,
    scope_manifest_ref: str,
    active_guard: Mapping[str, Any],
    evidence_root: Path,
    issued_at: str,
) -> dict[str, Any]:
    """Build revision one directly from the sole reviewed current scope.

    This is deliberately not a migration.  It consumes no prior registry and
    carries forward no historical green receipt, reuse ticket, graduation, or
    transaction authority.
    """

    if not isinstance(registry_id, str) or not registry_id.strip():
        raise ValueError("portfolio_current_registry_id_missing")
    if not isinstance(scope_manifest_ref, str) or not scope_manifest_ref:
        raise ValueError("portfolio_current_scope_ref_missing")
    if not _timestamp_ok(issued_at):
        raise ValueError("portfolio_current_registry_timestamp_invalid")
    scope_findings = validate_scope_manifest(scope)
    if scope_findings:
        raise ValueError(
            "portfolio_current_scope_invalid:"
            + ",".join(sorted({row["code"] for row in scope_findings}))
        )
    if not _guard_ok(active_guard):
        raise ValueError("portfolio_current_guard_invalid")

    entries: list[dict[str, Any]] = []
    for target in scope.get("targets", []):
        if not isinstance(target, Mapping):
            raise ValueError("portfolio_current_scope_target_invalid")
        skill_id = str(target.get("skill_id", ""))
        lifecycle = str(target.get("lifecycle", ""))
        if lifecycle in ACTIVE_LIFECYCLES:
            graduation_status = (
                "pending"
                if lifecycle == "pending_adoption"
                else "revalidation_required"
            )
            entry: dict[str, Any] = {
                "skill_id": skill_id,
                "target_kind": str(target.get("target_kind", "")),
                "skill_paths": list(target.get("skill_paths", [])),
                "order": target.get("order"),
                "lifecycle": lifecycle,
                "graduation_status": graduation_status,
                "canonical_source": copy.deepcopy(target.get("canonical_source")),
                "consumed_guard_feature_tags": list(
                    target.get("consumed_guard_feature_tags", [])
                ),
                "capability_inventory_status": "current",
                "required_capability_ids": list(
                    target.get("required_capability_ids", [])
                ),
                "member_capability_inventory": copy.deepcopy(
                    target.get("member_capability_inventory", [])
                ),
                "required_job_class_ids": list(
                    target.get("required_job_class_ids", [])
                ),
                "unresolved_failure_ids": [],
                "reuse_ticket": None,
                "reuse_ticket_chain": [],
            }
            repository = target.get("repository")
            if isinstance(repository, Mapping):
                entry["repository"] = copy.deepcopy(repository)
            if graduation_status == "revalidation_required":
                entry["revalidation_reason"] = (
                    "current_scope_direct_replacement_requires_fresh_evidence"
                )
            entries.append(entry)
            continue
        if lifecycle in EXCLUDED_LIFECYCLES:
            approval = target.get("exclusion_approval")
            if not isinstance(approval, Mapping):
                raise ValueError(
                    f"portfolio_current_exclusion_approval_missing:{skill_id}"
                )
            entry = {
                "skill_id": skill_id,
                "order": None,
                "lifecycle": lifecycle,
                "graduation_status": "excluded",
                "exclusion_reason": str(approval.get("reason", "")),
                "exclusion_decision_id": str(approval.get("decision_id", "")),
            }
            for field in (
                "retirement_disposition",
                "superseded_by_skill_id",
                "installation_disposition",
                "router_authority",
            ):
                if field in target:
                    entry[field] = target[field]
            entries.append(entry)
            continue
        if lifecycle == SUPPORTING_LIFECYCLE:
            entries.append(
                {
                    "skill_id": skill_id,
                    "order": None,
                    "lifecycle": lifecycle,
                    "graduation_status": "supporting",
                    "parent_skill_id": str(target.get("parent_skill_id", "")),
                }
            )
            continue
        raise ValueError(f"portfolio_current_lifecycle_invalid:{skill_id}")

    registry: dict[str, Any] = {
        "schema_version": PORTFOLIO_REGISTRY_SCHEMA,
        "registry_id": registry_id.strip(),
        "scope_manifest_id": str(scope.get("manifest_id", "")),
        "scope_manifest_hash": str(scope.get("manifest_hash", "")),
        "scope_manifest_ref": scope_manifest_ref,
        "revision": 1,
        "previous_registry_hash": "",
        "active_guard": copy.deepcopy(active_guard),
        "entries": entries,
        "transaction_history": [],
        "guard_change_history": [],
        "created_at": issued_at,
        "updated_at": issued_at,
    }
    _refresh_registry_hash(registry)
    registry_findings = validate_registry(
        registry,
        evidence_root=evidence_root.resolve(),
    )
    if registry_findings:
        raise ValueError(
            "portfolio_current_registry_invalid:"
            + ",".join(sorted({row["code"] for row in registry_findings}))
        )
    return registry


def _supersession_lifecycle_findings(
    entries_by_id: Mapping[str, Mapping[str, Any]],
    *,
    finding_prefix: str,
) -> list[dict[str, str]]:
    """Validate the complete, target-neutral superseded-skill authority tuple."""

    findings: list[dict[str, str]] = []
    supersession_fields = (
        "retirement_disposition",
        "superseded_by_skill_id",
        "installation_disposition",
        "router_authority",
    )
    for skill_id, entry in entries_by_id.items():
        if not any(field in entry for field in supersession_fields):
            continue
        if any(field not in entry for field in supersession_fields):
            findings.append(
                _finding(
                    f"{finding_prefix}_supersession_tuple_incomplete",
                    skill_id=skill_id,
                )
            )
            continue
        if entry.get("lifecycle") != "retired_private":
            findings.append(
                _finding(
                    f"{finding_prefix}_supersession_lifecycle_invalid",
                    skill_id=skill_id,
                )
            )
        if entry.get("retirement_disposition") != "superseded":
            findings.append(
                _finding(
                    f"{finding_prefix}_retirement_disposition_invalid",
                    skill_id=skill_id,
                )
            )
        replacement_id = entry.get("superseded_by_skill_id")
        if not isinstance(replacement_id, str) or not replacement_id:
            findings.append(
                _finding(
                    f"{finding_prefix}_superseded_by_missing",
                    skill_id=skill_id,
                )
            )
        elif replacement_id == skill_id:
            findings.append(
                _finding(
                    f"{finding_prefix}_supersession_self_reference",
                    skill_id=skill_id,
                )
            )
        else:
            replacement = entries_by_id.get(replacement_id)
            if replacement is None:
                findings.append(
                    _finding(
                        f"{finding_prefix}_superseding_target_missing",
                        skill_id=skill_id,
                        detail=replacement_id,
                    )
                )
            elif replacement.get("lifecycle") not in ACTIVE_LIFECYCLES:
                findings.append(
                    _finding(
                        f"{finding_prefix}_superseding_target_not_active",
                        skill_id=skill_id,
                        detail=replacement_id,
                    )
                )
        if entry.get("installation_disposition") != "absent":
            findings.append(
                _finding(
                    f"{finding_prefix}_superseded_installation_authority_invalid",
                    skill_id=skill_id,
                )
            )
        if entry.get("router_authority") != "blocked":
            findings.append(
                _finding(
                    f"{finding_prefix}_superseded_router_authority_invalid",
                    skill_id=skill_id,
                )
            )
    return findings


def _refresh_registry_hash(registry: dict[str, Any]) -> dict[str, Any]:
    registry["registry_hash"] = portfolio_registry_hash(registry)
    return registry


def _mutation_precondition_findings(
    registry: Mapping[str, Any], request: Mapping[str, Any]
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    transaction_id = request.get("transaction_id")
    if not isinstance(transaction_id, str) or not transaction_id.strip():
        findings.append(_finding("portfolio_mutation_transaction_id_missing"))
    expected_revision = request.get("expected_registry_revision")
    if (
        not isinstance(expected_revision, int)
        or isinstance(expected_revision, bool)
        or expected_revision < 1
    ):
        findings.append(_finding("portfolio_mutation_expected_revision_invalid"))
    elif expected_revision != registry.get("revision"):
        findings.append(
            _finding(
                "portfolio_mutation_stale_revision",
                detail=f"expected={expected_revision};actual={registry.get('revision')}",
            )
        )
    base_hash = request.get("base_registry_hash")
    if not _hash_ok(base_hash):
        findings.append(_finding("portfolio_mutation_base_hash_invalid"))
    elif base_hash != registry.get("registry_hash"):
        findings.append(_finding("portfolio_mutation_stale_base_hash"))
    history = registry.get("transaction_history", [])
    if isinstance(history, list) and any(
        isinstance(row, Mapping) and row.get("transaction_id") == transaction_id
        for row in history
    ):
        findings.append(_finding("portfolio_mutation_transaction_id_duplicate"))
    return findings


def _matching_committed_transaction(
    registry: Mapping[str, Any],
    request: Mapping[str, Any],
    *,
    mutation_kind: str,
) -> Mapping[str, Any] | None:
    transaction_id = request.get("transaction_id")
    if not isinstance(transaction_id, str) or not transaction_id:
        return None
    for row in registry.get("transaction_history", []):
        if (
            isinstance(row, Mapping)
            and row.get("transaction_id") == transaction_id
            and row.get("mutation_kind") == mutation_kind
            and row.get("request_hash") == canonical_hash(request)
        ):
            return row
    return None


def _append_registry_transaction(
    updated: dict[str, Any],
    base_registry: Mapping[str, Any],
    request: Mapping[str, Any],
    *,
    mutation_kind: str,
    committed_at: str,
    artifact_hashes: Sequence[str] = (),
) -> None:
    updated.setdefault("transaction_history", []).append(
        {
            "schema_version": "skillguard.portfolio_registry_transaction.v1",
            "transaction_id": str(request["transaction_id"]),
            "mutation_kind": mutation_kind,
            "base_registry_revision": int(base_registry["revision"]),
            "base_registry_hash": str(base_registry["registry_hash"]),
            "committed_registry_revision": int(base_registry["revision"]) + 1,
            "scope_manifest_hash": str(base_registry.get("scope_manifest_hash", "")),
            "request_hash": canonical_hash(request),
            "artifact_hashes": sorted(str(value) for value in artifact_hashes),
            "committed_at": committed_at,
        }
    )


def validate_scope_manifest(scope: object) -> list[dict[str, str]]:
    if not isinstance(scope, Mapping):
        return [_finding("portfolio_scope_not_object")]
    findings: list[dict[str, str]] = []
    if scope.get("schema_version") != PORTFOLIO_SCOPE_SCHEMA:
        findings.append(_finding("portfolio_scope_schema_unsupported"))
    if not isinstance(scope.get("manifest_id"), str) or not scope.get("manifest_id"):
        findings.append(_finding("portfolio_scope_id_missing"))
    revision = scope.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        findings.append(_finding("portfolio_scope_revision_invalid"))
    if not _timestamp_ok(scope.get("approved_at")):
        findings.append(_finding("portfolio_scope_approval_timestamp_invalid"))
    approval = scope.get("approval")
    if (
        not isinstance(approval, Mapping)
        or approval.get("status") != "user_confirmed"
        or not isinstance(approval.get("decision_id"), str)
        or not approval.get("decision_id")
    ):
        findings.append(_finding("portfolio_scope_approval_missing"))
    if scope.get("manifest_hash") != portfolio_scope_hash(scope):
        findings.append(_finding("portfolio_scope_hash_mismatch"))
    targets = scope.get("targets")
    if not isinstance(targets, list):
        return findings + [_finding("portfolio_scope_targets_not_list")]
    seen_ids: set[str] = set()
    active_orders: set[int] = set()
    active_count = 0
    for index, target in enumerate(targets):
        if not isinstance(target, Mapping):
            findings.append(_finding("portfolio_scope_target_not_object", detail=str(index)))
            continue
        skill_id = str(target.get("skill_id", ""))
        if not skill_id:
            findings.append(_finding("portfolio_scope_skill_id_missing", detail=str(index)))
        elif skill_id in seen_ids:
            findings.append(_finding("portfolio_scope_skill_id_duplicate", skill_id=skill_id))
        seen_ids.add(skill_id)
        lifecycle = str(target.get("lifecycle", ""))
        allowed = ACTIVE_LIFECYCLES | EXCLUDED_LIFECYCLES | {SUPPORTING_LIFECYCLE}
        if lifecycle not in allowed:
            findings.append(_finding("portfolio_scope_lifecycle_invalid", skill_id=skill_id))
        order = target.get("order")
        if lifecycle in ACTIVE_LIFECYCLES:
            active_count += 1
            if not isinstance(order, int) or isinstance(order, bool) or order < 0:
                findings.append(_finding("portfolio_scope_active_order_invalid", skill_id=skill_id))
            elif order in active_orders:
                findings.append(_finding("portfolio_scope_active_order_duplicate", skill_id=skill_id))
            else:
                active_orders.add(order)
            source = target.get("canonical_source")
            if (
                not isinstance(source, Mapping)
                or not isinstance(source.get("path_token"), str)
                or not source.get("path_token")
                or not isinstance(source.get("repository_identity"), Mapping)
            ):
                findings.append(_finding("portfolio_scope_canonical_source_invalid", skill_id=skill_id))
            else:
                if "target_kind" not in target or "skill_paths" not in target:
                    findings.append(
                        _finding("portfolio_scope_target_topology_missing", skill_id=skill_id)
                    )
                _target_kind, _primary_path, _skill_paths, source_findings = (
                    _target_source_configuration(target, skill_id=skill_id)
                )
                findings.extend(source_findings)
                path_token = Path(str(source["path_token"]))
                if path_token.is_absolute() or path_token.drive or ".." in path_token.parts:
                    findings.append(
                        _finding("portfolio_scope_canonical_source_path_invalid", skill_id=skill_id)
                    )
                if any(
                    not isinstance(source["repository_identity"].get(field), str)
                    or not source["repository_identity"].get(field)
                    for field in ("host", "owner", "name", "visibility")
                ):
                    findings.append(
                        _finding("portfolio_scope_repository_identity_invalid", skill_id=skill_id)
                    )
            required_capabilities = _unique_string_list(target.get("required_capability_ids"))
            if not required_capabilities:
                findings.append(_finding("portfolio_scope_capability_inventory_missing", skill_id=skill_id))
            findings.extend(_member_capability_inventory_findings(target))
            required_classes = _unique_string_list(target.get("required_job_class_ids"))
            if not required_classes or not set(DEFAULT_REQUIRED_JOB_CLASS_IDS).issubset(required_classes):
                findings.append(_finding("portfolio_scope_job_class_baseline_missing", skill_id=skill_id))
            if _unique_string_list(target.get("consumed_guard_feature_tags")) is None:
                findings.append(_finding("portfolio_scope_guard_tags_invalid", skill_id=skill_id))
        elif order is not None:
            findings.append(_finding("portfolio_scope_non_active_order_invalid", skill_id=skill_id))
        if lifecycle in EXCLUDED_LIFECYCLES:
            exclusion = target.get("exclusion_approval")
            if (
                not isinstance(exclusion, Mapping)
                or exclusion.get("status") != "user_confirmed"
                or not isinstance(exclusion.get("decision_id"), str)
                or not exclusion.get("decision_id")
                or not isinstance(exclusion.get("reason"), str)
                or not exclusion.get("reason")
            ):
                findings.append(_finding("portfolio_scope_exclusion_approval_missing", skill_id=skill_id))
        if lifecycle == SUPPORTING_LIFECYCLE and not target.get("parent_skill_id"):
            findings.append(_finding("portfolio_scope_supporting_parent_missing", skill_id=skill_id))
    policy = scope.get("scope_policy")
    if not isinstance(policy, Mapping):
        findings.append(_finding("portfolio_scope_policy_missing"))
    else:
        if policy.get("local_first") is not True:
            findings.append(_finding("portfolio_scope_local_first_policy_missing"))
        if policy.get("active_target_count") != active_count:
            findings.append(_finding("portfolio_scope_active_count_mismatch"))
    if active_orders and active_orders != set(range(active_count)):
        findings.append(_finding("portfolio_scope_active_order_not_contiguous"))
    targets_by_id = {
        str(row.get("skill_id", "")): row
        for row in targets
        if isinstance(row, Mapping) and row.get("skill_id")
    }
    findings.extend(
        _supersession_lifecycle_findings(
            targets_by_id,
            finding_prefix="portfolio_scope",
        )
    )
    for skill_id, target in targets_by_id.items():
        if target.get("lifecycle") != SUPPORTING_LIFECYCLE:
            continue
        parent = targets_by_id.get(str(target.get("parent_skill_id", "")))
        if parent is None or parent.get("lifecycle") not in ACTIVE_LIFECYCLES:
            findings.append(
                _finding("portfolio_scope_supporting_parent_not_active", skill_id=skill_id)
            )
    if not isinstance(scope.get("claim_boundary"), str) or not scope.get("claim_boundary"):
        findings.append(_finding("portfolio_scope_claim_boundary_missing"))
    return findings


def _load_registry_scope(
    registry: Mapping[str, Any],
    *,
    evidence_root: Path | None,
) -> tuple[Mapping[str, Any] | None, list[dict[str, str]]]:
    ref = registry.get("scope_manifest_ref")
    if not isinstance(ref, str):
        return None, [_finding("portfolio_scope_ref_missing")]
    scope, _relative, findings = _load_hash_bound_json(
        ref,
        evidence_root=evidence_root,
        finding_prefix="portfolio_scope_manifest",
    )
    if scope is None:
        return None, findings
    findings.extend(validate_scope_manifest(scope))
    if registry.get("scope_manifest_id") != scope.get("manifest_id"):
        findings.append(_finding("portfolio_scope_id_binding_mismatch"))
    if registry.get("scope_manifest_hash") != scope.get("manifest_hash"):
        findings.append(_finding("portfolio_scope_hash_binding_mismatch"))
    return scope, findings


def validate_registry(
    registry: object,
    *,
    evidence_root: Path | None = None,
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if not isinstance(registry, Mapping):
        return [_finding("registry_not_object")]
    if registry.get("schema_version") != PORTFOLIO_REGISTRY_SCHEMA:
        findings.append(_finding("registry_schema_unsupported"))
    if not isinstance(registry.get("registry_id"), str) or not registry.get("registry_id"):
        findings.append(_finding("registry_id_missing"))
    if not _guard_ok(registry.get("active_guard")):
        findings.append(_finding("active_guard_invalid"))
    revision = registry.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        findings.append(_finding("registry_revision_invalid"))
    if registry.get("registry_hash") != portfolio_registry_hash(registry):
        findings.append(_finding("registry_hash_mismatch"))
    transactions = registry.get("transaction_history")
    if not isinstance(transactions, list):
        findings.append(_finding("portfolio_transaction_history_not_list"))
    else:
        seen_transaction_ids: set[str] = set()
        for index, transaction in enumerate(transactions):
            if not isinstance(transaction, Mapping):
                findings.append(
                    _finding("portfolio_transaction_not_object", detail=str(index))
                )
                continue
            transaction_id = str(transaction.get("transaction_id", ""))
            if (
                transaction.get("schema_version")
                != "skillguard.portfolio_registry_transaction.v1"
            ):
                findings.append(
                    _finding(
                        "portfolio_transaction_schema_unsupported",
                        detail=transaction_id or str(index),
                    )
                )
            if not transaction_id:
                findings.append(
                    _finding("portfolio_transaction_id_missing", detail=str(index))
                )
            elif transaction_id in seen_transaction_ids:
                findings.append(
                    _finding("portfolio_transaction_id_duplicate", detail=transaction_id)
                )
            seen_transaction_ids.add(transaction_id)
            base_revision = transaction.get("base_registry_revision")
            committed_revision = transaction.get("committed_registry_revision")
            if (
                not isinstance(base_revision, int)
                or isinstance(base_revision, bool)
                or not isinstance(committed_revision, int)
                or isinstance(committed_revision, bool)
                or committed_revision != base_revision + 1
            ):
                findings.append(
                    _finding(
                        "portfolio_transaction_revision_invalid", detail=transaction_id
                    )
                )
            if not _hash_ok(transaction.get("base_registry_hash")):
                findings.append(
                    _finding(
                        "portfolio_transaction_base_hash_invalid", detail=transaction_id
                    )
                )
            if transaction.get("scope_manifest_hash") != registry.get(
                "scope_manifest_hash"
            ):
                findings.append(
                    _finding(
                        "portfolio_transaction_scope_mismatch", detail=transaction_id
                    )
                )
            if not _hash_ok(transaction.get("request_hash")):
                findings.append(
                    _finding(
                        "portfolio_transaction_request_hash_invalid", detail=transaction_id
                    )
                )
            artifact_hashes = _unique_string_list(
                transaction.get("artifact_hashes", [])
            )
            if artifact_hashes is None or any(
                not _hash_ok(value) for value in artifact_hashes
            ):
                findings.append(
                    _finding(
                        "portfolio_transaction_artifact_hashes_invalid",
                        detail=transaction_id,
                    )
                )
            if not _timestamp_ok(transaction.get("committed_at")):
                findings.append(
                    _finding(
                        "portfolio_transaction_timestamp_invalid", detail=transaction_id
                    )
                )
    if transactions:
        last = transactions[-1]
        if isinstance(last, Mapping):
            if last.get("committed_registry_revision") != registry.get("revision"):
                findings.append(_finding("portfolio_transaction_head_revision_mismatch"))
            if last.get("base_registry_hash") != registry.get(
                "previous_registry_hash"
            ):
                findings.append(_finding("portfolio_transaction_head_hash_mismatch"))
    elif registry.get("revision") != 1:
        findings.append(_finding("portfolio_transaction_history_missing_for_revision"))
    guard_history = registry.get("guard_change_history")
    if not isinstance(guard_history, list):
        findings.append(_finding("portfolio_guard_change_history_not_list"))
    else:
        previous_change_hash: str | None = None
        previous_guard_after: Mapping[str, Any] | None = None
        seen_change_ids: set[str] = set()
        for index, change in enumerate(guard_history):
            if not isinstance(change, Mapping):
                findings.append(_finding("portfolio_guard_change_not_object", detail=str(index)))
                continue
            change_id = str(change.get("change_id", ""))
            if not change_id or change_id in seen_change_ids:
                findings.append(_finding("portfolio_guard_change_id_invalid", detail=change_id or str(index)))
            seen_change_ids.add(change_id)
            if (
                not _guard_ok(change.get("guard_before"))
                or not _guard_ok(change.get("guard_after"))
                or _unique_string_list(change.get("affected_feature_tags")) is None
                or WIRE_HASH_RE.fullmatch(
                    str(change.get("impact_graph_hash", ""))
                )
                is None
                or (
                    (changed_ids := _unique_string_list(
                        change.get("changed_component_ids")
                    ))
                    is None
                    or not changed_ids
                    or changed_ids != sorted(changed_ids)
                )
                or not isinstance(change.get("reason"), str)
                or not change.get("reason")
                or not _timestamp_ok(change.get("recorded_at"))
            ):
                findings.append(_finding("portfolio_guard_change_record_invalid", detail=change_id))
            _required_targets, _required_members, _required_impact, impact_scope_findings = (
                _guard_change_required_scope(change)
            )
            if impact_scope_findings:
                findings.append(
                    _finding(
                        "portfolio_guard_change_impact_scope_invalid",
                        detail=f"{change_id}:{';'.join(impact_scope_findings)}",
                    )
                )
            if change.get("previous_change_hash") != previous_change_hash:
                findings.append(_finding("portfolio_guard_change_chain_gap", detail=change_id))
            if change.get("change_hash") != _guard_change_record_hash(change):
                findings.append(_finding("portfolio_guard_change_hash_mismatch", detail=change_id))
            if previous_guard_after is not None and not _same_guard(
                change.get("guard_before"), previous_guard_after
            ):
                findings.append(_finding("portfolio_guard_change_guard_fork", detail=change_id))
            previous_change_hash = str(change.get("change_hash", ""))
            previous_guard_after = change.get("guard_after") if isinstance(change.get("guard_after"), Mapping) else None
        if guard_history and not _same_guard(
            guard_history[-1].get("guard_after") if isinstance(guard_history[-1], Mapping) else None,
            registry.get("active_guard"),
        ):
            findings.append(_finding("portfolio_guard_change_head_not_active"))
    scope, scope_findings = _load_registry_scope(registry, evidence_root=evidence_root)
    findings.extend(scope_findings)
    entries = registry.get("entries")
    if not isinstance(entries, list):
        return findings + [_finding("entries_not_list")]

    seen_ids: set[str] = set()
    seen_orders: set[int] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            findings.append(_finding("entry_not_object", detail=str(index)))
            continue
        skill_id = str(entry.get("skill_id", ""))
        if not skill_id:
            findings.append(_finding("skill_id_missing", detail=str(index)))
        elif skill_id in seen_ids:
            findings.append(_finding("skill_id_duplicate", skill_id=skill_id))
        seen_ids.add(skill_id)
        lifecycle = str(entry.get("lifecycle", ""))
        allowed_lifecycles = ACTIVE_LIFECYCLES | EXCLUDED_LIFECYCLES | {SUPPORTING_LIFECYCLE}
        if lifecycle not in allowed_lifecycles:
            findings.append(_finding("lifecycle_invalid", skill_id=skill_id, detail=lifecycle))
        status = str(entry.get("graduation_status", ""))
        if status not in GRADUATION_STATUSES:
            findings.append(_finding("graduation_status_invalid", skill_id=skill_id, detail=status))

        order = entry.get("order")
        if lifecycle in ACTIVE_LIFECYCLES:
            if not isinstance(order, int) or isinstance(order, bool) or order < 0:
                findings.append(_finding("active_order_invalid", skill_id=skill_id))
            elif order in seen_orders:
                findings.append(_finding("active_order_duplicate", skill_id=skill_id, detail=str(order)))
            else:
                seen_orders.add(order)
            canonical_source = entry.get("canonical_source")
            if not isinstance(canonical_source, Mapping) or not canonical_source.get("path_token"):
                findings.append(_finding("canonical_source_missing", skill_id=skill_id))
            else:
                if "target_kind" not in entry or "skill_paths" not in entry:
                    findings.append(_finding("portfolio_target_topology_missing", skill_id=skill_id))
                _target_kind, _primary_path, _skill_paths, source_findings = (
                    _target_source_configuration(entry, skill_id=skill_id)
                )
                findings.extend(source_findings)
            if _string_list(entry.get("consumed_guard_feature_tags")) is None:
                findings.append(_finding("consumed_guard_feature_tags_invalid", skill_id=skill_id))
            if status not in ACTIVE_GRADUATION_STATUSES:
                findings.append(_finding("active_graduation_status_invalid", skill_id=skill_id, detail=status))
            inventory_status = str(entry.get("capability_inventory_status", "pending"))
            required_capabilities = _unique_string_list(entry.get("required_capability_ids", []))
            if inventory_status not in CAPABILITY_INVENTORY_STATUSES:
                findings.append(
                    _finding("capability_inventory_status_invalid", skill_id=skill_id, detail=inventory_status)
                )
            if required_capabilities is None:
                findings.append(_finding("required_capability_ids_invalid", skill_id=skill_id))
            elif inventory_status == "current" and not required_capabilities:
                findings.append(_finding("required_capability_ids_missing", skill_id=skill_id))
            if status == "current" and inventory_status != "current":
                findings.append(_finding("current_without_capability_inventory", skill_id=skill_id))
            findings.extend(_member_capability_inventory_findings(entry))
            member_statuses, member_status_findings = (
                _normalized_member_revalidation_statuses(
                    entry.get("member_revalidation_statuses")
                )
            )
            findings.extend(
                _finding(
                    code.split(":", 1)[0],
                    skill_id=skill_id,
                    detail=code,
                )
                for code in member_status_findings
            )
            if member_statuses:
                if entry.get("target_kind") != "skill_suite":
                    findings.append(
                        _finding(
                            "member_revalidation_statuses_non_suite",
                            skill_id=skill_id,
                        )
                    )
                inventory_rows, _inventory_findings = (
                    _normalized_member_capability_inventory(
                        entry.get("member_capability_inventory")
                    )
                )
                inventory_member_ids = {
                    str(row["member_skill_id"]) for row in inventory_rows
                }
                unknown_member_ids = sorted(
                    set(member_statuses) - inventory_member_ids
                )
                if unknown_member_ids:
                    findings.append(
                        _finding(
                            "member_revalidation_status_unknown_member",
                            skill_id=skill_id,
                            detail=",".join(unknown_member_ids),
                        )
                    )
                if status == "current":
                    findings.append(
                        _finding(
                            "portfolio_suite_hides_affected_member",
                            skill_id=skill_id,
                            detail=",".join(sorted(member_statuses)),
                        )
                    )
            if _unique_string_list(entry.get("unresolved_failure_ids", [])) is None:
                findings.append(_finding("unresolved_failure_ids_invalid", skill_id=skill_id))
            reuse_chain = entry.get("reuse_ticket_chain", [])
            if not isinstance(reuse_chain, list) or any(
                not isinstance(row, Mapping) for row in reuse_chain
            ):
                findings.append(_finding("reuse_ticket_chain_invalid", skill_id=skill_id))
            required_job_classes = _unique_string_list(
                entry.get("required_job_class_ids", list(DEFAULT_REQUIRED_JOB_CLASS_IDS))
            )
            if required_job_classes is None:
                findings.append(_finding("required_job_class_ids_invalid", skill_id=skill_id))
            elif not set(DEFAULT_REQUIRED_JOB_CLASS_IDS).issubset(required_job_classes):
                findings.append(_finding("required_job_class_baseline_missing", skill_id=skill_id))
        elif order is not None:
            findings.append(_finding("non_active_order_must_be_null", skill_id=skill_id))

        if lifecycle in EXCLUDED_LIFECYCLES:
            if status != "excluded":
                findings.append(_finding("excluded_status_invalid", skill_id=skill_id))
            if not isinstance(entry.get("exclusion_reason"), str) or not entry.get("exclusion_reason"):
                findings.append(_finding("exclusion_reason_missing", skill_id=skill_id))
        if lifecycle == SUPPORTING_LIFECYCLE:
            if status != "supporting":
                findings.append(_finding("supporting_status_invalid", skill_id=skill_id))
            if not isinstance(entry.get("parent_skill_id"), str) or not entry.get("parent_skill_id"):
                findings.append(_finding("supporting_parent_missing", skill_id=skill_id))

        failure = entry.get("failure_classification")
        if failure is not None and failure not in FAILURE_CLASSIFICATIONS:
            findings.append(_finding("failure_classification_invalid", skill_id=skill_id))

    entry_by_id = {
        str(entry.get("skill_id", "")): entry
        for entry in entries
        if isinstance(entry, Mapping) and entry.get("skill_id")
    }
    findings.extend(
        _supersession_lifecycle_findings(
            entry_by_id,
            finding_prefix="portfolio_registry",
        )
    )
    for entry in entries:
        if not isinstance(entry, Mapping) or entry.get("lifecycle") != SUPPORTING_LIFECYCLE:
            continue
        skill_id = str(entry.get("skill_id", ""))
        parent = entry_by_id.get(str(entry.get("parent_skill_id", "")))
        if parent is None or parent.get("lifecycle") not in ACTIVE_LIFECYCLES:
            findings.append(_finding("supporting_parent_not_active", skill_id=skill_id))
    if isinstance(scope, Mapping):
        scope_targets = {
            str(row.get("skill_id", "")): row
            for row in scope.get("targets", [])
            if isinstance(row, Mapping) and row.get("skill_id")
        }
        if set(entry_by_id) != set(scope_targets):
            missing = sorted(set(scope_targets) - set(entry_by_id))
            extra = sorted(set(entry_by_id) - set(scope_targets))
            findings.append(
                _finding(
                    "portfolio_registry_scope_set_mismatch",
                    detail=f"missing={','.join(missing)};extra={','.join(extra)}",
                )
            )
        for skill_id in sorted(set(entry_by_id) & set(scope_targets)):
            entry = entry_by_id[skill_id]
            target = scope_targets[skill_id]
            for field in ("order", "lifecycle"):
                if entry.get(field) != target.get(field):
                    findings.append(
                        _finding(f"portfolio_registry_scope_{field}_mismatch", skill_id=skill_id)
                    )
            if target.get("lifecycle") in ACTIVE_LIFECYCLES:
                entry_source = entry.get("canonical_source")
                target_source = target.get("canonical_source")
                entry_config = _target_source_configuration(
                    entry, skill_id=skill_id
                )
                target_config = _target_source_configuration(
                    target, skill_id=skill_id
                )
                if (
                    not isinstance(entry_source, Mapping)
                    or not isinstance(target_source, Mapping)
                    or entry_source.get("path_token") != target_source.get("path_token")
                    or entry_source.get("repository_identity")
                    != target_source.get("repository_identity")
                    or entry_config[:3] != target_config[:3]
                ):
                    findings.append(
                        _finding("portfolio_registry_scope_source_mismatch", skill_id=skill_id)
                    )
                for field in (
                    "required_capability_ids",
                    "required_job_class_ids",
                    "consumed_guard_feature_tags",
                ):
                    if sorted(entry.get(field, [])) != sorted(target.get(field, [])):
                        findings.append(
                            _finding(f"portfolio_registry_scope_{field}_mismatch", skill_id=skill_id)
                        )
                entry_inventory, _entry_inventory_findings = (
                    _normalized_member_capability_inventory(
                        entry.get("member_capability_inventory")
                    )
                )
                target_inventory, _target_inventory_findings = (
                    _normalized_member_capability_inventory(
                        target.get("member_capability_inventory")
                    )
                )
                if entry_inventory != target_inventory:
                    findings.append(
                        _finding(
                            "portfolio_registry_scope_member_capability_inventory_mismatch",
                            skill_id=skill_id,
                        )
                    )
            if target.get("lifecycle") in EXCLUDED_LIFECYCLES:
                expected_reason = target.get("exclusion_approval", {}).get("reason")
                if entry.get("exclusion_reason") != expected_reason:
                    findings.append(
                        _finding("portfolio_registry_scope_exclusion_mismatch", skill_id=skill_id)
                    )
                for field in (
                    "retirement_disposition",
                    "superseded_by_skill_id",
                    "installation_disposition",
                    "router_authority",
                ):
                    if entry.get(field) != target.get(field):
                        findings.append(
                            _finding(
                                f"portfolio_registry_scope_{field}_mismatch",
                                skill_id=skill_id,
                            )
                        )
            if target.get("lifecycle") == SUPPORTING_LIFECYCLE and entry.get(
                "parent_skill_id"
            ) != target.get("parent_skill_id"):
                findings.append(
                    _finding("portfolio_registry_scope_parent_mismatch", skill_id=skill_id)
                )
    return findings


def _full_receipt_is_current(
    entry: Mapping[str, Any],
    active_guard: Mapping[str, Any],
    *,
    evidence_root: Path | None,
    registry_id: str,
    scope_manifest_id: str,
    scope_manifest_hash: str,
    target_repository_root: Path | None = None,
    installation_context_holder: list[object] | None = None,
) -> bool:
    receipt = entry.get("full_run_receipt")
    source = entry.get("canonical_source")
    if not _full_receipt_identity_complete(receipt):
        return False
    assert isinstance(receipt, Mapping)
    if not isinstance(source, Mapping) or receipt.get("source_fingerprint") != source.get("source_fingerprint"):
        return False
    if receipt.get("contract_hash") != entry.get("contract_hash"):
        return False
    target_identity = entry.get("target_identity_receipt")
    if (
        not isinstance(target_identity, Mapping)
        or _target_identity_findings(target_identity)
        or target_identity.get("target_kind") != entry.get("target_kind")
        or sorted(target_identity.get("skill_paths", []))
        != sorted(entry.get("skill_paths", []))
        or target_identity.get("source_fingerprint") != source.get("source_fingerprint")
        or target_identity.get("contract_hash") != entry.get("contract_hash")
    ):
        return False
    jobs, job_findings = _normalized_representative_jobs(
        entry.get("representative_jobs"), require_job_classes=True
    )
    if job_findings or receipt.get("coverage_fingerprint") != representative_jobs_coverage_fingerprint(jobs):
        return False
    if _full_receipt_payload_findings(
        receipt,
        jobs,
        skill_id=str(entry.get("skill_id", "")),
        evidence_root=evidence_root,
        production_revalidation_bindings=receipt.get(
            "production_revalidation_bindings"
        ),
    ):
        return False
    if (
        entry.get("production_revalidation_bindings")
        != receipt.get("production_revalidation_bindings")
        or entry.get("production_revalidation_fingerprint")
        != receipt.get("production_revalidation_fingerprint")
    ):
        return False
    if target_repository_root is None:
        return False
    target_kind, primary_skill_path, skill_paths, topology_findings = (
        _target_source_configuration(
            entry, skill_id=str(entry.get("skill_id", ""))
        )
    )
    if topology_findings:
        return False
    current_target_identity, current_identity_findings = derive_target_identity(
        target_repository_root,
        skill_root_relative=primary_skill_path,
        expected_skill_id=str(entry.get("skill_id", "")),
        guard_runtime=active_guard,
        target_kind=target_kind,
        skill_root_relatives=skill_paths,
    )
    if (
        current_target_identity is None
        or current_identity_findings
        or current_target_identity.get("receipt_id")
        != target_identity.get("receipt_id")
        or current_target_identity.get("receipt_hash")
        != target_identity.get("receipt_hash")
    ):
        return False
    target_identity = current_target_identity
    production_rows = receipt.get("production_revalidation_bindings", [])
    if not isinstance(production_rows, list):
        return False
    production_refs = [
        str(row.get("binding_ref", ""))
        for row in production_rows
        if isinstance(row, Mapping)
    ]
    current_production_rows, production_findings, _verified_context = (
        _load_portfolio_production_revalidation_bindings(
            production_refs,
            target_identity=(
                target_identity
                if isinstance(target_identity, Mapping)
                else None
            ),
            target_repository_root=target_repository_root,
            evidence_root=evidence_root,
            verified_installation_context=(
                installation_context_holder[0]
                if installation_context_holder
                else None
            ),
        )
    )
    if (
        _verified_context is not None
        and installation_context_holder is not None
        and not installation_context_holder
    ):
        installation_context_holder.append(_verified_context)
    if production_findings or current_production_rows != production_rows:
        return False
    first_ref = next(
        (
            str(ref)
            for job in jobs
            for ref in job.get("evidence_refs", [])
        ),
        "",
    )
    first_record, first_record_findings = _load_evidence_record(
        first_ref, evidence_root=evidence_root
    )
    if first_record_findings or not isinstance(first_record, Mapping):
        return False
    preparation_binding = {
        "ref": first_record.get("preparation_receipt_ref"),
        "receipt_id": first_record.get("preparation_id"),
        "receipt_hash": first_record.get("preparation_receipt_hash"),
    }
    evidence_identity = {
        "registry_id": registry_id,
        "scope_manifest_id": scope_manifest_id,
        "scope_manifest_hash": scope_manifest_hash,
        "skill_id": str(entry.get("skill_id", "")),
        "target_kind": str(entry.get("target_kind", "")),
        "skill_paths": list(entry.get("skill_paths", [])),
        "guard_runtime": receipt.get("guard_runtime"),
        "source_fingerprint": receipt.get("source_fingerprint"),
        "contract_hash": receipt.get("contract_hash"),
        "preparation_receipt": preparation_binding,
    }
    if _representative_job_evidence_findings(
        jobs,
        evidence_identity,
        evidence_root=evidence_root,
    ):
        return False
    covered_capabilities = {
        capability for job in jobs for capability in job["covered_capability_ids"]
    }
    required_capabilities = _unique_string_list(entry.get("required_capability_ids", [])) or []
    if not required_capabilities or not set(required_capabilities).issubset(covered_capabilities):
        return False
    expected_members = {
        str(member.get("member_skill_id", "")): str(member.get("contract_hash", ""))
        for member in target_identity.get("member_identities", [])
        if isinstance(member, Mapping)
    }
    observed_members = {
        str(job.get("member_skill_id", "")): str(job.get("member_contract_hash", ""))
        for job in jobs
    }
    if observed_members != expected_members:
        return False
    declared_job_classes = _unique_string_list(
        entry.get("required_job_class_ids", list(DEFAULT_REQUIRED_JOB_CLASS_IDS))
    )
    required_job_classes = (
        sorted(set(DEFAULT_REQUIRED_JOB_CLASS_IDS) | set(declared_job_classes))
        if declared_job_classes is not None
        else None
    )
    covered_job_classes = {
        job_class for job in jobs for job_class in job.get("job_class_ids", [])
    }
    if (
        not required_job_classes
        or not set(required_job_classes).issubset(JOB_CLASS_IDS)
        or not set(required_job_classes).issubset(covered_job_classes)
    ):
        return False
    return _same_guard(receipt.get("guard_runtime"), active_guard)


def _reuse_ticket_is_current(
    entry: Mapping[str, Any],
    active_guard: Mapping[str, Any],
    guard_change_history: Sequence[Mapping[str, Any]] = (),
    *,
    evidence_root: Path | None,
    registry_id: str,
    scope_manifest_id: str,
    scope_manifest_hash: str,
    target_repository_root: Path | None = None,
    installation_context_holder: list[object] | None = None,
) -> bool:
    source = entry.get("canonical_source")
    ticket = entry.get("reuse_ticket")
    if not isinstance(ticket, Mapping) or not isinstance(source, Mapping):
        return False
    chain_value = entry.get("reuse_ticket_chain")
    if chain_value is None:
        chain: list[Mapping[str, Any]] = [ticket]
    elif not isinstance(chain_value, list) or not chain_value:
        return False
    else:
        chain = [row for row in chain_value if isinstance(row, Mapping)]
        if len(chain) != len(chain_value) or dict(chain[-1]) != dict(ticket):
            return False
    old_receipt = entry.get("full_run_receipt")
    if not _full_receipt_identity_complete(old_receipt):
        return False
    assert isinstance(old_receipt, Mapping)
    if not _full_receipt_is_current(
        entry,
        old_receipt.get("guard_runtime", {}),
        evidence_root=evidence_root,
        registry_id=registry_id,
        scope_manifest_id=scope_manifest_id,
        scope_manifest_hash=scope_manifest_hash,
        target_repository_root=target_repository_root,
        installation_context_holder=installation_context_holder,
    ):
        return False
    identity = _receipt_identity(old_receipt)
    proof_hash = str(old_receipt.get("receipt_hash", ""))
    proof_kind = "full_run_receipt"
    proof_guard: Mapping[str, Any] = old_receipt.get("guard_runtime", {})
    consumed = set(str(item) for item in entry.get("consumed_guard_feature_tags", []))
    seen_ticket_ids: set[str] = set()
    for chain_ticket in chain:
        ticket_id = str(chain_ticket.get("ticket_id", ""))
        if (
            chain_ticket.get("schema_version") != REUSE_TICKET_SCHEMA
            or chain_ticket.get("status") != "current"
            or chain_ticket.get("ticket_hash") != _ticket_hash(chain_ticket)
            or not ticket_id
            or ticket_id in seen_ticket_ids
            or chain_ticket.get("skill_id") != entry.get("skill_id")
            or chain_ticket.get("registry_id") != registry_id
            or chain_ticket.get("scope_manifest_id") != scope_manifest_id
            or chain_ticket.get("scope_manifest_hash") != scope_manifest_hash
            or chain_ticket.get("broad_semantic_change") is not False
            or chain_ticket.get("previous_proof_kind") != proof_kind
            or chain_ticket.get("previous_proof_hash") != proof_hash
            or not _same_guard(chain_ticket.get("from_guard"), proof_guard)
            or not _identity_ok(chain_ticket.get("identity"))
            or _receipt_identity(chain_ticket.get("identity", {})) != identity
            or not _timestamp_ok(chain_ticket.get("issued_at"))
        ):
            return False
        seen_ticket_ids.add(ticket_id)
        affected_tags = _unique_string_list(chain_ticket.get("affected_feature_tags"))
        if (
            affected_tags is None
            or consumed & set(affected_tags)
            or set(affected_tags) & NON_REUSABLE_GUARD_FEATURE_TAGS
        ):
            return False
        history_match = next(
            (
                change
                for change in guard_change_history
                if change.get("change_id") == chain_ticket.get("change_id")
                and _same_guard(change.get("guard_before"), chain_ticket.get("from_guard"))
                and _same_guard(change.get("guard_after"), chain_ticket.get("to_guard"))
                and change.get("broad_semantic_change") is False
                and sorted(change.get("affected_feature_tags", []))
                == sorted(affected_tags)
            ),
            None,
        )
        if history_match is None:
            return False
        proof_hash = str(chain_ticket.get("ticket_hash", ""))
        proof_kind = "reuse_ticket"
        proof_guard = chain_ticket.get("to_guard", {})
    if not _same_guard(proof_guard, active_guard):
        return False
    return (
        identity.get("source_fingerprint") == source.get("source_fingerprint")
        and identity.get("contract_hash") == entry.get("contract_hash")
    )


def entry_is_current(
    entry: Mapping[str, Any],
    active_guard: Mapping[str, Any],
    guard_change_history: Sequence[Mapping[str, Any]] = (),
    *,
    evidence_root: Path | None = None,
    registry_id: str = "",
    scope_manifest_id: str = "",
    scope_manifest_hash: str = "",
    target_repository_root: Path | None = None,
    installation_context_holder: list[object] | None = None,
) -> bool:
    return (
        entry.get("lifecycle") in ACTIVE_LIFECYCLES
        and entry.get("graduation_status") == "current"
        and entry.get("capability_inventory_status", "pending") == "current"
        and not entry.get("member_revalidation_statuses")
        and (
            _full_receipt_is_current(
                entry,
                active_guard,
                evidence_root=evidence_root,
                registry_id=registry_id,
                scope_manifest_id=scope_manifest_id,
                scope_manifest_hash=scope_manifest_hash,
                target_repository_root=target_repository_root,
                installation_context_holder=installation_context_holder,
            )
            or _reuse_ticket_is_current(
                entry,
                active_guard,
                guard_change_history,
                evidence_root=evidence_root,
                registry_id=registry_id,
                scope_manifest_id=scope_manifest_id,
                scope_manifest_hash=scope_manifest_hash,
                target_repository_root=target_repository_root,
                installation_context_holder=installation_context_holder,
            )
        )
    )


def entry_currentness_findings(
    entry: Mapping[str, Any],
    active_guard: Mapping[str, Any],
    guard_change_history: Sequence[Mapping[str, Any]] = (),
    *,
    evidence_root: Path | None = None,
    registry_id: str = "",
    scope_manifest_id: str = "",
    scope_manifest_hash: str = "",
    target_repository_root: Path | None = None,
    precomputed_current: bool | None = None,
    installation_context_holder: list[object] | None = None,
) -> list[str]:
    if precomputed_current is True or (
        precomputed_current is None
        and entry_is_current(
        entry,
        active_guard,
        guard_change_history,
        evidence_root=evidence_root,
        registry_id=registry_id,
        scope_manifest_id=scope_manifest_id,
        scope_manifest_hash=scope_manifest_hash,
        target_repository_root=target_repository_root,
        installation_context_holder=installation_context_holder,
    )):
        return []
    reasons: list[str] = []
    if entry.get("lifecycle") not in ACTIVE_LIFECYCLES:
        reasons.append("entry_not_active")
    if entry.get("graduation_status") != "current":
        reasons.append(f"graduation_status:{entry.get('graduation_status', 'missing')}")
    if entry.get("capability_inventory_status", "pending") != "current":
        reasons.append("capability_inventory_not_current")
    if entry.get("member_revalidation_statuses"):
        reasons.append("portfolio_suite_hides_affected_member")
    receipt = entry.get("full_run_receipt")
    if not _full_receipt_identity_complete(receipt):
        reasons.append("full_run_receipt_invalid")
    elif isinstance(receipt, Mapping):
        if target_repository_root is None:
            reasons.append("production_target_repository_root_missing")
        elif precomputed_current is False:
            reasons.append("production_revalidation_not_current")
        source = entry.get("canonical_source")
        if not isinstance(source, Mapping) or receipt.get("source_fingerprint") != source.get(
            "source_fingerprint"
        ):
            reasons.append("full_run_receipt_source_mismatch")
        if receipt.get("contract_hash") != entry.get("contract_hash"):
            reasons.append("full_run_receipt_contract_mismatch")
        jobs, job_findings = _normalized_representative_jobs(
            entry.get("representative_jobs"), require_job_classes=True
        )
        reasons.extend(value.split(":", 1)[0] for value in job_findings)
        if not job_findings:
            reasons.extend(
                row["code"]
                for row in _full_receipt_payload_findings(
                    receipt,
                    jobs,
                    skill_id=str(entry.get("skill_id", "")),
                    evidence_root=evidence_root,
                    production_revalidation_bindings=receipt.get(
                        "production_revalidation_bindings"
                    ),
                )
            )
            preparation_binding: dict[str, Any] | None = None
            first_ref = next(
                (
                    str(ref)
                    for job in jobs
                    for ref in job.get("evidence_refs", [])
                ),
                "",
            )
            if first_ref:
                first_record, first_record_findings = _load_evidence_record(
                    first_ref, evidence_root=evidence_root
                )
                if not first_record_findings and isinstance(first_record, Mapping):
                    preparation_binding = {
                        "ref": first_record.get("preparation_receipt_ref"),
                        "receipt_id": first_record.get("preparation_id"),
                        "receipt_hash": first_record.get("preparation_receipt_hash"),
                    }
            evidence_identity = {
                "registry_id": registry_id,
                "scope_manifest_id": scope_manifest_id,
                "scope_manifest_hash": scope_manifest_hash,
                "skill_id": str(entry.get("skill_id", "")),
                "guard_runtime": receipt.get("guard_runtime"),
                "source_fingerprint": receipt.get("source_fingerprint"),
                "contract_hash": receipt.get("contract_hash"),
                "preparation_receipt": preparation_binding,
            }
            reasons.extend(
                row["code"]
                for row in _representative_job_evidence_findings(
                    jobs, evidence_identity, evidence_root=evidence_root
                )
            )
        if not _same_guard(receipt.get("guard_runtime"), active_guard):
            reasons.append("full_run_receipt_guard_mismatch")
    if entry.get("reuse_ticket") is not None and not _reuse_ticket_is_current(
        entry,
        active_guard,
        guard_change_history,
        evidence_root=evidence_root,
        registry_id=registry_id,
        scope_manifest_id=scope_manifest_id,
        scope_manifest_hash=scope_manifest_hash,
        target_repository_root=target_repository_root,
        installation_context_holder=installation_context_holder,
    ):
        reasons.append("reuse_ticket_chain_invalid_or_stale")
    return sorted(set(reasons)) or ["current_proof_invalid_or_stale"]


def audit_portfolio(
    registry: object,
    *,
    actual_guard: Mapping[str, Any] | None = None,
    candidate_skill_id: str = "",
    evidence_root: Path | None = None,
    target_repository_roots: Mapping[str, Path] | None = None,
    mode: str = "all-current",
) -> dict[str, Any]:
    schema_findings = validate_registry(registry, evidence_root=evidence_root)
    if schema_findings or not isinstance(registry, Mapping):
        return {
            "artifact_type": "skillguard_portfolio_audit",
            "schema_version": "skillguard.portfolio_audit.v1",
            "status": "blocked",
            "schema_findings": schema_findings,
            "blockers": ["portfolio_registry_invalid"],
            "claim_boundary": "Registry validation failed before portfolio currentness could be evaluated.",
        }

    active_guard = registry["active_guard"]
    assert isinstance(active_guard, Mapping)
    blockers: list[dict[str, str]] = []
    if mode not in {"candidate-preflight", "candidate-graduation", "all-current"}:
        blockers.append(_finding("portfolio_audit_mode_invalid", detail=mode))
    if mode in {"candidate-preflight", "candidate-graduation"} and not candidate_skill_id:
        blockers.append(_finding("portfolio_audit_candidate_required"))
    if actual_guard is not None and not _same_guard(active_guard, actual_guard):
        expected = (
            f"{active_guard.get('runtime_id', '')}:"
            f"{active_guard.get('file_count', '')}:"
            f"{active_guard.get('source_hash', '')}"
        )
        actual = (
            f"{actual_guard.get('runtime_id', '')}:"
            f"{actual_guard.get('file_count', '')}:"
            f"{actual_guard.get('source_hash', '')}"
        )
        blockers.append(
            _finding(
                "active_guard_runtime_mismatch",
                detail=f"expected={expected}; actual={actual}",
            )
        )

    entries = [entry for entry in registry["entries"] if isinstance(entry, Mapping)]
    active_entries = [entry for entry in entries if entry.get("lifecycle") in ACTIVE_LIFECYCLES]
    guard_change_history = [
        row for row in registry.get("guard_change_history", []) if isinstance(row, Mapping)
    ]
    current_ids: list[str] = []
    pending_ids: list[str] = []
    pending_capability_inventory_ids: list[str] = []
    entry_findings: list[dict[str, Any]] = []
    current_by_skill_id: dict[str, bool] = {}
    installation_context_holder: list[object] = []
    repository_roots = dict(target_repository_roots or {})
    for entry in sorted(active_entries, key=lambda item: int(item.get("order", 10**9))):
        skill_id = str(entry.get("skill_id", ""))
        target_repository_root = repository_roots.get(skill_id)
        if entry.get("capability_inventory_status", "pending") != "current":
            pending_capability_inventory_ids.append(skill_id)
        is_current = entry_is_current(
            entry,
            active_guard,
            guard_change_history,
            evidence_root=evidence_root,
            registry_id=str(registry.get("registry_id", "")),
            scope_manifest_id=str(registry.get("scope_manifest_id", "")),
            scope_manifest_hash=str(registry.get("scope_manifest_hash", "")),
            target_repository_root=target_repository_root,
            installation_context_holder=installation_context_holder,
        )
        current_by_skill_id[skill_id] = is_current
        if is_current:
            current_ids.append(skill_id)
        else:
            pending_ids.append(skill_id)
            reasons = entry_currentness_findings(
                entry,
                active_guard,
                guard_change_history,
                evidence_root=evidence_root,
                registry_id=str(registry.get("registry_id", "")),
                scope_manifest_id=str(registry.get("scope_manifest_id", "")),
                scope_manifest_hash=str(registry.get("scope_manifest_hash", "")),
                target_repository_root=target_repository_root,
                precomputed_current=False,
                installation_context_holder=installation_context_holder,
            )
            entry_findings.append({"skill_id": skill_id, "current": False, "reasons": reasons})

    if candidate_skill_id:
        candidate = next((entry for entry in active_entries if entry.get("skill_id") == candidate_skill_id), None)
        if candidate is None:
            blockers.append(_finding("candidate_missing", skill_id=candidate_skill_id))
        else:
            if (
                mode == "candidate-graduation"
                and candidate.get("capability_inventory_status", "pending") != "current"
            ):
                blockers.append(
                    _finding("candidate_capability_inventory_incomplete", skill_id=candidate_skill_id)
                )
            candidate_order = int(candidate["order"])
            for prior in active_entries:
                if int(prior["order"]) < candidate_order and not current_by_skill_id.get(
                    str(prior.get("skill_id", "")), False
                ):
                    blockers.append(
                        _finding("prior_graduate_not_current", skill_id=str(prior.get("skill_id", "")))
                    )
            if mode == "candidate-graduation" and not current_by_skill_id.get(
                candidate_skill_id, False
            ):
                blockers.append(_finding("candidate_not_current", skill_id=candidate_skill_id))

    if blockers:
        status = "blocked"
    elif mode == "candidate-preflight":
        status = "current"
    elif mode == "candidate-graduation":
        status = "current"
    else:
        status = "current" if not pending_ids else "incomplete"
    return {
        "artifact_type": "skillguard_portfolio_audit",
        "schema_version": "skillguard.portfolio_audit.v1",
        "registry_id": registry["registry_id"],
        "mode": mode,
        "status": status,
        "active_guard": dict(active_guard),
        "active_entry_count": len(active_entries),
        "current_skill_ids": current_ids,
        "non_current_skill_ids": pending_ids,
        "capability_inventory_pending_skill_ids": pending_capability_inventory_ids,
        "entry_findings": entry_findings,
        "excluded_skill_ids": [
            str(entry.get("skill_id", "")) for entry in entries if entry.get("lifecycle") in EXCLUDED_LIFECYCLES
        ],
        "supporting_repository_ids": [
            str(entry.get("skill_id", "")) for entry in entries if entry.get("lifecycle") == SUPPORTING_LIFECYCLE
        ],
        "blockers": blockers,
        "claim_boundary": (
            "This audit checks registry structure, current Guard identity, child evidence identity, and prior-skill visibility. "
            "It does not execute target jobs, infer licenses, publish repositories, or prove future behavior."
        ),
    }


def validate_guard_change(
    change: object,
    *,
    content_impact_plan: object,
) -> list[dict[str, str]]:
    if not isinstance(change, Mapping):
        return [_finding("guard_change_not_object")]
    findings: list[dict[str, str]] = []
    if change.get("schema_version") != GUARD_CHANGE_SCHEMA:
        findings.append(_finding("guard_change_schema_unsupported"))
    if not change.get("change_id"):
        findings.append(_finding("guard_change_id_missing"))
    if not _guard_ok(change.get("guard_before")) or not _guard_ok(change.get("guard_after")):
        findings.append(_finding("guard_change_identity_invalid"))
    if _string_list(change.get("affected_feature_tags")) is None:
        findings.append(_finding("affected_feature_tags_invalid"))
    if any(
        field in change
        for field in (
            "broad_semantic_change",
            "required_target_ids",
            "required_member_ids_by_suite",
        )
    ):
        findings.append(_finding("caller_authored_impact_scope_forbidden"))
    if WIRE_HASH_RE.fullmatch(str(change.get("impact_graph_hash", ""))) is None:
        findings.append(_finding("guard_change_impact_graph_hash_invalid"))
    if not isinstance(change.get("reason"), str) or not change.get("reason"):
        findings.append(_finding("guard_change_reason_missing"))
    _required_targets, _required_members, _required_impact, scope_findings = (
        _derive_guard_change_scope(change, content_impact_plan)
    )
    findings.extend(_finding(code.split(":", 1)[0], detail=code) for code in scope_findings)
    return findings


def _guard_change_registry_scope_findings(
    registry: Mapping[str, Any],
    *,
    required_targets: Sequence[str],
    required_members: Mapping[str, Sequence[str]],
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    entries = {
        str(row.get("skill_id", "")): row
        for row in registry.get("entries", [])
        if isinstance(row, Mapping) and str(row.get("skill_id", ""))
    }
    def eligible(entry: Mapping[str, Any]) -> bool:
        return (
            entry.get("lifecycle") in ACTIVE_LIFECYCLES
            and str(entry.get("graduation_status", ""))
            in ACTIVE_GRADUATION_STATUSES
        )

    for target_id in required_targets:
        entry = entries.get(target_id)
        if entry is None:
            findings.append(
                _finding("guard_change_required_target_missing", skill_id=target_id)
            )
        elif not eligible(entry):
            findings.append(
                _finding("guard_change_required_target_not_impactable", skill_id=target_id)
            )
    for suite_id, member_ids in required_members.items():
        entry = entries.get(suite_id)
        if entry is None:
            findings.append(
                _finding("guard_change_required_member_suite_missing", skill_id=suite_id)
            )
            continue
        if entry.get("target_kind") != "skill_suite":
            findings.append(
                _finding("guard_change_required_member_owner_not_suite", skill_id=suite_id)
            )
            continue
        if not eligible(entry):
            findings.append(
                _finding("guard_change_required_member_suite_not_impactable", skill_id=suite_id)
            )
        inventory, inventory_findings = _normalized_member_capability_inventory(
            entry.get("member_capability_inventory")
        )
        if inventory_findings:
            findings.append(
                _finding(
                    "guard_change_required_member_inventory_invalid",
                    skill_id=suite_id,
                    detail=";".join(inventory_findings),
                )
            )
            continue
        known_member_ids = {str(row["member_skill_id"]) for row in inventory}
        for member_id in sorted(set(member_ids) - known_member_ids):
            findings.append(
                _finding(
                    "guard_change_required_member_missing",
                    skill_id=suite_id,
                    detail=member_id,
                )
            )
    return findings


def apply_guard_change(
    registry: object,
    change: object,
    *,
    content_impact_plan: object,
    evidence_root: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    findings = validate_registry(registry, evidence_root=evidence_root) + validate_guard_change(
        change, content_impact_plan=content_impact_plan
    )
    required_target_ids: list[str] = []
    required_member_ids_by_suite: dict[str, list[str]] = {}
    required_impact_ids: list[str] = []
    if isinstance(registry, Mapping) and isinstance(change, Mapping):
        (
            required_target_ids,
            required_member_ids_by_suite,
            required_impact_ids,
            _scope_findings,
        ) = _derive_guard_change_scope(change, content_impact_plan)
        findings.extend(
            _guard_change_registry_scope_findings(
                registry,
                required_targets=required_target_ids,
                required_members=required_member_ids_by_suite,
            )
        )
    if (
        not findings
        and isinstance(registry, Mapping)
        and isinstance(change, Mapping)
        and _matching_committed_transaction(
            registry, change, mutation_kind="guard_change"
        )
        is not None
    ):
        return (
            {
                "artifact_type": "skillguard_portfolio_impact_result",
                "schema_version": "skillguard.portfolio_impact_result.v1",
                "status": "already_committed",
                "change_id": str(change.get("change_id", "")),
                "transaction_id": str(change.get("transaction_id", "")),
                "claim_boundary": "Idempotent retry returned the already committed registry state without another mutation.",
            },
            copy.deepcopy(dict(registry)),
        )
    if isinstance(registry, Mapping) and isinstance(change, Mapping):
        findings.extend(_mutation_precondition_findings(registry, change))
    if findings or not isinstance(registry, Mapping) or not isinstance(change, Mapping):
        return (
            {
                "artifact_type": "skillguard_portfolio_impact_result",
                "status": "blocked",
                "blockers": findings,
                "claim_boundary": "No registry mutation occurred because the registry or Guard change was invalid.",
            },
            None,
        )
    if not _same_guard(registry.get("active_guard"), change.get("guard_before")):
        return (
            {
                "artifact_type": "skillguard_portfolio_impact_result",
                "status": "blocked",
                "blockers": [_finding("guard_before_not_active")],
                "claim_boundary": "No registry mutation occurred because the change did not start from the active Guard.",
            },
            None,
        )
    if _same_guard(change.get("guard_before"), change.get("guard_after")):
        return (
            {
                "artifact_type": "skillguard_portfolio_impact_result",
                "status": "blocked",
                "blockers": [_finding("guard_change_identity_unchanged")],
                "claim_boundary": "No registry mutation occurred because the Guard identity did not change.",
            },
            None,
        )
    history = [row for row in registry.get("guard_change_history", []) if isinstance(row, Mapping)]
    if any(row.get("change_id") == change.get("change_id") for row in history):
        return (
            {
                "artifact_type": "skillguard_portfolio_impact_result",
                "status": "blocked",
                "blockers": [_finding("guard_change_id_duplicate")],
                "claim_boundary": "No registry mutation occurred because the Guard change id was already registered.",
            },
            None,
        )

    updated = copy.deepcopy(dict(registry))
    updated["previous_registry_hash"] = str(registry.get("registry_hash", ""))
    updated["revision"] = int(registry.get("revision", 0)) + 1
    updated["active_guard"] = dict(change["guard_after"])
    updated["updated_at"] = utc_now()
    affected_tags = set(str(item) for item in change["affected_feature_tags"])
    invalidated: list[dict[str, Any]] = []
    invalidated_member_ids: list[str] = []
    member_revalidation_statuses: dict[str, dict[str, Any]] = {}
    status_transitions: list[dict[str, Any]] = []
    exact_target_ids = set(required_target_ids) | set(
        required_member_ids_by_suite
    )
    for entry in updated["entries"]:
        suite_id = str(entry.get("skill_id", ""))
        if suite_id not in exact_target_ids:
            continue
        graduation_status = str(entry.get("graduation_status", ""))
        if (
            entry.get("lifecycle") not in ACTIVE_LIFECYCLES
            or graduation_status not in ACTIVE_GRADUATION_STATUSES
        ):
            continue
        consumed = set(str(item) for item in entry.get("consumed_guard_feature_tags", []))
        intersection = sorted(consumed & affected_tags)
        prior_status = graduation_status
        entry["graduation_status"] = "revalidation_required"
        entry["reuse_ticket"] = None
        entry["revalidation_reason"] = "changed_component_edge"
        entry["pending_guard_change_id"] = str(change["change_id"])
        required_members = required_member_ids_by_suite.get(suite_id, [])
        if required_members:
            existing_member_statuses, _status_findings = (
                _normalized_member_revalidation_statuses(
                    entry.get("member_revalidation_statuses")
                )
            )
            for member_id in required_members:
                prior_member_status = existing_member_statuses.get(member_id, {})
                current_member_status = {
                    "graduation_status": "revalidation_required",
                    "pending_guard_change_id": str(change["change_id"]),
                    "reuse_ticket_absent": True,
                }
                existing_member_statuses[member_id] = current_member_status
                invalidated_member_ids.append(member_id)
                status_transitions.append(
                    {
                        "scope_kind": "suite_member",
                        "target_id": suite_id,
                        "member_id": member_id,
                        "before_status": str(
                            prior_member_status.get("graduation_status", "untracked")
                        ),
                        "after_status": "revalidation_required",
                    }
                )
            entry["member_revalidation_statuses"] = dict(
                sorted(existing_member_statuses.items())
            )
            member_revalidation_statuses[suite_id] = {
                member_id: copy.deepcopy(existing_member_statuses[member_id])
                for member_id in required_members
            }
        status_transitions.append(
            {
                "scope_kind": "portfolio_target",
                "target_id": suite_id,
                "member_id": "",
                "before_status": prior_status,
                "after_status": "revalidation_required",
            }
        )
        invalidated.append(
            {
                "skill_id": entry["skill_id"],
                "affected": True,
                "intersecting_feature_tags": intersection,
            }
        )
    previous_change_hash = (
        str(history[-1].get("change_hash", "")) if history else None
    )
    history_record: dict[str, Any] = {
        "change_id": change["change_id"],
        "guard_before": dict(change["guard_before"]),
        "guard_after": dict(change["guard_after"]),
        "affected_feature_tags": list(change["affected_feature_tags"]),
        "impact_graph_hash": str(change["impact_graph_hash"]),
        "changed_component_ids": list(change["changed_component_ids"]),
        "required_target_ids": required_target_ids,
        "required_member_ids_by_suite": required_member_ids_by_suite,
        "reason": str(change["reason"]),
        "recorded_at": updated["updated_at"],
        "previous_change_hash": previous_change_hash,
    }
    history_record["change_hash"] = _guard_change_record_hash(history_record)
    updated.setdefault("guard_change_history", []).append(history_record)
    _append_registry_transaction(
        updated,
        registry,
        change,
        mutation_kind="guard_change",
        committed_at=str(updated["updated_at"]),
    )
    _refresh_registry_hash(updated)
    return (
        {
            "artifact_type": "skillguard_portfolio_impact_result",
            "schema_version": "skillguard.portfolio_impact_result.v1",
            "status": "updated",
            "change_id": change["change_id"],
            "invalidated_entries": invalidated,
            "required_target_ids": required_target_ids,
            "required_member_ids_by_suite": required_member_ids_by_suite,
            "required_impact_ids": required_impact_ids,
            "invalidated_member_ids": sorted(set(invalidated_member_ids)),
            "member_revalidation_statuses": member_revalidation_statuses,
            "status_transitions": sorted(
                status_transitions,
                key=lambda row: (
                    str(row["scope_kind"]),
                    str(row["target_id"]),
                    str(row["member_id"]),
                ),
            ),
            "claim_boundary": (
                "This result invalidates only the compiler-derived exact target/member set. "
                "It does not revalidate those targets; unrelated targets remain current and "
                "need neither execution nor a reuse ticket."
            ),
        },
        updated,
    )


def issue_reuse_ticket(
    registry: object,
    request: object,
    *,
    content_impact_plan: object,
    evidence_root: Path | None = None,
    target_repository_root: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any] | None]:
    findings = validate_registry(registry, evidence_root=evidence_root)
    if not isinstance(request, Mapping):
        findings.append(_finding("reuse_request_not_object"))
    elif request.get("schema_version") != REUSE_REQUEST_SCHEMA:
        findings.append(_finding("reuse_request_schema_unsupported"))
    if (
        not findings
        and isinstance(registry, Mapping)
        and isinstance(request, Mapping)
        and _matching_committed_transaction(
            registry, request, mutation_kind="reuse_ticket"
        )
        is not None
    ):
        existing_entry = next(
            (
                row
                for row in registry.get("entries", [])
                if isinstance(row, Mapping)
                and row.get("skill_id") == request.get("skill_id")
            ),
            None,
        )
        existing_ticket = (
            existing_entry.get("reuse_ticket")
            if isinstance(existing_entry, Mapping)
            else None
        )
        if (
            isinstance(existing_ticket, Mapping)
            and existing_ticket.get("transaction_id") == request.get("transaction_id")
        ):
            return (
                {
                    "artifact_type": "skillguard_reuse_ticket_result",
                    "status": "already_committed",
                    "skill_id": str(request.get("skill_id", "")),
                    "ticket_id": str(existing_ticket.get("ticket_id", "")),
                    "ticket_hash": str(existing_ticket.get("ticket_hash", "")),
                    "transaction_id": str(request.get("transaction_id", "")),
                    "claim_boundary": "Idempotent retry returned the already committed reuse ticket without another mutation.",
                },
                copy.deepcopy(dict(registry)),
                copy.deepcopy(dict(existing_ticket)),
            )
    if isinstance(registry, Mapping) and isinstance(request, Mapping):
        findings.extend(_mutation_precondition_findings(registry, request))
    if findings or not isinstance(registry, Mapping) or not isinstance(request, Mapping):
        return ({"artifact_type": "skillguard_reuse_ticket_result", "status": "blocked", "blockers": findings}, None, None)

    skill_id = str(request.get("skill_id", ""))
    entries = [entry for entry in registry["entries"] if isinstance(entry, Mapping)]
    entry = next((item for item in entries if item.get("skill_id") == skill_id), None)
    change = request.get("guard_change")
    previous = request.get("previous_result")
    current = request.get("current_identity")
    blockers: list[dict[str, str]] = []
    if entry is None:
        blockers.append(_finding("reuse_skill_missing", skill_id=skill_id))
    if validate_guard_change(
        change, content_impact_plan=content_impact_plan
    ):
        blockers.append(_finding("reuse_guard_change_invalid", skill_id=skill_id))
    if not _identity_ok(previous) or not _identity_ok(current):
        blockers.append(_finding("reuse_identity_invalid", skill_id=skill_id))
    if blockers or entry is None or not isinstance(change, Mapping) or not isinstance(previous, Mapping) or not isinstance(current, Mapping):
        return ({"artifact_type": "skillguard_reuse_ticket_result", "status": "blocked", "blockers": blockers}, None, None)
    target_kind, skill_path, skill_paths, topology_findings = (
        _target_source_configuration(entry, skill_id=skill_id)
    )
    blockers.extend(topology_findings)
    target_identity: dict[str, Any] | None = None
    if target_repository_root is None:
        blockers.append(_finding("reuse_target_repository_required", skill_id=skill_id))
    else:
        target_identity, identity_findings = derive_target_identity(
            target_repository_root,
            skill_root_relative=skill_path,
            expected_skill_id=skill_id,
            guard_runtime=change.get("guard_after", {}),
            target_kind=target_kind,
            skill_root_relatives=skill_paths,
        )
        blockers.extend(identity_findings)
    if entry.get("lifecycle") not in ACTIVE_LIFECYCLES:
        blockers.append(_finding("reuse_skill_not_active", skill_id=skill_id))
    if entry.get("graduation_status") != "revalidation_required":
        blockers.append(_finding("reuse_target_not_revalidation_required", skill_id=skill_id))
    if entry.get("pending_guard_change_id") != change.get("change_id"):
        blockers.append(_finding("reuse_pending_change_mismatch", skill_id=skill_id))
    if entry.get("member_revalidation_statuses"):
        blockers.append(
            _finding(
                "reuse_forbidden_with_member_revalidation",
                skill_id=skill_id,
            )
        )
    required_targets, required_members, _required_impact, _scope_findings = (
        _derive_guard_change_scope(change, content_impact_plan)
        if isinstance(change, Mapping)
        else ([], {}, [], [])
    )
    if skill_id in set(required_targets) | set(required_members):
        blockers.append(
            _finding(
                "reuse_forbidden_for_changed_component_edge",
                skill_id=skill_id,
            )
        )
    affected_feature_tags = set(str(item) for item in change.get("affected_feature_tags", []))
    if affected_feature_tags & NON_REUSABLE_GUARD_FEATURE_TAGS:
        blockers.append(_finding("reuse_forbidden_for_core_semantic_change", skill_id=skill_id))
    consumed = set(str(item) for item in entry.get("consumed_guard_feature_tags", []))
    if consumed & set(str(item) for item in change.get("affected_feature_tags", [])):
        blockers.append(_finding("reuse_affected_feature_intersection", skill_id=skill_id))
    if not _same_guard(change.get("guard_after"), registry.get("active_guard")):
        blockers.append(_finding("reuse_guard_after_not_active", skill_id=skill_id))
    history = [row for row in registry.get("guard_change_history", []) if isinstance(row, Mapping)]
    history_match = next(
        (
            row
            for row in history
            if row.get("change_id") == change.get("change_id")
            and _same_guard(row.get("guard_before"), change.get("guard_before"))
            and _same_guard(row.get("guard_after"), change.get("guard_after"))
            and row.get("broad_semantic_change") == change.get("broad_semantic_change")
            and sorted(row.get("affected_feature_tags", []))
            == sorted(change.get("affected_feature_tags", []))
            and sorted(row.get("required_target_ids", []))
            == sorted(change.get("required_target_ids", []))
            and _normalized_required_member_ids_by_suite(
                row.get("required_member_ids_by_suite")
            )[0]
            == _normalized_required_member_ids_by_suite(
                change.get("required_member_ids_by_suite")
            )[0]
        ),
        None,
    )
    if history_match is None:
        blockers.append(_finding("reuse_guard_change_not_registered", skill_id=skill_id))
    old_receipt = entry.get("full_run_receipt")
    chain_value = entry.get("reuse_ticket_chain", [])
    if not isinstance(chain_value, list) or any(
        not isinstance(row, Mapping) for row in chain_value
    ):
        blockers.append(_finding("reuse_ticket_chain_invalid", skill_id=skill_id))
        chain: list[Mapping[str, Any]] = []
    else:
        chain = [row for row in chain_value if isinstance(row, Mapping)]
    if not _full_receipt_identity_complete(old_receipt):
        blockers.append(_finding("reuse_previous_receipt_incomplete", skill_id=skill_id))
    if not isinstance(old_receipt, Mapping) or _receipt_identity(old_receipt) != _receipt_identity(previous):
        blockers.append(_finding("reuse_previous_result_not_registered", skill_id=skill_id))
    if not isinstance(old_receipt, Mapping) or not old_receipt.get("completed_at"):
        blockers.append(_finding("reuse_previous_completion_missing", skill_id=skill_id))
    if isinstance(old_receipt, Mapping) and not _full_receipt_is_current(
        entry,
        old_receipt.get("guard_runtime", {}),
        evidence_root=evidence_root,
        registry_id=str(registry.get("registry_id", "")),
        scope_manifest_id=str(registry.get("scope_manifest_id", "")),
        scope_manifest_hash=str(registry.get("scope_manifest_hash", "")),
        target_repository_root=target_repository_root,
    ):
        blockers.append(_finding("reuse_previous_receipt_not_current", skill_id=skill_id))
    previous_proof_kind = "full_run_receipt"
    previous_proof_hash = (
        str(old_receipt.get("receipt_hash", "")) if isinstance(old_receipt, Mapping) else ""
    )
    previous_proof_guard = (
        old_receipt.get("guard_runtime", {}) if isinstance(old_receipt, Mapping) else {}
    )
    if chain:
        prior_entry = copy.deepcopy(dict(entry))
        prior_entry["reuse_ticket"] = copy.deepcopy(dict(chain[-1]))
        if not _reuse_ticket_is_current(
            prior_entry,
            change.get("guard_before", {}),
            history,
            evidence_root=evidence_root,
            registry_id=str(registry.get("registry_id", "")),
            scope_manifest_id=str(registry.get("scope_manifest_id", "")),
            scope_manifest_hash=str(registry.get("scope_manifest_hash", "")),
            target_repository_root=target_repository_root,
        ):
            blockers.append(_finding("reuse_previous_ticket_chain_not_current", skill_id=skill_id))
        previous_proof_kind = "reuse_ticket"
        previous_proof_hash = str(chain[-1].get("ticket_hash", ""))
        previous_proof_guard = chain[-1].get("to_guard", {})
    if _receipt_identity(previous) != _receipt_identity(current):
        blockers.append(_finding("reuse_identity_changed", skill_id=skill_id))
    if target_identity is not None and isinstance(old_receipt, Mapping):
        verifier_identity = _receipt_identity(old_receipt)
        verifier_identity["source_fingerprint"] = str(target_identity["source_fingerprint"])
        verifier_identity["contract_hash"] = str(target_identity["contract_hash"])
        if _receipt_identity(current) != verifier_identity:
            blockers.append(_finding("reuse_current_identity_not_verifier_derived", skill_id=skill_id))
    if not _same_guard(change.get("guard_before"), previous_proof_guard):
        blockers.append(_finding("reuse_guard_before_not_previous_proof", skill_id=skill_id))
    if blockers:
        return ({"artifact_type": "skillguard_reuse_ticket_result", "status": "blocked", "blockers": blockers}, None, None)

    assert isinstance(old_receipt, Mapping)
    ticket: dict[str, Any] = {
        "schema_version": REUSE_TICKET_SCHEMA,
        "ticket_id": f"reuse-{canonical_hash(request)[:20].lower()}",
        "transaction_id": str(request["transaction_id"]),
        "skill_id": skill_id,
        "status": "current",
        "change_id": change["change_id"],
        "from_guard": dict(change["guard_before"]),
        "to_guard": dict(change["guard_after"]),
        "affected_feature_tags": sorted(str(item) for item in change["affected_feature_tags"]),
        "broad_semantic_change": False,
        "identity": _receipt_identity(current),
        "registry_id": str(registry.get("registry_id", "")),
        "scope_manifest_id": str(registry.get("scope_manifest_id", "")),
        "scope_manifest_hash": str(registry.get("scope_manifest_hash", "")),
        "base_registry_revision": int(registry.get("revision", 0)),
        "base_registry_hash": str(registry.get("registry_hash", "")),
        "previous_full_receipt_hash": str(old_receipt.get("receipt_hash", "")),
        "previous_proof_kind": previous_proof_kind,
        "previous_proof_hash": previous_proof_hash,
        "target_identity_receipt_id": str(target_identity.get("receipt_id", "")) if target_identity else "",
        "target_identity_receipt_hash": str(target_identity.get("receipt_hash", "")) if target_identity else "",
        # Anchor issuance to the already committed Guard-change transaction so
        # retrying the same request against the same base registry is
        # byte-for-byte idempotent instead of minting a new proof each time.
        "issued_at": str(history_match.get("recorded_at", "")),
        "claim_boundary": "Reuse proves only unchanged registered identity and non-intersection with the named non-broad Guard change.",
    }
    ticket["ticket_hash"] = _ticket_hash(ticket)
    updated = copy.deepcopy(dict(registry))
    updated["previous_registry_hash"] = str(registry.get("registry_hash", ""))
    updated["revision"] = int(registry.get("revision", 0)) + 1
    updated_entry = next(item for item in updated["entries"] if item.get("skill_id") == skill_id)
    updated_entry.setdefault("reuse_ticket_chain", []).append(ticket)
    updated_entry["reuse_ticket"] = ticket
    updated_entry["graduation_status"] = "current"
    updated_entry["last_revalidation"] = ticket["issued_at"]
    updated_entry.pop("revalidation_reason", None)
    updated_entry.pop("pending_guard_change_id", None)
    updated["updated_at"] = ticket["issued_at"]
    _append_registry_transaction(
        updated,
        registry,
        request,
        mutation_kind="reuse_ticket",
        committed_at=str(ticket["issued_at"]),
        artifact_hashes=(str(ticket["ticket_hash"]),),
    )
    _refresh_registry_hash(updated)
    return (
        {
            "artifact_type": "skillguard_reuse_ticket_result",
            "status": "issued",
            "skill_id": skill_id,
            "ticket_id": ticket["ticket_id"],
            "ticket_hash": ticket["ticket_hash"],
            "claim_boundary": ticket["claim_boundary"],
        },
        updated,
        ticket,
    )


def _load_graduation_preparation(
    evidence: Mapping[str, Any],
    *,
    evidence_root: Path | None,
) -> tuple[Mapping[str, Any] | None, list[dict[str, str]]]:
    skill_id = str(evidence.get("skill_id", ""))
    findings: list[dict[str, str]] = []
    binding = evidence.get("preparation_receipt")
    if (
        not isinstance(binding, Mapping)
        or not isinstance(binding.get("ref"), str)
        or EVIDENCE_REF_RE.fullmatch(str(binding.get("ref", ""))) is None
        or not isinstance(binding.get("receipt_id"), str)
        or not binding.get("receipt_id")
        or not _hash_ok(binding.get("receipt_hash"))
    ):
        return None, [
            _finding("graduation_preparation_receipt_missing", skill_id=skill_id)
        ]
    preparation, _relative, load_findings = _load_hash_bound_json(
        str(binding["ref"]),
        evidence_root=evidence_root,
        finding_prefix="graduation_preparation_receipt",
    )
    findings.extend(load_findings)
    if preparation is None:
        return None, findings

    unsigned = dict(preparation)
    stored_hash = unsigned.pop("receipt_hash", None)
    prepared_specs = [
        {
            "order": row.get("order"),
            "job_id": row.get("job_id"),
            "job_spec_ref": row.get("job_spec_ref"),
            "job_spec_hash": row.get("job_spec_hash"),
        }
        for row in preparation.get("job_specs", [])
        if isinstance(row, Mapping)
    ]
    expected_specs = sorted(
        (
            {
                "job_id": str(job.get("job_id", "")),
                "job_spec_ref": str(job.get("job_spec_ref", "")),
                "job_spec_hash": str(job.get("job_spec_hash", "")),
            }
            for job in evidence.get("representative_jobs", [])
            if isinstance(job, Mapping)
        ),
        key=lambda row: row["job_id"],
    )
    actual_specs = sorted(
        (
            {
                "job_id": str(row.get("job_id", "")),
                "job_spec_ref": str(row.get("job_spec_ref", "")),
                "job_spec_hash": str(row.get("job_spec_hash", "")),
            }
            for row in prepared_specs
        ),
        key=lambda row: row["job_id"],
    )
    target_binding = preparation.get("target_identity_receipt")
    evidence_target_binding = evidence.get("target_identity_receipt")
    prepared_installed = preparation.get("installed_parity_receipt")
    evidence_installed = evidence.get("installed_parity_receipt")
    installed_binding_matches = (
        prepared_installed is None
        and evidence_installed is None
    ) or (
        isinstance(prepared_installed, Mapping)
        and isinstance(evidence_installed, Mapping)
        and prepared_installed.get("receipt_id")
        == evidence_installed.get("receipt_id")
        and prepared_installed.get("receipt_hash")
        == evidence_installed.get("receipt_hash")
    )
    expected_job_set_hash = canonical_hash(
        {
            "job_plan_ref": preparation.get("job_plan_ref"),
            "job_plan_hash": preparation.get("job_plan_hash"),
            "job_specs": preparation.get("job_specs"),
        }
    )
    if (
        preparation.get("schema_version") != PORTFOLIO_PREPARATION_SCHEMA
        or preparation.get("status") != "prepared"
        or preparation.get("receipt_id") != binding.get("receipt_id")
        or preparation.get("preparation_id") != binding.get("receipt_id")
        or stored_hash != binding.get("receipt_hash")
        or stored_hash != canonical_hash(unsigned)
        or preparation.get("registry_id") != evidence.get("registry_id")
        or preparation.get("registry_revision")
        != evidence.get("expected_registry_revision")
        or preparation.get("registry_hash") != evidence.get("base_registry_hash")
        or preparation.get("scope_manifest_id")
        != evidence.get("scope_manifest_id")
        or preparation.get("scope_manifest_hash")
        != evidence.get("scope_manifest_hash")
        or preparation.get("skill_id") != skill_id
        or preparation.get("target_kind") != evidence.get("target_kind")
        or sorted(preparation.get("skill_paths", []))
        != sorted(evidence.get("skill_paths", []))
        or not _same_guard(
            preparation.get("guard_runtime"), evidence.get("guard_runtime")
        )
        or not isinstance(target_binding, Mapping)
        or not isinstance(evidence_target_binding, Mapping)
        or dict(target_binding) != dict(evidence_target_binding)
        or preparation.get("job_plan_ref")
        != (evidence.get("job_plan_refs") or [""])[0]
        or preparation.get("job_plan_hash") != evidence.get("job_plan_hash")
        or actual_specs != expected_specs
        or preparation.get("job_set_hash") != expected_job_set_hash
        or preparation.get("prepared_sequence") != 1
        or not _timestamp_not_after(
            preparation.get("prepared_at"), evidence.get("submitted_at")
        )
        or not installed_binding_matches
    ):
        findings.append(
            _finding(
                "graduation_preparation_receipt_binding_invalid",
                skill_id=skill_id,
            )
        )
    return preparation, findings


def _installed_parity_freshness_findings(
    evidence: Mapping[str, Any],
    preparation: Mapping[str, Any] | None,
    *,
    evidence_root: Path | None,
    target_repository_root: Path | None,
    installed_target_root: Path | None,
    target_identity: Mapping[str, Any] | None,
) -> list[dict[str, str]]:
    skill_id = str(evidence.get("skill_id", ""))
    target_kind = str(evidence.get("target_kind", ""))
    binding = evidence.get("installed_parity_receipt")
    if binding is None:
        if target_kind == "skill_suite":
            return [
                _finding(
                    "graduation_installed_parity_required",
                    skill_id=skill_id,
                )
            ]
        return []
    if (
        not isinstance(binding, Mapping)
        or not isinstance(binding.get("ref"), str)
        or EVIDENCE_REF_RE.fullmatch(str(binding.get("ref", ""))) is None
        or not isinstance(binding.get("receipt_id"), str)
        or not binding.get("receipt_id")
        or not _hash_ok(binding.get("receipt_hash"))
    ):
        return [
            _finding("graduation_installed_parity_binding_invalid", skill_id=skill_id)
        ]
    receipt, _relative, load_findings = _load_hash_bound_json(
        str(binding["ref"]),
        evidence_root=evidence_root,
        finding_prefix="graduation_installed_parity_receipt",
    )
    findings = list(load_findings)
    guard_runtime = evidence.get("guard_runtime")
    portfolio_projection_hash = (
        str(guard_runtime.get("portfolio_projection_hash", ""))
        if isinstance(guard_runtime, Mapping)
        else ""
    )
    if receipt is not None:
        receipt_findings = validate_installed_parity_receipt(
            receipt,
            portfolio_projection_hash=portfolio_projection_hash,
        )
        target = receipt.get("target") if isinstance(receipt, Mapping) else None
        if (
            receipt_findings
            or receipt.get("status") != "current"
            or receipt.get("receipt_id") != binding.get("receipt_id")
            or receipt.get("receipt_hash") != binding.get("receipt_hash")
            or not isinstance(target, Mapping)
            or target.get("skill_id") != skill_id
            or target.get("target_kind") != target_kind
            or not isinstance(target_identity, Mapping)
            or target.get("members")
            != [
                {
                    "member_skill_id": str(row.get("member_skill_id", "")),
                    "skill_path": str(row.get("skill_path", "")),
                }
                for row in target_identity.get("member_identities", [])
                if isinstance(row, Mapping)
            ]
        ):
            findings.append(
                _finding(
                    "graduation_installed_parity_binding_invalid",
                    skill_id=skill_id,
                    detail=",".join(receipt_findings),
                )
            )
    if (
        target_repository_root is None
        or installed_target_root is None
        or not isinstance(target_identity, Mapping)
    ):
        findings.append(
            _finding(
                "graduation_installed_parity_freshness_root_required",
                skill_id=skill_id,
            )
        )
        return findings
    assert receipt is not None
    fresh_findings = replay_installed_content_parity_currentness(
        receipt,
        canonical_repository_root=target_repository_root,
        target_identity=target_identity,
        installed_target_root=installed_target_root,
        portfolio_projection_hash=portfolio_projection_hash,
    )
    if (
        fresh_findings
        or receipt.get("status") != "current"
        or receipt.get("receipt_id") != binding.get("receipt_id")
        or receipt.get("receipt_hash") != binding.get("receipt_hash")
    ):
        findings.append(
            _finding(
                "graduation_installed_parity_not_current",
                skill_id=skill_id,
                detail=",".join(
                    [
                        *(str(value) for value in receipt.get("blockers", [])),
                        *(str(value) for value in fresh_findings),
                    ]
                ),
            )
        )
    return findings


def _graduation_evidence_findings(
    evidence: object,
    *,
    evidence_root: Path | None,
    target_repository_root: Path | None,
    verified_installation_context: object | None = None,
) -> tuple[list[dict[str, str]], object | None]:
    if not isinstance(evidence, Mapping):
        return [_finding("graduation_evidence_not_object")], None
    skill_id = str(evidence.get("skill_id", ""))
    findings: list[dict[str, str]] = []
    if evidence.get("schema_version") != GRADUATION_EVIDENCE_SCHEMA:
        findings.append(_finding("graduation_evidence_schema_unsupported", skill_id=skill_id))
    if not isinstance(evidence.get("registry_id"), str) or not evidence.get("registry_id"):
        findings.append(_finding("graduation_registry_id_missing", skill_id=skill_id))
    if (
        not isinstance(evidence.get("scope_manifest_id"), str)
        or not evidence.get("scope_manifest_id")
        or not _hash_ok(evidence.get("scope_manifest_hash"))
    ):
        findings.append(_finding("graduation_scope_identity_missing", skill_id=skill_id))
    if not skill_id:
        findings.append(_finding("graduation_skill_id_missing"))
    target_kind = str(evidence.get("target_kind", ""))
    skill_paths = _unique_string_list(evidence.get("skill_paths"))
    if (
        target_kind not in TARGET_KINDS
        or not skill_paths
        or (target_kind == "single_skill" and len(skill_paths) != 1)
        or (target_kind == "skill_suite" and len(skill_paths) < 2)
    ):
        findings.append(_finding("graduation_target_topology_invalid", skill_id=skill_id))
    if not _guard_ok(evidence.get("guard_runtime")):
        findings.append(_finding("graduation_guard_invalid", skill_id=skill_id))
    if not _hash_ok(evidence.get("contract_hash")) or not _hash_ok(evidence.get("source_fingerprint")):
        findings.append(_finding("graduation_source_or_contract_invalid", skill_id=skill_id))
    _preparation, preparation_findings = _load_graduation_preparation(
        evidence, evidence_root=evidence_root
    )
    findings.extend(preparation_findings)
    target_identity_binding = evidence.get("target_identity_receipt")
    target_identity_ref = (
        str(target_identity_binding.get("ref", ""))
        if isinstance(target_identity_binding, Mapping)
        else ""
    )
    target_identity, _target_identity_relative, target_identity_findings = _load_hash_bound_json(
        target_identity_ref,
        evidence_root=evidence_root,
        finding_prefix="graduation_target_identity_receipt",
    )
    findings.extend(target_identity_findings)
    if target_identity is not None:
        target_identity_shape_findings = _target_identity_findings(target_identity)
        findings.extend(target_identity_shape_findings)
        if (
            not isinstance(target_identity_binding, Mapping)
            or target_identity_shape_findings
            or target_identity.get("receipt_id")
            != target_identity_binding.get("receipt_id")
            or target_identity.get("receipt_hash")
            != target_identity_binding.get("receipt_hash")
            or target_identity.get("skill_id") != skill_id
            or target_identity.get("target_kind") != target_kind
            or sorted(target_identity.get("skill_paths", []))
            != sorted(skill_paths or [])
            or target_identity.get("source_fingerprint")
            != evidence.get("source_fingerprint")
            or target_identity.get("contract_hash") != evidence.get("contract_hash")
            or not _same_guard(
                target_identity.get("guard_runtime"), evidence.get("guard_runtime")
            )
        ):
            findings.append(_finding("graduation_target_identity_binding_invalid", skill_id=skill_id))
    production_bindings, production_findings, _verified_context = (
        _load_portfolio_production_revalidation_bindings(
            evidence.get("production_revalidation_binding_refs"),
            target_identity=(
                target_identity if isinstance(target_identity, Mapping) else None
            ),
            target_repository_root=target_repository_root,
            evidence_root=evidence_root,
            verified_installation_context=verified_installation_context,
        )
    )
    findings.extend(production_findings)
    expected_production_fingerprint = (
        portfolio_production_revalidation_fingerprint(production_bindings)
    )
    if (
        evidence.get("production_revalidation_fingerprint")
        != expected_production_fingerprint
    ):
        findings.append(
            _finding(
                "graduation_production_revalidation_fingerprint_mismatch",
                skill_id=skill_id,
            )
        )
    jobs, job_findings = _normalized_representative_jobs(
        evidence.get("representative_jobs"), require_job_classes=True
    )
    for finding in job_findings:
        findings.append(
            _finding(finding.split(":", 1)[0], skill_id=skill_id, detail=finding)
        )

    global_plan: Mapping[str, Any] | None = None
    global_plan_ref = ""
    global_plan_hash = ""
    job_plan_refs = _unique_string_list(evidence.get("job_plan_refs"))
    if (
        not job_plan_refs
        or len(job_plan_refs) != 1
        or any(EVIDENCE_REF_RE.fullmatch(ref) is None for ref in job_plan_refs)
        or not _hash_ok(evidence.get("job_plan_hash"))
    ):
        findings.append(
            _finding(
                "graduation_global_job_plan_cardinality_invalid",
                skill_id=skill_id,
                detail=f"count={len(job_plan_refs or [])}",
            )
        )
    else:
        global_plan_ref = job_plan_refs[0]
        plan, _relative, plan_findings = _load_hash_bound_json(
            global_plan_ref,
            evidence_root=evidence_root,
            finding_prefix="graduation_job_plan",
        )
        findings.extend(plan_findings)
        if plan is not None:
            global_plan = plan
            global_plan_hash = str(plan.get("job_plan_hash", ""))
            plan_shape_findings = _job_plan_findings(
                plan,
                representative_jobs=jobs,
            )
            findings.extend(plan_shape_findings)
            if (
                plan_shape_findings
                or evidence.get("job_plan_hash") != global_plan_hash
                or plan.get("registry_id") != evidence.get("registry_id")
                or plan.get("scope_manifest_id")
                != evidence.get("scope_manifest_id")
                or plan.get("scope_manifest_hash")
                != evidence.get("scope_manifest_hash")
                or plan.get("skill_id") != skill_id
                or plan.get("target_kind") != target_kind
                or sorted(plan.get("skill_paths", []))
                != sorted(skill_paths or [])
            ):
                findings.append(
                    _finding(
                        "graduation_global_job_plan_binding_invalid",
                        skill_id=skill_id,
                    )
                )
        else:
            findings.append(
                _finding(
                    "graduation_global_job_plan_binding_invalid",
                    skill_id=skill_id,
                )
            )

    job_specs: dict[str, Mapping[str, Any]] = {}
    job_spec_refs = _unique_string_list(evidence.get("job_spec_refs"))
    if (
        not job_spec_refs
        or any(EVIDENCE_REF_RE.fullmatch(ref) is None for ref in job_spec_refs)
        or not _hash_ok(evidence.get("job_spec_hash"))
    ):
        findings.append(_finding("graduation_job_spec_binding_invalid", skill_id=skill_id))
    else:
        normalized_specs = sorted(
            {
                (str(job.get("job_spec_ref", "")), str(job.get("job_spec_hash", "")))
                for job in jobs
            }
        )
        expected_job_spec_hash = canonical_hash(
            {
                "job_specs": [
                    {"ref": ref, "hash": spec_hash}
                    for ref, spec_hash in normalized_specs
                ]
            }
        )
        expected_job_by_spec_ref: dict[str, Mapping[str, Any]] = {}
        duplicate_spec_ref = False
        for job in jobs:
            spec_ref = str(job.get("job_spec_ref", ""))
            if spec_ref in expected_job_by_spec_ref:
                duplicate_spec_ref = True
            expected_job_by_spec_ref[spec_ref] = job
        if (
            duplicate_spec_ref
            or
            sorted(job_spec_refs) != sorted(ref for ref, _hash in normalized_specs)
            or evidence.get("job_spec_hash") != expected_job_spec_hash
        ):
            findings.append(_finding("graduation_job_spec_binding_invalid", skill_id=skill_id))
        for spec_ref, spec_hash in normalized_specs:
            spec, _relative, spec_findings = _load_hash_bound_json(
                spec_ref,
                evidence_root=evidence_root,
                finding_prefix="graduation_job_spec",
            )
            findings.extend(spec_findings)
            if spec is None:
                continue
            job_specs[spec_ref] = spec
            expected_job = expected_job_by_spec_ref.get(spec_ref, {})
            expected_classes = _unique_string_list(
                expected_job.get("job_class_ids")
            )
            if (
                spec.get("schema_version") != PORTFOLIO_JOB_SPEC_SCHEMA
                or not _internal_hash_matches(spec, "job_spec_hash")
                or spec.get("job_spec_hash") != spec_hash
                or spec.get("registry_id") != evidence.get("registry_id")
                or spec.get("scope_manifest_id")
                != evidence.get("scope_manifest_id")
                or spec.get("scope_manifest_hash")
                != evidence.get("scope_manifest_hash")
                or spec.get("skill_id") != skill_id
                or spec.get("target_kind") != target_kind
                or sorted(spec.get("skill_paths", []))
                != sorted(skill_paths or [])
                or spec.get("job_id") != expected_job.get("job_id")
                or spec.get("job_class_id")
                != (expected_classes[0] if expected_classes else "")
                or spec.get("member_skill_id")
                != expected_job.get("member_skill_id")
                or spec.get("member_contract_hash")
                != expected_job.get("member_contract_hash")
                or sorted(spec.get("covered_capability_ids", []))
                != sorted(expected_job.get("covered_capability_ids", []))
            ):
                findings.append(
                    _finding(
                        "graduation_job_spec_binding_invalid",
                        skill_id=skill_id,
                        detail=spec_ref,
                    )
                )
    if global_plan is not None and global_plan_hash:
        findings.extend(
            _global_plan_claim_findings(
                jobs,
                global_plan_ref=global_plan_ref,
                global_plan_hash=global_plan_hash,
                global_plan=global_plan,
                job_specs=job_specs,
                evidence_root=evidence_root,
                skill_id=skill_id,
            )
        )
    unresolved = _unique_string_list(evidence.get("unresolved_failure_ids"))
    if unresolved is None or unresolved:
        findings.append(_finding("graduation_unresolved_failures_present", skill_id=skill_id))
    if not _timestamp_ok(evidence.get("submitted_at")):
        findings.append(_finding("graduation_submitted_at_invalid", skill_id=skill_id))
    if not isinstance(evidence.get("claim_boundary"), str) or not evidence.get("claim_boundary"):
        findings.append(_finding("graduation_claim_boundary_missing", skill_id=skill_id))
    if not _internal_hash_matches(evidence, "evidence_hash"):
        findings.append(_finding("graduation_evidence_hash_mismatch", skill_id=skill_id))
    if target_identity is not None and not _target_identity_findings(target_identity):
        expected_members = {
            str(member.get("member_skill_id", "")): str(member.get("contract_hash", ""))
            for member in target_identity.get("member_identities", [])
            if isinstance(member, Mapping)
        }
        observed_members = {
            str(job.get("member_skill_id", "")): str(job.get("member_contract_hash", ""))
            for job in jobs
        }
        if observed_members != expected_members:
            findings.append(
                _finding(
                    "graduation_suite_member_coverage_incomplete",
                    skill_id=skill_id,
                    detail=(
                        f"missing={','.join(sorted(set(expected_members) - set(observed_members)))};"
                        f"extra={','.join(sorted(set(observed_members) - set(expected_members)))}"
                    ),
                )
            )
    receipt = evidence.get("full_run_receipt")
    if not _full_receipt_identity_complete(receipt):
        findings.append(_finding("full_run_receipt_invalid", skill_id=skill_id))
    elif receipt.get("coverage_fingerprint") != representative_jobs_coverage_fingerprint(
        evidence.get("representative_jobs")
    ):
        findings.append(_finding("representative_jobs_not_bound_to_receipt", skill_id=skill_id))
    elif isinstance(receipt, Mapping):
        findings.extend(
            _full_receipt_payload_findings(
                receipt,
                jobs,
                skill_id=skill_id,
                evidence_root=evidence_root,
                production_revalidation_bindings=production_bindings,
            )
        )
    if jobs:
        findings.extend(
            _representative_job_evidence_findings(
                jobs,
                evidence,
                evidence_root=evidence_root,
            )
        )
    failure = evidence.get("failure_classification")
    if failure is not None and failure not in FAILURE_CLASSIFICATIONS:
        findings.append(_finding("graduation_failure_classification_invalid", skill_id=skill_id))
    return findings, _verified_context


def derive_target_identity(
    repository_root: Path,
    *,
    skill_root_relative: str,
    expected_skill_id: str,
    guard_runtime: Mapping[str, Any],
    target_kind: str = "single_skill",
    skill_root_relatives: Sequence[str] | None = None,
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    findings: list[dict[str, str]] = []
    repository_root = repository_root.resolve()
    if not repository_root.is_dir():
        return None, [_finding("target_repository_missing", skill_id=expected_skill_id)]
    source_config: dict[str, Any] = {
        "target_kind": target_kind,
        "skill_path": skill_root_relative,
        "skill_paths": list(skill_root_relatives or [skill_root_relative]),
    }
    normalized_kind, primary_path, normalized_paths, source_findings = (
        _target_source_configuration(source_config, skill_id=expected_skill_id)
    )
    if source_findings:
        return None, source_findings
    member_identities: list[dict[str, Any]] = []
    projection_snapshots: dict[str, str] = {}
    for skill_path in normalized_paths:
        relative = Path(skill_path)
        skill_root = (repository_root / relative).resolve()
        try:
            skill_root.relative_to(repository_root)
        except ValueError:
            findings.append(
                _finding(
                    "target_skill_path_escape",
                    skill_id=expected_skill_id,
                    detail=skill_path,
                )
            )
            continue
        if not skill_root.is_dir():
            findings.append(
                _finding(
                    "target_skill_root_missing",
                    skill_id=expected_skill_id,
                    detail=skill_path,
                )
            )
            continue
        compile_result = compile_skill_contract(
            skill_root,
            repository_root=repository_root,
            write=False,
        )
        if (
            not compile_result.ok
            or not compile_result.compiled_contract
            or not compile_result.check_manifest
        ):
            details = ",".join(sorted({row.code for row in compile_result.findings}))
            findings.append(
                _finding(
                    "target_contract_compile_parity_failed",
                    skill_id=expected_skill_id,
                    detail=f"{skill_path}:{details}",
                )
            )
            continue
        contract = compile_result.compiled_contract
        manifest = compile_result.check_manifest
        try:
            portfolio_projection = current_content_projection(
                manifest["content_impact_plan"],
                "projection:portfolio",
            )
        except (KeyError, TypeError, ValueError) as exc:
            findings.append(
                _finding(
                    "target_portfolio_projection_invalid",
                    skill_id=expected_skill_id,
                    detail=f"{skill_path}:{type(exc).__name__}",
                )
            )
            continue
        member_skill_id = str(contract.get("skill_id", ""))
        if not member_skill_id or manifest.get("skill_id") != member_skill_id:
            findings.append(
                _finding(
                    "target_member_compiled_skill_id_mismatch",
                    skill_id=expected_skill_id,
                    detail=skill_path,
                )
            )
        if manifest.get("contract_hash") != contract.get("contract_hash"):
            findings.append(
                _finding(
                    "target_manifest_contract_mismatch",
                    skill_id=expected_skill_id,
                    detail=skill_path,
                )
            )
        member_identities.append(
            {
                "member_skill_id": member_skill_id,
                "skill_path": relative.as_posix(),
                "source_fingerprint": canonical_hash(
                    {
                        "skill_root_token": relative.as_posix(),
                        "portfolio_projection_hash": portfolio_projection[
                            "consumer_projection_hash"
                        ],
                    }
                ),
                "portfolio_projection_hash": portfolio_projection[
                    "consumer_projection_hash"
                ],
                "contract_hash": str(contract.get("contract_hash", "")),
                "manifest_hash": str(manifest.get("manifest_hash", "")),
            }
        )
        projection_snapshots[relative.as_posix()] = str(
            portfolio_projection["consumer_projection_hash"]
        )
    for skill_path, expected_projection_hash in sorted(projection_snapshots.items()):
        skill_root = (repository_root / Path(skill_path)).resolve()
        replay = compile_skill_contract(
            skill_root,
            repository_root=repository_root,
            write=False,
        )
        try:
            current_projection_hash = current_content_projection(
                replay.check_manifest["content_impact_plan"],
                "projection:portfolio",
            )["consumer_projection_hash"]
        except (KeyError, TypeError, ValueError):
            current_projection_hash = ""
        if current_projection_hash != expected_projection_hash:
            findings.append(
                _finding(
                    "target_source_changed_during_identity_scan",
                    skill_id=expected_skill_id,
                    detail=skill_path,
                )
            )
    member_identities.sort(
        key=lambda row: (str(row["skill_path"]), str(row["member_skill_id"]))
    )
    member_ids = [str(row["member_skill_id"]) for row in member_identities]
    if len(member_ids) != len(set(member_ids)):
        findings.append(_finding("target_member_skill_id_duplicate", skill_id=expected_skill_id))
    if normalized_kind == "single_skill" and len(member_identities) != 1:
        findings.append(_finding("target_compiled_skill_id_mismatch", skill_id=expected_skill_id))
    if not _guard_ok(guard_runtime):
        findings.append(_finding("target_guard_runtime_invalid", skill_id=expected_skill_id))
    if findings:
        return None, findings
    primary_member = next(
        row for row in member_identities if row["skill_path"] == Path(primary_path).as_posix()
    )
    version = ""
    version_file = repository_root / "VERSION"
    if version_file.is_file():
        try:
            version = version_file.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError):
            version = ""
    source_fingerprint = canonical_hash(
        {
            "projection_policy": "skillguard.portfolio_projection.current",
            "target_kind": normalized_kind,
            "member_portfolio_projections": [
                {
                    "member_skill_id": row["member_skill_id"],
                    "skill_path": row["skill_path"],
                    "portfolio_projection_hash": row[
                        "portfolio_projection_hash"
                    ],
                }
                for row in member_identities
            ],
        }
    )
    if normalized_kind == "single_skill":
        target_contract_hash = str(member_identities[0]["contract_hash"])
        target_manifest_hash = str(member_identities[0]["manifest_hash"])
    else:
        target_contract_hash = _aggregate_member_contract_hash(
            expected_skill_id, member_identities
        )
        target_manifest_hash = _aggregate_member_manifest_hash(
            expected_skill_id, member_identities
        )
    identity: dict[str, Any] = {
        "schema_version": TARGET_IDENTITY_SCAN_SCHEMA,
        "skill_id": expected_skill_id,
        "target_kind": normalized_kind,
        "skill_root_token": Path(primary_path).as_posix(),
        "skill_paths": sorted(
            str(row["skill_path"]) for row in member_identities
        ),
        "member_identities": member_identities,
        "source_fingerprint": source_fingerprint,
        "contract_hash": target_contract_hash,
        "manifest_hash": target_manifest_hash,
        "guard_runtime": dict(guard_runtime),
        "version": version,
        "issued_by": "skillguard-v2-target-identity-verifier",
        "claim_boundary": (
            "This receipt proves current local compiler parity and the exact Portfolio component projections, complete declared member set, "
            "member contracts/manifests, aggregate target identity, and Guard identity scanned for the named target. "
            "It does not prove representative job outcomes, undeclared members, or publication."
        ),
    }
    identity["receipt_id"] = f"target-identity-{canonical_hash(identity)[:24].lower()}"
    identity["receipt_hash"] = canonical_hash(identity)
    identity_findings = _target_identity_findings(identity)
    return (None, identity_findings) if identity_findings else (identity, [])


def graduate_portfolio_target(
    registry: object,
    evidence: object,
    *,
    actual_guard: Mapping[str, Any] | None = None,
    evidence_root: Path | None = None,
    target_repository_root: Path | None = None,
    installed_target_root: Path | None = None,
    verified_installation_context: object | None = None,
    portfolio_target_repository_roots: Mapping[str, Path] | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any] | None]:
    findings = validate_registry(registry, evidence_root=evidence_root)
    if (
        not findings
        and isinstance(registry, Mapping)
        and isinstance(evidence, Mapping)
        and _matching_committed_transaction(
            registry, evidence, mutation_kind="graduation"
        )
        is not None
    ):
        existing_entry = next(
            (
                row
                for row in registry.get("entries", [])
                if isinstance(row, Mapping)
                and row.get("skill_id") == evidence.get("skill_id")
            ),
            None,
        )
        existing_receipt = (
            existing_entry.get("portfolio_graduation_receipt")
            if isinstance(existing_entry, Mapping)
            else None
        )
        if (
            isinstance(existing_receipt, Mapping)
            and existing_receipt.get("transaction_id")
            == evidence.get("transaction_id")
        ):
            return (
                {
                    "artifact_type": "skillguard_portfolio_graduation_result",
                    "status": "already_committed",
                    "skill_id": str(evidence.get("skill_id", "")),
                    "receipt_id": str(existing_receipt.get("receipt_id", "")),
                    "receipt_hash": str(existing_receipt.get("receipt_hash", "")),
                    "transaction_id": str(evidence.get("transaction_id", "")),
                    "claim_boundary": "Idempotent retry returned the already committed graduation receipt without another mutation.",
                },
                copy.deepcopy(dict(registry)),
                copy.deepcopy(dict(existing_receipt)),
            )
    if isinstance(registry, Mapping) and isinstance(evidence, Mapping):
        findings.extend(_mutation_precondition_findings(registry, evidence))
    if findings or not isinstance(registry, Mapping) or not isinstance(evidence, Mapping):
        return ({"artifact_type": "skillguard_portfolio_graduation_result", "status": "blocked", "blockers": findings}, None, None)
    skill_id = str(evidence.get("skill_id", ""))
    entries = [entry for entry in registry["entries"] if isinstance(entry, Mapping)]
    entry = next((item for item in entries if item.get("skill_id") == skill_id), None)
    blockers: list[dict[str, str]] = []
    active_guard = registry["active_guard"]
    assert isinstance(active_guard, Mapping)
    currentness_repository_roots = dict(
        portfolio_target_repository_roots or {}
    )
    if target_repository_root is not None:
        currentness_repository_roots.setdefault(
            skill_id, target_repository_root
        )
    target_kind, skill_path, skill_paths, topology_findings = (
        _target_source_configuration(entry, skill_id=skill_id)
    )
    blockers.extend(topology_findings)
    identity: dict[str, Any] | None = None
    if target_repository_root is None:
        blockers.append(_finding("graduation_target_repository_required", skill_id=skill_id))
    else:
        identity, identity_findings = derive_target_identity(
            target_repository_root,
            skill_root_relative=skill_path,
            expected_skill_id=skill_id,
            guard_runtime=actual_guard or active_guard,
            target_kind=target_kind,
            skill_root_relatives=skill_paths,
        )
        blockers.extend(identity_findings)
    if identity is not None:
        if evidence.get("source_fingerprint") != identity.get("source_fingerprint"):
            blockers.append(_finding("graduation_source_not_verifier_derived", skill_id=skill_id))
        if evidence.get("contract_hash") != identity.get("contract_hash"):
            blockers.append(_finding("graduation_contract_not_verifier_derived", skill_id=skill_id))
        if not _same_guard(evidence.get("guard_runtime"), identity.get("guard_runtime")):
            blockers.append(_finding("graduation_guard_not_verifier_derived", skill_id=skill_id))
        if evidence.get("version", "") != identity.get("version", ""):
            blockers.append(_finding("graduation_version_not_verifier_derived", skill_id=skill_id))
        identity_binding = evidence.get("target_identity_receipt")
        if (
            not isinstance(identity_binding, Mapping)
            or identity_binding.get("receipt_id") != identity.get("receipt_id")
            or identity_binding.get("receipt_hash") != identity.get("receipt_hash")
        ):
            blockers.append(
                _finding("graduation_target_identity_receipt_not_current", skill_id=skill_id)
            )
    findings, verified_installation_context = _graduation_evidence_findings(
        evidence,
        evidence_root=evidence_root,
        target_repository_root=target_repository_root,
        verified_installation_context=verified_installation_context,
    )
    if findings:
        blockers.extend(findings)
    preparation, preparation_findings = _load_graduation_preparation(
        evidence, evidence_root=evidence_root
    )
    if not findings:
        blockers.extend(preparation_findings)
    blockers.extend(
        _installed_parity_freshness_findings(
            evidence,
            preparation,
            evidence_root=evidence_root,
            target_repository_root=target_repository_root,
            installed_target_root=installed_target_root,
            target_identity=identity,
        )
    )
    if entry is None or entry.get("lifecycle") not in ACTIVE_LIFECYCLES:
        blockers.append(_finding("graduation_target_not_active", skill_id=skill_id))
    if evidence.get("registry_id") != registry.get("registry_id"):
        blockers.append(_finding("graduation_registry_id_mismatch", skill_id=skill_id))
    if (
        evidence.get("scope_manifest_id") != registry.get("scope_manifest_id")
        or evidence.get("scope_manifest_hash") != registry.get("scope_manifest_hash")
    ):
        blockers.append(_finding("graduation_scope_identity_mismatch", skill_id=skill_id))
    if actual_guard is not None and not _same_guard(active_guard, actual_guard):
        blockers.append(_finding("graduation_actual_guard_mismatch", skill_id=skill_id))
    if not _same_guard(evidence.get("guard_runtime"), active_guard):
        blockers.append(_finding("graduation_evidence_guard_mismatch", skill_id=skill_id))
    receipt = evidence["full_run_receipt"]
    assert isinstance(receipt, Mapping)
    if not _same_guard(receipt.get("guard_runtime"), active_guard):
        blockers.append(_finding("graduation_receipt_guard_mismatch", skill_id=skill_id))
    if receipt.get("contract_hash") != evidence.get("contract_hash"):
        blockers.append(_finding("graduation_receipt_contract_mismatch", skill_id=skill_id))
    if receipt.get("source_fingerprint") != evidence.get("source_fingerprint"):
        blockers.append(_finding("graduation_receipt_source_mismatch", skill_id=skill_id))
    if evidence.get("failure_classification") is not None:
        blockers.append(_finding("graduation_failure_unresolved", skill_id=skill_id))
    if isinstance(entry, Mapping):
        unresolved_failure_ids = _unique_string_list(entry.get("unresolved_failure_ids", []))
        if entry.get("failure_classification") is not None or unresolved_failure_ids:
            blockers.append(_finding("graduation_registry_failure_unresolved", skill_id=skill_id))

    normalized_jobs, _job_findings = _normalized_representative_jobs(
        evidence.get("representative_jobs"), require_job_classes=True
    )
    if isinstance(entry, Mapping):
        blockers.extend(
            _member_capability_inventory_findings(
                entry,
                target_identity=identity,
            )
        )
        member_inventory, _member_inventory_findings = (
            _normalized_member_capability_inventory(
                entry.get("member_capability_inventory")
            )
        )
        capabilities_by_member = {
            str(row["member_skill_id"]): set(row["required_capability_ids"])
            for row in member_inventory
        }
        observed_by_member: dict[str, set[str]] = {
            member_skill_id: set() for member_skill_id in capabilities_by_member
        }
        for job in normalized_jobs:
            member_skill_id = str(job.get("member_skill_id", ""))
            capabilities = set(
                str(value) for value in job.get("covered_capability_ids", [])
            )
            allowed = capabilities_by_member.get(member_skill_id)
            if allowed is None or not capabilities.issubset(allowed):
                blockers.append(
                    _finding(
                        "graduation_job_cross_member_capability_claim",
                        skill_id=skill_id,
                        detail=str(job.get("job_id", "")),
                    )
                )
            else:
                observed_by_member[member_skill_id].update(capabilities)
        for member_skill_id, required_member_capabilities in capabilities_by_member.items():
            missing_member_capabilities = sorted(
                required_member_capabilities
                - observed_by_member.get(member_skill_id, set())
            )
            if missing_member_capabilities:
                blockers.append(
                    _finding(
                        "graduation_member_capability_coverage_incomplete",
                        skill_id=skill_id,
                        detail=(
                            f"{member_skill_id}:"
                            f"{','.join(missing_member_capabilities)}"
                        ),
                    )
                )
    covered_capabilities = {
        capability
        for job in normalized_jobs
        for capability in job["covered_capability_ids"]
    }
    if entry is not None:
        if entry.get("capability_inventory_status", "pending") != "current":
            blockers.append(_finding("graduation_capability_inventory_incomplete", skill_id=skill_id))
        required_capabilities = _unique_string_list(entry.get("required_capability_ids", [])) or []
        missing_capabilities = sorted(set(required_capabilities) - covered_capabilities)
        if not required_capabilities:
            blockers.append(_finding("graduation_required_capabilities_missing", skill_id=skill_id))
        if missing_capabilities:
            blockers.append(
                _finding(
                    "graduation_capability_coverage_incomplete",
                    skill_id=skill_id,
                    detail=",".join(missing_capabilities),
                )
            )
        declared_job_classes = _unique_string_list(
            entry.get("required_job_class_ids", list(DEFAULT_REQUIRED_JOB_CLASS_IDS))
        )
        required_job_classes = (
            sorted(set(DEFAULT_REQUIRED_JOB_CLASS_IDS) | set(declared_job_classes))
            if declared_job_classes is not None
            else None
        )
        covered_job_classes = {
            job_class
            for job in normalized_jobs
            for job_class in job.get("job_class_ids", [])
        }
        if required_job_classes is None or not required_job_classes:
            blockers.append(_finding("graduation_required_job_classes_missing", skill_id=skill_id))
        else:
            unknown_job_classes = sorted(set(required_job_classes) - JOB_CLASS_IDS)
            missing_job_classes = sorted(set(required_job_classes) - covered_job_classes)
            if unknown_job_classes:
                blockers.append(
                    _finding(
                        "graduation_required_job_classes_invalid",
                        skill_id=skill_id,
                        detail=",".join(unknown_job_classes),
                    )
                )
            if missing_job_classes:
                blockers.append(
                    _finding(
                        "graduation_job_class_coverage_incomplete",
                        skill_id=skill_id,
                        detail=",".join(missing_job_classes),
                    )
                )

    if entry is not None:
        candidate_order = int(entry["order"])
        installation_context_holder = (
            [verified_installation_context]
            if verified_installation_context is not None
            else []
        )
        guard_change_history = [
            row for row in registry.get("guard_change_history", []) if isinstance(row, Mapping)
        ]
        for prior in entries:
            if prior.get("lifecycle") in ACTIVE_LIFECYCLES and int(prior["order"]) < candidate_order:
                if not entry_is_current(
                    prior,
                    active_guard,
                    guard_change_history,
                    evidence_root=evidence_root,
                    registry_id=str(registry.get("registry_id", "")),
                    scope_manifest_id=str(registry.get("scope_manifest_id", "")),
                    scope_manifest_hash=str(registry.get("scope_manifest_hash", "")),
                    target_repository_root=currentness_repository_roots.get(
                        str(prior.get("skill_id", ""))
                    ),
                    installation_context_holder=installation_context_holder,
                ):
                    blockers.append(_finding("prior_graduate_not_current", skill_id=str(prior.get("skill_id", ""))))
    if blockers or entry is None:
        return (
            {
                "artifact_type": "skillguard_portfolio_graduation_result",
                "status": "blocked",
                "skill_id": skill_id,
                "blockers": blockers,
                "claim_boundary": "No target graduated and no registry mutation occurred.",
            },
            None,
            None,
        )

    updated = copy.deepcopy(dict(registry))
    updated["previous_registry_hash"] = str(registry.get("registry_hash", ""))
    updated["revision"] = int(registry.get("revision", 0)) + 1
    updated_entry = next(item for item in updated["entries"] if item.get("skill_id") == skill_id)
    assert identity is not None
    updated_entry.setdefault("canonical_source", {})["source_fingerprint"] = evidence["source_fingerprint"]
    if identity.get("version"):
        updated_entry["canonical_source"]["version"] = identity["version"]
    updated_entry["target_identity_receipt"] = copy.deepcopy(identity)
    updated_entry["contract_hash"] = evidence["contract_hash"]
    updated_entry["representative_jobs"] = normalized_jobs
    updated_entry["representative_job_ids"] = [job["job_id"] for job in normalized_jobs]
    updated_entry["required_job_class_ids"] = list(
        _unique_string_list(
            updated_entry.get("required_job_class_ids", list(DEFAULT_REQUIRED_JOB_CLASS_IDS))
        )
        or DEFAULT_REQUIRED_JOB_CLASS_IDS
    )
    updated_entry["full_run_receipt"] = copy.deepcopy(dict(receipt))
    updated_entry["production_revalidation_bindings"] = copy.deepcopy(
        receipt.get("production_revalidation_bindings", [])
    )
    updated_entry["production_revalidation_fingerprint"] = str(
        receipt.get("production_revalidation_fingerprint", "")
    )
    updated_entry["reuse_ticket"] = None
    updated_entry["reuse_ticket_chain"] = []
    updated_entry["graduation_status"] = "current"
    updated_entry["failure_classification"] = None
    updated_entry["last_revalidation"] = str(receipt["completed_at"])
    _clear_member_revalidation_state(updated_entry)
    updated_entry.pop("revalidation_reason", None)
    updated_entry.pop("pending_guard_change_id", None)
    updated["updated_at"] = str(receipt["completed_at"])
    intended_entry_state_hash = canonical_hash(updated_entry)

    prior_evidence = []
    for prior in entries:
        if prior.get("lifecycle") in ACTIVE_LIFECYCLES and int(prior["order"]) < int(entry["order"]):
            proof = prior.get("reuse_ticket") or prior.get("full_run_receipt") or {}
            proof_identity = (
                proof.get("identity")
                if isinstance(proof.get("identity"), Mapping)
                else proof
            )
            prior_evidence.append(
                {
                    "skill_id": prior["skill_id"],
                    "proof_kind": (
                        "reuse_ticket" if proof.get("ticket_id") else "full_run_receipt"
                    ),
                    "proof_id": str(proof.get("ticket_id") or proof.get("receipt_id") or ""),
                    "proof_hash": str(proof.get("ticket_hash") or proof.get("receipt_hash") or ""),
                    "guard_runtime": dict(proof.get("to_guard") or proof.get("guard_runtime") or {}),
                    "source_fingerprint": str(proof_identity.get("source_fingerprint", "")),
                    "contract_hash": str(proof_identity.get("contract_hash", "")),
                    "coverage_fingerprint": str(proof_identity.get("coverage_fingerprint", "")),
                }
            )
    target_identity = {
        "target_kind": str(identity["target_kind"]),
        "skill_paths": list(identity["skill_paths"]),
        "member_identities": copy.deepcopy(identity["member_identities"]),
        **_receipt_identity(receipt),
        "production_revalidation_fingerprint": str(
            receipt.get("production_revalidation_fingerprint", "")
        ),
    }
    receipt_payload: dict[str, Any] = {
        "schema_version": PORTFOLIO_RECEIPT_SCHEMA,
        "receipt_id": f"portfolio-{canonical_hash(evidence)[:20].lower()}",
        "registry_id": registry["registry_id"],
        "scope_manifest_id": str(registry.get("scope_manifest_id", "")),
        "scope_manifest_hash": str(registry.get("scope_manifest_hash", "")),
        "transaction_id": str(evidence["transaction_id"]),
        "base_registry_revision": int(registry["revision"]),
        "base_registry_hash": str(registry["registry_hash"]),
        "registry_transaction": {
            "transaction_id": str(evidence["transaction_id"]),
            "base_registry_revision": int(registry["revision"]),
            "base_registry_hash": str(registry["registry_hash"]),
            "committed_registry_revision": int(registry["revision"]) + 1,
            "intended_entry_state_hash": intended_entry_state_hash,
        },
        "skill_id": skill_id,
        "target_kind": str(identity["target_kind"]),
        "skill_paths": list(identity["skill_paths"]),
        "status": "current",
        "guard_runtime": dict(active_guard),
        "contract_hash": evidence["contract_hash"],
        "source_fingerprint": evidence["source_fingerprint"],
        "target_identity": target_identity,
        "target_identity_scan_receipt_id": identity["receipt_id"],
        "target_identity_scan_receipt_hash": identity["receipt_hash"],
        "target_identity_scan_receipt_ref": str(
            evidence.get("target_identity_receipt", {}).get("ref", "")
        ),
        "graduation_evidence_hash": str(evidence.get("evidence_hash", "")),
        "job_plan_refs": list(evidence.get("job_plan_refs", [])),
        "job_plan_hash": str(evidence.get("job_plan_hash", "")),
        "job_spec_refs": list(evidence.get("job_spec_refs", [])),
        "job_spec_hash": str(evidence.get("job_spec_hash", "")),
        "representative_jobs": normalized_jobs,
        "representative_job_ids": [job["job_id"] for job in normalized_jobs],
        "evidence_record_refs": sorted(
            {
                str(ref)
                for job in normalized_jobs
                for ref in job.get("evidence_refs", [])
            }
        ),
        "production_revalidation_binding_refs": list(
            evidence.get("production_revalidation_binding_refs", [])
        ),
        "production_revalidation_fingerprint": str(
            evidence.get("production_revalidation_fingerprint", "")
        ),
        "full_run_receipt_id": str(receipt.get("receipt_id", "")),
        "full_run_receipt_hash": str(receipt.get("receipt_hash", "")),
        "full_run_result_hash": str(receipt.get("result_hash", "")),
        "intended_entry_state_hash": intended_entry_state_hash,
        "prior_evidence": prior_evidence,
        "issued_at": updated["updated_at"],
        "claim_boundary": (
            "This receipt proves the named target and every prior active portfolio entry had current full evidence or "
            "a valid reuse ticket under the exact active Guard identity at issuance."
        ),
    }
    receipt_payload["receipt_hash"] = canonical_hash(receipt_payload)
    updated_entry["portfolio_graduation_receipt"] = copy.deepcopy(receipt_payload)
    _append_registry_transaction(
        updated,
        registry,
        evidence,
        mutation_kind="graduation",
        committed_at=str(updated["updated_at"]),
        artifact_hashes=(str(receipt_payload["receipt_hash"]),),
    )
    _refresh_registry_hash(updated)
    return (
        {
            "artifact_type": "skillguard_portfolio_graduation_result",
            "status": "graduated",
            "skill_id": skill_id,
            "receipt_id": receipt_payload["receipt_id"],
            "receipt_hash": receipt_payload["receipt_hash"],
            "prior_evidence_count": len(prior_evidence),
            "claim_boundary": receipt_payload["claim_boundary"],
        },
        updated,
        receipt_payload,
    )


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(canonical_json_bytes(payload))
    os.replace(temporary, path)


class PortfolioRegistryLockError(RuntimeError):
    """Raised when another live writer owns the private portfolio registry."""


def _pid_alive(pid: object) -> bool:
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False
    if os.name == "nt":
        # On Windows Python implements os.kill through TerminateProcess for
        # ordinary signals; even signal 0 is not a safe existence probe. Use
        # a query-only process handle so lock inspection can never kill the
        # writer it is trying to protect.
        import ctypes
        from ctypes import wintypes

        process_query_limited_information = 0x1000
        still_active = 259
        error_access_denied = 5
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(
            process_query_limited_information, False, int(pid)
        )
        if not handle:
            # Access denied still proves an extant protected process. Other
            # failures (notably invalid parameter for a nonexistent PID) are
            # treated as not alive.
            return ctypes.get_last_error() == error_access_denied
        try:
            exit_code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return True
            return int(exit_code.value) == still_active
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


@contextmanager
def portfolio_registry_lock(
    registry_path: Path,
    *,
    timeout_seconds: float = 5.0,
    stale_after_seconds: float = 60.0,
) -> Iterator[dict[str, Any]]:
    """Serialize short registry mutations and recover abandoned writer locks."""

    registry_path = registry_path.resolve()
    lock_path = registry_path.with_name(f".{registry_path.name}.skillguard.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    token = canonical_hash(
        {
            "path": str(registry_path),
            "pid": os.getpid(),
            "time_ns": time.time_ns(),
        }
    )
    payload = {
        "schema_version": "skillguard.portfolio_registry_lock.v1",
        "token": token,
        "owner_pid": os.getpid(),
        "owner_host": socket.gethostname(),
        "claimed_at": utc_now(),
    }
    deadline = time.monotonic() + timeout_seconds
    recovered = False
    while True:
        try:
            descriptor = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            try:
                raw_payload = canonical_json_bytes(payload)
                offset = 0
                while offset < len(raw_payload):
                    offset += os.write(descriptor, raw_payload[offset:])
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            break
        except FileExistsError:
            existing: Mapping[str, Any] = {}
            existing_raw = b""
            try:
                existing_raw = lock_path.read_bytes()
                loaded = json.loads(existing_raw.decode("utf-8"))
                if isinstance(loaded, Mapping):
                    existing = loaded
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                existing = {}
            try:
                lock_stat = lock_path.stat()
            except FileNotFoundError:
                continue
            same_host = existing.get("owner_host") in (None, "", socket.gethostname())
            # Age alone is not authority to steal a live writer's lock.  Local
            # locks are recoverable only after their owner PID is confirmed
            # dead; remote/unknown-host locks require explicit intervention.
            owner_record_complete = (
                existing.get("schema_version")
                == "skillguard.portfolio_registry_lock.v1"
                and isinstance(existing.get("token"), str)
                and bool(existing.get("token"))
                and isinstance(existing.get("owner_pid"), int)
                and not isinstance(existing.get("owner_pid"), bool)
            )
            invalid_lock_old_enough = (
                not owner_record_complete
                and max(0.0, time.time() - lock_stat.st_mtime)
                >= stale_after_seconds
            )
            abandoned = (
                owner_record_complete
                and same_host
                and not _pid_alive(existing.get("owner_pid"))
            ) or invalid_lock_old_enough
            if abandoned:
                try:
                    # Do not unlink a lock that changed after inspection. This
                    # closes the common stale-lock ABA window and preserves a
                    # freshly written owner record.
                    if lock_path.read_bytes() != existing_raw:
                        continue
                    lock_path.unlink()
                    recovered = True
                    continue
                except FileNotFoundError:
                    continue
            if time.monotonic() >= deadline:
                raise PortfolioRegistryLockError(
                    f"portfolio registry is owned by pid {existing.get('owner_pid', 'unknown')}"
                )
            time.sleep(0.02)
    try:
        yield {"lock_recovered": recovered, "lock_file": lock_path.name}
    finally:
        try:
            current = json.loads(lock_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            current = {}
        if isinstance(current, Mapping) and current.get("token") == token:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass


def current_guard(
    runtime_root: Path | None = None,
    *,
    active_installation_currentness: bool = False,
) -> dict[str, Any]:
    root = resolve_guard_runtime_root(
        runtime_root or Path(__file__).resolve().parent
    )
    manifest_path = root / ".skillguard" / "check-manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("portfolio_guard_projection_manifest_missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, Mapping):
        raise ValueError("portfolio_guard_projection_manifest_invalid")
    plan = manifest.get("content_impact_plan")
    if not isinstance(plan, Mapping):
        raise ValueError("portfolio_guard_projection_plan_missing")
    projection = current_content_projection(plan, "projection:portfolio")
    runtime = (
        guard_active_installation_runtime_fingerprint(root)
        if active_installation_currentness
        else guard_runtime_fingerprint(root)
    )
    return {
        "runtime_id": runtime["runtime_id"],
        "provider_id": runtime["provider_id"],
        "runtime_contract_id": runtime["runtime_contract_id"],
        "capability_ids": list(runtime["capability_ids"]),
        "enrollment_status": runtime["enrollment_status"],
        "file_count": len(projection["input_component_ids"]),
        "source_hash": canonical_hash(
            {
                "portfolio_projection_hash": projection[
                    "consumer_projection_hash"
                ]
            }
        ),
        "portfolio_projection_hash": projection["consumer_projection_hash"],
    }
