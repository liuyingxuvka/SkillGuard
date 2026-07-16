"""Current canonical/stage/active installation verification receipts."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .contract_compiler import canonical_hash
from .installation import (
    _activation_receipt_current,
    _load_install_head,
    _load_transaction,
    replay_installed_smoke_currentness,
)
from .portfolio import atomic_write_json
from .runtime_fingerprint import (
    RUNTIME_CONTRACT_ID,
    RUNTIME_PROVIDER_ID,
    guard_active_installation_runtime_fingerprint,
    guard_runtime_fingerprint,
    resolve_guard_runtime_root,
)


INSTALL_VERIFICATION_SCHEMA = "skillguard.installation_verification_receipt.v1"
INSTALL_VERIFICATION_HEAD_SCHEMA = "skillguard.installation_verification_head.v1"
DEFAULT_INSTALLATION_RECEIPT_RELATIVE_PATH = ".sg-runtime/installation"
VERIFIED_INSTALLATION_CONTEXT_SCHEMA = "skillguard.verified_installation_context.v1"

_HASH_PATTERN = re.compile(r"^[A-F0-9]{64}$")
_TRANSACTION_ID_PATTERN = re.compile(r"^install-[a-f0-9]{32}$")
_RECEIPT_ID_PATTERN = re.compile(r"^installation-[a-f0-9]{24}$")
_SNAPSHOT_FIELDS = frozenset(
    {
        "transaction_id",
        "install_head_hash",
        "activation_receipt_hash",
        "stage_verification_hash",
        "post_activation_smoke_hash",
        "post_activation_member_comparisons_hash",
        "rollback_disposition",
        "canonical_source_identity",
        "installed_source_identity",
        "canonical_runtime_fingerprint",
        "installed_runtime_fingerprint",
        "current_installed_smoke_hash",
        "current_installed_smoke_command_fingerprint",
        "current_installed_smoke_environment_fingerprint",
    }
)
_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "status",
        *_SNAPSHOT_FIELDS,
        "claim_boundary",
        "receipt_id",
        "receipt_hash",
    }
)
_HEAD_FIELDS = frozenset(
    {"schema_version", "receipt_id", "receipt_hash", "receipt_ref", "head_hash"}
)
_SOURCE_IDENTITY_FIELDS = frozenset(
    {"exists", "kind", "manifest_hash", "file_count"}
)
_RUNTIME_FINGERPRINT_FIELDS = frozenset(
    {
        "runtime_id",
        "provider_id",
        "runtime_contract_id",
        "capability_ids",
        "enrollment_status",
        "file_count",
        "source_hash",
    }
)
_CONTEXT_SEAL = object()


def resolve_codex_home_root(value: Path | None = None) -> Path:
    """Resolve the user installation root without projecting it into reports."""

    return (value or Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))).resolve(
        strict=True
    )


def _require_exact_fields(
    value: Mapping[str, Any],
    expected: frozenset[str],
    *,
    label: str,
) -> None:
    actual = set(value)
    if actual != set(expected):
        missing = ",".join(sorted(set(expected) - actual))
        extra = ",".join(sorted(actual - set(expected)))
        raise ValueError(f"{label}_shape_mismatch:missing={missing}:extra={extra}")


def _require_hash(value: object, *, label: str) -> str:
    text = str(value)
    if not _HASH_PATTERN.fullmatch(text):
        raise ValueError(f"{label}_invalid")
    return text


def _validate_source_identity(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label}_invalid")
    _require_exact_fields(value, _SOURCE_IDENTITY_FIELDS, label=label)
    if value.get("exists") is not True or value.get("kind") != "directory":
        raise ValueError(f"{label}_not_current_directory")
    if isinstance(value.get("file_count"), bool) or not isinstance(
        value.get("file_count"), int
    ) or int(value["file_count"]) < 1:
        raise ValueError(f"{label}_file_count_invalid")
    _require_hash(value.get("manifest_hash"), label=f"{label}_manifest_hash")
    return dict(value)


def _validate_runtime_fingerprint(
    value: object,
    *,
    label: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label}_invalid")
    _require_exact_fields(value, _RUNTIME_FINGERPRINT_FIELDS, label=label)
    if (
        value.get("runtime_id") != "skillguard-v2"
        or value.get("provider_id") != RUNTIME_PROVIDER_ID
        or value.get("runtime_contract_id") != RUNTIME_CONTRACT_ID
        or value.get("enrollment_status") != "enrolled"
    ):
        raise ValueError(f"{label}_authority_invalid")
    capabilities = value.get("capability_ids")
    if (
        not isinstance(capabilities, list)
        or not capabilities
        or any(not isinstance(item, str) or not item for item in capabilities)
        or len(capabilities) != len(set(capabilities))
    ):
        raise ValueError(f"{label}_capability_ids_invalid")
    if isinstance(value.get("file_count"), bool) or not isinstance(
        value.get("file_count"), int
    ) or int(value["file_count"]) < 1:
        raise ValueError(f"{label}_file_count_invalid")
    _require_hash(value.get("source_hash"), label=f"{label}_source_hash")
    return dict(value)


def _validate_installation_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    _require_exact_fields(snapshot, _SNAPSHOT_FIELDS, label="installation_snapshot")
    transaction_id = str(snapshot.get("transaction_id", ""))
    if not _TRANSACTION_ID_PATTERN.fullmatch(transaction_id):
        raise ValueError("installation_snapshot_transaction_id_invalid")
    for field_name in (
        "install_head_hash",
        "activation_receipt_hash",
        "stage_verification_hash",
        "post_activation_smoke_hash",
        "post_activation_member_comparisons_hash",
        "current_installed_smoke_hash",
        "current_installed_smoke_command_fingerprint",
        "current_installed_smoke_environment_fingerprint",
    ):
        _require_hash(snapshot.get(field_name), label=f"installation_snapshot_{field_name}")
    if snapshot.get("rollback_disposition") != "not_required":
        raise ValueError("installation_snapshot_rollback_disposition_invalid")
    canonical_source = _validate_source_identity(
        snapshot.get("canonical_source_identity"),
        label="canonical_source_identity",
    )
    installed_source = _validate_source_identity(
        snapshot.get("installed_source_identity"),
        label="installed_source_identity",
    )
    if canonical_source != installed_source:
        raise ValueError("installation_snapshot_source_identity_mismatch")
    canonical_runtime = _validate_runtime_fingerprint(
        snapshot.get("canonical_runtime_fingerprint"),
        label="canonical_runtime_fingerprint",
    )
    installed_runtime = _validate_runtime_fingerprint(
        snapshot.get("installed_runtime_fingerprint"),
        label="installed_runtime_fingerprint",
    )
    if canonical_runtime != installed_runtime:
        raise ValueError("installation_snapshot_runtime_fingerprint_mismatch")
    return dict(snapshot)


def validate_installation_verification_receipt(
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply the one exact receipt validator shared by build/write/replay."""

    _require_exact_fields(receipt, _RECEIPT_FIELDS, label="installation_receipt")
    if receipt.get("schema_version") != INSTALL_VERIFICATION_SCHEMA:
        raise ValueError("installation_verification_receipt_schema_mismatch")
    if receipt.get("status") != "current_installed_parity":
        raise ValueError("installation_verification_receipt_status_mismatch")
    _validate_installation_snapshot(
        {key: receipt[key] for key in _SNAPSHOT_FIELDS}
    )
    if not isinstance(receipt.get("claim_boundary"), str) or not str(
        receipt["claim_boundary"]
    ).strip():
        raise ValueError("installation_verification_receipt_claim_boundary_invalid")
    expected_receipt_id = (
        "installation-"
        + canonical_hash(
            {
                key: value
                for key, value in receipt.items()
                if key not in {"receipt_id", "receipt_hash"}
            }
        )[:24].lower()
    )
    if (
        not _RECEIPT_ID_PATTERN.fullmatch(str(receipt.get("receipt_id", "")))
        or receipt.get("receipt_id") != expected_receipt_id
    ):
        raise ValueError("installation_verification_receipt_id_mismatch")
    expected_hash = canonical_hash(
        {key: value for key, value in receipt.items() if key != "receipt_hash"}
    )
    if receipt.get("receipt_hash") != expected_hash:
        raise ValueError("installation_verification_receipt_hash_mismatch")
    return dict(receipt)


