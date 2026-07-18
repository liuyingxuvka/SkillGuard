---
name: skillguard
description: "Use when authoring, maintaining, checking, graduating, installing, or releasing explicitly registered Codex skills. SkillGuard is author-side supervision, not a consumer runtime dependency."
---

# SkillGuard

## Purpose

SkillGuard is the school and graduation exam for other skills.

On the maintainer computer it helps each explicitly covered skill state:

- what it promises;
- what it protects;
- what “finished” means;
- how deep execution must go;
- which target-owned checks prove those claims.

SkillGuard then checks that the declarations, execution, evidence, and closure
agree. When the skill graduates, SkillGuard builds a clean standalone consumer
distribution. The graduated skill must work without SkillGuard.

SkillGuard is not a shared runtime, a universal project plugin, or a receipt
service for unrelated skills.

## Entrypoint Scope

This entrypoint governs SkillGuard itself and author-side maintenance of
explicitly registered skill sources.

It may create and consume the private .skillguard author tree only in a source repository whose
role is `skill_maintainer_source`. It may keep private run state, receipts,
Portfolio state, and routing state outside target consumer trees.

It must not:

- add `.skillguard` to an ordinary business/project repository;
- require SkillGuard on a consumer machine;
- copy SkillGuard contracts, receipts, router state, or Portfolio state into a
  graduated skill;
- infer ownership merely because a skill is installed;
- maintain, wrap, or replace official OpenSpec;
- let one maintenance unit use another unit's tests or receipts.

## Local Material Routing

- The author-side current contract is exactly
  `.skillguard/contract-source.json`,
  `.skillguard/compiled-contract.json`, and
  `.skillguard/check-manifest.json`.
- Read `references/skillguard-supervisor.md` for one maintenance-unit
  supervision run.
- Read `references/skillguard-execution-depth.md` for completion and depth
  evidence.
- Read `references/skillguard-test-mesh.md` for planning and executing the
  checks owned by one maintenance unit.
- Read `references/skillguard-portfolio.md` for the private inventory of
  independently maintained units.
- Read `references/skillguard-project-adoption.md` for author-repository
  adoption. This route is maintainer-only.
- Read `references/skillguard-target-installation.md` for clean consumer
  distribution staging, activation, rollback, and recovery.
- Use `scripts/skillguard_supervise.py` with explicit author run-state and
  evidence roots.
- Use `scripts/skillguard_test_mesh.py` for one unit's frozen check plan.
- Use `scripts/skillguard_consumer_install.py` for a clean standalone consumer
  installation.
- Use the `maintainer-adopt` and `maintainer-audit` author commands only for
  explicit author repositories.
- Use the `skillguard-global-router` skill only for the private maintainer
  routing registry and managed maintainer prompt.

## Entrypoint Acceptance Map

- `author-source-current`: the source declares
  `repository_role: skill_maintainer_source`, one maintenance unit, its member
  skills, and the exact current contract trio.
- `unit-checked`: every member's semantic checks have current evidence under
  that same unit and exact full identity.
- `graduated`: the unit has complete/deep evidence and a clean consumer
  projection audit passes.
- `installed-current`: the clean consumer projection was transactionally
  activated and matches its target-owned release identity.
- `blocked`: authority, identity, inventory, dependency, evidence, depth,
  distribution, or cleanup is incomplete or ambiguous.

No prose-only assertion turns a state into `current`.

## Use When

Use this skill when the user asks to:

- create or maintain a skill's author-side promise/contract;
- check whether a declared capability was fully and deeply executed;
- add, remove, rename, split, merge, or retire a maintained skill or
  maintenance unit;
- run affected-only or final validation for one maintained unit;
- prepare, audit, install, synchronize, release, or graduate a maintained
  skill;
- inspect whether multiple locally maintained skills have overlapping
  responsibilities or tests;
- maintain SkillGuard's private Portfolio or maintainer routing registry;
- repair an author repository's SkillGuard maintenance instructions.

## Do Not Use When

Do not start SkillGuard for:

- ordinary domain use of an already graduated/installed consumer skill;
- an unrelated project that merely happens to use a maintained skill;
- official OpenSpec proposal, design, spec, task, apply, sync, or archive work;
- checking third-party skill conflicts on another person's computer;
- sharing a test or receipt between maintenance units;
- treating similar command text as proof that two skills own the same
  responsibility.

If two locally maintained skills appear to promise the same semantic behavior,
stop and repair the boundary: split the promise, merge the units, or retire one
owner. Do not build shared proof.

## Required Workflow

1. Confirm the author boundary before any write.

   The target source must declare `skill_maintainer_source`, a non-empty
   `maintenance_unit_id`, and `member_skill_ids`. The skill root and target
   root must be inside that author repository. Run-state and evidence roots
   must be explicit, private, and outside the consumer target.

2. Freeze one maintenance unit.

   Record its unit id, members, promises, obligations, semantic checks,
   evidence subjects, dependency order, consumer projection, and exclusions.
   Official OpenSpec belongs in the exclusions, never the managed members.

3. Check semantic boundaries.

   Every check belongs to exactly one member and one maintenance unit. Different
   units may not depend on, import, project, or reuse one another's receipts.
   Similar commands do not create a shared owner.

