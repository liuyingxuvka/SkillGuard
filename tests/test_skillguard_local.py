"""Standard-library smoke checks for the local SkillGuard command surface."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = REPO_ROOT / ".agents" / "skills" / "skillguard" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import checker_engine  # noqa: E402
import skillguard_utils  # noqa: E402


SKILLGUARD = SCRIPT_DIR / "skillguard.py"
EXAMPLES = REPO_ROOT / "examples" / "README.md"

PRIVATE_OR_SECRET_PATTERNS = (
    re.compile(r"(?<![A-Za-z])(?:[A-Za-z]:[\\/][^\\s`\"']+|/[Uu]sers/|\\\\[^\\s`\"']+)"),
    re.compile(r"\b(?:packet|lease|result)-\d{4,}\b"),
    re.compile(r"BEGIN (?:RSA |OPENSSH |DSA |EC |PGP )?PRIVATE\s+KEY"),
    re.compile(r"(?i)\b(?:api[_-]?key|secret|token|password)\b\s*[:=]"),
)

UNSAFE_CLAIM_PATTERNS = (
    re.compile(r"(?i)\bfixture\s+coverage\s+(?:passed|complete|validated|proven)\b"),
    re.compile(r"(?i)\b(?:full|complete|end-to-end)\s+suite\s+automation\b"),
    re.compile(r"(?i)\bpackage\s+publication\s+(?:complete|ready|done|validated|proven)\b"),
    re.compile(r"(?i)\brelease\s+readiness\s+(?:complete|ready|validated|proven)\b"),
    re.compile(r"(?i)\bcode-contract\s+validation\s+(?:passed|complete|validated|proven)\b"),
    re.compile(r"(?i)\btests\s+passed\b"),
)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def run_skillguard(*args: str, expected_exit: int = 0) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(SKILLGUARD), *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != expected_exit:
        raise AssertionError(
            f"skillguard.py {' '.join(args)} exited {completed.returncode}, expected {expected_exit}\n"
            f"stderr={completed.stderr}\nstdout={completed.stdout}"
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"command did not produce parseable JSON: {exc}\n{completed.stdout}") from exc


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def freshness_record_for(path: Path, **extra: Any) -> dict[str, Any]:
    record = {
        "schema_version": "skillguard.cli_result.v1",
        "command": "check-skill",
        "decision": "pass",
        "checked_at": utc_timestamp(),
        "files_inspected": [
            {
                "path": rel(path),
                "kind": "file",
                "sha256": sha256(path),
                "line_count": len(path.read_text(encoding="utf-8").splitlines()),
            }
        ],
        "evidence": [
            {
                "evidence_id": "freshness-test-source",
                "kind": "file_inspection",
                "fresh": True,
                "source_path": rel(path),
                "summary": "Synthetic current source fingerprint for detect-stale-evidence regression.",
            }
        ],
        "failures": [],
        "blockers": [],
        "skipped_checks": [],
        "residual_risk": [],
        "claim_boundary": "Synthetic test evidence used only by the local detect-stale-evidence regression.",
    }
    record.update(extra)
    return record


def stale_blocker_codes(report: dict[str, Any]) -> set[str]:
    return {item.get("blocker_code") for item in report.get("stale_evidence_blockers", [])}


def valid_skill_idea(target_path: str, skill_name: str = "example-review-helper") -> dict[str, Any]:
    return {
        "skill_name": skill_name,
        "description": "Use when a maintainer needs a bounded review helper for repository notes.",
        "target_path": target_path,
        "purpose": "Create a review helper skill plan with explicit evidence and claim boundaries.",
        "workflow_mode": "create",
        "closure_scope": "blueprint preview only",
        "evidence_policy": "current direct evidence required before target acceptance",
        "safe_edit_mode": "no_write",
        "use_when": ["A maintainer asks for a review helper skill plan."],
        "do_not_use_when": ["The request needs target files written by the planning command."],
        "required_workflow": ["Inspect target files before any later edit.", "Run local checks after implementation."],
        "hard_gates": ["Do not write target files during planning.", "Keep claim boundaries visible."],
        "output_requirements": ["evidence", "blockers", "skipped_checks", "residual_risk", "claim_boundary"],
    }


def valid_suite_blueprint(target_path: str, suite_name: str, members: list[str] | None = None) -> dict[str, Any]:
    member_names = members or ["suite-alpha", "suite-beta"]
    return {
        "schema_version": "skillguard.suite_blueprint.v1",
        "suite_name": suite_name,
        "target": target_path,
        "workflow_mode": "suite",
        "purpose": "Create a bounded multi-skill suite scaffold with visible child evidence.",
        "evidence_policy": "current direct evidence required before suite or child acceptance",
        "safe_edit_scope": {
            "target_file_writes_allowed": True,
            "allowed_write_paths": [target_path],
        },
        "member_skills": [
            {
                "name": name,
                "role": f"{name} generated member",
                "description": f"Use when work falls inside the {name} suite member boundary.",
                "purpose": f"Maintain {name} with current child evidence and bounded suite claims.",
            }
            for name in member_names
        ],
        "claim_boundary": (
            "This Suite Blueprint is an input to generate-suite only. It does not prove child skill acceptance, runtime checker "
            "execution, fixture coverage, tests, suite automation, package publication, release readiness, code-contract "
            "validation, external services, or future AI behavior."
        ),
    }


def checker_change_baseline(
    *,
    command_surface: list[dict[str, Any]] | None = None,
    route_registry: list[dict[str, Any]] | None = None,
    fixture_manifests: list[dict[str, Any]] | None = None,
    evidence_records: list[dict[str, Any]] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    record = {
        "schema_version": checker_engine.REVIEW_CHECKER_CHANGE_BASELINE_SCHEMA,
        "baseline_id": "synthetic-checker-change-baseline",
        "checker_version": checker_engine.CHECKER_VERSION,
        "route_version": checker_engine.DETECT_STALE_EXPECTED_ROUTE_VERSION,
        "route_registry_version": checker_engine.ROUTE_TASK_REGISTRY_VERSION,
        "command_surface": command_surface if command_surface is not None else checker_engine.current_checker_command_surface(),
        "route_registry": route_registry
        if route_registry is not None
        else [checker_engine.public_route_entry(entry) for entry in checker_engine.current_route_entries()],
        "fixture_manifests": fixture_manifests or [],
        "evidence_records": evidence_records or [],
        "public_safety_checks": [finding_id for finding_id, _pattern in checker_engine.PUBLIC_SAFETY_PATTERNS],
    }
    record.update(overrides)
    return record


def checker_change_blocker_codes(report: dict[str, Any]) -> set[str]:
    return {item.get("blocker_code") for item in report.get("checker_change_blockers", [])}


def checker_change_suite_guard_codes(report: dict[str, Any]) -> set[str]:
    return {item.get("blocker_code") for item in report.get("checker_change_suite_guard_blockers", [])}


def checker_change_review_report_for(source_path: Path, **overrides: Any) -> dict[str, Any]:
    checked_at = utc_timestamp()
    source_relative = rel(source_path)
    report = {
        "schema_version": checker_engine.REVIEW_CHECKER_CHANGE_RESULT_SCHEMA,
        "command": "review-checker-change",
        "decision": "pass",
        "checked_at": checked_at,
        "checker_version": checker_engine.CHECKER_VERSION,
        "route_version": checker_engine.DETECT_STALE_EXPECTED_ROUTE_VERSION,
        "route_registry_version": checker_engine.ROUTE_TASK_REGISTRY_VERSION,
        "command_names": list(checker_engine.COMMANDS),
        "current_route_registry": [
            checker_engine.public_route_entry(entry) for entry in checker_engine.current_route_entries()
        ],
        "files_inspected": [
            {
                "path": source_relative,
                "kind": "file",
                "sha256": sha256(source_path),
                "line_count": len(source_path.read_text(encoding="utf-8").splitlines()),
            }
        ],
        "checker_change_blockers": [],
        "blockers": [],
        "failures": [],
        "checks": [
            {
                "check_id": "review-checker-change:synthetic-current",
                "name": "Synthetic current review",
                "required": True,
                "status": "pass",
                "summary": "Synthetic current checker-change review evidence for suite-guard regression.",
            }
        ],
        "evidence": [
            {
                "evidence_id": "synthetic-checker-change-review",
                "kind": "file_inspection",
                "fresh": True,
                "source_path": source_relative,
                "summary": "Synthetic checker-change review source fingerprint.",
            }
        ],
        "skipped_checks": [],
        "residual_risk": [],
        "claim_boundary": "Synthetic review-checker-change evidence used only by local suite-guard regression tests.",
        "mutation_check": {"read_only": True, "mutated_input_paths": [], "watched_input_count": 1},
    }
    report["maintenance_record"] = checker_engine.build_maintenance_record(
        record_kind="checker_change_review",
        artifact_id=".agents/skills/skillguard",
        route_node_id="review-checker-change",
        checker_name="review-checker-change",
        status="pass",
        blockers=[],
        evidence_timestamp=checked_at,
        owner_action={"action": "review_only", "status": "not_applicable"},
        content_seed={"source_path": source_relative, "decision": "pass"},
    )
    report["maintenance_record_schema_version"] = checker_engine.MAINTENANCE_RECORD_SCHEMA_VERSION
    report.update(overrides)
    return report


def valid_maintenance_record(**overrides: Any) -> dict[str, Any]:
    record = checker_engine.build_maintenance_record(
        record_kind="stale_evidence_review",
        artifact_id="synthetic-maintenance-record",
        route_node_id="detect-stale-evidence",
        checker_name="detect-stale-evidence",
        status="pass",
        blockers=[],
        evidence_timestamp=utc_timestamp(),
        owner_action={"action": "detect_only", "status": "not_applicable"},
        content_seed={"test": "maintenance-record"},
    )
    record.update(overrides)
    return record


def maintenance_blocker_codes(report: dict[str, Any]) -> set[str]:
    return {item.get("blocker_code") for item in report.get("maintenance_record_blockers", [])}


class SkillGuardLocalExamplesTest(unittest.TestCase):
    maxDiff = None

    def assert_clean_pass(self, report: dict[str, Any]) -> None:
        self.assertEqual(report.get("decision"), "pass")
        self.assertEqual(report.get("failures"), [])
        self.assertEqual(report.get("blockers"), [])
        self.assertIn("claim_boundary", report)

    def assert_route_conflict(self, report: dict[str, Any], blocker_code: str) -> dict[str, Any]:
        self.assertEqual(report.get("decision"), "block")
        structured = report.get("routing_conflict_blockers", [])
        self.assertIsInstance(structured, list)
        match = next((item for item in structured if item.get("blocker_code") == blocker_code), None)
        self.assertIsNotNone(match, structured)
        assert match is not None
        self.assertTrue(match.get("blocker_class"))
        self.assertTrue(match.get("message"))
        self.assertIn("recommended_resolution", match)
        self.assertTrue(match.get("conflicting_fields") or match.get("conflicting_candidates"), match)
        self.assertEqual(report.get("routing_decision"), {})
        return match

    def assert_validation_registry(self, report: dict[str, Any], command: str, decision: str) -> dict[str, Any]:
        registry = report.get("validation_registry")
        self.assertIsInstance(registry, dict)
        assert isinstance(registry, dict)
        self.assertEqual(registry.get("schema_version"), checker_engine.VALIDATION_REGISTRY_SCHEMA_VERSION)
        self.assertEqual(registry.get("command"), command)
        self.assertEqual(registry.get("decision"), decision)
        self.assertIsInstance(registry.get("validation_rows"), list)
        self.assertIsInstance(registry.get("evidence"), list)
        self.assertIn("checks", registry.get("source_of_truth_for", []))
        self.assertIn("evidence", registry.get("source_of_truth_for", []))
        return registry

    def validation_registry_ids(self, registry: dict[str, Any]) -> set[str]:
        return {
            str(row.get("validation_id"))
            for row in registry.get("validation_rows", [])
            if isinstance(row, dict) and row.get("validation_id")
        }

    def write_minimal_readme_release_repo(self, root: Path, *, version: str, model_text: str) -> None:
        skill_entrypoint = root / ".agents" / "skills" / "skillguard" / "SKILL.md"
        skill_entrypoint.parent.mkdir(parents=True)
        skill_entrypoint.write_text(
            "---\nname: skillguard\ndescription: Fixture SkillGuard source identity.\n---\n",
            encoding="utf-8",
        )
        hero_dir = root / "assets" / "readme-hero"
        hero_dir.mkdir(parents=True)
        (hero_dir / "hero.png").write_bytes(b"0" * 12_000)
        (hero_dir / "hero_prompt.md").write_text(
            "Prompt: SkillGuard visual concept with contract gates.\nGeneration method: text-to-image model.\n",
            encoding="utf-8",
        )
        (hero_dir / "hero_design_note.md").write_text(
            "# Hero\n\n## Core workflow\n\nWorkflow evidence.\n\n## Visual concept\n\nVisual evidence.\n",
            encoding="utf-8",
        )
        (hero_dir / "readme_model_evidence.md").write_text(model_text, encoding="utf-8")
        (root / "VERSION").write_text(f"{version}\n", encoding="utf-8")
        (root / "pyproject.toml").write_text(
            f'[project]\nname = "skillguard"\nversion = "{version}"\n\n[tool.skillguard.repository]\nbaseline_version = "{version}"\n',
            encoding="utf-8",
        )
        (root / "CHANGELOG.md").write_text(f"# Changelog\n\n## v{version} - 2026-06-28\n", encoding="utf-8")
        english_sections = [english for english, _chinese in checker_engine.README_RELEASE_HEADING_PAIRS]
        chinese_sections = [chinese for _english, chinese in checker_engine.README_RELEASE_HEADING_PAIRS]
        command_index = ", ".join(f"`{name}`" for name in checker_engine.COMMANDS)
        readme_lines = [
            "# SkillGuard",
            "",
            "<!-- README HERO START -->",
            '<img src="./assets/readme-hero/hero.png" alt="SkillGuard concept hero image" width="100%" />',
            "<!-- README HERO END -->",
            "",
            f"Current release: `v{version}`",
            "",
            "English comes first; the second half is a full Chinese mirror.",
            "",
        ]
        for heading in english_sections:
            readme_lines.extend([heading, "English section content.", ""])
        readme_lines.extend([command_index, "", "# SkillGuard 中文说明", "", f"当前版本：`v{version}`", ""])
        for heading in chinese_sections:
            readme_lines.extend([heading, "中文镜像内容。", ""])
        readme_lines.append(command_index)
        (root / "README.md").write_text("\n".join(readme_lines) + "\n", encoding="utf-8")

    def validation_registry_blocker_codes(self, registry: dict[str, Any]) -> set[str]:
        return {
            str(row.get("blocker_code"))
            for row in registry.get("blocker_evidence", [])
            if isinstance(row, dict) and row.get("blocker_code")
        }

    def test_reference_extraction_ignores_fenced_code_and_slash_commands(self) -> None:
        text = """Use `/opsx:apply <other>` when switching changes.

```bash
python tool.py --input <input.json>
```

