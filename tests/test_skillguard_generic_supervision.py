from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".agents" / "skills" / "skillguard" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from skillguard_v2.declared_check_supervision import (  # noqa: E402
    freeze_declared_check_inventory,
    reconcile_declared_check_results,
)


REQUEST = "A" * 64


def declaration(check_id: str) -> dict[str, object]:
    return {
        "check_id": check_id,
        "execution_owner_id": f"owner:{check_id}",
        "evidence_domain_id": "target:native",
        "depends_on_check_ids": [],
    }


def passed_result(check_id: str) -> dict[str, object]:
    return {
        "check_id": check_id,
        "execution_owner_id": f"owner:{check_id}",
        "request_fingerprint": REQUEST,
        "disposition": "passed",
        "current": True,
        "receipt_id": f"receipt:{check_id}",
        "receipt_hash": "B" * 64,
    }


class SkillGuardGenericSupervisionTests(unittest.TestCase):
    def test_ordinary_one_way_skill_is_not_forced_to_invent_a_bad_case(self) -> None:
        inventory = freeze_declared_check_inventory(
            [declaration("check:render-document")]
        )
        result = reconcile_declared_check_results(
            inventory,
            [passed_result("check:render-document")],
            request_fingerprint=REQUEST,
        )
        self.assertEqual("passed", result["status"])
        self.assertNotIn("purpose", str(result).lower())
        self.assertNotIn("calibration", str(result).lower())

    def test_every_check_declared_by_a_multi_check_target_is_supervised(self) -> None:
        inventory = freeze_declared_check_inventory(
            [
                declaration("check:target-primary-proof"),
                declaration("check:target-secondary-proof"),
            ]
        )
        result = reconcile_declared_check_results(
            inventory,
            [
                passed_result("check:target-primary-proof"),
                passed_result("check:target-secondary-proof"),
            ],
            request_fingerprint=REQUEST,
        )
        self.assertEqual("passed", result["status"])

        incomplete = reconcile_declared_check_results(
            inventory,
            [passed_result("check:target-primary-proof")],
            request_fingerprint=REQUEST,
        )
        self.assertEqual("blocked", incomplete["status"])
        self.assertIn(
            "declared_check_not_run:check:target-secondary-proof",
            incomplete["blockers"],
        )

    def test_skillguard_does_not_assign_domain_meaning_from_check_names(self) -> None:
        inventory = freeze_declared_check_inventory(
            [declaration("check:any-target-owned-depth-proof")]
        )
        result = reconcile_declared_check_results(
            inventory,
            [passed_result("check:any-target-owned-depth-proof")],
            request_fingerprint=REQUEST,
        )
        self.assertEqual("passed", result["status"])


if __name__ == "__main__":
    unittest.main()
