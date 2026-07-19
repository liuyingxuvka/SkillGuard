# native-depth-evidence-identity Specification

## Purpose

Define SkillGuard's target-neutral, exact declared-check execution identity, owner-scoped freshness, and immutable receipt boundaries without taking ownership of target-domain meaning.

## Requirements

### Requirement: Exact declared-check execution identity
SkillGuard MUST accept a check result only when the exact target, contract, owner, route, check, run, covered target-declared obligations, request, inputs, immutable receipt, observation locator when declared, and evidence domain agree across the compiled contract, execution record, replay, consumer, and closure.

#### Scenario: Complete current identity passes
- **WHEN** one declared check is executed by its sole owner against the frozen current inputs and emits a matching immutable terminal receipt
- **THEN** SkillGuard SHALL admit that result for the declared check

#### Scenario: One identity component differs
- **WHEN** target, contract, owner, route, check, run, obligation, request, input, receipt, locator, or domain differs
- **THEN** SkillGuard SHALL reject the result with the exact mismatch and SHALL NOT fall back to label similarity

### Requirement: Complete declared-check inventory
SkillGuard MUST reconcile the complete target-declared required check inventory. Every required check MUST have exactly one execution owner and exactly one visible terminal disposition for the current inputs.

#### Scenario: Every declared check is current
- **WHEN** every required manifest member has one current immutable terminal-success receipt
- **THEN** the declared-check gate MAY pass

#### Scenario: A declared check is hidden
- **WHEN** a required check is missing, skipped, timed out, stale, still running, not run, or omitted from an aggregation
- **THEN** closure SHALL block and name that exact check and disposition

#### Scenario: Result is undeclared
- **WHEN** a result names a check outside the frozen manifest
- **THEN** SkillGuard SHALL reject it and SHALL NOT expand the denominator after execution

### Requirement: Owner-scoped target input identity
SkillGuard MUST bind each task-data target-input role only to the exact execution owner whose declared checks consume that role. An explicitly universal target input MAY bind every selected owner, but a role-scoped input MUST NOT change an unrelated owner execution key.

#### Scenario: One owner consumes one fixture role
- **WHEN** a request supplies a `native-depth-fixture` role and only the native-depth check declares that role
- **THEN** only the native-depth owner semantic key SHALL include that role fingerprint
- **AND** every unrelated current owner receipt SHALL remain reusable

#### Scenario: Shared owner role declarations disagree
- **WHEN** checks compiled into one execution owner declare different target-input role sets
- **THEN** compilation or planning SHALL block before execution instead of broadening the owner inputs

#### Scenario: Declared target role is missing
- **WHEN** an owner declares a target-input role that the frozen request does not supply
- **THEN** final admission SHALL block with the missing role and SHALL launch zero owner processes

#### Scenario: Public-export candidate inventory changes
- **WHEN** a tracked or unignored-untracked public candidate is added, removed, or changes bytes
- **THEN** the exact `repository.public_export_candidates` role fingerprint SHALL change and stale `owner:self:public-export-privacy`
- **AND** unrelated owners SHALL remain reusable unless their own declared components or semantic dependencies changed
- **AND** the privacy command SHALL scan the same normalized candidate inventory used to construct the role, with no alternate inventory or fallback path

### Requirement: Semantic owner identity excludes attempt identity
SkillGuard MUST keep `run_id`, `step_id`, run-root path, timestamps, parent profile, aggregation identity, and output locations outside the reusable owner semantic execution key.

#### Scenario: Equivalent request is claimed in a new run
- **WHEN** owner declaration, maintained components, owner-scoped target inputs, semantic dependencies, toolchain, environment, evidence domain, and impact policy are unchanged but `run_id` differs
- **THEN** SkillGuard SHALL reuse the exact current terminal-success owner receipt and SHALL launch zero owner processes

#### Scenario: Check receives run root for output
- **WHEN** a check receives `{{run_root}}` only as its target-owned output location
- **THEN** the run-root path and run ID SHALL remain attempt metadata
- **AND** any task data read by the check MUST already be present in declared request or target-input identity

### Requirement: Every owner selector resolves independently
Every explicit `path` or `subtree` owner input selector MUST match at least one current maintained-inventory row before the compiled contract is admitted.

#### Scenario: One selector matches and one selector is missing
- **WHEN** an owner declares several selectors and only a subset resolves
- **THEN** compilation SHALL block and name every unresolved selector
- **AND** the matching union SHALL NOT hide the missing authority

