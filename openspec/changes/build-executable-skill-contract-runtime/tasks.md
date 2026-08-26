## 1. FlowGuard model and design gates

- [x] 1.1 Build the executable-contract child model under the existing runtime-contract owner and run scenario, conformance, loop/progress, contract, and refinement checks.
- [x] 1.2 Build Behavior Commitment Ledger rows from user outcome through function, owner, step, check, receipt, and safe claim.
- [x] 1.3 Build Primary Path Authority dispositions for the current runtime commands and prevent a former-format success path.
- [x] 1.4 Generate ContractExhaustion cases for single, multi, composed, conditional, recovery, skip, blocked, stale, resume, concurrency, and bounded-loop paths.
- [x] 1.5 Bind every invariant and commitment to focused tests in Model-Test Alignment and TestMesh records.

## 2. V2 model export, binding source, and compiler

- [x] 2.1 Add the FlowGuard adapter and version/schema handshake with missing/unsupported-toolchain failures.
- [x] 2.2 Add schemas for model export, binding source, compiled contract, check manifest, run, event, artifact, receipt, and closure.
- [x] 2.3 Implement deterministic `compiled-contract.json` generation and read-only check mode.
- [x] 2.4 Implement exact obligation-to-check compilation and reject orphan, broad-all-check, dangling-route, duplicate-owner, unbounded-loop, and uncovered-terminal records.
- [x] 2.5 Reject former contract/closure formats as direct-current rewrite
  blockers. No former-format helper, converter, alias, or alternate reader is
  part of the current runtime.

## 3. Claimed run and route runtime

- [x] 3.1 Implement typed route selection for one function or a declared composable path.
- [x] 3.2 Implement idempotent `claim-run`, target locking, request/target/contract fingerprints, and conflicting-claim rejection.
- [x] 3.3 Implement ready-step projection, legal begin/submit/fail/block/skip-request transitions, and append-only events.
- [x] 3.4 Implement deterministic replay and `resume-run` without chat history.
- [x] 3.5 Implement loop progress tokens, unchanged-progress blocking, and finite re-entry enforcement.
- [x] 3.6 Recover failed/dead writer locks with an audit event, preserve live-writer exclusion, and reacquire locks on idempotent resume.

## 4. Evidence, checks, artifacts, and freshness

- [x] 4.1 Implement immutable hard, witnessed, and judged receipts without caller-authored pass/current authority.
- [x] 4.2 Implement raw/semantic fingerprint policy, exact child receipt consumption, supersession, and affected-only stale propagation.
- [x] 4.3 Implement controlled native/hard check execution with timeout, cwd tokenization, exit/output capture, and non-run separation.
- [x] 4.4 Implement tool/API witness records and validators for files, directories, JSON, images, screenshots, documents, UI launch/interaction, and declared native outputs.
- [x] 4.5 Implement versioned judged rubrics and explicit self-review confidence boundaries.
- [x] 4.6 Add a target-owned reverse surface inventory covering public commands,
  scripts, exports, routes, action surfaces, artifacts, and failure/recovery
  boundaries, with deterministic discovery and typed dispositions.
- [x] 4.7 Make reverse surface completeness and adequacy mandatory for depth and
  graduation; an undeclared or unmapped real surface must fail closed.
- [x] 4.8 Add negative tests proving that a new command, route, export, or
  failure boundary without a current intent/check/owner/receipt cannot pass by
  generic smoke or historical evidence.

## 5. Closure and reports

- [x] 5.1 Implement monotonic routine, functional, release, and highest-quality profiles.
- [x] 5.2 Implement per-step and whole-run reports with missing, failed, blocked, skipped, stale, next-action, residual-risk, and claim-boundary detail.
- [x] 5.3 Implement exact-receipt `close-run`, replayable closure verification, safe claims, and unsafe claim boundaries.

## 6. SkillGuard self-hosting

- [x] 6.1 Model SkillGuard's static audit, contract compile, run supervision, deep audit, global-router handoff, and provenance functions.
- [x] 6.2 Compile SkillGuard's own V2 contract and bind the existing native tests/checks without broad all-check mappings.
- [x] 6.3 Implement and document direct-current self-host validation: former
  verifier/contract identities are rejection-only inputs and the current
  source, contract, manifest, and receipt authority must be rebuilt together.
- [x] 6.4 Add false-pass, illegal-skip, stale-artifact, unrelated-check, forged-evidence, crash/replay, context-loss, concurrency, and no-progress fixtures.
- [ ] 6.5 Complete one current SkillGuard self-maintenance run at the functional profile and then at the release profile. Functional closure must consume the current source/model, compiled contract, check manifest, target-owned surface inventory, current full TestMesh aggregation, and terminal-success receipts for every required lifecycle stage. The current direct-current functional run is now executed under one frozen plan (`sha256:dcad04b37712de2c2dc37584662c08ce50d90d212714ff33dd3a2c17b1253a9e`), with all four required owners executed successfully, a passing full aggregation (`sha256:663235b40b7d181d259cbd26e194129ed13376b9fc158714adc74f3789068da2`), current staged installation/parity/smoke, and a post-install full owner execution. Release still additionally requires `real_e2e` evidence for every required stage, deterministic quality evidence, a current `.skillguard/self-host/current` terminal receipt bound to source/contract/manifest/owner-plan identities, and current Windows/Linux CI receipts. Do not convert structural `check-depth`/self-check, fixture, workflow, install, router, or aggregation-only evidence into the release claim.

## 7. Autonomous UI external pressure test

