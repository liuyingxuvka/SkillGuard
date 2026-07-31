# Repository Agent Policy

This repository contains SkillGuard, a public tool and skill package for maintaining Codex skills. Agents and contributors should keep changes scoped, evidence-based, and safe for a public open-source repository.

## Working Scope

- Keep edits limited to the files required by the current task.
- Preserve existing user or peer-agent work. Do not overwrite a file without first inspecting the current content.
- Do not create implementation directories, release artifacts, credentials, remotes, or repository history unless the current task explicitly owns that work.
- If a task is limited to documentation or metadata, do not use it to add scripts, schemas, tests, fixtures, package code, or generated outputs.

## Multi-Agent Coordination

- Assume another agent may be editing the same repository.
- Recheck target files immediately before writing.
- If an unexpected file appears, treat it as user or peer-agent work and either preserve it or report a concrete conflict.
- Avoid broad formatting, cleanup, dependency installation, or generated rewrites unless the task explicitly requires them.

## Validation Expectations

- Run the narrowest practical checks for the files you changed.
- For metadata, parse machine-readable files with a real parser when available.
- For documentation, verify required sections, commands, status meanings, limitations, and claim boundaries directly from current file content.
- Report skipped validation as skipped. Do not describe a check as passing unless it actually ran against current files.

## Privacy And Public-Safety Boundaries

- Do not commit credentials, secrets, tokens, API keys, private keys, private task payloads, internal coordination records, private transcripts, local absolute paths, user-specific filesystem details, or private workspace transcripts.
- Use public, portable paths and examples in documentation.
- Keep machine-specific setup notes out of tracked files unless they are intentionally documented as examples.

## Claim Boundaries

- Do not claim that SkillGuard is fully implemented, validated, released, published, or integrated with external services unless current repository evidence proves that exact claim.
- Do not claim that SkillGuard guarantees Codex activation, AI correctness, fully automated semantic judgment, or one-click migration.
- Keep parent or suite summaries tied to child evidence. A high-level status must not hide stale, missing, blocked, or unreviewed child work.

## Packaging Boundaries

- Keep version fields synchronized when editing release metadata.
- Do not add CLI entry points, package discovery rules, dependencies, or build configuration for files that do not yet exist.
- Prefer conservative metadata until implementation, validation, and release nodes create the corresponding artifacts.

<!-- BEGIN FLOWGUARD PROJECT RULES -->

<!-- flowguard-rule:project.scope -->

## FlowGuard Project Rules

This project uses FlowGuard for non-trivial maintenance, feature work, bug
fixes, refactors, tests, release work, project upgrades, and evidence-sensitive
process changes.

<!-- flowguard-rule:project.repository -->

FlowGuard repository:
https://github.com/liuyingxuvka/FlowGuard

<!-- flowguard-rule:skill_suite.agent_surface -->

FlowGuard agent skill suite:
- Primary agent surface: the current clean consumer projection under
  `$CODEX_HOME/skills/`; default entry is
  `$CODEX_HOME/skills/flowguard/SKILL.md`.
- A project reads this block plus selected sibling guidance; it does not copy the FlowGuard suite into its local tree.
- The Python package/CLI is executable check support, not the AI-agent skill installation surface.

<!-- flowguard-rule:project.record_locations -->

Project FlowGuard record:
- Manifest: `.flowguard/project.toml`
- Machine log: `.flowguard/adoption_log.jsonl`
- Human log: `docs/flowguard_adoption_log.md`

<!-- flowguard-rule:project.rendered_versions -->

Current adoption record:
- FlowGuard check-engine version: `0.66.0`
- FlowGuard schema version: `1.0`

<!-- flowguard-rule:project.preflight_version_gate -->

Before non-trivial work, verify the real engine/schema/version and run
`python -m flowguard project-audit --root .`. Compare it with `.flowguard/project.toml`.
If installed is newer, run `project-upgrade` with artifact/model/test upgrade scanning
and revalidate affected evidence; if installed is older, connect the current
engine before claiming confidence.

<!-- flowguard-rule:runtime.latest_schema_first -->

FlowGuard runtime guidance is latest-schema-first: old artifacts may be
detected and upgraded at project/tool boundaries, but normal route logic should
not keep long-lived old branches for obsolete fields, aliases, or wrappers.

<!-- flowguard-rule:model_system.authority -->

Only the content-addressed `observed_implementation` snapshot selected by
the sole project head is current. Targets/experiments stay isolated; discovery
or green candidate checks grant no authority. Missing/invalid authority or
required coverage blocks broad confidence.

