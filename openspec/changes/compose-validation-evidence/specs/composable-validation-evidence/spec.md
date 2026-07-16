## ADDED Requirements

### Requirement: Ordered validation ownership
SkillGuard SHALL execute validation as an ordered ownership graph in which cheap authority, generated-contract, manifest, artifact-boundary, and freshness blockers run before expensive suites, and each validation node declares exactly one owner and one evidence domain.

#### Scenario: Cheap preflight fails
- **WHEN** runtime authority, generated contract, manifest, artifact boundary, or source inventory is invalid
- **THEN** SkillGuard SHALL block before launching expensive TestMesh children and SHALL preserve later children as explicitly not run

#### Scenario: Two wrappers name the same command
- **WHEN** a verification plan would execute the same normalized command and evidence obligation through two different wrapper labels
- **THEN** SkillGuard SHALL require one primary execution owner and SHALL make the other consumer use its current receipt or declare a distinct obligation

### Requirement: Complete content-addressed child inputs
Every TestMesh child SHALL bind a deterministic inventory of every regular file under its declared source paths, including non-Python schemas, fixtures, models, contracts, prompts, configuration, and documentation inputs, excluding only paths classified as runtime artifacts by the shared portable-artifact policy.

#### Scenario: JSON fixture changes
- **WHEN** a declared JSON fixture changes after a child passes
- **THEN** the child source-inventory hash SHALL change and previous child evidence SHALL be stale

#### Scenario: Declared path is missing
- **WHEN** a declared source path is missing, unreadable, escapes the repository, or resolves through an unsafe link
- **THEN** inventory preflight SHALL block before child execution

### Requirement: Proof-bound TestMesh child reuse
SkillGuard SHALL permit reattachment of a prior TestMesh child only through an immutable current reuse ticket bound to the direct child result, manifest, source and target profile declarations, suite declaration, normalized command, complete source inventory, artifact-policy version, environment, verifier/runtime, owned coverage, required coverage, result hash, and result locator.

#### Scenario: Focused child is current for full parent
- **WHEN** a directly executed focused-profile child passed with zero skips and every bound identity exactly matches the current full-profile suite requirement
- **THEN** SkillGuard MAY create a new full-parent child projection with `proof_kind` equal to `reused_current_child` and SHALL still evaluate the full parent's complete required coverage

#### Scenario: Whole focused parent is supplied
- **WHEN** a focused parent result is supplied as if it proved full-profile closure
- **THEN** SkillGuard SHALL reject parent-level reuse even if one or more child commands are identical

### Requirement: Reuse fails closed
SkillGuard MUST reject failed, skipped, timed-out, cancelled, not-run, partial, progress-only, output-truncated, mutable, foreign, stale, chained-reuse, or identity-mismatched child evidence.

#### Scenario: One non-Python input differs
- **WHEN** command and Python files are unchanged but any inventoried schema, fixture, model, contract, prompt, configuration, or documentation input differs
- **THEN** reuse SHALL be rejected and the affected child SHALL execute normally

#### Scenario: Result bytes are tampered
- **WHEN** a child result's current bytes, recorded hash, or resolved locator do not agree
- **THEN** reuse SHALL be rejected with a tamper or identity finding and SHALL NOT count as passing evidence

#### Scenario: Reused child is offered as source proof
- **WHEN** the proposed source child itself has `proof_kind` equal to `reused_current_child`
- **THEN** SkillGuard SHALL reject the chain and require the direct terminal child result

### Requirement: Parent reattachment preserves claim boundaries
A TestMesh parent SHALL pass only when every selected child is directly passed or accepted through an exact current owner receipt and every current required partition is owned; the parent SHALL retain its own profile, timeout, coverage, and claim-boundary identity. A `full` parent SHALL use the single current TestMesh result schema and bind exactly one current installation identity plus exactly one separately typed current `global_prompt` registry/managed-prompt identity.

#### Scenario: Reusable child covers only part of full profile
- **WHEN** one child is reusable but another full-profile child is absent or stale
- **THEN** SkillGuard SHALL reuse only the current child, SHALL execute or block the affected child, and SHALL NOT issue full-parent closure early

#### Scenario: Earlier child fails
- **WHEN** an earlier child fails and later children are not launched
- **THEN** the parent SHALL record the later children as not run and SHALL fail rather than hiding them

#### Scenario: Full parent lacks prompt currentness
- **WHEN** all selected children pass but the full parent omits, duplicates, or stales the separately typed global-router prompt binding
- **THEN** full-parent closure and receipt replay SHALL block even when the installation identity remains current

