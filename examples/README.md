# SkillGuard Local Examples

These examples show the current local script dispatch surface against fixture files in this repository. Run them from the repository root.

They are examples of bounded local checks only. They do not prove broad fixture coverage, packaged CLI installation, suite automation, package publication, release readiness, code-contract validation, or future AI behavior.

## Single-Skill Check

Run a maintained positive single-skill fixture:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py check-skill --target .agents/skills/skillguard/fixtures/good_single_skill
```

Interpretation:

- `decision: pass` means the current local checker found no failures or blockers for that fixture path.
- The result is bounded by its `claim_boundary` and the current files loaded during the invocation.
- It is not a package-installation or release claim.

## Suite Check

Run the maintained positive suite fixture:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py check-suite --suite-root .agents/skills/skillguard/fixtures/good_suite/suite --suite-map .agents/skills/skillguard/fixtures/good_suite/suite/suite-map.json --suite-contract .agents/skills/skillguard/fixtures/good_suite/suite/suite-contract.json --member-root .agents/skills
```

Interpretation:

- `decision: pass` means the suite map, suite contract, member path, direct evidence references, child closure rollup, unsafe-claim scan, and claim-boundary checks succeeded for this fixture.
- A suite-level result should not hide stale, missing, blocked, failed, or skipped child evidence.
- This is a local static suite check, not suite automation.

## Fixture Manifests

Run the positive fixture manifest:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py fixture-test --manifest .agents/skills/skillguard/fixtures/fixture-manifest.json
```

Run static-analysis negative fixtures:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py fixture-test --manifest .agents/skills/skillguard/fixtures/bad_static/fixture-manifest.json
```

Run suite, closure, stale-evidence, and policy negative fixtures:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py fixture-test --manifest .agents/skills/skillguard/fixtures/bad_suite_stale/fixture-manifest.json
```

Interpretation:

- Positive fixture cases are expected to observe `pass`.
- Negative fixture cases are expected to observe the declared `fail` or `block` decision for their isolated defect.
- A `fixture-test` command can return `decision: pass` when all expected failures were observed as expected.
- The `fixture_class_counts` field is useful for confirming which expected case classes ran.

## Self-Check

Run the local self-check:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py self-check --target .agents/skills/skillguard
```

Interpretation:

- `decision: pass` means the current local self-check found no failures or blockers in the required SkillGuard files, command boundary wording, policy references, public-safety scan, and unsafe-claim scan.
- Self-check is local and static. It does not replace human review for release, publication, compliance, or semantic adequacy decisions.

## Standard-Library Test Script

Run the local standard-library test script and write parseable evidence:

```powershell
python tests/test_skillguard_local.py --json-output .agents/skills/skillguard/fixtures/evidence_outputs/standard_library_tests_current.json
```

Interpretation:

- The script uses Python `unittest`, `subprocess`, and `json` from the standard library.
- It does not require network access, pytest, package installation, or external services.
- The JSON output records the bounded local command checks and keeps the same conservative claim boundary as the examples above.
