"""Deterministic compiler for FlowGuard-backed SkillGuard V2 contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contract_schema import (
    BINDING_SOURCE_SCHEMA,
    CHECK_MANIFEST_SCHEMA,
    CLOSURE_PROFILE_ORDER,
    COMPILED_CONTRACT_SCHEMA,
    SchemaFinding,
    validate_binding_source,
    validate_check_manifest,
    validate_compiled_contract,
)
from .flowguard_adapter import FlowGuardAdapterError, load_flowguard_model
from .evidence_policy import required_evidence_class


BINDING_SOURCE_FILE = "contract-source.json"
COMPILED_CONTRACT_FILE = "compiled-contract.json"
CHECK_MANIFEST_FILE = "check-manifest.json"
COMPILER_VERSION = "skillguard.contract_compiler.v2"

TRANSIENT_IMPLEMENTATION_PARTS = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".skillguard",
        "__pycache__",
        "node_modules",
    }
)
TRANSIENT_IMPLEMENTATION_SUFFIXES = frozenset({".pyc", ".pyo"})
TRANSIENT_IMPLEMENTATION_FILES = frozenset({".DS_Store", "Thumbs.db"})


@dataclass(frozen=True)
class CompileResult:
    ok: bool
    status: str
    findings: tuple[SchemaFinding, ...]
    compiled_contract: Mapping[str, Any] | None = None
    check_manifest: Mapping[str, Any] | None = None
    written_files: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "skillguard_v2_compile_report",
            "ok": self.ok,
            "status": self.status,
            "findings": [row.to_dict() for row in self.findings],
            "contract_hash": (
                str(self.compiled_contract.get("contract_hash", ""))
                if self.compiled_contract
                else ""
            ),
            "manifest_hash": (
                str(self.check_manifest.get("manifest_hash", ""))
                if self.check_manifest
                else ""
            ),
            "written_files": list(self.written_files),
            "claim_boundary": (
                "Compilation proves deterministic model/binding parity and exact check mapping. "
                "It does not execute target work or prove current runtime, functional, release, or publication closure."
            ),
        }


@dataclass(frozen=True)
class BindingMigrationCandidate:
    payload: Mapping[str, Any]
    findings: tuple[SchemaFinding, ...]


def canonical_json_bytes(payload: object) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def canonical_hash(payload: object) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest().upper()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def path_fingerprint(path: Path) -> str:
    if path.is_file():
        return file_hash(path)
    if path.is_dir():
        rows = [
            {
                "path": child.relative_to(path).as_posix(),
                "sha256": file_hash(child),
            }
            for child in sorted(item for item in path.rglob("*") if item.is_file())
            if not (set(child.relative_to(path).parts) & TRANSIENT_IMPLEMENTATION_PARTS)
            and child.suffix.lower() not in TRANSIENT_IMPLEMENTATION_SUFFIXES
            and child.name not in TRANSIENT_IMPLEMENTATION_FILES
        ]
        return canonical_hash(rows)
    raise ValueError(f"implementation path is missing: {path}")


def _load_json(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing JSON file: {path.name}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON file {path.name}: {exc.msg}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError(f"JSON root must be an object: {path.name}")
    return payload


def _ensure_under(path: Path, root: Path, finding_path: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"{finding_path} must stay under repository root") from exc
    return resolved


def _index(rows: Sequence[Mapping[str, Any]], key: str) -> dict[str, Mapping[str, Any]]:
    return {str(row.get(key, "")): row for row in rows if str(row.get(key, ""))}


def _cross_validate(model: Mapping[str, Any], binding: Mapping[str, Any]) -> tuple[SchemaFinding, ...]:
    findings: list[SchemaFinding] = []
    if binding.get("model_id") != model.get("model_id"):
        findings.append(
            SchemaFinding(
                "binding_model_mismatch",
                "$.model_id",
                f"binding={binding.get('model_id')} model={model.get('model_id')}",
            )
        )
    step_index = _index(model.get("steps", []), "step_id")
    route_index = _index(model.get("routes", []), "route_id")
    obligation_index = _index(model.get("obligations", []), "obligation_id")
    step_binding_index = _index(binding.get("step_bindings", []), "step_id")
    check_index = _index(binding.get("checks", []), "check_id")
    artifact_index = _index(binding.get("artifacts", []), "artifact_id")
    judgment_rubric_index = _index(binding.get("judgment_rubrics", []), "rubric_id")

    for step_id, step in step_index.items():
        if step.get("terminal_kind"):
            continue
        if step_id not in step_binding_index:
            findings.append(SchemaFinding("missing_step_binding", f"$.step_bindings[{step_id}]", step_id))
    for step_id, row in step_binding_index.items():
        if step_id not in step_index:
            findings.append(SchemaFinding("orphan_step_binding", f"$.step_bindings[{step_id}]", step_id))
            continue
        check_ids = tuple(str(item) for item in row.get("check_ids", []))
        if not check_ids:
            findings.append(SchemaFinding("step_without_check", f"$.step_bindings[{step_id}].check_ids", step_id))
        for check_id in check_ids:
            if check_id not in check_index:
                findings.append(SchemaFinding("dangling_step_check", f"$.step_bindings[{step_id}]", check_id))
        for artifact_id in row.get("output_artifact_ids", []):
            if str(artifact_id) not in artifact_index:
                findings.append(SchemaFinding("dangling_step_artifact", f"$.step_bindings[{step_id}]", str(artifact_id)))
        try:
            evidence_class = required_evidence_class({"binding": row})
        except ValueError as exc:
            findings.append(
                SchemaFinding(
                    "step_evidence_policy_invalid",
                    f"$.step_bindings[{step_id}].action.evidence_class",
                    str(exc),
                )
            )
            evidence_class = ""
        if evidence_class == "judged":
            action = row.get("action", {}) if isinstance(row.get("action"), Mapping) else {}
            rubric_id = str(action.get("rubric_id", ""))
            if not rubric_id:
                findings.append(
                    SchemaFinding(
                        "judged_step_rubric_missing",
                        f"$.step_bindings[{step_id}].action.rubric_id",
                        step_id,
                    )
                )
            elif rubric_id not in judgment_rubric_index:
                findings.append(
                    SchemaFinding(
                        "judged_step_rubric_unknown",
                        f"$.step_bindings[{step_id}].action.rubric_id",
                        rubric_id,
                    )
                )

    covered_obligations: set[str] = set()
    all_obligation_ids = set(obligation_index)
    referenced_checks = {
        str(check_id)
        for row in step_binding_index.values()
        for check_id in row.get("check_ids", [])
    }
    for check_id, row in check_index.items():
        coverage = {str(item) for item in row.get("covers_obligation_ids", [])}
        if check_id not in referenced_checks:
            findings.append(SchemaFinding("orphan_check", f"$.checks[{check_id}]", check_id))
        unknown = coverage - all_obligation_ids
        for obligation_id in sorted(unknown):
            findings.append(SchemaFinding("check_unknown_obligation", f"$.checks[{check_id}]", obligation_id))
        if len(all_obligation_ids) > 1 and coverage == all_obligation_ids:
            if row.get("coverage_scope") != "suite" or not str(row.get("coverage_rationale", "")).strip():
                findings.append(
                    SchemaFinding(
                        "broad_all_check_binding",
                        f"$.checks[{check_id}].covers_obligation_ids",
                        "all-obligation coverage requires suite scope and a concrete rationale",
                    )
                )
        covered_obligations.update(coverage & all_obligation_ids)
    for obligation_id in sorted(all_obligation_ids - covered_obligations):
        if bool(obligation_index[obligation_id].get("required", True)):
            findings.append(SchemaFinding("required_obligation_without_check", "$.checks", obligation_id))

    referenced_artifacts = {
        str(artifact_id)
        for row in step_binding_index.values()
        for artifact_id in row.get("output_artifact_ids", [])
    }
    for artifact_id, row in artifact_index.items():
        producer_step = str(row.get("producer_step_id", ""))
        if producer_step not in step_index:
            findings.append(SchemaFinding("artifact_unknown_producer", f"$.artifacts[{artifact_id}]", producer_step))
        if artifact_id not in referenced_artifacts:
            findings.append(SchemaFinding("orphan_artifact", f"$.artifacts[{artifact_id}]", artifact_id))

    previous_requirements: set[str] = set()
    profile_index = _index(binding.get("closure_profiles", []), "profile_id")
    for profile_id in CLOSURE_PROFILE_ORDER:
        row = profile_index.get(profile_id, {})
        requirements = {str(item) for item in row.get("required_obligation_ids", [])}
        if not previous_requirements.issubset(requirements):
            findings.append(
                SchemaFinding(
                    "non_monotonic_closure_profile",
                    f"$.closure_profiles[{profile_id}]",
                    "stronger profiles must include all weaker-profile obligations",
                )
            )
        previous_requirements = requirements

    for route_id, route in route_index.items():
        success_terminal = str(route.get("success_terminal_step_id", ""))
        terminal = step_index.get(success_terminal)
        if terminal is None or terminal.get("terminal_kind") != "success":
            findings.append(SchemaFinding("uncovered_success_terminal", f"$.routes[{route_id}]", success_terminal))
    return tuple(findings)


def _build_outputs(
    skill_id: str,
    model: Mapping[str, Any],
    binding: Mapping[str, Any],
    source_fingerprints: Mapping[str, str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    step_binding_index = _index(binding.get("step_bindings", []), "step_id")
    bound_steps = []
    for step in model.get("steps", []):
        row = dict(step)
        binding_row = step_binding_index.get(str(step.get("step_id", "")))
        if binding_row is not None:
            row["binding"] = {
                "action": dict(binding_row.get("action", {})),
                "check_ids": list(binding_row.get("check_ids", [])),
                "output_artifact_ids": list(binding_row.get("output_artifact_ids", [])),
            }
        bound_steps.append(row)
    bound_step_index = _index(bound_steps, "step_id")
    obligation_check_ids: dict[str, list[str]] = {}
    for check in binding.get("checks", []):
        check_id = str(check.get("check_id", ""))
        for obligation_id in check.get("covers_obligation_ids", []):
            obligation_check_ids.setdefault(str(obligation_id), []).append(check_id)
    enriched_obligations: list[dict[str, Any]] = []
    for obligation in model.get("obligations", []):
        row = dict(obligation)
        obligation_id = str(row.get("obligation_id", ""))
        required_checks = sorted(dict.fromkeys(obligation_check_ids.get(obligation_id, [])))
        if required_checks:
            row["required_check_ids"] = required_checks
        evidence_classes = sorted(
            {
                required_evidence_class(bound_step_index[step_id])
                for step_id in (str(item) for item in row.get("owner_step_ids", []))
                if step_id in bound_step_index
            }
        )
        if evidence_classes:
            row["evidence_classes"] = evidence_classes
        enriched_obligations.append(row)
    model_path = str(binding.get("model_path", ""))
    contract: dict[str, Any] = {
        "schema_version": COMPILED_CONTRACT_SCHEMA,
        "compiler_version": COMPILER_VERSION,
        "skill_id": skill_id,
        "model_id": model["model_id"],
        "parent_model_id": model["parent_model_id"],
        "flowguard_schema_version": model["flowguard_schema_version"],
        "model_path": model_path,
        "functions": list(model["functions"]),
        "routes": list(model["routes"]),
        "steps": bound_steps,
        "obligations": enriched_obligations,
        "artifacts": list(binding.get("artifacts", [])),
        "closure_profiles": list(binding.get("closure_profiles", [])),
        "judgment_rubrics": list(binding.get("judgment_rubrics", [])),
        "source_fingerprints": dict(source_fingerprints),
        "claim_boundary": str(binding.get("claim_boundary", "")),
    }
    contract["contract_hash"] = canonical_hash(contract)
    compiled_checks: list[dict[str, Any]] = []
    for source_check in binding.get("checks", []):
        check = dict(source_check)
        if check.get("kind") == "model_assertion" and not check.get("command"):
            check.update(
                {
                    "command": "python",
                    "args": [model_path],
                    "cwd_token": "repository_root",
                    "expected": {"exit_code": 0},
                    "assertion_scope": "current_full_flowguard_model",
                }
            )
        compiled_checks.append(check)
    manifest: dict[str, Any] = {
        "schema_version": CHECK_MANIFEST_SCHEMA,
        "compiler_version": COMPILER_VERSION,
        "skill_id": skill_id,
        "model_id": model["model_id"],
        "contract_hash": contract["contract_hash"],
        "checks": compiled_checks,
        "source_fingerprints": dict(source_fingerprints),
        "claim_boundary": (
            "This manifest binds checks to exact model obligations. Passing checks do not by themselves "
            "prove target execution, user-visible quality, full closure, installation, or publication."
        ),
    }
    manifest["manifest_hash"] = canonical_hash(manifest)
    return contract, manifest


def compile_skill_contract(
    skill_root: Path,
    *,
    repository_root: Path | None = None,
    write: bool = False,
) -> CompileResult:
    skill_root = skill_root.resolve()
    repo_root = (repository_root or skill_root).resolve()
    control_root = skill_root / ".skillguard"
    binding_path = control_root / BINDING_SOURCE_FILE
    findings: list[SchemaFinding] = []
    try:
        binding = _load_json(binding_path)
    except ValueError as exc:
        return CompileResult(False, "blocked", (SchemaFinding("binding_source_unreadable", "$.binding", str(exc)),))
    findings.extend(validate_binding_source(binding))
    model_path_text = str(binding.get("model_path", ""))
    try:
        model_path = _ensure_under(repo_root / model_path_text, repo_root, "$.model_path")
    except ValueError as exc:
        findings.append(SchemaFinding("model_path_outside_repository", "$.model_path", str(exc)))
        model_path = repo_root / "__invalid_model__"
    model: Mapping[str, Any] | None = None
    if not findings:
        try:
            snapshot = load_flowguard_model(model_path, repo_root)
            model = snapshot.model_export
        except FlowGuardAdapterError as exc:
            findings.extend(exc.findings)
    if model is not None:
        findings.extend(_cross_validate(model, binding))
    if findings or model is None:
        return CompileResult(False, "blocked", tuple(findings))

    entrypoint = skill_root / "SKILL.md"
    source_fingerprints = {
        "model": file_hash(model_path),
        "binding": file_hash(binding_path),
        "entrypoint": file_hash(entrypoint) if entrypoint.is_file() else "MISSING",
        "model_export": canonical_hash(model),
    }
    for index, path_text in enumerate(binding.get("implementation_paths", [])):
        try:
            implementation_path = _ensure_under(repo_root / str(path_text), repo_root, f"$.implementation_paths[{index}]")
            source_fingerprints[f"implementation:{Path(str(path_text)).as_posix()}"] = path_fingerprint(implementation_path)
        except ValueError as exc:
            findings.append(SchemaFinding("implementation_path_invalid", f"$.implementation_paths[{index}]", str(exc)))
    if findings:
        return CompileResult(False, "blocked", tuple(findings))
    contract, manifest = _build_outputs(str(binding["skill_id"]), model, binding, source_fingerprints)
    findings.extend(validate_compiled_contract(contract))
    findings.extend(validate_check_manifest(manifest))
    if findings:
        return CompileResult(False, "blocked", tuple(findings), contract, manifest)

    outputs = (
        (control_root / COMPILED_CONTRACT_FILE, contract),
        (control_root / CHECK_MANIFEST_FILE, manifest),
    )
    written: list[str] = []
    parity_findings: list[SchemaFinding] = []
    for path, payload in outputs:
        expected = canonical_json_bytes(payload)
        if write:
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.is_file() or path.read_bytes() != expected:
                path.write_bytes(expected)
                written.append(path.relative_to(skill_root).as_posix())
        elif not path.is_file():
            parity_findings.append(SchemaFinding("generated_file_missing", path.name, path.name))
        elif path.read_bytes() != expected:
            parity_findings.append(SchemaFinding("stale_generated_contract", path.name, path.name))
    all_findings = tuple(parity_findings)
    return CompileResult(
        ok=not all_findings,
        status="pass" if not all_findings else "blocked",
        findings=all_findings,
        compiled_contract=contract,
        check_manifest=manifest,
        written_files=tuple(written),
    )


def migrate_v1_binding_candidate(skill_root: Path) -> BindingMigrationCandidate:
    skill_root = skill_root.resolve()
    control_root = skill_root / ".skillguard"
    work_contract_path = control_root / "work-contract.json"
    old_manifest_path = control_root / "check_manifest.json"
    sources: list[str] = []
    old_contract: Mapping[str, Any] = {}
    old_manifest: Mapping[str, Any] = {}
    findings: list[SchemaFinding] = []
    if work_contract_path.is_file():
        old_contract = _load_json(work_contract_path)
        sources.append(".skillguard/work-contract.json")
    else:
        findings.append(SchemaFinding("v1_work_contract_missing", "$.migration", "work-contract.json"))
    if old_manifest_path.is_file():
        old_manifest = _load_json(old_manifest_path)
        sources.append(".skillguard/check_manifest.json")
    else:
        findings.append(SchemaFinding("v1_check_manifest_missing", "$.migration", "check_manifest.json"))
    candidate = {
        "schema_version": BINDING_SOURCE_SCHEMA,
        "skill_id": str(old_contract.get("skill_id") or skill_root.name),
        "model_id": "UNCONFIRMED_FLOWGUARD_MODEL",
        "model_path": ".flowguard/skill_contract_model.py",
        "confirmed": False,
        "release_eligible": False,
        "inference_sources": sources,
        "inferred_fields": ["skill_id", "legacy_check_ids", "legacy_phase_ids"],
        "legacy_check_ids": [
            str(row.get("check_id", ""))
            for row in old_manifest.get("checks", [])
            if isinstance(row, Mapping) and row.get("check_id")
        ],
        "legacy_phase_ids": [
            str(row.get("phase_id", ""))
            for row in old_contract.get("phases", [])
            if isinstance(row, Mapping) and row.get("phase_id")
        ],
        "step_bindings": [],
        "checks": [],
        "artifacts": [],
        "closure_profiles": [],
        "judgment_rubrics": [],
        "claim_boundary": (
            "Migration candidate only. No route, step, check, artifact, runtime, or release claim is confirmed."
        ),
    }
    findings.append(
        SchemaFinding(
            "migration_candidate_requires_confirmation",
            "$.confirmed",
            "candidate cannot compile or release until a FlowGuard model and every binding are reviewed",
        )
    )
    return BindingMigrationCandidate(payload=candidate, findings=tuple(findings))
