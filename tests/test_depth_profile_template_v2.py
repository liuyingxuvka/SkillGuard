from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / ".agents" / "skills" / "skillguard" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from skillguard_v2.contract_schema import validate_depth_profile  # noqa: E402
from skillguard_v2.runtime_fingerprint import RUNTIME_CAPABILITY_IDS  # noqa: E402


TEMPLATE = (
    ROOT
    / ".agents"
    / "skills"
    / "skillguard"
    / "assets"
    / "templates"
    / "skillguard_v2_depth_profile.fragment.template.json"
)
PROFILE_ROOT = (
    ROOT
    / ".agents"
    / "skills"
    / "skillguard"
    / "fixtures"
    / "depth_profiles"
)
RETIRED_DOMAIN_FIELDS = {
    "purpose_contract_policy",
    "calibration",
    "dimensions",
    "coverage_universes",
    "target_category",
    "mode",
}


class DepthProfileTemplateV2Tests(unittest.TestCase):
    def test_template_is_target_neutral_declared_check_supervision(self) -> None:
        payload = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        profile = payload["depth_profile"]
        declarations = payload["required_native_check_declarations"]

        self.assertEqual("skillguard.depth_profile.v2", profile["schema_version"])
        self.assertEqual("enforced", profile["enforcement_level"])
        self.assertFalse(profile["skillguard_adds_domain_route"])
        self.assertEqual(
            [row["check_id"] for row in declarations],
            profile["native_check_ids"],
        )
        self.assertEqual(
            list(RUNTIME_CAPABILITY_IDS),
            profile["provider_runtime"]["required_capability_ids"],
        )
        self.assertTrue(RETIRED_DOMAIN_FIELDS.isdisjoint(profile))
        serialized = json.dumps(payload, sort_keys=True).lower()
        self.assertNotIn("guard_family", serialized)
        self.assertNotIn("other_non_guard", serialized)
        self.assertNotIn("positive_calibration", serialized)
        self.assertNotIn("shallow_calibration", serialized)

    def test_all_persisted_profiles_use_the_same_fixed_generic_shape(self) -> None:
        paths = sorted(PROFILE_ROOT.glob("*_target_profile.json"))
        self.assertEqual(2, len(paths))
        for path in paths:
            with self.subTest(path=path.name):
                profile = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual((), validate_depth_profile(profile, path="$"))
                self.assertTrue(profile["native_check_ids"])
                self.assertTrue(RETIRED_DOMAIN_FIELDS.isdisjoint(profile))
                self.assertEqual("enforced", profile["enforcement_level"])


if __name__ == "__main__":
    unittest.main()
