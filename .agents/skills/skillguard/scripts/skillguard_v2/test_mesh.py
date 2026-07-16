"""Executable parent/child test mesh with current result artifacts."""

from __future__ import annotations

import json
import hashlib
import io
import os
import re
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contract_compiler import (
    canonical_json_bytes,
    wire_hash,
)
from .check_runner import (
    CheckRunnerError,
    check_toolchain_identity,
    get_or_execute_check,
    inspect_current_owner_execution,
    inspect_current_owner_input_projection,
    inspect_owner_receipt_history,
    load_owner_receipt_from_ref,
    owner_receipt_document_ref,
    resolve_owner_evidence_root,
)
from .execution_records import (
    ExecutionRecordError,
    durable_copy_immutable_stream,
    durable_write_immutable_json,
    filesystem_path,
)
from .installation_receipt import (
    VerifiedInstallationContext,
    load_verified_installation_context,
    resolve_codex_home_root,
    validate_verified_installation_context,
)
from .installation import compare_installation_projection_member
from .content_projection import (
    MARKDOWN_CHECKBOX_STATE_POLICY_ID,
    normalize_markdown_task_checkbox_state,
)
from .run_store import (
    load_check_manifest_snapshot,
    load_contract_snapshot,
    load_run,
)
from .path_identity import canonical_filesystem_path, physical_relative_path


CURRENT_TEST_MESH_MANIFEST_SCHEMA = "skillguard.test_mesh_manifest.current"
CURRENT_TEST_MESH_PLAN_SCHEMA = "skillguard.test_mesh_execution_plan.current"
CURRENT_TEST_MESH_OWNER_EXECUTION_SCHEMA = (
    "skillguard.test_mesh_owner_execution.current"
)
CURRENT_TEST_MESH_AGGREGATION_SCHEMA = "skillguard.test_mesh_aggregation.current"
CURRENT_TEST_MESH_REPLAY_SCHEMA = "skillguard.test_mesh_replay.current"
CURRENT_OPENSPEC_PROJECTION_SCHEMA = (
    "skillguard.openspec_receipt_projection.current"
)
CURRENT_OPENSPEC_PROJECTION_RESULT_SCHEMA = (
    "skillguard.openspec_receipt_projection_result.current"
)
PORTABLE_RECEIPT_REF_SCHEMA = "portable-receipt-ref.v1"
PORTABLE_RECEIPT_ENVELOPE_SCHEMA = "portable-receipt-envelope.v1"
PORTABLE_SOURCE_MANIFEST_SCHEMA = "portable-source-manifest.v1"
PORTABLE_RECEIPT_PROTOCOL = 1
PORTABLE_RECEIPT_ROOT_TOKEN = "<SPEC_EVIDENCE>"
PORTABLE_SOURCE_HASH_POLICY = {
    "version": 2,
    "algorithm": "sha256",
    "task_checkbox_normalization": MARKDOWN_CHECKBOX_STATE_POLICY_ID,
    "output_classifier_version": "verification-generated-output-v2",
}
TEST_MESH_INSTALLATION_BINDING_SCHEMA = (
    "skillguard.test_mesh_typed_domain_binding.current"
)
TEST_MESH_TYPED_DOMAIN_BINDING_SCHEMA = (
    "skillguard.test_mesh_typed_domain_binding.current"
)
GLOBAL_PROMPT_DOMAIN_ID = "global_prompt"
CANONICAL_SKILL_ROOT_RELATIVE_PATH = Path(".agents/skills/skillguard")
INSTALLATION_BINDING_FIELDS = (
    "schema_version",
    "evidence_domain",
    "owner_id",
    "installation_receipt_root_ref",
    "member_projection_hash",
    "content_consumer_projection_hash",
    "installed_smoke_result_hash",
    "installed_smoke_contract_hash",
    "owner_receipt_projection_hash",
    "binding_hash",
)
GLOBAL_PROMPT_BINDING_FIELDS = (
    "schema_version",
    "evidence_domain",
    "owner_id",
    "registry_ref",
    "projection_ref",
    "prompt_ref",
    "registry_hash",
    "managed_prompt_block_hash",
    "prompt_projection_identity_hash",
    "content_consumer_projection_hash",
    "binding_hash",
)


























































def _portable_relative_path(value: object) -> Path | None:
    text = str(value or "").replace("\\", "/")
    if (
        not text
        or text.startswith("/")
        or re.match(r"^[A-Za-z]:/", text)
        or text.startswith("//")
    ):
        return None
    relative = Path(text)
    if any(part in {"", ".", ".."} for part in relative.parts):
        return None
    return relative




def _load_global_prompt_currentness_binding(
    *, codex_home: Path | None = None
) -> dict[str, Any]:
    """Validate, but never refresh, the global registry and prompt projection."""

    from checker_engine import (
        build_global_prompt_projection,
        check_global_prompt_text,
        global_public_path,
        global_registry_current_route_failures,
        global_registry_integrity_failures,
    )
    from skillguard_v2.global_router_projection import (
        prompt_projection_integrity_failures,
    )

    try:
        home = resolve_codex_home_root(codex_home)
    except OSError:
        raise ExecutionRecordError("global_prompt_codex_home_not_current") from None
    registry_relative = Path(".skillguard/global-router/global_registry.json")
    projection_relative = Path(
        ".skillguard/global-router/global_prompt_projection.json"
    )
    prompt_relative = Path("AGENTS.md")
    registry_path = home / registry_relative
    projection_path = home / projection_relative
    prompt_path = home / prompt_relative
    if (
        registry_path.is_symlink()
        or projection_path.is_symlink()
        or prompt_path.is_symlink()
        or not registry_path.is_file()
        or not projection_path.is_file()
        or not prompt_path.is_file()
    ):
        raise ExecutionRecordError("global_prompt_currentness_input_missing")
    try:
        registry_value = json.loads(
            filesystem_path(registry_path).read_text(encoding="utf-8")
        )
        stored_projection_value = json.loads(
            filesystem_path(projection_path).read_text(encoding="utf-8")
        )
        prompt_text = filesystem_path(prompt_path).read_text(encoding="utf-8")
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExecutionRecordError(
            f"global_prompt_currentness_input_unreadable:{type(exc).__name__}"
        ) from None
    if not isinstance(registry_value, Mapping):
        raise ExecutionRecordError("global_prompt_registry_not_object")
    registry = dict(registry_value)
    if not isinstance(stored_projection_value, Mapping):
        raise ExecutionRecordError(
            "global_prompt_projection_not_object"
        )
    stored_projection = dict(stored_projection_value)
    stored_projection_failures = prompt_projection_integrity_failures(
        stored_projection
    )
    if stored_projection_failures:
        raise ExecutionRecordError(
            "global_prompt_projection_shape_or_hash_invalid:"
            + ",".join(sorted(stored_projection_failures))
        )
    integrity_failures = global_registry_integrity_failures(registry)
    if integrity_failures:
        raise ExecutionRecordError(
            "global_prompt_registry_shape_or_hash_invalid:"
            + ",".join(sorted(integrity_failures))
        )
    route_failures, route_blockers = global_registry_current_route_failures(
        registry, codex_home=str(home)
    )
    if route_failures or route_blockers:
        raise ExecutionRecordError(
            "global_prompt_registry_stale:"
            + ",".join(sorted([*route_failures, *route_blockers]))
        )
    try:
        current_projection = build_global_prompt_projection(
            registry, global_public_path(registry_path)
        )
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise ExecutionRecordError(
            f"global_prompt_projection_unavailable:{exc}"
        ) from None
    projection_mismatch_fields = [
        field
        for field in (
            "registry_hash",
            "managed_block_content_hash",
            "projection_identity_hash",
            "template_content_hash",
        )
        if stored_projection.get(field) != current_projection.get(field)
    ]
    stored_content_projection = stored_projection.get("content_projection")
    current_content_projection_value = current_projection.get(
        "content_projection"
    )
    if (
        not isinstance(stored_content_projection, Mapping)
        or not isinstance(current_content_projection_value, Mapping)
        or stored_content_projection.get("consumer_projection_hash")
        != current_content_projection_value.get("consumer_projection_hash")
    ):
        projection_mismatch_fields.append(
            "content_consumer_projection_hash"
        )
    if projection_mismatch_fields:
        raise ExecutionRecordError(
            "global_prompt_projection_stale:"
            + ",".join(sorted(set(projection_mismatch_fields)))
        )
    projection = stored_projection
    managed_block = str(projection.get("managed_block") or "")
    prompt_failures, prompt_blockers = check_global_prompt_text(
        prompt_text,
        str(registry.get("registry_hash") or ""),
        managed_block,
    )
    if prompt_failures or prompt_blockers:
        raise ExecutionRecordError(
            "global_prompt_managed_block_stale:"
            + ",".join(sorted([*prompt_failures, *prompt_blockers]))
        )
    content_projection = projection.get("content_projection")
    if not isinstance(content_projection, Mapping):
        raise ExecutionRecordError(
            "global_prompt_content_projection_missing"
        )
    content_projection_hash = str(
        content_projection.get("consumer_projection_hash") or ""
    )
    for field, value in (
        ("registry_hash", registry.get("registry_hash")),
        (
            "managed_prompt_block_hash",
            projection.get("managed_block_content_hash"),
        ),
        (
            "prompt_projection_identity_hash",
            projection.get("projection_identity_hash"),
        ),
        ("content_consumer_projection_hash", content_projection_hash),
    ):
        if re.fullmatch(r"sha256:[0-9a-f]{64}", str(value or "")) is None:
            raise ExecutionRecordError(
                f"global_prompt_binding_{field}_invalid"
            )
    binding: dict[str, Any] = {
        "schema_version": TEST_MESH_TYPED_DOMAIN_BINDING_SCHEMA,
        "evidence_domain": GLOBAL_PROMPT_DOMAIN_ID,
        "owner_id": "skillguard-global-router",
        "registry_ref": {
            "path_token": "codex_home",
            "relative_path": registry_relative.as_posix(),
        },
        "projection_ref": {
            "path_token": "codex_home",
            "relative_path": projection_relative.as_posix(),
        },
        "prompt_ref": {
            "path_token": "codex_home",
            "relative_path": prompt_relative.as_posix(),
        },
        "registry_hash": str(registry["registry_hash"]),
        "managed_prompt_block_hash": str(
            projection["managed_block_content_hash"]
        ),
        "prompt_projection_identity_hash": str(
            projection["projection_identity_hash"]
        ),
        "content_consumer_projection_hash": content_projection_hash,
    }
    binding["binding_hash"] = wire_hash(binding)
    return binding


def _replay_global_prompt_currentness_binding(
    value: object, *, codex_home: Path | None = None
) -> list[str]:
    if not isinstance(value, list) or len(value) != 1:
        return ["global_prompt_typed_domain_binding_missing_or_duplicated"]
    binding = value[0]
    if not isinstance(binding, Mapping):
        return ["global_prompt_typed_domain_binding_not_object"]
    if set(binding) != set(GLOBAL_PROMPT_BINDING_FIELDS):
        return ["global_prompt_typed_domain_binding_shape_invalid"]
    unsigned = dict(binding)
    unsigned.pop("binding_hash", None)
    if (
        binding.get("schema_version") != TEST_MESH_TYPED_DOMAIN_BINDING_SCHEMA
        or binding.get("evidence_domain") != GLOBAL_PROMPT_DOMAIN_ID
        or binding.get("owner_id") != "skillguard-global-router"
        or binding.get("binding_hash") != wire_hash(unsigned)
    ):
        return ["global_prompt_typed_domain_binding_hash_invalid"]
    try:
        current = _load_global_prompt_currentness_binding(codex_home=codex_home)
    except ExecutionRecordError as exc:
        return [f"global_prompt_currentness_replay_failed:{exc}"]
    return [
        f"global_prompt_currentness_mismatch:{field}"
        for field in GLOBAL_PROMPT_BINDING_FIELDS
        if binding.get(field) != current.get(field)
    ]


