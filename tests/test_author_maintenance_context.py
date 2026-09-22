from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

from tests._skillguard_v2_runtime_fixture import runtime_check_manifest, runtime_contract
from tests.test_compact_contract_cli import _request, _write_contract
from tests.test_fixed_preflight_units import _root as make_target_root
from skillguard_v2.compact_state import control_root
import checker_engine
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
            root = make_target_root(Path(temp))
            _write_contract(root)
            state = Path(temp) / "state"
            state.mkdir()
            request_path = _request(root, state, "change")
            request = json.loads(request_path.read_text(encoding="utf-8"))
            request["facts"] = {"operation": "unsupported"}
            request_path.write_text(json.dumps(request), encoding="utf-8")

            with patch("checker_engine.observe_inputs") as observe_inputs, patch(
                "checker_engine.execute_plan"
            ) as execute_plan:
                with self.assertRaises(checker_engine.SkillGuardCliError) as raised:
                    checker_engine.change(
                        ["--root", str(root), "--request", str(request_path), "--json"]
                    )

            self.assertEqual("operation_fact_mismatch", raised.exception.category)
            self.assertFalse((control_root(state, "fixture-unit", "fixture") / "binding.json").exists())
            observe_inputs.assert_not_called()
            execute_plan.assert_not_called()


if __name__ == "__main__":
    unittest.main()
