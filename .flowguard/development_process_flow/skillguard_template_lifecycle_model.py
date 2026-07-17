"""Executable child model for SkillGuard's neutral template lifecycle.

Every block is Input x State -> Set(Output x State).  Target Guards keep
semantic route, applicability, builder, and validator authority; SkillGuard
only validates the neutral projection and supervises current receipts.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer


FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"
MODEL_ID = "skillguard.template_lifecycle.v1"


@dataclass(frozen=True)
class TemplateRequest:
    route_current: bool = True
    projection_current: bool = True
    candidate_count: int = 1
    base_allowed: bool = True
    composition_safe: bool = False
    target_builder_current: bool = True
    target_validators_current: bool = True
    target_validation_passes: bool = True
    harvest_recorded: bool = True


@dataclass(frozen=True)
class ProjectionReady:
    request: TemplateRequest


@dataclass(frozen=True)
class SelectionReady:
    request: TemplateRequest
    disposition: str


@dataclass(frozen=True)
class InstanceReady:
    request: TemplateRequest


@dataclass(frozen=True)
class LifecycleReady:
    disposition: str


@dataclass(frozen=True)
class Blocked:
    reason: str


@dataclass(frozen=True)
class State:
    route_verified: bool = False
    projection_verified: bool = False
    selection_disposition: str = "not_run"
    selection_receipt_current: bool = False
    preview_current: bool = False
    target_builder_ran: bool = False
    target_validation_current: bool = False
    instance_receipt_current: bool = False
    harvest_recorded: bool = False
    semantic_owner: str = "target_guard"


class ResolveTargetProjection:
    name = "ResolveTargetProjection"
    reads = ()
    writes = ("route_verified", "projection_verified", "selection_disposition")
    accepted_input_type = TemplateRequest
    input_description = "target route receipt + target projection x fresh lifecycle state"
    output_description = "ProjectionReady or Blocked"
    idempotency = "Exact target request, route, and projection identities produce the same disposition."

    def apply(self, request: TemplateRequest, state: State) -> Iterable[FunctionResult]:
        state = State(semantic_owner=state.semantic_owner)
        if not request.route_current:
            yield FunctionResult(Blocked("target_native_route_not_current"), state, "route_not_current_blocked")
            return
        state = replace(state, route_verified=True)
        if not request.projection_current:
            yield FunctionResult(Blocked("target_template_projection_stale"), state, "projection_stale_blocked")
            return
        yield FunctionResult(
            ProjectionReady(request),
            replace(state, projection_verified=True),
            "target_projection_ready",
        )


class SelectTemplate:
    name = "SelectTemplate"
    reads = ("route_verified", "projection_verified")
    writes = ("selection_disposition", "selection_receipt_current", "preview_current")
    accepted_input_type = ProjectionReady
    input_description = "complete target candidate accounting x verified projection state"
    output_description = "SelectionReady or Blocked"
    idempotency = "Zero/one/many is deterministic for the exact current target projection."

    def apply(self, ready: ProjectionReady, state: State) -> Iterable[FunctionResult]:
        request = ready.request
        if not state.route_verified or not state.projection_verified:
            yield FunctionResult(Blocked("projection_not_verified"), state, "projection_not_verified_blocked")
            return
        if request.candidate_count < 0:
            yield FunctionResult(Blocked("candidate_inventory_invalid"), state, "candidate_inventory_invalid_blocked")
            return
        if request.candidate_count == 0:
            if not request.base_allowed:
                yield FunctionResult(
                    Blocked("no_candidate_and_base_forbidden"),
                    replace(state, selection_disposition="no_match"),
                    "base_forbidden_blocked",
                )
                return
            disposition = "base_no_match"
        elif request.candidate_count == 1:
            disposition = "single_selected"
        elif request.composition_safe:
            disposition = "composed"
        else:
            yield FunctionResult(
                Blocked("ambiguous_template_selection"),
                replace(state, selection_disposition="ambiguous_template_selection"),
                "ambiguous_selection_blocked",
            )
            return
        yield FunctionResult(
            SelectionReady(request, disposition),
            replace(
                state,
                selection_disposition=disposition,
                selection_receipt_current=True,
                preview_current=True,
            ),
            "selection_and_preview_current",
        )


class BuildAndValidateTargetInstance:
    name = "BuildAndValidateTargetInstance"
    reads = ("selection_receipt_current", "preview_current", "semantic_owner")
    writes = ("target_builder_ran", "target_validation_current", "instance_receipt_current")
    accepted_input_type = SelectionReady
    input_description = "current preview + target-native builder/validators x selected state"
    output_description = "InstanceReady or Blocked"
    idempotency = "Exact preview, builder, validator, and target inputs produce one current instance identity."

    def apply(self, selected: SelectionReady, state: State) -> Iterable[FunctionResult]:
        request = selected.request
        if not state.selection_receipt_current or not state.preview_current:
            yield FunctionResult(Blocked("selection_or_preview_stale"), state, "selection_preview_stale_blocked")
            return
        if not request.target_builder_current:
            yield FunctionResult(Blocked("target_builder_stale"), state, "target_builder_stale_blocked")
            return
        state = replace(state, target_builder_ran=True)
        if not request.target_validators_current:
            yield FunctionResult(Blocked("target_validator_inventory_stale"), state, "target_validators_stale_blocked")
            return
        if not request.target_validation_passes:
            yield FunctionResult(Blocked("target_native_validation_failed"), state, "target_validation_failed_blocked")
            return
        yield FunctionResult(
            InstanceReady(request),
            replace(
                state,
                target_validation_current=True,
                instance_receipt_current=True,
            ),
            "target_instance_current",
        )


class RecordHarvestDisposition:
    name = "RecordHarvestDisposition"
    reads = ("instance_receipt_current",)
    writes = ("harvest_recorded",)
    accepted_input_type = InstanceReady
    input_description = "current template instance + target harvest decision x instance state"
    output_description = "LifecycleReady or Blocked"
    idempotency = "The same target harvest decision records one disposition."

    def apply(self, instance: InstanceReady, state: State) -> Iterable[FunctionResult]:
        if not state.instance_receipt_current:
            yield FunctionResult(Blocked("instance_receipt_not_current"), state, "instance_receipt_stale_blocked")
            return
        if not instance.request.harvest_recorded:
            yield FunctionResult(Blocked("template_harvest_disposition_missing"), state, "harvest_missing_blocked")
            return
        yield FunctionResult(
            LifecycleReady(state.selection_disposition),
            replace(state, harvest_recorded=True),
            "template_lifecycle_ready",
        )


def template_route_precedes_selection(state: State, trace: object) -> InvariantResult:
    if state.selection_receipt_current and not (state.route_verified and state.projection_verified):
        return InvariantResult.fail("Template selection became current before target route/projection verification")
    return InvariantResult.pass_()


def template_ambiguity_never_builds(state: State, trace: object) -> InvariantResult:
    if state.selection_disposition == "ambiguous_template_selection" and (
        state.target_builder_ran or state.instance_receipt_current
    ):
        return InvariantResult.fail("Ambiguous selection reached a target builder or instance receipt")
    return InvariantResult.pass_()


def template_instance_requires_target_native_validation(state: State, trace: object) -> InvariantResult:
    if state.instance_receipt_current and not (
        state.target_builder_ran and state.target_validation_current and state.preview_current
    ):
        return InvariantResult.fail("Instance receipt became current without target builder/validation and preview")
    return InvariantResult.pass_()


def template_skillguard_never_owns_domain_semantics(state: State, trace: object) -> InvariantResult:
    if state.semantic_owner != "target_guard":
        return InvariantResult.fail("SkillGuard replaced the target Guard as semantic owner")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "template_route_precedes_selection",
        "A current target route and projection are prerequisites for selection.",
        template_route_precedes_selection,
    ),
    Invariant(
        "template_ambiguity_never_builds",
        "Unresolved multiple candidates cannot reach a builder or instance receipt.",
        template_ambiguity_never_builds,
    ),
    Invariant(
        "template_instance_requires_target_native_validation",
        "A current instance requires preview, target builder, and target-native validation.",
        template_instance_requires_target_native_validation,
    ),
    Invariant(
        "template_skillguard_never_owns_domain_semantics",
        "The target Guard remains semantic owner through the full lifecycle.",
        template_skillguard_never_owns_domain_semantics,
    ),
)

EXTERNAL_INPUTS = (
    TemplateRequest(candidate_count=0),
    TemplateRequest(candidate_count=1),
    TemplateRequest(candidate_count=2, composition_safe=True),
    TemplateRequest(candidate_count=2),
    TemplateRequest(route_current=False),
    TemplateRequest(projection_current=False),
    TemplateRequest(candidate_count=0, base_allowed=False),
    TemplateRequest(target_builder_current=False),
    TemplateRequest(target_validators_current=False),
    TemplateRequest(target_validation_passes=False),
    TemplateRequest(harvest_recorded=False),
)


def build_workflow() -> Workflow:
    return Workflow(
        (
            ResolveTargetProjection(),
            SelectTemplate(),
            BuildAndValidateTargetInstance(),
            RecordHarvestDisposition(),
        ),
        name=MODEL_ID,
    )


def terminal_predicate(current_input: object, state: State, trace: object) -> bool:
    return isinstance(current_input, (Blocked, LifecycleReady))


def review_template_lifecycle():
    return Explorer(
        workflow=build_workflow(),
        initial_states=(State(),),
        external_inputs=EXTERNAL_INPUTS,
        invariants=INVARIANTS,
        max_sequence_length=4,
        terminal_predicate=terminal_predicate,
        required_labels=(
            "route_not_current_blocked",
            "projection_stale_blocked",
            "target_projection_ready",
            "base_forbidden_blocked",
            "ambiguous_selection_blocked",
            "selection_and_preview_current",
            "target_builder_stale_blocked",
            "target_validators_stale_blocked",
            "target_validation_failed_blocked",
            "target_instance_current",
            "harvest_missing_blocked",
            "template_lifecycle_ready",
        ),
    ).explore()


def export_contract_extension() -> dict[str, object]:
    steps = (
        ("step:resolve-template-native-route", "router", ()),
        ("step:load-target-template-projection", "input", ("step:resolve-template-native-route",)),
        ("step:validate-template-applicability", "validator", ("step:load-target-template-projection",)),
        ("step:select-template-pack", "router", ("step:validate-template-applicability",)),
        ("step:issue-template-selection-receipt", "receipt", ("step:select-template-pack",)),
        ("step:materialize-template-preview", "preview", ("step:issue-template-selection-receipt",)),
        ("step:run-target-native-template-builder", "native", ("step:materialize-template-preview",)),
        ("step:run-target-native-template-validators", "native", ("step:run-target-native-template-builder",)),
        ("step:issue-template-instance-receipt", "receipt", ("step:run-target-native-template-validators",)),
        ("step:record-template-harvest-disposition", "receipt", ("step:issue-template-instance-receipt",)),
        ("step:stage-template-installation-projection", "preview", ("step:record-template-harvest-disposition",)),
        ("terminal:template-lifecycle-current", "terminal", ("step:record-template-harvest-disposition",)),
        ("terminal:template-lifecycle-blocked", "terminal", ()),
    )
    return {
        "functions": [
            {
                "function_id": "supervise_template_lifecycle",
                "business_intent": "supervise target-owned validated template selection and instance receipts",
                "owner_id": "template-lifecycle-supervisor-v1",
                "route_ids": ["route:template-lifecycle-supervision"],
            }
        ],
        "routes": [
            {
                "route_id": "route:template-lifecycle-supervision",
                "function_id": "supervise_template_lifecycle",
                "owner_id": "template-lifecycle-supervisor-v1",
                "start_step_id": "step:resolve-template-native-route",
                "step_ids": [item[0] for item in steps],
                "success_terminal_step_id": "terminal:template-lifecycle-current",
                "blocked_terminal_step_id": "terminal:template-lifecycle-blocked",
                "handoffs": [
                    {
                        "target_kind": "internal_route",
                        "target_id": "route:install-suite-transaction",
                        "condition": "target installation projection requested after current instance receipt",
                        "claim_scope": "installation projection only",
                    }
                ],
            }
        ],
        "steps": [
            {
                "step_id": step_id,
                "route_id": "route:template-lifecycle-supervision",
                "owner_id": "template-lifecycle-supervisor-v1",
                "action_kind": action_kind,
                "prerequisite_step_ids": list(prerequisites),
                "required": step_id != "step:stage-template-installation-projection",
                "terminal_kind": (
                    "success"
                    if step_id == "terminal:template-lifecycle-current"
                    else "blocked"
                    if step_id == "terminal:template-lifecycle-blocked"
                    else ""
                ),
            }
            for step_id, action_kind, prerequisites in steps
        ],
        "obligations": [
            (
                "obligation:template-target-route",
                "template_route_precedes_selection",
                [
                    "step:resolve-template-native-route",
                    "step:load-target-template-projection",
                    "step:validate-template-applicability",
                ],
            ),
            (
                "obligation:template-selection",
                "template_ambiguity_never_builds",
                [
                    "step:select-template-pack",
                    "step:issue-template-selection-receipt",
                    "step:materialize-template-preview",
                ],
            ),
            (
                "obligation:template-instance",
                "template_instance_requires_target_native_validation",
                [
                    "step:run-target-native-template-builder",
                    "step:run-target-native-template-validators",
                    "step:issue-template-instance-receipt",
                ],
            ),
            (
                "obligation:template-domain-ownership",
                "template_skillguard_never_owns_domain_semantics",
                [
                    "step:resolve-template-native-route",
                    "step:run-target-native-template-builder",
                    "step:run-target-native-template-validators",
                ],
            ),
            (
                "obligation:template-harvest",
                "template_instance_requires_target_native_validation",
                ["step:record-template-harvest-disposition"],
            ),
        ],
        "invariant_ids": [item.name for item in INVARIANTS],
    }


def main() -> int:
    report = review_template_lifecycle()
    print(report.format_text())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
