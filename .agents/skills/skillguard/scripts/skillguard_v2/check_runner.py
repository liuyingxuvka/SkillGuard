"""Controlled, shell-free native check execution with explicit non-run states."""

from __future__ import annotations

import hashlib
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .contract_compiler import canonical_hash
from .contract_compiler import canonical_json_bytes
from .run_store import load_contract_snapshot, load_run, utc_now


MAX_CAPTURE_BYTES = 256_000
SUPPORTED_CHECK_KINDS = frozenset({"command", "native", "model_assertion"})


@dataclass(frozen=True)
class CheckRunnerError(ValueError):
    code: str
    message: str
    check_id: str = ""

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def _under(path: Path, root: Path, code: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise CheckRunnerError(code, str(path)) from exc
    return resolved


def _resolve_cwd(
    token: str,
    *,
    target_root: Path,
    repository_root: Path,
    run_root: Path,
    relative: str = ".",
) -> Path:
    roots = {
        "target_root": target_root.resolve(),
        "repository_root": repository_root.resolve(),
        "run_root": run_root.resolve(),
    }
    if token not in roots:
        raise CheckRunnerError("cwd_token_unknown", token)
    relative_path = Path(relative)
    if relative_path.is_absolute():
        raise CheckRunnerError("cwd_relative_absolute", relative)
    return _under(roots[token] / relative_path, roots[token], "cwd_outside_token_root")


def _capture(value: bytes) -> tuple[str, str, bool]:
    digest = hashlib.sha256(value).hexdigest().upper()
    truncated = len(value) > MAX_CAPTURE_BYTES
    content = value[:MAX_CAPTURE_BYTES].decode("utf-8", errors="replace")
    return content, digest, truncated


def execute_check(
    check: Mapping[str, Any],
    *,
    target_root: Path,
    repository_root: Path,
    run_root: Path,
) -> Mapping[str, Any]:
    check_id = str(check.get("check_id") or check.get("id") or "")
    if not check_id:
        raise CheckRunnerError("check_id_missing", "check declaration needs check_id")
    kind = str(check.get("kind", ""))
    base: dict[str, Any] = {
        "check_id": check_id,
        "kind": kind,
        "covers_obligation_ids": list(check.get("covers_obligation_ids") or check.get("covers") or []),
        "created_at": utc_now(),
        "evidence_class": "hard",
    }
    if check.get("applicable") is False:
        return {
            **base,
            "status": "not_run",
            "reason": "declared_not_applicable",
            "executed": False,
            "claim_boundary": "A non-run check provides no passing evidence.",
        }
    if kind not in SUPPORTED_CHECK_KINDS:
        return {
            **base,
            "status": "not_run",
            "reason": "unsupported_check_kind",
            "executed": False,
            "claim_boundary": "Unsupported checks remain not-run and cannot pass.",
        }
    command = check.get("command")
    args = check.get("args", [])
    if not isinstance(command, str) or not command:
        raise CheckRunnerError("check_command_missing", "command is required", check_id)
    if not isinstance(args, list) or any(not isinstance(item, str) for item in args):
        raise CheckRunnerError("check_args_invalid", "args must be an array of strings", check_id)
    declared_args = list(args)
    argument_tokens = {
        "{{target_root}}": str(target_root.resolve()),
        "{{repository_root}}": str(repository_root.resolve()),
        "{{run_root}}": str(run_root.resolve()),
    }
    args = [argument_tokens.get(item, item) for item in args]
    cwd_token = str(check.get("cwd_token", "target_root"))
    cwd_relative = str(check.get("cwd_relative", "."))
    cwd = _resolve_cwd(
        cwd_token,
        target_root=target_root,
        repository_root=repository_root,
        run_root=run_root,
        relative=cwd_relative,
    )
    if not cwd.is_dir():
        return {
            **base,
            "status": "not_run",
            "reason": "cwd_missing",
            "executed": False,
            "cwd_token": cwd_token,
            "cwd_relative": cwd_relative,
            "claim_boundary": "Missing working directories are not passing executions.",
        }
    timeout = float(check.get("timeout_seconds", 30))
    if timeout <= 0 or timeout > 3600:
        raise CheckRunnerError("check_timeout_invalid", str(timeout), check_id)
    environment = os.environ.copy()
    declared_environment = check.get("environment", {})
    if declared_environment:
        if not isinstance(declared_environment, Mapping) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in declared_environment.items()
        ):
            raise CheckRunnerError("check_environment_invalid", "environment must map strings", check_id)
        environment.update(declared_environment)
    started = utc_now()
    try:
        completed = subprocess.run(
            [command, *args],
            cwd=cwd,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            shell=False,
            check=False,
        )
    except FileNotFoundError:
        return {
            **base,
            "status": "not_run",
            "reason": "executable_missing",
            "executed": False,
            "command": command,
            "args": args,
            "declared_args": declared_args,
            "cwd_token": cwd_token,
            "cwd_relative": cwd_relative,
            "claim_boundary": "A missing executable is a non-run, never a pass.",
        }
    except subprocess.TimeoutExpired as exc:
        stdout, stdout_hash, stdout_truncated = _capture(exc.stdout or b"")
        stderr, stderr_hash, stderr_truncated = _capture(exc.stderr or b"")
        return {
            **base,
            "status": "failed",
            "reason": "timeout",
            "executed": True,
            "command": command,
            "args": args,
            "declared_args": declared_args,
            "cwd_token": cwd_token,
            "cwd_relative": cwd_relative,
            "timeout_seconds": timeout,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_hash": stdout_hash,
            "stderr_hash": stderr_hash,
            "output_truncated": stdout_truncated or stderr_truncated,
            "started_at": started,
            "finished_at": utc_now(),
            "claim_boundary": "A timed-out execution is failed evidence.",
        }
    stdout, stdout_hash, stdout_truncated = _capture(completed.stdout)
    stderr, stderr_hash, stderr_truncated = _capture(completed.stderr)
    expected = check.get("expected", {})
    expected_exit = int(expected.get("exit_code", 0)) if isinstance(expected, Mapping) else 0
    status = "passed" if completed.returncode == expected_exit else "failed"
    result = {
        **base,
        "status": status,
        "reason": "expected_exit_observed" if status == "passed" else "unexpected_exit_code",
        "executed": True,
        "command": command,
        "args": args,
        "declared_args": declared_args,
        "cwd_token": cwd_token,
        "cwd_relative": cwd_relative,
        "timeout_seconds": timeout,
        "exit_code": completed.returncode,
        "expected_exit_code": expected_exit,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_hash": stdout_hash,
        "stderr_hash": stderr_hash,
        "output_truncated": stdout_truncated or stderr_truncated,
        "started_at": started,
        "finished_at": utc_now(),
        "claim_boundary": "This result covers only the exact declared shell-free execution.",
    }
    result["proof_fingerprint"] = canonical_hash(
        {
            "check_id": check_id,
            "command": command,
            "args": args,
            "declared_args": declared_args,
            "cwd_token": cwd_token,
            "cwd_relative": cwd_relative,
            "exit_code": completed.returncode,
            "stdout_hash": stdout_hash,
            "stderr_hash": stderr_hash,
        }
    )
    return result