def _validate_installation_verification_head(
    head: Mapping[str, Any],
) -> dict[str, Any]:
    _require_exact_fields(head, _HEAD_FIELDS, label="installation_head")
    if head.get("schema_version") != INSTALL_VERIFICATION_HEAD_SCHEMA:
        raise ValueError("installation_verification_head_schema_mismatch")
    if not _RECEIPT_ID_PATTERN.fullmatch(str(head.get("receipt_id", ""))):
        raise ValueError("installation_verification_head_receipt_id_invalid")
    _require_hash(head.get("receipt_hash"), label="installation_head_receipt_hash")
    ref = head.get("receipt_ref")
    if not isinstance(ref, Mapping):
        raise ValueError("installation_verification_receipt_ref_invalid")
    _require_exact_fields(
        ref,
        frozenset({"path_token", "relative_path"}),
        label="installation_receipt_ref",
    )
    relative = str(ref.get("relative_path", "")).replace("\\", "/")
    if (
        ref.get("path_token") != "receipt_root"
        or not re.fullmatch(r"receipts/[a-f0-9]{24}\.json", relative)
    ):
        raise ValueError("installation_verification_receipt_ref_invalid")
    expected_hash = canonical_hash(
        {key: value for key, value in head.items() if key != "head_hash"}
    )
    if head.get("head_hash") != expected_hash:
        raise ValueError("installation_verification_head_hash_mismatch")
    return dict(head)


