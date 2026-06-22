---
name: "child_without_closure_member"
description: "Suite member fixture for the child report without direct closure evidence case."
---

# Child Without Closure Member Fixture

## Purpose

Provide one valid suite member while the member report intentionally declares no direct evidence.

## Entrypoint Scope

Use this member only inside the local bad_suite_child_without_closure fixture.

## Local Material Routing

- Suite map: `../../suite/suite-map.json`
- Suite contract: `../../suite/suite-contract.json`
- Member report: `../../suite/evidence/child_without_closure_report.json`

## Entrypoint Acceptance Map

- The member path is valid.
- Suite closure must fail because the member report has no direct evidence entries.

## Use When

- A local fixture needs to show that a checked child cannot support closure without direct evidence.

## Do Not Use When

- The task needs package, release, or broad suite automation evidence.

## Required Workflow

1. Resolve this member under the configured suite member root.
2. Resolve its member report.
3. Reject the report when it lacks direct evidence entries.
4. Report evidence, failures, blockers, skipped_checks, residual_risk, and claim_boundary separately.

## Hard Gates

- Do not claim runtime checker execution, fixture coverage, CLI checks, tests, suite automation, package publication, or code-contract validation without separate current evidence.
- Do not treat an empty report as closure proof.

## Output Requirements

- Include evidence.
- Include failures.
- Include blockers.
- Include skipped_checks or skipped checks.
- Include residual_risk or residual risk.
- Include claim_boundary or claim boundary.

## SkillGuard Maintenance

Refresh this member when child closure rules or report evidence parsing changes.
