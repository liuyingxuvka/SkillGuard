"""Typed function-route selection for compiled SkillGuard V2 contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


TOKEN_RE = re.compile(r"[a-zA-Z0-9_\-]+|[\u4e00-\u9fff]+")


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
            "artifact_type": "skillguard_v2_route_decision",
            "ok": self.ok,
            "status": self.status,
            "function_ids": list(self.function_ids),
            "route_ids": list(self.route_ids),
            "claim_scope": self.claim_scope,
            "findings": [row.to_dict() for row in self.findings],
            "claim_boundary": "Selection chooses only routes declared by the compiled contract; it does not execute them.",
        }


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(text)}


def _function_score(function: Mapping[str, Any], request_text: str) -> int:
    text = request_text.lower()
    intent = str(function.get("business_intent", "")).lower()
    patterns = [intent, *(str(item).lower() for item in function.get("intent_patterns", []))]
    score = 0
    request_tokens = _tokens(text)
    for pattern in patterns:
        if not pattern:
            continue
        if pattern in text:
            score += 100 + len(_tokens(pattern))
        else:
            score += 5 * len(request_tokens & _tokens(pattern))
    for exclusion in function.get("exclude_patterns", []):
        if str(exclusion).lower() in text:
            score -= 1000
    return score


def _compatible(functions: Sequence[Mapping[str, Any]], function_ids: Sequence[str]) -> tuple[RouteFinding, ...]:
    selected = set(function_ids)
    findings: list[RouteFinding] = []
    for function in functions:
        function_id = str(function.get("function_id", ""))
        allowed = {str(item) for item in function.get("composable_with", [])}
        others = selected - {function_id}
        if others and not others.issubset(allowed):
            findings.append(
                RouteFinding(
                    "incompatible_function_composition",
                    f"{function_id} cannot compose with {', '.join(sorted(others - allowed))}",
                    function_id,
                )
            )
    return tuple(findings)


def select_routes(contract: Mapping[str, Any], request: Mapping[str, Any]) -> RouteDecision:
    functions = [row for row in contract.get("functions", []) if isinstance(row, Mapping)]
    function_index = {str(row.get("function_id", "")): row for row in functions}
    route_ids_known = {
        str(row.get("route_id", ""))
        for row in contract.get("routes", [])
        if isinstance(row, Mapping)
    }
    findings: list[RouteFinding] = []
    selected_functions: list[str] = []
    explicit_routes = tuple(str(item) for item in request.get("route_ids", []))
    explicit_functions = tuple(str(item) for item in request.get("function_ids", []))
    if explicit_routes:
        unknown_routes = tuple(route_id for route_id in explicit_routes if route_id not in route_ids_known)
        if unknown_routes:
            findings.extend(
                RouteFinding("unknown_route", "route is not declared by the compiled contract", route_id)
                for route_id in unknown_routes
            )
        for function_id, function in function_index.items():
            if set(explicit_routes) & {str(item) for item in function.get("route_ids", [])}:
                selected_functions.append(function_id)
    elif explicit_functions:
        for function_id in explicit_functions:
            if function_id not in function_index:
                findings.append(RouteFinding("unknown_function", "function is not declared", function_id))
            else:
                selected_functions.append(function_id)
    else:
        request_text = str(request.get("intent") or request.get("request") or "").strip()
        if not request_text:
            findings.append(RouteFinding("missing_route_intent", "request needs intent, function_ids, or route_ids"))
        else:
            scored = sorted(
                ((_function_score(function, request_text), function_id) for function_id, function in function_index.items()),
                key=lambda row: (-row[0], row[1]),
            )
            if not scored or scored[0][0] <= 0:
                findings.append(RouteFinding("no_route_match", "no declared function matches the request"))
            else:
                top_score = scored[0][0]
                top = tuple(function_id for score, function_id in scored if score == top_score)
                if len(top) != 1:
                    findings.append(
                        RouteFinding("ambiguous_route_match", f"equal top candidates: {', '.join(top)}")
                    )
                else:
                    selected_functions.append(top[0])

    selected_functions = list(dict.fromkeys(selected_functions))
    if len(selected_functions) > 1:
        if not bool(request.get("compose", False)):
            findings.append(
                RouteFinding(
                    "composition_not_requested",
                    "multiple functions require compose=true",
                    ",".join(selected_functions),
                )
            )
        else:
            findings.extend(_compatible([function_index[item] for item in selected_functions], selected_functions))
    selected_routes: list[str] = []
    if explicit_routes and not findings:
        selected_routes.extend(explicit_routes)
    else:
        for function_id in selected_functions:
            selected_routes.extend(str(item) for item in function_index[function_id].get("route_ids", []))
    if not selected_routes and not findings:
        findings.append(RouteFinding("selected_function_has_no_route", "selected function declares no route"))
    if findings:
        return RouteDecision(
            False,
            "blocked",
            tuple(selected_functions),
            tuple(selected_routes),
            str(request.get("claim_scope", "routine")),
            tuple(findings),
        )
    return RouteDecision(
        True,
        "selected",
        tuple(selected_functions),
        tuple(dict.fromkeys(selected_routes)),
        str(request.get("claim_scope", "routine")),
    )
