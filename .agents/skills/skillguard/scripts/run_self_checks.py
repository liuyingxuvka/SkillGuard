"""Run the registered SkillGuard self-check cases exactly once.

The self-check table is an author-owned input.  This runner deliberately does
not discover tests, run a second collection, invoke the public SkillGuard CLI,
or interpret a pytest exit code without checking every required case.
"""

from __future__ import annotations

import json
import ast
import os
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


SCHEMA_VERSION = "skillguard.self_case_groups.v1"
RESULT_SCHEMA_VERSION = "skillguard.self_check_result.v1"
GROUPS = ("admission", "execution", "release")
PLATFORMS = ("nt", "posix")
ALLOWED_TEST_FILES = frozenset(
    {
        "tests/test_contract_v3_routes.py",
        "tests/test_fixed_runtime_evidence.py",
    }
)


def _blocker(code: str, message: str, *, nodeid: str | None = None, phase: str | None = None) -> dict[str, Any]:
    return {
        "code": code,
        "nodeid": nodeid,
        "phase": phase,
        "message": str(message)[:512],
    }


def _print_blocked(group: str, blocker: dict[str, Any], *, expected_count: int = 0) -> int:
    payload = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "group": group,
        "status": "blocked",
        "expected_count": expected_count,
        "collected_count": 0,
        "called_count": 0,
        "passed_count": 0,
        "blocked_count": max(1, expected_count),
        "first_blocker": blocker,
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 1


