#!/usr/bin/env python3
"""Validate the current FlowGuard model export without running model reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


_SCRIPT_ROOT = Path(__file__).resolve().parent
if str(_SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_ROOT))

from skillguard_v2.flowguard_adapter import (  # noqa: E402
    FlowGuardAdapterError,
    load_flowguard_model,
)


CHECK_SCHEMA = "skillguard.flowguard_model_export_check.v1"
DEFAULT_MODEL_PATH = Path(
    ".agents/skills/skillguard/.skillguard/flowguard_contract_model.py"
)


def _resolve_path(path: Path, repository_root: Path) -> Path:
    return path if path.is_absolute() else repository_root / path


def _export_summary(snapshot: Any, repository_root: Path) -> dict[str, Any]:
    export = dict(snapshot.model_export)
    model_path = Path(snapshot.model_path)
    try:
        model_path_value = model_path.relative_to(repository_root).as_posix()
    except ValueError:
        model_path_value = model_path.as_posix()
    return {
        "schema_version": CHECK_SCHEMA,
        "status": "pass",
        "validation_status": "export_valid",
        "model_id": str(export["model_id"]),
        "export_schema_version": str(export["schema_version"]),
        "flowguard_schema_version": str(snapshot.flowguard_schema_version),
        "flowguard_package_version": str(snapshot.flowguard_package_version),
        "model_path": model_path_value,
        "function_count": len(export.get("functions", ())),
        "route_count": len(export.get("routes", ())),
        "step_count": len(export.get("steps", ())),
        "obligation_count": len(export.get("obligations", ())),
        "claim_boundary": str(export["claim_boundary"]),
        "known_bad_status": "not_run",
        "claim_note": (
            "This check validates only the marker-bounded FlowGuard export, "
            "schema, version, model identity, and claim boundary. It does "
            "not execute all_reports or known-bad scenarios."
        ),
    }


def _failure_summary(exc: FlowGuardAdapterError) -> dict[str, Any]:
    return {
        "schema_version": CHECK_SCHEMA,
        "status": "fail",
        "validation_status": "export_invalid",
        "findings": [finding.to_dict() for finding in exc.findings],
        "known_bad_status": "not_run",
        "claim_note": (
            "The model export could not be admitted; no full model or "
            "known-bad claim is made."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    args = parser.parse_args(argv)

    repository_root = args.repository_root.resolve(strict=True)
    model_path = _resolve_path(args.model_path, repository_root)
    try:
        snapshot = load_flowguard_model(model_path, repository_root)
    except FlowGuardAdapterError as exc:
        print(json.dumps(_failure_summary(exc), ensure_ascii=False, sort_keys=True))
        return 1
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        payload = {
            "schema_version": CHECK_SCHEMA,
            "status": "fail",
            "validation_status": "export_invalid",
            "findings": [
                {
                    "code": "model_export_check_failed",
                    "path": "$",
                    "message": f"{type(exc).__name__}: {exc}",
                    "severity": "blocker",
                }
            ],
            "known_bad_status": "not_run",
            "claim_note": "No model export or known-bad claim is made.",
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 1

    print(json.dumps(_export_summary(snapshot, repository_root), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
