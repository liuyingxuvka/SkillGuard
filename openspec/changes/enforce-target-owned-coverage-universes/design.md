## Context

Universal Execution Depth already extends the V2 compiler, supervisor, immutable receipt chain, and closure gate. Its current dimension denominator is only a list of obligation ids; an empty list is treated as complete, contribution uniqueness trusts a caller label, calibration resolves only passing check ids, and provider availability is a packet boolean. Those choices cannot distinguish broad target-owned validation from a shallow sample or a prompt/runtime version split.

The existing FlowGuard preflight assigns `CompileContract`, `SuperviseRun`, and `CloseRun` to the SkillGuard runtime-contract lifecycle. This change therefore extends those owners and does not add another target-domain executor. Native target routes, models, simulations, searches, judgments, and checks remain authoritative.

## Goals / Non-Goals

**Goals:**

- Make every required depth dimension use a non-empty obligation denominator and one or more target-owned coverage universes.
- Express large datasets without enumerating every point by using counts, strata, per-object depth, critical uncovered ids, and requested/covered claim scope.
- Derive uniqueness from immutable native receipt identity, immutable evidence-payload hash, and a normalized contribution range.
- Make positive and shallow calibration cases content-addressed and exact-command/input bound.
- Require calibration to emit an independently hashed native observation artifact containing the actual observed result; process exit and fixture labels are never the measured result.
- Preserve skill/model `repository_root` and task-data `target_root` as separate replay authorities.
- Fail closed when the active runtime/provider lacks the profile's required depth capabilities or enrollment evidence.
- Migrate SkillGuard self-host to distinct real receipts and add known-shallow regressions.

**Non-Goals:**

- SkillGuard will not choose PhysicsGuard time windows, LogicGuard argument branches, Word/document sections, or any other domain-specific sampling floor.
- SkillGuard will not require full point-by-point project validation. The target owns justified floors and floor origin; SkillGuard verifies that the declared floor was actually met and scopes the claim to what was covered.
- The global SkillGuard router will not become a mandatory runtime gate for ordinary target-skill use.
- This change will not archive, release, publish, or install the repository.

## Decisions

### 1. Extend the existing v1 execution-depth records fail-closed

The current profile/receipt schemas remain the named v1 surfaces, but enforced profiles gain mandatory fields and stricter semantic validation. Advisory or unmanaged records may be migrated explicitly; an old shape cannot silently remain enforced. This keeps the current runtime route and avoids a parallel v1/v2 success path.

Alternative considered: introduce a second depth-profile runtime version. Rejected because both versions would need closure authority during migration and could recreate the parallel-success problem.

### 2. Split declared universe from observed adequacy

Each profile declares a `coverage_universe` owned by the target: owner id, canonical universe fingerprint, eligible count, selected/validated floors and floor origin, requested claim scope, required strata, per-object depth rows or class-aware per-object policies, and criticality. Each run supplies observed selected/validated counts and covered scope through a row bound to an allowed target-owned native step/check receipt. SkillGuard copies owner, eligible population, floor, and fingerprint from the compiled profile; it does not trust packet overrides. A target may declare different floors for static objects and long time-varying objects, but native inventory must bind each object to one unambiguous declared class. `all_critical_objects` applies the per-object hard gate only to native-critical objects while retaining noncritical results as visible, not-required evidence.

The evaluator enforces `0 <= validated <= selected <= eligible`, selected and validated count floors, validated/eligible coverage floor, required strata, per-object or per-class depth, zero critical uncovered items, and requested-versus-covered scope. Aggregate coverage cannot compensate for a required shallow object. A target may choose bounded floors rather than exhaustive validation, but the floor must have a non-empty `floor_origin` explaining where it came from.

Dynamic universes also carry an object-scope attestation. Its fingerprint covers the discovery algorithm/input, discovered ids, declared ids, and typed exclusion rows. The runtime requires `discovered = declared union excluded`, disjoint declared/excluded sets, exact declared/inventory parity, non-empty exclusion reasons, no critical exclusion, and no `low_importance` escape hatch. Excluded objects are diagnostic only and cannot appear in object results or covered scope.

Each declared object's complete eligible item population deterministically creates a child-universe id, count, and fingerprint. A target-native floor receipt binds that child identity (or the parent universe for a universe-scoped algorithm), the allowed algorithm/version, input `N`, computed count/ratio, required strata, precommit time/fingerprint, and a content-addressed receipt. The evaluator takes the maximum compiled/native selected, evaluated, validated, and ratio floors and the union of compiled/native strata. A dynamic profile may therefore set compiled ratio to zero while retaining a positive compiled count safety floor; SkillGuard does not impose a generic one-percent rule over a stronger target-native algorithm.

