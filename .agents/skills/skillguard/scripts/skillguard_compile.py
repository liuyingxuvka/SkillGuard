"""Thin executable facade for the one current SkillGuard contract compiler."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from skillguard_utils import emit_json
from skillguard_v2.contract_compiler import compile_skill_contract


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="skillguard_compile.py")
    parser.add_argument("target", help="Target skill root.")
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--check", action="store_true", help="Check generated parity without writes.")
    args = parser.parse_args(argv)
    result = compile_skill_contract(
        Path(args.target),
        repository_root=Path(args.repository_root),
        write=not args.check,
    )
    emit_json(result.to_dict())
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
