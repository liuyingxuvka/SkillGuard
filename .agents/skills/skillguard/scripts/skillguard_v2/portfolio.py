"""Private portfolio registry, impact propagation, reuse, and graduation gates."""

from __future__ import annotations

import copy
import json
import os
import re
import socket
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from .contract_compiler import canonical_hash, canonical_json_bytes
from .run_store import utc_now
from .runtime_fingerprint import guard_runtime_fingerprint


PORTFOLIO_REGISTRY_SCHEMA = "skillguard.portfolio_registry.v1"
GUARD_CHANGE_SCHEMA = "skillguard.guard_change.v1"
GRADUATION_EVIDENCE_SCHEMA = "skillguard.portfolio_graduation_evidence.v1"
REUSE_REQUEST_SCHEMA = "skillguard.test_result_reuse_request.v1"
REUSE_TICKET_SCHEMA = "skillguard.test_result_reuse_ticket.v1"
PORTFOLIO_RECEIPT_SCHEMA = "skillguard.portfolio_graduation_receipt.v1"

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


def _finding(code: str, *, skill_id: str = "", detail: str = "") -> dict[str, str]:
    return {"code": code, "skill_id": skill_id, "detail": detail}


def _hash_ok(value: object) -> bool:
    return isinstance(value, str) and bool(HASH_RE.fullmatch(value))


def _string_list(value: object) -> list[str] | None:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        return None
    return [str(item) for item in value]


def _unique_string_list(value: object) -> list[str] | None:
    values = _string_list(value)
    if values is None or len(values) != len(set(values)):
        return None
    return values


def _guard_ok(value: object) -> bool:
    return (
        isinstance(value, Mapping)
        and value.get("runtime_id") == "skillguard-v2"
        and isinstance(value.get("file_count"), int)
        and int(value["file_count"]) > 0
        and _hash_ok(value.get("source_hash"))
    )


def _same_guard(left: object, right: object) -> bool:
    if not _guard_ok(left) or not _guard_ok(right):
        return False
    assert isinstance(left, Mapping) and isinstance(right, Mapping)
    return (
        left["runtime_id"] == right["runtime_id"]
        and left["file_count"] == right["file_count"]
        and left["source_hash"] == right["source_hash"]
    )


def _identity_ok(value: object) -> bool:
    return isinstance(value, Mapping) and all(_hash_ok(value.get(field)) for field in IDENTITY_FIELDS)


def _receipt_identity(receipt: Mapping[str, Any]) -> dict[str, str]:
    return {field: str(receipt.get(field, "")) for field in IDENTITY_FIELDS}


def _full_receipt_identity_complete(receipt: object) -> bool:
    return (
        isinstance(receipt, Mapping)
        and receipt.get("status") == "current"
        and _identity_ok(receipt)
        and isinstance(receipt.get("receipt_id"), str)
        and bool(receipt.get("receipt_id"))
        and isinstance(receipt.get("completed_at"), str)
        and bool(receipt.get("completed_at"))
        and _hash_ok(receipt.get("result_hash"))
        and _guard_ok(receipt.get("guard_runtime"))
    )


def _normalized_representative_jobs(value: object) -> tuple[list[dict[str, Any]], list[str]]:
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
        if not job_id:
            findings.append(f"representative_job_id_missing:{index}")
        elif job_id in seen_job_ids:
            findings.append(f"representative_job_id_duplicate:{job_id}")
        seen_job_ids.add(job_id)
        if capabilities is None or not capabilities:
            findings.append(f"representative_job_capabilities_invalid:{job_id or index}")
        if evidence_refs is None or not evidence_refs:
            findings.append(f"representative_job_evidence_invalid:{job_id or index}")
        if job_id and capabilities and evidence_refs:
            jobs.append(
                {
                    "job_id": job_id,
                    "covered_capability_ids": sorted(capabilities),
                    "evidence_refs": sorted(evidence_refs),
                }
            )
    return sorted(jobs, key=lambda item: item["job_id"]), findings


def representative_jobs_coverage_fingerprint(value: object) -> str:
    jobs, findings = _normalized_representative_jobs(value)
    if findings:
        return ""
    return canonical_hash({"representative_jobs": jobs})


