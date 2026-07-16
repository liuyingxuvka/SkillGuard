## Context

The Git source repository contains SkillGuard V1, while the installed tree is a strict superset with the V2 compiler, supervisor, receipts, self-hosting, portfolio, installer, and schemas. Current V2 depth checks validate target-rule mapping but do not prove that a current job exercised enough of the target's important behavior. PhysicsGuard demonstrates the failure: many target-specific obligations can reuse the same few generic checks and still receive `deep-pass`.

The change spans contract schema, compile time, runtime supervision, closure, portfolio governance, installation, and multiple target skills. The target skill must remain the only domain executor.

## Goals / Non-Goals

**Goals:**

- Distinguish mapped contract depth from actual execution depth.
- Apply to every skill category through optional dimensions rather than Guard-specific concepts.
- Preserve native routes and checks and prevent parallel SkillGuard implementations.
- Produce immutable, replayable, target-local execution-depth receipts.
- Calibrate profiles with representative work and shallow bad cases before enforcement.
- Re-establish Git source authority and prove whole-tree installed parity.
- Make SkillGuard maintenance intent portable in every adopted target repository.

**Non-Goals:**

- SkillGuard will not evaluate physics, logic, sources, traces, worlds, documents, spreadsheets, designs, or external actions itself.
- A depth pass will not claim factual truth, model correctness, aesthetic quality, or future AI behavior.
- The global router will not become a mandatory gate for ordinary skill execution.

## Decisions

### 1. Extend V2 instead of adding a separate depth engine

The V2 compiler owns target contracts, the supervisor owns current execution, receipts own immutable evidence, and closure owns claims. `DepthProfile` is compiled into the existing contract and `TargetExecutionReceipt` is consumed by existing closure. A separate `skillguard-execution-depth` skill may explain and maintain the feature, but it calls the same V2 runtime and is not a second executor.

Alternative rejected: a stand-alone semantic checker beside V2. It would duplicate run ownership and allow inconsistent closure.

### 2. Use optional universal dimensions

A profile declares only dimensions meaningful to the target: `input`, `scope`, `route`, `workflow`, `branch`, `semantic`, `validation`, `artifact`, `side_effect`, `recovery`, `closure`, and `reuse`. Each dimension contains target-authored obligations, evidence bindings, minimum coverage, and blockers. The core knows ids, counts, ratios, evidence classes, freshness, and closure consumption—not domain vocabulary.

### 3. Preserve the three integration modes

`native-integrated` binds a complete native route/check system. `hybrid-extension` keeps the native owner and adds only missing gates. `skillguard-runtime` may supply a route only when no target runtime exists. Compilation rejects a second domain route, and runtime receipts identify the native owner that executed each domain obligation.

### 4. Separate contract and execution decisions

Contract compilation can issue `CONTRACT_DEPTH_PASS`; a current run may issue `EXECUTION_DEPTH_PASS`. Other runtime states are `BOUNDED_PARTIAL`, `BOUNDARY_ONLY`, `SHALLOW_BLOCKED`, `NOT_RUN`, `DEPTH_CONTRACT_MISSING`, `PROVIDER_UNAVAILABLE`, `UNMANAGED`, and `STALE`. Closure profiles state which statuses they accept; broad completion accepts only current execution pass unless an explicit bounded profile says otherwise.

### 5. Make evidence contribution unique and target-local

Every obligation binds to a target-owned action/check/artifact and one or more execution observations. The evaluator deduplicates repeated evidence identity: the same five generic check receipts cannot independently satisfy forty-six semantic obligations. Coverage is computed from unique obligation-to-evidence bindings and required important branches.

### 6. Require two-key portfolio calibration

The target authors its profile and fixtures. SkillGuard grants `enforced` only when representative positive jobs and intentionally shallow bad jobs demonstrate useful discrimination. Lifecycle is `unmanaged -> contract_mapped -> advisory -> enforced -> blocked`; `blocked` is used when an enforced target cannot produce required depth evidence. A Guard-family slice and a non-Guard slice must pass before family-wide rollout.

### 7. Promote installed V2 to canonical source safely

The installed tree is imported as a one-time migration input because it is a strict superset of the tracked V1 tree. Runtime-local evidence and cache paths are excluded. After import, the Git repository becomes canonical; all later installation uses the existing whole-tree staged installer with rollback and parity checks. Partial copying is forbidden.

### 8. Add generated SkillGuard project adoption

SkillGuard adds `project-adopt`, `project-audit`, and `project-upgrade` lifecycle commands. Adoption writes a portable project manifest and replaces only one marker-bounded `AGENTS.md` block while preserving all unrelated project instructions. The block names `https://github.com/liuyingxuvka/SkillGuard`, the managed skill paths, integration modes, native-route-first policy, required maintenance workflow, local audit command, and claim boundary. Audit fails on missing, duplicated, incomplete, stale, or hand-diverged blocks. Upgrade refreshes generated fields without erasing user or peer content.

This project block applies to skill maintenance, validation, installation, and release. It does not force the global router before ordinary target-skill execution and does not transfer domain ownership to SkillGuard.

## Risks / Trade-offs

- [Profiles become checkbox lists] -> Require representative shallow failures, unique evidence contribution, and target-authored semantic receipts.
- [One universal schema becomes too abstract] -> Keep domain requirements in target-owned profiles and provide optional dimensions, not mandatory generic rows.
- [Enforcement blocks legitimate bounded work] -> Preserve `BOUNDED_PARTIAL`, `BOUNDARY_ONLY`, and provider-unavailable states with explicit claim boundaries.
- [Source migration copies local evidence] -> Use the V2 public-export policy and installation exclusions; run privacy and provenance checks before source acceptance.
- [Cross-repository drift] -> Fingerprint target profile, native route/check surface, SkillGuard runtime, and generated receipt; invalidate stale evidence after any change.
- [Managed prompt overwrites repository rules] -> Use exact begin/end markers, refuse incomplete or duplicated blocks, and preserve byte-for-byte surrounding content.

## Migration Plan

1. Import the installed V2 public source set into the Git tree and make V2 self-host checks runnable from source.
2. Add schemas and pure evaluator types with compatibility defaults for targets without profiles.
3. Extend compile, supervise, receipts, replay, and closure; add bad-case fixtures.
4. Calibrate one Guard target and one non-Guard target in advisory mode.
5. Graduate the five Guard targets, then representative non-Guard categories.
6. Adopt the target repositories with the managed SkillGuard project block and verify native-route bindings.
7. Refresh the global registry and managed prompt, stage whole-tree installation, validate, and retain automatic rollback.

Rollback restores the previous installed backup and leaves the source change available for repair. Target profiles may be downgraded from `enforced` to `advisory` only through an explicit registry change with reason; evidence is never silently reinterpreted.

## Open Questions

None blocking. Initial thresholds will be profile-authored and calibration-derived rather than hardcoded globally.
