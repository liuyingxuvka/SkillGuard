"""Current component projection identities and disk-currentness verification."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .wire_identity import wire_hash


CONTENT_IMPACT_PLAN_SCHEMA = "skillguard.content_impact_plan.current"
DERIVED_AUTHORITY_PROJECTION_POLICY_ID = (
    "skillguard.derived_authority_projection.current"
)
_DERIVED_AUTHORITY_FILES = frozenset(
    {"compiled-contract.json", "check-manifest.json"}
)
TEXT_SOURCE_SUFFIXES = frozenset(
    {
        ".py",
        ".json",
        ".md",
        ".toml",
        ".yaml",
        ".yml",
        ".txt",
        ".html",
        ".css",
        ".js",
        ".template",
    }
)
TEXT_SOURCE_NAMES = frozenset({".gitignore", ".gitattributes"})
MARKDOWN_CHECKBOX_STATE_POLICY_ID = "markdown-checkbox-state-v1"


def normalize_markdown_task_checkbox_state(text: str) -> str:
    normalized_lines: list[str] = []
    fence_character = ""
    fence_length = 0
    for line in text.splitlines(keepends=True):
        fence = re.match(r"^\s*(`{3,}|~{3,})", line)
        if fence_character:
            normalized_lines.append(line)
            marker = fence.group(1) if fence else ""
            if (
                marker
                and marker[0] == fence_character
                and len(marker) >= fence_length
            ):
                fence_character = ""
                fence_length = 0
            continue
        if fence:
            marker = fence.group(1)
            fence_character = marker[0]
            fence_length = len(marker)
            normalized_lines.append(line)
            continue
        normalized_lines.append(
            re.sub(
                r"^(\s*-\s+\[)[ xX](\]\s+)",
                r"\1 \2",
                line,
            )
        )
    return "".join(normalized_lines)


def _normalized_text_source(path: Path, text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if path.name.lower() == "tasks.md":
        normalized = normalize_markdown_task_checkbox_state(normalized)
    return normalized


def source_file_hash(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix.lower() in TEXT_SOURCE_SUFFIXES or path.name in TEXT_SOURCE_NAMES:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            pass
        else:
            data = _normalized_text_source(path, text).encode("utf-8")
    return hashlib.sha256(data).hexdigest().upper()


def impact_file_hash(path: Path) -> str:
    """Hash a maintained input without derived-authority feedback loops."""

    candidate = path.resolve(strict=True)
    if candidate.name not in _DERIVED_AUTHORITY_FILES:
        return "sha256:" + source_file_hash(candidate).lower()
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("derived_authority_unreadable") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("derived_authority_not_object")
    semantic = dict(payload)
    for field in (
        "content_impact_plan",
        "contract_hash",
        "manifest_hash",
        "compiled_at",
        "generated_at",
    ):
        semantic.pop(field, None)
    return wire_hash(
        {
            "normalization_policy": DERIVED_AUTHORITY_PROJECTION_POLICY_ID,
            "file_kind": candidate.name,
            "semantic_payload": semantic,
        }
    )


def current_content_projection(
    content_impact_plan: Mapping[str, Any],
    consumer_id: str,
) -> dict[str, Any]:
    if content_impact_plan.get("schema_version") != CONTENT_IMPACT_PLAN_SCHEMA:
        raise ValueError("content_impact_plan_schema_not_current")
    health = content_impact_plan.get("health")
    if not isinstance(health, Mapping) or any(health.get(key) for key in health):
        raise ValueError("content_impact_plan_health_blocked")
    components = content_impact_plan.get("components")
    projections = content_impact_plan.get("projection_consumers")
    if not isinstance(components, list) or not isinstance(projections, list):
        raise ValueError("content_impact_plan_shape_invalid")
    component_index: dict[str, Mapping[str, Any]] = {}
    for component in components:
        if not isinstance(component, Mapping):
            raise ValueError("content_impact_component_invalid")
        component_id = str(component.get("component_id", ""))
        component_hash = str(component.get("component_hash", ""))
        if (
            not component_id
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", component_hash)
            or component_id in component_index
        ):
            raise ValueError("content_impact_component_identity_invalid")
        component_index[component_id] = component
    matches = [
        row
        for row in projections
        if isinstance(row, Mapping) and row.get("consumer_id") == consumer_id
    ]
    if len(matches) != 1:
        raise ValueError("content_projection_consumer_not_unique")
    projection = dict(matches[0])
    expected_fields = {
        "consumer_id",
        "kind",
        "impact_plan_schema_version",
        "impact_policy_id",
        "input_component_ids",
        "projection_declaration_hash",
        "input_projection_hash",
        "consumer_projection_hash",
    }
    if set(projection) != expected_fields:
        raise ValueError("content_projection_shape_invalid")
    component_ids = projection.get("input_component_ids")
    if (
        not isinstance(component_ids, list)
        or not component_ids
        or component_ids != sorted(set(str(value) for value in component_ids))
        or any(component_id not in component_index for component_id in component_ids)
    ):
        raise ValueError("content_projection_components_invalid")
    declaration = {
        "consumer_id": consumer_id,
        "kind": str(projection.get("kind", "")),
        "impact_plan_schema_version": str(
            content_impact_plan.get("schema_version", "")
        ),
        "impact_policy_id": str(content_impact_plan.get("policy_id", "")),
        "input_component_ids": component_ids,
    }
    declaration_hash = wire_hash(declaration)
    input_projection_hash = wire_hash(
        [
            {
                "component_id": component_id,
                "component_hash": component_index[component_id]["component_hash"],
            }
            for component_id in component_ids
        ]
    )
    consumer_projection_hash = wire_hash(
        {
            "projection_declaration_hash": declaration_hash,
            "input_projection_hash": input_projection_hash,
        }
    )
    if (
        projection.get("projection_declaration_hash") != declaration_hash
        or projection.get("input_projection_hash") != input_projection_hash
        or projection.get("consumer_projection_hash") != consumer_projection_hash
    ):
        raise ValueError("content_projection_hash_mismatch")
    return projection


def current_content_projection_from_files(
    content_impact_plan: Mapping[str, Any],
    consumer_id: str,
    *,
    repository_root: Path,
    member_roots: Mapping[str, Path] | None = None,
) -> dict[str, Any]:
    projection = current_content_projection(content_impact_plan, consumer_id)
    components = content_impact_plan.get("components")
    if not isinstance(components, list):
        raise ValueError("content_impact_plan_shape_invalid")
    component_index = {
        str(row.get("component_id", "")): row
        for row in components
        if isinstance(row, Mapping)
    }
    root = repository_root.resolve(strict=True)
    normalized_member_roots: list[tuple[str, Path]] = []
    for prefix_value, member_root_value in (member_roots or {}).items():
        prefix = str(prefix_value).replace("\\", "/").strip("/") + "/"
        if not prefix or prefix == "/":
            raise ValueError("content_projection_member_prefix_invalid")
        member_root = Path(member_root_value).resolve(strict=True)
        normalized_member_roots.append((prefix, member_root))
    normalized_member_roots.sort(key=lambda row: (-len(row[0]), row[0]))

    current_components: list[dict[str, str]] = []
    for component_id in projection["input_component_ids"]:
        component = component_index.get(component_id)
        if not isinstance(component, Mapping):
            raise ValueError("content_impact_component_missing")
        member_paths = component.get("member_paths")
        if (
            not isinstance(member_paths, list)
            or not member_paths
            or member_paths != sorted(set(str(value) for value in member_paths))
        ):
            raise ValueError("content_impact_component_members_invalid")
        current_members: list[dict[str, str]] = []
        for member_path_value in member_paths:
            member_path = str(member_path_value).replace("\\", "/")
            relative = Path(*PurePosixPath(member_path).parts)
            if (
                not member_path
                or PurePosixPath(member_path).is_absolute()
                or any(
                    part in {"", ".", ".."}
                    for part in PurePosixPath(member_path).parts
                )
            ):
                raise ValueError("content_projection_member_path_invalid")
            candidate: Path | None = None
            for prefix, member_root in normalized_member_roots:
                if member_path.startswith(prefix):
                    suffix = member_path[len(prefix) :]
                    candidate = member_root / Path(*PurePosixPath(suffix).parts)
                    try:
                        candidate.resolve(strict=True).relative_to(member_root)
                    except (FileNotFoundError, OSError, ValueError) as exc:
                        raise ValueError("content_projection_member_missing") from exc
                    break
            if candidate is None:
                candidate = root / relative
                try:
                    candidate.resolve(strict=True).relative_to(root)
                except (FileNotFoundError, OSError, ValueError) as exc:
                    raise ValueError("content_projection_member_missing") from exc
            if candidate.is_symlink() or not candidate.is_file():
                raise ValueError("content_projection_member_missing")
            current_members.append(
                {
                    "path": member_path,
                    "content_hash": impact_file_hash(candidate),
                }
            )
        current_component_hash = wire_hash(current_members)
        if current_component_hash != component.get("component_hash"):
            raise ValueError("content_projection_component_stale")
        current_components.append(
            {
                "component_id": component_id,
                "component_hash": current_component_hash,
            }
        )
    if wire_hash(current_components) != projection["input_projection_hash"]:
        raise ValueError("content_projection_input_stale")
    return projection


__all__ = [
    "CONTENT_IMPACT_PLAN_SCHEMA",
    "DERIVED_AUTHORITY_PROJECTION_POLICY_ID",
    "MARKDOWN_CHECKBOX_STATE_POLICY_ID",
    "current_content_projection",
    "current_content_projection_from_files",
    "impact_file_hash",
    "normalize_markdown_task_checkbox_state",
    "source_file_hash",
]
