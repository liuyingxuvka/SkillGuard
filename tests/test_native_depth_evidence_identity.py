from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".agents" / "skills" / "skillguard" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from skillguard_v2.contract_compiler import canonical_hash  # noqa: E402
from skillguard_v2.native_evidence_identity import (  # noqa: E402
    NATIVE_OBSERVATION_LOCATOR_SCHEMA,
    NativeEvidenceIdentityError,
    validate_identifier,
    validate_native_observation_locator,
)


class NativeEvidenceIdentityTests(unittest.TestCase):
    def test_locator_binds_exact_target_native_content(self) -> None:
        content = {"status": "passed", "count": 3}
        receipt = {
            "observations": [
                {
                    "native_object_id": "object:thermal-envelope",
                    "observation_origin": "native_runtime",
                    "target_obligation_ids": ["obligation:declared-check-current"],
                    "content": content,
                }
            ]
        }
        projection = {
            "schema_version": NATIVE_OBSERVATION_LOCATOR_SCHEMA,
            "locator_type": "json_pointer.v1",
            "resolver_owner_id": "physicsguard",
            "native_object_id": "object:thermal-envelope",
            "native_coordinate": "/observations/0/content",
            "content_sha256": canonical_hash(content),
        }
        locator = {
            **projection,
            "locator_fingerprint": canonical_hash(projection),
        }
        validated = validate_native_observation_locator(
            locator,
            receipt=receipt,
            native_owner_id="physicsguard",
            target_obligation_ids=["obligation:declared-check-current"],
        )
        self.assertEqual(locator, validated)

    def test_generic_or_ordinal_identifiers_are_rejected(self) -> None:
        for value in ("default", "obligation:1", "step-2"):
            with self.subTest(value=value):
                with self.assertRaises(NativeEvidenceIdentityError):
                    validate_identifier(value, code_prefix="fixture")

    def test_locator_does_not_contain_guard_purpose_semantics(self) -> None:
        fields = {
            "schema_version",
            "locator_type",
            "resolver_owner_id",
            "native_object_id",
            "native_coordinate",
            "content_sha256",
            "locator_fingerprint",
        }
        self.assertFalse(
            fields
            & {
                "purpose_contract_identity",
                "protected_failure_claim_ids",
                "semantic_obligation_ids",
                "native_finding_identity",
            }
        )


if __name__ == "__main__":
    unittest.main()
