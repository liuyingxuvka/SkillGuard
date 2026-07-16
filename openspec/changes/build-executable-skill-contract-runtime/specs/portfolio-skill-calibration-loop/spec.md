## ADDED Requirements

### Requirement: Skills graduate one at a time from real outcomes
SkillGuard SHALL maintain an explicit optimization order and SHALL require each target skill to complete representative positive, invalid-input, recovery or resume, and out-of-scope user jobs plus native and artifact checks before graduation.

#### Scenario: Static contract passes but user outcome fails
- **WHEN** a target's compiled contract and static checks pass but its representative user job cannot reach a useful validated result
- **THEN** the target remains ungraduated and the failure is classified instead of being hidden by structural pass

### Requirement: Superseded skills leave the active portfolio authority
When the user confirms that one maintained skill replaces one or more prior skills, SkillGuard SHALL keep exactly the replacement skill active, SHALL record every replaced skill as retired and superseded by that active skill, and SHALL bind each replaced skill to absent installation authority and blocked router authority. An explicitly excluded target SHALL remain excluded and SHALL NOT enter the active optimization order merely because adjacent skills were merged.

#### Scenario: Logic Writing replaces the two former writing skills
- **WHEN** `logic-writing` replaces `research-investigation-workflow` and `academic-thesis-revision-workflow`
- **THEN** `logic-writing` is the only active target among the three, both former targets are retired with `superseded_by_skill_id: logic-writing`, `installation_disposition: absent`, and `router_authority: blocked`, and `databank-workflow` remains excluded

#### Scenario: A retired skill points to an inactive replacement
- **WHEN** a scope marks a skill as superseded but the named replacement is missing, non-active, or the same skill
- **THEN** scope validation blocks before registry projection, installation, routing, or target execution

### Requirement: Current portfolio registry is a direct scope replacement
When an approved current scope supersedes a stale portfolio registry, SkillGuard SHALL construct revision one directly from the exact hash-valid scope and current Guard identity. The builder SHALL NOT consume a prior registry, migration input, compatibility reader, fallback, historical graduation receipt, or reuse ticket. A file output SHALL acquire the sole current portfolio-registry writer lock before construction and commit. Active targets SHALL remain pending or revalidation-required until fresh evidence is produced; excluded, supporting, and superseded lifecycle entries SHALL be projected exactly from the scope.

#### Scenario: Reviewed scope replaces a stale registry
- **WHEN** the current reviewed scope includes active `logic-writing`, excluded `databank-workflow`, and the two former writing skills as superseded by `logic-writing`
- **THEN** the direct builder emits revision one with no previous-registry or transaction authority, keeps every active target non-current, preserves DataBank exclusion, and projects complete retirement/install/router tuples for both former writing skills

#### Scenario: A caller supplies a prior registry
- **WHEN** a caller attempts to pass an old registry to the direct builder
- **THEN** the command rejects the argument instead of reading, migrating, or reusing the old authority

#### Scenario: A live registry writer owns the output
- **WHEN** impact, reuse, graduation, or another direct replacement holds the current registry writer lock
- **THEN** the builder blocks without reading a prior registry or changing the output, and the live writer remains the sole mutation owner

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
