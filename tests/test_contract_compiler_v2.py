from __future__ import annotations

import copy
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / ".agents" / "skills" / "skillguard" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from skillguard_v2.contract_compiler import (  # noqa: E402
    CHECK_MANIFEST_FILE,
    COMPILED_CONTRACT_FILE,
    _content_role,
    _install_disposition,
    compile_skill_contract,
    canonical_hash,
    current_content_projection,
    path_fingerprint,
)
from skillguard_v2.contract_schema import BINDING_SOURCE_SCHEMA  # noqa: E402
from skillguard_v2 import flowguard_adapter  # noqa: E402
from skillguard_v2 import supervisor as supervisor_module  # noqa: E402
from skillguard_v2.flowguard_adapter import FlowGuardAdapterError, load_flowguard_model  # noqa: E402
from skillguard_v2.supervisor import (  # noqa: E402
    SupervisorError,
    _current_fingerprints,
    supervise_contract_run,
    validate_supervisor_packet,
)
from skillguard_v2.runtime_fingerprint import guard_runtime_fingerprint  # noqa: E402
from skillguard_v2.execution_records import filesystem_path  # noqa: E402
from skillguard_v2.installation import (  # noqa: E402
    _installation_member_relative_path,
    installation_projection_identity,
)


SELF_MODEL_PATH = ROOT / ".flowguard" / "development_process_flow" / "skillguard_executable_contract_model.py"


