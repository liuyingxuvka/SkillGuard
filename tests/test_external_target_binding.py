"""Explicit current root/projection tests for consumer distributions."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from tests.test_fixed_preflight_units import _root, _source

SCRIPT_ROOT = Path(__file__).resolve().parents[1] / ".agents" / "skills" / "skillguard" / "scripts"


def _repository_projection(tmp_path: Path):
    from skillguard_v2.contract_compiler import compile_skill_contract

    repository_root = Path(__file__).resolve().parents[1]
    compiled = compile_skill_contract(repository_root, write=False)
    assert compiled.ok, compiled.to_dict()
    return repository_root, compiled.compiled_contract


def test_external_nested_contract_and_static_checks_share_canonical_binding(tmp_path: Path) -> None:
    from skillguard_v2.consumer_distribution import audit_consumer_distribution, build_consumer_distribution

    repository_root, contract = _repository_projection(tmp_path)
    destination = tmp_path / "consumer" / "skillguard"
    built = build_consumer_distribution(repository_root / ".agents" / "skills" / "skillguard", destination, contract)
    assert built["status"] == "passed", built
    audited = audit_consumer_distribution(destination)
    assert audited["status"] == "passed", audited
    assert audited["release_id"] == built["manifest"]["release_id"]
    assert audited["manifest"]["projection_id"] == "projection:consumer-distribution"


def test_consumer_clean_skill_passes_without_author_maintenance_section(tmp_path: Path) -> None:
    from skillguard_v2.consumer_distribution import audit_consumer_distribution, build_consumer_distribution

    repository_root, contract = _repository_projection(tmp_path)
    destination = tmp_path / "consumer"
    built = build_consumer_distribution(repository_root / ".agents" / "skills" / "skillguard", destination, contract)
    assert built["status"] == "passed", built
    assert not (destination / ".skillguard").exists()
    assert not (destination / "references" / "global-router").exists()
    assert audit_consumer_distribution(destination)["status"] == "passed"


def test_standalone_dot_remains_one_repository_member_binding(tmp_path: Path) -> None:
    from skillguard_v2.consumer_distribution import consumer_distribution_plan

    root = _root(tmp_path)
    source = _source()
    source["consumer_projection"] = {
        "projection_id": "projection:consumer-distribution",
        "root_path": ".",
        "release_manifest_path": "consumer-release.json",
        "file_paths": ["src/a.txt", "src/b.txt"],
    }
    plan = consumer_distribution_plan(root, source)
    assert plan["status"] == "passed", plan
    assert {row["path"] for row in plan["files"]} == {"src/a.txt", "src/b.txt"}


def test_external_member_escape_blocks_without_fallback(tmp_path: Path) -> None:
    from skillguard_v2.consumer_distribution import consumer_distribution_plan

    root = _root(tmp_path)
    source = _source()
    source["consumer_projection"] = {
        "projection_id": "projection:consumer-distribution",
        "root_path": ".",
        "release_manifest_path": "consumer-release.json",
        "file_paths": ["../outside.txt"],
    }
    # Keep the traversal target real so the current planner reaches its
    # explicit path-safety branch instead of classifying a nonexistent path.
    (root.parent / "outside.txt").write_text("outside", encoding="utf-8")
    plan = consumer_distribution_plan(root, source)
    assert plan["status"] == "blocked"
    assert any(row["code"] == "consumer_projection_file_invalid" for row in plan["findings"])


def test_external_member_without_repository_root_blocks_without_inference(tmp_path: Path) -> None:
    from skillguard_v2.consumer_distribution import consumer_distribution_plan

    root = _root(tmp_path)
    source = _source()
    source["consumer_projection"] = {
        "projection_id": "projection:consumer-distribution",
        "root_path": ".",
        "release_manifest_path": "consumer-release.json",
        "file_paths": ["missing.txt"],
    }
    plan = consumer_distribution_plan(root, source)
    assert plan["status"] == "blocked"
    assert any(row["code"] == "consumer_projection_file_missing" for row in plan["findings"])


def test_external_static_reference_does_not_fall_back_to_same_named_member_path(tmp_path: Path) -> None:
    from skillguard_v2.consumer_distribution import consumer_distribution_plan

    root = _root(tmp_path)
    source = _source()
    source["consumer_projection"] = {
        "projection_id": "projection:consumer-distribution",
        "root_path": ".",
        "release_manifest_path": "consumer-release.json",
        "file_paths": ["src/a.txt", "same-name.txt"],
    }
    plan = consumer_distribution_plan(root, source)
    assert plan["status"] == "blocked"
    assert any(row["path"] == "same-name.txt" for row in plan["findings"])


def test_external_contract_model_path_does_not_fall_back_to_member_copy(tmp_path: Path) -> None:
    from skillguard_v2.compact_contract import ContractError, validate_contract_source

    root = _root(tmp_path)
    source = _source()
    source["model_path"] = "same-name/model.json"
    with pytest.raises(ContractError) as raised:
        validate_contract_source(root, source)
    assert raised.value.code == "unknown_field"


def test_former_check_contract_target_root_option_is_rejected(tmp_path: Path) -> None:
    import checker_engine

    assert not hasattr(checker_engine, "validate_schema_subset")
    assert not (SCRIPT_ROOT / "skillguard_v2" / "external_target_binding.py").exists()
