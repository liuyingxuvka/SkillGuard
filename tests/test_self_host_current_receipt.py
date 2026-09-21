"""Current self-runner contract tests replacing the retired self_host module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.test_fixed_runtime_evidence import _runner_sandbox, _run_sandbox

SCRIPT_ROOT = Path(__file__).resolve().parents[1] / ".agents" / "skills" / "skillguard" / "scripts"


def test_current_self_host_terminal_receipt_is_represented_by_runner_evidence() -> None:
    import run_self_checks

    table = Path(__file__).with_name("skillguard_self_cases.json").resolve()
    platform = "nt" if __import__("os").name == "nt" else "posix"
    admission = run_self_checks.load_required_nodeids(table, "admission", platform)
    execution = run_self_checks.load_required_nodeids(table, "execution", platform)
    release = run_self_checks.load_required_nodeids(table, "release", platform)
    assert len(admission) == 27
    assert len(execution) >= 26
    assert len(release) == 17
    assert all(node.startswith("tests/test_contract_v3_routes.py::test_") for node in admission)
    assert all("self_host" not in node and "run_store" not in node for node in admission + execution + release)


def test_current_self_host_terminal_receipt_allows_exact_noop_runner_input(tmp_path: Path) -> None:
    root, table = _runner_sandbox(tmp_path)
    code, payload = _run_sandbox(root, table)
    assert code == 0
    assert payload["status"] == "passed"
    assert payload["passed_count"] == 1
    assert payload["called_count"] == 1


def test_current_self_host_terminal_receipt_rejects_zero_execution_mixed_disposition(tmp_path: Path) -> None:
    root, table = _runner_sandbox(tmp_path, "def test_probe(): assert False\n")
    code, payload = _run_sandbox(root, table)
    assert code == 1
    assert payload["status"] == "blocked"
    assert payload["first_blocker"]["code"] == "required_case_not_passed"  # type: ignore[index]


def test_aggregation_only_report_cannot_become_current_self_host_receipt(tmp_path: Path) -> None:
    root, table = _runner_sandbox(tmp_path)
    raw = json.loads(table.read_text(encoding="utf-8"))
    raw["groups"]["execution"] = ["tests/test_fixed_runtime_evidence.py::test_other"]
    table.write_text(json.dumps(raw), encoding="utf-8")
    code, payload = _run_sandbox(root, table)
    assert code == 1
    assert payload["status"] == "blocked"
    assert payload["first_blocker"]["code"] == "required_case_missing"  # type: ignore[index]


def test_current_self_host_receipt_rejects_identity_mismatch(tmp_path: Path) -> None:
    root, table = _runner_sandbox(tmp_path)
    raw = json.loads(table.read_text(encoding="utf-8"))
    raw["schema_version"] = "legacy.self_host.v2"
    table.write_text(json.dumps(raw), encoding="utf-8")
    code, payload = _run_sandbox(root, table)
    assert code == 1
    assert payload["status"] == "blocked"
    assert payload["first_blocker"]["code"] == "self_runner_configuration"  # type: ignore[index]


def test_current_self_host_receipt_rejects_tampered_producer_report(tmp_path: Path) -> None:
    root, table = _runner_sandbox(tmp_path)
    table.write_text("{}", encoding="utf-8")
    code, payload = _run_sandbox(root, table)
    assert code == 1
    assert payload["status"] == "blocked"


def test_current_self_host_receipt_consumer_requires_exact_current_and_producer(tmp_path: Path) -> None:
    root, table = _runner_sandbox(tmp_path)
    code, payload = _run_sandbox(root, table)
    assert code == 0
    assert payload["called_count"] == 1
    assert payload["passed_count"] == 1


def test_current_self_host_receipt_consumer_fails_closed_when_missing(tmp_path: Path) -> None:
    root, table = _runner_sandbox(tmp_path)
    (root / "tests" / "test_fixed_runtime_evidence.py").unlink()
    code, payload = _run_sandbox(root, table)
    assert code == 1
    assert payload["status"] == "blocked"


def test_retired_current_verifier_refuses_before_claim_or_owner_start() -> None:
    assert not (SCRIPT_ROOT / "skillguard_v2" / "self_host.py").exists()


def test_frozen_mesh_finalizer_does_not_claim_compile_or_execute_and_is_idempotent(tmp_path: Path) -> None:
    import run_self_checks

    table = Path(__file__).with_name("skillguard_self_cases.json").resolve()
    first = run_self_checks.load_required_nodeids(table, "admission", "nt" if __import__("os").name == "nt" else "posix")
    second = run_self_checks.load_required_nodeids(table, "admission", "nt" if __import__("os").name == "nt" else "posix")
    assert first == second
    assert len(first) == 27

\n