"""Regression checks for SkillGuard's explicit self semantic map."""

from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET_ROOT = ROOT / ".agents" / "skills" / "skillguard"
sys.path.insert(0, str((TARGET_ROOT / "scripts").resolve()))

import checker_engine  # noqa: E402
from skillguard_v2.surface_inventory import discover_full_source_surfaces  # noqa: E402
from skillguard_v2.surface_inventory_authoring import CURRENT_MODEL_OBLIGATIONS  # noqa: E402


def _canonical_without_hash(payload: dict[str, object], field: str) -> bytes:
    unsigned = dict(payload)
    unsigned.pop(field, None)
    return json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def test_self_semantic_map_is_current_and_explicit() -> None:
    inventory = json.loads((TARGET_ROOT / ".skillguard" / "surface-inventory.json").read_text(encoding="utf-8"))
    semantic_map = json.loads((TARGET_ROOT / ".skillguard" / "surface-semantic-map.json").read_text(encoding="utf-8"))
    assert semantic_map["schema_version"] == "skillguard.surface_semantic_map.v1"
    assert semantic_map["current_obligation_ids"] == list(CURRENT_MODEL_OBLIGATIONS)
    assert semantic_map["full_surface_ids"] == inventory["full_surface_ids"]
    assert semantic_map["source_discovery_fingerprint"] == inventory["full_discovery_fingerprint"]
    assert semantic_map["map_hash"] == "sha256:" + hashlib.sha256(
        _canonical_without_hash(semantic_map, "map_hash")
    ).hexdigest()
    assert all(row["decision"] in {"explicit-author-rule", "explicit-author-component-group-closure"} for row in semantic_map["surface_bindings"])


def test_self_semantic_map_rejects_old_surface_local_obligation_ids() -> None:
    inventory = json.loads((TARGET_ROOT / ".skillguard" / "surface-inventory.json").read_text(encoding="utf-8"))
    assert inventory["current_obligation_ids"] == list(CURRENT_MODEL_OBLIGATIONS)
    assert all(
        set(row["model_obligation_ids"]).issubset(set(CURRENT_MODEL_OBLIGATIONS))
        and not any(value.startswith("obligation:surface:") for value in row["obligation_ids"])
        for row in inventory["full_surfaces"]
    )


def test_self_semantic_map_closes_every_component_group() -> None:
    inventory = json.loads((TARGET_ROOT / ".skillguard" / "surface-inventory.json").read_text(encoding="utf-8"))
    groups: dict[str, set[tuple[str, ...]]] = defaultdict(set)
    for row in inventory["full_surfaces"]:
        if row["review_granularity"] == "component":
            groups[row["review_group_id"]].add(tuple(row["model_obligation_ids"]))
    assert groups
    assert all(len(obligation_sets) == 1 for obligation_sets in groups.values())


def test_self_semantic_map_fingerprint_matches_fresh_source_observation() -> None:
    semantic_map = json.loads((TARGET_ROOT / ".skillguard" / "surface-semantic-map.json").read_text(encoding="utf-8"))
    scan = discover_full_source_surfaces(
        TARGET_ROOT,
        command_surface=checker_engine.current_checker_command_surface(),
        route_entries=checker_engine.current_route_entries(),
        command_handlers=checker_engine.COMMANDS,
    )
    assert scan.findings == ()
    assert scan.discovery_fingerprint == semantic_map["source_discovery_fingerprint"]
    assert [surface.surface_id for surface in sorted(scan.surfaces, key=lambda item: item.surface_id)] == semantic_map["full_surface_ids"]
