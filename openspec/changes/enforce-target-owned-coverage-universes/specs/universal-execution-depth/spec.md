## MODIFIED Requirements

### Requirement: Target-neutral depth profile
SkillGuard SHALL compile an optional target-owned depth profile using universal dimensions without embedding target names or domain rules in the core evaluator. Every required dimension SHALL declare at least one obligation id and at least one target-owned coverage-universe id; an empty denominator SHALL be invalid and SHALL NOT evaluate as complete.

#### Scenario: Non-Guard profile compiles
- **WHEN** a document or spreadsheet skill declares workflow, artifact, validation, and closure dimensions with non-empty obligations and target-owned coverage universes
- **THEN** the same compiler SHALL accept the profile without Guard-specific fields

#### Scenario: Empty denominator is declared
- **WHEN** a required dimension has no obligation ids
- **THEN** compilation SHALL block with an empty-denominator finding and execution SHALL NOT report 100% coverage

#### Scenario: Domain rule stays target-owned
- **WHEN** a target declares a semantic obligation such as a physical envelope or logic rebuttal
- **THEN** the compiled contract SHALL bind it to the target's native action or check rather than implement it in SkillGuard

### Requirement: Current target execution receipt
Every non-trivial enforced run MUST produce an immutable target-local execution receipt bound to the request, target version, depth profile, native route/check identities, observations, artifacts, coverage-universe results, provider/runtime audit, calibration bindings, separate repository/target root roles, and SkillGuard runtime fingerprint.

#### Scenario: Current deep execution
- **WHEN** all required important obligations have current unique evidence, every required coverage universe is adequate, provider/runtime enrollment is current, calibration bindings match, and closure consumes the receipt
- **THEN** the evaluator SHALL issue `EXECUTION_DEPTH_PASS`

#### Scenario: Supervisor derives repetitive observation mappings
- **WHEN** the supervisor packet has an empty observation list but current hard native receipts expose manifest-bound contribution ranges whose obligation ids match the compiled owner/check bindings
- **THEN** the supervisor MAY create explicit observation rows and SHALL persist a content-addressed derivation artifact/event binding source receipt, check, range, and current input fingerprints into the depth receipt

#### Scenario: Empty direct packet or forged mapping
- **WHEN** receipt issuance directly receives no observations, or a supplied/derived row names an undeclared obligation, wrong range, stale receipt, or unbound check
- **THEN** execution SHALL remain non-pass; empty SHALL be `NOT_RUN` and SHALL NOT mean pass

#### Scenario: Source changes after receipt
- **WHEN** target source, profile, universe definition, native checks, calibration input, or SkillGuard runtime changes after a receipt
- **THEN** replay SHALL classify that receipt as `STALE`

#### Scenario: Model repository and task data are separate
- **WHEN** calibration fixtures and models live under `repository_root` while concrete task inputs and artifacts live under a distinct `target_root`
- **THEN** issuance, closure, and replay SHALL preserve both roles and SHALL validate calibration only against `repository_root`

#### Scenario: Root roles are collapsed or swapped
- **WHEN** replay receives the task-data root as the skill/model repository root, omits either required role, or current portable root content no longer matches the receipt
- **THEN** broad closure SHALL block or become stale and SHALL NOT persist local absolute paths as portable evidence

### Requirement: Unique evidence contribution
SkillGuard SHALL prevent one generic receipt or payload range from being counted repeatedly as independent proof for unrelated target obligations. Uniqueness SHALL be derived from immutable native receipt identity, immutable evidence-payload hash, and normalized contribution range; caller-authored contribution labels SHALL NOT create uniqueness.

#### Scenario: Contribution labels rename one payload
- **WHEN** several obligations cite the same immutable receipt, payload hash, and contribution range under different contribution ids
- **THEN** execution-depth evaluation SHALL block with a non-unique evidence-contribution finding

