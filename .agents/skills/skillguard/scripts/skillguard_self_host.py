"""Thin executable facade for the single-authority SkillGuard self-host run."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any, Mapping

from skillguard_utils import emit_json
from skillguard_v2.self_host import SelfHostError, run_self_host_bootstrap


SELF_HOST_CLI_TERMINAL_SCHEMA = "skillguard.self_host_cli_terminal.v1"
SELF_HOST_CLI_TERMINAL_ARTIFACT = "skillguard_self_host_cli_terminal"
_SAFE_ERROR_CODE = re.compile(r"^[a-z][a-z0-9_.:-]*$")


def _exception_terminal(exc: Exception) -> Mapping[str, Any]:
    if isinstance(exc, SelfHostError):
        candidate_code = str(exc.code)
        error_code = (
            candidate_code
            if _SAFE_ERROR_CODE.fullmatch(candidate_code)
            else "self_host_declared_error"
        )
        status = "failed"
        reason = "Self-host bootstrap stopped at a declared self-host gate."
    elif isinstance(exc, OSError):
        error_code = "self_host_os_error"
        status = "blocked"
        reason = "Self-host bootstrap could not access a required local resource."
    else:
        error_code = "self_host_unexpected_exception"
        status = "failed"
        reason = "Self-host bootstrap failed unexpectedly."
    return {
        "schema_version": SELF_HOST_CLI_TERMINAL_SCHEMA,
        "artifact_type": SELF_HOST_CLI_TERMINAL_ARTIFACT,
        "status": status,
        "error_code": error_code,
        "reason": reason,
        "claim_boundary": (
            "This path-safe terminal reports only that the bootstrap did not return a "
            "normal self-host result. It does not prove self-host closure, installation, "
            "release readiness, or publication."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="skillguard_self_host.py")
    parser.add_argument("--repository-root", default=".")
    args = parser.parse_args(argv)
    try:
        result = run_self_host_bootstrap(
            Path(args.repository_root),
            profiles=("enforced",),
        )
    except Exception as exc:
        result = _exception_terminal(exc)
    emit_json(result)
    return 0 if result.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
