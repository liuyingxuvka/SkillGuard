"""Target-owned surface inventory validation and graduation readiness checks.

SkillGuard does not discover a target's domain surface or decide what the
surface means.  It verifies that the target supplied one explicit inventory,
that every row has an owner/intent/route/check disposition, and that the
declared adequacy and model-deepening checks are bound to the target profile.
The self-host helper additionally compares SkillGuard's inventory with its
actual public command and route registries; this is a target-native check, not
a generic domain evaluator.
"""

from __future__ import annotations

import hashlib
import ast
import inspect
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SURFACE_INVENTORY_SCHEMA = "skillguard.surface_inventory.v1"
SURFACE_DISPOSITIONS = frozenset(
    {"governed", "internal_proven", "retired_proven", "not_applicable_proven"}
)
MODEL_OBLIGATION_DISPOSITIONS = frozenset(
    {"governed", "model_only_proven", "retired_proven", "not_applicable_proven"}
)
SURFACE_KINDS = frozenset(
    {
        "command",
        "option",
        "route",
        "script",
        "dispatch",
        "api",
        "export",
        "template",
        "ui",
        "prompt",
        "config",
        "installer",
        "provider",
        "effect",
        "fault",
        "artifact",
        "recovery",
        "component",
        "other",
    }
)
FULL_SURFACE_CATEGORIES = (
    "command",
    "api",
    "script",
    "route",
    "template",
    "config",
    "installer",
    "ui",
    "effect",
    "fault",
    "recovery",
    "artifact",
    "provider",
    "component",
)
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}$")
_UNKNOWN_OWNER_SENTINELS = frozenset(
    {"", "?", "none", "null", "unknown", "unassigned", "unowned", "tbd", "todo"}
)
_COMPONENT_REVIEW_KINDS = frozenset(
    {"effect", "fault", "recovery", "provider", "component"}
)


def _review_group_for_surface(
    *,
    kind: str,
    source_path: str,
    function_id: str,
    surface_id: str,
) -> tuple[str, str]:
    """Return the human-review unit for one source observation.

    A source line is never a review unit.  Registry-visible commands, routes,
    scripts, APIs, configs, templates, and UI/actions stay individually
    addressable.  Derived implementation facets (effect/fault/recovery/
    provider observations) are grouped by their owning source component so a
    single component-level proof can cover the facet set without pretending
    that each AST observation is a new public feature.
    """

    granularity = "component" if kind in _COMPONENT_REVIEW_KINDS else "surface"
    # Component observations are deliberately grouped at the owning source
    # component boundary, not at the AST function or source-line boundary.
    # ``function_id`` remains useful provenance on the row, but it must not
    # manufacture a new review unit for every helper that happens to emit an
    # effect/fault/recovery/provider facet.  A target may later choose a
    # narrower explicit component boundary, but that boundary must be a
    # stable author-owned identity rather than an incidental line number.
    basis = source_path if granularity == "component" else surface_id
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]
    return f"group:{granularity}:{digest}", granularity


@dataclass(frozen=True)
class PublicSourceSurface:
    """One source-derived public surface discovered by the reverse scan.

    This is deliberately a small structural projection.  It identifies the
    source path and the symbol/route identity that a target inventory must
    account for; it does not claim that the surface is semantically correct or
    that its native checks passed.
    """

    surface_id: str
    kind: str
    name: str
    source_path: str
    source_fingerprint: str
    function_id: str
    route_id: str
    review_group_id: str = ""
    review_granularity: str = ""
    component_members: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.review_group_id and self.review_granularity:
            return
        group_id, granularity = _review_group_for_surface(
            kind=self.kind,
            source_path=self.source_path,
            function_id=self.function_id,
            surface_id=self.surface_id,
        )
        object.__setattr__(self, "review_group_id", group_id)
        object.__setattr__(self, "review_granularity", granularity)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "surface_id": self.surface_id,
            "kind": self.kind,
            "name": self.name,
            "source_path": self.source_path,
            "source_fingerprint": self.source_fingerprint,
            "function_id": self.function_id,
            "route_id": self.route_id,
            "review_group_id": self.review_group_id,
            "review_granularity": self.review_granularity,
        }
        if self.component_members:
            payload["component_members"] = list(self.component_members)
        return payload


@dataclass(frozen=True)
class PublicSourceSurfaceScan:
    """Result of discovering the bounded source-side public surface."""

    surfaces: tuple[PublicSourceSurface, ...]
    findings: tuple["SurfaceInventoryFinding", ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "surface_count": len(self.surfaces),
            "surfaces": [surface.to_dict() for surface in self.surfaces],
            "review_group_count": len({surface.review_group_id for surface in self.surfaces}),
            "review_granularity_counts": {
                granularity: sum(
                    1 for surface in self.surfaces
                    if surface.review_granularity == granularity
                )
                for granularity in ("component", "surface")
            },
            "findings": [finding.to_dict() for finding in self.findings],
        }


@dataclass(frozen=True)
class FullSourceSurfaceScan:
    """Deterministic reverse discovery over the target's production surface.

    This is a source observation, not a semantic model.  The target must
    author the intent, owner, adequacy envelope, and typed disposition for
    every observed row before graduation; names are never treated as intent.
    """

    surfaces: tuple[PublicSourceSurface, ...]
    source_paths: tuple[str, ...]
    findings: tuple["SurfaceInventoryFinding", ...]
    discovery_fingerprint: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "skillguard.full_surface_discovery.v1",
            "source_paths": list(self.source_paths),
            "surface_count": len(self.surfaces),
            "surfaces": [surface.to_dict() for surface in self.surfaces],
            "review_group_count": len({surface.review_group_id for surface in self.surfaces}),
            "review_granularity_counts": {
                granularity: sum(
                    1 for surface in self.surfaces
                    if surface.review_granularity == granularity
                )
                for granularity in ("component", "surface")
            },
            "findings": [finding.to_dict() for finding in self.findings],
            "discovery_fingerprint": self.discovery_fingerprint,
            "claim_boundary": (
                "Source observation only; it does not decide target intent, "
                "domain correctness, or a typed disposition."
            ),
        }


@dataclass(frozen=True)
class SurfaceInventoryFinding:
    """One stable, public-safe inventory failure."""

    code: str
    path: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "detail": self.detail}


