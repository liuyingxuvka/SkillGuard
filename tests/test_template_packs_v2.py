from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

try:
    import jsonschema  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover - optional complete validator
    jsonschema = None


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / ".agents" / "skills" / "skillguard" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from skillguard_v2.template_packs import (  # noqa: E402
    APPLICABILITY_RECEIPT_FIELDS,
    APPLICABILITY_RECEIPT_SCHEMA,
    CATALOG_FIELDS,
    INSTANCE_RECEIPT_FIELDS,
    MANIFEST_FIELDS,
    ROUTE_RECEIPT_FIELDS,
    SELECTION_RECEIPT_FIELDS,
    TEMPLATE_CATALOG_SCHEMA,
    TEMPLATE_MANIFEST_SCHEMA,
    TemplatePackError,
    build_instance_receipt,
    seal_applicability_receipt,
    seal_builder_receipt,
    seal_native_route_receipt,
    seal_template_catalog,
    seal_template_manifest,
    seal_validator_receipt,
    select_template_packs,
    selection_receipt_current,
    sha256_identity,
    template_content_components,
    validate_instance_receipt,
    validate_template_catalog,
    validate_template_manifest,
)


def manifest(
    template_id: str,
    *,
    kind: str = "profile",
    base: bool = False,
    composable: bool = False,
    order: int = 10,
    fields: tuple[str, ...] | None = None,
    dependencies: tuple[str, ...] = (),
    compatible: tuple[str, ...] = (),
    conflicts: tuple[str, ...] = (),
    dominates: tuple[str, ...] = (),
) -> dict:
    body_hash = sha256_identity({"body": template_id})
    builder_hash = sha256_identity({"builder": template_id})
    validator_hash = sha256_identity({"validator": template_id})
    prompt_hash = sha256_identity({"prompt": template_id})
    return seal_template_manifest(
        {
            "schema_version": TEMPLATE_MANIFEST_SCHEMA,
            "template_id": template_id,
            "revision": "1",
            "template_kind": "base" if base else kind,
            "native_owner_id": "owner:test-family",
            "family_id": "test-family",
            "route_ids": ["route:test"],
            "applicability_predicate_ids": [f"predicate:{template_id}"],
            "forbidden_condition_ids": [f"forbidden:{template_id}"],
            "dependencies": list(dependencies),
            "compatible_with": list(compatible),
            "conflicts_with": list(conflicts),
            "dominates_template_ids": list(dominates),
            "composable": composable,
            "composition_order": order,
            "is_validated_base": base,
            "field_ownership": list(fields or (f"field:{template_id}",)),
            "parameter_schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "default": template_id},
                    "count": {"type": "integer", "minimum": 1},
                },
                "required": ["count"],
                "additionalProperties": False,
            },
            "artifacts": [
                {
                    "artifact_id": f"artifact:{template_id}",
                    "path_template": f"generated/{template_id}.json",
                    "content_template_hash": body_hash,
                }
            ],
            "builder": {
                "builder_id": f"builder:{template_id}",
                "entrypoint": f"test_family.builders:{template_id}",
                "content_hash": builder_hash,
            },
            "validators": [
                {
                    "validator_id": f"validator:{template_id}",
                    "check_id": f"check:{template_id}",
                    "evidence_domain": "test-family",
                    "content_hash": validator_hash,
                }
            ],
            "prompt_fragments": [
                {
                    "fragment_id": f"prompt:{template_id}",
                    "content_hash": prompt_hash,
                }
            ],
            "protected_failure_ids": ["failure:invalid-output"],
            "fixtures": {
                "known_good_ids": [f"fixture:{template_id}:good"],
                "known_bad_by_failure": {
                    "failure:invalid-output": [f"fixture:{template_id}:bad"]
                },
                "ambiguity_ids": [f"fixture:{template_id}:ambiguous"],
                "stale_ids": [f"fixture:{template_id}:stale"],
            },
            "claim_boundary": "Template structure only; no domain truth or release claim.",
        }
    )


def catalog(*templates: dict, base_id: str = "") -> dict:
    return seal_template_catalog(
        {
            "schema_version": TEMPLATE_CATALOG_SCHEMA,
            "catalog_id": "catalog:test-family",
            "revision": "1",
            "native_owner_id": "owner:test-family",
            "family_id": "test-family",
            "base_template_id": base_id,
            "templates": list(templates),
            "harvest_policy": {
                "required": True,
                "allowed_dispositions": [
                    "reused",
                    "updated",
                    "duplicate_linked",
                    "created",
                    "not_harvestable",
                ],
            },
            "claim_boundary": "Catalog ownership only; selection and instances need receipts.",
        }
    )


