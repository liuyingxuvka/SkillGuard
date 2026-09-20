"""Direct SkillContract v3 compiler.

The author contract is the only authority in the compact runtime.  This
module deliberately has no model adapter, template platform, global-router
or portfolio dependency: it validates the declared inputs, routes, steps,
obligations and checks, then derives the two generated records from those
same bytes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .wire_identity import atomic_write_json, canonical_json_bytes, wire_hash


SCHEMA_VERSION = "skillguard.skill_contract.v3"
COMPILED_SCHEMA_VERSION = "skillguard.compiled_contract.v3"
MANIFEST_SCHEMA_VERSION = "skillguard.check_manifest.v3"
LEGACY_FIELDS = frozenset(
    {
        "model_path",
        "functions",
        "supervision_fragment_refs",
        "portfolio_capability_contracts",
        "global_prompt",
    }
)


def _finding(code: str, path: str, message: str, severity: str = "blocker") -> dict[str, str]:
    return {"code": code, "path": path, "message": message, "severity": severity}


def _load_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(str(exc)) from exc
    if not isinstance(value, Mapping):
        raise ValueError("contract source must be a JSON object")
    return value


def _hash_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _current_bytes(path: Path, expected: bytes) -> bool:
    try:
        return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n") == expected
    except OSError:
        return False


def _rows(value: object, name: str, findings: list[dict[str, str]]) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        findings.append(_finding("expected_array", f"$.{name}", "value must be an array"))
        return []
    rows: list[Mapping[str, Any]] = []
    for index, row in enumerate(value):
        if not isinstance(row, Mapping):
            findings.append(_finding("expected_object", f"$.{name}[{index}]", "row must be an object"))
        else:
            rows.append(row)
    return rows


def _ids(rows: list[Mapping[str, Any]], name: str, field: str, findings: list[dict[str, str]]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for index, row in enumerate(rows):
        value = row.get(field)
        path = f"$.{name}[{index}].{field}"
        if not isinstance(value, str) or not value.strip():
            findings.append(_finding("missing_id", path, f"{field} must be a non-empty string"))
            continue
        if value in result:
            findings.append(_finding("duplicate_id", path, f"duplicate {field}: {value}"))
            continue
        result[value] = row
    return result


def _references(
    rows: list[Mapping[str, Any]],
    name: str,
    field: str,
    known: Mapping[str, Any],
    findings: list[dict[str, str]],
) -> None:
    for index, row in enumerate(rows):
        refs = row.get(field, [])
        if not isinstance(refs, list):
            findings.append(_finding("expected_array", f"$.{name}[{index}].{field}", "reference list must be an array"))
            continue
        for ref_index, ref in enumerate(refs):
            if not isinstance(ref, str) or ref not in known:
                findings.append(
                    _finding(
                        "unknown_reference",
                        f"$.{name}[{index}].{field}[{ref_index}]",
                        f"unknown reference: {ref}",
                    )
                )


def _validate_inputs(rows: list[Mapping[str, Any]], root: Path, findings: list[dict[str, str]]) -> dict[str, Mapping[str, Any]]:
    index = _ids(rows, "inputs", "id", findings)
    for pos, row in enumerate(rows):
        path = row.get("path")
        if not isinstance(path, str) or not path.strip():
            findings.append(_finding("missing_input_path", f"$.inputs[{pos}].path", "input path is required"))
            continue
        candidate = Path(path)
        if candidate.is_absolute() or ".." in candidate.parts:
            findings.append(_finding("input_path_outside_root", f"$.inputs[{pos}].path", "input path must be relative and remain under the target root"))
            continue
        resolved = (root / candidate).resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            findings.append(_finding("input_path_outside_root", f"$.inputs[{pos}].path", "input path escapes the target root"))
            continue
        if not resolved.is_file():
            findings.append(_finding("input_missing", f"$.inputs[{pos}].path", path))
        if not isinstance(row.get("required"), bool):
            findings.append(_finding("input_required_invalid", f"$.inputs[{pos}].required", "required must be boolean"))
    return index


def _validate_routes(
    rows: list[Mapping[str, Any]],
    step_index: Mapping[str, Any],
    obligation_index: Mapping[str, Any],
    findings: list[dict[str, str]],
) -> dict[str, Mapping[str, Any]]:
    index = _ids(rows, "routes", "route_id", findings)
    for pos, row in enumerate(rows):
        if not isinstance(row.get("choice_group"), str) or not row.get("choice_group"):
            findings.append(_finding("route_choice_group_missing", f"$.routes[{pos}].choice_group", "choice_group is required"))
        predicates = row.get("when")
        if not isinstance(predicates, list) or not predicates:
            findings.append(_finding("route_predicates_missing", f"$.routes[{pos}].when", "route needs at least one fact predicate"))
        else:
            for pred_index, predicate in enumerate(predicates):
                if not isinstance(predicate, Mapping) or not isinstance(predicate.get("fact"), str) or "equals" not in predicate:
                    findings.append(_finding("route_predicate_invalid", f"$.routes[{pos}].when[{pred_index}]", "predicate must contain fact and equals"))
        _references(rows=[row], name="routes", field="step_ids", known=step_index, findings=findings)
        _references(rows=[row], name="routes", field="obligation_ids", known=obligation_index, findings=findings)
    return index


def _validate_checks(rows: list[Mapping[str, Any]], input_index: Mapping[str, Any], findings: list[dict[str, str]]) -> dict[str, Mapping[str, Any]]:
    index = _ids(rows, "checks", "check_id", findings)
    for pos, row in enumerate(rows):
        if not isinstance(row.get("kind"), str) or not row.get("kind"):
            findings.append(_finding("check_kind_missing", f"$.checks[{pos}].kind", "check kind is required"))
        if not isinstance(row.get("command"), str) or not row.get("command"):
            findings.append(_finding("check_command_missing", f"$.checks[{pos}].command", "check command is required"))
        if not isinstance(row.get("args", []), list) or not all(isinstance(item, str) for item in row.get("args", [])):
            findings.append(_finding("check_args_invalid", f"$.checks[{pos}].args", "args must be a list of strings"))
        if not isinstance(row.get("expected"), Mapping):
            findings.append(_finding("check_oracle_missing", f"$.checks[{pos}].expected", "check expected oracle is required"))
        _references(rows=[row], name="checks", field="input_ids", known=input_index, findings=findings)
    return index


def compile_direct_contract(
    skill_root: Path,
    binding_path: Path,
    *,
    write: bool = False,
) -> tuple[bool, str, tuple[dict[str, str], ...], Mapping[str, Any] | None, Mapping[str, Any] | None, tuple[str, ...]]:
    """Compile one v3 source and return plain records for CompileResult."""

    skill_root = skill_root.resolve()
    binding_path = binding_path.resolve()
    findings: list[dict[str, str]] = []
    try:
        source = _load_json(binding_path)
    except ValueError as exc:
        return False, "blocked", (_finding("binding_source_unreadable", "$.binding", str(exc)),), None, None, ()
    if source.get("schema_version") != SCHEMA_VERSION:
        findings.append(_finding("unsupported_contract_schema", "$.schema_version", f"expected {SCHEMA_VERSION}"))
    if not isinstance(source.get("skill_id"), str) or not source.get("skill_id"):
        findings.append(_finding("skill_id_missing", "$.skill_id", "skill_id is required"))
    for field in sorted(LEGACY_FIELDS & set(source)):
        findings.append(_finding("legacy_field_present", f"$.{field}", "legacy platform field is not accepted by the compact contract"))

    inputs = _rows(source.get("inputs"), "inputs", findings)
    routes = _rows(source.get("routes"), "routes", findings)
    steps = _rows(source.get("steps"), "steps", findings)
    obligations = _rows(source.get("obligations"), "obligations", findings)
    checks = _rows(source.get("checks"), "checks", findings)
    input_index = _validate_inputs(inputs, skill_root, findings)
    check_index = _validate_checks(checks, input_index, findings)
    step_index = _ids(steps, "steps", "step_id", findings)
    obligation_index = _ids(obligations, "obligations", "obligation_id", findings)
    _validate_routes(routes, step_index, obligation_index, findings)
    for pos, row in enumerate(steps):
        _references([row], "steps", "requires", step_index, findings)
        _references([row], "steps", "check_ids", check_index, findings)
    for pos, row in enumerate(obligations):
        _references([row], "obligations", "check_ids", check_index, findings)

    if findings:
        return False, "blocked", tuple(findings), None, None, ()

    input_fingerprints = {
        str(row["id"]): _hash_file((skill_root / str(row["path"])).resolve())
        for row in inputs
    }
    source_identity = {
        "path": binding_path.relative_to(skill_root).as_posix(),
        "content_hash": _hash_file(binding_path),
        "input_fingerprints": input_fingerprints,
    }
    contract_body: dict[str, Any] = {
        "schema_version": COMPILED_SCHEMA_VERSION,
        "skill_id": source["skill_id"],
        "inputs": [dict(row) for row in inputs],
        "routes": [dict(row) for row in routes],
        "steps": [dict(row) for row in steps],
        "obligations": [dict(row) for row in obligations],
        "checks": [dict(row) for row in checks],
        "check_declarations_hash": wire_hash(checks),
        "source_identity": source_identity,
        "claim_boundary": "Compilation derives one contract from the explicit source; it does not execute checks or prove installation or publication.",
    }
    projection = source.get("consumer_projection")
    if isinstance(projection, Mapping):
        contract_body["consumer_projection"] = dict(projection)
        file_paths = projection.get("file_paths")
        if isinstance(file_paths, list) and all(isinstance(item, str) and item for item in file_paths):
            contract_body["content_impact_plan"] = {
                "schema_version": "skillguard.content_impact_plan.v3",
                "member_root_path": ".",
                "inventory": [
                    {"path": item.replace("\\", "/"), "install_disposition": "copy"}
                    for item in sorted(set(file_paths))
                ],
            }
    for identity_field in ("maintenance_unit_id", "member_skill_ids"):
        if identity_field in source:
            contract_body[identity_field] = source[identity_field]
    contract = dict(contract_body)
    contract["contract_hash"] = wire_hash(contract_body)
    manifest_body: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "skill_id": source["skill_id"],
        "contract_hash": contract["contract_hash"],
        "checks": [dict(row) for row in checks],
        "check_declarations_hash": wire_hash(checks),
        "claim_boundary": "The manifest preserves declared commands, arguments, inputs and oracles; it does not claim their execution.",
    }
    manifest = dict(manifest_body)
    manifest["manifest_hash"] = wire_hash(manifest_body)

    control_root = skill_root / ".skillguard"
    outputs = (
        (control_root / "compiled-contract.json", contract),
        (control_root / "check-manifest.json", manifest),
    )
    expected = [(path, canonical_json_bytes(payload)) for path, payload in outputs]
    written: list[str] = []
    parity_findings: list[dict[str, str]] = []
    for path, encoded in expected:
        if write:
            if not _current_bytes(path, encoded):
                atomic_write_json(path, dict(next(payload for candidate, payload in outputs if candidate == path)))
                written.append(path.relative_to(skill_root).as_posix())
        elif not _current_bytes(path, encoded):
            parity_findings.append(_finding("generated_file_stale", path.relative_to(skill_root).as_posix(), path.relative_to(skill_root).as_posix()))
    if parity_findings:
        return False, "blocked", tuple(parity_findings), contract, manifest, tuple(written)
    return True, "pass", (), contract, manifest, tuple(written)


__all__ = ["compile_direct_contract", "SCHEMA_VERSION"]
