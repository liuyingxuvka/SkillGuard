---
name: "stale_member"
description: "Suite member fixture for the stale evidence negative case."
---

# Stale Member Fixture

## Purpose

Provide one valid suite member while its member report carries stale evidence metadata.

## Entrypoint Scope

Use this member only inside the local bad_suite_stale_evidence fixture.

## Local Material Routing

- Suite map: `../../suite/suite-map.json`
- Suite contract: `../../suite/suite-contract.json`
- Member report: `../../suite/evidence/stale_member_report.json`

## Entrypoint Acceptance Map

- The member path is valid.
- Suite evidence validation must fail because the member report is stale.

## Use When

- A local fixture needs to show that stale fixture-local evidence cannot support a checked child.

## Do Not Use When

- The task needs package, release, or broad suite automation evidence.

## Required Workflow

1. Resolve this member under the configured suite member root.
2. Resolve the stale member report.
3. Reject the report when stale timestamps or stale evidence markers are present.
4. Report evidence, failures, blockers, skipped_checks, residual_risk, and claim_boundary separately.

## Hard Gates

- Do not claim runtime checker execution, fixture coverage, CLI checks, tests, suite automation, package publication, or code-contract validation without separate current evidence.
- Do not promote stale report metadata to closure proof.

## Output Requirements

- Include evidence.
- Include failures.
- Include blockers.
- Include skipped_checks or skipped checks.
- Include residual_risk or residual risk.
- Include claim_boundary or claim boundary.

## SkillGuard Maintenance

Refresh this member when evidence freshness or stale-report semantics change.
