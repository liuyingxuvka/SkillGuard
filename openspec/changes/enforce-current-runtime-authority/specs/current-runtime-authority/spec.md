## ADDED Requirements

### Requirement: Single current daily authority
SkillGuard SHALL resolve daily runtime authority as exactly `current` or `blocked`. `current` SHALL require the complete validated current contract-source, compiled-contract, and exact check-manifest trio plus a clean former-runtime residual scan. No old or migration shape SHALL provide a successful daily authority.

#### Scenario: Complete current trio
- **WHEN** the current trio, content-impact plan, hashes, and bindings all validate and no former runtime surface exists
- **THEN** the resolver SHALL return `current`

#### Scenario: Current trio is incomplete
- **WHEN** any current authority member is missing, stale, malformed, or identity-mismatched
- **THEN** the resolver SHALL return `blocked` and SHALL NOT inspect an old pair for alternate success

#### Scenario: Only old authority exists
- **WHEN** a target contains an old work contract and legacy manifest but no complete current trio
- **THEN** the target SHALL remain blocked until ordinary maintenance rewrites it directly to the current shape

### Requirement: No live retirement or conversion surface
Historical eligibility, completion, prior-chain receipts, their validators and schemas, and conversion or renewal commands MUST NOT remain in maintained or installed product surfaces. Version-control history MAY preserve what changed, but runtime authority, owner execution keys, installation projection, Portfolio impact, global routing, managed prompt, and full-validation admission SHALL have no retirement-history input.

#### Scenario: Current implementation changes
- **WHEN** a current implementation, model, schema, prompt, or contract input changes
- **THEN** only exact affected current components and owner receipts SHALL become stale; no retirement history SHALL exist to renew or broaden validation

#### Scenario: Former retirement artifact reappears
- **WHEN** a former eligibility, completion, or prior-chain retirement artifact appears in a maintained target
- **THEN** the target SHALL block as a former-runtime residual and SHALL NOT parse the artifact as authority or conversion input

### Requirement: Old lifecycle fields are not current contract fields
The current source and compiled contract SHALL reject `v1_runtime_authority` and `legacy_v1_authority`. No maintained runtime tool SHALL parse them as conversion input. Direct current maintenance SHALL write a source without either field.

#### Scenario: Old lifecycle field appears in current source
- **WHEN** a current source declares either old lifecycle field
- **THEN** compilation SHALL fail closed and SHALL NOT auto-convert it

### Requirement: Legacy runtime commands are rejection-only
Former legacy compile, route, run, conversion, retirement, and renewal commands MUST NOT appear in the public dispatcher or route index. Old command and record shapes MAY remain only in exact negative fixtures and MUST NOT execute or close work.

#### Scenario: Old command is invoked
- **WHEN** a caller invokes a former legacy compile/route/run command through the daily CLI
- **THEN** dispatch SHALL fail before any legacy handler, file write, or target process executes

#### Scenario: Old pass record is supplied
- **WHEN** an old pass record is presented beside missing or shallow current evidence
- **THEN** SkillGuard SHALL reject the record and SHALL NOT elevate the current status

### Requirement: Former runtime residuals block current authority
A target otherwise eligible for `current` MUST fail with `former_runtime_residual` when a former work contract, former manifest, flat old run record, retirement receipt, or prior-chain record reappears. Current run directories and unrelated stable protocols SHALL remain unaffected.

#### Scenario: Former work contract reappears
- **WHEN** `.skillguard/work-contract.json` exists beside a current trio
- **THEN** compiler, audit, installation, provenance, parity, and routing SHALL remain blocked without fallback

#### Scenario: Current run directory exists
- **WHEN** a current run directory contains its current snapshot, events, checks, receipts, and closure records
- **THEN** the residual scan SHALL preserve it and SHALL NOT classify it as an old flat run record

### Requirement: Current-only consumer parity
Project adoption, provenance, installation, installed parity, Portfolio, global discovery, and managed prompt projection SHALL consume the same current authority decision and exact content-impact projections.

#### Scenario: Isolated installed current root
- **WHEN** a current skill is copied to an isolated installed root containing only declared installation components and the current trio
- **THEN** applicable consumers SHALL pass without repository escape or historical retirement receipts

#### Scenario: Unconverted global-router member
- **WHEN** discovery finds a skill with no complete current trio
- **THEN** the registry MAY list the skill as blocked but SHALL expose no executable current route for it

### Requirement: Direct current replacement has no conversion route
An old target SHALL be repaired only by ordinary maintenance that writes the current source directly, regenerates the complete current trio through the one current compiler, and removes every named former surface. No runtime converter, retirement command, renewal command, or old-shape reader SHALL provide a second route. Until the current trio and residual scan pass together, daily authority SHALL remain blocked.

