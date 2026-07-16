## ADDED Requirements

### Requirement: Target-owned conditional branch authority
SkillGuard SHALL derive the complete conditional branch universe from the target's exact `route_branch_requirements` and SHALL NOT embed target branch identifiers or target-domain branch semantics in the compiler or runtime.

#### Scenario: Arbitrary current branch names
- **WHEN** a target declares `current-noop` and `manual-apply` with complete route ownership and obligation dispositions
- **THEN** SkillGuard SHALL compile and operate those branches without requiring any historical branch identifier

#### Scenario: Runtime branch absent from target contract
- **WHEN** a native terminal names a branch not present exactly once in the selected target route and closure profile
- **THEN** SkillGuard SHALL reject it as an unknown or overlapping target branch

### Requirement: Total conditional obligation disposition
For every enforced route/branch pair, SkillGuard MUST require each conditional obligation to be either active or verifier-approved as `not_applicable`, and each conditional obligation MUST be active on at least one branch and not applicable on at least one branch.

#### Scenario: Conditional obligation omitted silently
- **WHEN** a branch neither requires a conditional obligation nor supplies its verifier-owned not-applicable rule
- **THEN** compilation SHALL fail with the exact missing branch disposition

#### Scenario: Conditional obligation is unreachable
- **WHEN** every branch marks the same conditional obligation not applicable
- **THEN** compilation SHALL fail because no branch can complete that obligation

#### Scenario: Conditional flag has no branch effect
- **WHEN** a conditional obligation remains active on every declared branch
- **THEN** compilation SHALL fail because no branch establishes its conditional disposition

### Requirement: Structurally classified native terminal
SkillGuard SHALL classify a branch with verifier-backed not-applicable rules as a conditional no-op and a branch without such rules as a completed branch, without inspecting the branch identifier.

#### Scenario: Target-declared no-op
- **WHEN** the selected branch has a valid not-applicable rule for a conditional obligation
- **THEN** SkillGuard SHALL issue the applicability receipt and close only after consuming the exact current native terminal and depth receipt

#### Scenario: Target-declared completing branch
- **WHEN** the selected branch has no applicability rules and all required obligations have current evidence
- **THEN** SkillGuard SHALL treat it as a completed branch and SHALL NOT require a prepared-update name or semantic

### Requirement: Evidence-domain-preserving native terminal
The native terminal MUST inherit the exact evidence domain of its selected current depth receipt. SkillGuard MUST reverify scheduled installation identity only for `scheduled_production`, and MUST forbid a scheduled identity for every non-scheduled evidence domain.

#### Scenario: Scheduled conditional run
- **WHEN** the selected depth receipt uses `scheduled_production`
- **THEN** the terminal SHALL carry the same exact scheduled identity and SkillGuard SHALL reverify current installed parity

#### Scenario: Non-scheduled conditional run
- **WHEN** the selected depth receipt uses a non-scheduled current evidence domain
- **THEN** the terminal SHALL carry that domain with an empty scheduled identity and SHALL close without manufacturing a scheduler identity

#### Scenario: Evidence identity mismatch
- **WHEN** the terminal evidence domain or scheduled identity differs from the selected depth receipt
- **THEN** SkillGuard SHALL reject the terminal as non-current

### Requirement: Verified forward replacement after unrestorable historical drift
When a historical installation head cannot restore because both its active tree and recorded backup have drifted, SkillGuard MUST keep ordinary recovery blocked. A new activation MAY proceed only from a separately verified current stage, MUST require each current active member to be a safe non-empty directory, and MUST snapshot those exact active members as the new transaction's backups before replacement.

#### Scenario: Recovery without a verified replacement
- **WHEN** the historical backup identity no longer matches and no verified replacement activation is in progress
- **THEN** SkillGuard SHALL remain blocked and SHALL NOT rewrite the active install or journal as successful

#### Scenario: Verified replacement is ready
- **WHEN** the historical head has stored activation integrity, the current active members are safe non-empty directories, and a distinct stage has current authority, exact parity, and passing smoke evidence
- **THEN** SkillGuard SHALL preserve explicit replacement-recovery provenance, snapshot the exact current active members in the new transaction, and MAY activate the verified replacement
