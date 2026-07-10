from __future__ import annotations

import copy
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / ".agents" / "skills" / "skillguard" / "scripts"
import sys

if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from checker_engine import COMMANDS, fixture_test  # noqa: E402
from skillguard_v2.portfolio import (  # noqa: E402
    GRADUATION_EVIDENCE_SCHEMA,
    GUARD_CHANGE_SCHEMA,
    PORTFOLIO_REGISTRY_SCHEMA,
    REUSE_REQUEST_SCHEMA,
    apply_guard_change,
    audit_portfolio,
    graduate_portfolio_target,
    issue_reuse_ticket,
    portfolio_registry_lock,
    representative_jobs_coverage_fingerprint,
    validate_registry,
)
from skillguard_v2.runtime_fingerprint import (  # noqa: E402
    guard_runtime_fingerprint,
    resolve_guard_runtime_root,
)


def digest(character: str) -> str:
    return character * 64


def guard(character: str) -> dict[str, object]:
    return {"runtime_id": "skillguard-v2", "file_count": 2, "source_hash": digest(character)}


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
    active_guard: dict[str, object],
    source: str,
    contract: str,
    *,
    coverage: str = "E",
) -> dict[str, object]:
    return {
        "receipt_id": f"receipt:{skill_id}",
        "status": "current",
        "guard_runtime": active_guard,
        **identity(source, contract, coverage=coverage),
        "result_hash": digest("F"),
        "completed_at": "2026-07-10T00:00:00Z",
    }