<!-- flowguard-rule:model_system.revision_transaction -->

Replace model authority only through one accepted `ModelRevisionSet` bound
to the exact base, candidate, affected closure, changes, and current owner
evidence. Persist records before the pointer. Rollback restores/compensates real
effects and revalidates the old snapshot; irreversible effects use forward repair.

<!-- flowguard-rule:lifecycle.default_replacement -->

Default replacement means dispose the old path, old field, alias, wrapper, or
alternate success path. Delete, block, migrate, delegate, repair, replace, or
scope it out with a concrete reason; do not leave it as a second successful
route.

<!-- flowguard-rule:behavior.commitment_ledger -->

Broad behavior claims use BehaviorCommitmentLedger: independently inventory
admitted external promises, give each source one modeled/delegated/scoped
disposition, one plane/actor and one primary model owner, and send
`path_sensitive=true` rows to Primary Path Authority. Helpers are not
automatically commitments.

<!-- flowguard-rule:behavior.plane_partitioning -->

Classify each commitment as `product_runtime`, `agent_operation`, or
`development_process`. A lightweight existing-model/commitment lookup selects
a bounded same-plane owner closure; typed related-plane context never transfers
ownership. Model Miss creates a gap only when that plane has no matching promise.

<!-- flowguard-rule:behavior.commitment_ledger_modes -->

Declare ledger mode before coverage work. Only `bootstrap_ledger` and
`coverage_gap_backfill` use broad history discovery; add/change/remove/miss
work stays on the affected commitment, owner, cases, and evidence closure.

<!-- flowguard-rule:lifecycle.field_mesh -->

Field-bearing work uses FieldLifecycleMesh. High-level models keep
behavior-bearing fields; leaf inventory accounts every field's owner,
readers/writers, projection, lifecycle, evidence, and old-field disposition.

<!-- flowguard-rule:evidence.ui_and_payload -->

UI runnable claims and file/work-package claims need current UI click-through
or artifact-payload evidence gates before broad done/release confidence.

<!-- flowguard-rule:behavior.primary_path_authority -->

Path-sensitive commitments need one Primary Path Authority, visible primary
failure, no automatic alternate success, and current exhaustion/test/risk evidence.

<!-- flowguard-rule:behavior.exact_intent_reuse -->

One exact user purpose has one intent, active commitment, and primary path.
Equivalent UI/API/CLI/adapter/wrapper surfaces delegate; they do not become
independent success implementations.

<!-- flowguard-rule:ui.product_language -->

UI Flow Structure owns product-wide language and complete rendered-surface
coverage. Full UI claims inventory every control, display, transition, overlay,
recovery path, and blindspot with stable identity, evidence, and disposition.

<!-- flowguard-rule:ui.content_admission -->

Classify UI content once as `user_visible`, `user_on_demand`, or `internal`.
On-demand needs reveal/return; internal diagnostics and routing stay hidden.

<!-- flowguard-rule:process.development_process_flow -->

Plans, staged/multi-skill work, sync, release, publish, and final process
claims enter `flowguard-development-process-flow`. It owns order/freshness,
preserves peer writes, delegates semantics, uses affected revalidation, and
reserves one full gate for frozen source. Conditional strategy selection runs
only for its declared triggers; progress is never completion evidence.

<!-- flowguard-rule:process.work_context_read_only -->

External specs/plans enter only through explicit project-bounded read-only
WorkContexts. Providers keep ownership; FlowGuard preserves identities,
fingerprints, and lanes, rejects fallback/write/execution authority, and admits
behavior sources only through explicit mappings. Zero providers is valid.

<!-- flowguard-rule:process.post_change_scan -->

After non-trivial work, let DevelopmentProcessFlow consume post-change scan signals:
changed artifacts, skips, stale evidence, open obligations, and split/reduction
pressure. Route each gap to its existing specialist owner.

<!-- flowguard-rule:claim.no_fake_adoption -->

Do not create a fake local FlowGuard replacement. Do not claim full FlowGuard
completion from an AGENTS/manifest/log update alone; executable model checks,
tests, replay, and closure evidence still need to be current for the claim.
Before model build/change, freeze this instance's task-specific failures and
boundary, then bind candidate plus native good/bad-per-failure/oracle/current
evidence. Reusable types are not fixed-purpose; no mode/fallback exists; only
FlowGuard-declared checks support completion claims.

<!-- END FLOWGUARD PROJECT RULES -->

