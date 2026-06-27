# SkillGuard

<!-- README HERO START -->
<p align="center">
  <img src="./assets/readme-hero/hero.png" alt="SkillGuard concept hero image showing skill files flowing through contracts, native bindings, evidence gates, and closure" width="100%" />
</p>

<p align="center">
  <strong>A local runtime-contract system for keeping Codex skills honest before, during, and after skill work.</strong>
</p>
<!-- README HERO END -->

Current release: `v0.1.3`

SkillGuard is a local maintenance and runtime-contract framework for Codex skills. It helps a skill define the route it should take, lock the expected work into a contract, record evidence while the work happens, run checks before closure, and report exactly what was checked, skipped, stale, blocked, or still uncertain.

It is designed for skill repositories where optimistic claims are easy to make: a skill can say it has checks that are not present, a suite can hide a failing child, an agent can skip a phase, or a README can imply release readiness that the files do not prove.

## What SkillGuard Does

SkillGuard gives maintainers a concrete way to ask:

- Which skill or route should handle this task?
- Does the target skill already have its own route or check system?
- If it does, is SkillGuard attached to that native system instead of adding a parallel path?
- What work contract, phase order, evidence, and checks must exist before the task can be closed?
- Which claims are supported by current files and current command output?
- Which claims are stale, skipped, blocked, or outside the current evidence boundary?

The important design rule is native-first integration:

> If a target skill already owns a route, controller, simulator, checker, or release flow, SkillGuard must bind its checks to that native system. It must not create a second SkillGuard-owned execution route beside the original workflow.

## Current Status

SkillGuard currently ships as source plus a local Python script surface inside this repository. It is not yet a packaged console command.

| Area | Current state |
| --- | --- |
| Codex skill entrypoint | `.agents/skills/skillguard/SKILL.md` |
| Local command dispatcher | `.agents/skills/skillguard/scripts/skillguard.py` |
| Runtime contracts | `compile-contract`, `check-contract`, `select-route`, `start-run`, `advance-run`, `check-run`, `close-run` |
| Global router support | `scan-global-skills`, `build-global-registry`, `check-global-registry`, `resolve-global-skill`, `render-global-prompt`, `install-global-prompt`, `check-global-prompt`, `refresh-global-router` |
| Skill and suite generation | `plan-skill`, `generate-skill`, `generate-suite` |
| Maintenance checks | `fixture-test`, `detect-stale-evidence`, `refresh-maintenance`, `review-checker-change`, `check-maintenance-record`, `self-check` |
| Validation | Standard-library local smoke tests in `tests/test_skillguard_local.py` |
| Release mode | Source-only GitHub release; no binary or packaged CLI artifact is promised |

Full local command surface:

`commands`, `route-task`, `inventory`, `plan-skill`, `generate-skill`, `generate-suite`, `scan-global-skills`, `build-global-registry`, `check-global-registry`, `resolve-global-skill`, `render-global-prompt`, `install-global-prompt`, `check-global-prompt`, `refresh-global-router`, `check-json-schema`, `compile-contract`, `check-contract`, `select-route`, `start-run`, `advance-run`, `check-run`, `close-run`, `init-target`, `init-suite`, `mark`, `check-skill`, `check-suite`, `check-skill-contract`, `check-suite-map`, `check-suite-contract`, `check-fixture-manifest`, `check-work-contract`, `check-run-record`, `check-check-manifest`, `fixture-test`, `detect-stale-evidence`, `refresh-maintenance`, `review-checker-change`, `check-maintenance-record`, `check-ai-judgment`, `check-report`, `check-workflow-report`, `make-closure`, `self-check`, and `write-report`.

This list is a local dispatch surface, not packaged CLI installation proof.

## Core Capabilities

### Runtime Contract Executor

SkillGuard can create or validate `.skillguard/work-contract.json` and `.skillguard/check_manifest.json` for a target skill. The contract records:

- integration mode: `native-integrated`, `hybrid-extension`, or `skillguard-runtime`;
- route options and route-selection rules;
- required phases such as intake, inventory, evidence, checks, and closure;
- required evidence for each phase;
- required check ids and local check scripts;
- quality floors, freshness rules, and closure rules;
- claim boundaries and forbidden shortcuts.

The runtime command family then uses that contract to select a route, create a run record, enforce phase order, check evidence, and block closure when the run does not satisfy the declared work.

### Native-Aware Skill Upgrade

SkillGuard can strengthen existing skills without replacing their original path.

For a skill with a native route/check system, the contract should use `native-integrated` or `hybrid-extension` and include native bindings. Each SkillGuard phase should point to the native route and native check evidence that proves the phase.

For a skill without any native path, SkillGuard may provide the runtime route itself through `skillguard-runtime`.

### Global Router Registry

SkillGuard can maintain a user-level registry of installed or repository-local skills. The registry is a selection aid and prompt-projection layer. It can help choose a skill and point the agent to the target skill's own `SKILL.md`, work contract, check manifest, or native route bindings.

The global router is not a mandatory pre-execution gate for every skill invocation, and it does not replace target skill checks.

### Evidence Freshness And Closure

SkillGuard keeps stale evidence visible. It can inspect evidence-bearing JSON artifacts, verify file hashes and route bindings, report stale records, and refresh supported metadata only when explicitly requested.

Closure should name:

- target and route;
- scope and decision;
- direct evidence;
- deterministic checks;
- judgment checks, when any;
- skipped checks;
- blockers;
- residual risk;
- claim boundary.

### Skill And Suite Scaffolding

SkillGuard includes controlled generation commands for new skills and suites:

- `plan-skill` previews a no-write skill blueprint from a repository-local idea file.
- `generate-skill` creates a bounded draft skill scaffold from a valid blueprint.
- `generate-suite` creates a bounded suite scaffold and child skill records from a valid suite blueprint.

These commands block unsafe paths and conflicting existing files. Generated scaffolds still need review and current checks before being treated as accepted.

## Quick Start

Run commands from the repository root.

List the current local command surface:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py commands
```

Check SkillGuard itself:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py self-check --target .agents/skills/skillguard
```

Create or refresh a work contract for a target skill:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py compile-contract --target .agents/skills/skillguard --write
python .agents/skills/skillguard/scripts/skillguard.py check-contract --target .agents/skills/skillguard
```

Select a route and start a run:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py select-route --target .agents/skills/skillguard --task "Audit the target skill before closure"
python .agents/skills/skillguard/scripts/skillguard.py start-run --target .agents/skills/skillguard --route audit --task "Audit the target skill before closure"
```

Advance and check a run before closure:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py advance-run --run .agents/skills/skillguard/.skillguard/runs/<run-file>.json --phase evidence --status pass --evidence direct_evidence --check check_evidence
python .agents/skills/skillguard/scripts/skillguard.py check-run --run .agents/skills/skillguard/.skillguard/runs/<run-file>.json --complete
python .agents/skills/skillguard/scripts/skillguard.py close-run --run .agents/skills/skillguard/.skillguard/runs/<run-file>.json --decision accepted
```

Refresh a global router registry for an explicit skill root and Codex home:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py refresh-global-router --skill-root .agents/skills --codex-home .skillguard/test_codex_home --output-dir .skillguard/global-router
python .agents/skills/skillguard/scripts/skillguard.py check-global-prompt --registry .skillguard/global-router/global_registry.json --codex-home .skillguard/test_codex_home
```

Run the local smoke tests:

```powershell
python tests/test_skillguard_local.py
```

## Main Workflows

### 1. Audit An Existing Skill

Use this path when you want to know whether a skill has a clear activation boundary, current maintained records, and safe public claims.

```powershell
python .agents/skills/skillguard/scripts/skillguard.py check-skill --target .agents/skills/skillguard
```

Expected result: a JSON report with checks, failures, blockers, skipped checks, residual risk, and a claim boundary.

### 2. Add Runtime Gates To A Skill

Use this path when the target skill needs a runnable contract before work begins.