def active_entry(
    skill_id: str,
    order: int,
    active_guard: dict[str, object],
    *,
    current: bool,
    source: str,
    contract: str,
    consumed: list[str] | None = None,
) -> dict[str, object]:
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
            "path_token": f"local/{skill_id}",
            "version": "1.0.0",
            "source_fingerprint": digest(source),
        },
        "repository": {"origin": f"https://example.invalid/{skill_id}", "visibility": "public"},
        "consumed_guard_feature_tags": consumed or ["compiler", "closure"],
        "capability_inventory_status": "current",
        "required_capability_ids": ["capability:primary"],
        "contract_hash": digest(contract) if current else "",
        "representative_jobs": jobs,
        "representative_job_ids": [f"job:{skill_id}"] if current else [],
        "full_run_receipt": (
            receipt(
                skill_id,
                active_guard,
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


def registry(entries: list[dict[str, object]], active_guard: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": PORTFOLIO_REGISTRY_SCHEMA,
        "registry_id": "portfolio:test",
        "active_guard": active_guard,
        "entries": entries,
    }


class PortfolioRuntimeV2Tests(unittest.TestCase):
    def test_command_surface_exposes_portfolio_runtime(self) -> None:
        self.assertTrue(
            {
                "audit-portfolio",
                "mark-portfolio-impact",
                "issue-portfolio-reuse-ticket",
                "graduate-portfolio",
            }.issubset(COMMANDS)
        )

    def test_portfolio_fixture_manifest_executes_all_public_commands(self) -> None:
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            exit_code = fixture_test(
                [
                    "--manifest",
                    ".agents/skills/skillguard/fixtures/portfolio_runtime/fixture-manifest.json",
                    "--output",
                    "-",
                ]
            )
        report = json.loads(stream.getvalue())
        self.assertEqual(0, exit_code)
        self.assertEqual("pass", report["decision"])
        self.assertEqual(4, len(report["fixture_results"]))
        self.assertEqual(
            {
                "audit-portfolio",
                "mark-portfolio-impact",
                "issue-portfolio-reuse-ticket",
                "graduate-portfolio",
            },
            {row["target_command"] for row in report["fixture_results"]},
        )

    def test_registry_requires_unique_active_order_and_explicit_exclusion_reason(self) -> None:
        current_guard = guard("A")
        payload = registry(
            [
                active_entry("one", 0, current_guard, current=False, source="1", contract="2"),
                active_entry("two", 0, current_guard, current=False, source="3", contract="4"),
                {
                    "skill_id": "databank-workflow",
                    "order": None,
                    "lifecycle": "excluded_private",
                    "graduation_status": "excluded",
                    "exclusion_reason": "",
                },
            ],
            current_guard,
        )
        codes = {finding["code"] for finding in validate_registry(payload)}
        self.assertIn("active_order_duplicate", codes)
        self.assertIn("exclusion_reason_missing", codes)

    def test_excluded_and_supporting_repositories_do_not_block_active_queue(self) -> None:
        current_guard = guard("A")
        first = active_entry("skillguard", 0, current_guard, current=True, source="1", contract="2")
        payload = registry(
            [
                first,
                {
                    "skill_id": "databank-workflow",
                    "order": None,
                    "lifecycle": "excluded_private",
                    "graduation_status": "excluded",
                    "exclusion_reason": "User explicitly excluded the private database skill.",
                },
                {
                    "skill_id": "khaos-org-kb-sandbox",
                    "order": None,
                    "lifecycle": "supporting_repository",
                    "graduation_status": "supporting",
                    "parent_skill_id": "skillguard",
                },
            ],
            current_guard,
        )
        report = audit_portfolio(payload, actual_guard=current_guard)
        self.assertEqual("current", report["status"])
        self.assertEqual(["databank-workflow"], report["excluded_skill_ids"])

    def test_guard_change_invalidates_old_green_and_preserves_exclusion(self) -> None:
        old_guard = guard("A")
        new_guard = guard("B")
        payload = registry(
            [
                active_entry("skillguard", 0, old_guard, current=True, source="1", contract="2"),
                {
                    "skill_id": "databank-workflow",
                    "order": None,
                    "lifecycle": "excluded_private",
                    "graduation_status": "excluded",
                    "exclusion_reason": "Explicitly excluded.",
                },
            ],
            old_guard,
        )
        change = {
            "schema_version": GUARD_CHANGE_SCHEMA,
            "change_id": "change:portfolio-runtime",
            "guard_before": old_guard,
            "guard_after": new_guard,
            "affected_feature_tags": ["portfolio", "closure"],
            "broad_semantic_change": True,
            "reason": "Portfolio closure semantics changed.",
        }
        report, updated = apply_guard_change(payload, change)
        self.assertEqual("updated", report["status"])
        assert updated is not None
        self.assertEqual("revalidation_required", updated["entries"][0]["graduation_status"])
        self.assertEqual("excluded", updated["entries"][1]["graduation_status"])

    def test_reuse_ticket_requires_non_broad_non_intersecting_unchanged_identity(self) -> None:
        old_guard = guard("A")
        new_guard = guard("B")
        entry = active_entry(
            "sourceguard", 0, old_guard, current=True, source="1", contract="2", consumed=["compiler"]
        )
        payload = registry([entry], old_guard)
        change = {
            "schema_version": GUARD_CHANGE_SCHEMA,
            "change_id": "change:docs-only",
            "guard_before": old_guard,
            "guard_after": new_guard,
            "affected_feature_tags": ["readme"],
            "broad_semantic_change": False,
            "reason": "Public documentation only.",
        }
        _, changed = apply_guard_change(payload, change)
        assert changed is not None
        old_receipt = entry["full_run_receipt"]
        assert isinstance(old_receipt, dict)
        request = {
            "schema_version": REUSE_REQUEST_SCHEMA,
            "skill_id": "sourceguard",
            "guard_change": change,
            "previous_result": identity(
                "1", "2", coverage=str(old_receipt["coverage_fingerprint"])
            ),
            "current_identity": identity(
                "1", "2", coverage=str(old_receipt["coverage_fingerprint"])
            ),
        }
        report, updated, ticket = issue_reuse_ticket(changed, request)
        self.assertEqual("issued", report["status"])
        self.assertIsNotNone(ticket)
        assert updated is not None
        self.assertEqual("current", updated["entries"][0]["graduation_status"])
        without_history = copy.deepcopy(updated)
        without_history["guard_change_history"] = []
        self.assertEqual("incomplete", audit_portfolio(without_history, actual_guard=new_guard)["status"])

        repeated, _, repeated_ticket = issue_reuse_ticket(changed, request)
        self.assertEqual(report["ticket_hash"], repeated["ticket_hash"])
        self.assertEqual(ticket, repeated_ticket)

        broad_request = copy.deepcopy(request)
        broad_request["guard_change"]["broad_semantic_change"] = True
        blocked, _, _ = issue_reuse_ticket(changed, broad_request)
        self.assertEqual("blocked", blocked["status"])

    def test_graduation_blocks_when_prior_skill_is_not_current(self) -> None:
        current_guard = guard("A")
        first = active_entry("skillguard", 0, current_guard, current=False, source="1", contract="2")
        second = active_entry("sourceguard", 1, current_guard, current=False, source="3", contract="4")
        payload = registry([first, second], current_guard)
        second_receipt = receipt("sourceguard", current_guard, "3", "4")
        jobs = [
            {
                "job_id": "job:sourceguard:positive",
                "covered_capability_ids": ["capability:primary"],
                "evidence_refs": ["receipt:sourceguard"],
            }
        ]
        second_receipt["coverage_fingerprint"] = representative_jobs_coverage_fingerprint(jobs)
        evidence = {
            "schema_version": GRADUATION_EVIDENCE_SCHEMA,
            "skill_id": "sourceguard",
            "version": "1.0.0",
            "source_fingerprint": digest("3"),
            "contract_hash": digest("4"),
            "guard_runtime": current_guard,
            "representative_jobs": jobs,
            "full_run_receipt": second_receipt,
            "failure_classification": None,
        }
        report, _, _ = graduate_portfolio_target(payload, evidence, actual_guard=current_guard)
        self.assertEqual("blocked", report["status"])
        self.assertIn("prior_graduate_not_current", {row["code"] for row in report["blockers"]})

    def test_graduation_updates_target_and_emits_parent_receipt(self) -> None:
        current_guard = guard("A")
        first = active_entry("skillguard", 0, current_guard, current=True, source="1", contract="2")
        second = active_entry("sourceguard", 1, current_guard, current=False, source="3", contract="4")
        payload = registry([first, second], current_guard)
        second_receipt = receipt("sourceguard", current_guard, "3", "4")
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
        second_receipt["coverage_fingerprint"] = representative_jobs_coverage_fingerprint(jobs)
        evidence = {
            "schema_version": GRADUATION_EVIDENCE_SCHEMA,
            "skill_id": "sourceguard",
            "version": "1.0.0",
            "source_fingerprint": digest("3"),
            "contract_hash": digest("4"),
            "guard_runtime": current_guard,
            "representative_jobs": jobs,
            "full_run_receipt": second_receipt,
            "failure_classification": None,
        }
        report, updated, parent_receipt = graduate_portfolio_target(
            payload, evidence, actual_guard=current_guard
        )
        self.assertEqual("graduated", report["status"])
        self.assertIsNotNone(parent_receipt)
        assert updated is not None
        self.assertEqual("current", updated["entries"][1]["graduation_status"])
        self.assertEqual(1, report["prior_evidence_count"])
        assert parent_receipt is not None
        self.assertEqual(digest("F"), parent_receipt["prior_evidence"][0]["proof_hash"])
        self.assertEqual(
            second_receipt["coverage_fingerprint"],
            parent_receipt["target_identity"]["coverage_fingerprint"],
        )
        repeated, _, repeated_receipt = graduate_portfolio_target(
            payload, evidence, actual_guard=current_guard
        )
        self.assertEqual(report["receipt_hash"], repeated["receipt_hash"])
        self.assertEqual(parent_receipt, repeated_receipt)

    def test_graduation_requires_declared_capability_coverage_bound_to_receipt(self) -> None:
        current_guard = guard("A")
        target = active_entry("sourceguard", 0, current_guard, current=False, source="3", contract="4")
        target["required_capability_ids"] = ["route:intake", "route:delivery"]
        payload = registry([target], current_guard)
        jobs = [
            {
                "job_id": "job:intake",
                "covered_capability_ids": ["route:intake"],
                "evidence_refs": ["receipt:intake"],
            }
        ]
        run_receipt = receipt("sourceguard", current_guard, "3", "4")
        evidence = {
            "schema_version": GRADUATION_EVIDENCE_SCHEMA,
            "skill_id": "sourceguard",
            "source_fingerprint": digest("3"),
            "contract_hash": digest("4"),
            "guard_runtime": current_guard,
            "representative_jobs": jobs,
            "full_run_receipt": run_receipt,
            "failure_classification": None,
        }
        report, _, _ = graduate_portfolio_target(payload, evidence, actual_guard=current_guard)
        codes = {row["code"] for row in report["blockers"]}
        self.assertIn("representative_jobs_not_bound_to_receipt", codes)
        run_receipt["coverage_fingerprint"] = representative_jobs_coverage_fingerprint(jobs)
        report, _, _ = graduate_portfolio_target(payload, evidence, actual_guard=current_guard)
        self.assertIn(
            "graduation_capability_coverage_incomplete",
            {row["code"] for row in report["blockers"]},
        )

    def test_registry_rejects_orphan_supporting_repository(self) -> None:
        current_guard = guard("A")
        payload = registry(
            [
                {
                    "skill_id": "orphan-support",
                    "order": None,
                    "lifecycle": "supporting_repository",
                    "graduation_status": "supporting",
                    "parent_skill_id": "missing-parent",
                }
            ],
            current_guard,
        )
        self.assertIn(
            "supporting_parent_not_active",
            {row["code"] for row in validate_registry(payload)},
        )

    def test_registry_writer_lock_recovers_abandoned_owner(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            registry_path = Path(temporary) / "portfolio.json"
            lock_path = registry_path.with_name(f".{registry_path.name}.skillguard.lock")
            lock_path.write_text(
                json.dumps({"owner_pid": 999999999, "owner_host": ""}),
                encoding="utf-8",
            )
            with portfolio_registry_lock(registry_path) as lock:
                self.assertTrue(lock["lock_recovered"])
                self.assertTrue(lock_path.is_file())
            self.assertFalse(lock_path.exists())

    def test_runtime_fingerprint_normalizes_python_line_endings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left = root / "left"
            right = root / "right"
            left.mkdir()
            right.mkdir()
            left.joinpath("runtime.py").write_bytes(b"VALUE = 1\n")
            right.joinpath("runtime.py").write_bytes(b"VALUE = 1\r\n")
            self.assertEqual(
                guard_runtime_fingerprint(left)["source_hash"],
                guard_runtime_fingerprint(right)["source_hash"],
            )

    def test_runtime_fingerprint_accepts_repository_and_skill_roots(self) -> None:
        package_root = (
            ROOT
            / ".agents"
            / "skills"
            / "skillguard"
            / "scripts"
            / "skillguard_v2"
        )
        skill_root = ROOT / ".agents" / "skills" / "skillguard"
        skill_identity = guard_runtime_fingerprint(skill_root)
        self.assertEqual(resolve_guard_runtime_root(ROOT), skill_root.resolve())
        self.assertEqual(resolve_guard_runtime_root(skill_root), skill_root.resolve())
        self.assertEqual(resolve_guard_runtime_root(package_root), skill_root.resolve())
        self.assertEqual(guard_runtime_fingerprint(ROOT), skill_identity)
        self.assertEqual(guard_runtime_fingerprint(package_root), skill_identity)
        self.assertEqual(guard_runtime_fingerprint(skill_root), skill_identity)
        self.assertGreater(skill_identity["file_count"], 50)


if __name__ == "__main__":
    unittest.main()
