from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

from _skillguard_v2_runtime_fixture import ROOT, SCRIPT_ROOT  # noqa: F401
from skillguard_v2.contract_compiler import canonical_hash
from skillguard_v2.installation import activate_stage, prepare_stage
from skillguard_v2.installation import replay_installed_smoke_currentness
from skillguard_v2.installation_receipt import (
    build_scheduled_production_identity,
    build_installation_verification_receipt,
    current_installation_snapshot,
    load_verified_installation_context,
    validate_installation_verification_receipt,
    verify_scheduled_production_installation_identity,
    verify_installation_verification_receipt,
    write_installation_verification_receipt,
)
from skillguard_v2.portfolio_cli import verify_installation_receipt_command


class InstallationVerificationReceiptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.canonical = self.root / "canonical"
        self.canonical.mkdir()
        identity = {"exists": True, "kind": "directory", "manifest_hash": "A" * 64, "file_count": 10}
        runtime = {
            "runtime_id": "skillguard-v2",
            "provider_id": "skillguard-local-provider",
            "runtime_contract_id": "skillguard-declared-check-supervision-current",
            "capability_ids": ["target-native-depth-identity.v1"],
            "enrollment_status": "enrolled",
            "file_count": 10,
            "source_hash": "B" * 64,
        }
        self.snapshot = {
            "transaction_id": "install-" + "a" * 32,
            "install_head_hash": "C" * 64,
            "activation_receipt_hash": "D" * 64,
            "stage_verification_hash": "E" * 64,
            "post_activation_smoke_hash": "F" * 64,
            "post_activation_member_comparisons_hash": "1" * 64,
            "rollback_disposition": "not_required",
            "canonical_source_identity": identity,
            "installed_source_identity": identity,
            "canonical_runtime_fingerprint": runtime,
            "installed_runtime_fingerprint": runtime,
            "current_installed_smoke_hash": "2" * 64,
            "current_installed_smoke_command_fingerprint": "3" * 64,
            "current_installed_smoke_environment_fingerprint": "4" * 64,
        }
        self.receipt_root = self.root / "receipt"
        receipt = build_installation_verification_receipt(self.snapshot)
        write_installation_verification_receipt(self.receipt_root, receipt)
        self.active_skill_root = self.root / "skills" / "skillguard"
        self.active_skill_root.mkdir(parents=True)
        self.active_receipt_root = (
            self.active_skill_root / ".sg-runtime" / "installation"
        )
        write_installation_verification_receipt(
            self.active_receipt_root, receipt
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _verify(self, snapshot=None):
        with patch(
            "skillguard_v2.installation_receipt.current_installation_snapshot",
            return_value=snapshot or self.snapshot,
        ):
            return verify_installation_verification_receipt(
                self.receipt_root,
                canonical_skill_root=self.canonical,
                codex_home=self.root,
            )

    def test_exact_current_installation_passes(self) -> None:
        report = self._verify()
        self.assertEqual(report["status"], "passed")
        self.assertEqual(self.snapshot, report["current_snapshot"])
        self.assertEqual(
            self.snapshot["current_installed_smoke_hash"],
            report["verified_context"]["current_installed_smoke_hash"],
        )
        self.assertNotIn("receipt_root", report["verified_context"])
        self.assertIn("context_binding_hash", report["verified_context"])
        json.dumps(report)

    def test_readonly_smoke_projection_never_starts_a_process(self) -> None:
        check_ids = [
            "installed:runtime-authority:skillguard",
            "installed:runtime-authority:skillguard-global-router",
            "installed:check-contract:skillguard",
            "installed:check-contract:skillguard-global-router",
            "installed:commands",
            "installed:self-check",
            "installed:check-skill",
            "installed:runtime-import",
            "installed:no-bytecode-residue",
        ]
        recorded = {
            "status": "passed",
            "checks": [
                {
                    "check_id": check_id,
                    "status": "passed",
                    "exit_code": 0,
                }
                for check_id in check_ids
            ],
            "skipped_checks": [],
        }
        installed_root = self.root / ".codex" / "skills" / "skillguard"
        installed_root.mkdir(parents=True)
        with patch(
            "skillguard_v2.installation.smoke_installed_skill",
            side_effect=AssertionError("read-only projection executed smoke"),
        ) as smoke:
            report = replay_installed_smoke_currentness(
                installed_root,
                recorded_smoke=recorded,
            )
        self.assertEqual("passed", report["status"])
        smoke.assert_not_called()

    def test_loader_returns_sealed_copy_safe_verified_context(self) -> None:
        with patch(
            "skillguard_v2.installation_receipt.current_installation_snapshot",
            return_value=self.snapshot,
        ):
            context = load_verified_installation_context(
                self.receipt_root,
                canonical_skill_root=self.canonical,
                codex_home=self.root,
            )
        snapshot_copy = context.current_snapshot
        snapshot_copy["current_installed_smoke_hash"] = "9" * 64
        self.assertEqual(
            self.snapshot["current_installed_smoke_hash"],
            context.current_snapshot["current_installed_smoke_hash"],
        )
        with self.assertRaises(FrozenInstanceError):
            context.receipt_hash = "9" * 64

    def test_old_runtime_new_prompt_or_install_drift_blocks(self) -> None:
        drift = dict(self.snapshot)
        changed_runtime = {
            **self.snapshot["installed_runtime_fingerprint"],
            "source_hash": "E" * 64,
        }
        drift["canonical_runtime_fingerprint"] = changed_runtime
        drift["installed_runtime_fingerprint"] = changed_runtime
        report = self._verify(drift)
        self.assertTrue(
            any(
                blocker.startswith("installation_verification_current_mismatch:")
                for blocker in report["blockers"]
            ),
            report,
        )

    def test_receipt_tamper_blocks(self) -> None:
        head = json.loads((self.receipt_root / "HEAD.json").read_text(encoding="utf-8"))
        receipt_path = self.receipt_root / head["receipt_ref"]["relative_path"]
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        payload["transaction_id"] = "install-" + "f" * 32
        receipt_path.write_text(json.dumps(payload), encoding="utf-8")
        self.assertEqual(self._verify()["status"], "blocked")

    def test_exact_shape_validator_rejects_missing_extra_and_invalid_status(self) -> None:
        head = json.loads((self.receipt_root / "HEAD.json").read_text(encoding="utf-8"))
        receipt_path = self.receipt_root / head["receipt_ref"]["relative_path"]
        original = json.loads(receipt_path.read_text(encoding="utf-8"))
        mutations = []
        missing = dict(original)
        missing.pop("current_installed_smoke_hash")
        mutations.append(missing)
        extra = dict(original)
        extra["caller_authorized"] = True
        mutations.append(extra)
        invalid_status = dict(original)
        invalid_status["status"] = "passed"
        mutations.append(invalid_status)
        for mutation in mutations:
            with self.subTest(fields=sorted(mutation)):
                with self.assertRaises(ValueError):
                    validate_installation_verification_receipt(mutation)

    def test_head_schema_tamper_blocks_even_with_recomputed_hash(self) -> None:
        head_path = self.receipt_root / "HEAD.json"
        head = json.loads(head_path.read_text(encoding="utf-8"))
        head["caller_authorized"] = True
        head["head_hash"] = canonical_hash(
            {key: value for key, value in head.items() if key != "head_hash"}
        )
        head_path.write_text(json.dumps(head), encoding="utf-8")
        report = self._verify()
        self.assertEqual("blocked", report["status"])
        self.assertIn("installation_head_shape_mismatch", report["blockers"][0])

    def test_current_smoke_result_command_and_environment_drift_block(self) -> None:
        for field_name in (
            "current_installed_smoke_hash",
            "current_installed_smoke_command_fingerprint",
            "current_installed_smoke_environment_fingerprint",
        ):
            drift = dict(self.snapshot)
            drift[field_name] = "9" * 64
            with self.subTest(field_name=field_name):
                report = self._verify(drift)
                self.assertIn(
                    f"installation_verification_current_mismatch:{field_name}",
                    report["blockers"],
                )

    def test_scheduled_identity_builder_binds_portable_current_install_receipt(self) -> None:
        with patch(
            "skillguard_v2.installation_receipt.current_installation_snapshot",
            return_value=self.snapshot,
        ), patch(
            "skillguard_v2.installation_receipt.guard_runtime_fingerprint",
            return_value=self.snapshot["installed_runtime_fingerprint"],
        ):
            context = load_verified_installation_context(
                self.active_receipt_root,
                canonical_skill_root=self.canonical,
                codex_home=self.root,
            )
            identity = build_scheduled_production_identity(
                scheduler_or_trigger_id="scheduler:update",
                scheduled_execution_id="scheduled:one",
                active_skill_root=self.active_skill_root,
                verified_context=context,
            )
            resolved = verify_scheduled_production_installation_identity(
                identity,
                active_skill_root=self.active_skill_root,
                verified_context=context,
            )
        self.assertEqual(
            {
                "path_token": "active_skill_root",
                "relative_path": ".sg-runtime/installation",
            },
            identity["installation_receipt_root_ref"],
        )
        self.assertEqual(
            self.snapshot["installed_runtime_fingerprint"]["source_hash"],
            identity["installed_runtime_fingerprint"],
        )
        self.assertEqual(
            "current_installed_parity", resolved["receipt"]["status"]
        )

    def test_sealed_context_reuse_does_not_repeat_current_smoke_replay(self) -> None:
        with patch(
            "skillguard_v2.installation_receipt.current_installation_snapshot",
            return_value=self.snapshot,
        ) as current_snapshot:
            context = load_verified_installation_context(
                self.active_receipt_root,
                canonical_skill_root=self.canonical,
                codex_home=self.root,
            )
            identity = build_scheduled_production_identity(
                scheduler_or_trigger_id="scheduler:update",
                scheduled_execution_id="scheduled:sealed",
                active_skill_root=self.active_skill_root,
                verified_context=context,
            )
            verify_scheduled_production_installation_identity(
                identity,
                active_skill_root=self.active_skill_root,
                verified_context=context,
            )
        self.assertEqual(1, current_snapshot.call_count)
        with self.assertRaises(TypeError):
            build_scheduled_production_identity(
                scheduler_or_trigger_id="scheduler:update",
                scheduled_execution_id="scheduled:caller-dict",
                active_skill_root=self.active_skill_root,
                verified_context=context.identity(),
            )

    def test_scheduled_identity_replay_requires_context_and_new_operation_rejects_drift(self) -> None:
        with patch(
            "skillguard_v2.installation_receipt.current_installation_snapshot",
            return_value=self.snapshot,
        ), patch(
            "skillguard_v2.installation_receipt.guard_runtime_fingerprint",
            return_value=self.snapshot["installed_runtime_fingerprint"],
        ):
            context = load_verified_installation_context(
                self.active_receipt_root,
                canonical_skill_root=self.canonical,
                codex_home=self.root,
            )
            identity = build_scheduled_production_identity(
                scheduler_or_trigger_id="scheduler:update",
                scheduled_execution_id="scheduled:stale",
                active_skill_root=self.active_skill_root,
                verified_context=context,
            )
        drift = dict(self.snapshot)
        drift["installed_runtime_fingerprint"] = {
            **self.snapshot["installed_runtime_fingerprint"],
            "source_hash": "F" * 64,
        }
        with patch(
            "skillguard_v2.installation_receipt.current_installation_snapshot",
            return_value=drift,
        ), patch(
            "skillguard_v2.installation_receipt.guard_runtime_fingerprint",
            return_value=self.snapshot["installed_runtime_fingerprint"],
        ), self.assertRaisesRegex(
            ValueError, "installation_snapshot_runtime_fingerprint_mismatch"
        ):
            load_verified_installation_context(
                self.active_receipt_root,
                canonical_skill_root=self.canonical,
                codex_home=self.root,
            )
        with self.assertRaisesRegex(
            ValueError, "verified_installation_context_required"
        ):
            verify_scheduled_production_installation_identity(
                identity, active_skill_root=self.active_skill_root
            )

    def test_real_active_installation_receipt_subtree_replays_without_mocking(self) -> None:
        canonical = ROOT / ".agents" / "skills" / "skillguard"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage = root / "stage" / ".codex" / "skills" / "skillguard"
            codex_home = root / "active" / ".codex"
            self.assertEqual("passed", prepare_stage(canonical, stage)["status"])
            activated = activate_stage(canonical, stage, codex_home)
            self.assertEqual("passed", activated["status"], activated)
            snapshot = current_installation_snapshot(
                canonical,
                codex_home=codex_home,
            )
            receipt = build_installation_verification_receipt(snapshot)
            receipt_root = (
                codex_home
                / "skills"
                / "skillguard"
                / ".sg-runtime"
                / "installation"
            )
            write_installation_verification_receipt(receipt_root, receipt)

            report = verify_installation_verification_receipt(
                receipt_root,
                canonical_skill_root=canonical,
                codex_home=codex_home,
            )

            self.assertEqual("passed", report["status"], report)
            self.assertEqual(
                snapshot["installed_source_identity"],
                report["current_snapshot"]["installed_source_identity"],
            )

    def test_cli_defaults_to_exact_active_installation_receipt_root(self) -> None:
        with patch(
            "skillguard_v2.portfolio_cli.verify_installation_verification_receipt",
            return_value={"status": "passed", "blockers": []},
        ) as verifier, patch("skillguard_v2.portfolio_cli._output"):
            exit_code = verify_installation_receipt_command(
                [
                    "--repository-root",
                    str(ROOT),
                    "--codex-home",
                    str(self.root),
                    "--require-current-installed-parity",
                ]
            )
        self.assertEqual(0, exit_code)
        self.assertEqual(
            self.active_receipt_root.resolve(),
            verifier.call_args.args[0],
        )

    def test_cli_rejects_foreign_absolute_installation_receipt_root(self) -> None:
        foreign = self.root / "foreign-receipt"
        foreign.mkdir()
        with self.assertRaisesRegex(
            ValueError, "exact active SkillGuard installation receipt root"
        ):
            verify_installation_receipt_command(
                [
                    "--repository-root",
                    str(ROOT),
                    "--codex-home",
                    str(self.root),
                    "--receipt-root",
                    str(foreign),
                    "--require-current-installed-parity",
                ]
            )


if __name__ == "__main__":
    unittest.main()
