---
name: "router_member"
description: "Suite member fixture for the missing suite-map negative case."
---

# Router Member Fixture

## Purpose

Provide one member skill for the missing suite-map negative fixture.

## Entrypoint Scope

Use this member only inside the local bad_suite_router_without_map fixture.

## Local Material Routing

- Suite contract: `../../suite/suite-contract.json`
- Member evidence: `../../suite/evidence/router_member_report.json`

## Entrypoint Acceptance Map

- The member path is valid when `SKILL.md` exists and direct evidence is present.
- The suite still fails when the suite map record is absent.

## Use When

- A local fixture needs a valid suite member while isolating a missing suite-map defect.

## Do Not Use When

- The task needs release, package, or broad automation evidence.

## Required Workflow

1. Resolve this member under the configured suite member root.
2. Resolve direct evidence from the suite contract.
3. Keep the missing suite map as the only intended suite-record defect.
4. Report evidence, failures, blockers, skipped_checks, residual_risk, and claim_boundary separately.

## Hard Gates

- Do not claim runtime checker execution, fixture coverage, CLI checks, tests, suite automation, package publication, or code-contract validation without separate current evidence.
- Do not use stale history, PM text, or runtime ids as closure proof.

## Output Requirements

- Include evidence.
- Include failures.
- Include blockers.
- Include skipped_checks or skipped checks.
- Include residual_risk or residual risk.
- Include claim_boundary or claim boundary.

## SkillGuard Maintenance

Refresh this member when suite fixture status vocabulary or member-root rules change.
