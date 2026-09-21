from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.test_fixed_preflight_units import _root, _source

from checker_engine import build_plan, observe_inputs
from skillguard_v2.compact_contract import ContractError, strict_json_load, validate_contract_source
from skillguard_v2.route_runtime import select_routes


def _validated(tmp_path: Path, source: dict[str, object] | None = None):
    root = _root(tmp_path)
    return root, validate_contract_source(root, source or _source())


def _change(validated):
    return select_routes(validated, {"operation": "change"}, ["route:change"])


def test_author_entry_loading_current_contract(tmp_path: Path) -> None:
    root, validated = _validated(tmp_path)
    decision = _change(validated)
    assert decision.ok, decision.to_dict()
    assert decision.route_ids == ("route:change",)
    assert set(validated.by_route) == {"route:change"}
    assert all(
        set(route) >= {"route_id", "choice_group", "when", "step_ids", "obligation_ids"}
        for route in validated.by_route.values()
    )
    plan = build_plan(validated, decision, root=root)
    assert plan.route_ids == ("route:change",)
    assert plan.required_checks == ("a", "b")
    assert plan.check_dependencies["b"] == ("a",)


def test_route_runtime_v2_current_contract(tmp_path: Path) -> None:
    """Route selection is explicit v3 fact matching with a frozen asserted scope."""

    _root_path, validated = _validated(tmp_path)
    selected = select_routes(validated, {"operation": "change"}, ["route:change"])
    assert selected.ok, selected.to_dict()
    assert selected.route_ids == ("route:change",)

    no_match = select_routes(validated, {"operation": "inspect"}, ["route:change"])
    assert not no_match.ok
    assert no_match.findings[0].code == "no_route"

    unknown = select_routes(validated, {"operation": "change"}, ["route:missing"])
    assert not unknown.ok
    assert unknown.findings[0].code == "scope_mismatch"


def test_launch_plan_v2_current_contract(tmp_path: Path) -> None:
    """The v3 executor binds one resolved interpreter/environment identity per check."""

    from checker_engine import resolve_invocation

    root, validated = _validated(tmp_path)
    invocation = resolve_invocation(root, validated.by_check["a"])
    assert Path(invocation["executable"]).is_file()
    assert invocation["args"] == ["-c", "pass"]
    assert invocation["cwd"].lower() == str(root.resolve()).lower()
    assert invocation["environment_identity"]["SystemRoot"].startswith("sha256:")


def test_sg_missing_explicit_contract_never_uses_default(tmp_path: Path) -> None:
    root = _root(tmp_path)
    with pytest.raises(ContractError) as raised:
        strict_json_load(root / ".skillguard" / "contract-source.json")
    assert raised.value.code == "json_unreadable"


def test_sg_empty_selection_does_not_expand_to_all_checks(tmp_path: Path) -> None:
    _root_path, validated = _validated(tmp_path)
    decision = select_routes(validated, {"operation": "change"}, [])
    assert not decision.ok
    assert decision.findings[0].code == "scope_mismatch"


def test_sg_obligation_checks_are_not_omitted(tmp_path: Path) -> None:
    _root_path, validated = _validated(tmp_path)
    plan = build_plan(validated, _change(validated))
    assert plan.required_checks == ("a", "b")
    assert plan.obligation_checks == {"ob:leaf": ("b",)}


def test_sg_required_step_is_included_before_child(tmp_path: Path) -> None:
    _root_path, validated = _validated(tmp_path)
    plan = build_plan(validated, _change(validated))
    assert plan.check_order == ("a", "b")
    assert plan.check_dependencies["b"] == ("a",)


def test_sg_step_cycle_blocks_before_execution(tmp_path: Path) -> None:
    source = _source()
    source["steps"][0]["requires"] = ["leaf"]  # type: ignore[index]
    root = _root(tmp_path)
    with pytest.raises(ContractError) as raised:
        validate_contract_source(root, source)
    assert raised.value.code == "step_dependency_cycle"


def test_sg_unknown_step_blocks_before_execution(tmp_path: Path) -> None:
    source = _source()
    source["steps"][1]["requires"] = ["missing"]  # type: ignore[index]
    root = _root(tmp_path)
    with pytest.raises(ContractError) as raised:
        validate_contract_source(root, source)
    assert raised.value.code == "unknown_reference"


def test_sg_duplicate_check_id_blocks_before_execution(tmp_path: Path) -> None:
    source = _source()
    source["checks"].append(copy.deepcopy(source["checks"][0]))  # type: ignore[index]
    root = _root(tmp_path)
    with pytest.raises(ContractError) as raised:
        validate_contract_source(root, source)
    assert raised.value.code == "duplicate_id"


def test_sg_missing_required_input_blocks_before_execution(tmp_path: Path) -> None:
    root, validated = _validated(tmp_path)
    (root / "src" / "a.txt").unlink()
    plan = build_plan(validated, _change(validated))
    with pytest.raises(ContractError) as raised:
        observe_inputs(root, validated, plan)
    assert raised.value.code == "input_missing"


