#!/usr/bin/env python3
"""CLI entrypoint for generic SkillGuard V2 claimed-run supervision."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from skillguard_v2.supervisor import SupervisorError, supervise_contract_run  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("skill_root", help="Skill root containing .skillguard/contract-source.json")
    parser.add_argument("packet", help="JSON execution packet with request, step evidence, and profiles")
    parser.add_argument("--target-root", required=True, help="Target-local run and artifact root")
    parser.add_argument("--repository-root", required=True, help="Canonical repository root")
    args = parser.parse_args()
    try:
        packet = json.loads(Path(args.packet).read_text(encoding="utf-8"))
        if not isinstance(packet, dict):
            raise ValueError("packet must be a JSON object")
        report = supervise_contract_run(
            Path(args.skill_root),
            Path(args.target_root),
            Path(args.repository_root),
            packet,
        )
    except (OSError, json.JSONDecodeError, ValueError, SupervisorError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps({"ok": True, "report": report}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
