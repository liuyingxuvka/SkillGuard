"""Strict direct-current compiler for SkillContract v3."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .wire_identity import atomic_write_json, canonical_json_bytes, wire_hash

SCHEMA_VERSION = "skillguard.skill_contract.v3"
COMPILED_SCHEMA_VERSION = "skillguard.compiled_contract.v3"
MANIFEST_SCHEMA_VERSION = "skillguard.check_manifest.v3"


class ContractError(ValueError):
    def __init__(self, code: str, path: str, message: str) -> None:
        super().__init__(f"{code} at {path}: {message}")
        self.code, self.path, self.message = code, path, message

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message, "severity": "blocker"}


@dataclass(frozen=True)
class ValidatedContract:
    source: Mapping[str, Any]
    by_input: Mapping[str, Mapping[str, Any]]
    by_route: Mapping[str, Mapping[str, Any]]
    by_step: Mapping[str, Mapping[str, Any]]
    by_obligation: Mapping[str, Mapping[str, Any]]
    by_check: Mapping[str, Mapping[str, Any]]
    check_owner_step: Mapping[str, str]
    step_topological_order: tuple[str, ...]


def strict_json_load(path: Path) -> dict[str, Any]:
    """Reject duplicate keys, NaN/Infinity and non-object roots."""

    def pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in rows:
            if key in result:
                raise ContractError("duplicate_json_key", "$", f"duplicate key: {key}")
            result[key] = value
        return result

    def nonfinite(value: str) -> None:
        raise ContractError("invalid_json_number", "$", f"non-finite number: {value}")

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ContractError("json_unreadable", "$", str(exc)) from exc
    try:
        value = json.loads(text, object_pairs_hook=pairs, parse_constant=nonfinite)
    except ContractError:
        raise
    except json.JSONDecodeError as exc:
        raise ContractError("invalid_json", "$", str(exc)) from exc
    if not isinstance(value, dict):
        raise ContractError("invalid_json", "$", "top-level JSON object required")
    return value


def _shape(row: Mapping[str, Any], required: set[str], optional: set[str], path: str) -> None:
    unknown = sorted(set(row) - required - optional)
    if unknown:
        raise ContractError("unknown_field", f"{path}.{unknown[0]}", "field is not declared")
    missing = sorted(required - set(row))
    if missing:
        raise ContractError("unknown_field", f"{path}.{missing[0]}", "required field is missing")


def _id(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ContractError("duplicate_id", path, "non-empty identifier without surrounding whitespace required")
    return value


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ContractError("unknown_field", path, "non-empty string required")
    return value


def _ids(value: Any, path: str, *, nonempty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ContractError("unknown_field", path, "array required")
    result = tuple(_id(item, f"{path}[{index}]") for index, item in enumerate(value))
    if nonempty and not result:
        raise ContractError("unknown_field", path, "non-empty array required")
    if len(result) != len(set(result)):
        raise ContractError("duplicate_id", path, "duplicate identifiers are not allowed")
    return result


def _rows(value: Any, path: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        raise ContractError("unknown_field", path, "array required")
    result: list[Mapping[str, Any]] = []
    for index, row in enumerate(value):
        if not isinstance(row, Mapping):
            raise ContractError("unknown_field", f"{path}[{index}]", "object required")
        result.append(row)
    return result


def _index(rows: Sequence[Mapping[str, Any]], field: str, path: str) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for index, row in enumerate(rows):
        identity = _id(row.get(field), f"{path}[{index}].{field}")
        if identity in result:
            raise ContractError("duplicate_id", f"{path}[{index}].{field}", identity)
        result[identity] = row
    return result


def _finite_json(value: Any, path: str) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ContractError("invalid_json_number", path, "finite JSON number required")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _finite_json(item, f"{path}[{index}]")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ContractError("unknown_field", path, "JSON object keys must be strings")
            _finite_json(item, f"{path}.{key}")
        return
    raise ContractError("unknown_field", path, "finite JSON value required")


def _relative(root: Path, value: Any, path: str, *, allow_dot: bool = False) -> str:
    text = _text(value, path)
    candidate = Path(text)
    if candidate.is_absolute() or ".." in candidate.parts or (text == "." and not allow_dot):
        raise ContractError("input_path_outside_root", path, "relative path inside root required")
    try:
        (root / candidate).resolve(strict=False).relative_to(root)
    except ValueError as exc:
        raise ContractError("input_path_outside_root", path, "path escapes root") from exc
    return candidate.as_posix()


def _topological(steps: Sequence[Mapping[str, Any]], by_step: Mapping[str, Mapping[str, Any]]) -> tuple[str, ...]:
    state: dict[str, int] = {}
    order: list[str] = []

    def visit(step_id: str) -> None:
        if state.get(step_id) == 1:
            raise ContractError("step_dependency_cycle", "$.steps", step_id)
        if state.get(step_id) == 2:
            return
        state[step_id] = 1
        for parent in by_step[step_id]["requires"]:
            visit(str(parent))
        state[step_id] = 2
        order.append(step_id)

    for row in steps:
        visit(str(row["step_id"]))
    return tuple(order)


def validate_contract_source(root: Path, source: Mapping[str, Any]) -> ValidatedContract:
    """Validate all structure without reading declared input bytes or presence."""

    if not isinstance(source, Mapping):
        raise ContractError("unknown_field", "$", "contract object required")
    if not root.is_absolute() or not root.is_dir():
        raise ContractError("input_path_outside_root", "$", "existing absolute root required")
    root = root.resolve(strict=True)
    _shape(source, {"schema_version", "skill_id", "maintenance_unit_id", "inputs", "routes", "steps", "obligations", "checks"}, {"member_skill_ids", "consumer_projection", "migration"}, "$")
    if source["schema_version"] != SCHEMA_VERSION:
        raise ContractError("unsupported_contract_schema", "$.schema_version", SCHEMA_VERSION)
    skill_id = _id(source["skill_id"], "$.skill_id")
    _id(source["maintenance_unit_id"], "$.maintenance_unit_id")
    if "member_skill_ids" in source and _ids(source["member_skill_ids"], "$.member_skill_ids", nonempty=True) != (skill_id,):
        raise ContractError("unknown_field", "$.member_skill_ids", "must equal [skill_id]")

    inputs, routes = _rows(source["inputs"], "$.inputs"), _rows(source["routes"], "$.routes")
    steps, obligations = _rows(source["steps"], "$.steps"), _rows(source["obligations"], "$.obligations")
    checks = _rows(source["checks"], "$.checks")

    for index, row in enumerate(inputs):
        path = f"$.inputs[{index}]"
        _shape(row, {"id", "path", "required"}, {"role"}, path)
        _id(row["id"], f"{path}.id")
        _relative(root, row["path"], f"{path}.path")
        if not isinstance(row["required"], bool):
            raise ContractError("unknown_field", f"{path}.required", "boolean required")
        if "role" in row and row["role"] is not None:
            _text(row["role"], f"{path}.role")
    by_input = _index(inputs, "id", "$.inputs")

    for index, row in enumerate(steps):
        path = f"$.steps[{index}]"
        _shape(row, {"step_id", "requires", "check_ids"}, set(), path)
        _id(row["step_id"], f"{path}.step_id")
        _ids(row["requires"], f"{path}.requires")
        _ids(row["check_ids"], f"{path}.check_ids")
    by_step = _index(steps, "step_id", "$.steps")

    for index, row in enumerate(obligations):
        path = f"$.obligations[{index}]"
        _shape(row, {"obligation_id", "check_ids"}, set(), path)
        _id(row["obligation_id"], f"{path}.obligation_id")
        _ids(row["check_ids"], f"{path}.check_ids", nonempty=True)
    by_obligation = _index(obligations, "obligation_id", "$.obligations")

    for index, row in enumerate(checks):
        path = f"$.checks[{index}]"
        _shape(row, {"check_id", "kind", "command", "args", "input_ids", "expected"}, {"timeout_seconds", "environment"}, path)
        _id(row["check_id"], f"{path}.check_id")
        if row["kind"] != "command":
            raise ContractError("unsupported_check_kind", f"{path}.kind", "only command is supported")
        _text(row["command"], f"{path}.command")
        if not isinstance(row["args"], list) or not all(isinstance(item, str) for item in row["args"]):
            raise ContractError("unknown_field", f"{path}.args", "string array required")
        for input_id in _ids(row["input_ids"], f"{path}.input_ids", nonempty=True):
            if input_id not in by_input:
                raise ContractError("unknown_reference", f"{path}.input_ids", input_id)
        expected = row["expected"]
        if not isinstance(expected, Mapping) or set(expected) != {"exit_code"} or isinstance(expected.get("exit_code"), bool) or not isinstance(expected.get("exit_code"), int):
            raise ContractError("invalid_oracle", f"{path}.expected", "exact integer exit_code required")
        if "timeout_seconds" in row:
            timeout = row["timeout_seconds"]
            if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(float(timeout)) or timeout <= 0:
                raise ContractError("invalid_timeout", f"{path}.timeout_seconds", "positive finite number required")
        if "environment" in row:
            environment = row["environment"]
            if not isinstance(environment, Mapping):
                raise ContractError("invalid_environment", f"{path}.environment", "object required")
            for key, value in environment.items():
                if not isinstance(key, str) or not key or "=" in key or "\x00" in key or not isinstance(value, str) or "\x00" in value:
                    raise ContractError("invalid_environment", f"{path}.environment", "valid string environment required")
    by_check = _index(checks, "check_id", "$.checks")

    for index, row in enumerate(steps):
        for field, known in (("requires", by_step), ("check_ids", by_check)):
            for ref in row[field]:
                if ref not in known:
                    raise ContractError("unknown_reference", f"$.steps[{index}].{field}", str(ref))
    for index, row in enumerate(obligations):
        for ref in row["check_ids"]:
            if ref not in by_check:
                raise ContractError("unknown_reference", f"$.obligations[{index}].check_ids", str(ref))

    check_owner_step: dict[str, str] = {}
    for row in steps:
        for check_id in row["check_ids"]:
            if check_id in check_owner_step:
                raise ContractError("check_owner_duplicate", "$.steps", str(check_id))
            check_owner_step[str(check_id)] = str(row["step_id"])
    for check_id in by_check:
        if check_id not in check_owner_step:
            raise ContractError("check_owner_missing", "$.steps", check_id)
    step_order = _topological(steps, by_step)

    for index, row in enumerate(routes):
        path = f"$.routes[{index}]"
        _shape(row, {"route_id", "choice_group", "when", "step_ids", "obligation_ids"}, {"composition_id"}, path)
        _id(row["route_id"], f"{path}.route_id")
        _id(row["choice_group"], f"{path}.choice_group")
        if "composition_id" in row:
            _id(row["composition_id"], f"{path}.composition_id")
        predicates = _rows(row["when"], f"{path}.when")
        if not predicates:
            raise ContractError("unknown_field", f"{path}.when", "non-empty predicate array required")
        for pred_index, predicate in enumerate(predicates):
            pred_path = f"{path}.when[{pred_index}]"
            _shape(predicate, {"fact", "equals"}, set(), pred_path)
            _id(predicate["fact"], f"{pred_path}.fact")
            _finite_json(predicate["equals"], f"{pred_path}.equals")
        for field, known in (("step_ids", by_step), ("obligation_ids", by_obligation)):
            for ref in _ids(row[field], f"{path}.{field}"):
                if ref not in known:
                    raise ContractError("unknown_reference", f"{path}.{field}", ref)
    by_route = _index(routes, "route_id", "$.routes")

    projection = source.get("consumer_projection")
    if projection is not None:
        if not isinstance(projection, Mapping):
            raise ContractError("consumer_projection_invalid", "$.consumer_projection", "object required")
        _shape(projection, {"projection_id", "root_path", "release_manifest_path", "file_paths"}, set(), "$.consumer_projection")
        if projection["projection_id"] != "projection:consumer-distribution":
            raise ContractError("consumer_projection_invalid", "$.consumer_projection.projection_id", "fixed projection id required")
        _relative(root, projection["root_path"], "$.consumer_projection.root_path", allow_dot=True)
        _relative(root, projection["release_manifest_path"], "$.consumer_projection.release_manifest_path")
        files = _ids(projection["file_paths"], "$.consumer_projection.file_paths", nonempty=True)
        for index, value in enumerate(files):
            _relative(root, value, f"$.consumer_projection.file_paths[{index}]")
        if "SKILL.md" not in files:
            raise ContractError("consumer_projection_invalid", "$.consumer_projection.file_paths", "SKILL.md is required")

    return ValidatedContract(source, by_input, by_route, by_step, by_obligation, by_check, check_owner_step, step_order)


def _hash_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _current_bytes(path: Path, expected: bytes) -> bool:
    try:
        return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n") == expected
    except OSError:
        return False


def compile_direct_contract(root: Path, contract_path: Path, *, write: bool = False) -> tuple[bool, str, tuple[dict[str, str], ...], Mapping[str, Any] | None, Mapping[str, Any] | None, tuple[str, ...]]:
    root = root.resolve(strict=True)
    contract_path = contract_path.resolve(strict=False)
    expected_source = (root / ".skillguard" / "contract-source.json").resolve(strict=False)
    if contract_path != expected_source:
        finding = ContractError("contract_path_invalid", "$.contract_path", str(contract_path))
        return False, "blocked", (finding.to_dict(),), None, None, ()
    try:
        source = strict_json_load(contract_path)
        validate_contract_source(root, source)
    except ContractError as exc:
        return False, "blocked", (exc.to_dict(),), None, None, ()
    source_identity = {"path": ".skillguard/contract-source.json", "content_hash": _hash_file(contract_path)}
    body: dict[str, Any] = {
        "schema_version": COMPILED_SCHEMA_VERSION,
        "skill_id": source["skill_id"],
        "maintenance_unit_id": source["maintenance_unit_id"],
        "member_skill_ids": list(source.get("member_skill_ids", [source["skill_id"]])),
        "inputs": [dict(row) for row in source["inputs"]],
        "routes": [dict(row) for row in source["routes"]],
        "steps": [dict(row) for row in source["steps"]],
        "obligations": [dict(row) for row in source["obligations"]],
        "checks": [dict(row) for row in source["checks"]],
        "check_declarations_hash": wire_hash(source["checks"]),
        "source_identity": source_identity,
        "claim_boundary": "Compilation validates one explicit source and does not execute checks.",
    }
    if "consumer_projection" in source:
        body["consumer_projection"] = dict(source["consumer_projection"])
    contract = dict(body)
    contract["contract_hash"] = wire_hash(body)
    manifest_body = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "skill_id": source["skill_id"],
        "maintenance_unit_id": source["maintenance_unit_id"],
        "contract_hash": contract["contract_hash"],
        "checks": [dict(row) for row in source["checks"]],
        "check_declarations_hash": wire_hash(source["checks"]),
        "claim_boundary": "The manifest declares exact checks and does not claim execution.",
    }
    manifest = dict(manifest_body)
    manifest["manifest_hash"] = wire_hash(manifest_body)
    outputs = ((root / ".skillguard" / "compiled-contract.json", contract), (root / ".skillguard" / "check-manifest.json", manifest))
    written: list[str] = []
    stale: list[dict[str, str]] = []
    for path, payload in outputs:
        encoded = canonical_json_bytes(payload)
        if write:
            if not _current_bytes(path, encoded):
                atomic_write_json(path, payload)
                written.append(path.relative_to(root).as_posix())
        elif not _current_bytes(path, encoded):
            stale.append(ContractError("generated_file_stale", path.relative_to(root).as_posix(), "generated bytes differ").to_dict())
    if stale:
        return False, "blocked", tuple(stale), contract, manifest, tuple(written)
    return True, "pass", (), contract, manifest, tuple(written)


__all__ = ["COMPILED_SCHEMA_VERSION", "ContractError", "MANIFEST_SCHEMA_VERSION", "SCHEMA_VERSION", "ValidatedContract", "compile_direct_contract", "strict_json_load", "validate_contract_source"]
