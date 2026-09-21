from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.test_fixed_preflight_units import _root, _source

from skillguard_v2.compact_contract import ContractError, validate_contract_source
from skillguard_v2.contract_compiler import compile_skill_contract
from skillguard_v2.consumer_distribution import audit_consumer_distribution, build_consumer_distribution


def _current_root(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    root = _root(tmp_path)
    control = root / ".skillguard"
    control.mkdir()
    source = _source()
    (control / "contract-source.json").write_text(json.dumps(source), encoding="utf-8")
    return root, source


def test_complete_current_trio_is_the_only_success_shape(tmp_path: Path) -> None:
    root, source = _current_root(tmp_path)
    result = compile_skill_contract(root, write=True)
    assert result.ok, result.to_dict()
    assert validate_contract_source(root, source).source["schema_version"] == "skillguard.skill_contract.v3"
    assert (root / ".skillguard" / "compiled-contract.json").is_file()
    assert (root / ".skillguard" / "check-manifest.json").is_file()


def test_incomplete_current_trio_is_blocked_without_fallback(tmp_path: Path) -> None:
    root, _source_payload = _current_root(tmp_path)
    result = compile_skill_contract(root, write=True)
    assert result.ok
    (root / ".skillguard" / "check-manifest.json").unlink()
    blocked = compile_skill_contract(root, write=False)
    assert not blocked.ok
    assert not (root / ".skillguard" / "check-manifest.json").exists()


def test_old_pair_only_is_blocked_and_cannot_manufacture_success(tmp_path: Path) -> None:
    root, _source_payload = _current_root(tmp_path)
    old = root / ".skillguard" / "work-contract.json"
    old.write_text(json.dumps({"schema_version": "skillguard.work_contract.v1"}), encoding="utf-8")
    assert not compile_skill_contract(root, write=False).ok


def test_old_lifecycle_field_is_rejected_from_current_source(tmp_path: Path) -> None:
    root, source = _current_root(tmp_path)
    source["v1_runtime_authority"] = {"status": "retired"}
    with pytest.raises(ContractError) as raised:
        validate_contract_source(root, source)
    assert raised.value.code == "unknown_field"


def test_model_identity_mismatch_blocks_even_when_envelopes_are_resigned(tmp_path: Path) -> None:
    root, source = _current_root(tmp_path)
    source["model_id"] = "retired-model"
    with pytest.raises(ContractError) as raised:
        validate_contract_source(root, source)
    assert raised.value.code == "unknown_field"


def test_former_runtime_residual_blocks_but_current_run_directory_does_not(tmp_path: Path) -> None:
    root, _source_payload = _current_root(tmp_path)
    repository_root = Path(__file__).resolve().parents[1]
    result = compile_skill_contract(repository_root, write=False)
    assert result.ok
    skill_source = repository_root / ".agents" / "skills" / "skillguard"
    report = build_consumer_distribution(skill_source, tmp_path / "consumer", result.compiled_contract)
    assert report["status"] == "passed", report
    (root / ".skillguard" / "work-contract.json").write_text("{}", encoding="utf-8")
    assert not (tmp_path / "consumer" / ".skillguard").exists()


def test_former_history_is_not_a_live_audit_surface(tmp_path: Path) -> None:
    root, _source_payload = _current_root(tmp_path)
    repository_root = Path(__file__).resolve().parents[1]
    result = compile_skill_contract(repository_root, write=False)
    assert result.ok
    stage = tmp_path / "consumer"
    skill_source = repository_root / ".agents" / "skills" / "skillguard"
    built = build_consumer_distribution(skill_source, stage, result.compiled_contract)
    assert built["status"] == "passed", built
    assert audit_consumer_distribution(stage)["status"] == "passed"


def test_isolated_root_never_escapes_to_parent_or_requested_repository(tmp_path: Path) -> None:
    root, source = _current_root(tmp_path)
    with pytest.raises(ContractError):
        validate_contract_source(root, {**source, "inputs": [{"id": "x", "path": "../outside", "required": True}]})


def test_no_live_conversion_or_retirement_schema_surface_exists() -> None:
    skill_root = Path(__file__).resolve().parents[1] / ".agents" / "skills" / "skillguard"
    assert not (skill_root / "scripts" / "skillguard_v1_retirement.py").exists()
    assert not (skill_root / "scripts" / "skillguard_legacy_depth_upgrade.py").exists()


def test_current_projection_names_the_exact_former_file_when_it_reappears(tmp_path: Path) -> None:
    root, source = _current_root(tmp_path)
    source["former_alias"] = True
    with pytest.raises(ContractError) as raised:
        validate_contract_source(root, source)
    assert raised.value.code == "unknown_field"
