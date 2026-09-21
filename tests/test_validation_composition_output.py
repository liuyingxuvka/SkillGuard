from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / ".flowguard" / "verification" / "owners" / "validation_composition" / "run_checks.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("validation_composition_output_runner", RUNNER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_summary_does_not_expand_report_to_dict(monkeypatch) -> None:
    module = _load_runner()

    def fail_if_called(_report):
        raise AssertionError("summary output must not expand report.to_dict()")

    monkeypatch.setattr(module, "_dict", fail_if_called)
    ok, payload = module.run_all()

    assert payload["detail_level"] == "summary"
    assert payload["status"] == ("pass" if ok else "fail")
    assert payload["positive_gate_status"]
    assert payload["known_bad_gate_status"]
    assert payload["repository_manifest_alignment"]["failed_checks"] == []
    assert len(payload["counterexamples"]) <= 3
    assert len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) <= 8192


def test_full_output_requires_explicit_destination(monkeypatch) -> None:
    module = _load_runner()

    with pytest.raises(SystemExit) as exc:
        module.main(["--full-output"])
    assert exc.value.code == 2

    monkeypatch.setattr(
        module,
        "_dict",
        lambda _report: {"repeated": {"same": "x" * 120, "values": [1, 2, 3]}},
    )
    _ok, payload = module.run_all(detail_level="full")
    assert payload["detail_level"] == "full"
    assert "reports" in payload
    assert "detail_store" in payload
    assert payload["status"] in {"pass", "fail"}
    assert payload["detail_store"]
    assert payload["reports"]["scenario_review"]["repeated"]["$ref"].startswith("detail:")
