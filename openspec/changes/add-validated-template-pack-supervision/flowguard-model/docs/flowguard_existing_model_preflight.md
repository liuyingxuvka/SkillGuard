# FlowGuard Existing Model Preflight Notes

Use this scaffold before discussing, proposing, or implementing a non-trivial
change in an existing modeled system.

## What Existing Model Preflight Reviews

- which existing FlowGuard models were searched;
- which affected UI, API, CLI, alias, adapter, wrapper, helper, and
  compatibility surfaces belong to the same exact external purpose, and
  whether the observed inventory matches the expected surface ids;
- which model responsibilities, FunctionBlocks, state fields, side effects,
  public entrypoints, and behavior-bearing fields already own the requested
  behavior;
- whether the change should reuse an existing boundary, extend an existing
  model, add a child model, or create a new boundary;
- whether duplicate model, state, side-effect, entrypoint, or responsibility
  ownership is resolved before downstream work starts;
- which downstream FlowGuard route should handle the concrete work.

For behavior-bearing work, hand downstream routes the same stable
`business_intent_id`, `behavior_commitment_id`, and singular
`primary_path_id`. Keep scoped dispositions for genuinely excluded surfaces;
do not silently omit them or create a new owner route just to avoid the
existing commitment/path boundary.

For field-bearing work, include `behavior_field_ids`, `field_owners`, and
`field_lifecycle_model_ids`, and name `field_lifecycle_mesh` as a downstream
route. If a field is discovered but not owned yet, stop at preflight and create
or extend FieldLifecycleMesh before changing production behavior.

Use a light grounding note for discussion and early analysis. Use a full
structured preflight before implementation, OpenSpec proposals, major
architecture changes, or risky behavior changes.

Use `existing_model_preflight_from_project(...)` when an agent needs a quick
project inventory from `.flowguard`, docs, and OpenSpec before filling or
reviewing the same `ExistingModelPreflight` shape. The inventory helper is not
the validator; pass its output to `review_existing_model_preflight(...)`.
