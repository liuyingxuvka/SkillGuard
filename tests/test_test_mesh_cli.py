from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from _skillguard_v2_runtime_fixture import SCRIPT_ROOT  # noqa: F401
import skillguard_test_mesh


class TestMeshCliTests(unittest.TestCase):
    def test_owner_execution_mode_forwards_exact_frozen_plan_without_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            for name in ("run", "skill", "target", "owner"):
                (repository / name).mkdir()
            plan = {"status": "passed", "profile_id": "fast"}
            (repository / "plan.json").write_text(
                json.dumps(plan), encoding="utf-8"
            )
            with patch.object(
                skillguard_test_mesh,
                "execute_test_mesh",
                return_value={"status": "passed"},
            ) as execute, redirect_stdout(io.StringIO()):
                exit_code = skillguard_test_mesh.main(
                    [
                        "--repository-root",
                        str(repository),
                        "--profile",
                        "fast",
                        "--mode",
                        "owner_execution_only",
                        "--run-root",
                        "run",
                        "--skill-root",
                        "skill",
                        "--target-root",
                        "target",
                        "--owner-evidence-root",
                        "owner",
                        "--frozen-plan",
                        "plan.json",
                    ]
                )
        self.assertEqual(0, exit_code)
        self.assertEqual("owner_execution_only", execute.call_args.kwargs["mode"])
        self.assertEqual(plan, execute.call_args.kwargs["frozen_plan"])

    def test_external_full_aggregation_forwards_canonical_skillguard_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = root / "external-target"
            canonical = root / "skillguard-source" / ".agents/skills/skillguard"
            for path in (
                repository / "run",
                repository / "skill",
                repository / "target",
                repository / "owner",
                repository / "installation",
                canonical,
            ):
                path.mkdir(parents=True)
            (repository / "plan.json").write_text(
                json.dumps({"status": "passed"}), encoding="utf-8"
            )
            with patch.object(
                skillguard_test_mesh,
                "execute_test_mesh",
                return_value={"status": "passed"},
            ) as execute, redirect_stdout(io.StringIO()):
                exit_code = skillguard_test_mesh.main(
                    [
                        "--repository-root",
                        str(repository),
                        "--profile",
                        "full",
                        "--mode",
                        "aggregation_only",
                        "--run-root",
                        "run",
                        "--skill-root",
                        "skill",
                        "--target-root",
                        "target",
                        "--owner-evidence-root",
                        "owner",
                        "--frozen-plan",
                        "plan.json",
                        "--installation-receipt-root",
                        "installation",
                        "--canonical-skillguard-root",
                        str(canonical),
                    ]
                )
        self.assertEqual(0, exit_code)
        self.assertEqual(
            canonical.resolve(), execute.call_args.kwargs["canonical_skillguard_root"]
        )

    def test_read_only_replay_forwards_same_canonical_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = root / "external-target"
            canonical = root / "skillguard-source" / ".agents/skills/skillguard"
            (repository / "owner").mkdir(parents=True)
            canonical.mkdir(parents=True)
            (repository / "aggregation-ref.json").write_text(
                json.dumps({"path_token": "owner_evidence_root"}),
                encoding="utf-8",
            )
            with patch.object(
                skillguard_test_mesh,
                "replay_current_test_mesh_aggregation",
                return_value={"status": "passed"},
            ) as replay, redirect_stdout(io.StringIO()):
                exit_code = skillguard_test_mesh.main(
                    [
                        "--repository-root",
                        str(repository),
                        "--replay-aggregation-ref",
                        "aggregation-ref.json",
                        "--owner-evidence-root",
                        "owner",
                        "--canonical-skillguard-root",
                        str(canonical),
                    ]
                )
        self.assertEqual(0, exit_code)
        self.assertEqual(
            canonical.resolve(), replay.call_args.kwargs["canonical_skillguard_root"]
        )


if __name__ == "__main__":
    unittest.main()
