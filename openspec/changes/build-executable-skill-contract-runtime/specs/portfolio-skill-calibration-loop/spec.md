## ADDED Requirements

### Requirement: Skills graduate one at a time from real outcomes
SkillGuard SHALL maintain an explicit optimization order and SHALL require each target skill to complete representative positive, invalid-input, recovery or resume, and out-of-scope user jobs plus native and artifact checks before graduation.

#### Scenario: Static contract passes but user outcome fails
- **WHEN** a target's compiled contract and static checks pass but its representative user job cannot reach a useful validated result
- **THEN** the target remains ungraduated and the failure is classified instead of being hidden by structural pass

### Requirement: Target failures feed Guard misses back to the owner
SkillGuard SHALL classify a post-green target failure and, when the failure exposes a Guard model, compiler, runtime, receipt, artifact, checker, or closure gap, SHALL preserve the old claim and observed failure, add an executable observed regression and same-class cases, repair the owning Guard boundary, and mark the old proof stale or overclaimed.

#### Scenario: Contract cannot execute a declared artifact check
- **WHEN** a target declares a valid artifact obligation but the SkillGuard runtime cannot execute or evaluate it
- **THEN** the episode is a SkillGuard runtime or validator miss, not a target success or a target-specific bypass

### Requirement: Guard changes invalidate affected prior graduates
Every SkillGuard change SHALL publish a compatibility fingerprint and affected feature tags and SHALL transition previously graduated skills that consume those features to `revalidation_required` until current evidence is restored.

#### Scenario: Receipt freshness semantics change
- **WHEN** SkillGuard changes receipt or closure semantics
- **THEN** every graduate that consumes those semantics loses current portfolio status and must be revalidated under the new fingerprint

### Requirement: Portfolio regression uses a TestMesh-backed hierarchy
SkillGuard SHALL run self-host and the current target, scan every prior graduate for contract/schema/freshness compatibility, rerun real representative jobs for affected graduates, and permit reuse only with a current proof-bound TestResultReuseTicket.

#### Scenario: Prior full result is outside the impact surface
- **WHEN** a prior graduate's source, contract, command, environment, coverage, and consumed Guard features remain unchanged and a current reuse ticket proves non-impact
- **THEN** the parent portfolio may consume the ticket without rerunning unrelated expensive evidence

#### Scenario: Core closure semantics change
- **WHEN** a Guard change affects route, receipt, schema, or closure meaning broadly
- **THEN** old result reuse is invalid and all affected graduates require real full reruns

### Requirement: Parent graduation preserves child truth
The Portfolio Graduation Gate SHALL consume a current full receipt or valid reuse ticket for the current target and every prior graduate and SHALL keep stale, revalidation-required, missing, failed, or blocked children visible.

#### Scenario: Current target passes but a prior target regresses
- **WHEN** the current target reaches functional closure but a prior graduate fails under the active Guard fingerprint
- **THEN** portfolio graduation is blocked until the prior target is repaired or the portfolio claim is explicitly narrowed
