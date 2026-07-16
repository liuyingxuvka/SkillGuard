"""Read-only resolution for SkillGuard's one current authority path."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


AUTHORITY_CURRENT = "current"
AUTHORITY_BLOCKED = "blocked"

CURRENT_CONTRACT_SOURCE_PATH = ".skillguard/contract-source.json"
CURRENT_COMPILED_CONTRACT_PATH = ".skillguard/compiled-contract.json"
CURRENT_CHECK_MANIFEST_PATH = ".skillguard/check-manifest.json"

FORMER_RUN_RECORD_SCHEMA = "skillguard.run_record.v1"
FORMER_HISTORY_PREFIX = ".skillguard/v1r"
FORMER_EXACT_FILES = {
    ".skillguard/work-contract.json": "former-work-contract",
    ".skillguard/check_manifest.json": "former-check-manifest",
    ".skillguard/skillguard_manifest.json": "former-skill-manifest",
    ".skillguard/skillguard_profile.json": "former-skill-profile",
    ".skillguard/skillguard_skill_contract.json": "former-skill-contract",
    ".skillguard/skillguard_evidence_rules.json": "former-evidence-rules",
    ".skillguard/skillguard_closure_policy.json": "former-closure-policy",
    ".skillguard/skillguard_progress_ledger.jsonl": "former-progress-ledger",
    ".skillguard/checks/check_route.py": "former-checker",
    ".skillguard/checks/check_phase_order.py": "former-checker",
    ".skillguard/checks/check_evidence.py": "former-checker",
    ".skillguard/checks/check_quality_floor.py": "former-checker",
    ".skillguard/checks/check_closure.py": "former-checker",
    ".skillguard/v1-retirement-eligibility-receipt.json": "former-retirement-receipt",
    ".skillguard/v1-retirement-completion-receipt.json": "former-retirement-receipt",
    "scripts/skillguard_v1_retirement.py": "former-conversion-tool",
    "scripts/skillguard_legacy_depth_upgrade.py": "former-conversion-tool",
    "scripts/skillguard_v2/field_lifecycle.py": "former-conversion-tool",
    "assets/schemas/skillguard_work_contract.schema.json": "former-runtime-schema",
    "assets/schemas/skillguard_run_record.schema.json": "former-runtime-schema",
    "assets/schemas/skillguard_check_manifest.schema.json": "former-runtime-schema",
    "assets/schemas/skillguard_skill_contract.schema.json": "former-runtime-schema",
    "assets/schemas/skillguard_v1_retirement_eligibility_receipt_v1.schema.json": "former-retirement-schema",
    "assets/schemas/skillguard_v1_retirement_completion_receipt_v1.schema.json": "former-retirement-schema",
    "references/skillguard-v1-field-lifecycle.md": "former-conversion-guidance",
}


def canonical_json_bytes(payload: object) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def canonical_payload_hash(payload: object) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest().upper()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


@dataclass(frozen=True)
class AuthorityFinding:
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


@dataclass(frozen=True)
class FormerRuntimeArtifact:
    kind: str
    path: str
    sha256: str
    schema_version: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "path": self.path,
            "sha256": self.sha256,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True)
class FormerRuntimeScan:
    artifacts: tuple[FormerRuntimeArtifact, ...]
    findings: tuple[AuthorityFinding, ...]

    @property
    def fingerprint(self) -> str:
        return canonical_payload_hash(
            {
                "artifacts": [row.to_dict() for row in self.artifacts],
                "findings": [row.to_dict() for row in self.findings],
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "skillguard_former_runtime_surface_scan",
            "artifacts": [row.to_dict() for row in self.artifacts],
            "artifact_count": len(self.artifacts),
            "findings": [row.to_dict() for row in self.findings],
            "fingerprint": self.fingerprint,
            "claim_boundary": (
                "The scan recognizes only named former product surfaces and "
                "flat old run records. Current nested run directories and "
                "unrelated stable protocols are preserved."
            ),
        }


@dataclass(frozen=True)
class RuntimeAuthorityDecision:
    ok: bool
    authority: str
    skill_id: str
    skill_root: str
    contract_source_path: str
    compiled_contract_path: str
    check_manifest_path: str
    former_runtime_residuals: tuple[FormerRuntimeArtifact, ...]
    findings: tuple[AuthorityFinding, ...]
    blockers: tuple[str, ...]
    claim_boundary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "skillguard_runtime_authority_decision",
            "ok": self.ok,
            "authority": self.authority,
            "skill_id": self.skill_id,
            "skill_root": self.skill_root,
            "contract_source_path": self.contract_source_path,
            "compiled_contract_path": self.compiled_contract_path,
            "check_manifest_path": self.check_manifest_path,
            "former_runtime_residuals": [
                row.to_dict() for row in self.former_runtime_residuals
            ],
            "findings": [row.to_dict() for row in self.findings],
            "blockers": list(self.blockers),
            "claim_boundary": self.claim_boundary,
        }


def _load_json_object(
    path: Path,
    code: str,
) -> tuple[Mapping[str, Any] | None, list[AuthorityFinding]]:
    findings: list[AuthorityFinding] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        findings.append(
            AuthorityFinding(f"{code}_missing", path.name, "file is missing")
        )
        return None, findings
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        findings.append(
            AuthorityFinding(f"{code}_unreadable", path.name, str(exc))
        )
        return None, findings
    if not isinstance(payload, Mapping):
        findings.append(
            AuthorityFinding(
                f"{code}_invalid",
                path.name,
                "JSON root must be an object",
            )
        )
        return None, findings
    return payload, findings


def _artifact(
    root: Path,
    relative: str,
    kind: str,
) -> FormerRuntimeArtifact | None:
    path = root / relative
    if not path.is_file():
        return None
    schema_version = ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        payload = None
    if isinstance(payload, Mapping):
        schema_version = str(payload.get("schema_version") or "")
    return FormerRuntimeArtifact(
        kind=kind,
        path=relative,
        sha256=file_sha256(path),
        schema_version=schema_version,
    )


def scan_former_runtime_artifacts(skill_root: Path) -> FormerRuntimeScan:
    """Scan named former surfaces without interpreting them as authority."""

    root = skill_root.resolve()
    artifacts: list[FormerRuntimeArtifact] = []
    findings: list[AuthorityFinding] = []
    if not root.is_dir():
        return FormerRuntimeScan((), ())

    for relative, kind in sorted(FORMER_EXACT_FILES.items()):
        row = _artifact(root, relative, kind)
        if row is not None:
            artifacts.append(row)

    history_root = root / FORMER_HISTORY_PREFIX
    if history_root.is_dir():
        for path in sorted(history_root.rglob("*")):
            if path.is_file():
                artifacts.append(
                    FormerRuntimeArtifact(
                        kind="former-retirement-history",
                        path=path.relative_to(root).as_posix(),
                        sha256=file_sha256(path),
                    )
                )

    runs_root = root / ".skillguard" / "runs"
    if runs_root.is_dir():
        for path in sorted(runs_root.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                findings.append(
                    AuthorityFinding(
                        "former_run_record_unreadable",
                        path.relative_to(root).as_posix(),
                        str(exc),
                    )
                )
                continue
            if (
                isinstance(payload, Mapping)
                and payload.get("schema_version") == FORMER_RUN_RECORD_SCHEMA
            ):
                artifacts.append(
                    FormerRuntimeArtifact(
                        kind="former-flat-run-record",
                        path=path.relative_to(root).as_posix(),
                        sha256=file_sha256(path),
                        schema_version=FORMER_RUN_RECORD_SCHEMA,
                    )
                )

    return FormerRuntimeScan(
        artifacts=tuple(sorted(artifacts, key=lambda row: (row.path, row.kind))),
        findings=tuple(findings),
    )


def _validate_current_trio(
    source_path: Path,
    contract_path: Path,
    manifest_path: Path,
) -> tuple[
    Mapping[str, Any] | None,
    Mapping[str, Any] | None,
    Mapping[str, Any] | None,
    list[AuthorityFinding],
]:
    findings: list[AuthorityFinding] = []
    source, rows = _load_json_object(source_path, "current_contract_source")
    findings.extend(rows)
    contract, rows = _load_json_object(contract_path, "current_compiled_contract")
    findings.extend(rows)
    manifest, rows = _load_json_object(manifest_path, "current_check_manifest")
    findings.extend(rows)
    if source is None or contract is None or manifest is None:
        return source, contract, manifest, findings

    skill_ids = (
        source.get("skill_id"),
        contract.get("skill_id"),
        manifest.get("skill_id"),
    )
    if not skill_ids[0] or len(set(skill_ids)) != 1:
        findings.append(
            AuthorityFinding(
                "current_skill_identity_mismatch",
                "$.skill_id",
                "contract source, compiled contract, and manifest must agree",
            )
        )
    model_ids = (
        source.get("model_id"),
        contract.get("model_id"),
        manifest.get("model_id"),
    )
    if not model_ids[0] or len(set(model_ids)) != 1:
        findings.append(
            AuthorityFinding(
                "current_model_identity_mismatch",
                "$.model_id",
                "contract source, compiled contract, and manifest must agree",
            )
        )

    contract_seed = dict(contract)
    contract_seed.pop("contract_hash", None)
    expected_contract_hash = canonical_payload_hash(contract_seed)
    if contract.get("contract_hash") != expected_contract_hash:
        findings.append(
            AuthorityFinding(
                "current_contract_hash_mismatch",
                "$.contract_hash",
                expected_contract_hash,
            )
        )
    manifest_seed = dict(manifest)
    manifest_seed.pop("manifest_hash", None)
    expected_manifest_hash = canonical_payload_hash(manifest_seed)
    if manifest.get("manifest_hash") != expected_manifest_hash:
        findings.append(
            AuthorityFinding(
                "current_manifest_hash_mismatch",
                "$.manifest_hash",
                expected_manifest_hash,
            )
        )
    if manifest.get("contract_hash") != contract.get("contract_hash"):
        findings.append(
            AuthorityFinding(
                "current_manifest_contract_mismatch",
                "$.contract_hash",
                str(contract.get("contract_hash") or ""),
            )
        )

    from .contract_schema import (
        validate_binding_source,
        validate_check_manifest,
        validate_compiled_contract,
    )

    for prefix, schema_findings in (
        ("contract_source", validate_binding_source(source)),
        ("compiled_contract", validate_compiled_contract(contract)),
        ("check_manifest", validate_check_manifest(manifest)),
    ):
        findings.extend(
            AuthorityFinding(
                f"{prefix}_{row.code}",
                row.path,
                row.message,
            )
            for row in schema_findings
        )
    return source, contract, manifest, findings


def _decision(
    *,
    skill_root: Path,
    authority: str,
    skill_id: str,
    scan: FormerRuntimeScan,
    findings: Sequence[AuthorityFinding],
) -> RuntimeAuthorityDecision:
    blockers = tuple(dict.fromkeys(row.code for row in findings))
    ok = not blockers and authority == AUTHORITY_CURRENT
    return RuntimeAuthorityDecision(
        ok=ok,
        authority=AUTHORITY_CURRENT if ok else AUTHORITY_BLOCKED,
        skill_id=skill_id,
        skill_root=skill_root.name,
        contract_source_path=(
            CURRENT_CONTRACT_SOURCE_PATH
            if (skill_root / CURRENT_CONTRACT_SOURCE_PATH).is_file()
            else ""
        ),
        compiled_contract_path=(
            CURRENT_COMPILED_CONTRACT_PATH
            if (skill_root / CURRENT_COMPILED_CONTRACT_PATH).is_file()
            else ""
        ),
        check_manifest_path=(
            CURRENT_CHECK_MANIFEST_PATH
            if (skill_root / CURRENT_CHECK_MANIFEST_PATH).is_file()
            else ""
        ),
        former_runtime_residuals=scan.artifacts,
        findings=tuple(findings),
        blockers=blockers,
        claim_boundary=(
            "This decision proves only current contract authority and exact "
            "former-surface absence. It does not prove target execution depth, "
            "domain correctness, installation parity, release, or future AI behavior."
        ),
    )


def resolve_runtime_authority(
    skill_root: Path,
    *,
    repository_root: Path | None = None,
) -> RuntimeAuthorityDecision:
    """Resolve one exact skill root as current or blocked only."""

    del repository_root
    root = skill_root.resolve()
    scan = scan_former_runtime_artifacts(root)
    if not root.is_dir():
        return _decision(
            skill_root=root,
            authority=AUTHORITY_BLOCKED,
            skill_id=root.name,
            scan=scan,
            findings=(
                AuthorityFinding(
                    "skill_root_missing",
                    ".",
                    "skill root is missing or not a directory",
                ),
            ),
        )

    source_path = root / CURRENT_CONTRACT_SOURCE_PATH
    contract_path = root / CURRENT_COMPILED_CONTRACT_PATH
    manifest_path = root / CURRENT_CHECK_MANIFEST_PATH
    presence = tuple(
        path.is_file() for path in (source_path, contract_path, manifest_path)
    )
    findings: list[AuthorityFinding] = []
    source: Mapping[str, Any] | None = None
    contract: Mapping[str, Any] | None = None
    manifest: Mapping[str, Any] | None = None
    if all(presence):
        source, contract, manifest, findings = _validate_current_trio(
            source_path,
            contract_path,
            manifest_path,
        )
    else:
        findings.append(
            AuthorityFinding(
                "current_authority_incomplete",
                ".skillguard",
                "contract-source.json, compiled-contract.json, and check-manifest.json are all required",
            )
        )
        if any(presence):
            source, contract, manifest, trio_findings = _validate_current_trio(
                source_path,
                contract_path,
                manifest_path,
            )
            findings.extend(trio_findings)

    skill_id = (
        str(source.get("skill_id") or root.name)
        if isinstance(source, Mapping)
        else root.name
    )
    for artifact in scan.artifacts:
        findings.append(
            AuthorityFinding(
                "former_runtime_residual",
                artifact.path,
                artifact.kind,
            )
        )
    findings.extend(scan.findings)

    if source is None or contract is None or manifest is None or findings:
        return _decision(
            skill_root=root,
            authority=AUTHORITY_BLOCKED,
            skill_id=skill_id,
            scan=scan,
            findings=findings,
        )
    return _decision(
        skill_root=root,
        authority=AUTHORITY_CURRENT,
        skill_id=skill_id,
        scan=scan,
        findings=(),
    )
