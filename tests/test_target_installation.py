from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


import tests.test_contract_compiler_v2 as compiler_tests

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


class TargetInstallationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        compiler_tests.ContractCompilerV2Tests.setUpClass()

    def setUp(self) -> None:
        self.fixture = compiler_tests.ContractCompilerV2Tests(
            "test_repository_root_fixture_directory_is_source_only"
        )
        self.fixture.setUp()
        self.repo = self.fixture.repo
        self.skill = self.fixture.skill
        self.runtime = self.fixture.implementation
        self.stage_temp = tempfile.TemporaryDirectory()
        self.home_temp = tempfile.TemporaryDirectory()
        self.stage_parent = Path(self.stage_temp.name)
        self.codex_home = Path(self.home_temp.name) / ".codex"
        self.self_head = self.codex_home / "install-transactions" / "HEAD.json"
        self.self_head.parent.mkdir(parents=True)
        self.self_head.write_bytes(b"self-install-head-must-not-change\n")
        self._compile()

    def tearDown(self) -> None:
        os.environ.pop("SKILLGUARD_TARGET_INSTALL_FAILPOINT", None)
        self.stage_temp.cleanup()
        self.home_temp.cleanup()
        self.fixture.tearDown()

    def _compile(self) -> None:
        result = compile_skill_contract(
            self.skill, repository_root=self.repo, write=True
        )
        self.assertTrue(result.ok, result.to_dict())

    def _stage(self, suffix: str = "") -> Path:
        parent = self.stage_parent / (suffix or "current")
        return parent / "fixture-skill"

    def _prepare(self, suffix: str = "") -> tuple[Path, dict[str, object]]:
        stage = self._stage(suffix)
        report = prepare_target_stage(self.repo, self.skill, stage)
        self.assertEqual("passed", report["status"], report)
        return stage, report

    def _activate(self, stage: Path, prepared: dict[str, object]) -> dict[str, object]:
        report = activate_target_stage(
            self.repo,
            self.skill,
            stage,
            self.codex_home,
            stage_verification=prepared["verification"],
        )
        return report

    def test_first_install_is_projection_exact_isolated_and_rollbackable(self) -> None:
        tests_root = self.skill / "tests"
        tests_root.mkdir()
        source_only = tests_root / "test_source_only.py"
        source_only.write_text("raise RuntimeError('must not execute or install')\n", encoding="utf-8")
        self._compile()
        stage, prepared = self._prepare("first")

        self.assertFalse((stage / "tests" / source_only.name).exists())
        before_self_head = self.self_head.read_bytes()
        activated = self._activate(stage, prepared)

        self.assertEqual("passed", activated["status"], activated)
        active = self.codex_home / "skills" / "fixture-skill"
        self.assertEqual(
            audit_consumer_distribution(stage)["release_id"],
            audit_consumer_distribution(active)["release_id"],
        )
        self.assertFalse((active / ".skillguard").exists())
        self.assertFalse((active / "tests" / source_only.name).exists())
        self.assertEqual(before_self_head, self.self_head.read_bytes())
        transaction_id = str(activated["transaction_id"])
        rolled_back = rollback_target_install(
            self.codex_home, "fixture-skill", transaction_id
        )
        self.assertEqual("passed", rolled_back["status"], rolled_back)
        self.assertFalse(active.exists())
        self.assertEqual(before_self_head, self.self_head.read_bytes())

    def test_replacement_failure_after_activation_restores_previous_active(self) -> None:
        stage_one, prepared_one = self._prepare("one")
        first = self._activate(stage_one, prepared_one)
        self.assertEqual("passed", first["status"], first)
        active = self.codex_home / "skills" / "fixture-skill"
        first_runtime = (active / "runtime.py").read_text(encoding="utf-8")

        self.runtime.write_text("VALUE = 2\n", encoding="utf-8")
        self._compile()
        stage_two, prepared_two = self._prepare("two")
        os.environ["SKILLGUARD_TARGET_INSTALL_FAILPOINT"] = "after_activation"
        second = self._activate(stage_two, prepared_two)

        self.assertEqual("blocked", second["status"], second)
        self.assertEqual("rolled_back", second["restored_status"])
        self.assertEqual(first_runtime, (active / "runtime.py").read_text(encoding="utf-8"))
        self.assertEqual(
            audit_consumer_distribution(stage_one)["release_id"],
            audit_consumer_distribution(active)["release_id"],
        )

    def test_successful_replacement_and_manual_rollback_restore_previous_version(self) -> None:
        stage_one, prepared_one = self._prepare("replace-one")
        first = self._activate(stage_one, prepared_one)
        self.assertEqual("passed", first["status"], first)
        active = self.codex_home / "skills" / "fixture-skill"
        first_runtime = (active / "runtime.py").read_text(encoding="utf-8")
        self.runtime.write_text("VALUE = 4\n", encoding="utf-8")
        self._compile()
        stage_two, prepared_two = self._prepare("replace-two")

        second = self._activate(stage_two, prepared_two)

        self.assertEqual("passed", second["status"], second)
        self.assertEqual("VALUE = 4\n", (active / "runtime.py").read_text(encoding="utf-8"))
        rolled_back = rollback_target_install(
            self.codex_home, "fixture-skill", str(second["transaction_id"])
        )
        self.assertEqual("passed", rolled_back["status"], rolled_back)
        self.assertEqual(first_runtime, (active / "runtime.py").read_text(encoding="utf-8"))

    def test_unexpected_stage_file_blocks_exact_projection(self) -> None:
        stage, _prepared = self._prepare("unexpected")
        (stage / "undeclared.txt").write_text("not projected\n", encoding="utf-8")

        report = verify_target_stage(self.repo, self.skill, stage)

        self.assertEqual("blocked", report["status"], report)
        self.assertIn("target_stage_unexpected:undeclared.txt", report["blockers"])

    def test_repository_root_mismatch_blocks_prepare(self) -> None:
        outside_repository = self.repo / "unrelated"
        outside_repository.mkdir()

        with self.assertRaisesRegex(
            ValueError, "target_install_skill_root_outside_repository"
        ):
            prepare_target_stage(
                outside_repository, self.skill, self._stage("wrong-root")
            )

    def test_reparse_stage_root_is_rejected_when_supported(self) -> None:
        real_stage, _prepared = self._prepare("real-link-target")
        link_parent = self.stage_parent / "link-parent"
        link_parent.mkdir()
        linked_stage = link_parent / "fixture-skill"
        try:
            linked_stage.symlink_to(real_stage, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"directory symlink unavailable: {exc}")

        with self.assertRaisesRegex(ValueError, "target_install_stage_root_invalid"):
            verify_target_stage(self.repo, self.skill, linked_stage)

    def test_stage_drift_blocks_before_activation(self) -> None:
        stage, _prepared = self._prepare("drift")
        (stage / "runtime.py").write_text("VALUE = 999\n", encoding="utf-8")

        report = verify_target_stage(self.repo, self.skill, stage)

        self.assertEqual("blocked", report["status"], report)
        self.assertIn("consumer_file_hash_mismatch:runtime.py", report["blockers"])

    def test_crash_after_backup_is_recovered_without_touching_self_head(self) -> None:
        stage_one, prepared_one = self._prepare("recover-one")
        first = self._activate(stage_one, prepared_one)
        self.assertEqual("passed", first["status"], first)
        active = self.codex_home / "skills" / "fixture-skill"
        first_runtime = (active / "runtime.py").read_text(encoding="utf-8")
        self.runtime.write_text("VALUE = 3\n", encoding="utf-8")
        self._compile()
        stage_two, prepared_two = self._prepare("recover-two")
        before_self_head = self.self_head.read_bytes()

        import skillguard_v2.target_installation as target_module

        original_rename = target_module._durable_rename

        def crash_after_backup(source: Path, destination: Path) -> Path:
            result = original_rename(source, destination)
            if "target-install-backups" in destination.parts and destination.name.startswith("target-install-"):
                raise KeyboardInterrupt("simulated crash")
            return result

        with mock.patch.object(target_module, "_durable_rename", side_effect=crash_after_backup):
            with self.assertRaises(KeyboardInterrupt):
                self._activate(stage_two, prepared_two)

        recovered = recover_target_installations(self.codex_home, "fixture-skill")
        self.assertEqual("passed", recovered["status"], recovered)
        self.assertEqual(1, len(recovered["recovered"]), recovered)
        self.assertEqual(first_runtime, (active / "runtime.py").read_text(encoding="utf-8"))
        self.assertEqual(before_self_head, self.self_head.read_bytes())

    def test_global_install_lock_blocks_target_activation(self) -> None:
        stage, prepared = self._prepare("locked")

        with _InstallMutex(self.codex_home, "test-owner"):
            report = self._activate(stage, prepared)

        self.assertEqual("blocked", report["status"], report)
        self.assertIn("target_activation_preflight:InstallBusyError", report["blockers"])

    @unittest.skipUnless(os.name == "nt", "Windows path-budget regression")
    def test_windows_stage_path_budget_blocks_before_copy(self) -> None:
        long_parent = Path(self.stage_temp.name) / ("x" * 230)
        stage = long_parent / "fixture-skill"

        report = prepare_target_stage(self.repo, self.skill, stage)

        self.assertEqual("blocked", report["status"], report)
        self.assertTrue(report["blockers"], report)
        self.assertFalse(stage.exists())


if __name__ == "__main__":
    unittest.main()
