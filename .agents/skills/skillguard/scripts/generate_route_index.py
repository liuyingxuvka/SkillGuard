#!/usr/bin/env python3
"""Generate or check the current public SkillGuard author-route index."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import checker_engine


DEFAULT_OUTPUT = Path(".agents/skills/skillguard/references/skillguard-route-index.json")
SHARED_REFERENCE_PATHS = (
    "references/skillguard-supervisor.md",
    "references/skillguard-execution-depth.md",
    "references/skillguard-test-mesh.md",
    "references/skillguard-assurance-diagnostics.md",
    "references/skillguard-execution-records.md",
    "references/skillguard-portfolio.md",
    "references/skillguard-project-adoption.md",
    "references/skillguard-target-installation.md",
    "references/skillguard-self-host.md",
    "references/validated-template-pack.md",
)


def canonical_bytes(payload: Any) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def build_route_index() -> dict[str, Any]:
    routes = [
        checker_engine.public_route_entry(entry)
        for entry in checker_engine.current_route_entries()
    ]
    route_fingerprint = "sha256:" + hashlib.sha256(canonical_bytes(routes)).hexdigest()
    load_graph = []
    for route in routes:
        selected = str(route["next_reference"])
        conditional = list(route["conditional_references"])
        loaded = ["SKILL.md", selected, *conditional]
        load_graph.append(
            {
                "route_id": route["route_id"],
                "always_loaded": ["SKILL.md"],
                "selected_reference": selected,
                "conditional_references": conditional,
                "excluded_by_default": [
                    path
                    for path in SHARED_REFERENCE_PATHS
                    if path not in {selected, *conditional}
                ],
                "load_order": list(dict.fromkeys(loaded)),
            }
        )
    return {
        "schema_version": "skillguard.author_route_index.v1",
        "route_registry_version": checker_engine.ROUTE_TASK_REGISTRY_VERSION,
        "route_registry_fingerprint": route_fingerprint,
        "selection_contract": {
            "explicit_route_id_allowed": True,
            "declared_predicate_match_allowed": True,
            "keyword_score_allowed": False,
            "zero_match_terminal": "blocked",
            "many_match_terminal": "blocked",
            "fallback_allowed": False,
        },
        "prompt_budget": {
            "entry_shell_max_characters": 12000,
            "single_route_capsule_max_characters": 7000,
            "global_managed_block_max_characters": 9000,
            "minimum_reasoning_headroom_characters": 12000,
        },
        "shared_entry_path": "SKILL.md",
        "routes": routes,
        "selected_route_load_graph": load_graph,
        "claim_boundary": (
            "This generated index routes explicitly registered author-side SkillGuard work only. "
            "It neither governs ordinary consumer runtime nor proves target checks, installation, Git, tag, release, or future AI behavior."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    output = Path(args.output)
    expected = canonical_bytes(build_route_index())
    current = output.read_bytes() if output.is_file() else b""
    current_ok = current == expected
    written = False
    if args.write and not current_ok:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(expected)
        current_ok = True
        written = True
    result = {
        "schema_version": "skillguard.author_route_index_generation.v1",
        "status": "pass" if current_ok else "blocked",
        "ok": current_ok,
        "output": output.as_posix(),
        "written": written,
        "route_count": len(build_route_index()["routes"]),
        "route_registry_version": checker_engine.ROUTE_TASK_REGISTRY_VERSION,
        "claim_boundary": (
            "Generation proves exact route-index projection only; it executes no selected route."
        ),
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"status={result['status']} routes={result['route_count']} written={written}")
    return 0 if current_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
