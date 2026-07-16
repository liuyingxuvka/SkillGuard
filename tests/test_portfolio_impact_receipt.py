from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from _skillguard_v2_runtime_fixture import SCRIPT_ROOT  # noqa: F401
from skillguard_v2.contract_compiler import canonical_hash
from skillguard_v2.portfolio import (
    REUSE_REQUEST_SCHEMA,
    _clear_member_revalidation_state,
    apply_guard_change,
    atomic_write_json,
    issue_reuse_ticket,
    portfolio_registry_hash,
    validate_registry,
)
from skillguard_v2.portfolio_impact_receipt import (
    build_portfolio_impact_receipt,
    verify_portfolio_impact_receipt,
    write_portfolio_impact_receipt,
)
from skillguard_v2.wire_identity import wire_hash


class PortfolioImpactReceiptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        self.guard_targets = [
            "logicguard-suite",
            "sourceguard",
            "traceguard-suite",
            "worldguard",
            "physicsguard-suite",
        ]
        self.chaos_suite_id = "khaos-brain-suite"
        self.chaos_members = [
            "kb-sleep-maintenance",
            "kb-dream-pass",
            "kb-organization-contribute",
            "kb-organization-maintenance",
            "khaos-brain-update",
        ]
        self.unrelated_active_target = "unrelated-active-suite"
        self.invalidated_top_level_ids = [*self.guard_targets, self.chaos_suite_id]
        self.required_impact_ids = sorted(
            set(self.invalidated_top_level_ids) | set(self.chaos_members)
        )
        self.guard_before = {
            "runtime_id": "skillguard-v2",
            "file_count": 10,
            "source_hash": "A" * 64,
            "portfolio_projection_hash": "sha256:" + "a" * 64,
        }
        self.guard_after = {
            "runtime_id": "skillguard-v2",
            "file_count": 11,
            "source_hash": "B" * 64,
            "portfolio_projection_hash": "sha256:" + "b" * 64,
        }
        components = []
        edges = []
        changed_component_ids = []
        for target_id in self.invalidated_top_level_ids:
            component_id = f"component:{target_id}"
            changed_component_ids.append(component_id)
            components.append(
                {
                    "component_id": component_id,
                    "role": "runtime_source",
                    "install_disposition": "source_only",
                    "member_paths": [f"runtime/{target_id}.py"],
                    "component_hash": wire_hash({"target_id": target_id}),
                    "consumer_ids": [f"portfolio-target:{target_id}"],
                    "classification_rule_ids": ["fixture:runtime"],
                }
            )
            edges.append(
                {
                    "target_id": target_id,
                    "input_component_ids": [component_id],
                    "member_ids": (
                        sorted(self.chaos_members)
                        if target_id == self.chaos_suite_id
                        else []
                    ),
                }
            )
        health = {
            "unmapped_paths": [],
            "ambiguous_role_paths": [],
            "duplicate_owner_ids": [],
            "owner_cycles": [],
            "invalid_dependency_edges": [],
            "dependency_parse_errors": [],
        }
        self.content_impact_plan = {
            "schema_version": "skillguard.content_impact_plan.current",
            "member_root_path": ".agents/skills/skillguard",
            "policy_id": "skillguard.content_impact_policy.current",
            "inventory_hash": wire_hash([]),
            "components": components,
            "owners": [],
            "check_projections": [],
            "projection_consumers": [],
            "portfolio_target_edges": edges,
            "health": health,
        }
        self.content_impact_plan["impact_graph_hash"] = wire_hash(
            {
                "member_root_path": self.content_impact_plan["member_root_path"],
                "policy_id": self.content_impact_plan["policy_id"],
                "inventory_hash": self.content_impact_plan["inventory_hash"],
                "components": components,
                "owners": [],
                "check_projections": [],
                "projection_consumers": [],
                "portfolio_target_edges": edges,
                "health": health,
            }
        )
        self.change = {
            "schema_version": "skillguard.guard_change.v2",
            "change_id": "harden-native-depth-evidence-identity",
            "guard_before": self.guard_before,
            "guard_after": self.guard_after,
            "affected_feature_tags": ["target-native-depth-identity"],
            "impact_graph_hash": self.content_impact_plan["impact_graph_hash"],
            "changed_component_ids": sorted(changed_component_ids),
            "reason": "A SkillGuard model miss invalidated target-native depth evidence.",
            "transaction_id": "tx:harden-native-depth-evidence-identity",
            "expected_registry_revision": 1,
            "base_registry_hash": "C" * 64,
        }
        member_statuses = {
            member_id: {
                "graduation_status": "revalidation_required",
                "pending_guard_change_id": self.change["change_id"],
                "reuse_ticket_absent": True,
            }
            for member_id in self.chaos_members
        }
        self.registry = {
            "schema_version": "skillguard.portfolio_registry.v2",
            "active_guard": self.guard_after,
            "entries": [
                {
                    "skill_id": target_id,
                    "lifecycle": "active_owned",
                    "graduation_status": (
                        "revalidation_required"
                        if target_id in self.invalidated_top_level_ids
                        else "current"
                    ),
                    **(
                        {
                            "pending_guard_change_id": self.change["change_id"]
                        }
                        if target_id in self.invalidated_top_level_ids
                        else {}
                    ),
                    "reuse_ticket": None,
                    **(
                        {"member_revalidation_statuses": member_statuses}
                        if target_id == self.chaos_suite_id
                        else {}
                    ),
                }
                for target_id in [
                    *self.invalidated_top_level_ids,
                    self.unrelated_active_target,
                ]
            ],
            "transaction_history": [
                {
                    "transaction_id": self.change["transaction_id"],
                    "mutation_kind": "guard_change",
                }
            ],
        }
        self.registry_path = self.workspace / "portfolio" / "registry.json"
        atomic_write_json(self.registry_path, self.registry)
        status_transitions = [
            {
                "scope_kind": "portfolio_target",
                "target_id": target_id,
                "member_id": "",
                "before_status": "current",
                "after_status": "revalidation_required",
            }
            for target_id in self.invalidated_top_level_ids
        ] + [
            {
                "scope_kind": "suite_member",
                "target_id": self.chaos_suite_id,
                "member_id": member_id,
                "before_status": "untracked",
                "after_status": "revalidation_required",
            }
            for member_id in self.chaos_members
        ]
        result = {
            "status": "updated",
            "invalidated_entries": [
                {"skill_id": target_id, "affected": True}
                for target_id in self.invalidated_top_level_ids
            ],
            "required_target_ids": list(self.invalidated_top_level_ids),
            "required_member_ids_by_suite": {
                self.chaos_suite_id: list(self.chaos_members)
            },
            "required_impact_ids": list(self.required_impact_ids),
            "invalidated_member_ids": list(self.chaos_members),
            "member_revalidation_statuses": {
                self.chaos_suite_id: member_statuses
            },
            "status_transitions": status_transitions,
        }
        self.receipt = build_portfolio_impact_receipt(
            change=self.change,
            registry=self.registry,
            registry_path=self.registry_path,
            workspace_root=self.workspace,
            impact_result=result,
        )
        self.receipt_root = self.workspace / "receipts"
        write_portfolio_impact_receipt(self.receipt_root, self.receipt)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _verify(self, targets=None, *, exact: bool = True):
        return verify_portfolio_impact_receipt(
            self.receipt_root,
            workspace_root=self.workspace,
            require_change_id=self.change["change_id"],
            require_status="revalidation_required",
            require_target_ids=(targets if targets is not None else self.required_impact_ids),
            require_exact_target_set=exact,
        )

    def test_exact_guard_targets_and_five_chaos_members_pass(self) -> None:
        report = self._verify()
        self.assertEqual("passed", report["status"], report)
        self.assertEqual(
            sorted(self.invalidated_top_level_ids),
            self.receipt["required_target_ids"],
        )
        self.assertEqual(
            {self.chaos_suite_id: sorted(self.chaos_members)},
            self.receipt["required_member_ids_by_suite"],
        )
        self.assertEqual(
            self.required_impact_ids, self.receipt["required_impact_ids"]
        )
        self.assertEqual(
            set(self.invalidated_top_level_ids),
            set(self.receipt["invalidated_target_ids"]),
        )
        self.assertNotIn(
            self.unrelated_active_target, self.receipt["required_impact_ids"]
        )
        persisted = self.receipt["member_revalidation_statuses"][
            self.chaos_suite_id
        ]
        self.assertEqual(set(self.chaos_members), set(persisted))
        for member_id in self.chaos_members:
            self.assertEqual(
                "revalidation_required",
                persisted[member_id]["graduation_status"],
            )

    def test_exact_required_set_rejects_missing_member_expectation(self) -> None:
        report = self._verify(self.required_impact_ids[:-1])
        self.assertIn(
            "portfolio_impact_target_set_mismatch",
            "|".join(report["blockers"]),
        )

    def test_suite_hiding_one_chaos_member_blocks(self) -> None:
        changed = copy.deepcopy(self.registry)
        suite = next(
            row
            for row in changed["entries"]
            if row["skill_id"] == self.chaos_suite_id
        )
        hidden_member = self.chaos_members[-1]
        suite["member_revalidation_statuses"].pop(hidden_member)
        atomic_write_json(self.registry_path, changed)
        report = self._verify()
        self.assertEqual("blocked", report["status"])
        self.assertIn("portfolio_impact_registry_hash_mismatch", report["blockers"])
        self.assertIn(
            f"portfolio_impact_registry_member_status_mismatch:{self.chaos_suite_id}:{hidden_member}",
            report["blockers"],
        )

    def test_registry_reuse_or_tamper_blocks(self) -> None:
        changed = copy.deepcopy(self.registry)
        changed["entries"][0]["reuse_ticket"] = {"ticket_id": "forbidden"}
        atomic_write_json(self.registry_path, changed)
        report = self._verify()
        self.assertEqual("blocked", report["status"])
        self.assertIn("portfolio_impact_registry_hash_mismatch", report["blockers"])
        self.assertIn(
            "portfolio_impact_reuse_not_cleared:logicguard-suite",
            report["blockers"],
        )

    def test_receipt_bytes_tamper_blocks(self) -> None:
        head = json.loads((self.receipt_root / "HEAD.json").read_text(encoding="utf-8"))
        receipt_path = self.receipt_root / head["receipt_ref"]["relative_path"]
        tampered = json.loads(receipt_path.read_text(encoding="utf-8"))
        tampered["registry_hash"] = canonical_hash({"tampered": True})
        receipt_path.write_text(json.dumps(tampered), encoding="utf-8")
        self.assertEqual("blocked", self._verify()["status"])

    def test_legacy_receipt_without_precise_fields_is_rejected(self) -> None:
        legacy = copy.deepcopy(self.receipt)
        for field in (
            "impact_graph_hash",
            "changed_component_ids",
            "affected_target_ids",
            "required_target_ids",
            "required_member_ids_by_suite",
            "required_impact_ids",
            "invalidated_member_ids",
            "member_revalidation_statuses",
            "status_transitions",
            "registry_transaction_id",
        ):
            legacy.pop(field, None)
        legacy.pop("receipt_id", None)
        legacy.pop("receipt_hash", None)
        legacy["receipt_id"] = (
            f"portfolio-impact-{canonical_hash(legacy)[:24].lower()}"
        )
        legacy["receipt_hash"] = canonical_hash(legacy)
        legacy_root = self.workspace / "legacy-receipt"
        write_portfolio_impact_receipt(legacy_root, legacy)
        report = verify_portfolio_impact_receipt(
            legacy_root,
            workspace_root=self.workspace,
            require_change_id=self.change["change_id"],
            require_status="revalidation_required",
            require_target_ids=self.invalidated_top_level_ids,
            require_exact_target_set=True,
        )
        self.assertEqual("blocked", report["status"], report)
        self.assertTrue(
            any(
                blocker.startswith(
                    "portfolio_impact_current_scope_fields_missing:"
                )
                for blocker in report["blockers"]
            ),
            report,
        )

    def _minimal_apply_registry(self) -> dict[str, object]:
        entries = []
        for index, target_id in enumerate(
            [*self.invalidated_top_level_ids, self.unrelated_active_target]
        ):
            if target_id == self.chaos_suite_id:
                members = list(self.chaos_members)
            elif target_id.endswith("-suite"):
                members = [f"{target_id}:member-a", f"{target_id}:member-b"]
            else:
                members = [target_id]
            entries.append(
                {
                    "skill_id": target_id,
                    "target_kind": (
                        "skill_suite" if len(members) > 1 else "single_skill"
                    ),
                    "lifecycle": "active_owned",
                    "graduation_status": "baseline",
                    "consumed_guard_feature_tags": [],
                    "member_capability_inventory": [
                        {
                            "member_skill_id": member_id,
                            "skill_path": f"skills/{index}-{member_index}",
                            "required_capability_ids": [
                                f"capability:{index}:{member_index}"
                            ],
                        }
                        for member_index, member_id in enumerate(members)
                    ],
                    "reuse_ticket": None,
                }
            )
        registry: dict[str, object] = {
            "revision": 1,
            "previous_registry_hash": "",
            "scope_manifest_hash": "D" * 64,
            "active_guard": self.guard_before,
            "entries": entries,
            "transaction_history": [],
            "guard_change_history": [],
            "updated_at": "2026-07-13T00:00:00Z",
        }
        registry["registry_hash"] = portfolio_registry_hash(registry)
        return registry

    def test_apply_persists_members_and_reuse_cannot_bypass(self) -> None:
        registry = self._minimal_apply_registry()
        prior_statuses = {
            entry["skill_id"]: entry["graduation_status"]
            for entry in registry["entries"]
        }
        change = {
            **self.change,
            "expected_registry_revision": registry["revision"],
            "base_registry_hash": registry["registry_hash"],
        }
        with patch(
            "skillguard_v2.portfolio.validate_registry", return_value=[]
        ):
            result, updated = apply_guard_change(
                registry,
                change,
                content_impact_plan=self.content_impact_plan,
            )
        self.assertEqual("updated", result["status"], result)
        self.assertIsNotNone(updated)
        assert updated is not None
        affected_top_level = set(self.guard_targets) | {self.chaos_suite_id}
        for entry in updated["entries"]:
            expected = (
                "revalidation_required"
                if entry["skill_id"] in affected_top_level
                else prior_statuses[entry["skill_id"]]
            )
            self.assertEqual(expected, entry["graduation_status"])
        unrelated = next(
            row
            for row in updated["entries"]
            if row["skill_id"] == self.unrelated_active_target
        )
        self.assertIsNone(unrelated["reuse_ticket"])
        self.assertNotIn("pending_guard_change_id", unrelated)
        suite = next(
            row
            for row in updated["entries"]
            if row["skill_id"] == self.chaos_suite_id
        )
        self.assertEqual(
            set(self.chaos_members),
            set(suite["member_revalidation_statuses"]),
        )
        self.assertEqual(
            sorted(self.chaos_members), result["invalidated_member_ids"]
        )

        identity = {
            "source_fingerprint": "1" * 64,
            "contract_hash": "2" * 64,
            "command_fingerprint": "3" * 64,
            "environment_fingerprint": "4" * 64,
            "coverage_fingerprint": "5" * 64,
        }
        reuse_request = {
            "schema_version": REUSE_REQUEST_SCHEMA,
            "transaction_id": "tx:member-reuse-forbidden",
            "expected_registry_revision": updated["revision"],
            "base_registry_hash": updated["registry_hash"],
            "skill_id": self.chaos_suite_id,
            "guard_change": change,
            "previous_result": identity,
            "current_identity": identity,
        }
        with patch(
            "skillguard_v2.portfolio.validate_registry", return_value=[]
        ):
            reuse, _updated, _ticket = issue_reuse_ticket(
                updated,
                reuse_request,
                content_impact_plan=self.content_impact_plan,
            )
        blocker_codes = {
            row["code"] for row in reuse.get("blockers", [])
        }
        self.assertIn(
            "reuse_forbidden_with_member_revalidation", blocker_codes
        )

    def test_registry_validator_rejects_current_suite_hiding_member_state(self) -> None:
        registry = self._minimal_apply_registry()
        suite = next(
            row
            for row in registry["entries"]
            if row["skill_id"] == self.chaos_suite_id
        )
        suite["graduation_status"] = "current"
        suite["member_revalidation_statuses"] = {
            self.chaos_members[0]: {
                "graduation_status": "revalidation_required",
                "pending_guard_change_id": self.change["change_id"],
                "reuse_ticket_absent": True,
            }
        }
        codes = {row["code"] for row in validate_registry(registry)}
        self.assertIn("portfolio_suite_hides_affected_member", codes)

    def test_graduation_clear_removes_member_revalidation_state(self) -> None:
        entry = {
            "member_revalidation_statuses": {
                member_id: {
                    "graduation_status": "revalidation_required",
                    "pending_guard_change_id": self.change["change_id"],
                    "reuse_ticket_absent": True,
                }
                for member_id in self.chaos_members
            }
        }
        _clear_member_revalidation_state(entry)
        self.assertNotIn("member_revalidation_statuses", entry)

    def test_schemas_project_exact_impact_and_member_state_fields(self) -> None:
        schema_root = (
            Path(__file__).resolve().parents[1]
            / ".agents"
            / "skills"
            / "skillguard"
            / "assets"
            / "schemas"
        )
        guard_change = json.loads(
            (schema_root / "skillguard_guard_change_v2.schema.json").read_text(
                encoding="utf-8"
            )
        )
        registry = json.loads(
            (schema_root / "skillguard_portfolio_registry_v2.schema.json").read_text(
                encoding="utf-8"
            )
        )
        receipt = json.loads(
            (
                schema_root
                / "skillguard_portfolio_impact_receipt_v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        self.assertIn("impact_graph_hash", guard_change["properties"])
        self.assertIn("changed_component_ids", guard_change["properties"])
        self.assertNotIn("broad_semantic_change", guard_change["properties"])
        self.assertIn(
            "member_revalidation_statuses",
            registry["$defs"]["active_entry"]["properties"],
        )
        for field in (
            "invalidated_target_ids",
            "impact_graph_hash",
            "changed_component_ids",
            "required_target_ids",
            "required_member_ids_by_suite",
            "required_impact_ids",
            "invalidated_member_ids",
            "member_revalidation_statuses",
            "status_transitions",
            "registry_transaction_id",
        ):
            self.assertIn(field, receipt["properties"])


if __name__ == "__main__":
    unittest.main()
