

<!-- BEGIN MANAGED SKILLGUARD GLOBAL ROUTER -->
## SkillGuard Global Router

- Use the SkillGuard global router registry only for skill-selection, skill-maintenance, prompt/process, or SkillGuard-family routing claims when it is present; do not make it a mandatory pre-execution gate for every skill invocation.
- If the registry or this managed block is missing or stale, run `skillguard.py refresh-global-router` before making a global skill-routing claim.
- Handoff order: select the target skill from the registry when selection help is needed, read the selected `SKILL.md`, then use that skill's own `.skillguard/work-contract.json`, `.skillguard/check_manifest.json`, or native route bindings.
- Do not let this global router replace a target skill's own hard gates, checks, evidence requirements, or closure boundary.
- router_skill_id: skillguard-global-router
- registry_hash: 56B5C919BEB3957A36A8BB8E01E5FECC2F2C19438E4651E772D93877A3A3F8E0
- registry_path: .agents/skills/skillguard/fixtures/global_router/workspace/global_router/global_registry.json

### Current Route Index
- `skillguard` -> .agents/skills/skillguard/SKILL.md (default_route=audit, integration=skillguard-runtime)
- `skillguard-global-router` -> .agents/skills/skillguard-global-router/SKILL.md (default_route=audit, integration=skillguard-runtime)

Claim boundary: this block is a routing projection only. It does not prove runtime checker execution, fixture coverage, CLI checks, tests, suite automation, package publication, code-contract validation, release readiness, or future AI behavior without separate current evidence.
<!-- END MANAGED SKILLGUARD GLOBAL ROUTER -->
