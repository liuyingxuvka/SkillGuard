---
name: "bad_static_unsafe_broad_claim"
description: "Negative fixture for unsupported broad claim text."
---

# Bad Static Unsafe Broad Claim Fixture

## Purpose

Isolate the static-analysis failure caused by unsupported broad claim wording.

## Entrypoint Scope

Fixture coverage complete.

The sentence above is intentionally unsupported fixture-local test material. All other structure is present so the observed failure is attributable to the unsafe broad-claim branch.

## Local Material Routing

- Fixture metadata: `.skillguard/skillguard_manifest.json`
- Fixture evidence: `.skillguard/evidence/current_evidence_manifest.json`
- Fixture report: `.skillguard/reports/current_check_report.json`

## Entrypoint Acceptance Map

- Expected decision: `fail`
- Intended failed branch: unsupported broad-claim phrase scanning.

## Use When

- A local fixture-test run needs the unsafe broad-claim static failure branch.
- A reviewer needs to verify that unsupported broad claim wording stays a fail-class result.

## Do Not Use When

- A task needs a passing skill fixture.
- A task needs blocker, boundary, stale, release, package publication, suite automation, or code-contract validation evidence.

## Required Workflow

1. Run `check-skill` against this fixture through `fixture-test` or directly.
2. Confirm the observed decision is `fail`, not `block`.
3. Confirm the failure detail names the unsafe broad-claim phrase branch.
4. Keep evidence, failures, blockers, skipped_checks, residual_risk, and claim_boundary separate.

## Hard Gates

- Do not reinterpret this static defect as a blocker condition.
- Do not move the unsupported broad claim sentence into public README, release, package, or good-fixture surfaces.
- Do not claim runtime checker execution, fixture coverage, CLI checks, tests, suite automation, package publication, or code-contract validation without separate current evidence.

## Output Requirements

- Include evidence.
- Include failures.
- Include blockers.
- Include skipped_checks or skipped checks.
- Include residual_risk or residual risk.
- Include claim_boundary or claim boundary.

## SkillGuard Maintenance

Refresh this fixture if unsupported claim phrase rules or check-skill failure vocabulary change.
