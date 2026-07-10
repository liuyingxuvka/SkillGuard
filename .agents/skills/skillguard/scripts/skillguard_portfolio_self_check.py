"""Native self-checks for SkillGuard portfolio audit, impact, reuse, and graduation."""

from __future__ import annotations

import argparse
import json
from typing import Any

from skillguard_v2.portfolio import (
    GRADUATION_EVIDENCE_SCHEMA,
    GUARD_CHANGE_SCHEMA,
    PORTFOLIO_REGISTRY_SCHEMA,
    REUSE_REQUEST_SCHEMA,
    apply_guard_change,
    audit_portfolio,
    current_guard,
    graduate_portfolio_target,
    issue_reuse_ticket,
    representative_jobs_coverage_fingerprint,
)


def digest(character: str) -> str:
    return character * 64


def identity(source: str, contract: str, *, coverage: str = "E") -> dict[str, str]:
    return {
        "source_fingerprint": digest(source),
        "contract_hash": digest(contract),
        "command_fingerprint": digest("C"),
        "environment_fingerprint": digest("D"),
        "coverage_fingerprint": coverage if len(coverage) == 64 else digest(coverage),
    }


def receipt(
    skill_id: str,
    guard: dict[str, Any],
    source: str,
    contract: str,
    *,
    coverage: str = "E",
) -> dict[str, Any]:
    return {
        "receipt_id": f"receipt:{skill_id}",
        "status": "current",
        "guard_runtime": guard,
        **identity(source, contract, coverage=coverage),
        "result_hash": digest("F"),
        "completed_at": "2026-07-10T00:00:00Z",
    }


def entry(skill_id: str, order: int, guard: dict[str, Any], source: str, contract: str, *, current: bool) -> dict[str, Any]:
    jobs = (
        [
            {
                "job_id": f"job:{skill_id}",
                "covered_capability_ids": ["capability:primary"],
                "evidence_refs": [f"receipt:{skill_id}"],
            }
        ]
        if current
        else []
    )
    return {
        "skill_id": skill_id,
        "order": order,
        "lifecycle": "active_owned",
        "graduation_status": "current" if current else "pending",
        "canonical_source": {
            "path_token": f"fixture/{skill_id}",
            "version": "self-check",
            "source_fingerprint": digest(source),
        },
        "repository": {"origin": "fixture", "visibility": "local_only"},
        "consumed_guard_feature_tags": ["compiler"],
        "capability_inventory_status": "current",
        "required_capability_ids": ["capability:primary"],
        "contract_hash": digest(contract) if current else "",
        "representative_jobs": jobs,
        "representative_job_ids": [f"job:{skill_id}"] if current else [],
        "full_run_receipt": (
            receipt(
                skill_id,
                guard,
                source,
                contract,
                coverage=representative_jobs_coverage_fingerprint(jobs),
            )
            if current
            else None
        ),
        "reuse_ticket": None,
        "last_revalidation": "2026-07-10T00:00:00Z" if current else "",
        "failure_classification": None,
    }


def registry(guard: dict[str, Any], entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": PORTFOLIO_REGISTRY_SCHEMA,
        "registry_id": "portfolio:self-check",
        "active_guard": guard,
        "entries": entries,
    }


def run(mode: str) -> dict[str, Any]:
    active = current_guard()
    if mode == "audit":
        report = audit_portfolio(
            registry(active, [entry("skillguard", 0, active, "1", "2", current=True)]),
            actual_guard=active,
        )
        ok = report["status"] == "current"
    elif mode == "impact":
        before = {"runtime_id": "skillguard-v2", "file_count": active["file_count"], "source_hash": digest("A")}
        original = registry(before, [entry("sourceguard", 0, before, "1", "2", current=True)])
        change = {
            "schema_version": GUARD_CHANGE_SCHEMA,
            "change_id": "change:self-check",
            "guard_before": before,
            "guard_after": active,
            "affected_feature_tags": ["readme"],
            "broad_semantic_change": False,
            "reason": "Exercise proof-bound non-intersecting reuse.",
        }
        impact, changed = apply_guard_change(original, change)
        assert changed is not None
        request = {
            "schema_version": REUSE_REQUEST_SCHEMA,
            "skill_id": "sourceguard",
            "guard_change": change,
            "previous_result": identity(
                "1",
                "2",
                coverage=str(original["entries"][0]["full_run_receipt"]["coverage_fingerprint"]),
            ),
            "current_identity": identity(
                "1",
                "2",
                coverage=str(original["entries"][0]["full_run_receipt"]["coverage_fingerprint"]),
            ),
        }
        reuse, updated, ticket = issue_reuse_ticket(changed, request)
        assert updated is not None
        audit = audit_portfolio(updated, actual_guard=active)
        report = {"impact": impact, "reuse": reuse, "audit": audit}
        ok = ticket is not None and audit["status"] == "current"
    elif mode == "graduation":
        original = registry(
            active,
            [
                entry("skillguard", 0, active, "1", "2", current=True),
                entry("sourceguard", 1, active, "3", "4", current=False),
            ],
        )
        jobs = [
            {
                "job_id": "job:sourceguard:positive",
                "covered_capability_ids": ["capability:primary"],
                "evidence_refs": ["receipt:sourceguard:positive"],
            },
            {
                "job_id": "job:sourceguard:recovery",
                "covered_capability_ids": ["capability:recovery"],
                "evidence_refs": ["receipt:sourceguard:recovery"],
            },
        ]
        evidence = {
            "schema_version": GRADUATION_EVIDENCE_SCHEMA,
            "skill_id": "sourceguard",
            "version": "self-check",
            "source_fingerprint": digest("3"),
            "contract_hash": digest("4"),
            "guard_runtime": active,
            "representative_jobs": jobs,
            "full_run_receipt": receipt(
                "sourceguard",
                active,
                "3",
                "4",
                coverage=representative_jobs_coverage_fingerprint(jobs),
            ),
            "failure_classification": None,
        }
        graduation, updated, parent_receipt = graduate_portfolio_target(
            original, evidence, actual_guard=active
        )
        assert updated is not None
        audit = audit_portfolio(updated, actual_guard=active)
        report = {"graduation": graduation, "audit": audit}
        ok = parent_receipt is not None and audit["status"] == "current"
    else:
        raise ValueError(f"unknown mode: {mode}")
    return {
        "artifact_type": "skillguard_portfolio_self_check",
        "mode": mode,
        "status": "passed" if ok else "failed",
        "report": report,
        "claim_boundary": "This deterministic self-check exercises synthetic portfolio records; real targets still require their own current evidence.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("audit", "impact", "graduation"), required=True)
    args = parser.parse_args()
    result = run(args.mode)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
