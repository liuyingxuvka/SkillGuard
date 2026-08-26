from __future__ import annotations

import json
import copy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / ".agents" / "skills" / "skillguard" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import checker_engine  # noqa: E402
from skillguard_v2.surface_inventory import (  # noqa: E402
    FULL_SURFACE_CATEGORIES,
    discover_full_source_surfaces,
    discover_public_source_surfaces,
    graduation_surface_findings,
    refresh_surface_inventory,
    surface_inventory_hash,
    _source_fingerprint,
    validate_command_surface_inventory,
    validate_full_surface_inventory,
    validate_reverse_surface_inventory,
    validate_surface_inventory,
)


LEGACY_ROUTE_GAP_COMMANDS = {
    "assurance-diagnostics",
    "build-global-registry",
    "capture-installation-receipt",
    "check-ai-judgment",
    "check-fixture-manifest",
    "check-global-registry",
    "check-json-schema",
    "check-report",
    "check-runtime-authority",
    "check-suite-contract",
    "check-suite-map",
    "check-workflow-report",
    "commands",
    "evidence-audit",
    "evidence-gc-apply",
    "evidence-gc-plan",
    "evidence-gc-purge",
    "init-suite",
    "init-target",
    "mark",
    "mark-portfolio-impact",
    "refresh-global-router",
    "scan-global-skills",
    "verify-installation-receipt",
    "verify-portfolio-impact-receipt",
    "write-report",
}

LEGACY_EMPTY_CHECK_COMMANDS = {
    name
    for name in checker_engine.COMMANDS
    if name not in {"commands", "route-task", "fixture-test", "detect-stale-evidence", "review-checker-change", "check-maintenance-record", "self-check"}
}


def _valid_inventory() -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "skillguard.surface_inventory.v1",
        "inventory_id": "inventory:test:surface",
        "target_skill_id": "demo",
        "source_kind": "target-native",
        "source_paths": ["src/entry.py"],
        "owner_ids": ["owner:demo:run"],
        "observed_surface_ids": ["command:run"],
        "rows": [
            {
                "surface_id": "command:run",
                "kind": "command",
                "name": "run",
                "disposition": "governed",
                "intent_id": "intent:run",
                "owner_id": "owner:demo:run",
                "route_id": "route:run",
                "function_id": "demo.run",
                "required_check_ids": ["check:demo:run"],
                "adequacy_check_ids": ["check:demo:surface"],
                "evidence_subject_ids": ["subject:demo:run"],
                "source_path": "src/entry.py",
            }
        ],
        "adequacy_check_ids": ["check:demo:surface"],
        "model_deepening_check_id": "check:demo:deepening",
        "claim_boundary": "The target owns surface meaning and check oracles.",
    }
    payload["inventory_hash"] = surface_inventory_hash(payload)
    return payload


def test_valid_target_inventory_is_currently_structurally_accepted() -> None:
    payload = _valid_inventory()
    assert validate_surface_inventory(
        payload,
        target_skill_id="demo",
        native_check_ids=["check:demo:surface", "check:demo:deepening", "check:demo:run"],
        model_deepening_check_id="check:demo:deepening",
    ) == ()


def test_missing_route_and_required_checks_are_not_synthesized() -> None:
    payload = _valid_inventory()
    row = payload["rows"][0]
    assert isinstance(row, dict)
    row["route_id"] = ""
    row["required_check_ids"] = []
    payload["inventory_hash"] = surface_inventory_hash(payload)
    codes = {finding.code for finding in validate_surface_inventory(payload)}
    assert "surface_row_missing_route" in codes
    assert "surface_row_missing_checks" in codes


def test_observed_denominator_is_required_and_cannot_be_empty() -> None:
    payload = _valid_inventory()
    payload["observed_surface_ids"] = []
    payload["inventory_hash"] = surface_inventory_hash(payload)
    codes = {finding.code for finding in validate_surface_inventory(payload)}
    assert "surface_inventory_observed_denominator_missing" in codes


def test_owner_registry_rejects_unknown_and_duplicate_owner_ids() -> None:
    payload = _valid_inventory()
    payload["owner_ids"] = ["owner:demo:run", "owner:demo:run"]
    row = payload["rows"][0]
    assert isinstance(row, dict)
    row["owner_id"] = "owner:demo:missing"
    payload["inventory_hash"] = surface_inventory_hash(payload)
    codes = {finding.code for finding in validate_surface_inventory(payload)}
    assert "surface_owner_id_duplicate" in codes
    assert "surface_row_owner_unknown" in codes


def test_missing_owner_is_fail_closed_even_after_hash_reseal() -> None:
    payload = _valid_inventory()
    row = payload["rows"][0]
    assert isinstance(row, dict)
    row.pop("owner_id")
    payload["inventory_hash"] = surface_inventory_hash(payload)
    codes = {finding.code for finding in validate_surface_inventory(payload)}
    assert "surface_row_missing_owner" in codes


def test_missing_owner_registry_is_fail_closed_by_default() -> None:
    payload = _valid_inventory()
    payload.pop("owner_ids")
    payload["inventory_hash"] = surface_inventory_hash(payload)
    codes = {finding.code for finding in validate_surface_inventory(payload)}
    assert "surface_owner_registry_missing" in codes


def test_row_name_is_required_even_when_the_inventory_hash_is_resealed() -> None:
    payload = _valid_inventory()
    row = payload["rows"][0]
    assert isinstance(row, dict)
    row["name"] = ""
    payload["inventory_hash"] = surface_inventory_hash(payload)
    codes = {finding.code for finding in validate_surface_inventory(payload)}
    assert "surface_row_missing_name" in codes


def test_self_inventory_closes_the_current_command_adequacy_gaps() -> None:
    path = ROOT / ".agents" / "skills" / "skillguard" / ".skillguard" / "surface-inventory.json"
    inventory = json.loads(path.read_text(encoding="utf-8"))
    findings = validate_command_surface_inventory(
        inventory,
        checker_engine.current_checker_command_surface(),
        checker_engine.current_route_entries(),
    )
    route_gaps = [item for item in findings if item.code == "surface_command_route_missing"]
    check_gaps = [item for item in findings if item.code == "surface_command_required_checks_empty"]
    assert len(checker_engine.COMMANDS) == 54
    assert route_gaps == []
    assert check_gaps == []
    assert all(item.code != "surface_command_denominator_mismatch" for item in findings)


