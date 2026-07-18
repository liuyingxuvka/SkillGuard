## MODIFIED Requirements

### Requirement: Receipts are immutable and freshness is derived
Every author receipt SHALL bind maintenance unit, member skill, evidence subject, semantic check, owner, request, exact inputs, dependencies, implementation, contract, artifacts, toolchain, environment, and evidence domain. Currentness SHALL be derived, and a foreign-unit receipt SHALL always be inadmissible.

#### Scenario: Source changes after a passing test
- **WHEN** an exact input of the same unit's receipt changes
- **THEN** that receipt becomes stale until its owner executes again

#### Scenario: Identical foreign receipt is offered
- **WHEN** another maintenance unit presents a receipt with otherwise identical hashes
- **THEN** admission SHALL fail before closure or process launch

### Requirement: Parent closure consumes exact child receipts
An author parent closure SHALL consume only exact current child receipts from the same maintenance unit and SHALL become stale when one of its required unit-local children is superseded. It SHALL NOT transfer truth to another unit or an external provider.

#### Scenario: Same-unit child is rerun
- **WHEN** a required child produces a newer receipt
- **THEN** the parent becomes stale until it consumes that exact new unit-local receipt

#### Scenario: Foreign child is supplied
- **WHEN** a child receipt names another maintenance unit
- **THEN** parent closure SHALL block and SHALL NOT copy or reinterpret the child
