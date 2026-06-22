# Reference 06: Evidence Freshness And Closure Boundaries

This reference defines how SkillGuard treats evidence freshness, stale evidence, closure boundaries, skipped checks, blockers, residual risk, and artifact digests.

Acceptance depends on current evidence for the stated scope. A summary that says work is complete is not enough by itself.

## Scope

Use this standard when a SkillGuard report, checker, review, or release decision needs to decide whether evidence is current enough to support a pass, fail, block, or accepted status.

The standard applies to skill files, repository metadata, references, schemas, fixtures, scripts, reports, suite maps, suite contracts, and public release claims.

It does not create checker code or a validation suite. It defines the evidence rules that future checkers and reviewers must enforce.

## Evidence Freshness

Evidence is fresh when it was collected against the current files, metadata, scope, and acceptance criteria being judged.

Freshness should consider:

- file content at the time of inspection;
- file hashes or line counts where useful;
- parser or command output from current files;
- the version or schema of the checker used;
- the task scope and closure boundary;
- whether dependent files changed after evidence was collected.

Pass criteria: required evidence is tied to the current artifact state and the current scope.

Fail criteria: evidence is old, unverifiable, or collected against different files or criteria.

Block criteria: required evidence cannot be collected because files, tools, credentials, or safe-edit decisions are missing.

## Stale Evidence

Evidence is stale when it no longer matches the artifact or decision it is used to support.

Common stale-evidence causes:

- a checked file changed after the evidence was collected;
- a referenced file moved or disappeared;
- a schema, checker, or fixture version changed;
- a parent summary cites child evidence from a different child version;
- acceptance criteria changed;
- a skipped check is later treated as passing.

Stale evidence may still be useful as history, but it cannot support current acceptance until refreshed.

Pass criteria: stale evidence is identified and not used as proof of current acceptance.

Fail criteria: stale evidence is presented as current evidence.

Block criteria: stale evidence is the only available evidence for a required gate.

## Direct Evidence

Direct evidence is collected from the artifact being judged or from a current command or parser run over that artifact.

Examples:

- reading the current `SKILL.md`;
- parsing current frontmatter;
- listing current reference files;
- hashing the files changed in the current node;
- running a checker against current fixtures;
- recording a current reviewer judgment with cited files.

Direct evidence is preferred for hard gates and closure decisions.

Pass criteria: hard gates are supported by direct evidence unless the scope explicitly allows another evidence type.

Fail criteria: direct evidence contradicts the claimed status.

Block criteria: direct evidence is required but cannot be obtained.

## Report-Only Evidence

Report-only evidence is a claim in a summary, note, or prior report without direct inspection of the current artifact.

Report-only evidence can help orient a reviewer, but it is insufficient for acceptance when direct evidence is required.

Examples:

- "the README was checked" without current file content or check output;
- "the suite passed" without child evidence;
- "fixtures were updated" without fixture listing or hash evidence;
- "AI reviewed this" without a structured judgment record.

Pass criteria: report-only evidence is used only as context and is not the sole support for a hard gate.

Fail criteria: report-only evidence is treated as direct proof.

Block criteria: no direct evidence is available for a required closure decision.

## Closure Boundary

A closure boundary states exactly what a report or node is allowed to close.

Examples:

- one README file;
- one `SKILL.md` contract;
- references 06 through 08;
- one single-skill standard check;
- one suite map validation.

Closure must not expand silently to downstream work. Completing a reference does not complete scripts, schemas, fixtures, tests, CLI checks, suite automation, package publication, code-contract checks, packages, git history, hosted releases, or external integrations.

Pass criteria: closure is limited to the stated scope and supported by current evidence.

Fail criteria: closure claims include artifacts or checks outside the scope.

Block criteria: the scope is ambiguous and materially affects the decision.

## Accepted Closure

Accepted closure means the current scope has enough evidence to support acceptance.

Minimum accepted-closure requirements:

- target and scope are named;
- required artifacts exist;
- required direct checks ran or were explicitly scoped out;
- skipped checks are named with reasons;
- blockers are absent or resolved;
- residual risks are identified;
- claim boundary is stated;
- evidence is fresh relative to the final artifact state.

Accepted closure is not a statement that all future work is complete.

## Skipped Checks

A skipped check is a check that did not run.

Every skipped check should include:

- check name;
- reason;
- whether it is optional or required;
- impact on status;
- recommended resolution.

A skipped required check cannot be counted as passing.

Pass criteria: skipped checks are visible and status reflects their impact.

Fail criteria: skipped checks are hidden or treated as passed.

Block criteria: a skipped required check prevents honest completion.

## Blocker Closure

Blocker closure means the correct result is to stop with a block decision rather than claim acceptance.

A block decision should name:

- the blocker;
- the missing or unsafe condition;
- the evidence already collected;
- why the task cannot honestly close;
- recommended resolution.

Blocker closure is valid completion for a blocked scope. It is not a failure to continue; it is a boundary against unsupported claims.

## Residual Risk

Residual risk is uncertainty that remains after required checks are handled.

Residual risk is not a replacement for failed or skipped required checks.

Examples:

- future model activation may differ;
- judgment quality may vary;
- external service availability may change;
- downstream implementation remains outside scope.

Pass criteria: residual risk is disclosed after required gates are handled.

Fail criteria: residual risk is used to hide a failed or missing required check.

Block criteria: uncertainty affects a required decision and cannot be reduced enough for the requested closure.

## Artifact Digest Limits

Hashes and digest labels are useful evidence, but they are not standalone authority for semantic acceptance.

A digest can show that a file did or did not change. It cannot prove that the file is correct, public-safe, complete, or aligned with requirements.

Digest evidence should be paired with direct content inspection when content obligations matter.

Pass criteria: digests support preservation, freshness, and reproducibility claims within their limits.

Fail criteria: digest labels are treated as proof of semantic quality.

Block criteria: direct inspection is required but only digest labels are available.

## Minimum Closure Review Rules

Before accepting closure, check:

- target path and scope;
- current artifact listing;
- required direct evidence;
- freshness relative to final files;
- skipped checks and reasons;
- blockers;
- residual risk;
- claim boundary;
- privacy and public-safety scan when public files are involved;
- no unsupported implementation, validation-suite, package, git, hosted release, or external integration claim.

These rules are gates for honest closure, not optional presentation preferences.

## Non-Claims

This evidence standard does not claim that checker code exists, that a fixture corpus exists, that tests, CLI checks, suite automation, code-contract checks, or a validation suite have passed, or that package publication or release publication is complete.

Those claims require their own current direct evidence.
