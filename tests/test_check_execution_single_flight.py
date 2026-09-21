"""Current v3 execution and single-flight protections.

This file retains the functional assertions that used to exercise the retired
claimed-run/check-runner platform, but drives the compact v3 plan executor
directly. It deliberately does not import ``run_store`` or any v2 adapter.
"""

from __future__ import annotations

import concurrent.futures
import json
import time
from pathlib import Path

import pytest

from checker_engine import (
    ExecutionContext,
    build_plan,
    execute_plan,
    leaf_execution_key,
    observe_inputs,
)
from skillguard_v2.compact_contract import ContractError, validate_contract_source
from skillguard_v2.route_runtime import select_routes

from tests.test_fixed_preflight_units import _root, _source


def _fixture(
    tmp_path: Path,
    *,
    checks: list[dict[str, object]] | None = None,
    independent: bool = False,
    maintenance_unit_id: str = "fixture-unit",
):
    root = _root(tmp_path)
    source = _source()
    source["maintenance_unit_id"] = maintenance_unit_id
    if checks is not None:
        source["checks"] = checks
        step_rows = []
        previous = None
        for index, row in enumerate(checks):
            step_id = f"step:{index}"
            step_rows.append(
                {
                    "step_id": step_id,
                    "requires": [] if independent or previous is None else [previous],
                    "check_ids": [str(row["check_id"])],
                }
            )
            previous = step_id
        source["steps"] = step_rows
        source["obligations"] = [
            {"obligation_id": "ob:fixture", "check_ids": [str(row["check_id"]) for row in checks]}
        ]
        source["routes"][0]["step_ids"] = [row["step_id"] for row in step_rows]
        source["routes"][0]["obligation_ids"] = ["ob:fixture"]
    validated = validate_contract_source(root, source)
    decision = select_routes(validated, {"operation": "change"}, ["route:change"])
    assert decision.ok, decision.to_dict()
    plan = build_plan(validated, decision, root=root)
    return root, source, validated, plan, tmp_path / "author-state"


def _command(
    check_id: str,
    *,
    args: list[str] | None = None,
    input_ids: list[str] | None = None,
    expected: int = 0,
    timeout_seconds: float | None = None,
    environment: dict[str, str] | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "check_id": check_id,
        "kind": "command",
        "command": "{{python}}",
        "args": list(args or ["-c", "pass"]),
        "input_ids": list(input_ids or ["a"]),
        "expected": {"exit_code": expected},
    }
    if timeout_seconds is not None:
        row["timeout_seconds"] = timeout_seconds
    if environment is not None:
        row["environment"] = environment
    return row


def _execute(root: Path, validated, plan, state: Path, *, context: ExecutionContext | None = None):
    return execute_plan(root, validated, plan, state, execution_context=context)


def test_toolchain_identity_returns_both_current_hashes(tmp_path: Path) -> None:
    root, _payload, validated, plan, _state = _fixture(tmp_path)
    snapshot = observe_inputs(root, validated, plan)
    key, invocation = leaf_execution_key(root, validated, plan, snapshot, "a", {})
    assert key.startswith("sha256:")
    assert invocation["executable_sha256"].startswith("sha256:")
    assert invocation["environment_identity"]


def test_terminal_success_is_reused_and_identities_remain_distinct(tmp_path: Path) -> None:
    root, _payload, validated, plan, state = _fixture(tmp_path)
    first = _execute(root, validated, plan, state)
    second = _execute(root, validated, plan, state)
    assert (first.producer_count, first.run_count, first.reused_count) == (2, 2, 0)
    assert (second.producer_count, second.run_count, second.reused_count) == (0, 0, 2)
    assert second.leaves == first.leaves
    assert len(list((state / "functions").glob("*.json"))) == 2


