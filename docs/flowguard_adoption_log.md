## flowguard-project-adopt - FlowGuard project adopt record update

- Project: SkillGuard
- Trigger reason: target project uses FlowGuard and needs durable AGENTS/version records
- Status: completed
- Skill decision: used_flowguard
- Started: 2026-06-26T11:08:18+00:00
- Ended: 2026-06-26T11:08:18+00:00
- Duration seconds: 0.000
- Commands OK: True

### Model Files
- none recorded

### Commands
- none recorded

### Findings
- FlowGuard repository recorded: https://github.com/liuyingxuvka/FlowGuard
- FlowGuard package version recorded: 0.52.2
- FlowGuard schema version recorded: 1.0

### Counterexamples
- none recorded

### Friction Points
- none recorded

### Skipped Steps
- Project adoption record does not replace executable model checks, tests, replay, or closure evidence.

### Risk Evidence Summary
- none recorded

### Next Actions
- Rerun affected FlowGuard models/tests before broad completion claims when behavior, tests, or version records change.

## skillguard-global-router-maintenance - Preserve FlowGuard model evidence and refresh SkillGuard global router local smoke outputs

- Project: SkillGuard
- Trigger reason: user approved maintenance cleanup after global-router coverage review
- Status: completed
- Skill decision: used_flowguard_development_process_flow
- Started: 2026-06-27T05:07:25+00:00
- Ended: 2026-06-27T05:09:19+00:00
- Commands OK: True

### Model Files
- `.flowguard/development_process_flow/skillguard_global_router_model.py`

### Commands
- `python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"`
- `python -c "import importlib.metadata as m; print(m.version('flowguard'))"`
- `python .flowguard/development_process_flow/skillguard_global_router_model.py`
- `python -m flowguard project-audit --root .`
- `python tests/test_skillguard_local.py --json-output .agents/skills/skillguard/fixtures/evidence_outputs/standard_library_tests_current.json`

### Findings
- Preserved the SkillGuard global router development-process model as a repository FlowGuard artifact.
- Regenerated repository-local global-router smoke output under the ignored root `.skillguard` directory.
- Refreshed standard library evidence after removing stale simple_generation workspace output.
- FlowGuard package version 0.52.2 and schema version 1.0 matched the project record.

### Counterexamples
- none recorded

### Friction Points
- A stale generated simple_generation workspace caused `standard_library_tests_current.json` to record a failed run until the local fixture workspace was cleaned and tests were rerun.

### Skipped Steps
- No release, package publication, GitHub push, or commit was performed.

### Risk Evidence Summary
- FlowGuard model returned `development_process_flow_green_can_continue`.
- FlowGuard project audit passed.
- Standard library tests reported 65 tests OK.

### Next Actions
- Keep `.flowguard/development_process_flow/skillguard_global_router_model.py` with future global-router behavior changes.
- Rerun the model, project audit, global-router fixture checks, and standard library tests before broad completion claims after route, prompt, or installed-skill changes.

## skillguard-native-contract-executor-upgrade - Upgrade SkillGuard into native-aware runtime contract executor and re-audit upgraded skills

- Project: SkillGuard
- Trigger reason: user required SkillGuard to upgrade existing skill routes instead of adding parallel execution paths
- Status: completed
- Skill decision: used_flowguard_development_process_flow
- Started: 2026-06-27T08:29:00+00:00
- Ended: 2026-06-27T09:04:52+00:00
- Commands OK: True

### Model Files
- `.flowguard/development_process_flow/skillguard_runtime_contract_model.py`

