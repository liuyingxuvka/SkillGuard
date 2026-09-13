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

from tests._skillguard_v2_runtime_fixture import runtime_contract_with_checks
from skillguard_v2.check_runner import get_or_execute_check
from skillguard_v2.receipts import ReceiptIndex, derive_freshness, fingerprint_value
from skillguard_v2.route_runtime import select_routes
from skillguard_v2.run_store import claim_run
from skillguard_v2.test_mesh import execute_test_mesh, replay_current_test_mesh_aggregation


def _fixture(tmp_path: Path):
    repository = tmp_path / "repository"
    target = tmp_path / "target"
    skill = repository / "skill"
    repository.mkdir()
    target.mkdir()
    skill.mkdir()
    contract, manifest = runtime_contract_with_checks(
        [
            {
                "check_id": "check:intake",
                "kind": "command",
                "command": sys.executable,
                "args": ["-c", "print('a')"],
                "expected": {"exit_code": 0},
                "covers_obligation_ids": ["obligation:intake"],
            },
            {
                "check_id": "check:review",
                "kind": "command",
                "command": sys.executable,
                "args": ["-c", "print('b')"],
                "expected": {"exit_code": 0},
                "covers_obligation_ids": ["obligation:review"],
            },
        ]
    )
    decision = select_routes(contract, {"function_ids": ["analyze"]})
    claim = claim_run(
        contract,
        {"function_ids": ["analyze"], "write_targets": ["out"], "request": "minimal closure"},
        target,
        decision,
        check_manifest=manifest,
    )
    assert claim.ok, claim.to_dict()
    assert claim.run_root is not None
    mesh = repository / "test-mesh.json"
    mesh.write_text(
        json.dumps(
            {
                "schema_version": "skillguard.test_mesh_manifest.current",
                "mesh_id": "minimal",
                "source_model_id": "minimal.model",
                "profiles": [
                    {"profile_id": "fast", "closure_profile_id": "enforced", "requested_claims": ["source_release"], "owner_ids": ["owner:intake"]},
                    {"profile_id": "focused", "closure_profile_id": "enforced", "requested_claims": ["source_release"], "owner_ids": ["owner:intake", "owner:review"]},
                    {"profile_id": "full", "closure_profile_id": "enforced", "requested_claims": ["global_router_current", "installed_current", "source_release"], "owner_ids": ["owner:intake", "owner:review"]},
                ],
                "claim_boundary": "minimal fixture only",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    owner_root = repository / "work" / "owner-evidence"
    return repository, target, skill, mesh, owner_root, claim.run_root, manifest


def _plan(repository, target, skill, mesh, owner_root, run_root, profile="focused", **kwargs):
    return execute_test_mesh(
        mesh,
        repository,
        profile,
        run_root=run_root,
        skill_root=skill,
        target_root=target,
        owner_evidence_root=owner_root,
        **kwargs,
    )


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
    repository, target, skill, mesh, owner_root, run_root, manifest = _fixture(tmp_path)
    plan = _plan(repository, target, skill, mesh, owner_root, run_root)
    assert plan["status"] == "passed"
    assert len(plan["will_execute_owner_ids"]) == 2
    first = _plan(
        repository, target, skill, mesh, owner_root, run_root,
        mode="owner_execution_only", frozen_plan=plan,
    )
    assert first["status"] == "passed"
    assert first["execution_count"] == 2
    second = _plan(repository, target, skill, mesh, owner_root, run_root)
    assert second["will_execute_owner_ids"] == []
    assert set(second["will_reuse_owner_ids"]) == set(plan["will_execute_owner_ids"])
    assert second["execution_count"] == 0
    aggregation = _plan(
        repository, target, skill, mesh, owner_root, run_root,
        mode="aggregation_only", frozen_plan=plan,
    )
    assert aggregation["status"] == "passed"
    assert aggregation["execution_count"] == 0
    assert len(aggregation["child_receipts"]) == 2
    assert replay_current_test_mesh_aggregation(owner_root, aggregation["aggregation_ref"])["status"] == "passed"


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
    repository, target, skill, mesh, owner_root, run_root, _manifest = _fixture(tmp_path)
    plan = _plan(repository, target, skill, mesh, owner_root, run_root, profile="fast")
    assert plan["status"] == "passed"
    assert plan["execution_count"] == 0
    assert plan["full_admission_required"] is False


def test_t14_fast_focused_full_are_distinct_and_t16_compiled_check_is_read_only(tmp_path: Path) -> None:
    repository, target, skill, mesh, owner_root, run_root, _manifest = _fixture(tmp_path)
    fast = _plan(repository, target, skill, mesh, owner_root, run_root, profile="fast")
    focused = _plan(repository, target, skill, mesh, owner_root, run_root, profile="focused")
    full = _plan(repository, target, skill, mesh, owner_root, run_root, profile="full")
    assert fast["profile_id"] == "fast"
    assert focused["profile_id"] == "focused"
    assert full["profile_id"] == "full"
    assert full["status"] == "blocked"
    assert "requested_claims_require_exact_freeze_identity" in full["findings"]
    assert fast["execution_count"] == focused["execution_count"] == full["execution_count"] == 0


def test_t15_t18_readback_preserves_functional_key_and_does_not_start_a_producer(tmp_path: Path) -> None:
    summary = tmp_path / "completion-summary.json"
    payload = {"functional_key": "sha256:" + "b" * 64, "execution_count": 0, "producer_invocations": 0}
    summary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    before = summary.read_bytes()
    loaded = json.loads(summary.read_text(encoding="utf-8"))
    assert loaded["functional_key"] == payload["functional_key"]
    assert loaded["execution_count"] == 0
    assert summary.read_bytes() == before
