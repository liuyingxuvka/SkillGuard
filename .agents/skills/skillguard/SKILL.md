---
name: skillguard
description: "Use when maintaining, reviewing, or releasing Codex skill repositories and skill-like workflows that need inventory, activation-boundary checks, hard validation gates, and evidence-backed status reporting."
---

# SkillGuard

## Purpose

SkillGuard is a guardrail workflow for Codex skill maintenance and skill-release work. It helps agents inspect skill materials, clarify activation boundaries, enforce hard validation gates, and report evidence-backed status without treating unstated assumptions or old evidence as proof.

Use SkillGuard to keep public skill repositories honest about what exists, what was checked, what still needs review, and what must be blocked before release or adoption.

## Entrypoint Scope

This `SKILL.md` is the activation and routing entrypoint for the SkillGuard skill. It is not evidence that every referenced workflow, script, fixture, test, package command, release artifact, git remote, or publication step already exists.

When a task asks for implementation, validation, packaging, publication, or release work, inspect the current filesystem first and report missing local materials as absent or skipped. Do not turn an intended workflow in the README into a completed capability unless current files and fresh checks support that claim.

## Local Material Routing

Start from the current layout instead of assuming generated files exist. SkillGuard can run from the source repository layout or from the installed Codex skill layout.

- In the source repository layout, treat this file as the Codex skill entrypoint under `.agents/skills/skillguard/SKILL.md`; in the installed layout, treat local `SKILL.md` as the entrypoint.
- Use the repository README, pyproject metadata, VERSION file, and AGENTS file for the public repository contract, metadata, version, and contributor boundaries only when the source repository layout is present.
- Use the repository references directory for the maintained SkillGuard standards only when the source repository layout is present.
- Use `assets/schemas/` and `assets/templates/` for local schema and template checks.
- Use `.skillguard/work-contract.json` and `.skillguard/check_manifest.json` when a task needs runtime contract routing, phase gates, or closure rules.
- Use `.skillguard/checks/` for local runtime check script stubs and `.skillguard/runs/` for run records created before non-trivial skill work begins.
- Use other `.skillguard/` material under the skill directory when the task asks for maintained SkillGuard records, evidence, reports, or self-check material.
- Treat local `scripts/` and `fixtures/` under this skill as evidence only after direct inspection in the current task finds those paths and their current content. Treat repository tests and examples as source-repository evidence only when that layout is present and the paths exist.

Do not cite or require scripts, fixtures, examples, tests, package commands, releases, git remotes, or publication records unless they exist in the current filesystem and were inspected for the current task.

## Entrypoint Acceptance Map

Use this map when checking whether the entrypoint itself is acceptable:

- Frontmatter: the file starts with closed YAML frontmatter containing `name: skillguard` and a specific `description`.
- Activation boundary: `Use When` and `Do Not Use When` define when SkillGuard applies and when it must stay inactive.
- Local routing: `Local Material Routing` identifies the current repository materials and separates existing local paths from absent optional paths.
- Workflow: `Required Workflow` orders inspection, target confirmation, inventory, deterministic checks, judgment checks, evidence collection, and pass/fail/block reporting.
- Gates: `Hard Gates` lists the checks that must stay visible and cannot be replaced by confidence, intent, or stale reports.
- Output: `Output Requirements` defines the evidence, blocker, skipped-check, residual-risk, and claim-boundary fields expected in SkillGuard reports.
- Maintenance: `SkillGuard Maintenance` says when this entrypoint and related public files must be kept in sync.

If a current check cannot support one of these criteria, report the specific gap. Do not compensate by adding unrelated files, broad repository edits, generated outputs, git operations, package metadata changes, or release claims.

## Use When

Use this skill when the user asks to:

- Create, update, audit, or prepare a Codex skill or skill-like workflow.
- Review a skill repository for public readiness, activation clarity, privacy safety, metadata consistency, or release claims.
- Check whether a skill's description is too broad, too vague, or likely to activate for unrelated tasks.
- Validate a maintained skill target, suite summary, README, `SKILL.md`, metadata, fixtures, schemas, scripts, or check evidence.
- Compare parent status against child evidence so a suite or release summary does not hide stale, failed, missing, or skipped checks.
- Produce a status report that needs current evidence, blockers, skipped checks, residual risk, and claim boundaries.

## Do Not Use When

Do not use this skill for unrelated coding tasks that do not involve a skill, skill repository, skill-like workflow, or skill-release boundary.

Do not use this skill for generic README writing, ordinary package publication, broad repository cleanup, dependency upgrades, application feature work, or release notes unless the work is specifically about a Codex skill or its maintenance evidence.

Do not use this skill merely because a repository contains Markdown, Python, tests, or a release process. The task must involve skill maintenance, skill activation, skill validation, or skill-publication claims.

Do not use this skill to certify AI correctness, guarantee Codex activation, or bypass human review. SkillGuard can require evidence and structure judgment records, but it cannot prove that future model behavior will always be correct.

## Required Workflow

1. Inspect the current materials before editing or judging them.

   Identify the target skill path, repository root, maintained target, suite file, or release artifact. Record whether files already exist and preserve user or peer-agent work.