def _ticket_hash(ticket: Mapping[str, Any]) -> str:
    payload = dict(ticket)
    payload.pop("ticket_hash", None)
    return canonical_hash(payload)


def validate_registry(registry: object) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if not isinstance(registry, Mapping):
        return [_finding("registry_not_object")]
    if registry.get("schema_version") != PORTFOLIO_REGISTRY_SCHEMA:
        findings.append(_finding("registry_schema_unsupported"))
    if not isinstance(registry.get("registry_id"), str) or not registry.get("registry_id"):
        findings.append(_finding("registry_id_missing"))
    if not _guard_ok(registry.get("active_guard")):
        findings.append(_finding("active_guard_invalid"))
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
    for entry in entries:
        if not isinstance(entry, Mapping) or entry.get("lifecycle") != SUPPORTING_LIFECYCLE:
            continue
        skill_id = str(entry.get("skill_id", ""))
        parent = entry_by_id.get(str(entry.get("parent_skill_id", "")))
        if parent is None or parent.get("lifecycle") not in ACTIVE_LIFECYCLES:
            findings.append(_finding("supporting_parent_not_active", skill_id=skill_id))
    return findings


def _full_receipt_is_current(entry: Mapping[str, Any], active_guard: Mapping[str, Any]) -> bool:
    receipt = entry.get("full_run_receipt")
    source = entry.get("canonical_source")
    if not _full_receipt_identity_complete(receipt):
        return False
    assert isinstance(receipt, Mapping)
    if not isinstance(source, Mapping) or receipt.get("source_fingerprint") != source.get("source_fingerprint"):
        return False
    if receipt.get("contract_hash") != entry.get("contract_hash"):
        return False
    jobs, job_findings = _normalized_representative_jobs(entry.get("representative_jobs"))
    if job_findings or receipt.get("coverage_fingerprint") != representative_jobs_coverage_fingerprint(jobs):
        return False
    covered_capabilities = {
        capability for job in jobs for capability in job["covered_capability_ids"]
    }
    required_capabilities = _unique_string_list(entry.get("required_capability_ids", [])) or []
    if not required_capabilities or not set(required_capabilities).issubset(covered_capabilities):
        return False
    return _same_guard(receipt.get("guard_runtime"), active_guard)


def _reuse_ticket_is_current(
    entry: Mapping[str, Any],
    active_guard: Mapping[str, Any],
    guard_change_history: Sequence[Mapping[str, Any]] = (),
) -> bool:
    ticket = entry.get("reuse_ticket")
    source = entry.get("canonical_source")
    if not isinstance(ticket, Mapping) or ticket.get("schema_version") != REUSE_TICKET_SCHEMA:
        return False
    if ticket.get("status") != "current" or ticket.get("ticket_hash") != _ticket_hash(ticket):
        return False
    if ticket.get("skill_id") != entry.get("skill_id") or not _same_guard(ticket.get("to_guard"), active_guard):
        return False
    if ticket.get("broad_semantic_change") is not False:
        return False
    affected_tags = _unique_string_list(ticket.get("affected_feature_tags"))
    if affected_tags is None:
        return False
    consumed = set(str(item) for item in entry.get("consumed_guard_feature_tags", []))
    if consumed & set(affected_tags):
        return False
    identity = ticket.get("identity")
    if not _identity_ok(identity) or not isinstance(source, Mapping):
        return False
    assert isinstance(identity, Mapping)
    old_receipt = entry.get("full_run_receipt")
    if not _full_receipt_identity_complete(old_receipt):
        return False
    assert isinstance(old_receipt, Mapping)
    if _receipt_identity(old_receipt) != _receipt_identity(identity):
        return False
    if not _same_guard(ticket.get("from_guard"), old_receipt.get("guard_runtime")):
        return False
    history_match = next(
        (
            change
            for change in guard_change_history
            if change.get("change_id") == ticket.get("change_id")
            and _same_guard(change.get("guard_before"), ticket.get("from_guard"))
            and _same_guard(change.get("guard_after"), ticket.get("to_guard"))
            and change.get("broad_semantic_change") is False
            and sorted(change.get("affected_feature_tags", [])) == sorted(affected_tags)
        ),
        None,
    )
    if history_match is None:
        return False
    return (
        identity.get("source_fingerprint") == source.get("source_fingerprint")
        and identity.get("contract_hash") == entry.get("contract_hash")
    )


