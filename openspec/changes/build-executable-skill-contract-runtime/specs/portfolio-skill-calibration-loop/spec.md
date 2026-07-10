## ADDED Requirements

### Requirement: Skills graduate one at a time from real outcomes
SkillGuard SHALL maintain an explicit optimization order and SHALL require each target skill to complete representative positive, invalid-input, recovery or resume, and out-of-scope user jobs plus native and artifact checks before graduation.

Each active target SHALL declare whether its capability inventory is pending or current. Graduation SHALL require a non-empty current inventory, representative jobs that name the capabilities and direct evidence they cover, and a deterministic coverage fingerprint in the full-run receipt. A non-empty job list alone is not sufficient.

#### Scenario: Static contract passes but user outcome fails
- **WHEN** a target's compiled contract and static checks pass but its representative user job cannot reach a useful validated result
- **THEN** the target remains ungraduated and the failure is classified instead of being hidden by structural pass

#### Scenario: Pressure-test baseline covers only selected routes
- **WHEN** an external pilot proves selected routes but not every representative function required for target graduation
- **THEN** the target remains `baseline` and blocks later ordered graduation until the missing representative jobs are current

#### Scenario: One job leaves a declared capability uncovered
- **WHEN** a multi-capability target has a valid full-run receipt but its receipt-bound representative jobs omit one declared capability or route
- **THEN** graduation blocks with the missing capability ids and the target remains non-current

### Requirement: Portfolio lifecycle is explicit and private
SkillGuard SHALL keep the operational portfolio registry private when it contains local source locations or private repository metadata and SHALL distinguish active owned/adopted targets, pending adoption, excluded private/system skills, retired private skills, and supporting repositories.

#### Scenario: User excludes a private skill
- **WHEN** the user explicitly excludes a private skill such as the database-design workflow
- **THEN** the registry records `order: null`, an excluded lifecycle/status, and a reason; the skill neither enters nor blocks the active graduation queue

#### Scenario: Repository only supports a parent skill
- **WHEN** a repository is data or provider state consumed through a parent target rather than a standalone skill
- **THEN** it is recorded as a supporting repository with a parent id and is validated through that parent instead of being falsely graduated alone

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

#### Scenario: Guard change is broad but target source is unchanged
- **WHEN** a broad Guard semantic change occurs while a prior target's own files remain unchanged
- **THEN** old green status still becomes `revalidation_required`; unchanged target source alone cannot authorize result reuse

### Requirement: Portfolio regression uses a TestMesh-backed hierarchy
SkillGuard SHALL run self-host and the current target, scan every prior graduate for contract/schema/freshness compatibility, rerun real representative jobs for affected graduates, and permit reuse only with a current proof-bound TestResultReuseTicket.

#### Scenario: Prior full result is outside the impact surface
- **WHEN** a prior graduate's source, contract, command, environment, coverage, and consumed Guard features remain unchanged and a current reuse ticket proves non-impact
- **THEN** the parent portfolio may consume the ticket without rerunning unrelated expensive evidence

#### Scenario: Reuse request names an unregistered Guard change
- **WHEN** a reuse request supplies matching hashes but the named before/after change is absent from the registry's append-only Guard change history
- **THEN** the reuse ticket is rejected and cannot restore current status

#### Scenario: Core closure semantics change
- **WHEN** a Guard change affects route, receipt, schema, or closure meaning broadly
- **THEN** old result reuse is invalid and all affected graduates require real full reruns

### Requirement: Parent graduation preserves child truth
The Portfolio Graduation Gate SHALL consume a current full receipt or valid reuse ticket for the current target and every prior graduate and SHALL keep stale, revalidation-required, missing, failed, or blocked children visible.

#### Scenario: Current target passes but a prior target regresses
- **WHEN** the current target reaches functional closure but a prior graduate fails under the active Guard fingerprint
- **THEN** portfolio graduation is blocked until the prior target is repaired or the portfolio claim is explicitly narrowed

### Requirement: Portfolio registry mutations preserve one-writer truth
SkillGuard SHALL serialize every registry-changing impact, reuse, and graduation command. A live writer SHALL block a second writer; an abandoned local writer lock SHALL be recoverable; output ticket or receipt artifacts SHALL be written before the registry begins referencing them.

#### Scenario: Two live AIs update the same registry state
- **WHEN** one process owns the portfolio registry writer lock and a second process requests a mutation
- **THEN** the second mutation terminates blocked without changing the registry or publishing a success receipt
