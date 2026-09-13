from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".agents" / "skills" / "skillguard" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import skillguard_v2.self_host as self_host  # noqa: E402
from skillguard_v2.self_host import (  # noqa: E402
    SelfHostError,
    SelfHostClaimContext,
    finalize_current_self_host_from_frozen_mesh,
    publish_current_self_host_terminal_receipt,
    run_current_verifier,
    verify_current_self_host_terminal_receipt,
)
from skillguard_v2.contract_compiler import canonical_hash  # noqa: E402
from skillguard_v2.test_mesh import _current_plan_hash  # noqa: E402


def _contract() -> dict[str, object]:
    return {
        "contract_hash": "CONTRACT-CURRENT",
        "source_fingerprints": {"model_export": "MODEL-CURRENT"},
        "content_impact_plan": {
            "inventory_hash": "SOURCE-CURRENT",
            "impact_graph_hash": "OWNER-PLAN-CURRENT",
        },
    }


def _manifest() -> dict[str, str]:
    return {"manifest_hash": "MANIFEST-CURRENT"}


def _terminal_report(**overrides: object) -> dict[str, object]:
    report: dict[str, object] = {
        "schema_version": "skillguard.self_host_result.v2",
        "status": "passed",
        "run_id": "run-current",
        "run_root": "work/verification/run-current",
        "execution_mode": "owner_check_verification",
        "source_identity_hash": "SOURCE-CURRENT",
        "model_identity_hash": "MODEL-CURRENT",
        "contract_hash": "CONTRACT-CURRENT",
        "manifest_hash": "MANIFEST-CURRENT",
        "owner_plan_hash": "OWNER-PLAN-CURRENT",
        "current_fingerprints": {"contract": {"raw": "CONTRACT-CURRENT"}},
        "executed_step_count": 1,
        "executed_steps": [
            {"step_id": "step:current", "receipt_ids": ["receipt:current"]}
        ],
        "target_execution_depth_receipt": {"receipt_id": "depth:current"},
        "closures": [
            {
                "profile": "enforced",
                "closure_receipt_id": "closure:current",
                "closure_hash": "CLOSURE-CURRENT",
                "verification": {"ok": True},
            }
        ],
    }
    report.update(overrides)
    report["report_hash"] = canonical_hash(report)
    return report