### Requirement: Evidence domains remain distinct
Source, staged-install, active-installation, synchronized-target, and global-prompt evidence SHALL remain separate domains, and a receipt from one domain MUST NOT satisfy another domain's obligation.

#### Scenario: Source TestMesh passed
- **WHEN** canonical-source TestMesh evidence is current but staged installation has not been checked
- **THEN** staged-install parity and smoke status SHALL remain not run rather than inherit the source pass

### Requirement: Verification outputs cannot become freshness inputs
SkillGuard-maintained OpenSpec verification-contract review SHALL resolve the report path and declared result/receipt roots against all freshness inputs. It SHALL reject any direct, globbed, normalized, link-equivalent, runtime-control, or source/evidence-root collision before executing checks. Reports, receipts, results, progress logs, reuse records, and other runtime evidence SHALL be replayed by their owner/consumer contract and SHALL NOT become source freshness inputs.

#### Scenario: Report is included through a glob
- **WHEN** `verification-report.json` is generated inside a directory matched by a declared freshness glob
- **THEN** verification SHALL block before checks run with `verification_report_in_freshness_watch`

#### Scenario: Report is outside all watched inputs
- **WHEN** the report path is not part of any resolved freshness input and all other contract rules pass
- **THEN** the self-watch rule SHALL allow verification to proceed

#### Scenario: Receipt or progress output is watched as source
- **WHEN** a freshness entry overlaps a declared receipt/result root, `work/verification`, `.sg-runtime`, a runtime `.skillguard` control path, or an ambiguous `.skillguard` JSON glob
- **THEN** verification SHALL block before checks run with `verification_evidence_output_in_freshness_watch`

#### Scenario: Evidence is consumed without becoming source
- **WHEN** an exact current parent receipt is supplied to the read-only consumer and no evidence-output path appears in freshness inputs
- **THEN** the consumer SHALL replay the receipt currentness without refreshing source identity or invoking its owner

### Requirement: Current proof replay
SkillGuard SHALL replay a composed parent by resolving every child result and reuse ticket, recomputing all current identities, and verifying the current manifest, policy, profile, suite, environment, coverage, result, and evidence-domain bindings.

#### Scenario: Manifest changes after composition
- **WHEN** the TestMesh manifest changes after a composed parent is written
- **THEN** replay SHALL classify the parent as stale even when all referenced result files still exist

### Requirement: Exact single-flight check execution
SkillGuard SHALL keep `semantic_check_id`, concrete `execution_id`, and content-addressed `execution_key` distinct. Only a complete terminal-success execution may write the reusable success head; failed attempts remain auditable but MUST NOT satisfy or poison reuse. Source-authority changes MUST stale reuse, while runtime output changes MUST NOT rewrite source authority.

#### Scenario: The same exact check is requested twice
- **WHEN** contract, manifest, step, target inputs, source authority, command, and environment still produce the same execution key and the first execution has a current terminal-success receipt
- **THEN** the second supervisor or self-host consumer SHALL return that exact success receipt without starting another process

#### Scenario: A failed attempt exists
- **WHEN** the prior attempt failed, timed out, or stopped before terminal success
- **THEN** it SHALL remain a failed attempt record and the next request SHALL execute rather than hit a success head

### Requirement: Full-parent receipt consumers are read-only
Any OpenSpec or downstream full-TestMesh verification layer SHALL consume exactly one immutable current parent receipt in fail-closed read-only mode. It MUST NOT invoke TestMesh execution, `--resume`, repair, backfill, or owner fallback.

#### Scenario: Parent receipt is incomplete or stale
- **WHEN** the supplied parent receipt is missing, partial, stale, foreign, tampered, or identity-incomplete
- **THEN** the consumer SHALL report a blocker and SHALL launch zero TestMesh children

### Requirement: Validation execution ownership is explicit and frozen
SkillGuard SHALL project one canonical validation-execution policy into maintained project and global prompts. Before multi-skill validation, the policy SHALL require one frozen task-level plan in the existing verification contract or TestMesh that lists every exact check, covered obligation and evidence domain, dependency order, persistent receipt root, and exactly one primary execution owner. Before execution, consumers SHALL resolve the exact owner receipt from frozen execution identity and inputs; only a current immutable terminal-success receipt is reusable, and a consumer MUST NOT carry or rerun the owner's command. Maintained test, code, contract, configuration, toolchain, and policy changes SHALL invalidate only affected receipts, while reports, receipts, progress logs, and runtime outputs MUST NOT refresh source authority or trigger their own validation. The policy SHALL also state that `--resume` is an execution command rather than receipt audit, full validation starts only after source and toolchain identities are frozen under exactly one explicit owner, interrupted launchers require confirmed zero descendant processes before evidence or another owner is admitted, and Windows Scheduled Tasks, background resume, or unattended retry MUST NOT run full validation or resume a mutable worktree.

