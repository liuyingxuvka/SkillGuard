from __future__ import annotations

import copy
import concurrent.futures
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / ".agents" / "skills" / "skillguard" / "scripts"
sys.path.insert(0, str(SCRIPT_ROOT))

from checker_engine import build_plan, execute_plan, freeze_execution_identity, leaf_execution_key, observe_inputs  # noqa: E402
from skillguard_v2.compact_contract import (  # noqa: E402
    ContractError,
    strict_json_load,
    validate_contract_source,
)
from skillguard_v2.route_runtime import select_routes  # noqa: E402


def _source() -> dict[str, object]:
    return {
        "schema_version": "skillguard.skill_contract.v3",
        "skill_id": "fixture",
        "maintenance_unit_id": "fixture-unit",
        "inputs": [
            {"id": "a", "path": "src/a.txt", "required": True},
            {"id": "b", "path": "src/b.txt", "required": True},
        ],
        "checks": [
            {"check_id": "a", "kind": "command", "command": "{{python}}", "args": ["-c", "pass"], "input_ids": ["a"], "expected": {"exit_code": 0}},
            {"check_id": "b", "kind": "command", "command": "{{python}}", "args": ["-c", "pass"], "input_ids": ["b"], "expected": {"exit_code": 0}},
        ],
        "steps": [
            {"step_id": "base", "requires": [], "check_ids": ["a"]},
            {"step_id": "leaf", "requires": ["base"], "check_ids": ["b"]},
        ],
        "obligations": [{"obligation_id": "ob:leaf", "check_ids": ["b"]}],
        "routes": [
            {
                "route_id": "route:change",
                "choice_group": "operation",
                "when": [{"fact": "operation", "equals": "change"}],
                "step_ids": [],
                "obligation_ids": ["ob:leaf"],
            }
        ],
    }


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "target"
    (root / "src").mkdir(parents=True)
    (root / "src" / "a.txt").write_text("a", encoding="utf-8")
    (root / "src" / "b.txt").write_text("b", encoding="utf-8")
    return root


def _validated(tmp_path: Path, source: dict[str, object] | None = None):
    return validate_contract_source(_root(tmp_path), source or _source())


def _error(root: Path, source: dict[str, object]) -> ContractError:
    with pytest.raises(ContractError) as raised:
        validate_contract_source(root, source)
    return raised.value


def test_valid_preflight_plan_has_dependency_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _root(tmp_path)
    source = _source()
    before = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: pytest.fail("producer started"))
    validated = validate_contract_source(root, source)
    decision = select_routes(validated, {"operation": "change"}, ["route:change"])
    plan = build_plan(validated, decision)
    assert plan.required_checks == ("a", "b")
    assert plan.check_dependencies == {"a": (), "b": ("a",)}
    assert plan.obligation_checks == {"ob:leaf": ("b",)}
    assert before == {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}


@pytest.mark.parametrize("text", ['{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}'])
def test_strict_loader_rejects_duplicate_and_nonfinite(tmp_path: Path, text: str) -> None:
    path = tmp_path / "bad.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ContractError):
        strict_json_load(path)


def test_contract_rejects_unknown_fields(tmp_path: Path) -> None:
    root, source = _root(tmp_path), _source()
    source["checks"][0]["unexpected"] = True  # type: ignore[index]
    assert _error(root, source).code == "unknown_field"


def test_contract_rejects_cycle(tmp_path: Path) -> None:
    root, source = _root(tmp_path), _source()
    source["steps"][0]["requires"] = ["leaf"]  # type: ignore[index]
    assert _error(root, source).code == "step_dependency_cycle"


@pytest.mark.parametrize(
    ("expected", "kind", "code"),
    [({}, "command", "invalid_oracle"), ({"exit_code": False}, "command", "invalid_oracle"), ({"exit_code": 0}, "made_up", "unsupported_check_kind")],
)
def test_contract_rejects_empty_or_unknown_oracle(tmp_path: Path, expected: object, kind: str, code: str) -> None:
    root, source = _root(tmp_path), _source()
    source["checks"][0]["expected"] = expected  # type: ignore[index]
    source["checks"][0]["kind"] = kind  # type: ignore[index]
    assert _error(root, source).code == code


