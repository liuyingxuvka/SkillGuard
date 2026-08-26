"""Read-only functional capability closure and source-sync audits.

This module deliberately sits beside the executable contract runtime.  The
runtime contract owns route execution and target semantics; this module only
checks that a target has declared a complete user-outcome path and that the
target-owned evidence is current enough for the requested claim scope.

There is no compatibility reader or automatic upgrade path here.  A stale or
ambiguous current identity is reported as a gap and must be directly rewritten
at the target's current schema before a new audit can pass.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .check_runner import (
    CheckRunnerError,
    check_toolchain_identity,
    inspect_current_owner_input_projection,
    _installed_runtime_input_component,
    load_owner_receipt_from_ref,
)
from .contract_compiler import canonical_hash, wire_hash
from .target_inputs import (
    TargetInputError,
    fingerprint_target_input_roles,
    fingerprint_target_inputs,
)
from .surface_inventory import (
    validate_full_surface_inventory,
    validate_surface_inventory,
)

FUNCTIONAL_CLOSURE_SCHEMA = "skillguard.functional_closure.current"
FUNCTIONAL_EVIDENCE_RECEIPT_REF_SCHEMA = (
    "skillguard.functional_evidence_receipt_ref.current"
)
CHECK_EXECUTION_HEAD_SCHEMA = "skillguard.check_execution_head.current"
PORTFOLIO_REGISTRY_SCHEMA = "skillguard.portfolio_registry.v1"

CLAIM_SCOPES = ("routine", "functional", "release", "highest-quality")
STAGE_ORDER = ("trigger", "intake", "route", "execute", "produce", "validate", "recover", "terminal")
REQUIRED_STAGE_ROLES = ("trigger", "intake", "route", "execute", "produce", "validate", "terminal")
EVIDENCE_DEPTH_ORDER = {
    "declaration": 0,
    "static": 1,
    "fixture": 2,
    "simulated_e2e": 3,
    "real_e2e": 4,
    "production_observed": 5,
}
QUALITY_ORDER = {"none": 0, "deterministic": 1, "human": 2, "domain_expert": 3}
PASS_RESULTS = frozenset({"pass"})
NON_TERMINAL_RESULTS = frozenset({"fail", "blocked", "skipped", "not_run"})
WIRE_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
NATIVE_HASH_RE = re.compile(r"^[A-F0-9]{64}$")
RECEIPT_REF_REQUIRED_FIELDS = frozenset(
    {
        "schema_version",
        "document_ref",
        "maintenance_unit_id",
        "member_skill_id",
        "check_id",
        "semantic_check_id",
        "execution_owner_id",
        "request_fingerprint",
        "target_input_paths",
        "target_input_roles",
        "check_manifest_hash",
        "projection_declaration_hash",
        "execution_key",
        "owner_declaration_hash",
        "owner_input_projection_hash",
        "input_components",
        "dependency_receipts",
        "target_input_fingerprint",
        "target_input_role_fingerprints",
        "toolchain_fingerprint",
        "execution_environment_fingerprint",
        "impact_policy_id",
        "status",
        "cleanup_confirmed",
        "receipt_id",
        "receipt_hash",
    }
)
RECEIPT_FIELD_MISSING_CODES = {
    "document_ref": "evidence-receipt-document-ref-missing",
    "maintenance_unit_id": "evidence-receipt-unit-missing",
    "member_skill_id": "evidence-receipt-member-missing",
    "check_id": "evidence-receipt-check-missing",
    "semantic_check_id": "evidence-receipt-check-missing",
    "execution_owner_id": "evidence-receipt-owner-missing",
    "request_fingerprint": "evidence-receipt-request-missing",
    "target_input_paths": "evidence-receipt-input-missing",
    "target_input_roles": "evidence-receipt-input-missing",
    "check_manifest_hash": "evidence-receipt-manifest-hash-missing",
    "projection_declaration_hash": "evidence-receipt-check-missing",
    "execution_key": "evidence-receipt-execution-key-missing",
    "owner_declaration_hash": "evidence-receipt-owner-missing",
    "owner_input_projection_hash": "evidence-receipt-input-missing",
    "input_components": "evidence-receipt-input-missing",
    "dependency_receipts": "evidence-receipt-dependency-missing",
    "target_input_fingerprint": "evidence-receipt-input-missing",
    "target_input_role_fingerprints": "evidence-receipt-input-missing",
    "toolchain_fingerprint": "evidence-receipt-toolchain-missing",
    "execution_environment_fingerprint": "evidence-receipt-environment-missing",
    "impact_policy_id": "evidence-receipt-impact-policy-missing",
    "status": "evidence-receipt-status-missing",
    "cleanup_confirmed": "evidence-receipt-cleanup-missing",
    "receipt_id": "evidence-receipt-id-missing",
    "receipt_hash": "evidence-receipt-hash-missing",
}
SOURCE_FILES = (
    "SKILL.md",
    ".skillguard/contract-source.json",
    ".skillguard/compiled-contract.json",
    ".skillguard/check-manifest.json",
    ".skillguard/functional-closure.json",
    ".skillguard/surface-inventory.json",
)


@dataclass(frozen=True)
class CapabilityFinding:
    code: str
    path: str
    message: str
    affected_ids: tuple[str, ...] = ()
    repair_action: str = "Rewrite the current target record and rerun the affected audit."

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "path": self.path,
            "message": self.message,
            "affected_ids": list(self.affected_ids),
            "repair_action": self.repair_action,
        }


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _ids(value: object, *, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list):
        return []
    result = [_text(item) for item in value]
    if any(not item for item in result) or len(result) != len(set(result)):
        return []
    if not allow_empty and not result:
        return []
    return sorted(result)


def _unique_objects(value: object, key: str, path: str, findings: list[CapabilityFinding]) -> dict[str, Mapping[str, Any]]:
    if not isinstance(value, list):
        findings.append(CapabilityFinding("functional-closure-array-missing", path, "record must be an array"))
        return {}
    index: dict[str, Mapping[str, Any]] = {}
    for number, item in enumerate(value):
        item_path = f"{path}[{number}]"
        if not isinstance(item, Mapping):
            findings.append(CapabilityFinding("functional-closure-row-not-object", item_path, "row must be an object"))
            continue
        identity = _text(item.get(key))
        if not identity:
            findings.append(CapabilityFinding("functional-closure-row-id-missing", f"{item_path}.{key}", "row identity is required"))
            continue
        if identity in index:
            findings.append(CapabilityFinding("functional-closure-duplicate-id", f"{item_path}.{key}", "identity is duplicated", (identity,)))
            continue
        index[identity] = item
    return index


def _source_fingerprint(root: Path) -> str:
    """Hash the maintained target bytes with a stable relative-path envelope."""

    digest = hashlib.sha256()
    if not root.is_dir():
        return ""
    # Control records are the evidence consumer, not the implementation input
    # whose fingerprint they record.  Including functional-closure.json here
    # would create a self-referential freshness loop after every rewrite.
    excluded_parts = {".git", ".skillguard", "__pycache__", ".pytest_cache", ".sg-runtime", "runs", "test-results"}
    rows: list[tuple[str, Path]] = []
    for path in root.rglob("*"):
        if not path.is_file() or any(part.casefold() in excluded_parts for part in path.relative_to(root).parts):
            continue
        rows.append((path.relative_to(root).as_posix(), path))
    for relative, path in sorted(rows):
        try:
            content = path.read_bytes()
        except OSError:
            continue
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return "sha256:" + digest.hexdigest()


def _json_fingerprint(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _load_json(path: Path) -> tuple[object | None, str | None]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle), None
    except FileNotFoundError:
        return None, "missing"
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"unreadable:{type(exc).__name__}"


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _wire_target_fingerprint(value: object) -> str:
    text = _text(value)
    if not NATIVE_HASH_RE.fullmatch(text):
        return ""
    return "sha256:" + text.lower()


def _receipt_request_fingerprint(receipt: Mapping[str, Any]) -> str:
    """Bind the closure request projection to producer-owned target inputs."""

    return wire_hash(
        {
            "target_input_fingerprint": _text(
                receipt.get("target_input_fingerprint")
            ),
            "target_input_role_fingerprints": dict(
                receipt.get("target_input_role_fingerprints", {})
            ),
        }
    )


def _receipt_ref_shape_findings(
    evidence_id: str,
    item: Mapping[str, Any],
) -> list[CapabilityFinding]:
    result = _text(item.get("result"))
    receipt_ref = item.get("receipt_ref")
    path = f"$.evidence[{evidence_id}].receipt_ref"
    if result != "pass":
        if receipt_ref is not None:
            return [
                CapabilityFinding(
                    "evidence-receipt-result-conflict",
                    path,
                    "a canonical terminal-success receipt cannot be attached to non-pass evidence",
                    (evidence_id,),
                )
            ]
        return []
    findings: list[CapabilityFinding] = []
    if not isinstance(receipt_ref, Mapping):
        return [
            CapabilityFinding(
                "evidence-receipt-ref-missing",
                path,
                "caller-authored pass is not evidence; a canonical current receipt projection is required",
                (evidence_id,),
            )
        ]
    actual_fields = set(receipt_ref)
    for field in sorted(RECEIPT_REF_REQUIRED_FIELDS - actual_fields):
        findings.append(
            CapabilityFinding(
                RECEIPT_FIELD_MISSING_CODES.get(
                    field, "evidence-receipt-binding-incomplete"
                ),
                f"{path}.{field}",
                "the current receipt projection is missing a required exact identity",
                (evidence_id, field),
            )
        )
    extras = sorted(actual_fields - RECEIPT_REF_REQUIRED_FIELDS)
    if extras:
        findings.append(
            CapabilityFinding(
                "evidence-receipt-binding-field-set-invalid",
                path,
                "the current receipt projection contains unsupported fields",
                (evidence_id, *extras),
            )
        )
    if (
        receipt_ref.get("schema_version")
        != FUNCTIONAL_EVIDENCE_RECEIPT_REF_SCHEMA
    ):
        findings.append(
            CapabilityFinding(
                "evidence-receipt-ref-schema-unsupported",
                f"{path}.schema_version",
                "former receipt-reference schemas are rejection-only and must be directly rewritten",
                (evidence_id,),
            )
        )
    document_ref = receipt_ref.get("document_ref")
    expected_document_fields = {
        "path_token",
        "relative_path",
        "content_hash",
        "media_type",
        "byte_count",
    }
    if not isinstance(document_ref, Mapping) or set(document_ref) != expected_document_fields:
        findings.append(
            CapabilityFinding(
                "evidence-receipt-document-ref-invalid",
                f"{path}.document_ref",
                "receipt document reference must use the canonical owner-evidence content-ref shape",
                (evidence_id,),
            )
        )
    for field in (
        "request_fingerprint",
        "projection_declaration_hash",
        "execution_key",
        "owner_declaration_hash",
        "owner_input_projection_hash",
        "target_input_fingerprint",
        "toolchain_fingerprint",
        "execution_environment_fingerprint",
        "receipt_id",
        "receipt_hash",
    ):
        if field in receipt_ref and not WIRE_HASH_RE.fullmatch(
            _text(receipt_ref.get(field))
        ):
            findings.append(
                CapabilityFinding(
                    "evidence-receipt-hash-field-invalid",
                    f"{path}.{field}",
                    "receipt projection hash must use the current sha256 wire identity",
                    (evidence_id, field),
                )
            )
    if "check_manifest_hash" in receipt_ref and not NATIVE_HASH_RE.fullmatch(
        _text(receipt_ref.get("check_manifest_hash"))
    ):
        findings.append(
            CapabilityFinding(
                "evidence-receipt-manifest-hash-invalid",
                f"{path}.check_manifest_hash",
                "check manifest hash must use the current canonical identity",
                (evidence_id,),
            )
        )
    return findings


def _repository_root_for_target(
    target_root: Path,
    manifest: Mapping[str, Any],
) -> Path | None:
    plan = manifest.get("content_impact_plan")
    if not isinstance(plan, Mapping):
        return None
    member_root_text = _text(plan.get("member_root_path"))
    member_root = Path(member_root_text)
    if (
        not member_root_text
        or member_root.is_absolute()
        or ".." in member_root.parts
    ):
        return None
    normalized_parts = tuple(part for part in member_root.parts if part not in {"."})
    candidate = target_root.resolve()
    for _part in normalized_parts:
        candidate = candidate.parent
    expected = candidate.joinpath(*normalized_parts).resolve()
    return candidate if expected == target_root.resolve() else None


def _load_json_mapping(path: Path) -> Mapping[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, Mapping) else None


def _current_head_findings(
    owner_evidence_root: Path,
    receipt: Mapping[str, Any],
    document_ref: Mapping[str, Any],
    *,
    evidence_id: str,
) -> list[CapabilityFinding]:
    execution_key = _text(receipt.get("execution_key"))
    if not WIRE_HASH_RE.fullmatch(execution_key):
        return [
            CapabilityFinding(
                "evidence-receipt-execution-key-invalid",
                f"$.evidence[{evidence_id}].receipt_ref.execution_key",
                "canonical receipt execution key is invalid",
                (evidence_id,),
            )
        ]
    head_path = (
        owner_evidence_root
        / "check-executions"
        / "heads"
        / f"{execution_key.split(':', 1)[1]}.json"
    )
    head = _load_json_mapping(head_path)
    if head is None:
        return [
            CapabilityFinding(
                "evidence-receipt-current-head-missing",
                f"$.evidence[{evidence_id}].receipt_ref",
                "the referenced producer receipt is not the canonical current success for its execution identity",
                (evidence_id,),
            )
        ]
    expected_fields = {
        "schema_version",
        "maintenance_unit_id",
        "member_skill_id",
        "execution_owner_id",
        "execution_key",
        "receipt_id",
        "receipt_hash",
        "receipt_ref",
        "observed_at",
        "claim_boundary",
        "head_hash",
    }
    unsigned = dict(head)
    stored_hash = unsigned.pop("head_hash", None)
    if (
        set(head) != expected_fields
        or head.get("schema_version") != CHECK_EXECUTION_HEAD_SCHEMA
        or stored_hash != wire_hash(unsigned)
    ):
        return [
            CapabilityFinding(
                "evidence-receipt-current-head-invalid",
                f"$.evidence[{evidence_id}].receipt_ref",
                "canonical current success head is malformed or hash-invalid",
                (evidence_id,),
            )
        ]
    for field in (
        "maintenance_unit_id",
        "member_skill_id",
        "execution_owner_id",
        "execution_key",
        "receipt_id",
        "receipt_hash",
    ):
        if head.get(field) != receipt.get(field):
            return [
                CapabilityFinding(
                    "evidence-receipt-current-head-mismatch",
                    f"$.evidence[{evidence_id}].receipt_ref.{field}",
                    "receipt identity does not match its canonical current success head",
                    (evidence_id, field),
                )
            ]
    if head.get("receipt_ref") != document_ref:
        return [
            CapabilityFinding(
                "evidence-receipt-current-head-mismatch",
                f"$.evidence[{evidence_id}].receipt_ref.document_ref",
                "receipt document reference does not match its canonical current success head",
                (evidence_id,),
            )
        ]
    return []


def _record_shape_findings(payload: object) -> list[CapabilityFinding]:
    findings: list[CapabilityFinding] = []
    if not isinstance(payload, Mapping):
        return [CapabilityFinding("functional-closure-record-not-object", "$", "functional closure must be a JSON object")]
    if _text(payload.get("schema_version")) != FUNCTIONAL_CLOSURE_SCHEMA:
        findings.append(CapabilityFinding("unsupported-functional-closure-schema", "$.schema_version", f"expected {FUNCTIONAL_CLOSURE_SCHEMA}"))
    for field in ("functional_closure_id", "target_skill_id", "claim_boundary"):
        if not _text(payload.get(field)):
            findings.append(CapabilityFinding("functional-closure-required-field-missing", f"$.{field}", "required non-empty field is missing"))
    outcomes = _unique_objects(payload.get("outcomes"), "outcome_id", "$.outcomes", findings)
    paths = _unique_objects(payload.get("closure_paths"), "path_id", "$.closure_paths", findings)
    failures = _unique_objects(payload.get("failure_modes"), "failure_id", "$.failure_modes", findings)
    qualities = _unique_objects(payload.get("quality_requirements"), "quality_id", "$.quality_requirements", findings)
    evidence = _unique_objects(payload.get("evidence"), "evidence_id", "$.evidence", findings)
    if not outcomes:
        findings.append(CapabilityFinding("functional-closure-outcomes-missing", "$.outcomes", "at least one required outcome is needed"))
    if not paths:
        findings.append(CapabilityFinding("functional-closure-paths-missing", "$.closure_paths", "at least one closure path is needed"))
    for outcome_id, outcome in outcomes.items():
        if not _ids(outcome.get("user_jobs"), allow_empty=False):
            findings.append(CapabilityFinding("missing-representative-user-job", f"$.outcomes[{outcome_id}].user_jobs", "outcome needs a representative user job", (outcome_id,)))
        if not _ids(outcome.get("success_outputs"), allow_empty=False) and not _text(outcome.get("success_result")):
            findings.append(CapabilityFinding("missing-success-output", f"$.outcomes[{outcome_id}]", "outcome needs a success result or artifact", (outcome_id,)))
        path_id = _text(outcome.get("path_id"))
        if not path_id or path_id not in paths:
            findings.append(CapabilityFinding("outcome-path-missing", f"$.outcomes[{outcome_id}].path_id", "outcome path is missing or unknown", (outcome_id, path_id)))
        quality_ids = _ids(outcome.get("quality_requirement_ids"))
        if not quality_ids:
            findings.append(CapabilityFinding("quality-requirement-missing", f"$.outcomes[{outcome_id}].quality_requirement_ids", "outcome needs at least one explicit quality requirement", (outcome_id,)))
        if quality_ids and not set(quality_ids).issubset(qualities):
            findings.append(CapabilityFinding("outcome-quality-reference-missing", f"$.outcomes[{outcome_id}].quality_requirement_ids", "quality requirement reference is unknown", (outcome_id,)))
    for path_id, path in paths.items():
        outcome_ids = _ids(path.get("outcome_ids"), allow_empty=False)
        if not outcome_ids or not set(outcome_ids).issubset(outcomes):
            findings.append(CapabilityFinding("path-outcome-reference-missing", f"$.closure_paths[{path_id}].outcome_ids", "path outcome reference is unknown or empty", (path_id,)))
        stages = path.get("stages")
        if not isinstance(stages, list) or not stages:
            findings.append(CapabilityFinding("path-stages-missing", f"$.closure_paths[{path_id}].stages", "path needs ordered stages", (path_id,)))
            continue
        seen: set[str] = set()
        roles: list[str] = []
        for stage_number, stage in enumerate(stages):
            stage_path = f"$.closure_paths[{path_id}].stages[{stage_number}]"
            if not isinstance(stage, Mapping):
                findings.append(CapabilityFinding("path-stage-not-object", stage_path, "stage must be an object", (path_id,)))
                continue
            stage_id = _text(stage.get("stage_id"))
            role = _text(stage.get("role"))
            if not stage_id or stage_id in seen:
                findings.append(CapabilityFinding("path-stage-id-invalid", f"{stage_path}.stage_id", "stage id is missing or duplicated", (path_id, stage_id)))
            if stage_id:
                seen.add(stage_id)
            if role not in STAGE_ORDER:
                findings.append(CapabilityFinding("path-stage-role-invalid", f"{stage_path}.role", "stage role is not supported", (path_id, stage_id)))
            roles.append(role)
            if not _text(stage.get("owner_id")):
                findings.append(CapabilityFinding("path-stage-owner-missing", f"{stage_path}.owner_id", "stage needs one native owner", (path_id, stage_id)))
            if not _ids(stage.get("check_ids"), allow_empty=False):
                findings.append(CapabilityFinding("path-stage-check-missing", f"{stage_path}.check_ids", "stage needs a target-native check", (path_id, stage_id)))
            stage_evidence = _ids(stage.get("evidence_ids"), allow_empty=False)
            if not stage_evidence:
                findings.append(CapabilityFinding("path-stage-evidence-missing", f"{stage_path}.evidence_ids", "stage needs evidence references", (path_id, stage_id)))
            if role == "route" and not _text(stage.get("native_route_id")):
                findings.append(CapabilityFinding("path-stage-native-route-missing", f"{stage_path}.native_route_id", "route stage needs native route binding", (path_id, stage_id)))
            if role == "terminal" and _text(stage.get("terminal_kind")) not in {"success", "blocked", "escalated", "scoped_out"}:
                findings.append(CapabilityFinding("path-terminal-condition-missing", f"{stage_path}.terminal_kind", "terminal stage needs an explicit terminal condition", (path_id, stage_id)))
        positions = [STAGE_ORDER.index(role) for role in roles if role in STAGE_ORDER]
        if positions != sorted(positions):
            findings.append(CapabilityFinding("path-stage-order-invalid", f"$.closure_paths[{path_id}].stages", "stage roles must follow lifecycle order", (path_id,)))
        for required in REQUIRED_STAGE_ROLES:
            if required not in roles:
                findings.append(CapabilityFinding("path-stage-role-missing", f"$.closure_paths[{path_id}].stages", f"required role {required!r} is missing", (path_id, required)))
    for failure_id, failure in failures.items():
        if not _text(failure.get("stage_id")) or not _text(failure.get("detector")):
            findings.append(CapabilityFinding("unclosed-failure-boundary", f"$.failure_modes[{failure_id}]", "failure needs a stage and detector", (failure_id,)))
        disposition = _text(failure.get("disposition"))
        if disposition not in {"recover", "block", "escalate", "scope_out"}:
            findings.append(CapabilityFinding("failure-disposition-invalid", f"$.failure_modes[{failure_id}].disposition", "failure disposition is invalid", (failure_id,)))
        terminal_kind = _text(failure.get("terminal_kind"))
        if terminal_kind not in {"blocked", "escalated", "scoped_out", "success"} or (disposition in {"block", "escalate", "scope_out"} and terminal_kind == "success"):
            findings.append(CapabilityFinding("failure-terminal-condition-missing", f"$.failure_modes[{failure_id}].terminal_kind", "failure must have a non-success terminal effect", (failure_id,)))
        if disposition == "recover" and not _text(failure.get("recovery_path_id")):
            findings.append(CapabilityFinding("missing-recovery-path", f"$.failure_modes[{failure_id}].recovery_path_id", "recoverable failure needs a recovery path", (failure_id,)))
        if not _ids(failure.get("evidence_ids"), allow_empty=False):
            findings.append(CapabilityFinding("failure-evidence-missing", f"$.failure_modes[{failure_id}].evidence_ids", "failure needs current evidence", (failure_id,)))
    for quality_id, quality in qualities.items():
        if not _text(quality.get("description")) or not isinstance(quality.get("required"), bool):
            findings.append(CapabilityFinding("quality-requirement-invalid", f"$.quality_requirements[{quality_id}]", "quality requirement needs description and required flag", (quality_id,)))
        if not _ids(quality.get("evidence_ids"), allow_empty=False):
            findings.append(CapabilityFinding("quality-evidence-missing", f"$.quality_requirements[{quality_id}].evidence_ids", "quality requirement needs evidence", (quality_id,)))
    for evidence_id, item in evidence.items():
        if _text(item.get("execution_depth")) not in EVIDENCE_DEPTH_ORDER:
            findings.append(CapabilityFinding("evidence-execution-depth-invalid", f"$.evidence[{evidence_id}].execution_depth", "evidence depth is invalid", (evidence_id,)))
        if _text(item.get("environment_scope")) not in {"single", "matrix", "field"}:
            findings.append(CapabilityFinding("evidence-environment-scope-invalid", f"$.evidence[{evidence_id}].environment_scope", "environment scope is invalid", (evidence_id,)))
        if _text(item.get("quality_level")) not in QUALITY_ORDER:
            findings.append(CapabilityFinding("evidence-quality-level-invalid", f"$.evidence[{evidence_id}].quality_level", "quality level is invalid", (evidence_id,)))
        if not _ids(item.get("assertion_categories"), allow_empty=False):
            findings.append(CapabilityFinding("evidence-missing-assertion-scope", f"$.evidence[{evidence_id}].assertion_categories", "evidence needs at least one assertion category", (evidence_id,)))
        if _text(item.get("result")) not in {"pass", "fail", "blocked", "skipped", "not_run"}:
            findings.append(CapabilityFinding("evidence-result-invalid", f"$.evidence[{evidence_id}].result", "evidence result is invalid", (evidence_id,)))
        if _text(item.get("result")) == "pass" and not _ids(item.get("assertion_categories"), allow_empty=False):
            findings.append(CapabilityFinding("evidence-missing-assertion-scope", f"$.evidence[{evidence_id}]", "passing evidence has no assertion scope", (evidence_id,)))
        if _text(item.get("result")) == "pass" and _ids(item.get("covered_outcome_ids")) and set(_ids(item.get("assertion_categories"))) <= {"non_goal_rejection"}:
            findings.append(CapabilityFinding("non-goal-evidence-used-for-success", f"$.evidence[{evidence_id}]", "non-goal rejection evidence cannot close a required success outcome", tuple(_ids(item.get("covered_outcome_ids")))))
        if _text(item.get("result")) == "pass" and not WIRE_HASH_RE.fullmatch(
            _text(item.get("source_fingerprint"))
        ):
            findings.append(
                CapabilityFinding(
                    "evidence-source-fingerprint-missing",
                    f"$.evidence[{evidence_id}].source_fingerprint",
                    "passing evidence must name the exact current target source identity",
                    (evidence_id,),
                )
            )
        findings.extend(_receipt_ref_shape_findings(evidence_id, item))
    return findings


def _collect_contract_ids(contract: Mapping[str, Any] | None, manifest: Mapping[str, Any] | None) -> tuple[set[str], set[str], set[str]]:
    check_ids: set[str] = set()
    route_ids: set[str] = set()
    owner_ids: set[str] = set()
    for source in (contract, manifest):
        if not isinstance(source, Mapping):
            continue
        for key, destination in (("checks", check_ids), ("routes", route_ids), ("owners", owner_ids), ("execution_owners", owner_ids)):
            rows = source.get(key)
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, Mapping):
                        identity_key = {"checks": "check_id", "routes": "route_id", "owners": "owner_id", "execution_owners": "owner_id"}[key]
                        identity = _text(row.get(identity_key))
                        if identity:
                            destination.add(identity)
                    elif isinstance(row, str) and key == "checks":
                        check_ids.add(row)
    return check_ids, route_ids, owner_ids


def _manifest_check_index(
    manifest: Mapping[str, Any] | None,
) -> tuple[dict[str, Mapping[str, Any]], list[CapabilityFinding]]:
    findings: list[CapabilityFinding] = []
    index: dict[str, Mapping[str, Any]] = {}
    rows = manifest.get("checks") if isinstance(manifest, Mapping) else None
    if not isinstance(rows, list):
        return {}, [
            CapabilityFinding(
                "evidence-receipt-check-manifest-missing",
                "$.check_manifest.checks",
                "receipt-backed evidence requires the current exact check manifest",
            )
        ]
    for number, row in enumerate(rows):
        if not isinstance(row, Mapping):
            findings.append(
                CapabilityFinding(
                    "evidence-receipt-check-manifest-invalid",
                    f"$.check_manifest.checks[{number}]",
                    "check declaration must be an object",
                )
            )
            continue
        check_id = _text(row.get("check_id"))
        if not check_id or check_id in index:
            findings.append(
                CapabilityFinding(
                    "evidence-receipt-check-manifest-invalid",
                    f"$.check_manifest.checks[{number}].check_id",
                    "check id is missing or duplicated",
                    (check_id,) if check_id else (),
                )
            )
            continue
        index[check_id] = row
    return index, findings


def _manifest_owner_index(
    manifest: Mapping[str, Any],
) -> tuple[dict[str, Mapping[str, Any]], list[CapabilityFinding]]:
    findings: list[CapabilityFinding] = []
    plan = manifest.get("content_impact_plan")
    if not isinstance(plan, Mapping):
        return {}, [
            CapabilityFinding(
                "evidence-receipt-impact-plan-missing",
                "$.check_manifest.content_impact_plan",
                "receipt freshness requires the current content-impact owner plan",
            )
        ]
    rows = plan.get("owners")
    if not isinstance(rows, list):
        return {}, [
            CapabilityFinding(
                "evidence-receipt-owner-plan-missing",
                "$.check_manifest.content_impact_plan.owners",
                "receipt freshness requires exact execution-owner rows",
            )
        ]
    index: dict[str, Mapping[str, Any]] = {}
    for number, row in enumerate(rows):
        owner_id = _text(row.get("execution_owner_id")) if isinstance(row, Mapping) else ""
        if not owner_id or owner_id in index:
            findings.append(
                CapabilityFinding(
                    "evidence-receipt-owner-plan-invalid",
                    f"$.check_manifest.content_impact_plan.owners[{number}]",
                    "execution owner is missing or duplicated",
                    (owner_id,) if owner_id else (),
                )
            )
            continue
        index[owner_id] = row
    return index, findings


def _load_current_dependency_receipt(
    owner_evidence_root: Path,
    dependency: Mapping[str, Any],
) -> tuple[Mapping[str, Any] | None, CapabilityFinding | None]:
    heads_root = owner_evidence_root / "check-executions" / "heads"
    if not heads_root.is_dir():
        return None, CapabilityFinding(
            "evidence-receipt-dependency-missing",
            "$.receipt_ref.dependency_receipts",
            "canonical dependency receipt store is missing",
            (_text(dependency.get("execution_owner_id")),),
        )
    matches: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    for head_path in sorted(heads_root.glob("*.json")):
        head = _load_json_mapping(head_path)
        if not isinstance(head, Mapping):
            continue
        if any(
            head.get(field) != dependency.get(field)
            for field in (
                "maintenance_unit_id",
                "member_skill_id",
                "execution_owner_id",
                "receipt_id",
                "receipt_hash",
            )
        ):
            continue
        unsigned = dict(head)
        stored_hash = unsigned.pop("head_hash", None)
        document_ref = head.get("receipt_ref")
        if (
            head.get("schema_version") != CHECK_EXECUTION_HEAD_SCHEMA
            or stored_hash != wire_hash(unsigned)
            or not isinstance(document_ref, Mapping)
        ):
            return None, CapabilityFinding(
                "evidence-receipt-dependency-head-invalid",
                "$.receipt_ref.dependency_receipts",
                "dependency current-success head is malformed or hash-invalid",
                (_text(dependency.get("execution_owner_id")),),
            )
        try:
            receipt = load_owner_receipt_from_ref(
                owner_evidence_root,
                document_ref,
                expected_owner_id=_text(dependency.get("execution_owner_id")),
                expected_maintenance_unit_id=_text(
                    dependency.get("maintenance_unit_id")
                ),
            )
        except CheckRunnerError as exc:
            return None, CapabilityFinding(
                "evidence-receipt-dependency-invalid",
                "$.receipt_ref.dependency_receipts",
                f"canonical dependency receipt failed verification: {exc.code}",
                (_text(dependency.get("execution_owner_id")),),
            )
        if receipt.get("member_skill_id") != dependency.get("member_skill_id"):
            return None, CapabilityFinding(
                "evidence-receipt-dependency-member-mismatch",
                "$.receipt_ref.dependency_receipts",
                "dependency receipt member differs from the frozen dependency identity",
                (_text(dependency.get("execution_owner_id")),),
            )
        matches.append((head, receipt))
    if len(matches) != 1:
        return None, CapabilityFinding(
            "evidence-receipt-dependency-missing"
            if not matches
            else "evidence-receipt-dependency-ambiguous",
            "$.receipt_ref.dependency_receipts",
            "dependency must resolve to exactly one canonical current-success receipt",
            (_text(dependency.get("execution_owner_id")),),
        )
    return matches[0][1], None


def _owner_receipt_freshness_findings(
    receipt: Mapping[str, Any],
    *,
    evidence_id: str,
    repository_root: Path,
    manifest: Mapping[str, Any],
    check_index: Mapping[str, Mapping[str, Any]],
    owner_index: Mapping[str, Mapping[str, Any]],
    owner_evidence_root: Path,
    root_target_input_fingerprint: str,
    visited: frozenset[tuple[str, str]],
) -> list[CapabilityFinding]:
    owner_id = _text(receipt.get("execution_owner_id"))
    identity = (_text(receipt.get("receipt_id")), _text(receipt.get("receipt_hash")))
    if identity in visited:
        return [
            CapabilityFinding(
                "evidence-receipt-dependency-cycle",
                f"$.evidence[{evidence_id}].receipt_ref.dependency_receipts",
                "dependency receipt graph is cyclic",
                (evidence_id, owner_id),
            )
        ]
    owner = owner_index.get(owner_id)
    if owner is None:
        return [
            CapabilityFinding(
                "evidence-receipt-owner-mismatch",
                f"$.evidence[{evidence_id}].receipt_ref.execution_owner_id",
                "receipt owner is absent from the current content-impact plan",
                (evidence_id, owner_id),
            )
        ]
    findings: list[CapabilityFinding] = []
    if receipt.get("owner_declaration_hash") != owner.get("owner_declaration_hash"):
        findings.append(
            CapabilityFinding(
                "evidence-receipt-owner-stale",
                f"$.evidence[{evidence_id}].receipt_ref.owner_declaration_hash",
                "receipt owner declaration differs from the current owner plan",
                (evidence_id, owner_id),
            )
        )
    plan = manifest.get("content_impact_plan")
    if isinstance(plan, Mapping):
        owner_checks = [
            row
            for row in check_index.values()
            if _text(row.get("execution_owner_id")) == owner_id
        ]
        try:
            current_input = inspect_current_owner_input_projection(
                repository_root=repository_root,
                content_impact_plan=plan,
                owner=owner,
            )
            # The executable owner identity adds the live installed-tree
            # component for checks that explicitly select an installation
            # disposition.  Capability replay must compare that same exact
            # projection; otherwise an old receipt carrying the former
            # installed-tree component can appear current while TestMesh has
            # already rejected it (or the reverse).  Use the receipt's check
            # projection so multi-check owners remain check-exact.
            receipt_check = next(
                (
                    row
                    for row in owner_checks
                    if _text(row.get("check_id")) == _text(receipt.get("check_id"))
                ),
                owner_checks[0] if owner_checks else None,
            )
            if receipt_check is not None:
                installed_component = _installed_runtime_input_component(
                    receipt_check,
                    plan=plan,
                    owner=owner,
                )
                if installed_component is not None:
                    components = list(current_input.get("components", []))
                    components.append(installed_component)
                    components.sort(key=lambda row: str(row.get("component_id", "")))
                    current_input = {
                        **current_input,
                        "components": components,
                        "owner_input_projection_hash": wire_hash(components),
                    }
        except CheckRunnerError as exc:
            findings.append(
                CapabilityFinding(
                    "evidence-receipt-input-stale",
                    f"$.evidence[{evidence_id}].receipt_ref.input_components",
                    f"current owner input projection failed: {exc.code}",
                    (evidence_id, owner_id),
                )
            )
        else:
            if (
                receipt.get("input_components") != current_input.get("components")
                or receipt.get("owner_input_projection_hash")
                != current_input.get("owner_input_projection_hash")
            ):
                findings.append(
                    CapabilityFinding(
                        "evidence-receipt-input-stale",
                        f"$.evidence[{evidence_id}].receipt_ref.input_components",
                        "receipt inputs differ from the current exact owner component projection",
                        (evidence_id, owner_id),
                    )
                )
        if receipt.get("impact_policy_id") != plan.get("policy_id"):
            findings.append(
                CapabilityFinding(
                    "evidence-receipt-impact-policy-stale",
                    f"$.evidence[{evidence_id}].receipt_ref.impact_policy_id",
                    "receipt impact policy differs from the current owner plan",
                    (evidence_id, owner_id),
                )
            )
    if not owner_checks:
        findings.append(
            CapabilityFinding(
                "evidence-receipt-check-missing",
                f"$.evidence[{evidence_id}].receipt_ref.check_id",
                "receipt owner has no current semantic check projection",
                (evidence_id, owner_id),
            )
        )
    else:
        identities: set[tuple[str, str]] = set()
        for check in owner_checks:
            try:
                current = check_toolchain_identity(check)
            except CheckRunnerError:
                continue
            identities.add(
                (
                    current["toolchain_fingerprint"],
                    current["execution_environment_fingerprint"],
                )
            )
        receipt_identity = (
            _text(receipt.get("toolchain_fingerprint")),
            _text(receipt.get("execution_environment_fingerprint")),
        )
        if receipt_identity not in identities:
            findings.extend(
                [
                    CapabilityFinding(
                        "evidence-receipt-toolchain-stale",
                        f"$.evidence[{evidence_id}].receipt_ref.toolchain_fingerprint",
                        "receipt toolchain differs from every current check owned by this producer",
                        (evidence_id, owner_id),
                    ),
                    CapabilityFinding(
                        "evidence-receipt-environment-stale",
                        f"$.evidence[{evidence_id}].receipt_ref.execution_environment_fingerprint",
                        "receipt environment differs from every current check owned by this producer",
                        (evidence_id, owner_id),
                    ),
                ]
            )
    if root_target_input_fingerprint and receipt.get(
        "target_input_fingerprint"
    ) != root_target_input_fingerprint:
        findings.append(
            CapabilityFinding(
                "evidence-receipt-request-mismatch",
                f"$.evidence[{evidence_id}].receipt_ref.target_input_fingerprint",
                "dependency receipt was produced for a different target-input request",
                (evidence_id, owner_id),
            )
        )
    dependencies = receipt.get("dependency_receipts")
    expected_dependency_owners = sorted(
        _text(value) for value in owner.get("depends_on_owner_ids", [])
    )
    actual_dependency_owners = sorted(
        _text(row.get("execution_owner_id"))
        for row in dependencies
        if isinstance(row, Mapping)
    ) if isinstance(dependencies, list) else []
    if expected_dependency_owners != actual_dependency_owners:
        findings.append(
            CapabilityFinding(
                "evidence-receipt-dependency-mismatch",
                f"$.evidence[{evidence_id}].receipt_ref.dependency_receipts",
                "receipt dependency owner set differs from the current owner plan",
                (evidence_id, owner_id),
            )
        )
        return findings
    for dependency in dependencies if isinstance(dependencies, list) else []:
        if not isinstance(dependency, Mapping):
            continue
        if dependency.get("maintenance_unit_id") != receipt.get(
            "maintenance_unit_id"
        ):
            findings.append(
                CapabilityFinding(
                    "evidence-receipt-cross-unit",
                    f"$.evidence[{evidence_id}].receipt_ref.dependency_receipts",
                    "dependency receipt belongs to another maintenance unit",
                    (evidence_id, _text(dependency.get("execution_owner_id"))),
                )
            )
            continue
        dependency_receipt, finding = _load_current_dependency_receipt(
            owner_evidence_root, dependency
        )
        if finding is not None:
            findings.append(finding)
            continue
        assert dependency_receipt is not None
        findings.extend(
            _owner_receipt_freshness_findings(
                dependency_receipt,
                evidence_id=evidence_id,
                repository_root=repository_root,
                manifest=manifest,
                check_index=check_index,
                owner_index=owner_index,
                owner_evidence_root=owner_evidence_root,
                root_target_input_fingerprint=root_target_input_fingerprint,
                visited=visited | {identity},
            )
        )
    return findings


def _verify_receipt_evidence(
    evidence_id: str,
    item: Mapping[str, Any],
    *,
    target_root: Path | None,
    repository_root: Path | None,
    owner_evidence_root: Path | None,
    manifest: Mapping[str, Any] | None,
    check_index: Mapping[str, Mapping[str, Any]],
    owner_index: Mapping[str, Mapping[str, Any]],
) -> tuple[list[CapabilityFinding], bool]:
    if _text(item.get("result")) != "pass":
        return [], False
    receipt_ref = item.get("receipt_ref")
    path = f"$.evidence[{evidence_id}].receipt_ref"
    if not isinstance(receipt_ref, Mapping) or set(receipt_ref) != RECEIPT_REF_REQUIRED_FIELDS:
        return [], False
    findings: list[CapabilityFinding] = []
    if manifest is None:
        return [
            CapabilityFinding(
                "evidence-receipt-check-manifest-missing",
                path,
                "receipt-backed pass requires the current exact check manifest",
                (evidence_id,),
            )
        ], False
    if target_root is None or repository_root is None:
        return [
            CapabilityFinding(
                "evidence-receipt-author-root-unresolved",
                path,
                "target and author repository roots are required for current receipt replay",
                (evidence_id,),
            )
        ], False
    if owner_evidence_root is None or not owner_evidence_root.is_dir():
        return [
            CapabilityFinding(
                "evidence-receipt-store-missing",
                path,
                "canonical owner-evidence store is missing; no alternate store is discovered",
                (evidence_id,),
            )
        ], False

    check_id = _text(receipt_ref.get("check_id"))
    check = check_index.get(check_id)
    if check is None:
        return [
            CapabilityFinding(
                "evidence-receipt-check-missing",
                f"{path}.check_id",
                "receipt projection names no current manifest check",
                (evidence_id, check_id),
            )
        ], False
    manifest_hash = _text(manifest.get("manifest_hash"))
    unsigned_manifest = dict(manifest)
    unsigned_manifest.pop("manifest_hash", None)
    if (
        not NATIVE_HASH_RE.fullmatch(manifest_hash)
        or canonical_hash(unsigned_manifest) != manifest_hash
    ):
        findings.append(
            CapabilityFinding(
                "evidence-receipt-check-manifest-stale",
                f"{path}.check_manifest_hash",
                "current check manifest is missing its exact canonical hash",
                (evidence_id,),
            )
        )
    if receipt_ref.get("check_manifest_hash") != manifest_hash:
        findings.append(
            CapabilityFinding(
                "evidence-receipt-check-manifest-mismatch",
                f"{path}.check_manifest_hash",
                "receipt projection names a different check manifest",
                (evidence_id, check_id),
            )
        )
    expected_unit = _text(manifest.get("maintenance_unit_id"))
    members = _ids(manifest.get("member_skill_ids"), allow_empty=False)
    expected_member = _text(check.get("member_skill_id"))
    expected_owner = _text(check.get("execution_owner_id"))
    identity_expectations = (
        (
            "maintenance_unit_id",
            expected_unit,
            "evidence-receipt-cross-unit",
        ),
        (
            "member_skill_id",
            expected_member,
            "evidence-receipt-member-mismatch",
        ),
        (
            "semantic_check_id",
            _text(check.get("semantic_check_id")),
            "evidence-receipt-check-mismatch",
        ),
        (
            "execution_owner_id",
            expected_owner,
            "evidence-receipt-owner-mismatch",
        ),
        (
            "projection_declaration_hash",
            _text(check.get("projection_declaration_hash")),
            "evidence-receipt-check-mismatch",
        ),
    )
    if expected_member not in members:
        findings.append(
            CapabilityFinding(
                "evidence-receipt-member-mismatch",
                f"{path}.member_skill_id",
                "check member is absent from the current maintenance unit",
                (evidence_id, expected_member),
            )
        )
    for field, expected, code in identity_expectations:
        if not expected or receipt_ref.get(field) != expected:
            findings.append(
                CapabilityFinding(
                    code,
                    f"{path}.{field}",
                    "receipt projection differs from the current manifest-owned check identity",
                    (evidence_id, check_id, field),
                )
            )
    document_ref = receipt_ref.get("document_ref")
    if not isinstance(document_ref, Mapping):
        return findings, False
    try:
        receipt = load_owner_receipt_from_ref(
            owner_evidence_root,
            document_ref,
            expected_owner_id=expected_owner,
            expected_maintenance_unit_id=expected_unit,
        )
    except CheckRunnerError as exc:
        code = "evidence-receipt-invalid"
        if "cleanup" in exc.message:
            code = "evidence-receipt-cleanup-unconfirmed"
        elif "foreign_unit" in exc.code or "maintenance_unit" in exc.message:
            code = "evidence-receipt-cross-unit"
        elif "dependency" in exc.code or "dependency" in exc.message:
            code = "evidence-receipt-dependency-invalid"
        elif "hash" in exc.message or "hash" in exc.code:
            code = "evidence-receipt-hash-mismatch"
        findings.append(
            CapabilityFinding(
                code,
                path,
                f"canonical owner receipt failed exact verification: {exc.code}",
                (evidence_id, check_id),
            )
        )
        return findings, False
    if receipt.get("member_skill_id") != expected_member:
        findings.append(
            CapabilityFinding(
                "evidence-receipt-member-mismatch",
                f"{path}.member_skill_id",
                "canonical owner receipt belongs to another member",
                (evidence_id, check_id),
            )
        )
    projection_fields = (
        "maintenance_unit_id",
        "member_skill_id",
        "execution_owner_id",
        "execution_key",
        "owner_declaration_hash",
        "owner_input_projection_hash",
        "input_components",
        "dependency_receipts",
        "target_input_fingerprint",
        "target_input_role_fingerprints",
        "toolchain_fingerprint",
        "execution_environment_fingerprint",
        "impact_policy_id",
        "status",
        "receipt_id",
        "receipt_hash",
    )
    mismatch_codes = {
        "maintenance_unit_id": "evidence-receipt-cross-unit",
        "member_skill_id": "evidence-receipt-member-mismatch",
        "execution_owner_id": "evidence-receipt-owner-mismatch",
        "input_components": "evidence-receipt-input-mismatch",
        "owner_input_projection_hash": "evidence-receipt-input-mismatch",
        "dependency_receipts": "evidence-receipt-dependency-mismatch",
        "toolchain_fingerprint": "evidence-receipt-toolchain-mismatch",
        "execution_environment_fingerprint": "evidence-receipt-environment-mismatch",
        "receipt_id": "evidence-receipt-id-mismatch",
        "receipt_hash": "evidence-receipt-hash-mismatch",
    }
    for field in projection_fields:
        if receipt_ref.get(field) != receipt.get(field):
            findings.append(
                CapabilityFinding(
                    mismatch_codes.get(field, "evidence-receipt-binding-mismatch"),
                    f"{path}.{field}",
                    "receipt projection differs from the verified canonical producer receipt",
                    (evidence_id, check_id, field),
                )
            )
    if receipt_ref.get("cleanup_confirmed") is not True:
        findings.append(
            CapabilityFinding(
                "evidence-receipt-cleanup-unconfirmed",
                f"{path}.cleanup_confirmed",
                "cleanup-unconfirmed evidence is never reusable",
                (evidence_id, check_id),
            )
        )
    findings.extend(
        _current_head_findings(
            owner_evidence_root,
            receipt,
            document_ref,
            evidence_id=evidence_id,
        )
    )
    # Native self-host receipts declare target-input paths relative to the
    # canonical author repository (the same root used when the owner ran),
    # while the closure itself is stored under the member skill root.  Use the
    # explicit/reconstructed author root for replay so a valid repo-relative
    # request is not incorrectly treated as a member-relative path.  Tests
    # that validate an isolated member without an author root continue to use
    # the member root.
    input_root = repository_root or target_root
    try:
        current_target_inputs = fingerprint_target_inputs(
            input_root, receipt_ref.get("target_input_paths")
        )
        current_target_fingerprint = _wire_target_fingerprint(
            current_target_inputs.get("fingerprint")
        )
    except TargetInputError as exc:
        current_target_fingerprint = ""
        findings.append(
            CapabilityFinding(
                "evidence-receipt-input-stale",
                f"{path}.target_input_paths",
                f"current target-input projection failed: {exc.code}",
                (evidence_id, check_id),
            )
        )
    if (
        not current_target_fingerprint
        or current_target_fingerprint != receipt.get("target_input_fingerprint")
        or receipt_ref.get("target_input_fingerprint")
        != current_target_fingerprint
    ):
        findings.append(
            CapabilityFinding(
                "evidence-receipt-input-stale",
                f"{path}.target_input_fingerprint",
                "receipt target inputs differ from the current named request inputs",
                (evidence_id, check_id),
            )
        )
    target_input_roles = receipt_ref.get("target_input_roles")
    current_role_fingerprints: dict[str, str] = {}
    if isinstance(target_input_roles, Mapping) and target_input_roles:
        try:
            current_roles = fingerprint_target_input_roles(
                target_root, target_input_roles
            )
        except TargetInputError as exc:
            findings.append(
                CapabilityFinding(
                    "evidence-receipt-input-stale",
                    f"{path}.target_input_roles",
                    f"current target-role projection failed: {exc.code}",
                    (evidence_id, check_id),
                )
            )
        else:
            current_role_fingerprints = {
                str(role): _wire_target_fingerprint(row.get("fingerprint"))
                for role, row in current_roles.items()
            }
    if (
        receipt.get("target_input_role_fingerprints")
        != current_role_fingerprints
        or receipt_ref.get("target_input_role_fingerprints")
        != current_role_fingerprints
    ):
        findings.append(
            CapabilityFinding(
                "evidence-receipt-input-stale",
                f"{path}.target_input_role_fingerprints",
                "receipt target-role inputs differ from the current named request inputs",
                (evidence_id, check_id),
            )
        )
    expected_request = _receipt_request_fingerprint(receipt)
    if receipt_ref.get("request_fingerprint") != expected_request:
        findings.append(
            CapabilityFinding(
                "evidence-receipt-request-mismatch",
                f"{path}.request_fingerprint",
                "receipt request fingerprint does not match producer-owned target inputs",
                (evidence_id, check_id),
            )
        )
    owner = owner_index.get(expected_owner)
    if owner is None:
        findings.append(
            CapabilityFinding(
                "evidence-receipt-owner-mismatch",
                f"{path}.execution_owner_id",
                "current owner plan does not contain the receipt producer",
                (evidence_id, check_id),
            )
        )
    else:
        findings.extend(
            _owner_receipt_freshness_findings(
                receipt,
                evidence_id=evidence_id,
                repository_root=repository_root,
                manifest=manifest,
                check_index=check_index,
                owner_index=owner_index,
                owner_evidence_root=owner_evidence_root,
                root_target_input_fingerprint=current_target_fingerprint,
                visited=frozenset(),
            )
        )
        try:
            current_toolchain = check_toolchain_identity(check)
        except CheckRunnerError as exc:
            findings.append(
                CapabilityFinding(
                    "evidence-receipt-toolchain-stale",
                    f"{path}.toolchain_fingerprint",
                    f"current toolchain identity failed: {exc.code}",
                    (evidence_id, check_id),
                )
            )
        else:
            for field, code in (
                ("toolchain_fingerprint", "evidence-receipt-toolchain-stale"),
                (
                    "execution_environment_fingerprint",
                    "evidence-receipt-environment-stale",
                ),
            ):
                if receipt.get(field) != current_toolchain.get(field):
                    findings.append(
                        CapabilityFinding(
                            code,
                            f"{path}.{field}",
                            "producer receipt no longer matches the current exact toolchain/environment",
                            (evidence_id, check_id),
                        )
                    )
    return findings, not findings


def _evidence_index(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        _text(row.get("evidence_id")): row
        for row in payload.get("evidence", [])
        if isinstance(row, Mapping) and _text(row.get("evidence_id"))
    }


def _evidence_satisfies(
    evidence_id: str,
    item: Mapping[str, Any],
    *,
    verified_evidence_ids: frozenset[str],
    minimum_depth: str,
    required_categories: Iterable[str] = (),
) -> bool:
    # The closure's own result string is only a claim.  A pass may satisfy a
    # lifecycle obligation only after exact replay of its canonical producer
    # receipt against the current manifest, inputs, dependencies and store.
    if (
        _text(item.get("result")) not in PASS_RESULTS
        or evidence_id not in verified_evidence_ids
    ):
        return False
    if EVIDENCE_DEPTH_ORDER.get(_text(item.get("execution_depth")), -1) < EVIDENCE_DEPTH_ORDER[minimum_depth]:
        return False
    return set(required_categories).issubset(set(_ids(item.get("assertion_categories"))))


def _scope_evidence_gaps(
    payload: Mapping[str, Any],
    scope: str,
    outcomes: Mapping[str, Mapping[str, Any]],
    paths: Mapping[str, Mapping[str, Any]],
    failures: Mapping[str, Mapping[str, Any]],
    qualities: Mapping[str, Mapping[str, Any]],
    evidence: Mapping[str, Mapping[str, Any]],
    verified_evidence_ids: frozenset[str],
) -> list[CapabilityFinding]:
    findings: list[CapabilityFinding] = []
    min_positive = {"routine": "fixture", "functional": "simulated_e2e", "release": "real_e2e", "highest-quality": "real_e2e"}[scope]
    for outcome_id, outcome in sorted(outcomes.items()):
        path = paths.get(_text(outcome.get("path_id")), {})
        stage_rows = path.get("stages", []) if isinstance(path, Mapping) else []
        for stage in stage_rows:
            if not isinstance(stage, Mapping):
                continue
            stage_id = _text(stage.get("stage_id"))
            evidence_rows = [(eid, evidence[eid]) for eid in _ids(stage.get("evidence_ids")) if eid in evidence]
            roles = _text(stage.get("role"))
            minimum = min_positive if roles in {"trigger", "intake", "route", "execute", "produce", "validate", "terminal"} else "fixture"
            if not any(
                _evidence_satisfies(
                    evidence_id,
                    row,
                    verified_evidence_ids=verified_evidence_ids,
                    minimum_depth=minimum,
                    required_categories=("execution",) if roles == "execute" else (),
                )
                for evidence_id, row in evidence_rows
            ):
                findings.append(CapabilityFinding("insufficient-execution-depth", f"$.closure_paths[{_text(outcome.get('path_id'))}].stages[{stage_id}]", f"{scope} scope needs current {minimum} evidence", (outcome_id, stage_id)))
    for failure_id, failure in sorted(failures.items()):
        rows = [(eid, evidence[eid]) for eid in _ids(failure.get("evidence_ids")) if eid in evidence]
        if not any(
            _evidence_satisfies(
                evidence_id,
                row,
                verified_evidence_ids=verified_evidence_ids,
                minimum_depth="fixture",
                required_categories=("validation",),
            )
            for evidence_id, row in rows
        ):
            findings.append(CapabilityFinding("failure-evidence-not-current", f"$.failure_modes[{failure_id}].evidence_ids", "failure evidence must be passing fixture-level or stronger validation evidence", (failure_id,)))
        if _text(failure.get("disposition")) == "recover":
            recovery_path_id = _text(failure.get("recovery_path_id"))
            recovery_path = paths.get(recovery_path_id, {})
            if not recovery_path:
                findings.append(CapabilityFinding("missing-recovery-path", f"$.failure_modes[{failure_id}].recovery_path_id", "recovery path is unknown", (failure_id,)))
    for quality_id, quality in sorted(qualities.items()):
        if quality.get("required") is not True:
            continue
        rows = [(eid, evidence[eid]) for eid in _ids(quality.get("evidence_ids")) if eid in evidence]
        required_level = "human" if scope == "highest-quality" else "deterministic"
        if not any(
            _evidence_satisfies(
                evidence_id,
                row,
                verified_evidence_ids=verified_evidence_ids,
                minimum_depth="fixture" if scope == "routine" else "simulated_e2e" if scope == "functional" else "real_e2e",
                required_categories=("quality",),
            )
            and QUALITY_ORDER.get(_text(row.get("quality_level")), -1)
            >= QUALITY_ORDER[required_level]
            for evidence_id, row in rows
        ):
            findings.append(CapabilityFinding("insufficient-quality-evidence", f"$.quality_requirements[{quality_id}]", f"{scope} scope needs {required_level} quality evidence", (quality_id,)))
    for evidence_id, item in sorted(evidence.items()):
        if _text(item.get("result")) in NON_TERMINAL_RESULTS and _text(item.get("result")) != "fail":
            # Keep these visible as skipped checks rather than silently treating
            # them as ordinary failures.
            findings.append(CapabilityFinding("evidence-not-current", f"$.evidence[{evidence_id}].result", "evidence is not a passing current result", (evidence_id,)))
    return findings


def _surface_inventory_gate(
    payload: Mapping[str, Any],
    *,
    target_root: Path | None,
    contract: Mapping[str, Any] | None,
    command_surface: Sequence[Mapping[str, Any]],
    route_entries: Sequence[Mapping[str, Any]],
    command_handlers: Mapping[str, Any] | None,
) -> tuple[list[CapabilityFinding], dict[str, Any]]:
    """Run the target-owned reverse denominator before a functional claim.

    ``functional-closure.json`` is evidence, not an implementation inventory.
    This gate deliberately loads the current target-owned inventory and then
    compares it with fresh source observation.  A caller-authored closure or a
    resealed inventory hash cannot make a missing/unknown surface disappear.
    ``command_surface``/``route_entries`` are supplied only by the target's
    native owner (the SkillGuard self-host caller supplies its own registry);
    an ordinary consumer never receives a fabricated registry from this
    module.
    """

    findings: list[CapabilityFinding] = []
    report: dict[str, Any] = {
        "status": "blocked",
        "required": True,
        "path": "",
        "findings": [],
        "full_surface_count": 0,
        "full_discovery_fingerprint": "",
    }

    def add(code: str, path: str, detail: object, repair: str) -> None:
        finding = CapabilityFinding(code, path, str(detail), repair_action=repair)
        findings.append(finding)
        report["findings"].append(finding.to_dict())

    if target_root is None:
        add(
            "surface_inventory_target_root_missing",
            "$.target_root",
            "a target root is required for reverse source discovery",
            "Directly supply the current target root and rerun the functional audit.",
        )
        return findings, report

    profile = contract.get("depth_profile") if isinstance(contract, Mapping) else None
    declaration = profile.get("surface_inventory") if isinstance(profile, Mapping) else None
    if not isinstance(declaration, Mapping):
        add(
            "surface_inventory_not_declared",
            "$.depth_profile.surface_inventory",
            "the current contract must bind one target-owned surface inventory",
            "Directly rewrite the current contract/depth profile with the target-owned surface inventory binding; do not infer one from closure prose.",
        )
        return findings, report

    relative = _text(declaration.get("path"))
    report["path"] = relative
    candidate = Path(relative)
    if not relative or candidate.is_absolute() or any(part == ".." for part in candidate.parts):
        add(
            "surface_inventory_path_unsafe",
            "$.depth_profile.surface_inventory.path",
            relative,
            "Directly rewrite the current contract to bind a safe target-owned inventory path.",
        )
        return findings, report
    inventory_path = (target_root.resolve() / candidate).resolve()
    if not inventory_path.is_relative_to(target_root.resolve()) or not inventory_path.is_file():
        add(
            "surface_inventory_file_missing",
            relative,
            "target-owned implementation surface inventory is missing",
            "Directly author the current target-owned surface inventory and rerun source discovery; no closure fallback is accepted.",
        )
        return findings, report
    inventory, error = _load_json(inventory_path)
    if error or not isinstance(inventory, Mapping):
        add(
            "surface_inventory_unreadable",
            relative,
            error or "inventory must be a JSON object",
            "Directly rewrite the current target-owned surface inventory as valid current JSON and rerun the audit.",
        )
        return findings, report

    target_skill_id = _text(payload.get("target_skill_id"))
    native_check_ids = profile.get("native_check_ids", []) if isinstance(profile, Mapping) else []
    model_deepening_check_id = _text(profile.get("model_deepening_check_id")) if isinstance(profile, Mapping) else ""
    surface_findings = list(
        validate_surface_inventory(
            inventory,
            target_skill_id=target_skill_id,
            native_check_ids=native_check_ids,
            model_deepening_check_id=model_deepening_check_id,
            path=relative,
        )
    )
    surface_findings.extend(
        validate_full_surface_inventory(
            inventory,
            target_root=target_root,
            command_surface=command_surface,
            route_entries=route_entries,
            command_handlers=command_handlers,
            native_check_ids=native_check_ids,
            model_deepening_check_id=model_deepening_check_id,
        )
    )
    report["full_surface_count"] = len(inventory.get("full_surfaces", [])) if isinstance(inventory.get("full_surfaces"), list) else 0
    report["full_discovery_fingerprint"] = _text(inventory.get("full_discovery_fingerprint"))
    report["status"] = "pass" if not surface_findings else "blocked"
    for item in surface_findings:
        add(
            item.code,
            item.path,
            item.detail,
            "Directly rewrite the current target-owned surface inventory and rerun fresh source discovery; do not reseal a missing semantic row or use a former inventory.",
        )
    return findings, report


def validate_functional_closure(
    payload: object,
    *,
    target_root: Path | None = None,
    contract: Mapping[str, Any] | None = None,
    check_manifest: Mapping[str, Any] | None = None,
    repository_root: Path | None = None,
    owner_evidence_root: Path | None = None,
    claim_scope: str = "routine",
    require_native_bindings: bool = True,
    require_surface_inventory: bool = False,
    surface_command_surface: Sequence[Mapping[str, Any]] = (),
    surface_route_entries: Sequence[Mapping[str, Any]] = (),
    surface_command_handlers: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate one closure declaration without executing the target workflow."""

    findings = _record_shape_findings(payload)
    root = target_root.resolve() if target_root is not None else None
    repository = repository_root.resolve() if repository_root is not None else None
    if not isinstance(payload, Mapping):
        payload = {}
    outcomes = _unique_objects(payload.get("outcomes"), "outcome_id", "$.outcomes", findings)
    paths = _unique_objects(payload.get("closure_paths"), "path_id", "$.closure_paths", findings)
    failures = _unique_objects(payload.get("failure_modes"), "failure_id", "$.failure_modes", findings)
    qualities = _unique_objects(payload.get("quality_requirements"), "quality_id", "$.quality_requirements", findings)
    evidence = _evidence_index(payload)
    if claim_scope not in CLAIM_SCOPES:
        findings.append(CapabilityFinding("claim-scope-invalid", "$.claim_scope", f"unsupported claim scope {claim_scope!r}"))
        claim_scope = "routine"
    check_ids, route_ids, owner_ids = _collect_contract_ids(contract, check_manifest)
    check_index, check_index_findings = _manifest_check_index(check_manifest)
    findings.extend(check_index_findings)
    owner_index: dict[str, Mapping[str, Any]] = {}
    if isinstance(check_manifest, Mapping):
        owner_index, owner_index_findings = _manifest_owner_index(check_manifest)
        findings.extend(owner_index_findings)
        if repository is None and root is not None:
            repository = _repository_root_for_target(root, check_manifest)
    receipt_store = (
        owner_evidence_root.resolve()
        if owner_evidence_root is not None
        else repository / "work" / "verification" / "owner-evidence"
        if repository is not None
        else None
    )
    verified_evidence_ids: set[str] = set()
    for evidence_id, item in evidence.items():
        receipt_findings, verified = _verify_receipt_evidence(
            evidence_id,
            item,
            target_root=root,
            repository_root=repository,
            owner_evidence_root=receipt_store,
            manifest=check_manifest,
            check_index=check_index,
            owner_index=owner_index,
        )
        findings.extend(receipt_findings)
        if verified:
            verified_evidence_ids.add(evidence_id)
    verified_receipts = frozenset(verified_evidence_ids)
    surface_report: dict[str, Any] | None = None
    if require_surface_inventory:
        surface_findings, surface_report = _surface_inventory_gate(
            payload,
            target_root=root,
            contract=contract,
            command_surface=surface_command_surface,
            route_entries=surface_route_entries,
            command_handlers=surface_command_handlers,
        )
        findings.extend(surface_findings)
    if require_native_bindings and contract is None and check_manifest is None:
        findings.append(CapabilityFinding("native-binding-source-missing", "$", "functional closure has no current target contract or check manifest to own its bindings"))
    for path_id, path in paths.items():
        for stage_number, stage in enumerate(path.get("stages", []) if isinstance(path, Mapping) else []):
            if not isinstance(stage, Mapping):
                continue
            stage_id = _text(stage.get("stage_id"))
            stage_path = f"$.closure_paths[{path_id}].stages[{stage_number}]"
            if require_native_bindings and check_ids:
                unknown = sorted(set(_ids(stage.get("check_ids"))) - check_ids)
                if unknown:
                    findings.append(CapabilityFinding("native-check-binding-missing", f"{stage_path}.check_ids", "stage references an unknown target-native check", (path_id, stage_id, *unknown)))
            if require_native_bindings and route_ids and _text(stage.get("native_route_id")) not in route_ids and _text(stage.get("role")) == "route":
                findings.append(CapabilityFinding("native-route-binding-missing", f"{stage_path}.native_route_id", "stage references an unknown target-native route", (path_id, stage_id)))
            if owner_ids and _text(stage.get("owner_id")) not in owner_ids:
                findings.append(CapabilityFinding("execution-owner-binding-missing", f"{stage_path}.owner_id", "stage references an unknown execution owner", (path_id, stage_id)))
            for evidence_id in _ids(stage.get("evidence_ids")):
                if evidence_id not in evidence:
                    findings.append(CapabilityFinding("stage-evidence-reference-missing", f"{stage_path}.evidence_ids", "stage evidence reference is unknown", (path_id, stage_id, evidence_id)))
                elif stage_id not in _ids(evidence[evidence_id].get("covered_stage_ids")):
                    findings.append(CapabilityFinding("evidence-stage-coverage-missing", f"$.evidence[{evidence_id}].covered_stage_ids", "stage evidence must name the stage it proves", (path_id, stage_id, evidence_id)))
                else:
                    receipt_ref = evidence[evidence_id].get("receipt_ref")
                    if isinstance(receipt_ref, Mapping):
                        if _text(receipt_ref.get("check_id")) not in _ids(stage.get("check_ids")):
                            findings.append(CapabilityFinding("evidence-receipt-stage-check-mismatch", f"$.evidence[{evidence_id}].receipt_ref.check_id", "receipt producer check is not one of the stage's declared native checks", (path_id, stage_id, evidence_id)))
                        if _text(receipt_ref.get("execution_owner_id")) != _text(stage.get("owner_id")):
                            findings.append(CapabilityFinding("evidence-receipt-stage-owner-mismatch", f"$.evidence[{evidence_id}].receipt_ref.execution_owner_id", "receipt producer owner differs from the stage owner", (path_id, stage_id, evidence_id)))
    for failure_id, failure in failures.items():
        for evidence_id in _ids(failure.get("evidence_ids")):
            if evidence_id not in evidence:
                findings.append(CapabilityFinding("failure-evidence-reference-missing", f"$.failure_modes[{failure_id}].evidence_ids", "failure evidence reference is unknown", (failure_id, evidence_id)))
            elif failure_id not in _ids(evidence[evidence_id].get("covered_failure_ids")):
                findings.append(CapabilityFinding("evidence-failure-coverage-missing", f"$.evidence[{evidence_id}].covered_failure_ids", "failure evidence must name the failure it proves", (failure_id, evidence_id)))
        recovery_path_id = _text(failure.get("recovery_path_id"))
        if recovery_path_id and recovery_path_id not in paths:
            findings.append(CapabilityFinding("recovery-path-reference-missing", f"$.failure_modes[{failure_id}].recovery_path_id", "recovery path reference is unknown", (failure_id, recovery_path_id)))
    for quality_id, quality in qualities.items():
        for evidence_id in _ids(quality.get("evidence_ids")):
            if evidence_id not in evidence:
                findings.append(CapabilityFinding("quality-evidence-reference-missing", f"$.quality_requirements[{quality_id}].evidence_ids", "quality evidence reference is unknown", (quality_id, evidence_id)))
            elif quality_id not in _ids(evidence[evidence_id].get("covered_quality_ids")):
                findings.append(CapabilityFinding("evidence-quality-coverage-missing", f"$.evidence[{evidence_id}].covered_quality_ids", "quality evidence must name the quality requirement it proves", (quality_id, evidence_id)))
    if root is not None:
        current_source = _source_fingerprint(root)
        declared_source = _text(payload.get("source_fingerprint"))
        if declared_source and current_source and declared_source != current_source:
            findings.append(CapabilityFinding("stale-capability-evidence", "$.source_fingerprint", "closure source identity does not match the current target source", (declared_source, current_source), "Directly rewrite the closure for the current source and execute fresh native checks."))
        for evidence_id, item in evidence.items():
            evidence_source = _text(item.get("source_fingerprint"))
            if evidence_source and current_source and evidence_source != current_source:
                findings.append(CapabilityFinding("stale-capability-evidence", f"$.evidence[{evidence_id}].source_fingerprint", "evidence source identity is stale", (evidence_id,)))
            artifact_ref = _text(item.get("artifact_ref"))
            if artifact_ref:
                candidate = Path(artifact_ref)
                if not candidate.is_absolute():
                    candidate = root / candidate
                if not candidate.is_file():
                    findings.append(CapabilityFinding("evidence-artifact-missing", f"$.evidence[{evidence_id}].artifact_ref", "referenced evidence artifact does not exist", (evidence_id,)))
    findings.extend(_scope_evidence_gaps(payload, claim_scope, outcomes, paths, failures, qualities, evidence, verified_receipts))
    deduped: dict[tuple[str, str, tuple[str, ...]], CapabilityFinding] = {}
    for finding in findings:
        deduped[(finding.code, finding.path, finding.affected_ids)] = finding
    findings = [deduped[key] for key in sorted(deduped)]
    skipped_checks = [
        {"evidence_id": evidence_id, "status": _text(item.get("result")), "reason": "evidence is not a current passing terminal result"}
        for evidence_id, item in sorted(evidence.items())
        if _text(item.get("result")) in {"skipped", "not_run", "blocked"}
    ]
    status = "pass" if not findings else "blocked"
    return {
        "schema_version": "skillguard.capability_audit.v1",
        "artifact_type": "skillguard_capability_audit",
        "status": status,
        "decision": "pass" if status == "pass" else "block",
        "claim_scope": claim_scope,
        "target_skill_id": _text(payload.get("target_skill_id")),
        "functional_closure_id": _text(payload.get("functional_closure_id")),
        "outcome_results": [
            {"outcome_id": outcome_id, "path_id": _text(row.get("path_id")), "status": "pass" if not any(f.affected_ids and outcome_id in f.affected_ids for f in findings) else "blocked"}
            for outcome_id, row in sorted(outcomes.items())
        ],
        "path_results": [
            {"path_id": path_id, "status": "pass" if not any(f.affected_ids and path_id in f.affected_ids for f in findings) else "blocked", "stage_count": len(row.get("stages", [])) if isinstance(row.get("stages"), list) else 0}
            for path_id, row in sorted(paths.items())
        ],
        "evidence_axes": [
            {
                "evidence_id": evidence_id,
                "execution_depth": _text(row.get("execution_depth")),
                "environment_scope": _text(row.get("environment_scope")),
                "quality_level": _text(row.get("quality_level")),
                "result": _text(row.get("result")),
                "assertion_categories": _ids(row.get("assertion_categories")),
                "execution_decision": "pass" if EVIDENCE_DEPTH_ORDER.get(_text(row.get("execution_depth")), -1) >= EVIDENCE_DEPTH_ORDER["fixture"] else "blocked",
                "environment_decision": "pass" if _text(row.get("environment_scope")) in {"single", "matrix", "field"} else "blocked",
                "quality_decision": "pass" if QUALITY_ORDER.get(_text(row.get("quality_level")), -1) >= QUALITY_ORDER["deterministic"] else "blocked",
                "result_decision": "pass" if evidence_id in verified_receipts else "blocked",
                "receipt_decision": "verified" if evidence_id in verified_receipts else "blocked",
                "freshness_decision": "current" if evidence_id in verified_receipts and not _text(row.get("freshness_reason")) else "stale",
            }
            for evidence_id, row in sorted(evidence.items())
        ],
        "findings": [finding.to_dict() for finding in findings],
        "gap_codes": sorted({finding.code for finding in findings}),
        "affected_ids": sorted({value for finding in findings for value in finding.affected_ids if value}),
        "repair_actions": [finding.repair_action for finding in findings],
        "skipped_checks": skipped_checks,
        "residual_risk": [
            "A passing capability audit verifies exact current target-owned producer receipts and declared closure scope; it does not decide domain correctness or replace target-native checks.",
            "Historical specifications are provenance inputs, not current authority; stale identity requires a direct current rewrite.",
        ],
        "claim_boundary": _text(payload.get("claim_boundary")) or "This audit does not prove arbitrary target-domain correctness, publication, or future AI behavior.",
        "source_fingerprint": _source_fingerprint(root) if root is not None else "",
        "surface_inventory": surface_report,
    }


