from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path

import pytest

from skillguard_v2.consumer_distribution import audit_consumer_distribution, build_consumer_distribution
from skillguard_v2.contract_compiler import compile_skill_contract


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / ".agents" / "skills" / "skillguard"


def _current_consumer(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    compiled = compile_skill_contract(ROOT, write=False)
    assert compiled.ok, compiled.to_dict()
    destination = tmp_path / "consumer"
    report = build_consumer_distribution(SKILL_ROOT, destination, compiled.compiled_contract)
    assert report["status"] == "passed", report
    return destination, report["manifest"]


def test_github_remote_identity_normalizes_https_ssh_case_and_git_suffix(tmp_path: Path) -> None:
    """Author provenance code is excluded from the target-owned projection."""

    destination, manifest = _current_consumer(tmp_path)
    paths = {str(row["path"]) for row in manifest["files"]}
    assert not any(path.rsplit("/", 1)[-1] == "provenance.py" for path in paths)
    assert not list(destination.rglob("provenance.py"))


def test_project_version_uses_the_declared_current_python_runtime() -> None:
    payload = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = str(payload["project"]["version"])
    assert version == (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def test_complete_source_manifest_detects_missing_changed_and_unexpected_files(tmp_path: Path) -> None:
    destination, manifest = _current_consumer(tmp_path)
    before = audit_consumer_distribution(destination)
    assert before["status"] == "passed", before
    (destination / "SKILL.md").write_text("drift\n", encoding="utf-8")
    (destination / "unexpected.txt").write_text("extra\n", encoding="utf-8")
    drifted = audit_consumer_distribution(destination)
    assert drifted["status"] == "blocked"
    assert drifted.get("blockers") or drifted.get("findings") or drifted.get("errors")
    assert manifest["release_id"] == before["release_id"]


def test_repository_audit_uses_tokens_and_can_pass_a_development_identity_check(tmp_path: Path) -> None:
    destination, _manifest = _current_consumer(tmp_path)
    report = audit_consumer_distribution(destination)
    assert report["status"] == "passed", report
    serialized = json.dumps(report, ensure_ascii=False)
    assert str(ROOT) not in serialized


def test_release_and_installed_downgrade_gates_block_independently(tmp_path: Path) -> None:
    destination, _manifest = _current_consumer(tmp_path)
    (destination / "SKILL.md").write_bytes(b"stale\n")
    report = audit_consumer_distribution(destination)
    assert report["status"] == "blocked"


def test_current_provenance_detects_residual_before_runs_are_filtered(tmp_path: Path) -> None:
    destination, _manifest = _current_consumer(tmp_path)
    runtime = destination / ".skillguard" / "runs" / "old.json"
    runtime.parent.mkdir(parents=True)
    runtime.write_text(json.dumps({"schema_version": "skillguard.run_record.v1"}), encoding="utf-8")
    assert audit_consumer_distribution(destination)["status"] == "blocked"


def test_provenance_blocks_unconverted_authority_without_fallback(tmp_path: Path) -> None:
    destination, _manifest = _current_consumer(tmp_path)
    old = destination / "work-contract.json"
    old.write_text("{}", encoding="utf-8")
    assert audit_consumer_distribution(destination)["status"] == "blocked"


def test_authority_change_during_transient_filtered_manifest_scan_blocks(tmp_path: Path) -> None:
    destination, _manifest = _current_consumer(tmp_path)
    tracked = destination / "SKILL.md"
    original = tracked.read_bytes()
    tracked.write_bytes(original + b"\nchanged\n")
    report = audit_consumer_distribution(destination)
    assert report["status"] == "blocked"
