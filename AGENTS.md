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
- Primary agent surface: `.agents/skills/`
- Default entry skill: `.agents/skills/model-first-function-flow/SKILL.md`
- Complete AI-agent setup means the agent can read `AGENTS.md` and all
  FlowGuard sibling `SKILL.md` files under `.agents/skills/`.
- The Python `flowguard` module/CLI is executable check support, not the
  AI-agent skill installation surface.

<!-- flowguard-rule:project.record_locations -->

Project FlowGuard record:
- Manifest: `.flowguard/project.toml`
- Machine log: `.flowguard/adoption_log.jsonl`
- Human log: `docs/flowguard_adoption_log.md`

<!-- flowguard-rule:project.rendered_versions -->

Current adoption record:
- FlowGuard check-engine version: `0.56.0`
- FlowGuard schema version: `1.0`

<!-- flowguard-rule:project.preflight_version_gate -->

Before non-trivial work:
1. Verify the real FlowGuard check engine:
   `python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"`
2. Check the installed check-engine version:
   `python -c "import importlib.metadata as m; print(m.version('flowguard'))"`
3. Audit the project record:
   `python -m flowguard project-audit --root .`
4. Compare the installed version with `.flowguard/project.toml`.
5. If the installed version is newer, run:
   `python -m flowguard project-upgrade --root .`
   This updates the project record and scans existing FlowGuard artifacts,
   model evidence, tests, docs, and guidance for deterministic upgrades into
   the current FlowGuard shape. Use `--records-only` only when intentionally
   scoping out artifact/model/test upgrade scanning.
   Then rerun affected models/tests before broad confidence and record the result.
6. If the installed version is older than the project record, stop and connect
   a current FlowGuard check engine before claiming FlowGuard confidence.

<!-- flowguard-rule:runtime.latest_schema_first -->

FlowGuard runtime guidance is latest-schema-first: old artifacts may be
detected and upgraded at project/tool boundaries, but normal route logic should
not keep long-lived old branches for obsolete fields, aliases, or wrappers.

<!-- flowguard-rule:lifecycle.default_replacement -->

Default replacement means dispose the old path, old field, alias, wrapper, or
alternate success path. Delete, block, migrate, delegate, repair, replace, or
scope it out with a concrete reason; do not leave it as a second successful
route.

<!-- flowguard-rule:behavior.commitment_ledger -->

Broad behavior work should use or update BehaviorCommitmentLedger before
claiming full coverage: register external behavior promises, map source
surfaces to commitments, assign exactly one primary owner model per
commitment, classify plane and actor kind, record typed relations/evidence,
and hand `path_sensitive=true`
commitments to Primary Path Authority. Do not treat every helper function,
file, field, or model as a behavior commitment.

<!-- flowguard-rule:behavior.plane_partitioning -->

Keep product runtime behavior, AI-agent operations, and development lifecycle
behavior in one BehaviorCommitmentLedger structure but classify every
production commitment as exactly one of `product_runtime`, `agent_operation`,
or `development_process`. `commitment_kind` describes form, not plane.
Before non-trivial work, use the lightweight existing-model/commitment lookup
to select one same-plane primary context; keep other planes separated or
connected only by typed, reasoned relations. A related product commitment is
target context for an AI/process step, not an instruction that the step owns.
Model Miss backfeed searches the affected plane first and creates a gap row
only when no matching promise exists. This is recall guidance, not a universal
requirement to execute a model for every trivial action.

<!-- flowguard-rule:behavior.commitment_ledger_modes -->

Before changing or claiming behavior coverage, classify the behavior-ledger
mode: `bootstrap_ledger`, `add_behavior`, `change_behavior`,
`remove_or_replace_behavior`, `coverage_gap_backfill`, or `model_miss_check`.
Only bootstrap and gap backfill require broad historical source discovery.
Ordinary add/change/remove work updates affected commitments, owner models,
DCAR cases, and TestMesh evidence. Model-miss checks first map the failure to
an existing same-plane commitment and owner model; keep typed related-plane
context separate, and create/backfill a commitment only when the observed
external behavior was not registered in that plane.

<!-- flowguard-rule:lifecycle.field_mesh -->