def test_current_self_host_terminal_receipt_is_published_with_exact_identities(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    skill_root = repository / ".agents" / "skills" / "skillguard"
    skill_root.mkdir(parents=True)
    report = _terminal_report()
    producer = repository / Path(str(report["run_root"]))
    producer.mkdir(parents=True)
    (producer / "self-host-result.json").write_text(
        json.dumps(report, sort_keys=True), encoding="utf-8"
    )

    receipt = publish_current_self_host_terminal_receipt(
        skill_root,
        report,
        contract=_contract(),
        manifest=_manifest(),
    )

    current = skill_root / ".skillguard" / "self-host" / "current"
    assert current.is_file()
    stored = json.loads(current.read_text(encoding="utf-8"))
    assert stored == receipt
    assert stored["status"] == "passed"
    assert stored["source_identity_hash"] == "SOURCE-CURRENT"
    assert stored["model_identity_hash"] == "MODEL-CURRENT"
    assert stored["contract_hash"] == "CONTRACT-CURRENT"
    assert stored["manifest_hash"] == "MANIFEST-CURRENT"
    assert stored["owner_plan_hash"] == "OWNER-PLAN-CURRENT"
    assert stored["receipt_hash"]


def test_current_self_host_terminal_receipt_allows_zero_execution_reuse(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    skill_root = repository / ".agents" / "skills" / "skillguard"
    skill_root.mkdir(parents=True)
    report = _terminal_report(
        execution_count=0,
        executed_step_count=0,
        executed_steps=[
            {
                "step_id": "step:current",
                "receipt_ids": ["receipt:current"],
                "check_execution_dispositions": ["reused_terminal_success"],
            }
        ],
    )
    producer = repository / Path(str(report["run_root"]))
    producer.mkdir(parents=True)
    (producer / "self-host-result.json").write_text(
        json.dumps(report, sort_keys=True), encoding="utf-8"
    )

    receipt = publish_current_self_host_terminal_receipt(
        skill_root,
        report,
        contract=_contract(),
        manifest=_manifest(),
    )

    assert receipt["executed_step_count"] == 0
    assert receipt["execution_count"] == 0
    assert receipt["executed_steps"][0]["check_execution_dispositions"] == [
        "reused_terminal_success"
    ]


def test_current_self_host_terminal_receipt_rejects_zero_execution_mixed_disposition(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    skill_root = repository / ".agents" / "skills" / "skillguard"
    skill_root.mkdir(parents=True)
    report = _terminal_report(
        execution_count=0,
        executed_step_count=0,
        executed_steps=[
            {
                "step_id": "step:current",
                "receipt_ids": ["receipt:current"],
                "check_execution_dispositions": ["executed_terminal_success"],
            }
        ],
    )
    producer = repository / Path(str(report["run_root"]))
    producer.mkdir(parents=True)
    (producer / "self-host-result.json").write_text(
        json.dumps(report, sort_keys=True), encoding="utf-8"
    )

    with pytest.raises(SelfHostError, match="zero-execution"):
        publish_current_self_host_terminal_receipt(
            skill_root,
            report,
            contract=_contract(),
            manifest=_manifest(),
        )


def test_aggregation_only_report_cannot_become_current_self_host_receipt(
    tmp_path: Path,
) -> None:
    with pytest.raises(SelfHostError, match="aggregation"):
        publish_current_self_host_terminal_receipt(
            tmp_path / "skillguard",
            _terminal_report(execution_mode="aggregation_only"),
            contract=_contract(),
            manifest=_manifest(),
        )


def test_current_self_host_receipt_rejects_identity_mismatch(
    tmp_path: Path,
) -> None:
    with pytest.raises(SelfHostError, match="identity"):
        publish_current_self_host_terminal_receipt(
            tmp_path / "skillguard",
            _terminal_report(contract_hash="FOREIGN-CONTRACT"),
            contract=_contract(),
            manifest=_manifest(),
        )


def test_current_self_host_receipt_rejects_tampered_producer_report(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    skill_root = repository / ".agents" / "skills" / "skillguard"
    skill_root.mkdir(parents=True)
    report = _terminal_report()
    producer = repository / Path(str(report["run_root"]))
    producer.mkdir(parents=True)
    tampered = dict(report)
    tampered["status"] = "failed"
    (producer / "self-host-result.json").write_text(
        json.dumps(tampered, sort_keys=True), encoding="utf-8"
    )

    with pytest.raises(SelfHostError, match="producer"):
        publish_current_self_host_terminal_receipt(
            skill_root,
            report,
            contract=_contract(),
            manifest=_manifest(),
        )


def test_current_self_host_receipt_consumer_requires_exact_current_and_producer(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    skill_root = repository / ".agents" / "skills" / "skillguard"
    skill_root.mkdir(parents=True)
    report = _terminal_report()
    producer = repository / Path(str(report["run_root"]))
    producer.mkdir(parents=True)
    (producer / "self-host-result.json").write_text(
        json.dumps(report, sort_keys=True), encoding="utf-8"
    )
    publish_current_self_host_terminal_receipt(
        skill_root,
        report,
        contract=_contract(),
        manifest=_manifest(),
    )

    consumed = verify_current_self_host_terminal_receipt(
        skill_root,
        contract=_contract(),
        manifest=_manifest(),
    )
    assert consumed["receipt_hash"]

    current = skill_root / ".skillguard" / "self-host" / "current"
    tampered = json.loads(current.read_text(encoding="utf-8"))
    tampered["contract_hash"] = "FOREIGN-CONTRACT"
    current.write_text(json.dumps(tampered, sort_keys=True), encoding="utf-8")
    with pytest.raises(SelfHostError, match="hash"):
        verify_current_self_host_terminal_receipt(
            skill_root,
            contract=_contract(),
            manifest=_manifest(),
        )


def test_current_self_host_receipt_consumer_fails_closed_when_missing(
    tmp_path: Path,
) -> None:
    with pytest.raises(SelfHostError, match="missing"):
        verify_current_self_host_terminal_receipt(
            tmp_path / "skillguard",
            contract=_contract(),
            manifest=_manifest(),
        )


def test_current_verifier_blocks_when_frozen_route_decision_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    skill_root = repository / ".agents" / "skills" / "skillguard"
    skill_root.mkdir(parents=True)
    context = SelfHostClaimContext(
        repository_root=repository,
        persistent_owner_root=repository / "owner-evidence",
        skill_root=skill_root,
        contract={},
        manifest={},
        test_mesh_boundary_checks=(),
        long_check_timeout_budget_checks=(),
        request={},
        target_input_paths=(),
        target_input_roles={},
        claim=SimpleNamespace(run_id="run-current"),
        run_root=repository / "work" / "run-current",
    )
    monkeypatch.setattr(
        self_host,
        "_prepare_current_self_host_claim",
        lambda *_args, **_kwargs: context,
    )

    with pytest.raises(SelfHostError, match="route"):
        run_current_verifier(repository, progress_callback=None)


def test_frozen_mesh_finalizer_does_not_claim_compile_or_execute_and_is_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    skill_root = repository / ".agents" / "skills" / "skillguard"
    run_root = repository / "work" / "verification" / "run-current"
    owner_root = repository / "work" / "verification" / "owners"
    skill_root.mkdir(parents=True)
    run_root.mkdir(parents=True)
    owner_root.mkdir(parents=True)
    contract = _contract()
    contract.update(
        {
            "skill_id": "skillguard",
            "maintenance_unit_id": "unit:skillguard",
            "source_fingerprints": {"model_export": "MODEL-CURRENT"},
        }
    )
    plan = {
        "schema_version": "skillguard.test_mesh_execution_plan.current",
        "artifact_type": "skillguard_test_mesh_execution_plan",
        "status": "passed",
        "mode": "plan_only",
        "requested_claims": ["source_release"],
        "maintenance_unit_id": "unit:skillguard",
        "member_skill_id": "skillguard",
        "source_identity_hash": "SOURCE-CURRENT",
        "impact_graph_hash": "OWNER-PLAN-CURRENT",
    }
    plan["plan_hash"] = _current_plan_hash(plan)
    aggregation_ref = {
        "path_token": "owner_evidence_root",
        "relative_path": "test-mesh/aggregations/current.json",
        "content_hash": "sha256:" + "1" * 64,
        "media_type": "application/json",
        "byte_count": 1,
    }
    aggregation = {
        "schema_version": "skillguard.test_mesh_aggregation.current",
        "status": "passed",
        "mode": "aggregation_only",
        "execution_count": 0,
        "maintenance_unit_id": "unit:skillguard",
        "member_skill_id": "skillguard",
        "plan_hash": plan["plan_hash"],
        "requested_claims": ["source_release"],
        "aggregation_id": "AGGREGATION-CURRENT",
        "aggregation_hash": "AGGREGATION-HASH-CURRENT",
        "child_receipts": [
            {
                "execution_owner_id": "owner:current",
                "check_ids": ["check:current"],
                "receipt_id": "receipt:current",
            }
        ],
    }
    monkeypatch.setattr(
        self_host,
        "load_run",
        lambda _path: {"run_id": "run-current"},
    )
    monkeypatch.setattr(self_host, "load_contract_snapshot", lambda _path: contract)
    monkeypatch.setattr(self_host, "load_check_manifest_snapshot", lambda _path: _manifest())
    monkeypatch.setattr(
        self_host,
        "_load_test_mesh_aggregation",
        lambda _root, _ref: aggregation,
    )
    monkeypatch.setattr(
        "skillguard_v2.test_mesh.replay_current_test_mesh_aggregation",
        lambda *_args, **_kwargs: {
            "status": "passed",
            "findings": [],
            "aggregation_id": "AGGREGATION-CURRENT",
        },
    )
    for name in ("compile_skill_contract", "claim_run", "get_or_execute_check"):
        monkeypatch.setattr(
            self_host,
            name,
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError(f"finalizer called forbidden {name}")
            ),
        )

    first = finalize_current_self_host_from_frozen_mesh(
        repository,
        run_root=run_root,
        frozen_plan=plan,
        aggregation_ref=aggregation_ref,
        owner_evidence_root=owner_root,
        skill_root=skill_root,
    )
    current = skill_root / ".skillguard" / "self-host" / "current"
    before = current.read_bytes()
    second = finalize_current_self_host_from_frozen_mesh(
        repository,
        run_root=run_root,
        frozen_plan=plan,
        aggregation_ref=aggregation_ref,
        owner_evidence_root=owner_root,
        skill_root=skill_root,
    )
    assert first["execution_mode"] == "frozen_plan_aggregation_finalize"
    assert second["report_hash"] == first["report_hash"]
    assert current.read_bytes() == before
