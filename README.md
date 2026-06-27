# SkillGuard

A conservative maintenance framework for Codex skills that keeps claims tied to current files, current checks, and visible review boundaries.

SkillGuard helps maintainers inspect a skill repository, describe what is present, separate deterministic checks from human or AI judgment, and report whether a skill or suite is missing, stale, blocked, checked, or accepted for a stated scope. It is designed for public skill repositories where overclaiming is easy: a README can promise commands that do not exist, a parent suite can hide a failing child, or an old report can be reused after files changed.

Current version: `0.1.2`

Current repository status: foundation metadata, local SkillGuard materials, local script-based CLI dispatch, deterministic `route-task` routing metadata, runtime work-contract commands, global SkillGuard registry and managed prompt commands, no-write `plan-skill` blueprint preview, controlled `generate-skill` scaffold creation with generated runtime contracts, controlled `generate-suite` suite scaffold creation, read-only `detect-stale-evidence` freshness checks, bounded `refresh-maintenance` metadata refreshes, read-only `review-checker-change` checker-change review, canonical `check-maintenance-record` schema validation, explicit fixture manifests including runtime-contract, global-router, simple-generation, and complex-generation fixtures, local examples, and a standard-library smoke test script are present. The current tree does not include a packaged CLI, suite automation, package publication, external service integration, or code-contract validation; GitHub release tags are external publication records and do not expand the local runtime claim boundary.

## Current Capability Boundary

The current repository supports reading and maintaining SkillGuard's public contract, standards, schemas, templates, initial self-maintenance records, a local standard-library CLI dispatch layer, explicit positive and negative fixture manifests, local examples, and a standard-library smoke test script. These files do not prove broad fixture coverage, package installation, suite automation, external publication, release readiness, or code-contract validation.

Use the README as a map of the current repository surface. Use current files, schemas, templates, and records as evidence before making a stronger claim.

## Runtime Contract Workflow

SkillGuard now includes a local runtime-contract command family. Its purpose is to help a target skill create a runnable work contract before the skill is used, select a route for a task, record the run, enforce phase order, check required evidence, and block closure when work was skipped or quality was downgraded.

This is still a local script surface, not a packaged CLI or external service. The runtime-contract commands prove only the current local files and explicit run records they load.

### Purpose

- Coordinate longer SkillGuard-governed work without hiding target scope, evidence state, skipped checks, blockers, or residual risk.
- Keep deterministic checks, human or AI judgment, repair work, and closure decisions visibly separate.
- Preserve the existing public claim boundary: current evidence supports only the files and checks that actually exist and ran.

### Command Surface

