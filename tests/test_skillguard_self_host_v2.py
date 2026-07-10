from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / ".agents" / "skills" / "skillguard" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from skillguard_v2.contract_compiler import compile_skill_contract  # noqa: E402
from skillguard_v2.self_host import run_frozen_old_verifier  # noqa: E402


class SkillGuardSelfHostV2Tests(unittest.TestCase):
    def test_generated_contracts_keep_canonical_lf_in_git_checkouts(self) -> None:
        attributes = set((ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines())
        self.assertIn(
            "/.agents/skills/skillguard/.skillguard/compiled-contract.json text eol=lf",
            attributes,
        )
        self.assertIn(
            "/.agents/skills/skillguard/.skillguard/check-manifest.json text eol=lf",
            attributes,
        )

    def test_self_contract_is_current_exact_and_not_broad_all(self) -> None:
        skill_root = ROOT / ".agents" / "skills" / "skillguard"
        result = compile_skill_contract(skill_root, repository_root=ROOT, write=False)
        self.assertTrue(result.ok, result.to_dict())
        contract = result.compiled_contract
        manifest = result.check_manifest
        self.assertEqual(27, sum(1 for row in contract["steps"] if not row["terminal_kind"]))
        self.assertEqual(2, len(contract["artifacts"]))
        all_obligations = {row["obligation_id"] for row in contract["obligations"]}
        for check in manifest["checks"]:
            coverage = set(check["covers_obligation_ids"])
            self.assertNotEqual(all_obligations, coverage, check["check_id"])
            self.assertTrue(coverage)

    def test_frozen_stage_records_checker_fingerprint_and_native_boundaries(self) -> None:
        report = run_frozen_old_verifier(ROOT, run_old_full=False)
        self.assertEqual("passed", report["status"])
        self.assertEqual("skillguard.local_cli_dispatch.v1", report["checker_version"])
        self.assertEqual(
            {"frozen-old:check-skill", "frozen-old:check-depth", "frozen-old:self-check"},
            {row["check_id"] for row in report["checks"]},
        )
        self.assertTrue(report["checker_fingerprint"])

    def test_failure_matrix_manifest_is_public_and_bounded(self) -> None:
        path = ROOT / ".agents" / "skills" / "skillguard" / "fixtures" / "v2_self_host_failure_matrix" / "fixture-manifest.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(9, len(payload["cases"]))
        self.assertIn("do not prove", payload["claim_boundary"])


if __name__ == "__main__":
    unittest.main()
