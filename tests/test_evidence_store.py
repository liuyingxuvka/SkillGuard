from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / ".agents" / "skills" / "skillguard" / "scripts"
SCHEMA_ROOT = ROOT / ".agents" / "skills" / "skillguard" / "assets" / "schemas"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from skillguard_v2 import evidence_store  # noqa: E402
from skillguard_v2.evidence_store import (  # noqa: E402
    EvidenceStoreError,
    apply_evidence_gc_plan,
    audit_evidence_store,
    begin_evidence_writer,
    end_evidence_writer,
    persist_compressed_stream,
    plan_evidence_gc,
    publish_current_aggregation_authority,
    publish_current_head_authority,
    purge_evidence_quarantine,
    verify_compressed_stream,
)

try:
    import jsonschema  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional local test dependency
    jsonschema = None


def _canonical_bytes(payload: object) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _wire_hash(payload: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _content_ref(root: Path, payload: object) -> dict[str, object]:
    body = _canonical_bytes(payload)
    digest = hashlib.sha256(body).hexdigest()
    relative = f"check-executions/blobs/{digest}.json"
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return {
        "path_token": "owner_evidence_root",
        "relative_path": relative,
        "content_hash": f"sha256:{digest}",
        "media_type": "application/json",
        "byte_count": len(body),
    }


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical_bytes(payload))


