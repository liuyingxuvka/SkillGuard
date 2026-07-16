from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / ".agents" / "skills" / "skillguard" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import checker_engine  # noqa: E402


class GlobalRouterProjectionCurrentTests(unittest.TestCase):
    def test_skill_scan_ignores_nested_fixture_skill_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            skills_root = Path(temporary) / "skills"
            direct = skills_root / "direct-skill"
            nested = direct / "fixtures" / "nested-skill"
            nested.mkdir(parents=True)
            direct.joinpath("SKILL.md").write_text(
                "---\nname: direct-skill\ndescription: Direct fixture.\n---\n",
                encoding="utf-8",
            )
            nested.joinpath("SKILL.md").write_text(
                "---\nname: nested-skill\ndescription: Nested fixture.\n---\n",
                encoding="utf-8",
            )

            items, _warnings = checker_engine.discover_global_skill_items(
                [skills_root]
            )

            self.assertEqual(["direct-skill"], [row["skill_id"] for row in items])

    def test_renderer_uses_exact_template_and_maintenance_boundary(self) -> None:
        registry = {
            "registry_hash": "sha256:" + "a" * 64,
            "items": [
                {
                    "skill_id": "current-skill",
                    "skill_file": ".codex/skills/current-skill/SKILL.md",
                    "status": "current",
                    "route_entrypoint": {
                        "default_route_id": "route:current",
                        "integration_mode": "native-integrated",
                    },
                }
            ],
        }

        block = checker_engine.render_global_prompt_block(
            registry, ".codex/.skillguard/global-router/global_registry.json"
        )
        failures, blockers = checker_engine.check_global_prompt_text(
            block,
            registry["registry_hash"],
            block,
        )

        self.assertEqual([], failures)
        self.assertEqual([], blockers)
        self.assertIn(
            "Creating, updating, directly rewriting a non-current target, installing/synchronizing, or releasing",
            block,
        )
        self.assertIn(
            "Ordinary use of an already-installed skill",
            block,
        )
        self.assertIn("invalidates only owners and projections", block)
        self.assertNotIn("v1-legacy", block)
        tampered = block.replace(
            "Ordinary use of an already-installed skill",
            "Ordinary use of a skill",
            1,
        )
        tampered_failures, _ = checker_engine.check_global_prompt_text(
            tampered,
            registry["registry_hash"],
            block,
        )
        self.assertIn(
            "SkillGuard global router managed block is not the exact canonical template projection",
            tampered_failures,
        )

    def test_registry_splits_route_identity_from_diagnostic_inventory(self) -> None:
        item = {
            "skill_id": "fixture",
            "skill_name": "Fixture",
            "description": "Initial non-routing prose.",
            "skill_path": ".codex/skills/fixture",
            "skill_file": ".codex/skills/fixture/SKILL.md",
            "skill_sha256": "sha256:" + "1" * 64,
            "status": "current",
            "use_when": ["Use for fixture routing."],
            "do_not_use_when": ["Do not use for unrelated work."],
            "route_terms": ["fixture", "routing"],
            "route_entrypoint": {
                "integration_mode": "native-integrated",
                "route_confidence": "native-bound",
                "contract_authority": "current",
                "authority_decision": "current",
                "authority_blockers": [],
                "contract_source_path": ".codex/skills/fixture/.skillguard/contract-source.json",
                "contract_path": ".codex/skills/fixture/.skillguard/compiled-contract.json",
                "contract_hash": "DIAGNOSTIC-ONLY-CONTRACT-HASH",
                "check_manifest_path": ".codex/skills/fixture/.skillguard/check-manifest.json",
                "check_manifest_hash": "DIAGNOSTIC-ONLY-MANIFEST-HASH",
                "check_declarations_hash": "DIAGNOSTIC-ONLY-CHECK-HASH",
                "model_id": "fixture.model",
                "function_ids": ["route"],
                "route_ids": ["route:fixture"],
                "default_route_id": "route:fixture",
                "native_route_owner": "fixture",
                "native_route_bindings": ["route:fixture"],
                "native_check_bindings": ["check:fixture"],
                "phase_native_bindings": [],
                "may_define_parallel_execution_route": False,
                "may_define_skillguard_runtime_route": False,
                "route_doc_paths": [
                    ".codex/skills/fixture/SKILL.md",
                    ".codex/skills/fixture/.skillguard/contract-source.json",
                    ".codex/skills/fixture/.skillguard/compiled-contract.json",
                    ".codex/skills/fixture/.skillguard/check-manifest.json",
                ],
                "handoff_rule": "Read the selected current contract.",
            },
            "claim_boundary": "Diagnostic prose only.",
        }
        payload = {
            "schema_version": "skillguard.global_registry.current",
            "router_skill_id": "skillguard-global-router",
            "scan_roots": [{"path": ".codex/skills", "exists": True}],
            "items": [item],
            "warnings": [],
        }
        route_hash = checker_engine.global_registry_hash(payload)
        diagnostic_hash = checker_engine.global_diagnostic_inventory_hash(payload)

        diagnostic_only = copy.deepcopy(payload)
        diagnostic_only["items"][0]["description"] = "Changed non-routing prose."
        diagnostic_only["items"][0]["skill_sha256"] = "sha256:" + "2" * 64
        diagnostic_only["items"][0]["route_entrypoint"][
            "check_declarations_hash"
        ] = "CHANGED-DIAGNOSTIC-CHECK-HASH"
        self.assertEqual(
            route_hash, checker_engine.global_registry_hash(diagnostic_only)
        )
        self.assertNotEqual(
            diagnostic_hash,
            checker_engine.global_diagnostic_inventory_hash(diagnostic_only),
        )

        changed_route = copy.deepcopy(payload)
        changed_route["items"][0]["use_when"] = ["Use for a changed route."]
        self.assertNotEqual(
            route_hash, checker_engine.global_registry_hash(changed_route)
        )
        changed_default = copy.deepcopy(payload)
        changed_default["items"][0]["route_entrypoint"][
            "default_route_id"
        ] = "route:changed"
        self.assertNotEqual(
            route_hash, checker_engine.global_registry_hash(changed_default)
        )

        unknown_behavior = copy.deepcopy(payload)
        unknown_behavior["items"][0]["route_entrypoint"][
            "new_behavior_without_identity_policy"
        ] = True
        with self.assertRaisesRegex(
            ValueError, "global_route_entrypoint_unknown_field"
        ):
            checker_engine.global_registry_hash(unknown_behavior)

    def test_real_discovery_ignores_description_but_tracks_use_when(self) -> None:
        contract = {
            "contract_authority": "current",
            "authority_decision": "current",
            "authority_blockers": [],
            "contract_source_path": ".codex/skills/fixture/.skillguard/contract-source.json",
            "contract_path": ".codex/skills/fixture/.skillguard/compiled-contract.json",
            "check_manifest_path": ".codex/skills/fixture/.skillguard/check-manifest.json",
            "integration_mode": "native-integrated",
            "route_confidence": "native-bound",
            "model_id": "fixture.model",
            "function_ids": ["route"],
            "route_ids": ["route:fixture"],
            "default_route_id": "route:fixture",
            "native_route_owner": "fixture",
            "native_route_bindings": ["route:fixture"],
            "native_check_bindings": ["check:fixture"],
            "phase_native_bindings": [],
            "may_define_parallel_execution_route": False,
            "may_define_skillguard_runtime_route": False,
            "route_doc_paths": [
                ".codex/skills/fixture/SKILL.md",
                ".codex/skills/fixture/.skillguard/contract-source.json",
                ".codex/skills/fixture/.skillguard/compiled-contract.json",
                ".codex/skills/fixture/.skillguard/check-manifest.json",
            ],
            "handoff_rule": "Read the current fixture contract.",
        }

        def skill_text(description: str, use_when: str) -> str:
            return (
                "---\n"
                "name: fixture\n"
                f"description: {description}\n"
                "---\n\n"
                "## Use When\n\n"
                f"- {use_when}\n\n"
                "## Do Not Use When\n\n"
                "- Do not use for unrelated work.\n"
            )

        with tempfile.TemporaryDirectory() as temporary:
            skills_root = Path(temporary) / "skills"
            skill = skills_root / "fixture"
            skill.mkdir(parents=True)
            skill_file = skill / "SKILL.md"
            with mock.patch.object(
                checker_engine.current_global_discovery,
                "contract_projection",
                return_value=(contract, []),
            ):
                skill_file.write_text(
                    skill_text("First diagnostic prose.", "Use for alpha routing."),
                    encoding="utf-8",
                )
                first = checker_engine.build_global_registry_payload([skills_root])
                skill_file.write_text(
                    skill_text("Completely different prose.", "Use for alpha routing."),
                    encoding="utf-8",
                )
                diagnostic_change = checker_engine.build_global_registry_payload(
                    [skills_root]
                )
                skill_file.write_text(
                    skill_text("Completely different prose.", "Use for beta routing."),
                    encoding="utf-8",
                )
                route_change = checker_engine.build_global_registry_payload(
                    [skills_root]
                )

        self.assertEqual(first["registry_hash"], diagnostic_change["registry_hash"])
        self.assertNotEqual(
            first["diagnostic_inventory_hash"],
            diagnostic_change["diagnostic_inventory_hash"],
        )
        self.assertNotEqual(first["registry_hash"], route_change["registry_hash"])


if __name__ == "__main__":
    unittest.main()
