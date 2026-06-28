# SkillGuard README Model Evidence

This file records the LogicGuard-backed capability model used for the `v0.1.6` public README page. It is evidence for README synthesis only; it does not replace runnable SkillGuard checks, FlowGuard checks, package publication, GitHub release confirmation, or future AI behavior validation.

## Repository Fact Ledger

- product surface: SkillGuard is a local Codex skill maintenance and runtime-contract framework with a Python command dispatcher under `.agents/skills/skillguard/scripts/`.
- entry points: public README, `.agents/skills/skillguard/SKILL.md`, `skillguard.py`, `checker_engine.py`, work-contract schemas/templates, fixtures, and local standard-library tests.
- release/version facts: current public release line is `v0.1.6`; `VERSION`, `pyproject.toml`, README, and changelog are expected to match this release until the next patch release is prepared.
- privacy-sensitive exclusions: public README material must not expose local absolute paths, private installed-skill inventories, private task text, credentials, internal coordination transcripts, or user-specific workflow details.

## LogicGuard-Backed Capability Model

### Root Claim

SkillGuard is a local runtime-contract system for maintaining Codex skills with evidence-backed route selection, target-specific coverage matrices, run records, checks, and closure blockers.

### Mechanism

SkillGuard reads the target skill entrypoint, detects the declared integration mode, binds source requirements to acceptance obligations, maps those obligations to SkillGuard checks or native check bindings, requires current run records only for SkillGuard-owned runtime targets, and blocks closure when evidence is stale, shallow, skipped, generic, or parallel-route risky.

### Evidence

- Source contract fields: `.agents/skills/skillguard/assets/schemas/skillguard_work_contract.schema.json`.
- Default contract template: `.agents/skills/skillguard/assets/templates/skillguard_work_contract.template.json`.
- Runtime command surface: `.agents/skills/skillguard/scripts/skillguard.py` and `.agents/skills/skillguard/scripts/checker_engine.py`.
- Deep negative fixtures: `.agents/skills/skillguard/fixtures/deep_contract/`.
- Runtime contract fixtures: `.agents/skills/skillguard/fixtures/runtime_contract/`.
- Standard-library local tests: `tests/test_skillguard_local.py`.

### Reader Value

Skill authors and maintainers can see whether a target skill is only wrapped by shallow entry text or is actually governed by a current work contract, native route binding, evidence trail, and closure gate.

### Boundary

The README may claim local source-level checking, runtime contract records, deep contract classification, native-first binding, README release gates, and source-only release status. It must not claim packaged CLI installation, broad fixture coverage, suite automation, package publication, external service behavior, GitHub release creation, or future AI correctness unless those are separately verified.

### Objection And Rebuttal

Objection: A global SkillGuard route could reduce target-skill flexibility.

Rebuttal: The README presents the global router as a selection and handoff registry only. It does not make SkillGuard a mandatory gate before every skill invocation, and native-integrated or hybrid-extension targets must bind their own route/check owners instead of accepting a parallel SkillGuard execution route.

## Capability Claim Matrix

| claim | problem | mechanism | evidence | warrant | reader value | boundary | objection |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SkillGuard checks skill contracts deeply. | A skill can look upgraded while only having generic contract fields. | `check-depth` compares inferred target requirements with target rules, routes, workflow stages, checks, evidence ids, coverage rows, and closure blockers. | `checker_engine.py`, work-contract schema/template, deep-contract fixtures, local tests. | A target-specific row must connect a rule to an obligation, route, stage, check or native binding, evidence, and blocker. | Maintainers can distinguish real coverage from shallow wrappers. | It proves local contract coverage, not future AI behavior. | The checker may still miss human semantic intent; residual risk is surfaced instead of hidden. |
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

- unsupported claims: packaged CLI installation, hosted service behavior, binary release artifact, suite automation completeness, package publication, and future AI correctness remain unsupported and must not be claimed.
- missing evidence: broad external-service behavior and package publication are not part of this source-only release evidence.
- maturity: SkillGuard is still a `0.1.x` source-level tool; the README should present it as useful and current without claiming stable 1.0 maturity.
- privacy risks: public examples must avoid private installed-skill inventory details, local absolute paths, private project names, credentials, and internal task transcripts.

## README Synthesis Use

The README keeps the root claim near the top, explains why shallow skill upgrades are risky, then shows the contract executor, native-first rule, command surface, README/release gates, validation boundary, and source-only release status. Claims that lack current runnable evidence are either excluded or described as not provided.
