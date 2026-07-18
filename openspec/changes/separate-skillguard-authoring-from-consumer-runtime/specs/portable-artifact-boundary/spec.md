## MODIFIED Requirements

### Requirement: Shared portable-artifact policy
SkillGuard SHALL maintain two explicit projections of one complete source classification: `maintainer-control`, which may contain author contracts, models, tests, receipts, and prompts, and `consumer-distribution`, which contains only target-owned domain files and rejects all SkillGuard control state.

#### Scenario: Author source classifies a path
- **WHEN** a maintained file is used only for contract compilation, author validation, Portfolio, or author routing
- **THEN** it SHALL belong only to `maintainer-control`

#### Scenario: Consumer classifies a path
- **WHEN** a target-owned prompt, reference, asset, script, runtime, or data file is required for ordinary work
- **THEN** it MAY belong to `consumer-distribution` only when it has no SkillGuard import, command, receipt, or hidden author-state dependency

### Requirement: Runtime workspaces are never portable
Live workspaces, caches, locks, run records, bootstrap outputs, receipts, test result roots, and temporary generation directories MUST NOT enter consumer distributions. Author maintenance runtime SHALL remain under an explicit author evidence root outside the target consumer tree.

#### Scenario: Consumer contains `.skillguard`
- **WHEN** any staged or installed consumer skill contains `.skillguard/**`
- **THEN** consumer validation and activation SHALL block

#### Scenario: Author evidence exists
- **WHEN** a maintainer run writes locks, runs, or receipts
- **THEN** those files SHALL remain under the explicit author evidence root and SHALL NOT make the target consumer projection stale

### Requirement: Maintained content is classified into semantic components
Every maintained leaf SHALL have one semantic role and explicit membership in zero or more named projections. A target-domain file hidden under an author-control prefix SHALL block consumer construction until it moves to a target-owned namespace.

#### Scenario: Hidden target runtime is found
- **WHEN** `.skillguard/runtime` contains a file referenced by the target's ordinary entrypoint
- **THEN** cleanup SHALL block and report the required target-owned relocation

#### Scenario: Author-only test changes
- **WHEN** an author test has no edge to consumer files
- **THEN** only maintainer validation becomes stale
