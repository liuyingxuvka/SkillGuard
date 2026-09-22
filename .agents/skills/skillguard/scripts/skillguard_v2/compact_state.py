"""Direct-current author state for the compact SkillGuard runtime.

Only the v2 pointer and the immutable objects it names are accepted.  The
reader is intentionally side-effect free and never consults live inputs or
route facts.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .compact_contract import ContractError, strict_json_load, strict_json_loads, validate_contract_source
from .contract_compiler import canonical_hash
from .path_identity import canonical_filesystem_path
from .execution_records import durable_write_immutable_json, filesystem_path
from .wire_identity import atomic_write_json, is_wire_hash, wire_hash


def _identity_directory(value: object) -> str:
    text = str(value)
    readable = re.sub(r"[^a-zA-Z0-9._-]+", "-", text).strip("-._")[:48] or "identity"
    return f"{readable}-{canonical_hash({'identity': text})[:12].lower()}"


def control_root(author_state_root: Path, maintenance_unit_id: str, skill_id: str) -> Path:
    return (
        author_state_root.resolve()
        / "units"
        / _identity_directory(maintenance_unit_id)
        / "members"
        / _identity_directory(skill_id)
    )


def author_root_identity(root: Path) -> str:
    import os

    return os.path.normcase(str(canonical_filesystem_path(root)))


@dataclass(frozen=True)
class AcceptedObservation:
    accepted: Mapping[str, Any]
    accepted_id: str
    aggregate: Mapping[str, Any]
    plan: Mapping[str, Any]
    input_snapshot: Mapping[str, Any]
    contract_snapshot: Mapping[str, Any]
    missing_leaf_checks: tuple[str, ...]


def ensure_binding(
    author_state_root: Path,
    *,
    root: Path,
    maintenance_unit_id: str,
    skill_id: str,
) -> Path:
    """Create the one immutable root binding, or require an exact match."""

    state = control_root(author_state_root, maintenance_unit_id, skill_id)
    state.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "skillguard.target_state_binding.v1",
        "maintenance_unit_id": maintenance_unit_id,
        "skill_id": skill_id,
        "author_root_identity": author_root_identity(root),
        "contract_relative_path": ".skillguard/contract-source.json",
    }
    path = state / "binding.json"
    if path.is_file():
        if strict_json_load(path) != payload:
            raise ContractError("state_binding_mismatch", "$.binding", "target state belongs to another author root")
    else:
        durable_write_immutable_json(path, payload)
    return state


def publish_acceptance(
    author_state_root: Path,
    *,
    root: Path,
    contract: Mapping[str, Any],
    plan: Mapping[str, Any],
    input_snapshot: Mapping[str, Any],
    leaves: tuple[Mapping[str, Any], ...],
    expected_current: str | None,
    qualification: str = "source_qualification_only",
    artifact: Mapping[str, Any] | None = None,
) -> tuple[Mapping[str, Any], str, bool]:
    """Publish immutable v2 objects and CAS current while caller holds single-flight."""

    maintenance_unit_id = str(contract["maintenance_unit_id"])
    skill_id = str(contract["skill_id"])
    state = ensure_binding(
        author_state_root,
        root=root,
        maintenance_unit_id=maintenance_unit_id,
        skill_id=skill_id,
    )
    current_pointer = _load_current_pointer(
        state,
        identity=author_root_identity(root),
        maintenance_unit_id=maintenance_unit_id,
        skill_id=skill_id,
    )
    current = current_pointer[0] if current_pointer else None
    current_id = current_pointer[1] if current_pointer else None
    if expected_current != current_id:
        raise ContractError("accepted_current_conflict", "$.expected_current", f"expected {expected_current!r}, current {current_id!r}")
    plan_hash = wire_hash(plan)
    snapshot_hash = wire_hash(input_snapshot)
    contract_hash = wire_hash(contract)
    plan_ref = f"plans/{plan_hash[7:]}.plan.json"
    snapshot_ref = f"inputs/{snapshot_hash[7:]}.inputs.json"
    contract_ref = f"contracts/{contract_hash[7:]}.contract.json"
    durable_write_immutable_json(state / plan_ref, plan)
    durable_write_immutable_json(state / snapshot_ref, input_snapshot)
    durable_write_immutable_json(state / contract_ref, contract)
    leaf_refs: list[Mapping[str, Any]] = []
    for leaf in leaves:
        execution_key = str(leaf["execution_key"])
        leaf_path = filesystem_path(state / "functions" / f"{execution_key[7:]}.json")
        if not leaf_path.is_file() or "sha256:" + hashlib.sha256(leaf_path.read_bytes()).hexdigest() != wire_hash(leaf):
            raise ContractError("evidence_invalid", f"$.functions.{leaf.get('check_id')}", "published leaf mismatch")
        leaf_refs.append({
            "check_id": leaf["check_id"],
            "execution_key": execution_key,
            "leaf_ref": (state / "functions" / f"{execution_key[7:]}.json").relative_to(state).as_posix(),
            "leaf_hash": wire_hash(leaf),
        })
    aggregate = {
        "schema_version": "skillguard.change_result.v2",
        "maintenance_unit_id": maintenance_unit_id,
        "skill_id": skill_id,
        "author_root_identity": author_root_identity(root),
        "status": "pass",
        "plan_ref": plan_ref,
        "plan_hash": plan_hash,
        "input_snapshot_ref": snapshot_ref,
        "input_snapshot_hash": snapshot_hash,
        "contract_snapshot_ref": contract_ref,
        "contract_snapshot_hash": contract_hash,
        "required_checks": list(plan["check_order"]),
        "leaves": leaf_refs,
        "qualification": qualification,
        "artifact": dict(artifact) if artifact is not None else None,
    }
    result_hash = wire_hash(aggregate)
    result_ref = f"results/{result_hash[7:]}.result.json"
    durable_write_immutable_json(state / result_ref, aggregate)
    if current and current.get("result_hash") == result_hash:
        return current, str(current_id), False
    generation = int(current["generation"]) + 1 if current else 1
    accepted = {
        "schema_version": "skillguard.accepted_target.v2",
        "maintenance_unit_id": maintenance_unit_id,
        "skill_id": skill_id,
        "author_root_identity": author_root_identity(root),
        "generation": generation,
        "result_ref": result_ref,
        "result_hash": result_hash,
        "input_snapshot_ref": snapshot_ref,
        "input_snapshot_hash": snapshot_hash,
        "contract_snapshot_ref": contract_ref,
        "contract_snapshot_hash": contract_hash,
    }
    atomic_write_json(state / "current.json", accepted)
    return accepted, wire_hash(accepted), True


def _shape(value: Mapping[str, Any], fields: set[str], path: str) -> None:
    if set(value) != fields:
        raise ContractError("evidence_invalid", path, "exact field set required")


def _load_hashed(root: Path, reference: Any, expected_hash: Any, path: str) -> tuple[Path, Mapping[str, Any]]:
    if not isinstance(reference, str) or not reference or "\\" in reference:
        raise ContractError("evidence_invalid", path, "safe POSIX relative ref required")
    relative = Path(reference)
    if relative.is_absolute() or ".." in relative.parts:
        raise ContractError("evidence_invalid", path, "safe POSIX relative ref required")
    target = canonical_filesystem_path(root / relative)
    try:
        target.relative_to(canonical_filesystem_path(root))
    except ValueError as exc:
        raise ContractError("evidence_invalid", path, "reference escapes target state") from exc
    target = filesystem_path(target)
    if not target.is_file():
        raise ContractError("evidence_missing", path, reference)
    if not is_wire_hash(expected_hash):
        raise ContractError("evidence_invalid", path, "wire hash required")
    raw = target.read_bytes()
    actual = "sha256:" + hashlib.sha256(raw).hexdigest()
    if actual != expected_hash:
        raise ContractError("evidence_invalid", path, "raw byte hash mismatch")
    return target, strict_json_loads(raw, source=path)


def _load_current_pointer(
    state: Path,
    *,
    identity: str,
    maintenance_unit_id: str,
    skill_id: str,
) -> tuple[Mapping[str, Any], str] | None:
    path = state / "current.json"
    if not path.is_file():
        return None
    accepted = strict_json_load(path)
    fields = {
        "schema_version", "maintenance_unit_id", "skill_id", "author_root_identity", "generation",
        "result_ref", "result_hash", "input_snapshot_ref", "input_snapshot_hash",
        "contract_snapshot_ref", "contract_snapshot_hash",
    }
    _shape(accepted, fields, "$.current")
    if accepted.get("schema_version") != "skillguard.accepted_target.v2" or any(
        accepted.get(key) != value
        for key, value in {
            "maintenance_unit_id": maintenance_unit_id,
            "skill_id": skill_id,
            "author_root_identity": identity,
        }.items()
    ):
        raise ContractError("evidence_invalid", "$.current", "schema or identity mismatch")
    generation = accepted.get("generation")
    if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
        raise ContractError("evidence_invalid", "$.current.generation", "positive integer required")
    return accepted, wire_hash(accepted)


def _verify_stream(root: Path, reference: Any, expected_hash: Any, path: str) -> None:
    if not isinstance(reference, str) or not reference or "\\" in reference:
        raise ContractError("evidence_invalid", path, "safe POSIX relative ref required")
    relative = Path(reference)
    if relative.is_absolute() or ".." in relative.parts or not is_wire_hash(expected_hash):
        raise ContractError("evidence_invalid", path, "safe ref and wire hash required")
    target = canonical_filesystem_path(root / relative)
    try:
        target.relative_to(canonical_filesystem_path(root))
    except ValueError as exc:
        raise ContractError("evidence_invalid", path, "stream escapes target state") from exc
    target = filesystem_path(target)
    if not target.is_file() or "sha256:" + hashlib.sha256(target.read_bytes()).hexdigest() != expected_hash:
        raise ContractError("evidence_invalid", path, "stream missing or hash mismatch")


def load_accepted_observation(
    author_state_root: Path,
    *,
    root: Path,
    maintenance_unit_id: str,
    skill_id: str,
    scope: tuple[str, ...],
) -> AcceptedObservation | None:
    """Verify current and its immutable snapshot graph without any writes."""

    state = control_root(author_state_root, maintenance_unit_id, skill_id)
    current_path = state / "current.json"
    if not current_path.is_file():
        return None
    binding_path = state / "binding.json"
    if not binding_path.is_file():
        raise ContractError("state_binding_mismatch", "$.binding", "binding is missing")
    binding = strict_json_load(binding_path)
    _shape(binding, {"schema_version", "maintenance_unit_id", "skill_id", "author_root_identity", "contract_relative_path"}, "$.binding")
    identity = author_root_identity(root)
    expected_binding = {
        "schema_version": "skillguard.target_state_binding.v1",
        "maintenance_unit_id": maintenance_unit_id,
        "skill_id": skill_id,
        "author_root_identity": identity,
        "contract_relative_path": ".skillguard/contract-source.json",
    }
    if binding != expected_binding:
        raise ContractError("state_binding_mismatch", "$.binding", "target state belongs to another author root")

    accepted = strict_json_load(current_path)
    accepted_fields = {
        "schema_version", "maintenance_unit_id", "skill_id", "author_root_identity", "generation",
        "result_ref", "result_hash", "input_snapshot_ref", "input_snapshot_hash",
        "contract_snapshot_ref", "contract_snapshot_hash",
    }
    _shape(accepted, accepted_fields, "$.current")
    if accepted.get("schema_version") != "skillguard.accepted_target.v2":
        raise ContractError("evidence_invalid", "$.current.schema_version", "v2 required")
    if any(accepted.get(key) != value for key, value in {
        "maintenance_unit_id": maintenance_unit_id, "skill_id": skill_id, "author_root_identity": identity,
    }.items()):
        raise ContractError("evidence_invalid", "$.current", "foreign accepted identity")
    generation = accepted.get("generation")
    if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
        raise ContractError("evidence_invalid", "$.current.generation", "positive integer required")

    _, aggregate = _load_hashed(state, accepted["result_ref"], accepted["result_hash"], "$.current.result_ref")
    _, plan = _load_hashed(state, aggregate.get("plan_ref"), aggregate.get("plan_hash"), "$.aggregate.plan_ref")
    _, snapshot = _load_hashed(state, accepted["input_snapshot_ref"], accepted["input_snapshot_hash"], "$.current.input_snapshot_ref")
    _, contract = _load_hashed(state, accepted["contract_snapshot_ref"], accepted["contract_snapshot_hash"], "$.current.contract_snapshot_ref")

    if contract.get("schema_version") != "skillguard.skill_contract.v3" or contract.get("maintenance_unit_id") != maintenance_unit_id or contract.get("skill_id") != skill_id:
        raise ContractError("evidence_invalid", "$.contract_snapshot", "contract locator mismatch")
    try:
        accepted_contract = validate_contract_source(root, contract)
    except ContractError as exc:
        raise ContractError("evidence_invalid", "$.contract_snapshot", exc.code) from exc

    _shape(plan, {"schema_version", "maintenance_unit_id", "skill_id", "author_root_identity", "operation", "route_ids", "step_ids", "obligation_checks", "check_order", "check_dependencies", "selected_input_ids"}, "$.plan")
    _shape(snapshot, {"schema_version", "maintenance_unit_id", "skill_id", "author_root_identity", "inputs"}, "$.input_snapshot")
    _shape(aggregate, {"schema_version", "maintenance_unit_id", "skill_id", "author_root_identity", "status", "plan_ref", "plan_hash", "input_snapshot_ref", "input_snapshot_hash", "contract_snapshot_ref", "contract_snapshot_hash", "required_checks", "leaves", "qualification", "artifact"}, "$.aggregate")
    for payload, schema, path in (
        (plan, "skillguard.frozen_plan.v1", "$.plan"),
        (snapshot, "skillguard.input_snapshot.v2", "$.input_snapshot"),
        (aggregate, "skillguard.change_result.v2", "$.aggregate"),
    ):
        if payload.get("schema_version") != schema or any(payload.get(key) != value for key, value in {
            "maintenance_unit_id": maintenance_unit_id, "skill_id": skill_id, "author_root_identity": identity,
        }.items()):
            raise ContractError("evidence_invalid", path, "schema or identity mismatch")
    if aggregate.get("status") != "pass":
        raise ContractError("evidence_invalid", "$.aggregate.status", "exact pass required")
    if aggregate.get("input_snapshot_ref") != accepted.get("input_snapshot_ref") or aggregate.get("input_snapshot_hash") != accepted.get("input_snapshot_hash"):
        raise ContractError("evidence_invalid", "$.aggregate.input_snapshot_ref", "pointer mismatch")
    if aggregate.get("contract_snapshot_ref") != accepted.get("contract_snapshot_ref") or aggregate.get("contract_snapshot_hash") != accepted.get("contract_snapshot_hash"):
        raise ContractError("evidence_invalid", "$.aggregate.contract_snapshot_ref", "pointer mismatch")

    # Rebuild the selected plan from the current v3 contract.  The accepted
    # plan is an immutable receipt, but it is not an authority which can
    # reduce the current check denominator by being rehashed.  Importing here
    # avoids the checker/compact-state module cycle during CLI startup.
    operation = plan.get("operation")
    if operation not in {"change", "release"}:
        raise ContractError("evidence_invalid", "$.plan.operation", "change or release required")
    route_ids = plan.get("route_ids")
    route_ids_valid = (
        isinstance(route_ids, list)
        and bool(route_ids)
        and all(type(item) is str and bool(item) for item in route_ids)
    )
    if not route_ids_valid or len(route_ids) != len(set(route_ids)) or any(item not in accepted_contract.by_route for item in route_ids):
        raise ContractError("evidence_invalid", "$.plan.route_ids", "current contract route identities required")
    from checker_engine import build_plan
    from .route_runtime import RouteDecision

    rebuilt = build_plan(
        accepted_contract,
        RouteDecision(True, "selected", tuple(route_ids)),
        operation=str(operation),
        root=root,
    )
    rebuilt_payload = rebuilt.to_dict()
    if dict(plan) != rebuilt_payload:
        raise ContractError("evidence_invalid", "$.plan", "stored plan does not equal current contract denominator")
    if not rebuilt.check_order:
        raise ContractError("evidence_invalid", "$.plan.check_order", "non-empty current denominator required")
    missing_scope = [route_id for route_id in scope if route_id not in route_ids]
    if missing_scope:
        raise ContractError("accepted_scope_missing", "$.scope", missing_scope[0])
    # A typed snapshot is part of the accepted contract.  Validate its rows
    # against the current contract declarations without reading live files.
    snapshot_rows = snapshot.get("inputs")
    if not isinstance(snapshot_rows, list):
        raise ContractError("evidence_invalid", "$.input_snapshot.inputs", "array required")
    expected_input_ids = list(rebuilt.selected_input_ids)
    if len(snapshot_rows) != len(expected_input_ids):
        raise ContractError("evidence_invalid", "$.input_snapshot.inputs", "snapshot denominator mismatch")
    expected_snapshot_fields = {"id", "path", "role", "required", "exists", "sha256"}
    for index, (row, expected_id) in enumerate(zip(snapshot_rows, expected_input_ids)):
        if not isinstance(row, Mapping) or set(row) != expected_snapshot_fields:
            raise ContractError("evidence_invalid", f"$.input_snapshot.inputs[{index}]", "exact typed row required")
        if row.get("id") != expected_id:
            raise ContractError("evidence_invalid", f"$.input_snapshot.inputs[{index}].id", "selected input order mismatch")
        declaration = accepted_contract.by_input.get(expected_id)
        if declaration is None:
            raise ContractError("evidence_invalid", f"$.input_snapshot.inputs[{index}].id", "unknown input")
        expected_path = Path(str(declaration["path"])).as_posix()
        if row.get("path") != expected_path or row.get("role") != declaration.get("role"):
            raise ContractError("evidence_invalid", f"$.input_snapshot.inputs[{index}]", "input declaration mismatch")
        if type(row.get("required")) is not bool or row.get("required") != declaration["required"]:
            raise ContractError("evidence_invalid", f"$.input_snapshot.inputs[{index}].required", "typed required flag mismatch")
        if type(row.get("exists")) is not bool:
            raise ContractError("evidence_invalid", f"$.input_snapshot.inputs[{index}].exists", "typed exists flag required")
        digest = row.get("sha256")
        if row["exists"]:
            if not is_wire_hash(digest):
                raise ContractError("evidence_invalid", f"$.input_snapshot.inputs[{index}].sha256", "wire hash required for present input")
        elif row["required"] or digest is not None:
            raise ContractError("evidence_invalid", f"$.input_snapshot.inputs[{index}]", "missing input must be optional with null hash")

    required = aggregate.get("required_checks")
    leaves = aggregate.get("leaves")
    if not isinstance(required, list) or len(required) != len(set(required)) or required != list(rebuilt.check_order):
        raise ContractError("evidence_invalid", "$.aggregate.required_checks", "plan denominator mismatch")
    if not isinstance(leaves, list) or len(leaves) != len(required):
        raise ContractError("evidence_invalid", "$.aggregate.leaves", "leaf denominator mismatch")
    if plan.get("obligation_checks") != rebuilt_payload["obligation_checks"] or plan.get("check_dependencies") != rebuilt_payload["check_dependencies"]:
        raise ContractError("evidence_invalid", "$.plan", "obligation or dependency denominator mismatch")
    qualification = aggregate.get("qualification")
    artifact = aggregate.get("artifact")
    if qualification not in {"source_qualification_only", "source_and_artifact"}:
        raise ContractError("evidence_invalid", "$.aggregate.qualification", "unsupported qualification")
    if qualification == "source_qualification_only" and artifact is not None:
        raise ContractError("evidence_invalid", "$.aggregate.artifact", "source-only result cannot carry artifact")
    if qualification == "source_and_artifact":
        if not isinstance(artifact, Mapping) or set(artifact) != {"path", "kind", "sha256"}:
            raise ContractError("evidence_invalid", "$.aggregate.artifact", "typed artifact identity required")
        artifact_path = artifact.get("path")
        if not isinstance(artifact_path, str) or not artifact_path or "\\" in artifact_path or Path(artifact_path).is_absolute() or ".." in Path(artifact_path).parts:
            raise ContractError("evidence_invalid", "$.aggregate.artifact.path", "safe relative artifact path required")
        if artifact.get("kind") not in {"file", "consumer_directory"} or not is_wire_hash(artifact.get("sha256")):
            raise ContractError("evidence_invalid", "$.aggregate.artifact", "artifact identity invalid")
    missing_leaf_checks: list[str] = []
    leaf_ids: list[str] = []
    ref_keys = {
        str(row.get("check_id")): str(row.get("execution_key"))
        for row in leaves
        if isinstance(row, Mapping)
    }
    plan_dependencies = plan.get("check_dependencies")
    if not isinstance(plan_dependencies, Mapping) or set(plan_dependencies) != set(required):
        raise ContractError("evidence_invalid", "$.plan.check_dependencies", "check denominator mismatch")
    for index, leaf_ref in enumerate(leaves):
        if not isinstance(leaf_ref, Mapping):
            raise ContractError("evidence_invalid", f"$.aggregate.leaves[{index}]", "object required")
        _shape(leaf_ref, {"check_id", "execution_key", "leaf_ref", "leaf_hash"}, f"$.aggregate.leaves[{index}]")
        check_id = leaf_ref.get("check_id")
        leaf_ids.append(str(check_id))
        try:
            _, leaf = _load_hashed(state, leaf_ref.get("leaf_ref"), leaf_ref.get("leaf_hash"), f"$.aggregate.leaves[{index}]")
        except ContractError as exc:
            if exc.code == "evidence_missing":
                missing_leaf_checks.append(str(check_id))
                continue
            else:
                raise
        _shape(leaf, {
            "schema_version", "maintenance_unit_id", "skill_id", "author_root_identity", "check_id",
            "execution_key", "dependency_execution_keys", "status", "exit_code", "cleanup_confirmed",
            "stdout_ref", "stdout_hash", "stderr_ref", "stderr_hash",
        }, f"$.leaf.{check_id}")
        dependencies = plan_dependencies.get(str(check_id))
        if not isinstance(dependencies, list) or not all(isinstance(item, str) for item in dependencies):
            raise ContractError("evidence_invalid", f"$.plan.check_dependencies.{check_id}", "string array required")
        expected_dependencies = {dependency: ref_keys.get(dependency) for dependency in dependencies}
        if any(value is None for value in expected_dependencies.values()):
            raise ContractError("evidence_invalid", f"$.leaf.{check_id}", "dependency leaf missing from denominator")
        exact = {
            "schema_version": "skillguard.leaf_result.v1",
            "maintenance_unit_id": maintenance_unit_id,
            "skill_id": skill_id,
            "author_root_identity": identity,
            "check_id": check_id,
            "execution_key": leaf_ref.get("execution_key"),
            "dependency_execution_keys": expected_dependencies,
            "status": "pass",
            "cleanup_confirmed": True,
        }
        if any(leaf.get(key) != value for key, value in exact.items()):
            raise ContractError("evidence_invalid", f"$.leaf.{check_id}", "leaf identity or status mismatch")
        if isinstance(leaf.get("exit_code"), bool) or not isinstance(leaf.get("exit_code"), int):
            raise ContractError("evidence_invalid", f"$.leaf.{check_id}.exit_code", "integer required")
        check = accepted_contract.by_check.get(str(check_id))
        if check is None or leaf.get("exit_code") != check["expected"]["exit_code"]:
            raise ContractError("evidence_invalid", f"$.leaf.{check_id}.exit_code", "accepted oracle mismatch")
        _verify_stream(state, leaf.get("stdout_ref"), leaf.get("stdout_hash"), f"$.leaf.{check_id}.stdout")
        _verify_stream(state, leaf.get("stderr_ref"), leaf.get("stderr_hash"), f"$.leaf.{check_id}.stderr")
    if leaf_ids != required or len(leaf_ids) != len(set(leaf_ids)):
        raise ContractError("evidence_invalid", "$.aggregate.leaves", "ordered check denominator mismatch")
    return AcceptedObservation(
        accepted=accepted,
        accepted_id=wire_hash(accepted),
        aggregate=aggregate,
        plan=plan,
        input_snapshot=snapshot,
        contract_snapshot=contract,
        missing_leaf_checks=tuple(missing_leaf_checks),
    )


__all__ = [
    "AcceptedObservation", "author_root_identity", "control_root", "ensure_binding",
    "load_accepted_observation", "publish_acceptance",
]
