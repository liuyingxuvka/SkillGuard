"""Current adapter from real FlowGuard models to SkillGuard contract exports."""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    import flowguard
except ModuleNotFoundError:  # pragma: no cover - exercised through the patched missing-toolchain path
    flowguard = None  # type: ignore[assignment]

from .contract_schema import (
    MODEL_EXPORT_SCHEMA,
    SUPPORTED_FLOWGUARD_SCHEMA_VERSIONS,
    SchemaFinding,
    validate_model_export,
)


@dataclass(frozen=True)
class FlowGuardModelSnapshot:
    model_path: Path
    model_export: Mapping[str, Any]
    flowguard_schema_version: str
    flowguard_package_version: str
    flowguard_module_path: str


class FlowGuardAdapterError(ValueError):
    def __init__(self, findings: Sequence[SchemaFinding]):
        self.findings = tuple(findings)
        super().__init__("; ".join(f"{row.code}@{row.path}" for row in self.findings))


def _ensure_under_root(path: Path, root: Path) -> Path:
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise FlowGuardAdapterError(
            (SchemaFinding("model_path_outside_repository", "$.model_path", path.as_posix()),)
        ) from exc
    return resolved_path


def _package_version() -> str:
    try:
        return importlib.metadata.version("flowguard")
    except importlib.metadata.PackageNotFoundError:
        return "uninstalled"


def load_flowguard_model(model_path: Path, repository_root: Path) -> FlowGuardModelSnapshot:
    resolved_model = _ensure_under_root(model_path, repository_root)
    if not resolved_model.is_file():
        raise FlowGuardAdapterError(
            (SchemaFinding("flowguard_model_missing", "$.model_path", resolved_model.name),)
        )
    if flowguard is None:
        raise FlowGuardAdapterError(
            (SchemaFinding("flowguard_toolchain_missing", "$.flowguard", "install or connect the real FlowGuard package"),)
        )
    schema_version = str(getattr(flowguard, "SCHEMA_VERSION", ""))
    if schema_version not in SUPPORTED_FLOWGUARD_SCHEMA_VERSIONS:
        raise FlowGuardAdapterError(
            (
                SchemaFinding(
                    "unsupported_installed_flowguard_schema",
                    "$.flowguard_schema_version",
                    schema_version or "missing",
                ),
            )
        )
    module_key = hashlib.sha256(str(resolved_model).encode("utf-8")).hexdigest()[:16]
    module_name = f"skillguard_flowguard_model_{module_key}"
    spec = importlib.util.spec_from_file_location(module_name, resolved_model)
    if spec is None or spec.loader is None:
        raise FlowGuardAdapterError(
            (SchemaFinding("flowguard_model_unloadable", "$.model_path", resolved_model.name),)
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        # Contract compilation is a read of governed source authority. Execute
        # the exact source bytes directly so the read cannot leave a mutable
        # Python bytecode cache side effect inside the target control root.
        code = compile(
            resolved_model.read_bytes(),
            str(resolved_model),
            "exec",
            dont_inherit=True,
        )
        exec(code, module.__dict__)
    except Exception as exc:
        raise FlowGuardAdapterError(
            (SchemaFinding("flowguard_model_execution_failed", "$.model_path", type(exc).__name__),)
        ) from exc
    finally:
        sys.modules.pop(module_name, None)
    if getattr(module, "FLOWGUARD_MODEL_MARKER", "") != "flowguard-executable-model":
        raise FlowGuardAdapterError(
            (SchemaFinding("flowguard_model_marker_missing", "$.FLOWGUARD_MODEL_MARKER", resolved_model.name),)
        )
    exporter = getattr(module, "export_contract_model", None)
    if not callable(exporter):
        raise FlowGuardAdapterError(
            (SchemaFinding("flowguard_model_exporter_missing", "$.export_contract_model", resolved_model.name),)
        )
    exported = exporter()
    if not isinstance(exported, Mapping):
        raise FlowGuardAdapterError(
            (SchemaFinding("flowguard_model_export_not_object", "$", type(exported).__name__),)
        )
    findings = list(validate_model_export(exported))
    if exported.get("schema_version") != MODEL_EXPORT_SCHEMA:
        findings.append(SchemaFinding("flowguard_model_export_schema_mismatch", "$.schema_version", MODEL_EXPORT_SCHEMA))
    if str(exported.get("flowguard_schema_version", "")) != schema_version:
        findings.append(
            SchemaFinding(
                "flowguard_model_runtime_schema_mismatch",
                "$.flowguard_schema_version",
                f"model={exported.get('flowguard_schema_version')} runtime={schema_version}",
            )
        )
    if findings:
        raise FlowGuardAdapterError(tuple(findings))
    return FlowGuardModelSnapshot(
        model_path=resolved_model,
        model_export=dict(exported),
        flowguard_schema_version=schema_version,
        flowguard_package_version=_package_version(),
        flowguard_module_path=str(Path(flowguard.__file__).resolve()),
    )
