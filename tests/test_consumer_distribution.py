from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from skillguard_v2.consumer_distribution import (
    audit_consumer_distribution,
    build_consumer_distribution,
    consumer_distribution_plan,
)


def _contract(skill_id: str = "demo") -> dict[str, object]:
    return {
        "skill_id": skill_id,
        "maintenance_unit_id": f"unit:{skill_id}",
        "contract_hash": "sha256:" + "1" * 64,
        "consumer_projection": {
            "projection_id": "projection:consumer-distribution",
            "prohibited_path_prefixes": [".skillguard/"],
            "prohibited_prompt_tokens": [
                "SkillGuard",
                ".skillguard",
                "skillguard.py",
            ],
            "release_manifest_path": "consumer-release.json",
        },
    }


class ConsumerDistributionTests(unittest.TestCase):
    def test_builder_emits_independent_target_owned_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            destination = root / "consumer"
            (source / "scripts").mkdir(parents=True)
            (source / ".skillguard").mkdir()
            (source / "SKILL.md").write_text(
                "---\nname: demo\ndescription: Standalone demo.\n---\n\n# Demo\n",
                encoding="utf-8",
            )
            (source / "scripts" / "run.py").write_text(
                "print('ready')\n",
                encoding="utf-8",
            )
            (source / ".skillguard" / "contract-source.json").write_text(
                "{}",
                encoding="utf-8",
            )

            result = build_consumer_distribution(
                source,
                destination,
                _contract(),
            )

            self.assertEqual("passed", result["status"])
            self.assertFalse((destination / ".skillguard").exists())
            self.assertTrue((destination / "SKILL.md").is_file())
            self.assertTrue((destination / "scripts" / "run.py").is_file())
            manifest = json.loads(
                (destination / "consumer-release.json").read_text(encoding="utf-8")
            )
            self.assertNotIn("maintenance_unit_id", manifest)
            self.assertNotIn("source_contract_hash", manifest)
            self.assertNotIn("SkillGuard", json.dumps(manifest))
            self.assertEqual(
                "passed",
                audit_consumer_distribution(destination)["status"],
            )

    def test_target_runtime_stranded_under_author_control_blocks_before_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            destination = root / "consumer"
            (source / ".skillguard" / "runtime").mkdir(parents=True)
            (source / "SKILL.md").write_text("# Demo\n", encoding="utf-8")
            (source / ".skillguard" / "runtime" / "engine.py").write_text(
                "print('domain runtime')\n",
                encoding="utf-8",
            )

            result = build_consumer_distribution(
                source,
                destination,
                _contract(),
            )

            self.assertEqual("blocked", result["status"])
            self.assertFalse(destination.exists())
            self.assertIn(
                "target_runtime_stranded_in_author_control",
                {row["code"] for row in result["findings"]},
            )

    def test_consumer_prompt_dependency_blocks_distribution(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source"
            source.mkdir()
            (source / "SKILL.md").write_text(
                "Run skillguard.py before ordinary work.\n",
                encoding="utf-8",
            )

            plan = consumer_distribution_plan(source, _contract())

            self.assertEqual("blocked", plan["status"])
            self.assertIn(
                "consumer_skillguard_command_reference",
                {row["code"] for row in plan["findings"]},
            )


if __name__ == "__main__":
    unittest.main()
