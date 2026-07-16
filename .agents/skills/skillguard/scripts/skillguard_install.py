#!/usr/bin/env python3
"""Prepare, verify, and optionally activate a complete staged SkillGuard install."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from skillguard_utils import emit_json
from skillguard_v2.installation import (
    activate_stage,
    prepare_stage,
    recover_incomplete_installations,
    rollback_install,
    verify_stage,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical-skill-root")
    parser.add_argument("--stage-root")
    parser.add_argument("--codex-home")
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--activate", action="store_true")
    recovery_group = parser.add_mutually_exclusive_group()
    recovery_group.add_argument("--recover", action="store_true")
    recovery_group.add_argument("--rollback", metavar="TRANSACTION_ID")
    args = parser.parse_args(argv)
    codex_home = Path(args.codex_home or os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    if args.recover or args.rollback:
        if args.prepare or args.activate or args.canonical_skill_root or args.stage_root:
            parser.error("--recover/--rollback cannot be combined with stage preparation or activation")
        report = (
            recover_incomplete_installations(codex_home)
            if args.recover
            else rollback_install(codex_home, str(args.rollback))
        )
        emit_json(report)
        return 0 if report.get("status") in {"passed", "recovered", "rolled_back"} else 1
    if not args.canonical_skill_root or not args.stage_root:
        parser.error("--canonical-skill-root and --stage-root are required for stage verification or activation")
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
        reports.append(
            activate_stage(
                canonical,
                stage,
                codex_home,
                stage_verification=reports[-1],
            )
        )
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
