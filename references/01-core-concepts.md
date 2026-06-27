# Reference 01: Core Concepts

This reference defines the shared vocabulary used by SkillGuard. These terms are meant to make skill maintenance reports precise, reproducible, and honest about what was checked.

## Purpose Of The Vocabulary

SkillGuard exists to help maintain Codex skills and skill-like workflows without confusing intent, evidence, and completion. The vocabulary below separates public documentation from validation evidence, deterministic checks from judgment, and bounded status claims from broad guarantees.

## Target Skill

A target skill is the skill or skill-like workflow being inspected, maintained, repaired, or prepared for release.

For a single-skill task, the target skill is the one skill entry and its supporting materials. For a suite task, each child skill remains its own target skill before any parent summary is accepted.

Operational consequence: a report must name the target skill and must not transfer evidence from one skill to another without a fresh comparison.

## Skill Repository

A skill repository is the tracked project that stores the skill contract, documentation, metadata, examples, and validation material.

A public-ready skill repository should keep public files portable and should not rely on private local paths, credentials, private workspace notes, or unpublished service state.

Operational consequence: repository-level status must distinguish foundation files, implementation files, validation files, package metadata, and release or publication state.

## Skill Contract

A skill contract is the set of public and local materials that define how a target skill should activate, what it should do, what it should avoid, which evidence it requires, and what it may claim after checking.

The main contract is usually `SKILL.md`, but the contract can also be supported by README text, schemas, templates, reference standards, self-check records, and evidence rules.

Operational consequence: a target skill is not accepted merely because one file exists. Related contract materials must point to the same scope, status vocabulary, evidence boundary, and public claim boundary.

## SKILL.md Contract

The `SKILL.md` contract is the discoverable skill entry that tells Codex what the skill is for, when to use it, when not to use it, which workflow to follow, which gates are mandatory, and what the output must report.

Operational consequence: if `SKILL.md` is missing, malformed, too broad, or missing hard-gate behavior, the target cannot be accepted as a maintained skill.

## README Contract

The README contract is the public user-facing explanation of the repository. It should state the purpose, why the project exists, limits and non-guarantees, basic structure, intended commands, maintained files, status meanings, and license boundary.

Operational consequence: README prose may describe intended commands and future structure, but it must not certify that scripts, fixtures, schemas, checks, package publication, or external release steps are complete unless current evidence proves those claims.

## Activation Boundary

An activation boundary describes the tasks where a skill should be used. It should be specific enough to prevent noisy activation on unrelated tasks.

Good activation boundaries name the relevant artifact, decision, or workflow. For SkillGuard, that means skill maintenance, skill review, skill repository readiness, activation clarity, hard-gate enforcement, and evidence-backed status reporting.

Operational consequence: a broad activation boundary is a finding because it can make a skill trigger where it should not.

## Do-Not-Use Boundary

A do-not-use boundary describes tasks where a skill should stay inactive even if a few keywords appear.

For SkillGuard, unrelated coding tasks, generic README writing, ordinary package publication, broad cleanup, and application feature work are out of scope unless the task is specifically about a skill or skill-like workflow.

Operational consequence: if the do-not-use boundary is missing or weak, the skill is at risk of over-activation.

## Hard Gate

A hard gate is a required condition that must pass, fail, block, or be explicitly skipped with a reason. A hard gate is not advice and cannot be satisfied by confidence, intent, or old evidence.

Examples include required files existing, frontmatter parsing, required sections being present, privacy scans passing, validation evidence being fresh, and release claims being directly validated.

Operational consequence: a hard-gate failure remains visible in the final report. It must not be downgraded to a warning to make the report look successful.

## Evidence Bundle

An evidence bundle is the current material used to justify a status decision. It can include inspected file paths, hashes, line counts, parser output, command output, fixture results, timestamps, and structured reviewer notes.

Evidence should be tied to current files. If a file changes after evidence was collected, dependent evidence becomes stale until refreshed.

Operational consequence: report-only closure is not enough. SkillGuard status needs current evidence or a concrete blocker.

## Absent Artifact Boundary

An absent artifact boundary states that a check, command, fixture, script, suite runner, package publication step, or code-contract test is not available in the current repository state.

