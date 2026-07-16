"""Run the generic declared-check supervision FlowGuard model."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
from typing import Any

import flowguard

from model import (
    BLOCKS,
    CLAIM_BOUNDARY,
    GOOD_MULTI,
    GOOD_SHARED_OWNER,
    GOOD_SINGLE,
    MODEL_ID,
    SupervisionState,
    WORKFLOW,
    known_bad_family_inventory,
    model_summary,
    run_contract_review,
    run_known_bad_rejection_review,
    run_loop_reviews,
    run_refinement_review,
    run_scenario_review,
)


def _report_summary(report: Any) -> dict[str, Any]:
    return {
        "ok": bool(getattr(report, "ok", False)),
        "decision": str(getattr(report, "decision", "")),
        "confidence": str(getattr(report, "confidence", "")),
        "finding_codes": [
            str(getattr(finding, "code", ""))
            for finding in getattr(report, "findings", ())
        ],
    }


def _terminal_state(case: Any) -> Any:
    run = WORKFLOW.execute(SupervisionState(), case)
    if len(run.completed_paths) != 1 or run.dead_branches or run.exception_branches:
        raise RuntimeError(f"case did not terminate exactly once: {case.case_name}")
    return run.completed_paths[0].state


def run_all() -> tuple[bool, dict[str, Any]]:
    scenarios = run_scenario_review()
    rejections = run_known_bad_rejection_review()
    contracts = run_contract_review()
    refinement = run_refinement_review()
    loop_good, progress_good, loop_bad = run_loop_reviews()
    single = _terminal_state(GOOD_SINGLE)
    multi = _terminal_state(GOOD_MULTI)
    shared_owner = _terminal_state(GOOD_SHARED_OWNER)

    positive = {
        "real_flowguard_schema_current": str(flowguard.SCHEMA_VERSION) == "1.0",
        "scenario_review": scenarios.ok,
        "known_bad_exact_rejections": bool(rejections["ok"]),
        "function_contract_review": contracts.ok,
        "refinement_review": refinement.ok,
        "loop_stuck_review": loop_good.ok,
        "progress_review": progress_good.ok,
        "single_check_target_closes": single.closure_status == "pass",
        "multi_check_target_closes": multi.closure_status == "pass",
        "shared_owner_retains_every_semantic_check": (
            shared_owner.closure_status == "pass"
        ),
        "function_blocks_use_input_state_set_contract": all(
            " x " in (block.__doc__ or "") and "Set(" in (block.__doc__ or "")
            for block in BLOCKS
        ),
        "all_failure_families_materialized": all(
            known_bad_family_inventory().get(family)
            for family in ("inventory", "ownership", "receipt", "reconciliation")
        ),
    }
    negative = {"nonterminating_result_wait_rejected": not loop_bad.ok}
    ok = all(positive.values()) and all(negative.values())
    payload = {
        "schema_version": "skillguard.declared_check_supervision_flowguard_report.current",
        "status": "pass" if ok else "fail",
        "flowguard": {
            "schema_version": str(flowguard.SCHEMA_VERSION),
            "package_version": importlib.metadata.version("flowguard"),
        },
        "model": model_summary(),
        "positive_gate_status": positive,
        "known_bad_gate_status": negative,
        "reviews": {
            "scenarios": _report_summary(scenarios),
            "contracts": _report_summary(contracts),
            "refinement": _report_summary(refinement),
            "loop_stuck": _report_summary(loop_good),
            "progress": _report_summary(progress_good),
        },
        "known_bad_rejection_summary": rejections,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return ok, payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    ok, payload = run_all()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"{payload['status'].upper()}: {MODEL_ID}")
        print(json.dumps(payload["positive_gate_status"], indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
