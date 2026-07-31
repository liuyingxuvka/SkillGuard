## Context

Existing SkillGuard authorities already form the operational assurance graph. Diagnostics must consume those immutable structures and receipts without becoming another closure path.

## Goals / Non-Goals

**Goals**

- Explain blocked closure with dependency-aware subset-minimal bases.
- Surface target-owned mutation sensitivity evidence.
- Provide bounded next actions while preserving target sovereignty.

**Non-Goals**

- No new authoritative graph, freshness engine, or closure receipt.
- No automatic claim weakening/removal.
- No universal target mutation policy invented by SkillGuard.

## Decisions

1. `AssuranceDiagnosticsReport` is a read-only projection over compiled contract, check manifest, impact graph, dependency receipts, and closure report fingerprints.
2. Blocker minimization uses a deterministic dependency-aware deletion pass and reports `subset_minimal`; `minimum_cardinality` is never claimed without exhaustive proof.
3. Every blocker records owner, obligation/check ids, receipt state, dependencies, and permitted next actions.
4. Target mutation evidence is applicable only when the target declares operators, oracle, applicability/equivalent disposition, threshold, and native current receipt.
5. SkillGuard self-mutations cover its own diagnostic invariants and current schema rejection.
6. Diagnostics cannot alter closure status, execute missing checks, or resume validation.

## Risks / Trade-offs

- Minimal explanations can hide alternate blockers; the report includes residual and alternate blocker counts.
- Equivalent mutants are domain judgments; absent target disposition blocks mutation adequacy rather than guessing.

## Migration Plan

Freeze the v0.4.2 baseline repairs and the derived diagnostics feature together, validate them under one v0.5.0 candidate identity, install that exact projection, and release v0.5.0. No intermediate v0.4.3 tag or parallel authority is created.
