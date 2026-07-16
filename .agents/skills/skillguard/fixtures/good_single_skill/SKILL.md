---
name: "good_single_skill"
description: "Positive maintained SkillGuard single-skill fixture."
---

# Good Single Skill Fixture

## Purpose

Exercise the maintained single-skill happy path for SkillGuard with one current contract authority and bounded static claims.

## Entrypoint Scope

Use this fixture only as a local positive fixture for SkillGuard checker behavior. It is intentionally small and does not represent a released skill package.

## Local Material Routing

- Skill entrypoint: `SKILL.md`
- Control root: `.skillguard`
- Current source: `.skillguard/contract-source.json`
- Current compiled contract: `.skillguard/compiled-contract.json`
- Exact check manifest: `.skillguard/check-manifest.json`
- Target-owned check: `scripts/run_checks.py`

## Entrypoint Acceptance Map

- The fixture passes when required sections, the complete current trio, exact target-owned check, and bounded claim language are present.
- The fixture blocks when the current trio is incomplete or any former runtime surface is introduced.

## Use When

- A SkillGuard worker or reviewer needs a maintained single-skill positive fixture.
- A local fixture-test or check-skill run needs a current fixture target.

## Do Not Use When

- The task needs negative, stale, blocked, or regression fixture behavior.
- The task needs release, package publication, suite automation evidence, broad fixture families, or code-contract validation evidence.

## Required Workflow

1. Inspect `SKILL.md` and the current source/compiled/manifest trio before making any fixture claim.
2. Run the local `check-skill` command against this fixture directory when current pass evidence is needed.
3. Run only the exact target-owned check when execution evidence is required.
4. Keep reports, receipts, logs, timestamps, and status records outside maintained fixture source identity.
5. Report evidence, failures, blockers, skipped_checks, residual_risk, and claim_boundary separately.

## Hard Gates

- Do not claim runtime checker execution, fixture coverage, CLI checks, tests, suite automation, package publication, or code-contract validation without separate current evidence.
- Do not use absolute local paths, private runtime ids, PM text, reports, or progress records as maintained source or closure proof.
- Do not add a fallback, compatibility reader, converter, migration command, alias, or parallel current authority.
- Do not hide failures, blockers, skipped checks, or residual risk behind a generic positive summary.

## Output Requirements

- Include evidence.
- Include failures.
- Include blockers.
- Include skipped_checks or skipped checks.
- Include residual_risk or residual risk.
- Include claim_boundary or claim boundary.

## SkillGuard Maintenance

Update this fixture directly when current checker schema requirements or required skill sections change. Invalidate only the exact affected owner, keep generated command output outside maintained source, and keep the claim boundary conservative.
