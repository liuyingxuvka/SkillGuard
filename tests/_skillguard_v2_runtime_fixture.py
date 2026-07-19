from __future__ import annotations

import copy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / ".agents" / "skills" / "skillguard" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from skillguard_v2.contract_compiler import (  # noqa: E402
    OWNER_BEHAVIOR_FIELDS,
    canonical_hash,
    wire_hash,
)


def _current_checks_and_plan(
    source_checks: list[dict[str, object]],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    checks = copy.deepcopy(source_checks)
    for check in checks:
        check_id = str(check.get("check_id", ""))
        check.setdefault("maintenance_unit_id", "unit:runtime-fixture")
        check.setdefault("member_skill_id", "runtime-fixture")
        check.setdefault("evidence_subject_id", f"subject:{check_id.removeprefix('check:')}")
        check.setdefault("semantic_check_id", check_id)
        check.setdefault("execution_owner_id", f"owner:{check_id.removeprefix('check:')}")
        check.setdefault(
            "input_selectors",
            [{"kind": "role", "role": "runtime_source"}],
        )
        check.setdefault("input_component_ids", [])
        check.setdefault("depends_on_check_ids", [])
        check.setdefault("target_input_role_ids", [])
        check.setdefault("evidence_domain_id", "validation")
        check.setdefault(
            "owner_declaration_hash",
            wire_hash(
                {
                    "behavior": {
                        key: check[key]
                        for key in OWNER_BEHAVIOR_FIELDS
                        if key in check
                    },
                    "input_selectors": list(check["input_selectors"]),
                    "target_input_role_ids": list(
                        check["target_input_role_ids"]
                    ),
                    "evidence_domain_id": str(check["evidence_domain_id"]),
                    "impact_policy_id": "skillguard.content_impact_policy.current",
                }
            ),
        )
        check.setdefault("owner_input_projection_hash", wire_hash([]))
        projection = {
            "check_id": check_id,
            "semantic_check_id": str(check["semantic_check_id"]),
            "execution_owner_id": str(check["execution_owner_id"]),
            "covers_obligation_ids": sorted(
                str(value) for value in check.get("covers_obligation_ids", [])
            ),
            "evidence_class": str(check.get("evidence_class", "")),
        }
        check.setdefault("projection_declaration_hash", wire_hash(projection))

    check_owner = {
        str(check["check_id"]): str(check["execution_owner_id"])
        for check in checks
    }
    owner_rows: dict[str, dict[str, object]] = {}
    for check in checks:
        owner_id = str(check["execution_owner_id"])
        dependencies = sorted(
            {
                check_owner[str(check_id)]
                for check_id in check.get("depends_on_check_ids", [])
                if str(check_id) in check_owner
                and check_owner[str(check_id)] != owner_id
            }
        )
        row = owner_rows.setdefault(
            owner_id,
            {
                "execution_owner_id": owner_id,
                "check_ids": [],
                "owner_declaration_hash": str(check["owner_declaration_hash"]),
                "input_selectors": list(check.get("input_selectors", [])),
                "input_component_ids": list(check.get("input_component_ids", [])),
                "owner_input_projection_hash": str(
                    check["owner_input_projection_hash"]
                ),
                "depends_on_owner_ids": [],
                "target_input_role_ids": list(
                    check.get("target_input_role_ids", [])
                ),
                "evidence_domain_id": str(check["evidence_domain_id"]),
            },
        )
        row["check_ids"] = sorted(
            {*row["check_ids"], str(check["check_id"])}
        )
        row["depends_on_owner_ids"] = sorted(
            {*row["depends_on_owner_ids"], *dependencies}
        )
    projections = [
        {
            "check_id": str(check["check_id"]),
            "semantic_check_id": str(check["semantic_check_id"]),
            "execution_owner_id": str(check["execution_owner_id"]),
            "covers_obligation_ids": sorted(
                str(value) for value in check.get("covers_obligation_ids", [])
            ),
            "evidence_class": str(check.get("evidence_class", "")),
            "projection_declaration_hash": str(
                check["projection_declaration_hash"]
            ),
        }
        for check in checks
    ]
    plan: dict[str, object] = {
        "schema_version": "skillguard.content_impact_plan.current",
        "policy_id": "skillguard.content_impact_policy.current",
        "member_root_path": ".",
        "owner_receipt_root_ref": {
            "path_token": "owner_evidence_root",
            "relative_path": "check-executions",
        },
        "unknown_mapping_disposition": "block",
        "full_admission_reason_codes": [
            "explicit_final_gate",
            "explicit_release_gate",
            "impact_policy_or_compiler_changed",
            "shared_validation_runtime_changed",
            "all_owner_component_changed",
        ],
        "inventory": [],
        "inventory_hash": wire_hash([]),
        "components": [],
        "owners": sorted(
            owner_rows.values(), key=lambda row: str(row["execution_owner_id"])
        ),
        "check_projections": projections,
        "projection_consumers": [],
        "portfolio_target_edges": [],
        "all_owner_component_ids": [],
        "health": {
            "unmapped_paths": [],
            "ambiguous_role_paths": [],
            "duplicate_owner_ids": [],
            "owner_cycles": [],
            "invalid_dependency_edges": [],
            "dependency_parse_errors": [],
        },
    }
    plan["impact_graph_hash"] = wire_hash(
        {
            "policy_id": plan["policy_id"],
            "member_root_path": plan["member_root_path"],
            "inventory_hash": plan["inventory_hash"],
            "components": plan["components"],
            "owners": plan["owners"],
            "check_projections": plan["check_projections"],
            "projection_consumers": plan["projection_consumers"],
            "portfolio_target_edges": plan["portfolio_target_edges"],
            "health": plan["health"],
        }
    )
    return checks, plan


def runtime_checks() -> list[dict[str, object]]:
    return [
        {
            "check_id": check_id,
            "semantic_check_id": check_id,
            "kind": "command",
            "command": sys.executable,
            "args": ["-c", "raise SystemExit(0)"],
            "cwd_token": "target_root",
            "timeout_seconds": 5,
            "expected": {"exit_code": 0},
            "covers_obligation_ids": [obligation_id],
        }
        for check_id, obligation_id in (
            ("check:intake", "obligation:intake"),
            ("check:review", "obligation:review"),
            ("check:finish", "obligation:finish"),
            ("check:release", "obligation:release"),
        )
    ]


def runtime_contract() -> dict[str, object]:
    checks, content_impact_plan = _current_checks_and_plan(runtime_checks())
    contract: dict[str, object] = {
        "schema_version": "skillguard.compiled_contract.v2",
        "compiler_version": "fixture",
        "skill_id": "runtime-fixture",
        "repository_role": "skill_maintainer_source",
        "maintenance_unit_id": "unit:runtime-fixture",
        "member_skill_ids": ["runtime-fixture"],
        "consumer_projection": {
            "projection_id": "projection:consumer-distribution",
            "prohibited_path_prefixes": [".skillguard/"],
            "prohibited_prompt_tokens": [
                "SkillGuard",
                ".skillguard",
                "skillguard.py",
            ],
            "release_manifest_path": "consumer-release.json",
        },
        "model_id": "runtime-fixture-model",
        "parent_model_id": "fixture-parent",
        "flowguard_schema_version": "1.0",
        "model_path": ".flowguard/runtime_fixture.py",
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
        "portfolio_capability_contracts": [],
        "closure_profiles": [
            {
                "profile_id": "enforced",
                "required_obligation_ids": [
                    "obligation:intake",
                    "obligation:review",
                    "obligation:finish",
                    "obligation:release",
                    "obligation:quality",
                ],
            }
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
        "checks": checks,
        "content_impact_plan": content_impact_plan,
        "check_declarations_hash": canonical_hash({"checks": checks}),
        "claim_boundary": "Runtime fixture only.",
    }
    contract["contract_hash"] = canonical_hash(contract)
    return contract


def runtime_check_manifest(
    contract: dict[str, object],
    checks: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    checks, content_impact_plan = _current_checks_and_plan(
        copy.deepcopy(checks if checks is not None else runtime_checks())
    )
    manifest: dict[str, object] = {
        "schema_version": "skillguard.check_manifest.v2",
        "compiler_version": "fixture",
        "skill_id": contract["skill_id"],
        "maintenance_unit_id": contract["maintenance_unit_id"],
        "member_skill_ids": contract["member_skill_ids"],
        "consumer_projection": contract["consumer_projection"],
        "model_id": contract["model_id"],
        "contract_hash": contract["contract_hash"],
        "check_declarations_hash": contract["check_declarations_hash"],
        "checks": checks,
        "content_impact_plan": content_impact_plan,
        "source_fingerprints": {},
        "claim_boundary": "Runtime fixture check manifest only.",
    }
    manifest["manifest_hash"] = canonical_hash(manifest)
    return manifest


def runtime_contract_with_checks(
    checks: list[dict[str, object]],
) -> tuple[dict[str, object], dict[str, object]]:
    checks, content_impact_plan = _current_checks_and_plan(checks)
    contract = runtime_contract()
    contract["checks"] = checks
    contract["content_impact_plan"] = content_impact_plan
    contract["check_declarations_hash"] = canonical_hash({"checks": checks})
    contract["contract_hash"] = canonical_hash(
        {key: value for key, value in contract.items() if key != "contract_hash"}
    )
    return contract, runtime_check_manifest(contract, checks)


def copied_contract() -> dict[str, object]:
    return copy.deepcopy(runtime_contract())
