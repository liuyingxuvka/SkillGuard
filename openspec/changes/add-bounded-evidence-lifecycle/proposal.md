## Why

SkillGuard currently preserves complete native stdout/stderr as uncompressed content-addressed blobs but has no reachability-based lifecycle or bounded cleanup path. Repeated FlowGuard supervision therefore accumulated nearly one gigabyte of mechanically duplicated evidence even though the target-declared checks and semantic receipts were already stable.

The correction must preserve target sovereignty: SkillGuard verifies only the checks, producer sharing, projections, obligations, and evidence domains explicitly declared by the target. It must not infer that two commands are semantically interchangeable, invent missing depth, or reinterpret target-domain output.

## What Changes

- Add a bounded evidence lifecycle with one canonical owner-evidence store per maintenance unit, compressed immutable stream objects, logical-content verification, reachability classification, explicit pins, read-only audit/planning, quarantine-first collection, and separately authorized purge.
- Require explicit target/compiler declarations when one producer execution supports several semantic check projections; identical command text, arguments, names, or outputs never authorize implicit sharing.
- Preserve bounded diagnostic head/tail text in receipts while storing complete stdout/stderr once as compressed sidecars that replay verifies against the uncompressed logical hash.
- Make one exact per-producer current-head authority and one exact current-aggregation authority per maintenance-unit member/profile, plus closure receipts, installation/release pins, retained failure diagnostics, and their transitive dependencies lifecycle roots; historical heads and aggregations no longer remain current by directory membership, and unreachable objects become visible candidates rather than silently accumulating.
- Keep normal validation limited to its own temporary-stage cleanup. Permanent evidence deletion remains a planned, freshness-checked lifecycle operation and never occurs as a hidden validation side effect.
- Remove current installation-projection leakage from source-only checks and suppress Python bytecode generation during installed smoke checks.
- **BREAKING**: replace the current uncompressed sidecar authority with the new compressed evidence-object schema and direct current lifecycle commands. Existing evidence remains archive-only and is not accepted through a compatibility reader or fallback path.

## Capabilities

### New Capabilities

- `bounded-evidence-lifecycle`: Compressed immutable evidence objects, lifecycle roots and states, deterministic audit/plan/apply/purge operations, quarantine and replay safety, and temporary-stage cleanup boundaries.

### Modified Capabilities

- `native-depth-evidence-identity`: Require explicit producer-to-semantic-check projection declarations and prohibit command-similarity inference while retaining exact target-declared identities.
- `universal-execution-depth`: Bind current owner receipts and closure replay to the new logical/storage evidence identities, lifecycle roots, and source-only installation projection boundary.

## Impact

- Affected runtime: `skillguard_v2` check planning, owner execution, receipt replay, sidecar persistence, TestMesh aggregation, installation projection, and CLI routing.
- Affected contracts: source/compiled contract schemas, check manifest, owner receipts, evidence-object metadata, lifecycle plans, and release pins.
- Affected maintenance surfaces: SkillGuard self-hosting contract/model, FlowGuard validation-composition model, tests, README/operator documentation, installed consumer projection, and release workflow.
- No target-domain evaluator moves into SkillGuard, and graduated consumer skills receive no SkillGuard evidence store, receipts, lifecycle state, or maintenance contract.
