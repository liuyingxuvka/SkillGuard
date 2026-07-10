from __future__ import annotations

import copy
import unittest

from _skillguard_v2_runtime_fixture import SCRIPT_ROOT, runtime_contract  # noqa: F401
from skillguard_v2.route_runtime import select_routes


class RouteRuntimeV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = runtime_contract()

    def test_single_function_is_selected_from_intent(self) -> None:
        decision = select_routes(self.contract, {"intent": "please audit this repository"})
        self.assertTrue(decision.ok, decision.to_dict())
        self.assertEqual(("analyze",), decision.function_ids)
        self.assertEqual(("route:analyze",), decision.route_ids)

    def test_explicit_unknown_route_blocks(self) -> None:
        decision = select_routes(self.contract, {"route_ids": ["route:missing"]})
        self.assertFalse(decision.ok)
        self.assertEqual({"unknown_route"}, {row.code for row in decision.findings})

    def test_equal_top_scores_block_as_ambiguous(self) -> None:
        ambiguous = copy.deepcopy(self.contract)
        ambiguous["functions"][1]["business_intent"] = "analyze repository"
        ambiguous["functions"][1]["intent_patterns"] = ["audit"]
        decision = select_routes(ambiguous, {"intent": "audit"})
        self.assertFalse(decision.ok)
        self.assertEqual({"ambiguous_route_match"}, {row.code for row in decision.findings})

    def test_multi_function_requires_explicit_composition(self) -> None:
        decision = select_routes(self.contract, {"function_ids": ["analyze", "publish"]})
        self.assertFalse(decision.ok)
        self.assertIn("composition_not_requested", {row.code for row in decision.findings})

    def test_declared_compatible_composition_is_selected(self) -> None:
        decision = select_routes(
            self.contract,
            {"function_ids": ["analyze", "publish"], "compose": True},
        )
        self.assertTrue(decision.ok, decision.to_dict())
        self.assertEqual(("route:analyze", "route:publish"), decision.route_ids)

    def test_one_sided_or_missing_compatibility_blocks_composition(self) -> None:
        incompatible = copy.deepcopy(self.contract)
        incompatible["functions"][1]["composable_with"] = []
        decision = select_routes(
            incompatible,
            {"function_ids": ["analyze", "publish"], "compose": True},
        )
        self.assertFalse(decision.ok)
        self.assertIn("incompatible_function_composition", {row.code for row in decision.findings})


if __name__ == "__main__":
    unittest.main()