def test_functional_closure_receipt_is_not_an_implementation_surface(tmp_path: Path) -> None:
    """Resealing author evidence must not enlarge or stale the source denominator."""

    target = tmp_path / ".agents" / "skills" / "demo"
    (target / ".skillguard").mkdir(parents=True)
    (target / "src").mkdir()
    (target / "src" / "entry.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    (target / ".skillguard" / "functional-closure.json").write_text(
        '{"source_fingerprint":"sha256:old"}\n', encoding="utf-8"
    )

    first = discover_full_source_surfaces(target)
    assert all(
        surface.source_path != ".skillguard/functional-closure.json"
        for surface in first.surfaces
    )
    first_fingerprint = first.discovery_fingerprint

    (target / ".skillguard" / "functional-closure.json").write_text(
        '{"source_fingerprint":"sha256:new"}\n', encoding="utf-8"
    )
    second = discover_full_source_surfaces(target)
    assert second.discovery_fingerprint == first_fingerprint


def test_current_command_reverse_denominator_binds_exact_metadata_for_every_command() -> None:
    """The current command surface is a closed, exact reverse binding.

    A green inventory must bind every public command to its current dispatch
    function, route, disposition, and target-native check set.  Checking only
    aggregate counts would allow a newly added command to borrow another
    command's row or route while the denominator still appears complete.
    """

    path = ROOT / ".agents" / "skills" / "skillguard" / ".skillguard" / "surface-inventory.json"
    inventory = json.loads(path.read_text(encoding="utf-8"))
    command_surface = checker_engine.current_checker_command_surface()
    route_by_command = {
        str(route["command_family"]): route
        for route in checker_engine.current_route_entries()
        if route.get("status") == "current"
    }
    rows_by_name = {
        str(row["name"]): row
        for row in inventory["rows"]
        if isinstance(row, dict) and row.get("kind") == "command"
    }

    assert len(command_surface) == len(checker_engine.COMMANDS) == 54
    assert {str(item["name"]) for item in command_surface} == set(rows_by_name)
    assert {"check-capability", "audit-capabilities", "check-source-sync"} <= rows_by_name.keys()

    for command in command_surface:
        name = str(command["name"])
        row = rows_by_name[name]
        route = route_by_command[name]
        assert row["surface_id"] == name
        assert row["name"] == name
        assert row["kind"] == "command"
        assert row["function_id"] == command["dispatch_function"]
        assert row["disposition"] == "governed"
        assert row["required_check_ids"] == command["required_checks"]
        assert row["route_id"] == route["route_id"]

    findings = validate_command_surface_inventory(
        inventory,
        command_surface,
        checker_engine.current_route_entries(),
    )
    assert findings == ()


def test_historical_underdeclaration_is_still_fail_closed() -> None:
    """Keep the missing-route and empty-check observations as a negative fixture."""

    path = ROOT / ".agents" / "skills" / "skillguard" / ".skillguard" / "surface-inventory.json"
    inventory = json.loads(path.read_text(encoding="utf-8"))
    commands = copy.deepcopy(checker_engine.current_checker_command_surface())
    routes = [
        row
        for row in checker_engine.current_route_entries()
        if row["command_family"] not in LEGACY_ROUTE_GAP_COMMANDS
    ]
    for row in commands:
        if row["name"] in LEGACY_EMPTY_CHECK_COMMANDS:
            row["required_checks"] = []
    findings = validate_command_surface_inventory(inventory, commands, routes)
    route_gaps = [item for item in findings if item.code == "surface_command_route_missing"]
    check_gaps = [item for item in findings if item.code == "surface_command_required_checks_empty"]
    assert len(route_gaps) == 26
    assert len(check_gaps) == 47


def test_self_inventory_negative_row_cannot_become_green_by_hash_reseal() -> None:
    path = ROOT / ".agents" / "skills" / "skillguard" / ".skillguard" / "surface-inventory.json"
    inventory = json.loads(path.read_text(encoding="utf-8"))
    inventory["rows"] = inventory["rows"][:-1]
    inventory["observed_surface_ids"] = inventory["observed_surface_ids"][:-1]
    inventory["inventory_hash"] = surface_inventory_hash(inventory)
    findings = validate_command_surface_inventory(
        inventory,
        checker_engine.current_checker_command_surface(),
        checker_engine.current_route_entries(),
    )
    assert any(item.code == "surface_command_denominator_mismatch" for item in findings)


def test_command_surface_duplicate_and_missing_dispatch_do_not_collapse_denominator() -> None:
    inventory = _valid_inventory()
    inventory["target_skill_id"] = "skillguard"
    inventory["rows"][0]["surface_id"] = "run"
    inventory["rows"][0]["name"] = "run"
    inventory["inventory_hash"] = surface_inventory_hash(inventory)
    commands = [
        {"name": "run", "dispatch_function": "demo.run", "required_checks": ["check:demo:run"]},
        {"name": "run", "dispatch_function": "demo.other", "required_checks": ["check:demo:run"]},
        {"name": "missing-dispatch", "required_checks": ["check:demo:run"]},
    ]
    findings = validate_command_surface_inventory(
        inventory,
        commands,
        [{"route_id": "route:run", "command_family": "run", "status": "current"}],
    )
    codes = {item.code for item in findings}
    assert "surface_command_name_duplicate" in codes
    assert "surface_dispatch_function_missing" in codes


def test_reverse_route_entry_with_missing_identity_is_not_silently_omitted() -> None:
    scan = discover_public_source_surfaces(
        ROOT / ".agents" / "skills" / "skillguard",
        command_surface=[],
        route_entries=[{"status": "current", "command_family": "missing-id"}],
    )
    assert any(item.code == "surface_route_identity_missing" for item in scan.findings)


