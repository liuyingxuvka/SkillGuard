"""Compact SkillGuard command surface.

The old checker catalogue was a platform layer.  The current public boundary
is intentionally small and explicit: read, change, and release.  The three
handlers share the same contract reader and never dispatch an old command by
alias.
"""

from __future__ import annotations

import json
import hashlib
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from skillguard_utils import summarize_payload
from skillguard_v2.compact_contract import (
    ContractError,
    ValidatedContract,
    strict_json_load,
    validate_contract_source,
)
from skillguard_v2.consumer_distribution import audit_consumer_distribution
from skillguard_v2.compact_state import (
    control_root as compact_control_root,
    ensure_binding,
    load_accepted_observation,
    publish_acceptance,
)
from skillguard_v2.path_identity import canonical_filesystem_path
from skillguard_v2.route_runtime import RouteDecision, select_routes
from skillguard_v2.runtime_fingerprint import current_execution_runtime
from skillguard_v2.execution_records import (
    ExecutionRecordError,
    _portable_file_lock,
    attach_process_tree_containment,
    durable_write_immutable_json,
    filesystem_path,
    release_process_tree_containment,
)
from skillguard_v2.wire_identity import is_wire_hash, wire_hash


@dataclass(frozen=True)
class FrozenPlan:
    maintenance_unit_id: str
    skill_id: str
    author_root_identity: str
    operation: str
    route_ids: tuple[str, ...]
    step_ids: tuple[str, ...]
    obligation_checks: Mapping[str, tuple[str, ...]]
    check_order: tuple[str, ...]
    check_dependencies: Mapping[str, tuple[str, ...]]
    selected_input_ids: tuple[str, ...]
    plan_hash: str

    @property
    def required_checks(self) -> tuple[str, ...]:
        return self.check_order

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "skillguard.frozen_plan.v1",
            "maintenance_unit_id": self.maintenance_unit_id,
            "skill_id": self.skill_id,
            "author_root_identity": self.author_root_identity,
            "operation": self.operation,
            "route_ids": list(self.route_ids),
            "step_ids": list(self.step_ids),
            "obligation_checks": {key: list(value) for key, value in self.obligation_checks.items()},
            "check_order": list(self.check_order),
            "check_dependencies": {key: list(value) for key, value in self.check_dependencies.items()},
            "selected_input_ids": list(self.selected_input_ids),
        }


@dataclass(frozen=True)
class InputSnapshot:
    rows: tuple[Mapping[str, Any], ...]
    snapshot_hash: str


@dataclass(frozen=True)
class PlanExecutionResult:
    snapshot: InputSnapshot
    leaves: tuple[Mapping[str, Any], ...]
    producer_count: int
    run_count: int
    reused_count: int
    not_run_count: int


def _author_root_identity(root: Path) -> str:
    return os.path.normcase(str(canonical_filesystem_path(root)))


def observe_inputs(root: Path, validated: ValidatedContract, plan: FrozenPlan) -> InputSnapshot:
    """Read only selected inputs once per physical path and preserve missing identity."""

    cache: dict[Path, tuple[bool, str | None]] = {}
    rows: list[Mapping[str, Any]] = []
    root_identity = canonical_filesystem_path(root)
    for input_id in plan.selected_input_ids:
        declaration = validated.by_input[input_id]
        relative = Path(str(declaration["path"]))
        candidate = canonical_filesystem_path(root_identity / relative)
        try:
            candidate.relative_to(root_identity)
        except ValueError as exc:
            raise ContractError("input_path_outside_root", f"$.inputs.{input_id}", str(relative)) from exc
        if candidate not in cache:
            if candidate.exists():
                if not candidate.is_file():
                    raise ContractError("input_unreadable", f"$.inputs.{input_id}", "regular file required")
                cache[candidate] = (True, "sha256:" + hashlib.sha256(candidate.read_bytes()).hexdigest())
            else:
                cache[candidate] = (False, None)
        exists, digest = cache[candidate]
        if declaration["required"] and not exists:
            raise ContractError("input_missing", f"$.inputs.{input_id}", str(relative))
        rows.append({
            "id": input_id,
            "path": relative.as_posix(),
            "role": declaration.get("role"),
            "required": declaration["required"],
            "exists": exists,
            "sha256": digest,
        })
    payload = {
        "schema_version": "skillguard.input_snapshot.v2",
        "maintenance_unit_id": plan.maintenance_unit_id,
        "skill_id": plan.skill_id,
        "author_root_identity": _author_root_identity(root),
        "inputs": rows,
    }
    return InputSnapshot(tuple(rows), wire_hash(payload))