@dataclass(frozen=True, slots=True)
class VerifiedInstallationContext:
    """Sealed, content-addressed result of one exact currentness replay."""

    schema_version: str
    receipt_root: str
    receipt_id: str
    receipt_hash: str
    head_hash: str
    current_snapshot_hash: str
    current_installed_smoke_hash: str
    current_installed_smoke_command_fingerprint: str
    current_installed_smoke_environment_fingerprint: str
    context_hash: str
    _head_json: str = field(repr=False)
    _receipt_json: str = field(repr=False)
    _snapshot_json: str = field(repr=False)
    _seal: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._seal is not _CONTEXT_SEAL:
            raise TypeError(
                "VerifiedInstallationContext must be loaded from current receipts"
            )

    @property
    def head(self) -> dict[str, Any]:
        return json.loads(self._head_json)

    @property
    def receipt(self) -> dict[str, Any]:
        return json.loads(self._receipt_json)

    @property
    def current_snapshot(self) -> dict[str, Any]:
        return json.loads(self._snapshot_json)

    def identity(self) -> dict[str, Any]:
        """Return the private in-process seal identity, including its local root."""

        return {
            "schema_version": self.schema_version,
            "receipt_root": self.receipt_root,
            "receipt_id": self.receipt_id,
            "receipt_hash": self.receipt_hash,
            "head_hash": self.head_hash,
            "current_snapshot_hash": self.current_snapshot_hash,
            "current_installed_smoke_hash": self.current_installed_smoke_hash,
            "current_installed_smoke_command_fingerprint": (
                self.current_installed_smoke_command_fingerprint
            ),
            "current_installed_smoke_environment_fingerprint": (
                self.current_installed_smoke_environment_fingerprint
            ),
            "context_hash": self.context_hash,
        }

    def portable_identity(self) -> dict[str, Any]:
        """Return a persistence-safe projection without absolute local paths."""

        identity = {
            "schema_version": self.schema_version,
            "receipt_id": self.receipt_id,
            "receipt_hash": self.receipt_hash,
            "head_hash": self.head_hash,
            "current_snapshot_hash": self.current_snapshot_hash,
            "current_installed_smoke_hash": self.current_installed_smoke_hash,
            "current_installed_smoke_command_fingerprint": (
                self.current_installed_smoke_command_fingerprint
            ),
            "current_installed_smoke_environment_fingerprint": (
                self.current_installed_smoke_environment_fingerprint
            ),
        }
        identity["context_binding_hash"] = canonical_hash(identity)
        return identity


