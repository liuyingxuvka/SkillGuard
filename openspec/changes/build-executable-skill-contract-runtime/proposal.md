## Why

SkillGuard currently validates static and deep contract structure, but a real AI task does not have to claim a current contract, follow a function-specific path, produce declared artifacts, submit evidence step by step, survive context loss, or obtain a verifier-derived closure receipt. A structurally deep skill can therefore still omit a user-visible function or claim completion from prose, stale output, or an unrelated native check.

FlowGuard's current local source provides concrete mechanisms to build on: deterministic semantic-source compilation, typed route handoffs, unique owners, bounded SCC loops, primary-path authority, behavior commitments, contract exhaustion, model-test alignment, and planned immutable evidence receipts. Its current suite also demonstrates the migration risk: the compiler tests pass while all 17 real member contracts still have missing or stale generated artifacts. SkillGuard must adopt the proven mechanisms while reducing generated surface and making real per-task execution mandatory.

## What Changes

- Replace the post-hoc functional-closure-record direction with a FlowGuard-compiled executable skill contract.
- Give every maintained skill a FlowGuard function/state model plus a small target-specific binding source for tools, scripts, APIs, artifacts, native checks, and judgment rubrics.
- Deterministically generate only `compiled-contract.json` and `check-manifest.json` as published contract artifacts.
- Add typed single-function, multi-function, conditional, composed, recovery, and bounded-loop routes with one canonical owner per business intent.
- Require every real task, including native-integrated tasks, to `claim-run` and persist an append-only recoverable run outside the installed skill package.
- Make AI actions submit evidence rather than authoritatively set pass/current; derive step and run status from hard, witnessed, or explicitly judged receipts.
- Add artifact contracts for files, JSON, images, screenshots, documents, UI launch/interaction evidence, and target-native outputs.
- Add routine, functional, release, and highest-quality closure profiles with exact receipt consumption and freshness propagation.
- Self-host the runtime on SkillGuard before any future external end-to-end pressure test. This current upgrade is bounded to SkillGuard itself and its repository-controlled fixtures; no external target repository is required or authorized by this change.
- Add source/installed/GitHub provenance and non-downgrade controls after functional closure works, before publication.
- Add an adoption route for maintained third-party or bundled skills that do not yet have a user-owned repository: preserve upstream identity and license, upgrade from a local canonical source, then by default fork an eligible GitHub upstream into the user's account, push the validated local maintenance branch, assign a new maintainer release version, publish a GitHub Release, and post-verify it. Attributed derivative or local overlay modes remain explicit exceptions when a fork is unavailable or redistribution is blocked.
- Add a one-skill-at-a-time portfolio calibration loop. Every target must prove representative real user outcomes after optimization. A target failure that exposes a SkillGuard miss must first become generalized replay evidence, repair SkillGuard, invalidate affected prior skill confidence, and trigger current revalidation before the target or portfolio can graduate.

## Authority status

`build-executable-skill-contract-runtime` is the sole current OpenSpec authority
for SkillGuard's executable contract, functional/release/highest-quality closure,
self-host acceptance, CI/release acceptance, and the related current schemas,
tasks, and terminal-evidence rules. The archived
`../archive/2026-08-20-add-skill-functional-closure-audit` change is provenance
only: it is superseded, is not an implementation entry point, and cannot supply
current commands, schemas, receipts, closure, or release authority. The active
`add-bounded-evidence-lifecycle` change remains an independent evidence-store
and lifecycle authority; it does not define executable-contract or closure
semantics and cannot create a competing self-host or release claim. If its
implementation changes inputs consumed by this change, those inputs require a
direct-current rebuild and revalidation here.

Former contract, closure, receipt, or installation identities are rejection-only
direct-current rewrite inputs. The current runtime has no compatibility reader,
fallback path, migration command, converter, alias, dual manifest, or alternate
success authority. An identity mismatch is a visible upgrade blocker until the
current source is manually rewritten and freshly validated.

## Capabilities

### New Capabilities

- `executable-skill-contract-compilation`: Compile FlowGuard behavior models and target bindings into deterministic executable contracts and exact check manifests.
- `claimed-skill-run-runtime`: Select a declared function route, claim a task run, return ready steps, record append-only events, enforce bounded recovery loops, and resume without chat memory.
- `skill-evidence-receipts`: Validate hard, witnessed, and judged evidence; create immutable receipts; derive freshness; and propagate child or input changes.
- `skill-functional-closure`: Close only when every required current step, artifact, check, terminal, and child receipt satisfies the selected claim profile.
- `skill-source-provenance`: Preserve canonical-source authority and reject installed or publication downgrade after the runtime is functionally proven.
- `portfolio-skill-calibration-loop`: Optimize skills in a fixed simple-to-complex order, classify target failures, feed Guard misses back into SkillGuard, and require affected prior skills to remain current through TestMesh-backed revalidation or valid reuse tickets.

### Modified Capabilities

None. Existing command behavior remains unchanged until its lifecycle disposition is explicitly implemented under Primary Path Authority. The previous `add-skill-functional-closure-audit` change is superseded, historical-only, and is not a parallel execution path or source of current acceptance.

## Impact

- New focused compiler, route runtime, run store, step runtime, check runner, artifact validator, receipt, closure, and provenance modules behind the existing CLI facade.
- New FlowGuard child model, Behavior Commitment Ledger, Primary Path Authority, ContractExhaustion, Model-Test Alignment, and TestMesh evidence.
- New v2 schemas and fixtures; former runtime shapes are rejection-only direct-current rewrite inputs and fail closed. No compatibility reader, fallback, migration command, converter, alias, or alternate current authority is introduced.
- SkillGuard self-contract, tests, documentation, installation flow, global-router freshness, CI, and release metadata.
- Any future external target receives a compiled contract only through a separate, explicitly authorized change after SkillGuard self-host closure passes; no external target is part of this current change's acceptance boundary.
- Later adopted skills may gain a user-owned GitHub fork or attributed derivative repository, but repository creation is downstream of provenance, license, local-source, and closure gates.
- Portfolio records gain optimization order, representative job sets, Guard compatibility fingerprints, graduation state, revalidation state, full-run receipts, and scoped result-reuse tickets.

## Terminal acceptance boundary

- A functional claim requires the current source, FlowGuard model export, compiled contract, check manifest, target-owned surface inventory, and one current full TestMesh aggregation for the self-host maintenance unit. Every required lifecycle stage must be represented by a current immutable terminal-success receipt under the exact unit, member, check, owner, request, input, dependency, toolchain, environment, and projection identities. Functional positive-path evidence is `simulated_e2e` or stronger; required failure, recovery, non-goal, and terminal evidence must meet the current target declaration. Structural `check-contract`, `check-depth`, a fixture, a progress log, or an aggregation-only record cannot replace the consumed terminal receipts.
- A release claim is stricter. Every required lifecycle stage needs current `real_e2e` or stronger evidence, deterministic quality evidence, a current `.skillguard/self-host/current` terminal receipt bound to the current source/contract/manifest/owner-plan identities, clean-install smoke and source/installed projection parity, post-install full self-host verification, and current Windows and Linux CI terminal receipts. A declared workflow, local install receipt, router refresh, or source/installed parity result without those current receipts leaves release `not_run` or `blocked`.
- A highest-quality claim includes the complete release boundary plus current human or domain-expert quality evidence for each declared quality requirement. Simulated, deterministic, or fixture-only evidence cannot satisfy that quality claim.
- Any missing, stale, foreign, duplicate, or mismatched identity blocks the named claim. The report must preserve the exact gap and next action; it must not select a former artifact or a compatibility/fallback path.