#### Scenario: Multi-skill validation has no exact owner plan
- **WHEN** validation would start without an exact owner, dependency order, evidence domain, or persistent receipt root for every listed check
- **THEN** validation SHALL block before execution rather than let each skill independently launch overlapping tests

#### Scenario: A consumer finds a current owner receipt
- **WHEN** the owner receipt is immutable terminal success and its complete frozen execution identity and inputs remain current
- **THEN** the consumer SHALL verify and project that receipt and SHALL launch zero copies of the owner command

#### Scenario: Writing evidence would refresh source authority
- **WHEN** a report, receipt, progress log, or other runtime output is produced
- **THEN** that output SHALL remain outside source authority and SHALL NOT invalidate or retrigger the check that produced it

#### Scenario: Resume is proposed as receipt audit
- **WHEN** a downstream verifier needs to inspect an existing full-parent receipt
- **THEN** it SHALL use the read-only receipt consumer and SHALL NOT invoke `--resume`

#### Scenario: Full validation inputs or owner are not fixed
- **WHEN** source or toolchain identity is still mutable, or more than one execution owner can launch the full parent
- **THEN** full validation SHALL remain not run and its output SHALL NOT enter evidence

#### Scenario: An interrupted launcher may still have descendants
- **WHEN** timeout, cancellation, or interruption occurs and descendant process count has not been confirmed as zero
- **THEN** the result SHALL be `cleanup-unconfirmed`, invalid, non-reusable, and no next owner SHALL start

#### Scenario: Unattended mutable-worktree retry is proposed
- **WHEN** a Windows Scheduled Task, background resume, or unattended retry would run full validation or resume mutable inputs
- **THEN** the execution SHALL be prohibited by the maintained process policy

### Requirement: Component-scoped impact graph is authoritative
SkillGuard SHALL compile one deterministic content-impact graph from the complete maintained inventory, shared portable-content policy, exact check input selectors, dependency owners, projection consumers, and reviewed role overrides. The generated graph SHALL be embedded in the existing compiled contract and check manifest and SHALL be the only authority for deciding which validation, installation, Portfolio, and router consumers are affected.

#### Scenario: One test fixture changes
- **WHEN** a file changes whose component is consumed by one fixture owner and no shared runtime owner
- **THEN** the impact plan SHALL stale only that owner and its downstream aggregation projections and SHALL NOT admit a whole TestMesh execution

#### Scenario: A maintained file is not mapped
- **WHEN** an inventoried path has no semantic role, installation disposition, or exact consumer
- **THEN** compilation SHALL block with an unmapped or ambiguous-path finding before any validation process starts and SHALL NOT fall back to run-all

#### Scenario: Owner dependencies cycle
- **WHEN** exact owner dependencies form a cycle or one check has more than one primary execution owner
- **THEN** impact planning SHALL block before receipt lookup or execution

### Requirement: Owner input projection controls freshness
Every execution owner SHALL bind a stable owner id, the complete normalized behavior declaration, exact input component ids and hashes, exact dependency receipt hashes, target inputs, command/toolchain, environment/verifier, evidence domain, and impact-policy version. A change outside that projection MUST NOT stale the owner.

#### Scenario: Parent profile changes without child input change
- **WHEN** a parent profile, parent manifest presentation, task checkbox, report, or aggregation declaration changes while an owner's declaration and input projection remain byte-identical
- **THEN** only the parent projection or aggregation identity SHALL become stale and the owner process SHALL NOT run again

#### Scenario: An unrecognized check field appears
- **WHEN** a check declaration includes an unknown behavior-bearing field that is not explicitly classified as display/generated metadata
- **THEN** compilation SHALL fail closed rather than omit the field from owner identity

### Requirement: Terminal owner receipts survive individual runs
SkillGuard SHALL publish only terminal-success owner receipts to a declared persistent content-addressed evidence root. The receipt SHALL bind the exact owner execution key plus independently recomputable stdout, stderr, result, and termination sidecars. Run-local check records SHALL be projections of that owner receipt; failed, timed-out, cancelled, or cleanup-unconfirmed attempts SHALL never create a reusable success index.

#### Scenario: A new task run requests the same owner
- **WHEN** a different run id and step id request an owner whose complete semantic execution identity and sidecars remain current
- **THEN** SkillGuard SHALL project the exact existing owner receipt into the new run and SHALL start zero owner processes

