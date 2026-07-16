"""Shared JSON, timestamp, and report helpers for SkillGuard scripts."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO


REPORT_OUTPUT_DIRECTORIES = (
    "work",
    ".skillguard/runs",
    ".skillguard/reports",
    ".skillguard/test-results",
)


def skill_root() -> Path:
    return Path(__file__).resolve().parent.parent


def repository_root_for_skill_root(root: Path) -> Path:
    resolved = root.resolve()
    if resolved.parent.name == "skills" and resolved.parent.parent.name == ".agents":
        return resolved.parents[2]
    if resolved.parent.name == "skills" and resolved.parent.parent.name == ".codex":
        return resolved.parents[2]
    return resolved


def repository_root() -> Path:
    return repository_root_for_skill_root(skill_root())


def utc_timestamp() -> str:
    """Return a stable UTC timestamp format for machine-readable reports."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_under_root(path_text: str | Path, root: Path | None = None) -> Path:
    base = (root or repository_root()).resolve()
    candidate = Path(path_text)
    if not candidate.is_absolute():
        candidate = base / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"path must stay under configured root: {path_text}") from exc
    return candidate


def public_relative_path(path_text: str | Path, root: Path | None = None) -> str:
    base = (root or repository_root()).resolve()
    candidate = Path(path_text)
    if not candidate.is_absolute():
        candidate = base / candidate
    candidate = candidate.resolve()
    return candidate.relative_to(base).as_posix()


def load_json(path_text: str | Path, root: Path | None = None) -> Any:
    path = ensure_under_root(path_text, root)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_jsonl(path_text: str | Path, root: Path | None = None) -> list[Any]:
    path = ensure_under_root(path_text, root)
    records: list[Any] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{public_relative_path(path, root)} line {line_number}: {exc}") from exc
    return records


def json_text(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def emit_json(payload: Any, stream: TextIO | None = None) -> None:
    if stream is None:
        stream = sys.stdout
    stream.write(json_text(payload))
    stream.flush()


def dump_json(payload: Any, path_text: str | Path, root: Path | None = None) -> Path:
    path = ensure_under_root(path_text, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_text(payload), encoding="utf-8")
    return path


def write_report(payload: Any, output: str | Path | None = None, root: Path | None = None) -> Path | None:
    if output is None or str(output) == "-":
        emit_json(payload)
        return None
    base = (root or skill_root()).resolve()
    path = ensure_under_root(output, base)
    allowed_roots = [(base / relative).resolve() for relative in REPORT_OUTPUT_DIRECTORIES]
    if not any(path == allowed or path.is_relative_to(allowed) for allowed in allowed_roots):
        allowed_text = ", ".join(REPORT_OUTPUT_DIRECTORIES)
        raise ValueError(
            f"report output must be stdout or stay under a runtime evidence directory ({allowed_text}); "
            "maintained source and fixture trees are not report destinations"
        )
    return dump_json(payload, path, base)
