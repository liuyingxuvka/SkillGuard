"""Fail-closed adapter from a router work package to the native SkillGuard CLI.

This script performs no scan, registry build, private prompt installation, or
route selection of its own. It invokes only the author-side SkillGuard command
owner and checks the returned evidence plus the one current author handoff
identity.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROUTER_SKILL_ID = "skillguard-global-router"
REQUIRED_ROUTER_COMMANDS = {
    "scan-global-skills",
    "build-global-registry",
    "check-global-registry",
    "refresh-global-router",
}
RETIRED_PUBLIC_ROUTER_COMMANDS = {
    "render-global-prompt",
    "install-global-prompt",
    "check-global-prompt",
    "resolve-global-skill",
}


class ContractCheckError(RuntimeError):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _under(path: Path, root: Path, code: str) -> Path:
    resolved_root = root.resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ContractCheckError(code, str(path)) from exc
    return resolved


def _load_json(path: Path, code: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractCheckError(code, f"{path.name}: {type(exc).__name__}") from exc
    if not isinstance(payload, Mapping):
        raise ContractCheckError(code, f"{path.name}: root_not_object")
    return payload


def _native_skillguard_root() -> Path:
    skill_root = Path(__file__).resolve().parents[1]
    candidate = skill_root.parent / "skillguard"
    if (candidate / "scripts" / "skillguard.py").is_file():
        return candidate.resolve()
    raise ContractCheckError(
        "native_skillguard_runtime_missing",
        "the sibling author-side skillguard source runtime is required",
    )


def _run_native_cli(args: Sequence[str]) -> Mapping[str, Any]:
    cli = _native_skillguard_root() / "scripts" / "skillguard.py"
    if not cli.is_file():
        raise ContractCheckError("native_cli_missing", cli.as_posix())
    completed = subprocess.run(
        [sys.executable, str(cli), *args, "--output", "-"],
        cwd=cli.parent.parent,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ContractCheckError(
            "native_output_not_json",
            f"exit={completed.returncode}; stderr={completed.stderr[:200]}",
        ) from exc
    if not isinstance(payload, Mapping):
        raise ContractCheckError("native_output_not_object", str(type(payload).__name__))
    if completed.returncode != 0 or payload.get("decision") != "pass":
        raise ContractCheckError(
            "native_check_failed",
            f"command={args[0]}; exit={completed.returncode}; decision={payload.get('decision')}",
        )
    if payload.get("blockers") or payload.get("failures"):
        raise ContractCheckError("native_check_has_gaps", args[0])
    return payload


def _check_command_surface() -> Mapping[str, Any]:
    native = _run_native_cli(("commands",))
    names = {str(item) for item in native.get("command_names", [])}
    names.update(
        str(item.get("name", ""))
        for item in native.get("commands", [])
        if isinstance(item, Mapping) and str(item.get("name", "")).strip()
    )
    missing = sorted(REQUIRED_ROUTER_COMMANDS - names)
    if missing:
        raise ContractCheckError("router_command_surface_incomplete", ",".join(missing))
    leaked = sorted(RETIRED_PUBLIC_ROUTER_COMMANDS & names)
    if leaked:
        raise ContractCheckError("retired_public_router_command_present", ",".join(leaked))
    return native


def _registry_entry(registry: Mapping[str, Any]) -> Mapping[str, Any]:
    matches = [
        row
        for row in registry.get("items", [])
        if isinstance(row, Mapping) and row.get("skill_id") == ROUTER_SKILL_ID
    ]
    if len(matches) != 1:
        raise ContractCheckError("router_registry_entry_not_unique", str(len(matches)))
    return matches[0]


def _require_current_handoff(registry: Mapping[str, Any]) -> Mapping[str, Any]:
    entry = _registry_entry(registry)
    if entry.get("status") != "current":
        raise ContractCheckError("router_registry_entry_not_current", str(entry.get("status", "missing")))
    route = entry.get("route_entrypoint")
    if not isinstance(route, Mapping):
        raise ContractCheckError("router_route_entrypoint_missing", ROUTER_SKILL_ID)
    route_docs = {str(item).replace("\\", "/") for item in route.get("route_doc_paths", [])}
    contract_path = str(route.get("contract_path", "")).replace("\\", "/")
    manifest_path = str(route.get("check_manifest_path", "")).replace("\\", "/")
    if not contract_path.endswith("/.skillguard/compiled-contract.json"):
        raise ContractCheckError("router_current_contract_handoff_missing", contract_path or "missing")
    if not manifest_path.endswith("/.skillguard/check-manifest.json"):
        raise ContractCheckError("router_current_manifest_handoff_missing", manifest_path or "missing")
    if contract_path not in route_docs or manifest_path not in route_docs:
        raise ContractCheckError("router_current_route_docs_incomplete", ROUTER_SKILL_ID)
    if not str(route.get("contract_hash", "")):
        raise ContractCheckError("router_contract_hash_missing", ROUTER_SKILL_ID)
    return entry


def _check_scan(target_root: Path) -> Mapping[str, Any]:
    report = _load_json(target_root / "global_router" / "skill_scan.json", "scan_report_unreadable")
    if report.get("decision") != "pass" or report.get("blockers") or report.get("failures"):
        raise ContractCheckError("scan_report_not_pass", str(report.get("decision", "missing")))
    if not isinstance(report.get("skill_items"), list) or not report.get("skill_items"):
        raise ContractCheckError("scan_report_empty", "skill_items")
    return report


def _check_registry(repository_root: Path, target_root: Path) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    registry_path = target_root / "global_router" / "global_registry.json"
    registry = _load_json(registry_path, "registry_unreadable")
    native = _run_native_cli(
        (
            "check-global-registry",
            "--registry",
            str(registry_path),
            "--codex-home",
            str(target_root / "codex_home"),
        ),
    )
    if native.get("registry_hash") != registry.get("registry_hash"):
        raise ContractCheckError("registry_hash_mismatch", str(native.get("registry_hash", "missing")))
    _require_current_handoff(registry)
    return native, registry


def _check_private_author_prompt(
    target_root: Path,
    registry: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    registry = registry or _load_json(
        target_root / "global_router" / "global_registry.json",
        "registry_unreadable",
    )
    agents = target_root / "codex_home" / "AGENTS.md"
    text = agents.read_text(encoding="utf-8") if agents.is_file() else ""
    if text.count("<!-- BEGIN MANAGED SKILLGUARD GLOBAL ROUTER -->") != 1:
        raise ContractCheckError("managed_prompt_begin_marker_count", "expected exactly one")
    if text.count("<!-- END MANAGED SKILLGUARD GLOBAL ROUTER -->") != 1:
        raise ContractCheckError("managed_prompt_end_marker_count", "expected exactly one")
    lowered = text.lower()
    for required in (
        "private maintainer-computer",
        "explicit author-side",
        "ordinary use",
        "does not start skillguard maintenance",
    ):
        if required not in lowered:
            raise ContractCheckError("private_author_prompt_boundary_missing", required)
    if str(registry.get("registry_hash", "")) not in text:
        raise ContractCheckError("private_author_prompt_registry_hash_missing", "AGENTS.md")
    return {
        "decision": "pass",
        "registry_hash": registry.get("registry_hash"),
        "prompt_path": "codex_home/AGENTS.md",
    }


def _check_projection(target_root: Path) -> Mapping[str, Any]:
    registry = _load_json(
        target_root / "global_router" / "global_registry.json",
        "registry_unreadable",
    )
    projection = _load_json(
        target_root / "global_router" / "global_prompt_projection.json",
        "prompt_projection_unreadable",
    )
    if projection.get("registry_hash") != registry.get("registry_hash"):
        raise ContractCheckError(
            "projection_registry_hash_mismatch",
            str(projection.get("registry_hash", "missing")),
        )
    if projection.get("router_skill_id") != ROUTER_SKILL_ID:
        raise ContractCheckError("projection_router_skill_mismatch", str(projection.get("router_skill_id", "missing")))
    block = str(projection.get("managed_block", ""))
    if block.count("<!-- BEGIN MANAGED SKILLGUARD GLOBAL ROUTER -->") != 1:
        raise ContractCheckError("projection_begin_marker_count", "expected exactly one")
    if block.count("<!-- END MANAGED SKILLGUARD GLOBAL ROUTER -->") != 1:
        raise ContractCheckError("projection_end_marker_count", "expected exactly one")
    lowered = block.lower()
    for required in (
        "private maintainer-computer",
        "explicit author-side",
        "ordinary use",
        "does not start skillguard maintenance",
    ):
        if required not in lowered:
            raise ContractCheckError("projection_author_boundary_missing", required)
    return projection


def check(mode: str, repository_root: Path, target_root: Path) -> Mapping[str, Any]:
    results: dict[str, Any] = {}
    if mode == "command-surface":
        native = _check_command_surface()
        results["command_surface"] = {
            "decision": native.get("decision"),
            "required_command_count": len(REQUIRED_ROUTER_COMMANDS),
        }
    elif mode == "scan":
        report = _check_scan(target_root)
        results["scan"] = {"decision": report.get("decision"), "item_count": len(report.get("skill_items", []))}
    elif mode == "registry":
        native, _registry = _check_registry(repository_root, target_root)
        results["registry"] = {"decision": native.get("decision"), "registry_hash": native.get("registry_hash")}
    elif mode == "projection":
        projection = _check_projection(target_root)
        results["projection"] = {
            "registry_hash": projection.get("registry_hash"),
            "router_skill_id": projection.get("router_skill_id"),
        }
    elif mode == "refresh":
        registry_native, registry = _check_registry(repository_root, target_root)
        projection = _check_projection(target_root)
        prompt = _check_private_author_prompt(target_root, registry)
        results = {
            "registry": {"decision": registry_native.get("decision"), "registry_hash": registry.get("registry_hash")},
            "projection": {"registry_hash": projection.get("registry_hash")},
            "private_author_prompt": {"decision": prompt.get("decision")},
        }
    else:  # pragma: no cover - argparse owns this boundary
        raise ContractCheckError("unknown_mode", mode)
    return {
        "schema_version": "skillguard.global_router_contract_check.v1",
        "decision": "pass",
        "mode": mode,
        "results": results,
        "failures": [],
        "blockers": [],
        "claim_boundary": (
            "This adapter proves only current author-side router checks, private author projection, "
            "and the current handoff identity for the supplied maintenance work package. It does not "
            "create a consumer dependency, execute a selected target skill, prove publication, or "
            "guarantee future AI behavior."
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        required=True,
        choices=(
            "command-surface",
            "scan",
            "registry",
            "projection",
            "refresh",
        ),
    )
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--target-root", required=True)
    args = parser.parse_args(argv)
    repository_root = Path(args.repository_root).resolve()
    target_root = Path(args.target_root).resolve()
    try:
        _under(repository_root, repository_root, "repository_root_invalid")
        _under(target_root, target_root, "target_root_invalid")
        result = check(args.mode, repository_root, target_root)
        exit_code = 0
    except (ContractCheckError, OSError) as exc:
        code = exc.code if isinstance(exc, ContractCheckError) else "filesystem_error"
        detail = exc.detail if isinstance(exc, ContractCheckError) else type(exc).__name__
        result = {
            "schema_version": "skillguard.global_router_contract_check.v1",
            "decision": "block",
            "mode": args.mode,
            "results": {},
            "failures": [],
            "blockers": [{"code": code, "detail": detail}],
            "claim_boundary": "A blocked adapter result supplies no current router closure authority.",
        }
        exit_code = 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
