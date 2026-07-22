from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from _skillguard_v2_runtime_fixture import (  # noqa: F401
    SCRIPT_ROOT,
    runtime_contract_with_checks,
)
from skillguard_v2.check_runner import get_or_execute_check
from skillguard_v2.execution_records import filesystem_path
import skillguard_v2.test_mesh as test_mesh_module
from skillguard_v2.route_runtime import select_routes
from skillguard_v2.run_store import claim_run
from skillguard_v2.test_mesh import (
    CURRENT_TEST_MESH_AGGREGATION_SCHEMA,
    CURRENT_TEST_MESH_MANIFEST_SCHEMA,
    CURRENT_TEST_MESH_OWNER_EXECUTION_SCHEMA,
    CURRENT_TEST_MESH_PLAN_SCHEMA,
    execute_test_mesh,
    _portfolio_targets_for_components,
    _portable_receipt_hash,
    project_current_test_mesh_aggregation_to_openspec_receipt,
    replay_current_test_mesh_aggregation,
)


class CurrentTestMeshTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repository = self.root / "repository"
        self.target = self.root / "target"
        self.skill = self.repository / "skill"
        self.repository.mkdir()
        self.target.mkdir()
        self.skill.mkdir()
        contract, manifest = runtime_contract_with_checks(
            [
                {
                    "check_id": "check:intake",
                    "kind": "command",
                    "command": sys.executable,
                    "args": ["-c", "print('current-owner')"],
                    "expected": {"exit_code": 0},
                    "covers_obligation_ids": ["obligation:intake"],
                }
            ]
        )
        decision = select_routes(contract, {"function_ids": ["analyze"]})
        claim = claim_run(
            contract,
            {
                "function_ids": ["analyze"],
                "write_targets": ["out"],
                "request": "current TestMesh",
            },
            self.target,
            decision,
            check_manifest=manifest,
        )
        self.assertTrue(claim.ok, claim.to_dict())
        assert claim.run_root is not None
        self.run_root = claim.run_root
        self.check = manifest["checks"][0]
        self.owner_root = (
            self.repository / "work" / "verification" / "owner-evidence"
        )
        self.mesh_manifest = self.repository / "test-mesh.json"
        self._write_mesh_manifest()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_mesh_manifest(self, *, second_profile: bool = False) -> None:
        profiles = [
            {
                "profile_id": "fast",
                "closure_profile_id": "enforced",
                "full_admission_required": False,
            },
            {
                "profile_id": "full",
                "closure_profile_id": "enforced",
                "full_admission_required": True,
            },
        ]
        if second_profile:
            profiles.append(
                {
                    "profile_id": "same-owners",
                    "closure_profile_id": "enforced",
                    "full_admission_required": False,
                }
            )
        self.mesh_manifest.write_text(
            json.dumps(
                {
                    "schema_version": CURRENT_TEST_MESH_MANIFEST_SCHEMA,
                    "mesh_id": "fixture-current-mesh",
                    "source_model_id": "fixture.current",
                    "profiles": profiles,
                    "claim_boundary": "Fixture current TestMesh only.",
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    def _plan(self, profile_id: str = "fast", **kwargs):
        return execute_test_mesh(
            self.mesh_manifest,
            self.repository,
            profile_id,
            run_root=self.run_root,
            skill_root=self.skill,
            target_root=self.target,
            owner_evidence_root=self.owner_root,
            **kwargs,
        )

    def test_shared_semantic_check_uses_first_declared_step_for_run_store(self) -> None:
        contract = json.loads(
            (self.run_root / "contract.json").read_text(encoding="utf-8")
        )
        first_step = deepcopy(contract["steps"][0])
        second_step = deepcopy(first_step)
        second_step["step_id"] = "step:second-shared-projection"
        contract["steps"].insert(1, second_step)

        self.assertEqual(
            first_step["step_id"],
            test_mesh_module._check_step_id(
                contract, self.check["check_id"]
            ),
        )

    def _execute_owner(self):
        return get_or_execute_check(
            self.check,
            skill_root=self.skill,
            target_root=self.target,
            repository_root=self.repository,
            run_root=self.run_root,
            step_id="step:intake",
            owner_evidence_root=self.owner_root,
        )

    def _claim_checks(
        self,
        checks,
        *,
        name: str,
        request_overrides: dict[str, object] | None = None,
    ) -> None:
        self.target = self.root / f"target-{name}"
        self.skill = self.repository / f"skill-{name}"
        self.target.mkdir()
        self.skill.mkdir()
        contract, manifest = runtime_contract_with_checks(checks)
        decision = select_routes(contract, {"function_ids": ["analyze"]})
        request = {
            "function_ids": ["analyze"],
            "write_targets": ["out"],
            "request": name,
            **dict(request_overrides or {}),
        }
        claim = claim_run(
            contract,
            request,
            self.target,
            decision,
            check_manifest=manifest,
        )
        self.assertTrue(claim.ok, claim.to_dict())
        assert claim.run_root is not None
        self.run_root = claim.run_root
        self.check = manifest["checks"][0]

    def test_missing_selected_target_role_blocks_before_any_owner_launch(
        self,
    ) -> None:
        self._claim_checks(
            [
                {
                    "check_id": "check:intake",
                    "kind": "command",
                    "command": sys.executable,
                    "args": ["-c", "print('intake')"],
                    "expected": {"exit_code": 0},
                    "covers_obligation_ids": ["obligation:intake"],
                    "target_input_role_ids": ["target.role.missing"],
                },
                {
                    "check_id": "check:downstream",
                    "kind": "command",
                    "command": sys.executable,
                    "args": ["-c", "print('downstream')"],
                    "expected": {"exit_code": 0},
                    "covers_obligation_ids": ["obligation:review"],
                    "depends_on_check_ids": ["check:intake"],
                    "target_input_role_ids": ["target.role.downstream"],
                },
            ],
            name="missing-downstream-role",
            request_overrides={
                "target_input_roles": {
                    "target.role.supplied": ["intake.txt"],
                }
            },
        )
        self.target.joinpath("intake.txt").write_text(
            "intake", encoding="utf-8"
        )
        plan = self._plan(
            "full",
            full_admission_reason="explicit_release_gate",
            freeze_identity={
                "source_identity_hash": "sha256:not-admitted",
                "toolchain_identity_hash": "sha256:not-admitted",
                "owner_plan_hash": "sha256:not-admitted",
            },
        )
        self.assertEqual("blocked", plan["status"])
        self.assertEqual(0, plan["execution_count"])
        self.assertTrue(
            any(
                "check_target_input_roles_missing" in finding
                for finding in plan["findings"]
            ),
            plan,
        )
        execution = self._run_frozen_owners(plan)
        self.assertEqual("blocked", execution["status"])
        self.assertEqual(0, execution["execution_count"])

    def _run_frozen_owners(self, frozen_plan):
        return self._plan(
            mode="owner_execution_only", frozen_plan=frozen_plan
        )

    def test_plan_lists_exact_missing_then_reusable_owner_without_execution(self) -> None:
        missing = self._plan()
        self.assertEqual(CURRENT_TEST_MESH_PLAN_SCHEMA, missing["schema_version"])
        self.assertEqual(["owner:intake"], missing["will_execute_owner_ids"])
        self.assertEqual(0, missing["execution_count"])
        self.assertFalse(hasattr(test_mesh_module, "subprocess"))
        self._execute_owner()
        current = self._plan()
        self.assertEqual([], current["will_execute_owner_ids"])
        self.assertEqual(["owner:intake"], current["will_reuse_owner_ids"])
        self.assertEqual(0, current["execution_count"])

    def test_aggregation_only_references_child_and_read_only_replay(self) -> None:
        frozen_plan = self._plan()
        execution = self._run_frozen_owners(frozen_plan)
        self.assertEqual(
            CURRENT_TEST_MESH_OWNER_EXECUTION_SCHEMA,
            execution["schema_version"],
        )
        self.assertEqual("passed", execution["status"])
        self.assertEqual(["owner:intake"], execution["executed_owner_ids"])
        self.assertEqual(1, execution["execution_count"])
        aggregation = self._plan(
            mode="aggregation_only", frozen_plan=frozen_plan
        )
        self.assertEqual(
            CURRENT_TEST_MESH_AGGREGATION_SCHEMA,
            aggregation["schema_version"],
        )
        self.assertEqual("passed", aggregation["status"])
        self.assertEqual(0, aggregation["execution_count"])
        self.assertEqual(1, len(aggregation["child_receipts"]))
        current_aggregation_authorities = list(
            (self.owner_root / "lifecycle" / "current-aggregations").glob("*.json")
        )
        self.assertEqual(1, len(current_aggregation_authorities))
        authority = json.loads(
            current_aggregation_authorities[0].read_text(encoding="utf-8")
        )
        self.assertEqual(
            aggregation["aggregation_ref"], authority["aggregation_ref"]
        )
        replay = replay_current_test_mesh_aggregation(
            self.owner_root,
            aggregation["aggregation_ref"],
        )
        self.assertEqual("passed", replay["status"])
        self.assertEqual(0, replay["execution_count"])

    def test_frozen_runner_reuses_after_freeze_without_repeated_execution(self) -> None:
        frozen_plan = self._plan()
        first = self._run_frozen_owners(frozen_plan)
        second = self._run_frozen_owners(frozen_plan)
        self.assertEqual("passed", first["status"])
        self.assertEqual(1, first["execution_count"])
        self.assertEqual("passed", second["status"])
        self.assertEqual(0, second["execution_count"])
        self.assertEqual(
            ["owner:intake"], second["reused_after_freeze_owner_ids"]
        )

    def test_distinct_semantic_checks_explicitly_share_one_execution_owner(self) -> None:
        shared = {
            "kind": "command",
            "command": sys.executable,
            "args": ["-c", "print('shared-owner')"],
            "expected": {"exit_code": 0},
            "execution_owner_id": "owner:shared",
        }
        self._claim_checks(
            [
                {
                    **shared,
                    "check_id": "check:intake",
                    "covers_obligation_ids": ["obligation:intake"],
                },
                {
                    **shared,
                    "check_id": "check:review",
                    "covers_obligation_ids": ["obligation:review"],
                },
            ],
            name="shared-owner",
        )

        frozen_plan = self._plan()
        self.assertEqual("passed", frozen_plan["status"], frozen_plan)
        self.assertEqual(["owner:shared"], frozen_plan["selected_owner_ids"])
        self.assertEqual(["owner:shared"], frozen_plan["will_execute_owner_ids"])
        owner_plan = frozen_plan["owner_plans"][0]
        self.assertEqual(
            ["check:intake", "check:review"], owner_plan["check_ids"]
        )
        self.assertEqual(
            ["check:intake", "check:review"],
            [row["check_id"] for row in owner_plan["check_projections"]],
        )
        self.assertEqual(
            2,
            len(
                {
                    row["projection_declaration_hash"]
                    for row in owner_plan["check_projections"]
                }
            ),
        )

        execution = self._run_frozen_owners(frozen_plan)
        self.assertEqual("passed", execution["status"], execution)
        self.assertEqual(1, execution["execution_count"])
        self.assertEqual(["owner:shared"], execution["executed_owner_ids"])
        self.assertEqual(
            ["check:intake", "check:review"],
            execution["owner_results"][0]["check_ids"],
        )

    def test_mismatched_shared_owner_rejection_happens_before_execution(self) -> None:
        shared = {
            "kind": "command",
            "command": sys.executable,
            "args": ["-c", "print('shared-owner')"],
            "expected": {"exit_code": 0},
            "execution_owner_id": "owner:shared",
        }
        with patch.object(test_mesh_module, "get_or_execute_check") as execute:
            with self.assertRaises(AssertionError):
                self._claim_checks(
                    [
                        {**shared, "check_id": "check:intake", "covers_obligation_ids": ["obligation:intake"]},
                        {
                            **shared,
                            "check_id": "check:review",
                            "covers_obligation_ids": ["obligation:review"],
                            "timeout_seconds": 31,
                        },
                    ],
                    name="shared-owner-omission",
                )
        execute.assert_not_called()

    def test_post_launch_persistence_error_preserves_process_count(self) -> None:
        marker = self.root / "post-launch-process-ran.txt"
        self._claim_checks(
            [
                {
                    "check_id": "check:intake",
                    "kind": "command",
                    "command": sys.executable,
                    "args": [
                        "-c",
                        f"from pathlib import Path; Path({str(marker)!r}).write_text('ran')",
                    ],
                    "expected": {"exit_code": 0},
                    "covers_obligation_ids": ["obligation:intake"],
                }
            ],
            name="post-launch-persistence-error",
        )
        frozen_plan = self._plan()
        with patch(
            "skillguard_v2.check_runner._persist_stream_sidecar",
            side_effect=OSError("forced post-launch persistence failure"),
        ):
            report = self._run_frozen_owners(frozen_plan)
        self.assertTrue(marker.is_file())
        self.assertEqual("failed", report["status"])
        self.assertEqual(1, report["execution_count"])
        self.assertEqual(["owner:intake"], report["failed_owner_ids"])
        self.assertEqual([], report["not_run_owner_ids"])
        self.assertIs(report["owner_results"][0]["process_started"], True)

    def test_frozen_runner_rejects_recomputed_partition_tamper_without_execution(self) -> None:
        frozen_plan = deepcopy(self._plan())
        frozen_plan["will_execute_owner_ids"] = []
        frozen_plan["will_reuse_owner_ids"] = ["owner:intake"]
        frozen_plan["will_aggregate_only"] = True
        frozen_plan["plan_hash"] = test_mesh_module._current_plan_hash(
            frozen_plan
        )
        with patch.object(test_mesh_module, "get_or_execute_check") as execute:
            report = self._run_frozen_owners(frozen_plan)
        self.assertEqual("blocked", report["status"])
        self.assertEqual(0, report["execution_count"])
        execute.assert_not_called()
        self.assertTrue(
            any("frozen_owner_plan_stale" in value for value in report["findings"])
        )

    def test_frozen_runner_rejects_recomputed_dependency_tamper_without_execution(self) -> None:
        frozen_plan = deepcopy(self._plan())
        frozen_plan["owner_plans"][0]["depends_on_owner_ids"] = [
            "owner:undeclared"
        ]
        frozen_plan["plan_hash"] = test_mesh_module._current_plan_hash(
            frozen_plan
        )
        with patch.object(test_mesh_module, "get_or_execute_check") as execute:
            report = self._run_frozen_owners(frozen_plan)
        self.assertEqual("blocked", report["status"])
        self.assertEqual(0, report["execution_count"])
        execute.assert_not_called()
        self.assertEqual(
            ["current_test_mesh_frozen_owner_plan_stale:owner:intake"],
            report["findings"],
        )

    def test_frozen_runner_blocks_stale_planned_reuse_before_any_execution(self) -> None:
        receipt = self._execute_owner()["execution_receipt"]
        frozen_plan = self._plan()
        head = (
            self.owner_root
            / "check-executions"
            / "heads"
            / f"{receipt['execution_key'].split(':', 1)[1]}.json"
        )
        head.unlink()
        with patch.object(test_mesh_module, "get_or_execute_check") as execute:
            report = self._run_frozen_owners(frozen_plan)
        self.assertEqual("blocked", report["status"])
        self.assertEqual(0, report["execution_count"])
        execute.assert_not_called()
        self.assertEqual(
            ["planned_owner_receipt_changed:owner:intake"],
            report["findings"],
        )

    @unittest.skipUnless(os.name == "nt", "Windows extended-length path regression")
    def test_replay_and_projection_read_parent_beyond_max_path(self) -> None:
        long_root = self.root / "long-owner-evidence"
        long_owner = long_root
        representative = (
            Path("test-mesh")
            / "aggregations"
            / "aa"
            / (("b" * 64) + ".json")
        )
        while len(str(long_owner / representative)) <= 260:
            long_owner /= "segment-abcdefghij"
        long_owner.mkdir(parents=True)
        original_owner_root = self.owner_root
        self.owner_root = long_owner
        try:
            frozen_plan = self._plan()
            self._execute_owner()
            aggregation = self._plan(
                mode="aggregation_only", frozen_plan=frozen_plan
            )
            aggregation_path = (
                self.owner_root
                / aggregation["aggregation_ref"]["relative_path"]
            )
            self.assertGreater(len(str(aggregation_path)), 260)

            replay = replay_current_test_mesh_aggregation(
                self.owner_root,
                aggregation["aggregation_ref"],
            )
            self.assertEqual("passed", replay["status"])
            self.assertEqual(0, replay["execution_count"])

            with self.assertRaisesRegex(
                ValueError,
                "external_provider_receipt_bridge_forbidden",
            ):
                project_current_test_mesh_aggregation_to_openspec_receipt(
                    self.repository,
                    self.owner_root,
                    aggregation["aggregation_ref"],
                    evidence_root=self.repository / "work" / "verification" / "long-read",
                    evidence_root_token="SKILLGUARD_EVIDENCE",
                    provider_id="skillguard",
                    work_package_id="fixture-long-read",
                    check_id="check.fixture.long-read",
                    semantic_check_id="semantic.fixture.long-read",
                    execution_id="execution.fixture.long-read.current",
                    coverage_ids=("req.fixture.long-read",),
                    validation_obligation_ids=("req.fixture.long-read",),
                    source_paths=("test-mesh.json",),
                    toolchain_fingerprint=frozen_plan["toolchain_identity_hash"],
                )
        finally:
            self.owner_root = original_owner_root
            shutil.rmtree(filesystem_path(long_root))

    def test_parent_profile_change_is_aggregation_only(self) -> None:
        self._write_mesh_manifest(second_profile=True)
        self._execute_owner()
        first_plan = self._plan()
        second_plan = self._plan("same-owners")
        first = self._plan(
            mode="aggregation_only", frozen_plan=first_plan
        )
        second = self._plan(
            "same-owners",
            mode="aggregation_only",
            frozen_plan=second_plan,
        )
        self.assertEqual("passed", first["status"])
        self.assertEqual("passed", second["status"])
        self.assertEqual(0, first["execution_count"])
        self.assertEqual(0, second["execution_count"])
        self.assertNotEqual(first["aggregation_id"], second["aggregation_id"])
        self.assertEqual(
            first["child_receipts"][0]["receipt_id"],
            second["child_receipts"][0]["receipt_id"],
        )

    def test_missing_child_and_full_without_freeze_fail_closed(self) -> None:
        frozen_plan = self._plan()
        missing = self._plan(
            mode="aggregation_only", frozen_plan=frozen_plan
        )
        self.assertEqual("blocked", missing["status"])
        self.assertIn("owner_receipt_missing", missing["findings"][0])
        full = self._plan("full")
        self.assertEqual("blocked", full["status"])
        self.assertEqual(
            ["full_gate_requires_exact_freeze_and_derived_reason"],
            full["findings"],
        )

    def test_plan_reads_persistent_ticket_without_run_projection(self) -> None:
        self._execute_owner()
        checks_root = self.run_root / "checks"
        for path in checks_root.glob("*.json"):
            path.unlink()
        checks_root.rmdir()
        plan = self._plan()
        self.assertEqual("passed", plan["status"])
        self.assertEqual(["owner:intake"], plan["will_reuse_owner_ids"])
        self.assertEqual([], plan["will_execute_owner_ids"])
        self.assertFalse(checks_root.exists())
        self.assertFalse(hasattr(test_mesh_module, "subprocess"))

    def test_frozen_plan_tamper_blocks_without_execution(self) -> None:
        frozen_plan = self._plan()
        self._execute_owner()
        frozen_plan["selected_owner_ids"] = ["owner:tampered"]
        report = self._plan(
            mode="aggregation_only", frozen_plan=frozen_plan
        )
        self.assertEqual("blocked", report["status"])
        self.assertEqual(
            ["current_test_mesh_frozen_plan_invalid"], report["findings"]
        )
        self.assertEqual(0, report["execution_count"])
        self.assertFalse(hasattr(test_mesh_module, "subprocess"))

    def test_read_only_replay_rejects_tampered_aggregation_reference(self) -> None:
        frozen_plan = self._plan()
        self._execute_owner()
        aggregation = self._plan(
            mode="aggregation_only", frozen_plan=frozen_plan
        )
        reference = dict(aggregation["aggregation_ref"])
        reference["content_hash"] = "sha256:" + "f" * 64
        replay = replay_current_test_mesh_aggregation(
            self.owner_root, reference
        )
        self.assertEqual("blocked", replay["status"])
        self.assertIn("aggregation_content_hash_mismatch", replay["findings"])
        self.assertEqual(0, replay["execution_count"])
        self.assertFalse(hasattr(test_mesh_module, "subprocess"))

    def test_read_only_replay_rejects_missing_child_receipt(self) -> None:
        frozen_plan = self._plan()
        self._execute_owner()
        aggregation = self._plan(
            mode="aggregation_only", frozen_plan=frozen_plan
        )
        child_ref = aggregation["child_receipts"][0]["receipt_ref"]
        (self.owner_root / child_ref["relative_path"]).unlink()
        replay = replay_current_test_mesh_aggregation(
            self.owner_root, aggregation["aggregation_ref"]
        )
        self.assertEqual("blocked", replay["status"])
        self.assertTrue(
            any(
                finding.startswith("aggregation_child_invalid:owner:intake")
                for finding in replay["findings"]
            )
        )
        self.assertEqual(0, replay["execution_count"])
        self.assertFalse(hasattr(test_mesh_module, "subprocess"))

    def test_external_provider_receipt_projection_is_rejected(self) -> None:
        frozen_plan = self._plan()
        self._execute_owner()
        aggregation = self._plan(
            mode="aggregation_only", frozen_plan=frozen_plan
        )
        evidence_root = self.repository / "work" / "verification" / "final"
        with self.assertRaisesRegex(
            ValueError,
            "external_provider_receipt_bridge_forbidden",
        ):
            project_current_test_mesh_aggregation_to_openspec_receipt(
                self.repository,
                self.owner_root,
                aggregation["aggregation_ref"],
                evidence_root=evidence_root,
                evidence_root_token="SKILLGUARD_EVIDENCE",
                provider_id="skillguard",
                work_package_id="fixture-change",
                check_id="check.fixture.final-parent",
                semantic_check_id="semantic.fixture.final-parent",
                execution_id="execution.fixture.final-parent.current",
                coverage_ids=("req.fixture",),
                validation_obligation_ids=("req.fixture",),
                source_paths=("test-mesh.json",),
                toolchain_fingerprint=frozen_plan["toolchain_identity_hash"],
            )
        self.assertFalse(evidence_root.exists())
        self.assertFalse(hasattr(test_mesh_module, "subprocess"))

    def test_portable_hash_matches_openspec_locale_order_for_skill_paths(self) -> None:
        payload = {
            "source_hash_policy": {
                "version": 2,
                "algorithm": "sha256",
                "task_checkbox_normalization": "markdown-checkbox-state-v1",
                "output_classifier_version": "verification-generated-output-v2",
            },
            "files": {
                "scripts/check.py": "sha256:" + ("1" * 64),
                "SKILL.md": "sha256:" + ("2" * 64),
                "skills/demo/SKILL.md": "sha256:" + ("3" * 64),
            },
        }
        self.assertEqual(
            "sha256:ddc51b6219672155a944484febe97a3b0bb9b03f22c6ade027b7d93116115317",
            _portable_receipt_hash(payload),
        )

    def test_portable_hash_matches_openspec_punctuation_order_for_paths(self) -> None:
        payload = {
            "files": {
                "tests/test_semantic_rollout.py": "sha256:" + ("a" * 64),
                "tests/test_semantic_rollout_runner.py": "sha256:" + ("b" * 64),
                "skills/worldguard/.skillguard/contract-source.json": (
                    "sha256:" + ("c" * 64)
                ),
                "skills/worldguard/.skillguard/contract_model.py": (
                    "sha256:" + ("d" * 64)
                ),
            }
        }
        self.assertEqual(
            "sha256:8d5d82d1174b62e051f31e886dd55f91a649452854320843530551c8840b591c",
            _portable_receipt_hash(payload),
        )

    def test_external_provider_bridge_rejects_before_source_path_handling(self) -> None:
        frozen_plan = self._plan()
        self._execute_owner()
        aggregation = self._plan(
            mode="aggregation_only", frozen_plan=frozen_plan
        )
        (self.repository / "技能.md").write_text("source", encoding="utf-8")
        evidence_root = self.repository / "work" / "verification" / "final"
        with self.assertRaisesRegex(
            ValueError,
            "external_provider_receipt_bridge_forbidden",
        ):
            project_current_test_mesh_aggregation_to_openspec_receipt(
                self.repository,
                self.owner_root,
                aggregation["aggregation_ref"],
                evidence_root=evidence_root,
                evidence_root_token="SKILLGUARD_EVIDENCE",
                provider_id="skillguard",
                work_package_id="fixture-change",
                check_id="check.fixture.final-parent",
                semantic_check_id="semantic.fixture.final-parent",
                execution_id="execution.fixture.final-parent.current",
                coverage_ids=("req.fixture",),
                validation_obligation_ids=("req.fixture",),
                source_paths=("技能.md",),
                toolchain_fingerprint=frozen_plan["toolchain_identity_hash"],
            )

    def test_external_provider_bridge_rejects_stale_parent_without_writes(self) -> None:
        frozen_plan = self._plan()
        self._execute_owner()
        aggregation = self._plan(
            mode="aggregation_only", frozen_plan=frozen_plan
        )
        reference = dict(aggregation["aggregation_ref"])
        reference["content_hash"] = "sha256:" + "f" * 64
        evidence_root = self.repository / "work" / "verification" / "final"
        with self.assertRaisesRegex(
            ValueError,
            "external_provider_receipt_bridge_forbidden",
        ):
            project_current_test_mesh_aggregation_to_openspec_receipt(
                self.repository,
                self.owner_root,
                reference,
                evidence_root=evidence_root,
                evidence_root_token="SKILLGUARD_EVIDENCE",
                provider_id="skillguard",
                work_package_id="fixture-change",
                check_id="check.fixture.final-parent",
                semantic_check_id="semantic.fixture.final-parent",
                execution_id="execution.fixture.final-parent.current",
                coverage_ids=("req.fixture",),
                validation_obligation_ids=("req.fixture",),
                source_paths=("test-mesh.json",),
                toolchain_fingerprint=frozen_plan["toolchain_identity_hash"],
            )
        self.assertFalse(evidence_root.exists())
        self.assertFalse(hasattr(test_mesh_module, "subprocess"))

    def test_plan_exposes_exact_impact_and_follow_up_actions(self) -> None:
        plan = self._plan()
        self.assertEqual("passed", plan["status"])
        self.assertEqual(["owner:intake"], plan["selected_owner_ids"])
        self.assertEqual(["owner:intake"], plan["will_execute_owner_ids"])
        self.assertEqual([], plan["will_reuse_owner_ids"])
        self.assertIs(plan["will_aggregate_only"], False)
        self.assertRegex(plan["plan_hash"], r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(
            plan["source_identity_hash"], r"^sha256:[0-9a-f]{64}$"
        )
        self.assertRegex(
            plan["toolchain_identity_hash"], r"^sha256:[0-9a-f]{64}$"
        )
        self.assertEqual(1, len(plan["owner_plans"]))

    def test_portfolio_scope_uses_only_explicit_component_edges(self) -> None:
        impact_plan = {
            "portfolio_target_edges": [
                {
                    "target_id": "skill-a",
                    "input_component_ids": ["component:function-a"],
                    "member_ids": [],
                },
                {
                    "target_id": "skill-b",
                    "input_component_ids": ["component:function-b"],
                    "member_ids": [],
                },
            ]
        }
        self.assertEqual(
            ["skill-a"],
            _portfolio_targets_for_components(
                impact_plan, {"component:function-a"}
            ),
        )
        self.assertEqual(
            [],
            _portfolio_targets_for_components(
                impact_plan, {"component:test-report-only"}
            ),
        )

    def test_legacy_manifest_is_rejection_only(self) -> None:
        self.mesh_manifest.write_text(
            '{"schema_version":"skillguard.test_mesh_manifest.v2"}\n',
            encoding="utf-8",
        )
        report = self._plan()
        self.assertEqual("blocked", report["status"])
        self.assertEqual(["legacy_test_mesh_manifest_rejected"], report["findings"])

    def test_manifest_cannot_copy_an_owner_command(self) -> None:
        payload = json.loads(self.mesh_manifest.read_text(encoding="utf-8"))
        payload["command"] = [sys.executable, "-m", "pytest"]
        self.mesh_manifest.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        report = self._plan()
        self.assertEqual("blocked", report["status"])
        self.assertEqual(
            ["current_test_mesh_manifest_field_set_invalid"],
            report["findings"],
        )
        self.assertEqual(0, report["execution_count"])
        self.assertFalse(hasattr(test_mesh_module, "subprocess"))


if __name__ == "__main__":
    unittest.main()
