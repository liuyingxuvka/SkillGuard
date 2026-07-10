"""Fail-closed validators for declared target artifacts and action witnesses."""

from __future__ import annotations

import hashlib
import json
import os
import struct
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .contract_compiler import canonical_hash, canonical_json_bytes, file_hash
from .contract_schema import ARTIFACT_SCHEMA, validate_runtime_payload
from .run_store import load_run, utc_now


FILE_KINDS = frozenset({"file", "json", "image", "screenshot", "document", "directory"})
WITNESS_KINDS = frozenset({"ui_launch", "ui_interaction", "tool_action", "api_action", "native_output"})


@dataclass(frozen=True)
class ArtifactValidationError(ValueError):
    code: str
    message: str
    artifact_id: str = ""

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def _safe_target_path(target_root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute():
        raise ArtifactValidationError("artifact_path_absolute", relative)
    root = target_root.resolve()
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ArtifactValidationError("artifact_path_outside_target", relative) from exc
    return resolved


def _directory_fingerprint(path: Path) -> str:
    rows: list[dict[str, object]] = []
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        rows.append(
            {
                "path": child.relative_to(path).as_posix(),
                "size": child.stat().st_size,
                "sha256": file_hash(child),
            }
        )
    return canonical_hash(rows)


def _image_dimensions(path: Path) -> tuple[int, int, str]:
    data = path.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return width, height, "png"
    if data.startswith((b"GIF87a", b"GIF89a")) and len(data) >= 10:
        width, height = struct.unpack("<HH", data[6:10])
        return width, height, "gif"
    if data.startswith(b"\xff\xd8"):
        index = 2
        while index + 9 < len(data):
            if data[index] != 0xFF:
                index += 1
                continue
            marker = data[index + 1]
            if marker in range(0xC0, 0xC4):
                height, width = struct.unpack(">HH", data[index + 5 : index + 9])
                return width, height, "jpeg"
            if index + 4 > len(data):
                break
            segment_length = struct.unpack(">H", data[index + 2 : index + 4])[0]
            index += 2 + segment_length
    raise ArtifactValidationError("image_format_unsupported", path.name)


def _validate_document(path: Path) -> tuple[bool, str]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return path.read_bytes().startswith(b"%PDF-"), "pdf_signature"
    if suffix == ".docx":
        try:
            with zipfile.ZipFile(path) as archive:
                return "word/document.xml" in archive.namelist(), "docx_package"
        except zipfile.BadZipFile:
            return False, "docx_package"
    if suffix in {".md", ".txt", ".html"}:
        return bool(path.read_text(encoding="utf-8").strip()), "text_nonempty"
    return False, "document_type_unsupported"


def _store_artifact_record(run_root: Path, record: Mapping[str, Any]) -> None:
    root = run_root / "artifacts"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{record['artifact_record_id']}.json"
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError as exc:
        raise ArtifactValidationError("artifact_record_collision", path.name, str(record["artifact_id"])) from exc
    try:
        os.write(descriptor, canonical_json_bytes(record))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def load_artifact_records(run_root: Path) -> tuple[Mapping[str, Any], ...]:
    root = run_root / "artifacts"
    if not root.is_dir():
        return ()
    records: list[Mapping[str, Any]] = []
    for path in sorted(root.glob("artifact-record-*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ArtifactValidationError("artifact_record_unreadable", type(exc).__name__, path.name) from exc
        if not isinstance(record, Mapping):
            raise ArtifactValidationError("artifact_record_not_object", path.name, path.name)
        findings = validate_runtime_payload(record, ARTIFACT_SCHEMA)
        if findings:
            raise ArtifactValidationError(findings[0].code, findings[0].message, path.name)
        unsigned = dict(record)
        stored_hash = str(unsigned.pop("record_hash", ""))
        if not stored_hash or stored_hash != canonical_hash(unsigned):
            raise ArtifactValidationError("artifact_record_hash_mismatch", path.name, path.name)
        records.append(record)
    return tuple(records)


def load_artifact_record(run_root: Path, artifact_record_id: str) -> Mapping[str, Any]:
    matches = [
        record
        for record in load_artifact_records(run_root)
        if record.get("artifact_record_id") == artifact_record_id
    ]
    if len(matches) != 1:
        raise ArtifactValidationError("artifact_record_not_found", artifact_record_id, artifact_record_id)
    return matches[0]


def hard_evidence_from_artifact(record: Mapping[str, Any]) -> Mapping[str, Any]:
    if record.get("status") != "passed" or not str(record.get("fingerprint", "")):
        raise ArtifactValidationError(
            "artifact_cannot_be_hard_evidence",
            str(record.get("status", "missing")),
            str(record.get("artifact_id", "")),
        )
    return {
        "proof_kind": "artifact_validation",
        "proof_fingerprint": str(record["record_hash"]),
        "artifact_record_id": str(record["artifact_record_id"]),
        "artifact_id": str(record["artifact_id"]),
        "artifact_fingerprint": str(record["fingerprint"]),
        "claim_boundary": "This proves only the declared artifact validators recorded by this artifact record.",
    }


def artifact_record_is_current(record: Mapping[str, Any], target_root: Path) -> tuple[bool, str]:
    if record.get("status") != "passed":
        return False, "artifact_record_not_passed"
    kind = str(record.get("kind", ""))
    if kind in FILE_KINDS:
        relative_path = str(record.get("relative_path", ""))
        try:
            path = _safe_target_path(target_root, relative_path)
        except ArtifactValidationError as exc:
            return False, exc.code
        if not path.exists():
            return False, "artifact_missing"
        if kind == "directory":
            current = _directory_fingerprint(path)
        elif path.is_file():
            current = file_hash(path)
        else:
            return False, "artifact_type_changed"
        if current != record.get("fingerprint"):
            return False, "artifact_fingerprint_changed"
    elif kind in WITNESS_KINDS:
        if not str(record.get("witness_fingerprint", "")):
            return False, "artifact_witness_missing"
    else:
        return False, "artifact_kind_unsupported"
    return True, "current"


def validate_artifact(
    run_root: Path,
    target_root: Path,
    declaration: Mapping[str, Any],
    *,
    producer_step_id: str,
    witness: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    run = load_run(run_root)
    artifact_id = str(declaration.get("artifact_id", ""))
    kind = str(declaration.get("kind", ""))
    expected_producer = str(declaration.get("producer_step_id", ""))
    if not artifact_id or not kind or not expected_producer:
        raise ArtifactValidationError("artifact_declaration_incomplete", artifact_id or kind)
    checks: list[dict[str, Any]] = []

    def check(check_id: str, passed: bool, detail: str) -> None:
        checks.append({"check_id": check_id, "status": "passed" if passed else "failed", "detail": detail})

    check("producer_step", producer_step_id == expected_producer, f"expected={expected_producer}; actual={producer_step_id}")
    fingerprint = ""
    relative_path = str(declaration.get("path_template", ""))
    metadata: dict[str, Any] = {}
    if kind in FILE_KINDS:
        if not relative_path:
            raise ArtifactValidationError("artifact_path_missing", artifact_id, artifact_id)
        path = _safe_target_path(target_root, relative_path)
        exists = path.exists()
        check("exists", exists, relative_path)
        if exists:
            is_expected_type = path.is_dir() if kind == "directory" else path.is_file()
            check("type", is_expected_type, kind)
            if is_expected_type and kind == "directory":
                fingerprint = _directory_fingerprint(path)
                minimum_files = int(declaration.get("minimum_files", 1))
                file_count = sum(1 for item in path.rglob("*") if item.is_file())
                metadata["file_count"] = file_count
                check("directory_minimum_files", file_count >= minimum_files, str(file_count))
            elif is_expected_type:
                fingerprint = file_hash(path)
                size = path.stat().st_size
                metadata["size_bytes"] = size
                check("nonempty", size > 0 or not bool(declaration.get("nonempty", True)), str(size))
                if kind == "json":
                    try:
                        payload = json.loads(path.read_text(encoding="utf-8"))
                        check("json_parse", True, "valid JSON")
                        required_keys = set(str(item) for item in declaration.get("required_keys", []))
                        actual_keys = set(payload) if isinstance(payload, Mapping) else set()
                        check("json_required_keys", required_keys.issubset(actual_keys), ",".join(sorted(required_keys - actual_keys)))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        check("json_parse", False, "invalid JSON")
                elif kind in {"image", "screenshot"}:
                    try:
                        width, height, image_format = _image_dimensions(path)
                        metadata.update({"width": width, "height": height, "format": image_format})
                        check("image_parse", True, f"{width}x{height} {image_format}")
                        check("minimum_width", width >= int(declaration.get("minimum_width", 1)), str(width))
                        check("minimum_height", height >= int(declaration.get("minimum_height", 1)), str(height))
                    except ArtifactValidationError as exc:
                        check("image_parse", False, exc.code)
                elif kind == "document":
                    valid, validator = _validate_document(path)
                    check("document_structure", valid, validator)
    elif kind in WITNESS_KINDS:
        witness = witness or {}
        required_witness = ("witness_id", "target_id", "input_fingerprint", "output_fingerprint")
        for key in required_witness:
            check(f"witness_{key}", bool(str(witness.get(key, ""))), str(witness.get(key, "")))
        fingerprint = canonical_hash(witness)
        metadata["witness_id"] = str(witness.get("witness_id", ""))
    else:
        raise ArtifactValidationError("artifact_kind_unsupported", kind, artifact_id)

    if kind == "screenshot":
        witness = witness or {}
        expected_surface = str(declaration.get("surface_id", ""))
        expected_state = str(declaration.get("state_id", ""))
        check(
            "screenshot_surface",
            bool(expected_surface) and witness.get("surface_id") == expected_surface,
            f"expected={expected_surface}; actual={witness.get('surface_id', '')}",
        )
        if expected_state:
            check(
                "screenshot_state",
                witness.get("state_id") == expected_state,
                f"expected={expected_state}; actual={witness.get('state_id', '')}",
            )
        check("screenshot_witness", bool(str(witness.get("interaction_receipt_id", ""))), "interaction receipt")

    expected_fingerprint = str(declaration.get("expected_fingerprint", ""))
    if expected_fingerprint:
        check("expected_fingerprint", fingerprint == expected_fingerprint, fingerprint)
    status = "passed" if checks and all(row["status"] == "passed" for row in checks) else "failed"
    record: dict[str, Any] = {
        "schema_version": ARTIFACT_SCHEMA,
        "artifact_id": artifact_id,
        "run_id": str(run["run_id"]),
        "kind": kind,
        "producer_step_id": producer_step_id,
        "relative_path": relative_path,
        "fingerprint": fingerprint,
        "status": status,
        "checks": checks,
        "metadata": metadata,
        "witness_fingerprint": canonical_hash(witness) if witness else "",
        "created_at": utc_now(),
    }
    record["artifact_record_id"] = f"artifact-record-{canonical_hash(record)[:24].lower()}"
    record["record_hash"] = canonical_hash(record)
    findings = validate_runtime_payload(record, ARTIFACT_SCHEMA)
    if findings:
        raise ArtifactValidationError(findings[0].code, findings[0].message, artifact_id)
    _store_artifact_record(run_root, record)
    return record
