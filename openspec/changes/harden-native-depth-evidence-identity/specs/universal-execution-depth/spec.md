## MODIFIED Requirements

### Requirement: Current target execution receipt
Every non-trivial supervised run MUST produce an immutable target-local receipt bound to the exact request, target, contract, declared check inventory, owners, current inputs, executed checks, visible non-pass dispositions, artifacts, runtime fingerprint, and closure scope.

#### Scenario: Current declared execution
- **WHEN** all required target-declared checks have current terminal-success receipts and closure consumes the exact run receipt
- **THEN** the supervisor MAY issue a bounded pass for the declared scope

#### Scenario: Source changes after receipt
- **WHEN** a functional input, contract, check command, owner, toolchain, runtime, or required installed projection changes
- **THEN** replay SHALL classify only affected receipts and consumers as stale

### Requirement: Declared checks, not universal test categories
SkillGuard SHALL require completion of the target's declared checks and SHALL NOT require every target to declare a purpose contract, counterexample, positive/shallow pair, semantic universe, or native finding.

#### Scenario: Target declares negative tests
- **WHEN** negative tests are required by the target manifest
- **THEN** SkillGuard SHALL execute and reconcile them like every other required check

#### Scenario: Target does not declare negative tests
- **WHEN** an ordinary skill's current manifest contains no such test category
- **THEN** SkillGuard SHALL NOT invent the category or classify the target as a different mode

### Requirement: No hidden execution gaps
Missing, failed, skipped, timeout, running, not-run, stale, duplicate-owner, duplicate-execution, and cleanup-unconfirmed results MUST remain visible and MUST NOT satisfy closure.

#### Scenario: Aggregation hides a child
- **WHEN** a parent result omits a required declared child check
- **THEN** the parent SHALL fail with the missing check ID

#### Scenario: Post-launch evidence persistence fails
- **WHEN** the native process started but durable evidence persistence raises an error
- **THEN** SkillGuard SHALL report one started execution and a visible failed disposition rather than classifying the owner as not run or reporting zero execution

### Requirement: Closure consumes exact declared-check evidence
Every declared consumer closure MUST consume the exact current receipts required by the target contract. SkillGuard exposes only the fixed `enforced` closure and a consumer MUST NOT execute or carry the owner's command.

#### Scenario: Consumer has a current owner receipt
- **WHEN** the receipt identity and frozen inputs match
- **THEN** the consumer SHALL replay and project it without rerunning the owner

#### Scenario: Receipt is not terminal current success
- **WHEN** the receipt is missing, stale, failed, partial, foreign, tampered, or cleanup-unconfirmed
- **THEN** closure SHALL block and the consumer SHALL NOT silently rerun it

### Requirement: Native route preservation
SkillGuard MUST preserve the target's existing native routes and checks. It MUST NOT add a parallel target-domain executor.

#### Scenario: Target owns domain evaluation
- **WHEN** a target skill evaluates its domain claim through its own native check
- **THEN** SkillGuard SHALL consume only the declared terminal check receipt and SHALL NOT duplicate the evaluator

### Requirement: Canonical source and installed parity
Installation MUST use the current transactional whole-tree projection with verification, backup, automatic rollback, and exact installed parity before an installed-runtime claim.

#### Scenario: Partial installed sync
- **WHEN** only selected files are copied into the installed tree
- **THEN** installation parity SHALL fail
