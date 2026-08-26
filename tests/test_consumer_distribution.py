from __future__ import annotations

import json
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / ".agents" / "skills" / "skillguard" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

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

            identity = {
                "schema_version": manifest["schema_version"],
                "skill_id": manifest["skill_id"],
                "projection_id": manifest["projection_id"],
                "files": manifest["files"],
                "author_control_excluded": manifest["author_control_excluded"],
            }
            canonical = lambda value: json.dumps(  # noqa: E731
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            expected_release_id = "sha256:" + hashlib.sha256(canonical(identity)).hexdigest()
            unsigned = dict(manifest)
            unsigned.pop("manifest_hash")
            expected_manifest_hash = "sha256:" + hashlib.sha256(canonical(unsigned)).hexdigest()
            self.assertEqual(expected_release_id, manifest["release_id"])
            self.assertEqual(expected_manifest_hash, manifest["manifest_hash"])
            self.assertEqual(canonical(manifest) + b"\n", (destination / "consumer-release.json").read_bytes())
            self.assertRegex(manifest["release_id"], r"^sha256:[0-9a-f]{64}$")
            self.assertRegex(manifest["manifest_hash"], r"^sha256:[0-9a-f]{64}$")

    def test_uppercase_or_pretty_release_identity_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            destination = root / "consumer"
            source.mkdir()
            (source / "SKILL.md").write_text("# Demo\n", encoding="utf-8")
            self.assertEqual("passed", build_consumer_distribution(source, destination, _contract())["status"])
            manifest_path = destination / "consumer-release.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["release_id"] = manifest["release_id"].upper().removeprefix("SHA256:")
            manifest["manifest_hash"] = "A" * 64
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            audited = audit_consumer_distribution(destination)
            codes = {row["code"] for row in audited["findings"]}
            self.assertEqual("blocked", audited["status"])
            self.assertIn("consumer_release_manifest_noncanonical", codes)
            self.assertIn("consumer_release_manifest_hash_format_invalid", codes)
            self.assertIn("consumer_release_release_id_format_invalid", codes)

    def test_author_identity_underscore_leak_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            (source / "SKILL.md").write_text("# Demo\n", encoding="utf-8")
            (source / "runtime.py").write_text(
                "maintenance_unit_id = 'author-only'\n",
                encoding="utf-8",
            )
            plan = consumer_distribution_plan(source, _contract())
            self.assertEqual("blocked", plan["status"])
            self.assertIn(
                "consumer_author_identity_field_reference",
                {row["code"] for row in plan["findings"]},
            )

    def test_manifest_author_field_cannot_be_rehashed_into_consumer_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            destination = root / "consumer"
            source.mkdir()
            (source / "SKILL.md").write_text("# Demo\n", encoding="utf-8")
            self.assertEqual("passed", build_consumer_distribution(source, destination, _contract())["status"])
            manifest_path = destination / "consumer-release.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["maintenance_unit_id"] = "author-only"
            canonical = lambda value: json.dumps(  # noqa: E731
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            unsigned = dict(manifest)
            unsigned.pop("manifest_hash")
            manifest["manifest_hash"] = "sha256:" + hashlib.sha256(canonical(unsigned)).hexdigest()
            manifest_path.write_bytes(canonical(manifest) + b"\n")
            audited = audit_consumer_distribution(destination)
            self.assertEqual("blocked", audited["status"])
            self.assertIn(
                "consumer_release_manifest_fields_invalid",
                {row["code"] for row in audited["findings"]},
            )

    def test_manifest_file_inventory_cannot_be_rehashed_with_duplicate_or_unsafe_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            destination = root / "consumer"
            source.mkdir()
            (source / "SKILL.md").write_text("# Demo\n", encoding="utf-8")
            self.assertEqual(
                "passed", build_consumer_distribution(source, destination, _contract())["status"]
            )
            manifest_path = destination / "consumer-release.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"] = [
                {"path": "../escape.txt", "content_hash": manifest["files"][0]["content_hash"]},
                dict(manifest["files"][0]),
                dict(manifest["files"][0]),
            ]
            canonical = lambda value: json.dumps(  # noqa: E731
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            identity = {
                key: manifest[key]
                for key in (
                    "schema_version",
                    "skill_id",
                    "projection_id",
                    "files",
                    "author_control_excluded",
                )
            }
            manifest["release_id"] = "sha256:" + hashlib.sha256(canonical(identity)).hexdigest()
            unsigned = dict(manifest)
            unsigned.pop("manifest_hash")
            manifest["manifest_hash"] = "sha256:" + hashlib.sha256(canonical(unsigned)).hexdigest()
            manifest_path.write_bytes(canonical(manifest) + b"\n")

            audited = audit_consumer_distribution(destination)
            codes = {row["code"] for row in audited["findings"]}
            self.assertEqual("blocked", audited["status"])
            self.assertIn("consumer_release_manifest_file_duplicate", codes)
            self.assertIn("consumer_release_manifest_file_path_invalid", codes)

    def test_author_contract_hash_and_incomplete_sentinel_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source"
            source.mkdir()
            (source / "SKILL.md").write_text("# Demo\n", encoding="utf-8")
            (source / "runtime.py").write_text(
                "contract_hash = 'sha256:' + '0' * 64\n",
                encoding="utf-8",
            )
            (source / "skillguard_depth.py").write_text(
                "# negative fixture\n"
                "skillguard_version = 'retired'\n",
                encoding="utf-8",
            )

            plan = consumer_distribution_plan(source, _contract())

            self.assertEqual("blocked", plan["status"])
            codes = {row["code"] for row in plan["findings"]}
            self.assertIn("consumer_author_identity_field_reference", codes)
            self.assertIn("consumer_author_control_name_present", codes)
            self.assertIn("consumer_skillguard_command_reference", codes)

    def test_skillguard_underscore_key_and_value_leak_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source"
            source.mkdir()
            (source / "SKILL.md").write_text("# Demo\n", encoding="utf-8")
            (source / "runtime.json").write_text(
                json.dumps(
                    {
                        "skillguard_version": "0.7.2",
                        "runtime": {"provider": "skillguard-author"},
                    }
                ),
                encoding="utf-8",
            )

            plan = consumer_distribution_plan(source, _contract())

            self.assertEqual("blocked", plan["status"])
            self.assertIn(
                "consumer_skillguard_command_reference",
                {row["code"] for row in plan["findings"]},
            )
            self.assertIn(
                "consumer_author_identity_field_reference",
                {row["code"] for row in plan["findings"]},
            )

    def test_retired_skillguard_depth_sentinel_is_not_runtime_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source"
            source.mkdir()
            (source / "SKILL.md").write_text("# Demo\n", encoding="utf-8")
            (source / "skillguard_depth.py").write_text(
                "# retired negative sentinel; not runtime\n"
                "skillguard_version = 'retired'\n",
                encoding="utf-8",
            )

            plan = consumer_distribution_plan(source, _contract())

            self.assertEqual("passed", plan["status"])

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