def route_receipt(cat: dict, request: str = "request-one") -> dict:
    return seal_native_route_receipt(
        {
            "target_id": "target:test",
            "native_owner_id": "owner:test-family",
            "family_id": "test-family",
            "route_id": "route:test",
            "request_fingerprint": sha256_identity({"request": request}),
            "catalog_id": cat["catalog_id"],
            "status": "passed",
            "claim_boundary": "Native route decision only.",
        }
    )


def applicability_receipt(cat: dict, route: dict, eligible: set[str]) -> dict:
    results = []
    for item in cat["templates"]:
        is_eligible = item["template_id"] in eligible
        results.append(
            {
                "template_id": item["template_id"],
                "manifest_digest": item["manifest_digest"],
                "eligible": is_eligible,
                "predicate_evidence_ids": [f"evidence:predicate:{item['template_id']}"] if is_eligible else [],
                "forbidden_clearance_evidence_ids": [f"evidence:forbidden:{item['template_id']}"] if is_eligible else [],
                "reasons": [] if is_eligible else ["target_predicate_not_satisfied"],
            }
        )
    return seal_applicability_receipt(
        {
            "schema_version": APPLICABILITY_RECEIPT_SCHEMA,
            "native_owner_id": "owner:test-family",
            "family_id": "test-family",
            "request_fingerprint": route["request_fingerprint"],
            "catalog_digest": cat["catalog_digest"],
            "route_receipt_hash": route["receipt_hash"],
            "results": results,
            "claim_boundary": "Target-native applicability only.",
        }
    )


def selection(cat: dict, eligible: set[str], request: str = "request-one"):
    route = route_receipt(cat, request)
    applicability = applicability_receipt(cat, route, eligible)
    return select_template_packs(cat, route, applicability), route, applicability


def reseal_receipt(payload: dict, prefix: str) -> dict:
    semantic = {
        key: copy.deepcopy(value)
        for key, value in payload.items()
        if key not in {"receipt_id", "receipt_hash"}
    }
    receipt_hash = sha256_identity(semantic)
    return {
        **semantic,
        "receipt_id": f"{prefix}-{receipt_hash.removeprefix('sha256:')[:24]}",
        "receipt_hash": receipt_hash,
    }


