"""Deterministic compiler for FlowGuard-backed current SkillGuard contracts."""

from __future__ import annotations

import ast
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

from .contract_schema import (
    CHECK_MANIFEST_SCHEMA,
    CLOSURE_PROFILE_ORDER,
    COMPILED_CONTRACT_SCHEMA,
    TARGET_NATIVE_DEPTH_EVIDENCE_SCHEMA,
    SchemaFinding,
    validate_binding_source,
    validate_check_manifest,
    validate_compiled_contract,
    validate_depth_profile,
)
from .capability_contract import (
    capability_contract_topology_findings,
    normalize_portfolio_capability_contracts,
)
from .flowguard_adapter import FlowGuardAdapterError, load_flowguard_model
from .evidence_policy import required_evidence_class
from .portable_content import PORTABLE, classify_member_path, portable_files, scan_member_boundary
from .wire_identity import canonical_json_bytes, wire_hash
from .content_projection import (
    current_content_projection,
    current_content_projection_from_files,
    impact_file_hash,
    source_file_hash,
)
from .global_router_projection import is_global_router_projection_path


BINDING_SOURCE_FILE = "contract-source.json"
COMPILED_CONTRACT_FILE = "compiled-contract.json"
CHECK_MANIFEST_FILE = "check-manifest.json"
_DERIVED_AUTHORITY_FILES = frozenset(
    {COMPILED_CONTRACT_FILE, CHECK_MANIFEST_FILE}
)
COMPILER_VERSION = "skillguard.contract_compiler.v2"
CONTENT_IMPACT_PLAN_SCHEMA = "skillguard.content_impact_plan.current"
CONTENT_IMPACT_POLICY_ID = "skillguard.content_impact_policy.current"
OWNER_RECEIPT_ROOT_REF = {
    "path_token": "owner_evidence_root",
    "relative_path": "check-executions",
}
CONTENT_ROLES = frozenset(
    {
        "runtime_source",
        "contract_schema",
        "prompt_router",
        "fixture_reference",
        "test_dev",
        "documentation_model",
    }
)
INSTALL_DISPOSITIONS = frozenset({"copy", "source_only", "generate", "exclude"})
SELECTOR_KINDS = frozenset({"path", "subtree", "role", "install_disposition"})
CHECK_SOURCE_FIELDS = frozenset(
    {
        "args",
        "check_id",
        "command",
        "coverage_rationale",
        "coverage_scope",
        "covers_obligation_ids",
        "cwd_relative",
        "cwd_token",
        "depends_on_check_ids",
        "evidence_class",
        "evidence_domain_id",
        "execution_owner_id",
        "environment",
        "expected",
        "input_selectors",
        "kind",
        "native_route_id",
        "semantic_check_id",
        "timeout_seconds",
        "applicable",
    }
)
OWNER_BEHAVIOR_FIELDS = (
    "kind",
    "command",
    "args",
    "cwd_token",
    "cwd_relative",
    "environment",
    "expected",
    "timeout_seconds",
    "assertion_scope",
    "native_route_id",
    "applicable",
)
FULL_ADMISSION_REASON_CODES = (
    "explicit_final_gate",
    "explicit_release_gate",
    "impact_policy_or_compiler_changed",
    "shared_validation_runtime_changed",
    "all_owner_component_changed",
)

@dataclass(frozen=True)
class CompileResult:
    ok: bool
    status: str
    findings: tuple[SchemaFinding, ...]
    compiled_contract: Mapping[str, Any] | None = None
    check_manifest: Mapping[str, Any] | None = None
    written_files: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "skillguard_v2_compile_report",
            "ok": self.ok,
            "status": self.status,
            "findings": [row.to_dict() for row in self.findings],
            "contract_hash": (
                str(self.compiled_contract.get("contract_hash", ""))
                if self.compiled_contract
                else ""
            ),
            "manifest_hash": (
                str(self.check_manifest.get("manifest_hash", ""))
                if self.check_manifest
                else ""
            ),
            "written_files": list(self.written_files),
            "claim_boundary": (
                "Compilation proves deterministic model/binding parity and exact check mapping. "
                "It does not execute target work or prove declared-check execution, installation, or publication closure."
            ),
        }


def canonical_hash(payload: object) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest().upper()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def path_fingerprint(path: Path, *, member_root: Path | None = None) -> str:
    if path.is_file():
        root = (member_root or path.parent).resolve(strict=True)
        decision = classify_member_path(root, path)
        if decision.classification != PORTABLE:
            raise ValueError(
                "implementation file portable boundary is blocked: "
                f"{decision.reason}:{path.name}"
            )
        return source_file_hash(path)
    if path.is_dir():
        boundary = scan_member_boundary(path)
        if not boundary.ok:
            raise ValueError(
                "implementation path portable boundary is blocked: "
                + ",".join(
                    [
                        *(f"runtime:{value}" for value in boundary.blocking_runtime_paths),
                        *(f"unsafe:{value}" for value in boundary.unsafe_paths),
                    ]
                )
            )
        rows = [
            {
                "path": relative.as_posix(),
                "sha256": source_file_hash(child),
            }
            for relative, child in portable_files(path)
            if ".skillguard" not in relative.parts
        ]
        return canonical_hash(rows)
    raise ValueError(f"implementation path is missing: {path}")


