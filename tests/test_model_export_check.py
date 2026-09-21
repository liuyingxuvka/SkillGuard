from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.test_fixed_preflight_units import _root, _source

from skillguard_v2.compact_contract import ContractError, validate_contract_source
from skillguard_v2.contract_compiler import compile_skill_contract


def test_export_check_does_not_execute_all_reports(tmp_path: Path) -> None:
    """Current SkillGuard compiles the explicit v3 source only."""

    root = _root(tmp_path)
    control = root / ".skillguard"
    control.mkdir()
    source = _source()
    source["checks"][0]["args"] = ["-c", "raise RuntimeError('model must not run')"]  # type: ignore[index]
    (control / "contract-source.json").write_text(json.dumps(source), encoding="utf-8")
    result = compile_skill_contract(root, write=True)
    assert result.ok, result.to_dict()
    assert (control / "compiled-contract.json").is_file()
    assert (control / "check-manifest.json").is_file()
    validated = validate_contract_source(root, source)
    assert validated.source["schema_version"] == "skillguard.skill_contract.v3"


@pytest.mark.parametrize("field", ["model_path", "functions", "portfolio"])
def test_export_check_rejects_invalid_model_inputs(tmp_path: Path, field: str) -> None:
    root = _root(tmp_path)
    source = _source()
    source[field] = {}  # type: ignore[index]
    with pytest.raises(ContractError) as raised:
        validate_contract_source(root, source)
    assert raised.value.code == "unknown_field"
