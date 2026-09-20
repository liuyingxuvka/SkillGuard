from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests._skillguard_v2_runtime_fixture import runtime_check_manifest, runtime_contract
from skillguard_v2.author_context import (
    AuthorContextError,
    validate_author_maintenance_context,
)
from skillguard_v2.supervisor import SupervisorError, supervise_contract_run


def _author_contract() -> dict[str, object]:
    return {
        "repository_role": "skill_maintainer_source",
        "maintenance_unit_id": "unit:demo",
        "skill_id": "demo",
        "member_skill_ids": ["demo"],
    }


def _inventory(root: Path) -> tuple[tuple[str, bytes], ...]:
    return tuple(
        (path.relative_to(root).as_posix(), path.read_bytes())
        for path in sorted(root.rglob("*"))
        if path.is_file()
    )


class AuthorMaintenanceContextTests(unittest.TestCase):
    def test_explicit_author_context_is_accepted_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repository = Path(temp) / "author"
            skill = repository / "skills" / "demo"
            target = skill
            skill.mkdir(parents=True)
            before = _inventory(repository)
            context = validate_author_maintenance_context(
                contract=_author_contract(),
                skill_root=skill,
                target_root=target,
                author_repository_root=repository,
                run_state_root=repository / "work" / "run-state",
                owner_evidence_root=repository / "work" / "owner-evidence",
            )
            self.assertEqual("unit:demo", context.maintenance_unit_id)
            self.assertEqual(before, _inventory(repository))

    def test_missing_explicit_roots_is_rejected_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repository = Path(temp) / "author"
            skill = repository / "skills" / "demo"
            skill.mkdir(parents=True)
            before = _inventory(repository)
            with self.assertRaisesRegex(
                AuthorContextError,
                "author_run_state_root_required",
            ):
                validate_author_maintenance_context(
                    contract=_author_contract(),
                    skill_root=skill,
                    target_root=skill,
                    author_repository_root=repository,
                    run_state_root=None,
                    owner_evidence_root=None,
                )
            self.assertEqual(before, _inventory(repository))

    def test_consumer_repository_is_rejected_before_supervisor_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repository = Path(temp) / "ordinary-project"
            skill = repository / "skills" / "demo"
            skill.mkdir(parents=True)
            (repository / "business.txt").write_text("unchanged", encoding="utf-8")
            before = _inventory(repository)
            consumer_contract = {
                **_author_contract(),
                "repository_role": "consumer_distribution",
            }
            with self.assertRaisesRegex(
                SupervisorError,
                "author_repository_role_required",
            ):
                supervise_contract_run(
                    skill,
                    skill,
                    repository,
                    {"request": {}, "steps": {}, "execution_depth": {}},
                    compiled_contract=consumer_contract,
                    check_manifest={},
                    run_state_root=repository / "work" / "run-state",
                    owner_evidence_root=repository / "work" / "owner-evidence",
                )
            self.assertEqual(before, _inventory(repository))
            self.assertFalse((repository / ".skillguard").exists())
            self.assertFalse((repository / "work").exists())

    def test_route_predicate_rejection_precedes_input_and_run_producers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repository = root / "author"
            skill = repository / "skills" / "demo"
            target = repository / "target"
            skill.mkdir(parents=True)
            target.mkdir()
            contract = runtime_contract()
            contract["repository_role"] = "skill_maintainer_source"
            for route in contract["routes"]:
                route["when"] = {"operation": route["route_id"]}
            manifest = runtime_check_manifest(contract)
            packet = {
                "request": {"facts": {}},
                "steps": {},
                "execution_depth": {},
            }

            with patch(
                "skillguard_v2.supervisor._load_or_compile_runtime_pair",
                return_value=(contract, manifest),
            ), patch("skillguard_v2.supervisor.claim_run") as claim_run, patch(
                "skillguard_v2.supervisor.fingerprint_target_inputs"
            ) as fingerprint_target_inputs:
                with self.assertRaisesRegex(SupervisorError, "route_selection_blocked"):
                    supervise_contract_run(
                        skill,
                        target,
                        repository,
                        packet,
                        compiled_contract=contract,
                        check_manifest=manifest,
                        run_state_root=repository / "work" / "run-state",
                        owner_evidence_root=repository / "work" / "owner-evidence",
                    )

            claim_run.assert_not_called()
            fingerprint_target_inputs.assert_not_called()


if __name__ == "__main__":
    unittest.main()
