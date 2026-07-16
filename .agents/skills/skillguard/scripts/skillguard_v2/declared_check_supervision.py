"""Fixed, target-neutral supervision of target-declared checks.

SkillGuard owns only this equality and completeness boundary.  The target
skill owns each check's domain meaning, implementation, oracle, fixtures, and
claim boundary.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


TERMINAL_DISPOSITIONS = frozenset(
    {
        "passed",
        "failed",
        "skipped",
        "timeout",
        "not_run",
        "stale",
        "cleanup_unconfirmed",
        "cancelled",
        "blocked",
    }
)
NON_TERMINAL_DISPOSITIONS = frozenset({"pending", "claimed", "running"})
ALL_DISPOSITIONS = TERMINAL_DISPOSITIONS | NON_TERMINAL_DISPOSITIONS


@dataclass(frozen=True)
class DeclaredCheckError(ValueError):
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def _required_text(value: object, code: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise DeclaredCheckError(code, "non-empty text required")
    return text


def freeze_declared_check_inventory(
    declarations: Sequence[Mapping[str, Any]],
    *,
    required_check_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Freeze one exact current inventory with exactly one owner per check."""

    required = (
        {str(item) for item in required_check_ids}
        if required_check_ids is not None
        else None
    )
    rows: list[dict[str, Any]] = []
    seen_checks: set[str] = set()
    seen_owner_pairs: set[tuple[str, str]] = set()
    for declaration in declarations:
        check_id = _required_text(
            declaration.get("check_id"), "declared_check_id_missing"
        )
        if required is not None and check_id not in required:
            continue
        if check_id in seen_checks:
            raise DeclaredCheckError("declared_check_duplicate", check_id)
        owner_id = _required_text(
            declaration.get("execution_owner_id"),
            "declared_check_execution_owner_missing",
        )
        owner_pair = (check_id, owner_id)
        if owner_pair in seen_owner_pairs:
            raise DeclaredCheckError("declared_check_owner_duplicate", check_id)
        seen_checks.add(check_id)
        seen_owner_pairs.add(owner_pair)
        dependencies_value = declaration.get("depends_on_check_ids", [])
        if isinstance(dependencies_value, (str, bytes)) or not isinstance(
            dependencies_value, Sequence
        ):
            raise DeclaredCheckError(
                "declared_check_dependencies_invalid", check_id
            )
        dependencies = [str(item) for item in dependencies_value]
        if any(not item for item in dependencies) or len(dependencies) != len(
            set(dependencies)
        ):
            raise DeclaredCheckError(
                "declared_check_dependencies_invalid", check_id
            )
        rows.append(
            {
                "check_id": check_id,
                "execution_owner_id": owner_id,
                "evidence_domain_id": str(
                    declaration.get("evidence_domain_id", "")
                ),
                "depends_on_check_ids": sorted(dependencies),
                "required": True,
            }
        )
    if required is not None:
        missing = sorted(required - seen_checks)
        if missing:
            raise DeclaredCheckError(
                "declared_required_check_missing", ",".join(missing)
            )
    if not rows:
        raise DeclaredCheckError(
            "declared_check_inventory_empty", "at least one check is required"
        )
    known = {row["check_id"] for row in rows}
    for row in rows:
        unknown = sorted(set(row["depends_on_check_ids"]) - known)
        if unknown:
            raise DeclaredCheckError(
                "declared_check_dependency_unknown",
                f"{row['check_id']}:{','.join(unknown)}",
            )
    rows.sort(key=lambda row: row["check_id"])
    payload: dict[str, Any] = {
        "schema_version": "skillguard.declared_check_inventory.current",
        "checks": rows,
    }
    payload["inventory_hash"] = _canonical_hash(payload)
    return payload


