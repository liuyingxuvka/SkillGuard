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

from skillguard_v2.project_adoption import (  # noqa: E402
    BEGIN_MARKER,
    END_MARKER,
    SKILLGUARD_REPOSITORY,
    ProjectAdoptionError,
    adopt_project,
    audit_project_adoption,
)
from skillguard_v2.validation_execution_policy import (  # noqa: E402
    VALIDATION_EXECUTION_POLICY_ID,
    VALIDATION_EXECUTION_POLICY_LINES,
)
from tests._runtime_authority_consumer_fixture import make_current_skill  # noqa: E402


class SkillGuardProjectAdoptionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        make_current_skill(self.root / "skills" / "demo", "demo")
        (self.root / "AGENTS.md").write_text("# Existing project rules\n\nKeep this text.\n", encoding="utf-8")
        self.rows = [
            {
                "skill_path": "skills/demo",
                "integration_mode": "native-integrated",
                "native_owner_id": "demo-native-route",
            }
        ]

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_adopt_preserves_existing_prompt_and_installs_portable_rules(self) -> None:
        result = adopt_project(self.root, self.rows, skillguard_version="0.3.0")
        self.assertTrue(result["ok"], result)
        text = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Existing project rules"))
        self.assertIn("Keep this text.", text)
        self.assertEqual(1, text.count(BEGIN_MARKER))
        self.assertEqual(1, text.count(END_MARKER))
        self.assertIn(SKILLGUARD_REPOSITORY, text)
        self.assertIn("current declared-check execution receipt", text)
        self.assertIn(VALIDATION_EXECUTION_POLICY_ID, text)
        for line in VALIDATION_EXECUTION_POLICY_LINES:
            self.assertIn(line, text)
        audit = audit_project_adoption(self.root)
        self.assertTrue(audit["ok"], audit)

    def test_tampered_or_duplicated_prompt_fails_closed(self) -> None:
        adopt_project(self.root, self.rows, skillguard_version="0.3.0")
        path = self.root / "AGENTS.md"
        path.write_text(path.read_text(encoding="utf-8") + BEGIN_MARKER + "\n", encoding="utf-8")
        audit = audit_project_adoption(self.root)
        self.assertFalse(audit["ok"])
        self.assertIn("managed_begin_marker_count:2", audit["findings"])

    def test_manifest_repository_link_is_integrity_checked(self) -> None:
        adopt_project(self.root, self.rows, skillguard_version="0.3.0")
        path = self.root / ".skillguard" / "project.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["skillguard_repository"] = "https://example.invalid/not-skillguard"
        path.write_text(json.dumps(payload), encoding="utf-8")
        audit = audit_project_adoption(self.root)
        self.assertFalse(audit["ok"])
        self.assertIn("skillguard_repository_mismatch", audit["findings"])
        self.assertIn("project_manifest_hash_mismatch", audit["findings"])

    def test_project_adopt_directly_replaces_noncurrent_shape_from_explicit_inputs(self) -> None:
        adopt_project(self.root, self.rows, skillguard_version="0.3.0")
        manifest_path = self.root / ".skillguard" / "project.json"
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload["former_field"] = {"must_not_be_read": True}
        manifest_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

        result = adopt_project(self.root, self.rows, skillguard_version="0.3.1")

        self.assertTrue(result["ok"], result)
        current = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertNotIn("former_field", current)
        self.assertEqual("0.3.1", current["skillguard_version"])

    def test_project_adopt_refreshes_current_manifest_version_from_explicit_input(self) -> None:
        first = adopt_project(self.root, self.rows, skillguard_version="0.3.2")
        self.assertTrue(first["ok"], first)

        refreshed = adopt_project(self.root, self.rows, skillguard_version="0.3.3")

        self.assertTrue(refreshed["ok"], refreshed)
        self.assertTrue(refreshed["changed"])
        current = json.loads(
            (self.root / ".skillguard" / "project.json").read_text(encoding="utf-8")
        )
        self.assertEqual("0.3.3", current["skillguard_version"])

    def test_non_current_integration_markers_are_rejected(self) -> None:
        for marker in ("skillguard-runtime", "hybrid-extension"):
            with self.subTest(marker=marker):
                rows = [
                    {
                        "skill_path": "skills/demo",
                        "integration_mode": marker,
                        "native_owner_id": "demo-domain-owner",
                    }
                ]
                with self.assertRaises(ProjectAdoptionError) as raised:
                    adopt_project(self.root, rows, skillguard_version="0.3.0")
                self.assertEqual(
                    "managed_skill_integration_mode_invalid", raised.exception.code
                )

    def test_repository_root_skill_has_portable_identity_and_evidence_path(self) -> None:
        make_current_skill(self.root, self.root.name)
        rows = [
            {
                "skill_path": ".",
                "integration_mode": "native-integrated",
                "native_owner_id": "root-native-route",
            }
        ]
        result = adopt_project(self.root, rows, skillguard_version="0.3.0")
        self.assertTrue(result["ok"], result)
        manifest = json.loads((self.root / ".skillguard" / "project.json").read_text(encoding="utf-8"))
        root_row = manifest["managed_skills"][0]
        self.assertEqual(self.root.name, root_row["skill_id"])
        self.assertEqual("SKILL.md", root_row["native_route_evidence_path"])
        self.assertTrue(audit_project_adoption(self.root)["ok"])

    def test_repository_generic_vertical_slice_is_current(self) -> None:
        fixture_root = (
            ROOT
            / ".agents"
            / "skills"
            / "skillguard"
            / "fixtures"
            / "generic_project"
        )
        audit = audit_project_adoption(fixture_root)
        self.assertTrue(audit["ok"], audit)
        prompt = (fixture_root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("Keep fixture outputs local", prompt)
        self.assertIn(SKILLGUARD_REPOSITORY, prompt)
        self.assertIn(VALIDATION_EXECUTION_POLICY_ID, prompt)
        for line in VALIDATION_EXECUTION_POLICY_LINES:
            self.assertIn(line, prompt)


if __name__ == "__main__":
    unittest.main()
