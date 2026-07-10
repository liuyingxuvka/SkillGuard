from __future__ import annotations

import copy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / ".agents" / "skills" / "skillguard" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from skillguard_v2.contract_compiler import canonical_hash  # noqa: E402


def runtime_contract() -> dict[str, object]:
    contract: dict[str, object] = {
        "schema_version": "skillguard.compiled_contract.v2",
        "compiler_version": "fixture",
        "skill_id": "runtime-fixture",
        "model_id": "runtime-fixture-model",
        "parent_model_id": "fixture-parent",
        "flowguard_schema_version": "1.0",
        "functions": [
            {
                "function_id": "analyze",
                "business_intent": "analyze repository",
                "intent_patterns": ["audit", "检查"],
                "owner_id": "fixture",
                "route_ids": ["route:analyze"],
                "composable_with": ["publish"],
            },
            {
                "function_id": "publish",
                "business_intent": "publish release",
                "intent_patterns": ["release", "发布"],
                "owner_id": "fixture",
                "route_ids": ["route:publish"],
                "composable_with": ["analyze"],
            },
        ],
        "routes": [
            {
                "route_id": "route:analyze",
                "function_id": "analyze",
                "owner_id": "fixture",
                "start_step_id": "step:intake",
                "step_ids": ["step:intake", "step:optional-review", "step:finish", "terminal:analyzed"],
                "success_terminal_step_id": "terminal:analyzed",
                "blocked_terminal_step_id": "terminal:analyze-blocked",
                "handoffs": [],
                "loop_policy": {
                    "progress_measure": "new_receipt",
                    "allowed_delta": "strict",
                    "success_terminal_step_id": "terminal:analyzed",
                    "blocked_terminal_step_id": "terminal:analyze-blocked",
                    "max_reentries": 2,
                },
            },
            {
                "route_id": "route:publish",
                "function_id": "publish",
                "owner_id": "fixture",
                "start_step_id": "step:package",
                "step_ids": ["step:package", "terminal:published"],
                "success_terminal_step_id": "terminal:published",
                "blocked_terminal_step_id": "terminal:publish-blocked",
                "handoffs": [],
            },
        ],
        "steps": [
            {
                "step_id": "step:intake",
                "route_id": "route:analyze",
                "owner_id": "fixture",
                "action_kind": "native",
                "prerequisite_step_ids": [],
                "required": True,
                "terminal_kind": "",
            },
            {
                "step_id": "step:optional-review",
                "route_id": "route:analyze",
                "owner_id": "fixture",
                "action_kind": "judged",
                "prerequisite_step_ids": ["step:intake"],
                "required": False,
                "terminal_kind": "",
            },
            {
                "step_id": "step:finish",
                "route_id": "route:analyze",
                "owner_id": "fixture",
                "action_kind": "native",
                "prerequisite_step_ids": ["step:optional-review"],
                "required": True,
                "terminal_kind": "",
            },
            {
                "step_id": "terminal:analyzed",
                "route_id": "route:analyze",
                "owner_id": "fixture",
                "action_kind": "terminal",
                "prerequisite_step_ids": ["step:finish"],
                "required": True,
                "terminal_kind": "success",
            },
            {
                "step_id": "step:package",
                "route_id": "route:publish",
                "owner_id": "fixture",
                "action_kind": "native",
                "prerequisite_step_ids": [],
                "required": True,
                "terminal_kind": "",
            },
            {
                "step_id": "terminal:published",
                "route_id": "route:publish",
                "owner_id": "fixture",
                "action_kind": "terminal",
                "prerequisite_step_ids": ["step:package"],
                "required": True,
                "terminal_kind": "success",
            },
        ],
        "obligations": [
            {
                "obligation_id": "obligation:intake",
                "invariant_id": "fixture:intake",
                "owner_step_ids": ["step:intake"],
                "required": True,
                "evidence_classes": ["hard"],
                "required_check_ids": ["check:intake"],
            },
            {
                "obligation_id": "obligation:review",
                "invariant_id": "fixture:review",
                "owner_step_ids": ["step:optional-review"],
                "required": True,
                "evidence_classes": ["hard"],
                "required_check_ids": ["check:review"],
            },
            {
                "obligation_id": "obligation:finish",
                "invariant_id": "fixture:finish",
                "owner_step_ids": ["step:finish"],
                "required": True,
                "evidence_classes": ["hard"],
                "required_check_ids": ["check:finish"],
            },
            {
                "obligation_id": "obligation:release",
                "invariant_id": "fixture:release",
                "owner_step_ids": ["step:finish"],
                "required": True,
                "evidence_classes": ["hard"],
                "required_check_ids": ["check:release"],
            },
            {
                "obligation_id": "obligation:quality",
                "invariant_id": "fixture:quality",
                "owner_step_ids": ["step:finish"],
                "required": True,
                "evidence_classes": ["judged"],
            },
        ],
        "artifacts": [],
        "closure_profiles": [
            {
                "profile_id": "routine",
                "required_obligation_ids": ["obligation:intake"],
            },
            {
                "profile_id": "functional",
                "required_obligation_ids": [
                    "obligation:intake",
                    "obligation:review",
                    "obligation:finish",
                ],
            },
            {
                "profile_id": "release",
                "required_obligation_ids": [
                    "obligation:intake",
                    "obligation:review",
                    "obligation:finish",
                    "obligation:release",
                ],
            },
            {
                "profile_id": "highest_quality",
                "required_obligation_ids": [
                    "obligation:intake",
                    "obligation:review",
                    "obligation:finish",
                    "obligation:release",
                    "obligation:quality",
                ],
            },
        ],
        "judgment_rubrics": [
            {
                "rubric_id": "rubric:quality",
                "version": "2",
                "criteria": ["declared outcome is visibly satisfied"],
                "claim_boundary": "Fixture quality judgment only.",
            }
        ],
        "source_fingerprints": {},
        "claim_boundary": "Runtime fixture only.",
    }
    contract["contract_hash"] = canonical_hash(contract)
    return contract


def copied_contract() -> dict[str, object]:
    return copy.deepcopy(runtime_contract())
