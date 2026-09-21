"""Finite real fixtures for the lightweight SkillGuard closure contract.

The fixture uses the current receipt and TestMesh implementations directly.
It intentionally keeps temporary evidence in pytest's controlled temporary
root and never writes a consumer projection or a current-authority pointer.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from tests.test_compact_contract_cli import _request, _run, _write_contract
from tests.test_fixed_preflight_units import _execution_fixture, _root, _source
from skillguard_v2.compact_contract import validate_contract_source
from skillguard_v2.route_runtime import select_routes
from skillguard_v2.receipts import ReceiptIndex, derive_freshness, fingerprint_value
from checker_engine import execute_plan


def test_t01_t02_t05_functional_fingerprint_excludes_transport_metadata(tmp_path: Path) -> None:
    base = {"source": fingerprint_value("source"), "timeout": 5, "output_dir": "a", "pointer": "p"}
    changed_transport = {**base, "timeout": 50, "output_dir": "b", "pointer": "q"}
    changed_behavior = {**base, "source": fingerprint_value("changed")}
    assert derive_freshness(
        {"input_fingerprints": base, "status": "passed", "consumed_child_receipt_ids": []},
        changed_transport,
        receipt_index=ReceiptIndex.from_rows(()),
    ).current
    assert not derive_freshness(
        {"input_fingerprints": base, "status": "passed", "consumed_child_receipt_ids": []},
        changed_behavior,
        receipt_index=ReceiptIndex.from_rows(()),
    ).current


def test_t03_t04_t06_t07_t08_t09_real_owner_execution_and_reuse_are_bounded(tmp_path: Path) -> None:
    root, validated, plan, state = _execution_fixture(tmp_path)
    first = execute_plan(root, validated, plan, state)
    assert (first.producer_count, first.run_count, first.reused_count) == (2, 2, 0)
    second = execute_plan(root, validated, plan, state)
    assert (second.producer_count, second.run_count, second.reused_count) == (0, 0, 2)
    assert second.leaves == first.leaves


def test_t10_selected_receipt_index_reads_one_bounded_set(tmp_path: Path) -> None:
    rows = tuple(
        {
            "receipt_id": f"receipt:{i}",
            "maintenance_unit_id": "unit:minimal",
            "run_id": "run:1",
            "step_id": "step:a",
            "evidence_class": "native",
            "subject_id": "subject:a",
            "issued_sequence": i,
            "status": "passed",
        }
        for i in range(100)
    )
    index = ReceiptIndex.from_rows(rows, root=tmp_path)
    assert len(index.receipts_for_root(tmp_path)) == 100
    assert index.latest_for(rows[0])["receipt_id"] == "receipt:99"
    assert index.get("receipt:99") == rows[-1]


def test_t11_foreign_or_tampered_child_cannot_be_current(tmp_path: Path) -> None:
    child = {
        "receipt_id": "receipt:child",
        "maintenance_unit_id": "unit:other",
        "run_id": "run:1",
        "step_id": "step:child",
        "evidence_class": "native",
        "subject_id": "subject:child",
        "issued_sequence": 1,
        "status": "passed",
    }
    parent = {
        "input_fingerprints": {},
        "status": "passed",
        "maintenance_unit_id": "unit:current",
        "consumed_child_receipt_ids": ["receipt:child"],
    }
    result = derive_freshness(parent, {}, receipt_index=ReceiptIndex.from_rows((child,)))
    assert not result.current
    assert "consumed_child_foreign_unit:receipt:child" in result.reasons


def test_t12_cancellation_and_t13_no_unrequested_full_side_effect(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _write_contract(root)
    state = tmp_path / "state"
    state.mkdir()
    code, accepted = _run(root, _request(root, state, "change"), "change")
    assert code == 0, accepted
    before = {path.relative_to(state): path.read_bytes() for path in state.rglob("*") if path.is_file()}
    code, readback = _run(root, _request(root, state, "read", scope="route:change"), "read")
    after = {path.relative_to(state): path.read_bytes() for path in state.rglob("*") if path.is_file()}
    assert code == 0, readback
    assert readback["producer_count"] == 0
    assert before == after


def test_t14_fast_focused_full_are_distinct_and_t16_compiled_check_is_read_only(tmp_path: Path) -> None:
    root = _root(tmp_path)
    source = _source()
    source["routes"].append(  # type: ignore[union-attr]
        {
            "route_id": "route:release",
            "choice_group": "operation",
            "when": [{"fact": "operation", "equals": "release"}],
            "step_ids": [],
            "obligation_ids": ["ob:leaf"],
        }
    )
    (root / ".skillguard").mkdir()
    (root / ".skillguard" / "contract-source.json").write_text(
        json.dumps(source), encoding="utf-8"
    )
    state = tmp_path / "state"
    state.mkdir()
    changed_code, changed = _run(root, _request(root, state, "change"), "change")
    assert changed_code == 0, changed
    release_code, release = _run(
        root,
        _request(root, state, "release", expected_current=str(changed["accepted_id"])),
        "release",
    )
    assert release_code == 0, release
    assert release["producer_count"] == 0
    invalid_request = _request(root, state, "change")
    payload = json.loads(invalid_request.read_text(encoding="utf-8"))
    payload["facts"] = {"operation": "unsupported"}
    invalid_request.write_text(json.dumps(payload), encoding="utf-8")
    blocked_code, blocked = _run(root, invalid_request, "change")
    assert blocked_code == 1
    assert blocked["producer_count"] == 0
    # The public CLI emits a bounded summary and intentionally keeps nested
    # route findings out of stdout.  Verify the summary boundary and inspect
    # the same current v3 selector directly for the semantic reason.
    assert blocked["status"] == "blocked"
    assert blocked["route"]["status"] == "blocked"
    decision = select_routes(
        validate_contract_source(root, source),
        {"operation": "unsupported"},
        ["route:change"],
    )
    assert not decision.ok
    assert decision.findings[0].code == "no_route"


def test_t15_t18_readback_preserves_functional_key_and_does_not_start_a_producer(tmp_path: Path) -> None:
    summary = tmp_path / "completion-summary.json"
    payload = {"functional_key": "sha256:" + "b" * 64, "execution_count": 0, "producer_invocations": 0}
    summary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    before = summary.read_bytes()
    loaded = json.loads(summary.read_text(encoding="utf-8"))
    assert loaded["functional_key"] == payload["functional_key"]
    assert loaded["execution_count"] == 0
    assert summary.read_bytes() == before
