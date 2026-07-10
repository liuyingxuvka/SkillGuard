## ADDED Requirements

### Requirement: Closure profiles are monotonic
SkillGuard SHALL provide routine, functional, release, and highest-quality profiles whose requirements increase monotonically and never hide a failure visible at a weaker profile.

#### Scenario: Functional passes but release execution is missing
- **WHEN** functional evidence is current but release-only evidence has not run
- **THEN** functional may pass while release remains not-run or blocked with the missing evidence named

### Requirement: Only current exact evidence closes a run
SkillGuard SHALL close a run only when every required reachable step, artifact, check, terminal, and child receipt is passing, current, scope-matched, and consumed under the selected profile.

#### Scenario: Required check was skipped
- **WHEN** a required check is skipped, stale, partial, progress-only, or not run
- **THEN** full closure is refused

### Requirement: Reports preserve gaps and safe claim boundaries
SkillGuard SHALL report missing, failed, blocked, skipped, stale, and uncertain items, next actions, residual risk, a safe claim, and an unsafe claim boundary without collapsing them into one score.

#### Scenario: Useful work is incomplete
- **WHEN** some optional or judged evidence exists but a required artifact is missing
- **THEN** SkillGuard reports the useful evidence and exact gap while refusing an overbroad completion claim

### Requirement: Closure is replay-verifiable
SkillGuard SHALL allow a closure receipt to be verified against its immutable event and receipt history and SHALL invalidate it when covered history, contract, or inputs change.

#### Scenario: Event history is modified
- **WHEN** a closed run's event log or consumed receipt content no longer matches its recorded hash
- **THEN** closure verification fails and reports the altered boundary