def validate_verified_installation_context(
    context: VerifiedInstallationContext,
    *,
    expected_receipt_root: Path | None = None,
) -> VerifiedInstallationContext:
    """Validate a sealed context without replaying its already-bound smoke."""

    if type(context) is not VerifiedInstallationContext:
        raise TypeError("verified_installation_context_type_invalid")
    if context.schema_version != VERIFIED_INSTALLATION_CONTEXT_SCHEMA:
        raise ValueError("verified_installation_context_schema_mismatch")
    if expected_receipt_root is not None and context.receipt_root != str(
        expected_receipt_root.resolve(strict=True)
    ):
        raise ValueError("verified_installation_context_root_mismatch")
    head = _validate_installation_verification_head(context.head)
    receipt = validate_installation_verification_receipt(context.receipt)
    snapshot = _validate_installation_snapshot(context.current_snapshot)
    if any(receipt[key] != snapshot[key] for key in _SNAPSHOT_FIELDS):
        raise ValueError("verified_installation_context_snapshot_mismatch")
    if (
        head["receipt_id"] != context.receipt_id
        or receipt["receipt_id"] != context.receipt_id
        or head["receipt_hash"] != context.receipt_hash
        or receipt["receipt_hash"] != context.receipt_hash
        or head["head_hash"] != context.head_hash
        or canonical_hash(snapshot) != context.current_snapshot_hash
        or snapshot["current_installed_smoke_hash"]
        != context.current_installed_smoke_hash
        or snapshot["current_installed_smoke_command_fingerprint"]
        != context.current_installed_smoke_command_fingerprint
        or snapshot["current_installed_smoke_environment_fingerprint"]
        != context.current_installed_smoke_environment_fingerprint
    ):
        raise ValueError("verified_installation_context_binding_mismatch")
    identity = context.identity()
    expected_context_hash = canonical_hash(
        {key: value for key, value in identity.items() if key != "context_hash"}
    )
    if context.context_hash != expected_context_hash:
        raise ValueError("verified_installation_context_hash_mismatch")
    return context


def current_installation_snapshot(
    canonical_skill_root: Path | None = None, *, codex_home: Path | None = None
) -> dict[str, Any]:
    home = resolve_codex_home_root(codex_home)
    installed = (home / "skills" / "skillguard").resolve(strict=True)
    head = _load_install_head(home)
    transaction_id = str(head.get("transaction_id") or "")
    if not transaction_id:
        raise ValueError("installation_head_has_no_committed_transaction")
    record = _load_transaction(home, transaction_id)
    if record.get("status") != "committed" or record.get("phase") != "committed":
        raise ValueError("installation_transaction_not_committed")
    if record.get("install_head_hash") != head.get("head_hash"):
        raise ValueError("installation_transaction_head_mismatch")
    if not _activation_receipt_current(record):
        raise ValueError("installation_activation_receipt_not_current")
    members = record.get("members", {})
    skill_record = members.get("skillguard") if isinstance(members, Mapping) else None
    if not isinstance(skill_record, Mapping):
        raise ValueError("installation_skillguard_member_missing")
    canonical = (
        canonical_skill_root.resolve(strict=True)
        if canonical_skill_root is not None
        else Path(str(skill_record.get("canonical_root", ""))).resolve(
            strict=True
        )
    )
    if Path(str(skill_record.get("canonical_root", ""))).resolve() != canonical:
        raise ValueError("installation_canonical_root_mismatch")
    canonical_identity = skill_record.get("canonical_identity")
    installed_identity = skill_record.get("installed_identity")
    if not isinstance(canonical_identity, Mapping) or not isinstance(
        installed_identity, Mapping
    ):
        raise ValueError("installation_record_source_identity_missing")
    if canonical_identity != installed_identity:
        raise ValueError("installation_record_source_identity_mismatch")
    canonical_runtime = guard_runtime_fingerprint(canonical)
    installed_runtime = guard_active_installation_runtime_fingerprint(installed)
    if canonical_runtime != installed_runtime:
        raise ValueError("installation_runtime_fingerprint_mismatch")
    recorded_smoke = record.get("post_activation_smoke")
    if not isinstance(recorded_smoke, Mapping):
        raise ValueError("installation_recorded_smoke_missing")
    current_smoke = replay_installed_smoke_currentness(
        installed,
        recorded_smoke=recorded_smoke,
    )
    if current_smoke.get("status") != "passed":
        raise ValueError("installation_current_installed_smoke_failed")
    snapshot = {
        "transaction_id": transaction_id,
        "install_head_hash": str(head.get("head_hash", "")),
        "activation_receipt_hash": str(record.get("activation_receipt_hash", "")),
        "stage_verification_hash": canonical_hash(
            record.get("stage_verification", {})
        ),
        "post_activation_smoke_hash": canonical_hash(
            record.get("post_activation_smoke", {})
        ),
        "post_activation_member_comparisons_hash": canonical_hash(
            record.get("post_activation_member_comparisons", {})
        ),
        "rollback_disposition": str(record.get("rollback_disposition", "")),
        "canonical_source_identity": canonical_identity,
        "installed_source_identity": installed_identity,
        "canonical_runtime_fingerprint": canonical_runtime,
        "installed_runtime_fingerprint": installed_runtime,
        "current_installed_smoke_hash": current_smoke[
            "current_installed_smoke_hash"
        ],
        "current_installed_smoke_command_fingerprint": current_smoke[
            "current_installed_smoke_command_fingerprint"
        ],
        "current_installed_smoke_environment_fingerprint": current_smoke[
            "current_installed_smoke_environment_fingerprint"
        ],
    }
    return _validate_installation_snapshot(snapshot)


