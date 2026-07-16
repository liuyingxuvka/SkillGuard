# SkillGuard README Model Evidence

This file records the LogicGuard-backed capability model used for the `v0.3.1` source README update. It is evidence for README synthesis only; it does not replace runnable SkillGuard checks, FlowGuard checks, package publication, GitHub release confirmation, or future AI behavior validation.

## Repository Fact Ledger

- product surface: SkillGuard is a local Codex skill maintenance and runtime-contract framework with a Python command dispatcher under `.agents/skills/skillguard/scripts/`.
- entry points: public README, `.agents/skills/skillguard/SKILL.md`, the current dispatcher, compiler, supervisor, execution-depth, project-adoption, self-host, TestMesh, install, provenance, and privacy scripts, the FlowGuard executable model, schemas, fixtures, tests, and CI workflow definition.
- release/version facts: the source version is being advanced to `v0.3.1`; `VERSION`, `pyproject.toml`, README, changelog, and release notes must match before any tag or GitHub Release claim.
- runtime facts: the supported interpreter boundary is Python 3.11+ because the current FlowGuard runtime requires standard-library `tomllib`; CI covers Python 3.11 and 3.12 on Windows and Linux.
- privacy-sensitive exclusions: public README material must not expose local absolute paths, private installed-skill inventories, private task text, credentials, internal coordination transcripts, or user-specific workflow details.

## LogicGuard-Backed Capability Model

### Root Claim

SkillGuard is a local executable-contract and maintenance system for Codex skills with model-owned routes, target bindings, claimed runs, exact checks, target-owned execution-depth receipts, portable repository adoption, replayable closure, installation safety, and visible claim boundaries.

### Mechanism

SkillGuard reads the target entrypoint and its target-owned native route/check declarations, compiles the current FlowGuard model plus confirmed bindings into the one current contract, freezes every declared check and owner, claims and locks the target-local run, reconciles immutable terminal receipts, replays hash-chained events, and blocks closure when evidence is missing, duplicated, failed, skipped, stale, non-terminal, foreign, or cleanup-unconfirmed. Project adoption separately writes and audits one marker-bounded repository prompt block plus a hash-bound manifest.

### Evidence

- Source contract fields: `.agents/skills/skillguard/assets/schemas/skillguard_work_contract.schema.json`.
- Default generated authority: one portable FlowGuard model plus `.skillguard/contract-source.json`, compiled deterministically into `.skillguard/compiled-contract.json` and `.skillguard/check-manifest.json`; former contract shapes are rejected rather than read or converted.
- Runtime command surface: `.agents/skills/skillguard/scripts/skillguard.py` and `.agents/skills/skillguard/scripts/checker_engine.py`.
- Deep negative fixtures: `.agents/skills/skillguard/fixtures/deep_contract/`.
- Runtime contract fixtures: `.agents/skills/skillguard/fixtures/runtime_contract/`.
- Standard-library local tests: `tests/test_skillguard_local.py`.
- Current focused/full test ownership: `.agents/skills/skillguard/test-mesh.json` and `skillguard_test_mesh.py`.
- Declared-check supervision runtime, fixed enforced profile, generic one-check/multi-check model, and omitted-check negative fixture: `skillguard_v2/declared_check_supervision.py`, `skillguard_v2/execution_depth.py`, `.flowguard/declared_check_supervision/`, and the generic supervision tests.
- Portable project adoption and the representative ordinary-skill repository slice: `skillguard_v2/project_adoption.py`, `fixtures/generic_project/`, and `tests/test_skillguard_project_adoption.py`.
- Staged local installation and rollback: `skillguard_install.py` plus `tests/test_installation.py`.
- Current self-host and external-target evidence remains local runtime evidence and is not committed as public task history.

### Reader Value

Skill authors and maintainers can distinguish four different things that are often conflated: a skill was discoverable, its declared checks were mapped, every declared check actually produced a current terminal receipt for this request, and its repository carries a portable maintenance handoff for future agents.

### Boundary

The README may claim the one current source runtime, exact declared-check compilation, target-native receipt binding, honest non-pass statuses, marker-bounded project adoption, focused/full local TestMesh, staged whole-tree install/rollback, privacy/provenance checks, native-owned routing, and current local self-host closure only after their current checks pass. It must not claim packaged CLI distribution, hosted service behavior, binary artifacts, remote CI success, GitHub release creation, domain correctness, or future AI correctness unless separately verified.

### Objection And Rebuttal

