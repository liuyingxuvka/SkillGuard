from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / ".agents" / "skills" / "skillguard"
SCRIPT_ROOT = SKILL_ROOT / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from checker_engine import render_global_prompt_block  # noqa: E402
from skillguard_v2.project_adoption import render_project_block  # noqa: E402
from skillguard_v2.validation_execution_policy import (  # noqa: E402
    VALIDATION_EXECUTION_POLICY_ID,
    VALIDATION_EXECUTION_POLICY_LINES,
)


class ValidationExecutionPolicyProjectionTests(unittest.TestCase):
    def test_one_policy_projects_to_global_template_router_and_project_block(self) -> None:
        template = (
            SKILL_ROOT
            / "assets"
            / "templates"
            / "global_skillguard_prompt_block.md.template"
        ).read_text(encoding="utf-8")
        global_block = render_global_prompt_block(
            {
                "registry_hash": "A" * 64,
                "items": [],
            },
            ".codex/.skillguard/global-router/global_registry.json",
        )
        project_block = render_project_block({"managed_skills": []})
        self.assertIn("{{validation_execution_policy}}", template)
        for line in VALIDATION_EXECUTION_POLICY_LINES:
            self.assertNotIn(line, template)
        for projection in (global_block, project_block):
            self.assertIn(VALIDATION_EXECUTION_POLICY_ID, projection)
            for line in VALIDATION_EXECUTION_POLICY_LINES:
                self.assertIn(line, projection)

        policy_literal = VALIDATION_EXECUTION_POLICY_LINES[0]
        owners = []
        for path in (SKILL_ROOT / "scripts").rglob("*.py"):
            if policy_literal in path.read_text(encoding="utf-8"):
                owners.append(path.relative_to(SKILL_ROOT).as_posix())
        self.assertEqual(
            ["scripts/skillguard_v2/validation_execution_policy.py"],
            owners,
        )

    def test_test_mesh_manifest_has_no_file_or_command_freshness_surface(self) -> None:
        manifest = json.loads((SKILL_ROOT / "test-mesh.json").read_text(encoding="utf-8"))
        self.assertEqual("skillguard.test_mesh_manifest.current", manifest["schema_version"])
        self.assertNotIn("suites", manifest)
        self.assertEqual(
            {
                "schema_version",
                "mesh_id",
                "source_model_id",
                "profiles",
                "claim_boundary",
            },
            set(manifest),
        )
        declared_keys = set(manifest)
        for profile in manifest["profiles"]:
            declared_keys.update(profile)
        for forbidden in (
            "source_paths",
            "command",
            "tasks.md",
            "receipt_root",
            "timeout_seconds",
        ):
            self.assertNotIn(forbidden, declared_keys)


if __name__ == "__main__":
    unittest.main()