### Commands
- `python -m py_compile .agents/skills/skillguard/scripts/checker_engine.py`
- `python tests/test_skillguard_local.py --json-output .agents/skills/skillguard/fixtures/evidence_outputs/standard_library_tests_current.json`
- `python .agents/skills/skillguard/scripts/skillguard.py self-check --target .agents/skills/skillguard --output fixtures/evidence_outputs/self_check_current.json`
- `python .agents/skills/skillguard/scripts/skillguard.py fixture-test --manifest .agents/skills/skillguard/fixtures/runtime_contract/fixture-manifest.json --output fixtures/evidence_outputs/fixture_test_runtime_contract_current.json`
- `python .agents/skills/skillguard/scripts/skillguard.py check-contract --target .agents/skills/skillguard --output fixtures/evidence_outputs/check_contract_self_current.json`
- `python .agents/skills/skillguard/scripts/skillguard.py check-contract --target-root ../release-worktrees/FlowPilot-main --target skills/flowpilot --output fixtures/evidence_outputs/check_contract_flowpilot_current.json`
- `python .agents/skills/skillguard/scripts/skillguard.py scan-global-skills --skill-root ~/.codex/skills --output fixtures/evidence_outputs/scan_global_user_skills_current.json`
- `python .flowguard/development_process_flow/skillguard_runtime_contract_model.py`
- `python -m flowguard project-audit --root .`
- `openspec status --change harden-skillguard-native-contract-executor --json`
- `python .agents/skills/skillguard/scripts/skillguard.py fixture-test --manifest .agents/skills/skillguard/fixtures/runtime_contract/fixture-manifest.json`

### Findings
- Added structured `phase_native_bindings` so native-integrated and hybrid contracts bind each SkillGuard phase to native route/check evidence.
- Added read-only `--target-root` support for external target contract checks without expanding default write scope.
- FlowPilot contract now binds SkillGuard phases to FlowPilot native route/check evidence without replacing the FlowPilot entrypoint or router.
- Installed user skill scan found 64 user-created skills current: 45 native-integrated, 17 hybrid-extension, and 2 skillguard-runtime.
- Missing contracts were limited to system skills and SkillGuard test fixtures.
- Public evidence uses `user_skill_audit_summary_current.json`; detailed local per-skill scan outputs are intentionally excluded from publication.
- FlowPilot FlowGuard project adoption record was repaired separately and its audit passed.

### Counterexamples
- none recorded

### Friction Points
- The first OpenSpec verification contract used an obsolete `fixture-test` flag and was corrected to the current `--manifest` interface.
- A transient output path mistake created a nested `.agents` directory under the skill target; it was removed before final validation.
- FlowPilot smoke checks touched line-ending metadata on simulation JSON files without content changes; those noise-only modifications were restored.

### Skipped Steps
- No GitHub push, release, tag, or publication was performed in this validation step.
- System skills and SkillGuard fixture skills were not converted because they are not user-created upgraded skill targets.

### Risk Evidence Summary
- FlowGuard runtime-contract model returned `development_process_flow_green_can_continue`.
- FlowGuard project audit passed.
- Standard library tests reported 65 tests OK.
- Runtime-contract fixture manifest reported pass.
- SkillGuard self contract, FlowPilot contract, installed SkillGuard contract, installed FlowPilot contract, and installed global skill scan reported pass.

### Next Actions
- Before publishing, perform final git status review across SkillGuard and FlowPilot, then commit/push on `master`/`main` only.
- Keep SkillGuard's global scanner enforcing `phase_native_bindings` so future native/hybrid skill upgrades cannot silently create parallel routes.

## deepen-skillguard-contract-coverage - Deepen SkillGuard contract coverage, README gates, installed-skill audit, and global routing correction

- Project: SkillGuard
- Trigger reason: user found README skill misuse, indicating SkillGuard's previous coverage was too shallow
- Status: completed
- Skill decision: used_flowguard_development_process_flow
- Started: 2026-06-27T16:24:00+00:00
- Ended: 2026-06-27T16:39:30+00:00
- Commands OK: True

