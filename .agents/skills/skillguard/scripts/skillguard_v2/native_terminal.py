"""Exact target-native terminal receipts and verifier-owned applicability decisions."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from .contract_compiler import canonical_hash, canonical_json_bytes
from .contract_schema import DEPTH_EVIDENCE_DOMAINS
from .execution_depth import EXECUTION_DEPTH_PASS, load_target_execution_receipts
from .installation_receipt import (
    VerifiedInstallationContext,
    verify_scheduled_production_installation_identity,
)
from .native_evidence_identity import (
    NativeEvidenceIdentityError,
    scheduled_production_identity,
)
from .run_store import load_run, utc_now


NATIVE_NOOP_RECEIPT_SCHEMA = "skillguard.native_noop_receipt.v2"
NATIVE_TERMINAL_RECEIPT_SCHEMA = "skillguard.native_terminal_receipt.v2"
OBLIGATION_APPLICABILITY_RECEIPT_SCHEMA = (
    "skillguard.obligation_applicability_receipt.v2"
)
APPLICABILITY_VERIFIER_ID = "skillguard.route_branch_applicability_verifier"
APPLICABILITY_VERIFIER_VERSION = "1"
SHA256_CHARACTERS = frozenset("0123456789ABCDEF")
STANDARD_CLOSURE_PROFILES = frozenset({"enforced"})


@dataclass(frozen=True)
class NativeTerminalError(ValueError):
    code: str
    message: str
    field: str = ""

    def __str__(self) -> str:
        suffix = f" ({self.field})" if self.field else ""
        return f"{self.code}: {self.message}{suffix}"


@dataclass(frozen=True)
class NativeTerminalResolution:
    receipt: Mapping[str, Any]
    receipt_ref: Mapping[str, str]
    artifact_sha256: str
    route_requirement: Mapping[str, Any]
    applicability_receipts: tuple[Mapping[str, Any], ...]

    @property
    def route_id(self) -> str:
        return str(self.receipt.get("native_route_id", ""))

    @property
    def branch_id(self) -> str:
        return str(self.receipt.get("branch_id", ""))

    @property
    def is_noop(self) -> bool:
        return bool(self.not_applicable_obligation_ids)

    @property
    def branch_required_obligation_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                str(item)
                for item in self.route_requirement.get("required_obligation_ids", [])
            )
        )

    @property
    def not_applicable_obligation_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                str(row.get("obligation_id", ""))
                for row in self.route_requirement.get("applicability_rules", [])
                if isinstance(row, Mapping)
                and row.get("allowed_disposition") == "not_applicable"
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "verified",
            "native_terminal_receipt_ref": dict(self.receipt_ref),
            "native_terminal_receipt_id": str(self.receipt.get("receipt_id", "")),
            "native_terminal_receipt_hash": str(self.receipt.get("receipt_hash", "")),
            "native_terminal_artifact_sha256": self.artifact_sha256,
            "native_route_id": self.route_id,
            "branch_id": self.branch_id,
            "terminal_kind": str(self.receipt.get("terminal_kind", "")),
            "closure_profile": str(self.receipt.get("closure_profile", "")),
            "closure_disposition": str(
                self.receipt.get("closure_disposition", "")
            ),
            "evidence_domain": str(self.receipt.get("evidence_domain", "")),
            "depth_receipt_id": str(self.receipt.get("depth_receipt_id", "")),
            "branch_required_obligation_ids": list(
                self.branch_required_obligation_ids
            ),
            "not_applicable_obligation_ids": list(
                self.not_applicable_obligation_ids
            ),
            "applicability_receipt_ids": [
                str(row.get("receipt_id", ""))
                for row in self.applicability_receipts
            ],
            "applicability_receipt_hashes": [
                str(row.get("receipt_hash", ""))
                for row in self.applicability_receipts
            ],
        }


def _expected_closure_disposition(*, profile: str) -> str:
    if profile not in STANDARD_CLOSURE_PROFILES:
        raise NativeTerminalError(
            "native_terminal_closure_profile_invalid", profile, "profile"
        )
    return "terminal_completion"


def _required_text(payload: Mapping[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise NativeTerminalError(
            "native_terminal_required_field_missing", field, field
        )
    return value


def _require_sha256(payload: Mapping[str, Any], field: str) -> str:
    value = _required_text(payload, field).upper()
    if len(value) != 64 or any(character not in SHA256_CHARACTERS for character in value):
        raise NativeTerminalError(
            "native_terminal_hash_invalid", str(payload.get(field, "")), field
        )
    return value


def _string_set(payload: Mapping[str, Any], field: str) -> set[str]:
    value = payload.get(field)
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes))
        or not value
        or any(not isinstance(item, str) or not item for item in value)
    ):
        raise NativeTerminalError(
            "native_terminal_string_array_invalid", field, field
        )
    values = {str(item) for item in value}
    if len(values) != len(value):
        raise NativeTerminalError(
            "native_terminal_string_array_duplicate", field, field
        )
    return values


def normalize_run_root_ref(
    run_root: Path, artifact_ref: str | Mapping[str, Any]
) -> tuple[dict[str, str], Path]:
    if isinstance(artifact_ref, str):
        relative_text = artifact_ref
    elif isinstance(artifact_ref, Mapping):
        if artifact_ref.get("path_token") != "run_root":
            raise NativeTerminalError(
                "native_terminal_ref_token_invalid",
                str(artifact_ref.get("path_token", "")),
                "path_token",
            )
        relative_text = str(artifact_ref.get("relative_path", ""))
    else:
        raise NativeTerminalError(
            "native_terminal_ref_invalid", "portable run_root reference required"
        )
    relative = PurePosixPath(relative_text.replace("\\", "/"))
    relative_parts = relative.parts
    if (
        not relative_text
        or relative.is_absolute()
        or not relative_parts
        or ".." in relative_parts
        or ":" in relative_parts[0]
    ):
        raise NativeTerminalError(
            "native_terminal_ref_not_portable", relative_text, "relative_path"
        )
    root = run_root.resolve()
    path = (root / Path(*relative_parts)).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise NativeTerminalError(
            "native_terminal_ref_escape", relative_text, "relative_path"
        ) from exc
    return {
        "path_token": "run_root",
        "relative_path": relative.as_posix(),
    }, path


def _load_json_artifact(path: Path, *, code: str) -> tuple[Mapping[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NativeTerminalError(code, type(exc).__name__) from exc
    if not isinstance(payload, Mapping):
        raise NativeTerminalError(code, "receipt must be a JSON object")
    return payload, raw


def _receipt_hash(payload: Mapping[str, Any]) -> str:
    unsigned = dict(payload)
    unsigned.pop("receipt_hash", None)
    return canonical_hash(unsigned)


def _expected_receipt_id(payload: Mapping[str, Any], prefix: str) -> str:
    identity = dict(payload)
    identity.pop("receipt_id", None)
    identity.pop("receipt_hash", None)
    return f"{prefix}-{canonical_hash(identity)[:24].lower()}"


def _profile_route_requirement(
    contract: Mapping[str, Any],
    profile: str,
    route_id: str,
    branch_id: str,
) -> Mapping[str, Any]:
    profile_row = next(
        (
            row
            for row in contract.get("closure_profiles", [])
            if isinstance(row, Mapping) and row.get("profile_id") == profile
        ),
        None,
    )
    if profile_row is None:
        raise NativeTerminalError("closure_profile_missing", profile, "profile")
    matches: list[Mapping[str, Any]] = []
    for row in profile_row.get("route_branch_requirements", []):
        if not isinstance(row, Mapping):
            continue
        if row.get("native_route_id") == route_id and branch_id in row.get(
            "branch_ids", []
        ):
            matches.append(row)
    if len(matches) != 1:
        code = (
            "unknown_native_branch"
            if not matches
            else "route_branch_ownership_overlap"
        )
        raise NativeTerminalError(code, f"{route_id}:{branch_id}", "branch_id")
    return matches[0]


def contract_has_branch_requirements(
    contract: Mapping[str, Any], profile: str, selected_route_ids: Sequence[str]
) -> bool:
    selected = {str(item) for item in selected_route_ids}
    for profile_row in contract.get("closure_profiles", []):
        if not isinstance(profile_row, Mapping) or profile_row.get("profile_id") != profile:
            continue
        return any(
            isinstance(row, Mapping)
            and str(row.get("native_route_id", "")) in selected
            for row in profile_row.get("route_branch_requirements", [])
        )
    return False


def _native_check_covers_branch(
    contract: Mapping[str, Any], check_id: str, obligation_ids: set[str]
) -> bool:
    obligations = {
        str(row.get("obligation_id", "")): row
        for row in contract.get("obligations", [])
        if isinstance(row, Mapping)
    }
    return all(
        check_id in {
            str(item) for item in obligations.get(obligation_id, {}).get("required_check_ids", [])
        }
        for obligation_id in obligation_ids
    )


def _select_current_depth_receipt(
    receipts: Sequence[Mapping[str, Any]],
    *,
    target_skill_id: str,
    contract_hash: str,
    native_owner_id: str,
    run_id: str,
    native_check_id: str,
) -> Mapping[str, Any]:
    """Select one exact current PASS without history-order fallback."""

    matches: list[Mapping[str, Any]] = []
    for receipt in receipts:
        raw_check_ids = receipt.get("native_check_ids", [])
        if isinstance(raw_check_ids, (str, bytes)) or not isinstance(
            raw_check_ids, Sequence
        ):
            continue
        check_ids = {str(item) for item in raw_check_ids}
        if (
            receipt.get("status") == EXECUTION_DEPTH_PASS
            and receipt.get("evidence_domain") in DEPTH_EVIDENCE_DOMAINS
            and receipt.get("target_skill_id") == target_skill_id
            and receipt.get("contract_hash") == contract_hash
            and receipt.get("native_owner_id") == native_owner_id
            and receipt.get("run_id") == run_id
            and native_check_id in check_ids
        ):
            matches.append(receipt)
    if not matches:
        raise NativeTerminalError(
            "native_noop_depth_receipt_missing",
            f"current PASS for {native_check_id}",
            "native_check_ids",
        )
    if len(matches) != 1:
        raise NativeTerminalError(
            "native_noop_depth_receipt_ambiguous",
            f"{native_check_id}:{len(matches)}",
            "native_check_ids",
        )
    return matches[0]


def _validate_depth_evidence_identity(
    receipt: Mapping[str, Any],
    *,
    verified_installation_context: VerifiedInstallationContext | None = None,
) -> tuple[str, Mapping[str, Any]]:
    evidence_domain = str(receipt.get("evidence_domain", ""))
    if evidence_domain not in DEPTH_EVIDENCE_DOMAINS:
        raise NativeTerminalError(
            "native_terminal_evidence_domain_invalid",
            evidence_domain,
            "evidence_domain",
        )
    scheduled = receipt.get("scheduled_production_identity")
    if evidence_domain != "scheduled_production":
        if scheduled not in (None, {}):
            raise NativeTerminalError(
                "native_terminal_nonproduction_schedule_identity_forbidden",
                evidence_domain,
                "scheduled_production_identity",
            )
        return evidence_domain, {}
    try:
        normalized = scheduled_production_identity(scheduled)
    except NativeEvidenceIdentityError as exc:
        raise NativeTerminalError(
            "scheduled_production_identity_invalid",
            str(exc),
            "scheduled_production_identity",
        ) from exc
    try:
        verify_scheduled_production_installation_identity(
            normalized,
            verified_context=verified_installation_context,
        )
    except (OSError, ValueError) as exc:
        raise NativeTerminalError(
            "scheduled_production_installation_not_current",
            str(exc),
            "scheduled_production_identity",
        ) from exc
    return evidence_domain, normalized


def _build_applicability_receipts(
    terminal_receipt: Mapping[str, Any],
    route_requirement: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    if not route_requirement.get("applicability_rules"):
        return ()
    rows: list[Mapping[str, Any]] = []
    for rule in route_requirement.get("applicability_rules", []):
        if not isinstance(rule, Mapping):
            continue
        if rule.get("allowed_disposition") != "not_applicable":
            raise NativeTerminalError(
                "applicability_disposition_invalid",
                str(rule.get("allowed_disposition", "")),
            )
        receipt: dict[str, Any] = {
            "schema_version": OBLIGATION_APPLICABILITY_RECEIPT_SCHEMA,
            "target_skill_id": str(terminal_receipt.get("target_skill_id", "")),
            "target_contract_hash": str(
                terminal_receipt.get("target_contract_hash", "")
            ),
            "native_owner_id": str(terminal_receipt.get("native_owner_id", "")),
            "native_route_id": str(terminal_receipt.get("native_route_id", "")),
            "branch_id": str(terminal_receipt.get("branch_id", "")),
            "run_id": str(terminal_receipt.get("run_id", "")),
            "obligation_id": str(rule.get("obligation_id", "")),
            "disposition": "not_applicable",
            "reason_code": "verified_target_branch_not_applicable",
            "native_terminal_receipt_id": str(
                terminal_receipt.get("receipt_id", "")
            ),
            "native_terminal_receipt_hash": str(
                terminal_receipt.get("receipt_hash", "")
            ),
            "verifier_check_id": str(rule.get("verifier_check_id", "")),
            "verifier_id": APPLICABILITY_VERIFIER_ID,
            "verifier_version": APPLICABILITY_VERIFIER_VERSION,
            "evidence_witness_consumed": False,
            "created_at": str(terminal_receipt.get("created_at", "")),
        }
        receipt["receipt_id"] = _expected_receipt_id(
            receipt, "applicability"
        )
        receipt["receipt_hash"] = _receipt_hash(receipt)
        rows.append(receipt)
    return tuple(rows)


def build_target_native_terminal_receipt(
    run_root: Path,
    contract: Mapping[str, Any],
    *,
    profile: str,
    native_route_id: str,
    branch_id: str,
    native_check_id: str,
    native_receipt_artifact_ref: str | Mapping[str, Any],
    observed_state: Mapping[str, Any],
    created_at: str | None = None,
    verified_installation_context: VerifiedInstallationContext | None = None,
) -> dict[str, Any]:
    """Build a target-owned terminal receipt from the exact latest depth receipt.

    This is the supported producer entry point between supervisor stage 1 and
    stage 2. It never fabricates a completion witness: branches with verifier-
    approved not-applicable rules produce conditional no-op receipts, while
    branches without those rules retain every required obligation. Every
    accepted receipt represents terminal completion.
    """

    run = load_run(run_root)
    if native_route_id not in {str(item) for item in run.get("route_ids", [])}:
        raise NativeTerminalError(
            "native_terminal_route_mismatch", native_route_id, "native_route_id"
        )
    closure_disposition = _expected_closure_disposition(profile=profile)
    depth_profile = contract.get("depth_profile")
    if not isinstance(depth_profile, Mapping):
        raise NativeTerminalError(
            "native_noop_depth_contract_missing", "depth_profile"
        )
    requirement = _profile_route_requirement(
        contract, profile, native_route_id, branch_id
    )
    obligation_ids = sorted(
        str(item) for item in requirement.get("required_obligation_ids", [])
    )
    if not obligation_ids:
        raise NativeTerminalError(
            "native_terminal_obligation_set_missing",
            f"{native_route_id}:{branch_id}",
            "target_obligation_ids",
        )
    if not _native_check_covers_branch(
        contract, native_check_id, set(obligation_ids)
    ):
        raise NativeTerminalError(
            "native_terminal_check_mismatch", native_check_id, "native_check_id"
        )
    depth_receipts = load_target_execution_receipts(run_root)
    depth_receipt = _select_current_depth_receipt(
        depth_receipts,
        target_skill_id=str(contract.get("skill_id", "")),
        contract_hash=str(contract.get("contract_hash", "")),
        native_owner_id=str(depth_profile.get("native_owner_id", "")),
        run_id=str(run.get("run_id", "")),
        native_check_id=native_check_id,
    )
    for field, expected in (
        ("target_skill_id", contract.get("skill_id")),
        ("contract_hash", contract.get("contract_hash")),
        ("native_owner_id", depth_profile.get("native_owner_id")),
        ("run_id", run.get("run_id")),
    ):
        if depth_receipt.get(field) != expected:
            raise NativeTerminalError(
                f"native_terminal_depth_{field}_mismatch",
                str(depth_receipt.get(field, "")),
                field,
            )
    if depth_receipt.get("status") != EXECUTION_DEPTH_PASS:
        raise NativeTerminalError(
            "native_noop_depth_receipt_not_passed",
            str(depth_receipt.get("status", "")),
            "status",
        )
    if native_route_id not in {
        str(item) for item in depth_receipt.get("native_route_ids", [])
    }:
        raise NativeTerminalError(
            "native_terminal_depth_route_mismatch",
            native_route_id,
            "native_route_ids",
        )
    evidence_domain, scheduled = _validate_depth_evidence_identity(
        depth_receipt,
        verified_installation_context=verified_installation_context,
    )
    normalized_native_ref, native_path = normalize_run_root_ref(
        run_root, native_receipt_artifact_ref
    )
    try:
        native_bytes = native_path.read_bytes()
    except OSError as exc:
        raise NativeTerminalError(
            "native_terminal_native_receipt_unreadable", type(exc).__name__
        ) from exc
    is_noop = bool(requirement.get("applicability_rules"))
    receipt: dict[str, Any] = {
        "schema_version": (
            NATIVE_NOOP_RECEIPT_SCHEMA
            if is_noop
            else NATIVE_TERMINAL_RECEIPT_SCHEMA
        ),
        "target_skill_id": str(contract.get("skill_id", "")),
        "target_contract_hash": str(contract.get("contract_hash", "")),
        "depth_profile_hash": canonical_hash(depth_profile),
        "native_owner_id": str(depth_profile.get("native_owner_id", "")),
        "native_route_id": native_route_id,
        "native_check_id": native_check_id,
        "run_id": str(run.get("run_id", "")),
        "branch_id": branch_id,
        "terminal_kind": "conditional_noop" if is_noop else "completed_branch",
        "closure_profile": profile,
        "closure_disposition": closure_disposition,
        "reason_code": branch_id,
        "observed_state_fingerprint": canonical_hash(dict(observed_state)),
        "target_obligation_ids": obligation_ids,
        "evidence_domain": evidence_domain,
        "scheduled_production_identity": dict(scheduled),
        "depth_receipt_id": str(depth_receipt.get("receipt_id", "")),
        "depth_receipt_hash": str(depth_receipt.get("receipt_hash", "")),
        "native_receipt_artifact_ref": normalized_native_ref,
        "native_receipt_hash": hashlib.sha256(native_bytes).hexdigest().upper(),
        "created_at": created_at or utc_now(),
    }
    prefix = "native-noop" if is_noop else "native-terminal"
    receipt["receipt_id"] = _expected_receipt_id(receipt, prefix)
    receipt["receipt_hash"] = _receipt_hash(receipt)
    return receipt


def write_target_native_terminal_receipt(
    run_root: Path,
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Persist a built terminal receipt immutably and return its portable ref."""

    schema = str(receipt.get("schema_version", ""))
    if schema == NATIVE_NOOP_RECEIPT_SCHEMA:
        prefix = "native-noop"
    elif schema == NATIVE_TERMINAL_RECEIPT_SCHEMA:
        prefix = "native-terminal"
    else:
        raise NativeTerminalError(
            "native_terminal_schema_invalid", schema, "schema_version"
        )
    if receipt.get("receipt_id") != _expected_receipt_id(receipt, prefix):
        raise NativeTerminalError(
            "native_terminal_receipt_id_mismatch",
            str(receipt.get("receipt_id", "")),
            "receipt_id",
        )
    if receipt.get("receipt_hash") != _receipt_hash(receipt):
        raise NativeTerminalError(
            "native_terminal_receipt_hash_mismatch",
            str(receipt.get("receipt_id", "")),
            "receipt_hash",
        )
    relative = (
        Path("native-terminal")
        / "receipts"
        / f"{str(receipt['receipt_id'])}.json"
    )
    path = run_root.resolve() / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = canonical_json_bytes(dict(receipt))
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError:
        if path.read_bytes() != encoded:
            raise NativeTerminalError(
                "native_terminal_receipt_collision", path.name
            )
    else:
        try:
            os.write(descriptor, encoded)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    return {
        "receipt": dict(receipt),
        "receipt_ref": {
            "path_token": "run_root",
            "relative_path": relative.as_posix(),
        },
    }


