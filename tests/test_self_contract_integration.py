"""Static checks for the real current SkillGuard self-contract.

These tests inspect the author contract and its declared input edges without
invoking the self-check runner.  Adding this module to a self-check group
would make the runner validate its own validation inventory recursively.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / ".skillguard" / "contract-source.json"


def _contract() -> dict[str, object]:
    payload = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_current_self_contract_has_only_three_check_owners_and_two_routes() -> None:
    contract = _contract()
    checks = contract["checks"]
    assert isinstance(checks, list)
    assert [row["check_id"] for row in checks] == [
        "check:self:author-entry-loading",
        "check:self:declared-check-runtime",
        "check:self:verify-release-provenance",
    ]
    assert [row["args"][-1] for row in checks] == ["admission", "execution", "release"]
    assert all(row["command"] == "{{python}}" for row in checks)
    assert {row["route_id"] for row in contract["routes"]} == {
        "route:change",
        "route:release",
    }
    assert "migration" not in contract
    assert all(
        route["route_id"] not in {"route:read", "route:legacy"}
        for route in contract["routes"]
    )
    assert all(
        obligation["obligation_id"] not in {"obligation:read", "obligation:migration"}
        for obligation in contract["obligations"]
    )


def test_current_self_contract_declares_the_complete_runtime_and_support_edges() -> None:
    contract = _contract()
    inputs = contract["inputs"]
    assert isinstance(inputs, list)
    by_path = {str(row["path"]): row for row in inputs}
    runtime_paths = {
        ".agents/skills/skillguard/scripts/checker_engine.py",
        ".agents/skills/skillguard/scripts/skillguard_v2/execution_records.py",
        ".agents/skills/skillguard/scripts/skillguard_v2/wire_identity.py",
        ".agents/skills/skillguard/scripts/skillguard_v2/path_identity.py",
        ".agents/skills/skillguard/scripts/skillguard_v2/runtime_fingerprint.py",
        ".agents/skills/skillguard/scripts/skillguard_v2/compact_contract.py",
        ".agents/skills/skillguard/scripts/skillguard_v2/compact_state.py",
        ".agents/skills/skillguard/scripts/skillguard_v2/route_runtime.py",
    }
    assert runtime_paths <= by_path.keys()
    assert all((ROOT / path).is_file() for path in runtime_paths)
    assert all(row.get("required") is True for row in inputs)
    declared_ids = {str(row["id"]) for row in inputs}
    for check in contract["checks"]:
        assert set(check["input_ids"]) <= declared_ids
    retired = {
        "references/skillguard-" + "execution-depth.md",
        "references/skillguard-" + "test-mesh.md",
        "references/skillguard-" + "route-index.json",
        ".agents/skills/skillguard/scripts/generate_" + "route_index.py",
    }
    assert retired.isdisjoint(by_path)


def test_self_case_map_names_existing_test_functions_without_recursive_self_tests() -> None:
    table_path = ROOT / "tests" / "skillguard_self_cases.json"
    table = json.loads(table_path.read_text(encoding="utf-8"))
    assert isinstance(table, dict)
    assert set(table["groups"]) == {"admission", "execution", "release"}
    all_cases = [
        *table["groups"]["admission"],
        *table["groups"]["execution"],
        *table["groups"]["release"],
        *table["platform_cases"]["nt"]["execution"],
        *table["platform_cases"]["posix"]["execution"],
    ]
    assert len(all_cases) == len(set(all_cases))
    assert all("test_self_contract_integration.py" not in case for case in all_cases)
    for nodeid in all_cases:
        relative, function = nodeid.split("::", 1)
        source = (ROOT / relative).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=relative)
        function_name = re.split(r"\[", function, maxsplit=1)[0]
        names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert function_name in names, nodeid