- [x] 7.1 Build the four entry routes and conditional FlowGuard gate from the local canonical Autonomous UI source.
- [x] 7.2 Bind framing, structure, concept, implementation, launch, screenshot, geometry, review, iteration, icon, and final-ledger artifacts.
- [x] 7.3 Run a controlled fixture-app positive path from claim through closure.
- [x] 7.4 Run negative cases for missing/untrusted/wrong-surface screenshots, unreachable controls, popup bounds, icon-only-in-content, structural drift without revalidation, and no-improvement loops.
- [x] 7.5 Record the bounded two-repository scope for the architecture-reduction follow-up: rerun the current SkillGuard functional self-host and repository-controlled fixture pressure test only. The external Autonomous UI pilot is explicitly out of scope for this upgrade and remains a downstream change; it MUST NOT be performed, used as current evidence, or require mutation of another repository. Pilot/fixture evidence is not a substitute for the required current terminal functional/release receipts, canonical self-host release receipt, real-e2e stage evidence, CI receipts, or quality evidence.

## 8. Lifecycle, provenance, installation, and release

- [x] 8.1 Complete direct removal, replacement, retirement, or blocking for every former field, command, generated artifact, and alternate-authority surface.
- [x] 8.2 Add fast/focused/full test manifests, current parent/child evidence, timeouts, progress, and cancellation.
- [x] 8.3 Add canonical-source, installed, repository, and release provenance with non-downgrade gates.
- [x] 8.4 Add tracked/public-export privacy checks and path tokenization.
- [ ] 8.5 Add and execute the declared Windows/Linux CI matrix, clean-install smoke, staged installed sync, global-router refresh/check, and post-install full verification. The local staged activation/install parity/router receipts and post-install full owner execution now pass under the current source identity. Keep the task open because current Windows/Linux CI terminal receipts are still absent; local Windows evidence cannot be promoted to a Linux/CI claim.
- [ ] 8.6 Update README, CHANGELOG, version, package metadata, and release notes only after the current release profile passes; publish only from the local source branch after the self-host, clean-install, post-install, CI, provenance, and full release closure receipts are current.

## 9. Third-party or bundled skill adoption

- [ ] 9.1 Inventory maintained skills without a user-owned repository, including their local/installed source, upstream identity, current modifications, and repository status.
- [ ] 9.2 Verify upstream repository, license, attribution, NOTICE, trademark, fork, and redistribution boundaries for each adoption candidate.
- [ ] 9.3 Choose and record `github_fork`, `attributed_derivative_repo`, `local_overlay_only`, `contribute_upstream`, or `do_not_adopt` for each candidate.
- [ ] 9.4 Establish a local canonical source with `origin` and `upstream` identities kept distinct before applying SkillGuard or functional changes.
- [ ] 9.5 Run model, compile, positive/negative/recovery, functional closure, provenance, and privacy gates on the adopted local source.
- [ ] 9.6 After target account/name/visibility and license text are frozen, fork an eligible GitHub upstream into the user's account, set distinct `origin` and `upstream` remotes, and push the already validated local maintenance branch.
- [ ] 9.7 Merge or select the fork maintenance branch as the fork's maintained default, choose a new maintainer version without moving upstream tags, update version/changelog metadata, create the tag and GitHub Release with upstream-base attribution and verification scope.
- [ ] 9.8 Clean-install from the fork release, rerun contract/native/functional/release and source-install-fork parity checks, then register the fork, branch, tag, upstream base, and lifecycle `active_adopted`.

## 10. One-skill-at-a-time portfolio calibration

- [x] 10.1 Freeze the optimization queue from self-host and Autonomous UI pilot through SourceGuard, WorldGuard, the merged Logic Writing target, TraceGuard, Storyline, LogicGuard, Travel Story Planner, Khaos Brain, PhysicsGuard, and later adopted candidates. Retire Research Investigation and Academic Thesis as superseded by Logic Writing with zero installation/router authority; keep DataBank explicitly excluded.
- [ ] 10.2 Extend the private portfolio registry with order, target source/version, exact current Guard identity fingerprint, contract hash, representative job ids, full-run receipt, reuse ticket, last revalidation, and graduation status.
- [ ] 10.3 For every target, capture pre-change real-job baselines and run positive, invalid-input, recovery/resume, out-of-scope, native, artifact, and judged-quality evidence after the functional repair.
- [ ] 10.4 Classify each failure as target implementation, target binding, SkillGuard model miss, SkillGuard runtime/validator gap, or external blocker and preserve the classification in the run and portfolio records.
- [ ] 10.5 For every SkillGuard miss, add the observed regression and generalized ContractExhaustion cases before the Guard repair; rerun MTA, TestMesh, self-host, and the current target.
- [ ] 10.6 Emit affected Guard feature tags for every Guard change and set matching prior graduates to `revalidation_required` instead of preserving old green status.
- [ ] 10.7 Run universal compile/schema/freshness scans across all graduates and real functional regression across every affected graduate; issue TestResultReuseTickets only with current source, contract, Guard, command, environment, and coverage fingerprints.
- [ ] 10.8 Before each target graduates, run the parent Portfolio Graduation Gate and require every current/prior target to provide a current full receipt or valid reuse ticket; require all-real full reruns for broad closure/schema/receipt/routing changes and final release.
- [x] 10.9 Validate the reviewed scope lifecycle before registry projection: every superseded target names one distinct active replacement and declares `installation_disposition: absent` plus `router_authority: blocked`.
- [x] 10.10 Add the current direct-replacement registry builder: consume only the exact hash-valid scope and current Guard, emit revision one with no old green/reuse authority, keep active targets pending or revalidation-required, preserve exclusions/supporting entries, and reject any prior-registry argument.
- [x] 10.11 Repair the current SkillGuard capability inventory to name the direct builder instead of the retired former registry command, regenerate revision-one authority only through that builder, serialize file output through the sole registry-writer lock, and cover live-writer rejection.