#### Scenario: One receipt contains distinct ranges
- **WHEN** a profile explicitly permits shared evidence and one immutable receipt contains separately identified, non-overlapping contribution ranges with one concrete rationale
- **THEN** those ranges MAY contribute separately without treating their caller labels as authority

### Requirement: Calibration before enforcement
A target SHALL NOT enter enforced mode until representative positive tasks and intentionally shallow bad tasks prove that its profile distinguishes deep from shallow execution. Each calibration case MUST bind the fixture path and SHA-256, a complete referenced fixture/model/config input manifest, native check id, exact declared-command fingerprint, expected terminal status, and expected blocker code. The native calibration runner MUST emit a separate content-addressed observation artifact containing the actual observed status and blocker; command exit and fixture-authored outcome fields SHALL NOT satisfy calibration.

#### Scenario: Only positive jobs exist
- **WHEN** a target passes representative positive jobs but has no content-addressed shallow bad-case evidence
- **THEN** its lifecycle SHALL remain `advisory`

#### Scenario: Calibration check is retargeted
- **WHEN** a fixture or referenced model/config changes, a command or complete input fingerprint changes, or the shallow case blocks for a different code
- **THEN** the calibration key SHALL be non-current and enforced execution SHALL block

#### Scenario: Calibration process exits zero without observation
- **WHEN** a calibration command exits zero but writes no valid observed-result artifact, supplies only a plausible hash, or references missing/different native bytes
- **THEN** the check and enforced execution SHALL block

#### Scenario: Fixture reports its own expected outcome
- **WHEN** a calibration fixture contains expected or observed status/blocker fields
- **THEN** compilation or runtime validation SHALL reject the self-report rather than treating it as measured evidence

#### Scenario: Both bound keys pass
- **WHEN** positive jobs pass, shallow bad jobs produce the expected non-pass status and blocker, exact fixture/command/input bindings are current, and all capabilities are covered
- **THEN** portfolio graduation MAY set the target to `enforced`

## ADDED Requirements

### Requirement: Target-owned coverage-universe adequacy
Each enforced required dimension MUST bind at least one target-owned coverage universe. A universe SHALL identify its owner and canonical fingerprint, eligible population, selected and validated floors plus floor origin, requested claim scope, strata, critical uncovered items, and per-object depth where declared. Every dynamic universe SHALL reconcile the native discovered object set with the declared set plus explicit typed exclusions through a content-addressed attestation; exclusions SHALL carry a reason and SHALL NOT contribute to coverage or claim scope. Every declared object SHALL bind a content-addressed child universe. Per-object policy MAY declare native object classes with different floors or scope only native-critical objects, but every required object SHALL bind to exactly one declared class and noncritical results SHALL remain visible. Runtime adequacy SHALL preserve eligible, selected, evaluated, and validated counts and covered claim scope from a current target-owned native receipt.

#### Scenario: Sparse time-series validation
- **WHEN** a signal has one thousand eligible time points but the target validates only one point below its declared count, coverage, stratum, or per-object floor
- **THEN** SkillGuard SHALL block the universe as inadequate and SHALL report the uncovered scope

#### Scenario: Justified bounded sampling
- **WHEN** a target declares a non-exhaustive floor with a concrete floor origin, validates enough points across every required stratum and object, leaves no critical item uncovered, and covers the requested claim scope
- **THEN** the universe MAY pass without requiring project-level exhaustive validation

#### Scenario: Aggregate coverage hides one shallow object
- **WHEN** total selected/validated counts meet the universe floor but one required object or time-varying signal does not meet its own count, coverage, or stratum floor
- **THEN** the universe SHALL block and SHALL identify the shallow object

#### Scenario: Static and time-varying objects need different floors
- **WHEN** the native inventory binds each object to one declared class and every class-specific per-object policy is met
- **THEN** the universe MAY pass without inventing time points for static objects

#### Scenario: Object class is missing, unknown, or changes mid-run
- **WHEN** one required object has no declared native class, uses an unknown class, or appears under conflicting classes
- **THEN** per-object depth SHALL block rather than choose an arbitrary floor

