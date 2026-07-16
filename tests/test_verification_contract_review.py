from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from _skillguard_v2_runtime_fixture import SCRIPT_ROOT  # noqa: F401
from skillguard_v2.verification_contract_review import review_verification_contract


def contract_text(watch: list[str], *, duplicate: bool = False) -> str:
    checks = """checks:
  - id: check.one
    kind: command
    command: python
    args:
      - ./tests/run.py
    covers:
      - req.one
"""
    if duplicate:
        checks += """  - id: check.two
    kind: command
    command: python
    args:
      - tests/../tests/run.py
    covers:
      - req.one
"""
    return checks + "freshness:\n  watch:\n" + "".join(
        f"    - {row}\n" for row in watch
    )


class VerificationContractReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.change = self.repo / "openspec" / "changes" / "sample"
        self.change.mkdir(parents=True)
        self.contract = self.change / "verification-contract.yaml"
        self.report = self.change / "verification-report.json"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _review(self, watch: list[str], *, duplicate: bool = False):
        self.contract.write_text(contract_text(watch, duplicate=duplicate), encoding="utf-8")
        return review_verification_contract(self.contract, repository_root=self.repo)

    def test_direct_normalized_and_globbed_collisions_block(self) -> None:
        cases = (
            "openspec/changes/sample/verification-report.json",
            "openspec/changes/sample/./verification-report.json",
            "openspec/changes/**/verification-report.json",
            "openspec/changes/sample/*.json",
        )
        for watch in cases:
            with self.subTest(watch=watch):
                payload = self._review([watch])
                self.assertEqual(payload["status"], "blocked")
                self.assertIn(
                    "verification_report_in_freshness_watch",
                    {row["code"] for row in payload["findings"]},
                )

    def test_link_equivalent_collision_blocks_when_supported(self) -> None:
        target = self.repo / "work" / "future-report.json"
        target.parent.mkdir(parents=True)
        target.write_text("{}\n", encoding="utf-8")
        try:
            os.link(target, self.report)
        except OSError as exc:
            self.fail(f"hardlink fixture unavailable: {exc}")
        payload = self._review(["work/future-report.json"])
        self.assertEqual(payload["status"], "blocked")

    def test_safe_report_outside_watch_passes(self) -> None:
        payload = self._review(
            [
                "tests/**/*.py",
                "docs/*.md",
                ".agents/skills/skillguard/.skillguard/contract-source.json",
            ]
        )
        self.assertEqual(payload["status"], "passed")

    def test_runtime_evidence_outputs_cannot_be_freshness_inputs(self) -> None:
        cases = (
            "work/verification/task/receipts/*.json",
            ".agents/skills/demo/.sg-runtime/installation/HEAD.json",
            ".agents/skills/demo/.skillguard/runs/*.json",
            ".agents/skills/demo/.skillguard/v1-retirement-completion-receipt.json",
            ".agents/skills/demo/.skillguard/*.json",
        )
        for watch in cases:
            with self.subTest(watch=watch):
                payload = self._review([watch])
                self.assertIn(
                    "verification_evidence_output_in_freshness_watch",
                    {row["code"] for row in payload["findings"]},
                )

    def test_declared_custom_evidence_roots_cannot_be_watched(self) -> None:
        self.contract.write_text(
            """checks:
  - id: check.consume
    kind: command
    command: python
    args:
      - consume.py
      - --replay-receipt-root
      - custom/evidence/closure
      - --result-root
      - custom/evidence/results
    covers:
      - req.one
freshness:
  watch:
    - custom/evidence/**/*.json
""",
            encoding="utf-8",
        )
        payload = review_verification_contract(
            self.contract, repository_root=self.repo
        )
        self.assertIn(
            "verification_evidence_output_in_freshness_watch",
            {row["code"] for row in payload["findings"]},
        )

    def test_malformed_and_escape_watch_paths_block(self) -> None:
        for watch in ("../verification-report.json", "/tmp/report.json", "C:\\temp\\report.json"):
            with self.subTest(watch=watch):
                payload = self._review([watch])
                self.assertIn(
                    "freshness_watch_path_invalid",
                    {row["code"] for row in payload["findings"]},
                )

    def test_duplicate_normalized_command_and_obligation_owner_blocks(self) -> None:
        payload = self._review(["docs/*.md"], duplicate=True)
        self.assertIn(
            "duplicate_normalized_command_obligation_owner",
            {row["code"] for row in payload["findings"]},
        )


if __name__ == "__main__":
    unittest.main()
