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

Run routing conflict negative fixtures:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py fixture-test --manifest .agents/skills/skillguard/fixtures/bad_routing/fixture-manifest.json
```

Run simple generation fixtures:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py fixture-test --manifest .agents/skills/skillguard/fixtures/simple_generation/fixture-manifest.json
```

Run complex generation fixtures:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py fixture-test --manifest .agents/skills/skillguard/fixtures/complex_generation/fixture-manifest.json
```

Run runtime-contract fixtures:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py fixture-test --manifest .agents/skills/skillguard/fixtures/runtime_contract/fixture-manifest.json
```

Run global-router fixtures:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py fixture-test --manifest .agents/skills/skillguard/fixtures/global_router/fixture-manifest.json
```

Interpretation:

- Positive fixture cases are expected to observe `pass`.
- Negative fixture cases are expected to observe the declared `fail` or `block` decision for their isolated defect.
- A `fixture-test` command can return `decision: pass` when all expected failures were observed as expected.
- The `fixture_class_counts` field is useful for confirming which expected case classes ran.
- Routing fixtures also report `routing_conflict_blocker_codes` in each route-task fixture result so stable conflict classes can be checked without relying only on prose blocker text.
- Runtime-contract fixtures prove the explicit local command family can compile and check a contract, select a route, check complete runs, accept a complete run, and observe expected failures or blocks for missing contracts, hollow contracts, missing routes, ambiguous routes, missing evidence, skipped phases, stale evidence, quality downgrades, closure overclaims, parent suite child-failure hiding, and early closure.
- Global-router fixtures exercise scan, registry refresh, managed prompt install/check, and route resolution against explicit local roots and a test Codex home only.
- Simple generation fixtures run the public `plan-skill` and `generate-skill` path inside marker-owned temporary workspaces, validate current generated evidence, and clean up generated files after each case.
- Complex generation fixtures add richer generated-content assertions, malformed blueprint blocking, generated-output corruption checks, stale-evidence integration, and non-target mutation probes on top of the same public generation path.

## Runtime Contract

Create or refresh the runtime contract files for a target skill:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py compile-contract --target .agents/skills/skillguard --write
```

Check the contract before using it:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py check-contract --target .agents/skills/skillguard
```

Select the route before starting work:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py select-route --target .agents/skills/skillguard --task "Audit the target skill before closure"
```

Start a run record bound to the selected route:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py start-run --target .agents/skills/skillguard --route audit --task "Audit the target skill before closure"
```

Advance phases only after evidence and checks exist:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py advance-run --run .agents/skills/skillguard/.skillguard/runs/<run-id>.json --phase intake --status checked --check check_route
```

Check and close only when the run is complete:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py check-run --run .agents/skills/skillguard/.skillguard/runs/<run-id>.json --complete
python .agents/skills/skillguard/scripts/skillguard.py close-run --run .agents/skills/skillguard/.skillguard/runs/<run-id>.json --decision accepted
```

Interpretation:

- `compile-contract` builds the local work contract, check manifest, check script stubs, and run directory.
- `select-route` must choose exactly one route; missing, ambiguous, or unsupported routes block before work starts.
- `check-run --complete` fails skipped phases, missing evidence, stale evidence, missing passing check ids, blockers, and quality failures.
- `close-run` does not make prose-only completion pass and does not broaden a checked-only contract into accepted closure. It only closes inside the evidence-backed contract boundary.

## Task Routing

Route one task request to a current public SkillGuard command family:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py route-task --task "Create a draft skill scaffold from a Skill Blueprint"
```

