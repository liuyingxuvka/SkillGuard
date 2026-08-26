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

For non-trivial work, select the smallest current FlowGuard public owner; clear satellites are direct peers and unclear ordinary behavior/state work uses `flowguard`.

<!-- flowguard-rule:project.repository -->

FlowGuard repository:
https://github.com/liuyingxuvka/FlowGuard

<!-- flowguard-rule:skill_suite.agent_surface -->

FlowGuard agent skill suite: Primary agent surface: the current clean consumer projection at `$CODEX_HOME/skills/flowguard/SKILL.md`; the project does not copy the FlowGuard suite into its local tree, and the Python package/CLI is not the AI-agent skill installation surface.

<!-- flowguard-rule:project.record_locations -->

Project record: `.flowguard/project.toml`; machine log: `.flowguard/adoption_log.jsonl`; human log: `docs/flowguard_adoption_log.md`.

<!-- flowguard-rule:project.rendered_versions -->

Current adoption record: FlowGuard check-engine version: `0.68.16`; FlowGuard schema version: `1.0`.

<!-- flowguard-rule:project.preflight_version_gate -->

Before non-trivial work run `python -m flowguard project-audit --root .`; if the installed engine is newer, run full `project-upgrade` scanning and affected revalidation, and if older connect the current engine.

<!-- flowguard-rule:runtime.latest_schema_first -->

Use latest-schema-first direct replacement; obsolete fields, aliases, wrappers, and alternate success paths have no normal-runtime fallback.

<!-- flowguard-rule:model_system.authority -->

Only the sole content-addressed `observed_implementation` head is current; targets, experiments, discovery, and green candidates do not own current behavior.

<!-- flowguard-rule:model_system.revision_transaction -->

Change model authority only through one accepted `ModelRevisionSet`; keep the revision-local delta distinct from its complete `CurrentEffectiveIntentView`, bind every current model owner exactly, persist evidence before the pointer, and restore/compensate effects before rollback.

<!-- flowguard-rule:lifecycle.default_replacement -->

Default replacement means dispose the old path: every replaced field, alias, wrapper, or alternate success needs an explicit delete/block/migrate/delegate/repair/replace/scope disposition.

<!-- flowguard-rule:behavior.commitment_ledger -->

Broad behavior claims require an independent BehaviorCommitmentLedger inventory, one plane and primary owner per admitted promise, and Primary Path Authority for path-sensitive rows.

<!-- flowguard-rule:behavior.plane_partitioning -->

Commitments stay in `product_runtime`, `agent_operation`, or `development_process`; select a bounded same-plane owner closure and keep related planes as typed context only.

<!-- flowguard-rule:behavior.commitment_ledger_modes -->

Declare ledger mode first; only bootstrap/backfill may discover broadly, while add/change/remove/miss stays on the affected commitment closure.

<!-- flowguard-rule:lifecycle.field_mesh -->

Field-bearing work uses FieldLifecycleMesh and accounts owner, readers/writers, projection, lifecycle evidence, and old-field disposition.

<!-- flowguard-rule:evidence.ui_and_payload -->

UI runnable claims and file/work-package claims need current real-surface or payload evidence before broad confidence.

<!-- flowguard-rule:behavior.primary_path_authority -->

Commitments with `path_sensitive=true` need one Primary Path Authority, visible primary failure, no alternate automatic success, and current exhaustion/test/risk evidence.

<!-- flowguard-rule:behavior.exact_intent_reuse -->

One exact purpose has one intent, commitment, and primary path; equivalent UI/API/CLI/adapter/wrapper surfaces delegate rather than own independent success.

<!-- flowguard-rule:ui.product_language -->

UI Flow Structure owns product language and complete rendered control/display/transition/overlay/recovery/blindspot coverage for full UI claims.

<!-- flowguard-rule:ui.content_admission -->

Classify UI content once as `user_visible`, `user_on_demand`, or `internal`; on-demand needs reveal/return and internal diagnostics stay hidden.

<!-- flowguard-rule:process.development_process_flow -->

Plans, staged/multi-skill work, sync, release, publish, and final process claims use `flowguard-development-process-flow`: start with lightweight existing-model/commitment lookup, preserve peers, revalidate affected owners, and reserve one full gate for frozen source.

<!-- flowguard-rule:process.work_context_read_only -->

External specs/plans are optional project-bounded read-only WorkContexts; providers retain identity, lane, execution, validation, and lifecycle authority.

<!-- flowguard-rule:process.post_change_scan -->

DevelopmentProcessFlow consumes post-change scan signals—changed, skipped, stale, open, split, or reduction—and routes each to its existing specialist.

<!-- flowguard-rule:claim.no_fake_adoption -->

Do not create a fake local FlowGuard replacement. AGENTS/manifest/log changes are not proof: freeze task-specific failures and boundary, bind native good/bad-per-failure/oracle/current evidence, and let only declared checks support completion.

<!-- END FLOWGUARD PROJECT RULES -->

<!-- BEGIN MANAGED SKILLGUARD AUTHOR RULES -->
## SkillGuard author maintenance

This repository is an explicit skill-authoring workspace. Use SkillGuard only while maintaining, validating, graduating, or releasing the managed source skills below.

Canonical SkillGuard repository: https://github.com/liuyingxuvka/SkillGuard

Managed skills:
- `.agents/skills/skillguard` — native owner=`skillguard`, maintenance unit=`unit:skillguard`, route evidence=`.agents/skills/skillguard/SKILL.md`; the target skill keeps domain-route, judgment, action, and native-check authority.

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

<!-- BEGIN MANAGED SKILLGUARD GLOBAL ROUTER -->
## SkillGuard Author Router

- Use this private block only for authoring, maintaining, checking, installing, or releasing an explicitly registered SkillGuard-maintained source.
- Ordinary use of a graduated consumer skill stays independent: no `.skillguard`, contract, receipt, command, router, Portfolio, or author path is required.
- External OpenSpec is outside this registry. Never infer maintenance membership by scanning installed consumer skills; refresh only from explicit author-side `--skill-root` values.
- The selected target owns domain behavior, completion/depth criteria, checks, and results. SkillGuard supervises exact author identities/evidence and clean consumer projection only.
- Different maintenance units never share, import, project, or reuse check receipts. Similar command text does not create shared evidence authority.

### Direct-Current Validation Boundary
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

### Private Registry Pointer

- router_skill_id: `skillguard-global-router`
- registry_hash: sha256:e65935a79ce0c765a57941c88d202dd59640e4a4fb6429f03b82f1a41ad63b6e
- registry_path: .codex/.skillguard/global-router/global_registry.json
- current_registered_source_count: 2; exact source paths and route identities are read from the registry JSON only when author maintenance is selected.
- Read the selected registered source's own `SKILL.md` and conditional references before executing its maintenance route. The global block neither selects a domain template nor carries the full route/template manuals.

Claim boundary: this block routes registered author maintenance only. It proves no target check, consumer installation, Git/tag/release, factual result, or future AI behavior without separate current evidence.
<!-- END MANAGED SKILLGUARD GLOBAL ROUTER -->