@pytest.mark.parametrize("duplicate", [False, True])
def test_contract_rejects_missing_or_duplicate_check_owner(tmp_path: Path, duplicate: bool) -> None:
    root, source = _root(tmp_path), _source()
    if duplicate:
        source["steps"][1]["check_ids"] = ["a", "b"]  # type: ignore[index]
        code = "check_owner_duplicate"
    else:
        source["steps"][0]["check_ids"] = []  # type: ignore[index]
        code = "check_owner_missing"
    assert _error(root, source).code == code


def test_optional_input_presence_is_not_structure_validation(tmp_path: Path) -> None:
    root, source = _root(tmp_path), _source()
    source["inputs"][1]["required"] = False  # type: ignore[index]
    (root / "src" / "b.txt").unlink()
    assert validate_contract_source(root, source).by_input["b"]["required"] is False


def test_missing_unruled_fact_blocks_even_when_other_route_matches(tmp_path: Path) -> None:
    source = _source()
    source["routes"].append({"route_id": "route:unknown", "choice_group": "operation", "when": [{"fact": "unprovided", "equals": True}], "step_ids": [], "obligation_ids": ["ob:leaf"]})  # type: ignore[union-attr]
    decision = select_routes(_validated(tmp_path, source), {"operation": "change"}, ["route:change"])
    assert not decision.ok and decision.findings[0].code == "missing_fact"


def test_known_false_predicate_rules_out_route(tmp_path: Path) -> None:
    source = _source()
    source["routes"].append({"route_id": "route:unknown", "choice_group": "operation", "when": [{"fact": "operation", "equals": "release"}, {"fact": "unprovided", "equals": True}], "step_ids": [], "obligation_ids": ["ob:leaf"]})  # type: ignore[union-attr]
    decision = select_routes(_validated(tmp_path, source), {"operation": "change"}, ["route:change"])
    assert decision.ok and decision.route_ids == ("route:change",)


@pytest.mark.parametrize(("expected", "actual"), [(True, 1), ([True], [1])])
def test_facts_keep_json_types(tmp_path: Path, expected: object, actual: object) -> None:
    source = _source()
    source["routes"][0]["when"] = [{"fact": "operation", "equals": expected}]  # type: ignore[index]
    decision = select_routes(_validated(tmp_path, source), {"operation": actual}, ["route:change"])
    assert not decision.ok and decision.findings[0].code == "no_route"


def test_composition_and_scope_are_assertions(tmp_path: Path) -> None:
    source = _source()
    source["routes"][0]["composition_id"] = "pair"  # type: ignore[index]
    source["routes"].append({"route_id": "route:extra", "choice_group": "extra", "composition_id": "pair", "when": [{"fact": "extra", "equals": True}], "step_ids": [], "obligation_ids": ["ob:leaf"]})  # type: ignore[union-attr]
    validated = _validated(tmp_path, source)
    assert select_routes(validated, {"operation": "change", "extra": True}, ["route:change", "route:extra"]).ok
    mismatch = select_routes(validated, {"operation": "change", "extra": True}, ["route:change"])
    assert mismatch.findings[0].code == "scope_mismatch"
    source["routes"][1].pop("composition_id")  # type: ignore[index]
    incompatible = select_routes(_validated(tmp_path / "second", source), {"operation": "change", "extra": True}, ["route:change", "route:extra"])
    assert incompatible.findings[0].code == "incompatible_composition"


def test_obligation_pulls_owner_and_all_requires(tmp_path: Path) -> None:
    source = _source()
    source["checks"].append({"check_id": "c", "kind": "command", "command": "{{python}}", "args": ["-c", "pass"], "input_ids": ["b"], "expected": {"exit_code": 0}})  # type: ignore[union-attr]
    source["steps"].append({"step_id": "tail", "requires": ["leaf"], "check_ids": ["c"]})  # type: ignore[union-attr]
    source["obligations"].append({"obligation_id": "ob:tail", "check_ids": ["b", "c"]})  # type: ignore[union-attr]
    source["routes"][0]["obligation_ids"] = ["ob:leaf", "ob:tail"]  # type: ignore[index]
    validated = _validated(tmp_path, source)
    plan = build_plan(validated, select_routes(validated, {"operation": "change"}, ["route:change"]))
    assert plan.required_checks == ("a", "b", "c")
    assert plan.check_dependencies["c"] == ("a", "b")


