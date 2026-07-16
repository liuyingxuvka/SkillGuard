from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock


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
from skillguard_v2.installation import installation_member_paths  # noqa: E402
from tests._runtime_authority_consumer_fixture import (  # noqa: E402
    add_old_flat_run_rejection,
    make_current_skill,
    make_old_lifecycle_rejection_skill,
    make_old_pair_rejection_skill,
)


class ProvenanceTests(unittest.TestCase):
    @staticmethod
    def _copy_installation_projection(source: Path, target: Path) -> None:
        for relative in installation_member_paths(source):
            source_path = source / Path(*relative.split("/"))
            target_path = target / Path(*relative.split("/"))
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)

    def test_github_remote_identity_normalizes_https_ssh_case_and_git_suffix(self) -> None:
        expected = "github.com/liuyingxuvka/skillguard"
        for remote in (
            "https://github.com/liuyingxuvka/SkillGuard.git",
            "https://github.com/liuyingxuvka/SkillGuard",
            "https://x-access-token@github.com/liuyingxuvka/SkillGuard",
            "git@github.com:liuyingxuvka/SkillGuard.git",
        ):
            self.assertEqual(expected, normalize_remote_identity(remote))

    def test_project_version_uses_the_declared_current_python_runtime(self) -> None:
        self.assertEqual("0.3.2", project_version(ROOT / "pyproject.toml"))

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
        with tempfile.TemporaryDirectory() as temporary:
            installed_parent = Path(temporary) / "skills"
            installed = installed_parent / "skillguard"
            self._copy_installation_projection(skill, installed)
            self._copy_installation_projection(
                skill.parent / "skillguard-global-router",
                installed_parent / "skillguard-global-router",
            )
            report = audit_release_provenance(
                ROOT,
                skill,
                installed,
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
        self.assertIn("installed_projection_missing_files", report["blockers"])
        self.assertIn("installed_projection_changed_files", report["blockers"])
        self.assertIn("github_release_version_mismatch", report["blockers"])

    def test_current_provenance_detects_residual_before_runs_are_filtered(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canonical_parent = root / "canonical"
            installed_parent = root / "installed"
            canonical = canonical_parent / "skillguard"
            make_current_skill(canonical, "skillguard")
            make_current_skill(
                canonical_parent / "skillguard-global-router",
                "skillguard-global-router",
            )
            shutil.copytree(canonical_parent, installed_parent)
            installed = installed_parent / "skillguard"

            current = audit_release_provenance(
                ROOT,
                canonical,
                installed,
                expected_origin="https://github.com/liuyingxuvka/SkillGuard.git",
                release_snapshot={"status": "unavailable"},
                require_clean=False,
                require_installed_parity=True,
                require_release_alignment=False,
            )
            self.assertEqual("passed", current["status"], current["blockers"])
            self.assertEqual(
                "current",
                current["runtime_authority"]["installed"]["skillguard"][
                    "authority"
                ],
            )

            add_old_flat_run_rejection(installed)
            blocked = audit_release_provenance(
                ROOT,
                canonical,
                installed,
                expected_origin="https://github.com/liuyingxuvka/SkillGuard.git",
                release_snapshot={"status": "unavailable"},
                require_clean=False,
                require_installed_parity=True,
                require_release_alignment=False,
            )
            self.assertEqual("blocked", blocked["status"])
            self.assertIn("former_runtime_residual", blocked["blockers"])
            comparison = blocked["member_comparisons"]["skillguard"]
            self.assertEqual([], comparison["missing_in_installed"])
            self.assertEqual([], comparison["changed_in_installed"])
            self.assertEqual([], comparison["unexpected_in_installed"])
            self.assertEqual(
                "blocked",
                comparison["installed_runtime_authority"]["authority"],
            )

    def test_provenance_blocks_unconverted_authority_without_fallback(self) -> None:
        for label, builder in (
            ("old-lifecycle", make_old_lifecycle_rejection_skill),
            ("old-pair", make_old_pair_rejection_skill),
        ):
            with self.subTest(shape=label), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                canonical_parent = root / "canonical"
                installed_parent = root / "installed"
                canonical = canonical_parent / "skillguard"
                builder(canonical, "skillguard")
                builder(
                    canonical_parent / "skillguard-global-router",
                    "skillguard-global-router",
                )
                shutil.copytree(canonical_parent, installed_parent)
                report = audit_release_provenance(
                    ROOT,
                    canonical,
                    installed_parent / "skillguard",
                    expected_origin="https://github.com/liuyingxuvka/SkillGuard.git",
                    release_snapshot={"status": "unavailable"},
                    require_clean=False,
                    require_installed_parity=True,
                    require_release_alignment=False,
                )
                self.assertEqual("blocked", report["status"], report)
                self.assertEqual(
                    "blocked",
                    report["runtime_authority"]["canonical"]["skillguard"][
                        "authority"
                    ],
                )

    def test_authority_change_during_transient_filtered_manifest_scan_blocks(self) -> None:
        import skillguard_v2.provenance as provenance

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canonical = root / "canonical"
            installed = root / "installed"
            make_current_skill(canonical, "race-fixture")
            shutil.copytree(canonical, installed)
            original_manifest = provenance.skill_source_manifest
            injected = False

            def manifest_with_injection(skill_root: Path) -> dict[str, str]:
                nonlocal injected
                if not injected and skill_root.resolve() == canonical.resolve():
                    injected = True
                    add_old_flat_run_rejection(installed)
                return original_manifest(skill_root)

            with mock.patch.object(
                provenance,
                "skill_source_manifest",
                side_effect=manifest_with_injection,
            ):
                comparison = compare_skill_sources(canonical, installed)

            self.assertEqual([], comparison["missing_in_installed"])
            self.assertEqual([], comparison["changed_in_installed"])
            self.assertEqual([], comparison["unexpected_in_installed"])
            authority = comparison["installed_runtime_authority"]
            self.assertEqual("blocked", authority["authority"])
            self.assertIn("former_runtime_residual", authority["blockers"])
            self.assertIn(
                "runtime_authority_changed_during_manifest_scan",
                authority["blockers"],
            )


if __name__ == "__main__":
    unittest.main()