def load_target_documents(target_root: Path) -> tuple[Mapping[str, Any] | None, Mapping[str, Any] | None, object | None, list[str]]:
    """Load current target documents without converting any former shape."""

    target_root = target_root.resolve()
    errors: list[str] = []
    contract: Mapping[str, Any] | None = None
    manifest: Mapping[str, Any] | None = None
    closure: object | None = None
    for name, destination in (("contract-source.json", "contract"), ("check-manifest.json", "manifest"), ("functional-closure.json", "closure")):
        value, error = _load_json(target_root / ".skillguard" / name)
        if error == "missing":
            if destination == "closure":
                errors.append("missing-functional-contract")
            else:
                errors.append(f"missing-{destination}")
        elif error:
            errors.append(f"unreadable-{destination}")
        elif destination == "contract" and isinstance(value, Mapping):
            contract = value
        elif destination == "manifest" and isinstance(value, Mapping):
            manifest = value
        elif destination == "closure":
            closure = value
    return contract, manifest, closure, errors


def audit_target_capability(
    target_root: Path,
    *,
    claim_scope: str = "routine",
    closure_path: Path | None = None,
    repository_root: Path | None = None,
    require_surface_inventory: bool = False,
    surface_command_surface: Sequence[Mapping[str, Any]] = (),
    surface_route_entries: Sequence[Mapping[str, Any]] = (),
    surface_command_handlers: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    target_root = target_root.resolve()
    path = (closure_path or target_root / ".skillguard" / "functional-closure.json").resolve()
    closure, error = _load_json(path)
    contract, manifest, _loaded_closure, document_errors = load_target_documents(target_root)
    if error == "missing":
        return {
            "schema_version": "skillguard.capability_audit.v1",
            "artifact_type": "skillguard_capability_audit",
            "status": "blocked", "decision": "block", "claim_scope": claim_scope,
            "target_skill_id": "", "functional_closure_id": "",
            "outcome_results": [], "path_results": [], "evidence_axes": [],
            "findings": [CapabilityFinding("missing-functional-contract", ".skillguard/functional-closure.json", "target has no current functional-closure record", (), "Write a current target-owned functional-closure record; do not infer one from SKILL.md or deep-pass.").to_dict()],
            "gap_codes": ["missing-functional-contract"], "affected_ids": [],
            "repair_actions": ["Write a current target-owned functional-closure record; do not infer one from SKILL.md or deep-pass."],
            "skipped_checks": [], "residual_risk": ["No functional claim is licensed."],
            "claim_boundary": "Missing functional closure is a visible blocker, not a reason to use a fallback record.",
            "source_fingerprint": _source_fingerprint(target_root),
            "document_errors": sorted(set(document_errors)),
        }
    if error:
        return {
            "schema_version": "skillguard.capability_audit.v1", "artifact_type": "skillguard_capability_audit",
            "status": "blocked", "decision": "block", "claim_scope": claim_scope,
            "target_skill_id": "", "functional_closure_id": "", "outcome_results": [], "path_results": [], "evidence_axes": [],
            "findings": [CapabilityFinding("functional-closure-unreadable", ".skillguard/functional-closure.json", error).to_dict()],
            "gap_codes": ["functional-closure-unreadable"], "affected_ids": [], "repair_actions": ["Rewrite the current functional-closure record as valid JSON."], "skipped_checks": [], "residual_risk": [], "claim_boundary": "Unreadable current authority blocks capability claims.", "source_fingerprint": _source_fingerprint(target_root), "document_errors": sorted(set(document_errors)),
        }
    report = validate_functional_closure(
        closure,
        target_root=target_root,
        repository_root=repository_root,
        contract=contract,
        check_manifest=manifest,
        claim_scope=claim_scope,
        require_surface_inventory=require_surface_inventory,
        surface_command_surface=surface_command_surface,
        surface_route_entries=surface_route_entries,
        surface_command_handlers=surface_command_handlers,
    )
    report["target_path"] = "." if target_root.name == "." else target_root.name
    report["document_errors"] = sorted(set(document_errors) - {"missing-functional-contract"})
    if report["document_errors"]:
        report["findings"].extend({"code": code, "path": ".skillguard", "message": "current target document is missing or unreadable", "affected_ids": [], "repair_action": "Directly rewrite the missing current target document and rerun the audit."} for code in report["document_errors"])
        report["gap_codes"] = sorted(set(report["gap_codes"]) | set(report["document_errors"]))
        report["status"] = "blocked"
        report["decision"] = "block"
    return report


def _discover_target_roots(root: Path) -> list[Path]:
    root = root.resolve()
    if (root / "SKILL.md").is_file() or (root / ".skillguard" / "functional-closure.json").is_file():
        return [root]
    candidates: list[Path] = []
    ignored_discovery_parts = {".git", "__pycache__", ".pytest_cache", ".sg-runtime", "tests", "fixtures"}
    for skill_file in root.rglob("SKILL.md"):
        if any(part.casefold() in ignored_discovery_parts for part in skill_file.relative_to(root).parts):
            continue
        candidates.append(skill_file.parent)
    for closure in root.rglob(".skillguard/functional-closure.json"):
        if any(part.casefold() in ignored_discovery_parts for part in closure.relative_to(root).parts):
            continue
        candidates.append(closure.parent.parent)
    return sorted(set(path.resolve() for path in candidates), key=lambda path: path.as_posix())


def _registry_lifecycle(registry: Mapping[str, Any] | None) -> dict[str, str]:
    if not isinstance(registry, Mapping):
        return {}
    result: dict[str, str] = {}
    for row in registry.get("entries", []):
        if isinstance(row, Mapping) and _text(row.get("skill_id")):
            lifecycle = _text(row.get("lifecycle")) or "active"
            # The current functional registry uses ``retired``.  Existing
            # private portfolio scope projections use typed retired/excluded
            # labels; they are accepted only as an explicit exclusion signal,
            # never as an implicit active fallback.
            if lifecycle in {"retired_private", "excluded_private", "excluded_system"}:
                lifecycle = "retired"
            result[_text(row.get("skill_id"))] = lifecycle
    return result


def audit_capabilities(root: Path, *, claim_scope: str = "routine", registry: Mapping[str, Any] | None = None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    lifecycle = _registry_lifecycle(registry)
    for target in _discover_target_roots(root):
        closure, _error = _load_json(target / ".skillguard" / "functional-closure.json")
        skill_id = _text(closure.get("target_skill_id")) if isinstance(closure, Mapping) else target.name
        if lifecycle.get(skill_id) == "retired":
            rows.append({"skill_id": skill_id, "status": "retired_excluded", "target_path": _relative(target, root), "exclusion_reason": "registry lifecycle is retired"})
            continue
        report = audit_target_capability(target, claim_scope=claim_scope)
        report["skill_id"] = skill_id
        report["target_path"] = _relative(target, root)
        rows.append(report)
    if not rows:
        rows.append({"skill_id": "", "status": "blocked", "gap_codes": ["no-capability-targets"], "findings": [CapabilityFinding("no-capability-targets", str(root), "no target functional-closure records were found").to_dict()]})
    active_rows = [row for row in rows if row.get("status") != "retired_excluded"]
    blocked = [row for row in active_rows if row.get("status") != "pass"]
    return {
        "schema_version": "skillguard.capability_portfolio_audit.v1",
        "artifact_type": "skillguard_capability_portfolio_audit",
        "status": "pass" if not blocked else "blocked",
        "decision": "pass" if not blocked else "block",
        "claim_scope": claim_scope,
        "rows": rows,
        "counts": {"discovered": len(rows), "active": len(active_rows), "passed": len(active_rows) - len(blocked), "blocked": len(blocked), "retired_excluded": sum(row.get("status") == "retired_excluded" for row in rows)},
        "gap_codes": sorted({code for row in blocked for code in row.get("gap_codes", [])}),
        "residual_risk": ["Portfolio status preserves every active child result; a passing child never hides a missing, stale, failed, or blocked child."],
        "claim_boundary": "This portfolio report does not prove a fleet-wide domain claim, publication, or release; it reports only the named target records and current evidence.",
    }


def _registry_shape_findings(registry: object) -> list[CapabilityFinding]:
    findings: list[CapabilityFinding] = []
    if not isinstance(registry, Mapping):
        return [CapabilityFinding("portfolio-registry-not-object", "$", "private portfolio registry must be an object")]
    unknown_root = sorted(set(registry) - {"schema_version", "registry_id", "generated_at", "entries", "claim_boundary"})
    for key in unknown_root:
        findings.append(CapabilityFinding("portfolio-registry-additional-field", f"$.{key}", "unsupported private registry field"))
    if _text(registry.get("schema_version")) != PORTFOLIO_REGISTRY_SCHEMA:
        findings.append(CapabilityFinding("unsupported-portfolio-registry-schema", "$.schema_version", f"expected {PORTFOLIO_REGISTRY_SCHEMA}"))
    entries = registry.get("entries")
    if not isinstance(entries, list) or not entries:
        findings.append(CapabilityFinding("portfolio-registry-entries-missing", "$.entries", "registry needs at least one entry"))
        return findings
    seen: set[str] = set()
    for number, row in enumerate(entries):
        path = f"$.entries[{number}]"
        if not isinstance(row, Mapping):
            findings.append(CapabilityFinding("portfolio-registry-entry-not-object", path, "entry must be an object"))
            continue
        unknown_entry = sorted(set(row) - {"skill_id", "lifecycle", "retirement_reason", "canonical_source", "installed_path", "repository_identity", "visibility", "release_policy"})
        for key in unknown_entry:
            findings.append(CapabilityFinding("portfolio-registry-additional-field", f"{path}.{key}", "unsupported portfolio entry field", (_text(row.get("skill_id")),)))
        skill_id = _text(row.get("skill_id"))
        if not skill_id or skill_id in seen:
            findings.append(CapabilityFinding("portfolio-registry-skill-id-invalid", f"{path}.skill_id", "skill id is missing or duplicated", (skill_id,)))
        seen.add(skill_id)
        lifecycle = _text(row.get("lifecycle"))
        if lifecycle not in {"active", "retired"}:
            findings.append(CapabilityFinding("portfolio-registry-lifecycle-invalid", f"{path}.lifecycle", "lifecycle must be active or retired", (skill_id,)))
        source = row.get("canonical_source")
        if isinstance(source, Mapping):
            for key in sorted(set(source) - {"root", "skill_path"}):
                findings.append(CapabilityFinding("portfolio-registry-additional-field", f"{path}.canonical_source.{key}", "unsupported canonical source field", (skill_id,)))
        if lifecycle == "active" and (not isinstance(source, Mapping) or not _text(source.get("root")) or not _text(source.get("skill_path"))):
            findings.append(CapabilityFinding("missing-source-owner", f"{path}.canonical_source", "active entry must name one canonical source", (skill_id,)))
        for field in ("installed_path", "repository_identity", "visibility", "release_policy"):
            if not _text(row.get(field)):
                findings.append(CapabilityFinding("portfolio-registry-required-field-missing", f"{path}.{field}", "active entry requires this field", (skill_id,)))
        if _text(row.get("visibility")) not in {"", "private", "public"}:
            findings.append(CapabilityFinding("portfolio-registry-visibility-invalid", f"{path}.visibility", "visibility must be private or public", (skill_id,)))
        if _text(row.get("release_policy")) not in {"", "no_publish", "private_only", "public_release"}:
            findings.append(CapabilityFinding("portfolio-registry-release-policy-invalid", f"{path}.release_policy", "release policy is invalid", (skill_id,)))
        if lifecycle == "retired" and not _text(row.get("retirement_reason")):
            findings.append(CapabilityFinding("retired-reason-missing", f"{path}.retirement_reason", "retired entry needs an explicit reason", (skill_id,)))
    return findings


def validate_portfolio_registry(registry: object) -> tuple[CapabilityFinding, ...]:
    """Return deterministic shape findings for one explicit private registry."""

    return tuple(_registry_shape_findings(registry))


def load_private_portfolio_registry(path: Path) -> tuple[Mapping[str, Any] | None, tuple[CapabilityFinding, ...]]:
    """Load exactly the named registry; never search, merge, or migrate another one."""

    value, error = _load_json(path.resolve())
    if error:
        return None, (CapabilityFinding("portfolio-registry-unreadable", "registry", error, repair_action="Rewrite the explicitly named current private registry and rerun source-sync."),)
    findings = validate_portfolio_registry(value)
    return (value if isinstance(value, Mapping) else None), findings


def _semantic_file_hash(path: Path) -> str:
    value, error = _load_json(path)
    if error is None:
        return _json_fingerprint(value)
    try:
        return "sha256:" + hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()
    except OSError:
        return ""


def _closure_strength(root: Path) -> tuple[int, int, int]:
    closure, error = _load_json(root / ".skillguard" / "functional-closure.json")
    if error or not isinstance(closure, Mapping):
        return (-1, -1, -1)
    depths = [EVIDENCE_DEPTH_ORDER.get(_text(item.get("execution_depth")), -1) for item in closure.get("evidence", []) if isinstance(item, Mapping) and _text(item.get("result")) == "pass"]
    passed = sum(_text(item.get("result")) == "pass" for item in closure.get("evidence", []) if isinstance(item, Mapping))
    quality = max((QUALITY_ORDER.get(_text(item.get("quality_level")), -1) for item in closure.get("evidence", []) if isinstance(item, Mapping) and _text(item.get("result")) == "pass"), default=-1)
    return (max(depths, default=-1), passed, quality)


def check_source_sync(registry: object) -> dict[str, Any]:
    """Compare explicit private source owners with installed projections."""

    findings = _registry_shape_findings(registry)
    if not isinstance(registry, Mapping):
        return {"schema_version": "skillguard.source_sync_audit.v1", "artifact_type": "skillguard_source_sync_audit", "status": "blocked", "decision": "block", "rows": [], "findings": [finding.to_dict() for finding in findings], "gap_codes": sorted({finding.code for finding in findings}), "claim_boundary": "Invalid private registry does not establish source ownership."}
    rows: list[dict[str, Any]] = []
    for entry in registry.get("entries", []):
        if not isinstance(entry, Mapping):
            continue
        skill_id = _text(entry.get("skill_id"))
        lifecycle = _text(entry.get("lifecycle"))
        if lifecycle == "retired":
            rows.append({"skill_id": skill_id, "lifecycle": "retired", "status": "retired_excluded", "source_path": "private_registry_source", "installed_path": "private_registry_installed"})
            continue
        source_decl = entry.get("canonical_source")
        source_root_text = _text(source_decl.get("root")) if isinstance(source_decl, Mapping) else ""
        skill_path_text = _text(source_decl.get("skill_path")) if isinstance(source_decl, Mapping) else ""
        source = (Path(source_root_text) / skill_path_text).resolve() if source_root_text and skill_path_text else None
        installed_text = _text(entry.get("installed_path"))
        installed = Path(installed_text).resolve() if installed_text else None
        row_findings: list[CapabilityFinding] = []
        if source is None or not source.is_dir():
            row_findings.append(CapabilityFinding("missing-source-owner", "canonical_source", "active skill source is missing or ambiguous", (skill_id,)))
        if installed is None or not installed.is_dir():
            row_findings.append(CapabilityFinding("installed-source-missing", "installed_path", "installed target projection is missing", (skill_id,)))
        source_hashes: dict[str, str] = {}
        installed_hashes: dict[str, str] = {}
        if source is not None and source.is_dir():
            source_hashes = {name: _semantic_file_hash(source / name) for name in SOURCE_FILES if (source / name).is_file()}
        if installed is not None and installed.is_dir():
            installed_hashes = {name: _semantic_file_hash(installed / name) for name in SOURCE_FILES if (installed / name).is_file()}
        for name in SOURCE_FILES:
            if name in installed_hashes and name not in source_hashes:
                row_findings.append(CapabilityFinding("source-to-installed-downgrade", name, "installed projection has protection absent from canonical source", (skill_id, name), "Directly restore the current source record before synchronization; do not add a compatibility reader."))
        for name in ("SKILL.md", ".skillguard/contract-source.json", ".skillguard/check-manifest.json", ".skillguard/functional-closure.json"):
            if name not in source_hashes:
                row_findings.append(CapabilityFinding("source-current-authority-missing", name, "active canonical source is missing a required current authority", (skill_id,)))
        if source is not None and installed is not None and _closure_strength(source) < _closure_strength(installed):
            row_findings.append(CapabilityFinding("source-to-installed-downgrade", ".skillguard/functional-closure.json", "canonical source has weaker functional evidence than installed projection", (skill_id,), "Directly upgrade the canonical source and rerun source-sync before replacing the installed projection."))
        if source_hashes != installed_hashes and not any(f.code == "source-to-installed-downgrade" for f in row_findings):
            row_findings.append(CapabilityFinding("source-installed-identity-drift", "source_and_installed", "source and installed current authorities differ", (skill_id,), "Rebuild the installed projection from the exact current source and verify parity."))
        rows.append({"skill_id": skill_id, "lifecycle": lifecycle, "status": "pass" if not row_findings else "blocked", "source_path": "canonical_source", "installed_path": "installed_projection", "source_file_count": len(source_hashes), "installed_file_count": len(installed_hashes), "findings": [finding.to_dict() for finding in row_findings], "source_fingerprint": _source_fingerprint(source) if source is not None and source.is_dir() else "", "installed_fingerprint": _source_fingerprint(installed) if installed is not None and installed.is_dir() else ""})
        findings.extend(row_findings)
    return {
        "schema_version": "skillguard.source_sync_audit.v1",
        "artifact_type": "skillguard_source_sync_audit",
        "status": "pass" if not findings else "blocked",
        "decision": "pass" if not findings else "block",
        "rows": rows,
        "findings": [finding.to_dict() for finding in sorted(findings, key=lambda item: (item.code, item.path, item.affected_ids))],
        "gap_codes": sorted({finding.code for finding in findings}),
        "retired_excluded": [row["skill_id"] for row in rows if row.get("status") == "retired_excluded"],
        "residual_risk": ["Source-sync checks identities and protection strength only; they do not execute the target domain workflow or prove publication."],
        "claim_boundary": "Private source and installed paths are intentionally sanitized. This report does not grant source, install, Git, tag, or release authority to any other identity.",
    }


__all__ = [
    "CLAIM_SCOPES",
    "FUNCTIONAL_CLOSURE_SCHEMA",
    "PORTFOLIO_REGISTRY_SCHEMA",
    "CapabilityFinding",
    "audit_capabilities",
    "audit_target_capability",
    "check_source_sync",
    "load_private_portfolio_registry",
    "load_target_documents",
    "validate_portfolio_registry",
    "validate_functional_closure",
]