### Commands
- `python .agents/skills/skillguard/scripts/skillguard.py check-readme-release --repo .`
- `python .agents/skills/skillguard/scripts/skillguard.py audit-installed-skills --root ~/.codex/skills`
- `python tests/test_skillguard_local.py`
- `python .agents/skills/skillguard/scripts/skillguard.py resolve-global-skill --registry ~/.codex/skillguard-global-router/global_registry.json --task "README release task"`
- `python .agents/skills/skillguard/scripts/skillguard.py compile-contract --target .agents/skills/skillguard-global-router --write --force`
- `python .agents/skills/skillguard/scripts/skillguard.py start-run --target .agents/skills/skillguard-global-router --route audit`
- `python .agents/skills/skillguard/scripts/skillguard.py check-depth --target .agents/skills/skillguard-global-router`
- `python ~/.codex/skills/skillguard/scripts/skillguard.py audit-installed-skills --root ~/.codex/skills`
- `python ~/.codex/skills/skillguard/scripts/skillguard.py refresh-global-router --skill-root ~/.codex/skills --codex-home ~/.codex --output-dir ~/.codex/skillguard-global-router`
- `python ~/.codex/skills/skillguard/scripts/skillguard.py check-global-prompt --registry ~/.codex/skillguard-global-router/global_registry.json --codex-home ~/.codex`
- `python ~/.codex/skills/skillguard/scripts/skillguard.py resolve-global-skill --registry ~/.codex/skillguard-global-router/global_registry.json --task "README release task"`
- `python ~/.codex/skills/skillguard/scripts/skillguard.py resolve-global-skill --registry ~/.codex/skillguard-global-router/global_registry.json --task "FlowPilot route task"`

### Findings
- Added executable `check-readme-release` for bilingual README mirror, text-to-image hero provenance, README model evidence, version consistency, command-surface wording, and public-boundary checks.
- Added `audit-installed-skills` so installed user-created skills can be rechecked with deep contract logic without ad hoc shell scripts.
- Fixed global route scoring so README/hero/bilingual tasks route to `readme-showcase-writer` even when the target project name is SkillGuard.
- Recompiled `skillguard-global-router`'s source work contract with deep fields and created a current run record after installed audit found its old shallow contract.
- Synchronized installed SkillGuard and SkillGuard Global Router copies to the source skill directories and removed explicitly identified extra old run-record files.
- Installed audit returned 64 audited user skills with `deep-pass:64` after the fix.

### Friction Points
- The first `check-readme-release` implementation treated a PNG as UTF-8 text while building file evidence; it was corrected to record image byte count and hash.
- A PowerShell copy command used `-LiteralPath` with a wildcard and did not copy; it was rerun with explicit child enumeration.
- Global route resolution initially selected `skillguard` for a README task because the project name appeared in the request; the route scoring rule now suppresses the SkillGuard-specific bias for README tasks.

### Risk Evidence Summary
- README release gate passed on the current repository.
- Standard library tests reported 68 tests OK before the final verification run.
- Installed SkillGuard audit reported `deep-pass` for 64 user skills.
- Global prompt check passed with registry hash `8516119C84D564E1C1EC955BB999092EFD2536AD0553B621CC380CEAA443CA73`.
- README route resolved to `readme-showcase-writer`; FlowPilot route resolved to `flowpilot` with `native-integrated`.

### Skipped Steps
- No GitHub push, tag, or release was performed in this validation step.
- FlowGuard project audit and OpenSpec verification remain to be rerun after the final edits.

### Next Actions
- Run final full verification, OpenSpec verification, project audit, privacy diff, commit on master, push, and publish the next `0.1.x` release only after all checks stay current.

## skillguard-universal-target-lock-final-validation - Final pre-release validation for universal target-lock SkillGuard upgrade

- Project: SkillGuard
- Trigger reason: user required SkillGuard to deeply cover every covered skill, including SkillGuard itself, without replacing target-native routes
- Status: completed
- Skill decision: used_flowguard_development_process_flow
- Started: 2026-06-28T02:01:00Z
- Ended: 2026-06-28T02:05:15Z
- Commands OK: True

### Findings
- Universal target-lock extraction and validation are active for SkillGuard itself: target rules, routes, workflow stages, native checks, test gaps, coverage matrix, runtime lock policy, and source requirements are checked by `check-depth`.
- Installed SkillGuard audit reported 64 user-created installed skills with `deep-pass:64`.
- FlowPilot remained `native-integrated` and passed `check-depth`, preserving its own route/check surface instead of becoming a SkillGuard-owned parallel route.
- README release gate passed after README/CHANGELOG text was aligned with the universal target-lock capability.
- Global router refresh and `check-global-prompt` passed with registry hash `7F9792ABD7EC99E3068EAD5DE0483D75DEE2FC88B7ABC350A866C95B8B49CB3C`.
- Negative fixtures proved missing target lock, README shallow coverage, stale/missing run evidence, and parallel route risk are blocked.