def test_empty_verification_never_passes(tmp_path: Path) -> None:
    source = _source()
    source["routes"][0]["obligation_ids"] = []  # type: ignore[index]
    source["steps"] = [{"step_id": "base", "requires": [], "check_ids": ["a", "b"]}]
    validated = _validated(tmp_path, source)
    decision = select_routes(validated, {"operation": "change"}, ["route:change"])
    with pytest.raises(ContractError) as raised:
        build_plan(validated, decision)
    assert raised.value.code == "no_verification_obligation"


def test_input_snapshot_distinguishes_missing_from_literal_marker(tmp_path: Path) -> None:
    root, source = _root(tmp_path), _source()
    source["inputs"][1]["required"] = False  # type: ignore[index]
    validated = validate_contract_source(root, source)
    plan = build_plan(validated, select_routes(validated, {"operation": "change"}, ["route:change"]))
    (root / "src" / "b.txt").unlink()
    missing = observe_inputs(root, validated, plan)
    assert missing.rows[1]["exists"] is False and missing.rows[1]["sha256"] is None
    (root / "src" / "b.txt").write_text("<missing>", encoding="utf-8")
    present = observe_inputs(root, validated, plan)
    assert present.rows[1]["exists"] is True and present.rows[1]["sha256"] is not None
    assert present.snapshot_hash != missing.snapshot_hash


def test_leaf_key_binds_root_unit_environment_and_dependencies(tmp_path: Path) -> None:
    root, source = _root(tmp_path), _source()
    source["checks"][1]["environment"] = {"DECLARED_VALUE": "visible"}  # type: ignore[index]
    validated = validate_contract_source(root, source)
    plan = build_plan(validated, select_routes(validated, {"operation": "change"}, ["route:change"]))
    snapshot = observe_inputs(root, validated, plan)
    execution_identity = freeze_execution_identity(root, validated, plan)
    a_key, _ = leaf_execution_key(root, validated, plan, snapshot, "a", {}, execution_identity)
    b_key, invocation = leaf_execution_key(root, validated, plan, snapshot, "b", {"a": a_key}, execution_identity)
    assert invocation["effective_environment"]["DECLARED_VALUE"] == "visible"
    assert leaf_execution_key(root, validated, plan, snapshot, "b", {"a": a_key}, execution_identity)[0] == b_key
    assert leaf_execution_key(root, validated, plan, snapshot, "b", {"a": "sha256:" + "0" * 64}, execution_identity)[0] != b_key


def test_leaf_key_excludes_route_identity_but_binds_input_bytes(tmp_path: Path) -> None:
    root, source = _root(tmp_path), _source()
    source["routes"].append({"route_id": "route:release", "choice_group": "operation", "when": [{"fact": "operation", "equals": "release"}], "step_ids": [], "obligation_ids": ["ob:leaf"]})  # type: ignore[union-attr]
    validated = validate_contract_source(root, source)
    change_plan = build_plan(validated, select_routes(validated, {"operation": "change"}, ["route:change"]))
    release_plan = build_plan(validated, select_routes(validated, {"operation": "release"}, ["route:release"]))
    first = observe_inputs(root, validated, change_plan)
    change_key = leaf_execution_key(root, validated, change_plan, first, "a", {}, freeze_execution_identity(root, validated, change_plan))[0]
    release_key = leaf_execution_key(root, validated, release_plan, first, "a", {}, freeze_execution_identity(root, validated, release_plan))[0]
    assert change_key == release_key
    (root / "src" / "a.txt").write_text("changed", encoding="utf-8")
    second = observe_inputs(root, validated, change_plan)
    assert leaf_execution_key(root, validated, change_plan, second, "a", {}, freeze_execution_identity(root, validated, change_plan))[0] != change_key


