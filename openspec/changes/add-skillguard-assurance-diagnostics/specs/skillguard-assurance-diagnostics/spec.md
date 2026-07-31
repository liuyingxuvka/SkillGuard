## ADDED Requirements

### Requirement: Assurance diagnostics are read-only projections

SkillGuard SHALL derive diagnostics only from current compiled contract, check manifest, impact graph, receipts, and closure identities and SHALL NOT become another closure authority.

#### Scenario: Diagnostics run on a blocked closure

- **WHEN** current closure is blocked
- **THEN** diagnostics SHALL explain blockers while preserving the blocked terminal

#### Scenario: A receipt is missing

- **WHEN** a diagnostic input lacks a required current receipt
- **THEN** diagnostics SHALL report the missing evidence and SHALL NOT execute or resume the owner

### Requirement: Blocker bases use exact minimality language

SkillGuard SHALL distinguish deletion-proven subset minimality, unproven minimum cardinality, and bounded incomplete computation.

#### Scenario: Dependency-aware deletion minimality is proven

- **WHEN** removing any retained blocker makes the selected blocked obligation no longer explained
- **THEN** the report SHALL label the basis `subset_minimal`

#### Scenario: Minimum cardinality was not exhaustively proven

- **WHEN** only deletion minimization ran
- **THEN** the report SHALL NOT claim `minimum_cardinality`

### Requirement: Mutation adequacy remains target-owned

SkillGuard SHALL consume mutation adequacy only as a target-declared native check with explicit applicability, oracle, and current receipt evidence.

#### Scenario: Target mutation contract is complete

- **WHEN** the target declares operators, oracle, applicability, equivalent-mutant disposition, threshold, and current native receipt
- **THEN** SkillGuard SHALL report the target result without reinterpreting its domain judgment

#### Scenario: Target mutation contract is incomplete

- **WHEN** any required declaration or native evidence is absent
- **THEN** mutation adequacy SHALL be `not_run` or `blocked`, never inferred from ordinary tests

### Requirement: Diagnostics cannot weaken claims

Assurance diagnostics SHALL provide explanatory next actions only and SHALL NOT remove, relax, or auto-scope a target obligation.

#### Scenario: A next action proposes deleting an obligation

- **WHEN** no explicit target requirement authorizes that removal
- **THEN** diagnostics SHALL reject it as an unauthorized weakening