- Runtime contract compiler: `compile-contract` creates or previews `.skillguard/work-contract.json`, `.skillguard/check_manifest.json`, `.skillguard/checks/*.py`, and `.skillguard/runs/` for a target skill.
- Runtime contract checker: `check-contract` validates contract schema, canonical hash, routes, phases, required evidence, check scripts, quality floors, stale bindings, and closure rules.
- Runtime route selector: `select-route` chooses exactly one contract route for a task before work begins.
- Runtime run ledger: `start-run` creates a run record bound to the selected route and current contract hash.
- Runtime phase updater: `advance-run` records phase status, evidence ids, and passing check ids while preserving route order.
- Runtime run checker: `check-run` checks route order, skipped phases, missing or stale evidence, passing check evidence, blockers, and quality failures.
- Runtime closure gate: `close-run` allows `checked` or `accepted` closure only when the required phases, evidence, checks, quality floors, and claim boundary support that decision.
- Current local router: `route-task` accepts one task request from `--task` or a repository-local JSON config from `--input`, optionally with `--route-hint`, and returns either a deterministic public route decision or structured conflict blockers without invoking generators or mutating project files.
- Current local generator: `plan-skill` reads a repository-local skill idea JSON file and emits a Skill Blueprint preview to command output.
- Current local scaffold command: `generate-skill` reads a valid Skill Blueprint and creates draft skill scaffold files inside the explicit repository-local target path, blocking unsafe paths and conflicting existing files, then runs the local generated skill check against the final written target.
- Current local suite scaffold command: `generate-suite` reads a valid Suite Blueprint and creates draft suite records plus child skill scaffold/check records inside the explicit repository-local target path, blocking unsafe paths and conflicting existing files, then runs the local suite and child skill checks against the final written paths.
- Current local freshness command: `detect-stale-evidence` reads supplied evidence-bearing JSON artifacts and reports stale or unverifiable path/hash, route-version, route-registry, command-surface, fixture, generated-artifact, or OpenSpec status bindings without rewriting source artifacts.
- Current local maintenance command: `refresh-maintenance` uses the stale bindings reported for explicit evidence artifacts to plan or execute approved metadata refreshes for evidence summaries, fixture manifest/result bindings, generated artifact status records, command/self-check outputs, OpenSpec status metadata, and route registry metadata. Dry-run mode does not rewrite evidence artifacts; execute mode rewrites only supported metadata fields in the supplied evidence JSON files.
- Current local checker-change review command: `review-checker-change` compares an approved public checker-change baseline with current command dispatch, route bindings, fixture expectations, supplied evidence freshness, and public-boundary scans without rewriting baselines, fixtures, evidence, or source artifacts.
- Current local record schema command: `check-maintenance-record` validates canonical public maintenance records and can normalize supported legacy SkillGuard command outputs without rewriting the source artifact.
- Current global router commands: `scan-global-skills`, `build-global-registry`, `check-global-registry`, `resolve-global-skill`, `render-global-prompt`, `install-global-prompt`, `check-global-prompt`, and `refresh-global-router` scan local skill roots, build a route registry, resolve a task to a current skill, render the managed `AGENTS.md` router block, install only that managed block, and verify prompt freshness against the registry hash.
- Current limitation: these commands do not prove future AI behavior, package installation, external release readiness, broad fixture coverage, or code-contract validation. They enforce the local runtime contract and run-record evidence for the declared target only.

### Work Routing

- Default generated route: `intake -> inventory -> evidence -> checks -> closure`.
- Each route declares activation keywords, phases, required evidence, required checks, and closure rules.
- A run should stop or block when the target, route, scope, evidence, or contract hash is ambiguous or stale.

### Evidence Gates

- Runtime gates require current direct evidence from files, parser output, command output, fixture output, schema validation, or structured reviewer records.
- Runtime gates keep stale evidence, report-only evidence, hidden skipped checks, unresolved blockers, and unsupported claim expansion visible.
- A skipped required check should not be counted as passing evidence unless the declared scope explicitly excludes it.

### Closure Reporting

- Closure output should name target, route, scope, decision, evidence, deterministic checks, judgment checks, skipped checks, blockers, residual risks, claim boundary, and next action.
- Parent or suite summaries should not exceed child evidence.
- Public reports should avoid secrets, private transcripts, local machine details, internal run identifiers, and unsupported release or publication claims.

## What SkillGuard Is

SkillGuard is a skill-maintenance system for Codex skill projects. Its core job is to make maintenance evidence explicit:

- what skill entrypoint is being reviewed;
- what local standards, schemas, templates, and maintained records exist;
- what deterministic checks can be made from current files;
- what still requires human or AI judgment;
- what evidence is stale, missing, skipped, or blocked;
- what a final status does and does not prove.

The repository currently contains the public README, project metadata, MIT license, SkillGuard standards, a Codex skill entrypoint, schemas, templates, and initial self-maintenance records.

## What SkillGuard Is Not

SkillGuard does not guarantee that Codex will always activate a skill correctly.

SkillGuard does not prove AI correctness or replace human review. It can structure evidence and review records, but final release, compliance, safety, and publication decisions still need a responsible reviewer.

SkillGuard does not currently ship a packaged CLI in this repository. A local script dispatch surface exists under `.agents/skills/skillguard/scripts/`, and the repository includes explicit fixtures, examples, and a standard-library smoke test script. Do not assume package publication, release automation, broad fixture coverage, or broader checker coverage exists unless the current filesystem contains those files and they have been checked.