def _load_current_installation_binding(
    repository_root: Path,
    installation_receipt_root: Path,
    *,
    canonical_skillguard_root: Path | None = None,
    verified_installation_context: VerifiedInstallationContext | None = None,
) -> dict[str, Any]:
    """Verify and normalize one current installation receipt for TestMesh."""

    repository_root = canonical_filesystem_path(repository_root)
    try:
        codex_home = resolve_codex_home_root()
    except OSError:
        raise ExecutionRecordError("codex_home_not_current") from None
    try:
        receipt_root = canonical_filesystem_path(installation_receipt_root)
        receipt_root_relative = physical_relative_path(receipt_root, codex_home)
    except (OSError, ValueError):
        raise ExecutionRecordError("installation_receipt_root_not_portable") from None
    expected_relative = Path(
        "skills/skillguard/.sg-runtime/installation"
    )
    if (
        not receipt_root.is_dir()
        or receipt_root_relative != expected_relative
    ):
        raise ExecutionRecordError("installation_receipt_root_not_portable")

    canonical_skill_root = (
        canonical_skillguard_root.resolve()
        if canonical_skillguard_root is not None
        else (repository_root / CANONICAL_SKILL_ROOT_RELATIVE_PATH).resolve()
    )
    try:
        verified_context = (
            validate_verified_installation_context(
                verified_installation_context,
                expected_receipt_root=receipt_root,
            )
            if verified_installation_context is not None
            else load_verified_installation_context(
                receipt_root,
                canonical_skill_root=canonical_skill_root,
                codex_home=codex_home,
            )
        )
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ExecutionRecordError(
            f"installation_receipt_verification_failed:{type(exc).__name__}"
        ) from None
    receipt = verified_context.receipt
    current = verified_context.current_snapshot
    member_rows: list[dict[str, str]] = []
    for member_id, canonical_member, installed_member in (
        (
            "skillguard",
            canonical_skill_root,
            codex_home / "skills" / "skillguard",
        ),
        (
            "skillguard-global-router",
            canonical_skill_root.parent / "skillguard-global-router",
            codex_home / "skills" / "skillguard-global-router",
        ),
    ):
        try:
            comparison = compare_installation_projection_member(
                canonical_member,
                installed_member,
            )
        except (OSError, UnicodeError, ValueError) as exc:
            raise ExecutionRecordError(
                f"installation_projection_replay_failed:{member_id}:{type(exc).__name__}"
            ) from None
        canonical_projection = comparison.get(
            "canonical_installation_projection"
        )
        installed_projection = comparison.get(
            "installed_installation_projection"
        )
        if (
            comparison.get("status") != "current"
            or not isinstance(canonical_projection, Mapping)
            or canonical_projection != installed_projection
        ):
            raise ExecutionRecordError(
                f"installation_projection_not_current:{member_id}"
            )
        member_rows.append(
            {
                "member_skill_id": member_id,
                "installation_projection_identity_hash": str(
                    canonical_projection.get("identity_hash", "")
                ),
                "consumer_projection_hash": str(
                    canonical_projection.get("consumer_projection_hash", "")
                ),
            }
        )
    member_projection_hash = wire_hash(member_rows)
    content_consumer_projection_hash = wire_hash(
        [
            {
                "member_skill_id": row["member_skill_id"],
                "consumer_projection_hash": row["consumer_projection_hash"],
            }
            for row in member_rows
        ]
    )
    installed_smoke_result_hash = wire_hash(
        {"semantic_result_hash": current["current_installed_smoke_hash"]}
    )
    installed_smoke_contract_hash = wire_hash(
        {
            "command_fingerprint": current[
                "current_installed_smoke_command_fingerprint"
            ],
            "environment_fingerprint": current[
                "current_installed_smoke_environment_fingerprint"
            ],
        }
    )
    owner_receipt_projection_hash = wire_hash(
        {
            "member_projection_hash": member_projection_hash,
            "content_consumer_projection_hash": content_consumer_projection_hash,
            "installed_smoke_result_hash": installed_smoke_result_hash,
            "installed_smoke_contract_hash": installed_smoke_contract_hash,
        }
    )
    binding: dict[str, Any] = {
        "schema_version": TEST_MESH_INSTALLATION_BINDING_SCHEMA,
        "evidence_domain": "active_installation",
        "owner_id": "skillguard-installation",
        "installation_receipt_root_ref": {
            "path_token": "codex_home",
            "relative_path": receipt_root_relative.as_posix(),
        },
        "member_projection_hash": member_projection_hash,
        "content_consumer_projection_hash": content_consumer_projection_hash,
        "installed_smoke_result_hash": installed_smoke_result_hash,
        "installed_smoke_contract_hash": installed_smoke_contract_hash,
        "owner_receipt_projection_hash": owner_receipt_projection_hash,
    }
    binding["binding_hash"] = wire_hash(binding)
    return binding


def _replay_installation_binding(
    repository_root: Path,
    value: object,
    *,
    canonical_skillguard_root: Path | None = None,
    verified_installation_context: VerifiedInstallationContext | None = None,
) -> list[str]:
    if not isinstance(value, Mapping):
        return ["installation_identity_missing"]
    binding = dict(value)
    if set(binding) != set(INSTALLATION_BINDING_FIELDS):
        return ["installation_identity_shape_invalid"]
    unsigned = dict(binding)
    unsigned.pop("binding_hash", None)
    if (
        binding.get("schema_version") != TEST_MESH_INSTALLATION_BINDING_SCHEMA
        or binding.get("evidence_domain") != "active_installation"
        or binding.get("owner_id") != "skillguard-installation"
        or binding.get("binding_hash") != wire_hash(unsigned)
    ):
        return ["installation_identity_hash_mismatch"]
    locator = binding.get("installation_receipt_root_ref")
    relative = None
    if isinstance(locator, Mapping) and locator.get("path_token") == "codex_home":
        relative = _portable_relative_path(locator.get("relative_path"))
    if relative is None:
        return ["installation_receipt_root_ref_invalid"]
    try:
        codex_home = resolve_codex_home_root()
        current = _load_current_installation_binding(
            repository_root,
            codex_home / relative,
            canonical_skillguard_root=canonical_skillguard_root,
            verified_installation_context=verified_installation_context,
        )
    except (ExecutionRecordError, OSError) as exc:
        return [f"installation_currentness_replay_failed:{exc}"]
    mismatches = [
        f"installation_identity_current_mismatch:{field}"
        for field in INSTALLATION_BINDING_FIELDS
        if binding.get(field) != current.get(field)
    ]
    return mismatches


