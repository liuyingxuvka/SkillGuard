## ADDED Requirements

### Requirement: Evidence records independent proof axes
SkillGuard SHALL record execution depth, environment scope, quality level, assertion category, result, freshness, covered outcome/stage/failure/quality ids, and direct artifact or command references for each capability evidence item.

#### Scenario: Real end-to-end evidence is fully described
- **WHEN** a native route produces a passing real task artifact with current fingerprints and exact coverage ids
- **THEN** SkillGuard credits the evidence only to the declared axes and coverage categories

#### Scenario: Passing result has no assertion scope
- **WHEN** an evidence item says pass but does not identify what behavior or result it proves
- **THEN** SkillGuard reports `evidence-missing-assertion-scope`

### Requirement: Prose and static structure are not runtime proof
SkillGuard SHALL NOT allow declaration, prose, schema presence, file existence, or static routing evidence to satisfy simulated or real end-to-end execution requirements.

#### Scenario: Deep contract is the only evidence
- **WHEN** a target is deep-pass but all capability evidence is declaration or static
- **THEN** SkillGuard keeps structural depth visible and reports the functional outcome as unverified

### Requirement: Stale or non-passing evidence cannot close a path
SkillGuard SHALL reject failed, blocked, skipped, not-run, stale, fingerprint-mismatched, or missing evidence for a current closure claim.

#### Scenario: Target changed after evidence was produced
- **WHEN** the recorded source fingerprint does not match the current target artifact
- **THEN** SkillGuard reports `stale-capability-evidence` and invalidates dependent path stages

### Requirement: Claim scopes enforce minimum evidence floors
SkillGuard SHALL apply distinct routine, functional, release, and highest-quality floors without averaging away a missing stage or quality requirement.

#### Scenario: Functional claim uses only fixtures
- **WHEN** all required path categories have fixture evidence but no simulated end-to-end positive path
- **THEN** routine scope may pass while functional scope reports `insufficient-execution-depth`

#### Scenario: Highest-quality claim lacks human review
- **WHEN** an outcome declares human or domain-expert quality as required but only deterministic checks exist
- **THEN** SkillGuard refuses highest-quality closure and reports the missing quality evidence
