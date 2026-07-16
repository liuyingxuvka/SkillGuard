from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from _skillguard_v2_runtime_fixture import SCRIPT_ROOT  # noqa: F401
import skillguard_supervise


class SupervisorCliTests(unittest.TestCase):
    def test_explicit_repository_owner_authority_is_forwarded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            skill = root / "deep" / "skill"
            target = root / "target"
            owner = root / "repository-work" / "owner-evidence"
            run_state = root / "repository-work" / "runs" / "deep-skill"
            for directory in (skill, target):
                directory.mkdir(parents=True)
            packet = root / "packet.json"
            packet.write_text(json.dumps({"request": {}, "steps": {}}), encoding="utf-8")

            with patch.object(
                skillguard_supervise,
                "supervise_contract_run",
                return_value={"status": "closed"},
            ) as supervise, redirect_stdout(io.StringIO()):
                exit_code = skillguard_supervise.main(
                    [
                        str(skill),
                        str(packet),
                        "--target-root",
                        str(target),
                        "--repository-root",
                        str(skill),
                        "--owner-evidence-root",
                        str(owner),
                        "--run-state-root",
                        str(run_state),
                    ]
                )

        self.assertEqual(0, exit_code)
        self.assertEqual(owner, supervise.call_args.kwargs["owner_evidence_root"])
        self.assertEqual(run_state, supervise.call_args.kwargs["run_state_root"])

    def test_omitted_owner_authority_keeps_the_single_runtime_default(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            skill = root / "skill"
            target = root / "target"
            for directory in (skill, target):
                directory.mkdir()
            packet = root / "packet.json"
            packet.write_text(json.dumps({"request": {}, "steps": {}}), encoding="utf-8")

            with patch.object(
                skillguard_supervise,
                "supervise_contract_run",
                return_value={"status": "closed"},
            ) as supervise, redirect_stdout(io.StringIO()):
                exit_code = skillguard_supervise.main(
                    [
                        str(skill),
                        str(packet),
                        "--target-root",
                        str(target),
                        "--repository-root",
                        str(skill),
                    ]
                )

        self.assertEqual(0, exit_code)
        self.assertIsNone(supervise.call_args.kwargs["owner_evidence_root"])
        self.assertIsNone(supervise.call_args.kwargs["run_state_root"])


if __name__ == "__main__":
    unittest.main()
