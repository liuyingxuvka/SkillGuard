## ADDED Requirements

### Requirement: Every real task claims a contract run
SkillGuard SHALL instantiate a target-local run for every supervised task, including native-integrated tasks, and SHALL freeze request, target, contract, route, and claim-scope fingerprints.

#### Scenario: Duplicate claim
- **WHEN** the same request and target are claimed again under the same contract
- **THEN** SkillGuard returns the existing run idempotently

#### Scenario: Conflicting writer claim
- **WHEN** another active run owns an overlapping write target
- **THEN** SkillGuard blocks the claim and reports the owning run and release condition

#### Scenario: Failed or crashed writer lock
- **WHEN** an overlapping prior run has a verified failed terminal event or its recorded owner process no longer exists
- **THEN** SkillGuard records a stale-lock recovery event, releases only that prior run's locks, and permits a fresh claim while continuing to block a live writer

#### Scenario: Idempotent resume after lock release
- **WHEN** the same run resumes after its prior process released or lost the transient locks
- **THEN** SkillGuard replays the durable run and reacquires every declared write lock before returning the idempotent claim

### Requirement: Step authority is verifier-derived
SkillGuard SHALL treat an AI completion action as evidence submission and SHALL allow only the verifier to derive passed status.

#### Scenario: AI writes passed directly
- **WHEN** a caller attempts to set a required step to passed without a valid receipt
- **THEN** SkillGuard rejects the transition and preserves the prior state

### Requirement: Runs resume from durable events
SkillGuard SHALL use append-only events and immutable receipts so a new process or context can reconstruct the same state and next ready steps without conversation memory.

#### Scenario: Context is lost mid-run
- **WHEN** a run is reopened after process or chat interruption
- **THEN** SkillGuard replays the recorded contract and events and does not infer unrecorded completion

### Requirement: Skip and loops fail closed
Required steps SHALL NOT be skippable; optional or conditional skips SHALL require condition evidence and a reason; every loop SHALL require progress and a finite bound.

#### Scenario: Repeated iteration has no progress delta
- **WHEN** a loop re-enters with unchanged declared progress
- **THEN** SkillGuard transitions to the declared blocked terminal instead of continuing
