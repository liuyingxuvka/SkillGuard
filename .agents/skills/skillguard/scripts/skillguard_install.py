#!/usr/bin/env python3
"""Prepare, verify, and optionally activate a complete staged SkillGuard install."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from skillguard_utils import emit_json
from skillguard_v2.installation import activate_stage, prepare_stage, verify_stage


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical-skill-root", required=True)
    parser.add_argument("--stage-root", required=True)
    parser.add_argument("--codex-home")
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args(argv)
    canonical = Path(args.canonical_skill_root).resolve()
    stage = Path(args.stage_root).resolve()
    reports = []
    if args.prepare:
        reports.append(prepare_stage(canonical, stage))
        if reports[-1]["status"] != "passed":
            emit_json({"status": "blocked", "reports": reports})
            return 1
    reports.append(verify_stage(canonical, stage))
    if reports[-1]["status"] != "passed":
        emit_json({"status": "blocked", "reports": reports})
        return 1
    if args.activate:
        codex_home = Path(args.codex_home or os.environ.get("CODEX_HOME", Path.home() / ".codex"))
        reports.append(activate_stage(canonical, stage, codex_home))
    status = "passed" if all(row["status"] == "passed" for row in reports) else reports[-1]["status"]
    emit_json(
        {
            "artifact_type": "skillguard_install_workflow",
            "status": status,
            "reports": reports,
            "claim_boundary": "This workflow mutates the active install only with --activate after stage parity and smoke pass.",
        }
    )
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
