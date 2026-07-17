from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPO_ROOT / ".agents" / "skills" / "skillguard"
SKILLGUARD = SKILL_ROOT / "scripts" / "skillguard.py"
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from skillguard_v2.template_packs import (  # noqa: E402
    seal_template_catalog,
    seal_template_manifest,
    sha256_identity,
)
from skillguard_v2.template_profiles import (  # noqa: E402
    PROFILE_FIELDS,
    TemplateProfileError,
    validate_template_profile,
)
import checker_engine  # noqa: E402


def relative(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_skillguard(*args: str, expected_exit: int = 0) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(SKILLGUARD), *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != expected_exit:
        raise AssertionError(
            f"skillguard.py {' '.join(args)} exited {completed.returncode}, expected {expected_exit}\n"
            f"stderr={completed.stderr}\nstdout={completed.stdout}"
        )
    return json.loads(completed.stdout)


def skill_idea(target: Path) -> dict[str, Any]:
    return {
        "skill_name": target.name,
        "description": f"Use when maintaining {target.name} through validated evidence.",
        "purpose": f"Maintain {target.name} without hidden validation gaps.",
        "target_path": relative(target),
    }


def manifest(template_id: str, kind: str, *, base: bool, field: str) -> dict[str, Any]:
    failure_id = f"failure:{template_id}"
    content_hash = sha256_identity({"template_id": template_id, "content": "current"})
    return seal_template_manifest(
        {
            "schema_version": "skillguard.template_manifest.v1",
            "template_id": template_id,
            "revision": "1",
            "template_kind": kind,
            "native_owner_id": "owner:test-target",
            "family_id": "family:test-target",
            "route_ids": ["route:test-target"],
            "applicability_predicate_ids": [f"predicate:{template_id}"],
            "forbidden_condition_ids": [f"forbidden:{template_id}"],
            "dependencies": [],
            "compatible_with": [],
            "conflicts_with": [],
            "dominates_template_ids": [],
            "composable": False,
            "composition_order": 0 if base else 1,
            "is_validated_base": base,
            "field_ownership": [field],
            "parameter_schema": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
            "artifacts": [
                {
                    "artifact_id": f"artifact:{template_id}",
                    "path_template": f"generated/{template_id}.json",
                    "content_template_hash": content_hash,
                }
            ],
            "builder": {
                "builder_id": f"builder:{template_id}",
                "entrypoint": "target_builder:build",
                "content_hash": content_hash,
            },
            "validators": [
                {
                    "validator_id": f"validator:{template_id}",
                    "check_id": f"check:{template_id}",
                    "evidence_domain": "test-target",
                    "content_hash": content_hash,
                }
            ],
            "prompt_fragments": [],
            "protected_failure_ids": [failure_id],
            "fixtures": {
                "known_good_ids": [f"fixture:good:{template_id}"],
                "known_bad_by_failure": {failure_id: [f"fixture:bad:{template_id}"]},
                "ambiguity_ids": ["fixture:ambiguous"],
                "stale_ids": ["fixture:stale"],
            },
            "claim_boundary": "Test target template semantics remain target-owned.",
        }
    )


def external_records(workspace: Path, domain_count: int) -> dict[str, str]:
    templates = [manifest("test-base", "base", base=True, field="field:base")]
    templates.extend(
        manifest(f"test-domain-{index}", "profile", base=False, field=f"field:domain:{index}")
        for index in range(1, domain_count + 1)
    )
    catalog = seal_template_catalog(
        {
            "schema_version": "skillguard.template_catalog.v1",
            "catalog_id": "catalog:test-target",
            "revision": "1",
            "native_owner_id": "owner:test-target",
            "family_id": "family:test-target",
            "base_template_id": "test-base",
            "templates": templates,
            "harvest_policy": {
                "required": True,
                "allowed_dispositions": ["reused", "created", "not_harvestable"],
            },
            "claim_boundary": "Test catalog only.",
        }
    )
    request_fingerprint = sha256_identity({"request": "external-template-test", "domain_count": domain_count})
    projection = {
        "schema_version": "skillguard.target_template_projection.v1",
        "target_id": "target:test-target",
        "native_owner_id": "owner:test-target",
        "family_id": "family:test-target",
        "route_id": "route:test-target",
        "request_fingerprint": request_fingerprint,
        "catalog": catalog,
        "applicability_results": [
            {
                "template_id": item["template_id"],
                "eligible": True,
                "predicate_evidence_ids": [f"evidence:predicate:{item['template_id']}"],
                "forbidden_clearance_evidence_ids": [f"evidence:forbidden:{item['template_id']}"],
                "reasons": [],
            }
            for item in templates
        ],
        "claim_boundary": "Test target owns route and applicability semantics.",
    }
    projection_path = workspace / "target-template-projection.json"
    write_json(projection_path, projection)
    return {"adapter_projection_path": relative(projection_path)}


class TemplateProfileIntegrationTest(unittest.TestCase):
    def test_profile_schema_and_runtime_root_fields_are_identical(self) -> None:
        schema = json.loads(
            (SKILL_ROOT / "assets" / "schemas" / "skillguard_template_profile_v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(set(schema["required"]), set(PROFILE_FIELDS))
        self.assertEqual(set(schema["properties"]), set(PROFILE_FIELDS))
        self.assertFalse(schema["additionalProperties"])
        blueprint_schema = json.loads(
            (SKILL_ROOT / "assets" / "schemas" / "skillguard_skill_blueprint_v2.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            set(blueprint_schema["properties"]),
            set(checker_engine.GENERATE_SKILL_BLUEPRINT_FIELDS),
        )
        self.assertEqual(
            set(blueprint_schema["required"]),
            set(checker_engine.GENERATE_SKILL_BLUEPRINT_FIELDS),
        )

    def test_plan_and_generate_use_current_validated_base_preview(self) -> None:
        with tempfile.TemporaryDirectory(prefix="template-profile-", dir=REPO_ROOT / ".agents" / "skills") as tmp:
            workspace = Path(tmp)
            target = workspace / "validated-base-skill"
            idea_path = workspace / "idea.json"
            plan_path = workspace / "plan.json"
            write_json(idea_path, skill_idea(target))

            plan = run_skillguard("plan-skill", "--input", relative(idea_path))
            self.assertFalse(target.exists())
            blueprint = plan["skill_blueprint"]
            self.assertEqual(blueprint["schema_version"], "skillguard.skill_blueprint.v2")
            self.assertEqual(blueprint["template_profile"]["profile_kind"], "skillguard_validated_base")
            self.assertEqual(plan["template_selection"]["disposition"], "base_no_match")
            self.assertEqual(plan["template_preview"]["status"], "current")
            self.assertTrue(plan["affected_components"])
            poisoned = json.loads(json.dumps(blueprint["template_profile"]))
            poisoned["undeclared"] = True
            with self.assertRaises(TemplateProfileError):
                validate_template_profile(poisoned)
            write_json(plan_path, plan)

            generated = run_skillguard("generate-skill", "--input", relative(plan_path))
            self.assertEqual(generated["decision"], "pass")
            self.assertEqual(generated["template_instance_receipt"]["status"], "passed")
            self.assertEqual(generated["template_harvest_review"]["disposition"], "not_harvestable")
            skill_text = (target / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("## Validated Template Pack Selection", skill_text)
            self.assertIn("## Validated Template Pack Instance", skill_text)
            self.assertIn("## Validated Template Pack Installation", skill_text)

    def test_stale_source_blocks_before_any_target_write(self) -> None:
        with tempfile.TemporaryDirectory(prefix="template-stale-", dir=REPO_ROOT / ".agents" / "skills") as tmp:
            workspace = Path(tmp)
            target = workspace / "stale-source-skill"
            idea_path = workspace / "idea.json"
            plan_path = workspace / "plan.json"
            idea = skill_idea(target)
            write_json(idea_path, idea)
            write_json(plan_path, run_skillguard("plan-skill", "--input", relative(idea_path)))
            idea["purpose"] = "Materially changed after preview."
            write_json(idea_path, idea)

            blocked = run_skillguard("generate-skill", "--input", relative(plan_path), expected_exit=1)
            self.assertEqual(blocked["decision"], "block")
            self.assertFalse(target.exists())
            self.assertTrue(any("template source is stale: source_input" in item for item in blocked["blockers"]))

    def test_existing_empty_target_is_not_partially_filled(self) -> None:
        with tempfile.TemporaryDirectory(prefix="template-atomic-", dir=REPO_ROOT / ".agents" / "skills") as tmp:
            workspace = Path(tmp)
            target = workspace / "existing-empty-skill"
            idea_path = workspace / "idea.json"
            plan_path = workspace / "plan.json"
            write_json(idea_path, skill_idea(target))
            write_json(plan_path, run_skillguard("plan-skill", "--input", relative(idea_path)))
            target.mkdir()

            blocked = run_skillguard("generate-skill", "--input", relative(plan_path), expected_exit=1)
            self.assertEqual(blocked["decision"], "block")
            self.assertEqual(list(target.iterdir()), [])
            self.assertTrue(
                any("atomic direct-current replacement" in item for item in blocked["blockers"]),
                blocked["blockers"],
            )

    def test_target_owned_profile_hands_off_without_generic_write(self) -> None:
        with tempfile.TemporaryDirectory(prefix="template-handoff-", dir=REPO_ROOT / ".agents" / "skills") as tmp:
            workspace = Path(tmp)
            target = workspace / "target-owned-skill"
            idea_path = workspace / "idea.json"
            plan_path = workspace / "plan.json"
            idea = skill_idea(target)
            idea["template_request"] = {**external_records(workspace, 1), "parameters": {}}
            write_json(idea_path, idea)

            plan = run_skillguard("plan-skill", "--input", relative(idea_path))
            self.assertEqual(plan["template_selection"]["disposition"], "single_selected")
            self.assertEqual(plan["template_preview"]["status"], "target_builder_required")
            write_json(plan_path, plan)

            blocked = run_skillguard("generate-skill", "--input", relative(plan_path), expected_exit=1)
            self.assertEqual(blocked["decision"], "block")
            self.assertFalse(target.exists())
            self.assertTrue(any("target_native_builder_required" in item for item in blocked["blockers"]))

    def test_ambiguous_target_candidates_block_in_plan(self) -> None:
        with tempfile.TemporaryDirectory(prefix="template-ambiguous-", dir=REPO_ROOT / ".agents" / "skills") as tmp:
            workspace = Path(tmp)
            target = workspace / "ambiguous-skill"
            idea_path = workspace / "idea.json"
            idea = skill_idea(target)
            idea["template_request"] = {**external_records(workspace, 2), "parameters": {}}
            write_json(idea_path, idea)

            plan = run_skillguard("plan-skill", "--input", relative(idea_path), expected_exit=1)
            self.assertEqual(plan["decision"], "block")
            self.assertEqual(plan["template_selection"]["disposition"], "ambiguous_template_selection")
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
