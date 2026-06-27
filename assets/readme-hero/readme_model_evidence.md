# SkillGuard README Model Evidence

This file records the README-facing capability model used for the `v0.1.4` public page. It is evidence for README synthesis only; it does not replace runnable SkillGuard checks, FlowGuard checks, package publication, GitHub release confirmation, or future AI behavior validation.

## LogicGuard-Backed Capability Model

### Root Claim

SkillGuard is a local runtime-contract system for maintaining Codex skills with evidence-backed route selection, run records, checks, and closure blockers.

### Mechanism

SkillGuard reads the target skill entrypoint, detects the declared integration mode, binds source requirements to acceptance obligations, maps those obligations to SkillGuard checks or native check bindings, requires current run records tied to the contract hash, and blocks closure when evidence is stale, shallow, skipped, or parallel-route risky.

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

The README may claim local source-level checking, runtime contract records, deep contract classification, native-first binding, and source-only release status. It must not claim packaged CLI installation, broad fixture coverage, suite automation, package publication, external service behavior, GitHub release creation, or future AI correctness unless those are separately verified.

### Objection And Rebuttal

Objection: A global SkillGuard route could reduce target-skill flexibility.

Rebuttal: The README presents the global router as a selection and handoff registry only. It does not make SkillGuard a mandatory gate before every skill invocation, and native-integrated or hybrid-extension targets must bind their own route/check owners instead of accepting a parallel SkillGuard execution route.

## README Synthesis Use

The README keeps the root claim near the top, explains why shallow skill upgrades are risky, then shows the contract executor, native-first rule, command surface, README/release gates, validation boundary, and source-only release status. Claims that lack current runnable evidence are either excluded or described as not provided.