def test_self_inventory_negative_route_and_check_mutation_is_visible() -> None:
    path = ROOT / ".agents" / "skills" / "skillguard" / ".skillguard" / "surface-inventory.json"
    inventory = json.loads(path.read_text(encoding="utf-8"))
    row = inventory["rows"][0]
    assert isinstance(row, dict)
    row["route_id"] = ""
    row["required_check_ids"] = []
    inventory["inventory_hash"] = surface_inventory_hash(inventory)
    findings = validate_command_surface_inventory(
        inventory,
        checker_engine.current_checker_command_surface(),
        checker_engine.current_route_entries(),
    )
    codes = {item.code for item in findings}
    assert "surface_command_route_mismatch" in codes
    assert "surface_row_missing_checks" in codes


def test_self_inventory_resealed_metadata_and_check_underdeclaration_is_visible() -> None:
    path = ROOT / ".agents" / "skills" / "skillguard" / ".skillguard" / "surface-inventory.json"
    inventory = json.loads(path.read_text(encoding="utf-8"))
    row = next(item for item in inventory["rows"] if item["surface_id"] == "plan-skill")
    row["name"] = "wrong-public-name"
    row["kind"] = "ui"
    row["function_id"] = "wrong.dispatch"
    row["disposition"] = "retired_proven"
    row["required_check_ids"] = ["check:self:select-function-route"]
    inventory["inventory_hash"] = surface_inventory_hash(inventory)
    findings = validate_command_surface_inventory(
        inventory,
        checker_engine.current_checker_command_surface(),
        checker_engine.current_route_entries(),
    )
    codes = {item.code for item in findings}
    assert "surface_command_name_mismatch" in codes
    assert "surface_command_kind_invalid" in codes
    assert "surface_command_function_mismatch" in codes
    assert "surface_command_disposition_invalid" in codes
    assert "surface_command_required_checks_mismatch" in codes


def test_graduation_surface_gate_accepts_explicit_self_model_obligation_mapping() -> None:
    target_root = ROOT / ".agents" / "skills" / "skillguard"
    compiled = json.loads(
        (target_root / ".skillguard" / "compiled-contract.json").read_text(encoding="utf-8")
    )
    profile = compiled["depth_profile"]
    findings = graduation_surface_findings(
        target_root,
        target_skill_id="skillguard",
        profile=profile,
        native_check_ids=profile["native_check_ids"],
        model_deepening_check_id=profile["model_deepening_check_id"],
    )
    assert findings == ()


def test_graduation_gate_requires_the_declaration_even_when_contract_is_current() -> None:
    target_root = ROOT / ".agents" / "skills" / "skillguard"
    findings = graduation_surface_findings(
        target_root,
        target_skill_id="skillguard",
        profile={"native_check_ids": ["check:deepening"]},
        native_check_ids=["check:deepening"],
        model_deepening_check_id="check:deepening",
    )
    assert [item.code for item in findings] == ["graduation_surface_inventory_missing"]


def _reverse_inventory() -> dict[str, object]:
    inventory = copy.deepcopy(
        json.loads(
            (
                ROOT
                / ".agents"
                / "skills"
                / "skillguard"
                / ".skillguard"
                / "surface-inventory.json"
            ).read_text(encoding="utf-8")
        )
    )
    scan = discover_public_source_surfaces(
        ROOT / ".agents" / "skills" / "skillguard",
        command_surface=checker_engine.current_checker_command_surface(),
        route_entries=checker_engine.current_route_entries(),
        command_handlers=checker_engine.COMMANDS,
    )
    assert scan.findings == ()
    rows = []
    for surface in scan.surfaces:
        rows.append(
            {
                **surface.to_dict(),
                "disposition": "governed",
                "intent_id": f"intent:reverse:{surface.surface_id}",
                "owner_id": "owner:self:reverse-surface",
                "required_check_ids": ["check:self:surface-inventory"],
                "adequacy_check_ids": ["check:self:surface-inventory"],
                "evidence_subject_ids": [f"subject:reverse:{surface.surface_id}"],
                "symbol": surface.function_id,
            }
        )
    inventory["reverse_surfaces"] = rows
    inventory["reverse_surface_ids"] = [surface.surface_id for surface in scan.surfaces]
    inventory["inventory_hash"] = surface_inventory_hash(inventory)
    return inventory


def test_reverse_scan_discovers_entry_scripts_dispatch_functions_and_routes() -> None:
    scan = discover_public_source_surfaces(
        ROOT / ".agents" / "skills" / "skillguard",
        command_surface=checker_engine.current_checker_command_surface(),
        route_entries=checker_engine.current_route_entries(),
        command_handlers=checker_engine.COMMANDS,
    )
    assert scan.findings == ()
    kinds = {kind: sum(surface.kind == kind for surface in scan.surfaces) for kind in ("script", "dispatch", "route")}
    assert kinds["script"] >= 1
    assert kinds["dispatch"] == len(checker_engine.COMMANDS)
    assert kinds["route"] == len(checker_engine.current_route_entries())


def test_reverse_inventory_passes_only_when_every_discovered_surface_is_bound() -> None:
    inventory = _reverse_inventory()
    findings = validate_reverse_surface_inventory(
        inventory,
        target_root=ROOT / ".agents" / "skills" / "skillguard",
        command_surface=checker_engine.current_checker_command_surface(),
        route_entries=checker_engine.current_route_entries(),
        command_handlers=checker_engine.COMMANDS,
    )
    assert findings == ()


def test_reverse_inventory_fails_closed_on_live_orphan_surface() -> None:
    inventory = _reverse_inventory()
    rows = inventory["reverse_surfaces"]
    assert isinstance(rows, list)
    removed = rows.pop()
    assert isinstance(removed, dict)
    inventory["reverse_surface_ids"] = [row["surface_id"] for row in rows]
    inventory["inventory_hash"] = surface_inventory_hash(inventory)
    findings = validate_reverse_surface_inventory(
        inventory,
        target_root=ROOT / ".agents" / "skills" / "skillguard",
        command_surface=checker_engine.current_checker_command_surface(),
        route_entries=checker_engine.current_route_entries(),
        command_handlers=checker_engine.COMMANDS,
    )
    assert any(item.code == "surface_reverse_unmapped" for item in findings)


