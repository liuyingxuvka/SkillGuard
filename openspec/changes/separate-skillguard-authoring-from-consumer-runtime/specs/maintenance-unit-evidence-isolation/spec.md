## ADDED Requirements

### Requirement: Maintenance-unit identity
Every maintained target, declared check, execution key, dependency, receipt, and evidence root MUST identify exactly one `maintenance_unit_id`.

#### Scenario: Complete unit identity
- **WHEN** a target contract is compiled
- **THEN** its unit, member, evidence subject, semantic check, owner, dependencies, and projections SHALL be explicit and internally consistent

#### Scenario: Missing unit identity
- **WHEN** any current declared check or receipt lacks a maintenance-unit identity
- **THEN** compilation or receipt admission SHALL block

### Requirement: Cross-unit evidence rejection
A receipt or dependency from one maintenance unit MUST NOT satisfy a check, closure, or graduation claim for another maintenance unit.

#### Scenario: Identical command and inputs across units
- **WHEN** two units declare checks with identical commands, inputs, toolchains, and environments
- **THEN** they SHALL have distinct execution keys and each unit SHALL produce or reuse only its own receipt

#### Scenario: Foreign dependency receipt
- **WHEN** a check references a dependency receipt from another maintenance unit
- **THEN** execution SHALL block with a cross-unit receipt finding

### Requirement: Same-unit exact-check single-flight
SkillGuard SHALL permit single-flight only for the same maintenance unit, member, evidence subject, semantic check, owner, exact inputs, dependencies, toolchain, and environment.

#### Scenario: Concurrent duplicate request
- **WHEN** two author workflows request the same complete execution identity concurrently
- **THEN** one owner process SHALL execute and both workflows MAY read the same current terminal receipt

#### Scenario: Different evidence subject
- **WHEN** two checks share a command but protect different evidence subjects
- **THEN** they SHALL execute and issue receipts independently

### Requirement: Semantic responsibility overlap audit
SkillGuard SHALL compare explicit semantic ownership across maintained units and SHALL block duplicate responsibility instead of creating shared evidence.

#### Scenario: Duplicate semantic test owner
- **WHEN** two units claim the same semantic test or protected responsibility
- **THEN** the portfolio boundary audit SHALL require split, merge, or retirement before either can graduate

#### Scenario: Generic tool check in separate units
- **WHEN** separate units each run a generic syntax or import check over their own source
- **THEN** the checks MAY remain separately owned without being classified as a shared semantic responsibility
