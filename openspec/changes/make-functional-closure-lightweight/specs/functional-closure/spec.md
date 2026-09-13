## Purpose

Provide a finite, affected-only functional closure that preserves real
model/code/test coverage while making terminal reuse and ordinary AI work
fast, deterministic, and independent from release bookkeeping.

## ADDED Requirements

### Requirement: Functional freshness excludes operational metadata

The functional currentness identity SHALL include only behavior-bearing source,
model, contract, test, oracle, and declared functional dependency components.
Timeouts, output paths, receipts, reports, pointers, generation numbers,
attempt timing, and platform metadata SHALL NOT invalidate a functional leaf.

#### Scenario: Timeout policy changes
- **WHEN** only a timeout or retry-policy value changes
- **THEN** the functional leaf remains current
- **AND** execution metadata records the new policy for the next run

#### Scenario: Model contract changes
- **WHEN** a selected model, contract, oracle, or behavior-bearing test changes
- **THEN** the exact consuming leaf and typed dependants become stale
- **AND** unrelated leaves remain eligible for exact reuse

### Requirement: Exact current leaves are reused without a producer

An exact-current terminal producer receipt SHALL be reusable only when its
native owner, request, covered ids, source inputs, dependencies, toolchain,
environment, and proof artifacts match the current declaration. A reuse hit
SHALL perform no producer, lease, receipt, head, or run-directory write.

#### Scenario: Fast read after a successful run
- **WHEN** all required leaves have exact-current terminal receipts
- **THEN** closure returns a terminal pass with zero new executions
- **AND** the existing leaf receipt identities are preserved

#### Scenario: Foreign or tampered receipt
- **WHEN** a candidate receipt has a foreign owner, changed covered ids, bad
  fingerprint, or non-terminal result
- **THEN** the leaf is blocked or executed by its declared owner
- **AND** the aggregate is not allowed to relabel it as current

### Requirement: One bounded parent observation composes closure

One parent invocation SHALL verify each current child at most once, execute
only missing or stale native owners, run one post-producer source check, and
reconcile child identities once. It SHALL not rescan the receipt store or
recompute leaf semantics for every aggregate projection.

#### Scenario: Mixed reused and executed leaves
- **WHEN** one affected leaf is stale and the remaining leaves are current
- **THEN** only the stale owner executes
- **AND** the parent reports exact executed/reused/not-run counts and all leaf ids

#### Scenario: Source drift during execution
- **WHEN** a functional input changes before the final source check
- **THEN** publication is stale/blocked with the drift identity
- **AND** no second automatic run starts

### Requirement: Profiles and rehearsal are complexity-gated

Fast, focused, and full profiles SHALL select different declared functional
owner sets. Installation/release owners SHALL run only for an explicit
installation or release claim. Agent Workflow Rehearsal SHALL run only for an
explicit rehearsal request or a declared multi-owner/shared-write/irreversible
effect, route-change, or post-validation invalidation trigger.

#### Scenario: Ordinary small change
- **WHEN** one local behavior owner changes with no rehearsal trigger
- **THEN** fast or affected-focused closure runs the affected owner set
- **AND** no rehearsal, installation, release, or whole-suite owner runs

#### Scenario: Explicit cross-owner change
- **WHEN** a change crosses owner boundaries or has a shared write
- **THEN** focused/full routing includes the required rehearsal and relation
  checks exactly once
- **AND** unrelated owners are not widened into a run-all fallback

#### Scenario: Project-adoption audit is not a local functional owner
- **WHEN** a routine local model/code/test change is closed
- **THEN** project-layout/adoption, installation, release, and consumer-parity
  checks remain outside the local functional owner set
- **AND** those checks run only when their explicit qualification or release
  operation is requested

### Requirement: Temporary evidence is retained but not authoritative

Functional execution MAY retain temporary receipts, logs, and intermediate
artifacts in a controlled work root. They SHALL not enter the current
authority or published consumer projection unless explicitly promoted by their
native owner, and cleanup SHALL be a separate bounded operation.

#### Scenario: Work finishes with temporary evidence
- **WHEN** a closure run produces temporary artifacts
- **THEN** the artifacts remain available for diagnostics in the controlled root
- **AND** current authority and publication omit them

#### Scenario: Publication is requested
- **WHEN** an explicit install or release projection is requested
- **THEN** only the declared sanitized projection is published
- **AND** raw temporary evidence is excluded
