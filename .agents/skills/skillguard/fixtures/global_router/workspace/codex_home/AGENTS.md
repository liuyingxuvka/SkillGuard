

<!-- BEGIN MANAGED SKILLGUARD GLOBAL ROUTER -->
## SkillGuard Global Router

- Before using a Codex skill for non-trivial skill, prompt, process, or SkillGuard-family work, consult the SkillGuard global router registry when it is present.
- If the registry or this managed block is missing or stale, run `skillguard.py refresh-global-router` before making a skill-routing claim.
- Route order: select the target skill from the registry, read the selected `SKILL.md`, then follow that skill's `.skillguard/work-contract.json` and `.skillguard/check_manifest.json` or native route bindings.
- Do not let this global router replace a target skill's own hard gates, checks, evidence requirements, or closure boundary.
- router_skill_id: skillguard-global-router
- registry_hash: 4D10B9F7BEFBE12DC39499644F81D4259199BE0EBEF0931AE3EB6077BE29AE23
- registry_path: .agents/skills/skillguard/fixtures/global_router/workspace/global_router/global_registry.json

### Current Route Index
- `skillguard` -> .agents/skills/skillguard/SKILL.md (default_route=audit, integration=skillguard-runtime)
- `skillguard-global-router` -> .agents/skills/skillguard-global-router/SKILL.md (default_route=audit, integration=skillguard-runtime)
- `complex-generation-review-helper` -> .agents/skills/skillguard/fixtures/complex_generation/workspace/generate-skill-complex-public-input/complex-generation-review-helper/SKILL.md (default_route=audit, integration=skillguard-runtime)

Claim boundary: this block is a routing projection only. It does not prove runtime checker execution, fixture coverage, CLI checks, tests, suite automation, package publication, code-contract validation, release readiness, or future AI behavior without separate current evidence.
<!-- END MANAGED SKILLGUARD GLOBAL ROUTER -->
