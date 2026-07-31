## Context

SkillGuard's existing `depth_profile.native_check_ids`, one-owner execution, freshness, closure consumption, and consumer-distribution rules already provide the correct author-side boundary. The target Guard remains responsible for what its model depth means and for producing the native receipt.

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

1. Use target-declared `native_check_ids`; do not add a SkillGuard domain route.
2. Add the no-self-report/no-addressable-gap rule to maintainer guidance and fixture expectations.
3. Compile and stage from authoritative contract sources; never hand-edit generated consumer files.
4. Keep one maintenance unit and one execution owner per check; no cross-unit receipt reuse.

## Risks / Trade-offs

- [Target contracts are updated before target code] -> SkillGuard validation remains blocked until the target-native check exists and produces a current receipt.
- [Generated files drift] -> run compiler, manifest parity, and clean consumer audit after source changes.
- [A diagnostic is mistaken for closure] -> retain the existing rule that read-only assurance diagnostics cannot issue receipts.

## Migration Plan

Update target contract sources after the Guard implementations are current, compile/validate the unit, stage and activate local consumers transactionally, and run the final author-side closure. Do not push remote branches or releases.