def _validate_nodeid(value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("self_case_nodeid_invalid")
    if "::test_" not in value:
        raise ValueError("self_case_nodeid_selector_invalid")
    file_part, test_part = value.split("::", 1)
    if file_part not in ALLOWED_TEST_FILES or not test_part.startswith("test_"):
        raise ValueError("self_case_nodeid_file_or_test_invalid")
    if (
        PurePosixPath(file_part).is_absolute()
        or PureWindowsPath(file_part).is_absolute()
        or PureWindowsPath(file_part).drive
        or file_part.startswith(("/", "\\"))
        or any(part in {"", ".", ".."} for part in file_part.replace("\\", "/").split("/"))
    ):
        raise ValueError("self_case_nodeid_path_invalid")
    return value


def _strict_node_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError("self_case_node_list_invalid")
    result = tuple(_validate_nodeid(item) for item in value)
    if len(set(result)) != len(result):
        raise ValueError("self_case_node_list_duplicate")
    return result


def load_required_nodeids(table_path: Path, group: str, platform: str) -> tuple[str, ...]:
    """Load the exact nodeids for one group and the current platform."""

    if group not in GROUPS:
        raise ValueError("self_case_group_invalid")
    if platform not in PLATFORMS:
        raise ValueError("self_case_platform_invalid")
    if not table_path.is_absolute():
        raise ValueError("self_case_table_must_be_absolute")
    raw = json.loads(table_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != {"schema_version", "groups", "platform_cases"}:
        raise ValueError("self_case_table_top_level_invalid")
    if raw.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("self_case_table_schema_invalid")
    groups = raw.get("groups")
    platforms = raw.get("platform_cases")
    if not isinstance(groups, dict) or set(groups) != set(GROUPS):
        raise ValueError("self_case_groups_invalid")
    if not isinstance(platforms, dict) or set(platforms) != set(PLATFORMS):
        raise ValueError("self_case_platforms_invalid")
    selected = list(_strict_node_list(groups[group]))
    for name in PLATFORMS:
        entry = platforms[name]
        if not isinstance(entry, dict) or set(entry) != {"execution"}:
            raise ValueError("self_case_platform_entry_invalid")
        platform_nodes = _strict_node_list(entry["execution"])
        if group == "execution" and name == platform:
            selected.extend(platform_nodes)
    if len(set(selected)) != len(selected):
        raise ValueError("self_case_combined_duplicate")
    return tuple(selected)


class RequiredCaseRecorder:
    """Pytest plugin that records the complete required-case lifecycle."""

    def __init__(self, expected: tuple[str, ...]) -> None:
        if not expected or len(set(expected)) != len(expected):
            raise ValueError("self_case_expected_invalid")
        self.expected = expected
        self.collected: list[str] = []
        self.collection_errors: list[dict[str, Any]] = []
        self.reports: dict[str, dict[str, dict[str, Any]]] = {}
        self.duplicate_reports: list[dict[str, Any]] = []
        self.unexpected_reports: list[dict[str, Any]] = []
        self.invocation_count = 0
        self.collection_finished = False

    def pytest_collectreport(self, report: Any) -> None:
        if getattr(report, "failed", False) or getattr(report, "skipped", False):
            longrepr = getattr(report, "longrepr", "")
            self.collection_errors.append(
                {
                    "code": "collection_error" if getattr(report, "failed", False) else "collection_skipped",
                    "nodeid": str(getattr(report, "nodeid", "")),
                    "phase": "collection",
                    "message": str(longrepr)[:512],
                }
            )

    def pytest_collection_finish(self, session: Any) -> None:
        if self.collection_finished:
            self.collection_errors.append(
                _blocker("duplicate_collection_finish", "pytest_collection_finish called more than once", phase="collection")
            )
            return
        self.collection_finished = True
        self.collected = [str(item.nodeid) for item in session.items]
        if len(set(self.collected)) != len(self.collected):
            self.collection_errors.append(
                _blocker("duplicate_collected_node", "pytest collected a duplicate required node", phase="collection")
            )
        expected_set = set(self.expected)
        collected_set = set(self.collected)
        for nodeid in self.expected:
            if nodeid not in collected_set:
                self.collection_errors.append(
                    _blocker("required_case_missing", "required node was not collected", nodeid=nodeid, phase="collection")
                )
        for nodeid in self.collected:
            if nodeid not in expected_set:
                self.collection_errors.append(
                    _blocker("unexpected_case_collected", "pytest collected an undeclared node", nodeid=nodeid, phase="collection")
                )
        if self.collection_errors or set(self.collected) != expected_set:
            session.shouldfail = "required_case_collection_mismatch"
            session.items[:] = []

    def pytest_runtest_logreport(self, report: Any) -> None:
        nodeid = str(getattr(report, "nodeid", ""))
        phase = str(getattr(report, "when", ""))
        if nodeid not in set(self.expected) or phase not in {"setup", "call", "teardown"}:
            self.unexpected_reports.append(
                _blocker("unexpected_test_report", "pytest emitted a report outside the required case table", nodeid=nodeid, phase=phase)
            )
            return
        phases = self.reports.setdefault(nodeid, {})
        if phase in phases:
            self.duplicate_reports.append(
                _blocker("duplicate_test_report", "pytest emitted the same test phase twice", nodeid=nodeid, phase=phase)
            )
            return
        phases[phase] = {
            "outcome": str(getattr(report, "outcome", "")),
            "wasxfail": bool(getattr(report, "wasxfail", False)) if hasattr(report, "wasxfail") else False,
            "has_wasxfail": hasattr(report, "wasxfail"),
        }


def _first_runtime_blocker(recorder: RequiredCaseRecorder) -> dict[str, Any] | None:
    if recorder.collection_errors:
        return recorder.collection_errors[0]
    if recorder.duplicate_reports:
        return recorder.duplicate_reports[0]
    if recorder.unexpected_reports:
        return recorder.unexpected_reports[0]
    for nodeid in recorder.expected:
        phases = recorder.reports.get(nodeid, {})
        for phase in ("setup", "call", "teardown"):
            report = phases.get(phase)
            if report is None:
                return _blocker("required_case_phase_missing", "required test phase was not reported", nodeid=nodeid, phase=phase)
            if report["outcome"] != "passed":
                return _blocker("required_case_not_passed", f"required test phase outcome was {report['outcome']!r}", nodeid=nodeid, phase=phase)
            if report["wasxfail"] or report["has_wasxfail"]:
                return _blocker("required_case_xfail", "required test phase carried a wasxfail marker", nodeid=nodeid, phase=phase)
    return None


def _result(recorder: RequiredCaseRecorder, pytest_exit: int, blocker: dict[str, Any] | None) -> dict[str, Any]:
    passed_nodes = 0
    called_nodes = 0
    for nodeid in recorder.expected:
        phases = recorder.reports.get(nodeid, {})
        if "call" in phases:
            called_nodes += 1
        if all(
            phase in phases
            and phases[phase]["outcome"] == "passed"
            and not phases[phase]["wasxfail"]
            and not phases[phase]["has_wasxfail"]
            for phase in ("setup", "call", "teardown")
        ):
            passed_nodes += 1
    structure_errors = len(recorder.collection_errors) + len(recorder.duplicate_reports) + len(recorder.unexpected_reports)
    blocked_count = max(0, len(recorder.expected) - passed_nodes) + structure_errors
    status = "passed" if pytest_exit == 0 and blocker is None and passed_nodes == len(recorder.expected) else "blocked"
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "group": "",
        "status": status,
        "expected_count": len(recorder.expected),
        "collected_count": len(recorder.collected),
        "called_count": called_nodes,
        "passed_count": passed_nodes,
        "blocked_count": blocked_count,
        "first_blocker": blocker,
    }


def _validate_expected_sources(root: Path, expected: tuple[str, ...]) -> dict[str, Any] | None:
    """Reject a table entry whose source file no longer declares its test.

    Pytest can reuse an already-imported module when this runner is invoked
    repeatedly in one interpreter.  That can make a missing node look like a
    passing file-level collection.  The table is an author-owned exact
    denominator, so a small source declaration preflight closes that hole
    before the single pytest execution.  Runtime collection still remains the
    authority for parametrization, fixtures, phases, and duplicate reports.
    """

    parsed: dict[Path, ast.AST] = {}
    for nodeid in expected:
        file_part, selector = nodeid.split("::", 1)
        source_path = root / Path(file_part)
        if source_path not in parsed:
            try:
                parsed[source_path] = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
            except FileNotFoundError:
                return _blocker("required_case_missing", "required test source file was not found", nodeid=nodeid, phase="configuration")
            except (OSError, UnicodeError, SyntaxError) as exc:
                return _blocker("required_case_source_invalid", f"required test source cannot be parsed: {exc}", nodeid=nodeid, phase="configuration")
        function_name = selector.split("[", 1)[0]
        if not any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name
            for node in ast.walk(parsed[source_path])
        ):
            return _blocker("required_case_missing", "required test declaration was not found in its source", nodeid=nodeid, phase="configuration")
    return None


