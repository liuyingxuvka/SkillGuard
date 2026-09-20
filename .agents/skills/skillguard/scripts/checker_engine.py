"""Compact SkillGuard command surface.

The old checker catalogue was a platform layer.  The current public boundary
is intentionally small and explicit: read, change, and release.  The three
handlers share the same contract reader and never dispatch an old command by
alias.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping

from skillguard_utils import summarize_payload
from skillguard_v2.contract_compiler import compile_skill_contract
from skillguard_v2.route_runtime import select_routes
from skillguard_v2.run_store import (
    RunStoreError,
    accept_target_result,
    accepted_target_identity,
    load_accepted_target,
)
from skillguard_v2.wire_identity import atomic_write_json, wire_hash


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
    allowed = {"--root", "--request", "--expected-current", "--json"}
    values: dict[str, Any] = {"json": False}
    index = 0
    while index < len(argv):
        item = argv[index]
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
    if command in {"change", "release"} and "request" not in values:
        raise SkillGuardCliError(command, "--request is required")
    root = Path(str(values["root"])).expanduser().resolve()
    if not root.is_dir():
        raise SkillGuardCliError(command, f"root is not a directory: {root}", "missing_root")
    values["root"] = root
    return values


def _load_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SkillGuardCliError("read", f"cannot read JSON: {path}: {exc}", "invalid_json") from exc
    if not isinstance(value, Mapping):
        raise SkillGuardCliError("read", f"JSON object required: {path}", "invalid_json")
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
    if isinstance(requested, str) and requested:
        path = _under(root, requested)
        if path.is_file():
            return path
    default = root / ".skillguard" / "contract-source.json"
    if default.is_file():
        return default
    raise SkillGuardCliError("read", f"contract source is missing under {root}", "missing_contract")


def _read_contract(root: Path, request: Mapping[str, Any] | None) -> tuple[Path, Mapping[str, Any]]:
    path = _request_path(root, request)
    payload = _load_json(path)
    if payload.get("schema_version") != "skillguard.skill_contract.v3":
        raise SkillGuardCliError("read", "only skillguard.skill_contract.v3 is accepted", "unsupported_contract_schema")
    return path, payload


def _route_payload(contract: Mapping[str, Any], request: Mapping[str, Any]) -> tuple[bool, Mapping[str, Any]]:
    decision = select_routes(contract, request)
    if hasattr(decision, "to_dict"):
        payload = decision.to_dict()
    else:
        payload = dict(decision)
    return bool(getattr(decision, "ok", payload.get("ok", False))), payload


def _selected_check_ids(contract: Mapping[str, Any], route_payload: Mapping[str, Any]) -> list[str]:
    step_index = {str(row.get("step_id")): row for row in contract.get("steps", []) if isinstance(row, Mapping)}
    check_ids: list[str] = []
    for route_id in route_payload.get("route_ids", []):
        route = next((row for row in contract.get("routes", []) if str(row.get("route_id")) == str(route_id)), {})
        for step_id in route.get("step_ids", []):
            step = step_index.get(str(step_id), {})
            for check_id in step.get("check_ids", []):
                if str(check_id) not in check_ids:
                    check_ids.append(str(check_id))
    if not check_ids:
        for check in contract.get("checks", []):
            if isinstance(check, Mapping) and str(check.get("check_id", "")):
                check_ids.append(str(check["check_id"]))
    return check_ids


def _run_checks(root: Path, contract: Mapping[str, Any], check_ids: list[str]) -> tuple[list[dict[str, Any]], bool]:
    checks = {str(row.get("check_id")): row for row in contract.get("checks", []) if isinstance(row, Mapping)}
    results: list[dict[str, Any]] = []
    all_passed = True
    for check_id in check_ids:
        check = checks.get(check_id)
        if check is None:
            results.append({"check_id": check_id, "status": "BLOCKED", "reason": "unknown_check"})
            all_passed = False
            continue
        command = str(check.get("command", ""))
        args = check.get("args", [])
        if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
            results.append({"check_id": check_id, "status": "BLOCKED", "reason": "invalid_args"})
            all_passed = False
            continue
        if command in {"{{python}}", "python", "python3"}:
            executable = sys.executable
        else:
            executable = command
        if not executable or executable.startswith("{{"):
            results.append({"check_id": check_id, "status": "BLOCKED", "reason": "unresolved_command"})
            all_passed = False
            continue
        timeout = int(check.get("timeout_seconds", 300) or 300)
        expected = check.get("expected", {})
        expected_code = int(expected.get("exit_code", 0)) if isinstance(expected, Mapping) else 0
        started = time.monotonic()
        try:
            completed = subprocess.run(
                [executable, *args],
                cwd=root,
                env=dict(os.environ),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
                shell=False,
                check=False,
            )
            status = "PASS" if completed.returncode == expected_code else "FAIL"
            result: dict[str, Any] = {
                "check_id": check_id,
                "status": status,
                "returncode": completed.returncode,
                "expected_exit_code": expected_code,
                "duration_ms": int((time.monotonic() - started) * 1000),
            }
        except subprocess.TimeoutExpired:
            result = {"check_id": check_id, "status": "BLOCKED", "reason": "timeout", "timeout_seconds": timeout}
        except OSError as exc:
            result = {"check_id": check_id, "status": "FAIL", "reason": str(exc)}
        results.append(result)
        if result["status"] != "PASS":
            all_passed = False
    return results, all_passed


def _check_summary(check_ids: list[str], results: list[Mapping[str, Any]]) -> dict[str, int]:
    """Return stable counts for the bounded public decision summary."""

    return {
        "required_count": len(check_ids),
        "run_count": len(results),
        "passed_count": sum(1 for row in results if row.get("status") == "PASS"),
        "failed_count": sum(1 for row in results if row.get("status") == "FAIL"),
        "blocked_count": sum(1 for row in results if row.get("status") == "BLOCKED"),
        "reused_count": 0,
    }


def _failure_codes(results: list[Mapping[str, Any]]) -> list[str]:
    """Expose at most five stable blocker identifiers in the summary."""

    return [
        str(row.get("check_id") or row.get("reason") or "unknown")
        for row in results
        if row.get("status") != "PASS"
    ][:5]


def _author_state_root(request: Mapping[str, Any], command: str) -> Path:
    value = request.get("author_state_root")
    if not isinstance(value, str) or not value.strip() or value.startswith("REPLACE_WITH_"):
        raise SkillGuardCliError(command, "request.author_state_root must be an explicit absolute path")
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise SkillGuardCliError(command, f"author_state_root is not a directory: {path}", "missing_author_state_root")
    return path


def _load_accepted(state_root: Path, contract: Mapping[str, Any], command: str) -> Mapping[str, Any] | None:
    try:
        return load_accepted_target(state_root, contract)
    except RunStoreError as exc:
        raise SkillGuardCliError(command, str(exc), "accepted_target_invalid") from exc


def _current_accepted_id(state_root: Path, contract: Mapping[str, Any], command: str) -> str | None:
    value = _load_accepted(state_root, contract, command)
    return accepted_target_identity(value) if value is not None else None


def read(argv: list[str]) -> int:
    values = _parse("read", argv)
    root: Path = values["root"]
    request: Mapping[str, Any] | None = None
    if values.get("request"):
        request = _load_json(_under(root, str(values["request"])))
    path, contract = _read_contract(root, request)
    route_ok, route = _route_payload(contract, request or {"facts": {}, "claim_scope": "enforced"})
    state_root = _author_state_root(request or {}, "read")
    accepted_id = _current_accepted_id(state_root, contract, "read")
    payload = {
        "artifact_type": "skillguard_cli_result",
        "operation": "read",
        "status": "pass" if route_ok else "blocked",
        "decision": "pass" if route_ok else "block",
        "producer_count": 0,
        "root": str(root),
        "contract_path": str(path),
        "route": route,
        "accepted_id": accepted_id,
        "claim_boundary": "Read is side-effect free and never executes a producer.",
    }
    return _emit(payload)


def change(argv: list[str]) -> int:
    values = _parse("change", argv)
    root: Path = values["root"]
    request = _load_json(_under(root, str(values["request"])))
    path, contract = _read_contract(root, request)
    state_root = _author_state_root(request, "change")
    expected_current = values.get("expected_current", request.get("expected_current"))
    current = _current_accepted_id(state_root, contract, "change")
    if expected_current not in {None, "", "null"} and str(expected_current) != str(current):
        return _emit({
            "artifact_type": "skillguard_cli_result",
            "operation": "change",
            "status": "blocked",
            "decision": "block",
            "producer_count": 0,
            "reason": "accepted_current_conflict",
            "expected_current": expected_current,
            "current": current,
        })
    route_ok, route = _route_payload(contract, request)
    if not route_ok:
        return _emit({
            "artifact_type": "skillguard_cli_result",
            "operation": "change",
            "status": "blocked",
            "decision": "block",
            "producer_count": 0,
            "route": route,
        })
    check_ids = _selected_check_ids(contract, route)
    results, checks_ok = _run_checks(root, contract, check_ids)
    if not checks_ok:
        return _emit({
            "artifact_type": "skillguard_cli_result",
            "operation": "change",
            "command": "change",
            "status": "blocked",
            "decision": "block",
            "producer_count": len(results),
            **_check_summary(check_ids, results),
            "contract_path": str(path),
            "route": route,
            "checks": results,
            "blockers": _failure_codes(results),
            "claim_boundary": "Failed or unavailable checks prevent an accepted current result.",
        })
    observation_id = wire_hash({
        "contract_hash": wire_hash(contract),
        "route": route,
        "checks": results,
    })[7:]
    result_ref = f"observations/{observation_id}.result.json"
    input_snapshot_ref = f"observations/{observation_id}.inputs.json"
    result_payload = {
        "schema_version": "skillguard.change_result.v1",
        "operation": "change",
        "status": "pass",
        "target_id": str(request.get("target_id") or contract.get("skill_id")),
        "contract_hash": wire_hash(contract),
        "route": route,
        "check_summary": _check_summary(check_ids, results),
        "checks": results,
        "source_path": str(path),
    }
    input_payload = {
        "schema_version": "skillguard.input_snapshot.v1",
        "contract_hash": wire_hash(contract),
        "route": route,
        "input_ids": [str(row.get("id")) for row in contract.get("inputs", []) if isinstance(row, Mapping)],
    }
    atomic_write_json(state_root / result_ref, result_payload)
    atomic_write_json(state_root / input_snapshot_ref, input_payload)
    accepted = accept_target_result(
        state_root,
        contract,
        expected_current=(None if expected_current in {"", "null"} else expected_current),
        result_ref=result_ref,
        result_hash=wire_hash(result_payload),
        input_snapshot_ref=input_snapshot_ref,
        input_snapshot_hash=wire_hash(input_payload),
    )
    accepted_id = accepted_target_identity(accepted)
    return _emit({
        "artifact_type": "skillguard_cli_result",
        "operation": "change",
        "command": "change",
        "status": "pass",
        "decision": "pass",
        "producer_count": len(results),
        **_check_summary(check_ids, results),
        "accepted_id": accepted_id,
        "contract_path": str(path),
        "route": route,
        "checks": results,
        "full_report_path": str(state_root / result_ref),
        "claim_boundary": "This accepted result covers only the declared route and executed checks; it does not prove installation or publication.",
    })


def release(argv: list[str]) -> int:
    values = _parse("release", argv)
    root: Path = values["root"]
    request = _load_json(_under(root, str(values["request"])))
    _path, contract = _read_contract(root, request)
    state_root = _author_state_root(request, "release")
    accepted = _load_accepted(state_root, contract, "release")
    expected = values.get("expected_current", request.get("expected_current"))
    current = accepted_target_identity(accepted) if accepted is not None else None
    if not accepted or (expected not in {None, "", "null"} and str(expected) != str(current)):
        return _emit({
            "artifact_type": "skillguard_cli_result",
            "operation": "release",
            "status": "blocked",
            "decision": "block",
            "producer_count": 0,
            "reason": "accepted_result_missing_or_stale",
            "expected_current": expected,
            "current": current,
        })
    return _emit({
        "artifact_type": "skillguard_cli_result",
        "operation": "release",
        "status": "pass",
        "decision": "pass",
        "producer_count": 0,
        "accepted_id": current,
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
