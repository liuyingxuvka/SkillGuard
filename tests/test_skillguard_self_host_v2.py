from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import call, patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / ".agents" / "skills" / "skillguard" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from skillguard_v2.contract_compiler import compile_skill_contract  # noqa: E402
from skillguard_v2 import self_host  # noqa: E402
from skillguard_v2.self_host import (  # noqa: E402
    SelfHostError,
    _order_step_checks_by_owner_dependencies,
    _reopen_failed_steps_after_owner_input_change,
    _self_host_request,
    _select_ready_step_by_owner_dependencies,
    validate_self_host_long_check_timeout_budgets,
    validate_self_host_test_mesh_boundary,
)


class SkillGuardSelfHostV2Tests(unittest.TestCase):
    def test_self_host_fingerprints_use_the_location_derived_execution_boundary(self) -> None:
        runtime = {
            "runtime_id": "skillguard-v2",
            "source_hash": "sha256:" + "1" * 64,
        }
        contract = {
            "contract_hash": "sha256:" + "2" * 64,
            "source_fingerprints": {},
        }
        with patch.object(
            self_host,
            "guard_execution_runtime_fingerprint",
            return_value=runtime,
        ) as execution_fingerprint:
            fingerprints = self_host._current_fingerprints(contract)

        self.assertEqual(
            self_host.fingerprint_value(runtime),
            fingerprints["guard_runtime"],
        )
        self.assertEqual(2, execution_fingerprint.call_count)
        self.assertEqual([call(), call()], execution_fingerprint.call_args_list)

    def test_self_host_request_uses_the_direct_target_input_fingerprint(self) -> None:
        request = _self_host_request(ROOT, ("route:static-audit",))
        target_inputs = self_host.fingerprint_target_inputs(
            ROOT,
            request["target_input_paths"],
        )
        self.assertEqual(
            target_inputs["fingerprint"],
            request["target_input_fingerprint"],
        )

    def test_failed_step_reopens_only_after_exact_owner_identity_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_root = Path(directory)
            checks_root = run_root / "checks"
            checks_root.mkdir()
            (checks_root / "check-record-fixture.json").write_text("{}", encoding="utf-8")
            step = {
                "step_id": "step:install",
                "binding": {"check_ids": ["check:install"]},
            }
            check = {"check_id": "check:install", "execution_owner_id": "owner:install"}
            record = {
                "step_id": "step:install",
                "check_id": "check:install",
                "status": "failed",
                "execution_key": "sha256:" + "1" * 64,
            }
            inspection = {
                "identity": {"execution_key": "sha256:" + "2" * 64},
                "receipt": None,
            }
            with patch.object(
                self_host,
                "replay_run",
                return_value=SimpleNamespace(step_statuses={"step:install": "failed"}),
            ), patch.object(
                self_host, "load_check_result", return_value=record
            ), patch.object(
                self_host, "inspect_current_owner_execution", return_value=inspection
            ), patch.object(self_host, "reopen_step") as reopen:
                reopened = _reopen_failed_steps_after_owner_input_change(
                    run_root,
                    skill_root=ROOT / ".agents" / "skills" / "skillguard",
                    repository_root=ROOT,
                    persistent_owner_root=run_root / "owner",
                    selected_steps=[step],
                    check_index={"check:install": check},
                    owner_rows={"owner:install": {"depends_on_owner_ids": []}},
                    owner_receipts={},
                )
                self.assertEqual(("step:install",), reopened)
                reopen.assert_called_once()
            inspection["identity"]["execution_key"] = record["execution_key"]
            with patch.object(
                self_host,
                "replay_run",
                return_value=SimpleNamespace(step_statuses={"step:install": "failed"}),
            ), patch.object(
                self_host, "load_check_result", return_value=record
            ), patch.object(
                self_host, "inspect_current_owner_execution", return_value=inspection
            ), patch.object(self_host, "reopen_step") as reopen:
                reopened = _reopen_failed_steps_after_owner_input_change(
                    run_root,
                    skill_root=ROOT / ".agents" / "skills" / "skillguard",
                    repository_root=ROOT,
                    persistent_owner_root=run_root / "owner",
                    selected_steps=[step],
                    check_index={"check:install": check},
                    owner_rows={"owner:install": {"depends_on_owner_ids": []}},
                    owner_receipts={},
                )
                self.assertEqual((), reopened)
                reopen.assert_not_called()

    def test_ready_step_selection_respects_native_owner_dependencies(self) -> None:
        ready = [
            {
                "step_id": "step:dependent",
                "route_id": "route:static-audit",
                "binding": {"check_ids": ["check:dependent"]},
            },
            {
                "step_id": "step:owner",
                "route_id": "route:compile-contract",
                "binding": {"check_ids": ["check:owner"]},
            },
        ]
        check_index = {
            "check:dependent": {"execution_owner_id": "owner:dependent"},
            "check:owner": {"execution_owner_id": "owner:owner"},
        }
        owner_rows = {
            "owner:dependent": {
                "depends_on_owner_ids": ["owner:owner"]
            },
            "owner:owner": {"depends_on_owner_ids": []},
        }
        selected = _select_ready_step_by_owner_dependencies(
            ready,
            check_index=check_index,
            owner_rows=owner_rows,
            owner_receipts={},
        )
        self.assertEqual("step:owner", selected["step_id"])

        with self.assertRaises(SelfHostError) as caught:
            _select_ready_step_by_owner_dependencies(
                [ready[0]],
                check_index=check_index,
                owner_rows=owner_rows,
                owner_receipts={},
            )
        self.assertEqual(
            "self_host_owner_dependency_deadlock", caught.exception.code
        )

    def test_same_step_owner_dependencies_are_topologically_ordered(self) -> None:
        step = {
            "step_id": "step:combined",
            "route_id": "route:static-audit",
            "binding": {"check_ids": ["check:dependent", "check:owner"]},
        }
        check_index = {
            "check:dependent": {"execution_owner_id": "owner:dependent"},
            "check:owner": {"execution_owner_id": "owner:owner"},
        }
        owner_rows = {
            "owner:dependent": {"depends_on_owner_ids": ["owner:owner"]},
            "owner:owner": {"depends_on_owner_ids": []},
        }
        self.assertEqual(
            step,
            _select_ready_step_by_owner_dependencies(
                [step],
                check_index=check_index,
                owner_rows=owner_rows,
                owner_receipts={},
            ),
        )
        self.assertEqual(
            ("check:owner", "check:dependent"),
            _order_step_checks_by_owner_dependencies(
                step["binding"]["check_ids"],
                check_index=check_index,
                owner_rows=owner_rows,
                owner_receipts={},
            ),
        )

        owner_rows["owner:owner"]["depends_on_owner_ids"] = ["owner:dependent"]
        with self.assertRaises(SelfHostError) as caught:
            _order_step_checks_by_owner_dependencies(
                step["binding"]["check_ids"],
                check_index=check_index,
                owner_rows=owner_rows,
                owner_receipts={},
            )
        self.assertEqual(
            "self_host_step_owner_dependency_cycle", caught.exception.code
        )

    def test_generated_contracts_keep_canonical_lf_in_git_checkouts(self) -> None:
        attributes = set((ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines())
        self.assertIn(
            "/.agents/skills/skillguard/.skillguard/compiled-contract.json text eol=lf",
            attributes,
        )
        self.assertIn(
            "/.agents/skills/skillguard/.skillguard/check-manifest.json text eol=lf",
            attributes,
        )

    def test_self_contract_is_current_exact_and_not_broad_all(self) -> None:
        skill_root = ROOT / ".agents" / "skills" / "skillguard"
        result = compile_skill_contract(skill_root, repository_root=ROOT, write=False)
        self.assertTrue(result.ok, result.to_dict())
        contract = result.compiled_contract
        manifest = result.check_manifest
        self.assertEqual(31, sum(1 for row in contract["steps"] if not row["terminal_kind"]))
        self.assertEqual(
            {
                "artifact:self-compiled-contract",
                "artifact:self-check-manifest",
                "artifact:self-project-adoption-manifest",
                "artifact:self-project-prompt",
            },
            {row["artifact_id"] for row in contract["artifacts"]},
        )
        artifact_paths = {
            row["artifact_id"]: row["path_template"]
            for row in contract["artifacts"]
        }
        self.assertEqual(
            ".agents/skills/skillguard/.skillguard/compiled-contract.json",
            artifact_paths["artifact:self-compiled-contract"],
        )
        self.assertEqual(
            ".agents/skills/skillguard/.skillguard/check-manifest.json",
            artifact_paths["artifact:self-check-manifest"],
        )
        self.assertEqual(
            ".skillguard/project.json",
            artifact_paths["artifact:self-project-adoption-manifest"],
        )
        project_audit = next(
            row
            for row in manifest["checks"]
            if row["check_id"] == "check:self:audit-project-adoption"
        )
        self.assertEqual("command", project_audit["kind"])
        self.assertEqual("python", project_audit["command"])
        self.assertEqual(
            [
                ".agents/skills/skillguard/scripts/skillguard.py",
                "project-audit",
                "--root",
                ".",
            ],
            project_audit["args"],
        )
        all_obligations = {row["obligation_id"] for row in contract["obligations"]}
        for check in manifest["checks"]:
            coverage = set(check["covers_obligation_ids"])
            self.assertNotEqual(all_obligations, coverage, check["check_id"])
            self.assertTrue(coverage)

    def test_self_host_exposes_only_the_current_verifier(self) -> None:
        self.assertTrue(callable(self_host.run_current_verifier))
        self.assertTrue(callable(self_host.run_self_host_bootstrap))
        self.assertFalse(hasattr(self_host, "run_frozen_old_verifier"))
        self.assertFalse(hasattr(self_host, "run_new_verifier"))

    def test_real_test_mesh_uses_one_native_owner_without_nested_execution(self) -> None:
        manifest_path = (
            ROOT
            / ".agents"
            / "skills"
            / "skillguard"
            / ".skillguard"
            / "check-manifest.json"
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        checks = validate_self_host_test_mesh_boundary(ROOT, manifest)
        self.assertEqual(1, len(checks))
        boundary = checks[0]
        self.assertEqual("check:self:test-mesh-fast", boundary["check_id"])
        self.assertEqual([], boundary["nested_wrapper_check_ids"])
        self.assertEqual(
            "native_owner_once_then_read_only_aggregation",
            boundary["execution_mode"],
        )
        nested = copy.deepcopy(manifest)
        nested["checks"][0]["args"] = [
            *nested["checks"][0].get("args", []),
            "scripts/skillguard_test_mesh.py",
        ]
        with self.assertRaises(SelfHostError) as caught:
            validate_self_host_test_mesh_boundary(ROOT, nested)
        self.assertEqual(
            "self_host_nested_test_mesh_execution_forbidden",
            caught.exception.code,
        )

    def test_real_long_check_timeout_dominates_measured_ceiling(self) -> None:
        manifest_path = (
            ROOT
            / ".agents"
            / "skills"
            / "skillguard"
            / ".skillguard"
            / "check-manifest.json"
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        budgets = validate_self_host_long_check_timeout_budgets(manifest)
        self.assertEqual(1, len(budgets))
        budget = budgets[0]
        self.assertEqual("check:self:installation-safety", budget["check_id"])
        self.assertGreater(
            budget["declared_timeout_seconds"],
            budget["required_timeout_seconds"],
        )
        self.assertGreater(budget["headroom_seconds"], 0)

    def test_failure_matrix_manifest_is_public_and_bounded(self) -> None:
        path = ROOT / ".agents" / "skills" / "skillguard" / "fixtures" / "v2_self_host_failure_matrix" / "fixture-manifest.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(9, len(payload["cases"]))
        self.assertIn("do not prove", payload["claim_boundary"])


if __name__ == "__main__":
    unittest.main()
