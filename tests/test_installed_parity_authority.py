from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / ".agents" / "skills" / "skillguard" / "scripts"
SKILL_ROOT = ROOT / ".agents" / "skills" / "skillguard"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from skillguard_v2.contract_compiler import (  # noqa: E402
    canonical_json_bytes,
    compile_skill_contract,
    current_content_projection,
)
from skillguard_v2.installation import installation_member_paths  # noqa: E402
from skillguard_v2.installed_parity import (  # noqa: E402
    INSTALLED_PARITY_RECEIPT_SCHEMA,
    replay_installed_content_parity_currentness,
    validate_installed_parity_receipt,
    verify_installed_content_parity,
)
from skillguard_v2.wire_identity import wire_hash  # noqa: E402


class InstalledParityAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        compiled = compile_skill_contract(
            SKILL_ROOT,
            repository_root=ROOT,
            write=False,
        )
        non_stale = [
            finding
            for finding in compiled.findings
            if finding.code != "stale_generated_contract"
        ]
        if non_stale or not compiled.check_manifest or not compiled.compiled_contract:
            raise AssertionError(compiled.findings)
        cls.compiled_contract = compiled.compiled_contract
        cls.check_manifest = compiled.check_manifest
        cls.portfolio_projection_hash = current_content_projection(
            cls.check_manifest["content_impact_plan"],
            "projection:portfolio",
        )["consumer_projection_hash"]

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repository = self.root / "repository"
        self.canonical = self.repository / ".agents" / "skills" / "skillguard"
        self.installed = self.root / "installed"
        self._materialize_current_member()
        self.identity = {
            "skill_id": "skillguard",
            "target_kind": "single_skill",
            "skill_root_token": ".agents/skills/skillguard",
            "skill_paths": [".agents/skills/skillguard"],
            "member_identities": [
                {
                    "member_skill_id": "skillguard",
                    "skill_path": ".agents/skills/skillguard",
                }
            ],
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _materialize_current_member(self) -> None:
        plan = self.check_manifest["content_impact_plan"]
        installation = current_content_projection(plan, "projection:installation")
        components = {
            row["component_id"]: row for row in plan["components"]
        }
        prefix = ".agents/skills/skillguard/"
        for component_id in installation["input_component_ids"]:
            for repository_path in components[component_id]["member_paths"]:
                self.assertTrue(repository_path.startswith(prefix), repository_path)
                relative = repository_path[len(prefix) :]
                destination = self.canonical / Path(*relative.split("/"))
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / Path(*repository_path.split("/")), destination)
        control = self.canonical / ".skillguard"
        control.mkdir(parents=True, exist_ok=True)
        control.joinpath("compiled-contract.json").write_bytes(
            canonical_json_bytes(self.compiled_contract)
        )
        control.joinpath("check-manifest.json").write_bytes(
            canonical_json_bytes(self.check_manifest)
        )
        control.joinpath("contract-source.json").write_bytes(
            (SKILL_ROOT / ".skillguard" / "contract-source.json").read_bytes()
        )
        for relative in installation_member_paths(self.canonical):
            source = self.canonical / Path(*relative.split("/"))
            destination = self.installed / Path(*relative.split("/"))
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    def _issue(self) -> dict[str, object]:
        return verify_installed_content_parity(
            self.repository,
            self.identity,
            self.installed,
            portfolio_projection_hash=self.portfolio_projection_hash,
        )

    def test_current_receipt_binds_only_exact_installation_projection(self) -> None:
        receipt = self._issue()
        self.assertEqual(INSTALLED_PARITY_RECEIPT_SCHEMA, receipt["schema_version"])
        self.assertEqual("current", receipt["status"], receipt)
        self.assertEqual(
            [],
            validate_installed_parity_receipt(
                receipt,
                portfolio_projection_hash=self.portfolio_projection_hash,
            ),
        )
        self.assertNotIn("preparation_id", receipt)
        self.assertNotIn("guard_runtime", receipt)
        self.assertNotIn("target_identity_receipt_hash", receipt["target"])
        self.assertRegex(receipt["receipt_id"], r"^sha256:[0-9a-f]{64}$")

        before = receipt["receipt_id"]
        report = self.canonical / "work" / "latest-report.json"
        report.parent.mkdir(parents=True)
        report.write_text('{"status":"pass"}\n', encoding="utf-8")
        after = self._issue()
        self.assertEqual(before, after["receipt_id"])
        self.assertEqual("current", after["status"])

    def test_installation_member_change_blocks_and_read_only_replay_goes_stale(self) -> None:
        receipt = self._issue()
        self.assertEqual(
            [],
            replay_installed_content_parity_currentness(
                receipt,
                canonical_repository_root=self.repository,
                target_identity=self.identity,
                installed_target_root=self.installed,
                portfolio_projection_hash=self.portfolio_projection_hash,
            ),
        )
        changed_path = next(
            path
            for path in installation_member_paths(self.canonical)
            if path not in {
                ".skillguard/check-manifest.json",
                ".skillguard/compiled-contract.json",
            }
        )
        candidate = self.installed / Path(*changed_path.split("/"))
        candidate.write_bytes(candidate.read_bytes() + b"\n")
        findings = replay_installed_content_parity_currentness(
            receipt,
            canonical_repository_root=self.repository,
            target_identity=self.identity,
            installed_target_root=self.installed,
            portfolio_projection_hash=self.portfolio_projection_hash,
        )
        self.assertIn("installed_parity_receipt_stale", findings)
        blocked = self._issue()
        self.assertEqual("blocked", blocked["status"])

    def test_projection_policy_change_stales_without_reissuing_owner_receipt(self) -> None:
        receipt = self._issue()
        changed_projection = "sha256:" + "1" * 64
        findings = replay_installed_content_parity_currentness(
            receipt,
            canonical_repository_root=self.repository,
            target_identity=self.identity,
            installed_target_root=self.installed,
            portfolio_projection_hash=changed_projection,
        )
        self.assertIn(
            "installed_parity_receipt_portfolio_projection_stale",
            findings,
        )

    def test_tampered_projection_cannot_be_resigned_as_current(self) -> None:
        receipt = copy.deepcopy(self._issue())
        receipt["members"][0]["installed_file_hashes"].pop(
            next(iter(receipt["members"][0]["installed_file_hashes"]))
        )
        semantic_keys = (
            "schema_version",
            "owner_id",
            "verifier_id",
            "manifest_policy_id",
            "portfolio_projection_hash",
            "target",
            "members",
            "status",
            "blockers",
        )
        receipt["receipt_id"] = wire_hash(
            {key: receipt[key] for key in semantic_keys}
        )
        unsigned = dict(receipt)
        unsigned.pop("receipt_hash", None)
        receipt["receipt_hash"] = wire_hash(unsigned)
        findings = validate_installed_parity_receipt(receipt)
        self.assertTrue(
            any(value.endswith("_mismatch") for value in findings),
            findings,
        )

    def test_legacy_v1_shape_is_rejection_only(self) -> None:
        legacy = {
            "schema_version": "skillguard.portfolio_installed_content_parity_receipt.v1",
            "receipt_id": "installed-parity-legacy",
        }
        findings = validate_installed_parity_receipt(legacy)
        self.assertIn("installed_parity_receipt_schema_unsupported", findings)
        self.assertIn("installed_parity_receipt_structure_invalid", findings)


if __name__ == "__main__":
    unittest.main()
