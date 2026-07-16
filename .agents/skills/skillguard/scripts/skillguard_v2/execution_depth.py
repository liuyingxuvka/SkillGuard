"""Target-neutral declared-check evaluation and immutable receipts."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contract_schema import (
    TARGET_EXECUTION_RECEIPT_SCHEMA,
    SchemaFinding,
    validate_depth_profile,
    validate_runtime_payload,
)
from .declared_check_supervision import (
    DeclaredCheckError,
    freeze_declared_check_inventory,
    reconcile_declared_check_results,
)
from .installation_receipt import (
    VerifiedInstallationContext,
    verify_scheduled_production_installation_identity,
)
from .native_evidence_identity import (
    DEPTH_EVIDENCE_DOMAINS,
    scheduled_production_identity as validate_scheduled_production_identity,
)
from .runtime_fingerprint import guard_execution_runtime_fingerprint
from .execution_records import filesystem_path


EXECUTION_DEPTH_PASS = "EXECUTION_DEPTH_PASS"
BOUNDED_PARTIAL = "BOUNDED_PARTIAL"
BOUNDARY_ONLY = "BOUNDARY_ONLY"
SHALLOW_BLOCKED = "SHALLOW_BLOCKED"
NOT_RUN = "NOT_RUN"
DEPTH_CONTRACT_MISSING = "DEPTH_CONTRACT_MISSING"
PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
STALE = "STALE"


def _canonical_json_bytes(payload: object) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _canonical_hash(payload: object) -> str:
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest().upper()


def _execution_runtime_identity(
    explicit_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve one non-selectable location-derived identity for runtime work."""

    return dict(explicit_identity or guard_execution_runtime_fingerprint())


@dataclass
class DepthError(ValueError):
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


@dataclass(frozen=True)
class DepthEvaluation:
    status: str
    enforcement_decision: str
    dimension_results: tuple[Mapping[str, Any], ...]
    coverage_universe_results: tuple[Mapping[str, Any], ...]
    obligation_results: tuple[Mapping[str, Any], ...]
    evidence_contributions: tuple[Mapping[str, Any], ...]
    provider_runtime_audit: Mapping[str, Any]
    declared_check_results: tuple[Mapping[str, Any], ...]
    unresolved_check_ids: tuple[str, ...]
    uncovered_obligation_ids: tuple[str, ...]
    blockers: tuple[str, ...]
    limitations: tuple[str, ...]
    claim_boundary: str

    @property
    def ok(self) -> bool:
        return self.status == EXECUTION_DEPTH_PASS

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "artifact_type": "skillguard_execution_depth_evaluation",
            "status": self.status,
            "ok": self.ok,
            "enforcement_decision": self.enforcement_decision,
            "dimension_results": [dict(row) for row in self.dimension_results],
            "coverage_universe_results": [
                dict(row) for row in self.coverage_universe_results
            ],
            "obligation_results": [dict(row) for row in self.obligation_results],
            "evidence_contributions": [
                dict(row) for row in self.evidence_contributions
            ],
            "provider_runtime_audit": dict(self.provider_runtime_audit),
            "declared_check_results": [
                dict(row) for row in self.declared_check_results
            ],
            "unresolved_check_ids": list(self.unresolved_check_ids),
            "uncovered_obligation_ids": list(self.uncovered_obligation_ids),
            "blockers": list(self.blockers),
            "limitations": list(self.limitations),
            "claim_boundary": self.claim_boundary,
        }
        payload["evaluation_hash"] = _canonical_hash(payload)
        return payload


def _empty_evaluation(status: str, blocker: str) -> DepthEvaluation:
    return DepthEvaluation(
        status=status,
        enforcement_decision="block",
        dimension_results=(),
        coverage_universe_results=(),
        obligation_results=(),
        evidence_contributions=(),
        provider_runtime_audit={"status": "not_run", "blockers": [blocker]},
        declared_check_results=(),
        unresolved_check_ids=(),
        uncovered_obligation_ids=(),
        blockers=(blocker,),
        limitations=("No current complete declared-check execution is proven.",),
        claim_boundary=(
            "SkillGuard reports only the target-declared execution boundary; "
            "it does not infer target-domain correctness."
        ),
    )