Read `references/README.md` before closing.
"""
        self.assertEqual(checker_engine.extract_reference_tokens(text), ["references/README.md"])

    def test_reference_extraction_keeps_real_inline_missing_references(self) -> None:
        text = "Read `references/missing-guide.md` before claiming completion."
        self.assertEqual(checker_engine.extract_reference_tokens(text), ["references/missing-guide.md"])

    def test_declared_references_resolve_target_local_references_directory(self) -> None:
        with tempfile.TemporaryDirectory(prefix="target-reference-", dir=REPO_ROOT / ".agents" / "skills") as tmp:
            target = Path(tmp)
            references = target / "references"
            references.mkdir()
            guide = references / "guide.md"
            guide.write_text("target-local reference\n", encoding="utf-8")
            self.assertEqual(checker_engine.resolve_declared_reference(target, "references/guide.md"), guide)

    def test_declared_references_still_fail_missing_target_local_reference(self) -> None:
        with tempfile.TemporaryDirectory(prefix="target-reference-", dir=REPO_ROOT / ".agents" / "skills") as tmp:
            target = Path(tmp)
            failures: list[str] = []
            blockers: list[str] = []
            entry = checker_engine.validate_reference(
                target,
                "references/missing-guide.md",
                failures,
                blockers,
                allow_project_boundary=True,
            )
            self.assertEqual(entry.get("status"), "fail")
            self.assertIn("references/missing-guide.md: referenced path is missing", failures)
            self.assertEqual(blockers, [])

    def test_former_runtime_references_are_never_optional(self) -> None:
        from tests._runtime_authority_consumer_fixture import make_current_skill

        with tempfile.TemporaryDirectory(prefix="retired-ref-", dir=REPO_ROOT / ".agents" / "skills") as tmp:
            target = Path(tmp)
            make_current_skill(target, target.name)
            for reference in (
                ".skillguard/work-contract.json",
                ".skillguard/check_manifest.json",
            ):
                failures: list[str] = []
                blockers: list[str] = []
                entry = checker_engine.validate_reference(
                    target,
                    reference,
                    failures,
                    blockers,
                    allow_project_boundary=True,
                )
                self.assertEqual("fail", entry.get("status"), entry)
                self.assertTrue(entry.get("required"), entry)
                self.assertIn("referenced path is missing", failures[0])
                self.assertEqual([], blockers)

    def test_current_check_contract_preserves_explicit_repository_root(self) -> None:
        target = REPO_ROOT / ".agents" / "skills" / "skillguard"
        report = run_skillguard(
            "check-contract",
            "--repository-root",
            str(REPO_ROOT),
            "--target",
            rel(target),
        )
        self.assert_clean_pass(report)
        self.assertEqual("current", report.get("authority_decision"))

    def test_current_check_contract_preserves_standalone_member_paths(self) -> None:
        from tests._runtime_authority_consumer_fixture import make_current_skill

        with tempfile.TemporaryDirectory(prefix="nested-contract-", dir=REPO_ROOT) as tmp:
            target_root = Path(tmp)
            target = target_root / "skills" / "nested-current"
            make_current_skill(target, "nested-current")
            report = run_skillguard(
                "check-contract",
                "--repository-root",
                str(target),
                "--target",
                ".",
            )

        self.assert_clean_pass(report)
        self.assertEqual("current", report.get("authority_decision"))

    def test_installed_check_contract_consumes_current_trio_without_source_only_model(self) -> None:
        with tempfile.TemporaryDirectory(prefix="installed-contract-", dir=REPO_ROOT) as tmp:
            skills_root = Path(tmp) / ".codex" / "skills"
            target = skills_root / "skillguard"
            source = REPO_ROOT / ".agents" / "skills" / "skillguard"
            target.joinpath(".skillguard").mkdir(parents=True)
            shutil.copy2(source / "SKILL.md", target / "SKILL.md")
            for name in (
                "contract-source.json",
                "compiled-contract.json",
                "check-manifest.json",
            ):
                shutil.copy2(source / ".skillguard" / name, target / ".skillguard" / name)
            report = run_skillguard(
                "check-contract",
                "--repository-root",
                str(skills_root),
                "--target",
                "skillguard",
            )

        self.assert_clean_pass(report)
        self.assertEqual("current", report.get("authority_decision"))
        self.assertEqual("installed-current-authority", report.get("verification_scope"))
        self.assertEqual(
            "check-contract:installed-current-authority",
            report["checks"][0]["check_id"],
        )

    def test_source_layout_references_map_to_installed_target_layout(self) -> None:
        with tempfile.TemporaryDirectory(prefix="installed-layout-", dir=REPO_ROOT) as tmp:
            target = Path(tmp) / ".codex" / "skills" / "installed-layout"
            target.mkdir(parents=True)
            skill = target / "SKILL.md"
            skill.write_text("installed entrypoint\n", encoding="utf-8")
            reference = f".agents/skills/{target.name}/SKILL.md"

            self.assertEqual(checker_engine.resolve_declared_reference(target, reference), skill)

    def test_record_references_map_to_installed_target_layout(self) -> None:
        with tempfile.TemporaryDirectory(prefix="installed-layout-", dir=REPO_ROOT) as tmp:
            target = Path(tmp) / ".codex" / "skills" / "installed-layout"
            control_root = target / ".skillguard"
            control_root.mkdir(parents=True)
            skill = target / "SKILL.md"
            skill.write_text("installed entrypoint\n", encoding="utf-8")
            reference = f".agents/skills/{target.name}/SKILL.md"

            self.assertEqual(checker_engine.resolve_record_reference(target, control_root, reference), skill)

    def test_contract_target_path_accepts_installed_target_layout_mapping(self) -> None:
        with tempfile.TemporaryDirectory(prefix="installed-layout-", dir=REPO_ROOT) as tmp:
            target = Path(tmp)
            target.mkdir(exist_ok=True)
            (target / "SKILL.md").write_text("---\nname: fixture\ndescription: fixture\n---\n", encoding="utf-8")
            reference = f".agents/skills/{target.name}"

            self.assertTrue(checker_engine.contract_target_matches_target(reference, target))

    def test_repository_root_detection_supports_source_and_installed_layouts(self) -> None:
        source_skill_root = REPO_ROOT / ".agents" / "skills" / "skillguard"
        installed_skill_root = REPO_ROOT / ".codex" / "skills" / "skillguard"

        self.assertEqual(skillguard_utils.repository_root_for_skill_root(source_skill_root), REPO_ROOT)
        self.assertEqual(skillguard_utils.repository_root_for_skill_root(installed_skill_root), REPO_ROOT)

        original_repo = checker_engine.repository_root
        original_skill = checker_engine.skill_root
        try:
            checker_engine.repository_root = lambda: REPO_ROOT
            checker_engine.skill_root = lambda: installed_skill_root
            mapped = checker_engine.resolve_skillguard_self_layout_path(".agents/skills/skillguard/fixtures/runtime_contract")
            self.assertEqual(mapped, installed_skill_root.resolve() / "fixtures" / "runtime_contract")
        finally:
            checker_engine.repository_root = original_repo
            checker_engine.skill_root = original_skill

    def test_single_skill_example_command(self) -> None:
        report = run_skillguard(
            "check-skill",
            "--repository-root",
            str(REPO_ROOT),
            "--target",
            ".agents/skills/skillguard/fixtures/good_single_skill",
        )
        self.assert_clean_pass(report)
        self.assertEqual(report.get("target_path"), ".agents/skills/skillguard/fixtures/good_single_skill")

    def test_suite_example_command(self) -> None:
        report = run_skillguard(
            "check-suite",
            "--suite-root",
            ".agents/skills/skillguard/fixtures/good_suite/suite",
            "--suite-map",
            ".agents/skills/skillguard/fixtures/good_suite/suite/suite-map.json",
            "--suite-contract",
            ".agents/skills/skillguard/fixtures/good_suite/suite/suite-contract.json",
            "--member-root",
            ".agents/skills",
        )
        self.assert_clean_pass(report)
        self.assertEqual(report.get("target_path"), ".agents/skills/skillguard/fixtures/good_suite/suite")

    def test_fixture_manifest_examples(self) -> None:
        positive = run_skillguard("fixture-test", "--manifest", ".agents/skills/skillguard/fixtures/fixture-manifest.json")
        self.assert_clean_pass(positive)
        self.assertEqual(positive.get("fixture_class_counts", {}).get("expected_pass"), 3)

        selected_fixture = run_skillguard(
            "fixture-test",
            "--manifest",
            ".agents/skills/skillguard/fixtures/runtime_contract/fixture-manifest.json",
            "--fixture-id",
            "former-runtime-authority-blocked",
        )
        self.assert_clean_pass(selected_fixture)
        self.assertEqual(len(selected_fixture.get("fixture_results", [])), 1)
        self.assertEqual(selected_fixture["fixture_results"][0].get("fixture_id"), "former-runtime-authority-blocked")

        missing_fixture = run_skillguard(
            "fixture-test",
            "--manifest",
            ".agents/skills/skillguard/fixtures/runtime_contract/fixture-manifest.json",
            "--fixture-id",
            "missing_fixture_id",
            expected_exit=1,
        )
        self.assertIn("missing_fixture_id", "\n".join(missing_fixture.get("failures", [])))

        simple_generation = run_skillguard("fixture-test", "--manifest", ".agents/skills/skillguard/fixtures/simple_generation/fixture-manifest.json")
        self.assert_clean_pass(simple_generation)
        self.assertEqual(simple_generation.get("fixture_class_counts", {}).get("expected_pass"), 1)
        self.assertEqual(simple_generation.get("fixture_class_counts", {}).get("blocker_condition"), 1)
        generation_results = {item.get("fixture_id"): item for item in simple_generation.get("fixture_results", [])}
        happy = generation_results["generate_skill_simple_public_input"]
        self.assertEqual(happy.get("target_command"), "generate-skill")
        self.assertTrue(happy.get("deterministic_repeat_checked"))
        self.assertEqual(happy.get("generation_validation", {}).get("check_maintenance_record_decision"), "pass")
        self.assertEqual(happy.get("generation_validation", {}).get("detect_stale_evidence_decision"), "pass")
        self.assertEqual(generation_results["generate_skill_existing_user_file_blocks"].get("observed_decision"), "block")

        complex_generation = run_skillguard("fixture-test", "--manifest", ".agents/skills/skillguard/fixtures/complex_generation/fixture-manifest.json")
        self.assert_clean_pass(complex_generation)
        self.assertEqual(complex_generation.get("fixture_class_counts", {}).get("expected_pass"), 1)
        self.assertEqual(complex_generation.get("fixture_class_counts", {}).get("expected_fail"), 1)
        self.assertEqual(complex_generation.get("fixture_class_counts", {}).get("blocker_condition"), 1)
        complex_results = {item.get("fixture_id"): item for item in complex_generation.get("fixture_results", [])}
        complex_happy = complex_results["generate_skill_complex_public_input"]
        self.assertTrue(complex_happy.get("deterministic_repeat_checked"))
        self.assertEqual(complex_happy.get("generation_validation", {}).get("check_maintenance_record_decision"), "pass")
        self.assertEqual(complex_happy.get("generation_validation", {}).get("detect_stale_evidence_decision"), "pass")
        self.assertEqual(complex_happy.get("generation_validation", {}).get("public_boundary_problem_count"), 0)
        self.assertEqual(complex_results["generate_skill_complex_missing_description_blocks"].get("observed_decision"), "block")
        self.assertEqual(complex_results["generate_skill_complex_corrupted_output_fails"].get("observed_decision"), "fail")

        bad_static = run_skillguard("fixture-test", "--manifest", ".agents/skills/skillguard/fixtures/bad_static/fixture-manifest.json")
        self.assert_clean_pass(bad_static)
        self.assertEqual(bad_static.get("fixture_class_counts", {}).get("blocker_condition"), 3)

        bad_suite = run_skillguard("fixture-test", "--manifest", ".agents/skills/skillguard/fixtures/bad_suite_stale/fixture-manifest.json")
        self.assert_clean_pass(bad_suite)
        self.assertEqual(bad_suite.get("fixture_class_counts", {}).get("expected_fail"), 4)

        deep_contract = run_skillguard("fixture-test", "--manifest", ".agents/skills/skillguard/fixtures/deep_contract/fixture-manifest.json")
        self.assert_clean_pass(deep_contract)
        self.assertEqual(deep_contract.get("fixture_class_counts", {}).get("blocker_condition"), 3)

        bad_routing = run_skillguard("fixture-test", "--manifest", ".agents/skills/skillguard/fixtures/bad_routing/fixture-manifest.json")
        self.assert_clean_pass(bad_routing)
        self.assertEqual(bad_routing.get("fixture_class_counts", {}).get("blocker_condition"), 11)
        expected_codes = {
            "conflicting_input_sources",
            "ambiguous_task_sources",
            "unsupported_route_hint",
            "stale_route_identifier",
            "mutually_exclusive_flags",
            "malformed_json",
            "invalid_path_config",
            "multiple_equal_route_candidates",
            "incompatible_route_identifiers",
            "responsibility_route_conflict",
            "incompatible_route_hint",
        }
        observed_codes = {
            code
            for result in bad_routing.get("fixture_results", [])
            for code in result.get("routing_conflict_blocker_codes", [])
        }
        self.assertEqual(observed_codes, expected_codes)
        self.assertFalse(any(result.get("routing_decision_present") for result in bad_routing.get("fixture_results", [])))
        self.assertTrue(all(result.get("deterministic_repeat_checked") for result in bad_routing.get("fixture_results", [])))

        global_router_evidence = [
            REPO_ROOT / ".agents" / "skills" / "skillguard" / "fixtures" / "global_router" / "workspace" / "global_router" / "global_registry.json",
            REPO_ROOT / ".agents" / "skills" / "skillguard" / "fixtures" / "global_router" / "workspace" / "global_router" / "global_prompt_projection.json",
            REPO_ROOT / ".agents" / "skills" / "skillguard" / "fixtures" / "global_router" / "workspace" / "codex_home" / "AGENTS.md",
        ]
        global_router_before = {path: sha256(path) for path in global_router_evidence}
        global_router = run_skillguard("fixture-test", "--manifest", ".agents/skills/skillguard/fixtures/global_router/fixture-manifest.json")
        self.assert_clean_pass(global_router)
        self.assertEqual(global_router.get("fixture_class_counts", {}).get("expected_pass"), 1)
        self.assertEqual(global_router.get("fixture_class_counts", {}).get("expected_fail"), 1)
        self.assertIsNone(global_router.get("fixture_class_counts", {}).get("blocker_condition"))
        self.assertEqual(global_router_before, {path: sha256(path) for path in global_router_evidence})

    def test_check_depth_blocks_former_authority_before_reading_old_run(self) -> None:
        source = REPO_ROOT / ".agents" / "skills" / "skillguard" / "fixtures" / "deep_contract" / "bad_missing_run_record"
        with tempfile.TemporaryDirectory(prefix="former-authority-", dir=REPO_ROOT / ".agents" / "skills") as tmp:
            target = Path(tmp) / "former-authority"
            shutil.copytree(source, target)

            report = run_skillguard(
                "check-depth",
                "--target",
                rel(target),
                expected_exit=1,
            )

            self.assertEqual("block", report.get("decision"))
            self.assertEqual("blocked", report.get("authority_decision"))
            self.assertIn("former_runtime_residual", report.get("blockers", []))

    def test_self_check_example_command(self) -> None:
        report = run_skillguard("self-check", "--target", ".agents/skills/skillguard")
        self.assert_clean_pass(report)

    def test_plan_skill_outputs_blueprint_without_writing_target(self) -> None:
        with tempfile.TemporaryDirectory(prefix="skillguard-plan-", dir=REPO_ROOT) as tmp:
            tmp_root = Path(tmp)
            target = tmp_root / "planned_skill"
            idea_path = tmp_root / "idea.json"
            write_json(idea_path, valid_skill_idea(rel(target)))

            report = run_skillguard("plan-skill", "--input", rel(idea_path))

            self.assert_clean_pass(report)
            self.assertFalse(target.exists(), "plan-skill must not create the declared target directory")
            blueprint = report.get("skill_blueprint")
            self.assertIsInstance(blueprint, dict)
            for field in (
                "blueprint_id",
                "target",
                "workflow_mode",
                "closure_scope",
                "evidence_policy",
                "safe_edit_scope",
                "phase_plan",
                "evidence_gates",
                "handoffs",
                "closure_report",
                "residual_risk",
                "claim_boundary",
            ):
                self.assertIn(field, blueprint)
            self.assertEqual(blueprint.get("workflow_mode"), "create")
            self.assertEqual(blueprint.get("safe_edit_scope", {}).get("target_file_writes_allowed"), False)
            self.assertGreaterEqual(len(blueprint.get("phase_plan", [])), 5)

    def test_plan_skill_blocks_missing_target_and_unsafe_writes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="skillguard-plan-", dir=REPO_ROOT) as tmp:
            tmp_root = Path(tmp)
            idea_path = tmp_root / "idea.json"
            idea = valid_skill_idea(rel(tmp_root / "planned_skill"))
            idea.pop("target_path")
            write_json(idea_path, idea)
            missing_target = run_skillguard("plan-skill", "--input", rel(idea_path), expected_exit=1)
            self.assertEqual(missing_target.get("decision"), "block")
            self.assertTrue(any("target_path" in blocker for blocker in missing_target.get("blockers", [])))

            unsafe_path = tmp_root / "unsafe.json"
            unsafe = valid_skill_idea(rel(tmp_root / "planned_skill"))
            unsafe["safe_edit_mode"] = "write"
            unsafe["write_target_files"] = True
            write_json(unsafe_path, unsafe)
            unsafe_report = run_skillguard("plan-skill", "--input", rel(unsafe_path), expected_exit=1)
            self.assertEqual(unsafe_report.get("decision"), "block")
            self.assertFalse((tmp_root / "planned_skill").exists())
            self.assertTrue(any("no_write" in blocker or "preview-only" in blocker for blocker in unsafe_report.get("blockers", [])))

    def test_commands_includes_plan_skill(self) -> None:
        report = run_skillguard("commands")
        self.assert_clean_pass(report)
        names = {item.get("name") for item in report.get("commands", [])}
        self.assertIn("route-task", names)
        self.assertIn("plan-skill", names)
        self.assertIn("generate-suite", names)
        self.assertIn("scan-global-skills", names)
        self.assertIn("build-global-registry", names)
        self.assertIn("check-global-registry", names)
        self.assertIn("refresh-global-router", names)
        self.assertNotIn("resolve-global-skill", names)
        self.assertNotIn("render-global-prompt", names)
        self.assertNotIn("install-global-prompt", names)
        self.assertNotIn("check-global-prompt", names)
        self.assertNotIn("audit-installed-skills", names)
        self.assertIn("detect-stale-evidence", names)
        self.assertNotIn("refresh-maintenance", names)
        self.assertIn("review-checker-change", names)
        self.assertIn("check-maintenance-record", names)
        self.assertIn("check-contract", names)
        self.assertIn("check-depth", names)
        self.assertIn("check-readme-release", names)
        for former_command in (
            "compile-contract",
            "select-route",
            "start-run",
            "advance-run",
            "check-run",
            "close-run",
            "check-skill-contract",
        ):
            self.assertNotIn(former_command, names)
        self.assertIn("capture-portfolio-production-revalidation", names)
        self.assertIn("graduate-portfolio", names)

    def test_check_readme_release_current_repo_passes(self) -> None:
        report = run_skillguard("check-readme-release", "--repo", ".")
        self.assert_clean_pass(report)
        check_ids = {item.get("check_id") for item in report.get("checks", [])}
        self.assertIn("check-readme-release:bilingual-mirror", check_ids)
        self.assertIn("check-readme-release:hero-provenance", check_ids)
        self.assertIn("check-readme-release:model-evidence", check_ids)
        self.assertIn("check-readme-release:version-consistency", check_ids)
        self.assertIn("check-readme-release:public-boundary", check_ids)

    def test_check_readme_release_blocks_stale_model_version(self) -> None:
        with tempfile.TemporaryDirectory(prefix="skillguard-readme-stale-model-", dir=REPO_ROOT) as tmp:
            tmp_root = Path(tmp)
            model_text = """
