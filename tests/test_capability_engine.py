"""Current v3 capability/evidence boundaries.

The former capability portfolio engine and its receipt bridge were retired.
These tests keep the meaningful claims on the compact contract, target-owned
checks and clean consumer projection.
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.test_compact_contract_cli import _accepted_v2, _request, _run, _write_contract
from tests.test_fixed_preflight_units import _root, _source
from skillguard_v2.compact_state import control_root

SCRIPT_ROOT = Path(__file__).resolve().parents[1] / ".agents" / "skills" / "skillguard" / "scripts"


def test_current_contract_is_the_only_capability_authority(tmp_path: Path) -> None:
    from skillguard_v2.compact_contract import validate_contract_source

    root = _root(tmp_path)
    validated = validate_contract_source(root, _source())
    assert validated.source["schema_version"] == "skillguard.skill_contract.v3"
    assert set(validated.source) >= {
        "schema_version",
        "skill_id",
        "maintenance_unit_id",
        "inputs",
        "routes",
        "steps",
        "obligations",
        "checks",
    }
    assert "capability_portfolio" not in validated.source


def test_functional_claim_without_producer_receipt_is_blocked(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _write_contract(root)
    state = tmp_path / "state"
    state.mkdir()

    code, payload = _run(root, _request(root, state, "read", scope="route:change"), "read")

    assert code == 1
    assert payload["status"] == "blocked"
    assert payload["producer_count"] == 0
    assert payload["reason"] == "uninitialized"


def test_missing_reverse_surface_input_blocks_before_execution(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _write_contract(root)
    (root / "src" / "a.txt").unlink()
    state = tmp_path / "state"
    state.mkdir()

    code, payload = _run(root, _request(root, state, "change"), "change")

    assert code == 1
    assert payload["reason"] == "input_missing"
    assert payload["producer_count"] == 0


def test_source_input_change_invalidates_previous_leaf_identity(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _write_contract(root)
    state = tmp_path / "state"
    state.mkdir()
    first_code, first = _run(root, _request(root, state, "change"), "change")
    assert first_code == 0, first
    (root / "src" / "a.txt").write_text("changed", encoding="utf-8")

    second_code, second = _run(
        root,
        _request(root, state, "change", expected_current=str(first["accepted_id"])),
        "change",
    )

    assert second_code == 0, second
    # `a` is the prerequisite of `b`; changing its declared input invalidates
    # both functional owners, so the compact executor must re-produce both.
    assert second["producer_count"] == 2
    assert second["reused_count"] == 0
    assert second["accepted_id"] != first["accepted_id"]


def test_cross_unit_state_is_not_a_functional_receipt(tmp_path: Path) -> None:
    root_a = _root(tmp_path / "a")
    _write_contract(root_a)
    state = tmp_path / "state"
    state.mkdir()
    first_code, first = _run(root_a, _request(root_a, state, "change"), "change")
    assert first_code == 0, first

    root_b = _root(tmp_path / "b")
    _write_contract(root_b)
    request = _request(root_b, state, "change", expected_current=str(first["accepted_id"]))
    code, payload = _run(root_b, request, "change")

    assert code == 1
    assert payload["reason"] in {"evidence_invalid", "accepted_current_conflict", "state_binding_mismatch"}
    assert payload["producer_count"] == 0


def test_tampered_leaf_never_becomes_a_capability_pass(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _write_contract(root)
    state = tmp_path / "state"
    state.mkdir()
    first_code, first = _run(root, _request(root, state, "change"), "change")
    assert first_code == 0, first
    target = control_root(state, "fixture-unit", "fixture")
    leaf_path = next((target / "functions").glob("*.json"))
    leaf = json.loads(leaf_path.read_text(encoding="utf-8"))
    leaf["exit_code"] = 99
    leaf_path.write_text(json.dumps(leaf), encoding="utf-8")

    code, payload = _run(
        root,
        _request(root, state, "change", expected_current=str(first["accepted_id"])),
        "change",
    )
    assert code == 1
    assert payload["reason"] == "evidence_invalid"
    assert payload["producer_count"] == 0


def test_timeout_or_cleanup_failure_cannot_publish_capability(tmp_path: Path) -> None:
    source = _source()
    source["checks"][0]["timeout_seconds"] = 0.2  # type: ignore[index]
    source["checks"][0]["args"] = ["-c", "import time; time.sleep(3)"]  # type: ignore[index]
    root = _root(tmp_path)
    control = root / ".skillguard"
    control.mkdir()
    (control / "contract-source.json").write_text(json.dumps(source), encoding="utf-8")
    state = tmp_path / "state"
    state.mkdir()

    code, payload = _run(root, _request(root, state, "change"), "change")

    assert code == 1
    assert payload["reason"] == "check_timeout"
    assert payload["producer_count"] == 1
    assert not (control_root(state, "fixture-unit", "fixture") / "current.json").exists()


def test_release_scope_requires_current_source_evidence(tmp_path: Path) -> None:
    source = _source()
    source["routes"].append({"route_id": "route:release", "choice_group": "operation", "when": [{"fact": "operation", "equals": "release"}], "step_ids": [], "obligation_ids": ["ob:leaf"]})  # type: ignore[union-attr]
    root = _root(tmp_path)
    control = root / ".skillguard"
    control.mkdir()
    (control / "contract-source.json").write_text(json.dumps(source), encoding="utf-8")
    state = tmp_path / "state"
    state.mkdir()

    code, payload = _run(root, _request(root, state, "release"), "release")

    assert code == 1
    assert payload["reason"] == "accepted_result_missing"
    assert payload["producer_count"] == 0


def test_clean_consumer_projection_contains_no_capability_authority(tmp_path: Path) -> None:
    from skillguard_v2.consumer_distribution import audit_consumer_distribution, build_consumer_distribution
    from skillguard_v2.contract_compiler import compile_skill_contract

    repository_root = Path(__file__).resolve().parents[1]
    compiled = compile_skill_contract(repository_root, write=False)
    assert compiled.ok, compiled.to_dict()
    destination = tmp_path / "consumer"
    built = build_consumer_distribution(repository_root / ".agents" / "skills" / "skillguard", destination, compiled.compiled_contract)
    assert built["status"] == "passed", built
    assert audit_consumer_distribution(destination)["status"] == "passed"
    paths = {str(row["path"]) for row in built["manifest"]["files"]}
    assert not any("portfolio" in path or "assurance" in path or "capability" in path for path in paths)
    assert ".skillguard" not in paths


def test_retired_capability_engine_surface_is_absent() -> None:
    assert not (SCRIPT_ROOT / "skillguard_v2" / "capability_engine.py").exists()
