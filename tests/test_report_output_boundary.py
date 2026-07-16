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

from skillguard_utils import write_report  # noqa: E402


class ReportOutputBoundaryTests(unittest.TestCase):
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
