from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".agents" / "skills" / "skillguard" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import skillguard_v2.execution_depth as execution_depth_module  # noqa: E402
from skillguard_v2.execution_depth import (  # noqa: E402
    EXECUTION_DEPTH_PASS,
    SHALLOW_BLOCKED,
    _execution_runtime_identity,
    _model_deepening_projection_blocker,
    evaluate_execution_depth,
    profile_fingerprint,
)


def declared_check_profile(
    native_check_ids: tuple[str, ...] = ("check:intake",),
    *,
    model_deepening_check_id: str | None = None,
) -> dict[str, object]:
    profile: dict[str, object] = {
        "schema_version": "skillguard.depth_profile.v2",
        "profile_id": "fixture-declared-check-supervision",
        "target_skill_id": "runtime-fixture",
        "integration_mode": "native-integrated",
        "native_owner_id": "fixture",
        "native_route_ids": ["route:analyze"],
        "native_check_ids": list(native_check_ids),
        "skillguard_adds_domain_route": False,
        "enforcement_level": "enforced",
        "required_closure_profiles": ["enforced"],
        "provider_runtime": {
            "provider_id": "skillguard-local-provider",
            "required_runtime_contract_id": (
                "skillguard-declared-check-supervision-current"
            ),
            "required_capability_ids": [
                "declared-check-inventory.v1",
                "declared-check-receipt-reconciliation.v1",
            ],
            "readiness_check_ids": [native_check_ids[0]],
            "required_enrollment_status": "enrolled",
        },
        "claim_boundary": (
            "The receipt proves only the target's own declared checks."
        ),
    }
    if model_deepening_check_id is not None:
        profile["model_deepening_check_id"] = model_deepening_check_id
    return profile


def _context(
    *,
    passed: bool = True,
    current: bool | None = None,
    owner_id: str = "owner:intake",
    request_fingerprint: str = "B" * 64,
    receipt_id: str | None = None,
    receipt_hash: str | None = None,
) -> dict[str, object]:
    is_current = passed if current is None else current
    blockers = [] if passed else ["declared_check_not_run:check:intake"]
    return {
        "run_started": True,
        "current": True,
        "declared_check_reconciliation": {
            "status": "passed" if passed else "blocked",
            "request_fingerprint": request_fingerprint,
            "check_results": [
                {
                    "check_id": "check:intake",
                    "execution_owner_id": owner_id,
                    "disposition": "passed" if passed else "not_run",
                    "current": is_current,
                    "receipt_id": (
                        "receipt:intake" if passed else ""
                    ) if receipt_id is None else receipt_id,
                    "receipt_hash": (
                        "A" * 64 if passed else ""
                    ) if receipt_hash is None else receipt_hash,
                }
            ],
            "unresolved_check_ids": [] if passed else ["check:intake"],
            "blockers": blockers,
        },
        "provider_runtime_audit": {
            "status": "passed",
            "blockers": [],
        },
    }


