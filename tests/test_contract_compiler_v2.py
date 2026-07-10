from __future__ import annotations

import copy
import importlib.util
import json
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
    compile_skill_contract,
    migrate_v1_binding_candidate,
)
from skillguard_v2.contract_schema import BINDING_SOURCE_SCHEMA  # noqa: E402
from skillguard_v2 import flowguard_adapter  # noqa: E402
from skillguard_v2.flowguard_adapter import FlowGuardAdapterError, load_flowguard_model  # noqa: E402
from skillguard_v2.supervisor import (  # noqa: E402
    SupervisorError,
    _current_fingerprints,
    supervise_contract_run,
    validate_supervisor_packet,
)
from skillguard_v2.runtime_fingerprint import guard_runtime_fingerprint  # noqa: E402


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
        requirements = {
            "routine": obligations[:3],
            "functional": obligations[:8],
            "release": obligations,
            "highest_quality": obligations,
        }
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
                {"profile_id": profile, "required_obligation_ids": requirements[profile]}
                for profile in ("routine", "functional", "release", "highest_quality")
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

    def test_real_self_model_loads_through_versioned_adapter(self) -> None:
        snapshot = load_flowguard_model(SELF_MODEL_PATH, ROOT)
        self.assertEqual("skillguard.executable_contract_runtime.v2", snapshot.model_export["model_id"])
        self.assertEqual("1.0", snapshot.flowguard_schema_version)

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
            if row["step_id"] == "step:verify-target-specific-coverage"
        )
        judged_obligation = next(
            row
            for row in contract["obligations"]
            if judged_step["step_id"] in row["owner_step_ids"]
        )
        self.assertIn("judged", judged_obligation["evidence_classes"])

    def test_judged_step_with_unknown_declared_rubric_is_blocked(self) -> None:
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
                    "claim_scope": "routine",
                    "write_targets": ["out"],
                },
                "steps": {},
                "profiles": ["routine"],
            },
        )
        self.assertEqual("passed", report["status"])
        self.assertEqual(["route:static-audit"], report["route_ids"])
        self.assertEqual(3, len(report["executed_steps"]))
        self.assertTrue(report["closures"][0]["verification"]["ok"])

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
        base_request = {"route_ids": ["route:static-audit"], "claim_scope": "routine"}
        cases = (
            {"request": base_request, "steps": {}, "unknown_top": True},
            {"request": {**base_request, "cliam_scope": "routine"}, "steps": {}},
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
                    "request": {"route_ids": ["route:static-audit"], "claim_scope": "routine"},
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
                    "request": {"route_ids": ["route:static-audit"], "claim_scope": "routine"},
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

    def test_non_monotonic_profiles_are_rejected(self) -> None:
        self.binding["closure_profiles"][2]["required_obligation_ids"] = [
            self.export["obligations"][0]["obligation_id"]
        ]
        self._write_binding(self.binding)
        result = compile_skill_contract(self.skill, repository_root=self.repo, write=True)
        self.assertIn("non_monotonic_closure_profile", {row.code for row in result.findings})

    def test_v1_migration_is_candidate_only_and_cannot_compile(self) -> None:
        (self.control / "work-contract.json").write_text(
            json_text({"skill_id": "fixture-skill", "phases": [{"phase_id": "intake"}]}),
            encoding="utf-8",
        )
        (self.control / "check_manifest.json").write_text(
            json_text({"checks": [{"check_id": "legacy-check"}]}),
            encoding="utf-8",
        )
        candidate = migrate_v1_binding_candidate(self.skill)
        self.assertFalse(candidate.payload["confirmed"])
        self.assertFalse(candidate.payload["release_eligible"])
        self.assertIn("migration_candidate_requires_confirmation", {row.code for row in candidate.findings})
        self._write_binding(dict(candidate.payload))
        result = compile_skill_contract(self.skill, repository_root=self.repo, write=True)
        self.assertIn("unconfirmed_binding_source", {row.code for row in result.findings})

    def test_all_v2_json_schemas_are_parseable(self) -> None:
        schema_root = ROOT / ".agents" / "skills" / "skillguard" / "assets" / "schemas"
        paths = sorted(schema_root.glob("*v2.schema.json"))
        self.assertEqual(9, len(paths))
        for path in paths:
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual("object", payload["type"], path.name)
            self.assertTrue(payload["required"], path.name)


if __name__ == "__main__":
    unittest.main()
