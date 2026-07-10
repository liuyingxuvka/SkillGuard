## Context

SkillGuard has a global-router owner and a runtime-contract owner. The new executable contract is a child boundary of the runtime-contract owner. It supervises target-native work but does not become a second target-skill executor and does not replace FlowPilot.

FlowGuard calibration established two distinct facts:

- typed topology and liveness are already executable and current;
- real-suite contract generation and immutable evidence closure are not yet fully deployed.

The design therefore reuses the former directly, implements the latter inside SkillGuard's narrower boundary, and avoids copying FlowGuard's fixed five-phase and large generated-file surface.

## Goals / Non-Goals

**Goals:**

- Compile behavior, route, terminal, loop, and invariant truth from a real FlowGuard model.
- Bind non-model details such as tools, API calls, output files, native checks, and rubrics without duplicating the model.
- Support one or many functions per skill and safe composed paths.
- Make every task instance claimable, inspectable, resumable, and closable from current receipts.
- Distinguish hard facts, witnessed external actions, and judged quality.
- Reject self-awarded pass, stale evidence, unrelated checks, illegal skip, no-progress loops, and missing artifacts.
- Keep published contracts portable and task-run evidence local to the target project.

**Non-Goals:**

- Execute target-domain work instead of the target skill.
- Turn subjective quality into fake mechanical proof.
- Infer an authoritative workflow from headings or keywords alone.
- Commit user task runs or private canonical paths into public skill packages.
- Preserve two successful runtime authorities indefinitely.

## Architecture

### 1. Two authoritative inputs

`.flowguard/skill_contract_model.py` owns function blocks, states, events, transitions, route ownership, terminals, invariants, refinement, progress measures, and loop bounds. Each block follows `Input x State -> Set(Output x State)`.

`.skillguard/contract-source.json` owns only target bindings that the model cannot safely infer: commands, tools, API actions, artifact schemas and locations, native check identifiers, timeouts, environment requirements, quality rubrics, and portable claim boundaries.

The compiler consumes a canonical FlowGuard export through a versioned adapter. It does not parse Python source heuristically and does not recreate FlowGuard dataclasses.

### 2. Minimal published output

The deterministic compiler emits:

- `.skillguard/compiled-contract.json` for functions, routes, steps, prerequisites, actions, artifacts, transitions, terminals, and closure policy;
- `.skillguard/check-manifest.json` for exact obligation-to-check bindings, applicability, timeouts, expected evidence, and hash policy.

No current run, AI judgment, progress ledger, closure receipt, private path, or target input is published with the skill.

### 3. Local claimed run

A task run lives at `<target>/.skillguard/runs/<run-id>/` and contains `run.json`, append-only `events.jsonl`, `artifacts.json`, immutable step receipts, and an eventual closure receipt. Claiming freezes contract, request, target, and scope fingerprints and obtains a target lock. A run can be reconstructed from its contract snapshot and event log without relying on chat history.

### 4. Step authority

The visible AI action “complete” maps to `evidence_submitted`, not `passed`. Only a verifier can derive `passed`. Required steps cannot be skipped. Conditional or optional steps may enter `skip_requested`; the runtime approves `skipped` only when the declared applicability condition and reason are evidenced.

Step states are `pending`, `ready`, `in_progress`, `evidence_submitted`, `passed`, `failed`, `blocked`, `skip_requested`, `skipped`, `not_applicable`, and `stale`.

### 5. Evidence and freshness

- `hard`: repeatable command, schema, hash, geometry, file, image, test, or exit-code proof.
- `witnessed`: a tool/API/desktop/browser action with target and input/output fingerprints.
- `judged`: versioned rubric evaluation with evaluator identity, input hash, conclusion, and limitations.

Receipts are immutable. Freshness is derived from current input, implementation, contract, artifact, environment-policy, and consumed-child fingerprints. A caller cannot set authoritative `current` or `pass` fields. A newer required child receipt invalidates a parent until the parent consumes it.

### 6. Routes and loops

Every handoff is typed and names a target, condition, and claim scope. Every business intent has one canonical success owner. A multi-function request may compose only declared compatible paths. Every SCC declares a progress measure, allowed delta, successful and blocked terminals, and a finite re-entry bound. Re-entry without progress is blocked.

### 7. Closure profiles

`routine`, `functional`, `release`, and `highest_quality` are monotonic. A stricter profile adds requirements and never hides a failure. Closure consumes exact current receipts and reports a safe claim and unsafe claim boundary. `partial`, `stale`, `skipped`, `not_run`, `progress_only`, and `blocked` cannot satisfy full closure.

### 8. Bootstrap and first external test

Self-hosting uses two stages: the frozen old verifier checks the new compiler/runtime build boundary, then the new verifier runs its own contract and fixtures with recorded version and hashes. The first external target is Autonomous Concept UI Redesign because it exercises explicit routing, conditional FlowGuard work, images, code, real UI launch, screenshots, geometry, bounded iteration, judged review, app-icon evidence, and parent closure.

### 9. Portfolio calibration is a feedback loop