class ExecutionDepthTests(unittest.TestCase):
    def test_runtime_identity_is_location_derived_unless_already_bound(self) -> None:
        derived = {"runtime_id": "derived", "source_hash": "A" * 64}
        explicit = {"runtime_id": "explicit", "source_hash": "B" * 64}
        with patch.object(
            execution_depth_module,
            "guard_execution_runtime_fingerprint",
            return_value=derived,
        ) as fingerprint:
            self.assertEqual(derived, _execution_runtime_identity())
            self.assertEqual(explicit, _execution_runtime_identity(explicit))
        fingerprint.assert_called_once_with()

    def test_target_declared_checks_are_the_only_depth_denominator(self) -> None:
        result = evaluate_execution_depth(
            declared_check_profile(), (), context=_context(passed=True)
        )
        self.assertEqual(EXECUTION_DEPTH_PASS, result.status)
        self.assertEqual((), result.unresolved_check_ids)
        self.assertEqual((), result.dimension_results)
        self.assertEqual((), result.coverage_universe_results)

    def test_missing_declared_check_blocks(self) -> None:
        result = evaluate_execution_depth(
            declared_check_profile(), (), context=_context(passed=False)
        )
        self.assertEqual(SHALLOW_BLOCKED, result.status)
        self.assertIn("check:intake", result.unresolved_check_ids)

    def test_profile_has_one_fixed_enforcement_behavior(self) -> None:
        profile = declared_check_profile()
        self.assertTrue(profile_fingerprint(profile))
        profile["enforcement_level"] = "optional"
        with self.assertRaises(Exception):
            profile_fingerprint(profile)

    def test_designated_model_deepening_check_projects_exact_current_receipt(self) -> None:
        result = evaluate_execution_depth(
            declared_check_profile(model_deepening_check_id="check:intake"),
            (),
            context=_context(passed=True),
        )
        self.assertEqual(EXECUTION_DEPTH_PASS, result.status)
        self.assertEqual(
            {
                "required": True,
                "check_id": "check:intake",
                "execution_owner_id": "owner:intake",
                "request_fingerprint": "B" * 64,
                "disposition": "passed",
                "current": True,
                "receipt_id": "receipt:intake",
                "receipt_hash": "A" * 64,
                "status": "passed",
            },
            result.model_deepening_result,
        )

    def test_designated_model_deepening_check_missing_result_blocks(self) -> None:
        context = _context(passed=True)
        context["declared_check_reconciliation"]["check_results"] = []
        result = evaluate_execution_depth(
            declared_check_profile(model_deepening_check_id="check:intake"),
            (),
            context=context,
        )
        self.assertEqual(SHALLOW_BLOCKED, result.status)
        self.assertEqual("blocked", result.model_deepening_result["status"])

    def test_designated_model_deepening_check_stale_receipt_blocks(self) -> None:
        context = _context(passed=True, current=False)
        context["declared_check_reconciliation"]["status"] = "blocked"
        context["declared_check_reconciliation"]["blockers"] = [
            "declared_check_stale:check:intake"
        ]
        result = evaluate_execution_depth(
            declared_check_profile(model_deepening_check_id="check:intake"),
            (),
            context=context,
        )
        self.assertEqual(SHALLOW_BLOCKED, result.status)
        self.assertFalse(result.model_deepening_result["current"])

    def test_designated_model_deepening_check_self_report_without_receipt_blocks(self) -> None:
        context = _context(
            passed=True,
            receipt_id="",
            receipt_hash="",
        )
        context["caller_reports_understanding"] = True
        result = evaluate_execution_depth(
            declared_check_profile(model_deepening_check_id="check:intake"),
            (),
            context=context,
        )
        self.assertEqual(SHALLOW_BLOCKED, result.status)
        self.assertEqual("blocked", result.model_deepening_result["status"])

    def test_designated_check_must_be_in_native_inventory(self) -> None:
        profile = declared_check_profile(model_deepening_check_id="check:other")
        with self.assertRaises(Exception):
            profile_fingerprint(profile)

    def test_profiles_without_designated_lane_do_not_claim_model_deepening(self) -> None:
        result = evaluate_execution_depth(
            declared_check_profile(), (), context=_context(passed=True)
        )
        self.assertEqual(EXECUTION_DEPTH_PASS, result.status)
        self.assertEqual("not_declared", result.model_deepening_result["status"])

    def test_replay_rejects_forged_model_deepening_projection(self) -> None:
        profile = declared_check_profile(
            model_deepening_check_id="check:intake"
        )
        row = {
            "check_id": "check:intake",
            "execution_owner_id": "owner:intake",
            "disposition": "passed",
            "current": True,
            "receipt_id": "receipt:intake",
            "receipt_hash": "A" * 64,
        }
        receipt = {
            "request_fingerprint": "B" * 64,
            "declared_check_inventory": {
                "checks": [
                    {
                        "check_id": "check:intake",
                        "execution_owner_id": "owner:intake",
                    }
                ]
            },
            "declared_check_results": [row],
            "model_deepening_result": {
                "required": True,
                **row,
                "request_fingerprint": "B" * 64,
                "status": "passed",
            },
        }
        self.assertEqual(
            "", _model_deepening_projection_blocker(receipt, profile)
        )
        receipt["model_deepening_result"]["execution_owner_id"] = "owner:foreign"
        self.assertEqual(
            "model_deepening_execution_owner_mismatch",
            _model_deepening_projection_blocker(receipt, profile),
        )


if __name__ == "__main__":
    unittest.main()
