"""Compile reviewed target-neutral supervision fragments into V2 projections.

Fragments bind generic SkillGuard lifecycle concerns to target-declared steps,
checks, and artifacts.  They cannot add or execute domain checks and are never
runtime authority on their own.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


FRAGMENT_SCHEMA = "skillguard.supervision_fragment.v1"
FRAGMENT_CATALOG_SCHEMA = "skillguard.supervision_fragment_catalog.v1"
FRAGMENT_REFERENCE_FIELDS = frozenset(
    {"fragment_id", "revision", "fragment_digest", "slot_bindings"}
)
FRAGMENT_FIELDS = frozenset(
    {
        "schema_version",
        "fragment_id",
        "revision",
        "description",
        "slots",
        "content_components",
        "claim_boundary",
        "fragment_digest",
    }
)
TARGET_TYPES = frozenset({"step", "check", "artifact"})


@dataclass(frozen=True)
class FragmentFinding:
    code: str
    path: str
    message: str


@dataclass(frozen=True)
class FragmentCompileResult:
    projections: tuple[Mapping[str, Any], ...]
    content_components: Mapping[str, str]
    findings: tuple[FragmentFinding, ...]

    @property
    def ok(self) -> bool:
        return not self.findings


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def fragment_digest(payload: Mapping[str, Any]) -> str:
    return _digest({key: copy.deepcopy(value) for key, value in payload.items() if key != "fragment_digest"})


def fragment_catalog_digest(payload: Mapping[str, Any]) -> str:
    semantic = {key: copy.deepcopy(value) for key, value in payload.items() if key != "catalog_digest"}
    if isinstance(semantic.get("fragments"), list):
        semantic["fragments"] = sorted(semantic["fragments"], key=lambda item: str(item.get("fragment_id", "")))
    return _digest(semantic)


def seal_fragment(payload: Mapping[str, Any]) -> dict[str, Any]:
    semantic = {key: copy.deepcopy(value) for key, value in payload.items() if key != "fragment_digest"}
    return {**semantic, "fragment_digest": _digest(semantic)}


def seal_fragment_catalog(payload: Mapping[str, Any]) -> dict[str, Any]:
    semantic = {key: copy.deepcopy(value) for key, value in payload.items() if key != "catalog_digest"}
    if isinstance(semantic.get("fragments"), list):
        semantic["fragments"] = sorted(semantic["fragments"], key=lambda item: str(item.get("fragment_id", "")))
    return {**semantic, "catalog_digest": _digest(semantic)}


def _unknown(payload: Mapping[str, Any], allowed: frozenset[str], path: str, findings: list[FragmentFinding]) -> None:
    for key in sorted(set(payload) - allowed):
        findings.append(FragmentFinding("unknown_field", f"{path}.{key}", "field is not declared"))


def _text(payload: Mapping[str, Any], key: str, path: str, findings: list[FragmentFinding]) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        findings.append(FragmentFinding("required_text_missing", f"{path}.{key}", "required non-empty string"))
        return ""
    return value.strip()


def validate_fragment(payload: object, path: str = "$") -> tuple[dict[str, Any], tuple[FragmentFinding, ...]]:
    findings: list[FragmentFinding] = []
    if not isinstance(payload, Mapping):
        return {}, (FragmentFinding("expected_object", path, "fragment must be an object"),)
    row = copy.deepcopy(dict(payload))
    _unknown(row, FRAGMENT_FIELDS, path, findings)
    if row.get("schema_version") != FRAGMENT_SCHEMA:
        findings.append(FragmentFinding("fragment_schema_mismatch", f"{path}.schema_version", FRAGMENT_SCHEMA))
    _text(row, "fragment_id", path, findings)
    _text(row, "revision", path, findings)
    _text(row, "description", path, findings)
    _text(row, "claim_boundary", path, findings)
    slots = row.get("slots")
    if not isinstance(slots, list) or not slots:
        findings.append(FragmentFinding("fragment_slots_invalid", f"{path}.slots", "non-empty array required"))
        slots = []
    slot_ids: set[str] = set()
    slot_allowed = frozenset({"slot_id", "target_type", "min_items", "max_items", "purpose"})
    for index, raw in enumerate(slots):
        slot_path = f"{path}.slots[{index}]"
        if not isinstance(raw, Mapping):
            findings.append(FragmentFinding("expected_object", slot_path, "slot must be an object"))
            continue
        slot = dict(raw)
        _unknown(slot, slot_allowed, slot_path, findings)
        slot_id = _text(slot, "slot_id", slot_path, findings)
        if slot_id in slot_ids:
            findings.append(FragmentFinding("duplicate_slot_id", f"{slot_path}.slot_id", slot_id))
        slot_ids.add(slot_id)
        target_type = _text(slot, "target_type", slot_path, findings)
        if target_type and target_type not in TARGET_TYPES:
            findings.append(FragmentFinding("slot_target_type_invalid", f"{slot_path}.target_type", target_type))
        minimum, maximum = slot.get("min_items"), slot.get("max_items")
        if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 0:
            findings.append(FragmentFinding("slot_min_items_invalid", f"{slot_path}.min_items", str(minimum)))
        if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 1:
            findings.append(FragmentFinding("slot_max_items_invalid", f"{slot_path}.max_items", str(maximum)))
        if isinstance(minimum, int) and isinstance(maximum, int) and minimum > maximum:
            findings.append(FragmentFinding("slot_cardinality_invalid", slot_path, "min_items exceeds max_items"))
        _text(slot, "purpose", slot_path, findings)
    components = row.get("content_components")
    if not isinstance(components, list) or not components:
        findings.append(FragmentFinding("fragment_components_invalid", f"{path}.content_components", "non-empty array required"))
        components = []
    component_ids: set[str] = set()
    component_allowed = frozenset({"component_id", "component_kind", "content_hash"})
    for index, raw in enumerate(components):
        component_path = f"{path}.content_components[{index}]"
        if not isinstance(raw, Mapping):
            findings.append(FragmentFinding("expected_object", component_path, "component must be an object"))
            continue
        component = dict(raw)
        _unknown(component, component_allowed, component_path, findings)
        component_id = _text(component, "component_id", component_path, findings)
        if component_id in component_ids:
            findings.append(FragmentFinding("duplicate_component_id", f"{component_path}.component_id", component_id))
        component_ids.add(component_id)
        _text(component, "component_kind", component_path, findings)
        content_hash = _text(component, "content_hash", component_path, findings)
        if content_hash and not (content_hash.startswith("sha256:") and len(content_hash) == 71):
            findings.append(FragmentFinding("component_hash_invalid", f"{component_path}.content_hash", content_hash))
    observed = _text(row, "fragment_digest", path, findings)
    expected = fragment_digest(row)
    if observed and observed != expected:
        findings.append(FragmentFinding("fragment_digest_mismatch", f"{path}.fragment_digest", f"expected {expected}"))
    return row, tuple(findings)


def load_fragment_catalog(path: Path) -> tuple[dict[str, Any], tuple[FragmentFinding, ...]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, (FragmentFinding("fragment_catalog_unreadable", "$.fragment_catalog", type(exc).__name__),)
    findings: list[FragmentFinding] = []
    if not isinstance(raw, Mapping):
        return {}, (FragmentFinding("expected_object", "$", "catalog must be an object"),)
    catalog = copy.deepcopy(dict(raw))
    _unknown(catalog, frozenset({"schema_version", "fragments", "catalog_digest", "claim_boundary"}), "$", findings)
    if catalog.get("schema_version") != FRAGMENT_CATALOG_SCHEMA:
        findings.append(FragmentFinding("fragment_catalog_schema_mismatch", "$.schema_version", FRAGMENT_CATALOG_SCHEMA))
    _text(catalog, "claim_boundary", "$", findings)
    fragments = catalog.get("fragments")
    if not isinstance(fragments, list) or not fragments:
        findings.append(FragmentFinding("fragment_catalog_empty", "$.fragments", "non-empty array required"))
        fragments = []
    ids: set[str] = set()
    for index, fragment in enumerate(fragments):
        normalized, fragment_findings = validate_fragment(fragment, f"$.fragments[{index}]")
        findings.extend(fragment_findings)
        fragment_id = str(normalized.get("fragment_id", ""))
        if fragment_id in ids:
            findings.append(FragmentFinding("duplicate_fragment_id", f"$.fragments[{index}].fragment_id", fragment_id))
        ids.add(fragment_id)
    observed = _text(catalog, "catalog_digest", "$", findings)
    expected = fragment_catalog_digest(catalog)
    if observed and observed != expected:
        findings.append(FragmentFinding("fragment_catalog_digest_mismatch", "$.catalog_digest", f"expected {expected}"))
    return catalog, tuple(findings)


def compile_supervision_fragment_refs(
    *,
    references: object,
    model: Mapping[str, Any],
    binding: Mapping[str, Any],
    catalog_path: Path,
) -> FragmentCompileResult:
    catalog, catalog_findings = load_fragment_catalog(catalog_path)
    findings = list(catalog_findings)
    if not isinstance(references, list):
        findings.append(FragmentFinding("fragment_references_invalid", "$.supervision_fragment_refs", "must be an array"))
        references = []
    fragment_index = {
        str(item.get("fragment_id", "")): dict(item)
        for item in catalog.get("fragments", [])
        if isinstance(item, Mapping)
    }
    target_inventory = {
        "step": {str(item.get("step_id", "")) for item in model.get("steps", [])},
        "check": {str(item.get("check_id", "")) for item in binding.get("checks", [])},
        "artifact": {str(item.get("artifact_id", "")) for item in binding.get("artifacts", [])},
    }
    projections: list[dict[str, Any]] = []
    components: dict[str, str] = {}
    seen_refs: set[str] = set()
    for index, raw in enumerate(references):
        path = f"$.supervision_fragment_refs[{index}]"
        if not isinstance(raw, Mapping):
            findings.append(FragmentFinding("expected_object", path, "reference must be an object"))
            continue
        reference = dict(raw)
        _unknown(reference, FRAGMENT_REFERENCE_FIELDS, path, findings)
        fragment_id = _text(reference, "fragment_id", path, findings)
        if fragment_id in seen_refs:
            findings.append(FragmentFinding("duplicate_fragment_reference", f"{path}.fragment_id", fragment_id))
        seen_refs.add(fragment_id)
        fragment = fragment_index.get(fragment_id)
        if fragment is None:
            findings.append(FragmentFinding("fragment_reference_unknown", f"{path}.fragment_id", fragment_id))
            continue
        if reference.get("revision") != fragment.get("revision"):
            findings.append(FragmentFinding("fragment_revision_mismatch", f"{path}.revision", str(reference.get("revision", ""))))
        if reference.get("fragment_digest") != fragment.get("fragment_digest"):
            findings.append(FragmentFinding("fragment_reference_stale", f"{path}.fragment_digest", str(reference.get("fragment_digest", ""))))
        raw_bindings = reference.get("slot_bindings")
        if not isinstance(raw_bindings, Mapping):
            findings.append(FragmentFinding("slot_bindings_invalid", f"{path}.slot_bindings", "must be an object"))
            raw_bindings = {}
        slots = {str(item["slot_id"]): dict(item) for item in fragment.get("slots", []) if isinstance(item, Mapping)}
        unknown_slots = set(raw_bindings) - set(slots)
        missing_slots = set(slots) - set(raw_bindings)
        for slot_id in sorted(unknown_slots):
            findings.append(FragmentFinding("slot_binding_unknown", f"{path}.slot_bindings.{slot_id}", slot_id))
        for slot_id in sorted(missing_slots):
            findings.append(FragmentFinding("slot_binding_missing", f"{path}.slot_bindings.{slot_id}", slot_id))
        compiled_bindings: list[dict[str, Any]] = []
        for slot_id, slot in slots.items():
            values = raw_bindings.get(slot_id, [])
            if not isinstance(values, list) or any(not isinstance(item, str) or not item for item in values):
                findings.append(FragmentFinding("slot_binding_ids_invalid", f"{path}.slot_bindings.{slot_id}", "must be a string array"))
                values = []
            ids = list(dict.fromkeys(str(item) for item in values))
            if len(ids) != len(values):
                findings.append(FragmentFinding("slot_binding_duplicate_id", f"{path}.slot_bindings.{slot_id}", slot_id))
            minimum, maximum = int(slot["min_items"]), int(slot["max_items"])
            if len(ids) < minimum or len(ids) > maximum:
                findings.append(FragmentFinding("slot_binding_cardinality", f"{path}.slot_bindings.{slot_id}", f"expected {minimum}..{maximum}, got {len(ids)}"))
            target_type = str(slot["target_type"])
            for target_id in ids:
                if target_id not in target_inventory[target_type]:
                    findings.append(FragmentFinding("slot_binding_target_unknown", f"{path}.slot_bindings.{slot_id}", target_id))
            compiled_bindings.append(
                {
                    "slot_id": slot_id,
                    "target_type": target_type,
                    "target_ids": sorted(ids),
                }
            )
        projections.append(
            {
                "fragment_id": fragment_id,
                "revision": fragment.get("revision"),
                "fragment_digest": fragment.get("fragment_digest"),
                "slot_bindings": sorted(compiled_bindings, key=lambda item: item["slot_id"]),
                "claim_boundary": fragment.get("claim_boundary"),
            }
        )
        components[f"supervision_fragment:{fragment_id}"] = str(fragment.get("fragment_digest", ""))
        for component in fragment.get("content_components", []):
            if isinstance(component, Mapping):
                components[f"fragment_component:{component.get('component_id', '')}"] = str(component.get("content_hash", ""))
    return FragmentCompileResult(
        projections=tuple(sorted(projections, key=lambda item: str(item["fragment_id"]))),
        content_components=dict(sorted(components.items())),
        findings=tuple(findings),
    )


__all__ = [
    "FRAGMENT_CATALOG_SCHEMA",
    "FRAGMENT_FIELDS",
    "FRAGMENT_REFERENCE_FIELDS",
    "FRAGMENT_SCHEMA",
    "FragmentCompileResult",
    "FragmentFinding",
    "compile_supervision_fragment_refs",
    "fragment_catalog_digest",
    "fragment_digest",
    "load_fragment_catalog",
    "seal_fragment",
    "seal_fragment_catalog",
    "validate_fragment",
]
