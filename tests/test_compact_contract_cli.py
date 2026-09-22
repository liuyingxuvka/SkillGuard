from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tests.test_fixed_preflight_units import SCRIPT_ROOT, _root, _source

sys.path.insert(0, str(SCRIPT_ROOT))

from skillguard_v2.contract_compiler import compile_skill_contract  # noqa: E402
from skillguard_v2.compact_contract import validate_contract_source  # noqa: E402
from skillguard_v2.compact_state import author_root_identity, control_root  # noqa: E402
from skillguard_v2.route_runtime import select_routes  # noqa: E402
from skillguard_v2.execution_records import durable_write_immutable_json  # noqa: E402
from skillguard_v2.wire_identity import atomic_write_json, wire_hash  # noqa: E402
from checker_engine import build_plan, freeze_execution_identity, leaf_execution_key, observe_inputs  # noqa: E402


CLI = SCRIPT_ROOT / "skillguard.py"


def _write_contract(root: Path) -> None:
    control = root / ".skillguard"
    control.mkdir()
    (control / "contract-source.json").write_text(json.dumps(_source()), encoding="utf-8")


def _request(root: Path, state: Path, operation: str, *, expected_current: str | None = None, scope: str | None = None, artifact: dict[str, str] | None = None) -> Path:
    payload: dict[str, object] = {
        "operation": operation,
        "target_id": "fixture",
        "scope": [scope or f"route:{operation}"],
        "contract_path": ".skillguard/contract-source.json",
        "author_state_root": str(state),
    }
    if operation in {"change", "release"}:
        payload["expected_current"] = expected_current
        payload["facts"] = {"operation": operation}
    if operation == "release" and artifact is not None:
        payload["artifact"] = artifact
    path = root / f"{operation}.request.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _run(root: Path, request: Path, operation: str) -> tuple[int, dict[str, object]]:
    completed = subprocess.run(
        [sys.executable, str(CLI), operation, "--root", str(root), "--request", str(request), "--json"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return completed.returncode, json.loads(completed.stdout)


def _accepted_v2(root: Path, state: Path, source: dict[str, object]) -> tuple[str, Path]:
    validated = validate_contract_source(root, source)
    decision = select_routes(validated, {"operation": "change"}, ["route:change"])
    plan = build_plan(validated, decision, operation="change", root=root)
    snapshot = observe_inputs(root, validated, plan)
    execution_identity = freeze_execution_identity(root, validated, plan)
    target = control_root(state, "fixture-unit", "fixture")
    target.mkdir(parents=True)
    identity = author_root_identity(root)
    atomic_write_json(target / "binding.json", {
        "schema_version": "skillguard.target_state_binding.v1",
        "maintenance_unit_id": "fixture-unit",
        "skill_id": "fixture",
        "author_root_identity": identity,
        "contract_relative_path": ".skillguard/contract-source.json",
    })
    plan_payload = plan.to_dict()
    plan_ref = f"plans/{wire_hash(plan_payload)[7:]}.plan.json"
    durable_write_immutable_json(target / plan_ref, plan_payload)
    snapshot_payload = {
        "schema_version": "skillguard.input_snapshot.v2",
        "maintenance_unit_id": "fixture-unit",
        "skill_id": "fixture",
        "author_root_identity": identity,
        "inputs": list(snapshot.rows),
    }
    snapshot_ref = f"inputs/{wire_hash(snapshot_payload)[7:]}.inputs.json"
    durable_write_immutable_json(target / snapshot_ref, snapshot_payload)
    contract_ref = f"contracts/{wire_hash(source)[7:]}.contract.json"
    durable_write_immutable_json(target / contract_ref, source)
    dependency_keys: dict[str, str] = {}
    leaf_refs: list[dict[str, str]] = []
    for check_id in plan.check_order:
        dependencies = {item: dependency_keys[item] for item in plan.check_dependencies[check_id]}
        key, _ = leaf_execution_key(root, validated, plan, snapshot, check_id, dependencies, execution_identity)
        attempt = target / "attempts" / ("fixture-" + check_id)
        attempt.mkdir(parents=True)
        (attempt / "stdout.bin").write_bytes(b"")
        (attempt / "stderr.bin").write_bytes(b"")
        empty_hash = "sha256:" + __import__("hashlib").sha256(b"").hexdigest()
        leaf = {
            "schema_version": "skillguard.leaf_result.v1",
            "maintenance_unit_id": "fixture-unit",
            "skill_id": "fixture",
            "author_root_identity": identity,
            "check_id": check_id,
            "execution_key": key,
            "dependency_execution_keys": dependencies,
            "status": "pass",
            "exit_code": 0,
            "cleanup_confirmed": True,
            "stdout_ref": (attempt / "stdout.bin").relative_to(target).as_posix(),
            "stdout_hash": empty_hash,
            "stderr_ref": (attempt / "stderr.bin").relative_to(target).as_posix(),
            "stderr_hash": empty_hash,
        }
        leaf_ref = f"functions/{key[7:]}.json"
        durable_write_immutable_json(target / leaf_ref, leaf)
        leaf_refs.append({"check_id": check_id, "execution_key": key, "leaf_ref": leaf_ref, "leaf_hash": wire_hash(leaf)})
        dependency_keys[check_id] = key
    aggregate = {
        "schema_version": "skillguard.change_result.v2",
        "maintenance_unit_id": "fixture-unit",
        "skill_id": "fixture",
        "author_root_identity": identity,
        "status": "pass",
        "plan_ref": plan_ref,
        "plan_hash": wire_hash(plan_payload),
        "input_snapshot_ref": snapshot_ref,
        "input_snapshot_hash": wire_hash(snapshot_payload),
        "contract_snapshot_ref": contract_ref,
        "contract_snapshot_hash": wire_hash(source),
        "required_checks": list(plan.check_order),
        "leaves": leaf_refs,
        "qualification": "source_qualification_only",
        "artifact": None,
    }
    result_ref = f"results/{wire_hash(aggregate)[7:]}.result.json"
    durable_write_immutable_json(target / result_ref, aggregate)
    accepted = {
        "schema_version": "skillguard.accepted_target.v2",
        "maintenance_unit_id": "fixture-unit",
        "skill_id": "fixture",
        "author_root_identity": identity,
        "generation": 1,
        "result_ref": result_ref,
        "result_hash": wire_hash(aggregate),
        "input_snapshot_ref": snapshot_ref,
        "input_snapshot_hash": wire_hash(snapshot_payload),
        "contract_snapshot_ref": contract_ref,
        "contract_snapshot_hash": wire_hash(source),
    }
    atomic_write_json(target / "current.json", accepted)
    return wire_hash(accepted), target


def test_compiler_uses_only_repository_root_contract(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _write_contract(root)
    result = compile_skill_contract(root, write=True)
    assert result.ok
    assert set(result.written_files) == {".skillguard/compiled-contract.json", ".skillguard/check-manifest.json"}
    assert not (root / ".agents" / "skills" / "skillguard" / ".skillguard").exists()
    checked = compile_skill_contract(root, write=False)
    assert checked.ok and checked.written_files == ()


def test_read_uninitialized_is_blocked_and_writes_nothing(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _write_contract(root)
    state = tmp_path / "state"
    state.mkdir()
    before = list(state.rglob("*"))
    code, payload = _run(root, _request(root, state, "read", scope="route:change"), "read")
    assert code == 1
    assert payload["status"] == "blocked"
    assert payload["producer_count"] == 0
    assert list(state.rglob("*")) == before


def test_read_uses_accepted_snapshot_after_live_contract_and_inputs_change(tmp_path: Path) -> None:
    root = _root(tmp_path)
    source = _source()
    _write_contract(root)
    state = tmp_path / "state"
    state.mkdir()
    accepted_id, _ = _accepted_v2(root, state, source)
    (root / "src" / "b.txt").unlink()
    locator_only = {"schema_version": "skillguard.skill_contract.v3", "skill_id": "fixture", "maintenance_unit_id": "fixture-unit"}
    (root / ".skillguard" / "contract-source.json").write_text(json.dumps(locator_only), encoding="utf-8")
    before = {path.relative_to(state): path.read_bytes() for path in state.rglob("*") if path.is_file()}
    code, payload = _run(root, _request(root, state, "read", scope="route:change"), "read")
    assert code == 0
    assert payload["status"] == "pass" and payload["as_of_accepted"] is True
    assert payload["accepted_id"] == accepted_id and payload["producer_count"] == 0
    assert before == {path.relative_to(state): path.read_bytes() for path in state.rglob("*") if path.is_file()}


def test_read_reports_missing_leaf_without_writes_or_execution(tmp_path: Path) -> None:
    root = _root(tmp_path)
    source = _source()
    _write_contract(root)
    state = tmp_path / "state"
    state.mkdir()
    _, target = _accepted_v2(root, state, source)
    next((target / "functions").glob("*.json")).unlink()
    before = {path.relative_to(state): path.read_bytes() for path in state.rglob("*") if path.is_file()}
    code, payload = _run(root, _request(root, state, "read", scope="route:change"), "read")
    assert code == 1
    assert payload["reason"] == "qualification_incomplete" and payload["producer_count"] == 0
    assert before == {path.relative_to(state): path.read_bytes() for path in state.rglob("*") if path.is_file()}


def test_change_executes_obligation_owner_and_prerequisite(tmp_path: Path) -> None:
    root = _root(tmp_path)
    source = _source()
    source["routes"].append({"route_id": "route:release", "choice_group": "operation", "when": [{"fact": "operation", "equals": "release"}], "step_ids": [], "obligation_ids": ["ob:leaf"]})  # type: ignore[union-attr]
    control = root / ".skillguard"
    control.mkdir()
    (control / "contract-source.json").write_text(json.dumps(source), encoding="utf-8")
    state = tmp_path / "state"
    state.mkdir()
    code, payload = _run(root, _request(root, state, "change"), "change")
    assert code == 0
    assert payload["status"] == "pass"
    assert payload["required_count"] == 2
    assert payload["run_count"] == 2
    assert payload["producer_count"] == 2
    assert isinstance(payload["accepted_id"], str)


def test_change_same_plan_reuses_leaves_and_keeps_accepted_generation(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _write_contract(root)
    state = tmp_path / "state"
    state.mkdir()
    first_code, first = _run(root, _request(root, state, "change"), "change")
    assert first_code == 0
    second_code, second = _run(
        root,
        _request(root, state, "change", expected_current=str(first["accepted_id"])),
        "change",
    )
    assert second_code == 0
    assert second["accepted_id"] == first["accepted_id"]
    assert second["generation"] == first["generation"] == 1
    assert second["producer_count"] == 0 and second["reused_count"] == 2


def test_change_wrong_initial_pointer_starts_no_producer_and_creates_no_binding(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _write_contract(root)
    state = tmp_path / "state"
    state.mkdir()
    code, payload = _run(root, _request(root, state, "change", expected_current="sha256:" + "0" * 64), "change")
    assert code == 1
    assert payload["reason"] == "accepted_current_conflict" and payload["producer_count"] == 0
    assert not control_root(state, "fixture-unit", "fixture").joinpath("binding.json").exists()


def test_change_rejects_selected_source_drift_after_execution(tmp_path: Path) -> None:
    root = _root(tmp_path)
    source = _source()
    source["checks"][0]["args"] = [  # type: ignore[index]
        "-c",
        "import json; from pathlib import Path; p=Path('.skillguard/contract-source.json'); d=json.loads(p.read_text()); d['checks'][1]['args']=['-c','print(1)']; p.write_text(json.dumps(d))",
    ]
    (root / ".skillguard").mkdir()
    (root / ".skillguard" / "contract-source.json").write_text(json.dumps(source), encoding="utf-8")
    state = tmp_path / "state"
    state.mkdir()
    code, payload = _run(root, _request(root, state, "change"), "change")
    assert code == 1
    assert payload["reason"] == "source_changed" and payload["producer_count"] == 2
    assert not control_root(state, "fixture-unit", "fixture").joinpath("current.json").exists()


def test_release_without_current_is_blocked_before_producer(tmp_path: Path) -> None:
    root = _root(tmp_path)
    source = _source()
    source["routes"].append({"route_id": "route:release", "choice_group": "operation", "when": [{"fact": "operation", "equals": "release"}], "step_ids": [], "obligation_ids": ["ob:leaf"]})  # type: ignore[union-attr]
    control = root / ".skillguard"
    control.mkdir()
    (control / "contract-source.json").write_text(json.dumps(source), encoding="utf-8")
    state = tmp_path / "state"
    state.mkdir()
    code, payload = _run(root, _request(root, state, "release"), "release")
    assert code == 1
    assert payload["status"] == "blocked"
    assert payload["producer_count"] == 0


def test_release_repairs_only_missing_referenced_leaf(tmp_path: Path) -> None:
    root = _root(tmp_path)
    source = _source()
    source["routes"].append({"route_id": "route:release", "choice_group": "operation", "when": [{"fact": "operation", "equals": "release"}], "step_ids": [], "obligation_ids": ["ob:leaf"]})  # type: ignore[union-attr]
    control = root / ".skillguard"
    control.mkdir()
    (control / "contract-source.json").write_text(json.dumps(source), encoding="utf-8")
    state = tmp_path / "state"
    state.mkdir()
    change_code, change_payload = _run(root, _request(root, state, "change"), "change")
    assert change_code == 0
    accepted_id = str(change_payload["accepted_id"])
    target = control_root(state, "fixture-unit", "fixture")
    next((target / "functions").glob("*.json")).unlink()
    release_code, release_payload = _run(
        root,
        _request(root, state, "release", expected_current=accepted_id),
        "release",
    )
    assert release_code == 0
    assert release_payload["producer_count"] == 1
    assert release_payload["run_count"] == 1 and release_payload["reused_count"] == 1


def test_release_blocks_tampered_aggregate_before_producer(tmp_path: Path) -> None:
    root = _root(tmp_path)
    source = _source()
    source["routes"].append({"route_id": "route:release", "choice_group": "operation", "when": [{"fact": "operation", "equals": "release"}], "step_ids": [], "obligation_ids": ["ob:leaf"]})  # type: ignore[union-attr]
    control = root / ".skillguard"
    control.mkdir()
    (control / "contract-source.json").write_text(json.dumps(source), encoding="utf-8")
    state = tmp_path / "state"
    state.mkdir()
    _, change_payload = _run(root, _request(root, state, "change"), "change")
    target = control_root(state, "fixture-unit", "fixture")
    result = next((target / "results").glob("*.json"))
    result.write_text(result.read_text(encoding="utf-8") + " ", encoding="utf-8")
    code, payload = _run(
        root,
        _request(root, state, "release", expected_current=str(change_payload["accepted_id"])),
        "release",
    )
    assert code == 1
    assert payload["reason"] == "evidence_invalid" and payload["producer_count"] == 0


def test_release_validates_file_artifact_before_producer_and_accepts_identity(tmp_path: Path) -> None:
    import hashlib

    root = _root(tmp_path)
    source = _source()
    source["routes"].append({"route_id": "route:release", "choice_group": "operation", "when": [{"fact": "operation", "equals": "release"}], "step_ids": [], "obligation_ids": ["ob:leaf"]})  # type: ignore[union-attr]
    (root / ".skillguard").mkdir()
    (root / ".skillguard" / "contract-source.json").write_text(json.dumps(source), encoding="utf-8")
    state = tmp_path / "state"
    state.mkdir()
    _, changed = _run(root, _request(root, state, "change"), "change")
    artifact = root / "release.bin"
    artifact.write_bytes(b"release")
    artifact_request = {"path": "release.bin", "kind": "file", "sha256": hashlib.sha256(b"release").hexdigest()}
    code, payload = _run(root, _request(root, state, "release", expected_current=str(changed["accepted_id"]), artifact=artifact_request), "release")
    assert code == 0 and payload["producer_count"] == 0

    bad = dict(artifact_request)
    bad["sha256"] = "0" * 64
    blocked_code, blocked = _run(root, _request(root, state, "release", expected_current=str(payload["accepted_id"]), artifact=bad), "release")
    assert blocked_code == 1 and blocked["reason"] == "artifact_hash_mismatch"
    assert blocked["producer_count"] == 0
