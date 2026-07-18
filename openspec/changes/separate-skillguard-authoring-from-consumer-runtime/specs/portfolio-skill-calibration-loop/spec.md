## MODIFIED Requirements

### Requirement: Current portfolio registry is a direct scope replacement
The author Portfolio SHALL be built directly from explicit managed maintenance units, their members, semantic ownership, source-maintenance status, consumer-isolation status, external exclusions, and retired units. It SHALL NOT discover ordinary installed skills as managed or consume prior-target receipts, reuse tickets, or migration authority.

#### Scenario: Reviewed scope replaces a stale registry
- **WHEN** the explicit managed-unit scope is approved
- **THEN** Portfolio SHALL construct the sole current registry and keep each unit independently pending until its own evidence is current

#### Scenario: OpenSpec is present
- **WHEN** official OpenSpec skills exist in the installed root
- **THEN** they SHALL appear only as external exclusions and SHALL NOT enter graduation or blocked-target counts

### Requirement: Guard changes invalidate affected prior graduates
An author implementation change SHALL stale only maintenance units reached by the exact component-impact graph. An unaffected unit retains its own current receipt; Portfolio SHALL NOT create a reuse ticket or borrow another unit's evidence.

#### Scenario: One unit is affected
- **WHEN** the changed component graph reaches one maintenance unit
- **THEN** only that unit's own maintenance and consumer-isolation evidence becomes stale

#### Scenario: Another unit is unaffected
- **WHEN** its exact source, toolchain, unit identity, checks, and consumer projection remain unchanged
- **THEN** its own current evidence remains current without a reuse ticket

### Requirement: Portfolio regression uses a TestMesh-backed hierarchy
Each maintenance unit MAY use its own TestMesh hierarchy. Portfolio SHALL aggregate the terminal status of independent unit roots and SHALL reject any hierarchy or parent receipt that spans units.

#### Scenario: All units are independently green
- **WHEN** every active unit has its own current source-maintenance and consumer-isolation evidence
- **THEN** Portfolio MAY report all units green without creating a shared proof root

#### Scenario: Mixed-unit parent is supplied
- **WHEN** one TestMesh parent contains children from different maintenance units
- **THEN** Portfolio SHALL block the parent and preserve the independent child statuses

### Requirement: Parent graduation preserves child truth
Portfolio graduation SHALL consume only the current unit's own terminal evidence and SHALL display every other unit's independent status without using it as proof for the current unit.

#### Scenario: Current unit passes and another unit fails
- **WHEN** one unit has current green evidence and another unit is stale or failed
- **THEN** the first unit remains independently green, the second remains visibly non-green, and neither receipt satisfies the other