def _execution_fixture(tmp_path: Path, source: dict[str, object] | None = None):
    root = _root(tmp_path)
    payload = source or _source()
    validated = validate_contract_source(root, payload)
    plan = build_plan(validated, select_routes(validated, {"operation": "change"}, ["route:change"]))
    state = (tmp_path / "author-state").resolve()
    return root, validated, plan, state


def test_executor_passes_declared_real_environment_and_reuses_current_leaves(tmp_path: Path) -> None:
    source = _source()
    source["checks"][1]["environment"] = {"DECLARED_VALUE": "visible"}  # type: ignore[index]
    source["checks"][1]["args"] = [  # type: ignore[index]
        "-c",
        "import os,sys; sys.exit(0 if os.environ.get('DECLARED_VALUE') == 'visible' and os.environ.get('PYTHONDONTWRITEBYTECODE') == '1' else 7)",
    ]
    root, validated, plan, state = _execution_fixture(tmp_path, source)
    first = execute_plan(root, validated, plan, state)
    assert (first.producer_count, first.run_count, first.reused_count) == (2, 2, 0)
    second = execute_plan(root, validated, plan, state)
    assert (second.producer_count, second.run_count, second.reused_count) == (0, 0, 2)
    assert second.leaves == first.leaves


def test_executor_reexecutes_only_changed_leaf(tmp_path: Path) -> None:
    root, validated, plan, state = _execution_fixture(tmp_path)
    assert execute_plan(root, validated, plan, state).producer_count == 2
    (root / "src" / "b.txt").write_text("changed", encoding="utf-8")
    result = execute_plan(root, validated, plan, state)
    assert (result.producer_count, result.run_count, result.reused_count) == (1, 1, 1)
    assert [leaf["check_id"] for leaf in result.leaves] == ["a", "b"]


def test_executor_single_flight_rejects_second_operation_without_producer(tmp_path: Path) -> None:
    source = _source()
    for check in source["checks"]:  # type: ignore[index]
        check["args"] = ["-c", "import time; time.sleep(0.35)"]
    root, validated, plan, state = _execution_fixture(tmp_path, source)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        running = pool.submit(execute_plan, root, validated, plan, state)
        deadline = time.monotonic() + 5
        while not (state / "operation.lock").exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        with pytest.raises(ContractError) as raised:
            execute_plan(root, validated, plan, state)
        assert raised.value.code == "target_busy"
        assert running.result(timeout=10).producer_count == 2


def test_executor_blocks_when_selected_input_drifts_during_run(tmp_path: Path) -> None:
    source = _source()
    source["checks"][0]["args"] = ["-c", "from pathlib import Path; Path('src/b.txt').write_text('drift', encoding='utf-8')"]  # type: ignore[index]
    root, validated, plan, state = _execution_fixture(tmp_path, source)
    with pytest.raises(ContractError) as raised:
        execute_plan(root, validated, plan, state)
    assert raised.value.code == "input_changed"


def test_executor_rejects_existing_tampered_leaf_without_rerun(tmp_path: Path) -> None:
    root, validated, plan, state = _execution_fixture(tmp_path)
    first = execute_plan(root, validated, plan, state)
    leaf = next((state / "functions").glob("*.json"))
    payload = json.loads(leaf.read_text(encoding="utf-8"))
    payload["status"] = "success"
    leaf.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ContractError) as raised:
        execute_plan(root, validated, plan, state)
    assert raised.value.code == "evidence_invalid"
    assert len(list((state / "attempts").iterdir())) == first.producer_count


def test_executor_failure_stops_all_later_checks(tmp_path: Path) -> None:
    source = _source()
    source["checks"][0]["args"] = ["-c", "import sys; sys.exit(9)"]  # type: ignore[index]
    source["checks"][1]["args"] = ["-c", "from pathlib import Path; Path('later-ran').write_text('bad')"]  # type: ignore[index]
    root, validated, plan, state = _execution_fixture(tmp_path, source)
    with pytest.raises(ContractError) as raised:
        execute_plan(root, validated, plan, state)
    assert raised.value.code == "check_failed"
    assert not (root / "later-ran").exists()
    assert len(list((state / "attempts").iterdir())) == 1
