#!/usr/bin/env python3
"""Run a declared SkillGuard fast, focused, or full TestMesh profile."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from skillguard_utils import emit_json
from skillguard_v2.test_mesh import execute_test_mesh


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, choices=("fast", "focused", "full"))
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--manifest", default=".agents/skills/skillguard/test-mesh.json")
    parser.add_argument("--result-root", default=".skillguard/test-results")
    parser.add_argument("--cancel-file")
    parser.add_argument("--progress-interval-seconds", type=float, default=5.0)
    args = parser.parse_args(argv)
    repository_root = Path(args.repository_root).resolve()

    def progress(event):
        sys.stderr.write(json.dumps(event, sort_keys=True) + "\n")
        sys.stderr.flush()

    report = execute_test_mesh(
        (repository_root / args.manifest).resolve(),
        repository_root,
        args.profile,
        (repository_root / args.result_root).resolve(),
        cancel_file=(repository_root / args.cancel_file).resolve() if args.cancel_file else None,
        progress_interval_seconds=args.progress_interval_seconds,
        progress_callback=progress,
    )
    emit_json(report)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
