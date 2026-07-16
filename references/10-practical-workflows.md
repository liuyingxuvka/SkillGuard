# Reference 10: Practical Workflows

This reference explains the practical SkillGuard workflow modes: create, audit, repair, suite, and closure. Each mode has its own entry conditions, evidence needs, hard gates, expected outputs, blockers, skipped-check handling, residual risk, and claim boundary.

These workflows are guidance for future SkillGuard use. They do not claim that scripts, workflow automation, schemas, fixture files, tests, CLI checks, suite automation, package publication, code-contract checks, git commits, hosted releases, or external integrations are already present.

## Workflow Selection

Choose a workflow mode before doing detailed work.

Use:

- create workflow when a new skill or maintained skill target is being prepared;
- audit workflow when existing skill materials need review;
- repair workflow when a failed or blocked skill needs correction;
- suite workflow when multiple skills or a suite contract are in scope;
- closure workflow when deciding whether a checked result can be accepted, failed, or blocked.

Pass criteria: the selected workflow matches the task and target.

Fail criteria: the selected workflow omits required checks for the task.

Block criteria: the task could materially follow multiple modes and no safe default exists.

## Native Integration Selection

Before compiling or accepting a runtime contract, decide whether the target skill already has native routing or checking.

Use:

- `native-integrated` when the original skill already owns route selection, controller state, validation checks, and closure semantics;
- `hybrid-extension` when the original skill owns part of the path but needs SkillGuard to add missing gates;
- `skillguard-runtime` only when no native runtime path exists.

Pass criteria: SkillGuard either binds the original route/check system or clearly owns the runtime because no native system is present.

Fail criteria: SkillGuard adds a second execution route beside an existing native system, or reports maintenance evidence while the native route/check contract remains unbound.

Block criteria: the native owner cannot be identified and the choice would change who controls work execution.

## End-To-End Operating Route

A practical SkillGuard workflow should move through the same visible route even when the mode changes:

1. Intake: name the target, workflow mode, scope, owner boundary, and public claim boundary.
2. Inventory: list relevant files, identify the target skill when a skill is in scope, identify any native route/check owner before adding SkillGuard runtime material, note whether a skill map or suite map is part of the evidence, and explicitly name absent scripts, fixtures, tests, CLI checks, suite automation, package publication, and code-contract checks when those categories matter.
3. Deterministic evidence: inspect current files, parse metadata where applicable, collect hashes or line counts when useful, and run only checks that actually exist.
4. Judgment: use structured human or AI judgment for semantic questions after deterministic evidence is clear.
5. Repair or blocker handling: fix owned failures, preserve unrelated work, and keep unresolved blockers visible.
6. Closure: decide pass, fail, or block for the stated scope with skipped checks, residual risk, and a claim boundary.

Pass criteria: the route connects intake, evidence, judgment, and closure without hiding missing artifacts.

Fail criteria: the route jumps from intake to acceptance without current evidence or judgment where required.

Block criteria: the target, scope, or required evidence cannot be determined.

## External Target Binding

For `check-contract` and `check-skill`, an external target has exactly two declared path roles: one canonical `--repository-root` and one `--target` member contained inside it. Repository-relative models, checks, implementation paths, and references resolve only from the canonical root. If the member escapes, the repository is missing, or binding fails, stop visibly; do not retry from the member directory, SkillGuard repository, or current working directory. The former `check-contract --target-root` spelling is removed rather than preserved as an alias. A standalone skill is the one bounded exception: from its own directory, `--target .` binds that directory as both repository and member and projects `member_root_path` as `.`.

## Create Workflow

Create workflow prepares a new skill or maintained target.

Entry conditions:

- target name or path is known;
- intended activation scope is known;
- public repository or maintained target boundary is known;
- overwrite conflicts have been inspected.

Required evidence:

- target directory listing;
- existing-file preservation record;
- intended `SKILL.md` contract;
- README or public usage plan when in scope;
- metadata and version plan when in scope;
- initial validation expectations.

Hard gates:

- do not overwrite existing user or peer work silently;
- frontmatter and required sections must be present for a skill contract;
- public files must be private-safe;
- unimplemented scripts, schemas, fixtures, tests, CLI checks, suite automation, checkers, package publication, or code-contract checks must not be claimed complete.

Expected output:

- created files;
- evidence collected;
- checks completed;
- skipped checks with reasons;
- blockers and residual risk;
- claim boundary for what was actually created.

## Audit Workflow

Audit workflow reviews an existing skill or repository without assuming ownership of broad edits.

Entry conditions:

- target files exist or the missing target is itself the finding;
- audit scope is known;
- review can inspect current files.

Required evidence:

- current file listing;
- current content inspection;
- parser output where applicable;
- heading inventories for documentation contracts;
- status and evidence records;
- public-safety scan;
- prior evidence freshness review.

Hard gates:

- stale evidence cannot support current acceptance;
- report-only evidence is not enough where direct evidence is required;
- skipped required checks must be visible;
- AI judgment cannot replace deterministic checks.

Expected output:

- pass, fail, or block decision;
- findings grouped by severity or gate;
- evidence and skipped checks;
- residual risk;
- recommended repair actions.

