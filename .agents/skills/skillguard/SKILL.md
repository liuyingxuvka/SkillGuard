---
name: skillguard
description: Use for authoring, maintaining, checking, graduating, installing, or releasing explicitly registered Codex skill sources. SkillGuard supervises author-side contracts and target-owned evidence; it is not a consumer runtime dependency.
---

# SkillGuard

## Purpose

SkillGuard supervises maintenance of explicitly registered skill sources. A target skill declares its own promises, completion/depth criteria, native checks, evidence subjects, a reverse implementation-surface inventory, and clean consumer material. SkillGuard verifies that those exact declarations, execution receipts, projections, and closure agree; it does not invent deeper domain criteria or reinterpret the target's result. A declared-check list without a current surface inventory is incomplete and cannot graduate.

Graduated consumer skills must work from their own `SKILL.md`, scripts, references, assets, and native checks with no SkillGuard dependency.

## Entrypoint Scope

Admit a task only when all are explicit:

- a source repository declares `repository_role: skill_maintainer_source`;
- one non-empty maintenance unit and exact member skill ids are current;
- the current contract trio exists: `.skillguard/contract-source.json`, `.skillguard/compiled-contract.json`, `.skillguard/check-manifest.json`;
- private run-state and evidence roots remain outside the consumer projection;
- the request is author maintenance, not ordinary domain use of an installed skill.

SkillGuard does not maintain official OpenSpec, infer ownership by scanning installed consumers, add `.skillguard` to ordinary projects, or share receipts between maintenance units.

## Use When

- Creating or changing a registered skill's author contract, prompt, scripts, references, models, checks, installation, or release.
- Freezing and executing affected-only or final validation for one maintenance unit.
- Auditing completion/depth evidence, blockers, stale receipts, check ownership, or consumer isolation.
- Adding, removing, splitting, merging, retiring, graduating, installing, or releasing a maintained skill/unit.
- Maintaining the private Portfolio or global author-side router.

## Do Not Use When

- An installed consumer skill is simply doing its domain job.
- A third-party or ordinary project only happens to use a maintained skill.
- Official OpenSpec is proposing, designing, applying, syncing, or archiving a change.
- A test or receipt would be imported from another maintenance unit.
- A target's domain semantics, purpose, protected failures, fixtures, or closure criteria would be invented by SkillGuard.

## Minimum task facts

Extract facts with source locations; do not ask the AI whether it understands:

- author repository, maintenance unit, member skill, and current contract identities;
- requested action/command family and whether it reads or writes;
- target-owned obligations/checks/evidence subjects and dependencies;
- source/toolchain/input/environment identities and current receipt status;
- consumer projection and requested install/release boundary;
- explicit unavailable authority, cleanup, or external blockers.

Missing facts remain visible. A route is not chosen by a weighted keyword score.

## Entrypoint Acceptance Map

Use the deterministic `route-task` command to evaluate the current registry without loading its complete catalog into the prompt. Read [references/skillguard-route-index.json](references/skillguard-route-index.json) only when auditing the registry projection, investigating a blocked route, or regenerating it.

1. Prefer one explicit current route id/command family.
2. Otherwise derive typed request facts and evaluate declared positive and forbidden predicates.
3. Require exactly one matching route for a single command decision. Zero, many, stale, conflicting, missing-input, or forbidden results block with the exact candidate/fact set.
4. Verify the selected route's read/write authority, first command, next reference, conditional references, and claim boundary.
5. Load only the returned `load_order` before acting; all `excluded_by_default` material stays unloaded.

Text cues may be recorded as typed source-span evidence, but no cue weight, strongest-score tie-break, failure retry, compatibility alias, or fallback may authorize a route.