def build_installation_verification_receipt(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    validated_snapshot = _validate_installation_snapshot(snapshot)
    receipt: dict[str, Any] = {
        "schema_version": INSTALL_VERIFICATION_SCHEMA,
        "status": "current_installed_parity",
        **validated_snapshot,
        "claim_boundary": (
            "This receipt proves current local canonical-to-active SkillGuard suite parity for "
            "the named committed installation transaction. It does not prove external targets or publication."
        ),
    }
    receipt["receipt_id"] = f"installation-{canonical_hash(receipt)[:24].lower()}"
    receipt["receipt_hash"] = canonical_hash(receipt)
    return validate_installation_verification_receipt(receipt)


def write_installation_verification_receipt(
    receipt_root: Path, receipt: Mapping[str, Any]
) -> dict[str, Any]:
    root = receipt_root.resolve()
    validated_receipt = validate_installation_verification_receipt(receipt)
    expected = str(validated_receipt["receipt_hash"])
    receipt_path = root / "receipts" / f"{expected[:24].lower()}.json"
    if receipt_path.exists():
        if json.loads(receipt_path.read_text(encoding="utf-8")) != validated_receipt:
            raise ValueError("installation_verification_receipt_collision")
    else:
        atomic_write_json(receipt_path, validated_receipt)
    head: dict[str, Any] = {
        "schema_version": INSTALL_VERIFICATION_HEAD_SCHEMA,
        "receipt_id": str(validated_receipt["receipt_id"]),
        "receipt_hash": expected,
        "receipt_ref": {
            "path_token": "receipt_root",
            "relative_path": receipt_path.relative_to(root).as_posix(),
        },
    }
    head["head_hash"] = canonical_hash(head)
    validated_head = _validate_installation_verification_head(head)
    atomic_write_json(root / "HEAD.json", validated_head)
    return {"receipt": validated_receipt, "head": validated_head}


def load_verified_installation_context(
    receipt_root: Path,
    *,
    canonical_skill_root: Path | None = None,
    codex_home: Path | None = None,
) -> VerifiedInstallationContext:
    """Load and replay one receipt into a sealed currentness context."""

    if receipt_root.is_symlink():
        raise ValueError("installation_verification_receipt_root_invalid")
    root = receipt_root.resolve(strict=True)
    head_path = root / "HEAD.json"
    if head_path.is_symlink() or not head_path.is_file():
        raise ValueError("installation_verification_head_path_invalid")
    head = _validate_installation_verification_head(
        json.loads(head_path.read_text(encoding="utf-8"))
    )
    ref = head["receipt_ref"]
    if (root / "receipts").is_symlink():
        raise ValueError("installation_verification_receipt_path_invalid")
    receipt_candidate = root / str(ref["relative_path"])
    if receipt_candidate.is_symlink():
        raise ValueError("installation_verification_receipt_path_invalid")
    receipt_path = receipt_candidate.resolve(strict=True)
    receipt_path.relative_to(root)
    if not receipt_path.is_file():
        raise ValueError("installation_verification_receipt_path_invalid")
    receipt = validate_installation_verification_receipt(
        json.loads(receipt_path.read_text(encoding="utf-8"))
    )
    if (
        head["receipt_id"] != receipt["receipt_id"]
        or head["receipt_hash"] != receipt["receipt_hash"]
        or ref["relative_path"]
        != f"receipts/{str(receipt['receipt_hash'])[:24].lower()}.json"
    ):
        raise ValueError("installation_verification_head_receipt_mismatch")
    current = _validate_installation_snapshot(
        current_installation_snapshot(
            canonical_skill_root,
            codex_home=codex_home,
        )
    )
    for key in _SNAPSHOT_FIELDS:
        if receipt[key] != current[key]:
            raise ValueError(f"installation_verification_current_mismatch:{key}")
    current_snapshot_hash = canonical_hash(current)
    context_base = {
        "schema_version": VERIFIED_INSTALLATION_CONTEXT_SCHEMA,
        "receipt_root": str(root),
        "receipt_id": str(receipt["receipt_id"]),
        "receipt_hash": str(receipt["receipt_hash"]),
        "head_hash": str(head["head_hash"]),
        "current_snapshot_hash": current_snapshot_hash,
        "current_installed_smoke_hash": current["current_installed_smoke_hash"],
        "current_installed_smoke_command_fingerprint": current[
            "current_installed_smoke_command_fingerprint"
        ],
        "current_installed_smoke_environment_fingerprint": current[
            "current_installed_smoke_environment_fingerprint"
        ],
    }
    context = VerifiedInstallationContext(
        **context_base,
        context_hash=canonical_hash(context_base),
        _head_json=json.dumps(head, sort_keys=True, separators=(",", ":")),
        _receipt_json=json.dumps(receipt, sort_keys=True, separators=(",", ":")),
        _snapshot_json=json.dumps(current, sort_keys=True, separators=(",", ":")),
        _seal=_CONTEXT_SEAL,
    )
    return validate_verified_installation_context(
        context,
        expected_receipt_root=root,
    )


def verify_installation_verification_receipt(
    receipt_root: Path,
    *,
    canonical_skill_root: Path | None = None,
    codex_home: Path | None = None,
) -> dict[str, Any]:
    try:
        context = load_verified_installation_context(
            receipt_root,
            canonical_skill_root=canonical_skill_root,
            codex_home=codex_home,
        )
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return {
            "artifact_type": "skillguard_installation_receipt_verification",
            "status": "blocked",
            "blockers": [str(exc)],
        }
    return {
        "artifact_type": "skillguard_installation_receipt_verification",
        "status": "passed",
        "blockers": [],
        "validated_head": context.head,
        "validated_receipt": context.receipt,
        "current_snapshot": context.current_snapshot,
        "verified_context": context.portable_identity(),
    }


def verify_scheduled_production_installation_identity(
    identity: Mapping[str, Any],
    *,
    active_skill_root: Path | None = None,
    verified_context: VerifiedInstallationContext | None = None,
) -> dict[str, Any]:
    """Bind a scheduled identity to one already replayed sealed context.

    Current installation replay is a top-level operation.  Depth, terminal,
    closure, portfolio, and TestMesh consumers must receive the same sealed
    context instead of independently rerunning the installed smoke.
    """

    active = resolve_guard_runtime_root(
        active_skill_root or Path(__file__).resolve().parent
    )
    ref = identity.get("installation_receipt_root_ref")
    if not isinstance(ref, Mapping) or ref.get("path_token") != "active_skill_root":
        raise ValueError("scheduled_installation_receipt_root_ref_invalid")
    relative = str(ref.get("relative_path", "")).replace("\\", "/")
    if (
        not relative
        or relative.startswith("/")
        or any(part in {"", ".", ".."} for part in relative.split("/"))
    ):
        raise ValueError("scheduled_installation_receipt_root_ref_invalid")
    if verified_context is None:
        raise ValueError("verified_installation_context_required")
    context = validate_verified_installation_context(verified_context)
    receipt_root = Path(context.receipt_root).resolve(strict=True)
    if active_skill_root is not None:
        expected_receipt_root = (
            active / Path(*relative.split("/"))
        ).resolve(strict=True)
        expected_receipt_root.relative_to(active)
        if receipt_root != expected_receipt_root:
            raise ValueError("verified_installation_context_root_mismatch")
    elif receipt_root.as_posix().replace("\\", "/").endswith(relative) is False:
        raise ValueError("verified_installation_context_root_mismatch")
    head = context.head
    receipt = context.receipt
    current = context.current_snapshot
    active_runtime = current["installed_runtime_fingerprint"]
    if context.receipt_id != identity.get("installation_receipt_id"):
        raise ValueError("scheduled_installation_receipt_id_mismatch")
    if context.receipt_hash != identity.get("installation_receipt_hash"):
        raise ValueError("scheduled_installation_receipt_hash_mismatch")
    if receipt.get("receipt_hash") != identity.get("installation_receipt_hash"):
        raise ValueError("scheduled_installation_receipt_payload_mismatch")
    if active_runtime.get("source_hash") != identity.get(
        "installed_runtime_fingerprint"
    ):
        raise ValueError("scheduled_installed_runtime_fingerprint_stale")
    return {
        "installation_receipt_root_ref": {
            "path_token": "active_skill_root",
            "relative_path": relative,
        },
        "receipt": receipt,
        "head": head,
        "active_runtime": active_runtime,
        "current_snapshot": current,
        "verified_context": context.portable_identity(),
    }


def load_scheduled_production_installation_context(
    identity: Mapping[str, Any],
    *,
    active_skill_root: Path | None = None,
) -> VerifiedInstallationContext:
    """Load one sealed context from a scheduled identity, then bind it exactly.

    This is the in-process single-replay entry point for supervisors and
    portfolio assemblers.  Passing the returned context to all downstream
    consumers avoids repeated installed-smoke execution without allowing a
    caller-authored mapping to become currentness authority.
    """

    active = resolve_guard_runtime_root(
        active_skill_root or Path(__file__).resolve().parent
    )
    ref = identity.get("installation_receipt_root_ref")
    if not isinstance(ref, Mapping) or ref.get("path_token") != "active_skill_root":
        raise ValueError("scheduled_installation_receipt_root_ref_invalid")
    relative = str(ref.get("relative_path", "")).replace("\\", "/")
    if (
        not relative
        or relative.startswith("/")
        or any(part in {"", ".", ".."} for part in relative.split("/"))
    ):
        raise ValueError("scheduled_installation_receipt_root_ref_invalid")
    receipt_root = (active / Path(*relative.split("/"))).resolve(strict=True)
    receipt_root.relative_to(active)
    context = load_verified_installation_context(
        receipt_root,
        canonical_skill_root=None,
        codex_home=active.parent.parent,
    )
    verify_scheduled_production_installation_identity(
        identity,
        active_skill_root=active,
        verified_context=context,
    )
    return context


def build_scheduled_production_identity(
    *,
    scheduler_or_trigger_id: str,
    scheduled_execution_id: str,
    active_skill_root: Path | None = None,
    installation_receipt_relative_path: str = DEFAULT_INSTALLATION_RECEIPT_RELATIVE_PATH,
    verified_context: VerifiedInstallationContext,
) -> dict[str, Any]:
    """Construct one current scheduled-production identity from the active install.

    Producers use this after installation verification has been captured under
    the active SkillGuard root.  The returned portable reference lets every
    later depth/terminal replay re-check the same receipt against the *current*
    install instead of trusting copied hash-shaped fields.
    """

    if not scheduler_or_trigger_id.strip():
        raise ValueError("scheduled_trigger_id_missing")
    if not scheduled_execution_id.strip():
        raise ValueError("scheduled_execution_id_missing")
    relative = installation_receipt_relative_path.replace("\\", "/")
    if (
        not relative
        or relative.startswith("/")
        or any(part in {"", ".", ".."} for part in relative.split("/"))
    ):
        raise ValueError("scheduled_installation_receipt_root_ref_invalid")
    active = resolve_guard_runtime_root(
        active_skill_root or Path(__file__).resolve().parent
    )
    receipt_root = (active / Path(*relative.split("/"))).resolve(strict=True)
    receipt_root.relative_to(active)
    context = validate_verified_installation_context(
        verified_context,
        expected_receipt_root=receipt_root,
    )
    active_runtime = context.current_snapshot["installed_runtime_fingerprint"]
    return {
        "scheduler_or_trigger_id": scheduler_or_trigger_id.strip(),
        "scheduled_execution_id": scheduled_execution_id.strip(),
        "installation_receipt_id": context.receipt_id,
        "installation_receipt_hash": context.receipt_hash,
        "installation_receipt_root_ref": {
            "path_token": "active_skill_root",
            "relative_path": relative,
        },
        "installed_runtime_fingerprint": str(active_runtime.get("source_hash", "")),
    }


__all__ = [
    "INSTALL_VERIFICATION_HEAD_SCHEMA",
    "INSTALL_VERIFICATION_SCHEMA",
    "DEFAULT_INSTALLATION_RECEIPT_RELATIVE_PATH",
    "VERIFIED_INSTALLATION_CONTEXT_SCHEMA",
    "VerifiedInstallationContext",
    "build_scheduled_production_identity",
    "build_installation_verification_receipt",
    "current_installation_snapshot",
    "load_scheduled_production_installation_context",
    "load_verified_installation_context",
    "resolve_codex_home_root",
    "validate_installation_verification_receipt",
    "validate_verified_installation_context",
    "verify_installation_verification_receipt",
    "verify_scheduled_production_installation_identity",
    "write_installation_verification_receipt",
]
