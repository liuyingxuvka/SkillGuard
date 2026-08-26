## Context

SkillGuard has a global-router owner and a runtime-contract owner. The new executable contract is a child boundary of the runtime-contract owner. It supervises target-native work but does not become a second target-skill executor and does not replace FlowPilot.

FlowGuard calibration established two distinct facts:

- typed topology and liveness are already executable and current;
- real-suite contract generation and immutable evidence closure are not yet fully deployed.

The design therefore reuses the former directly, implements the latter inside SkillGuard's narrower boundary, and avoids copying FlowGuard's fixed five-phase and large generated-file surface.

## Authority and direct-current boundary

`build-executable-skill-contract-runtime` is the sole current authority for the
executable contract, functional/release/highest-quality closure, SkillGuard
self-host acceptance, and CI/release acceptance. The archived
`../archive/2026-08-20-add-skill-functional-closure-audit` change is retained
only as historical provenance and cannot provide current commands, schemas,
receipts, tasks, or success authority. `add-bounded-evidence-lifecycle` owns
only the evidence-store and lifecycle boundary; it is not a second authority
for executable-contract or closure semantics. A lifecycle change that alters
inputs consumed here must be integrated by a direct-current rebuild and fresh
validation under this change.

Former contract, closure, receipt, and installation identities are
rejection-only direct-current rewrite inputs. There is no compatibility reader,
fallback path, migration command, converter, alias, dual manifest, or alternate
success authority. A mismatch is a visible blocker until the current source is
manually rewritten and validated again.

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

Every handoff is typed and names a target, condition, and claim scope. Every business intent has one canonical success owner. A multi-function request may compose only declared composable paths. Every SCC declares a progress measure, allowed delta, successful and blocked terminals, and a finite re-entry bound. Re-entry without progress is blocked.

### 7. Closure profiles

`routine`, `functional`, `release`, and `highest_quality` are monotonic. A stricter profile adds requirements and never hides a failure. Closure consumes exact current receipts and reports a safe claim and unsafe claim boundary. `partial`, `stale`, `skipped`, `not_run`, `progress_only`, and `blocked` cannot satisfy full closure.

The functional profile requires the current source, FlowGuard model export,
compiled contract, check manifest, target-owned surface inventory, and one
current full TestMesh aggregation for the self-host maintenance unit. Every
required lifecycle stage must resolve to a current immutable terminal-success
receipt with exact unit/member/check/owner/request/input/dependency/toolchain/
environment/projection identity. Functional positive-path evidence is
`simulated_e2e` or stronger; target-declared failure, recovery, non-goal, and
terminal evidence must also be current.

The release profile additionally requires `real_e2e` or stronger evidence for
each required lifecycle stage, deterministic quality evidence, a canonical
`.skillguard/self-host/current` terminal receipt bound to the current source,
contract, manifest, and owner-plan identities, clean-install smoke,
source/installed projection parity, post-install full self-host verification,
and current terminal receipts for the declared Windows and Linux CI matrix. A
workflow declaration, local install/router receipt, or aggregation-only record
does not prove CI or release closure. The highest-quality profile adds current
human or domain-expert evidence for every declared quality requirement.

### 8. Direct-current self-host and bounded pressure test

Self-hosting uses one current verifier after the current source, compiler,
runtime, contract, manifest, and receipt authority are rebuilt and frozen
together. Former verifier or contract identities are rejection-only inputs; they
never close a current run. A transactional rollback may restore an incomplete
write, but it cannot accept the former artifact as a current success. The
current pressure test is limited to SkillGuard itself and its repository-
controlled fixtures, so that the self-host contract, runtime, and evidence
authority can be closed without mutating or depending on another project. A
future external target may be selected only by a separate, explicitly
authorized change after this self-host closure passes; external pilot evidence
is not an input to this change. A missing canonical self-host receipt or a
non-terminal/foreign receipt leaves the requested profile blocked; no weaker
profile, old receipt, or alternate authority is substituted.

### 9. Portfolio calibration is a feedback loop

After the first pilot, maintained skills graduate one at a time in a recorded simple-to-complex order. Each target defines representative positive, invalid-input, recovery/resume, and out-of-scope user jobs; captures a pre-change baseline; receives model, binding, implementation, and native-check changes; and is then exercised through a real user-visible outcome and artifact review.

