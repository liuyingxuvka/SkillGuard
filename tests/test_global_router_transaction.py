from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / ".agents" / "skills" / "skillguard" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from skillguard_v2 import global_router_transaction  # noqa: E402


class GlobalRouterTransactionTests(unittest.TestCase):
    def test_identical_refresh_is_noop_and_preserves_mtime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = {
                root / "global_registry.json": b"registry\n",
                root / "global_prompt_projection.json": b"projection\n",
                root / "AGENTS.md": b"agents\n",
            }
            for path, payload in files.items():
                path.write_bytes(payload)
            before = {path: path.stat().st_mtime_ns for path in files}

            result = global_router_transaction.apply_global_router_transaction(
                files
            )

            self.assertEqual("unchanged", result["status"])
            self.assertEqual([], result["changed_paths"])
            self.assertEqual(
                before, {path: path.stat().st_mtime_ns for path in files}
            )

    def test_failed_batch_restores_every_committed_member(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = {
                root / "a.json": b"new-a\n",
                root / "b.json": b"new-b\n",
                root / "AGENTS.md": b"new-agents\n",
            }
            originals = {
                path: f"old-{path.name}\n".encode("utf-8") for path in files
            }
            for path, payload in originals.items():
                path.write_bytes(payload)

            real_replace = os.replace
            commits = 0

            def fail_second_commit(source: object, target: object) -> None:
                nonlocal commits
                if str(source).endswith(".new"):
                    commits += 1
                    if commits == 2:
                        raise OSError("simulated commit failure")
                real_replace(source, target)

            with mock.patch.object(
                global_router_transaction.os,
                "replace",
                side_effect=fail_second_commit,
            ):
                with self.assertRaises(
                    global_router_transaction.GlobalRouterTransactionError
                ):
                    global_router_transaction.apply_global_router_transaction(
                        files
                    )

            self.assertEqual(
                originals, {path: path.read_bytes() for path in files}
            )
            self.assertEqual([], list(root.glob(".*.new")))
            self.assertEqual([], list(root.glob(".*.rollback")))


if __name__ == "__main__":
    unittest.main()
