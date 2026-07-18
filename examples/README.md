# SkillGuard local author-maintenance examples

These examples exercise the current source dispatcher from the repository
root. They are bounded local checks. They do not prove broad fixture coverage,
packaged installation, suite automation, package publication, release
readiness, code-contract validation, or future AI behavior.

## Inspect the command surface

```powershell
python .agents/skills/skillguard/scripts/skillguard.py commands
```

The list should contain author-only `maintainer-adopt`,
`maintainer-audit`, and `refresh-global-router`, plus the current checking,
Portfolio, installation-evidence, and reporting commands. It should not contain
retired ordinary installed-skill or consumer prompt routes.

## Route an author-maintenance task

```powershell
python .agents/skills/skillguard/scripts/skillguard.py route-task --task "Audit an explicitly maintained skill before graduation"
```

`route-task` selects only a current SkillGuard author-maintenance command
family. It does not choose a domain skill for ordinary consumer work and does
not execute the selected command.

## Preview and generate an author source

```powershell
python .agents/skills/skillguard/scripts/skillguard.py plan-skill --input examples/skill-idea.json
python .agents/skills/skillguard/scripts/skillguard.py generate-skill --input path/to/reviewed-blueprint.json
python .agents/skills/skillguard/scripts/skillguard.py generate-suite --input path/to/reviewed-suite-blueprint.json
```

`plan-skill` is no-write. Generation creates a maintained author scaffold.
Its consumer `SKILL.md` template contains target-owned native validation rules,
not SkillGuard runtime or router onboarding instructions.

## Check one maintained skill

```powershell
python .agents/skills/skillguard/scripts/skillguard.py check-skill --target .agents/skills/skillguard/fixtures/good_single_skill
python .agents/skills/skillguard/scripts/skillguard.py check-contract --target .agents/skills/skillguard
python .agents/skills/skillguard/scripts/skillguard.py check-depth --target .agents/skills/skillguard
```

`check-skill` checks the author source shape. `check-contract` checks the one
current author contract trio. `check-depth` compares declared promises,
target-owned checks, and current execution evidence. None of these commands
turns a contract file into proof that the checks ran.

## Check one same-unit suite

```powershell
python .agents/skills/skillguard/scripts/skillguard.py check-suite --suite-root .agents/skills/skillguard/fixtures/good_suite/suite --suite-map .agents/skills/skillguard/fixtures/good_suite/suite/suite-map.json --suite-contract .agents/skills/skillguard/fixtures/good_suite/suite/suite-contract.json --member-root .agents/skills
```

A deliberately inseparable suite may be one maintenance unit. The suite check
does not authorize evidence sharing with another maintenance unit.

## Run fixture manifests

```powershell
python .agents/skills/skillguard/scripts/skillguard.py fixture-test --manifest .agents/skills/skillguard/fixtures/fixture-manifest.json
python .agents/skills/skillguard/scripts/skillguard.py fixture-test --manifest .agents/skills/skillguard/fixtures/bad_static/fixture-manifest.json
python .agents/skills/skillguard/scripts/skillguard.py fixture-test --manifest .agents/skills/skillguard/fixtures/bad_suite_stale/fixture-manifest.json
python .agents/skills/skillguard/scripts/skillguard.py fixture-test --manifest .agents/skills/skillguard/fixtures/global_router/fixture-manifest.json
```

A negative fixture passes when the expected `fail` or `block` is observed. A
fixture result does not make an unlisted path current.

## Adopt an explicit author repository

```powershell
python .agents/skills/skillguard/scripts/skillguard.py maintainer-adopt --root <author-repository> --managed-skill "<skill-path>|<native-owner>" --skillguard-version 0.3.3
python .agents/skills/skillguard/scripts/skillguard.py maintainer-audit --root <author-repository>
```

Every member must already declare `repository_role:
skill_maintainer_source`, a maintenance unit, and member binding.
An ordinary business project is rejected before any `.skillguard` directory or
prompt block is created.

## Refresh the private author router

```powershell
python .agents/skills/skillguard/scripts/skillguard.py refresh-global-router --skill-root <explicit-author-skill-root> --codex-home <maintainer-codex-home> --output-dir <private-output>
python .agents/skills/skillguard/scripts/skillguard.py check-global-registry --registry <private-output>/global_registry.json
```

The composite refresh builds the private maintained-source registry and
maintainer prompt projection. The registry is not copied into consumers and
does not govern ordinary skill use.

## Review current evidence

```powershell
python .agents/skills/skillguard/scripts/skillguard.py detect-stale-evidence --input path/to/evidence.json
python .agents/skills/skillguard/scripts/skillguard.py review-checker-change --baseline .agents/skills/skillguard/fixtures/checker_change/current-baseline.json --evidence path/to/current-evidence.json
python .agents/skills/skillguard/scripts/skillguard.py check-maintenance-record --input path/to/maintenance-record.json
```

`detect-stale-evidence` is read-only. `review-checker-change` compares the
current command and route bindings to an approved baseline.
`check-maintenance-record` accepts only the current canonical record.

## Validate README and public boundaries

```powershell
python .agents/skills/skillguard/scripts/skillguard.py check-readme-release --repo .
python .agents/skills/skillguard/scripts/skillguard.py self-check --target .agents/skills/skillguard
```

These gates check current files and conservative claim wording. They do not
push Git, create a release, or publish a package.

## Build and install a clean consumer

```powershell
python .agents/skills/skillguard/scripts/skillguard_consumer_install.py --repository-root <author-repository> --skill-root <member-root> --stage-root <stage-root> --codex-home <consumer-codex-home> --prepare
python .agents/skills/skillguard/scripts/skillguard_consumer_install.py --repository-root <author-repository> --skill-root <member-root> --stage-root <stage-root> --codex-home <consumer-codex-home> --activate
```

The staged and installed skill must contain no `.skillguard`, SkillGuard
prompt, receipt, router, Portfolio, import, or command dependency. If
target-domain runtime still exists below `.skillguard/runtime`, preparation
blocks until it is relocated and checked.

## Portfolio as independent status aggregation

```powershell
python .agents/skills/skillguard/scripts/skillguard.py build-current-portfolio-registry --help
python .agents/skills/skillguard/scripts/skillguard.py audit-portfolio --help
python .agents/skills/skillguard/scripts/skillguard.py prepare-portfolio-run --help
python .agents/skills/skillguard/scripts/skillguard.py execute-portfolio-run --help
python .agents/skills/skillguard/scripts/skillguard.py assemble-portfolio-run --help
python .agents/skills/skillguard/scripts/skillguard.py graduate-portfolio --help
```

Portfolio aggregates one status per independently proven maintenance unit.
Unchanged units remain current because their own component identities remain
current, not because another skill lends them evidence.

## `standard-library` smoke script

```powershell
python tests/test_skillguard_local.py --json-output .agents/skills/skillguard/fixtures/evidence_outputs/standard_library_tests_current.json
```

The JSON output records only the checks that actually ran and preserves their
claim boundary.
