# Reference 02: Single-Skill Standard

This reference defines the target standard for one Codex skill repository or one maintained skill target. It is a standard for evidence-backed acceptance, not a claim that every supporting tool already exists.

## Scope

The single-skill standard applies when SkillGuard reviews one skill, one skill repository, or one maintained target for public readiness, activation quality, validation evidence, and claim boundaries.

The standard does not accept a suite summary as a substitute for the target skill's own evidence. It also does not certify multi-skill suite behavior, package publication, git commits, hosted release pages, or external integrations unless those items are in scope and directly checked.

In this reference, "single-skill standard" and "target-skill standard" mean the same thing: the target skill must carry its own current evidence, privacy boundary, version and license consistency, and claim boundary.

## Required Foundation Files

A public single-skill repository should identify these foundation files when they are part of the target scope:

- `README.md` for public purpose, usage, limits, structure, status meanings, and license boundary.
- `AGENTS.md` for public-safe contributor and agent policy.
- `LICENSE` for the repository license text.
- `VERSION` for the release baseline.
- `pyproject.toml` or equivalent metadata when Python packaging metadata is part of the repository.
- `.gitignore` for local caches, build outputs, logs, environment files, editor files, and other non-source artifacts.
- `.agents/skills/<skill-name>/SKILL.md` for the skill contract.

Pass criteria: required foundation files for the stated scope exist and do not contradict each other.

Fail criteria: required files are missing, malformed, or mutually inconsistent.

Block criteria: the target path or required scope decision is unavailable, or an existing-file conflict cannot be preserved safely.

## SKILL.md Standard

The skill contract should include parseable frontmatter and operational body sections.

Required frontmatter expectations:

- A stable `name` field.
- A clear public `description` that identifies when the skill should be used.
- No private paths, credentials, private task text, or internal coordination details.

Required body expectations:

- Purpose.
- Use When.
- Do Not Use When.
- Required Workflow.
- Hard Gates.
- Output Requirements.
- Maintenance obligations.

Pass criteria: frontmatter is structurally valid, required sections exist, activation and do-not-use boundaries are clear, hard gates are mandatory, and output requirements force evidence, failures, blockers, skipped checks, residual risk, and claim boundaries.

Fail criteria: frontmatter is malformed, activation scope is too broad, do-not-use guidance is missing, hard gates are optionalized, or output requirements allow unsupported success claims.

Block criteria: the skill entry cannot be read, required parser support is unavailable for a mandatory parse step, or ownership conflicts prevent safe edits.

## Entrypoint Behavior Standard

The target skill entrypoint is the file that Codex can discover and use to decide whether the skill applies. For a Codex skill repository, the expected entrypoint is `.agents/skills/<skill-name>/SKILL.md` unless the target scope explicitly declares another public-safe entrypoint.

Expected entrypoint behavior:

- The entrypoint path is named in repository-relative form.
- The entrypoint can be read before acceptance.
- Frontmatter identifies the skill name and activation description.
- Body instructions define use and non-use boundaries.
- Required workflow steps are operational, not merely descriptive.
- Hard gates say what must pass, fail, block, or be skipped with a reason.
- Output requirements force evidence, failures, blockers, skipped checks, residual risk, and claim boundary.
- Local material routing points to current repository files and marks missing scripts, fixtures, tests, schemas, templates, or examples as absent rather than successful.

Pass criteria: the entrypoint exists, is readable, has the required activation and non-use boundaries, and makes required workflow, hard-gate, output, and local-material behavior checkable.

Fail criteria: the entrypoint exists but is malformed, too broad, missing required activation or non-use behavior, optionalizes hard gates, hides absent local materials, or permits unsupported success claims.

Block criteria: the entrypoint is missing, cannot be read, cannot be parsed when parsing is required, or cannot be safely changed without an owner decision. A missing entrypoint is never treated as a passing check.

## Input Obligations Standard

A target skill should state what inputs are needed before its workflow can produce an honest result. Inputs can come from the user request, current repository files, current metadata, referenced local materials, authorized external tools, credentials, or reviewer judgment.

Expected input obligations:

- Name required input materials, target paths, or scope decisions.
- State which inputs are optional and how they affect the claim boundary.
- Inspect current repository files before using them as evidence.
- Treat unavailable files, credentials, tools, or owner decisions as `missing`, `blocked`, `skipped`, or `not applicable` according to scope.
- Avoid copying private task payloads, private transcripts, credentials, local absolute paths, or internal coordination identifiers into public artifacts.
- Refresh dependent evidence when an input file changes.
- Report input gaps in the final evidence instead of replacing them with assumptions.

Pass criteria: required inputs are identified, inspected when available, and tied to current evidence or explicit absence boundaries.

Fail criteria: the skill accepts stale inputs, silently assumes missing inputs, uses private material in public output, or treats unavailable inputs as passing evidence.

Block criteria: a required input, credential, tool, target path, scope decision, or safe-edit decision is unavailable and the requested acceptance claim depends on it.

## README Standard

The README should let a public user understand what the skill repository is for and what it does not guarantee.

Expected README coverage:

- Project name and one-sentence purpose.
- Why the skill exists.
- What the skill does.
- Non-guarantees.
- Directory structure.
- Quick-start commands or intended command names when applicable.
- Maintained files.
- Single-skill versus suite behavior.
- Deterministic checks versus AI judgment.
- Status meanings.
- Maintenance marker or ownership note.
- License boundary.