def test_sg_unknown_oracle_key_does_not_silently_pass(tmp_path: Path) -> None:
    source = _source()
    source["checks"][0]["expected"] = {"exit_code": 0, "status": "pass"}  # type: ignore[index]
    root = _root(tmp_path)
    with pytest.raises(ContractError) as raised:
        validate_contract_source(root, source)
    assert raised.value.code == "invalid_oracle"


def test_sg_rejects_legacy_fields_before_execution(tmp_path: Path) -> None:
    source = _source()
    source["legacy_contract"] = {"schema_version": "v2"}
    root = _root(tmp_path)
    with pytest.raises(ContractError) as raised:
        validate_contract_source(root, source)
    assert raised.value.code == "unknown_field"


def test_sg_no_function_id_predicate_bypass(tmp_path: Path) -> None:
    source = _source()
    source["routes"][0]["when"] = [{"fact": "function_id", "equals": "analyze"}]  # type: ignore[index]
    _root_path, validated = _validated(tmp_path, source)
    decision = select_routes(validated, {"operation": "change"}, ["route:change"])
    assert not decision.ok
    assert decision.findings[0].code == "missing_fact"


def test_sg_json_boolean_does_not_match_integer(tmp_path: Path) -> None:
    source = _source()
    source["routes"][0]["when"] = [{"fact": "operation", "equals": 1}]  # type: ignore[index]
    _root_path, validated = _validated(tmp_path, source)
    decision = select_routes(validated, {"operation": True}, ["route:change"])
    assert not decision.ok
    assert decision.findings[0].code == "no_route"


def test_sg_explicit_route_does_not_override_ambiguity(tmp_path: Path) -> None:
    source = _source()
    extra = copy.deepcopy(source["routes"][0])
    extra["route_id"] = "route:duplicate"  # type: ignore[index]
    source["routes"].append(extra)  # type: ignore[union-attr]
    _root_path, validated = _validated(tmp_path, source)
    decision = select_routes(validated, {"operation": "change"}, ["route:change"])
    assert not decision.ok
    assert decision.findings[0].code == "ambiguous_route"


def test_sg_different_composition_ids_not_composable(tmp_path: Path) -> None:
    source = _source()
    source["routes"][0]["composition_id"] = "one"  # type: ignore[index]
    extra = copy.deepcopy(source["routes"][0])
    extra["route_id"] = "route:extra"  # type: ignore[index]
    extra["choice_group"] = "extra"  # type: ignore[index]
    extra["composition_id"] = "two"  # type: ignore[index]
    extra["when"] = [{"fact": "extra", "equals": True}]  # type: ignore[index]
    source["routes"].append(extra)  # type: ignore[union-attr]
    _root_path, validated = _validated(tmp_path, source)
    decision = select_routes(validated, {"operation": "change", "extra": True}, ["route:change", "route:extra"])
    assert not decision.ok
    assert decision.findings[0].code == "incompatible_composition"


def test_sg_unselected_bad_check_never_runs(tmp_path: Path) -> None:
    source = _source()
    source["checks"].append({"check_id": "unused", "kind": "command", "command": "bad", "args": [], "input_ids": ["a"], "expected": {"exit_code": 0}})  # type: ignore[union-attr]
    source["steps"].append({"step_id": "unused-step", "requires": [], "check_ids": ["unused"]})  # type: ignore[union-attr]
    root, validated = _validated(tmp_path, source)
    plan = build_plan(validated, _change(validated))
    assert "unused" not in plan.required_checks
    assert root.exists()


def test_sg_undeclared_arguments_rejected(tmp_path: Path) -> None:
    source = _source()
    source["checks"][0]["args"] = [1]  # type: ignore[index]
    root = _root(tmp_path)
    with pytest.raises(ContractError) as raised:
        validate_contract_source(root, source)
    assert raised.value.code == "unknown_field"


def test_sg_no_match_rejected(tmp_path: Path) -> None:
    _root_path, validated = _validated(tmp_path)
    decision = select_routes(validated, {"operation": "release"}, ["route:change"])
    assert not decision.ok
    assert decision.findings[0].code == "no_route"


def test_sg_missing_facts_rejected(tmp_path: Path) -> None:
    _root_path, validated = _validated(tmp_path)
    decision = select_routes(validated, {}, ["route:change"])
    assert not decision.ok
    assert decision.findings[0].code == "missing_fact"


def test_sg_unverified_empty_oracle_rejected(tmp_path: Path) -> None:
    source = _source()
    source["checks"][0]["expected"] = {}  # type: ignore[index]
    root = _root(tmp_path)
    with pytest.raises(ContractError) as raised:
        validate_contract_source(root, source)
    assert raised.value.code == "invalid_oracle"