#### Scenario: Unknown path is introduced
- **WHEN** a maintained source path has no unambiguous component and owner/projection mapping
- **THEN** impact planning SHALL block and SHALL NOT fall back to run-all

### Requirement: Target retains domain authority
SkillGuard MUST NOT require, create, or interpret a target-domain purpose contract, protected failure set, semantic-obligation universe, native finding, or Guard-style counterexample. The target skill remains the only owner of test meaning and domain judgment.

#### Scenario: Ordinary non-Guard skill declares ordinary checks
- **WHEN** a maintained document, utility, or workflow skill declares current checks but no Guard model purpose or bad-case pair
- **THEN** SkillGuard SHALL supervise those declared checks without demanding Guard-specific fields

#### Scenario: Guard declares purpose checks natively
- **WHEN** a Guard skill declares native purpose, oracle, good-case, and bad-case checks
- **THEN** SkillGuard SHALL execute and reconcile them as target-declared checks without interpreting their domain result

### Requirement: No selectable purpose mode
SkillGuard SHALL have one fixed supervision behavior. It MUST NOT expose a `core`, `guard`, `strict`, `advisory`, opt-in, bypass, or similar selector that changes whether declared required checks must execute.

#### Scenario: Caller tries to bypass a required check
- **WHEN** a caller supplies a mode, flag, or profile label intended to ignore a required declared check
- **THEN** SkillGuard SHALL reject the request or keep the check visibly not run and block closure

### Requirement: Generic native observation locator
When a target declares content-addressed native observation identity, each contribution MUST bind a `native_observation_locator` inside the exact immutable native receipt. SkillGuard MUST validate identity and content equality without interpreting the observation's domain meaning.

#### Scenario: Current observation resolves
- **WHEN** the declared target-owned locator resolves inside the immutable receipt and its content fingerprint matches
- **THEN** SkillGuard MAY count it for the target-declared obligation

#### Scenario: Mechanical range is reused
- **WHEN** several obligations cite a renamed numeric range or the same receipt material without an explicit target-declared shared-evidence contract
- **THEN** SkillGuard SHALL block duplicate contribution

### Requirement: Typed evidence domains
Where the target declares evidence domains, SkillGuard MUST preserve exact domain equality and MUST NOT promote one domain into another.

#### Scenario: Domain matches
- **WHEN** the check result and consumer require the same declared domain
- **THEN** SkillGuard MAY consume the receipt

#### Scenario: Domain promotion is attempted
- **WHEN** a source-only, fixture, capability, or other bounded receipt is offered for a stronger declared domain
- **THEN** SkillGuard SHALL block with an evidence-domain mismatch

### Requirement: Retired Guard-specific fields fail closed
The sole current SkillGuard schema MUST reject `purpose_contract_policy`, `purpose_contract_identity`, protected-failure, semantic-obligation, and native-finding fields in runtime authority.

#### Scenario: Former purpose payload is supplied
- **WHEN** a current contract or runtime payload supplies any removed Guard-specific authority field
- **THEN** SkillGuard SHALL return a specific unknown-or-retired-field finding and SHALL NOT read it through an alias or fallback

### Requirement: Existing branch, installation, and receipt-consumer gates remain current
Declared branch closure, transactional installation, exact installed parity, affected-only freshness, one final full validation owner, and read-only TestMesh receipt consumption MUST remain intact.

#### Scenario: Full receipt is consumed
- **WHEN** the frozen final validation owner emits one current full parent receipt
- **THEN** OpenSpec and later consumers SHALL replay that receipt without rerunning the owner
- **AND** updating task checkboxes, progress logs, reports, or receipt pointers SHALL NOT invalidate that receipt

#### Scenario: Frozen TestMesh plan resolves missing owners
- **WHEN** `plan_only` emits one immutable current plan and its public owner runner consumes that exact plan
- **THEN** the runner SHALL validate the plan identity, owner partition, and dependencies, verify `will_reuse_owner_ids` without execution, resolve only `will_execute_owner_ids` through the existing single-flight owner authority, and allow `aggregation_only` to consume the same unchanged plan
- **AND** a repeated runner invocation SHALL reuse newly current exact receipts without replanning, broadening the owner set, or repeating an owner process

#### Scenario: Several semantic checks share one execution owner
- **WHEN** the current compiler assigns several declared semantic checks to one identical execution owner
- **THEN** the frozen owner row SHALL retain every exact `check_id`, semantic identity, and projection hash, execute that owner at most once, and carry the complete projection into aggregation
- **AND** a missing, extra, reordered, ambiguous, or mismatched owner-check projection SHALL block before execution

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
