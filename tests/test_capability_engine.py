"""Focused tests for the read-only functional capability audit."""

from __future__ import annotations

import copy
import json
import contextlib
import io
import sys
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / ".agents" / "skills" / "skillguard" / "scripts"
TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from tests._skillguard_v2_runtime_fixture import runtime_contract_with_checks  # noqa: E402
from skillguard_v2.capability_engine import (  # noqa: E402
    _source_fingerprint,
    audit_capabilities,
    check_source_sync,
    validate_functional_closure,
)
import skillguard_v2.capability_engine as capability_engine  # noqa: E402
from skillguard_v2.check_runner import get_or_execute_check  # noqa: E402
from skillguard_v2.contract_compiler import wire_hash  # noqa: E402
from skillguard_v2.route_runtime import select_routes  # noqa: E402
from skillguard_v2.run_store import claim_run  # noqa: E402
from skillguard_v2.target_inputs import fingerprint_target_inputs  # noqa: E402
from checker_engine import (  # noqa: E402
    audit_capabilities as audit_capabilities_command,
    check_capability as check_capability_command,
    check_source_sync as check_source_sync_command,
)


ROLES = ("trigger", "intake", "route", "execute", "produce", "validate", "terminal")
FUNCTIONAL_CLOSURE_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / ".agents"
    / "skills"
    / "skillguard"
    / "assets"
    / "schemas"
    / "skillguard_functional_closure.schema.json"
)


def closure_payload(*, result: str = "pass", depth: str = "fixture") -> dict:
    evidence = [
        {
            "evidence_id": f"evidence-{index}",
            "execution_depth": depth,
            "environment_scope": "single",
            "quality_level": "deterministic",
            "assertion_categories": ["execution", "output", "validation", "terminal"],
            "result": result,
            "covered_stage_ids": [f"stage-{index}"],
        }
        for index, _role in enumerate(ROLES)
    ]
    stages = []
    for index, role in enumerate(ROLES):
        row = {
            "stage_id": f"stage-{index}",
            "role": role,
            "owner_id": "owner:native",
            "check_ids": ["check:native"],
            "evidence_ids": [f"evidence-{index}"],
        }
        if role == "route":
            row["native_route_id"] = "route:native"
        if role == "terminal":
            row["terminal_kind"] = "success"
        stages.append(row)
    evidence[0]["covered_quality_ids"] = ["quality:test"]
    return {
        "schema_version": "skillguard.functional_closure.current",
        "functional_closure_id": "closure:test",
        "target_skill_id": "target:test",
        "outcomes": [
            {
                "outcome_id": "outcome:test",
                "user_jobs": ["perform representative job"],
                "success_outputs": ["validated result"],
                "non_goals": ["unrelated work"],
                "quality_requirement_ids": ["quality:test"],
                "path_id": "path:test",
            }
        ],
        "closure_paths": [
            {"path_id": "path:test", "outcome_ids": ["outcome:test"], "stages": stages}
        ],
        "failure_modes": [],
        "quality_requirements": [
            {"quality_id": "quality:test", "description": "result is deterministic", "required": False, "evidence_ids": ["evidence-0"]}
        ],
        "evidence": evidence,
        "claim_boundary": "Target domain truth remains target-owned.",
    }


