from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / ".agents" / "skills" / "skillguard" / "scripts"
import sys

if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from skillguard_v2.provenance import (  # noqa: E402
    audit_release_provenance,
    compare_skill_sources,
    normalize_remote_identity,
    project_version,
)


class ProvenanceTests(unittest.TestCase):
    def test_github_remote_identity_normalizes_https_ssh_case_and_git_suffix(self) -> None:
        expected = "github.com/liuyingxuvka/skillguard"
        for remote in (
            "https://github.com/liuyingxuvka/SkillGuard.git",
            "https://github.com/liuyingxuvka/SkillGuard",
            "https://x-access-token@github.com/liuyingxuvka/SkillGuard",
            "git@github.com:liuyingxuvka/SkillGuard.git",
        ):
            self.assertEqual(expected, normalize_remote_identity(remote))

    def test_project_version_parser_has_a_python_310_fallback(self) -> None:
        import skillguard_v2.provenance as provenance

        original = provenance.tomllib
        try:
            provenance.tomllib = None
            self.assertEqual("0.2.0", project_version(ROOT / "pyproject.toml"))
        finally:
            provenance.tomllib = original

    def test_complete_source_manifest_detects_missing_changed_and_unexpected_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canonical = root / "canonical"
            installed = root / "installed"
            canonical.mkdir()
            installed.mkdir()
            canonical.joinpath("same.txt").write_text("same\n", encoding="utf-8")
            canonical.joinpath("changed.txt").write_text("new\n", encoding="utf-8")
            canonical.joinpath("missing.txt").write_text("required\n", encoding="utf-8")
            installed.joinpath("same.txt").write_text("same\n", encoding="utf-8")
            installed.joinpath("changed.txt").write_text("old\n", encoding="utf-8")
            installed.joinpath("unexpected.txt").write_text("stale\n", encoding="utf-8")
            comparison = compare_skill_sources(canonical, installed)
            self.assertEqual(["missing.txt"], comparison["missing_in_installed"])
            self.assertEqual(["changed.txt"], comparison["changed_in_installed"])
            self.assertEqual(["unexpected.txt"], comparison["unexpected_in_installed"])

    def test_repository_audit_uses_tokens_and_can_pass_a_development_identity_check(self) -> None:
        skill = ROOT / ".agents" / "skills" / "skillguard"
        report = audit_release_provenance(
            ROOT,
            skill,
            skill,
            expected_origin="https://github.com/liuyingxuvka/SkillGuard.git",
            release_snapshot={"status": "unavailable"},
            require_clean=False,
            require_installed_parity=True,
            require_release_alignment=False,
        )
        self.assertEqual("passed", report["status"], report["blockers"])
        self.assertEqual("repository_skill_root", report["canonical_source"]["path_token"])
        self.assertEqual("installed_skill_root", report["installed_source"]["path_token"])

    def test_release_and_installed_downgrade_gates_block_independently(self) -> None:
        skill = ROOT / ".agents" / "skills" / "skillguard"
        with tempfile.TemporaryDirectory() as temporary:
            installed = Path(temporary) / "skillguard"
            installed.mkdir()
            installed.joinpath("SKILL.md").write_text("stale\n", encoding="utf-8")
            report = audit_release_provenance(
                ROOT,
                skill,
                installed,
                expected_origin="https://github.com/liuyingxuvka/SkillGuard.git",
                release_snapshot={
                    "status": "available",
                    "tagName": "v0.0.1",
                    "isDraft": False,
                    "isPrerelease": False,
                },
                require_clean=False,
                require_installed_parity=True,
                require_release_alignment=True,
            )
        self.assertIn("installed_source_downgrade_missing_files", report["blockers"])
        self.assertIn("installed_source_downgrade_changed_files", report["blockers"])
        self.assertIn("github_release_version_mismatch", report["blockers"])


if __name__ == "__main__":
    unittest.main()
