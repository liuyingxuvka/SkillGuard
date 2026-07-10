# SkillGuard README Model Evidence

This file records the LogicGuard-backed capability model used for the `v0.3.0` public README page. It is evidence for README synthesis only; it does not replace runnable SkillGuard checks, FlowGuard checks, package publication, GitHub release confirmation, or future AI behavior validation.

## Repository Fact Ledger

- product surface: SkillGuard is a local Codex skill maintenance and runtime-contract framework with a Python command dispatcher under `.agents/skills/skillguard/scripts/`.
- entry points: public README, `.agents/skills/skillguard/SKILL.md`, the V1 dispatcher, V2 compiler/supervisor/self-host/TestMesh/install/provenance/privacy scripts, the FlowGuard executable model, schemas, fixtures, tests, and CI workflow definition.
- release/version facts: the prepared public release line is `v0.3.0`; `VERSION`, `pyproject.toml`, README, changelog, and release notes must match before tagging.
- runtime facts: the supported interpreter boundary is Python 3.11+ because the current FlowGuard runtime requires standard-library `tomllib`; CI covers Python 3.11 and 3.12 on Windows and Linux.
- privacy-sensitive exclusions: public README material must not expose local absolute paths, private installed-skill inventories, private task text, credentials, internal coordination transcripts, or user-specific workflow details.

## LogicGuard-Backed Capability Model

### Root Claim

SkillGuard is a local executable-contract and maintenance system for Codex skills with model-owned routes, target bindings, claimed runs, exact checks, immutable evidence, replayable closure, installation safety, and visible claim boundaries.

### Mechanism

SkillGuard reads the target entrypoint and integration mode, compiles a current FlowGuard model plus confirmed target bindings into an exact V2 contract, claims and locks the target-local run, derives pass only through checks/witnesses/rubrics, replays hash-chained events, and blocks closure when evidence is stale, shallow, skipped, generic, unrelated, or parallel-route risky. Its portfolio parent inventories every maintained target capability, invalidates old green evidence after Guard changes, and graduates one target only from receipt-bound route coverage plus current prior evidence.

### Evidence

- Source contract fields: `.agents/skills/skillguard/assets/schemas/skillguard_work_contract.schema.json`.
- Default contract template: `.agents/skills/skillguard/assets/templates/skillguard_work_contract.template.json`.
- Runtime command surface: `.agents/skills/skillguard/scripts/skillguard.py` and `.agents/skills/skillguard/scripts/checker_engine.py`.
- Deep negative fixtures: `.agents/skills/skillguard/fixtures/deep_contract/`.
- Runtime contract fixtures: `.agents/skills/skillguard/fixtures/runtime_contract/`.
- Standard-library local tests: `tests/test_skillguard_local.py`.
- V2 focused/full test ownership: `.agents/skills/skillguard/test-mesh.json` and `skillguard_test_mesh.py`.
- Staged local installation and rollback: `skillguard_install.py` plus `tests/test_installation.py`.
- Current self-host and external-target evidence remains local runtime evidence and is not committed as public task history.

### Reader Value

Skill authors and maintainers can see whether a target skill is only wrapped by shallow entry text or is actually governed by a current work contract, native route binding, evidence trail, and closure gate.

### Boundary

The README may claim the source-level V1 and V2 runtime, focused/full local TestMesh, staged whole-tree install/rollback, installed-source parity, privacy/provenance checks, native-first binding, and current local self-host closure. It must not claim packaged CLI distribution, hosted service behavior, binary artifacts, remote CI success, GitHub release creation, cross-platform runtime proof, or future AI correctness unless separately verified.

### Objection And Rebuttal

Objection: A global SkillGuard route could reduce target-skill flexibility.

Rebuttal: The README presents the global router as a selection and handoff registry only. It does not make SkillGuard a mandatory gate before every skill invocation, and native-integrated or hybrid-extension targets must bind their own route/check owners instead of accepting a parallel SkillGuard execution route.

## Capability Claim Matrix

