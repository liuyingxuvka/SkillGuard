from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / ".agents" / "skills" / "skillguard" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from skillguard_v2.consumer_distribution import (  # noqa: E402
    audit_consumer_distribution,
    build_consumer_distribution,
)
from skillguard_v2.contract_compiler import compile_skill_contract  # noqa: E402


class InstalledParityAuthorityTests(unittest.TestCase):
    """Current consumer projection parity is the installation authority.

    The former fixture consumed the removed author-side content-impact plan
    and replayed portfolio receipts.  Compact v3 exposes one explicit
    consumer projection, so the current tests build two exact projections and
    verify the installed tree against its target-owned release manifest.
    """

    @classmethod
    def setUpClass(cls) -> None:
        compiled = compile_skill_contract(ROOT, write=False)
        non_stale = [
            finding
            for finding in compiled.findings
            if finding.code != "stale_generated_contract"
        ]
        if non_stale or not compiled.compiled_contract:
            raise AssertionError(compiled.findings)
        cls.compiled_contract = dict(compiled.compiled_contract)

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repository = self.root / "repository"
        self.canonical = self.root / "canonical"
        self.installed = self.root / "installed"
        self.repository.mkdir()
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
        source = ROOT / ".agents" / "skills" / "skillguard"
        for destination in (self.canonical, self.installed):
            built = build_consumer_distribution(
                source,
                destination,
                self.compiled_contract,
            )
            self.assertEqual("passed", built["status"], built)

    def _issue(self) -> dict[str, object]:
        return audit_consumer_distribution(self.installed)

    def test_current_receipt_binds_only_exact_installation_projection(self) -> None:
        receipt = self._issue()
        self.assertEqual("passed", receipt["status"], receipt)
        canonical = audit_consumer_distribution(self.canonical)
        self.assertEqual(canonical["release_id"], receipt["release_id"])
        self.assertNotIn(
            ".skillguard",
            {row["path"] for row in receipt["manifest"]["files"]},
        )

        before = receipt["release_id"]
        unrelated = self.repository / "work" / "latest-report.json"
        unrelated.parent.mkdir(parents=True)
        unrelated.write_text('{"status":"pass"}\n', encoding="utf-8")
        after = self._issue()
        self.assertEqual(before, after["release_id"])
        self.assertEqual("passed", after["status"])

    def test_installation_member_change_blocks_and_read_only_replay_goes_stale(self) -> None:
        receipt = self._issue()
        self.assertEqual("passed", receipt["status"], receipt)
        member_path = next(
            row["path"]
            for row in receipt["manifest"]["files"]
            if row["path"] != "consumer-release.json"
        )
        candidate = self.installed / Path(*str(member_path).split("/"))
        candidate.write_bytes(candidate.read_bytes() + b"\n")
        replay = self._issue()
        self.assertEqual("blocked", replay["status"], replay)
        self.assertTrue(
            any(
                row["code"] == "consumer_file_hash_mismatch"
                for row in replay["findings"]
            ),
            replay,
        )
        self.assertEqual(receipt["release_id"], replay["release_id"])

    def test_projection_policy_change_stales_without_reissuing_owner_receipt(self) -> None:
        receipt = self._issue()
        manifest_path = self.installed / "consumer-release.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["projection_id"] = "projection:retired"
        manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
        stale = self._issue()
        self.assertEqual("blocked", stale["status"], stale)
        self.assertTrue(
            any(
                row["code"] == "consumer_release_manifest_invalid"
                for row in stale["findings"]
            ),
            stale,
        )
        self.assertEqual(receipt["release_id"], stale["release_id"])

    def test_tampered_projection_cannot_be_resigned_as_current(self) -> None:
        manifest_path = self.installed / "consumer-release.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"].pop()
        manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
        findings = self._issue()
        self.assertEqual("blocked", findings["status"], findings)
        self.assertTrue(
            any(
                row["code"]
                in {
                    "consumer_release_manifest_hash_invalid",
                    "consumer_release_manifest_noncanonical",
                    "consumer_file_missing",
                }
                for row in findings["findings"]
            ),
            findings,
        )

    def test_legacy_v1_shape_is_rejection_only(self) -> None:
        legacy = self.root / "legacy"
        legacy.mkdir()
        (legacy / "consumer-release.json").write_text(
            json.dumps(
                {
                    "schema_version": "skillguard.portfolio_installed_content_parity_receipt.v1",
                    "receipt_id": "installed-parity-legacy",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        report = audit_consumer_distribution(legacy)
        self.assertEqual("blocked", report["status"], report)
        codes = {row["code"] for row in report["findings"]}
        self.assertIn("consumer_release_manifest_invalid", codes)
        self.assertIn("consumer_release_manifest_fields_invalid", codes)


if __name__ == "__main__":
    unittest.main()
