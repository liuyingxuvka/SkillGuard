#!/usr/bin/env python3
"""Plan, execute frozen owners, aggregate, or replay current TestMesh."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from skillguard_utils import emit_json
from skillguard_v2.test_mesh import (
    execute_test_mesh,
    project_current_test_mesh_aggregation_to_openspec_receipt,
    replay_current_test_mesh_aggregation,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--profile", choices=("fast", "focused", "full"))
    action.add_argument(
        "--replay-aggregation-ref",
        help="Read-only replay of one current aggregation reference JSON file.",
    )
    action.add_argument(
        "--project-openspec-receipt",
        help=(
            "Read-only replay one current aggregation reference and project it "
            "into OpenSpec's existing portable receipt wire."
        ),
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
    parser.add_argument("--installation-receipt-root")
    parser.add_argument(
        "--canonical-skillguard-root",
        help=(
            "Exact current canonical SkillGuard skill root used to verify the "
            "installed runtime when full TestMesh runs in an external target repository."
        ),
    )
    parser.add_argument("--global-prompt-codex-home")
    parser.add_argument("--openspec-evidence-root")
    parser.add_argument(
        "--openspec-evidence-root-token", default="SKILLGUARD_EVIDENCE"
    )
    parser.add_argument("--provider-id")
    parser.add_argument("--work-package-id")
    parser.add_argument("--check-id")
    parser.add_argument("--semantic-check-id")
    parser.add_argument("--execution-id")
    parser.add_argument("--coverage", action="append", default=[])
    parser.add_argument(
        "--validation-obligation", action="append", default=[]
    )
    parser.add_argument("--source-path", action="append", default=[])
    parser.add_argument("--toolchain-fingerprint")
    args = parser.parse_args(argv)

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

    if args.project_openspec_receipt:
        forbidden = any(
            (
                args.run_root,
                args.skill_root,
                args.target_root,
                args.frozen_plan,
                args.freeze_identity,
                args.full_admission_reason,
                args.installation_receipt_root,
            )
        ) or args.mode != "plan_only"
        if forbidden:
            parser.error(
                "--project-openspec-receipt is a zero-execution projection and "
                "rejects planning, execution, freeze, and installation options"
            )
        required = {
            "--openspec-evidence-root": args.openspec_evidence_root,
            "--provider-id": args.provider_id,
            "--work-package-id": args.work_package_id,
            "--check-id": args.check_id,
            "--semantic-check-id": args.semantic_check_id,
            "--execution-id": args.execution_id,
            "--toolchain-fingerprint": args.toolchain_fingerprint,
        }
        missing = [name for name, value in required.items() if not value]
        if missing or not args.coverage or not args.validation_obligation or not args.source_path:
            parser.error(
                "--project-openspec-receipt requires "
                + ", ".join(missing)
                + (", --coverage, --validation-obligation, and --source-path" if not missing else " plus --coverage, --validation-obligation, and --source-path")
            )
        reference = json.loads(
            repository_path(args.project_openspec_receipt).read_text(
                encoding="utf-8"
            )
        )
        report = project_current_test_mesh_aggregation_to_openspec_receipt(
            repository_root,
            owner_root,
            reference,
            evidence_root=repository_path(args.openspec_evidence_root),
            evidence_root_token=args.openspec_evidence_root_token,
            provider_id=args.provider_id,
            work_package_id=args.work_package_id,
            check_id=args.check_id,
            semantic_check_id=args.semantic_check_id,
            execution_id=args.execution_id,
            coverage_ids=args.coverage,
            validation_obligation_ids=args.validation_obligation,
            source_paths=args.source_path,
            toolchain_fingerprint=args.toolchain_fingerprint,
            canonical_skillguard_root=canonical_skillguard_root,
            global_prompt_codex_home=prompt_home,
        )
    elif args.replay_aggregation_ref:
        forbidden = any(
            (
                args.run_root,
                args.skill_root,
                args.target_root,
                args.frozen_plan,
                args.freeze_identity,
                args.full_admission_reason,
                args.installation_receipt_root,
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
        if args.mode in {"plan_only", "owner_execution_only"} and (
            args.installation_receipt_root
            or canonical_skillguard_root
            or prompt_home
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
        if (args.installation_receipt_root or canonical_skillguard_root) and (
            args.profile != "full" or args.mode != "aggregation_only"
        ):
            parser.error(
                "installation and canonical SkillGuard bindings are valid only for full aggregation"
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
            installation_receipt_root=(
                repository_path(args.installation_receipt_root)
                if args.installation_receipt_root
                else None
            ),
            canonical_skillguard_root=canonical_skillguard_root,
            global_prompt_codex_home=prompt_home,
        )
    emit_json(report)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
