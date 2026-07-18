# Global Router Author Contract

Read this reference only while maintaining SkillGuard source repositories. The
router is a private author tool: it inventories maintained source skills,
builds one current registry, validates that registry, and refreshes the private
author prompt. It is not copied into graduated consumer skills or ordinary
business projects.

## Public author command map

| Author operation | Contract route | SkillGuard command |
| --- | --- | --- |
| Scan explicit source roots | `route:scan-global-skills` | `scan-global-skills` |
| Build the private registry | `route:build-global-registry` | `build-global-registry` |
| Check the private registry | `route:check-global-registry` | `check-global-registry` |
| Refresh all private projections | `route:refresh-global-router` | `refresh-global-router` |

Prompt rendering, prompt installation, prompt checking, and route resolution
are internal steps of the composite refresh. They are deliberately not public
commands. The refresh must receive explicitly intended author source roots; it
must not discover installed consumer skills as an alternate authority.

Every selected operation also enters `route:author-supervision`, which runs the
current FlowGuard child model and the router's positive and negative checks.

## Private work-package layout

The author-side target root may contain:

```text
target_root/
├── codex_home/
│   └── AGENTS.md
└── global_router/
    ├── skill_scan.json
    ├── global_registry.json
    ├── global_prompt_projection.json
    ├── registry_check.json
    └── refresh_report.json
```

This layout is maintenance evidence. None of it belongs in a consumer skill
distribution. Machine-specific scan roots remain inside the private work
package and are never copied into tracked consumer files.

## Evidence boundary

- Every checked skill comes from an explicitly supplied
  `skill_maintainer_source` root.
- The current registry may point to author-side contract and manifest evidence,
  but a graduated consumer receives neither those files nor a registry lookup.
- Each maintenance unit owns its checks and receipts. Another unit cannot reuse
  them, even when a command happens to be textually identical.
- The composite refresh may update the maintainer computer's managed
  `AGENTS.md` block. Ordinary skill use never starts that maintenance action.
- No retired standalone prompt or resolver command is a valid route.
- A passing author-router contract does not execute a consumer skill, prove
  publication, prove another machine's state, or guarantee future AI behavior.