def store_check_result(run_root: Path, step_id: str, result: Mapping[str, Any]) -> Mapping[str, Any]:
    run = load_run(run_root)
    contract = load_contract_snapshot(run_root)
    declared_steps = {
        str(row.get("step_id", ""))
        for row in contract.get("steps", [])
        if isinstance(row, Mapping)
    }
    if step_id not in declared_steps:
        raise CheckRunnerError("check_result_step_unknown", step_id, str(result.get("check_id", "")))
    record: dict[str, Any] = {
        "schema_version": "skillguard.check_result.v2",
        "run_id": str(run["run_id"]),
        "contract_hash": str(run["contract_hash"]),
        "step_id": step_id,
        "check_id": str(result.get("check_id", "")),
        "status": str(result.get("status", "")),
        "executed": bool(result.get("executed", False)),
        "proof_fingerprint": str(result.get("proof_fingerprint", "")),
        "result": dict(result),
        "created_at": utc_now(),
    }
    record_id_source = dict(record)
    record_id_source.pop("created_at", None)
    record["check_record_id"] = f"check-record-{canonical_hash(record_id_source)[:24].lower()}"
    record["record_hash"] = canonical_hash(record)
    root = run_root / "checks"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{record['check_record_id']}.json"
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError as exc:
        raise CheckRunnerError("check_record_collision", path.name, str(result.get("check_id", ""))) from exc
    try:
        os.write(descriptor, canonical_json_bytes(record))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return record


def load_check_result(run_root: Path, check_record_id: str) -> Mapping[str, Any]:
    path = run_root / "checks" / f"{check_record_id}.json"
    try:
        import json

        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CheckRunnerError("check_record_unreadable", type(exc).__name__, check_record_id) from exc
    if not isinstance(record, Mapping):
        raise CheckRunnerError("check_record_not_object", path.name, check_record_id)
    unsigned = dict(record)
    stored_hash = str(unsigned.pop("record_hash", ""))
    if not stored_hash or stored_hash != canonical_hash(unsigned):
        raise CheckRunnerError("check_record_hash_mismatch", path.name, check_record_id)
    if record.get("check_record_id") != check_record_id:
        raise CheckRunnerError("check_record_id_mismatch", path.name, check_record_id)
    return record


def hard_evidence_from_check(result: Mapping[str, Any]) -> Mapping[str, Any]:
    if result.get("status") != "passed" or not result.get("executed"):
        raise CheckRunnerError(
            "check_cannot_be_hard_evidence",
            str(result.get("status", "missing")),
            str(result.get("check_id", "")),
        )
    proof_fingerprint = str(result.get("proof_fingerprint", ""))
    if not proof_fingerprint:
        raise CheckRunnerError(
            "check_proof_fingerprint_missing",
            "passed check result lacks proof fingerprint",
            str(result.get("check_id", "")),
        )
    check_record_id = str(result.get("check_record_id", ""))
    check_record_hash = str(result.get("record_hash", ""))
    if not check_record_id or not check_record_hash:
        raise CheckRunnerError(
            "check_result_not_immutably_stored",
            "store the current check result before deriving hard evidence",
            str(result.get("check_id", "")),
        )
    return {
        "proof_kind": "native_check",
        "proof_fingerprint": proof_fingerprint,
        "check_id": str(result.get("check_id", "")),
        "check_record_id": check_record_id,
        "check_record_hash": check_record_hash,
        "exit_code": result.get("exit_code"),
        "stdout_hash": str(result.get("stdout_hash", "")),
        "stderr_hash": str(result.get("stderr_hash", "")),
        "claim_boundary": "This hard evidence covers only the exact declared check execution.",
    }
