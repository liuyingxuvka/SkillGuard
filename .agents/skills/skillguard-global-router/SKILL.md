---
name: skillguard-global-router
description: "Use when maintaining the user-level SkillGuard global skill registry, route selection, managed AGENTS prompt block, or new-skill onboarding defaults."
---

# SkillGuard Global Router

## Purpose

SkillGuard Global Router is the user-level routing layer for Codex skills. It scans installed or repository-local skills, records each skill's SkillGuard contract and route documents, resolves a task to the right skill, and keeps the managed global AGENTS prompt block current.

The router does not replace target skills. It chooses the target skill, resolves its one current SkillGuard authority, then hands control to that skill's `SKILL.md`, contract source, compiled contract, exact check manifest, and declared native route bindings. Anything other than the exact current authority is blocked and has no fallback success route.

Covered skill maintenance is direct current replacement. The router must not publish or select a compatibility reader, migration command, upgrade route, alias, converter, renewal route, or second authority for an older skill shape. Former skill shapes are rejection fixtures only. Compatibility for historical documents, data, or interfaces belongs to an explicitly scoped ordinary-software requirement and its bounded FlowGuard owner; it is never a router fallback for a skill.

## Entrypoint Scope

This `SKILL.md` is the activation entrypoint for global SkillGuard routing and prompt installation work. It covers registry refreshes, global prompt projection, prompt freshness checks, and default onboarding expectations for newly added skills.

It is not a proof that any selected skill has executed, that a target skill's test evidence supports success, or that future AI behavior will follow the route. Those claims require current target-skill evidence.

## Local Material Routing

Use the SkillGuard CLI owned by the `skillguard` skill for all deterministic router operations:

- Use `scan-global-skills` to discover `SKILL.md` files and adjacent SkillGuard route documents.
- Use `build-global-registry` to generate the registry artifact.
- Use `check-global-registry` to verify registry schema and freshness.
- Use `resolve-global-skill` to select exactly one current skill for a task.
- Use `render-global-prompt` to generate the managed prompt projection.
- Use `install-global-prompt` to insert or replace only the managed SkillGuard global router block in the user-level AGENTS prompt file.
- Use `check-global-prompt` to verify the installed block contains the current registry hash.
- Use `refresh-global-router` as the standard end-to-end path for scan, registry, prompt projection, install, and prompt freshness check.

Treat the generated global registry artifact as the source of truth for route selection. Treat the managed AGENTS block as a projection of that registry, not a hand-edited route index.

## Entrypoint Acceptance Map

- Frontmatter: the file starts with closed YAML frontmatter containing `name: skillguard-global-router` and a specific `description`.
- Activation boundary: `Use When` and `Do Not Use When` define global routing scope.
- Local routing: `Local Material Routing` points to SkillGuard CLI commands and separates registry source of truth from prompt projection.
- Workflow: `Required Workflow` orders scan, registry build, prompt render, prompt install, prompt check, and target-skill handoff.
- Gates: `Hard Gates` require freshness checks and block stale global prompt claims.
- Output: `Output Requirements` requires evidence, failures, blockers, skipped checks, residual risk, and claim boundary.
- Maintenance: `SkillGuard Maintenance` says new skills and prompt changes must refresh the global registry and managed AGENTS prompt block.

## Use When

Use this skill when the user asks to:

- Create, refresh, check, install, or repair the global SkillGuard skill router.
- Scan installed or repository-local Codex skills and build a global route registry.
- Make global prompt behavior default through a managed user-level AGENTS prompt block.
- Resolve a task to the correct skill before that skill's native workflow begins.
- Onboard a newly added skill so it appears in the global registry and prompt projection.
- Check whether the global route registry or managed AGENTS prompt block is stale.

## Do Not Use When

Do not use this skill to execute the selected target skill's actual work. After route selection, use the selected skill and its contract.

Do not use this skill as a parallel route system beside a target skill that already owns native route/check behavior. Bind and hand off to the native route documents instead.

Do not use this skill to claim global AI correctness, package publication, release readiness, test success, external service behavior, or future model compliance.

## Required Workflow

1. Inspect the current SkillGuard router materials.

   Locate the SkillGuard CLI, the skill roots to scan, the existing registry artifact if present, and the target user-level AGENTS prompt file or test equivalent.