### Risk Evidence Summary
- `pytest` passed: 70 tests and 12 subtests.
- SkillGuard source `check-depth` passed with 51 coverage rows.
- README release gate passed and inspected README, VERSION, pyproject, changelog, hero asset, prompt, design note, and README model evidence.
- Installed audit passed for 64 user-created skills with `deep-pass:64`.
- FlowGuard project audit passed for package `0.52.2` and schema `1.0`.
- OpenSpec strict validation passed for `deepen-skillguard-contract-coverage`.
- Deep-contract fixture manifest passed with `expected_fail:4`; runtime-contract fixture manifest passed with `expected_pass:5`, `expected_fail:11`, `blocker_condition:3`.

### Skipped Steps
- No GitHub push, tag, release object creation, package artifact build, or binary asset publication was performed in this validation step.
- This record does not prove future peer-agent changes to installed skill files after the checked timestamp.

### Next Actions
- Review git diff and privacy boundary, commit scoped changes on `master`, push `master`, create or verify the correct GitHub release for `v0.1.5`, then perform KB postflight.

## skillguard-covered-skill-sequential-audit - Sequentially inspect every covered installed skill for real target-lock depth

- Project: SkillGuard
- Trigger reason: user challenged that rerunning tests alone does not prove deeper coverage
- Status: completed
- Skill decision: used_flowguard_development_process_flow
- Ended: 2026-06-28T02:08:10Z

### Findings
- Sequential covered-skill audit produced one row per covered installed user skill, not only an aggregate test result.
- All 64 covered installed user skills had `deep-pass`, complete target-lock status, non-empty target rules, non-empty route inventory, non-empty workflow stage inventory, non-empty coverage matrix, and `may_define_parallel_execution_route=false`.
- Only `skillguard` and `skillguard-global-router` remained `skillguard-runtime` with `run_record_required=true`; native-integrated and hybrid-extension skills retained `run_record_required=false`.
- FlowPilot specifically remained `native-integrated` with 45 source requirements, 45 target rules, 6 route inventory rows, 1 workflow-stage inventory row, 16 native checks, 45 coverage matrix rows, 5 phase native bindings, `parallel_allowed=false`, and `run_record_required=false`.

### Risk Evidence Summary
- This sequential audit confirms coverage depth by contract content counts, not by merely rerunning the test suite.
- Each covered skill row was checked for source requirements, target rules, route inventory, workflow stages, native checks, coverage matrix, phase bindings, parallel route flag, run-record policy, and ok status.

### Skipped Steps
- The full per-skill CSV was reviewed in-terminal and summarized here; it was not committed as a public evidence artifact to avoid publishing local installed-skill inventory details.

## skillguard-covered-skill-final-depth-reaudit - Repeat per-skill deep contract audit after user challenged test-only coverage claims

- Project: SkillGuard
- Trigger reason: user reminded that rerunning tests does not make SkillGuard coverage deeper
- Status: completed
- Skill decision: used_flowguard_development_process_flow
- Started: 2026-06-28T02:20:57Z
- Ended: 2026-06-28T02:23:16Z
- Commands OK: True

### Findings
- Reran installed FlowPilot `check-depth` after peer-agent activity and confirmed it is `native-integrated`, not a SkillGuard-owned parallel route.
- Parsed FlowPilot's installed contract fields directly: 45 source requirements, 45 target rules, 6 route rows, 1 workflow-stage row, 16 native checks, 45 coverage matrix rows, 5 phase native bindings, `may_define_parallel_execution_route=false`, `may_define_skillguard_runtime_route=false`, and `run_record_required=false`.
- Reran installed audit and parsed all 64 covered skill contracts: `deep-pass=64`, `bad_rows=0`, `hybrid-extension=17`, `native-integrated=45`, `skillguard-runtime=2`.
- Direct checks for `readme-showcase-writer` and `frontend-design` passed, confirming README-specific bilingual/hero/model gates and UI-design target rules are present in their own contracts.
- Global prompt freshness check passed against registry hash `7F9792ABD7EC99E3068EAD5DE0483D75DEE2FC88B7ABC350A866C95B8B49CB3C`.

