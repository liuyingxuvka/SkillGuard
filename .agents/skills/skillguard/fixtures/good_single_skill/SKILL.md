---
name: "good_single_skill"
description: "Positive maintained SkillGuard single-skill fixture."
---

# Good Single Skill Fixture

## Purpose

Exercise the maintained single-skill happy path for SkillGuard with direct local evidence and bounded closure data.

## Entrypoint Scope

Use this fixture only as a local positive fixture for SkillGuard checker behavior. It is intentionally small and does not represent a released skill package.

## Local Material Routing

- Skill entrypoint: `SKILL.md`
- Control root: `.skillguard`
- Direct evidence: `.skillguard/evidence/current_evidence_manifest.json`
- Current report summary: `.skillguard/reports/good_single_skill_check_report.json`
- Closure data: `.skillguard/reports/good_single_skill_closure.json`

## Entrypoint Acceptance Map

- The fixture passes when required sections, local control records, direct evidence, and bounded claim language are present.
- The fixture blocks or fails when closure relies on stale history, PM text, runtime ids, or progress-ledger-only proof.

## Use When

- A SkillGuard worker or reviewer needs a maintained single-skill positive fixture.
- A local fixture-test or check-skill run needs a current fixture target with closure data.

## Do Not Use When

- The task needs negative, stale, blocked, or regression fixture behavior.
- The task needs release, package publication, suite automation evidence, broad fixture families, or code-contract validation evidence.

## Required Workflow

1. Inspect `SKILL.md` and `.skillguard` records before making any fixture claim.
2. Run the local `check-skill` command against this fixture directory when current pass evidence is needed.
3. Treat `skillguard_progress_ledger.jsonl` as historical context only.
4. Use direct report and evidence files for closure support.
5. Report evidence, failures, blockers, skipped_checks, residual_risk, and claim_boundary separately.

## Hard Gates

- Do not claim runtime checker execution, fixture coverage, CLI checks, tests, suite automation, package publication, or code-contract validation without separate current evidence.
- Do not use absolute local paths, private runtime ids, PM text, or progress ledgers as closure proof.
- Do not hide failures, blockers, skipped checks, or residual risk behind a generic positive summary.

## Output Requirements

- Include evidence.
- Include failures.
- Include blockers.
- Include skipped_checks or skipped checks.
- Include residual_risk or residual risk.
- Include claim_boundary or claim boundary.

## SkillGuard Maintenance

Refresh this fixture when checker schema requirements, required skill sections, closure policy, or evidence-record expectations change. Keep generated command output outside runtime-only history and keep the claim boundary conservative.