def entry_is_current(
    entry: Mapping[str, Any],
    active_guard: Mapping[str, Any],
    guard_change_history: Sequence[Mapping[str, Any]] = (),
) -> bool:
    return (
        entry.get("lifecycle") in ACTIVE_LIFECYCLES
        and entry.get("graduation_status") == "current"
        and entry.get("capability_inventory_status", "pending") == "current"
        and (
            _full_receipt_is_current(entry, active_guard)
            or _reuse_ticket_is_current(entry, active_guard, guard_change_history)
        )
    )


def audit_portfolio(
    registry: object,
    *,
    actual_guard: Mapping[str, Any] | None = None,
    candidate_skill_id: str = "",
) -> dict[str, Any]:
    schema_findings = validate_registry(registry)
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
    for entry in sorted(active_entries, key=lambda item: int(item.get("order", 10**9))):
        skill_id = str(entry.get("skill_id", ""))
        if entry.get("capability_inventory_status", "pending") != "current":
            pending_capability_inventory_ids.append(skill_id)
        if entry_is_current(entry, active_guard, guard_change_history):
            current_ids.append(skill_id)
        else:
            pending_ids.append(skill_id)

    if candidate_skill_id:
        candidate = next((entry for entry in active_entries if entry.get("skill_id") == candidate_skill_id), None)
        if candidate is None:
            blockers.append(_finding("candidate_missing", skill_id=candidate_skill_id))
        else:
            if candidate.get("capability_inventory_status", "pending") != "current":
                blockers.append(
                    _finding("candidate_capability_inventory_incomplete", skill_id=candidate_skill_id)
                )
            candidate_order = int(candidate["order"])
            for prior in active_entries:
                if int(prior["order"]) < candidate_order and not entry_is_current(
                    prior, active_guard, guard_change_history
                ):
                    blockers.append(
                        _finding("prior_graduate_not_current", skill_id=str(prior.get("skill_id", "")))
                    )

    status = "blocked" if blockers else "current" if not pending_ids else "incomplete"
    return {
        "artifact_type": "skillguard_portfolio_audit",
        "schema_version": "skillguard.portfolio_audit.v1",
        "registry_id": registry["registry_id"],
        "status": status,
        "active_guard": dict(active_guard),
        "active_entry_count": len(active_entries),
        "current_skill_ids": current_ids,
        "non_current_skill_ids": pending_ids,
        "capability_inventory_pending_skill_ids": pending_capability_inventory_ids,
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


def validate_guard_change(change: object) -> list[dict[str, str]]:
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
    if not isinstance(change.get("broad_semantic_change"), bool):
        findings.append(_finding("broad_semantic_change_invalid"))
    if not isinstance(change.get("reason"), str) or not change.get("reason"):
        findings.append(_finding("guard_change_reason_missing"))
    return findings


def apply_guard_change(registry: object, change: object) -> tuple[dict[str, Any], dict[str, Any] | None]:
    findings = validate_registry(registry) + validate_guard_change(change)
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
    updated["active_guard"] = dict(change["guard_after"])
    updated["updated_at"] = utc_now()
    affected_tags = set(str(item) for item in change["affected_feature_tags"])
    broad = bool(change["broad_semantic_change"])
    invalidated: list[dict[str, Any]] = []
    for entry in updated["entries"]:
        if entry.get("lifecycle") not in ACTIVE_LIFECYCLES or entry.get("graduation_status") != "current":
            continue
        consumed = set(str(item) for item in entry.get("consumed_guard_feature_tags", []))
        intersection = sorted(consumed & affected_tags)
        entry["graduation_status"] = "revalidation_required"
        entry["reuse_ticket"] = None
        entry["revalidation_reason"] = (
            "broad_guard_semantic_change"
            if broad
            else "affected_guard_feature"
            if intersection
            else "proof_bound_reuse_ticket_required"
        )
        entry["pending_guard_change_id"] = str(change["change_id"])
        invalidated.append(
            {
                "skill_id": entry["skill_id"],
                "affected": broad or bool(intersection),
                "intersecting_feature_tags": intersection,
            }
        )
    updated.setdefault("guard_change_history", []).append(
        {
            "change_id": change["change_id"],
            "guard_before": dict(change["guard_before"]),
            "guard_after": dict(change["guard_after"]),
            "affected_feature_tags": list(change["affected_feature_tags"]),
            "broad_semantic_change": broad,
            "recorded_at": updated["updated_at"],
        }
    )
    return (
        {
            "artifact_type": "skillguard_portfolio_impact_result",
            "schema_version": "skillguard.portfolio_impact_result.v1",
            "status": "updated",
            "change_id": change["change_id"],
            "invalidated_entries": invalidated,
            "claim_boundary": (
                "This result invalidates prior confidence after a Guard change. It does not revalidate any target; "
                "unaffected targets still need a proof-bound reuse ticket before returning to current."
            ),
        },
        updated,
    )


def issue_reuse_ticket(
    registry: object, request: object
) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any] | None]:
    findings = validate_registry(registry)
    if not isinstance(request, Mapping):
        findings.append(_finding("reuse_request_not_object"))
    elif request.get("schema_version") != REUSE_REQUEST_SCHEMA:
        findings.append(_finding("reuse_request_schema_unsupported"))
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
    if validate_guard_change(change):
        blockers.append(_finding("reuse_guard_change_invalid", skill_id=skill_id))
    if not _identity_ok(previous) or not _identity_ok(current):
        blockers.append(_finding("reuse_identity_invalid", skill_id=skill_id))
    if blockers or entry is None or not isinstance(change, Mapping) or not isinstance(previous, Mapping) or not isinstance(current, Mapping):
        return ({"artifact_type": "skillguard_reuse_ticket_result", "status": "blocked", "blockers": blockers}, None, None)
    if entry.get("lifecycle") not in ACTIVE_LIFECYCLES:
        blockers.append(_finding("reuse_skill_not_active", skill_id=skill_id))
    if entry.get("graduation_status") != "revalidation_required":
        blockers.append(_finding("reuse_target_not_revalidation_required", skill_id=skill_id))
    if entry.get("pending_guard_change_id") != change.get("change_id"):
        blockers.append(_finding("reuse_pending_change_mismatch", skill_id=skill_id))
    if change.get("broad_semantic_change"):
        blockers.append(_finding("reuse_forbidden_for_broad_change", skill_id=skill_id))
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
        ),
        None,
    )
    if history_match is None:
        blockers.append(_finding("reuse_guard_change_not_registered", skill_id=skill_id))
    old_receipt = entry.get("full_run_receipt")
    if not _full_receipt_identity_complete(old_receipt):
        blockers.append(_finding("reuse_previous_receipt_incomplete", skill_id=skill_id))
    if not isinstance(old_receipt, Mapping) or _receipt_identity(old_receipt) != _receipt_identity(previous):
        blockers.append(_finding("reuse_previous_result_not_registered", skill_id=skill_id))
    if not isinstance(old_receipt, Mapping) or not old_receipt.get("completed_at"):
        blockers.append(_finding("reuse_previous_completion_missing", skill_id=skill_id))
    if _receipt_identity(previous) != _receipt_identity(current):
        blockers.append(_finding("reuse_identity_changed", skill_id=skill_id))
    if isinstance(old_receipt, Mapping) and not _same_guard(
        change.get("guard_before"), old_receipt.get("guard_runtime")
    ):
        blockers.append(_finding("reuse_guard_before_not_previous_receipt", skill_id=skill_id))
    if blockers:
        return ({"artifact_type": "skillguard_reuse_ticket_result", "status": "blocked", "blockers": blockers}, None, None)

    assert isinstance(old_receipt, Mapping)
    ticket: dict[str, Any] = {
        "schema_version": REUSE_TICKET_SCHEMA,
        "ticket_id": f"reuse-{canonical_hash(request)[:20].lower()}",
        "skill_id": skill_id,
        "status": "current",
        "change_id": change["change_id"],
        "from_guard": dict(change["guard_before"]),
        "to_guard": dict(change["guard_after"]),
        "affected_feature_tags": sorted(str(item) for item in change["affected_feature_tags"]),
        "broad_semantic_change": False,
        "identity": _receipt_identity(current),
        "issued_at": str(old_receipt["completed_at"]),
        "claim_boundary": "Reuse proves only unchanged registered identity and non-intersection with the named non-broad Guard change.",
    }
    ticket["ticket_hash"] = _ticket_hash(ticket)
    updated = copy.deepcopy(dict(registry))
    updated_entry = next(item for item in updated["entries"] if item.get("skill_id") == skill_id)
    updated_entry["reuse_ticket"] = ticket
    updated_entry["graduation_status"] = "current"
    updated_entry["last_revalidation"] = ticket["issued_at"]
    updated_entry.pop("revalidation_reason", None)
    updated_entry.pop("pending_guard_change_id", None)
    updated["updated_at"] = ticket["issued_at"]
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


