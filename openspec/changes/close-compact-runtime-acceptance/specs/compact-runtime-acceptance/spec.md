## Purpose

Define a finite, exact acceptance contract for the compact SkillGuard runtime
so declared checks, clean consumer behavior, real self-audit, and release
claims cannot be promoted from stale, static, or shared evidence.

## ADDED Requirements

### Requirement: Closeout uses one frozen current identity

The closeout process MUST bind every implementation, contract, test,
environment, owner-plan, and evidence result to one declared SkillGuard
revision and MUST preserve an explicit blocked or not-run state when that
identity cannot be verified. Historical receipts or a moved remote revision
MUST NOT be silently reused.

#### Scenario: Baseline and workspace are current

- **WHEN** closeout starts with the declared SkillGuard revision, source
  inventory, prepared interpreter, and isolated workspace
- **THEN** the process records those identities before any owner executes and
  permits only the declared C01-C12 steps to consume them

#### Scenario: Baseline identity is missing or changed

- **WHEN** a source, environment, or remote identity differs from the frozen
  starting record
- **THEN** the closeout blocks with the exact mismatch and does not reinterpret
  a historical result as current

### Requirement: Declared-check denominator and execution count are exact

SkillGuard MUST compile the complete current required-check inventory with one
owner and one terminal disposition per check. An execution count MUST increase
only when the target OS process is actually created, and cancellation, attach,
timeout, persistence, and cleanup failures MUST preserve the real started
state and prevent a false success.

#### Scenario: Empty or invalid denominator is supplied

- **WHEN** an accepted contract has an empty, duplicated, foreign, or
  rehashed-invalid required-check set
- **THEN** planning blocks before execution and the prior current state remains
  unchanged

#### Scenario: One concurrent winner executes

- **WHEN** two equivalent requests contend for one owner and only one creates
  the target process
- **THEN** the winner records one execution, the loser records zero executions
  and a typed busy/reuse outcome, and shared attempt files cannot inflate either
  count

### Requirement: Consumer projection is a minimal independent closure

The public consumer MUST import and execute from its explicit projected files
in a clean environment without author-only modules, FlowGuard, old `run_store`,
editable finders, or root-search fallback. Installation MUST use one
preflight/stage/full-recheck/swap/readback transaction and restore exact old
bytes on failure.

#### Scenario: Clean projected consumer runs

- **WHEN** a clean interpreter exposes only the staged SkillGuard scripts and
  selects a current public operation
- **THEN** import, contract read, and target operation succeed without loading
  author or other-Guard paths

#### Scenario: Projection closure or stage validation fails

- **WHEN** a projected import is missing, a stage file drifts, or a rename is
  detected during the transaction
- **THEN** the transaction rejects, restores the previous byte identity, and
  does not add old modules or invoke a fallback

### Requirement: Self-audit executes real target-owned checks

The admission, execution, and release self-audit groups MUST execute the
declared current checks with exact collected identities, setup/call/teardown
success, and the complete current protection denominator. File existence or a
static report MUST NOT count as self-audit evidence.

#### Scenario: Valid self-audit passes

- **WHEN** every declared self case is collected and executes successfully in
  its assigned group with current source and contract identities
- **THEN** the group emits current terminal evidence containing its exact case
  multiset and owner identity

#### Scenario: Target source is deliberately broken

- **WHEN** current route or checker source is syntactically invalid or a
  required case is missing, duplicated, skipped, or xfailed
- **THEN** the real self-runner fails after observing that condition and leaves
  the current state unchanged

### Requirement: Retired platform paths stay rejected

The compact runtime MUST have one direct current contract and MUST reject the
retired platform, compatibility reader, migration route, alias, and fallback.
The current target-owned check meaning remains outside SkillGuard's domain
authority.

#### Scenario: Retired payload is supplied

- **WHEN** a request or runtime payload contains a former platform field,
  author-only route, compatibility alias, or old receipt coordinate
- **THEN** SkillGuard returns a typed retired/unknown finding and does not read
  the payload through another path

#### Scenario: Ordinary target check is supervised

- **WHEN** a target declares an ordinary check without Guard-specific purpose
  semantics
- **THEN** SkillGuard reconciles its identity and evidence without inventing a
  target contract or interpreting its domain result

### Requirement: Protection and test identity remain complete

Every in-scope retained protection and migrated test node MUST have one exact
current owner, one disposition, and one observable replacement or retirement
reason. Collection and final validation MUST reject new ignore, skip, xfail,
hidden, duplicate, or compatibility escapes.

#### Scenario: Required inventory is mapped

- **WHEN** all retained, ported, and retired nodes are reconciled with current
  source and test distribution
- **THEN** collection exits without errors and each node has an auditable
  current disposition

#### Scenario: A node is unmapped or hidden

- **WHEN** a required node cannot be collected, has duplicate owners, or is
  suppressed by a new escape
- **THEN** the migration gate blocks and names that node rather than shrinking
  the denominator

### Requirement: Cross-Guard journeys and measurements are independent

The acceptance suite MUST exercise the required public journeys and verify
that SkillGuard can run without FlowGuard, with fixed measurement fixtures and
explicit source, environment, and privacy identities. A measurement collected
before the final freeze MUST NOT be promoted to final evidence.

#### Scenario: SkillGuard runs in isolation

- **WHEN** a clean target environment executes the public lifecycle and
  consumer operations
- **THEN** it imports and runs without FlowGuard or author-path leakage and
  records zero unauthorized shared receipts

#### Scenario: Measurement fixture is current

- **WHEN** performance and installation fixtures run under the final freeze
  identity
- **THEN** the receipt records exact counters, details hash, and platform
  boundary without claiming an unmeasured token percentage

### Requirement: Freeze and final validation preserve evidence order

SkillGuard MUST freeze source, test, contract, toolchain, environment,
owner-plan, self-audit, and measurement identities before final full pytest.
The final full-test owner runs once, and later verification consumes its
immutable result without rerunning an owner or modifying the current contract.

#### Scenario: Freeze follows current self-audit

- **WHEN** real self-audit and all required owner plans are current and agree
- **THEN** the delivery freeze records one immutable identity and unlocks the
  single final full-test owner

#### Scenario: Final validation is requested before freeze

- **WHEN** a required self group, owner plan, or target input is missing
- **THEN** final validation remains blocked before any owner process starts and
  cannot be overridden by a release label

### Requirement: Packaging and publication remain separate claims

The final delivery package MUST contain only source-safe evidence tied to the
freeze, explicit platform and not-run boundaries, and isolated installation
proof. A future patch release MUST require a separate explicit authorization
after all C00-C12 gates pass.

#### Scenario: Candidate package is complete

- **WHEN** full pytest, four measurements, clean installation, self-audit, and
  privacy/provenance checks all match the freeze
- **THEN** a clean candidate package may be prepared without changing the
  existing release

#### Scenario: Release authorization is absent

- **WHEN** any evidence gate is missing or publication authorization has not
  been granted
- **THEN** the existing tag and release remain unchanged and the candidate is
  reported as blocked or scoped