## Repair Workflow

Repair workflow corrects a failed or blocked skill target while preserving unrelated work.

Entry conditions:

- failure or blocker is named;
- target files are known;
- safe edit boundary is known;
- current file state has been inspected.

Required evidence:

- failing evidence or blocker record;
- current target file hashes or content;
- planned repair scope;
- post-repair checks;
- unchanged-file preservation evidence when needed.

Hard gates:

- fix the root cause rather than only changing the report wording;
- do not weaken standards to pass a check;
- preserve user and peer-agent work;
- rerun checks affected by the repair;
- report remaining blockers and skipped checks.

Expected output:

- files changed;
- reason for each change;
- validation rerun;
- remaining failures, blockers, skipped checks, and residual risk;
- updated claim boundary.

## Suite Workflow

Suite workflow checks a collection of skills or a suite contract.

Entry conditions:

- suite map or suite contract is in scope;
- included skills are identifiable;
- child evidence expectations are known.

Required evidence:

- included-skill inventory;
- child status evidence;
- routing and dependency declarations;
- current-authority identity and former-surface absence;
- shared evidence rules;
- suite-level validation evidence;
- child skipped checks and blockers.

Hard gates:

- suite status must not exceed child evidence;
- missing, stale, blocked, failed, or unreviewed child work must remain visible;
- shared evidence must be fresh for each child it supports;
- routing conflicts must be reported;
- suite claims must avoid guaranteed future activation or AI correctness language.

Expected output:

- suite decision;
- child decisions;
- dependency and routing findings;
- current-authority and former-surface findings;
- skipped checks;
- blockers;
- residual risk;
- suite claim boundary.

## Closure Workflow

Closure workflow decides whether a checked result can be accepted, failed, or blocked.

Entry conditions:

- target and scope are known;
- required evidence has been collected or blockers are known;
- final artifact state has been inspected.

Required evidence:

- current artifact listing;
- required file hashes or line counts when useful;
- direct evidence for hard gates;
- skipped-check list;
- blocker list;
- residual-risk list;
- public-safety scan when public files are involved;
- claim boundary.

Hard gates:

- report-only closure is not enough when direct evidence is required;
- evidence must be fresh relative to final files;
- skipped required checks cannot be counted as passing;
- blockers must remain visible;
- closure must not expand to downstream work.

Expected output:

- `pass`, `fail`, or `block`;
- evidence summary;
- skipped checks and reasons;
- blockers and recommended resolution;
- residual risk;
- claim boundary;
- next action when not accepted.

## Skipped-Check Handling

Every workflow must report skipped checks.

Skipped-check records should include:

- check name;
- reason;
- whether the check was required;
- status impact;
- recommended resolution.

Skipped required checks should usually produce `block` unless the scope explicitly excludes them.

## Blocker Handling

Blockers should be concrete and actionable.

Good blocker records name:

- missing or unsafe condition;
- affected target;
- evidence already collected;
- why the workflow cannot honestly close;
- recommended next action.

Do not hide blockers in residual risk or narrative summaries.

## Residual-Risk Handling

Residual risk should identify uncertainty that remains after required checks are handled.

Examples:

- future model activation may vary;
- future external services may change;
- judgment uncertainty remains;
- downstream implementation remains outside scope.

Residual risk should not replace a failed hard gate, skipped required check, or blocker.

## Claim Boundaries

Every practical workflow should state what it proves and what it does not prove.

Create workflow proves only what was created and checked. Audit workflow proves only what was inspected. Repair workflow proves only the repair scope and rerun checks. Suite workflow proves only the suite claim supported by current child evidence. Closure workflow proves only the accepted, failed, or blocked scope.

None of these workflows proves package publication, git history, hosted release pages, external integration, fixture coverage, test execution, CLI checks, suite automation, checker implementation, code-contract verification, or future AI correctness unless those items are explicitly in scope and directly evidenced.

## Absent Artifact Handling

When a practical workflow encounters an absent artifact category, it should preserve the absence as part of the report.

Common absent categories include scripts, fixture files, executable tests, CLI checks, suite automation, package publication records, and code-contract checks.

The workflow may still close a documentation-only or policy-only scope when those categories are out of scope, but it must not describe them as passing. If any absent category is required for the selected scope, the workflow should fail or block instead of broadening residual risk.

Pass criteria: absence is reported with status impact and does not inflate the claim boundary.

Fail criteria: absence is converted into a success claim.

Block criteria: a required absent artifact prevents current evidence from supporting closure.

## Minimum Workflow Report

A practical workflow report should include:

- workflow mode;
- target;
- entry condition;
- files inspected or changed;
- evidence;
- hard gates applied;
- skipped checks;
- blockers;
- residual risk;
- decision;
- claim boundary;
- next action.

If those fields cannot be filled for a required scope, the workflow should block rather than imply success.

## Non-Claims

This workflow reference does not claim that create, audit, repair, suite, or closure automation exists. It does not claim that command tools, schemas, fixture files, tests, CLI checks, suite automation, checker code, package publication, code-contract checks, git commits, hosted release pages, external services, or AI correctness are complete.

Those claims require separate current evidence and explicit scope.