Route with an explicit current route hint:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py route-task --task "Review suite records and member evidence." --route-hint check-suite
```

Arguments:

- `--task` supplies one task request directly.
- `--input` supplies a repository-local JSON object with `task` and optional `route_hint`.
- `--route-hint` may name a current route id, route node id, or command family.
- `--output` writes the JSON result under the SkillGuard skill root; `-` prints to stdout.

Interpretation:

- `decision: pass` means the command selected one current public route from the local route registry.
- `decision: block` means the input was missing, ambiguous, unsupported, malformed, path-unsafe, or used conflicting options; inspect `routing_conflict_blockers` for stable `blocker_class`, `blocker_code`, conflicting fields or candidates, and recommended resolution.
- Conflict blockers cover conflicting task/input sources, incompatible route hints, mutually exclusive routing flags, equal route candidates, stale route identifiers, invalid path/config combinations, and requested responsibility mismatches.
- `route-task` does not invoke generators, run target checks, create files, expose private runtime material, or make a closure claim.

## Global Router

Refresh the global SkillGuard router against explicit local roots and a test Codex home:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py refresh-global-router --skill-root .agents/skills --codex-home .skillguard/test_codex_home --output-dir .skillguard/global-router
```

Check the generated registry and installed managed prompt block:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py check-global-registry --registry .skillguard/global-router/global_registry.json --skill-root .agents/skills
python .agents/skills/skillguard/scripts/skillguard.py check-global-prompt --registry .skillguard/global-router/global_registry.json --codex-home .skillguard/test_codex_home
```

Resolve a task to the global router skill before handing off to that skill's own contract:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py resolve-global-skill --registry .skillguard/global-router/global_registry.json --task "Refresh the global SkillGuard router prompt and registry"
```

Interpretation:

- `refresh-global-router` scans current skill roots, writes a registry and prompt projection, inserts or replaces only the managed SkillGuard block in `AGENTS.md`, and checks that block against the registry hash.
- `check-global-registry` blocks or fails stale registry claims instead of treating old route indexes as current.
- `check-global-prompt` blocks missing, duplicated, corrupted, or stale managed prompt blocks.
- `resolve-global-skill` selects a current skill and returns route-document paths; it does not execute the selected skill or replace the selected skill's own gates.

## Evidence Freshness

Check whether a current evidence output still matches the files and route metadata it recorded:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py detect-stale-evidence --input .agents/skills/skillguard/fixtures/evidence_outputs/fixture_test_bad_routing_current.json
```

Interpretation:

- `decision: pass` means every comparable path, hash, route, command, fixture, generated-artifact, or OpenSpec status binding supplied by the input artifact still matches the current repository state.
- `decision: block` means at least one input is stale or unverifiable; inspect `stale_evidence_blockers` for the artifact id, expected current binding, observed stale binding, stale reason, and recommended refresh action.
- Missing freshness metadata is treated as unverifiable evidence rather than accepted current evidence.
- `detect-stale-evidence` reads evidence and referenced artifacts only. It does not refresh records, rerun fixtures, invoke generators, inspect sealed FlowPilot bodies, or make closure decisions.

## Maintenance Refresh

Plan a refresh for an explicit evidence output before rewriting any metadata:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py refresh-maintenance --input .agents/skills/skillguard/fixtures/evidence_outputs/fixture_test_bad_routing_current.json
```

Execute only supported metadata refreshes after reviewing the dry-run plan:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py refresh-maintenance --input .agents/skills/skillguard/fixtures/evidence_outputs/fixture_test_bad_routing_current.json --execute
```

Interpretation:

- `decision: pass` in dry-run mode means the command loaded the explicit evidence artifacts and reported any approved refresh actions without rewriting those artifacts.
- `decision: pass` in execute mode means supported stale metadata was refreshed and the post-refresh freshness check found no remaining stale bindings in the supplied artifacts.
- `decision: block` means at least one target is unrefreshable by metadata rewrite, such as missing metadata, invalid paths, or a missing generated artifact that must be restored by its owning workflow.
- `refresh-maintenance` does not rerun target commands, regenerate missing artifacts, inspect sealed FlowPilot bodies, expose sibling role text, or make closure decisions.

## Checker-Change Review

Review a checker change against an approved repository-local baseline before accepting current evidence:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py review-checker-change --baseline .agents/skills/skillguard/fixtures/checker_change/current-baseline.json --evidence .agents/skills/skillguard/fixtures/evidence_outputs/self_check_current.json
```

