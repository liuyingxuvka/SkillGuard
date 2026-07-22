"""CLI dispatch handlers for the bounded SkillGuard evidence lifecycle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from skillguard_utils import emit_json

from .evidence_store import (
    DEFAULT_MAX_LOGICAL_BYTES,
    apply_evidence_gc_plan,
    audit_evidence_store,
    plan_evidence_gc,
    purge_evidence_quarantine,
)


def _load_mapping(path_text: str, code: str) -> Mapping[str, Any]:
    path = Path(path_text).resolve()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{code}: unreadable JSON input") from exc
    if not isinstance(payload, Mapping):
        raise ValueError(f"{code}: input must be a JSON object")
    return payload


def _read_only_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--owner-evidence-root", required=True)
    parser.add_argument(
        "--max-logical-bytes",
        type=int,
        default=DEFAULT_MAX_LOGICAL_BYTES,
        help="Maximum permitted decompressed bytes for each verified stream",
    )


def evidence_audit_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="skillguard.py evidence-audit")
    _read_only_common(parser)
    args = parser.parse_args(argv)
    payload = audit_evidence_store(
        Path(args.owner_evidence_root),
        max_logical_bytes=args.max_logical_bytes,
    )
    emit_json(payload)
    return 0 if payload["status"] == "passed" else 1


def evidence_gc_plan_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="skillguard.py evidence-gc-plan")
    _read_only_common(parser)
    args = parser.parse_args(argv)
    payload = plan_evidence_gc(
        Path(args.owner_evidence_root),
        max_logical_bytes=args.max_logical_bytes,
    )
    emit_json(payload)
    return 0 if payload["status"] == "ready" else 1


def evidence_gc_apply_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="skillguard.py evidence-gc-apply")
    parser.add_argument("--owner-evidence-root", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--quarantine-root", required=True)
    args = parser.parse_args(argv)
    payload = apply_evidence_gc_plan(
        Path(args.owner_evidence_root),
        _load_mapping(args.plan, "gc_plan_invalid"),
        quarantine_root=Path(args.quarantine_root),
    )
    emit_json(payload)
    return 0


def evidence_gc_purge_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="skillguard.py evidence-gc-purge")
    parser.add_argument("--owner-evidence-root", required=True)
    parser.add_argument("--apply-receipt", required=True)
    parser.add_argument("--quarantine-root", required=True)
    parser.add_argument("--confirm-plan-hash", required=True)
    parser.add_argument("--grace-seconds", required=True, type=int)
    args = parser.parse_args(argv)
    payload = purge_evidence_quarantine(
        Path(args.owner_evidence_root),
        _load_mapping(args.apply_receipt, "gc_apply_receipt_invalid"),
        quarantine_root=Path(args.quarantine_root),
        confirm_plan_hash=args.confirm_plan_hash,
        grace_seconds=args.grace_seconds,
    )
    emit_json(payload)
    return 0


EVIDENCE_STORE_COMMANDS: dict[str, Callable[[list[str]], int]] = {
    "evidence-audit": evidence_audit_command,
    "evidence-gc-plan": evidence_gc_plan_command,
    "evidence-gc-apply": evidence_gc_apply_command,
    "evidence-gc-purge": evidence_gc_purge_command,
}


__all__ = [
    "EVIDENCE_STORE_COMMANDS",
    "evidence_audit_command",
    "evidence_gc_apply_command",
    "evidence_gc_plan_command",
    "evidence_gc_purge_command",
]
