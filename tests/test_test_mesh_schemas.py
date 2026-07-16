from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from test_test_mesh_current import CurrentTestMeshTests


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ROOT = (
    ROOT / ".agents" / "skills" / "skillguard" / "assets" / "schemas"
)
CURRENT_SCHEMAS = {
    "head": "skillguard_check_execution_head_current.schema.json",
    "receipt": "skillguard_check_execution_receipt_current.schema.json",
    "result_sidecar": "skillguard_check_execution_result_sidecar_current.schema.json",
    "termination_sidecar": "skillguard_check_execution_termination_sidecar_current.schema.json",
    "plan": "skillguard_test_mesh_execution_plan_current.schema.json",
    "owner_execution": "skillguard_test_mesh_owner_execution_current.schema.json",
    "aggregation": "skillguard_test_mesh_aggregation_current.schema.json",
}


class CurrentTestMeshSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = CurrentTestMeshTests(
            "test_aggregation_only_references_child_and_read_only_replay"
        )
        self.fixture.setUp()

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def _schemas(self) -> dict[str, dict[str, object]]:
        return {
            key: json.loads((SCHEMA_ROOT / name).read_text(encoding="utf-8"))
            for key, name in CURRENT_SCHEMAS.items()
        }

    def test_current_records_match_strict_declared_surfaces(self) -> None:
        schemas = self._schemas()
        plan = self.fixture._plan()
        owner_execution = self.fixture._run_frozen_owners(plan)
        execution = self.fixture._execute_owner()
        receipt = execution["execution_receipt"]
        aggregation = self.fixture._plan(
            mode="aggregation_only", frozen_plan=plan
        )
        evidence_root = self.fixture.owner_root
        head = json.loads(
            (
                evidence_root
                / "check-executions"
                / "heads"
                / f"{receipt['execution_key'].split(':', 1)[1]}.json"
            ).read_text(encoding="utf-8")
        )
        result_sidecar = json.loads(
            (
                evidence_root
                / receipt["sidecars"]["result"]["relative_path"]
            ).read_text(encoding="utf-8")
        )
        termination_sidecar = json.loads(
            (
                evidence_root
                / receipt["sidecars"]["termination"]["relative_path"]
            ).read_text(encoding="utf-8")
        )
        records = {
            "head": head,
            "receipt": receipt,
            "result_sidecar": result_sidecar,
            "termination_sidecar": termination_sidecar,
            "plan": plan,
            "owner_execution": owner_execution,
            "aggregation": aggregation,
        }
        for name, record in records.items():
            with self.subTest(name=name):
                schema = schemas[name]
                self.assertIs(schema["additionalProperties"], False)
                self.assertEqual(
                    set(record), set(schema["properties"])
                )
                self.assertLessEqual(
                    set(schema["required"]), set(record)
                )

    def test_current_schema_ids_and_hashes_have_one_wire_shape(self) -> None:
        for name, schema in self._schemas().items():
            with self.subTest(name=name):
                serialized = json.dumps(schema, sort_keys=True)
                self.assertNotIn(".v1", str(schema["$id"]))
                self.assertNotIn(".v2", str(schema["$id"]))
                for pattern in re.findall(r'\^sha256:\[0-9a-f\]\{64\}\$', serialized):
                    self.assertEqual("^sha256:[0-9a-f]{64}$", pattern)


if __name__ == "__main__":
    unittest.main()