SkillGuard does not publish to GitHub or external services by itself.

## Repository Structure

Current public structure:

```text
SkillGuard/
  README.md
  AGENTS.md
  LICENSE
  VERSION
  pyproject.toml
  references/
  examples/
  tests/
  .agents/
    skills/
      skillguard/
        SKILL.md
        assets/
          schemas/
          templates/
        scripts/
        fixtures/
        .skillguard/
          ai_judgments/
          evidence/
          reports/
      skillguard-global-router/
        SKILL.md
        .skillguard/
```

Current local material status:

| Area | Current status |
| --- | --- |
| `README.md` | Public project overview |
| `LICENSE` | MIT license text |
| `VERSION` | `0.1.2` |
| `pyproject.toml` | Metadata with conservative local implementation status |
| `references/` | SkillGuard standards and policy references |
| `examples/` | Local examples for `check-skill`, `check-suite`, `fixture-test`, `route-task`, global router commands, `plan-skill`, `generate-skill`, `generate-suite`, `detect-stale-evidence`, `refresh-maintenance`, `review-checker-change`, `check-maintenance-record`, and `self-check` |
| `tests/` | Standard-library local smoke checks |
| `.agents/skills/skillguard/SKILL.md` | Codex skill entrypoint |
| `.agents/skills/skillguard/assets/schemas/` | JSON schemas for SkillGuard records |
| `.agents/skills/skillguard/assets/templates/` | JSON and `SKILL.md` templates |
| `.agents/skills/skillguard/.skillguard/` | Initial self-maintenance records |
| `.agents/skills/skillguard/scripts/` | Local standard-library CLI dispatch, runtime-contract commands, `route-task` deterministic routing, global registry and prompt-router commands, `plan-skill` preview generation, `generate-skill` scaffold creation, `generate-suite` suite scaffold creation, `detect-stale-evidence` freshness checks, `refresh-maintenance` metadata refreshes, `review-checker-change` checker-change review, `check-maintenance-record` schema validation, and checker-engine helpers |
| `.agents/skills/skillguard/fixtures/` | Local positive, static-negative, suite-negative, routing-conflict, runtime-contract, global-router, simple-generation, and complex-generation fixture manifests with generated command-output evidence |
| `.agents/skills/skillguard-global-router/` | Global SkillGuard router skill entrypoint and runtime contract for registry, route selection, and managed prompt installation work |

## Quick Start

This repository currently supports a documentation-and-records workflow plus a local script dispatch workflow. It is not packaged as an installed console command.

1. Read the skill entrypoint:

   ```text
   .agents/skills/skillguard/SKILL.md
   ```

2. Review the standards that define SkillGuard expectations:

   ```text
   references/
   ```

3. Inspect the local schemas and templates before creating or judging maintained records:

   ```text
   .agents/skills/skillguard/assets/schemas/
   .agents/skills/skillguard/assets/templates/
   ```

4. Inspect the initial self-maintenance records:

   ```text
   .agents/skills/skillguard/.skillguard/
   ```

5. When writing a report, state the current status, evidence, blockers, skipped checks, residual risk, and claim boundary. Do not describe a check as passed unless it actually ran against current files.

6. To inspect the local dispatch surface, run:

   ```powershell
   python .agents/skills/skillguard/scripts/skillguard.py commands
   ```

   The current local command set is `commands`, `route-task`, `inventory`, `plan-skill`, `generate-skill`, `generate-suite`, `scan-global-skills`, `build-global-registry`, `check-global-registry`, `resolve-global-skill`, `render-global-prompt`, `install-global-prompt`, `check-global-prompt`, `refresh-global-router`, `check-json-schema`, `compile-contract`, `check-contract`, `select-route`, `start-run`, `advance-run`, `check-run`, `close-run`, `init-target`, `init-suite`, `mark`, `check-skill`, `check-suite`, `check-skill-contract`, `check-suite-map`, `check-suite-contract`, `check-fixture-manifest`, `check-work-contract`, `check-run-record`, `check-check-manifest`, `fixture-test`, `detect-stale-evidence`, `refresh-maintenance`, `review-checker-change`, `check-maintenance-record`, `check-ai-judgment`, `check-report`, `check-workflow-report`, `make-closure`, `self-check`, and `write-report`.

