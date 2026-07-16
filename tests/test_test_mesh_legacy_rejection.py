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

import skillguard_v2.test_mesh as test_mesh_module  # noqa: E402
from skillguard_v2.test_mesh import execute_test_mesh  # noqa: E402


class LegacyTestMeshRejectionTests(unittest.TestCase):
    def test_old_success_manifests_are_rejection_fixtures_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for schema_version in (
                "skillguard.test_mesh_manifest.v1",
                "skillguard.test_mesh_manifest.v2",
            ):
                manifest = root / f"{schema_version.rsplit('.', 1)[-1]}.json"
                manifest.write_text(
                    json.dumps({"schema_version": schema_version}) + "\n",
                    encoding="utf-8",
                )
                report = execute_test_mesh(
                    manifest,
                    root,
                    "fast",
                    run_root=root,
                    skill_root=root,
                    target_root=root,
                )
                self.assertEqual("blocked", report["status"])
                self.assertEqual(
                    ["legacy_test_mesh_manifest_rejected"], report["findings"]
                )
        self.assertFalse(hasattr(test_mesh_module, "subprocess"))
        self.assertFalse(
            hasattr(test_mesh_module, "replay_test_mesh_closure_receipt")
        )
        self.assertFalse(
            hasattr(test_mesh_module, "write_test_mesh_closure_receipt")
        )


if __name__ == "__main__":
    unittest.main()
