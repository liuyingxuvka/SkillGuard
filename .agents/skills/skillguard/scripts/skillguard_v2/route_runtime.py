"""Deterministic three-valued route selection for SkillContract v3."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .compact_contract import ValidatedContract


@dataclass(frozen=True)
class RouteFinding:
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


@dataclass(frozen=True)
class RouteDecision:
    ok: bool
    status: str
    route_ids: tuple[str, ...]
    findings: tuple[RouteFinding, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "skillguard_v3_route_decision",
            "ok": self.ok,
            "status": self.status,
            "route_ids": list(self.route_ids),
            "findings": [row.to_dict() for row in self.findings],
            "claim_boundary": "Selection asserts only declared routes and starts no producer.",
        }


def _json_equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left is right
    if left is None or right is None:
        return left is None and right is None
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        if not math.isfinite(float(left)) or not math.isfinite(float(right)):
            return False
        return left == right
    if isinstance(left, str) or isinstance(right, str):
        return isinstance(left, str) and isinstance(right, str) and left == right
    if isinstance(left, list) or isinstance(right, list):
        return isinstance(left, list) and isinstance(right, list) and len(left) == len(right) and all(_json_equal(a, b) for a, b in zip(left, right))
    if isinstance(left, Mapping) or isinstance(right, Mapping):
        return isinstance(left, Mapping) and isinstance(right, Mapping) and set(left) == set(right) and all(_json_equal(left[key], right[key]) for key in left)
    return False


def _assertion(value: str | Sequence[str] | None) -> tuple[str, ...] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return (value,)
    return tuple(value)


def select_routes(
    validated: ValidatedContract,
    facts: Mapping[str, Any],
    asserted_scope: Sequence[str],
    explicit_assertion: str | Sequence[str] | None = None,
) -> RouteDecision:
    """Select all routes from facts, then verify scope/route assertions exactly."""

    if not isinstance(facts, Mapping):
        return RouteDecision(False, "blocked", (), (RouteFinding("missing_fact", "$.facts", "facts object required"),))
    matches: list[str] = []
    unresolved: list[tuple[str, str]] = []
    groups: dict[str, list[str]] = {}
    for route_id, route in validated.by_route.items():
        missing: list[str] = []
        ruled_out = False
        for predicate in route["when"]:
            fact = str(predicate["fact"])
            if fact not in facts:
                missing.append(fact)
            elif not _json_equal(facts[fact], predicate["equals"]):
                ruled_out = True
                break
        if ruled_out:
            continue
        if missing:
            unresolved.extend((route_id, fact) for fact in missing)
            continue
        matches.append(route_id)
        groups.setdefault(str(route["choice_group"]), []).append(route_id)
    if unresolved:
        details = ", ".join(f"{route}:{fact}" for route, fact in unresolved)
        return RouteDecision(False, "blocked", (), (RouteFinding("missing_fact", "$.facts", details),))
    ambiguous = [route_id for rows in groups.values() if len(rows) > 1 for route_id in rows]
    if ambiguous:
        return RouteDecision(False, "blocked", (), (RouteFinding("ambiguous_route", "$.routes", ",".join(ambiguous)),))
    if not matches:
        return RouteDecision(False, "blocked", (), (RouteFinding("no_route", "$.facts", "no declared route matches"),))
    if len(matches) > 1:
        composition_ids = {str(validated.by_route[route_id].get("composition_id", "")) for route_id in matches}
        if len(composition_ids) != 1 or "" in composition_ids:
            return RouteDecision(False, "blocked", (), (RouteFinding("incompatible_composition", "$.routes", ",".join(matches)),))
    selected = tuple(route_id for route_id in validated.by_route if route_id in set(matches))
    scope = tuple(asserted_scope)
    if not scope or len(scope) != len(set(scope)) or set(scope) != set(selected):
        return RouteDecision(False, "blocked", selected, (RouteFinding("scope_mismatch", "$.scope", "scope must equal selected routes"),))
    explicit = _assertion(explicit_assertion)
    if explicit is not None and (not explicit or len(explicit) != len(set(explicit)) or set(explicit) != set(selected)):
        return RouteDecision(False, "blocked", selected, (RouteFinding("route_assertion_mismatch", "$.route_ids", "route assertion must equal selected routes"),))
    return RouteDecision(True, "selected", selected)


__all__ = ["RouteDecision", "RouteFinding", "select_routes"]