def _finding(code: str, path: str, detail: object = "") -> SurfaceInventoryFinding:
    return SurfaceInventoryFinding(code, path, str(detail))


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _wire_hash(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _source_fingerprint(path: Path) -> str:
    """Return the current semantic identity for one discovered source file.

    ``large_text_review_records`` in the public-export policy are
    hash-bound evidence about a generated inventory, not implementation
    semantics. Including those rows in the reverse source identity creates a
    policy -> inventory -> policy cycle and makes every reseal stale. Keep all
    policy bytes authoritative except that evidence-only field; the privacy
    owner still checks the exact file hash itself.
    """

    if path.name == "public-export-policy.json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            # Invalid policy bytes retain their exact identity so policy
            # validation fails closed instead of hiding the error.
            return _wire_hash(path.read_bytes())
        if isinstance(payload, dict) and "large_text_review_records" in payload:
            payload = dict(payload)
            payload.pop("large_text_review_records", None)
            return _wire_hash(_canonical_bytes(payload))
    return _wire_hash(path.read_bytes())


def surface_inventory_hash(payload: Mapping[str, Any]) -> str:
    """Hash an inventory without its self-referential ``inventory_hash``."""

    unsigned = dict(payload)
    unsigned.pop("inventory_hash", None)
    return _wire_hash(_canonical_bytes(unsigned))


def _text(value: object) -> str:
    return str(value).strip() if isinstance(value, str) else ""


def _ids(value: object, *, path: str, findings: list[SurfaceInventoryFinding]) -> list[str]:
    if not isinstance(value, list):
        findings.append(_finding("surface_inventory_ids_invalid", path, "a list of ids is required"))
        return []
    result: list[str] = []
    for index, item in enumerate(value):
        text = _text(item)
        if not text or not _ID_RE.fullmatch(text):
            findings.append(_finding("surface_inventory_id_invalid", f"{path}[{index}]", item))
        result.append(text)
    if len(result) != len(set(result)):
        findings.append(_finding("surface_inventory_id_duplicate", path, "ids must be unique"))
    return result


def _owner_ids(
    value: object,
    *,
    path: str,
    findings: list[SurfaceInventoryFinding],
) -> list[str]:
    """Validate the explicit target-owned owner universe.

    Owner identity is part of the current surface authority.  There is no
    compatibility read that treats a missing registry as an unbounded owner
    universe.
    """

    if not isinstance(value, list):
        findings.append(
            _finding(
                "surface_owner_registry_missing",
                path,
                "a non-empty list of owner ids is required",
            )
        )
        return []
    owners = _ids(value, path=path, findings=findings)
    if not owners:
        findings.append(
            _finding(
                "surface_owner_registry_missing",
                path,
                "at least one target-owned owner id is required",
            )
        )
    if len(owners) != len(set(owners)):
        findings.append(
            _finding(
                "surface_owner_id_duplicate",
                path,
                "owner ids must be unique",
            )
        )
    return owners


def _owner_sentinel(value: object) -> bool:
    return _text(value).casefold() in _UNKNOWN_OWNER_SENTINELS


def _paths(value: object, *, path: str, findings: list[SurfaceInventoryFinding]) -> list[str]:
    if not isinstance(value, list):
        findings.append(_finding("surface_inventory_paths_invalid", path, "a list of paths is required"))
        return []
    result: list[str] = []
    for index, item in enumerate(value):
        text = _text(item)
        if not text:
            findings.append(_finding("surface_inventory_path_invalid", f"{path}[{index}]", item))
        result.append(text)
    if not result:
        findings.append(_finding("surface_inventory_paths_missing", path, "at least one target-owned source path is required"))
    if len(result) != len(set(result)):
        findings.append(_finding("surface_inventory_path_duplicate", path, "paths must be unique"))
    return result


def _validate_path(path: str, findings: list[SurfaceInventoryFinding]) -> None:
    if not path:
        findings.append(_finding("surface_inventory_path_missing", "$.path", "target-owned inventory path is required"))
    if Path(path).is_absolute() or any(part == ".." for part in Path(path).parts):
        findings.append(_finding("surface_inventory_path_unsafe", "$.path", path))


def _is_main_guard(test: ast.AST) -> bool:
    """Return whether an AST test is the conventional Python entry guard."""

    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
        return False
    if not isinstance(test.left, ast.Name) or test.left.id != "__name__":
        return False
    return any(isinstance(value, ast.Constant) and value.value == "__main__" for value in test.comparators)


def _module_name_for_source(path: Path, scripts_root: Path) -> str:
    relative = path.relative_to(scripts_root).with_suffix("")
    parts = list(relative.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _source_module_index(scripts_root: Path) -> tuple[dict[str, tuple[Path, set[str], bool, dict[str, str]]], list[SurfaceInventoryFinding]]:
    """Parse script modules and return (path, functions, main-guard) metadata."""

    index: dict[str, tuple[Path, set[str], bool, dict[str, str]]] = {}
    findings: list[SurfaceInventoryFinding] = []
    if not scripts_root.is_dir():
        return index, [_finding("surface_source_root_missing", "$.source_paths", scripts_root)]
    for path in sorted(scripts_root.rglob("*.py")):
        relative = path.relative_to(scripts_root.parent.parent).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        except (OSError, UnicodeError, SyntaxError) as exc:
            findings.append(_finding("surface_source_parse_failed", relative, exc))
            continue
        functions = {
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        main_guard = any(isinstance(node, ast.If) and _is_main_guard(node.test) for node in tree.body)
        imports: dict[str, str] = {}
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                for alias in node.names:
                    imports[alias.asname or alias.name] = f"{node.module}.{alias.name}"
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    local = alias.asname or alias.name.split(".", 1)[0]
                    imports[local] = alias.name
        index[_module_name_for_source(path, scripts_root)] = (path, functions, main_guard, imports)
    return index, findings


def discover_public_source_surfaces(
    target_root: Path,
    *,
    command_surface: Sequence[Mapping[str, Any]],
    route_entries: Sequence[Mapping[str, Any]],
    command_handlers: Mapping[str, Any] | None = None,
) -> PublicSourceSurfaceScan:
    """Discover bounded Python entry scripts, dispatch functions, and routes.

    The scan intentionally has a narrow, deterministic boundary:

    * Python files below ``<target>/scripts`` with a conventional
      ``if __name__ == "__main__"`` guard are entry-script surfaces.
    * ``dispatch_function`` values in the current command surface must resolve
      to a top-level function in the matching source module.
    * Every current route-registry entry is a route surface.

    No arbitrary private helper is promoted to a public surface.  A missing or
    unparsable source module is a finding and therefore blocks the reverse
    inventory check instead of being silently omitted.
    """

    target = target_root.resolve()
    scripts_root = target / "scripts"
    module_index, findings = _source_module_index(scripts_root)
    surfaces: list[PublicSourceSurface] = []

    for module, (path, _functions, main_guard, _imports) in sorted(module_index.items()):
        if not main_guard:
            continue
        relative = path.relative_to(target).as_posix()
        main_function = f"{module}.main"
        if "main" not in _functions:
            findings.append(_finding("surface_entry_function_missing", relative, main_function))
        surfaces.append(
            PublicSourceSurface(
                surface_id=f"script:{relative}",
                kind="script",
                name=relative,
                source_path=relative,
                source_fingerprint=_source_fingerprint(path),
                function_id=main_function,
                route_id=f"entry:{relative}",
            )
        )

    route_by_command: dict[str, Mapping[str, Any]] = {}
    seen_route_ids: set[str] = set()
    seen_route_commands: set[str] = set()
    for index, entry in enumerate(route_entries):
        route_path = f"$.route_registry[{index}]"
        if not isinstance(entry, Mapping):
            findings.append(_finding("surface_route_entry_invalid", route_path, "an object is required"))
            continue
        if _text(entry.get("status") or "current") != "current":
            continue
        route_id = _text(entry.get("route_id"))
        command_family = _text(entry.get("command_family"))
        if not route_id:
            findings.append(_finding("surface_route_identity_missing", f"{route_path}.route_id", "current routes need an id"))
        elif route_id in seen_route_ids:
            findings.append(_finding("surface_route_identity_duplicate", f"{route_path}.route_id", route_id))
        else:
            seen_route_ids.add(route_id)
        if not command_family:
            findings.append(_finding("surface_route_command_missing", f"{route_path}.command_family", "current routes need a command family"))
        elif command_family in seen_route_commands:
            findings.append(_finding("surface_route_command_duplicate", f"{route_path}.command_family", command_family))
        else:
            seen_route_commands.add(command_family)
        if command_family and command_family not in route_by_command:
            route_by_command[command_family] = entry
    command_by_dispatch: dict[str, Mapping[str, Any]] = {}
    seen_command_names: set[str] = set()
    for index, command in enumerate(command_surface):
        command_path = f"$.command_surface[{index}]"
        if not isinstance(command, Mapping):
            findings.append(_finding("surface_command_entry_invalid", command_path, "an object is required"))
            continue
        command_name = _text(command.get("name"))
        if not command_name:
            findings.append(_finding("surface_command_name_missing", f"{command_path}.name", "public commands need a name"))
        elif command_name in seen_command_names:
            findings.append(_finding("surface_command_name_duplicate", f"{command_path}.name", command_name))
        else:
            seen_command_names.add(command_name)
        dispatch = _text(command.get("dispatch_function"))
        if not dispatch:
            findings.append(_finding("surface_dispatch_function_missing", f"{command_path}.dispatch_function", command_name))
            continue
        if dispatch in command_by_dispatch:
            findings.append(_finding("surface_dispatch_function_duplicate", f"{command_path}.dispatch_function", dispatch))
            continue
        command_by_dispatch[dispatch] = command

    for dispatch, command in sorted(command_by_dispatch.items()):
        module, separator, symbol = dispatch.rpartition(".")
        metadata = module_index.get(module) if separator else None
        command_name = _text(command.get("name")) or dispatch
        handler = command_handlers.get(command_name) if isinstance(command_handlers, Mapping) else None
        source_fingerprint = ""
        if handler is not None:
            actual_module = _text(getattr(handler, "__module__", ""))
            actual_symbol = _text(getattr(handler, "__name__", ""))
            actual_metadata = module_index.get(actual_module)
            if actual_metadata is not None:
                resolved_path, resolved_functions, _guard, _imports = actual_metadata
                if actual_symbol not in resolved_functions:
                    findings.append(_finding("surface_dispatch_symbol_missing", dispatch, resolved_path.relative_to(target).as_posix()))
                source_path = resolved_path.relative_to(target).as_posix()
                source_fingerprint = _source_fingerprint(resolved_path)
            else:
                source_file = inspect.getsourcefile(handler)
                source_path = ""
                if source_file:
                    try:
                        source_path = Path(source_file).resolve().relative_to(target).as_posix()
                    except ValueError:
                        source_path = ""
                if not source_path:
                    findings.append(_finding("surface_dispatch_source_missing", dispatch, actual_module or "handler source"))
        elif metadata is None:
            findings.append(_finding("surface_dispatch_source_missing", dispatch, "module was not found below scripts/"))
            source_path = ""
        else:
            path, functions, _main_guard, imports = metadata
            resolved_path = path
            resolved_functions = functions
            if symbol not in resolved_functions and symbol in imports:
                imported_module, _separator, imported_symbol = imports[symbol].rpartition(".")
                imported_metadata = module_index.get(imported_module)
                if imported_metadata is not None:
                    resolved_path, resolved_functions, _unused_guard, _unused_imports = imported_metadata
                    if imported_symbol not in resolved_functions:
                        findings.append(_finding("surface_dispatch_symbol_missing", dispatch, resolved_path.relative_to(target).as_posix()))
                else:
                    findings.append(_finding("surface_dispatch_source_missing", dispatch, imports[symbol]))
            elif symbol not in resolved_functions:
                findings.append(_finding("surface_dispatch_symbol_missing", dispatch, path.relative_to(target).as_posix()))
            source_path = resolved_path.relative_to(target).as_posix()
            source_fingerprint = _source_fingerprint(resolved_path)
        route = route_by_command.get(command_name, {})
        route_id = _text(route.get("route_id")) or f"command:{command_name}"
        surfaces.append(
            PublicSourceSurface(
                surface_id=f"dispatch:{dispatch}",
                kind="dispatch",
                name=dispatch,
                source_path=source_path,
                source_fingerprint=source_fingerprint,
                function_id=dispatch,
                route_id=route_id,
            )
        )

    for route in sorted(
        (entry for entry in route_entries if isinstance(entry, Mapping)),
        key=lambda item: _text(item.get("route_id")),
    ):
        if not isinstance(route, Mapping) or _text(route.get("status") or "current") != "current":
            continue
        route_id = _text(route.get("route_id"))
        command_family = _text(route.get("command_family"))
        if not route_id or not command_family:
            # The first pass records field-specific findings.  Do not emit a
            # second generic finding for the same malformed route.
            continue
        surfaces.append(
            PublicSourceSurface(
                surface_id=f"route:{route_id}",
                kind="route",
                name=command_family,
                source_path="scripts/checker_engine.py",
                source_fingerprint=_source_fingerprint(target / "scripts" / "checker_engine.py"),
                function_id=f"route:{route_id}",
                route_id=route_id,
            )
        )

    return PublicSourceSurfaceScan(tuple(surfaces), tuple(findings))


_FULL_SOURCE_SUFFIXES = frozenset(
    {".py", ".json", ".toml", ".yaml", ".yml", ".md", ".txt"}
)
_FULL_SKIP_PARTS = frozenset(
    {
        ".git",
        ".pytest_cache",
        "__pycache__",
        ".venv",
        "venv",
        "build",
        "dist",
        "node_modules",
        "runs",
        "evidence",
        # The target's work tree contains generated plans, diagnostics,
        # launcher output, and other transient evidence-production material.
        # These files are not implementation surfaces and must not enlarge
        # the reverse denominator or make a sealed inventory stale merely
        # because a validation run created a new report.
        "work",
        "model-mesh",
        "model-system",
        "tmp",
    }
)
_FULL_CONFIG_NAMES = frozenset(
    {
        "pyproject.toml",
        "setup.cfg",
        "tox.ini",
        "pytest.ini",
        "mypy.ini",
        "test-mesh.json",
        "public-export-policy.json",
        "contract-source.json",
        "compiled-contract.json",
        "check-manifest.json",
    }
)
_FULL_INSTALL_RE = re.compile(
    r"(?:^|[._-])(install|uninstall|upgrade|bootstrap|stage|activate|rollback|recover|recovery|restore|sync)(?:$|[._-])",
    re.IGNORECASE,
)
_FULL_PROVIDER_RE = re.compile(r"(?:provider|platform|runtime|enroll|capabilit)", re.IGNORECASE)
_FULL_UI_RE = re.compile(r"(?:button|click|on_click|onclick|menu|control|submit|navigate|select|action|confirm|prompt|interactive)", re.IGNORECASE)
_FULL_FAULT_RE = re.compile(r"(?:error|exception|invalid|reject|fail|fault|denied|timeout|cancel|interrupt|stale|corrupt)", re.IGNORECASE)
_FULL_RECOVERY_RE = re.compile(r"(?:retry|resume|rollback|recover|cleanup|restore|repair|reconnect|close|idempotent)", re.IGNORECASE)
_FULL_EFFECT_NAMES = frozenset(
    {
        "write_text",
        "write_bytes",
        "unlink",
        "remove",
        "rmdir",
        "mkdir",
        "rename",
        "replace",
        "copy",
        "copy2",
        "move",
        "rmtree",
        "run",
        "run_sync",
        "popen",
        "system",
        "chmod",
        "touch",
    }
)


def _full_call_name(node: ast.Call) -> str:
    value: ast.AST = node.func
    parts: list[str] = []
    while isinstance(value, ast.Attribute):
        parts.append(value.attr)
        value = value.value
    if isinstance(value, ast.Name):
        parts.append(value.id)
    return ".".join(reversed(parts))


def _full_module_name(path: Path, root: Path) -> str:
    relative = path.relative_to(root).with_suffix("")
    parts = list(relative.parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts) or path.stem


def _full_is_source_file(path: Path, root: Path) -> bool:
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    if path.suffix.lower() not in _FULL_SOURCE_SUFFIXES:
        return False
    if any(part in _FULL_SKIP_PARTS for part in relative.parts):
        return False
    # Runtime reports are evidence outputs, not implementation surfaces.  A
    # report created by a self-check must never enlarge its own reverse
    # denominator or make a previously sealed inventory stale.
    if (
        len(relative.parts) >= 2
        and relative.parts[0] == ".skillguard"
        and relative.parts[1] in {"reports", "test-results"}
    ):
        return False
    # The inventory is a derived evidence projection.  Including its own
    # bytes would create a self-referential discovery fingerprint and make
    # every reseal stale immediately.
    if relative.as_posix() in {
        ".skillguard/surface-inventory.json",
        # The semantic map is the target-owned authoring source for that
        # derived inventory.  Its bytes are already bound by the inventory's
        # explicit model-obligation joins; observing it as implementation
        # code would create the same self-referential fingerprint loop.
        ".skillguard/surface-semantic-map.json",
    }:
        return False
    # These files are compiler outputs, not independent implementation
    # surfaces.  Discovering them would make the reverse inventory depend on
    # the hashes of its own generated contract/manifest, while the compiler
    # already owns their exact currentness.  Keep them in the derived-artifact
    # checks, but out of the source-surface denominator.
    if relative.as_posix() in {
        ".skillguard/compiled-contract.json",
        ".skillguard/check-manifest.json",
        # Functional closure is receipt-backed author evidence.  It is
        # deliberately source-only and must not become an implementation
        # surface whose bytes invalidate the reverse denominator whenever a
        # current closure is resealed.
        ".skillguard/functional-closure.json",
    }:
        return False
    # Tests are evidence consumers, not production surface observations.
    if any(part.casefold() in {"tests", "test", "fixtures"} for part in relative.parts):
        return False
    return True


def _full_source_files(root: Path) -> tuple[Path, ...]:
    files = tuple(
        path
        for path in sorted(root.rglob("*"))
        if path.is_file() and _full_is_source_file(path, root)
    )
    return files


def _private_component_members(tree: ast.AST) -> tuple[str, ...]:
    """Return top-level private implementation members as one component.

    A private helper is not promoted to an intent or a one-row-per-function
    contract.  The source file is the review unit: all behavior-significant
    private functions/classes in that file must be covered by the component
    row's one target-owned intent/owner/check/evidence envelope.  Dunder
    protocol methods are excluded because they are class internals rather than
    independently discoverable top-level components.
    """

    members: list[str] = []
    for node in getattr(tree, "body", ()):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if node.name.startswith("_") and not node.name.startswith("__"):
            members.append(node.name)
    return tuple(sorted(set(members)))


def _literal_option_strings(node: ast.AST) -> tuple[str, ...]:
    """Extract CLI option strings from one ``add_argument`` positional list.

    This is deliberately limited to literal option names.  It never executes
    target code and it does not treat arbitrary string constants as a public
    option.  A target that constructs an option name dynamically therefore
    produces an explicit discovery gap rather than a guessed surface.
    """

    values: list[str] = []
    candidates: Iterable[ast.AST]
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        candidates = node.elts
    else:
        candidates = (node,)
    for candidate in candidates:
        if isinstance(candidate, ast.Constant) and isinstance(candidate.value, str):
            value = candidate.value.strip()
            if value.startswith("-"):
                values.append(value)
    return tuple(values)


def _source_command_options(
    target_root: Path,
    command_surface: Sequence[Mapping[str, Any]],
    command_handlers: Mapping[str, Any] | None = None,
) -> tuple[dict[str, tuple[str, ...]], dict[str, str]]:
    """Discover literal parser options for the current command handlers.

    Commands are the review unit; options are only a child surface of their
    owning handler.  The small AST call walk follows helpers defined in the
    same module (for example the shared ``--input/--output`` parser) without
    executing the CLI or assigning one intent to every source line.
    """

    source_files = _full_source_files(target_root.resolve())
    module_functions: dict[str, dict[str, ast.AST]] = {}
    module_imports: dict[str, dict[str, tuple[str, str]]] = {}
    for path in source_files:
        if path.suffix.lower() != ".py":
            continue
        try:
            tree = ast.parse(
                path.read_text(encoding="utf-8"),
                filename=path.relative_to(target_root).as_posix(),
            )
        except (OSError, UnicodeError, SyntaxError):
            continue
        module = _full_module_name(path, target_root)
        module_functions[module] = {
            node.name: node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        imports: dict[str, tuple[str, str]] = {}
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                for alias in node.names:
                    imports[alias.asname or alias.name] = (node.module, alias.name)
        module_imports[module] = imports

    by_stem: dict[str, list[str]] = {}
    for module in module_functions:
        by_stem.setdefault(module.rsplit(".", 1)[-1], []).append(module)

    def resolve_module(module_hint: str) -> str | None:
        if module_hint in module_functions:
            return module_hint
        candidates = by_stem.get(module_hint.rsplit(".", 1)[-1], [])
        return candidates[0] if len(candidates) == 1 else None

    def collect(module: str, name: str, visiting: set[tuple[str, str]]) -> set[str]:
        key = (module, name)
        if key in visiting:
            return set()
        visiting.add(key)
        node = module_functions.get(module, {}).get(name)
        if node is None:
            imported = module_imports.get(module, {}).get(name)
            if imported is None:
                visiting.remove(key)
                return set()
            imported_module, imported_name = imported
            resolved = resolve_module(imported_module)
            result = (
                collect(resolved, imported_name, visiting)
                if resolved is not None and imported_name in module_functions.get(resolved, {})
                else set()
            )
            visiting.remove(key)
            return result
        result: set[str] = set()
        imports = module_imports.get(module, {})
        for call in ast.walk(node):
            if not isinstance(call, ast.Call):
                continue
            if isinstance(call.func, ast.Attribute) and call.func.attr == "add_argument":
                for arg in call.args:
                    result.update(_literal_option_strings(arg))
            if isinstance(call.func, ast.Name):
                child_name = call.func.id
                if child_name in module_functions.get(module, {}):
                    result.update(collect(module, child_name, visiting))
                elif child_name in imports:
                    imported_module, imported_name = imports[child_name]
                    resolved = resolve_module(imported_module)
                    if resolved is not None and imported_name in module_functions.get(resolved, {}):
                        result.update(collect(resolved, imported_name, visiting))
        visiting.remove(key)
        return result

    options_by_dispatch: dict[str, tuple[str, ...]] = {}
    source_paths_by_dispatch: dict[str, str] = {}
    for command in command_surface:
        if not isinstance(command, Mapping):
            continue
        dispatch = _text(command.get("dispatch_function"))
        if not dispatch:
            continue
        command_name = _text(command.get("name"))
        handler = command_handlers.get(command_name) if isinstance(command_handlers, Mapping) else None
        module_hint = _text(getattr(handler, "__module__", ""))
        symbol = _text(getattr(handler, "__name__", ""))
        if not module_hint or not symbol:
            module_hint, separator, symbol = dispatch.rpartition(".")
        else:
            separator = "."
        resolved_module = resolve_module(module_hint) if separator else None
        discovered = collect(resolved_module, symbol, set()) if resolved_module else set()
        declared = command.get("options", command.get("option_names", ()))
        if isinstance(declared, Mapping):
            declared = tuple(declared.values())
        if isinstance(declared, Sequence) and not isinstance(declared, (str, bytes, bytearray)):
            for item in declared:
                if isinstance(item, Mapping):
                    discovered.update(_literal_option_strings(ast.Constant(value=_text(item.get("name")))))
                else:
                    discovered.update(_literal_option_strings(ast.Constant(value=_text(item))))
        options_by_dispatch[dispatch] = tuple(sorted(discovered))
        if resolved_module:
            resolved_path = module_functions[resolved_module].get(symbol)
            if resolved_path is not None:
                # The AST node does not retain its file; resolve the module
                # path deterministically from the module name instead.
                module_parts = resolved_module.split(".")
                candidates = [
                    path
                    for path in source_files
                    if path.suffix.lower() == ".py"
                    and _full_module_name(path, target_root) == resolved_module
                ]
                if candidates:
                    source_paths_by_dispatch[dispatch] = candidates[0].relative_to(target_root).as_posix()
        if dispatch not in source_paths_by_dispatch and handler is not None:
            source_file = inspect.getsourcefile(handler)
            if source_file:
                try:
                    source_paths_by_dispatch[dispatch] = Path(source_file).resolve().relative_to(target_root.resolve()).as_posix()
                except ValueError:
                    pass
    return options_by_dispatch, source_paths_by_dispatch


def discover_full_source_surfaces(
    target_root: Path,
    *,
    command_surface: Sequence[Mapping[str, Any]] = (),
    route_entries: Sequence[Mapping[str, Any]] = (),
    command_handlers: Mapping[str, Any] | None = None,
) -> FullSourceSurfaceScan:
    """Discover the broad production denominator without inferring intent.

    The command/route registries are only observation inputs.  Python AST,
    configuration, template, installer/effect, UI-like, and fault/recovery
    observations are added from the current source tree.  A malformed source,
    an over-budget tree, or a duplicate surface id is returned as a finding;
    callers must block instead of dropping the row or using a fallback scan.
    """

    root = target_root.resolve()
    files = _full_source_files(root)
    findings: list[SurfaceInventoryFinding] = []
    surfaces: list[PublicSourceSurface] = []
    seen: set[str] = set()
    discovered_command_options, option_source_paths = _source_command_options(
        root,
        command_surface,
        command_handlers,
    )

    if len(files) > 2_000:
        findings.append(_finding("full_surface_source_budget_exceeded", "$.source_paths", len(files)))

    def add(
        *,
        surface_id: str,
        kind: str,
        name: str,
        source_path: str,
        function_id: str,
        route_id: str,
        component_members: Sequence[str] = (),
    ) -> None:
        if surface_id in seen:
            findings.append(_finding("full_surface_id_duplicate", "$.surfaces", surface_id))
            return
        seen.add(surface_id)
        surfaces.append(
            PublicSourceSurface(
                surface_id=surface_id,
                kind=kind,
                name=name,
                source_path=source_path,
                source_fingerprint=_source_fingerprint(root / source_path),
                function_id=function_id,
                route_id=route_id,
                component_members=tuple(sorted(set(component_members))),
            )
        )

    # Registry-backed behavior surfaces are observed independently of source
    # names; a missing/duplicate identity is itself a blocker.
    command_names: set[str] = set()
    command_source_paths: dict[str, str] = {}
    for index, command in enumerate(command_surface):
        path = f"$.command_surface[{index}]"
        if not isinstance(command, Mapping):
            findings.append(_finding("full_surface_command_invalid", path, "an object is required"))
            continue
        name = _text(command.get("name"))
        dispatch = _text(command.get("dispatch_function"))
        if not name or not dispatch:
            findings.append(_finding("full_surface_command_identity_missing", path, name or dispatch))
            continue
        if name in command_names:
            findings.append(_finding("full_surface_command_duplicate", path, name))
            continue
        command_names.add(name)
        route = next(
            (
                row
                for row in route_entries
                if isinstance(row, Mapping)
                and _text(row.get("status") or "current") == "current"
                and _text(row.get("command_family")) == name
            ),
            {},
        )
        route_id = _text(route.get("route_id")) or f"command:{name}"
        command_source_path = option_source_paths.get(dispatch, "scripts/checker_engine.py")
        command_source_paths[name] = command_source_path
        add(
            surface_id=f"command:{name}",
            kind="command",
            name=name,
            source_path=command_source_path,
            function_id=dispatch,
            route_id=route_id,
        )
        options = command.get("options", command.get("option_names", ()))
        if isinstance(options, Mapping):
            options = tuple(options)
        option_names: set[str] = set(discovered_command_options.get(dispatch, ()))
        if isinstance(options, Sequence) and not isinstance(options, (str, bytes, bytearray)):
            for option in options:
                option_name = _text(option.get("name")) if isinstance(option, Mapping) else _text(option)
                if option_name:
                    option_names.add(option_name)
        option_source_path = command_source_path
        for option_name in sorted(option_names):
            add(
                surface_id=f"option:{name}:{option_name}",
                kind="option",
                name=f"{name} {option_name}",
                source_path=option_source_path,
                function_id=dispatch,
                route_id=route_id,
            )

    route_ids: set[str] = set()
    for index, route in enumerate(route_entries):
        path = f"$.route_registry[{index}]"
        if not isinstance(route, Mapping) or _text(route.get("status") or "current") != "current":
            continue
        route_id = _text(route.get("route_id"))
        command_family = _text(route.get("command_family"))
        if not route_id or not command_family:
            findings.append(_finding("full_surface_route_identity_missing", path, route_id or command_family))
            continue
        if route_id in route_ids:
            findings.append(_finding("full_surface_route_duplicate", path, route_id))
            continue
        route_ids.add(route_id)
        route_source_path = _text(route.get("source_path")) or command_source_paths.get(command_family, "")
        if not route_source_path:
            candidates = [path for path in files if path.suffix.lower() == ".py"]
            if candidates:
                route_source_path = candidates[0].relative_to(root).as_posix()
        if not route_source_path or not (root / route_source_path).is_file():
            findings.append(_finding("full_surface_route_source_missing", path, command_family))
            continue
        add(
            surface_id=f"route:{route_id}",
            kind="route",
            name=command_family,
            source_path=route_source_path,
            function_id=f"route:{route_id}",
            route_id=route_id,
        )

    for path in files:
        relative = path.relative_to(root).as_posix()
        suffix = path.suffix.lower()
        if suffix == ".py":
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
            except (OSError, UnicodeError, SyntaxError) as exc:
                findings.append(_finding("full_surface_source_parse_failed", relative, exc))
                continue
            module = _full_module_name(path, root)
            private_members = _private_component_members(tree)
            if any(isinstance(node, ast.If) and _is_main_guard(node.test) for node in tree.body):
                add(
                    surface_id=f"script:{relative}",
                    kind="script",
                    name=relative,
                    source_path=relative,
                    function_id=f"{module}.main",
                    route_id=f"entry:{relative}",
                )
            exported: set[str] = set()
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "__all__" and isinstance(node.value, (ast.List, ast.Tuple)):
                            exported.update(
                                item.value
                                for item in node.value.elts
                                if isinstance(item, ast.Constant) and isinstance(item.value, str)
                            )
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    name = node.name
                    if name.startswith("_") and name not in exported:
                        continue
                    add(
                        surface_id=f"api:{relative}:{name}",
                        kind="api" if name not in exported else "export",
                        name=f"{module}.{name}",
                        source_path=relative,
                        function_id=f"{module}.{name}",
                        route_id=f"api:{module}.{name}",
                    )
                    calls = tuple(
                        _full_call_name(call)
                        for call in ast.walk(node)
                        if isinstance(call, ast.Call)
                    )
                    joined = " ".join(calls) + " " + name
                    if any(call.rsplit(".", 1)[-1] in _FULL_EFFECT_NAMES for call in calls):
                        add(
                            surface_id=f"effect:{relative}:{name}",
                            kind="effect",
                            name=f"{module}.{name}",
                            source_path=relative,
                            function_id=f"{module}.{name}",
                            route_id=f"effect:{module}.{name}",
                        )
                    if _FULL_INSTALL_RE.search(joined):
                        add(
                            surface_id=f"installer:{relative}:{name}",
                            kind="installer",
                            name=f"{module}.{name}",
                            source_path=relative,
                            function_id=f"{module}.{name}",
                            route_id=f"install:{module}.{name}",
                        )
                    if _FULL_UI_RE.search(joined):
                        add(
                            surface_id=f"ui:{relative}:{name}",
                            kind="ui",
                            name=f"{module}.{name}",
                            source_path=relative,
                            function_id=f"{module}.{name}",
                            route_id=f"ui:{module}.{name}",
                        )
                    if _FULL_FAULT_RE.search(joined):
                        add(
                            surface_id=f"fault:{relative}:{name}",
                            kind="fault",
                            name=f"{module}.{name}",
                            source_path=relative,
                            function_id=f"{module}.{name}",
                            route_id=f"fault:{module}.{name}",
                        )
                    if _FULL_RECOVERY_RE.search(joined):
                        add(
                            surface_id=f"recovery:{relative}:{name}",
                            kind="recovery",
                            name=f"{module}.{name}",
                            source_path=relative,
                            function_id=f"{module}.{name}",
                            route_id=f"recovery:{module}.{name}",
                        )
                    if _FULL_PROVIDER_RE.search(joined):
                        add(
                            surface_id=f"provider:{relative}:{name}",
                            kind="provider",
                            name=f"{module}.{name}",
                            source_path=relative,
                            function_id=f"{module}.{name}",
                            route_id=f"provider:{module}.{name}",
                        )
            if private_members:
                # Private helpers are reviewed as one source component.  The
                # component row is deliberately coarse (file/function group,
                # never source-line level) while its member list keeps the
                # reverse denominator honest when a helper is added/removed.
                add(
                    surface_id=f"component:{relative}",
                    kind="component",
                    name=f"{module}.__private_components__",
                    source_path=relative,
                    function_id=f"component:{module}",
                    route_id=f"component:{module}",
                    component_members=private_members,
                )
        elif suffix in {".json", ".toml", ".yaml", ".yml"}:
            kind = "config" if path.name in _FULL_CONFIG_NAMES or "schema" in path.name.casefold() else "artifact"
            add(
                surface_id=f"{kind}:{relative}",
                kind=kind,
                name=relative,
                source_path=relative,
                function_id=f"{kind}:{relative}",
                route_id=f"{kind}:{relative}",
            )
        elif suffix in {".md", ".txt"}:
            parts = {part.casefold() for part in path.relative_to(root).parts}
            if path.name == "SKILL.md" or "templates" in parts or "references" in parts:
                add(
                    surface_id=f"template:{relative}",
                    kind="template",
                    name=relative,
                    source_path=relative,
                    function_id=f"template:{relative}",
                    route_id=f"template:{relative}",
                )

    surfaces.sort(key=lambda item: item.surface_id)
    source_paths = tuple(sorted(path.relative_to(root).as_posix() for path in files))
    fingerprint_payload = {
        "schema_version": "skillguard.full_surface_discovery.v1",
        "source_paths": source_paths,
        "surfaces": [surface.to_dict() for surface in surfaces],
        "findings": [finding.to_dict() for finding in findings],
    }
    return FullSourceSurfaceScan(
        surfaces=tuple(surfaces),
        source_paths=source_paths,
        findings=tuple(findings),
        discovery_fingerprint=_wire_hash(_canonical_bytes(fingerprint_payload)),
    )


_REFRESH_STRUCTURAL_FIELDS = (
    "kind",
    "name",
    "source_path",
    "source_fingerprint",
    "function_id",
    "route_id",
    "review_group_id",
    "review_granularity",
    "component_members",
)
_REFRESH_SEMANTIC_FIELDS = {
    "rows": (
        "disposition",
        "intent_id",
        "owner_id",
        "required_check_ids",
        "adequacy_check_ids",
        "evidence_subject_ids",
    ),
    "reverse_surfaces": (
        "disposition",
        "intent_id",
        "owner_id",
        "required_check_ids",
        "adequacy_check_ids",
        "evidence_subject_ids",
    ),
    "full_surfaces": (
        "disposition",
        "intent_id",
        "owner_id",
        "obligation_ids",
        "model_obligation_ids",
        "required_check_ids",
        "adequacy_check_ids",
        "execution_owner_ids",
        "evidence_subject_ids",
    ),
}
_REFRESH_REQUIRED_TOP_LEVEL_FIELDS = (
    "inventory_id",
    "target_skill_id",
    "source_kind",
    "owner_ids",
    "adequacy_check_ids",
    "model_deepening_check_id",
    "surface_category_dispositions",
    "current_obligation_ids",
    "model_obligations",
    "claim_boundary",
)
_REFRESH_LIST_FIELDS = frozenset(
    {
        "owner_ids",
        "adequacy_check_ids",
        "required_check_ids",
        "evidence_subject_ids",
        "obligation_ids",
        "model_obligation_ids",
        "execution_owner_ids",
        "current_obligation_ids",
        "model_obligations",
    }
)


def _refresh_missing_semantic_fields(
    inventory: Mapping[str, Any],
) -> tuple[SurfaceInventoryFinding, ...]:
    """Return missing target-owned meaning that a structural refresh cannot invent."""

    findings: list[SurfaceInventoryFinding] = []
    for field in _REFRESH_REQUIRED_TOP_LEVEL_FIELDS:
        value = inventory.get(field)
        if field in _REFRESH_LIST_FIELDS:
            missing = not isinstance(value, list) or not value
        else:
            missing = not _text(value) and field != "surface_category_dispositions"
            if field == "surface_category_dispositions":
                missing = not isinstance(value, Mapping) or not value
        if missing:
            findings.append(
                _finding(
                    "surface_inventory_refresh_semantic_field_missing",
                    f"$.{field}",
                    "the target must supply current semantic authority; refresh never synthesizes it",
                )
            )

    for section, fields in _REFRESH_SEMANTIC_FIELDS.items():
        rows = inventory.get(section)
        if not isinstance(rows, list) or not rows:
            findings.append(
                _finding(
                    "surface_inventory_refresh_semantic_field_missing",
                    f"$.{section}",
                    "target-owned semantic rows are required before a structural refresh",
                )
            )
            continue
        for index, row in enumerate(rows):
            if not isinstance(row, Mapping):
                findings.append(
                    _finding(
                        "surface_inventory_refresh_semantic_field_missing",
                        f"$.{section}[{index}]",
                        "a target-owned semantic row is required",
                    )
                )
                continue
            row_path = f"$.{section}[{index}]"
            for field in fields:
                value = row.get(field)
                missing = (
                    (field in _REFRESH_LIST_FIELDS and (not isinstance(value, list) or not value))
                    or (field not in _REFRESH_LIST_FIELDS and not _text(value))
                )
                if missing:
                    findings.append(
                        _finding(
                            "surface_inventory_refresh_semantic_field_missing",
                            f"{row_path}.{field}",
                            "refresh cannot infer intent, owner, obligation, check, or evidence meaning",
                        )
                    )
            disposition = _text(row.get("disposition"))
            conditional_fields = (
                ("lifecycle_phase", "consumer_exposure", "write_authority")
                if section == "full_surfaces" and disposition == "governed"
                else ("disposition_reason", "disposition_proof_ref")
                if disposition in {"internal_proven", "retired_proven", "not_applicable_proven"}
                else ()
            )
            for field in conditional_fields:
                if not _text(row.get(field)):
                    findings.append(
                        _finding(
                            "surface_inventory_refresh_semantic_field_missing",
                            f"{row_path}.{field}",
                            "conditional disposition/lifecycle meaning must remain target-authored",
                        )
                    )
    return tuple(findings)


def _refresh_surface_set_findings(
    inventory: Mapping[str, Any],
    *,
    command_ids: set[str],
    reverse_ids: set[str],
    full_ids: set[str],
) -> tuple[SurfaceInventoryFinding, ...]:
    """Reject a changed denominator instead of guessing a new semantic row."""

    findings: list[SurfaceInventoryFinding] = []
    sections = (
        ("observed_surface_ids", command_ids, "command surface"),
        ("reverse_surface_ids", reverse_ids, "reverse public surface"),
        ("full_surface_ids", full_ids, "full implementation surface"),
    )
    for field, expected, label in sections:
        value = inventory.get(field)
        declared = set(value) if isinstance(value, list) else set()
        if isinstance(value, list) and len(value) != len(declared):
            findings.append(
                _finding(
                    "surface_inventory_refresh_surface_set_invalid",
                    f"$.{field}",
                    "surface ids must be unique before a structural refresh",
                )
            )
        if declared != expected:
            added = sorted(expected - declared)
            removed = sorted(declared - expected)
            findings.append(
                _finding(
                    "surface_inventory_refresh_surface_set_changed",
                    f"$.{field}",
                    f"{label} denominator changed; added={added!r}, removed={removed!r}; manually rebuild semantic rows under the current standard",
                )
            )
    row_sections = (
        ("rows", command_ids, "command surface rows"),
        ("reverse_surfaces", reverse_ids, "reverse public surface rows"),
        ("full_surfaces", full_ids, "full implementation surface rows"),
    )
    for section, expected, label in row_sections:
        raw_rows = inventory.get(section)
        row_ids = {
            _text(row.get("surface_id"))
            for row in raw_rows
            if isinstance(row, Mapping) and _text(row.get("surface_id"))
        } if isinstance(raw_rows, list) else set()
        if isinstance(raw_rows, list):
            raw_id_values = [
                _text(row.get("surface_id"))
                for row in raw_rows
                if isinstance(row, Mapping)
            ]
            if len(raw_id_values) != len(row_ids):
                findings.append(
                    _finding(
                        "surface_inventory_refresh_surface_set_invalid",
                        f"$.{section}",
                        "target-owned surface rows must have unique ids before a structural refresh",
                    )
                )
        if row_ids != expected:
            added = sorted(expected - row_ids)
            removed = sorted(row_ids - expected)
            findings.append(
                _finding(
                    "surface_inventory_refresh_surface_set_changed",
                    f"$.{section}",
                    f"{label} denominator changed; added={added!r}, removed={removed!r}; manually rebuild semantic rows under the current standard",
                )
            )
    return tuple(findings)


def _refresh_row_structure(
    row: Mapping[str, Any],
    surface: PublicSourceSurface,
) -> dict[str, Any]:
    """Replace only source-derived fields, preserving all target-owned meaning."""

    refreshed = dict(row)
    source = surface.to_dict()
    for field in _REFRESH_STRUCTURAL_FIELDS:
        # Full rows require these fields; compact/reverse rows may use a
        # smaller projection.  Preserve optional keys that the target did not
        # choose to expose rather than manufacturing extra semantics.
        if field in row or field in {"kind", "name", "source_path", "function_id", "route_id"}:
            refreshed[field] = source[field]
    if "source_symbol_or_route" in row:
        refreshed["source_symbol_or_route"] = surface.function_id or surface.route_id
    if "symbol" in row:
        refreshed["symbol"] = surface.function_id or surface.route_id
    return refreshed


def _refresh_atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    """Write one canonical JSON projection without exposing a partial file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        if temporary_name:
            temporary = Path(temporary_name)
            if temporary.exists():
                temporary.unlink()


def refresh_surface_inventory(
    inventory: Mapping[str, Any],
    *,
    target_root: Path,
    command_surface: Sequence[Mapping[str, Any]] = (),
    route_entries: Sequence[Mapping[str, Any]] = (),
    command_handlers: Mapping[str, Any] | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Refresh one current target-owned inventory's structural projection.

    This is an author-side direct-current writer.  It deliberately has a
    narrow authority boundary:

    * fresh source discovery must succeed without findings;
    * command, reverse, and full surface identity sets must be unchanged;
    * all target-owned semantic fields must already be present; and
    * only source-derived fields, source paths, discovery identity, and the
      inventory hash may be replaced.

    A changed surface denominator is not migrated, aliased, or auto-filled.
    The caller must manually rebuild the affected rows under the current
    standard and call this writer again.  Function names never supply intent,
    owner, obligation, check, lifecycle, or evidence values.
    """

    if not isinstance(inventory, Mapping):
        finding = _finding(
            "surface_inventory_refresh_current_shape_invalid",
            "$",
            "a current target-owned inventory object is required",
        )
        return {
            "decision": "blocked",
            "written": False,
            "inventory": None,
            "findings": [finding.to_dict()],
            "updated_structural_fields": [],
        }

    root = target_root.resolve()
    public_scan = discover_public_source_surfaces(
        root,
        command_surface=command_surface,
        route_entries=route_entries,
        command_handlers=command_handlers,
    )
    full_scan = discover_full_source_surfaces(
        root,
        command_surface=command_surface,
        route_entries=route_entries,
        command_handlers=command_handlers,
    )
    findings = list(public_scan.findings) + list(full_scan.findings)
    command_ids = {
        _text(row.get("name"))
        for row in command_surface
        if isinstance(row, Mapping) and _text(row.get("name"))
    }
    reverse_ids = {surface.surface_id for surface in public_scan.surfaces}
    full_ids = {surface.surface_id for surface in full_scan.surfaces}
    findings.extend(
        _refresh_surface_set_findings(
            inventory,
            command_ids=command_ids,
            reverse_ids=reverse_ids,
            full_ids=full_ids,
        )
    )
    findings.extend(_refresh_missing_semantic_fields(inventory))
    stored_inventory_hash = _text(inventory.get("inventory_hash"))
    if not stored_inventory_hash:
        findings.append(
            _finding(
                "surface_inventory_refresh_current_hash_missing",
                "$.inventory_hash",
                "the current semantic projection must be hash-bound before structural refresh",
            )
        )
    elif stored_inventory_hash != surface_inventory_hash(inventory):
        findings.append(
            _finding(
                "surface_inventory_refresh_current_hash_mismatch",
                "$.inventory_hash",
                "repair the target-owned semantic projection before refreshing source identity",
            )
        )
    if output_path is not None:
        destination = output_path.resolve()
        if not destination.is_relative_to(root):
            findings.append(
                _finding(
                    "surface_inventory_refresh_output_unsafe",
                    "$.output_path",
                    "the writer may only replace a target-owned inventory under target_root",
                )
            )
    if findings:
        return {
            "decision": "blocked",
            "written": False,
            "inventory": None,
            "findings": [finding.to_dict() for finding in findings],
            "updated_structural_fields": [],
            "surface_set_changed": any(
                finding.code == "surface_inventory_refresh_surface_set_changed"
                for finding in findings
            ),
        }

    current = json.loads(json.dumps(inventory, ensure_ascii=False))
    full_by_id = {surface.surface_id: surface for surface in full_scan.surfaces}
    public_by_id = {surface.surface_id: surface for surface in public_scan.surfaces}
    updated_fields: list[str] = []

    rows = current.get("rows", [])
    for index, row in enumerate(rows):
        surface_id = _text(row.get("surface_id"))
        surface = full_by_id.get(f"command:{surface_id}") or full_by_id.get(surface_id)
        if surface is None:
            # The denominator guard above should make this unreachable.  Keep
            # it fail-closed if a future projection introduces a new shape.
            return {
                "decision": "blocked",
                "written": False,
                "inventory": None,
                "findings": [
                    _finding(
                        "surface_inventory_refresh_structural_binding_missing",
                        f"$.rows[{index}].surface_id",
                        surface_id,
                    ).to_dict()
                ],
                "updated_structural_fields": [],
            }
        refreshed = _refresh_row_structure(row, surface)
        if refreshed != row:
            updated_fields.append(f"rows[{index}]")
        rows[index] = refreshed

    reverse_rows = current.get("reverse_surfaces", [])
    for index, row in enumerate(reverse_rows):
        surface_id = _text(row.get("surface_id"))
        surface = public_by_id.get(surface_id)
        if surface is None:
            return {
                "decision": "blocked",
                "written": False,
                "inventory": None,
                "findings": [
                    _finding(
                        "surface_inventory_refresh_structural_binding_missing",
                        f"$.reverse_surfaces[{index}].surface_id",
                        surface_id,
                    ).to_dict()
                ],
                "updated_structural_fields": [],
            }
        refreshed = _refresh_row_structure(row, surface)
        if refreshed != row:
            updated_fields.append(f"reverse_surfaces[{index}]")
        reverse_rows[index] = refreshed

    full_rows = current.get("full_surfaces", [])
    for index, row in enumerate(full_rows):
        surface_id = _text(row.get("surface_id"))
        surface = full_by_id.get(surface_id)
        if surface is None:
            return {
                "decision": "blocked",
                "written": False,
                "inventory": None,
                "findings": [
                    _finding(
                        "surface_inventory_refresh_structural_binding_missing",
                        f"$.full_surfaces[{index}].surface_id",
                        surface_id,
                    ).to_dict()
                ],
                "updated_structural_fields": [],
            }
        refreshed = _refresh_row_structure(row, surface)
        if refreshed != row:
            updated_fields.append(f"full_surfaces[{index}]")
        full_rows[index] = refreshed

    for field, value in (
        ("source_paths", list(full_scan.source_paths)),
        ("observed_surface_ids", sorted(command_ids)),
        ("reverse_surface_ids", sorted(reverse_ids)),
        ("full_surface_ids", sorted(full_ids)),
        ("full_discovery_fingerprint", full_scan.discovery_fingerprint),
    ):
        if current.get(field) != value:
            current[field] = value
            updated_fields.append(field)
    current["inventory_hash"] = surface_inventory_hash(current)
    if current.get("inventory_hash") != inventory.get("inventory_hash"):
        updated_fields.append("inventory_hash")

    wrote = False
    if output_path is not None:
        destination = output_path.resolve()
        if current != inventory or not destination.is_file():
            _refresh_atomic_write(destination, current)
            wrote = True
    return {
        "decision": "pass",
        "written": wrote,
        "inventory": current,
        "findings": [],
        "updated_structural_fields": sorted(set(updated_fields)),
        "surface_set_changed": False,
    }


def validate_surface_inventory(
    payload: object,
    *,
    target_skill_id: str | None = None,
    native_check_ids: Iterable[str] = (),
    model_deepening_check_id: str | None = None,
    path: str = "$",
) -> tuple[SurfaceInventoryFinding, ...]:
    """Validate one target-owned inventory without inferring missing rows.

    The validator deliberately reports missing route/check/intent/owner data
    instead of synthesising a fallback.  That is what prevents an empty or
    partially mapped surface from becoming a graduation pass.
    """

    findings: list[SurfaceInventoryFinding] = []
    if not isinstance(payload, Mapping):
        return (_finding("surface_inventory_shape_invalid", path, "an object is required"),)
    allowed = {
        "schema_version",
        "inventory_id",
        "target_skill_id",
        "source_kind",
        "source_paths",
        "observed_surface_ids",
        "rows",
        "reverse_surface_ids",
        "reverse_surfaces",
        "full_surface_ids",
        "full_surfaces",
        "current_obligation_ids",
        "model_obligations",
        "surface_category_dispositions",
        "full_discovery_fingerprint",
        "owner_ids",
        "adequacy_check_ids",
        "model_deepening_check_id",
        "inventory_hash",
        "claim_boundary",
    }
    for key in sorted(set(payload) - allowed):
        findings.append(_finding("surface_inventory_unknown_field", f"{path}.{key}"))
    if payload.get("schema_version") != SURFACE_INVENTORY_SCHEMA:
        findings.append(_finding("surface_inventory_schema_mismatch", f"{path}.schema_version", SURFACE_INVENTORY_SCHEMA))
    for key in ("inventory_id", "target_skill_id", "source_kind", "claim_boundary"):
        if not _text(payload.get(key)):
            findings.append(_finding("surface_inventory_required_field_missing", f"{path}.{key}"))
    declared_target = _text(payload.get("target_skill_id"))
    if target_skill_id and declared_target != target_skill_id:
        findings.append(_finding("surface_inventory_target_mismatch", f"{path}.target_skill_id", f"expected {target_skill_id}"))
    source_paths = payload.get("source_paths", [])
    _paths(source_paths, path=f"{path}.source_paths", findings=findings)
    observed_ids = _ids(payload.get("observed_surface_ids"), path=f"{path}.observed_surface_ids", findings=findings)
    if not observed_ids:
        findings.append(
            _finding(
                "surface_inventory_observed_denominator_missing",
                f"{path}.observed_surface_ids",
                "the real observed surface denominator must be non-empty",
            )
        )
    declared_owner_ids = _owner_ids(
        payload.get("owner_ids"),
        path=f"{path}.owner_ids",
        findings=findings,
    )
    known_owners = {
        _text(owner_id)
        for owner_id in declared_owner_ids
        if _text(owner_id)
    }
    adequacy_ids = _ids(payload.get("adequacy_check_ids"), path=f"{path}.adequacy_check_ids", findings=findings)
    native_ids = {str(value) for value in native_check_ids if _text(value)}
    if not adequacy_ids:
        findings.append(_finding("surface_adequacy_checks_missing", f"{path}.adequacy_check_ids", "at least one target-owned adequacy check is required"))
    for check_id in sorted(set(adequacy_ids) - native_ids) if native_ids else []:
        findings.append(_finding("surface_adequacy_check_not_native", f"{path}.adequacy_check_ids", check_id))
    declared_deepening = _text(payload.get("model_deepening_check_id"))
    if not declared_deepening:
        findings.append(_finding("surface_model_deepening_missing", f"{path}.model_deepening_check_id"))
    elif model_deepening_check_id and declared_deepening != model_deepening_check_id:
        findings.append(_finding("surface_model_deepening_mismatch", f"{path}.model_deepening_check_id", f"expected {model_deepening_check_id}"))
    if declared_deepening and native_ids and declared_deepening not in native_ids:
        findings.append(_finding("surface_model_deepening_not_native", f"{path}.model_deepening_check_id", declared_deepening))

    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        findings.append(_finding("surface_inventory_empty", f"{path}.rows", "at least one surface row is required"))
        rows = []
    row_ids: list[str] = []
    row_by_id: dict[str, Mapping[str, Any]] = {}
    for index, row in enumerate(rows):
        row_path = f"{path}.rows[{index}]"
        if not isinstance(row, Mapping):
            findings.append(_finding("surface_row_shape_invalid", row_path, "an object is required"))
            continue
        row_id = _text(row.get("surface_id"))
        if not row_id or not _ID_RE.fullmatch(row_id):
            findings.append(_finding("surface_row_id_invalid", f"{row_path}.surface_id", row.get("surface_id")))
        elif row_id in row_by_id:
            findings.append(_finding("surface_row_id_duplicate", f"{row_path}.surface_id", row_id))
        else:
            row_ids.append(row_id)
            row_by_id[row_id] = row
        kind = _text(row.get("kind"))
        if kind not in SURFACE_KINDS:
            findings.append(_finding("surface_row_kind_invalid", f"{row_path}.kind", kind))
        if not _text(row.get("name")):
            findings.append(_finding("surface_row_missing_name", f"{row_path}.name", "each surface must declare its public name"))
        disposition = _text(row.get("disposition"))
        if disposition not in SURFACE_DISPOSITIONS:
            findings.append(_finding("surface_row_disposition_invalid", f"{row_path}.disposition", disposition))
        for field, code in (("intent_id", "surface_row_missing_intent"), ("owner_id", "surface_row_missing_owner")):
            value = _text(row.get(field))
            if not value or not _ID_RE.fullmatch(value):
                findings.append(_finding(code, f"{row_path}.{field}"))
        owner_id = _text(row.get("owner_id"))
        if _owner_sentinel(owner_id):
            findings.append(
                _finding(
                    "surface_row_owner_unknown",
                    f"{row_path}.owner_id",
                    "an explicit target-owned owner id is required",
                )
            )
        elif known_owners and owner_id not in known_owners:
            findings.append(
                _finding(
                    "surface_row_owner_unknown",
                    f"{row_path}.owner_id",
                    owner_id,
                )
            )
        route_id = _text(row.get("route_id"))
        if not route_id and disposition == "governed":
            findings.append(_finding("surface_row_missing_route", f"{row_path}.route_id", "governed rows need an explicit route"))
        function_id = _text(row.get("function_id"))
        if not function_id or not _ID_RE.fullmatch(function_id):
            findings.append(_finding("surface_row_missing_function", f"{row_path}.function_id", "each surface must name its target-owned function or dispatch owner"))
        required_ids = _ids(row.get("required_check_ids"), path=f"{row_path}.required_check_ids", findings=findings)
        if not required_ids:
            findings.append(_finding("surface_row_missing_checks", f"{row_path}.required_check_ids", "at least one native check is required"))
        row_adequacy_ids = _ids(row.get("adequacy_check_ids"), path=f"{row_path}.adequacy_check_ids", findings=findings)
        if not row_adequacy_ids:
            findings.append(_finding("surface_row_adequacy_missing", f"{row_path}.adequacy_check_ids", "each row must be covered by an adequacy check"))
        for check_id in sorted(set(row_adequacy_ids) - set(adequacy_ids)):
            findings.append(_finding("surface_row_adequacy_unknown", f"{row_path}.adequacy_check_ids", check_id))
        evidence_ids = _ids(row.get("evidence_subject_ids"), path=f"{row_path}.evidence_subject_ids", findings=findings)
        if not evidence_ids:
            findings.append(_finding("surface_row_evidence_missing", f"{row_path}.evidence_subject_ids"))
        if disposition in {"internal_proven", "retired_proven", "not_applicable_proven"} and not _text(row.get("disposition_reason")):
            findings.append(_finding("surface_row_disposition_reason_missing", f"{row_path}.disposition_reason"))
        if native_ids:
            for check_id in sorted(set(required_ids) - native_ids):
                findings.append(_finding("surface_row_check_not_native", f"{row_path}.required_check_ids", check_id))
    if observed_ids and set(observed_ids) != set(row_ids):
        findings.append(_finding("surface_observed_denominator_mismatch", f"{path}.observed_surface_ids", f"observed={len(observed_ids)} rows={len(row_ids)}"))
    stored_hash = _text(payload.get("inventory_hash"))
    if not stored_hash:
        findings.append(_finding("surface_inventory_hash_missing", f"{path}.inventory_hash"))
    elif stored_hash != surface_inventory_hash(payload):
        findings.append(_finding("surface_inventory_hash_mismatch", f"{path}.inventory_hash", stored_hash))
    return tuple(findings)


def validate_command_surface_inventory(
    inventory: Mapping[str, Any],
    command_surface: Sequence[Mapping[str, Any]],
    route_entries: Sequence[Mapping[str, Any]],
) -> tuple[SurfaceInventoryFinding, ...]:
    """Target-native self check for the complete public command surface."""

    findings = list(
        validate_surface_inventory(
            inventory,
            target_skill_id="skillguard",
        )
    )
    rows: dict[str, Mapping[str, Any]] = {}
    raw_rows = inventory.get("rows", []) if isinstance(inventory, Mapping) else []
    if not isinstance(raw_rows, list):
        raw_rows = []
    for index, row in enumerate(raw_rows):
        if not isinstance(row, Mapping):
            continue
        surface_id = _text(row.get("surface_id"))
        if not surface_id:
            continue
        if surface_id in rows:
            findings.append(
                _finding(
                    "surface_command_surface_id_duplicate",
                    f"$.rows[{index}].surface_id",
                    surface_id,
                )
            )
            continue
        rows[surface_id] = row

    commands: dict[str, Mapping[str, Any]] = {}
    dispatches: dict[str, str] = {}
    for index, row in enumerate(command_surface):
        command_path = f"$.command_surface[{index}]"
        if not isinstance(row, Mapping):
            findings.append(_finding("surface_command_entry_invalid", command_path, "an object is required"))
            continue
        name = _text(row.get("name"))
        if not name:
            findings.append(_finding("surface_command_name_missing", f"{command_path}.name", "public commands need a name"))
            continue
        if name in commands:
            findings.append(
                _finding(
                    "surface_command_name_duplicate",
                    f"$.command_surface[{index}].name",
                    name,
                )
            )
            continue
        commands[name] = row
        dispatch = _text(row.get("dispatch_function"))
        if not dispatch:
            findings.append(
                _finding(
                    "surface_dispatch_function_missing",
                    f"{command_path}.dispatch_function",
                    name,
                )
            )
        elif dispatch in dispatches:
            findings.append(
                _finding(
                    "surface_dispatch_function_duplicate",
                    f"{command_path}.dispatch_function",
                    dispatch,
                )
            )
        else:
            dispatches[dispatch] = name

    routes: dict[str, Mapping[str, Any]] = {}
    route_ids: set[str] = set()
    for index, row in enumerate(route_entries):
        route_path = f"$.route_registry[{index}]"
        if not isinstance(row, Mapping):
            findings.append(_finding("surface_route_entry_invalid", route_path, "an object is required"))
            continue
        if _text(row.get("status") or "current") != "current":
            continue
        command_family = _text(row.get("command_family"))
        route_id = _text(row.get("route_id"))
        if not route_id:
            findings.append(_finding("surface_route_identity_missing", f"{route_path}.route_id", "current routes need an id"))
        elif route_id in route_ids:
            findings.append(
                _finding(
                    "surface_command_route_id_duplicate",
                    f"{route_path}.route_id",
                    route_id,
                )
            )
        elif route_id:
            route_ids.add(route_id)
        if not command_family:
            findings.append(_finding("surface_route_command_missing", f"{route_path}.command_family", "current routes need a command family"))
            continue
        if command_family in routes:
            findings.append(
                _finding(
                    "surface_command_route_command_duplicate",
                    f"{route_path}.command_family",
                    command_family,
                )
            )
            continue
        routes[command_family] = row
    if set(rows) != set(commands):
        findings.append(_finding("surface_command_denominator_mismatch", "$.rows", f"inventory={len(rows)} commands={len(commands)}"))
    for name in sorted(set(commands) - set(rows)):
        findings.append(_finding("surface_command_row_missing", "$.rows", name))
    for name, command in sorted(commands.items()):
        row = rows.get(name)
        if row is None:
            continue
        row_path = f"$.rows[{name}]"
        if _text(row.get("name")) != name:
            findings.append(_finding("surface_command_name_mismatch", f"{row_path}.name", name))
        if _text(row.get("kind")) != "command":
            findings.append(_finding("surface_command_kind_invalid", f"{row_path}.kind", "command"))
        expected_function = _text(command.get("dispatch_function"))
        if expected_function and _text(row.get("function_id")) != expected_function:
            findings.append(_finding("surface_command_function_mismatch", f"{row_path}.function_id", expected_function))
        disposition = _text(row.get("disposition"))
        if disposition != "governed":
            findings.append(_finding("surface_command_disposition_invalid", f"{row_path}.disposition", "live public commands must be governed"))
        expected_checks = command.get("required_checks")
        if not isinstance(expected_checks, list) or not expected_checks:
            findings.append(_finding("surface_command_required_checks_empty", f"{row_path}.required_check_ids", name))
        if isinstance(expected_checks, list) and list(row.get("required_check_ids", [])) != expected_checks:
            findings.append(_finding("surface_command_required_checks_mismatch", f"{row_path}.required_check_ids", name))
        if name not in routes:
            findings.append(_finding("surface_command_route_missing", f"{row_path}.route_id", name))
        elif name in routes and _text(row.get("route_id")) != _text(routes[name].get("route_id")):
            findings.append(_finding("surface_command_route_mismatch", f"{row_path}.route_id", name))
    return tuple(findings)


def validate_reverse_surface_inventory(
    inventory: Mapping[str, Any],
    *,
    target_root: Path,
    command_surface: Sequence[Mapping[str, Any]],
    route_entries: Sequence[Mapping[str, Any]],
    command_handlers: Mapping[str, Any] | None = None,
) -> tuple[SurfaceInventoryFinding, ...]:
    """Compare a target inventory with source-derived public surfaces.

    ``rows`` remains the command-surface inventory.  ``reverse_surfaces`` is
    the explicit reverse-closure projection for entry scripts, dispatch
    functions, and route-registry entries.  Every discovered surface needs one
    current ``governed`` row.  An old surface may remain only with an explicit
    ``retired_proven`` or ``not_applicable_proven`` disposition and reason; a
    live orphan is always a failure.
    """

    findings: list[SurfaceInventoryFinding] = []
    findings.extend(
        validate_command_surface_inventory(
            inventory,
            command_surface,
            route_entries,
        )
    )
    owner_universe = {
        _text(value)
        for value in (inventory.get("owner_ids", []) if isinstance(inventory, Mapping) else [])
        if _text(value)
    }
    reverse_rows = inventory.get("reverse_surfaces") if isinstance(inventory, Mapping) else None
    if not isinstance(reverse_rows, list) or not reverse_rows:
        findings.append(
            _finding(
                "surface_reverse_inventory_missing",
                "$.reverse_surfaces",
                "source-derived scripts, dispatch functions, and routes must be explicitly inventoried",
            )
        )
        return tuple(findings)

    reverse_ids = _ids(
        inventory.get("reverse_surface_ids"),
        path="$.reverse_surface_ids",
        findings=findings,
    )
    if not reverse_ids:
        findings.append(
            _finding(
                "surface_reverse_denominator_missing",
                "$.reverse_surface_ids",
                "the real reverse surface denominator must be non-empty",
            )
        )
    reverse_by_id: dict[str, Mapping[str, Any]] = {}
    for index, row in enumerate(reverse_rows):
        row_path = f"$.reverse_surfaces[{index}]"
        if not isinstance(row, Mapping):
            findings.append(_finding("surface_reverse_row_shape_invalid", row_path, "an object is required"))
            continue
        surface_id = _text(row.get("surface_id"))
        if not surface_id or not _ID_RE.fullmatch(surface_id):
            findings.append(_finding("surface_reverse_row_id_invalid", f"{row_path}.surface_id", row.get("surface_id")))
            continue
        if surface_id in reverse_by_id:
            findings.append(_finding("surface_reverse_row_id_duplicate", f"{row_path}.surface_id", surface_id))
        reverse_by_id[surface_id] = row
        kind = _text(row.get("kind"))
        if kind not in {"script", "dispatch", "route"}:
            findings.append(_finding("surface_reverse_row_kind_invalid", f"{row_path}.kind", kind))
        if not _text(row.get("name")):
            findings.append(_finding("surface_reverse_row_missing_name", f"{row_path}.name"))
        disposition = _text(row.get("disposition"))
        if disposition not in SURFACE_DISPOSITIONS:
            findings.append(_finding("surface_reverse_row_disposition_invalid", f"{row_path}.disposition", disposition))
        for field, code in (("intent_id", "surface_reverse_row_missing_intent"), ("owner_id", "surface_reverse_row_missing_owner"), ("function_id", "surface_reverse_row_missing_function")):
            value = _text(row.get(field))
            if not value or not _ID_RE.fullmatch(value):
                findings.append(_finding(code, f"{row_path}.{field}"))
        owner_id = _text(row.get("owner_id"))
        if _owner_sentinel(owner_id):
            findings.append(
                _finding(
                    "surface_reverse_row_owner_unknown",
                    f"{row_path}.owner_id",
                    "an explicit target-owned owner id is required",
                )
            )
        elif owner_universe and owner_id not in owner_universe:
            findings.append(
                _finding(
                    "surface_reverse_row_owner_unknown",
                    f"{row_path}.owner_id",
                    owner_id,
                )
            )
        if disposition == "governed" and not _text(row.get("route_id")):
            findings.append(_finding("surface_reverse_row_missing_route", f"{row_path}.route_id"))
        if disposition in {"internal_proven", "retired_proven", "not_applicable_proven"} and not _text(row.get("disposition_reason")):
            findings.append(_finding("surface_reverse_row_disposition_reason_missing", f"{row_path}.disposition_reason"))
        for field, code in (("required_check_ids", "surface_reverse_row_missing_checks"), ("adequacy_check_ids", "surface_reverse_row_adequacy_missing"), ("evidence_subject_ids", "surface_reverse_row_evidence_missing")):
            values = _ids(row.get(field), path=f"{row_path}.{field}", findings=findings)
            if not values:
                findings.append(_finding(code, f"{row_path}.{field}"))

    if reverse_ids and set(reverse_ids) != set(reverse_by_id):
        findings.append(
            _finding(
                "surface_reverse_denominator_mismatch",
                "$.reverse_surface_ids",
                f"declared={len(reverse_ids)} rows={len(reverse_by_id)}",
            )
        )

    scan = discover_public_source_surfaces(
        target_root,
        command_surface=command_surface,
        route_entries=route_entries,
        command_handlers=command_handlers,
    )
    findings.extend(scan.findings)
    discovered_by_id = {surface.surface_id: surface for surface in scan.surfaces}
    for surface_id, surface in sorted(discovered_by_id.items()):
        row = reverse_by_id.get(surface_id)
        if row is None:
            findings.append(_finding("surface_reverse_unmapped", f"$.reverse_surfaces[{surface_id}]", surface_id))
            continue
        if _text(row.get("disposition")) != "governed":
            findings.append(_finding("surface_reverse_live_disposition_invalid", f"$.reverse_surfaces[{surface_id}].disposition", surface_id))
        for field, expected in (
            ("kind", surface.kind),
            ("name", surface.name),
            ("source_path", surface.source_path),
            ("function_id", surface.function_id),
            ("route_id", surface.route_id),
        ):
            observed = _text(row.get(field))
            if expected and observed != expected:
                findings.append(_finding("surface_reverse_binding_mismatch", f"$.reverse_surfaces[{surface_id}].{field}", f"expected {expected}"))

    discovered_ids = set(discovered_by_id)
    for surface_id, row in sorted(reverse_by_id.items()):
        if surface_id in discovered_ids:
            continue
        disposition = _text(row.get("disposition"))
        if disposition not in {"retired_proven", "not_applicable_proven"}:
            findings.append(_finding("surface_reverse_orphan_live", f"$.reverse_surfaces[{surface_id}]", surface_id))
    return tuple(findings)


def _full_surface_category(kind: str) -> str:
    if kind in {"option"}:
        return "command"
    if kind in {"export"}:
        return "api"
    if kind in {"prompt"}:
        return "template"
    return kind


def validate_full_surface_inventory(
    inventory: Mapping[str, Any],
    *,
    target_root: Path,
    command_surface: Sequence[Mapping[str, Any]] = (),
    route_entries: Sequence[Mapping[str, Any]] = (),
    command_handlers: Mapping[str, Any] | None = None,
    native_check_ids: Iterable[str] = (),
    model_deepening_check_id: str | None = None,
) -> tuple[SurfaceInventoryFinding, ...]:
    """Validate the independent implementation-to-intent denominator.

    This gate is deliberately stricter than command/route self-checking.  It
    compares the target-authored rows with a fresh source observation and
    requires a complete adequacy envelope and typed disposition for every
    code, config, template, effect, UI-like, installer, fault, and recovery
    surface.  A row count match or a resealed hash is never enough.
    """

    findings: list[SurfaceInventoryFinding] = []
    if not isinstance(inventory, Mapping):
        return (_finding("full_surface_inventory_shape_invalid", "$", "an object is required"),)
    owner_ids = _owner_ids(
        inventory.get("owner_ids"),
        path="$.owner_ids",
        findings=findings,
    )
    owners = set(owner_ids)
    raw_ids = inventory.get("full_surface_ids")
    full_ids = _ids(raw_ids, path="$.full_surface_ids", findings=findings)
    if not full_ids:
        findings.append(_finding("full_surface_denominator_missing", "$.full_surface_ids", "the independently discovered denominator is required"))
    raw_rows = inventory.get("full_surfaces")
    if not isinstance(raw_rows, list) or not raw_rows:
        findings.append(_finding("full_surface_rows_missing", "$.full_surfaces", "target-owned rows are required"))
        raw_rows = []
    row_by_id: dict[str, Mapping[str, Any]] = {}
    for index, row in enumerate(raw_rows):
        row_path = f"$.full_surfaces[{index}]"
        if not isinstance(row, Mapping):
            findings.append(_finding("full_surface_row_shape_invalid", row_path, "an object is required"))
            continue
        surface_id = _text(row.get("surface_id"))
        if not surface_id or not _ID_RE.fullmatch(surface_id):
            findings.append(_finding("full_surface_row_id_invalid", f"{row_path}.surface_id", surface_id))
            continue
        if surface_id in row_by_id:
            findings.append(_finding("full_surface_row_id_duplicate", f"{row_path}.surface_id", surface_id))
            continue
        row_by_id[surface_id] = row
        kind = _text(row.get("kind"))
        if kind not in SURFACE_KINDS:
            findings.append(_finding("full_surface_row_kind_invalid", f"{row_path}.kind", kind))
        disposition = _text(row.get("disposition"))
        if disposition not in SURFACE_DISPOSITIONS:
            findings.append(_finding("full_surface_row_disposition_invalid", f"{row_path}.disposition", disposition))
        owner = _text(row.get("owner_id"))
        if not owner or _owner_sentinel(owner) or owner not in owners:
            findings.append(_finding("full_surface_row_owner_unknown", f"{row_path}.owner_id", owner))
        for field, code in (
            ("intent_id", "full_surface_row_intent_missing"),
            ("function_id", "full_surface_row_function_missing"),
            ("route_id", "full_surface_row_route_missing"),
            ("source_path", "full_surface_row_source_missing"),
        ):
            if not _text(row.get(field)):
                findings.append(_finding(code, f"{row_path}.{field}"))
        review_group_id = _text(row.get("review_group_id"))
        review_granularity = _text(row.get("review_granularity"))
        if not review_group_id or not _ID_RE.fullmatch(review_group_id):
            findings.append(_finding("full_surface_row_review_group_missing", f"{row_path}.review_group_id"))
        if review_granularity not in {"surface", "component"}:
            findings.append(_finding("full_surface_row_review_granularity_invalid", f"{row_path}.review_granularity", review_granularity))
        obligation_ids = _ids(row.get("obligation_ids"), path=f"{row_path}.obligation_ids", findings=findings)
        model_obligation_ids = _ids(
            row.get("model_obligation_ids"),
            path=f"{row_path}.model_obligation_ids",
            findings=findings,
        )
        required_ids = _ids(row.get("required_check_ids"), path=f"{row_path}.required_check_ids", findings=findings)
        adequacy_ids = _ids(row.get("adequacy_check_ids"), path=f"{row_path}.adequacy_check_ids", findings=findings)
        execution_owner_ids = _ids(row.get("execution_owner_ids"), path=f"{row_path}.execution_owner_ids", findings=findings)
        evidence_ids = _ids(row.get("evidence_subject_ids"), path=f"{row_path}.evidence_subject_ids", findings=findings)
        if kind == "component":
            members = row.get("component_members")
            normalized_members = (
                [_text(member) for member in members]
                if isinstance(members, list)
                else []
            )
            if (
                not normalized_members
                or any(not member for member in normalized_members)
                or len(set(normalized_members)) != len(normalized_members)
            ):
                findings.append(
                    _finding(
                        "full_surface_component_members_missing",
                        f"{row_path}.component_members",
                        "a component row must enumerate its private members exactly",
                    )
                )
        elif "component_members" in row:
            findings.append(
                _finding(
                    "full_surface_component_members_unexpected",
                    f"{row_path}.component_members",
                    "only component rows may enumerate private members",
                )
            )
        if not obligation_ids:
            findings.append(_finding("full_surface_row_obligation_missing", f"{row_path}.obligation_ids"))
        if not model_obligation_ids:
            findings.append(
                _finding(
                    "full_surface_row_model_obligation_missing",
                    f"{row_path}.model_obligation_ids",
                    "every current implementation surface must name its target-owned model obligation binding",
                )
            )
        if not required_ids:
            findings.append(_finding("full_surface_row_checks_missing", f"{row_path}.required_check_ids"))
        # One generic smoke check is intentionally insufficient for a governed
        # surface.  The target must provide at least a native check plus a
        # separate adequacy/failure/recovery check projection.
        if disposition == "governed" and len(set(adequacy_ids)) < 2:
            findings.append(_finding("full_surface_row_adequacy_shallow", f"{row_path}.adequacy_check_ids", "governed rows need a non-empty adequacy envelope, not one generic smoke check"))
        if not execution_owner_ids:
            findings.append(_finding("full_surface_row_execution_owner_missing", f"{row_path}.execution_owner_ids"))
        if not evidence_ids:
            findings.append(_finding("full_surface_row_evidence_missing", f"{row_path}.evidence_subject_ids"))
        if disposition in {"internal_proven", "retired_proven", "not_applicable_proven"}:
            if not _text(row.get("disposition_reason")) or not _text(row.get("disposition_proof_ref")):
                findings.append(_finding("full_surface_row_disposition_proof_missing", row_path))
        native_ids = {str(value) for value in native_check_ids if _text(value)}
        if native_ids:
            for check_id in sorted(set(required_ids + adequacy_ids) - native_ids):
                findings.append(_finding("full_surface_row_check_not_native", f"{row_path}.required_check_ids", check_id))
        if disposition == "governed" and model_deepening_check_id and model_deepening_check_id not in set(adequacy_ids):
            findings.append(_finding("full_surface_row_deepening_missing", f"{row_path}.adequacy_check_ids", model_deepening_check_id))

    if full_ids and set(full_ids) != set(row_by_id):
        findings.append(_finding("full_surface_denominator_row_mismatch", "$.full_surface_ids", f"declared={len(full_ids)} rows={len(row_by_id)}"))

    current_obligation_ids = _ids(
        inventory.get("current_obligation_ids"),
        path="$.current_obligation_ids",
        findings=findings,
    )
    if not current_obligation_ids:
        findings.append(
            _finding(
                "full_surface_model_obligation_denominator_missing",
                "$.current_obligation_ids",
                "the current target-owned model-obligation denominator is required",
            )
        )

    raw_model_obligations = inventory.get("model_obligations")
    if not isinstance(raw_model_obligations, list) or not raw_model_obligations:
        findings.append(
            _finding(
                "full_surface_model_obligations_missing",
                "$.model_obligations",
                "target-owned current model-obligation rows are required",
            )
        )
        raw_model_obligations = []
    model_obligation_by_id: dict[str, Mapping[str, Any]] = {}
    for index, model_row in enumerate(raw_model_obligations):
        model_path = f"$.model_obligations[{index}]"
        if not isinstance(model_row, Mapping):
            findings.append(
                _finding(
                    "full_surface_model_obligation_row_shape_invalid",
                    model_path,
                    "a target-owned model-obligation row is required",
                )
            )
            continue
        obligation_id = _text(model_row.get("obligation_id"))
        if not obligation_id or not _ID_RE.fullmatch(obligation_id):
            findings.append(
                _finding(
                    "full_surface_model_obligation_id_invalid",
                    f"{model_path}.obligation_id",
                    obligation_id,
                )
            )
            continue
        if obligation_id in model_obligation_by_id:
            findings.append(
                _finding(
                    "full_surface_model_obligation_id_duplicate",
                    f"{model_path}.obligation_id",
                    obligation_id,
                )
            )
            continue
        model_obligation_by_id[obligation_id] = model_row
        disposition = _text(model_row.get("disposition"))
        if disposition not in MODEL_OBLIGATION_DISPOSITIONS:
            findings.append(
                _finding(
                    "full_surface_model_obligation_disposition_invalid",
                    f"{model_path}.disposition",
                    disposition,
                )
            )
        model_surface_ids = _ids(
            model_row.get("surface_ids"),
            path=f"{model_path}.surface_ids",
            findings=findings,
        )
        if disposition == "governed" and not model_surface_ids:
            findings.append(
                _finding(
                    "full_surface_model_obligation_surface_ids_missing",
                    f"{model_path}.surface_ids",
                    "a governed current model obligation must name at least one implementation surface",
                )
            )
        if disposition != "governed" and model_surface_ids:
            findings.append(
                _finding(
                    "full_surface_model_obligation_non_governed_surface_binding",
                    f"{model_path}.surface_ids",
                    "model-only, retired, or not-applicable obligations cannot claim a live implementation surface",
                )
            )
        if not _text(model_row.get("reason")) or not _text(model_row.get("proof_ref")):
            findings.append(
                _finding(
                    "full_surface_model_obligation_proof_missing",
                    model_path,
                    "every model-obligation disposition needs target-authored reason and proof_ref",
                )
            )

    if current_obligation_ids and set(current_obligation_ids) != set(model_obligation_by_id):
        findings.append(
            _finding(
                "full_surface_model_obligation_denominator_mismatch",
                "$.current_obligation_ids",
                f"declared={len(current_obligation_ids)} rows={len(model_obligation_by_id)}",
            )
        )

    discovery = discover_full_source_surfaces(
        target_root,
        command_surface=command_surface,
        route_entries=route_entries,
        command_handlers=command_handlers,
    )
    findings.extend(discovery.findings)
    discovered = {surface.surface_id: surface for surface in discovery.surfaces}
    declared_discovery_fingerprint = _text(inventory.get("full_discovery_fingerprint"))
    if not declared_discovery_fingerprint:
        findings.append(
            _finding(
                "full_surface_discovery_fingerprint_missing",
                "$.full_discovery_fingerprint",
                "the inventory must bind the exact current source discovery",
            )
        )
    elif declared_discovery_fingerprint != discovery.discovery_fingerprint:
        findings.append(
            _finding(
                "full_surface_discovery_fingerprint_mismatch",
                "$.full_discovery_fingerprint",
                f"expected {discovery.discovery_fingerprint}",
            )
        )
    if full_ids and set(full_ids) != set(discovered):
        findings.append(_finding("full_surface_discovery_denominator_mismatch", "$.full_surface_ids", f"declared={len(full_ids)} discovered={len(discovered)}"))
    for surface_id, surface in sorted(discovered.items()):
        row = row_by_id.get(surface_id)
        if row is None:
            findings.append(_finding("full_surface_unmapped", f"$.full_surfaces[{surface_id}]", surface_id))
            continue
        disposition = _text(row.get("disposition"))
        if disposition in {"retired_proven", "not_applicable_proven"}:
            findings.append(_finding("full_surface_live_disposition_invalid", f"$.full_surfaces[{surface_id}].disposition", "a source-observed surface cannot be retired or not-applicable while it remains present; use governed or internal_proven with proof"))
        for field, expected in (
            ("kind", surface.kind),
            ("name", surface.name),
            ("source_path", surface.source_path),
            ("source_fingerprint", surface.source_fingerprint),
            ("function_id", surface.function_id),
            ("route_id", surface.route_id),
            ("review_group_id", surface.review_group_id),
            ("review_granularity", surface.review_granularity),
        ):
            observed = _text(row.get(field))
            if observed != expected:
                findings.append(_finding("full_surface_binding_mismatch", f"$.full_surfaces[{surface_id}].{field}", f"expected {expected}"))
        if surface.kind == "component":
            observed_members = row.get("component_members")
            expected_members = list(surface.component_members)
            if observed_members != expected_members:
                findings.append(
                    _finding(
                        "full_surface_component_members_mismatch",
                        f"$.full_surfaces[{surface_id}].component_members",
                        f"expected {expected_members}",
                    )
                )

    # The implementation -> model edge and the model -> implementation edge
    # are one current contract.  A non-empty arbitrary string in
    # ``obligation_ids`` cannot stand in for this join: every referenced model
    # obligation must be declared in the current denominator, and every
    # governed model obligation must point back to the exact live rows that
    # carry it.  No names, checks, or function paths are used to infer an edge.
    discovered_ids = set(discovered)
    declared_full_ids = set(full_ids)
    for surface_id, row in sorted(row_by_id.items()):
        model_refs = _ids(
            row.get("model_obligation_ids"),
            path=f"$.full_surfaces[{surface_id}].model_obligation_ids",
            findings=findings,
        )
        for obligation_id in sorted(set(model_refs)):
            model_row = model_obligation_by_id.get(obligation_id)
            if model_row is None:
                findings.append(
                    _finding(
                        "full_surface_row_model_obligation_unknown",
                        f"$.full_surfaces[{surface_id}].model_obligation_ids",
                        obligation_id,
                    )
                )
                continue
            if _text(model_row.get("disposition")) != "governed":
                findings.append(
                    _finding(
                        "full_surface_row_model_obligation_non_governed",
                        f"$.full_surfaces[{surface_id}].model_obligation_ids",
                        obligation_id,
                    )
                )
            model_surface_ids = set(
                _ids(
                    model_row.get("surface_ids"),
                    path=f"$.model_obligations[{obligation_id}].surface_ids",
                    findings=findings,
                )
            )
            if surface_id not in model_surface_ids:
                findings.append(
                    _finding(
                        "full_surface_model_obligation_reverse_mismatch",
                        f"$.full_surfaces[{surface_id}].model_obligation_ids",
                        f"obligation {obligation_id} does not point back to this surface",
                    )
                )

    for obligation_id, model_row in sorted(model_obligation_by_id.items()):
        disposition = _text(model_row.get("disposition"))
        model_surface_ids = set(
            _ids(
                model_row.get("surface_ids"),
                path=f"$.model_obligations[{obligation_id}].surface_ids",
                findings=findings,
            )
        )
        unknown_surface_ids = sorted(model_surface_ids - discovered_ids)
        for surface_id in unknown_surface_ids:
            findings.append(
                _finding(
                    "full_surface_model_obligation_surface_unknown",
                    f"$.model_obligations[{obligation_id}].surface_ids",
                    surface_id,
                )
            )
        if disposition != "governed":
            continue
        for surface_id in sorted(model_surface_ids & declared_full_ids):
            row = row_by_id.get(surface_id)
            if row is None:
                continue
            row_refs = set(
                _ids(
                    row.get("model_obligation_ids"),
                    path=f"$.full_surfaces[{surface_id}].model_obligation_ids",
                    findings=findings,
                )
            )
            if obligation_id not in row_refs:
                findings.append(
                    _finding(
                        "full_surface_model_obligation_forward_mismatch",
                        f"$.model_obligations[{obligation_id}].surface_ids",
                        f"surface {surface_id} does not declare this model obligation",
                    )
                )

    # Derived effect/fault/recovery/provider observations that share one
    # component review group must consume one explicit model-obligation set.
    # Otherwise a component can appear closed merely because each facet has a
    # different synthetic row, while no single proof boundary covers the
    # component as a whole.
    component_groups: dict[str, list[tuple[str, Mapping[str, Any]]]] = {}
    for surface_id, row in sorted(row_by_id.items()):
        if _text(row.get("review_granularity")) != "component":
            continue
        group_id = _text(row.get("review_group_id"))
        if group_id:
            component_groups.setdefault(group_id, []).append((surface_id, row))
    for group_id, group_rows in sorted(component_groups.items()):
        if len(group_rows) < 2:
            continue
        expected_refs = tuple(
            sorted(
                set(
                    _ids(
                        group_rows[0][1].get("model_obligation_ids"),
                        path=f"$.full_surfaces[{group_rows[0][0]}].model_obligation_ids",
                        findings=findings,
                    )
                )
            )
        )
        for surface_id, row in group_rows[1:]:
            observed_refs = tuple(
                sorted(
                    set(
                        _ids(
                            row.get("model_obligation_ids"),
                            path=f"$.full_surfaces[{surface_id}].model_obligation_ids",
                            findings=findings,
                        )
                    )
                )
            )
            if observed_refs != expected_refs:
                findings.append(
                    _finding(
                        "full_surface_component_model_obligation_mismatch",
                        f"$.full_surfaces[{surface_id}].model_obligation_ids",
                        f"component group {group_id} must share one model-obligation set; expected={list(expected_refs)!r}, observed={list(observed_refs)!r}",
                    )
                )

    categories = inventory.get("surface_category_dispositions")
    if not isinstance(categories, Mapping):
        findings.append(_finding("full_surface_category_dispositions_missing", "$.surface_category_dispositions"))
        categories = {}
    unknown_categories = set(categories) - set(FULL_SURFACE_CATEGORIES)
    for category in sorted(unknown_categories):
        findings.append(_finding("full_surface_category_unknown", f"$.surface_category_dispositions.{category}"))
    discovered_categories = {
        _full_surface_category(surface.kind)
        for surface in discovery.surfaces
        if _full_surface_category(surface.kind) in FULL_SURFACE_CATEGORIES
    }
    for category in FULL_SURFACE_CATEGORIES:
        row = categories.get(category)
        if not isinstance(row, Mapping):
            findings.append(_finding("full_surface_category_missing", f"$.surface_category_dispositions.{category}"))
            continue
        disposition = _text(row.get("disposition"))
        if disposition not in SURFACE_DISPOSITIONS:
            findings.append(_finding("full_surface_category_disposition_invalid", f"$.surface_category_dispositions.{category}.disposition", disposition))
        if not _text(row.get("reason")) or not _text(row.get("proof_ref")):
            findings.append(_finding("full_surface_category_proof_missing", f"$.surface_category_dispositions.{category}"))
        if category in discovered_categories and disposition not in {"governed", "internal_proven"}:
            findings.append(_finding("full_surface_category_live_not_governed", f"$.surface_category_dispositions.{category}.disposition", category))
        if category not in discovered_categories and disposition not in {"not_applicable_proven", "retired_proven", "internal_proven"}:
            findings.append(_finding("full_surface_category_empty_without_typed_na", f"$.surface_category_dispositions.{category}.disposition", category))

    return tuple(findings)


def graduation_surface_findings(
    target_root: Path,
    *,
    target_skill_id: str,
    profile: Mapping[str, Any] | None,
    native_check_ids: Iterable[str],
    model_deepening_check_id: str | None,
) -> tuple[SurfaceInventoryFinding, ...]:
    """Load and validate the mandatory graduation inventory for one target."""

    if not isinstance(profile, Mapping):
        return (_finding("graduation_surface_inventory_missing", "$.depth_profile", "target must declare surface_inventory before graduation"),)
    declaration = profile.get("surface_inventory")
    if not isinstance(declaration, Mapping):
        return (_finding("graduation_surface_inventory_missing", "$.depth_profile.surface_inventory", "target must declare surface_inventory before graduation"),)
    relative = _text(declaration.get("path"))
    _validate_path(relative, findings := [])
    if findings:
        return tuple(_finding("graduation_" + item.code, item.path, item.detail) for item in findings)
    inventory_path = (target_root / relative).resolve()
    if not inventory_path.is_file() or not inventory_path.is_relative_to(target_root.resolve()):
        return (_finding("graduation_surface_inventory_file_missing", relative),)
    try:
        payload = json.loads(inventory_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return (_finding("graduation_surface_inventory_unreadable", relative, exc),)
    findings = list(
        validate_surface_inventory(
            payload,
            target_skill_id=target_skill_id,
            native_check_ids=native_check_ids,
            model_deepening_check_id=model_deepening_check_id,
            path=relative,
        )
    )
    # Graduation must consume the same independent implementation denominator
    # that check-depth validates.  The compact rows/route projection alone is
    # not sufficient: a target can otherwise graduate while an API, effect,
    # fault, recovery, installer, or UI-like action is absent from its model.
    command_surface: Sequence[Mapping[str, Any]] = ()
    route_entries: Sequence[Mapping[str, Any]] = ()
    command_handlers: Mapping[str, Any] | None = None
    if target_skill_id == "skillguard":
        # SkillGuard's own command/route registry is target-owned source data;
        # use it only for the self target, never as a generic domain oracle.
        try:
            from checker_engine import (  # type: ignore
                COMMANDS,
                current_checker_command_surface,
                current_route_entries,
            )

            command_surface = current_checker_command_surface()
            route_entries = current_route_entries()
            command_handlers = COMMANDS
        except ImportError:
            # A standalone library consumer cannot silently downgrade the
            # gate.  The source-derived scan still runs and reports any
            # denominator mismatch; no compatibility path is introduced.
            command_surface = ()
            route_entries = ()
            command_handlers = None
    findings.extend(
        validate_full_surface_inventory(
            payload,
            target_root=target_root,
            command_surface=command_surface,
            route_entries=route_entries,
            command_handlers=command_handlers,
            native_check_ids=native_check_ids,
            model_deepening_check_id=model_deepening_check_id,
        )
    )
    return tuple(
        _finding("graduation_" + item.code, item.path, item.detail)
        for item in findings
    )
