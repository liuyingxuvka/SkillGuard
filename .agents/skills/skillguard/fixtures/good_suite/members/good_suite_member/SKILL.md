---
name: "good_suite_member"
description: "Positive suite member fixture for SkillGuard suite checks."
---

# Good Suite Member Fixture

## Purpose

Provide one maintained member skill for the good_suite positive suite fixture.

## Entrypoint Scope

Use this member only inside the local good_suite fixture. It is not a standalone release artifact.

## Local Material Routing

- Suite map: `../../suite/suite-map.json`
- Suite contract: `../../suite/suite-contract.json`
- Member evidence: `../../suite/evidence/good_suite_member_report.json`

## Entrypoint Acceptance Map

- The member supports the suite fixture when its `SKILL.md` exists and suite records cite direct current evidence.
- The member does not support suite closure when evidence is stale, missing, or only historical.

## Use When

- A local suite fixture needs a concrete member path with a skill entrypoint.
- A reviewer needs to rerun `check-suite` against a maintained positive suite example.

## Do Not Use When

- The task needs multi-member routing, release publication, or broad suite automation evidence.
- The task needs negative or stale suite member behavior.

## Required Workflow

1. Resolve this member under the configured suite member root.
2. Inspect the member entrypoint and suite records.
3. Resolve direct evidence paths from suite map and contract records.
4. Keep progress ledgers and runtime ids out of closure proof.
5. Report evidence, failures, blockers, skipped_checks, residual_risk, and claim_boundary separately.

## Hard Gates

- Do not claim runtime checker execution, fixture coverage, CLI checks, tests, suite automation, package publication, or code-contract validation without separate current evidence.
- Do not treat the suite fixture as a released or installed package.
- Do not use stale history, PM text, or runtime ids as closure proof.

## Output Requirements

- Include evidence.
- Include failures.
- Include blockers.
- Include skipped_checks or skipped checks.
- Include residual_risk or residual risk.
- Include claim_boundary or claim boundary.

## SkillGuard Maintenance

Refresh this member when the suite map, suite contract, member-root rule, evidence policy, or checker command behavior changes.
