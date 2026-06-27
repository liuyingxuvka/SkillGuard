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
