# SkillGuard author-repository rules

This is the public SkillGuard source and an explicit author-maintenance
workspace. Keep edits scoped, portable, evidence-backed, and safe for dirty or
parallel work. Never reset, delete, install, publish, or overwrite outside the
current authorized scope.

## Identity and boundaries

- Repository: https://github.com/liuyingxuvka/SkillGuard
- Managed source: `.agents/skills/skillguard`; native owner=`skillguard`;
  maintenance unit=`unit:skillguard`; native route evidence is its `SKILL.md`.
- A consumer skill is independent. It contains no `.skillguard` receipts,
  author path, router/Portfolio state, author-only fixtures, or SkillGuard
  runtime dependency.
- Direct-current replacement is the only maintained format: no compatibility
  reader, fallback, migration, alias, dual manifest, or parallel authority.
- The target skill owns domain meaning, judgments, actions, native checks, and
  closure criteria. SkillGuard supervises author identity, owner evidence, and
  clean projection only.

## Route-first entry

Read the short `.agents/skills/skillguard/SKILL.md` first. Then query exactly one
current route and load only its selected reference:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py route-reference --route-id <route>
python .agents/skills/skillguard/scripts/skillguard.py maintainer-audit --root .
```

The complete route catalog remains in the generated
`.agents/skills/skillguard/references/skillguard-route-index.json`; ordinary
work must not preload it. Zero, many, stale, forbidden, or missing-input
matches block. No keyword score, declaration order, or fallback selects a
route. See `references/route_map_summary.md` for the compact map.

## Execution phase boundary

- Read/diagnose is read-only: no compile, lease, run directory, owner start,
  pointer write, installation, router refresh, or release write.
- Source-change freezes one maintenance unit, exact checks, evidence subjects,
  dependencies, private evidence root, toolchain, and one owner per check.
  It runs only the selected source checks and aggregation.
- `reuse_current` requires one exact current terminal receipt in the same unit;
  stale, failed, skipped, foreign, duplicate, timed-out, cancelled, or
  cleanup-unconfirmed evidence blocks.
- Installation/currentness, global-router refresh, and release are separate
  explicit claims. A source `full` profile never implies them.

## Source of truth and evidence

The current contract trio is `.skillguard/contract-source.json`,
`.skillguard/compiled-contract.json`, and `.skillguard/check-manifest.json`.
The current surface inventory and native route/check records are required for a
source claim. Reports, progress logs, checkboxes, and old receipts do not make
source authority current. After a timeout or cancellation, confirm the entire
descendant process tree is gone before accepting evidence.

## Explicit references

Use `references/skillguard-supervisor.md` for unit ownership and closure;
`skillguard-test-mesh.md` for affected/full execution; execution-records for
receipts; assurance-diagnostics for read-only blockers; target-installation for
explicit install/currentness; self-host for SkillGuard's own governed release;
and portfolio/project-adoption only when those routes are selected. Do not read
all route references, model history, logs, or receipt trees without a named
trigger.

## Short command index

```powershell
python .agents/skills/skillguard/scripts/skillguard.py route-reference --route-id <route>
python .agents/skills/skillguard/scripts/skillguard.py maintainer-audit --root .
python .agents/skills/skillguard/scripts/skillguard.py self-check --root .
python .agents/skills/skillguard/scripts/generate_route_index.py --json
```

These entrypoints produce scoped evidence only; report actual checks, receipts,
skipped/not-run obligations, blockers, residual risk, and claim boundary.

<!-- BEGIN MANAGED SKILLGUARD AUTHOR RULES -->
## SkillGuard author maintenance

This is an explicit SkillGuard author repository. This block is only a short admission pointer; the target skill keeps its domain route, judgment, actions, and native-check authority.

Canonical SkillGuard repository: https://github.com/liuyingxuvka/SkillGuard

Managed skills:
- `.skillguard/author-project.json` is the exact managed inventory (1 member(s)); each row binds one native owner, maintenance unit, and route-evidence path.
- The target skills keep domain-route, judgment, action, and native-check authority.

Before a source edit or validation, read the target `SKILL.md`, its native route/check contracts, and `references/skillguard-supervisor.md`.
Use one frozen maintenance unit, exact owner/check identities, private evidence roots, and current terminal receipts; missing, duplicate, foreign, stale, or cleanup-unconfirmed evidence blocks.

Validation policy: `skillguard.validation_execution_ownership.current`. It is direct-current only: no fallback, migration, alias, dual authority, or cross-unit receipt reuse.
Consumer projections contain no author contracts, receipts, router, Portfolio, or author-only runtime. Installation, global-router currentness, and release are separate explicit claims; read `references/skillguard-target-installation.md` and `references/skillguard-self-host.md` only for those routes.

Author audit command: `python <installed-skillguard>/scripts/skillguard.py maintainer-audit --root .`

This managed block is a routing and maintenance contract. It is not runtime, test, release, or future-behavior proof.
<!-- END MANAGED SKILLGUARD AUTHOR RULES -->