def test_sg_duplicate_json_rejected_before_work(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text('{"a":1,"a":2}', encoding="utf-8")
    with pytest.raises(ContractError) as raised:
        strict_json_load(path)
    assert raised.value.code == "duplicate_json_key"


def test_target_id_mismatch_starts_zero(tmp_path: Path) -> None:
    root = _root(tmp_path)
    request = root / "request.json"
    request.write_text(json.dumps({"target_id": "wrong"}), encoding="utf-8")
    assert json.loads(request.read_text(encoding="utf-8"))["target_id"] == "wrong"
    assert not (root / "author-state").exists()


def test_check_has_exactly_one_step_owner(tmp_path: Path) -> None:
    source = _source()
    source["steps"][1]["check_ids"] = ["a", "b"]  # type: ignore[index]
    root = _root(tmp_path)
    with pytest.raises(ContractError) as raised:
        validate_contract_source(root, source)
    assert raised.value.code == "check_owner_duplicate"


def test_obligation_pulls_owner_and_transitive_preconditions(tmp_path: Path) -> None:
    _root_path, validated = _validated(tmp_path)
    plan = build_plan(validated, _change(validated))
    assert plan.required_checks == ("a", "b")
    assert plan.check_dependencies["b"] == ("a",)


def test_unknown_route_candidate_cannot_hide_ambiguity(tmp_path: Path) -> None:
    source = _source()
    source["routes"].append({"route_id": "route:unknown", "choice_group": "other", "when": [{"fact": "unprovided", "equals": True}], "step_ids": [], "obligation_ids": ["ob:leaf"]})  # type: ignore[union-attr]
    _root_path, validated = _validated(tmp_path, source)
    decision = select_routes(validated, {"operation": "change"}, ["route:change"])
    assert not decision.ok
    assert decision.findings[0].code == "missing_fact"


def test_ruled_out_route_does_not_require_irrelevant_fact(tmp_path: Path) -> None:
    source = _source()
    source["routes"].append({"route_id": "route:release", "choice_group": "operation", "when": [{"fact": "operation", "equals": "release"}, {"fact": "missing", "equals": True}], "step_ids": [], "obligation_ids": ["ob:leaf"]})  # type: ignore[union-attr]
    _root_path, validated = _validated(tmp_path, source)
    decision = select_routes(validated, {"operation": "change"}, ["route:change"])
    assert decision.ok


def test_nested_json_boolean_does_not_match_integer(tmp_path: Path) -> None:
    source = _source()
    source["routes"][0]["when"] = [{"fact": "payload", "equals": {"value": 1}}]  # type: ignore[index]
    _root_path, validated = _validated(tmp_path, source)
    decision = select_routes(validated, {"payload": {"value": True}}, ["route:change"])
    assert not decision.ok
    assert decision.findings[0].code == "no_route"


def test_self_input_inventory_complete(tmp_path: Path) -> None:
    root, validated = _validated(tmp_path)
    plan = build_plan(validated, _change(validated))
    snapshot = observe_inputs(root, validated, plan)
    assert {str(row["id"]) for row in snapshot.rows} == {"a", "b"}


def test_template_adapters_v2_current_contract(tmp_path: Path) -> None:
    root, validated = _validated(tmp_path)
    assert validated.source["schema_version"] == "skillguard.skill_contract.v3"
    assert set(validated.source) == {
        "schema_version",
        "skill_id",
        "maintenance_unit_id",
        "inputs",
        "checks",
        "steps",
        "obligations",
        "routes",
    }
    assert not any(key in validated.source for key in ("template", "catalog", "adapter", "profile"))
    assert build_plan(validated, _change(validated), root=root).required_checks == ("a", "b")


def test_template_fragments_v2_current_contract(tmp_path: Path) -> None:
    root, validated = _validated(tmp_path)
    route = validated.by_route["route:change"]
    assert route["step_ids"] == []
    assert route["obligation_ids"] == ["ob:leaf"]
    assert validated.by_obligation["ob:leaf"]["check_ids"] == ["b"]
    assert build_plan(validated, _change(validated), root=root).check_dependencies == {
        "a": (),
        "b": ("a",),
    }


def test_template_profiles_v2_current_contract(tmp_path: Path) -> None:
    root, validated = _validated(tmp_path)
    decision = select_routes(validated, {"operation": "change"}, ["route:change"])
    assert decision.ok
    plan = build_plan(validated, decision, operation="change", root=root)
    assert plan.operation == "change"
    assert plan.required_checks == tuple(plan.check_order)
    with pytest.raises(ContractError):
        build_plan(validated, decision, operation="profile", root=root)


def test_template_packs_v2_current_contract(tmp_path: Path) -> None:
    root, validated = _validated(tmp_path)
    plan = build_plan(validated, _change(validated), root=root)
    assert plan.route_ids == ("route:change",)
    assert set(plan.to_dict()) == {
        "schema_version",
        "maintenance_unit_id",
        "skill_id",
        "author_root_identity",
        "operation",
        "route_ids",
        "step_ids",
        "obligation_checks",
        "check_order",
        "check_dependencies",
        "selected_input_ids",
    }
