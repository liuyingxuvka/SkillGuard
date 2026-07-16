"""Exact, target-neutral native evidence identities.

This module validates identity, location, and freshness bindings only.  It
never interprets a target skill's purpose, protected failures, domain oracle,
or good/bad cases.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contract_compiler import canonical_hash, canonical_json_bytes


TARGET_NATIVE_DEPTH_RECEIPT_SCHEMA = "skillguard.target_native_depth_receipt.current"
NATIVE_EVIDENCE_IDENTITY_SCHEMA = "skillguard.native_evidence_identity.current"
NATIVE_OBSERVATION_LOCATOR_SCHEMA = "skillguard.native_observation_locator.current"
DEPTH_EVIDENCE_DOMAINS = frozenset(
    {"fixture_validation", "capability_validation", "scheduled_production"}
)
GENERIC_IDENTIFIERS = frozenset(
    {
        "all",
        "default",
        "first",
        "generic",
        "item",
        "one",
        "obligation",
        "phase",
        "second",
        "self",
        "skill",
        "step",
        "target",
        "two",
        "check",
        "route",
    }
)
_ORDINAL_IDENTIFIER = re.compile(
    r"^(?:obligation|phase|step|item)(?:(?:::|[-_.])(?:id[-_.]?)?)?\d+$",
    re.IGNORECASE,
)
_SHA256 = re.compile(r"^[0-9A-F]{64}$")


@dataclass(frozen=True)
class NativeEvidenceIdentityError(ValueError):
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def _text(value: object, code: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise NativeEvidenceIdentityError(code, "non-empty text required")
    return text


def _hash(value: object, code: str) -> str:
    text = _text(value, code).upper()
    if not _SHA256.fullmatch(text):
        raise NativeEvidenceIdentityError(code, text)
    return text


def _unique_strings(value: object, code: str, *, nonempty: bool = True) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise NativeEvidenceIdentityError(code, "string array required")
    result = [str(item or "").strip() for item in value]
    if (
        any(not item for item in result)
        or len(result) != len(set(result))
        or (nonempty and not result)
    ):
        raise NativeEvidenceIdentityError(code, "unique non-empty strings required")
    return sorted(result)


def _reject_unknown(value: Mapping[str, Any], allowed: set[str], code: str) -> None:
    unknown = sorted(str(key) for key in value if key not in allowed)
    if unknown:
        raise NativeEvidenceIdentityError(code, ",".join(unknown))


def validate_identifier(
    value: object,
    *,
    code_prefix: str,
    allowed_ids: Sequence[str] | None = None,
) -> str:
    identifier = _text(value, f"{code_prefix}_missing")
    lowered = identifier.lower()
    tokens = [token for token in re.split(r"[:/._-]+", lowered) if token]
    meaningful = [
        token
        for token in tokens
        if token not in GENERIC_IDENTIFIERS
        and not token.isdigit()
        and not re.fullmatch(r"(?:id)?\d+", token)
    ]
    if lowered in GENERIC_IDENTIFIERS or not meaningful:
        raise NativeEvidenceIdentityError(f"{code_prefix}_generic", identifier)
    if _ORDINAL_IDENTIFIER.fullmatch(lowered):
        raise NativeEvidenceIdentityError(f"{code_prefix}_ordinal_only", identifier)
    if allowed_ids is not None and identifier not in {str(item) for item in allowed_ids}:
        raise NativeEvidenceIdentityError(f"{code_prefix}_undeclared", identifier)
    return identifier


def depth_profile_hash(contract: Mapping[str, Any]) -> str:
    profile = contract.get("depth_profile")
    if not isinstance(profile, Mapping):
        raise NativeEvidenceIdentityError(
            "native_identity_depth_profile_missing", "depth_profile"
        )
    return canonical_hash(profile)


def _portable_run_ref(value: object, code: str) -> tuple[dict[str, str], Path]:
    if not isinstance(value, Mapping):
        raise NativeEvidenceIdentityError(code, "portable reference required")
    _reject_unknown(value, {"path_token", "relative_path"}, f"{code}_unknown_field")
    if value.get("path_token") != "run_root":
        raise NativeEvidenceIdentityError(f"{code}_token_invalid", str(value.get("path_token")))
    text = str(value.get("relative_path", "")).replace("\\", "/")
    if (
        not text
        or text.startswith("/")
        or re.match(r"^[A-Za-z]:", text)
        or any(part in {"", ".", ".."} for part in text.split("/"))
    ):
        raise NativeEvidenceIdentityError(f"{code}_path_invalid", text)
    return {"path_token": "run_root", "relative_path": text}, Path(*text.split("/"))


def load_native_receipt(
    run_root: Path,
    artifact_ref: object,
    expected_file_hash: object,
) -> tuple[dict[str, Any], dict[str, str], bytes]:
    locator, relative = _portable_run_ref(artifact_ref, "native_receipt_artifact_ref")
    root = run_root.resolve()
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
        body = path.read_bytes()
    except (ValueError, OSError) as exc:
        raise NativeEvidenceIdentityError(
            "native_receipt_artifact_unreadable", locator["relative_path"]
        ) from exc
    if not body or len(body) > 64 * 1024 * 1024:
        raise NativeEvidenceIdentityError(
            "native_receipt_artifact_size_invalid", str(len(body))
        )
    actual = hashlib.sha256(body).hexdigest().upper()
    if actual != _hash(expected_file_hash, "native_receipt_hash_invalid"):
        raise NativeEvidenceIdentityError("native_receipt_hash_mismatch", actual)
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise NativeEvidenceIdentityError(
            "native_receipt_json_invalid", type(exc).__name__
        ) from exc
    if not isinstance(payload, Mapping):
        raise NativeEvidenceIdentityError("native_receipt_not_object", type(payload).__name__)
    receipt = dict(payload)
    unsigned = dict(receipt)
    stored_hash = unsigned.pop("receipt_hash", None)
    if stored_hash != canonical_hash(unsigned):
        raise NativeEvidenceIdentityError(
            "native_receipt_internal_hash_mismatch", str(stored_hash or "")
        )
    return receipt, locator, body


def build_target_native_receipt(payload: Mapping[str, Any]) -> dict[str, Any]:
    receipt = dict(payload)
    receipt.pop("receipt_hash", None)
    receipt["receipt_hash"] = canonical_hash(receipt)
    return receipt


def native_receipt_bytes(payload: Mapping[str, Any]) -> bytes:
    return canonical_json_bytes(build_target_native_receipt(payload))


def _json_pointer(document: Any, pointer: str) -> Any:
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise NativeEvidenceIdentityError(
            "native_observation_locator_coordinate_invalid", pointer
        )
    value = document
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(value, Mapping):
            if token not in value:
                raise NativeEvidenceIdentityError(
                    "native_observation_locator_coordinate_missing", pointer
                )
            value = value[token]
        elif isinstance(value, list):
            if not token.isdigit() or int(token) >= len(value):
                raise NativeEvidenceIdentityError(
                    "native_observation_locator_coordinate_missing", pointer
                )
            value = value[int(token)]
        else:
            raise NativeEvidenceIdentityError(
                "native_observation_locator_coordinate_missing", pointer
            )
    return value


def validate_native_observation_locator(
    locator_value: object,
    *,
    receipt: Mapping[str, Any],
    native_owner_id: str,
    target_obligation_ids: Sequence[str],
) -> dict[str, Any]:
    if not isinstance(locator_value, Mapping):
        raise NativeEvidenceIdentityError(
            "native_observation_locator_missing", "object required"
        )
    locator = dict(locator_value)
    _reject_unknown(
        locator,
        {
            "schema_version",
            "locator_type",
            "resolver_owner_id",
            "native_object_id",
            "native_coordinate",
            "content_sha256",
            "locator_fingerprint",
        },
        "native_observation_locator_unknown_field",
    )
    if locator.get("schema_version") != NATIVE_OBSERVATION_LOCATOR_SCHEMA:
        raise NativeEvidenceIdentityError(
            "native_observation_locator_schema_mismatch",
            str(locator.get("schema_version", "missing")),
        )
    if locator.get("locator_type") != "json_pointer.v1":
        raise NativeEvidenceIdentityError(
            "native_observation_locator_type_unregistered",
            str(locator.get("locator_type", "missing")),
        )
    if locator.get("resolver_owner_id") != native_owner_id:
        raise NativeEvidenceIdentityError(
            "native_observation_locator_resolver_owner_mismatch",
            str(locator.get("resolver_owner_id", "missing")),
        )
    object_id = validate_identifier(
        locator.get("native_object_id"), code_prefix="native_observation_object"
    )
    coordinate = _text(
        locator.get("native_coordinate"),
        "native_observation_locator_coordinate_missing",
    )
    if not re.fullmatch(r"/observations/\d+/content", coordinate):
        raise NativeEvidenceIdentityError(
            "native_observation_locator_coordinate_not_observation", coordinate
        )
    material = _json_pointer(receipt, coordinate)
    content_hash = canonical_hash(material)
    if content_hash != _hash(
        locator.get("content_sha256"),
        "native_observation_locator_content_hash_invalid",
    ):
        raise NativeEvidenceIdentityError(
            "native_observation_locator_content_hash_mismatch", coordinate
        )
    observation_pointer = coordinate.rsplit("/", 1)[0]
    observation = _json_pointer(receipt, observation_pointer)
    if not isinstance(observation, Mapping) or observation.get("native_object_id") != object_id:
        raise NativeEvidenceIdentityError(
            "native_observation_locator_object_mismatch", object_id
        )
    if observation.get("observation_origin") in {
        "declared_catalog",
        "manifest_catalog",
        "phase_catalog",
    }:
        raise NativeEvidenceIdentityError(
            "catalog_only_phase_expansion", str(observation.get("observation_origin"))
        )
    observed_obligations = _unique_strings(
        observation.get("target_obligation_ids"),
        "native_observation_locator_obligations_invalid",
    )
    if not set(target_obligation_ids).issubset(observed_obligations):
        raise NativeEvidenceIdentityError(
            "native_observation_locator_obligation_mismatch",
            ",".join(sorted(set(target_obligation_ids) - set(observed_obligations))),
        )
    projection = {
        "schema_version": NATIVE_OBSERVATION_LOCATOR_SCHEMA,
        "locator_type": "json_pointer.v1",
        "resolver_owner_id": native_owner_id,
        "native_object_id": object_id,
        "native_coordinate": coordinate,
        "content_sha256": content_hash,
    }
    expected = canonical_hash(projection)
    if locator.get("locator_fingerprint") != expected:
        raise NativeEvidenceIdentityError(
            "native_observation_locator_fingerprint_mismatch", coordinate
        )
    return {**projection, "locator_fingerprint": expected}


def scheduled_production_identity(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise NativeEvidenceIdentityError(
            "scheduled_production_identity_missing", "object required"
        )
    _reject_unknown(
        value,
        {
            "scheduler_or_trigger_id",
            "scheduled_execution_id",
            "installation_receipt_id",
            "installation_receipt_hash",
            "installation_receipt_root_ref",
            "installed_runtime_fingerprint",
        },
        "scheduled_production_identity_unknown_field",
    )
    root_ref, _ = _portable_run_ref(
        value.get("installation_receipt_root_ref"),
        "scheduled_production_installation_receipt_root_ref",
    ) if isinstance(value.get("installation_receipt_root_ref"), Mapping) and value.get("installation_receipt_root_ref", {}).get("path_token") == "run_root" else ({}, Path())
    if not root_ref:
        raw_ref = value.get("installation_receipt_root_ref")
        if not isinstance(raw_ref, Mapping) or raw_ref.get("path_token") != "active_skill_root":
            raise NativeEvidenceIdentityError(
                "scheduled_production_installation_receipt_root_ref_invalid",
                str(raw_ref),
            )
        relative = str(raw_ref.get("relative_path", "")).replace("\\", "/")
        if not relative or relative.startswith("/") or any(part in {"", ".", ".."} for part in relative.split("/")):
            raise NativeEvidenceIdentityError(
                "scheduled_production_installation_receipt_root_ref_invalid", relative
            )
        root_ref = {"path_token": "active_skill_root", "relative_path": relative}
    return {
        "scheduler_or_trigger_id": _text(value.get("scheduler_or_trigger_id"), "scheduled_production_trigger_missing"),
        "scheduled_execution_id": _text(value.get("scheduled_execution_id"), "scheduled_production_execution_missing"),
        "installation_receipt_id": _text(value.get("installation_receipt_id"), "scheduled_production_installation_receipt_missing"),
        "installation_receipt_hash": _hash(value.get("installation_receipt_hash"), "scheduled_production_installation_receipt_hash_invalid"),
        "installation_receipt_root_ref": root_ref,
        "installed_runtime_fingerprint": _hash(value.get("installed_runtime_fingerprint"), "scheduled_production_runtime_fingerprint_invalid"),
    }


def validate_native_identity_common(
    payload: Mapping[str, Any],
    *,
    contract: Mapping[str, Any],
    check: Mapping[str, Any],
    run: Mapping[str, Any],
    current_fingerprints: Mapping[str, Any],
    target_obligation_ids: Sequence[str],
) -> dict[str, Any]:
    profile = contract.get("depth_profile")
    if not isinstance(profile, Mapping):
        raise NativeEvidenceIdentityError(
            "native_identity_depth_profile_missing", "depth_profile"
        )
    target_skill_id = validate_identifier(
        payload.get("target_skill_id"),
        code_prefix="native_identity_target_skill_id",
        allowed_ids=[str(contract.get("skill_id", ""))],
    )
    expected_contract_hash = _hash(
        run.get("contract_hash"), "native_identity_run_contract_hash_invalid"
    )
    if payload.get("target_contract_hash") != expected_contract_hash:
        raise NativeEvidenceIdentityError(
            "native_identity_target_contract_hash_mismatch",
            str(payload.get("target_contract_hash", "missing")),
        )
    expected_profile_hash = depth_profile_hash(contract)
    if payload.get("depth_profile_hash") != expected_profile_hash:
        raise NativeEvidenceIdentityError(
            "native_identity_depth_profile_hash_mismatch",
            str(payload.get("depth_profile_hash", "missing")),
        )
    expected_request = _hash(
        run.get("request_fingerprint"),
        "native_identity_run_request_fingerprint_invalid",
    )
    if payload.get("request_fingerprint") != expected_request:
        raise NativeEvidenceIdentityError(
            "native_identity_request_fingerprint_mismatch",
            str(payload.get("request_fingerprint", "missing")),
        )
    expected_owner = _text(profile.get("native_owner_id"), "native_identity_profile_owner_missing")
    if payload.get("native_owner_id") != expected_owner:
        raise NativeEvidenceIdentityError(
            "native_identity_owner_mismatch", str(payload.get("native_owner_id", "missing"))
        )
    route_id = validate_identifier(
        payload.get("native_route_id"),
        code_prefix="native_identity_route_id",
        allowed_ids=[str(item) for item in profile.get("native_route_ids", [])],
    )
    if route_id != str(check.get("native_route_id", "")):
        raise NativeEvidenceIdentityError("native_identity_route_check_mismatch", route_id)
    native_check_id = validate_identifier(
        payload.get("native_check_id"),
        code_prefix="native_identity_check_id",
        allowed_ids=[str(check.get("check_id", ""))],
    )
    if payload.get("run_id") != run.get("run_id"):
        raise NativeEvidenceIdentityError(
            "native_identity_run_id_mismatch", str(payload.get("run_id", "missing"))
        )
    contract_obligations = [
        str(row.get("obligation_id", ""))
        for row in contract.get("obligations", [])
        if isinstance(row, Mapping)
    ]
    obligations = [
        validate_identifier(
            item,
            code_prefix="native_identity_obligation_id",
            allowed_ids=contract_obligations,
        )
        for item in _unique_strings(
            payload.get("target_obligation_ids"),
            "native_identity_obligation_ids_invalid",
        )
    ]
    if sorted(obligations) != sorted(str(item) for item in target_obligation_ids):
        raise NativeEvidenceIdentityError(
            "native_identity_obligation_set_mismatch", ",".join(obligations)
        )
    domain = _text(payload.get("evidence_domain"), "native_identity_domain_missing")
    if domain not in DEPTH_EVIDENCE_DOMAINS:
        raise NativeEvidenceIdentityError("native_identity_domain_invalid", domain)
    if domain != str(check.get("depth_evidence_domain", "")):
        raise NativeEvidenceIdentityError(
            "native_identity_domain_mismatch",
            f"observed={domain};expected={check.get('depth_evidence_domain', '')}",
        )
    schedule: dict[str, Any] = {}
    if domain == "scheduled_production":
        schedule = scheduled_production_identity(payload.get("scheduled_production_identity"))
    elif payload.get("scheduled_production_identity") not in (None, {}):
        raise NativeEvidenceIdentityError(
            "native_identity_schedule_for_nonproduction", domain
        )
    return {
        "schema_version": NATIVE_EVIDENCE_IDENTITY_SCHEMA,
        "target_skill_id": target_skill_id,
        "target_contract_hash": expected_contract_hash,
        "depth_profile_hash": expected_profile_hash,
        "request_fingerprint": expected_request,
        "native_owner_id": expected_owner,
        "native_route_id": route_id,
        "native_check_id": native_check_id,
        "run_id": str(run.get("run_id", "")),
        "target_obligation_ids": sorted(obligations),
        "evidence_domain": domain,
        "scheduled_production_identity": schedule,
    }


def validate_receipt_identity(
    receipt: Mapping[str, Any],
    *,
    common: Mapping[str, Any],
    expected_receipt_id: str,
) -> None:
    if receipt.get("schema_version") != TARGET_NATIVE_DEPTH_RECEIPT_SCHEMA:
        raise NativeEvidenceIdentityError(
            "native_receipt_schema_mismatch", str(receipt.get("schema_version", "missing"))
        )
    for field in (
        "target_skill_id",
        "target_contract_hash",
        "depth_profile_hash",
        "request_fingerprint",
        "native_owner_id",
        "native_route_id",
        "native_check_id",
        "run_id",
        "target_obligation_ids",
        "evidence_domain",
        "scheduled_production_identity",
    ):
        if receipt.get(field) != common.get(field):
            raise NativeEvidenceIdentityError(
                f"native_receipt_{field}_mismatch", str(receipt.get(field, "missing"))
            )
    if receipt.get("native_receipt_id") != expected_receipt_id:
        raise NativeEvidenceIdentityError(
            "native_receipt_id_mismatch", str(receipt.get("native_receipt_id", "missing"))
        )
    observations = receipt.get("observations")
    if not isinstance(observations, list) or not observations or any(
        not isinstance(row, Mapping) for row in observations
    ):
        raise NativeEvidenceIdentityError(
            "native_receipt_observations_invalid", "non-empty object array required"
        )


def build_contribution_identity(
    common: Mapping[str, Any],
    *,
    native_receipt_id: str,
    native_receipt_hash: str,
    native_receipt_artifact_ref: Mapping[str, str],
    native_observation_locator: Mapping[str, Any],
) -> dict[str, Any]:
    identity = {
        **dict(common),
        "native_receipt_id": native_receipt_id,
        "native_receipt_hash": native_receipt_hash,
        "native_receipt_artifact_ref": dict(native_receipt_artifact_ref),
        "native_observation_locator": dict(native_observation_locator),
        "observation_range_fingerprint": str(
            native_observation_locator.get("locator_fingerprint", "")
        ),
    }
    identity["native_evidence_identity_hash"] = canonical_hash(identity)
    return identity
