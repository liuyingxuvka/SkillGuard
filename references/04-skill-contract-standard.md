# Reference 04: Skill Contract Standard

This reference defines the standard for one skill contract. A skill contract is the public agreement expressed by `SKILL.md` and supporting documentation: when to use the skill, when not to use it, how to run the maintenance workflow, which gates are mandatory, and what evidence must appear in the report.

The standard is generic. It applies to arbitrary Codex skills and does not depend on a specific named skill family.

## Scope

Use this standard when reviewing, creating, or maintaining a single skill contract.

The contract standard applies to:

- frontmatter metadata;
- activation and do-not-use boundaries;
- required workflow;
- hard gates;
- evidence requirements;
- output and reporting rules;
- maintenance synchronization;
- privacy and public-safety boundaries;
- no-overclaim rules.

It does not prove that implementation scripts, fixtures, tests, CLI checks, suite automation, package publication, code-contract checks, schemas, package metadata, git history, hosted releases, or external integrations exist unless those items are explicitly in scope and checked.

## Frontmatter Metadata

The `SKILL.md` frontmatter should be structurally valid and public-safe.

Required fields:

- `name`: stable skill identifier.
- `description`: concise activation description that identifies the intended task shape.

Recommended checks:

- opening and closing `---` delimiters are present;
- metadata parses with an appropriate parser or structural check;
- name and description are non-empty;
- description is specific enough to avoid noisy activation;
- metadata contains no credentials, private local paths, private task text, or internal coordination details.

Pass criteria: metadata parses or structurally validates and gives a clear public activation signal.

Fail criteria: metadata is malformed, missing required fields, private, or too vague.

Block criteria: parser support is required by the task but unavailable, or the file cannot be read safely.

## Activation Boundary

The activation boundary states when the skill should be used.

An actionable boundary names the artifact, task, decision, or workflow that triggers the skill. It should avoid generic claims such as "use for all coding" or "use for any release" unless the skill truly owns those scopes.

Pass criteria: users and agents can tell when the skill belongs in the task.

Fail criteria: activation is overly broad, ambiguous, contradictory, or tied to private context.

Block criteria: the intended target tasks are unknown and cannot be inferred safely.

## Do-Not-Use Boundary

The do-not-use boundary states when the skill should stay inactive.

It should include nearby but out-of-scope tasks, such as generic documentation, ordinary coding, unrelated release publication, broad cleanup, or tasks that merely mention similar terms without involving the target skill workflow.

Pass criteria: the skill has clear negative examples or exclusions.

Fail criteria: no non-use boundary exists, or exclusions are too weak to prevent over-activation.

Block criteria: overlapping skills or workflows claim the same scope with no resolution rule.

## Required Workflow

The workflow should be ordered and operational.

Expected workflow elements:

1. Inspect current materials.
2. Confirm target scope and skill path.
3. Inventory relevant files and references.
4. Initialize or update maintained records only when the task owns that work.
5. Run deterministic checks first.
6. Run judgment checks where deterministic checks cannot answer the question.
7. Collect fresh evidence.
8. Report pass, fail, or block with skipped checks and residual risk.

Pass criteria: the workflow can guide an agent through real maintenance work.

Fail criteria: the workflow is aspirational, unordered, or missing evidence collection.

Block criteria: required scope or target information is missing.

## Native Runtime Integration

When a target skill already has its own route selection, controller, simulator, checker, validation script, or closure workflow, SkillGuard should integrate with that native system instead of creating a parallel runtime.

Every runtime work contract should declare one integration mode:

- `native-integrated`: the target skill already owns the runtime path. SkillGuard records and enforces the native route/check contract.
- `hybrid-extension`: the target skill owns part of the runtime path, and SkillGuard fills missing gates such as evidence, freshness, quality-floor, or closure checks.
- `skillguard-runtime`: no native runtime system is declared, so SkillGuard owns the route/phase/check contract.

Required native-integration fields:

- `integration_mode`;
- `native_route_owner`;
- `native_route_bindings`;
- `native_check_bindings`;
- `skillguard_role`;
- `may_define_parallel_execution_route`;
- `may_define_skillguard_runtime_route`;
- `integration_claim_boundary`.