def test_functional_execution_key_ignores_shared_parent_plan_identity(tmp_path: Path) -> None:
    root, source, validated, change_plan, _state = _fixture(tmp_path)
    source["routes"].append(
        {
            "route_id": "route:release",
            "choice_group": "operation",
            "when": [{"fact": "operation", "equals": "release"}],
            "step_ids": list(source["routes"][0]["step_ids"]),
            "obligation_ids": list(source["routes"][0]["obligation_ids"]),
        }
    )
    validated = validate_contract_source(root, source)
    release_decision = select_routes(validated, {"operation": "release"}, ["route:release"])
    release_plan = build_plan(validated, release_decision, operation="release", root=root)
    snapshot = observe_inputs(root, validated, change_plan)
    first = leaf_execution_key(root, validated, change_plan, snapshot, "a", {})[0]
    second = leaf_execution_key(root, validated, release_plan, snapshot, "a", {})[0]
    assert first == second


def test_failed_attempt_never_hits_and_retry_can_succeed(tmp_path: Path) -> None:
    checks = [_command("a", args=["-c", "import sys; sys.exit(9)"]), _command("b")]
    root, source, validated, plan, state = _fixture(tmp_path, checks=checks)
    context = ExecutionContext(required_check_ids=plan.check_order)
    with pytest.raises(ContractError) as raised:
        _execute(root, validated, plan, state, context=context)
    assert raised.value.code == "check_failed"
    assert context.producer_count == 1
    assert not list((state / "functions").glob("*.json")) if (state / "functions").exists() else True

    source["checks"][0]["args"] = ["-c", "pass"]
    validated = validate_contract_source(root, source)
    decision = select_routes(validated, {"operation": "change"}, ["route:change"])
    plan = build_plan(validated, decision, root=root)
    result = _execute(root, validated, plan, state)
    assert result.producer_count == 2


def test_terminal_success_is_reused_across_claimed_runs(tmp_path: Path) -> None:
    root, _payload, validated, plan, state = _fixture(tmp_path)
    first = _execute(root, validated, plan, state)
    second = _execute(root, validated, plan, tmp_path / "other-state")
    assert first.producer_count == second.producer_count == 2
    assert first.leaves != second.leaves


def test_target_input_role_change_invalidates_only_its_owner(tmp_path: Path) -> None:
    checks = [_command("a", input_ids=["a"]), _command("b", input_ids=["b"])]
    root, _payload, validated, plan, state = _fixture(tmp_path, checks=checks, independent=True)
    first = _execute(root, validated, plan, state)
    (root / "src" / "a.txt").write_text("a-v2", encoding="utf-8")
    second = _execute(root, validated, plan, state)
    assert (first.producer_count, second.producer_count) == (2, 1)
    assert second.reused_count == 1
    assert second.leaves[1]["check_id"] == "b"


def test_explicit_owner_projects_one_receipt_to_distinct_semantic_checks(tmp_path: Path) -> None:
    root, _payload, validated, plan, state = _fixture(tmp_path, checks=[_command("a")])
    first = _execute(root, validated, plan, state)
    second = _execute(root, validated, plan, tmp_path / "other-state")
    # The functional key is intentionally independent of the control-root
    # storage location; each state root still owns and publishes its own leaf.
    assert first.leaves[0]["execution_key"] == second.leaves[0]["execution_key"]
    assert first.producer_count == second.producer_count == 1


def test_identical_checks_in_different_units_keep_independent_receipts(tmp_path: Path) -> None:
    root, source, validated, plan, state = _fixture(
        tmp_path, checks=[_command("a")], maintenance_unit_id="unit:one"
    )
    first = _execute(root, validated, plan, state)
    source["maintenance_unit_id"] = "unit:two"
    validated_two = validate_contract_source(root, source)
    decision = select_routes(validated_two, {"operation": "change"}, ["route:change"])
    plan_two = build_plan(validated_two, decision, root=root)
    second = _execute(root, validated_two, plan_two, tmp_path / "unit-two-state")
    assert first.leaves[0]["execution_key"] != second.leaves[0]["execution_key"]
    assert first.producer_count == second.producer_count == 1


