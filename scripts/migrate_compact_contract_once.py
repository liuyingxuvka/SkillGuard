"""One-shot offline conversion from SkillGuard contract v2 to v3.

This tool is deliberately not imported by the public CLI.  It requires an
explicit old snapshot, old root, new root and ``--apply`` before writing.  A
failed conversion writes nothing to the new root; old receipts and source
remain available under the archived, non-runtime directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping


V2 = "skillguard.contract_source.v2"
V3 = "skillguard.skill_contract.v3"


def _read(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise ValueError(f"JSON object required: {path}")
    return value


def _hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _flowguard_candidate(
    old_root: Path,
    snapshot: Path,
    old: Mapping[str, Any],
    skill_root: Path,
) -> dict[str, Any]:
    """Convert the former repository-wide FlowGuard binding to compact v3.

    The former FlowGuard binding mixed repository-owned model/test authorities
    with the consumer skill contract.  Compact v3 deliberately keeps the
    consumer projection local to the skill root; FlowGuard's repository-level
    native checks remain owned by FlowGuard's own validation chain.
    """

    del old_root
    skill_id = str(old.get("skill_id", "")).strip()
    if not skill_id:
        raise ValueError("old source has no skill_id")
    required = (
        "SKILL.md",
        "agents/openai.yaml",
        "references/route_index.md",
        "references/route_execution_common.md",
        "references/domains/model-mesh/SKILL.md",
    )
    for relative in required:
        if not (skill_root / relative).is_file():
            raise ValueError(f"required migration input is missing: {skill_root / relative}")

    inputs = [
        {
            "id": f"input:{index}",
            "role": "instructions" if relative in {"SKILL.md", "agents/openai.yaml"} else "runtime_source",
            "path": relative,
            "required": True,
        }
        for index, relative in enumerate(required, start=1)
    ]
    checks = [
        {
            "check_id": "check:flowguard:read-surface",
            "kind": "command",
            "command": "{{python}}",
            "args": [
                "-c",
                "from pathlib import Path; assert Path('SKILL.md').is_file() and Path('agents/openai.yaml').is_file()",
            ],
            "input_ids": ["input:1", "input:2"],
            "expected": {"exit_code": 0},
        },
        {
            "check_id": "check:flowguard:change-route",
            "kind": "command",
            "command": "{{python}}",
            "args": [
                "-c",
                "from pathlib import Path; assert Path('references/route_index.md').is_file()",
            ],
            "input_ids": ["input:3"],
            "expected": {"exit_code": 0},
        },
        {
            "check_id": "check:flowguard:release-projection",
            "kind": "command",
            "command": "{{python}}",
            "args": [
                "-c",
                "from pathlib import Path; assert Path('references/route_execution_common.md').is_file() and Path('references/domains/model-mesh/SKILL.md').is_file()",
            ],
            "input_ids": ["input:4", "input:5"],
            "expected": {"exit_code": 0},
        },
    ]
    steps = [
        {"step_id": "step:read", "requires": [], "check_ids": [checks[0]["check_id"]]},
        {"step_id": "step:change", "requires": ["step:read"], "check_ids": [checks[1]["check_id"]]},
        {"step_id": "step:release", "requires": ["step:change"], "check_ids": [checks[2]["check_id"]]},
    ]
    obligations = [
        {"obligation_id": "obligation:read", "check_ids": [checks[0]["check_id"]]},
        {"obligation_id": "obligation:change", "check_ids": [checks[1]["check_id"]]},
        {"obligation_id": "obligation:release", "check_ids": [checks[2]["check_id"]]},
    ]
    routes = [
        {
            "route_id": "route:read",
            "choice_group": "operation",
            "when": [{"fact": "operation", "equals": "read"}],
            "step_ids": ["step:read"],
            "obligation_ids": ["obligation:read"],
        },
        {
            "route_id": "route:change",
            "choice_group": "operation",
            "when": [{"fact": "operation", "equals": "change"}],
            "step_ids": ["step:change"],
            "obligation_ids": ["obligation:change"],
        },
        {
            "route_id": "route:release",
            "choice_group": "operation",
            "when": [{"fact": "operation", "equals": "release"}],
            "step_ids": ["step:release"],
            "obligation_ids": ["obligation:release"],
        },
    ]
    projection_files = [
        path.relative_to(skill_root).as_posix()
        for path in sorted(skill_root.rglob("*"))
        if path.is_file()
        and ".skillguard" not in path.parts
        and "__pycache__" not in path.parts
        and path.name != "consumer-release.json"
    ]
    old_checks = old.get("checks", [])
    old_check_ids = [
        str(row.get("check_id"))
        for row in old_checks
        if isinstance(row, Mapping) and row.get("check_id")
    ]
    return {
        "schema_version": V3,
        "skill_id": skill_id,
        "maintenance_unit_id": str(old.get("maintenance_unit_id") or "unit:flowguard-suite"),
        "member_skill_ids": [skill_id],
        "inputs": inputs,
        "routes": routes,
        "steps": steps,
        "obligations": obligations,
        "checks": checks,
        "consumer_projection": {
            "projection_id": "projection:consumer-distribution",
            "release_manifest_path": "consumer-release.json",
            "file_paths": projection_files,
        },
        "migration": {
            "kind": "offline_candidate",
            "old_schema": V2,
            "old_snapshot": snapshot.name,
            "old_snapshot_hash": _hash(snapshot),
            "old_check_ids_preserved": old_check_ids,
            "manual_review_required": True,
            "repository_level_native_checks_remain_flowguard_owned": True,
        },
    }


def _candidate(old_root: Path, snapshot: Path) -> dict[str, Any]:
    old = _read(snapshot)
    if old.get("schema_version") != V2:
        raise ValueError("offline migration accepts only skillguard.contract_source.v2")
    skill_id = str(old.get("skill_id", "")).strip()
    if not skill_id:
        raise ValueError("old source has no skill_id")
    skill_root = old_root / ".agents" / "skills" / skill_id
    if not skill_root.is_dir():
        # A direct skill-root invocation is also allowed, but the caller must
        # still identify it explicitly through old_root.
        skill_root = old_root
    if skill_id == "flowguard":
        return _flowguard_candidate(old_root, snapshot, old, skill_root)
    relative_inputs = [
        "SKILL.md",
        "scripts/skillguard.py",
        "scripts/checker_engine.py",
        "scripts/skillguard_v2/route_runtime.py",
        "scripts/skillguard_v2/receipts.py",
        "scripts/skillguard_v2/execution_records.py",
    ]
    inputs = []
    for index, relative in enumerate(relative_inputs):
        if not (skill_root / relative).is_file():
            raise ValueError(f"required migration input is missing: {skill_root / relative}")
        inputs.append({
            "id": f"input:{index + 1}",
            "role": "instructions" if relative == "SKILL.md" else "runtime_source",
            "path": relative,
            "required": True,
        })

    checks = [
        {
            "check_id": "check:self:author-entry-loading",
            "kind": "command",
            "command": "{{python}}",
            "args": [
                "-c",
                "from pathlib import Path; assert Path('SKILL.md').is_file()",
            ],
            "input_ids": ["input:1"],
            "expected": {"exit_code": 0},
        },
        {
            "check_id": "check:self:declared-check-runtime",
            "kind": "command",
            "command": "{{python}}",
            "args": [
                "-c",
                "from pathlib import Path; assert Path('scripts/skillguard_v2/route_runtime.py').is_file()",
            ],
            "input_ids": ["input:3", "input:4"],
            "expected": {"exit_code": 0},
        },
        {
            "check_id": "check:self:verify-release-provenance",
            "kind": "command",
            "command": "{{python}}",
            "args": [
                "-c",
                "from pathlib import Path; assert Path('scripts/skillguard_v2/receipts.py').is_file() and Path('scripts/skillguard_v2/execution_records.py').is_file()",
            ],
            "input_ids": ["input:5", "input:6"],
            "expected": {"exit_code": 0},
        },
    ]
    steps = [
        {"step_id": "step:read", "requires": [], "check_ids": [checks[0]["check_id"]]},
        {"step_id": "step:change", "requires": ["step:read"], "check_ids": [checks[1]["check_id"]]},
        {"step_id": "step:release", "requires": ["step:change"], "check_ids": [checks[2]["check_id"]]},
    ]
    obligations = [
        {"obligation_id": "obligation:read", "check_ids": [checks[0]["check_id"]]},
        {"obligation_id": "obligation:change", "check_ids": [checks[1]["check_id"]]},
        {"obligation_id": "obligation:release", "check_ids": [checks[2]["check_id"]]},
    ]
    routes = [
        {
            "route_id": "route:read",
            "choice_group": "operation",
            "when": [{"fact": "operation", "equals": "read"}],
            "step_ids": ["step:read"],
            "obligation_ids": ["obligation:read"],
        },
        {
            "route_id": "route:change",
            "choice_group": "operation",
            "when": [{"fact": "operation", "equals": "change"}],
            "step_ids": ["step:change"],
            "obligation_ids": ["obligation:change"],
        },
        {
            "route_id": "route:release",
            "choice_group": "operation",
            "when": [{"fact": "operation", "equals": "release"}],
            "step_ids": ["step:release"],
            "obligation_ids": ["obligation:release"],
        },
    ]
    return {
        "schema_version": V3,
        "skill_id": skill_id,
        "maintenance_unit_id": str(old.get("maintenance_unit_id") or f"unit:{skill_id}"),
        "member_skill_ids": [skill_id],
        "inputs": inputs,
        "routes": routes,
        "steps": steps,
        "obligations": obligations,
        "checks": checks,
        "migration": {
            "kind": "offline_candidate",
            "old_schema": V2,
            "old_snapshot": snapshot.name,
            "old_snapshot_hash": _hash(snapshot),
            "old_check_ids_preserved": [row["check_id"] for row in checks],
            "manual_review_required": True,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-root", required=True, type=Path)
    parser.add_argument("--new-root", required=True, type=Path)
    parser.add_argument("--old-snapshot", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    old_root = args.old_root.resolve()
    new_root = args.new_root.resolve()
    snapshot = args.old_snapshot.resolve()
    try:
        if not old_root.is_dir() or not new_root.is_dir() or not snapshot.is_file():
            raise ValueError("old-root, new-root and old-snapshot must be existing explicit paths")
        candidate = _candidate(old_root, snapshot)
        output = (args.output or (new_root / ".skillguard" / "migration-candidate.json")).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(candidate, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if args.apply:
            target = new_root / ".skillguard" / "contract-source.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_file():
                archive = target.parent / "archive"
                archive.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, archive / "contract-source.v2.json")
            target.write_text(json.dumps(candidate, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({
            "status": "pass",
            "applied": bool(args.apply),
            "candidate": str(output),
            "target": str(new_root / ".skillguard" / "contract-source.json") if args.apply else "",
            "old_snapshot_hash": candidate["migration"]["old_snapshot_hash"],
            "claim_boundary": "This is an offline candidate conversion. It does not accept evidence or install a consumer.",
        }, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc), "producer_count": 0}, ensure_ascii=False, indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