# SkillGuard README Model Evidence

This LogicGuard-backed capability model is for `v0.1.4`.

## Repository Fact Ledger
- product surface: local SkillGuard command surface.
- entry points: README and skillguard.py.
- release/version facts: current public notes reference v0.1.4.
- privacy-sensitive exclusions: no private data.

## Capability Claim Matrix
- claim: SkillGuard checks README releases.
- problem: stale claims can pass.
- mechanism: checker reads files.
- evidence: README files.
- warrant: local files support local claims.
- reader value: clearer release boundary.
- boundary: source-only.
- objection: future behavior is not guaranteed.

## Narrative Structure Plan
- first-screen promise: explain SkillGuard.
- section order: definition, workflow, commands, validation.
- visual proof placement: hero near the top.
- quick-start placement: command section.
- public/private boundary placement: near release gates.

## Gap Ledger
- unsupported claims: package publication.
- missing evidence: none for this fixture.
- maturity: local test fixture only.
- privacy risks: none.
"""
            self.write_minimal_readme_release_repo(tmp_root, version="0.1.5", model_text=model_text)

            report = run_skillguard("check-readme-release", "--repo", rel(tmp_root), expected_exit=1)

            self.assertEqual(report.get("decision"), "fail")
            failures = "\n".join(report.get("failures", []))
            self.assertIn("stale-readme-model-evidence", failures)
            self.assertIn("v0.1.4", failures)

    def test_check_readme_release_blocks_compact_model_without_showcase_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="skillguard-readme-compact-model-", dir=REPO_ROOT) as tmp:
            tmp_root = Path(tmp)
            model_text = (
                "# SkillGuard README Model Evidence\n\n"
                "This LogicGuard-backed capability model is for `v0.1.5` and includes mechanism, "
                "evidence, boundary, and objection notes, but no full README Showcase Writer matrix.\n"
            )
            self.write_minimal_readme_release_repo(tmp_root, version="0.1.5", model_text=model_text)

            report = run_skillguard("check-readme-release", "--repo", rel(tmp_root), expected_exit=1)

            self.assertEqual(report.get("decision"), "fail")
            failures = "\n".join(report.get("failures", []))
            self.assertIn("missing-readme-model-artifact", failures)
            self.assertIn("Repository Fact Ledger", failures)
            self.assertIn("Capability Claim Matrix", failures)

    def test_check_readme_release_blocks_missing_chinese_mirror(self) -> None:
        with tempfile.TemporaryDirectory(prefix="skillguard-readme-release-", dir=REPO_ROOT) as tmp:
            tmp_root = Path(tmp)
            skill_entrypoint = tmp_root / ".agents" / "skills" / "skillguard" / "SKILL.md"
            skill_entrypoint.parent.mkdir(parents=True)
            skill_entrypoint.write_text(
                "---\nname: skillguard\ndescription: Fixture SkillGuard source identity.\n---\n",
                encoding="utf-8",
            )
            hero_dir = tmp_root / "assets" / "readme-hero"
            hero_dir.mkdir(parents=True)
            (hero_dir / "hero.png").write_bytes(b"0" * 12_000)
            (hero_dir / "hero_prompt.md").write_text(
                "Prompt: SkillGuard visual concept.\nGeneration method: text-to-image model.\n",
                encoding="utf-8",
            )
            (hero_dir / "hero_design_note.md").write_text(
                "# Hero\n\n## Core workflow\n\nWorkflow evidence.\n\n## Visual concept\n\nVisual evidence.\n",
                encoding="utf-8",
            )
            (hero_dir / "readme_model_evidence.md").write_text(
                "LogicGuard capability model mechanism evidence boundary objection.\n",
                encoding="utf-8",
            )
            (tmp_root / "VERSION").write_text("0.1.4\n", encoding="utf-8")
            (tmp_root / "pyproject.toml").write_text(
                '[project]\nname = "skillguard"\nversion = "0.1.4"\n\n[tool.skillguard.repository]\nbaseline_version = "0.1.4"\n',
                encoding="utf-8",
            )
            (tmp_root / "CHANGELOG.md").write_text("# Changelog\n\n## v0.1.4 - 2026-06-28\n", encoding="utf-8")
            command_index = ", ".join(f"`{name}`" for name in checker_engine.COMMANDS)
            (tmp_root / "README.md").write_text(
                "\n".join(
                    [
                        "# SkillGuard",
                        "",
                        "<!-- README HERO START -->",
                        '<img src="./assets/readme-hero/hero.png" alt="SkillGuard concept hero image" width="100%" />',
                        "<!-- README HERO END -->",
                        "",
                        "Current release: `v0.1.4`",
                        "",
                        "English comes first; the second half is a full Chinese mirror.",
                        "",
                        "## Why It Exists",
                        "English-only placeholder.",
                        "",
                        command_index,
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            report = run_skillguard("check-readme-release", "--repo", rel(tmp_root), expected_exit=1)
            self.assertEqual(report.get("decision"), "fail")
            self.assertTrue(
                any("missing-bilingual-mirror" in item for item in report.get("failures", [])),
                report.get("failures", []),
            )

    def test_retired_installed_skill_audit_is_not_a_public_command(self) -> None:
        report = run_skillguard("commands")
        names = {item.get("name") for item in report.get("commands", [])}
        self.assertNotIn("audit-installed-skills", names)

    def test_global_route_score_prefers_readme_skill_for_readme_task(self) -> None:
        task = "用 README 技能给 SkillGuard 写发布 README，中英双语，文生图 hero"
        readme_score, readme_reasons = checker_engine.global_skill_route_score(
            {
                "skill_id": "readme-showcase-writer",
                "skill_name": "readme-showcase-writer",
                "route_terms": ["readme", "hero", "bilingual"],
            },
            task,
        )
        skillguard_score, skillguard_reasons = checker_engine.global_skill_route_score(
            {
                "skill_id": "skillguard",
                "skill_name": "skillguard",
                "route_terms": ["skillguard", "skill", "check"],
            },
            task,
        )
        self.assertIn("readme-showcase-task-bias", readme_reasons)
        self.assertNotIn("skillguard-boundary-audit-bias", skillguard_reasons)
        self.assertGreater(readme_score, skillguard_score)

    def test_global_router_refresh_prompt_and_route_resolution(self) -> None:
        with tempfile.TemporaryDirectory(prefix="skillguard-global-router-", dir=REPO_ROOT) as tmp:
            workspace = Path(tmp)
            codex_home = workspace / "codex_home"
            output_dir = workspace / "global_router"
            registry = output_dir / "global_registry.json"
            extra_root = workspace / "extra_skills"

            def write_skill(skill_dir: Path, name: str, description: str) -> None:
                skill_dir.mkdir(parents=True, exist_ok=True)
                skill_dir.joinpath("SKILL.md").write_text(
                    "\n".join(
                        [
                            "---",
                            f"name: {name}",
                            f"description: {description}",
                            "---",
                            "",
                            "# Purpose",
                            description,
                            "",
                            "## Use When",
                            f"- Use for {name} audit work and route handoff.",
                            "",
                            "## Do Not Use When",
                            "- Do not use for unrelated fixture tasks.",
                            "",
                        ]
                    ),
                    encoding="utf-8",
                )

            def compile_current_authority(skill_dir: Path) -> None:
                control = skill_dir / ".skillguard"
                control.mkdir(parents=True, exist_ok=True)
                scripts = skill_dir / "scripts"
                scripts.mkdir(parents=True, exist_ok=True)
                scripts.joinpath("run_checks.py").write_text(
                    "print('{\"decision\": \"pass\"}')\n",
                    encoding="utf-8",
                )
                model_source, binding = checker_engine.generated_current_contract_sources(
                    skill_dir.name
                )
                binding.update(
                    {
                        "repository_role": "skill_maintainer_source",
                        "maintenance_unit_id": f"unit:{skill_dir.name}",
                        "member_skill_ids": [skill_dir.name],
                        "consumer_projection": {
                            "projection_id": "projection:consumer-distribution",
                            "prohibited_path_prefixes": [".skillguard/"],
                            "prohibited_prompt_tokens": [
                                "SkillGuard",
                                ".skillguard",
                                "skillguard.py",
                            ],
                            "release_manifest_path": "consumer-release.json",
                        },
                    }
                )
                control.joinpath("flowguard_contract_model.py").write_text(
                    model_source,
                    encoding="utf-8",
                )
                write_json(control / "contract-source.json", binding)
                result = checker_engine.compile_skill_contract(
                    skill_dir,
                    repository_root=skill_dir,
                    write=True,
                )
                self.assertTrue(
                    result.ok,
                    [finding.to_dict() for finding in result.findings],
                )

            def write_former_contract_rejection(skill_dir: Path) -> None:
                control = skill_dir / ".skillguard"
                control.mkdir(parents=True, exist_ok=True)
                write_json(
                    control / "work-contract.json",
                    {
                        "schema_version": "skillguard.work_contract.v1",
                        "skill_id": skill_dir.name,
                    },
                )
                write_json(
                    control / "check_manifest.json",
                    {
                        "schema_version": "skillguard.check_manifest.v1",
                        "target_skill": rel(skill_dir),
                        "checks": [],
                    },
                )

            write_skill(extra_root / "fixture-missing-contract", "fixture-missing-contract", "Use for fixture missing contract global router tests.")
            write_skill(extra_root / "skillguard", "skillguard", "Use for fixture SkillGuard activation boundary audit tests.")
            compile_current_authority(extra_root / "skillguard")
            write_skill(
                extra_root / "skillguard-global-router",
                "skillguard-global-router",
                "Use for fixture global router registry prompt refresh tests.",
            )
            compile_current_authority(extra_root / "skillguard-global-router")
            write_skill(extra_root / "fixture-former-one", "fixture-former-one", "Exact former-authority rejection fixture.")
            write_former_contract_rejection(extra_root / "fixture-former-one")
            write_skill(extra_root / "fixture-former-two", "fixture-former-two", "Second exact former-authority rejection fixture.")
            write_former_contract_rejection(extra_root / "fixture-former-two")

            refresh = run_skillguard(
                "refresh-global-router",
                "--skill-root",
                rel(extra_root),
                "--codex-home",
                rel(codex_home),
                "--output-dir",
                rel(output_dir),
            )
            self.assert_clean_pass(refresh)
            self.assertEqual(refresh.get("target_path"), rel(output_dir))
            self.assertEqual(2, refresh.get("registry_item_count", 0), refresh)
            self.assertEqual(2, refresh.get("current_item_count", 0), refresh)
            self.assertTrue((codex_home / "AGENTS.md").is_file())
            self.assertTrue(registry.is_file())

            default_codex_home = workspace / "default_codex_home"
            default_refresh = run_skillguard(
                "refresh-global-router",
                "--skill-root",
                rel(extra_root),
                "--codex-home",
                rel(default_codex_home),
            )
            self.assert_clean_pass(default_refresh)
            default_output_dir = (
                default_codex_home / ".skillguard" / "global-router"
            )
            self.assertEqual(
                default_refresh.get("target_path"), rel(default_output_dir)
            )
            self.assertTrue(
                (default_output_dir / "global_registry.json").is_file()
            )

            registry_check = run_skillguard("check-global-registry", "--registry", rel(registry))
            self.assert_clean_pass(registry_check)
            self.assertEqual(registry_check.get("registry_hash"), refresh.get("registry_hash"))
            registry_payload = json.loads(registry.read_text(encoding="utf-8"))
            entries = {item.get("skill_id"): item for item in registry_payload.get("items", [])}
            self.assertEqual(
                {"skillguard", "skillguard-global-router"},
                set(entries),
            )
            self.assertTrue(
                all(
                    item.get("route_entrypoint", {}).get("repository_role")
                    == "skill_maintainer_source"
                    for item in entries.values()
                )
            )
            self.assertTrue(
                any(
                    "not an explicit SkillGuard author source" in warning
                    for warning in registry_payload.get("warnings", [])
                )
            )

            managed_prompt = (codex_home / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("private maintainer-computer routing projection", managed_prompt)
            self.assertIn(
                "Do not use this registry as a pre-execution gate for ordinary domain use",
                managed_prompt,
            )
            self.assertIn(
                "Different maintenance units never share, import, project, or reuse check receipts",
                managed_prompt,
            )
            self.assertIn(
                "External OpenSpec is outside this registry",
                managed_prompt,
            )
            self.assertIn("## Validated Template Pack Selection", managed_prompt)
            self.assertIn("## Validated Template Pack Instance", managed_prompt)
            self.assertIn("## Validated Template Pack Installation", managed_prompt)
            self.assertIn("global_router_selects_domain_template: false", managed_prompt)
            self.assertNotIn("Before using a Codex skill", managed_prompt)

    def test_global_registry_check_resolves_codex_scan_roots_from_codex_home(self) -> None:
        with tempfile.TemporaryDirectory(prefix="skillguard-global-router-roots-", dir=REPO_ROOT) as tmp:
            workspace = Path(tmp)
            codex_home = workspace / ".codex"
            skills_root = codex_home / "skills"
            plugin_root = codex_home / "plugins" / "cache" / "openai-bundled"
            skills_root.mkdir(parents=True)
            plugin_root.mkdir(parents=True)
            registry = {
                "scan_roots": [
                    {"path": ".codex/skills"},
                    {"path": ".codex/plugins/cache/openai-bundled"},
                ]
            }
            roots, blockers = checker_engine.registry_roots_for_check(registry, [], str(codex_home))
            self.assertEqual(blockers, [])
            self.assertEqual([skills_root.resolve(), plugin_root.resolve()], roots)

    def test_global_registry_currentness_accepts_explicit_external_author_roots(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="skillguard-external-author-root-",
            dir=REPO_ROOT.parent,
        ) as temporary:
            external_root = Path(temporary)
            current = {"registry_hash": "sha256:" + "a" * 64}
            with patch(
                "checker_engine.build_global_registry_payload",
                return_value=current,
            ) as rebuild:
                failures, blockers = (
                    checker_engine.global_registry_current_route_failures(
                        current,
                        codex_home=str(REPO_ROOT / ".codex"),
                        skill_roots=[str(external_root)],
                    )
                )
            self.assertEqual([], failures)
            self.assertEqual([], blockers)
            rebuild.assert_called_once_with([external_root.resolve()])

    def test_global_registry_hash_is_stable_between_installed_cli_and_test_mesh_contexts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="skillguard-global-router-context-", dir=REPO_ROOT) as tmp:
            workspace = Path(tmp)
            fake_home = workspace / "home"
            skills_root = fake_home / ".codex" / "skills"
            fixture_skill = skills_root / "fixture-skill"
            fixture_skill.mkdir(parents=True)
            fixture_skill.joinpath("SKILL.md").write_text(
                "---\nname: fixture-skill\ndescription: Stable router fixture.\n---\n",
                encoding="utf-8",
            )

            with patch.object(Path, "home", return_value=fake_home), patch(
                "checker_engine.repository_root", return_value=fake_home
            ):
                installed_cli_view = checker_engine.build_global_registry_payload(
                    [skills_root]
                )
            with patch.object(Path, "home", return_value=fake_home), patch(
                "checker_engine.repository_root", return_value=REPO_ROOT
            ):
                test_mesh_view = checker_engine.build_global_registry_payload(
                    [skills_root]
                )

            self.assertEqual(".codex/skills", installed_cli_view["scan_roots"][0]["path"])
            self.assertEqual(installed_cli_view["scan_roots"], test_mesh_view["scan_roots"])
            self.assertEqual(installed_cli_view["items"], test_mesh_view["items"])
            self.assertEqual(
                installed_cli_view["registry_hash"], test_mesh_view["registry_hash"]
            )

    def test_self_contract_projects_as_current_native_route(self) -> None:
        skill_dir = REPO_ROOT / ".agents" / "skills" / "skillguard"
        projection, warnings = checker_engine.global_contract_projection(skill_dir)

        self.assertEqual(warnings, [])
        self.assertEqual(projection.get("contract_authority"), "current")
        self.assertEqual(projection.get("integration_mode"), "native-integrated")
        self.assertEqual(
            projection.get("native_route_owner"),
            "skillguard.executable_contract_runtime.v2",
        )
        self.assertTrue(projection.get("native_route_bindings"))
        self.assertTrue(projection.get("native_check_bindings"))
        self.assertFalse(projection.get("may_define_parallel_execution_route"))
        self.assertFalse(projection.get("may_define_skillguard_runtime_route"))


    def test_current_command_surface_rejects_every_removed_live_entrypoint(self) -> None:
        target = REPO_ROOT / ".agents" / "skills" / "skillguard"
        command_report = run_skillguard("commands")
        current_names = {row.get("name") for row in command_report.get("commands", [])}

        for former_command in (
            "compile-contract",
            "select-route",
            "start-run",
            "advance-run",
            "check-run",
            "close-run",
            "check-skill-contract",
            "refresh-maintenance",
            "project-upgrade",
        ):
            with self.subTest(command=former_command):
                self.assertNotIn(former_command, current_names)
                rejected = run_skillguard(
                    former_command,
                    "--target",
                    rel(target),
                    expected_exit=2,
                )
                self.assertEqual("fail", rejected.get("decision"))
                self.assertEqual(
                    [f"unknown command: {former_command}"],
                    rejected.get("failures"),
                )

    def test_route_task_routes_ordinary_task_and_is_deterministic(self) -> None:
        task = "Create a draft skill scaffold from a Skill Blueprint"

        first = run_skillguard("route-task", "--task", task)
        second = run_skillguard("route-task", "--task", task)

        self.assert_clean_pass(first)
        self.assert_clean_pass(second)
        first_route = first.get("routing_decision", {})
        second_route = second.get("routing_decision", {})
        for field in ("route_id", "route_node_id", "command_family", "responsibility", "next_step"):
            self.assertEqual(first_route.get(field), second_route.get(field))
        self.assertEqual(first_route.get("command_family"), "generate-skill")
        self.assertEqual(first_route.get("route_node_id"), "generate-skill")
        self.assertEqual(first.get("task_fingerprint"), second.get("task_fingerprint"))
        self.assertNotIn(task, json.dumps(first, sort_keys=True))
        self.assertTrue(any(item.get("command_family") == "generate-skill" for item in first.get("candidate_routes", [])))
        registry = self.assert_validation_registry(first, "route-task", "pass")
        self.assertIn("route-task:selection", self.validation_registry_ids(registry))
        self.assertTrue(
            any(
                item.get("evidence_id") == "route-task-current-route-registry"
                for item in registry.get("evidence", [])
                if isinstance(item, dict)
            )
        )

    def test_route_task_routes_exact_portfolio_production_phases(self) -> None:
        cases = (
            (
                "Capture portfolio production revalidation for the completed member",
                "capture-portfolio-production-revalidation",
            ),
            (
                "Graduate portfolio after the assembled production receipts are current",
                "graduate-portfolio",
            ),
        )
        for task, expected in cases:
            with self.subTest(expected=expected):
                report = run_skillguard("route-task", "--task", task)
                self.assert_clean_pass(report)
                route = report.get("routing_decision", {})
                self.assertEqual(expected, route.get("command_family"))
                self.assertEqual(expected, route.get("route_node_id"))

    def test_route_task_honors_explicit_current_route_hint(self) -> None:
        report = run_skillguard("route-task", "--task", "Review suite records and member evidence.", "--route-hint", "check-suite")

        self.assert_clean_pass(report)
        self.assertEqual(report.get("routing_conflict_blockers"), [])
        route = report.get("routing_decision", {})
        self.assertEqual(route.get("selection_reason"), "explicit_route_hint")
        self.assertEqual(route.get("command_family"), "check-suite")
        self.assertEqual(route.get("responsibility"), "checker")

    def test_route_task_blocks_ambiguous_input(self) -> None:
        report = run_skillguard("route-task", "--task", "check skill and check suite", expected_exit=1)
        repeat = run_skillguard("route-task", "--task", "check skill and check suite", expected_exit=1)

        conflict = self.assert_route_conflict(report, "multiple_equal_route_candidates")
        self.assertEqual(report.get("routing_conflict_blockers"), repeat.get("routing_conflict_blockers"))
        self.assertTrue(any("ambiguous" in blocker for blocker in report.get("blockers", [])))
        self.assertGreaterEqual(len(report.get("candidate_routes", [])), 2)
        self.assertGreaterEqual(len(conflict.get("conflicting_candidates", [])), 2)

    def test_route_task_blocks_incompatible_route_hint_without_route_selection(self) -> None:
        task = "Create a draft skill scaffold from a Skill Blueprint"

        report = run_skillguard("route-task", "--task", task, "--route-hint", "check-suite", expected_exit=1)

        conflict = self.assert_route_conflict(report, "incompatible_route_hint")
        self.assertEqual(report.get("target_path"), "")
        candidate_commands = {item.get("command_family") for item in conflict.get("conflicting_candidates", [])}
        self.assertIn("check-suite", candidate_commands)
        self.assertIn("generate-skill", candidate_commands)
        self.assertNotIn(task, json.dumps(report, sort_keys=True))

    def test_route_task_blocks_mutually_exclusive_flags(self) -> None:
        with tempfile.TemporaryDirectory(prefix="route-task-", dir=REPO_ROOT) as tmp:
            input_path = Path(tmp) / "route-task.json"
            write_json(
                input_path,
                {
                    "task": "Create a draft skill scaffold from a Skill Blueprint",
                    "execute": True,
                    "dry_run": True,
                },
            )

            report = run_skillguard("route-task", "--input", rel(input_path), expected_exit=1)

            conflict = self.assert_route_conflict(report, "mutually_exclusive_flags")
            self.assertEqual(set(conflict.get("conflicting_fields", [])), {"$.execute", "$.dry_run"})

    def test_route_task_blocks_requested_responsibility_conflict(self) -> None:
        with tempfile.TemporaryDirectory(prefix="route-task-", dir=REPO_ROOT) as tmp:
            input_path = Path(tmp) / "route-task.json"
            write_json(
                input_path,
                {
                    "task": "Create a draft skill scaffold from a Skill Blueprint",
                    "requested_responsibility": "checker",
                },
            )

            report = run_skillguard("route-task", "--input", rel(input_path), expected_exit=1)

            conflict = self.assert_route_conflict(report, "responsibility_route_conflict")
            self.assertEqual(report.get("requested_responsibility"), "checker")
            self.assertTrue(any(item.get("responsibility") == "generator" for item in conflict.get("conflicting_candidates", [])))

    def test_route_task_blocks_conflicting_route_identifier_fields(self) -> None:
        with tempfile.TemporaryDirectory(prefix="route-task-", dir=REPO_ROOT) as tmp:
            input_path = Path(tmp) / "route-task.json"
            write_json(
                input_path,
                {
                    "task": "Create a draft skill scaffold from a Skill Blueprint",
                    "route_id": "skillguard.route.generate-skill.v1",
                    "route_node_id": "check-suite",
                },
            )

            report = run_skillguard("route-task", "--input", rel(input_path), expected_exit=1)

            conflict = self.assert_route_conflict(report, "incompatible_route_identifiers")
            self.assertEqual(set(conflict.get("conflicting_fields", [])), {"$.route_id", "$.route_node_id"})

    def test_route_task_blocks_unsupported_route_hint_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="route-task-", dir=REPO_ROOT) as tmp:
            workspace = Path(tmp)
            target = workspace / "must-not-exist"
            input_path = workspace / "route-task.json"
            write_json(
                input_path,
                {
                    "task": "Create a draft skill scaffold from a Skill Blueprint",
                    "route_hint": "old-router-v0",
                    "target_path": rel(target),
                },
            )

            report = run_skillguard("route-task", "--input", rel(input_path), expected_exit=1)

            self.assert_route_conflict(report, "stale_route_identifier")
            self.assertTrue(any("not a current public route" in blocker or "unsupported route_hint" in blocker for blocker in report.get("blockers", [])))
            self.assertFalse(target.exists())
            self.assertNotIn("created_files", report)

    def test_route_task_blocks_malformed_json_and_invalid_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="route-task-", dir=REPO_ROOT) as tmp:
            workspace = Path(tmp)
            malformed_path = workspace / "malformed.json"
            malformed_path.write_text("{not valid json\n", encoding="utf-8")

            malformed = run_skillguard("route-task", "--input", rel(malformed_path), expected_exit=1)
            self.assert_route_conflict(malformed, "malformed_json")
            self.assertTrue(any("invalid JSON" in blocker or "parse" in blocker for blocker in malformed.get("blockers", [])))

            invalid_path = workspace / "invalid-path.json"
            write_json(
                invalid_path,
                {
                    "task": "Create a draft skill scaffold from a Skill Blueprint",
                    "target_path": "../outside-skillguard",
                },
            )
            invalid = run_skillguard("route-task", "--input", rel(invalid_path), expected_exit=1)
            self.assert_route_conflict(invalid, "invalid_path_config")
            self.assertTrue(any("escapes repository boundary" in blocker for blocker in invalid.get("blockers", [])))
            self.assertTrue(any(item.get("status") == "block" for item in invalid.get("path_checks", [])))
            registry = self.assert_validation_registry(invalid, "route-task", "block")
            self.assertIn("invalid_path_config", self.validation_registry_blocker_codes(registry))
            categories = {
                row.get("blocker_category")
                for row in registry.get("blocker_evidence", [])
                if isinstance(row, dict)
            }
            self.assertIn("invalid_input", categories)

    def test_route_task_blocks_conflicting_cli_input_modes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="route-task-", dir=REPO_ROOT) as tmp:
            input_path = Path(tmp) / "route-task.json"
            write_json(input_path, {"task": "Create a draft skill scaffold from a Skill Blueprint"})

            report = run_skillguard("route-task", "--input", rel(input_path), "--task", "Check a skill", expected_exit=1)

            self.assert_route_conflict(report, "conflicting_input_sources")
            self.assertTrue(any("cannot be combined" in blocker for blocker in report.get("blockers", [])))

    def test_route_task_executes_generate_skill_from_explicit_route_hint(self) -> None:
        with tempfile.TemporaryDirectory(prefix="route-task-generated-skill-", dir=REPO_ROOT / ".agents" / "skills") as tmp:
            workspace = Path(tmp)
            target = workspace / "routed-review-helper"
            idea_path = workspace / "idea.json"
            plan_path = workspace / "blueprint.json"
            route_input_path = workspace / "route-task.json"
            write_json(idea_path, valid_skill_idea(rel(target), skill_name=target.name))
            plan_report = run_skillguard("plan-skill", "--input", rel(idea_path))
            write_json(plan_path, plan_report)
            write_json(
                route_input_path,
                {
                    "task": "Create a draft skill scaffold from a Skill Blueprint",
                    "route_hint": "generate-skill",
                    "input_path": rel(plan_path),
                },
            )

            report = run_skillguard("route-task", "--input", rel(route_input_path))

            self.assert_clean_pass(report)
            self.assertEqual(report.get("command"), "generate-skill")
            self.assertEqual(report.get("target_path"), rel(target))
            self.assertTrue((target / "SKILL.md").is_file())
            self.assertEqual(
                [(item.get("command"), item.get("artifact_path"), item.get("status")) for item in report.get("post_generation_checks", [])],
                [
                    ("check-skill", rel(target), "pass"),
                    ("check-contract", rel(target / ".skillguard" / "contract-source.json"), "pass"),
                ],
            )
            registry = self.assert_validation_registry(report, "generate-skill", "pass")
            self.assertIn("generate-skill:post-generation-checks", self.validation_registry_ids(registry))
            self.assertIn("generate-skill:post-check-skill", self.validation_registry_ids(registry))
            self.assertIn("generate-skill:post-check-contract", self.validation_registry_ids(registry))
            self.assertIn("generate-skill:global-router-refresh-required", self.validation_registry_ids(registry))
            self.assertEqual(report.get("global_router_refresh", {}).get("status"), "required_after_generation")
            self.assertEqual(report.get("global_router_refresh", {}).get("command"), "refresh-global-router")
            self.assertIn("post_generation_checks", registry.get("source_of_truth_for", []))

    def test_route_task_executes_generate_suite_from_explicit_route_hint(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rgs-", dir=REPO_ROOT / ".agents" / "skills") as tmp:
            workspace = Path(tmp)
            target = workspace / "routed-review-suite"
            suite_root = target / ".skillguard" / "suite"
            blueprint_path = workspace / "suite-blueprint.json"
            route_input_path = workspace / "route-task.json"
            write_json(blueprint_path, valid_suite_blueprint(rel(target), target.name))
            write_json(
                route_input_path,
                {
                    "task": "Create a draft suite scaffold from a Suite Blueprint",
                    "route_hint": "generate-suite",
                    "input_path": rel(blueprint_path),
                },
            )

            report = run_skillguard("route-task", "--input", rel(route_input_path))

            self.assert_clean_pass(report)
            self.assertEqual(report.get("command"), "generate-suite")
            self.assertEqual(report.get("target_path"), rel(target))
            self.assertTrue((suite_root / "suite-map.json").is_file())
            self.assertTrue(all(item.get("status") == "pass" for item in report.get("post_generation_checks", [])))
            registry = self.assert_validation_registry(report, "generate-suite", "pass")
            self.assertIn("generate-suite:post-generation-checks", self.validation_registry_ids(registry))
            post_rows = [
                row
                for row in registry.get("validation_rows", [])
                if isinstance(row, dict) and row.get("validation_kind") == "post_generation_check"
            ]
            self.assertGreaterEqual(len(post_rows), 3)

    def test_route_task_blocks_generator_command_path_without_explicit_hint(self) -> None:
        with tempfile.TemporaryDirectory(prefix="route-task-unhinted-generator-", dir=REPO_ROOT / ".agents" / "skills") as tmp:
            workspace = Path(tmp)
            target = workspace / "unhinted-review-helper"
            idea_path = workspace / "idea.json"
            plan_path = workspace / "blueprint.json"
            route_input_path = workspace / "route-task.json"
            write_json(idea_path, valid_skill_idea(rel(target), skill_name=target.name))
            plan_report = run_skillguard("plan-skill", "--input", rel(idea_path))
            write_json(plan_path, plan_report)
            write_json(
                route_input_path,
                {
                    "task": "Create a draft skill scaffold from a Skill Blueprint",
                    "input_path": rel(plan_path),
                    "execute": True,
                },
            )

            report = run_skillguard("route-task", "--input", rel(route_input_path), expected_exit=1)

            self.assert_route_conflict(report, "command_path_requires_explicit_route_hint")
            self.assertFalse((target / "SKILL.md").exists())
            registry = self.assert_validation_registry(report, "route-task", "block")
            self.assertIn("command_path_requires_explicit_route_hint", self.validation_registry_blocker_codes(registry))
            categories = {
                row.get("blocker_category")
                for row in registry.get("blocker_evidence", [])
                if isinstance(row, dict)
            }
            self.assertIn("blocked_generation_request", categories)

    def test_route_task_registry_records_no_write_generator_blocker(self) -> None:
        with tempfile.TemporaryDirectory(prefix="route-task-no-write-generator-", dir=REPO_ROOT / ".agents" / "skills") as tmp:
            workspace = Path(tmp)
            target = workspace / "no-write-review-helper"
            idea_path = workspace / "idea.json"
            plan_path = workspace / "blueprint.json"
            route_input_path = workspace / "route-task.json"
            write_json(idea_path, valid_skill_idea(rel(target), skill_name=target.name))
            plan_report = run_skillguard("plan-skill", "--input", rel(idea_path))
            write_json(plan_path, plan_report)
            write_json(
                route_input_path,
                {
                    "task": "Create a draft skill scaffold from a Skill Blueprint",
                    "route_hint": "generate-skill",
                    "input_path": rel(plan_path),
                    "no_write": True,
                },
            )

            report = run_skillguard("route-task", "--input", rel(route_input_path), expected_exit=1)

            self.assert_route_conflict(report, "generator_execution_forbidden_by_no_write_flag")
            self.assertFalse((target / "SKILL.md").exists())
            registry = self.assert_validation_registry(report, "route-task", "block")
            self.assertIn("generator_execution_forbidden_by_no_write_flag", self.validation_registry_blocker_codes(registry))

    def test_detect_stale_evidence_passes_fresh_source_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory(prefix="detect-stale-", dir=REPO_ROOT) as tmp:
            workspace = Path(tmp)
            source_path = workspace / "source.txt"
            source_path.write_text("fresh source\n", encoding="utf-8")
            evidence_path = workspace / "evidence.json"
            write_json(
                evidence_path,
                freshness_record_for(
                    source_path,
                    route_version=checker_engine.DETECT_STALE_EXPECTED_ROUTE_VERSION,
                    route_registry_version=checker_engine.ROUTE_TASK_REGISTRY_VERSION,
                    command_names=list(checker_engine.COMMANDS),
                ),
            )

            report = run_skillguard("detect-stale-evidence", "--input", rel(evidence_path))

            self.assert_clean_pass(report)
            self.assertEqual(report.get("stale_evidence_blockers"), [])
            self.assertGreaterEqual(report.get("freshness_bindings_checked", 0), 4)
            freshness = report.get("maintenance_freshness", {})
            self.assertEqual(freshness.get("state"), "fresh")
            self.assertTrue(freshness.get("current_evidence_can_pass"))
            self.assertEqual(freshness.get("missing_count"), 0)
            self.assertIn("fresh", freshness.get("states_supported", []))

    def test_detect_stale_evidence_blocks_stale_source_route_fixture_generated_command_and_missing_metadata(self) -> None:
        with tempfile.TemporaryDirectory(prefix="detect-stale-", dir=REPO_ROOT) as tmp:
            workspace = Path(tmp)
            source_path = workspace / "source.txt"
            source_path.write_text("original\n", encoding="utf-8")
            stale_source_path = workspace / "stale-source.json"
            write_json(stale_source_path, freshness_record_for(source_path))
            source_path.write_text("changed\n", encoding="utf-8")

            route_path = workspace / "stale-route.json"
            write_json(
                route_path,
                freshness_record_for(source_path, route_version="3", route_registry_version="stale-registry.v0"),
            )

            manifest_path = workspace / "fixture-manifest.json"
            case_path = workspace / "case.fixture.json"
            manifest_path.write_text('{"schema_version":"skillguard.fixture_manifest.v1","fixtures":[]}\n', encoding="utf-8")
            case_path.write_text('{"fixture_id":"stale-case"}\n', encoding="utf-8")
            fixture_output_path = workspace / "fixture-output.json"
            write_json(
                fixture_output_path,
                {
                    "schema_version": "skillguard.cli_result.v1",
                    "command": "fixture-test",
                    "decision": "pass",
                    "checked_at": utc_timestamp(),
                    "target_path": rel(manifest_path),
                    "files_inspected": [{"path": rel(manifest_path), "sha256": sha256(manifest_path), "kind": "json"}],
                    "fixture_results": [{"fixture_id": "stale-case", "fixture_path": rel(case_path), "sha256": sha256(case_path)}],
                    "evidence": [],
                    "failures": [],
                    "blockers": [],
                    "skipped_checks": [],
                    "residual_risk": [],
                    "claim_boundary": "Synthetic fixture output.",
                },
            )
            manifest_path.write_text('{"schema_version":"skillguard.fixture_manifest.v1","fixtures":[1]}\n', encoding="utf-8")
            case_path.write_text('{"fixture_id":"stale-case","changed":true}\n', encoding="utf-8")

            generated_path = workspace / "generated-output.json"
            write_json(
                generated_path,
                {
                    "schema_version": "skillguard.cli_result.v1",
                    "command": "generate-skill",
                    "decision": "pass",
                    "checked_at": utc_timestamp(),
                    "all_scaffold_files": [rel(workspace / "missing-generated" / "SKILL.md")],
                    "evidence": [],
                    "failures": [],
                    "blockers": [],
                    "skipped_checks": [],
                    "residual_risk": [],
                    "claim_boundary": "Synthetic generated output.",
                },
            )

            command_surface_path = workspace / "stale-command-surface.json"
            write_json(command_surface_path, freshness_record_for(source_path, command="self-check", command_names=["commands"]))

            missing_metadata_path = workspace / "missing-metadata.json"
            write_json(
                missing_metadata_path,
                {
                    "schema_version": "skillguard.cli_result.v1",
                    "command": "check-skill",
                    "decision": "pass",
                    "checked_at": utc_timestamp(),
                    "evidence": [{"evidence_id": "summary-only", "summary": "No comparable metadata."}],
                },
            )

            openspec_status_path = workspace / "stale-openspec-status.json"
            write_json(
                openspec_status_path,
                {
                    "schema_version": "skillguard.cli_result.v1",
                    "command": "detect-stale-evidence",
                    "decision": "pass",
                    "checked_at": utc_timestamp(),
                    "openspec_status": {
                        "changes_directory_present": not checker_engine.current_openspec_changes_present()
                    },
                    "claim_boundary": "Synthetic OpenSpec status evidence.",
                },
            )

            report = run_skillguard(
                "detect-stale-evidence",
                "--input",
                rel(stale_source_path),
                "--input",
                rel(route_path),
                "--input",
                rel(fixture_output_path),
                "--input",
                rel(generated_path),
                "--input",
                rel(command_surface_path),
                "--input",
                rel(missing_metadata_path),
                "--input",
                rel(openspec_status_path),
                expected_exit=1,
            )

            codes = stale_blocker_codes(report)
            self.assertEqual(report.get("decision"), "block")
            self.assertIn("stale_source_fingerprint", codes)
            self.assertIn("stale_route_version", codes)
            self.assertIn("stale_route_registry_version", codes)
            self.assertIn("stale_fixture_manifest", codes)
            self.assertIn("stale_fixture_output", codes)
            self.assertIn("stale_generated_artifact_path", codes)
            self.assertIn("stale_command_surface", codes)
            self.assertIn("missing_evidence_metadata", codes)
            self.assertIn("stale_openspec_status", codes)
            freshness = report.get("maintenance_freshness", {})
            self.assertEqual(freshness.get("state"), "stale_or_missing")
            self.assertFalse(freshness.get("current_evidence_can_pass"))
            self.assertGreater(freshness.get("stale_count", 0), 0)
            self.assertGreater(freshness.get("missing_count", 0), 0)
            self.assertIn("stale_evidence_blockers[].expected_current_binding", freshness.get("recorded_source_status_fields", []))
            for blocker in report.get("stale_evidence_blockers", []):
                self.assertTrue(blocker.get("artifact_id"))
                self.assertTrue(blocker.get("expected_current_binding"))
                self.assertTrue(blocker.get("observed_stale_binding"))
                self.assertTrue(blocker.get("recommended_owner_action"))

    def test_detect_stale_evidence_keeps_blockers_public_safe_and_read_only(self) -> None:
        with tempfile.TemporaryDirectory(prefix="detect-stale-", dir=REPO_ROOT) as tmp:
            workspace = Path(tmp)
            evidence_path = workspace / "private-probe.json"
            write_json(
                evidence_path,
                {
                    "schema_version": "skillguard.cli_result.v1",
                    "command": "check-skill",
                    "decision": "pass",
                    "private_payload": "PRIVATE_ROUTE_BODY_TEXT_DO_NOT_ECHO",
                },
            )
            before_hash = sha256(evidence_path)

            report = run_skillguard("detect-stale-evidence", "--input", rel(evidence_path), expected_exit=1)

            self.assertEqual(sha256(evidence_path), before_hash)
            output_text = json.dumps(report, sort_keys=True)
            self.assertNotIn("PRIVATE_ROUTE_BODY_TEXT_DO_NOT_ECHO", output_text)
            self.assertIn("missing_evidence_metadata", stale_blocker_codes(report))
            for blocker in report.get("stale_evidence_blockers", []):
                self.assertNotIn("private_payload", json.dumps(blocker, sort_keys=True))

    def test_check_maintenance_record_accepts_only_current_records(self) -> None:
        with tempfile.TemporaryDirectory(prefix="maintenance-record-", dir=REPO_ROOT) as tmp:
            workspace = Path(tmp)
            canonical_path = workspace / "canonical.json"
            write_json(canonical_path, valid_maintenance_record())

            canonical = run_skillguard("check-maintenance-record", "--input", rel(canonical_path))

            self.assert_clean_pass(canonical)
            self.assertEqual(canonical.get("record_shape"), "current_direct")
            self.assertEqual(canonical.get("normalized_record", {}).get("schema_version"), checker_engine.MAINTENANCE_RECORD_SCHEMA_VERSION)
            self.assertEqual(canonical.get("maintenance_record", {}).get("schema_version"), checker_engine.MAINTENANCE_RECORD_SCHEMA_VERSION)

            source_path = workspace / "source.txt"
            source_path.write_text("current\n", encoding="utf-8")
            former_path = workspace / "former-command-output.json"
            write_json(
                former_path,
                freshness_record_for(
                    source_path,
                    route_version=checker_engine.DETECT_STALE_EXPECTED_ROUTE_VERSION,
                    route_registry_version=checker_engine.ROUTE_TASK_REGISTRY_VERSION,
                    command_names=list(checker_engine.COMMANDS),
                    current_route_registry=[checker_engine.public_route_entry(entry) for entry in checker_engine.current_route_entries()],
                ),
            )

            former = run_skillguard(
                "check-maintenance-record",
                "--input",
                rel(former_path),
                expected_exit=1,
            )

            self.assertEqual(former.get("decision"), "block")
            self.assertEqual(former.get("record_shape"), "blocked_non_current")
            self.assertIn("non_current_maintenance_record", maintenance_blocker_codes(former))

    def test_check_maintenance_record_blocks_schema_route_command_alias_blocker_and_public_boundary_defects(self) -> None:
        with tempfile.TemporaryDirectory(prefix="maintenance-record-", dir=REPO_ROOT) as tmp:
            workspace = Path(tmp)
            cases: list[tuple[str, dict[str, Any], str]] = []

            missing = valid_maintenance_record()
            missing.pop("artifact_id")
            cases.append(("missing.json", missing, "missing_required_field"))

            alias = valid_maintenance_record(changes_directory_found=True)
            cases.append(("alias.json", alias, "unknown_legacy_alias"))

            bad_version = valid_maintenance_record(schema_version="skillguard.maintenance_record.v0")
            cases.append(("bad-version.json", bad_version, "non_current_maintenance_record"))

            malformed_blocker = valid_maintenance_record(blockers=["not-structured"])
            cases.append(("malformed-blocker.json", malformed_blocker, "malformed_blocker_row"))

            bad_route = valid_maintenance_record(route_version="3")
            cases.append(("bad-route.json", bad_route, "route_version_mismatch"))

            bad_command = valid_maintenance_record()
            bad_command["command_surface"]["command_names"] = ["commands"]
            cases.append(("bad-command.json", bad_command, "command_binding_mismatch"))

            leaked = valid_maintenance_record(artifact_id="PRIVATE_ROUTE_BODY_TEXT_DO_NOT_ECHO")
            cases.append(("leaked.json", leaked, "public_boundary_leakage"))

            unsupported_legacy = {
                "schema_version": "skillguard.legacy_record.v0",
                "private_payload": "PRIVATE_ROUTE_BODY_TEXT_DO_NOT_ECHO",
            }
            cases.append(("unsupported-former.json", unsupported_legacy, "non_current_maintenance_record"))

            for name, record, expected_code in cases:
                path = workspace / name
                write_json(path, record)
                report = run_skillguard("check-maintenance-record", "--input", rel(path), expected_exit=1)
                self.assertEqual(report.get("decision"), "block", name)
                self.assertIn(expected_code, maintenance_blocker_codes(report), name)
                output_text = json.dumps(report, sort_keys=True)
                self.assertNotIn("PRIVATE_ROUTE_BODY_TEXT_DO_NOT_ECHO", output_text)
                for blocker in report.get("maintenance_record_blockers", []):
                    self.assertTrue(blocker.get("artifact_id"))
                    self.assertTrue(blocker.get("observed_shape") is not None)
                    self.assertEqual(blocker.get("expected_schema_version"), checker_engine.MAINTENANCE_RECORD_SCHEMA_VERSION)
                    self.assertTrue(blocker.get("recommended_repair_action"))

    def test_maintenance_record_integration_with_stale_review_dispatch_and_self_check(self) -> None:
        with tempfile.TemporaryDirectory(prefix="maintenance-record-", dir=REPO_ROOT) as tmp:
            workspace = Path(tmp)
            source_path = workspace / "source.txt"
            source_path.write_text("original\n", encoding="utf-8")
            evidence_path = workspace / "evidence.json"
            write_json(evidence_path, freshness_record_for(source_path))
            source_path.write_text("changed\n", encoding="utf-8")

            stale = run_skillguard("detect-stale-evidence", "--input", rel(evidence_path), expected_exit=1)
            self.assertEqual(stale.get("maintenance_record", {}).get("record_kind"), "stale_evidence_review")
            stale_output = workspace / "stale-output.json"
            write_json(stale_output, stale)
            stale_check = run_skillguard("check-maintenance-record", "--input", rel(stale_output))
            self.assert_clean_pass(stale_check)

            baseline_path = workspace / "baseline.json"
            write_json(baseline_path, checker_change_baseline())
            review = run_skillguard("review-checker-change", "--baseline", rel(baseline_path))
            self.assertEqual(review.get("maintenance_record", {}).get("record_kind"), "checker_change_review")
            review_output = workspace / "review-output.json"
            write_json(review_output, review)
            review_check = run_skillguard("check-maintenance-record", "--input", rel(review_output))
            self.assert_clean_pass(review_check)

            commands = run_skillguard("commands")
            self.assert_clean_pass(commands)
            names = {item.get("name") for item in commands.get("commands", [])}
            self.assertIn("check-maintenance-record", names)
            self.assertEqual(commands.get("maintenance_record", {}).get("record_kind"), "command_surface")

            route = run_skillguard("route-task", "--task", "Validate the maintenance record schema")
            self.assert_clean_pass(route)
            self.assertEqual(route.get("routing_decision", {}).get("command_family"), "check-maintenance-record")

            self_check = run_skillguard("self-check", "--target", ".agents/skills/skillguard")
            self.assert_clean_pass(self_check)
            self.assertEqual(self_check.get("maintenance_record", {}).get("record_kind"), "self_check")

    def test_generation_fixture_maintenance_staleness_uses_current_evidence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="maintenance-generation-", dir=REPO_ROOT) as tmp:
            workspace = Path(tmp)

            simple_manifest = ".agents/skills/skillguard/fixtures/simple_generation/fixture-manifest.json"
            complex_manifest = ".agents/skills/skillguard/fixtures/complex_generation/fixture-manifest.json"
            simple = run_skillguard("fixture-test", "--manifest", simple_manifest)
            complex_report = run_skillguard("fixture-test", "--manifest", complex_manifest)
            self_check = run_skillguard("self-check", "--target", ".agents/skills/skillguard")
            target_check = run_skillguard("check-skill", "--target", ".agents/skills/skillguard")
            for workspace_path in (
                REPO_ROOT / ".agents" / "skills" / "skillguard" / "fixtures" / "simple_generation" / "workspace",
                REPO_ROOT / ".agents" / "skills" / "skillguard" / "fixtures" / "complex_generation" / "workspace",
            ):
                self.assertFalse(workspace_path.exists(), workspace_path)

            simple_path = workspace / "simple-fixture-current.json"
            complex_path = workspace / "complex-fixture-current.json"
            self_check_path = workspace / "self-check-current.json"
            target_check_path = workspace / "target-check-current.json"
            write_json(simple_path, simple)
            write_json(complex_path, complex_report)
            write_json(self_check_path, self_check)
            write_json(target_check_path, target_check)

            fresh = run_skillguard(
                "detect-stale-evidence",
                "--input",
                rel(simple_path),
                "--input",
                rel(complex_path),
                "--input",
                rel(self_check_path),
                "--input",
                rel(target_check_path),
            )
            self.assert_clean_pass(fresh)
            self.assertEqual(fresh.get("stale_evidence_count"), 0)
            self.assertEqual(fresh.get("maintenance_record", {}).get("record_kind"), "stale_evidence_review")
            for path in (simple_path, complex_path, self_check_path, target_check_path):
                maintenance = run_skillguard("check-maintenance-record", "--input", rel(path))
                self.assert_clean_pass(maintenance)
                self.assertEqual(maintenance.get("record_shape"), "current_nested")

            baseline_path = workspace / "checker-baseline.json"
            write_json(
                baseline_path,
                checker_change_baseline(
                    fixture_manifests=[
                        {
                            "path": simple_manifest,
                            "sha256": sha256(REPO_ROOT / simple_manifest),
                            "fixture_ids": [item.get("fixture_id") for item in simple.get("fixture_results", [])],
                        },
                        {
                            "path": complex_manifest,
                            "sha256": sha256(REPO_ROOT / complex_manifest),
                            "fixture_ids": [item.get("fixture_id") for item in complex_report.get("fixture_results", [])],
                        },
                    ],
                    evidence_records=[
                        {"path": rel(simple_path), "sha256": sha256(simple_path)},
                        {"path": rel(complex_path), "sha256": sha256(complex_path)},
                    ],
                ),
            )
            review = run_skillguard(
                "review-checker-change",
                "--baseline",
                rel(baseline_path),
                "--fixture-manifest",
                simple_manifest,
                "--fixture-manifest",
                complex_manifest,
                "--evidence",
                rel(simple_path),
                "--evidence",
                rel(complex_path),
            )
            self.assert_clean_pass(review)
            review_path = workspace / "review-current.json"
            write_json(review_path, review)
            review_maintenance = run_skillguard("check-maintenance-record", "--input", rel(review_path))
            self.assert_clean_pass(review_maintenance)

            def clone(payload: dict[str, Any]) -> dict[str, Any]:
                return json.loads(json.dumps(payload))

            governed_generated_artifact = workspace / "generated-artifact.md"
            governed_generated_artifact.write_text("generated artifact v1\n", encoding="utf-8")
            generated_hash_drift = clone(complex_report)
            generated_hash_drift["generated_artifact_hashes"] = [
                {
                    "path": rel(governed_generated_artifact),
                    "kind": "markdown",
                    "sha256": sha256(governed_generated_artifact),
                }
            ]
            governed_generated_artifact.write_text("generated artifact v2\n", encoding="utf-8")
            generated_hash_path = workspace / "generated-hash-drift.json"
            write_json(generated_hash_path, generated_hash_drift)

            fixture_manifest_drift = clone(complex_report)
            fixture_manifest_drift["files_inspected"][0]["sha256"] = "0" * 64
            fixture_manifest_drift["fixture_results"][0]["sha256"] = "1" * 64
            fixture_manifest_path = workspace / "fixture-manifest-drift.json"
            write_json(fixture_manifest_path, fixture_manifest_drift)

            route_drift = clone(complex_report)
            route_drift["route_version"] = "3"
            route_drift["route_registry_version"] = "stale-registry.v0"
            route_drift["maintenance_record"]["route_version"] = "3"
            route_drift["maintenance_record"]["route_registry_version"] = "stale-registry.v0"
            route_drift_path = workspace / "route-drift.json"
            write_json(route_drift_path, route_drift)

            missing_generated_metadata = clone(complex_report)
            missing_generated_metadata["generated_artifact_hashes"] = [{"path": rel(governed_generated_artifact)}]
            missing_generated_metadata_path = workspace / "missing-generated-metadata.json"
            write_json(missing_generated_metadata_path, missing_generated_metadata)

            stale_command = clone(self_check)
            stale_command["command_names"] = ["commands"]
            stale_command["current_route_registry"] = [{"route_id": "skillguard.route.old.v0"}]
            stale_command_path = workspace / "stale-command-output.json"
            write_json(stale_command_path, stale_command)

            malformed_maintenance = clone(complex_report)
            malformed_maintenance["maintenance_record"]["schema_version"] = "skillguard.maintenance_record.v0"
            malformed_maintenance["maintenance_record"]["changes_directory_found"] = True
            malformed_maintenance["maintenance_record"]["artifact_id"] = "PRIVATE_ROUTE_BODY_TEXT_DO_NOT_ECHO"
            malformed_maintenance_path = workspace / "malformed-maintenance-record.json"
            write_json(malformed_maintenance_path, malformed_maintenance)

            stale_inputs = [
                generated_hash_path,
                fixture_manifest_path,
                route_drift_path,
                missing_generated_metadata_path,
                stale_command_path,
                malformed_maintenance_path,
            ]
            before_hashes = {path: sha256(path) for path in stale_inputs}
            stale = run_skillguard(
                "detect-stale-evidence",
                *[arg for path in stale_inputs for arg in ("--input", rel(path))],
                expected_exit=1,
            )
            stale_again = run_skillguard(
                "detect-stale-evidence",
                *[arg for path in stale_inputs for arg in ("--input", rel(path))],
                expected_exit=1,
            )
            self.assertEqual(stale_blocker_codes(stale), stale_blocker_codes(stale_again))
            codes = stale_blocker_codes(stale)
            self.assertIn("stale_generated_artifact_hash", codes)
            self.assertIn("stale_fixture_manifest", codes)
            self.assertIn("stale_fixture_output", codes)
            self.assertIn("stale_route_version", codes)
            self.assertIn("stale_route_registry_version", codes)
            self.assertIn("route_version_mismatch", codes)
            self.assertIn("route_registry_version_mismatch", codes)
            self.assertIn("missing_evidence_metadata", codes)
            self.assertIn("stale_command_surface", codes)
            self.assertIn("stale_route_registry", codes)
            self.assertIn("incompatible_schema_version", codes)
            self.assertIn("unknown_legacy_alias", codes)
            for blocker in stale.get("stale_evidence_blockers", []):
                self.assertTrue(blocker.get("artifact_id"))
                self.assertTrue(blocker.get("binding_id"))
                self.assertTrue(blocker.get("stale_reason"))
                self.assertTrue(blocker.get("expected_current_binding"))
                self.assertTrue(blocker.get("observed_stale_binding"))
            for path, before_hash in before_hashes.items():
                self.assertEqual(sha256(path), before_hash, path)

            output_text = json.dumps({"stale": stale}, sort_keys=True)
            self.assertNotIn("PRIVATE_ROUTE_BODY_TEXT_DO_NOT_ECHO", output_text)
            self.assertNotIn("sealed packet body text", output_text)
            self.assertNotIn("sibling role-only result text", output_text)

    def test_review_checker_change_passes_unchanged_and_additive_command(self) -> None:
        with tempfile.TemporaryDirectory(prefix="review-checker-change-", dir=REPO_ROOT) as tmp:
            workspace = Path(tmp)
            baseline_path = workspace / "baseline.json"
            write_json(baseline_path, checker_change_baseline())

            unchanged = run_skillguard("review-checker-change", "--baseline", rel(baseline_path))

            self.assert_clean_pass(unchanged)
            self.assertEqual(unchanged.get("baseline_binding", {}).get("command_count"), len(checker_engine.COMMANDS))
            self.assertEqual(unchanged.get("checker_change_blockers"), [])
            self.assertTrue(unchanged.get("mutation_check", {}).get("read_only"))

            additive_commands = [
                item
                for item in checker_engine.current_checker_command_surface()
                if item.get("name") != "review-checker-change"
            ]
            additive_routes = [
                checker_engine.public_route_entry(entry)
                for entry in checker_engine.current_route_entries()
                if entry.get("command_family") != "review-checker-change"
            ]
            additive_baseline_path = workspace / "additive-baseline.json"
            write_json(
                additive_baseline_path,
                checker_change_baseline(command_surface=additive_commands, route_registry=additive_routes),
            )

            additive = run_skillguard("review-checker-change", "--baseline", rel(additive_baseline_path))

            self.assert_clean_pass(additive)
            compatible_classes = {item.get("change_class") for item in additive.get("safe_additions", [])}
            self.assertIn("additive_command", compatible_classes)
            self.assertIn("additive_route", compatible_classes)
            self.assertTrue(
                any(item.get("checker") == "review-checker-change" for item in additive.get("safe_additions", []))
            )

    def test_review_checker_change_blocks_removed_weakened_renamed_schema_and_fixture_changes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="review-checker-change-", dir=REPO_ROOT) as tmp:
            workspace = Path(tmp)
            manifest_path = workspace / "fixture-manifest.json"
            write_json(
                manifest_path,
                {
                    "schema_version": "skillguard.fixture_manifest.v1",
                    "fixtures": [{"fixture_id": "checker-change-case", "target_command": "self-check", "expected_decision": "pass"}],
                },
            )
            original_manifest_hash = sha256(manifest_path)
            command_surface = checker_engine.current_checker_command_surface()
            for item in command_surface:
                if item["name"] == "check-skill":
                    item["required_checks"] = item["required_checks"] + ["check-skill:must-not-ignore-failing-checks"]
                if item["name"] == "commands":
                    item["output_schema"] = "skillguard.old_command_result.v0"
            command_surface.extend(
                [
                    {
                        "name": "removed-checker",
                        "dispatch_function": "checker_engine.removed_checker",
                        "summary": "Removed checker in synthetic baseline.",
                        "required_checks": ["removed-checker:hard-gate"],
                        "output_schema": "skillguard.cli_result.v1",
                    },
                    {
                        "name": "old-review-checker-change",
                        "dispatch_function": "checker_engine.review_checker_change",
                        "summary": "Old checker name in synthetic baseline.",
                        "required_checks": checker_engine.checker_command_required_checks("review-checker-change"),
                        "output_schema": checker_engine.REVIEW_CHECKER_CHANGE_RESULT_SCHEMA,
                    },
                ]
            )
            baseline_path = workspace / "baseline.json"
            write_json(
                baseline_path,
                checker_change_baseline(
                    command_surface=command_surface,
                    fixture_manifests=[
                        {
                            "path": rel(manifest_path),
                            "sha256": original_manifest_hash,
                            "fixture_ids": ["checker-change-case"],
                        }
                    ],
                ),
            )
            write_json(
                manifest_path,
                {
                    "schema_version": "skillguard.fixture_manifest.v1",
                    "fixtures": [
                        {
                            "fixture_id": "checker-change-case-renamed",
                            "target_command": "self-check",
                            "expected_decision": "block",
                        }
                    ],
                },
            )

            report = run_skillguard(
                "review-checker-change",
                "--baseline",
                rel(baseline_path),
                "--fixture-manifest",
                rel(manifest_path),
                expected_exit=1,
            )

            codes = checker_change_blocker_codes(report)
            self.assertEqual(report.get("decision"), "block")
            self.assertIn("checker_command_removed", codes)
            self.assertIn("checker_required_check_removed", codes)
            self.assertIn("checker_command_renamed", codes)
            self.assertIn("checker_output_schema_changed", codes)
            self.assertIn("fixture_expectation_changed", codes)
            for blocker in report.get("checker_change_blockers", []):
                self.assertTrue(blocker.get("changed_checker"))
                self.assertTrue(blocker.get("old_binding"))
                self.assertTrue(blocker.get("new_binding"))
                self.assertTrue(blocker.get("impact_class"))
                self.assertTrue(blocker.get("affected_evidence_kinds"))
                self.assertTrue(blocker.get("required_revalidation"))
                self.assertTrue(blocker.get("recommended_repair_action"))

    def test_review_checker_change_blocks_missing_baseline_stale_evidence_and_stays_public_safe_read_only(self) -> None:
        with tempfile.TemporaryDirectory(prefix="review-checker-change-", dir=REPO_ROOT) as tmp:
            workspace = Path(tmp)
            missing = run_skillguard("review-checker-change", expected_exit=1)
            self.assertIn("missing_baseline_metadata", checker_change_blocker_codes(missing))

            source_path = workspace / "source.txt"
            source_path.write_text("original\n", encoding="utf-8")
            evidence_path = workspace / "evidence.json"
            write_json(evidence_path, freshness_record_for(source_path))
            baseline_path = workspace / "baseline.json"
            write_json(
                baseline_path,
                checker_change_baseline(
                    evidence_records=[{"path": rel(evidence_path), "sha256": sha256(evidence_path)}],
                    private_payload="PRIVATE_ROUTE_BODY_TEXT_DO_NOT_ECHO",
                ),
            )
            baseline_before = sha256(baseline_path)
            evidence_before = sha256(evidence_path)
            source_path.write_text("changed\n", encoding="utf-8")

            report = run_skillguard(
                "review-checker-change",
                "--baseline",
                rel(baseline_path),
                "--evidence",
                rel(evidence_path),
                expected_exit=1,
            )

            self.assertEqual(sha256(baseline_path), baseline_before)
            self.assertEqual(sha256(evidence_path), evidence_before)
            output_text = json.dumps(report, sort_keys=True)
            self.assertNotIn("PRIVATE_ROUTE_BODY_TEXT_DO_NOT_ECHO", output_text)
            codes = checker_change_blocker_codes(report)
            self.assertIn("stale_evidence_after_checker_change", codes)
            self.assertEqual(report.get("mutation_check", {}).get("mutated_input_paths"), [])
            for blocker in report.get("checker_change_blockers", []):
                self.assertNotIn("private_payload", json.dumps(blocker, sort_keys=True))

    def test_review_checker_change_command_dispatch_route_and_self_check(self) -> None:
        commands = run_skillguard("commands")
        self.assert_clean_pass(commands)
        names = {item.get("name") for item in commands.get("commands", [])}
        self.assertIn("review-checker-change", names)

        route = run_skillguard("route-task", "--task", "Review checker change against current baseline metadata")
        self.assert_clean_pass(route)
        self.assertEqual(route.get("routing_decision", {}).get("command_family"), "review-checker-change")
        self.assertEqual(route.get("routing_decision", {}).get("responsibility"), "reviewer")

        self_check = run_skillguard("self-check", "--target", ".agents/skills/skillguard")
        self.assert_clean_pass(self_check)

    def test_checker_change_suite_guard_passes_and_projects_registry_for_route_and_generators(self) -> None:
        with tempfile.TemporaryDirectory(prefix="checker-change-guard-", dir=REPO_ROOT / ".agents" / "skills") as tmp:
            workspace = Path(tmp)
            source_path = workspace / "review-source.txt"
            source_path.write_text("current checker-change review source\n", encoding="utf-8")
            review_path = workspace / "review-current.json"
            write_json(review_path, checker_change_review_report_for(source_path))

            target = workspace / "guarded-skill"
            idea_path = workspace / "guarded-skill-idea.json"
            plan_path = workspace / "guarded-skill-blueprint.json"
            write_json(idea_path, valid_skill_idea(rel(target), skill_name=target.name))
            write_json(plan_path, run_skillguard("plan-skill", "--input", rel(idea_path)))

            report = run_skillguard(
                "generate-skill",
                "--input",
                rel(plan_path),
                "--checker-suite",
                "generate-skill",
                "--checker-suite-impact",
                "checker_change",
                "--checker-change-review",
                rel(review_path),
            )

            self.assert_clean_pass(report)
            guard = report.get("checker_change_suite_guard", {})
            self.assertEqual(guard.get("state"), "fresh")
            self.assertTrue(guard.get("current_evidence_can_pass"))
            self.assertEqual(guard.get("selected_suites"), ["generate-skill"])
            registry = self.assert_validation_registry(report, "generate-skill", "pass")
            self.assertIn("checker_change_suite_guard", registry.get("source_of_truth_for", []))
            self.assertIn("generate-skill:checker-change-suite-guard", self.validation_registry_ids(registry))
            self.assertTrue(
                any(
                    item.get("kind") == "checker_change_suite_guard"
                    for item in registry.get("evidence", [])
                    if isinstance(item, dict)
                )
            )

            suite_target = workspace / "guarded-suite"
            suite_blueprint_path = workspace / "guarded-suite-blueprint.json"
            route_input_path = workspace / "guarded-suite-route.json"
            write_json(suite_blueprint_path, valid_suite_blueprint(rel(suite_target), suite_target.name))
            write_json(
                route_input_path,
                {
                    "task": "Create a draft suite scaffold from a Suite Blueprint",
                    "route_hint": "generate-suite",
                    "input_path": rel(suite_blueprint_path),
                    "checker_change_review_path": rel(review_path),
                    "checker_suite": "generate-suite",
                    "checker_suite_impact": "suite_change",
                },
            )

            routed = run_skillguard("route-task", "--input", rel(route_input_path))

            self.assert_clean_pass(routed)
            self.assertEqual(routed.get("command"), "generate-suite")
            self.assertEqual(routed.get("checker_change_suite_guard", {}).get("state"), "fresh")
            route_registry = self.assert_validation_registry(routed, "generate-suite", "pass")
            self.assertIn("checker_change_suite_guard", route_registry.get("source_of_truth_for", []))

    def test_checker_change_suite_guard_blocks_missing_stale_and_invalid_states(self) -> None:
        with tempfile.TemporaryDirectory(prefix="checker-change-guard-", dir=REPO_ROOT / ".agents" / "skills") as tmp:
            workspace = Path(tmp)

            def write_plan(name: str) -> Path:
                target = workspace / name
                idea_path = workspace / f"{name}-idea.json"
                plan_path = workspace / f"{name}-blueprint.json"
                write_json(idea_path, valid_skill_idea(rel(target), skill_name=target.name))
                write_json(plan_path, run_skillguard("plan-skill", "--input", rel(idea_path)))
                return plan_path

            current_source = workspace / "current-review-source.txt"
            current_source.write_text("current review source\n", encoding="utf-8")
            current_review = workspace / "current-review.json"
            write_json(current_review, checker_change_review_report_for(current_source))

            missing = run_skillguard(
                "generate-skill",
                "--input",
                rel(write_plan("missing-guard-skill")),
                "--checker-suite-required",
                "--checker-suite-impact",
                "checker_change",
                expected_exit=1,
            )
            missing_codes = checker_change_suite_guard_codes(missing)
            self.assertIn("empty_checker_suite_selection", missing_codes)
            self.assertIn("missing_checker_change_review_evidence", missing_codes)

            invalid = run_skillguard(
                "generate-skill",
                "--input",
                rel(write_plan("invalid-selection-skill")),
                "--checker-suite",
                "bad/suite",
                "--checker-suite-impact",
                "checker_change",
                "--checker-change-review",
                rel(current_review),
                expected_exit=1,
            )
            self.assertIn("invalid_checker_suite_selection", checker_change_suite_guard_codes(invalid))
            self.assertEqual(invalid.get("checker_change_suite_guard", {}).get("state"), "invalid_selection")

            stale_source = workspace / "stale-review-source.txt"
            stale_source.write_text("before\n", encoding="utf-8")
            stale_review = workspace / "stale-review.json"
            write_json(stale_review, checker_change_review_report_for(stale_source))
            stale_source.write_text("after\n", encoding="utf-8")

            stale = run_skillguard(
                "generate-skill",
                "--input",
                rel(write_plan("stale-guard-skill")),
                "--checker-suite",
                "generate-skill",
                "--checker-suite-impact",
                "checker_change",
                "--checker-change-review",
                rel(stale_review),
                expected_exit=1,
            )
            self.assertIn("stale_checker_change_review_evidence", checker_change_suite_guard_codes(stale))
            self.assertEqual(stale.get("checker_change_suite_guard", {}).get("state"), "stale_or_missing")

    def test_generate_skill_creates_expected_scaffold_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory(prefix="generated-skill-", dir=REPO_ROOT / ".agents" / "skills") as tmp:
            workspace = Path(tmp)
            target = workspace / "generated-review-helper"
            idea_path = workspace / "idea.json"
            plan_path = workspace / "blueprint.json"
            write_json(idea_path, valid_skill_idea(rel(target), skill_name=target.name))
            plan_report = run_skillguard("plan-skill", "--input", rel(idea_path))
            write_json(plan_path, plan_report)

            report = run_skillguard("generate-skill", "--input", rel(plan_path))
            report_path = workspace / "generate-output.json"
            write_json(report_path, report)

            self.assert_clean_pass(report)
            self.assertEqual(report.get("maintenance_record", {}).get("schema_version"), checker_engine.MAINTENANCE_RECORD_SCHEMA_VERSION)
            required_files = {
                "SKILL.md",
                "README.md",
                "references/README.md",
                "assets/schemas/generated_record.schema.json",
                "assets/templates/check_report.template.json",
                "scripts/README.md",
                "scripts/run_checks.py",
                "fixtures/README.md",
                "fixtures/fixture-manifest.json",
                "tests/README.md",
                "tests/test_smoke.py",
                ".skillguard/flowguard_contract_model.py",
                ".skillguard/contract-source.json",
                ".skillguard/compiled-contract.json",
                ".skillguard/check-manifest.json",
            }
            for relative in required_files:
                self.assertTrue((target / relative).is_file(), relative)
                text = (target / relative).read_text(encoding="utf-8")
                for pattern in PRIVATE_OR_SECRET_PATTERNS:
                    self.assertIsNone(pattern.search(text), f"{relative}: {pattern.pattern}")
                for pattern in UNSAFE_CLAIM_PATTERNS:
                    self.assertIsNone(pattern.search(text), f"{relative}: {pattern.pattern}")
            generated_entrypoint = (target / "SKILL.md").read_text(encoding="utf-8")
            current_template = (
                SCRIPT_DIR.parent / "assets" / "templates" / "target_SKILL.md.template"
            ).read_text(encoding="utf-8")
            for text in (generated_entrypoint, current_template):
                self.assertNotIn("v1-legacy", text)
                self.assertNotIn(".skillguard/work-contract.json", text)
                self.assertNotIn(".skillguard/check_manifest.json", text)
            self.assertIn("private graduation evidence", generated_entrypoint)
            self.assertNotIn(".skillguard/", current_template)
            self.assertNotIn("SkillGuard", current_template)
            self.assertEqual(
                json.loads((target / ".skillguard" / "contract-source.json").read_text(encoding="utf-8"))[
                    "schema_version"
                ],
                "skillguard.contract_source.v2",
            )
            self.assertEqual(
                json.loads((target / ".skillguard" / "compiled-contract.json").read_text(encoding="utf-8"))[
                    "schema_version"
                ],
                "skillguard.compiled_contract.v2",
            )
            self.assertEqual(set(report.get("missing_after_write", [])), set())
            post_checks = report.get("post_generation_checks", [])
            self.assertEqual(
                [(item.get("command"), item.get("artifact_path"), item.get("status")) for item in post_checks],
                [
                    ("check-skill", rel(target), "pass"),
                    ("check-contract", rel(target / ".skillguard" / "contract-source.json"), "pass"),
                ],
            )

            maintenance = run_skillguard("check-maintenance-record", "--input", rel(report_path))
            self.assert_clean_pass(maintenance)
            self.assertEqual(maintenance.get("record_shape"), "current_nested")

            stale = run_skillguard("detect-stale-evidence", "--input", rel(report_path))
            self.assert_clean_pass(stale)
            self.assertEqual(stale.get("stale_evidence_count"), 0)

            manifest_check = run_skillguard("check-fixture-manifest", "--input", rel(target / "fixtures" / "fixture-manifest.json"))
            self.assert_clean_pass(manifest_check)

            check_report = run_skillguard(
                "check-skill", "--repository-root", ".", "--target", rel(target)
            )
            self.assert_clean_pass(check_report)

            rerun = run_skillguard("generate-skill", "--input", rel(plan_path))
            self.assert_clean_pass(rerun)
            self.assertEqual(rerun.get("created_files"), [])
            self.assertGreaterEqual(len(rerun.get("existing_files", [])), len(required_files))
            self.assertTrue(all(item.get("status") == "pass" for item in rerun.get("post_generation_checks", [])))

            bad_manifest = target / "fixtures" / "fixture-manifest.json"
            write_json(bad_manifest, {"schema_version": "skillguard.fixture_manifest.v1", "fixtures": [1]})
            malformed = run_skillguard("check-fixture-manifest", "--input", rel(bad_manifest), expected_exit=1)
            self.assertEqual(malformed.get("decision"), "fail")
            self.assertTrue(malformed.get("failures"))

            removed = target / "SKILL.md"
            removed.unlink()
            stale_after_remove = run_skillguard("detect-stale-evidence", "--input", rel(report_path), expected_exit=1)
            self.assertEqual(stale_after_remove.get("decision"), "block")
            self.assertIn("stale_generated_artifact_path", stale_blocker_codes(stale_after_remove))

    def test_generate_skill_blocks_conflicts_and_unsafe_target(self) -> None:
        with tempfile.TemporaryDirectory(prefix="generated-skill-", dir=REPO_ROOT / ".agents" / "skills") as tmp:
            workspace = Path(tmp)
            target = workspace / "generated-review-helper"
            idea_path = workspace / "idea.json"
            plan_path = workspace / "blueprint.json"
            write_json(idea_path, valid_skill_idea(rel(target), skill_name=target.name))
            plan_report = run_skillguard("plan-skill", "--input", rel(idea_path))
            write_json(plan_path, plan_report)
            target.mkdir()
            (target / "SKILL.md").write_text("conflicting content\n", encoding="utf-8")

            conflict = run_skillguard("generate-skill", "--input", rel(plan_path), expected_exit=1)

            self.assertEqual(conflict.get("decision"), "block")
            self.assertTrue(any("different content" in blocker for blocker in conflict.get("blockers", [])))
            self.assertTrue(
                any(
                    item.get("conflict_kind") == "existing_file_content_mismatch"
                    and item.get("conflicting_path") == rel(target / "SKILL.md")
                    for item in conflict.get("write_preflight_conflicts", [])
                )
            )
            self.assertFalse((target / ".skillguard").exists())

            unsafe_path = workspace / "unsafe-blueprint.json"
            unsafe_report = dict(plan_report)
            unsafe_blueprint = dict(plan_report["skill_blueprint"])
            unsafe_blueprint["target"] = "../outside-skill"
            unsafe_blueprint["skill"] = dict(unsafe_blueprint["skill"])
            unsafe_blueprint["skill"]["target_path"] = "../outside-skill"
            unsafe_report["skill_blueprint"] = unsafe_blueprint
            write_json(unsafe_path, unsafe_report)
            unsafe = run_skillguard("generate-skill", "--input", rel(unsafe_path), expected_exit=1)
            self.assertEqual(unsafe.get("decision"), "block")
            self.assertTrue(any("repository root" in blocker for blocker in unsafe.get("blockers", [])))

    def test_generate_skill_blocks_required_directory_file_conflicts_before_writing(self) -> None:
        required_directories = (
            ".skillguard",
            "assets/schemas",
            "assets/templates",
            "fixtures",
            "references",
            "scripts",
            "tests",
        )
        for required_directory in required_directories:
            with self.subTest(required_directory=required_directory):
                with tempfile.TemporaryDirectory(prefix="generated-skill-", dir=REPO_ROOT / ".agents" / "skills") as tmp:
                    workspace = Path(tmp)
                    target = workspace / "generated-review-helper"
                    idea_path = workspace / "idea.json"
                    plan_path = workspace / "blueprint.json"
                    write_json(idea_path, valid_skill_idea(rel(target), skill_name=target.name))
                    plan_report = run_skillguard("plan-skill", "--input", rel(idea_path))
                    write_json(plan_path, plan_report)

                    conflict_path = target / Path(*required_directory.split("/"))
                    conflict_path.parent.mkdir(parents=True, exist_ok=True)
                    conflict_path.write_text("directory conflict\n", encoding="utf-8")

                    conflict = run_skillguard("generate-skill", "--input", rel(plan_path), expected_exit=1)

                    conflict_relative = rel(conflict_path)
                    self.assertEqual(conflict.get("decision"), "block")
                    self.assertTrue(
                        any(
                            "required scaffold directory conflict" in blocker and conflict_relative in blocker
                            for blocker in conflict.get("blockers", [])
                        )
                    )
                    structured_conflicts = conflict.get("write_preflight_conflicts", [])
                    self.assertTrue(
                        any(
                            item.get("conflicting_path") == conflict_relative
                            and item.get("expected_directory_role")
                            and item.get("safe_remediation_path") == conflict_relative
                            for item in structured_conflicts
                        ),
                        structured_conflicts,
                    )
                    self.assertEqual(conflict.get("planned_created_files"), [])
                    self.assertNotIn("created_files", conflict)
                    for generated_file in (
                        "SKILL.md",
                        "README.md",
                        "references/README.md",
                        "assets/schemas/generated_record.schema.json",
                        "assets/templates/check_report.template.json",
                        "scripts/run_checks.py",
                        "fixtures/fixture-manifest.json",
                        "tests/test_smoke.py",
                        ".skillguard/contract-source.json",
                    ):
                        self.assertFalse((target / Path(*generated_file.split("/"))).is_file(), generated_file)

    def test_generate_skill_blocks_unowned_existing_target_without_writing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="generated-skill-", dir=REPO_ROOT / ".agents" / "skills") as tmp:
            workspace = Path(tmp)
            target = workspace / "generated-review-helper"
            idea_path = workspace / "idea.json"
            plan_path = workspace / "blueprint.json"
            write_json(idea_path, valid_skill_idea(rel(target), skill_name=target.name))
            plan_report = run_skillguard("plan-skill", "--input", rel(idea_path))
            write_json(plan_path, plan_report)
            target.mkdir()
            user_note = target / "notes.md"
            user_note.write_text("user-owned note\n", encoding="utf-8")

            conflict = run_skillguard("generate-skill", "--input", rel(plan_path), expected_exit=1)

            self.assertEqual(conflict.get("decision"), "block")
            self.assertEqual(conflict.get("planned_created_files"), [])
            self.assertNotIn("created_files", conflict)
            self.assertTrue(user_note.is_file())
            self.assertFalse((target / "SKILL.md").exists())
            self.assertFalse((target / ".skillguard").exists())
            self.assertTrue(
                any(
                    item.get("conflict_kind") == "unexpected_existing_file"
                    and item.get("conflicting_path") == rel(user_note)
                    and item.get("safe_remediation_path") == rel(user_note)
                    for item in conflict.get("write_preflight_conflicts", [])
                ),
                conflict.get("write_preflight_conflicts", []),
            )

    def test_generate_skill_blocks_partial_generated_tree_before_writing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="generated-skill-", dir=REPO_ROOT / ".agents" / "skills") as tmp:
            workspace = Path(tmp)
            target = workspace / "generated-review-helper"
            idea_path = workspace / "idea.json"
            plan_path = workspace / "blueprint.json"
            write_json(idea_path, valid_skill_idea(rel(target), skill_name=target.name))
            plan_report = run_skillguard("plan-skill", "--input", rel(idea_path))
            write_json(plan_path, plan_report)
            first = run_skillguard("generate-skill", "--input", rel(plan_path))
            self.assert_clean_pass(first)

            removed = target / "references" / "README.md"
            removed.unlink()
            conflict = run_skillguard("generate-skill", "--input", rel(plan_path), expected_exit=1)

            self.assertEqual(conflict.get("decision"), "block")
            self.assertEqual(conflict.get("planned_created_files"), [])
            self.assertNotIn("created_files", conflict)
            self.assertFalse(removed.exists())
            self.assertTrue(
                any(
                    item.get("conflict_kind") == "incomplete_generated_ownership"
                    and item.get("conflicting_path") == rel(target)
                    for item in conflict.get("write_preflight_conflicts", [])
                ),
                conflict.get("write_preflight_conflicts", []),
            )

    def test_generate_skill_fails_when_post_generation_check_fails(self) -> None:
        with tempfile.TemporaryDirectory(prefix="generated-skill-", dir=REPO_ROOT / ".agents" / "skills") as tmp:
            workspace = Path(tmp)
            target = workspace / "generated-review-helper"
            idea_path = workspace / "idea.json"
            plan_path = workspace / "blueprint.json"
            idea = valid_skill_idea(rel(target), skill_name=target.name)
            idea["description"] = "Use when a maintainer asks for tests passed evidence without a current review."
            write_json(idea_path, idea)
            plan_report = run_skillguard("plan-skill", "--input", rel(idea_path))
            write_json(plan_path, plan_report)

            report = run_skillguard("generate-skill", "--input", rel(plan_path), expected_exit=1)

            self.assertEqual(report.get("decision"), "fail")
            self.assertTrue((target / "SKILL.md").is_file())
            self.assertTrue(
                any(
                    item.get("command") == "check-skill"
                    and item.get("artifact_path") == rel(target)
                    and item.get("status") == "fail"
                    and item.get("reported_decision") == "fail"
                    for item in report.get("post_generation_checks", [])
                ),
                report.get("post_generation_checks", []),
            )
            self.assertTrue(any("post-generation check" in failure for failure in report.get("failures", [])))
            self.assertNotEqual(report.get("decision"), "pass")

    def test_post_generation_check_reports_missing_artifact_blocker(self) -> None:
        with tempfile.TemporaryDirectory(prefix="generated-skill-", dir=REPO_ROOT / ".agents" / "skills") as tmp:
            missing_target = Path(tmp) / "missing-generated-skill"
            check = checker_engine.build_post_generation_check_result(
                check_id="test:missing-generated-artifact",
                command_name="check-skill",
                argv=["--repository-root", ".", "--target", rel(missing_target)],
                artifact_path=rel(missing_target),
            )

            self.assertEqual(check.get("status"), "block")
            self.assertEqual(check.get("reported_decision"), "block")
            self.assertEqual(check.get("artifact_path"), rel(missing_target))
            self.assertTrue(any("does not exist" in item for item in check.get("reported_blockers", [])))

    def test_generate_skill_blocks_invalid_blueprint_shape(self) -> None:
        with tempfile.TemporaryDirectory(prefix="generated-skill-", dir=REPO_ROOT / ".agents" / "skills") as tmp:
            target = Path(tmp)
            invalid_path = target / "invalid.json"
            write_json(invalid_path, {"schema_version": "skillguard.skill_blueprint.v2", "target": rel(target)})

            report = run_skillguard("generate-skill", "--input", rel(invalid_path), expected_exit=1)

            self.assertEqual(report.get("decision"), "block")
            self.assertTrue(any("missing required field" in blocker for blocker in report.get("blockers", [])))
            self.assertFalse((target / ".skillguard").exists())

    def test_generate_suite_creates_suite_child_records_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gs-", dir=REPO_ROOT / ".agents" / "skills") as tmp:
            workspace = Path(tmp)
            target = workspace / "generated-review-suite"
            blueprint_path = workspace / "suite-blueprint.json"
            write_json(blueprint_path, valid_suite_blueprint(rel(target), target.name))

            report = run_skillguard("generate-suite", "--input", rel(blueprint_path))

            self.assert_clean_pass(report)
            suite_root = target / ".skillguard" / "suite"
            member_root = target / "members"
            required_files = {
                "README.md",
                ".skillguard/suite/suite-map.json",
                ".skillguard/suite/suite-contract.json",
                ".skillguard/suite/evidence/source_blueprint_trace.json",
                ".skillguard/suite/evidence/suite_closure.json",
                ".skillguard/suite/evidence/suite-alpha_check_report.json",
                ".skillguard/suite/evidence/suite-beta_check_report.json",
                ".skillguard/suite/reports/suite_generation_report.json",
                "members/suite-alpha/SKILL.md",
                "members/suite-alpha/.skillguard/contract-source.json",
                "members/suite-beta/SKILL.md",
                "members/suite-beta/.skillguard/contract-source.json",
            }
            for relative in required_files:
                path = target / Path(*relative.split("/"))
                self.assertTrue(path.is_file(), relative)
                text = path.read_text(encoding="utf-8")
                for pattern in PRIVATE_OR_SECRET_PATTERNS:
                    self.assertIsNone(pattern.search(text), f"{relative}: {pattern.pattern}")
                for pattern in UNSAFE_CLAIM_PATTERNS:
                    self.assertIsNone(pattern.search(text), f"{relative}: {pattern.pattern}")
            self.assertEqual(set(report.get("missing_after_write", [])), set())
            self.assertEqual(set(report.get("child_skill_paths", [])), {rel(member_root / "suite-alpha"), rel(member_root / "suite-beta")})
            post_checks = report.get("post_generation_checks", [])
            self.assertTrue(all(item.get("status") == "pass" for item in post_checks), post_checks)
            self.assertEqual(
                {(item.get("command"), item.get("artifact_path")) for item in post_checks},
                {
                    ("check-suite", rel(suite_root)),
                    ("check-skill", rel(member_root / "suite-alpha")),
                    ("check-skill", rel(member_root / "suite-beta")),
                },
            )

            suite_check = run_skillguard(
                "check-suite",
                "--suite-root",
                rel(suite_root),
                "--suite-map",
                rel(suite_root / "suite-map.json"),
                "--suite-contract",
                rel(suite_root / "suite-contract.json"),
                "--member-root",
                rel(member_root),
            )
            self.assert_clean_pass(suite_check)
            for child in ("suite-alpha", "suite-beta"):
                child_check = run_skillguard(
                    "check-skill",
                    "--repository-root",
                    ".",
                    "--target",
                    rel(member_root / child),
                )
                self.assert_clean_pass(child_check)

            rerun = run_skillguard("generate-suite", "--input", rel(blueprint_path))
            self.assert_clean_pass(rerun)
            self.assertEqual(rerun.get("created_files"), [])
            self.assertGreaterEqual(len(rerun.get("existing_files", [])), len(required_files))
            self.assertTrue(all(item.get("status") == "pass" for item in rerun.get("post_generation_checks", [])))

    def test_generate_suite_honors_declared_nested_member_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gs-", dir=REPO_ROOT / ".agents" / "skills") as tmp:
            workspace = Path(tmp)
            target = workspace / "generated-review-suite"
            member_root = target / "members"
            nested_child = member_root / "nested" / "suite-alpha"
            blueprint_path = workspace / "suite-blueprint.json"
            blueprint = valid_suite_blueprint(rel(target), target.name, members=["suite-alpha"])
            blueprint["member_skills"][0]["path"] = rel(nested_child)
            write_json(blueprint_path, blueprint)

            report = run_skillguard("generate-suite", "--input", rel(blueprint_path))

            self.assert_clean_pass(report)
            self.assertEqual(report.get("child_skill_paths"), [rel(nested_child)])
            self.assertTrue(
                any(
                    item.get("command") == "check-skill"
                    and item.get("artifact_path") == rel(nested_child)
                    and item.get("status") == "pass"
                    for item in report.get("post_generation_checks", [])
                ),
                report.get("post_generation_checks", []),
            )
            self.assertTrue((nested_child / "SKILL.md").is_file())
            self.assertTrue((nested_child / ".skillguard" / "contract-source.json").is_file())
            self.assertFalse((member_root / "suite-alpha" / "SKILL.md").exists())

            suite_root = target / ".skillguard" / "suite"
            suite_map = json.loads((suite_root / "suite-map.json").read_text(encoding="utf-8"))
            suite_contract = json.loads((suite_root / "suite-contract.json").read_text(encoding="utf-8"))
            self.assertEqual(suite_map["included_skills"][0]["path"], rel(nested_child))
            self.assertEqual(suite_contract["included_skills"][0]["path"], rel(nested_child))
            self.assertEqual(
                json.loads((suite_root / "evidence" / "suite-alpha_check_report.json").read_text(encoding="utf-8"))["target_path"],
                rel(nested_child),
            )

            suite_check = run_skillguard(
                "check-suite",
                "--suite-root",
                rel(suite_root),
                "--suite-map",
                rel(suite_root / "suite-map.json"),
                "--suite-contract",
                rel(suite_root / "suite-contract.json"),
                "--member-root",
                rel(member_root),
            )
            self.assert_clean_pass(suite_check)
            child_check = run_skillguard(
                "check-skill", "--repository-root", ".", "--target", rel(nested_child)
            )
            self.assert_clean_pass(child_check)

    def test_generate_suite_blocks_unowned_nested_member_path_without_writing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gs-", dir=REPO_ROOT / ".agents" / "skills") as tmp:
            workspace = Path(tmp)
            target = workspace / "generated-review-suite"
            member_root = target / "members"
            nested_child = member_root / "nested" / "suite-alpha"
            blueprint_path = workspace / "suite-blueprint.json"
            blueprint = valid_suite_blueprint(rel(target), target.name, members=["suite-alpha"])
            blueprint["member_skills"][0]["path"] = rel(nested_child)
            write_json(blueprint_path, blueprint)
            nested_child.mkdir(parents=True)
            user_note = nested_child / "notes.md"
            user_note.write_text("user-owned nested member note\n", encoding="utf-8")

            conflict = run_skillguard("generate-suite", "--input", rel(blueprint_path), expected_exit=1)

            self.assertEqual(conflict.get("decision"), "block")
            self.assertEqual(conflict.get("planned_created_files"), [])
            self.assertNotIn("created_files", conflict)
            self.assertTrue(user_note.is_file())
            self.assertFalse((target / "README.md").exists())
            self.assertFalse((nested_child / "SKILL.md").exists())
            self.assertTrue(
                any(
                    item.get("conflict_kind") == "unexpected_existing_file"
                    and item.get("conflicting_path") == rel(user_note)
                    and item.get("safe_remediation_path") == rel(user_note)
                    for item in conflict.get("write_preflight_conflicts", [])
                ),
                conflict.get("write_preflight_conflicts", []),
            )

    def test_generate_suite_fails_when_child_post_generation_check_fails(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gs-", dir=REPO_ROOT / ".agents" / "skills") as tmp:
            workspace = Path(tmp)
            target = workspace / "generated-review-suite"
            member_root = target / "members"
            child = member_root / "suite-alpha"
            blueprint_path = workspace / "suite-blueprint.json"
            blueprint = valid_suite_blueprint(rel(target), target.name, members=["suite-alpha"])
            blueprint["member_skills"][0]["description"] = (
                "Use when maintainers ask for tests passed evidence without current child review."
            )
            write_json(blueprint_path, blueprint)

            report = run_skillguard("generate-suite", "--input", rel(blueprint_path), expected_exit=1)

            self.assertEqual(report.get("decision"), "fail")
            self.assertTrue((target / "README.md").is_file())
            self.assertTrue((child / "SKILL.md").is_file())
            post_checks = report.get("post_generation_checks", [])
            self.assertTrue(
                any(
                    item.get("command") == "check-skill"
                    and item.get("artifact_path") == rel(child)
                    and item.get("status") == "fail"
                    for item in post_checks
                ),
                post_checks,
            )
            self.assertTrue(any("post-generation check" in failure for failure in report.get("failures", [])))
            self.assertNotEqual(report.get("decision"), "pass")

    def test_generate_suite_blocks_conflicts_and_unsafe_or_invalid_input(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gs-", dir=REPO_ROOT / ".agents" / "skills") as tmp:
            workspace = Path(tmp)
            target = workspace / "generated-review-suite"
            blueprint_path = workspace / "suite-blueprint.json"
            write_json(blueprint_path, valid_suite_blueprint(rel(target), target.name))
            (target / ".skillguard" / "suite").mkdir(parents=True)
            (target / ".skillguard" / "suite" / "suite-map.json").write_text("conflicting content\n", encoding="utf-8")

            conflict = run_skillguard("generate-suite", "--input", rel(blueprint_path), expected_exit=1)

            self.assertEqual(conflict.get("decision"), "block")
            self.assertTrue(any("different content" in blocker for blocker in conflict.get("blockers", [])))
            self.assertFalse((target / "members" / "suite-alpha" / "SKILL.md").exists())

            unsafe_path = workspace / "unsafe-suite.json"
            unsafe = valid_suite_blueprint(rel(workspace / "unsafe-suite"), "unsafe-suite")
            unsafe["target"] = "../outside-suite"
            unsafe["safe_edit_scope"] = {"target_file_writes_allowed": True, "allowed_write_paths": ["../outside-suite"]}
            write_json(unsafe_path, unsafe)
            unsafe_report = run_skillguard("generate-suite", "--input", rel(unsafe_path), expected_exit=1)
            self.assertEqual(unsafe_report.get("decision"), "block")
            self.assertTrue(any("repository root" in blocker for blocker in unsafe_report.get("blockers", [])))

            invalid_path = workspace / "invalid-suite.json"
            invalid = valid_suite_blueprint(rel(workspace / "invalid-suite"), "invalid-suite")
            invalid.pop("member_skills")
            write_json(invalid_path, invalid)
            invalid_report = run_skillguard("generate-suite", "--input", rel(invalid_path), expected_exit=1)
            self.assertEqual(invalid_report.get("decision"), "block")
            self.assertTrue(any("member_skills" in blocker for blocker in invalid_report.get("blockers", [])))

    def test_generate_suite_blocks_required_directory_file_conflicts_before_writing(self) -> None:
        conflict_paths = (".skillguard/suite", "members/suite-alpha/references")
        for conflict_relative in conflict_paths:
            with self.subTest(conflict_relative=conflict_relative):
                with tempfile.TemporaryDirectory(prefix="gs-", dir=REPO_ROOT / ".agents" / "skills") as tmp:
                    workspace = Path(tmp)
                    target = workspace / "generated-review-suite"
                    blueprint_path = workspace / "suite-blueprint.json"
                    write_json(blueprint_path, valid_suite_blueprint(rel(target), target.name, members=["suite-alpha"]))
                    conflict_path = target / Path(*conflict_relative.split("/"))
                    conflict_path.parent.mkdir(parents=True, exist_ok=True)
                    conflict_path.write_text("directory conflict\n", encoding="utf-8")

                    conflict = run_skillguard("generate-suite", "--input", rel(blueprint_path), expected_exit=1)

                    path_relative = rel(conflict_path)
                    self.assertEqual(conflict.get("decision"), "block")
                    self.assertTrue(
                        any(
                            "required suite scaffold directory conflict" in blocker and path_relative in blocker
                            for blocker in conflict.get("blockers", [])
                        )
                    )
                    structured_conflicts = conflict.get("write_preflight_conflicts", [])
                    self.assertTrue(
                        any(
                            item.get("conflicting_path") == path_relative
                            and item.get("expected_directory_role")
                            and item.get("safe_remediation_path") == path_relative
                            for item in structured_conflicts
                        ),
                        structured_conflicts,
                    )
                    self.assertEqual(conflict.get("planned_created_files"), [])
                    self.assertNotIn("created_files", conflict)
                    self.assertFalse((target / "README.md").is_file())
                    self.assertFalse((target / "members" / "suite-alpha" / "SKILL.md").is_file())

    def test_example_document_is_public_safe_and_current(self) -> None:
        self.assertTrue(EXAMPLES.is_file(), f"missing {rel(EXAMPLES)}")
        text = EXAMPLES.read_text(encoding="utf-8")
        for required in (
            "check-skill",
            "check-suite",
            "fixture-test",
            "check-depth",
            "check-readme-release",
            "maintainer-adopt",
            "maintainer-audit",
            "self-check",
            "route-task",
            "plan-skill",
            "generate-skill",
            "generate-suite",
            "detect-stale-evidence",
            "review-checker-change",
            "check-maintenance-record",
            "standard-library",
        ):
            self.assertIn(required, text)
        for pattern in PRIVATE_OR_SECRET_PATTERNS:
            self.assertIsNone(pattern.search(text), pattern.pattern)
        for pattern in UNSAFE_CLAIM_PATTERNS:
            self.assertIsNone(pattern.search(text), pattern.pattern)


def result_payload(result: unittest.TestResult, elapsed_seconds: float) -> dict[str, Any]:
    failure_items = [
        {"test": str(test), "details": details}
        for test, details in list(result.failures) + list(result.errors)
    ]
    decision = "pass" if result.wasSuccessful() else "fail"
    payload = {
        "schema_version": "skillguard.standard_library_test_result.v1",
        "checked_at": utc_timestamp(),
        "command": "python tests/test_skillguard_local.py",
        "decision": decision,
        "test_count": result.testsRun,
        "failure_count": len(result.failures),
        "error_count": len(result.errors),
        "elapsed_seconds": round(elapsed_seconds, 3),
        "checks": [
            {
                "check_id": "standard-library-local-examples",
                "name": "Local examples and checker command smoke checks",
                "required": True,
                "status": decision,
                "summary": "Ran standard-library unittest checks for single-skill, suite, fixture manifests, self-check, and public-safe example wording.",
            }
        ],
        "evidence": [
            {
                "evidence_id": "standard-library-unittest",
                "kind": "command_output",
                "fresh": True,
                "summary": f"Ran {result.testsRun} unittest checks using the local Python interpreter.",
                "source_path": "tests/test_skillguard_local.py",
            },
            {
                "evidence_id": "examples-readme",
                "kind": "file_inspection",
                "fresh": True,
                "summary": "Checked examples/README.md for local command names and public-safe wording.",
                "source_path": "examples/README.md",
            },
        ],
        "failures": failure_items,
        "blockers": [],
        "skipped_checks": [],
        "residual_risk": [
            "These are local standard-library smoke checks, not packaged CLI, network, release, suite automation, or code-contract checks."
        ],
        "claim_boundary": (
            "This test result covers only the local examples and explicit SkillGuard command invocations run by this script. "
            "It does not prove broad fixture coverage, packaged CLI installation, suite automation, package publication, "
            "release readiness, code-contract validation, external services, or future AI behavior."
        ),
    }
    payload["maintenance_record_schema_version"] = checker_engine.MAINTENANCE_RECORD_SCHEMA_VERSION
    payload["maintenance_record"] = checker_engine.build_maintenance_record(
        record_kind="workflow_evidence",
        artifact_id="tests/test_skillguard_local.py",
        route_node_id="standard-library-tests",
        checker_name="check-maintenance-record",
        status=decision,
        blockers=failure_items,
        evidence_timestamp=payload["checked_at"],
        owner_action={"action": "not_applicable", "status": "test_result"},
        content_seed={"test_count": result.testsRun, "failure_count": len(result.failures), "error_count": len(result.errors)},
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run local standard-library SkillGuard checks.")
    parser.add_argument("--json-output", help="Optional JSON report output path under the repository root.")
    args = parser.parse_args(argv)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SkillGuardLocalExamplesTest)
    stream = io.StringIO()
    started = time.perf_counter()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    elapsed = time.perf_counter() - started
    sys.stdout.write(stream.getvalue())

    payload = result_payload(result, elapsed)
    if args.json_output:
        output = (REPO_ROOT / args.json_output).resolve()
        output.relative_to(REPO_ROOT.resolve())
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
