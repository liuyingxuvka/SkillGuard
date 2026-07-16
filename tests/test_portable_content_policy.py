from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from _skillguard_v2_runtime_fixture import ROOT, SCRIPT_ROOT  # noqa: F401
from skillguard_v2 import portable_content
from skillguard_v2.runtime_fingerprint import (
    GuardRuntimeFingerprintError,
    guard_execution_runtime_fingerprint,
)


class PortableContentPolicyTests(unittest.TestCase):
    def test_reserved_runtime_workspaces_block_at_any_depth(self) -> None:
        for token in (
            ".sg-runtime/run.json",
            ".sg-fixtures/member/data.json",
            ".sgf/member/marker",
            ".runtime_workspaces/run/data.json",
            "runtime_workspaces/run/data.json",
            "fixtures/fixture-runtime/work/data.json",
            "fixtures/fixture-generation/work/data.json",
        ):
            with self.subTest(token=token):
                decision = portable_content.classify_relative_path(token)
                self.assertEqual(decision.classification, portable_content.RUNTIME)
                self.assertTrue(decision.boundary_blocking)
                self.assertEqual(decision.reason, "reserved_runtime_workspace")

    def test_member_control_runtime_is_excluded_but_nested_fixture_is_portable(self) -> None:
        live = portable_content.classify_relative_path(".skillguard/runs/run.json")
        fixture = portable_content.classify_relative_path(
            "fixtures/runtime_contract/legacy_target/.skillguard/runs/old-flat-run-rejection.json"
        )
        self.assertEqual(live.classification, portable_content.RUNTIME)
        self.assertFalse(live.boundary_blocking)
        self.assertTrue(fixture.portable)

    def test_member_root_work_output_is_excluded_but_nested_fixture_work_is_portable(self) -> None:
        live = portable_content.classify_relative_path(
            "work/global-router-refresh-final.json"
        )
        fixture = portable_content.classify_relative_path(
            "fixtures/example/work/expected.json"
        )
        self.assertEqual(live.classification, portable_content.RUNTIME)
        self.assertEqual(live.reason, "member_root_runtime")
        self.assertFalse(live.boundary_blocking)
        self.assertTrue(fixture.portable)

    def test_scan_reports_blocking_runtime_without_losing_static_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "skill"
            static = (
                root
                / "fixtures"
                / "runtime_contract"
                / "legacy_target"
                / ".skillguard"
                / "runs"
                / "old-flat-run-rejection.json"
            )
            live = root / ".skillguard" / "runs" / "run.json"
            blocking = root / ".sg-runtime" / "case" / "marker.json"
            for path in (static, live, blocking):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}\n", encoding="utf-8")

            report = portable_content.scan_member_boundary(root)
            portable = {
                relative.as_posix()
                for relative, _path in portable_content.portable_files(root)
            }

        self.assertFalse(report.ok)
        self.assertIn(".sg-runtime", report.blocking_runtime_paths)
        self.assertIn(".skillguard/runs", report.excluded_runtime_paths)
        self.assertIn(
            "fixtures/runtime_contract/legacy_target/.skillguard/runs/old-flat-run-rejection.json",
            portable,
        )
        self.assertNotIn(".skillguard/runs/run.json", portable)
        self.assertNotIn(".sg-runtime/case/marker.json", portable)

    def test_copy_projection_uses_member_root_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "skill"
            fixture_control = (
                root / "fixtures" / "member" / ".skillguard"
            )
            live_control = root / ".skillguard"
            fixture_control.mkdir(parents=True)
            live_control.mkdir(parents=True)
            fixture_ignored = portable_content.ignored_copy_names(
                root, fixture_control, ["runs", "contract-source.json"]
            )
            live_ignored = portable_content.ignored_copy_names(
                root, live_control, ["runs", "contract-source.json"]
            )
        self.assertNotIn("runs", fixture_ignored)
        self.assertIn("runs", live_ignored)
        self.assertNotIn("contract-source.json", live_ignored)

    def test_unsafe_relative_tokens_fail_closed(self) -> None:
        for token in ("../escape", "/absolute", "a/../../escape"):
            with self.subTest(token=token):
                decision = portable_content.classify_relative_path(token)
                self.assertEqual(decision.classification, portable_content.UNSAFE)
                self.assertTrue(decision.boundary_blocking)

    def test_runtime_projection_covers_caches_locks_bootstrap_and_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "skill"
            paths = (
                root / ".pytest_cache" / "state.json",
                root / ".skillguard" / "locks" / "run.lock",
                root / ".skillguard" / "bootstrap" / "authority.json",
                root / ".skillguard" / "test-results" / "result.json",
            )
            for path in paths:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}\n", encoding="utf-8")
                with self.subTest(path=path):
                    self.assertTrue(
                        portable_content.runtime_fingerprint_excluded(root, path)
                    )

    def test_owned_cleanup_projection_allows_only_reserved_direct_parent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            self.assertTrue(
                portable_content.owned_runtime_parent_may_be_pruned(
                    root, root / ".sg-runtime"
                )
            )
            self.assertFalse(
                portable_content.owned_runtime_parent_may_be_pruned(
                    root, root / "ordinary-workspace"
                )
            )
            self.assertFalse(
                portable_content.owned_runtime_parent_may_be_pruned(
                    root, root / "nested" / ".sg-runtime"
                )
            )

    def test_execution_fingerprint_projects_receipt_only_for_exact_active_install(self) -> None:
        canonical = ROOT / ".agents" / "skills" / "skillguard"
        router = ROOT / ".agents" / "skills" / "skillguard-global-router"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / ".codex"
            active = codex_home / "skills" / "skillguard"
            source_copy = root / "canonical-copy"
            shutil.copytree(canonical, active)
            shutil.copytree(canonical, source_copy)
            shutil.copytree(router, active.parent / "skillguard-global-router")
            shutil.copytree(router, source_copy.parent / "skillguard-global-router")
            for member in (active, source_copy):
                receipt = member / ".sg-runtime" / "installation" / "HEAD.json"
                receipt.parent.mkdir(parents=True)
                receipt.write_text("{}\n", encoding="utf-8")

            with patch.dict(os.environ, {"CODEX_HOME": str(codex_home)}):
                active_fingerprint = guard_execution_runtime_fingerprint(active)
                with self.assertRaisesRegex(
                    GuardRuntimeFingerprintError,
                    r"portable boundary blocked: runtime:\.sg-runtime",
                ):
                    guard_execution_runtime_fingerprint(source_copy)

        self.assertEqual("skillguard-v2", active_fingerprint["runtime_id"])

    def test_active_install_keeps_unrelated_runtime_siblings_blocking(self) -> None:
        canonical = ROOT / ".agents" / "skills" / "skillguard"
        router = ROOT / ".agents" / "skills" / "skillguard-global-router"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / ".codex"
            active = codex_home / "skills" / "skillguard"
            shutil.copytree(canonical, active)
            shutil.copytree(router, active.parent / "skillguard-global-router")
            receipt = active / ".sg-runtime" / "installation" / "HEAD.json"
            receipt.parent.mkdir(parents=True)
            receipt.write_text("{}\n", encoding="utf-8")
            sibling = active / ".sg-runtime" / "unexpected" / "state.json"
            sibling.parent.mkdir(parents=True)
            sibling.write_text("{}\n", encoding="utf-8")

            with patch.dict(os.environ, {"CODEX_HOME": str(codex_home)}), self.assertRaisesRegex(
                GuardRuntimeFingerprintError,
                r"portable boundary blocked: runtime:\.sg-runtime",
            ):
                guard_execution_runtime_fingerprint(active)


if __name__ == "__main__":
    unittest.main()