| claim | problem | mechanism | evidence | warrant | reader value | boundary | objection |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SkillGuard checks skill contracts deeply. | A skill can look upgraded while only having generic contract fields. | `check-depth` compares inferred target requirements with target rules, routes, workflow stages, checks, evidence ids, coverage rows, and closure blockers. | `checker_engine.py`, work-contract schema/template, deep-contract fixtures, local tests. | A target-specific row must connect a rule to an obligation, route, stage, check or native binding, evidence, and blocker. | Maintainers can distinguish real coverage from shallow wrappers. | It proves local contract coverage, not future AI behavior. | The checker may still miss human semantic intent; residual risk is surfaced instead of hidden. |
| SkillGuard executes V2 contracts from model to closure. | Prose plans and AI-authored “complete” can omit routes, fields, checks, or artifacts. | A FlowGuard model plus confirmed binding compiles exact routes and checks; a target-local claimed run records transitions and immutable receipts; only current receipts can close. | V2 model, compiler, supervisor, schemas, negative fixtures, 123-test focused suite, and self-host receipts. | Route, obligation, check, evidence, artifact, and closure identities are bound by current fingerprints. | Maintainers can inspect exactly what ran, failed, skipped, became stale, or remains outside the claim. | It does not prove future model behavior or the truth of subjective judgment. | Judged evidence remains evaluator-bound and states limitations. |
| SkillGuard graduates a portfolio one capability-complete target at a time. | A single successful job or an old green result can hide untested routes after the Guard changes. | A private ordered registry distinguishes active, adopted, excluded, retired, system, and supporting entries; every active target declares required capabilities; representative jobs bind route coverage and evidence refs into the receipt fingerprint; registered Guard changes invalidate old current status. | Portfolio schemas/runtime, four CLI fixtures, FlowGuard negative scenarios, focused tests, self-host receipts, and external target graduation evidence. | Current status is derived only when the exact Guard identity, target five-part identity, required capability coverage, and every prior proof are current. | Maintainers can improve skills sequentially without silently skipping an earlier target or carrying stale confidence forward. | The private registry and real target evidence remain outside public repositories; public release material claims only the runtime capability. | A proof-bound reuse ticket is allowed only for a registered non-broad, non-intersecting change and unchanged identity. |
| Failed or crashed locks recover without weakening concurrency safety. | A failed process can otherwise leave a permanent writer lock, while aggressive cleanup could permit two live writers. | New locks record the owner process; dead-owner recovery emits an event; legacy locks recover only from verified terminal events; idempotent resume reacquires locks. | `run_store.py`, lock recovery model invariant, ContractExhaustion case, and focused/full regression tests. | Recovery requires a concrete dead/terminal condition under the atomic claim guard. | Interrupted work can resume without silently disabling live-writer exclusion. | It is local process ownership, not a distributed lease service. | Unknown or still-live ownership remains blocking. |
| Whole-tree installation is parity-checked and reversible. | Partial copy can silently downgrade an installed skill. | Stage the complete skill source, compare manifests, run installed-layout smoke checks, atomically activate, retain backup, and roll back on failure. | `skillguard_install.py`, installation tests, installed-source provenance audit. | Activation cannot start from a partial or stale stage. | Local installed behavior stays traceable to the canonical repository source. | It is not a packaged CLI or installer product. | Remote/cross-platform installation still needs its own evidence. |
| Generated contracts are checkout-platform stable. | Raw text-byte hashing makes LF and CRLF checkouts produce different contracts. | Contract source fingerprints normalize UTF-8 text line endings and retain exact hashing for binary assets. | Compiler implementation, LF/CRLF regression, Windows/Linux CI. | Semantically identical committed text must compile identically across checkout platforms. | A committed contract can be verified on Windows and Linux without hiding real binary changes. | Other environment-dependent behavior remains separately tested. | A true source or binary change still invalidates the generated contract. |
| SkillGuard preserves native skill routes. | Adding a second route can weaken FlowPilot, FlowGuard, README, UI, or other existing skill workflows. | Contracts declare `native-integrated`, `hybrid-extension`, or `skillguard-runtime` and bind native route/check owners when present. | Native binding fields, phase native bindings, FlowPilot checks, installed audit rows. | Native/hybrid targets fail when they retain a SkillGuard-owned run record or allow parallel execution. | Existing skill behavior remains the main work path while SkillGuard adds gates around it. | It does not prove the native system itself is perfect. | Native evidence must still be current and separately checked. |
| SkillGuard README release gates are evidence-bound. | A README can claim current release depth while model evidence is stale. | `check-readme-release` checks bilingual mirror, hero provenance, version consistency, public boundary, and this version-bound README model. | README, VERSION, pyproject, changelog, hero prompt/design note, this model evidence. | The README page stays attractive but honest. | It does not prove package publication or binary assets. | A compact model summary might seem enough. | Highest-standard README work requires this full matrix, not only a summary. |
| Installed-skill audit is local coverage evidence. | Local installed skills can pass coverage while not being individual GitHub repositories. | `audit-installed-skills` reports local deep coverage and publication status separately. | Installed skill work contracts and publication-status rows. | The user can see what is covered locally without accidental GitHub overclaiming. | It does not push, tag, or release those skills. | A passing local audit may be mistaken for publication. | The report must separate local coverage from remote publication. |

## Narrative Structure Plan

- first-screen promise: define SkillGuard as a local runtime-contract system for keeping Codex skills on the right path.
- section order: start with why shallow skill upgrades are risky, then show current capability, status, command surface, runtime contract executor, native-first integration, workflows, README/release gates, validation, non-goals, public boundary, repository layout, release history, and license.
- visual proof placement: place one generated concept hero image immediately after the H1 so the native-route-to-contract-gate workflow is visible before detailed text.
- quick-start placement: keep command examples under Command Surface and Typical Workflows, after the reader understands what the tool is.
- public/private boundary placement: keep public boundary and non-goal sections near the validation and repository layout sections so readers understand exactly what the release does not claim.

## Gap Ledger

- unsupported claims: packaged CLI distribution, hosted service behavior, binary release artifact, remote CI success, package publication, cross-platform runtime proof, and future AI correctness remain unsupported and must not be claimed.
- missing evidence: broad external-service behavior and package publication are not part of this source-only release evidence.
- maturity: SkillGuard is a `0.3.x` source-level alpha; V2 and the portfolio runtime are executable and self-hosted locally, but the README must not imply stable 1.0 maturity.
- privacy risks: public examples must avoid private installed-skill inventory details, local absolute paths, private project names, credentials, and internal task transcripts.

## README Synthesis Use

The README keeps the root claim near the top, explains why shallow skill upgrades are risky, then shows the contract executor, native-first rule, command surface, README/release gates, validation boundary, and source-only release status. Claims that lack current runnable evidence are either excluded or described as not provided.
