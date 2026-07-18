"""Generic claimed-run supervisor for any compiled current SkillGuard contract."""

from __future__ import annotations

import json
import os
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .artifact_validators import WITNESS_KINDS, validate_artifact
from .author_context import (
    AuthorContextError,
    validate_author_maintenance_context,
)
from .check_runner import (
    get_or_execute_check,
    hard_evidence_from_check,
    load_run_owner_receipt_index,
    resolve_owner_evidence_root,
)
from .closure import close_run, verify_closure
from .contract_compiler import canonical_hash, canonical_json_bytes, compile_skill_contract
from .evidence_policy import required_evidence_class
from .execution_depth import (
    DepthError,
    issue_target_execution_receipt,
)
from .execution_records import filesystem_path
from .installation_receipt import (
    VerifiedInstallationContext,
    load_scheduled_production_installation_context,
    validate_verified_installation_context,
    verify_scheduled_production_installation_identity,
)
from .receipts import build_action_witness, fingerprint_value, issue_receipt, load_receipts
from .route_runtime import select_routes
from .runtime_authority import AUTHORITY_CURRENT, resolve_runtime_authority
from .runtime_fingerprint import guard_execution_runtime_fingerprint
from .run_store import claim_run, utc_now
from .step_runtime import (
    approve_skip,
    begin_step,
    next_ready_steps,
    record_failure,
    record_step,
    record_verification,
    replay_run,
    request_skip,
)
from .target_inputs import (
    TargetInputError,
    fingerprint_target_input_roles,
    fingerprint_target_inputs,
)


@dataclass(frozen=True)
class SupervisorError(RuntimeError):
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


_TOP_LEVEL_PACKET_FIELDS = frozenset(
    {
        "supervision_mode",
        "request",
        "profiles",
        "steps",
        "execution_depth",
        "native_terminal",
    }
)
_REQUEST_PACKET_FIELDS = frozenset(
    {
        "route_ids",
        "function_ids",
        "compose",
        "request",
        "intent",
        "claim_scope",
        "write_targets",
        "target_input_paths",
        "target_input_roles",
        "portfolio_job_id",
        "portfolio_job_class_id",
        "portfolio_job_plan_ref",
        "portfolio_job_plan_hash",
        "portfolio_job_spec_ref",
        "portfolio_job_spec_hash",
        "portfolio_preparation_id",
        "portfolio_preparation_ref",
        "portfolio_preparation_hash",
        "portfolio_member_skill_id",
        "portfolio_member_contract_hash",
        "portfolio_covered_capability_ids",
        "portfolio_mutation_fingerprint_before",
        "portfolio_input",
        "portfolio_scope",
        "portfolio_artifact_path",
    }
)
_STEP_PACKET_FIELDS = frozenset({"skip", "witness", "judgment", "artifact_witnesses"})
_SKIP_PACKET_FIELDS = frozenset(
    {"reason", "condition_step_id", "verifier_step_id", "condition_receipt_id", "verifier_receipt_id"}
)
_JUDGMENT_PACKET_FIELDS = frozenset(
    {
        "rubric_id",
        "rubric_version",
        "evaluator_id",
        "input",
        "conclusion",
        "limitations",
        "self_review",
        "confidence_boundary",
    }
)
_WITNESS_PACKET_FIELDS = frozenset(
    {
        "schema_version",
        "witness_id",
        "witness_kind",
        "target_id",
        "executor_id",
        "input",
        "output",
        "input_fingerprint",
        "output_fingerprint",
        "limitations",
        "claim_boundary",
        "surface_id",
        "state_id",
        "interaction_receipt_id",
        "interaction_receipt_step_id",
    }
)
_EXECUTION_DEPTH_PACKET_FIELDS = frozenset(
    {
        "observations",
        "run_started",
        "boundary_only",
        "evidence_domain",
        "scheduled_production_identity",
    }
)
_NATIVE_TERMINAL_PACKET_FIELDS = frozenset(
    {"receipt_ref", "expected_route_id", "expected_branch_id"}
)
_DEPTH_OBSERVATION_FIELDS = frozenset(
    {
        "obligation_id",
        "step_id",
        "check_id",
        "contribution_id",
        "contribution",
        "contribution_range_id",
    }
)


def _reject_unknown_fields(value: Mapping[str, Any], allowed: frozenset[str], path: str) -> None:
    unknown = sorted(str(key) for key in value if not isinstance(key, str) or key not in allowed)
    if unknown:
        raise SupervisorError(
            "unconsumed_packet_field",
            f"{path}.{unknown[0]} is not declared or consumed",
        )


