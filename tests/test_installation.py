from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / ".agents" / "skills" / "skillguard"
SCRIPT_ROOT = SKILL_ROOT / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import skillguard_v2.installation as installation_module  # noqa: E402
from skillguard_v2.installation import (  # noqa: E402
    _activation_receipt_current,
    _hardened_activation_receipt_historical_integrity,
    _load_transaction,
    _persist_transaction,
    _write_install_head,
    activate_stage,
    prepare_stage,
    recover_incomplete_installations,
    smoke_installed_skill,
    verify_stage,
)
from skillguard_v2.installation_receipt import (  # noqa: E402
    build_installation_verification_receipt,
    current_installation_snapshot,
    write_installation_verification_receipt,
)
from tests._runtime_authority_consumer_fixture import (  # noqa: E402
    add_old_flat_run_rejection,
    install_stub_runtime,
    make_current_skill,
    make_old_lifecycle_rejection_skill,
    make_old_pair_rejection_skill,
)


class InstallationTests(unittest.TestCase):
    def test_former_terminal_install_record_is_stored_only_during_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            codex_home = root / "active" / ".codex"
            former_id = "install-" + ("a" * 32)
            former = {
                "schema_version": installation_module.TRANSACTION_SCHEMA,
                "artifact_type": "skillguard_install_transaction",
                "transaction_id": former_id,
                "status": "committed",
                "phase": "committed",
                "generation": 1,
                "previous_committed_transaction_id": None,
                "member_order": ["skillguard", "skillguard-global-router"],
                "members": {
                    member_id: {
                        "active_root": str(codex_home / "skills" / member_id),
                        "incoming_root": str(
                            codex_home
                            / "skills"
                            / f".{member_id}-installing-{former_id[8:]}"
                        ),
                        "backup_root": str(
                            codex_home / "backups" / f"{member_id}-{former_id[8:]}"
                        ),
                    }
                    for member_id in ("skillguard", "skillguard-global-router")
                },
                "activation_receipt_path": str(
                    codex_home
                    / "install-transactions"
                    / "receipts"
                    / f"{former_id}-activation.json"
                ),
            }
            _persist_transaction(codex_home, former)
            _write_install_head(
                codex_home,
                transaction_id=former_id,
                previous_transaction_id=None,
                generation=1,
            )

            recovery = recover_incomplete_installations(codex_home)
            self.assertEqual("passed", recovery["status"], recovery)
            self.assertEqual([former_id], recovery["former_terminal_record_ids"])

            stage = root / "stage" / ".codex" / "skills" / "skillguard"
            self.assertEqual("passed", prepare_stage(SKILL_ROOT, stage)["status"])
            activated = activate_stage(SKILL_ROOT, stage, codex_home)
            self.assertEqual("passed", activated["status"], activated)

    def test_complete_stage_passes_parity_and_installed_layout_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary) / "stage" / ".codex" / "skills" / "skillguard"
            prepared = prepare_stage(SKILL_ROOT, stage)
            self.assertEqual("passed", prepared["status"], prepared)
            verified = verify_stage(SKILL_ROOT, stage)
            self.assertEqual("passed", verified["status"], verified)
            self.assertEqual("passed", verified["smoke"]["status"], verified["smoke"])

    def test_installed_suite_contract_smoke_binds_the_explicit_layout_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            installed = (
                Path(temporary) / ".codex" / "skills" / "skillguard"
            )
            layout_root, checks = installation_module._installed_smoke_plan(
                installed,
                active_installation_currentness=False,
            )
            contract_checks = {
                row["check_id"]: row["command"]
                for row in checks
                if row["check_id"].startswith("installed:check-contract:")
            }
            self.assertEqual(
                {
                    "installed:check-contract:skillguard",
                    "installed:check-contract:skillguard-global-router",
                },
                set(contract_checks),
            )
            for command in contract_checks.values():
                self.assertIn("--repository-root", command)
                root_index = command.index("--repository-root") + 1
                self.assertEqual(str(layout_root), command[root_index])

    def test_partial_stage_is_blocked_as_a_source_downgrade(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary) / ".codex" / "skills" / "skillguard"
            stage.mkdir(parents=True)
            stage.joinpath("SKILL.md").write_text("partial\n", encoding="utf-8")
            verified = verify_stage(SKILL_ROOT, stage)
            self.assertEqual("blocked", verified["status"])
            self.assertIn("staged_source_parity_failed", verified["blockers"])

    def test_verified_stage_can_activate_into_an_empty_codex_home(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage = root / "stage" / ".codex" / "skills" / "skillguard"
            codex_home = root / "active" / ".codex"
            prepare_stage(SKILL_ROOT, stage)
            activated = activate_stage(SKILL_ROOT, stage, codex_home)
            self.assertEqual("passed", activated["status"], activated)
            self.assertTrue((codex_home / "skills" / "skillguard" / "SKILL.md").is_file())
            self.assertEqual([], activated["comparison"]["missing_in_installed"])
            record = _load_transaction(codex_home, activated["transaction_id"])
            self.assertTrue(_activation_receipt_current(record))
            activation_receipt = json.loads(
                Path(activated["receipt_path"]).read_text(encoding="utf-8")
            )
            for field in (
                "stage_verification_hash",
                "post_activation_smoke_hash",
                "post_activation_member_comparisons_hash",
                "rollback_disposition",
            ):
                self.assertIn(field, activation_receipt)

            mutations = []
            missing_stage = copy.deepcopy(record)
            missing_stage.pop("stage_verification")
            mutations.append(missing_stage)
            failed_smoke = copy.deepcopy(record)
            failed_smoke["post_activation_smoke"]["status"] = "failed"
            mutations.append(failed_smoke)
            stale_parity = copy.deepcopy(record)
            stale_parity["post_activation_member_comparisons"]["skillguard"][
                "changed_in_installed"
            ] = ["SKILL.md"]
            mutations.append(stale_parity)
            rolled_back = copy.deepcopy(record)
            rolled_back["rollback_disposition"] = "performed"
            mutations.append(rolled_back)
            for mutation in mutations:
                with self.subTest(mutation=mutation.get("rollback_disposition", "evidence")):
                    self.assertFalse(_activation_receipt_current(mutation))

            former_record = copy.deepcopy(record)
            former_receipt = copy.deepcopy(activation_receipt)
            for field in (
                "stage_verification_hash",
                "post_activation_smoke_hash",
                "post_activation_member_comparisons_hash",
                "rollback_disposition",
            ):
                former_receipt.pop(field)
            former_path = (
                codex_home / "install-transactions" / "receipts" / "former.json"
            )
            former_path.write_text(
                json.dumps(former_receipt, sort_keys=True), encoding="utf-8"
            )
            former_record["activation_receipt_path"] = str(former_path)
            former_record.pop("stage_verification")
            former_record.pop("rollback_disposition")
            self.assertFalse(_activation_receipt_current(former_record))
            self.assertFalse(
                hasattr(installation_module, "_legacy_activation_receipt_current_for_upgrade")
            )
            self.assertFalse(
                hasattr(installation_module, "_legacy_activation_receipt_stored_integrity")
            )

    def test_stage_path_must_use_an_isolated_codex_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                prepare_stage(SKILL_ROOT, Path(temporary) / "skillguard")

    def test_prepare_stage_accepts_only_current_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canonical_parent = root / "canonical"
            canonical = canonical_parent / "skillguard"
            make_current_skill(canonical, "skillguard")
            make_current_skill(
                canonical_parent / "skillguard-global-router",
                "skillguard-global-router",
            )
            install_stub_runtime(canonical)
            stage = root / "stage" / ".codex" / "skills" / "skillguard"
            report = prepare_stage(canonical, stage)
            self.assertEqual("passed", report["status"], report)
            self.assertEqual(
                "current",
                report["runtime_authority"]["skillguard"]["authority"],
            )

    def test_prepare_stage_blocks_unconverted_authority_without_copy(self) -> None:
        for label, builder in (
            ("old-lifecycle", make_old_lifecycle_rejection_skill),
            ("old-pair", make_old_pair_rejection_skill),
        ):
            with self.subTest(shape=label), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                canonical_parent = root / "canonical"
                canonical = canonical_parent / "skillguard"
                builder(canonical, "skillguard")
                builder(
                    canonical_parent / "skillguard-global-router",
                    "skillguard-global-router",
                )
                install_stub_runtime(canonical)
                stage = root / "stage" / ".codex" / "skills" / "skillguard"
                report = prepare_stage(canonical, stage)
                self.assertEqual("blocked", report["status"], report)
                self.assertFalse(stage.exists())
                self.assertEqual(
                    "blocked",
                    report["runtime_authority"]["skillguard"]["authority"],
                )
                self.assertIn(
                    "canonical_runtime_authority_blocked",
                    report["blockers"],
                )

    def test_prepare_stage_blocks_retired_residual_before_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canonical_parent = root / "canonical"
            canonical = canonical_parent / "skillguard"
            make_current_skill(canonical, "skillguard")
            make_current_skill(
                canonical_parent / "skillguard-global-router",
                "skillguard-global-router",
            )
            install_stub_runtime(canonical)
            add_old_flat_run_rejection(canonical)
            stage = root / "stage" / ".codex" / "skills" / "skillguard"
            report = prepare_stage(canonical, stage)
            self.assertEqual("blocked", report["status"])
            self.assertIn("former_runtime_residual", report["blockers"])
            self.assertFalse(stage.exists())
            self.assertIsNone(report["copy"])

    def test_stage_excludes_runtime_outputs_and_source_only_fixture_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canonical_parent = root / "canonical"
            canonical = canonical_parent / "skillguard"
            make_current_skill(canonical, "skillguard")
            make_current_skill(
                canonical_parent / "skillguard-global-router",
                "skillguard-global-router",
            )
            install_stub_runtime(canonical)
            runtime_cache = canonical / ".skillguard" / "runs" / "runtime.txt"
            runtime_cache.parent.mkdir(parents=True, exist_ok=True)
            runtime_cache.write_text("transient\n", encoding="utf-8")
            fixture_run = (
                canonical
                / "fixtures"
                / "legacy-target"
                / ".skillguard"
                / "runs"
                / "static-fixture.json"
            )
            fixture_run.parent.mkdir(parents=True, exist_ok=True)
            fixture_run.write_text("{}\n", encoding="utf-8")

            stage = root / "stage" / ".codex" / "skills" / "skillguard"
            prepared = prepare_stage(canonical, stage)

            self.assertEqual("passed", prepared["status"], prepared)
            self.assertFalse((stage / ".skillguard" / "runs").exists())
            self.assertFalse(
                (
                    stage
                    / "fixtures"
                    / "legacy-target"
                    / ".skillguard"
                    / "runs"
                    / "static-fixture.json"
                ).is_file()
            )

    def test_prepare_stage_blocks_reserved_runtime_workspace_before_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canonical_parent = root / "canonical"
            canonical = canonical_parent / "skillguard"
            make_current_skill(canonical, "skillguard")
            make_current_skill(
                canonical_parent / "skillguard-global-router",
                "skillguard-global-router",
            )
            install_stub_runtime(canonical)
            runtime = (
                canonical
                / ".sg-runtime"
                / "installation"
                / "receipts"
                / "receipt.json"
            )
            runtime.parent.mkdir(parents=True)
            runtime.write_text("{}\n", encoding="utf-8")
            stage = root / "stage" / ".codex" / "skills" / "skillguard"

            report = prepare_stage(canonical, stage)

            self.assertEqual("blocked", report["status"])
            self.assertFalse(stage.exists())
            self.assertIsNone(report["copy"])
            self.assertIn(
                "canonical_runtime_artifact_present:skillguard:.sg-runtime",
                report["blockers"],
            )

    def test_installed_smoke_accepts_current_authority_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            skills = Path(temporary) / ".codex" / "skills"
            skill = skills / "skillguard"
            make_current_skill(skill, "skillguard")
            make_current_skill(
                skills / "skillguard-global-router", "skillguard-global-router"
            )
            install_stub_runtime(skill)
            report = smoke_installed_skill(skill, timeout_seconds=30)
            self.assertEqual("passed", report["status"], report)
            authority_checks = [
                row
                for row in report["checks"]
                if row["check_id"].startswith("installed:runtime-authority:")
            ]
            self.assertEqual(2, len(authority_checks))
            self.assertTrue(
                all('"authority": "current"' in row["stdout_tail"] for row in authority_checks)
            )

    def test_installed_smoke_rejects_residual_before_other_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            skills = Path(temporary) / ".codex" / "skills"
            skill = skills / "skillguard"
            make_current_skill(skill, "skillguard")
            make_current_skill(
                skills / "skillguard-global-router", "skillguard-global-router"
            )
            install_stub_runtime(skill)
            add_old_flat_run_rejection(skill)
            report = smoke_installed_skill(skill, timeout_seconds=30)
            self.assertEqual("failed", report["status"])
            self.assertEqual(1, len(report["checks"]))
            self.assertEqual(
                "installed:runtime-authority:skillguard",
                report["checks"][0]["check_id"],
            )
            self.assertIn("former_runtime_residual", report["checks"][0]["stdout_tail"])

    def test_isolated_current_suite_verifies_and_activates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canonical_parent = root / "canonical"
            canonical = canonical_parent / "skillguard"
            make_current_skill(canonical, "skillguard")
            make_current_skill(
                canonical_parent / "skillguard-global-router",
                "skillguard-global-router",
            )
            install_stub_runtime(canonical)
            stage = root / "stage" / ".codex" / "skills" / "skillguard"
            codex_home = root / "active" / ".codex"
            prepared = prepare_stage(canonical, stage)
            self.assertEqual("passed", prepared["status"], prepared)
            verified = verify_stage(canonical, stage)
            self.assertEqual("passed", verified["status"], verified)
            activated = activate_stage(canonical, stage, codex_home)
            self.assertEqual("passed", activated["status"], activated)
            self.assertEqual(
                "current",
                activated["member_comparisons"]["skillguard"][
                    "installed_runtime_authority"
                ]["authority"],
            )


    def test_two_consecutive_hardened_installs_keep_non_head_history_stored_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            codex_home = root / "active" / ".codex"
            first_stage = root / "stage-one" / ".codex" / "skills" / "skillguard"
            self.assertEqual("passed", prepare_stage(SKILL_ROOT, first_stage)["status"])
            first = activate_stage(SKILL_ROOT, first_stage, codex_home)
            self.assertEqual("passed", first["status"], first)
            snapshot = current_installation_snapshot(
                SKILL_ROOT,
                codex_home=codex_home,
            )
            receipt = build_installation_verification_receipt(snapshot)
            write_installation_verification_receipt(
                codex_home
                / "skills"
                / "skillguard"
                / ".sg-runtime"
                / "installation",
                receipt,
            )

            second_stage = root / "stage-two" / ".codex" / "skills" / "skillguard"
            self.assertEqual("passed", prepare_stage(SKILL_ROOT, second_stage)["status"])
            second = activate_stage(SKILL_ROOT, second_stage, codex_home)
            self.assertEqual("passed", second["status"], second)

            first_record = _load_transaction(codex_home, first["transaction_id"])
            self.assertTrue(
                _hardened_activation_receipt_historical_integrity(first_record)
            )
            detached_history = copy.deepcopy(first_record)
            for member_id, member in detached_history["members"].items():
                member["active_root"] = str(root / "no-longer-live" / member_id)
            self.assertTrue(
                _hardened_activation_receipt_historical_integrity(detached_history)
            )
            recovery = recover_incomplete_installations(codex_home)
            self.assertEqual("passed", recovery["status"], recovery)

    def test_source_upgrade_preserves_the_current_committed_head_until_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canonical_parent = root / "canonical"
            canonical = canonical_parent / "skillguard"
            make_current_skill(canonical, "skillguard", revision="first source revision")
            make_current_skill(
                canonical_parent / "skillguard-global-router",
                "skillguard-global-router",
            )
            codex_home = root / "active" / ".codex"
            first_stage = root / "stage-one" / ".codex" / "skills" / "skillguard"
            self.assertEqual("passed", prepare_stage(canonical, first_stage)["status"])
            first = activate_stage(canonical, first_stage, codex_home)
            self.assertEqual("passed", first["status"], first)

            make_current_skill(canonical, "skillguard", revision="second source revision")
            self.assertFalse(
                _activation_receipt_current(
                    _load_transaction(codex_home, first["transaction_id"])
                )
            )

            second_stage = root / "stage-two" / ".codex" / "skills" / "skillguard"
            self.assertEqual("passed", prepare_stage(canonical, second_stage)["status"])
            second = activate_stage(canonical, second_stage, codex_home)
            self.assertEqual("passed", second["status"], second)
            self.assertEqual(
                "committed",
                _load_transaction(codex_home, first["transaction_id"])["status"],
            )
            second_record = _load_transaction(codex_home, second["transaction_id"])
            self.assertEqual(
                first["transaction_id"],
                second_record["previous_committed_transaction_id"],
            )
            self.assertTrue(_activation_receipt_current(second_record))

    def test_commit_head_recovery_uses_canonical_phase_and_separate_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage = root / "stage" / ".codex" / "skills" / "skillguard"
            codex_home = root / "active" / ".codex"
            self.assertEqual("passed", prepare_stage(SKILL_ROOT, stage)["status"])
            activated = activate_stage(SKILL_ROOT, stage, codex_home)
            self.assertEqual("passed", activated["status"], activated)
            record = _load_transaction(codex_home, activated["transaction_id"])
            record["status"] = "commit_head_pending"
            record["phase"] = "install_head_written"
            _persist_transaction(codex_home, record)

            recovery = recover_incomplete_installations(codex_home)
            recovered = _load_transaction(codex_home, activated["transaction_id"])

            self.assertEqual("recovered", recovery["status"], recovery)
            self.assertEqual("committed", recovered["status"])
            self.assertEqual("committed", recovered["phase"])
            self.assertEqual(
                "commit_head_finalize",
                recovered["recovery_provenance"]["recovery_kind"],
            )
            self.assertEqual(
                "install_head_written",
                recovered["recovery_provenance"]["recovered_from_phase"],
            )


if __name__ == "__main__":
    unittest.main()