4. Compile the author-side contract.

   Compile the exact current source into the compiled contract and check
   manifest. Former formats are rejection-only; there is no converter,
   fallback, dual reader, or compatibility success route.

5. Freeze the unit's validation plan.

   List every exact check, covered obligation/evidence domain, dependencies,
   persistent private evidence root, and one execution owner. Missing,
   duplicated, foreign-unit, cyclic, or ambiguous ownership blocks before
   execution.

6. Resolve exact same-unit evidence.

   A terminal-success receipt may be reused only when maintenance unit, member,
   evidence subject, semantic check, owner, request, inputs, dependencies,
   toolchain, environment, and policy identities all match. Otherwise execute
   the unit's own check.

7. Execute and close.

   Execute missing owners, preserve immutable results, confirm process-tree
   cleanup after timeout/cancellation, and require the target-owned native
   checks plus fixed enforced closure. Skipped, failed, stale, timed-out,
   cancelled, cleanup-unconfirmed, or non-terminal evidence blocks.

8. Build the consumer distribution.

   Include only target-owned runtime material. Exclude the complete private
   .skillguard author tree,
   SkillGuard imports/commands/receipts, router/Portfolio state, and author-only
   tests, fixtures, models, plans, and notes. Block if target runtime is still
   hidden under the retired author-runtime location named .skillguard/runtime.

9. Audit independence.

   Verify that the consumer tree can be understood and used from its own
   `SKILL.md`, scripts, references, assets, and native checks. Missing
   SkillGuard on the consumer machine must be a valid expected condition.

10. Install or release transactionally.

    Stage the clean projection, verify its target-owned identity, activate it,
    and retain rollback/recovery. Installation must not create `.skillguard`
    in the installed skill or any ordinary project.

11. Update private maintenance indexes only when affected.

    Portfolio and the maintainer router may record the unit's author-side
    status. They cannot make another unit current and cannot export their state
    to consumers.

12. Report the exact claim boundary.

    State what was checked, what executed, what was skipped, which evidence is
    current, whether the consumer distribution is clean, and what remains
    blocked.

## Maintenance Unit and Evidence Rules

- One maintenance unit may contain one skill or a deliberately inseparable
  suite.
- Each member has its own semantic check ids and evidence subjects.
- Same-unit single-flight is allowed only under the exact full identity.
- Cross-unit receipt consumption is always forbidden.
- Unrelated units stay current after a change that has no component edge to
  them; they need neither rerun nor a “reuse ticket.”
- Affected units rerun their own checks.
- Portfolio graduation proves only the named unit. It never cites an earlier
  unit's result as an authorization condition.

## Official OpenSpec Boundary

OpenSpec is an external requirements provider.

SkillGuard may read a stable OpenSpec proposal/design/spec/tasks/status artifact
when a maintained skill's author workflow needs requirements context. It must
not create an OpenSpec receipt bridge, session/cache authority, execution owner,
SkillGuard contract, or installed dependency. OpenSpec's official skills remain
official and independent.

## Consumer Distribution Rules

A consumer release is target-owned. Its release identity may include:

- target skill id/version;
- target-owned file inventory and hashes;
- target-owned entrypoint/native-check declarations;
- installation transaction identity.

It must not contain:

- SkillGuard contract or manifest hashes;
- maintenance unit ids;
- SkillGuard receipt/run ids;
- author repository paths;
- SkillGuard command instructions;
- global router or Portfolio bindings.

## Hard Gates

- No author role/unit/member binding: no write and no execution.
- No explicit private run/evidence roots: no supervision.
- No cross-unit dependency or receipt: block.
- No semantic owner for a check: block.
- Duplicate semantic ownership across units: repair the boundary first.
- `.skillguard` in a consumer distribution: block.
- target runtime under the retired .skillguard/runtime author location: block
  until moved.
- SkillGuard import/command/receipt/router/Portfolio reference in a consumer
  distribution: block.
- ordinary project adoption/write: block.
- official OpenSpec enrolled as a maintained target: block.
- source identity unknown: block destructive withdrawal until the canonical
  author source is established.
- timeout/cancellation without zero descendants confirmed: evidence invalid.
- final full validation before source/toolchain/plan freeze: invalid.

## Output Requirements

Every result states:

- the author repository and maintenance unit/member identities using safe path
  labels;
- the route and exact checks considered;
- evidence and receipt status;
- failures and blockers;
- skipped checks with reasons;
- consumer-distribution audit status;
- installation/release status when requested;
- residual risk;
- a claim boundary that distinguishes author-side proof from consumer runtime
  behavior.

## SkillGuard Maintenance

When SkillGuard itself changes:

- update its OpenSpec change artifacts first;
- update the existing FlowGuard models that own the affected behavior;
- keep contract source, compiled contract, manifest, implementation, schemas,
  fixtures, tests, references, router prompt, and installation projection
  synchronized;
- run affected validation during development;
- run one final full validation only after source/toolchain/impact identities
  are frozen;
- keep the author-side SkillGuard installation separate from clean consumer
  installations;
- never restore retired installed-skill scanning, cross-unit reuse tickets,
  prior-unit graduation gates, ordinary-project adoption, or OpenSpec receipt
  bridges.