def resolve_native_terminal_receipt(
    run_root: Path,
    contract: Mapping[str, Any],
    run: Mapping[str, Any],
    *,
    profile: str,
    artifact_ref: str | Mapping[str, Any],
    expected_route_id: str = "",
    expected_branch_id: str = "",
    verified_installation_context: VerifiedInstallationContext | None = None,
) -> NativeTerminalResolution:
    normalized_ref, path = normalize_run_root_ref(run_root, artifact_ref)
    receipt, raw = _load_json_artifact(
        path, code="native_terminal_receipt_unreadable"
    )
    schema = str(receipt.get("schema_version", ""))
    branch_id = _required_text(receipt, "branch_id")
    route_id = _required_text(receipt, "native_route_id")
    terminal_kind = _required_text(receipt, "terminal_kind")
    closure_profile = _required_text(receipt, "closure_profile")
    closure_disposition = _required_text(receipt, "closure_disposition")
    requirement = _profile_route_requirement(
        contract, profile, route_id, branch_id
    )
    is_noop = bool(requirement.get("applicability_rules"))
    if is_noop:
        if schema != NATIVE_NOOP_RECEIPT_SCHEMA or terminal_kind != "conditional_noop":
            raise NativeTerminalError(
                "native_noop_terminal_kind_invalid", terminal_kind, "terminal_kind"
            )
        id_prefix = "native-noop"
    else:
        if schema != NATIVE_TERMINAL_RECEIPT_SCHEMA or terminal_kind != "completed_branch":
            raise NativeTerminalError(
                "native_completed_terminal_kind_invalid", terminal_kind, "terminal_kind"
            )
        id_prefix = "native-terminal"
    expected_disposition = _expected_closure_disposition(profile=profile)
    if closure_profile != profile:
        raise NativeTerminalError(
            "native_terminal_closure_profile_mismatch",
            f"receipt={closure_profile}; requested={profile}",
            "closure_profile",
        )
    if closure_disposition != expected_disposition:
        raise NativeTerminalError(
            "native_terminal_closure_disposition_mismatch",
            f"receipt={closure_disposition}; expected={expected_disposition}",
            "closure_disposition",
        )

    for field in (
        "receipt_id",
        "target_skill_id",
        "target_contract_hash",
        "depth_profile_hash",
        "native_owner_id",
        "native_route_id",
        "native_check_id",
        "run_id",
        "closure_profile",
        "closure_disposition",
        "reason_code",
        "native_receipt_hash",
        "depth_receipt_id",
        "depth_receipt_hash",
        "created_at",
        "receipt_hash",
    ):
        _required_text(receipt, field)
    for field in (
        "target_contract_hash",
        "depth_profile_hash",
        "observed_state_fingerprint",
        "native_receipt_hash",
        "depth_receipt_hash",
        "receipt_hash",
    ):
        _require_sha256(receipt, field)
    if receipt.get("receipt_hash") != _receipt_hash(receipt):
        raise NativeTerminalError(
            "native_terminal_receipt_hash_mismatch", path.name, "receipt_hash"
        )
    if receipt.get("receipt_id") != _expected_receipt_id(receipt, id_prefix):
        raise NativeTerminalError(
            "native_terminal_receipt_id_mismatch",
            str(receipt.get("receipt_id", "")),
            "receipt_id",
        )
    if receipt.get("target_skill_id") != contract.get("skill_id"):
        raise NativeTerminalError(
            "native_terminal_target_skill_mismatch",
            str(receipt.get("target_skill_id", "")),
            "target_skill_id",
        )
    if receipt.get("target_contract_hash") != contract.get("contract_hash"):
        raise NativeTerminalError(
            "native_terminal_contract_hash_mismatch",
            str(receipt.get("target_contract_hash", "")),
            "target_contract_hash",
        )
    depth_profile = contract.get("depth_profile")
    if not isinstance(depth_profile, Mapping):
        raise NativeTerminalError(
            "native_noop_depth_contract_missing", "depth_profile"
        )
    if receipt.get("depth_profile_hash") != canonical_hash(depth_profile):
        raise NativeTerminalError(
            "native_terminal_depth_profile_mismatch",
            str(receipt.get("depth_profile_hash", "")),
            "depth_profile_hash",
        )
    if receipt.get("native_owner_id") != depth_profile.get("native_owner_id"):
        raise NativeTerminalError(
            "native_terminal_owner_mismatch",
            str(receipt.get("native_owner_id", "")),
            "native_owner_id",
        )
    if receipt.get("run_id") != run.get("run_id"):
        raise NativeTerminalError(
            "native_terminal_run_mismatch",
            str(receipt.get("run_id", "")),
            "run_id",
        )
    if route_id not in {str(item) for item in run.get("route_ids", [])}:
        raise NativeTerminalError(
            "native_terminal_route_mismatch", route_id, "native_route_id"
        )
    if expected_route_id and expected_route_id != route_id:
        raise NativeTerminalError(
            "native_terminal_expected_route_mismatch",
            expected_route_id,
            "expected_route_id",
        )
    if expected_branch_id and expected_branch_id != branch_id:
        raise NativeTerminalError(
            "native_terminal_expected_branch_mismatch",
            expected_branch_id,
            "expected_branch_id",
        )
    target_obligation_ids = _string_set(receipt, "target_obligation_ids")
    expected_obligation_ids = {
        str(item) for item in requirement.get("required_obligation_ids", [])
    }
    if target_obligation_ids != expected_obligation_ids:
        raise NativeTerminalError(
            "native_terminal_obligation_set_mismatch",
            ",".join(sorted(target_obligation_ids)),
            "target_obligation_ids",
        )
    native_check_id = str(receipt.get("native_check_id", ""))
    if not _native_check_covers_branch(
        contract, native_check_id, expected_obligation_ids
    ):
        raise NativeTerminalError(
            "native_terminal_check_mismatch", native_check_id, "native_check_id"
        )
    if receipt.get("reason_code") != branch_id:
        raise NativeTerminalError(
            "native_terminal_reason_mismatch",
            str(receipt.get("reason_code", "")),
            "reason_code",
        )
    evidence_domain, normalized_scheduled_identity = _validate_depth_evidence_identity(
        receipt,
        verified_installation_context=verified_installation_context,
    )

    native_artifact_ref = receipt.get("native_receipt_artifact_ref")
    if not isinstance(native_artifact_ref, Mapping):
        raise NativeTerminalError(
            "native_terminal_native_receipt_ref_missing",
            "native_receipt_artifact_ref",
        )
    _, native_artifact_path = normalize_run_root_ref(run_root, native_artifact_ref)
    try:
        native_bytes = native_artifact_path.read_bytes()
    except OSError as exc:
        raise NativeTerminalError(
            "native_terminal_native_receipt_unreadable", type(exc).__name__
        ) from exc
    if hashlib.sha256(native_bytes).hexdigest().upper() != str(
        receipt.get("native_receipt_hash", "")
    ):
        raise NativeTerminalError(
            "native_terminal_native_receipt_hash_mismatch",
            native_artifact_path.name,
            "native_receipt_hash",
        )

    try:
        depth_receipts = load_target_execution_receipts(run_root)
    except Exception as exc:
        raise NativeTerminalError(
            "native_noop_depth_receipt_invalid", getattr(exc, "code", type(exc).__name__)
        ) from exc
    depth_receipt = _select_current_depth_receipt(
        depth_receipts,
        target_skill_id=str(contract.get("skill_id", "")),
        contract_hash=str(contract.get("contract_hash", "")),
        native_owner_id=str(depth_profile.get("native_owner_id", "")),
        run_id=str(run.get("run_id", "")),
        native_check_id=native_check_id,
    )
    if receipt.get("depth_receipt_id") != depth_receipt.get("receipt_id"):
        raise NativeTerminalError(
            "native_terminal_depth_receipt_mismatch",
            str(receipt.get("depth_receipt_id", "")),
            "depth_receipt_id",
        )
    if receipt.get("depth_receipt_hash") != depth_receipt.get("receipt_hash"):
        raise NativeTerminalError(
            "native_terminal_depth_receipt_hash_mismatch",
            str(receipt.get("depth_receipt_hash", "")),
            "depth_receipt_hash",
        )
    if depth_receipt.get("scheduled_production_identity", {}) != normalized_scheduled_identity:
        raise NativeTerminalError(
            "native_terminal_scheduled_identity_mismatch",
            "terminal and depth receipts must bind the same installed scheduled execution",
            "scheduled_production_identity",
        )
    for field, expected in (
        ("target_skill_id", contract.get("skill_id")),
        ("contract_hash", contract.get("contract_hash")),
        ("native_owner_id", depth_profile.get("native_owner_id")),
        ("run_id", run.get("run_id")),
        ("evidence_domain", evidence_domain),
    ):
        if depth_receipt.get(field) != expected:
            raise NativeTerminalError(
                f"native_terminal_depth_{field}_mismatch",
                str(depth_receipt.get(field, "")),
                field,
            )
    if depth_receipt.get("status") != EXECUTION_DEPTH_PASS:
        raise NativeTerminalError(
            "native_noop_depth_receipt_not_passed",
            str(depth_receipt.get("status", "")),
            "status",
        )
    if route_id not in {
        str(item) for item in depth_receipt.get("native_route_ids", [])
    }:
        raise NativeTerminalError(
            "native_terminal_depth_route_mismatch", route_id, "native_route_ids"
        )
    applicability = _build_applicability_receipts(receipt, requirement)
    if is_noop and not applicability:
        raise NativeTerminalError(
            "native_noop_applicability_rule_missing",
            f"{route_id}:{branch_id}",
        )
    if not is_noop and applicability:
        raise NativeTerminalError(
            "native_completed_branch_applicability_forbidden",
            f"{route_id}:{branch_id}",
        )
    return NativeTerminalResolution(
        receipt=receipt,
        receipt_ref=normalized_ref,
        artifact_sha256=hashlib.sha256(raw).hexdigest().upper(),
        route_requirement=requirement,
        applicability_receipts=applicability,
    )