7. To create and use a runtime contract for a target skill:

   ```powershell
   python .agents/skills/skillguard/scripts/skillguard.py compile-contract --target .agents/skills/skillguard --write
   python .agents/skills/skillguard/scripts/skillguard.py check-contract --target .agents/skills/skillguard
   python .agents/skills/skillguard/scripts/skillguard.py select-route --target .agents/skills/skillguard --task "Audit the target skill before closure"
   python .agents/skills/skillguard/scripts/skillguard.py start-run --target .agents/skills/skillguard --route audit --task "Audit the target skill before closure"
   ```

   Use `advance-run`, `check-run --complete`, and `close-run --decision accepted` only after the run has current evidence and passing check ids for every required phase.

8. To run the local examples, read:

   ```text
   examples/README.md
   ```

9. To refresh the local global router against a test Codex home:

   ```powershell
   python .agents/skills/skillguard/scripts/skillguard.py refresh-global-router --skill-root .agents/skills --codex-home .skillguard/test_codex_home --output-dir .skillguard/global-router
   python .agents/skills/skillguard/scripts/skillguard.py check-global-prompt --registry .skillguard/global-router/global_registry.json --codex-home .skillguard/test_codex_home
   ```

   Run the same refresh/check path after `generate-skill`, installed-skill sync, or any change to `SKILL.md`, `.skillguard/work-contract.json`, `.skillguard/check_manifest.json`, or native route bindings before claiming default global routing is current.

10. To run the standard-library smoke checks, use:

   ```powershell
   python tests/test_skillguard_local.py --json-output .agents/skills/skillguard/fixtures/evidence_outputs/standard_library_tests_current.json
   ```

## Validation And Test Boundary

The current repository contains a local standard-library smoke test script and explicit positive and negative fixture manifests. It does not contain packaged CLI checks, suite automation, broad fixture coverage proof, package-publication checks, release-readiness checks, or code-contract tests for README behavior. Current README validation therefore relies on deterministic documentation checks, local CLI smoke checks, explicit fixture-manifest runs, required sections, current path existence or absence, version and license consistency, suite and status wording, AI judgment boundaries, parseable JSON command output, and privacy-safe public wording.

For this repository state, broad fixture proof, packaged CLI proof, suite-automation proof, package-publication proof, release-readiness proof, and code-contract evidence are not applicable because the corresponding proof surfaces are absent. Local script CLI smoke evidence and fixture-manifest evidence are narrower and must not be reported as broad fixture coverage, suite automation, package publication, release readiness, or code-contract validation.

Current README proof is limited documentation-plus-local-smoke evidence: a reviewer can check the file content, file hash, heading coverage, path existence or absence, version and license consistency, suite and status wording, AI-boundary wording, parseable local command output, explicit fixture-manifest behavior, and privacy scan. That proof is not a substitute for packaged CLI installation checks, suite automation, package-publication checks, release-readiness checks, or code-contract checks.

### FlowPilot-Routed Validation Status

When this README is refreshed through a FlowPilot-routed maintenance run, FlowPilot is the orchestration path, not a public SkillGuard command. The public usage path is: inspect the current repository files, use current deterministic evidence and reviewer records, refresh only public documentation when that node owns README work, keep sealed runtime material out of the README, and return the role result through the FlowPilot runtime.

Current public validation evidence supports the local SkillGuard documentation and local command surface only:

| Evidence area | Current public evidence | Status boundary |
| --- | --- | --- |
| Local command surface | `python .agents/skills/skillguard/scripts/skillguard.py commands` | Current dispatch table is present; this is not packaged CLI installation proof. |
| Local smoke checks | `python tests/test_skillguard_local.py` | Standard-library local examples and command checks pass for the current files; this is not release-readiness or code-contract proof. |
| SkillGuard self and target checks | `self-check` and `check-skill` evidence outputs | Current entrypoint, local control records, public-boundary wording, and target records pass the local static checks for the stated scope. |
| Checker-change review | `review-checker-change` evidence output | Current checker bindings, route bindings, fixture expectations, evidence freshness, and public-boundary scans pass read-only review for the supplied public artifacts. |
| Explicit fixture behavior | Positive, negative, routing-conflict, runtime-contract, global-router, simple-generation, and complex-generation fixture outputs | Expected pass, fail, or block behavior is observed for explicit local manifests only; this is not broad fixture coverage. |
| Global router prompt path | `refresh-global-router`, `check-global-registry`, `check-global-prompt`, and `resolve-global-skill` evidence outputs | Current registry and managed prompt projection pass for explicit local/test roots only; this is not proof of future AI behavior or external installation state. |

Release-gate status: current evidence is sufficient for this README's local documentation claim boundary. It is not a package publication, external release, release-readiness, suite automation, broad fixture coverage, packaged CLI, git remote, external service, or code-contract validation gate.

For this limited local implementation state, absence and proof obligations should be classified this way:

| Obligation | Current basis | Public claim boundary |
| --- | --- | --- |
| Executable tests | `tests/test_skillguard_local.py` provides standard-library local smoke checks | Local smoke checks only; do not claim packaged CLI, suite automation, release, or code-contract coverage. |
| Fixture proof | `.agents/skills/skillguard/fixtures/` contains explicit positive, negative, routing-conflict, runtime-contract, simple-generation, and complex-generation fixture manifests | Local explicit fixture-case checks only; do not claim broad fixture coverage. |
| CLI proof | `.agents/skills/skillguard/scripts/` contains a local script dispatch surface | Local smoke checks only; do not claim packaged CLI installation or broad checker coverage. |
| Suite automation proof | A local static `check-suite` command and suite fixture files are present, but no suite automation runner is present | Local static suite checks only; do not claim suite automation or broad fixture coverage. |
| Code-contract evidence | No implementation contract tests are present | Not applicable; do not claim code-contract verification. |
| Proof artifact freshness | README hash, line count, headings, path checks, license/version checks, fixture/test command output, privacy scan, and claim-boundary scan must be regenerated after the last README edit | Current local evidence only; previous hashes or scans are stale after an edit. |

Current documentation validation should map each README obligation to either a current deterministic check or an explicit absence boundary:

- Public coverage is checked by required README section headings.
- Repository structure and maintained-file claims are checked by current path existence or absence.
- Version and license claims are checked against `VERSION`, `pyproject.toml`, and `LICENSE`.
- Suite, status, evidence, and AI-judgment boundaries are checked from current README wording and the local standards, schemas, and templates.
- Packaged CLI automation, package installation, suite automation, release readiness, and code-contract checks remain absent unless those evidence surfaces are added.
- Missing code-contract evidence is closed as not applicable only for the explicitly documented absent-evidence scope; once packaging, automation, or contract-test files exist, those checks need current executable evidence.

When command, test, fixture, package installation, suite automation, package-publication, release-readiness, or code-contract evidence changes later, README claims should be revalidated against those files before being described as complete.

## Maintained Files

SkillGuard maintained records are intended to keep review state close to the skill being maintained. The current self-maintenance record set includes:

- `skillguard_profile.json` for local applicability and scope.
- `skillguard_skill_contract.json` for activation, workflow, hard gates, and output expectations.
- `skillguard_evidence_rules.json` for evidence freshness and public-safety rules.
- `skillguard_closure_policy.json` for closure states and claim boundaries.
- `skillguard_manifest.json` for the local control-file index.
- `skillguard_progress_ledger.jsonl` for append-only progress records.
- `evidence/initial_evidence_manifest.json` for initial evidence.
- `ai_judgments/initial_ai_judgment.json` for a bounded initial judgment record.
- `reports/initial_self_check_report.json` and `reports/initial_workflow_report.json` for initial setup reports.

