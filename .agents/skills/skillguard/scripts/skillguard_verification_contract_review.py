#!/usr/bin/env python3
"""CLI for SkillGuard-maintained OpenSpec verification-contract review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from skillguard_v2.verification_contract_review import (
    audit_active_verification_contracts,
    review_verification_contract,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--all-active", action="store_true")
    args = parser.parse_args()
    repo = args.repository_root.resolve(strict=True)
    if args.all_active:
        payload = audit_active_verification_contracts(repo)
    else:
        if args.contract is None:
            parser.error("--contract is required unless --all-active is used")
        contract = args.contract if args.contract.is_absolute() else repo / args.contract
        report = None
        if args.report is not None:
            report = args.report if args.report.is_absolute() else repo / args.report
        payload = review_verification_contract(
            contract, repository_root=repo, report_path=report
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
