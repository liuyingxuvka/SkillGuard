from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / ".agents" / "skills" / "skillguard"
SCRIPT_ROOT = SKILL_ROOT / "scripts"
CLI = SCRIPT_ROOT / "skillguard.py"
FIXTURE = SKILL_ROOT / "fixtures" / "good_single_skill"
SCHEMA = (
    SKILL_ROOT
    / "assets"
    / "schemas"
    / "skillguard_external_target_binding_v1.schema.json"
)
sys.path.insert(0, str(SCRIPT_ROOT))

from checker_engine import validate_schema_subset  # noqa: E402
from skillguard_utils import json_text  # noqa: E402
from skillguard_v2.contract_compiler import compile_skill_contract  # noqa: E402


def _run(*args: str, cwd: Path = ROOT) -> tuple[int, dict[str, object]]:
    completed = subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    return completed.returncode, json.loads(completed.stdout)


def _prefix_repository_paths(source: dict[str, object], prefix: str) -> None:
    source["model_path"] = f"{prefix}/{source['model_path']}"
    source["implementation_paths"] = [
        f"{prefix}/{path}" for path in source["implementation_paths"]  # type: ignore[index]
    ]
    for check in source["checks"]:  # type: ignore[index]
        check["args"] = [
            f"{prefix}/{value}" if (FIXTURE / str(value)).exists() else value
            for value in check.get("args", [])
        ]
        for selector in check.get("input_selectors", []):
            if selector.get("kind") == "path":
                selector["path"] = f"{prefix}/{selector['path']}"


def _nested_current_target(tmp_path: Path) -> tuple[Path, Path]:
    repository = tmp_path / "external-repository"
    target = repository / "skills" / "good_single_skill"
    target.parent.mkdir(parents=True)
    shutil.copytree(FIXTURE, target)
    source_path = target / ".skillguard" / "contract-source.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    _prefix_repository_paths(source, "skills/good_single_skill")
    source_path.write_text(json_text(source), encoding="utf-8")
    result = compile_skill_contract(target, repository_root=repository, write=True)
    assert result.ok, result.to_dict()
    return repository, target


def _assert_current_binding(
    report: dict[str, object],
    *,
    mode: str,
    member_root_path: str,
) -> None:
    assert report["decision"] == "pass"
    binding = report["target_binding"]
    assert isinstance(binding, dict)
    assert binding["binding_mode"] == mode
    assert binding["member_root_path"] == member_root_path
    assert binding["member_within_repository"] is True
    assert binding["fallback_used"] is False
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert validate_schema_subset(binding, schema) == []


def test_external_nested_contract_and_static_checks_share_canonical_binding(
    tmp_path: Path,
) -> None:
    repository, _target = _nested_current_target(tmp_path)
    arguments = (
        "--repository-root",
        str(repository),
        "--target",
        "skills/good_single_skill",
    )

    contract_code, contract = _run("check-contract", *arguments)
    static_code, static = _run("check-skill", *arguments)

    assert contract_code == 0
    assert static_code == 0
    _assert_current_binding(
        contract,
        mode="explicit_repository",
        member_root_path="skills/good_single_skill",
    )
    _assert_current_binding(
        static,
        mode="explicit_repository",
        member_root_path="skills/good_single_skill",
    )
    serialized = json.dumps({"contract": contract, "static": static})
    assert str(repository) not in serialized


def test_standalone_dot_remains_one_repository_member_binding(tmp_path: Path) -> None:
    target = tmp_path / "good_single_skill"
    shutil.copytree(FIXTURE, target)

    contract_code, contract = _run("check-contract", "--target", ".", cwd=target)
    static_code, static = _run("check-skill", "--target", ".", cwd=target)

    assert contract_code == 0
    assert static_code == 0
    _assert_current_binding(contract, mode="standalone_dot", member_root_path=".")
    _assert_current_binding(static, mode="standalone_dot", member_root_path=".")


def test_external_member_escape_blocks_without_fallback(tmp_path: Path) -> None:
    repository, _target = _nested_current_target(tmp_path)
    outside = tmp_path / "outside-skill"
    shutil.copytree(FIXTURE, outside)

    code, report = _run(
        "check-contract",
        "--repository-root",
        str(repository),
        "--target",
        str(outside),
    )

    assert code == 2
    assert report["decision"] == "block"
    assert "declared canonical --repository-root" in " ".join(report["blockers"])


def test_external_member_without_repository_root_blocks_without_inference(
    tmp_path: Path,
) -> None:
    _repository, target = _nested_current_target(tmp_path)

    for command in ("check-contract", "check-skill"):
        code, report = _run(command, "--target", str(target))

        assert code == 2
        assert report["decision"] == "block"
        assert "--repository-root is required for a non-self target" in " ".join(
            report["blockers"]
        )
        assert "target_binding" not in report


def test_external_static_reference_does_not_fall_back_to_same_named_member_path(
    tmp_path: Path,
) -> None:
    repository, target = _nested_current_target(tmp_path)
    repository_reference = ".agents/skills/good_single_skill/SKILL.md"
    member_fallback = target / repository_reference
    member_fallback.parent.mkdir(parents=True)
    member_fallback.write_text("member fallback must not be accepted\n", encoding="utf-8")
    skill_path = target / "SKILL.md"
    skill_path.write_text(
        skill_path.read_text(encoding="utf-8")
        + f"\n[Canonical-only regression]({repository_reference})\n",
        encoding="utf-8",
    )
    result = compile_skill_contract(target, repository_root=repository, write=True)
    assert result.ok, result.to_dict()

    code, report = _run(
        "check-skill",
        "--repository-root",
        str(repository),
        "--target",
        "skills/good_single_skill",
    )

    assert code == 1
    assert report["decision"] == "fail"
    binding = report["target_binding"]
    assert binding["fallback_used"] is False
    reference = next(
        row
        for row in report["declared_references"]
        if row["reference"] == repository_reference
    )
    assert reference["resolved_path"] == repository_reference
    assert reference["exists"] is False
    assert member_fallback.is_file()


def test_external_contract_model_path_does_not_fall_back_to_member_copy(
    tmp_path: Path,
) -> None:
    repository, target = _nested_current_target(tmp_path)
    repository_model_path = (
        ".agents/skills/good_single_skill/.skillguard/flowguard_contract_model.py"
    )
    member_fallback = target / repository_model_path
    member_fallback.parent.mkdir(parents=True)
    shutil.copy2(target / ".skillguard" / "flowguard_contract_model.py", member_fallback)
    source_path = target / ".skillguard" / "contract-source.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source["model_path"] = repository_model_path
    source_path.write_text(json_text(source), encoding="utf-8")

    result = compile_skill_contract(target, repository_root=repository, write=False)
    assert not result.ok
    assert any(finding.code == "flowguard_model_missing" for finding in result.findings)
    code, report = _run(
        "check-contract",
        "--repository-root",
        str(repository),
        "--target",
        "skills/good_single_skill",
    )

    assert code == 1
    assert report["decision"] == "fail"
    assert member_fallback.is_file()


def test_former_check_contract_target_root_option_is_rejected(tmp_path: Path) -> None:
    repository, _target = _nested_current_target(tmp_path)

    code, report = _run(
        "check-contract",
        "--target-root",
        str(repository),
        "--target",
        "skills/good_single_skill",
    )

    assert code == 2
    assert report["decision"] == "fail"
    assert "unrecognized arguments: --target-root" in " ".join(report["failures"])