def _effective_environment(declared: Mapping[str, Any] | None) -> dict[str, str]:
    baseline = (
        ("SystemRoot", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP", "USERPROFILE", "HOMEDRIVE", "HOMEPATH")
        if os.name == "nt"
        else ("HOME", "TMPDIR", "LANG", "LC_ALL")
    )
    result = {key: os.environ[key] for key in (*baseline, "PATH") if key in os.environ}
    for key, value in (declared or {}).items():
        result[str(key)] = str(value)
    result["PYTHONDONTWRITEBYTECODE"] = "1"
    result["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    return result


def resolve_invocation(root: Path, check: Mapping[str, Any]) -> Mapping[str, Any]:
    command = str(check["command"])
    if command == "{{python}}":
        # Keep the exact interpreter spelling used by the launcher.  Windows
        # Store Python exposes a zero-byte app-execution alias here, so bind
        # the key to the package interpreter bytes under sys.prefix without
        # replacing the command that is actually executed.
        executable = Path(sys.executable)
        binary_identity_path = Path(sys.prefix) / ("python.exe" if os.name == "nt" else "bin/python")
        if not binary_identity_path.is_file():
            binary_identity_path = executable
        try:
            binary_bytes = binary_identity_path.read_bytes()
        except OSError as exc:
            raise ContractError("unresolved_command", "$.checks.command", "python interpreter bytes are unreadable") from exc
        is_python = True
    else:
        candidate = Path(command)
        if not candidate.is_absolute() or not candidate.is_file():
            raise ContractError("unresolved_command", "$.checks.command", "absolute existing executable required")
        executable = candidate
        is_python = os.path.normcase(str(candidate)) == os.path.normcase(sys.executable)
        binary_identity_path = (
            Path(sys.prefix) / ("python.exe" if os.name == "nt" else "bin/python")
            if is_python
            else candidate
        )
        try:
            binary_bytes = binary_identity_path.read_bytes()
        except OSError as exc:
            raise ContractError("unresolved_command", "$.checks.command", "executable bytes are unreadable") from exc
    environment = _effective_environment(check.get("environment") if isinstance(check.get("environment"), Mapping) else None)
    env_identity = {key: "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest() for key, value in sorted(environment.items())}
    return {
        "executable": str(executable),
        "binary_identity_path": str(binary_identity_path),
        "executable_sha256": "sha256:" + hashlib.sha256(binary_bytes).hexdigest(),
        "args": list(check["args"]),
        "cwd": _author_root_identity(root),
        "effective_environment": environment,
        "environment_identity": env_identity,
        "python_implementation": sys.implementation.name if is_python else None,
        "python_version": list(sys.version_info[:3]) if is_python else None,
        "sys_prefix": sys.prefix if is_python else None,
    }


def leaf_execution_key(
    root: Path,
    validated: ValidatedContract,
    plan: FrozenPlan,
    snapshot: InputSnapshot,
    check_id: str,
    dependency_execution_keys: Mapping[str, str],
) -> tuple[str, Mapping[str, Any]]:
    check = validated.by_check[check_id]
    row_index = {str(row["id"]): row for row in snapshot.rows}
    invocation = resolve_invocation(root, check)
    key_invocation = {key: value for key, value in invocation.items() if key != "effective_environment"}
    payload = {
        "schema_version": "skillguard.leaf_execution.v1",
        "maintenance_unit_id": plan.maintenance_unit_id,
        "skill_id": plan.skill_id,
        "author_root_identity": _author_root_identity(root),
        "check_id": check_id,
        "check_declaration": {key: check[key] for key in ("kind", "command", "args", "input_ids", "expected") if key in check} | ({"environment": check["environment"]} if "environment" in check else {}),
        "input_snapshot_rows": [row_index[input_id] for input_id in check["input_ids"]],
        "invocation": key_invocation,
        "execution_runtime": current_execution_runtime(Path(__file__).resolve().parent),
        "dependency_execution_keys": {key: dependency_execution_keys[key] for key in sorted(dependency_execution_keys)},
    }
    return wire_hash(payload), invocation


_LEAF_FIELDS = {
    "schema_version", "maintenance_unit_id", "skill_id", "author_root_identity",
    "check_id", "execution_key", "dependency_execution_keys", "status", "exit_code",
    "cleanup_confirmed", "stdout_ref", "stdout_hash", "stderr_ref", "stderr_hash",
}


def _hash_bytes(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _state_ref(control_root: Path, reference: Any, *, field: str) -> Path:
    if not isinstance(reference, str) or not reference or "\\" in reference:
        raise ContractError("evidence_invalid", field, "safe POSIX relative ref required")
    relative = Path(reference)
    if relative.is_absolute() or ".." in relative.parts:
        raise ContractError("evidence_invalid", field, "safe POSIX relative ref required")
    root_identity = canonical_filesystem_path(control_root)
    target = canonical_filesystem_path(root_identity / relative)
    try:
        target.relative_to(root_identity)
    except ValueError as exc:
        raise ContractError("evidence_invalid", field, "ref escapes control root") from exc
    return filesystem_path(target)


def _load_current_leaf(
    control_root: Path,
    leaf_path: Path,
    *,
    plan: FrozenPlan,
    check_id: str,
    execution_key: str,
    dependency_keys: Mapping[str, str],
) -> Mapping[str, Any]:
    try:
        leaf = strict_json_load(leaf_path)
    except ContractError as exc:
        raise ContractError("evidence_invalid", f"$.functions.{check_id}", exc.code) from exc
    if set(leaf) != _LEAF_FIELDS:
        raise ContractError("evidence_invalid", f"$.functions.{check_id}", "leaf field set mismatch")
    expected_identity = {
        "schema_version": "skillguard.leaf_result.v1",
        "maintenance_unit_id": plan.maintenance_unit_id,
        "skill_id": plan.skill_id,
        "author_root_identity": plan.to_dict().get("author_root_identity", _author_root_identity(Path.cwd())),
        "check_id": check_id,
        "execution_key": execution_key,
        "dependency_execution_keys": dict(dependency_keys),
        "status": "pass",
        "cleanup_confirmed": True,
    }
    # The caller separately compares root because old FrozenPlan objects do
    # not carry it yet; every other evidence identity is exact here.
    expected_identity.pop("author_root_identity")
    if any(leaf.get(key) != value for key, value in expected_identity.items()):
        raise ContractError("evidence_invalid", f"$.functions.{check_id}", "leaf identity mismatch")
    if not isinstance(leaf.get("author_root_identity"), str):
        raise ContractError("evidence_invalid", f"$.functions.{check_id}.author_root_identity", "invalid root identity")
    if isinstance(leaf.get("exit_code"), bool) or not isinstance(leaf.get("exit_code"), int):
        raise ContractError("evidence_invalid", f"$.functions.{check_id}.exit_code", "integer required")
    for stream in ("stdout", "stderr"):
        ref = _state_ref(control_root, leaf.get(f"{stream}_ref"), field=f"$.{stream}_ref")
        if not ref.is_file() or _hash_bytes(ref) != leaf.get(f"{stream}_hash"):
            raise ContractError("evidence_invalid", f"$.functions.{check_id}.{stream}", "stream missing or hash mismatch")
    return leaf


def execute_plan(
    root: Path,
    validated: ValidatedContract,
    plan: FrozenPlan,
    control_root: Path,
    *,
    lock_timeout_seconds: float = 0.0,
    preflight: Callable[[], None] | None = None,
    final_validation: Callable[[InputSnapshot], None] | None = None,
    on_success: Callable[[PlanExecutionResult], None] | None = None,
) -> PlanExecutionResult:
    """Execute or reuse each leaf under one target-wide single-flight lock."""

    if not control_root.is_absolute() or control_root == root or control_root in root.parents or root in control_root.parents:
        raise ContractError("invalid_state_root", "$.author_state_root", "separate absolute control root required")
    control_root.mkdir(parents=True, exist_ok=True)
    producer_count = 0
    try:
        lock = _portable_file_lock(control_root / "operation.lock", timeout_seconds=lock_timeout_seconds)
        with lock:
            if preflight is not None:
                preflight()
            # Observe after winning single-flight so the snapshot and all leaf
            # keys describe one frozen operation.
            snapshot = observe_inputs(root, validated, plan)
            leaves: list[Mapping[str, Any]] = []
            dependency_keys: dict[str, str] = {}
            reused_count = 0
            run_count = 0
            for index, check_id in enumerate(plan.check_order):
                declared_dependencies = {
                    dependency: dependency_keys[dependency]
                    for dependency in plan.check_dependencies[check_id]
                }
                execution_key, invocation = leaf_execution_key(
                    root, validated, plan, snapshot, check_id, declared_dependencies
                )
                leaf_path = filesystem_path(control_root / "functions" / f"{execution_key.removeprefix('sha256:')}.json")
                if leaf_path.exists():
                    leaf = _load_current_leaf(
                        control_root,
                        leaf_path,
                        plan=plan,
                        check_id=check_id,
                        execution_key=execution_key,
                        dependency_keys=declared_dependencies,
                    )
                    if leaf.get("author_root_identity") != _author_root_identity(root):
                        raise ContractError("evidence_invalid", f"$.functions.{check_id}", "foreign author root")
                    if leaf.get("exit_code") != validated.by_check[check_id]["expected"]["exit_code"]:
                        raise ContractError("evidence_invalid", f"$.functions.{check_id}.exit_code", "oracle mismatch")
                    leaves.append(leaf)
                    dependency_keys[check_id] = execution_key
                    reused_count += 1
                    continue

                attempt_root = control_root / "attempts" / uuid.uuid4().hex
                attempt_root.mkdir(parents=True, exist_ok=False)
                stdout_path, stderr_path = attempt_root / "stdout.bin", attempt_root / "stderr.bin"
                check = validated.by_check[check_id]
                creation: dict[str, Any] = {}
                if os.name != "nt":
                    creation["start_new_session"] = True
                try:
                    with stdout_path.open("xb") as stdout_handle, stderr_path.open("xb") as stderr_handle:
                        process = subprocess.Popen(
                            [str(invocation["executable"]), *[str(item) for item in invocation["args"]]],
                            cwd=root,
                            env=dict(invocation["effective_environment"]),
                            stdin=subprocess.DEVNULL,
                            stdout=stdout_handle,
                            stderr=stderr_handle,
                            shell=False,
                            **creation,
                        )
                        producer_count += 1
                        run_count += 1
                        containment = attach_process_tree_containment(process)
                        timed_out = False
                        try:
                            process.wait(timeout=float(check.get("timeout_seconds", 120.0)))
                        except subprocess.TimeoutExpired:
                            timed_out = True
                        cleanup = release_process_tree_containment(process, containment, timed_out=timed_out)
                except OSError as exc:
                    for attempt_file in (stdout_path, stderr_path):
                        try:
                            attempt_file.unlink()
                        except FileNotFoundError:
                            pass
                    try:
                        attempt_root.rmdir()
                    except OSError:
                        pass
                    raise ContractError("producer_launch_failed", f"$.checks.{check_id}", type(exc).__name__) from exc
                if timed_out:
                    raise ContractError("check_timeout", f"$.checks.{check_id}", "declared timeout elapsed")
                if not cleanup.get("cleanup_confirmed"):
                    raise ContractError("cleanup_unconfirmed", f"$.checks.{check_id}", str(cleanup.get("termination_error_kind", "unknown")))
                expected_exit = int(check["expected"]["exit_code"])
                if process.returncode != expected_exit:
                    raise ContractError("check_failed", f"$.checks.{check_id}", f"expected {expected_exit}, got {process.returncode}")
                stdout_ref = stdout_path.relative_to(control_root).as_posix()
                stderr_ref = stderr_path.relative_to(control_root).as_posix()
                leaf = {
                    "schema_version": "skillguard.leaf_result.v1",
                    "maintenance_unit_id": plan.maintenance_unit_id,
                    "skill_id": plan.skill_id,
                    "author_root_identity": _author_root_identity(root),
                    "check_id": check_id,
                    "execution_key": execution_key,
                    "dependency_execution_keys": declared_dependencies,
                    "status": "pass",
                    "exit_code": int(process.returncode),
                    "cleanup_confirmed": True,
                    "stdout_ref": stdout_ref,
                    "stdout_hash": _hash_bytes(stdout_path),
                    "stderr_ref": stderr_ref,
                    "stderr_hash": _hash_bytes(stderr_path),
                }
                try:
                    durable_write_immutable_json(leaf_path, leaf)
                except ExecutionRecordError as exc:
                    raise ContractError("evidence_cas_conflict", f"$.functions.{check_id}", str(exc)) from exc
                leaves.append(leaf)
                dependency_keys[check_id] = execution_key
            final_snapshot = observe_inputs(root, validated, plan)
            if final_snapshot.snapshot_hash != snapshot.snapshot_hash:
                raise ContractError("input_changed", "$.inputs", "selected input bytes changed during execution")
            if final_validation is not None:
                final_validation(final_snapshot)
            result = PlanExecutionResult(
                snapshot=snapshot,
                leaves=tuple(leaves),
                producer_count=producer_count,
                run_count=run_count,
                reused_count=reused_count,
                not_run_count=0,
            )
            if on_success is not None:
                on_success(result)
            return result
    except ExecutionRecordError as exc:
        if exc.code == "execution_record_lock_timeout":
            raise ContractError("target_busy", "$.author_state_root", "another execution owns the target") from exc
        raise ContractError("evidence_invalid", "$.author_state_root", str(exc)) from exc


def build_plan(validated: ValidatedContract, decision: RouteDecision, *, operation: str = "change", root: Path | None = None) -> FrozenPlan:
    """Expand selected routes through obligation owners and all step prerequisites."""

    if not decision.ok:
        raise ContractError("route_not_selected", "$.routes", "a successful route decision is required")
    if operation not in {"change", "release"}:
        raise ContractError("invalid_operation", "$.operation", "change or release required")
    plan_root = canonical_filesystem_path(root or Path.cwd())
    selected_steps: set[str] = set()
    selected_obligations: list[str] = []
    for route_id in decision.route_ids:
        route = validated.by_route[route_id]
        selected_steps.update(str(item) for item in route["step_ids"])
        for obligation_id in route["obligation_ids"]:
            value = str(obligation_id)
            if value not in selected_obligations:
                selected_obligations.append(value)
    obligation_checks: dict[str, tuple[str, ...]] = {}
    for obligation_id in selected_obligations:
        checks = tuple(str(item) for item in validated.by_obligation[obligation_id]["check_ids"])
        obligation_checks[obligation_id] = checks
        selected_steps.update(validated.check_owner_step[check_id] for check_id in checks)

    def add_requirements(step_id: str) -> None:
        for parent in validated.by_step[step_id]["requires"]:
            parent_id = str(parent)
            if parent_id not in selected_steps:
                selected_steps.add(parent_id)
                add_requirements(parent_id)

    for step_id in tuple(selected_steps):
        add_requirements(step_id)
    step_order = tuple(step_id for step_id in validated.step_topological_order if step_id in selected_steps)
    check_order = tuple(str(check_id) for step_id in step_order for check_id in validated.by_step[step_id]["check_ids"])
    if not check_order:
        raise ContractError("no_verification_obligation", "$.routes", "selected plan has no required checks")

    ancestors: dict[str, set[str]] = {}

    def step_ancestors(step_id: str) -> set[str]:
        if step_id in ancestors:
            return ancestors[step_id]
        result: set[str] = set()
        for parent in validated.by_step[step_id]["requires"]:
            parent_id = str(parent)
            result.add(parent_id)
            result.update(step_ancestors(parent_id))
        ancestors[step_id] = result
        return result

    dependencies: dict[str, tuple[str, ...]] = {}
    for check_id in check_order:
        owner = validated.check_owner_step[check_id]
        parent_steps = step_ancestors(owner)
        dependencies[check_id] = tuple(
            candidate for candidate in check_order if validated.check_owner_step[candidate] in parent_steps
        )
    selected_inputs: list[str] = []
    for check_id in check_order:
        for input_id in validated.by_check[check_id]["input_ids"]:
            value = str(input_id)
            if value not in selected_inputs:
                selected_inputs.append(value)
    payload = {
        "schema_version": "skillguard.frozen_plan.v1",
        "maintenance_unit_id": str(validated.source["maintenance_unit_id"]),
        "skill_id": str(validated.source["skill_id"]),
        "author_root_identity": _author_root_identity(plan_root),
        "operation": operation,
        "route_ids": list(decision.route_ids),
        "step_ids": list(step_order),
        "obligation_checks": {key: list(value) for key, value in obligation_checks.items()},
        "check_order": list(check_order),
        "check_dependencies": {key: list(value) for key, value in dependencies.items()},
        "selected_input_ids": selected_inputs,
    }
    return FrozenPlan(
        str(validated.source["maintenance_unit_id"]),
        str(validated.source["skill_id"]),
        _author_root_identity(plan_root),
        operation,
        decision.route_ids,
        step_order,
        obligation_checks,
        check_order,
        dependencies,
        tuple(selected_inputs),
        wire_hash(payload),
    )


class SkillGuardCliError(ValueError):
    def __init__(self, command: str, message: str, category: str = "invalid_request") -> None:
        super().__init__(message)
        self.command = command
        self.message = message
        self.category = category


def error_payload(command: str, message: str, category: str = "invalid_request") -> dict[str, Any]:
    return {
        "artifact_type": "skillguard_cli_result",
        "operation": command,
        "status": "blocked",
        "decision": "block",
        "producer_count": 0,
        "error": {"category": category, "message": message},
        "claim_boundary": "No producer was started by this rejected request.",
    }


def public_safe_exception_message(exc: BaseException) -> str:
    return str(exc) or exc.__class__.__name__


def _emit(payload: Mapping[str, Any]) -> int:
    """Emit only the bounded decision summary on the public CLI surface.

    The complete result remains in the explicit author-state observation when
    a change is accepted.  Keeping stdout as a projection prevents a large
    check/case expansion from becoming a second evidence source or from
    changing the reported denominator when the display is bounded.
    """

    summary = dict(payload)
    summary.setdefault("command", summary.get("operation", ""))
    print(json.dumps(summarize_payload(summary), ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload.get("status") == "pass" else 1


def _parse(command: str, argv: list[str]) -> dict[str, Any]:
    allowed = {"--root", "--request", "--json"}
    values: dict[str, Any] = {"json": False}
    seen: set[str] = set()
    index = 0
    while index < len(argv):
        item = argv[index]
        if item in seen:
            raise SkillGuardCliError(command, f"duplicate argument: {item}")
        seen.add(item)
        if item == "--json":
            values["json"] = True
            index += 1
            continue
        if item not in allowed:
            raise SkillGuardCliError(command, f"unsupported argument: {item}")
        if index + 1 >= len(argv) or argv[index + 1].startswith("--"):
            raise SkillGuardCliError(command, f"missing value for {item}")
        values[item[2:].replace("-", "_")] = argv[index + 1]
        index += 2
    if "root" not in values:
        raise SkillGuardCliError(command, "--root is required")
    if "request" not in values:
        raise SkillGuardCliError(command, "--request is required")
    raw_root = Path(str(values["root"]))
    if not raw_root.is_absolute():
        raise SkillGuardCliError(command, "--root must be absolute")
    root = raw_root.resolve()
    if not root.is_dir():
        raise SkillGuardCliError(command, f"root is not a directory: {root}", "missing_root")
    values["root"] = root
    return values


def _load_json(path: Path) -> Mapping[str, Any]:
    try:
        value = strict_json_load(path)
    except ContractError as exc:
        raise SkillGuardCliError("read", f"cannot read JSON: {path}: {exc}", "invalid_json") from exc
    return value


def _under(root: Path, value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise SkillGuardCliError("read", "request path must remain under --root", "path_boundary") from exc
    return resolved


def _request_path(root: Path, request: Mapping[str, Any] | None) -> Path:
    requested = request.get("contract_path") if request else None
    if not isinstance(requested, str) or not requested:
        raise SkillGuardCliError("read", "request.contract_path is required", "missing_contract")
    path = _under(root, requested)
    expected = (root / ".skillguard" / "contract-source.json").resolve()
    if path != expected or not path.is_file():
        raise SkillGuardCliError("read", "request.contract_path must name .skillguard/contract-source.json", "missing_contract")
    return path


def _read_contract(root: Path, request: Mapping[str, Any] | None) -> tuple[Path, Mapping[str, Any]]:
    path = _request_path(root, request)
    payload = _load_json(path)
    if payload.get("schema_version") != "skillguard.skill_contract.v3":
        raise SkillGuardCliError("read", "only skillguard.skill_contract.v3 is accepted", "unsupported_contract_schema")
    return path, payload


def _validate_request(operation: str, root: Path, request: Mapping[str, Any]) -> None:
    required = {"operation", "target_id", "scope", "contract_path", "author_state_root"}
    optional: set[str] = set()
    if operation in {"change", "release"}:
        required.update({"expected_current", "facts"})
        optional.update({"route_id", "route_ids"})
    if operation == "release":
        optional.add("artifact")
    unknown = sorted(set(request) - required - optional)
    missing = sorted(required - set(request))
    if unknown or missing:
        name = unknown[0] if unknown else missing[0]
        raise SkillGuardCliError(operation, f"request field invalid: {name}")
    if request.get("operation") != operation:
        raise SkillGuardCliError(operation, "request.operation mismatch")
    scope = request.get("scope")
    if not isinstance(scope, list) or not scope or not all(isinstance(item, str) and item and item == item.strip() for item in scope) or len(scope) != len(set(scope)):
        raise SkillGuardCliError(operation, "request.scope must be a unique non-empty route id array")
    if "route_id" in request and "route_ids" in request:
        raise SkillGuardCliError(operation, "route_id and route_ids cannot both be present")
    if operation in {"change", "release"}:
        expected = request.get("expected_current")
        if expected is not None and not is_wire_hash(expected):
            raise SkillGuardCliError(operation, "request.expected_current must be JSON null or a sha256 wire identity")
    state_value = request.get("author_state_root")
    if not isinstance(state_value, str) or not Path(state_value).is_absolute():
        raise SkillGuardCliError(operation, "request.author_state_root must be absolute")
    state_root = Path(state_value).resolve()
    if not state_root.is_dir() or state_root == root or root in state_root.parents or state_root in root.parents:
        raise SkillGuardCliError(operation, "request.author_state_root must be an existing separate directory")


def _route_payload(validated: ValidatedContract, request: Mapping[str, Any]) -> tuple[RouteDecision, Mapping[str, Any]]:
    explicit: str | list[str] | None = None
    if "route_id" in request:
        explicit = request["route_id"] if isinstance(request["route_id"], str) else []
    elif "route_ids" in request:
        explicit = request["route_ids"] if isinstance(request["route_ids"], list) else []
    decision = select_routes(validated, request.get("facts", {}), request.get("scope", []), explicit)
    return decision, decision.to_dict()


def _revalidate_selected_source(
    root: Path,
    contract_path: Path,
    request: Mapping[str, Any],
    initial: ValidatedContract,
    plan: FrozenPlan,
    operation: str,
) -> None:
    """Reject selected source drift without binding unrelated source wording."""

    try:
        current_source = strict_json_load(contract_path)
        current = validate_contract_source(root, current_source)
        decision, _ = _route_payload(current, request)
        if not decision.ok:
            raise ContractError("source_changed", "$.routes", "route selection changed during execution")
        current_plan = build_plan(current, decision, operation=operation, root=root)
    except ContractError as exc:
        if exc.code == "source_changed":
            raise
        raise ContractError("source_changed", exc.path, exc.code) from exc
    if current_plan.to_dict() != plan.to_dict():
        raise ContractError("source_changed", "$.routes", "selected plan changed during execution")
    functional_fields = ("kind", "command", "args", "input_ids", "expected", "environment")
    for check_id in plan.check_order:
        before = {key: initial.by_check[check_id].get(key) for key in functional_fields}
        after = {key: current.by_check[check_id].get(key) for key in functional_fields}
        if before != after:
            raise ContractError("source_changed", f"$.checks.{check_id}", "selected check changed during execution")
    for input_id in plan.selected_input_ids:
        if dict(initial.by_input[input_id]) != dict(current.by_input[input_id]):
            raise ContractError("source_changed", f"$.inputs.{input_id}", "selected input declaration changed during execution")


def _author_state_root(request: Mapping[str, Any], command: str) -> Path:
    value = request.get("author_state_root")
    if not isinstance(value, str) or not value.strip() or value.startswith("REPLACE_WITH_"):
        raise SkillGuardCliError(command, "request.author_state_root must be an explicit absolute path")
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise SkillGuardCliError(command, f"author_state_root is not a directory: {path}", "missing_author_state_root")
    return path


def _artifact_identity(root: Path, value: Any) -> Mapping[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping) or set(value) != {"path", "kind", "sha256"}:
        raise ContractError("artifact_invalid", "$.artifact", "exact path/kind/sha256 fields required")
    path_value, kind, requested_hash = value.get("path"), value.get("kind"), value.get("sha256")
    if not isinstance(path_value, str) or not path_value or "\\" in path_value:
        raise ContractError("artifact_invalid", "$.artifact.path", "safe POSIX relative path required")
    relative = Path(path_value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ContractError("artifact_invalid", "$.artifact.path", "safe POSIX relative path required")
    artifact_path = canonical_filesystem_path(root / relative)
    try:
        artifact_path.relative_to(canonical_filesystem_path(root))
    except ValueError as exc:
        raise ContractError("artifact_invalid", "$.artifact.path", "artifact escapes root") from exc
    if not isinstance(requested_hash, str) or len(requested_hash) != 64 or any(char not in "0123456789abcdef" for char in requested_hash):
        raise ContractError("artifact_invalid", "$.artifact.sha256", "bare lowercase sha256 required")
    if kind == "file":
        if not artifact_path.is_file():
            raise ContractError("artifact_missing", "$.artifact.path", path_value)
        actual = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    elif kind == "consumer_directory":
        if not artifact_path.is_dir():
            raise ContractError("artifact_missing", "$.artifact.path", path_value)
        audit = audit_consumer_distribution(artifact_path)
        if audit.get("status") != "passed":
            raise ContractError("artifact_invalid", "$.artifact.path", "consumer directory audit failed")
        manifest = audit.get("manifest")
        if not isinstance(manifest, Mapping) or not is_wire_hash(manifest.get("manifest_hash")):
            raise ContractError("artifact_invalid", "$.artifact.path", "consumer manifest identity missing")
        actual = str(manifest["manifest_hash"])[7:]
    else:
        raise ContractError("artifact_invalid", "$.artifact.kind", "file or consumer_directory required")
    if actual != requested_hash:
        raise ContractError("artifact_hash_mismatch", "$.artifact.sha256", "artifact differs from request")
    return {"path": relative.as_posix(), "kind": kind, "sha256": "sha256:" + actual}


def read(argv: list[str]) -> int:
    values = _parse("read", argv)
    root: Path = values["root"]
    request = _load_json(_under(root, str(values["request"])))
    _validate_request("read", root, request)
    path, contract = _read_contract(root, request)
    if request.get("target_id") != contract.get("skill_id"):
        raise SkillGuardCliError("read", "request.target_id does not match contract")
    if not isinstance(contract.get("maintenance_unit_id"), str) or not contract.get("maintenance_unit_id"):
        raise SkillGuardCliError("read", "live contract maintenance_unit_id is invalid", "invalid_contract_locator")
    state_root = _author_state_root(request, "read")
    try:
        observation = load_accepted_observation(
            state_root,
            root=root,
            maintenance_unit_id=str(contract["maintenance_unit_id"]),
            skill_id=str(contract["skill_id"]),
            scope=tuple(str(item) for item in request["scope"]),
        )
    except ContractError as exc:
        return _emit({
            "artifact_type": "skillguard_cli_result",
            "operation": "read",
            "status": "blocked",
            "decision": "block",
            "producer_count": 0,
            "reason": exc.code,
            "blockers": [exc.to_dict()],
            "claim_boundary": "Read verified only accepted immutable evidence and executed no producer.",
        })
    initialized = observation is not None
    incomplete = bool(observation and observation.missing_leaf_checks)
    payload = {
        "artifact_type": "skillguard_cli_result",
        "operation": "read",
        "status": "pass" if initialized and not incomplete else "blocked",
        "decision": "pass" if initialized and not incomplete else "block",
        "producer_count": 0,
        "root": str(root),
        "contract_path": str(path),
        "scope": list(request["scope"]),
        "accepted_id": observation.accepted_id if observation else None,
        "as_of_accepted": bool(observation),
        "reason": "qualification_incomplete" if incomplete else None if initialized else "uninitialized",
        "missing_leaf_checks": list(observation.missing_leaf_checks) if observation else [],
        "claim_boundary": "Read is side-effect free, uses accepted snapshots only, and never executes a producer.",
    }
    return _emit(payload)


def change(argv: list[str]) -> int:
    values = _parse("change", argv)
    root: Path = values["root"]
    request = _load_json(_under(root, str(values["request"])))
    _validate_request("change", root, request)
    path, contract = _read_contract(root, request)
    if request.get("target_id") != contract.get("skill_id"):
        raise SkillGuardCliError("change", "request.target_id does not match contract")
    validated = validate_contract_source(root, contract)
    state_root = _author_state_root(request, "change")
    expected_current = request.get("expected_current")
    decision, route = _route_payload(validated, request)
    if not decision.ok:
        return _emit({
            "artifact_type": "skillguard_cli_result",
            "operation": "change",
            "status": "blocked",
            "decision": "block",
            "producer_count": 0,
            "route": route,
        })
    try:
        plan = build_plan(validated, decision, operation="change", root=root)
    except ContractError as exc:
        return _emit({
            "artifact_type": "skillguard_cli_result",
            "operation": "change",
            "status": "blocked",
            "decision": "block",
            "producer_count": 0,
            "reason": exc.code,
        })
    check_ids = list(plan.check_order)
    target_state = compact_control_root(
        state_root, str(contract["maintenance_unit_id"]), str(contract["skill_id"])
    )
    accepted_result: dict[str, Any] = {}

    def preflight() -> None:
        current_observation = load_accepted_observation(
            state_root,
            root=root,
            maintenance_unit_id=str(contract["maintenance_unit_id"]),
            skill_id=str(contract["skill_id"]),
            scope=(),
        )
        current_id = current_observation.accepted_id if current_observation else None
        if expected_current != current_id:
            raise ContractError("accepted_current_conflict", "$.expected_current", f"expected {expected_current!r}, current {current_id!r}")
        ensure_binding(
            state_root,
            root=root,
            maintenance_unit_id=str(contract["maintenance_unit_id"]),
            skill_id=str(contract["skill_id"]),
        )

    def accept(execution: PlanExecutionResult) -> None:
        snapshot_payload = {
            "schema_version": "skillguard.input_snapshot.v2",
            "maintenance_unit_id": plan.maintenance_unit_id,
            "skill_id": plan.skill_id,
            "author_root_identity": _author_root_identity(root),
            "inputs": list(execution.snapshot.rows),
        }
        accepted, accepted_id, changed = publish_acceptance(
            state_root,
            root=root,
            contract=contract,
            plan=plan.to_dict(),
            input_snapshot=snapshot_payload,
            leaves=execution.leaves,
            expected_current=expected_current,
        )
        accepted_result.update({"accepted": accepted, "accepted_id": accepted_id, "changed": changed})

    before_attempts = len(list((target_state / "attempts").glob("*"))) if (target_state / "attempts").is_dir() else 0
    try:
        execution = execute_plan(
            root,
            validated,
            plan,
            target_state,
            preflight=preflight,
            final_validation=lambda _snapshot: _revalidate_selected_source(
                root, path, request, validated, plan, "change"
            ),
            on_success=accept,
        )
    except ContractError as exc:
        after_attempts = len(list((target_state / "attempts").glob("*"))) if (target_state / "attempts").is_dir() else before_attempts
        producers = max(0, after_attempts - before_attempts)
        return _emit({
            "artifact_type": "skillguard_cli_result",
            "operation": "change",
            "status": "blocked",
            "decision": "block",
            "producer_count": producers,
            "required_count": len(check_ids),
            "run_count": producers,
            "reused_count": 0,
            "not_run_count": max(0, len(check_ids) - producers),
            "reason": exc.code,
            "blockers": [exc.to_dict()],
            "claim_boundary": "A blocked execution did not update accepted current.",
        })
    accepted_id = str(accepted_result["accepted_id"])
    return _emit({
        "artifact_type": "skillguard_cli_result",
        "operation": "change",
        "command": "change",
        "status": "pass",
        "decision": "pass",
        "producer_count": execution.producer_count,
        "required_count": len(check_ids),
        "run_count": execution.run_count,
        "passed_count": len(check_ids),
        "failed_count": 0,
        "blocked_count": 0,
        "reused_count": execution.reused_count,
        "not_run_count": execution.not_run_count,
        "accepted_id": accepted_id,
        "contract_path": str(path),
        "route": route,
        "generation": accepted_result["accepted"]["generation"],
        "accepted_changed": accepted_result["changed"],
        "claim_boundary": "This accepted result covers only the declared route and executed checks; it does not prove installation or publication.",
    })


def release(argv: list[str]) -> int:
    values = _parse("release", argv)
    root: Path = values["root"]
    request = _load_json(_under(root, str(values["request"])))
    _validate_request("release", root, request)
    path, contract = _read_contract(root, request)
    if request.get("target_id") != contract.get("skill_id"):
        raise SkillGuardCliError("release", "request.target_id does not match contract")
    validated = validate_contract_source(root, contract)
    decision, route = _route_payload(validated, request)
    if not decision.ok:
        return _emit({
            "artifact_type": "skillguard_cli_result",
            "operation": "release",
            "status": "blocked",
            "decision": "block",
            "producer_count": 0,
            "route": route,
        })
    try:
        plan = build_plan(validated, decision, operation="release", root=root)
    except ContractError as exc:
        return _emit({
            "artifact_type": "skillguard_cli_result",
            "operation": "release",
            "status": "blocked",
            "decision": "block",
            "producer_count": 0,
            "reason": exc.code,
        })
    state_root = _author_state_root(request, "release")
    expected = request.get("expected_current")
    try:
        artifact_identity = _artifact_identity(root, request.get("artifact"))
    except ContractError as exc:
        return _emit({
            "artifact_type": "skillguard_cli_result",
            "operation": "release",
            "status": "blocked",
            "decision": "block",
            "producer_count": 0,
            "reason": exc.code,
            "blockers": [exc.to_dict()],
        })
    target_state = compact_control_root(
        state_root, str(contract["maintenance_unit_id"]), str(contract["skill_id"])
    )
    accepted_result: dict[str, Any] = {}

    def preflight() -> None:
        current_observation = load_accepted_observation(
            state_root,
            root=root,
            maintenance_unit_id=str(contract["maintenance_unit_id"]),
            skill_id=str(contract["skill_id"]),
            scope=(),
        )
        if current_observation is None:
            raise ContractError("accepted_result_missing", "$.current", "release requires accepted current")
        if expected != current_observation.accepted_id:
            raise ContractError("accepted_current_conflict", "$.expected_current", f"expected {expected!r}, current {current_observation.accepted_id!r}")

    def accept(execution: PlanExecutionResult) -> None:
        final_artifact = _artifact_identity(root, request.get("artifact"))
        if final_artifact != artifact_identity:
            raise ContractError("artifact_changed", "$.artifact", "artifact identity changed during validation")
        snapshot_payload = {
            "schema_version": "skillguard.input_snapshot.v2",
            "maintenance_unit_id": plan.maintenance_unit_id,
            "skill_id": plan.skill_id,
            "author_root_identity": _author_root_identity(root),
            "inputs": list(execution.snapshot.rows),
        }
        accepted, accepted_id, changed = publish_acceptance(
            state_root,
            root=root,
            contract=contract,
            plan=plan.to_dict(),
            input_snapshot=snapshot_payload,
            leaves=execution.leaves,
            expected_current=expected,
            qualification="source_and_artifact" if final_artifact is not None else "source_qualification_only",
            artifact=final_artifact,
        )
        accepted_result.update({"accepted": accepted, "accepted_id": accepted_id, "changed": changed})

    before_attempts = len(list((target_state / "attempts").glob("*"))) if (target_state / "attempts").is_dir() else 0
    try:
        execution = execute_plan(
            root,
            validated,
            plan,
            target_state,
            preflight=preflight,
            final_validation=lambda _snapshot: _revalidate_selected_source(
                root, path, request, validated, plan, "release"
            ),
            on_success=accept,
        )
    except ContractError as exc:
        after_attempts = len(list((target_state / "attempts").glob("*"))) if (target_state / "attempts").is_dir() else before_attempts
        producers = max(0, after_attempts - before_attempts)
        return _emit({
            "artifact_type": "skillguard_cli_result",
            "operation": "release",
            "status": "blocked",
            "decision": "block",
            "producer_count": producers,
            "required_count": len(plan.check_order),
            "run_count": producers,
            "reused_count": 0,
            "not_run_count": max(0, len(plan.check_order) - producers),
            "reason": exc.code,
            "blockers": [exc.to_dict()],
        })
    return _emit({
        "artifact_type": "skillguard_cli_result",
        "operation": "release",
        "status": "pass",
        "decision": "pass",
        "producer_count": execution.producer_count,
        "required_count": len(plan.check_order),
        "run_count": execution.run_count,
        "reused_count": execution.reused_count,
        "not_run_count": execution.not_run_count,
        "accepted_id": accepted_result["accepted_id"],
        "generation": accepted_result["accepted"]["generation"],
        "accepted_changed": accepted_result["changed"],
        "artifact": request.get("artifact"),
        "install": bool(request.get("install", False)),
        "claim_boundary": "Release verifies an accepted current result and produces no source mutation; installation and Git publication remain separate transactions.",
    })


def commands(argv: list[str] | None = None) -> int:
    if argv and any(item not in {"--json"} for item in argv):
        raise SkillGuardCliError("help", "unsupported help argument")
    print(json.dumps({
        "usage": "skillguard.py {read,change,release} --root ROOT [--request REQUEST] [--json]",
        "operations": ["read", "change", "release"],
        "claim_boundary": "Only these three operations are public; legacy commands and profiles are rejected.",
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


COMMANDS = {"read": read, "change": change, "release": release}


__all__ = [
    "COMMANDS",
    "SkillGuardCliError",
    "commands",
    "error_payload",
    "public_safe_exception_message",
]
