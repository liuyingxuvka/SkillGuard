from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / ".agents" / "skills" / "skillguard"


def test_one_policy_projects_to_global_template_router_and_project_block() -> None:
    """The retired global policy has no current consumer import or renderer."""

    template = (
        SKILL_ROOT / "assets" / "templates" / "global_skillguard_prompt_block.md.template"
    ).read_text(encoding="utf-8")
    assert "{{validation_execution_policy}}" in template
    assert not (SKILL_ROOT / "scripts" / "skillguard_v2" / "validation_execution_policy.py").exists()
    assert "global_router" not in template


def test_test_mesh_manifest_has_no_file_or_command_freshness_surface() -> None:
    manifest = json.loads((SKILL_ROOT / "test-mesh.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "skillguard.test_mesh_manifest.current"
    assert "suites" not in manifest
    assert set(manifest) == {
        "schema_version",
        "mesh_id",
        "source_model_id",
        "profiles",
        "claim_boundary",
    }
    declared_keys = set(manifest)
    for profile in manifest["profiles"]:
        declared_keys.update(profile)
    for forbidden in ("source_paths", "command", "tasks.md", "receipt_root", "timeout_seconds"):
        assert forbidden not in declared_keys
