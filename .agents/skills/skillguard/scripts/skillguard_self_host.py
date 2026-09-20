"""Thin executable facade for the single-authority SkillGuard self-host run."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Mapping

from skillguard_utils import emit_json
from skillguard_v2.self_host import (
    SELF_HOST_CURRENT_RECEIPT_RELATIVE_PATH,
    SelfHostError,
    claim_current_self_host_run,
    finalize_current_self_host_from_frozen_mesh,
)


SELF_HOST_CLI_TERMINAL_SCHEMA = "skillguard.self_host_cli_terminal.v1"
SELF_HOST_CLI_TERMINAL_ARTIFACT = "skillguard_self_host_cli_terminal"
_SAFE_ERROR_CODE = re.compile(r"^[a-z][a-z0-9_.:-]*$")


def _exception_terminal(exc: Exception) -> Mapping[str, Any]:
    if isinstance(exc, SelfHostError):
        candidate_code = str(exc.code)
        error_code = (
            candidate_code
            if _SAFE_ERROR_CODE.fullmatch(candidate_code)
            else "self_host_declared_error"
        )
        status = "failed"
        reason = "Self-host bootstrap stopped at a declared self-host gate."
    elif isinstance(exc, OSError):
        error_code = "self_host_os_error"
        status = "blocked"
        reason = "Self-host bootstrap could not access a required local resource."
    else:
        error_code = "self_host_unexpected_exception"
        status = "failed"
        reason = "Self-host bootstrap failed unexpectedly."
    return {
        "schema_version": SELF_HOST_CLI_TERMINAL_SCHEMA,
        "artifact_type": SELF_HOST_CLI_TERMINAL_ARTIFACT,
        "status": status,
        "error_code": error_code,
        "reason": reason,
        "claim_boundary": (
            "This path-safe terminal reports only that the bootstrap did not return a "
            "normal self-host result. It does not prove self-host closure, installation, "
            "release readiness, or publication."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="skillguard_self_host.py")
    parser.add_argument("--repository-root", default=".")
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument(
        "--claim-only",
        action="store_true",
        help=(
            "Create the current self-host run identity for TestMesh planning "
            "without executing validation owners."
        ),
    )
    operation.add_argument(
        "--finalize",
        action="store_true",
        help=(
            "Consume one frozen TestMesh plan and one aggregation to publish "
            "the current self-host terminal without claim, compile, or owner execution."
        ),
    )
    parser.add_argument("--run-root")
    parser.add_argument("--frozen-plan")
    parser.add_argument("--aggregation-ref")
    parser.add_argument("--owner-evidence-root")
    parser.add_argument("--skill-root")
    parser.add_argument("--target-root")
    parser.add_argument("--canonical-skillguard-root")
    parser.add_argument("--global-prompt-codex-home")
    parser.add_argument("--global-prompt-skill-root", action="append", default=[])
    parser.add_argument("--profile", action="append", default=[])
    parser.add_argument("--output", help="Write the complete machine report to this repository-relative file.")
    parser.add_argument(
        "--full-output",
        action="store_true",
        help="Require --output for the complete machine report; stdout remains a bounded summary.",
    )
    args = parser.parse_args(argv)
    if args.full_output and not args.output:
        parser.error("--full-output requires --output PATH")
    repository_root = Path(args.repository_root).resolve()
    if args.claim_only:
        if any(
            value
            for value in (
                args.run_root,
                args.frozen_plan,
                args.aggregation_ref,
                args.owner_evidence_root,
            )
        ):
            parser.error("claim-only does not accept frozen-finalization inputs")
    if args.finalize and not all(
        (args.run_root, args.frozen_plan, args.aggregation_ref, args.owner_evidence_root)
    ):
        parser.error(
            "--finalize requires --run-root, --frozen-plan, --aggregation-ref, "
            "and --owner-evidence-root"
        )
    if args.claim_only:
        try:
            result = claim_current_self_host_run(Path(args.repository_root))
        except Exception as exc:
            result = _exception_terminal(exc)
        emit_json(
            result,
            output=args.output,
            full_output=args.full_output,
            root=repository_root,
        )
        return 0 if result.get("status") == "passed" else 1
    if not args.finalize:
        parser.error(
            "choose --claim-only or --finalize; owner execution belongs only "
            "to the frozen TestMesh owner-execution stage"
        )
    try:
        frozen_plan_path = Path(args.frozen_plan).resolve()
        aggregation_ref_path = Path(args.aggregation_ref).resolve()
        frozen_plan = json.loads(frozen_plan_path.read_text(encoding="utf-8"))
        aggregation_ref_payload = json.loads(
            aggregation_ref_path.read_text(encoding="utf-8")
        )
        if isinstance(aggregation_ref_payload.get("aggregation_ref"), Mapping):
            aggregation_ref = aggregation_ref_payload["aggregation_ref"]
        else:
            aggregation_ref = aggregation_ref_payload
        if not isinstance(frozen_plan, Mapping) or not isinstance(aggregation_ref, Mapping):
            raise SelfHostError(
                "self_host_finalize_input_invalid",
                "frozen plan and aggregation reference must be JSON objects",
            )
        result = dict(
            finalize_current_self_host_from_frozen_mesh(
                repository_root,
                run_root=Path(args.run_root),
                frozen_plan=frozen_plan,
                aggregation_ref=aggregation_ref,
                owner_evidence_root=Path(args.owner_evidence_root),
                profiles=tuple(args.profile) or ("enforced",),
                skill_root=Path(args.skill_root) if args.skill_root else None,
                target_root=Path(args.target_root) if args.target_root else None,
                canonical_skillguard_root=(
                    Path(args.canonical_skillguard_root)
                    if args.canonical_skillguard_root
                    else None
                ),
                global_prompt_codex_home=(
                    Path(args.global_prompt_codex_home)
                    if args.global_prompt_codex_home
                    else None
                ),
                global_prompt_skill_roots=tuple(
                    Path(value) for value in args.global_prompt_skill_root
                ),
            )
        )
        result.update(
            {
                "frozen_plan_path": str(frozen_plan_path),
                "aggregation_ref_path": str(aggregation_ref_path),
                "canonical_terminal_path": str(
                    (
                        Path(args.skill_root).resolve()
                        if args.skill_root
                        else repository_root
                        / ".agents"
                        / "skills"
                        / "skillguard"
                    )
                    / SELF_HOST_CURRENT_RECEIPT_RELATIVE_PATH
                ),
                "executed_count": int(result.get("execution_count", 0) or 0),
                "reused_count": sum(
                    len(
                        [
                            item
                            for item in row.get("check_execution_dispositions", [])
                            if item == "reused_terminal_success"
                        ]
                    )
                    for row in result.get("executed_steps", [])
                    if isinstance(row, Mapping)
                ),
                "not_run": [],
            }
        )
    except Exception as exc:
        result = _exception_terminal(exc)
    emit_json(
        result,
        output=args.output,
        full_output=args.full_output,
        root=repository_root,
    )
    return 0 if result.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
