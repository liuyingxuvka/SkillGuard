"""Current target consumer installation transaction tests.

The former multi-member self-author installer and runtime-authority fixture
were retired.  Installation is now the explicit target projection transaction
owned by ``target_installation``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from skillguard_v2.contract_compiler import compile_skill_contract
from skillguard_v2.consumer_distribution import audit_consumer_distribution
from skillguard_v2.installation import _InstallMutex
from skillguard_v2.target_installation import (
    activate_target_stage,
    prepare_target_stage,
    recover_target_installations,
    rollback_target_install,
    verify_target_stage,
)


def _fixture(tmp_path: Path, *, runtime: str = "VALUE = 1\n") -> tuple[Path, Path]:
    repository = tmp_path / "repository"
    skill = repository / ".agents" / "skills" / "fixture-skill"
    control = repository / ".skillguard"
    skill.mkdir(parents=True)
    control.mkdir()
    (skill / "SKILL.md").write_text(
        "---\nname: fixture-skill\ndescription: target fixture\n---\n# Fixture\n",
        encoding="utf-8",
    )
    (skill / "runtime.py").write_text(runtime, encoding="utf-8")
    source = {
        "schema_version": "skillguard.skill_contract.v3",
        "skill_id": "fixture-skill",
        "maintenance_unit_id": "unit:fixture",
        "inputs": [{"id": "runtime", "path": ".agents/skills/fixture-skill/runtime.py", "required": True}],
        "routes": [{"route_id": "route:read", "choice_group": "operation", "when": [{"fact": "operation", "equals": "read"}], "step_ids": [], "obligation_ids": ["ob:read"]}],
        "steps": [{"step_id": "step:read", "requires": [], "check_ids": ["check:fixture"]}],
        "obligations": [{"obligation_id": "ob:read", "check_ids": ["check:fixture"]}],
        "checks": [{"check_id": "check:fixture", "kind": "command", "command": "{{python}}", "args": ["-c", "from pathlib import Path; assert Path('.agents/skills/fixture-skill/runtime.py').is_file()"], "input_ids": ["runtime"], "expected": {"exit_code": 0}}],
        "consumer_projection": {"projection_id": "projection:consumer-distribution", "root_path": ".agents/skills/fixture-skill", "release_manifest_path": "consumer-release.json", "file_paths": ["SKILL.md", "runtime.py"]},
    }
    (control / "contract-source.json").write_text(json.dumps(source), encoding="utf-8")
    compiled = compile_skill_contract(repository, write=True)
    assert compiled.ok, compiled.to_dict()
    return repository, skill


def _stage(tmp_path: Path, name: str = "stage") -> Path:
    return tmp_path / name / "fixture-skill"


def test_complete_stage_passes_parity_and_installed_layout_smoke(tmp_path: Path) -> None:
    repository, skill = _fixture(tmp_path)
    stage = _stage(tmp_path)
    prepared = prepare_target_stage(repository, skill, stage)
    assert prepared["status"] == "passed", prepared
    verified = verify_target_stage(repository, skill, stage)
    assert verified["status"] == "passed", verified
    assert audit_consumer_distribution(stage)["status"] == "passed"


def test_verified_stage_can_activate_into_an_empty_codex_home(tmp_path: Path) -> None:
    repository, skill = _fixture(tmp_path)
    stage = _stage(tmp_path)
    home = tmp_path / "active" / ".codex"
    prepared = prepare_target_stage(repository, skill, stage)
    activated = activate_target_stage(repository, skill, stage, home, stage_verification=prepared["verification"])
    assert activated["status"] == "passed", activated
    active = home / "skills" / "fixture-skill"
    assert active.is_dir()
    assert audit_consumer_distribution(active)["status"] == "passed"
    assert not (active / ".skillguard").exists()


def test_exact_current_projection_activation_is_a_noop(tmp_path: Path) -> None:
    repository, skill = _fixture(tmp_path)
    stage = _stage(tmp_path)
    home = tmp_path / "active" / ".codex"
    prepared = prepare_target_stage(repository, skill, stage)
    first = activate_target_stage(
        repository, skill, stage, home, stage_verification=prepared["verification"]
    )
    assert first["status"] == "passed", first
    tracked = home / "skills" / "fixture-skill"
    before_files = {
        path.relative_to(home): path.read_bytes()
        for path in home.rglob("*")
        if path.is_file()
    }
    before_mtimes = {
        path.relative_to(home): path.stat().st_mtime_ns
        for path in home.rglob("*")
        if path.is_file()
    }
    second = activate_target_stage(
        repository, skill, stage, home, stage_verification=prepared["verification"]
    )
    assert second["status"] == "no_change", second
    assert second["transaction_id"] is None
    assert second["transaction_created"] is False
    assert tracked.is_dir()
    after_files = {
        path.relative_to(home): path.read_bytes()
        for path in home.rglob("*")
        if path.is_file()
    }
    after_mtimes = {
        path.relative_to(home): path.stat().st_mtime_ns
        for path in home.rglob("*")
        if path.is_file()
    }
    assert after_files == before_files
    assert after_mtimes == before_mtimes


def test_first_install_is_projection_exact_and_rollbackable(tmp_path: Path) -> None:
    repository, skill = _fixture(tmp_path)
    stage = _stage(tmp_path)
    home = tmp_path / "active" / ".codex"
    prepared = prepare_target_stage(repository, skill, stage)
    activated = activate_target_stage(repository, skill, stage, home, stage_verification=prepared["verification"])
    assert activated["status"] == "passed", activated
    active = home / "skills" / "fixture-skill"
    assert sorted(path.relative_to(active).as_posix() for path in active.rglob("*") if path.is_file()) == ["SKILL.md", "consumer-release.json", "runtime.py"]
    rolled_back = rollback_target_install(home, "fixture-skill", str(activated["transaction_id"]))
    assert rolled_back["status"] == "passed", rolled_back
    assert not active.exists()


def test_replacement_failure_after_activation_restores_previous_active(tmp_path: Path) -> None:
    repository, skill = _fixture(tmp_path)
    home = tmp_path / "active" / ".codex"
    first_stage = _stage(tmp_path, "first")
    first_prepared = prepare_target_stage(repository, skill, first_stage)
    first = activate_target_stage(repository, skill, first_stage, home, stage_verification=first_prepared["verification"])
    assert first["status"] == "passed", first
    before = (home / "skills" / "fixture-skill" / "runtime.py").read_text(encoding="utf-8")
    (skill / "runtime.py").write_text("VALUE = 2\n", encoding="utf-8")
    assert compile_skill_contract(repository, write=True).ok
    second_stage = _stage(tmp_path, "second")
    second_prepared = prepare_target_stage(repository, skill, second_stage)
    os.environ["SKILLGUARD_TARGET_INSTALL_FAILPOINT"] = "after_activation"
    try:
        second = activate_target_stage(repository, skill, second_stage, home, stage_verification=second_prepared["verification"])
    finally:
        os.environ.pop("SKILLGUARD_TARGET_INSTALL_FAILPOINT", None)
    assert second["status"] == "blocked", second
    assert second["restored_status"] == "rolled_back"
    assert (home / "skills" / "fixture-skill" / "runtime.py").read_text(encoding="utf-8") == before


def test_unexpected_stage_file_blocks_exact_projection(tmp_path: Path) -> None:
    repository, skill = _fixture(tmp_path)
    stage = _stage(tmp_path)
    prepare_target_stage(repository, skill, stage)
    (stage / "unexpected.txt").write_text("private\n", encoding="utf-8")
    report = verify_target_stage(repository, skill, stage)
    assert report["status"] == "blocked"
    assert "target_stage_unexpected:unexpected.txt" in report["blockers"]


def test_repository_root_mismatch_blocks_prepare(tmp_path: Path) -> None:
    repository, skill = _fixture(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        prepare_target_stage(outside, skill, _stage(tmp_path, "wrong"))
    except ValueError as exc:
        assert str(exc) == "target_install_skill_root_outside_repository"
    else:
        raise AssertionError("repository-root mismatch must block")


def test_stage_path_must_use_an_isolated_skill_root(tmp_path: Path) -> None:
    repository, skill = _fixture(tmp_path)
    try:
        prepare_target_stage(repository, skill, tmp_path / "stage" / "wrong-name")
    except ValueError as exc:
        assert str(exc) == "target_install_stage_skill_id_mismatch"
    else:
        raise AssertionError("invalid stage member name must block")


def test_stage_drift_blocks_before_activation(tmp_path: Path) -> None:
    repository, skill = _fixture(tmp_path)
    stage = _stage(tmp_path)
    prepare_target_stage(repository, skill, stage)
    (stage / "runtime.py").write_text("VALUE = drifted\n", encoding="utf-8")
    report = verify_target_stage(repository, skill, stage)
    assert report["status"] == "blocked"
    assert "consumer_file_hash_mismatch:runtime.py" in report["blockers"]


def test_global_install_lock_blocks_target_activation(tmp_path: Path) -> None:
    repository, skill = _fixture(tmp_path)
    stage = _stage(tmp_path)
    home = tmp_path / "active" / ".codex"
    prepared = prepare_target_stage(repository, skill, stage)
    with _InstallMutex(home, "test-owner"):
        report = activate_target_stage(repository, skill, stage, home, stage_verification=prepared["verification"])
    assert report["status"] == "blocked", report
    assert any("InstallBusyError" in item for item in report["blockers"])


def test_source_only_files_are_excluded_from_target_projection(tmp_path: Path) -> None:
    repository, skill = _fixture(tmp_path)
    source_only = skill / "tests" / "test_source_only.py"
    source_only.parent.mkdir()
    source_only.write_text("raise RuntimeError('must not run')\n", encoding="utf-8")
    assert compile_skill_contract(repository, write=True).ok
    stage = _stage(tmp_path)
    report = prepare_target_stage(repository, skill, stage)
    assert report["status"] == "passed", report
    assert not (stage / "tests").exists()


def test_reparse_stage_root_is_rejected_when_supported(tmp_path: Path) -> None:
    repository, skill = _fixture(tmp_path)
    real_stage = _stage(tmp_path, "real")
    prepare_target_stage(repository, skill, real_stage)
    link = tmp_path / "link" / "fixture-skill"
    link.parent.mkdir()
    try:
        link.symlink_to(real_stage, target_is_directory=True)
    except OSError:
        return
    try:
        verify_target_stage(repository, skill, link)
    except ValueError as exc:
        assert str(exc) == "target_install_stage_root_invalid"
    else:
        raise AssertionError("reparse stage root must block")
