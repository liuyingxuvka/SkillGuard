"""Portable executable FlowGuard export for the global-router skill.

The target skill owns no second router implementation.  This model binds the
public command paths to the sibling SkillGuard CLI and intentionally carries no
source-repository parent-path dependency, so the same bytes load from a copied
or installed skill root.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import flowguard


FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"
MODEL_ID = "skillguard.global_router.executable_contract.v2"
PARENT_MODEL_ID = "skillguard-global-router"

FUNCTION_SPECS = (
    (
        "function:scan-global-skills",
        "scan explicit installed or repository-local skill roots",
        "route:scan-global-skills",
        ("scan global skills", "scan skill roots", "discover skill documents"),
    ),
    (
        "function:build-global-registry",
        "build the global SkillGuard registry from a current skill scan",
        "route:build-global-registry",
        ("build global registry", "create skill registry", "rebuild route registry"),
    ),
    (
        "function:check-global-registry",
        "check global registry schema identity and freshness against its scan roots",
        "route:check-global-registry",
        ("check global registry", "registry freshness", "stale registry"),
    ),
    (
        "function:render-global-prompt",
        "render the managed AGENTS prompt projection from the current registry",
        "route:render-global-prompt",
        ("render global prompt", "prompt projection", "managed agents block"),
    ),
    (
        "function:install-global-prompt",
        "install or replace only the managed SkillGuard block while preserving unrelated AGENTS content",
        "route:install-global-prompt",
        ("install global prompt", "repair managed agents block", "preserve agents content"),
    ),
    (
        "function:check-global-prompt",
        "check managed AGENTS block uniqueness markers and current registry hash",
        "route:check-global-prompt",
        ("check global prompt", "prompt freshness", "marker corruption"),
    ),
    (
        "function:resolve-global-skill",
        "resolve one task to exactly one current skill and hand off to its own route documents",
        "route:resolve-global-skill",
        ("resolve global skill", "select target skill", "route handoff"),
    ),
    (
        "function:refresh-global-router",
        "refresh scan registry prompt installation freshness checks and a smoke handoff end to end",
        "route:refresh-global-router",
        ("refresh global router", "onboard new skill", "repair global router"),
    ),
)


def _step(
    step_id: str,
    route_id: str,
    action_kind: str,
    prerequisites: Sequence[str] = (),
    *,
    terminal_kind: str = "",
) -> dict[str, object]:
    return {
        "step_id": step_id,
        "route_id": route_id,
        "owner_id": "skillguard.global_router_cli",
        "action_kind": action_kind,
        "prerequisite_step_ids": list(prerequisites),
        "required": True,
        "terminal_kind": terminal_kind,
    }


def _route(route_id: str) -> dict[str, object]:
    suffix = route_id.removeprefix("route:")
    action = f"step:{suffix}:execute"
    verify = f"step:{suffix}:verify"
    success = f"terminal:{suffix}:current"
    blocked = f"terminal:{suffix}:blocked"
    return {
        "route_id": route_id,
        "function_id": f"function:{suffix}",
        "owner_id": "skillguard.global_router_cli",
        "start_step_id": action,
        "step_ids": [action, verify, success, blocked],
        "success_terminal_step_id": success,
        "blocked_terminal_step_id": blocked,
        "handoffs": [],
    }


def export_contract_model() -> Mapping[str, object]:
    function_ids = tuple(row[0] for row in FUNCTION_SPECS)
    functions = [
        {
            "function_id": function_id,
            "business_intent": business_intent,
            "owner_id": "skillguard.global_router_cli",
            "route_ids": [route_id, "route:shared-supervision"],
            "intent_patterns": list(intent_patterns),
            "exclude_patterns": [
                "execute the selected target skill",
                "prove package publication",
                "guarantee future ai behavior",
            ],
            "composable_with": [item for item in function_ids if item != function_id],
        }
        for function_id, business_intent, route_id, intent_patterns in FUNCTION_SPECS
    ]
    routes = [_route(route_id) for _, _, route_id, _ in FUNCTION_SPECS]
    routes.append(
        {
            "route_id": "route:shared-supervision",
            "function_id": "function:scan-global-skills",
            "owner_id": "skillguard.global_router_contract_supervisor",
            "start_step_id": "step:shared:validate-model",
            "step_ids": [
                "step:shared:validate-model",
                "step:shared:run-native-regressions",
                "terminal:shared:current",
                "terminal:shared:blocked",
            ],
            "success_terminal_step_id": "terminal:shared:current",
            "blocked_terminal_step_id": "terminal:shared:blocked",
            "handoffs": [],
        }
    )
    steps: list[dict[str, object]] = []
    for _, _, route_id, _ in FUNCTION_SPECS:
        suffix = route_id.removeprefix("route:")
        action = f"step:{suffix}:execute"
        verify = f"step:{suffix}:verify"
        steps.extend(
            (
                _step(action, route_id, "native_action"),
                _step(verify, route_id, "native_check", (action,)),
                _step(
                    f"terminal:{suffix}:current",
                    route_id,
                    "terminal",
                    (verify,),
                    terminal_kind="success",
                ),
                _step(
                    f"terminal:{suffix}:blocked",
                    route_id,
                    "terminal",
                    terminal_kind="blocked",
                ),
            )
        )
    steps.extend(
        (
            _step(
                "step:shared:validate-model",
                "route:shared-supervision",
                "flowguard_model",
            ),
            _step(
                "step:shared:run-native-regressions",
                "route:shared-supervision",
                "native_check",
                ("step:shared:validate-model",),
            ),
            _step(
                "terminal:shared:current",
                "route:shared-supervision",
                "terminal",
                ("step:shared:run-native-regressions",),
                terminal_kind="success",
            ),
            _step(
                "terminal:shared:blocked",
                "route:shared-supervision",
                "terminal",
                terminal_kind="blocked",
            ),
        )
    )
    obligations = []
    for _, _, route_id, _ in FUNCTION_SPECS:
        suffix = route_id.removeprefix("route:")
        obligations.append(
            {
                "obligation_id": f"obligation:{suffix}",
                "invariant_id": "requested_route_uses_native_owner",
                "owner_step_ids": [
                    f"step:{suffix}:execute",
                    f"step:{suffix}:verify",
                ],
                "required": True,
            }
        )
    obligations.extend(
        (
            {
                "obligation_id": "obligation:model-authority",
                "invariant_id": "model_and_binding_are_authoritative",
                "owner_step_ids": ["step:shared:validate-model"],
                "required": True,
            },
            {
                "obligation_id": "obligation:portable-root",
                "invariant_id": "portable_skill_root_is_self_contained",
                "owner_step_ids": ["step:shared:validate-model"],
                "required": True,
            },
            {
                "obligation_id": "obligation:native-regression",
                "invariant_id": "native_checks_are_current",
                "owner_step_ids": ["step:shared:run-native-regressions"],
                "required": True,
            },
            {
                "obligation_id": "obligation:command-surface",
                "invariant_id": "public_commands_are_available",
                "owner_step_ids": [
                    *[
                        f"step:{route_id.removeprefix('route:')}:execute"
                        for _, _, route_id, _ in FUNCTION_SPECS
                    ],
                    "step:shared:run-native-regressions",
                ],
                "required": True,
            },
            {
                "obligation_id": "obligation:negative-boundaries",
                "invariant_id": "failures_and_stale_state_remain_visible",
                "owner_step_ids": ["step:shared:run-native-regressions"],
                "required": True,
            },
            {
                "obligation_id": "obligation:claim-boundary",
                "invariant_id": "router_does_not_replace_target_skill",
                "owner_step_ids": ["step:shared:validate-model"],
                "required": True,
            },
        )
    )
    return {
        "schema_version": "skillguard.flowguard_model_export.v2",
        "flowguard_schema_version": str(flowguard.SCHEMA_VERSION),
        "model_id": MODEL_ID,
        "parent_model_id": PARENT_MODEL_ID,
        "functions": functions,
        "routes": routes,
        "steps": steps,
        "obligations": obligations,
        "invariant_ids": [
            "requested_route_uses_native_owner",
            "model_and_binding_are_authoritative",
            "portable_skill_root_is_self_contained",
            "native_checks_are_current",
            "public_commands_are_available",
            "failures_and_stale_state_remain_visible",
            "router_does_not_replace_target_skill",
        ],
        "claim_boundary": (
            "This portable model enumerates the global-router command paths and binds them to the existing "
            "sibling SkillGuard CLI without a source-layout parent dependency. It does not implement a second "
            "router, execute the selected target skill, prove a user-level installation, prove publication, "
            "or guarantee future AI behavior."
        ),
    }


def main() -> int:
    skill_root = Path(__file__).resolve().parents[1]
    candidates = [skill_root.parent / "skillguard"]
    codex_home = os.environ.get("CODEX_HOME", "").strip()
    if codex_home:
        candidates.append(Path(codex_home) / "skills" / "skillguard")
    candidates.append(Path.home() / ".codex" / "skills" / "skillguard")
    scripts_root = next(
        (candidate / "scripts" for candidate in candidates if (candidate / "scripts").is_dir()),
        None,
    )
    if scripts_root is None:
        print(json.dumps({
            "schema_version": "skillguard.global_router_contract_model_check.v1",
            "decision": "block",
            "model_findings": [{"code": "sibling_skillguard_missing"}],
            "model_id": MODEL_ID,
            "claim_boundary": "A missing sibling SkillGuard runtime supplies no native-router proof.",
        }, ensure_ascii=False, sort_keys=True))
        return 1
    sys.path.insert(0, str(scripts_root.resolve()))
    try:
        from skillguard_v2.contract_schema import validate_model_export

        findings = validate_model_export(export_contract_model())
    finally:
        sys.path.pop(0)
    result = {
        "schema_version": "skillguard.global_router_contract_model_check.v1",
        "decision": "pass" if not findings else "block",
        "portable_root_model": True,
        "model_findings": [row.to_dict() for row in findings],
        "model_id": MODEL_ID,
        "claim_boundary": export_contract_model()["claim_boundary"],
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
