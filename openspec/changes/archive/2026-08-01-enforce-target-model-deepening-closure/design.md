## Context

SkillGuard's existing `depth_profile.native_check_ids`, one-owner execution, freshness, closure consumption, and consumer-distribution rules provide most of the author-side boundary. They do not identify which generic check proves model deepening. Consequently a target can have many passing checks while the relevant model check is absent, stale, or merely represented by an abstract Boolean. The target Guard remains responsible for model meaning and native judgment; SkillGuard must make the selected receipt identity explicit and fail closed when it is not exact and current.

## Goals / Non-Goals

**Goals:**

- Ensure each maintained target declares a current native closure check for iterative deepening.
- Ensure affected known-bad mutations are rejected and target receipts remain opaque.
- Keep source, compiled contract, check manifest, installation projection, and local router identities distinct.

**Non-Goals:**

- No SkillGuard interpretation of Flow, physics, research, or world semantics.
- No central understanding or assurance graph authority.
- No copying author contracts/receipts into consumers.

## Decisions

1. Extend, rather than replace, `depth_profile`: an affected target declares exactly one `model_deepening_check_id`, and that id must already be present in its own `native_check_ids` and declared-check manifest.
2. Select the model-deepening result from the same immutable receipt reconciliation used by execution depth. Do not accept a second packet field, caller Boolean, prose statement, fallback id, or receipt from another execution owner.
3. Project a typed `model_deepening_result` into every current target execution receipt. For affected targets, closure is allowed only when the selected result is `passed`, current, request-bound, owner-bound, and has non-empty immutable receipt identity. Targets without a declared model-deepening lane are reported as `not_declared`; this does not silently prove model depth.
4. Replace the former abstract-only self check with a target-owned runtime test that exercises good and known-bad receipts. The FlowGuard model remains a design constraint, not execution evidence.
5. Compile and stage from authoritative contract sources; never hand-edit generated consumer files.
6. Keep one maintenance unit and one execution owner per check; no cross-unit receipt reuse.

## Risks / Trade-offs

- [Target profile names an undeclared or wrong check] -> compilation fails before execution.
- [Target check is absent, stale, failed, skipped, wrong-request, or wrong-owner] -> the typed result is blocked and execution-depth closure cannot pass.
- [Generated files drift] -> run compiler, manifest parity, and clean consumer audit after source changes.
- [A diagnostic is mistaken for closure] -> retain the existing rule that read-only assurance diagnostics cannot issue receipts.

## Migration Plan

Update the current SkillGuard schema/runtime first, then update affected target contract sources after their Guard implementations are current. Compile and validate each unit, stage and activate local consumers transactionally, run the frozen final author-side closure, and only then publish the separately versioned repositories.
