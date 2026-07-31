## Why

SkillGuard already has an operational assurance graph across contract source, compiled contract, exact check manifest, impact graph, receipts, and closure. The missing capability is a concise read-only explanation of why closure is blocked and whether target-declared mutation checks provide meaningful sensitivity evidence.

## What Changes

- Add a derived assurance-diagnostics report over existing authorities; do not add another AssuranceGraph schema or closure owner.
- Compute dependency-aware subset-minimal blocker bases and label them separately from minimum-cardinality optimization.
- Report blocker provenance, affected obligations, stale/missing/failed receipt state, and bounded next actions without weakening claims automatically.
- Admit mutation adequacy only when the target declares operators, applicability, equivalent-mutant disposition, oracle, thresholds, and native receipt; SkillGuard continues to supervise rather than invent target semantics.
- Add SkillGuard self-mutations for its own current contract and diagnostics behavior.
- Extend prompt/reference, CLI/runtime, FlowGuard contract model, SkillGuard contracts, tests, installation, and release evidence.

## Capabilities

### New Capabilities

- `skillguard-assurance-diagnostics`: Defines derived blocker-basis and target-owned mutation-adequacy diagnostics.

## Impact

Affected surfaces: SkillGuard v2 runtime/CLI, execution-depth and closure projections, prompt/references, FlowGuard model, contract sources, tests, installed author-side projection, README, version, and release metadata.