def test_reverse_inventory_allows_only_explicit_typed_retirement_for_old_surface() -> None:
    inventory = _reverse_inventory()
    rows = inventory["reverse_surfaces"]
    assert isinstance(rows, list)
    rows.append(
        {
            "surface_id": "script:old-entry.py",
            "kind": "script",
            "name": "scripts/old-entry.py",
            "source_path": "scripts/old-entry.py",
            "function_id": "old_entry.main",
            "route_id": "entry:scripts/old-entry.py",
            "disposition": "retired_proven",
            "disposition_reason": "Removed in the current author source; retained only as an explicit historical disposition.",
            "intent_id": "intent:reverse:old-entry",
            "owner_id": "owner:self:reverse-surface",
            "required_check_ids": ["check:self:surface-inventory"],
            "adequacy_check_ids": ["check:self:surface-inventory"],
            "evidence_subject_ids": ["subject:reverse:old-entry"],
        }
    )
    inventory["reverse_surface_ids"] = [row["surface_id"] for row in rows]
    inventory["inventory_hash"] = surface_inventory_hash(inventory)
    findings = validate_reverse_surface_inventory(
        inventory,
        target_root=ROOT / ".agents" / "skills" / "skillguard",
        command_surface=checker_engine.current_checker_command_surface(),
        route_entries=checker_engine.current_route_entries(),
        command_handlers=checker_engine.COMMANDS,
    )
    assert not any(item.code == "surface_reverse_orphan_live" for item in findings)


def test_reverse_scan_reports_unresolved_dispatch_source() -> None:
    scan = discover_public_source_surfaces(
        ROOT / ".agents" / "skills" / "skillguard",
        command_surface=[
            {
                "name": "fake",
                "dispatch_function": "missing_module.fake",
            }
        ],
        route_entries=[],
    )
    assert any(item.code == "surface_dispatch_source_missing" for item in scan.findings)


def test_reverse_scan_does_not_collapse_duplicate_route_registry_entries() -> None:
    routes = [
        {
            "route_id": "route:duplicate",
            "command_family": "run",
            "status": "current",
        },
        {
            "route_id": "route:duplicate",
            "command_family": "run",
            "status": "current",
        },
    ]
    scan = discover_public_source_surfaces(
        ROOT / ".agents" / "skills" / "skillguard",
        command_surface=[],
        route_entries=routes,
    )
    codes = {item.code for item in scan.findings}
    assert "surface_route_identity_duplicate" in codes
    assert "surface_route_command_duplicate" in codes


def _full_fixture_root(tmp_path: Path) -> Path:
    """Create a tiny production tree with every reverse-scan class.

    The fixture intentionally contains no tests or evidence directories: those
    are consumers of the target contract, not part of the implementation
    denominator.  The source names exercise the scanner's structural lanes;
    the validator still requires the target to provide the semantic mapping.
    """

    package = tmp_path / "pkg"
    package.mkdir()
    (package / "entry.py").write_text(
        """
from pathlib import Path

__all__ = ["public_api"]

def public_api(value):
    return value

def install_and_recover(path):
    Path(path).write_text("current")
    try:
        return confirm_action(reject_invalid(path))
    except ValueError:
        cleanup(path)
        raise

def reject_invalid(path):
    return path

def confirm_action(path):
    return path

def cleanup(path):
    Path(path).unlink(missing_ok=True)

def _component_helper(path):
    return path

if __name__ == "__main__":
    install_and_recover("state.txt")
""".lstrip(),
        encoding="utf-8",
    )
    (package / "pyproject.toml").write_text('[tool.fixture]\nenabled = true\n', encoding="utf-8")
    (package / "SKILL.md").write_text("# Fixture skill\n", encoding="utf-8")
    (package / "templates").mkdir()
    (package / "templates" / "prompt.md").write_text("confirm\n", encoding="utf-8")
    return tmp_path


def test_full_source_scan_is_deterministic_and_observes_reverse_surface_classes(tmp_path: Path) -> None:
    root = _full_fixture_root(tmp_path)
    first = discover_full_source_surfaces(root)
    second = discover_full_source_surfaces(root)
    assert first.findings == ()
    assert first.to_dict() == second.to_dict()
    assert first.discovery_fingerprint == second.discovery_fingerprint
    kinds = {surface.kind for surface in first.surfaces}
    assert {"api", "export", "script", "config", "template", "effect", "ui", "fault", "recovery", "component"} <= kinds
    assert all(surface.review_group_id for surface in first.surfaces)
    assert all(surface.review_granularity in {"surface", "component"} for surface in first.surfaces)
    assert any(surface.review_granularity == "component" for surface in first.surfaces)
    assert any(surface.review_granularity == "surface" for surface in first.surfaces)
    assert len({surface.review_group_id for surface in first.surfaces}) < len(first.surfaces)
    component_groups = {
        surface.source_path: {
            item.review_group_id
            for item in first.surfaces
            if item.source_path == surface.source_path
            and item.review_granularity == "component"
        }
        for surface in first.surfaces
        if surface.review_granularity == "component"
    }
    assert all(len(group_ids) == 1 for group_ids in component_groups.values())


def test_private_only_source_file_gets_one_explicit_component_surface(tmp_path: Path) -> None:
    """Private implementation is grouped as a component, never omitted."""

    root = tmp_path / "target"
    package = root / "pkg"
    package.mkdir(parents=True)
    (package / "internal.py").write_text(
        "def _resolve_current(value):\n    return value\n\n"
        "def _recover_current(value):\n    return _resolve_current(value)\n",
        encoding="utf-8",
    )
    scan = discover_full_source_surfaces(root)
    assert scan.findings == ()
    components = [surface for surface in scan.surfaces if surface.kind == "component"]
    assert len(components) == 1
    component = components[0]
    assert component.surface_id == "component:pkg/internal.py"
    assert component.component_members == ("_recover_current", "_resolve_current")
    assert component.review_granularity == "component"


