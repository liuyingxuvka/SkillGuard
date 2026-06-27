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
