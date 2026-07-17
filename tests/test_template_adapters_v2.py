from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPO_ROOT / ".agents" / "skills" / "skillguard"
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from skillguard_v2.template_adapters import (  # noqa: E402
    PROJECTION_FIELDS,
    compile_target_template_projection,
)
from skillguard_v2.template_packs import (  # noqa: E402
    TemplatePackError,
    seal_template_catalog,
    seal_template_manifest,
    sha256_identity,
)


def manifest(template_id: str, *, base: bool) -> dict[str, object]:
    content_hash = sha256_identity({"template": template_id, "content": "current"})
    failure_id = f"failure:{template_id}"
    return seal_template_manifest(
        {
            "schema_version": "skillguard.template_manifest.v1",
            "template_id": template_id,
            "revision": "1",
            "template_kind": "base" if base else "profile",
            "native_owner_id": "owner:test-guard",
            "family_id": "family:test-guard",
            "route_ids": ["route:test-guard"],
            "applicability_predicate_ids": [f"predicate:{template_id}"],
            "forbidden_condition_ids": [f"forbidden:{template_id}"],
            "dependencies": [],
            "compatible_with": [],
            "conflicts_with": [],
            "dominates_template_ids": [],
            "composable": False,
            "composition_order": 0 if base else 1,
            "is_validated_base": base,
            "field_ownership": [f"field:{template_id}"],
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
                "entrypoint": "test_guard.adapter:build",
                "content_hash": content_hash,
            },
            "validators": [
                {
                    "validator_id": f"validator:{template_id}",
                    "check_id": f"check:{template_id}",
                    "evidence_domain": "test-guard",
                    "content_hash": content_hash,
                }
            ],
            "prompt_fragments": [],
            "protected_failure_ids": [failure_id],
            "fixtures": {
                "known_good_ids": [f"fixture:good:{template_id}"],
                "known_bad_by_failure": {failure_id: [f"fixture:bad:{template_id}"]},
                "ambiguity_ids": ["fixture:ambiguity"],
                "stale_ids": ["fixture:stale"],
            },
            "claim_boundary": "Target test Guard remains the semantic owner.",
        }
    )


def projection() -> dict[str, object]:
    templates = [manifest("test-base", base=True), manifest("test-domain", base=False)]
    catalog = seal_template_catalog(
        {
            "schema_version": "skillguard.template_catalog.v1",
            "catalog_id": "catalog:test-guard",
            "revision": "1",
            "native_owner_id": "owner:test-guard",
            "family_id": "family:test-guard",
            "base_template_id": "test-base",
            "templates": templates,
            "harvest_policy": {
                "required": True,
                "allowed_dispositions": ["reused", "created", "not_harvestable"],
            },
            "claim_boundary": "Target test catalog only.",
        }
    )
    return {
        "schema_version": "skillguard.target_template_projection.v1",
        "target_id": "target:test-guard",
        "native_owner_id": "owner:test-guard",
        "family_id": "family:test-guard",
        "route_id": "route:test-guard",
        "request_fingerprint": sha256_identity({"request": "current"}),
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
        "claim_boundary": "Target owns route and applicability semantics.",
    }


class TargetTemplateAdapterTests(unittest.TestCase):
    def test_schema_and_runtime_root_fields_are_exact(self) -> None:
        schema = json.loads(
            (SKILL_ROOT / "assets" / "schemas" / "skillguard_target_template_projection_v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(set(schema["required"]), set(PROJECTION_FIELDS))
        self.assertEqual(set(schema["properties"]), set(PROJECTION_FIELDS))
        self.assertFalse(schema["additionalProperties"])

    def test_target_projection_seals_current_neutral_records(self) -> None:
        records = compile_target_template_projection(projection())
        self.assertEqual(records.catalog["family_id"], "family:test-guard")
        self.assertEqual(records.native_route_receipt["route_id"], "route:test-guard")
        self.assertEqual(
            {row["template_id"] for row in records.applicability_receipt["results"]},
            {"test-base", "test-domain"},
        )

    def test_unknown_root_and_incomplete_candidate_inventory_block(self) -> None:
        unknown = projection()
        unknown["family_guess"] = "forbidden"
        incomplete = projection()
        incomplete["applicability_results"] = incomplete["applicability_results"][:-1]
        for payload, expected in (
            (unknown, "target_projection_unknown_field"),
            (incomplete, "target_projection_candidate_inventory_mismatch"),
        ):
            with self.subTest(expected=expected), self.assertRaises(TemplatePackError) as caught:
                compile_target_template_projection(payload)
            self.assertIn(expected, {item.code for item in caught.exception.findings})

    def test_wrong_native_route_and_stale_native_manifest_block(self) -> None:
        wrong_route = projection()
        wrong_route["route_id"] = "route:not-declared"
        stale = projection()
        stale["catalog"] = copy.deepcopy(stale["catalog"])
        stale["catalog"]["templates"][0]["claim_boundary"] = "Changed after native sealing."
        for payload, expected in (
            (wrong_route, "native_route_unknown"),
            (stale, "manifest_digest_mismatch"),
        ):
            with self.subTest(expected=expected), self.assertRaises(TemplatePackError) as caught:
                compile_target_template_projection(payload)
            self.assertIn(expected, {item.code for item in caught.exception.findings})


if __name__ == "__main__":
    unittest.main()