Objection: A global SkillGuard route could reduce target-skill flexibility.

Rebuttal: The README presents the global router as a selection and handoff registry only. It does not make SkillGuard a mandatory gate before every skill invocation, and every target must bind its own route/check owner under the single current integration marker instead of accepting a parallel SkillGuard execution route.

Objection: A complete-looking depth profile could become another checkbox layer.

Rebuttal: The README separates `CONTRACT_DEPTH_PASS` from `EXECUTION_DEPTH_PASS`. The fixed `enforced` closure requires one exact current terminal-success receipt for every target-declared check and rejects omissions, duplicates, stale evidence, and caller-authored pass claims.

## Capability Claim Matrix

| claim | problem | mechanism | evidence | warrant | reader value | boundary | objection |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SkillGuard checks declared contracts exactly. | A skill can look upgraded while its compiled contract silently omits a declared check. | `check-depth` compares the target declaration with owners, dependencies, compiled checks, immutable receipts, and closure consumption. | `checker_engine.py`, current contract schemas/templates, declared-check FlowGuard model, and local tests. | Every target-declared check must remain represented exactly once and produce one current terminal-success receipt before closure. | Maintainers can distinguish complete supervision from a shallow wrapper. | It proves declared contract execution, not future AI behavior or domain truth. | The target's own check design may still be incomplete; that residual risk remains target-owned. |
| SkillGuard executes current contracts from model to closure. | Prose plans and AI-authored “complete” can omit routes, fields, checks, or artifacts. | A FlowGuard model plus confirmed binding compiles exact routes and checks; a target-local claimed run records transitions and immutable receipts; only current receipts can close. | Current model, compiler, supervisor, schemas, negative fixtures, focused regression suite, and self-host receipts. | Route, obligation, check, evidence, artifact, and closure identities are bound by current fingerprints. | Maintainers can inspect exactly what ran, failed, skipped, became stale, or remains outside the claim. | It does not prove future model behavior or the truth of subjective judgment. | Judged evidence remains evaluator-bound and states limitations. |
| SkillGuard separates mapped checks from executed checks. | A target can list several checks yet omit one during execution. | The fixed workflow freezes the exact declared-check inventory, one owner and dependency graph per check, then reconciles immutable terminal receipts before closure. | `declared_check_supervision.py`, `execution_depth.py`, compiler/supervisor/closure integration, FlowGuard declared-check model, and focused tests. | Contract presence cannot produce `EXECUTION_DEPTH_PASS`; every declared check must have one current terminal-success receipt for the same request and owner. | Maintainers can prevent “loaded the skill” or “ran one convenient check” from masquerading as completion. | It proves the declared exact run, not domain truth or future AI behavior. | Target skills still own every domain action, model, simulation, search, fixture, oracle, and judgment. |
| SkillGuard carries maintenance rules with each adopted repository. | A future AI or another computer may not know that the repository expects SkillGuard maintenance. | `project-adopt` and `project-audit` manage one bounded `AGENTS.md` block and `.skillguard/project.json`, including the canonical GitHub URL, managed paths, fixed integration marker, native-owner evidence, hashes, and claim boundary. Re-adoption directly writes the current shape. | `project_adoption.py`, project schema, corruption tests, self-adopted SkillGuard repository, and ordinary-skill fixture repository. | Missing, duplicate, tampered, stale, non-current, or incomplete adoption blocks fail closed while surrounding project instructions are preserved. | Maintenance expectations remain discoverable and portable without taking over ordinary skill execution. | Project adoption is routing evidence, not runtime or release proof. | A current execution receipt and native tests are still required separately. |
| Target checks retain domain ownership. | A universal supervisor can accidentally force one domain's test pattern onto every skill. | SkillGuard never classifies target families or invents purpose, counterexample, fixture, or oracle requirements; it supervises whatever checks the target declares. | Generic one-check and multi-check FlowGuard scenarios, ordinary-skill fixture, retired-field rejection tests, and target-owned native bindings. | The same inventory and receipt rules apply regardless of check names or count. | Ordinary skills avoid artificial paired tests, while skills with richer native suites still cannot omit a declared member. | SkillGuard does not judge whether the target's own suite is a perfect domain specification. | Domain quality remains the target skill's responsibility. |
| Failed or crashed current locks recover without weakening concurrency safety. | A failed process can otherwise leave a permanent writer lock, while aggressive cleanup could permit two live writers. | Current locks record the owner process; dead-owner recovery emits an event; non-current lock shapes block; an explicit current execution may reacquire a recoverable lock. | `run_store.py`, lock recovery model invariant, ContractExhaustion case, and focused/full regression tests. | Recovery requires a concrete current dead/terminal condition under the atomic claim guard. | Interrupted work can continue without silently disabling live-writer exclusion or reading a former lock shape. | It is local process ownership, not a distributed lease service. | Unknown, non-current, or still-live ownership remains blocking. |
| Whole-tree installation is parity-checked and reversible. | Partial copy can silently downgrade an installed skill. | Stage the complete skill source, compare manifests, run installed-layout smoke checks, atomically activate, retain backup, and roll back on failure. | `skillguard_install.py`, installation tests, installed-source provenance audit. | Activation cannot start from a partial or stale stage. | Local installed behavior stays traceable to the canonical repository source. | It is not a packaged CLI or installer product. | Remote/cross-platform installation still needs its own evidence. |
| Generated contracts are checkout-platform stable. | Raw text-byte hashing makes LF and CRLF checkouts produce different contracts. | Contract source fingerprints normalize UTF-8 text line endings and retain exact hashing for binary assets. | Compiler implementation, LF/CRLF regression, Windows/Linux CI. | Semantically identical committed text must compile identically across checkout platforms. | A committed contract can be verified on Windows and Linux without hiding real binary changes. | Other environment-dependent behavior remains separately tested. | A true source or binary change still invalidates the generated contract. |
| SkillGuard preserves native skill routes. | Adding a second route can weaken an existing skill workflow. | Contracts use the sole current `native-integrated` marker and bind target-owned route/check owners; any alternate integration marker or parallel domain executor is rejected. | Native binding fields, singleton-marker schema tests, global-router checks, and installed audit rows. | The target's route remains the only domain execution path while SkillGuard supervises receipts around it. | Existing skill behavior remains the main work path while SkillGuard adds generic gates around it. | It does not prove the native system itself is perfect. | Native evidence must still be current and separately checked. |
| SkillGuard README release gates are evidence-bound. | A README can claim current release depth while model evidence is stale. | `check-readme-release` checks bilingual mirror, hero provenance, version consistency, public boundary, and this version-bound README model. | README, VERSION, pyproject, changelog, hero prompt/design note, this model evidence. | The README page stays attractive but honest. | It does not prove package publication or binary assets. | A compact model summary might seem enough. | Highest-standard README work requires this full matrix, not only a summary. |
| Installed-skill audit is local coverage evidence. | Local installed skills can pass coverage while not being individual GitHub repositories. | `audit-installed-skills` reports local deep coverage and publication status separately. | Installed skill work contracts and publication-status rows. | The user can see what is covered locally without accidental GitHub overclaiming. | It does not push, tag, or release those skills. | A passing local audit may be mistaken for publication. | The report must separate local coverage from remote publication. |

