#!/usr/bin/env python3
"""Audit the current public repository candidate boundary without mutation."""

from __future__ import annotations

import argparse
from pathlib import Path

from skillguard_utils import emit_json
from skillguard_v2.privacy import audit_public_export


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--policy", default=".agents/skills/skillguard/public-export-policy.json")
    args = parser.parse_args(argv)
    root = Path(args.repository_root).resolve()
    report = audit_public_export(root, (root / args.policy).resolve())
    emit_json(report)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
