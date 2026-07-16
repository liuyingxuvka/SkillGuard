"""Authoritative portfolio capability-to-contract path declarations.

Capability labels live outside the generic FlowGuard topology.  This module
keeps their semantic ownership explicit and hash-bound in each compiled skill
contract so a portfolio job cannot relabel an unrelated but internally valid
route as evidence for another capability.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


PORTFOLIO_JOB_CLASS_IDS = frozenset(
    {
        "positive",
        "invalid_input",
        "recovery_or_resume",
        "out_of_scope",
        "native_check",
        "artifact_check",
        "judged_quality",
    }
)
CAPABILITY_PATH_FIELDS = (
    "function_ids",
    "route_ids",
    "step_ids",
    "obligation_ids",
    "check_ids",
    "artifact_ids",
)


@dataclass(frozen=True)
class CapabilityContractFinding:
    code: str
    path: str
    message: str


def _string_list(
    value: object,
    *,
    path: str,
    findings: list[CapabilityContractFinding],
    allow_empty: bool = False,
) -> list[str]:
    if (
        not isinstance(value, list)
        or any(not isinstance(item, str) or not item.strip() for item in value)
        or len(value) != len(set(value))
        or (not allow_empty and not value)
    ):
        findings.append(
            CapabilityContractFinding(
                "portfolio_capability_contract_id_list_invalid",
                path,
                "value must be a duplicate-free list of non-empty strings",
            )
        )
        return []
    return sorted(value)


def normalize_portfolio_capability_contracts(
    value: object,
) -> tuple[list[dict[str, Any]], tuple[CapabilityContractFinding, ...]]:
    """Return a deterministic declaration list and exact shape findings.

    The field is optional for ordinary compilation so older targets can still
    be inspected and directly replaced with the current shape. Portfolio graduation separately requires a
    declaration for every reviewed capability.
    """

    if value is None:
        return [], ()
    if not isinstance(value, list):
        return [], (
            CapabilityContractFinding(
                "portfolio_capability_contracts_not_array",
                "$.portfolio_capability_contracts",
                "portfolio capability contracts must be an array",
            ),
        )
    findings: list[CapabilityContractFinding] = []
    normalized: list[dict[str, Any]] = []
    seen_capabilities: set[str] = set()
    for capability_index, raw_capability in enumerate(value):
        path = f"$.portfolio_capability_contracts[{capability_index}]"
        if not isinstance(raw_capability, Mapping):
            findings.append(
                CapabilityContractFinding(
                    "portfolio_capability_contract_not_object",
                    path,
                    "capability contract must be an object",
                )
            )
            continue
        capability_id = str(raw_capability.get("capability_id", "")).strip()
        business_intent = str(raw_capability.get("business_intent", "")).strip()
        if not capability_id or capability_id in seen_capabilities:
            findings.append(
                CapabilityContractFinding(
                    "portfolio_capability_contract_id_invalid",
                    f"{path}.capability_id",
                    capability_id or "missing capability id",
                )
            )
        if capability_id:
            seen_capabilities.add(capability_id)
        if not business_intent:
            findings.append(
                CapabilityContractFinding(
                    "portfolio_capability_contract_intent_missing",
                    f"{path}.business_intent",
                    capability_id,
                )
            )
        raw_variants = raw_capability.get("path_variants")
        if not isinstance(raw_variants, list) or not raw_variants:
            findings.append(
                CapabilityContractFinding(
                    "portfolio_capability_contract_variants_missing",
                    f"{path}.path_variants",
                    capability_id,
                )
            )
            continue
        variants: list[dict[str, Any]] = []
        seen_variants: set[str] = set()
        for variant_index, raw_variant in enumerate(raw_variants):
            variant_path = f"{path}.path_variants[{variant_index}]"
            if not isinstance(raw_variant, Mapping):
                findings.append(
                    CapabilityContractFinding(
                        "portfolio_capability_variant_not_object",
                        variant_path,
                        capability_id,
                    )
                )
                continue
            variant_id = str(raw_variant.get("variant_id", "")).strip()
            if not variant_id or variant_id in seen_variants:
                findings.append(
                    CapabilityContractFinding(
                        "portfolio_capability_variant_id_invalid",
                        f"{variant_path}.variant_id",
                        variant_id or capability_id,
                    )
                )
            if variant_id:
                seen_variants.add(variant_id)
            job_class_ids = _string_list(
                raw_variant.get("job_class_ids"),
                path=f"{variant_path}.job_class_ids",
                findings=findings,
            )
            unknown_job_classes = sorted(
                set(job_class_ids) - PORTFOLIO_JOB_CLASS_IDS
            )
            if unknown_job_classes:
                findings.append(
                    CapabilityContractFinding(
                        "portfolio_capability_variant_job_class_invalid",
                        f"{variant_path}.job_class_ids",
                        ",".join(unknown_job_classes),
                    )
                )
            variant: dict[str, Any] = {
                "variant_id": variant_id,
                "job_class_ids": job_class_ids,
            }
            for field in CAPABILITY_PATH_FIELDS:
                variant[field] = _string_list(
                    raw_variant.get(field, []),
                    path=f"{variant_path}.{field}",
                    findings=findings,
                    allow_empty=field == "artifact_ids",
                )
            if variant_id and job_class_ids:
                variants.append(variant)
        if capability_id and business_intent and variants:
            normalized.append(
                {
                    "capability_id": capability_id,
                    "business_intent": business_intent,
                    "path_variants": sorted(
                        variants, key=lambda row: str(row["variant_id"])
                    ),
                }
            )
    return (
        sorted(normalized, key=lambda row: str(row["capability_id"])),
        tuple(findings),
    )


def capability_contract_topology_findings(
    capability_contracts: Sequence[Mapping[str, Any]],
    *,
    contract: Mapping[str, Any],
    checks: Sequence[Mapping[str, Any]],
) -> tuple[CapabilityContractFinding, ...]:
    """Validate every declared capability variant against one exact path."""

    functions = {
        str(row.get("function_id", "")): row
        for row in contract.get("functions", [])
        if isinstance(row, Mapping)
    }
    routes = {
        str(row.get("route_id", "")): row
        for row in contract.get("routes", [])
        if isinstance(row, Mapping)
    }
    steps = {
        str(row.get("step_id", "")): row
        for row in contract.get("steps", [])
        if isinstance(row, Mapping)
    }
    obligations = {
        str(row.get("obligation_id", "")): row
        for row in contract.get("obligations", [])
        if isinstance(row, Mapping)
    }
    check_index = {
        str(row.get("check_id", "")): row
        for row in checks
        if isinstance(row, Mapping)
    }
    artifacts = {
        str(row.get("artifact_id", "")): row
        for row in contract.get("artifacts", [])
        if isinstance(row, Mapping)
    }
    findings: list[CapabilityContractFinding] = []
    for capability in capability_contracts:
        capability_id = str(capability.get("capability_id", ""))
        for variant in capability.get("path_variants", []):
            if not isinstance(variant, Mapping):
                continue
            variant_id = str(variant.get("variant_id", ""))
            path = (
                f"$.portfolio_capability_contracts[{capability_id}]"
                f".path_variants[{variant_id}]"
            )
            selected_functions = set(variant.get("function_ids", []))
            selected_routes = set(variant.get("route_ids", []))
            selected_steps = set(variant.get("step_ids", []))
            selected_obligations = set(variant.get("obligation_ids", []))
            selected_checks = set(variant.get("check_ids", []))
            selected_artifacts = set(variant.get("artifact_ids", []))
            known = (
                selected_functions.issubset(functions)
                and selected_routes.issubset(routes)
                and selected_steps.issubset(steps)
                and selected_obligations.issubset(obligations)
                and selected_checks.issubset(check_index)
                and selected_artifacts.issubset(artifacts)
            )
            route_owned = known and all(
                str(routes[route_id].get("function_id", ""))
                in selected_functions
                for route_id in selected_routes
            )
            step_owned = known and all(
                str(steps[step_id].get("route_id", "")) in selected_routes
                for step_id in selected_steps
            )
            artifact_owned = known and all(
                str(artifacts[artifact_id].get("producer_step_id", ""))
                in selected_steps
                for artifact_id in selected_artifacts
            )
            obligation_bound = known and all(
                any(
                    step_id in set(obligations[obligation_id].get("owner_step_ids", []))
                    and any(
                        check_id
                        in set(
                            steps[step_id]
                            .get("binding", {})
                            .get("check_ids", [])
                        )
                        and obligation_id
                        in set(check_index[check_id].get("covers_obligation_ids", []))
                        for check_id in selected_checks
                    )
                    for step_id in selected_steps
                )
                for obligation_id in selected_obligations
            )
            check_bound = known and all(
                any(
                    check_id
                    in set(
                        steps[step_id].get("binding", {}).get("check_ids", [])
                    )
                    and any(
                        obligation_id
                        in set(check_index[check_id].get("covers_obligation_ids", []))
                        and step_id
                        in set(
                            obligations[obligation_id].get("owner_step_ids", [])
                        )
                        for obligation_id in selected_obligations
                    )
                    for step_id in selected_steps
                )
                for check_id in selected_checks
            )
            if not (
                known
                and route_owned
                and step_owned
                and artifact_owned
                and obligation_bound
                and check_bound
            ):
                findings.append(
                    CapabilityContractFinding(
                        "portfolio_capability_contract_path_invalid",
                        path,
                        capability_id,
                    )
                )
    return tuple(findings)


def capability_binding_matches_contract(
    binding: Mapping[str, Any],
    *,
    job_class_id: str,
    capability_contracts: Sequence[Mapping[str, Any]],
) -> bool:
    """Return true only for a precompiled semantic variant exact match."""

    capability_id = str(binding.get("capability_id", ""))
    authority = next(
        (
            row
            for row in capability_contracts
            if str(row.get("capability_id", "")) == capability_id
        ),
        None,
    )
    if authority is None:
        return False
    normalized_binding = {
        field: sorted(str(item) for item in binding.get(field, []))
        for field in CAPABILITY_PATH_FIELDS
    }
    return any(
        isinstance(variant, Mapping)
        and job_class_id in set(variant.get("job_class_ids", []))
        and all(
            normalized_binding[field]
            == sorted(str(item) for item in variant.get(field, []))
            for field in CAPABILITY_PATH_FIELDS
        )
        for variant in authority.get("path_variants", [])
    )