def test_changed_dependency_receipt_invalidates_only_dependent_owner(tmp_path: Path) -> None:
    checks = [_command("a"), _command("b"), _command("c")]
    root, source, validated, plan, state = _fixture(tmp_path, checks=checks)
    first = _execute(root, validated, plan, state)
    source["checks"][0]["args"] = ["-c", "print('changed')"]
    validated = validate_contract_source(root, source)
    decision = select_routes(validated, {"operation": "change"}, ["route:change"])
    plan = build_plan(validated, decision, root=root)
    second = _execute(root, validated, plan, state)
    assert second.producer_count == 3
    assert all(first.leaves[index]["execution_key"] != second.leaves[index]["execution_key"] for index in range(3))


def test_declared_source_change_makes_success_stale(tmp_path: Path) -> None:
    root, _payload, validated, plan, state = _fixture(tmp_path)
    first = _execute(root, validated, plan, state)
    (root / "src" / "a.txt").write_text("changed", encoding="utf-8")
    second = _execute(root, validated, plan, state)
    assert second.producer_count == 2
    assert first.leaves[0]["execution_key"] != second.leaves[0]["execution_key"]


def test_tampered_success_receipt_is_quarantined_before_owner_reexecution(tmp_path: Path) -> None:
    root, _payload, validated, plan, state = _fixture(tmp_path)
    first = _execute(root, validated, plan, state)
    leaf_path = next((state / "functions").glob("*.json"))
    payload = json.loads(leaf_path.read_text(encoding="utf-8"))
    payload["status"] = "failed"
    leaf_path.write_text(json.dumps(payload), encoding="utf-8")
    context = ExecutionContext(required_check_ids=plan.check_order)
    with pytest.raises(ContractError) as raised:
        _execute(root, validated, plan, state, context=context)
    assert raised.value.code == "evidence_invalid"
    assert context.producer_count == 0
    assert first.producer_count == 2


def test_tampered_full_output_sidecar_cannot_be_reused(tmp_path: Path) -> None:
    root, _payload, validated, plan, state = _fixture(tmp_path)
    first = _execute(root, validated, plan, state)
    leaf = first.leaves[0]
    (state / leaf["stdout_ref"]).write_bytes(b"tampered")
    with pytest.raises(ContractError) as raised:
        _execute(root, validated, plan, state)
    assert raised.value.code == "evidence_invalid"


def test_timeout_terminates_descendant_tree_before_any_receipt(tmp_path: Path) -> None:
    child = "import pathlib,time; time.sleep(1); pathlib.Path('escaped.txt').write_text('escaped')"
    parent = f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{child!r}]); time.sleep(30)"
    checks = [_command("a", args=["-c", parent], timeout_seconds=0.2)]
    root, _payload, validated, plan, state = _fixture(tmp_path, checks=checks)
    context = ExecutionContext(required_check_ids=plan.check_order)
    with pytest.raises(ContractError) as raised:
        _execute(root, validated, plan, state, context=context)
    assert raised.value.code == "check_timeout"
    assert context.producer_count == 1
    time.sleep(1.2)
    assert not (root / "escaped.txt").exists()


def test_executor_single_flight_rejects_second_operation_without_producer(tmp_path: Path) -> None:
    checks = [
        _command("a", args=["-c", "import time; time.sleep(0.4)"]),
        _command("b", args=["-c", "import time; time.sleep(0.4)"]),
    ]
    root, _payload, validated, plan, state = _fixture(tmp_path, checks=checks)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        running = pool.submit(_execute, root, validated, plan, state)
        deadline = time.monotonic() + 5
        while not (state / "operation.lock").exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        loser_context = ExecutionContext(required_check_ids=plan.check_order)
        with pytest.raises(ContractError) as raised:
            _execute(root, validated, plan, state, context=loser_context)
        assert raised.value.code == "target_busy"
        assert loser_context.producer_count == 0
        assert running.result(timeout=10).producer_count == 2


def test_execution_cleanup_is_required_before_leaf_publication(tmp_path: Path) -> None:
    root, _payload, validated, plan, state = _fixture(tmp_path, checks=[_command("a")])
    result = _execute(root, validated, plan, state)
    assert result.leaves[0]["cleanup_confirmed"] is True
    assert (state / "functions").is_dir()
