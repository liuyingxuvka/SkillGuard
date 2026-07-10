from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / ".agents" / "skills" / "skillguard" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from skillguard_v2.test_mesh import execute_test_mesh, validate_test_mesh_manifest  # noqa: E402


class TestMeshRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.workspace = Path(self.temp.name)
        self.source = self.workspace / "source.py"
        self.source.write_text("VALUE = 1\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _manifest(self, command: list[str], timeout: float = 10.0) -> dict[str, object]:
        return {
            "schema_version": "skillguard.test_mesh_manifest.v1",
            "partition_items": [
                {"partition_id": "runtime", "owner_suite_id": "child"}
            ],
            "suites": [
                {
                    "suite_id": "child",
                    "commands": {"fast": command},
                    "timeout_seconds": timeout,
                    "source_paths": [self.source.relative_to(ROOT).as_posix()],
                    "owned_partition_ids": ["runtime"],
                }
            ],
            "profiles": [
                {
                    "profile_id": "fast",
                    "scope": "routine",
                    "suite_ids": ["child"],
                    "required_partition_ids": ["runtime"],
                    "claim_boundary": "Fixture child only.",
                }
            ],
        }

    def _write_manifest(self, payload: dict[str, object]) -> Path:
        path = self.workspace / "manifest.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_current_child_result_and_parent_proof_artifacts_are_written(self) -> None:
        manifest = self._write_manifest(self._manifest([sys.executable, "-c", "print('ok')"]))
        report = execute_test_mesh(manifest, ROOT, "fast", self.workspace / "results")
        self.assertEqual("passed", report["status"])
        child = report["child_results"][0]
        self.assertEqual("passed", child["status"])
        self.assertTrue(Path(child["result_path"]).is_file())
        self.assertTrue(Path(report["result_path"]).is_file())
        self.assertFalse(child["progress_is_completion_evidence"])

    def test_timeout_is_final_failure_not_progress_only_success(self) -> None:
        manifest = self._write_manifest(
            self._manifest([sys.executable, "-c", "import time; time.sleep(2)"], timeout=0.2)
        )
        report = execute_test_mesh(manifest, ROOT, "fast", self.workspace / "timeout-results")
        self.assertEqual("failed", report["status"])
        self.assertEqual("timed_out", report["child_results"][0]["status"])
        self.assertTrue(report["skipped_checks"])

    def test_large_child_output_does_not_deadlock_the_supervisor(self) -> None:
        manifest = self._write_manifest(
            self._manifest([sys.executable, "-c", "print('x' * 250000)"], timeout=5)
        )
        report = execute_test_mesh(manifest, ROOT, "fast", self.workspace / "large-output-results")
        self.assertEqual("passed", report["status"])
        self.assertEqual(0, report["child_results"][0]["exit_code"])
        self.assertLessEqual(len(report["child_results"][0]["stdout_tail"]), 4000)

    def test_cancel_file_stops_child_and_remains_visible(self) -> None:
        cancel = self.workspace / "cancel.requested"
        cancel.write_text("cancel\n", encoding="utf-8")
        manifest = self._write_manifest(self._manifest([sys.executable, "-c", "print('must not run')"]))
        report = execute_test_mesh(
            manifest,
            ROOT,
            "fast",
            self.workspace / "cancel-results",
            cancel_file=cancel,
        )
        self.assertEqual("failed", report["status"])
        self.assertEqual("cancelled", report["child_results"][0]["status"])

    def test_missing_partition_owner_blocks_before_execution(self) -> None:
        manifest = self._manifest([sys.executable, "-c", "print('must not run')"])
        manifest["partition_items"][0]["owner_suite_id"] = "missing"
        self.assertIn("partition_owner_unknown:runtime:missing", validate_test_mesh_manifest(manifest))


if __name__ == "__main__":
    unittest.main()
