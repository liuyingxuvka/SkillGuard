from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".agents" / "skills" / "skillguard" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from skillguard_v2.contract_schema import validate_depth_profile  # noqa: E402
from test_execution_depth import declared_check_profile  # noqa: E402


class RetiredGuardFieldsTests(unittest.TestCase):
    def test_universal_guard_purpose_fields_are_rejected(self) -> None:
        for field, value in (
            ("purpose_contract_policy", {"provider_id": "skillguard"}),
            ("calibration", {"positive_cases": [], "shallow_cases": []}),
            ("dimensions", []),
            ("coverage_universes", []),
            ("mode", "guard"),
        ):
            with self.subTest(field=field):
                profile = copy.deepcopy(declared_check_profile())
                profile[field] = value
                codes = {finding.code for finding in validate_depth_profile(profile)}
                self.assertIn("depth_profile_unknown_field", codes)

    def test_enforcement_cannot_be_optional_or_bypassed(self) -> None:
        for value in ("optional", "advisory", "disabled", "bypass"):
            with self.subTest(value=value):
                profile = copy.deepcopy(declared_check_profile())
                profile["enforcement_level"] = value
                codes = {finding.code for finding in validate_depth_profile(profile)}
                self.assertIn("depth_enforcement_level_invalid", codes)


if __name__ == "__main__":
    unittest.main()