Field-bearing work should use or update FieldLifecycleMesh: high-level behavior
models include behavior-bearing fields, while child/leaf field rows account all
discovered fields and record owner, readers, writers, projection, lifecycle,
and old-field disposition.

<!-- flowguard-rule:evidence.ui_and_payload -->

UI runnable claims and file/work-package claims need current UI click-through
or artifact-payload evidence gates before broad done/release confidence.

<!-- flowguard-rule:behavior.primary_path_authority -->

Path-sensitive behavior commitments need Primary Path Authority evidence before
broad confidence: one primary runtime authority per business intent, visible
primary failure, no automatic alternate success, ContractExhaustionMesh
coverage, TestMesh shards, and Risk Evidence Ledger gates.

<!-- flowguard-rule:behavior.exact_intent_reuse -->

Treat one exact external user purpose as one stable `business_intent_id`, one
active Behavior Commitment, and one singular `primary_path_id`. UI, API, CLI,
aliases, adapters, wrappers, helpers, and compatibility surfaces for that same
purpose delegate to the selected commitment and path; they do not become
independent successful implementations.

<!-- flowguard-rule:ui.product_language -->

Use the existing UI Flow Structure route to review one product-wide design
language across declared surfaces: typography hierarchy, components,
navigation, interaction, feedback, recovery, and transition semantics. Equal
semantic roles reuse the same rule or token; any exception is bounded,
presentation-only, and cannot change the business intent, commitment, path,
visibility class, or user-visible result.

<!-- flowguard-rule:ui.content_admission -->

Classify UI content exactly once as `user_visible`, `user_on_demand`, or
`internal`. Ordinary UI renders only admitted user content; on-demand content
needs an explicit reveal and return path, while internal identities, audit
fields, evidence metadata, diagnostics, and routing state stay internal by
default.

<!-- flowguard-rule:process.development_process_flow -->

Non-trivial rough-plan discussion, multi-skill/tool workflow setup, staged
execution, install/sync, release/archive/publish, post-change owner scans, and
final process claims enter `flowguard-development-process-flow` first as the
development-process simulator. Record `plan_detailing`, internal
`strategy_selection`, `agent_workflow`, and `execution_freshness` modes in that
order; delegate to PlanDetailing or
AgentWorkflowRehearsal only when explicit or simulator-selected.
DevelopmentProcessFlow owns lifecycle order/freshness; AgentWorkflowRehearsal
owns AI-operation planning. Both may reference product commitments and their
evidence without copying product behavior into their own steps. Internal
`strategy_selection` stays inactive unless `explicit_request`,
`multiple_equivalent_routes`, `material_rework_risk`, or
`diagnostic_boundary_choice` applies. When active, first prove
outcome/obligation-evidence/safety/protected-side-effect/dependency-authority/
execution-owner equivalence, then choose `targeted`, `declared_complete`, or
`budgeted` diagnosis plus `sequential` or isolation-proven `safe_parallel`
execution. Hard blockers stop invalid descendants and material evidence stales
the decision. TestMesh owns diagnostic accounting; relation-backed repair
groups use ordinary primary-owner evidence and affected revalidation.
Estimated comparison may support a preference, never a global optimum.

<!-- flowguard-rule:process.spec_work_package_reconciliation -->

When OpenSpec, Spec Kit, or another supported specification provider is in
scope, keep provider tasks native and reconcile them bidirectionally with
FlowGuard obligations/checks through one development-process Spec Work
Package. Begin and close one immutable input session, reuse only exact terminal
receipts within an explicit boundary, and block archive when mappings,
post-snapshot evidence, provider verification, or receipt freshness is
missing. Internal work-package fields never become product UI content.

<!-- flowguard-rule:process.post_change_scan -->

After non-trivial FlowGuard-managed work, let DevelopmentProcessFlow consume
post-change scan signals for changed artifacts, skipped routes, stale evidence,
open obligations, or split/reduction pressure. The scan output routes each gap
to the owning specialist, such as Model-Test Alignment, Architecture
Reduction, StructureMesh, ModelMesh, TestMesh, or AgentWorkflowRehearsal.

<!-- flowguard-rule:claim.no_fake_adoption -->

Do not create a fake local FlowGuard replacement. Do not claim full FlowGuard
completion from an AGENTS/manifest/log update alone; executable model checks,
tests, replay, and closure evidence still need to be current for the claim.