After the first pilot, maintained skills graduate one at a time in a recorded simple-to-complex order. Each target defines representative positive, invalid-input, recovery/resume, and out-of-scope user jobs; captures a pre-change baseline; receives model, binding, implementation, and native-check changes; and is then exercised through a real user-visible outcome and artifact review.

Failures are classified as target implementation, target binding, SkillGuard model miss, SkillGuard runtime/validator gap, or environment/external blocker. A previous SkillGuard green followed by real failure invokes Model Miss Review: preserve the old claim and observed failure, classify the missed boundary, add an observed-regression and ContractExhaustion same-class cases, repair the owning model/code/test boundary, and mark the old proof stale or overclaimed.

Every SkillGuard change declares affected feature tags such as schema, compiler, route, run-state, receipt, artifact, native-check, closure, or provenance. All graduated skills receive a cheap contract/parity/freshness scan; skills using an affected feature must rerun representative real jobs and related negative/recovery evidence. Before the next target graduates, every earlier target must have either current full evidence under the active Guard compatibility fingerprint or a current TestResultReuseTicket proving the Guard change does not intersect its covered surface. Core closure, receipt, routing, or schema changes invalidate reuse and require full reruns.

The parent portfolio gate consumes current child receipts or reuse tickets. It never hides `revalidation_required`, stale, missing, failed, or blocked children inside a green aggregate.

## Module Boundaries

- `flowguard_adapter.py`: versioned FlowGuard export only.
- `contract_schema.py`: schemas and stable diagnostics.
- `contract_compiler.py`: deterministic compilation and parity.
- `route_runtime.py`: typed routing, ownership, composition, liveness.
- `run_store.py`: claim, lock, append-only storage, replay.
- `step_runtime.py`: ready steps and legal transitions.
- `check_runner.py`: controlled native/hard checks and receipts.
- `artifact_validators.py`: target artifact validation.
- `receipts.py`: immutable evidence, hashes, freshness, consumption.
- `closure.py`: profiles, parent closure, safe claims.
- `provenance.py`: later source/install/publication authority.

The CLI stays a thin facade. No module may implement an alternate successful version of another module's owned behavior.

## Risks / Trade-offs

- **Contract overhead harms normal skill use** → compile target-specific paths; return only ready steps; pressure-test friction and remove unconsumed fields.
- **Subjective work cannot be machine-proven** → preserve judged evidence as a separate class and disclose evaluator/self-review limits.
- **FlowGuard API changes** → use a versioned adapter and fail closed on unsupported schema; never vendor a mini-FlowGuard.
- **Generated files drift across many skills** → emit only two published files and provide deterministic check mode.
- **Self-verification becomes circular** → retain two-stage bootstrap evidence and negative fixtures.
- **Runtime duplicates native workflow** → enforce canonical owner and require target-native action/check bindings.
- **Old commands become a fallback path** → govern every old field and command through FieldLifecycle and Primary Path Authority before release.
- **The Guard evolves while targets are being migrated** → version a Guard compatibility fingerprint, project affected feature tags, stale affected prior graduates, and require TestMesh-backed revalidation before the next graduation.
- **Full portfolio reruns become too expensive** → run universal compile/freshness scans, targeted real reruns for affected skills, and permit result reuse only through current proof-bound tickets; require all-real full reruns for broad semantic or release changes.

## Migration Plan

1. Build and validate FlowGuard parent/child models, BCL, PPA, CEM, MTA, and tests before production implementation.
2. Implement schemas/compiler, then claimed run/replay, then receipts/checks/artifacts, then closure.
3. Self-host on SkillGuard and remove or migrate duplicate old runtime authority.
4. Run the Autonomous UI positive path and negative matrix; simplify the architecture based on measured friction.
5. Add provenance, privacy, CI, staged install, global-router refresh, and post-install verification.
6. Publish from the local canonical source branch only after release closure passes.
7. For maintained skills without a user-owned repository, identify the real upstream and license, choose fork, attributed derivative, local overlay, upstream contribution, or no-adoption, and only then create or synchronize a GitHub repository.
8. Roll targets out one at a time; after every target-driven SkillGuard repair, rerun self-host, the current target, all affected prior graduates, and the parent portfolio graduation gate before continuing.

Rollback preserves the frozen prior release and installed backup. V2 run directories are additive and ignored by published skill packages. No rollback may silently treat a V2 failure as a V1 success.

## Third-Party Skill Adoption

An adopted skill records both `upstream_identity` and `maintainer_repository_identity`; they are never collapsed into one owner claim. A GitHub-hosted upstream should normally be upgraded and verified on a local branch first, then forked into the user's account. The validated local branch is pushed to the fork, merged or selected as its maintained default branch, assigned a new non-moving maintainer version/tag, and published with upstream-base and verification notes. A separately created derivative repository is allowed only when no useful fork exists and redistribution is licensed; it must preserve LICENSE, NOTICE, authorship, source revision, and a clear modifications statement. Missing or ambiguous license blocks public copying and routes to a local overlay or upstream clarification. SkillGuard functional pass proves workflow closure, not intellectual-property ownership or publication permission.
