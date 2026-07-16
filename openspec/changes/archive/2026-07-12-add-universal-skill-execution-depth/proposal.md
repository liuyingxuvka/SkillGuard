## Why

SkillGuard can currently prove that a target contract is mapped, yet still accept evidence produced by a shallow execution that touched only a few generic checks. We need a target-neutral execution-depth layer that proves the selected skill actually exercised the important routes, branches, artifacts, validation, recovery, and closure obligations appropriate to the task, while leaving every domain decision with the target skill.

## What Changes

- Add a universal `DepthProfile` contract with optional dimensions for input, scope, route, workflow, branch, semantic reasoning, validation, artifacts, side effects, recovery, closure, and reuse.
- Add a target-local `TargetExecutionReceipt` and deterministic evaluator that distinguish contract mapping from current execution depth.
- Preserve native routes as a hard invariant: `native-integrated` extends an existing complete route, `hybrid-extension` fills only missing gates, and `skillguard-runtime` may create a route only when none exists.
- Add honest terminal states including `EXECUTION_DEPTH_PASS`, `BOUNDED_PARTIAL`, `BOUNDARY_ONLY`, `SHALLOW_BLOCKED`, `NOT_RUN`, `PROVIDER_UNAVAILABLE`, and `STALE`.
- Add portfolio calibration with representative positive tasks and shallow bad cases before a target can enter enforced mode.
- Add SkillGuard project adoption: generate and audit a managed `AGENTS.md` block, a portable project record, and a stable GitHub handoff so future AIs and machines default to SkillGuard for skill maintenance.
- Restore the installed V2 implementation into the Git source repository as the canonical source, then require whole-tree source/install parity.
- Add one Guard-family and one non-Guard vertical slice before broader rollout, so the core cannot overfit to the Guard family.

## Capabilities

### New Capabilities
- `universal-execution-depth`: Universal target-neutral depth profiles, execution receipts, enforcement decisions, native-route preservation, calibration, and source/install lifecycle.

### Modified Capabilities

None.

## Impact

The change affects the SkillGuard V2 schemas, compiler, supervisor, receipts, closure, portfolio workflow, CLI, project-adoption generator/auditor, fixtures, self-hosting, installation, global router projection, public documentation, target repository `AGENTS.md` files, and the installed SkillGuard tree. Covered target skills gain target-owned profiles and receipt bindings; they do not gain a second domain executor.
