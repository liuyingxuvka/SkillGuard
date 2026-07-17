"""Validate target-owned template projections and seal neutral SkillGuard records.

The target Guard owns route meaning, applicability, builders, validators, and
fixtures.  This module only checks the fixed interchange shape, binds content
identities, and creates the two neutral receipts consumed by SkillGuard's
generic selector.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any, Mapping

from .template_packs import (
    TemplatePackError,
    TemplatePackFinding,
    seal_applicability_receipt,
    seal_native_route_receipt,
    seal_template_catalog,
    seal_template_manifest,
    validate_applicability_receipt,
    validate_native_route_receipt,
    validate_template_catalog,
)


TARGET_TEMPLATE_PROJECTION_SCHEMA = "skillguard.target_template_projection.v1"
PROJECTION_FIELDS = frozenset(
    {
        "schema_version",
        "target_id",
        "native_owner_id",
        "family_id",
        "route_id",
        "request_fingerprint",
        "catalog",
        "applicability_results",
        "claim_boundary",
    }
)
APPLICABILITY_RESULT_FIELDS = frozenset(
    {
        "template_id",
        "eligible",
        "predicate_evidence_ids",
        "forbidden_clearance_evidence_ids",
        "reasons",
    }
)
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True)
class TargetTemplateRecords:
    catalog: Mapping[str, Any]
    native_route_receipt: Mapping[str, Any]
    applicability_receipt: Mapping[str, Any]


def _finding(code: str, path: str, message: str) -> TemplatePackFinding:
    return TemplatePackFinding(code, path, message)


def _required_text(
    row: Mapping[str, Any],
    field: str,
    findings: list[TemplatePackFinding],
) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        findings.append(_finding("target_projection_required_text", f"$.{field}", "non-empty string required"))
        return ""
    return value.strip()


def _string_list(
    value: object,
    path: str,
    findings: list[TemplatePackFinding],
) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        findings.append(_finding("target_projection_string_list_invalid", path, "string array required"))
        return []
    if len(value) != len(set(value)):
        findings.append(_finding("target_projection_string_list_duplicate", path, "values must be unique"))
    return list(value)


def compile_target_template_projection(payload: object) -> TargetTemplateRecords:
    """Compile one target-authored projection into current neutral records.

    Canonical sealing is identity plumbing, not domain selection.  Eligibility
    rows are accepted only when their inventory exactly equals the target's
    declared catalog; SkillGuard never invents or re-scores a candidate.
    """

    findings: list[TemplatePackFinding] = []
    if not isinstance(payload, Mapping):
        raise TemplatePackError((_finding("target_projection_expected_object", "$", "object required"),))
    row = copy.deepcopy(dict(payload))
    for field in sorted(set(row) - PROJECTION_FIELDS):
        findings.append(_finding("target_projection_unknown_field", f"$.{field}", "field is not declared"))
    if row.get("schema_version") != TARGET_TEMPLATE_PROJECTION_SCHEMA:
        findings.append(
            _finding(
                "target_projection_schema_mismatch",
                "$.schema_version",
                TARGET_TEMPLATE_PROJECTION_SCHEMA,
            )
        )
    target_id = _required_text(row, "target_id", findings)
    owner_id = _required_text(row, "native_owner_id", findings)
    family_id = _required_text(row, "family_id", findings)
    route_id = _required_text(row, "route_id", findings)
    request_fingerprint = _required_text(row, "request_fingerprint", findings)
    if request_fingerprint and not SHA256_RE.fullmatch(request_fingerprint):
        findings.append(
            _finding(
                "target_projection_request_fingerprint_invalid",
                "$.request_fingerprint",
                request_fingerprint,
            )
        )
    claim_boundary = _required_text(row, "claim_boundary", findings)

    raw_catalog = row.get("catalog")
    if not isinstance(raw_catalog, Mapping):
        findings.append(_finding("target_projection_catalog_invalid", "$.catalog", "object required"))
        raw_catalog = {}
    catalog_spec = copy.deepcopy(dict(raw_catalog))
    raw_templates = catalog_spec.get("templates")
    if not isinstance(raw_templates, list):
        findings.append(_finding("target_projection_templates_invalid", "$.catalog.templates", "array required"))
        raw_templates = []
    sealed_templates: list[dict[str, Any]] = []
    for index, manifest in enumerate(raw_templates):
        if not isinstance(manifest, Mapping):
            findings.append(
                _finding(
                    "target_projection_manifest_invalid",
                    f"$.catalog.templates[{index}]",
                    "object required",
                )
            )
            continue
        manifest_row = copy.deepcopy(dict(manifest))
        sealed_templates.append(
            manifest_row if "manifest_digest" in manifest_row else seal_template_manifest(manifest_row)
        )
    catalog_spec["templates"] = sealed_templates
    if catalog_spec.get("native_owner_id") != owner_id:
        findings.append(_finding("target_projection_owner_mismatch", "$.catalog.native_owner_id", owner_id))
    if catalog_spec.get("family_id") != family_id:
        findings.append(_finding("target_projection_family_mismatch", "$.catalog.family_id", family_id))

    raw_results = row.get("applicability_results")
    if not isinstance(raw_results, list):
        findings.append(
            _finding(
                "target_projection_applicability_invalid",
                "$.applicability_results",
                "array required",
            )
        )
        raw_results = []
    normalized_results: list[dict[str, Any]] = []
    for index, result in enumerate(raw_results):
        path = f"$.applicability_results[{index}]"
        if not isinstance(result, Mapping):
            findings.append(_finding("target_projection_result_invalid", path, "object required"))
            continue
        result_row = copy.deepcopy(dict(result))
        for field in sorted(set(result_row) - APPLICABILITY_RESULT_FIELDS):
            findings.append(_finding("target_projection_result_unknown_field", f"{path}.{field}", "field is not declared"))
        template_id = result_row.get("template_id")
        if not isinstance(template_id, str) or not template_id:
            findings.append(_finding("target_projection_result_template_invalid", f"{path}.template_id", "non-empty string required"))
            template_id = ""
        if not isinstance(result_row.get("eligible"), bool):
            findings.append(_finding("target_projection_result_eligible_invalid", f"{path}.eligible", "boolean required"))
        predicate_ids = _string_list(result_row.get("predicate_evidence_ids"), f"{path}.predicate_evidence_ids", findings)
        clearance_ids = _string_list(
            result_row.get("forbidden_clearance_evidence_ids"),
            f"{path}.forbidden_clearance_evidence_ids",
            findings,
        )
        reasons = _string_list(result_row.get("reasons"), f"{path}.reasons", findings)
        normalized_results.append(
            {
                "template_id": template_id,
                "eligible": result_row.get("eligible"),
                "predicate_evidence_ids": predicate_ids,
                "forbidden_clearance_evidence_ids": clearance_ids,
                "reasons": reasons,
            }
        )
    if findings:
        raise TemplatePackError(findings)

    catalog_payload = (
        catalog_spec if "catalog_digest" in catalog_spec else seal_template_catalog(catalog_spec)
    )
    catalog = validate_template_catalog(catalog_payload)
    manifest_index = catalog.manifest_index()
    result_ids = [str(item["template_id"]) for item in normalized_results]
    if len(result_ids) != len(set(result_ids)) or set(result_ids) != set(manifest_index):
        raise TemplatePackError(
            (
                _finding(
                    "target_projection_candidate_inventory_mismatch",
                    "$.applicability_results",
                    "results must equal the target catalog inventory exactly once",
                ),
            )
        )

    route_payload = seal_native_route_receipt(
        {
            "target_id": target_id,
            "native_owner_id": owner_id,
            "family_id": family_id,
            "route_id": route_id,
            "request_fingerprint": request_fingerprint,
            "catalog_id": catalog.payload["catalog_id"],
            "status": "passed",
            "claim_boundary": claim_boundary,
        }
    )
    route = validate_native_route_receipt(route_payload, catalog)
    applicability_payload = seal_applicability_receipt(
        {
            "native_owner_id": owner_id,
            "family_id": family_id,
            "request_fingerprint": request_fingerprint,
            "catalog_digest": catalog.digest,
            "route_receipt_hash": route["receipt_hash"],
            "results": [
                {
                    **item,
                    "manifest_digest": manifest_index[str(item["template_id"])].digest,
                }
                for item in normalized_results
            ],
            "claim_boundary": claim_boundary,
        }
    )
    applicability = validate_applicability_receipt(applicability_payload, catalog, route)
    return TargetTemplateRecords(catalog.payload, route, applicability)


__all__ = [
    "APPLICABILITY_RESULT_FIELDS",
    "PROJECTION_FIELDS",
    "TARGET_TEMPLATE_PROJECTION_SCHEMA",
    "TargetTemplateRecords",
    "compile_target_template_projection",
]
