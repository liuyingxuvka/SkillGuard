"""Production portfolio prepare, execute, and assemble orchestration.

The runner deliberately delegates contract compilation, route selection,
claimed-run execution, check/receipt creation, closure replay, installed
content parity, and final graduation validation to their existing current owners.
It owns only the durable target-attempt phase graph and exact bindings between
those authorities.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from .capability_contract import CAPABILITY_PATH_FIELDS
from .check_runner import resolve_owner_evidence_root
from .closure import load_closure
from .contract_compiler import (
    canonical_hash,
    canonical_json_bytes,
    compile_skill_contract,
    path_fingerprint,
)
from .installed_parity import (
    replay_installed_content_parity_currentness,
    validate_installed_parity_receipt,
    verify_installed_content_parity,
)
from .execution_depth import load_target_execution_receipts
from .installation_receipt import (
    VerifiedInstallationContext,
    load_scheduled_production_installation_context,
    validate_verified_installation_context,
)
from .portfolio import (
    DEFAULT_REQUIRED_JOB_CLASS_IDS,
    GRADUATION_EVIDENCE_SCHEMA,
    JOB_CLASS_EXPECTED_OUTCOMES,
    PORTFOLIO_JOB_EVIDENCE_SCHEMA,
    PORTFOLIO_JOB_PLAN_SCHEMA,
    PORTFOLIO_JOB_SPEC_SCHEMA,
    _job_contract_path_findings,
    _load_portfolio_production_revalidation_bindings,
    _member_capability_inventory_findings,
    _same_guard,
    assemble_capability_stage_receipt,
    assemble_full_run_receipt,
    build_portfolio_production_revalidation_binding,
    current_guard,
    derive_target_identity,
    graduate_portfolio_target,
    portfolio_registry_hash,
    portfolio_production_revalidation_fingerprint,
    representative_jobs_coverage_fingerprint,
    validate_registry,
)
from .portfolio_records import (
    PortfolioRecordError,
    reference_existing_file,
    resolve_record_ref,
    write_hash_bound_json,
)
from .portable_content import ignored_copy_names
from .receipts import load_receipts
from .run_store import utc_now
from .step_runtime import resume_run
from .supervisor import supervise_contract_run, validate_supervisor_packet


PREPARATION_SCHEMA = "skillguard.portfolio_preparation_receipt.v1"
EXECUTION_RESULT_SCHEMA = "skillguard.portfolio_execution_result.v1"
ASSEMBLY_RESULT_SCHEMA = "skillguard.portfolio_assembly_result.v1"
TERMINAL_OBSERVATION_SCHEMA = "skillguard.portfolio_terminal_observation.v1"
MUTATION_OBSERVATION_SCHEMA = "skillguard.portfolio_mutation_observation.v1"


@dataclass(frozen=True)
class PortfolioRunnerError(RuntimeError):
    code: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


def _fail(code: str, detail: object = "") -> None:
    raise PortfolioRunnerError(code, str(detail))


def _safe_token(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    readable = "".join(
        character.lower() if character.isalnum() else "-" for character in value
    ).strip("-")[:36]
    return f"{readable or 'record'}-{digest}"


def _record_ref(relative: PurePosixPath, payload: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest().upper()
    return f"record:{relative.as_posix()}@{digest}"


def _finalize(payload: dict[str, Any], field: str) -> dict[str, Any]:
    payload[field] = canonical_hash(payload)
    return payload


def _load_json_ref(record_ref: str, workspace_root: Path) -> dict[str, Any]:
    try:
        _path, raw = resolve_record_ref(record_ref, workspace_root)
        payload = json.loads(raw.decode("utf-8"))
    except (PortfolioRecordError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        _fail("portfolio_runner_record_invalid", getattr(exc, "code", type(exc).__name__))
    if not isinstance(payload, dict):
        _fail("portfolio_runner_record_not_object", record_ref)
    return payload


def _entry(registry: Mapping[str, Any], skill_id: str) -> Mapping[str, Any]:
    matches = [
        row
        for row in registry.get("entries", [])
        if isinstance(row, Mapping) and row.get("skill_id") == skill_id
    ]
    if len(matches) != 1:
        _fail("portfolio_runner_target_not_unique", skill_id)
    entry = matches[0]
    if entry.get("lifecycle") not in {
        "active_owned",
        "active_adopted",
        "pending_adoption",
    }:
        _fail("portfolio_runner_target_not_active", skill_id)
    if entry.get("capability_inventory_status") != "current":
        _fail("portfolio_runner_capability_inventory_not_current", skill_id)
    return entry


def _source_configuration(entry: Mapping[str, Any]) -> tuple[str, str, list[str]]:
    target_kind = str(entry.get("target_kind", ""))
    skill_paths = sorted(str(value) for value in entry.get("skill_paths", []))
    canonical_source = entry.get("canonical_source", {})
    primary = (
        str(canonical_source.get("skill_path", ""))
        if isinstance(canonical_source, Mapping)
        else ""
    )
    if target_kind not in {"single_skill", "skill_suite"} or not skill_paths:
        _fail("portfolio_runner_target_topology_invalid", entry.get("skill_id", ""))
    if not primary:
        primary = skill_paths[0]
    if primary not in skill_paths:
        _fail("portfolio_runner_primary_member_invalid", primary)
    return target_kind, primary, skill_paths


def _compile_members(
    repository_root: Path,
    identity: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    compiled: dict[str, dict[str, Any]] = {}
    for member in identity.get("member_identities", []):
        if not isinstance(member, Mapping):
            _fail("portfolio_runner_member_identity_invalid")
        member_id = str(member.get("member_skill_id", ""))
        member_path = str(member.get("skill_path", ""))
        skill_root = repository_root if member_path == "." else repository_root / member_path
        result = compile_skill_contract(
            skill_root,
            repository_root=repository_root,
            write=False,
        )
        if not result.ok or result.compiled_contract is None or result.check_manifest is None:
            _fail(
                "portfolio_runner_member_compile_failed",
                f"{member_id}:{','.join(sorted({row.code for row in result.findings}))}",
            )
        contract = dict(result.compiled_contract)
        manifest = dict(result.check_manifest)
        if (
            contract.get("contract_hash") != member.get("contract_hash")
            or manifest.get("manifest_hash") != member.get("manifest_hash")
        ):
            _fail("portfolio_runner_member_identity_drift", member_id)
        compiled[member_id] = {
            "skill_path": member_path,
            "contract": contract,
            "manifest": manifest,
        }
    return compiled


def _variant_for_job(
    contract: Mapping[str, Any],
    capability_id: str,
    job_class_id: str,
    requested_variant_id: str,
) -> Mapping[str, Any]:
    authority = next(
        (
            row
            for row in contract.get("portfolio_capability_contracts", [])
            if isinstance(row, Mapping) and row.get("capability_id") == capability_id
        ),
        None,
    )
    if authority is None:
        _fail("portfolio_runner_capability_authority_missing", capability_id)
    variants = [
        row
        for row in authority.get("path_variants", [])
        if isinstance(row, Mapping)
        and job_class_id in set(row.get("job_class_ids", []))
        and (not requested_variant_id or row.get("variant_id") == requested_variant_id)
    ]
    if len(variants) != 1:
        _fail(
            "portfolio_runner_capability_variant_not_unique",
            f"{capability_id}:{job_class_id}:{requested_variant_id or 'auto'}:{len(variants)}",
        )
    return variants[0]


def _evidence_requirements(job_class_id: str) -> list[str]:
    values = {"manifest_check_passed", "closure_replay_current"}
    if job_class_id == "recovery_or_resume":
        values.add("resume_replay_current")
    elif job_class_id == "artifact_check":
        values.add("artifact_current")
    elif job_class_id in {"invalid_input", "out_of_scope"}:
        values.add("no_mutation")
    elif job_class_id == "judged_quality":
        values.add("judgment_current")
    return sorted(values)


def _artifact_request_path(
    repository_root: Path,
    member_root: Path,
    contract: Mapping[str, Any],
    artifact_ids: set[str],
) -> str:
    if not artifact_ids:
        return ""
    artifacts = {
        str(row.get("artifact_id", "")): row
        for row in contract.get("artifacts", [])
        if isinstance(row, Mapping)
    }
    declaration = artifacts.get(sorted(artifact_ids)[0])
    if declaration is None or not str(declaration.get("path_template", "")):
        _fail("portfolio_runner_artifact_path_missing", sorted(artifact_ids)[0])
    relative = member_root.relative_to(repository_root)
    return (relative / str(declaration["path_template"])).as_posix()


def _validate_job_matrix(
    job_matrix: Sequence[Mapping[str, Any]],
    *,
    entry: Mapping[str, Any],
    identity: Mapping[str, Any],
    members: Mapping[str, Mapping[str, Any]],
    repository_root: Path,
    created_at: str,
    registry: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if isinstance(job_matrix, (str, bytes)) or not job_matrix:
        _fail("portfolio_runner_job_matrix_missing")
    inventory_findings = _member_capability_inventory_findings(
        entry,
        target_identity=identity,
    )
    if inventory_findings:
        _fail(
            "portfolio_runner_member_capability_inventory_invalid",
            ",".join(sorted(row["code"] for row in inventory_findings)),
        )
    owners: dict[str, str] = {}
    inventory_by_member: dict[str, set[str]] = {}
    for row in entry.get("member_capability_inventory", []):
        if not isinstance(row, Mapping):
            continue
        member_id = str(row.get("member_skill_id", ""))
        inventory_by_member[member_id] = {
            str(value) for value in row.get("required_capability_ids", [])
        }
        for capability_id in row.get("required_capability_ids", []):
            owners[str(capability_id)] = member_id
    for member_id, member in members.items():
        declared = {
            str(row.get("capability_id", ""))
            for row in member["contract"].get("portfolio_capability_contracts", [])
            if isinstance(row, Mapping) and row.get("capability_id")
        }
        expected = inventory_by_member.get(member_id, set())
        if declared != expected:
            _fail(
                "portfolio_runner_member_capability_authority_mismatch",
                f"{member_id}:missing={','.join(sorted(expected-declared))};"
                f"extra={','.join(sorted(declared-expected))}",
            )
    required_capabilities = set(str(value) for value in entry.get("required_capability_ids", []))
    required_classes = set(
        str(value)
        for value in entry.get(
            "required_job_class_ids", DEFAULT_REQUIRED_JOB_CLASS_IDS
        )
    )
    seen_ids: set[str] = set()
    covered_capabilities: set[str] = set()
    covered_classes: set[str] = set()
    covered_members: set[str] = set()
    specs: list[dict[str, Any]] = []
    for index, raw_job in enumerate(job_matrix):
        if not isinstance(raw_job, Mapping):
            _fail("portfolio_runner_job_not_object", index)
        job_id = str(raw_job.get("job_id", ""))
        job_class_id = str(raw_job.get("job_class_id", ""))
        member_id = str(raw_job.get("member_skill_id", ""))
        capability_ids = sorted(
            str(value) for value in raw_job.get("covered_capability_ids", [])
        )
        if not job_id or job_id in seen_ids:
            _fail("portfolio_runner_job_id_invalid", job_id or index)
        if job_class_id not in JOB_CLASS_EXPECTED_OUTCOMES:
            _fail("portfolio_runner_job_class_invalid", f"{job_id}:{job_class_id}")
        if member_id not in members:
            _fail("portfolio_runner_job_member_unknown", f"{job_id}:{member_id}")
        if not capability_ids or len(capability_ids) != len(set(capability_ids)):
            _fail("portfolio_runner_job_capabilities_invalid", job_id)
        wrong_owner = [value for value in capability_ids if owners.get(value) != member_id]
        if wrong_owner:
            _fail(
                "portfolio_runner_job_capability_owner_mismatch",
                f"{job_id}:{','.join(wrong_owner)}",
            )
        member = members[member_id]
        contract = member["contract"]
        manifest = member["manifest"]
        requested_variants = raw_job.get("capability_variant_ids", {})
        if not isinstance(requested_variants, Mapping):
            _fail("portfolio_runner_capability_variant_map_invalid", job_id)
        requirements = _evidence_requirements(job_class_id)
        bindings: list[dict[str, Any]] = []
        for capability_id in capability_ids:
            variant = _variant_for_job(
                contract,
                capability_id,
                job_class_id,
                str(requested_variants.get(capability_id, "")),
            )
            binding = {"capability_id": capability_id}
            for field in CAPABILITY_PATH_FIELDS:
                binding[field] = sorted(str(value) for value in variant.get(field, []))
            binding["evidence_requirements"] = requirements
            bindings.append(binding)
        function_ids = sorted(
            {value for row in bindings for value in row["function_ids"]}
        )
        route_ids = sorted({value for row in bindings for value in row["route_ids"]})
        required_check_ids = sorted(
            {value for row in bindings for value in row["check_ids"]}
        )
        artifact_ids = {value for row in bindings for value in row["artifact_ids"]}
        selected_step_ids = {
            value for row in bindings for value in row["step_ids"]
        }
        step_index = {
            str(row.get("step_id", "")): row
            for row in contract.get("steps", [])
            if isinstance(row, Mapping)
        }
        execution_artifact_ids = {
            str(value)
            for step_id in selected_step_ids
            for value in step_index.get(step_id, {})
            .get("binding", {})
            .get("output_artifact_ids", [])
        }
        member_path = str(member["skill_path"])
        member_root = (
            repository_root if member_path == "." else repository_root / member_path
        )
        request_seed = raw_job.get("request", {})
        if not isinstance(request_seed, Mapping):
            _fail("portfolio_runner_job_request_invalid", job_id)
        request = dict(request_seed)
        request.update(
            {
                "function_ids": function_ids,
                "route_ids": route_ids,
                "claim_scope": str(request.get("claim_scope", "enforced")),
                "write_targets": list(
                    request.get(
                        "write_targets",
                        [f".skillguard/portfolio-artifacts/{_safe_token(job_id)}"],
                    )
                ),
                "request": str(request.get("request", job_id)),
                "portfolio_input": str(
                    request.get(
                        "portfolio_input",
                        "malformed" if job_class_id == "invalid_input" else "valid",
                    )
                ),
                "portfolio_scope": str(
                    request.get(
                        "portfolio_scope",
                        "external" if job_class_id == "out_of_scope" else "in-scope",
                    )
                ),
                "portfolio_artifact_path": str(
                    request.get(
                        "portfolio_artifact_path",
                        _artifact_request_path(
                            repository_root,
                            member_root,
                            contract,
                            execution_artifact_ids,
                        ),
                    )
                ),
            }
        )
        profiles = [str(value) for value in raw_job.get("profiles", ["enforced"])]
        steps = raw_job.get("steps", {})
        packet = {"request": request, "profiles": profiles, "steps": copy.deepcopy(steps)}
        validate_supervisor_packet(packet, contract=contract, route_ids=route_ids)
        spec: dict[str, Any] = {
            "schema_version": PORTFOLIO_JOB_SPEC_SCHEMA,
            "registry_id": str(registry.get("registry_id", "")),
            "scope_manifest_id": str(registry.get("scope_manifest_id", "")),
            "scope_manifest_hash": str(registry.get("scope_manifest_hash", "")),
            "skill_id": str(entry.get("skill_id", "")),
            "target_kind": str(identity.get("target_kind", "")),
            "skill_paths": list(identity.get("skill_paths", [])),
            "member_skill_id": member_id,
            "member_contract_hash": str(contract.get("contract_hash", "")),
            "job_id": job_id,
            "job_class_id": job_class_id,
            "covered_capability_ids": capability_ids,
            "capability_bindings": bindings,
            "required_check_ids": required_check_ids,
            "expected_outcome": JOB_CLASS_EXPECTED_OUTCOMES[job_class_id],
            "execution_packet": packet,
            "created_at": created_at,
            "claim_boundary": (
                "This spec freezes one exact target-authoritative capability path and its "
                "production execution packet before any representative claim."
            ),
        }
        _finalize(spec, "job_spec_hash")
        path_findings = _job_contract_path_findings(spec, contract, manifest)
        if path_findings:
            _fail(
                "portfolio_runner_job_contract_path_invalid",
                f"{job_id}:{','.join(sorted(row['code'] for row in path_findings))}",
            )
        specs.append(spec)
        seen_ids.add(job_id)
        covered_capabilities.update(capability_ids)
        covered_classes.add(job_class_id)
        covered_members.add(member_id)
    if covered_capabilities != required_capabilities:
        _fail(
            "portfolio_runner_capability_coverage_incomplete",
            f"missing={','.join(sorted(required_capabilities-covered_capabilities))};"
            f"extra={','.join(sorted(covered_capabilities-required_capabilities))}",
        )
    if not required_classes.issubset(covered_classes):
        _fail(
            "portfolio_runner_job_class_coverage_incomplete",
            ",".join(sorted(required_classes - covered_classes)),
        )
    if covered_members != set(members):
        _fail(
            "portfolio_runner_member_coverage_incomplete",
            f"missing={','.join(sorted(set(members)-covered_members))}",
        )
    return specs


def _assert_distinct_roots(repository_root: Path, workspace_root: Path) -> None:
    repository = repository_root.resolve()
    workspace = workspace_root.resolve()
    if (
        repository == workspace
        or repository.is_relative_to(workspace)
        or workspace.is_relative_to(repository)
    ):
        _fail("portfolio_runner_workspace_overlaps_repository")


def _write_prepared_tree(
    *,
    workspace_root: Path,
    attempt_relative: PurePosixPath,
    files: Mapping[PurePosixPath, Mapping[str, Any]],
) -> None:
    final_root = workspace_root / Path(*attempt_relative.parts)
    if final_root.exists():
        return
    temporary = final_root.with_name(f".{final_root.name}.{os.getpid()}.tmp")
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir(parents=True)
    try:
        for final_relative, payload in files.items():
            relative_inside = final_relative.relative_to(attempt_relative)
            path = temporary / Path(*relative_inside.parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(canonical_json_bytes(payload))
            with path.open("r+b") as handle:
                handle.flush()
                os.fsync(handle.fileno())
        os.replace(temporary, final_root)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)
        raise


def prepare_portfolio_attempt(
    *,
    registry: Mapping[str, Any],
    repository_root: Path,
    workspace_root: Path,
    skill_id: str,
    job_matrix: Sequence[Mapping[str, Any]],
    installed_target_root: Path | None = None,
) -> dict[str, Any]:
    """Freeze one complete target attempt before any representative claim."""

    repository_root = repository_root.resolve()
    workspace_root = workspace_root.resolve()
    workspace_root.mkdir(parents=True, exist_ok=True)
    _assert_distinct_roots(repository_root, workspace_root)
    guard = current_guard()
    registry_findings = validate_registry(registry, evidence_root=workspace_root)
    if registry_findings:
        _fail(
            "portfolio_runner_registry_invalid",
            ",".join(sorted({row["code"] for row in registry_findings})),
        )
    if not _same_guard(registry.get("active_guard"), guard):
        _fail("portfolio_runner_active_guard_mismatch")
    if registry.get("registry_hash") != portfolio_registry_hash(registry):
        _fail("portfolio_runner_registry_hash_invalid")
    entry = _entry(registry, skill_id)
    target_kind, primary, skill_paths = _source_configuration(entry)
    identity, identity_findings = derive_target_identity(
        repository_root,
        skill_root_relative=primary,
        expected_skill_id=skill_id,
        guard_runtime=guard,
        target_kind=target_kind,
        skill_root_relatives=skill_paths,
    )
    if identity is None or identity_findings:
        _fail(
            "portfolio_runner_target_identity_invalid",
            ",".join(sorted(row["code"] for row in identity_findings)),
        )
    members = _compile_members(repository_root, identity)
    created_at = utc_now()
    specs = _validate_job_matrix(
        job_matrix,
        entry=entry,
        identity=identity,
        members=members,
        repository_root=repository_root,
        created_at=created_at,
        registry=registry,
    )
    semantic_spec_hashes: list[str] = []
    for spec in specs:
        semantic_spec = dict(spec)
        semantic_spec.pop("job_spec_hash", None)
        semantic_spec.pop("created_at", None)
        semantic_spec_hashes.append(canonical_hash(semantic_spec))
    seed = {
        "registry_id": registry.get("registry_id"),
        "registry_revision": registry.get("revision"),
        "registry_hash": registry.get("registry_hash"),
        "skill_id": skill_id,
        "target_identity_receipt_hash": identity.get("receipt_hash"),
        "guard_runtime": guard,
        "semantic_job_spec_hashes": semantic_spec_hashes,
    }
    preparation_id = f"portfolio-prep-{canonical_hash(seed)[:24].lower()}"
    attempt_relative = PurePosixPath("portfolio-runs") / preparation_id
    final_receipt_path = (
        workspace_root / Path(*attempt_relative.parts) / "prepared" / "preparation.json"
    )
    if final_receipt_path.is_file():
        ref = reference_existing_file(final_receipt_path, workspace_root)
        existing = _load_json_ref(ref, workspace_root)
        if (
            existing.get("schema_version") != PREPARATION_SCHEMA
            or existing.get("preparation_id") != preparation_id
            or existing.get("seed_hash") != canonical_hash(seed)
            or existing.get("receipt_hash")
            != canonical_hash({key: value for key, value in existing.items() if key != "receipt_hash"})
        ):
            _fail("portfolio_runner_preparation_collision", preparation_id)
        return {
            "status": "prepared",
            "resumed": True,
            "preparation_id": preparation_id,
            "preparation_ref": ref,
            "preparation_receipt": existing,
        }

    prepared_prefix = attempt_relative / "prepared"
    files: dict[PurePosixPath, Mapping[str, Any]] = {}
    identity_relative = prepared_prefix / "target-identity.json"
    identity_ref = _record_ref(identity_relative, identity)
    files[identity_relative] = identity
    member_bindings: list[dict[str, Any]] = []
    for member_id, member in sorted(members.items()):
        token = _safe_token(member_id)
        contract_relative = prepared_prefix / "members" / token / "contract.json"
        manifest_relative = prepared_prefix / "members" / token / "check-manifest.json"
        contract_ref = _record_ref(contract_relative, member["contract"])
        manifest_ref = _record_ref(manifest_relative, member["manifest"])
        files[contract_relative] = member["contract"]
        files[manifest_relative] = member["manifest"]
        member_bindings.append(
            {
                "member_skill_id": member_id,
                "skill_path": member["skill_path"],
                "contract_ref": contract_ref,
                "contract_hash": member["contract"]["contract_hash"],
                "manifest_ref": manifest_ref,
                "manifest_hash": member["manifest"]["manifest_hash"],
            }
        )
    spec_bindings: list[dict[str, Any]] = []
    plan_jobs: list[dict[str, Any]] = []
    for index, spec in enumerate(specs):
        token = _safe_token(str(spec["job_id"]))
        relative = prepared_prefix / "job-specs" / f"{index:03d}-{token}.json"
        ref = _record_ref(relative, spec)
        files[relative] = spec
        spec_bindings.append(
            {
                "order": index,
                "job_id": spec["job_id"],
                "job_spec_ref": ref,
                "job_spec_hash": spec["job_spec_hash"],
            }
        )
        plan_jobs.append(
            {
                "job_id": spec["job_id"],
                "job_class_id": spec["job_class_id"],
                "member_skill_id": spec["member_skill_id"],
                "member_contract_hash": spec["member_contract_hash"],
                "job_spec_ref": ref,
                "job_spec_hash": spec["job_spec_hash"],
                "covered_capability_ids": spec["covered_capability_ids"],
            }
        )
    plan: dict[str, Any] = {
        "schema_version": PORTFOLIO_JOB_PLAN_SCHEMA,
        "registry_id": str(registry.get("registry_id", "")),
        "scope_manifest_id": str(registry.get("scope_manifest_id", "")),
        "scope_manifest_hash": str(registry.get("scope_manifest_hash", "")),
        "skill_id": skill_id,
        "target_kind": identity["target_kind"],
        "skill_paths": list(identity["skill_paths"]),
        "jobs": plan_jobs,
        "created_at": created_at,
        "claim_boundary": (
            "This is the single complete ordered target-level plan frozen atomically with every job spec before any claim."
        ),
    }
    _finalize(plan, "job_plan_hash")
    plan_relative = prepared_prefix / "job-plan.json"
    plan_ref = _record_ref(plan_relative, plan)
    files[plan_relative] = plan

    installed_binding: dict[str, Any] | None = None
    if installed_target_root is not None:
        installed_receipt = verify_installed_content_parity(
            repository_root,
            identity,
            installed_target_root,
            portfolio_projection_hash=str(guard["portfolio_projection_hash"]),
        )
        installed_findings = validate_installed_parity_receipt(
            installed_receipt,
            portfolio_projection_hash=str(guard["portfolio_projection_hash"]),
        )
        if installed_receipt.get("status") != "current" or installed_findings:
            _fail(
                "portfolio_runner_installed_parity_blocked",
                ",".join(
                    [
                        *(str(value) for value in installed_receipt.get("blockers", [])),
                        *(str(value) for value in installed_findings),
                    ]
                ),
            )
        installed_relative = (
            PurePosixPath("owner-receipts")
            / "installed-content-parity"
            / (
                str(installed_receipt["receipt_id"]).removeprefix("sha256:")
                + ".json"
            )
        )
        _installed_path, installed_ref = write_hash_bound_json(
            installed_relative,
            installed_receipt,
            workspace_root,
        )
        installed_binding = {
            "ref": installed_ref,
            "receipt_id": installed_receipt["receipt_id"],
            "receipt_hash": installed_receipt["receipt_hash"],
        }
    elif target_kind == "skill_suite":
        _fail("portfolio_runner_suite_installed_parity_required", skill_id)

    receipt: dict[str, Any] = {
        "schema_version": PREPARATION_SCHEMA,
        "receipt_id": preparation_id,
        "preparation_id": preparation_id,
        "status": "prepared",
        "seed_hash": canonical_hash(seed),
        "registry_id": str(registry.get("registry_id", "")),
        "registry_revision": int(registry.get("revision", 0)),
        "registry_hash": str(registry.get("registry_hash", "")),
        "scope_manifest_id": str(registry.get("scope_manifest_id", "")),
        "scope_manifest_hash": str(registry.get("scope_manifest_hash", "")),
        "skill_id": skill_id,
        "target_kind": identity["target_kind"],
        "skill_root_token": identity["skill_root_token"],
        "skill_paths": list(identity["skill_paths"]),
        "guard_runtime": guard,
        "target_identity_receipt": {
            "ref": identity_ref,
            "receipt_id": identity["receipt_id"],
            "receipt_hash": identity["receipt_hash"],
        },
        "member_contracts": member_bindings,
        "job_plan_ref": plan_ref,
        "job_plan_hash": plan["job_plan_hash"],
        "job_specs": spec_bindings,
        "job_set_hash": canonical_hash(
            {
                "job_plan_ref": plan_ref,
                "job_plan_hash": plan["job_plan_hash"],
                "job_specs": spec_bindings,
            }
        ),
        "installed_parity_receipt": installed_binding,
        "prepared_sequence": 1,
        "prepared_at": created_at,
        "claim_boundary": (
            "This receipt proves one atomically persisted complete plan/spec set, current target and Guard identity, and optional exact installed-member parity before any run claim."
        ),
    }
    _finalize(receipt, "receipt_hash")
    receipt_relative = prepared_prefix / "preparation.json"
    files[receipt_relative] = receipt
    _write_prepared_tree(
        workspace_root=workspace_root,
        attempt_relative=attempt_relative,
        files=files,
    )
    preparation_ref = reference_existing_file(final_receipt_path, workspace_root)
    return {
        "status": "prepared",
        "resumed": False,
        "preparation_id": preparation_id,
        "preparation_ref": preparation_ref,
        "preparation_receipt": receipt,
    }


def _copy_ignore_for_root(repository_root: Path):
    repository_root = repository_root.resolve()

    def ignore(directory: str, names: list[str]) -> set[str]:
        return ignored_copy_names(repository_root, Path(directory), names)

    return ignore


def _assert_copy_tree_safe(repository_root: Path) -> None:
    for path in repository_root.rglob("*"):
        try:
            is_junction = bool(getattr(path, "is_junction", lambda: False)())
        except OSError:
            is_junction = True
        if path.is_symlink() or is_junction:
            _fail("portfolio_runner_source_link_unsupported", path.relative_to(repository_root).as_posix())


def _working_repository(
    repository_root: Path,
    workspace_root: Path,
    preparation_id: str,
    job_id: str,
) -> Path:
    attempt_root = workspace_root / "portfolio-runs" / preparation_id
    working = (
        attempt_root
        / "execution"
        / "w"
        / hashlib.sha256(job_id.encode("utf-8")).hexdigest()[:12]
    )
    if working.is_dir():
        return working
    _assert_copy_tree_safe(repository_root)
    temporary = working.with_name(f".{working.name}.{os.getpid()}.tmp")
    temporary.parent.mkdir(parents=True, exist_ok=True)
    if temporary.exists():
        shutil.rmtree(temporary)
    shutil.copytree(
        repository_root,
        temporary,
        ignore=_copy_ignore_for_root(repository_root),
    )
    os.replace(temporary, working)
    return working


def _binding_map(receipt: Mapping[str, Any], field: str, key: str) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    rows = receipt.get(field)
    if not isinstance(rows, list):
        _fail("portfolio_runner_preparation_binding_invalid", field)
    for row in rows:
        if not isinstance(row, Mapping) or not str(row.get(key, "")):
            _fail("portfolio_runner_preparation_binding_invalid", field)
        token = str(row[key])
        if token in result:
            _fail("portfolio_runner_preparation_binding_duplicate", f"{field}:{token}")
        result[token] = row
    return result


def _preparation_current(
    preparation_ref: str,
    *,
    workspace_root: Path,
) -> dict[str, Any]:
    receipt = _load_json_ref(preparation_ref, workspace_root)
    unsigned = dict(receipt)
    stored_hash = unsigned.pop("receipt_hash", None)
    receipt_paths = receipt.get("skill_paths")
    if (
        receipt.get("schema_version") != PREPARATION_SCHEMA
        or receipt.get("status") != "prepared"
        or receipt.get("receipt_id") != receipt.get("preparation_id")
        or stored_hash != canonical_hash(unsigned)
    ):
        _fail("portfolio_runner_preparation_invalid", preparation_ref)
    identity_binding = receipt.get("target_identity_receipt")
    if not isinstance(identity_binding, Mapping):
        _fail("portfolio_runner_preparation_identity_binding_invalid")
    identity = _load_json_ref(str(identity_binding.get("ref", "")), workspace_root)
    unsigned_identity = dict(identity)
    identity_hash = unsigned_identity.pop("receipt_hash", None)
    identity_paths = identity.get("skill_paths")
    if (
        identity.get("receipt_id") != identity_binding.get("receipt_id")
        or identity_hash != identity_binding.get("receipt_hash")
        or identity_hash != canonical_hash(unsigned_identity)
        or identity.get("skill_id") != receipt.get("skill_id")
        or identity.get("target_kind") != receipt.get("target_kind")
        or not isinstance(identity_paths, list)
        or not isinstance(receipt_paths, list)
        or sorted(identity_paths) != sorted(receipt_paths)
        or not _same_guard(identity.get("guard_runtime"), receipt.get("guard_runtime"))
    ):
        _fail("portfolio_runner_preparation_identity_binding_invalid")
    plan = _load_json_ref(str(receipt.get("job_plan_ref", "")), workspace_root)
    unsigned_plan = dict(plan)
    plan_hash = unsigned_plan.pop("job_plan_hash", None)
    plan_paths = plan.get("skill_paths")
    if (
        plan.get("schema_version") != PORTFOLIO_JOB_PLAN_SCHEMA
        or plan_hash != receipt.get("job_plan_hash")
        or plan_hash != canonical_hash(unsigned_plan)
        or plan.get("registry_id") != receipt.get("registry_id")
        or plan.get("scope_manifest_id") != receipt.get("scope_manifest_id")
        or plan.get("scope_manifest_hash") != receipt.get("scope_manifest_hash")
        or plan.get("skill_id") != receipt.get("skill_id")
        or plan.get("target_kind") != receipt.get("target_kind")
        or not isinstance(plan_paths, list)
        or not isinstance(receipt_paths, list)
        or sorted(plan_paths) != sorted(receipt_paths)
    ):
        _fail("portfolio_runner_preparation_plan_invalid")
    spec_bindings = _binding_map(receipt, "job_specs", "job_id")
    raw_plan_jobs = plan.get("jobs")
    if not isinstance(raw_plan_jobs, list):
        _fail("portfolio_runner_preparation_job_set_invalid")
    plan_jobs = {
        str(row.get("job_id", "")): row
        for row in raw_plan_jobs
        if isinstance(row, Mapping)
    }
    if (
        len(plan_jobs) != len(raw_plan_jobs)
        or set(plan_jobs) != set(spec_bindings)
    ):
        _fail("portfolio_runner_preparation_job_set_invalid")
    for job_id, binding in spec_bindings.items():
        spec = _load_json_ref(str(binding.get("job_spec_ref", "")), workspace_root)
        unsigned_spec = dict(spec)
        spec_hash = unsigned_spec.pop("job_spec_hash", None)
        plan_job = plan_jobs[job_id]
        plan_capabilities = plan_job.get("covered_capability_ids")
        spec_capabilities = spec.get("covered_capability_ids")
        if (
            spec.get("schema_version") != PORTFOLIO_JOB_SPEC_SCHEMA
            or spec_hash != binding.get("job_spec_hash")
            or spec_hash != canonical_hash(unsigned_spec)
            or spec.get("job_id") != job_id
            or plan_job.get("job_spec_ref") != binding.get("job_spec_ref")
            or plan_job.get("job_spec_hash") != binding.get("job_spec_hash")
            or plan_job.get("member_skill_id") != spec.get("member_skill_id")
            or plan_job.get("member_contract_hash")
            != spec.get("member_contract_hash")
            or not isinstance(plan_capabilities, list)
            or not isinstance(spec_capabilities, list)
            or sorted(plan_capabilities) != sorted(spec_capabilities)
        ):
            _fail("portfolio_runner_preparation_spec_invalid", job_id)
    member_bindings = _binding_map(
        receipt, "member_contracts", "member_skill_id"
    )
    for member_id, binding in member_bindings.items():
        contract = _load_json_ref(str(binding.get("contract_ref", "")), workspace_root)
        manifest = _load_json_ref(str(binding.get("manifest_ref", "")), workspace_root)
        unsigned_contract = dict(contract)
        contract_hash = unsigned_contract.pop("contract_hash", None)
        unsigned_manifest = dict(manifest)
        manifest_hash = unsigned_manifest.pop("manifest_hash", None)
        if (
            contract.get("skill_id") != member_id
            or contract_hash != binding.get("contract_hash")
            or contract_hash != canonical_hash(unsigned_contract)
            or manifest.get("skill_id") != member_id
            or manifest.get("contract_hash") != contract_hash
            or manifest_hash != binding.get("manifest_hash")
            or manifest_hash != canonical_hash(unsigned_manifest)
        ):
            _fail("portfolio_runner_preparation_member_snapshot_invalid", member_id)
    expected_job_set_hash = canonical_hash(
        {
            "job_plan_ref": receipt.get("job_plan_ref"),
            "job_plan_hash": receipt.get("job_plan_hash"),
            "job_specs": receipt.get("job_specs"),
        }
    )
    if receipt.get("job_set_hash") != expected_job_set_hash:
        _fail("portfolio_runner_preparation_job_set_hash_invalid")
    installed_binding = receipt.get("installed_parity_receipt")
    if installed_binding is not None:
        if not isinstance(installed_binding, Mapping):
            _fail("portfolio_runner_preparation_installed_parity_invalid")
        installed_receipt = _load_json_ref(
            str(installed_binding.get("ref", "")), workspace_root
        )
        installed_findings = validate_installed_parity_receipt(
            installed_receipt,
            portfolio_projection_hash=str(
                receipt.get("guard_runtime", {}).get(
                    "portfolio_projection_hash", ""
                )
            ),
        )
        if (
            installed_findings
            or installed_receipt.get("status") != "current"
            or installed_receipt.get("receipt_id")
            != installed_binding.get("receipt_id")
            or installed_receipt.get("receipt_hash")
            != installed_binding.get("receipt_hash")
        ):
            _fail(
                "portfolio_runner_preparation_installed_parity_invalid",
                ",".join(installed_findings),
            )
    elif receipt.get("target_kind") == "skill_suite":
        _fail("portfolio_runner_preparation_installed_parity_missing")
    return receipt


def _identity_current(
    repository_root: Path,
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    identity_binding = receipt.get("target_identity_receipt", {})
    if not isinstance(identity_binding, Mapping):
        _fail("portfolio_runner_target_identity_binding_missing")
    target_kind = str(receipt.get("target_kind", ""))
    paths = [str(value) for value in receipt.get("skill_paths", [])]
    primary = str(receipt.get("skill_root_token", ""))
    if primary not in paths:
        _fail("portfolio_runner_primary_member_binding_invalid", primary)
    identity, findings = derive_target_identity(
        repository_root,
        skill_root_relative=primary,
        expected_skill_id=str(receipt.get("skill_id", "")),
        guard_runtime=receipt.get("guard_runtime", {}),
        target_kind=target_kind,
        skill_root_relatives=paths,
    )
    if identity is None or findings or identity.get("receipt_hash") != identity_binding.get("receipt_hash"):
        _fail(
            "portfolio_runner_target_identity_not_current",
            ",".join(sorted(row["code"] for row in findings)),
        )
    return identity


def _run_record_refs(run_root: Path, workspace_root: Path) -> dict[str, str]:
    return {
        "run_record_ref": reference_existing_file(run_root / "run.json", workspace_root),
        "contract_snapshot_ref": reference_existing_file(run_root / "contract.json", workspace_root),
        "check_manifest_snapshot_ref": reference_existing_file(run_root / "check-manifest.json", workspace_root),
        "preparation_snapshot_ref": reference_existing_file(
            run_root / "claim" / "portfolio-preparation.json", workspace_root
        ),
        "job_plan_snapshot_ref": reference_existing_file(
            run_root / "claim" / "portfolio-job-plan.json", workspace_root
        ),
        "job_spec_snapshot_ref": reference_existing_file(
            run_root / "claim" / "portfolio-job-spec.json", workspace_root
        ),
        "event_log_ref": reference_existing_file(run_root / "events.jsonl", workspace_root),
    }


def _select_closure_for_receipt(run_root: Path, receipt_id: str) -> Mapping[str, Any]:
    for path in sorted((run_root / "closures").glob("closure-*.json")):
        closure_id = path.stem
        closure = load_closure(run_root, closure_id)
        if receipt_id in set(closure.get("consumed_receipt_ids", [])):
            return closure
    _fail("portfolio_runner_receipt_not_consumed_by_closure", receipt_id)


def _observation_records(
    *,
    run_root: Path,
    workspace_root: Path,
    receipt: Mapping[str, Any],
    job_spec: Mapping[str, Any],
    supervisor_result: Mapping[str, Any],
    before: str,
    after: str,
    before_observed_at: str,
    terminal_observed_at: str,
    after_observed_at: str,
) -> tuple[str, str]:
    job_class_id = str(job_spec["job_class_id"])
    terminal_kind = (
        "expected_rejection"
        if job_class_id == "invalid_input"
        else "out_of_scope_decline"
    )
    terminal: dict[str, Any] = {
        "schema_version": TERMINAL_OBSERVATION_SCHEMA,
        "preparation_id": receipt["preparation_id"],
        "job_id": job_spec["job_id"],
        "job_class_id": job_class_id,
        "run_id": supervisor_result["run_id"],
        "terminal_kind": terminal_kind,
        "authorized_capability_paths": [
            {
                "capability_id": row["capability_id"],
                "function_ids": row["function_ids"],
                "route_ids": row["route_ids"],
                "step_ids": row["step_ids"],
                "check_ids": row["check_ids"],
            }
            for row in job_spec["capability_bindings"]
        ],
        "status": "observed",
        "observed_at": terminal_observed_at,
        "claim_boundary": (
            "The verifier emits this typed terminal only after the exact class-authorized contract path, checks, receipts, and closure completed; request labels or stdout do not create it."
        ),
    }
    _finalize(terminal, "observation_hash")
    terminal_path, terminal_ref = write_hash_bound_json(
        PurePosixPath("portfolio-runs")
        / str(receipt["preparation_id"])
        / "execution"
        / "observations"
        / f"{_safe_token(str(job_spec['job_id']))}-terminal.json",
        terminal,
        workspace_root,
    )
    mutation: dict[str, Any] = {
        "schema_version": MUTATION_OBSERVATION_SCHEMA,
        "preparation_id": receipt["preparation_id"],
        "job_id": job_spec["job_id"],
        "run_id": supervisor_result["run_id"],
        "terminal_observation_ref": terminal_ref,
        "mutation_boundary": "canonical-maintainable-source",
        "before_fingerprint": before,
        "after_fingerprint": after,
        "before_observed_at": before_observed_at,
        "after_observed_at": after_observed_at,
        "ordered": True,
        "equal": before == after,
        "observed_at": after_observed_at,
        "claim_boundary": (
            "This verifier-owned record binds ordered before/after maintainable-source fingerprints around one attempted negative execution."
        ),
    }
    _finalize(mutation, "observation_hash")
    _mutation_path, mutation_ref = write_hash_bound_json(
        PurePosixPath("portfolio-runs")
        / str(receipt["preparation_id"])
        / "execution"
        / "observations"
        / f"{_safe_token(str(job_spec['job_id']))}-mutation.json",
        mutation,
        workspace_root,
    )
    if before != after:
        _fail("portfolio_runner_negative_job_mutated_source", job_spec["job_id"])
    return terminal_ref, mutation_ref


def _validate_job_result(
    result: Mapping[str, Any],
    *,
    receipt: Mapping[str, Any],
    plan_job: Mapping[str, Any],
) -> dict[str, Any]:
    unsigned = dict(result)
    stored_hash = unsigned.pop("result_hash", None)
    representative = result.get("representative_job")
    job_id = str(plan_job.get("job_id", ""))
    if (
        result.get("schema_version")
        != "skillguard.portfolio_job_execution_result.v1"
        or result.get("status") != "executed"
        or result.get("preparation_id") != receipt.get("preparation_id")
        or result.get("job_id") != job_id
        or not isinstance(result.get("run_id"), str)
        or not result.get("run_id")
        or not isinstance(representative, Mapping)
        or stored_hash != canonical_hash(unsigned)
    ):
        _fail("portfolio_runner_job_result_invalid", job_id)
    expected_outcome = JOB_CLASS_EXPECTED_OUTCOMES.get(
        str(plan_job.get("job_class_id", "")), ""
    )
    representative_capabilities = representative.get("covered_capability_ids")
    plan_capabilities = plan_job.get("covered_capability_ids")
    if (
        representative.get("job_id") != job_id
        or representative.get("job_class_ids")
        != [plan_job.get("job_class_id")]
        or representative.get("member_skill_id")
        != plan_job.get("member_skill_id")
        or representative.get("member_contract_hash")
        != plan_job.get("member_contract_hash")
        or representative.get("job_spec_ref") != plan_job.get("job_spec_ref")
        or representative.get("job_spec_hash") != plan_job.get("job_spec_hash")
        or not isinstance(representative_capabilities, list)
        or not isinstance(plan_capabilities, list)
        or sorted(representative_capabilities) != sorted(plan_capabilities)
        or not isinstance(representative.get("evidence_refs"), list)
        or not representative.get("evidence_refs")
        or representative.get("expected_outcome") != expected_outcome
        or representative.get("observed_outcome") != expected_outcome
    ):
        _fail("portfolio_runner_job_result_binding_invalid", job_id)
    return dict(representative)


def _validate_execution_result(
    execution: Mapping[str, Any],
    *,
    execution_ref: str,
    preparation_ref: str,
    receipt: Mapping[str, Any],
    plan: Mapping[str, Any],
    identity: Mapping[str, Any],
    workspace_root: Path,
) -> list[dict[str, Any]]:
    unsigned = dict(execution)
    stored_hash = unsigned.pop("result_hash", None)
    if (
        execution.get("schema_version") != EXECUTION_RESULT_SCHEMA
        or execution.get("status") != "executed"
        or execution.get("preparation_id") != receipt.get("preparation_id")
        or execution.get("preparation_ref") != preparation_ref
        or execution.get("preparation_receipt_hash") != receipt.get("receipt_hash")
        or stored_hash != canonical_hash(unsigned)
    ):
        _fail("portfolio_runner_execution_result_invalid", execution_ref)
    raw_plan_jobs = plan.get("jobs")
    if not isinstance(raw_plan_jobs, list):
        _fail("portfolio_runner_execution_result_job_set_invalid")
    plan_jobs = {
        str(row.get("job_id", "")): row
        for row in raw_plan_jobs
        if isinstance(row, Mapping)
    }
    representative_jobs = execution.get("representative_jobs")
    if not isinstance(representative_jobs, list):
        _fail("portfolio_runner_execution_result_job_set_invalid")
    execution_jobs = {
        str(row.get("job_id", "")): row
        for row in representative_jobs
        if isinstance(row, Mapping)
    }
    if (
        len(plan_jobs) != len(raw_plan_jobs)
        or len(execution_jobs) != len(representative_jobs)
        or set(plan_jobs) != set(execution_jobs)
        or execution.get("coverage_fingerprint")
        != representative_jobs_coverage_fingerprint(representative_jobs)
    ):
        _fail("portfolio_runner_execution_result_job_set_invalid")
    validated_jobs: list[dict[str, Any]] = []
    for job_id, plan_job in sorted(plan_jobs.items()):
        job_result_path = (
            workspace_root
            / "portfolio-runs"
            / str(receipt["preparation_id"])
            / "execution"
            / "jobs"
            / _safe_token(job_id)
            / "result.json"
        )
        if not job_result_path.is_file():
            _fail("portfolio_runner_job_result_missing", job_id)
        job_result_ref = reference_existing_file(job_result_path, workspace_root)
        job_result = _load_json_ref(job_result_ref, workspace_root)
        representative = _validate_job_result(
            job_result, receipt=receipt, plan_job=plan_job
        )
        if representative != dict(execution_jobs[job_id]):
            _fail("portfolio_runner_execution_job_projection_mismatch", job_id)
        validated_jobs.append(representative)
    _receipt, findings = assemble_capability_stage_receipt(
        skill_id=str(receipt.get("skill_id", "")),
        guard_runtime=receipt.get("guard_runtime", {}),
        source_fingerprint=str(identity.get("source_fingerprint", "")),
        contract_hash=str(identity.get("contract_hash", "")),
        representative_jobs=validated_jobs,
        evidence_root=workspace_root,
    )
    if findings:
        _fail(
            "portfolio_runner_existing_execution_evidence_not_current",
            ",".join(
                sorted(
                    f"{row.get('code', '')}:{row.get('detail', '')}"
                    for row in findings
                )
            ),
        )
    return validated_jobs


def _consume_installed_parity_currentness(
    *,
    receipt: Mapping[str, Any],
    identity: Mapping[str, Any],
    repository_root: Path,
    installed_target_root: Path | None,
    workspace_root: Path,
) -> dict[str, Any] | None:
    prepared_binding = receipt.get("installed_parity_receipt")
    if prepared_binding is None:
        if receipt.get("target_kind") == "skill_suite":
            _fail("portfolio_runner_suite_installed_parity_required")
        if installed_target_root is not None:
            _fail("portfolio_runner_installed_parity_not_prepared")
        return None
    if not isinstance(prepared_binding, Mapping):
        _fail("portfolio_runner_installed_parity_binding_invalid")
    if installed_target_root is None:
        _fail("portfolio_runner_installed_parity_freshness_root_required")
    installed_receipt = _load_json_ref(
        str(prepared_binding.get("ref", "")), workspace_root
    )
    portfolio_projection_hash = str(
        receipt.get("guard_runtime", {}).get("portfolio_projection_hash", "")
    )
    fresh_findings = replay_installed_content_parity_currentness(
        installed_receipt,
        canonical_repository_root=repository_root,
        target_identity=identity,
        installed_target_root=installed_target_root,
        portfolio_projection_hash=portfolio_projection_hash,
    )
    if (
        fresh_findings
        or installed_receipt.get("status") != "current"
        or installed_receipt.get("receipt_id") != prepared_binding.get("receipt_id")
        or installed_receipt.get("receipt_hash") != prepared_binding.get("receipt_hash")
    ):
        _fail(
            "portfolio_runner_installed_parity_not_current",
            ",".join(
                [
                    *(
                        str(value)
                        for value in installed_receipt.get("blockers", [])
                    ),
                    *(str(value) for value in fresh_findings),
                ]
            ),
        )
    return {
        "ref": str(prepared_binding["ref"]),
        "receipt_id": str(prepared_binding["receipt_id"]),
        "receipt_hash": str(prepared_binding["receipt_hash"]),
    }


def execute_portfolio_attempt(
    *,
    preparation_ref: str,
    registry: Mapping[str, Any],
    repository_root: Path,
    workspace_root: Path,
) -> dict[str, Any]:
    """Execute or resume every job frozen by one preparation receipt."""

    repository_root = repository_root.resolve()
    workspace_root = workspace_root.resolve()
    receipt = _preparation_current(preparation_ref, workspace_root=workspace_root)
    execution_result_path = (
        workspace_root
        / "portfolio-runs"
        / str(receipt["preparation_id"])
        / "execution"
        / "execution-result.json"
    )
    existing_execution: tuple[str, dict[str, Any]] | None = None
    if execution_result_path.is_file():
        execution_ref = reference_existing_file(execution_result_path, workspace_root)
        existing = _load_json_ref(execution_ref, workspace_root)
        existing_execution = (execution_ref, existing)
    guard = current_guard()
    if not _same_guard(receipt.get("guard_runtime"), guard):
        _fail("portfolio_runner_guard_drift_after_prepare")
    if (
        registry.get("registry_id") != receipt.get("registry_id")
        or registry.get("revision") != receipt.get("registry_revision")
        or registry.get("registry_hash") != receipt.get("registry_hash")
    ):
        _fail("portfolio_runner_registry_drift_after_prepare")
    canonical_identity = _identity_current(repository_root, receipt)
    plan = _load_json_ref(str(receipt["job_plan_ref"]), workspace_root)
    if existing_execution is not None:
        execution_ref, existing = existing_execution
        _validate_execution_result(
            existing,
            execution_ref=execution_ref,
            preparation_ref=preparation_ref,
            receipt=receipt,
            plan=plan,
            identity=canonical_identity,
            workspace_root=workspace_root,
        )
        return {
            "status": "executed",
            "resumed": True,
            "preparation_id": receipt["preparation_id"],
            "execution_ref": execution_ref,
            "execution_result": existing,
            "working_repository_token": "w",
        }
    specs_by_job = _binding_map(receipt, "job_specs", "job_id")
    members_by_id = _binding_map(receipt, "member_contracts", "member_skill_id")
    identity_binding = receipt["target_identity_receipt"]
    representative_jobs: list[dict[str, Any]] = []
    completed_at_values: list[str] = []
    for plan_job in plan.get("jobs", []):
        if not isinstance(plan_job, Mapping):
            _fail("portfolio_runner_plan_job_invalid")
        job_id = str(plan_job.get("job_id", ""))
        spec_binding = specs_by_job.get(job_id)
        if spec_binding is None:
            _fail("portfolio_runner_prepared_spec_missing", job_id)
        job_spec = _load_json_ref(str(spec_binding["job_spec_ref"]), workspace_root)
        job_token = _safe_token(job_id)
        result_relative = (
            PurePosixPath("portfolio-runs")
            / str(receipt["preparation_id"])
            / "execution"
            / "jobs"
            / job_token
            / "result.json"
        )
        result_path = workspace_root / Path(*result_relative.parts)
        if result_path.is_file():
            existing_ref = reference_existing_file(result_path, workspace_root)
            existing = _load_json_ref(existing_ref, workspace_root)
            representative_jobs.append(
                _validate_job_result(
                    existing,
                    receipt=receipt,
                    plan_job=plan_job,
                )
            )
            completed_at_values.append(str(existing.get("completed_at", "")))
            continue
        member_id = str(job_spec["member_skill_id"])
        member_binding = members_by_id.get(member_id)
        if member_binding is None:
            _fail("portfolio_runner_member_snapshot_missing", member_id)
        contract = _load_json_ref(str(member_binding["contract_ref"]), workspace_root)
        manifest = _load_json_ref(str(member_binding["manifest_ref"]), workspace_root)
        working_repository = _working_repository(
            repository_root,
            workspace_root,
            str(receipt["preparation_id"]),
            job_id,
        )
        working_identity = _identity_current(working_repository, receipt)
        if working_identity.get("receipt_hash") != canonical_identity.get(
            "receipt_hash"
        ):
            _fail("portfolio_runner_working_copy_identity_mismatch", job_id)
        member_path = str(member_binding["skill_path"])
        working_member = (
            working_repository
            if member_path == "."
            else working_repository / member_path
        )
        packet = copy.deepcopy(job_spec["execution_packet"])
        request = packet["request"]
        request.update(
            {
                "portfolio_job_id": job_id,
                "portfolio_job_class_id": job_spec["job_class_id"],
                "portfolio_job_plan_ref": receipt["job_plan_ref"],
                "portfolio_job_plan_hash": receipt["job_plan_hash"],
                "portfolio_job_spec_ref": spec_binding["job_spec_ref"],
                "portfolio_job_spec_hash": spec_binding["job_spec_hash"],
                "portfolio_preparation_id": receipt["preparation_id"],
                "portfolio_preparation_ref": preparation_ref,
                "portfolio_preparation_hash": receipt["receipt_hash"],
                "portfolio_member_skill_id": member_id,
                "portfolio_member_contract_hash": job_spec["member_contract_hash"],
                "portfolio_covered_capability_ids": job_spec["covered_capability_ids"],
                "portfolio_mutation_fingerprint_before": canonical_identity[
                    "source_fingerprint"
                ],
            }
        )
        before_identity = _identity_current(working_repository, receipt)
        before = str(before_identity["source_fingerprint"])
        before_observed_at = utc_now()
        run_state_root = (
            workspace_root
            / "p"
            / str(receipt["preparation_id"]).removeprefix("portfolio-prep-")[:12]
            / "r"
            / hashlib.sha256(job_id.encode("utf-8")).hexdigest()[:12]
        )
        supervisor_result = supervise_contract_run(
            working_member,
            working_member,
            working_repository,
            packet,
            compiled_contract=contract,
            check_manifest=manifest,
            claim_snapshots={
                "portfolio-preparation": receipt,
                "portfolio-job-plan": plan,
                "portfolio-job-spec": job_spec,
            },
            run_state_root=run_state_root,
            owner_evidence_root=resolve_owner_evidence_root(
                repository_root,
                workspace_root / "owner-evidence",
            ),
            guard_runtime_identity=guard,
        )
        run_root = run_state_root / ".skillguard" / "runs" / str(
            supervisor_result["run_id"]
        )
        terminal_observed_at = utc_now()
        after_identity = _identity_current(working_repository, receipt)
        after = str(after_identity["source_fingerprint"])
        after_observed_at = utc_now()
        if after_identity.get("receipt_hash") != before_identity.get("receipt_hash"):
            _fail("portfolio_runner_job_mutated_maintainable_source", job_id)
        terminal_ref = ""
        mutation_ref = ""
        if job_spec["job_class_id"] in {"invalid_input", "out_of_scope"}:
            terminal_ref, mutation_ref = _observation_records(
                run_root=run_root,
                workspace_root=workspace_root,
                receipt=receipt,
                job_spec=job_spec,
                supervisor_result=supervisor_result,
                before=before,
                after=after,
                before_observed_at=before_observed_at,
                terminal_observed_at=terminal_observed_at,
                after_observed_at=after_observed_at,
            )
        common_refs = _run_record_refs(run_root, workspace_root)
        runtime_receipts = load_receipts(run_root)
        hard_receipts = [
            row
            for row in runtime_receipts
            if row.get("status") == "passed"
            and row.get("evidence_class") == "hard"
            and isinstance(row.get("evidence"), Mapping)
            and row.get("evidence", {}).get("proof_kind")
            == "owner_receipt_projection"
            and row.get("evidence", {}).get("check_id")
            in set(job_spec["required_check_ids"])
        ]
        if not hard_receipts:
            _fail("portfolio_runner_required_hard_receipts_missing", job_id)
        # The runtime replay scans the complete run for every required check.
        # One primary evidence record anchors the job; the verifier-derived full
        # receipt expands the exact current run command set during assembly.
        primary_receipt = hard_receipts[0]
        check_record_id = str(primary_receipt["evidence"]["check_record_id"])
        closure = _select_closure_for_receipt(
            run_root, str(primary_receipt["receipt_id"])
        )
        payload: dict[str, Any] = {
            **common_refs,
            "target_root_token": working_member.relative_to(workspace_root).as_posix(),
            "check_record_ref": reference_existing_file(
                run_root / "checks" / f"{check_record_id}.json", workspace_root
            ),
            "runtime_receipt_ref": reference_existing_file(
                run_root
                / "receipts"
                / f"{primary_receipt['receipt_id']}.json",
                workspace_root,
            ),
            "closure_receipt_ref": reference_existing_file(
                run_root
                / "closures"
                / f"{closure['closure_receipt_id']}.json",
                workspace_root,
            ),
            "owner_receipt_bindings": [
                {
                    "check_id": str(row["evidence"]["check_id"]),
                    "execution_owner_id": str(
                        row["evidence"]["execution_owner_id"]
                    ),
                    "owner_receipt_id": str(row["evidence"]["owner_receipt_id"]),
                    "owner_receipt_hash": str(
                        row["evidence"]["owner_receipt_hash"]
                    ),
                    "owner_receipt_ref": dict(
                        row["evidence"]["owner_receipt_ref"]
                    ),
                    "execution_disposition": str(
                        row["evidence"]["execution_disposition"]
                    ),
                }
                for row in sorted(
                    hard_receipts,
                    key=lambda value: str(value["evidence"]["check_id"]),
                )
            ],
        }
        if job_spec["job_class_id"] == "recovery_or_resume":
            payload["resume_state_hash"] = canonical_hash(resume_run(run_root).to_dict())
        if job_spec["job_class_id"] in {"invalid_input", "out_of_scope"}:
            payload.update(
                {
                    "mutation_fingerprint_before": before,
                    "mutation_fingerprint_after": after,
                    "outcome_observation": (
                        "expected_rejection"
                        if job_spec["job_class_id"] == "invalid_input"
                        else "out_of_scope_decline"
                    ),
                    "terminal_observation_ref": terminal_ref,
                    "mutation_observation_ref": mutation_ref,
                }
            )
        if job_spec["job_class_id"] == "artifact_check":
            artifact_ids = [
                str(value)
                for row in job_spec["capability_bindings"]
                for value in row["artifact_ids"]
            ]
            artifact_files = sorted((run_root / "artifacts").glob("artifact-*.json"))
            selected_artifact = None
            for path in artifact_files:
                candidate = json.loads(path.read_text(encoding="utf-8"))
                if candidate.get("artifact_id") in set(artifact_ids):
                    selected_artifact = path
                    break
            if selected_artifact is None:
                _fail("portfolio_runner_required_artifact_receipt_missing", job_id)
            payload["artifact_record_ref"] = reference_existing_file(
                selected_artifact, workspace_root
            )
        evidence: dict[str, Any] = {
            "schema_version": PORTFOLIO_JOB_EVIDENCE_SCHEMA,
            "record_id": f"portfolio-evidence-{_safe_token(job_id)}",
            "registry_id": receipt["registry_id"],
            "scope_manifest_id": receipt["scope_manifest_id"],
            "scope_manifest_hash": receipt["scope_manifest_hash"],
            "skill_id": receipt["skill_id"],
            "target_kind": receipt["target_kind"],
            "skill_paths": receipt["skill_paths"],
            "member_skill_id": member_id,
            "member_contract_hash": job_spec["member_contract_hash"],
            "job_id": job_id,
            "job_class_id": job_spec["job_class_id"],
            "preparation_id": receipt["preparation_id"],
            "preparation_receipt_ref": preparation_ref,
            "preparation_receipt_hash": receipt["receipt_hash"],
            "job_plan_ref": receipt["job_plan_ref"],
            "job_plan_hash": receipt["job_plan_hash"],
            "job_spec_ref": spec_binding["job_spec_ref"],
            "job_spec_hash": spec_binding["job_spec_hash"],
            "covered_capability_ids": job_spec["covered_capability_ids"],
            "expected_outcome": job_spec["expected_outcome"],
            "observed_outcome": job_spec["expected_outcome"],
            "evidence_class": "hard",
            "status": "current",
            "target_identity_receipt": identity_binding,
            "guard_runtime": guard,
            "source_fingerprint": canonical_identity["source_fingerprint"],
            "contract_hash": canonical_identity["contract_hash"],
            "payload": payload,
            "payload_hash": canonical_hash(payload),
            "created_at": utc_now(),
        }
        _finalize(evidence, "record_hash")
        _evidence_path, evidence_ref = write_hash_bound_json(
            result_relative.parent / "evidence.json",
            evidence,
            workspace_root,
        )
        representative_job = {
            "job_id": job_id,
            "job_class_ids": [job_spec["job_class_id"]],
            "member_skill_id": member_id,
            "member_contract_hash": job_spec["member_contract_hash"],
            "job_spec_ref": spec_binding["job_spec_ref"],
            "job_spec_hash": spec_binding["job_spec_hash"],
            "covered_capability_ids": job_spec["covered_capability_ids"],
            "evidence_refs": [evidence_ref],
            "expected_outcome": job_spec["expected_outcome"],
            "observed_outcome": job_spec["expected_outcome"],
        }
        result: dict[str, Any] = {
            "schema_version": "skillguard.portfolio_job_execution_result.v1",
            "preparation_id": receipt["preparation_id"],
            "job_id": job_id,
            "status": "executed",
            "run_id": supervisor_result["run_id"],
            "representative_job": representative_job,
            "completed_at": utc_now(),
            "claim_boundary": "This result binds one prepared job to its ordinary current run and verifier-owned evidence records.",
        }
        _finalize(result, "result_hash")
        write_hash_bound_json(result_relative, result, workspace_root)
        representative_jobs.append(representative_job)
        completed_at_values.append(str(result["completed_at"]))

    representative_jobs.sort(key=lambda row: str(row["job_id"]))
    _validated_receipt, validation_findings = assemble_capability_stage_receipt(
        skill_id=str(receipt["skill_id"]),
        guard_runtime=guard,
        source_fingerprint=str(canonical_identity["source_fingerprint"]),
        contract_hash=str(canonical_identity["contract_hash"]),
        representative_jobs=representative_jobs,
        evidence_root=workspace_root,
    )
    if validation_findings:
        _fail(
            "portfolio_runner_execution_evidence_not_current",
            ",".join(
                sorted(
                    f"{row.get('code', '')}:{row.get('detail', '')}"
                    for row in validation_findings
                )
            ),
        )
    execution: dict[str, Any] = {
        "schema_version": EXECUTION_RESULT_SCHEMA,
        "preparation_id": receipt["preparation_id"],
        "preparation_ref": preparation_ref,
        "preparation_receipt_hash": receipt["receipt_hash"],
        "status": "executed",
        "representative_jobs": representative_jobs,
        "coverage_fingerprint": representative_jobs_coverage_fingerprint(
            representative_jobs
        ),
        "completed_at": max(completed_at_values, default=utc_now()) or utc_now(),
        "claim_boundary": "All frozen jobs have an ordinary current run and hash-bound evidence; graduation remains verifier-gated by assembly.",
    }
    _finalize(execution, "result_hash")
    execution_path, execution_ref = write_hash_bound_json(
        PurePosixPath("portfolio-runs")
        / str(receipt["preparation_id"])
        / "execution"
        / "execution-result.json",
        execution,
        workspace_root,
    )
    return {
        "status": "executed",
        "preparation_id": receipt["preparation_id"],
        "execution_ref": execution_ref,
        "execution_result": execution,
        "working_repository_token": "w",
    }


def capture_portfolio_production_revalidation_binding(
    *,
    member_skill_id: str,
    member_skill_path: str,
    repository_root: Path,
    run_root: Path,
    target_root: Path,
    workspace_root: Path,
    closure_receipt_id: str,
    owner_evidence_root: Path | None = None,
    verified_installation_context: VerifiedInstallationContext | None = None,
) -> dict[str, Any]:
    """Write one exact member production binding for later assemble injection."""

    repository_root = repository_root.resolve()
    workspace_root = workspace_root.resolve()
    guard = current_guard()
    identity, identity_findings = derive_target_identity(
        repository_root,
        skill_root_relative=member_skill_path,
        expected_skill_id=member_skill_id,
        guard_runtime=guard,
        target_kind="single_skill",
        skill_root_relatives=[member_skill_path],
    )
    if identity is None or identity_findings:
        _fail(
            "portfolio_runner_production_member_identity_invalid",
            ",".join(
                sorted(
                    str(row.get("code", ""))
                    for row in identity_findings
                    if isinstance(row, Mapping)
                )
            ),
        )
    members = [
        row
        for row in identity.get("member_identities", [])
        if isinstance(row, Mapping)
        and row.get("member_skill_id") == member_skill_id
    ]
    if len(members) != 1:
        _fail(
            "portfolio_runner_production_member_identity_invalid",
            f"{member_skill_id}:{len(members)}",
        )
    member = members[0]
    member_repository_root = (
        repository_root / Path(member_skill_path)
    ).resolve()
    if verified_installation_context is None:
        depth_receipts = load_target_execution_receipts(run_root)
        if not depth_receipts:
            _fail("portfolio_runner_production_depth_receipt_missing")
        scheduled_identity = depth_receipts[-1].get(
            "scheduled_production_identity"
        )
        if not isinstance(scheduled_identity, Mapping):
            _fail("portfolio_runner_production_installation_identity_missing")
        verified_installation_context = (
            load_scheduled_production_installation_context(
                scheduled_identity
            )
        )
    else:
        verified_installation_context = validate_verified_installation_context(
            verified_installation_context
        )
    try:
        binding = build_portfolio_production_revalidation_binding(
            member_skill_id=member_skill_id,
            member_skill_path=member_skill_path,
            source_fingerprint=str(member.get("source_fingerprint", "")),
            member_contract_hash=str(member.get("contract_hash", "")),
            member_manifest_hash=str(member.get("manifest_hash", "")),
            member_repository_root=member_repository_root,
            run_root=run_root,
            target_root=target_root,
            workspace_root=workspace_root,
            closure_receipt_id=closure_receipt_id,
            owner_evidence_root=owner_evidence_root,
            verified_installation_context=verified_installation_context,
        )
    except PortfolioRecordError as exc:
        _fail(exc.code, exc.detail)
    relative = (
        PurePosixPath("portfolio-production-revalidation")
        / _safe_token(member_skill_id)
        / f"{str(binding['binding_hash']).lower()}.json"
    )
    _path, binding_ref = write_hash_bound_json(
        relative, binding, workspace_root
    )
    return {
        "status": "captured",
        "member_skill_id": member_skill_id,
        "binding_ref": binding_ref,
        "binding_hash": binding["binding_hash"],
        "binding": binding,
        "claim_boundary": (
            "Capture writes one immutable production-revalidation binding only; "
            "portfolio assembly must independently replay it with every required member."
        ),
    }


def assemble_portfolio_attempt(
    *,
    preparation_ref: str,
    execution_ref: str,
    registry: Mapping[str, Any],
    repository_root: Path,
    workspace_root: Path,
    installed_target_root: Path | None = None,
    production_revalidation_refs: Sequence[str] = (),
    portfolio_target_repository_roots: Mapping[str, Path] | None = None,
) -> dict[str, Any]:
    """Replay one complete execution and build verifier-authored graduation input."""

    repository_root = repository_root.resolve()
    workspace_root = workspace_root.resolve()
    installed_target_root = (
        installed_target_root.resolve()
        if installed_target_root is not None
        else None
    )
    receipt = _preparation_current(preparation_ref, workspace_root=workspace_root)
    portfolio_target_repository_roots = {
        str(skill_id): Path(root).resolve()
        for skill_id, root in dict(
            portfolio_target_repository_roots or {}
        ).items()
    }
    portfolio_target_repository_roots.setdefault(
        str(receipt["skill_id"]), repository_root
    )
    assembly_result_path = (
        workspace_root
        / "portfolio-runs"
        / str(receipt["preparation_id"])
        / "assembly"
        / "assembly-result.json"
    )
    existing_assembly: tuple[str, dict[str, Any]] | None = None
    if assembly_result_path.is_file():
        assembly_ref = reference_existing_file(assembly_result_path, workspace_root)
        existing = _load_json_ref(assembly_ref, workspace_root)
        existing_assembly = (assembly_ref, existing)
    execution = _load_json_ref(execution_ref, workspace_root)
    guard = current_guard()
    if not _same_guard(guard, receipt.get("guard_runtime")):
        _fail("portfolio_runner_guard_drift_before_assembly")
    if (
        registry.get("registry_id") != receipt.get("registry_id")
        or registry.get("revision") != receipt.get("registry_revision")
        or registry.get("registry_hash") != receipt.get("registry_hash")
    ):
        _fail("portfolio_runner_registry_drift_before_assembly")
    identity = _identity_current(repository_root, receipt)
    (
        production_bindings,
        production_findings,
        verified_installation_context,
    ) = (
        _load_portfolio_production_revalidation_bindings(
            list(production_revalidation_refs),
            target_identity=identity,
            target_repository_root=repository_root,
            evidence_root=workspace_root,
        )
    )
    if production_findings:
        _fail(
            "portfolio_runner_production_revalidation_blocked",
            ",".join(
                sorted(
                    f"{row.get('code', '')}:{row.get('skill_id', '')}"
                    for row in production_findings
                )
            ),
        )
    production_fingerprint = portfolio_production_revalidation_fingerprint(
        production_bindings
    )
    if not production_fingerprint:
        _fail("portfolio_runner_production_revalidation_missing")
    plan = _load_json_ref(str(receipt["job_plan_ref"]), workspace_root)
    jobs = _validate_execution_result(
        execution,
        execution_ref=execution_ref,
        preparation_ref=preparation_ref,
        receipt=receipt,
        plan=plan,
        identity=identity,
        workspace_root=workspace_root,
    )
    final_installed_binding = _consume_installed_parity_currentness(
        receipt=receipt,
        identity=identity,
        repository_root=repository_root,
        installed_target_root=installed_target_root,
        workspace_root=workspace_root,
    )
    if existing_assembly is not None:
        assembly_ref, existing = existing_assembly
        unsigned_existing = dict(existing)
        stored_existing_hash = unsigned_existing.pop("result_hash", None)
        if (
            existing.get("schema_version") != ASSEMBLY_RESULT_SCHEMA
            or existing.get("status") != "assembled"
            or existing.get("preparation_id") != receipt.get("preparation_id")
            or existing.get("preparation_ref") != preparation_ref
            or existing.get("execution_ref") != execution_ref
            or existing.get("installed_parity_receipt")
            != final_installed_binding
            or existing.get("production_revalidation_binding_refs")
            != sorted(str(item) for item in production_revalidation_refs)
            or existing.get("production_revalidation_fingerprint")
            != production_fingerprint
            or stored_existing_hash != canonical_hash(unsigned_existing)
        ):
            _fail("portfolio_runner_assembly_result_collision")
        existing_evidence = _load_json_ref(
            str(existing.get("graduation_evidence_ref", "")), workspace_root
        )
        if (
            existing_evidence.get("evidence_hash")
            != existing.get("graduation_evidence_hash")
            or existing_evidence.get("installed_parity_receipt")
            != final_installed_binding
            or existing_evidence.get("production_revalidation_binding_refs")
            != sorted(str(item) for item in production_revalidation_refs)
            or existing_evidence.get("production_revalidation_fingerprint")
            != production_fingerprint
        ):
            _fail("portfolio_runner_assembly_evidence_not_current")
        replay_report, _replay_updated, replay_receipt = graduate_portfolio_target(
            registry,
            existing_evidence,
            actual_guard=guard,
            evidence_root=workspace_root,
            target_repository_root=repository_root,
            installed_target_root=installed_target_root,
            verified_installation_context=verified_installation_context,
            portfolio_target_repository_roots=(
                portfolio_target_repository_roots
            ),
        )
        if (
            replay_receipt is None
            or replay_receipt.get("receipt_id")
            != existing.get("graduation_receipt_id")
            or replay_receipt.get("receipt_hash")
            != existing.get("graduation_receipt_hash")
        ):
            blockers = (
                replay_report.get("blockers", [])
                if isinstance(replay_report, Mapping)
                else []
            )
            _fail(
                "portfolio_runner_assembly_evidence_not_current",
                ",".join(
                    str(row.get("code", ""))
                    for row in blockers
                    if isinstance(row, Mapping)
                ),
            )
        return {
            "status": "assembled",
            "resumed": True,
            "preparation_id": receipt["preparation_id"],
            "assembly_ref": assembly_ref,
            "assembly_result": existing,
        }
    full_receipt, receipt_findings = assemble_full_run_receipt(
        skill_id=str(receipt["skill_id"]),
        guard_runtime=guard,
        source_fingerprint=str(identity["source_fingerprint"]),
        contract_hash=str(identity["contract_hash"]),
        representative_jobs=jobs,
        evidence_root=workspace_root,
        production_revalidation_bindings=production_bindings,
    )
    if full_receipt is None or receipt_findings:
        _fail(
            "portfolio_runner_full_receipt_assembly_failed",
            ",".join(
                sorted(
                    f"{row['code']}:{row.get('detail', '')}"
                    for row in receipt_findings
                )
            ),
        )
    spec_rows = sorted(
        (
            {
                "ref": str(row["job_spec_ref"]),
                "hash": str(row["job_spec_hash"]),
            }
            for row in receipt.get("job_specs", [])
        ),
        key=lambda row: (row["ref"], row["hash"]),
    )
    evidence: dict[str, Any] = {
        "schema_version": GRADUATION_EVIDENCE_SCHEMA,
        "transaction_id": f"graduate-{receipt['preparation_id']}",
        "expected_registry_revision": registry["revision"],
        "base_registry_hash": registry["registry_hash"],
        "registry_id": registry["registry_id"],
        "scope_manifest_id": registry["scope_manifest_id"],
        "scope_manifest_hash": registry["scope_manifest_hash"],
        "skill_id": receipt["skill_id"],
        "target_kind": receipt["target_kind"],
        "skill_paths": receipt["skill_paths"],
        "version": identity.get("version", ""),
        "source_fingerprint": identity["source_fingerprint"],
        "contract_hash": identity["contract_hash"],
        "guard_runtime": guard,
        "preparation_receipt": {
            "ref": preparation_ref,
            "receipt_id": receipt["receipt_id"],
            "receipt_hash": receipt["receipt_hash"],
        },
        "installed_parity_receipt": final_installed_binding,
        "target_identity_receipt": receipt["target_identity_receipt"],
        "job_plan_refs": [receipt["job_plan_ref"]],
        "job_plan_hash": receipt["job_plan_hash"],
        "job_spec_refs": [row["ref"] for row in spec_rows],
        "job_spec_hash": canonical_hash({"job_specs": spec_rows}),
        "representative_jobs": jobs,
        "production_revalidation_binding_refs": sorted(
            str(item) for item in production_revalidation_refs
        ),
        "production_revalidation_fingerprint": production_fingerprint,
        "full_run_receipt": full_receipt,
        "failure_classification": None,
        "unresolved_failure_ids": [],
        "submitted_at": full_receipt["completed_at"],
        "claim_boundary": (
            "Production runner assembly replays the exact prepared runs and builds this input; only graduate_portfolio_target can authorize registry mutation."
        ),
    }
    _finalize(evidence, "evidence_hash")
    report, _updated, graduation_receipt = graduate_portfolio_target(
        registry,
        evidence,
        actual_guard=guard,
        evidence_root=workspace_root,
        target_repository_root=repository_root,
        installed_target_root=installed_target_root,
        verified_installation_context=verified_installation_context,
        portfolio_target_repository_roots=portfolio_target_repository_roots,
    )
    if graduation_receipt is None:
        blockers = report.get("blockers", []) if isinstance(report, Mapping) else []
        _fail(
            "portfolio_runner_graduation_dry_run_blocked",
            ",".join(
                sorted(
                    str(row.get("code", ""))
                    for row in blockers
                    if isinstance(row, Mapping)
                )
            ),
        )
    evidence_path, evidence_ref = write_hash_bound_json(
        PurePosixPath("portfolio-runs")
        / str(receipt["preparation_id"])
        / "assembly"
        / "graduation-evidence.json",
        evidence,
        workspace_root,
    )
    assembly: dict[str, Any] = {
        "schema_version": ASSEMBLY_RESULT_SCHEMA,
        "preparation_id": receipt["preparation_id"],
        "preparation_ref": preparation_ref,
        "execution_ref": execution_ref,
        "status": "assembled",
        "graduation_evidence_ref": evidence_ref,
        "graduation_evidence_hash": evidence["evidence_hash"],
        "installed_parity_receipt": final_installed_binding,
        "production_revalidation_binding_refs": sorted(
            str(item) for item in production_revalidation_refs
        ),
        "production_revalidation_fingerprint": production_fingerprint,
        "full_run_receipt_id": full_receipt["receipt_id"],
        "full_run_receipt_hash": full_receipt["receipt_hash"],
        "graduation_receipt_id": graduation_receipt["receipt_id"],
        "graduation_receipt_hash": graduation_receipt["receipt_hash"],
        "completed_at": full_receipt["completed_at"],
        "claim_boundary": "Assembly proves a current graduation dry-run only; it does not mutate the registry or publish a release.",
    }
    _finalize(assembly, "result_hash")
    _assembly_path, assembly_ref = write_hash_bound_json(
        PurePosixPath("portfolio-runs")
        / str(receipt["preparation_id"])
        / "assembly"
        / "assembly-result.json",
        assembly,
        workspace_root,
    )
    return {
        "status": "assembled",
        "preparation_id": receipt["preparation_id"],
        "assembly_ref": assembly_ref,
        "assembly_result": assembly,
        "graduation_evidence": evidence,
        "graduation_report": report,
    }


__all__ = [
    "ASSEMBLY_RESULT_SCHEMA",
    "EXECUTION_RESULT_SCHEMA",
    "MUTATION_OBSERVATION_SCHEMA",
    "PREPARATION_SCHEMA",
    "PortfolioRunnerError",
    "TERMINAL_OBSERVATION_SCHEMA",
    "assemble_portfolio_attempt",
    "capture_portfolio_production_revalidation_binding",
    "execute_portfolio_attempt",
    "prepare_portfolio_attempt",
]
