# Reference 09: SkillGuard Self-Check

This reference defines SkillGuard self-check: an evidence-backed internal quality check for SkillGuard-style skill artifacts and for this repository's own maintained materials.

Self-check is not self-certification. It can pass, fail, or block, and it must report evidence, skipped checks, blockers, residual risk, and claim boundaries.

## Scope

Use self-check when a repository needs to inspect its own SkillGuard materials or a SkillGuard-style skill target before relying on them.

Self-check may inspect:

- repository foundation files;
- `SKILL.md`;
- reference documents;
- metadata and version fields;
- suite maps and contracts;
- evidence freshness rules;
- structured AI judgment records;
- checker-change and fixture policies;
- public-safety and privacy boundaries.

Self-check does not prove that future model activation is guaranteed, that AI judgment is always correct, that package installation works, that package publication happened, that external publication has happened, or that unimplemented scripts, schemas, fixtures, tests, CLI checks, suite automation, code-contract checks, checkers, or validation suites are present.

## Target Selection

A self-check must name the target before checking.

Possible targets:

- the SkillGuard repository foundation;
- one skill contract;
- one reference file;
- the full reference set;
- one maintained skill target;
- one suite map;
- one suite contract;
- a release candidate scope.

Pass criteria: the target is named and the scope is narrow enough to check.

Fail criteria: the target is named but required content fails the standard.

Block criteria: the target is ambiguous, missing, or unsafe to inspect.

## Required Inputs

Self-check should collect current inputs before judging.

Required inputs may include:

- current file listing;
- current file content;
- hashes or line counts for checked files;
- parser output for machine-readable metadata;
- heading inventories for documentation contracts;
- status records;
- fixture or checker output when those artifacts are in scope and exist;
- user-supplied acceptance criteria;
- known skipped checks and blockers.

Pass criteria: required inputs for the selected scope are available and current.

Fail criteria: inputs are available and show a required mismatch.

Block criteria: a required input is unavailable and cannot be safely inferred.

## Absent Automation Boundary

Self-check must keep unavailable automation and proof artifacts visible.

If scripts, fixture files, executable tests, CLI checks, suite automation, package publication records, or code-contract checks are absent, the self-check report should:

- name the absent category;
- state whether it is out of scope, not applicable, skipped, or blocking for the selected target;
- avoid counting the absent category as passing evidence;
- require separate current evidence before claiming command execution, fixture coverage, test success, suite automation, package publication, or code-contract verification.

Pass criteria: unavailable automation is clearly scoped and not used as proof.

Fail criteria: the report claims unavailable automation passed or exists.

Block criteria: an unavailable automation artifact is required for the selected self-check scope.

## Deterministic Checks

Self-check should run deterministic checks before judgment checks.

Deterministic checks may include:

- required files exist;
- frontmatter is structurally valid;
- metadata versions align;
- required headings are present;
- referenced paths resolve;
- public files avoid private or credential material;
- known status terms are used consistently;
- closure boundaries do not exceed the stated scope;
- prior evidence is still tied to current files.

Pass criteria: required deterministic checks pass for the selected scope.

Fail criteria: a deterministic check finds a mismatch, missing file, malformed field, stale evidence, or unsafe public content.

Block criteria: a required deterministic check cannot run because files, tools, or decisions are missing.

## Structured AI Judgment Checks

Self-check may use structured AI judgment for semantic questions after deterministic evidence is clear.

AI judgment may inspect:

- activation boundary clarity;
- do-not-use boundary strength;
- hard-gate language;
- overclaim risk;
- residual-risk wording;
- workflow clarity;
- whether skipped checks are visible;
- whether a parent summary hides child evidence problems.

The judgment should name reviewed inputs, confidence, uncertainty, blockers, skipped checks, residual risk, and claim boundary.

Pass criteria: judgment supports the claim boundary and does not override deterministic failures.

Fail criteria: judgment finds unclear scope, overclaiming, weak gates, hidden blockers, or unsupported completion claims.

Block criteria: required inputs for judgment are missing or the judgment question is outside the authorized scope.

## Evidence Freshness

Self-check must use evidence fresh enough for the current target.

Fresh evidence is tied to the current files and acceptance criteria. Evidence becomes stale when dependent files, schemas, fixtures, checkers, metadata, or requirements change.

Pass criteria: evidence is current for the checked files.

Fail criteria: stale evidence is presented as current.

Block criteria: required current evidence cannot be collected.

## Closure Boundaries

Self-check must state what it closes.

The closure boundary should name the exact artifact, workflow mode, and evidence set that the self-check decision covers.

Examples:

- "Reference 09 exists and meets this reference-node scope";
- "the README contract is present and aligned";
- "one skill contract has current frontmatter and heading evidence";
- "a release candidate remains blocked because fixture evidence is missing."

Self-check closure must not expand into implementation, automation, package publication, git history, hosted release pages, or external integrations unless those items are explicitly in scope and directly checked.

## Status Reporting

Self-check reports should include:

- checked target;
- decision: `pass`, `fail`, or `block`;
- supporting status labels when useful;
- current evidence;
- deterministic checks performed;
- structured AI judgment checks performed;
- failures;
- blockers;
- skipped checks with reasons;
- residual risk;
- claim boundary;
- recommended next action.

Pass criteria: the report is reproducible from current evidence.

Fail criteria: the report hides failures, blockers, skipped checks, or residual risk.

Block criteria: required report inputs are missing.

## Public-Safety Checks

Self-check must scan public materials for unsafe content when public files are in scope.

Scan targets include:

- credentials and token patterns;
- private keys;
- private local paths or usernames;
- private task payloads or transcripts;
- internal coordination records;
- named private dependencies;
- unsupported publication or external-integration claims.

Pass criteria: public-safety scan is clean for the checked scope.

Fail criteria: unsafe material is present.

Block criteria: unsafe material cannot be removed or assessed without an owner decision.

## Residual-Risk Handling

Self-check should separate residual risk from failures and blockers.

Residual risk may include:

- future model activation behavior;
- future external service availability;
- judgment uncertainty;
- downstream implementation outside the current scope;
- validation layers not yet created.

Residual risk is acceptable only when required gates for the current scope are handled. A missing required check is a skipped check or blocker, not residual risk.

## Pass, Fail, And Block

Self-check can pass only when required checks for the selected scope have current evidence and no blocking failures.

Self-check should fail when a required checked condition is wrong, unsafe, stale, malformed, or contradictory.

Self-check should block when a required file, input, parser, checker, credential, owner decision, or safe-edit boundary is missing.

Skipped required checks must prevent a simple pass unless the selected scope explicitly excludes them.

## Non-Claims

Self-check does not claim that command automation exists, checker code exists, schemas exist, fixture files exist, tests, CLI checks, suite automation, package publication, or code-contract checks exist or passed, package installation works, git commits exist, hosted release pages exist, external services are configured, or AI judgment is guaranteed correct.

Those claims require separate current evidence and explicit scope.