```powershell
python .agents/skills/skillguard/scripts/skillguard.py compile-contract --target <target-skill> --write
python .agents/skills/skillguard/scripts/skillguard.py check-contract --target <target-skill>
```

If the target skill already has native routes or checks, review the generated contract and bind SkillGuard phases to those native routes and checks. Do not leave a duplicate SkillGuard execution route next to the original system.

### 3. Govern A Skill Run

Use this path to prevent skipped work or weak closure claims.

```powershell
python .agents/skills/skillguard/scripts/skillguard.py select-route --target <target-skill> --task "<task>"
python .agents/skills/skillguard/scripts/skillguard.py start-run --target <target-skill> --route <route-id> --task "<task>"
python .agents/skills/skillguard/scripts/skillguard.py check-run --run <run-record> --complete
python .agents/skills/skillguard/scripts/skillguard.py close-run --run <run-record> --decision checked
```

### 4. Maintain Global Skill Routing

Use this path when installed or repository-local skill routing metadata changes.

```powershell
python .agents/skills/skillguard/scripts/skillguard.py refresh-global-router --skill-root <skill-root> --codex-home <codex-home> --output-dir <router-output>
python .agents/skills/skillguard/scripts/skillguard.py check-global-registry --registry <router-output>/global_registry.json --codex-home <codex-home>
python .agents/skills/skillguard/scripts/skillguard.py resolve-global-skill --registry <router-output>/global_registry.json --task "<task>"
```

This confirms the registry and managed prompt block are current for the supplied roots. It does not prove future AI behavior or target skill execution.

### 5. Review Stale Evidence

Use this path when an old report might no longer match the files it claims to cover.

```powershell
python .agents/skills/skillguard/scripts/skillguard.py detect-stale-evidence --input <evidence-json>
python .agents/skills/skillguard/scripts/skillguard.py refresh-maintenance --input <evidence-json> --dry-run
```

Only supported metadata fields are refreshed, and dry-run mode does not rewrite evidence artifacts.

## Validation

The current repository has direct local evidence for:

- command dispatch enumeration;
- JSON schema parsing for maintained records;
- skill and suite static checks;
- runtime contract commands;
- global router registry and prompt projection commands;
- positive and negative fixture cases;
- generation and maintenance command behavior;
- standard-library local smoke tests.

Run the strongest local check with:

```powershell
python tests/test_skillguard_local.py
```

For release or repository-maintenance work, also run:

```powershell
python -m flowguard project-audit --root .
```

## What SkillGuard Is Not

SkillGuard does not guarantee that Codex will always choose the right skill.

SkillGuard does not prove AI correctness. It can require evidence and make skipped work visible, but judgment still belongs to the responsible maintainer.

SkillGuard does not currently provide a packaged CLI, hosted service, external integration, binary release artifact, or automatic GitHub publication workflow.

SkillGuard's local smoke tests do not prove broad fixture coverage, package publication, suite automation, legal compliance, release quality, or code-contract validation beyond the exact files and commands checked.

## Public Boundary

Public files in this repository should not contain:

- credentials, tokens, private keys, or environment secrets;
- private task text, private transcripts, or internal coordination notes;
- local absolute paths or user-specific machine details;
- runtime logs, caches, exports, backups, or local generated state;
- screenshots or examples with private data;
- release, package, test, or external-service claims that current files do not prove.

When a capability is absent, the README should say it is absent rather than turning it into a planned or implied feature.

## Repository Layout

```text
SkillGuard/
  README.md
  CHANGELOG.md
  VERSION
  pyproject.toml
  LICENSE
  AGENTS.md
  references/
  examples/
  tests/
  assets/readme-hero/
  .agents/
    skills/
      skillguard/
        SKILL.md
        assets/
          schemas/
          templates/
        scripts/
        fixtures/
        .skillguard/
      skillguard-global-router/
        SKILL.md
        .skillguard/
  .flowguard/
```

## Release History

See [CHANGELOG.md](CHANGELOG.md).

## License

SkillGuard is licensed under the MIT License. See [LICENSE](LICENSE).