def persist_applicability_receipts(
    run_root: Path, receipts: Sequence[Mapping[str, Any]]
) -> tuple[Mapping[str, Any], ...]:
    root = run_root / "applicability-receipts"
    persisted: list[Mapping[str, Any]] = []
    for receipt in receipts:
        receipt_id = str(receipt.get("receipt_id", ""))
        if (
            not receipt_id
            or receipt_id
            != _expected_receipt_id(receipt, "applicability")
            or receipt.get("receipt_hash") != _receipt_hash(receipt)
        ):
            raise NativeTerminalError(
                "applicability_receipt_invalid", receipt_id, "receipt_hash"
            )
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{receipt_id}.json"
        expected = canonical_json_bytes(receipt)
        if path.is_file():
            if path.read_bytes() != expected:
                raise NativeTerminalError(
                    "applicability_receipt_collision", path.name
                )
        else:
            try:
                descriptor = os.open(
                    path,
                    os.O_WRONLY
                    | os.O_CREAT
                    | os.O_EXCL
                    | getattr(os, "O_BINARY", 0),
                )
            except FileExistsError as exc:
                raise NativeTerminalError(
                    "applicability_receipt_collision", path.name
                ) from exc
            try:
                os.write(descriptor, expected)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        persisted.append(receipt)
    return tuple(persisted)


