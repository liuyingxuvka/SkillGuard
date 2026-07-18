## Why

SkillGuard currently projects author-maintenance contracts, receipts, routing, and project state into maintained skills and ordinary consumer projects. That turns a graduation system into a runtime dependency, permits cross-skill evidence sharing to blur responsibility boundaries, and has modified official OpenSpec skills that should remain independently upgradeable.

## What Changes

- **BREAKING** Separate SkillGuard author-maintenance state from every graduated consumer skill distribution.
- **BREAKING** Bind every declared check and receipt to one explicit maintenance unit and reject cross-unit receipt consumption.
- **BREAKING** Replace portable ordinary-project adoption with explicit author-repository adoption; ordinary business projects reject SkillGuard state with zero writes.
- **BREAKING** Reduce the global router to an author-side explicit maintained-target registry; unregistered and external skills are not blocked for ordinary use.
- **BREAKING** Remove cross-skill Portfolio reuse tickets, shared validation proof, and OpenSpec receipt projection.
- Add a consumer-distribution projection that excludes `.skillguard/**`, SkillGuard prompts, receipts, supervisor state, Portfolio state, and router state.
- Preserve target-owned native checks, execution-depth reconciliation, exact input and toolchain identity, immutable receipts, timeout cleanup, affected-only revalidation, and same-unit exact-check single-flight.
- Restore official OpenSpec skills as external unmanaged dependencies and restrict FlowGuard integration to read-only proposal/design/spec/task context.
- Move any target-domain runtime currently stored under `.skillguard/runtime` into target-owned namespaces before consumer control state is removed.
- Supersede conflicting live requirements from `compose-validation-evidence`, `build-executable-skill-contract-runtime`, `enforce-current-runtime-authority`, and target template/global-router supervision without rewriting historical change records.

## Capabilities

### New Capabilities

- `author-maintenance-boundary`: Explicit author repository, author evidence root, and zero-write ordinary-project boundary.
- `maintenance-unit-evidence-isolation`: Per-unit semantic ownership, execution identity, receipt isolation, overlap detection, and same-unit single-flight.
- `consumer-skill-distribution`: Clean graduated skill projection, staged installation, safe withdrawal of installer-owned control files, and clean-machine independence.
- `external-provider-exclusion`: External official skill exclusion and read-only specification-provider context.
- `independent-portfolio-aggregation`: Portfolio status as an aggregation of independently proven maintenance units, without cross-unit evidence reuse.

### Modified Capabilities

- `universal-execution-depth`: Execution depth remains mandatory for author maintenance, but its state and receipts are author-side evidence and never an ordinary consumer runtime prerequisite.
- `composable-validation-evidence`: Validation ownership, reuse, parent aggregation, and single-flight become maintenance-unit-local and lose external/OpenSpec receipt consumers.
- `portable-artifact-boundary`: Author-control portability and consumer-distribution portability become disjoint named projections.
- `current-runtime-authority`: The current contract trio governs author maintenance only; consumer currentness is target-owned and independent.
- `claimed-skill-run-runtime`: Claimed runs require explicit author context, unit identity, and author evidence roots before writes.
- `skill-evidence-receipts`: Every receipt and parent-child relation is unit/member/subject/semantic-check bound and rejects foreign-unit proof.
- `portfolio-skill-calibration-loop`: Portfolio aggregates independently proven units and audits overlap without reuse tickets or prior-target proof transfer.
- `template-first-skill-maintenance`: Template selection and receipts remain author records; generated consumer prompts and installations contain target-owned material only.
- `validated-template-pack-supervision`: Template supervision remains author-side and may not project SkillGuard receipts or runtime requirements into graduated skills.

## Impact

- SkillGuard contracts, schemas, compiler, execution identity, supervisor, run store, TestMesh, Portfolio, installation, project adoption, global router, templates, prompts, CLI, fixtures, and documentation.
- Existing FlowGuard validation-composition, declared-check, runtime-authority, Portfolio, template-lifecycle, and router models and their tests.
- FlowGuard's 17 skill prompts, distribution installer, suite validation, project adoption, shadow synchronization, and OpenSpec adapter/cache/session surfaces.
- Installed official OpenSpec skills and all currently maintained target skills, including staged relocation of target-domain runtime hidden beneath `.skillguard/runtime`.
- Local source repositories, installed Codex skill projections, installation manifests/receipts, and local Git branches used for release and synchronization.
