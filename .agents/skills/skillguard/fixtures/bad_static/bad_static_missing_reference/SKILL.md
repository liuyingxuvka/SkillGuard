---
name: "bad_static_missing_reference"
description: "Negative fixture for a missing declared reference."
---

# Bad Static Missing Reference Fixture

## Purpose

Isolate the static-analysis failure caused by a declared but missing local reference.

## Entrypoint Scope

This fixture is intentionally defective only through the declared reference `missing_static_reference.json`, which is not present in this fixture directory.

## Local Material Routing

- Fixture metadata: `.skillguard/skillguard_manifest.json`
- Fixture evidence: `.skillguard/evidence/current_evidence_manifest.json`
- Fixture report: `.skillguard/reports/current_check_report.json`
- Missing reference under test: `missing_static_reference.json`

## Entrypoint Acceptance Map

- Expected decision: `fail`
- Intended failed branch: declared-reference resolution.

## Use When

- A local fixture-test run needs the missing-reference static failure branch.
- A reviewer needs to verify that a missing declared reference stays a fail-class result.

## Do Not Use When

- A task needs a passing skill fixture.
- A task needs blocker, boundary, stale, release, package publication, suite automation, or code-contract validation evidence.

## Required Workflow

1. Run `check-skill` against this fixture through `fixture-test` or directly.
2. Confirm the observed decision is `fail`, not `block`.
3. Confirm the failure detail names `missing_static_reference.json`.
4. Keep evidence, failures, blockers, skipped_checks, residual_risk, and claim_boundary separate.

## Hard Gates

- Do not reinterpret this static defect as a blocker condition.
- Do not add the missing reference file unless this fixture is being intentionally retired.
- Do not claim runtime checker execution, fixture coverage, CLI checks, tests, suite automation, package publication, or code-contract validation without separate current evidence.

## Output Requirements

- Include evidence.
- Include failures.
- Include blockers.
- Include skipped_checks or skipped checks.
- Include residual_risk or residual risk.
- Include claim_boundary or claim boundary.

## SkillGuard Maintenance

Refresh this fixture if declared-reference behavior or check-skill failure vocabulary changes.