Interpretation:

- `decision: pass` means the supplied baseline, current command surface, route registry, fixture expectations, evidence freshness, public-boundary scan, and no-mutation check did not expose a checker-change blocker.
- `decision: block` means a checker binding was removed, renamed, weakened, stale, missing metadata, fixture expectations changed, public-boundary wording leaked private or unsupported material, or supplied evidence is stale.
- `review-checker-change` is read-only for baselines, fixtures, evidence, and source files. It does not refresh evidence, rerun target checkers, inspect sealed FlowPilot bodies, expose sibling role text, or make closure decisions.

## Maintenance Record Schema

Validate a canonical maintenance record or supported legacy SkillGuard command output:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py check-maintenance-record --input .agents/skills/skillguard/fixtures/evidence_outputs/review_checker_change_current.json
```

Interpretation:

- `decision: pass` means the command found a canonical `maintenance_record` or normalized a supported legacy SkillGuard command output into the canonical public schema.
- `decision: block` means the record is missing required public fields, uses an incompatible schema version, contains stale legacy aliases, has malformed blocker rows, mismatches current route or command bindings, or includes private/sealed text in public maintenance fields.
- `check-maintenance-record` does not rewrite legacy artifacts, refresh stale evidence, inspect sealed FlowPilot bodies, expose sibling role text, or make closure decisions.

## Skill Blueprint Preview

Run `plan-skill` with a repository-local skill idea JSON file:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py plan-skill --input examples/skill-idea.json
```

Input shape:

```json
{
  "skill_name": "example-review-helper",
  "description": "Use when a maintainer needs a bounded review helper for repository notes.",
  "target_path": ".agents/skills/example-review-helper",
  "purpose": "Create a review helper skill plan with explicit evidence and claim boundaries.",
  "workflow_mode": "create",
  "safe_edit_mode": "no_write"
}
```

Interpretation:

- `decision: pass` means the command parsed the idea JSON, checked the repository-relative target boundary, and emitted a Skill Blueprint preview.
- `plan-skill` does not create or modify the declared target path.
- The blueprint is planning evidence only; target file creation, deterministic target checks, reviewer judgment, and closure require separate current evidence.

## Skill Scaffold Generation

After reviewing a Skill Blueprint, run `generate-skill` against a repository-local blueprint JSON file:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py generate-skill --input path/to/blueprint-output.json
```

Interpretation:

- `decision: pass` means the command parsed the Skill Blueprint, checked the target write boundary, created missing scaffold files, verified required file presence, and ran `check-skill` against the final generated target.
- Generated skills include `.skillguard/work-contract.json`, `.skillguard/check_manifest.json`, `.skillguard/checks/*.py`, and `.skillguard/runs/`; post-generation validation runs both `check-skill` and `check-contract`.
- Successful generation records `global_router_refresh.required: true`; run `refresh-global-router`, `check-global-registry`, and `check-global-prompt` before claiming the new skill is available through default global routing.
- Differing existing files block generation; identical existing files are preserved for idempotent reruns.
- Generated scaffold files remain draft evidence only. Run target checks and reviewer judgment before any accepted status or closure claim.

## Suite Scaffold Generation

After reviewing a Suite Blueprint, run `generate-suite` against a repository-local blueprint JSON file:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py generate-suite --input examples/suite-blueprint.json
```

Interpretation:

- `decision: pass` means the command parsed the Suite Blueprint, checked the suite target write boundary, created missing suite and child scaffold files, verified required file presence, and ran `check-suite` plus child `check-skill` checks against the final generated paths.
- Differing existing files or required directory path conflicts block generation before suite or child files are written; identical existing files are preserved for idempotent reruns.
- Generated suite and child files remain draft evidence only. Run `check-suite`, child `check-skill` commands, and reviewer judgment before any accepted status or closure claim.

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
