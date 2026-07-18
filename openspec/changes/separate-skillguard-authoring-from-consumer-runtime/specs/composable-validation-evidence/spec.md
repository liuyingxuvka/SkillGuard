## MODIFIED Requirements

### Requirement: Ordered validation ownership
SkillGuard SHALL freeze validation ownership separately for each maintenance unit. Within one unit, checks SHALL be ordered by cost and dependency and an identical complete execution identity MAY have one primary owner. Different maintenance units SHALL retain independent owners and receipts even when commands and inputs are identical.

#### Scenario: Two checks inside one unit are exact duplicates
- **WHEN** the unit, member, evidence subject, semantic check, owner inputs, dependencies, toolchain, environment, and evidence domain are identical
- **THEN** one primary process MAY execute and both same-unit requests MAY consume its current immutable receipt

#### Scenario: Two maintenance units name the same command
- **WHEN** otherwise identical checks belong to different maintenance units
- **THEN** each unit SHALL own and execute or reuse only its own receipt

### Requirement: Proof-bound TestMesh child reuse
SkillGuard SHALL permit reuse of a prior TestMesh child only inside the same maintenance unit and only for the identical unit, member, evidence subject, semantic check, owner, manifest, input projection, dependency set, command, toolchain, environment, coverage, result, and evidence-domain identity.

#### Scenario: Same-unit child remains current
- **WHEN** every complete identity field remains unchanged inside one maintenance unit
- **THEN** the same unit MAY attach the exact current immutable child receipt without another process

#### Scenario: Foreign-unit child is supplied
- **WHEN** the child receipt names another maintenance unit
- **THEN** TestMesh SHALL reject it before execution or parent aggregation

### Requirement: Parent reattachment preserves claim boundaries
A TestMesh parent SHALL aggregate only child receipts from its own maintenance unit. The parent SHALL retain the unit, profile, timeout, coverage, and claim-boundary identity and SHALL NOT become proof for another unit or an external provider.

#### Scenario: Every same-unit child is current
- **WHEN** the selected parent contains the complete current child set for one maintenance unit
- **THEN** the parent MAY report that unit's aggregate status without rewriting child receipts

#### Scenario: Parent contains a foreign child
- **WHEN** any required child names another maintenance unit
- **THEN** parent aggregation SHALL block and no receipt SHALL transfer

### Requirement: Exact single-flight check execution
SkillGuard SHALL keep maintenance unit, member, evidence subject, semantic check, concrete execution, and execution key distinct. Only the same complete identity inside one maintenance unit may single-flight; failed or foreign-unit attempts MUST NOT satisfy or poison its success head.

#### Scenario: The same exact check is requested twice inside one unit
- **WHEN** the complete execution identity and inputs remain current
- **THEN** one process SHALL execute and the second request MAY receive that exact unit-local success receipt

#### Scenario: A second unit requests the same command
- **WHEN** maintenance-unit identity differs
- **THEN** the second unit SHALL use a distinct lock, execution key, success slot, and receipt

### Requirement: Validation execution ownership is explicit and frozen
Each maintenance unit SHALL freeze its own check inventory, dependencies, covered obligations, evidence domains, author evidence root, and primary execution owners before validation. No task-level multi-unit plan or consumer SHALL transfer receipts between units. Full validation SHALL start only after that unit's source and toolchain freeze under one explicit owner; interrupted launchers require confirmed zero descendants, and unattended mutable-worktree retry remains forbidden.

#### Scenario: Multi-unit plan offers one shared owner
- **WHEN** one execution owner or receipt is proposed to satisfy checks from different maintenance units
- **THEN** validation SHALL block and require separate unit plans or a deliberate unit-boundary merge

#### Scenario: One unit is frozen
- **WHEN** all owners, inputs, dependencies, evidence roots, and toolchains for one unit are frozen
- **THEN** only that unit's exact plan MAY execute or reuse unit-local receipts

### Requirement: Installation, Portfolio, and routing consume graph projections
Maintainer deployment, consumer distribution, Portfolio status, and the author registry SHALL consume distinct explicit projections. Consumer distribution MUST exclude author-control state. Ordinary target use MUST NOT invoke SkillGuard, and an external provider MUST NOT consume SkillGuard receipts.

#### Scenario: Test-only author source changes
- **WHEN** a source-only author component changes
- **THEN** consumer distribution SHALL remain current unless its exact target-owned input projection changed

#### Scenario: Consumer distribution is built
- **WHEN** a graduated target is staged for ordinary installation
- **THEN** `.skillguard`, receipts, Portfolio data, author router state, and SkillGuard prompts SHALL be absent

## REMOVED Requirements

### Requirement: Full-parent receipt consumers are read-only
**Reason**: External and OpenSpec receipt consumption is itself an invalid authority bridge, even when read-only.

**Migration**: Keep parent aggregation private to one maintenance unit. External providers run their own native validation and receive no SkillGuard receipt.

### Requirement: Single-skill activation is projection-exact and transaction-isolated
**Reason**: The former `projection:installation` mixed author controls with consumer files.

**Migration**: Use explicit maintainer deployment for author state and `projection:consumer-distribution` for independently usable target files, both with separate staged transactions.
