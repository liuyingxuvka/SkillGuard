"""Pure current global-router registry and managed-prompt projections.

The CLI wrapper deliberately lives elsewhere.  Keeping the semantic registry,
prompt, and no-op comparison rules in this small module prevents an unrelated
checker command from invalidating the global router projection.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping, Sequence

from .wire_identity import wire_hash


GLOBAL_REGISTRY_SCHEMA_VERSION = "skillguard.global_registry.current"
GLOBAL_PROMPT_PROJECTION_SCHEMA_VERSION = (
    "skillguard.global_prompt_projection.current"
)
GLOBAL_PROMPT_BEGIN = "<!-- BEGIN MANAGED SKILLGUARD GLOBAL ROUTER -->"
GLOBAL_PROMPT_END = "<!-- END MANAGED SKILLGUARD GLOBAL ROUTER -->"
GLOBAL_ROUTER_SKILL_ID = "skillguard-global-router"
TEMPLATE_PLACEHOLDERS = frozenset(
    {
        "{{validation_execution_policy}}",
        "{{registry_hash}}",
        "{{registry_path}}",
        "{{route_index}}",
    }
)
CURRENT_ROUTE_ENTRYPOINT_FIELDS = (
    "repository_role",
    "maintenance_unit_id",
    "member_skill_id",
    "integration_mode",
    "route_confidence",
    "contract_authority",
    "authority_decision",
    "authority_blockers",
    "contract_source_path",
    "contract_path",
    "check_manifest_path",
    "model_id",
    "function_ids",
    "route_ids",
    "default_route_id",
    "native_route_owner",
    "native_route_bindings",
    "native_check_bindings",
    "phase_native_bindings",
    "may_define_parallel_execution_route",
    "may_define_skillguard_runtime_route",
    "route_doc_paths",
    "handoff_rule",
)
DIAGNOSTIC_ROUTE_ENTRYPOINT_FIELDS = (
    "contract_source_sha256",
    "contract_sha256",
    "contract_hash",
    "check_manifest_sha256",
    "check_manifest_hash",
    "check_declarations_hash",
)
CURRENT_ROUTE_ITEM_FIELDS = frozenset(
    {
        "skill_id",
        "skill_name",
        "description",
        "skill_path",
        "skill_file",
        "skill_sha256",
        "status",
        "use_when",
        "do_not_use_when",
        "route_entrypoint",
        "route_terms",
        "claim_boundary",
    }
)
CURRENT_REGISTRY_FIELDS = frozenset(
    {
        "schema_version",
        "generated_at",
        "router_skill_id",
        "scan_roots",
        "item_count",
        "current_item_count",
        "items",
        "warnings",
        "claim_boundary",
        "diagnostic_inventory_hash",
        "registry_hash",
    }
)
CURRENT_PROMPT_PROJECTION_FIELDS = frozenset(
    {
        "schema_version",
        "generated_at",
        "router_skill_id",
        "registry_hash",
        "registry_path",
        "managed_block_markers",
        "managed_block",
        "route_index",
        "content_projection",
        "template_content_hash",
        "managed_block_content_hash",
        "claim_boundary",
        "projection_identity_hash",
    }
)
WIRE_HASH_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
GLOBAL_ROUTE_STOPWORDS = {
    "and",
    "are",
    "for",
    "from",
    "into",
    "the",
    "this",
    "that",
    "with",
}


def is_global_router_projection_path(
    path: str, skill_root_relative: str
) -> bool:
    """Return whether a maintained member changes global-router behavior."""

    normalized = str(path).replace("\\", "/")
    normalized_root = skill_root_relative.strip("/")
    if normalized_root in {"", "."}:
        relative = normalized
    else:
        prefix = normalized_root + "/"
        if not normalized.startswith(prefix):
            return False
        relative = normalized[len(prefix) :]
    return (
        relative.startswith("scripts/skillguard_v2/global_router_")
        and relative.endswith(".py")
    ) or relative in {
        "scripts/skillguard_v2/wire_identity.py",
        "scripts/skillguard_v2/content_projection.py",
        "scripts/skillguard_v2/validation_execution_policy.py",
        "assets/templates/global_skillguard_prompt_block.md.template",
        "assets/schemas/skillguard_global_registry.schema.json",
        "assets/schemas/skillguard_global_prompt_projection.schema.json",
    }


def current_route_entrypoint_projection(value: object) -> dict[str, Any]:
    entrypoint = value if isinstance(value, Mapping) else {}
    unknown_fields = set(entrypoint) - set(CURRENT_ROUTE_ENTRYPOINT_FIELDS) - set(
        DIAGNOSTIC_ROUTE_ENTRYPOINT_FIELDS
    )
    if unknown_fields:
        raise ValueError("global_route_entrypoint_unknown_field")
    return {
        field: entrypoint.get(field)
        for field in CURRENT_ROUTE_ENTRYPOINT_FIELDS
    }


def current_route_item_projection(item: Mapping[str, Any]) -> dict[str, Any]:
    """Return only fields that can change routing or its typed handoff.

    Whole-file hashes, check identities, generated timestamps, claim text, and
    diagnostics remain auditable in ``diagnostic_inventory_hash`` but cannot
    invalidate an unchanged route.
    """

    return {
        "skill_id": item.get("skill_id"),
        "skill_name": item.get("skill_name"),
        "skill_path": item.get("skill_path"),
        "skill_file": item.get("skill_file"),
        "status": item.get("status"),
        "use_when": list(item.get("use_when", []))
        if isinstance(item.get("use_when"), list)
        else [],
        "do_not_use_when": list(item.get("do_not_use_when", []))
        if isinstance(item.get("do_not_use_when"), list)
        else [],
        "route_terms": sorted(
            set(
                str(value)
                for value in item.get("route_terms", [])
                if isinstance(value, str)
            )
        ),
        "route_entrypoint": current_route_entrypoint_projection(
            item.get("route_entrypoint")
        ),
    }


def task_tokens(text: str) -> set[str]:
    lowered = text.lower()
    return {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9_.:-]{1,}", lowered)
        if len(token) > 2 and token not in GLOBAL_ROUTE_STOPWORDS
    }


def skill_route_score(
    item: Mapping[str, Any], task: str, route_hint: str = ""
) -> tuple[int, list[str]]:
    task_lower = task.lower()
    hint_lower = route_hint.lower().strip()
    skill_id = str(item.get("skill_id") or "").lower()
    skill_name = str(item.get("skill_name") or "").lower()
    terms = {
        str(term).lower()
        for term in item.get("route_terms", [])
        if isinstance(term, str)
    }
    tokens = task_tokens(task)
    score = 0
    reasons: list[str] = []
    if hint_lower and hint_lower in {skill_id, skill_name}:
        score += 1000
        reasons.append("explicit-route-hint")
    if skill_id and skill_id in task_lower:
        score += 40
        reasons.append("skill-id-substring")
    if skill_name and skill_name in task_lower:
        score += 30
        reasons.append("skill-name-substring")
    exact = sorted(tokens & terms)
    if exact:
        score += len(exact) * 4
        reasons.append(f"term-overlap:{','.join(exact[:6])}")
    readme_task = any(
        marker in task_lower
        for marker in (
            "readme",
            "github readme",
            "hero",
            "bilingual",
            "chinese mirror",
            "\u4e2d\u82f1\u53cc\u8bed",
            "\u4e2d\u6587\u955c\u50cf",
            "\u6587\u751f\u56fe",
            "\u9996\u5c4f",
        )
    )
    if skill_id == "readme-showcase-writer" and readme_task:
        score += 180
        reasons.append("readme-showcase-task-bias")
    if (
        skill_id == "skillguard"
        and not readme_task
        and "skillguard" in task_lower
        and any(
            token in tokens
            for token in {
                "audit",
                "check",
                "review",
                "activation",
                "boundary",
                "skill",
            }
        )
    ):
        score += 45
        reasons.append("skillguard-boundary-audit-bias")
    if skill_id == GLOBAL_ROUTER_SKILL_ID and any(
        token in tokens for token in {"global", "router", "registry", "prompt"}
    ):
        score += 120
        reasons.append("global-router-task-bias")
    return score, reasons


def route_candidates(
    registry: Mapping[str, Any], task: str, route_hint: str = ""
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    items = registry.get("items", [])
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, Mapping) or item.get("status") != "current":
            continue
        route_item = current_route_item_projection(item)
        score, reasons = skill_route_score(route_item, task, route_hint)
        if score <= 0:
            continue
        entrypoint = route_item["route_entrypoint"]
        rows.append(
            {
                "skill_id": route_item.get("skill_id"),
                "skill_name": route_item.get("skill_name"),
                "skill_path": route_item.get("skill_path"),
                "use_when": route_item.get("use_when", []),
                "do_not_use_when": route_item.get("do_not_use_when", []),
                "score": score,
                "selection_reasons": reasons,
                **entrypoint,
            }
        )
    return sorted(rows, key=lambda item: (-int(item["score"]), str(item["skill_id"])))


def candidate_handoff_blockers(candidate: Mapping[str, Any]) -> list[str]:
    mode = str(candidate.get("integration_mode") or "")
    blockers: list[str] = []
    authority = str(candidate.get("contract_authority") or "")
    authority_decision = str(candidate.get("authority_decision") or "")
    if authority != "current" or authority_decision != "current":
        blockers.append("global route has no usable typed runtime authority")
    if authority == "current" and authority_decision != "current":
        blockers.append(
            "current global route has an inconsistent runtime authority decision"
        )
    if authority == "current":
        for key in (
            "contract_source_path",
            "contract_path",
            "check_manifest_path",
            "model_id",
        ):
            if not str(candidate.get(key) or "").strip():
                blockers.append(f"current global route is missing {key}")
        if not isinstance(candidate.get("function_ids"), list) or not candidate.get(
            "function_ids"
        ):
            blockers.append("current global route is missing function_ids")
        route_docs = (
            candidate.get("route_doc_paths")
            if isinstance(candidate.get("route_doc_paths"), list)
            else []
        )
        for suffix in (
            "/.skillguard/contract-source.json",
            "/.skillguard/compiled-contract.json",
            "/.skillguard/check-manifest.json",
        ):
            if not any(
                str(path).replace("\\", "/").endswith(suffix)
                for path in route_docs
            ):
                blockers.append(
                    f"current global route handoff is missing {suffix.rsplit('/', 1)[-1]}"
                )
    if mode != "native-integrated":
        return blockers
    if not str(candidate.get("native_route_owner") or "").strip():
        blockers.append("current global route is missing native_route_owner")
    if not isinstance(candidate.get("native_route_bindings"), list) or not candidate.get(
        "native_route_bindings"
    ):
        blockers.append("native or hybrid global route is missing native_route_bindings")
    if not isinstance(candidate.get("native_check_bindings"), list) or not candidate.get(
        "native_check_bindings"
    ):
        blockers.append("current global route is missing native_check_bindings")
    if candidate.get("may_define_parallel_execution_route") is True:
        blockers.append(
            "current global route cannot define a parallel execution route"
        )
    if candidate.get("may_define_skillguard_runtime_route") is True:
        blockers.append(
            "current global route cannot be selected through a SkillGuard-owned runtime route"
        )
    return blockers


def registry_hash(payload: Mapping[str, Any]) -> str:
    current_items = sorted(
        (
            current_route_item_projection(item)
            for item in payload.get("items", [])
            if isinstance(item, Mapping) and item.get("status") == "current"
        ),
        key=lambda item: (str(item.get("skill_path", "")), str(item.get("skill_id", ""))),
    )
    return wire_hash(
        {
            "schema_version": payload.get("schema_version"),
            "router_skill_id": payload.get("router_skill_id"),
            "items": current_items,
        }
    )


def diagnostic_inventory_hash(payload: Mapping[str, Any]) -> str:
    scan_roots = sorted(
        (
            dict(row)
            for row in payload.get("scan_roots", [])
            if isinstance(row, Mapping)
        ),
        key=lambda row: str(row.get("path", "")),
    )
    items = sorted(
        (
            dict(item)
            for item in payload.get("items", [])
            if isinstance(item, Mapping)
        ),
        key=lambda item: (str(item.get("skill_path", "")), str(item.get("skill_id", ""))),
    )
    return wire_hash(
        {
            "scan_roots": scan_roots,
            "items": items,
            "warnings": sorted(set(str(value) for value in payload.get("warnings", []))),
        }
    )


def registry_integrity_failures(payload: object) -> list[str]:
    if not isinstance(payload, Mapping):
        return ["global registry root must be an object"]
    failures: list[str] = []
    if set(payload) != CURRENT_REGISTRY_FIELDS:
        failures.append("registry field set is not current")
    items_value = payload.get("items")
    items = list(items_value) if isinstance(items_value, list) else []
    current_count = sum(
        1
        for item in items
        if isinstance(item, Mapping) and item.get("status") == "current"
    )
    if payload.get("schema_version") != GLOBAL_REGISTRY_SCHEMA_VERSION:
        failures.append("registry schema is not current")
    if payload.get("item_count") != len(items):
        failures.append("registry item_count does not match items")
    if payload.get("current_item_count") != current_count:
        failures.append("registry current_item_count does not match current items")
    canonical_items = sorted(
        (
            item for item in items if isinstance(item, Mapping)
        ),
        key=lambda item: (str(item.get("skill_path", "")), str(item.get("skill_id", ""))),
    )
    if items != canonical_items:
        failures.append("registry items are not in canonical order")
    for item in canonical_items:
        if set(item) != CURRENT_ROUTE_ITEM_FIELDS:
            failures.append("registry item field set is not current")
            break
        if WIRE_HASH_PATTERN.fullmatch(str(item.get("skill_sha256", ""))) is None:
            failures.append("registry item skill_sha256 is not a current wire hash")
            break
        route_terms = item.get("route_terms")
        if (
            not isinstance(route_terms, list)
            or route_terms != sorted(set(str(value) for value in route_terms))
        ):
            failures.append("registry item route_terms are not canonical")
            break
        entrypoint = item.get("route_entrypoint")
        if not isinstance(entrypoint, Mapping):
            failures.append("registry route_entrypoint is not an object")
            break
        unknown_route_fields = (
            set(entrypoint)
            - set(CURRENT_ROUTE_ENTRYPOINT_FIELDS)
            - set(DIAGNOSTIC_ROUTE_ENTRYPOINT_FIELDS)
        )
        if unknown_route_fields:
            failures.append("registry route_entrypoint has unknown fields")
            break
        for field in (
            "contract_source_sha256",
            "contract_sha256",
            "contract_hash",
            "check_manifest_sha256",
            "check_manifest_hash",
            "check_declarations_hash",
        ):
            value = str(entrypoint.get(field, ""))
            if value and WIRE_HASH_PATTERN.fullmatch(value) is None:
                failures.append(
                    f"registry route_entrypoint {field} is not a current wire hash"
                )
                break
        if failures:
            break
    try:
        expected_registry_hash = registry_hash(payload)
    except ValueError as exc:
        failures.append(str(exc))
        expected_registry_hash = ""
    if payload.get("registry_hash") != expected_registry_hash:
        failures.append("registry hash does not match the current route projection")
    if payload.get("diagnostic_inventory_hash") != diagnostic_inventory_hash(
        payload
    ):
        failures.append(
            "diagnostic inventory hash does not match registry diagnostics"
        )
    return failures


def render_prompt_block(
    registry: Mapping[str, Any],
    *,
    registry_path: str,
    template: str,
    policy_id: str,
    policy_lines: Sequence[str],
) -> str:
    placeholders = re.findall(r"\{\{[^{}\n]+\}\}", template)
    if set(placeholders) != TEMPLATE_PLACEHOLDERS or any(
        placeholders.count(value) != 1 for value in TEMPLATE_PLACEHOLDERS
    ):
        raise ValueError("global_prompt_template_placeholder_set_invalid")
    route_rows = sorted(
        (
            item
            for item in registry.get("items", [])
            if isinstance(item, Mapping) and item.get("status") == "current"
        ),
        key=lambda item: (str(item.get("skill_path", "")), str(item.get("skill_id", ""))),
    )
    route_lines: list[str] = []
    for item in route_rows[:120]:
        entrypoint = (
            item.get("route_entrypoint")
            if isinstance(item.get("route_entrypoint"), Mapping)
            else {}
        )
        default_route = str(entrypoint.get("default_route_id") or "")
        mode = str(entrypoint.get("integration_mode") or "")
        route_lines.append(
            f"- `{item.get('skill_id')}` -> {item.get('skill_file')} "
            f"(default_route={default_route or 'none'}, integration={mode or 'unknown'})"
        )
    if len(route_rows) > 120:
        route_lines.append(
            f"- ... {len(route_rows) - 120} additional current route(s) are in the registry JSON."
        )
    if not route_lines:
        route_lines.append(
            "- No current route is available; maintenance routing is blocked until current contracts are installed."
        )
    policy = "\n".join([f"- policy_id: `{policy_id}`", *policy_lines])
    block = (
        template.replace("{{validation_execution_policy}}", policy)
        .replace("{{registry_hash}}", str(registry.get("registry_hash", "")))
        .replace("{{registry_path}}", registry_path or "<not-written>")
        .replace("{{route_index}}", "\n".join(route_lines))
    )
    if "{{" in block or "}}" in block:
        raise ValueError("global_prompt_template_placeholder_unresolved")
    return block.rstrip() + "\n"


def build_prompt_projection(
    registry: Mapping[str, Any],
    *,
    registry_path: str,
    managed_block: str,
    template_content_hash: str,
    content_projection: Mapping[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    route_index = [
        {
            "skill_id": item.get("skill_id"),
            "skill_file": item.get("skill_file"),
            "status": item.get("status"),
            "default_route_id": (
                item.get("route_entrypoint") or {}
            ).get("default_route_id")
            if isinstance(item.get("route_entrypoint"), Mapping)
            else "",
        }
        for item in registry.get("items", [])
        if isinstance(item, Mapping) and item.get("status") == "current"
    ]
    projection: dict[str, Any] = {
        "schema_version": GLOBAL_PROMPT_PROJECTION_SCHEMA_VERSION,
        "generated_at": generated_at,
        "router_skill_id": GLOBAL_ROUTER_SKILL_ID,
        "registry_hash": str(registry.get("registry_hash") or ""),
        "registry_path": registry_path,
        "managed_block_markers": {
            "begin": GLOBAL_PROMPT_BEGIN,
            "end": GLOBAL_PROMPT_END,
        },
        "managed_block": managed_block,
        "route_index": route_index,
        "content_projection": dict(content_projection),
        "template_content_hash": template_content_hash,
        "managed_block_content_hash": "sha256:"
        + hashlib.sha256(managed_block.encode("utf-8")).hexdigest(),
        "claim_boundary": (
            "This prompt projection installs a managed routing block only. It does not prove target skill execution, tests, "
            "fixture coverage, suite automation, package publication, release readiness, code-contract validation, or future AI behavior."
        ),
    }
    projection["projection_identity_hash"] = wire_hash(
        {
            key: value
            for key, value in projection.items()
            if key not in {"generated_at", "claim_boundary", "projection_identity_hash"}
        }
    )
    return projection


def prompt_projection_integrity_failures(payload: object) -> list[str]:
    if not isinstance(payload, Mapping):
        return ["global prompt projection root must be an object"]
    failures: list[str] = []
    if set(payload) != CURRENT_PROMPT_PROJECTION_FIELDS:
        failures.append("global prompt projection field set is not current")
    if payload.get("schema_version") != GLOBAL_PROMPT_PROJECTION_SCHEMA_VERSION:
        failures.append("global prompt projection schema is not current")
    for field in (
        "registry_hash",
        "template_content_hash",
        "managed_block_content_hash",
        "projection_identity_hash",
    ):
        if WIRE_HASH_PATTERN.fullmatch(str(payload.get(field, ""))) is None:
            failures.append(f"global prompt projection {field} is not a current wire hash")
    content_projection = payload.get("content_projection")
    expected_content_fields = {
        "consumer_id",
        "kind",
        "impact_plan_schema_version",
        "impact_policy_id",
        "input_component_ids",
        "projection_declaration_hash",
        "input_projection_hash",
        "consumer_projection_hash",
    }
    if not isinstance(content_projection, Mapping) or set(
        content_projection
    ) != expected_content_fields:
        failures.append("global prompt content projection shape is not current")
    else:
        declaration = {
            "consumer_id": content_projection.get("consumer_id"),
            "kind": content_projection.get("kind"),
            "impact_plan_schema_version": content_projection.get(
                "impact_plan_schema_version"
            ),
            "impact_policy_id": content_projection.get("impact_policy_id"),
            "input_component_ids": content_projection.get(
                "input_component_ids"
            ),
        }
        for field in (
            "projection_declaration_hash",
            "input_projection_hash",
            "consumer_projection_hash",
        ):
            if WIRE_HASH_PATTERN.fullmatch(
                str(content_projection.get(field, ""))
            ) is None:
                failures.append(
                    f"global prompt content projection {field} is not a current wire hash"
                )
        if content_projection.get("projection_declaration_hash") != wire_hash(
            declaration
        ):
            failures.append(
                "global prompt content projection declaration hash mismatch"
            )
        if content_projection.get("consumer_projection_hash") != wire_hash(
            {
                "projection_declaration_hash": content_projection.get(
                    "projection_declaration_hash"
                ),
                "input_projection_hash": content_projection.get(
                    "input_projection_hash"
                ),
            }
        ):
            failures.append(
                "global prompt content projection identity hash mismatch"
            )
    block = payload.get("managed_block")
    if not isinstance(block, str):
        failures.append("global prompt projection managed_block is invalid")
    else:
        actual_block_hash = "sha256:" + hashlib.sha256(
            block.encode("utf-8")
        ).hexdigest()
        if payload.get("managed_block_content_hash") != actual_block_hash:
            failures.append("global prompt managed block content hash mismatch")
    unsigned = {
        key: value
        for key, value in payload.items()
        if key not in {"generated_at", "claim_boundary", "projection_identity_hash"}
    }
    if payload.get("projection_identity_hash") != wire_hash(unsigned):
        failures.append("global prompt projection identity hash mismatch")
    return failures


def replace_managed_block(existing: str, block: str) -> tuple[str, str]:
    if existing.count(GLOBAL_PROMPT_BEGIN) > 1 or existing.count(
        GLOBAL_PROMPT_END
    ) > 1:
        raise ValueError(
            "existing AGENTS.md has duplicate SkillGuard global router managed blocks"
        )
    begin = existing.find(GLOBAL_PROMPT_BEGIN)
    end = existing.find(GLOBAL_PROMPT_END)
    if begin == -1 and end == -1:
        prefix = existing.rstrip()
        separator = "\n\n" if prefix else ""
        return prefix + separator + block.rstrip() + "\n", "inserted"
    if begin == -1 or end == -1 or end < begin:
        raise ValueError(
            "existing AGENTS.md has an incomplete SkillGuard global router managed block"
        )
    end += len(GLOBAL_PROMPT_END)
    updated = (
        existing[:begin].rstrip()
        + "\n\n"
        + block.rstrip()
        + "\n"
        + existing[end:].lstrip("\n")
    )
    return updated, "replaced"


def check_prompt_text(
    text: str,
    registry_hash_value: str,
    *,
    expected_block: str | None,
    policy_id: str,
    policy_lines: Sequence[str],
) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    blockers: list[str] = []
    if text.count(GLOBAL_PROMPT_BEGIN) != 1 or text.count(GLOBAL_PROMPT_END) != 1:
        blockers.append(
            "SkillGuard global router managed block must appear exactly once"
        )
        return failures, blockers
    begin = text.find(GLOBAL_PROMPT_BEGIN)
    end = text.find(GLOBAL_PROMPT_END)
    if end < begin:
        blockers.append(
            "SkillGuard global router managed block markers are out of order"
        )
        return failures, blockers
    block = text[begin : end + len(GLOBAL_PROMPT_END)]
    if expected_block is not None and block.rstrip() != expected_block.rstrip():
        failures.append(
            "SkillGuard global router managed block is not the exact canonical template projection"
        )
    if f"registry_hash: {registry_hash_value}" not in block:
        failures.append(
            "SkillGuard global router managed block is stale for the supplied registry hash"
        )
    if GLOBAL_ROUTER_SKILL_ID not in block:
        failures.append(
            "SkillGuard global router managed block does not name the router skill"
        )
    if expected_block is None:
        blockers.append(
            "SkillGuard global router canonical expected block is required"
        )
    if f"policy_id: `{policy_id}`" not in block or any(
        line not in block for line in policy_lines
    ):
        failures.append(
            "SkillGuard global router managed block is missing the canonical validation execution ownership policy"
        )
    return failures, blockers


def reuse_unchanged_generated(
    existing: object, candidate: Mapping[str, Any]
) -> bool:
    if not isinstance(existing, Mapping):
        return False
    existing_semantic = dict(existing)
    candidate_semantic = dict(candidate)
    existing_semantic.pop("generated_at", None)
    candidate_semantic.pop("generated_at", None)
    return existing_semantic == candidate_semantic


__all__ = [
    "GLOBAL_PROMPT_BEGIN",
    "GLOBAL_PROMPT_END",
    "GLOBAL_PROMPT_PROJECTION_SCHEMA_VERSION",
    "GLOBAL_REGISTRY_SCHEMA_VERSION",
    "GLOBAL_ROUTER_SKILL_ID",
    "CURRENT_ROUTE_ENTRYPOINT_FIELDS",
    "DIAGNOSTIC_ROUTE_ENTRYPOINT_FIELDS",
    "build_prompt_projection",
    "check_prompt_text",
    "current_route_entrypoint_projection",
    "current_route_item_projection",
    "candidate_handoff_blockers",
    "is_global_router_projection_path",
    "route_candidates",
    "skill_route_score",
    "task_tokens",
    "diagnostic_inventory_hash",
    "prompt_projection_integrity_failures",
    "registry_hash",
    "registry_integrity_failures",
    "render_prompt_block",
    "replace_managed_block",
    "reuse_unchanged_generated",
]
