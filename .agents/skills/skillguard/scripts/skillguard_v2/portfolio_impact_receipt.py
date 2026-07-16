"""Immutable portfolio-impact handoff receipts for SkillGuard model misses."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contract_compiler import canonical_hash
from .portfolio import atomic_write_json


IMPACT_RECEIPT_SCHEMA = "skillguard.portfolio_impact_receipt.v1"
IMPACT_HEAD_SCHEMA = "skillguard.portfolio_impact_head.v1"


def _id_list(value: object) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        return []
    return sorted(
        {
            str(item).strip()
            for item in value
            if isinstance(item, str) and str(item).strip()
        }
    )


def _member_ids_by_suite(value: object) -> dict[str, list[str]]:
    if not isinstance(value, Mapping):
        return {}
    normalized: dict[str, list[str]] = {}
    for raw_suite_id, raw_member_ids in value.items():
        suite_id = str(raw_suite_id).strip()
        member_ids = _id_list(raw_member_ids)
        if suite_id and member_ids:
            normalized[suite_id] = member_ids
    return dict(sorted(normalized.items()))


def _required_impact_ids(
    required_target_ids: Sequence[str],
    required_member_ids_by_suite: Mapping[str, Sequence[str]],
) -> list[str]:
    return sorted(
        set(str(item) for item in required_target_ids)
        | {
            str(member_id)
            for member_ids in required_member_ids_by_suite.values()
            for member_id in member_ids
        }
    )


def _member_status_projection(
    entries: Mapping[str, Mapping[str, Any]],
    required_member_ids_by_suite: Mapping[str, Sequence[str]],
) -> dict[str, dict[str, Any]]:
    projection: dict[str, dict[str, Any]] = {}
    for suite_id, member_ids in sorted(required_member_ids_by_suite.items()):
        entry = entries.get(suite_id, {})
        statuses = entry.get("member_revalidation_statuses", {})
        if not isinstance(statuses, Mapping):
            statuses = {}
        projection[suite_id] = {
            member_id: dict(statuses[member_id])
            for member_id in member_ids
            if isinstance(statuses.get(member_id), Mapping)
        }
    return projection


def _portable_ref(path: Path, root: Path, *, token: str) -> dict[str, str]:
    resolved_root = root.resolve()
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"portfolio_impact_path_escapes_{token}") from exc
    if relative == Path("."):
        raise ValueError("portfolio_impact_path_must_be_file")
    return {"path_token": token, "relative_path": relative.as_posix()}


def build_portfolio_impact_receipt(
    *,
    change: Mapping[str, Any],
    registry: Mapping[str, Any],
    registry_path: Path,
    workspace_root: Path,
    impact_result: Mapping[str, Any],
) -> dict[str, Any]:
    invalidated = sorted(
        str(row.get("skill_id", ""))
        for row in impact_result.get("invalidated_entries", [])
        if isinstance(row, Mapping) and str(row.get("skill_id", ""))
    )
    entries = {
        str(row.get("skill_id", "")): row
        for row in registry.get("entries", [])
        if isinstance(row, Mapping) and str(row.get("skill_id", ""))
    }
    if not invalidated:
        invalidated = sorted(
            target_id
            for target_id, entry in entries.items()
            if entry.get("graduation_status") == "revalidation_required"
            and entry.get("pending_guard_change_id") == change.get("change_id")
        )
    required_target_ids = _id_list(impact_result.get("required_target_ids"))
    required_member_ids_by_suite = _member_ids_by_suite(
        impact_result.get("required_member_ids_by_suite")
    )
    required_impact_ids = _required_impact_ids(
        required_target_ids, required_member_ids_by_suite
    )
    member_revalidation_statuses = _member_status_projection(
        entries, required_member_ids_by_suite
    )
    invalidated_member_ids = _id_list(
        impact_result.get(
            "invalidated_member_ids",
            [
                member_id
                for member_ids in required_member_ids_by_suite.values()
                for member_id in member_ids
            ],
        )
    )
    affected_target_ids = sorted(
        str(row.get("skill_id", ""))
        for row in impact_result.get("invalidated_entries", [])
        if isinstance(row, Mapping)
        and str(row.get("skill_id", ""))
        and row.get("affected") is True
    )
    status_transitions = [
        dict(row)
        for row in impact_result.get("status_transitions", [])
        if isinstance(row, Mapping)
    ]
    if not status_transitions:
        status_transitions = [
            {
                "scope_kind": "portfolio_target",
                "target_id": target_id,
                "member_id": "",
                "before_status": "unknown",
                "after_status": str(
                    entries.get(target_id, {}).get("graduation_status", "")
                ),
            }
            for target_id in invalidated
        ]
    target_statuses = {
        target_id: {
            "graduation_status": str(entries[target_id].get("graduation_status", "")),
            "pending_guard_change_id": str(entries[target_id].get("pending_guard_change_id", "")),
            "reuse_ticket_absent": entries[target_id].get("reuse_ticket") is None,
        }
        for target_id in invalidated
        if target_id in entries
    }
    receipt: dict[str, Any] = {
        "schema_version": IMPACT_RECEIPT_SCHEMA,
        "change_id": str(change.get("change_id", "")),
        "change_hash": canonical_hash(change),
        "impact_graph_hash": str(change.get("impact_graph_hash", "")),
        "changed_component_ids": _id_list(
            change.get("changed_component_ids")
        ),
        "status": "revalidation_required",
        "affected_target_ids": affected_target_ids,
        "invalidated_target_ids": invalidated,
        "required_target_ids": required_target_ids,
        "required_member_ids_by_suite": required_member_ids_by_suite,
        "required_impact_ids": required_impact_ids,
        "invalidated_member_ids": invalidated_member_ids,
        "target_statuses": target_statuses,
        "member_revalidation_statuses": member_revalidation_statuses,
        "status_transitions": sorted(
            status_transitions,
            key=lambda row: (
                str(row.get("scope_kind", "")),
                str(row.get("target_id", "")),
                str(row.get("member_id", "")),
            ),
        ),
        "registry_transaction_id": str(change.get("transaction_id", "")),
        "guard_before_hash": canonical_hash(change.get("guard_before", {})),
        "guard_after_hash": canonical_hash(change.get("guard_after", {})),
        "registry_ref": _portable_ref(
            registry_path, workspace_root, token="workspace_root"
        ),
        "registry_hash": canonical_hash(registry),
        "claim_boundary": (
            "This receipt proves that the named portfolio entries were invalidated for the exact "
            "SkillGuard model miss. It does not revalidate a target or permit evidence reuse."
        ),
    }
    receipt["receipt_id"] = f"portfolio-impact-{canonical_hash(receipt)[:24].lower()}"
    receipt["receipt_hash"] = canonical_hash(receipt)
    return receipt


def write_portfolio_impact_receipt(receipt_root: Path, receipt: Mapping[str, Any]) -> dict[str, Any]:
    root = receipt_root.resolve()
    receipt_hash = str(receipt.get("receipt_hash", ""))
    if receipt_hash != canonical_hash(
        {key: value for key, value in receipt.items() if key != "receipt_hash"}
    ):
        raise ValueError("portfolio_impact_receipt_hash_mismatch")
    receipt_path = root / "receipts" / f"{receipt_hash[:24].lower()}.json"
    if receipt_path.exists():
        existing = json.loads(receipt_path.read_text(encoding="utf-8"))
        if existing != dict(receipt):
            raise ValueError("portfolio_impact_receipt_collision")
    else:
        atomic_write_json(receipt_path, receipt)
    head: dict[str, Any] = {
        "schema_version": IMPACT_HEAD_SCHEMA,
        "receipt_id": str(receipt.get("receipt_id", "")),
        "receipt_hash": receipt_hash,
        "receipt_ref": _portable_ref(receipt_path, root, token="receipt_root"),
    }
    head["head_hash"] = canonical_hash(head)
    atomic_write_json(root / "HEAD.json", head)
    return {"receipt": dict(receipt), "head": head}


def verify_portfolio_impact_receipt(
    receipt_root: Path,
    *,
    workspace_root: Path,
    require_change_id: str,
    require_status: str,
    require_target_ids: Sequence[str],
    require_exact_target_set: bool = False,
) -> dict[str, Any]:
    root = receipt_root.resolve(strict=True)
    workspace = workspace_root.resolve(strict=True)
    blockers: list[str] = []
    try:
        head = json.loads((root / "HEAD.json").read_text(encoding="utf-8"))
        if head.get("schema_version") != IMPACT_HEAD_SCHEMA:
            raise ValueError("portfolio_impact_head_schema_mismatch")
        if head.get("head_hash") != canonical_hash(
            {key: value for key, value in head.items() if key != "head_hash"}
        ):
            raise ValueError("portfolio_impact_head_hash_mismatch")
        ref = head.get("receipt_ref", {})
        if not isinstance(ref, Mapping) or ref.get("path_token") != "receipt_root":
            raise ValueError("portfolio_impact_receipt_ref_invalid")
        receipt_path = (root / str(ref.get("relative_path", ""))).resolve(strict=True)
        receipt_path.relative_to(root)
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        receipt = {}
        blockers.append(str(exc))
    if receipt:
        if receipt.get("schema_version") != IMPACT_RECEIPT_SCHEMA:
            blockers.append("portfolio_impact_receipt_schema_mismatch")
        receipt_hash = canonical_hash(
            {key: value for key, value in receipt.items() if key != "receipt_hash"}
        )
        if receipt.get("receipt_hash") != receipt_hash or head.get("receipt_hash") != receipt_hash:
            blockers.append("portfolio_impact_receipt_hash_mismatch")
        if receipt.get("change_id") != require_change_id:
            blockers.append("portfolio_impact_change_id_mismatch")
        if receipt.get("status") != require_status:
            blockers.append("portfolio_impact_status_mismatch")
        invalidated_targets = set(_id_list(receipt.get("invalidated_target_ids")))
        required_scope_fields = {
            "required_target_ids",
            "required_member_ids_by_suite",
            "required_impact_ids",
            "invalidated_member_ids",
            "affected_target_ids",
            "impact_graph_hash",
            "changed_component_ids",
            "status_transitions",
        }
        missing_scope_fields = sorted(required_scope_fields - set(receipt))
        if missing_scope_fields:
            blockers.append(
                "portfolio_impact_current_scope_fields_missing:"
                + ",".join(missing_scope_fields)
            )
        if re.fullmatch(
            r"sha256:[0-9a-f]{64}",
            str(receipt.get("impact_graph_hash", "")),
        ) is None:
            blockers.append("portfolio_impact_graph_hash_invalid")
        changed_component_ids = _id_list(
            receipt.get("changed_component_ids")
        )
        if (
            not changed_component_ids
            or receipt.get("changed_component_ids") != changed_component_ids
        ):
            blockers.append("portfolio_impact_changed_components_invalid")
        receipt_required_targets = _id_list(receipt.get("required_target_ids"))
        receipt_required_members = _member_ids_by_suite(
            receipt.get("required_member_ids_by_suite")
        )
        derived_required_impact = set(
            _required_impact_ids(
                receipt_required_targets, receipt_required_members
            )
        )
        receipt_required_impact = set(
            _id_list(receipt.get("required_impact_ids"))
        )
        if receipt_required_impact != derived_required_impact:
            blockers.append("portfolio_impact_required_set_internal_mismatch")
        required = set(str(item) for item in require_target_ids)
        missing = sorted(required - receipt_required_impact)
        if missing:
            blockers.append("portfolio_impact_required_target_missing:" + ",".join(missing))
        if require_exact_target_set and receipt_required_impact != required:
            blockers.append(
                "portfolio_impact_target_set_mismatch:"
                + ",".join(sorted(receipt_required_impact ^ required))
            )
        required_member_ids = {
            member_id
            for member_ids in receipt_required_members.values()
            for member_id in member_ids
        }
        if set(_id_list(receipt.get("invalidated_member_ids"))) != required_member_ids:
            blockers.append("portfolio_impact_invalidated_member_set_mismatch")
        affected_targets = set(_id_list(receipt.get("affected_target_ids")))
        if not affected_targets.issubset(invalidated_targets):
            blockers.append("portfolio_impact_affected_target_set_invalid")
        transitions = receipt.get("status_transitions", [])
        if not isinstance(transitions, list):
            transitions = []
        transition_keys = {
            (
                str(row.get("scope_kind", "")),
                str(row.get("target_id", "")),
                str(row.get("member_id", "")),
            )
            for row in transitions
            if isinstance(row, Mapping)
            and row.get("after_status") == "revalidation_required"
        }
        required_transition_keys = {
            ("portfolio_target", target_id, "")
            for target_id in invalidated_targets
        } | {
            ("suite_member", suite_id, member_id)
            for suite_id, member_ids in receipt_required_members.items()
            for member_id in member_ids
        }
        if not required_transition_keys.issubset(transition_keys):
            blockers.append("portfolio_impact_status_transitions_incomplete")
        registry_ref = receipt.get("registry_ref", {})
        try:
            if not isinstance(registry_ref, Mapping) or registry_ref.get("path_token") != "workspace_root":
                raise ValueError("portfolio_impact_registry_ref_invalid")
            registry_path = (workspace / str(registry_ref.get("relative_path", ""))).resolve(strict=True)
            registry_path.relative_to(workspace)
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            registry = {}
            blockers.append(str(exc))
        if registry:
            if canonical_hash(registry) != receipt.get("registry_hash"):
                blockers.append("portfolio_impact_registry_hash_mismatch")
            entries = {
                str(row.get("skill_id", "")): row
                for row in registry.get("entries", [])
                if isinstance(row, Mapping)
            }
            target_statuses = receipt.get("target_statuses", {})
            if not isinstance(target_statuses, Mapping):
                target_statuses = {}
                blockers.append("portfolio_impact_target_statuses_invalid")
            for target_id in sorted(invalidated_targets):
                entry = entries.get(target_id)
                if not isinstance(entry, Mapping):
                    blockers.append(f"portfolio_impact_registry_target_missing:{target_id}")
                    continue
                if entry.get("graduation_status") != "revalidation_required":
                    blockers.append(f"portfolio_impact_registry_status_mismatch:{target_id}")
                if entry.get("pending_guard_change_id") != require_change_id:
                    blockers.append(f"portfolio_impact_registry_change_mismatch:{target_id}")
                if entry.get("reuse_ticket") is not None:
                    blockers.append(f"portfolio_impact_reuse_not_cleared:{target_id}")
                projected = target_statuses.get(target_id)
                if not isinstance(projected, Mapping):
                    blockers.append(
                        f"portfolio_impact_target_status_missing:{target_id}"
                    )
                elif (
                    projected.get("graduation_status")
                    != entry.get("graduation_status")
                    or projected.get("pending_guard_change_id")
                    != entry.get("pending_guard_change_id")
                    or projected.get("reuse_ticket_absent")
                    is not (entry.get("reuse_ticket") is None)
                ):
                    blockers.append(
                        f"portfolio_impact_target_status_mismatch:{target_id}"
                    )
            receipt_member_statuses = receipt.get(
                "member_revalidation_statuses", {}
            )
            if not isinstance(receipt_member_statuses, Mapping):
                receipt_member_statuses = {}
                blockers.append("portfolio_impact_member_statuses_invalid")
            for suite_id, member_ids in sorted(receipt_required_members.items()):
                suite = entries.get(suite_id)
                if not isinstance(suite, Mapping):
                    blockers.append(
                        f"portfolio_impact_registry_member_suite_missing:{suite_id}"
                    )
                    continue
                if suite.get("graduation_status") != "revalidation_required":
                    blockers.append(
                        f"portfolio_impact_registry_status_mismatch:{suite_id}"
                    )
                if suite.get("pending_guard_change_id") != require_change_id:
                    blockers.append(
                        f"portfolio_impact_registry_change_mismatch:{suite_id}"
                    )
                if suite.get("reuse_ticket") is not None:
                    blockers.append(
                        f"portfolio_impact_reuse_not_cleared:{suite_id}"
                    )
                registry_member_statuses = suite.get(
                    "member_revalidation_statuses", {}
                )
                receipt_suite_statuses = receipt_member_statuses.get(suite_id, {})
                if not isinstance(registry_member_statuses, Mapping):
                    registry_member_statuses = {}
                if not isinstance(receipt_suite_statuses, Mapping):
                    receipt_suite_statuses = {}
                for member_id in member_ids:
                    expected_member_status = {
                        "graduation_status": "revalidation_required",
                        "pending_guard_change_id": require_change_id,
                        "reuse_ticket_absent": True,
                    }
                    if registry_member_statuses.get(member_id) != expected_member_status:
                        blockers.append(
                            f"portfolio_impact_registry_member_status_mismatch:{suite_id}:{member_id}"
                        )
                    if receipt_suite_statuses.get(member_id) != expected_member_status:
                        blockers.append(
                            f"portfolio_impact_receipt_member_status_mismatch:{suite_id}:{member_id}"
                        )
            transaction_id = str(receipt.get("registry_transaction_id", ""))
            matching_transactions = [
                row
                for row in registry.get("transaction_history", [])
                if isinstance(row, Mapping)
                and row.get("transaction_id") == transaction_id
                and row.get("mutation_kind") == "guard_change"
            ]
            if len(matching_transactions) != 1:
                blockers.append("portfolio_impact_registry_transaction_mismatch")
    return {
        "artifact_type": "skillguard_portfolio_impact_receipt_verification",
        "status": "passed" if not blockers else "blocked",
        "change_id": require_change_id,
        "required_target_ids": sorted(set(require_target_ids)),
        "required_impact_ids": sorted(set(require_target_ids)),
        "receipt_required_target_ids": (
            receipt_required_targets if receipt else []
        ),
        "receipt_required_member_ids_by_suite": (
            receipt_required_members if receipt else {}
        ),
        "invalidated_target_ids": (
            sorted(invalidated_targets) if receipt else []
        ),
        "blockers": blockers,
    }


__all__ = [
    "IMPACT_HEAD_SCHEMA",
    "IMPACT_RECEIPT_SCHEMA",
    "build_portfolio_impact_receipt",
    "verify_portfolio_impact_receipt",
    "write_portfolio_impact_receipt",
]
