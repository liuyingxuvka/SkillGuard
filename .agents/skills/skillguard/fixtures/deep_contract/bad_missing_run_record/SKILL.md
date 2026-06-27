---
name: missing-run-fixture
description: Runtime contract fixture requiring current run evidence.
---

# Missing Run Fixture

## Purpose

Use for checking that SkillGuard blocks closure when a non-trivial contract has no current run record.

## Required Workflow

Run records must exist before closure.

## Hard Gates

Do not close without a current run record.