#### Scenario: Critical-only per-object scope
- **WHEN** policy scope is `all_critical_objects`, all native-critical objects meet their floors, and noncritical objects remain visible as not required
- **THEN** per-object depth MAY pass; a shallow critical object SHALL still block regardless of high global coverage

#### Scenario: Claim scope is broader than coverage
- **WHEN** requested claim scope contains an item not present in covered claim scope
- **THEN** broad execution depth SHALL block or remain explicitly bounded and SHALL list the scope gap

#### Scenario: A discovered low-ranked object is omitted
- **WHEN** the native discovery set contains an object absent from both the declared set and the explicit exclusion rows, or an exclusion uses `low_importance` as its disposition
- **THEN** the universe SHALL block with an object-scope reconciliation or exclusion-disposition finding

#### Scenario: A justified object is explicitly excluded
- **WHEN** a noncritical discovered object has a non-empty reason and an allowed typed disposition and is absent from declared object results
- **THEN** it SHALL remain visible as excluded and SHALL contribute no selected, validated, or covered-claim evidence

#### Scenario: Child universe changes
- **WHEN** an object's child eligible population, eligible count, discovery input, or child-universe fingerprint differs from the current native evidence
- **THEN** the per-object gate SHALL block and any floor receipt bound to the old child universe SHALL be stale or mismatched

### Requirement: Native-bound dynamic floor
Every enforced dynamic universe MUST bind a target-native floor policy. The current native receipt SHALL identify the allowed algorithm and version, eligible input count and fingerprint, selected/evaluated/validated floors, coverage floor, required strata, precommit timestamp and fingerprint, and content-addressed receipt reference/hash. SkillGuard SHALL compute the effective count, ratio, and stratum requirements as the stricter combination of the compiled safety floor and the native floor; neither authority MAY lower the other.

#### Scenario: Native floor is stricter than compiled floor
- **WHEN** a target-native algorithm computes 32 required points from a 1000-point child universe while the compiled safety floor is one point and zero percent
- **THEN** 31 points SHALL block and 32 points MAY pass when all other native strata and semantic checks pass

#### Scenario: Compiled floor is stricter than native floor
- **WHEN** the compiled floor requires 40 points but the native receipt requires 32
- **THEN** the effective floor SHALL remain 40 and 32 points SHALL block

#### Scenario: Fixed generic ratio conflicts with target-native adequacy
- **WHEN** a dynamic profile uses a current native floor receipt and declares a zero compiled coverage baseline with a positive count floor
- **THEN** SkillGuard SHALL use the native ratio/count instead of inventing a universal fixed percentage

#### Scenario: Native floor is post-hoc or rebound
- **WHEN** the floor algorithm is not allowed, its eligible count or child fingerprint differs, its precommit fingerprint is invalid, or its receipt hash is not content-addressed
- **THEN** execution SHALL block rather than accept a result-dependent threshold

### Requirement: Provider runtime readiness and enrollment
Enforced execution MUST audit the active provider/runtime identity and current enrollment evidence. The profile SHALL name the provider, required runtime contract and capability ids, enrollment status, and readiness check ids; caller-authored availability booleans SHALL NOT satisfy the audit.

#### Scenario: Prompt new runtime old
- **WHEN** the current profile requires coverage-universe support but the active runtime lacks the required runtime contract or capability id
- **THEN** execution SHALL block before `EXECUTION_DEPTH_PASS` with a provider/runtime readiness finding

#### Scenario: Readiness check is missing
- **WHEN** the runtime identity is compatible but an enforced target lacks a current passing readiness or enrollment receipt
- **THEN** execution SHALL remain non-pass and SHALL name the missing check

#### Scenario: Compatible enrolled provider
- **WHEN** the active provider identity, runtime contract, capability ids, enrollment status, and readiness receipts all match the compiled profile
- **THEN** provider/runtime readiness MAY contribute to execution-depth pass while the target retains native domain authority
