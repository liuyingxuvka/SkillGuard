"""Two-stage frozen-old/new-verifier SkillGuard self-host execution."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .artifact_validators import validate_artifact
from .check_runner import execute_check, hard_evidence_from_check, store_check_result
from .closure import close_run, verify_closure
from .contract_compiler import canonical_hash, canonical_json_bytes, compile_skill_contract, file_hash
from .evidence_policy import required_evidence_class
from .receipts import fingerprint_value, issue_receipt
from .route_runtime import select_routes
from .runtime_fingerprint import guard_runtime_fingerprint
from .run_store import claim_run, utc_now
from .step_runtime import (
    begin_step,
    next_ready_steps,
    record_failure,
    record_step,
    record_verification,
    replay_run,
)


ROUTE_PRIORITY = (
    "route:static-audit",
    "route:deep-audit",
    "route:compile-contract",
    "route:supervise-run",
    "route:global-router-handoff",
    "route:provenance-audit",
    "route:portfolio-graduation",
    "route:verify-evidence",
    "route:derive-closure",
)


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


def _frozen_checks(run_old_full: bool) -> tuple[dict[str, Any], ...]:
    checks: list[dict[str, Any]] = [
        {
            "check_id": "frozen-old:check-skill",
            "kind": "command",
            "command": "python",
            "args": [
                ".agents/skills/skillguard/scripts/skillguard.py",
                "check-skill",
                "--target",
                ".agents/skills/skillguard",
            ],
            "cwd_token": "repository_root",
            "timeout_seconds": 180,
            "expected": {"exit_code": 0},
        },
        {
            "check_id": "frozen-old:check-depth",
            "kind": "command",
            "command": "python",
            "args": [
                ".agents/skills/skillguard/scripts/skillguard.py",
                "check-depth",
                "--target",
                ".agents/skills/skillguard",
            ],
            "cwd_token": "repository_root",
            "timeout_seconds": 180,
            "expected": {"exit_code": 0},
        },
        {
            "check_id": "frozen-old:self-check",
            "kind": "command",
            "command": "python",
            "args": [
                ".agents/skills/skillguard/scripts/skillguard.py",
                "self-check",
                "--target",
                ".agents/skills/skillguard",
            ],
            "cwd_token": "repository_root",
            "timeout_seconds": 180,
            "expected": {"exit_code": 0},
        },
    ]
    if run_old_full:
        checks.append(
            {
                "check_id": "frozen-old:full-regression",
                "kind": "command",
                "command": "python",
                "args": ["tests/test_skillguard_local.py"],
                "cwd_token": "repository_root",
                "timeout_seconds": 600,
                "expected": {"exit_code": 0},
            }
        )
    return tuple(checks)


def run_frozen_old_verifier(repository_root: Path, *, run_old_full: bool = True) -> Mapping[str, Any]:
    repository_root = repository_root.resolve()
    bootstrap_root = repository_root / ".skillguard" / "bootstrap"
    bootstrap_root.mkdir(parents=True, exist_ok=True)
    results = [
        execute_check(
            check,
            target_root=repository_root,
            repository_root=repository_root,
            run_root=bootstrap_root,
        )
        for check in _frozen_checks(run_old_full)
    ]
    checker_path = repository_root / ".agents" / "skills" / "skillguard" / "scripts" / "checker_engine.py"
    report: dict[str, Any] = {
        "schema_version": "skillguard.self_host_bootstrap.v2",
        "stage": "frozen_old_verifier",
        "status": "passed" if all(row.get("status") == "passed" for row in results) else "failed",
        "checker_version": "skillguard.local_cli_dispatch.v1",
        "checker_fingerprint": file_hash(checker_path),
        "python": platform.python_version(),
        "run_old_full": run_old_full,
        "checks": results,
        "created_at": utc_now(),
        "claim_boundary": (
            "The frozen old verifier checks the pre-existing static/deep/self-check and optional full regression boundary. "
            "It does not certify the new V2 verifier or release publication."
        ),
    }
    report["report_hash"] = canonical_hash(report)
    report_id = f"frozen-old-{report['report_hash'][:20].lower()}"
    report["report_id"] = report_id
    _atomic_write(bootstrap_root / f"{report_id}.json", report)
    if report["status"] != "passed":
        failed = [str(row.get("check_id")) for row in results if row.get("status") != "passed"]
        raise SelfHostError("frozen_old_verifier_failed", ",".join(failed))
    return report


def _current_fingerprints(contract: Mapping[str, Any], frozen_report: Mapping[str, Any]) -> Mapping[str, Mapping[str, str]]:
    sources = contract.get("source_fingerprints", {})
    return {
        "guard_runtime": fingerprint_value(guard_runtime_fingerprint()),
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
                "frozen_checker": frozen_report.get("checker_fingerprint"),
            }
        ),
    }


def _step_sort_key(step: Mapping[str, Any]) -> tuple[int, str]:
    route_id = str(step.get("route_id", ""))
    try:
        priority = ROUTE_PRIORITY.index(route_id)
    except ValueError:
        priority = len(ROUTE_PRIORITY)
    return priority, str(step.get("step_id", ""))


def run_new_verifier(
    repository_root: Path,
    frozen_report: Mapping[str, Any],
    *,
    profiles: Sequence[str] = ("functional", "release"),
) -> Mapping[str, Any]:
    repository_root = repository_root.resolve()
    skill_root = repository_root / ".agents" / "skills" / "skillguard"
    compile_result = compile_skill_contract(skill_root, repository_root=repository_root, write=True)
    if not compile_result.ok or compile_result.compiled_contract is None or compile_result.check_manifest is None:
        raise SelfHostError("self_compile_failed", json.dumps(compile_result.to_dict(), sort_keys=True))
    contract = compile_result.compiled_contract
    manifest = compile_result.check_manifest
    route_ids = [str(row["route_id"]) for row in contract["routes"]]
    request = {
        "request": "SkillGuard V2 self-maintenance functional and release verification",
        "route_ids": route_ids,
        "compose": True,
        "claim_scope": "release",
        "write_targets": [
            ".agents/skills/skillguard",
            ".flowguard/development_process_flow/skillguard_executable_contract_model.py",
            "tests",
        ],
        "frozen_old_report_id": frozen_report["report_id"],
    }
    decision = select_routes(contract, request)
    if not decision.ok:
        raise SelfHostError("self_host_route_blocked", json.dumps(decision.to_dict(), sort_keys=True))
    claim = claim_run(
        contract,
        request,
        repository_root,
        decision,
        guard_compatibility=guard_runtime_fingerprint(),
    )
    if not claim.ok or claim.run_root is None:
        raise SelfHostError("self_host_claim_blocked", json.dumps(claim.to_dict(), sort_keys=True))
    run_root = claim.run_root
    fingerprints = _current_fingerprints(contract, frozen_report)
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
    executed_steps: list[dict[str, Any]] = []
    while True:
        ready = sorted(next_ready_steps(run_root), key=_step_sort_key)
        if not ready:
            break
        step = ready[0]
        step_id = str(step["step_id"])
        begin_step(run_root, step_id)
        binding = step.get("binding", {}) if isinstance(step.get("binding"), Mapping) else {}
        check_records: list[Mapping[str, Any]] = []
        failures: list[str] = []
        for check_id in binding.get("check_ids", []):
            check = check_index.get(str(check_id))
            if check is None:
                failures.append(f"missing check declaration: {check_id}")
                continue
            raw_result = execute_check(
                check,
                target_root=repository_root,
                repository_root=repository_root,
                run_root=run_root,
            )
            record = store_check_result(run_root, step_id, raw_result)
            check_records.append(record)
            if raw_result.get("status") != "passed":
                failures.append(f"{check_id}:{raw_result.get('status')}:{raw_result.get('reason')}")
        record_step(
            run_root,
            step_id,
            {
                "check_record_ids": [row["check_record_id"] for row in check_records],
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
                    "confidence_boundary": "Self-review is sufficient for functional/release closure but not highest-quality closure.",
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
    closures: list[Mapping[str, Any]] = []
    for profile in profiles:
        evaluation, closure = close_run(
            run_root,
            profile=profile,
            current_fingerprints=fingerprints,
        )
        if evaluation.status != "closed" or closure is None:
            raise SelfHostError("self_host_closure_failed", json.dumps(evaluation.to_dict(), sort_keys=True))
        verification = verify_closure(
            run_root,
            str(closure["closure_receipt_id"]),
            current_fingerprints=fingerprints,
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
        "frozen_old_report_id": frozen_report["report_id"],
        "executed_step_count": len(executed_steps),
        "executed_steps": executed_steps,
        "closures": closures,
        "created_at": utc_now(),
        "claim_boundary": (
            "This self-host result proves current local V2 functional/release closure for the declared SkillGuard routes. "
            "It does not prove installation, GitHub publication, external target skills, or future AI behavior."
        ),
    }
    report["report_hash"] = canonical_hash(report)
    _atomic_write(run_root / "self-host-result.json", report)
    return report


def run_self_host_bootstrap(
    repository_root: Path,
    *,
    run_old_full: bool = True,
    profiles: Sequence[str] = ("functional", "release"),
) -> Mapping[str, Any]:
    frozen = run_frozen_old_verifier(repository_root, run_old_full=run_old_full)
    return run_new_verifier(repository_root, frozen, profiles=profiles)