Absence is not success. If tests, fixtures, CLI scripts, suite automation, package publication files, or code-contract checks are absent, reports should say `missing`, `not applicable`, `skipped`, or `blocked` according to scope. They must not describe absent artifacts as passing evidence.

Operational consequence: SkillGuard can accept a documentation-only or foundation-metadata scope only when the claim boundary says that implementation and executable validation remain outside the current proof.

## Status Taxonomy

SkillGuard uses narrow status terms so readers can see what is known:

- `missing`: required files or records are absent.
- `draft`: files exist but have not been checked against current requirements.
- `checked`: deterministic checks ran against current files and did not report blocking failures.
- `needs-review`: deterministic checks are not enough and judgment is required.
- `blocked`: a required file, decision, credential, or external condition prevents completion.
- `stale`: prior evidence exists but no longer matches current files.
- `accepted`: the target has current deterministic evidence and any required judgment records for the stated scope.

Reports may also use `pass`, `fail`, and `block` as decision outcomes:

- `pass`: the stated scope passed the required checks with current evidence.
- `fail`: the stated scope was checked and one or more required conditions failed.
- `block`: the stated scope cannot be checked or completed because required information, files, tools, credentials, or decisions are missing.

Operational consequence: parent and suite status must not hide child states such as `missing`, `blocked`, `stale`, `needs-review`, or `fail`.

## Blocker

A blocker is a concrete condition that prevents honest completion of the requested scope.

Examples include a missing target path, malformed required metadata, unavailable required parser, absent credentials for an external action, a privacy exposure that must be removed, or a conflict with existing user work.

Operational consequence: blockers should name the missing or unsafe condition and the recommended resolution. They should not be hidden as residual risk.

## Residual Risk

Residual risk is what remains uncertain after the performed checks. It is not the same as a failed hard gate.

Examples include future model behavior, judgment quality, future external service availability, and downstream work not in the current scope.

Operational consequence: residual risk is acceptable only after required gates for the current scope have been handled. A missing required check is a skipped check or blocker, not residual risk.

## Claim Boundary

A claim boundary states exactly what a report proves and what it does not prove.

SkillGuard reports should not imply that a repository is fully implemented, fully tested, published, externally integrated, or guaranteed to activate correctly unless those exact claims were directly validated.

Operational consequence: every public-ready report should avoid broad completion language and tie status to current evidence.

## Skill Map

A skill map is a public-safe inventory of one or more target skills and the relationships among their files, references, schemas, templates, self-check records, evidence records, and status claims.

For a single skill, the map can show how `SKILL.md`, README, metadata, references, schemas, templates, and local records support the same contract. For a suite, the map must keep every child skill visible before any parent status is summarized.

Operational consequence: a skill map must not hide missing, blocked, stale, skipped, or unreviewed child evidence behind a parent label.

## Maintenance Synchronization

Maintenance synchronization keeps related files aligned as a skill evolves. The `SKILL.md` contract, README, version metadata, validation commands, fixtures, schemas, status records, and release notes must not drift into contradictory claims.

Operational consequence: when one maintained artifact changes, dependent evidence and public claims should be rechecked before acceptance.

## Deterministic Checks And AI Judgment

Deterministic checks answer questions with direct file, parser, or command evidence. Examples include whether a file exists, whether frontmatter parses, whether a required heading is present, or whether metadata versions match.

AI judgment answers questions that require interpretation. Examples include whether an activation boundary is too broad, whether a claim overreaches, whether instructions are operational enough, or whether a residual risk is material.

Operational consequence: judgment can support a decision, but it must be identified as judgment. It should not be presented as deterministic proof or as a guarantee of future AI correctness.

## Non-Guarantees

SkillGuard is an evidence-backed checking workflow. It does not guarantee:

- that Codex will always activate a skill at the right time;
- that AI judgment is independently sufficient;
- that semantic review can be fully automated;
- that all skills can be migrated in one automatic batch;
- it does not prove package publication, git history, external credentials, or hosted release pages exist.

Operational consequence: the safest SkillGuard report is specific: it says what was checked, what passed, what failed, what blocked, what was skipped, and what remains outside the claim boundary.