### Risk Evidence Summary
- This record answers the user's concern that tests alone do not prove depth: every covered installed skill was checked for source requirements, target rules, routes, stages, native checks, coverage matrix, phase bindings, parallel-route policy, and run-record policy.
- The claim boundary remains current local installed files at the checked timestamp; it does not guarantee future peer-agent edits after the final audit.

### Friction Points
- The aggregate installed audit alone was not treated as enough evidence; the follow-up parser inspected each target contract's content fields to prove depth rather than only test success.
- Parallel agents can still change installed skill files after a passing check, so the release workflow must repeat installed audit immediately before commit/release.

### Skipped Steps
- No GitHub push, tag, or release was performed in this validation step.
- No public per-skill installed inventory artifact was committed; local user skill inventory stayed in terminal evidence and summarized counts.

### Next Actions
- Run final repo tests, README release gate, OpenSpec strict validation, privacy scan, short-delay installed audit, then commit on `master` and publish `v0.1.5` only if evidence remains current.

## skillguard-v015-final-prepublish-validation - Final validation, privacy review, installed-skill recheck, and release-boundary review before v0.1.5 publication

- Project: SkillGuard
- Trigger reason: release only after deep SkillGuard coverage and user-requested sequential installed-skill audit remained current
- Status: completed
- Skill decision: used_flowguard_development_process_flow
- Started: 2026-06-28T02:25:36Z
- Ended: 2026-06-28T02:32:30Z
- Commands OK: True

### Findings
- Final pre-commit validation passed after the last documentation/log edits.
- Tests passed with 70 tests and 12 subtests; source `py_compile`, SkillGuard self `check-depth`, README release gate, OpenSpec strict validation, deep-contract fixtures, runtime-contract fixtures, and installed skill audit all passed.
- A short-delay installed audit still reported 64 covered user skills with `deep-pass:64`, reducing the chance that parallel-agent edits immediately stale the installed-skill claim.
- Privacy and stale-release-target scans returned no matches for local machine paths or obsolete public release-target wording in active public release files.
- GitHub repository ruleset `Protect default branch` is active for `~DEFAULT_BRANCH` with `deletion` and `non_fast_forward` rules; `v0.1.5` tag and release did not exist before publication.

### Risk Evidence Summary
- Current evidence supports a source-only `v0.1.5` release from `master` after commit; it does not prove future installed-skill state after additional peer-agent writes.
- No package binary assets are part of this release contract.

### Friction Points
- The first parallel `pytest` invocation timed out, so `pytest` was rerun alone with a longer timeout and passed.
- A fixed-string stale-version scan had to be rerun with PowerShell-safe quoting; the rerun returned no matches.

### Skipped Steps
- No binary asset build was run because this release is source-only.
- GitHub push, tag, and release creation were not performed before this record; they are the next release steps.

### Next Actions
- Commit scoped changes on `master`, push `master`, create annotated `v0.1.5` tag, push the tag, create GitHub release, verify release, then record KB postflight.

## repair-skillguard-deep-pass-semantics - Repair deep-pass semantics after shallow README evidence was found

- Project: SkillGuard
- Trigger reason: user found that README depth and installed-skill `deep-pass` claims were inconsistent under the current checker
- Status: in_progress
- Skill decision: used_flowguard_development_process_flow
- Started: 2026-06-28T03:20:00Z
- Latest evidence: 2026-06-28T03:27:16Z
- Commands OK: True

### Findings
- Started OpenSpec change `repair-skillguard-deep-pass-semantics` to tighten `deep-pass` from structural coverage to target-specific semantic coverage.
- FlowGuard package/schema preflight passed with package `0.52.2`, schema `1.0`, and project audit `pass`.
- OpenSpec strict validation passed for the new change artifacts before implementation.
- The previous installed-skill `deep-pass` aggregate is now treated as stale under the stricter standard until the upgraded checker reruns.