Failures are classified as target implementation, target binding, SkillGuard model miss, SkillGuard runtime/validator gap, or environment/external blocker. A previous SkillGuard green followed by real failure invokes Model Miss Review: preserve the old claim and observed failure, classify the missed boundary, add an observed-regression and ContractExhaustion same-class cases, repair the owning model/code/test boundary, and mark the old proof stale or overclaimed.

Every SkillGuard change declares affected feature tags such as schema, compiler,
route, run-state, receipt, artifact, native-check, closure, or provenance. All
graduated skills receive a cheap contract/parity/freshness scan; skills using an
affected feature must rerun representative real jobs and related
negative/recovery evidence. Before the next target graduates, every earlier
target must have either current full evidence under the exact current Guard
identity fingerprint or a current TestResultReuseTicket proving the Guard
change does not intersect its covered surface. Core closure, receipt, routing,
or schema changes invalidate reuse and require full reruns.

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
- **Self-verification becomes circular** → retain direct-current bootstrap evidence and negative fixtures.
- **Runtime duplicates native workflow** → enforce canonical owner and require target-native action/check bindings.
- **Old commands remain unresolved** → give every old field and command a direct
  FieldLifecycle and Primary Path Authority disposition before release; rewrite,
  retire, or block it, with no alternate success path.
- **The Guard identity changes while targets are being updated** → record the
  exact current Guard identity fingerprint, project affected feature tags, mark
  affected prior graduates stale, and require TestMesh-backed revalidation
  before the next graduation.
- **Full portfolio reruns become too expensive** → run universal compile/freshness scans, targeted real reruns for affected skills, and permit result reuse only through current proof-bound tickets; require all-real full reruns for broad semantic or release changes.

## Direct-current rollout plan

1. Build and validate FlowGuard parent/child models, BCL, PPA, CEM, MTA, and tests before production implementation.
2. Implement schemas/compiler, then claimed run/replay, then receipts/checks/artifacts, then closure.
3. Self-host on SkillGuard and directly rebuild the current authority; remove,
   retire, or block every duplicate former runtime authority. No former-format
   reader or alternate success path is introduced. Then freeze the current
   source, FlowGuard model, compiled contract, check manifest, target surface
   inventory, toolchain, and owner plan.
4. Run one functional self-host owner under the frozen identities and consume
   its current full TestMesh aggregation and terminal receipts.
5. Run the release self-host owner once under the same frozen identities, then
   run clean-install smoke, source/installed parity, post-install full
   verification, and the declared Windows/Linux CI matrix. Missing terminal
   evidence keeps release blocked.
6. Run the Autonomous UI positive path and negative matrix; simplify the architecture based on measured friction.
7. Add provenance, privacy, staged install, global-router refresh, and post-install verification.
8. Publish from the local canonical source branch only after release closure passes.
9. For maintained skills without a user-owned repository, identify the real upstream and license, choose fork, attributed derivative, local overlay, upstream contribution, or no-adoption, and only then create or synchronize a GitHub repository.
10. Roll targets out one at a time; after every target-driven SkillGuard repair, rerun self-host, the current target, all affected prior graduates, and the parent portfolio graduation gate before continuing.

Rollback preserves the frozen prior release and installed backup. V2 run
directories are additive and ignored by published skill packages. A rollback
may restore an incomplete transaction, but it may not silently treat a current
failure as a former-format success.

## Third-Party Skill Adoption

An adopted skill records both `upstream_identity` and `maintainer_repository_identity`; they are never collapsed into one owner claim. A GitHub-hosted upstream should normally be upgraded and verified on a local branch first, then forked into the user's account. The validated local branch is pushed to the fork, merged or selected as its maintained default branch, assigned a new non-moving maintainer version/tag, and published with upstream-base and verification notes. A separately created derivative repository is allowed only when no useful fork exists and redistribution is licensed; it must preserve LICENSE, NOTICE, authorship, source revision, and a clear modifications statement. Missing or ambiguous license blocks public copying and routes to a local overlay or upstream clarification. SkillGuard functional pass proves workflow closure, not intellectual-property ownership or publication permission.
