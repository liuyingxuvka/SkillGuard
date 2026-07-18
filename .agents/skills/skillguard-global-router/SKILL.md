---
name: skillguard-global-router
description: "Use when maintaining the private author-side SkillGuard registry, its managed AGENTS prompt projection, or explicit maintained-skill onboarding."
---

# SkillGuard Global Router

## Purpose

This router is a maintainer-computer index. It helps an author select an
explicitly registered skill source for SkillGuard maintenance. It is not part of
the graduated skill and is not a runtime dependency of consumer machines or
ordinary projects.

Each current entry points to an author-side source with a current maintenance
contract trio:

- `.skillguard/contract-source.json`
- `.skillguard/compiled-contract.json`
- `.skillguard/check-manifest.json`

Those files prove what SkillGuard is checking while the skill is being
maintained. A consumer distribution deliberately excludes them.

Official OpenSpec is external and unmanaged. Do not add its official skills to
this registry and do not project SkillGuard authority into OpenSpec.

## Use When

Use this skill when the user asks to:

- build, refresh, inspect, or repair the private author-side maintained-skill
  registry;
- route SkillGuard maintenance work to an explicitly covered skill source;
- install or check the maintainer-only managed AGENTS prompt block;
- onboard a new maintained skill source after its maintenance unit and contract
  are explicit;
- verify that a registry entry still matches its author-side source.

## Do Not Use When

Do not use this skill:

- before ordinary use of an installed consumer skill;
- to scan every installed skill and infer that SkillGuard owns it;
- to require `.skillguard`, SkillGuard commands, receipts, imports, router
  state, or Portfolio state in a consumer distribution;
- to maintain or wrap official OpenSpec;
- to replace a target skill's domain workflow or native checks;
- to make execution, publication, release, or future-AI-behavior claims.

## Author-Side Inputs

Every scan/build/refresh must receive one or more explicit `--skill-root`
values that resolve to maintainer sources. No command may fall back to
`~/.codex/skills` or another installed-consumer directory.

A routable author source must declare:

- `repository_role: skill_maintainer_source`;
- one non-empty `maintenance_unit_id`;
- its `skill_id` in `member_skill_ids`;
- the current contract trio and exact native route/check bindings.

An uncontracted directory is skipped, not silently adopted. An external
exclusion such as official OpenSpec remains outside the registry.

## Required Workflow

1. Identify the explicit author-side roots and the private registry location.
2. Run `refresh-global-router` with repeated `--skill-root` arguments. This
   single author-only command scans, builds, projects, installs, and checks the
   private maintainer block.
3. Run `check-global-registry` against the same explicit roots when a separate
   read-only registry audit is needed.
4. Read the selected source skill's `SKILL.md`; invoke SkillGuard maintenance
   only because that source is explicitly registered.
5. Report registry identity, inspected roots, skipped unmaintained sources,
   failures, blockers, and the author-only claim boundary.

## Maintenance-Unit Boundary

The router selects a source; it does not combine evidence.

- Every maintenance unit owns its members, semantic checks, evidence subjects,
  run state, and receipts.
- A receipt may be reused only inside the same unit under the exact full
  identity.
- Different units never import, share, or project one another's receipts, even
  if commands and inputs are identical.
- Apparent semantic overlap is a source-boundary defect. Split, merge, or retire
  the declarations instead of creating shared proof.

## Consumer Boundary

Graduation produces a clean standalone distribution containing only the
target-owned files needed for domain work. It must exclude:

- `.skillguard/**`;
- SkillGuard imports and command invocations;
- SkillGuard run/receipt references;
- router/registry and Portfolio state;
- author-only tests, fixtures, models, plans, and maintenance notes unless the
  target itself explicitly owns them as runtime material.

The installed skill reads its own `SKILL.md` and follows its own native
workflow. Missing SkillGuard on the consumer machine is a valid and expected
state.

## Hard Gates

- No implicit installed-skill scan.
- No current registry entry without the exact author role, unit, member, and
  contract bindings.
- No official OpenSpec entry.
- No consumer-runtime handoff through maintenance contracts.
- No cross-unit receipt consumption.
- No duplicated/corrupted managed prompt markers.
- No private absolute paths or credentials in portable registry output.

## Output Requirements

Reports include:

- private registry path and hash;
- explicit author roots;
- selected maintenance unit/member;
- current/skipped/blocked entries;
- prompt projection/check status when applicable;
- failures, blockers, skipped checks, residual risk, and claim boundary.

## SkillGuard Maintenance

Changes to this router must keep its source contract, implementation, schema,
template, tests, and documentation synchronized. Ordinary use of a consumer
skill never activates this maintenance workflow.
