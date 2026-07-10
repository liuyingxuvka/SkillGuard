"""Generic claimed-run supervisor for any compiled SkillGuard V2 contract."""

from __future__ import annotations

import json
import os
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .artifact_validators import WITNESS_KINDS, validate_artifact
from .check_runner import execute_check, hard_evidence_from_check, store_check_result
from .closure import close_run, verify_closure
from .contract_compiler import canonical_hash, canonical_json_bytes, compile_skill_contract
from .evidence_policy import required_evidence_class
from .receipts import build_action_witness, fingerprint_value, issue_receipt, load_receipts
from .route_runtime import select_routes
from .runtime_fingerprint import guard_runtime_fingerprint
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


@dataclass(frozen=True)
class SupervisorError(RuntimeError):
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


_TOP_LEVEL_PACKET_FIELDS = frozenset({"request", "profiles", "steps"})
_REQUEST_PACKET_FIELDS = frozenset(
    {"route_ids", "function_ids", "compose", "request", "intent", "claim_scope", "write_targets"}
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
    profiles = packet.get("profiles", [request.get("claim_scope", "functional")])
    if isinstance(profiles, (str, bytes)) or not isinstance(profiles, Sequence):
        raise SupervisorError("packet_array_required", "$.profiles")
    steps_packet = _packet_object(packet.get("steps", {}), "$.steps")
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
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(canonical_json_bytes(payload))
    os.replace(temporary, path)


def _current_fingerprints(
    contract: Mapping[str, Any], request: Mapping[str, Any]
) -> Mapping[str, Mapping[str, str]]:
    sources = contract.get("source_fingerprints", {})
    implementation = {
        key: value
        for key, value in sources.items()
        if str(key).startswith("implementation:")
    }
    return {
        "guard_runtime": fingerprint_value(guard_runtime_fingerprint()),
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
) -> Mapping[str, Any]:
    """Compile, claim, execute, evidence, close, and replay one target-local run."""

    validate_supervisor_packet(packet)
    skill_root = skill_root.resolve()
    target_root = target_root.resolve()
    repository_root = repository_root.resolve()
    request = packet.get("request", {})
    if not isinstance(request, Mapping):
        raise SupervisorError("request_packet_invalid", "request must be an object")
    steps_packet = packet.get("steps", {})
    if not isinstance(steps_packet, Mapping):
        raise SupervisorError("steps_packet_invalid", "steps must be an object")
    profiles = tuple(str(item) for item in packet.get("profiles", [request.get("claim_scope", "functional")]))

    compiled = compile_skill_contract(skill_root, repository_root=repository_root, write=True)
    if not compiled.ok or compiled.compiled_contract is None or compiled.check_manifest is None:
        raise SupervisorError("contract_compile_failed", json.dumps(compiled.to_dict(), sort_keys=True))
    contract = compiled.compiled_contract
    manifest = compiled.check_manifest
    decision = select_routes(contract, request)
    if not decision.ok:
        raise SupervisorError("route_selection_blocked", json.dumps(decision.to_dict(), sort_keys=True))
    validate_supervisor_packet(packet, contract=contract, route_ids=decision.route_ids)
    guard_compatibility = guard_runtime_fingerprint()
    claim = claim_run(
        contract,
        request,
        target_root,
        decision,
        guard_compatibility=guard_compatibility,
    )
    if not claim.ok or claim.run_root is None:
        raise SupervisorError("run_claim_blocked", json.dumps(claim.to_dict(), sort_keys=True))
    run_root = claim.run_root
    fingerprints = _current_fingerprints(contract, request)
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
        failures: list[str] = []
        for check_id_value in binding.get("check_ids", []):
            check_id = str(check_id_value)
            check = check_index.get(check_id)
            if check is None:
                failures.append(f"missing check declaration:{check_id}")
                continue
            raw = execute_check(
                check,
                target_root=target_root,
                repository_root=repository_root,
                run_root=run_root,
            )
            record = store_check_result(run_root, step_id, raw)
            check_records.append(record)
            if raw.get("status") != "passed":
                failures.append(f"{check_id}:{raw.get('status')}:{raw.get('reason')}")
        record_step(
            run_root,
            step_id,
            {
                "check_record_ids": [str(row["check_record_id"]) for row in check_records],
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
    closures: list[Mapping[str, Any]] = []
    for profile in profiles:
        evaluation, closure = close_run(run_root, profile=profile, current_fingerprints=fingerprints)
        if evaluation.status != "closed" or closure is None:
            raise SupervisorError("closure_failed", json.dumps(evaluation.to_dict(), sort_keys=True))
        verification = verify_closure(
            run_root,
            str(closure["closure_receipt_id"]),
            current_fingerprints=fingerprints,
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
        "skill_id": str(contract.get("skill_id", "")),
        "run_id": str(claim.run_id),
        "run_root": run_root.as_posix(),
        "contract_hash": str(contract["contract_hash"]),
        "manifest_hash": str(manifest["manifest_hash"]),
        "route_ids": list(decision.route_ids),
        "executed_steps": executed_steps,
        "closures": closures,
        "created_at": utc_now(),
        "claim_boundary": (
            "This result proves only the selected routes, declared checks, supplied evaluator/witness packets, "
            "current artifacts, and replayed closure profiles for this exact target-local run."
        ),
    }
    report["report_hash"] = canonical_hash(report)
    _atomic_write(run_root / "supervisor-result.json", report)
    return report