def load_self_model():
    spec = importlib.util.spec_from_file_location("skillguard_executable_contract_model_for_compiler", SELF_MODEL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load model: {SELF_MODEL_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def json_text(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


class ContractCompilerV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.self_model = load_self_model()
        cls.base_export = cls.self_model.export_contract_model()

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.skill = self.repo / ".agents" / "skills" / "fixture-skill"
        self.control = self.skill / ".skillguard"
        self.model_dir = self.repo / ".flowguard"
        self.control.mkdir(parents=True)
        self.model_dir.mkdir(parents=True)
        (self.skill / "SKILL.md").write_text(
            "---\nname: fixture-skill\ndescription: Fixture for SkillGuard V2 compiler tests.\n---\n# Fixture\n",
            encoding="utf-8",
        )
        self.export = copy.deepcopy(self.base_export)
        self.model_path = self.model_dir / "skill_contract_model.py"
        self._write_model(self.export)
        self.binding = self._binding_for(self.export)
        self.implementation = self.skill / "runtime.py"
        self.implementation.write_text("VALUE = 1\n", encoding="utf-8")
        self.binding["implementation_paths"] = [
            self.implementation.relative_to(self.repo).as_posix()
        ]
        self._write_binding(self.binding)

    def test_source_fingerprint_normalizes_text_line_endings_but_not_binary_bytes(self) -> None:
        left = self.repo / "lf"
        right = self.repo / "crlf"
        left.mkdir()
        right.mkdir()
        left.joinpath("source.py").write_bytes(b"VALUE = 1\nVALUE = 2\n")
        right.joinpath("source.py").write_bytes(b"VALUE = 1\r\nVALUE = 2\r\n")
        left.joinpath("asset.bin").write_bytes(b"\x00\n")
        right.joinpath("asset.bin").write_bytes(b"\x00\n")
        self.assertEqual(path_fingerprint(left), path_fingerprint(right))
        right.joinpath("asset.bin").write_bytes(b"\x00\r\n")
        self.assertNotEqual(path_fingerprint(left), path_fingerprint(right))

    def test_single_file_fingerprint_uses_shared_portable_policy(self) -> None:
        cache_file = self.repo / ".pytest_cache" / "state.json"
        cache_file.parent.mkdir(parents=True)
        cache_file.write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "generic_transient"):
            path_fingerprint(cache_file, member_root=self.repo)

    def test_repository_root_fixture_directory_is_source_only(self) -> None:
        role = _content_role("fixtures/contract/case.json")

        self.assertEqual("fixture_reference", role)
        self.assertEqual(
            "source_only",
            _install_disposition("fixtures/contract/case.json", ".", role),
        )

    def test_current_nested_skill_repository_layout_replays_installation_projection(self) -> None:
        nested_skill = self.repo / "skills" / "fixture-skill"
        nested_skill.parent.mkdir(parents=True)
        shutil.copytree(self.skill, nested_skill)
        self.skill = nested_skill
        self.control = self.skill / ".skillguard"
        self.implementation = self.skill / "runtime.py"
        self.binding["implementation_paths"] = [
            self.implementation.relative_to(self.repo).as_posix()
        ]
        self._write_binding(self.binding)

        result = compile_skill_contract(
            self.skill, repository_root=self.repo, write=True
        )

        self.assertTrue(result.ok, result.to_dict())
        identity = installation_projection_identity(self.skill)
        self.assertEqual("fixture-skill", identity["skill_id"])
        self.assertRegex(identity["identity_hash"], r"^sha256:[a-f0-9]{64}$")
        self.assertEqual(
            "skills/fixture-skill",
            result.check_manifest["content_impact_plan"]["member_root_path"],
        )
        self.assertEqual(
            "SKILL.md",
            _installation_member_relative_path(
                "skills/fixture-skill", "skills/fixture-skill/SKILL.md"
            ),
        )

    def test_current_skill_root_layout_rejects_a_path_outside_declared_member_root(self) -> None:
        with self.assertRaisesRegex(
            ValueError, "installation_projection_path_outside_member"
        ):
            _installation_member_relative_path(
                "skills/fixture-skill", "skills/other-skill/SKILL.md"
            )

    def test_repository_root_member_path_requires_no_layout_inference(self) -> None:
        self.assertEqual(
            "SKILL.md",
            _installation_member_relative_path(".", "SKILL.md"),
        )
        self.assertEqual(
            "scripts/check.py",
            _installation_member_relative_path(
                ".codex/skills/fixture-skill",
                ".codex/skills/fixture-skill/scripts/check.py",
            ),
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_model(self, payload: dict[str, object]) -> None:
        source = (
            "FLOWGUARD_MODEL_MARKER = 'flowguard-executable-model'\n"
            f"EXPORT = {payload!r}\n"
            "def export_contract_model():\n"
            "    return EXPORT\n"
        )
        self.model_path.write_text(source, encoding="utf-8")

    def _write_binding(self, payload: dict[str, object]) -> None:
        (self.control / "contract-source.json").write_text(json_text(payload), encoding="utf-8")

    def _binding_for(self, model: dict[str, object]) -> dict[str, object]:
        obligations = [str(row["obligation_id"]) for row in model["obligations"]]
        owner_by_step: dict[str, str] = {}
        for row in model["obligations"]:
            for step_id in row["owner_step_ids"]:
                owner_by_step.setdefault(str(step_id), str(row["obligation_id"]))
        default_obligation = obligations[0]
        step_bindings = []
        checks = []
        for step in model["steps"]:
            if step["terminal_kind"]:
                continue
            step_id = str(step["step_id"])
            check_id = f"check:{step_id.removeprefix('step:')}"
            obligation_id = owner_by_step.get(step_id, default_obligation)
            artifact_ids = ["artifact:compiled-contract"] if step_id == "step:compile-generated-contract" else []
            action = {"kind": step["action_kind"], "summary": f"execute {step_id}"}
            if step["action_kind"] == "judged":
                action["rubric_id"] = "rubric:fixture-judgment"
            step_bindings.append(
                {
                    "step_id": step_id,
                    "action": action,
                    "check_ids": [check_id],
                    "output_artifact_ids": artifact_ids,
                }
            )
            checks.append(
                {
                    "check_id": check_id,
                    "kind": "model_assertion",
                    "evidence_class": "hard",
                    "covers_obligation_ids": [obligation_id],
                    "timeout_seconds": 30,
                }
            )
        covered = {
            str(obligation_id)
            for check in checks
            for obligation_id in check["covers_obligation_ids"]
        }
        step_binding_index = {row["step_id"]: row for row in step_bindings}
        obligation_index = {str(row["obligation_id"]): row for row in model["obligations"]}
        for obligation_id in sorted(set(obligations) - covered):
            owner_step_id = str(obligation_index[obligation_id]["owner_step_ids"][0])
            check_id = f"check:obligation:{obligation_id.removeprefix('obligation:')}"
            checks.append(
                {
                    "check_id": check_id,
                    "kind": "model_assertion",
                    "evidence_class": "hard",
                    "covers_obligation_ids": [obligation_id],
                    "timeout_seconds": 30,
                }
            )
            step_binding_index[owner_step_id]["check_ids"].append(check_id)
        return {
            "schema_version": BINDING_SOURCE_SCHEMA,
            "skill_id": "fixture-skill",
            "model_id": model["model_id"],
            "model_path": ".flowguard/skill_contract_model.py",
            "confirmed": True,
            "step_bindings": step_bindings,
            "checks": checks,
            "artifacts": [
                {
                    "artifact_id": "artifact:compiled-contract",
                    "kind": "json",
                    "producer_step_id": "step:compile-generated-contract",
                    "path_template": ".skillguard/compiled-contract.json",
                    "required": True,
                    "validators": ["exists", "json", "contract_hash"],
                }
            ],
            "closure_profiles": [
                {"profile_id": "enforced", "required_obligation_ids": obligations}
            ],
            "judgment_rubrics": [
                {
                    "rubric_id": "rubric:fixture-judgment",
                    "version": "1",
                    "criteria": ["declared target-specific result is supported"],
                    "claim_boundary": "Compiler fixture judgment only.",
                }
            ],
            "claim_boundary": "Fixture compilation only; no target execution or release claim.",
        }

    def _attach_depth_profile(self) -> str:
        obligation = next(
            row
            for row in self.export["obligations"]
            if row["obligation_id"] == "obligation:depth-native-authority"
        )
        step_id = next(
            str(item)
            for item in obligation["owner_step_ids"]
            if any(row["step_id"] == item for row in self.binding["step_bindings"])
        )
        step = next(row for row in self.export["steps"] if row["step_id"] == step_id)
        route_id = str(step["route_id"])
        check_id = "check:target-declared-depth"
        self.binding["checks"].append(
            {
                "check_id": check_id,
                "kind": "model_assertion",
                "evidence_class": "hard",
                "covers_obligation_ids": [obligation["obligation_id"]],
                "execution_owner_id": "fixture-native-owner",
                "evidence_domain_id": "target:native",
                "depends_on_check_ids": [],
                "timeout_seconds": 30,
            }
        )
        next(
            row for row in self.binding["step_bindings"] if row["step_id"] == step_id
        )["check_ids"].append(check_id)
        self.binding["depth_profile"] = {
            "schema_version": "skillguard.depth_profile.v2",
            "profile_id": "fixture-declared-check-profile",
            "target_skill_id": "fixture-skill",
            "integration_mode": "native-integrated",
            "native_owner_id": "fixture-native-owner",
            "native_route_ids": [route_id],
            "native_check_ids": [check_id],
            "skillguard_adds_domain_route": False,
            "enforcement_level": "enforced",
            "required_closure_profiles": ["enforced"],
            "provider_runtime": {
                "provider_id": "fixture-provider",
                "required_runtime_contract_id": "fixture-runtime-current",
                "required_capability_ids": [
                    "declared-check-receipt-reconciliation.v1"
                ],
                "required_enrollment_status": "enrolled",
                "readiness_check_ids": [check_id],
            },
            "claim_boundary": "Exact target-declared checks only.",
        }
        return check_id

    def _target_input_roles(self, target: Path) -> dict[str, list[str]]:
        target.mkdir(parents=True, exist_ok=True)
        target.joinpath("input.json").write_text(
            json_text({"fixture": "target-input"}), encoding="utf-8"
        )
        return {"target_input": ["input.json"]}

    def test_depth_profile_compiles_as_target_neutral_declared_checks(self) -> None:
        check_id = self._attach_depth_profile()
        self._write_binding(self.binding)

        result = compile_skill_contract(self.skill, repository_root=self.repo, write=True)

        self.assertTrue(result.ok, result.to_dict())
        compiled_profile = result.compiled_contract["depth_profile"]
        self.assertEqual([check_id], compiled_profile["native_check_ids"])
        self.assertEqual("enforced", compiled_profile["enforcement_level"])
        for retired_field in (
            "purpose_contract_policy",
            "calibration",
            "dimensions",
            "coverage_universes",
            "mode",
        ):
            self.assertNotIn(retired_field, compiled_profile)

    def test_depth_profile_rejects_target_domain_fields(self) -> None:
        self._attach_depth_profile()
        self.binding["depth_profile"]["purpose_contract_policy"] = {
            "policy_id": "target-domain-policy"
        }
        self._write_binding(self.binding)

        result = compile_skill_contract(self.skill, repository_root=self.repo, write=False)

        self.assertIn(
            "depth_profile_unknown_field",
            {row.code for row in result.findings},
        )

    def test_depth_profile_requires_every_named_check_to_be_declared(self) -> None:
        self._attach_depth_profile()
        self.binding["depth_profile"]["native_check_ids"].append(
            "check:not-declared"
        )
        self._write_binding(self.binding)

        result = compile_skill_contract(self.skill, repository_root=self.repo, write=False)

        self.assertIn(
            "depth_native_check_unknown",
            {row.code for row in result.findings},
        )

    def test_depth_profile_requires_the_selected_check_dependency_closure(self) -> None:
        check_id = self._attach_depth_profile()
        dependency_id = next(
            row["check_id"]
            for row in self.binding["checks"]
            if row["check_id"] != check_id
        )
        selected = next(
            row for row in self.binding["checks"] if row["check_id"] == check_id
        )
        selected["depends_on_check_ids"] = [dependency_id]
        self._write_binding(self.binding)

        result = compile_skill_contract(
            self.skill,
            repository_root=self.repo,
            write=False,
        )

        self.assertIn(
            "depth_native_check_dependency_outside_inventory",
            {row.code for row in result.findings},
        )

    def test_depth_profile_blocks_unknown_provider_readiness_check(self) -> None:
        self._attach_depth_profile()
        self.binding["depth_profile"]["provider_runtime"]["readiness_check_ids"] = [
            "check:missing-readiness"
        ]
        self.binding["depth_profile"]["native_check_ids"].append(
            "check:missing-readiness"
        )
        self._write_binding(self.binding)

        result = compile_skill_contract(self.skill, repository_root=self.repo, write=True)

        self.assertIn(
            "depth_runtime_readiness_check_unknown",
            {row.code for row in result.findings},
        )

    def test_real_self_model_loads_through_versioned_adapter(self) -> None:
        snapshot = load_flowguard_model(SELF_MODEL_PATH, ROOT)
        self.assertEqual("skillguard.executable_contract_runtime.v2", snapshot.model_export["model_id"])
        self.assertEqual("1.0", snapshot.flowguard_schema_version)

    def test_model_authority_read_does_not_write_bytecode_into_target(self) -> None:
        cache = self.model_path.parent / "__pycache__"
        self.assertFalse(cache.exists())

        snapshot = load_flowguard_model(self.model_path, self.repo)

        self.assertEqual(self.export["model_id"], snapshot.model_export["model_id"])
        self.assertFalse(cache.exists())

    def test_installed_projection_runtime_is_loaded_without_recompilation(self) -> None:
        source_result = compile_skill_contract(
            self.skill,
            repository_root=self.repo,
            write=True,
        )
        self.assertTrue(source_result.ok, source_result.to_dict())
        fixture = self.control / "fixtures" / "source-only.json"
        fixture.parent.mkdir(parents=True)
        fixture.write_text("{}\n", encoding="utf-8")
        source_result = compile_skill_contract(
            self.skill,
            repository_root=self.repo,
            write=True,
        )
        self.assertTrue(source_result.ok, source_result.to_dict())

        codex_home = self.repo / "installed-home"
        installed = codex_home / "skills" / "fixture-skill"
        shutil.copytree(self.skill, installed)
        shutil.rmtree(installed / ".skillguard" / "fixtures")
        before_contract = (installed / ".skillguard" / COMPILED_CONTRACT_FILE).read_bytes()
        before_manifest = (installed / ".skillguard" / CHECK_MANIFEST_FILE).read_bytes()

        with mock.patch.dict(os.environ, {"CODEX_HOME": str(codex_home)}):
            with mock.patch.object(
                supervisor_module,
                "compile_skill_contract",
                side_effect=AssertionError("installed projections must not compile"),
            ):
                contract, manifest = supervisor_module._load_or_compile_runtime_pair(
                    installed,
                    installed,
                    None,
                    None,
                )

        assert source_result.compiled_contract is not None
        assert source_result.check_manifest is not None
        self.assertEqual(
            source_result.compiled_contract["contract_hash"],
            contract["contract_hash"],
        )
        self.assertEqual(
            source_result.check_manifest["manifest_hash"],
            manifest["manifest_hash"],
        )
        self.assertEqual(
            before_contract,
            (installed / ".skillguard" / COMPILED_CONTRACT_FILE).read_bytes(),
        )
        self.assertEqual(
            before_manifest,
            (installed / ".skillguard" / CHECK_MANIFEST_FILE).read_bytes(),
        )

    def test_missing_flowguard_toolchain_fails_with_stable_code(self) -> None:
        with mock.patch.object(flowguard_adapter, "flowguard", None):
            with self.assertRaises(FlowGuardAdapterError) as raised:
                load_flowguard_model(SELF_MODEL_PATH, ROOT)
        self.assertEqual({"flowguard_toolchain_missing"}, {row.code for row in raised.exception.findings})

    def test_generation_is_deterministic_and_check_mode_is_read_only(self) -> None:
        result = compile_skill_contract(self.skill, repository_root=self.repo, write=True)
        self.assertTrue(result.ok, result.to_dict())
        self.assertEqual(
            {".skillguard/compiled-contract.json", ".skillguard/check-manifest.json"},
            set(result.written_files),
        )
        first_contract = (self.control / COMPILED_CONTRACT_FILE).read_bytes()
        first_manifest = (self.control / CHECK_MANIFEST_FILE).read_bytes()
        second = compile_skill_contract(self.skill, repository_root=self.repo, write=True)
        self.assertTrue(second.ok, second.to_dict())
        self.assertFalse(second.written_files)
        checked = compile_skill_contract(self.skill, repository_root=self.repo, write=False)
        self.assertTrue(checked.ok, checked.to_dict())
        self.assertEqual(first_contract, (self.control / COMPILED_CONTRACT_FILE).read_bytes())
        self.assertEqual(first_manifest, (self.control / CHECK_MANIFEST_FILE).read_bytes())
        model_checks = [
            row for row in result.check_manifest["checks"] if row["kind"] == "model_assertion"
        ]
        self.assertTrue(model_checks)
        self.assertTrue(all(row["args"] == [".flowguard/skill_contract_model.py"] for row in model_checks))
        self.assertTrue(all(row["cwd_token"] == "repository_root" for row in model_checks))

    def test_content_impact_graph_is_current_component_scoped_and_wire_hashed(self) -> None:
        result = compile_skill_contract(self.skill, repository_root=self.repo, write=True)

        self.assertTrue(result.ok, result.to_dict())
        plan = result.check_manifest["content_impact_plan"]
        self.assertEqual("skillguard.content_impact_plan.current", plan["schema_version"])
        self.assertEqual("skillguard.content_impact_policy.current", plan["policy_id"])
        self.assertEqual(
            {"path_token": "owner_evidence_root", "relative_path": "check-executions"},
            plan["owner_receipt_root_ref"],
        )
        self.assertEqual(
            {
                "unmapped_paths": [],
                "ambiguous_role_paths": [],
                "duplicate_owner_ids": [],
                "owner_cycles": [],
                "invalid_dependency_edges": [],
                "dependency_parse_errors": [],
            },
            plan["health"],
        )
        for value in (
            plan["inventory_hash"],
            plan["impact_graph_hash"],
            *(row["component_hash"] for row in plan["components"]),
            *(row["owner_declaration_hash"] for row in plan["owners"]),
            *(row["owner_input_projection_hash"] for row in plan["owners"]),
            *(row["projection_declaration_hash"] for row in plan["projection_consumers"]),
            *(row["input_projection_hash"] for row in plan["projection_consumers"]),
            *(row["consumer_projection_hash"] for row in plan["projection_consumers"]),
        ):
            self.assertRegex(value, r"^sha256:[0-9a-f]{64}$")
        installation = current_content_projection(plan, "projection:installation")
        self.assertEqual("installation", installation["kind"])
        self.assertEqual(
            "skillguard.content_impact_plan.current",
            installation["impact_plan_schema_version"],
        )
        self.assertEqual(
            "skillguard.content_impact_policy.current",
            installation["impact_policy_id"],
        )

        stale_policy = copy.deepcopy(plan)
        stale_policy["policy_id"] = "skillguard.content_impact_policy.changed"
        with self.assertRaisesRegex(ValueError, "content_projection_hash_mismatch"):
            current_content_projection(stale_policy, "projection:installation")

    def test_portfolio_target_edge_is_explicit_and_component_scoped(self) -> None:
        runtime_path = self.implementation.relative_to(self.repo).as_posix()
        self.binding["portfolio_target_edges"] = [
            {
                "target_id": "fixture-skill",
                "input_selectors": [{"kind": "path", "path": runtime_path}],
            }
        ]
        self._write_binding(self.binding)

        result = compile_skill_contract(
            self.skill, repository_root=self.repo, write=True
        )

        self.assertTrue(result.ok, result.to_dict())
        plan = result.check_manifest["content_impact_plan"]
        self.assertEqual(1, len(plan["portfolio_target_edges"]))
        edge = plan["portfolio_target_edges"][0]
        self.assertEqual("fixture-skill", edge["target_id"])
        self.assertEqual([], edge["member_ids"])
        self.assertTrue(edge["input_component_ids"])
        for component_id in edge["input_component_ids"]:
            component = next(
                row
                for row in plan["components"]
                if row["component_id"] == component_id
            )
            self.assertIn(
                "portfolio-target:fixture-skill", component["consumer_ids"]
            )

        skill_component = next(
            row
            for row in plan["components"]
            if (self.skill / "SKILL.md").relative_to(self.repo).as_posix()
            in row["member_paths"]
        )
        self.assertNotIn(
            skill_component["component_id"], edge["input_component_ids"]
        )

    def test_consumer_projection_rejects_component_hash_tamper(self) -> None:
        result = compile_skill_contract(self.skill, repository_root=self.repo, write=True)
        self.assertTrue(result.ok, result.to_dict())
        plan = copy.deepcopy(result.check_manifest["content_impact_plan"])
        installation = current_content_projection(plan, "projection:installation")
        component_id = installation["input_component_ids"][0]
        component = next(
            row for row in plan["components"] if row["component_id"] == component_id
        )
        component["component_hash"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(ValueError, "content_projection_hash_mismatch"):
            current_content_projection(plan, "projection:installation")

    def test_complete_skill_inventory_keeps_tests_out_of_install_projection(self) -> None:
        tests_root = self.skill / "tests"
        tests_root.mkdir()
        test_path = tests_root / "test_runtime.py"
        test_path.write_text("def test_runtime(): assert True\n", encoding="utf-8")

        first = compile_skill_contract(
            self.skill, repository_root=self.repo, write=True
        )

        self.assertTrue(first.ok, first.to_dict())
        plan = first.compiled_contract["content_impact_plan"]
        rows = {row["path"]: row for row in plan["inventory"]}
        relative_test = test_path.relative_to(self.repo).as_posix()
        relative_skill = (self.skill / "SKILL.md").relative_to(self.repo).as_posix()
        self.assertEqual("test_dev", rows[relative_test]["role"])
        self.assertEqual("source_only", rows[relative_test]["install_disposition"])
        self.assertEqual("copy", rows[relative_skill]["install_disposition"])
        install = current_content_projection(plan, "projection:installation")
        install_members = {
            path
            for component in plan["components"]
            if component["component_id"] in install["input_component_ids"]
            for path in component["member_paths"]
        }
        self.assertNotIn(relative_test, install_members)
        first_install_hash = install["consumer_projection_hash"]
        first_installed_identity = installation_projection_identity(self.skill)

        test_path.write_text(
            "def test_runtime(): assert 1 == 1\n", encoding="utf-8"
        )
        second = compile_skill_contract(
            self.skill, repository_root=self.repo, write=True
        )

        self.assertTrue(second.ok, second.to_dict())
        second_install = current_content_projection(
            second.compiled_contract["content_impact_plan"],
            "projection:installation",
        )
        self.assertEqual(
            first_install_hash,
            second_install["consumer_projection_hash"],
        )
        self.assertEqual(
            first_installed_identity,
            installation_projection_identity(self.skill),
        )

    def test_directory_role_override_covers_future_fixture_descendants_without_install_staleness(self) -> None:
        examples_root = self.skill / "examples"
        nested_root = examples_root / "nested"
        nested_root.mkdir(parents=True)
        first_fixture = examples_root / "positive.json"
        second_fixture = nested_root / "negative.json"
        first_fixture.write_text('{"status": "pass"}\n', encoding="utf-8")
        second_fixture.write_text('{"status": "blocked"}\n', encoding="utf-8")
        relative_examples = examples_root.relative_to(self.repo).as_posix()
        self.binding["implementation_paths"].append(relative_examples)
        self.binding["content_role_overrides"] = [
            {
                "path": relative_examples,
                "role": "fixture_reference",
                "install_disposition": "source_only",
                "reason": "target-owned regression fixture subtree",
            }
        ]
        self._write_binding(self.binding)

        first = compile_skill_contract(self.skill, repository_root=self.repo, write=True)

        self.assertTrue(first.ok, first.to_dict())
        first_plan = first.compiled_contract["content_impact_plan"]
        first_rows = {row["path"]: row for row in first_plan["inventory"]}
        for fixture in (first_fixture, second_fixture):
            row = first_rows[fixture.relative_to(self.repo).as_posix()]
            self.assertEqual("fixture_reference", row["role"])
            self.assertEqual("source_only", row["install_disposition"])
            self.assertTrue(
                row["classification_rule_id"].startswith(
                    "reviewed_override:subtree:"
                )
            )
        first_install_hash = current_content_projection(
            first_plan, "projection:installation"
        )["consumer_projection_hash"]

        future_fixture = nested_root / "future.json"
        future_fixture.write_text('{"future": true}\n', encoding="utf-8")
        second = compile_skill_contract(self.skill, repository_root=self.repo, write=True)

        self.assertTrue(second.ok, second.to_dict())
        second_plan = second.compiled_contract["content_impact_plan"]
        future_row = next(
            row
            for row in second_plan["inventory"]
            if row["path"] == future_fixture.relative_to(self.repo).as_posix()
        )
        self.assertEqual("fixture_reference", future_row["role"])
        self.assertEqual("source_only", future_row["install_disposition"])
        self.assertEqual(
            first_install_hash,
            current_content_projection(second_plan, "projection:installation")[
                "consumer_projection_hash"
            ],
        )

    def test_overlapping_content_role_overrides_block_without_precedence_fallback(self) -> None:
        examples_root = self.skill / "examples"
        examples_root.mkdir()
        fixture_path = examples_root / "case.json"
        fixture_path.write_text("{}\n", encoding="utf-8")
        relative_examples = examples_root.relative_to(self.repo).as_posix()
        relative_fixture = fixture_path.relative_to(self.repo).as_posix()
        self.binding["implementation_paths"].append(relative_examples)
        self.binding["content_role_overrides"] = [
            {
                "path": relative_examples,
                "role": "fixture_reference",
                "install_disposition": "source_only",
                "reason": "fixture subtree",
            },
            {
                "path": relative_fixture,
                "role": "runtime_source",
                "install_disposition": "copy",
                "reason": "conflicting exact override",
            },
        ]
        self._write_binding(self.binding)

        result = compile_skill_contract(self.skill, repository_root=self.repo, write=True)

        self.assertFalse(result.ok)
        self.assertIn(
            "content_role_override_overlap",
            {finding.code for finding in result.findings},
        )

    def test_unmapped_source_only_file_blocks_before_execution_without_full_fallback(self) -> None:
        unowned = self.repo / "tests" / "test_unowned.py"
        unowned.parent.mkdir(exist_ok=True)
        unowned.write_text("def test_unowned():\n    assert True\n", encoding="utf-8")
        self.binding["implementation_paths"].append(
            unowned.relative_to(self.repo).as_posix()
        )
        self._write_binding(self.binding)

        result = compile_skill_contract(self.skill, repository_root=self.repo, write=True)

        self.assertFalse(result.ok)
        finding = next(
            row
            for row in result.findings
            if row.path == "$.content_impact_plan.health.unmapped_paths"
        )
        self.assertIn("tests/test_unowned.py", finding.message)
        self.assertNotIn("full", finding.message.casefold())

    def test_unknown_check_behavior_field_fails_closed(self) -> None:
        self.binding["checks"][0]["unregistered_behavior_toggle"] = True
        self._write_binding(self.binding)

        result = compile_skill_contract(self.skill, repository_root=self.repo, write=True)

        self.assertIn(
            "check_behavior_field_unknown", {row.code for row in result.findings}
        )

    def test_duplicate_commands_share_one_execution_owner_but_keep_check_projections(self) -> None:
        result = compile_skill_contract(self.skill, repository_root=self.repo, write=True)

        self.assertTrue(result.ok, result.to_dict())
        model_checks = [
            row
            for row in result.check_manifest["checks"]
            if row["kind"] == "model_assertion"
        ]
        self.assertGreater(len(model_checks), 1)
        self.assertEqual(1, len({row["execution_owner_id"] for row in model_checks}))
        self.assertEqual(
            len(model_checks),
            len({row["projection_declaration_hash"] for row in model_checks}),
        )

    def test_projection_only_coverage_change_preserves_owner_identity(self) -> None:
        first = compile_skill_contract(self.skill, repository_root=self.repo, write=True)
        self.assertTrue(first.ok, first.to_dict())
        check = self.binding["checks"][0]
        existing = set(check["covers_obligation_ids"])
        additional = next(
            row["obligation_id"]
            for row in self.export["obligations"]
            if row["obligation_id"] not in existing
        )
        check["covers_obligation_ids"].append(additional)
        self._write_binding(self.binding)

        second = compile_skill_contract(self.skill, repository_root=self.repo, write=True)

        self.assertTrue(second.ok, second.to_dict())
        first_check = next(
            row
            for row in first.check_manifest["checks"]
            if row["check_id"] == check["check_id"]
        )
        second_check = next(
            row
            for row in second.check_manifest["checks"]
            if row["check_id"] == check["check_id"]
        )
        self.assertEqual(
            first_check["owner_declaration_hash"],
            second_check["owner_declaration_hash"],
        )
        self.assertEqual(
            first_check["owner_input_projection_hash"],
            second_check["owner_input_projection_hash"],
        )
        self.assertNotEqual(
            first_check["projection_declaration_hash"],
            second_check["projection_declaration_hash"],
        )

    def test_owner_dependency_cycle_is_a_pre_execution_blocker(self) -> None:
        left, right = self.binding["checks"][:2]
        left["execution_owner_id"] = "owner:left"
        right["execution_owner_id"] = "owner:right"
        left["depends_on_check_ids"] = [right["check_id"]]
        right["depends_on_check_ids"] = [left["check_id"]]
        self._write_binding(self.binding)

        result = compile_skill_contract(self.skill, repository_root=self.repo, write=True)

        self.assertFalse(result.ok)
        self.assertTrue(
            any(
                row.path == "$.content_impact_plan.health.owner_cycles"
                for row in result.findings
            ),
            result.to_dict(),
        )

    def test_compiled_obligations_bind_exact_checks_and_primary_evidence_classes(self) -> None:
        result = compile_skill_contract(self.skill, repository_root=self.repo, write=True)
        self.assertTrue(result.ok, result.to_dict())
        contract = result.compiled_contract
        obligations = {row["obligation_id"]: row for row in contract["obligations"]}
        check_index = {row["check_id"]: row for row in self.binding["checks"]}
        for obligation_id, obligation in obligations.items():
            expected_checks = sorted(
                check_id
                for check_id, check in check_index.items()
                if obligation_id in check["covers_obligation_ids"]
            )
            self.assertEqual(expected_checks, obligation["required_check_ids"])
            self.assertTrue(obligation["evidence_classes"])
        judged_step = next(
            row
            for row in contract["steps"]
            if row["step_id"] == "step:reconcile-declared-check-results"
        )
        judged_obligation = next(
            row
            for row in contract["obligations"]
            if judged_step["step_id"] in row["owner_step_ids"]
        )
        self.assertIn("hard", judged_obligation["evidence_classes"])

    def test_judged_step_with_unknown_declared_rubric_is_blocked(self) -> None:
        step = self.binding["step_bindings"][0]
        step["action"] = {
            "kind": "judged",
            "rubric_id": "rubric:missing",
            "summary": "fixture judged step",
        }
        self.binding["judgment_rubrics"] = []
        self._write_binding(self.binding)
        result = compile_skill_contract(self.skill, repository_root=self.repo, write=True)
        self.assertIn("judged_step_rubric_unknown", {row.code for row in result.findings})

    def test_generic_supervisor_claims_executes_closes_and_replays_selected_route(self) -> None:
        static_obligation = "obligation:static-audit"
        for profile in self.binding["closure_profiles"]:
            profile["required_obligation_ids"] = [static_obligation]
        self._write_binding(self.binding)
        target = self.repo / "target"
        report = supervise_contract_run(
            self.skill,
            target,
            self.repo,
            {
                "request": {
                    "route_ids": ["route:static-audit"],
                    "request": "execute the static audit route",
                    "claim_scope": "enforced",
                    "write_targets": ["out"],
                },
                "steps": {},
                "profiles": ["enforced"],
            },
        )
        self.assertEqual("passed", report["status"])
        self.assertEqual(["route:static-audit"], report["route_ids"])
        self.assertEqual(3, len(report["executed_steps"]))
        self.assertTrue(report["closures"][0]["verification"]["ok"])

    @unittest.skipUnless(os.name == "nt", "Windows extended-length path regression")
    def test_generic_supervisor_closes_with_long_runtime_authorities(self) -> None:
        static_obligation = "obligation:static-audit"
        for profile in self.binding["closure_profiles"]:
            profile["required_obligation_ids"] = [static_obligation]
        self._write_binding(self.binding)
        target = self.repo / "long-runtime-target"
        runtime_root = self.repo / "long-runtime-authorities"
        long_parent = runtime_root
        representative_receipt = (
            long_parent
            / "state"
            / ".skillguard"
            / "runs"
            / ("run-" + ("a" * 20))
            / "receipts"
            / ("receipt-" + ("a" * 24) + ".json")
        )
        while len(str(representative_receipt)) <= 270:
            long_parent /= "segment-abcdefghij"
            representative_receipt = (
                long_parent
                / "state"
                / ".skillguard"
                / "runs"
                / ("run-" + ("a" * 20))
                / "receipts"
                / ("receipt-" + ("a" * 24) + ".json")
            )
        run_state_root = long_parent / "state"
        owner_evidence_root = long_parent / "owner-evidence"
        run_state_root.mkdir(parents=True)
        owner_evidence_root.mkdir(parents=True)
        try:
            report = supervise_contract_run(
                self.skill,
                target,
                self.repo,
                {
                    "request": {
                        "route_ids": ["route:static-audit"],
                        "request": "execute the static audit route at long paths",
                        "claim_scope": "enforced",
                        "write_targets": ["out"],
                    },
                    "steps": {},
                    "profiles": ["enforced"],
                },
                run_state_root=run_state_root,
                owner_evidence_root=owner_evidence_root,
            )
            self.assertEqual("passed", report["status"])
            self.assertTrue(report["closures"][0]["verification"]["ok"])
        finally:
            shutil.rmtree(filesystem_path(runtime_root))

    def test_two_stage_supervisor_reuses_exact_depth_receipt_without_rerunning_checks(self) -> None:
        self._attach_depth_profile()
        static_obligation = "obligation:static-audit"
        for profile in self.binding["closure_profiles"]:
            profile["required_obligation_ids"] = [static_obligation]
        self._write_binding(self.binding)
        target = self.repo / "two-stage-target"
        request = {
            "route_ids": ["route:static-audit"],
            "request": "execute then close the same staged run",
            "claim_scope": "enforced",
            "write_targets": ["out"],
            "target_input_roles": self._target_input_roles(target),
        }
        exact_depth = {
            "receipt_id": "depth-" + "a" * 24,
            "receipt_hash": "B" * 64,
            "status": "EXECUTION_DEPTH_PASS",
        }
        execution_counter = 0

        def fake_check(check, **_kwargs):
            nonlocal execution_counter
            execution_counter += 1
            check_id = str(check["check_id"])
            record = {
                "status": "passed",
                "executed": True,
                "check_id": check_id,
                "check_record_id": f"check-record-{execution_counter}",
                "record_hash": canonical_hash(
                    {"check_id": check_id, "sequence": execution_counter}
                ),
                "proof_fingerprint": canonical_hash(
                    {"proof": check_id, "sequence": execution_counter}
                ),
                "check_manifest_hash": "C" * 64,
                "check_declarations_hash": "D" * 64,
                "declared_check_hash": canonical_hash(dict(check)),
                "result": {
                    "exit_code": 0,
                    "stdout_content_hash": "sha256:" + "e" * 64,
                    "stderr_content_hash": "sha256:" + "f" * 64,
                    "execution_environment_fingerprint": "1" * 64,
                },
            }
            return {
                "disposition": "executed_terminal_success",
                "record": record,
                "execution_receipt": {
                    "receipt_id": f"execution-receipt-{execution_counter}"
                },
            }

        evaluation = mock.Mock(status="closed")
        evaluation.to_dict.return_value = {"status": "closed"}
        closure = {
            "closure_receipt_id": "closure-two-stage",
            "closure_hash": "2" * 64,
        }
        installation_context = mock.sentinel.installation_context
        with mock.patch.object(
            supervisor_module, "get_or_execute_check", side_effect=fake_check
        ) as check_execution, mock.patch.object(
            supervisor_module,
            "hard_evidence_from_check",
            side_effect=lambda record: {
                "proof_kind": "two_stage_test_stub",
                "proof_fingerprint": str(record["proof_fingerprint"]),
                "check_id": str(record["check_id"]),
            },
        ), mock.patch.object(
            supervisor_module,
            "issue_target_execution_receipt",
            return_value=exact_depth,
        ) as issue_depth, mock.patch.object(
            supervisor_module,
            "close_run",
            return_value=(evaluation, closure),
        ) as close_execution, mock.patch.object(
            supervisor_module,
            "verify_closure",
            return_value={"ok": True},
        ) as closure_verification, mock.patch.object(
            supervisor_module,
            "load_scheduled_production_installation_context",
            return_value=installation_context,
        ) as load_installation_context, mock.patch.object(
            supervisor_module,
            "validate_verified_installation_context",
            return_value=installation_context,
        ), mock.patch.object(
            supervisor_module,
            "verify_scheduled_production_installation_identity",
            return_value={"receipt": {"status": "current_installed_parity"}},
        ):
            staged = supervise_contract_run(
                self.skill,
                target,
                self.repo,
                {
                    "supervision_mode": "stage_depth",
                    "request": request,
                    "steps": {},
                    "profiles": [],
                },
                verified_installation_context=installation_context,
            )
            stage_check_count = check_execution.call_count
            check_execution.reset_mock()
            closed = supervise_contract_run(
                self.skill,
                target,
                self.repo,
                {
                    "supervision_mode": "close",
                    "request": request,
                    "steps": {},
                    "profiles": ["enforced"],
                },
                verified_installation_context=installation_context,
            )
        self.assertEqual("staged", staged["status"])
        self.assertEqual("stage_depth", staged["supervision_mode"])
        self.assertFalse(staged["closures"])
        self.assertGreater(stage_check_count, 0)
        self.assertTrue(staged["executed_steps"])
        staged_depth = staged["target_execution_depth_receipt"]
        self.assertEqual(0, check_execution.call_count)
        self.assertEqual("passed", closed["status"])
        self.assertEqual("close", closed["supervision_mode"])
        closed_depth = closed["target_execution_depth_receipt"]
        self.assertEqual(staged["run_id"], closed["run_id"])
        self.assertEqual(staged_depth["receipt_id"], closed_depth["receipt_id"])
        self.assertEqual(
            staged_depth["receipt_hash"], closed_depth["receipt_hash"]
        )
        self.assertEqual(0, load_installation_context.call_count)
        self.assertTrue(
            all(
                call.kwargs["verified_installation_context"]
                is installation_context
                for call in issue_depth.call_args_list
            )
        )
        self.assertIs(
            installation_context,
            close_execution.call_args.kwargs["verified_installation_context"],
        )
        self.assertIs(
            installation_context,
            closure_verification.call_args.kwargs[
                "verified_installation_context"
            ],
        )

    def test_supervisor_does_not_load_installation_context_for_empty_non_production_schedule(self) -> None:
        self._attach_depth_profile()
        self._write_binding(self.binding)
        target = self.repo / "non-production-empty-schedule-target"
        request = {
            "route_ids": ["route:static-audit"],
            "request": "validate ordinary capability depth",
            "claim_scope": "enforced",
            "write_targets": ["out"],
            "target_input_roles": self._target_input_roles(target),
        }
        execution_counter = 0

        def fake_check(check, **_kwargs):
            nonlocal execution_counter
            execution_counter += 1
            check_id = str(check["check_id"])
            record = {
                "status": "passed",
                "executed": True,
                "check_id": check_id,
                "check_record_id": f"check-record-{execution_counter}",
                "record_hash": canonical_hash(
                    {"check_id": check_id, "sequence": execution_counter}
                ),
                "proof_fingerprint": canonical_hash(
                    {"proof": check_id, "sequence": execution_counter}
                ),
                "check_manifest_hash": "C" * 64,
                "check_declarations_hash": "D" * 64,
                "declared_check_hash": canonical_hash(dict(check)),
                "result": {
                    "exit_code": 0,
                    "stdout_content_hash": "sha256:" + "e" * 64,
                    "stderr_content_hash": "sha256:" + "f" * 64,
                    "execution_environment_fingerprint": "1" * 64,
                },
            }
            return {
                "disposition": "executed_terminal_success",
                "record": record,
                "execution_receipt": {
                    "receipt_id": f"execution-receipt-{execution_counter}"
                },
            }

        with mock.patch.object(
            supervisor_module, "get_or_execute_check", side_effect=fake_check
        ), mock.patch.object(
            supervisor_module,
            "hard_evidence_from_check",
            side_effect=lambda record: {
                "proof_kind": "empty_schedule_test_stub",
                "proof_fingerprint": str(record["proof_fingerprint"]),
                "check_id": str(record["check_id"]),
            },
        ), mock.patch.object(
            supervisor_module,
            "issue_target_execution_receipt",
            return_value={
                "receipt_id": "depth-" + "a" * 24,
                "receipt_hash": "B" * 64,
                "status": "EXECUTION_DEPTH_PASS",
            },
        ), mock.patch.object(
            supervisor_module,
            "load_scheduled_production_installation_context",
        ) as load_installation_context:
            staged = supervise_contract_run(
                self.skill,
                target,
                self.repo,
                {
                    "supervision_mode": "stage_depth",
                    "request": request,
                    "steps": {},
                    "profiles": [],
                },
            )

        self.assertEqual("staged", staged["status"])
        self.assertEqual(0, load_installation_context.call_count)

        with mock.patch.object(
            supervisor_module, "get_or_execute_check", side_effect=fake_check
        ), mock.patch.object(
            supervisor_module,
            "hard_evidence_from_check",
            side_effect=lambda record: {
                "proof_kind": "nonempty_schedule_test_stub",
                "proof_fingerprint": str(record["proof_fingerprint"]),
                "check_id": str(record["check_id"]),
            },
        ), mock.patch.object(
            supervisor_module,
            "issue_target_execution_receipt",
        ) as issue_depth, mock.patch.object(
            supervisor_module,
            "load_scheduled_production_installation_context",
        ) as bad_load_installation_context:
            with self.assertRaisesRegex(
                SupervisorError, "non_production_schedule_identity_forbidden"
            ):
                nonempty_target = self.repo / "non-production-nonempty-schedule-target"
                nonempty_request = {
                    **request,
                    "target_input_roles": self._target_input_roles(
                        nonempty_target
                    ),
                }
                supervise_contract_run(
                    self.skill,
                    nonempty_target,
                    self.repo,
                    {
                        "supervision_mode": "stage_depth",
                        "request": nonempty_request,
                        "steps": {},
                        "profiles": [],
                        "execution_depth": {
                            "evidence_domain": "capability_validation",
                            "scheduled_production_identity": {
                                "unexpected": "cross-domain-identity"
                            },
                        },
                    },
                )

        self.assertEqual(0, bad_load_installation_context.call_count)
        self.assertEqual(0, issue_depth.call_count)

    def test_guard_runtime_change_invalidates_external_run_fingerprint(self) -> None:
        runtime_root = self.repo / "guard-runtime"
        runtime_root.mkdir()
        runtime_file = runtime_root / "engine.py"
        runtime_file.write_text("VALUE = 1\n", encoding="utf-8")
        before = guard_runtime_fingerprint(runtime_root)
        runtime_file.write_text("VALUE = 2\n", encoding="utf-8")
        after = guard_runtime_fingerprint(runtime_root)
        self.assertNotEqual(before["source_hash"], after["source_hash"])

        result = compile_skill_contract(self.skill, repository_root=self.repo, write=True)
        self.assertTrue(result.ok, result.to_dict())
        fingerprints = _current_fingerprints(result.compiled_contract, {"request": "fixture"})
        self.assertIn("guard_runtime", fingerprints)
        self.assertTrue(fingerprints["guard_runtime"]["raw"])

    def test_supervisor_rejects_unknown_packet_fields_at_every_declared_boundary(self) -> None:
        base_request = {"route_ids": ["route:static-audit"], "claim_scope": "enforced"}
        cases = (
            {"request": base_request, "steps": {}, "unknown_top": True},
            {"request": {**base_request, "cliam_scope": "enforced"}, "steps": {}},
            {"request": base_request, "steps": {"step:x": {"judgemnt": {}}}},
            {"request": base_request, "steps": {"step:x": {"judgment": {"rubric_id": "r", "conclsuion": "x"}}}},
            {"request": base_request, "steps": {"step:x": {"witness": {"target_id": "t", "executer_id": "e"}}}},
            {"request": base_request, "steps": {"step:x": {"skip": {"reason": "x", "verifer_step_id": "s"}}}},
            {
                "request": base_request,
                "steps": {
                    "step:x": {
                        "artifact_witnesses": {
                            "artifact:x": {"target_id": "t", "surfaceid": "s"}
                        }
                    }
                },
            },
        )
        for packet in cases:
            with self.subTest(packet=packet):
                with self.assertRaises(SupervisorError) as caught:
                    validate_supervisor_packet(packet)
                self.assertEqual("unconsumed_packet_field", caught.exception.code)

    def test_supervisor_rejects_packet_for_unselected_or_hard_only_step(self) -> None:
        result = compile_skill_contract(self.skill, repository_root=self.repo, write=True)
        self.assertTrue(result.ok, result.to_dict())
        contract = result.compiled_contract
        with self.assertRaises(SupervisorError) as unselected:
            validate_supervisor_packet(
                {
                    "request": {"route_ids": ["route:static-audit"], "claim_scope": "enforced"},
                    "steps": {
                        "step:load-model-export": {
                            "witness": {
                                "witness_kind": "tool",
                                "target_id": "compiler",
                                "executor_id": "test",
                                "input": {},
                                "output": {},
                                "limitations": [],
                            }
                        }
                    },
                },
                contract=contract,
                route_ids=("route:static-audit",),
            )
        self.assertEqual("unconsumed_step_packet", unselected.exception.code)

        with self.assertRaises(SupervisorError) as hard_only:
            validate_supervisor_packet(
                {
                    "request": {"route_ids": ["route:static-audit"], "claim_scope": "enforced"},
                    "steps": {
                        "step:inventory-static-surface": {
                            "witness": {
                                "witness_kind": "tool",
                                "target_id": "inventory",
                                "executor_id": "test",
                                "input": {},
                                "output": {},
                                "limitations": [],
                            }
                        }
                    },
                },
                contract=contract,
                route_ids=("route:static-audit",),
            )
        self.assertEqual("unconsumed_packet_field", hard_only.exception.code)

    def test_check_mode_reports_missing_without_writing(self) -> None:
        result = compile_skill_contract(self.skill, repository_root=self.repo, write=False)
        self.assertFalse(result.ok)
        self.assertEqual({"generated_file_missing"}, {row.code for row in result.findings})
        self.assertFalse((self.control / COMPILED_CONTRACT_FILE).exists())
        self.assertFalse((self.control / CHECK_MANIFEST_FILE).exists())

    def test_entrypoint_change_invalidates_generated_outputs(self) -> None:
        self.assertTrue(compile_skill_contract(self.skill, repository_root=self.repo, write=True).ok)
        (self.skill / "SKILL.md").write_text("# changed boundary\n", encoding="utf-8")
        result = compile_skill_contract(self.skill, repository_root=self.repo, write=False)
        self.assertEqual({"stale_generated_contract"}, {row.code for row in result.findings})

    def test_declared_implementation_change_invalidates_generated_outputs(self) -> None:
        self.assertTrue(compile_skill_contract(self.skill, repository_root=self.repo, write=True).ok)
        self.implementation.write_text("VALUE = 2\n", encoding="utf-8")
        result = compile_skill_contract(self.skill, repository_root=self.repo, write=False)
        self.assertEqual({"stale_generated_contract"}, {row.code for row in result.findings})

    def test_task_checkbox_progress_does_not_invalidate_generated_outputs(self) -> None:
        tasks = self.implementation.with_name("tasks.md")
        tasks.write_text(
            "- [ ] Implement the current behavior.\n"
            "  - [ ] Preserve nested progress.\n",
            encoding="utf-8",
        )
        self.binding["implementation_paths"] = [
            tasks.relative_to(self.repo).as_posix()
        ]
        self._write_binding(self.binding)
        self.assertTrue(
            compile_skill_contract(
                self.skill, repository_root=self.repo, write=True
            ).ok
        )

        tasks.write_text(
            "- [x] Implement the current behavior.\n"
            "  - [X] Preserve nested progress.\n",
            encoding="utf-8",
        )
        checkbox_only = compile_skill_contract(
            self.skill, repository_root=self.repo, write=False
        )
        self.assertTrue(checkbox_only.ok, checkbox_only.to_dict())

        tasks.write_text(
            "- [x] Implement changed behavior.\n"
            "  - [X] Preserve nested progress.\n",
            encoding="utf-8",
        )
        changed_text = compile_skill_contract(
            self.skill, repository_root=self.repo, write=False
        )
        self.assertEqual(
            {"stale_generated_contract"},
            {row.code for row in changed_text.findings},
        )

    def test_task_checkbox_example_inside_fence_remains_authoritative(self) -> None:
        tasks = self.implementation.with_name("tasks.md")
        tasks.write_text(
            "```markdown\n- [ ] Example, not progress.\n```\n",
            encoding="utf-8",
        )
        self.binding["implementation_paths"] = [
            tasks.relative_to(self.repo).as_posix()
        ]
        self._write_binding(self.binding)
        self.assertTrue(
            compile_skill_contract(
                self.skill, repository_root=self.repo, write=True
            ).ok
        )

        tasks.write_text(
            "```markdown\n- [x] Example, not progress.\n```\n",
            encoding="utf-8",
        )
        result = compile_skill_contract(
            self.skill, repository_root=self.repo, write=False
        )
        self.assertEqual(
            {"stale_generated_contract"},
            {row.code for row in result.findings},
        )

    def test_transient_runtime_cache_does_not_invalidate_implementation_fingerprint(self) -> None:
        runtime_dir = self.skill / "runtime"
        runtime_dir.mkdir()
        (runtime_dir / "engine.py").write_text("VALUE = 1\n", encoding="utf-8")
        self.binding["implementation_paths"] = [runtime_dir.relative_to(self.repo).as_posix()]
        self._write_binding(self.binding)
        self.assertTrue(compile_skill_contract(self.skill, repository_root=self.repo, write=True).ok)
        cache = runtime_dir / "__pycache__"
        cache.mkdir()
        (cache / "engine.cpython-312.pyc").write_bytes(b"transient bytecode")
        control = runtime_dir / ".skillguard"
        control.mkdir()
        (control / "compiled-contract.json").write_text("{}\n", encoding="utf-8")
        result = compile_skill_contract(self.skill, repository_root=self.repo, write=False)
        self.assertTrue(result.ok, result.to_dict())

    def test_unsupported_flowguard_schema_fails_closed(self) -> None:
        broken = copy.deepcopy(self.export)
        broken["flowguard_schema_version"] = "9.9"
        self._write_model(broken)
        result = compile_skill_contract(self.skill, repository_root=self.repo, write=True)
        self.assertIn("unsupported_flowguard_schema", {row.code for row in result.findings})

    def test_broad_all_check_binding_is_rejected(self) -> None:
        obligations = [row["obligation_id"] for row in self.export["obligations"]]
        self.binding["checks"][0]["covers_obligation_ids"] = obligations
        self._write_binding(self.binding)
        result = compile_skill_contract(self.skill, repository_root=self.repo, write=True)
        self.assertIn("broad_all_check_binding", {row.code for row in result.findings})

    def test_dangling_handoff_and_unbounded_cycle_are_rejected(self) -> None:
        broken = copy.deepcopy(self.export)
        broken["routes"][0]["handoffs"] = [
            {
                "target_kind": "internal_route",
                "target_id": "route:missing",
                "condition": "always",
                "claim_scope": "fixture",
            }
        ]
        next(row for row in broken["routes"] if row["route_id"] == "route:supervise-run").pop("loop_policy")
        self._write_model(broken)
        result = compile_skill_contract(self.skill, repository_root=self.repo, write=True)
        codes = {row.code for row in result.findings}
        self.assertIn("dangling_handoff", codes)
        self.assertIn("unbounded_route_cycle", codes)

    def test_orphan_check_and_artifact_are_rejected(self) -> None:
        self.binding["checks"].append(
            {
                "check_id": "check:orphan",
                "kind": "model_assertion",
                "evidence_class": "hard",
                "covers_obligation_ids": [self.export["obligations"][0]["obligation_id"]],
            }
        )
        self.binding["artifacts"].append(
            {
                "artifact_id": "artifact:orphan",
                "kind": "file",
                "producer_step_id": "step:claim-run",
                "validators": ["exists"],
            }
        )
        self._write_binding(self.binding)
        result = compile_skill_contract(self.skill, repository_root=self.repo, write=True)
        codes = {row.code for row in result.findings}
        self.assertIn("orphan_check", codes)
        self.assertIn("orphan_artifact", codes)

    def test_additional_closure_profile_is_rejected(self) -> None:
        self.binding["closure_profiles"].append(
            {
                "profile_id": "optional",
                "required_obligation_ids": [
                    self.export["obligations"][0]["obligation_id"]
                ],
            }
        )
        self._write_binding(self.binding)
        result = compile_skill_contract(self.skill, repository_root=self.repo, write=True)
        codes = {row.code for row in result.findings}
        self.assertTrue(
            {"closure_profiles_incomplete", "closure_profile_unknown"} & codes,
            codes,
        )

    def test_real_compile_rejects_conditional_model_without_branch_contract(self) -> None:
        self.export["obligations"][0]["conditional"] = True
        self._write_model(self.export)
        result = compile_skill_contract(
            self.skill, repository_root=self.repo, write=False
        )
        codes = {row.code for row in result.findings}
        self.assertIn("route_branch_closure_opt_in_missing", codes)
        self.assertIn("conditional_obligation_branch_contract_missing", codes)

    def test_real_compile_rejects_non_boolean_conditional_flag(self) -> None:
        self.export["obligations"][0]["conditional"] = "true"
        self._write_model(self.export)
        result = compile_skill_contract(
            self.skill, repository_root=self.repo, write=False
        )
        self.assertIn(
            "obligation_conditional_flag_invalid",
            {row.code for row in result.findings},
        )

    def test_real_compile_rejects_branch_rows_without_explicit_opt_in(self) -> None:
        obligation_id = str(self.export["obligations"][0]["obligation_id"])
        route_id = str(self.export["routes"][0]["route_id"])
        for profile in self.binding["closure_profiles"]:
            profile["route_branch_requirements"] = [
                {
                    "native_route_id": route_id,
                    "branch_ids": ["conditional-path"],
                    "required_obligation_ids": [obligation_id],
                    "applicability_rules": [],
                }
            ]
        self._write_binding(self.binding)
        result = compile_skill_contract(
            self.skill, repository_root=self.repo, write=False
        )
        self.assertIn(
            "route_branch_closure_opt_in_missing",
            {row.code for row in result.findings},
        )

    def test_current_runtime_json_schemas_are_parseable_without_former_pairs(self) -> None:
        schema_root = ROOT / ".agents" / "skills" / "skillguard" / "assets" / "schemas"
        paths = sorted(schema_root.glob("*_v[0-9].schema.json"))
        required_names = {
            "skillguard_compiled_contract_v2.schema.json",
            "skillguard_contract_source_v2.schema.json",
            "skillguard_depth_profile_v2.schema.json",
            "skillguard_guard_change_v2.schema.json",
            "skillguard_native_terminal_receipt_v1.schema.json",
            "skillguard_obligation_applicability_receipt_v1.schema.json",
            "skillguard_project_adoption_v1.schema.json",
            "skillguard_target_execution_receipt_v2.schema.json",
        }
        self.assertTrue(required_names.issubset({path.name for path in paths}))
        former_names = {
            "skillguard_depth_calibration_record_v1.schema.json",
            "skillguard_depth_profile_v1.schema.json",
            "skillguard_guard_change_v1.schema.json",
            "skillguard_native_depth_calibration_evidence_v1.schema.json",
            "skillguard_native_depth_calibration_observation_v1.schema.json",
            "skillguard_native_depth_evidence_v1.schema.json",
            "skillguard_purpose_contract_identity_v1.schema.json",
            "skillguard_portfolio_job_evidence_record_v1.schema.json",
            "skillguard_portfolio_registry_v1.schema.json",
            "skillguard_target_execution_receipt_v1.schema.json",
        }
        self.assertTrue(former_names.isdisjoint({path.name for path in paths}))
        schema_ids = set()
        for path in paths:
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual("object", payload["type"], path.name)
            self.assertTrue(payload["required"], path.name)
            schema_id = payload.get("$id")
            if schema_id:
                self.assertNotIn(schema_id, schema_ids, path.name)
                schema_ids.add(schema_id)


if __name__ == "__main__":
    unittest.main()