Use `route-task` for a deterministic route record. It does not prove the selected command executed or closed:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py route-task --task <public-safe-task> --route-hint <current-route>
```

## Local Material Routing

- One maintenance-unit supervision and closure: [references/skillguard-supervisor.md](references/skillguard-supervisor.md).
- Target-owned completion/depth identity: [references/skillguard-execution-depth.md](references/skillguard-execution-depth.md).
- Large, layered, affected-only, or full validation: [references/skillguard-test-mesh.md](references/skillguard-test-mesh.md).
- Read-only blocker explanation: [references/skillguard-assurance-diagnostics.md](references/skillguard-assurance-diagnostics.md).
- Persistent receipt records: [references/skillguard-execution-records.md](references/skillguard-execution-records.md).
- Private multi-unit inventory/graduation: [references/skillguard-portfolio.md](references/skillguard-portfolio.md).
- Author repository adoption/audit: [references/skillguard-project-adoption.md](references/skillguard-project-adoption.md).
- Clean consumer preparation, activation, rollback, recovery, and currentness: [references/skillguard-target-installation.md](references/skillguard-target-installation.md).
- SkillGuard's own governed maintenance: [references/skillguard-self-host.md](references/skillguard-self-host.md).
- A target that explicitly declares validated-template-pack support: [references/validated-template-pack.md](references/validated-template-pack.md).

Do not load Portfolio, installation, self-host, template-pack, or release material for an unrelated read-only unit check.

## Required Workflow

1. Establish the author boundary and freeze one maintenance unit.
2. Compile the direct-current contract source into the compiled contract and exact check manifest. Former formats are rejection-only; there is no converter or dual reader.
3. Freeze every check, obligation/evidence domain, dependency, subject, private evidence root, and exactly one execution owner.
4. Reuse a terminal-success receipt only inside the same unit when unit/member/owner/request/inputs/dependencies/toolchain/environment/policy and consumer projection identities are exact.
5. Execute missing owners under single-flight ownership. Skipped, failed, stale, timed-out, cancelled, cleanup-unconfirmed, or non-terminal evidence blocks.
  6. Require the target's enforced closure, model-deepening check, and current
     surface-inventory/adequacy binding. The target decides domain closure;
     SkillGuard verifies only discovered surfaces and typed dispositions.
    A pass requires replaying the canonical terminal receipt against identity,
    owner, inputs, dependencies, toolchain, environment, obligations, and cleanup;
    caller results, logs, and fixtures never close.
  7. Reverse discovery belongs to the maintained target's author surface and
     must cover public commands/routes/APIs, effects, faults, recovery, installers,
     configuration, UI-like actions, and behavior-significant helpers through
     governed components. Forward intent/model/test obligations and reverse
     observations meet at a reviewable surface/component boundary: a line, local
     variable, or incidental helper needs no intent row unless independently
     meaningful. A visible control, effect, fault, recovery path, or implementation
     surface without intent, owner, check, and evidence is a blocking gap; this
     does not make SkillGuard a consumer runtime dependency. Unknown, orphan,
     ambiguous, or one-way rows block.
    Each row carries `surface_id`, kind, source+fingerprint, component, intent,
    route, obligations, owners, checks, adequacy, evidence, fault/recovery/oracle,
    disposition, and proof. Groups enumerate every member and share owner/oracle;
    stale, unknown, one-way, or resealed rows block. Identity mismatch requires a
    direct-current rewrite; former formats reject, never becoming another authority.
  8. Build a clean target-owned consumer projection and audit it with SkillGuard absent.
  9. Prepare/activate installation transactionally; verify installation currentness separately.
  10. Update Portfolio/router only when affected; they never make another unit current.
  11. Report exact checked, executed, reused, skipped, blocked, consumer, install, release, and residual boundaries.

## Terminals

- `current`: exact author source, contract, owner evidence, closure, and requested projection are current within the declared boundary.
- `blocked`: an authority, identity, inventory, dependency, evidence, depth, distribution, cleanup, or route condition is incomplete or ambiguous.
- `graduated`: the named unit satisfies its target-owned criteria and its clean standalone consumer audit passes.
- `installed-current`: one prepared consumer projection was transactionally activated and separately replayed against current target identity.

Progress, a PID, a log, generated prompt text, an old receipt, or prose cannot create a terminal.

## Hard Gates

- No explicit author role/unit/member/contract trio: no write or validation.
- No explicit private run/evidence roots: no supervision.
- No semantic owner, duplicate owner, foreign-unit dependency/receipt, or cyclic plan: block.
- No functional-closure pass without a current canonical terminal receipt replay.
- No compatibility reader, fallback, migration command, alias, dual manifest, or alternate current authority.
- No `.skillguard`, SkillGuard command/import/receipt/router/Portfolio state, author path, or author-only fixture/model/test in a consumer projection.
- No target runtime hidden inside a retired private maintenance-runtime directory.
- No `--resume` described or used as read-only; it may execute missing owners.
- No final full validation before source, toolchain, and impact-plan freeze; exactly one owner runs it.
- After timeout/cancellation, no evidence reuse or new owner until the entire descendant process tree is confirmed zero.
- No Windows Scheduled Task, unattended retry, or background resume for a mutable full validation.
- No read-only installation currentness check that launches smoke/validation.
- No stale GC plan, reachable evidence, active store, failed replay, or unauthorized purge.
- No template selection by SkillGuard: ask the target for a current native route receipt and target-authored applicability; zero/many/stale/forbidden/field-conflict results block.
- No installation, source, package/runtime, receipt, router, Git, tag, or GitHub Release identity substituted for another.

## Output Requirements

Every result states:

- safe author repository, unit, member, route, and selected reference identities;
- exact checks/owners/obligations/evidence subjects and their executed/reused/skipped status, including a `skipped_checks` list;
- immutable receipt/currentness status and cleanup state;
- target-owned closure/depth result without reinterpretation;
- clean consumer audit and install state when requested;
- source/package/router/install/Git/tag/release identities separately;
- blockers, residual risk, and claim boundary.

## SkillGuard self-maintenance

For SkillGuard itself, use OpenSpec first, ground the change in current FlowGuard models, keep source/compiled contract/check manifest/runtime/schemas/fixtures/tests/references/router/installation synchronized, run affected checks during development, and run one full self-host validation only after freeze. Never restore installed-skill scanning, cross-unit reuse, prior-unit graduation gates, ordinary-project adoption, or an OpenSpec receipt bridge.
