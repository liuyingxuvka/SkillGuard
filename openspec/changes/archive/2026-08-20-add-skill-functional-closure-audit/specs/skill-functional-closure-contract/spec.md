## ADDED Requirements

### Requirement: Required outcomes are explicit
SkillGuard SHALL require each maintained functional-closure record to identify every required user outcome, representative user job, success result or artifact, non-goal boundary, quality requirement, and closure path.

#### Scenario: Complete outcome declaration
- **WHEN** a target declares a required outcome with user jobs, success outputs, non-goals, quality requirements, and a path id
- **THEN** SkillGuard accepts the outcome declaration for further closure evaluation

#### Scenario: Outcome has no useful result
- **WHEN** a required outcome omits both a success result and a success artifact
- **THEN** SkillGuard reports `missing-success-output` and refuses functional closure

### Requirement: Closure paths cover the user-visible lifecycle
SkillGuard SHALL require every required outcome path to cover trigger, intake, route, execute, produce, validate, and terminal roles in order, with native owner and evidence bindings for each required stage.

#### Scenario: Complete ordered path
- **WHEN** a path contains all required roles in valid order and every stage binds current evidence
- **THEN** SkillGuard marks the path structurally complete

#### Scenario: UI or workflow stops after implementation
- **WHEN** a path declares execution but omits production, validation, or terminal evidence
- **THEN** SkillGuard reports the missing stage roles and refuses functional closure

### Requirement: Failure and recovery boundaries are closed
SkillGuard SHALL require route, execution, production, and validation failures to have a declared detector, disposition, terminal effect, and current evidence; recoverable failures SHALL bind a recovery path.

#### Scenario: Recoverable failure has a tested recovery path
- **WHEN** a failure is marked recoverable and cites a recovery path with current evidence
- **THEN** SkillGuard treats the failure boundary as covered

#### Scenario: Failure silently falls through to success
- **WHEN** a declared failure has no detector, disposition, recovery path, or blocking terminal
- **THEN** SkillGuard reports `unclosed-failure-boundary` and refuses closure

### Requirement: Stop conditions and non-goals prevent false completion
SkillGuard SHALL require explicit success, blocked, escalated, and scoped terminal conditions and SHALL verify that declared non-goals cannot satisfy a required outcome.

#### Scenario: Safe blocked terminal
- **WHEN** required input is unavailable and the declared path produces a blocked terminal with evidence
- **THEN** SkillGuard accepts the failure terminal without treating the outcome as successful

#### Scenario: Non-goal is counted as success
- **WHEN** evidence covers only a declared non-goal or helper output
- **THEN** SkillGuard reports `non-goal-evidence-used-for-success`
