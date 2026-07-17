"""Target-owned validated Template Pack supervision for SkillGuard V2.

This module is deliberately domain-neutral.  A target Guard owns catalog
meaning, route selection, applicability, builders, validators, fixtures, and
claim boundaries.  SkillGuard validates identities, reconciles the complete
candidate set, blocks ambiguity, and emits immutable selection/instance
receipts.  These records are compiler/runtime inputs and evidence; they are
never a fourth contract authority beside the current contract-source,
compiled-contract, and exact check-manifest trio.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Iterable, Mapping, Sequence


TEMPLATE_MANIFEST_SCHEMA = "skillguard.template_manifest.v1"
TEMPLATE_CATALOG_SCHEMA = "skillguard.template_catalog.v1"
NATIVE_ROUTE_RECEIPT_SCHEMA = "skillguard.native_route_receipt.v1"
APPLICABILITY_RECEIPT_SCHEMA = "skillguard.template_applicability_receipt.v1"
SELECTION_RECEIPT_SCHEMA = "skillguard.template_selection_receipt.v1"
INSTANCE_RECEIPT_SCHEMA = "skillguard.template_instance_receipt.v1"

TEMPLATE_KINDS = frozenset({"base", "profile", "fragment"})
SELECTION_DISPOSITIONS = frozenset(
    {
        "base_no_match",
        "single_selected",
        "composed",
        "strictly_dominated_selection",
        "ambiguous_template_selection",
    }
)
RECEIPT_STATUSES = frozenset({"selected", "blocked"})
VALIDATOR_STATUSES = frozenset({"passed", "failed", "blocked", "skipped", "stale", "not_run"})
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$")
PLACEHOLDER_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_.-]*)\}")

MANIFEST_FIELDS = frozenset(
    {
        "schema_version",
        "template_id",
        "revision",
        "template_kind",
        "native_owner_id",
        "family_id",
        "route_ids",
        "applicability_predicate_ids",
        "forbidden_condition_ids",
        "dependencies",
        "compatible_with",
        "conflicts_with",
        "dominates_template_ids",
        "composable",
        "composition_order",
        "is_validated_base",
        "field_ownership",
        "parameter_schema",
        "artifacts",
        "builder",
        "validators",
        "prompt_fragments",
        "protected_failure_ids",
        "fixtures",
        "claim_boundary",
        "manifest_digest",
    }
)
CATALOG_FIELDS = frozenset(
    {
        "schema_version",
        "catalog_id",
        "revision",
        "native_owner_id",
        "family_id",
        "base_template_id",
        "templates",
        "harvest_policy",
        "claim_boundary",
        "catalog_digest",
    }
)
ROUTE_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "target_id",
        "native_owner_id",
        "family_id",
        "route_id",
        "request_fingerprint",
        "catalog_id",
        "status",
        "claim_boundary",
        "receipt_id",
        "receipt_hash",
    }
)
APPLICABILITY_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "native_owner_id",
        "family_id",
        "request_fingerprint",
        "catalog_digest",
        "route_receipt_hash",
        "results",
        "claim_boundary",
        "receipt_id",
        "receipt_hash",
    }
)
SELECTION_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "status",
        "disposition",
        "request_fingerprint",
        "catalog_digest",
        "route_receipt_hash",
        "applicability_receipt_hash",
        "candidate_accounting",
        "selected_template_ids",
        "composition_order",
        "field_owner_map",
        "findings",
        "harvest_review_required",
        "claim_boundary",
        "receipt_id",
        "receipt_hash",
    }
)
INSTANCE_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "status",
        "selection_receipt_hash",
        "catalog_digest",
        "selected_template_ids",
        "parameters",
        "builder_receipts",
        "generated_artifacts",
        "unresolved_placeholders",
        "validator_receipts",
        "findings",
        "instance_fingerprint",
        "claim_boundary",
        "receipt_id",
        "receipt_hash",
    }
)


@dataclass(frozen=True)
class TemplatePackFinding:
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


class TemplatePackError(ValueError):
    def __init__(self, findings: Iterable[TemplatePackFinding]):
        self.findings = tuple(findings)
        super().__init__(
            "; ".join(f"{row.code}@{row.path}" for row in self.findings)
            or "template pack validation failed"
        )


@dataclass(frozen=True)
class ValidatedManifest:
    payload: Mapping[str, Any]

    @property
    def template_id(self) -> str:
        return str(self.payload["template_id"])

    @property
    def digest(self) -> str:
        return str(self.payload["manifest_digest"])


@dataclass(frozen=True)
class ValidatedCatalog:
    payload: Mapping[str, Any]
    manifests: tuple[ValidatedManifest, ...]

    @property
    def digest(self) -> str:
        return str(self.payload["catalog_digest"])

    def manifest_index(self) -> dict[str, ValidatedManifest]:
        return {row.template_id: row for row in self.manifests}


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha256_identity(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _copy_mapping(value: object, path: str, findings: list[TemplatePackFinding]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        findings.append(TemplatePackFinding("expected_object", path, "value must be an object"))
        return {}
    try:
        return copy.deepcopy(dict(value))
    except Exception as exc:  # pragma: no cover - unusual custom mappings
        findings.append(TemplatePackFinding("non_json_object", path, type(exc).__name__))
        return {}


def _rows(value: object, path: str, findings: list[TemplatePackFinding]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        findings.append(TemplatePackFinding("expected_array", path, "value must be an array"))
        return []
    return [_copy_mapping(row, f"{path}[{index}]", findings) for index, row in enumerate(value)]


def _reject_unknown(payload: Mapping[str, Any], allowed: frozenset[str], path: str, findings: list[TemplatePackFinding]) -> None:
    for key in sorted(set(payload) - allowed):
        findings.append(TemplatePackFinding("unknown_field", f"{path}.{key}", "field is not declared by the current schema"))


def _required_text(payload: Mapping[str, Any], key: str, path: str, findings: list[TemplatePackFinding]) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        findings.append(TemplatePackFinding("required_text_missing", f"{path}.{key}", "required non-empty string"))
        return ""
    return value.strip()


def _id_text(payload: Mapping[str, Any], key: str, path: str, findings: list[TemplatePackFinding]) -> str:
    value = _required_text(payload, key, path, findings)
    if value and not ID_RE.fullmatch(value):
        findings.append(TemplatePackFinding("invalid_id", f"{path}.{key}", value))
    return value


def _string_list(
    value: object,
    path: str,
    findings: list[TemplatePackFinding],
    *,
    nonempty: bool = False,
) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        findings.append(TemplatePackFinding("expected_string_array", path, "array items must be non-empty strings"))
        return ()
    rows = tuple(item.strip() for item in value)
    if nonempty and not rows:
        findings.append(TemplatePackFinding("empty_array", path, "at least one item is required"))
    if len(rows) != len(set(rows)):
        findings.append(TemplatePackFinding("duplicate_array_item", path, "array items must be unique"))
    return rows


def _boolean(payload: Mapping[str, Any], key: str, path: str, findings: list[TemplatePackFinding]) -> bool:
    value = payload.get(key)
    if not isinstance(value, bool):
        findings.append(TemplatePackFinding("expected_boolean", f"{path}.{key}", "value must be true or false"))
        return False
    return value


def _positive_int(payload: Mapping[str, Any], key: str, path: str, findings: list[TemplatePackFinding]) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        findings.append(TemplatePackFinding("expected_nonnegative_integer", f"{path}.{key}", str(value)))
        return 0
    return value


def _portable_relative(value: str) -> bool:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    return bool(value) and not path.is_absolute() and ".." not in path.parts and not re.match(r"^[A-Za-z]:", value)


def _semantic_payload(payload: Mapping[str, Any], *identity_fields: str) -> dict[str, Any]:
    return {key: copy.deepcopy(value) for key, value in payload.items() if key not in set(identity_fields)}


def _canonical_manifest_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    normalized = _semantic_payload(payload, "manifest_digest")
    for key in (
        "route_ids",
        "applicability_predicate_ids",
        "forbidden_condition_ids",
        "dependencies",
        "compatible_with",
        "conflicts_with",
        "dominates_template_ids",
        "field_ownership",
        "protected_failure_ids",
    ):
        if isinstance(normalized.get(key), list):
            normalized[key] = sorted(normalized[key])
    parameter_schema = normalized.get("parameter_schema")
    if isinstance(parameter_schema, dict) and isinstance(parameter_schema.get("required"), list):
        parameter_schema["required"] = sorted(parameter_schema["required"])
    for key, identity in (
        ("artifacts", "artifact_id"),
        ("validators", "validator_id"),
        ("prompt_fragments", "fragment_id"),
    ):
        if isinstance(normalized.get(key), list):
            normalized[key] = sorted(normalized[key], key=lambda item: str(item.get(identity, "")))
    fixtures = normalized.get("fixtures")
    if isinstance(fixtures, dict):
        for key in ("known_good_ids", "ambiguity_ids", "stale_ids"):
            if isinstance(fixtures.get(key), list):
                fixtures[key] = sorted(fixtures[key])
        known_bad = fixtures.get("known_bad_by_failure")
        if isinstance(known_bad, dict):
            for key, value in known_bad.items():
                if isinstance(value, list):
                    known_bad[key] = sorted(value)
    return normalized


def _seal_receipt(payload: Mapping[str, Any], *, prefix: str) -> dict[str, Any]:
    semantic = _semantic_payload(payload, "receipt_id", "receipt_hash")
    receipt_hash = sha256_identity(semantic)
    return {
        **semantic,
        "receipt_id": f"{prefix}-{receipt_hash.removeprefix('sha256:')[:24]}",
        "receipt_hash": receipt_hash,
    }


def _validate_sealed_receipt(payload: Mapping[str, Any], *, prefix: str, path: str, findings: list[TemplatePackFinding]) -> None:
    expected = _seal_receipt(payload, prefix=prefix)
    if payload.get("receipt_hash") != expected["receipt_hash"]:
        findings.append(TemplatePackFinding("receipt_hash_mismatch", f"{path}.receipt_hash", str(payload.get("receipt_hash", ""))))
    if payload.get("receipt_id") != expected["receipt_id"]:
        findings.append(TemplatePackFinding("receipt_id_mismatch", f"{path}.receipt_id", str(payload.get("receipt_id", ""))))


def _validate_parameter_schema(value: object, path: str, findings: list[TemplatePackFinding]) -> dict[str, Any]:
    schema = _copy_mapping(value, path, findings)
    allowed = frozenset({"type", "properties", "required", "additionalProperties"})
    _reject_unknown(schema, allowed, path, findings)
    if schema.get("type") != "object":
        findings.append(TemplatePackFinding("parameter_schema_type_invalid", f"{path}.type", "type must be object"))
    if schema.get("additionalProperties") is not False:
        findings.append(TemplatePackFinding("parameter_schema_open", f"{path}.additionalProperties", "must be false"))
    properties = _copy_mapping(schema.get("properties"), f"{path}.properties", findings)
    required = _string_list(schema.get("required"), f"{path}.required", findings)
    for name in required:
        if name not in properties:
            findings.append(TemplatePackFinding("required_parameter_unknown", f"{path}.required", name))
    property_allowed = frozenset({"type", "enum", "default", "pattern", "minimum", "maximum"})
    allowed_types = {"string", "integer", "number", "boolean", "array", "object"}
    for name, raw in properties.items():
        property_path = f"{path}.properties.{name}"
        row = _copy_mapping(raw, property_path, findings)
        _reject_unknown(row, property_allowed, property_path, findings)
        if row.get("type") not in allowed_types:
            findings.append(TemplatePackFinding("parameter_type_invalid", f"{property_path}.type", str(row.get("type"))))
        if "enum" in row and (not isinstance(row["enum"], list) or not row["enum"]):
            findings.append(TemplatePackFinding("parameter_enum_invalid", f"{property_path}.enum", "enum must be a non-empty array"))
        for bound in ("minimum", "maximum"):
            if bound in row and (not isinstance(row[bound], (int, float)) or isinstance(row[bound], bool) or not math.isfinite(float(row[bound]))):
                findings.append(TemplatePackFinding("parameter_bound_invalid", f"{property_path}.{bound}", str(row[bound])))
    return schema


def _validate_fixture_contract(value: object, failures: tuple[str, ...], path: str, findings: list[TemplatePackFinding]) -> None:
    fixture = _copy_mapping(value, path, findings)
    allowed = frozenset({"known_good_ids", "known_bad_by_failure", "ambiguity_ids", "stale_ids"})
    _reject_unknown(fixture, allowed, path, findings)
    _string_list(fixture.get("known_good_ids"), f"{path}.known_good_ids", findings, nonempty=True)
    _string_list(fixture.get("ambiguity_ids"), f"{path}.ambiguity_ids", findings)
    _string_list(fixture.get("stale_ids"), f"{path}.stale_ids", findings)
    bad = _copy_mapping(fixture.get("known_bad_by_failure"), f"{path}.known_bad_by_failure", findings)
    if set(bad) != set(failures):
        findings.append(TemplatePackFinding("known_bad_failure_inventory_mismatch", f"{path}.known_bad_by_failure", "keys must equal protected_failure_ids"))
    for failure_id, ids in bad.items():
        _string_list(ids, f"{path}.known_bad_by_failure.{failure_id}", findings, nonempty=True)


def manifest_digest(payload: Mapping[str, Any]) -> str:
    return sha256_identity(_canonical_manifest_payload(payload))


def seal_template_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    semantic = _canonical_manifest_payload(payload)
    return {**semantic, "manifest_digest": sha256_identity(semantic)}


def validate_template_manifest(payload: object) -> ValidatedManifest:
    findings: list[TemplatePackFinding] = []
    row = _copy_mapping(payload, "$", findings)
    _reject_unknown(row, MANIFEST_FIELDS, "$", findings)
    if row.get("schema_version") != TEMPLATE_MANIFEST_SCHEMA:
        findings.append(TemplatePackFinding("manifest_schema_mismatch", "$.schema_version", TEMPLATE_MANIFEST_SCHEMA))
    _id_text(row, "template_id", "$", findings)
    _required_text(row, "revision", "$", findings)
    kind = _required_text(row, "template_kind", "$", findings)
    if kind and kind not in TEMPLATE_KINDS:
        findings.append(TemplatePackFinding("template_kind_invalid", "$.template_kind", kind))
    _id_text(row, "native_owner_id", "$", findings)
    _id_text(row, "family_id", "$", findings)
    _string_list(row.get("route_ids"), "$.route_ids", findings, nonempty=True)
    _string_list(row.get("applicability_predicate_ids"), "$.applicability_predicate_ids", findings, nonempty=True)
    _string_list(row.get("forbidden_condition_ids"), "$.forbidden_condition_ids", findings)
    for key in ("dependencies", "compatible_with", "conflicts_with", "dominates_template_ids"):
        _string_list(row.get(key), f"$.{key}", findings)
    composable = _boolean(row, "composable", "$", findings)
    _positive_int(row, "composition_order", "$", findings)
    is_base = _boolean(row, "is_validated_base", "$", findings)
    fields = _string_list(row.get("field_ownership"), "$.field_ownership", findings, nonempty=True)
    if is_base and kind != "base":
        findings.append(TemplatePackFinding("base_kind_mismatch", "$.template_kind", "validated base must use template_kind=base"))
    if kind == "base" and not is_base:
        findings.append(TemplatePackFinding("base_flag_missing", "$.is_validated_base", "base kind must be validated base"))
    if is_base and composable:
        findings.append(TemplatePackFinding("base_cannot_compose", "$.composable", "validated base is fallback-only"))
    _validate_parameter_schema(row.get("parameter_schema"), "$.parameter_schema", findings)

    artifact_rows = _rows(row.get("artifacts"), "$.artifacts", findings)
    artifact_ids: list[str] = []
    for index, artifact in enumerate(artifact_rows):
        path = f"$.artifacts[{index}]"
        _reject_unknown(artifact, frozenset({"artifact_id", "path_template", "content_template_hash"}), path, findings)
        artifact_ids.append(_id_text(artifact, "artifact_id", path, findings))
        path_template = _required_text(artifact, "path_template", path, findings)
        if path_template and not _portable_relative(path_template):
            findings.append(TemplatePackFinding("artifact_path_not_portable", f"{path}.path_template", path_template))
        content_hash = _required_text(artifact, "content_template_hash", path, findings)
        if content_hash and not SHA256_RE.fullmatch(content_hash):
            findings.append(TemplatePackFinding("content_template_hash_invalid", f"{path}.content_template_hash", content_hash))
    if not artifact_rows:
        findings.append(TemplatePackFinding("artifact_inventory_empty", "$.artifacts", "at least one generated artifact is required"))
    if len(artifact_ids) != len(set(artifact_ids)):
        findings.append(TemplatePackFinding("duplicate_artifact_id", "$.artifacts", "artifact ids must be unique"))

    builder = _copy_mapping(row.get("builder"), "$.builder", findings)
    _reject_unknown(builder, frozenset({"builder_id", "entrypoint", "content_hash"}), "$.builder", findings)
    _id_text(builder, "builder_id", "$.builder", findings)
    entrypoint = _required_text(builder, "entrypoint", "$.builder", findings)
    if entrypoint and (re.match(r"^[A-Za-z]:", entrypoint) or entrypoint.startswith(("/", "\\"))):
        findings.append(TemplatePackFinding("builder_entrypoint_not_portable", "$.builder.entrypoint", entrypoint))
    builder_hash = _required_text(builder, "content_hash", "$.builder", findings)
    if builder_hash and not SHA256_RE.fullmatch(builder_hash):
        findings.append(TemplatePackFinding("builder_content_hash_invalid", "$.builder.content_hash", builder_hash))

    validator_rows = _rows(row.get("validators"), "$.validators", findings)
    validator_ids: list[str] = []
    for index, validator in enumerate(validator_rows):
        path = f"$.validators[{index}]"
        _reject_unknown(validator, frozenset({"validator_id", "check_id", "evidence_domain", "content_hash"}), path, findings)
        validator_ids.append(_id_text(validator, "validator_id", path, findings))
        _id_text(validator, "check_id", path, findings)
        _id_text(validator, "evidence_domain", path, findings)
        content_hash = _required_text(validator, "content_hash", path, findings)
        if content_hash and not SHA256_RE.fullmatch(content_hash):
            findings.append(TemplatePackFinding("validator_content_hash_invalid", f"{path}.content_hash", content_hash))
    if not validator_rows:
        findings.append(TemplatePackFinding("validator_inventory_empty", "$.validators", "native validators are required"))
    if len(validator_ids) != len(set(validator_ids)):
        findings.append(TemplatePackFinding("duplicate_validator_id", "$.validators", "validator ids must be unique"))

    prompt_rows = _rows(row.get("prompt_fragments"), "$.prompt_fragments", findings)
    prompt_ids: list[str] = []
    for index, prompt in enumerate(prompt_rows):
        path = f"$.prompt_fragments[{index}]"
        _reject_unknown(prompt, frozenset({"fragment_id", "content_hash"}), path, findings)
        prompt_ids.append(_id_text(prompt, "fragment_id", path, findings))
        content_hash = _required_text(prompt, "content_hash", path, findings)
        if content_hash and not SHA256_RE.fullmatch(content_hash):
            findings.append(TemplatePackFinding("prompt_content_hash_invalid", f"{path}.content_hash", content_hash))
    if len(prompt_ids) != len(set(prompt_ids)):
        findings.append(TemplatePackFinding("duplicate_prompt_fragment_id", "$.prompt_fragments", "fragment ids must be unique"))

    failures = _string_list(row.get("protected_failure_ids"), "$.protected_failure_ids", findings, nonempty=True)
    _validate_fixture_contract(row.get("fixtures"), failures, "$.fixtures", findings)
    _required_text(row, "claim_boundary", "$", findings)
    observed_digest = _required_text(row, "manifest_digest", "$", findings)
    expected_digest = manifest_digest(row)
    if observed_digest and observed_digest != expected_digest:
        findings.append(TemplatePackFinding("manifest_digest_mismatch", "$.manifest_digest", f"expected {expected_digest}"))
    if findings:
        raise TemplatePackError(findings)
    # Canonicalize sets for stable downstream receipt projection without using
    # lexical order as a selection winner.
    normalized = {
        **_canonical_manifest_payload(row),
        "manifest_digest": expected_digest,
    }
    return ValidatedManifest(normalized)


def catalog_digest(payload: Mapping[str, Any]) -> str:
    semantic = _semantic_payload(payload, "catalog_digest")
    if isinstance(semantic.get("templates"), list):
        semantic["templates"] = sorted(semantic["templates"], key=lambda item: str(item.get("template_id", "")))
    return sha256_identity(semantic)


def seal_template_catalog(payload: Mapping[str, Any]) -> dict[str, Any]:
    semantic = _semantic_payload(payload, "catalog_digest")
    if isinstance(semantic.get("templates"), list):
        semantic["templates"] = sorted(semantic["templates"], key=lambda item: str(item.get("template_id", "")))
    return {**semantic, "catalog_digest": sha256_identity(semantic)}


def _find_cycles(graph: Mapping[str, Sequence[str]]) -> tuple[tuple[str, ...], ...]:
    visiting: list[str] = []
    visited: set[str] = set()
    cycles: set[tuple[str, ...]] = set()

    def visit(node: str) -> None:
        if node in visiting:
            start = visiting.index(node)
            cycles.add(tuple(visiting[start:] + [node]))
            return
        if node in visited:
            return
        visiting.append(node)
        for child in graph.get(node, ()):
            visit(child)
        visiting.pop()
        visited.add(node)

    for node in graph:
        visit(node)
    return tuple(sorted(cycles))


def validate_template_catalog(payload: object) -> ValidatedCatalog:
    findings: list[TemplatePackFinding] = []
    row = _copy_mapping(payload, "$", findings)
    _reject_unknown(row, CATALOG_FIELDS, "$", findings)
    if row.get("schema_version") != TEMPLATE_CATALOG_SCHEMA:
        findings.append(TemplatePackFinding("catalog_schema_mismatch", "$.schema_version", TEMPLATE_CATALOG_SCHEMA))
    _id_text(row, "catalog_id", "$", findings)
    _required_text(row, "revision", "$", findings)
    owner_id = _id_text(row, "native_owner_id", "$", findings)
    family_id = _id_text(row, "family_id", "$", findings)
    base_id = row.get("base_template_id")
    if not isinstance(base_id, str):
        findings.append(TemplatePackFinding("base_template_id_invalid", "$.base_template_id", "must be a string, possibly empty"))
        base_id = ""
    harvest = _copy_mapping(row.get("harvest_policy"), "$.harvest_policy", findings)
    _reject_unknown(harvest, frozenset({"required", "allowed_dispositions"}), "$.harvest_policy", findings)
    if harvest.get("required") is not True:
        findings.append(TemplatePackFinding("harvest_review_not_required", "$.harvest_policy.required", "must be true"))
    _string_list(harvest.get("allowed_dispositions"), "$.harvest_policy.allowed_dispositions", findings, nonempty=True)
    _required_text(row, "claim_boundary", "$", findings)

    raw_templates = _rows(row.get("templates"), "$.templates", findings)
    manifests: list[ValidatedManifest] = []
    for index, raw in enumerate(raw_templates):
        try:
            manifests.append(validate_template_manifest(raw))
        except TemplatePackError as exc:
            findings.extend(
                TemplatePackFinding(item.code, f"$.templates[{index}]{item.path.removeprefix('$')}", item.message)
                for item in exc.findings
            )
    if not manifests:
        findings.append(TemplatePackFinding("catalog_empty", "$.templates", "at least one current manifest is required"))
    ids = [item.template_id for item in manifests]
    if len(ids) != len(set(ids)):
        findings.append(TemplatePackFinding("duplicate_template_id", "$.templates", "template ids must be unique"))
    index = {item.template_id: item for item in manifests}
    bases = [item for item in manifests if item.payload["is_validated_base"]]
    if base_id:
        if base_id not in index:
            findings.append(TemplatePackFinding("base_template_missing", "$.base_template_id", base_id))
        elif not index[base_id].payload["is_validated_base"]:
            findings.append(TemplatePackFinding("base_template_not_validated", "$.base_template_id", base_id))
        if len(bases) != 1:
            findings.append(TemplatePackFinding("base_template_cardinality_invalid", "$.templates", "declared base requires exactly one base manifest"))
    elif bases:
        findings.append(TemplatePackFinding("undeclared_base_template", "$.base_template_id", "catalog base id is empty"))
    for manifest in manifests:
        path = f"$.templates[{manifest.template_id}]"
        if manifest.payload["native_owner_id"] != owner_id:
            findings.append(TemplatePackFinding("catalog_owner_mismatch", f"{path}.native_owner_id", manifest.template_id))
        if manifest.payload["family_id"] != family_id:
            findings.append(TemplatePackFinding("catalog_family_mismatch", f"{path}.family_id", manifest.template_id))
        for key in ("dependencies", "compatible_with", "conflicts_with", "dominates_template_ids"):
            for target in manifest.payload[key]:
                if target not in index:
                    findings.append(TemplatePackFinding("template_reference_unknown", f"{path}.{key}", target))
                if target == manifest.template_id:
                    findings.append(TemplatePackFinding("template_self_reference", f"{path}.{key}", target))
        for target in manifest.payload["compatible_with"]:
            if target in index and manifest.template_id not in index[target].payload["compatible_with"]:
                findings.append(TemplatePackFinding("compatibility_not_mutual", f"{path}.compatible_with", target))
        for target in manifest.payload["conflicts_with"]:
            if target in index and manifest.template_id not in index[target].payload["conflicts_with"]:
                findings.append(TemplatePackFinding("conflict_not_mutual", f"{path}.conflicts_with", target))
        overlap = set(manifest.payload["compatible_with"]) & set(manifest.payload["conflicts_with"])
        for target in sorted(overlap):
            findings.append(TemplatePackFinding("compatibility_conflict_contradiction", path, target))
    dependency_graph = {item.template_id: tuple(item.payload["dependencies"]) for item in manifests}
    for cycle in _find_cycles(dependency_graph):
        findings.append(TemplatePackFinding("dependency_cycle", "$.templates", " -> ".join(cycle)))
    dominance_graph = {item.template_id: tuple(item.payload["dominates_template_ids"]) for item in manifests}
    for cycle in _find_cycles(dominance_graph):
        findings.append(TemplatePackFinding("dominance_cycle", "$.templates", " -> ".join(cycle)))
    observed_digest = _required_text(row, "catalog_digest", "$", findings)
    expected_digest = catalog_digest(row)
    if observed_digest and observed_digest != expected_digest:
        findings.append(TemplatePackFinding("catalog_digest_mismatch", "$.catalog_digest", f"expected {expected_digest}"))
    if findings:
        raise TemplatePackError(findings)
    normalized = copy.deepcopy(row)
    normalized["templates"] = [item.payload for item in sorted(manifests, key=lambda item: item.template_id)]
    return ValidatedCatalog(normalized, tuple(sorted(manifests, key=lambda item: item.template_id)))


def seal_native_route_receipt(payload: Mapping[str, Any]) -> dict[str, Any]:
    return _seal_receipt({**payload, "schema_version": NATIVE_ROUTE_RECEIPT_SCHEMA}, prefix="native-route")


def validate_native_route_receipt(payload: object, catalog: ValidatedCatalog) -> dict[str, Any]:
    findings: list[TemplatePackFinding] = []
    row = _copy_mapping(payload, "$", findings)
    _reject_unknown(row, ROUTE_RECEIPT_FIELDS, "$", findings)
    if row.get("schema_version") != NATIVE_ROUTE_RECEIPT_SCHEMA:
        findings.append(TemplatePackFinding("route_receipt_schema_mismatch", "$.schema_version", NATIVE_ROUTE_RECEIPT_SCHEMA))
    for key in ("target_id", "native_owner_id", "family_id", "route_id", "catalog_id"):
        _id_text(row, key, "$", findings)
    request_fingerprint = _required_text(row, "request_fingerprint", "$", findings)
    if request_fingerprint and not SHA256_RE.fullmatch(request_fingerprint):
        findings.append(TemplatePackFinding("request_fingerprint_invalid", "$.request_fingerprint", request_fingerprint))
    if row.get("status") != "passed":
        findings.append(TemplatePackFinding("native_route_not_passed", "$.status", str(row.get("status"))))
    _required_text(row, "claim_boundary", "$", findings)
    if row.get("native_owner_id") != catalog.payload["native_owner_id"]:
        findings.append(TemplatePackFinding("native_route_owner_mismatch", "$.native_owner_id", str(row.get("native_owner_id"))))
    if row.get("family_id") != catalog.payload["family_id"]:
        findings.append(TemplatePackFinding("native_route_family_mismatch", "$.family_id", str(row.get("family_id"))))
    if row.get("catalog_id") != catalog.payload["catalog_id"]:
        findings.append(TemplatePackFinding("native_route_catalog_mismatch", "$.catalog_id", str(row.get("catalog_id"))))
    allowed_routes = {route for manifest in catalog.manifests for route in manifest.payload["route_ids"]}
    if row.get("route_id") not in allowed_routes:
        findings.append(TemplatePackFinding("native_route_unknown", "$.route_id", str(row.get("route_id"))))
    _validate_sealed_receipt(row, prefix="native-route", path="$", findings=findings)
    if findings:
        raise TemplatePackError(findings)
    return row


def seal_applicability_receipt(payload: Mapping[str, Any]) -> dict[str, Any]:
    semantic = {**payload, "schema_version": APPLICABILITY_RECEIPT_SCHEMA}
    if isinstance(semantic.get("results"), list):
        semantic["results"] = sorted(semantic["results"], key=lambda item: str(item.get("template_id", "")))
    return _seal_receipt(semantic, prefix="template-applicability")


def validate_applicability_receipt(
    payload: object,
    catalog: ValidatedCatalog,
    route_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    findings: list[TemplatePackFinding] = []
    row = _copy_mapping(payload, "$", findings)
    _reject_unknown(row, APPLICABILITY_RECEIPT_FIELDS, "$", findings)
    if row.get("schema_version") != APPLICABILITY_RECEIPT_SCHEMA:
        findings.append(TemplatePackFinding("applicability_schema_mismatch", "$.schema_version", APPLICABILITY_RECEIPT_SCHEMA))
    if row.get("native_owner_id") != catalog.payload["native_owner_id"]:
        findings.append(TemplatePackFinding("applicability_owner_mismatch", "$.native_owner_id", str(row.get("native_owner_id"))))
    if row.get("family_id") != catalog.payload["family_id"]:
        findings.append(TemplatePackFinding("applicability_family_mismatch", "$.family_id", str(row.get("family_id"))))
    if row.get("request_fingerprint") != route_receipt.get("request_fingerprint"):
        findings.append(TemplatePackFinding("applicability_request_mismatch", "$.request_fingerprint", str(row.get("request_fingerprint"))))
    if row.get("catalog_digest") != catalog.digest:
        findings.append(TemplatePackFinding("applicability_catalog_stale", "$.catalog_digest", str(row.get("catalog_digest"))))
    if row.get("route_receipt_hash") != route_receipt.get("receipt_hash"):
        findings.append(TemplatePackFinding("applicability_route_mismatch", "$.route_receipt_hash", str(row.get("route_receipt_hash"))))
    _required_text(row, "claim_boundary", "$", findings)
    result_rows = _rows(row.get("results"), "$.results", findings)
    index = catalog.manifest_index()
    seen: set[str] = set()
    result_allowed = frozenset(
        {
            "template_id",
            "manifest_digest",
            "eligible",
            "predicate_evidence_ids",
            "forbidden_clearance_evidence_ids",
            "reasons",
        }
    )
    for position, result in enumerate(result_rows):
        path = f"$.results[{position}]"
        _reject_unknown(result, result_allowed, path, findings)
        template_id = _id_text(result, "template_id", path, findings)
        if template_id in seen:
            findings.append(TemplatePackFinding("duplicate_applicability_result", f"{path}.template_id", template_id))
        seen.add(template_id)
        manifest = index.get(template_id)
        if manifest is None:
            findings.append(TemplatePackFinding("applicability_template_unknown", f"{path}.template_id", template_id))
            continue
        if result.get("manifest_digest") != manifest.digest:
            findings.append(TemplatePackFinding("applicability_manifest_stale", f"{path}.manifest_digest", template_id))
        eligible = result.get("eligible")
        if not isinstance(eligible, bool):
            findings.append(TemplatePackFinding("applicability_eligible_invalid", f"{path}.eligible", str(eligible)))
            eligible = False
        predicate_evidence = _string_list(result.get("predicate_evidence_ids"), f"{path}.predicate_evidence_ids", findings)
        forbidden_evidence = _string_list(result.get("forbidden_clearance_evidence_ids"), f"{path}.forbidden_clearance_evidence_ids", findings)
        reasons = _string_list(result.get("reasons"), f"{path}.reasons", findings)
        if eligible:
            if reasons:
                findings.append(TemplatePackFinding("eligible_candidate_has_rejection_reason", f"{path}.reasons", template_id))
            if len(predicate_evidence) < len(manifest.payload["applicability_predicate_ids"]):
                findings.append(TemplatePackFinding("predicate_evidence_incomplete", f"{path}.predicate_evidence_ids", template_id))
            if len(forbidden_evidence) < len(manifest.payload["forbidden_condition_ids"]):
                findings.append(TemplatePackFinding("forbidden_clearance_incomplete", f"{path}.forbidden_clearance_evidence_ids", template_id))
        elif not reasons:
            findings.append(TemplatePackFinding("rejected_candidate_reason_missing", f"{path}.reasons", template_id))
    if seen != set(index):
        findings.append(TemplatePackFinding("candidate_accounting_incomplete", "$.results", "results must equal the frozen catalog inventory"))
    _validate_sealed_receipt(row, prefix="template-applicability", path="$", findings=findings)
    if findings:
        raise TemplatePackError(findings)
    normalized = copy.deepcopy(row)
    normalized["results"] = sorted(normalized["results"], key=lambda item: item["template_id"])
    return normalized


def _composition_result(candidates: Sequence[ValidatedManifest]) -> tuple[bool, tuple[str, ...], dict[str, str], tuple[str, ...]]:
    findings: list[str] = []
    selected_ids = {item.template_id for item in candidates}
    owner_map: dict[str, str] = {}
    orders: dict[int, str] = {}
    for manifest in candidates:
        payload = manifest.payload
        if not payload["composable"]:
            findings.append(f"non_composable:{manifest.template_id}")
        missing = set(payload["dependencies"]) - selected_ids
        for dependency in sorted(missing):
            findings.append(f"missing_dependency:{manifest.template_id}:{dependency}")
        order = int(payload["composition_order"])
        if order in orders:
            findings.append(f"composition_order_conflict:{orders[order]}:{manifest.template_id}:{order}")
        orders[order] = manifest.template_id
        for field_id in payload["field_ownership"]:
            if field_id in owner_map:
                findings.append(f"field_owner_conflict:{field_id}:{owner_map[field_id]}:{manifest.template_id}")
            else:
                owner_map[field_id] = manifest.template_id
    for left_index, left in enumerate(candidates):
        for right in candidates[left_index + 1 :]:
            left_payload, right_payload = left.payload, right.payload
            if right.template_id not in left_payload["compatible_with"] or left.template_id not in right_payload["compatible_with"]:
                findings.append(f"pair_not_compatible:{left.template_id}:{right.template_id}")
            if right.template_id in left_payload["conflicts_with"] or left.template_id in right_payload["conflicts_with"]:
                findings.append(f"declared_conflict:{left.template_id}:{right.template_id}")
    ordered = tuple(item.template_id for item in sorted(candidates, key=lambda item: int(item.payload["composition_order"])))
    return not findings, ordered, dict(sorted(owner_map.items())), tuple(findings)


def select_template_packs(
    catalog_payload: object,
    route_receipt_payload: object,
    applicability_receipt_payload: object,
) -> dict[str, Any]:
    catalog = validate_template_catalog(catalog_payload)
    route = validate_native_route_receipt(route_receipt_payload, catalog)
    applicability = validate_applicability_receipt(applicability_receipt_payload, catalog, route)
    manifest_index = catalog.manifest_index()
    applicability_index = {row["template_id"]: row for row in applicability["results"]}
    base_id = str(catalog.payload["base_template_id"])
    eligible = [
        manifest
        for manifest in catalog.manifests
        if manifest.template_id != base_id and applicability_index[manifest.template_id]["eligible"]
    ]
    status = "selected"
    disposition = "ambiguous_template_selection"
    selected: tuple[ValidatedManifest, ...] = ()
    order: tuple[str, ...] = ()
    owner_map: dict[str, str] = {}
    findings: list[str] = []

    if not eligible:
        disposition = "base_no_match"
        if base_id and base_id in manifest_index and applicability_index[base_id]["eligible"]:
            selected = (manifest_index[base_id],)
            order = (base_id,)
            owner_map = {field: base_id for field in selected[0].payload["field_ownership"]}
        else:
            status = "blocked"
            findings.append("no_eligible_domain_template_and_no_eligible_validated_base")
    elif len(eligible) == 1:
        disposition = "single_selected"
        selected = (eligible[0],)
        order = (eligible[0].template_id,)
        owner_map = {field: eligible[0].template_id for field in eligible[0].payload["field_ownership"]}
    else:
        composable, composed_order, composed_owners, composition_findings = _composition_result(eligible)
        if composable:
            disposition = "composed"
            order = composed_order
            selected = tuple(manifest_index[item] for item in order)
            owner_map = composed_owners
        else:
            eligible_ids = {item.template_id for item in eligible}
            dominant = [
                item
                for item in eligible
                if eligible_ids - {item.template_id} <= set(item.payload["dominates_template_ids"])
            ]
            if len(dominant) == 1:
                disposition = "strictly_dominated_selection"
                selected = (dominant[0],)
                order = (dominant[0].template_id,)
                owner_map = {field: dominant[0].template_id for field in dominant[0].payload["field_ownership"]}
                findings.extend(f"strictly_dominated:{item.template_id}:by:{dominant[0].template_id}" for item in eligible if item is not dominant[0])
            else:
                status = "blocked"
                disposition = "ambiguous_template_selection"
                findings.extend(composition_findings)
                findings.append("multiple_eligible_candidates_without_safe_composition_or_unique_strict_dominance")

    selected_ids = {item.template_id for item in selected}
    candidate_rows: list[dict[str, Any]] = []
    for manifest in catalog.manifests:
        native = applicability_index[manifest.template_id]
        if manifest.template_id in selected_ids:
            selection_status = "selected"
            reasons: list[str] = []
        elif not native["eligible"]:
            selection_status = "rejected"
            reasons = list(native["reasons"])
        elif disposition == "base_no_match" and manifest.template_id != base_id:
            selection_status = "rejected"
            reasons = ["not_eligible_as_reported_by_target"]
        elif disposition == "strictly_dominated_selection" and selected:
            selection_status = "rejected"
            reasons = [f"strictly_dominated_by:{selected[0].template_id}"]
        elif manifest.template_id == base_id:
            selection_status = "rejected"
            reasons = ["validated_base_is_fallback_only"]
        else:
            selection_status = "rejected"
            reasons = ["ambiguous_or_incompatible_candidate"]
        candidate_rows.append(
            {
                "template_id": manifest.template_id,
                "manifest_digest": manifest.digest,
                "native_eligible": bool(native["eligible"]),
                "selection_status": selection_status,
                "reasons": reasons,
            }
        )

    receipt = _seal_receipt(
        {
            "schema_version": SELECTION_RECEIPT_SCHEMA,
            "status": status,
            "disposition": disposition,
            "request_fingerprint": route["request_fingerprint"],
            "catalog_digest": catalog.digest,
            "route_receipt_hash": route["receipt_hash"],
            "applicability_receipt_hash": applicability["receipt_hash"],
            "candidate_accounting": candidate_rows,
            "selected_template_ids": [item.template_id for item in selected],
            "composition_order": list(order),
            "field_owner_map": owner_map,
            "findings": sorted(set(findings)),
            "harvest_review_required": disposition == "base_no_match",
            "claim_boundary": (
                "This receipt proves only target-routed candidate accounting and deterministic selection. "
                "It does not prove instantiation, native validation, closure, installation, release, or publication."
            ),
        },
        prefix="template-selection",
    )
    validate_selection_receipt(receipt, catalog, route, applicability)
    return receipt


def validate_selection_receipt(
    payload: object,
    catalog: ValidatedCatalog | object,
    route_receipt: Mapping[str, Any] | object,
    applicability_receipt: Mapping[str, Any] | object,
) -> dict[str, Any]:
    validated_catalog = catalog if isinstance(catalog, ValidatedCatalog) else validate_template_catalog(catalog)
    route = route_receipt if isinstance(route_receipt, Mapping) else {}
    route = validate_native_route_receipt(route, validated_catalog)
    applicability = applicability_receipt if isinstance(applicability_receipt, Mapping) else {}
    applicability = validate_applicability_receipt(applicability, validated_catalog, route)
    findings: list[TemplatePackFinding] = []
    row = _copy_mapping(payload, "$", findings)
    _reject_unknown(row, SELECTION_RECEIPT_FIELDS, "$", findings)
    if row.get("schema_version") != SELECTION_RECEIPT_SCHEMA:
        findings.append(TemplatePackFinding("selection_schema_mismatch", "$.schema_version", SELECTION_RECEIPT_SCHEMA))
    if row.get("status") not in RECEIPT_STATUSES:
        findings.append(TemplatePackFinding("selection_status_invalid", "$.status", str(row.get("status"))))
    if row.get("disposition") not in SELECTION_DISPOSITIONS:
        findings.append(TemplatePackFinding("selection_disposition_invalid", "$.disposition", str(row.get("disposition"))))
    expected_pairs = {
        "request_fingerprint": route["request_fingerprint"],
        "catalog_digest": validated_catalog.digest,
        "route_receipt_hash": route["receipt_hash"],
        "applicability_receipt_hash": applicability["receipt_hash"],
    }
    for key, expected in expected_pairs.items():
        if row.get(key) != expected:
            findings.append(TemplatePackFinding("selection_input_stale", f"$.{key}", f"expected {expected}"))
    accounting = _rows(row.get("candidate_accounting"), "$.candidate_accounting", findings)
    accounting_allowed = frozenset({"template_id", "manifest_digest", "native_eligible", "selection_status", "reasons"})
    catalog_index = validated_catalog.manifest_index()
    seen: set[str] = set()
    for index, candidate in enumerate(accounting):
        path = f"$.candidate_accounting[{index}]"
        _reject_unknown(candidate, accounting_allowed, path, findings)
        template_id = _id_text(candidate, "template_id", path, findings)
        seen.add(template_id)
        manifest = catalog_index.get(template_id)
        if manifest is None:
            findings.append(TemplatePackFinding("selection_candidate_unknown", f"{path}.template_id", template_id))
        elif candidate.get("manifest_digest") != manifest.digest:
            findings.append(TemplatePackFinding("selection_manifest_stale", f"{path}.manifest_digest", template_id))
        if candidate.get("selection_status") not in {"selected", "rejected"}:
            findings.append(TemplatePackFinding("candidate_disposition_invalid", f"{path}.selection_status", str(candidate.get("selection_status"))))
        reasons = _string_list(candidate.get("reasons"), f"{path}.reasons", findings)
        if candidate.get("selection_status") == "selected" and reasons:
            findings.append(TemplatePackFinding("selected_candidate_has_rejection_reason", f"{path}.reasons", template_id))
        if candidate.get("selection_status") == "rejected" and not reasons:
            findings.append(TemplatePackFinding("rejected_candidate_reason_missing", f"{path}.reasons", template_id))
    if seen != set(catalog_index) or len(accounting) != len(catalog_index):
        findings.append(TemplatePackFinding("selection_candidate_accounting_incomplete", "$.candidate_accounting", "must equal catalog inventory exactly once"))
    selected_ids = _string_list(row.get("selected_template_ids"), "$.selected_template_ids", findings)
    order = _string_list(row.get("composition_order"), "$.composition_order", findings)
    if selected_ids != order:
        findings.append(TemplatePackFinding("selection_order_mismatch", "$.composition_order", "order must equal selected ids"))
    selected_rows = {str(item.get("template_id")) for item in accounting if item.get("selection_status") == "selected"}
    if selected_rows != set(selected_ids):
        findings.append(TemplatePackFinding("selected_candidate_accounting_mismatch", "$.selected_template_ids", "selected rows differ"))
    field_owner_map = _copy_mapping(row.get("field_owner_map"), "$.field_owner_map", findings)
    expected_fields = {
        field: template_id
        for template_id in selected_ids
        if template_id in catalog_index
        for field in catalog_index[template_id].payload["field_ownership"]
    }
    if field_owner_map != expected_fields:
        findings.append(TemplatePackFinding("field_owner_map_mismatch", "$.field_owner_map", "must equal selected manifest ownership"))
    _string_list(row.get("findings"), "$.findings", findings)
    if not isinstance(row.get("harvest_review_required"), bool):
        findings.append(TemplatePackFinding("harvest_review_flag_invalid", "$.harvest_review_required", "must be boolean"))
    _required_text(row, "claim_boundary", "$", findings)
    if row.get("status") == "selected" and not selected_ids:
        findings.append(TemplatePackFinding("selected_receipt_empty", "$.selected_template_ids", "selected status requires a template"))
    if row.get("status") == "blocked" and selected_ids:
        findings.append(TemplatePackFinding("blocked_receipt_selects_template", "$.selected_template_ids", "blocked status cannot authorize output"))
    _validate_sealed_receipt(row, prefix="template-selection", path="$", findings=findings)
    if findings:
        raise TemplatePackError(findings)
    return row


def selection_receipt_current(
    payload: object,
    catalog_payload: object,
    route_receipt_payload: object,
    applicability_receipt_payload: object,
) -> tuple[bool, tuple[str, ...]]:
    try:
        catalog = validate_template_catalog(catalog_payload)
        route = validate_native_route_receipt(route_receipt_payload, catalog)
        applicability = validate_applicability_receipt(applicability_receipt_payload, catalog, route)
        validate_selection_receipt(payload, catalog, route, applicability)
    except TemplatePackError as exc:
        return False, tuple(f"{item.code}:{item.path}" for item in exc.findings)
    expected = select_template_packs(catalog.payload, route, applicability)
    observed = dict(payload) if isinstance(payload, Mapping) else {}
    if observed.get("receipt_hash") != expected.get("receipt_hash"):
        return False, ("selection_recomputation_mismatch",)
    return True, ()


def _type_matches(value: object, declared: str) -> bool:
    if declared == "string":
        return isinstance(value, str)
    if declared == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if declared == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))
    if declared == "boolean":
        return isinstance(value, bool)
    if declared == "array":
        return isinstance(value, list)
    if declared == "object":
        return isinstance(value, Mapping)
    return False


def normalize_parameters(manifest: ValidatedManifest, raw: object) -> dict[str, Any]:
    findings: list[TemplatePackFinding] = []
    values = _copy_mapping(raw, f"$.parameters.{manifest.template_id}", findings)
    schema = manifest.payload["parameter_schema"]
    properties = schema["properties"]
    unknown = set(values) - set(properties)
    for key in sorted(unknown):
        findings.append(TemplatePackFinding("unknown_parameter", f"$.parameters.{manifest.template_id}.{key}", "not declared"))
    normalized = copy.deepcopy(values)
    for name, declaration in properties.items():
        if name not in normalized and "default" in declaration:
            normalized[name] = copy.deepcopy(declaration["default"])
    for name in schema["required"]:
        if name not in normalized:
            findings.append(TemplatePackFinding("required_parameter_missing", f"$.parameters.{manifest.template_id}.{name}", name))
    for name, value in normalized.items():
        declaration = properties.get(name)
        if declaration is None:
            continue
        if not _type_matches(value, declaration["type"]):
            findings.append(TemplatePackFinding("parameter_type_mismatch", f"$.parameters.{manifest.template_id}.{name}", declaration["type"]))
            continue
        if "enum" in declaration and value not in declaration["enum"]:
            findings.append(TemplatePackFinding("parameter_enum_mismatch", f"$.parameters.{manifest.template_id}.{name}", str(value)))
        if isinstance(value, str) and "pattern" in declaration and not re.search(str(declaration["pattern"]), value):
            findings.append(TemplatePackFinding("parameter_pattern_mismatch", f"$.parameters.{manifest.template_id}.{name}", str(declaration["pattern"])))
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in declaration and value < declaration["minimum"]:
                findings.append(TemplatePackFinding("parameter_minimum_mismatch", f"$.parameters.{manifest.template_id}.{name}", str(value)))
            if "maximum" in declaration and value > declaration["maximum"]:
                findings.append(TemplatePackFinding("parameter_maximum_mismatch", f"$.parameters.{manifest.template_id}.{name}", str(value)))
    if findings:
        raise TemplatePackError(findings)
    return dict(sorted(normalized.items()))


def _seal_native_evidence(payload: Mapping[str, Any], *, prefix: str) -> dict[str, Any]:
    return _seal_receipt(payload, prefix=prefix)


def seal_builder_receipt(payload: Mapping[str, Any]) -> dict[str, Any]:
    return _seal_native_evidence(payload, prefix="template-builder")


def seal_validator_receipt(payload: Mapping[str, Any]) -> dict[str, Any]:
    return _seal_native_evidence(payload, prefix="template-validator")


def build_instance_receipt(
    *,
    selection_receipt_payload: object,
    catalog_payload: object,
    route_receipt_payload: object,
    applicability_receipt_payload: object,
    parameters: Mapping[str, Any],
    builder_receipts: Sequence[Mapping[str, Any]],
    generated_artifacts: Sequence[Mapping[str, Any]],
    unresolved_placeholders: Sequence[str],
    validator_receipts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    catalog = validate_template_catalog(catalog_payload)
    route = validate_native_route_receipt(route_receipt_payload, catalog)
    applicability = validate_applicability_receipt(applicability_receipt_payload, catalog, route)
    selection = validate_selection_receipt(selection_receipt_payload, catalog, route, applicability)
    findings: list[str] = []
    selected_ids = tuple(selection["selected_template_ids"])
    manifests = catalog.manifest_index()
    normalized_parameters: dict[str, Any] = {}
    if selection["status"] != "selected":
        findings.append("selection_is_blocked")
    unknown_parameter_namespaces = set(parameters) - set(selected_ids)
    for namespace in sorted(unknown_parameter_namespaces):
        findings.append(f"parameter_namespace_not_selected:{namespace}")
    for template_id in selected_ids:
        try:
            normalized_parameters[template_id] = normalize_parameters(manifests[template_id], parameters.get(template_id, {}))
        except TemplatePackError as exc:
            findings.extend(f"{item.code}:{item.path}" for item in exc.findings)

    builder_index = {str(item.get("template_id")): dict(item) for item in builder_receipts}
    if len(builder_index) != len(builder_receipts):
        findings.append("duplicate_builder_receipt")
    for template_id in selected_ids:
        receipt = builder_index.get(template_id)
        manifest = manifests[template_id]
        if receipt is None:
            findings.append(f"builder_receipt_missing:{template_id}")
            continue
        expected_builder = manifest.payload["builder"]
        expected = _seal_receipt(receipt, prefix="template-builder")
        if receipt.get("receipt_hash") != expected["receipt_hash"] or receipt.get("receipt_id") != expected["receipt_id"]:
            findings.append(f"builder_receipt_hash_invalid:{template_id}")
        if receipt.get("status") != "passed":
            findings.append(f"builder_not_passed:{template_id}:{receipt.get('status')}")
        if receipt.get("manifest_digest") != manifest.digest:
            findings.append(f"builder_manifest_stale:{template_id}")
        if receipt.get("builder_id") != expected_builder["builder_id"] or receipt.get("builder_content_hash") != expected_builder["content_hash"]:
            findings.append(f"builder_identity_mismatch:{template_id}")

    artifact_index = {(str(item.get("template_id")), str(item.get("artifact_id"))): dict(item) for item in generated_artifacts}
    if len(artifact_index) != len(generated_artifacts):
        findings.append("duplicate_generated_artifact")
    expected_artifacts = {
        (template_id, artifact["artifact_id"])
        for template_id in selected_ids
        for artifact in manifests[template_id].payload["artifacts"]
    }
    if set(artifact_index) != expected_artifacts:
        findings.append("generated_artifact_inventory_mismatch")
    for key, artifact in artifact_index.items():
        if artifact.get("manifest_digest") != manifests[key[0]].digest:
            findings.append(f"artifact_manifest_stale:{key[0]}:{key[1]}")
        relative_path = str(artifact.get("relative_path", ""))
        if not _portable_relative(relative_path):
            findings.append(f"artifact_path_not_portable:{key[0]}:{key[1]}")
        if not SHA256_RE.fullmatch(str(artifact.get("sha256", ""))):
            findings.append(f"artifact_hash_invalid:{key[0]}:{key[1]}")

    unresolved = tuple(sorted(set(str(item) for item in unresolved_placeholders if str(item))))
    if unresolved:
        findings.extend(f"unresolved_placeholder:{item}" for item in unresolved)

    validator_index = {(str(item.get("template_id")), str(item.get("validator_id"))): dict(item) for item in validator_receipts}
    if len(validator_index) != len(validator_receipts):
        findings.append("duplicate_validator_receipt")
    expected_validators = {
        (template_id, validator["validator_id"])
        for template_id in selected_ids
        for validator in manifests[template_id].payload["validators"]
    }
    if set(validator_index) != expected_validators:
        findings.append("validator_receipt_inventory_mismatch")
    for key, receipt in validator_index.items():
        manifest = manifests[key[0]]
        expected_declaration = next(item for item in manifest.payload["validators"] if item["validator_id"] == key[1])
        expected = _seal_receipt(receipt, prefix="template-validator")
        if receipt.get("receipt_hash") != expected["receipt_hash"] or receipt.get("receipt_id") != expected["receipt_id"]:
            findings.append(f"validator_receipt_hash_invalid:{key[0]}:{key[1]}")
        if receipt.get("status") != "passed":
            findings.append(f"validator_not_passed:{key[0]}:{key[1]}:{receipt.get('status')}")
        if receipt.get("manifest_digest") != manifest.digest:
            findings.append(f"validator_manifest_stale:{key[0]}:{key[1]}")
        if receipt.get("check_id") != expected_declaration["check_id"]:
            findings.append(f"validator_check_mismatch:{key[0]}:{key[1]}")
        if receipt.get("validator_content_hash") != expected_declaration["content_hash"]:
            findings.append(f"validator_identity_mismatch:{key[0]}:{key[1]}")

    status = "passed" if not findings else "blocked"
    fingerprint_payload = {
        "selection_receipt_hash": selection["receipt_hash"],
        "catalog_digest": catalog.digest,
        "selected_template_ids": list(selected_ids),
        "parameters": normalized_parameters,
        "builder_receipt_hashes": sorted(str(row.get("receipt_hash", "")) for row in builder_receipts),
        "generated_artifacts": sorted((dict(row) for row in generated_artifacts), key=lambda row: (str(row.get("template_id", "")), str(row.get("artifact_id", "")))),
        "validator_receipt_hashes": sorted(str(row.get("receipt_hash", "")) for row in validator_receipts),
    }
    instance_fingerprint = sha256_identity(fingerprint_payload)
    receipt = _seal_receipt(
        {
            "schema_version": INSTANCE_RECEIPT_SCHEMA,
            "status": status,
            "selection_receipt_hash": selection["receipt_hash"],
            "catalog_digest": catalog.digest,
            "selected_template_ids": list(selected_ids),
            "parameters": normalized_parameters,
            "builder_receipts": sorted((dict(row) for row in builder_receipts), key=lambda row: str(row.get("template_id", ""))),
            "generated_artifacts": sorted((dict(row) for row in generated_artifacts), key=lambda row: (str(row.get("template_id", "")), str(row.get("artifact_id", "")))),
            "unresolved_placeholders": list(unresolved),
            "validator_receipts": sorted((dict(row) for row in validator_receipts), key=lambda row: (str(row.get("template_id", "")), str(row.get("validator_id", "")))),
            "findings": sorted(set(findings)),
            "instance_fingerprint": instance_fingerprint,
            "claim_boundary": (
                "This receipt binds one generated instance to its selection, parameters, target builders, artifacts, and native validators. "
                "It does not independently prove target closure, installation, release, publication, or domain truth."
            ),
        },
        prefix="template-instance",
    )
    validate_instance_receipt(receipt, selection, catalog)
    return receipt


def validate_instance_receipt(payload: object, selection_receipt: Mapping[str, Any], catalog: ValidatedCatalog | object) -> dict[str, Any]:
    validated_catalog = catalog if isinstance(catalog, ValidatedCatalog) else validate_template_catalog(catalog)
    findings: list[TemplatePackFinding] = []
    row = _copy_mapping(payload, "$", findings)
    _reject_unknown(row, INSTANCE_RECEIPT_FIELDS, "$", findings)
    if row.get("schema_version") != INSTANCE_RECEIPT_SCHEMA:
        findings.append(TemplatePackFinding("instance_schema_mismatch", "$.schema_version", INSTANCE_RECEIPT_SCHEMA))
    if row.get("status") not in {"passed", "blocked"}:
        findings.append(TemplatePackFinding("instance_status_invalid", "$.status", str(row.get("status"))))
    if row.get("selection_receipt_hash") != selection_receipt.get("receipt_hash"):
        findings.append(TemplatePackFinding("instance_selection_stale", "$.selection_receipt_hash", str(row.get("selection_receipt_hash"))))
    if row.get("catalog_digest") != validated_catalog.digest:
        findings.append(TemplatePackFinding("instance_catalog_stale", "$.catalog_digest", str(row.get("catalog_digest"))))
    selected_ids = _string_list(row.get("selected_template_ids"), "$.selected_template_ids", findings)
    if tuple(selection_receipt.get("selected_template_ids", ())) != selected_ids:
        findings.append(TemplatePackFinding("instance_selected_set_mismatch", "$.selected_template_ids", "must equal selection receipt"))
    parameters = _copy_mapping(row.get("parameters"), "$.parameters", findings)
    builder_rows = _rows(row.get("builder_receipts"), "$.builder_receipts", findings)
    artifact_rows = _rows(row.get("generated_artifacts"), "$.generated_artifacts", findings)
    unresolved = _string_list(row.get("unresolved_placeholders"), "$.unresolved_placeholders", findings)
    validator_rows = _rows(row.get("validator_receipts"), "$.validator_receipts", findings)
    instance_findings = _string_list(row.get("findings"), "$.findings", findings)
    fingerprint = _required_text(row, "instance_fingerprint", "$", findings)
    if fingerprint and not SHA256_RE.fullmatch(fingerprint):
        findings.append(TemplatePackFinding("instance_fingerprint_invalid", "$.instance_fingerprint", fingerprint))
    expected_fingerprint = sha256_identity(
        {
            "selection_receipt_hash": selection_receipt.get("receipt_hash"),
            "catalog_digest": validated_catalog.digest,
            "selected_template_ids": list(selected_ids),
            "parameters": parameters,
            "builder_receipt_hashes": sorted(str(item.get("receipt_hash", "")) for item in builder_rows),
            "generated_artifacts": sorted(
                artifact_rows,
                key=lambda item: (str(item.get("template_id", "")), str(item.get("artifact_id", ""))),
            ),
            "validator_receipt_hashes": sorted(str(item.get("receipt_hash", "")) for item in validator_rows),
        }
    )
    if fingerprint and fingerprint != expected_fingerprint:
        findings.append(TemplatePackFinding("instance_fingerprint_mismatch", "$.instance_fingerprint", f"expected {expected_fingerprint}"))

    manifest_index = validated_catalog.manifest_index()
    for index, builder in enumerate(builder_rows):
        path = f"$.builder_receipts[{index}]"
        template_id = str(builder.get("template_id", ""))
        manifest = manifest_index.get(template_id)
        expected_receipt = _seal_receipt(builder, prefix="template-builder")
        if builder.get("receipt_id") != expected_receipt["receipt_id"] or builder.get("receipt_hash") != expected_receipt["receipt_hash"]:
            findings.append(TemplatePackFinding("builder_receipt_hash_invalid", path, template_id))
        if manifest is None or template_id not in selected_ids:
            findings.append(TemplatePackFinding("builder_receipt_template_invalid", f"{path}.template_id", template_id))
        else:
            declaration = manifest.payload["builder"]
            if builder.get("manifest_digest") != manifest.digest:
                findings.append(TemplatePackFinding("builder_manifest_stale", f"{path}.manifest_digest", template_id))
            if builder.get("builder_id") != declaration["builder_id"] or builder.get("builder_content_hash") != declaration["content_hash"]:
                findings.append(TemplatePackFinding("builder_identity_mismatch", path, template_id))
        if builder.get("status") != "passed":
            findings.append(TemplatePackFinding("builder_not_passed", f"{path}.status", str(builder.get("status"))))

    for index, validator in enumerate(validator_rows):
        path = f"$.validator_receipts[{index}]"
        template_id = str(validator.get("template_id", ""))
        validator_id = str(validator.get("validator_id", ""))
        manifest = manifest_index.get(template_id)
        expected_receipt = _seal_receipt(validator, prefix="template-validator")
        if validator.get("receipt_id") != expected_receipt["receipt_id"] or validator.get("receipt_hash") != expected_receipt["receipt_hash"]:
            findings.append(TemplatePackFinding("validator_receipt_hash_invalid", path, f"{template_id}:{validator_id}"))
        if manifest is None or template_id not in selected_ids:
            findings.append(TemplatePackFinding("validator_receipt_template_invalid", f"{path}.template_id", template_id))
        else:
            declarations = {item["validator_id"]: item for item in manifest.payload["validators"]}
            declaration = declarations.get(validator_id)
            if declaration is None:
                findings.append(TemplatePackFinding("validator_receipt_unknown", f"{path}.validator_id", validator_id))
            else:
                if validator.get("manifest_digest") != manifest.digest:
                    findings.append(TemplatePackFinding("validator_manifest_stale", f"{path}.manifest_digest", template_id))
                if validator.get("check_id") != declaration["check_id"] or validator.get("validator_content_hash") != declaration["content_hash"]:
                    findings.append(TemplatePackFinding("validator_identity_mismatch", path, f"{template_id}:{validator_id}"))
        if validator.get("status") != "passed":
            findings.append(TemplatePackFinding("validator_not_passed", f"{path}.status", str(validator.get("status"))))

    expected_artifacts = {
        (template_id, artifact["artifact_id"])
        for template_id in selected_ids
        if template_id in manifest_index
        for artifact in manifest_index[template_id].payload["artifacts"]
    }
    observed_artifacts = {
        (str(item.get("template_id", "")), str(item.get("artifact_id", "")))
        for item in artifact_rows
    }
    if expected_artifacts != observed_artifacts or len(observed_artifacts) != len(artifact_rows):
        findings.append(TemplatePackFinding("generated_artifact_inventory_mismatch", "$.generated_artifacts", "must equal selected manifest artifacts"))
    for index, artifact in enumerate(artifact_rows):
        path = f"$.generated_artifacts[{index}]"
        template_id = str(artifact.get("template_id", ""))
        manifest = manifest_index.get(template_id)
        if manifest is None or template_id not in selected_ids:
            findings.append(TemplatePackFinding("generated_artifact_template_invalid", f"{path}.template_id", template_id))
            continue
        if artifact.get("manifest_digest") != manifest.digest:
            findings.append(TemplatePackFinding("artifact_manifest_stale", f"{path}.manifest_digest", template_id))
        relative_path = str(artifact.get("relative_path", ""))
        if not _portable_relative(relative_path):
            findings.append(TemplatePackFinding("artifact_path_not_portable", f"{path}.relative_path", relative_path))
        if not SHA256_RE.fullmatch(str(artifact.get("sha256", ""))):
            findings.append(TemplatePackFinding("artifact_hash_invalid", f"{path}.sha256", str(artifact.get("sha256", ""))))
    if row.get("status") == "passed" and (unresolved or instance_findings):
        findings.append(TemplatePackFinding("passing_instance_has_findings", "$.status", "passed instance must have no gaps"))
    if row.get("status") == "blocked" and not instance_findings:
        findings.append(TemplatePackFinding("blocked_instance_reason_missing", "$.findings", "blocked instance needs findings"))
    _required_text(row, "claim_boundary", "$", findings)
    _validate_sealed_receipt(row, prefix="template-instance", path="$", findings=findings)
    if findings:
        raise TemplatePackError(findings)
    return row


def unresolved_placeholders(value: object) -> tuple[str, ...]:
    found: set[str] = set()

    def visit(item: object) -> None:
        if isinstance(item, Mapping):
            for nested in item.values():
                visit(nested)
        elif isinstance(item, (list, tuple)):
            for nested in item:
                visit(nested)
        elif isinstance(item, str):
            found.update(PLACEHOLDER_RE.findall(item))

    visit(value)
    return tuple(sorted(found))


def template_content_components(catalog_payload: object) -> dict[str, str]:
    """Return exact behavior-bearing content components for impact planning."""

    catalog = validate_template_catalog(catalog_payload)
    components: dict[str, str] = {"template_catalog": catalog.digest}
    for manifest in catalog.manifests:
        components[f"manifest:{manifest.template_id}"] = manifest.digest
        builder = manifest.payload["builder"]
        components[f"builder:{builder['builder_id']}"] = builder["content_hash"]
        for artifact in manifest.payload["artifacts"]:
            components[f"template_body:{manifest.template_id}:{artifact['artifact_id']}"] = artifact["content_template_hash"]
        for validator in manifest.payload["validators"]:
            components[f"validator:{validator['validator_id']}"] = validator["content_hash"]
        for prompt in manifest.payload["prompt_fragments"]:
            components[f"prompt:{prompt['fragment_id']}"] = prompt["content_hash"]
    return dict(sorted(components.items()))


__all__ = [
    "APPLICABILITY_RECEIPT_FIELDS",
    "APPLICABILITY_RECEIPT_SCHEMA",
    "CATALOG_FIELDS",
    "INSTANCE_RECEIPT_SCHEMA",
    "INSTANCE_RECEIPT_FIELDS",
    "MANIFEST_FIELDS",
    "NATIVE_ROUTE_RECEIPT_SCHEMA",
    "ROUTE_RECEIPT_FIELDS",
    "SELECTION_RECEIPT_FIELDS",
    "SELECTION_RECEIPT_SCHEMA",
    "TEMPLATE_CATALOG_SCHEMA",
    "TEMPLATE_MANIFEST_SCHEMA",
    "TemplatePackError",
    "TemplatePackFinding",
    "ValidatedCatalog",
    "ValidatedManifest",
    "build_instance_receipt",
    "canonical_json_bytes",
    "catalog_digest",
    "manifest_digest",
    "normalize_parameters",
    "seal_applicability_receipt",
    "seal_builder_receipt",
    "seal_native_route_receipt",
    "seal_template_catalog",
    "seal_template_manifest",
    "seal_validator_receipt",
    "select_template_packs",
    "selection_receipt_current",
    "sha256_identity",
    "template_content_components",
    "unresolved_placeholders",
    "validate_applicability_receipt",
    "validate_instance_receipt",
    "validate_native_route_receipt",
    "validate_selection_receipt",
    "validate_template_catalog",
    "validate_template_manifest",
]
