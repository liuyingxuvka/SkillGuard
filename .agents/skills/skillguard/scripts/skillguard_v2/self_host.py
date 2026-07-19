"""Single-authority SkillGuard self-host execution."""

from __future__ import annotations

import json
import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .artifact_validators import validate_artifact
from .check_runner import (
    get_or_execute_check,
    hard_evidence_from_check,
    inspect_current_owner_execution,
    load_check_result,
    load_run_owner_receipt_index,
    resolve_owner_evidence_root,
)
from .closure import close_run, verify_closure
from .contract_compiler import canonical_hash, canonical_json_bytes, compile_skill_contract
from .evidence_policy import required_evidence_class
from .execution_depth import issue_target_execution_receipt
from .privacy import git_public_candidates
from .receipts import fingerprint_value, issue_receipt
from .route_runtime import select_routes
from .runtime_fingerprint import guard_execution_runtime_fingerprint
from .run_store import claim_run, utc_now
from .step_runtime import (
    begin_step,
    next_ready_steps,
    record_failure,
    record_step,
    record_verification,
    reopen_step,
    replay_run,
)
from .target_inputs import fingerprint_target_input_roles, fingerprint_target_inputs


ProgressCallback = Callable[[Mapping[str, Any]], None]


ROUTE_PRIORITY = (
    "route:static-audit",
    "route:deep-audit",
    "route:compile-contract",
    "route:supervise-run",
    "route:author-repository-adoption",
    "route:global-router-handoff",
    "route:provenance-audit",
    "route:portfolio-graduation",
    "route:verify-evidence",
    "route:derive-closure",
)
SELF_HOST_LONG_CHECK_TIMEOUT_POLICIES: Mapping[str, Mapping[str, Any]] = {
    "check:self:installation-safety": {
        "kind": "command",
        "command": "python",
        "args": (
            "-m",
            "pytest",
            "tests/test_installation.py",
            "tests/test_installation_verification_receipt.py",
            "-q",
        ),
        "measurement_samples_seconds": (352.834, 563.984),
        "measured_elapsed_seconds": 563.984,
        "measured_ceiling_seconds": 600.0,
        "runtime_variance_grace_seconds": 120.0,
    },
}


