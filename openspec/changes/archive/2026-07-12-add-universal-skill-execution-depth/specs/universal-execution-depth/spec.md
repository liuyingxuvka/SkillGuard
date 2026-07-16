## ADDED Requirements

### Requirement: Target-neutral depth profile
SkillGuard SHALL compile an optional target-owned depth profile using universal dimensions without embedding target names or domain rules in the core evaluator.

#### Scenario: Non-Guard profile compiles
- **WHEN** a document or spreadsheet skill declares only workflow, artifact, validation, and closure dimensions
- **THEN** the same compiler SHALL accept the profile without Guard-specific fields

#### Scenario: Domain rule stays target-owned
- **WHEN** a target declares a semantic obligation such as a physical envelope or logic rebuttal
- **THEN** the compiled contract SHALL bind it to the target's native action or check rather than implement it in SkillGuard

### Requirement: Native route preservation
SkillGuard MUST preserve a target's existing route and check ownership and MUST reject a parallel domain executor.

#### Scenario: Complete native system
- **WHEN** a target has a complete native router and checks
- **THEN** its integration mode SHALL be `native-integrated` and every domain receipt SHALL identify that native owner

#### Scenario: Partial native system
- **WHEN** a target has a partial native route/check system
- **THEN** `hybrid-extension` SHALL add only the missing supervision gates and SHALL retain the native owner

#### Scenario: No native runtime
- **WHEN** no native runtime route exists
- **THEN** `skillguard-runtime` MAY provide a route and the contract SHALL record why no native route could be extended

### Requirement: Current target execution receipt
Every non-trivial enforced run MUST produce an immutable target-local execution receipt bound to the request, target version, depth profile, native route/check identities, observations, artifacts, and SkillGuard runtime fingerprint.

#### Scenario: Current deep execution
- **WHEN** all required important obligations have current unique evidence and closure consumes the receipt
- **THEN** the evaluator SHALL issue `EXECUTION_DEPTH_PASS`

#### Scenario: Source changes after receipt
- **WHEN** target source, profile, native checks, or SkillGuard runtime changes after a receipt
- **THEN** replay SHALL classify that receipt as `STALE`

### Requirement: Unique evidence contribution
SkillGuard SHALL prevent one generic receipt from being counted repeatedly as independent proof for unrelated target obligations.

#### Scenario: Reused generic checks
- **WHEN** forty-six target obligations all cite the same five generic checks without target-specific observations
- **THEN** execution-depth evaluation SHALL block with a duplicate or insufficient evidence-contribution finding

### Requirement: Honest depth status
SkillGuard SHALL preserve `EXECUTION_DEPTH_PASS`, `BOUNDED_PARTIAL`, `BOUNDARY_ONLY`, `SHALLOW_BLOCKED`, `NOT_RUN`, `DEPTH_CONTRACT_MISSING`, `PROVIDER_UNAVAILABLE`, `UNMANAGED`, and `STALE` as distinct terminal states.

#### Scenario: Provider is unavailable
- **WHEN** a required external provider cannot run and no valid alternative evidence exists
- **THEN** the status SHALL be `PROVIDER_UNAVAILABLE` and SHALL NOT be promoted to pass

#### Scenario: Explicit bounded task
- **WHEN** the request intentionally covers a declared subset and the bounded closure profile is satisfied
- **THEN** the status MAY be `BOUNDED_PARTIAL` with uncovered obligations and claim limits listed

### Requirement: Calibration before enforcement
A target SHALL NOT enter enforced mode until representative positive tasks and intentionally shallow bad tasks prove that its profile distinguishes deep from shallow execution.

#### Scenario: Only positive jobs exist
- **WHEN** a target passes representative positive jobs but has no shallow bad-case evidence
- **THEN** its lifecycle SHALL remain `advisory`

#### Scenario: Both keys pass
- **WHEN** positive jobs pass, shallow bad jobs block for the intended reasons, and all capabilities are covered
- **THEN** portfolio graduation MAY set the target to `enforced`

### Requirement: Closure consumes execution depth
Broad functional, release, archive, or publish closure MUST consume a current accepted execution-depth receipt for every enforced target in scope.

#### Scenario: Contract mapped but execution shallow
- **WHEN** `CONTRACT_DEPTH_PASS` exists but the current run is `SHALLOW_BLOCKED`
- **THEN** broad closure SHALL fail and SHALL report the execution gap

### Requirement: Canonical source and installed parity
The Git repository SHALL be the canonical SkillGuard source after migration, and installation SHALL use whole-tree staged copy, validation, backup, and automatic rollback.

#### Scenario: Partial installed sync
- **WHEN** only selected V2 files are copied into the installed tree
- **THEN** installation parity SHALL fail and broad readiness SHALL remain blocked

#### Scenario: Post-activation check fails
- **WHEN** staged activation succeeds but a required post-activation validation fails
- **THEN** the installer SHALL restore the previous active tree and retain failure evidence

### Requirement: Portable SkillGuard project adoption
SkillGuard SHALL generate a marker-bounded project prompt block and portable project record for every adopted target repository, naming `https://github.com/liuyingxuvka/SkillGuard` and making SkillGuard the default maintenance workflow for covered skills.

#### Scenario: New AI opens an adopted repository
- **WHEN** an AI reads the repository `AGENTS.md`
- **THEN** it SHALL see that non-trivial skill maintenance, validation, installation, and release use SkillGuard, while the target's native route remains the domain owner

#### Scenario: Different computer lacks SkillGuard
- **WHEN** an adopted repository is opened on a computer without a current SkillGuard installation
- **THEN** the managed block SHALL provide the public GitHub repository and SHALL require installation or an explicit blocked/partial report before SkillGuard confidence is claimed

### Requirement: Safe project prompt lifecycle
Project adoption MUST preserve unrelated repository instructions and MUST fail closed on missing, duplicated, incomplete, or stale managed blocks.

#### Scenario: Existing project instructions surround the block
- **WHEN** `project-upgrade` refreshes the SkillGuard block
- **THEN** all content outside the exact markers SHALL remain unchanged

#### Scenario: One marker is missing
- **WHEN** `AGENTS.md` contains only the begin or end marker
- **THEN** adoption and audit SHALL block instead of guessing replacement boundaries