def test_component_member_removal_is_not_hidden_by_inventory_hash_reseal(tmp_path: Path) -> None:
    root = _full_fixture_root(tmp_path)
    inventory, checks = _complete_full_inventory(root)
    component = next(
        row for row in inventory["full_surfaces"] if row["kind"] == "component"
    )
    assert isinstance(component, dict)
    component["component_members"] = ["_different_private_member"]
    inventory["inventory_hash"] = surface_inventory_hash(inventory)
    codes = {
        item.code
        for item in validate_full_surface_inventory(
            inventory,
            target_root=root,
            native_check_ids=checks,
            model_deepening_check_id="check:fixture:deepening",
        )
    }
    assert "full_surface_component_members_mismatch" in codes


def test_full_source_scan_excludes_generated_work_artifacts(tmp_path: Path) -> None:
    root = _full_fixture_root(tmp_path)
    work = root / "work" / "verification"
    work.mkdir(parents=True)
    (work / "launcher-report.json").write_text(
        '{"status":"passed"}\n',
        encoding="utf-8",
    )
    (work / "diagnostic.md").write_text("transient output\n", encoding="utf-8")

    scan = discover_full_source_surfaces(root)

    assert scan.findings == ()
    assert all(not surface.source_path.startswith("work/") for surface in scan.surfaces)