def _profile_findings(profile: object) -> tuple[SchemaFinding, ...]:
    return validate_depth_profile(profile)


def profile_fingerprint(profile: Mapping[str, Any]) -> str:
    findings = _profile_findings(profile)
    if findings:
        raise DepthError(findings[0].code, findings[0].message)
    return _canonical_hash(profile)


def _root_role_bindings(
    profile: Mapping[str, Any],
    *,
    repository_root: Path,
    target_root: Path,
    current_fingerprints: Mapping[str, Any],
    inventory_hash: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "skillguard.root_role_bindings.current",
        "repository_root": {
            "role_token": "repository_root",
            "profile_fingerprint": _canonical_hash(profile),
            "declared_check_inventory_hash": inventory_hash,
        },
        "target_root": {
            "role_token": "target_root",
            "input_fingerprint_hash": _canonical_hash(current_fingerprints),
        },
        "roots_distinct": repository_root.resolve() != target_root.resolve(),
    }
    payload["binding_hash"] = _canonical_hash(payload)
    return payload


def evaluate_execution_depth(
    profile: Mapping[str, Any] | None,
    observations: Sequence[Mapping[str, Any]],
    *,
    context: Mapping[str, Any] | None = None,
) -> DepthEvaluation:
    """Evaluate only declared obligations and declared-check terminal results."""

    context = context or {}
    if profile is None:
        return _empty_evaluation(DEPTH_CONTRACT_MISSING, "depth_profile_missing")
    findings = _profile_findings(profile)
    if findings:
        return _empty_evaluation(
            DEPTH_CONTRACT_MISSING, f"depth_profile_invalid:{findings[0].code}"
        )
    if context.get("run_started", bool(observations)) is not True:
        return _empty_evaluation(NOT_RUN, "target_execution_not_run")
    if context.get("current", True) is not True:
        return _empty_evaluation(STALE, "target_execution_inputs_stale")
    if context.get("boundary_only", False) is True:
        return _empty_evaluation(BOUNDARY_ONLY, "only_boundary_checks_observed")

    raw_reconciliation = context.get("declared_check_reconciliation", {})
    reconciliation = (
        dict(raw_reconciliation)
        if isinstance(raw_reconciliation, Mapping)
        else {
            "status": "blocked",
            "blockers": ["declared_check_reconciliation_missing"],
            "check_results": [],
            "unresolved_check_ids": [],
        }
    )
    blockers = [str(item) for item in reconciliation.get("blockers", [])]
    unresolved_check_ids = tuple(
        sorted(str(item) for item in reconciliation.get("unresolved_check_ids", []))
    )

    provider = context.get("provider_runtime_audit", {})
    provider_runtime_audit = (
        dict(provider)
        if isinstance(provider, Mapping)
        else {"status": "blocked", "blockers": ["provider_runtime_audit_missing"]}
    )
    if provider_runtime_audit.get("status") != "passed":
        blockers.extend(
            str(item)
            for item in provider_runtime_audit.get(
                "blockers", ["provider_runtime_readiness_not_proven"]
            )
        )

    # SkillGuard does not interpret domain observations.  Any coverage, oracle,
    # good/bad case, or semantic depth rule is implemented by a target-declared
    # check and is represented here only by that check's current terminal receipt.
    obligation_results: list[dict[str, Any]] = []
    contribution_rows: list[dict[str, Any]] = []
    coverage_results: list[dict[str, Any]] = []
    dimension_results: list[dict[str, Any]] = []

    blockers = sorted(dict.fromkeys(blockers))
    uncovered = tuple(
        sorted(
            row["obligation_id"]
            for row in obligation_results
            if row["status"] != "passed"
        )
    )
    if not blockers and not uncovered and reconciliation.get("status") == "passed":
        status = EXECUTION_DEPTH_PASS
    elif provider_runtime_audit.get("status") != "passed":
        status = PROVIDER_UNAVAILABLE
    else:
        status = SHALLOW_BLOCKED
    return DepthEvaluation(
        status=status,
        enforcement_decision="allow" if status == EXECUTION_DEPTH_PASS else "block",
        dimension_results=tuple(dimension_results),
        coverage_universe_results=tuple(coverage_results),
        obligation_results=tuple(obligation_results),
        evidence_contributions=tuple(contribution_rows),
        provider_runtime_audit=provider_runtime_audit,
        declared_check_results=tuple(
            dict(row) for row in reconciliation.get("check_results", [])
        ),
        unresolved_check_ids=unresolved_check_ids,
        uncovered_obligation_ids=uncovered,
        blockers=tuple(blockers),
        limitations=(
            "The receipt proves only the target-declared checks and this exact execution.",
            "The target skill remains the sole owner of domain meaning and native oracles.",
        ),
        claim_boundary=(
            "SkillGuard verifies declared-check completeness, identity, freshness, and "
            "closure consumption only."
        ),
    )


