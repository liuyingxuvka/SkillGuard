---
name: skillguard-global-router
description: Use only to build, refresh, inspect, or repair the private author-side SkillGuard registry and its managed global prompt projection from explicit maintained source roots.
---

# SkillGuard Global Router

## Purpose

This maintainer-computer router selects an explicitly registered author source for SkillGuard maintenance. It is not a consumer runtime dependency, a domain router, an evidence combiner, or proof that any target check ran.

## Use when

- Building, refreshing, checking, or repairing the private maintained-source registry.
- Installing or checking the compact managed SkillGuard author block in global `AGENTS.md`.
- Onboarding one explicit author source after its maintenance unit and current contract trio exist.

## Do not use when

- An installed consumer skill is performing ordinary domain work.
- Membership would be inferred by scanning `$CODEX_HOME/skills` or another consumer directory.
- Official OpenSpec, a target's native workflow, or its domain template would be selected or governed.
- Receipts, checks, or closure would be shared between maintenance units.

## Required inputs

Every build/refresh receives one or more explicit `--skill-root` paths resolving to author sources. Each routable source must declare:

- `repository_role: skill_maintainer_source`;
- one maintenance unit and member binding;
- current `.skillguard/contract-source.json`, `compiled-contract.json`, and `check-manifest.json`;
- exact native route/check bindings and clean consumer boundary.

An uncontracted source is skipped, never silently adopted. A missing, stale, ambiguous, or duplicate source blocks that route.

## Workflow

1. Freeze the explicit author roots and private registry/managed-prompt targets.
2. Run `refresh-global-router` once; it discovers only those roots, builds the current registry, projects the compact managed block, activates transactionally, and checks currentness.
3. Use `check-global-registry` with the same explicit roots for a separate read-only audit.
4. Read the selected source skill's own `SKILL.md` and conditional references. The registry points to the owner; it does not carry the owner's full manual.
5. Report registry hash/path, inspected and skipped roots, selected source, blockers, global block currentness, and bounded claim.

```powershell
python .agents/skills/skillguard/scripts/skillguard.py refresh-global-router --skill-root <explicit-author-skill-root> --codex-home <codex-home>
```

## Hard gates

- No installed-consumer scan or fallback root.
- No official OpenSpec registration.
- No cross-unit receipt import, sharing, projection, or graduation gate.
- No global route catalog or validated-template lifecycle duplicated in the always-loaded block.
- No global router selection of a target domain template.
- No registry hash, prompt block, or source path used as proof of checks, installation, Git/tag/release, or future behavior.
- No direct edits to the managed global block; regenerate it from current explicit sources.

## Output

Return the registry identity, explicit roots, current/blocked/skipped source rows, selected author source and native route pointer, compact prompt currentness, consumer-independence boundary, and all separate unverified claims.

The router selects only where registered author maintenance begins. Each target keeps its own checks and evidence, and each consumer remains standalone.
