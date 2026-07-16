## Why

SkillGuard currently proves layered maintenance safety by rerunning overlapping checks across direct pytest commands, TestMesh, OpenSpec, staged installation, active installation, and external skill synchronization. This is fail-closed but unnecessarily slow, and inconsistent transient-file and source-fingerprint policies can either ship runtime artifacts or miss non-Python freshness changes.

## What Changes

- Add proof-bound TestMesh child-result reuse that is accepted only when command, complete declared input inventory, environment, manifest, profile/suite ownership, coverage scope, verifier version, and immutable result identities are exact and current.
- Replace Python-only directory fingerprints with a target-declared, content-addressed source inventory that includes every relevant code, schema, fixture, model, contract, and configuration input while excluding only centrally declared runtime artifacts.
- Introduce one shared transient-artifact policy consumed by installation, installed parity, provenance, privacy, compilation/runtime fingerprints, fixture cleanup, and TestMesh; reject runtime workspaces such as `.sg-runtime` as installable content while preserving static nested fixture evidence.
- Make validation fail fast through cheap authority, generated-contract, manifest, and freshness checks before expensive suites, and let downstream gates consume current proof artifacts instead of rerunning identical work.
- Add single-flight check execution with separate semantic-check, concrete-execution, and execution-key identities; only terminal success is reusable and failed attempts cannot populate the success head.
- Make full-parent receipt consumers strictly read-only and fail closed, with no TestMesh execute, resume, repair, or backfill fallback.
- Project one validation-execution ownership policy into maintained prompts: `--resume` remains execution; full runs only after source/toolchain freeze under one owner; interrupted launchers require confirmed zero descendants; Scheduled Task, background resume, and unattended mutable-worktree retry are forbidden.
- Make SkillGuard-maintained OpenSpec verification contracts reject reports, receipts, results, progress logs, and declared evidence roots from source freshness watches, and use non-overlapping check ownership; the OpenSpec runtime-level collision blocker is maintained in its native repository when available.
- Preserve distinct source, stage, installed, synchronized-target, and global-prompt freshness domains. Receipt reuse never turns one domain's proof into another domain's proof and never accepts failed, skipped, timed-out, partial, progress-only, foreign, or stale evidence.
- Replace whole-contract, whole-manifest, whole-source, whole-installation, and caller-declared broad-portfolio invalidation with one compiler-generated content-impact graph. The graph groups maintained files by semantic role, installation disposition, and exact consumer set; unmapped, ambiguously classified, multiply owned, or cyclic rows block before validation instead of falling back to run-all.
- Give every execution owner an exact input-component projection and dependency-receipt set. Parent/profile/report/task-checkbox changes may stale their own projection or aggregation identity, but they do not make unchanged child owners execute again.
- Publish terminal-success owner receipts in a persistent content-addressed evidence root that survives individual runs. `run_id`, `step_id`, timestamps, display text, and parent aggregation identity remain attempt/audit metadata and do not change the semantic execution key.
- Add a genuinely read-only impact-plan preview that lists reused owners, owners to execute, aggregation-only work, affected installation components, router refresh, Portfolio targets, and any derived full-admission reason. Execution must consume the same frozen plan hash.
- Make installation, installed parity, Portfolio impact, and global-router refresh consume projections of the same graph. Ordinary skill use does not invoke SkillGuard; non-trivial skill maintenance or installation enters SkillGuard supervision and validates only affected owners.
- Retire the bounded V1 suite from the daily TestMesh execution path. Historical old-shape artifacts remain exact rejection fixtures only; the runtime accepts one current contract/receipt/impact shape and has no compatibility success fallback.

## Capabilities

### New Capabilities

- `composable-validation-evidence`: Defines exact TestMesh child evidence, proof-bound reuse, fail-fast ordering, non-overlapping validation ownership, parent reattachment, and stale/foreign/failed reuse blockers.
- `portable-artifact-boundary`: Defines a single portable-versus-runtime artifact policy across source fingerprints, installation, parity, provenance, privacy, fixture cleanup, and synchronized skill trees.

### Modified Capabilities

- `universal-execution-depth`: Strengthens canonical source/installed parity so runtime workspaces and test outputs cannot become portable SkillGuard content or alter a target-depth claim.

## Impact

- SkillGuard TestMesh runtime, manifest schema, execution records, CLI, self-host bootstrap, and focused/full validation profiles.
- Shared path classification used by compiler/runtime fingerprints, installer, installed parity, provenance, privacy, fixture workspaces, and synchronization checks.
- FlowGuard validation child model, ModelMesh reattachment, FieldLifecycleMesh rows, DevelopmentProcessFlow freshness rules, and model/test regressions.
- SkillGuard contract compiler/schema, check runner, persistent execution receipts, TestMesh plan compiler, installation/parity projections, Portfolio impact derivation, router prompt projection, and their narrow regressions.
- The active `retire-v1-runtime-compatibility` verification contract and final Guard-family installation/coverage workflow.
- OpenSpec verification lint/runtime in its native source repository if a maintainable local checkout is available; no installed-only patch is treated as a durable source fix.