These records are initial local maintenance evidence. They do not prove that future implementation, checker behavior, fixture coverage, release readiness, or external publication is complete.

## Core Workflow

SkillGuard work follows a conservative sequence:

1. Inspect the current repository state.
2. Confirm the target skill, suite, or report scope.
3. Inventory relevant files and note absent files explicitly.
4. Run deterministic checks that are supported by current files.
5. Record human or AI judgment separately from deterministic results.
6. Report status with evidence, skipped checks, blockers, residual risk, and claim boundary.
7. Keep stale evidence visible instead of silently reusing it.

The workflow should preserve user and peer-agent work. It should not add broad cleanup, generated outputs, package metadata, git history, releases, or remotes unless a specific task owns that work.

## Suite Behavior

SkillGuard can describe suite-level maintenance rules through its standards, schemas, and templates. The key suite rule is evidence inheritance: a parent summary must not hide a child skill that is failed, missing, blocked, skipped, stale, or not yet reviewed.

For a suite report, each child skill should keep its own status and evidence. A suite-level `accepted` label is only meaningful when the current child evidence supports that exact scope.

Suite status should be calculated conservatively:

- If any required child is `missing`, the suite cannot be accepted.
- If any required child is `blocked`, the suite is blocked for the affected scope.
- If any required child evidence is `stale`, the suite must report stale evidence until that child evidence is refreshed.
- If any required child needs human or AI review, the suite should report `needs-review` or an equivalent visible blocker instead of hiding the gap.
- If checks were skipped, the suite report must name the skipped checks and explain their effect on the parent claim.
- A parent summary may be `checked` or `accepted` only for the exact scope supported by current child evidence.

The current repository contains suite schemas, templates, suite fixture files, and a local `check-suite` command for static suite map, contract, member, evidence, and unsafe-claim checks. It does not contain suite automation, broad fixture coverage proof, package-publication proof, release-readiness proof, or code-contract validation.

## AI Judgment Boundary

SkillGuard separates deterministic checks from judgment-based review.

Deterministic checks answer questions such as:

- Does the target `SKILL.md` exist?
- Does frontmatter parse?
- Do referenced local paths exist?
- Are required records present?
- Is evidence fresh for the files being judged?

Human or AI judgment answers questions such as:

- Is the activation boundary too broad?
- Are instructions likely to cause unsafe edits?
- Does a status overclaim what the evidence proves?
- Does a suite summary hide a failing or stale child result?

Judgment records should name the reviewer type, files reviewed, reasoning summary, limitations, and residual risk. They should not be flattened into a simple proof of correctness.

## Status Meanings

SkillGuard status labels should stay narrow:

| Status | Meaning |
| --- | --- |
| `missing` | Required files or records are absent. |
| `draft` | Files exist but have not been checked against the current scope. |
| `checked` | Deterministic checks ran against current files without blocking failures for the stated scope. |
| `needs-review` | Deterministic checks are not enough and human or AI judgment is required. |
| `blocked` | A required file, decision, credential, or external condition prevents completion. |
| `stale` | Prior evidence exists but no longer matches current files. |
| `accepted` | Current deterministic evidence and required judgment records support the stated scope. |

No label guarantees future Codex activation, AI correctness, legal compliance, package publication, release quality, or external service integration.

## Public Boundaries

Public README and documentation should avoid:

- credentials, secrets, tokens, API keys, private keys, or local machine configuration;
- private task payloads, internal coordination records, or private transcripts;
- runtime packet, result, lease, or internal run identifiers;
- local absolute paths or user-specific filesystem details;
- claims about commands, tests, fixtures, releases, remotes, or publication that current files do not support;
- screenshots or examples containing private data.

When a file or capability is absent, say it is absent. Do not replace absence with a planned command or a future-looking success claim.

Unsupported claims should be rewritten as limitations, assumptions, or future work.

## License

SkillGuard is licensed under the MIT License. See `LICENSE`.