Pass criteria: the README is understandable, public-safe, consistent with `SKILL.md`, and clear about limitations.

Fail criteria: the README is mostly marketing prose, lacks required usage or limitation sections, contradicts the skill contract, or claims that unbuilt commands or integrations are complete.

Block criteria: the README cannot be read, has a preservation conflict, or depends on missing release decisions that must be resolved first.

## Root Metadata Standard

Root metadata should support public repository use without overstating implementation or release state.

Expected metadata behavior:

- `VERSION` and package metadata use the same version when both are present.
- License metadata matches the license file.
- Package metadata does not advertise missing packages, entry points, dependencies, scripts, or external integrations.
- Ignore rules do not hide source, docs, skill files, specs, fixtures, or release materials that the repository is expected to track.

Pass criteria: metadata parses where applicable, version fields align, license metadata is consistent, and ignore rules are scoped.

Fail criteria: metadata is malformed, versions diverge, license fields conflict, package metadata advertises missing artifacts, or ignore rules hide required repository deliverables.

Block criteria: a required parser is unavailable, a version decision is missing, or an existing metadata conflict cannot be resolved safely.

## Validation Evidence Standard

Single-skill acceptance requires evidence tied to current files.

Strong evidence can include:

- File existence checks.
- SHA256 hashes or line counts for changed files.
- Parser output for machine-readable metadata.
- Heading inventories for documentation contracts.
- Reference and path-resolution checks.
- Fixture or command output when those artifacts exist and are in scope.
- Structured human or AI judgment records for semantic questions.

Pass criteria: required checks for the stated scope were performed against current files and did not find blocking failures.

Fail criteria: a required check ran and found a failed condition.

Block criteria: a required check cannot run because a tool, file, credential, decision, or safe-edit boundary is missing.

Skipped checks must be listed with reasons. A skipped required check cannot be counted as passing.

## Absent Artifact And Non-Overclaim Standard

If a target repository does not contain implementation scripts, fixture files, tests, CLI checkers, suite automation, package publication files, or code-contract tests, the report should treat those categories as absent or not applicable for the stated scope.

Required absence handling:

- Do not claim a runnable CLI when no script or entry point exists.
- Do not claim tests passed when no test suite exists.
- Do not claim fixture coverage when no fixture files exist.
- Do not claim suite automation when no suite runner exists.
- Do not claim package publication or release readiness without current publication or release evidence.
- Do not claim code-contract verification when no implementation contract tests exist.

Pass criteria: absent artifacts are named as absent, skipped, not applicable, or blocked according to scope.

Fail criteria: the report treats absent artifacts as successful checks or uses future plans as current evidence.

Block criteria: a required artifact is expected for the scope but cannot be inspected or safely created.

## Privacy And Public-Safety Standard

Public skill repositories must avoid exposing private or machine-specific material.

Required scan targets include:

- Credentials, secrets, tokens, API keys, private keys, and environment secrets.
- Private local paths, local absolute paths, local usernames, and user-specific filesystem details.
- Private workspace transcripts, private task payloads, or private task context.
- Internal coordination records or private runtime identifiers.
- Claims of external publication or integration without current evidence.

Pass criteria: no public-safety finding appears in the current files for the stated scope.

Fail criteria: unsafe private or credential material is present.

Block criteria: private material cannot be removed without an owner decision, or the worker cannot inspect the relevant files.

## Status Reporting Standard

A single-skill report should provide:

- Target path and scope.
- Decision: `pass`, `fail`, or `block`.
- Supporting status labels such as `missing`, `draft`, `checked`, `needs-review`, `blocked`, `stale`, or `accepted` when useful.
- Current evidence.
- Failures and blockers.
- Skipped checks with reasons.
- Residual risk.
- Claim boundary.

Pass criteria: the report gives enough current evidence for a reviewer to reproduce the decision.

Fail criteria: the report hides failures, omits blockers, treats skipped checks as passing, or presents judgment as deterministic proof.

Block criteria: the report cannot be completed because required target information or evidence is unavailable.

## Maintenance Obligations

Maintainers should keep the single-skill standard current as files evolve:

- Keep `SKILL.md`, README, metadata, references, fixtures, schemas, scripts, and tests synchronized.
- Refresh evidence after changes to files that evidence depends on.
- Preserve existing user or peer-agent work before applying updates.
- Keep public claims tied to actual repository state.
- Separate deterministic check output from judgment-based review.
- Keep the license, version, and public metadata consistent.

Pass criteria: maintenance records and public claims match current files.

Fail criteria: records are stale, public claims overreach, or related files contradict each other.

Block criteria: ownership, missing decisions, missing credentials, or unavailable tools prevent safe completion.

## Explicit Non-Claims

Meeting this single-skill standard for one target does not by itself prove that:

- multi-skill suite checks are complete;
- the standard does not prove implementation scripts exist;
- schemas exist;
- fixtures exist;
- the standard does not prove command-line tools are installed or validated;
- the standard does not prove package publication is complete;
- the standard does not prove git commits or hosted release pages exist;
- the standard does not prove AI judgment is guaranteed correct;
- the standard does not prove future Codex activation is guaranteed.

Those claims require their own current evidence and acceptance scope.