<!-- BEGIN MANAGED SKILLGUARD AUTHOR RULES -->
## SkillGuard author maintenance

This repository is an explicit skill-authoring workspace. Use SkillGuard only while maintaining, validating, graduating, or releasing the managed source skills below.

Canonical SkillGuard repository: https://github.com/liuyingxuvka/SkillGuard

Managed skills:
- `.agents/skills/skillguard` — native owner=`skillguard.executable_contract_runtime.v2`, maintenance unit=`unit:skillguard`, route evidence=`.agents/skills/skillguard/SKILL.md`; the target skill keeps domain-route, judgment, action, and native-check authority.

Required maintenance handoff:

1. Read the target skill's `SKILL.md` and its native route/check contracts before editing.
2. Use SkillGuard to inventory, run every target-declared check, reconcile exact receipts, and close non-trivial skill changes.
3. Preserve the target's sole current native route and exact declared checks; SkillGuard never supplies a target-domain route.
4. Never let SkillGuard replace target-owned domain judgment, simulation, search, modeling, actions, or checks.
5. Do not claim complete use from contract presence alone; require a current declared-check execution receipt.
6. Never copy this block, the author manifest, contracts, receipts, router state, or Portfolio state into a graduated consumer skill or an ordinary business project.
7. If SkillGuard is unavailable or this block/manifest is missing, stale, duplicated, or invalid, report only author maintenance as blocked; ordinary consumer use remains independent.

Validation execution ownership:

- policy_id: `skillguard.validation_execution_ownership.current`
- Creating, updating, directly rewriting, installing/synchronizing, or releasing an explicitly registered maintained skill source requires SkillGuard author-side supervision; no migration or compatibility route exists.
- Covered skill maintenance uses direct current replacement. Do not add a compatibility reader, fallback, migration or upgrade command, converter, alias, renewal path, dual manifest, or parallel authority. An ordinary software historical reader is allowed only when an explicit requirement names the old document/data/interface and FlowGuard records its bounded owner and claim boundary.
- Ordinary use of an installed consumer skill for its domain work does not start SkillGuard maintenance or validation and must not require SkillGuard files, imports, commands, receipts, or router state.
- SkillGuard supervises the author-side frozen owner plan, receipts, affected-only revalidation, clean consumer projection, and closure; the target skill retains its domain actions, judgment, and native-check authority.
- Before validating one maintenance unit, freeze its unit id, member ids, exact semantic checks, evidence subjects, covered obligations/domains, dependency order, private receipt root, and exactly one execution owner per check; missing, duplicate, foreign-unit, or cyclic ownership blocks execution.
- Reuse one immutable terminal-success producer receipt only inside the same maintenance unit when unit, member, explicitly declared owner, request, inputs, dependencies, toolchain, and environment are all exact. Each semantic check keeps its own subject, domain, obligations, and projection identity. A different unit must execute and own its own evidence even when command text and inputs look identical.
- Consumer distributions contain no SkillGuard receipt reference or execution-owner projection. They run their target-owned checks directly when their own workflow requires them.
- Compile the complete maintained inventory into exact content components before validation. A change invalidates only owners and projections that explicitly consume its changed component; an unmapped or ambiguous file blocks instead of falling back to run-all.
- Treat maintained test, code, contract, configuration, toolchain, and policy changes as freshness inputs only through those exact component edges. Reports, receipts, progress logs, checkboxes, and other runtime outputs are evidence outputs and must not refresh source authority or trigger their own validation.
- Installation consumes only the frozen `projection:installation`; source-only tests, fixtures, models, and notes do not make an installation stale. A read-only installation currentness check never launches smoke or another validation owner.
- Treat `--resume` as an execution command that may run missing owners; it is never a read-only receipt audit, and a receipt consumer must not invoke it.
- Start exactly one final full validation for the maintenance unit only after its source, toolchain, and impact-plan identities are frozen, under one explicit execution owner. Other maintenance units and consumers do not consume that parent receipt.
- After any launcher timeout, cancellation, or interruption, confirm the entire descendant process tree count is zero before accepting evidence or starting another owner; `cleanup-unconfirmed` results are invalid and non-reusable.
- Never use a Windows Scheduled Task, background resume, or unattended retry script to run full validation or resume a mutable worktree.

Author audit command: `python <installed-skillguard>/scripts/skillguard.py maintainer-audit --root .`

This managed block is a routing and maintenance contract. It is not runtime, test, release, or future-behavior proof.
<!-- END MANAGED SKILLGUARD AUTHOR RULES -->

