"""Exact current global-router discovery and registry construction.

This module owns the semantic path from installed/canonical ``SKILL.md`` files
and current contract authorities to registry items.  Keeping it beside the
other ``global_router_*`` modules ensures unrelated CLI/checker edits cannot
invalidate routing while any real discovery-rule edit does.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .content_projection import impact_file_hash
from .contract_schema import (
    validate_binding_source,
    validate_check_manifest,
    validate_compiled_contract,
)
from .global_router_projection import (
    GLOBAL_REGISTRY_SCHEMA_VERSION,
    GLOBAL_ROUTER_SKILL_ID,
    diagnostic_inventory_hash,
    registry_hash,
)
from .runtime_authority import AUTHORITY_CURRENT, resolve_runtime_authority


_CURRENT_CONTROL_FILES = (
    "contract-source.json",
    "compiled-contract.json",
    "check-manifest.json",
)


def _generated_at() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _canonical_hash(payload: object) -> str:
    raw = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest().upper()


def _wire_from_internal_hash(value: object) -> str:
    text = str(value or "")
    if re.fullmatch(r"sha256:[0-9a-f]{64}", text):
        return text
    if re.fullmatch(r"[0-9A-Fa-f]{64}", text):
        return "sha256:" + text.lower()
    return ""


def public_path(
    path: Path,
    *,
    repository_root: Path,
    codex_home: Path,
) -> str:
    resolved = path.resolve()
    try:
        return ".codex/" + resolved.relative_to(codex_home.resolve()).as_posix()
    except ValueError:
        pass
    try:
        return resolved.relative_to(repository_root.resolve()).as_posix()
    except ValueError:
        digest = hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()[:12]
        return f"<external:{digest}>/{resolved.name}"


def _semantic_root(skill_dir: Path, repository_root: Path) -> Path:
    resolved = skill_dir.resolve()
    try:
        resolved.relative_to(repository_root.resolve())
        return repository_root.resolve()
    except ValueError:
        if resolved.parent.name == "skills":
            return resolved.parent.parent
        return resolved


def _read_json_object(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("JSON root must be an object")
    return payload


def _schema_warnings(label: str, findings: Sequence[Any]) -> list[str]:
    return [
        f"{label} validation failure: {finding.code}@{finding.path}: {finding.message}"
        for finding in findings[:8]
    ]


def _empty_contract_projection(skill_file_path: str) -> dict[str, Any]:
    return {
        "repository_role": "",
        "maintenance_unit_id": "",
        "member_skill_id": "",
        "integration_mode": "missing",
        "route_confidence": "blocked",
        "contract_authority": "missing",
        "authority_decision": "blocked",
        "authority_blockers": ["runtime_authority_missing"],
        "contract_source_path": "",
        "contract_source_sha256": "",
        "contract_path": "",
        "contract_sha256": "",
        "contract_hash": "",
        "check_manifest_path": "",
        "check_manifest_sha256": "",
        "check_manifest_hash": "",
        "check_declarations_hash": "",
        "model_id": "",
        "function_ids": [],
        "route_ids": [],
        "default_route_id": "",
        "native_route_owner": "",
        "native_route_bindings": [],
        "native_check_bindings": [],
        "phase_native_bindings": [],
        "may_define_parallel_execution_route": False,
        "may_define_skillguard_runtime_route": False,
        "route_doc_paths": [skill_file_path],
        "handoff_rule": (
            "Read the selected SKILL.md before acting; no current typed contract "
            "authority is available."
        ),
    }


def contract_projection(
    skill_dir: Path,
    *,
    repository_root: Path,
    codex_home: Path,
) -> tuple[dict[str, Any], list[str]]:
    """Project one current contract trio; old authority is rejection-only."""

    root = skill_dir.resolve()
    skill_path = public_path(
        root / "SKILL.md",
        repository_root=repository_root,
        codex_home=codex_home,
    )
    projection = _empty_contract_projection(skill_path)
    warnings: list[str] = []
    control = root / ".skillguard"
    paths = {name: control / name for name in _CURRENT_CONTROL_FILES}
    present = {name: path.is_file() for name, path in paths.items()}
    if not all(present.values()):
        for name, is_present in present.items():
            if not is_present:
                warnings.append(
                    "current contract authority file is missing: "
                    + public_path(
                        paths[name],
                        repository_root=repository_root,
                        codex_home=codex_home,
                    )
                )
        authority = resolve_runtime_authority(
            root,
            repository_root=_semantic_root(root, repository_root),
        )
        projection["authority_decision"] = authority.authority
        projection["authority_blockers"] = list(authority.blockers)
        return projection, warnings

    try:
        source = _read_json_object(paths["contract-source.json"])
        contract = _read_json_object(paths["compiled-contract.json"])
        manifest = _read_json_object(paths["check-manifest.json"])
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        warnings.append(f"current contract authority is unreadable: {type(exc).__name__}")
        return projection, warnings

    projection.update(
        {
            "contract_authority": "current",
            "contract_source_path": public_path(
                paths["contract-source.json"],
                repository_root=repository_root,
                codex_home=codex_home,
            ),
            "contract_source_sha256": impact_file_hash(
                paths["contract-source.json"]
            ),
            "contract_path": public_path(
                paths["compiled-contract.json"],
                repository_root=repository_root,
                codex_home=codex_home,
            ),
            "contract_sha256": impact_file_hash(paths["compiled-contract.json"]),
            "check_manifest_path": public_path(
                paths["check-manifest.json"],
                repository_root=repository_root,
                codex_home=codex_home,
            ),
            "check_manifest_sha256": impact_file_hash(
                paths["check-manifest.json"]
            ),
        }
    )
    projection["route_doc_paths"].extend(
        [
            projection["contract_source_path"],
            projection["contract_path"],
            projection["check_manifest_path"],
        ]
    )
    warnings.extend(_schema_warnings("contract-source", validate_binding_source(source)))
    warnings.extend(_schema_warnings("compiled-contract", validate_compiled_contract(contract)))
    warnings.extend(_schema_warnings("check-manifest", validate_check_manifest(manifest)))

    unsigned_contract = dict(contract)
    stored_contract_hash = unsigned_contract.pop("contract_hash", None)
    unsigned_manifest = dict(manifest)
    stored_manifest_hash = unsigned_manifest.pop("manifest_hash", None)
    if stored_contract_hash != _canonical_hash(unsigned_contract):
        warnings.append("compiled-contract hash does not match canonical content")
    if stored_manifest_hash != _canonical_hash(unsigned_manifest):
        warnings.append("check-manifest hash does not match canonical content")
    if manifest.get("contract_hash") != stored_contract_hash:
        warnings.append("check-manifest does not bind compiled-contract")
    if manifest.get("check_declarations_hash") != contract.get(
        "check_declarations_hash"
    ):
        warnings.append("contract and manifest check declarations differ")
    identities = (
        source.get("skill_id"),
        contract.get("skill_id"),
        manifest.get("skill_id"),
    )
    if not identities[0] or len(set(identities)) != 1:
        warnings.append("current contract trio skill_id binding is inconsistent")
    repository_roles = (
        source.get("repository_role"),
        contract.get("repository_role"),
    )
    if (
        repository_roles[0] != "skill_maintainer_source"
        or len(set(repository_roles)) != 1
    ):
        warnings.append(
            "global router accepts only explicit skill_maintainer_source contracts"
        )
    maintenance_unit_ids = (
        source.get("maintenance_unit_id"),
        contract.get("maintenance_unit_id"),
        manifest.get("maintenance_unit_id"),
    )
    if not maintenance_unit_ids[0] or len(set(maintenance_unit_ids)) != 1:
        warnings.append(
            "current contract trio maintenance_unit_id binding is inconsistent"
        )
    member_skill_ids = source.get("member_skill_ids")
    if (
        not isinstance(member_skill_ids, list)
        or not identities[0]
        or identities[0] not in member_skill_ids
    ):
        warnings.append("skill_id is not a declared member of its maintenance unit")
    model_ids = (source.get("model_id"), contract.get("model_id"), manifest.get("model_id"))
    if not model_ids[0] or len(set(model_ids)) != 1:
        warnings.append("current contract trio model_id binding is inconsistent")

    functions = [
        row for row in contract.get("functions", []) if isinstance(row, Mapping)
    ]
    routes = [row for row in contract.get("routes", []) if isinstance(row, Mapping)]
    function_ids = [str(row.get("function_id", "")) for row in functions]
    route_ids = [str(row.get("route_id", "")) for row in routes]
    if not function_ids or any(not value for value in function_ids) or len(
        function_ids
    ) != len(set(function_ids)):
        warnings.append("compiled-contract function_ids are missing or duplicated")
    if not route_ids or any(not value for value in route_ids) or len(route_ids) != len(
        set(route_ids)
    ):
        warnings.append("compiled-contract route_ids are missing or duplicated")

    integration_mode = str(source.get("integration_mode") or "")
    if integration_mode != "native-integrated":
        warnings.append("contract integration marker must be native-integrated")
    native_route_owner = str(source.get("native_route_owner") or "")
    native_route_bindings = (
        list(source.get("native_route_bindings", []))
        if isinstance(source.get("native_route_bindings"), list)
        else []
    )
    native_check_bindings = (
        list(source.get("native_check_bindings", []))
        if isinstance(source.get("native_check_bindings"), list)
        else []
    )
    phase_native_bindings = (
        list(source.get("phase_native_bindings", []))
        if isinstance(source.get("phase_native_bindings"), list)
        else []
    )
    if integration_mode == "native-integrated":
        if not native_route_owner:
            warnings.append("native route owner is missing")
        if not native_route_bindings:
            warnings.append("native route bindings are missing")
        if not native_check_bindings:
            warnings.append("native check bindings are missing")
        if source.get("may_define_parallel_execution_route") is True:
            warnings.append("native route cannot define parallel execution")
        if source.get("may_define_skillguard_runtime_route") is True:
            warnings.append("native route cannot define SkillGuard runtime authority")

    declared_default = str(source.get("default_route_id") or "")
    compiled_defaults = [
        str(row.get("route_id"))
        for row in routes
        if row.get("default_route") is True and row.get("route_id")
    ]
    first_function_routes = (
        [str(value) for value in functions[0].get("route_ids", []) if str(value)]
        if functions and isinstance(functions[0].get("route_ids"), list)
        else []
    )
    default_route_id = (
        declared_default
        or (compiled_defaults[0] if compiled_defaults else "")
        or (first_function_routes[0] if first_function_routes else "")
        or (route_ids[0] if route_ids else "")
    )
    if default_route_id and default_route_id not in route_ids:
        warnings.append("default_route_id is absent from compiled routes")

    authority = resolve_runtime_authority(
        root,
        repository_root=_semantic_root(root, repository_root),
    )
    projection.update(
        {
            "repository_role": str(source.get("repository_role") or ""),
            "maintenance_unit_id": str(source.get("maintenance_unit_id") or ""),
            "member_skill_id": str(source.get("skill_id") or ""),
            "integration_mode": integration_mode,
            "route_confidence": "native-bound",
            "authority_decision": authority.authority,
            "authority_blockers": list(authority.blockers),
            "contract_hash": _wire_from_internal_hash(stored_contract_hash),
            "check_manifest_hash": _wire_from_internal_hash(stored_manifest_hash),
            "check_declarations_hash": _wire_from_internal_hash(
                contract.get("check_declarations_hash")
            ),
            "model_id": str(contract.get("model_id") or ""),
            "function_ids": function_ids,
            "route_ids": route_ids,
            "default_route_id": default_route_id,
            "native_route_owner": native_route_owner,
            "native_route_bindings": native_route_bindings,
            "native_check_bindings": native_check_bindings,
            "phase_native_bindings": phase_native_bindings,
            "may_define_parallel_execution_route": bool(
                source.get("may_define_parallel_execution_route")
            ),
            "may_define_skillguard_runtime_route": bool(
                source.get("may_define_skillguard_runtime_route")
            ),
            "handoff_rule": (
                "Use this private author registry only to select a maintained skill "
                "source. Read its SKILL.md for domain work. Its adjacent maintenance "
                "contract is author-side audit evidence and is never a consumer "
                "runtime dependency."
            ),
        }
    )
    if not authority.ok or authority.authority != AUTHORITY_CURRENT:
        projection["route_confidence"] = "blocked"
        projection["default_route_id"] = ""
        warnings.extend(
            f"runtime authority {finding.code}@{finding.path}: {finding.message}"
            for finding in authority.findings[:8]
        )
    return projection, list(dict.fromkeys(warnings))


def _frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    lines = text.splitlines()
    try:
        end = lines.index("---", 1)
    except ValueError:
        return {}
    values: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key.strip() in {"name", "description"}:
            values[key.strip()] = value.strip().strip("'\"")
    return values


def _section_items(text: str, heading: str, limit: int = 8) -> list[str]:
    pattern = re.compile(
        rf"^##+\s+{re.escape(heading)}\s*$\n(?P<body>.*?)(?=^##+\s|\Z)",
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    if match is None:
        return []
    items: list[str] = []
    for raw in match.group("body").splitlines():
        line = raw.strip()
        if line.startswith(("- ", "* ")):
            items.append(" ".join(line[2:].split()))
        if len(items) >= limit:
            break
    return items


def route_terms(skill_id: str, skill_name: str, use_when: Sequence[str]) -> list[str]:
    """Derive search terms only from route-semantic declarations."""

    seed = " ".join([skill_id, skill_name, *use_when]).lower()
    return sorted(
        {
            token
            for token in re.findall(r"[a-z0-9][a-z0-9_.:-]{1,}", seed)
            if len(token) > 2
        }
    )[:40]


def discover_skill_items(
    skill_roots: Sequence[Path],
    *,
    repository_root: Path,
    codex_home: Path,
) -> tuple[list[dict[str, Any]], list[str]]:
    items: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[Path] = set()
    for root_value in skill_roots:
        root = root_value.resolve()
        candidates: list[Path] = []
        if (root / "SKILL.md").is_file():
            candidates.append(root / "SKILL.md")
        if root.is_dir():
            candidates.extend(
                child / "SKILL.md"
                for child in sorted(root.iterdir(), key=lambda value: value.name)
                if child.is_dir() and (child / "SKILL.md").is_file()
            )
        for skill_file in candidates:
            skill_file = skill_file.resolve()
            if skill_file in seen:
                continue
            seen.add(skill_file)
            try:
                text = skill_file.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                warnings.append(
                    public_path(
                        skill_file,
                        repository_root=repository_root,
                        codex_home=codex_home,
                    )
                    + f" could not be read: {type(exc).__name__}"
                )
                continue
            metadata = _frontmatter(text)
            skill_dir = skill_file.parent
            if not (
                skill_dir / ".skillguard" / "contract-source.json"
            ).is_file():
                warnings.append(
                    public_path(
                        skill_dir,
                        repository_root=repository_root,
                        codex_home=codex_home,
                    )
                    + ": skipped because it is not an explicit SkillGuard author source"
                )
                continue
            declared_name = metadata.get("name") or skill_dir.name
            description = metadata.get("description") or "No description declared."
            use_when = _section_items(text, "Use When")
            do_not_use_when = _section_items(text, "Do Not Use When")
            contract, contract_warnings = contract_projection(
                skill_dir,
                repository_root=repository_root,
                codex_home=codex_home,
            )
            skill_path = public_path(
                skill_dir,
                repository_root=repository_root,
                codex_home=codex_home,
            )
            warnings.extend(f"{skill_path}: {value}" for value in contract_warnings)
            status = (
                "current"
                if contract.get("contract_authority") == "current"
                and contract.get("authority_decision") == AUTHORITY_CURRENT
                and contract.get("contract_path")
                and contract.get("check_manifest_path")
                and not contract_warnings
                else "blocked"
            )
            skill_id = re.sub(r"[^a-z0-9._-]+", "-", declared_name.lower()).strip("-")
            if skill_dir.name in {"skillguard", GLOBAL_ROUTER_SKILL_ID}:
                skill_id = skill_dir.name
            items.append(
                {
                    "skill_id": skill_id,
                    "skill_name": declared_name,
                    "description": " ".join(description.split()),
                    "skill_path": skill_path,
                    "skill_file": public_path(
                        skill_file,
                        repository_root=repository_root,
                        codex_home=codex_home,
                    ),
                    "skill_sha256": impact_file_hash(skill_file),
                    "status": status,
                    "use_when": use_when,
                    "do_not_use_when": do_not_use_when,
                    "route_entrypoint": contract,
                    "route_terms": route_terms(skill_id, declared_name, use_when),
                    "claim_boundary": (
                        "This entry is a current file-derived routing index only; "
                        "it does not prove target execution or domain correctness."
                    ),
                }
            )
    return (
        sorted(items, key=lambda item: (item["skill_path"], item["skill_id"])),
        sorted(set(warnings)),
    )


def build_registry_payload(
    skill_roots: Sequence[Path],
    *,
    repository_root: Path,
    codex_home: Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    ordered_roots = sorted(
        (root.resolve() for root in skill_roots),
        key=lambda path: public_path(
            path,
            repository_root=repository_root,
            codex_home=codex_home,
        ),
    )
    items, warnings = discover_skill_items(
        ordered_roots,
        repository_root=repository_root,
        codex_home=codex_home,
    )
    payload: dict[str, Any] = {
        "schema_version": GLOBAL_REGISTRY_SCHEMA_VERSION,
        "generated_at": generated_at or _generated_at(),
        "router_skill_id": GLOBAL_ROUTER_SKILL_ID,
        "scan_roots": [
            {
                "path": public_path(
                    root,
                    repository_root=repository_root,
                    codex_home=codex_home,
                ),
                "exists": root.is_dir(),
                "skill_file_count": (
                    sum(
                        1
                        for child in root.iterdir()
                        if child.is_dir() and (child / "SKILL.md").is_file()
                    )
                    + (1 if (root / "SKILL.md").is_file() else 0)
                    if root.is_dir()
                    else 0
                ),
            }
            for root in ordered_roots
        ],
        "item_count": len(items),
        "current_item_count": sum(
            1 for item in items if item.get("status") == "current"
        ),
        "items": items,
        "warnings": warnings,
        "claim_boundary": (
            "This private maintainer registry selects explicit author-side skill "
            "sources only. It does not govern consumer execution, require SkillGuard "
            "on another machine, cover external OpenSpec, execute checks, or prove "
            "future AI behavior."
        ),
    }
    payload["diagnostic_inventory_hash"] = diagnostic_inventory_hash(payload)
    payload["registry_hash"] = registry_hash(payload)
    return payload


__all__ = [
    "build_registry_payload",
    "contract_projection",
    "discover_skill_items",
    "public_path",
    "route_terms",
]