def reconcile_declared_check_results(
    inventory: Mapping[str, Any],
    results: Sequence[Mapping[str, Any]],
    *,
    request_fingerprint: str,
) -> dict[str, Any]:
    """Require one visible current terminal disposition per declared check."""

    fingerprint = _required_text(
        request_fingerprint, "declared_check_request_fingerprint_missing"
    )
    declarations = inventory.get("checks", [])
    if isinstance(declarations, (str, bytes)) or not isinstance(
        declarations, Sequence
    ):
        raise DeclaredCheckError(
            "declared_check_inventory_invalid", "checks must be an array"
        )
    expected = {
        str(row.get("check_id", "")): row
        for row in declarations
        if isinstance(row, Mapping)
    }
    if not expected or any(not key for key in expected):
        raise DeclaredCheckError(
            "declared_check_inventory_invalid", "non-empty check ids required"
        )
    indexed: dict[str, list[Mapping[str, Any]]] = {}
    blockers: list[str] = []
    for result in results:
        check_id = str(result.get("check_id", ""))
        if check_id not in expected:
            blockers.append(f"undeclared_check_result:{check_id or 'missing'}")
            continue
        indexed.setdefault(check_id, []).append(result)

    resolved: list[dict[str, Any]] = []
    unresolved: list[str] = []
    for check_id in sorted(expected):
        declaration = expected[check_id]
        candidates = indexed.get(check_id, [])
        if len(candidates) != 1:
            code = (
                "declared_check_not_run"
                if not candidates
                else "declared_check_duplicate_execution"
            )
            blockers.append(f"{code}:{check_id}")
            unresolved.append(check_id)
            resolved.append(
                {
                    "check_id": check_id,
                    "execution_owner_id": str(
                        declaration.get("execution_owner_id", "")
                    ),
                    "disposition": "not_run" if not candidates else "blocked",
                    "current": False,
                    "receipt_id": "",
                    "receipt_hash": "",
                }
            )
            continue
        result = candidates[0]
        owner_id = str(result.get("execution_owner_id", ""))
        if owner_id != declaration.get("execution_owner_id"):
            blockers.append(f"declared_check_owner_mismatch:{check_id}")
        if str(result.get("request_fingerprint", "")) != fingerprint:
            blockers.append(f"declared_check_request_mismatch:{check_id}")
        disposition = str(result.get("disposition", ""))
        if disposition not in ALL_DISPOSITIONS:
            blockers.append(f"declared_check_disposition_invalid:{check_id}")
        elif disposition in NON_TERMINAL_DISPOSITIONS:
            blockers.append(f"declared_check_not_terminal:{check_id}:{disposition}")
        elif disposition != "passed":
            blockers.append(f"declared_check_{disposition}:{check_id}")
        if result.get("current") is not True:
            blockers.append(f"declared_check_stale:{check_id}")
        receipt_id = str(result.get("receipt_id", ""))
        receipt_hash = str(result.get("receipt_hash", ""))
        if not receipt_id or len(receipt_hash) != 64:
            blockers.append(f"declared_check_receipt_identity_missing:{check_id}")
        check_blocked = any(
            blocker.endswith(f":{check_id}")
            or f":{check_id}:" in blocker
            for blocker in blockers
        )
        if check_blocked:
            unresolved.append(check_id)
        resolved.append(
            {
                "check_id": check_id,
                "execution_owner_id": owner_id,
                "disposition": disposition or "blocked",
                "current": result.get("current") is True,
                "receipt_id": receipt_id,
                "receipt_hash": receipt_hash,
            }
        )
    blockers = sorted(dict.fromkeys(blockers))
    payload: dict[str, Any] = {
        "schema_version": "skillguard.declared_check_reconciliation.current",
        "inventory_hash": str(inventory.get("inventory_hash", "")),
        "request_fingerprint": fingerprint,
        "check_results": resolved,
        "unresolved_check_ids": sorted(set(unresolved)),
        "blockers": blockers,
        "status": "passed" if not blockers else "blocked",
    }
    payload["reconciliation_hash"] = _canonical_hash(payload)
    return payload
