from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / ".agents" / "skills" / "skillguard" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from skillguard_v2.execution_records import (  # noqa: E402
    ExecutionRecordError,
    append_progress_event,
    durable_write_immutable_json,
    execution_single_flight_lock,
    filesystem_path,
)
from skillguard_v2.test_mesh import _atomic_replace_projection_ref  # noqa: E402


class ExecutionRecordDurabilityTests(unittest.TestCase):
    def test_non_current_progress_log_is_rejected_without_conversion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            relative = Path("events/progress.jsonl")
            path = root / relative
            path.parent.mkdir(parents=True)
            original = '{"schema_version": "skillguard.execution_progress_event.v1"}\n'
            path.write_text(original, encoding="utf-8")

            with self.assertRaises(ExecutionRecordError):
                append_progress_event(root, relative, {}, path_token="run_root")

            self.assertEqual(original, path.read_text(encoding="utf-8"))
            self.assertEqual([], list(path.parent.glob("*.legacy-*.json")))

    def test_long_destination_name_does_not_expand_temporary_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            segment_index = 0
            while len(str(parent)) < 145:
                parent /= f"segment-{segment_index:02d}-abcdefghij"
                segment_index += 1
            parent.mkdir(parents=True)

            available = max(24, 230 - len(str(parent)) - 1)
            destination = parent / ("r" * (available - 5) + ".json")
            self.assertLessEqual(len(str(destination)), 230)

            payload = {"schema_version": "test.record.v1", "value": "portable"}
            durable_write_immutable_json(destination, payload)

            self.assertEqual(payload, json.loads(destination.read_text(encoding="utf-8")))
            self.assertEqual([], list(parent.glob(".sg-*.tmp")))

    @unittest.skipUnless(os.name == "nt", "Windows extended-length path regression")
    def test_windows_immutable_publish_supports_destination_beyond_max_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            segment_index = 0
            while len(str(parent)) < 190:
                parent /= f"segment-{segment_index:02d}-abcdefghij"
                segment_index += 1
            parent.mkdir(parents=True)
            destination = parent / (("r" * 64) + ".json")
            representative_temporary = parent / (".sg-" + ("0" * 32) + ".tmp")

            payload = {
                "schema_version": "test.record.v1",
                "value": "windows-extended-path",
            }
            durable_write_immutable_json(destination, payload)
            durable_write_immutable_json(destination, payload)

            self.assertGreater(len(str(destination)), 260)
            self.assertLessEqual(len(str(representative_temporary)), 260)
            io_destination = Path("\\\\?\\" + str(destination))
            self.assertEqual(
                payload,
                json.loads(io_destination.read_text(encoding="utf-8")),
            )
            self.assertEqual([], list(parent.glob(".sg-*.tmp")))
            io_destination.unlink()

    @unittest.skipUnless(os.name == "nt", "Windows extended-length path regression")
    def test_windows_projection_pointer_supports_long_parent_and_replace(self) -> None:
        root = Path(tempfile.mkdtemp())
        try:
            parent = root
            segment_index = 0
            while len(str(parent)) <= 275:
                parent /= f"segment-{segment_index:02d}-abcdefghij"
                segment_index += 1
            destination = parent / "ref.json"

            _atomic_replace_projection_ref(destination, {"version": 1})
            _atomic_replace_projection_ref(destination, {"version": 2})

            self.assertGreater(len(str(destination.parent)), 260)
            self.assertEqual(
                {"version": 2},
                json.loads(
                    filesystem_path(destination).read_text(encoding="utf-8")
                ),
            )
        finally:
            shutil.rmtree(filesystem_path(root))

    @unittest.skipUnless(os.name == "nt", "Windows extended-length path regression")
    def test_windows_single_flight_lock_supports_path_beyond_max_path(self) -> None:
        root = Path(tempfile.mkdtemp())
        try:
            owner_root = root
            segment_index = 0
            while len(str(owner_root)) < 185:
                owner_root /= f"segment-{segment_index:02d}-abcdefghij"
                segment_index += 1
            owner_root.mkdir(parents=True)
            execution_key = "sha256:" + ("a" * 64)
            lock_path = (
                owner_root
                / "check-executions"
                / "locks"
                / (("a" * 64) + ".lock")
            )

            self.assertGreater(len(str(lock_path)), 260)
            with execution_single_flight_lock(owner_root, execution_key):
                self.assertTrue(filesystem_path(lock_path).is_file())
        finally:
            shutil.rmtree(filesystem_path(root))


if __name__ == "__main__":
    unittest.main()
