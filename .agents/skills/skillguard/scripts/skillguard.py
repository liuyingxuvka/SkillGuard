"""SkillGuard local CLI dispatch surface."""

from __future__ import annotations

import sys

from checker_engine import COMMANDS, SkillGuardCliError, error_payload, public_safe_exception_message
from skillguard_utils import emit_json


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help", "help"}:
        return COMMANDS["commands"]([])

    command = args[0]
    handler = COMMANDS.get(command)
    if handler is None:
        emit_json(error_payload(command, f"unknown command: {command}"))
        return 2

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
