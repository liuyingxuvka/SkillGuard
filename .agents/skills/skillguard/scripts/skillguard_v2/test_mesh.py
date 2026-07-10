"""Executable parent/child test mesh with current result artifacts."""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .contract_compiler import canonical_hash, canonical_json_bytes, file_hash
from .run_store import utc_now


TEST_MESH_SCHEMA = "skillguard.test_mesh_manifest.v1"
ProgressCallback = Callable[[Mapping[str, Any]], None]


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(canonical_json_bytes(payload))
    os.replace(temporary, path)


def _source_fingerprint(repository_root: Path, paths: Sequence[str]) -> str:
    rows = []
    for path_text in sorted(paths):
        path = (repository_root / path_text).resolve()
        if path.is_file():
            rows.append({"path": path_text, "sha256": file_hash(path)})
        elif path.is_dir():
            rows.extend(
                {
                    "path": item.relative_to(repository_root).as_posix(),
                    "sha256": file_hash(item),
                }
                for item in sorted(path.rglob("*.py"))
                if item.is_file() and "__pycache__" not in item.parts
            )
        else:
            rows.append({"path": path_text, "missing": True})
    return canonical_hash(rows)


def validate_test_mesh_manifest(manifest: Mapping[str, Any]) -> list[str]:
    findings: list[str] = []
    if manifest.get("schema_version") != TEST_MESH_SCHEMA:
        findings.append("manifest_schema_unsupported")
    suites = manifest.get("suites", [])
    profiles = manifest.get("profiles", [])
    partitions = manifest.get("partition_items", [])
    if not isinstance(suites, list) or not isinstance(profiles, list) or not isinstance(partitions, list):
        return findings + ["manifest_collections_invalid"]
    suite_index = {
        str(row.get("suite_id", "")): row
        for row in suites
        if isinstance(row, Mapping) and row.get("suite_id")
    }
    if len(suite_index) != len(suites):
        findings.append("suite_id_missing_or_duplicate")
    partition_owner: dict[str, str] = {}
    for row in partitions:
        if not isinstance(row, Mapping):
            findings.append("partition_row_invalid")
            continue
        partition_id = str(row.get("partition_id", ""))
        owner = str(row.get("owner_suite_id", ""))
        if not partition_id or not owner:
            findings.append("partition_owner_missing")
        elif partition_id in partition_owner:
            findings.append(f"partition_owner_duplicate:{partition_id}")
        elif owner not in suite_index:
            findings.append(f"partition_owner_unknown:{partition_id}:{owner}")
        partition_owner[partition_id] = owner
    for suite_id, suite in suite_index.items():
        commands = suite.get("commands", {})
        if not isinstance(commands, Mapping):
            findings.append(f"suite_commands_invalid:{suite_id}")
        timeout = suite.get("timeout_seconds", 0)
        if not isinstance(timeout, (int, float)) or timeout <= 0 or timeout > 3600:
            findings.append(f"suite_timeout_invalid:{suite_id}")
        if not suite.get("source_paths"):
            findings.append(f"suite_source_paths_missing:{suite_id}")
    for profile in profiles:
        if not isinstance(profile, Mapping):
            findings.append("profile_row_invalid")
            continue
        profile_id = str(profile.get("profile_id", ""))
        selected = [str(item) for item in profile.get("suite_ids", [])]
        for suite_id in selected:
            suite = suite_index.get(suite_id)
            if suite is None:
                findings.append(f"profile_suite_unknown:{profile_id}:{suite_id}")
            elif profile_id not in suite.get("commands", {}):
                findings.append(f"profile_suite_command_missing:{profile_id}:{suite_id}")
        selected_owners = set(selected)
        for partition_id in profile.get("required_partition_ids", []):
            owner = partition_owner.get(str(partition_id))
            if owner not in selected_owners:
                findings.append(f"profile_partition_unowned:{profile_id}:{partition_id}")
    return findings


def _terminate(process: subprocess.Popen[str]) -> None:
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _pytest_counts(output: str) -> tuple[int, int]:
    passed = sum(int(value) for value in re.findall(r"(\d+) passed", output))
    skipped = sum(int(value) for value in re.findall(r"(\d+) skipped", output))
    return passed, skipped


