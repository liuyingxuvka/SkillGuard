"""Template-first planning and preview profiles for SkillGuard generators."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .template_packs import (
    TemplatePackError,
    seal_applicability_receipt,
    seal_native_route_receipt,
    seal_template_catalog,
    seal_template_manifest,
    select_template_packs,
    selection_receipt_current,
    sha256_identity,
    template_content_components,
    unresolved_placeholders,
    validate_template_catalog,
)


TEMPLATE_PROFILE_SCHEMA = "skillguard.template_profile.v1"
BUILTIN_SCAFFOLD_TEMPLATE_ID = "skillguard-validated-base"
BUILTIN_SCAFFOLD_FAMILY_ID = "skillguard-generated-skill"
BUILTIN_SCAFFOLD_OWNER_ID = "owner:skillguard-generate-skill"
BUILTIN_SCAFFOLD_ROUTE_ID = "route:generate-skill"
PROFILE_FIELDS = frozenset(
    {
        "schema_version",
        "profile_kind",
        "catalog",
        "native_route_receipt",
        "applicability_receipt",
        "selection_receipt",
        "source_bindings",
        "parameters",
        "materialized_preview",
        "content_components",
        "claim_boundary",
        "profile_hash",
    }
)
SOURCE_BINDING_FIELDS = frozenset({"role", "path", "sha256"})
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class TemplateProfileError(ValueError):
    def __init__(self, findings: Sequence[str]):
        self.findings = tuple(findings)
        super().__init__("; ".join(self.findings) or "template profile is invalid")


def _profile_hash(payload: Mapping[str, Any]) -> str:
    return sha256_identity(
        {
            key: copy.deepcopy(value)
            for key, value in payload.items()
            if key != "profile_hash"
        }
    )


def seal_template_profile(payload: Mapping[str, Any]) -> dict[str, Any]:
    semantic = {
        key: copy.deepcopy(value)
        for key, value in payload.items()
        if key != "profile_hash"
    }
    return {**semantic, "profile_hash": sha256_identity(semantic)}


def normalize_source_bindings(bindings: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    findings: list[str] = []
    normalized: list[dict[str, str]] = []
    seen_roles: set[str] = set()
    for index, item in enumerate(bindings):
        if not isinstance(item, Mapping):
            findings.append(f"template_source_binding_not_object:{index}")
            continue
        unknown = set(item) - SOURCE_BINDING_FIELDS
        findings.extend(
            f"template_source_binding_unknown_field:{index}:{key}"
            for key in sorted(unknown)
        )
        role = item.get("role")
        path = item.get("path")
        identity = item.get("sha256")
        if not isinstance(role, str) or not role.strip():
            findings.append(f"template_source_binding_role_invalid:{index}")
            continue
        if role in seen_roles:
            findings.append(f"template_source_binding_role_duplicate:{role}")
        seen_roles.add(role)
        if (
            not isinstance(path, str)
            or not path.strip()
            or Path(path).is_absolute()
            or ".." in Path(path).parts
        ):
            findings.append(f"template_source_binding_path_invalid:{role}")
            continue
        if not isinstance(identity, str) or not SHA256_RE.fullmatch(identity):
            findings.append(f"template_source_binding_hash_invalid:{role}")
            continue
        normalized.append({"role": role, "path": path.replace("\\", "/"), "sha256": identity})
    if not normalized:
        findings.append("template_source_bindings_empty")
    if findings:
        raise TemplateProfileError(findings)
    return sorted(normalized, key=lambda item: item["role"])


def _artifact_template_hash(relative_path: str, builder_content_hash: str) -> str:
    return sha256_identity(
        {
            "template": "skillguard-generate-skill-scaffold-v1",
            "relative_path": relative_path,
            "builder_content_hash": builder_content_hash,
        }
    )


def _built_in_catalog(
    *,
    artifact_paths: Sequence[str],
    builder_content_hash: str,
    validator_content_hash: str,
    prompt_content_hash: str,
) -> dict[str, Any]:
    manifest = seal_template_manifest(
        {
            "schema_version": "skillguard.template_manifest.v1",
            "template_id": BUILTIN_SCAFFOLD_TEMPLATE_ID,
            "revision": "1",
            "template_kind": "base",
            "native_owner_id": BUILTIN_SCAFFOLD_OWNER_ID,
            "family_id": BUILTIN_SCAFFOLD_FAMILY_ID,
            "route_ids": [BUILTIN_SCAFFOLD_ROUTE_ID],
            "applicability_predicate_ids": ["predicate:create-skill-route"],
            "forbidden_condition_ids": ["forbidden:existing-unowned-output"],
            "dependencies": [],
            "compatible_with": [],
            "conflicts_with": [],
            "dominates_template_ids": [],
            "composable": False,
            "composition_order": 0,
            "is_validated_base": True,
            "field_ownership": [
                "skill-entrypoint",
                "reference-scaffold",
                "runtime-contract",
                "check-manifest",
                "fixture-scaffold",
                "test-scaffold",
            ],
            "parameter_schema": {
                "type": "object",
                "properties": {
                    "skill_name": {"type": "string"},
                    "description": {"type": "string"},
                    "purpose": {"type": "string"},
                    "target_path": {"type": "string"},
                },
                "required": [
                    "skill_name",
                    "description",
                    "purpose",
                    "target_path",
                ],
                "additionalProperties": False,
            },
            "artifacts": [
                {
                    "artifact_id": f"artifact:scaffold:{index:03d}",
                    "path_template": str(relative_path),
                    "content_template_hash": _artifact_template_hash(
                        str(relative_path), builder_content_hash
                    ),
                }
                for index, relative_path in enumerate(sorted(artifact_paths), 1)
            ],
            "builder": {
                "builder_id": "builder:skillguard-generate-skill",
                "entrypoint": "checker_engine:build_generate_skill_scaffold",
                "content_hash": builder_content_hash,
            },
            "validators": [
                {
                    "validator_id": "validator:skillguard-check-skill",
                    "check_id": "check:generated-skill-static",
                    "evidence_domain": "skillguard-generated-skill",
                    "content_hash": validator_content_hash,
                },
                {
                    "validator_id": "validator:skillguard-check-contract",
                    "check_id": "check:generated-skill-contract",
                    "evidence_domain": "skillguard-generated-skill",
                    "content_hash": validator_content_hash,
                },
            ],
            "prompt_fragments": [
                {
                    "fragment_id": "prompt:template-lifecycle-supervision-bundle",
                    "content_hash": prompt_content_hash,
                }
            ],
            "protected_failure_ids": [
                "failure:unowned-output-overwrite",
                "failure:incomplete-scaffold",
                "failure:stale-preview",
                "failure:unresolved-placeholder",
            ],
            "fixtures": {
                "known_good_ids": ["fixture:generate-skill:current-base"],
                "known_bad_by_failure": {
                    "failure:unowned-output-overwrite": [
                        "fixture:generate-skill:unowned-output"
                    ],
                    "failure:incomplete-scaffold": [
                        "fixture:generate-skill:missing-artifact"
                    ],
                    "failure:stale-preview": [
                        "fixture:generate-skill:stale-preview"
                    ],
                    "failure:unresolved-placeholder": [
                        "fixture:generate-skill:unresolved-placeholder"
                    ],
                },
                "ambiguity_ids": ["fixture:generate-skill:ambiguous-profile"],
                "stale_ids": ["fixture:generate-skill:stale-preview"],
            },
            "claim_boundary": (
                "This validated base owns only the generic generated-skill scaffold. "
                "It does not infer or replace target-domain routes, checks, builders, or validators."
            ),
        }
    )
    return seal_template_catalog(
        {
            "schema_version": "skillguard.template_catalog.v1",
            "catalog_id": "catalog:skillguard-generated-skill",
            "revision": "1",
            "native_owner_id": BUILTIN_SCAFFOLD_OWNER_ID,
            "family_id": BUILTIN_SCAFFOLD_FAMILY_ID,
            "base_template_id": BUILTIN_SCAFFOLD_TEMPLATE_ID,
            "templates": [manifest],
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
            "claim_boundary": (
                "This catalog covers only the SkillGuard-owned generic scaffold. "
                "Target Guard catalogs remain target-owned."
            ),
        }
    )


def _materialized_preview(
    *,
    selection_receipt: Mapping[str, Any],
    scaffold_files: Mapping[str, str],
    source_input_hash: str,
    builder_content_hash: str,
) -> dict[str, Any]:
    artifacts = [
        {
            "relative_path": str(relative_path),
            "sha256": sha256_identity(
                str(content).replace("\r\n", "\n").replace("\r", "\n")
            ),
        }
        for relative_path, content in sorted(scaffold_files.items())
    ]
    unresolved = list(unresolved_placeholders(scaffold_files))
    semantic = {
        "status": "current" if not unresolved else "blocked",
        "selection_receipt_hash": selection_receipt["receipt_hash"],
        "source_input_hash": source_input_hash,
        "builder_content_hash": builder_content_hash,
        "artifacts": artifacts,
        "unresolved_placeholders": unresolved,
        "claim_boundary": (
            "This is a read-only materialized scaffold preview. It does not write, "
            "activate, install, release, or prove the generated skill."
        ),
    }
    return {**semantic, "preview_fingerprint": sha256_identity(semantic)}


def build_builtin_scaffold_profile(
    *,
    parameters: Mapping[str, Any],
    artifact_paths: Sequence[str],
    scaffold_files: Mapping[str, str],
    source_input_hash: str,
    builder_content_hash: str,
    validator_content_hash: str,
    prompt_content_hash: str,
    source_bindings: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    catalog = _built_in_catalog(
        artifact_paths=artifact_paths,
        builder_content_hash=builder_content_hash,
        validator_content_hash=validator_content_hash,
        prompt_content_hash=prompt_content_hash,
    )
    request_fingerprint = sha256_identity(
        {
            "route_id": BUILTIN_SCAFFOLD_ROUTE_ID,
            "parameters": dict(parameters),
            "source_input_hash": source_input_hash,
        }
    )
    route = seal_native_route_receipt(
        {
            "target_id": "target:new-skill-scaffold",
            "native_owner_id": BUILTIN_SCAFFOLD_OWNER_ID,
            "family_id": BUILTIN_SCAFFOLD_FAMILY_ID,
            "route_id": BUILTIN_SCAFFOLD_ROUTE_ID,
            "request_fingerprint": request_fingerprint,
            "catalog_id": catalog["catalog_id"],
            "status": "passed",
            "claim_boundary": "SkillGuard create-skill route only.",
        }
    )
    manifest = catalog["templates"][0]
    applicability = seal_applicability_receipt(
        {
            "native_owner_id": BUILTIN_SCAFFOLD_OWNER_ID,
            "family_id": BUILTIN_SCAFFOLD_FAMILY_ID,
            "request_fingerprint": request_fingerprint,
            "catalog_digest": catalog["catalog_digest"],
            "route_receipt_hash": route["receipt_hash"],
            "results": [
                {
                    "template_id": BUILTIN_SCAFFOLD_TEMPLATE_ID,
                    "manifest_digest": manifest["manifest_digest"],
                    "eligible": True,
                    "predicate_evidence_ids": [
                        "evidence:create-skill-route-selected"
                    ],
                    "forbidden_clearance_evidence_ids": [
                        "evidence:write-preflight-required"
                    ],
                    "reasons": [],
                }
            ],
            "claim_boundary": "SkillGuard base-scaffold applicability only.",
        }
    )
    selection = select_template_packs(catalog, route, applicability)
    preview = _materialized_preview(
        selection_receipt=selection,
        scaffold_files=scaffold_files,
        source_input_hash=source_input_hash,
        builder_content_hash=builder_content_hash,
    )
    return seal_template_profile(
        {
            "schema_version": TEMPLATE_PROFILE_SCHEMA,
            "profile_kind": "skillguard_validated_base",
            "catalog": catalog,
            "native_route_receipt": route,
            "applicability_receipt": applicability,
            "selection_receipt": selection,
            "source_bindings": normalize_source_bindings(source_bindings),
            "parameters": dict(parameters),
            "materialized_preview": preview,
            "content_components": template_content_components(catalog),
            "claim_boundary": (
                "This profile proves a current read-only generic scaffold preview only. "
                "Generation, target-native validation, installation, release, and routing remain separate."
            ),
        }
    )


def build_external_selection_profile(
    *,
    catalog_payload: object,
    native_route_receipt: object,
    applicability_receipt: object,
    parameters: Mapping[str, Any],
    source_bindings: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    catalog = validate_template_catalog(catalog_payload)
    selection = select_template_packs(
        catalog.payload,
        native_route_receipt,
        applicability_receipt,
    )
    manifests = catalog.manifest_index()
    expected_artifacts = [
        {
            "template_id": template_id,
            "artifact_id": artifact["artifact_id"],
            "path_template": artifact["path_template"],
            "builder_id": manifests[template_id].payload["builder"]["builder_id"],
        }
        for template_id in selection["selected_template_ids"]
        for artifact in manifests[template_id].payload["artifacts"]
    ]
    preview_semantic = {
        "status": (
            "target_builder_required"
            if selection["status"] == "selected"
            else "blocked"
        ),
        "selection_receipt_hash": selection["receipt_hash"],
        "expected_artifacts": expected_artifacts,
        "unresolved_placeholders": [],
        "claim_boundary": (
            "This preview identifies target-owned builder work only. SkillGuard does "
            "not execute or emulate the target domain builder."
        ),
    }
    preview = {
        **preview_semantic,
        "preview_fingerprint": sha256_identity(preview_semantic),
    }
    return seal_template_profile(
        {
            "schema_version": TEMPLATE_PROFILE_SCHEMA,
            "profile_kind": "target_owned_selection",
            "catalog": catalog.payload,
            "native_route_receipt": dict(native_route_receipt) if isinstance(native_route_receipt, Mapping) else {},
            "applicability_receipt": dict(applicability_receipt) if isinstance(applicability_receipt, Mapping) else {},
            "selection_receipt": selection,
            "source_bindings": normalize_source_bindings(source_bindings),
            "parameters": dict(parameters),
            "materialized_preview": preview,
            "content_components": template_content_components(catalog.payload),
            "claim_boundary": (
                "This profile routes to a target-owned builder and validator set. "
                "It is not a generic generate-skill write authorization."
            ),
        }
    )


def validate_template_profile(payload: object) -> dict[str, Any]:
    findings: list[str] = []
    if not isinstance(payload, Mapping):
        raise TemplateProfileError(("template_profile_expected_object",))
    row = copy.deepcopy(dict(payload))
    unknown = set(row) - PROFILE_FIELDS
    findings.extend(f"template_profile_unknown_field:{key}" for key in sorted(unknown))
    if row.get("schema_version") != TEMPLATE_PROFILE_SCHEMA:
        findings.append("template_profile_schema_mismatch")
    if row.get("profile_kind") not in {
        "skillguard_validated_base",
        "target_owned_selection",
    }:
        findings.append("template_profile_kind_invalid")
    try:
        catalog = validate_template_catalog(row.get("catalog"))
        current, current_findings = selection_receipt_current(
            row.get("selection_receipt"),
            catalog.payload,
            row.get("native_route_receipt"),
            row.get("applicability_receipt"),
        )
        if not current:
            findings.extend(f"template_selection_stale:{item}" for item in current_findings)
        expected_components = template_content_components(catalog.payload)
        if row.get("content_components") != expected_components:
            findings.append("template_content_components_mismatch")
    except TemplatePackError as exc:
        findings.extend(
            f"template_protocol:{item.code}:{item.path}" for item in exc.findings
        )
    preview = row.get("materialized_preview")
    if not isinstance(preview, Mapping):
        findings.append("template_preview_missing")
    else:
        preview_semantic = {
            key: copy.deepcopy(value)
            for key, value in preview.items()
            if key != "preview_fingerprint"
        }
        if preview.get("preview_fingerprint") != sha256_identity(preview_semantic):
            findings.append("template_preview_fingerprint_mismatch")
        if preview.get("unresolved_placeholders"):
            findings.append("template_preview_has_unresolved_placeholders")
    if not isinstance(row.get("parameters"), Mapping):
        findings.append("template_profile_parameters_invalid")
    try:
        normalized_bindings = normalize_source_bindings(row.get("source_bindings", []))
        if row.get("source_bindings") != normalized_bindings:
            findings.append("template_source_bindings_not_canonical")
    except TemplateProfileError as exc:
        findings.extend(exc.findings)
    if not isinstance(row.get("claim_boundary"), str) or not row["claim_boundary"].strip():
        findings.append("template_profile_claim_boundary_missing")
    if row.get("profile_hash") != _profile_hash(row):
        findings.append("template_profile_hash_mismatch")
    if findings:
        raise TemplateProfileError(findings)
    return row


def validate_builtin_profile_current(
    payload: object,
    *,
    parameters: Mapping[str, Any],
    artifact_paths: Sequence[str],
    scaffold_files: Mapping[str, str],
    source_input_hash: str,
    builder_content_hash: str,
    validator_content_hash: str,
    prompt_content_hash: str,
    source_bindings: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    observed = validate_template_profile(payload)
    expected = build_builtin_scaffold_profile(
        parameters=parameters,
        artifact_paths=artifact_paths,
        scaffold_files=scaffold_files,
        source_input_hash=source_input_hash,
        builder_content_hash=builder_content_hash,
        validator_content_hash=validator_content_hash,
        prompt_content_hash=prompt_content_hash,
        source_bindings=source_bindings,
    )
    if observed.get("profile_hash") != expected.get("profile_hash"):
        raise TemplateProfileError(("template_profile_stale_recomputation",))
    return observed


def read_json_under_root(path: Path, repository_root: Path) -> Mapping[str, Any]:
    resolved = path.resolve()
    resolved.relative_to(repository_root.resolve())
    raw = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise TemplateProfileError((f"template_input_not_object:{resolved.name}",))
    return raw


__all__ = [
    "BUILTIN_SCAFFOLD_FAMILY_ID",
    "BUILTIN_SCAFFOLD_OWNER_ID",
    "BUILTIN_SCAFFOLD_ROUTE_ID",
    "BUILTIN_SCAFFOLD_TEMPLATE_ID",
    "PROFILE_FIELDS",
    "TEMPLATE_PROFILE_SCHEMA",
    "TemplateProfileError",
    "build_builtin_scaffold_profile",
    "build_external_selection_profile",
    "normalize_source_bindings",
    "seal_template_profile",
    "validate_builtin_profile_current",
    "validate_template_profile",
]
