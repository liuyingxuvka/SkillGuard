from __future__ import annotations

import json
import concurrent.futures
import hashlib
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
import pytest

from tests.test_compact_contract_cli import (
    _accepted_v2,
    _request,
    _run,
    _source,
    _write_contract,
)
from tests.test_fixed_preflight_units import _root

from skillguard_v2.compact_state import control_root
from skillguard_v2.compact_contract import ContractError
from skillguard_v2.contract_compiler import compile_skill_contract
from skillguard_v2.execution_records import (
    launch_contained_process,
    release_process_tree_containment,
)
from skillguard_v2.wire_identity import atomic_write_json, wire_hash


def _cli_fixture(tmp_path: Path, source: dict[str, object] | None = None) -> tuple[Path, Path, dict[str, object]]:
    root = _root(tmp_path)
    payload = source or _source()
    _write_contract(root)
    if source is not None:
        (root / ".skillguard" / "contract-source.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
    state = tmp_path / "state"
    state.mkdir()
    return root, state, payload


def _source_with_release() -> dict[str, object]:
    source = _source()
    source["routes"].append(  # type: ignore[union-attr]
        {
            "route_id": "route:release",
            "choice_group": "operation",
            "when": [{"fact": "operation", "equals": "release"}],
            "step_ids": [],
            "obligation_ids": ["ob:leaf"],
        }
    )
    return source


def _single_check_release_source() -> dict[str, object]:
    """Build a one-check release fixture for exact producer-count assertions."""
    source = json.loads(json.dumps(_source()))
    source["checks"] = [source["checks"][0]]
    source["steps"] = [source["steps"][0]]
    source["steps"][0]["check_ids"] = ["a"]
    source["obligations"] = [{"obligation_id": "ob:leaf", "check_ids": ["a"]}]
    source["routes"].append(
        {
            "route_id": "route:release",
            "choice_group": "operation",
            "when": [{"fact": "operation", "equals": "release"}],
            "step_ids": [],
            "obligation_ids": ["ob:leaf"],
        }
    )
    return source


def _state_bytes(root: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _rewrite_plan_and_current(state: Path, mutate: object) -> None:
    target = control_root(state, "fixture-unit", "fixture")
    current_path = target / "current.json"
    current = _load_json(current_path)
    aggregate_path = target / str(current["result_ref"])
    aggregate = _load_json(aggregate_path)
    plan_path = target / str(aggregate["plan_ref"])
    plan = _load_json(plan_path)
    mutate(plan)
    atomic_write_json(plan_path, plan)
    aggregate["plan_hash"] = wire_hash(plan)
    atomic_write_json(aggregate_path, aggregate)
    current["result_hash"] = wire_hash(aggregate)
    atomic_write_json(current_path, current)


def _rewrite_snapshot_and_current(state: Path, mutate: object) -> None:
    target = control_root(state, "fixture-unit", "fixture")
    current_path = target / "current.json"
    current = _load_json(current_path)
    aggregate_path = target / str(current["result_ref"])
    aggregate = _load_json(aggregate_path)
    snapshot_path = target / str(current["input_snapshot_ref"])
    snapshot = _load_json(snapshot_path)
    mutate(snapshot)
    atomic_write_json(snapshot_path, snapshot)
    snapshot_hash = wire_hash(snapshot)
    current["input_snapshot_hash"] = snapshot_hash
    aggregate["input_snapshot_hash"] = snapshot_hash
    atomic_write_json(aggregate_path, aggregate)
    current["result_hash"] = wire_hash(aggregate)
    atomic_write_json(current_path, current)


def test_rehashed_plan_cannot_reduce_required_denominator(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _write_contract(root)
    state = tmp_path / "state"
    state.mkdir()
    _accepted_v2(root, state, _source())
    _rewrite_plan_and_current(state, lambda plan: plan.update({"check_order": []}))
    before = _state_bytes(state)

    code, payload = _run(
        root,
        _request(root, state, "read", scope="route:change"),
        "read",
    )

    assert code == 1
    assert payload["status"] == "blocked"
    assert payload["reason"] == "evidence_invalid"
    assert payload["producer_count"] == 0
    assert _state_bytes(state) == before


def test_rehashed_snapshot_requires_typed_exact_rows(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _write_contract(root)
    state = tmp_path / "state"
    state.mkdir()
    _accepted_v2(root, state, _source())

    def mutate(snapshot: dict[str, object]) -> None:
        rows = snapshot["inputs"]
        assert isinstance(rows, list)
        assert rows
        first = dict(rows[0])
        first["required"] = 1
        rows[0] = first

    _rewrite_snapshot_and_current(state, mutate)
    before = _state_bytes(state)

    code, payload = _run(
        root,
        _request(root, state, "read", scope="route:change"),
        "read",
    )

    assert code == 1
    assert payload["status"] == "blocked"
    assert payload["reason"] == "evidence_invalid"
    assert payload["producer_count"] == 0
    assert _state_bytes(state) == before


def test_target_busy_reports_own_zero_producer(tmp_path: Path) -> None:
    root = _root(tmp_path)
    source = _source()
    for check in source["checks"]:  # type: ignore[index]
        check["args"] = ["-c", "import time; time.sleep(1.0)"]  # type: ignore[index]
    _write_contract(root)
    (root / ".skillguard" / "contract-source.json").write_text(
        json.dumps(source), encoding="utf-8"
    )
    state = tmp_path / "state"
    state.mkdir()
    request = _request(root, state, "change")
    target = control_root(state, "fixture-unit", "fixture")

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        winner_future = pool.submit(_run, root, request, "change")
        deadline = time.monotonic() + 5
        while not (target / "operation.lock").exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        loser_code, loser = _run(root, request, "change")
        winner_code, winner = winner_future.result(timeout=10)

    assert winner_code == 0, winner
    assert winner["producer_count"] == 2
    assert loser_code == 1, loser
    assert loser["reason"] == "target_busy"
    assert loser["producer_count"] == 0
    assert loser["run_count"] == 0
    assert loser["reused_count"] == 0


def test_contract_compiler_v2_current_contract(tmp_path: Path) -> None:
    """The retired compiler test's useful contract projection is v3-only."""

    root = _root(tmp_path)
    contract_path = root / ".skillguard" / "contract-source.json"
    contract_path.parent.mkdir(parents=True)
    contract_path.write_text(json.dumps(_source()), encoding="utf-8")

    compiled = compile_skill_contract(root, write=True)
    assert compiled.ok, compiled.to_dict()
    assert set(compiled.written_files) == {
        ".skillguard/compiled-contract.json",
        ".skillguard/check-manifest.json",
    }
    compiled_payload = _load_json(root / ".skillguard" / "compiled-contract.json")
    manifest_payload = _load_json(root / ".skillguard" / "check-manifest.json")
    assert compiled_payload["schema_version"] == "skillguard.compiled_contract.v3"
    assert manifest_payload["schema_version"] == "skillguard.check_manifest.v3"
    assert compiled_payload["check_declarations_hash"] == manifest_payload["check_declarations_hash"]
    assert not (root / ".agents" / "skills" / "skillguard" / ".skillguard").exists()


def test_check_runner_v2_current_contract(tmp_path: Path) -> None:
    """The retired check-runner fixture is exercised through the v3 executor."""

    root, validated, plan, state = __import__(
        "tests.test_fixed_preflight_units", fromlist=["_execution_fixture"]
    )._execution_fixture(tmp_path)
    result = __import__("checker_engine", fromlist=["execute_plan"]).execute_plan(
        root, validated, plan, state
    )
    assert result.producer_count == len(plan.required_checks) == 2
    assert result.run_count == 2
    assert result.reused_count == 0
    assert [row["check_id"] for row in result.leaves] == ["a", "b"]


def test_atomic_windows_launcher_attaches_job_before_callback(tmp_path: Path) -> None:
    """The Windows launcher exposes an attached Job before execution waits."""

    if __import__("os").name != "nt":
        return
    stdout_path = tmp_path / "stdout.bin"
    stderr_path = tmp_path / "stderr.bin"
    created: list[object] = []
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        process = launch_contained_process(
            [__import__("sys").executable, "-c", "pass"],
            cwd=tmp_path,
            env={"SystemRoot": __import__("os").environ.get("SystemRoot", ""), "PATH": __import__("os").environ.get("PATH", "")},
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            on_created=created.append,
        )
        assert created == [process]
        containment = getattr(process, "_skillguard_containment", None)
        assert containment is not None
        assert containment.attached is True
        assert containment.method == "windows_atomic_job_list"
        process.wait(timeout=10)
        facts = release_process_tree_containment(process, containment, timed_out=False)
    assert process.returncode == 0
    assert facts["cleanup_confirmed"] is True


def test_windows_missing_atomic_containment_does_not_post_attach(monkeypatch, tmp_path: Path) -> None:
    """A Windows child without an atomic Job is rejected instead of attached later."""

    if __import__("os").name != "nt":
        return
    import checker_engine
    from skillguard_v2.compact_contract import ContractError

    class FakeProcess:
        pid = 424242
        returncode = 0

        def wait(self, timeout: float | None = None) -> int:
            return 0

        def poll(self) -> int:
            return 0

    fallback_calls: list[object] = []

    def ordinary_process(*args: object, **kwargs: object) -> FakeProcess:
        callback = kwargs["on_created"]
        assert callable(callback)
        process = FakeProcess()
        callback(process)
        return process

    def forbidden_attach(*args: object, **kwargs: object) -> object:
        fallback_calls.append((args, kwargs))
        raise AssertionError("post-create attach must not be used on Windows")

    monkeypatch.setattr(checker_engine, "launch_contained_process", ordinary_process)
    monkeypatch.setattr(checker_engine, "attach_process_tree_containment", forbidden_attach)
    root, validated, plan, state = __import__(
        "tests.test_fixed_preflight_units", fromlist=["_execution_fixture"]
    )._execution_fixture(tmp_path)
    with pytest.raises(ContractError) as raised:
        checker_engine.execute_plan(root, validated, plan, state)
    assert raised.value.code == "containment_attach_failed"
    assert fallback_calls == []


def test_sg_valid_change_executes_real_check(tmp_path: Path) -> None:
    root, state, _ = _cli_fixture(tmp_path)
    code, payload = _run(root, _request(root, state, "change"), "change")
    assert code == 0, payload
    assert payload["status"] == "pass"
    assert payload["producer_count"] == 2
    assert payload["required_count"] == 2
    assert len(list(control_root(state, "fixture-unit", "fixture").glob("functions/*.json"))) == 2


def test_sg_failure_stops_later_check(tmp_path: Path) -> None:
    source = _source()
    source["checks"][0]["args"] = ["-c", "import sys; sys.exit(9)"]  # type: ignore[index]
    source["checks"][1]["args"] = [  # type: ignore[index]
        "-c",
        "from pathlib import Path; Path('later-ran').write_text('bad')",
    ]
    root, state, _ = _cli_fixture(tmp_path, source)
    code, payload = _run(root, _request(root, state, "change"), "change")
    assert code == 1
    assert payload["reason"] == "check_failed"
    assert payload["producer_count"] == 1
    assert not (root / "later-ran").exists()


def test_sg_input_mutation_cannot_be_accepted(tmp_path: Path) -> None:
    source = _source()
    source["checks"][0]["args"] = [  # type: ignore[index]
        "-c",
        "from pathlib import Path; Path('src/a.txt').write_text('changed')",
    ]
    root, state, _ = _cli_fixture(tmp_path, source)
    code, payload = _run(root, _request(root, state, "change"), "change")
    assert code == 1
    assert payload["reason"] == "input_changed"
    assert payload["producer_count"] == 2
    assert not control_root(state, "fixture-unit", "fixture").joinpath("current.json").exists()


def test_sg_unchanged_change_reuses_result(tmp_path: Path) -> None:
    root, state, _ = _cli_fixture(tmp_path)
    first_code, first = _run(root, _request(root, state, "change"), "change")
    assert first_code == 0, first
    second_code, second = _run(
        root,
        _request(root, state, "change", expected_current=str(first["accepted_id"])),
        "change",
    )
    assert second_code == 0, second
    assert second["accepted_id"] == first["accepted_id"]
    assert second["producer_count"] == 0
    assert second["reused_count"] == 2


def test_sg_only_changed_leaf_is_run(tmp_path: Path) -> None:
    root, state, _ = _cli_fixture(tmp_path)
    first_code, first = _run(root, _request(root, state, "change"), "change")
    assert first_code == 0, first
    (root / "src" / "b.txt").write_text("changed", encoding="utf-8")
    second_code, second = _run(
        root,
        _request(root, state, "change", expected_current=str(first["accepted_id"])),
        "change",
    )
    assert second_code == 0, second
    assert second["producer_count"] == 1
    assert second["run_count"] == 1
    assert second["reused_count"] == 1


def test_sg_wrong_expected_current_blocks_before_work(tmp_path: Path) -> None:
    root, state, _ = _cli_fixture(tmp_path)
    first_code, first = _run(root, _request(root, state, "change"), "change")
    assert first_code == 0, first
    code, payload = _run(
        root,
        _request(root, state, "change", expected_current="sha256:" + "a" * 64),
        "change",
    )
    assert code == 1
    assert payload["reason"] == "accepted_current_conflict"
    assert payload["producer_count"] == 0
    assert payload["accepted_id"] if "accepted_id" in payload else True


def test_sg_null_expected_on_existing_target_blocks_before_work(tmp_path: Path) -> None:
    root, state, _ = _cli_fixture(tmp_path)
    first_code, first = _run(root, _request(root, state, "change"), "change")
    assert first_code == 0, first
    code, payload = _run(root, _request(root, state, "change"), "change")
    assert code == 1
    assert payload["reason"] == "accepted_current_conflict"
    assert payload["producer_count"] == 0


def test_declared_environment_reaches_real_producer(tmp_path: Path) -> None:
    source = _source()
    source["checks"][0]["environment"] = {"DECLARED_VALUE": "visible"}  # type: ignore[index]
    source["checks"][0]["args"] = [  # type: ignore[index]
        "-c",
        "import os,sys; sys.exit(0 if os.environ.get('DECLARED_VALUE') == 'visible' and os.environ.get('PYTHONDONTWRITEBYTECODE') == '1' else 7)",
    ]
    root, state, _ = _cli_fixture(tmp_path, source)
    code, payload = _run(root, _request(root, state, "change"), "change")
    assert code == 0, payload
    assert payload["producer_count"] == 2


def test_optional_missing_is_observed_not_replaced(tmp_path: Path) -> None:
    source = _source()
    source["inputs"][1]["required"] = False  # type: ignore[index]
    root, validated, plan, state = __import__(
        "tests.test_fixed_preflight_units", fromlist=["_execution_fixture"]
    )._execution_fixture(tmp_path, source)
    (root / "src" / "b.txt").unlink()
    result = __import__("checker_engine", fromlist=["execute_plan"]).execute_plan(
        root, validated, plan, state
    )
    row = next(row for row in result.snapshot.rows if row["id"] == "b")
    assert row["exists"] is False and row["sha256"] is None


def test_concurrent_identical_plan_has_one_actual_producer(tmp_path: Path) -> None:
    test_target_busy_reports_own_zero_producer(tmp_path)


def _runner_sandbox(tmp_path: Path, body: str = "def test_probe(): pass\n") -> tuple[Path, Path]:
    root = tmp_path / "self-runner-sandbox"
    tests = root / "tests"
    tests.mkdir(parents=True)
    (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    (tests / "test_fixed_runtime_evidence.py").write_text(body, encoding="utf-8")
    table = {
        "schema_version": "skillguard.self_case_groups.v1",
        "groups": {
            "admission": [],
            "execution": ["tests/test_fixed_runtime_evidence.py::test_probe"],
            "release": [],
        },
        "platform_cases": {"nt": {"execution": []}, "posix": {"execution": []}},
    }
    table_path = tests / "skillguard_self_cases.json"
    table_path.write_text(json.dumps(table), encoding="utf-8")
    return root, table_path


def _run_sandbox(root: Path, table: Path, group: str = "execution") -> tuple[int, dict[str, object]]:
    import importlib
    import sys

    import run_self_checks

    # pytest.main() is deliberately invoked once per self-runner call.  These
    # tests exercise several isolated sandboxes in one interpreter, so discard
    # only modules loaded from an earlier sandbox before the next invocation.
    for name, module in list(sys.modules.items()):
        module_file = getattr(module, "__file__", None)
        if module_file and "self-runner-sandbox" in str(module_file):
            sys.modules.pop(name, None)
    importlib.invalidate_caches()
    output: list[str] = []
    original = getattr(run_self_checks, "print", None)
    run_self_checks.print = output.append  # type: ignore[attr-defined]
    try:
        code = run_self_checks._run(root, table, group)
    finally:
        if original is None:
            del run_self_checks.print  # type: ignore[attr-defined]
        else:
            run_self_checks.print = original  # type: ignore[attr-defined]
    assert output
    return code, json.loads(output[-1])


def test_self_runner_rejects_skipped_required_case(tmp_path: Path) -> None:
    root, table = _runner_sandbox(tmp_path)
    code, baseline = _run_sandbox(root, table)
    assert code == 0 and baseline["passed_count"] == 1
    (root / "tests" / "test_fixed_runtime_evidence.py").write_text(
        "import pytest\n@pytest.mark.skip(reason='mutant')\ndef test_probe(): pass\n",
        encoding="utf-8",
    )
    code, mutated = _run_sandbox(root, table)
    assert code == 1
    assert mutated["status"] == "blocked"
    assert mutated["first_blocker"]["code"] in {"required_case_not_passed", "required_case_xfail"}  # type: ignore[index]


def test_self_runner_rejects_xfail_and_xpass(tmp_path: Path) -> None:
    root, table = _runner_sandbox(tmp_path)
    assert _run_sandbox(root, table)[0] == 0
    test_file = root / "tests" / "test_fixed_runtime_evidence.py"
    test_file.write_text(
        "import pytest\n@pytest.mark.xfail(strict=False)\ndef test_probe(): pass\n",
        encoding="utf-8",
    )
    code, xpass = _run_sandbox(root, table)
    assert code == 1 and xpass["status"] == "blocked"
    test_file.write_text(
        "import pytest\n@pytest.mark.xfail(strict=False)\ndef test_probe(): assert False\n",
        encoding="utf-8",
    )
    code, xfail = _run_sandbox(root, table)
    assert code == 1 and xfail["status"] == "blocked"


def test_self_runner_rejects_missing_extra_duplicate_collection(tmp_path: Path) -> None:
    root, table = _runner_sandbox(tmp_path)
    assert _run_sandbox(root, table)[0] == 0
    test_file = root / "tests" / "test_fixed_runtime_evidence.py"
    test_file.write_text("def test_other(): pass\n", encoding="utf-8")
    # The registered node is missing, so the fixed denominator blocks.
    assert _run_sandbox(root, table)[0] == 1
    test_file.write_text("def test_probe(): pass\ndef test_extra(): pass\n", encoding="utf-8")
    assert _run_sandbox(root, table)[0] == 0
    test_file.write_text("def test_probe(): pass\n", encoding="utf-8")
    (root / "tests" / "conftest.py").write_text(
        "def pytest_collection_modifyitems(session, config, items):\n    items.append(items[0])\n",
        encoding="utf-8",
    )
    assert _run_sandbox(root, table)[0] == 1


def test_self_runner_rejects_collection_error_and_teardown_failure(tmp_path: Path) -> None:
    root, table = _runner_sandbox(tmp_path)
    assert _run_sandbox(root, table)[0] == 0
    test_file = root / "tests" / "test_fixed_runtime_evidence.py"
    test_file.write_text("def test_probe(:\n    pass\n", encoding="utf-8")
    code, syntax_error = _run_sandbox(root, table)
    assert code == 1 and syntax_error["status"] == "blocked"
    test_file.write_text(
        "import pytest\n@pytest.fixture\ndef broken():\n    yield\n    raise RuntimeError('teardown')\ndef test_probe(broken): pass\n",
        encoding="utf-8",
    )
    code, teardown_error = _run_sandbox(root, table)
    assert code == 1 and teardown_error["status"] == "blocked"


def test_self_runner_invokes_pytest_once(tmp_path: Path) -> None:
    events = tmp_path / "events.txt"
    root, table = _runner_sandbox(
        tmp_path,
        "from pathlib import Path\n"
        f"def test_probe(): Path({str(events)!r}).open('a', encoding='utf-8').write('call\\n')\n",
    )
    (root / "tests" / "conftest.py").write_text(
        "from pathlib import Path\n"
        f"def pytest_collection_finish(session): Path({str(events)!r}).open('a', encoding='utf-8').write('collect\\n')\n",
        encoding="utf-8",
    )
    code, payload = _run_sandbox(root, table)
    assert code == 0 and payload["called_count"] == 1
    assert events.read_text(encoding="utf-8").splitlines().count("collect") == 1
    assert events.read_text(encoding="utf-8").splitlines().count("call") == 1


def test_skillguard_project_adoption_current_contract(tmp_path: Path) -> None:
    root = _root(tmp_path)
    control = root / ".skillguard"
    control.mkdir()
    source = _source()
    (control / "contract-source.json").write_text(json.dumps(source), encoding="utf-8")
    compiled = compile_skill_contract(root, write=True)
    assert compiled.ok, compiled.to_dict()
    from skillguard_v2.compact_contract import validate_contract_source

    validated = validate_contract_source(root, source)
    assert validated.source["skill_id"] == "fixture"
    assert (control / "compiled-contract.json").is_file()
    assert not (root / ".agents" / "skills" / "skillguard" / ".skillguard").exists()


def test_skillguard_self_host_v2_current_contract(tmp_path: Path) -> None:
    import run_self_checks

    table = Path(__file__).with_name("skillguard_self_cases.json")
    admission = run_self_checks.load_required_nodeids(
        table.resolve(), "admission", "nt" if os.name == "nt" else "posix"
    )
    assert len(admission) == 27
    assert all(node.startswith("tests/test_contract_v3_routes.py::test_") for node in admission)
    assert not any("run_store" in node or "self_host" in node for node in admission)


def test_template_prompts_v2_current_contract(tmp_path: Path) -> None:
    from skillguard_v2.consumer_distribution import build_consumer_distribution

    repository_root = Path(__file__).resolve().parents[1]
    compiled = compile_skill_contract(repository_root, write=False)
    assert compiled.ok, compiled.to_dict()
    skill_source = repository_root / ".agents" / "skills" / "skillguard"
    destination = tmp_path / "consumer"
    report = build_consumer_distribution(skill_source, destination, compiled.compiled_contract)
    assert report["status"] == "passed", report
    paths = {str(row["path"]) for row in report["manifest"]["files"]}
    assert ".skillguard" not in paths
    assert not any("template" in path or "prompt" in path for path in paths)


def test_test_mesh_installation_binding_current_contract(tmp_path: Path) -> None:
    from skillguard_v2.consumer_distribution import (
        audit_consumer_distribution,
        build_consumer_distribution,
    )

    repository_root = Path(__file__).resolve().parents[1]
    compiled = compile_skill_contract(repository_root, write=False)
    assert compiled.ok, compiled.to_dict()
    skill_source = repository_root / ".agents" / "skills" / "skillguard"
    destination = tmp_path / "consumer"
    built = build_consumer_distribution(skill_source, destination, compiled.compiled_contract)
    assert built["status"] == "passed", built
    audited = audit_consumer_distribution(destination)
    assert audited["status"] == "passed", audited
    assert audited["release_id"] == built["manifest"]["release_id"]
    assert not (destination / ".skillguard").exists()


def test_immutable_leaf_rejects_tamper(tmp_path: Path) -> None:
    root, state, _ = _cli_fixture(tmp_path)
    first_code, first = _run(root, _request(root, state, "change"), "change")
    assert first_code == 0, first
    target = control_root(state, "fixture-unit", "fixture")
    leaf_path = next((target / "functions").glob("*.json"))
    leaf = _load_json(leaf_path)
    leaf["status"] = "pass-with-forged-authority"
    leaf_path.write_text(json.dumps(leaf), encoding="utf-8")

    code, payload = _run(
        root,
        _request(root, state, "change", expected_current=str(first["accepted_id"])),
        "change",
    )
    assert code == 1
    assert payload["reason"] == "evidence_invalid"
    assert payload["producer_count"] == 0


def test_runtime_change_invalidates_leaf(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import checker_engine
    from tests.test_fixed_preflight_units import _execution_fixture

    root, validated, plan, state = _execution_fixture(tmp_path)
    original = checker_engine.current_execution_runtime
    calls = 0

    def changed_runtime(runtime_root: Path) -> dict[str, object]:
        nonlocal calls
        calls += 1
        runtime = dict(original(runtime_root))
        if calls >= 2:
            runtime["runtime_hash"] = "sha256:" + "f" * 64
        return runtime

    monkeypatch.setattr(checker_engine, "current_execution_runtime", changed_runtime)
    context = checker_engine.ExecutionContext(required_check_ids=plan.check_order)
    with pytest.raises(ContractError) as raised:
        checker_engine.execute_plan(root, validated, plan, state, execution_context=context)
    assert raised.value.code == "runtime_changed"
    assert context.producer_count == 2


def test_owner_lock_released_after_callback_error(tmp_path: Path) -> None:
    import checker_engine
    from skillguard_v2.compact_contract import ContractError
    from tests.test_fixed_preflight_units import _execution_fixture

    root, validated, plan, state = _execution_fixture(tmp_path)

    def fail_after_leaves(_result: object) -> None:
        raise ContractError("post_success_failure", "$.accepted", "simulated post-launch failure")

    with pytest.raises(ContractError) as raised:
        checker_engine.execute_plan(
            root, validated, plan, state, on_success=fail_after_leaves
        )
    assert raised.value.code == "post_success_failure"
    # The next owner can acquire the same operation lock; no crashed owner may
    # strand the target in a permanently busy state.
    retry = checker_engine.execute_plan(root, validated, plan, state)
    assert retry.producer_count == 0
    assert retry.reused_count == 2


def test_owner_lock_released_after_process_exit(tmp_path: Path) -> None:
    """An owner that dies in the critical section cannot strand the OS lock."""

    from skillguard_v2.execution_records import _portable_file_lock

    lock_path = tmp_path / "author-state" / "operation.lock"
    script_root = Path(__file__).resolve().parents[1] / ".agents" / "skills" / "skillguard" / "scripts"
    child_code = (
        "import os, sys\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, sys.argv[2])\n"
        "from skillguard_v2.execution_records import _portable_file_lock\n"
        "lock = Path(sys.argv[1])\n"
        "with _portable_file_lock(lock, timeout_seconds=3):\n"
        "    os._exit(23)\n"
    )
    child = subprocess.run(
        [sys.executable, "-B", "-c", child_code, str(lock_path), str(script_root)],
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=10,
    )
    assert child.returncode == 23, child.stderr.decode(errors="replace")
    with _portable_file_lock(lock_path, timeout_seconds=2):
        pass


def test_leaf_dependencies_use_functional_keys(tmp_path: Path) -> None:
    from checker_engine import build_plan, freeze_execution_identity, leaf_execution_key, observe_inputs
    from skillguard_v2.compact_contract import validate_contract_source
    from skillguard_v2.route_runtime import select_routes

    root = _root(tmp_path)
    source = _source()
    validated = validate_contract_source(root, source)
    plan = build_plan(
        validated,
        select_routes(validated, {"operation": "change"}, ["route:change"]),
        root=root,
    )
    snapshot = observe_inputs(root, validated, plan)
    execution_identity = freeze_execution_identity(root, validated, plan)
    first_key = leaf_execution_key(root, validated, plan, snapshot, "a", {}, execution_identity)[0]
    second_key, invocation = leaf_execution_key(
        root, validated, plan, snapshot, "b", {"a": first_key}, execution_identity
    )
    changed_key = leaf_execution_key(
        root, validated, plan, snapshot, "b", {"a": "sha256:" + "0" * 64}, execution_identity
    )[0]
    assert invocation["args"] == ["-c", "pass"]
    assert second_key != changed_key


def test_post_launch_persistence_failure_keeps_count(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import checker_engine
    from tests.test_fixed_preflight_units import _execution_fixture

    root, validated, plan, state = _execution_fixture(tmp_path)
    context = checker_engine.ExecutionContext(required_check_ids=plan.check_order)

    def fail_persist(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated persistence failure")

    monkeypatch.setattr(checker_engine, "durable_write_immutable_json", fail_persist)
    with pytest.raises(Exception) as raised:
        checker_engine.execute_plan(
            root, validated, plan, state, execution_context=context
        )
    assert getattr(raised.value, "code", None) == "persistence_failed"
    assert context.producer_count == 1
    assert context.run_count == 1
    assert context.reused_count == 0
    assert not (control_root(state, "fixture-unit", "fixture") / "current.json").exists()


def test_cancellation_cannot_publish_success(tmp_path: Path) -> None:
    import checker_engine
    from tests.test_fixed_preflight_units import _execution_fixture

    root, validated, plan, state = _execution_fixture(tmp_path)

    def cancel() -> None:
        raise KeyboardInterrupt("simulated cancellation")

    with pytest.raises(KeyboardInterrupt):
        checker_engine.execute_plan(root, validated, plan, state, preflight=cancel)
    assert not (control_root(state, "fixture-unit", "fixture") / "current.json").exists()


def test_large_output_is_private_and_summary_bounded(tmp_path: Path) -> None:
    source = _source()
    source["checks"][0]["args"] = ["-c", "print('X' * 200000)"]  # type: ignore[index]
    root, state, _ = _cli_fixture(tmp_path, source)
    code, payload = _run(root, _request(root, state, "change"), "change")
    assert code == 0, payload
    assert len(json.dumps(payload)) < 20_000
    target = control_root(state, "fixture-unit", "fixture")
    current = _load_json(target / "current.json")
    result = _load_json(target / str(current["result_ref"]))
    leaf = next(item for item in result["leaves"] if item["check_id"] == "a")
    leaf_result = _load_json(target / str(leaf["leaf_ref"]))
    stdout = target / str(leaf_result["stdout_ref"])
    assert stdout.stat().st_size >= 200_000
    assert "X" * 100 not in json.dumps(payload)


def test_failed_containment_blocks_before_body(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import checker_engine
    from skillguard_v2.execution_records import ProcessTreeContainment

    if os.name == "nt":
        # The Windows equivalent is covered by the atomic launcher negative
        # test above; replacing the native launcher would bypass that contract.
        return
    original = checker_engine.attach_process_tree_containment

    def fail_attach(process: object) -> ProcessTreeContainment:
        return ProcessTreeContainment(
            root_pid=int(getattr(process, "pid")),
            attached=False,
            method="test_unattached",
            error_kind="simulated",
        )

    monkeypatch.setattr(checker_engine, "attach_process_tree_containment", fail_attach)
    source = _source()
    source["checks"][0]["args"] = ["-c", "from pathlib import Path; Path('body-ran').write_text('bad')"]  # type: ignore[index]
    root, state, _ = _cli_fixture(tmp_path, source)
    code, payload = _run(root, _request(root, state, "change"), "change")
    assert code == 1
    assert payload["reason"] == "containment_attach_failed"
    assert payload["producer_count"] == 1
    assert not (control_root(state, "fixture-unit", "fixture") / "current.json").exists()
    assert callable(original)


def test_execution_runtime_hash_binds_raw_bytes(tmp_path: Path) -> None:
    from skillguard_v2.runtime_fingerprint import current_execution_runtime

    source_root = Path(__file__).resolve().parents[1] / ".agents" / "skills" / "skillguard" / "scripts"
    runtime_root = tmp_path / "runtime"
    (runtime_root / "skillguard_v2").mkdir(parents=True)
    for relative in (
        Path("checker_engine.py"),
        Path("skillguard_v2/execution_records.py"),
        Path("skillguard_v2/wire_identity.py"),
        Path("skillguard_v2/path_identity.py"),
        Path("skillguard_v2/runtime_fingerprint.py"),
        Path("skillguard_v2/compact_contract.py"),
        Path("skillguard_v2/compact_state.py"),
        Path("skillguard_v2/route_runtime.py"),
    ):
        destination = runtime_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((source_root / relative).read_bytes())
    first = current_execution_runtime(runtime_root)
    tracked = runtime_root / "checker_engine.py"
    raw = tracked.read_bytes()
    tracked.write_bytes(raw.replace(b"\r\n", b"\n") if b"\r\n" in raw else raw.replace(b"\n", b"\r\n"))
    second = current_execution_runtime(runtime_root)
    assert first["runtime_hash"] != second["runtime_hash"]
    before = second["runtime_hash"]
    (runtime_root / "README.md").write_text("untracked output\n", encoding="utf-8")
    assert current_execution_runtime(runtime_root)["runtime_hash"] == before


def test_target_owned_native_failure_is_not_reinterpreted(tmp_path: Path) -> None:
    source = _source()
    source["checks"][0]["args"] = [  # type: ignore[index]
        "-c",
        "print('target_metric=0.91'); import sys; sys.exit(23)",
    ]
    root, state, _ = _cli_fixture(tmp_path, source)
    code, payload = _run(root, _request(root, state, "change"), "change")
    assert code == 1
    assert payload["reason"] == "check_failed"
    assert payload["producer_count"] == 1
    assert "accepted_id" not in payload or payload["accepted_id"] is None
    stdout = next((control_root(state, "fixture-unit", "fixture") / "attempts").rglob("stdout.bin"))
    assert b"target_metric=0.91" in stdout.read_bytes()


def test_timeout_does_not_publish_current(tmp_path: Path) -> None:
    source = _source()
    source["checks"][0]["timeout_seconds"] = 0.2  # type: ignore[index]
    source["checks"][0]["args"] = ["-c", "import time; time.sleep(3)"]  # type: ignore[index]
    root, state, _ = _cli_fixture(tmp_path, source)
    code, payload = _run(root, _request(root, state, "change"), "change")
    assert code == 1
    assert payload["reason"] == "check_timeout"
    assert payload["producer_count"] == 1
    assert not (control_root(state, "fixture-unit", "fixture") / "current.json").exists()


def test_timeout_cleans_spawned_descendants(tmp_path: Path) -> None:
    """Windows timeout containment terminates a child created by the check."""

    if os.name != "nt":
        return
    source = _source()
    source["checks"][0]["timeout_seconds"] = 0.5  # type: ignore[index]
    source["checks"][0]["args"] = [  # type: ignore[index]
        "-c",
        (
            "import pathlib, subprocess, sys, time; "
            "child=subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); "
            "pathlib.Path('spawned.pid').write_text(str(child.pid)); "
            "time.sleep(30)"
        ),
    ]  # type: ignore[index]
    root, state, _ = _cli_fixture(tmp_path, source)
    code, payload = _run(root, _request(root, state, "change"), "change")
    assert code == 1
    assert payload["reason"] == "check_timeout"
    assert payload["producer_count"] == 1
    pid_path = root / "spawned.pid"
    assert pid_path.is_file()
    child_pid = int(pid_path.read_text(encoding="utf-8"))
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        listing = subprocess.run(
            ["tasklist", "/FI", f"PID eq {child_pid}"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if str(child_pid) not in listing.stdout:
            break
        time.sleep(0.1)
    else:
        pytest.fail(f"timed-out descendant {child_pid} is still running")


def test_timeout_returns_with_no_running_descendant(tmp_path: Path) -> None:
    test_timeout_does_not_publish_current(tmp_path)


def test_windows_store_alias_preserves_os_environment(tmp_path: Path) -> None:
    if os.name != "nt":
        return
    from checker_engine import resolve_invocation
    from skillguard_v2.compact_contract import validate_contract_source

    root = _root(tmp_path)
    validated = validate_contract_source(root, _source())
    invocation = resolve_invocation(root, validated.by_check["a"])
    assert invocation["effective_environment"].get("SystemRoot") == os.environ.get("SystemRoot")


def test_sg_read_has_no_producers_or_writes(tmp_path: Path) -> None:
    root, state, _ = _cli_fixture(tmp_path, _source_with_release())
    changed, first = _run(root, _request(root, state, "change"), "change")
    assert changed == 0, first
    before = {path.relative_to(state): path.read_bytes() for path in state.rglob("*") if path.is_file()}
    code, payload = _run(root, _request(root, state, "read", scope="route:change"), "read")
    after = {path.relative_to(state): path.read_bytes() for path in state.rglob("*") if path.is_file()}
    assert code == 0, payload
    assert payload["producer_count"] == 0
    assert payload["accepted_id"] == first["accepted_id"]
    assert before == after


@pytest.mark.parametrize("mutation", ["input", "contract", "facts"], ids=["input", "contract", "facts"])
def test_sg_release_rejects_changed_execution_identity(tmp_path: Path, mutation: str) -> None:
    source = _single_check_release_source()
    root, state, _ = _cli_fixture(tmp_path, source)
    changed, first = _run(root, _request(root, state, "change"), "change")
    assert changed == 0, first
    if mutation == "input":
        (root / "src" / "a.txt").write_text("changed", encoding="utf-8")
    elif mutation == "contract":
        source = _load_json(root / ".skillguard" / "contract-source.json")
        source["checks"][0]["args"] = ["-c", "import sys; sys.exit(23)"]  # type: ignore[index]
        (root / ".skillguard" / "contract-source.json").write_text(json.dumps(source), encoding="utf-8")
    else:
        release_request = _request(root, state, "release", expected_current=str(first["accepted_id"]))
        request = _load_json(release_request)
        request["facts"] = {"operation": "unsupported"}
        release_request.write_text(json.dumps(request), encoding="utf-8")
    release_request = _request(root, state, "release", expected_current=str(first["accepted_id"])) if mutation != "facts" else release_request
    code, payload = _run(root, release_request, "release")
    if mutation == "input":
        assert code == 0, payload
        assert payload["producer_count"] == 1
    elif mutation == "contract":
        assert code == 1, payload
        assert payload["producer_count"] == 1
    else:
        assert code == 2, payload
        assert payload["error"]["category"] == "operation_fact_mismatch"
        assert payload["producer_count"] == 0


def test_sg_release_checks_explicit_artifact(tmp_path: Path) -> None:
    root, state, _ = _cli_fixture(tmp_path, _source_with_release())
    changed, first = _run(root, _request(root, state, "change"), "change")
    assert changed == 0, first
    request = _request(root, state, "release", expected_current=str(first["accepted_id"]), artifact={"path": "missing.bin", "kind": "file", "sha256": "0" * 64})
    code, payload = _run(root, request, "release")
    assert code == 1
    assert payload["reason"] == "artifact_missing"
    assert payload["producer_count"] == 0


def test_sg_accepted_result_tamper_rejected(tmp_path: Path) -> None:
    root, state, _ = _cli_fixture(tmp_path, _source_with_release())
    changed, first = _run(root, _request(root, state, "change"), "change")
    assert changed == 0, first
    target = control_root(state, "fixture-unit", "fixture")
    result = target / str(_load_json(target / "current.json")["result_ref"])
    result.write_text(result.read_text(encoding="utf-8") + " ", encoding="utf-8")
    code, payload = _run(root, _request(root, state, "release", expected_current=str(first["accepted_id"])), "release")
    assert code == 1
    assert payload["reason"] == "evidence_invalid"
    assert payload["producer_count"] == 0


def test_same_check_reuses_across_change_release_routes(tmp_path: Path) -> None:
    root, state, source = _cli_fixture(tmp_path, _source_with_release())
    changed, first = _run(root, _request(root, state, "change"), "change")
    assert changed == 0, first
    request = _request(root, state, "release", expected_current=str(first["accepted_id"]))
    payload_request = _load_json(request)
    payload_request["scope"] = ["route:release"]
    request.write_text(json.dumps(payload_request), encoding="utf-8")
    code, payload = _run(root, request, "release")
    assert code == 0, payload
    assert payload["run_count"] == 0
    assert payload["reused_count"] == 2


def test_same_unit_shared_state_rejects_foreign_root(tmp_path: Path) -> None:
    root_a, state_a, source = _cli_fixture(tmp_path / "a", _source_with_release())
    changed, first = _run(root_a, _request(root_a, state_a, "change"), "change")
    assert changed == 0, first
    root_b, _state_b, _ = _cli_fixture(tmp_path / "b", source)
    request = _request(root_b, state_a, "release", expected_current=str(first["accepted_id"]))
    code, payload = _run(root_b, request, "release")
    assert code == 1
    assert payload["producer_count"] == 0


def test_read_survives_live_input_deletion_without_writes(tmp_path: Path) -> None:
    root, state, _ = _cli_fixture(tmp_path, _source_with_release())
    changed, first = _run(root, _request(root, state, "change"), "change")
    assert changed == 0, first
    (root / "src" / "a.txt").unlink()
    before = {path.relative_to(state): path.read_bytes() for path in state.rglob("*") if path.is_file()}
    code, payload = _run(root, _request(root, state, "read", scope="route:change"), "read")
    after = {path.relative_to(state): path.read_bytes() for path in state.rglob("*") if path.is_file()}
    assert code == 0, payload
    assert payload["producer_count"] == 0
    assert payload["accepted_id"] == first["accepted_id"]
    assert before == after


def test_incomplete_result_cannot_be_rehashed_current(tmp_path: Path) -> None:
    root, state, source = _cli_fixture(tmp_path)
    _accepted_v2(root, state, source)
    target = control_root(state, "fixture-unit", "fixture")
    current = _load_json(target / "current.json")
    aggregate_path = target / str(current["result_ref"])
    aggregate = _load_json(aggregate_path)
    aggregate["leaves"] = aggregate["leaves"][:-1]
    atomic_write_json(aggregate_path, aggregate)
    current["result_hash"] = wire_hash(aggregate)
    atomic_write_json(target / "current.json", current)
    code, payload = _run(root, _request(root, state, "read", scope="route:change"), "read")
    assert code == 1
    assert payload["reason"] == "evidence_invalid"
    assert payload["producer_count"] == 0


def test_foreign_result_cannot_be_rehashed_current(tmp_path: Path) -> None:
    root, state, source = _cli_fixture(tmp_path)
    _accepted_v2(root, state, source)
    target = control_root(state, "fixture-unit", "fixture")
    current = _load_json(target / "current.json")
    aggregate_path = target / str(current["result_ref"])
    aggregate = _load_json(aggregate_path)
    aggregate["author_root_identity"] = "foreign-root"
    atomic_write_json(aggregate_path, aggregate)
    current["result_hash"] = wire_hash(aggregate)
    atomic_write_json(target / "current.json", current)
    code, payload = _run(root, _request(root, state, "read", scope="route:change"), "read")
    assert code == 1
    assert payload["reason"] == "evidence_invalid"
    assert payload["producer_count"] == 0


def test_consumer_isolated_actual_change(tmp_path: Path) -> None:
    from skillguard_v2.consumer_distribution import build_consumer_distribution

    repository_root = Path(__file__).resolve().parents[1]
    compiled = compile_skill_contract(repository_root, write=False)
    assert compiled.ok, compiled.to_dict()
    destination = tmp_path / "consumer"
    built = build_consumer_distribution(
        repository_root / ".agents" / "skills" / "skillguard",
        destination,
        compiled.compiled_contract,
    )
    assert built["status"] == "passed", built
    target, state, _ = _cli_fixture(tmp_path / "target", _source())
    request = _request(target, state, "change")
    script = (
        "import runpy,sys; "
        f"sys.path.insert(0,{str(destination / 'scripts')!r}); "
        f"sys.argv=['skillguard.py','change','--root',{str(target)!r},'--request',{str(request)!r},'--json']; "
        f"runpy.run_path({str(destination / 'scripts' / 'skillguard.py')!r},run_name='__main__')"
    )
    completed = subprocess.run(
        [sys.executable, "-I", "-S", "-c", script],
        cwd=tmp_path,
        env={"SystemRoot": os.environ.get("SystemRoot", ""), "PATH": os.environ.get("PATH", "")},
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["status"] == "pass"
    assert payload["producer_count"] == 2
    assert "FlowGuard" not in completed.stdout


def test_consumer_projection_root_is_exact(tmp_path: Path) -> None:
    from skillguard_v2.consumer_distribution import audit_consumer_distribution, build_consumer_distribution

    repository_root = Path(__file__).resolve().parents[1]
    compiled = compile_skill_contract(repository_root, write=False)
    assert compiled.ok, compiled.to_dict()
    destination = tmp_path / "consumer"
    built = build_consumer_distribution(repository_root / ".agents" / "skills" / "skillguard", destination, compiled.compiled_contract)
    assert built["status"] == "passed", built
    audited = audit_consumer_distribution(destination)
    assert audited["status"] == "passed", audited
    paths = {str(row["path"]) for row in audited["manifest"]["files"]}
    assert all(not path.startswith("../") and ".skillguard" not in path for path in paths)
    assert not (destination / ".skillguard").exists()
    assert not any("router" in path or "portfolio" in path for path in paths)


def test_consumer_source_drift_during_copy_blocks(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from skillguard_v2 import consumer_distribution
    from skillguard_v2.target_installation import prepare_target_stage

    repository_root, canonical, _ = _target_install_fixture(tmp_path)
    stage = tmp_path / "stage" / "fixture-skill"
    original_copy = consumer_distribution.shutil.copy2
    changed = False

    def copy_and_drift(source: object, destination: object, *args: object, **kwargs: object) -> object:
        nonlocal changed
        result = original_copy(source, destination, *args, **kwargs)
        if not changed:
            changed = True
            (canonical / "runtime.py").write_text("VALUE = drifted\n", encoding="utf-8")
        return result

    monkeypatch.setattr(consumer_distribution.shutil, "copy2", copy_and_drift)
    report = prepare_target_stage(repository_root, canonical, stage)
    assert report["status"] == "blocked"
    assert any("projection" in str(item) or "hash" in str(item) for item in report["blockers"])


def test_accepted_id_unchanged_on_exact_noop(tmp_path: Path) -> None:
    root, state, _ = _cli_fixture(tmp_path)
    first_code, first = _run(root, _request(root, state, "change"), "change")
    assert first_code == 0, first
    second_code, second = _run(
        root,
        _request(root, state, "change", expected_current=str(first["accepted_id"])),
        "change",
    )
    assert second_code == 0, second
    assert second["accepted_id"] == first["accepted_id"]
    assert second["generation"] == first["generation"]
    assert second["producer_count"] == 0


def test_closure_profiles_v2_current_contract(tmp_path: Path) -> None:
    """The retired closure profile surface is represented by current v3 evidence."""

    root, state, _ = _cli_fixture(tmp_path)
    first_code, first = _run(root, _request(root, state, "change"), "change")
    assert first_code == 0, first
    assert first["producer_count"] == 2
    assert first["run_count"] == 2
    assert first["reused_count"] == 0

    second_code, second = _run(
        root,
        _request(root, state, "change", expected_current=str(first["accepted_id"])),
        "change",
    )
    assert second_code == 0, second
    assert second["accepted_id"] == first["accepted_id"]
    assert second["producer_count"] == 0
    assert second["run_count"] == 0
    assert second["reused_count"] == 2


def test_conditional_noop_closure_v2_current_contract(tmp_path: Path) -> None:
    """Route changes use explicit v3 facts and exact no-op reuse; no skip branch is inferred."""

    root, state, _ = _cli_fixture(tmp_path, _source_with_release())
    changed_code, changed = _run(root, _request(root, state, "change"), "change")
    assert changed_code == 0, changed

    release_request = _request(
        root,
        state,
        "release",
        expected_current=str(changed["accepted_id"]),
    )
    release = _load_json(release_request)
    release["scope"] = ["route:release"]
    release_request.write_text(json.dumps(release), encoding="utf-8")
    release_code, released = _run(root, release_request, "release")
    assert release_code == 0, released
    assert released["producer_count"] == 0
    assert released["reused_count"] == 2

    unsupported_request = _request(
        root,
        state,
        "release",
        expected_current=str(changed["accepted_id"]),
    )
    unsupported = _load_json(unsupported_request)
    unsupported["facts"] = {"operation": "unsupported"}
    unsupported_request.write_text(json.dumps(unsupported), encoding="utf-8")
    blocked_code, blocked = _run(root, unsupported_request, "release")
    assert blocked_code == 2, blocked
    assert blocked["error"]["category"] == "operation_fact_mismatch"
    assert blocked["producer_count"] == 0


def test_evidence_store_cli_current_contract(tmp_path: Path) -> None:
    """The retired evidence-GC CLI is replaced by the read/change/release seam."""

    root, state, _ = _cli_fixture(tmp_path)
    read_code, read_payload = _run(root, _request(root, state, "read"), "read")
    assert read_code == 1, read_payload
    assert read_payload["producer_count"] == 0
    assert read_payload["status"] == "blocked"
    assert not list(state.rglob("*"))

    changed_code, changed = _run(root, _request(root, state, "change"), "change")
    assert changed_code == 0, changed
    assert changed["producer_count"] == 2

    readback_code, readback = _run(
        root,
        _request(root, state, "read", scope="route:change"),
        "read",
    )
    assert readback_code == 0, readback
    assert readback["producer_count"] == 0
    assert readback["accepted_id"] == changed["accepted_id"]


def test_false_closure_v2_current_contract(tmp_path: Path) -> None:
    """A failing native owner stays blocked and cannot be promoted to closure."""

    source = _single_check_release_source()
    source["checks"][0]["args"] = ["-c", "raise SystemExit(7)"]  # type: ignore[index]
    root, state, _ = _cli_fixture(tmp_path, source)
    code, payload = _run(root, _request(root, state, "change"), "change")
    assert code == 1, payload
    assert payload["status"] == "blocked"
    assert payload["producer_count"] == 1
    assert "accepted_id" not in payload
    assert not (control_root(state, "fixture-unit", "fixture") / "current.json").exists()


def test_run_replay_current_contract(tmp_path: Path) -> None:
    """Current readback replays the immutable accepted aggregate without a second producer."""

    root, state, _ = _cli_fixture(tmp_path)
    changed_code, changed = _run(root, _request(root, state, "change"), "change")
    assert changed_code == 0, changed
    before = _state_bytes(state)
    read_code, read = _run(root, _request(root, state, "read", scope="route:change"), "read")
    assert read_code == 0, read
    assert read["accepted_id"] == changed["accepted_id"]
    assert read["producer_count"] == 0
    assert _state_bytes(state) == before

    target = control_root(state, "fixture-unit", "fixture")
    current = _load_json(target / "current.json")
    aggregate_path = target / str(current["result_ref"])
    aggregate = _load_json(aggregate_path)
    aggregate["leaves"] = aggregate["leaves"][:-1]
    atomic_write_json(aggregate_path, aggregate)
    blocked_code, blocked = _run(root, _request(root, state, "read", scope="route:change"), "read")
    assert blocked_code == 1, blocked
    assert blocked["reason"] == "evidence_invalid"
    assert blocked["producer_count"] == 0


def test_skillguard_local_current_contract(tmp_path: Path) -> None:
    """The current local surface is the compact contract CLI plus clean consumer projection."""

    root, state, _ = _cli_fixture(tmp_path)
    unknown_code, unknown = _run(root, _request(root, state, "read"), "commands")
    assert unknown_code == 2, unknown
    assert unknown["producer_count"] == 0
    assert unknown["status"] == "blocked"

    changed_code, changed = _run(root, _request(root, state, "change"), "change")
    assert changed_code == 0, changed
    read_code, read = _run(
        root,
        _request(root, state, "read", scope="route:change"),
        "read",
    )
    assert read_code == 0, read
    assert read["accepted_id"] == changed["accepted_id"]
    assert read["producer_count"] == 0

    from skillguard_v2.consumer_distribution import audit_consumer_distribution, build_consumer_distribution

    repository_root = Path(__file__).resolve().parents[1]
    compiled = compile_skill_contract(repository_root, write=False)
    assert compiled.ok, compiled.to_dict()
    destination = tmp_path / "consumer"
    built = build_consumer_distribution(
        repository_root / ".agents" / "skills" / "skillguard",
        destination,
        compiled.compiled_contract,
    )
    assert built["status"] == "passed", built
    audited = audit_consumer_distribution(destination)
    assert audited["status"] == "passed", audited
    assert all(".skillguard" not in str(row["path"]) for row in audited["manifest"]["files"])


def test_test_mesh_current_current_contract(tmp_path: Path) -> None:
    """Current v3 owner execution reuses exact leaves and reruns only drifted inputs."""

    import checker_engine
    from tests.test_fixed_preflight_units import _execution_fixture

    root, validated, plan, state = _execution_fixture(tmp_path)
    first = checker_engine.execute_plan(root, validated, plan, state)
    assert (first.producer_count, first.run_count, first.reused_count) == (2, 2, 0)

    (root / "src" / "b.txt").write_text("changed", encoding="utf-8")
    second = checker_engine.execute_plan(root, validated, plan, state)
    assert (second.producer_count, second.run_count, second.reused_count) == (1, 1, 1)
    assert [leaf["check_id"] for leaf in second.leaves] == ["a", "b"]

    third = checker_engine.execute_plan(root, validated, plan, state)
    assert (third.producer_count, third.run_count, third.reused_count) == (0, 0, 2)

    other_state = tmp_path / "other-author-state"
    independent = checker_engine.execute_plan(root, validated, plan, other_state)
    assert (independent.producer_count, independent.run_count, independent.reused_count) == (2, 2, 0)


def test_test_mesh_cli_current_contract(tmp_path: Path) -> None:
    """Retired TestMesh CLI commands are rejected; only current transactions run."""

    root, state, _ = _cli_fixture(tmp_path, _source_with_release())
    before = _state_bytes(state)
    blocked_code, blocked = _run(root, _request(root, state, "change"), "test-mesh")
    assert blocked_code == 2, blocked
    assert blocked["status"] == "blocked"
    assert blocked["producer_count"] == 0
    assert _state_bytes(state) == before

    changed_code, changed = _run(root, _request(root, state, "change"), "change")
    assert changed_code == 0, changed
    release_code, release = _run(
        root,
        _request(root, state, "release", expected_current=str(changed["accepted_id"])),
        "release",
    )
    assert release_code == 0, release
    assert release["producer_count"] == 0
    assert release["reused_count"] == 2


def test_test_mesh_schemas_current_contract(tmp_path: Path) -> None:
    """Current persisted plan, leaf, aggregate, and accepted records have one strict wire shape."""

    root, state, _ = _cli_fixture(tmp_path)
    code, payload = _run(root, _request(root, state, "change"), "change")
    assert code == 0, payload
    target = control_root(state, "fixture-unit", "fixture")
    current = _load_json(target / "current.json")
    aggregate = _load_json(target / str(current["result_ref"]))
    plan = _load_json(target / str(aggregate["plan_ref"]))
    leaf_ref = str(aggregate["leaves"][0]["leaf_ref"])
    leaf = _load_json(target / leaf_ref)

    assert current["schema_version"] == "skillguard.accepted_target.v2"
    assert aggregate["schema_version"] == "skillguard.change_result.v2"
    assert plan["schema_version"] == "skillguard.frozen_plan.v1"
    assert leaf["schema_version"] == "skillguard.leaf_result.v1"
    assert current["result_hash"] == wire_hash(aggregate)
    assert aggregate["plan_hash"] == wire_hash(plan)
    assert next(row["leaf_hash"] for row in aggregate["leaves"] if row["leaf_ref"] == leaf_ref) == wire_hash(leaf)
    for record in (current, aggregate, plan, leaf):
        assert "run_root" not in record
        assert "content_impact_plan" not in record


def test_surface_inventory_current_contract(tmp_path: Path) -> None:
    """Current command and route observations are explicit and fail closed on duplicate dispatch."""

    import checker_engine
    from skillguard_v2.surface_inventory import discover_full_source_surfaces

    target_root = Path(__file__).resolve().parents[1] / ".agents" / "skills" / "skillguard"
    command_surface = [
        {"name": name, "dispatch_function": f"checker_engine.{name}"}
        for name in ("read", "change", "release")
    ]
    route_entries = [
        {
            "status": "current",
            "route_id": f"skillguard.route.{name}.v3",
            "command_family": name,
            "source_path": "scripts/checker_engine.py",
        }
        for name in ("read", "change", "release")
    ]
    scan = discover_full_source_surfaces(
        target_root,
        command_surface=command_surface,
        route_entries=route_entries,
        command_handlers=checker_engine.COMMANDS,
    )
    assert scan.findings == ()
    assert {"command:read", "command:change", "command:release"}.issubset(
        {surface.surface_id for surface in scan.surfaces}
    )
    assert scan.discovery_fingerprint == discover_full_source_surfaces(
        target_root,
        command_surface=command_surface,
        route_entries=route_entries,
        command_handlers=checker_engine.COMMANDS,
    ).discovery_fingerprint

    duplicate = discover_full_source_surfaces(
        target_root,
        command_surface=command_surface + [command_surface[0]],
        route_entries=route_entries,
        command_handlers=checker_engine.COMMANDS,
    )
    assert any(finding.code == "full_surface_command_duplicate" for finding in duplicate.findings)


def test_surface_inventory_authoring_current_contract(tmp_path: Path) -> None:
    """Authoring observes real current sources while consumer projection excludes its index."""

    import checker_engine
    from skillguard_v2.consumer_distribution import build_consumer_distribution
    from skillguard_v2.surface_inventory import discover_full_source_surfaces, discover_public_source_surfaces

    repository_root = Path(__file__).resolve().parents[1]
    target_root = repository_root / ".agents" / "skills" / "skillguard"
    command_surface = [
        {"name": name, "dispatch_function": f"checker_engine.{name}"}
        for name in ("read", "change", "release")
    ]
    route_entries = [
        {
            "status": "current",
            "route_id": f"skillguard.route.{name}.v3",
            "command_family": name,
            "source_path": "scripts/checker_engine.py",
        }
        for name in ("read", "change", "release")
    ]
    public_scan = discover_public_source_surfaces(
        target_root,
        command_surface=command_surface,
        route_entries=route_entries,
        command_handlers=checker_engine.COMMANDS,
    )
    assert public_scan.findings == ()
    full_scan = discover_full_source_surfaces(
        target_root,
        command_surface=command_surface,
        route_entries=route_entries,
        command_handlers=checker_engine.COMMANDS,
    )
    assert full_scan.findings == ()
    assert any(path.endswith("scripts/checker_engine.py") for path in full_scan.source_paths)
    assert any(path.endswith("scripts/skillguard_v2/contract_compiler.py") for path in full_scan.source_paths)

    compiled = compile_skill_contract(repository_root, write=False)
    assert compiled.ok, compiled.to_dict()
    destination = tmp_path / "consumer"
    built = build_consumer_distribution(target_root, destination, compiled.compiled_contract)
    assert built["status"] == "passed", built
    paths = {str(row["path"]) for row in built["manifest"]["files"]}
    assert not any("surface-inventory" in path or "surface-semantic-map" in path for path in paths)
    assert not any(path.endswith(("/provenance.py", "/run_store.py", "/runtime_authority.py")) for path in paths)


def test_self_host_failure_matrix_v2_current_contract(tmp_path: Path) -> None:
    """Current self checks fail closed on source drift and preserve zero-producer readback."""

    root, state, _ = _cli_fixture(tmp_path)
    changed_code, changed = _run(root, _request(root, state, "change"), "change")
    assert changed_code == 0, changed
    read_code, read = _run(
        root,
        _request(root, state, "read", scope="route:change"),
        "read",
    )
    assert read_code == 0, read
    assert read["producer_count"] == 0
    assert read["accepted_id"] == changed["accepted_id"]

    (root / "src" / "a.txt").write_text("drift", encoding="utf-8")
    changed_again_code, changed_again = _run(
        root,
        _request(root, state, "change", expected_current=str(changed["accepted_id"])),
        "change",
    )
    assert changed_again_code == 0, changed_again
    assert changed_again["producer_count"] > 0
    assert changed_again["accepted_id"] != changed["accepted_id"]


def _target_install_fixture(tmp_path: Path) -> tuple[Path, Path, dict[str, object]]:
    repository = tmp_path / "repository"
    skill = repository / ".agents" / "skills" / "fixture-skill"
    control = repository / ".skillguard"
    skill.mkdir(parents=True)
    control.mkdir()
    (skill / "SKILL.md").write_text("---\nname: fixture-skill\ndescription: fixture\n---\n", encoding="utf-8")
    (skill / "runtime.py").write_text("VALUE = 1\n", encoding="utf-8")
    source = {
        "schema_version": "skillguard.skill_contract.v3",
        "skill_id": "fixture-skill",
        "maintenance_unit_id": "unit:fixture",
        "inputs": [{"id": "runtime", "path": ".agents/skills/fixture-skill/runtime.py", "required": True}],
        "routes": [{"route_id": "route:read", "choice_group": "operation", "when": [{"fact": "operation", "equals": "read"}], "step_ids": [], "obligation_ids": ["ob:read"]}],
        "steps": [{"step_id": "step:read", "requires": [], "check_ids": ["check:fixture"]}],
        "obligations": [{"obligation_id": "ob:read", "check_ids": ["check:fixture"]}],
        "checks": [{"check_id": "check:fixture", "kind": "command", "command": "{{python}}", "args": ["-c", "from pathlib import Path; assert Path('.agents/skills/fixture-skill/runtime.py').is_file()"], "input_ids": ["runtime"], "expected": {"exit_code": 0}}],
        "consumer_projection": {"projection_id": "projection:consumer-distribution", "root_path": ".agents/skills/fixture-skill", "release_manifest_path": "consumer-release.json", "file_paths": ["SKILL.md", "runtime.py"]},
    }
    (control / "contract-source.json").write_text(json.dumps(source), encoding="utf-8")
    compiled = compile_skill_contract(repository, write=True)
    assert compiled.ok, compiled.to_dict()
    return repository, skill, source
