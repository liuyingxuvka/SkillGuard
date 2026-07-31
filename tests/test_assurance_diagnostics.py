from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from skillguard_v2.assurance_diagnostics import (
    ASSURANCE_INPUT_SCHEMA,
    MUTATION_CONTRACT_SCHEMA,
    MUTATION_RECEIPT_SCHEMA,
    AssuranceDiagnosticError,
    derive_assurance_diagnostics,
    minimize_blockers,
    project_mutation_adequacy,
    BlockerAtom,
)
from skillguard_v2.contract_compiler import canonical_hash
import checker_engine


ROOT = Path(__file__).resolve().parents[1]
CONTROL_ROOT = ROOT / ".agents" / "skills" / "skillguard" / ".skillguard"


def sealed(payload: dict, hash_field: str) -> dict:
    result = dict(payload)
    result[hash_field] = canonical_hash(result)
    return result


def closure_report(rows: list[dict], status: str = "blocked") -> dict:
    payload = {
        "artifact_type": "skillguard_v2_closure_evaluation",
        "profile": "full",
        "status": status,
        "consumed_receipt_ids": [],
        "obligation_results": rows,
        "step_results": [],
        "terminal_results": [],
        "artifact_results": [],
        "execution_depth_result": {},
        "native_terminal_result": {},
        "applicability_results": [],
        "gaps": {},
        "next_actions": [],
        "residual_risk": [],
        "safe_claim": "",
        "unsafe_claim_boundary": "",
    }
    return sealed(payload, "assessment_hash")


class AssuranceDiagnosticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(
            (CONTROL_ROOT / "compiled-contract.json").read_text(encoding="utf-8")
        )
        cls.manifest = json.loads(
            (CONTROL_ROOT / "check-manifest.json").read_text(encoding="utf-8")
        )

    def input(self, closure: dict, **overrides: object) -> dict:
        payload = {
            "schema_version": ASSURANCE_INPUT_SCHEMA,
            "compiled_contract": self.contract,
            "check_manifest": self.manifest,
            "closure_report": closure,
            "receipts": [],
            "evaluation_budget": 10_000,
        }
        payload.update(overrides)
        return payload

    def test_subset_minimal_basis_has_per_atom_necessity_witnesses(self) -> None:
        atoms = (
            BlockerAtom("a", "o", "c1", ("x",), "missing", (), "p", ("n",)),
            BlockerAtom("b", "o", "c2", ("x", "y"), "failed", (), "p", ("n",)),
            BlockerAtom("c", "o", "c3", ("y",), "stale", (), "p", ("n",)),
        )
        result = minimize_blockers(atoms, ("x", "y"), 10)
        self.assertEqual(result["status"], "subset_minimal")
        self.assertFalse(result["minimum_cardinality_proven"])
        self.assertTrue(result["necessity_witnesses"])
        self.assertEqual(
            {row["atom_id"] for row in result["necessity_witnesses"]},
            {row["atom_id"] for row in result["retained_atoms"]},
        )

    def test_budget_exhaustion_never_claims_minimality(self) -> None:
        atom = BlockerAtom("a", "o", "c", ("x",), "missing", (), "p", ("n",))
        result = minimize_blockers((atom,), ("x",), 0)
        self.assertEqual(result["status"], "bounded_incomplete")
        self.assertFalse(result["computation_complete"])
        self.assertFalse(result["minimum_cardinality_proven"])
        self.assertEqual(result["necessity_witnesses"], [])

    def test_missing_receipts_are_visible_without_execution(self) -> None:
        obligation_id = str(
            self.manifest["checks"][0]["covers_obligation_ids"][0]
        )
        report = derive_assurance_diagnostics(
            self.input(
                closure_report(
                    [{"obligation_id": obligation_id, "status": "missing"}]
                )
            )
        )
        self.assertEqual(report["source_closure_status"], "blocked")
        self.assertFalse(report["closure_licensed"])
        self.assertTrue(report["all_blocker_atoms"])
        self.assertTrue(
            all(
                "provide_current_receipt:" in action
                or "inspect_" in action
                for atom in report["all_blocker_atoms"]
                for action in atom["permitted_next_actions"]
            )
        )

    def test_blocked_closure_is_preserved(self) -> None:
        obligation_id = str(
            self.manifest["checks"][0]["covers_obligation_ids"][0]
        )
        report = derive_assurance_diagnostics(
            self.input(
                closure_report(
                    [{"obligation_id": obligation_id, "status": "blocked"}]
                )
            )
        )
        self.assertTrue(report["closure_status_preserved"])
        self.assertEqual(report["source_closure_status"], "blocked")

    def test_unauthorized_obligation_removal_is_rejected(self) -> None:
        report = derive_assurance_diagnostics(
            self.input(
                closure_report([]),
                proposed_next_actions=[
                    {
                        "action_id": "drop-it",
                        "kind": "remove_obligation",
                    }
                ],
            )
        )
        action = report["proposed_next_action_results"][0]
        self.assertEqual(action["status"], "rejected")
        self.assertEqual(action["reason"], "unauthorized_obligation_weakening")

    def test_current_schema_rejects_unknown_root_fields(self) -> None:
        payload = self.input(closure_report([]))
        payload["former_alias"] = {}
        with self.assertRaises(AssuranceDiagnosticError) as raised:
            derive_assurance_diagnostics(payload)
        self.assertEqual(raised.exception.code, "assurance_input_unknown_fields")

    def test_target_mutation_result_is_projected_without_reinterpretation(self) -> None:
        contract = sealed(
            {
                "schema_version": MUTATION_CONTRACT_SCHEMA,
                "target_id": "target-a",
                "operators": ["flip-closure-status"],
                "oracle": "target-owned-test",
                "applicability": "all-current-diagnostics",
                "equivalent_mutant_disposition": "target-review-required",
                "threshold": 1,
                "check_id": "check:target-a:mutations",
            },
            "contract_hash",
        )
        receipt = sealed(
            {
                "schema_version": MUTATION_RECEIPT_SCHEMA,
                "target_id": "target-a",
                "check_id": "check:target-a:mutations",
                "contract_hash": contract["contract_hash"],
                "current": True,
                "status": "fail",
                "metrics": {"target_score": 0.91},
            },
            "receipt_hash",
        )
        result = project_mutation_adequacy(contract, receipt)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["target_result"], "fail")
        self.assertEqual(result["target_metrics"], {"target_score": 0.91})

    def test_missing_mutation_declaration_is_not_run(self) -> None:
        result = project_mutation_adequacy(None, None)
        self.assertEqual(result["status"], "not_run")

    def test_incomplete_equivalent_mutant_disposition_blocks(self) -> None:
        result = project_mutation_adequacy(
            {
                "schema_version": MUTATION_CONTRACT_SCHEMA,
                "target_id": "target-a",
                "operators": ["x"],
                "oracle": "o",
                "applicability": "a",
                "equivalent_mutant_disposition": "",
                "threshold": 1,
                "check_id": "c",
                "contract_hash": "invalid",
            },
            None,
        )
        self.assertEqual(result["status"], "blocked")
        self.assertIn(
            "equivalent_mutant_disposition", result["missing_fields"]
        )

    def test_stale_or_foreign_mutation_receipt_blocks(self) -> None:
        contract = sealed(
            {
                "schema_version": MUTATION_CONTRACT_SCHEMA,
                "target_id": "target-a",
                "operators": ["x"],
                "oracle": "o",
                "applicability": "a",
                "equivalent_mutant_disposition": "reviewed",
                "threshold": 1,
                "check_id": "c",
            },
            "contract_hash",
        )
        foreign = sealed(
            {
                "schema_version": MUTATION_RECEIPT_SCHEMA,
                "target_id": "target-b",
                "check_id": "c",
                "contract_hash": contract["contract_hash"],
                "current": True,
                "status": "pass",
            },
            "receipt_hash",
        )
        self.assertEqual(
            project_mutation_adequacy(contract, foreign)["reason"],
            "target_mutation_receipt_identity_mismatch",
        )
        stale = sealed(
            {
                "schema_version": MUTATION_RECEIPT_SCHEMA,
                "target_id": "target-a",
                "check_id": "c",
                "contract_hash": contract["contract_hash"],
                "current": False,
                "status": "pass",
            },
            "receipt_hash",
        )
        self.assertEqual(
            project_mutation_adequacy(contract, stale)["reason"],
            "target_mutation_receipt_stale",
        )

    def test_cli_exposes_read_only_report_without_claiming_closure(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            input_path = Path(temporary) / "assurance-input.json"
            input_path.write_text(
                json.dumps(self.input(closure_report([]))),
                encoding="utf-8",
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exit_code = checker_engine.assurance_diagnostics(
                    ["--input", str(input_path)]
                )
        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["decision"], "pass")
        self.assertFalse(payload["diagnostics"]["closure_licensed"])
        self.assertIn("does not", payload["claim_boundary"])


if __name__ == "__main__":
    unittest.main()
