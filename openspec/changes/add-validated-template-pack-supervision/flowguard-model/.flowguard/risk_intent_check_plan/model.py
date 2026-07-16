"""Model-first Template Pack selection contract.

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard

Purpose:
Model the finite zero/one/many selection boundary shared by Guard-family
Template Pack builders before production selector code is edited.

Guards against:
- an empty candidate set silently producing an unvalidated blank artifact;
- two equally plausible or non-composable packs being guessed together;
- two selected fragments owning the same output field;
- input ordering changing the selected pack order or instance fingerprint;
- a blocked decision being misreported as generated output.

Run:
python .flowguard/risk_intent_check_plan/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
from typing import Iterable

from flowguard import (
    FlowGuardCheckPlan,
    FunctionResult,
    Invariant,
    InvariantResult,
    KnownBadProof,
    MinimumModelContract,
    RiskIntent,
    RiskProfile,
    TemplateHarvestReview,
    TemplateReuseReview,
    Workflow,
    run_model_first_checks,
)


@dataclass(frozen=True)
class TemplatePack:
    pack_id: str
    priority: int
    composable: bool
    owned_fields: tuple[str, ...]


PACKS: dict[str, TemplatePack] = {
    "compiler-profile": TemplatePack(
        "compiler-profile", 80, True, ("compiler_profile", "fragment_bindings")
    ),
    "family-flow": TemplatePack(
        "family-flow", 100, True, ("family_id", "model_route")
    ),
    "portable-launch": TemplatePack(
        "portable-launch", 60, True, ("launcher", "platform_policy")
    ),
    "conflict-alpha": TemplatePack("conflict-alpha", 50, True, ("launcher",)),
    "conflict-beta": TemplatePack("conflict-beta", 40, True, ("launcher",)),
    "exclusive-review": TemplatePack(
        "exclusive-review", 120, False, ("review_mode",)
    ),
}
BASE_PACK_ID = "validated-base"


@dataclass(frozen=True)
class SelectionRequest:
    request_id: str
    candidate_ids: tuple[str, ...]
    validated_base_available: bool = True


@dataclass(frozen=True)
class SelectionCompleted:
    request_id: str
    decision: str
    selected_ids: tuple[str, ...]
    instance_fingerprint: str


@dataclass(frozen=True)
class SelectionBlocked:
    request_id: str
    reason: str


@dataclass(frozen=True)
class State:
    request_id: str = ""
    offered_ids: tuple[str, ...] = ()
    validated_base_available: bool = False
    decision: str = "pending"
    selected_ids: tuple[str, ...] = ()
    field_owners: tuple[tuple[str, str], ...] = ()
    instance_fingerprint: str = ""
    blocked_reason: str = ""


def canonical_ids(candidate_ids: Iterable[str]) -> tuple[str, ...]:
    return tuple(
        pack_id
        for pack_id in sorted(
            dict.fromkeys(candidate_ids),
            key=lambda item: (-PACKS[item].priority, item),
        )
    )


def field_owners(selected_ids: Iterable[str]) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            (
                (field_id, pack_id)
                for pack_id in selected_ids
                for field_id in PACKS[pack_id].owned_fields
            ),
            key=lambda item: (item[0], item[1]),
        )
    )


def fingerprint(selected_ids: tuple[str, ...], owners: tuple[tuple[str, str], ...]) -> str:
    payload = "template-pack-instance-v1|" + ",".join(selected_ids) + "|" + ",".join(
        f"{field_id}={owner_id}" for field_id, owner_id in owners
    )
    return "sha256:" + sha256(payload.encode("utf-8")).hexdigest()


class SelectTemplatePacks:
    name = "SelectTemplatePacks"
    reads = ("offered_ids", "validated_base_available")
    writes = (
        "decision",
        "selected_ids",
        "field_owners",
        "instance_fingerprint",
        "blocked_reason",
    )
    accepted_input_type = SelectionRequest
    input_description = "resolved Template Pack candidate set"
    output_description = "SelectionCompleted or SelectionBlocked"
    idempotency = "The same candidate set always yields the same canonical selection and fingerprint."

    def apply(self, input_obj: SelectionRequest, state: State) -> Iterable[FunctionResult]:
        offered = tuple(input_obj.candidate_ids)
        base_state = replace(
            state,
            request_id=input_obj.request_id,
            offered_ids=offered,
            validated_base_available=input_obj.validated_base_available,
            selected_ids=(),
            field_owners=(),
            instance_fingerprint="",
            blocked_reason="",
        )

        unknown = tuple(sorted({item for item in offered if item not in PACKS}))
        if unknown:
            yield self._blocked(base_state, "blocked_unknown", "unknown:" + ",".join(unknown))
            return

        unique = tuple(dict.fromkeys(offered))
        if not unique:
            if not input_obj.validated_base_available:
                yield self._blocked(base_state, "blocked_no_match", "no_validated_base")
                return
            selected = (BASE_PACK_ID,)
            receipt = fingerprint(selected, ())
            next_state = replace(
                base_state,
                decision="selected_base",
                selected_ids=selected,
                instance_fingerprint=receipt,
            )
            yield FunctionResult(
                SelectionCompleted(
                    input_obj.request_id,
                    next_state.decision,
                    selected,
                    receipt,
                ),
                next_state,
                label="selected_base",
            )
            return

        ordered = canonical_ids(unique)
        if len(ordered) == 1:
            owners = field_owners(ordered)
            receipt = fingerprint(ordered, owners)
            next_state = replace(
                base_state,
                decision="selected_single",
                selected_ids=ordered,
                field_owners=owners,
                instance_fingerprint=receipt,
            )
            yield FunctionResult(
                SelectionCompleted(
                    input_obj.request_id,
                    next_state.decision,
                    ordered,
                    receipt,
                ),
                next_state,
                label="selected_single",
            )
            return

        if not all(PACKS[item].composable for item in ordered):
            yield self._blocked(base_state, "blocked_ambiguous", "non_composable_candidates")
            return

        owners = field_owners(ordered)
        fields = tuple(field_id for field_id, _ in owners)
        if len(fields) != len(set(fields)):
            yield self._blocked(base_state, "blocked_conflict", "field_owner_conflict")
            return

        receipt = fingerprint(ordered, owners)
        next_state = replace(
            base_state,
            decision="selected_composed",
            selected_ids=ordered,
            field_owners=owners,
            instance_fingerprint=receipt,
        )
        yield FunctionResult(
            SelectionCompleted(
                input_obj.request_id,
                next_state.decision,
                ordered,
                receipt,
            ),
            next_state,
            label="selected_composed",
        )

    @staticmethod
    def _blocked(state: State, decision: str, reason: str) -> FunctionResult:
        blocked_state = replace(state, decision=decision, blocked_reason=reason)
        return FunctionResult(
            SelectionBlocked(state.request_id, reason),
            blocked_state,
            label=decision,
        )


class BrokenSelectTemplatePacks(SelectTemplatePacks):
    """Known-bad variant that composes conflicting packs instead of blocking."""

    name = "BrokenSelectTemplatePacks"

    def apply(self, input_obj: SelectionRequest, state: State) -> Iterable[FunctionResult]:
        unique = tuple(dict.fromkeys(input_obj.candidate_ids))
        if len(unique) > 1 and all(item in PACKS for item in unique):
            ordered = canonical_ids(unique)
            owners = field_owners(ordered)
            receipt = fingerprint(ordered, owners)
            next_state = replace(
                state,
                request_id=input_obj.request_id,
                offered_ids=input_obj.candidate_ids,
                validated_base_available=input_obj.validated_base_available,
                decision="selected_composed",
                selected_ids=ordered,
                field_owners=owners,
                instance_fingerprint=receipt,
                blocked_reason="",
            )
            yield FunctionResult(
                SelectionCompleted(
                    input_obj.request_id,
                    next_state.decision,
                    ordered,
                    receipt,
                ),
                next_state,
                label="broken_conflicting_composition",
            )
            return
        yield from super().apply(input_obj, state)


def selection_is_unambiguous(state: State, _trace) -> InvariantResult:
    if state.decision in {"pending", "blocked_no_match", "blocked_unknown", "blocked_conflict", "blocked_ambiguous"}:
        return InvariantResult.pass_()
    if state.decision == "selected_base":
        if state.offered_ids or not state.validated_base_available:
            return InvariantResult.fail("base selected outside a validated zero-match boundary")
        return InvariantResult.pass_()
    if state.decision == "selected_single":
        if len(set(state.offered_ids)) != 1:
            return InvariantResult.fail("single selection does not have exactly one unique candidate")
        return InvariantResult.pass_()
    if state.decision == "selected_composed":
        if len(set(state.offered_ids)) < 2:
            return InvariantResult.fail("composition does not have multiple candidates")
        if any(item not in PACKS or not PACKS[item].composable for item in set(state.offered_ids)):
            return InvariantResult.fail("non-composable or unknown candidate was composed")
        fields = tuple(field_id for field_id, _ in state.field_owners)
        if len(fields) != len(set(fields)):
            return InvariantResult.fail("composed packs claim the same output field")
        return InvariantResult.pass_()
    return InvariantResult.fail(f"unknown terminal decision {state.decision}")


def field_has_exactly_one_selected_owner(state: State, _trace) -> InvariantResult:
    fields = tuple(field_id for field_id, _ in state.field_owners)
    if len(fields) != len(set(fields)):
        return InvariantResult.fail("one output field has more than one owner")
    for _, owner_id in state.field_owners:
        if owner_id not in state.selected_ids:
            return InvariantResult.fail("field owner is not part of the selected pack set")
    return InvariantResult.pass_()


def successful_receipt_is_canonical(state: State, _trace) -> InvariantResult:
    if not state.decision.startswith("selected_"):
        if state.instance_fingerprint:
            return InvariantResult.fail("blocked decision emitted an instance fingerprint")
        return InvariantResult.pass_()
    if not state.instance_fingerprint.startswith("sha256:"):
        return InvariantResult.fail("successful selection lacks a deterministic fingerprint")
    if state.decision == "selected_base":
        expected = (BASE_PACK_ID,)
    else:
        if any(item not in PACKS for item in state.offered_ids):
            return InvariantResult.fail("successful selection contains an unknown candidate")
        expected = canonical_ids(state.offered_ids)
    if state.selected_ids != expected:
        return InvariantResult.fail("selected pack order is not canonical")
    if state.instance_fingerprint != fingerprint(state.selected_ids, state.field_owners):
        return InvariantResult.fail("instance fingerprint does not bind the selected packs and field owners")
    return InvariantResult.pass_()


def selected_set_is_bounded(state: State, _trace) -> InvariantResult:
    if state.decision == "selected_base":
        return InvariantResult.pass_()
    offered = set(state.offered_ids)
    if any(item not in offered for item in state.selected_ids):
        return InvariantResult.fail("selector introduced a pack that was not a candidate")
    return InvariantResult.pass_()


def risk_profile() -> RiskProfile:
    return RiskProfile(
        modeled_boundary="validated Template Pack zero/one/many selection",
        risk_classes=("idempotency", "module_boundary", "conformance"),
        risk_intent=RiskIntent(
            failure_modes=(
                "zero matches silently generate an unvalidated blank artifact",
                "multiple non-composable candidates are guessed",
                "two fragments claim the same output field",
                "candidate order changes the generated instance identity",
            ),
            protected_error_classes=(
                "unvalidated_fallback",
                "ambiguous_template_selection",
                "duplicate_field_ownership",
                "unstable_instance_identity",
            ),
            protected_harms=(
                "a maintained skill receives a plausible-looking but invalid contract",
                "validation receipts attach to a different generated instance",
            ),
            must_model_state=(
                "offered_ids",
                "decision",
                "selected_ids",
                "field_owners",
                "instance_fingerprint",
            ),
            must_model_side_effects=("selection_receipt_record",),
            completion_evidence=("selection_instance_fingerprint",),
            adversarial_inputs=(
                "zero candidates with and without a validated base",
                "one candidate",
                "multiple composable candidates in reverse priority order",
                "multiple candidates with a field-owner conflict",
                "multiple candidates including a non-composable pack",
                "unknown candidate id",
            ),
            hard_invariants=(
                "ambiguous sets never succeed",
                "every output field has exactly one selected owner",
                "selection and fingerprint are canonical",
                "blocked decisions emit no success fingerprint",
            ),
            known_bad_cases=("conflicting_packs_are_composed",),
            used_template_ids=(
                "completion_requires_evidence",
                "artifact_payload_real_surface",
            ),
            blindspots=(
                "production manifest parsing and filesystem emission require conformance tests",
            ),
        ),
        confidence_goal="model_level",
    )


def external_inputs() -> tuple[SelectionRequest, ...]:
    return (
        SelectionRequest("zero-with-base", ()),
        SelectionRequest("zero-without-base", (), validated_base_available=False),
        SelectionRequest("one", ("family-flow",)),
        SelectionRequest(
            "many-composable-reversed",
            ("portable-launch", "compiler-profile", "family-flow"),
        ),
        SelectionRequest("many-conflicting", ("conflict-beta", "conflict-alpha")),
        SelectionRequest("many-non-composable", ("family-flow", "exclusive-review")),
        SelectionRequest("unknown", ("missing-pack",)),
    )


def build_workflow(*, broken: bool = False) -> Workflow:
    block = BrokenSelectTemplatePacks() if broken else SelectTemplatePacks()
    return Workflow((block,), name="validated_template_pack_selection")


def build_check_plan(*, broken: bool = False) -> FlowGuardCheckPlan:
    return FlowGuardCheckPlan(
        workflow=build_workflow(broken=broken),
        initial_states=(State(),),
        external_inputs=external_inputs(),
        invariants=(
            Invariant(
                "selection_is_unambiguous",
                "zero/one/many success is licensed only by its declared boundary",
                selection_is_unambiguous,
                metadata={"property_classes": ("ambiguity", "composition_conflict")},
            ),
            Invariant(
                "field_has_exactly_one_selected_owner",
                "each generated field has exactly one selected Template Pack owner",
                field_has_exactly_one_selected_owner,
                metadata={"property_classes": ("field_ownership",)},
            ),
            Invariant(
                "successful_receipt_is_canonical",
                "successful output has a canonical selection and instance fingerprint",
                successful_receipt_is_canonical,
                metadata={"property_classes": ("determinism", "completion_evidence")},
            ),
            Invariant(
                "selected_set_is_bounded",
                "the selector cannot introduce an undeclared candidate",
                selected_set_is_bounded,
                metadata={"property_classes": ("selection_boundary",)},
            ),
        ),
        max_sequence_length=1,
        risk_profile=risk_profile(),
        template_reuse_review=TemplateReuseReview(
            used_template_ids=(
                "completion_requires_evidence",
                "artifact_payload_real_surface",
            ),
            searched_layers=("public", "local"),
            match_template_ids=(
                "completion_requires_evidence",
                "artifact_payload_real_surface",
            ),
        ),
        template_harvest_review=TemplateHarvestReview(
            disposition="not_harvestable",
            not_harvestable_reason="not_reusable_project_specific",
        ),
        minimum_model_contract=MinimumModelContract(
            protected_error_classes=(
                "unvalidated_fallback",
                "ambiguous_template_selection",
                "duplicate_field_ownership",
                "unstable_instance_identity",
            ),
            modeled_state=(
                "offered_ids",
                "decision",
                "selected_ids",
                "field_owners",
                "instance_fingerprint",
            ),
            modeled_side_effects=("selection_receipt_record",),
            completion_evidence=("selection_instance_fingerprint",),
            known_bad_cases=("conflicting_packs_are_composed",),
        ),
        known_bad_proofs=(
            KnownBadProof(
                "conflicting_packs_are_composed",
                protected_error_class="duplicate_field_ownership",
                method="broken_workflow_variant",
                observed_status="failed",
                observed_failure=(
                    "BrokenSelectTemplatePacks composes conflict-alpha and conflict-beta; "
                    "selection_is_unambiguous and field ownership invariants reject it"
                ),
                evidence_id="template-pack-selection:known-bad",
            ),
        ),
    )


def run_checks():
    return (
        run_model_first_checks(build_check_plan()),
        run_model_first_checks(build_check_plan(broken=True)),
    )