def _snapshot(root: Path) -> dict[str, tuple[int, str]]:
    return {
        path.relative_to(root).as_posix(): (
            path.stat().st_size,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _current_store(root: Path) -> tuple[dict[str, object], dict[str, object]]:
    current_stream = persist_compressed_stream(
        root, io.BytesIO((b"current-output\n" * 512))
    )
    pinned_stream = persist_compressed_stream(
        root, io.BytesIO((b"release-output\n" * 256))
    )
    receipt_ref = _content_ref(
        root,
        {
            "schema_version": "test.execution_receipt.current",
            "stdout": current_stream,
            "stderr": current_stream,
        },
    )
    _publish_head(root, receipt_ref, execution_owner_id="owner:test:current")
    _write_json(
        root / "lifecycle/pins/release/release.json",
        {
            "schema_version": "test.release_pin.current",
            "references": [pinned_stream],
        },
    )
    return current_stream, pinned_stream


def _publish_head(
    root: Path,
    receipt_ref: dict[str, object],
    *,
    execution_owner_id: str,
) -> dict[str, object]:
    execution_key = "sha256:" + hashlib.sha256(
        execution_owner_id.encode("utf-8")
    ).hexdigest()
    head: dict[str, object] = {
        "schema_version": "skillguard.check_execution_head.current",
        "maintenance_unit_id": "unit:test",
        "member_skill_id": "test-skill",
        "evidence_subject_id": "subject:test",
        "semantic_check_id": "check:test",
        "execution_owner_id": execution_owner_id,
        "execution_key": execution_key,
        "receipt_id": "sha256:" + ("1" * 64),
        "receipt_hash": "sha256:" + ("2" * 64),
        "receipt_ref": receipt_ref,
        "observed_at": "2026-07-22T00:00:00Z",
        "claim_boundary": "Synthetic current head for lifecycle tests.",
    }
    head["head_hash"] = _wire_hash(head)
    head_path = (
        root
        / "check-executions/heads"
        / f"{execution_key.removeprefix('sha256:')}.json"
    )
    _write_json(head_path, head)
    return publish_current_head_authority(root, head_path)


class CompressedStreamTests(unittest.TestCase):
    def test_deterministic_streaming_gzip_deduplicates_and_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = (b"model-report-line\n" * 20000) + bytes(range(256))

            first = persist_compressed_stream(root, io.BytesIO(data))
            second = persist_compressed_stream(root, io.BytesIO(data))

            self.assertEqual(first, second)
            self.assertEqual(1, len(list((root / "check-executions/blobs").glob("*.gz"))))
            self.assertLess(first["storage_byte_count"], first["logical_byte_count"])
            stored = root / str(first["relative_path"])
            self.assertEqual(b"\x00\x00\x00\x00", stored.read_bytes()[4:8])

            output = io.BytesIO()
            verified = verify_compressed_stream(
                root,
                first,
                max_logical_bytes=len(data),
                output=output,
            )
            self.assertEqual(data, output.getvalue())
            self.assertEqual(first["logical_content_hash"], verified.logical_content_hash)
            self.assertEqual(stored, verified.object_path)

    @unittest.skipUnless(os.name == "nt", "Windows extended-path regression")
    def test_windows_long_path_publish_and_verify(self) -> None:
        temporary = tempfile.mkdtemp()
        try:
            root = Path(temporary)
            while len(str(root)) < 210:
                root /= "bounded-evidence-segment"
            root.mkdir(parents=True)

            data = b"long-path-evidence\n" * 1024
            reference = persist_compressed_stream(root, io.BytesIO(data))
            stored = root / str(reference["relative_path"])

            self.assertGreater(len(str(stored)), 260)
            self.assertTrue(
                evidence_store._windows_extended_path(stored).startswith("\\\\?\\")
            )
            output = io.BytesIO()
            verify_compressed_stream(
                root,
                reference,
                max_logical_bytes=len(data),
                output=output,
            )
            self.assertEqual(data, output.getvalue())
            audit = audit_evidence_store(root)
            self.assertEqual("passed", audit["status"])
            self.assertEqual(
                [reference["relative_path"]],
                [row["relative_path"] for row in audit["inventory"]],
            )
        finally:
            shutil.rmtree(
                evidence_store._windows_extended_path(Path(temporary))
            )

    def test_stream_verification_rejects_storage_logical_path_and_budget_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = b"bounded" * 4096
            reference = persist_compressed_stream(root, io.BytesIO(data))

            with self.assertRaisesRegex(EvidenceStoreError, "logical_byte_limit_exceeded"):
                verify_compressed_stream(
                    root, reference, max_logical_bytes=len(data) - 1
                )

            logical_tamper = dict(reference)
            logical_tamper["logical_content_hash"] = "sha256:" + ("0" * 64)
            with self.assertRaisesRegex(EvidenceStoreError, "logical_hash_mismatch"):
                verify_compressed_stream(
                    root, logical_tamper, max_logical_bytes=len(data)
                )

            path_tamper = dict(reference)
            path_tamper["relative_path"] = "../outside.gz"
            with self.assertRaisesRegex(EvidenceStoreError, "relative_path_invalid"):
                verify_compressed_stream(
                    root, path_tamper, max_logical_bytes=len(data)
                )

            stored = root / str(reference["relative_path"])
            body = bytearray(stored.read_bytes())
            body[-1] ^= 1
            stored.write_bytes(body)
            with self.assertRaisesRegex(EvidenceStoreError, "storage_hash_mismatch"):
                verify_compressed_stream(
                    root, reference, max_logical_bytes=len(data)
                )


class EvidenceLifecycleTests(unittest.TestCase):
    def test_audit_and_plan_are_read_only_and_preserve_shared_and_pinned_objects(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            current, pinned = _current_store(root)
            orphan = root / "check-executions/blobs/orphan.json"
            _write_json(orphan, {"unused": True})
            before = _snapshot(root)

            audit = audit_evidence_store(root)
            plan = plan_evidence_gc(root)

            self.assertEqual(before, _snapshot(root))
            self.assertEqual("passed", audit["status"])
            by_path = {row["relative_path"]: row for row in audit["inventory"]}
            self.assertEqual("current", by_path[current["relative_path"]]["classification"])
            self.assertEqual(
                "release_pinned", by_path[pinned["relative_path"]]["classification"]
            )
            self.assertEqual("ready", plan["status"])
            self.assertEqual(
                [orphan.relative_to(root).as_posix()],
                [row["relative_path"] for row in plan["candidates"]],
            )

    def test_missing_reference_cycle_and_active_writer_block_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_json(
                root / "lifecycle/pins/release/missing.json",
                {
                    "missing": {
                        "path_token": "owner_evidence_root",
                        "relative_path": "check-executions/blobs/missing.json",
                        "content_hash": "sha256:" + ("a" * 64),
                        "media_type": "application/json",
                        "byte_count": 2,
                    }
                },
            )
            marker = begin_evidence_writer(
                root,
                maintenance_unit_id="unit:test",
                member_skill_id="test-skill",
                execution_owner_id="owner:test",
                attempt_id="attempt:test",
            )

            audit = audit_evidence_store(root)
            codes = {row["code"] for row in audit["findings"]}
            self.assertEqual("blocked", audit["status"])
            self.assertIn("referenced_object_missing", codes)
            self.assertIn("active_writer_present", codes)
            self.assertEqual("blocked", plan_evidence_gc(root)["status"])
            end_evidence_writer(root, marker)

    def test_historical_heads_are_not_roots_after_current_authority_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _current_store(root)
            legacy_stream = root / "check-executions/blobs/legacy.bin"
            legacy_stream.parent.mkdir(parents=True, exist_ok=True)
            legacy_stream.write_bytes(b"legacy raw evidence")
            legacy_ref = {
                "path_token": "owner_evidence_root",
                "relative_path": legacy_stream.relative_to(root).as_posix(),
                "content_hash": "sha256:" + hashlib.sha256(
                    legacy_stream.read_bytes()
                ).hexdigest(),
                "media_type": "application/octet-stream",
                "byte_count": legacy_stream.stat().st_size,
            }
            old_receipt_ref = _content_ref(
                root,
                {
                    "schema_version": "test.old_receipt",
                    "stdout": legacy_ref,
                },
            )
            old_owner = "owner:test:retired"
            old_execution_key = "sha256:" + hashlib.sha256(
                old_owner.encode("utf-8")
            ).hexdigest()
            _write_json(
                root
                / "check-executions/heads"
                / f"{old_execution_key.removeprefix('sha256:')}.json",
                {"schema_version": "historical.head", "receipt_ref": old_receipt_ref},
            )

            audit = audit_evidence_store(root)
            plan = plan_evidence_gc(root)
            by_path = {row["relative_path"]: row for row in audit["inventory"]}

            self.assertEqual("passed", audit["status"])
            self.assertNotIn(
                "legacy_uncompressed_stream_reference_non_current",
                {row["code"] for row in audit["findings"]},
            )
            self.assertEqual(
                "orphan", by_path[legacy_stream.relative_to(root).as_posix()]["classification"]
            )
            candidate_paths = {row["relative_path"] for row in plan["candidates"]}
            self.assertIn(legacy_stream.relative_to(root).as_posix(), candidate_paths)
            self.assertIn(old_receipt_ref["relative_path"], candidate_paths)

    def test_current_aggregation_authority_retires_old_aggregation_and_ignores_typed_external_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            def write_aggregation(aggregation_id: str) -> Path:
                payload = {
                    "schema_version": "skillguard.test_mesh_aggregation.current",
                    "maintenance_unit_id": "unit:test",
                    "member_skill_id": "test-skill",
                    "profile_id": "full",
                    "aggregation_id": aggregation_id,
                    "installation_verification_identity": {
                        "installation_receipt_root_ref": {
                            "path_token": "codex_home",
                            "relative_path": "skills/skillguard/.sg-runtime/installation",
                        }
                    },
                    "typed_domain_bindings": [
                        {
                            "registry_ref": {
                                "path_token": "codex_home",
                                "relative_path": ".skillguard/global-router/global_registry.json",
                            },
                            "projection_ref": {
                                "path_token": "codex_home",
                                "relative_path": ".skillguard/global-router/global_prompt_projection.json",
                            },
                            "prompt_ref": {
                                "path_token": "codex_home",
                                "relative_path": "AGENTS.md",
                            },
                        }
                    ],
                }
                digest = hashlib.sha256(_canonical_bytes(payload)).hexdigest()
                path = root / f"test-mesh/aggregations/{digest[:2]}/{digest}.json"
                _write_json(path, payload)
                return path

            first = write_aggregation("sha256:" + ("1" * 64))
            publish_current_aggregation_authority(root, first)
            second = write_aggregation("sha256:" + ("2" * 64))
            publish_current_aggregation_authority(root, second)

            audit = audit_evidence_store(root)
            plan = plan_evidence_gc(root)
            by_path = {row["relative_path"]: row for row in audit["inventory"]}
            codes = {row["code"] for row in audit["findings"]}

            self.assertEqual("passed", audit["status"], audit)
            self.assertNotIn("multiple_or_foreign_evidence_authority", codes)
            self.assertEqual(
                "orphan", by_path[first.relative_to(root).as_posix()]["classification"]
            )
            self.assertEqual(
                "current", by_path[second.relative_to(root).as_posix()]["classification"]
            )
            self.assertIn(
                first.relative_to(root).as_posix(),
                {row["relative_path"] for row in plan["candidates"]},
            )

    def test_foreign_reference_outside_typed_aggregation_binding_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_json(
                root / "lifecycle/pins/release/foreign.json",
                {
                    "reference": {
                        "path_token": "codex_home",
                        "relative_path": "AGENTS.md",
                    }
                },
            )
            audit = audit_evidence_store(root)
            self.assertEqual("blocked", audit["status"])
            self.assertIn(
                "multiple_or_foreign_evidence_authority",
                {row["code"] for row in audit["findings"]},
            )

    def test_heads_without_direct_current_authority_block_planning(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_json(
                root / "check-executions/heads/old.json",
                {"schema_version": "historical.head"},
            )
            audit = audit_evidence_store(root)
            self.assertEqual("blocked", audit["status"])
            self.assertIn(
                "current_head_authority_missing",
                {row["code"] for row in audit["findings"]},
            )
            self.assertEqual("blocked", plan_evidence_gc(root)["status"])

    def test_active_writer_marker_blocks_apply_until_runner_finishes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            orphan = root / "orphan.bin"
            orphan.write_bytes(b"orphan")
            plan = plan_evidence_gc(root)
            marker = begin_evidence_writer(
                root,
                maintenance_unit_id="unit:test",
                member_skill_id="test-skill",
                execution_owner_id="owner:test",
                attempt_id="attempt:test",
            )
            quarantine = root / "lifecycle/quarantine"
            with self.assertRaisesRegex(
                EvidenceStoreError, "gc_apply_current_audit_blocked"
            ):
                apply_evidence_gc_plan(root, plan, quarantine_root=quarantine)
            self.assertTrue(orphan.is_file())

            end_evidence_writer(root, marker)
            receipt = apply_evidence_gc_plan(
                root, plan, quarantine_root=quarantine
            )
            self.assertEqual("applied", receipt["status"])

    def test_stale_plan_makes_zero_additional_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "orphan.bin").write_bytes(b"orphan")
            plan = plan_evidence_gc(root)
            (root / "late.bin").write_bytes(b"late")
            before_apply = _snapshot(root)

            with self.assertRaisesRegex(EvidenceStoreError, "gc_plan_stale"):
                apply_evidence_gc_plan(
                    root,
                    plan,
                    quarantine_root=root / "lifecycle/quarantine",
                )

            self.assertEqual(before_apply, _snapshot(root))
            self.assertFalse((root / "lifecycle/quarantine").exists())

    def test_apply_quarantines_exact_candidates_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _current_store(root)
            orphan = root / "unused.bin"
            orphan.write_bytes(b"unused")
            plan = plan_evidence_gc(root)
            quarantine = root / "lifecycle/quarantine"

            first = apply_evidence_gc_plan(root, plan, quarantine_root=quarantine)
            second = apply_evidence_gc_plan(root, plan, quarantine_root=quarantine)

            self.assertEqual(first, second)
            self.assertFalse(orphan.exists())
            self.assertEqual(1, len(first["items"]))
            quarantined = root / first["items"][0]["quarantine_relative_path"]
            self.assertEqual(b"unused", quarantined.read_bytes())
            self.assertEqual("passed", audit_evidence_store(root)["status"])

    def test_partial_apply_journal_recovers_without_duplicate_move(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "first.bin").write_bytes(b"first")
            (root / "second.bin").write_bytes(b"second")
            plan = plan_evidence_gc(root)
            quarantine = root / "lifecycle/quarantine"
            original_move = evidence_store._atomic_move_no_replace
            call_count = 0

            def fail_second(source: Path, destination: Path) -> None:
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    raise EvidenceStoreError("injected_partial_apply")
                original_move(source, destination)

            with patch.object(
                evidence_store, "_atomic_move_no_replace", side_effect=fail_second
            ):
                with self.assertRaisesRegex(EvidenceStoreError, "injected_partial_apply"):
                    apply_evidence_gc_plan(root, plan, quarantine_root=quarantine)

            receipt = apply_evidence_gc_plan(
                root, plan, quarantine_root=quarantine
            )
            self.assertEqual(2, len(receipt["items"]))
            self.assertEqual(
                {"quarantined", "recovered"},
                {row["disposition"] for row in receipt["items"]},
            )

    def test_mutable_atomic_write_retries_transient_permission_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "lifecycle/journals/current.json"
            evidence_store._write_json_atomic(
                path, {"revision": 1}, root=root, immutable=False
            )
            real_replace = os.replace
            attempts = 0

            def transient_replace(source: object, destination: object) -> None:
                nonlocal attempts
                attempts += 1
                if attempts < 3:
                    raise PermissionError("injected transient journal lock")
                real_replace(source, destination)

            with patch.object(
                evidence_store.os, "replace", side_effect=transient_replace
            ), patch.object(evidence_store.time, "sleep"):
                evidence_store._write_json_atomic(
                    path, {"revision": 2}, root=root, immutable=False
                )

            self.assertEqual(3, attempts)
            self.assertEqual({"revision": 2}, json.loads(path.read_text("utf-8")))
            self.assertEqual([], list(path.parent.glob(".sg-*.tmp")))

    def test_partial_purge_journal_resumes_same_operation_after_replace_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            orphan = root / "unused.bin"
            orphan.write_bytes(b"unused")
            plan = plan_evidence_gc(root)
            quarantine = root / "lifecycle/quarantine"
            applied = apply_evidence_gc_plan(
                root, plan, quarantine_root=quarantine
            )
            real_replace = os.replace

            def deny_deleted_journal(source: object, destination: object) -> None:
                source_path = Path(source)
                destination_path = Path(destination)
                if destination_path.parent.name == "journals":
                    payload = json.loads(source_path.read_text("utf-8"))
                    if any(
                        item.get("status") == "deleted"
                        for item in payload.get("items", [])
                    ):
                        raise PermissionError("injected persistent journal lock")
                real_replace(source, destination)

            with patch.object(
                evidence_store.os, "replace", side_effect=deny_deleted_journal
            ), patch.object(evidence_store.time, "sleep"):
                with self.assertRaisesRegex(
                    EvidenceStoreError, "mutable_record_replace_failed"
                ):
                    purge_evidence_quarantine(
                        root,
                        applied,
                        quarantine_root=quarantine,
                        confirm_plan_hash=plan["plan_hash"],
                        grace_seconds=0,
                    )

            journal_paths = list((root / "lifecycle/journals").glob("evidence-purge-*.json"))
            self.assertEqual(1, len(journal_paths))
            journal = json.loads(journal_paths[0].read_text("utf-8"))
            self.assertEqual("prepared", journal["items"][0]["status"])
            quarantined = root / applied["items"][0]["quarantine_relative_path"]
            self.assertFalse(quarantined.exists())

            purged = purge_evidence_quarantine(
                root,
                applied,
                quarantine_root=quarantine,
                confirm_plan_hash=plan["plan_hash"],
                grace_seconds=0,
            )
            self.assertEqual(journal["operation_id"], purged["purge_id"])
            self.assertEqual("purged", purged["status"])

    def test_purge_is_quarantine_only_and_fresh_audit_gated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            orphan = root / "unused.json"
            _write_json(orphan, {"unused": True})
            plan = plan_evidence_gc(root)
            quarantine = root / "lifecycle/quarantine"
            applied = apply_evidence_gc_plan(
                root, plan, quarantine_root=quarantine
            )

            purged = purge_evidence_quarantine(
                root,
                applied,
                quarantine_root=quarantine,
                confirm_plan_hash=plan["plan_hash"],
                grace_seconds=0,
            )
            replay = purge_evidence_quarantine(
                root,
                applied,
                quarantine_root=quarantine,
                confirm_plan_hash=plan["plan_hash"],
                grace_seconds=0,
            )

            self.assertEqual(purged, replay)
            self.assertEqual("purged", purged["status"])
            self.assertFalse(
                (root / applied["items"][0]["quarantine_relative_path"]).exists()
            )
            with self.assertRaisesRegex(
                EvidenceStoreError, "quarantine_root_not_lifecycle_quarantine"
            ):
                purge_evidence_quarantine(
                    root,
                    applied,
                    quarantine_root=root,
                    confirm_plan_hash=plan["plan_hash"],
                    grace_seconds=0,
                )

    def test_new_reference_after_apply_blocks_purge_and_retains_quarantine(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            orphan = root / "check-executions/blobs/orphan.json"
            _write_json(orphan, {"unused": True})
            plan = plan_evidence_gc(root)
            quarantine = root / "lifecycle/quarantine"
            applied = apply_evidence_gc_plan(
                root, plan, quarantine_root=quarantine
            )
            source_row = plan["candidates"][0]
            _publish_head(
                root,
                {
                    "path_token": "owner_evidence_root",
                    "relative_path": source_row["relative_path"],
                    "content_hash": source_row["content_hash"],
                    "media_type": "application/json",
                    "byte_count": source_row["byte_count"],
                },
                execution_owner_id="owner:test:new",
            )
            quarantined = root / applied["items"][0]["quarantine_relative_path"]

            with self.assertRaisesRegex(
                EvidenceStoreError, "gc_purge_fresh_audit_blocked"
            ):
                purge_evidence_quarantine(
                    root,
                    applied,
                    quarantine_root=quarantine,
                    confirm_plan_hash=plan["plan_hash"],
                    grace_seconds=0,
                )
            self.assertTrue(quarantined.is_file())


@unittest.skipIf(jsonschema is None, "jsonschema is not installed")
class EvidenceLifecycleSchemaTests(unittest.TestCase):
    def test_current_outputs_validate_against_lifecycle_schemas(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "orphan.bin").write_bytes(b"orphan")
            audit = audit_evidence_store(root)
            plan = plan_evidence_gc(root)
            quarantine = root / "lifecycle/quarantine"
            applied = apply_evidence_gc_plan(
                root, plan, quarantine_root=quarantine
            )
            purged = purge_evidence_quarantine(
                root,
                applied,
                quarantine_root=quarantine,
                confirm_plan_hash=plan["plan_hash"],
                grace_seconds=0,
            )
            cases = (
                ("skillguard_evidence_audit_current.schema.json", audit),
                ("skillguard_evidence_gc_plan_current.schema.json", plan),
                (
                    "skillguard_evidence_gc_apply_receipt_current.schema.json",
                    applied,
                ),
                (
                    "skillguard_evidence_gc_purge_receipt_current.schema.json",
                    purged,
                ),
            )
            for schema_name, payload in cases:
                with self.subTest(schema=schema_name):
                    schema = json.loads(
                        (SCHEMA_ROOT / schema_name).read_text(encoding="utf-8")
                    )
                    jsonschema.Draft202012Validator(schema).validate(payload)


if __name__ == "__main__":
    unittest.main()