<!-- END FLOWGUARD PROJECT RULES -->

<!-- BEGIN MANAGED SKILLGUARD PROJECT RULES -->
## SkillGuard project maintenance

This repository contains skills maintained with SkillGuard. For non-trivial skill maintenance, validation, installation, synchronization, or release work, use SkillGuard by default.

Canonical SkillGuard repository: https://github.com/liuyingxuvka/SkillGuard

Managed skills:
- `.agents/skills/skillguard` — native owner=`skillguard`, route evidence=`.agents/skills/skillguard/SKILL.md`; the target skill keeps domain-route, judgment, action, and native-check authority.
- `.agents/skills/skillguard-global-router` — native owner=`skillguard-global-router`, route evidence=`.agents/skills/skillguard-global-router/SKILL.md`; the target skill keeps domain-route, judgment, action, and native-check authority.

Required maintenance handoff:

1. Read the target skill's `SKILL.md` and its native route/check contracts before editing.
2. Use SkillGuard to inventory, run every target-declared check, reconcile exact receipts, and close non-trivial skill changes.
3. Preserve the target's sole current native route and exact declared checks; SkillGuard never supplies a target-domain route.
4. Never let SkillGuard replace target-owned domain judgment, simulation, search, modeling, actions, or checks.
5. Do not claim complete use from contract presence alone; require a current declared-check execution receipt.
6. If SkillGuard is unavailable or this block/manifest is missing, stale, duplicated, or invalid, report the maintenance result as blocked instead of silently bypassing it.

Validation execution ownership:

- policy_id: `skillguard.validation_execution_ownership.current`
- Creating, updating, directly rewriting a non-current target, installing/synchronizing, or releasing a maintained skill requires SkillGuard maintenance supervision; no migration or compatibility route exists.
- Covered skill maintenance uses direct current replacement. Do not add a compatibility reader, fallback, migration or upgrade command, converter, alias, renewal path, dual manifest, or parallel authority. An ordinary software historical reader is allowed only when an explicit requirement names the old document/data/interface and FlowGuard records its bounded owner and claim boundary.
- Ordinary use of an already-installed skill for its domain work does not start SkillGuard maintenance or validation.
- SkillGuard supervises the frozen owner plan, receipts, affected-only revalidation, installation projection, and closure; the target skill retains its domain actions, judgment, and native-check authority.
- Before multi-skill validation starts, freeze one task-level validation plan in the existing verification contract or TestMesh: list every exact check, covered obligation and evidence domain, dependency/order, persistent receipt root, and exactly one primary execution owner; missing, duplicate, or cyclic ownership blocks execution.
- Before executing a listed check, resolve its exact owner receipt from the frozen execution identity and inputs. Reuse only a current immutable terminal-success receipt; consumer skills verify and project that receipt and must not carry or rerun the owner's command.
- Compile the complete maintained inventory into exact content components before validation. A change invalidates only owners and projections that explicitly consume its changed component; an unmapped or ambiguous file blocks instead of falling back to run-all.
- Treat maintained test, code, contract, configuration, toolchain, and policy changes as freshness inputs only through those exact component edges. Reports, receipts, progress logs, checkboxes, and other runtime outputs are evidence outputs and must not refresh source authority or trigger their own validation.
- Installation consumes only the frozen `projection:installation`; source-only tests, fixtures, models, and notes do not make an installation stale. A read-only installation currentness check never launches smoke or another validation owner.
- Treat `--resume` as an execution command that may run missing owners; it is never a read-only receipt audit, and a receipt consumer must not invoke it.
- Start exactly one final full validation only after source, toolchain, and impact-plan identities are frozen, under one explicit execution owner; later consumers project its immutable parent receipt and never launch another equivalent full run.
- After any launcher timeout, cancellation, or interruption, confirm the entire descendant process tree count is zero before accepting evidence or starting another owner; `cleanup-unconfirmed` results are invalid and non-reusable.
- Never use a Windows Scheduled Task, background resume, or unattended retry script to run full validation or resume a mutable worktree.

Portable audit command: `python <installed-skillguard>/scripts/skillguard.py project-audit --root .`

This managed block is a routing and maintenance contract. It is not runtime, test, release, or future-behavior proof.
<!-- END MANAGED SKILLGUARD PROJECT RULES -->
