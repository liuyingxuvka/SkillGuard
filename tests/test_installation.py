from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / ".agents" / "skills" / "skillguard"
SCRIPT_ROOT = SKILL_ROOT / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from skillguard_v2.installation import activate_stage, prepare_stage, verify_stage  # noqa: E402


class InstallationTests(unittest.TestCase):
    def test_complete_stage_passes_parity_and_installed_layout_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary) / "stage" / ".codex" / "skills" / "skillguard"
            prepared = prepare_stage(SKILL_ROOT, stage)
            self.assertEqual("passed", prepared["status"], prepared)
            verified = verify_stage(SKILL_ROOT, stage)
            self.assertEqual("passed", verified["status"], verified)
            self.assertEqual("passed", verified["smoke"]["status"], verified["smoke"])

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

    def test_stage_path_must_use_an_isolated_codex_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                prepare_stage(SKILL_ROOT, Path(temporary) / "skillguard")


if __name__ == "__main__":
    unittest.main()
