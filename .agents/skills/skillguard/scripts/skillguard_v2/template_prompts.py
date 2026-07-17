"""Generate managed target-skill template-routing guidance from one projection."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Mapping

from .template_adapters import compile_target_template_projection


TARGET_TEMPLATE_PROMPT_BEGIN = "<!-- BEGIN MANAGED VALIDATED TEMPLATE PACK -->"
TARGET_TEMPLATE_PROMPT_END = "<!-- END MANAGED VALIDATED TEMPLATE PACK -->"
TARGET_TEMPLATE_COMPACT_PROMPT_BEGIN = "<!--VTP:"
TARGET_TEMPLATE_COMPACT_PROMPT_END = ":VTP-->"


def render_target_template_routing_section(projection: object, *, compact: bool = False) -> str:
    """Render lifecycle guidance from one or more same-owner projections."""

    raw_projections = (
        list(projection)
        if isinstance(projection, Sequence) and not isinstance(projection, (str, bytes, bytearray))
        else [projection]
    )
    if not raw_projections:
        raise ValueError("at least one target template projection is required")
    records = [compile_target_template_projection(item) for item in raw_projections]
    catalogs = [item.catalog for item in records]
    target_ids = {str(item["target_id"]) for item in raw_projections}
    owner_ids = {str(item["native_owner_id"]) for item in raw_projections}
    if len(target_ids) != 1 or len(owner_ids) != 1:
        raise ValueError("managed target template sections cannot combine different targets or native owners")
    catalog_keys = [(str(item["catalog_id"]), str(item["revision"])) for item in catalogs]
    if len(catalog_keys) != len(set(catalog_keys)):
        raise ValueError("managed target template sections cannot repeat a catalog identity")
    manifests = [manifest for catalog in catalogs for manifest in catalog["templates"]]
    manifest_ids = [str(item["template_id"]) for item in manifests]
    if len(manifest_ids) != len(set(manifest_ids)):
        raise ValueError("managed target template sections cannot repeat a template identity")
    template_ids = manifest_ids
    validator_ids = sorted(
        {
            str(validator["validator_id"])
            for item in manifests
            for validator in item["validators"]
        }
    )
    if compact:
        return (
            TARGET_TEMPLATE_COMPACT_PROMPT_BEGIN
            + "target adapter/catalog;native validation;stale/ambiguous=block;"
            + "preview!=proof;harvest"
            + TARGET_TEMPLATE_COMPACT_PROMPT_END
            + "\n"
        )
    lines = [
        TARGET_TEMPLATE_PROMPT_BEGIN,
        "## Validated Template Pack Routing",
        "",
        "- Target families: " + ", ".join(f"`{item['family_id']}`" for item in catalogs) + f"; native owner: `{next(iter(owner_ids))}`.",
        "- Current catalogs: " + ", ".join(f"`{item['catalog_id']}` revision `{item['revision']}`" for item in catalogs) + ".",
        "- Resolve the task through this Guard's native router first, then ask the target-owned adapter for a current neutral projection; never infer a template from wording or a skill name.",
        "- Preserve the adapter's complete candidate and rejection accounting. Zero candidates may use only the declared validated base; one candidate gets a read-only preview; many candidates require complete dependencies, pairwise compatibility, one field owner, and target-authored dominance or must block as ambiguous.",
        "- Recompute the projection immediately before applying a preview. A stale request, catalog, route, builder, validator, or content identity blocks all writes.",
        "- Hand the selected preview to the target-declared builder and consume every target-native validator receipt. Template structure is not domain validity, completion, installation, release, or publication evidence.",
        "- Record a harvest disposition after creating or materially deepening a reusable model, and keep no-match evidence visible.",
        "- Declared validated bases: " + ", ".join(f"`{item['base_template_id']}`" for item in catalogs) + ".",
        "- Template inventory: " + ", ".join(f"`{item}`" for item in template_ids) + ".",
        "- Native validator inventory: " + ", ".join(f"`{item}`" for item in validator_ids) + ".",
        "- Claim boundaries: " + " ".join(str(item["claim_boundary"]) for item in catalogs),
        TARGET_TEMPLATE_PROMPT_END,
        "",
    ]
    return "\n".join(lines)


def replace_target_template_routing_section(existing: str, managed_section: str) -> tuple[str, str]:
    """Insert or replace only the managed section and preserve all other text."""

    managed_pairs = [
        (TARGET_TEMPLATE_PROMPT_BEGIN, TARGET_TEMPLATE_PROMPT_END),
        (TARGET_TEMPLATE_COMPACT_PROMPT_BEGIN, TARGET_TEMPLATE_COMPACT_PROMPT_END),
    ]
    if not any(begin in managed_section and end in managed_section for begin, end in managed_pairs):
        raise ValueError("managed target template section markers are missing")
    existing_pairs = [
        (begin_marker, end_marker)
        for begin_marker, end_marker in managed_pairs
        if begin_marker in existing or end_marker in existing
    ]
    if len(existing_pairs) > 1:
        raise ValueError("existing target template section markers are duplicated")
    if existing_pairs:
        begin_marker, end_marker = existing_pairs[0]
        begin = existing.find(begin_marker)
        end = existing.find(end_marker)
        if (begin < 0) != (end < 0):
            raise ValueError("existing target template section markers are incomplete")
        if existing.find(begin_marker, begin + 1) >= 0 or existing.find(end_marker, end + 1) >= 0:
            raise ValueError("existing target template section markers are duplicated")
        end += len(end_marker)
        prefix = existing[:begin].rstrip()
        suffix = existing[end:].lstrip("\r\n")
        updated = prefix + "\n\n" + managed_section.rstrip() + "\n"
        if suffix:
            updated += "\n" + suffix
        return updated, "replaced"
    prefix = existing.rstrip()
    updated = (prefix + "\n\n" if prefix else "") + managed_section.rstrip() + "\n"
    return updated, "inserted"


__all__ = [
    "TARGET_TEMPLATE_PROMPT_BEGIN",
    "TARGET_TEMPLATE_COMPACT_PROMPT_BEGIN",
    "TARGET_TEMPLATE_COMPACT_PROMPT_END",
    "TARGET_TEMPLATE_PROMPT_END",
    "render_target_template_routing_section",
    "replace_target_template_routing_section",
]