#### Scenario: Direct replacement is incomplete
- **WHEN** current compilation, residual cleanup, staging, or post-write validation is incomplete or fails
- **THEN** daily authority SHALL remain blocked and installation SHALL not activate the target

### Requirement: Maintenance has no refresh or upgrade route
Current maintenance SHALL accept complete explicit current inputs and write the current shape directly. `refresh-maintenance`, project-upgrade mode, and any command that reads a former or stale record to manufacture current authority MUST NOT exist in the daily dispatcher, route index, generated guidance, or installed surface.

#### Scenario: Former maintenance command is invoked
- **WHEN** a caller invokes maintenance refresh or project upgrade
- **THEN** dispatch SHALL reject the command before reading a former record, writing a current file, or executing a target owner

#### Scenario: Direct project adoption
- **WHEN** a caller supplies the complete explicit current contract, manifest, model, and target inputs
- **THEN** project adoption MAY write and validate the one current shape without deriving any field from prior target state

### Requirement: Functional freshness excludes execution output
Owner execution identity SHALL bind only the normalized behavioral check declaration and exact functional source components. Receipts, reports, logs, caches, timestamps, generated status, and result sidecars SHALL be downstream evidence stored outside maintained fixture source and SHALL NOT invalidate their own owner receipt.

#### Scenario: A check writes its receipt
- **WHEN** an owner check completes and writes immutable evidence under the governed evidence root
- **THEN** the owner execution key SHALL remain current if its functional inputs and declaration are unchanged

#### Scenario: Broad subtree selector includes evidence output
- **WHEN** a source component would include a report, receipt, log, cache, timestamp, generated status, or result sidecar
- **THEN** contract compilation or validation SHALL block the component instead of broadening owner invalidation

### Requirement: Native tests keep one owner and are never copied by consumers
SkillGuard SHALL optimize and govern the target skill's existing native validation path rather than create a parallel implementation of that validation. The frozen task-level plan SHALL assign each exact normalized command, functional input projection, evidence domain, and obligation set to exactly one primary execution owner. TestMesh and downstream skills SHALL carry only immutable receipt references and their own projection or aggregation identity; they MUST NOT copy, wrap, re-declare, or rerun the owner's command.

#### Scenario: Two skills request the same native test
- **WHEN** two selected skills require the same normalized native command over the same functional inputs and evidence domain
- **THEN** the task-level plan SHALL name one owner execution and SHALL make every other requirement a read-only receipt projection

#### Scenario: Consumer copies the owner command
- **WHEN** a receipt consumer or parent aggregation includes the owner's command, selectors, toolchain declaration, or an execution callback
- **THEN** pre-execution validation SHALL block the plan before any target process starts

#### Scenario: Target already owns a native test
- **WHEN** a covered target declares an existing native test path
- **THEN** SkillGuard SHALL reference that path and its owner identity and SHALL NOT create an equivalent SkillGuard-authored test implementation

### Requirement: Covered skill upgrades are current-only
Every SkillGuard-covered skill upgrade SHALL use direct current replacement and exact former-shape rejection fixtures. A fallback reader, compatibility reader, migration or upgrade command, converter, alias, renewal path, dual manifest, or parallel success authority MUST NOT be admitted for skill runtime maintenance. Ordinary software compatibility MAY exist only outside the skill runtime when an explicit requirement names the historical document/data/interface and FlowGuard records its bounded reader owner and claim boundary.

#### Scenario: Skill proposes a fallback for safety
- **WHEN** a skill change proposes keeping a former reader, alias, converter, or alternate success path without an external historical-data requirement
- **THEN** SkillGuard and DevelopmentProcessFlow SHALL block the change as a current-authority violation

#### Scenario: Ordinary software must read historical data
- **WHEN** a product requirement explicitly identifies historical data or an external interface that must remain readable
- **THEN** FlowGuard MAY admit a bounded compatibility branch with its own owner, accepted/rejected cases, and claim boundary without creating a SkillGuard runtime fallback

### Requirement: Current-authority claim boundary
Current-authority evidence SHALL prove only contract authority, exact residual absence, and named consumer parity. It SHALL NOT prove target-domain correctness, future AI behavior, package publication, release readiness, or project-level simulation accuracy.

#### Scenario: Current authority passes without target execution
- **WHEN** the current trio passes but no current target-domain receipt exists
- **THEN** SkillGuard MAY report current contract authority and SHALL NOT report functional execution-depth success
