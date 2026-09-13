## Context

The current author source has one native check graph but several checks consume
the same behavior-bearing files. Runtime fingerprints also include operational
metadata, and closure freshness repeatedly reloads receipt roots. Self-host
readback evaluates the same closure twice and insists on a new execution even
when every real leaf is already current. See `proposal.md` for the motivation.

## Goals / Non-Goals

**Goals:**

- Keep model/code/test alignment, parent-child and cross-owner coverage, and
  tamper/foreign/stale evidence gates.
- Make functional currentness affected-only, deterministic, and finite.
- Reuse exact terminal leaves without producing new evidence.
- Preserve installation, release, and platform provenance as explicit scopes.

**Non-Goals:**

- Removing content-addressed evidence, negative cases, model topology, or the
  one-owner-per-semantic-check rule.
- Adding a compatibility migration, fallback reader, background retry, or
  alternate authority.
- Claiming release or installed-projection confidence from local functional
  closure alone.

## Decisions

### 1. Separate functional and operational identities

Compile functional identity from behavior/model/contract/test/oracle inputs and
declared functional dependencies only. Keep timeout, output locations,
receipt/report/pointer metadata, host platform, and attempt timing in
provenance or execution identity. Installation/release compilers may continue
to use those fields in their own explicit identity.

### 2. One observation and one receipt index

At the beginning of a closure invocation, load and verify the immutable receipt
set once into `ReceiptIndex`. Candidate freshness queries use indexed owner,
subject, covered-id, and fingerprint keys. The index is invocation-local and
is never persisted as an authority or reused by a later invocation.

### 3. Zero-execution terminal closure

The parent compositor may publish a terminal local functional result when every
required real leaf has an independently verified exact-current terminal receipt
or a bounded delegated disposition. `executed_step_count` may be zero. The
composer still checks source identity once after producers (if any), verifies
the complete leaf set, and rejects foreign/tampered/aggregate-only evidence.

### 4. Read-only exact hits

An exact-current hit returns the existing immutable receipt and does not write a
new receipt, head, lease, run directory, or check attempt. A failed/stale/missing
owner is executed only by its declared native owner. Reuse and report/readback
operations never call an execution command.

### 5. Explicit depth and rehearsal routing

Fast mode performs declaration/affected functional checks; focused mode adds
affected model/test alignment; full mode adds the explicitly requested
cross-owner/release/install checks. Agent Workflow Rehearsal is admitted only
for an explicit rehearsal request, multi-owner/shared-write/irreversible effect,
route change, or post-validation write that invalidates the frozen plan.

## Risks / Trade-offs

- [Risk] A too-small functional identity could miss a real behavior change.
  -> Keep model, contract, oracle, test, and declared dependency components in
  the identity; unknown or ambiguous impact blocks instead of widening to
  run-all.
- [Risk] Zero-execution closure could accept copied aggregate evidence.
  -> Verify each leaf's native owner, covered ids, source/toolchain/dependency
  fingerprints, terminal status, and currentness before composition.
- [Risk] Installation/release drift may be overlooked in local work.
  -> Keep those claims explicit and fail them with visible `not_requested` or
  `not_run` dispositions; never relabel local closure as release.
- [Risk] Owner deduplication could merge different semantics.
  -> Merge only exact behavior/selectors/roles/dependency declarations;
  semantic check ids remain distinct and all required projections stay visible.

## Migration Plan

1. Add the functional-closure contract and focused tests.
2. Change identity, receipt-index, reuse, and compositor code under their
   existing native owners; update generated declarations once.
3. Remove duplicate owner execution and make profile/rehearsal routing explicit.
4. Run affected tests, compile `--check`, and perform one bounded functional
   closure followed by one zero-execution readback.
5. Keep historical receipts and temporary work evidence; publication excludes
   them. No compatibility migration is created.

## Open Questions

None.
