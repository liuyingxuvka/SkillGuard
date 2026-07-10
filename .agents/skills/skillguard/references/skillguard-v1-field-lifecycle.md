# SkillGuard V1 Runtime Lifecycle

V1 is a lifecycle label only for the three former runtime-authority surfaces below. Other public schemas whose stable identifiers end in `.v1` remain current until separately versioned; their names alone do not make them legacy.

## Authority boundary

- `.skillguard/work-contract.json` and `.skillguard/check_manifest.json` are migration inputs only when V2 authority is absent.
- V1 `run_record` files and V1 closure records are read-only historical or diagnostic evidence. They never satisfy V2 receipts or closure profiles.
- When `.skillguard/contract-source.json` exists, the V1 commands `compile-contract`, `select-route`, `start-run`, `advance-run`, `check-run`, and `close-run` block before their legacy handlers execute.
- V1 validators remain available as bounded migration diagnostics. `make-closure` remains a bounded report utility and is not consumed by the V2 closure engine.

## Replacement map

- Work-contract routes, phases, obligations, evidence, checks, quality floors, closure rules, stale bindings, and hashes migrate to the FlowGuard model export, target binding source, compiled contract, and exact check manifest.
- Run-record phases, statuses, evidence, commands, skips, blockers, and closure decisions migrate to claimed runs, append-only events, stored check records, immutable receipts, replay, and closure receipts.
- Check-manifest checks, contract references, freshness watches, and output schemas migrate to exact V2 check declarations and current source, implementation, environment, and Guard-runtime fingerprints.

`skillguard_v2.field_lifecycle.build_v1_field_lifecycle_plan` expands every property path in all three V1 runtime schemas. A newly added top-level field has no default disposition and therefore blocks the lifecycle check until its replacement is explicit.

## Removal policy

Do not delete V1 artifacts portfolio-wide in one sweep. Each target removes them only after its local V2 model, contract, representative functional run, negative/recovery cases, and rollback evidence are current. This preserves local-first migration without allowing V1 fallback success.
