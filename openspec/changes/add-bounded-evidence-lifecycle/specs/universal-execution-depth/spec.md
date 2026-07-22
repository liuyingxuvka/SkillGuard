## MODIFIED Requirements

### Requirement: Current target execution receipt
Every non-trivial supervised run MUST produce an immutable target-local receipt bound to the exact request, target, contract, declared semantic-check inventory, explicit producer owners, current inputs, executed/reused producers, visible non-pass dispositions, logical evidence identities, physical storage identities, runtime fingerprint, lifecycle root, and closure scope.

#### Scenario: Current declared execution
- **WHEN** all required target-declared check projections have current terminal-success producer receipts with verified complete sidecars and closure consumes the exact run receipt
- **THEN** the supervisor MAY issue a bounded pass for the declared scope

#### Scenario: Source changes after receipt
- **WHEN** a functional input, contract, producer declaration, check projection, toolchain, runtime, lifecycle root, or required installed projection changes
- **THEN** replay SHALL classify only affected receipts, projections, and consumers as stale

#### Scenario: One target-input role changes
- **WHEN** one producer-scoped target-input role changes and all unrelated producer inputs remain identical
- **THEN** replay SHALL stale only the explicit producer or producers that consume that role plus genuine semantic receipt dependants

#### Scenario: Attempt or storage-location identity changes
- **WHEN** only the claimed run ID, run-root path, step ID, timestamp, parent profile, aggregation identity, temporary path, or physical output location changes while the logical evidence and current storage reference remain valid
- **THEN** the exact current owner receipt SHALL remain reusable

### Requirement: Declared checks, not universal test categories
SkillGuard SHALL require completion of the target's declared checks and SHALL NOT decide that a target's declared capability is insufficient, deepen the target contract, infer producer sharing, or require every target to declare a purpose contract, counterexample, positive/shallow pair, semantic universe, or native finding.

#### Scenario: Target declares negative tests
- **WHEN** negative tests are required by the target manifest
- **THEN** SkillGuard SHALL execute and reconcile them like every other required check

#### Scenario: Target does not declare negative tests or additional depth
- **WHEN** an ordinary skill's current manifest contains no such test category or depth claim
- **THEN** SkillGuard SHALL NOT invent the category, modify the declaration, or classify the target as a different mode

### Requirement: Canonical source and installed parity
Installation MUST use the current transactional whole-tree installation projection with verification, backup, automatic rollback, exact installed parity, and bytecode-disabled smoke before an installed-runtime claim. Source-only tests, fixtures, models, workflows, reports, evidence stores, receipts, and author-maintenance fingerprints MUST NOT enter installed currentness identity unless the target explicitly declares them in `projection:installation`.

#### Scenario: Partial installed sync
- **WHEN** only selected installation-projection files are copied into the installed tree or a required projected file is missing
- **THEN** installation parity SHALL fail

#### Scenario: Source-only authority changes
- **WHEN** only a source-only test, model, workflow, report, receipt, or author-maintenance file changes
- **THEN** installed currentness SHALL remain unchanged while affected author checks become stale through their own component edges

#### Scenario: Installed smoke imports Python modules
- **WHEN** transactional installation runs its required smoke checks
- **THEN** Python bytecode generation SHALL be disabled and the staged/installed projection SHALL contain no `.pyc` or `__pycache__` residue

#### Scenario: Post-activation check fails
- **WHEN** staged activation succeeds but a required post-activation validation fails
- **THEN** the installer SHALL restore the previous active tree and retain failure evidence