2. Confirm the scope and target.

   State whether the task is for one skill, a suite of skills, a public repository foundation, a release check, or a repair. If the target is unclear, block or ask for the missing information instead of guessing.

3. Inventory the relevant files.

   List the skill entry file, referenced documents, schemas, templates, package metadata, status records, and public documentation that matter to the requested check. Include scripts, fixtures, tests, generated outputs, and release artifacts only when they exist or when their absence is itself the finding.

4. Initialize or update maintained records only when the current task owns that work.

   If the task only asks for review, do not create new maintained files. If initialization is requested, create only the target files required by the documented structure and preserve existing content.

5. Apply deterministic checks first.

   Check file existence, frontmatter, required headings, parseable metadata, referenced paths, version consistency, status-record freshness, and any fixture or command availability that the current task actually claims. If a task depends on a local script, fixture, test, example, release artifact, or command that is absent, report that absence as a finding instead of fabricating or assuming the missing material.

6. Apply judgment checks only after deterministic evidence is clear.

   Review activation scope, non-use boundaries, unsafe claims, stale evidence risk, parent overclaim, privacy exposure, and whether instructions are operational enough for future agents.

7. Collect fresh evidence.

   Use current filesystem content, parser output, command output, hashes, line counts, timestamps, or concrete reviewer notes. Do not rely on old reports unless they are still tied to unchanged files.

8. Report pass, fail, or block.

   A missing required file, stale required evidence, privacy exposure, malformed metadata, or unvalidated release claim must be reported as a failure or blocker. Do not downgrade it to a warning just to complete the task.

## Runtime Contract Mode

Use Runtime Contract Mode when the task is about making a target skill's actual work path enforceable, not merely reviewing repository files.

In this mode SkillGuard should help the target skill:

- compile a `.skillguard/work-contract.json` with routes, phases, evidence obligations, quality floors, forbidden shortcuts, checks, closure rules, and stale bindings;
- require route selection before non-trivial skill work starts;
- create or update a `.skillguard/runs/` run record for the selected route;
- advance phases only when required evidence and checks are present for earlier phases;
- run route, phase-order, evidence, quality-floor, freshness, suite-child, and closure checks before closure;
- block missing contracts, hollow contracts, ambiguous routes, skipped phases, stale evidence, prose-only evidence, quality downgrades, and closure overclaims.

AI or human judgment may be recorded after deterministic evidence is clear, but it cannot replace required runnable checks or make skipped work pass.

## Hard Gates

These gates are mandatory for SkillGuard work. If a gate cannot be checked, mark it as skipped with a reason or block the task. Do not claim success for unchecked gates.

- Required files must exist for the stated scope.
- `SKILL.md` frontmatter must be structurally valid and closed before body content.
- Required sections must be present for the artifact being checked.
- Activation boundaries must say when to use the skill and when not to use it.
- Public files must not expose credentials, machine-specific local paths, confidential task material, or internal coordination records.
- Validation evidence must be fresh enough for the current files being judged.
- Parent or suite status must cite current child evidence and must not hide failed, missing, blocked, skipped, or stale child checks.
- AI or human judgment must be recorded as judgment, not as deterministic proof.
- Release, package, command, fixture, schema, git, and publication claims must be directly validated before they are described as complete.
- Failures and blockers must remain visible in the final report.
- Runtime contract work must not close unless the selected route, run record, required phases, required evidence, required checks, quality floors, and closure boundary are all current for the declared scope.

Hard gates are not suggestions. Vague confidence, intent, partial inspection, or a prior successful run is not enough to pass a hard gate.

## Output Requirements

SkillGuard reports should include:

- `checked_target`: the skill path, maintained target, suite file, repository area, or release artifact.
- `status`: `pass`, `fail`, or `block`, with `needs-review` or `stale` only when those labels are more accurate for the requested scope.
- `evidence`: current files inspected, commands or parsers run, hashes or line counts when useful, and the specific records used for the decision.
- `failures` and `blockers`: missing files, malformed metadata, stale evidence, unsafe claims, privacy findings, unclear activation boundaries, or unavailable required tools.
- `skipped_checks`: every skipped check and the reason it was skipped.
- `residual_risk`: what remains uncertain after the completed checks.
- `claim_boundary`: what the report does and does not prove.

Do not claim that scripts, fixtures, schemas, command-line tools, package publication, git commits, GitHub releases, external credentials, or downstream validation are complete unless those exact items were directly validated in the current task.

## SkillGuard Maintenance

When SkillGuard changes, keep the public contract synchronized across the maintained files:

- Update `SKILL.md` when activation scope, non-use boundaries, hard gates, or output requirements change.
- Update the repository README when public usage, status meanings, command names, non-guarantees, or repository structure change.
- Keep version metadata synchronized when release metadata changes.
- Keep validation commands and examples aligned with the scripts, fixtures, schemas, and tests that actually exist.
- Preserve privacy boundaries in public files. Do not copy private workspace instructions, local machine paths, private task text, or internal coordination details into maintained artifacts.
- Re-run the relevant deterministic checks after edits and record any judgment-based review separately from parser or command results.
- Treat stale evidence as stale. If a maintained file changes, refresh the evidence that depends on it before claiming acceptance.
