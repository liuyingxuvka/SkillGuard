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

from skillguard_v2.runtime_authority import (  # noqa: E402
    AUTHORITY_BLOCKED,
    AUTHORITY_CURRENT,
    resolve_runtime_authority,
)
from tests._runtime_authority_consumer_fixture import (  # noqa: E402
    OLD_WORK_CONTRACT_PATH,
    add_old_flat_run_rejection,
    make_current_skill,
    write_json,
    write_old_pair_rejection,
)


class CurrentRuntimeAuthorityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="skillguard-current-authority-")
        self.root = Path(self.temp.name)
        self.skill = self.root / "fixture-skill"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_complete_current_trio_is_the_only_success_shape(self) -> None:
        make_current_skill(self.skill, self.skill.name)

        decision = resolve_runtime_authority(self.skill)

        self.assertTrue(decision.ok, decision.to_dict())
        self.assertEqual(AUTHORITY_CURRENT, decision.authority)
        projection = decision.to_dict()
        self.assertNotIn("lifecycle_status", projection)
        self.assertNotIn("eligibility_receipt_path", projection)
        self.assertNotIn("completion_receipt_path", projection)
        self.assertNotIn("legacy_runtime_artifacts", projection)
        self.assertEqual([], projection["former_runtime_residuals"])

    def test_incomplete_current_trio_is_blocked_without_fallback(self) -> None:
        make_current_skill(self.skill, self.skill.name)
        (self.skill / ".skillguard" / "check-manifest.json").unlink()

        decision = resolve_runtime_authority(self.skill)

        self.assertFalse(decision.ok)
        self.assertEqual(AUTHORITY_BLOCKED, decision.authority)
        self.assertIn("current_authority_incomplete", decision.blockers)

    def test_old_pair_only_is_blocked_and_cannot_manufacture_success(self) -> None:
        write_old_pair_rejection(self.skill, self.skill.name)

        decision = resolve_runtime_authority(self.skill)

        self.assertEqual(AUTHORITY_BLOCKED, decision.authority)
        self.assertIn("current_authority_incomplete", decision.blockers)
        self.assertIn("former_runtime_residual", decision.blockers)

    def test_old_lifecycle_field_is_rejected_from_current_source(self) -> None:
        make_current_skill(self.skill, self.skill.name)
        source_path = self.skill / ".skillguard" / "contract-source.json"
        source = json.loads(source_path.read_text(encoding="utf-8"))
        source["v1_runtime_authority"] = {"status": "retired"}
        write_json(source_path, source)

        decision = resolve_runtime_authority(self.skill)

        self.assertEqual(AUTHORITY_BLOCKED, decision.authority)
        self.assertIn(
            "contract_source_binding_source_unknown_field",
            decision.blockers,
        )

    def test_model_identity_mismatch_blocks_even_when_envelopes_are_resigned(self) -> None:
        make_current_skill(self.skill, self.skill.name)
        source_path = self.skill / ".skillguard" / "contract-source.json"
        source = json.loads(source_path.read_text(encoding="utf-8"))
        source["model_id"] = "different.model.current"
        write_json(source_path, source)

        decision = resolve_runtime_authority(self.skill)

        self.assertEqual(AUTHORITY_BLOCKED, decision.authority)
        self.assertIn("current_model_identity_mismatch", decision.blockers)

    def test_former_runtime_residual_blocks_but_current_run_directory_does_not(self) -> None:
        make_current_skill(self.skill, self.skill.name, with_current_run=True)
        current_run = self.skill / ".skillguard" / "runs" / "run-current" / "run.json"
        self.assertTrue(current_run.is_file())
        self.assertEqual(AUTHORITY_CURRENT, resolve_runtime_authority(self.skill).authority)

        add_old_flat_run_rejection(self.skill)
        blocked = resolve_runtime_authority(self.skill)

        self.assertEqual(AUTHORITY_BLOCKED, blocked.authority)
        self.assertIn("former_runtime_residual", blocked.blockers)
        self.assertTrue(current_run.is_file())

    def test_former_history_is_not_a_live_audit_surface(self) -> None:
        make_current_skill(self.skill, self.skill.name)
        history = self.skill / ".skillguard" / "v1r" / "audit-history.json"
        write_json(history, {"event": "historical-only", "sequence": 1})
        decision = resolve_runtime_authority(self.skill)

        self.assertEqual(AUTHORITY_BLOCKED, decision.authority)
        self.assertIn("former_runtime_residual", decision.blockers)
        self.assertIn(
            ".skillguard/v1r/audit-history.json",
            {row.path for row in decision.former_runtime_residuals},
        )

    def test_isolated_root_never_escapes_to_parent_or_requested_repository(self) -> None:
        make_current_skill(self.skill, self.skill.name)
        decoy = self.root / "elsewhere"
        write_old_pair_rejection(decoy / "fixture-skill", "fixture-skill")

        decision = resolve_runtime_authority(
            self.skill,
            repository_root=decoy,
        )

        self.assertEqual(AUTHORITY_CURRENT, decision.authority)
        self.assertEqual([], decision.to_dict()["former_runtime_residuals"])

    def test_no_live_conversion_or_retirement_schema_surface_exists(self) -> None:
        skill_root = ROOT / ".agents" / "skills" / "skillguard"
        schema_root = (
            skill_root / "assets" / "schemas"
        )
        for filename in (
            "skillguard_v1_retirement_eligibility_receipt_v1.schema.json",
            "skillguard_v1_retirement_completion_receipt_v1.schema.json",
        ):
            self.assertFalse((schema_root / filename).exists())
        self.assertFalse((skill_root / "scripts" / "skillguard_v1_retirement.py").exists())
        self.assertFalse((skill_root / "scripts" / "skillguard_legacy_depth_upgrade.py").exists())

    def test_current_projection_names_the_exact_former_file_when_it_reappears(self) -> None:
        make_current_skill(self.skill, self.skill.name)
        write_json(
            self.skill / OLD_WORK_CONTRACT_PATH,
            {"schema_version": "skillguard.work_contract.v1", "skill_id": self.skill.name},
        )

        decision = resolve_runtime_authority(self.skill)

        self.assertEqual(AUTHORITY_BLOCKED, decision.authority)
        self.assertIn(
            OLD_WORK_CONTRACT_PATH,
            {row.path for row in decision.former_runtime_residuals},
        )


if __name__ == "__main__":
    unittest.main()
