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
    publish_current_self_host_terminal_receipt,
    run_current_verifier,
    verify_current_self_host_terminal_receipt,
)
from skillguard_v2.contract_compiler import canonical_hash  # noqa: E402


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