The supervisor may eliminate repetitive hand-authored obligation→range rows only after native execution. For an empty supervisor observation list, it derives explicit rows from the compiled obligation owner, exact check manifest, current hard/native receipt, and the obligation ids carried by the immutable native range. It persists source receipt/check/range hashes and current input fingerprints in a content-addressed derivation artifact and binds that artifact into the depth receipt. Direct issuance with an empty packet remains `NOT_RUN`; invalid or incomplete derivation never becomes a pass.

Alternative considered: enumerate every eligible item in SkillGuard. Rejected because time-series and document/model universes may contain thousands or millions of items and because item selection is domain-owned.

### 3. Bind evidence uniqueness to immutable facts

Every accepted observation carries the native receipt id/hash, a canonical hash of the immutable evidence payload, and a normalized contribution range. The uniqueness key is the tuple of those values. `contribution_id` remains descriptive only and cannot make duplicate proof unique. Shared evidence remains possible only where the dimension explicitly allows it, all uses carry one rationale, and their contribution ranges are genuinely distinct.

### 4. Compile calibration as content-addressed cases

Calibration changes from four loose id arrays to positive and shallow case rows. Each row binds a fixture path and SHA-256, the complete referenced fixture/model/config path→hash manifest, native check id, exact declared-command fingerprint, expected terminal status, and expected blocker code. Compiler checks bind the case to the current inputs and check declaration. Runtime resolution binds it again to a current immutable check record, resolved command fingerprint, separately written native observation artifact, exact artifact bytes/hash/reference, and the actual observed status/blocker. A shallow check is a passing meta-check whose observed target outcome is non-pass with the declared blocker; a zero-exit no-op, self-reported fixture outcome, random hash, or absent native artifact blocks.

### 5. Preserve repository and target root roles

`repository_root` owns the maintained skill, model, calibration fixtures, and referenced configuration. `target_root` owns the concrete task inputs and produced artifacts. Issuance, closure, and replay receive both explicitly. The target execution receipt stores a portable content-addressed role binding—calibration input identities, target-input fingerprint hash, and whether the roots were distinct—without storing local absolute paths. Missing, swapped, collapsed, or content-drifted roles block or become stale. A self-host run may intentionally bind one directory to both roles, but must still name both roles.

### 6. Audit provider/runtime readiness from runtime identity, not prompt claims

The runtime fingerprint exposes a runtime contract id and capability ids. An enforced profile declares the provider id, required runtime contract id/capabilities, enrollment status, and readiness check ids. The supervisor supplies the actual active runtime identity and current native readiness receipts. Caller packet booleans cannot create readiness. A prompt/profile requiring new capabilities with an older runtime therefore blocks before `EXECUTION_DEPTH_PASS`.

### 7. Keep closure monotonic and receipts explanatory

The target execution receipt gains coverage-universe results, provider/runtime audit, detailed calibration bindings, and root-role bindings. Closure continues to consume only a current `EXECUTION_DEPTH_PASS`; empty denominators, inadequate universes, duplicate immutable contributions, calibration mismatch, root-role mismatch, or runtime mismatch remain explicit blockers.

## Risks / Trade-offs

- [Existing enforced profiles become invalid until migrated] → Keep errors specific, update SkillGuard self-host in the same change, and provide fixtures for each new blocker.
- [A target may declare a weak but internally consistent floor] → Require floor origin and requested/covered scope; SkillGuard proves adherence, while target maintainers remain responsible for domain adequacy.
- [Counts can still be false if a native checker lies] → Accept counts only through a bound current native check receipt and state this claim boundary; SkillGuard cannot replace target-domain truth validation.
- [A calibration wrapper can look green without measuring anything] → Require an actual native observation artifact with exact bytes/hash/reference and reject fixture-authored outcomes.
- [Task data and model sources may live in different repositories] → Carry both root roles through issue/close/replay and bind their portable content identities.
- [Portable command fingerprints can differ from resolved absolute commands] → Bind both the portable declared command fingerprint and the runtime check record's resolved command fingerprint.
- [Self-host changes can invalidate earlier evidence] → Treat all earlier depth and closure receipts as stale and regenerate focused/current evidence after code, schema, fixture, and model updates.

## Migration Plan

1. Tighten schemas and semantic validation; old enforced profiles fail with migration blockers.
2. Update compiler bindings and runtime identity capability declarations.
3. Extend evaluator, supervisor issuance, receipt schema, and closure replay, including class-aware per-object floors, native observation artifacts, and separate root-role binding.
4. Migrate SkillGuard's own profile, calibration fixtures/check declarations, and distinct evidence observations.
5. Update FlowGuard model obligations and known-bad cases, then run focused tests, model checks, compiler parity, SkillGuard project audit, and OpenSpec verification.

Rollback is source-level only: revert this change before any release. Do not accept old receipts under the new profile fingerprint.

## Open Questions

None for this change. Target-specific numeric floors remain intentionally owned by each maintained skill and are not standardized here.