def _depth_receipts_root(run_root: Path) -> Path:
    return filesystem_path(run_root / "depth-receipts")


def load_target_execution_receipts(run_root: Path) -> tuple[Mapping[str, Any], ...]:
    root = _depth_receipts_root(run_root)
    if not root.is_dir():
        return ()
    rows: list[Mapping[str, Any]] = []
    for path in sorted(root.glob("depth-*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DepthError(
                "depth_receipt_unreadable", f"{path.name}:{type(exc).__name__}"
            ) from exc
        if not isinstance(payload, Mapping):
            raise DepthError("depth_receipt_not_object", path.name)
        findings = validate_runtime_payload(payload, TARGET_EXECUTION_RECEIPT_SCHEMA)
        if findings:
            raise DepthError(findings[0].code, findings[0].message)
        unsigned = dict(payload)
        stored_hash = str(unsigned.pop("receipt_hash", ""))
        if stored_hash != _canonical_hash(unsigned):
            raise DepthError("depth_receipt_hash_mismatch", path.name)
        rows.append(payload)
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                int(row.get("sequence", 0)),
                str(row.get("created_at", "")),
                str(row.get("receipt_id", "")),
            ),
        )
    )


def issue_target_execution_receipt(
    run_root: Path,
    contract: Mapping[str, Any],
    packet: Mapping[str, Any],
    *,
    current_fingerprints: Mapping[str, Any],
    repository_root: Path | None = None,
    target_root: Path | None = None,
    active_runtime_identity: Mapping[str, Any] | None = None,
    verified_installation_context: VerifiedInstallationContext | None = None,
) -> Mapping[str, Any]:
    """Write one immutable generic declared-check execution receipt."""

    from .receipts import derive_freshness, load_receipts
    from .run_store import append_event, load_check_manifest_snapshot, load_run, utc_now

    profile = contract.get("depth_profile")
    if not isinstance(profile, Mapping):
        raise DepthError("depth_profile_missing", "compiled contract has no depth_profile")
    findings = validate_depth_profile(profile)
    if findings:
        raise DepthError(findings[0].code, findings[0].message)
    if repository_root is None or target_root is None:
        raise DepthError(
            "execution_depth_root_missing",
            "repository_root and target_root are required",
        )
    run = load_run(run_root)
    request_fingerprint = str(run.get("request_fingerprint", ""))
    if packet.get("request_fingerprint") not in (None, request_fingerprint):
        raise DepthError("depth_packet_request_fingerprint_mismatch", request_fingerprint)
    manifest = load_check_manifest_snapshot(run_root)
    declarations = [
        row for row in manifest.get("checks", []) if isinstance(row, Mapping)
    ]
    required_check_ids = [str(item) for item in profile.get("native_check_ids", [])]
    try:
        inventory = freeze_declared_check_inventory(
            declarations, required_check_ids=required_check_ids
        )
    except DeclaredCheckError as exc:
        raise DepthError(exc.code, exc.message) from exc
    declaration_index = {
        str(row.get("check_id", "")): row for row in declarations
    }
    latest: dict[str, Mapping[str, Any]] = {}
    runtime_receipts = load_receipts(run_root)
    for receipt in runtime_receipts:
        evidence = receipt.get("evidence", {})
        if isinstance(evidence, Mapping):
            check_id = str(evidence.get("check_id", ""))
            if check_id in set(required_check_ids):
                latest[check_id] = receipt
    check_results: list[dict[str, Any]] = []
    for check_id in required_check_ids:
        declaration = declaration_index.get(check_id, {})
        receipt = latest.get(check_id)
        if receipt is None:
            check_results.append(
                {
                    "check_id": check_id,
                    "execution_owner_id": str(declaration.get("execution_owner_id", "")),
                    "request_fingerprint": request_fingerprint,
                    "disposition": "not_run",
                    "current": False,
                    "receipt_id": "",
                    "receipt_hash": "",
                }
            )
            continue
        freshness = derive_freshness(
            receipt, current_fingerprints, receipt_roots=(run_root,)
        )
        status = str(receipt.get("status", ""))
        disposition = status if status in {"passed", "failed", "skipped", "blocked", "timeout", "cancelled"} else "blocked"
        check_results.append(
            {
                "check_id": check_id,
                "execution_owner_id": str(declaration.get("execution_owner_id", "")),
                "request_fingerprint": request_fingerprint,
                "disposition": disposition,
                "current": freshness.current,
                "receipt_id": str(receipt.get("receipt_id", "")),
                "receipt_hash": str(receipt.get("receipt_hash", "")),
            }
        )
    try:
        reconciliation = reconcile_declared_check_results(
            inventory,
            check_results,
            request_fingerprint=request_fingerprint,
        )
    except DeclaredCheckError as exc:
        raise DepthError(exc.code, exc.message) from exc

    evidence_domain = str(packet.get("evidence_domain", "capability_validation"))
    scheduled = (
        dict(packet.get("scheduled_production_identity", {}))
        if isinstance(packet.get("scheduled_production_identity", {}), Mapping)
        else {}
    )
    if evidence_domain not in DEPTH_EVIDENCE_DOMAINS:
        raise DepthError("depth_evidence_domain_invalid", evidence_domain)
    if evidence_domain == "scheduled_production":
        scheduled = validate_scheduled_production_identity(scheduled)
        try:
            verify_scheduled_production_installation_identity(
                scheduled, verified_context=verified_installation_context
            )
        except (OSError, ValueError) as exc:
            raise DepthError(
                "scheduled_production_installation_not_current", str(exc)
            ) from exc
    elif scheduled:
        raise DepthError("non_production_schedule_identity_forbidden", evidence_domain)
    observation_binding = {
        "source": "declared_check_reconciliation",
        "inventory_hash": str(inventory.get("inventory_hash", "")),
        "reconciliation_hash": str(reconciliation.get("reconciliation_hash", "")),
    }

    actual_runtime = _execution_runtime_identity(active_runtime_identity)
    expected_runtime = profile.get("provider_runtime", {})
    provider_blockers: list[str] = []
    if not isinstance(expected_runtime, Mapping):
        expected_runtime = {}
        provider_blockers.append("provider_runtime_contract_missing")
    if actual_runtime.get("provider_id") != expected_runtime.get("provider_id"):
        provider_blockers.append("provider_id_mismatch")
    required_capabilities = {str(item) for item in expected_runtime.get("required_capability_ids", [])}
    observed_capabilities = {str(item) for item in actual_runtime.get("capability_ids", [])}
    for capability_id in sorted(required_capabilities - observed_capabilities):
        provider_blockers.append(f"provider_capability_missing:{capability_id}")
    provider_runtime_audit = {
        "status": "passed" if not provider_blockers else "blocked",
        "provider_id": str(actual_runtime.get("provider_id", "")),
        "runtime_contract_id": str(actual_runtime.get("runtime_contract_id", "")),
        "capability_ids": sorted(observed_capabilities),
        "blockers": provider_blockers,
        "runtime_identity_hash": _canonical_hash(actual_runtime),
    }
    evaluation = evaluate_execution_depth(
        profile,
        (),
        context={
            "run_started": True,
            "current": True,
            "boundary_only": packet.get("boundary_only", False) is True,
            "declared_check_reconciliation": reconciliation,
            "provider_runtime_audit": provider_runtime_audit,
        },
    )
    evaluation_payload = evaluation.to_dict()
    existing = load_target_execution_receipts(run_root)
    root_bindings = _root_role_bindings(
        profile,
        repository_root=repository_root.resolve(),
        target_root=target_root.resolve(),
        current_fingerprints=current_fingerprints,
        inventory_hash=str(inventory.get("inventory_hash", "")),
    )
    receipt: dict[str, Any] = {
        "schema_version": TARGET_EXECUTION_RECEIPT_SCHEMA,
        "sequence": len(existing) + 1,
        "run_id": str(run.get("run_id", "")),
        "target_skill_id": str(profile.get("target_skill_id", contract.get("skill_id", ""))),
        "contract_hash": str(contract.get("contract_hash", "")),
        "profile_id": str(profile.get("profile_id", "")),
        "profile_fingerprint": profile_fingerprint(profile),
        "integration_mode": str(profile.get("integration_mode", "")),
        "native_owner_id": str(profile.get("native_owner_id", "")),
        "native_route_ids": [str(item) for item in profile.get("native_route_ids", [])],
        "native_check_ids": required_check_ids,
        "request_fingerprint": request_fingerprint,
        "declared_check_inventory": inventory,
        "declared_check_results": [dict(row) for row in evaluation.declared_check_results],
        "unresolved_check_ids": list(evaluation.unresolved_check_ids),
        "evidence_domain": evidence_domain,
        "scheduled_production_identity": scheduled,
        "status": evaluation.status,
        "enforcement_decision": evaluation.enforcement_decision,
        "dimension_results": [dict(row) for row in evaluation.dimension_results],
        "coverage_universe_results": [dict(row) for row in evaluation.coverage_universe_results],
        "obligation_results": [dict(row) for row in evaluation.obligation_results],
        "evidence_contributions": [dict(row) for row in evaluation.evidence_contributions],
        "provider_runtime_audit": dict(evaluation.provider_runtime_audit),
        "observation_binding": observation_binding,
        "root_role_bindings": root_bindings,
        "root_role_bindings_hash": str(root_bindings["binding_hash"]),
        "uncovered_obligation_ids": list(evaluation.uncovered_obligation_ids),
        "blockers": list(evaluation.blockers),
        "active_runtime_identity": actual_runtime,
        "active_runtime_identity_hash": _canonical_hash(actual_runtime),
        "input_fingerprints": dict(current_fingerprints),
        "input_fingerprint_hash": _canonical_hash(current_fingerprints),
        "target_fingerprint": str(contract.get("contract_hash", "")),
        "runtime_fingerprint": str(actual_runtime.get("source_hash", "")),
        "evaluation_hash": str(evaluation_payload["evaluation_hash"]),
        "supersedes_receipt_id": str(existing[-1].get("receipt_id", "")) if existing else "",
        "claim_boundary": evaluation.claim_boundary,
        "created_at": utc_now(),
    }
    identity = dict(receipt)
    identity.pop("created_at", None)
    identity.pop("supersedes_receipt_id", None)
    identity.pop("sequence", None)
    receipt["receipt_id"] = f"depth-{_canonical_hash(identity)[:24].lower()}"
    for row in existing:
        if row.get("receipt_id") == receipt["receipt_id"]:
            return row
    receipt["receipt_hash"] = _canonical_hash(receipt)
    schema_findings = validate_runtime_payload(receipt, TARGET_EXECUTION_RECEIPT_SCHEMA)
    if schema_findings:
        raise DepthError(schema_findings[0].code, schema_findings[0].message)
    root = _depth_receipts_root(run_root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{receipt['receipt_id']}.json"
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError as exc:
        raise DepthError("depth_receipt_collision", path.name) from exc
    try:
        os.write(descriptor, _canonical_json_bytes(receipt))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    append_event(
        run_root,
        "target_execution_depth_evaluated",
        {
            "receipt_id": receipt["receipt_id"],
            "receipt_hash": receipt["receipt_hash"],
            "status": receipt["status"],
            "profile_id": receipt["profile_id"],
        },
    )
    return receipt


def evaluate_depth_receipt_gate(
    run_root: Path,
    contract: Mapping[str, Any],
    *,
    closure_profile: str,
    current_fingerprints: Mapping[str, Any],
    repository_root: Path | None = None,
    target_root: Path | None = None,
    owner_evidence_root: Path | None = None,
    verified_installation_context: VerifiedInstallationContext | None = None,
) -> Mapping[str, Any]:
    """Replay the latest receipt without executing a check owner."""

    del owner_evidence_root
    profile = contract.get("depth_profile")
    if not isinstance(profile, Mapping):
        return {
            "required": False,
            "ok": True,
            "status": "not_required",
            "receipt_id": "",
            "detail": "compiled contract has no execution-depth gate",
        }
    required = closure_profile in {
        str(item) for item in profile.get("required_closure_profiles", [])
    }
    if not required:
        return {
            "required": False,
            "ok": True,
            "status": "not_required",
            "receipt_id": "",
            "detail": f"depth gate is not required for {closure_profile}",
        }
    try:
        receipts = load_target_execution_receipts(run_root)
    except DepthError as exc:
        return {"required": True, "ok": False, "status": SHALLOW_BLOCKED, "receipt_id": "", "detail": exc.code}
    if not receipts:
        return {"required": True, "ok": False, "status": NOT_RUN, "receipt_id": "", "detail": "target execution receipt missing"}
    if repository_root is None or target_root is None:
        return {"required": True, "ok": False, "status": SHALLOW_BLOCKED, "receipt_id": "", "detail": "repository_root_or_target_root_missing"}
    receipt = receipts[-1]
    from .run_store import load_run

    current_runtime = _execution_runtime_identity()
    run = load_run(run_root)
    inventory = receipt.get("declared_check_inventory", {})
    current_bindings = _root_role_bindings(
        profile,
        repository_root=repository_root.resolve(),
        target_root=target_root.resolve(),
        current_fingerprints=current_fingerprints,
        inventory_hash=str(inventory.get("inventory_hash", "")) if isinstance(inventory, Mapping) else "",
    )
    if receipt.get("contract_hash") != contract.get("contract_hash"):
        status, detail = STALE, "contract hash changed"
    elif receipt.get("profile_fingerprint") != profile_fingerprint(profile):
        status, detail = STALE, "profile fingerprint changed"
    elif receipt.get("request_fingerprint") != run.get("request_fingerprint"):
        status, detail = STALE, "request fingerprint changed"
    elif receipt.get("input_fingerprint_hash") != _canonical_hash(current_fingerprints):
        status, detail = STALE, "target inputs changed"
    elif receipt.get("active_runtime_identity_hash") != _canonical_hash(current_runtime):
        status, detail = STALE, "active runtime identity changed"
    elif receipt.get("root_role_bindings") != current_bindings:
        status, detail = STALE, "repository/target role binding changed"
    elif receipt.get("unresolved_check_ids"):
        status, detail = SHALLOW_BLOCKED, "declared checks remain unresolved"
    else:
        status, detail = str(receipt.get("status", SHALLOW_BLOCKED)), "current declared-check receipt"
    if receipt.get("evidence_domain") == "scheduled_production":
        try:
            scheduled = validate_scheduled_production_identity(
                receipt.get("scheduled_production_identity")
            )
            verify_scheduled_production_installation_identity(
                scheduled, verified_context=verified_installation_context
            )
        except (OSError, ValueError):
            status, detail = STALE, "scheduled installation receipt is not current"
    return {
        "required": True,
        "ok": status == EXECUTION_DEPTH_PASS,
        "status": status,
        "receipt_id": str(receipt.get("receipt_id", "")),
        "detail": detail,
        "root_role_bindings": current_bindings,
        "root_role_bindings_hash": str(current_bindings["binding_hash"]),
        "uncovered_obligation_ids": list(receipt.get("uncovered_obligation_ids", [])),
        "unresolved_check_ids": list(receipt.get("unresolved_check_ids", [])),
        "blockers": list(receipt.get("blockers", [])),
    }
