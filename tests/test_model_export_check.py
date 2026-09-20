import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / ".agents" / "skills" / "skillguard" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

try:
    import flowguard  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - source-only SkillGuard checkout
    pytest.skip("the real FlowGuard package is required", allow_module_level=True)

from check_model_export import main  # noqa: E402


MODEL_SOURCE = ROOT / ".agents" / "skills" / "skillguard" / ".skillguard" / "flowguard_contract_model.py"


def _run_model_copy(tmp_path: Path, name: str, suffix: str = "") -> tuple[int, dict[str, object]]:
    model_path = tmp_path / f"{name}.py"
    model_path.write_text(MODEL_SOURCE.read_text(encoding="utf-8") + suffix, encoding="utf-8")
    result = main(
        [
            "--repository-root",
            str(tmp_path),
            "--model-path",
            str(model_path),
        ]
    )
    # main's CLI result is intentionally stdout-only; the test invokes it in
    # a subprocess-shaped boundary so all failures remain typed JSON.
    return result, {}


def test_export_check_does_not_execute_all_reports(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, _ = _run_model_copy(
        tmp_path,
        "model_no_full_run",
        "\n\ndef all_reports():\n    raise RuntimeError('full model must not run')\n",
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 0, payload
    assert payload["status"] == "pass"
    assert payload["known_bad_status"] == "not_run"


@pytest.mark.parametrize(
    ("name", "suffix", "finding"),
    (
        (
            "missing_marker",
            "",
            "flowguard_model_marker_missing",
        ),
        (
            "load_failure",
            "\nraise RuntimeError('load failed')\n",
            "flowguard_model_execution_failed",
        ),
        (
            "wrong_schema",
            "",
            "flowguard_model_export_schema_mismatch",
        ),
    ),
)
def test_export_check_rejects_invalid_model_inputs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    name: str,
    suffix: str,
    finding: str,
) -> None:
    source = MODEL_SOURCE.read_text(encoding="utf-8")
    if name == "missing_marker":
        source = source.replace(
            'FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"',
            'FLOWGUARD_MODEL_MARKER = "wrong-marker"',
            1,
        )
    elif name == "wrong_schema":
        source = source.replace(
            '"schema_version": "skillguard.flowguard_model_export.v2"',
            '"schema_version": "wrong.schema"',
            1,
        )
    model_path = tmp_path / f"{name}.py"
    model_path.write_text(source + suffix, encoding="utf-8")
    code = main(["--repository-root", str(tmp_path), "--model-path", str(model_path)])
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["status"] == "fail"
    assert finding in {row["code"] for row in payload["findings"]}
