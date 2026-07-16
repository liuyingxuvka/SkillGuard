from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _skillguard_v2_runtime_fixture import SCRIPT_ROOT, runtime_contract  # noqa: F401
from skillguard_v2.supervisor import (
    SupervisorError,
    _current_fingerprints,
    validate_supervisor_packet,
)
from skillguard_v2.receipts import fingerprint_value
from skillguard_v2.target_inputs import (
    TargetInputError,
    fingerprint_target_input_roles,
    fingerprint_target_inputs,
)


class TargetInputV2Tests(unittest.TestCase):
    def test_fingerprint_comes_from_actual_bytes_and_changes_at_same_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "series.json"
            source.write_text('{"points": [1]}\n', encoding="utf-8")
            first = fingerprint_target_inputs(root, ["series.json"])
            source.write_text('{"points": [1, 2]}\n', encoding="utf-8")
            second = fingerprint_target_inputs(root, ["series.json"])
            self.assertNotEqual(first["fingerprint"], second["fingerprint"])

    def test_outside_missing_directory_and_duplicate_inputs_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.joinpath("folder").mkdir()
            root.joinpath("input.txt").write_text("x", encoding="utf-8")
            cases = (
                (["../outside.txt"], "target_input_path_outside_target"),
                (["missing.txt"], "target_input_path_missing"),
                (["folder"], "target_input_path_not_file"),
                (["input.txt", "input.txt"], "target_input_path_duplicate"),
            )
            for paths, code in cases:
                with self.subTest(paths=paths):
                    with self.assertRaises(TargetInputError) as raised:
                        fingerprint_target_inputs(root, paths)
                    self.assertEqual(code, raised.exception.code)

    def test_caller_cannot_supply_a_target_input_hash(self) -> None:
        with self.assertRaises(SupervisorError) as raised:
            validate_supervisor_packet(
                {
                    "request": {
                        "function_ids": ["analyze"],
                        "claim_scope": "enforced",
                        "target_input_fingerprint": "A" * 64,
                    },
                    "steps": {},
                }
            )
        self.assertEqual("unconsumed_packet_field", raised.exception.code)

    def test_current_fingerprints_detect_post_check_input_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input.txt"
            source.write_text("before", encoding="utf-8")
            request = {"request": "fixture", "target_input_paths": ["input.txt"]}
            before = _current_fingerprints(runtime_contract(), request, root)
            source.write_text("after", encoding="utf-8")
            after = _current_fingerprints(runtime_contract(), request, root)
            self.assertNotEqual(before["target_inputs"], after["target_inputs"])

    def test_role_fingerprints_are_verifier_derived_and_role_specific(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.joinpath("purpose.md").write_text("prevent unsafe output", encoding="utf-8")
            root.joinpath("universe.json").write_text('{"objects": ["a"]}', encoding="utf-8")
            roles = {
                "purpose_contract": ["purpose.md"],
                "external_universe": ["universe.json"],
            }
            inventories = fingerprint_target_input_roles(root, roles)
            current = _current_fingerprints(
                runtime_contract(),
                {"request": "fixture", "target_input_roles": roles},
                root,
            )
            self.assertEqual(
                fingerprint_value(inventories["purpose_contract"]),
                current["target_role:purpose_contract"],
            )
            self.assertEqual(
                fingerprint_value(inventories["external_universe"]),
                current["target_role:external_universe"],
            )
            root.joinpath("universe.json").write_text(
                '{"objects": ["a", "b"]}', encoding="utf-8"
            )
            changed = _current_fingerprints(
                runtime_contract(),
                {"request": "fixture", "target_input_roles": roles},
                root,
            )
            self.assertEqual(
                current["target_role:purpose_contract"],
                changed["target_role:purpose_contract"],
            )
            self.assertNotEqual(
                current["target_role:external_universe"],
                changed["target_role:external_universe"],
            )

    def test_role_map_rejects_empty_invalid_and_old_caller_fingerprint_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.joinpath("input.txt").write_text("x", encoding="utf-8")
            cases = (
                ({}, "target_input_roles_invalid"),
                ({"bad role": ["input.txt"]}, "target_input_role_invalid"),
                ({"purpose_contract": []}, "target_input_paths_empty"),
            )
            for roles, code in cases:
                with self.subTest(roles=roles):
                    with self.assertRaises(TargetInputError) as raised:
                        fingerprint_target_input_roles(root, roles)
                    self.assertEqual(code, raised.exception.code)
        for field in ("input_role_fingerprints", "purpose_contract_identity"):
            with self.subTest(field=field):
                with self.assertRaises(SupervisorError) as raised:
                    validate_supervisor_packet(
                        {
                            "request": {
                                "function_ids": ["analyze"],
                                "claim_scope": "enforced",
                                field: {"purpose_contract": "A" * 64},
                            },
                            "steps": {},
                        }
                    )
                self.assertEqual("unconsumed_packet_field", raised.exception.code)


if __name__ == "__main__":
    unittest.main()
