"""Executable FieldLifecycle inventory for the SkillGuard V1-to-V2 boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .contract_compiler import file_hash


V1_RUNTIME_SCHEMAS = {
    "skillguard.work_contract.v1": "skillguard_work_contract.schema.json",
    "skillguard.run_record.v1": "skillguard_run_record.schema.json",
    "skillguard.check_manifest.v1": "skillguard_check_manifest.schema.json",
}

WORK_CONTRACT_REPLACEMENTS = {
    "acceptance_obligations": "obligations plus exact check coverage",
    "check_scripts": "checks with command bindings",
    "claim_boundary": "compiled contract claim_boundary",
    "cleanup_required": "lifecycle and release blockers",
    "closure_blockers": "closure profile gaps and failed receipts",
    "closure_rules": "monotonic closure_profiles",
    "contract_hash": "compiled contract_hash",
    "contract_version": "V2 schema_version plus contract_hash",
    "coverage_matrix": "obligations, owner steps, and check manifest coverage",
    "forbidden_shortcuts": "model invariants and negative cases",
    "integration_claim_boundary": "binding claim_boundary",
    "integration_mode": "canonical owner/action bindings",
    "may_define_parallel_execution_route": "declared route composition policy",
    "may_define_skillguard_runtime_route": "canonical primary-path ownership",
    "native_check_bindings": "checks",
    "native_check_inventory": "checks",
    "native_route_bindings": "functions and routes",
    "native_route_owner": "function and step owner_id",
    "not_parallel_route_proof": "canonical owner plus route compatibility",
    "phase_native_bindings": "step bindings",
    "phases": "steps and prerequisite_step_ids",
    "quality_floors": "judgment rubrics and closure profiles",
    "required_evidence": "artifact declarations and evidence policy",
    "route_inventory": "functions and routes",
    "routes": "functions and routes",
    "run_record_required": "claimed-run requirement",
    "runtime_lock_policy": "claim-run and replay invariants",
    "schema_version": "skillguard.compiled_contract.v2",
    "skill_id": "skill_id",
    "skill_specific_checks": "exact check coverage",
    "skillguard_role": "canonical owner/action bindings",
    "source_requirements": "model obligations and source fingerprints",
    "stale_bindings": "source and Guard runtime fingerprints",
    "target_path": "target-local run root and request write_targets",
    "target_rule_inventory": "model obligations",
    "test_gap_plan": "ContractExhaustion and TestMesh cases",
    "workflow_stage_inventory": "steps and routes",
}

RUN_RECORD_REPLACEMENTS = {
    "blockers": "failed/blocked run events and closure gaps",
    "claim_boundary": "run and closure claim_boundary",
    "closure_decision": "immutable closure receipt",
    "commands_run": "stored check records and evidence receipts",
    "contract_ref": "immutable contract snapshot and contract fingerprint",
    "current_phase": "replayed state and next-ready-step derivation",
    "evidence": "immutable evidence receipts",
    "phase_statuses": "append-only step events",
    "quality_failures": "judged evidence and closure uncertainty",
    "run_id": "claimed V2 run_id",
    "schema_version": "skillguard.run.v2 plus skillguard.run_event.v2",
    "selected_route": "selected route_ids",
    "skipped_checks": "verifier-approved conditional skip protocol",
    "target_skill": "contract skill_id plus target-local run root",
    "task_summary": "fingerprinted request packet",
}

CHECK_MANIFEST_REPLACEMENTS = {
    "checks": "exact V2 check manifest checks",
    "claim_boundary": "check manifest claim_boundary",
    "contract_ref": "contract_hash",
    "freshness": "source, implementation, environment, and Guard runtime fingerprints",
    "output_schema": "skillguard.check_manifest.v2",
    "schema_version": "skillguard.check_manifest.v2",
    "target_skill": "skill_id",
}

SCHEMA_REPLACEMENTS = {
    "skillguard.work_contract.v1": WORK_CONTRACT_REPLACEMENTS,
    "skillguard.run_record.v1": RUN_RECORD_REPLACEMENTS,
    "skillguard.check_manifest.v1": CHECK_MANIFEST_REPLACEMENTS,
}

ARTIFACT_DISPOSITIONS = {
    ".skillguard/work-contract.json": "migration_input_only_when_v2_absent",
    ".skillguard/check_manifest.json": "migration_input_only_when_v2_absent",
    ".skillguard/runs/*.json (skillguard.run_record.v1)": "legacy_read_only_never_v2_closure",
    ".skillguard/checks/* V1 stubs": "preserved_only_for_unmigrated_runtime_targets",
    "skillguard.closure.v1": "bounded_report_record_never_v2_closure",
}

COMMAND_DISPOSITIONS = {
    "compile-contract": "legacy_generation_only_blocked_when_v2_authority_present",
    "select-route": "legacy_runtime_only_blocked_when_v2_authority_present",
    "start-run": "legacy_runtime_only_blocked_when_v2_authority_present",
    "advance-run": "legacy_runtime_only_blocked_when_v2_authority_present",
    "check-run": "legacy_runtime_only_blocked_when_v2_authority_present",
    "close-run": "legacy_runtime_only_blocked_when_v2_authority_present",
    "check-contract": "legacy_read_only_diagnostic",
    "check-work-contract": "legacy_read_only_diagnostic",
    "check-run-record": "legacy_read_only_diagnostic",
    "check-check-manifest": "legacy_read_only_diagnostic",
    "make-closure": "bounded_report_utility_not_v2_closure_authority",
}

V1_RUNTIME_AUTHORITY_COMMANDS = frozenset(
    {command for command, disposition in COMMAND_DISPOSITIONS.items() if "blocked_when_v2_authority_present" in disposition}
)


def _property_rows(schema: Mapping[str, Any], prefix: str = "$") -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    properties = schema.get("properties", {})
    if not isinstance(properties, Mapping):
        return rows
    for name in sorted(str(item) for item in properties):
        declaration = properties.get(name, {})
        path = f"{prefix}.{name}"
        rows.append((path, "container" if isinstance(declaration, Mapping) and ("properties" in declaration or "items" in declaration) else "leaf"))
        if isinstance(declaration, Mapping):
            rows.extend(_property_rows(declaration, path))
            items = declaration.get("items", {})
            if isinstance(items, Mapping):
                rows.extend(_property_rows(items, f"{path}[]"))
    return rows


def _root_field(path: str) -> str:
    return path.removeprefix("$.").split(".", 1)[0].removesuffix("[]")


def build_v1_field_lifecycle_plan(skill_root: Path) -> dict[str, Any]:
    skill_root = skill_root.resolve()
    schema_root = skill_root / "assets" / "schemas"
    field_rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    schema_evidence: list[dict[str, str]] = []
    for schema_id, filename in V1_RUNTIME_SCHEMAS.items():
        path = schema_root / filename
        payload = json.loads(path.read_text(encoding="utf-8"))
        replacements = SCHEMA_REPLACEMENTS[schema_id]
        schema_evidence.append({"schema_id": schema_id, "path": f"assets/schemas/{filename}", "sha256": file_hash(path)})
        for field_path, role in _property_rows(payload):
            root_field = _root_field(field_path)
            replacement = replacements.get(root_field)
            disposition = "migrated_to_v2" if replacement else "unknown"
            if replacement is None:
                blockers.append(f"unaccounted_field:{schema_id}:{field_path}")
            field_rows.append(
                {
                    "field_id": f"{schema_id}:{field_path}",
                    "parent_group": schema_id,
                    "field_path": field_path,
                    "role": role,
                    "lifecycle": "legacy_v1_runtime",
                    "disposition": disposition,
                    "replacement": replacement or "",
                    "owner_route": "skillguard-v2-runtime",
                    "reader_writer_boundary": "V1 checker_engine reads/writes only while V2 contract-source authority is absent",
                }
            )
    return {
        "artifact_type": "skillguard_v1_field_lifecycle_plan",
        "status": "blocked" if blockers else "passed",
        "field_boundary": "The three V1 runtime-authority schemas, their artifacts, and their public command surfaces.",
        "field_rows": field_rows,
        "field_row_count": len(field_rows),
        "projections": [
            {
                "projection_id": "projection:v2-authority-wins",
                "source_fields": ["V1 runtime schema fields and authority commands"],
                "behavior": "When contract-source.json exists, V1 runtime authority commands block and cannot issue success.",
                "owner": "skillguard.py facade plus SkillGuard V2 runtime",
            },
            {
                "projection_id": "projection:legacy-diagnostics-remain-bounded",
                "source_fields": ["V1 validators and skillguard.closure.v1"],
                "behavior": "Legacy validators remain read-only migration diagnostics and never satisfy V2 closure.",
                "owner": "checker_engine legacy diagnostic surface",
            },
        ],
        "artifact_dispositions": ARTIFACT_DISPOSITIONS,
        "command_dispositions": COMMAND_DISPOSITIONS,
        "evidence": schema_evidence,
        "failures": [],
        "blockers": blockers,
        "skipped_checks": [
            {
                "check_id": "flowguard:project-audit-0.54",
                "reason": "FlowGuard project adoption requires an unrelated canonical suite map for this repository.",
                "impact": "No broad FlowGuard project-adoption claim; bounded executable FieldLifecycle inventory still runs.",
            }
        ],
        "residual_risk": [
            "Unmigrated target skills may continue using V1 runtime artifacts until their one-at-a-time V2 graduation.",
            "Current non-runtime schemas whose identifiers end in .v1 remain supported APIs and are not evidence of legacy status by name alone.",
        ],
        "claim_boundary": "This plan accounts for V1 runtime authority fields, artifacts, and commands. It does not retire unrelated current schemas merely because their stable identifier ends in .v1.",
        "typed_next_actions": [
            "Block V1 runtime-authority commands whenever V2 semantic authority exists.",
            "Keep legacy validators diagnostic-only during portfolio migration.",
            "Delete each target's V1 runtime artifacts only after that target has current V2 closure and rollback evidence.",
        ],
    }