## Narrative Structure Plan

- first-screen promise: define SkillGuard as a local runtime-contract system for keeping Codex skills on the right path.
- section order: start with why shallow skill upgrades are risky, then distinguish contract depth from execution depth, show portable project adoption, current capability, status, command surface, runtime contract executor, native-first integration, workflows, validation, non-goals, public boundary, repository layout, release history, and license.
- visual proof placement: place one generated concept hero image immediately after the H1 so the native-route-to-contract-gate workflow is visible before detailed text.
- quick-start placement: keep command examples under Command Surface and Typical Workflows, after the reader understands what the tool is.
- public/private boundary placement: keep public boundary and non-goal sections near the validation and repository layout sections so readers understand exactly what the release does not claim.

## Gap Ledger

- unsupported claims: packaged CLI distribution, hosted service behavior, binary release artifact, remote CI success, package publication, cross-platform runtime proof, and future AI correctness remain unsupported and must not be claimed.
- missing evidence: broad external-service behavior and package publication are not part of this source-only release evidence.
- maturity: SkillGuard is a `0.3.x` source-level alpha; current declared-check supervision and project adoption are executable and locally tested, but the README must not imply stable 1.0 maturity, universal domain correctness, or future-agent guarantees.
- privacy risks: public examples must avoid private installed-skill inventory details, local absolute paths, private project names, credentials, and internal task transcripts.

## README Synthesis Use

The README keeps the root claim near the top, explains why shallow skill upgrades are risky, distinguishes contract mapping from current execution, shows the portable repository handoff, then presents the contract executor, native-first rule, command surface, validation boundary, and source-only release status. Claims that lack current runnable evidence are either excluded or described as not provided.