def _packet_object(value: object, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SupervisorError("packet_object_required", path)
    return value


def _validate_witness_packet(value: object, path: str) -> Mapping[str, Any]:
    witness = _packet_object(value, path)
    _reject_unknown_fields(witness, _WITNESS_PACKET_FIELDS, path)
    return witness


def validate_supervisor_packet(
    packet: Mapping[str, Any],
    *,
    contract: Mapping[str, Any] | None = None,
    route_ids: Sequence[str] = (),
) -> None:
    """Reject every packet field that is misspelled, unreachable, or unused."""

    packet = _packet_object(packet, "$")
    _reject_unknown_fields(packet, _TOP_LEVEL_PACKET_FIELDS, "$")
    request = _packet_object(packet.get("request", {}), "$.request")
    _reject_unknown_fields(request, _REQUEST_PACKET_FIELDS, "$.request")
    supervision_mode = str(packet.get("supervision_mode", "close"))
    if supervision_mode not in {"stage_depth", "close"}:
        raise SupervisorError(
            "supervision_mode_invalid", "$.supervision_mode"
        )
    profiles = packet.get("profiles", ["enforced"])
    if isinstance(profiles, (str, bytes)) or not isinstance(profiles, Sequence):
        raise SupervisorError("packet_array_required", "$.profiles")
    steps_packet = _packet_object(packet.get("steps", {}), "$.steps")
    execution_depth = _packet_object(packet.get("execution_depth", {}), "$.execution_depth")
    _reject_unknown_fields(execution_depth, _EXECUTION_DEPTH_PACKET_FIELDS, "$.execution_depth")
    observations = execution_depth.get("observations", [])
    if isinstance(observations, (str, bytes)) or not isinstance(observations, Sequence):
        raise SupervisorError("packet_array_required", "$.execution_depth.observations")
    for index, observation in enumerate(observations):
        row = _packet_object(observation, f"$.execution_depth.observations[{index}]")
        _reject_unknown_fields(row, _DEPTH_OBSERVATION_FIELDS, f"$.execution_depth.observations[{index}]")
    native_terminal = _packet_object(
        packet.get("native_terminal", {}), "$.native_terminal"
    )
    _reject_unknown_fields(
        native_terminal, _NATIVE_TERMINAL_PACKET_FIELDS, "$.native_terminal"
    )
    if native_terminal:
        receipt_ref = _packet_object(
            native_terminal.get("receipt_ref", {}),
            "$.native_terminal.receipt_ref",
        )
        _reject_unknown_fields(
            receipt_ref,
            frozenset({"path_token", "relative_path"}),
            "$.native_terminal.receipt_ref",
        )
        if receipt_ref.get("path_token") != "run_root" or not str(
            receipt_ref.get("relative_path", "")
        ):
            raise SupervisorError(
                "native_terminal_receipt_ref_invalid",
                "$.native_terminal.receipt_ref",
            )
    if supervision_mode == "stage_depth":
        if list(profiles):
            raise SupervisorError(
                "stage_depth_profiles_forbidden",
                "stage_depth requires profiles=[] and never closes a run",
            )
        if native_terminal:
            raise SupervisorError(
                "stage_depth_native_terminal_forbidden",
                "a terminal receipt can only be consumed by the close stage",
            )
    elif list(profiles) != ["enforced"]:
        raise SupervisorError(
            "enforced_closure_profile_required",
            "close always uses the sole enforced closure profile",
        )
    for step_id_value, raw_step_packet in steps_packet.items():
        step_id = str(step_id_value)
        step_path = f"$.steps.{step_id}"
        step_packet = _packet_object(raw_step_packet, step_path)
        _reject_unknown_fields(step_packet, _STEP_PACKET_FIELDS, step_path)
        if not step_packet:
            raise SupervisorError("unconsumed_step_packet", step_path)
        skip = step_packet.get("skip", {})
        if skip:
            skip = _packet_object(skip, f"{step_path}.skip")
            _reject_unknown_fields(skip, _SKIP_PACKET_FIELDS, f"{step_path}.skip")
            if any(step_packet.get(key) for key in ("witness", "judgment", "artifact_witnesses")):
                raise SupervisorError("skip_packet_conflict", step_path)
        witness = step_packet.get("witness", {})
        if witness:
            _validate_witness_packet(witness, f"{step_path}.witness")
        judgment = step_packet.get("judgment", {})
        if judgment:
            judgment = _packet_object(judgment, f"{step_path}.judgment")
            _reject_unknown_fields(judgment, _JUDGMENT_PACKET_FIELDS, f"{step_path}.judgment")
        artifact_witnesses = step_packet.get("artifact_witnesses", {})
        if artifact_witnesses:
            artifact_witnesses = _packet_object(
                artifact_witnesses,
                f"{step_path}.artifact_witnesses",
            )
            for artifact_id, witness_packet in artifact_witnesses.items():
                _validate_witness_packet(
                    witness_packet,
                    f"{step_path}.artifact_witnesses.{artifact_id}",
                )

    if contract is None:
        return
    if execution_depth and not isinstance(contract.get("depth_profile"), Mapping):
        raise SupervisorError("unconsumed_packet_field", "$.execution_depth")
    selected_profiles = {str(item) for item in profiles}
    has_branch_contract = any(
        isinstance(row, Mapping)
        and str(row.get("profile_id", "")) in selected_profiles
        and any(
            isinstance(requirement, Mapping)
            and str(requirement.get("native_route_id", "")) in set(route_ids)
            for requirement in row.get("route_branch_requirements", [])
        )
        for row in contract.get("closure_profiles", [])
    )
    if native_terminal and not has_branch_contract:
        raise SupervisorError("unconsumed_packet_field", "$.native_terminal")
    if supervision_mode == "close" and has_branch_contract and not native_terminal:
        raise SupervisorError(
            "native_terminal_receipt_required",
            "selected route/profile has a branch closure contract",
        )
    selected_route_ids = set(route_ids)
    step_index = {
        str(row.get("step_id", "")): row
        for row in contract.get("steps", [])
        if isinstance(row, Mapping)
    }
    artifact_index = {
        str(row.get("artifact_id", "")): row
        for row in contract.get("artifacts", [])
        if isinstance(row, Mapping)
    }
    for step_id_value, raw_step_packet in steps_packet.items():
        step_id = str(step_id_value)
        step_path = f"$.steps.{step_id}"
        step = step_index.get(step_id)
        if (
            step is None
            or str(step.get("route_id", "")) not in selected_route_ids
            or bool(str(step.get("terminal_kind", "")))
        ):
            raise SupervisorError("unconsumed_step_packet", step_path)
        step_packet = _packet_object(raw_step_packet, step_path)
        binding = step.get("binding", {}) if isinstance(step.get("binding"), Mapping) else {}
        action_class = required_evidence_class(step)
        if step_packet.get("skip"):
            if bool(step.get("required", True)):
                raise SupervisorError("required_step_skip_packet", step_path)
            continue
        if step_packet.get("judgment") and action_class != "judged":
            raise SupervisorError("unconsumed_packet_field", f"{step_path}.judgment")
        if step_packet.get("witness") and action_class != "witnessed":
            raise SupervisorError("unconsumed_packet_field", f"{step_path}.witness")
        if action_class == "judged" and not step_packet.get("judgment"):
            raise SupervisorError("judgment_packet_missing", step_id)
        if action_class == "witnessed" and not step_packet.get("witness"):
            raise SupervisorError("step_witness_missing", step_id)
        output_artifact_ids = {str(item) for item in binding.get("output_artifact_ids", [])}
        artifact_witnesses = _packet_object(
            step_packet.get("artifact_witnesses", {}),
            f"{step_path}.artifact_witnesses",
        )
        unknown_artifacts = sorted(str(item) for item in artifact_witnesses if str(item) not in output_artifact_ids)
        if unknown_artifacts:
            raise SupervisorError(
                "unconsumed_packet_field",
                f"{step_path}.artifact_witnesses.{unknown_artifacts[0]}",
            )
        for artifact_id in output_artifact_ids:
            declaration = artifact_index.get(artifact_id, {})
            kind = str(declaration.get("kind", ""))
            has_specific_witness = artifact_id in artifact_witnesses
            if has_specific_witness and kind not in WITNESS_KINDS | {"screenshot"}:
                raise SupervisorError(
                    "unconsumed_packet_field",
                    f"{step_path}.artifact_witnesses.{artifact_id}",
                )
            if kind == "screenshot" and not has_specific_witness:
                raise SupervisorError("screenshot_witness_packet_missing", artifact_id)


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    path = filesystem_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(canonical_json_bytes(payload))
    os.replace(temporary, path)


def _is_installed_projection_root(skill_root: Path) -> bool:
    configured = os.environ.get("CODEX_HOME")
    codex_home = (
        Path(configured).expanduser()
        if configured
        else Path.home() / ".codex"
    ).resolve()
    return skill_root.resolve().parent == (codex_home / "skills").resolve()


def _load_current_runtime_object(path: Path, error_code: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SupervisorError(error_code, path.as_posix()) from exc
    if not isinstance(payload, Mapping):
        raise SupervisorError(error_code, path.as_posix())
    return payload


def _load_or_compile_runtime_pair(
    skill_root: Path,
    repository_root: Path,
    compiled_contract: Mapping[str, Any] | None,
    check_manifest: Mapping[str, Any] | None,
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    if (compiled_contract is None) != (check_manifest is None):
        raise SupervisorError(
            "compiled_runtime_pair_incomplete",
            "compiled_contract and check_manifest must be supplied together",
        )
    if compiled_contract is not None:
        assert check_manifest is not None
        contract = compiled_contract
        manifest = check_manifest
    elif _is_installed_projection_root(skill_root):
        authority = resolve_runtime_authority(skill_root)
        if not authority.ok or authority.authority != AUTHORITY_CURRENT:
            raise SupervisorError(
                "runtime_authority_blocked",
                json.dumps(authority.to_dict(), sort_keys=True),
            )
        control = skill_root / ".skillguard"
        contract = _load_current_runtime_object(
            control / "compiled-contract.json",
            "installed_compiled_contract_unreadable",
        )
        manifest = _load_current_runtime_object(
            control / "check-manifest.json",
            "installed_check_manifest_unreadable",
        )
    else:
        compiled = compile_skill_contract(
            skill_root, repository_root=repository_root, write=True
        )
        if (
            not compiled.ok
            or compiled.compiled_contract is None
            or compiled.check_manifest is None
        ):
            raise SupervisorError(
                "contract_compile_failed",
                json.dumps(compiled.to_dict(), sort_keys=True),
            )
        contract = compiled.compiled_contract
        manifest = compiled.check_manifest
    authority = resolve_runtime_authority(skill_root)
    if not authority.ok or authority.authority != AUTHORITY_CURRENT:
        raise SupervisorError(
            "runtime_authority_blocked",
            json.dumps(authority.to_dict(), sort_keys=True),
        )
    return contract, manifest


def _preview_runtime_pair(
    skill_root: Path,
    repository_root: Path,
    compiled_contract: Mapping[str, Any] | None,
    check_manifest: Mapping[str, Any] | None,
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    """Resolve a candidate current pair without writing compiler outputs."""

    if (compiled_contract is None) != (check_manifest is None):
        raise SupervisorError(
            "compiled_runtime_pair_incomplete",
            "compiled_contract and check_manifest must be supplied together",
        )
    if compiled_contract is not None:
        assert check_manifest is not None
        return compiled_contract, check_manifest
    if _is_installed_projection_root(skill_root):
        control = skill_root / ".skillguard"
        return (
            _load_current_runtime_object(
                control / "compiled-contract.json",
                "installed_compiled_contract_unreadable",
            ),
            _load_current_runtime_object(
                control / "check-manifest.json",
                "installed_check_manifest_unreadable",
            ),
        )
    compiled = compile_skill_contract(
        skill_root,
        repository_root=repository_root,
        write=False,
    )
    preview_only_findings = {
        str(finding.code)
        for finding in compiled.findings
    }
    generated_parity_only = preview_only_findings.issubset(
        {"generated_file_missing", "stale_generated_contract"}
    )
    if (
        compiled.compiled_contract is None
        or compiled.check_manifest is None
        or not generated_parity_only
    ):
        raise SupervisorError(
            "contract_preview_failed",
            json.dumps(compiled.to_dict(), sort_keys=True),
        )
    return compiled.compiled_contract, compiled.check_manifest


def _current_fingerprints(
    contract: Mapping[str, Any],
    request: Mapping[str, Any],
    target_root: Path | None = None,
    *,
    guard_runtime_identity: Mapping[str, Any] | None = None,
) -> Mapping[str, Mapping[str, str]]:
    sources = contract.get("source_fingerprints", {})
    implementation = {
        key: value
        for key, value in sources.items()
        if str(key).startswith("implementation:")
    }
    fingerprints: dict[str, Mapping[str, str]] = {
        "guard_runtime": fingerprint_value(
            guard_runtime_identity or guard_execution_runtime_fingerprint()
        ),
        "contract": fingerprint_value(str(contract.get("contract_hash", ""))),
        "implementation": fingerprint_value(implementation),
        "model_export": fingerprint_value(str(sources.get("model_export", ""))),
        "environment": fingerprint_value(
            {
                "python": platform.python_version(),
                "platform": platform.system(),
                "request": request,
            }
        ),
    }
    target_input_paths = request.get("target_input_paths")
    if target_input_paths is not None:
        if target_root is None:
            raise SupervisorError(
                "target_input_root_missing",
                "target_root is required to derive target input fingerprints",
            )
        try:
            target_inputs = fingerprint_target_inputs(target_root, target_input_paths)
        except TargetInputError as exc:
            raise SupervisorError(exc.code, exc.detail) from exc
        fingerprints["target_inputs"] = fingerprint_value(target_inputs)
    target_input_roles = request.get("target_input_roles")
    if target_input_roles is not None:
        if target_root is None:
            raise SupervisorError(
                "target_input_root_missing",
                "target_root is required to derive target input role fingerprints",
            )
        try:
            role_inputs = fingerprint_target_input_roles(target_root, target_input_roles)
        except TargetInputError as exc:
            raise SupervisorError(exc.code, exc.detail) from exc
        for role, inventory in sorted(role_inputs.items()):
            fingerprints[f"target_role:{role}"] = fingerprint_value(inventory)
    return fingerprints


def _step_sort_key(
    contract: Mapping[str, Any], route_ids: Sequence[str], step: Mapping[str, Any]
) -> tuple[int, int, str]:
    route_id = str(step.get("route_id", ""))
    route_priority = {route: index for index, route in enumerate(route_ids)}
    routes = {
        str(row.get("route_id", "")): row
        for row in contract.get("routes", [])
        if isinstance(row, Mapping)
    }
    declared = [str(item) for item in routes.get(route_id, {}).get("step_ids", [])]
    try:
        step_priority = declared.index(str(step.get("step_id", "")))
    except ValueError:
        step_priority = len(declared)
    return route_priority.get(route_id, len(route_priority)), step_priority, str(step.get("step_id", ""))


def _latest_passed_receipt_id(run_root: Path, step_id: str) -> str:
    matches = [
        row
        for row in load_receipts(run_root)
        if row.get("step_id") == step_id and row.get("status") == "passed"
    ]
    if not matches:
        raise SupervisorError("referenced_step_receipt_missing", step_id)
    return str(matches[-1]["receipt_id"])


def _materialize_witness(
    run_root: Path,
    spec: Mapping[str, Any],
    *,
    default_kind: str,
    default_target_id: str,
) -> dict[str, Any]:
    if {"witness_id", "target_id", "input_fingerprint", "output_fingerprint"}.issubset(spec):
        witness = dict(spec)
    else:
        witness = build_action_witness(
            witness_kind=str(spec.get("witness_kind", default_kind)),
            target_id=str(spec.get("target_id", default_target_id)),
            input_value=spec.get("input", {}),
            output_value=spec.get("output", {}),
            executor_id=str(spec.get("executor_id", "skillguard-v2-supervisor")),
            limitations=[str(item) for item in spec.get("limitations", [])],
        )
        witness["witness_id"] = f"witness-{canonical_hash(witness)[:24].lower()}"
    for key in ("surface_id", "state_id", "interaction_receipt_id"):
        if spec.get(key):
            witness[key] = str(spec[key])
    reference_step = str(spec.get("interaction_receipt_step_id", ""))
    if reference_step:
        witness["interaction_receipt_id"] = _latest_passed_receipt_id(run_root, reference_step)
    return witness


def _judged_evidence(
    contract: Mapping[str, Any],
    packet: Mapping[str, Any],
    *,
    check_id: str,
    expected_rubric_id: str,
) -> Mapping[str, Any]:
    judgment = packet.get("judgment", {})
    if not isinstance(judgment, Mapping):
        raise SupervisorError("judgment_packet_invalid", "judgment must be an object")
    rubric_id = str(judgment.get("rubric_id", expected_rubric_id))
    if rubric_id != expected_rubric_id:
        raise SupervisorError(
            "judgment_rubric_mismatch",
            f"expected {expected_rubric_id}; actual {rubric_id}",
        )
    rubrics = {
        str(row.get("rubric_id", "")): row
        for row in contract.get("judgment_rubrics", [])
        if isinstance(row, Mapping)
    }
    rubric = rubrics.get(rubric_id)
    if rubric is None:
        raise SupervisorError("judgment_rubric_not_declared", rubric_id)
    evidence: dict[str, Any] = {
        "rubric_id": rubric_id,
        "rubric_version": str(judgment.get("rubric_version", rubric.get("version", ""))),
        "evaluator_id": str(judgment.get("evaluator_id", "")),
        "input_fingerprint": fingerprint_value(judgment.get("input", {}))["raw"],
        "conclusion": str(judgment.get("conclusion", "")),
        "limitations": [str(item) for item in judgment.get("limitations", [])],
        "self_review": bool(judgment.get("self_review", False)),
        "check_id": check_id,
    }
    if judgment.get("confidence_boundary"):
        evidence["confidence_boundary"] = str(judgment["confidence_boundary"])
    return evidence


def supervise_contract_run(
    skill_root: Path,
    target_root: Path,
    repository_root: Path,
    packet: Mapping[str, Any],
    *,
    compiled_contract: Mapping[str, Any] | None = None,
    check_manifest: Mapping[str, Any] | None = None,
    claim_snapshots: Mapping[str, Mapping[str, Any]] | None = None,
    run_state_root: Path | None = None,
    owner_evidence_root: Path | None = None,
    guard_runtime_identity: Mapping[str, Any] | None = None,
    verified_installation_context: VerifiedInstallationContext | None = None,
) -> Mapping[str, Any]:
    """Compile, claim, execute, evidence, close, and replay one target-local run."""

    validate_supervisor_packet(packet)
    skill_root = skill_root.resolve()
    target_root = target_root.resolve()
    repository_root = repository_root.resolve()
    request_packet = packet.get("request", {})
    if not isinstance(request_packet, Mapping):
        raise SupervisorError("request_packet_invalid", "request must be an object")
    request = dict(request_packet)
    steps_packet = packet.get("steps", {})
    if not isinstance(steps_packet, Mapping):
        raise SupervisorError("steps_packet_invalid", "steps must be an object")
    supervision_mode = str(packet.get("supervision_mode", "close"))
    profiles = tuple(str(item) for item in packet.get("profiles", ["enforced"]))

    preview_contract, _preview_manifest = _preview_runtime_pair(
        skill_root,
        repository_root,
        compiled_contract,
        check_manifest,
    )
    effective_run_state_root = (
        run_state_root
        if run_state_root is not None
        else repository_root / "work" / "skillguard" / "run-state"
    )
    effective_owner_evidence_root = (
        owner_evidence_root
        if owner_evidence_root is not None
        else repository_root / "work" / "verification" / "owner-evidence"
    )
    try:
        author_context = validate_author_maintenance_context(
            contract=preview_contract,
            skill_root=skill_root,
            target_root=target_root,
            author_repository_root=repository_root,
            run_state_root=effective_run_state_root,
            owner_evidence_root=effective_owner_evidence_root,
        )
    except AuthorContextError as exc:
        raise SupervisorError(exc.code, exc.message) from exc
    contract, manifest = _load_or_compile_runtime_pair(
        skill_root,
        repository_root,
        compiled_contract,
        check_manifest,
    )
    persistent_owner_root = resolve_owner_evidence_root(
        repository_root,
        author_context.owner_evidence_root,
    )
    if "target_input_paths" in request:
        try:
            target_inputs = fingerprint_target_inputs(
                target_root,
                request["target_input_paths"],
            )
        except TargetInputError as exc:
            raise SupervisorError(exc.code, exc.detail) from exc
        request["target_input_paths"] = list(target_inputs["paths"])
        request["target_input_fingerprint"] = str(target_inputs["fingerprint"])
    if "target_input_roles" in request:
        try:
            target_input_roles = fingerprint_target_input_roles(
                target_root,
                request["target_input_roles"],
            )
        except TargetInputError as exc:
            raise SupervisorError(exc.code, exc.detail) from exc
        request["target_input_roles"] = {
            role: list(inventory["paths"])
            for role, inventory in sorted(target_input_roles.items())
        }
    decision = select_routes(contract, request)
    if not decision.ok:
        raise SupervisorError("route_selection_blocked", json.dumps(decision.to_dict(), sort_keys=True))
    validate_supervisor_packet(packet, contract=contract, route_ids=decision.route_ids)
    effective_guard = dict(
        guard_runtime_identity or guard_execution_runtime_fingerprint()
    )
    claim = claim_run(
        contract,
        request,
        author_context.run_state_root,
        decision,
        check_manifest=manifest,
        claim_snapshots=claim_snapshots,
        guard_runtime_identity=effective_guard,
    )
    if not claim.ok or claim.run_root is None:
        raise SupervisorError("run_claim_blocked", json.dumps(claim.to_dict(), sort_keys=True))
    run_root = claim.run_root
    fingerprints = _current_fingerprints(
        contract,
        request,
        target_root,
        guard_runtime_identity=effective_guard,
    )
    check_index = {
        str(row.get("check_id", "")): row
        for row in manifest.get("checks", [])
        if isinstance(row, Mapping)
    }
    artifact_index = {
        str(row.get("artifact_id", "")): row
        for row in contract.get("artifacts", [])
        if isinstance(row, Mapping)
    }
    executed_steps: list[dict[str, Any]] = []
    owner_rows = {
        str(row.get("execution_owner_id", "")): row
        for row in contract.get("content_impact_plan", {}).get("owners", [])
        if isinstance(row, Mapping)
    }
    owner_receipts = load_run_owner_receipt_index(
        run_root,
        persistent_owner_root,
    )

    while True:
        ready = sorted(
            next_ready_steps(run_root),
            key=lambda row: _step_sort_key(contract, decision.route_ids, row),
        )
        if not ready:
            break
        step = ready[0]
        step_id = str(step["step_id"])
        packet_for_step = steps_packet.get(step_id, {})
        if not isinstance(packet_for_step, Mapping):
            raise SupervisorError("step_packet_invalid", step_id)
        skip = packet_for_step.get("skip", {})
        if isinstance(skip, Mapping) and skip:
            condition_step_id = str(skip.get("condition_step_id", ""))
            verifier_step_id = str(skip.get("verifier_step_id", condition_step_id))
            condition_receipt_id = str(skip.get("condition_receipt_id", "")) or _latest_passed_receipt_id(
                run_root, condition_step_id
            )
            verifier_receipt_id = str(skip.get("verifier_receipt_id", "")) or _latest_passed_receipt_id(
                run_root, verifier_step_id
            )
            request_skip(run_root, step_id, str(skip.get("reason", "")), condition_receipt_id)
            approve_skip(run_root, step_id, verifier_receipt_id)
            executed_steps.append(
                {
                    "step_id": step_id,
                    "status": "skipped",
                    "condition_receipt_id": condition_receipt_id,
                    "verifier_receipt_id": verifier_receipt_id,
                }
            )
            continue

        begin_step(run_root, step_id)
        binding = step.get("binding", {}) if isinstance(step.get("binding"), Mapping) else {}
        check_records: list[Mapping[str, Any]] = []
        check_executions: list[Mapping[str, Any]] = []
        failures: list[str] = []
        for check_id_value in binding.get("check_ids", []):
            check_id = str(check_id_value)
            check = check_index.get(check_id)
            if check is None:
                failures.append(f"missing check declaration:{check_id}")
                continue
            owner_id = str(check.get("execution_owner_id", ""))
            owner_row = owner_rows.get(owner_id, {})
            dependency_receipts = {
                str(dependency_owner_id): owner_receipts[
                    str(dependency_owner_id)
                ]
                for dependency_owner_id in owner_row.get(
                    "depends_on_owner_ids", []
                )
                if str(dependency_owner_id) in owner_receipts
            }
            execution = get_or_execute_check(
                check,
                skill_root=skill_root,
                target_root=target_root,
                repository_root=repository_root,
                run_root=run_root,
                step_id=step_id,
                owner_evidence_root=persistent_owner_root,
                dependency_execution_receipts=dependency_receipts,
            )
            check_executions.append(execution)
            if isinstance(execution.get("execution_receipt"), Mapping):
                owner_receipts[owner_id] = execution["execution_receipt"]
            record = execution["record"]
            check_records.append(record)
            if record.get("status") != "passed":
                result = (
                    record.get("result", {})
                    if isinstance(record.get("result"), Mapping)
                    else {}
                )
                failures.append(
                    f"{check_id}:{record.get('status')}:{result.get('reason')}"
                )
        record_step(
            run_root,
            step_id,
            {
                "check_record_ids": [str(row["check_record_id"]) for row in check_records],
                "check_execution_receipt_ids": [
                    str(row["execution_receipt"]["receipt_id"])
                    for row in check_executions
                    if isinstance(row.get("execution_receipt"), Mapping)
                ],
                "owner_execution_receipts": [
                    {
                        "check_id": str(row["record"].get("check_id", "")),
                        "execution_owner_id": str(
                            row["record"].get("execution_owner_id", "")
                        ),
                        "receipt_id": str(
                            row["execution_receipt"].get("receipt_id", "")
                        ),
                        "receipt_hash": str(
                            row["execution_receipt"].get("receipt_hash", "")
                        ),
                        "receipt_ref": dict(
                            row.get("execution_receipt_ref", {})
                        ),
                    }
                    for row in check_executions
                    if isinstance(row.get("execution_receipt"), Mapping)
                    and isinstance(row.get("execution_receipt_ref"), Mapping)
                ],
                "packet_hash": canonical_hash(packet_for_step),
                "action_summary": str(binding.get("action", {}).get("summary", "")),
            },
        )
        if failures:
            record_failure(run_root, step_id, "all declared checks pass", ";".join(failures), "declared check failure")
            raise SupervisorError("step_check_failed", f"{step_id}:{';'.join(failures)}")
        if not check_records:
            record_failure(run_root, step_id, "at least one current check", "none", "step has no executed check")
            raise SupervisorError("step_without_check_record", step_id)

        step_witness: Mapping[str, Any] | None = None
        if isinstance(packet_for_step.get("witness"), Mapping):
            step_witness = _materialize_witness(
                run_root,
                packet_for_step["witness"],
                default_kind="ui_interaction",
                default_target_id=step_id,
            )
        artifact_records: list[Mapping[str, Any]] = []
        artifact_witnesses = packet_for_step.get("artifact_witnesses", {})
        if not isinstance(artifact_witnesses, Mapping):
            raise SupervisorError("artifact_witnesses_invalid", step_id)
        for artifact_id_value in binding.get("output_artifact_ids", []):
            artifact_id = str(artifact_id_value)
            declaration = artifact_index.get(artifact_id)
            if declaration is None:
                raise SupervisorError("artifact_declaration_missing", artifact_id)
            witness: Mapping[str, Any] | None = None
            witness_spec = artifact_witnesses.get(artifact_id)
            if isinstance(witness_spec, Mapping):
                witness = _materialize_witness(
                    run_root,
                    witness_spec,
                    default_kind="ui_interaction",
                    default_target_id=artifact_id,
                )
            elif str(declaration.get("kind", "")) in WITNESS_KINDS:
                witness = step_witness
            artifact_record = validate_artifact(
                run_root,
                target_root,
                declaration,
                producer_step_id=step_id,
                witness=witness,
            )
            if artifact_record.get("status") != "passed":
                raise SupervisorError("artifact_validation_failed", artifact_id)
            artifact_records.append(artifact_record)

        hard_receipts: list[Mapping[str, Any]] = []
        for index, check_record in enumerate(check_records):
            hard_receipts.append(
                issue_receipt(
                    run_root,
                    step_id=step_id,
                    evidence_class="hard",
                    evidence=hard_evidence_from_check(check_record),
                    decision="passed",
                    verifier_id="skillguard-v2-native-check-verifier",
                    input_fingerprints=fingerprints,
                    artifact_record_ids=(
                        [str(row["artifact_record_id"]) for row in artifact_records]
                        if index == 0
                        else []
                    ),
                    owner_evidence_root=persistent_owner_root,
                )
            )
        primary_class = required_evidence_class(step)
        check_id = str(check_records[0]["check_id"])
        if primary_class == "hard":
            primary = hard_receipts[0]
        elif primary_class == "witnessed":
            if step_witness is None:
                raise SupervisorError("step_witness_missing", step_id)
            witnessed_evidence = dict(step_witness)
            witnessed_evidence["check_id"] = check_id
            primary = issue_receipt(
                run_root,
                step_id=step_id,
                evidence_class="witnessed",
                evidence=witnessed_evidence,
                decision="passed",
                verifier_id=str(step_witness.get("executor_id", "skillguard-v2-witness-verifier")),
                input_fingerprints=fingerprints,
                artifact_record_ids=[str(row["artifact_record_id"]) for row in artifact_records],
                consumed_child_receipt_ids=[str(row["receipt_id"]) for row in hard_receipts],
            )
        elif primary_class == "judged":
            action = binding.get("action", {}) if isinstance(binding.get("action"), Mapping) else {}
            expected_rubric_id = str(action.get("rubric_id", ""))
            if not expected_rubric_id:
                raise SupervisorError("judged_step_rubric_missing", step_id)
            judged = _judged_evidence(
                contract,
                packet_for_step,
                check_id=check_id,
                expected_rubric_id=expected_rubric_id,
            )
            primary = issue_receipt(
                run_root,
                step_id=step_id,
                evidence_class="judged",
                evidence=judged,
                decision="passed",
                verifier_id=str(judged["evaluator_id"]),
                input_fingerprints=fingerprints,
                artifact_record_ids=[str(row["artifact_record_id"]) for row in artifact_records],
                consumed_child_receipt_ids=[str(row["receipt_id"]) for row in hard_receipts],
            )
        else:
            raise SupervisorError("unsupported_primary_evidence_class", f"{step_id}:{primary_class}")
        record_verification(
            run_root,
            step_id,
            "passed",
            str(primary["receipt_id"]),
            verifier=str(primary["verifier_id"]),
        )
        executed_steps.append(
            {
                "step_id": step_id,
                "status": "passed",
                "primary_receipt_id": str(primary["receipt_id"]),
                "primary_evidence_class": primary_class,
                "check_record_ids": [str(row["check_record_id"]) for row in check_records],
                "check_execution_dispositions": [
                    str(row.get("disposition", "")) for row in check_executions
                ],
                "check_execution_receipt_ids": [
                    str(row["execution_receipt"]["receipt_id"])
                    for row in check_executions
                    if isinstance(row.get("execution_receipt"), Mapping)
                ],
                "artifact_record_ids": [str(row["artifact_record_id"]) for row in artifact_records],
            }
        )

    state = replay_run(run_root)
    selected_route_ids = set(decision.route_ids)
    selected_step_ids = {
        str(row.get("step_id", ""))
        for row in contract.get("steps", [])
        if isinstance(row, Mapping)
        and str(row.get("route_id", "")) in selected_route_ids
        and not str(row.get("terminal_kind", ""))
    }
    unfinished = {
        step_id: status
        for step_id, status in state.step_statuses.items()
        if step_id in selected_step_ids and status not in {"passed", "skipped"}
    }
    if unfinished:
        raise SupervisorError("run_unfinished", json.dumps(unfinished, sort_keys=True))
    depth_receipt: Mapping[str, Any] | None = None
    installation_context = (
        validate_verified_installation_context(verified_installation_context)
        if verified_installation_context is not None
        else None
    )
    # Re-read every target input immediately before depth and closure.  A file
    # changed after the native check invalidates the earlier receipts.
    fingerprints = _current_fingerprints(
        contract,
        request,
        target_root,
        guard_runtime_identity=effective_guard,
    )
    if isinstance(contract.get("depth_profile"), Mapping):
        raw_depth_packet = packet.get("execution_depth", {})
        if not isinstance(raw_depth_packet, Mapping):
            raise SupervisorError("execution_depth_packet_invalid", "execution_depth must be an object")
        depth_packet = dict(raw_depth_packet)
        evidence_domain = str(
            depth_packet.get("evidence_domain", "capability_validation")
        )
        scheduled_identity = depth_packet.get("scheduled_production_identity")
        if evidence_domain == "scheduled_production":
            if not isinstance(scheduled_identity, Mapping):
                raise SupervisorError(
                    "scheduled_production_identity_missing",
                    "scheduled production requires an installation-bound identity",
                )
            try:
                if installation_context is None:
                    installation_context = load_scheduled_production_installation_context(
                        scheduled_identity
                    )
                else:
                    verify_scheduled_production_installation_identity(
                        scheduled_identity,
                        verified_context=installation_context,
                    )
            except (OSError, TypeError, ValueError) as exc:
                raise SupervisorError(
                    "scheduled_production_installation_not_current",
                    str(exc),
                ) from exc
        elif scheduled_identity not in (None, {}):
            raise SupervisorError(
                "non_production_schedule_identity_forbidden",
                evidence_domain,
            )
        depth_receipt = issue_target_execution_receipt(
            run_root,
            contract,
            depth_packet,
            current_fingerprints=fingerprints,
            repository_root=repository_root,
            target_root=target_root,
            active_runtime_identity=effective_guard,
            verified_installation_context=installation_context,
        )
    if supervision_mode == "stage_depth":
        if depth_receipt is None:
            raise SupervisorError(
                "stage_depth_receipt_missing",
                "stage_depth requires an enforced execution-depth profile",
            )
        report: dict[str, Any] = {
            "schema_version": "skillguard.supervisor_result.v2",
            "status": "staged",
            "supervision_mode": "stage_depth",
            "skill_id": str(contract.get("skill_id", "")),
            "run_id": str(claim.run_id),
            "run_root": run_root.as_posix(),
            "contract_hash": str(contract["contract_hash"]),
            "manifest_hash": str(manifest["manifest_hash"]),
            "route_ids": list(decision.route_ids),
            "executed_steps": executed_steps,
            "target_execution_depth_receipt": dict(depth_receipt),
            "closures": [],
            "created_at": utc_now(),
            "claim_boundary": (
                "This stage proves only current execution and one exact target-depth receipt. "
                "It is intentionally not a closure claim; the target must build a native terminal "
                "receipt from this depth receipt before resuming the same run in close mode."
            ),
        }
        report["report_hash"] = canonical_hash(report)
        _atomic_write(run_root / "supervisor-result.json", report)
        return report
    closures: list[Mapping[str, Any]] = []
    native_terminal_packet = packet.get("native_terminal", {})
    if not isinstance(native_terminal_packet, Mapping):
        native_terminal_packet = {}
    native_terminal_ref = native_terminal_packet.get("receipt_ref")
    expected_native_route_id = str(
        native_terminal_packet.get("expected_route_id", "")
    )
    expected_native_branch_id = str(
        native_terminal_packet.get("expected_branch_id", "")
    )
    for profile in profiles:
        fingerprints = _current_fingerprints(
            contract,
            request,
            target_root,
            guard_runtime_identity=effective_guard,
        )
        evaluation, closure = close_run(
            run_root,
            profile=profile,
            current_fingerprints=fingerprints,
            target_root=target_root,
            repository_root=repository_root,
            owner_evidence_root=persistent_owner_root,
            native_terminal_receipt_ref=(
                native_terminal_ref
                if isinstance(native_terminal_ref, Mapping)
                else None
            ),
            expected_route_id=expected_native_route_id,
            expected_branch_id=expected_native_branch_id,
            verified_installation_context=installation_context,
        )
        if evaluation.status != "closed" or closure is None:
            raise SupervisorError("closure_failed", json.dumps(evaluation.to_dict(), sort_keys=True))
        fingerprints = _current_fingerprints(
            contract,
            request,
            target_root,
            guard_runtime_identity=effective_guard,
        )
        verification = verify_closure(
            run_root,
            str(closure["closure_receipt_id"]),
            current_fingerprints=fingerprints,
            target_root=target_root,
            repository_root=repository_root,
            owner_evidence_root=persistent_owner_root,
            verified_installation_context=installation_context,
        )
        if not verification.get("ok"):
            raise SupervisorError("closure_replay_failed", json.dumps(verification, sort_keys=True))
        closures.append(
            {
                "profile": profile,
                "closure_receipt_id": str(closure["closure_receipt_id"]),
                "closure_hash": str(closure["closure_hash"]),
                "verification": verification,
            }
        )
    report: dict[str, Any] = {
        "schema_version": "skillguard.supervisor_result.v2",
        "status": "passed",
        "supervision_mode": "close",
        "skill_id": str(contract.get("skill_id", "")),
        "run_id": str(claim.run_id),
        "run_root": run_root.as_posix(),
        "contract_hash": str(contract["contract_hash"]),
        "manifest_hash": str(manifest["manifest_hash"]),
        "route_ids": list(decision.route_ids),
        "executed_steps": executed_steps,
        "target_execution_depth_receipt": dict(depth_receipt) if depth_receipt is not None else None,
        "closures": closures,
        "created_at": utc_now(),
        "claim_boundary": (
            "This result proves only the selected routes, declared checks, supplied evaluator/witness packets, "
            "current artifacts, and the enforced closure for this exact target-local run."
        ),
    }
    report["report_hash"] = canonical_hash(report)
    _atomic_write(run_root / "supervisor-result.json", report)
    return report