def execute_test_mesh(
    manifest_path: Path,
    repository_root: Path,
    profile_id: str,
    result_root: Path,
    *,
    cancel_file: Path | None = None,
    progress_interval_seconds: float = 5.0,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    repository_root = repository_root.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    findings = validate_test_mesh_manifest(manifest)
    profiles = {
        str(row.get("profile_id", "")): row
        for row in manifest.get("profiles", [])
        if isinstance(row, Mapping)
    }
    profile = profiles.get(profile_id)
    if profile is None:
        findings.append(f"profile_unknown:{profile_id}")
    if findings:
        return {
            "artifact_type": "skillguard_test_mesh_result",
            "status": "blocked",
            "profile_id": profile_id,
            "findings": findings,
            "child_results": [],
            "claim_boundary": "Manifest validation failed before child execution.",
        }
    suite_index = {str(row["suite_id"]): row for row in manifest["suites"]}
    child_results: list[dict[str, Any]] = []
    selected_ids = [str(item) for item in profile["suite_ids"]]
    stop_reason = ""
    for suite_id in selected_ids:
        suite = suite_index[suite_id]
        command = [str(item) for item in suite["commands"][profile_id]]
        timeout_seconds = float(suite["timeout_seconds"])
        started = time.monotonic()
        started_at = utc_now()
        status = "running"
        stdout = ""
        stderr = ""
        exit_code: int | None = None
        if cancel_file is not None and cancel_file.exists():
            status = "cancelled"
            stop_reason = "cancel_file_present"
        else:
            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stdout_file, tempfile.TemporaryFile(
                mode="w+", encoding="utf-8"
            ) as stderr_file:
                process = subprocess.Popen(
                    command,
                    cwd=repository_root,
                    text=True,
                    stdout=stdout_file,
                    stderr=stderr_file,
                )
                next_progress = started + max(progress_interval_seconds, 0.1)
                while process.poll() is None:
                    now = time.monotonic()
                    if cancel_file is not None and cancel_file.exists():
                        status = "cancelled"
                        stop_reason = "cancel_file_present"
                        _terminate(process)
                        break
                    if now - started >= timeout_seconds:
                        status = "timed_out"
                        stop_reason = "suite_timeout"
                        _terminate(process)
                        break
                    if progress_callback is not None and now >= next_progress:
                        progress_callback(
                            {
                                "event": "suite_progress",
                                "suite_id": suite_id,
                                "profile_id": profile_id,
                                "elapsed_seconds": round(now - started, 3),
                                "authority": "liveness_only",
                            }
                        )
                        next_progress = now + max(progress_interval_seconds, 0.1)
                    time.sleep(0.05)
                exit_code = process.returncode
                stdout_file.seek(0)
                stderr_file.seek(0)
                stdout = stdout_file.read()
                stderr = stderr_file.read()
            if status == "running":
                status = "passed" if exit_code == 0 else "failed"
                if status == "failed":
                    stop_reason = "child_failed"
        duration = round(time.monotonic() - started, 3)
        selected_count, skipped_count = _pytest_counts(f"{stdout}\n{stderr}")
        child = {
            "artifact_type": "skillguard_test_mesh_child_result",
            "suite_id": suite_id,
            "profile_id": profile_id,
            "status": status,
            "command": command,
            "command_fingerprint": canonical_hash(command),
            "source_fingerprint": _source_fingerprint(repository_root, suite["source_paths"]),
            "owned_partition_ids": list(suite.get("owned_partition_ids", [])),
            "started_at": started_at,
            "duration_seconds": duration,
            "timeout_seconds": timeout_seconds,
            "exit_code": exit_code,
            "selected_count": selected_count,
            "skipped_count": skipped_count,
            "stdout_tail": stdout[-4000:],
            "stderr_tail": stderr[-4000:],
            "proof_kind": "final_exit_and_captured_output",
            "progress_is_completion_evidence": False,
        }
        child["result_hash"] = canonical_hash(child)
        child_path = result_root / f"{profile_id}-{suite_id}-{child['result_hash'][:12].lower()}.json"
        child["result_path"] = child_path.relative_to(repository_root).as_posix() if child_path.is_relative_to(repository_root) else child_path.as_posix()
        _atomic_write(child_path, child)
        child_results.append(child)
        if status != "passed":
            break
    completed_ids = {str(row["suite_id"]) for row in child_results}
    for suite_id in selected_ids:
        if suite_id not in completed_ids:
            child_results.append(
                {
                    "suite_id": suite_id,
                    "profile_id": profile_id,
                    "status": "not_run",
                    "reason": stop_reason or "earlier_child_not_passed",
                    "progress_is_completion_evidence": False,
                }
            )
    status = "passed" if all(row.get("status") == "passed" for row in child_results) else "failed"
    report: dict[str, Any] = {
        "artifact_type": "skillguard_test_mesh_result",
        "schema_version": "skillguard.test_mesh_result.v1",
        "status": status,
        "profile_id": profile_id,
        "scope": profile["scope"],
        "child_results": child_results,
        "required_partition_ids": list(profile["required_partition_ids"]),
        "skipped_checks": [row for row in child_results if row.get("status") in {"not_run", "cancelled", "timed_out"}],
        "environment": {"python": platform.python_version(), "platform": platform.system()},
        "created_at": utc_now(),
        "claim_boundary": str(profile["claim_boundary"]),
    }
    report["report_hash"] = canonical_hash(report)
    report_path = result_root / f"{profile_id}-parent-{report['report_hash'][:12].lower()}.json"
    report["result_path"] = report_path.relative_to(repository_root).as_posix() if report_path.is_relative_to(repository_root) else report_path.as_posix()
    _atomic_write(report_path, report)
    return report
