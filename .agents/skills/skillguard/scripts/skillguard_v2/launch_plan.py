"""Canonical cross-platform launch planning for target-declared checks."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contract_compiler import canonical_hash


LAUNCH_PLAN_SCHEMA = "skillguard.launch_plan.v1"
WINDOWS_COMMAND_SHIMS = frozenset({".cmd", ".bat"})
WINDOWS_POWERSHELL_SCRIPTS = frozenset({".ps1"})
WINDOWS_PYTHON_SCRIPTS = frozenset({".py"})


@dataclass(frozen=True)
class LaunchPlanError(ValueError):
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


@dataclass(frozen=True)
class ResolvedLaunchPlan:
    record: Mapping[str, Any]
    argv: tuple[str, ...]
    popen_args: str | tuple[str, ...]


def _content_identity(path: Path) -> str:
    if not path.is_file():
        raise LaunchPlanError("launch_program_not_file", str(path))
    candidates = [path]
    if path.name.lower().startswith("python"):
        candidates.extend(
            [Path(sys.prefix) / path.name, Path(sys.base_prefix) / path.name]
        )
    for candidate in candidates:
        try:
            content = candidate.read_bytes()
        except OSError:
            continue
        return "sha256:" + hashlib.sha256(content).hexdigest()
    raise LaunchPlanError("launch_program_unhashable", str(path))


def _resolve_requested_program(
    command: str,
    *,
    cwd: Path,
    environment: Mapping[str, str],
) -> Path:
    candidate = Path(command)
    has_path = candidate.is_absolute() or any(separator in command for separator in ("/", "\\"))
    if has_path:
        resolved = candidate if candidate.is_absolute() else cwd / candidate
        resolved = resolved.resolve()
        if not resolved.is_file():
            raise LaunchPlanError("launch_program_missing", command)
        return resolved
    located = shutil.which(command, path=environment.get("PATH"))
    if not located:
        raise LaunchPlanError("launch_program_missing", command)
    return Path(located).resolve()


def _resolve_interpreter(
    candidates: Sequence[str],
    *,
    environment: Mapping[str, str],
) -> Path:
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.is_file():
            return path.resolve()
        located = shutil.which(candidate, path=environment.get("PATH"))
        if located:
            return Path(located).resolve()
    raise LaunchPlanError("launch_interpreter_missing", ",".join(candidates))


def resolve_launch_plan(
    command: str,
    args: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str],
    environment_fingerprint: str,
    cwd_token: str,
    cwd_relative: str,
    platform_name: str | None = None,
) -> ResolvedLaunchPlan:
    if not isinstance(command, str) or not command:
        raise LaunchPlanError("launch_command_invalid", "command must be non-empty")
    if any(not isinstance(item, str) for item in args):
        raise LaunchPlanError("launch_args_invalid", "args must be strings")
    active_platform = platform_name or sys.platform
    windows = active_platform.startswith("win")
    program = _resolve_requested_program(command, cwd=cwd, environment=environment)
    suffix = program.suffix.lower()
    interpreter: Path | None = None
    adapter = "direct_executable"
    adapter_args: list[str] = []

    if windows and suffix in WINDOWS_COMMAND_SHIMS:
        system_root = environment.get("SystemRoot", os.environ.get("SystemRoot", ""))
        interpreter = _resolve_interpreter(
            [
                environment.get("ComSpec", ""),
                str(Path(system_root) / "System32" / "cmd.exe") if system_root else "",
                "cmd.exe",
            ],
            environment=environment,
        )
        adapter = "windows_command_shim"
        adapter_args = ["/d", "/s", "/c", str(program)]
    elif windows and suffix in WINDOWS_POWERSHELL_SCRIPTS:
        interpreter = _resolve_interpreter(
            ["pwsh.exe", "powershell.exe", "pwsh", "powershell"],
            environment=environment,
        )
        adapter = "windows_powershell_script"
        adapter_args = ["-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(program)]
    elif windows and suffix in WINDOWS_PYTHON_SCRIPTS:
        interpreter = Path(sys.executable).resolve()
        adapter = "windows_python_script"
        adapter_args = [str(program)]
    elif not windows and not os.access(program, os.X_OK):
        raise LaunchPlanError("launch_program_not_executable", str(program))

    if interpreter is None:
        argv = [str(program), *args]
    else:
        argv = [str(interpreter), *adapter_args, *args]
    popen_args: str | tuple[str, ...] = tuple(argv)
    if adapter == "windows_command_shim" and interpreter is not None:
        payload = subprocess.list2cmdline([str(program), *args])
        popen_args = f'"{interpreter}" /d /s /c "{payload}"'
    semantic: dict[str, Any] = {
        "schema_version": LAUNCH_PLAN_SCHEMA,
        "requested_command": command,
        "requested_args": list(args),
        "resolved_program": str(program),
        "resolved_program_identity": _content_identity(program),
        "adapter": adapter,
        "interpreter": str(interpreter) if interpreter is not None else "",
        "interpreter_identity": _content_identity(interpreter) if interpreter is not None else "",
        "argv": argv,
        "cwd": {
            "token": cwd_token,
            "relative": cwd_relative,
            "resolved_identity": canonical_hash(str(cwd.resolve())),
        },
        "platform": active_platform,
        "environment_fingerprint": environment_fingerprint,
        "claim_boundary": (
            "This launch plan proves only exact command resolution for one environment. "
            "It does not prove process success, target semantics, or cleanup."
        ),
    }
    record = {**semantic, "launch_plan_fingerprint": canonical_hash(semantic)}
    return ResolvedLaunchPlan(record=record, argv=tuple(argv), popen_args=popen_args)


__all__ = [
    "LAUNCH_PLAN_SCHEMA",
    "LaunchPlanError",
    "ResolvedLaunchPlan",
    "resolve_launch_plan",
]
