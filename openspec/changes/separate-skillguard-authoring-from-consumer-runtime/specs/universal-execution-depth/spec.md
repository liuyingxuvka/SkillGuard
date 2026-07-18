## MODIFIED Requirements

### Requirement: Native route preservation
SkillGuard MUST preserve a target's existing route and exact declared-check ownership and MUST reject every parallel or substitute target-domain executor.

#### Scenario: Complete native system
- **WHEN** a target has a native router and checks
- **THEN** its integration mode SHALL be `native-integrated` and every domain receipt SHALL identify that native owner

#### Scenario: Partial native system
- **WHEN** a target's native route or declared checks are incomplete
- **THEN** SkillGuard SHALL block enforced maintenance until the target completes its own native boundary and SHALL NOT supply the missing domain route

#### Scenario: No native runtime
- **WHEN** no target-native runtime route exists
- **THEN** SkillGuard SHALL remain a contract and release supervisor and SHALL NOT become the target-domain runtime

### Requirement: Current target execution receipt
Every non-trivial enforced author-maintenance run MUST produce an immutable author-side target execution receipt bound to the maintenance unit, member, evidence subject, request, target version, depth profile, native route/check identities, observations, artifacts, and SkillGuard runtime fingerprint.

#### Scenario: Current deep execution
- **WHEN** all target-declared checks have current unique evidence and the author-maintenance closure consumes the receipt
- **THEN** the evaluator SHALL issue `EXECUTION_DEPTH_PASS`

#### Scenario: Source changes after receipt
- **WHEN** target source, profile, native checks, SkillGuard runtime, or maintenance-unit identity changes after a receipt
- **THEN** replay SHALL classify that receipt as `STALE`

#### Scenario: Ordinary consumer use
- **WHEN** a graduated target performs ordinary domain work
- **THEN** it SHALL NOT require, create, or consume an author-maintenance execution receipt

### Requirement: Unique evidence contribution
SkillGuard SHALL prevent one receipt from being counted repeatedly as independent proof for unrelated target obligations or different maintenance units.

#### Scenario: Reused generic checks inside one unit
- **WHEN** several obligations cite one generic check without distinct target-owned evidence subjects
- **THEN** execution-depth evaluation SHALL block with a duplicate or insufficient evidence-contribution finding

#### Scenario: Receipt offered across units
- **WHEN** a receipt from one maintenance unit is offered for another unit
- **THEN** execution-depth evaluation SHALL block with a cross-unit evidence finding

### Requirement: Closure consumes execution depth
Broad author-maintenance, graduation, installation, release, archive, or publish closure MUST consume a current accepted execution-depth receipt for every enforced maintenance unit in scope. Ordinary consumer domain work MUST NOT require that receipt.

#### Scenario: Contract mapped but execution shallow
- **WHEN** `CONTRACT_DEPTH_PASS` exists but the current maintenance run is `SHALLOW_BLOCKED`
- **THEN** broad maintenance or release closure SHALL fail and SHALL report the execution gap

#### Scenario: Graduated skill is used
- **WHEN** a consumer invokes the independently distributed skill
- **THEN** missing SkillGuard execution-depth state SHALL NOT block the target's domain closure

### Requirement: Canonical source and installed parity
The Git repository SHALL be the canonical author source. Maintainer deployment and consumer installation MUST use separate exact projections, staged validation, backup, atomic activation, and automatic rollback.

#### Scenario: Maintainer projection
- **WHEN** SkillGuard deploys an author maintenance workspace
- **THEN** the projection MAY include current contracts, models, tests, and author-control state

#### Scenario: Consumer projection
- **WHEN** a graduated target is installed for ordinary use
- **THEN** the projection SHALL exclude author-control state and parity SHALL compare only target-owned consumer files

#### Scenario: Partial installed sync
- **WHEN** only selected files are copied outside the frozen projection
- **THEN** installation parity SHALL fail and broad readiness SHALL remain blocked

#### Scenario: Post-activation check fails
- **WHEN** staged activation succeeds but a required post-activation validation fails
- **THEN** the installer SHALL restore the previous active tree and retain failure evidence

### Requirement: Author repository adoption
SkillGuard SHALL generate a marker-bounded author prompt block and author project record only for an explicitly adopted skill-maintainer repository.

#### Scenario: New AI opens an author repository
- **WHEN** an AI reads the maintainer repository `AGENTS.md`
- **THEN** it SHALL see the explicit managed units, author evidence boundary, and target-native ownership rules

#### Scenario: Ordinary project lacks SkillGuard
- **WHEN** a consumer or business project has no SkillGuard installation or project record
- **THEN** ordinary target-domain work SHALL continue without a SkillGuard blocked state

### Requirement: Safe author prompt lifecycle
Author-repository adoption MUST preserve unrelated repository instructions and MUST fail closed on missing, duplicated, incomplete, or stale author-managed blocks without writing to ordinary projects.

#### Scenario: Existing author instructions surround the block
- **WHEN** author adoption directly rewrites the current SkillGuard block
- **THEN** all content outside the exact markers SHALL remain unchanged

#### Scenario: Ordinary project is supplied
- **WHEN** the repository lacks explicit skill-maintainer role and maintenance-unit declarations
- **THEN** adoption SHALL reject the request before changing `AGENTS.md` or creating a manifest

## REMOVED Requirements

### Requirement: Portable SkillGuard project adoption
**Reason**: Portable adoption put SkillGuard control state and a blocking maintenance dependency into ordinary consumer repositories.

**Migration**: Explicitly adopt only canonical skill-maintainer repositories. Consumer and business projects remain unmanaged by SkillGuard and receive no SkillGuard prompt or manifest.
