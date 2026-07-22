## MODIFIED Requirements

### Requirement: Exact declared-check execution identity
SkillGuard MUST accept a check result only when the exact target, contract, explicit producer execution owner, semantic check projection, route, covered target-declared obligations, request, inputs, immutable receipt, observation locator when declared, and evidence domain agree across the compiled contract, execution record, replay, consumer, and closure. SkillGuard MUST NOT infer a shared producer from command, argument, filename, check-name, or output similarity.

#### Scenario: Complete current identity passes
- **WHEN** one declared producer is executed by its sole owner against the frozen current inputs and emits a matching immutable terminal receipt whose explicit projections include the required semantic check
- **THEN** SkillGuard SHALL admit that result for that exact declared check projection

#### Scenario: One identity component differs
- **WHEN** target, contract, producer owner, route, semantic projection, obligation, request, input, receipt, locator, or domain differs
- **THEN** SkillGuard SHALL reject the result with the exact mismatch and SHALL NOT fall back to label or command similarity

#### Scenario: Similar commands lack an explicit shared producer
- **WHEN** several semantic checks happen to compile to equal command text or emit equal output but do not explicitly declare one shared execution owner
- **THEN** SkillGuard SHALL preserve distinct producers and receipts

### Requirement: Target retains domain authority
SkillGuard MUST NOT require, create, infer, or interpret a target-domain purpose contract, protected failure set, semantic-obligation universe, native finding, Guard-style counterexample, producer-sharing rule, or evidence projection. The target skill remains the only owner of test meaning and domain judgment; SkillGuard verifies only exact current declarations and their evidence.

#### Scenario: Ordinary non-Guard skill declares ordinary checks
- **WHEN** a maintained document, utility, or workflow skill declares current checks but no Guard model purpose or bad-case pair
- **THEN** SkillGuard SHALL supervise those declared checks without demanding Guard-specific fields or deeper declarations

#### Scenario: Guard declares purpose checks natively
- **WHEN** a Guard skill declares native purpose, oracle, good-case, bad-case, or shared-producer projections
- **THEN** SkillGuard SHALL execute and reconcile those exact target declarations without interpreting their domain result

### Requirement: Existing branch, installation, and receipt-consumer gates remain current
Declared branch closure, transactional installation, exact installed parity, affected-only freshness, one final full validation owner, and read-only TestMesh receipt consumption MUST remain intact. Several semantic checks MAY share one producer only through an explicit same-unit declaration whose producer behavior, inputs, target-input roles, toolchain, and environment agree exactly. Evidence domains and check dependencies remain projection-owned; external producer dependencies are the union of the declared projection dependencies after owner mapping.

#### Scenario: Full receipt is consumed
- **WHEN** the frozen final validation owner emits one current full parent receipt
- **THEN** OpenSpec and later consumers SHALL replay that receipt without rerunning the owner
- **AND** updating task checkboxes, progress logs, reports, or receipt pointers SHALL NOT invalidate that receipt

#### Scenario: Frozen TestMesh plan resolves missing owners
- **WHEN** `plan_only` emits one immutable current plan and its public owner runner consumes that exact plan
- **THEN** the runner SHALL validate the plan identity, owner partition, dependencies, and explicit producer projections, verify `will_reuse_owner_ids` without execution, resolve only `will_execute_owner_ids` through the existing single-flight owner authority, and allow `aggregation_only` to consume the same unchanged plan
- **AND** a repeated runner invocation SHALL reuse newly current exact receipts without replanning, broadening the owner set, or repeating an owner process

#### Scenario: Several semantic checks explicitly share one execution owner
- **WHEN** the current source contract explicitly assigns several declared semantic checks to one execution owner and their producer declarations agree exactly
- **THEN** the frozen owner row SHALL retain every exact `check_id`, semantic identity, and projection hash, execute that producer at most once, and carry the complete projection into aggregation
- **AND** a missing, extra, reordered, ambiguous, inferred, or mismatched owner-check projection SHALL block before execution

#### Scenario: Persistence fails after process launch
- **WHEN** an owner process starts but output or receipt persistence fails before a terminal receipt can be published
- **THEN** the owner result SHALL remain failed with `process_started=true`, SHALL increment `execution_count`, and SHALL NOT publish or reuse a success receipt

#### Scenario: Background run has no terminal artifact
- **WHEN** only PID, heartbeat, progress, or a running log exists
- **THEN** SkillGuard SHALL treat it as liveness only and SHALL NOT count it as pass evidence

#### Scenario: Final gate is requested before freeze
- **WHEN** a full/final/release request lacks current source, toolchain, impact-plan, dependency, selector-health, or required target-input identity
- **THEN** SkillGuard SHALL reject final admission before any owner process starts
- **AND** a caller-supplied label such as `explicit_release_gate` SHALL NOT override the missing evidence

#### Scenario: Dependency is order-only
- **WHEN** a check is ordered after another check but does not consume its immutable receipt
- **THEN** it SHALL NOT declare `depends_on_check_ids`
- **AND** the ordering MAY remain in the development-process model or final aggregation without propagating owner freshness
