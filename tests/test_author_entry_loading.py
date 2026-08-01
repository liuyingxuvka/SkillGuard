from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / ".agents" / "skills" / "skillguard"
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import checker_engine  # noqa: E402
import generate_route_index  # noqa: E402


def _select(task: str, hint: str = ""):
    blockers: list[str] = []
    structured: list[dict] = []
    selected, candidates = checker_engine.select_route_task_decision(
        task, hint, blockers, structured
    )
    return selected, candidates, blockers, structured


def test_every_current_route_has_complete_capsule_and_reference():
    required = {
        "applicability_predicates",
        "forbidden_predicates",
        "required_input_fields",
        "read_authority",
        "write_authority",
        "first_command",
        "next_reference",
        "conditional_references",
        "load_order",
        "claim_boundary",
    }
    for row in checker_engine.current_route_entries():
        assert not (required - row.keys()), row["route_id"]
        assert (SKILL_ROOT / row["next_reference"]).is_file(), row["route_id"]
        assert row["required_input_fields"]
        assert row["applicability_predicates"]
        assert row["forbidden_predicates"]


def test_route_index_is_exact_current_projection():
    expected = generate_route_index.canonical_bytes(
        generate_route_index.build_route_index()
    )
    actual = (
        SKILL_ROOT / "references" / "skillguard-route-index.json"
    ).read_bytes()

    assert actual == expected
    assert generate_route_index.build_route_index()["selection_contract"] == {
        "explicit_route_id_allowed": True,
        "declared_predicate_match_allowed": True,
        "keyword_score_allowed": False,
        "zero_match_terminal": "blocked",
        "many_match_terminal": "blocked",
        "fallback_allowed": False,
    }


def test_selected_route_load_graph_is_narrow_and_complete():
    index = generate_route_index.build_route_index()
    routes = {row["route_id"]: row for row in index["routes"]}
    graphs = {row["route_id"]: row for row in index["selected_route_load_graph"]}

    assert set(graphs) == set(routes)
    for route_id, route in routes.items():
        graph = graphs[route_id]
        assert graph["always_loaded"] == ["SKILL.md"]
        assert graph["selected_reference"] == route["next_reference"]
        assert graph["conditional_references"] == route["conditional_references"]
        assert len(graph["load_order"]) == len(set(graph["load_order"]))
        for reference in graph["load_order"][1:]:
            assert (SKILL_ROOT / reference).is_file(), (route_id, reference)

    check_skill = graphs["skillguard.route.check-skill.v1"]
    assert check_skill["load_order"] == [
        "SKILL.md",
        "references/skillguard-supervisor.md",
    ]
    assert "references/skillguard-target-installation.md" in check_skill["excluded_by_default"]
    assert "references/skillguard-portfolio.md" in check_skill["excluded_by_default"]

    self_check = graphs["skillguard.route.self-check.v1"]
    assert self_check["load_order"] == [
        "SKILL.md",
        "references/skillguard-self-host.md",
        "references/skillguard-supervisor.md",
        "references/skillguard-execution-depth.md",
        "references/skillguard-test-mesh.md",
    ]
    assert "references/validated-template-pack.md" in self_check["excluded_by_default"]


def test_declared_predicate_selects_without_score():
    selected, candidates, blockers, _ = _select(
        "Create a draft skill scaffold from a Skill Blueprint"
    )

    assert not blockers
    assert selected is not None
    assert selected["command_family"] == "generate-skill"
    assert selected["selection_reason"] == "declared_predicate_match"
    assert selected["confidence"] == "exact"
    assert "score" not in selected
    assert all("score" not in candidate for candidate in candidates)
    assert selected["matched_fact_evidence"][0]["source_span"]


def test_multiple_predicates_block_without_tie_breaking():
    selected, candidates, _, structured = _select("check skill and check suite")

    assert selected is None
    assert {row["command_family"] for row in candidates} == {
        "check-skill",
        "check-suite",
    }
    assert {row["blocker_code"] for row in structured} == {
        "multiple_route_predicate_matches"
    }


def test_explicit_incompatible_route_stays_blocked():
    selected, candidates, _, structured = _select(
        "Create a draft skill scaffold from a Skill Blueprint", "check-suite"
    )

    assert selected is None
    assert {row["command_family"] for row in candidates} >= {
        "generate-skill",
        "check-suite",
    }
    assert "incompatible_route_hint" in {
        row["blocker_code"] for row in structured
    }


def test_entry_and_global_prompt_preserve_declared_headroom():
    index = generate_route_index.build_route_index()
    budget = index["prompt_budget"]
    entry = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    block = checker_engine.render_global_prompt_block(
        {"registry_hash": "sha256:" + "a" * 64, "items": []},
        ".codex/.skillguard/global-router/global_registry.json",
    )

    assert len(entry) <= budget["entry_shell_max_characters"]
    assert len(block) <= budget["global_managed_block_max_characters"]
    assert budget["minimum_reasoning_headroom_characters"] >= 12000
    assert "## Validated Template Pack Selection" not in block
    assert "### Current Route Index" not in block
    assert "current_registered_source_count: 0" in block


def test_no_always_loaded_prompt_contains_an_understanding_level():
    entry = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8").lower()
    global_template = (
        SKILL_ROOT
        / "assets"
        / "templates"
        / "global_skillguard_prompt_block.md.template"
    ).read_text(encoding="utf-8").lower()

    for marker in ("understanding level", "u1", "u2", "u3"):
        assert marker not in entry
        assert marker not in global_template
