## Why

SkillGuard currently treats pointer, installation, report, runtime-fingerprint,
and receipt bookkeeping as if they were functional behavior. A small source
change can therefore reopen unrelated checks and prevent a terminal current
result from ever being reusable. This change makes functional closure the
small, affected-only contract and keeps release/provenance work separate.

## What Changes

- Define one functional freshness identity containing only behavior-bearing
  source, contract, model, test, oracle, and required dependency inputs.
- Remove timeout, output-path, receipt, report, pointer, and platform metadata
  from functional identity while retaining them for attempt/provenance data.
- Build one immutable receipt index per invocation and reuse it for all
  freshness decisions instead of rescanning every receipt for every candidate.
- Allow a terminal current parent composed entirely of exact-current leaves to
  close with zero new producers; reject fabricated, foreign, stale, or
  tampered evidence.
- Make exact-current hits read-only: no new receipt, head, lease, or run
  directory is written.
- Deduplicate semantically identical native owners and make fast/focused/full
  profiles genuinely different; installation and release remain explicit
  operations rather than routine functional gates.
- Route Agent Workflow Rehearsal only for explicit complexity/risk triggers.
- **BREAKING**: no compatibility reader, fallback authority, alternate receipt
  store, or second currentness path is added.

## Capabilities

### New Capabilities

- `functional-closure`: affected functional freshness, finite parent closure,
  zero-execution terminal reuse, and profile routing.

### Modified Capabilities

- None. Existing author/depth specifications remain valid; this change adds a
  direct-current closure contract used by their native owners.

## Impact

Affected modules include runtime fingerprinting, contract compilation, closure
and receipt indexing, check execution, test-mesh orchestration, self-host
readback, router documentation, generated owner declarations, and focused
regression tests. Installation and publication projections remain separate
and continue to include their required provenance inputs.