def _graduation_evidence_findings(evidence: object) -> list[dict[str, str]]:
    if not isinstance(evidence, Mapping):
        return [_finding("graduation_evidence_not_object")]
    skill_id = str(evidence.get("skill_id", ""))
    findings: list[dict[str, str]] = []
    if evidence.get("schema_version") != GRADUATION_EVIDENCE_SCHEMA:
        findings.append(_finding("graduation_evidence_schema_unsupported", skill_id=skill_id))
    if not skill_id:
        findings.append(_finding("graduation_skill_id_missing"))
    if not _guard_ok(evidence.get("guard_runtime")):
        findings.append(_finding("graduation_guard_invalid", skill_id=skill_id))
    if not _hash_ok(evidence.get("contract_hash")) or not _hash_ok(evidence.get("source_fingerprint")):
        findings.append(_finding("graduation_source_or_contract_invalid", skill_id=skill_id))
    _jobs, job_findings = _normalized_representative_jobs(evidence.get("representative_jobs"))
    for finding in job_findings:
        findings.append(_finding(finding.split(":", 1)[0], skill_id=skill_id, detail=finding))
    receipt = evidence.get("full_run_receipt")
    if not _full_receipt_identity_complete(receipt):
        findings.append(_finding("full_run_receipt_invalid", skill_id=skill_id))
    elif receipt.get("coverage_fingerprint") != representative_jobs_coverage_fingerprint(
        evidence.get("representative_jobs")
    ):
        findings.append(_finding("representative_jobs_not_bound_to_receipt", skill_id=skill_id))
    failure = evidence.get("failure_classification")
    if failure is not None and failure not in FAILURE_CLASSIFICATIONS:
        findings.append(_finding("graduation_failure_classification_invalid", skill_id=skill_id))
    return findings