def verify_persisted_applicability_receipts(
    run_root: Path, receipts: Sequence[Mapping[str, Any]]
) -> tuple[str, ...]:
    findings: list[str] = []
    root = run_root / "applicability-receipts"
    for receipt in receipts:
        receipt_id = str(receipt.get("receipt_id", ""))
        path = root / f"{receipt_id}.json"
        try:
            actual = path.read_bytes()
        except OSError:
            findings.append(f"applicability_receipt_missing:{receipt_id}")
            continue
        if actual != canonical_json_bytes(receipt):
            findings.append(f"applicability_receipt_tampered:{receipt_id}")
        if receipt.get("receipt_hash") != _receipt_hash(receipt):
            findings.append(f"applicability_receipt_hash_mismatch:{receipt_id}")
    return tuple(findings)


def placeholder_or_caller_applicability(receipt: Mapping[str, Any]) -> str:
    evidence = receipt.get("evidence")
    if not isinstance(evidence, Mapping):
        return ""
    if evidence.get("disposition") == "not_applicable" or evidence.get(
        "caller_approved_applicability"
    ) is True:
        return "caller_authored_applicability_rejected"
    if (
        evidence.get("placeholder") is True
        or evidence.get("synthetic") is True
        or str(evidence.get("witness_kind", "")).lower()
        in {"placeholder", "synthetic", "not_applicable"}
        or str(evidence.get("proof_kind", "")).lower()
        in {"placeholder", "synthetic", "not_applicable"}
    ):
        return "placeholder_finalize_witness_rejected"
    return ""