def _run(root: Path, table_path: Path, group: str) -> int:
    """Run one explicit table group; this is the private test seam."""

    try:
        root = root.resolve(strict=True)
        table_path = table_path.resolve(strict=True)
        if not root.is_absolute() or not root.is_dir():
            raise ValueError("self_case_root_invalid")
        if not table_path.is_absolute() or not table_path.is_file() or root not in table_path.parents:
            raise ValueError("self_case_table_outside_root")
        if not (root / "pyproject.toml").is_file():
            raise ValueError("self_case_pyproject_missing")
        platform = "nt" if os.name == "nt" else "posix"
        expected = load_required_nodeids(table_path, group, platform)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _print_blocked(group, _blocker("self_runner_configuration", str(exc), phase="configuration"))

    source_blocker = _validate_expected_sources(root, expected)
    if source_blocker is not None:
        return _print_blocked(group, source_blocker, expected_count=len(expected))

    recorder = RequiredCaseRecorder(expected)
    recorder.invocation_count = 1
    previous_cwd = Path.cwd()
    old_autoload = os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD")
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    try:
        os.chdir(root)
        # This import is intentionally after the environment boundary above.
        import pytest

        argv = [
            "-c",
            "pyproject.toml",
            "-p",
            "no:cacheprovider",
            "--confcutdir",
            str(root),
            *expected,
        ]
        pytest_exit = int(pytest.main(argv, plugins=[recorder]))
    except BaseException as exc:
        pytest_exit = 1
        recorder.collection_errors.append(_blocker("self_runner_exception", f"{type(exc).__name__}: {exc}", phase="runner"))
    finally:
        os.chdir(previous_cwd)
        if old_autoload is None:
            os.environ.pop("PYTEST_DISABLE_PLUGIN_AUTOLOAD", None)
        else:
            os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = old_autoload
    blocker = _first_runtime_blocker(recorder)
    payload = _result(recorder, pytest_exit, blocker)
    payload["group"] = group
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if payload["status"] == "passed" else 1


def main(argv: list[str] | None = None) -> int:
    values = list(sys.argv[1:] if argv is None else argv)
    if len(values) != 1 or values[0] not in GROUPS:
        return _print_blocked(values[0] if len(values) == 1 else "", _blocker("self_runner_arguments", "exactly one group argument is required", phase="configuration"))
    root = Path(__file__).resolve().parents[4]
    table_path = root / "tests" / "skillguard_self_cases.json"
    return _run(root, table_path, values[0])


if __name__ == "__main__":
    raise SystemExit(main())
