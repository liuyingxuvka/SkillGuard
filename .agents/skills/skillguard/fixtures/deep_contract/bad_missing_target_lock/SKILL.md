---
name: missing-target-lock-fixture
description: Runtime contract fixture requiring a target-local lock matrix.
---

# Purpose

Use this fixture when SkillGuard must prove that ordinary covered skills need a target-specific route, stage, check, evidence, and closure matrix.

## Use When

- Use when checking that a covered target cannot pass with source requirements alone.

## Required Workflow

1. Inspect the target entrypoint.
2. Map the route, stage, check, evidence, and closure blocker for every target rule.
3. Fail closure when the target-local matrix is missing.

## Hard Gates

- The work contract must include a target-local coverage matrix.
- The check manifest must cover the matrix checks before closure.
