"""Run the one current SkillGuard executable-contract model."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

_MODEL_DIR = Path(__file__).resolve().parents[4] / ".flowguard" / "models" / "owners" / "development_process_flow"
if str(_MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(_MODEL_DIR))

from model import all_reports, reports_ok


MODEL_EXPORT_CHECK_SCHEMA = "skillguard.flowguard_model_export_check.v1"
MODEL_ID = "skillguard.executable_contract_runtime.v2"


def _load_joint_model_export(path: Path, repository_root: Path) -> dict[str, Any]:
    """Read a real export-leaf result from the same frozen joint plan.

    The complete model remains the only producer of scenario and known-bad
    evidence.  This optional input lets a joint plan project the already-run
    export leaf into this wrapper without invoking the loader or model again.
    """

    resolved = path if path.is_absolute() else repository_root / path
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"model export leaf unreadable: {type(exc).__name__}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("model export leaf must be an object")
    if payload.get("schema_version") != MODEL_EXPORT_CHECK_SCHEMA:
        raise ValueError("model export leaf schema mismatch")
    if payload.get("status") != "pass" or payload.get("validation_status") != "export_valid":
        raise ValueError("model export leaf is not a passing export validation")
    if payload.get("model_id") != MODEL_ID:
        raise ValueError("model export leaf model identity mismatch")
    return {
        "status": "reused",
        "validation_status": str(payload["validation_status"]),
        "model_id": str(payload["model_id"]),
        "export_schema_version": str(payload.get("export_schema_version", "")),
        "known_bad_status": str(payload.get("known_bad_status", "not_run")),
    }


def _build_payload(
    reports: Mapping[str, object],
    *,
    model_export_leaf: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "skillguard.flowguard_model_result.v1",
        "model_id": "skillguard.executable_contract_runtime.v2",
        "status": "pass" if reports_ok(reports.values()) else "fail",
        "reports": {
            name: {
                "ok": bool(getattr(report, "ok", False)),
                "finding_count": len(getattr(report, "findings", ())),
            }
            for name, report in reports.items()
        },
        "claim_boundary": (
            "This runner covers the current SkillGuard executable-contract "
            "model, including its read-only assurance-diagnostics route. It "
            "does not prove repository tests, installation, Git, or release."
        ),
    }
    if model_export_leaf is not None:
        payload["model_export_leaf"] = dict(model_export_leaf)
    return payload


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--model-export-result", type=Path)
    args = parser.parse_args(argv)

    repository_root = Path(__file__).resolve().parents[4]
    model_export_leaf = None
    if args.model_export_result is not None:
        try:
            model_export_leaf = _load_joint_model_export(
                args.model_export_result,
                repository_root,
            )
        except ValueError as exc:
            print(
                json.dumps(
                    {
                        "schema_version": "skillguard.flowguard_model_result.v1",
                        "model_id": MODEL_ID,
                        "status": "fail",
                        "model_export_leaf": {
                            "status": "rejected",
                            "reason": str(exc),
                        },
                        "claim_boundary": (
                            "The joint model export leaf was not admitted; "
                            "no complete-model or known-bad claim is made."
                        ),
                    },
                    sort_keys=True,
                )
            )
            return 1
    reports = all_reports()
    payload = _build_payload(reports, model_export_leaf=model_export_leaf)
    print(json.dumps(payload, sort_keys=True))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
