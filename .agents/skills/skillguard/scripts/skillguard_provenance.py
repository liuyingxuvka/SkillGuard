#!/usr/bin/env python3
"""Audit SkillGuard canonical/install/repository/release provenance without mutation."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from skillguard_utils import emit_json
from skillguard_v2.provenance import audit_release_provenance, github_release_snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--canonical-skill-root", default=".agents/skills/skillguard")
    parser.add_argument("--installed-skill-root")
    parser.add_argument("--expected-origin", required=True)
    parser.add_argument("--github-repository", required=True)
    parser.add_argument("--development", action="store_true", help="Report dirty/release drift without requiring release closure.")
    args = parser.parse_args(argv)
    root = Path(args.repository_root).resolve()
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    installed_skill_root = Path(args.installed_skill_root).resolve() if args.installed_skill_root else codex_home / "skills" / "skillguard"
    report = audit_release_provenance(
        root,
        (root / args.canonical_skill_root).resolve(),
        installed_skill_root,
        expected_origin=args.expected_origin,
        release_snapshot=github_release_snapshot(args.github_repository),
        require_clean=not args.development,
        require_installed_parity=True,
        require_release_alignment=not args.development,
    )
    emit_json(report)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
