#!/usr/bin/env python3
"""Plan, execute frozen owners, aggregate, or replay current TestMesh."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from skillguard_utils import emit_json
from skillguard_v2.test_mesh import (
    execute_test_mesh,
    replay_current_test_mesh_aggregation,
)
from skillguard_v2.execution_records import filesystem_path
from skillguard_v2.contract_compiler import canonical_json_bytes


def _pin_invocation_python_runtime() -> None:
    """Make every declared ``python`` owner use this frozen invocation runtime.

    TestMesh is itself launched through the fixed audit Python executable.  A
    child check declared as ``python`` must not silently resolve through a
    WindowsApps shim or another interpreter on PATH, because that changes the
    owner evidence while leaving the frozen plan looking unchanged.  Prefixing
    this process' interpreter directory is deliberately local to this CLI
    invocation; it does not install anything or mutate the user's environment.
    """

    interpreter_dir = str(Path(sys.executable).parent)
    current_path = os.environ.get("PATH", "")
    entries = [entry for entry in current_path.split(os.pathsep) if entry]
    if entries and entries[0].casefold() == interpreter_dir.casefold():
        return
    os.environ["PATH"] = os.pathsep.join(
        [interpreter_dir, *[entry for entry in entries if entry.casefold() != interpreter_dir.casefold()]]
    )


def _write_plan_snapshot(run_root: Path, report: dict[str, object]) -> Path:
    """Persist the exact plan object once so later stages consume one file."""

    path = filesystem_path(run_root / "test-mesh-plan.json")
    body = canonical_json_bytes(report)
    if path.is_file():
        if path.read_bytes() != body:
            raise ValueError("frozen_plan_path_already_contains_different_plan")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    return path


def main(argv: list[str] | None = None) -> int:
    _pin_invocation_python_runtime()
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--profile", choices=("fast", "focused", "full"))
    action.add_argument(
        "--replay-aggregation-ref",
        help="Read-only replay of one current aggregation reference JSON file.",
    )
    parser.add_argument("--repository-root", default=".")
    parser.add_argument(
        "--manifest", default=".agents/skills/skillguard/test-mesh.json"
    )
    parser.add_argument("--run-root")
    parser.add_argument("--skill-root")
    parser.add_argument("--target-root")
    parser.add_argument("--owner-evidence-root")
    parser.add_argument(
        "--mode",
        choices=("plan_only", "owner_execution_only", "aggregation_only"),
        default="plan_only",
    )
    parser.add_argument(
        "--frozen-plan",
        help="Exact plan-only JSON consumed unchanged by owner execution or aggregation.",
    )
    parser.add_argument("--full-admission-reason", default="")
    parser.add_argument("--freeze-identity")
    parser.add_argument(
        "--requested-claim",
        action="append",
        choices=("source_release", "installed_current", "global_router_current"),
        default=None,
        help=(
            "Explicit claim set for the frozen plan. Repeat for each claim; "
            "source_release is always required."
        ),
    )
    parser.add_argument("--installation-receipt-root")
    parser.add_argument(
        "--canonical-skillguard-root",
        help=(
            "Exact current canonical SkillGuard skill root used to verify the "
            "installed runtime when full TestMesh runs in an external target repository."
        ),
    )
    parser.add_argument("--global-prompt-codex-home")
    parser.add_argument(
        "--global-prompt-skill-root",
        action="append",
        default=[],
        help=(
            "Explicit author-side maintained skill root used to re-check the "
            "private global registry during full aggregation or read-only replay. "
            "Repeat for every registered root."
        ),
    )
    parser.add_argument("--output", help="Write the complete machine report to this repository-relative file.")
    parser.add_argument(
        "--full-output",
        action="store_true",
        help="Require --output for the complete machine report; stdout remains a bounded summary.",
    )
    parser.add_argument(
        "--total-budget-seconds",
        type=float,
        help=(
            "Operational monotonic budget for one owner-execution call. "
            "Defaults to 30s/120s/900s for fast/focused/full."
        ),
    )
    parser.add_argument(
        "--diagnostic",
        action="store_true",
        help=(
            "Collect independent owner failures after a normal failure; "
            "never overrides cancellation, cleanup, or budget stops."
        ),
    )
    args = parser.parse_args(argv)
    if args.full_output and not args.output:
        parser.error("--full-output requires --output PATH")

    repository_root = Path(args.repository_root).resolve()

    def repository_path(value: str) -> Path:
        path = Path(value)
        return (
            (repository_root / path).resolve()
            if not path.is_absolute()
            else path.resolve()
        )

    owner_root = (
        repository_path(args.owner_evidence_root)
        if args.owner_evidence_root
        else repository_root / "work" / "verification" / "owner-evidence"
    )
    prompt_home = (
        repository_path(args.global_prompt_codex_home)
        if args.global_prompt_codex_home
        else None
    )
    canonical_skillguard_root = (
        repository_path(args.canonical_skillguard_root)
        if args.canonical_skillguard_root
        else None
    )
    global_prompt_skill_roots = [
        repository_path(value) for value in args.global_prompt_skill_root
    ]

    if args.replay_aggregation_ref:
        forbidden = any(
            (
                args.run_root,
                args.skill_root,
                args.target_root,
                args.frozen_plan,
                args.freeze_identity,
                args.full_admission_reason,
                args.installation_receipt_root,
                args.requested_claim,
                args.total_budget_seconds,
                args.diagnostic,
            )
        ) or args.mode != "plan_only"
        if forbidden:
            parser.error(
                "--replay-aggregation-ref is read-only and rejects planning, "
                "execution, freeze, and installation options"
            )
        reference_path = repository_path(args.replay_aggregation_ref)
        reference = json.loads(reference_path.read_text(encoding="utf-8"))
        report = replay_current_test_mesh_aggregation(
            owner_root,
            reference,
            repository_root=repository_root,
            canonical_skillguard_root=canonical_skillguard_root,
            global_prompt_codex_home=prompt_home,
            global_prompt_skill_roots=global_prompt_skill_roots,
            total_budget_seconds=args.total_budget_seconds,
            diagnostic=args.diagnostic,
        )
    else:
        if not args.run_root or not args.skill_root or not args.target_root:
            parser.error(
                "--profile requires exact --run-root, --skill-root, and --target-root"
            )
        if args.mode in {"owner_execution_only", "aggregation_only"} and not args.frozen_plan:
            parser.error(f"--mode {args.mode} requires --frozen-plan")
        if args.mode == "plan_only" and args.frozen_plan:
            parser.error("--mode plan_only rejects --frozen-plan")
        if args.mode == "owner_execution_only" and (
            args.installation_receipt_root
            or canonical_skillguard_root
            or prompt_home
            or global_prompt_skill_roots
        ):
            parser.error(
                f"{args.mode} rejects installation, canonical-source, and prompt bindings"
            )
        if args.mode == "owner_execution_only" and (
            args.full_admission_reason or args.freeze_identity
        ):
            parser.error(
                "owner-execution mode rejects planning and freeze inputs"
            )
        if canonical_skillguard_root is not None and not args.installation_receipt_root:
            parser.error(
                "--canonical-skillguard-root requires --installation-receipt-root"
            )
        freeze_identity = (
            json.loads(
                repository_path(args.freeze_identity).read_text(encoding="utf-8")
            )
            if args.freeze_identity
            else None
        )
        frozen_plan = (
            json.loads(
                repository_path(args.frozen_plan).read_text(encoding="utf-8")
            )
            if args.frozen_plan
            else None
        )
        report = execute_test_mesh(
            (repository_root / args.manifest).resolve(),
            repository_root,
            args.profile,
            run_root=repository_path(args.run_root),
            skill_root=repository_path(args.skill_root),
            target_root=repository_path(args.target_root),
            owner_evidence_root=owner_root,
            mode=args.mode,
            frozen_plan=frozen_plan,
            full_admission_reason=args.full_admission_reason,
            freeze_identity=freeze_identity,
            requested_claims=args.requested_claim,
            installation_receipt_root=(
                repository_path(args.installation_receipt_root)
                if args.installation_receipt_root
                else None
            ),
            canonical_skillguard_root=canonical_skillguard_root,
            global_prompt_codex_home=prompt_home,
            global_prompt_skill_roots=global_prompt_skill_roots,
        )
        output = dict(report)
        # Stable machine-facing counters let callers advance to the next
        # stage without parsing human-oriented findings or re-running a
        # status helper.  They are projections only; the frozen artifacts
        # remain the authority.
        if args.mode == "plan_only":
            output.setdefault("executed_count", 0)
            output.setdefault(
                "reused_count", len(report.get("will_reuse_owner_ids", []))
            )
            output.setdefault("not_run", [])
        elif args.mode == "owner_execution_only":
            output.setdefault("executed_count", int(report.get("execution_count", 0) or 0))
            output.setdefault(
                "reused_count",
                len(report.get("verified_planned_reuse_owner_ids", []))
                + len(report.get("reused_after_freeze_owner_ids", [])),
            )
            output.setdefault("not_run", list(report.get("not_run_owner_ids", [])))
        elif args.mode == "aggregation_only":
            output.setdefault("executed_count", 0)
            output.setdefault("reused_count", len(report.get("child_receipts", [])))
            output.setdefault("not_run", [])
        if args.mode == "plan_only" and report.get("status") == "passed":
            plan_path = _write_plan_snapshot(repository_path(args.run_root), report)
            output["frozen_plan_path"] = str(plan_path)
        aggregation_ref = report.get("aggregation_ref")
        if args.mode == "aggregation_only" and isinstance(aggregation_ref, dict):
            relative = Path(str(aggregation_ref.get("relative_path", "")))
            aggregation_path = filesystem_path(owner_root / relative)
            output["aggregation_ref_path"] = str(aggregation_path)
        report = output
    emit_json(
        report,
        output=args.output,
        full_output=args.full_output,
        root=repository_root,
    )
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