def test_policy_review_record_does_not_change_reverse_source_identity(tmp_path: Path) -> None:
    policy = tmp_path / "public-export-policy.json"
    policy.write_text(
        json.dumps(
            {
                "blocked_extensions": [".key"],
                "large_text_review_records": [
                    {
                        "asset_path": ".skillguard/surface-inventory.json",
                        "asset_sha256": "sha256:" + "1" * 64,
                        "status": "passed",
                        "review_scope": "generated inventory only",
                    }
                ],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    first = _source_fingerprint(policy)
    payload = json.loads(policy.read_text(encoding="utf-8"))
    payload["large_text_review_records"][0]["asset_sha256"] = "sha256:" + "2" * 64
    policy.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    assert _source_fingerprint(policy) == first


def test_policy_semantic_change_still_changes_reverse_source_identity(tmp_path: Path) -> None:
    policy = tmp_path / "public-export-policy.json"
    policy.write_text(
        json.dumps(
            {
                "blocked_extensions": [".key"],
                "large_text_review_records": [],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    first = _source_fingerprint(policy)
    payload = json.loads(policy.read_text(encoding="utf-8"))
    payload["blocked_extensions"].append(".pem")
    policy.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    assert _source_fingerprint(policy) != first


def test_runtime_reports_are_evidence_not_reverse_implementation_surfaces(tmp_path: Path) -> None:
    root = _full_fixture_root(tmp_path)
    first = discover_full_source_surfaces(root)
    reports = root / ".skillguard" / "reports"
    reports.mkdir(parents=True)
    (reports / "self-check.json").write_text("{\"decision\": \"pass\"}\n", encoding="utf-8")
    (reports / "check-depth.json").write_text("{\"decision\": \"pass\"}\n", encoding="utf-8")
    second = discover_full_source_surfaces(root)
    assert second.findings == ()
    assert second.to_dict() == first.to_dict()
    assert not any(surface.source_path.startswith(".skillguard/reports/") for surface in second.surfaces)


def test_full_source_scan_discovers_literal_cli_options_without_line_level_rows(tmp_path: Path) -> None:
    root = _full_fixture_root(tmp_path)
    entry = root / "pkg" / "entry.py"
    entry.write_text(
        entry.read_text(encoding="utf-8")
        + "\n\ndef run(argv):\n"
        + "    parser = object()\n"
        + "    parser.add_argument('--input')\n"
        + "    parser.add_argument('--output', '--out')\n"
        + "    return argv\n",
        encoding="utf-8",
    )
    scan = discover_full_source_surfaces(
        root,
        command_surface=[{"name": "run", "dispatch_function": "entry.run"}],
        route_entries=[{"route_id": "route:run", "command_family": "run", "status": "current"}],
    )
    assert scan.findings == ()
    option_ids = {surface.surface_id for surface in scan.surfaces if surface.kind == "option"}
    assert option_ids == {
        "option:run:--input",
        "option:run:--output",
        "option:run:--out",
    }
    assert all(surface.review_granularity == "surface" for surface in scan.surfaces if surface.kind == "option")


def test_full_source_scan_uses_native_handler_identity_for_imported_cli_options(tmp_path: Path) -> None:
    root = _full_fixture_root(tmp_path)
    entry = root / "pkg" / "entry.py"
    entry.write_text(
        entry.read_text(encoding="utf-8")
        + "\n\ndef run(argv):\n"
        + "    parser = object()\n"
        + "    parser.add_argument('--native')\n"
        + "    return argv\n",
        encoding="utf-8",
    )

    import importlib.util

    spec = importlib.util.spec_from_file_location("entry", entry)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    scan = discover_full_source_surfaces(
        root,
        command_surface=[{"name": "run", "dispatch_function": "checker_engine.run"}],
        route_entries=[{"route_id": "route:run", "command_family": "run", "status": "current"}],
        command_handlers={"run": module.run},
    )
    option = next(surface for surface in scan.surfaces if surface.kind == "option")
    assert option.source_path == "pkg/entry.py"


def test_derived_component_surface_ids_do_not_encode_source_line_numbers(tmp_path: Path) -> None:
    root = _full_fixture_root(tmp_path)
    before = discover_full_source_surfaces(root)
    entry = root / "pkg" / "entry.py"
    entry.write_text("# harmless line insertion\n" + entry.read_text(encoding="utf-8"), encoding="utf-8")
    after = discover_full_source_surfaces(root)
    derived = {"effect", "installer", "ui", "fault", "recovery", "provider"}
    before_ids = {surface.surface_id for surface in before.surfaces if surface.kind in derived}
    after_ids = {surface.surface_id for surface in after.surfaces if surface.kind in derived}
    assert before_ids == after_ids


def test_full_source_scan_reports_malformed_production_source(tmp_path: Path) -> None:
    root = _full_fixture_root(tmp_path)
    (root / "pkg" / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    scan = discover_full_source_surfaces(root)
    assert any(item.code == "full_surface_source_parse_failed" for item in scan.findings)


def _complete_full_inventory(root: Path) -> tuple[dict[str, object], tuple[str, ...]]:
    scan = discover_full_source_surfaces(root)
    assert scan.findings == ()
    owner = "owner:fixture:surface"
    native_checks = (
        "check:fixture:native",
        "check:fixture:adequacy",
        "check:fixture:failure",
        "check:fixture:recovery",
        "check:fixture:deepening",
    )
    model_obligation_ids_by_surface, model_obligations = _fixture_model_obligation_bindings(
        scan.surfaces
    )
    rows: list[dict[str, object]] = []
    for surface in scan.surfaces:
        rows.append(
            {
                **surface.to_dict(),
                "disposition": "governed",
                "intent_id": f"intent:fixture:{surface.surface_id}",
                "owner_id": owner,
                "obligation_ids": [f"obligation:fixture:{surface.surface_id}"],
                "model_obligation_ids": model_obligation_ids_by_surface[surface.surface_id],
                "required_check_ids": [native_checks[0]],
                "adequacy_check_ids": list(native_checks[1:]),
                "execution_owner_ids": [owner],
                "evidence_subject_ids": [f"subject:fixture:{surface.surface_id}"],
                "lifecycle": ["happy", "failure", "recovery"],
                "consumer_exposure": "target-owned",
                "write_authority": "target-owned",
            }
        )
    inventory: dict[str, object] = {
        "schema_version": "skillguard.surface_inventory.v1",
        "inventory_id": "inventory:fixture:full",
        "target_skill_id": "fixture",
        "source_kind": "target-native",
        "source_paths": list(scan.source_paths),
        "owner_ids": [owner],
        "full_surface_ids": [surface.surface_id for surface in scan.surfaces],
        "current_obligation_ids": [
            str(row["obligation_id"]) for row in model_obligations
        ],
        "model_obligations": model_obligations,
        "full_surfaces": rows,
        "full_discovery_fingerprint": scan.discovery_fingerprint,
        "surface_category_dispositions": {
            category: {
                "disposition": "governed" if any(
                    _full_category(surface.kind) == category for surface in scan.surfaces
                ) else "not_applicable_proven",
                "reason": "fixture source observation is explicit",
                "proof_ref": f"proof:fixture:category:{category}",
            }
            for category in FULL_SURFACE_CATEGORIES
        },
        "claim_boundary": "Fixture source observation is not a domain correctness oracle.",
    }
    inventory["inventory_hash"] = surface_inventory_hash(inventory)
    return inventory, native_checks


def _fixture_model_obligation_bindings(
    surfaces: object,
) -> tuple[dict[str, list[str]], list[dict[str, object]]]:
    """Build an explicit fixture-only model-to-surface relation.

    Component observations intentionally share one model-obligation row.  The
    production target must author its own relation; this helper only gives
    validator fixtures a target-owned, deterministic map.
    """

    ids_by_surface: dict[str, list[str]] = {}
    surface_ids_by_obligation: dict[str, list[str]] = {}
    for surface in surfaces:
        surface_id = str(surface.surface_id)
        binding_key = (
            str(surface.review_group_id)
            if surface.review_granularity == "component"
            else surface_id
        )
        obligation_id = f"model-obligation:fixture:{binding_key}"
        ids_by_surface[surface_id] = [obligation_id]
        surface_ids_by_obligation.setdefault(obligation_id, []).append(surface_id)
    model_obligations = [
        {
            "obligation_id": obligation_id,
            "disposition": "governed",
            "surface_ids": surface_ids,
            "reason": "Fixture model obligation is explicitly bound to its observed implementation surface set.",
            "proof_ref": f"proof:fixture:model-obligation:{obligation_id}",
        }
        for obligation_id, surface_ids in surface_ids_by_obligation.items()
    ]
    return ids_by_surface, model_obligations


def _full_category(kind: str) -> str:
    return {"option": "command", "export": "api", "prompt": "template"}.get(kind, kind)


def test_full_inventory_requires_semantic_adequacy_and_fresh_bindings(tmp_path: Path) -> None:
    root = _full_fixture_root(tmp_path)
    inventory, checks = _complete_full_inventory(root)
    assert validate_full_surface_inventory(
        inventory,
        target_root=root,
        native_check_ids=checks,
        model_deepening_check_id="check:fixture:deepening",
    ) == ()

    row = inventory["full_surfaces"][0]
    assert isinstance(row, dict)
    row["adequacy_check_ids"] = ["check:fixture:adequacy"]
    inventory["inventory_hash"] = surface_inventory_hash(inventory)
    codes = {
        item.code
        for item in validate_full_surface_inventory(
            inventory,
            target_root=root,
            native_check_ids=checks,
            model_deepening_check_id="check:fixture:deepening",
        )
    }
    assert "full_surface_row_adequacy_shallow" in codes
    assert "full_surface_row_deepening_missing" in codes


def test_full_inventory_requires_review_group_metadata(tmp_path: Path) -> None:
    root = _full_fixture_root(tmp_path)
    inventory, checks = _complete_full_inventory(root)
    row = inventory["full_surfaces"][0]
    assert isinstance(row, dict)
    row.pop("review_group_id")
    inventory["inventory_hash"] = surface_inventory_hash(inventory)
    codes = {
        item.code
        for item in validate_full_surface_inventory(
            inventory,
            target_root=root,
            native_check_ids=checks,
            model_deepening_check_id="check:fixture:deepening",
        )
    }
    assert "full_surface_row_review_group_missing" in codes


def test_full_inventory_requires_explicit_current_model_obligation_denominator(tmp_path: Path) -> None:
    root = _full_fixture_root(tmp_path)
    inventory, checks = _complete_full_inventory(root)
    inventory.pop("current_obligation_ids")
    inventory.pop("model_obligations")
    inventory["inventory_hash"] = surface_inventory_hash(inventory)
    codes = {
        item.code
        for item in validate_full_surface_inventory(
            inventory,
            target_root=root,
            native_check_ids=checks,
            model_deepening_check_id="check:fixture:deepening",
        )
    }
    assert "full_surface_model_obligation_denominator_missing" in codes
    assert "full_surface_model_obligations_missing" in codes


def test_full_inventory_rejects_missing_surface_model_obligation_binding(tmp_path: Path) -> None:
    root = _full_fixture_root(tmp_path)
    inventory, checks = _complete_full_inventory(root)
    row = inventory["full_surfaces"][0]
    assert isinstance(row, dict)
    row.pop("model_obligation_ids")
    inventory["inventory_hash"] = surface_inventory_hash(inventory)
    codes = {
        item.code
        for item in validate_full_surface_inventory(
            inventory,
            target_root=root,
            native_check_ids=checks,
            model_deepening_check_id="check:fixture:deepening",
        )
    }
    assert "full_surface_row_model_obligation_missing" in codes


def test_full_inventory_rejects_one_way_model_obligation_binding(tmp_path: Path) -> None:
    root = _full_fixture_root(tmp_path)
    inventory, checks = _complete_full_inventory(root)
    rows = inventory["full_surfaces"]
    assert isinstance(rows, list)
    row = rows[0]
    assert isinstance(row, dict)
    obligation_id = row["model_obligation_ids"][0]
    model_row = next(
        item
        for item in inventory["model_obligations"]
        if item["obligation_id"] == obligation_id
    )
    other_surface_id = rows[1]["surface_id"]
    model_row["surface_ids"] = [other_surface_id]
    inventory["inventory_hash"] = surface_inventory_hash(inventory)
    codes = {
        item.code
        for item in validate_full_surface_inventory(
            inventory,
            target_root=root,
            native_check_ids=checks,
            model_deepening_check_id="check:fixture:deepening",
        )
    }
    assert "full_surface_model_obligation_reverse_mismatch" in codes


def test_full_inventory_rejects_unknown_model_obligation_reference(tmp_path: Path) -> None:
    root = _full_fixture_root(tmp_path)
    inventory, checks = _complete_full_inventory(root)
    row = inventory["full_surfaces"][0]
    assert isinstance(row, dict)
    row["model_obligation_ids"] = ["model-obligation:fixture:unknown"]
    inventory["inventory_hash"] = surface_inventory_hash(inventory)
    codes = {
        item.code
        for item in validate_full_surface_inventory(
            inventory,
            target_root=root,
            native_check_ids=checks,
            model_deepening_check_id="check:fixture:deepening",
        )
    }
    assert "full_surface_row_model_obligation_unknown" in codes


def test_full_inventory_requires_component_group_model_obligation_closure(tmp_path: Path) -> None:
    root = _full_fixture_root(tmp_path)
    inventory, checks = _complete_full_inventory(root)
    rows = inventory["full_surfaces"]
    assert isinstance(rows, list)
    component_rows = [
        row
        for row in rows
        if row["review_granularity"] == "component"
    ]
    assert len(component_rows) >= 2
    first_group = component_rows[0]["review_group_id"]
    same_group = [row for row in component_rows if row["review_group_id"] == first_group]
    assert len(same_group) >= 2
    other_row = next(
        row for row in rows if row["review_group_id"] != first_group
    )
    same_group[1]["model_obligation_ids"] = list(other_row["model_obligation_ids"])
    inventory["inventory_hash"] = surface_inventory_hash(inventory)
    codes = {
        item.code
        for item in validate_full_surface_inventory(
            inventory,
            target_root=root,
            native_check_ids=checks,
            model_deepening_check_id="check:fixture:deepening",
        )
    }
    assert "full_surface_component_model_obligation_mismatch" in codes


def test_full_inventory_fails_closed_on_underdeclaration_but_allows_proved_internal_helper(tmp_path: Path) -> None:
    root = _full_fixture_root(tmp_path)
    inventory, checks = _complete_full_inventory(root)
    rows = inventory["full_surfaces"]
    assert isinstance(rows, list)
    removed = rows.pop()
    assert isinstance(removed, dict)
    inventory["full_surface_ids"] = [row["surface_id"] for row in rows]
    rows[0]["disposition"] = "internal_proven"
    rows[0]["disposition_reason"] = "explicit helper proof"
    rows[0]["disposition_proof_ref"] = "proof:fixture:helper"
    inventory["inventory_hash"] = surface_inventory_hash(inventory)
    codes = {
        item.code
        for item in validate_full_surface_inventory(
            inventory,
            target_root=root,
            native_check_ids=checks,
            model_deepening_check_id="check:fixture:deepening",
        )
    }
    assert "full_surface_discovery_denominator_mismatch" in codes
    assert "full_surface_unmapped" in codes
    assert "full_surface_live_disposition_invalid" not in codes

    rows[0].pop("disposition_proof_ref")
    inventory["inventory_hash"] = surface_inventory_hash(inventory)
    codes = {
        item.code
        for item in validate_full_surface_inventory(
            inventory,
            target_root=root,
            native_check_ids=checks,
            model_deepening_check_id="check:fixture:deepening",
        )
    }
    assert "full_surface_row_disposition_proof_missing" in codes


def _refresh_fixture_root(tmp_path: Path) -> tuple[Path, list[dict[str, object]], list[dict[str, object]]]:
    """Create a small target with command, reverse, and full projections."""

    root = tmp_path / "target"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "checker_engine.py").write_text(
        """
def run(value):
    return value

def main():
    return run(1)

if __name__ == "__main__":
    main()
""".lstrip(),
        encoding="utf-8",
    )
    commands: list[dict[str, object]] = [
        {
            "name": "run",
            "dispatch_function": "checker_engine.run",
            "required_checks": ["check:fixture:native"],
        }
    ]
    routes: list[dict[str, object]] = [
        {"route_id": "route:run", "command_family": "run", "status": "current"}
    ]
    return root, commands, routes


def _refresh_fixture_inventory(
    root: Path,
    commands: list[dict[str, object]],
    routes: list[dict[str, object]],
) -> dict[str, object]:
    public_scan = discover_public_source_surfaces(
        root,
        command_surface=commands,
        route_entries=routes,
    )
    full_scan = discover_full_source_surfaces(
        root,
        command_surface=commands,
        route_entries=routes,
    )
    assert public_scan.findings == ()
    assert full_scan.findings == ()
    owner = "owner:fixture:surface"
    checks = [
        "check:fixture:native",
        "check:fixture:adequacy",
        "check:fixture:failure",
        "check:fixture:recovery",
        "check:fixture:deepening",
    ]
    model_obligation_ids_by_surface, model_obligations = _fixture_model_obligation_bindings(
        full_scan.surfaces
    )

    def semantic_row(surface: object, *, full: bool = False) -> dict[str, object]:
        assert hasattr(surface, "to_dict")
        row = {
            **surface.to_dict(),
            "disposition": "governed",
            "intent_id": f"intent:fixture:{surface.surface_id}",
            "owner_id": owner,
            "required_check_ids": [checks[0]],
            "adequacy_check_ids": checks[1:],
            "evidence_subject_ids": [f"subject:fixture:{surface.surface_id}"],
        }
        if full:
            row.update(
                {
                    "obligation_ids": [f"obligation:fixture:{surface.surface_id}"],
                    "model_obligation_ids": model_obligation_ids_by_surface[surface.surface_id],
                    "execution_owner_ids": [owner],
                    "lifecycle_phase": "runtime",
                    "consumer_exposure": "target-owned",
                    "write_authority": "target-owned",
                }
            )
        return row

    command_rows = []
    for command in commands:
        name = str(command["name"])
        surface = next(item for item in full_scan.surfaces if item.surface_id == f"command:{name}")
        command_rows.append({**semantic_row(surface), "surface_id": name})
    categories = {
        category: {
            "disposition": "governed"
            if any(_full_category(surface.kind) == category for surface in full_scan.surfaces)
            else "not_applicable_proven",
            "reason": "fixture category is explicitly accounted for",
            "proof_ref": f"proof:fixture:{category}",
        }
        for category in FULL_SURFACE_CATEGORIES
    }
    inventory: dict[str, object] = {
        "schema_version": "skillguard.surface_inventory.v1",
        "inventory_id": "inventory:fixture:refresh",
        "target_skill_id": "fixture",
        "source_kind": "target-native",
        "source_paths": list(full_scan.source_paths),
        "owner_ids": [owner],
        "observed_surface_ids": [str(command["name"]) for command in commands],
        "rows": command_rows,
        "reverse_surface_ids": [surface.surface_id for surface in public_scan.surfaces],
        "reverse_surfaces": [semantic_row(surface) for surface in public_scan.surfaces],
        "full_surface_ids": [surface.surface_id for surface in full_scan.surfaces],
        "full_surfaces": [semantic_row(surface, full=True) for surface in full_scan.surfaces],
        "current_obligation_ids": [
            str(row["obligation_id"]) for row in model_obligations
        ],
        "model_obligations": model_obligations,
        "full_discovery_fingerprint": full_scan.discovery_fingerprint,
        "surface_category_dispositions": categories,
        "adequacy_check_ids": checks[1:],
        "model_deepening_check_id": checks[-1],
        "claim_boundary": "Fixture structural refresh never supplies target meaning.",
    }
    inventory["inventory_hash"] = surface_inventory_hash(inventory)
    return inventory


def test_refresh_writer_updates_source_identity_only_and_preserves_target_meaning(tmp_path: Path) -> None:
    root, commands, routes = _refresh_fixture_root(tmp_path)
    inventory = _refresh_fixture_inventory(root, commands, routes)
    output = root / ".skillguard" / "surface-inventory.json"
    output.parent.mkdir(parents=True)
    output.write_text(json.dumps(inventory, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    before = json.loads(output.read_text(encoding="utf-8"))
    before_intents = {
        row["surface_id"]: row["intent_id"]
        for row in before["full_surfaces"]
    }
    source = root / "scripts" / "checker_engine.py"
    source.write_text("# source-only identity change\n" + source.read_text(encoding="utf-8"), encoding="utf-8")
    result = refresh_surface_inventory(
        before,
        target_root=root,
        command_surface=commands,
        route_entries=routes,
        output_path=output,
    )
    assert result["decision"] == "pass"
    assert result["written"] is True
    refreshed = json.loads(output.read_text(encoding="utf-8"))
    assert {
        row["surface_id"]: row["intent_id"]
        for row in refreshed["full_surfaces"]
    } == before_intents
    assert refreshed["full_discovery_fingerprint"] != before["full_discovery_fingerprint"]
    assert any(
        row["source_fingerprint"] != old["source_fingerprint"]
        for row, old in zip(refreshed["full_surfaces"], before["full_surfaces"])
        if row["source_path"] == "scripts/checker_engine.py"
    )


def test_refresh_writer_fails_closed_on_surface_set_change_without_writing(tmp_path: Path) -> None:
    root, commands, routes = _refresh_fixture_root(tmp_path)
    inventory = _refresh_fixture_inventory(root, commands, routes)
    output = root / ".skillguard" / "surface-inventory.json"
    output.parent.mkdir(parents=True)
    output.write_text(json.dumps(inventory, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    before_bytes = output.read_bytes()
    source = root / "scripts" / "checker_engine.py"
    source.write_text(
        source.read_text(encoding="utf-8")
        + "\n\ndef newly_exposed_public_surface(value):\n    return value\n",
        encoding="utf-8",
    )
    result = refresh_surface_inventory(
        inventory,
        target_root=root,
        command_surface=commands,
        route_entries=routes,
        output_path=output,
    )
    assert result["decision"] == "blocked"
    assert result["written"] is False
    assert result["surface_set_changed"] is True
    assert any(
        item["code"] == "surface_inventory_refresh_surface_set_changed"
        for item in result["findings"]
    )
    assert output.read_bytes() == before_bytes


def test_refresh_writer_does_not_fill_missing_intent_from_function_name(tmp_path: Path) -> None:
    root, commands, routes = _refresh_fixture_root(tmp_path)
    inventory = _refresh_fixture_inventory(root, commands, routes)
    missing = copy.deepcopy(inventory)
    row = missing["full_surfaces"][0]
    assert isinstance(row, dict)
    row.pop("intent_id")
    missing["inventory_hash"] = surface_inventory_hash(missing)
    result = refresh_surface_inventory(
        missing,
        target_root=root,
        command_surface=commands,
        route_entries=routes,
    )
    assert result["decision"] == "blocked"
    assert result["written"] is False
    assert any(
        item["code"] == "surface_inventory_refresh_semantic_field_missing"
        and item["path"].endswith(".intent_id")
        for item in result["findings"]
    )
    assert result["inventory"] is None
