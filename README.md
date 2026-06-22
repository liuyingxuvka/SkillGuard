# SkillGuard

A conservative maintenance framework for Codex skills that keeps claims tied to current files, current checks, and visible review boundaries.

SkillGuard helps maintainers inspect a skill repository, describe what is present, separate deterministic checks from human or AI judgment, and report whether a skill or suite is missing, stale, blocked, checked, or accepted for a stated scope. It is designed for public skill repositories where overclaiming is easy: a README can promise commands that do not exist, a parent suite can hide a failing child, or an old report can be reused after files changed.

Current version: `1.0.0`

Current repository status: foundation metadata, local SkillGuard materials, local script-based CLI dispatch, explicit fixture manifests, local examples, and a standard-library smoke test script are present. The current tree does not include a packaged CLI, suite automation, package publication, release artifacts, git remotes, external service integration, or code-contract validation.

## Current Capability Boundary

The current repository supports reading and maintaining SkillGuard's public contract, standards, schemas, templates, initial self-maintenance records, a local standard-library CLI dispatch layer, explicit positive and negative fixture manifests, local examples, and a standard-library smoke test script. These files do not prove broad fixture coverage, package installation, suite automation, external publication, release readiness, or code-contract validation.

Use the README as a map of the current repository surface. Use current files, schemas, templates, and records as evidence before making a stronger claim.

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
```

Current local material status:

| Area | Current status |
| --- | --- |
| `README.md` | Public project overview |
| `LICENSE` | MIT license text |
| `VERSION` | `1.0.0` |
| `pyproject.toml` | Metadata with conservative local implementation status |
| `references/` | SkillGuard standards and policy references |
| `examples/` | Local examples for `check-skill`, `check-suite`, `fixture-test`, and `self-check` |
| `tests/` | Standard-library local smoke checks |
| `.agents/skills/skillguard/SKILL.md` | Codex skill entrypoint |
| `.agents/skills/skillguard/assets/schemas/` | JSON schemas for SkillGuard records |
| `.agents/skills/skillguard/assets/templates/` | JSON and `SKILL.md` templates |
| `.agents/skills/skillguard/.skillguard/` | Initial self-maintenance records |
| `.agents/skills/skillguard/scripts/` | Local standard-library CLI dispatch and checker-engine helpers |
| `.agents/skills/skillguard/fixtures/` | Local positive and negative fixture manifests with generated command-output evidence |

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

   The current local command set is `commands`, `inventory`, `init-target`, `init-suite`, `mark`, `check-skill`, `check-suite`, `check-skill-contract`, `check-suite-map`, `check-suite-contract`, `check-fixture-manifest`, `fixture-test`, `check-ai-judgment`, `check-report`, `check-workflow-report`, `make-closure`, `self-check`, and `write-report`.

7. To run the local examples, read:

   ```text
   examples/README.md
   ```

8. To run the standard-library smoke checks, use:

   ```powershell
   python tests/test_skillguard_local.py --json-output .agents/skills/skillguard/fixtures/evidence_outputs/standard_library_tests_current.json
   ```

## Validation And Test Boundary

The current repository contains a local standard-library smoke test script and explicit positive and negative fixture manifests. It does not contain packaged CLI checks, suite automation, broad fixture coverage proof, package-publication checks, release-readiness checks, or code-contract tests for README behavior. Current README validation therefore relies on deterministic documentation checks, local CLI smoke checks, explicit fixture-manifest runs, required sections, current path existence or absence, version and license consistency, suite and status wording, AI judgment boundaries, parseable JSON command output, and privacy-safe public wording.

For this repository state, broad fixture proof, packaged CLI proof, suite-automation proof, package-publication proof, release-readiness proof, and code-contract evidence are not applicable because the corresponding proof surfaces are absent. Local script CLI smoke evidence and fixture-manifest evidence are narrower and must not be reported as broad fixture coverage, suite automation, package publication, release readiness, or code-contract validation.

Current README proof is limited documentation-plus-local-smoke evidence: a reviewer can check the file content, file hash, heading coverage, path existence or absence, version and license consistency, suite and status wording, AI-boundary wording, parseable local command output, explicit fixture-manifest behavior, and privacy scan. That proof is not a substitute for packaged CLI installation checks, suite automation, package-publication checks, release-readiness checks, or code-contract checks.

For this limited local implementation state, absence and proof obligations should be classified this way:

| Obligation | Current basis | Public claim boundary |
| --- | --- | --- |
| Executable tests | `tests/test_skillguard_local.py` provides standard-library local smoke checks | Local smoke checks only; do not claim packaged CLI, suite automation, release, or code-contract coverage. |
| Fixture proof | `.agents/skills/skillguard/fixtures/` contains explicit positive and negative fixture manifests | Local explicit fixture-case checks only; do not claim broad fixture coverage. |
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
