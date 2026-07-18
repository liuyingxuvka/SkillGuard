"""Immutable evidence receipts and derived, affected-only freshness."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contract_compiler import canonical_hash, canonical_json_bytes
from .contract_schema import EVIDENCE_CLASSES, RECEIPT_SCHEMA, SchemaFinding, validate_runtime_payload
from .execution_records import filesystem_path
from .run_store import append_event, load_contract_snapshot, load_run, utc_now


FORBIDDEN_EVIDENCE_AUTHORITY_FIELDS = frozenset(
    {"pass", "passed", "current", "status", "authoritative_status", "fresh"}
)
RECEIPT_DECISIONS = frozenset({"passed", "failed", "blocked"})
FINGERPRINT_POLICIES = frozenset({"raw", "semantic"})
SAFE_ID = re.compile(r"^[A-Za-z0-9_.:-]+$")


@dataclass(frozen=True)
class ReceiptError(ValueError):
    code: str
    message: str
    target_id: str = ""

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


@dataclass(frozen=True)
class FreshnessResult:
    current: bool
    status: str
    reasons: tuple[str, ...]
    affected_keys: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "current": self.current,
            "status": self.status,
            "reasons": list(self.reasons),
            "affected_keys": list(self.affected_keys),
            "claim_boundary": "Currentness is derived only for fingerprints declared by this receipt.",
        }


def _semantic_normalize(value: object) -> object:
    if isinstance(value, str):
        return " ".join(value.split())
    if isinstance(value, Mapping):
        return {str(key): _semantic_normalize(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_semantic_normalize(item) for item in value]
    return value


def _raw_digest(value: object) -> str:
    if isinstance(value, bytes):
        content = value
    elif isinstance(value, str):
        content = value.encode("utf-8")
    else:
        content = canonical_json_bytes(value)
    return hashlib.sha256(content).hexdigest().upper()


def fingerprint_value(
    value: object,
    *,
    policy: str = "raw",
    semantic_value: object | None = None,
) -> dict[str, str]:
    if policy not in FINGERPRINT_POLICIES:
        raise ReceiptError("unknown_fingerprint_policy", policy)
    semantic_source = value if semantic_value is None else semantic_value
    return {
        "algorithm": "sha256",
        "policy": policy,
        "raw": _raw_digest(value),
        "semantic": _raw_digest(_semantic_normalize(semantic_source)),
    }


def build_action_witness(
    *,
    witness_kind: str,
    target_id: str,
    input_value: object,
    output_value: object,
    executor_id: str,
    limitations: Sequence[str] = (),
) -> dict[str, Any]:
    if witness_kind not in {"tool", "api", "browser", "desktop", "ui_launch", "ui_interaction"}:
        raise ReceiptError("witness_kind_invalid", witness_kind, target_id)
    if not target_id or not executor_id:
        raise ReceiptError("witness_identity_incomplete", "target_id and executor_id are required", target_id)
    return {
        "witness_kind": witness_kind,
        "target_id": target_id,
        "executor_id": executor_id,
        "input_fingerprint": _raw_digest(input_value),
        "output_fingerprint": _raw_digest(output_value),
        "limitations": list(limitations),
        "claim_boundary": "This is an action witness, not an independent pass or quality judgment.",
    }


def _validate_fingerprints(values: Mapping[str, Any]) -> tuple[SchemaFinding, ...]:
    findings: list[SchemaFinding] = []
    for key, value in values.items():
        if not isinstance(key, str) or not key:
            findings.append(SchemaFinding("fingerprint_key_invalid", "$.input_fingerprints", str(key)))
            continue
        if not isinstance(value, Mapping):
            findings.append(SchemaFinding("fingerprint_not_object", f"$.input_fingerprints.{key}", key))
            continue
        policy = str(value.get("policy", ""))
        if policy not in FINGERPRINT_POLICIES:
            findings.append(SchemaFinding("fingerprint_policy_invalid", f"$.input_fingerprints.{key}", policy))
        for field in ("raw", "semantic"):
            if not str(value.get(field, "")):
                findings.append(SchemaFinding("fingerprint_digest_missing", f"$.input_fingerprints.{key}.{field}", key))
    return tuple(findings)


def _receipts_root(run_root: Path) -> Path:
    return filesystem_path(run_root / "receipts")


def load_receipts(run_root: Path) -> tuple[Mapping[str, Any], ...]:
    root = _receipts_root(run_root)
    if not root.is_dir():
        return ()
    rows: list[Mapping[str, Any]] = []
    for path in sorted(root.glob("receipt-*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ReceiptError("receipt_unreadable", type(exc).__name__, path.name) from exc
        if not isinstance(payload, Mapping):
            raise ReceiptError("receipt_not_object", path.name, path.name)
        findings = validate_runtime_payload(payload, RECEIPT_SCHEMA)
        if findings:
            raise ReceiptError(findings[0].code, findings[0].message, path.name)
        unsigned = dict(payload)
        stored_hash = str(unsigned.pop("receipt_hash", ""))
        if not stored_hash or stored_hash != canonical_hash(unsigned):
            raise ReceiptError("receipt_hash_mismatch", "immutable receipt content changed", path.name)
        rows.append(payload)
    return tuple(sorted(rows, key=lambda row: int(row.get("issued_sequence", 0))))


def load_receipt(run_root: Path, receipt_id: str) -> Mapping[str, Any]:
    if not SAFE_ID.fullmatch(receipt_id):
        raise ReceiptError("receipt_id_invalid", receipt_id, receipt_id)
    matches = [row for row in load_receipts(run_root) if row.get("receipt_id") == receipt_id]
    if len(matches) != 1:
        raise ReceiptError("receipt_not_found", receipt_id, receipt_id)
    return matches[0]


def _validate_class_evidence(evidence_class: str, evidence: Mapping[str, Any]) -> None:
    if evidence_class == "hard":
        if not str(evidence.get("proof_kind", "")) or not str(evidence.get("proof_fingerprint", "")):
            raise ReceiptError("hard_evidence_incomplete", "proof_kind and proof_fingerprint are required")
    elif evidence_class == "witnessed":
        required = ("witness_kind", "target_id", "input_fingerprint", "output_fingerprint")
        missing = [key for key in required if not str(evidence.get(key, ""))]
        if missing:
            raise ReceiptError("witness_evidence_incomplete", ",".join(missing))
    elif evidence_class == "judged":
        required = ("rubric_id", "rubric_version", "evaluator_id", "input_fingerprint", "conclusion")
        missing = [key for key in required if not str(evidence.get(key, ""))]
        if missing:
            raise ReceiptError("judged_evidence_incomplete", ",".join(missing))
        limitations = evidence.get("limitations")
        if not isinstance(limitations, list) or not limitations:
            raise ReceiptError("judged_limitations_missing", "judged evidence must disclose limitations")
        if bool(evidence.get("self_review")) and not str(evidence.get("confidence_boundary", "")):
            raise ReceiptError("self_review_boundary_missing", "self-review needs a confidence boundary")


def _evidence_subject_id(evidence_class: str, evidence: Mapping[str, Any]) -> str:
    declared_subject = str(evidence.get("evidence_subject_id", ""))
    if declared_subject:
        return declared_subject
    if evidence_class == "hard":
        if evidence.get("check_id"):
            return f"check:{evidence['check_id']}"
        if evidence.get("artifact_id"):
            return f"artifact:{evidence['artifact_id']}"
        return f"hard:{evidence.get('proof_kind', 'unspecified')}"
    if evidence_class == "witnessed":
        return f"witness:{evidence.get('witness_kind', '')}:{evidence.get('target_id', '')}"
    return f"rubric:{evidence.get('rubric_id', '')}"


def issue_receipt(
    run_root: Path,
    *,
    step_id: str,
    evidence_class: str,
    evidence: Mapping[str, Any],
    decision: str,
    verifier_id: str,
    input_fingerprints: Mapping[str, Mapping[str, str]],
    artifact_record_ids: Sequence[str] = (),
    consumed_child_receipt_ids: Sequence[str] = (),
    owner_evidence_root: Path | None = None,
) -> Mapping[str, Any]:
    if evidence_class not in EVIDENCE_CLASSES:
        raise ReceiptError("evidence_class_invalid", evidence_class, step_id)
    if decision not in RECEIPT_DECISIONS:
        raise ReceiptError("receipt_decision_invalid", decision, step_id)
    forbidden = FORBIDDEN_EVIDENCE_AUTHORITY_FIELDS & set(evidence)
    if forbidden:
        raise ReceiptError("caller_authored_receipt_authority", ",".join(sorted(forbidden)), step_id)
    if not verifier_id.strip():
        raise ReceiptError("verifier_id_missing", "verifier identity is required", step_id)
    _validate_class_evidence(evidence_class, evidence)
    fingerprint_findings = _validate_fingerprints(input_fingerprints)
    if fingerprint_findings:
        raise ReceiptError(fingerprint_findings[0].code, fingerprint_findings[0].message, step_id)
    run = load_run(run_root)
    contract = load_contract_snapshot(run_root)
    declared_steps = {str(row.get("step_id", "")) for row in contract.get("steps", []) if isinstance(row, Mapping)}
    if step_id not in declared_steps:
        raise ReceiptError("receipt_step_unknown", step_id, step_id)
    if evidence_class == "judged":
        rubric_index = {
            str(row.get("rubric_id", "")): row
            for row in contract.get("judgment_rubrics", [])
            if isinstance(row, Mapping) and row.get("rubric_id")
        }
        rubric_id = str(evidence.get("rubric_id", ""))
        rubric = rubric_index.get(rubric_id)
        if rubric is None:
            raise ReceiptError("judgment_rubric_not_declared", rubric_id, step_id)
        if str(rubric.get("version", "")) != str(evidence.get("rubric_version", "")):
            raise ReceiptError("judgment_rubric_version_mismatch", rubric_id, step_id)
    if artifact_record_ids:
        from .artifact_validators import ArtifactValidationError, load_artifact_record

        for artifact_record_id in artifact_record_ids:
            try:
                artifact_record = load_artifact_record(run_root, str(artifact_record_id))
            except ArtifactValidationError as exc:
                raise ReceiptError("receipt_artifact_invalid", exc.code, str(artifact_record_id)) from exc
            if artifact_record.get("producer_step_id") != step_id:
                raise ReceiptError("receipt_artifact_wrong_step", str(artifact_record_id), step_id)
            if artifact_record.get("status") != "passed":
                raise ReceiptError("receipt_artifact_not_passed", str(artifact_record_id), step_id)
    if evidence_class == "hard" and evidence.get("proof_kind") == "native_check":
        raise ReceiptError(
            "legacy_native_check_evidence_rejected",
            "current hard evidence must project a verified owner receipt",
            step_id,
        )
    if evidence_class == "hard" and evidence.get("proof_kind") == "owner_receipt_projection":
        from .check_runner import (
            CheckRunnerError,
            load_check_result,
            load_owner_receipt_from_projection,
        )

        check_record_id = str(evidence.get("check_record_id", ""))
        if not check_record_id:
            raise ReceiptError("hard_check_record_missing", "native-check evidence needs check_record_id", step_id)
        try:
            check_record = load_check_result(run_root, check_record_id)
        except CheckRunnerError as exc:
            raise ReceiptError("hard_check_record_invalid", exc.code, check_record_id) from exc
        if check_record.get("run_id") != run.get("run_id") or check_record.get("contract_hash") != run.get("contract_hash"):
            raise ReceiptError("hard_check_record_wrong_run", check_record_id, step_id)
        if (
            check_record.get("check_manifest_hash")
            != run.get("check_manifest_hash")
            or check_record.get("check_declarations_hash")
            != run.get("check_declarations_hash")
            or check_record.get("check_manifest_hash")
            != evidence.get("check_manifest_hash")
            or check_record.get("check_declarations_hash")
            != evidence.get("check_declarations_hash")
            or check_record.get("declared_check_hash")
            != evidence.get("declared_check_hash")
        ):
            raise ReceiptError(
                "hard_check_manifest_binding_mismatch",
                check_record_id,
                step_id,
            )
        if check_record.get("step_id") != step_id:
            raise ReceiptError("hard_check_record_wrong_step", check_record_id, step_id)
        if check_record.get("check_id") != evidence.get("check_id"):
            raise ReceiptError("hard_check_record_wrong_check", check_record_id, step_id)
        if check_record.get("status") != "passed":
            raise ReceiptError("hard_check_record_not_passed", check_record_id, step_id)
        if check_record.get("execution_disposition") not in {
            "executed_terminal_success",
            "reused_terminal_success",
        }:
            raise ReceiptError(
                "hard_check_execution_disposition_invalid",
                check_record_id,
                step_id,
            )
        if check_record.get("proof_fingerprint") != evidence.get("proof_fingerprint"):
            raise ReceiptError("hard_check_fingerprint_mismatch", check_record_id, step_id)
        if check_record.get("record_hash") != evidence.get("check_record_hash"):
            raise ReceiptError("hard_check_record_hash_mismatch", check_record_id, step_id)
        for field in (
            "maintenance_unit_id",
            "member_skill_id",
            "evidence_subject_id",
            "semantic_check_id",
            "execution_owner_id",
            "execution_key",
            "projection_declaration_hash",
            "owner_receipt_id",
            "owner_receipt_hash",
            "owner_receipt_ref",
        ):
            if check_record.get(field) != evidence.get(field):
                raise ReceiptError(
                    "hard_check_owner_projection_mismatch",
                    f"{check_record_id}:{field}",
                    step_id,
                )
        if (
            check_record.get("maintenance_unit_id")
            != run.get("maintenance_unit_id")
            or check_record.get("member_skill_id") != run.get("member_skill_id")
        ):
            raise ReceiptError(
                "hard_check_maintenance_identity_mismatch",
                check_record_id,
                step_id,
            )
        if owner_evidence_root is None:
            raise ReceiptError(
                "hard_check_owner_evidence_root_missing",
                check_record_id,
                step_id,
            )
        try:
            owner_receipt = load_owner_receipt_from_projection(
                owner_evidence_root.resolve(),
                check_record,
            )
        except CheckRunnerError as exc:
            raise ReceiptError(
                "hard_check_owner_receipt_invalid",
                exc.code,
                check_record_id,
            ) from exc
        if (
            owner_receipt.get("receipt_id") != evidence.get("owner_receipt_id")
            or owner_receipt.get("receipt_hash")
            != evidence.get("owner_receipt_hash")
        ):
            raise ReceiptError(
                "hard_check_owner_receipt_mismatch",
                check_record_id,
                step_id,
            )
    existing = load_receipts(run_root)
    sequence = len(existing) + 1
    subject_id = _evidence_subject_id(evidence_class, evidence)
    previous = next(
        (
            row
            for row in reversed(existing)
            if row.get("step_id") == step_id
            and row.get("evidence_class") == evidence_class
            and row.get("subject_id") == subject_id
        ),
        None,
    )
    receipt: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA,
        "run_id": str(run["run_id"]),
        "maintenance_unit_id": str(run["maintenance_unit_id"]),
        "member_skill_id": str(run["member_skill_id"]),
        "evidence_subject_id": subject_id,
        "semantic_check_id": str(
            evidence.get("semantic_check_id", step_id)
        ),
        "step_id": step_id,
        "evidence_class": evidence_class,
        "subject_id": subject_id,
        "status": decision,
        "verifier_id": verifier_id,
        "contract_hash": str(run["contract_hash"]),
        "issued_sequence": sequence,
        "created_at": utc_now(),
        "input_fingerprints": {key: dict(value) for key, value in sorted(input_fingerprints.items())},
        "artifact_record_ids": sorted(dict.fromkeys(str(item) for item in artifact_record_ids)),
        "consumed_child_receipt_ids": sorted(
            dict.fromkeys(str(item) for item in consumed_child_receipt_ids)
        ),
        "evidence": dict(evidence),
        "supersedes_receipt_id": str(previous.get("receipt_id", "")) if previous else "",
        "claim_boundary": (
            f"This {evidence_class} receipt preserves only {evidence_class} authority; "
            "currentness and parent closure remain derived separately."
        ),
    }
    receipt_id_source = dict(receipt)
    receipt_id_source.pop("created_at", None)
    receipt["receipt_id"] = f"receipt-{canonical_hash(receipt_id_source)[:24].lower()}"
    receipt["receipt_hash"] = canonical_hash(receipt)
    findings = validate_runtime_payload(receipt, RECEIPT_SCHEMA)
    if findings:
        raise ReceiptError(findings[0].code, findings[0].message, step_id)
    root = _receipts_root(run_root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{receipt['receipt_id']}.json"
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError as exc:
        raise ReceiptError("receipt_immutable_collision", path.name, str(receipt["receipt_id"])) from exc
    try:
        os.write(descriptor, canonical_json_bytes(receipt))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    append_event(
        run_root,
        "receipt_issued",
        {
            "step_id": step_id,
            "receipt_id": receipt["receipt_id"],
            "evidence_class": evidence_class,
            "verification_status": decision,
            "receipt_hash": receipt["receipt_hash"],
        },
    )
    return receipt


def derive_freshness(
    receipt: Mapping[str, Any],
    current_fingerprints: Mapping[str, object],
    *,
    receipt_roots: Sequence[Path] = (),
) -> FreshnessResult:
    reasons: list[str] = []
    affected: list[str] = []
    expected_inputs = receipt.get("input_fingerprints", {})
    if not isinstance(expected_inputs, Mapping):
        return FreshnessResult(False, "stale", ("receipt_fingerprints_invalid",), ())
    for key, expected in expected_inputs.items():
        if not isinstance(expected, Mapping):
            reasons.append(f"invalid_fingerprint:{key}")
            affected.append(str(key))
            continue
        if key not in current_fingerprints:
            reasons.append(f"missing_current_fingerprint:{key}")
            affected.append(str(key))
            continue
        current = current_fingerprints[key]
        policy = str(expected.get("policy", "raw"))
        if isinstance(current, Mapping) and {"raw", "semantic"}.issubset(current):
            actual = current
        else:
            actual = fingerprint_value(current, policy=policy)
        if str(actual.get(policy, "")) != str(expected.get(policy, "")):
            reasons.append(f"fingerprint_changed:{key}:{policy}")
            affected.append(str(key))

    all_receipts: dict[str, Mapping[str, Any]] = {}
    latest_by_subject: dict[tuple[str, str, str, str, str], Mapping[str, Any]] = {}
    for root in receipt_roots:
        for row in load_receipts(root):
            receipt_id = str(row.get("receipt_id", ""))
            all_receipts[receipt_id] = row
            subject = (
                str(row.get("maintenance_unit_id", "")),
                str(row.get("run_id", "")),
                str(row.get("step_id", "")),
                str(row.get("evidence_class", "")),
                str(row.get("subject_id", "")),
            )
            latest_by_subject[subject] = row
    for child_id in receipt.get("consumed_child_receipt_ids", []):
        child = all_receipts.get(str(child_id))
        if child is None:
            reasons.append(f"consumed_child_missing:{child_id}")
            affected.append(f"child:{child_id}")
            continue
        if child.get("maintenance_unit_id") != receipt.get(
            "maintenance_unit_id"
        ):
            reasons.append(f"consumed_child_foreign_unit:{child_id}")
            affected.append(f"child:{child_id}")
            continue
        subject = (
            str(child.get("maintenance_unit_id", "")),
            str(child.get("run_id", "")),
            str(child.get("step_id", "")),
            str(child.get("evidence_class", "")),
            str(child.get("subject_id", "")),
        )
        latest = latest_by_subject.get(subject)
        if latest and latest.get("receipt_id") != child_id:
            reasons.append(f"consumed_child_superseded:{child_id}")
            affected.append(f"child:{child_id}")
        if child.get("status") != "passed":
            reasons.append(f"consumed_child_not_passed:{child_id}")
            affected.append(f"child:{child_id}")
    current = not reasons and receipt.get("status") == "passed"
    if receipt.get("status") != "passed":
        reasons.append(f"receipt_status:{receipt.get('status', 'missing')}")
    return FreshnessResult(
        current,
        "current" if current else "stale",
        tuple(dict.fromkeys(reasons)),
        tuple(dict.fromkeys(affected)),
    )
