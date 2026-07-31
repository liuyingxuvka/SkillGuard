"""Read-only assurance diagnostics over current SkillGuard authorities.

This module deliberately does not issue receipts, execute checks, resume runs,
or derive closure.  It only explains an already-materialized current authority
set and preserves the supplied closure terminal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .contract_compiler import canonical_hash
from .contract_schema import validate_check_manifest, validate_compiled_contract


ASSURANCE_INPUT_SCHEMA = "skillguard.assurance_diagnostic_input.v1"
ASSURANCE_REPORT_SCHEMA = "skillguard.assurance_diagnostics_report.v1"
MUTATION_CONTRACT_SCHEMA = "skillguard.target_mutation_contract.v1"
MUTATION_RECEIPT_SCHEMA = "skillguard.target_mutation_receipt.v1"

PASS_STATUSES = frozenset({"pass", "passed", "current", "closed", "closed_with_evidence"})
UNSAFE_ACTION_KINDS = frozenset(
    {
        "delete_obligation",
        "remove_obligation",
        "relax_obligation",
        "scope_obligation",
        "weaken_claim",
    }
)
ALLOWED_ROOT_FIELDS = frozenset(
    {
        "schema_version",
        "compiled_contract",
        "check_manifest",
        "closure_report",
        "receipts",
        "evaluation_budget",
        "proposed_next_actions",
        "mutation_contract",
        "mutation_receipt",
    }
)


@dataclass(frozen=True)
class AssuranceDiagnosticError(ValueError):
    code: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


@dataclass(frozen=True)
class BlockerAtom:
    atom_id: str
    owner_id: str
    check_id: str
    obligation_ids: tuple[str, ...]
    receipt_state: str
    dependency_ids: tuple[str, ...]
    provenance: str
    permitted_next_actions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "atom_id": self.atom_id,
            "owner_id": self.owner_id,
            "check_id": self.check_id,
            "obligation_ids": list(self.obligation_ids),
            "receipt_state": self.receipt_state,
            "dependency_ids": list(self.dependency_ids),
            "provenance": self.provenance,
            "permitted_next_actions": list(self.permitted_next_actions),
        }


@dataclass(frozen=True)
class NecessityWitness:
    atom_id: str
    newly_unexplained_obligation_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "atom_id": self.atom_id,
            "newly_unexplained_obligation_ids": list(
                self.newly_unexplained_obligation_ids
            ),
        }


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AssuranceDiagnosticError("field_not_object", field)
    return value


def _sequence(value: Any, field: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise AssuranceDiagnosticError("field_not_array", field)
    return value


def _rows(value: Any, field: str) -> tuple[Mapping[str, Any], ...]:
    rows = _sequence(value, field)
    if any(not isinstance(row, Mapping) for row in rows):
        raise AssuranceDiagnosticError("array_item_not_object", field)
    return tuple(row for row in rows if isinstance(row, Mapping))


def _status(value: Any) -> str:
    return str(value or "missing").strip().lower()


def _receipt_check_id(receipt: Mapping[str, Any]) -> str:
    direct = str(receipt.get("check_id", ""))
    if direct:
        return direct
    evidence = receipt.get("evidence")
    if isinstance(evidence, Mapping):
        return str(evidence.get("check_id", ""))
    return ""


def _receipt_state(receipt: Mapping[str, Any] | None) -> str:
    if receipt is None:
        return "missing"
    if receipt.get("current") is False:
        return "stale"
    freshness = receipt.get("freshness")
    if isinstance(freshness, Mapping):
        freshness_status = _status(freshness.get("status"))
        if freshness_status not in PASS_STATUSES:
            return "stale" if freshness_status == "stale" else freshness_status
    return _status(receipt.get("status", receipt.get("decision", "missing")))


def _latest_receipts(
    receipts: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    latest: dict[str, Mapping[str, Any]] = {}
    for receipt in receipts:
        check_id = _receipt_check_id(receipt)
        if check_id:
            latest[check_id] = receipt
    return latest


def _blocked_obligations(
    closure_report: Mapping[str, Any],
) -> tuple[str, ...]:
    rows = _rows(closure_report.get("obligation_results", []), "closure_report.obligation_results")
    return tuple(
        sorted(
            {
                str(row.get("obligation_id", ""))
                for row in rows
                if str(row.get("obligation_id", ""))
                and _status(row.get("status")) not in PASS_STATUSES
                and _status(row.get("status")) != "not_applicable"
            }
        )
    )


def _downstream_obligations(
    check_id: str,
    checks: Mapping[str, Mapping[str, Any]],
) -> tuple[str, ...]:
    """Return obligations blocked by this check, including dependency consumers."""

    reached = {check_id}
    changed = True
    while changed:
        changed = False
        for candidate_id, row in checks.items():
            dependencies = {
                str(item) for item in row.get("depends_on_check_ids", [])
            }
            if candidate_id not in reached and dependencies & reached:
                reached.add(candidate_id)
                changed = True
    obligations: set[str] = set()
    for reached_id in reached:
        obligations.update(
            str(item)
            for item in checks[reached_id].get("covers_obligation_ids", [])
            if str(item)
        )
    return tuple(sorted(obligations))


def derive_blocker_atoms(
    check_manifest: Mapping[str, Any],
    receipts: Sequence[Mapping[str, Any]],
    closure_report: Mapping[str, Any],
) -> tuple[BlockerAtom, ...]:
    check_rows = _rows(check_manifest.get("checks", []), "check_manifest.checks")
    checks = {
        str(row.get("check_id", "")): row
        for row in check_rows
        if str(row.get("check_id", ""))
    }
    latest = _latest_receipts(receipts)
    blocked_obligations = set(_blocked_obligations(closure_report))
    atoms: list[BlockerAtom] = []
    for check_id in sorted(checks):
        row = checks[check_id]
        receipt = latest.get(check_id)
        state = _receipt_state(receipt)
        if state in PASS_STATUSES:
            continue
        downstream = set(_downstream_obligations(check_id, checks))
        affected = tuple(sorted(downstream & blocked_obligations))
        if not affected:
            continue
        owner_id = str(row.get("execution_owner_id", ""))
        actions = (
            f"provide_current_receipt:{check_id}",
            f"inspect_owner:{owner_id or 'undeclared'}",
        )
        atoms.append(
            BlockerAtom(
                atom_id=f"blocker:{check_id}:{state}",
                owner_id=owner_id,
                check_id=check_id,
                obligation_ids=affected,
                receipt_state=state,
                dependency_ids=tuple(
                    sorted(
                        str(item)
                        for item in row.get("depends_on_check_ids", [])
                        if str(item)
                    )
                ),
                provenance=(
                    "missing_current_receipt"
                    if receipt is None
                    else f"current_manifest_receipt_state:{state}"
                ),
                permitted_next_actions=actions,
            )
        )

    explained = {
        obligation_id for atom in atoms for obligation_id in atom.obligation_ids
    }
    for obligation_id in sorted(blocked_obligations - explained):
        closure_row = next(
            (
                row
                for row in closure_report.get("obligation_results", [])
                if isinstance(row, Mapping)
                and str(row.get("obligation_id", "")) == obligation_id
            ),
            {},
        )
        state = _status(closure_row.get("status"))
        atoms.append(
            BlockerAtom(
                atom_id=f"blocker:closure:{obligation_id}:{state}",
                owner_id="closure-runtime-v2",
                check_id="",
                obligation_ids=(obligation_id,),
                receipt_state=state,
                dependency_ids=(),
                provenance="current_closure_obligation_result",
                permitted_next_actions=(
                    f"inspect_closure_obligation:{obligation_id}",
                ),
            )
        )
    return tuple(sorted(atoms, key=lambda atom: atom.atom_id))


def _covered(atoms: Sequence[BlockerAtom]) -> set[str]:
    return {
        obligation_id
        for atom in atoms
        for obligation_id in atom.obligation_ids
    }


def minimize_blockers(
    atoms: Sequence[BlockerAtom],
    blocked_obligation_ids: Sequence[str],
    evaluation_budget: int,
) -> Mapping[str, Any]:
    if evaluation_budget < 0:
        raise AssuranceDiagnosticError(
            "evaluation_budget_invalid", str(evaluation_budget)
        )
    target = set(blocked_obligation_ids)
    retained = list(sorted(atoms, key=lambda atom: atom.atom_id))
    evaluations = 0
    complete = True
    for atom in tuple(retained):
        if evaluations >= evaluation_budget:
            complete = False
            break
        evaluations += 1
        candidate = [item for item in retained if item.atom_id != atom.atom_id]
        if target.issubset(_covered(candidate)):
            retained = candidate

    witnesses: list[NecessityWitness] = []
    if complete:
        for atom in retained:
            without = [item for item in retained if item.atom_id != atom.atom_id]
            newly_unexplained = tuple(sorted(target - _covered(without)))
            if not newly_unexplained:
                raise AssuranceDiagnosticError(
                    "subset_minimality_internal_error", atom.atom_id
                )
            witnesses.append(
                NecessityWitness(
                    atom_id=atom.atom_id,
                    newly_unexplained_obligation_ids=newly_unexplained,
                )
            )
    status = "subset_minimal" if complete else "bounded_incomplete"
    return {
        "status": status,
        "computation_complete": complete,
        "minimum_cardinality_proven": False,
        "algorithm": "dependency_aware_deterministic_deletion.v1",
        "evaluation_budget": evaluation_budget,
        "evaluations_used": evaluations,
        "blocked_obligation_ids": sorted(target),
        "retained_atoms": [atom.to_dict() for atom in retained],
        "necessity_witnesses": [witness.to_dict() for witness in witnesses],
        "alternate_or_residual_atom_count": len(atoms) - len(retained),
    }


def _validate_action(action: Mapping[str, Any]) -> Mapping[str, Any]:
    action_id = str(action.get("action_id", ""))
    kind = str(action.get("kind", ""))
    if not action_id or not kind:
        raise AssuranceDiagnosticError("next_action_incomplete", action_id or kind)
    if kind in UNSAFE_ACTION_KINDS:
        return {
            "action_id": action_id,
            "kind": kind,
            "status": "rejected",
            "reason": "unauthorized_obligation_weakening",
        }
    return {
        "action_id": action_id,
        "kind": kind,
        "status": "advisory_only",
        "reason": "does_not_execute_or_change_closure",
    }


def project_mutation_adequacy(
    contract: Mapping[str, Any] | None,
    receipt: Mapping[str, Any] | None,
) -> Mapping[str, Any]:
    if contract is None:
        return {
            "status": "not_run",
            "reason": "target_mutation_contract_missing",
            "target_result": "",
        }
    if contract.get("schema_version") != MUTATION_CONTRACT_SCHEMA:
        return {
            "status": "blocked",
            "reason": "target_mutation_contract_schema_mismatch",
            "target_result": "",
        }
    required = {
        "target_id": contract.get("target_id"),
        "operators": contract.get("operators"),
        "oracle": contract.get("oracle"),
        "applicability": contract.get("applicability"),
        "equivalent_mutant_disposition": contract.get(
            "equivalent_mutant_disposition"
        ),
        "threshold": contract.get("threshold"),
        "check_id": contract.get("check_id"),
        "contract_hash": contract.get("contract_hash"),
    }
    missing = sorted(
        key
        for key, value in required.items()
        if value is None or value == "" or value == []
    )
    if missing:
        return {
            "status": "blocked",
            "reason": "target_mutation_contract_incomplete",
            "missing_fields": missing,
            "target_result": "",
        }
    unsigned_contract = dict(contract)
    stored_contract_hash = str(unsigned_contract.pop("contract_hash", ""))
    if canonical_hash(unsigned_contract) != stored_contract_hash:
        return {
            "status": "blocked",
            "reason": "target_mutation_contract_hash_mismatch",
            "target_result": "",
        }
    if receipt is None:
        return {
            "status": "not_run",
            "reason": "target_mutation_receipt_missing",
            "target_result": "",
        }
    if receipt.get("schema_version") != MUTATION_RECEIPT_SCHEMA:
        return {
            "status": "blocked",
            "reason": "target_mutation_receipt_schema_mismatch",
            "target_result": "",
        }
    if (
        receipt.get("target_id") != contract.get("target_id")
        or receipt.get("check_id") != contract.get("check_id")
        or receipt.get("contract_hash") != stored_contract_hash
    ):
        return {
            "status": "blocked",
            "reason": "target_mutation_receipt_identity_mismatch",
            "target_result": str(receipt.get("status", "")),
        }
    unsigned_receipt = dict(receipt)
    stored_receipt_hash = str(unsigned_receipt.pop("receipt_hash", ""))
    if canonical_hash(unsigned_receipt) != stored_receipt_hash:
        return {
            "status": "blocked",
            "reason": "target_mutation_receipt_hash_mismatch",
            "target_result": str(receipt.get("status", "")),
        }
    if receipt.get("current") is not True:
        return {
            "status": "blocked",
            "reason": "target_mutation_receipt_stale",
            "target_result": str(receipt.get("status", "")),
        }
    target_result = str(receipt.get("status", ""))
    if target_result not in {"pass", "fail", "blocked", "not_run"}:
        return {
            "status": "blocked",
            "reason": "target_mutation_result_invalid",
            "target_result": target_result,
        }
    return {
        "status": target_result,
        "reason": "target_native_result_projected_without_reinterpretation",
        "target_result": target_result,
        "target_id": str(contract.get("target_id")),
        "check_id": str(contract.get("check_id")),
        "contract_hash": stored_contract_hash,
        "receipt_hash": stored_receipt_hash,
        "target_metrics": dict(receipt.get("metrics", {}))
        if isinstance(receipt.get("metrics"), Mapping)
        else {},
    }


def _validate_authorities(payload: Mapping[str, Any]) -> None:
    unknown = sorted(set(payload) - ALLOWED_ROOT_FIELDS)
    if unknown:
        raise AssuranceDiagnosticError(
            "assurance_input_unknown_fields", ",".join(unknown)
        )
    if payload.get("schema_version") != ASSURANCE_INPUT_SCHEMA:
        raise AssuranceDiagnosticError(
            "assurance_input_schema_mismatch",
            str(payload.get("schema_version", "")),
        )
    contract = _mapping(payload.get("compiled_contract"), "compiled_contract")
    manifest = _mapping(payload.get("check_manifest"), "check_manifest")
    contract_findings = validate_compiled_contract(contract)
    if contract_findings:
        raise AssuranceDiagnosticError(
            "compiled_contract_invalid", contract_findings[0].code
        )
    manifest_findings = validate_check_manifest(manifest)
    if manifest_findings:
        raise AssuranceDiagnosticError(
            "check_manifest_invalid", manifest_findings[0].code
        )
    contract_plan = contract.get("content_impact_plan")
    manifest_plan = manifest.get("content_impact_plan")
    identities_match = (
        contract.get("check_declarations_hash")
        == manifest.get("check_declarations_hash")
        and isinstance(contract_plan, Mapping)
        and isinstance(manifest_plan, Mapping)
        and contract_plan.get("impact_graph_hash")
        == manifest_plan.get("impact_graph_hash")
    )
    if not identities_match:
        raise AssuranceDiagnosticError(
            "contract_manifest_identity_mismatch",
            "compiled contract does not bind supplied check manifest",
        )
    closure = _mapping(payload.get("closure_report"), "closure_report")
    if closure.get("artifact_type") != "skillguard_v2_closure_evaluation":
        raise AssuranceDiagnosticError(
            "closure_report_type_mismatch",
            str(closure.get("artifact_type", "")),
        )
    unsigned_closure = dict(closure)
    stored_assessment_hash = str(unsigned_closure.pop("assessment_hash", ""))
    if canonical_hash(unsigned_closure) != stored_assessment_hash:
        raise AssuranceDiagnosticError(
            "closure_report_hash_mismatch", stored_assessment_hash
        )


def derive_assurance_diagnostics(payload: Mapping[str, Any]) -> dict[str, Any]:
    _validate_authorities(payload)
    contract = _mapping(payload["compiled_contract"], "compiled_contract")
    manifest = _mapping(payload["check_manifest"], "check_manifest")
    closure = _mapping(payload["closure_report"], "closure_report")
    receipt_rows = _rows(payload.get("receipts", []), "receipts")
    budget = payload.get("evaluation_budget", 10_000)
    if not isinstance(budget, int) or isinstance(budget, bool):
        raise AssuranceDiagnosticError(
            "evaluation_budget_invalid", str(budget)
        )
    atoms = derive_blocker_atoms(manifest, receipt_rows, closure)
    blocked = _blocked_obligations(closure)
    basis = minimize_blockers(atoms, blocked, budget)
    proposed_actions = tuple(
        _validate_action(row)
        for row in _rows(
            payload.get("proposed_next_actions", []), "proposed_next_actions"
        )
    )
    mutation_contract = payload.get("mutation_contract")
    mutation_receipt = payload.get("mutation_receipt")
    if mutation_contract is not None:
        mutation_contract = _mapping(mutation_contract, "mutation_contract")
    if mutation_receipt is not None:
        mutation_receipt = _mapping(mutation_receipt, "mutation_receipt")

    report: dict[str, Any] = {
        "schema_version": ASSURANCE_REPORT_SCHEMA,
        "projection_kind": "read_only_non_authoritative",
        "source_closure_status": str(closure.get("status", "")),
        "closure_status_preserved": True,
        "closure_licensed": False,
        "authority_identities": {
            "contract_hash": str(contract.get("contract_hash", "")),
            "manifest_hash": str(manifest.get("manifest_hash", "")),
            "impact_graph_hash": str(
                manifest.get("content_impact_plan", {}).get(
                    "impact_graph_hash", ""
                )
                if isinstance(manifest.get("content_impact_plan"), Mapping)
                else ""
            ),
            "closure_assessment_hash": str(closure.get("assessment_hash", "")),
            "receipt_set_hash": canonical_hash(list(receipt_rows)),
        },
        "blocker_basis": basis,
        "all_blocker_atoms": [atom.to_dict() for atom in atoms],
        "proposed_next_action_results": list(proposed_actions),
        "mutation_adequacy": project_mutation_adequacy(
            mutation_contract, mutation_receipt
        ),
        "claim_boundary": (
            "This report explains supplied current authorities only. It does not "
            "execute or resume an owner, issue a receipt, change an obligation, "
            "or license closure."
        ),
    }
    report["report_hash"] = canonical_hash(report)
    return report
