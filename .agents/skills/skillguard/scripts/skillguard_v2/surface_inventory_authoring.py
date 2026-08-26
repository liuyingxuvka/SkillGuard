"""Author the current SkillGuard implementation-surface semantic map.

The reverse source scan is intentionally structural.  This module is the
small, target-owned authoring bridge that turns an explicit, reviewed rule
set into a current semantic inventory.  It never derives a model edge from a
check, a function name, a historical synthetic obligation, or a row count.
Every source surface receives the baseline current-audit obligation plus the
explicit domain decisions selected by the rules below.  The generated map
keeps the rule decisions and the per-surface expansion so the resulting
inventory can be inspected without re-running a heuristic.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


_SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(_SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_ROOT))

from skillguard_v2.surface_inventory import (  # noqa: E402
    PublicSourceSurface,
    discover_full_source_surfaces,
    surface_inventory_hash,
)


SEMANTIC_MAP_SCHEMA = "skillguard.surface_semantic_map.v1"
CURRENT_MODEL_OBLIGATIONS = (
    "obligation:static-audit",
    "obligation:deep-audit",
    "obligation:model-authority",
    "obligation:route-ownership",
    "obligation:author-entry-loading",
    "obligation:packet-consumption",
    "obligation:guard-run-identity",
    "obligation:claimed-run",
    "obligation:failed-lock-recovery",
    "obligation:verifier-pass",
    "obligation:artifact-freshness",
    "obligation:durable-resume",
    "obligation:loop-liveness",
    "obligation:exact-closure",
    "obligation:assurance-diagnostics",
    "obligation:no-former-authority-success",
    "obligation:portfolio-freshness",
    "obligation:depth-native-authority",
    "obligation:target-native-deepening-closure",
    "obligation:execution-depth-closure",
    "obligation:unique-depth-evidence",
    "obligation:author-repository-adoption",
    "obligation:global-router-handoff",
    "obligation:provenance",
)


@dataclass(frozen=True)
class SemanticRule:
    """One explicit target-author decision; no selector is inferred."""

    rule_id: str
    model_obligation_ids: tuple[str, ...]
    reason: str
    proof_ref: str
    source_paths: tuple[str, ...] = ()
    kinds: tuple[str, ...] = ()

    def matches(self, surface: PublicSourceSurface) -> bool:
        if self.source_paths and surface.source_path not in self.source_paths:
            return False
        if self.kinds and surface.kind not in self.kinds:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "rule_id": self.rule_id,
            "model_obligation_ids": list(self.model_obligation_ids),
            "reason": self.reason,
            "proof_ref": self.proof_ref,
        }
        if self.source_paths:
            payload["source_paths"] = list(self.source_paths)
        if self.kinds:
            payload["kinds"] = list(self.kinds)
        return payload


_P = ".agents/skills/skillguard/"
_MODEL_PROOF = _P + ".skillguard/flowguard_contract_model.py"
_CONTRACT_PROOF = _P + ".skillguard/contract-source.json"
_CHECK_PROOF = _P + ".skillguard/check-manifest.json"


# This is deliberately an author-owned table, not a classifier.  Each row is
# a written decision about a source boundary and its contract obligation.  A
# surface may receive several rows because one implementation can participate
# in several explicitly declared lifecycle obligations.
SEMANTIC_RULES: tuple[SemanticRule, ...] = (
    SemanticRule(
        "decision:all-current-surfaces-static-audit",
        ("obligation:static-audit",),
        "Every source-observed implementation surface is admitted only through the current static inventory and its current source identity.",
        _P + ".skillguard/surface-inventory.json#full_discovery_fingerprint",
    ),
    SemanticRule(
        "decision:public-entry-route-ownership",
        ("obligation:route-ownership",),
        "Commands, options, routes, and UI entry surfaces are typed route boundaries and must have one current route owner.",
        _CONTRACT_PROOF + "#native_route_bindings",
        kinds=("command", "option", "route", "ui"),
    ),
    SemanticRule(
        "decision:entry-material-loading",
        ("obligation:author-entry-loading",),
        "Entry scripts and route-facing surfaces load only the declared target-owned material.",
        _CONTRACT_PROOF + "#native_route_bindings",
        kinds=("script", "command", "option", "route", "ui", "template"),
    ),
    SemanticRule(
        "decision:entry-packet-consumption",
        ("obligation:packet-consumption",),
        "Command and route inputs are explicit packets whose fields must be declared and consumed.",
        _CONTRACT_PROOF + "#step_bindings/step:select-function-route",
        kinds=("command", "option", "route"),
    ),
    SemanticRule(
        "decision:contract-model-authority",
        ("obligation:model-authority",),
        "Model, contract, schema, capability, and internal component surfaces are governed by the current executable model authority.",
        _MODEL_PROOF + "#build_model_test_alignment_plan",
        source_paths=(
            ".skillguard/flowguard_contract_model.py",
            ".skillguard/template_lifecycle_model.py",
            "scripts/skillguard_compile.py",
            "scripts/skillguard_v2/capability_contract.py",
            "scripts/skillguard_v2/capability_engine.py",
            "scripts/skillguard_v2/contract_compiler.py",
            "scripts/skillguard_v2/contract_schema.py",
            "scripts/skillguard_v2/flowguard_adapter.py",
            "assets/contract_fragments/catalog.json",
            "assets/schemas/skillguard_compiled_contract_v2.schema.json",
            "assets/schemas/skillguard_contract_source_v2.schema.json",
            "assets/schemas/skillguard_flowguard_model_export_v2.schema.json",
            "assets/schemas/skillguard_depth_profile_v2.schema.json",
        ),
    ),
    SemanticRule(
        "decision:deep-audit-and-native-depth",
        ("obligation:deep-audit", "obligation:depth-native-authority"),
        "Declared-check execution, depth supervision, test-mesh replay, and verification-contract surfaces own deep-audit and native-depth evidence.",
        _CONTRACT_PROOF + "#native_check_bindings",
        source_paths=(
            "scripts/skillguard_v2/check_runner.py",
            "scripts/skillguard_v2/declared_check_supervision.py",
            "scripts/skillguard_v2/execution_depth.py",
            "scripts/skillguard_v2/test_mesh.py",
            "scripts/skillguard_test_mesh.py",
            "scripts/skillguard_v2/verification_contract_review.py",
            "scripts/skillguard_verification_contract_review.py",
            "test-mesh.json",
            "references/skillguard-execution-depth.md",
            "references/skillguard-test-mesh.md",
        ),
    ),
    SemanticRule(
        "decision:run-identity-and-claim",
        ("obligation:guard-run-identity", "obligation:claimed-run"),
        "Run records, claim packets, locks, and supervisor boundaries own fresh run identity and claimed-run state.",
        _CHECK_PROOF + "#check:self:guard-run-identity",
        source_paths=(
            "scripts/skillguard_v2/execution_records.py",
            "scripts/skillguard_v2/run_store.py",
            "scripts/skillguard_v2/supervisor.py",
            "scripts/skillguard_v2/self_host.py",
        ),
    ),
    SemanticRule(
        "decision:failed-lock-recovery",
        ("obligation:failed-lock-recovery",),
        "Lock, writer, terminal, and run-state recovery surfaces must make failed or dead writers recoverable without silent success.",
        _CHECK_PROOF + "#check:self:failed-lock-recovery",
        source_paths=(
            "scripts/skillguard_v2/execution_records.py",
            "scripts/skillguard_v2/run_store.py",
            "scripts/skillguard_v2/supervisor.py",
            "scripts/skillguard_v2/native_terminal.py",
            "scripts/skillguard_v2/step_runtime.py",
            "scripts/skillguard_v2/installation.py",
            "scripts/skillguard_v2/target_installation.py",
        ),
    ),
    SemanticRule(
        "decision:verifier-and-artifact-freshness",
        ("obligation:verifier-pass", "obligation:artifact-freshness"),
        "Verifier, evidence, artifact, fingerprint, and receipt surfaces decide pass/skip and current artifact identity.",
        _CHECK_PROOF + "#check:self:validate-step-evidence",
        source_paths=(
            "scripts/skillguard_v2/artifact_validators.py",
            "scripts/skillguard_v2/check_runner.py",
            "scripts/skillguard_v2/evidence_store.py",
            "scripts/skillguard_v2/evidence_store_cli.py",
            "scripts/skillguard_v2/receipts.py",
            "scripts/skillguard_v2/native_evidence_identity.py",
            "scripts/skillguard_v2/native_terminal.py",
            "scripts/skillguard_v2/runtime_fingerprint.py",
            "scripts/skillguard_v2/wire_identity.py",
        ),
    ),
    SemanticRule(
        "decision:durable-resume",
        ("obligation:durable-resume",),
        "Step runtime and event-store surfaces own durable resume and replay state.",
        _CHECK_PROOF + "#check:self:record-step-event",
        source_paths=(
            "scripts/skillguard_v2/execution_records.py",
            "scripts/skillguard_v2/run_store.py",
            "scripts/skillguard_v2/step_runtime.py",
            "scripts/skillguard_v2/native_terminal.py",
        ),
    ),
    SemanticRule(
        "decision:loop-liveness",
        ("obligation:loop-liveness",),
        "Step, supervisor, portfolio, and depth-loop surfaces own finite progress and liveness evidence.",
        _CHECK_PROOF + "#check:self:obligation:loop-liveness",
        source_paths=(
            "scripts/skillguard_v2/step_runtime.py",
            "scripts/skillguard_v2/execution_depth.py",
            "scripts/skillguard_v2/supervisor.py",
            "scripts/skillguard_v2/portfolio_runner.py",
        ),
    ),
    SemanticRule(
        "decision:exact-closure",
        ("obligation:exact-closure",),
        "Closure and receipt surfaces consume only exact current terminal evidence before closure.",
        _CHECK_PROOF + "#check:self:issue-closure-receipt",
        source_paths=(
            "scripts/skillguard_v2/closure.py",
            "scripts/skillguard_v2/receipts.py",
            "scripts/skillguard.py",
            "assets/schemas/skillguard_closure_receipt_v2.schema.json",
            "assets/schemas/skillguard_functional_closure.schema.json",
        ),
    ),
    SemanticRule(
        "decision:assurance-diagnostics",
        ("obligation:assurance-diagnostics",),
        "Fault, diagnostic, capability, and assurance surfaces preserve authority while explaining blockers and outcomes.",
        _CHECK_PROOF + "#check:self:assurance-diagnostics",
        source_paths=(
            "scripts/skillguard_v2/assurance_diagnostics.py",
            "scripts/skillguard_v2/evidence_policy.py",
            "scripts/skillguard_v2/capability_engine.py",
            "assets/schemas/skillguard_assurance_diagnostic_input_v1.schema.json",
            "assets/schemas/skillguard_assurance_diagnostics_report_v1.schema.json",
        ),
        kinds=("fault", "recovery", "provider"),
    ),
    SemanticRule(
        "decision:no-former-authority-success",
        ("obligation:no-former-authority-success",),
        "Runtime-authority, closure, installation, and recovery surfaces reject former authority as a successful current result.",
        _CHECK_PROOF + "#check:self:obligation:no-former-authority-success",
        source_paths=(
            "scripts/skillguard_v2/runtime_authority.py",
            "scripts/skillguard_v2/closure.py",
            "scripts/skillguard_v2/provenance.py",
            "scripts/skillguard_v2/run_store.py",
            "scripts/skillguard_v2/check_runner.py",
            "scripts/skillguard_v2/target_installation.py",
            "scripts/skillguard_v2/installation.py",
        ),
    ),
    SemanticRule(
        "decision:portfolio-freshness",
        ("obligation:portfolio-freshness",),
        "Portfolio preparation, impact, execution, and graduation surfaces use only the maintenance-unit evidence that is current for that unit.",
        _CHECK_PROOF + "#check:self:scan-maintenance-unit-freshness",
        source_paths=(
            "scripts/skillguard_v2/portfolio.py",
            "scripts/skillguard_v2/portfolio_records.py",
            "scripts/skillguard_v2/portfolio_runner.py",
            "scripts/skillguard_v2/portfolio_cli.py",
            "scripts/skillguard_v2/portfolio_impact_receipt.py",
            "assets/schemas/skillguard_portfolio_registry_v2.schema.json",
            "assets/schemas/skillguard_portfolio_graduation_receipt_v2.schema.json",
            "assets/schemas/skillguard_portfolio_graduation_evidence_v2.schema.json",
            "assets/schemas/skillguard_portfolio_impact_receipt_v1.schema.json",
        ),
    ),
    SemanticRule(
        "decision:target-native-deepening",
        ("obligation:target-native-deepening-closure",),
        "Target-native model-deepening and test-mesh surfaces remain target-owned and current before broad closure.",
        _CHECK_PROOF + "#check:self:target-native-deepening-closure",
        source_paths=(
            "scripts/skillguard_v2/execution_depth.py",
            "scripts/skillguard_v2/test_mesh.py",
            "scripts/skillguard_test_mesh.py",
            "assets/schemas/skillguard_functional_closure.schema.json",
        ),
    ),
    SemanticRule(
        "decision:execution-depth-closure",
        ("obligation:execution-depth-closure",),
        "Execution-depth, closure, and step result surfaces consume the exact current depth profile before closure.",
        _CHECK_PROOF + "#check:self:check-run-closure",
        source_paths=(
            "scripts/skillguard_v2/execution_depth.py",
            "scripts/skillguard_v2/check_runner.py",
            "scripts/skillguard_v2/closure.py",
            "scripts/skillguard_v2/execution_records.py",
            "assets/schemas/skillguard_depth_profile_v2.schema.json",
        ),
    ),
    SemanticRule(
        "decision:unique-depth-evidence",
        ("obligation:unique-depth-evidence",),
        "Evidence-store, receipt, identity, and depth surfaces keep each contribution unique to its declared owner and subject.",
        _CHECK_PROOF + "#check:self:declared-check-runtime",
        source_paths=(
            "scripts/skillguard_v2/evidence_store.py",
            "scripts/skillguard_v2/receipts.py",
            "scripts/skillguard_v2/native_evidence_identity.py",
            "scripts/skillguard_v2/execution_depth.py",
            "scripts/skillguard_v2/check_runner.py",
        ),
    ),
    SemanticRule(
        "decision:author-repository-adoption",
        ("obligation:author-repository-adoption",),
        "Author-repository adoption surfaces keep maintenance instructions private to the author workspace and do not enter consumer projections.",
        _CHECK_PROOF + "#check:self:audit-author-repository-adoption",
        source_paths=(
            "scripts/skillguard_v2/project_adoption.py",
            "scripts/skillguard_v2/self_host.py",
            "scripts/skillguard_self_host.py",
            "AGENTS.md",
        ),
    ),
    SemanticRule(
        "decision:global-router-handoff",
        ("obligation:global-router-handoff",),
        "Global-router discovery, projection, transaction, route index, and consumer projection surfaces own the exact handoff boundary.",
        _CHECK_PROOF + "#check:self:verify-target-handoff",
        source_paths=(
            "scripts/skillguard_v2/global_router_discovery.py",
            "scripts/skillguard_v2/global_router_projection.py",
            "scripts/skillguard_v2/global_router_transaction.py",
            "scripts/skillguard_v2/content_projection.py",
            "scripts/skillguard_v2/consumer_distribution.py",
            "scripts/skillguard.py",
            "scripts/generate_route_index.py",
            "references/skillguard-route-index.json",
        ),
    ),
    SemanticRule(
        "decision:provenance-and-installation",
        ("obligation:provenance",),
        "Source, installation, privacy, release, wire-identity, and target-installation surfaces preserve non-downgrade provenance.",
        _CHECK_PROOF + "#check:self:verify-release-provenance",
        source_paths=(
            "scripts/skillguard_v2/provenance.py",
            "scripts/skillguard_provenance.py",
            "scripts/skillguard_v2/portable_content.py",
            "scripts/skillguard_v2/wire_identity.py",
            "scripts/skillguard_v2/installation.py",
            "scripts/skillguard_v2/installation_receipt.py",
            "scripts/skillguard_v2/target_installation.py",
            "scripts/skillguard_v2/installed_parity.py",
            "scripts/skillguard_v2/privacy.py",
            "scripts/skillguard_privacy.py",
            "scripts/skillguard_consumer_install.py",
            "scripts/skillguard_install.py",
            "scripts/skillguard_v2/runtime_authority.py",
            "scripts/skillguard_v2/runtime_fingerprint.py",
            "VERSION",
            "pyproject.toml",
            "public-export-policy.json",
        ),
        kinds=("installer", "artifact", "config"),
    ),
    SemanticRule(
        "decision:internal-components-model-owned",
        ("obligation:model-authority",),
        "Every complete internal component review group is explicitly model-owned; members share this same current obligation set.",
        _MODEL_PROOF + "#build_model_test_alignment_plan",
        kinds=("component",),
    ),
    SemanticRule(
        "decision:public-api-model-owned",
        ("obligation:model-authority",),
        "Every discovered API/export surface is a target-owned contract boundary and is explicitly model-owned before it can be exposed.",
        _MODEL_PROOF + "#CodeContract",
        kinds=("api", "export"),
    ),
    SemanticRule(
        "decision:fault-diagnostic-owned",
        ("obligation:assurance-diagnostics",),
        "Every discovered fault surface is an explicit diagnostic outcome and cannot silently become a successful path.",
        _CHECK_PROOF + "#check:self:assurance-diagnostics",
        kinds=("fault",),
    ),
    SemanticRule(
        "decision:recovery-authority-owned",
        ("obligation:failed-lock-recovery", "obligation:no-former-authority-success"),
        "Every discovered recovery surface is an explicit recovery boundary with visible failure and current-authority checks.",
        _CHECK_PROOF + "#check:self:failed-lock-recovery",
        kinds=("recovery",),
    ),
    SemanticRule(
        "decision:provider-verifier-owned",
        ("obligation:model-authority", "obligation:verifier-pass"),
        "Every provider surface is a model-owned boundary whose result must be verifier-owned before closure.",
        _CHECK_PROOF + "#check:self:validate-step-evidence",
        kinds=("provider",),
    ),
    SemanticRule(
        "decision:effect-closure-owned",
        ("obligation:exact-closure",),
        "Every observed effect is admitted only when the current closure can account for its terminal evidence.",
        _CHECK_PROOF + "#check:self:issue-closure-receipt",
        kinds=("effect",),
    ),
)


def _wire_hash(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as handle:
            temporary_name = handle.name
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        if temporary_name and Path(temporary_name).exists():
            Path(temporary_name).unlink()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def _compiled_obligation_ids(target_root: Path) -> tuple[str, ...]:
    payload = _load_json(target_root / ".skillguard" / "compiled-contract.json")
    values = tuple(str(row["obligation_id"]) for row in payload.get("obligations", []) if isinstance(row, Mapping))
    if values != CURRENT_MODEL_OBLIGATIONS:
        raise ValueError(
            "compiled contract obligation denominator changed; author a new map instead of inheriting it"
        )
    return values


def _rules_for_surface(surface: PublicSourceSurface) -> tuple[SemanticRule, ...]:
    matched = tuple(rule for rule in SEMANTIC_RULES if rule.matches(surface))
    if not matched:
        raise ValueError(f"no explicit semantic rule for {surface.surface_id}")
    return matched


def _surface_model_ids(surface: PublicSourceSurface) -> tuple[str, ...]:
    result: list[str] = []
    for rule in _rules_for_surface(surface):
        for obligation_id in rule.model_obligation_ids:
            if obligation_id not in result:
                result.append(obligation_id)
    unknown = set(result) - set(CURRENT_MODEL_OBLIGATIONS)
    if unknown:
        raise ValueError(f"semantic rule references unknown compiled obligation(s): {sorted(unknown)}")
    return tuple(sorted(result))


def _fresh_structural_row(surface: PublicSourceSurface) -> dict[str, Any]:
    value = surface.to_dict()
    value.update(
        {
            "disposition": "governed",
            "intent_id": "intent:skillguard:" + hashlib.sha256(surface.surface_id.encode()).hexdigest()[:24],
            "owner_id": "owner:self:runtime-surface",
            "obligation_ids": [],
            "required_check_ids": ["check:self:surface-inventory", "check:self:assurance-diagnostics"],
            "adequacy_check_ids": [
                "check:self:surface-inventory",
                "check:self:target-native-deepening-closure",
                "check:self:failed-lock-recovery",
                "check:self:assurance-diagnostics",
            ],
            "execution_owner_ids": ["owner:self:runtime-surface"],
            "evidence_subject_ids": ["subject:surface:" + surface.surface_id],
            "lifecycle_phase": "runtime",
            "consumer_exposure": "author-runtime",
            "write_authority": "target-owned",
        }
    )
    return value


def _merge_structural_and_authority(
    surface: PublicSourceSurface,
    old_row: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not old_row:
        return _fresh_structural_row(surface)
    row = dict(old_row)
    structural = surface.to_dict()
    for field, value in structural.items():
        row[field] = value
    # Old surface-local obligation IDs are not current model authority.  The
    # caller replaces them with the explicit compiled IDs below.
    row.pop("component_members", None)
    if surface.component_members:
        row["component_members"] = list(surface.component_members)
    for field, default in _fresh_structural_row(surface).items():
        row.setdefault(field, default)
    return row


def _rule_summary(surface: PublicSourceSurface) -> list[str]:
    return [rule.rule_id for rule in _rules_for_surface(surface)]


def build_current_semantic_map(
    *,
    target_root: Path,
    inventory_path: Path,
    command_surface: Sequence[Mapping[str, Any]],
    route_entries: Sequence[Mapping[str, Any]],
    command_handlers: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build the current map and inventory from explicit author rules."""

    target_root = target_root.resolve()
    obligation_ids = _compiled_obligation_ids(target_root)
    scan = discover_full_source_surfaces(
        target_root,
        command_surface=command_surface,
        route_entries=route_entries,
        command_handlers=command_handlers,
    )
    if scan.findings:
        raise ValueError("fresh source discovery is not clean; semantic authoring is blocked")
    old = _load_json(inventory_path) if inventory_path.is_file() else {}
    old_rows = {
        str(row.get("surface_id")): row
        for row in old.get("full_surfaces", [])
        if isinstance(row, Mapping) and row.get("surface_id")
    }

    rows: list[dict[str, Any]] = []
    for surface in sorted(scan.surfaces, key=lambda item: item.surface_id):
        model_ids = _surface_model_ids(surface)
        row = _merge_structural_and_authority(surface, old_rows.get(surface.surface_id))
        rule_ids = _rule_summary(surface)
        row["intent_id"] = "intent:skillguard:surface-map:" + hashlib.sha256(
            "|".join(rule_ids).encode("utf-8")
        ).hexdigest()[:24]
        row["model_obligation_ids"] = list(model_ids)
        row["obligation_ids"] = list(model_ids)
        rows.append(row)

    # A component row is one author review unit, even though the reverse
    # discovery exposes several effect/fault/provider/recovery observations
    # inside it.  Close each complete group over the union of its explicit
    # member decisions, then use that exact same set for every member.  This
    # is a deliberate author decision, not a check-name or symbol heuristic.
    surfaces_by_id = {surface.surface_id: surface for surface in scan.surfaces}
    component_groups: dict[str, list[int]] = {}
    for index, row in enumerate(rows):
        if row.get("review_granularity") == "component":
            component_groups.setdefault(str(row["review_group_id"]), []).append(index)
    for indices in component_groups.values():
        union: set[str] = set()
        group_rule_ids: set[str] = set()
        for index in indices:
            union.update(str(value) for value in rows[index]["model_obligation_ids"])
            group_rule_ids.update(
                _rule_summary(surfaces_by_id[str(rows[index]["surface_id"])])
            )
        normalized = sorted(union)
        intent_id = "intent:skillguard:component-map:" + hashlib.sha256(
            "|".join(sorted(group_rule_ids)).encode("utf-8")
        ).hexdigest()[:24]
        for index in indices:
            rows[index]["model_obligation_ids"] = normalized
            rows[index]["obligation_ids"] = normalized
            rows[index]["intent_id"] = intent_id

    bindings: list[dict[str, Any]] = []
    by_obligation: dict[str, list[str]] = {obligation_id: [] for obligation_id in obligation_ids}
    for row in rows:
        surface_id = str(row["surface_id"])
        model_ids = tuple(str(value) for value in row["model_obligation_ids"])
        for obligation_id in model_ids:
            by_obligation[obligation_id].append(surface_id)
        member_rows = component_groups.get(str(row["review_group_id"]), []) if row.get("review_granularity") == "component" else []
        member_rule_ids: set[str] = set()
        if member_rows:
            for member_index in member_rows:
                member_surface = surfaces_by_id[str(rows[member_index]["surface_id"])]
                member_rule_ids.update(_rule_summary(member_surface))
        else:
            member_rule_ids.update(_rule_summary(surfaces_by_id[surface_id]))
        bindings.append(
            {
                "surface_id": surface_id,
                "model_obligation_ids": list(model_ids),
                "rule_ids": sorted(member_rule_ids),
                "decision": "explicit-author-component-group-closure" if member_rows else "explicit-author-rule",
            }
        )

    missing = [obligation_id for obligation_id, surfaces in by_obligation.items() if not surfaces]
    if missing:
        raise ValueError(f"current compiled obligations have no explicit implementation surfaces: {missing}")

    map_payload: dict[str, Any] = {
        "schema_version": SEMANTIC_MAP_SCHEMA,
        "map_id": "map:self:surface-semantics-direct-current-2026-08-22-r1",
        "target_skill_id": "skillguard",
        "source_discovery_fingerprint": scan.discovery_fingerprint,
        "full_surface_ids": [surface.surface_id for surface in sorted(scan.surfaces, key=lambda item: item.surface_id)],
        "current_obligation_ids": list(obligation_ids),
        "decision_rules": [rule.to_dict() for rule in SEMANTIC_RULES],
        "surface_bindings": bindings,
        "obligation_bindings": [
            {
                "obligation_id": obligation_id,
                "disposition": "governed",
                "surface_ids": sorted(surface_ids),
                "reason": "This obligation has an explicit target-owned source boundary in the decision rules.",
                "proof_ref": next(
                    rule.proof_ref
                    for rule in SEMANTIC_RULES
                    if obligation_id in rule.model_obligation_ids
                ),
            }
            for obligation_id, surface_ids in by_obligation.items()
        ],
        "claim_boundary": (
            "Target-owned semantic decisions for the current SkillGuard source observation. "
            "The rules are not inferred from checks or names; they must be rewritten when "
            "the current source identity or contract obligation denominator changes."
        ),
    }
    map_payload["map_hash"] = _wire_hash(_canonical_bytes(map_payload))

    inventory = dict(old)
    inventory["schema_version"] = "skillguard.surface_inventory.v1"
    inventory.setdefault("inventory_id", "inventory:self:implementation-surface-direct-current-2026-08-22-r1")
    inventory["target_skill_id"] = "skillguard"
    inventory["source_kind"] = "target-owned-full-source-discovery"
    inventory["source_paths"] = list(scan.source_paths)
    inventory["full_surface_ids"] = list(map_payload["full_surface_ids"])
    inventory["full_surfaces"] = rows
    inventory["current_obligation_ids"] = list(obligation_ids)
    inventory["model_obligations"] = map_payload["obligation_bindings"]
    inventory["full_discovery_fingerprint"] = scan.discovery_fingerprint
    inventory["claim_boundary"] = (
        "This current reverse inventory is target-authored from an explicit semantic map and a "
        "fresh source observation. It accounts for every source-observed surface, but does not "
        "by itself prove native functional checks, installation, release, or consumer independence."
    )
    inventory["inventory_hash"] = surface_inventory_hash(inventory)
    return map_payload, inventory


def write_current_semantic_map_and_inventory(
    *,
    target_root: Path,
    inventory_path: Path,
    map_path: Path,
    command_surface: Sequence[Mapping[str, Any]],
    route_entries: Sequence[Mapping[str, Any]],
    command_handlers: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Write both current target-owned projections atomically."""

    mapping, inventory = build_current_semantic_map(
        target_root=target_root,
        inventory_path=inventory_path,
        command_surface=command_surface,
        route_entries=route_entries,
        command_handlers=command_handlers,
    )
    _atomic_write(map_path, mapping)
    _atomic_write(inventory_path, inventory)
    return mapping, inventory


__all__ = [
    "CURRENT_MODEL_OBLIGATIONS",
    "SEMANTIC_MAP_SCHEMA",
    "SEMANTIC_RULES",
    "SemanticRule",
    "build_current_semantic_map",
    "write_current_semantic_map_and_inventory",
]
