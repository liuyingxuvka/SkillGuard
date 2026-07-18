## ADDED Requirements

### Requirement: Independent unit graduation
Every Portfolio entry SHALL graduate only from the current source-maintenance and consumer-isolation evidence of its own maintenance unit.

#### Scenario: One target is green
- **WHEN** one unit has complete current evidence and another is pending or failed
- **THEN** Portfolio SHALL report the first unit green and the second unit's actual state without transferring proof

#### Scenario: Foreign prior evidence supplied
- **WHEN** a graduation candidate cites another unit's full-run or installation receipt
- **THEN** graduation SHALL block

### Requirement: Status-only aggregation
Portfolio parent status SHALL be a read-only aggregation of independent child decisions and MUST NOT become an execution or evidence owner.

#### Scenario: Portfolio summary is requested
- **WHEN** all active units have current independent decisions
- **THEN** the summary MAY report their aggregate status and exact child receipt references without rewriting or re-signing them

#### Scenario: Parent summary used as child proof
- **WHEN** a child currentness check is offered only a Portfolio parent receipt
- **THEN** the child SHALL remain unproven

### Requirement: No cross-unit reuse ticket
Portfolio MUST NOT issue or consume a reuse ticket that authorizes evidence across maintenance units.

#### Scenario: Guard implementation change does not affect a unit
- **WHEN** the exact component impact graph has no edge to a unit and that unit's own execution identity is unchanged
- **THEN** its own receipt SHALL remain current without a reuse ticket

#### Scenario: Guard implementation change affects a unit
- **WHEN** the exact component impact graph reaches a unit
- **THEN** only that unit's affected checks and consumer projection SHALL become stale and require revalidation

### Requirement: Explicit scope and exclusions
Portfolio SHALL inventory explicitly managed units, supporting members, external exclusions, and retired units without discovering ordinary installed skills as managed targets.

#### Scenario: OpenSpec appears in installed root
- **WHEN** the author Portfolio is built
- **THEN** OpenSpec SHALL remain `external_excluded` and outside the graduation queue
