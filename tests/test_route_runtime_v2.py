from __future__ import annotations

import copy
import unittest

from tests._skillguard_v2_runtime_fixture import SCRIPT_ROOT, runtime_contract  # noqa: F401
from skillguard_v2.route_runtime import select_routes


class RouteRuntimeV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = runtime_contract()

    def _predicate_contract(self) -> dict[str, object]:
        contract = copy.deepcopy(self.contract)
        predicates = {
            "route:analyze": {"operation": "analyze"},
            "route:publish": {"operation": "publish"},
        }
        for route in contract["routes"]:
            route["when"] = predicates[route["route_id"]]
        return contract

    def test_single_function_is_selected_from_facts(self) -> None:
        decision = select_routes(
            self._predicate_contract(),
            {"facts": {"operation": "analyze"}},
        )
        self.assertTrue(decision.ok, decision.to_dict())
        self.assertEqual(("analyze",), decision.function_ids)
        self.assertEqual(("route:analyze",), decision.route_ids)

    def test_keyword_intent_is_not_a_route_selector(self) -> None:
        decision = select_routes(
            self._predicate_contract(),
            {"intent": "please audit this repository"},
        )
        self.assertFalse(decision.ok)
        self.assertEqual({"MISSING_FACT"}, {row.code for row in decision.findings})

    def test_missing_fact_blocks_before_selecting_a_route(self) -> None:
        decision = select_routes(self._predicate_contract(), {"facts": {}})
        self.assertFalse(decision.ok)
        self.assertEqual({"MISSING_FACT"}, {row.code for row in decision.findings})

    def test_facts_that_match_no_predicate_return_no_route(self) -> None:
        decision = select_routes(
            self._predicate_contract(),
            {"facts": {"operation": "inspect"}},
        )
        self.assertFalse(decision.ok)
        self.assertEqual({"NO_ROUTE"}, {row.code for row in decision.findings})

    def test_multiple_matching_predicates_return_ambiguous_route(self) -> None:
        ambiguous = self._predicate_contract()
        ambiguous["routes"][1]["when"] = {"operation": "analyze"}
        decision = select_routes(ambiguous, {"facts": {"operation": "analyze"}})
        self.assertFalse(decision.ok)
        self.assertEqual({"AMBIGUOUS_ROUTE"}, {row.code for row in decision.findings})

    def test_explicit_unknown_route_blocks(self) -> None:
        decision = select_routes(
            self._predicate_contract(),
            {"route_id": "route:missing", "facts": {"operation": "analyze"}},
        )
        self.assertFalse(decision.ok)
        self.assertEqual({"UNKNOWN_ROUTE"}, {row.code for row in decision.findings})

    def test_unknown_explicit_route_is_reported_before_missing_facts(self) -> None:
        decision = select_routes(
            self._predicate_contract(),
            {"route_id": "route:missing"},
        )
        self.assertFalse(decision.ok)
        self.assertEqual({"UNKNOWN_ROUTE"}, {row.code for row in decision.findings})

    def test_explicit_route_must_satisfy_its_predicate(self) -> None:
        decision = select_routes(
            self._predicate_contract(),
            {"route_id": "route:analyze", "facts": {"operation": "publish"}},
        )
        self.assertFalse(decision.ok)
        self.assertEqual({"NO_ROUTE"}, {row.code for row in decision.findings})

    def test_explicit_route_missing_fact_is_rejected(self) -> None:
        decision = select_routes(
            self._predicate_contract(),
            {"route_id": "route:analyze", "facts": {}},
        )
        self.assertFalse(decision.ok)
        self.assertEqual({"MISSING_FACT"}, {row.code for row in decision.findings})

    def test_explicit_route_with_matching_facts_is_selected(self) -> None:
        decision = select_routes(
            self._predicate_contract(),
            {"route_id": "route:analyze", "facts": {"operation": "analyze"}},
        )
        self.assertTrue(decision.ok, decision.to_dict())
        self.assertEqual(("analyze",), decision.function_ids)
        self.assertEqual(("route:analyze",), decision.route_ids)

    def test_business_routes_are_not_limited_to_three(self) -> None:
        expanded = self._predicate_contract()
        for index in range(3, 7):
            function_id = f"business_{index}"
            route_id = f"route:business-{index}"
            expanded["routes"].append(
                {
                    "route_id": route_id,
                    "function_id": function_id,
                    "when": {"operation": f"business-{index}"},
                    "step_ids": [],
                    "obligation_ids": [],
                    "composable_with": [],
                }
            )

        self.assertGreater(len(expanded["routes"]), 3)
        decision = select_routes(
            expanded,
            {"facts": {"operation": "business-6"}},
        )
        self.assertTrue(decision.ok, decision.to_dict())
        self.assertEqual(("business_6",), decision.function_ids)
        self.assertEqual(("route:business-6",), decision.route_ids)

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
        incompatible["routes"][1]["composable_with"] = []
        decision = select_routes(
            incompatible,
            {"function_ids": ["analyze", "publish"], "compose": True},
        )
        self.assertFalse(decision.ok)
        self.assertIn("incompatible_function_composition", {row.code for row in decision.findings})


if __name__ == "__main__":
    unittest.main()
