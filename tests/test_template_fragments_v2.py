from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / ".agents" / "skills" / "skillguard"
SCRIPT_ROOT = SKILL_ROOT / "scripts"
CATALOG_PATH = SKILL_ROOT / "assets" / "contract_fragments" / "catalog.json"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from skillguard_v2.template_fragments import (  # noqa: E402
    compile_supervision_fragment_refs,
    load_fragment_catalog,
    seal_fragment,
    seal_fragment_catalog,
    validate_fragment,
)


def selection_reference() -> dict[str, object]:
    return {
        "fragment_id": "template-selection-supervision",
        "revision": "1",
        "fragment_digest": "sha256:a488f76a50d9b64034be1e3bd9dde24c827addc0035b8b4d80628436db40e23f",
        "slot_bindings": {
            "native-route-step": ["step:route"],
            "applicability-step": ["step:applicability"],
            "selection-check": ["check:selection"],
            "selection-receipt-artifact": ["artifact:selection"],
        },
    }


def model_and_binding():
    return (
        {
            "steps": [
                {"step_id": "step:route"},
                {"step_id": "step:applicability"},
            ]
        },
        {
            "checks": [{"check_id": "check:selection"}],
            "artifacts": [{"artifact_id": "artifact:selection"}],
        },
    )


class TemplateFragmentTests(unittest.TestCase):
    def test_reviewed_catalog_and_prompt_component_hashes_are_current(self) -> None:
        catalog, findings = load_fragment_catalog(CATALOG_PATH)
        self.assertEqual((), findings)
        prompt_files = {
            "template-selection-supervision": "template_selection_supervision.md.template",
            "template-instance-supervision": "template_instance_supervision.md.template",
            "template-installation-supervision": "template_installation_supervision.md.template",
        }
        for fragment in catalog["fragments"]:
            data = (
                SKILL_ROOT / "assets" / "templates" / prompt_files[fragment["fragment_id"]]
            ).read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            expected = "sha256:" + hashlib.sha256(data).hexdigest()
            self.assertEqual(
                expected,
                fragment["content_components"][0]["content_hash"],
            )

    def test_fragment_cannot_add_domain_checks(self) -> None:
        catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        forged = copy.deepcopy(catalog["fragments"][0])
        forged["add_checks"] = ["check:invented"]
        forged = seal_fragment(forged)

        _, findings = validate_fragment(forged)

        self.assertIn("unknown_field", {row.code for row in findings})

    def test_unrelated_fragment_change_does_not_stale_selection_consumer(self) -> None:
        catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        model, binding = model_and_binding()
        baseline = compile_supervision_fragment_refs(
            references=[selection_reference()],
            model=model,
            binding=binding,
            catalog_path=CATALOG_PATH,
        )
        self.assertTrue(baseline.ok, baseline.findings)

        with tempfile.TemporaryDirectory() as temporary:
            changed = copy.deepcopy(catalog)
            installation = next(
                item
                for item in changed["fragments"]
                if item["fragment_id"] == "template-installation-supervision"
            )
            installation["description"] += " Reviewed wording changed."
            installation.update(seal_fragment(installation))
            changed.update(seal_fragment_catalog(changed))
            changed_path = Path(temporary) / "catalog.json"
            changed_path.write_text(
                json.dumps(changed, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            observed = compile_supervision_fragment_refs(
                references=[selection_reference()],
                model=model,
                binding=binding,
                catalog_path=changed_path,
            )

        self.assertTrue(observed.ok, observed.findings)
        self.assertEqual(baseline.projections, observed.projections)
        self.assertEqual(baseline.content_components, observed.content_components)

    def test_changed_consumed_fragment_requires_current_reference_digest(self) -> None:
        catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        selection = next(
            item
            for item in catalog["fragments"]
            if item["fragment_id"] == "template-selection-supervision"
        )
        selection["description"] += " Materially changed."
        selection.update(seal_fragment(selection))
        catalog.update(seal_fragment_catalog(catalog))
        model, binding = model_and_binding()

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "catalog.json"
            path.write_text(
                json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            result = compile_supervision_fragment_refs(
                references=[selection_reference()],
                model=model,
                binding=binding,
                catalog_path=path,
            )

        self.assertFalse(result.ok)
        self.assertIn("fragment_reference_stale", {row.code for row in result.findings})


if __name__ == "__main__":
    unittest.main()