### Risk Evidence Summary
- This record proves only pre-implementation routing and validation setup.
- It does not prove the stricter checker until code, tests, installed audit, and release checks are rerun.

### Friction Points
- The prior `deep-pass` wording overclaimed what the checker proved; this repair separates structural field coverage from target-specific semantic coverage.

### Skipped Steps
- No checker code, installed skill files, git push, tag, or release was completed at this stage.

### Next Actions
- Harden `check-depth`, `check-readme-release`, installed audit publication-status reporting, fixtures, tests, SkillGuard self evidence, installed sync, final audit, then publish only after current verification.

## repair-skillguard-deep-pass-semantics-final-validation - Complete stricter deep-pass repair before v0.1.6 publication

- Project: SkillGuard
- Trigger reason: user required SkillGuard to deeply cover itself and covered user skills, while preserving native routes and separating local coverage from GitHub publication
- Status: completed
- Skill decision: used_flowguard_development_process_flow
- Started: 2026-06-28T03:20:00Z
- Ended: 2026-06-28T03:55:16Z
- Commands OK: True

### Findings
- `check-depth` now treats `deep-pass` as target-specific semantic coverage and requires evidence ids in coverage rows instead of accepting generic field presence alone.
- `check-readme-release` now blocks stale README model evidence and requires current-version README Showcase Writer artifacts: fact ledger, capability claim matrix, narrative structure plan, and gap ledger.
- Installed-skill audit reports local coverage separately from GitHub publication: 64 audited user skills, `deep-pass:64`, `publication_status not-a-git-repo:64`, failures `0`, blockers `0`.
- High-risk direct checks for SkillGuard, SkillGuard global router, FlowPilot, README showcase writer, UI/design skills, and release skills all passed under the upgraded checker.
- OpenSpec verify passed after correcting the verification contract's path model; the earlier failure was a verification-contract issue, not an implementation pass.

### Risk Evidence Summary
- Current local evidence supports a source-only `v0.1.6` patch release from `master`; no binary asset build is required because the README says binary artifacts are not provided.
- Installed-skill audit proves local target-lock coverage only; it does not prove individual GitHub publication for installed skill directories.

### Friction Points
- The formal verification contract had to be corrected because OpenSpec runs from the planning root while SkillGuard CLI resolves target arguments from the SkillGuard repository root.
- Large JSON command output is truncated in the terminal; key release evidence is summarized as counts and pass/fail status instead of committing local installed-skill inventory details.

### Skipped Steps
- No binary artifact build was run because this release is source-only.
- GitHub push, tag, release creation, and post-publication verification are not covered by this record; they are the next release steps.

### Next Actions
- Run final privacy and remote-release checks, commit scoped changes on `master`, push `master`, create annotated `v0.1.6` tag, create GitHub release, verify remote release, rerun post-publication verification, and record KB postflight.


## flowguard-project-upgrade - FlowGuard project upgrade record update

- Project: skillguard-functional-closure-src
- Trigger reason: target project uses FlowGuard and needs durable AGENTS/version records
- Status: completed
- Skill decision: used_flowguard
- Started: 2026-07-10T03:36:29+00:00
- Ended: 2026-07-10T03:36:29+00:00
- Duration seconds: 0.000
- Commands OK: True

### Model Files
- none recorded

### Commands
- none recorded

### Findings
- FlowGuard repository recorded: https://github.com/liuyingxuvka/FlowGuard
- FlowGuard check-engine version recorded: 0.53.1
- FlowGuard schema version recorded: 1.0

### Counterexamples
- none recorded

### Friction Points
- none recorded

### Skipped Steps
- Project adoption record does not replace executable model checks, tests, replay, or closure evidence.
- Artifact/model/test upgrade scan was scoped out by records-only mode.

### Risk Evidence Summary
- none recorded

### Next Actions
- Rerun affected FlowGuard models/tests before broad completion claims when behavior, tests, or version records change.
