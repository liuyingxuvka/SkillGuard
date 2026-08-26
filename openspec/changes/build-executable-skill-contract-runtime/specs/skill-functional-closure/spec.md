## ADDED Requirements

### Requirement: Closure profiles are monotonic
SkillGuard SHALL provide routine, functional, release, and highest-quality profiles whose requirements increase monotonically and never hide a failure visible at a weaker profile.

#### Scenario: Functional passes but release execution is missing
- **WHEN** functional evidence is current but release-only evidence has not run
- **THEN** functional may pass while release remains not-run or blocked with the missing evidence named

### Requirement: Profile-specific terminal self-host evidence is mandatory
SkillGuard SHALL evaluate each closure profile against its own terminal evidence
floor. A functional claim SHALL consume the current source, FlowGuard model
export, compiled contract, check manifest, target-owned surface inventory, and
one current full TestMesh aggregation for the self-host maintenance unit, with
current immutable terminal-success receipts for every required lifecycle stage.
Functional positive-path evidence SHALL be `simulated_e2e` or stronger, and the
target-declared failure, recovery, non-goal, and terminal evidence SHALL be
current. For this change, the acceptance boundary is the registered SkillGuard
source and repository-controlled fixtures only; external pilot/adoption work
and mutation of another repository are not prerequisites and require a
separate explicit change. A release claim SHALL additionally require `real_e2e` or stronger
evidence for every required lifecycle stage, deterministic quality evidence,
the canonical `.skillguard/self-host/current` terminal receipt bound to current
source/contract/manifest/owner-plan identities, clean-install smoke,
source/installed projection parity, post-install full self-host verification,
and current Windows/Linux CI terminal receipts. Highest-quality SHALL add
current human or domain-expert evidence for every declared quality requirement.
Structural checks, fixtures, progress logs, workflow declarations, local
router/install receipts, and aggregation-only records cannot substitute for
these terminal receipts.

#### Scenario: Functional self-host is current but release is not
- **WHEN** all functional stages have current terminal receipts and the full
  TestMesh aggregation is current, but one or more release stages lack
  `real_e2e`, deterministic quality, or canonical self-host release evidence
- **THEN** the functional claim may pass while release remains blocked with each
  missing identity or evidence subject named

#### Scenario: Canonical self-host receipt is absent
- **WHEN** `check-depth`, the functional closure, installation smoke, or router
  refresh passes but `.skillguard/self-host/current` is absent, stale, foreign,
  or non-terminal
- **THEN** release and higher profiles remain blocked; no weaker receipt or
  former authority is promoted to release evidence

#### Scenario: CI workflow is declared without current receipts
- **WHEN** the repository declares Windows/Linux CI jobs but no current terminal
  receipts exist for the required matrix
- **THEN** the CI/release claim remains `not_run` or blocked and the workflow
  declaration is reported only as plan/configuration evidence

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

### Requirement: Functional closure has a bidirectional surface denominator
SkillGuard SHALL require each maintained target to provide a current,
target-owned inventory of its observed executable surfaces, including public
commands, entry scripts, exports, routes, action surfaces, artifacts, and
failure/recovery boundaries that are applicable to that target. Every discovered
row SHALL have exactly one typed disposition and an explicit current intent,
contract path, native check, execution owner, and evidence projection, or the
target SHALL remain blocked. SkillGuard validates the declaration and its
identity; it does not invent domain intent or silently classify an unbound row
as internal or not applicable.

#### Scenario: A new command is added without a surface row
- **WHEN** the target source exposes a new public command but the current
  surface inventory and contract do not contain a matching row
- **THEN** reverse-closure validation fails before execution or graduation and
  names the missing row; no declaration-only smoke result can close it

#### Scenario: A historical requirement is superseded
- **WHEN** an old requirement is no longer part of the current product intent
- **THEN** the target records its provenance and an explicit superseded,
  retired, rejected, or not-applicable disposition with current rationale; the
  old requirement is not automatically inherited as current authority

#### Scenario: Current identity no longer matches
- **WHEN** a model, contract, manifest, receipt, or installation identity does
  not match the current source and schema
- **THEN** SkillGuard reports a visible currentness blocker and requires a
  direct manual rewrite plus fresh validation; it rejects the former artifact
  and never uses an alias, alternate reader, or alternate success authority

### Requirement: This change is the sole current closure authority
The current executable-contract change SHALL own functional, release,
highest-quality, self-host, and CI closure semantics. The archived
`add-skill-functional-closure-audit` change is provenance-only and SHALL NOT be
read as a second schema, command, receipt, or acceptance authority. The
evidence-lifecycle change may own storage/lifecycle semantics but SHALL NOT
create a competing closure or release claim. Former closure or receipt
identities are direct-current rewrite blockers only; no compatibility reader,
fallback, migration command, converter, alias, dual manifest, or alternate
success authority is permitted.

#### Scenario: The observed surface denominator is empty or re-sealed after row removal
- **WHEN** a target declares an empty `observed_surface_ids` list, or removes a
  row and recomputes the inventory fingerprint without updating the real source
  denominator
- **THEN** reverse-closure validation emits
  `surface_inventory_observed_denominator_missing` or
  `surface_observed_denominator_mismatch` and remains blocked

#### Scenario: Surface owner identity is unknown, duplicated, or missing
- **WHEN** the target owner registry is absent or contains duplicate ids, or a
  discovered row names an unknown, sentinel, or missing `owner_id`
- **THEN** validation emits a stable owner blocker
  (`surface_owner_registry_missing`, `surface_owner_id_duplicate`,
  `surface_row_owner_unknown`, or `surface_row_missing_owner`) and a resealed
  inventory cannot make the row current

#### Scenario: Malformed command or route identity cannot collapse the denominator
- **WHEN** a current command or route entry has a missing identity, duplicate
  public name, duplicate dispatch function, duplicate route id, or duplicate
  command family
- **THEN** reverse-closure validation emits a stable malformed-entry or
  duplicate finding and does not discard the entry while calculating the
  denominator

#### Scenario: Adequacy and model deepening are mandatory depth gates
- **WHEN** a target depth profile omits its surface inventory, declares no
  native adequacy check, or binds a different/non-native model-deepening check
- **THEN** depth and graduation remain blocked with a visible declaration finding
  even when generic contract or smoke checks are current