@dataclass(frozen=True)
class SelfHostError(RuntimeError):
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def _load_json(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise SelfHostError("self_host_json_not_object", path.name)
    return payload


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(canonical_json_bytes(payload))
    os.replace(temporary, path)


def _stderr_progress(event: Mapping[str, Any]) -> None:
    sys.stderr.write(json.dumps(dict(event), sort_keys=True) + "\n")
    sys.stderr.flush()










def _current_fingerprints(
    contract: Mapping[str, Any],
    *,
    repository_root: Path | None = None,
    target_input_paths: Sequence[str] = (),
    target_input_roles: Mapping[str, Sequence[str]] | None = None,
) -> Mapping[str, Mapping[str, str]]:
    sources = contract.get("source_fingerprints", {})
    fingerprints: dict[str, Mapping[str, str]] = {
        "guard_runtime": fingerprint_value(guard_execution_runtime_fingerprint()),
        "contract": fingerprint_value(str(contract.get("contract_hash", ""))),
        "implementation": fingerprint_value(
            {
                "entrypoint": sources.get("entrypoint"),
                "model": sources.get("model"),
                "binding": sources.get("binding"),
                "declared_implementation": {
                    key: value
                    for key, value in sources.items()
                    if str(key).startswith("implementation:")
                },
            }
        ),
        "model_export": fingerprint_value(str(sources.get("model_export", ""))),
        "environment": fingerprint_value(
            {
                "python": platform.python_version(),
                "platform": platform.system(),
                "guard_runtime": guard_execution_runtime_fingerprint(),
            }
        ),
    }
    if repository_root is not None and target_input_paths:
        fingerprints["target_inputs"] = fingerprint_value(
            fingerprint_target_inputs(repository_root, target_input_paths)
        )
    if repository_root is not None and target_input_roles:
        for role_id, inventory in sorted(
            fingerprint_target_input_roles(
                repository_root,
                target_input_roles,
            ).items()
        ):
            fingerprints[f"target_role:{role_id}"] = fingerprint_value(inventory)
    return fingerprints


def _step_sort_key(step: Mapping[str, Any]) -> tuple[int, str]:
    route_id = str(step.get("route_id", ""))
    try:
        priority = ROUTE_PRIORITY.index(route_id)
    except ValueError:
        priority = len(ROUTE_PRIORITY)
    return priority, str(step.get("step_id", ""))


def _select_ready_step_by_owner_dependencies(
    ready_steps: Sequence[Mapping[str, Any]],
    *,
    check_index: Mapping[str, Mapping[str, Any]],
    owner_rows: Mapping[str, Mapping[str, Any]],
    owner_receipts: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any]:
    """Select a ready workflow step whose native owner dependencies are current."""

    missing_by_step: dict[str, list[str]] = {}
    for step in sorted(ready_steps, key=_step_sort_key):
        binding = (
            step.get("binding", {})
            if isinstance(step.get("binding"), Mapping)
            else {}
        )
        missing: set[str] = set()
        step_owner_ids: set[str] = set()
        for check_id in binding.get("check_ids", []):
            check = check_index.get(str(check_id))
            if not isinstance(check, Mapping):
                missing.add(f"missing-check:{check_id}")
                continue
            owner_id = str(check.get("execution_owner_id", ""))
            owner = owner_rows.get(owner_id)
            if not isinstance(owner, Mapping):
                missing.add(f"missing-owner:{owner_id}")
                continue
            step_owner_ids.add(owner_id)
        for check_id in binding.get("check_ids", []):
            check = check_index.get(str(check_id))
            if not isinstance(check, Mapping):
                continue
            owner_id = str(check.get("execution_owner_id", ""))
            owner = owner_rows.get(owner_id)
            if not isinstance(owner, Mapping):
                continue
            missing.update(
                str(dependency_owner_id)
                for dependency_owner_id in owner.get(
                    "depends_on_owner_ids", []
                )
                if str(dependency_owner_id) not in owner_receipts
                and str(dependency_owner_id) not in step_owner_ids
            )
        if not missing:
            return step
        missing_by_step[str(step.get("step_id", ""))] = sorted(missing)
    raise SelfHostError(
        "self_host_owner_dependency_deadlock",
        json.dumps(missing_by_step, sort_keys=True),
    )


def _order_step_checks_by_owner_dependencies(
    check_ids: Sequence[str],
    *,
    check_index: Mapping[str, Mapping[str, Any]],
    owner_rows: Mapping[str, Mapping[str, Any]],
    owner_receipts: Mapping[str, Mapping[str, Any]],
) -> tuple[str, ...]:
    """Topologically order one step's native owners without executing them."""

    pending = [str(check_id) for check_id in check_ids]
    available = set(owner_receipts)
    ordered: list[str] = []
    while pending:
        selected_index: int | None = None
        for index, check_id in enumerate(pending):
            check = check_index.get(check_id)
            if not isinstance(check, Mapping):
                raise SelfHostError(
                    "self_host_step_check_missing",
                    check_id,
                )
            owner_id = str(check.get("execution_owner_id", ""))
            owner = owner_rows.get(owner_id)
            if not isinstance(owner, Mapping):
                raise SelfHostError(
                    "self_host_step_owner_missing",
                    owner_id,
                )
            dependencies = {
                str(value) for value in owner.get("depends_on_owner_ids", [])
            }
            if dependencies.issubset(available):
                selected_index = index
                break
        if selected_index is None:
            blocked = {
                check_id: sorted(
                    str(value)
                    for value in owner_rows[
                        str(check_index[check_id].get("execution_owner_id", ""))
                    ].get("depends_on_owner_ids", [])
                    if str(value) not in available
                )
                for check_id in pending
            }
            raise SelfHostError(
                "self_host_step_owner_dependency_cycle",
                json.dumps(blocked, sort_keys=True),
            )
        check_id = pending.pop(selected_index)
        ordered.append(check_id)
        available.add(str(check_index[check_id].get("execution_owner_id", "")))
    return tuple(ordered)


def _reopen_failed_steps_after_owner_input_change(
    run_root: Path,
    *,
    skill_root: Path,
    repository_root: Path,
    persistent_owner_root: Path,
    selected_steps: Sequence[Mapping[str, Any]],
    check_index: Mapping[str, Mapping[str, Any]],
    owner_rows: Mapping[str, Mapping[str, Any]],
    owner_receipts: dict[str, Mapping[str, Any]],
) -> tuple[str, ...]:
    """Reopen only failed/stale steps whose exact execution identity changed.

    An unchanged failure remains terminal, preventing automatic retry loops.
    A changed installation or other declared behavior input may reopen the
    step, after which the normal single-flight owner path decides reuse versus
    one new execution.
    """

    state = replay_run(run_root)
    selected_index = {
        str(step.get("step_id", "")): step for step in selected_steps
    }
    failed_records: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    checks_root = run_root / "checks"
    if checks_root.is_dir():
        for path in sorted(checks_root.glob("check-record-*.json")):
            record = load_check_result(run_root, path.stem)
            if record.get("status") == "passed":
                continue
            key = (str(record.get("step_id", "")), str(record.get("check_id", "")))
            failed_records.setdefault(key, []).append(record)
    reopened: list[str] = []
    for step_id, status in sorted(state.step_statuses.items()):
        if status not in {"failed", "stale"}:
            continue
        step = selected_index.get(step_id)
        if step is None:
            continue
        binding = step.get("binding", {}) if isinstance(step.get("binding"), Mapping) else {}
        ordered_check_ids = _order_step_checks_by_owner_dependencies(
            tuple(str(value) for value in binding.get("check_ids", [])),
            check_index=check_index,
            owner_rows=owner_rows,
            owner_receipts=owner_receipts,
        )
        identity_changed = False
        inspection_receipts = dict(owner_receipts)
        for check_id in ordered_check_ids:
            check = check_index.get(check_id)
            if check is None:
                continue
            owner_id = str(check.get("execution_owner_id", ""))
            owner_row = owner_rows.get(owner_id, {})
            dependency_ids = [
                str(value) for value in owner_row.get("depends_on_owner_ids", [])
            ]
            if any(value not in inspection_receipts for value in dependency_ids):
                break
            inspection = inspect_current_owner_execution(
                check,
                skill_root=skill_root,
                target_root=repository_root,
                repository_root=repository_root,
                run_root=run_root,
                owner_evidence_root=persistent_owner_root,
                dependency_execution_receipts={
                    value: inspection_receipts[value] for value in dependency_ids
                },
            )
            current_key = str(inspection.get("identity", {}).get("execution_key", ""))
            prior = failed_records.get((step_id, check_id), [])
            if prior and str(prior[-1].get("execution_key", "")) != current_key:
                identity_changed = True
            receipt = inspection.get("receipt")
            if isinstance(receipt, Mapping):
                inspection_receipts[owner_id] = receipt
        if identity_changed:
            reopen_step(
                run_root,
                step_id,
                "exact owner execution identity changed after the failed attempt",
            )
            reopened.append(step_id)
    return tuple(reopened)


def validate_self_host_test_mesh_boundary(
    repository_root: Path,
    manifest: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    """Require one native TestMesh test owner and forbid a nested TestMesh runner."""

    from .test_mesh import CURRENT_TEST_MESH_MANIFEST_SCHEMA

    repository_root = repository_root.resolve()
    mesh_path = (
        repository_root
        / ".agents"
        / "skills"
        / "skillguard"
        / "test-mesh.json"
    )
    if not mesh_path.is_file():
        raise SelfHostError(
            "self_host_test_mesh_manifest_missing",
            "required TestMesh manifest is unavailable",
        )
    mesh_manifest = _load_json(mesh_path)
    if mesh_manifest.get("schema_version") != CURRENT_TEST_MESH_MANIFEST_SCHEMA:
        raise SelfHostError(
            "self_host_test_mesh_manifest_not_current",
            "required TestMesh manifest does not use the current plan/aggregation schema",
        )
    checks = manifest.get("checks", [])
    if not isinstance(checks, list):
        raise SelfHostError(
            "self_host_check_manifest_invalid",
            "checks collection is not a list",
        )
    nested_wrapper_ids = []
    for check in checks:
        if not isinstance(check, Mapping):
            continue
        command_parts = [
            str(check.get("command", "")),
            *[str(value) for value in check.get("args", [])],
        ]
        if any(
            Path(value).name == "skillguard_test_mesh.py"
            for value in command_parts
        ):
            nested_wrapper_ids.append(str(check.get("check_id", "")))
    if nested_wrapper_ids:
        raise SelfHostError(
            "self_host_nested_test_mesh_execution_forbidden",
            ",".join(sorted(nested_wrapper_ids)),
        )
    owner_checks = [
        check
        for check in checks
        if isinstance(check, Mapping)
        and str(check.get("check_id", "")) == "check:self:test-mesh-fast"
    ]
    if len(owner_checks) != 1:
        raise SelfHostError(
            "self_host_test_mesh_native_owner_invalid",
            "expected exactly one native TestMesh test owner",
        )
    owner = owner_checks[0]
    record: dict[str, Any] = {
        "policy_id": "skillguard.self_host_test_mesh_boundary.current",
        "check_id": str(owner["check_id"]),
        "execution_owner_id": str(owner.get("execution_owner_id", "")),
        "mesh_manifest_hash": canonical_hash(mesh_manifest),
        "nested_wrapper_check_ids": [],
        "execution_mode": "native_owner_once_then_read_only_aggregation",
    }
    record["boundary_hash"] = canonical_hash(record)
    return (record,)


def validate_self_host_long_check_timeout_budgets(
    manifest: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    """Reject known long self-host checks whose exact command is under-budgeted."""

    checks = manifest.get("checks", [])
    if not isinstance(checks, list):
        raise SelfHostError(
            "self_host_check_manifest_invalid",
            "checks collection is not a list",
        )
    validated: list[Mapping[str, Any]] = []
    for check_id, policy in sorted(SELF_HOST_LONG_CHECK_TIMEOUT_POLICIES.items()):
        matching = [
            check
            for check in checks
            if isinstance(check, Mapping) and str(check.get("check_id", "")) == check_id
        ]
        if len(matching) != 1:
            code = (
                "self_host_long_check_missing"
                if not matching
                else "self_host_long_check_duplicate"
            )
            raise SelfHostError(code, f"{check_id}: expected exactly one declaration")
        check = matching[0]
        expected_kind = str(policy.get("kind", ""))
        expected_command = str(policy.get("command", ""))
        expected_args = [str(value) for value in policy.get("args", ())]
        actual_args = check.get("args", [])
        if (
            str(check.get("kind", "")) != expected_kind
            or str(check.get("command", "")) != expected_command
            or not isinstance(actual_args, list)
            or [str(value) for value in actual_args] != expected_args
        ):
            raise SelfHostError(
                "self_host_long_check_signature_mismatch",
                f"{check_id}: declaration no longer matches the measured command",
            )
        measured_value = policy.get("measured_elapsed_seconds")
        ceiling_value = policy.get("measured_ceiling_seconds")
        grace_value = policy.get("runtime_variance_grace_seconds")
        sample_values = policy.get("measurement_samples_seconds", ())
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or float(value) <= 0
            for value in (measured_value, ceiling_value, grace_value)
        ):
            raise SelfHostError(
                "self_host_long_check_policy_invalid",
                f"{check_id}: measured budget policy is not positive",
            )
        if (
            not isinstance(sample_values, (list, tuple))
            or not sample_values
            or any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or float(value) <= 0
                for value in sample_values
            )
        ):
            raise SelfHostError(
                "self_host_long_check_policy_invalid",
                f"{check_id}: measurement samples are not positive durations",
            )
        measurement_samples_seconds = [float(value) for value in sample_values]
        measured_seconds = float(measured_value)
        measured_ceiling_seconds = float(ceiling_value)
        runtime_variance_grace_seconds = float(grace_value)
        if (
            measured_seconds != max(measurement_samples_seconds)
            or measured_ceiling_seconds < measured_seconds
        ):
            raise SelfHostError(
                "self_host_long_check_policy_invalid",
                f"{check_id}: measured maximum or ceiling is inconsistent",
            )
        declared_value = check.get("timeout_seconds")
        if (
            isinstance(declared_value, bool)
            or not isinstance(declared_value, (int, float))
            or float(declared_value) <= 0
        ):
            raise SelfHostError(
                "self_host_long_check_timeout_invalid",
                f"{check_id}: timeout is not a positive duration",
            )
        declared_seconds = float(declared_value)
        required_seconds = measured_ceiling_seconds + runtime_variance_grace_seconds
        if declared_seconds <= required_seconds:
            raise SelfHostError(
                "self_host_long_check_timeout_not_dominant",
                (
                    f"{check_id}:declared={declared_seconds:g}:"
                    f"measured_ceiling={measured_ceiling_seconds:g}:"
                    f"runtime_variance_grace={runtime_variance_grace_seconds:g}"
                ),
            )
        policy_record: dict[str, Any] = {
            "check_id": check_id,
            "kind": expected_kind,
            "command": expected_command,
            "args": expected_args,
            "measurement_samples_seconds": measurement_samples_seconds,
            "measured_elapsed_seconds": measured_seconds,
            "measured_ceiling_seconds": measured_ceiling_seconds,
            "runtime_variance_grace_seconds": runtime_variance_grace_seconds,
            "required_timeout_seconds": required_seconds,
        }
        policy_record["policy_hash"] = canonical_hash(policy_record)
        budget_record: dict[str, Any] = {
            **policy_record,
            "declared_timeout_seconds": declared_seconds,
            "headroom_seconds": declared_seconds - required_seconds,
            "check_declaration_hash": canonical_hash(dict(check)),
        }
        budget_record["budget_hash"] = canonical_hash(budget_record)
        validated.append(budget_record)
    return tuple(validated)


def _self_host_claim_boundary(
    requested_profiles: Sequence[str],
    closures: Sequence[Mapping[str, Any]],
) -> str:
    """Project only the closure profiles that were requested and replay-verified."""

    requested = tuple(str(value) for value in requested_profiles)
    closed = tuple(str(row.get("profile", "")) for row in closures)
    if (
        not requested
        or any(not value for value in requested)
        or len(set(requested)) != len(requested)
        or requested != closed
    ):
        raise SelfHostError(
            "self_host_closure_profile_projection_mismatch",
            "requested and replay-verified closure profiles do not match exactly",
        )
    profile_text = ", ".join(requested)
    return (
        "This self-host result proves current local closure only for the "
        f"requested replay-verified profile(s): {profile_text}. "
        "It does not by itself prove an installation transaction, GitHub publication, "
        "external target skills, or future AI behavior."
    )


def _self_host_request(
    repository_root: Path,
    route_ids: Sequence[str],
) -> dict[str, Any]:
    """Build the self-host request with the same target identity as supervision."""

    target_input_paths = [".agents/skills/skillguard/SKILL.md"]
    target_inputs = fingerprint_target_inputs(
        repository_root,
        target_input_paths,
    )
    public_export_role_id = "repository.public_export_candidates"
    target_input_roles = fingerprint_target_input_roles(
        repository_root,
        {
            public_export_role_id: git_public_candidates(repository_root),
        },
    )
    return {
        "request": "SkillGuard current self-maintenance enforced verification",
        "route_ids": list(route_ids),
        "compose": True,
        "claim_scope": "enforced",
        "write_targets": [
            ".agents/skills/skillguard",
            ".flowguard/development_process_flow/skillguard_executable_contract_model.py",
            "tests",
        ],
        "target_input_paths": list(target_inputs["paths"]),
        "target_input_fingerprint": str(target_inputs["fingerprint"]),
        "target_input_roles": {
            role_id: list(inventory["paths"])
            for role_id, inventory in sorted(target_input_roles.items())
        },
    }


def run_current_verifier(
    repository_root: Path,
    *,
    profiles: Sequence[str] = ("enforced",),
    progress_callback: ProgressCallback | None = _stderr_progress,
    heartbeat_interval_seconds: float = 5.0,
    owner_evidence_root: Path | None = None,
) -> Mapping[str, Any]:
    repository_root = repository_root.resolve()
    persistent_owner_root = resolve_owner_evidence_root(
        repository_root,
        owner_evidence_root
        or repository_root / "work" / "verification" / "owner-evidence",
    )
    skill_root = repository_root / ".agents" / "skills" / "skillguard"
    compile_result = compile_skill_contract(skill_root, repository_root=repository_root, write=True)
    if not compile_result.ok or compile_result.compiled_contract is None or compile_result.check_manifest is None:
        raise SelfHostError("self_compile_failed", json.dumps(compile_result.to_dict(), sort_keys=True))
    contract = compile_result.compiled_contract
    manifest = compile_result.check_manifest
    test_mesh_boundary_checks = validate_self_host_test_mesh_boundary(
        repository_root,
        manifest,
    )
    long_check_timeout_budget_checks = validate_self_host_long_check_timeout_budgets(
        manifest,
    )
    route_ids = [str(row["route_id"]) for row in contract["routes"]]
    request = _self_host_request(repository_root, route_ids)
    target_input_paths = list(request["target_input_paths"])
    target_input_roles = {
        str(role_id): list(paths)
        for role_id, paths in request["target_input_roles"].items()
    }
    decision = select_routes(contract, request)
    if not decision.ok:
        raise SelfHostError("self_host_route_blocked", json.dumps(decision.to_dict(), sort_keys=True))
    claim = claim_run(
        contract,
        request,
        repository_root / "work" / "verification" / "skillguard-author-state",
        decision,
        check_manifest=manifest,
        guard_runtime_identity=guard_execution_runtime_fingerprint(),
    )
    if not claim.ok or claim.run_root is None:
        raise SelfHostError("self_host_claim_blocked", json.dumps(claim.to_dict(), sort_keys=True))
    run_root = claim.run_root
    fingerprints = _current_fingerprints(
        contract,
        repository_root=repository_root,
        target_input_paths=target_input_paths,
        target_input_roles=target_input_roles,
    )
    check_index = {
        str(row["check_id"]): row
        for row in manifest.get("checks", [])
        if isinstance(row, Mapping)
    }
    artifact_index = {
        str(row["artifact_id"]): row
        for row in contract.get("artifacts", [])
        if isinstance(row, Mapping)
    }
    selected_route_ids = set(decision.route_ids)
    selected_steps = [
        row
        for row in contract.get("steps", [])
        if isinstance(row, Mapping)
        and str(row.get("route_id", "")) in selected_route_ids
    ]
    total_checks = sum(
        len(
            row.get("binding", {}).get("check_ids", [])
            if isinstance(row.get("binding"), Mapping)
            else []
        )
        for row in selected_steps
    )
    completed_checks = 0
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
    _reopen_failed_steps_after_owner_input_change(
        run_root,
        skill_root=skill_root,
        repository_root=repository_root,
        persistent_owner_root=persistent_owner_root,
        selected_steps=selected_steps,
        check_index=check_index,
        owner_rows=owner_rows,
        owner_receipts=owner_receipts,
    )
    while True:
        ready = sorted(next_ready_steps(run_root), key=_step_sort_key)
        if not ready:
            break
        step = _select_ready_step_by_owner_dependencies(
            ready,
            check_index=check_index,
            owner_rows=owner_rows,
            owner_receipts=owner_receipts,
        )
        step_id = str(step["step_id"])
        begin_step(run_root, step_id)
        binding = step.get("binding", {}) if isinstance(step.get("binding"), Mapping) else {}
        check_records: list[Mapping[str, Any]] = []
        check_executions: list[Mapping[str, Any]] = []
        failures: list[str] = []
        ordered_check_ids = _order_step_checks_by_owner_dependencies(
            tuple(str(value) for value in binding.get("check_ids", [])),
            check_index=check_index,
            owner_rows=owner_rows,
            owner_receipts=owner_receipts,
        )
        for check_id in ordered_check_ids:
            check = check_index.get(str(check_id))
            if check is None:
                failures.append(f"missing check declaration: {check_id}")
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
                target_root=repository_root,
                repository_root=repository_root,
                run_root=run_root,
                step_id=step_id,
                owner_evidence_root=persistent_owner_root,
                dependency_execution_receipts=dependency_receipts,
                progress_context={
                    "step_id": step_id,
                    "completed_count": completed_checks,
                    "total_count": total_checks,
                },
                progress_callback=progress_callback,
                heartbeat_interval_seconds=heartbeat_interval_seconds,
            )
            completed_checks += 1
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
                # Stop at the first real owner failure.  Downstream owners in
                # the same step must not execute without the dependency receipt
                # that this failed owner was responsible for producing.
                break
        record_step(
            run_root,
            step_id,
            {
                "check_record_ids": [row["check_record_id"] for row in check_records],
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
                "native_action_summary": str(binding.get("action", {}).get("summary", "")),
            },
        )
        if failures:
            record_failure(run_root, step_id, "all declared checks pass", ";".join(failures), "self-host check failure")
            raise SelfHostError("self_host_step_failed", f"{step_id}: {';'.join(failures)}")
        artifact_records: list[Mapping[str, Any]] = []
        for artifact_id in binding.get("output_artifact_ids", []):
            declaration = artifact_index.get(str(artifact_id))
            if declaration is None:
                raise SelfHostError("self_host_artifact_declaration_missing", str(artifact_id))
            artifact_record = validate_artifact(
                run_root,
                repository_root,
                declaration,
                producer_step_id=step_id,
            )
            if artifact_record.get("status") != "passed":
                raise SelfHostError("self_host_artifact_failed", str(artifact_id))
            artifact_records.append(artifact_record)
        receipts: list[Mapping[str, Any]] = []
        for index, check_record in enumerate(check_records):
            evidence = hard_evidence_from_check(check_record)
            receipt = issue_receipt(
                run_root,
                step_id=step_id,
                evidence_class="hard",
                evidence=evidence,
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
            receipts.append(receipt)
        if not receipts:
            raise SelfHostError("self_host_step_without_receipt", step_id)
        primary_class = required_evidence_class(step)
        if primary_class == "judged":
            action = binding.get("action", {}) if isinstance(binding.get("action"), Mapping) else {}
            rubric_id = str(action.get("rubric_id", ""))
            rubrics = {
                str(row.get("rubric_id", "")): row
                for row in contract.get("judgment_rubrics", [])
                if isinstance(row, Mapping)
            }
            rubric = rubrics.get(rubric_id)
            if rubric is None:
                raise SelfHostError("self_host_judgment_rubric_missing", f"{step_id}:{rubric_id}")
            primary = issue_receipt(
                run_root,
                step_id=step_id,
                evidence_class="judged",
                evidence={
                    "rubric_id": str(rubric["rubric_id"]),
                    "rubric_version": str(rubric["version"]),
                    "evaluator_id": "skillguard-v2-self-review",
                    "input_fingerprint": fingerprint_value(
                        {
                            "check_record_ids": [row["check_record_id"] for row in check_records],
                            "artifact_record_ids": [row["artifact_record_id"] for row in artifact_records],
                        }
                    )["raw"],
                    "conclusion": "declared target-specific coverage criteria are satisfied",
                    "limitations": [str(rubric.get("claim_boundary", "self-review remains evaluator-bound"))],
                    "self_review": True,
                    "confidence_boundary": "Self-review remains evaluator-bound and cannot replace a required independent check.",
                    "check_id": str(check_records[0]["check_id"]),
                },
                decision="passed",
                verifier_id="skillguard-v2-self-review",
                input_fingerprints=fingerprints,
                artifact_record_ids=[str(row["artifact_record_id"]) for row in artifact_records],
                consumed_child_receipt_ids=[str(row["receipt_id"]) for row in receipts],
            )
            receipts.append(primary)
        elif primary_class == "hard":
            primary = receipts[0]
        else:
            raise SelfHostError("self_host_unsupported_primary_evidence", f"{step_id}:{primary_class}")
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
                "check_record_ids": [row["check_record_id"] for row in check_records],
                "check_execution_dispositions": [
                    str(row.get("disposition", "")) for row in check_executions
                ],
                "check_execution_receipt_ids": [
                    str(row["execution_receipt"]["receipt_id"])
                    for row in check_executions
                    if isinstance(row.get("execution_receipt"), Mapping)
                ],
                "receipt_ids": [row["receipt_id"] for row in receipts],
                "artifact_record_ids": [row["artifact_record_id"] for row in artifact_records],
            }
        )
    final_state = replay_run(run_root)
    unfinished = {
        step_id: status
        for step_id, status in final_state.step_statuses.items()
        if status != "passed"
    }
    if unfinished:
        raise SelfHostError("self_host_unfinished_steps", json.dumps(unfinished, sort_keys=True))
    depth_receipt: Mapping[str, Any] | None = None
    fingerprints = _current_fingerprints(
        contract,
        repository_root=repository_root,
        target_input_paths=target_input_paths,
        target_input_roles=target_input_roles,
    )
    if isinstance(contract.get("depth_profile"), Mapping):
        depth_receipt = issue_target_execution_receipt(
            run_root,
            contract,
            {
                "run_started": True,
            },
            current_fingerprints=fingerprints,
            repository_root=repository_root,
            target_root=repository_root,
            active_runtime_identity=guard_execution_runtime_fingerprint(),
        )
    closures: list[Mapping[str, Any]] = []
    for profile in profiles:
        evaluation, closure = close_run(
            run_root,
            profile=profile,
            current_fingerprints=fingerprints,
            target_root=repository_root,
            repository_root=repository_root,
        )
        if evaluation.status != "closed" or closure is None:
            raise SelfHostError("self_host_closure_failed", json.dumps(evaluation.to_dict(), sort_keys=True))
        verification = verify_closure(
            run_root,
            str(closure["closure_receipt_id"]),
            current_fingerprints=fingerprints,
            target_root=repository_root,
            repository_root=repository_root,
        )
        if not verification.get("ok"):
            raise SelfHostError("self_host_closure_replay_failed", json.dumps(verification, sort_keys=True))
        closures.append(
            {
                "profile": profile,
                "closure_receipt_id": closure["closure_receipt_id"],
                "closure_hash": closure["closure_hash"],
                "verification": verification,
            }
        )
    report: dict[str, Any] = {
        "schema_version": "skillguard.self_host_result.v2",
        "status": "passed",
        "run_id": claim.run_id,
        "run_root": run_root.relative_to(repository_root).as_posix(),
        "contract_hash": contract["contract_hash"],
        "manifest_hash": manifest["manifest_hash"],
        "executed_step_count": len(executed_steps),
        "executed_steps": executed_steps,
        "target_execution_depth_receipt": dict(depth_receipt) if depth_receipt is not None else None,
        "test_mesh_boundary_checks": list(test_mesh_boundary_checks),
        "long_check_timeout_budget_checks": list(long_check_timeout_budget_checks),
        "closures": closures,
        "created_at": utc_now(),
        "claim_boundary": _self_host_claim_boundary(profiles, closures),
    }
    report["report_hash"] = canonical_hash(report)
    _atomic_write(run_root / "self-host-result.json", report)
    return report


def run_self_host_bootstrap(
    repository_root: Path,
    *,
    profiles: Sequence[str] = ("enforced",),
    progress_callback: ProgressCallback | None = _stderr_progress,
    heartbeat_interval_seconds: float = 5.0,
) -> Mapping[str, Any]:
    return run_current_verifier(
        repository_root,
        profiles=profiles,
        progress_callback=progress_callback,
        heartbeat_interval_seconds=heartbeat_interval_seconds,
    )