Pass criteria: a native or hybrid target binds the original route/check system and uses SkillGuard as a native-bound or hybrid contract executor, not as a parallel route owner.

Fail criteria: a native or hybrid target adds a second SkillGuard execution route, omits native route/check bindings, or lets SkillGuard bypass the original router, controller, simulator, checker, or closure flow.

Block criteria: the target appears to have a native system, but ownership cannot be identified well enough to choose between native integration, hybrid extension, and SkillGuard-owned runtime.

## Hard Gates

Hard gates are required checks that cannot be softened into suggestions.

Common hard gates:

- required files exist;
- frontmatter is valid;
- required sections are present;
- activation and do-not-use boundaries are clear;
- privacy and public-safety scans pass;
- validation evidence is fresh;
- child or suite evidence is not hidden by parent summaries;
- failures, blockers, and skipped checks remain visible;
- implementation, publication, and external-integration claims are directly validated before being claimed complete.
- runtime contracts for skills with existing native route/check systems bind those native systems rather than creating a second execution route;

Pass criteria: every required gate passes or is explicitly out of scope.

Fail criteria: a required gate fails.

Block criteria: a required gate cannot be checked and the missing condition prevents honest completion.

Skipped gates must be named with reasons and must not be counted as passing.

## Evidence Requirements

A skill contract should require current evidence for its status decisions.

Evidence may include:

- file existence checks;
- hashes or line counts;
- frontmatter parse output;
- heading inventories;
- path-resolution checks;
- deterministic command output;
- fixture output;
- structured judgment notes;
- skipped-check reasons;
- residual-risk notes.

Pass criteria: evidence is current, reproducible, and tied to the checked files.

Fail criteria: evidence is stale, missing, unverifiable, or detached from the target.

Block criteria: required evidence cannot be collected because files, tools, credentials, or safe-edit decisions are missing.

## Output Contract

The skill's report should be structured enough for review.

Required report fields:

- checked target;
- decision or status;
- evidence;
- failures;
- blockers;
- skipped checks with reasons;
- residual risk;
- claim boundary;
- next action when blocked or failed.

Pass criteria: the report exposes enough evidence to reproduce or challenge the decision.

Fail criteria: the report hides failures, omits blockers, treats skipped checks as passing, or presents judgment as deterministic proof.

Block criteria: required report inputs are unavailable.

## Maintenance Synchronization

The skill contract should explain how maintainers keep related files aligned.

Synchronization targets may include:

- `SKILL.md`;
- README;
- references;
- version metadata;
- schemas;
- fixtures;
- scripts;
- tests;
- status records;
- release notes.

Pass criteria: maintainers know which files to update when the contract changes.

Fail criteria: public claims, metadata, workflow text, and validation artifacts drift apart.

Block criteria: a required ownership or version decision is missing.

## Privacy And Public Safety

The skill contract must be suitable for a public repository.

It should not contain:

- credentials or token patterns;
- private keys;
- private local paths or usernames;
- private transcripts or task payloads;
- internal coordination records;
- unvalidated claims of external publication or hosted release state.

Pass criteria: no private or unsafe content is found in the current contract.

Fail criteria: private or credential material is present.

Block criteria: unsafe material cannot be removed without an owner decision.

## No-Overclaim Rules

A skill contract should avoid claiming more than current evidence proves.

It should not claim:

- future model activation is guaranteed;
- AI judgment is always correct;
- scripts, schemas, fixtures, tests, CLI checks, suite automation, package publication, code-contract checks, package metadata, command-line tools, git history, hosted releases, or external integrations are complete without direct evidence;
- suite-level acceptance when child skills are missing, stale, failed, blocked, or unreviewed.

Pass criteria: claims are bounded to current evidence and stated scope.

Fail criteria: broad completion, safety, activation, or publication claims appear without evidence.

Block criteria: a required claim boundary cannot be determined from current materials.

## Minimum Review Checklist

Before accepting a skill contract, verify:

- frontmatter is valid;
- activation and non-use boundaries are clear;
- workflow is ordered and operational;
- hard gates are mandatory;
- output requirements expose evidence, failures, blockers, skipped checks, residual risk, and claim boundaries;
- maintenance synchronization is described;
- privacy and public-safety scans are clean;
- no unvalidated implementation or publication claims are present.
