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

from skillguard_utils import emit_json, summarize_payload, write_report  # noqa: E402
from skillguard_v2.test_mesh import replay_current_test_mesh_aggregation  # noqa: E402


class ReportOutputBoundaryTests(unittest.TestCase):
    def test_summary_bounds_large_problem_index_and_preserves_counts(self) -> None:
        payload = {
            "schema_version": "skillguard.cli_result.v1",
            "command": "fixture",
            "decision": "block",
            "blockers": [f"problem-{index}" for index in range(1000)],
            "claim_boundary": "The summary is not execution evidence.",
        }
        summary = summarize_payload(payload)
        self.assertEqual("skillguard.cli_summary.v1", summary["schema_version"])
        self.assertEqual(10, len(summary["blockers"]))
        self.assertEqual(990, summary["truncated_count"])
        self.assertEqual("problem-0", summary["primary_blocker"])
        self.assertLessEqual(len(json.dumps(summary, ensure_ascii=False).encode("utf-8")), 8192)

    def test_explicit_emit_output_writes_full_report_and_stdout_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "full.json"
            stream = __import__("io").StringIO()
            payload = {
                "schema_version": "skillguard.cli_result.v1",
                "command": "fixture",
                "decision": "pass",
                "checks": [{"check_id": "one", "status": "pass"}],
            }
            emit_json(payload, stream=stream, output=output, root=Path(tmp))
            self.assertEqual(payload, json.loads(output.read_text(encoding="utf-8")))
            summary = json.loads(stream.getvalue())
            self.assertEqual("skillguard.cli_summary.v1", summary["schema_version"])
            self.assertEqual(str(output), summary["full_report_path"])

    def test_summary_cannot_be_consumed_as_current_aggregation_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = summarize_payload(
                {
                    "schema_version": "skillguard.cli_result.v1",
                    "command": "test-mesh",
                    "status": "passed",
                    "execution_count": 1,
                }
            )
            result = replay_current_test_mesh_aggregation(Path(tmp), summary)
            self.assertIn("aggregation_ref_invalid", result["findings"])

    def test_runtime_evidence_directory_is_writable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_report({"status": "pass"}, "work/report.json", root)
            self.assertTrue(path.samefile(root / "work" / "report.json"))
            self.assertEqual({"status": "pass"}, json.loads(path.read_text(encoding="utf-8")))

    def test_maintained_source_and_fixture_trees_are_not_report_destinations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            forbidden = root / "fixtures" / "evidence_outputs" / "report.json"

            with self.assertRaisesRegex(ValueError, "runtime evidence directory"):
                write_report({"status": "pass"}, forbidden, root)

            self.assertFalse(forbidden.exists())


if __name__ == "__main__":
    unittest.main()
