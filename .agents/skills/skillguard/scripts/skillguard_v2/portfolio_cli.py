"""CLI handlers for the private SkillGuard portfolio runtime."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from skillguard_utils import emit_json

from .portfolio import (
    apply_guard_change,
    atomic_write_json,
    audit_portfolio,
    current_guard,
    graduate_portfolio_target,
    issue_reuse_ticket,
    portfolio_registry_lock,
    PortfolioRegistryLockError,
)


def _workspace_path(path_text: str, workspace_root: Path) -> Path:
    root = workspace_root.resolve()
    path = Path(path_text)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path must stay under workspace root: {path_text}") from exc
    return path


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _output(payload: Mapping[str, Any], output_text: str, workspace_root: Path) -> None:
    if not output_text or output_text == "-":
        emit_json(payload)
        return
    atomic_write_json(_workspace_path(output_text, workspace_root), payload)


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace-root", default=".")
    parser.add_argument("--registry", required=True)
    parser.add_argument("--output", default="-")


def audit_portfolio_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="skillguard.py audit-portfolio")
    _common(parser)
    parser.add_argument(
        "--runtime-root",
        help="SkillGuard repository, installed skill, scripts, or skillguard_v2 package root",
    )
    parser.add_argument("--candidate", default="")
    args = parser.parse_args(argv)
    workspace = Path(args.workspace_root).resolve()
    registry = _load(_workspace_path(args.registry, workspace))
    guard = current_guard(Path(args.runtime_root).resolve()) if args.runtime_root else current_guard()
    report = audit_portfolio(registry, actual_guard=guard, candidate_skill_id=args.candidate)
    _output(report, args.output, workspace)
    return 0 if report["status"] == "current" else 1


def mark_portfolio_impact_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="skillguard.py mark-portfolio-impact")
    _common(parser)
    parser.add_argument("--change", required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    workspace = Path(args.workspace_root).resolve()
    registry_path = _workspace_path(args.registry, workspace)
    change = _load(_workspace_path(args.change, workspace))
    try:
        if args.write:
            with portfolio_registry_lock(registry_path) as lock:
                report, updated = apply_guard_change(_load(registry_path), change)
                if updated is not None:
                    atomic_write_json(registry_path, updated)
                    report["registry_written"] = True
                else:
                    report["registry_written"] = False
                report["registry_lock_recovered"] = lock["lock_recovered"]
        else:
            report, updated = apply_guard_change(_load(registry_path), change)
            report["registry_written"] = False
    except PortfolioRegistryLockError as exc:
        report = {
            "artifact_type": "skillguard_portfolio_impact_result",
            "status": "blocked",
            "blockers": [{"code": "portfolio_registry_writer_conflict", "detail": str(exc)}],
            "registry_written": False,
        }
        updated = None
    _output(report, args.output, workspace)
    return 0 if updated is not None else 1


def issue_portfolio_reuse_ticket_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="skillguard.py issue-portfolio-reuse-ticket")
    _common(parser)
    parser.add_argument("--request", required=True)
    parser.add_argument("--ticket-output")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    workspace = Path(args.workspace_root).resolve()
    registry_path = _workspace_path(args.registry, workspace)
    request = _load(_workspace_path(args.request, workspace))
    if args.write and not args.ticket_output:
        raise ValueError("--ticket-output is required with --write")
    try:
        if args.write:
            ticket_path = _workspace_path(args.ticket_output, workspace)
            with portfolio_registry_lock(registry_path) as lock:
                report, updated, ticket = issue_reuse_ticket(_load(registry_path), request)
                if updated is not None and ticket is not None:
                    atomic_write_json(ticket_path, ticket)
                    atomic_write_json(registry_path, updated)
                    report["registry_written"] = True
                    report["ticket_written"] = True
                else:
                    report["registry_written"] = False
                    report["ticket_written"] = False
                report["registry_lock_recovered"] = lock["lock_recovered"]
        else:
            report, updated, ticket = issue_reuse_ticket(_load(registry_path), request)
            report["registry_written"] = False
            report["ticket_written"] = False
    except PortfolioRegistryLockError as exc:
        report = {
            "artifact_type": "skillguard_reuse_ticket_result",
            "status": "blocked",
            "blockers": [{"code": "portfolio_registry_writer_conflict", "detail": str(exc)}],
            "registry_written": False,
            "ticket_written": False,
        }
        updated = None
        ticket = None
    _output(report, args.output, workspace)
    return 0 if ticket is not None else 1


def graduate_portfolio_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="skillguard.py graduate-portfolio")
    _common(parser)
    parser.add_argument("--evidence", required=True)
    parser.add_argument(
        "--runtime-root",
        help="SkillGuard repository, installed skill, scripts, or skillguard_v2 package root",
    )
    parser.add_argument("--receipt-output")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    workspace = Path(args.workspace_root).resolve()
    registry_path = _workspace_path(args.registry, workspace)
    guard = current_guard(Path(args.runtime_root).resolve()) if args.runtime_root else current_guard()
    evidence = _load(_workspace_path(args.evidence, workspace))
    if args.write and not args.receipt_output:
        raise ValueError("--receipt-output is required with --write")
    try:
        if args.write:
            receipt_path = _workspace_path(args.receipt_output, workspace)
            with portfolio_registry_lock(registry_path) as lock:
                report, updated, receipt = graduate_portfolio_target(
                    _load(registry_path), evidence, actual_guard=guard
                )
                if updated is not None and receipt is not None:
                    atomic_write_json(receipt_path, receipt)
                    atomic_write_json(registry_path, updated)
                    report["registry_written"] = True
                    report["receipt_written"] = True
                else:
                    report["registry_written"] = False
                    report["receipt_written"] = False
                report["registry_lock_recovered"] = lock["lock_recovered"]
        else:
            report, updated, receipt = graduate_portfolio_target(
                _load(registry_path), evidence, actual_guard=guard
            )
            report["registry_written"] = False
            report["receipt_written"] = False
    except PortfolioRegistryLockError as exc:
        report = {
            "artifact_type": "skillguard_portfolio_graduation_result",
            "status": "blocked",
            "blockers": [{"code": "portfolio_registry_writer_conflict", "detail": str(exc)}],
            "registry_written": False,
            "receipt_written": False,
        }
        updated = None
        receipt = None
    _output(report, args.output, workspace)
    return 0 if receipt is not None else 1


PORTFOLIO_COMMANDS: dict[str, Callable[[list[str]], int]] = {
    "audit-portfolio": audit_portfolio_command,
    "mark-portfolio-impact": mark_portfolio_impact_command,
    "issue-portfolio-reuse-ticket": issue_portfolio_reuse_ticket_command,
    "graduate-portfolio": graduate_portfolio_command,
}
