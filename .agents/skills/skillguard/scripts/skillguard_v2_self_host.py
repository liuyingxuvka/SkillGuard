"""Thin executable facade for the two-stage SkillGuard V2 self-host run."""

from __future__ import annotations

import argparse
from pathlib import Path

from skillguard_utils import emit_json
from skillguard_v2.self_host import run_self_host_bootstrap


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="skillguard_v2_self_host.py")
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--skip-old-full", action="store_true")
    parser.add_argument(
        "--profile",
        action="append",
        choices=("functional", "release", "highest_quality"),
        dest="profiles",
    )
    args = parser.parse_args(argv)
    result = run_self_host_bootstrap(
        Path(args.repository_root),
        run_old_full=not args.skip_old_full,
        profiles=tuple(args.profiles or ("functional", "release")),
    )
    emit_json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
