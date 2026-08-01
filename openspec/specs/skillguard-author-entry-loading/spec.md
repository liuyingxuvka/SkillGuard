# skillguard-author-entry-loading Specification

## Purpose
Define a compact, author-only SkillGuard entry that selects one current maintenance route from explicit identity or typed request facts and loads only the reference material that route requires.
## Requirements
### Requirement: SkillGuard entry remains author-only
The always-loaded SkillGuard entry SHALL first establish an explicit `skill_maintainer_source`, maintenance unit, member inventory, and private evidence boundary. Ordinary use of a graduated consumer skill, official OpenSpec work, and unregistered installed skills MUST remain outside SkillGuard admission.

#### Scenario: Ordinary consumer task mentions a maintained skill
- **WHEN** a task uses an installed consumer skill for its domain behavior but does not request author maintenance
- **THEN** SkillGuard does not start and requires no contract, receipt, registry, or author path from the consumer

#### Scenario: Registered author source is maintained
- **WHEN** the task names an explicit maintained author source and requests maintenance, checking, installation, or release
- **THEN** SkillGuard admits the task and binds it to that exact maintenance unit before any write or execution

### Requirement: Route applicability is predicate-derived
Each current SkillGuard author route SHALL declare positive applicability facts, forbidden facts, required inputs, read/write authority, one first command, one next reference, and one claim boundary. Selection SHALL use an explicit current route id or program-evaluated typed facts; keyword score MUST NOT authorize a semantic route.

#### Scenario: Explicit route id is current and compatible
- **WHEN** the request supplies one current route id and its required and forbidden predicates pass
- **THEN** SkillGuard selects that exact route and returns its first command and next reference

#### Scenario: Typed facts match exactly one route
- **WHEN** the request supplies typed facts that satisfy exactly one current route without a route id
- **THEN** SkillGuard selects that route with a fact-derived decision record

#### Scenario: Route cannot be decided exactly
- **WHEN** zero routes match, several routes match, a route is stale, required inputs are absent, or a forbidden predicate is true
- **THEN** SkillGuard blocks with the exact candidates and missing or conflicting facts instead of scoring or guessing

### Requirement: One registry owns all route projections
The current route registry SHALL be the sole semantic route authority. The machine-readable route index, public SkillGuard entry, global maintainer prompt, route-task output, and fixtures MUST be deterministic projections of that registry and MUST fail currentness checks if they drift.

#### Scenario: Route index is generated
- **WHEN** the SkillGuard source is compiled or checked
- **THEN** the generated route index exactly equals the current registry's public fields and fingerprint

#### Scenario: Hand-written route projection drifts
- **WHEN** a route appears in the prompt or index with different ownership, first action, reference, or claim boundary
- **THEN** validation fails and requires regeneration from the registry

### Requirement: Selected route controls prompt loading
The public `SKILL.md` SHALL contain only author boundary, minimum typed facts, exact route selection, conditional reference loading, terminals, shared hard gates, and claim boundary. Detailed supervision, execution-depth, TestMesh, Portfolio, installation, diagnostics, and self-host protocols SHALL load only for their declared routes.

#### Scenario: Read-only maintainer audit stays light
- **WHEN** typed facts select the author-audit route
- **THEN** the prompt bundle loads the entry shell and audit reference but excludes installation, Portfolio execution, and release protocols

#### Scenario: Final maintenance validation is selected
- **WHEN** typed facts select the current supervision and closure route
- **THEN** the prompt bundle loads the declared supervisor, execution-depth, and TestMesh references before a closure claim

### Requirement: Validated template guidance is conditional and complete
When a target declares validated-template-pack support, the target's generated consumer material SHALL contain the full target-owned validated-template guidance in a dedicated reference and only a short trigger-and-pointer in `SKILL.md`. Targets without that trigger MUST NOT load or receive the reference.

#### Scenario: Target has validated template packs
- **WHEN** the target contract declares current template selection, instance, validation, and installation ownership
- **THEN** generation emits the complete target-owned reference and a conditional pointer whose identity is covered by installation currentness

#### Scenario: Target has no template route
- **WHEN** the target contract declares no validated-template-pack capability
- **THEN** generation emits neither the full reference nor a misleading template trigger

### Requirement: Global maintainer prompt is a compact registry pointer
The managed global SkillGuard block SHALL contain only author-only trigger conditions, direct-current maintenance rules, the private registry identity/path, a compact selection instruction, and the consumer-independence claim boundary. It MUST NOT repeat the full current route catalog, target template lifecycle manual, or ordinary consumer workflow.

#### Scenario: Global block routes author maintenance
- **WHEN** a user explicitly requests maintenance of a registered author source
- **THEN** the block points the agent to the private registry and selected source without loading all route protocols

#### Scenario: Global block is measured
- **WHEN** the global prompt is regenerated
- **THEN** mandatory content and a declared maximum size are both validated, preserving headroom for task reasoning

### Requirement: Patch identity is consistent
SkillGuard's source metadata, package metadata, generated prompt identity, self-host contract, installed author runtime, Git tag, and GitHub Release SHALL use patch version `0.7.2`, with each authority verified separately.

#### Scenario: Source candidate is ready
- **WHEN** the candidate source is frozen before publication
- **THEN** source version, generated route index, prompt projections, FlowGuard model authority, and self-host contract agree on `0.7.2`
- **AND** installation, Git, tag, and GitHub Release remain unclaimed until their own checks pass