def graduate_portfolio_target(
    registry: object,
    evidence: object,
    *,
    actual_guard: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any] | None]:
    findings = validate_registry(registry) + _graduation_evidence_findings(evidence)
    if findings or not isinstance(registry, Mapping) or not isinstance(evidence, Mapping):
        return ({"artifact_type": "skillguard_portfolio_graduation_result", "status": "blocked", "blockers": findings}, None, None)
    skill_id = str(evidence["skill_id"])
    entries = [entry for entry in registry["entries"] if isinstance(entry, Mapping)]
    entry = next((item for item in entries if item.get("skill_id") == skill_id), None)
    blockers: list[dict[str, str]] = []
    active_guard = registry["active_guard"]
    assert isinstance(active_guard, Mapping)
    if entry is None or entry.get("lifecycle") not in ACTIVE_LIFECYCLES:
        blockers.append(_finding("graduation_target_not_active", skill_id=skill_id))
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

    normalized_jobs, _job_findings = _normalized_representative_jobs(
        evidence.get("representative_jobs")
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

    if entry is not None:
        candidate_order = int(entry["order"])
        guard_change_history = [
            row for row in registry.get("guard_change_history", []) if isinstance(row, Mapping)
        ]
        for prior in entries:
            if prior.get("lifecycle") in ACTIVE_LIFECYCLES and int(prior["order"]) < candidate_order:
                if not entry_is_current(prior, active_guard, guard_change_history):
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
    updated_entry = next(item for item in updated["entries"] if item.get("skill_id") == skill_id)
    updated_entry.setdefault("canonical_source", {})["source_fingerprint"] = evidence["source_fingerprint"]
    if evidence.get("version"):
        updated_entry["canonical_source"]["version"] = evidence["version"]
    updated_entry["contract_hash"] = evidence["contract_hash"]
    updated_entry["representative_jobs"] = normalized_jobs
    updated_entry["representative_job_ids"] = [job["job_id"] for job in normalized_jobs]
    updated_entry["full_run_receipt"] = copy.deepcopy(dict(receipt))
    updated_entry["reuse_ticket"] = None
    updated_entry["graduation_status"] = "current"
    updated_entry["failure_classification"] = None
    updated_entry["last_revalidation"] = str(receipt["completed_at"])
    updated_entry.pop("revalidation_reason", None)
    updated_entry.pop("pending_guard_change_id", None)
    updated["updated_at"] = str(receipt["completed_at"])

    prior_evidence = []
    for prior in entries:
        if prior.get("lifecycle") in ACTIVE_LIFECYCLES and int(prior["order"]) < int(entry["order"]):
            proof = prior.get("reuse_ticket") or prior.get("full_run_receipt") or {}
            prior_evidence.append(
                {
                    "skill_id": prior["skill_id"],
                    "proof_id": str(proof.get("ticket_id") or proof.get("receipt_id") or ""),
                    "proof_hash": str(proof.get("ticket_hash") or proof.get("result_hash") or ""),
                    "guard_runtime": dict(proof.get("to_guard") or proof.get("guard_runtime") or {}),
                }
            )
    target_identity = _receipt_identity(receipt)
    receipt_payload: dict[str, Any] = {
        "schema_version": PORTFOLIO_RECEIPT_SCHEMA,
        "receipt_id": f"portfolio-{canonical_hash(evidence)[:20].lower()}",
        "registry_id": registry["registry_id"],
        "skill_id": skill_id,
        "status": "current",
        "guard_runtime": dict(active_guard),
        "contract_hash": evidence["contract_hash"],
        "source_fingerprint": evidence["source_fingerprint"],
        "target_identity": target_identity,
        "representative_jobs": normalized_jobs,
        "representative_job_ids": [job["job_id"] for job in normalized_jobs],
        "full_run_receipt_id": str(receipt.get("receipt_id", "")),
        "full_run_result_hash": str(receipt.get("result_hash", "")),
        "prior_evidence": prior_evidence,
        "issued_at": updated["updated_at"],
        "claim_boundary": (
            "This receipt proves the named target and every prior active portfolio entry had current full evidence or "
            "a valid reuse ticket under the exact active Guard identity at issuance."
        ),
    }
    receipt_payload["receipt_hash"] = canonical_hash(receipt_payload)
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
                os.write(descriptor, canonical_json_bytes(payload))
            finally:
                os.close(descriptor)
            break
        except FileExistsError:
            existing: Mapping[str, Any] = {}
            try:
                loaded = json.loads(lock_path.read_text(encoding="utf-8"))
                if isinstance(loaded, Mapping):
                    existing = loaded
            except (OSError, json.JSONDecodeError):
                existing = {}
            try:
                age = max(0.0, time.time() - lock_path.stat().st_mtime)
            except FileNotFoundError:
                continue
            same_host = existing.get("owner_host") in (None, "", socket.gethostname())
            abandoned = age >= stale_after_seconds or (
                same_host and not _pid_alive(existing.get("owner_pid"))
            )
            if abandoned:
                try:
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


def current_guard(runtime_root: Path | None = None) -> dict[str, Any]:
    return guard_runtime_fingerprint(runtime_root)