def test_functional_closure_schema_requires_current_receipt_for_pass() -> None:
    schema = json.loads(FUNCTIONAL_CLOSURE_SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["properties"]["schema_version"]["const"] == (
        "skillguard.functional_closure.current"
    )
    pass_requirement = schema["$defs"]["evidence"]["allOf"][0]
    assert pass_requirement["if"]["properties"]["result"]["const"] == "pass"
    assert set(pass_requirement["then"]["required"]) == {
        "source_fingerprint",
        "receipt_ref",
    }
    receipt_schema = schema["$defs"]["receipt_ref"]
    assert receipt_schema["additionalProperties"] is False
    assert {
        "maintenance_unit_id",
        "member_skill_id",
        "check_id",
        "execution_owner_id",
        "request_fingerprint",
        "target_input_fingerprint",
        "toolchain_fingerprint",
        "execution_environment_fingerprint",
        "dependency_receipts",
        "cleanup_confirmed",
        "receipt_id",
        "receipt_hash",
    }.issubset(receipt_schema["required"])


@pytest.fixture
def canonical_receipt_case(tmp_path: Path) -> dict[str, object]:
    """Create one real current producer receipt in a private temporary store."""

    target = tmp_path / "repository"
    target.mkdir()
    (target / "SKILL.md").write_text("current\n", encoding="utf-8")
    owner_root = tmp_path / "owner-evidence"
    contract, manifest = runtime_contract_with_checks(
        [
            {
                "check_id": "check:native",
                "semantic_check_id": "check:native",
                "kind": "command",
                "command": sys.executable,
                "args": ["-c", "raise SystemExit(0)"],
                "cwd_token": "target_root",
                "timeout_seconds": 5,
                "expected": {"exit_code": 0},
                "covers_obligation_ids": ["obligation:intake"],
            }
        ]
    )
    request = {
        "function_ids": ["analyze"],
        "write_targets": ["out"],
        "request": "functional closure canonical receipt bridge",
        "target_input_paths": ["SKILL.md"],
        "target_input_fingerprint": fingerprint_target_inputs(
            target, ["SKILL.md"]
        )["fingerprint"],
    }
    decision = select_routes(contract, request)
    claim = claim_run(
        contract,
        request,
        target,
        decision,
        check_manifest=manifest,
    )
    assert claim.ok, claim.to_dict()
    assert claim.run_root is not None
    declared = manifest["checks"][0]
    execution = get_or_execute_check(
        declared,
        skill_root=target,
        target_root=target,
        repository_root=target,
        run_root=claim.run_root,
        step_id="step:intake",
        owner_evidence_root=owner_root,
    )
    receipt = execution["execution_receipt"]
    document_ref = execution["execution_receipt_ref"]
    receipt_ref = {
        "schema_version": "skillguard.functional_evidence_receipt_ref.current",
        "document_ref": document_ref,
        "maintenance_unit_id": receipt["maintenance_unit_id"],
        "member_skill_id": receipt["member_skill_id"],
        "check_id": declared["check_id"],
        "semantic_check_id": declared["semantic_check_id"],
        "execution_owner_id": receipt["execution_owner_id"],
        "request_fingerprint": wire_hash(
            {
                "target_input_fingerprint": receipt["target_input_fingerprint"],
                "target_input_role_fingerprints": receipt[
                    "target_input_role_fingerprints"
                ],
            }
        ),
        "target_input_paths": ["SKILL.md"],
        "target_input_roles": {},
        "check_manifest_hash": manifest["manifest_hash"],
        "projection_declaration_hash": declared["projection_declaration_hash"],
        "execution_key": receipt["execution_key"],
        "owner_declaration_hash": receipt["owner_declaration_hash"],
        "owner_input_projection_hash": receipt["owner_input_projection_hash"],
        "input_components": receipt["input_components"],
        "dependency_receipts": receipt["dependency_receipts"],
        "target_input_fingerprint": receipt["target_input_fingerprint"],
        "target_input_role_fingerprints": receipt[
            "target_input_role_fingerprints"
        ],
        "toolchain_fingerprint": receipt["toolchain_fingerprint"],
        "execution_environment_fingerprint": receipt[
            "execution_environment_fingerprint"
        ],
        "impact_policy_id": receipt["impact_policy_id"],
        "status": receipt["status"],
        # A canonical success is only published after its termination sidecar
        # proves cleanup; the validator independently replays that sidecar.
        "cleanup_confirmed": True,
        "receipt_id": receipt["receipt_id"],
        "receipt_hash": receipt["receipt_hash"],
    }
    payload = closure_payload()
    source_fingerprint = _source_fingerprint(target)
    payload["source_fingerprint"] = source_fingerprint
    for evidence in payload["evidence"]:
        evidence["source_fingerprint"] = source_fingerprint
        evidence["receipt_ref"] = copy.deepcopy(receipt_ref)
    return {
        "payload": payload,
        "target": target,
        "repository": target,
        "contract": contract,
        "manifest": manifest,
        "owner_root": owner_root,
    }


def _validate_canonical_case(case: dict[str, object], **overrides: object) -> dict:
    kwargs = {
        "target_root": case["target"],
        "repository_root": case["repository"],
        "owner_evidence_root": case["owner_root"],
        "contract": case["contract"],
        "check_manifest": case["manifest"],
        "claim_scope": "routine",
        "require_native_bindings": False,
    }
    kwargs.update(overrides)
    return validate_functional_closure(case["payload"], **kwargs)


def test_routine_positive_path_requires_verified_current_receipt(
    canonical_receipt_case: dict[str, object],
) -> None:
    report = validate_functional_closure(
        canonical_receipt_case["payload"],
        target_root=canonical_receipt_case["target"],
        repository_root=canonical_receipt_case["repository"],
        owner_evidence_root=canonical_receipt_case["owner_root"],
        contract=canonical_receipt_case["contract"],
        check_manifest=canonical_receipt_case["manifest"],
        claim_scope="routine",
        require_native_bindings=False,
    )
    assert report["decision"] == "pass"
    assert report["gap_codes"] == []
    assert {row["receipt_decision"] for row in report["evidence_axes"]} == {
        "verified"
    }


def test_former_v1_closure_is_rejection_only() -> None:
    payload = closure_payload()
    payload["schema_version"] = "skillguard.functional_closure.v1"
    report = validate_functional_closure(payload, require_native_bindings=False)
    assert report["decision"] == "block"
    assert "unsupported-functional-closure-schema" in report["gap_codes"]


def test_caller_authored_pass_without_producer_receipt_is_blocked() -> None:
    report = validate_functional_closure(
        closure_payload(), claim_scope="routine", require_native_bindings=False
    )
    assert report["decision"] == "block"
    assert "evidence-receipt-ref-missing" in report["gap_codes"]
    assert {row["result_decision"] for row in report["evidence_axes"]} == {
        "blocked"
    }


def test_functional_claim_cannot_bypass_missing_reverse_surface_inventory(
    tmp_path: Path,
) -> None:
    """A receipt-backed closure is still blocked without the current denominator."""

    target = tmp_path / "target"
    (target / ".skillguard").mkdir(parents=True)
    (target / "SKILL.md").write_text("current target\n", encoding="utf-8")
    payload = closure_payload()
    payload["target_skill_id"] = "target:test"
    contract = {
        "depth_profile": {
            "target_skill_id": "target:test",
            "native_check_ids": ["check:native"],
            "model_deepening_check_id": "check:deepening",
            "surface_inventory": {"path": ".skillguard/surface-inventory.json"},
        }
    }
    report = validate_functional_closure(
        payload,
        target_root=target,
        contract=contract,
        require_native_bindings=False,
        require_surface_inventory=True,
    )
    assert report["decision"] == "block"
    assert "surface_inventory_file_missing" in report["gap_codes"]
    assert report["surface_inventory"]["status"] == "blocked"


@pytest.mark.parametrize(
    ("field", "code"),
    [
        ("document_ref", "evidence-receipt-document-ref-missing"),
        ("receipt_hash", "evidence-receipt-hash-missing"),
        ("execution_owner_id", "evidence-receipt-owner-missing"),
        ("maintenance_unit_id", "evidence-receipt-unit-missing"),
        ("member_skill_id", "evidence-receipt-member-missing"),
        ("check_id", "evidence-receipt-check-missing"),
        ("request_fingerprint", "evidence-receipt-request-missing"),
        ("target_input_fingerprint", "evidence-receipt-input-missing"),
        ("toolchain_fingerprint", "evidence-receipt-toolchain-missing"),
        (
            "execution_environment_fingerprint",
            "evidence-receipt-environment-missing",
        ),
        ("dependency_receipts", "evidence-receipt-dependency-missing"),
        ("cleanup_confirmed", "evidence-receipt-cleanup-missing"),
    ],
)
def test_pass_rejects_missing_exact_receipt_identity(
    canonical_receipt_case: dict[str, object], field: str, code: str
) -> None:
    canonical_receipt_case["payload"]["evidence"][0]["receipt_ref"].pop(field)
    report = _validate_canonical_case(canonical_receipt_case)
    assert report["decision"] == "block"
    assert code in report["gap_codes"]


def test_pass_requires_source_fingerprint() -> None:
    payload = closure_payload()
    report = validate_functional_closure(payload, require_native_bindings=False)
    assert report["decision"] == "block"
    assert "evidence-source-fingerprint-missing" in report["gap_codes"]


def test_cross_unit_receipt_projection_is_blocked(
    canonical_receipt_case: dict[str, object],
) -> None:
    canonical_receipt_case["payload"]["evidence"][0]["receipt_ref"][
        "maintenance_unit_id"
    ] = "unit:foreign"
    report = _validate_canonical_case(canonical_receipt_case)
    assert report["decision"] == "block"
    assert "evidence-receipt-cross-unit" in report["gap_codes"]


@pytest.mark.parametrize(
    ("field", "code"),
    [
        ("receipt_hash", "evidence-receipt-hash-mismatch"),
        ("execution_owner_id", "evidence-receipt-owner-mismatch"),
        ("member_skill_id", "evidence-receipt-member-mismatch"),
        ("request_fingerprint", "evidence-receipt-request-mismatch"),
        ("toolchain_fingerprint", "evidence-receipt-toolchain-mismatch"),
        (
            "execution_environment_fingerprint",
            "evidence-receipt-environment-mismatch",
        ),
    ],
)
def test_pass_rejects_forged_receipt_projection(
    canonical_receipt_case: dict[str, object], field: str, code: str
) -> None:
    canonical_receipt_case["payload"]["evidence"][0]["receipt_ref"][field] = (
        "sha256:" + "0" * 64
        if field not in {"execution_owner_id", "member_skill_id"}
        else "foreign:" + field
    )
    report = _validate_canonical_case(canonical_receipt_case)
    assert report["decision"] == "block"
    assert code in report["gap_codes"]


def test_stale_target_input_invalidates_canonical_receipt(
    canonical_receipt_case: dict[str, object],
) -> None:
    target = canonical_receipt_case["target"]
    (target / "SKILL.md").write_text("changed after receipt\n", encoding="utf-8")
    current_source = _source_fingerprint(target)
    canonical_receipt_case["payload"]["source_fingerprint"] = current_source
    for evidence in canonical_receipt_case["payload"]["evidence"]:
        evidence["source_fingerprint"] = current_source
    report = _validate_canonical_case(canonical_receipt_case)
    assert report["decision"] == "block"
    assert "evidence-receipt-input-stale" in report["gap_codes"]


def test_receipt_replay_includes_installation_component_in_exact_owner_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = {
        "component_id": "component:runtime_source:base",
        "component_hash": "sha256:" + "1" * 64,
    }
    installed = {
        "component_id": "component:active_installed_skill_trees",
        "component_hash": "sha256:" + "2" * 64,
    }
    monkeypatch.setattr(
        capability_engine,
        "inspect_current_owner_input_projection",
        lambda **_: {
            "components": [base],
            "owner_input_projection_hash": wire_hash([base]),
        },
    )
    monkeypatch.setattr(
        capability_engine,
        "_installed_runtime_input_component",
        lambda *_args, **_kwargs: installed,
    )
    monkeypatch.setattr(
        capability_engine,
        "check_toolchain_identity",
        lambda _check: {
            "toolchain_fingerprint": "sha256:" + "3" * 64,
            "execution_environment_fingerprint": "sha256:" + "4" * 64,
        },
    )
    receipt = {
        "receipt_id": "sha256:" + "5" * 64,
        "receipt_hash": "sha256:" + "6" * 64,
        "execution_owner_id": "owner:test:installed",
        "owner_declaration_hash": "sha256:" + "7" * 64,
        "input_components": sorted([base, installed], key=lambda row: row["component_id"]),
        "owner_input_projection_hash": wire_hash(
            sorted([base, installed], key=lambda row: row["component_id"])
        ),
        "impact_policy_id": "policy:test",
        "check_id": "check:test:installed",
        "toolchain_fingerprint": "sha256:" + "3" * 64,
        "execution_environment_fingerprint": "sha256:" + "4" * 64,
        "dependency_receipts": [],
        "maintenance_unit_id": "unit:test",
        "member_skill_id": "skillguard",
        "target_input_fingerprint": "",
    }
    owner = {
        "execution_owner_id": "owner:test:installed",
        "owner_declaration_hash": "sha256:" + "7" * 64,
        "depends_on_owner_ids": [],
    }
    findings = capability_engine._owner_receipt_freshness_findings(
        receipt,
        evidence_id="e-install",
        repository_root=Path("."),
        manifest={"content_impact_plan": {"policy_id": "policy:test"}},
        check_index={
            "check:test:installed": {
                "check_id": "check:test:installed",
                "execution_owner_id": "owner:test:installed",
                "input_selectors": [
                    {"kind": "install_disposition", "install_disposition": "copy"}
                ],
            }
        },
        owner_index={"owner:test:installed": owner},
        owner_evidence_root=Path("."),
        root_target_input_fingerprint="",
        visited=frozenset(),
    )
    assert findings == []


def test_cleanup_unconfirmed_projection_is_never_reusable(
    canonical_receipt_case: dict[str, object],
) -> None:
    canonical_receipt_case["payload"]["evidence"][0]["receipt_ref"][
        "cleanup_confirmed"
    ] = False
    report = _validate_canonical_case(canonical_receipt_case)
    assert report["decision"] == "block"
    assert "evidence-receipt-cleanup-unconfirmed" in report["gap_codes"]


@pytest.mark.parametrize(
    ("mutator", "code"),
    [
        (lambda payload: payload["outcomes"][0].pop("success_outputs"), "missing-success-output"),
        (lambda payload: payload["closure_paths"][0]["stages"].pop(3), "path-stage-role-missing"),
        (lambda payload: payload["closure_paths"][0]["stages"].__setitem__(0, {"stage_id": "stage-0", "role": "trigger", "owner_id": "", "check_ids": [], "evidence_ids": []}), "path-stage-owner-missing"),
    ],
)
def test_structural_gaps_are_stable_and_fail_closed(mutator, code: str) -> None:
    payload = closure_payload()
    mutator(payload)
    report = validate_functional_closure(payload, require_native_bindings=False)
    assert report["decision"] == "block"
    assert code in report["gap_codes"]


def test_functional_scope_does_not_promote_fixture_only_evidence() -> None:
    report = validate_functional_closure(
        closure_payload(),
        claim_scope="functional",
        require_native_bindings=False,
    )
    assert report["decision"] == "block"
    assert "insufficient-execution-depth" in report["gap_codes"]


def test_release_scope_requires_real_end_to_end_evidence(
    canonical_receipt_case: dict[str, object],
) -> None:
    for evidence in canonical_receipt_case["payload"]["evidence"]:
        evidence["execution_depth"] = "real_e2e"
    report = _validate_canonical_case(canonical_receipt_case, claim_scope="release")
    assert report["decision"] == "pass"


def test_highest_quality_scope_requires_human_quality_evidence(
    canonical_receipt_case: dict[str, object],
) -> None:
    payload = canonical_receipt_case["payload"]
    for evidence in payload["evidence"]:
        evidence["execution_depth"] = "real_e2e"
    payload["quality_requirements"][0]["required"] = True
    payload["evidence"][0]["assertion_categories"].append("quality")
    report = _validate_canonical_case(
        canonical_receipt_case, claim_scope="highest-quality"
    )
    assert report["decision"] == "block"
    assert "insufficient-quality-evidence" in report["gap_codes"]


def test_recoverable_failure_needs_current_recovery_path_and_evidence() -> None:
    payload = closure_payload()
    payload["closure_paths"].append(
        {
            "path_id": "path:recovery",
            "outcome_ids": ["outcome:test"],
            "stages": [
                {
                    "stage_id": "recovery-terminal",
                    "role": "terminal",
                    "owner_id": "owner:native",
                    "check_ids": ["check:native"],
                    "evidence_ids": ["evidence-0"],
                    "terminal_kind": "blocked",
                }
            ],
        }
    )
    payload["failure_modes"].append(
        {
            "failure_id": "failure:test",
            "stage_id": "stage-3",
            "detector": "native detector",
            "disposition": "recover",
            "recovery_path_id": "path:recovery",
            "terminal_kind": "blocked",
            "evidence_ids": ["evidence-0"],
        }
    )
    report = validate_functional_closure(payload, claim_scope="routine", require_native_bindings=False)
    assert report["decision"] == "block"
    assert "path-stage-role-missing" in report["gap_codes"]


def test_stale_source_fingerprint_blocks(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "SKILL.md").write_text("current", encoding="utf-8")
    payload = closure_payload()
    payload["source_fingerprint"] = "sha256:" + "0" * 64
    report = validate_functional_closure(payload, target_root=target, require_native_bindings=False)
    assert report["decision"] == "block"
    assert "stale-capability-evidence" in report["gap_codes"]


def test_portfolio_preserves_missing_child_truth(tmp_path: Path) -> None:
    good = tmp_path / "good"
    bad = tmp_path / "bad"
    (good / ".skillguard").mkdir(parents=True)
    (bad / ".skillguard").mkdir(parents=True)
    (good / "SKILL.md").write_text("good", encoding="utf-8")
    (bad / "SKILL.md").write_text("bad", encoding="utf-8")
    (good / ".skillguard" / "functional-closure.json").write_text(json.dumps(closure_payload()), encoding="utf-8")
    report = audit_capabilities(tmp_path, claim_scope="routine")
    assert report["decision"] == "block"
    assert report["counts"]["active"] == 2
    assert any(row.get("status") == "blocked" for row in report["rows"])


def test_retired_registry_entry_is_explicitly_excluded() -> None:
    registry = {
        "schema_version": "skillguard.portfolio_registry.v1",
        "registry_id": "registry:test",
        "entries": [
            {
                "skill_id": "retired-skill",
                "lifecycle": "retired",
                "retirement_reason": "superseded",
                "canonical_source": {"root": "<private-root>", "skill_path": "retired"},
                "installed_path": "<private-root>/installed",
                "repository_identity": "private:retired",
                "visibility": "private",
                "release_policy": "no_publish",
            }
        ],
        "claim_boundary": "private registry only",
    }
    report = check_source_sync(registry)
    assert report["decision"] == "pass"
    assert report["retired_excluded"] == ["retired-skill"]


def test_source_sync_blocks_source_to_installed_functional_downgrade(tmp_path: Path) -> None:
    source = tmp_path / "source"
    installed = tmp_path / "installed"
    (source / ".skillguard").mkdir(parents=True)
    (installed / ".skillguard").mkdir(parents=True)
    (source / "SKILL.md").write_text("source", encoding="utf-8")
    (installed / "SKILL.md").write_text("installed", encoding="utf-8")
    shallow = closure_payload(depth="fixture")
    deep = closure_payload(depth="production_observed")
    (source / ".skillguard" / "functional-closure.json").write_text(json.dumps(shallow), encoding="utf-8")
    (installed / ".skillguard" / "functional-closure.json").write_text(json.dumps(deep), encoding="utf-8")
    registry = {
        "schema_version": "skillguard.portfolio_registry.v1",
        "registry_id": "registry:test",
        "entries": [
            {
                "skill_id": "active-skill",
                "lifecycle": "active",
                "canonical_source": {"root": str(tmp_path), "skill_path": "source"},
                "installed_path": str(installed),
                "repository_identity": "private:active",
                "visibility": "private",
                "release_policy": "private_only",
            }
        ],
        "claim_boundary": "private registry only",
    }
    report = check_source_sync(registry)
    assert report["decision"] == "block"
    assert "source-to-installed-downgrade" in report["gap_codes"]
    rendered = json.dumps(report)
    assert str(source) not in rendered
    assert str(installed) not in rendered


def test_source_sync_accepts_normalized_json_and_line_ending_drift(tmp_path: Path) -> None:
    source = tmp_path / "source"
    installed = tmp_path / "installed"
    (source / ".skillguard").mkdir(parents=True)
    (installed / ".skillguard").mkdir(parents=True)
    for root in (source, installed):
        (root / "SKILL.md").write_bytes(b"skill\n")
        for name, value in {
            "contract-source.json": {"schema_version": "current"},
            "check-manifest.json": {"checks": []},
            "functional-closure.json": closure_payload(),
        }.items():
            text = json.dumps(value, indent=2, sort_keys=True)
            if root is installed:
                text = text.replace("\n", "\r\n")
            (root / ".skillguard" / name).write_bytes(text.encode("utf-8"))
    registry = {
        "schema_version": "skillguard.portfolio_registry.v1",
        "registry_id": "registry:test",
        "entries": [{
            "skill_id": "active-skill", "lifecycle": "active",
            "canonical_source": {"root": str(tmp_path), "skill_path": "source"},
            "installed_path": str(installed), "repository_identity": "private:active",
            "visibility": "private", "release_policy": "private_only",
        }],
        "claim_boundary": "private registry only",
    }
    report = check_source_sync(registry)
    assert report["decision"] == "pass"


def test_registered_command_paths_emit_json_without_target_execution(tmp_path: Path) -> None:
    target = tmp_path / "target"
    (target / ".skillguard").mkdir(parents=True)
    (target / "SKILL.md").write_text("target", encoding="utf-8")
    (target / ".skillguard" / "functional-closure.json").write_text(json.dumps(closure_payload()), encoding="utf-8")

    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        exit_code = check_capability_command(["--target", "target", "--repository-root", str(tmp_path), "--claim-scope", "routine"])
    assert exit_code == 1  # no current contract/check manifest is an explicit blocker
    assert json.loads(stream.getvalue())["artifact_type"] == "skillguard_capability_audit"

    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        exit_code = audit_capabilities_command(["--root", str(tmp_path), "--claim-scope", "routine"])
    assert exit_code == 1
    assert json.loads(stream.getvalue())["artifact_type"] == "skillguard_capability_portfolio_audit"

    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps({
        "schema_version": "skillguard.portfolio_registry.v1",
        "registry_id": "registry:test",
        "entries": [{
            "skill_id": "retired-skill", "lifecycle": "retired", "retirement_reason": "superseded",
            "canonical_source": {"root": "<private-root>", "skill_path": "retired"},
            "installed_path": "<private-root>/installed", "repository_identity": "private:retired",
            "visibility": "private", "release_policy": "no_publish",
        }],
        "claim_boundary": "private registry only",
    }), encoding="utf-8")
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        exit_code = check_source_sync_command(["--registry", str(registry_path)])
    assert exit_code == 0
    report = json.loads(stream.getvalue())
    assert report["artifact_type"] == "skillguard_source_sync_audit"
    assert "<private-root>" not in stream.getvalue()
