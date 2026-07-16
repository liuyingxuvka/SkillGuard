# Global Router Executable Contract

Read this reference when running or maintaining the router's one current
contract. The contract supervises the existing SkillGuard CLI; it never
implements a second scanner, registry builder, prompt installer, route selector,
converter, or fallback reader.

## Function and route map

| Function | Contract route | Native owner |
| --- | --- | --- |
| Scan skill roots | `route:scan-global-skills` | `scan-global-skills` |
| Build registry | `route:build-global-registry` | `build-global-registry` |
| Check registry | `route:check-global-registry` | `check-global-registry` |
| Render prompt projection | `route:render-global-prompt` | `render-global-prompt` |
| Install managed prompt | `route:install-global-prompt` | `install-global-prompt` |
| Check managed prompt | `route:check-global-prompt` | `check-global-prompt` |
| Resolve and hand off | `route:resolve-global-skill` | `resolve-global-skill` |
| End-to-end refresh | `route:refresh-global-router` | `refresh-global-router` |

Every selected function also enters `route:shared-supervision`, which runs the
current FlowGuard child model and native positive/negative router fixtures.

## Work-package layout

Pass a task workspace as the current supervisor's `target_root`. The applicable
native action writes its outputs under this portable layout:

```text
target_root/
├── codex_home/
│   └── AGENTS.md
└── global_router/
    ├── skill_scan.json
    ├── global_registry.json
    ├── global_prompt_projection.json
    ├── registry_check.json
    ├── prompt_check.json
    ├── route_resolution.json
    └── refresh_report.json
```

Only files declared by the selected route are required. The end-to-end refresh
route requires the scan, registry, projection, AGENTS prompt, and refresh
report. Keep private or machine-specific scan roots inside the task work
package; do not copy them into tracked skill files.

## Evidence boundary

- Record a witnessed action for every task-specific CLI invocation that scans, writes, installs, or resolves against the supplied work package.
- The router declares its command-surface and FlowGuard-model checks in the current contract. SkillGuard freezes that exact inventory and requires one current immutable terminal-success receipt for each declared check.
- SkillGuard does not treat the router as a special target category, infer route meaning from check names, or require a paired validation pattern. Router-domain expectations remain inside the router's own model and native checks.
- Let the native check adapter re-run registry freshness, prompt freshness, and the fixed router smoke handoff. The adapter must block unless the registry points at the exact current `.skillguard/compiled-contract.json` and `.skillguard/check-manifest.json` pair.
- Any former authority shape is rejected. Ordinary maintenance rewrites the target directly into the current source/compiled/manifest trio; the router has no migration, conversion, or fallback success path.
- A passing router contract does not execute the selected target skill or prove publication, a different machine's installed state, or future AI behavior.
