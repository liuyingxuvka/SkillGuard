"""Deterministic fact-to-route selection for SkillContract v3."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


MISSING_FACT = "MISSING_FACT"
NO_ROUTE = "NO_ROUTE"
AMBIGUOUS_ROUTE = "AMBIGUOUS_ROUTE"
UNKNOWN_ROUTE = "UNKNOWN_ROUTE"


@dataclass(frozen=True)
class RouteFinding:
    code: str
    message: str
    target_id: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message, "target_id": self.target_id}


@dataclass(frozen=True)
class RouteDecision:
    ok: bool
    status: str
    function_ids: tuple[str, ...]
    route_ids: tuple[str, ...]
    claim_scope: str
    findings: tuple[RouteFinding, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "skillguard_v3_route_decision",
            "ok": self.ok,
            "status": self.status,
            "function_ids": list(self.function_ids),
            "route_ids": list(self.route_ids),
            "claim_scope": self.claim_scope,
            "findings": [row.to_dict() for row in self.findings],
            "claim_boundary": "Selection chooses only declared routes; it does not execute them.",
        }


def _facts(request: Mapping[str, Any]) -> Mapping[str, Any] | None:
    value = request.get("facts")
    return value if isinstance(value, Mapping) else None


def _predicates(route: Mapping[str, Any]) -> tuple[tuple[str, Any], ...] | None:
    value = route.get("when", [])
    if isinstance(value, Mapping):
        return tuple((str(key), expected) for key, expected in value.items())
    if not isinstance(value, list):
        return None
    result: list[tuple[str, Any]] = []
    for predicate in value:
        if not isinstance(predicate, Mapping) or not isinstance(predicate.get("fact"), str) or "equals" not in predicate:
            return None
        result.append((str(predicate["fact"]), predicate["equals"]))
    return tuple(result)


def _evaluate(route: Mapping[str, Any], facts: Mapping[str, Any]) -> tuple[str, tuple[str, ...]]:
    predicates = _predicates(route)
    route_id = str(route.get("route_id", ""))
    if predicates is None or not predicates:
        return "invalid", (route_id,)
    missing = tuple(sorted({fact for fact, _expected in predicates if fact not in facts}))
    if missing:
        return "missing", missing
    if all(facts[fact] == expected for fact, expected in predicates):
        return "match", ()
    return "mismatch", ()


def _decision(
    route_ids: list[str],
    routes: Mapping[str, Mapping[str, Any]],
    request: Mapping[str, Any],
    findings: list[RouteFinding],
) -> RouteDecision:
    function_ids = tuple(
        dict.fromkeys(
            str(routes[route_id]["function_id"])
            for route_id in route_ids
            if routes[route_id].get("function_id")
        )
    )
    claim_scope = str(request.get("claim_scope", "enforced"))
    if claim_scope != "enforced":
        findings.append(RouteFinding("claim_scope_must_be_enforced", "claim scope must be enforced", claim_scope))
    if findings:
        return RouteDecision(False, "blocked", function_ids, tuple(route_ids), claim_scope, tuple(findings))
    return RouteDecision(True, "selected", function_ids, tuple(dict.fromkeys(route_ids)), claim_scope)


def _function_composition_findings(
    functions: Mapping[str, Mapping[str, Any]],
    function_ids: list[str],
    request: Mapping[str, Any],
) -> list[RouteFinding]:
    findings: list[RouteFinding] = []
    unknown = [function_id for function_id in function_ids if function_id not in functions]
    findings.extend(RouteFinding("unknown_function", "function is not declared", item) for item in unknown)
    if len(function_ids) > 1 and not bool(request.get("compose", False)):
        findings.append(RouteFinding("composition_not_requested", "multiple functions require compose=true", ",".join(function_ids)))
    if len(function_ids) > 1 and bool(request.get("compose", False)):
        selected = set(function_ids)
        for function_id in function_ids:
            allowed = {str(item) for item in functions[function_id].get("composable_with", [])}
            if not (selected - {function_id}).issubset(allowed):
                findings.append(RouteFinding("incompatible_function_composition", "declared function composition is not symmetric", function_id))
    return findings


def select_routes(contract: Mapping[str, Any], request: Mapping[str, Any]) -> RouteDecision:
    """Select routes only by exact declared facts.

    No text scoring, similarity, first-match fallback, coercion or alternate
    route is permitted. Every blocked result returns before a producer can be
    started by the caller.
    """

    routes = [row for row in contract.get("routes", []) if isinstance(row, Mapping)]
    route_index = {str(row.get("route_id", "")): row for row in routes if row.get("route_id")}
    functions = {
        str(row.get("function_id", "")): row
        for row in contract.get("functions", [])
        if isinstance(row, Mapping) and row.get("function_id")
    }
    if not functions:
        # Compact v3 keeps the route declaration as the single public routing
        # record.  Internal callers may still name a function alias, so derive
        # the minimal lookup from route rows without restoring a second
        # top-level function registry.
        for row in routes:
            function_id = str(row.get("function_id", "")).strip()
            route_id = str(row.get("route_id", "")).strip()
            if not function_id or not route_id:
                continue
            functions.setdefault(
                function_id,
                {
                    "function_id": function_id,
                    "route_ids": [route_id],
                    "composable_with": list(row.get("composable_with", []))
                    if isinstance(row.get("composable_with", []), list)
                    else [],
                },
            )
    findings: list[RouteFinding] = []
    facts = _facts(request)
    raw_function_ids = request.get("function_ids", [])

    requested: list[str] = []
    if isinstance(request.get("route_id"), str):
        requested.append(str(request["route_id"]))
    raw = request.get("route_ids", [])
    if isinstance(raw, str):
        requested.append(raw)
    elif isinstance(raw, list):
        requested.extend(str(item) for item in raw)
    requested = list(dict.fromkeys(requested))
    if facts is None and not raw_function_ids and not requested:
        return RouteDecision(False, "blocked", (), (), str(request.get("claim_scope", "enforced")), (
            RouteFinding(MISSING_FACT, "request.facts must be an object", "facts"),
        ))
    if requested:
        unknown = [route_id for route_id in requested if route_id not in route_index]
        if unknown:
            findings.extend(RouteFinding(UNKNOWN_ROUTE, "route is not declared", route_id) for route_id in unknown)
            return _decision([], route_index, request, findings)
        if facts is None:
            findings.append(RouteFinding(MISSING_FACT, "request.facts must be an object", "facts"))
            return _decision([], route_index, request, findings)
        states = {route_id: _evaluate(route_index[route_id], facts) for route_id in requested}
        missing = sorted({fact for state, details in states.values() if state == "missing" for fact in details})
        invalid = [route_id for route_id, (state, _details) in states.items() if state == "invalid"]
        mismatch = [route_id for route_id, (state, _details) in states.items() if state == "mismatch"]
        if missing:
            findings.append(RouteFinding(MISSING_FACT, "route requires missing facts: " + ", ".join(missing), ",".join(requested)))
        elif invalid or mismatch:
            findings.append(RouteFinding(NO_ROUTE, "explicit route predicates do not match", ",".join((*mismatch, *invalid))))
        elif len(requested) > 1 and not all(route_index[route_id].get("composition_id") for route_id in requested):
            findings.append(RouteFinding(NO_ROUTE, "multiple routes require an explicit contract composition", ",".join(requested)))
        return _decision(requested if not findings else [], route_index, request, findings)

    if isinstance(raw_function_ids, str):
        function_ids = [raw_function_ids]
    elif isinstance(raw_function_ids, list):
        function_ids = list(dict.fromkeys(str(item) for item in raw_function_ids))
    else:
        function_ids = []
    if function_ids:
        findings.extend(_function_composition_findings(functions, function_ids, request))
        selected = [
            route_id
            for function_id in function_ids
            for route_id in functions.get(function_id, {}).get("route_ids", [])
            if str(route_id) in route_index
        ]
        if not findings:
            return _decision([str(item) for item in selected], route_index, request, findings)
        return _decision([], route_index, request, findings)

    matched_by_group: dict[str, list[str]] = {}
    any_missing: set[str] = set()
    invalid: list[str] = []
    for route in routes:
        route_id = str(route.get("route_id", ""))
        state, details = _evaluate(route, facts)
        if state == "match":
            group = str(route.get("choice_group", ""))
            matched_by_group.setdefault(group, []).append(route_id)
        elif state == "missing":
            any_missing.update(details)
        elif state == "invalid":
            invalid.append(route_id)

    ambiguous = [route_id for group in matched_by_group.values() if len(group) > 1 for route_id in group]
    if ambiguous:
        findings.append(RouteFinding(AMBIGUOUS_ROUTE, "same choice_group has multiple matches", ",".join(ambiguous)))
        return _decision([], route_index, request, findings)
    selected = [group[0] for group in matched_by_group.values()]
    if not selected:
        if any_missing:
            findings.append(RouteFinding(MISSING_FACT, "route predicates require missing facts: " + ", ".join(sorted(any_missing)), "facts"))
        else:
            message = "no declared route matches request facts"
            if invalid:
                message += "; invalid predicates: " + ", ".join(invalid)
            findings.append(RouteFinding(NO_ROUTE, message))
        return _decision([], route_index, request, findings)
    if len(selected) > 1 and not all(route_index[route_id].get("composition_id") for route_id in selected):
        findings.append(RouteFinding(NO_ROUTE, "multiple choice groups require an explicit contract composition", ",".join(selected)))
        return _decision([], route_index, request, findings)
    return _decision(selected, route_index, request, findings)


__all__ = [
    "AMBIGUOUS_ROUTE",
    "MISSING_FACT",
    "NO_ROUTE",
    "UNKNOWN_ROUTE",
    "RouteDecision",
    "RouteFinding",
    "select_routes",
]
