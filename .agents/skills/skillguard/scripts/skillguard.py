"""SkillGuard local CLI dispatch surface."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from checker_engine import COMMANDS, SkillGuardCliError, error_payload, public_safe_exception_message
from skillguard_utils import emit_json, ensure_under_root, public_relative_path, utc_timestamp
from skillguard_v2.field_lifecycle import V1_RUNTIME_AUTHORITY_COMMANDS


def _argument_value(args: list[str], flag: str) -> str:
    try:
        index = args.index(flag)
    except ValueError:
        return ""
    return args[index + 1] if index + 1 < len(args) else ""


def _v2_authority_target(command: str, args: list[str]) -> Path | None:
    target_text = _argument_value(args, "--target")
    if target_text:
        return ensure_under_root(target_text)
    run_text = _argument_value(args, "--run")
    if not run_text:
        return None
    run_path = ensure_under_root(run_text)
    try:
        payload = json.loads(run_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    target_skill = payload.get("target_skill") if isinstance(payload, dict) else None
    return ensure_under_root(target_skill) if isinstance(target_skill, str) and target_skill else None


def _block_v1_authority_when_v2_present(command: str, args: list[str]) -> bool:
    if command not in V1_RUNTIME_AUTHORITY_COMMANDS:
        return False
    target = _v2_authority_target(command, args)
    if target is None or not (target / ".skillguard" / "contract-source.json").is_file():
        return False
    emit_json(
        {
            "schema_version": "skillguard.cli_result.v1",
            "command": command,
            "checked_at": utc_timestamp(),
            "decision": "block",
            "target_path": public_relative_path(target),
            "blockers": [
                "v2_authority_present: V1 runtime authority cannot execute when .skillguard/contract-source.json exists"
            ],
            "next_action": "Use the V2 compiler and claimed-run supervisor; legacy artifacts remain migration inputs only.",
            "claim_boundary": "This blocker prevents V1 runtime success from replacing or bypassing V2 contract, run, receipt, and closure authority.",
        }
    )
    return True


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help", "help"}:
        return COMMANDS["commands"]([])

    command = args[0]
    handler = COMMANDS.get(command)
    if handler is None:
        emit_json(error_payload(command, f"unknown command: {command}"))
        return 2

    if _block_v1_authority_when_v2_present(command, args[1:]):
        return 1

    try:
        return handler(args[1:])
    except SkillGuardCliError as exc:
        emit_json(error_payload(exc.command, exc.message, exc.category))
        return 2
    except FileNotFoundError as exc:
        emit_json(error_payload(command, public_safe_exception_message(exc), "missing_file"))
        return 1
    except ValueError as exc:
        emit_json(error_payload(command, public_safe_exception_message(exc), "validation_error"))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
