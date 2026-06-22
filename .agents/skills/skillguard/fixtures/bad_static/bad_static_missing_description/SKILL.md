---
name: "bad_static_missing_description"
---

# Bad Static Missing Description Fixture

## Purpose

Isolate the static-analysis failure caused by a missing non-empty `description` field in skill frontmatter.

## Entrypoint Scope

This fixture is intentionally defective. All non-description structure is present so the observed failure is attributable to the frontmatter description expectation.

## Local Material Routing

- Fixture metadata: `.skillguard/skillguard_manifest.json`
- Fixture evidence: `.skillguard/evidence/current_evidence_manifest.json`
- Fixture report: `.skillguard/reports/current_check_report.json`

## Entrypoint Acceptance Map

- Expected decision: `fail`
- Intended failed branch: SKILL.md frontmatter description check.

## Use When

- A local fixture-test run needs the missing-description static failure branch.
- A reviewer needs to verify that missing frontmatter description stays a fail-class result.

## Do Not Use When

- A task needs a passing skill fixture.
- A task needs blocker, boundary, stale, release, package publication, suite automation, or code-contract validation evidence.

## Required Workflow

1. Run `check-skill` against this fixture through `fixture-test` or directly.
2. Confirm the observed decision is `fail`, not `block`.
3. Confirm the failure detail names the missing non-empty description.
4. Keep evidence, failures, blockers, skipped_checks, residual_risk, and claim_boundary separate.

## Hard Gates

- Do not reinterpret this static defect as a blocker condition.
- Do not use runtime ids, PM text, stale history, or progress ledgers as closure proof.
- Do not claim runtime checker execution, fixture coverage, CLI checks, tests, suite automation, package publication, or code-contract validation without separate current evidence.

## Output Requirements

- Include evidence.
- Include failures.
- Include blockers.
- Include skipped_checks or skipped checks.
- Include residual_risk or residual risk.
- Include claim_boundary or claim boundary.

## SkillGuard Maintenance

Refresh this fixture if frontmatter requirements or check-skill failure vocabulary change.
