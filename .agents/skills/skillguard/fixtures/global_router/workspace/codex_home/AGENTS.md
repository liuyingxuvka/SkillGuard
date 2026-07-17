

<!-- BEGIN MANAGED SKILLGUARD GLOBAL ROUTER -->
## SkillGuard Global Router

- Use the SkillGuard global router registry only for skill-selection, skill-maintenance, prompt/process, or SkillGuard-family routing claims when it is present; do not make it a mandatory pre-execution gate for every skill invocation.
- If the registry or this managed block is missing or stale, run `skillguard.py refresh-global-router` before making a global skill-routing claim.
- Handoff order: select the target skill from the registry when selection help is needed and read its `SKILL.md`; a current route uses `.skillguard/contract-source.json`, `.skillguard/compiled-contract.json`, and the exact `.skillguard/check-manifest.json`. Every non-current authority is `blocked` and has no alternate success route.
- Do not let this global router replace a target skill's own hard gates, checks, evidence requirements, or closure boundary.

### Generic Declared-Check Supervision
- Freeze the target skill's exact declared-check inventory and require one current immutable terminal-success receipt for every declared check under its exact owner and request identity. Do not classify targets, infer domain semantics, or require any particular check pattern.
- SkillGuard validates current identities, inventory equality, execution ownership, dependencies, receipt freshness, provider readiness, and fixed `enforced` closure consumption. The target skill remains the sole authority for domain meaning, fixtures, oracles, native findings, and claim boundaries.
- A target may declare one check or several checks. SkillGuard supervises both through the same fixed workflow and never invents a purpose contract, counterexample pair, family category, domain route, or quality mode.

### Validation Execution Ownership
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
- router_skill_id: skillguard-global-router
- registry_hash: sha256:9c1ab488fed574e5a58325e2850fdd91950b1c37607d3ab463ff639d7bedb37b
- registry_path: .agents/skills/skillguard/fixtures/global_router/workspace/global_router/global_registry.json

## Validated Template Pack Selection

- Ask the selected target skill for its current native route receipt before consulting its catalog.
- Require target-authored applicability and forbidden-condition evidence for every frozen candidate.
- Reconcile zero, one, and many candidates without lexical scoring or guessed family semantics.
- Permit composition only when dependencies, mutual compatibility, declared order, and single field ownership are complete.
- Materialize a read-only preview and keep ambiguity, no-match, stale, and rejected-candidate reasons visible.
- Treat the selection receipt as planning evidence only; it does not prove instantiation or closure.

## Validated Template Pack Instance

- Bind the instance to one current selection receipt, exact parameters, and target builder identities.
- Require the generated artifact inventory to equal the selected manifests and scan every output for unresolved placeholders.
- Consume every target-declared native validator receipt; failed, skipped, stale, blocked, or not-run validation keeps the instance blocked.
- Keep the instance fingerprint separate from source, installed projection, release, and Git identities.
- Require a harvest disposition after a new or materially deepened reusable model.

## Validated Template Pack Installation

- Stage the compiler-owned installation projection and verify content before activation.
- Activate the maintained target transactionally and run installed currentness separately from native validation.
- Restore the previous active projection when a required post-activation check fails.
- Refresh the global router only when the target route projection changed; the router never selects a domain template.
- Keep installation, source, package/runtime, receipt, and Git identities distinct.

- template_lifecycle_hash: sha256:602df2d488f470fce94f187803c27a625180eae549355bce982e474fc58aa555
- template_domain_selection_owner: selected_target_skill
- global_router_selects_domain_template: false

### Current Route Index
- `flowguard-agent-workflow-rehearsal` -> .agents/skills/flowguard-agent-workflow-rehearsal/SKILL.md (default_route=route:agent_workflow_rehearsal, integration=native-integrated)
- `flowguard-architecture-reduction` -> .agents/skills/flowguard-architecture-reduction/SKILL.md (default_route=route:architecture_reduction, integration=native-integrated)
- `flowguard-behavior-commitment-ledger` -> .agents/skills/flowguard-behavior-commitment-ledger/SKILL.md (default_route=route:behavior_commitment_ledger, integration=native-integrated)
- `flowguard-code-structure-recommendation` -> .agents/skills/flowguard-code-structure-recommendation/SKILL.md (default_route=route:code_structure_recommendation, integration=native-integrated)
- `flowguard-contract-exhaustion-mesh` -> .agents/skills/flowguard-contract-exhaustion-mesh/SKILL.md (default_route=route:contract_exhaustion_mesh, integration=native-integrated)
- `flowguard-development-process-flow` -> .agents/skills/flowguard-development-process-flow/SKILL.md (default_route=route:development_process_flow, integration=native-integrated)
- `flowguard-existing-model-preflight` -> .agents/skills/flowguard-existing-model-preflight/SKILL.md (default_route=route:existing_model_preflight, integration=native-integrated)
- `flowguard-field-lifecycle-mesh` -> .agents/skills/flowguard-field-lifecycle-mesh/SKILL.md (default_route=route:field_lifecycle_mesh, integration=native-integrated)
- `flowguard-model-mesh` -> .agents/skills/flowguard-model-mesh/SKILL.md (default_route=route:model_mesh_maintenance, integration=native-integrated)
- `flowguard-model-miss-review` -> .agents/skills/flowguard-model-miss-review/SKILL.md (default_route=route:model_miss_review, integration=native-integrated)
- `flowguard-model-test-alignment` -> .agents/skills/flowguard-model-test-alignment/SKILL.md (default_route=route:model_test_alignment, integration=native-integrated)
- `flowguard-model-topology-hazard-review` -> .agents/skills/flowguard-model-topology-hazard-review/SKILL.md (default_route=route:model_topology_hazard_review, integration=native-integrated)
- `flowguard-plan-detailing-compiler` -> .agents/skills/flowguard-plan-detailing-compiler/SKILL.md (default_route=route:plan_detailing_compiler, integration=native-integrated)
- `flowguard-structure-mesh` -> .agents/skills/flowguard-structure-mesh/SKILL.md (default_route=route:structure_mesh_maintenance, integration=native-integrated)
- `flowguard-test-mesh` -> .agents/skills/flowguard-test-mesh/SKILL.md (default_route=route:test_mesh_maintenance, integration=native-integrated)
- `flowguard-ui-flow-structure` -> .agents/skills/flowguard-ui-flow-structure/SKILL.md (default_route=route:ui_flow_structure, integration=native-integrated)
- `model-first-function-flow` -> .agents/skills/model-first-function-flow/SKILL.md (default_route=route:model_first_function_flow, integration=native-integrated)
- `skillguard` -> .agents/skills/skillguard/SKILL.md (default_route=route:static-audit, integration=native-integrated)
- `skillguard-global-router` -> .agents/skills/skillguard-global-router/SKILL.md (default_route=route:scan-global-skills, integration=native-integrated)

Claim boundary: this block is a routing projection only. It does not prove runtime checker execution, fixture coverage, CLI checks, tests, suite automation, package publication, code-contract validation, release readiness, or future AI behavior without separate current evidence.
<!-- END MANAGED SKILLGUARD GLOBAL ROUTER -->