2. Scan skill roots.

   Run `skillguard.py scan-global-skills --skill-root <root>` for each intended root or use `refresh-global-router` with repeated `--skill-root` flags. Record missing roots as blockers.

3. Build or refresh the registry.

   Run `build-global-registry` or `refresh-global-router`. The registry must include each discovered skill's status, route documents, contract hash when present, route IDs, fixed integration marker, and claim boundary.

4. Check registry freshness.

   Run `check-global-registry` against the generated registry. Do not claim a registry is current if its hash differs from a fresh scan.

5. Render and install the managed prompt block.

   Run `render-global-prompt` or `refresh-global-router`, then install with `install-global-prompt` or the refresh command. Only the managed block between the SkillGuard markers may be inserted or replaced.

6. Check global prompt freshness.

   Run `check-global-prompt` against the registry and AGENTS prompt file. Block if the managed block is missing, duplicated, marker-corrupted, or stale for the current registry hash.

7. Resolve target skill and hand off.

   Run `resolve-global-skill` for the task. Then read the selected skill's `SKILL.md` and follow its current source/compiled/manifest authority. Anything other than the exact current authority is a blocker, not permission to use an older pair. Do not skip the target skill's gates.

8. Report closure.

   Report the registry path, registry hash, AGENTS prompt target, commands run, failures, blockers, skipped checks, residual risk, and claim boundary.

## Current Runtime Contract

Use the current runtime contract when the router itself is being changed, checked, or installed.

The router must follow this fixed workflow:

- the router must maintain a confirmed `.skillguard/contract-source.json`, deterministic `.skillguard/compiled-contract.json`, exact `.skillguard/check-manifest.json`, and one current typed authority decision with no former runtime-authority residual;
- the router declares its exact command-surface and FlowGuard-model checks; SkillGuard freezes and reconciles those receipts without assigning router-domain meaning or requiring a special check pattern;
- the registry and prompt projection must be generated by current CLI output, not prose-only edits;
- AGENTS prompt installation must preserve unrelated user content and only replace the managed SkillGuard block;
- closure requires `check-global-registry`, `check-global-prompt`, and at least one `resolve-global-skill` smoke route.

## Hard Gates

- A global registry claim must cite a current registry hash.
- A global prompt claim must cite a current managed AGENTS prompt block check.
- The user-level AGENTS prompt file must contain at most one SkillGuard global router managed block.
- Prompt installation must preserve unrelated AGENTS prompt content.
- Missing skill roots, missing registry files, stale registry hashes, marker corruption, or unresolved target routes are blockers.
- Newly added skills must be rescanned before claiming they are globally routable.
- The global router must hand off to the selected skill's own route documents and must not override that skill's contract or native route bindings.
- Every routable skill has one current authority only. A former skill shape is blocked; it is never migrated or interpreted during routing.
- Output must not expose private absolute paths, credentials, hidden coordination state, or task-private route material.

## Output Requirements

Router reports should include:

- `checked_target`: the registry path, AGENTS prompt path, skill root, or selected skill path.
- `status`: `pass`, `fail`, or `block`.
- `registry_hash`: the current global registry hash when applicable.
- `evidence`: commands run, files inspected, generated artifacts, hashes, and prompt marker checks.
- `failures` and `blockers`: stale hashes, missing roots, malformed registry JSON, prompt marker corruption, unresolved routes, or handoff gaps.
- `skipped_checks`: every skipped scan, install, prompt check, or target-skill handoff check.
- `residual_risk`: what remains uncertain after the completed router checks.
- `claim_boundary`: what the router did and did not prove.

## SkillGuard Maintenance

When this router changes, keep the SkillGuard CLI, schemas, prompt template, fixtures, tests, and documentation synchronized.

Ordinary use of an already-installed skill does not run SkillGuard maintenance. Creating, changing, directly rewriting a non-current target, installing, synchronizing, or releasing a skill does: load its frozen component-impact plan and refresh the registry/prompt only when the plan marks the router projection affected. There is no migration reader or compatibility route.

When any new skill is added or an existing skill's `SKILL.md`, current contract trio, route entrypoint, managed-prompt component, or native route binding changes, refresh the global registry and reinstall or recheck the managed AGENTS prompt block before claiming global route coverage. Diagnostic-only files, test reports, receipts, and logs do not make the route projection stale.