def _load_json(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing JSON file: {path.name}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON file {path.name}: {exc.msg}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError(f"JSON root must be an object: {path.name}")
    return payload


def _ensure_under(path: Path, root: Path, finding_path: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"{finding_path} must stay under repository root") from exc
    return resolved


def _index(rows: Sequence[Mapping[str, Any]], key: str) -> dict[str, Mapping[str, Any]]:
    return {str(row.get(key, "")): row for row in rows if str(row.get(key, ""))}


def _wire_file_hash(path: Path) -> str:
    return "sha256:" + source_file_hash(path).lower()


def _relative_path(path: Path, repository_root: Path) -> str:
    return path.resolve(strict=True).relative_to(repository_root.resolve(strict=True)).as_posix()


def _existing_argument_paths(
    check: Mapping[str, Any], repository_root: Path
) -> tuple[tuple[str, str], ...]:
    """Return exact repository paths named by a check command.

    Runtime outputs and placeholders do not exist before execution and therefore
    cannot silently become source selectors.
    """

    rows: set[tuple[str, str]] = set()
    root = repository_root.resolve(strict=True)
    for value in check.get("args", []):
        text = str(value).strip()
        if (
            not text
            or text == "."
            or text.startswith("-")
            or "{{" in text
            or "://" in text
        ):
            continue
        candidate_text = text.split("::", 1)[0].replace("\\", "/")
        candidate = Path(candidate_text)
        if candidate.is_absolute():
            continue
        resolved = (root / candidate).resolve()
        try:
            relative = resolved.relative_to(root).as_posix()
        except ValueError:
            continue
        if resolved.is_file():
            rows.add(("path", relative))
        elif resolved.is_dir() and relative not in {"", "."}:
            rows.add(("subtree", relative.rstrip("/")))
    return tuple(sorted(rows))


def _content_role(path: str) -> str:
    folded = path.casefold()
    name = PurePosixPath(path).name.casefold()
    # Fixtures and development tests must win before filename-based runtime
    # classifiers.  Otherwise a fixture named ``global_router`` becomes a
    # router input and a test-only edit invalidates the managed prompt.
    if folded.startswith("fixtures/") or "/fixtures/" in folded:
        return "fixture_reference"
    if folded.startswith("tests/") or "/tests/" in folded:
        return "test_dev"
    if (
        (
            name.startswith("global_router_")
            and name.endswith(".py")
        )
        or name
        in {
            "wire_identity.py",
            "content_projection.py",
            "validation_execution_policy.py",
            "skillguard_global_registry.schema.json",
            "skillguard_global_prompt_projection.schema.json",
            "global_skillguard_prompt_block.md.template",
        }
    ):
        return "prompt_router"
    if (
        path.endswith("/.skillguard/contract-source.json")
        or "/assets/schemas/" in folded
        or name in {"contract_compiler.py", "contract_schema.py", "test-mesh.json"}
    ):
        return "contract_schema"
    if folded.startswith(".flowguard/") or name == "skill.md" or PurePosixPath(path).suffix.lower() == ".md":
        return "documentation_model"
    return "runtime_source"


def _install_disposition(path: str, skill_root_relative: str, role: str) -> str:
    normalized_root = skill_root_relative.strip("/")
    if normalized_root in {"", "."}:
        relative = path
    else:
        prefix = normalized_root + "/"
        if not path.startswith(prefix):
            return "source_only"
        relative = path[len(prefix) :]
    name = PurePosixPath(relative).name
    if name in _DERIVED_AUTHORITY_FILES and relative.startswith(".skillguard/"):
        return "generate"
    if role in {"test_dev", "fixture_reference"}:
        return "source_only"
    if relative == "SKILL.md" or relative.startswith(
        ("scripts/", "assets/", "references/", ".skillguard/")
    ):
        return "copy"
    if role == "documentation_model":
        return "source_only"
    return "copy"


def _inventory_rows(
    *,
    binding: Mapping[str, Any],
    compiled_checks: Sequence[Mapping[str, Any]],
    repository_root: Path,
    skill_root: Path,
    binding_path: Path,
    model_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Path], list[SchemaFinding]]:
    findings: list[SchemaFinding] = []
    root = repository_root.resolve(strict=True)
    skill_relative = _relative_path(skill_root, root)
    paths: dict[str, Path] = {}
    forced_roles: dict[str, str] = {}

    def add_file(path: Path, *, role: str | None = None) -> None:
        try:
            resolved_candidate = path.resolve(strict=True)
        except (FileNotFoundError, OSError):
            resolved_candidate = path
        if (
            resolved_candidate.name in _DERIVED_AUTHORITY_FILES
            and resolved_candidate.parent.name.casefold() == ".skillguard"
        ):
            # Generated authorities are outputs at every maintained-member
            # depth.  They are verified through their normalized generated
            # projection, but never become functional inputs that invalidate
            # the compiler which produced them.
            return
        try:
            relative = _relative_path(path, root)
        except (FileNotFoundError, ValueError) as exc:
            findings.append(
                SchemaFinding("impact_inventory_path_invalid", "$.content_impact_plan", str(exc))
            )
            return
        paths[relative] = resolved_candidate.resolve(strict=True)
        if role:
            forced_roles[relative] = role

    add_file(binding_path, role="contract_schema")
    add_file(model_path, role="documentation_model")
    entrypoint = skill_root / "SKILL.md"
    if entrypoint.is_file():
        add_file(entrypoint, role="documentation_model")

    # Inventory the complete portable member before deriving consumers.  The
    # inventory proves omission-freedom; component projections decide which
    # owner, installation, Portfolio, or router identity a file may affect.
    try:
        for _relative, child in portable_files(skill_root):
            add_file(child)
    except (OSError, ValueError) as exc:
        findings.append(
            SchemaFinding(
                "impact_inventory_skill_tree_invalid",
                "$.content_impact_plan",
                str(exc),
            )
        )

    for index, path_value in enumerate(binding.get("implementation_paths", [])):
        try:
            implementation = _ensure_under(
                root / str(path_value), root, f"$.implementation_paths[{index}]"
            )
            if implementation.is_file():
                add_file(implementation)
            elif implementation.is_dir():
                for _relative, child in portable_files(implementation):
                    add_file(child)
            else:
                raise ValueError(f"implementation path is missing: {path_value}")
        except ValueError as exc:
            findings.append(
                SchemaFinding(
                    "impact_inventory_implementation_invalid",
                    f"$.implementation_paths[{index}]",
                    str(exc),
                )
            )

    for check in compiled_checks:
        for kind, path_text in _existing_argument_paths(check, root):
            if kind == "path":
                add_file(root / path_text)

    override_selectors: dict[str, Mapping[str, Any]] = {}
    for index, value in enumerate(binding.get("content_role_overrides", [])):
        if not isinstance(value, Mapping):
            findings.append(
                SchemaFinding(
                    "content_role_override_invalid",
                    f"$.content_role_overrides[{index}]",
                    "override must be an object",
                )
            )
            continue
        path = str(value.get("path", "")).replace("\\", "/").strip("/")
        if not path or path in override_selectors:
            findings.append(
                SchemaFinding(
                    "content_role_override_duplicate_or_missing",
                    f"$.content_role_overrides[{index}].path",
                    path or "missing",
                )
            )
            continue
        override_selectors[path] = value

    # A reviewed override may name either one maintained file or one maintained
    # directory. Directory selectors apply to every inventoried descendant so a
    # newly added fixture inherits the same role/disposition without extending a
    # hand-maintained file list. Overlapping selectors are rejected instead of
    # relying on precedence or a hidden fallback.
    overrides: dict[str, tuple[Mapping[str, Any], str, str]] = {}
    matched_override_paths: set[str] = set()
    for selector_path, value in sorted(override_selectors.items()):
        subtree_prefix = selector_path + "/"
        matched_paths = [
            path
            for path in sorted(paths)
            if path == selector_path or path.startswith(subtree_prefix)
        ]
        if not matched_paths:
            continue
        selector_kind = "path" if selector_path in paths else "subtree"
        matched_override_paths.add(selector_path)
        for matched_path in matched_paths:
            prior = overrides.get(matched_path)
            if prior is not None:
                findings.append(
                    SchemaFinding(
                        "content_role_override_overlap",
                        f"$.content_role_overrides[{selector_path}]",
                        f"{matched_path} is selected by both {prior[2]} and {selector_path}",
                    )
                )
                continue
            overrides[matched_path] = (value, selector_kind, selector_path)

    rows: list[dict[str, Any]] = []
    for path in sorted(paths):
        override_match = overrides.get(path)
        override = override_match[0] if override_match else None
        role = str(override.get("role", "")) if override else forced_roles.get(path, _content_role(path))
        disposition = (
            str(override.get("install_disposition", ""))
            if override
            else _install_disposition(path, skill_relative, role)
        )
        if role not in CONTENT_ROLES:
            findings.append(SchemaFinding("content_role_invalid", f"$.inventory[{path}].role", role))
        if disposition not in INSTALL_DISPOSITIONS:
            findings.append(
                SchemaFinding(
                    "install_disposition_invalid",
                    f"$.inventory[{path}].install_disposition",
                    disposition,
                )
            )
        rows.append(
            {
                "path": path,
                "content_hash": impact_file_hash(paths[path]),
                "role": role,
                "install_disposition": disposition,
                "classification_rule_id": (
                    "reviewed_override:"
                    + str(override_match[1])
                    + ":"
                    + str(override.get("reason", "unspecified"))
                    if override
                    else f"skillguard.content_role_classifier.current:{role}"
                ),
            }
        )
    for path in sorted(set(override_selectors) - matched_override_paths):
        findings.append(
            SchemaFinding(
                "content_role_override_unmatched",
                "$.content_role_overrides",
                path,
            )
        )
    return rows, paths, findings


