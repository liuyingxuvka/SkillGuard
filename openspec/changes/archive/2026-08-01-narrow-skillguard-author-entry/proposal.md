## Why

SkillGuard's author-side behavior is mature, but its always-loaded skill prompt and managed global block repeat a large maintenance manual and route index before a specific author task is known. The `route-task` command also still allows keyword scoring to stand in for declared applicability, which can make an efficient entry less reliable rather than more precise.

## What Changes

- Keep SkillGuard strictly author-side and reduce its public `SKILL.md` to the author boundary, minimum typed task facts, route selection, first action, conditional reference loading, terminals, hard gates, and claim boundary.
- Upgrade the existing `ROUTE_TASK_ROUTE_REGISTRY` into the single compact route authority with positive and forbidden predicates, required inputs, read/write authority, first command, next reference, and claim boundary.
- Replace semantic keyword-score selection with explicit route id or program-evaluated typed task facts; zero, many, stale, conflicting, and forbidden cases block visibly.
- Generate a machine-readable route index from that registry and test its parity with the human entry shell.
- Generate full validated-template-pack guidance into a conditional reference while leaving only a trigger and pointer in each target's `SKILL.md`.
- Reduce the managed global SkillGuard prompt to an author-only trigger and private registry pointer; remove the repeated route catalog and template lifecycle prose from the always-loaded global surface.
- Preserve every existing target-owned semantic check, clean-consumer boundary, no-fallback rule, and final validation gate.

## Capabilities

### New Capabilities

- `skillguard-author-entry-loading`: Defines fact-derived author-route admission, conditional reference loading, route-index generation, prompt budgets, validated-template-pack projection, and the compact global maintainer prompt.

### Modified Capabilities

None.

## Impact

Affected surfaces include SkillGuard's public and global-router skill entries, route registry and `route-task` behavior, prompt/template projection, target prompt generation, fixtures and tests, FlowGuard models, SkillGuard's self-host contract, documentation, and patch version metadata. Ordinary consumer skills and official OpenSpec remain independent.