class TemplateManifestAndCatalogTests(unittest.TestCase):
    def test_runtime_allowed_fields_equal_published_schema_fields(self) -> None:
        protocol_schema = json.loads(
            (
                ROOT
                / ".agents"
                / "skills"
                / "skillguard"
                / "assets"
                / "schemas"
                / "skillguard_template_pack_protocol_v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        expected = {
            "manifest": MANIFEST_FIELDS,
            "catalog": CATALOG_FIELDS,
            "nativeRouteReceipt": ROUTE_RECEIPT_FIELDS,
            "applicabilityReceipt": APPLICABILITY_RECEIPT_FIELDS,
            "selectionReceipt": SELECTION_RECEIPT_FIELDS,
            "instanceReceipt": INSTANCE_RECEIPT_FIELDS,
        }
        for definition, runtime_fields in expected.items():
            schema = protocol_schema["$defs"][definition]
            with self.subTest(definition=definition):
                self.assertFalse(schema["additionalProperties"])
                self.assertEqual(runtime_fields, frozenset(schema["properties"]))
                self.assertEqual(runtime_fields, frozenset(schema["required"]))

    def test_current_manifest_and_catalog_are_content_addressed(self) -> None:
        base = manifest("base", base=True)
        profile = manifest("profile")
        cat = catalog(base, profile, base_id="base")

        self.assertEqual("base", validate_template_manifest(base).template_id)
        validated = validate_template_catalog(cat)
        self.assertEqual(cat["catalog_digest"], validated.digest)
        self.assertEqual({"base", "profile"}, set(validated.manifest_index()))

    def test_unknown_field_digest_drift_and_missing_native_binding_block(self) -> None:
        current = manifest("profile")
        cases = []
        unknown = copy.deepcopy(current)
        unknown["quality_score"] = 99
        cases.append((unknown, "unknown_field"))
        stale = copy.deepcopy(current)
        stale["revision"] = "2"
        cases.append((stale, "manifest_digest_mismatch"))
        missing = copy.deepcopy(current)
        missing["builder"]["builder_id"] = ""
        missing = seal_template_manifest(missing)
        cases.append((missing, "required_text_missing"))

        for payload, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(TemplatePackError) as caught:
                    validate_template_manifest(payload)
                self.assertIn(code, {row.code for row in caught.exception.findings})

    def test_catalog_rejects_dangling_dependency_asymmetric_compatibility_and_cycles(self) -> None:
        dangling = manifest("dangling", dependencies=("missing",))
        with self.assertRaises(TemplatePackError) as caught:
            validate_template_catalog(catalog(dangling))
        self.assertIn("template_reference_unknown", {row.code for row in caught.exception.findings})

        left = manifest("left", composable=True, compatible=("right",))
        right = manifest("right", composable=True)
        with self.assertRaises(TemplatePackError) as caught:
            validate_template_catalog(catalog(left, right))
        self.assertIn("compatibility_not_mutual", {row.code for row in caught.exception.findings})

        alpha = manifest("alpha", dependencies=("beta",))
        beta = manifest("beta", dependencies=("alpha",))
        with self.assertRaises(TemplatePackError) as caught:
            validate_template_catalog(catalog(alpha, beta))
        self.assertIn("dependency_cycle", {row.code for row in caught.exception.findings})


class TemplateSelectionTests(unittest.TestCase):
    def test_zero_candidate_uses_only_declared_eligible_base(self) -> None:
        base = manifest("base", base=True)
        profile = manifest("profile")
        cat = catalog(base, profile, base_id="base")
        receipt, _, _ = selection(cat, {"base"})

        self.assertEqual("selected", receipt["status"])
        self.assertEqual("base_no_match", receipt["disposition"])
        self.assertEqual(["base"], receipt["selected_template_ids"])
        self.assertTrue(receipt["harvest_review_required"])
        self.assertEqual(2, len(receipt["candidate_accounting"]))

    def test_zero_candidate_without_base_is_explicitly_blocked(self) -> None:
        cat = catalog(manifest("profile"))
        receipt, _, _ = selection(cat, set())

        self.assertEqual("blocked", receipt["status"])
        self.assertEqual("base_no_match", receipt["disposition"])
        self.assertEqual([], receipt["selected_template_ids"])
        self.assertIn(
            "no_eligible_domain_template_and_no_eligible_validated_base",
            receipt["findings"],
        )

    def test_one_candidate_is_selected_without_lexical_scoring(self) -> None:
        cat = catalog(manifest("zulu"), manifest("alpha"))
        receipt, _, _ = selection(cat, {"zulu"})

        self.assertEqual("single_selected", receipt["disposition"])
        self.assertEqual(["zulu"], receipt["selected_template_ids"])

    def test_many_compatible_disjoint_fragments_compose_in_declared_order(self) -> None:
        first = manifest(
            "zulu",
            kind="fragment",
            composable=True,
            order=10,
            compatible=("alpha",),
            fields=("field:zulu",),
        )
        second = manifest(
            "alpha",
            kind="fragment",
            composable=True,
            order=20,
            compatible=("zulu",),
            fields=("field:alpha",),
        )
        cat = catalog(first, second)
        receipt, _, _ = selection(cat, {"alpha", "zulu"})

        self.assertEqual("composed", receipt["disposition"])
        self.assertEqual(["zulu", "alpha"], receipt["composition_order"])
        self.assertEqual(
            {"field:alpha": "alpha", "field:zulu": "zulu"},
            receipt["field_owner_map"],
        )

    def test_field_collision_and_missing_dependency_block_as_ambiguous(self) -> None:
        left = manifest(
            "left",
            kind="fragment",
            composable=True,
            order=10,
            compatible=("right",),
            fields=("shared",),
        )
        right = manifest(
            "right",
            kind="fragment",
            composable=True,
            order=20,
            compatible=("left",),
            fields=("shared",),
        )
        receipt, _, _ = selection(catalog(left, right), {"left", "right"})
        self.assertEqual("ambiguous_template_selection", receipt["disposition"])
        self.assertTrue(any(item.startswith("field_owner_conflict") for item in receipt["findings"]))

        dependency = manifest("dependency")
        child = manifest("child", composable=True, dependencies=("dependency",))
        other = manifest("other", composable=True)
        receipt, _, _ = selection(catalog(dependency, child, other), {"child", "other"})
        self.assertEqual("blocked", receipt["status"])
        self.assertTrue(any(item.startswith("missing_dependency") for item in receipt["findings"]))

    def test_unique_target_authored_strict_dominance_selects_without_score(self) -> None:
        winner = manifest("winner", dominates=("other",))
        other = manifest("other")
        receipt, _, _ = selection(catalog(winner, other), {"winner", "other"})

        self.assertEqual("strictly_dominated_selection", receipt["disposition"])
        self.assertEqual(["winner"], receipt["selected_template_ids"])
        other_row = next(item for item in receipt["candidate_accounting"] if item["template_id"] == "other")
        self.assertEqual(["strictly_dominated_by:winner"], other_row["reasons"])

    def test_changed_request_or_catalog_makes_selection_stale(self) -> None:
        cat = catalog(manifest("profile"))
        receipt, route, applicability = selection(cat, {"profile"})
        current, findings = selection_receipt_current(receipt, cat, route, applicability)
        self.assertTrue(current, findings)

        changed_route = route_receipt(cat, "changed-request")
        changed_applicability = applicability_receipt(cat, changed_route, {"profile"})
        current, findings = selection_receipt_current(
            receipt,
            cat,
            changed_route,
            changed_applicability,
        )
        self.assertFalse(current)
        self.assertTrue(findings)


class TemplateInstanceTests(unittest.TestCase):
    def _good_instance_inputs(self):
        item = manifest("profile")
        cat = catalog(item)
        selected, route, applicability = selection(cat, {"profile"})
        builder = item["builder"]
        validator = item["validators"][0]
        builder_receipt = seal_builder_receipt(
            {
                "template_id": "profile",
                "manifest_digest": item["manifest_digest"],
                "builder_id": builder["builder_id"],
                "builder_content_hash": builder["content_hash"],
                "status": "passed",
                "claim_boundary": "Read-only builder execution facts only.",
            }
        )
        validator_receipt = seal_validator_receipt(
            {
                "template_id": "profile",
                "manifest_digest": item["manifest_digest"],
                "validator_id": validator["validator_id"],
                "validator_content_hash": validator["content_hash"],
                "check_id": validator["check_id"],
                "status": "passed",
                "claim_boundary": "Native structural validator only.",
            }
        )
        artifact = {
            "template_id": "profile",
            "manifest_digest": item["manifest_digest"],
            "artifact_id": "artifact:profile",
            "relative_path": "generated/profile.json",
            "sha256": sha256_identity({"generated": "profile"}),
        }
        return cat, selected, route, applicability, builder_receipt, validator_receipt, artifact

    def test_instance_binds_parameters_builders_artifacts_and_native_validators(self) -> None:
        cat, selected, route, applicability, builder, validator, artifact = self._good_instance_inputs()
        receipt = build_instance_receipt(
            selection_receipt_payload=selected,
            catalog_payload=cat,
            route_receipt_payload=route,
            applicability_receipt_payload=applicability,
            parameters={"profile": {"count": 2}},
            builder_receipts=[builder],
            generated_artifacts=[artifact],
            unresolved_placeholders=[],
            validator_receipts=[validator],
        )

        self.assertEqual("passed", receipt["status"])
        self.assertEqual("profile", receipt["parameters"]["profile"]["title"])
        self.assertTrue(receipt["instance_fingerprint"].startswith("sha256:"))
        validate_instance_receipt(receipt, selected, cat)

    def test_unresolved_placeholder_missing_validator_and_unknown_parameter_block(self) -> None:
        cat, selected, route, applicability, builder, validator, artifact = self._good_instance_inputs()
        receipt = build_instance_receipt(
            selection_receipt_payload=selected,
            catalog_payload=cat,
            route_receipt_payload=route,
            applicability_receipt_payload=applicability,
            parameters={"profile": {"count": 2, "unknown": True}},
            builder_receipts=[builder],
            generated_artifacts=[artifact],
            unresolved_placeholders=["title"],
            validator_receipts=[],
        )

        self.assertEqual("blocked", receipt["status"])
        self.assertTrue(any(item.startswith("unknown_parameter") for item in receipt["findings"]))
        self.assertIn("unresolved_placeholder:title", receipt["findings"])
        self.assertIn("validator_receipt_inventory_mismatch", receipt["findings"])

    def test_forged_instance_fingerprint_and_native_identity_are_rejected(self) -> None:
        cat, selected, route, applicability, builder, validator, artifact = self._good_instance_inputs()
        current = build_instance_receipt(
            selection_receipt_payload=selected,
            catalog_payload=cat,
            route_receipt_payload=route,
            applicability_receipt_payload=applicability,
            parameters={"profile": {"count": 2}},
            builder_receipts=[builder],
            generated_artifacts=[artifact],
            unresolved_placeholders=[],
            validator_receipts=[validator],
        )

        forged_fingerprint = copy.deepcopy(current)
        forged_fingerprint["instance_fingerprint"] = sha256_identity({"forged": True})
        forged_fingerprint = reseal_receipt(forged_fingerprint, "template-instance")
        with self.assertRaises(TemplatePackError) as caught:
            validate_instance_receipt(forged_fingerprint, selected, cat)
        self.assertIn("instance_fingerprint_mismatch", {row.code for row in caught.exception.findings})

        forged_builder = copy.deepcopy(current)
        forged_nested = copy.deepcopy(forged_builder["builder_receipts"][0])
        forged_nested["builder_id"] = "builder:unrelated"
        forged_nested = reseal_receipt(forged_nested, "template-builder")
        forged_builder["builder_receipts"] = [forged_nested]
        fingerprint_payload = {
            "selection_receipt_hash": selected["receipt_hash"],
            "catalog_digest": cat["catalog_digest"],
            "selected_template_ids": ["profile"],
            "parameters": forged_builder["parameters"],
            "builder_receipt_hashes": [forged_nested["receipt_hash"]],
            "generated_artifacts": forged_builder["generated_artifacts"],
            "validator_receipt_hashes": [validator["receipt_hash"]],
        }
        forged_builder["instance_fingerprint"] = sha256_identity(fingerprint_payload)
        forged_builder = reseal_receipt(forged_builder, "template-instance")
        with self.assertRaises(TemplatePackError) as caught:
            validate_instance_receipt(forged_builder, selected, cat)
        self.assertIn("builder_identity_mismatch", {row.code for row in caught.exception.findings})

    def test_content_component_map_excludes_runtime_outputs(self) -> None:
        cat = catalog(manifest("profile"))
        components = template_content_components(cat)

        self.assertIn("template_catalog", components)
        self.assertIn("manifest:profile", components)
        self.assertIn("builder:builder:profile", components)
        self.assertIn("validator:validator:profile", components)
        self.assertIn("prompt:prompt:profile", components)
        self.assertFalse(any("receipt" in key or "task" in key or "progress" in key for key in components))


@unittest.skipIf(jsonschema is None, "jsonschema is not installed")
class TemplateProtocolSchemaParityTests(unittest.TestCase):
    def test_schema_accepts_every_runtime_accepted_record_kind(self) -> None:
        protocol_schema = json.loads(
            (
                ROOT
                / ".agents"
                / "skills"
                / "skillguard"
                / "assets"
                / "schemas"
                / "skillguard_template_pack_protocol_v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        item = manifest("profile")
        cat = catalog(item)
        selected, route, applicability = selection(cat, {"profile"})
        builder = item["builder"]
        validator = item["validators"][0]
        builder_receipt = seal_builder_receipt(
            {
                "template_id": "profile",
                "manifest_digest": item["manifest_digest"],
                "builder_id": builder["builder_id"],
                "builder_content_hash": builder["content_hash"],
                "status": "passed",
                "claim_boundary": "Builder receipt only.",
            }
        )
        validator_receipt = seal_validator_receipt(
            {
                "template_id": "profile",
                "manifest_digest": item["manifest_digest"],
                "validator_id": validator["validator_id"],
                "validator_content_hash": validator["content_hash"],
                "check_id": validator["check_id"],
                "status": "passed",
                "claim_boundary": "Validator receipt only.",
            }
        )
        instance = build_instance_receipt(
            selection_receipt_payload=selected,
            catalog_payload=cat,
            route_receipt_payload=route,
            applicability_receipt_payload=applicability,
            parameters={"profile": {"count": 1}},
            builder_receipts=[builder_receipt],
            generated_artifacts=[
                {
                    "template_id": "profile",
                    "manifest_digest": item["manifest_digest"],
                    "artifact_id": "artifact:profile",
                    "relative_path": "generated/profile.json",
                    "sha256": sha256_identity({"generated": "profile"}),
                }
            ],
            unresolved_placeholders=[],
            validator_receipts=[validator_receipt],
        )

        validator_engine = jsonschema.Draft202012Validator(protocol_schema)
        for payload in (item, cat, route, applicability, selected, instance):
            with self.subTest(schema_version=payload["schema_version"]):
                self.assertEqual([], list(validator_engine.iter_errors(payload)))

    def test_schema_and_runtime_both_reject_unknown_manifest_fields(self) -> None:
        protocol_schema = json.loads(
            (
                ROOT
                / ".agents"
                / "skills"
                / "skillguard"
                / "assets"
                / "schemas"
                / "skillguard_template_pack_protocol_v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        payload = manifest("profile")
        payload["unknown_field"] = True
        self.assertTrue(list(jsonschema.Draft202012Validator(protocol_schema).iter_errors(payload)))
        with self.assertRaises(TemplatePackError):
            validate_template_manifest(payload)


if __name__ == "__main__":
    unittest.main()