def _python_import_graph(
    inventory_paths: Mapping[str, Path],
) -> tuple[dict[str, set[str]], tuple[str, ...]]:
    module_index: dict[str, set[str]] = {}
    python_paths = sorted(path for path in inventory_paths if path.endswith(".py"))
    for path in python_paths:
        pure = PurePosixPath(path)
        parts = list(pure.with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts.pop()
        aliases: set[str] = {".".join(parts)}
        if "scripts" in parts:
            aliases.add(".".join(parts[parts.index("scripts") + 1 :]))
        if parts:
            aliases.add(parts[-1])
        for alias in aliases:
            if alias:
                module_index.setdefault(alias, set()).add(path)

    graph: dict[str, set[str]] = {path: set() for path in python_paths}
    parse_errors: list[str] = []

    def add_module(targets: set[str], module: str) -> None:
        if module in module_index:
            targets.update(module_index[module])

    for path in python_paths:
        try:
            tree = ast.parse(inventory_paths[path].read_text(encoding="utf-8"), filename=path)
        except (OSError, UnicodeError, SyntaxError):
            parse_errors.append(path)
            continue
        targets = graph[path]
        parent = PurePosixPath(path).parent
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    add_module(targets, alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = str(node.module or "")
                if node.level:
                    base = parent
                    for _ in range(max(0, node.level - 1)):
                        base = base.parent
                    relative_base = base.joinpath(*module.split(".")) if module else base
                    candidates = [
                        relative_base.with_suffix(".py").as_posix(),
                        (relative_base / "__init__.py").as_posix(),
                    ]
                    for alias in node.names:
                        if alias.name != "*":
                            candidates.append((relative_base / f"{alias.name}.py").as_posix())
                    targets.update(candidate for candidate in candidates if candidate in inventory_paths)
                else:
                    add_module(targets, module)
                    for alias in node.names:
                        if alias.name != "*":
                            add_module(targets, f"{module}.{alias.name}" if module else alias.name)
        targets.discard(path)
    return graph, tuple(sorted(parse_errors))


def _dependency_closure(seeds: Iterable[str], graph: Mapping[str, set[str]]) -> set[str]:
    seen = set(seeds)
    pending = list(seen)
    while pending:
        current = pending.pop()
        for dependency in graph.get(current, set()):
            if dependency not in seen:
                seen.add(dependency)
                pending.append(dependency)
    return seen


def _normalized_selector(
    value: Mapping[str, Any], *, path: str, findings: list[SchemaFinding]
) -> dict[str, str] | None:
    unknown = sorted(set(value) - {"kind", "path", "role", "install_disposition"})
    if unknown:
        findings.append(SchemaFinding("input_selector_unknown_field", path, ",".join(unknown)))
        return None
    kind = str(value.get("kind", ""))
    if kind not in SELECTOR_KINDS:
        findings.append(SchemaFinding("input_selector_kind_invalid", f"{path}.kind", kind))
        return None
    key = "path" if kind in {"path", "subtree"} else kind
    selected = str(value.get(key, "")).replace("\\", "/").strip("/")
    if not selected or selected in {".", ".."}:
        findings.append(SchemaFinding("input_selector_value_invalid", f"{path}.{key}", selected))
        return None
    if kind == "role" and selected not in CONTENT_ROLES:
        findings.append(SchemaFinding("input_selector_role_invalid", f"{path}.role", selected))
        return None
    if kind == "install_disposition" and selected not in INSTALL_DISPOSITIONS:
        findings.append(
            SchemaFinding("input_selector_disposition_invalid", f"{path}.install_disposition", selected)
        )
        return None
    return {"kind": kind, key: selected}


def _selector_matches(selector: Mapping[str, str], row: Mapping[str, Any]) -> bool:
    kind = selector["kind"]
    if kind == "path":
        return row["path"] == selector["path"]
    if kind == "subtree":
        prefix = selector["path"].rstrip("/")
        return row["path"] == prefix or str(row["path"]).startswith(prefix + "/")
    if kind == "role":
        return row["role"] == selector["role"]
    return row["install_disposition"] == selector["install_disposition"]


def _check_behavior_declaration(check: Mapping[str, Any]) -> dict[str, Any]:
    return {key: check[key] for key in OWNER_BEHAVIOR_FIELDS if key in check}


def _source_check_dependencies(check: Mapping[str, Any]) -> tuple[str, ...]:
    args = [str(value) for value in check.get("args", [])]
    dependencies = {str(value) for value in check.get("depends_on_check_ids", [])}
    for index, value in enumerate(args[:-1]):
        if value == "--source-check-id":
            dependencies.add(args[index + 1])
    return tuple(sorted(dependencies))


def _owner_cycles(graph: Mapping[str, Sequence[str]]) -> tuple[str, ...]:
    state: dict[str, int] = {}
    stack: list[str] = []
    cycles: set[str] = set()

    def visit(owner_id: str) -> None:
        status = state.get(owner_id, 0)
        if status == 2:
            return
        if status == 1:
            if owner_id in stack:
                start = stack.index(owner_id)
                cycles.add(" -> ".join([*stack[start:], owner_id]))
            return
        state[owner_id] = 1
        stack.append(owner_id)
        for dependency in graph.get(owner_id, ()):
            visit(dependency)
        stack.pop()
        state[owner_id] = 2

    for owner_id in sorted(graph):
        visit(owner_id)
    return tuple(sorted(cycles))


def _compiled_checks(
    binding: Mapping[str, Any], model_path: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_check in binding.get("checks", []):
        check = dict(source_check)
        check["semantic_check_id"] = str(
            source_check.get("semantic_check_id") or source_check.get("check_id", "")
        )
        if check.get("kind") == "model_assertion" and not check.get("command"):
            check.update(
                {
                    "command": "python",
                    "args": [model_path],
                    "cwd_token": "repository_root",
                    "expected": {"exit_code": 0},
                    "assertion_scope": "current_full_flowguard_model",
                }
            )
        rows.append(check)
    return rows


def _build_content_impact_plan(
    *,
    binding: Mapping[str, Any],
    compiled_checks: Sequence[Mapping[str, Any]],
    repository_root: Path,
    skill_root: Path,
    binding_path: Path,
    model_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], tuple[SchemaFinding, ...]]:
    findings: list[SchemaFinding] = []
    try:
        member_root_path = skill_root.resolve().relative_to(
            repository_root.resolve()
        ).as_posix()
    except ValueError:
        findings.append(
            SchemaFinding(
                "skill_root_outside_repository",
                "$.content_impact_plan.member_root_path",
                "skill root must be contained by repository root",
            )
        )
        member_root_path = ""
    inventory, path_objects, inventory_findings = _inventory_rows(
        binding=binding,
        compiled_checks=compiled_checks,
        repository_root=repository_root,
        skill_root=skill_root,
        binding_path=binding_path,
        model_path=model_path,
    )
    findings.extend(inventory_findings)
    inventory_index = {str(row["path"]): row for row in inventory}
    import_graph, parse_errors = _python_import_graph(path_objects)

    policy_source = binding.get("content_impact_policy")
    policy = dict(policy_source) if isinstance(policy_source, Mapping) else {}
    policy.setdefault("policy_id", CONTENT_IMPACT_POLICY_ID)
    policy.setdefault("owner_receipt_root_ref", dict(OWNER_RECEIPT_ROOT_REF))
    policy.setdefault("unknown_mapping_disposition", "block")
    policy.setdefault("full_admission_reason_codes", list(FULL_ADMISSION_REASON_CODES))

    prepared_checks: list[dict[str, Any]] = []
    signature_owner: dict[str, str] = {}
    owner_declarations: dict[str, dict[str, Any]] = {}
    owner_selector_paths: dict[str, set[str]] = {}
    owner_check_ids: dict[str, set[str]] = {}
    conflicting_owner_ids: set[str] = set()

    for index, source in enumerate(compiled_checks):
        check = dict(source)
        source_unknown = sorted(set(check) - CHECK_SOURCE_FIELDS - {"assertion_scope"})
        if source_unknown:
            findings.append(
                SchemaFinding(
                    "check_behavior_field_unknown",
                    f"$.checks[{index}]",
                    ",".join(source_unknown),
                )
            )
        selectors: list[dict[str, str]] = []
        declared_selectors = check.get("input_selectors")
        if declared_selectors is not None:
            if not isinstance(declared_selectors, list):
                findings.append(
                    SchemaFinding(
                        "input_selectors_invalid",
                        f"$.checks[{index}].input_selectors",
                        "must be an array",
                    )
                )
            else:
                for selector_index, value in enumerate(declared_selectors):
                    if not isinstance(value, Mapping):
                        findings.append(
                            SchemaFinding(
                                "input_selector_invalid",
                                f"$.checks[{index}].input_selectors[{selector_index}]",
                                "must be an object",
                            )
                        )
                        continue
                    normalized = _normalized_selector(
                        value,
                        path=f"$.checks[{index}].input_selectors[{selector_index}]",
                        findings=findings,
                    )
                    if normalized is not None:
                        selectors.append(normalized)
        else:
            selectors.extend(
                {"kind": kind, "path": path}
                for kind, path in _existing_argument_paths(check, repository_root)
            )
        selectors = sorted(
            {json.dumps(row, sort_keys=True): row for row in selectors}.values(),
            key=lambda row: json.dumps(row, sort_keys=True),
        )
        if not selectors:
            findings.append(
                SchemaFinding(
                    "owner_input_selectors_missing",
                    f"$.checks[{index}].input_selectors",
                    str(check.get("check_id", "")),
                )
            )
        evidence_domain_id = str(
            check.get("evidence_domain_id") or "validation"
        )
        owner_declaration = {
            "behavior": _check_behavior_declaration(check),
            "input_selectors": selectors,
            "evidence_domain_id": evidence_domain_id,
            "impact_policy_id": policy["policy_id"],
        }
        declaration_signature = wire_hash(owner_declaration)
        explicit_owner = str(check.get("execution_owner_id", "")).strip()
        if explicit_owner:
            owner_id = explicit_owner
        else:
            owner_id = signature_owner.setdefault(
                declaration_signature,
                "owner:" + str(check.get("check_id", "")).removeprefix("check:"),
            )
        if owner_id in owner_declarations and owner_declarations[owner_id] != owner_declaration:
            conflicting_owner_ids.add(owner_id)
        else:
            owner_declarations.setdefault(owner_id, owner_declaration)
        matched = {
            path
            for path, row in inventory_index.items()
            if any(_selector_matches(selector, row) for selector in selectors)
        }
        if not matched:
            findings.append(
                SchemaFinding(
                    "owner_input_selector_empty",
                    f"$.checks[{index}].input_selectors",
                    str(check.get("check_id", "")),
                )
            )
        matched = _dependency_closure(matched, import_graph)
        owner_selector_paths.setdefault(owner_id, set()).update(matched)
        owner_check_ids.setdefault(owner_id, set()).add(str(check.get("check_id", "")))
        check["execution_owner_id"] = owner_id
        check["input_selectors"] = selectors
        check["evidence_domain_id"] = evidence_domain_id
        check["owner_declaration_hash"] = declaration_signature
        prepared_checks.append(check)

    check_owner = {
        str(check.get("check_id", "")): str(check.get("execution_owner_id", ""))
        for check in prepared_checks
    }
    invalid_edges: set[str] = set()
    owner_dependencies: dict[str, set[str]] = {owner_id: set() for owner_id in owner_declarations}
    for check in prepared_checks:
        owner_id = str(check["execution_owner_id"])
        dependency_checks = _source_check_dependencies(check)
        check["depends_on_check_ids"] = list(dependency_checks)
        for dependency_check_id in dependency_checks:
            dependency_owner = check_owner.get(dependency_check_id)
            if not dependency_owner:
                invalid_edges.add(f"{check['check_id']}->{dependency_check_id}:unknown")
            elif dependency_owner != owner_id:
                owner_dependencies.setdefault(owner_id, set()).add(dependency_owner)

    consumers_by_path: dict[str, set[str]] = {path: set() for path in inventory_index}
    for owner_id, paths in owner_selector_paths.items():
        for path in paths:
            if path in consumers_by_path:
                consumers_by_path[path].add(owner_id)

    skill_prefix = _relative_path(skill_root, repository_root).rstrip("/")
    if skill_prefix == ".":
        skill_prefix = ""
    global_router_seeds = {
        path
        for path in inventory_index
        if is_global_router_projection_path(path, skill_prefix)
    }
    portfolio_seeds = {
        path for path in inventory_index if "portfolio" in path.casefold()
    }
    contract_compile_seeds = {
        path
        for path in inventory_index
        if path
        in {
            _relative_path(binding_path, repository_root),
            _relative_path(model_path, repository_root),
        }
        or PurePosixPath(path).name in {"contract_compiler.py", "contract_schema.py"}
    }
    projection_paths: dict[str, set[str]] = {
        "projection:installation": {
            path
            for path, row in inventory_index.items()
            if row["install_disposition"] in {"copy", "generate"}
        },
        "projection:global-router": global_router_seeds,
        "projection:portfolio": _dependency_closure(portfolio_seeds, import_graph),
        "projection:contract-compile": _dependency_closure(
            contract_compile_seeds, import_graph
        ),
        "projection:source-maintenance": {
            path
            for path, row in inventory_index.items()
            if row["install_disposition"] in {"source_only", "exclude"}
            and (
                not skill_prefix
                or path == skill_prefix
                or path.startswith(skill_prefix + "/")
            )
        },
    }
    projection_kinds = {
        "projection:installation": "installation",
        "projection:global-router": "global_router",
        "projection:portfolio": "portfolio",
        "projection:contract-compile": "contract_compile",
        "projection:source-maintenance": "source_maintenance",
    }
    for index, value in enumerate(binding.get("projection_consumers", [])):
        if not isinstance(value, Mapping):
            findings.append(
                SchemaFinding(
                    "projection_consumer_invalid",
                    f"$.projection_consumers[{index}]",
                    "must be an object",
                )
            )
            continue
        consumer_id = str(value.get("consumer_id", "")).strip()
        if not consumer_id or consumer_id in projection_paths:
            findings.append(
                SchemaFinding(
                    "projection_consumer_duplicate_or_missing",
                    f"$.projection_consumers[{index}].consumer_id",
                    consumer_id or "missing",
                )
            )
            continue
        selected_paths: set[str] = set()
        selectors = value.get("input_selectors", [])
        if not isinstance(selectors, list):
            findings.append(
                SchemaFinding(
                    "projection_consumer_selectors_invalid",
                    f"$.projection_consumers[{index}].input_selectors",
                    "must be an array",
                )
            )
            continue
        for selector_index, selector in enumerate(selectors):
            if not isinstance(selector, Mapping):
                continue
            normalized = _normalized_selector(
                selector,
                path=f"$.projection_consumers[{index}].input_selectors[{selector_index}]",
                findings=findings,
            )
            if normalized:
                selected_paths.update(
                    path
                    for path, row in inventory_index.items()
                    if _selector_matches(normalized, row)
                )
        if not selected_paths:
            findings.append(
                SchemaFinding(
                    "projection_consumer_selector_empty",
                    f"$.projection_consumers[{index}]",
                    consumer_id,
                )
            )
        projection_paths[consumer_id] = selected_paths
        projection_kinds[consumer_id] = str(value.get("kind", "external_projection"))

    portfolio_target_paths: dict[str, set[str]] = {}
    portfolio_target_members: dict[str, list[str]] = {}
    for index, value in enumerate(binding.get("portfolio_target_edges", [])):
        if not isinstance(value, Mapping):
            findings.append(
                SchemaFinding(
                    "portfolio_target_edge_invalid",
                    f"$.portfolio_target_edges[{index}]",
                    "must be an object",
                )
            )
            continue
        target_id = str(value.get("target_id", "")).strip()
        if not target_id or target_id in portfolio_target_paths:
            findings.append(
                SchemaFinding(
                    "portfolio_target_edge_duplicate_or_missing",
                    f"$.portfolio_target_edges[{index}].target_id",
                    target_id or "missing",
                )
            )
            continue
        selected_paths: set[str] = set()
        selectors = value.get("input_selectors", [])
        if not isinstance(selectors, list):
            findings.append(
                SchemaFinding(
                    "portfolio_target_edge_selectors_invalid",
                    f"$.portfolio_target_edges[{index}].input_selectors",
                    "must be an array",
                )
            )
            continue
        for selector_index, selector in enumerate(selectors):
            if not isinstance(selector, Mapping):
                continue
            normalized = _normalized_selector(
                selector,
                path=(
                    f"$.portfolio_target_edges[{index}]"
                    f".input_selectors[{selector_index}]"
                ),
                findings=findings,
            )
            if normalized:
                selected_paths.update(
                    path
                    for path, row in inventory_index.items()
                    if _selector_matches(normalized, row)
                )
        if not selected_paths:
            findings.append(
                SchemaFinding(
                    "portfolio_target_edge_selector_empty",
                    f"$.portfolio_target_edges[{index}]",
                    target_id,
                )
            )
        portfolio_target_paths[target_id] = selected_paths
        raw_members = value.get("member_ids", [])
        portfolio_target_members[target_id] = sorted(
            {str(member).strip() for member in raw_members if str(member).strip()}
            if isinstance(raw_members, list)
            else set()
        )

    for target_id, paths in portfolio_target_paths.items():
        for path in paths:
            consumers_by_path[path].add(f"portfolio-target:{target_id}")

    for consumer_id, paths in projection_paths.items():
        for path in paths:
            consumers_by_path[path].add(consumer_id)

    component_groups: dict[tuple[str, str, tuple[str, ...]], list[str]] = {}
    for path, row in inventory_index.items():
        key = (
            str(row["role"]),
            str(row["install_disposition"]),
            tuple(sorted(consumers_by_path[path])),
        )
        component_groups.setdefault(key, []).append(path)
    components: list[dict[str, Any]] = []
    component_by_path: dict[str, str] = {}
    for (role, disposition, consumer_ids), member_paths in sorted(component_groups.items()):
        members = sorted(member_paths)
        stable_membership = {
            "role": role,
            "install_disposition": disposition,
            "consumer_ids": list(consumer_ids),
            "member_paths": members,
        }
        component_id = f"component:{role}:{wire_hash(stable_membership).split(':', 1)[1][:16]}"
        component = {
            "component_id": component_id,
            "role": role,
            "install_disposition": disposition,
            "member_paths": members,
            "component_hash": wire_hash(
                [
                    {
                        "path": path,
                        "content_hash": inventory_index[path]["content_hash"],
                    }
                    for path in members
                ]
            ),
            "consumer_ids": list(consumer_ids),
            "classification_rule_ids": sorted(
                {str(inventory_index[path]["classification_rule_id"]) for path in members}
            ),
        }
        components.append(component)
        for path in members:
            component_by_path[path] = component_id
    component_index = {str(row["component_id"]): row for row in components}

    owners: list[dict[str, Any]] = []
    for owner_id in sorted(owner_declarations):
        component_ids = sorted(
            {component_by_path[path] for path in owner_selector_paths.get(owner_id, set())}
        )
        dependencies = sorted(owner_dependencies.get(owner_id, set()))
        owners.append(
            {
                "execution_owner_id": owner_id,
                "check_ids": sorted(owner_check_ids.get(owner_id, set())),
                "owner_declaration_hash": wire_hash(owner_declarations[owner_id]),
                "input_selectors": list(owner_declarations[owner_id]["input_selectors"]),
                "input_component_ids": component_ids,
                "owner_input_projection_hash": wire_hash(
                    [
                        {
                            "component_id": component_id,
                            "component_hash": component_index[component_id]["component_hash"],
                        }
                        for component_id in component_ids
                    ]
                ),
                "depends_on_owner_ids": dependencies,
                "evidence_domain_id": owner_declarations[owner_id]["evidence_domain_id"],
            }
        )
    owner_index = {str(row["execution_owner_id"]): row for row in owners}

    check_projections: list[dict[str, Any]] = []
    for check in prepared_checks:
        owner = owner_index.get(str(check["execution_owner_id"]), {})
        check["input_component_ids"] = list(owner.get("input_component_ids", []))
        check["owner_input_projection_hash"] = str(owner.get("owner_input_projection_hash", ""))
        projection = {
            "check_id": str(check.get("check_id", "")),
            "semantic_check_id": str(check.get("semantic_check_id", "")),
            "execution_owner_id": str(check.get("execution_owner_id", "")),
            "covers_obligation_ids": sorted(
                {str(value) for value in check.get("covers_obligation_ids", [])}
            ),
            "evidence_class": str(check.get("evidence_class", "")),
        }
        projection_hash = wire_hash(projection)
        projection["projection_declaration_hash"] = projection_hash
        check["projection_declaration_hash"] = projection_hash
        check_projections.append(projection)

    projection_consumers: list[dict[str, Any]] = []
    for consumer_id in sorted(projection_paths):
        component_ids = sorted(
            {component_by_path[path] for path in projection_paths[consumer_id] if path in component_by_path}
        )
        declaration = {
            "consumer_id": consumer_id,
            "kind": projection_kinds[consumer_id],
            "impact_plan_schema_version": CONTENT_IMPACT_PLAN_SCHEMA,
            "impact_policy_id": str(policy["policy_id"]),
            "input_component_ids": component_ids,
        }
        declaration["projection_declaration_hash"] = wire_hash(declaration)
        declaration["input_projection_hash"] = wire_hash(
            [
                {
                    "component_id": component_id,
                    "component_hash": component_index[component_id]["component_hash"],
                }
                for component_id in component_ids
            ]
        )
        declaration["consumer_projection_hash"] = wire_hash(
            {
                "projection_declaration_hash": declaration[
                    "projection_declaration_hash"
                ],
                "input_projection_hash": declaration["input_projection_hash"],
            }
        )
        projection_consumers.append(declaration)

    portfolio_target_edges = [
        {
            "target_id": target_id,
            "input_component_ids": sorted(
                {
                    component_by_path[path]
                    for path in portfolio_target_paths[target_id]
                    if path in component_by_path
                }
            ),
            "member_ids": portfolio_target_members[target_id],
        }
        for target_id in sorted(portfolio_target_paths)
    ]

    cycle_rows = _owner_cycles(
        {owner_id: sorted(values) for owner_id, values in owner_dependencies.items()}
    )
    health = {
        "unmapped_paths": sorted(
            path for path, consumers in consumers_by_path.items() if not consumers
        ),
        "ambiguous_role_paths": [],
        "duplicate_owner_ids": sorted(conflicting_owner_ids),
        "owner_cycles": list(cycle_rows),
        "invalid_dependency_edges": sorted(invalid_edges),
        "dependency_parse_errors": list(parse_errors),
    }
    all_owner_ids = set(owner_declarations)
    all_owner_component_ids = sorted(
        row["component_id"]
        for row in components
        if all_owner_ids
        and all_owner_ids.issubset(
            {consumer for consumer in row["consumer_ids"] if consumer.startswith("owner:")}
        )
    )
    plan: dict[str, Any] = {
        "schema_version": CONTENT_IMPACT_PLAN_SCHEMA,
        "member_root_path": member_root_path,
        "policy_id": str(policy["policy_id"]),
        "owner_receipt_root_ref": dict(policy["owner_receipt_root_ref"]),
        "unknown_mapping_disposition": str(policy["unknown_mapping_disposition"]),
        "full_admission_reason_codes": list(policy["full_admission_reason_codes"]),
        "inventory": inventory,
        "inventory_hash": wire_hash(inventory),
        "components": components,
        "owners": owners,
        "check_projections": check_projections,
        "projection_consumers": projection_consumers,
        "portfolio_target_edges": portfolio_target_edges,
        "all_owner_component_ids": all_owner_component_ids,
        "health": health,
    }
    plan["impact_graph_hash"] = wire_hash(
        {
            "member_root_path": plan["member_root_path"],
            "policy_id": plan["policy_id"],
            "inventory_hash": plan["inventory_hash"],
            "components": components,
            "owners": owners,
            "check_projections": check_projections,
            "projection_consumers": projection_consumers,
            "portfolio_target_edges": portfolio_target_edges,
            "health": health,
        }
    )
    for key, values in health.items():
        if values:
            findings.append(
                SchemaFinding(
                    "content_impact_graph_unhealthy",
                    f"$.content_impact_plan.health.{key}",
                    ",".join(str(value) for value in values),
                )
            )
    return plan, prepared_checks, tuple(findings)


def _cross_validate(
    model: Mapping[str, Any],
    binding: Mapping[str, Any],
    repository_root: Path,
) -> tuple[SchemaFinding, ...]:
    findings: list[SchemaFinding] = []
    if binding.get("model_id") != model.get("model_id"):
        findings.append(
            SchemaFinding(
                "binding_model_mismatch",
                "$.model_id",
                f"binding={binding.get('model_id')} model={model.get('model_id')}",
            )
        )
    step_index = _index(model.get("steps", []), "step_id")
    route_index = _index(model.get("routes", []), "route_id")
    obligation_index = _index(model.get("obligations", []), "obligation_id")
    step_binding_index = _index(binding.get("step_bindings", []), "step_id")
    check_index = _index(binding.get("checks", []), "check_id")
    artifact_index = _index(binding.get("artifacts", []), "artifact_id")
    judgment_rubric_index = _index(binding.get("judgment_rubrics", []), "rubric_id")

    depth_profile = binding.get("depth_profile")
    if depth_profile is not None:
        depth_findings = validate_depth_profile(depth_profile, path="$.depth_profile")
        findings.extend(depth_findings)
        if isinstance(depth_profile, Mapping) and not depth_findings:
            if depth_profile.get("target_skill_id") != binding.get("skill_id"):
                findings.append(
                    SchemaFinding(
                        "depth_target_skill_mismatch",
                        "$.depth_profile.target_skill_id",
                        f"profile={depth_profile.get('target_skill_id')} binding={binding.get('skill_id')}",
                    )
                )
            declared_route_ids = {str(item) for item in depth_profile.get("native_route_ids", [])}
            unknown_routes = declared_route_ids - set(route_index)
            for route_id in sorted(unknown_routes):
                findings.append(
                    SchemaFinding(
                        "depth_native_route_unknown",
                        "$.depth_profile.native_route_ids",
                        route_id,
                    )
                )
            declared_check_ids = {str(item) for item in depth_profile.get("native_check_ids", [])}
            unknown_checks = declared_check_ids - set(check_index)
            for check_id in sorted(unknown_checks):
                findings.append(
                    SchemaFinding(
                        "depth_native_check_unknown",
                        "$.depth_profile.native_check_ids",
                        check_id,
                    )
                )
            for check_id in sorted(declared_check_ids - unknown_checks):
                check = check_index[check_id]
                missing_dependencies = {
                    str(value)
                    for value in check.get("depends_on_check_ids", [])
                } - declared_check_ids
                for dependency_id in sorted(missing_dependencies):
                    findings.append(
                        SchemaFinding(
                            "depth_native_check_dependency_outside_inventory",
                            "$.depth_profile.native_check_ids",
                            f"{check_id}:{dependency_id}",
                        )
                    )
            provider_runtime = depth_profile.get("provider_runtime", {})
            if isinstance(provider_runtime, Mapping):
                for check_id in provider_runtime.get("readiness_check_ids", []):
                    if str(check_id) not in check_index:
                        findings.append(
                            SchemaFinding(
                                "depth_runtime_readiness_check_unknown",
                                "$.depth_profile.provider_runtime.readiness_check_ids",
                                str(check_id),
                            )
                        )

    for step_id, step in step_index.items():
        if step.get("terminal_kind"):
            continue
        if step_id not in step_binding_index:
            findings.append(SchemaFinding("missing_step_binding", f"$.step_bindings[{step_id}]", step_id))
    for step_id, row in step_binding_index.items():
        if step_id not in step_index:
            findings.append(SchemaFinding("orphan_step_binding", f"$.step_bindings[{step_id}]", step_id))
            continue
        check_ids = tuple(str(item) for item in row.get("check_ids", []))
        if not check_ids:
            findings.append(SchemaFinding("step_without_check", f"$.step_bindings[{step_id}].check_ids", step_id))
        for check_id in check_ids:
            if check_id not in check_index:
                findings.append(SchemaFinding("dangling_step_check", f"$.step_bindings[{step_id}]", check_id))
        for artifact_id in row.get("output_artifact_ids", []):
            if str(artifact_id) not in artifact_index:
                findings.append(SchemaFinding("dangling_step_artifact", f"$.step_bindings[{step_id}]", str(artifact_id)))
        try:
            evidence_class = required_evidence_class({"binding": row})
        except ValueError as exc:
            findings.append(
                SchemaFinding(
                    "step_evidence_policy_invalid",
                    f"$.step_bindings[{step_id}].action.evidence_class",
                    str(exc),
                )
            )
            evidence_class = ""
        if evidence_class == "judged":
            action = row.get("action", {}) if isinstance(row.get("action"), Mapping) else {}
            rubric_id = str(action.get("rubric_id", ""))
            if not rubric_id:
                findings.append(
                    SchemaFinding(
                        "judged_step_rubric_missing",
                        f"$.step_bindings[{step_id}].action.rubric_id",
                        step_id,
                    )
                )
            elif rubric_id not in judgment_rubric_index:
                findings.append(
                    SchemaFinding(
                        "judged_step_rubric_unknown",
                        f"$.step_bindings[{step_id}].action.rubric_id",
                        rubric_id,
                    )
                )

    covered_obligations: set[str] = set()
    all_obligation_ids = set(obligation_index)
    referenced_checks = {
        str(check_id)
        for row in step_binding_index.values()
        for check_id in row.get("check_ids", [])
    }
    for check_id, row in check_index.items():
        coverage = {str(item) for item in row.get("covers_obligation_ids", [])}
        if check_id not in referenced_checks:
            findings.append(SchemaFinding("orphan_check", f"$.checks[{check_id}]", check_id))
        unknown = coverage - all_obligation_ids
        for obligation_id in sorted(unknown):
            findings.append(SchemaFinding("check_unknown_obligation", f"$.checks[{check_id}]", obligation_id))
        if len(all_obligation_ids) > 1 and coverage == all_obligation_ids:
            if row.get("coverage_scope") != "suite" or not str(row.get("coverage_rationale", "")).strip():
                findings.append(
                    SchemaFinding(
                        "broad_all_check_binding",
                        f"$.checks[{check_id}].covers_obligation_ids",
                        "all-obligation coverage requires suite scope and a concrete rationale",
                    )
                )
        covered_obligations.update(coverage & all_obligation_ids)
    for obligation_id in sorted(all_obligation_ids - covered_obligations):
        if bool(obligation_index[obligation_id].get("required", True)):
            findings.append(SchemaFinding("required_obligation_without_check", "$.checks", obligation_id))

    referenced_artifacts = {
        str(artifact_id)
        for row in step_binding_index.values()
        for artifact_id in row.get("output_artifact_ids", [])
    }
    for artifact_id, row in artifact_index.items():
        producer_step = str(row.get("producer_step_id", ""))
        if producer_step not in step_index:
            findings.append(SchemaFinding("artifact_unknown_producer", f"$.artifacts[{artifact_id}]", producer_step))
        if artifact_id not in referenced_artifacts:
            findings.append(SchemaFinding("orphan_artifact", f"$.artifacts[{artifact_id}]", artifact_id))

    previous_requirements: set[str] = set()
    profile_index = _index(binding.get("closure_profiles", []), "profile_id")
    for profile_id in CLOSURE_PROFILE_ORDER:
        row = profile_index.get(profile_id, {})
        requirements = {str(item) for item in row.get("required_obligation_ids", [])}
        if not previous_requirements.issubset(requirements):
            findings.append(
                SchemaFinding(
                    "non_monotonic_closure_profile",
                    f"$.closure_profiles[{profile_id}]",
                    "stronger profiles must include all weaker-profile obligations",
                )
            )
        previous_requirements = requirements

    for route_id, route in route_index.items():
        success_terminal = str(route.get("success_terminal_step_id", ""))
        terminal = step_index.get(success_terminal)
        if terminal is None or terminal.get("terminal_kind") != "success":
            findings.append(SchemaFinding("uncovered_success_terminal", f"$.routes[{route_id}]", success_terminal))
    return tuple(findings)


def _build_outputs(
    skill_id: str,
    model: Mapping[str, Any],
    binding: Mapping[str, Any],
    source_fingerprints: Mapping[str, str],
    compiled_checks: Sequence[Mapping[str, Any]],
    content_impact_plan: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    capability_contracts, capability_findings = (
        normalize_portfolio_capability_contracts(
            binding.get("portfolio_capability_contracts")
        )
    )
    if capability_findings:
        raise ValueError("capability contracts must be validated before compilation")
    model_path = str(binding.get("model_path", ""))
    check_declarations_hash = canonical_hash({"checks": list(compiled_checks)})
    step_binding_index = _index(binding.get("step_bindings", []), "step_id")
    bound_steps = []
    for step in model.get("steps", []):
        row = dict(step)
        binding_row = step_binding_index.get(str(step.get("step_id", "")))
        if binding_row is not None:
            row["binding"] = {
                "action": dict(binding_row.get("action", {})),
                "check_ids": list(binding_row.get("check_ids", [])),
                "output_artifact_ids": list(binding_row.get("output_artifact_ids", [])),
            }
        bound_steps.append(row)
    bound_step_index = _index(bound_steps, "step_id")
    obligation_check_ids: dict[str, list[str]] = {}
    for check in binding.get("checks", []):
        check_id = str(check.get("check_id", ""))
        for obligation_id in check.get("covers_obligation_ids", []):
            obligation_check_ids.setdefault(str(obligation_id), []).append(check_id)
    enriched_obligations: list[dict[str, Any]] = []
    for obligation in model.get("obligations", []):
        row = dict(obligation)
        obligation_id = str(row.get("obligation_id", ""))
        required_checks = sorted(dict.fromkeys(obligation_check_ids.get(obligation_id, [])))
        if required_checks:
            row["required_check_ids"] = required_checks
        evidence_classes = sorted(
            {
                required_evidence_class(bound_step_index[step_id])
                for step_id in (str(item) for item in row.get("owner_step_ids", []))
                if step_id in bound_step_index
            }
        )
        if evidence_classes:
            row["evidence_classes"] = evidence_classes
        enriched_obligations.append(row)
    contract: dict[str, Any] = {
        "schema_version": COMPILED_CONTRACT_SCHEMA,
        "compiler_version": COMPILER_VERSION,
        "skill_id": skill_id,
        "model_id": model["model_id"],
        "parent_model_id": model["parent_model_id"],
        "flowguard_schema_version": model["flowguard_schema_version"],
        "model_path": model_path,
        "functions": list(model["functions"]),
        "routes": list(model["routes"]),
        "steps": bound_steps,
        "obligations": enriched_obligations,
        "artifacts": list(binding.get("artifacts", [])),
        "portfolio_capability_contracts": capability_contracts,
        "closure_profiles": list(binding.get("closure_profiles", [])),
        "judgment_rubrics": list(binding.get("judgment_rubrics", [])),
        "check_declarations_hash": check_declarations_hash,
        "checks": list(compiled_checks),
        "source_fingerprints": dict(source_fingerprints),
        "content_impact_plan": dict(content_impact_plan),
        "claim_boundary": str(binding.get("claim_boundary", "")),
    }
    if "route_branch_closure_required" in binding:
        contract["route_branch_closure_required"] = binding[
            "route_branch_closure_required"
        ]
    if isinstance(binding.get("depth_profile"), Mapping):
        contract["depth_profile"] = dict(binding["depth_profile"])
    contract["contract_hash"] = canonical_hash(contract)
    manifest: dict[str, Any] = {
        "schema_version": CHECK_MANIFEST_SCHEMA,
        "compiler_version": COMPILER_VERSION,
        "skill_id": skill_id,
        "model_id": model["model_id"],
        "contract_hash": contract["contract_hash"],
        "check_declarations_hash": check_declarations_hash,
        "checks": list(compiled_checks),
        "source_fingerprints": dict(source_fingerprints),
        "content_impact_plan": dict(content_impact_plan),
        "claim_boundary": (
            "This manifest binds checks to exact model obligations. Passing checks do not by themselves "
            "prove target execution, user-visible quality, full closure, installation, or publication."
        ),
    }
    manifest["manifest_hash"] = canonical_hash(manifest)
    return contract, manifest


def compile_skill_contract(
    skill_root: Path,
    *,
    repository_root: Path | None = None,
    write: bool = False,
) -> CompileResult:
    skill_root = skill_root.resolve()
    repo_root = (repository_root or skill_root).resolve()
    control_root = skill_root / ".skillguard"
    binding_path = control_root / BINDING_SOURCE_FILE
    findings: list[SchemaFinding] = []
    try:
        binding = _load_json(binding_path)
    except ValueError as exc:
        return CompileResult(False, "blocked", (SchemaFinding("binding_source_unreadable", "$.binding", str(exc)),))
    binding_fingerprint = source_file_hash(binding_path)
    findings.extend(validate_binding_source(binding))
    model_path_text = str(binding.get("model_path", ""))
    try:
        model_path = _ensure_under(repo_root / model_path_text, repo_root, "$.model_path")
    except ValueError as exc:
        findings.append(SchemaFinding("model_path_outside_repository", "$.model_path", str(exc)))
        model_path = repo_root / "__invalid_model__"
    model: Mapping[str, Any] | None = None
    if not findings:
        try:
            snapshot = load_flowguard_model(model_path, repo_root)
            model = snapshot.model_export
        except FlowGuardAdapterError as exc:
            findings.extend(exc.findings)
    if model is not None:
        findings.extend(_cross_validate(model, binding, repo_root))
    if findings or model is None:
        return CompileResult(False, "blocked", tuple(findings))

    entrypoint = skill_root / "SKILL.md"
    source_fingerprints = {
        "model": source_file_hash(model_path),
        "binding": binding_fingerprint,
        "entrypoint": source_file_hash(entrypoint) if entrypoint.is_file() else "MISSING",
        "model_export": canonical_hash(model),
    }
    for index, path_text in enumerate(binding.get("implementation_paths", [])):
        try:
            implementation_path = _ensure_under(repo_root / str(path_text), repo_root, f"$.implementation_paths[{index}]")
            source_fingerprints[f"implementation:{Path(str(path_text)).as_posix()}"] = path_fingerprint(
                implementation_path,
                member_root=repository_root,
            )
        except ValueError as exc:
            findings.append(SchemaFinding("implementation_path_invalid", f"$.implementation_paths[{index}]", str(exc)))
    if findings:
        return CompileResult(False, "blocked", tuple(findings))
    compiled_checks = _compiled_checks(binding, model_path_text)
    content_impact_plan, compiled_checks, impact_findings = _build_content_impact_plan(
        binding=binding,
        compiled_checks=compiled_checks,
        repository_root=repo_root,
        skill_root=skill_root,
        binding_path=binding_path,
        model_path=model_path,
    )
    findings.extend(impact_findings)
    if findings:
        return CompileResult(False, "blocked", tuple(findings))
    contract, manifest = _build_outputs(
        str(binding["skill_id"]),
        model,
        binding,
        source_fingerprints,
        compiled_checks,
        content_impact_plan,
    )
    findings.extend(
        SchemaFinding(row.code, row.path, row.message)
        for row in capability_contract_topology_findings(
            contract.get("portfolio_capability_contracts", []),
            contract=contract,
            checks=manifest.get("checks", []),
        )
    )
    findings.extend(validate_compiled_contract(contract))
    findings.extend(validate_check_manifest(manifest))
    if findings:
        return CompileResult(False, "blocked", tuple(findings), contract, manifest)

    outputs = (
        (control_root / COMPILED_CONTRACT_FILE, contract),
        (control_root / CHECK_MANIFEST_FILE, manifest),
    )
    written: list[str] = []
    parity_findings: list[SchemaFinding] = []
    for path, payload in outputs:
        expected = canonical_json_bytes(payload)
        if write:
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.is_file() or path.read_bytes() != expected:
                path.write_bytes(expected)
                written.append(path.relative_to(skill_root).as_posix())
        elif not path.is_file():
            parity_findings.append(SchemaFinding("generated_file_missing", path.name, path.name))
        elif path.read_bytes() != expected:
            parity_findings.append(SchemaFinding("stale_generated_contract", path.name, path.name))
    all_findings = tuple(parity_findings)
    return CompileResult(
        ok=not all_findings,
        status="pass" if not all_findings else "blocked",
        findings=all_findings,
        compiled_contract=contract,
        check_manifest=manifest,
        written_files=tuple(written),
    )