#### Scenario: A content-addressed sidecar is missing or tampered
- **WHEN** any stdout, stderr, result, or termination sidecar cannot be independently rehashed to the receipt's declared address
- **THEN** the receipt SHALL be stale and unavailable and SHALL NOT authorize reuse or parent closure

### Requirement: Impact planning is read-only and frozen
SkillGuard SHALL expose a side-effect-free impact-plan preview that reports changed components, reusable owners, owners that would execute, aggregation-only work, installation components, router refresh, Portfolio targets, derived full-admission reasons, and a plan hash. Any execution SHALL consume the same frozen plan hash.

#### Scenario: Planning finds only aggregation drift
- **WHEN** all owner receipts remain exact and only a parent projection changed
- **THEN** `will_execute_owner_ids` SHALL be empty, `will_aggregate_only` SHALL be true, and execution SHALL issue no child process

#### Scenario: Inputs drift after planning
- **WHEN** any governed component, owner declaration, dependency receipt, toolchain, or policy changes after plan generation
- **THEN** execution SHALL reject the stale plan and require a new preview rather than silently expand work

### Requirement: Full validation requires a derived admission reason
SkillGuard SHALL admit full validation only after source and toolchain freeze under one execution owner and only for an explicit final/release gate, an impact compiler or policy change, a shared verifier/runtime core consumed by every owner, or an explicitly modeled all-owner component.

#### Scenario: Installation happened
- **WHEN** the only new fact is that an affected component was installed and its exact parity/smoke projection is current
- **THEN** installation SHALL NOT by itself admit full validation

#### Scenario: The agent is uncertain about scope
- **WHEN** the impact graph is incomplete or the agent cannot determine an owner
- **THEN** validation SHALL block for graph repair and SHALL NOT use full as an uncertainty fallback

### Requirement: Installation, Portfolio, and routing consume graph projections
The staged installer, installed parity, Portfolio impact, global-router refresh, and managed prompt installation SHALL consume their exact projections from the same frozen impact graph. Ordinary target-skill use MUST NOT invoke SkillGuard; non-trivial skill maintenance, installation, migration, or release SHALL enter SkillGuard supervision and validate only affected owners.

#### Scenario: Test-only source changes
- **WHEN** changed components have `source_only` installation disposition and no router or Portfolio edge
- **THEN** installation, router refresh, and Portfolio target invalidation SHALL remain not required

#### Scenario: Managed route entrypoint changes
- **WHEN** a prompt/router component changes
- **THEN** the router projection SHALL require refresh while unrelated runtime and Portfolio owners remain reusable

### Requirement: Daily runtime accepts one current shape
SkillGuard SHALL use one current contract, impact-plan, receipt, and TestMesh path. Retired V1 runtime artifacts and suites MAY remain only as exact negative fixtures and MUST NOT execute as daily validation, be auto-converted, or provide fallback success.

#### Scenario: Old receipt shape is supplied
- **WHEN** a historical receipt or manifest lacks the current impact-plan and owner-projection identity
- **THEN** the current parser SHALL reject it as stale or unsupported and SHALL NOT translate it into passing evidence
### Requirement: Single-skill activation is projection-exact and transaction-isolated
SkillGuard SHALL provide one explicit single-skill staged installation route for maintained targets. It SHALL copy only the frozen `projection:installation`, validate the compiled `member_root_path`, activate only `CODEX_HOME/skills/<validated-skill-id>`, and keep a per-target transaction, HEAD, receipt, backup, rollback, and recovery chain separate from the SkillGuard self-install transaction domain. The installer SHALL NOT discover or execute arbitrary target commands.

#### Scenario: A maintained target is installed for the first time
- **WHEN** the canonical target, isolated stage, and exact installation projection are current and the active target is absent
- **THEN** SkillGuard SHALL activate the exact stage, write one per-target committed receipt and HEAD, and leave the SkillGuard self-install HEAD unchanged

#### Scenario: Post-activation parity fails
- **WHEN** the active target does not reproduce the frozen canonical installation projection after activation
- **THEN** SkillGuard SHALL roll back to the exact prior active tree, retain a durable blocked transaction record, and SHALL NOT report the new target as current

#### Scenario: Source-only content exists
- **WHEN** the maintained target contains tests, examples, models, notes, or other files classified `source_only`
- **THEN** stage and active target inventories SHALL exclude those files and SHALL block on any unexpected projected member rather than silently retaining it

#### Scenario: Target commands are present
- **WHEN** a target repository declares native checks or contains executable scripts
- **THEN** the installation transaction SHALL perform only projection, parity, authority, and filesystem-safety work; native execution SHALL require a separately frozen owner/check receipt
