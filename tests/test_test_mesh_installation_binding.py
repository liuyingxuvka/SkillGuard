from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / ".agents" / "skills" / "skillguard" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from skillguard_v2.contract_compiler import canonical_hash, wire_hash  # noqa: E402
from skillguard_v2.check_runner import (  # noqa: E402
    check_toolchain_identity,
    get_or_execute_check,
)
from skillguard_v2.execution_records import ExecutionRecordError  # noqa: E402
from skillguard_v2.installation_receipt import (  # noqa: E402
    build_installation_verification_receipt,
    write_installation_verification_receipt,
)
from skillguard_v2.test_mesh import (  # noqa: E402
    CURRENT_TEST_MESH_AGGREGATION_SCHEMA,
    CURRENT_TEST_MESH_MANIFEST_SCHEMA,
    _load_current_installation_binding,
    _load_global_prompt_currentness_binding,
    execute_test_mesh,
    replay_current_test_mesh_aggregation,
)
from skillguard_v2.global_router_projection import (  # noqa: E402
    build_prompt_projection,
)
from skillguard_v2.route_runtime import select_routes  # noqa: E402
from skillguard_v2.run_store import claim_run  # noqa: E402
from _skillguard_v2_runtime_fixture import runtime_contract_with_checks  # noqa: E402


INSTALLATION_RECEIPT_RELATIVE_PATH = (
    "skills/skillguard/.sg-runtime/installation"
)


def fixture_source_identity(hash_character: str) -> dict[str, object]:
    return {
        "exists": True,
        "kind": "directory",
        "manifest_hash": hash_character * 64,
        "file_count": 1,
    }


def fixture_runtime_fingerprint(hash_character: str) -> dict[str, object]:
    return {
        "runtime_id": "skillguard-v2",
        "provider_id": "skillguard-local-provider",
        "runtime_contract_id": "skillguard-declared-check-supervision-current",
        "capability_ids": ["fixture-runtime"],
        "enrollment_status": "enrolled",
        "file_count": 1,
        "source_hash": hash_character * 64,
    }


def fixture_installation_binding() -> dict[str, object]:
    binding: dict[str, object] = {
        "schema_version": "skillguard.test_mesh_typed_domain_binding.current",
        "evidence_domain": "active_installation",
        "owner_id": "skillguard-installation",
        "installation_receipt_root_ref": {
            "path_token": "codex_home",
            "relative_path": INSTALLATION_RECEIPT_RELATIVE_PATH,
        },
        "member_projection_hash": "sha256:" + "1" * 64,
        "content_consumer_projection_hash": "sha256:" + "2" * 64,
        "installed_smoke_result_hash": "sha256:" + "3" * 64,
        "installed_smoke_contract_hash": "sha256:" + "4" * 64,
        "owner_receipt_projection_hash": "sha256:" + "5" * 64,
    }
    binding["binding_hash"] = wire_hash(binding)
    return binding


def fixture_global_prompt_binding() -> dict[str, object]:
    binding: dict[str, object] = {
        "schema_version": "skillguard.test_mesh_typed_domain_binding.current",
        "evidence_domain": "global_prompt",
        "owner_id": "skillguard-global-router",
        "registry_ref": {
            "path_token": "codex_home",
            "relative_path": ".skillguard/global-router/global_registry.json",
        },
        "projection_ref": {
            "path_token": "codex_home",
            "relative_path": ".skillguard/global-router/global_prompt_projection.json",
        },
        "prompt_ref": {
            "path_token": "codex_home",
            "relative_path": "AGENTS.md",
        },
        "registry_hash": "sha256:" + "6" * 64,
        "managed_prompt_block_hash": "sha256:" + "8" * 64,
        "prompt_projection_identity_hash": "sha256:" + "9" * 64,
        "content_consumer_projection_hash": "sha256:" + "a" * 64,
    }
    binding["binding_hash"] = wire_hash(binding)
    return binding


class TestMeshInstallationBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.workspace = Path(self.temp.name)
        self.repository = self.workspace / "repository"
        self.target = self.workspace / "target"
        self.skill = self.repository / "skill"
        self.repository.mkdir()
        self.target.mkdir()
        self.skill.mkdir()
        self.codex_home = self.workspace / "codex-home"
        self.installation_root = (
            self.codex_home / Path(INSTALLATION_RECEIPT_RELATIVE_PATH)
        )
        self.installation_root.mkdir(parents=True)
        contract, manifest = runtime_contract_with_checks(
            [
                {
                    "check_id": "check:intake",
                    "kind": "command",
                    "command": sys.executable,
                    "args": ["-c", "print('current-install-owner')"],
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
                "request": "current installation binding",
            },
            self.target,
            decision,
            check_manifest=manifest,
        )
        self.assertTrue(claim.ok, claim.to_dict())
        assert claim.run_root is not None
        self.run_root = claim.run_root
        self.check = manifest["checks"][0]
        self.owner_root = self.repository / "owner-evidence"
        self.impact_graph_hash = str(
            contract["content_impact_plan"]["impact_graph_hash"]
        )
        self.freeze_identity = {
            "source_identity_hash": str(
                contract["content_impact_plan"]["inventory_hash"]
            ),
            "toolchain_identity_hash": wire_hash(
                [
                    {
                        "execution_owner_id": "owner:intake",
                        **check_toolchain_identity(self.check),
                    }
                ]
            ),
            "owner_plan_hash": self.impact_graph_hash,
        }
        self.manifest_payload = {
            "schema_version": CURRENT_TEST_MESH_MANIFEST_SCHEMA,
            "mesh_id": "installation-binding-fixture",
            "source_model_id": "fixture.current",
            "profiles": [
                {
                    "profile_id": "full",
                    "closure_profile_id": "enforced",
                    "full_admission_required": True,
                }
            ],
            "claim_boundary": "Installation binding fixture only.",
        }
        self.manifest_path = self.workspace / "manifest.json"
        self.manifest_path.write_text(
            json.dumps(self.manifest_payload), encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _binding(self) -> dict[str, object]:
        return fixture_installation_binding()

    def _execute_owner(self) -> None:
        result = get_or_execute_check(
            self.check,
            skill_root=self.skill,
            target_root=self.target,
            repository_root=self.repository,
            run_root=self.run_root,
            step_id="step:intake",
            owner_evidence_root=self.owner_root,
        )
        self.assertEqual(
            "passed", (result.get("record") or {}).get("status"), result
        )

    def _plan(self):
        return execute_test_mesh(
            self.manifest_path,
            self.repository,
            "full",
            run_root=self.run_root,
            skill_root=self.skill,
            target_root=self.target,
            owner_evidence_root=self.owner_root,
            mode="plan_only",
            full_admission_reason="explicit_final_gate",
            freeze_identity=self.freeze_identity,
        )

    def _aggregate(self, *, include_installation: bool = True):
        frozen_plan = self._plan()
        self.assertEqual("passed", frozen_plan["status"], frozen_plan)
        return execute_test_mesh(
            self.manifest_path,
            self.repository,
            "full",
            run_root=self.run_root,
            skill_root=self.skill,
            target_root=self.target,
            owner_evidence_root=self.owner_root,
            mode="aggregation_only",
            frozen_plan=frozen_plan,
            full_admission_reason="explicit_final_gate",
            freeze_identity=self.freeze_identity,
            installation_receipt_root=(
                self.installation_root if include_installation else None
            ),
            global_prompt_codex_home=self.codex_home,
        )

    def test_full_execution_without_installation_receipt_blocks_before_launch(self) -> None:
        marker = self.workspace / "must-not-run.txt"
        with patch(
            "skillguard_v2.test_mesh._load_global_prompt_currentness_binding",
            return_value=fixture_global_prompt_binding(),
        ):
            report = self._aggregate(include_installation=False)
        self.assertEqual("blocked", report["status"], report)
        self.assertIn("installation_receipt_root_required", report["findings"])
        self.assertFalse(marker.exists())
        self.assertEqual(0, report["execution_count"])

    def test_full_result_closure_and_replay_bind_current_installation(self) -> None:
        binding = self._binding()
        prompt_binding = fixture_global_prompt_binding()
        self._execute_owner()
        with patch(
            "skillguard_v2.test_mesh._load_current_installation_binding",
            return_value=copy.deepcopy(binding),
        ), patch(
            "skillguard_v2.test_mesh._load_global_prompt_currentness_binding",
            return_value=copy.deepcopy(prompt_binding),
        ):
            report = self._aggregate()
            replay = replay_current_test_mesh_aggregation(
                self.owner_root,
                report["aggregation_ref"],
                repository_root=self.repository,
                global_prompt_codex_home=self.codex_home,
            )
        self.assertEqual(CURRENT_TEST_MESH_AGGREGATION_SCHEMA, report["schema_version"])
        self.assertEqual("passed", report["status"], report)
        self.assertEqual(binding, report["installation_verification_identity"])
        self.assertEqual([prompt_binding], report["typed_domain_bindings"])
        self.assertEqual("passed", replay["status"], replay)
        self.assertEqual(0, report["execution_count"])

    def test_replay_rejects_installation_identity_drift(self) -> None:
        binding = self._binding()
        prompt_binding = fixture_global_prompt_binding()
        self._execute_owner()
        with patch(
            "skillguard_v2.test_mesh._load_current_installation_binding",
            return_value=copy.deepcopy(binding),
        ), patch(
            "skillguard_v2.test_mesh._load_global_prompt_currentness_binding",
            return_value=copy.deepcopy(prompt_binding),
        ):
            report = self._aggregate()
        changed = copy.deepcopy(binding)
        changed["member_projection_hash"] = "sha256:" + "f" * 64
        unsigned = dict(changed)
        unsigned.pop("binding_hash")
        changed["binding_hash"] = wire_hash(unsigned)
        with patch(
            "skillguard_v2.test_mesh._load_current_installation_binding",
            return_value=changed,
        ), patch(
            "skillguard_v2.test_mesh._load_global_prompt_currentness_binding",
            return_value=copy.deepcopy(prompt_binding),
        ):
            replay = replay_current_test_mesh_aggregation(
                self.owner_root,
                report["aggregation_ref"],
                repository_root=self.repository,
                global_prompt_codex_home=self.codex_home,
            )
        self.assertEqual("blocked", replay["status"], replay)
        self.assertIn(
            "installation_identity_current_mismatch:member_projection_hash",
            replay["findings"],
        )

    def test_replay_rejects_global_prompt_currentness_drift(self) -> None:
        binding = self._binding()
        prompt_binding = fixture_global_prompt_binding()
        self._execute_owner()
        with patch(
            "skillguard_v2.test_mesh._load_current_installation_binding",
            return_value=copy.deepcopy(binding),
        ), patch(
            "skillguard_v2.test_mesh._load_global_prompt_currentness_binding",
            return_value=copy.deepcopy(prompt_binding),
        ):
            report = self._aggregate()
        changed = copy.deepcopy(prompt_binding)
        changed["managed_prompt_block_hash"] = "sha256:" + "b" * 64
        unsigned = dict(changed)
        unsigned.pop("binding_hash")
        changed["binding_hash"] = wire_hash(unsigned)
        with patch(
            "skillguard_v2.test_mesh._load_current_installation_binding",
            return_value=copy.deepcopy(binding),
        ), patch(
            "skillguard_v2.test_mesh._load_global_prompt_currentness_binding",
            return_value=changed,
        ):
            replay = replay_current_test_mesh_aggregation(
                self.owner_root,
                report["aggregation_ref"],
                repository_root=self.repository,
                global_prompt_codex_home=self.codex_home,
            )
        self.assertEqual("blocked", replay["status"], replay)
        self.assertIn(
            "global_prompt_currentness_mismatch:managed_prompt_block_hash",
            replay["findings"],
        )

    def test_loader_consumes_one_sealed_current_snapshot(self) -> None:
        snapshot = {
            "transaction_id": "install-" + "1" * 32,
            "install_head_hash": "1" * 64,
            "activation_receipt_hash": "2" * 64,
            "stage_verification_hash": "3" * 64,
            "post_activation_smoke_hash": "4" * 64,
            "post_activation_member_comparisons_hash": "5" * 64,
            "rollback_disposition": "not_required",
            "canonical_source_identity": fixture_source_identity("6"),
            "installed_source_identity": fixture_source_identity("6"),
            "canonical_runtime_fingerprint": fixture_runtime_fingerprint("7"),
            "installed_runtime_fingerprint": fixture_runtime_fingerprint("7"),
            "current_installed_smoke_hash": "8" * 64,
            "current_installed_smoke_command_fingerprint": "9" * 64,
            "current_installed_smoke_environment_fingerprint": "A" * 64,
        }
        receipt = build_installation_verification_receipt(snapshot)
        write_installation_verification_receipt(self.installation_root, receipt)
        head = json.loads((self.installation_root / "HEAD.json").read_text(encoding="utf-8"))
        context = SimpleNamespace(
            head=copy.deepcopy(head),
            receipt=copy.deepcopy(receipt),
            current_snapshot=copy.deepcopy(snapshot),
        )
        projection = {
            "identity_hash": "sha256:" + "b" * 64,
            "consumer_projection_hash": "sha256:" + "c" * 64,
        }
        comparison = {
            "status": "current",
            "canonical_installation_projection": projection,
            "installed_installation_projection": projection,
        }
        with patch(
            "skillguard_v2.test_mesh.resolve_codex_home_root",
            return_value=self.codex_home,
        ), patch(
            "skillguard_v2.test_mesh.load_verified_installation_context",
            return_value=context,
        ) as load_context, patch(
            "skillguard_v2.test_mesh.compare_installation_projection_member",
            side_effect=[copy.deepcopy(comparison), copy.deepcopy(comparison)],
        ):
            binding = _load_current_installation_binding(
                self.repository, self.installation_root
            )
        load_context.assert_called_once()
        self.assertEqual(
            "skillguard.test_mesh_typed_domain_binding.current",
            binding["schema_version"],
        )
        self.assertEqual("active_installation", binding["evidence_domain"])
        self.assertRegex(binding["member_projection_hash"], r"^sha256:[0-9a-f]{64}$")

        head_path = self.installation_root / "HEAD.json"
        head = json.loads(head_path.read_text(encoding="utf-8"))
        head["unexpected"] = True
        unsigned = dict(head)
        unsigned.pop("head_hash")
        head["head_hash"] = canonical_hash(unsigned)
        head_path.write_text(json.dumps(head), encoding="utf-8")
        with patch(
            "skillguard_v2.test_mesh.resolve_codex_home_root",
            return_value=self.codex_home,
        ), self.assertRaisesRegex(
            ExecutionRecordError, "installation_receipt_verification_failed:ValueError"
        ):
            _load_current_installation_binding(
                self.repository, self.installation_root
            )

    def test_external_target_can_bind_exact_canonical_skillguard_root(self) -> None:
        snapshot = {
            "current_installed_smoke_hash": "1" * 64,
            "current_installed_smoke_command_fingerprint": "2" * 64,
            "current_installed_smoke_environment_fingerprint": "3" * 64,
        }
        context = SimpleNamespace(receipt={}, current_snapshot=snapshot)
        projection = {
            "identity_hash": "sha256:" + "d" * 64,
            "consumer_projection_hash": "sha256:" + "e" * 64,
        }
        comparison = {
            "status": "current",
            "canonical_installation_projection": projection,
            "installed_installation_projection": projection,
        }
        canonical_root = (
            self.workspace
            / "canonical-skillguard-repository"
            / ".agents"
            / "skills"
            / "skillguard"
        )
        with patch(
            "skillguard_v2.test_mesh.resolve_codex_home_root",
            return_value=self.codex_home,
        ), patch(
            "skillguard_v2.test_mesh.load_verified_installation_context",
            return_value=context,
        ) as load_context, patch(
            "skillguard_v2.test_mesh.compare_installation_projection_member",
            side_effect=[copy.deepcopy(comparison), copy.deepcopy(comparison)],
        ) as compare:
            binding = _load_current_installation_binding(
                self.repository,
                self.installation_root,
                canonical_skillguard_root=canonical_root,
            )
        self.assertEqual("active_installation", binding["evidence_domain"])
        self.assertEqual(
            canonical_root.resolve(),
            load_context.call_args.kwargs["canonical_skill_root"],
        )
        self.assertEqual(canonical_root.resolve(), compare.call_args_list[0].args[0])
        self.assertEqual(
            canonical_root.resolve().parent / "skillguard-global-router",
            compare.call_args_list[1].args[0],
        )

    def test_equivalent_reinstall_metadata_does_not_stale_parent_binding(self) -> None:
        snapshot = {
            "current_installed_smoke_hash": "1" * 64,
            "current_installed_smoke_command_fingerprint": "2" * 64,
            "current_installed_smoke_environment_fingerprint": "3" * 64,
        }
        first_context = SimpleNamespace(
            receipt={"transaction_id": "install-" + "a" * 32},
            current_snapshot={**snapshot, "transaction_id": "install-" + "a" * 32},
        )
        second_context = SimpleNamespace(
            receipt={"transaction_id": "install-" + "b" * 32},
            current_snapshot={**snapshot, "transaction_id": "install-" + "b" * 32},
        )
        projection = {
            "identity_hash": "sha256:" + "d" * 64,
            "consumer_projection_hash": "sha256:" + "e" * 64,
        }
        comparison = {
            "status": "current",
            "canonical_installation_projection": projection,
            "installed_installation_projection": projection,
        }
        with patch(
            "skillguard_v2.test_mesh.resolve_codex_home_root",
            return_value=self.codex_home,
        ), patch(
            "skillguard_v2.test_mesh.validate_verified_installation_context",
            side_effect=lambda context, **_kwargs: context,
        ), patch(
            "skillguard_v2.test_mesh.compare_installation_projection_member",
            side_effect=[
                copy.deepcopy(comparison),
                copy.deepcopy(comparison),
                copy.deepcopy(comparison),
                copy.deepcopy(comparison),
            ],
        ):
            first = _load_current_installation_binding(
                self.repository,
                self.installation_root,
                verified_installation_context=first_context,
            )
            second = _load_current_installation_binding(
                self.repository,
                self.installation_root,
                verified_installation_context=second_context,
            )
        self.assertEqual(first, second)
        self.assertNotIn("installation_transaction_id", first)
        self.assertNotIn("installation_receipt_hash", first)

    def test_global_prompt_loader_requires_stored_projection_but_ignores_outer_prompt_text(self) -> None:
        router_root = self.codex_home / ".skillguard" / "global-router"
        router_root.mkdir(parents=True, exist_ok=True)
        registry_hash = wire_hash({"registry": "fixture"})
        registry = {"registry_hash": registry_hash}
        content_declaration = {
            "consumer_id": "projection:global-router",
            "kind": "global_router",
            "impact_plan_schema_version": "skillguard.content_impact_plan.current",
            "impact_policy_id": "skillguard.content_impact_policy.current",
            "input_component_ids": ["component:router"],
        }
        content_projection = {
            **content_declaration,
            "projection_declaration_hash": wire_hash(content_declaration),
            "input_projection_hash": wire_hash(
                [{"component_id": "component:router", "component_hash": wire_hash({"router": 1})}]
            ),
        }
        content_projection["consumer_projection_hash"] = wire_hash(
            {
                "projection_declaration_hash": content_projection[
                    "projection_declaration_hash"
                ],
                "input_projection_hash": content_projection[
                    "input_projection_hash"
                ],
            }
        )
        managed_block = (
            "<!-- BEGIN MANAGED SKILLGUARD GLOBAL ROUTER -->\n"
            f"registry_hash: {registry_hash}\n"
            "<!-- END MANAGED SKILLGUARD GLOBAL ROUTER -->\n"
        )
        projection = build_prompt_projection(
            registry,
            registry_path=(
                ".codex/.skillguard/global-router/global_registry.json"
            ),
            managed_block=managed_block,
            template_content_hash=wire_hash({"template": 1}),
            content_projection=content_projection,
            generated_at="2026-07-13T00:00:00Z",
        )
        registry_path = router_root / "global_registry.json"
        projection_path = router_root / "global_prompt_projection.json"
        registry_path.write_text(json.dumps(registry), encoding="utf-8")
        projection_path.write_text(json.dumps(projection), encoding="utf-8")
        agents_path = self.codex_home / "AGENTS.md"
        agents_path.write_text("unmanaged before\n" + managed_block, encoding="utf-8")

        patches = (
            patch(
                "checker_engine.global_registry_integrity_failures",
                return_value=[],
            ),
            patch(
                "checker_engine.global_registry_current_route_failures",
                return_value=([], []),
            ),
            patch(
                "checker_engine.build_global_prompt_projection",
                return_value=copy.deepcopy(projection),
            ),
            patch(
                "checker_engine.check_global_prompt_text",
                return_value=([], []),
            ),
        )
        with patches[0], patches[1], patches[2], patches[3]:
            first = _load_global_prompt_currentness_binding(
                codex_home=self.codex_home
            )
            agents_path.write_text(
                "different unmanaged prose\n" + managed_block,
                encoding="utf-8",
            )
            second = _load_global_prompt_currentness_binding(
                codex_home=self.codex_home
            )
        self.assertEqual(first, second)
        self.assertEqual(
            {
                "path_token": "codex_home",
                "relative_path": (
                    ".skillguard/global-router/global_prompt_projection.json"
                ),
            },
            first["projection_ref"],
        )

        projection_path.unlink()
        with patches[0], patches[1], patches[2], patches[3], self.assertRaisesRegex(
            ExecutionRecordError, "global_prompt_currentness_input_missing"
        ):
            _load_global_prompt_currentness_binding(codex_home=self.codex_home)


if __name__ == "__main__":
    unittest.main()
