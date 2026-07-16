#!/usr/bin/env python3
"""Prepare, verify, activate, recover, or roll back one maintained skill."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from skillguard_utils import emit_json
from skillguard_v2.target_installation import (
    activate_target_stage,
    prepare_target_stage,
    recover_target_installations,
    rollback_target_install,
    verify_target_stage,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root")
    parser.add_argument("--skill-root")
    parser.add_argument("--stage-root")
    parser.add_argument("--codex-home")
    parser.add_argument("--skill-id")
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--activate", action="store_true")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--recover", action="store_true")
    group.add_argument("--rollback")
    args = parser.parse_args(argv)
    codex_home = Path(
        args.codex_home or os.environ.get("CODEX_HOME", Path.home() / ".codex")
    )
    if args.recover or args.rollback:
        if not args.skill_id:
            parser.error("--skill-id is required for recovery or rollback")
        if args.prepare or args.activate or args.repository_root or args.skill_root or args.stage_root:
            parser.error("recovery/rollback cannot be combined with preparation inputs")
        report = (
            recover_target_installations(codex_home, args.skill_id)
            if args.recover
            else rollback_target_install(codex_home, args.skill_id, str(args.rollback))
        )
        emit_json(report)
        return 0 if report.get("status") == "passed" else 1
    if not args.repository_root or not args.skill_root or not args.stage_root:
        parser.error("--repository-root, --skill-root, and --stage-root are required")
    repository = Path(args.repository_root)
    skill = Path(args.skill_root)
    stage = Path(args.stage_root)
    reports: list[dict[str, object]] = []
    if args.prepare:
        prepared = prepare_target_stage(repository, skill, stage)
        reports.append(prepared)
        if prepared.get("status") != "passed":
            emit_json({"status": "blocked", "reports": reports})
            return 1
        verification = prepared["verification"]
    else:
        verification = verify_target_stage(repository, skill, stage)
        reports.append(verification)
    if verification.get("status") != "passed":
        emit_json({"status": "blocked", "reports": reports})
        return 1
    if args.activate:
        reports.append(
            activate_target_stage(
                repository,
                skill,
                stage,
                codex_home,
                stage_verification=verification,
            )
        )
    status = "passed" if all(row.get("status") == "passed" for row in reports) else "blocked"
    emit_json(
        {
            "status": status,
            "reports": reports,
            "claim_boundary": "The target installer copies and activates only the exact current installation projection; it executes no target-native command.",
        }
    )
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
