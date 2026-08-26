from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPO_ROOT / ".agents" / "skills" / "skillguard"
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from skillguard_v2.template_prompts import (  # noqa: E402
    TARGET_TEMPLATE_PROMPT_BEGIN,
    TARGET_TEMPLATE_REFERENCE_PATH,
    materialize_target_template_guidance,
    render_target_template_routing_section,
    replace_target_template_routing_section,
)
from tests.test_template_adapters_v2 import manifest, projection  # noqa: E402
from skillguard_v2.template_packs import (  # noqa: E402
    TemplatePackError,
    seal_template_catalog,
)


class TargetTemplatePromptTests(unittest.TestCase):
    def test_section_is_catalog_derived_and_never_selects_domain_semantics(self) -> None:
        section = render_target_template_routing_section(projection())
        self.assertIn("catalog:test-guard", section)
        self.assertIn("test-base", section)
        self.assertIn("test-domain", section)
        self.assertIn("native router first", section)
        self.assertIn("must block as ambiguous", section)
        self.assertNotIn("choose test-domain", section.lower())

    def test_insert_and_replace_preserve_unrelated_skill_instructions(self) -> None:
        original = "# Target Skill\n\nKeep this unrelated instruction.\n"
        first, first_status = replace_target_template_routing_section(
            original,
            render_target_template_routing_section(projection()),
        )
        self.assertEqual("inserted", first_status)
        self.assertIn("Keep this unrelated instruction.", first)
        changed = projection()
        changed["claim_boundary"] = "A changed request-level boundary."
        second, second_status = replace_target_template_routing_section(
            first,
            render_target_template_routing_section(changed),
        )
        self.assertEqual("replaced", second_status)
        self.assertEqual(1, second.count(TARGET_TEMPLATE_PROMPT_BEGIN))
        self.assertIn("Keep this unrelated instruction.", second)

    def test_stale_projection_blocks_before_prompt_generation(self) -> None:
        stale = copy.deepcopy(projection())
        stale["catalog"]["templates"][0]["claim_boundary"] = "changed after sealing"
        with self.assertRaises(TemplatePackError):
            render_target_template_routing_section(stale)

    def test_multiple_same_owner_catalogs_are_rendered_without_selection(self) -> None:
        first = projection()
        secondary_manifest = manifest("test-secondary-base", base=True)
        second = {
            **copy.deepcopy(first),
            "catalog": seal_template_catalog(
                {
                    **copy.deepcopy(first["catalog"]),
                    "catalog_id": "catalog:test-guard-secondary",
                    "base_template_id": "test-secondary-base",
                    "templates": [secondary_manifest],
                }
            ),
            "applicability_results": [
                {
                    **copy.deepcopy(first["applicability_results"][0]),
                    "template_id": "test-secondary-base",
                }
            ],
        }
        section = render_target_template_routing_section([first, second])
        self.assertIn("catalog:test-guard-secondary", section)
        self.assertIn("test-secondary-base", section)
        self.assertEqual(1, section.count(TARGET_TEMPLATE_PROMPT_BEGIN))

    def test_multiple_catalogs_cannot_mix_native_owners(self) -> None:
        second = projection()
        second["target_id"] = "target:another-guard"
        with self.assertRaisesRegex(ValueError, "different targets or native owners"):
            render_target_template_routing_section([projection(), second])

    def test_compact_section_is_only_a_conditional_reference_pointer(self) -> None:
        section = render_target_template_routing_section(projection(), compact=True)
        self.assertIn("## Conditional Validated Template Packs", section)
        self.assertIn(TARGET_TEMPLATE_REFERENCE_PATH, section)
        self.assertIn("Do not load", section)
        self.assertNotIn("## Validated Template Pack Routing", section)

    def test_applicable_target_materializes_pointer_and_complete_reference(self) -> None:
        with tempfile.TemporaryDirectory(prefix="target-template-guidance-") as directory:
            target = Path(directory)
            (target / "SKILL.md").write_text("# Target\n", encoding="utf-8")

            result = materialize_target_template_guidance(
                target, projection(), write=True
            )

            self.assertTrue(result["ok"], result)
            entry = (target / "SKILL.md").read_text(encoding="utf-8")
            reference = (target / TARGET_TEMPLATE_REFERENCE_PATH).read_text(
                encoding="utf-8"
            )
            self.assertIn("## Conditional Validated Template Packs", entry)
            self.assertNotIn("Template inventory:", entry)
            self.assertIn("## Validated Template Pack Routing", reference)
            self.assertIn("### Instance and Validation", reference)
            self.assertIn("### Installation", reference)
            replay = materialize_target_template_guidance(target, projection())
            self.assertTrue(replay["ok"], replay)

    def test_target_without_declared_template_support_gets_no_guidance(self) -> None:
        with tempfile.TemporaryDirectory(prefix="target-without-template-") as directory:
            target = Path(directory)
            (target / "SKILL.md").write_text("# Target\n", encoding="utf-8")

            self.assertFalse((target / TARGET_TEMPLATE_REFERENCE_PATH).exists())
            self.assertNotIn("Validated Template", (target / "SKILL.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
