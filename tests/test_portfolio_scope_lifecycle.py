from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".agents" / "skills" / "skillguard" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from skillguard_v2.portfolio import (  # noqa: E402
    PortfolioRegistryLockError,
    _supersession_lifecycle_findings,
    audit_portfolio,
    build_current_portfolio_registry,
    portfolio_registry_lock,
    portfolio_scope_hash,
    validate_registry,
    validate_scope_manifest,
)
from skillguard_v2.portfolio_records import reference_existing_file  # noqa: E402
from skillguard_v2.portfolio_cli import (  # noqa: E402
    build_current_portfolio_registry_command,
)


def _active(skill_id: str, order: int) -> dict[str, object]:
    capabilities = [f"{skill_id}-capability"]
    return {
        "skill_id": skill_id,
        "target_kind": "single_skill",
        "skill_paths": [f"skills/{skill_id}"],
        "order": order,
        "lifecycle": "active_owned",
        "canonical_source": {
            "path_token": f"local/{skill_id}",
            "skill_path": f"skills/{skill_id}",
            "version": "1.0.0",
            "source_fingerprint": "A" * 64,
            "repository_identity": {
                "host": "github.com",
                "owner": "example",
                "name": skill_id,
                "visibility": "public",
            },
        },
        "required_capability_ids": capabilities,
        "member_capability_inventory": [
            {
                "member_skill_id": skill_id,
                "skill_path": f"skills/{skill_id}",
                "required_capability_ids": capabilities,
            }
        ],
        "required_job_class_ids": [
            "positive",
            "invalid_input",
            "recovery_or_resume",
            "out_of_scope",
            "native_check",
            "artifact_check",
        ],
        "consumed_guard_feature_tags": ["portfolio"],
    }


def _superseded(skill_id: str, replacement_id: str) -> dict[str, object]:
    return {
        "skill_id": skill_id,
        "order": None,
        "lifecycle": "retired_private",
        "exclusion_approval": {
            "status": "user_confirmed",
            "decision_id": f"retire-{skill_id}",
            "reason": f"Replaced by {replacement_id}.",
        },
        "retirement_disposition": "superseded",
        "superseded_by_skill_id": replacement_id,
        "installation_disposition": "absent",
        "router_authority": "blocked",
    }


def _excluded(skill_id: str) -> dict[str, object]:
    return {
        "skill_id": skill_id,
        "order": None,
        "lifecycle": "excluded_private",
        "exclusion_approval": {
            "status": "user_confirmed",
            "decision_id": f"exclude-{skill_id}",
            "reason": "User excluded this private target from the maintained portfolio.",
        },
    }


def _scope(*targets: dict[str, object]) -> dict[str, object]:
    active_count = sum(
        target["lifecycle"] in {"active_owned", "active_adopted", "pending_adoption"}
        for target in targets
    )
    scope: dict[str, object] = {
        "schema_version": "skillguard.portfolio_scope_manifest.v1",
        "manifest_id": "scope-test",
        "revision": 1,
        "approved_at": "2026-07-15T00:00:00Z",
        "approval": {
            "status": "user_confirmed",
            "decision_id": "scope-test-decision",
        },
        "scope_policy": {"local_first": True, "active_target_count": active_count},
        "targets": list(targets),
        "claim_boundary": "Lifecycle test fixture only.",
    }
    scope["manifest_hash"] = portfolio_scope_hash(scope)
    return scope


class PortfolioScopeLifecycleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        schema_path = (
            ROOT
            / ".agents"
            / "skills"
            / "skillguard"
            / "assets"
            / "schemas"
            / "skillguard_portfolio_scope_manifest_v1.schema.json"
        )
        cls.schema = json.loads(schema_path.read_text(encoding="utf-8"))

    def test_complete_supersession_tuple_points_to_active_replacement(self) -> None:
        scope = _scope(
            _active("merged-writing", 0),
            _superseded("old-research", "merged-writing"),
            _superseded("old-academic", "merged-writing"),
        )

        self.assertEqual([], validate_scope_manifest(scope))
        excluded = self.schema["$defs"]["excluded_target"]
        self.assertEqual(
            "superseded",
            excluded["properties"]["retirement_disposition"]["const"],
        )
        self.assertEqual(
            "absent",
            excluded["properties"]["installation_disposition"]["const"],
        )
        self.assertEqual(
            "blocked",
            excluded["properties"]["router_authority"]["const"],
        )

    def test_partial_supersession_tuple_blocks(self) -> None:
        retired = _superseded("old-research", "merged-writing")
        retired.pop("router_authority")
        scope = _scope(_active("merged-writing", 0), retired)
        scope["manifest_hash"] = portfolio_scope_hash(scope)

        codes = {row["code"] for row in validate_scope_manifest(scope)}
        self.assertIn("portfolio_scope_supersession_tuple_incomplete", codes)
        self.assertIn(
            "router_authority",
            self.schema["$defs"]["excluded_target"]["dependentRequired"][
                "superseded_by_skill_id"
            ],
        )

    def test_missing_inactive_and_self_replacements_block(self) -> None:
        cases = (
            (
                [_active("current", 0), _superseded("old", "missing")],
                "portfolio_scope_superseding_target_missing",
            ),
            (
                [
                    _active("current", 0),
                    _superseded("inactive", "current"),
                    _superseded("old", "inactive"),
                ],
                "portfolio_scope_superseding_target_not_active",
            ),
            (
                [_active("current", 0), _superseded("old", "old")],
                "portfolio_scope_supersession_self_reference",
            ),
        )
        for targets, expected_code in cases:
            with self.subTest(expected_code=expected_code):
                scope = _scope(*targets)
                codes = {row["code"] for row in validate_scope_manifest(scope)}
                self.assertIn(expected_code, codes)

    def test_registry_projection_uses_the_same_target_neutral_rule(self) -> None:
        rows = {
            "current": _active("current", 0),
            "old": _superseded("old", "current"),
        }
        self.assertEqual(
            [],
            _supersession_lifecycle_findings(
                rows,
                finding_prefix="portfolio_registry",
            ),
        )

        bad_rows = copy.deepcopy(rows)
        bad_rows["old"]["installation_disposition"] = "present"
        codes = {
            row["code"]
            for row in _supersession_lifecycle_findings(
                bad_rows,
                finding_prefix="portfolio_registry",
            )
        }
        self.assertIn(
            "portfolio_registry_superseded_installation_authority_invalid",
            codes,
        )

    def test_current_registry_is_directly_built_from_scope_without_old_green_evidence(self) -> None:
        scope = _scope(
            _active("logic-writing", 0),
            _excluded("databank-workflow"),
            _superseded("academic-thesis-revision-workflow", "logic-writing"),
            _superseded("research-investigation-workflow", "logic-writing"),
        )
        guard = {
            "runtime_id": "skillguard-v2",
            "provider_id": "skillguard-local-provider",
            "runtime_contract_id": "skillguard-declared-check-supervision-current",
            "capability_ids": ["declared-check-inventory.v1"],
            "enrollment_status": "enrolled",
            "file_count": 1,
            "source_hash": "B" * 64,
            "portfolio_projection_hash": "sha256:" + "c" * 64,
        }
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            scope_path = workspace / "scope.json"
            scope_path.write_text(
                json.dumps(scope, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            registry = build_current_portfolio_registry(
                scope,
                registry_id="current-direct-replacement",
                scope_manifest_ref=reference_existing_file(scope_path, workspace),
                active_guard=guard,
                evidence_root=workspace,
                issued_at="2026-07-15T00:00:00Z",
            )

            self.assertEqual([], validate_registry(registry, evidence_root=workspace))
            self.assertEqual(1, registry["revision"])
            self.assertEqual("", registry["previous_registry_hash"])
            self.assertEqual([], registry["transaction_history"])
            self.assertEqual([], registry["guard_change_history"])
            entries = {row["skill_id"]: row for row in registry["entries"]}
            self.assertEqual(
                "revalidation_required",
                entries["logic-writing"]["graduation_status"],
            )
            self.assertNotIn("full_run_receipt", entries["logic-writing"])
            self.assertIsNone(entries["logic-writing"]["reuse_ticket"])
            self.assertEqual(
                "excluded", entries["databank-workflow"]["graduation_status"]
            )
            for retired_id in (
                "academic-thesis-revision-workflow",
                "research-investigation-workflow",
            ):
                self.assertEqual("logic-writing", entries[retired_id]["superseded_by_skill_id"])
                self.assertEqual("absent", entries[retired_id]["installation_disposition"])
                self.assertEqual("blocked", entries[retired_id]["router_authority"])

            preflight = audit_portfolio(
                registry,
                actual_guard=guard,
                candidate_skill_id="logic-writing",
                evidence_root=workspace,
                mode="candidate-preflight",
            )
            self.assertEqual("current", preflight["status"])
            self.assertEqual(["logic-writing"], preflight["non_current_skill_ids"])

    def test_current_registry_builder_rejects_non_current_scope_authority(self) -> None:
        scope = _scope(_active("logic-writing", 0))
        scope["manifest_hash"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "portfolio_current_scope_invalid"):
            build_current_portfolio_registry(
                scope,
                registry_id="current-direct-replacement",
                scope_manifest_ref="record:scope.json@" + "A" * 64,
                active_guard={
                    "runtime_id": "skillguard-v2",
                    "file_count": 1,
                    "source_hash": "B" * 64,
                    "portfolio_projection_hash": "sha256:" + "c" * 64,
                },
                evidence_root=Path("."),
                issued_at="2026-07-15T00:00:00Z",
            )

    def test_current_registry_command_does_not_accept_a_prior_registry(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            build_current_portfolio_registry_command(
                [
                    "--workspace-root",
                    ".",
                    "--scope",
                    "scope.json",
                    "--registry-id",
                    "direct-current",
                    "--registry",
                    "stale-registry.json",
                ]
            )
        self.assertEqual(2, raised.exception.code)

    def test_current_registry_builder_refuses_live_writer_without_overwrite(self) -> None:
        scope = _scope(_active("logic-writing", 0))
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            scope_path = workspace / "scope.json"
            scope_path.write_text(
                json.dumps(scope, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            registry_path = workspace / "registry.json"
            registry_path.write_text('{"sentinel": true}\n', encoding="utf-8")
            before = registry_path.read_bytes()

            real_lock = portfolio_registry_lock

            def short_live_lock(path: Path):
                return real_lock(path, timeout_seconds=0.01)

            with real_lock(registry_path):
                with mock.patch(
                    "skillguard_v2.portfolio_cli.portfolio_registry_lock",
                    side_effect=short_live_lock,
                ):
                    with self.assertRaises(PortfolioRegistryLockError):
                        build_current_portfolio_registry_command(
                            [
                                "--workspace-root",
                                str(workspace),
                                "--scope",
                                scope_path.name,
                                "--registry-id",
                                "current-direct-replacement",
                                "--runtime-root",
                                str(ROOT / ".agents" / "skills" / "skillguard"),
                                "--output",
                                registry_path.name,
                            ]
                        )

            self.assertEqual(before, registry_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