def _load_current_test_mesh_manifest(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(
            filesystem_path(path).read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("current_test_mesh_manifest_unreadable") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("current_test_mesh_manifest_object_required")
    if set(payload) != {
        "schema_version",
        "mesh_id",
        "source_model_id",
        "profiles",
        "claim_boundary",
    }:
        raise ValueError("current_test_mesh_manifest_field_set_invalid")
    if payload.get("schema_version") != CURRENT_TEST_MESH_MANIFEST_SCHEMA:
        raise ValueError("legacy_test_mesh_manifest_rejected")
    profiles = payload.get("profiles")
    if not isinstance(profiles, list) or not profiles:
        raise ValueError("current_test_mesh_profiles_missing")
    seen: set[str] = set()
    for row in profiles:
        if not isinstance(row, Mapping) or set(row) != {
            "profile_id",
            "closure_profile_id",
            "full_admission_required",
        }:
            raise ValueError("current_test_mesh_profile_shape_invalid")
        profile_id = str(row.get("profile_id", ""))
        closure_profile_id = str(row.get("closure_profile_id", ""))
        if (
            not profile_id
            or not closure_profile_id
            or profile_id in seen
            or not isinstance(row.get("full_admission_required"), bool)
        ):
            raise ValueError("current_test_mesh_profile_invalid")
        seen.add(profile_id)
    return payload


def _selected_owner_rows(
    contract: Mapping[str, Any],
    mesh_manifest: Mapping[str, Any],
    profile_id: str,
) -> tuple[Mapping[str, Any], list[Mapping[str, Any]]]:
    profile = next(
        (
            row
            for row in mesh_manifest.get("profiles", [])
            if isinstance(row, Mapping) and row.get("profile_id") == profile_id
        ),
        None,
    )
    if profile is None:
        raise ValueError(f"current_test_mesh_profile_unknown:{profile_id}")
    closure_profile_id = str(profile["closure_profile_id"])
    closure_profile = next(
        (
            row
            for row in contract.get("closure_profiles", [])
            if isinstance(row, Mapping)
            and row.get("profile_id") == closure_profile_id
        ),
        None,
    )
    if closure_profile is None:
        raise ValueError(
            f"current_test_mesh_closure_profile_unknown:{closure_profile_id}"
        )
    obligation_index = {
        str(row.get("obligation_id", "")): row
        for row in contract.get("obligations", [])
        if isinstance(row, Mapping)
    }
    check_ids: set[str] = set()
    for obligation_id_value in closure_profile.get(
        "required_obligation_ids", []
    ):
        obligation_id = str(obligation_id_value)
        obligation = obligation_index.get(obligation_id)
        if obligation is None:
            raise ValueError(
                f"current_test_mesh_obligation_unknown:{obligation_id}"
            )
        check_ids.update(
            str(value) for value in obligation.get("required_check_ids", [])
        )
    plan = contract.get("content_impact_plan")
    if (
        not isinstance(plan, Mapping)
        or plan.get("schema_version")
        != "skillguard.content_impact_plan.current"
    ):
        raise ValueError("current_test_mesh_content_impact_plan_missing")
    health = plan.get("health")
    if not isinstance(health, Mapping) or any(health.get(key) for key in health):
        raise ValueError("current_test_mesh_content_impact_plan_unhealthy")
    owner_index = {
        str(row.get("execution_owner_id", "")): row
        for row in plan.get("owners", [])
        if isinstance(row, Mapping)
    }
    check_owner = {
        str(row.get("check_id", "")): str(row.get("execution_owner_id", ""))
        for row in contract.get("checks", [])
        if isinstance(row, Mapping)
    }
    selected = {
        check_owner[check_id]
        for check_id in check_ids
        if check_id in check_owner
    }
    pending = list(selected)
    while pending:
        owner_id = pending.pop()
        owner = owner_index.get(owner_id)
        if owner is None:
            raise ValueError(f"current_test_mesh_owner_unknown:{owner_id}")
        for dependency_value in owner.get("depends_on_owner_ids", []):
            dependency = str(dependency_value)
            if dependency not in selected:
                selected.add(dependency)
                pending.append(dependency)
    if not selected:
        raise ValueError("current_test_mesh_owner_selection_empty")
    return profile, [owner_index[owner_id] for owner_id in sorted(selected)]


def _exact_owner_check_projection(
    owner: Mapping[str, Any],
    owner_checks: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], list[str], list[dict[str, str]], dict[str, str]]:
    """Resolve one owner execution without dropping its semantic check projections."""

    owner_id = str(owner.get("execution_owner_id", ""))
    declared_check_ids = owner.get("check_ids")
    if (
        not isinstance(declared_check_ids, list)
        or not declared_check_ids
        or any(not isinstance(value, str) or not value for value in declared_check_ids)
        or declared_check_ids != sorted(set(declared_check_ids))
    ):
        raise ValueError(f"current_test_mesh_owner_check_ids_invalid:{owner_id}")
    check_index = {
        str(check.get("check_id", "")): check for check in owner_checks
    }
    if (
        len(check_index) != len(owner_checks)
        or "" in check_index
        or set(check_index) != set(declared_check_ids)
    ):
        raise ValueError(f"current_test_mesh_owner_check_projection_mismatch:{owner_id}")
    owner_declaration_hash = str(owner.get("owner_declaration_hash", ""))
    evidence_domain_id = str(owner.get("evidence_domain_id", ""))
    projections: list[dict[str, str]] = []
    toolchain: dict[str, str] | None = None
    for check_id in declared_check_ids:
        check = check_index[check_id]
        projection = {
            "check_id": check_id,
            "semantic_check_id": str(check.get("semantic_check_id", "")),
            "projection_declaration_hash": str(
                check.get("projection_declaration_hash", "")
            ),
        }
        if (
            check.get("execution_owner_id") != owner_id
            or check.get("owner_declaration_hash") != owner_declaration_hash
            or str(check.get("evidence_domain_id", "")) != evidence_domain_id
            or not projection["semantic_check_id"]
            or not re.fullmatch(
                r"sha256:[0-9a-f]{64}",
                projection["projection_declaration_hash"],
            )
        ):
            raise ValueError(
                f"current_test_mesh_owner_check_projection_invalid:{owner_id}:{check_id}"
            )
        current_toolchain = check_toolchain_identity(check)
        if toolchain is None:
            toolchain = dict(current_toolchain)
        elif toolchain != current_toolchain:
            raise ValueError(
                f"current_test_mesh_owner_check_toolchain_ambiguous:{owner_id}"
            )
        projections.append(projection)
    assert toolchain is not None
    return check_index[declared_check_ids[0]], list(declared_check_ids), projections, toolchain




def _current_plan_hash(report: Mapping[str, Any]) -> str:
    return wire_hash(
        {
            key: value
            for key, value in report.items()
            if key not in {"plan_hash", "claim_boundary"}
        }
    )


def _blocked_current_plan(
    profile_id: str, findings: Sequence[str]
) -> dict[str, Any]:
    return {
        "schema_version": CURRENT_TEST_MESH_PLAN_SCHEMA,
        "artifact_type": "skillguard_test_mesh_execution_plan",
        "status": "blocked",
        "mode": "plan_only",
        "profile_id": profile_id,
        "execution_count": 0,
        "selected_owner_ids": [],
        "changed_component_ids": [],
        "will_reuse_owner_ids": [],
        "will_execute_owner_ids": [],
        "will_aggregate_only": False,
        "required_install_component_ids": [],
        "required_router_refresh": False,
        "required_portfolio_target_ids": [],
        "full_required_reason_codes": [],
        "owner_plans": [],
        "findings": list(findings),
        "claim_boundary": (
            "Invalid or stale planning inputs launch no owner commands."
        ),
    }


def _topological_owner_rows(
    owners: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    pending = {
        str(row.get("execution_owner_id", "")): row for row in owners
    }
    if not pending or "" in pending:
        raise ValueError("current_test_mesh_owner_selection_invalid")
    ordered: list[Mapping[str, Any]] = []
    completed: set[str] = set()
    while pending:
        ready = sorted(
            owner_id
            for owner_id, row in pending.items()
            if set(str(value) for value in row.get("depends_on_owner_ids", []))
            <= completed
        )
        if not ready:
            raise ValueError("current_test_mesh_owner_cycle")
        for owner_id in ready:
            ordered.append(pending.pop(owner_id))
            completed.add(owner_id)
    return ordered


def _projection_component_ids(
    impact_plan: Mapping[str, Any], consumer_id: str
) -> set[str]:
    for row in impact_plan.get("projection_consumers", []):
        if (
            isinstance(row, Mapping)
            and row.get("consumer_id") == consumer_id
        ):
            return {
                str(value) for value in row.get("input_component_ids", [])
            }
    return set()


def _portfolio_targets_for_components(
    impact_plan: Mapping[str, Any], changed_component_ids: set[str]
) -> list[str]:
    """Project only explicitly declared target edges from changed components."""

    return sorted(
        str(row.get("target_id", ""))
        for row in impact_plan.get("portfolio_target_edges", [])
        if isinstance(row, Mapping)
        and str(row.get("target_id", ""))
        and changed_component_ids
        & {
            str(component_id)
            for component_id in row.get("input_component_ids", [])
        }
    )


def _component_changes_from_history(
    current_components: Sequence[Mapping[str, Any]],
    history: Sequence[Mapping[str, Any]],
) -> set[str]:
    current = {
        str(row.get("component_id", "")): str(
            row.get("component_hash", "")
        )
        for row in current_components
    }
    if not history:
        return set(current)
    candidates: list[tuple[int, tuple[str, ...]]] = []
    for receipt in history:
        previous = {
            str(row.get("component_id", "")): str(
                row.get("component_hash", "")
            )
            for row in receipt.get("input_components", [])
            if isinstance(row, Mapping)
        }
        changed = tuple(
            sorted(
                component_id
                for component_id in set(current) | set(previous)
                if current.get(component_id) != previous.get(component_id)
            )
        )
        candidates.append((len(changed), changed))
    return set(min(candidates)[1])


def _derived_full_admission_reasons(
    impact_plan: Mapping[str, Any],
    changed_component_ids: set[str],
    selected_owner_ids: set[str],
    explicit_reason: str,
) -> list[str]:
    reasons: set[str] = set()
    if explicit_reason in {"explicit_final_gate", "explicit_release_gate"}:
        reasons.add(explicit_reason)
    component_index = {
        str(row.get("component_id", "")): row
        for row in impact_plan.get("components", [])
        if isinstance(row, Mapping)
    }
    changed_paths = {
        str(path)
        for component_id in changed_component_ids
        for path in component_index.get(component_id, {}).get(
            "member_paths", []
        )
    }
    if any(
        Path(path).name
        in {
            "contract_compiler.py",
            "content_projection.py",
            "portable_content.py",
        }
        or path.endswith("/.skillguard/contract-source.json")
        for path in changed_paths
    ):
        reasons.add("impact_policy_or_compiler_changed")
    all_owner_components = {
        str(value)
        for value in impact_plan.get("all_owner_component_ids", [])
    }
    if changed_component_ids & all_owner_components:
        reasons.add("all_owner_component_changed")
    for component_id in changed_component_ids:
        component = component_index.get(component_id, {})
        consumers = {
            str(value)
            for value in component.get("consumer_ids", [])
            if str(value).startswith("owner:")
        }
        if (
            selected_owner_ids
            and selected_owner_ids <= consumers
            and component.get("role") == "runtime_source"
        ):
            reasons.add("shared_validation_runtime_changed")
    allowed = set(
        str(value)
        for value in impact_plan.get("full_admission_reason_codes", [])
    )
    return sorted(reasons & allowed)


def _compile_current_test_mesh_plan(
    manifest_path: Path,
    repository_root: Path,
    run_root: Path,
    profile_id: str,
    *,
    skill_root: Path,
    target_root: Path,
    owner_evidence_root: Path | None,
    full_admission_reason: str,
    freeze_identity: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Read the persistent receipt pool and freeze an exact zero-write plan."""

    try:
        mesh_manifest = _load_current_test_mesh_manifest(manifest_path)
        contract = load_contract_snapshot(run_root)
        check_manifest = load_check_manifest_snapshot(run_root)
        run = load_run(run_root)
        profile, selected_rows = _selected_owner_rows(
            contract, mesh_manifest, profile_id
        )
        owners = _topological_owner_rows(selected_rows)
    except (ValueError, OSError) as exc:
        return _blocked_current_plan(profile_id, [str(exc)])
    impact_plan = contract["content_impact_plan"]
    persistent_root = resolve_owner_evidence_root(
        repository_root, owner_evidence_root
    )
    checks_by_owner: dict[str, list[Mapping[str, Any]]] = {}
    for check in check_manifest.get("checks", []):
        if isinstance(check, Mapping):
            checks_by_owner.setdefault(
                str(check.get("execution_owner_id", "")), []
            ).append(check)

    reusable_receipts: dict[str, Mapping[str, Any]] = {}
    owner_plans: list[dict[str, Any]] = []
    reusable: list[str] = []
    execute: list[str] = []
    changed_components: set[str] = set()
    toolchain_rows: list[dict[str, str]] = []
    try:
        for owner in owners:
            owner_id = str(owner["execution_owner_id"])
            owner_checks = sorted(
                checks_by_owner.get(owner_id, []),
                key=lambda row: str(row.get("check_id", "")),
            )
            check, check_ids, check_projections, toolchain = (
                _exact_owner_check_projection(owner, owner_checks)
            )
            current_input = inspect_current_owner_input_projection(
                repository_root=repository_root,
                content_impact_plan=impact_plan,
                owner=owner,
            )
            toolchain_rows.append(
                {"execution_owner_id": owner_id, **toolchain}
            )
            dependency_ids = [
                str(value)
                for value in owner.get("depends_on_owner_ids", [])
            ]
            missing_dependencies = [
                dependency_id
                for dependency_id in dependency_ids
                if dependency_id not in reusable_receipts
            ]
            inspection: Mapping[str, Any] | None = None
            if not missing_dependencies:
                inspection = inspect_current_owner_execution(
                    check,
                    skill_root=skill_root,
                    target_root=target_root,
                    repository_root=repository_root,
                    run_root=run_root,
                    owner_evidence_root=persistent_root,
                    dependency_execution_receipts={
                        dependency_id: reusable_receipts[dependency_id]
                        for dependency_id in dependency_ids
                    },
                )
            if (
                inspection is not None
                and inspection.get("disposition")
                == "reuse_owner_receipt"
                and isinstance(inspection.get("receipt"), Mapping)
            ):
                receipt = inspection["receipt"]
                reusable_receipts[owner_id] = receipt
                reusable.append(owner_id)
                decision = "reuse_owner_receipt"
                reason = "current_owner_receipt_exact"
                receipt_binding: Mapping[str, Any] | None = {
                    "receipt_id": str(receipt.get("receipt_id", "")),
                    "receipt_hash": str(receipt.get("receipt_hash", "")),
                    "receipt_ref": dict(owner_receipt_document_ref(receipt)),
                }
            else:
                execute.append(owner_id)
                decision = "execute_owner"
                reason = (
                    "dependency_owner_will_execute:"
                    + ",".join(missing_dependencies)
                    if missing_dependencies
                    else str(
                        inspection.get("reason", "current_owner_receipt_missing")
                        if inspection is not None
                        else "current_owner_receipt_missing"
                    )
                )
                receipt_binding = None
                history = inspect_owner_receipt_history(
                    persistent_root,
                    execution_owner_id=owner_id,
                    owner_declaration_hash=str(
                        owner.get("owner_declaration_hash", "")
                    ),
                )
                changed_components.update(
                    _component_changes_from_history(
                        current_input["components"], history
                    )
                )
            owner_plans.append(
                {
                    "execution_owner_id": owner_id,
                    "primary_check_id": str(check.get("check_id", "")),
                    "check_ids": check_ids,
                    "check_projections": check_projections,
                    "owner_declaration_hash": str(
                        owner.get("owner_declaration_hash", "")
                    ),
                    "owner_input_projection_hash": str(
                        current_input["owner_input_projection_hash"]
                    ),
                    "input_components": list(current_input["components"]),
                    "depends_on_owner_ids": dependency_ids,
                    "evidence_domain_id": str(
                        owner.get("evidence_domain_id", "")
                    ),
                    **toolchain,
                    "decision": decision,
                    "reason": reason,
                    "reusable_receipt": (
                        dict(receipt_binding)
                        if isinstance(receipt_binding, Mapping)
                        else None
                    ),
                }
            )
    except (CheckRunnerError, ValueError, OSError) as exc:
        return _blocked_current_plan(profile_id, [str(exc)])

    component_index = {
        str(row.get("component_id", "")): row
        for row in impact_plan.get("components", [])
        if isinstance(row, Mapping)
    }
    required_install_components = sorted(
        component_id
        for component_id in changed_components
        if component_index.get(component_id, {}).get("install_disposition")
        in {"copy", "generate"}
    )
    router_components = _projection_component_ids(
        impact_plan, "projection:global-router"
    )
    required_portfolio_target_ids = _portfolio_targets_for_components(
        impact_plan, changed_components
    )
    selected_owner_ids = [
        str(row["execution_owner_id"]) for row in owners
    ]
    source_identity_hash = str(impact_plan.get("inventory_hash", ""))
    toolchain_identity_hash = wire_hash(toolchain_rows)
    selection_declaration = {
        "mesh_id": str(mesh_manifest.get("mesh_id", "")),
        "profile_id": profile_id,
        "closure_profile_id": str(profile.get("closure_profile_id", "")),
        "execution_owner_ids": selected_owner_ids,
        "impact_graph_hash": str(
            impact_plan.get("impact_graph_hash", "")
        ),
    }
    selection_declaration_hash = wire_hash(selection_declaration)
    snapshot_identity_hash = wire_hash(
        {
            "selection_declaration_hash": selection_declaration_hash,
            "source_identity_hash": source_identity_hash,
            "toolchain_identity_hash": toolchain_identity_hash,
            "request_fingerprint": str(run.get("request_fingerprint", "")),
        }
    )
    full_reasons = _derived_full_admission_reasons(
        impact_plan,
        changed_components,
        set(selected_owner_ids),
        full_admission_reason,
    )
    full_required = bool(profile.get("full_admission_required", False))
    if full_required:
        expected_freeze = {
            "source_identity_hash": source_identity_hash,
            "toolchain_identity_hash": toolchain_identity_hash,
            "owner_plan_hash": str(
                impact_plan.get("impact_graph_hash", "")
            ),
        }
        if (
            not isinstance(freeze_identity, Mapping)
            or dict(freeze_identity) != expected_freeze
            or full_admission_reason not in full_reasons
        ):
            return _blocked_current_plan(
                profile_id,
                ["full_gate_requires_exact_freeze_and_derived_reason"],
            )
    report: dict[str, Any] = {
        "schema_version": CURRENT_TEST_MESH_PLAN_SCHEMA,
        "artifact_type": "skillguard_test_mesh_execution_plan",
        "status": "passed",
        "mode": "plan_only",
        "profile_id": profile_id,
        "full_admission_required": full_required,
        "full_admission_reason": (
            full_admission_reason if full_required else ""
        ),
        "selection_declaration_hash": selection_declaration_hash,
        "snapshot_identity_hash": snapshot_identity_hash,
        "source_identity_hash": source_identity_hash,
        "toolchain_identity_hash": toolchain_identity_hash,
        "impact_graph_hash": str(
            impact_plan.get("impact_graph_hash", "")
        ),
        "selected_owner_ids": selected_owner_ids,
        "changed_component_ids": sorted(changed_components),
        "will_reuse_owner_ids": reusable,
        "will_execute_owner_ids": execute,
        "will_aggregate_only": not execute,
        "required_install_component_ids": required_install_components,
        "required_router_refresh": bool(
            changed_components & router_components
        ),
        "required_portfolio_target_ids": required_portfolio_target_ids,
        "full_required_reason_codes": full_reasons,
        "owner_plans": owner_plans,
        "execution_count": 0,
        "findings": [],
        "claim_boundary": (
            "This immutable preview reads exact persistent owner receipts and plans only stale owners; "
            "it launches and writes nothing."
        ),
    }
    report["plan_hash"] = _current_plan_hash(report)
    return report


def _validate_frozen_current_plan(
    frozen_plan: Mapping[str, Any],
    *,
    manifest_path: Path,
    repository_root: Path,
    run_root: Path,
    skill_root: Path,
    target_root: Path,
    owner_evidence_root: Path | None,
) -> tuple[list[Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    if (
        frozen_plan.get("schema_version") != CURRENT_TEST_MESH_PLAN_SCHEMA
        or frozen_plan.get("status") != "passed"
        or frozen_plan.get("mode") != "plan_only"
        or frozen_plan.get("plan_hash") != _current_plan_hash(frozen_plan)
    ):
        raise ValueError("current_test_mesh_frozen_plan_invalid")
    mesh_manifest = _load_current_test_mesh_manifest(manifest_path)
    contract = load_contract_snapshot(run_root)
    check_manifest = load_check_manifest_snapshot(run_root)
    run = load_run(run_root)
    _profile, selected_rows = _selected_owner_rows(
        contract, mesh_manifest, str(frozen_plan.get("profile_id", ""))
    )
    owners = _topological_owner_rows(selected_rows)
    selected_owner_ids = [
        str(row["execution_owner_id"]) for row in owners
    ]
    if selected_owner_ids != list(frozen_plan.get("selected_owner_ids", [])):
        raise ValueError("current_test_mesh_frozen_owner_selection_stale")
    impact_plan = contract["content_impact_plan"]
    checks_by_owner_rows: dict[str, list[Mapping[str, Any]]] = {}
    for check in check_manifest.get("checks", []):
        if isinstance(check, Mapping):
            checks_by_owner_rows.setdefault(
                str(check.get("execution_owner_id", "")), []
            ).append(check)
    checks_by_owner: dict[str, Mapping[str, Any]] = {}
    owner_plan_rows = frozen_plan.get("owner_plans", [])
    if not isinstance(owner_plan_rows, list) or len(owner_plan_rows) != len(
        owners
    ):
        raise ValueError("current_test_mesh_frozen_owner_plans_invalid")
    if any(not isinstance(row, Mapping) for row in owner_plan_rows):
        raise ValueError("current_test_mesh_frozen_owner_plans_invalid")
    plan_by_owner = {
        str(row.get("execution_owner_id", "")): row
        for row in owner_plan_rows
        if isinstance(row, Mapping)
    }
    if list(plan_by_owner) != selected_owner_ids:
        raise ValueError("current_test_mesh_frozen_owner_plan_order_invalid")
    planned_reuse = frozen_plan.get("will_reuse_owner_ids", [])
    planned_execute = frozen_plan.get("will_execute_owner_ids", [])
    if (
        not isinstance(planned_reuse, list)
        or not isinstance(planned_execute, list)
        or any(not isinstance(value, str) or not value for value in planned_reuse)
        or any(not isinstance(value, str) or not value for value in planned_execute)
        or len(set(planned_reuse)) != len(planned_reuse)
        or len(set(planned_execute)) != len(planned_execute)
        or set(planned_reuse) & set(planned_execute)
        or set(planned_reuse) | set(planned_execute) != set(selected_owner_ids)
        or planned_reuse
        != [
            owner_id
            for owner_id in selected_owner_ids
            if owner_id in set(planned_reuse)
        ]
        or planned_execute
        != [
            owner_id
            for owner_id in selected_owner_ids
            if owner_id in set(planned_execute)
        ]
        or not isinstance(frozen_plan.get("will_aggregate_only"), bool)
        or bool(frozen_plan.get("will_aggregate_only")) != (not planned_execute)
    ):
        raise ValueError("current_test_mesh_frozen_owner_partition_invalid")
    toolchain_rows: list[dict[str, str]] = []
    for owner in owners:
        owner_id = str(owner["execution_owner_id"])
        owner_checks = sorted(
            checks_by_owner_rows.get(owner_id, []),
            key=lambda row: str(row.get("check_id", "")),
        )
        check, check_ids, check_projections, toolchain = (
            _exact_owner_check_projection(owner, owner_checks)
        )
        checks_by_owner[owner_id] = check
        owner_plan = plan_by_owner[owner_id]
        current_input = inspect_current_owner_input_projection(
            repository_root=repository_root,
            content_impact_plan=impact_plan,
            owner=owner,
        )
        expected_decision = (
            "reuse_owner_receipt"
            if owner_id in planned_reuse
            else "execute_owner"
        )
        expected_owner_fields = {
            "primary_check_id": str(check.get("check_id", "")),
            "check_ids": check_ids,
            "check_projections": check_projections,
            "owner_declaration_hash": str(
                owner.get("owner_declaration_hash", "")
            ),
            "owner_input_projection_hash": str(
                current_input["owner_input_projection_hash"]
            ),
            "input_components": list(current_input["components"]),
            "depends_on_owner_ids": [
                str(value)
                for value in owner.get("depends_on_owner_ids", [])
            ],
            "evidence_domain_id": str(
                owner.get("evidence_domain_id", "")
            ),
            "toolchain_fingerprint": str(
                toolchain["toolchain_fingerprint"]
            ),
            "execution_environment_fingerprint": str(
                toolchain["execution_environment_fingerprint"]
            ),
            "decision": expected_decision,
        }
        if any(
            owner_plan.get(field) != expected
            for field, expected in expected_owner_fields.items()
        ):
            raise ValueError(
                f"current_test_mesh_frozen_owner_plan_stale:{owner_id}"
            )
        reusable_receipt = owner_plan.get("reusable_receipt")
        if expected_decision == "execute_owner" and reusable_receipt is not None:
            raise ValueError(
                f"current_test_mesh_frozen_execute_owner_has_receipt:{owner_id}"
            )
        if expected_decision == "reuse_owner_receipt" and not isinstance(
            reusable_receipt, Mapping
        ):
            raise ValueError(
                f"current_test_mesh_frozen_reuse_owner_receipt_missing:{owner_id}"
            )
        toolchain_rows.append(
            {"execution_owner_id": owner_id, **toolchain}
        )
    source_identity_hash = str(impact_plan.get("inventory_hash", ""))
    toolchain_identity_hash = wire_hash(toolchain_rows)
    selection_declaration_hash = wire_hash(
        {
            "mesh_id": str(mesh_manifest.get("mesh_id", "")),
            "profile_id": str(frozen_plan.get("profile_id", "")),
            "closure_profile_id": str(
                _profile.get("closure_profile_id", "")
            ),
            "execution_owner_ids": selected_owner_ids,
            "impact_graph_hash": str(
                impact_plan.get("impact_graph_hash", "")
            ),
        }
    )
    expected_snapshot = wire_hash(
        {
            "selection_declaration_hash": selection_declaration_hash,
            "source_identity_hash": source_identity_hash,
            "toolchain_identity_hash": toolchain_identity_hash,
            "request_fingerprint": str(run.get("request_fingerprint", "")),
        }
    )
    for field, expected in (
        ("selection_declaration_hash", selection_declaration_hash),
        ("snapshot_identity_hash", expected_snapshot),
        ("source_identity_hash", source_identity_hash),
        ("toolchain_identity_hash", toolchain_identity_hash),
        ("impact_graph_hash", impact_plan.get("impact_graph_hash")),
    ):
        if frozen_plan.get(field) != expected:
            raise ValueError(f"current_test_mesh_frozen_{field}_stale")
    return owners, checks_by_owner


def _check_step_id(
    contract: Mapping[str, Any], check_id: str
) -> str:
    candidates: set[str] = set()
    declared_steps = {
        str(row.get("step_id", ""))
        for row in contract.get("steps", [])
        if isinstance(row, Mapping)
        and str(row.get("step_id", ""))
        and not str(row.get("terminal_kind", ""))
    }
    for step in contract.get("steps", []):
        if not isinstance(step, Mapping):
            continue
        binding = step.get("binding")
        if (
            isinstance(binding, Mapping)
            and check_id
            in {str(value) for value in binding.get("check_ids", [])}
        ):
            candidates.add(str(step.get("step_id", "")))
    if not candidates:
        for obligation in contract.get("obligations", []):
            if (
                isinstance(obligation, Mapping)
                and check_id
                in {
                    str(value)
                    for value in obligation.get("required_check_ids", [])
                }
            ):
                candidates.update(
                    str(value)
                    for value in obligation.get("owner_step_ids", [])
                    if str(value) in declared_steps
                )
    candidates.discard("")
    if len(candidates) != 1:
        raise ValueError(
            f"current_test_mesh_owner_check_step_invalid:{check_id}"
        )
    return next(iter(candidates))


def _blocked_owner_execution(
    profile_id: str,
    frozen_plan: Mapping[str, Any] | None,
    findings: Sequence[str],
) -> dict[str, Any]:
    return {
        "schema_version": CURRENT_TEST_MESH_OWNER_EXECUTION_SCHEMA,
        "artifact_type": "skillguard_test_mesh_owner_execution",
        "status": "blocked",
        "mode": "owner_execution_only",
        "profile_id": profile_id,
        "plan_hash": str(
            frozen_plan.get("plan_hash", "")
            if isinstance(frozen_plan, Mapping)
            else ""
        ),
        "planned_execute_owner_ids": [],
        "planned_reuse_owner_ids": [],
        "verified_planned_reuse_owner_ids": [],
        "executed_owner_ids": [],
        "reused_after_freeze_owner_ids": [],
        "failed_owner_ids": [],
        "not_run_owner_ids": [],
        "execution_count": 0,
        "owner_results": [],
        "findings": list(findings),
        "claim_boundary": (
            "Invalid or stale frozen plans launch no owner commands."
        ),
    }


def _owner_result_check_projection(
    owner_plan: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "check_ids": list(owner_plan.get("check_ids", [])),
        "check_projections": [
            dict(row)
            for row in owner_plan.get("check_projections", [])
            if isinstance(row, Mapping)
        ],
    }


def _execute_frozen_current_test_mesh_owners(
    frozen_plan: Mapping[str, Any],
    manifest_path: Path,
    repository_root: Path,
    run_root: Path,
    *,
    skill_root: Path,
    target_root: Path,
    owner_evidence_root: Path | None,
) -> dict[str, Any]:
    """Execute only the immutable plan's exact missing owner partition."""

    profile_id = str(frozen_plan.get("profile_id", ""))
    try:
        owners, checks_by_owner = _validate_frozen_current_plan(
            frozen_plan,
            manifest_path=manifest_path,
            repository_root=repository_root,
            run_root=run_root,
            skill_root=skill_root,
            target_root=target_root,
            owner_evidence_root=owner_evidence_root,
        )
        contract = load_contract_snapshot(run_root)
        step_by_owner = {
            owner_id: _check_step_id(
                contract, str(check.get("check_id", ""))
            )
            for owner_id, check in checks_by_owner.items()
        }
    except (CheckRunnerError, ValueError, OSError) as exc:
        return _blocked_owner_execution(profile_id, frozen_plan, [str(exc)])

    persistent_root = resolve_owner_evidence_root(
        repository_root, owner_evidence_root
    )
    planned_execute = list(frozen_plan.get("will_execute_owner_ids", []))
    planned_reuse = list(frozen_plan.get("will_reuse_owner_ids", []))
    selected_owner_ids = [
        str(owner["execution_owner_id"]) for owner in owners
    ]
    planned_execute_set = set(planned_execute)
    plan_by_owner = {
        str(row.get("execution_owner_id", "")): row
        for row in frozen_plan.get("owner_plans", [])
        if isinstance(row, Mapping)
    }
    receipts: dict[str, Mapping[str, Any]] = {}
    verified_reuse: list[str] = []
    executed: list[str] = []
    reused_after_freeze: list[str] = []
    failed: list[str] = []
    not_run: list[str] = []
    results_by_owner: dict[str, dict[str, Any]] = {}
    findings: list[str] = []
    execution_count = 0

    # Planned reuse is a read-only precondition on the frozen plan.  Verify
    # every such receipt before any process may start so a stale plan cannot
    # partially execute an independent owner and then discover that the
    # immutable reuse partition changed underneath it.
    for owner in owners:
        owner_id = str(owner["execution_owner_id"])
        if owner_id in planned_execute_set:
            continue
        check = checks_by_owner[owner_id]
        check_id = str(check.get("check_id", ""))
        step_id = step_by_owner[owner_id]
        dependency_ids = [
            str(value) for value in owner.get("depends_on_owner_ids", [])
        ]
        missing_dependencies = [
            dependency_id
            for dependency_id in dependency_ids
            if dependency_id not in receipts
        ]
        if missing_dependencies:
            finding = (
                f"planned_reuse_dependency_receipt_missing:{owner_id}:"
                + ",".join(missing_dependencies)
            )
            findings.append(finding)
            not_run.append(owner_id)
            results_by_owner[owner_id] = {
                "execution_owner_id": owner_id,
                "primary_check_id": check_id,
                **_owner_result_check_projection(plan_by_owner[owner_id]),
                "step_id": step_id,
                "planned_disposition": "reuse_owner_receipt",
                "terminal_disposition": "not_run_dependency_missing",
                "process_started": False,
                "receipt_id": "",
                "receipt_hash": "",
                "receipt_ref": None,
                "finding": finding,
            }
            break

        dependency_receipts = {
            dependency_id: receipts[dependency_id]
            for dependency_id in dependency_ids
        }
        try:
            inspection = inspect_current_owner_execution(
                check,
                skill_root=skill_root,
                target_root=target_root,
                repository_root=repository_root,
                run_root=run_root,
                owner_evidence_root=persistent_root,
                dependency_execution_receipts=dependency_receipts,
            )
        except CheckRunnerError as exc:
            inspection = {"disposition": "execute_owner", "reason": str(exc)}
        receipt = inspection.get("receipt")
        planned_receipt = plan_by_owner[owner_id].get("reusable_receipt")
        if (
            inspection.get("disposition") != "reuse_owner_receipt"
            or not isinstance(receipt, Mapping)
            or not isinstance(planned_receipt, Mapping)
            or planned_receipt.get("receipt_id") != receipt.get("receipt_id")
            or planned_receipt.get("receipt_hash") != receipt.get("receipt_hash")
            or planned_receipt.get("receipt_ref")
            != owner_receipt_document_ref(receipt)
        ):
            finding = f"planned_owner_receipt_changed:{owner_id}"
            findings.append(finding)
            not_run.append(owner_id)
            results_by_owner[owner_id] = {
                "execution_owner_id": owner_id,
                "primary_check_id": check_id,
                **_owner_result_check_projection(plan_by_owner[owner_id]),
                "step_id": step_id,
                "planned_disposition": "reuse_owner_receipt",
                "terminal_disposition": "planned_reuse_stale",
                "process_started": False,
                "receipt_id": "",
                "receipt_hash": "",
                "receipt_ref": None,
                "finding": finding,
            }
            break
        receipts[owner_id] = receipt
        verified_reuse.append(owner_id)
        results_by_owner[owner_id] = {
            "execution_owner_id": owner_id,
            "primary_check_id": check_id,
            **_owner_result_check_projection(plan_by_owner[owner_id]),
            "step_id": step_id,
            "planned_disposition": "reuse_owner_receipt",
            "terminal_disposition": "planned_reuse_verified",
            "process_started": False,
            "receipt_id": str(receipt.get("receipt_id", "")),
            "receipt_hash": str(receipt.get("receipt_hash", "")),
            "receipt_ref": dict(owner_receipt_document_ref(receipt)),
            "finding": "",
        }

    if findings:
        not_run.extend(
            owner_id
            for owner_id in selected_owner_ids
            if owner_id not in receipts and owner_id not in not_run
        )
        return {
            **_blocked_owner_execution(profile_id, frozen_plan, findings),
            "planned_execute_owner_ids": planned_execute,
            "planned_reuse_owner_ids": planned_reuse,
            "verified_planned_reuse_owner_ids": verified_reuse,
            "not_run_owner_ids": not_run,
            "owner_results": [
                results_by_owner[owner_id]
                for owner_id in selected_owner_ids
                if owner_id in results_by_owner
            ],
        }

    for owner in owners:
        owner_id = str(owner["execution_owner_id"])
        if owner_id not in planned_execute_set:
            continue
        check = checks_by_owner[owner_id]
        check_id = str(check.get("check_id", ""))
        step_id = step_by_owner[owner_id]
        dependency_ids = [
            str(value) for value in owner.get("depends_on_owner_ids", [])
        ]
        missing_dependencies = [
            dependency_id
            for dependency_id in dependency_ids
            if dependency_id not in receipts
        ]
        if missing_dependencies:
            finding = (
                f"owner_dependency_receipt_missing:{owner_id}:"
                + ",".join(missing_dependencies)
            )
            findings.append(finding)
            not_run.append(owner_id)
            results_by_owner[owner_id] = {
                "execution_owner_id": owner_id,
                "primary_check_id": check_id,
                **_owner_result_check_projection(plan_by_owner[owner_id]),
                "step_id": step_id,
                "planned_disposition": "execute_owner",
                "terminal_disposition": "not_run_dependency_missing",
                "process_started": False,
                "receipt_id": "",
                "receipt_hash": "",
                "receipt_ref": None,
                "finding": finding,
            }
            continue

        dependency_receipts = {
            dependency_id: receipts[dependency_id]
            for dependency_id in dependency_ids
        }

        process_started_in_call = False

        def mark_process_started() -> None:
            nonlocal process_started_in_call
            process_started_in_call = True

        try:
            execution = get_or_execute_check(
                check,
                skill_root=skill_root,
                target_root=target_root,
                repository_root=repository_root,
                run_root=run_root,
                step_id=step_id,
                owner_evidence_root=persistent_root,
                dependency_execution_receipts=dependency_receipts,
                progress_context={
                    "completed_count": len(executed)
                    + len(reused_after_freeze)
                    + len(failed),
                    "total_count": len(planned_execute),
                },
                process_started_callback=mark_process_started,
            )
        except (CheckRunnerError, OSError, ValueError) as exc:
            finding = f"owner_execution_error:{owner_id}:{exc}"
            findings.append(finding)
            if process_started_in_call:
                execution_count += 1
                failed.append(owner_id)
            else:
                not_run.append(owner_id)
            results_by_owner[owner_id] = {
                "execution_owner_id": owner_id,
                "primary_check_id": check_id,
                **_owner_result_check_projection(plan_by_owner[owner_id]),
                "step_id": step_id,
                "planned_disposition": "execute_owner",
                "terminal_disposition": "owner_execution_error",
                "process_started": process_started_in_call,
                "receipt_id": "",
                "receipt_hash": "",
                "receipt_ref": None,
                "finding": finding,
            }
            continue

        disposition = str(execution.get("disposition", ""))
        receipt = execution.get("execution_receipt")
        record = execution.get("record")
        process_started = bool(
            isinstance(record, Mapping)
            and record.get("command_executed_in_this_call") is True
        ) or process_started_in_call
        if process_started:
            execution_count += 1
        if (
            disposition
            in {"executed_terminal_success", "reused_terminal_success"}
            and isinstance(receipt, Mapping)
        ):
            receipts[owner_id] = receipt
            if disposition == "executed_terminal_success":
                executed.append(owner_id)
            else:
                reused_after_freeze.append(owner_id)
            finding = ""
        else:
            finding = f"owner_execution_not_successful:{owner_id}:{disposition}"
            findings.append(finding)
            if process_started:
                failed.append(owner_id)
            else:
                not_run.append(owner_id)
        results_by_owner[owner_id] = {
            "execution_owner_id": owner_id,
            "primary_check_id": check_id,
            **_owner_result_check_projection(plan_by_owner[owner_id]),
            "step_id": step_id,
            "planned_disposition": "execute_owner",
            "terminal_disposition": disposition or "unknown",
            "process_started": process_started,
            "receipt_id": str(
                receipt.get("receipt_id", "")
                if isinstance(receipt, Mapping)
                else ""
            ),
            "receipt_hash": str(
                receipt.get("receipt_hash", "")
                if isinstance(receipt, Mapping)
                else ""
            ),
            "receipt_ref": (
                dict(owner_receipt_document_ref(receipt))
                if isinstance(receipt, Mapping)
                else None
            ),
            "finding": finding,
        }

    return {
        "schema_version": CURRENT_TEST_MESH_OWNER_EXECUTION_SCHEMA,
        "artifact_type": "skillguard_test_mesh_owner_execution",
        "status": "passed" if not findings else "failed",
        "mode": "owner_execution_only",
        "profile_id": profile_id,
        "plan_hash": str(frozen_plan.get("plan_hash", "")),
        "planned_execute_owner_ids": planned_execute,
        "planned_reuse_owner_ids": planned_reuse,
        "verified_planned_reuse_owner_ids": verified_reuse,
        "executed_owner_ids": executed,
        "reused_after_freeze_owner_ids": reused_after_freeze,
        "failed_owner_ids": failed,
        "not_run_owner_ids": not_run,
        "execution_count": execution_count,
        "owner_results": [
            results_by_owner[owner_id]
            for owner_id in selected_owner_ids
            if owner_id in results_by_owner
        ],
        "findings": findings,
        "claim_boundary": (
            "This runner consumes one immutable plan, verifies its exact current identities, "
            "and resolves only will_execute_owner_ids through the existing single-flight owner authority. "
            "It never replans, broadens the owner set, executes a planned-reuse owner, or aggregates."
        ),
    }


def _aggregate_frozen_current_test_mesh(
    frozen_plan: Mapping[str, Any],
    manifest_path: Path,
    repository_root: Path,
    run_root: Path,
    *,
    skill_root: Path,
    target_root: Path,
    owner_evidence_root: Path | None,
    installation_binding: Mapping[str, Any] | None = None,
    global_prompt_binding: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        owners, checks_by_owner = _validate_frozen_current_plan(
            frozen_plan,
            manifest_path=manifest_path,
            repository_root=repository_root,
            run_root=run_root,
            skill_root=skill_root,
            target_root=target_root,
            owner_evidence_root=owner_evidence_root,
        )
    except (CheckRunnerError, ValueError, OSError) as exc:
        return {
            "schema_version": CURRENT_TEST_MESH_AGGREGATION_SCHEMA,
            "status": "blocked",
            "mode": "aggregation_only",
            "execution_count": 0,
            "findings": [str(exc)],
            "child_receipts": [],
        }
    persistent_root = resolve_owner_evidence_root(
        repository_root, owner_evidence_root
    )
    receipts: dict[str, Mapping[str, Any]] = {}
    planned_reuse = {
        str(row.get("execution_owner_id", "")): row.get(
            "reusable_receipt"
        )
        for row in frozen_plan.get("owner_plans", [])
        if isinstance(row, Mapping)
        and row.get("decision") == "reuse_owner_receipt"
    }
    plan_by_owner = {
        str(row.get("execution_owner_id", "")): row
        for row in frozen_plan.get("owner_plans", [])
        if isinstance(row, Mapping)
    }
    child_receipts: list[dict[str, Any]] = []
    for owner in owners:
        owner_id = str(owner["execution_owner_id"])
        dependency_ids = [
            str(value) for value in owner.get("depends_on_owner_ids", [])
        ]
        try:
            inspection = inspect_current_owner_execution(
                checks_by_owner[owner_id],
                skill_root=skill_root,
                target_root=target_root,
                repository_root=repository_root,
                run_root=run_root,
                owner_evidence_root=persistent_root,
                dependency_execution_receipts={
                    dependency_id: receipts[dependency_id]
                    for dependency_id in dependency_ids
                },
            )
        except (CheckRunnerError, KeyError) as exc:
            return {
                "schema_version": CURRENT_TEST_MESH_AGGREGATION_SCHEMA,
                "status": "blocked",
                "mode": "aggregation_only",
                "execution_count": 0,
                "findings": [str(exc)],
                "child_receipts": [],
            }
        receipt = inspection.get("receipt")
        if (
            inspection.get("disposition") != "reuse_owner_receipt"
            or not isinstance(receipt, Mapping)
        ):
            return {
                "schema_version": CURRENT_TEST_MESH_AGGREGATION_SCHEMA,
                "status": "blocked",
                "mode": "aggregation_only",
                "execution_count": 0,
                "findings": [f"owner_receipt_missing:{owner_id}"],
                "child_receipts": [],
            }
        planned = planned_reuse.get(owner_id)
        if isinstance(planned, Mapping) and (
            planned.get("receipt_id") != receipt.get("receipt_id")
            or planned.get("receipt_hash") != receipt.get("receipt_hash")
            or planned.get("receipt_ref")
            != owner_receipt_document_ref(receipt)
        ):
            return {
                "schema_version": CURRENT_TEST_MESH_AGGREGATION_SCHEMA,
                "status": "blocked",
                "mode": "aggregation_only",
                "execution_count": 0,
                "findings": [f"planned_owner_receipt_changed:{owner_id}"],
                "child_receipts": [],
            }
        receipts[owner_id] = receipt
        child_receipts.append(
            {
                "execution_owner_id": owner_id,
                **_owner_result_check_projection(plan_by_owner[owner_id]),
                "receipt_id": str(receipt["receipt_id"]),
                "receipt_hash": str(receipt["receipt_hash"]),
                "receipt_ref": dict(owner_receipt_document_ref(receipt)),
            }
        )
    aggregation: dict[str, Any] = {
        "schema_version": CURRENT_TEST_MESH_AGGREGATION_SCHEMA,
        "profile_id": str(frozen_plan.get("profile_id", "")),
        "plan_hash": str(frozen_plan.get("plan_hash", "")),
        "full_admission_required": bool(
            frozen_plan.get("full_admission_required", False)
        ),
        "selection_declaration_hash": str(
            frozen_plan.get("selection_declaration_hash", "")
        ),
        "snapshot_identity_hash": str(
            frozen_plan.get("snapshot_identity_hash", "")
        ),
        "impact_graph_hash": str(
            frozen_plan.get("impact_graph_hash", "")
        ),
        "child_receipts": child_receipts,
        "installation_verification_identity": (
            dict(installation_binding)
            if isinstance(installation_binding, Mapping)
            else None
        ),
        "typed_domain_bindings": (
            [dict(global_prompt_binding)]
            if isinstance(global_prompt_binding, Mapping)
            else []
        ),
        "status": "passed",
        "mode": "aggregation_only",
        "execution_count": 0,
        "findings": [],
        "claim_boundary": (
            "This parent consumes one unchanged frozen plan and immutable child receipts; "
            "it launches no owner process and never reissues child receipts."
        ),
    }
    aggregation["external_projection_bindings_hash"] = wire_hash(
        {
            "installation_verification_identity": aggregation[
                "installation_verification_identity"
            ],
            "typed_domain_bindings": aggregation["typed_domain_bindings"],
        }
    )
    aggregation["aggregation_id"] = wire_hash(aggregation)
    aggregation["aggregation_hash"] = wire_hash(aggregation)
    body = canonical_json_bytes(aggregation)
    content_hash = "sha256:" + hashlib.sha256(body).hexdigest()
    relative = (
        Path("test-mesh")
        / "aggregations"
        / content_hash.split(":", 1)[1][:2]
        / f"{content_hash.split(':', 1)[1]}.json"
    )
    durable_write_immutable_json(persistent_root / relative, aggregation)
    aggregation["aggregation_ref"] = {
        "path_token": "owner_evidence_root",
        "relative_path": relative.as_posix(),
        "content_hash": content_hash,
        "media_type": "application/json",
        "byte_count": len(body),
    }
    return aggregation




def replay_current_test_mesh_aggregation(
    owner_evidence_root: Path,
    aggregation_ref: Mapping[str, Any],
    *,
    repository_root: Path | None = None,
    canonical_skillguard_root: Path | None = None,
    verified_installation_context: VerifiedInstallationContext | None = None,
    global_prompt_codex_home: Path | None = None,
) -> Mapping[str, Any]:
    findings: list[str] = []
    required_ref_fields = {
        "path_token",
        "relative_path",
        "content_hash",
        "media_type",
        "byte_count",
    }
    if (
        set(aggregation_ref) != required_ref_fields
        or aggregation_ref.get("path_token") != "owner_evidence_root"
        or not re.fullmatch(
            r"sha256:[0-9a-f]{64}",
            str(aggregation_ref.get("content_hash", "")),
        )
    ):
        findings.append("aggregation_ref_invalid")
        path = Path()
    else:
        relative = Path(str(aggregation_ref.get("relative_path", "")))
        path = (owner_evidence_root / relative).resolve()
        try:
            path.relative_to(owner_evidence_root.resolve())
        except ValueError:
            findings.append("aggregation_ref_escape")
    payload: Mapping[str, Any] = {}
    if not findings:
        try:
            body = filesystem_path(path).read_bytes()
            loaded = json.loads(body.decode("utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            findings.append("aggregation_unreadable")
        else:
            if not isinstance(loaded, Mapping):
                findings.append("aggregation_object_required")
            else:
                payload = loaded
            if (
                "sha256:" + hashlib.sha256(body).hexdigest()
                != aggregation_ref.get("content_hash")
                or len(body) != aggregation_ref.get("byte_count")
            ):
                findings.append("aggregation_content_hash_mismatch")
    if payload:
        if payload.get("schema_version") != CURRENT_TEST_MESH_AGGREGATION_SCHEMA:
            findings.append("aggregation_schema_invalid")
        unsigned_hash = dict(payload)
        stored_hash = unsigned_hash.pop("aggregation_hash", None)
        if stored_hash != wire_hash(unsigned_hash):
            findings.append("aggregation_hash_mismatch")
        unsigned_id = dict(unsigned_hash)
        stored_id = unsigned_id.pop("aggregation_id", None)
        if stored_id != wire_hash(unsigned_id):
            findings.append("aggregation_id_mismatch")
        installation_binding = payload.get(
            "installation_verification_identity"
        )
        typed_bindings = payload.get("typed_domain_bindings")
        expected_external_hash = wire_hash(
            {
                "installation_verification_identity": installation_binding,
                "typed_domain_bindings": typed_bindings,
            }
        )
        if payload.get("external_projection_bindings_hash") != expected_external_hash:
            findings.append("aggregation_external_projection_bindings_hash_mismatch")
        if payload.get("full_admission_required") is True:
            if repository_root is None:
                findings.append("aggregation_repository_root_required_for_full_replay")
            else:
                findings.extend(
                    _replay_installation_binding(
                        repository_root.resolve(),
                        installation_binding,
                        canonical_skillguard_root=canonical_skillguard_root,
                        verified_installation_context=(
                            verified_installation_context
                        ),
                    )
                )
            findings.extend(
                _replay_global_prompt_currentness_binding(
                    typed_bindings,
                    codex_home=global_prompt_codex_home,
                )
            )
        elif installation_binding is not None or typed_bindings not in ([], None):
            findings.append("aggregation_external_bindings_for_non_full_profile")
        children = payload.get("child_receipts")
        if not isinstance(children, list):
            findings.append("aggregation_child_receipts_invalid")
            children = []
        seen: set[str] = set()
        for child in children:
            if not isinstance(child, Mapping) or set(child) != {
                "execution_owner_id",
                "check_ids",
                "check_projections",
                "receipt_id",
                "receipt_hash",
                "receipt_ref",
            }:
                findings.append("aggregation_child_shape_invalid")
                continue
            owner_id = str(child.get("execution_owner_id", ""))
            if not owner_id or owner_id in seen:
                findings.append("aggregation_child_owner_duplicate_or_missing")
                continue
            check_ids = child.get("check_ids")
            check_projections = child.get("check_projections")
            if (
                not isinstance(check_ids, list)
                or not check_ids
                or check_ids != sorted(set(check_ids))
                or not isinstance(check_projections, list)
                or [
                    row.get("check_id")
                    for row in check_projections
                    if isinstance(row, Mapping)
                ]
                != check_ids
                or any(
                    not isinstance(row, Mapping)
                    or set(row)
                    != {
                        "check_id",
                        "semantic_check_id",
                        "projection_declaration_hash",
                    }
                    for row in check_projections
                )
            ):
                findings.append(
                    f"aggregation_child_check_projection_invalid:{owner_id}"
                )
                continue
            seen.add(owner_id)
            try:
                receipt = load_owner_receipt_from_ref(
                    owner_evidence_root,
                    child["receipt_ref"],
                    expected_owner_id=owner_id,
                )
            except CheckRunnerError as exc:
                findings.append(f"aggregation_child_invalid:{owner_id}:{exc.code}")
                continue
            if (
                receipt.get("receipt_id") != child.get("receipt_id")
                or receipt.get("receipt_hash") != child.get("receipt_hash")
            ):
                findings.append(f"aggregation_child_identity_mismatch:{owner_id}")
    return {
        "schema_version": CURRENT_TEST_MESH_REPLAY_SCHEMA,
        "status": "passed" if not findings else "blocked",
        "mode": "read_only_replay",
        "execution_count": 0,
        "aggregation_id": str(payload.get("aggregation_id", "")),
        "findings": findings,
        "claim_boundary": (
            "Replay only verifies the immutable aggregation and child owner receipts; "
            "missing evidence is reported and never backfilled."
        ),
    }


_OPENSPEC_ASCII_COLLATION_ORDER = (
    " _-,;:!?.'\"()[]{}@*/\\&#%`^+<=>|~$0123456789abcdefghijklmnopqrstuvwxyz"
)
_OPENSPEC_ASCII_PRIMARY_WEIGHTS = {
    character: index
    for index, character in enumerate(_OPENSPEC_ASCII_COLLATION_ORDER)
}


def _openspec_ascii_collation_key(value: str) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Match Node's default localeCompare ordering for portable ASCII keys.

    OpenSpec canonicalizes receipt objects with JavaScript ``localeCompare``.
    Windows' process locale is not the same collation: notably, it orders
    ``.`` and ``_`` differently inside repository paths.  Portable projection
    admits ASCII source paths only, so an explicit primary/case key is both
    deterministic and independent of the machine's active locale.
    """

    if not value.isascii():
        raise ValueError("OpenSpec portable canonical keys must be ASCII")
    primary = tuple(
        _OPENSPEC_ASCII_PRIMARY_WEIGHTS[character.lower()]
        for character in value
    )
    case = tuple(
        1 if character.isalpha() and character.isupper() else 0
        for character in value
    )
    return primary, case


def _portable_canonicalize(payload: object) -> object:
    if isinstance(payload, list):
        return [_portable_canonicalize(value) for value in payload]
    if isinstance(payload, Mapping):
        keys = sorted(payload, key=_openspec_ascii_collation_key)
        return {
            key: _portable_canonicalize(payload[key])
            for key in keys
        }
    return payload


def _portable_receipt_hash(payload: object) -> str:
    """Match OpenSpec's localeCompare-based canonical JSON identity exactly."""

    canonical = _portable_canonicalize(payload)
    body = json.dumps(
        canonical,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _raw_content_hash(body: bytes) -> str:
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _portable_token(token: str, relative: Path) -> str:
    return f"<{token}>/{relative.as_posix()}"


def _atomic_replace_projection_ref(path: Path, payload: Mapping[str, Any]) -> None:
    """Atomically replace the one mutable consumer pointer, never its blobs."""

    body = canonical_json_bytes(dict(payload))
    path = filesystem_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".sg-{uuid.uuid4().hex}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)
    try:
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _write_portable_sidecar(
    evidence_root: Path,
    evidence_root_token: str,
    *,
    role: str,
    body: bytes,
    suffix: str,
) -> tuple[str, str]:
    content_hash = _raw_content_hash(body)
    digest = content_hash.split(":", 1)[1]
    relative = (
        Path("portable")
        / "blobs"
        / digest[:2]
        / f"{digest}.{role}.{suffix}"
    )
    durable_copy_immutable_stream(
        evidence_root / relative,
        io.BytesIO(body),
        expected_content_hash=content_hash,
    )
    return _portable_token(evidence_root_token, relative), content_hash


def _projection_source_files(
    repository_root: Path,
    source_paths: Sequence[str],
) -> tuple[dict[str, str], list[str]]:
    files: dict[str, str] = {}
    findings: list[str] = []
    root = repository_root.resolve()
    for raw in source_paths:
        normalized = str(raw).replace("\\", "/").strip("/")
        relative = Path(normalized)
        if (
            not normalized
            or Path(str(raw)).is_absolute()
            or any(part in {"", ".", ".."} for part in relative.parts)
            or normalized in files
        ):
            findings.append(f"openspec_projection_source_path_invalid:{raw}")
            continue
        if not normalized.isascii():
            findings.append(
                f"openspec_projection_source_path_non_ascii_unsupported:{normalized}"
            )
            continue
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            findings.append(f"openspec_projection_source_path_escape:{normalized}")
            continue
        physical_candidate = filesystem_path(candidate)
        if not physical_candidate.is_file():
            findings.append(f"openspec_projection_source_missing:{normalized}")
            continue
        body = physical_candidate.read_bytes()
        if candidate.name.lower() == "tasks.md":
            try:
                text = body.decode("utf-8")
            except UnicodeDecodeError:
                findings.append(
                    f"openspec_projection_tasks_not_utf8:{normalized}"
                )
                continue
            body = normalize_markdown_task_checkbox_state(text).encode("utf-8")
        files[normalized] = _raw_content_hash(body)
    if not files:
        findings.append("openspec_projection_source_manifest_empty")
    return dict(sorted(files.items())), findings


def project_current_test_mesh_aggregation_to_openspec_receipt(
    repository_root: Path,
    owner_evidence_root: Path,
    aggregation_ref: Mapping[str, Any],
    *,
    evidence_root: Path,
    evidence_root_token: str,
    provider_id: str,
    work_package_id: str,
    check_id: str,
    semantic_check_id: str,
    execution_id: str,
    coverage_ids: Sequence[str],
    validation_obligation_ids: Sequence[str],
    source_paths: Sequence[str],
    toolchain_fingerprint: str,
    canonical_skillguard_root: Path | None = None,
    global_prompt_codex_home: Path | None = None,
) -> dict[str, Any]:
    """Project one replayed current parent into OpenSpec's existing wire.

    This is a format/identity projection only.  It is structurally unable to
    execute a TestMesh child or to repair a missing receipt.
    """

    findings: list[str] = []
    identities = {
        "provider_id": provider_id,
        "work_package_id": work_package_id,
        "check_id": check_id,
        "semantic_check_id": semantic_check_id,
        "execution_id": execution_id,
    }
    if any(not str(value) for value in identities.values()):
        findings.append("openspec_projection_identity_missing")
    if re.fullmatch(r"[A-Z][A-Z0-9_]*", evidence_root_token) is None:
        findings.append("openspec_projection_evidence_root_token_invalid")
    if re.fullmatch(r"sha256:[0-9a-f]{64}", toolchain_fingerprint) is None:
        findings.append("openspec_projection_toolchain_fingerprint_invalid")
    coverage = [str(value) for value in coverage_ids]
    obligations = [str(value) for value in validation_obligation_ids]
    if (
        not coverage
        or any(not value for value in coverage)
        or len(set(coverage)) != len(coverage)
    ):
        findings.append("openspec_projection_coverage_invalid")
    if (
        not obligations
        or any(not value for value in obligations)
        or len(set(obligations)) != len(obligations)
    ):
        findings.append("openspec_projection_validation_obligations_invalid")
    if findings:
        return {
            "schema_version": CURRENT_OPENSPEC_PROJECTION_SCHEMA,
            "status": "blocked",
            "execution_count": 0,
            "findings": findings,
        }

    replay = replay_current_test_mesh_aggregation(
        owner_evidence_root.resolve(),
        aggregation_ref,
        repository_root=repository_root.resolve(),
        canonical_skillguard_root=canonical_skillguard_root,
        global_prompt_codex_home=global_prompt_codex_home,
    )
    if replay.get("status") != "passed":
        return {
            "schema_version": CURRENT_OPENSPEC_PROJECTION_SCHEMA,
            "status": "blocked",
            "execution_count": 0,
            "findings": [
                f"openspec_projection_parent_not_current:{finding}"
                for finding in replay.get("findings", [])
            ] or ["openspec_projection_parent_not_current"],
        }

    aggregation_relative = Path(str(aggregation_ref.get("relative_path", "")))
    aggregation_path = (owner_evidence_root.resolve() / aggregation_relative).resolve()
    aggregation = json.loads(
        filesystem_path(aggregation_path).read_text(encoding="utf-8")
    )
    if not isinstance(aggregation, Mapping):
        return {
            "schema_version": CURRENT_OPENSPEC_PROJECTION_SCHEMA,
            "status": "blocked",
            "execution_count": 0,
            "findings": ["openspec_projection_parent_object_required"],
        }

    source_files, source_findings = _projection_source_files(
        repository_root.resolve(), source_paths
    )
    if source_findings:
        return {
            "schema_version": CURRENT_OPENSPEC_PROJECTION_SCHEMA,
            "status": "blocked",
            "execution_count": 0,
            "findings": source_findings,
        }

    source_manifest_id = _portable_receipt_hash(
        {
            "source_hash_policy": PORTABLE_SOURCE_HASH_POLICY,
            "files": source_files,
        }
    )
    source_manifest = {
        "schema_version": PORTABLE_SOURCE_MANIFEST_SCHEMA,
        "manifest_id": source_manifest_id,
        "source_hash_policy": PORTABLE_SOURCE_HASH_POLICY,
        "files": source_files,
    }
    source_manifest_hash = _portable_receipt_hash(source_manifest)
    source_fingerprint = _portable_receipt_hash(source_files)
    manifest_relative = (
        Path("portable")
        / "source-manifests"
        / f"{source_manifest_id.split(':', 1)[1]}.json"
    )
    evidence_root = evidence_root.resolve()
    durable_write_immutable_json(evidence_root / manifest_relative, source_manifest)

    result_content = {
        "schema_version": CURRENT_OPENSPEC_PROJECTION_RESULT_SCHEMA,
        "status": "passed",
        "execution_count": 0,
        "aggregation": dict(aggregation),
        "aggregation_ref": dict(aggregation_ref),
        "replay": dict(replay),
        "claim_boundary": (
            "This result embeds one already replayed immutable SkillGuard parent; "
            "the projection executes no owner and cannot backfill missing evidence."
        ),
    }
    termination_content = {
        "status": "passed",
        "exit_code": 0,
        "execution_count": 0,
        "cleanup_confirmed": True,
    }
    result_body = canonical_json_bytes(result_content)
    termination_body = canonical_json_bytes(termination_content)
    sidecar_refs: dict[str, str] = {}
    sidecar_hashes: dict[str, str] = {}
    for role, body, suffix in (
        ("stdout", b"", "log"),
        ("stderr", b"", "log"),
        ("result", result_body, "json"),
        ("termination", termination_body, "json"),
    ):
        reference, content_hash = _write_portable_sidecar(
            evidence_root,
            evidence_root_token,
            role=role,
            body=body,
            suffix=suffix,
        )
        sidecar_refs[role] = reference
        sidecar_hashes[role] = content_hash

    result_fingerprint = _portable_receipt_hash(result_content)
    termination_fingerprint = _portable_receipt_hash(termination_content)
    execution_key = _portable_receipt_hash(
        {
            "schema_version": CURRENT_OPENSPEC_PROJECTION_SCHEMA,
            **identities,
            "aggregation_id": aggregation.get("aggregation_id"),
            "aggregation_hash": aggregation.get("aggregation_hash"),
            "aggregation_content_hash": aggregation_ref.get("content_hash"),
            "source_manifest_id": source_manifest_id,
            "toolchain_fingerprint": toolchain_fingerprint,
            "coverage_ids": sorted(coverage),
            "validation_obligation_ids": sorted(obligations),
        }
    )
    semantic_payload = {
        **identities,
        "execution_key": execution_key,
        "source_manifest_id": source_manifest_id,
        "source_manifest_hash": source_manifest_hash,
        "source_hash_policy": PORTABLE_SOURCE_HASH_POLICY,
        "source_fingerprint": source_fingerprint,
        "toolchain_fingerprint": toolchain_fingerprint,
        "result_fingerprint": result_fingerprint,
        "termination_fingerprint": termination_fingerprint,
        "snapshot_policy": "frozen",
        "coverage_ids": sorted(coverage),
        "validation_obligation_ids": sorted(obligations),
        "result_sidecar_hashes": {
            role: sidecar_hashes[role]
            for role in ("stdout", "stderr", "result", "termination")
        },
        "child_receipts": [],
    }
    receipt_id = _portable_receipt_hash(
        {
            "schema_version": PORTABLE_RECEIPT_ENVELOPE_SCHEMA,
            "semantic_identity": semantic_payload,
        }
    )
    receipt_fingerprint = _portable_receipt_hash(
        {"receipt_id": receipt_id, **semantic_payload}
    )
    envelope = {
        "schema_version": PORTABLE_RECEIPT_ENVELOPE_SCHEMA,
        "protocol_version": PORTABLE_RECEIPT_PROTOCOL,
        "root_token": PORTABLE_RECEIPT_ROOT_TOKEN,
        "receipt_id": receipt_id,
        "receipt_fingerprint": receipt_fingerprint,
        **identities,
        "execution_key": execution_key,
        "coverage_ids": sorted(coverage),
        "validation_obligation_ids": sorted(obligations),
        "source_manifest_id": source_manifest_id,
        "source_manifest_ref": _portable_token(
            evidence_root_token, manifest_relative
        ),
        "source_manifest_hash": source_manifest_hash,
        "source_hash_policy": PORTABLE_SOURCE_HASH_POLICY,
        "source_fingerprint": source_fingerprint,
        "toolchain_fingerprint": toolchain_fingerprint,
        "result_fingerprint": result_fingerprint,
        "termination_fingerprint": termination_fingerprint,
        "snapshot_policy": "frozen",
        "sidecar_refs": sidecar_refs,
        "sidecar_hashes": sidecar_hashes,
        "child_receipt_refs": [],
        "child_receipt_hashes": {},
    }
    envelope["envelope_fingerprint"] = _portable_receipt_hash(envelope)
    envelope_relative = (
        Path("portable")
        / "envelopes"
        / f"{receipt_id.split(':', 1)[1]}.json"
    )
    durable_write_immutable_json(evidence_root / envelope_relative, envelope)

    pointer = {
        "schema_version": PORTABLE_RECEIPT_REF_SCHEMA,
        "protocol_version": PORTABLE_RECEIPT_PROTOCOL,
        "root_token": PORTABLE_RECEIPT_ROOT_TOKEN,
        **identities,
        "coverage_ids": sorted(coverage),
        "envelope_ref": _portable_token(evidence_root_token, envelope_relative),
        "envelope_fingerprint": envelope["envelope_fingerprint"],
        "receipt_id": receipt_id,
        "receipt_fingerprint": receipt_fingerprint,
    }
    pointer_relative = Path("portable") / work_package_id / "ref.json"
    _atomic_replace_projection_ref(evidence_root / pointer_relative, pointer)
    return {
        "schema_version": CURRENT_OPENSPEC_PROJECTION_SCHEMA,
        "status": "passed",
        "execution_count": 0,
        "findings": [],
        "receipt_id": receipt_id,
        "receipt_fingerprint": receipt_fingerprint,
        "envelope_fingerprint": envelope["envelope_fingerprint"],
        "receipt_ref": _portable_token(evidence_root_token, pointer_relative),
        "aggregation_id": aggregation.get("aggregation_id"),
        "claim_boundary": (
            "Projection converts one current SkillGuard parent into OpenSpec's "
            "existing portable receipt wire and launches zero owner processes."
        ),
    }


def execute_test_mesh(
    manifest_path: Path,
    repository_root: Path,
    profile_id: str,
    *,
    run_root: Path | None = None,
    skill_root: Path | None = None,
    target_root: Path | None = None,
    owner_evidence_root: Path | None = None,
    mode: str = "plan_only",
    frozen_plan: Mapping[str, Any] | None = None,
    full_admission_reason: str = "",
    freeze_identity: Mapping[str, Any] | None = None,
    installation_receipt_root: Path | None = None,
    canonical_skillguard_root: Path | None = None,
    verified_installation_context: VerifiedInstallationContext | None = None,
    global_prompt_codex_home: Path | None = None,
) -> dict[str, Any]:
    repository_root = canonical_filesystem_path(repository_root)
    try:
        manifest = json.loads(
            filesystem_path(manifest_path).read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, json.JSONDecodeError):
        manifest = {}
    if not isinstance(manifest, Mapping) or manifest.get(
        "schema_version"
    ) != CURRENT_TEST_MESH_MANIFEST_SCHEMA:
        if mode == "owner_execution_only":
            return _blocked_owner_execution(
                profile_id,
                frozen_plan,
                ["legacy_test_mesh_manifest_rejected"],
            )
        return {
            "schema_version": CURRENT_TEST_MESH_PLAN_SCHEMA,
            "artifact_type": "skillguard_test_mesh_execution_plan",
            "status": "blocked",
            "mode": mode,
            "profile_id": profile_id,
            "execution_count": 0,
            "findings": ["legacy_test_mesh_manifest_rejected"],
            "will_reuse_owner_ids": [],
            "will_execute_owner_ids": [],
            "claim_boundary": "Old TestMesh shapes are rejection fixtures only.",
        }
    if mode not in {
        "plan_only",
        "owner_execution_only",
        "aggregation_only",
    }:
        raise ValueError("current_test_mesh_mode_invalid")
    profile = next(
        (
            row
            for row in manifest.get("profiles", [])
            if isinstance(row, Mapping) and row.get("profile_id") == profile_id
        ),
        None,
    )
    full_required = bool(
        isinstance(profile, Mapping)
        and profile.get("full_admission_required") is True
    )
    binding_options_supplied = bool(
        installation_receipt_root
        or canonical_skillguard_root
        or verified_installation_context
        or global_prompt_codex_home
    )
    if mode == "owner_execution_only" and binding_options_supplied:
        return _blocked_owner_execution(
            profile_id,
            frozen_plan,
            ["current_test_mesh_binding_options_only_valid_for_aggregation"],
        )
    if mode == "plan_only" and binding_options_supplied:
        schema_version = (
            CURRENT_TEST_MESH_PLAN_SCHEMA
            if mode == "plan_only"
            else CURRENT_TEST_MESH_OWNER_EXECUTION_SCHEMA
        )
        return {
            "schema_version": schema_version,
            "artifact_type": (
                "skillguard_test_mesh_execution_plan"
                if mode == "plan_only"
                else "skillguard_test_mesh_owner_execution"
            ),
            "status": "blocked",
            "mode": mode,
            "profile_id": profile_id,
            "execution_count": 0,
            "findings": [
                "current_test_mesh_binding_options_only_valid_for_aggregation"
            ],
            "will_reuse_owner_ids": [],
            "will_execute_owner_ids": [],
            "claim_boundary": "External projections are consumed only by final aggregation.",
        }
    if mode == "aggregation_only" and not full_required and binding_options_supplied:
        return {
            "schema_version": CURRENT_TEST_MESH_AGGREGATION_SCHEMA,
            "status": "blocked",
            "mode": mode,
            "profile_id": profile_id,
            "execution_count": 0,
            "findings": [
                "current_test_mesh_external_bindings_only_valid_for_full"
            ],
            "child_receipts": [],
        }
    if run_root is None:
        if mode == "owner_execution_only":
            return _blocked_owner_execution(
                profile_id,
                frozen_plan,
                ["current_test_mesh_run_root_required"],
            )
        return {
            "schema_version": CURRENT_TEST_MESH_PLAN_SCHEMA,
            "artifact_type": "skillguard_test_mesh_execution_plan",
            "status": "blocked",
            "mode": mode,
            "profile_id": profile_id,
            "execution_count": 0,
            "findings": ["current_test_mesh_run_root_required"],
            "will_reuse_owner_ids": [],
            "will_execute_owner_ids": [],
            "claim_boundary": "Current TestMesh consumes one frozen claimed-run snapshot.",
        }
    if skill_root is None or target_root is None:
        if mode == "owner_execution_only":
            return _blocked_owner_execution(
                profile_id,
                frozen_plan,
                ["current_test_mesh_exact_roots_required"],
            )
        return _blocked_current_plan(
            profile_id, ["current_test_mesh_exact_roots_required"]
        )
    if mode == "plan_only":
        if frozen_plan is not None:
            return _blocked_current_plan(
                profile_id,
                ["current_test_mesh_plan_mode_rejects_frozen_plan"],
            )
        return _compile_current_test_mesh_plan(
            manifest_path,
            repository_root,
            run_root.resolve(),
            profile_id,
            skill_root=skill_root.resolve(),
            target_root=target_root.resolve(),
            owner_evidence_root=owner_evidence_root,
            full_admission_reason=full_admission_reason,
            freeze_identity=freeze_identity,
        )
    if mode == "owner_execution_only" and (
        full_admission_reason or freeze_identity is not None
    ):
        return _blocked_owner_execution(
            profile_id,
            frozen_plan,
            ["current_test_mesh_execution_rejects_planning_inputs"],
        )
    if not isinstance(frozen_plan, Mapping):
        if mode == "owner_execution_only":
            return _blocked_owner_execution(
                profile_id,
                frozen_plan,
                ["current_test_mesh_frozen_plan_required"],
            )
        return {
            "schema_version": CURRENT_TEST_MESH_AGGREGATION_SCHEMA,
            "status": "blocked",
            "mode": "aggregation_only",
            "profile_id": profile_id,
            "execution_count": 0,
            "findings": ["current_test_mesh_frozen_plan_required"],
            "child_receipts": [],
        }
    if str(frozen_plan.get("profile_id", "")) != profile_id:
        if mode == "owner_execution_only":
            return _blocked_owner_execution(
                profile_id,
                frozen_plan,
                ["current_test_mesh_frozen_profile_mismatch"],
            )
        return {
            "schema_version": CURRENT_TEST_MESH_AGGREGATION_SCHEMA,
            "status": "blocked",
            "mode": "aggregation_only",
            "profile_id": profile_id,
            "execution_count": 0,
            "findings": ["current_test_mesh_frozen_profile_mismatch"],
            "child_receipts": [],
        }
    if mode == "owner_execution_only":
        return _execute_frozen_current_test_mesh_owners(
            frozen_plan,
            manifest_path,
            repository_root,
            run_root.resolve(),
            skill_root=skill_root.resolve(),
            target_root=target_root.resolve(),
            owner_evidence_root=owner_evidence_root,
        )
    if mode == "aggregation_only":
        installation_binding: Mapping[str, Any] | None = None
        prompt_binding: Mapping[str, Any] | None = None
        if full_required and frozen_plan.get("status") == "passed":
            if installation_receipt_root is None:
                return {
                    "schema_version": CURRENT_TEST_MESH_AGGREGATION_SCHEMA,
                    "status": "blocked",
                    "mode": mode,
                    "profile_id": profile_id,
                    "execution_count": 0,
                    "findings": ["installation_receipt_root_required"],
                    "child_receipts": [],
                }
            try:
                installation_binding = _load_current_installation_binding(
                    repository_root,
                    installation_receipt_root,
                    canonical_skillguard_root=canonical_skillguard_root,
                    verified_installation_context=(
                        verified_installation_context
                    ),
                )
                prompt_binding = _load_global_prompt_currentness_binding(
                    codex_home=global_prompt_codex_home
                )
            except (ExecutionRecordError, OSError) as exc:
                return {
                    "schema_version": CURRENT_TEST_MESH_AGGREGATION_SCHEMA,
                    "status": "blocked",
                    "mode": mode,
                    "profile_id": profile_id,
                    "execution_count": 0,
                    "findings": [str(exc)],
                    "child_receipts": [],
                }
        return _aggregate_frozen_current_test_mesh(
            frozen_plan,
            manifest_path,
            repository_root,
            run_root.resolve(),
            skill_root=skill_root.resolve(),
            target_root=target_root.resolve(),
            owner_evidence_root=owner_evidence_root,
            installation_binding=installation_binding,
            global_prompt_binding=prompt_binding,
        )
