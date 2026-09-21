"""Current compact-runtime safety checks for the former diagnostics surface.

The generic assurance solver and mutation projection were retired.  The
useful obligations remain covered by the v3 contract, accepted snapshot and
target-native execution paths exercised here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.test_compact_contract_cli import _accepted_v2, _request, _run, _write_contract
from tests.test_fixed_preflight_units import _root, _source

SCRIPT_ROOT = Path(__file__).resolve().parents[1] / ".agents" / "skills" / "skillguard" / "scripts"


def test_missing_receipts_are_visible_without_execution(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _write_contract(root)
    state = tmp_path / "state"
    state.mkdir()
    _, target = _accepted_v2(root, state, _source())
    next((target / "functions").glob("*.json")).unlink()
    before = {path.relative_to(state): path.read_bytes() for path in state.rglob("*") if path.is_file()}

    code, payload = _run(root, _request(root, state, "read", scope="route:change"), "read")

    assert code == 1
    assert payload["status"] == "blocked"
    assert payload["reason"] == "qualification_incomplete"
    assert payload["producer_count"] == 0
    assert before == {path.relative_to(state): path.read_bytes() for path in state.rglob("*") if path.is_file()}


def test_blocked_closure_is_preserved_as_current_read_boundary(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _write_contract(root)
    state = tmp_path / "state"
    state.mkdir()
    before = list(state.rglob("*"))

    code, payload = _run(root, _request(root, state, "read", scope="route:change"), "read")

    assert code == 1
    assert payload["status"] == "blocked"
    assert payload["producer_count"] == 0
    assert list(state.rglob("*")) == before


def test_unauthorized_required_denominator_removal_is_rejected(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _write_contract(root)
    state = tmp_path / "state"
    state.mkdir()
    _, target = _accepted_v2(root, state, _source())
    current = json.loads((target / "current.json").read_text(encoding="utf-8"))
    aggregate_path = target / str(current["result_ref"])
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    plan_path = target / str(aggregate["plan_ref"])
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["check_order"] = []
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    aggregate["plan_hash"] = "sha256:" + "0" * 64
    aggregate_path.write_text(json.dumps(aggregate), encoding="utf-8")

    code, payload = _run(root, _request(root, state, "read", scope="route:change"), "read")

    assert code == 1
    assert payload["status"] == "blocked"
    assert payload["reason"] == "evidence_invalid"
    assert payload["producer_count"] == 0


def test_current_schema_rejects_unknown_root_fields(tmp_path: Path) -> None:
    from skillguard_v2.compact_contract import ContractError, validate_contract_source

    root = _root(tmp_path)
    source = _source()
    source["former_alias"] = {}
    with pytest.raises(ContractError) as raised:
        validate_contract_source(root, source)
    assert raised.value.code == "unknown_field"


def test_target_mutation_result_is_not_reinterpreted(tmp_path: Path) -> None:
    source = _source()
    source["checks"][0]["args"] = [  # type: ignore[index]
        "-c",
        "print('target_metric=0.91'); import sys; sys.exit(23)",
    ]
    root = _root(tmp_path)
    (root / ".skillguard").mkdir()
    (root / ".skillguard" / "contract-source.json").write_text(json.dumps(source), encoding="utf-8")
    state = tmp_path / "state"
    state.mkdir()

    code, payload = _run(root, _request(root, state, "change"), "change")

    assert code == 1
    assert payload["reason"] == "check_failed"
    assert payload["producer_count"] == 1
    assert "accepted_id" not in payload or payload["accepted_id"] is None
    assert any(
        b"target_metric=0.91" in path.read_bytes()
        for path in (state / "units").rglob("stdout.bin")
    )


def test_retired_assurance_solver_surface_is_absent() -> None:
    assert not (SCRIPT_ROOT / "skillguard_v2" / "assurance_diagnostics.py").exists()
